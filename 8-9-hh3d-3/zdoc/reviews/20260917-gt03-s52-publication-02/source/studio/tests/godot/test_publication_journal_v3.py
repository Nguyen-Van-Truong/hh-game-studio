"""Real Windows journal/selector effects; all engine/auth facts are synthetic.

These tests prove storage ordering and recovery, never actual Godot adoption,
validator execution, authentication, or a public committed response.
"""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


journal = load('gt03_journal_v3_tests', STUDIO / 'godot-addon/publication_journal_v3.py')
legacy = load('gt03_v3_cleanup_helpers', Path(__file__).with_name('test_publication_journal.py'))
codec, state = journal.bundle_codec, journal.state_model
from studio.protocol.core import parse_json
from studio.host.core.custody_registry import RegistryCustody


def sha(value): return hashlib.sha256(value.encode()).hexdigest()
def rev(value): return 'sha256:' + sha(value)
def now(owner=None):
    return max(time.time_ns() // 1_000_000, 0 if owner is None else owner._state.snapshot()['last_observed_ms'])


def bundle(scene='scene-one'):
    files = {name: ('uid://abc123\n' if name.endswith('.uid') else 'synthetic ' + name + '\n').encode()
             for name in codec.PATHS}
    files[codec.SCENE_PATH] = scene.encode()
    return codec.create_bundle(files, scene_revision=rev('captured-state'), engine_sha256=sha('validator'))


def configuration():
    return {'schema': state.SCHEMA, 'kind': 'CONFIG', 'sequence': 1, 'project_id': 'v3-journal-test',
            'observed_ms': now(), 'validator_engine_sha256': sha('validator'),
            'editor_engine_sha256': sha('editor'), 'source_closure_sha256': sha('source'),
            'validation_source_release_sha256': sha('validation-source')}


@unittest.skipUnless(os.name == 'nt', 'actual Windows native protected roots/Registry required')
class JournalV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): RegistryCustody.provision_base()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-gt03-journal-')
        self.base = Path(self.temp.name).resolve()
        self.storage_id, self.owners = uuid.uuid4().hex, []
        self.addCleanup(lambda: legacy.PublicationJournalTests.cleanup(self))

    def create(self):
        try:
            owner = journal.PublicationJournalV3.create(self.base, storage_id=self.storage_id,
                                                       config=configuration(), initial_bundle=bundle())
        except journal.PublicationJournalV3Error as exc:
            if exc.cleanup_owner is not None: self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner)
        return owner

    def reopen(self):
        try:
            owner = journal.PublicationJournalV3.reopen(self.storage_id, project_id='v3-journal-test')
        except journal.PublicationJournalV3Error as exc:
            if exc.cleanup_owner is not None: self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner)
        return owner

    def capture(self, owner, value=None, command='command.save'):
        value = bundle('scene-two') if value is None else value
        t = now(owner)
        editor = {'session_id': 'synthetic-editor', 'pid': 1234, 'creation_filetime': '123456789',
                  'root_identity': {'volume': '1', 'file_id': 'a' * 32},
                  'engine_sha256': sha('editor'), 'installed_source_sha256': sha('installed')}
        admission = {'session_id': 'synthetic-auth', 'catalog_digest': rev('catalog'),
                     'lease_id': 'lease-one', 'fencing_epoch': 1, 'admitted_ms': t,
                     'deadline_ms': t + 30000, 'lease_expires_ms': t + 30000}
        owner.capture_prepared(command, rev(command), expected_revision=value.scene_revision,
            editor=editor, editor_generation=1, root_instance_id=1, admission=admission,
            scratch_name='capture-' + uuid.uuid4().hex + '.tscn', observed_ms=t)
        p = owner.lookup(command)['capture_prepared']; t = now(owner)
        files = parse_json(value.manifest_bytes)['files']
        owner.captured(command, rev(command), {'capture_id': 'capture-' + uuid.uuid4().hex,
            'scratch_name': p['scratch_name'], 'editor': editor, 'generation_before': 1,
            'generation_after': 1, 'root_instance_id': 1, 'effect_started_ms': t,
            'effect_completed_ms': t, 'semantic_revision': value.scene_revision,
            'semantic_sha256': value.scene_revision[7:], 'files': files,
            'scene_sha256': files[codec.SCENE_PATH]['sha256'],
            'scene_size_bytes': files[codec.SCENE_PATH]['size_bytes']}, observed_ms=t)
        return value

    def activate(self, owner, command='command.save'):
        value = self.capture(owner, command=command)
        before = set(p.name for p in owner._files.root.iterdir())
        owner.prepare(command, rev(command), value, observed_ms=now(owner))
        self.assertEqual(set(p.name for p in owner._files.root.iterdir()), before)
        owner.stage_prepared(command, rev(command), observed_ms=now(owner))
        self.assertEqual(len(set(p.name for p in owner._files.root.iterdir()) - before), 12)
        m = parse_json(value.manifest_bytes); t = now(owner)
        owner.validated(command, rev(command), {'command_id': command, 'project_revision': value.project_revision,
            'scene_revision': value.scene_revision, 'manifest_sha256': hashlib.sha256(value.manifest_bytes).hexdigest(),
            'input_files_sha256': state.digest(m['files']), 'source_release_sha256': sha('validation-source'),
            'validator_engine_sha256': sha('validator'), 'observation_sha256': sha('observation'),
            'evidence_sha256': sha('evidence'), 'run_id': 'hh-gt03-' + uuid.uuid4().hex,
            'validation_started_ms': t, 'validation_completed_ms': t, 'context_kind': 'isolated_candidate',
            'public_ack': False, 'selected_state_verified': False, 'live_editor_adoption_verified': False}, observed_ms=t)
        current = state.activation_current(owner.lookup(command)['capture_prepared'])
        owner.prepare_activation(command, rev(command), current=current, observed_ms=now(owner))
        return value

    def adopt(self, owner, command='command.save'):
        c = owner.lookup(command); p, m = c['capture_prepared'], c['bundle_manifest']; t = now(owner)
        adoption = {'adoption_id': 'adoption-' + uuid.uuid4().hex, 'context_kind': 'live_editor',
            'editor': p['editor'], 'generation_before': 1, 'generation_after': 2,
            'root_instance_id_before': 1, 'root_instance_id_after': 2,
            'effect_started_ms': t, 'effect_completed_ms': t,
            'semantic_revision': m['caller_observations']['scene_revision'],
            'semantic_sha256': m['caller_observations']['scene_revision'][7:],
            'project_revision': m['project_revision'], 'manifest_sha256': state.digest(m), 'files': m['files'],
            'selection': c['selector']['selection'], 'selector_version': c['selector_version'],
            'scene_path': 'res://scenes/fixture.tscn', 'history_boundary': True}
        owner.readback(command, rev(command), adoption, observed_ms=t)
        return adoption

    def test_complete_native_chain_commits_then_reopens_selected_candidate_readonly(self):
        owner = self.create(); old = owner.selection_facts(); value = self.activate(owner)
        owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        new = owner.selection_facts()
        self.assertNotEqual(old['selector_version']['file_id'], new['selector_version']['file_id'])
        self.assertEqual(new['selector']['selection']['generation'], 1)
        self.assertEqual(owner.read_selected_bundle(), value)
        self.adopt(owner)
        result = owner.commit('command.save', rev('command.save'), observed_ms=now(owner))
        self.assertEqual(result['phase'], 'COMMITTED')
        self.assertIs(result['public_ack'], False); self.assertIs(result['engine_effects_verified'], False)
        before = owner._head
        self.assertEqual(owner.commit('command.save', rev('command.save'), observed_ms=now(owner)), result)
        self.assertEqual(owner._head, before)
        events = [parse_json(raw)['kind'] for raw in owner._native_events()]
        self.assertEqual(events[3:], ['CONFIG', 'CAPTURE_PREPARED', 'CAPTURED', 'PREPARED', 'STAGED',
            'VALIDATED', 'ACTIVATING', 'SELECTED', 'READBACK', 'COMMITTED'])
        owner.close(); reopened = self.reopen()
        self.assertEqual(reopened.selection_facts(), new)
        self.assertEqual(reopened.read_selected_bundle(), value)
        self.assertEqual(reopened.lookup('command.save', rev('command.save')), result)
        with self.assertRaisesRegex(journal.PublicationJournalV3Error, 'READ_ONLY'):
            reopened.commit('command.save', rev('command.save'), observed_ms=now(reopened))

    def test_before_cas_cut_reopens_old_selection_and_pending_activating(self):
        owner = self.create(); old = owner.selection_facts(); self.activate(owner)
        owner.close(); reopened = self.reopen()
        self.assertEqual(reopened.selection_facts(), old)
        self.assertEqual(reopened.lookup('command.save')['phase'], 'ACTIVATING')
        with self.assertRaisesRegex(journal.PublicationJournalV3Error, 'READ_ONLY'):
            reopened.select_prepared('command.save', rev('command.save'), observed_ms=now(reopened))

    def test_after_cas_before_selected_cut_holds_and_reopen_rejects_unwitnessed_selector(self):
        owner = self.create(); self.activate(owner)
        actual = owner._store.select
        def lost(intent):
            actual(intent)
            raise OSError('injected lost result after real CAS')
        with mock.patch.object(owner._store, 'select', side_effect=lost):
            with self.assertRaises(journal.PublicationJournalV3Error) as raised:
                owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        self.assertIs(raised.exception.cleanup_owner, owner)
        self.assertTrue(raised.exception.outcome_unknown)
        owner.close()
        with self.assertRaises(journal.PublicationJournalV3Error): self.reopen()

    def test_selected_before_adoption_cut_reopens_new_selection_without_committed_claim(self):
        owner = self.create(); value = self.activate(owner)
        owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        owner.close(); reopened = self.reopen()
        self.assertEqual(reopened.read_selected_bundle(), value)
        record = reopened.lookup('command.save')
        self.assertEqual(record['phase'], 'SELECTED'); self.assertIs(record['public_ack'], False)

    def test_same_byte_new_file_id_selector_substitution_rejected_after_normal_cas(self):
        owner = self.create(); self.activate(owner)
        owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        path = owner._files.root / 'active.json'; raw = path.read_bytes(); owner.close()
        self.assertEqual(path.parent.parent, self.base)
        path.unlink(); path.write_bytes(raw)
        with self.assertRaises(journal.PublicationJournalV3Error): self.reopen()

    def test_selected_content_substitution_rejected_by_actual_native_read(self):
        owner = self.create(); self.activate(owner)
        owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        row = owner.selection_facts()['selector']['descriptor']['files'][codec.SCENE_PATH]
        path = owner._files.root / row['name']; owner.close()
        self.assertEqual(path.parent.parent, self.base); path.write_bytes(b'tampered!')
        with self.assertRaises(journal.PublicationJournalV3Error): self.reopen()

    def test_failed_unused_prepare_cleanup_retains_outer_owner_and_interrupt(self):
        owner = self.create(); value = self.capture(owner)
        cause = journal.store_model.ProtectedBundleError('cleanup', outcome_unknown=True, cleanup_owner=owner._store)
        with mock.patch.object(state, 'reduce_event', side_effect=KeyboardInterrupt), \
             mock.patch.object(owner._store, 'cancel_unused_prepare', side_effect=cause):
            with self.assertRaises(KeyboardInterrupt) as raised:
                owner.prepare('command.save', rev('command.save'), value, observed_ms=now(owner))
        self.assertIs(raised.exception.cleanup_owner, owner)
        with self.assertRaisesRegex(journal.PublicationJournalV3Error, 'JOURNAL_HELD'): owner.snapshot()

    def test_native_close_failure_retains_owner_for_exact_retry(self):
        owner = self.create(); resource = owner._log
        with mock.patch.object(resource, 'close', side_effect=OSError('injected native close failure')):
            with self.assertRaises(journal.PublicationJournalV3Error) as raised: owner.close()
        self.assertIs(raised.exception.cleanup_owner, owner)
        self.assertIs(owner._log, resource); self.assertIsNotNone(owner._store)
        owner.close()
        self.assertIsNone(owner._log); self.assertIsNone(owner._store)

    def test_capture_and_readback_reject_boolean_integer_alias_without_native_append(self):
        owner = self.create(); self.activate(owner)
        owner.select_prepared('command.save', rev('command.save'), observed_ms=now(owner))
        self.adopt(owner)
        events = [parse_json(raw) for raw in owner._state.events]
        mutations = [(1, ('editor_generation',)), (2, ('capture', 'generation_before')),
                     (6, ('current', 'editor_generation')), (8, ('adoption', 'generation_before')),
                     (8, ('adoption', 'history_boundary'))]
        for index, path in mutations:
            with self.subTest(index=index, path=path):
                changed = copy.deepcopy(events); item = changed[index]
                for key in path[:-1]: item = item[key]
                item[path[-1]] = 1 if type(item[path[-1]]) is bool else True
                with self.assertRaises(state.PublicationError): state.replay(changed)


if __name__ == '__main__': unittest.main()
