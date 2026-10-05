"""Inert receipt/readback negatives; no native engine or acceptance claim."""
import copy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.jobs.native_dispatch import NativeOwnerDispatcher, NativeDispatchError
from studio.protocol.core import Request, Response, Status, canonical_bytes


def sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class GodotReadbackTests(unittest.TestCase):
    def fixture(self, operation='scene.node.update'):
        self.identity = {'session_id': 'editor.original', 'pid': 100}
        self.old_identity = copy.deepcopy(self.identity)
        self.selection = {'generation': 1, 'identity': 'sha256:' + '1' * 64}
        self.files = {'scene': {'sha256': '2' * 64, 'size_bytes': 1}}
        self.selected = {'selector': {'selection': self.selection},
                         'selector_version': {'file_id': '3' * 32}}
        self.manifest = {'files': self.files, 'project_revision': 'sha256:' + '5' * 64}
        self.observed = {'revision': 'sha256:' + '4' * 64,
            'project_revision': 'sha256:' + '5' * 64, 'generation': 1,
            'editor_session_id': 'editor.original', 'root_instance_id': '123',
            'selected_files': self.files, 'history_id': 1, 'can_undo': True, 'can_redo': False}
        self.request = Request('command.one', 'project.fixture', operation, 'lease.one', 1,
            'sha256:' + '6' * 64, {'stable_id': 'root'}, {}, 'sha256:' + sha({}), 30_000)
        self.post = {'scene_revision': self.observed['revision'],
            'project_revision': self.observed['project_revision'], 'generation': 1,
            'selection': self.selection, 'effect_scope': 'editor_session',
            'files_saved': False, 'live_state_durable': False, 'journal_receipt_durable': True,
            'history_boundary': False, 'editor_session_id': 'editor.original',
            'history_id': 1, 'can_undo': True, 'can_redo': False}
        self.receipt = {'command_id': self.request.command_id, 'digest': self.request.digest,
            'operation': operation, 'status': 'COMMITTED', 'selection': self.selection,
            'selector_version': self.selected['selector_version'],
            'schema': 'hh-godot-editor-terminal-5', 'editor': self.identity,
            'root_instance_id': 123,
            'observation': {'semantic_revision': self.observed['revision'], 'history_id_after': 1}}
        self.code = 'GODOT_EDITOR_EDITED'
        self.adoption = None
        if operation in ('scene.save', 'script_text.replace'):
            self.observed.update(generation=2, can_undo=False)
            self.post.update(generation=2, history_boundary=True)
            self.receipt['schema'] = 'hh-godot-publication-terminal-4'
            self.adoption = {'generation_after': 2, 'semantic_revision': self.observed['revision'],
                             'project_revision': self.observed['project_revision'], 'files': self.files}
            if operation == 'scene.save':
                self.code = 'GODOT_MANAGED_SCENE_SAVED'
                self.adoption.update(editor=self.identity, root_instance_id_after=123)
            else:
                self.code = 'GODOT_MANAGED_SCRIPT_REPLACED'
                self.identity = {'session_id': 'editor.successor', 'pid': 200}
                self.observed['editor_session_id'] = 'editor.successor'
                self.adoption.update(old_editor=self.old_identity, new_editor=self.identity, root_after=123)
            self.receipt['adoption_sha256'] = sha(self.adoption)
        self.owner = SimpleNamespace(
            _source_closure_sha256='a' * 64, _editor=SimpleNamespace(identity=self.identity),
            inspect=lambda: copy.deepcopy(self.observed),
            auth_model=SimpleNamespace(EDIT_OPERATIONS={'scene.node.update'}),
            _journal=SimpleNamespace(selection_facts=lambda: copy.deepcopy(self.selected),
                                     read_selected_bundle=lambda: SimpleNamespace(
                                         manifest_bytes=canonical_bytes(self.manifest)),
                                     lookup_adoption=lambda *_: copy.deepcopy(self.adoption)))
        self.binding = SimpleNamespace(owner=self.owner, source_closure_sha256='a' * 64,
                                       editor_identity=canonical_bytes(self.old_identity))

    def check(self):
        NativeOwnerDispatcher._godot_readback(self.binding, self.request,
            Response(Status.COMMITTED, self.code, self.request.command_id, postconditions=self.post),
            self.receipt)

    def test_matching_edit_save_and_fresh_script_successor(self):
        for operation in ('scene.node.update', 'scene.save', 'script_text.replace'):
            with self.subTest(operation=operation):
                self.fixture(operation)
                self.check()

    def test_live_revision_generation_history_and_editor_must_match(self):
        for key, value in (('revision', 'sha256:' + 'b' * 64), ('project_revision', 'stale'),
                           ('generation', 99), ('history_id', 99), ('can_undo', False),
                           ('editor_session_id', 'editor.other'), ('root_instance_id', '999')):
            with self.subTest(key=key):
                self.fixture()
                self.observed[key] = value
                with self.assertRaises(NativeDispatchError): self.check()

    def test_live_selected_files_cannot_drift(self):
        self.fixture()
        self.observed['selected_files'] = {'changed': {}}
        with self.assertRaises(NativeDispatchError): self.check()

    def test_edit_receipt_cannot_claim_saved_files_or_durable_live_state(self):
        for key, value in (('files_saved', True), ('live_state_durable', True),
                           ('journal_receipt_durable', False), ('history_boundary', True),
                           ('effect_scope', 'saved_files')):
            with self.subTest(key=key):
                self.fixture()
                self.post[key] = value
                with self.assertRaises(NativeDispatchError): self.check()

    def test_receipt_bound_to_exact_command_digest_operation(self):
        for key in ('command_id', 'digest', 'operation', 'status'):
            with self.subTest(key=key):
                self.fixture()
                self.receipt[key] = 'different'
                with self.assertRaises(NativeDispatchError): self.check()

    def test_script_successor_requires_original_and_current_identity(self):
        for key in ('old_editor', 'new_editor'):
            with self.subTest(key=key):
                self.fixture('script_text.replace')
                self.adoption[key] = {'session_id': 'editor.forged', 'pid': 999}
                self.receipt['adoption_sha256'] = sha(self.adoption)
                with self.assertRaises(NativeDispatchError): self.check()

    def test_script_adoption_hash_and_root_must_match(self):
        self.fixture('script_text.replace')
        self.adoption['root_after'] = 999
        with self.assertRaises(NativeDispatchError): self.check()
        self.receipt['adoption_sha256'] = sha(self.adoption)
        with self.assertRaises(NativeDispatchError): self.check()

    def test_save_may_not_silently_swap_editor(self):
        self.fixture('scene.save')
        self.owner._editor.identity = {'session_id': 'editor.other', 'pid': 999}
        self.observed['editor_session_id'] = 'editor.other'
        with self.assertRaises(NativeDispatchError): self.check()


if __name__ == '__main__':
    unittest.main()
