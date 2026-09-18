"""Common ledger/publication seam over inert storage and exact typed owners."""
import copy
import threading
import unittest
from unittest.mock import Mock, patch

import test_client_writer_owner as fixture
from studio.host.blender.client_writer_owner import BlenderWriterClientOwner
from studio.host.blender.publication_owner import BlenderPublicationOwner
from studio.host.blender import publication_state as model
from studio.host.blender import client_write_catalog as catalog
from studio.protocol.core import canonical_bytes, parse_json, Status
from studio.host.core.limits import SafetyViolation


class PublicationClientTests(unittest.TestCase):
    profile = 'export.publish'
    for _name in ('_revision', '_row', 'acquire', 'check_lease', 'execute', 'body', 'submit', 'lookup', 'stop'):
        locals()[_name] = getattr(fixture.WriterOwnerTests, _name)
    del _name

    def setUp(self):
        factory = BlenderWriterClientOwner.from_session
        def attach(durable, **kwargs):
            self.publisher = publisher = BlenderPublicationOwner()
            publisher.host = durable.host; publisher.session = durable
            publisher.storage_id = 'b'*32; publisher._readonly = False
            publisher._state = {'phase': 'EMPTY', 'stopped': False, 'config': {
                'schema': model.SCHEMA, 'kind': 'CONFIG', 'generation': durable.host._session,
                'source_sha256': model.sha(canonical_bytes(durable.host._source)),
                'binary_sha256': fixture.host_module.BLENDER_SHA256, 'publication_profile': self.profile}}
            publisher._refresh = Mock(side_effect=lambda: publisher._state)
            publisher.publish = Mock(side_effect=self.publish)
            publisher.read_selected = Mock(side_effect=lambda: (self.manifest, self.artifacts))
            def stop():
                self.events.append('publication-stop'); durable.stop()
                publisher._state['stopped'] = True
                return {'stopped': True, 'public_ack': False}
            publisher.stop = Mock(side_effect=stop)
            return factory(durable, publications={self.profile: publisher}, **kwargs)
        with patch.object(BlenderWriterClientOwner, 'from_session', side_effect=attach):
            fixture.WriterOwnerTests.setUp(self)

    def publish(self, command, lease, *, deadline_ms, phase_guard):
        self.assertIs(lease, self.current_lease)
        self.assertTrue(callable(phase_guard)); phase_guard()
        pending = self.journal._state()[command['command_id']]
        self.assertIsNone(pending['response'])
        self.events.append('publication-effect')
        intent = {'request': command, 'request_sha256': model.sha(canonical_bytes(command))}
        self.artifacts = {'checkpoint.blend': b'inert-blend', 'scene.glb': b'inert-glb'}
        staged = {'command_id': command['command_id'], 'request_sha256': intent['request_sha256'],
            'manifest': {'sha256': 'c'*64},
            'artifacts': {name: {'sha256': model.sha(data), 'identity': {'size': len(data)}}
                          for name, data in self.artifacts.items()}}
        selector = model.selection(staged)
        receipt = model.response(intent, staged, selector)
        self.publisher._state.update(phase='TERMINAL', intent=intent, staged=staged, selector=selector,
            terminal={'response': receipt, 'selector_version': {'sha256': model.sha(canonical_bytes(selector))}})
        self.manifest = {'snapshot': copy.deepcopy(self.scene['snapshot']),
            'scene_revision': command['expected_revision'], 'generation': self.host._session,
            'source_files': copy.deepcopy(self.host._source)}
        return canonical_bytes(receipt)

    def export_request(self):
        return self.body(command_id='Export/Public', operation=self.profile,
            payload={'expected_context': copy.deepcopy(self.scene['context']), 'arguments': {}})

    def test_export_discovery_requires_exact_owned_publisher_and_registered_lease(self):
        discovered = self.owner.discover({'project_id': 'blender.test'}, **self.kw)
        self.assertIn(self.profile, {item.operation for item in discovered.capabilities})
        self.publisher.host = object()
        self.assertEqual(self.submit(self.export_request()).code, 'BLENDER_PUBLICATION_BINDING')
        self.publisher.publish.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_public_intent_precedes_publication_and_private_terminal_binds_common_receipt(self):
        request = self.export_request(); result = self.submit(request)
        self.assertEqual(result.status, Status.COMMITTED)
        self.assertEqual(result.code, 'BLENDER_CLIENT_PUBLICATION')
        self.assertEqual(self.events, ['INTENT', 'publication-effect', 'TERMINAL'])
        self.assertTrue(result.postconditions['durable_publication'])
        self.assertFalse(result.postconditions['public_ack']); self.assertFalse(result.postconditions['scene_state_durable'])
        publication = result.postconditions['publication']
        self.assertEqual(result.result_hash, fixture.module.digest(canonical_bytes(publication)))
        self.assertEqual(self.publisher.publish.call_args.kwargs['deadline_ms'], request['deadline_ms'])
        self.assertEqual(publication['receipt']['command_id'], self.publisher.publish.call_args.args[0]['command_id'])
        self.assertNotEqual(publication['receipt']['command_id'], request['command_id'])
        self.host.execute.assert_not_called()
        self.assertEqual(self.lookup(request['command_id']), result)

    def test_publication_retry_after_expired_original_deadline_has_no_new_native_dispatch(self):
        request = self.export_request(); result = self.submit(request)
        self.assertEqual(result.status, Status.COMMITTED)
        retry = dict(request, deadline_ms=1, fencing_epoch=999, lease_id='expired')
        self.assertEqual(self.submit(retry), result)
        self.assertEqual(self.publisher.publish.call_count, 1)

    def test_unknown_publication_holds_and_never_replays_effect(self):
        self.publisher.publish.side_effect = model.PublicationError('PUBLICATION_OUTCOME_UNKNOWN', outcome_unknown=True)
        request = self.export_request(); result = self.submit(request)
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertTrue(self.owner._held); self.assertTrue(self.owner.sessions._write_held)
        self.assertEqual(self.submit(request), result); self.assertEqual(self.publisher.publish.call_count, 1)

    def test_known_pre_effect_publication_rejection_keeps_live_owner_usable(self):
        self.publisher.publish.side_effect = model.PublicationError('PUBLICATION_ONE_BUNDLE_CAPACITY')
        result = self.submit(self.export_request())
        self.assertEqual(result.status, Status.REJECTED)
        self.assertEqual(result.code, 'PUBLICATION_ONE_BUNDLE_CAPACITY')
        self.assertFalse(self.owner._held); self.assertFalse(self.owner.sessions._write_held)
        self.assertEqual(self.lookup('Export/Public'), result)
        self.assertEqual(self.submit().status, Status.COMMITTED)

    def test_foreign_artifact_readback_cannot_create_public_committed_receipt(self):
        def tampered(*args, **kwargs):
            wire = self.publish(*args, **kwargs); self.artifacts['scene.glb'] = b'tampered'; return wire
        self.publisher.publish.side_effect = tampered
        result = self.submit(self.export_request())
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertEqual(result.code, 'BLENDER_PUBLICATION_ARTIFACT_BINDING'); self.assertTrue(self.owner._held)

    def test_revoked_before_publication_phase_aborts_and_revoked_after_commit_denies_delivery(self):
        def revoked(*args, **kwargs):
            self.owner.sessions.revoke(self.credential); kwargs['phase_guard']()
            raise AssertionError('unreachable')
        self.publisher.publish.side_effect = revoked
        result = self.submit(self.export_request())
        self.assertEqual(result.status, Status.UNKNOWN); self.assertNotIn('publication', result.postconditions)
        self.assertNotIn('publication-effect', self.events)

    def test_revoke_after_selected_bytes_keeps_true_terminal_but_denies_observation(self):
        def revoked(*args, **kwargs):
            wire = self.publish(*args, **kwargs); self.owner.sessions.revoke(self.credential); return wire
        self.publisher.publish.side_effect = revoked
        result = self.submit(self.export_request())
        self.assertEqual(result.status, Status.UNKNOWN); self.assertNotIn('publication', result.postconditions)
        terminal, = self.journal._state().values()
        self.assertEqual(parse_json(terminal['response'])['code'], 'BLENDER_CLIENT_PUBLICATION')

    def test_stop_delegates_to_exact_publication_owner_so_export_job_is_canceled(self):
        result = self.stop()
        self.assertEqual(result.status, Status.COMMITTED)
        self.publisher.stop.assert_called_once_with()
        self.assertEqual(self.events, ['publication-stop', 'native-stop', 'journal-stop'])

    def test_common_terminal_loss_keeps_existing_publication_and_avoids_second_publish(self):
        def lost(*args, **kwargs):
            wire = self.publish(*args, **kwargs); self.journal.failure = 'after'; return wire
        self.publisher.publish.side_effect = lost
        request = self.export_request(); result = self.submit(request)
        self.assertEqual(result.code, 'BLENDER_LEDGER_TERMINAL_UNKNOWN')
        self.journal.failure = None
        history = self.lookup(request['command_id'])
        self.assertEqual(history.status, Status.COMMITTED)
        self.assertEqual(self.submit(request), history); self.assertEqual(self.publisher.publish.call_count, 1)


class SceneSaveClientTests(PublicationClientTests):
    profile = 'scene.save'


class CheckpointSaveClientTests(PublicationClientTests):
    profile = 'checkpoint.save'


if __name__ == '__main__': unittest.main()
