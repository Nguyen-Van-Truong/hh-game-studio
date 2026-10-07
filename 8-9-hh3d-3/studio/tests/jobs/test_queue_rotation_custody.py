"""Real registry/event-log barriers; no engine or queue-compaction PASS claim."""
from contextlib import ExitStack
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.custody import (CustodyError, WitnessCustody, binding_from, binding_value,
                                      decode_record, encode_record, MAX_EPOCH)
from studio.host.core.custody_registry import BASE_PATH, RegistryCustody
from studio.host.core.private_events import PrivateEventLog, EventLogError
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.safe_replace import ProtectedFileRoot


@unittest.skipUnless(os.name == 'nt', 'Windows registry/retained handles required')
class QueueRotationCustodyTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='gt07-rotate-'))).resolve()
        RegistryCustody.provision_base()
        self.local_id = uuid.uuid4().hex
        self.registry = RegistryCustody.create(self.local_id)
        self.stack.callback(self.remove_leaf)
        self.stack.callback(self.registry.close)
        self.files = self.stack.enter_context(ProtectedFileRoot.create(self.root))
        self.blobs = self.stack.enter_context(PrivateBlobStore.create(self.root))
        self.old = self.stack.enter_context(PrivateEventLog.create(self.root))
        self.new = self.stack.enter_context(PrivateEventLog.create(self.root))
        self.custody = WitnessCustody(self.registry, storage_id=self.local_id,
                                     project_id='studio.scheduler', create=True)
        self.custody.activate(file_root=self.files.root, file_identity=self.files.root_identity,
                              blob_root=self.blobs.root, blob_identity=self.blobs.root_identity,
                              event_root=self.old.root, event_binding=self.old.binding())
        self.old.bind_custody(self.custody)
        self.old.append({'kind': 'OLD'}, self.old.binding().witnessed)
        checkpoint = {'kind': 'TEST_CHECKPOINT', 'old_hash': self.old.binding().witnessed.sha256}
        self.new.append(checkpoint, self.new.binding().witnessed)
        self.checkpoint_sha = hashlib.sha256(self.new.read(2).event).hexdigest()
        self.old_binding, self.new_binding = self.old.binding(), self.new.binding()
        # The native event stream is private and denies ordinary path reads.
        # Preserve a guarded readback witness instead of weakening its ACL.
        self.old_bytes = self.old._read_at(0, self.old_binding.witnessed.size)

    def assert_old_unchanged(self, log):
        self.assertEqual(log.binding().witnessed, self.old_binding.witnessed)
        self.assertEqual(log._read_at(0, self.old_binding.witnessed.size), self.old_bytes)

    def remove_leaf(self):
        import winreg
        leaf = BASE_PATH + '\\' + self.local_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, leaf, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            self.assertEqual(winreg.QueryValueEx(key, 'Format'),
                             (b'hh-registry-custody-1\0' + self.local_id.encode(), winreg.REG_BINARY))
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, leaf, winreg.KEY_WOW64_64KEY, 0)

    def prepare(self, **overrides):
        args = dict(expected=self.old_binding, candidate_root=self.new.root,
                    candidate_root_identity=self.new._store.root_identity,
                    candidate_binding=self.new_binding, checkpoint_sha256=self.checkpoint_sha)
        args.update(overrides)
        self.custody.prepare_queue_rotation(**args)

    def advance(self, phase, **overrides):
        args = dict(expected_phase=phase, previous=self.old_binding, candidate=self.new_binding,
                    checkpoint_sha256=self.checkpoint_sha)
        args.update(overrides)
        self.custody.advance_queue_rotation(**args)

    def test_legacy_bytes_unchanged_and_rotation_has_three_durable_barriers(self):
        legacy_raw = self.registry.read()
        self.assertEqual(encode_record(decode_record(legacy_raw)), legacy_raw)
        self.assertNotIn('rotation', decode_record(legacy_raw))
        self.prepare()
        for phase in ('PREPARED', 'ACTIVE_POINTER'):
            self.assertEqual(decode_record(self.registry.read())['rotation']['phase'], phase)
            with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
                _ = self.custody.binding
            self.advance(phase)
        self.assertEqual(self.custody.binding.witnessed, self.new_binding.witnessed)
        self.assertEqual(self.custody.record['rotation']['phase'], 'COMMITTED')
        self.old.close()
        self.new.bind_custody(self.custody)
        head = self.new.append({'kind': 'NEXT'}, self.new_binding.witnessed)
        self.assertEqual(self.custody.binding.witnessed, head)
        with PrivateEventLog.reopen(self.old.root, self.old_binding) as archive:
            self.assert_old_unchanged(archive)
        self.assertEqual(encode_record(decode_record(self.registry.read())), self.registry.read())

    def test_restart_at_each_pending_phase_does_not_select_or_advance_automatically(self):
        self.prepare()
        for phase in ('PREPARED', 'ACTIVE_POINTER'):
            raw = self.registry.read()
            restarted = WitnessCustody(self.registry, storage_id=self.local_id, project_id='studio.scheduler')
            self.assertEqual(restarted.record['rotation']['phase'], phase)
            with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
                _ = restarted.binding
            self.assertEqual(self.registry.read(), raw)
            self.custody = restarted
            self.advance(phase)
        self.assertEqual(self.custody.record['events']['path'], str(self.new.root))

    def test_wrong_phase_hash_or_binding_does_not_write(self):
        self.prepare()
        for phase, changes in [('COMMITTED', {}), ('ACTIVE_POINTER', {}),
                               ('PREPARED', {'checkpoint_sha256': '0' * 64}),
                               ('PREPARED', {'candidate': self.old_binding})]:
            with self.subTest(phase=phase, changes=changes):
                before = self.registry.read()
                with self.assertRaises(CustodyError):
                    self.advance(phase, **changes)
                self.assertEqual(self.registry.read(), before)
        self.advance('PREPARED')
        self.advance('ACTIVE_POINTER')

    def test_old_log_cannot_append_during_or_after_pointer_switch(self):
        self.prepare()
        for phase in ('PREPARED', 'ACTIVE_POINTER', 'COMMITTED'):
            with self.subTest(phase=phase):
                with mock.patch.object(self.old, '_write_at', side_effect=AssertionError('must refuse before write')):
                    with self.assertRaisesRegex(EventLogError, 'EVENT_CUSTODY_NOT_READY'):
                        self.old.append({'kind': 'TOO_LATE'}, self.old_binding.witnessed)
                self.assert_old_unchanged(self.old)
                if phase != 'COMMITTED':
                    self.advance(phase)

    def test_candidate_aliases_or_stale_expected_are_refused_before_write(self):
        before = self.registry.read()
        for changes in ({'candidate_root': self.old.root, 'candidate_binding': self.old_binding},
                        {'expected': self.new_binding}, {'checkpoint_sha256': 'bad'},
                        {'candidate_root': self.blobs.root}):
            with self.subTest(changes=changes), self.assertRaises(CustodyError):
                self.prepare(**changes)
            self.assertEqual(self.registry.read(), before)

    def test_malformed_pointer_and_legacy_scope_are_rejected(self):
        self.prepare()
        original = self.custody.record
        for mutate in (lambda row: row.update(project_id='another-project'),
                       lambda row: row.update(events=copy.deepcopy(row['rotation']['candidate'])),
                       lambda row: row['rotation'].update(generation=True),
                       lambda row: row['rotation'].update(phase='SKIP')):
            row = copy.deepcopy(original)
            mutate(row)
            with self.assertRaises(CustodyError):
                encode_record(row)
        legacy = copy.deepcopy(original)
        legacy.pop('rotation')
        legacy.update(schema='hh-fixture-custody-1', project_id='another-project')
        self.registry.store(encode_record(legacy), expected=self.registry.read())
        other = WitnessCustody(self.registry, storage_id=self.local_id, project_id='another-project')
        with self.assertRaisesRegex(CustodyError, 'QUEUE_ONLY'):
            other.prepare_queue_rotation(expected=self.old_binding, candidate_root=self.new.root,
                                         candidate_root_identity=self.new._store.root_identity,
                                         candidate_binding=self.new_binding, checkpoint_sha256=self.checkpoint_sha)

    def test_persistence_failure_poisoned_without_rewriting_either_log(self):
        self.prepare()
        raw = self.registry.read()
        with mock.patch.object(self.registry, 'store', side_effect=OSError('injected registry flush failure')):
            with self.assertRaisesRegex(CustodyError, 'PERSIST_UNCERTAIN') as caught:
                self.advance('PREPARED')
        self.assertTrue(caught.exception.outcome_unknown)
        with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
            self.custody.confirm_current()
        self.assertEqual(self.registry.read(), raw)
        self.assert_old_unchanged(self.old)
        self.assertEqual(self.new.binding().witnessed, self.new_binding.witnessed)

    def test_second_rotation_must_follow_commit_and_carries_latest_head(self):
        self.prepare()
        before = self.registry.read()
        with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
            self.prepare()
        self.assertEqual(self.registry.read(), before)
        self.advance('PREPARED')
        self.advance('ACTIVE_POINTER')
        self.old.close()
        self.new.bind_custody(self.custody)
        self.new.append({'kind': 'NEXT'}, self.new.binding().witnessed)
        with PrivateEventLog.create(self.root) as third:
            self.custody.prepare_queue_rotation(expected=self.new.binding(), candidate_root=third.root,
                candidate_root_identity=third._store.root_identity,
                candidate_binding=third.binding(), checkpoint_sha256='a' * 64)
            row = self.custody.record['rotation']
            self.assertEqual(row['generation'], 2)
            self.assertEqual(binding_from(row['previous']['binding']).witnessed, self.new.binding().witnessed)

    def test_set_before_flush_failure_requires_fresh_registry_readback(self):
        # Fail only after the real native State write. A successful fresh read
        # flushes and verifies what survived; the failed instance cannot retry
        # or claim which side of the barrier reached durable storage.
        for phase in ('PREPARED', 'ACTIVE_POINTER', 'COMMITTED'):
            with self.subTest(phase=phase):
                did_set = False
                api = self.registry._api
                native_set, native_flush = api.set, api.flush
                def set_then_mark(*args):
                    nonlocal did_set
                    native_set(*args)
                    did_set = True
                def fail_after_set(*args):
                    if did_set:
                        raise OSError('injected after native set, before flush')
                    return native_flush(*args)
                with mock.patch.object(api, 'set', side_effect=set_then_mark), \
                     mock.patch.object(api, 'flush', side_effect=fail_after_set):
                    with self.assertRaisesRegex(CustodyError, 'PERSIST_UNCERTAIN') as caught:
                        if phase == 'PREPARED':
                            self.prepare()
                        else:
                            self.advance('PREPARED' if phase == 'ACTIVE_POINTER' else 'ACTIVE_POINTER')
                self.assertTrue(did_set and caught.exception.outcome_unknown)
                with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
                    self.custody.confirm_current()
                self.assert_old_unchanged(self.old)
                self.assertEqual(self.new.binding().witnessed, self.new_binding.witnessed)
                self.registry.close()
                self.registry = RegistryCustody.reopen(self.local_id)
                self.stack.callback(self.registry.close)
                self.custody = WitnessCustody(self.registry, storage_id=self.local_id,
                                             project_id='studio.scheduler')
                self.assertEqual(self.custody.record['rotation']['phase'], phase)
                if phase != 'COMMITTED':
                    with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
                        _ = self.custody.binding
                else:
                    self.assertEqual(self.custody.binding.witnessed, self.new_binding.witnessed)

    def test_prepare_reserves_both_following_epoch_barriers(self):
        for epoch in (MAX_EPOCH - 2, MAX_EPOCH - 1, MAX_EPOCH):
            record = self.custody.record
            record['epoch'] = epoch
            self.registry.store(encode_record(record), expected=self.registry.read())
            self.custody = WitnessCustody(self.registry, storage_id=self.local_id, project_id='studio.scheduler')
            before = self.registry.read()
            with self.assertRaisesRegex(CustodyError, 'ROTATION_EPOCH_LIMIT'):
                self.prepare()
            self.assertEqual(self.registry.read(), before)
        record['epoch'] = MAX_EPOCH - 3
        self.registry.store(encode_record(record), expected=self.registry.read())
        self.custody = WitnessCustody(self.registry, storage_id=self.local_id, project_id='studio.scheduler')
        self.prepare()
        self.advance('PREPARED')
        self.advance('ACTIVE_POINTER')
        self.assertEqual(self.custody.record['epoch'], MAX_EPOCH)

    def test_native_process_exit_at_each_barrier_preserves_exact_recovery_state(self):
        # Each subcase creates its own three-root owner and candidate; no
        # process is killed by PID. The child deliberately exits after the
        # completed native registry barrier, without executing Python cleanup.
        for phase in ('PREPARED', 'ACTIVE_POINTER', 'COMMITTED'):
            with self.subTest(phase=phase):
                with ExitStack() as setup:
                    storage = uuid.uuid4().hex
                    registry = RegistryCustody.create(storage)
                    def remove_exact_leaf():
                        import winreg
                        leaf = BASE_PATH + '\\' + storage
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, leaf, 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
                            self.assertEqual(winreg.QueryValueEx(key, 'Format'),
                                (b'hh-registry-custody-1\0' + storage.encode(), winreg.REG_BINARY))
                        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, leaf, winreg.KEY_WOW64_64KEY, 0)
                    setup.callback(remove_exact_leaf)
                    setup.callback(registry.close)
                    old = setup.enter_context(PrivateEventLog.create(self.root))
                    candidate = setup.enter_context(PrivateEventLog.create(self.root))
                    file_parent = self.root / phase
                    file_parent.mkdir()
                    files = setup.enter_context(ProtectedFileRoot.create(file_parent))
                    blobs = setup.enter_context(PrivateBlobStore.create(self.root))
                    custody = WitnessCustody(registry, storage_id=storage, project_id='studio.scheduler', create=True)
                    custody.activate(file_root=files.root, file_identity=files.root_identity,
                        blob_root=blobs.root, blob_identity=blobs.root_identity,
                        event_root=old.root, event_binding=old.binding())
                    old_binding, candidate_binding = old.binding(), candidate.binding()
                    old.close(); candidate.close(); files.close(); blobs.close(); registry.close()
                    config = {'id': storage, 'candidate': str(candidate.root),
                              'binding': binding_value(candidate_binding), 'cut': phase}
                    code = '''
import json, os, sys
from studio.host.core.custody import WitnessCustody, binding_from, identity_from
from studio.host.core.custody_registry import RegistryCustody
from studio.host.core.private_events import PrivateEventLog
from studio.host.core.safe_replace import ProtectedFileRoot
c=json.loads(sys.stdin.read())
r=RegistryCustody.reopen(c['id'])
w=WitnessCustody(r,storage_id=c['id'],project_id='studio.scheduler')
v=w.record
f=ProtectedFileRoot.reopen_readonly(v['files']['path'],identity_from(v['files']['identity']))
old=PrivateEventLog.reopen(v['events']['path'],w.binding)
new=PrivateEventLog.reopen(c['candidate'],binding_from(c['binding']))
a,b=old.binding(),new.binding()
w.prepare_queue_rotation(expected=a,candidate_root=new.root,candidate_root_identity=b.root,
                         candidate_binding=b,checkpoint_sha256='a'*64)
if c['cut']!='PREPARED':
    w.advance_queue_rotation(expected_phase='PREPARED',previous=a,candidate=b,checkpoint_sha256='a'*64)
if c['cut']=='COMMITTED':
    w.advance_queue_rotation(expected_phase='ACTIVE_POINTER',previous=a,candidate=b,checkpoint_sha256='a'*64)
os._exit(73)
'''
                    run = subprocess.run([sys.executable, '-B', '-c', code], input=json.dumps(config),
                        capture_output=True, text=True, timeout=20, cwd=STUDIO.parent)
                    self.assertEqual(run.returncode, 73, run.stderr)
                    with RegistryCustody.reopen(storage) as reopened:
                        recovered = WitnessCustody(reopened, storage_id=storage, project_id='studio.scheduler')
                        raw = reopened.read()
                        self.assertEqual(recovered.record['rotation']['phase'], phase)
                        with PrivateEventLog.reopen(old.root, old_binding) as old_again, \
                             PrivateEventLog.reopen(candidate.root, candidate_binding) as new_again:
                            self.assertEqual(old_again.binding().witnessed, old_binding.witnessed)
                            self.assertEqual(new_again.binding().witnessed, candidate_binding.witnessed)
                            if phase == 'COMMITTED':
                                self.assertEqual(recovered.binding.witnessed, candidate_binding.witnessed)
                            else:
                                with self.assertRaisesRegex(CustodyError, 'RECONCILIATION_REQUIRED'):
                                    _ = recovered.binding
                        self.assertEqual(reopened.read(), raw)

    def test_prepare_cannot_race_past_the_append_preflight(self):
        entered, release, preparing = threading.Event(), threading.Event(), threading.Event()
        outcomes = {}
        original_write = self.old._write_at
        def delayed_write(offset, frame):
            self.assertTrue(self.custody._mutex._is_owned(),
                            'native write must stay inside the custody barrier')
            entered.set()
            if not release.wait(5):
                raise AssertionError('test barrier timeout')
            return original_write(offset, frame)
        def append():
            try:
                outcomes['append'] = self.old.append({'kind': 'WINNING_APPEND'}, self.old_binding.witnessed)
            except BaseException as exc:
                outcomes['append'] = exc
        def prepare():
            preparing.set()
            try:
                self.prepare()
                outcomes['prepare'] = 'unexpected success'
            except BaseException as exc:
                outcomes['prepare'] = exc
        writer = threading.Thread(target=append)
        rotator = threading.Thread(target=prepare)
        with mock.patch.object(self.old, '_write_at', side_effect=delayed_write):
            writer.start()
            try:
                self.assertTrue(entered.wait(5))
                rotator.start()
                self.assertTrue(preparing.wait(5))
            finally:
                release.set()
                writer.join(5)
                if rotator.ident is not None:
                    rotator.join(5)
        self.assertFalse(writer.is_alive() or rotator.is_alive())
        self.assertNotIsInstance(outcomes['append'], BaseException)
        self.assertIsInstance(outcomes['prepare'], CustodyError)
        self.assertEqual(outcomes['prepare'].code, 'CUSTODY_BINDING_CHANGED')
        self.assertNotIn('rotation', self.custody.record)
        self.assertEqual(self.custody.binding.witnessed, outcomes['append'])

    def test_stale_bound_append_is_a_deterministic_head_conflict(self):
        self.old.append({'kind': 'FIRST'}, self.old_binding.witnessed)
        before = self.old.binding()
        with mock.patch.object(self.old, '_write_at', side_effect=AssertionError('must not write')):
            with self.assertRaisesRegex(EventLogError, 'EVENT_HEAD_CONFLICT') as caught:
                self.old.append({'kind': 'STALE'}, self.old_binding.witnessed)
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertEqual(self.old.binding(), before)


if __name__ == '__main__':
    unittest.main()
