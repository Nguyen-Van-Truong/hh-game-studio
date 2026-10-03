"""AUTHORITY=0 GT07 preparation: fair choices never grant execution authority."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.jobs.dispatch_policy import (
    ActiveJob, Cursor, DispatchPolicyError, PendingJob, QueueLimits, select_next,
)


NOW = 1_000


def queued(job_id, *, project='project-a', session='session-a', sequence=1,
           deadline=10_000, resources=None, dependencies=()):
    return PendingJob(job_id, project, session, sequence, deadline,
                      resources if resources is not None else ('resource.' + job_id,),
                      dependencies)


def running(job_id, *, project='project-a', session='session-a', resources=None):
    # A draining/uncertain job is still represented here until its owner
    # proves it has released its slot and resource; it has no expiry shortcut.
    return ActiveJob(job_id, project, session,
                     resources if resources is not None else ('resource.' + job_id,))


class DispatchPolicyTests(unittest.TestCase):
    def choose(self, pending, *, active=(), receipts=None, cursor=None,
               now_ms=NOW, stopped=False, limits=QueueLimits()):
        return select_next(pending=pending, active=active,
                           receipts={} if receipts is None else receipts,
                           cursor=Cursor() if cursor is None else cursor,
                           now_ms=now_ms, stopped=stopped, limits=limits)

    def test_two_level_fairness_many_sessions_cannot_overwhelm_another_project(self):
        jobs = []
        sequence = 0
        for project, sessions, depth in [('project-a', 20, 2), ('project-b', 2, 6)]:
            for session in range(sessions):
                for index in range(depth):
                    sequence += 1
                    jobs.append(queued(f'{project}-s{session:02d}-{index}', project=project,
                                       session=f'session-{session:02d}', sequence=sequence))
        pending = tuple(reversed(jobs))  # Arrival tuple order is not durable FIFO order.
        cursor = Cursor()
        receipts = {}
        chosen = []
        for _ in range(12):
            selection = self.choose(pending, cursor=cursor, receipts=receipts)
            self.assertIsNotNone(selection)
            job = next(row for row in pending if row.job_id == selection.job_id)
            chosen.append((job.project_id, job.session_id, job.job_id))
            # Simulate the caller completing one admitted job and persisting
            # the cursor before its next coherent snapshot.
            pending = tuple(row for row in pending if row is not job)
            receipts[job.job_id] = 'COMMITTED'
            cursor = selection.next_cursor
        self.assertEqual([row[0] for row in chosen], ['project-a', 'project-b'] * 6)
        self.assertEqual([row[1] for row in chosen[::2]],
                         [f'session-{index:02d}' for index in range(6)])
        self.assertEqual([row[1] for row in chosen[1::2]],
                         ['session-00', 'session-01'] * 3)
        self.assertEqual([row[2] for row in chosen[1::2]],
                         [f'project-b-s{session:02d}-{index}'
                          for index in range(3) for session in range(2)])

    def test_blocked_dependency_head_preserves_shared_resource_fifo(self):
        older = queued('older', project='project-z', resources=('shared.blend',),
                       dependencies=('export-complete',), sequence=1)
        younger = queued('younger', resources=('shared.blend',), sequence=2)
        unrelated = queued('unrelated', project='project-b', sequence=3)
        pending = (younger, unrelated, older)
        selection = self.choose(pending)
        self.assertEqual(selection.job_id, unrelated.job_id)
        self.assertIsNone(self.choose((younger, older)))
        selection = self.choose((younger, older), receipts={'export-complete': 'COMMITTED'})
        self.assertEqual(selection.job_id, older.job_id)
        active = (running(older.job_id, project=older.project_id,
                          session=older.session_id, resources=older.resources),)
        self.assertIsNone(self.choose((younger,), active=active, cursor=selection.next_cursor))
        self.assertEqual(self.choose((younger,), cursor=selection.next_cursor).job_id, younger.job_id)

    def test_blocked_session_head_cannot_be_bypassed_on_an_unrelated_resource(self):
        head = queued('head', sequence=1, dependencies=('missing',))
        follower = queued('follower', sequence=2)
        other_session = queued('other-session', session='session-b', sequence=3)
        self.assertIsNone(self.choose((follower, head)))
        self.assertEqual(self.choose((follower, head, other_session)).job_id, other_session.job_id)

    def test_draining_active_job_keeps_resource_reserved_until_owner_releases_it(self):
        active = (running('draining', resources=('shared.tscn',)),)
        pending = (queued('next', project='project-b', resources=('shared.tscn',),
                          deadline=100_000),)
        self.assertIsNone(self.choose(pending, active=active, now_ms=50_000))
        self.assertEqual(self.choose(pending, now_ms=50_000).job_id, 'next')

    def test_global_active_quota_blocks_even_an_unrelated_ready_job(self):
        active = tuple(running(f'active-{index}', project=f'project-{index}',
                               session=f'session-{index}') for index in range(4))
        pending = (queued('ready', project='project-new'),)
        self.assertIsNone(self.choose(pending, active=active))
        self.assertEqual(self.choose(pending, active=active[:-1]).job_id, 'ready')

    def test_project_active_quota_does_not_block_another_project(self):
        limits = QueueLimits(active=3, project_active=1, session_active=1)
        active = (running('draining', session='old-session'),)
        capped = queued('capped', session='new-session', sequence=1)
        other = queued('other', project='project-b', sequence=2)
        selection = self.choose((capped, other), active=active, limits=limits)
        self.assertEqual(selection.job_id, other.job_id)
        self.assertEqual(self.choose((capped,), cursor=selection.next_cursor,
                                     limits=limits).job_id, capped.job_id)

    def test_session_active_quota_still_allows_another_session(self):
        active = (running('draining'),)
        capped = queued('capped', sequence=1)
        other = queued('other', session='session-b', sequence=2)
        self.assertEqual(self.choose((capped, other), active=active).job_id, other.job_id)
        self.assertEqual(self.choose((capped, other)).job_id, capped.job_id)

    def test_incoherent_active_snapshot_above_project_or_session_quota_is_rejected(self):
        cases = {
            'project': tuple(running(f'active-{index}', session=f'session-{index}')
                             for index in range(3)),
            'session': (running('one'), running('two')),
        }
        for name, active in cases.items():
            with self.subTest(scope=name), self.assertRaisesRegex(
                    DispatchPolicyError, 'DISPATCH_ACTIVE_OVER_QUOTA'):
                self.choose((queued('ready', project='project-new'),), active=active)

    def test_stop_returns_no_selection_and_does_not_mutate_inputs_or_cursor(self):
        pending = (queued('ready', dependencies=('done',)),)
        active = (running('draining', project='project-b'),)
        receipts = {'done': 'COMMITTED'}
        cursor = Cursor('project-b', (('project-a', 'session-old'), ('project-b', 'session-a')))
        before = deepcopy((pending, active, receipts, cursor))
        self.assertIsNone(self.choose(pending, active=active, receipts=receipts,
                                      cursor=cursor, stopped=True))
        self.assertEqual((pending, active, receipts, cursor), before)
        self.assertEqual(self.choose(pending, active=active, receipts=receipts,
                                     cursor=cursor).job_id, 'ready')

    def test_expired_head_is_excluded_at_exact_deadline_without_creating_receipt(self):
        head = queued('expired', sequence=1, deadline=NOW, resources=('shared',),
                      dependencies=('missing',))
        follower = queued('follower', sequence=2, resources=('shared',))
        receipts = {}
        self.assertIsNone(self.choose((follower, head), receipts=receipts, now_ms=NOW - 1))
        self.assertEqual(self.choose((follower, head), receipts=receipts).job_id, 'follower')
        self.assertEqual(receipts, {})  # Exclusion cannot forge durable terminal proof.

    def test_missing_failed_unknown_canceled_or_still_active_dependency_never_dispatches(self):
        pending = (queued('dependent', dependencies=('prerequisite',)),)
        for state in (None, 'REJECTED', 'UNKNOWN', 'CANCELED'):
            receipts = {} if state is None else {'prerequisite': state}
            with self.subTest(state=state):
                self.assertIsNone(self.choose(pending, receipts=receipts))
        self.assertIsNone(self.choose(pending, active=(running('prerequisite', project='project-b'),)))
        self.assertEqual(self.choose(pending, receipts={'prerequisite': 'COMMITTED'}).job_id,
                         'dependent')

    def test_every_prerequisite_requires_committed_proof(self):
        pending = (queued('dependent', dependencies=('first', 'second')),)
        self.assertIsNone(self.choose(pending, receipts={'first': 'COMMITTED'}))
        self.assertIsNone(self.choose(pending, receipts={'first': 'COMMITTED', 'second': 'UNKNOWN'}))
        self.assertEqual(self.choose(pending, receipts={'first': 'COMMITTED', 'second': 'COMMITTED'}).job_id,
                         'dependent')

    def test_duplicate_ids_and_ambiguous_enqueue_sequences_are_rejected(self):
        cases = {
            'duplicate pending id': ((queued('same'), queued('same', sequence=2)), ()),
            'duplicate active id': ((), (running('same'), running('same', session='session-b'))),
            'pending active collision': ((queued('same'),), (running('same'),)),
            'ambiguous sequence': ((queued('one'), queued('two', session='session-b')), ()),
        }
        for name, (pending, active) in cases.items():
            with self.subTest(conflict=name), self.assertRaisesRegex(
                    DispatchPolicyError, 'DISPATCH_ID_CONFLICT'):
                self.choose(pending, active=active)

    def test_terminal_job_ids_cannot_reenter_pending_or_active_work(self):
        for state in ('COMMITTED', 'REJECTED', 'CANCELED', 'UNKNOWN'):
            for pending, active in [((queued('done'),), ()), ((), (running('done'),))]:
                with self.subTest(state=state, active=bool(active)), self.assertRaisesRegex(
                        DispatchPolicyError, 'DISPATCH_ID_CONFLICT'):
                    self.choose(pending, active=active, receipts={'done': state})

    def test_duplicate_resource_claims_and_invalid_dependencies_fail_closed(self):
        invalid = [queued('bad', resources=('same', 'same')),
                   queued('bad', dependencies=('same', 'same'))]
        for job in invalid:
            with self.subTest(job=job), self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_JOB_INVALID'):
                self.choose((job,))
        with self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_DEPENDENCY_INVALID'):
            self.choose((queued('self', dependencies=('self',)),))
        with self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_RESOURCE_CONFLICT'):
            self.choose((), active=(running('one', resources=('shared',)),
                                    running('two', session='session-b', resources=('shared',))))

    def test_bounded_snapshot_caps_reject_without_dispatch_or_mutation(self):
        pending = (queued('one'), queued('two', sequence=2))
        before = deepcopy(pending)
        with self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_CAPACITY'):
            self.choose(pending, limits=QueueLimits(pending=1))
        self.assertEqual(pending, before)
        with self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_RECEIPTS_INVALID'):
            self.choose((queued('ready'),), receipts={'first': 'COMMITTED', 'second': 'COMMITTED'},
                        limits=QueueLimits(receipts=1))
        with self.assertRaisesRegex(DispatchPolicyError, 'DISPATCH_JOB_INVALID'):
            self.choose((queued('ready', resources=('first', 'second')),), limits=QueueLimits(resources=1))

    def test_same_snapshot_is_pure_and_caller_must_reserve_the_selected_resource(self):
        first = queued('first', resources=('shared',), sequence=1)
        second = queued('second', project='project-b', resources=('shared',), sequence=2)
        pending = (second, first)
        cursor = Cursor()
        receipts = {}
        before = deepcopy((pending, cursor, receipts))
        selected = self.choose(pending, cursor=cursor, receipts=receipts)
        self.assertEqual(selected.job_id, first.job_id)
        self.assertEqual(self.choose(pending, cursor=cursor, receipts=receipts), selected)
        # Cursor persistence alone is not a reservation or a lease grant.
        self.assertEqual(self.choose(pending, cursor=selected.next_cursor).job_id, first.job_id)
        self.assertEqual((pending, cursor, receipts), before)
        active = (running(first.job_id, project=first.project_id,
                          session=first.session_id, resources=first.resources),)
        self.assertIsNone(self.choose((second,), active=active, cursor=selected.next_cursor))
        self.assertEqual(self.choose((second,), cursor=selected.next_cursor).job_id, second.job_id)

    def test_caller_must_persist_returned_cursor_to_advance_fairness(self):
        pending = (queued('first'), queued('second', project='project-b', sequence=2))
        cursor = Cursor()
        selected = self.choose(pending, cursor=cursor)
        self.assertEqual(selected.job_id, 'first')
        self.assertEqual(cursor, Cursor())
        self.assertEqual(self.choose(pending, cursor=cursor), selected)
        self.assertEqual(self.choose(pending, cursor=selected.next_cursor).job_id, 'second')


if __name__ == '__main__':
    unittest.main()
