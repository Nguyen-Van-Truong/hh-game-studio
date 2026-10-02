"""Private candidate admission over real grants; native effects remain inert.

These tests make no native authoring, UndoRedo, save, or AUTH acceptance claim.
Only the existing publication owner admission and session lifecycle execute.
"""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location(
    'o2_authoring_bridge_owner_tests', STUDIO / 'godot-addon/publication_owner.py')
owner_model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = owner_model
SPEC.loader.exec_module(owner_model)
contract = owner_model._load('contract')
auth = owner_model._load('publication_session')

from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, Status, ValidationError, canonical_bytes


class AuthoringUpdateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-authoring-bridge-test-')
        self.addCleanup(self.temporary.cleanup)
        self.bridge_model = owner_model._load('authoring_update_bridge')
        self.owner = object.__new__(owner_model.GodotPublicationOwner)
        value = self.owner
        value.project_id = 'project.fixture'
        value.contract, value.auth_model = contract, auth
        value._lock, value._work = threading.RLock(), threading.Lock()
        value._held = value._closed = False
        value._jobs, value._leases, value._read_leases = {}, {}, {}
        value._same_release = Mock()
        value._editor = SimpleNamespace(_intents={})
        value.editor_model = SimpleNamespace(MAX_EFFECTS=16)
        value._validator = Mock()
        value._validator.snapshot.return_value = {'attempts': []}
        value.validation_model = SimpleNamespace(MAX_RUNS=10)
        value.sessions = auth.PublicationSession(
            value.project_id, Path(self.temporary.name), contract.CATALOG_DIGEST)
        self.addCleanup(value.sessions.halt)
        self.credential = value.sessions.issue()
        self.arguments = {'authorization': 'Bearer ' + self.credential.bearer,
                          'catalog_digest': contract.CATALOG_DIGEST}
        self.grant = value.sessions.authorize(
            self.arguments['authorization'], 'scene.node.update',
            project_id=value.project_id, catalog_digest=contract.CATALOG_DIGEST)
        self.lease = value.sessions.lease(self.grant, ttl_ms=60_000)
        value._leases[self.grant.session_id] = self.lease
        self.snapshot = {
            'generation': 3, 'revision': 'sha256:' + '1' * 64,
            'project_revision': 'sha256:' + '2' * 64,
            'can_undo': False, 'can_redo': False,
            'state': {'nodes': [
                {'stable_id': 'root', 'parent_id': None, 'node_type': 'Node3D',
                 'name': 'Fixture', 'position': [0, 0, 0],
                 'rotation_degrees': [0, 0, 0], 'scale': [1, 1, 1]},
                {'stable_id': 'box', 'parent_id': 'root', 'node_type': 'MeshInstance3D',
                 'name': 'Box', 'position': [1, 0, 0], 'rotation_degrees': [0, 0, 0],
                 'scale': [1, 1, 1], 'box_size': [1, 1, 1]},
            ]},
            'working_files': {name: {'sha256': '3' * 64} for name in
                              (contract.SCENE_PATH, contract.SCRIPT_PATH)},
        }
        value.inspect = Mock(side_effect=lambda: copy.deepcopy(self.snapshot))
        self.replies = {}

        def inert_edit(request, grant, lease, before, validated, record):
            # Admission is real. This replaces the complete native effect and
            # durable journal path, so its response expressly grants no ACK.
            self.assertIs(grant, self.grant)
            self.assertIs(lease, self.lease)
            self.assertTrue(value._work.locked())
            self.assertEqual(validated.request_digest, request.digest)
            response = Response(Status.COMMITTED, 'INERT_CANDIDATE_EDIT',
                request.command_id, postconditions={'public_ack': False,
                    'native_effect_exercised': False, 'request_digest': request.digest})
            record.update(status='COMMITTED', code=response.code)
            self.replies[request.command_id] = response
            return response

        value._edit = Mock(side_effect=inert_edit)
        value._save = Mock(side_effect=AssertionError('unexpected native save path'))
        value._reply = Mock(side_effect=lambda command, _record: self.replies[command])

    def request(self, *, command='candidate.update', changes=None, target='box',
                operation='scene.node.update', payload=None, **envelope):
        body = {'expected_generation': self.snapshot['generation'],
                'expected_project_revision': self.snapshot['project_revision']}
        if payload is None:
            payload = {'changes': {'position': [4, 5, 6]} if changes is None else changes}
        body.update(copy.deepcopy(payload))
        values = {'command_id': command, 'project_id': self.owner.project_id,
            'operation': operation, 'lease_id': self.lease.lease_id,
            'fencing_epoch': self.lease.fencing_epoch,
            'expected_revision': self.snapshot['revision'], 'target': {'stable_id': target},
            'payload': body, 'payload_hash': 'sha256:' + hashlib.sha256(canonical_bytes(body)).hexdigest(),
            'deadline_ms': min(self.lease.expires_ms - 1, epoch_ms() + 20_000)}
        values.update(envelope)
        return Request(**values)

    def submit(self, request, **arguments):
        return self.owner.submit_candidate_update(request.as_dict(),
                                                   **(arguments or self.arguments))

    def assert_no_admission(self):
        self.owner._edit.assert_not_called()
        self.owner._save.assert_not_called()
        self.assertEqual(self.owner._jobs, {})
        self.assertFalse(self.owner._work.locked())

    def assert_rejected(self, request, pattern=None, **arguments):
        with self.assertRaises((SafetyViolation, ValidationError)) as caught:
            self.submit(request, **arguments)
        if pattern is not None:
            self.assertRegex(str(caught.exception), pattern)
        self.assert_no_admission()

    def test_new_admission_uses_owned_context_under_work_lock_and_same_digest(self):
        bridge = self.bridge_model.AuthoringUpdateBridge()
        self.owner._authoring_update_bridge = bridge
        original_validate = bridge.validate
        observations = []

        def observe(request, context, validated):
            self.assertTrue(self.owner._work.locked())
            self.assertIs(type(context), contract.ValidationContext)
            self.assertEqual((context.revision, context.project_revision, context.generation),
                (self.snapshot['revision'], self.snapshot['project_revision'], 3))
            self.assertEqual((context.lease_id, context.fencing_epoch, context.lease_expires_ms),
                (self.lease.lease_id, self.lease.fencing_epoch, self.lease.expires_ms))
            self.assertEqual(context.nodes[1].node_type, 'MeshInstance3D')
            self.assertEqual(context.file_hashes, tuple((name, '3' * 64) for name in
                (contract.SCENE_PATH, contract.SCRIPT_PATH)))
            self.assertFalse(context.stopped)
            self.assertLessEqual(context.now_ms, epoch_ms())
            observations.append((request.digest, validated.projection))
            return original_validate(request, context, validated)

        request = self.request(changes={'position': [4, 5, 6], 'scale': [2, 3, 4]})
        before = canonical_bytes(request.as_dict())
        with patch.object(bridge, 'validate', side_effect=observe):
            result = self.submit(request)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0][0], request.digest)
        self.assertEqual(observations[0][1]['command_id'], request.command_id)
        self.assertEqual(canonical_bytes(request.as_dict()), before)
        self.assertEqual(self.owner._edit.call_args.args[0].digest, request.digest)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertFalse(self.owner._work.locked())

    def test_bridge_is_lazy_and_reused_for_both_supported_observed_node_types(self):
        for index, target in enumerate(('root', 'box')):
            self.submit(self.request(command=f'candidate.target.{index}', target=target,
                                     changes={'position': [index, 2, 3], 'scale': [1, 2, 3]}))
            if index == 0:
                first = self.owner._authoring_update_bridge
            else:
                self.assertIs(self.owner._authoring_update_bridge, first)
        self.assertEqual(self.owner._edit.call_count, 2)

    def test_exact_retry_skips_stale_context_and_candidate_revalidation(self):
        request = self.request()
        result = self.submit(request)
        self.snapshot['revision'] = 'sha256:' + '4' * 64
        self.owner._leases.clear()
        self.owner.inspect.side_effect = AssertionError('retry inspected current scene')
        bridge = self.owner._authoring_update_bridge
        with patch.object(bridge, 'validate', side_effect=AssertionError('retry revalidated')):
            self.assertEqual(self.submit(request), result)
        self.assertEqual(self.owner._edit.call_count, 1)
        self.owner._reply.assert_called_once()

    def test_retry_still_enforces_command_digest(self):
        original = self.request()
        self.submit(original)
        with self.assertRaisesRegex(SafetyViolation, 'GODOT_COMMAND_CONFLICT'):
            self.submit(self.request(changes={'position': [7, 8, 9]},
                                     deadline_ms=original.deadline_ms))
        self.assertEqual(self.owner._edit.call_count, 1)
        self.owner._reply.assert_not_called()

    def test_retry_still_requires_live_authorization(self):
        request = self.request()
        self.submit(request)
        self.owner.sessions.revoke(self.credential)
        with self.assertRaises(SafetyViolation):
            self.submit(request)
        self.assertEqual(self.owner._edit.call_count, 1)
        self.owner._reply.assert_not_called()

    def test_stale_scene_project_generation_lease_and_deadline_reject_before_edit(self):
        cases = ({'expected_revision': 'sha256:' + '4' * 64},
                 {'payload': {'expected_project_revision': 'sha256:' + '4' * 64,
                              'changes': {'position': [4, 5, 6]}}},
                 {'payload': {'expected_generation': 2, 'changes': {'position': [4, 5, 6]}}},
                 {'lease_id': 'lease.other'}, {'fencing_epoch': self.lease.fencing_epoch + 1},
                 {'deadline_ms': epoch_ms() - 1})
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.assert_rejected(self.request(**arguments))

    def test_copied_lease_with_identical_fields_is_not_registered_authority(self):
        self.owner._leases[self.grant.session_id] = replace(self.lease)
        self.assert_rejected(self.request(), 'GODOT_STALE_LEASE')

    def test_inspect_only_grant_and_wrong_catalog_never_reach_edit(self):
        reader = self.owner.sessions.issue(operations=frozenset({'scene.inspect'}))
        self.assert_rejected(self.request(), authorization='Bearer ' + reader.bearer,
                             catalog_digest=contract.CATALOG_DIGEST)
        self.assert_rejected(self.request(), authorization=self.arguments['authorization'],
                             catalog_digest='sha256:' + '9' * 64)

    def test_stop_and_revocation_before_new_admission_reject(self):
        self.owner.sessions.stop(self.grant)
        self.assert_rejected(self.request())
        self.owner.sessions.revoke(self.credential)
        self.assert_rejected(self.request())

    def test_revocation_during_candidate_validation_is_rechecked_before_edit(self):
        bridge = self.bridge_model.AuthoringUpdateBridge()
        self.owner._authoring_update_bridge = bridge
        original_validate = bridge.validate

        def revoke(request, context, validated):
            result = original_validate(request, context, validated)
            self.owner.sessions.revoke(self.credential)
            return result

        with patch.object(bridge, 'validate', side_effect=revoke):
            self.assert_rejected(self.request())

    def test_unsupported_properties_and_non_update_operation_are_closed(self):
        for changes in ({'name': 'Renamed'}, {'box_size': [2, 2, 2]},
                        {'rotation_degrees': [0, 10, 0]}, {'rotation': [0, 1, 0]},
                        {'visible': False}, {'mesh': {'resource_id': 'mesh.test'}}):
            with self.subTest(changes=changes):
                self.assert_rejected(self.request(changes=changes))
        create = self.request(operation='scene.node.create', target='root', payload={
            'stable_id': 'new.node', 'node_type': 'Node3D', 'name': 'NewNode',
            'position': [0, 0, 0], 'rotation_degrees': [0, 0, 0], 'scale': [1, 1, 1]})
        self.assert_rejected(create, 'GODOT_CANDIDATE_UPDATE_ONLY')

    def test_accepted_scale_limits_remain_stricter_than_candidate_catalog(self):
        for scale in ([0, 1, 1], [-1, 1, 1], [1001, 1, 1]):
            with self.subTest(scale=scale):
                self.assert_rejected(self.request(changes={'scale': scale}),
                                     'GODOT_INVALID_COMPONENT')

    def test_ordinary_submit_does_not_invoke_candidate_gate(self):
        self.owner._authoring_update_bridge = SimpleNamespace(
            validate=Mock(side_effect=AssertionError('ordinary submit used candidate gate')))
        self.owner.submit(self.request(changes={'rotation_degrees': [0, 10, 0]}).as_dict(),
                          **self.arguments)
        self.owner._edit.assert_called_once()
        self.owner._authoring_update_bridge.validate.assert_not_called()

    def test_bridge_rejects_forged_accepted_projection(self):
        bridge = self.bridge_model.AuthoringUpdateBridge()
        request = self.request()
        context = self.owner._context(self.snapshot, self.lease)
        validated = contract.validate_request(request, context)
        projection = validated.projection
        projection['payload']['changes']['position'] = [99, 99, 99]
        forged = replace(validated, _projection=canonical_bytes(projection))
        with self.assertRaisesRegex(self.bridge_model.AuthoringUpdateBridgeError,
                                    'AUTHORING_BRIDGE_PROJECTION_MISMATCH'):
            bridge.validate(request, context, forged)
        self.assert_no_admission()

    def test_bound_catalog_contract_and_bridge_source_drift_reject_before_edit(self):
        original_read = Path.read_bytes
        for name in ('contracts/godot-authoring-schema-v1.json',
                     'godot-addon/authoring_contract.py', 'godot-addon/authoring_update_bridge.py'):
            with self.subTest(source=name):
                self.owner._authoring_update_bridge = self.bridge_model.AuthoringUpdateBridge()
                changed = STUDIO / name

                def changed_read(path):
                    raw = original_read(path)
                    return raw + b'\n ' if path.absolute() == changed.absolute() else raw

                with patch.object(Path, 'read_bytes', changed_read):
                    self.assert_rejected(self.request(), 'AUTHORING_BRIDGE_')


if __name__ == '__main__':
    unittest.main()
