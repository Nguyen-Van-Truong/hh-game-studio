"""Registered owner and real socket checks over explicitly inert native data."""
import copy
import http.client
import threading
import unittest
from unittest.mock import Mock, patch

import test_client_writer_owner as fixture
from studio.host.blender import client_preview as preview
from studio.host.blender.client_writer_transport import BlenderWriterClientTransport
from studio.host.blender.client_transport import BlenderClientTransport
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes, parse_json, ValidationError, Status


class PreviewOwnerTests(unittest.TestCase):
    # Reuse the inert exact-owner setup, without inheriting/rerunning its tests.
    for _name in ('setUp', '_revision', '_row', 'acquire', 'check_lease', 'execute',
                  'body', 'submit', 'lookup', 'stop'):
        locals()[_name] = getattr(fixture.WriterOwnerTests, _name)
    del _name

    def native_preview(self, command, **kwargs):
        self.assertEqual(len(self.journal._records), 1)
        self.assertEqual(self.owner.sessions._write_active['phase'], 'PREPARED')
        return {'schema': preview.PREVIEW_SCHEMA, 'command_id': command['command_id'],
            'command_digest': fixture.module.queue.c.digest(command), 'operation': command['operation'],
            'before': copy.deepcopy(self.scene), 'requested_changes': command['payload'],
            'history_target': None, 'affected_files': [], 'undo_policy': preview.UNDO_POLICY,
            'value_policy': preview.VALUE_POLICY, 'no_effect': True, 'apply_id_reserved': False,
            'public_ack': False, 'scene_state_durable': False}

    def prepare(self):
        self.host.preview = Mock(side_effect=self.native_preview)
        return self.body()

    def test_preview_no_intent_no_effect_and_same_request_applies_exactly_once(self):
        body = self.prepare(); before = copy.deepcopy(self.scene)
        result = self.owner.preview(body, **self.kw)
        self.assertEqual(result['schema'], 'HH-BLENDER-CLIENT-PREVIEW-1')
        self.assertEqual(result['command_id'], body['command_id'])
        self.assertEqual(result['before'], before)
        self.assertTrue(result['no_effect']); self.assertFalse(result['apply_id_reserved'])
        self.assertFalse(result['authority_granted']); self.assertNotIn('after_revision', result)
        self.assertEqual(self.scene, before); self.assertEqual(len(self.journal._records), 1)
        self.assertIsNone(self.owner.sessions._write_active)
        self.host.execute.assert_not_called()
        options = self.host.preview.call_args.kwargs
        self.assertEqual(options['deadline_ms'], body['deadline_ms'])
        self.assertEqual(options['lease'], {'fencing_epoch': self.current_lease.fencing_epoch,
                                            'expires_ms': self.current_lease.expires_ms})
        actual = self.submit(body)
        self.assertEqual(actual.status, Status.COMMITTED)
        changes = actual.postconditions['actual_diff']
        self.assertEqual(changes['objects']['added'], self.scene['snapshot']['objects'])
        self.assertEqual(self.submit(body), actual); self.assertEqual(self.host.execute.call_count, 1)

    def test_changed_request_still_revalidated_after_preview(self):
        body = self.prepare(); self.owner.preview(body, **self.kw)
        invalid = dict(body, expected_revision='sha256:'+'0'*64)
        self.assertEqual(self.submit(invalid).status, Status.REJECTED)
        self.host.execute.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_preview_invalid_lease_deadline_revision_and_read_operation_never_dispatch(self):
        body = self.prepare()
        for changes in ({'deadline_ms': 1}, {'fencing_epoch': 999},
                        {'expected_revision': 'sha256:'+'0'*64}, {'lease_id': 'write.forged'}):
            with self.subTest(changes=changes), self.assertRaises((SafetyViolation, ValidationError)):
                self.owner.preview(self.body(**changes), **self.kw)
        self.host.preview.assert_not_called(); self.assertEqual(len(self.journal._records), 1)

    def test_preview_revoke_and_stop_during_native_inspection_deny_delivery(self):
        body = self.prepare()
        def revoked(command, **kwargs):
            result = self.native_preview(command, **kwargs)
            self.owner.sessions.revoke(self.credential)
            return result
        self.host.preview.side_effect = revoked
        with self.assertRaises(SafetyViolation): self.owner.preview(body, **self.kw)
        self.assertIsNone(self.owner.sessions._write_active)
        self.assertEqual(len(self.journal._records), 1); self.host.execute.assert_not_called()

    def test_preview_stop_during_native_inspection_does_not_persist_or_return_observation(self):
        body = self.prepare()
        def stopped(command, **kwargs):
            result = self.native_preview(command, **kwargs); self.stop(); return result
        self.host.preview.side_effect = stopped
        with self.assertRaises(SafetyViolation): self.owner.preview(body, **self.kw)
        self.assertIsNone(self.owner.sessions._write_active)
        self.assertEqual(len(self.journal._records), 1); self.host.execute.assert_not_called()

    def test_unbound_native_preview_rejected_without_consuming_apply_id(self):
        body = self.prepare()
        def wrong(command, **kwargs):
            result = self.native_preview(command, **kwargs); result['command_digest'] = 'sha256:'+'0'*64
            return result
        self.host.preview.side_effect = wrong
        with self.assertRaises(ValidationError): self.owner.preview(body, **self.kw)
        self.assertEqual(len(self.journal._records), 1)
        self.assertEqual(self.submit(body).status, Status.COMMITTED)

    def test_preview_secret_added_after_owner_return_cannot_silently_rewrite_wire(self):
        body = self.prepare(); result = self.owner.preview(body, **self.kw)
        # The authenticated issuer records newly issued secret bytes. Use its
        # same redactor directly to model the late boundary without RNG tricks.
        with patch.object(fixture.session_module.BlenderClientSession, 'encode_output',
                          return_value=canonical_bytes(dict(result, command_id='[REDACTED]'))):
            with self.assertRaisesRegex(SafetyViolation, 'SENSITIVE_OBSERVATION'):
                self.owner.sessions.encode_output(result)

    def test_preview_busy_rejects_without_blocking_stop(self):
        body = self.prepare(); self.owner._work.acquire()
        try:
            with self.assertRaisesRegex(SafetyViolation, 'CLIENT_BUSY'):
                self.owner.preview(body, **self.kw)
            self.assertEqual(self.stop().status, Status.COMMITTED)
        finally: self.owner._work.release()
        self.host.preview.assert_not_called()

    def test_writer_socket_preview_and_readonly_route_remains_unavailable(self):
        body = self.prepare()
        for cls, expected in ((BlenderWriterClientTransport, 200), (BlenderClientTransport, 400)):
            server = cls(self.owner).start()
            try:
                connection = http.client.HTTPConnection('127.0.0.1', server.port, timeout=2)
                connection.request('POST', '/v1/preview', canonical_bytes(body),
                    {'Content-Type': 'application/json', 'Authorization': self.auth,
                     'X-HH-Catalog': self.kw['catalog_digest']})
                reply = connection.getresponse(); data = parse_json(reply.read())
                self.assertEqual(reply.status, expected)
                if expected == 200: self.assertTrue(data['no_effect'])
                else: self.assertEqual(data['code'], 'UNSUPPORTED_ROUTE')
                connection.close()
            finally: server.close()
        self.assertEqual(len(self.journal._records), 1); self.host.execute.assert_not_called()


if __name__ == '__main__': unittest.main()
