"""Real private journals/releases and fixed mock consumer; no engine claim."""
from __future__ import annotations
import copy
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.fixture_selector import FixtureSelector, FixtureReleaseConsumer, SelectorError, ConsumerReadback
from host.core.private_events import PrivateEventLog, EventHead, EventBinding
from host.core.private_store import PrivateBlobStore, PrivateStoreError
from host.core.limits import Request, payload_digest, SafetyViolation
from host.core.safe_open import FileIdentity


@unittest.skipUnless(os.name == 'nt', 'Windows NTFS selector fixture required')
class FixtureSelectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-selector-test-')
        self.base = Path(self.temp.name).resolve()
        self.log = PrivateEventLog.create(self.base)
        self.store = PrivateBlobStore.create(self.base)
        self.consumer = FixtureReleaseConsumer('project-one')
        self.selector = FixtureSelector(self.log, self.store, self.consumer, project_id='project-one',
                                       initial_revisions={'source_revision': 'source-0', 'source_sha256': 'a'*64, 'game_revision': 'game-0'})
        self.lease = self.selector.lease('owner', now_ms=100)

    def tearDown(self):
        self.selector.close()
        self.log.close()
        self.store.close()
        self.temp.cleanup()

    def request(self, identifier='cmd-one', value='one', *, deadline=10_000):
        snap = self.selector.snapshot()
        payload = {'assets': {'scene': {'value': value, 'references': ['texture']},
                              'texture': {'value': value+'-leaf', 'references': []}},
                   'entrypoint': 'scene', 'expected_generation': snap['generation'],
                   'expected_selection_hash': snap['selection_hash'],
                   **{'expected_'+k: v for k, v in snap['revisions'].items()}}
        target = {'stable_id': 'active-release'}
        return Request(identifier, 'project-one', 'fixture.release.activate', self.lease['lease_id'],
                       self.lease['fencing_epoch'], snap['revisions']['game_revision'], target, payload,
                       payload_digest('fixture.release.activate', target, payload, 'hh-studio-0.1'), deadline).as_dict()

    def activate(self, request=None, *, now=101):
        request = request or self.request()
        identifier = request['command_id']
        self.selector.prepare(request, now_ms=now)
        self.selector.stage(identifier, now_ms=now+1)
        self.selector.select(identifier, now_ms=now+2)
        return self.selector.adopt(identifier, now_ms=now+3)

    def reopen(self, *, fresh_consumer=False):
        root, binding = self.log.root, self.log.binding()
        self.selector.close(); self.log.close()
        self.log = PrivateEventLog.reopen(root, binding)
        if fresh_consumer:
            self.consumer = FixtureReleaseConsumer('project-one')
        self.selector = FixtureSelector(self.log, self.store, self.consumer, project_id='project-one')

    def test_intent_precedes_staging_and_selection_precedes_readback_receipt(self):
        request = self.request()
        pending = self.selector.prepare(request, now_ms=101)
        self.assertEqual(pending['status'], 'ACCEPTED_PENDING')
        self.assertEqual(list(self.store.root.glob('blob-*')), [])
        self.selector.stage('cmd-one', now_ms=102)
        self.assertEqual(self.selector.snapshot()['generation'], 0)
        self.selector.select('cmd-one', now_ms=103)
        self.assertEqual(self.selector.lookup('cmd-one')['status'], 'UNKNOWN')
        self.assertIsNone(self.consumer.readback())
        receipt = self.selector.adopt('cmd-one', now_ms=104)
        self.assertEqual(receipt['status'], 'COMMITTED')
        self.assertTrue(self.selector.snapshot()['ready'])
        self.assertEqual(self.consumer.readback().generation, 1)
        self.assertEqual(self.consumer.adoption_count, 1)
        self.assertEqual(self.selector.lookup('cmd-one'), receipt)

    def test_duplicate_after_deadline_and_lease_change_returns_original_receipt(self):
        request = self.request()
        receipt = self.activate(request)
        count, head = len(list(self.store.root.glob('blob-*'))), self.log.binding().witnessed
        self.lease = self.selector.lease('owner', now_ms=20_000)
        retry = copy.deepcopy(request)
        retry['lease_id'], retry['fencing_epoch'] = self.lease['lease_id'], self.lease['fencing_epoch']
        self.assertEqual(self.selector.prepare(retry, now_ms=20_001), receipt)
        self.assertEqual(self.consumer.adoption_count, 1)
        self.assertEqual(self.selector.snapshot()['generation'], 1)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))), count)
        self.assertEqual(self.log.binding().witnessed.sequence, head.sequence+1)

    def test_same_id_changed_payload_and_wrong_project_never_reuse_receipt(self):
        request = self.request()
        self.activate(request)
        changed = self.request(value='changed')
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_COMMAND_CONFLICT'):
            self.selector.prepare(changed, now_ms=105)
        wrong = copy.deepcopy(request); wrong['project_id'] = 'other'
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_REQUEST_SCOPE'):
            self.selector.prepare(wrong, now_ms=105)
        wrong = copy.deepcopy(request); wrong['unrecognized'] = True
        with self.assertRaises(SafetyViolation):
            self.selector.prepare(wrong, now_ms=105)
        self.assertEqual(self.selector.snapshot()['generation'], 1)

    def test_invalid_request_has_no_journal_or_blob_effect(self):
        request = self.request()
        before = self.log.binding().witnessed
        for change in ({'deadline_ms': 100}, {'payload_hash': 'sha256:'+'0'*64}, {'fencing_epoch': 999},
                       {'expected_revision': 'wrong'}, {'project_id': 'other'}):
            changed = copy.deepcopy(request); changed.update(change)
            with self.subTest(change=change), self.assertRaises(SafetyViolation):
                self.selector.prepare(changed, now_ms=101)
        self.assertEqual(self.log.binding().witnessed, before)
        self.assertEqual(list(self.store.root.glob('blob-*')), [])

    def test_two_same_parent_commands_admit_one_then_reject_stale_parent(self):
        first, second = self.request('first'), self.request('second')
        barrier, results = threading.Barrier(3), []
        def submit(request):
            barrier.wait(5)
            try:
                results.append((request, self.selector.prepare(request, now_ms=101)))
            except SelectorError as exc:
                results.append((request, exc.code))
        threads = [threading.Thread(target=submit, args=(r,), daemon=True) for r in (first,second)]
        for thread in threads: thread.start()
        barrier.wait(5)
        for thread in threads: thread.join(5)
        self.assertFalse(any(t.is_alive() for t in threads))
        winner = next(r for r, result in results if type(result) is dict)
        loser = next(r for r, result in results if type(result) is str)
        self.assertEqual(len([result for _, result in results if type(result) is dict]), 1)
        self.selector.stage(winner['command_id'], now_ms=102)
        self.selector.select(winner['command_id'], now_ms=103)
        self.selector.adopt(winner['command_id'], now_ms=104)
        with self.assertRaises(SafetyViolation):
            self.selector.prepare(loser, now_ms=105)
        self.assertEqual(self.selector.snapshot()['generation'], 1)

    def test_late_revision_and_fence_changes_refuse_selection(self):
        request = self.request()
        self.selector.prepare(request, now_ms=101); self.selector.stage('cmd-one', now_ms=102)
        before = self.selector.snapshot()['revisions']
        after = {**before, 'source_revision': 'owner-edit', 'source_sha256': 'b'*64}
        self.selector.observe_revisions(before, after)
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_REVISION_CONFLICT'):
            self.selector.select('cmd-one', now_ms=103)
        self.assertEqual(self.selector.snapshot()['generation'], 0)
        self.selector.observe_revisions(after, before)
        self.selector.lease('owner', now_ms=104)
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STALE_LEASE'):
            self.selector.select('cmd-one', now_ms=105)

    def test_reopen_requires_explicit_reconcile_and_does_not_restage(self):
        request = self.request()
        self.selector.prepare(request, now_ms=101)
        self.reopen()
        self.assertEqual(self.selector.prepare(request, now_ms=102)['phase'], 'INTENT')
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_EXPLICIT_RECONCILE_REQUIRED'):
            self.selector.stage('cmd-one', now_ms=103)
        self.selector.reconcile('cmd-one', 'stage', now_ms=104)
        self.reopen()
        before = sorted(p.name for p in self.store.root.iterdir())
        self.selector.reconcile('cmd-one', 'select', now_ms=105)
        self.selector.reconcile('cmd-one', 'adopt', now_ms=106)
        self.assertEqual(sorted(p.name for p in self.store.root.iterdir()), before)
        self.assertEqual(self.selector.snapshot()['generation'], 1)

    def test_stop_cancels_preselection_and_stays_stopped_after_reopen(self):
        self.selector.prepare(self.request(), now_ms=101)
        self.selector.stage('cmd-one', now_ms=102)
        stopped = self.selector.stop()
        self.assertTrue(stopped['stopped'])
        self.assertEqual(stopped['generation'], 0)
        self.assertEqual(self.selector.lookup('cmd-one')['status'], 'CANCELED')
        head = self.log.binding().witnessed
        self.selector.stop()
        self.assertEqual(self.log.binding().witnessed, head)
        self.reopen()
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STOPPED'):
            self.selector.prepare(self.request('new'), now_ms=103)

    def test_selected_stop_requires_restore_preserving_monotonic_generation(self):
        first = self.request('first', 'old'); self.activate(first)
        self.selector.prepare(self.request('second', 'new'), now_ms=105)
        self.selector.stage('second', now_ms=106); self.selector.select('second', now_ms=107)
        old_readback = self.consumer.readback()
        self.selector.stop()
        self.assertEqual(self.selector.lookup('second')['status'], 'UNKNOWN')
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STOPPED'):
            self.selector.adopt('second', now_ms=108)
        restored = self.selector.reconcile('second', 'restore', now_ms=109)
        self.assertEqual(restored['code'], 'FIXTURE_ACTIVATION_RESTORED')
        self.assertEqual(self.consumer.readback().release_id, old_readback.release_id)
        self.assertEqual(self.consumer.readback().generation, 3)
        self.assertTrue(self.selector.snapshot()['ready'])
        self.assertTrue(self.selector.snapshot()['stopped'])

    def test_restore_refuses_new_owner_revision_without_overwrite(self):
        self.selector.prepare(self.request(), now_ms=101)
        self.selector.stage('cmd-one', now_ms=102); self.selector.select('cmd-one', now_ms=103)
        before = self.selector.snapshot()['revisions']; after = {**before, 'game_revision': 'owner-edit'}
        self.selector.observe_revisions(before, after)
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_REVISION_CONFLICT'):
            self.selector.reconcile('cmd-one', 'restore', now_ms=104)
        self.assertEqual(self.selector.snapshot()['revisions'], after)
        self.assertEqual(self.selector.snapshot()['generation'], 1)
        self.assertIsNone(self.consumer.readback())

    def test_lost_terminal_reply_replays_receipt_and_never_adopts_twice(self):
        request = self.request()
        self.selector.prepare(request, now_ms=101); self.selector.stage('cmd-one', now_ms=102)
        self.selector.select('cmd-one', now_ms=103)
        append = self.log.append
        def lost(event, *args, **kwargs):
            head = append(event, *args, **kwargs)
            if event['kind'] == 'TERMINAL':
                raise PrivateStoreError('SIMULATED_LOST_RETURN')
            return head
        with mock.patch.object(self.log, 'append', side_effect=lost):
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_ADOPTION_UNKNOWN') as caught:
                self.selector.adopt('cmd-one', now_ms=104)
        self.assertTrue(caught.exception.outcome_unknown)
        self.reopen()
        self.assertEqual(self.selector.prepare(request, now_ms=105)['status'], 'COMMITTED')
        self.assertEqual(self.consumer.adoption_count, 1)
        self.assertTrue(self.selector.snapshot()['ready'])

    def test_consumer_changed_before_failed_terminal_requires_readback_reconcile(self):
        self.selector.prepare(self.request(), now_ms=101); self.selector.stage('cmd-one', now_ms=102)
        self.selector.select('cmd-one', now_ms=103)
        append = self.log.append
        def fail(event, *args, **kwargs):
            if event['kind'] == 'TERMINAL':
                raise PrivateStoreError('SIMULATED_BEFORE_TERMINAL')
            return append(event, *args, **kwargs)
        with mock.patch.object(self.log, 'append', side_effect=fail):
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_ADOPTION_UNKNOWN'):
                self.selector.adopt('cmd-one', now_ms=104)
        self.assertFalse(self.selector.snapshot()['ready'])
        self.assertEqual(self.consumer.adoption_count, 1)
        self.reopen()
        receipt = self.selector.reconcile('cmd-one', 'adopt', now_ms=105)
        self.assertEqual(receipt['status'], 'COMMITTED')
        self.assertEqual(self.consumer.adoption_count, 1)

    def test_false_consumer_readback_never_commits_or_marks_ready(self):
        self.selector.prepare(self.request(), now_ms=101); self.selector.stage('cmd-one', now_ms=102)
        self.selector.select('cmd-one', now_ms=103)
        with mock.patch.object(self.consumer, 'readback', return_value=None):
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_ADOPTION_UNKNOWN'):
                self.selector.adopt('cmd-one', now_ms=104)
        self.assertEqual(self.selector.lookup('cmd-one')['status'], 'UNKNOWN')
        self.selector.reconcile('cmd-one', 'adopt', now_ms=105)
        real = self.consumer.readback()
        with mock.patch.object(self.consumer, 'readback', return_value=dataclasses.replace(real, asset_set_sha256='0'*64)):
            self.assertFalse(self.selector.snapshot()['ready'])

    def test_expired_adoption_needs_fresh_recovery_lease(self):
        self.selector.prepare(self.request(deadline=105), now_ms=101)
        self.selector.stage('cmd-one', now_ms=102); self.selector.select('cmd-one', now_ms=103)
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_DEADLINE_EXPIRED'):
            self.selector.adopt('cmd-one', now_ms=106)
        self.assertIsNone(self.consumer.readback())
        self.reopen()
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STALE_LEASE'):
            self.selector.reconcile('cmd-one', 'adopt', now_ms=31_000)
        self.lease = self.selector.lease('recovery-owner', now_ms=31_001)
        self.assertEqual(self.selector.reconcile('cmd-one', 'adopt', now_ms=31_002)['status'], 'COMMITTED')

    def test_partial_staging_is_cancel_only_and_files_are_preserved(self):
        self.selector.prepare(self.request(), now_ms=101)
        put, count = self.store.put_bytes, 0
        def partial(data):
            nonlocal count
            count += 1
            if count == 2: raise PrivateStoreError('PRIVATE_STAGE_QUOTA')
            return put(data)
        with mock.patch.object(self.store, 'put_bytes', side_effect=partial):
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_STAGE_UNKNOWN'):
                self.selector.stage('cmd-one', now_ms=102)
        files = sorted(p.name for p in self.store.root.iterdir())
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_PHASE_CONFLICT'):
            self.selector.reconcile('cmd-one', 'stage', now_ms=103)
        self.assertEqual(self.selector.reconcile('cmd-one', 'cancel')['status'], 'CANCELED')
        self.assertEqual(sorted(p.name for p in self.store.root.iterdir()), files)
        self.assertEqual(self.selector.snapshot()['generation'], 0)

    def test_whole_operation_capacity_reserved_before_intent(self):
        import host.core.private_events as events
        before = self.log.binding().witnessed
        # At this capacity an intent itself fits, its completion budget does not.
        with mock.patch.object(events, 'MAX_RECORDS', before.sequence + 6):
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_CAPACITY') as caught:
                self.selector.prepare(self.request(), now_ms=101)
            self.assertFalse(caught.exception.outcome_unknown)
        self.assertEqual(self.log.binding().witnessed, before)
        self.assertEqual(list(self.store.root.glob('blob-*')), [])
        self.selector.prepare(self.request(), now_ms=102)

    def test_fresh_runtime_load_is_explicit_and_does_not_reselect_or_restage(self):
        request = self.request(); receipt = self.activate(request)
        before = self.log.binding().witnessed
        self.reopen(fresh_consumer=True)
        self.assertFalse(self.selector.snapshot()['ready'])
        self.assertEqual(self.selector.prepare(request, now_ms=105), receipt)
        self.assertIsNone(self.consumer.readback())
        self.selector.load_committed(now_ms=106)
        self.selector.load_committed(now_ms=107)
        self.assertEqual(self.consumer.adoption_count, 1)
        self.assertEqual(self.log.binding().witnessed, before)
        self.assertTrue(self.selector.snapshot()['ready'])

    def test_real_process_cuts_preserve_phase_and_resume_without_duplicate_files(self):
        script = r'''import json, os, sys
from host.core.fixture_selector import FixtureSelector, FixtureReleaseConsumer
from host.core.private_store import PrivateBlobStore
from host.core.private_events import PrivateEventLog, EventBinding, EventHead
from host.core.safe_open import FileIdentity
import host.core.fixture_selector as module
c = json.loads(sys.stdin.read()); b = c['binding']
binding = EventBinding(FileIdentity(**b['root']), FileIdentity(**b['stream']), EventHead(**b['witnessed']))
log = PrivateEventLog.reopen(c['log_root'], binding)
store = PrivateBlobStore.reopen(c['store_root'], FileIdentity(**c['store_identity']))
consumer = FixtureReleaseConsumer('project-one')
selector = FixtureSelector(log, store, consumer, project_id='project-one')
append, stage, adopt = log.append, module.stage_fixture_release, consumer.adopt
def cut_append(event, *args, **kwargs):
    result = append(event, *args, **kwargs)
    if c['cut'] == 'after_' + event['kind']:
        os._exit(81)
    return result
def cut_stage(*args, **kwargs):
    result = stage(*args, **kwargs)
    if c['cut'] == 'after_MANIFEST': os._exit(81)
    return result
def cut_adopt(*args, **kwargs):
    adopt(*args, **kwargs)
    if c['cut'] in ('after_CONSUMER', 'after_RESTORE_CONSUMER'): os._exit(81)
log.append, module.stage_fixture_release, consumer.adopt = cut_append, cut_stage, cut_adopt
print(json.dumps({'marker':'SELECTOR_CUT_ARMED','cut':c['cut'],'pid':os.getpid()}), flush=True)
selector.prepare(c['request'], now_ms=101)
selector.stage('cmd-one', now_ms=102)
selector.select('cmd-one', now_ms=103)
if c['cut'] in ('after_RESTORE', 'after_RESTORE_CONSUMER'):
    selector.stop()
    selector.reconcile('cmd-one', 'restore', now_ms=104)
else:
    selector.adopt('cmd-one', now_ms=104)
raise AssertionError('cut not reached')
'''
        cases = [('after_INTENT', 'INTENT', 0), ('after_STAGING', 'STAGING', 0),
                 ('after_MANIFEST', 'STAGING', 3), ('after_STAGED', 'STAGED', 3),
                 ('after_SELECT', 'SELECTED', 3), ('after_CONSUMER', 'SELECTED', 3),
                 ('after_TERMINAL', 'COMMITTED', 3), ('after_RESTORE', 'RESTORING', 3),
                 ('after_RESTORE_CONSUMER', 'RESTORING', 3)]
        for cut, phase, expected_files in cases:
            with self.subTest(cut=cut):
                log, store = PrivateEventLog.create(self.base), PrivateBlobStore.create(self.base)
                consumer = FixtureReleaseConsumer('project-one')
                selector = FixtureSelector(log, store, consumer, project_id='project-one',
                             initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
                lease = selector.lease('owner', now_ms=100)
                request = self.request()
                request['lease_id'], request['fencing_epoch'] = lease['lease_id'], lease['fencing_epoch']
                binding, store_identity = log.binding(), store.root_identity
                config = {'cut':cut, 'binding':dataclasses.asdict(binding), 'log_root':str(log.root),
                          'store_root':str(store.root), 'store_identity':dataclasses.asdict(store_identity), 'request':request}
                selector.close(); log.close(); store.close()
                process = subprocess.Popen([sys.executable, '-B', '-c', script], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT)
                try:
                    stdout, stderr = process.communicate(json.dumps(config), timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()  # exact owned child, inherited outer test Job
                    process.communicate(timeout=5)
                    raise
                self.assertEqual(process.returncode, 81, stderr)
                self.assertEqual(json.loads(stdout), {'marker':'SELECTOR_CUT_ARMED','cut':cut,'pid':process.pid})
                self.assertEqual(stderr, '')
                log = PrivateEventLog.reopen(config['log_root'], binding)
                store = PrivateBlobStore.reopen(config['store_root'], store_identity)
                selector = FixtureSelector(log, store, consumer, project_id='project-one')
                try:
                    outcome = selector.lookup('cmd-one')
                    self.assertEqual(outcome.get('phase', outcome['status']), phase)
                    self.assertEqual(len(list(store.root.glob('blob-*'))), expected_files)
                    if phase == 'STAGING' and expected_files == 0:
                        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STAGING_INCOMPLETE_OR_AMBIGUOUS'):
                            selector.reconcile('cmd-one', 'discover_staged')
                        selector.reconcile('cmd-one', 'cancel')
                        self.assertEqual(selector.snapshot()['generation'], 0)
                    else:
                        if phase == 'INTENT': selector.reconcile('cmd-one', 'stage', now_ms=105)
                        if phase == 'STAGING': selector.reconcile('cmd-one', 'discover_staged')
                        if phase in ('INTENT','STAGING','STAGED'): selector.reconcile('cmd-one', 'select', now_ms=106)
                        if phase != 'COMMITTED': selector.reconcile('cmd-one', 'adopt', now_ms=107)
                        else:
                            before = log.binding().witnessed
                            self.assertEqual(selector.prepare(request, now_ms=105), outcome)
                            selector.load_committed(now_ms=106)
                            self.assertEqual(log.binding().witnessed, before)
                        self.assertTrue(selector.snapshot()['ready'])
                        self.assertEqual(selector.snapshot()['generation'], 2 if phase == 'RESTORING' else 1)
                        self.assertEqual(len(list(store.root.glob('blob-*'))), 3)
                    snapshot = selector.snapshot()
                    print('HH_GT02_SELECTOR_CUT '+json.dumps({
                        'cut':cut, 'host_pid':process.pid, 'host_exit':process.returncode,
                        'armed_marker':json.loads(stdout), 'phase_on_reopen':phase,
                        'blob_count_on_reopen':expected_files,
                        'generation_after_reconcile':snapshot['generation'], 'ready':snapshot['ready'],
                        'stopped':snapshot['stopped'], 'receipt':selector.lookup('cmd-one'),
                        'blob_count_after_reconcile':len(list(store.root.glob('blob-*')))
                    }), flush=True)
                finally:
                    selector.close(); log.close(); store.close()

    def test_staged_discovery_rejects_ambiguous_manifest_without_creating_files(self):
        self.selector.prepare(self.request(), now_ms=101)
        append = self.log.append
        def fail_staged(event, *args, **kwargs):
            if event['kind'] == 'STAGED': raise PrivateStoreError('LOST_STAGED_RECORD')
            return append(event, *args, **kwargs)
        with mock.patch.object(self.log, 'append', side_effect=fail_staged):
            with self.assertRaises(SafetyViolation):
                self.selector.stage('cmd-one', now_ms=102)
        # The stage function succeeded; only its event append was denied.
        self.reopen()
        manifest_bytes = next(p.read_bytes() for p in self.store.root.glob('blob-*')
                              if json.loads(p.read_bytes()).get('format') == 'hh-fixture-release-1')
        self.store.put_bytes(manifest_bytes)
        before = self.log.binding().witnessed
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STAGING_INCOMPLETE_OR_AMBIGUOUS'):
            self.selector.reconcile('cmd-one', 'discover_staged')
        self.assertEqual(self.log.binding().witnessed, before)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))), 4)

    def test_valid_checksum_cannot_authorize_semantically_invalid_event(self):
        before = self.log.binding().witnessed
        self.log.append({'kind': 'TERMINAL', 'command_id': 'unadmitted', 'digest': 'sha256:'+'a'*64,
                         'response': {'status':'COMMITTED'}, 'authority':None}, before)
        with self.assertRaisesRegex(SafetyViolation, 'EVENT_RECOVERY_REQUIRED'):
            self.selector.snapshot()
        self.assertIsNone(self.consumer.readback())

    def test_stop_signal_blocks_selection_while_waiting_for_selector_lock(self):
        self.selector.prepare(self.request(), now_ms=101); self.selector.stage('cmd-one', now_ms=102)
        done, errors = threading.Event(), []
        def stop():
            try: self.selector.stop()
            except BaseException as exc: errors.append(type(exc).__name__)
            finally: done.set()
        with self.selector._mutex:
            thread = threading.Thread(target=stop, daemon=True); thread.start()
            self.assertTrue(self.selector._stop_requested.wait(5))
            with self.assertRaisesRegex(SelectorError, 'SELECTOR_STOPPED'):
                self.selector.select('cmd-one', now_ms=103)
        thread.join(5)
        self.assertTrue(done.is_set())
        self.assertEqual(errors, [])
        self.assertEqual(self.selector.snapshot()['generation'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
