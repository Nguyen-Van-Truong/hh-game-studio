"""Live file-preview boundaries with inert owners; no Blender or native storage."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import test_native_preview as ui_fixture
import test_client_preview as value_fixture
import test_client_writer_publication as client_fixture
import test_publication_deadline as deadline_fixture
from studio.host.blender import client_preview as preview
from studio.host.blender import publication_state as model
from studio.host.blender import deadline
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes, parse_json, Status, ValidationError


def advisory(command, before):
    result = value_fixture.response(command, before)
    result.update(affected_files=[command['payload']['slot']+'.blend'],
        undo_policy='immutable-private-copy-no-file-undo',
        value_policy='native-preflight-only; artifact-hashes-require-publication')
    return result


def envelope(request, profile, storage_id, before):
    command = model.preparation_command(request, {'publication_profile': profile})
    return {'schema': 'HH-BLENDER-PUBLICATION-PREVIEW-1', 'command_id': request['command_id'],
        'request_sha256': model.sha(canonical_bytes(request)), 'profile': profile,
        'storage_id': storage_id, 'native_command': command,
        'native_preview': advisory(command, before),
        'no_effect': True, 'apply_id_reserved': False, 'public_ack': False}


class NativeFilePreviewTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.owner = ui_fixture.fake_ui()
        self.owner._owned_root = self.root
        self.owner._export_preflight = Mock(return_value={'profile': 'inert'})

    def command(self, slot='checkpoint'):
        return dict(ui_fixture.command(), operation='export.prepare' if slot=='export' else 'checkpoint.save',
                    payload={'slot': slot})

    def test_each_fixed_slot_observed_without_file_operator_or_history_mutation(self):
        for slot in ('fixture', 'checkpoint', 'export'):
            value = self.command(slot)
            old = copy.deepcopy((self.owner._commands, self.owner._history, self.owner._baseline))
            result = self.owner._preview(value)
            self.assertEqual(result, advisory(value, ui_fixture.BEFORE))
            self.assertEqual(list(self.root.iterdir()), [])
            self.assertEqual((self.owner._commands, self.owner._history, self.owner._baseline), old)
        self.assertEqual(self.owner._export_preflight.call_count, 3)
        self.assertEqual(self.owner.bpy.ops.mock_calls, [])
        self.owner._mode.assert_not_called()

    def test_existing_final_or_stage_slot_rejected_before_any_operator(self):
        for name in ('checkpoint.blend', 'stage-checkpoint.blend'):
            path = self.root/name
            path.write_bytes(b'original')
            with self.assertRaisesRegex(ui_fixture.q.c.Rejected, 'SAVE_SLOT_EXISTS'):
                self.owner._preview(self.command())
            self.assertEqual(path.read_bytes(), b'original')
            path.unlink()
        self.assertEqual(self.owner.bpy.ops.mock_calls, [])

    def test_export_profile_rejects_before_slot_or_file_access(self):
        self.owner._export_preflight.side_effect = ui_fixture.q.c.Rejected('UNSUPPORTED_PROFILE')
        self.owner._save_preflight = Mock(side_effect=AssertionError('must not inspect slots'))
        with self.assertRaisesRegex(ui_fixture.q.c.Rejected, 'UNSUPPORTED_PROFILE'):
            self.owner._preview(self.command())
        self.owner._save_preflight.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_save_root_fails_closed_without_effect(self):
        self.owner._owned_root = None
        with self.assertRaisesRegex(ui_fixture.q.c.Rejected, 'NO_OWNED_SAVE_ROOT'):
            self.owner._preview(self.command())
        self.assertFalse(self.owner._held)


class PublicationPreviewOwnerTests(unittest.TestCase):
    def setUp(self):
        self.clock = deadline_fixture.Clock()
        self.enterContext(patch.object(deadline.time, 'time', lambda: self.clock.wall))
        self.enterContext(patch.object(deadline.time, 'monotonic', lambda: self.clock.mono))
        self.owner = deadline_fixture.MemoryPublication(self.clock)
        self.owner.storage_id = 'b'*32
        self.owner.host.preview = Mock(return_value={'inert-native-response': True})
        self.guard = Mock()

    def call(self, **options):
        return self.owner.preview(self.owner.request, self.owner.lease,
            **dict(deadline_ms=1001000, phase_guard=self.guard, **options))

    def test_each_profile_binds_exact_preparation_and_deadline_without_intent(self):
        for profile, slot in [('scene.save','fixture'), ('checkpoint.save','checkpoint'), ('export.publish','export')]:
            self.owner._state['config']['publication_profile'] = profile
            old = copy.deepcopy(self.owner._state)
            result = self.call()
            command = self.owner.host.preview.call_args.args[0]
            self.assertEqual(command, model.preparation_command(self.owner.request, old['config']))
            self.assertEqual(command['payload'], {'slot': slot})
            self.assertEqual(self.owner.host.preview.call_args.kwargs,
                dict(lease={'fencing_epoch':1, 'expires_ms':1005000}, deadline_ms=1001000, ttl_ms=5000))
            self.assertEqual(result['request_sha256'], model.sha(canonical_bytes(self.owner.request)))
            self.assertEqual(result['native_command'], command)
            self.assertEqual(self.owner._state, old)
            self.assertTrue(result['no_effect']); self.assertFalse(result['apply_id_reserved'])
            self.assertFalse(self.owner.writes)
            self.assertFalse(any(item.startswith(('append:', 'export:')) for item in self.owner.trace))

    def test_capacity_and_namespace_rejections_do_not_call_native_or_poison(self):
        self.owner._state['phase'] = 'TERMINAL'
        with self.assertRaisesRegex(model.PublicationError, 'ONE_BUNDLE_CAPACITY'): self.call()
        self.owner._state['phase'] = 'EMPTY'
        self.owner.files.root.iterdir = lambda: []
        with self.assertRaisesRegex(model.PublicationError, 'INITIAL_NAMESPACE'): self.call()
        self.owner.host.preview.assert_not_called()
        self.assertFalse(self.owner._held)

    def test_expiry_during_namespace_inspection_prevents_native_dispatch(self):
        self.owner.hooks['namespace'] = self.clock.expire
        with self.assertRaises(deadline.DeadlineError): self.call()
        self.owner.host.preview.assert_not_called()
        self.assertEqual(self.owner._state['phase'], 'EMPTY')

    def test_stop_revoke_and_expiry_during_native_preview_prevent_delivery(self):
        def stopped(*args, **kwargs):
            self.owner.request_stop(); return {}
        self.owner.host.preview.side_effect = stopped
        with self.assertRaisesRegex(model.PublicationError, 'READONLY_OR_HELD'): self.call()
        self.assertEqual(self.owner._state['phase'], 'EMPTY')
        self.assertFalse(self.owner._held)

    def test_guard_is_rechecked_after_native_preview(self):
        def revoke(*args, **kwargs):
            self.guard.side_effect = SafetyViolation('REVOKED'); return {}
        self.owner.host.preview.side_effect = revoke
        with self.assertRaisesRegex(SafetyViolation, 'REVOKED'): self.call()
        self.assertEqual(self.owner._state['phase'], 'EMPTY')


class PublicationPreviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.before = value_fixture.observed([value_fixture.box()])
        self.storage_id = 'd'*32

    def fixture(self, operation='export.publish'):
        request = value_fixture.request(self.before, operation)
        private = {'schema': model.SCHEMA, 'command_id': value_fixture.PRIVATE_ID,
            'expected_revision': request.expected_revision, 'expected_context': request.payload['expected_context']}
        command = private if operation=='export.publish' else {
            'schema':model.queue.SCHEMA, 'command_id':private['command_id'], 'operation':'checkpoint.save',
            'expected_revision':private['expected_revision'], 'expected_context':private['expected_context'],
            'payload':{'slot':'fixture' if operation=='scene.save' else 'checkpoint'}}
        return request, command, envelope(private, operation, self.storage_id, self.before)

    def normalize(self, request, command, response):
        return preview.normalize_publication_preview(request, command, response,
            source_sha256=value_fixture.SOURCE, generation=value_fixture.GENERATION, storage_id=self.storage_id)

    def test_three_profiles_report_only_planned_files_and_never_future_hashes(self):
        for operation in sorted(model.PROFILES):
            result = self.normalize(*self.fixture(operation))
            self.assertEqual(result['operation'], operation)
            self.assertEqual(result['affected_files'], ['checkpoint.blend','scene.glb','manifest.json','active.json'])
            self.assertIsNone(result['requested_diff']['artifact_hashes'])
            self.assertNotIn('after_revision', result)
            self.assertTrue(result['no_effect']); self.assertFalse(result['authority_granted'])

    def test_foreign_owner_profile_request_or_preparation_is_rejected(self):
        for key, value in [('storage_id','e'*32), ('profile','scene.save'), ('command_id','foreign'),
                           ('request_sha256','0'*64), ('no_effect',False), ('apply_id_reserved',True),
                           ('public_ack',True), ('native_command',{})]:
            request, command, response = self.fixture(); response[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError): self.normalize(request, command, response)

    def test_native_digest_paths_effect_flags_and_precondition_are_bound(self):
        for key, value in [('command_digest','sha256:'+'0'*64), ('affected_files',['foreign.blend']),
                           ('requested_changes',{'slot':'checkpoint'}), ('no_effect',False),
                           ('apply_id_reserved',True), ('scene_state_durable',True), ('history_target',{}),
                           ('before',value_fixture.observed()), ('extra','unknown')]:
            request, command, response = self.fixture(); response['native_preview'][key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError): self.normalize(request, command, response)


class PublicFilePreviewTests(unittest.TestCase):
    profile = 'export.publish'
    for _name in ('_revision','_row','acquire','check_lease','execute','body','submit','lookup','stop',
                  'publish','export_request'):
        locals()[_name] = getattr(client_fixture.PublicationClientTests, _name)
    del _name

    def setUp(self):
        client_fixture.PublicationClientTests.setUp(self)
        self.assertEqual(self.submit().status, Status.COMMITTED)
        self.events.clear(); self.host.execute.reset_mock()
        def preflight(request, lease, *, deadline_ms, phase_guard):
            self.assertIs(lease, self.current_lease); phase_guard()
            return envelope(request, self.profile, self.publisher.storage_id, self.scene)
        self.publisher.preview = Mock(side_effect=preflight)

    def test_preview_no_journal_or_effect_reservation_then_same_id_apply_commits_once(self):
        request = self.export_request(); records = copy.deepcopy(self.journal._records)
        result = self.owner.preview(request, **self.kw)
        self.assertEqual(self.owner.preview(request, **self.kw), result)
        self.assertEqual(self.journal._records, records); self.assertEqual(self.events, [])
        self.publisher.publish.assert_not_called(); self.host.execute.assert_not_called()
        self.assertEqual(self.publisher.preview.call_args.kwargs['deadline_ms'], request['deadline_ms'])
        self.assertEqual(self.submit(request).status, Status.COMMITTED)
        self.assertEqual(self.submit(request).status, Status.COMMITTED)
        self.publisher.publish.assert_called_once()

    def test_revoke_after_preview_blocks_observation_without_ledger_intent(self):
        original = self.publisher.preview.side_effect
        def revoked(*args, **kwargs):
            result = original(*args, **kwargs); self.owner.sessions.revoke(self.credential); return result
        self.publisher.preview.side_effect = revoked
        records = copy.deepcopy(self.journal._records)
        with self.assertRaises(SafetyViolation): self.owner.preview(self.export_request(), **self.kw)
        self.assertEqual(self.journal._records, records); self.publisher.publish.assert_not_called()

    def test_native_preview_reject_does_not_poison_and_live_apply_can_continue(self):
        self.publisher.preview.side_effect = model.PublicationError('PUBLICATION_ONE_BUNDLE_CAPACITY')
        with self.assertRaisesRegex(model.PublicationError, 'ONE_BUNDLE_CAPACITY'):
            self.owner.preview(self.export_request(), **self.kw)
        self.assertFalse(self.owner._held); self.assertFalse(self.owner.sessions._write_held)
        self.assertEqual(self.submit(self.export_request()).status, Status.COMMITTED)


class PublicScenePreviewTests(PublicFilePreviewTests):
    profile = 'scene.save'


class PublicCheckpointPreviewTests(PublicFilePreviewTests):
    profile = 'checkpoint.save'


if __name__ == '__main__': unittest.main()
