"""Fake-storage fault matrix over the real owner; native proof is a separate lane."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline import snapshot_owner as implementation, snapshot_state as model
from studio.host.core.journal import Journal, JournalLimits, Lease
from studio.host.core.private_events import EventBinding, EventHead, EventRecord
from studio.host.core.private_store import StagedBlob
from studio.host.core.safe_open import FileIdentity
from studio.host.core.safe_replace import FileVersion
from studio.protocol.core import canonical_bytes, parse_json
from studio.tests.pipeline.test_snapshot_state import candidate, request


class MemoryBackend:
    """No native claims: identities/custody are explicit, faultable test values."""
    def __init__(self):
        self.next_id = 0
        self.roots = {}
        self.registries = {}
        self.calls = []
        self.hook = lambda label: None

    def touch(self, label):
        self.calls.append(label)
        self.hook(label)

    def identity(self, size=0):
        self.next_id += 1
        return FileIdentity(1, '%032x' % self.next_id, size)

    def create_root(self, parent, kind):
        identity = self.identity()
        root = Path(parent) / ('hh-files-' if kind == 'files' else 'hh-private-') / identity.file_id
        root.mkdir(parents=True)
        (root / '.writer').write_bytes(b'')
        data = SimpleNamespace(kind=kind, root=root, identity=identity, entries={})
        self.roots[str(root)] = data
        return MemoryRoot(self, data)

    def root(self, path, identity):
        data = self.roots[str(path)]
        model.need(data.identity.same_file(identity), 'FAKE_ROOT_REPLACED')
        return MemoryRoot(self, data)

    def registry(self, storage_id, create=False):
        if create:
            self.registries[storage_id] = SimpleNamespace(record=None, binding=None)
        return SimpleNamespace(data=self.registries[storage_id], close=lambda: self.touch('close:registry'))

    def custody(self, registry, *, storage_id, project_id, create=False):
        backend = self

        class Custody:
            @property
            def record(self):
                return registry.data.record

            @property
            def binding(self):
                return registry.data.binding

            def confirm_current(self):
                backend.touch('custody')

            def activate(self, *, file_root, file_identity, blob_root, blob_identity, event_root, event_binding):
                registry.data.record = {'phase': 'READY', 'storage_id': storage_id, 'project_id': project_id,
                    'files': {'path': str(file_root), 'identity': implementation.identity_value(file_identity)},
                    'blobs': {'path': str(blob_root), 'identity': implementation.identity_value(blob_identity)},
                    'events': {'path': str(event_root)}}
                registry.data.binding = event_binding

            def persist_binding(self, binding):
                registry.data.binding = binding

        return Custody()

    def event_log(self, parent):
        root = self.create_root(parent, 'log')
        root.data.stream = self.identity()
        event = {'kind': 'GENESIS', 'store_id': root.root.name, 'volume': '1',
                 'file_id': root.data.stream.file_id, 'root_file_id': root.root_identity.file_id}
        root.data.rows = []
        log = MemoryLog(self, root.data)
        log.add(event)
        return log

    def reopen_log(self, path, binding):
        log = MemoryLog(self, self.roots[str(path)])
        model.need(log.binding() == binding, 'FAKE_UNWITNESSED_SUFFIX')
        return log

    def install(self):
        return patch.multiple(implementation,
            ProtectedFileRoot=SimpleNamespace(create=lambda parent: self.create_root(parent, 'files'), reopen_readonly=self.root),
            PrivateBlobStore=SimpleNamespace(create=lambda parent: self.create_root(parent, 'blobs'), reopen=self.root),
            PrivateEventLog=SimpleNamespace(create=self.event_log, reopen=self.reopen_log),
            RegistryCustody=SimpleNamespace(provision_base=lambda: None,
                create=lambda storage_id: self.registry(storage_id, True), reopen=self.registry),
            WitnessCustody=self.custody)


class MemoryRoot:
    def __init__(self, backend, data):
        self.backend, self.data = backend, data
        self.root, self.root_identity = data.root, data.identity
        self._mutex = threading.RLock()
        self.closed = False

    def _check(self, **ignored):
        model.need(not self.closed and self.root_identity == self.data.identity, 'FAKE_ROOT_REPLACED')

    def check_mutation_available(self):
        self._check()

    def create_new(self, name, raw):
        self._check()
        self.backend.touch('before_file:' + name)
        model.need(name not in self.data.entries, 'FAKE_EXISTS')
        value = FileVersion(self.backend.identity(len(raw)), model.sha(raw))
        self.data.entries[name] = (value, raw)
        (self.root / name).write_bytes(raw)
        self.backend.touch('after_file:' + name)
        return value

    def read(self, name):
        self._check()
        self.backend.touch('read:' + name)
        return self.data.entries[name]

    def confirm_barrier(self, name, expected):
        self._check()
        model.need(self.data.entries[name][0] == expected, 'FAKE_BARRIER_VERSION')
        self.backend.touch('barrier:' + name)

    def put_bytes(self, raw):
        self._check()
        self.backend.touch('before_blob')
        identity = self.backend.identity(len(raw))
        value = StagedBlob('blob-' + identity.file_id, identity, model.sha(raw))
        self.data.entries[value.object_id] = (value, raw)
        (self.root / value.object_id).write_bytes(raw)
        self.backend.touch('after_blob')
        return value

    def read_blob(self, value):
        self._check()
        self.backend.touch('read_blob')
        expected, raw = self.data.entries[value.object_id]
        model.need(expected == value, 'FAKE_BLOB_VERSION')
        return raw

    def close(self):
        self.backend.touch('close:' + self.data.kind)
        self.closed = True


class MemoryLog:
    def __init__(self, backend, data):
        self.backend, self.data, self.root = backend, data, data.root
        self.custody = None

    def add(self, event):
        raw = canonical_bytes(event)
        size = (self.data.rows[-1].head.size if self.data.rows else 0) + len(raw) + 36
        row = EventRecord(EventHead(len(self.data.rows) + 1, model.sha(raw), size), raw)
        self.data.rows.append(row)
        return row.head

    def binding(self):
        return EventBinding(self.data.identity, self.data.stream, self.data.rows[-1].head)

    def bind_custody(self, custody):
        model.need(custody.binding == self.binding(), 'FAKE_UNWITNESSED_SUFFIX')
        self.custody = custody

    def append(self, event, expected, *, reserve_records, reserve_bytes):
        model.need(expected == self.binding().witnessed and expected.sequence + 1 + reserve_records <= 512)
        model.need(expected.size + len(canonical_bytes(event)) + 36 + reserve_bytes <= 8 * 1024 * 1024)
        self.backend.touch('before_event:' + event['kind'])
        head = self.add(event)
        self.backend.touch('before_witness:' + event['kind'])
        self.custody.persist_binding(self.binding())
        self.backend.touch('after_event:' + event['kind'])
        return head

    def fold(self, initial, reducer):
        state = initial
        for row in self.data.rows:
            state = reducer(state, row)
        return self.binding().witnessed, state

    def close(self):
        self.backend.touch('close:log')


class SnapshotOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='gt05-snapshot-test-')
        self.base = Path(self.temporary.name)
        self.backend = MemoryBackend()
        self.patch = self.backend.install()
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temporary.cleanup)
        self.journal = Journal(self.base / 'journal.jsonl')
        self.provider = Mock(spec=['__call__', 'request_stop'], return_value=candidate())
        self.current = Mock(return_value='1' * 64)
        self.owners = []
        self.addCleanup(self.close_all)
        self.owner = self.create()
        self.lease = self.journal.acquire_lease(project_id=model.PROJECT, target=model.TARGET, owner='test',
            now_ms=implementation.epoch_ms(), ttl_ms=30000)

    def create(self, provider=None):
        owner = implementation.SnapshotOwner.create(self.base, journal=self.journal,
            provider=provider or self.provider, current_source=self.current)
        self.owners.append(owner)
        return owner

    def close_all(self):
        self.backend.hook = lambda label: None
        for owner in reversed(self.owners):
            owner.close()

    def publish(self, req=None, owner=None):
        return (owner or self.owner).publish(req or request(), self.lease, deadline_ms=implementation.epoch_ms() + 10000)

    def test_success_exact_bytes_receipt_barriers_and_readonly_reopen(self):
        receipt = self.publish()
        manifest, payloads = self.owner.read_selected()
        self.assertEqual(payloads, dict(candidate().payloads))
        self.assertEqual(manifest['metadata'], parse_json(candidate().metadata_json))
        self.assertFalse(parse_json(receipt)['public_ack'])
        self.assertFalse(parse_json(receipt)['editor_activation'])
        self.assertLess(self.backend.calls.index('barrier:snapshot.json'), self.backend.calls.index('before_event:TERMINAL'))
        self.owner.close()
        reopened = implementation.SnapshotOwner.reopen(self.owner.storage_id)
        self.owners.append(reopened)
        self.assertTrue(reopened._readonly)
        self.assertEqual(reopened.lookup_bytes('snapshot'), receipt)
        self.assertEqual(self.publish(owner=reopened), receipt)
        with self.assertRaisesRegex(ValueError, 'READONLY'):
            self.publish(request('new'), reopened)

    def test_exact_retry_zero_provider_or_storage_mutation_conflict_rejected(self):
        receipt = self.publish()
        self.provider.reset_mock()
        self.backend.calls.clear()
        self.assertEqual(self.publish(), receipt)
        self.provider.assert_not_called()
        self.assertFalse(any(x.startswith(('before_file:', 'before_blob', 'before_event:')) for x in self.backend.calls))
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            self.publish(dict(request(), expected_source_sha256='2' * 64))
        self.assertFalse(self.owner._held)

    def test_global_dedupe_reconciles_other_snapshot_without_provider(self):
        receipt = self.publish()
        self.owner.close()
        other = self.create()
        self.provider.reset_mock()
        self.assertEqual(self.publish(owner=other), receipt)
        self.provider.assert_not_called()
        self.assertEqual(other._state['phase'], 'EMPTY')
        self.assertEqual(other.files.data.entries, {})

    def test_global_ledger_must_match_protected_receipt(self):
        receipt = self.publish()
        self.owner.close()
        other = self.create()
        changed = dict(parse_json(receipt), public_ack=True)
        other.journal = Mock()
        other.journal.lookup.return_value = {'status': 'COMMITTED', 'receipt': changed}
        with self.assertRaisesRegex(ValueError, 'JOURNAL_BINDING'):
            self.publish(owner=other)
        self.assertEqual(other.files.data.entries, {})

    def test_global_expired_or_unknown_lookup_never_invokes_provider(self):
        from studio.host.core.journal import JournalError
        for code in ('RETRY_HORIZON_EXPIRED', 'JOURNAL_LOCKED', 'COMMAND_NOT_FOUND'):
            with self.subTest(code=code):
                error = JournalError(code)
                error.outcome_unknown = True
                with patch.object(self.owner.journal, 'lookup', side_effect=error), self.assertRaises(JournalError):
                    self.publish()
        self.provider.assert_not_called()
        self.assertEqual(self.owner.files.data.entries, {})

    def test_caller_certificates_and_provider_boolean_fail_before_effect(self):
        for req in (dict(request(), completed=True), dict(request(), evidence={'godot': True}), dict(request(), path='foreign')):
            with self.assertRaises(ValueError):
                self.publish(req)
        self.provider.assert_not_called()
        self.provider.return_value = {'completed': True}
        with self.assertRaisesRegex(ValueError, 'PROVIDER_REQUIRED'):
            self.publish()
        self.assertEqual(self.owner._state['phase'], 'EMPTY')
        self.assertEqual(self.owner.files.data.entries, {})

    def test_provider_bad_name_oversize_and_foreign_source_no_intent(self):
        value = candidate()
        meta = parse_json(value.metadata_json)
        meta['catalog']['assets'][0]['asset_id'] = '../outside'
        cases = [replace(value, metadata_json=canonical_bytes(meta)), replace(value, source_sha256='9' * 64),
            replace(value, payloads=((model.NAMES[0], b'x' * (model.MAX_BLOB_BYTES + 1)),) + value.payloads[1:])]
        for bad in cases:
            self.provider.return_value = bad
            with self.assertRaises(ValueError):
                self.publish()
            self.assertEqual(self.owner._state['phase'], 'EMPTY')
            self.assertEqual(self.owner.files.data.entries, {})

    def test_forged_stale_lease_source_deadline_rejected_before_provider(self):
        self.lease = replace(self.lease, owner='forged')
        with self.assertRaisesRegex(Exception, 'STALE_LEASE'):
            self.publish()
        self.provider.assert_not_called()
        with self.assertRaisesRegex(Exception, 'DEADLINE_EXPIRED'):
            self.owner.publish(request(), self.lease, deadline_ms=implementation.epoch_ms() - 1)
        self.assertEqual(self.owner._state['phase'], 'EMPTY')

    def test_source_or_lease_change_during_provider_no_intent(self):
        for kind in ('source', 'lease'):
            def provider(req):
                if kind == 'source':
                    self.current.return_value = '2' * 64
                else:
                    self.journal.acquire_lease(project_id=model.PROJECT, target=model.TARGET, owner='test',
                        now_ms=implementation.epoch_ms(), ttl_ms=30000)
                return candidate()
            self.owner.provider = provider
            with self.assertRaises(Exception):
                self.publish()
            self.assertEqual(self.owner._state['phase'], 'EMPTY')
            self.assertEqual(self.owner.files.data.entries, {})
            self.current.return_value = '1' * 64

    def test_stop_signals_active_provider_without_waiting_for_lock(self):
        entered, release = threading.Event(), threading.Event()
        failures = []

        class Provider:
            def __call__(self, req):
                entered.set()
                release.wait(3)
                return candidate()

            def request_stop(self):
                release.set()

        self.owner.provider = Provider()
        def run():
            try:
                self.publish()
            except BaseException as error:
                failures.append(error)
        worker = threading.Thread(target=run)
        worker.start()
        self.assertTrue(entered.wait(2))
        self.assertIn(b'VALIDATING', self.owner.lookup_bytes('snapshot'))
        self.owner.stop()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertTrue(self.owner._state['stopped'])
        self.assertEqual(self.owner.files.data.entries, {})

    def test_provider_verify_receives_original_deadline_and_owned_stop_outside_lock(self):
        owner = self.owner
        deadline = implementation.epoch_ms() + 10000
        calls = []

        class Provider:
            def __call__(self, req):
                raise AssertionError('verify method must receive the original budget')

            def verify(self, req, *, deadline_ms, stop):
                calls.append((req, deadline_ms, stop))
                acquired = []
                def take_lock():
                    with owner._mutex:
                        acquired.append(True)
                worker = threading.Thread(target=take_lock)
                worker.start()
                worker.join(2)
                if worker.is_alive() or acquired != [True]:
                    raise AssertionError('provider verification held the publication mutex')
                return candidate()

        owner.provider = Provider()
        receipt = owner.publish(request(), self.lease, deadline_ms=deadline)
        self.assertEqual(parse_json(receipt)['status'], 'COMMITTED')
        self.assertEqual(calls[0][:2], (request(), deadline))
        self.assertIs(calls[0][2], owner._stop)

    def test_provider_verify_result_after_deadline_cannot_begin_effects(self):
        deadline = implementation.epoch_ms() + 10000
        advance = patch('studio.host.blender.deadline.time.time', return_value=(deadline + 1) / 1000)
        self.addCleanup(advance.stop)

        class Provider:
            def __call__(self, req):
                raise AssertionError('verify hook required')

            def verify(self, req, *, deadline_ms, stop):
                advance.start()
                return candidate()

        self.owner.provider = Provider()
        with self.assertRaisesRegex(ValueError, 'DEADLINE_EXPIRED'):
            self.owner.publish(request(), self.lease, deadline_ms=deadline)
        self.assertEqual(self.owner._state['phase'], 'EMPTY')
        self.assertEqual(self.owner.files.data.entries, {})
        self.assertEqual(self.owner.store.data.entries, {})
        self.assertFalse(self.owner._held)

    def test_effect_fault_prefix_matrix_never_replays(self):
        points = ['after_event:INTENT', *('after_file:' + name for name in model.NAMES),
                  'after_file:' + model.MANIFEST, 'after_event:STAGED', 'after_event:SELECTING',
                  'after_file:' + model.SELECTOR, 'barrier:' + model.SELECTOR, 'before_event:TERMINAL']
        for i, point in enumerate(points):
            with self.subTest(point=point):
                owner = self.create()
                req = request('fault-%d' % i)
                fired = []
                def fail(label):
                    if label == point and not fired:
                        fired.append(label)
                        raise OSError('injected interruption')
                self.backend.hook = fail
                with self.assertRaises(model.SnapshotError) as caught:
                    self.publish(req, owner)
                self.assertTrue(caught.exception.outcome_unknown)
                self.assertIs(caught.exception.cleanup_owner, owner)
                self.backend.hook = lambda label: None
                owner.close()
                reopened = implementation.SnapshotOwner.reopen(owner.storage_id)
                self.owners.append(reopened)
                self.provider.reset_mock()
                raw = self.publish(req, reopened)
                self.assertEqual(parse_json(raw)['status'], 'UNKNOWN')
                self.provider.assert_not_called()
                with self.assertRaisesRegex(ValueError, 'NOT_COMMITTED'):
                    reopened.read_selected()

    def test_stop_before_each_effect_boundary_no_selection_receipt(self):
        for i, point in enumerate(['after_event:INTENT', 'after_blob', 'after_file:fixture.glb',
                                  'after_event:STAGED', 'after_event:SELECTING', 'after_file:snapshot.json']):
            owner = self.create()
            fired = []
            def stop(label):
                if label == point and not fired:
                    fired.append(label)
                    owner.request_stop()
            self.backend.hook = stop
            with self.assertRaises(model.SnapshotError):
                self.publish(request('stop-%d' % i), owner)
            self.backend.hook = lambda label: None
            owner.stop()
            self.assertTrue(owner._state['stopped'])
            self.assertEqual(parse_json(owner.lookup_bytes('stop-%d' % i))['status'], 'UNKNOWN')

    def test_corrupt_selector_or_root_reopen_rejects_and_last_good_survives(self):
        receipt = self.publish()
        saved = self.owner.read_selected()[1]
        failed = self.create()
        self.backend.hook = lambda label: (_ for _ in ()).throw(OSError('disk full')) if label == 'before_file:fixture.glb' else None
        with self.assertRaises(model.SnapshotError):
            self.publish(request('failed'), failed)
        self.backend.hook = lambda label: None
        self.assertEqual(self.owner.lookup_bytes('snapshot'), receipt)
        self.assertEqual(self.owner.read_selected()[1], saved)
        old, raw = self.owner.files.data.entries[model.SELECTOR]
        self.owner.files.data.entries[model.SELECTOR] = (replace(old, identity=self.backend.identity(len(raw))), raw)
        with self.assertRaisesRegex(ValueError, 'SELECTOR_CHANGED'):
            self.owner.read_selected()

    def test_unwitnessed_suffix_and_terminal_witness_failure_hold(self):
        def fail(label):
            if label == 'before_witness:TERMINAL':
                raise OSError('witness unavailable')
        self.backend.hook = fail
        with self.assertRaises(model.SnapshotError):
            self.publish()
        self.backend.hook = lambda label: None
        self.owner.close()
        with self.assertRaisesRegex(ValueError, 'OPEN_HELD'):
            implementation.SnapshotOwner.reopen(self.owner.storage_id)

    def test_staged_and_selecting_reopen_reread_recorded_bytes(self):
        for i, point in enumerate(('after_event:STAGED', 'after_event:SELECTING', 'after_file:snapshot.json')):
            for tamper in ('payload', 'manifest', 'selector'):
                if tamper == 'selector' and point != 'after_file:snapshot.json':
                    continue
                with self.subTest(point=point, tamper=tamper):
                    owner = self.create()
                    fired = []
                    def fail(label):
                        if label == point and not fired:
                            fired.append(label)
                            raise OSError('crash')
                    self.backend.hook = fail
                    with self.assertRaises(model.SnapshotError):
                        self.publish(request('tamper-%d-%s' % (i, tamper)), owner)
                    self.backend.hook = lambda label: None
                    name = {'payload': 'fixture.glb', 'manifest': model.MANIFEST, 'selector': model.SELECTOR}[tamper]
                    old, raw = owner.files.data.entries[name]
                    owner.files.data.entries[name] = (old, raw + b'corrupted')
                    owner.close()
                    with self.assertRaisesRegex(ValueError, 'OPEN_HELD'):
                        implementation.SnapshotOwner.reopen(owner.storage_id)

    def test_stop_after_terminal_preserves_exact_receipt_and_readonly_stop_has_no_effect(self):
        receipt = self.publish()
        self.owner.stop()
        self.assertTrue(self.owner._state['stopped'])
        self.assertEqual(self.owner.lookup_bytes('snapshot'), receipt)
        self.assertEqual(self.publish(), receipt)
        self.owner.close()
        reopened = implementation.SnapshotOwner.reopen(self.owner.storage_id)
        self.owners.append(reopened)
        sequence = reopened._head.sequence
        with self.assertRaisesRegex(ValueError, 'READONLY'):
            reopened.stop()
        self.assertEqual(reopened._head.sequence, sequence)
        self.assertEqual(reopened.lookup_bytes('snapshot'), receipt)

    def test_journal_capacity_rejects_before_intent_and_protected_bytes(self):
        self.owner.journal = Journal(self.base / 'limited.jsonl', limits=JournalLimits(max_records=1))
        self.lease = self.owner.journal.acquire_lease(project_id=model.PROJECT, target=model.TARGET, owner='test',
            now_ms=implementation.epoch_ms(), ttl_ms=30000)
        with self.assertRaisesRegex(Exception, 'RECORD_LIMIT'):
            self.publish()
        self.assertEqual(self.owner._state['phase'], 'EMPTY')
        self.assertEqual(self.owner.files.data.entries, {})
        self.assertFalse(self.owner._held)

    def test_cleanup_retains_failed_owner_for_retry(self):
        self.owner.files.close = Mock(side_effect=[OSError('close failed'), None])
        with self.assertRaises(model.SnapshotError) as caught:
            self.owner.close()
        self.assertIs(caught.exception.cleanup_owner, self.owner)
        self.assertIsNotNone(self.owner.files)
        self.owner.close()
        self.assertTrue(self.owner._closed)


if __name__ == '__main__':
    unittest.main()
