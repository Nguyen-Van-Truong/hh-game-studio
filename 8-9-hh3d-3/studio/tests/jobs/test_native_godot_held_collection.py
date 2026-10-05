"""Held-editor collector regression: real auth/owner, inert OS and queue edges.

This proves the Python collection boundary, not a native save or durable disk.
The M5 native lock scenario supplies those separate observations.
"""
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.jobs import test_native_godot_recovery as fixture
from studio.host.jobs.native_dispatch import NativeDispatchError
from studio.protocol.core import Response, Status, canonical_bytes

editor_module = fixture.owner_module._load('editor_owner')
session_module = fixture.owner_module._load('publication_session')


class HeldCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt07-held-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.fx = fixture.NativeGodotRecoveryTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        self.owner = self.fx.owner
        self.owner.project_id = self.fx.request.project_id
        self.fx.request = replace(self.fx.request, operation='scene.save')
        self.owner.sessions = session_module.PublicationSession(
            self.owner.project_id, self.base, self.fx.binding.catalog_digest)
        self.credential = self.owner.sessions.issue()
        self.authorization = 'Bearer ' + self.credential.bearer
        del self.owner._auth  # Use real publication authorization, not fixture lambda.
        self.fx.grant = self.owner._auth(self.fx.request.as_dict(), 'scene.save',
                                         self.authorization, self.fx.binding.catalog_digest)
        self.editor = object.__new__(editor_module.EditorOwner)
        self.editor._mutex = threading.RLock()
        self.editor._closed = self.editor._held = False
        self.editor._overflow = threading.Event()
        self.editor._source = editor_module._release()
        self.editor._process = SimpleNamespace(poll=Mock(return_value=None))
        self.editor._job = SimpleNamespace(active_count=Mock(return_value=1))
        self.editor._root_identity = SimpleNamespace(volume=1, file_id='root.fixture')
        self.editor._root_handle = object()
        self.editor._api = SimpleNamespace(
            inspect=Mock(return_value=SimpleNamespace(same_file=Mock(return_value=True))),
            check_security=Mock())
        self.editor.directory = self.editor.project = self.base
        self.editor._session, self.editor._pid, self.editor._creation = 'editor.fixture', 1234, '5678'
        self.owner._editor = self.editor
        self.response = Response(Status.UNKNOWN, 'GODOT_PUBLICATION_RECONCILE_REQUIRED',
            self.fx.request.command_id, postconditions={
                'request_digest': self.fx.request.digest, 'public_ack': False,
                'reason': 'owner.effect.uncertain', 'next_action': 'lookup.reconcile'})
        self.raw = canonical_bytes(self.response.as_dict())
        self.owner._journal = SimpleNamespace(lookup_response=Mock(return_value=self.raw))
        self.owner._jobs = {self.fx.request.command_id: {
            'digest': self.fx.request.digest, 'status': 'UNKNOWN', 'code': self.response.code,
            'postconditions': self.response.postconditions,
            'durable_response_sha256': hashlib.sha256(self.raw).hexdigest()}}
        self.binding = self.fx._binding()
        # Fixture constructor uses a fixed authorization; register the real token.
        object.__setattr__(self.binding, 'authorization', self.authorization)
        object.__setattr__(self.binding, 'session_id', self.fx.grant.session_id)
        with __import__('studio.host.jobs.native_dispatch', fromlist=['_BIND'])._BIND:
            fixture._BINDINGS[self.binding] = tuple(
                getattr(self.binding, key) for key in self.binding.__dataclass_fields__)
        self.record = self.fx.queue.broker.record_owner_result = Mock(return_value='recorded')
        self.editor._held = self.owner._held = True
        self.owner.sessions.halt()

    def collect(self, response=None):
        return self.fx.dispatch._collect_godot(object(), self.binding,
                                               self.response if response is None else response)

    def test_old_healthy_identity_reproduces_collection_failure(self):
        # Exactly the old check: .identity refuses the held editor before lookup.
        with patch.object(editor_module.EditorOwner, 'lookup_identity',
                          editor_module.EditorOwner.identity):
            with self.assertRaisesRegex(editor_module.EditorOwnerError, 'HELD_OR_CLOSED'):
                self.collect()
        self.record.assert_not_called()

    def test_authenticated_unknown_collected_and_effect_identity_stays_blocked(self):
        result, actual = self.collect()
        self.assertEqual((result, actual.as_dict()), ('recorded', self.response.as_dict()))
        owner_result = self.record.call_args.args[1]
        self.assertEqual(owner_result.outcome, 'UNKNOWN')
        self.assertEqual(owner_result.receipt_sha256, hashlib.sha256(self.raw).hexdigest())
        with self.assertRaisesRegex(editor_module.EditorOwnerError, 'HELD_OR_CLOSED'):
            self.binding.check()
        with self.assertRaisesRegex(editor_module.EditorOwnerError, 'HELD_OR_CLOSED'):
            self.editor.inspect()

    def test_rotated_credentials_cannot_collect_even_supplied_unknown(self):
        self.owner.sessions.rotate(self.credential)
        with self.assertRaises(Exception):
            self.collect()
        self.record.assert_not_called()

    def test_revoked_credentials_cannot_collect(self):
        self.owner.sessions.revoke(self.credential)
        with self.assertRaises(Exception):
            self.collect()
        self.record.assert_not_called()

    def test_source_and_owner_binding_drift_rejected(self):
        for name, value in (('_source_closure_sha256', 'f' * 64),
                            ('_source_release', ('different',)), ('_journal', object()),
                            ('sessions', object()), ('storage_id', 'different')):
            original = getattr(self.owner, name)
            with self.subTest(name=name):
                setattr(self.owner, name, value)
                with self.assertRaisesRegex(NativeDispatchError, 'OWNER_BINDING_CHANGED'):
                    self.collect()
                setattr(self.owner, name, original)
        self.record.assert_not_called()

    def test_lookup_identity_keeps_process_source_root_security_and_log_checks(self):
        faults = [
            patch.object(self.editor, '_closed', True),
            patch.object(self.editor, '_source', {}),
            patch.object(self.editor._process, 'poll', return_value=1),
            patch.object(self.editor._job, 'active_count', return_value=0),
            patch.object(self.editor._api.inspect.return_value, 'same_file', return_value=False),
            patch.object(self.editor._api, 'check_security', side_effect=ValueError('ACL')),
            patch.object(self.editor, '_creation', 'changed'),
        ]
        for fault in faults:
            with fault, self.assertRaises(Exception):
                self.collect()
        self.editor._overflow.set()
        with self.assertRaisesRegex(editor_module.EditorOwnerError, 'HELD_OR_CLOSED'):
            self.collect()
        self.editor._overflow.clear()
        (self.base / 'stderr.txt').write_bytes(b'ERROR native diagnostic')
        with self.assertRaisesRegex(editor_module.EditorOwnerError, 'NATIVE_DIAGNOSTIC'):
            self.collect()
        self.record.assert_not_called()

    def test_active_phase_cannot_be_collected(self):
        with self.owner._work, self.assertRaisesRegex(NativeDispatchError, 'PHASE_ACTIVE'):
            self.collect()
        self.owner.sessions._active = 'still.running'
        with self.assertRaisesRegex(NativeDispatchError, 'PHASE_ACTIVE'):
            self.collect()
        self.record.assert_not_called()

    def test_response_and_journal_mismatch_cannot_be_collected(self):
        other = Response(Status.UNKNOWN, 'DIFFERENT', self.response.command_id,
                         postconditions=self.response.postconditions)
        with self.assertRaisesRegex(NativeDispatchError, 'LOOKUP_MISMATCH'):
            self.collect(other)
        self.owner._journal.lookup_response.return_value = canonical_bytes(other.as_dict())
        with self.assertRaisesRegex(NativeDispatchError, 'LOOKUP_MISMATCH'):
            self.collect()
        self.record.assert_not_called()

    def test_committed_result_still_requires_healthy_editor_readback(self):
        # No held-state relaxation reaches the COMMITTED readback boundary.
        with self.assertRaisesRegex(editor_module.EditorOwnerError, 'HELD_OR_CLOSED'):
            self.fx.dispatch._godot_readback(self.binding, self.fx.request,
                                            Response(Status.COMMITTED, 'unused', 'unused'), {})
        self.record.assert_not_called()


if __name__ == '__main__':
    unittest.main()
