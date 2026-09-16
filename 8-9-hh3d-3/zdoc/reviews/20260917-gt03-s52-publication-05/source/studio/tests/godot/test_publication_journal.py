"""Native protected Windows journal tests; engine facts are synthetic only."""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import replace
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_publication_journal', STUDIO/'godot-addon/publication_journal.py')
journal = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = journal
SPEC.loader.exec_module(journal)
state_model = journal.state_model
from studio.host.core.custody import decode_record
from studio.host.core.custody_registry import RegistryCustody, BASE_PATH, _RegistryApi, _HKCU, _ACCESS
from studio.host.core.private_events import EventLogError, pending_event_cleanup

if os.name == 'nt':
    import winreg


def digest(label):
    return hashlib.sha256(label.encode()).hexdigest()


def revision(label):
    return 'sha256:' + digest(label)


def configuration():
    files = {state_model.SCENE_PATH: {'sha256': digest('scene'), 'size_bytes': 100},
             state_model.SCRIPT_PATH: {'sha256': digest('script'), 'size_bytes': 15}}
    engine, scene = digest('engine'), revision('scene')
    return {'schema': state_model.SCHEMA, 'sequence': 1, 'kind': 'CONFIG', 'project_id': 'journal-test',
        'observed_ms': 100, 'engine_sha256': engine, 'source_closure_sha256': digest('closure'),
        'initial': {'project_revision': state_model.project_revision(files, scene, engine),
                    'scene_revision': scene, 'files': files,
                    'selection': {'generation': 0, 'identity': revision('initial-selection')}}}


def event(state, kind, **fields):
    snapshot = state.snapshot()
    return {'schema': state_model.SCHEMA, 'sequence': state.event_count + 1, 'kind': kind,
            'project_id': snapshot['project_id'], 'observed_ms': snapshot['last_observed_ms'] + 1, **fields}


def prepared(state):
    before = state.snapshot()['last_good']
    now = state.snapshot()['last_observed_ms'] + 1
    return event(state, 'PREPARED', command_id='cmd.save', digest=revision('cmd.save'), operation='scene.save',
        candidate_id='candidate-' + 'a' * 32, before_project_revision=before['project_revision'],
        before_scene_revision=before['scene_revision'], expected_files=before['files'], parent_selection=before['selection'],
        admission={'lease_id': 'lease.journal', 'fencing_epoch': 1, 'admitted_ms': now,
                   'deadline_ms': now + 1000, 'lease_expires_ms': 10000,
                   'editor_session_id': 'editor.synthetic', 'editor_generation': 1},
        checkpoint_sha256=digest('checkpoint'), script_input=None)


def next_event(state):
    """Synthetic engine facts exercise durable storage, never engine proof."""
    snapshot = state.snapshot()
    command = snapshot['commands'][-1]
    common = {'command_id': command['command_id'], 'digest': command['digest']}
    phase = command['phase']
    if phase == 'PREPARED':
        request = command['prepared']
        files = {path: {'object_id': 'blob-' + f'{index:032x}',
                 'volume': snapshot['store_identity']['volume'], 'file_id': f'{index + 10:032x}', **info}
                 for index, (path, info) in enumerate(request['expected_files'].items(), 1)}
        candidate = {'candidate_id': request['candidate_id'], 'project_revision': request['before_project_revision'],
            'scene_revision': request['before_scene_revision'], 'engine_sha256': snapshot['engine_sha256'], 'files': files,
            'manifest': {'object_id': 'blob-' + '3'.zfill(32), 'volume': snapshot['store_identity']['volume'],
                         'file_id': '13'.zfill(32), 'size_bytes': 1000, 'sha256': digest('manifest')}}
        return event(state, 'STAGED', **common, candidate=candidate)
    candidate = command['candidate']
    if phase in ('STAGED', 'ACTIVATING'):
        kind = 'VALIDATED' if phase == 'STAGED' else 'READBACK'
        observation = {'observation_id': kind.lower() + '.observation', 'editor_session_id': kind.lower() + '.session',
            'editor_generation': 1, 'candidate_id': candidate['candidate_id'], 'project_revision': candidate['project_revision'],
            'scene_revision': candidate['scene_revision'], 'engine_sha256': candidate['engine_sha256'],
            'source_closure_sha256': snapshot['source_closure_sha256'], 'manifest_sha256': candidate['manifest']['sha256'],
            'files': {path: {k: value[k] for k in ('sha256', 'size_bytes')} for path, value in candidate['files'].items()},
            'parse_status': 'PASS', 'import_status': 'PASS', 'exit_code': 0, 'tree_drained': True, 'logs_clean': True}
        fields = {'observation': observation}
        if kind == 'READBACK':
            fields['selection'] = command['selection']
        return event(state, kind, **common, **fields)
    if phase == 'VALIDATED':
        request = command['prepared']
        current = {'project_revision': request['before_project_revision'], 'scene_revision': request['before_scene_revision'],
            'files': request['expected_files'], 'selection': request['parent_selection'],
            **{k: request['admission'][k] for k in ('lease_id', 'fencing_epoch', 'editor_session_id', 'editor_generation')}}
        selection = {'generation': request['parent_selection']['generation'] + 1,
            'identity': state_model.selection_identity(snapshot['project_id'], command['command_id'], command['digest'],
                                                      request['parent_selection'], candidate)}
        return event(state, 'ACTIVATING', **common, current=current, selection=selection)
    if phase == 'READBACK':
        return event(state, 'COMMITTED', **common, readback_event_sha256=command['readback_event_sha256'],
                     after_project_revision=candidate['project_revision'], selection=command['selection'])
    raise AssertionError('no next phase')


@unittest.skipUnless(os.name == 'nt', 'requires actual Windows NTFS and protected Registry custody')
class PublicationJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        RegistryCustody.provision_base()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-gt03-journal-')
        self.base = Path(self.temp.name).resolve()
        self.storage_id = uuid.uuid4().hex
        self.owners = []
        with self.assertRaises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH + '\\' + self.storage_id,
                           0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        self.addCleanup(self.cleanup)
        self.owner = self.create()

    def create(self, config=None):
        try:
            owner = journal.PublicationJournal.create(self.base, storage_id=self.storage_id,
                                                      config=configuration() if config is None else config)
        except journal.PublicationJournalError as exc:
            if exc.cleanup_owner is not None:
                self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner)
        return owner

    def reopen(self, **changes):
        try:
            owner = journal.PublicationJournal.reopen(self.storage_id,
                project_id=changes.get('project_id', 'journal-test'))
        except journal.PublicationJournalError as exc:
            if exc.cleanup_owner is not None:
                self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner)
        return owner

    def cleanup(self):
        for owner in reversed(self.owners):
            owner.close()
        # Delete only this randomly minted absent-before-create leaf by a
        # checked no-follow native handle. Never remove the shared base keys.
        api = _RegistryApi()
        try:
            key = W.HANDLE()
            code = api.adv.RegOpenKeyExW(_HKCU, BASE_PATH + '\\' + self.storage_id, 8,
                                       _ACCESS | 0x10000, C.byref(key))
            if code == 0:
                api.keys.add(key.value)
                expected = '\\REGISTRY\\USER\\' + api.owner + '\\' + BASE_PATH + '\\' + self.storage_id
                self.assertEqual(api.native_name(key.value).casefold(), expected.casefold())
                self.assertEqual(api.query(key.value, 'Format'),
                                 (3, b'hh-registry-custody-1\0' + self.storage_id.encode()))
                api.nt.NtDeleteKey.argtypes = [W.HANDLE]
                api.nt.NtDeleteKey.restype = W.LONG
                self.assertEqual(api.nt.NtDeleteKey(key), 0)
                api.close_key(key.value)
            else:
                self.assertEqual(code, 2)
        finally:
            api.close_owned()
        # TemporaryDirectory was minted by this fixture; verify before its
        # recursive cleanup so a substituted parent cannot widen the target.
        self.assertEqual(self.base, Path(self.temp.name).resolve())
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith('hh-gt03-journal-'))
        self.temp.cleanup()

    def test_native_genesis_excluded_and_config_binds_real_root_and_custody(self):
        observed = self.owner.snapshot()
        self.assertEqual(observed['event_count'], 1)
        self.assertEqual(observed['journal_event_sequence'], 2)
        self.assertEqual(observed['store_identity'], {'volume': str(self.owner._blobs.root_identity.volume),
                                                     'file_id': self.owner._blobs.root_identity.file_id})
        record = decode_record(self.owner._registry.read())
        self.assertEqual(record['events']['binding']['witnessed']['sequence'], 2)
        self.assertFalse(observed['public_ack'])
        self.assertFalse(observed['engine_effects_verified'])
        self.assertFalse(observed['execution_permitted'])
        self.assertIsNone(self.owner.lookup('not.present'))

    def test_invalid_prospective_transition_never_calls_native_append(self):
        before = self.owner._log.binding()
        invalid = prepared(self.owner._state)
        invalid['before_project_revision'] = revision('stale')
        with mock.patch.object(self.owner._log, 'append', side_effect=AssertionError('native append called')) as append:
            with self.assertRaisesRegex(state_model.PublicationError, 'PUBLICATION_STALE_BASE'):
                self.owner.append(invalid)
            append.assert_not_called()
        self.assertEqual(self.owner._log.binding(), before)
        self.assertFalse(self.owner.snapshot()['journal_held'])

    def test_invalid_config_is_rejected_before_native_provisioning(self):
        invalid = configuration()
        invalid['initial']['project_revision'] = revision('stale')
        with mock.patch.object(RegistryCustody, 'create', side_effect=AssertionError('native provisioning called')) as create:
            with self.assertRaises(state_model.PublicationError):
                journal.PublicationJournal.create(self.base, storage_id=uuid.uuid4().hex, config=invalid)
            create.assert_not_called()

    def test_reducer_loader_binds_each_snapshot_path_and_exact_source(self):
        source = (STUDIO/'godot-addon/publication_state.py').read_bytes()
        modules = []
        for index in (1, 2):
            root = self.base / ('loader-' + str(index))
            root.mkdir()
            (root/'publication_journal.py').write_bytes((STUDIO/'godot-addon/publication_journal.py').read_bytes())
            (root/'publication_state.py').write_bytes(source + ('\nLOADER_MARKER = %d\n' % index).encode())
            name = 'journal_loader_fixture_' + str(index)
            spec = importlib.util.spec_from_file_location(name, root/'publication_journal.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            finally:
                sys.modules.pop(name, None)
            modules.append(module)
        self.assertIsNot(modules[0].state_model, modules[1].state_model)
        self.assertNotEqual(modules[0]._STATE_MODULE, modules[1]._STATE_MODULE)
        self.assertEqual([module.state_model.LOADER_MARKER for module in modules], [1, 2])
        for module in modules:
            self.assertEqual(module._STATE_SHA256, hashlib.sha256(module._STATE_PATH.read_bytes()).hexdigest())

    def test_native_append_is_cas_bound_and_custody_barrier_is_read_back(self):
        before = self.owner._head
        with mock.patch.object(self.owner._log, 'append', wraps=self.owner._log.append) as append:
            self.owner.append(prepared(self.owner._state))
        self.assertEqual(append.call_args.args[1], before)
        self.assertGreater(append.call_args.kwargs['reserve_records'], 0)
        self.assertGreater(append.call_args.kwargs['reserve_bytes'], 0)
        self.assertEqual(self.owner._head, self.owner._custody.binding.witnessed)
        self.assertEqual(self.owner._log.read(3).event, self.owner._state.events[-1])

    def test_pending_reopen_is_read_only_and_never_resumes(self):
        self.owner.append(prepared(self.owner._state))
        old = self.owner.lookup('cmd.save', revision('cmd.save'))
        self.owner.close()
        reopened = self.reopen()
        self.assertEqual(reopened.lookup('cmd.save', revision('cmd.save')), old)
        self.assertEqual(reopened.snapshot()['pending_command_id'], 'cmd.save')
        self.assertTrue(reopened.snapshot()['journal_read_only'])
        before = reopened._log.binding()
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_REOPEN_READ_ONLY'):
            reopened.append(next_event(reopened._state))
        self.assertEqual(reopened._log.binding(), before)

    def test_committed_attestations_return_original_receipt_without_public_ack(self):
        self.owner.append(prepared(self.owner._state))
        for _ in range(5):
            self.owner.append(next_event(self.owner._state))
        original = self.owner.lookup('cmd.save', revision('cmd.save'))
        self.assertEqual(original['phase'], 'COMMITTED')
        self.assertFalse(original['public_ack'])
        self.assertFalse(original['receipt']['public_ack'])
        self.assertTrue(original['receipt']['durable_owner_required'])
        before = self.owner._head
        altered = self.owner.lookup('cmd.save')
        altered['receipt']['status'] = 'forged'
        self.assertEqual(self.owner.lookup('cmd.save'), original)
        self.assertEqual(self.owner._head, before)
        self.owner.close()
        reopened = self.reopen()
        self.assertEqual(reopened.lookup('cmd.save', revision('cmd.save')), original)
        self.assertFalse(reopened.snapshot()['engine_effects_verified'])
        self.assertTrue(reopened.snapshot()['journal_read_only'])

    def test_changed_same_id_digest_rejects_without_disabling_lookup_or_stop(self):
        self.owner.append(prepared(self.owner._state))
        before = self.owner._head
        original = self.owner.lookup('cmd.save', revision('cmd.save'))
        with self.assertRaisesRegex(state_model.PublicationError, 'PUBLICATION_COMMAND_CONFLICT'):
            self.owner.lookup('cmd.save', revision('changed'))
        invalid = next_event(self.owner._state)
        invalid['digest'] = revision('changed')
        with mock.patch.object(self.owner._log, 'append', side_effect=AssertionError('unexpected native append')) as append:
            with self.assertRaisesRegex(state_model.PublicationError, 'PUBLICATION_COMMAND_CONFLICT'):
                self.owner.append(invalid)
            append.assert_not_called()
        self.assertEqual(self.owner._log.binding().witnessed, before)
        self.assertEqual(self.owner.lookup('cmd.save', revision('cmd.save')), original)
        self.assertFalse(self.owner.snapshot()['journal_held'])
        stopped = self.owner.append(event(self.owner._state, 'STOP', reason='USER_STOP'))
        self.assertTrue(stopped['stopped'])
        self.assertFalse(stopped['journal_held'])
        self.assertEqual(self.owner.lookup('cmd.save')['receipt']['reason'], 'STOPPED_BEFORE_ACTIVATION')

    def test_lost_append_response_holds_and_reopen_preserves_actual_record(self):
        native_append = self.owner._log.append
        def lost(*args, **kwargs):
            native_append(*args, **kwargs)
            raise RuntimeError('injected reply loss after actual append and custody')
        with mock.patch.object(self.owner._log, 'append', side_effect=lost):
            with self.assertRaises(journal.PublicationJournalError) as caught:
                self.owner.append(prepared(self.owner._state))
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIs(caught.exception.cleanup_owner, self.owner)
        self.owner.close()
        reopened = self.reopen()
        self.assertEqual(reopened.lookup('cmd.save')['phase'], 'PREPARED')
        self.assertEqual(reopened.snapshot()['event_count'], 2)

    def test_custody_failure_after_flush_keeps_ahead_history_and_refuses_reopen(self):
        event_path = self.owner._log.root / '.events'
        registry_before = self.owner._registry.read()
        with mock.patch.object(self.owner._custody, 'persist_binding', side_effect=RuntimeError('injected custody failure')):
            with self.assertRaises(journal.PublicationJournalError):
                self.owner.append(prepared(self.owner._state))
        self.assertEqual(self.owner._registry.read(), registry_before)
        self.owner.close()
        retained = event_path.read_bytes()
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_OPEN_FAILED'):
            self.reopen()
        self.assertEqual(event_path.read_bytes(), retained)

    def test_external_append_and_wrong_root_identity_poison_owner(self):
        stop = event(self.owner._state, 'STOP', reason='USER_STOP')
        self.owner._log.append(stop, self.owner._head)
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_RECOVERY_REQUIRED'):
            self.owner.snapshot()
        self.owner.close()
        reopened = self.reopen()
        original = reopened._blobs.root_identity
        reopened._blobs.root_identity = replace(original, file_id='0' * 32)
        try:
            with self.assertRaises(journal.PublicationJournalError):
                reopened.snapshot()
        finally:
            reopened._blobs.root_identity = original

    def test_second_owner_and_wrong_project_cannot_open_current_native_roots(self):
        with self.assertRaises(journal.PublicationJournalError):
            self.reopen()
        self.assertFalse(self.owner.snapshot()['journal_held'])
        self.owner.close()
        with self.assertRaises(journal.PublicationJournalError):
            self.reopen(project_id='different-project')

    def test_closed_native_file_owner_cannot_pass_cached_root_identity(self):
        self.owner._files.close()
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_RECOVERY_REQUIRED'):
            self.owner.snapshot()
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_HELD'):
            self.owner.lookup('not.present')

    def test_closed_native_blob_owner_cannot_pass_cached_root_identity(self):
        self.owner._blobs.close()
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_RECOVERY_REQUIRED'):
            self.owner.lookup('not.present')
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_HELD'):
            self.owner.snapshot()

    def test_append_identity_conflict_holds_before_native_write(self):
        request = prepared(self.owner._state)
        original = self.owner._blobs.root_identity
        self.owner._blobs.root_identity = replace(original, file_id='0' * 32)
        try:
            with mock.patch.object(self.owner._log, 'append', side_effect=AssertionError('unexpected native append')) as append:
                with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_RECOVERY_REQUIRED'):
                    self.owner.append(request)
                append.assert_not_called()
        finally:
            self.owner._blobs.root_identity = original
        with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_JOURNAL_HELD'):
            self.owner.lookup('not.present')

    def test_checks_complete_history_not_only_native_checksum(self):
        # A trusted bypass writes a checksummed native row with invalid typed
        # history. Reopen must reject it even though custody exactly matches.
        invalid = prepared(self.owner._state)
        invalid['sequence'] = 99
        self.owner._log.append(invalid, self.owner._head)
        event_path = self.owner._log.root / '.events'
        self.owner.close()
        retained = event_path.read_bytes()
        with self.assertRaises(journal.PublicationJournalError):
            self.reopen()
        self.assertEqual(event_path.read_bytes(), retained)

    def test_close_failure_retains_all_ancestors_for_retry(self):
        log, registry, files, blobs = self.owner._log, self.owner._registry, self.owner._files, self.owner._blobs
        with mock.patch.object(log, 'close', side_effect=RuntimeError('injected close refusal')):
            with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_CLOSE_UNCERTAIN') as caught:
                self.owner.close()
        self.assertIs(caught.exception.cleanup_owner, self.owner)
        self.assertIs(self.owner._log, log)
        self.assertIs(self.owner._registry, registry)
        self.assertIs(self.owner._files, files)
        self.assertIs(self.owner._blobs, blobs)
        self.owner.close()
        self.assertNotIn(log, pending_event_cleanup())

    def test_constructor_cleanup_failure_preserves_unassigned_native_owner(self):
        self.owner.close()
        native_reopen = journal.PrivateEventLog.reopen
        retained = []
        def fail_after_open(*args, **kwargs):
            log = native_reopen(*args, **kwargs)
            retained.append(log)
            error = EventLogError('INJECTED_INIT_FAILURE', outcome_unknown=True)
            error.cleanup_owner = log
            raise error
        with mock.patch.object(journal.PrivateEventLog, 'reopen', side_effect=fail_after_open), \
             mock.patch.object(journal.PrivateEventLog, 'close', side_effect=RuntimeError('injected cleanup refusal')):
            with self.assertRaisesRegex(journal.PublicationJournalError, 'PUBLICATION_INIT_CLEANUP_REQUIRED') as caught:
                self.reopen()
        held = caught.exception.cleanup_owner
        self.assertIs(held._extra_cleanup, retained[0])
        self.assertIsNotNone(held._blobs)
        self.assertIsNotNone(held._files)
        self.assertIsNotNone(held._registry)
        self.assertIn(retained[0], pending_event_cleanup())
        held.close()
        self.assertNotIn(retained[0], pending_event_cleanup())

    def test_wrapper_lock_holds_until_custody_barrier_finishes(self):
        entered, release, read_done = (threading.Event() for _ in range(3))
        persist = self.owner._custody.persist_binding
        errors = []
        def delayed(binding):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('fixture barrier deadline')
            persist(binding)
        def append():
            try:
                self.owner.append(prepared(self.owner._state))
            except BaseException as exc:
                errors.append(exc)
        def read():
            try:
                self.owner.snapshot()
            except BaseException as exc:
                errors.append(exc)
            finally:
                read_done.set()
        writer, reader = threading.Thread(target=append), threading.Thread(target=read)
        with mock.patch.object(self.owner._custody, 'persist_binding', side_effect=delayed):
            writer.start()
            try:
                self.assertTrue(entered.wait(5))
                reader.start()
                self.assertFalse(read_done.wait(.05))
            finally:
                release.set()
                writer.join(5)
                if reader.ident is not None:
                    reader.join(5)
        self.assertFalse(writer.is_alive())
        self.assertFalse(reader.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(read_done.is_set())


if __name__ == '__main__':
    unittest.main()
