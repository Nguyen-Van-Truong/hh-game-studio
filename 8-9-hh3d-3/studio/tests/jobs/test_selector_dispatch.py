"""Real Windows queue/registry/file-selector integration; no game/engine proof."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.managed_fixture import ManagedFixtureOwner
from studio.host.core.selector_pipe import SelectorFixtureBroker
from studio.host.core.transport import epoch_ms
from studio.host.core.limits import payload_digest
from studio.host.jobs.durable_broker import JobRequest
from studio.host.jobs.queue_owner import QueueOwner, QueueOwnerError
from studio.host.jobs.selector_dispatch import SelectorDispatcher, DispatchError
from studio.protocol.core import Request, Status

SCOPES = frozenset({'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'})


@unittest.skipUnless(os.name == 'nt', 'Windows custody fixture required')
class SelectorDispatchTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='gt07-selector-'))).resolve()
        self.queue = self._queue()
        self.dispatch = SelectorDispatcher(self.queue)
        self.stack.callback(self.dispatch.close)

    def _remove_registry(self, local_id):
        import winreg
        path = BASE_PATH + '\\' + local_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            self.assertEqual(winreg.QueryValueEx(key, 'Format'),
                             (b'hh-registry-custody-1\0' + local_id.encode(), winreg.REG_BINARY))
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, path, winreg.KEY_WOW64_64KEY, 0)

    def _queue(self):
        parent = self.temp / 'queue'
        parent.mkdir()
        queue = QueueOwner.create(parent)
        self.stack.callback(self._remove_registry, queue.storage_id)
        self.stack.callback(queue.close)
        return queue

    def _project(self, name):
        parent = self.temp / name
        parent.mkdir()
        owner = ManagedFixtureOwner.create(parent, project_id=name, initial_revisions={
            'source_revision': 'source-0', 'source_sha256': 'a' * 64, 'game_revision': 'game-0'})
        self.stack.callback(self._remove_registry, owner.storage_id)
        self.stack.callback(owner.close)
        broker = SelectorFixtureBroker.from_managed(owner)
        self.stack.callback(broker.close)
        # Latest callback must detach before broker/owner teardown.
        self.stack.callback(self.dispatch.close)
        credential = broker.sessions.issue(scopes=SCOPES)
        session = broker.sessions.authenticate('Bearer ' + credential.bearer)
        self.dispatch.register(broker)
        return owner, broker, session

    def _request(self, broker, session, command='activate.one'):
        state = broker.selector.snapshot()
        lease = broker.dispatch('/v1/lease', {'project_id': broker.project_id, 'ttl_ms': 30_000}, session, control=False)
        payload = {'assets': {'scene': {'value': 'new', 'references': ['leaf']},
                              'leaf': {'value': 1, 'references': []}}, 'entrypoint': 'scene',
                   'expected_generation': state['generation'], 'expected_selection_hash': state['selection_hash'],
                   **{'expected_' + k: v for k, v in state['revisions'].items()}}
        operation, target = 'fixture.release.activate', {'stable_id': 'active-release'}
        request = Request(command, broker.project_id, operation, lease['lease_id'], lease['fencing_epoch'],
                          state['revisions']['game_revision'], target, payload,
                          payload_digest(operation, target, payload, 'hh-studio-0.1'), epoch_ms() + 20_000)
        return request

    def _admit(self, broker, session, command='activate.one'):
        request = self._request(broker, session, command)
        response = broker.dispatch('/v1/commands', request.as_dict(), session, control=False)
        self.assertIs(response.status, Status.ACCEPTED_PENDING)
        return request

    def test_new_admission_waits_until_old_terminal_collection(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        old = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        self.dispatch.advance(reservation)
        self.dispatch.advance(reservation)
        ready, done = threading.Event(), threading.Event()
        results, errors, workers = [], [], []
        original = self.dispatch._collect

        def collect(reservation, binding, response):
            request = self._request(broker, session, 'activate.next')
            def submit():
                ready.set()
                try:
                    results.append(broker.dispatch('/v1/commands', request.as_dict(), session, control=False))
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    done.set()
            worker = threading.Thread(target=submit)
            workers.append(worker)
            worker.start()
            self.assertTrue(ready.wait(1))
            self.assertFalse(done.wait(.2), 'new admission interleaved before terminal collection')
            return original(reservation, binding, response)

        try:
            with mock.patch.object(self.dispatch, '_collect', side_effect=collect):
                self.assertIs(self.dispatch.advance(reservation).status, Status.COMMITTED)
        finally:
            for worker in workers:
                worker.join(3)
                self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertEqual([r.status for r in results], [Status.ACCEPTED_PENDING])
        self.assertEqual(self.queue.broker.lookup(old.job.job_id).state, 'COMMITTED')
        self.assertEqual(broker._job.command_id, 'activate.next')
        self.assertFalse(broker._hold.is_set())
        self.assertEqual(owner.selector.snapshot()['pending_command'], 'activate.next')

    def test_two_registered_owners_publish_through_original_readback(self):
        a, broker_a, session_a = self._project('project.a')
        b, broker_b, session_b = self._project('project.b')
        self._admit(broker_a, session_a)
        self._admit(broker_b, session_b)
        row_a = self.dispatch.enqueue(broker_a, 'activate.one')
        row_b = self.dispatch.enqueue(broker_b, 'activate.one')
        self.assertNotEqual(row_a.job.resources, row_b.job.resources)
        self.assertEqual(self.dispatch.enqueue(broker_a, 'activate.one'), row_a)
        first, second = self.dispatch.reserve(), self.dispatch.reserve()
        self.assertEqual((first.job.project_id, second.job.project_id), ('project.a', 'project.b'))
        for reservation in (first, second):
            replies = [self.dispatch.advance(reservation) for _ in range(3)]
            self.assertEqual([r.status for r in replies], [Status.ACCEPTED_PENDING, Status.UNKNOWN, Status.COMMITTED])
            self.assertEqual(self.queue.broker.lookup(reservation.job.job_id).state, 'COMMITTED')
        self.assertTrue(a.selector.snapshot()['ready'])
        self.assertTrue(b.selector.snapshot()['ready'])
        self.assertFalse(self.queue.broker.snapshot().reservations)
        self.assertIsNone(broker_a._job)

    def test_revoked_session_cancels_without_selection(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        broker.sessions.revoke(session.credential)
        response = self.dispatch.advance(reservation)
        self.assertIs(response.status, Status.CANCELED)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'CANCELED')
        self.assertIsNone(owner.selector.snapshot()['selected'])

    def test_manual_revision_change_never_commits_scheduler(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        before = owner.selector.snapshot()['revisions']
        owner.selector.observe_revisions(before, {**before, 'source_revision': 'owner-edit-1'})
        with self.assertRaisesRegex(Exception, 'SELECTOR_REVISION_CONFLICT'):
            self.dispatch.advance(reservation)
        self.assertTrue(broker._hold.is_set())
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        self.assertEqual(owner.selector.snapshot()['revisions']['source_revision'], 'owner-edit-1')
        self.assertIsNone(owner.selector.snapshot()['selected'])

    def test_authenticated_cancel_before_advance_retires_exact_reservation(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        canceled = broker.dispatch('/v1/cancel', {'project_id': broker.project_id,
                                  'command_id': 'activate.one'}, session, control=True)
        self.assertIs(canceled.status, Status.CANCELED)
        self.assertEqual(self.dispatch.advance(reservation), canceled)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'CANCELED')
        self.assertFalse(self.queue.broker.snapshot().reservations)
        self.assertIsNone(broker._job)
        self.assertIsNone(owner.selector.snapshot()['selected'])

    def test_stop_retains_reserved_and_never_resumes_after_reopen(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        self.dispatch.stop()
        self.assertIsNone(self.dispatch.reserve())
        with self.assertRaisesRegex(DispatchError, 'DISPATCH_STOPPED'):
            self.dispatch.advance(reservation)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        storage = self.queue.storage_id
        self.dispatch.close()
        self.queue.close()
        with QueueOwner.reopen(storage) as reopened:
            snap = reopened.broker.snapshot()
            self.assertTrue(snap.stopped)
            self.assertEqual(len(snap.reservations), 1)
            self.assertTrue(snap.reservations[0].recovered)
            self.assertIsNone(reopened.broker.reserve_next(now_ms=epoch_ms()))
        self.assertIsNone(owner.selector.snapshot()['selected'])

    def test_restart_reservation_cannot_be_reissued_or_advanced(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        storage = self.queue.storage_id
        self.dispatch.close()
        self.queue.close()
        with QueueOwner.reopen(storage) as reopened, SelectorDispatcher(reopened) as fresh:
            restored = reopened.broker.snapshot().reservations[0]
            self.assertTrue(restored.recovered)
            self.assertEqual(restored.fence, reservation.fence)
            self.assertIsNone(fresh.reserve())
            with self.assertRaisesRegex(DispatchError, 'DISPATCH_RECOVERY_REQUIRED'):
                fresh.advance(restored)
        self.assertIsNone(owner.selector.snapshot()['selected'])

    def test_forged_public_callback_or_unregistered_owner_rejected(self):
        for item in (lambda: None, object(), None):
            with self.assertRaisesRegex(DispatchError, 'DISPATCH_REGISTERED_OWNER_REQUIRED'):
                self.dispatch.register(item)
        with self.assertRaisesRegex(QueueOwnerError, 'QUEUE_DISPATCHER_ACTIVE'):
            self.queue.close()

    def test_restart_after_owner_commit_reconciles_without_republishing(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        self.dispatch.advance(reservation)
        self.dispatch.advance(reservation)
        with mock.patch.object(self.queue.broker, 'record_owner_result', side_effect=OSError('injected cut')):
            with self.assertRaisesRegex(OSError, 'injected cut'):
                self.dispatch.advance(reservation)
        previous = owner.selector.snapshot()
        self.assertTrue(previous['ready'])
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        queue_id, owner_id = self.queue.storage_id, owner.storage_id
        self.dispatch.close(); broker.close(); owner.close(); self.queue.close()
        reopened_owner = ManagedFixtureOwner.reopen(owner_id, project_id='project.a', now_ms=epoch_ms())
        self.stack.callback(reopened_owner.close)
        reopened_broker = SelectorFixtureBroker.from_managed(reopened_owner)
        self.stack.callback(reopened_broker.close)
        with QueueOwner.reopen(queue_id) as reopened, SelectorDispatcher(reopened) as dispatcher:
            dispatcher.register(reopened_broker)
            held = reopened.broker.snapshot().reservations[0]
            with mock.patch.object(reopened_broker, 'advance', side_effect=AssertionError('must never reexecute')):
                with self.assertRaisesRegex(DispatchError, 'DISPATCH_RECOVERY_BINDING_MISMATCH'):
                    dispatcher.reconcile_terminal(held, reopened_broker, 'different.command')
                result = dispatcher.reconcile_terminal(held, reopened_broker, 'activate.one')
            self.assertEqual(result.state, 'COMMITTED')
            self.assertFalse(reopened.broker.snapshot().reservations)
            self.assertEqual(reopened_owner.selector.snapshot()['selected'], previous['selected'])
            self.assertEqual(reopened_owner.selector.snapshot()['generation'], previous['generation'])

    def test_owner_receipt_mismatch_retains_reservation(self):
        owner, broker, session = self._project('project.a')
        self._admit(broker, session)
        row = self.dispatch.enqueue(broker, 'activate.one')
        reservation = self.dispatch.reserve()
        self.dispatch.advance(reservation)
        self.dispatch.advance(reservation)
        original = broker.advance
        def altered():
            real = original()
            return Response.from_dict({**real.as_dict(), 'command_id': 'forged.command'})
        from studio.protocol.core import Response
        with mock.patch.object(broker, 'advance', side_effect=altered):
            with self.assertRaisesRegex(DispatchError, 'DISPATCH_OWNER_RECEIPT_MISMATCH'):
                self.dispatch.advance(reservation)
        self.assertEqual(self.queue.broker.lookup(row.job.job_id).state, 'RESERVED')
        self.assertTrue(owner.selector.snapshot()['ready'])  # Actual effect is preserved.


if __name__ == '__main__':
    unittest.main(verbosity=2)
