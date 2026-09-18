"""Replay authority/lifecycle tests. No simulated phase is engine evidence."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import session
from studio.protocol.core import canonical_bytes

CATALOG = 'sha256:' + '1' * 64
DIGEST = 'sha256:' + '2' * 64


def binding():
    return {'run_id': 'run.replay.01', 'command_id': 'command.run.01',
            'runtime_instance_id': 'runtime.01', 'source_closure_sha256': '3' * 64,
            'runtime_snapshot_sha256': '4' * 64, 'trace_sha256': '5' * 64,
            'glb_sha256': '6' * 64, 'generation': 1}


class ReplaySessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_800_000_000_000
        for name in ('studio.host.replay.session.epoch_ms', 'studio.host.core.transport.epoch_ms'):
            mocked = patch(name, side_effect=lambda: self.now)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='hh-replay-session-')
        self.addCleanup(self.temp.cleanup)
        self.owner = self.make_owner()
        self.credential = self.owner.issue()
        self.grant = self.authorize()

    def make_owner(self, **changes):
        fields = dict(catalog_digest=CATALOG, binding=binding(), owner_deadline_ms=self.now + 90_000)
        fields.update(changes)
        return session.ReplaySession('project.replay', Path(self.temp.name), **fields)

    def authorize(self, credential=None, operation='play.start', **changes):
        fields = dict(project_id='project.replay', catalog_digest=CATALOG, binding=binding())
        fields.update(changes)
        return self.owner.authorize('Bearer ' + (credential or self.credential).bearer, operation, **fields)

    def reserve(self, grant=None, **changes):
        fields = dict(command_id='command.start', request_digest=DIGEST, operation='play.start',
                      deadline_ms=self.now + 10_000)
        fields.update(changes)
        return self.owner.reserve(grant or self.grant, **fields)

    def drain(self, permit, known=True):
        self.owner.start_effect(permit)
        self.owner.finish_effect(permit, known=known)

    def rejects(self, code, callback, *args, **kwargs):
        with self.assertRaises(session.SafetyViolation) as caught:
            callback(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_fixture_bearers_and_unregistered_empty_scopes_never_grant_replay(self):
        issuer = session.SessionAuthority('project.replay', Path(self.temp.name), session.TransportLimits())
        for scopes in (frozenset({'fixture.write'}), frozenset()):
            self.rejects('AUTH_REQUIRED', self.authorize, issuer.issue(scopes=scopes))
        credential = self.owner._issuer.issue(scopes=frozenset())
        self.rejects('REPLAY_GRANT_REQUIRED', self.authorize, credential)
        self.assertEqual(self.credential.scopes, frozenset())
        self.assertNotIn(self.credential.bearer, repr(self.credential))

    def test_every_scope_binding_is_exact_and_caller_cannot_expand_operations(self):
        for name, value in binding().items():
            altered = binding()
            altered[name] = value + 1 if type(value) is int else ('7' * 64 if name.endswith('sha256') else value + '.other')
            with self.subTest(name=name):
                self.rejects('REPLAY_GRANT_BINDING', self.authorize, binding=altered)
        for changed in ({'project_id': 'project.other'}, {'catalog_digest': 'sha256:' + '0' * 64}):
            self.rejects('REPLAY_GRANT_BINDING', self.authorize, **changed)
        for operation in ('fixture.set', 'scene.inspect', 'play.mutate', None):
            self.rejects('REPLAY_OPERATION_FORBIDDEN', self.authorize, operation=operation)

    def test_binding_copies_are_detached_and_hash_covers_all_fields(self):
        original = binding()
        owner = self.make_owner(binding=original)
        digest = hashlib.sha256(canonical_bytes(original)).hexdigest()
        original['generation'] = 9
        detached = owner.binding
        detached['run_id'] = 'other'
        self.assertEqual(owner.binding, binding())
        self.assertEqual(owner.binding_sha256, digest)
        self.assertEqual(self.grant.binding_sha256, digest)

    def test_constructor_binding_validation_rejects_unknown_fields_and_scalar_coercions(self):
        cases = [(None, 'REPLAY_BINDING_FIELDS'), ({}, 'REPLAY_BINDING_FIELDS'),
                 ({**binding(), 'extra': True}, 'REPLAY_BINDING_FIELDS')]
        for name, bad, code in (
            ('run_id', '../outside', 'REPLAY_BINDING_ID'),
            ('command_id', 'A', 'REPLAY_BINDING_ID'),
            ('runtime_instance_id', 'r' * 129, 'REPLAY_BINDING_ID'),
            ('trace_sha256', 'A' * 64, 'REPLAY_BINDING_HASH'),
            ('glb_sha256', 'sha256:' + '6' * 64, 'REPLAY_BINDING_HASH'),
            ('generation', True, 'REPLAY_BINDING_GENERATION'),
            ('generation', 0, 'REPLAY_BINDING_GENERATION'),
            ('generation', 2147483648, 'REPLAY_BINDING_GENERATION')):
            cases.append(({**binding(), name: bad}, code))
        for value, code in cases:
            with self.subTest(value=value):
                self.rejects(code, self.make_owner, binding=value)
        for deadline in (True, self.now, self.now + session.MAX_OWNER_MS + 1):
            self.rejects('REPLAY_OWNER_DEADLINE', self.make_owner, owner_deadline_ms=deadline)

    def test_authentication_rejects_missing_wrong_and_non_string_headers(self):
        for value in (None, b'Bearer invalid', '', 'Basic x', 'Bearer ' + 'a' * 43):
            self.rejects('AUTH_REQUIRED', self.owner.authenticate, value)

    def test_operations_are_fixed_nonempty_and_do_not_coerce_sets(self):
        for value in (set(session.OPERATIONS), frozenset(), ('play.start',), frozenset({'fixture.read'})):
            self.rejects('REPLAY_INVALID_GRANT', self.owner.issue, operations=value)
        credential = self.owner.issue(operations=frozenset({'play.inspect', 'control.lookup'}))
        grant = self.authorize(credential, 'play.inspect')
        self.rejects('REPLAY_OPERATION_FORBIDDEN', self.owner.stop, grant)
        self.rejects('REPLAY_OPERATION_FORBIDDEN', self.reserve, grant)
        self.assertFalse(self.owner.status()['stopped'])

    def test_copied_or_field_modified_authority_objects_are_rejected(self):
        self.rejects('REPLAY_GRANT_REQUIRED', self.reserve, replace(self.grant))
        self.rejects('REPLAY_CREDENTIAL_REQUIRED', self.owner.rotate, replace(self.credential))
        self.rejects('REPLAY_CREDENTIAL_REQUIRED', self.owner.revoke, replace(self.credential))
        object.__setattr__(self.grant, 'operations', ('play.start',))
        self.rejects('REPLAY_GRANT_REQUIRED', self.authorize)

    def test_credential_in_place_modification_is_not_authority(self):
        object.__setattr__(self.credential, 'expires_ms', self.now + 120_000)
        self.rejects('REPLAY_CREDENTIAL_CHANGED', self.authorize)
        self.rejects('REPLAY_CREDENTIAL_REQUIRED', self.owner.rotate, self.credential)

    def test_permit_copy_field_edit_and_double_finish_cannot_repeat_effect(self):
        permit = self.reserve()
        self.rejects('REPLAY_PERMIT_REQUIRED', self.owner.start_effect, replace(permit))
        self.drain(permit)
        self.rejects('REPLAY_PERMIT_ALREADY_USED', self.owner.start_effect, permit)
        self.rejects('REPLAY_EFFECT_NOT_STARTED', self.owner.finish_effect, permit, known=True)
        object.__setattr__(permit, 'operation', 'play.capture')
        self.rejects('REPLAY_PERMIT_REQUIRED', self.owner.start_effect, permit)

    def test_launch_phase_completion_does_not_block_running_runtime_inspection(self):
        launch = self.reserve()
        self.drain(launch)
        # Runtime process ownership remains with the separate owner. These
        # bounded observation phases need no second launch or grant extension.
        for operation in ('play.inspect', 'play.capture'):
            permit = self.reserve(command_id='command.' + operation, operation=operation)
            self.drain(permit)
        self.assertEqual(self.owner.status()['commands_used'], 3)
        self.assertFalse(self.owner.status()['draining'])

    def test_one_bounded_command_slot_and_controls_remain_independent(self):
        permit = self.reserve()
        self.rejects('REPLAY_WORK_BUSY', self.reserve, command_id='command.inspect', operation='play.inspect')
        self.assertIs(self.authorize(operation='control.lookup'), self.grant)
        self.owner.cancel_reserved(permit)
        self.assertEqual(self.owner.permit_status(permit), 'CANCELED')
        self.drain(self.reserve(command_id='command.inspect', operation='play.inspect'))

    def test_exact_command_tombstones_survive_rotation_and_do_not_become_retry_authority(self):
        permit = self.reserve()
        self.drain(permit)
        self.rejects('REPLAY_COMMAND_ALREADY_REGISTERED', self.reserve)
        self.rejects('REPLAY_COMMAND_ID_COLLISION', self.reserve, request_digest='sha256:' + '8' * 64)
        self.rejects('REPLAY_COMMAND_ID_COLLISION', self.reserve, operation='play.inspect')
        rotated = self.owner.rotate(self.credential)
        grant = self.authorize(rotated)
        self.rejects('REPLAY_COMMAND_ALREADY_REGISTERED', self.reserve, grant)

    def test_budget_is_finite_without_eviction_and_stop_still_works(self):
        for index in range(session.MAX_COMMANDS):
            self.drain(self.reserve(command_id='command.' + str(index)))
        self.rejects('REPLAY_COMMAND_LIMIT', self.reserve, command_id='command.extra')
        self.rejects('REPLAY_COMMAND_ALREADY_REGISTERED', self.reserve, command_id='command.0')
        self.assertIs(self.authorize(operation='control.lookup'), self.grant)
        self.assertTrue(self.owner.stop(self.grant)['stopped'])
        self.assertEqual(self.owner.status()['commands_used'], session.MAX_COMMANDS)

    def test_rotation_cancels_unused_grant_and_invalidates_old_bearer(self):
        permit = self.reserve()
        rotated = self.owner.rotate(self.credential)
        self.rejects('AUTH_REQUIRED', self.authorize)
        self.rejects('REPLAY_GRANT_REQUIRED', self.reserve)
        self.assertEqual(self.owner.permit_status(permit), 'CANCELED')
        self.rejects('REPLAY_PERMIT_ALREADY_USED', self.owner.start_effect, permit)
        self.drain(self.reserve(self.authorize(rotated), command_id='command.next'))

    def test_unrelated_rotation_and_revoke_do_not_cancel_active_grant(self):
        reader = self.owner.issue(operations=frozenset({'play.inspect'}))
        permit = self.reserve()
        rotated = self.owner.rotate(reader)
        self.owner.revoke(rotated)
        self.drain(permit)
        self.assertEqual(self.owner.permit_status(permit), 'DRAINED')

    def test_revoke_cancels_reserved_and_does_not_claim_process_effect(self):
        permit = self.reserve()
        status = self.owner.revoke(self.credential)
        self.assertFalse(status['draining'])
        self.assertFalse(status['public_ack'])
        self.assertEqual(self.owner.permit_status(permit), 'CANCELED')
        self.rejects('AUTH_REQUIRED', self.authorize)

    def test_started_effect_drains_after_revoke_but_cannot_deliver_under_old_grant(self):
        permit = self.reserve()
        self.owner.start_effect(permit)
        self.assertTrue(self.owner.revoke(self.credential)['draining'])
        self.owner.finish_effect(permit, known=True)
        self.rejects('REPLAY_GRANT_REQUIRED', self.owner.check_delivery, self.grant,
                     operation='play.start', deadline_ms=permit.deadline_ms)
        self.assertFalse(self.owner.status()['draining'])

    def test_stop_cancels_reserved_and_rotation_cannot_resume(self):
        permit = self.reserve()
        status = self.owner.stop(self.grant)
        self.assertEqual(self.owner.permit_status(permit), 'CANCELED')
        self.assertFalse(status['draining'])
        self.assertFalse(status['public_ack'])
        self.rejects('REPLAY_STOPPED', self.owner.issue)
        rotated = self.owner.rotate(self.credential)
        self.rejects('REPLAY_STOPPED', self.authorize, rotated)
        grant = self.authorize(rotated, 'control.lookup')
        self.assertTrue(self.owner.stop(grant)['stopped'])

    def test_stop_returns_while_started_external_phase_has_not_finished(self):
        permit = self.reserve()
        self.owner.start_effect(permit)
        outputs = []
        thread = threading.Thread(target=lambda: outputs.append(self.owner.stop(self.grant)))
        thread.start()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive(), 'Stop waited for a started external phase')
        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0]['draining'])
        self.owner.finish_effect(permit, known=True)
        self.assertFalse(self.owner.status()['draining'])
        self.rejects('REPLAY_STOPPED', self.owner.check_delivery, self.grant,
                     operation='play.start', deadline_ms=permit.deadline_ms)

    def test_unknown_effect_latches_hold_and_keeps_lookup_access(self):
        permit = self.reserve()
        self.drain(permit, known=False)
        status = self.owner.status()
        self.assertTrue(status['held'])
        self.assertTrue(status['stopped'])
        self.assertFalse(status['draining'])
        self.assertFalse(status['public_ack'])
        self.assertEqual(self.owner.permit_status(permit), 'UNKNOWN')
        self.rejects('REPLAY_STOPPED', self.reserve, command_id='command.next')
        self.assertIs(self.authorize(operation='control.lookup'), self.grant)

    def test_deadline_rechecked_at_start_and_delivery_without_fake_drain(self):
        permit = self.reserve(deadline_ms=self.now + 100)
        self.now += 100
        self.rejects('REPLAY_DEADLINE_EXPIRED', self.owner.start_effect, permit)
        self.rejects('REPLAY_DEADLINE_EXPIRED', self.owner.check_delivery, self.grant,
                     operation='play.start', deadline_ms=permit.deadline_ms)
        self.assertEqual(self.owner.permit_status(permit), 'RESERVED')
        self.owner.cancel_reserved(permit)
        self.assertFalse(self.owner.status()['draining'])

    def test_deadlines_are_limited_by_command_grant_and_owner(self):
        for bad in (True, self.now, self.now + session.MAX_COMMAND_MS + 1):
            self.rejects('REPLAY_DEADLINE_EXPIRED', self.reserve, deadline_ms=bad)
        credential = self.owner.issue(ttl_ms=500)
        grant = self.authorize(credential)
        self.rejects('REPLAY_DEADLINE_EXPIRED', self.reserve, grant, deadline_ms=self.now + 501)
        self.owner.cancel_reserved(self.reserve(grant, deadline_ms=self.now + 500))
        self.now += 59_900
        rotated = self.owner.rotate(self.credential, ttl_ms=session.MAX_OWNER_MS)
        self.assertEqual(rotated.expires_ms, 1_800_000_090_000)
        self.now = rotated.expires_ms
        self.rejects('SESSION_EXPIRED', self.authorize, rotated)

    def test_expiry_after_start_allows_only_cleanup(self):
        permit = self.reserve()
        self.owner.start_effect(permit)
        self.now = self.credential.expires_ms
        self.owner.finish_effect(permit, known=True)
        self.assertEqual(self.owner.permit_status(permit), 'DRAINED')
        self.rejects('SESSION_INVALIDATED', self.owner.check_delivery, self.grant,
                     operation='play.start', deadline_ms=permit.deadline_ms)

    def test_owner_deadline_is_hard_bound_even_if_issuer_mints_a_millisecond_later(self):
        value = self.make_owner(owner_deadline_ms=self.now + 500)
        # The accepted issuer reads its own clock after the replay TTL was
        # computed. A later mint must not extend the replay owner's lifetime.
        with patch('studio.host.core.transport.epoch_ms', side_effect=lambda: self.now + 1):
            credential = value.issue()
        self.assertEqual(credential.expires_ms, self.now + 501)
        self.now += 500
        self.rejects('REPLAY_OWNER_EXPIRED', value.authenticate, 'Bearer ' + credential.bearer)

    def test_ttl_command_id_digest_and_outcome_types_are_strict(self):
        for bad in (True, 0, -1, session.MAX_OWNER_MS + 1):
            self.rejects('REPLAY_INVALID_SESSION_TTL', self.owner.issue, ttl_ms=bad)
        for bad in (None, '../command', 'Upper', 'c' * 65):
            self.rejects('REPLAY_INVALID_COMMAND_ID', self.reserve, command_id=bad)
        for bad in (None, 'a' * 64, 'sha256:' + 'A' * 64):
            self.rejects('REPLAY_INVALID_REQUEST_DIGEST', self.reserve, request_digest=bad)
        self.rejects('REPLAY_WORK_OPERATION_REQUIRED', self.reserve, operation='control.stop')
        permit = self.reserve()
        self.owner.start_effect(permit)
        self.rejects('REPLAY_INVALID_OUTCOME', self.owner.finish_effect, permit, known=1)
        self.owner.finish_effect(permit, known=True)

    def test_retained_secrets_cannot_be_public_ids_or_rewritten_hash_bound_output(self):
        with patch('studio.host.core.transport.secrets.token_urlsafe', return_value='a' * 43):
            credential = self.owner.issue()
        rotated = self.owner.rotate(credential)
        self.owner.revoke(rotated)
        self.rejects('SENSITIVE_IDENTIFIER_FORBIDDEN', self.owner.validate_public_identifier, credential.bearer)
        self.rejects('REPLAY_SENSITIVE_OUTPUT', self.owner.encode_output, {'value': credential.bearer})
        output = repr(self.owner.redact_output({'old': credential.bearer, 'new': rotated.bearer}))
        self.assertNotIn(credential.bearer, output)
        self.assertNotIn(rotated.bearer, output)
        plain = {'command_id': 'command.safe', 'observation_sha256': '8' * 64}
        self.assertEqual(self.owner.encode_output(plain), canonical_bytes(plain))

    def test_newly_minted_secret_in_bound_id_is_rejected_and_revoked(self):
        for field in ('run_id', 'command_id', 'runtime_instance_id'):
            value = self.make_owner(binding={**binding(), field: 'a' * 43})
            with patch('studio.host.core.transport.secrets.token_urlsafe', return_value='a' * 43):
                self.rejects('SENSITIVE_IDENTIFIER_FORBIDDEN', value.issue)
            self.rejects('AUTH_REQUIRED', value.authenticate, 'Bearer ' + 'a' * 43)
        value = session.ReplaySession('a' * 43, Path(self.temp.name), catalog_digest=CATALOG,
            binding=binding(), owner_deadline_ms=self.now + 90_000)
        with patch('studio.host.core.transport.secrets.token_urlsafe', return_value='a' * 43):
            self.rejects('SENSITIVE_IDENTIFIER_FORBIDDEN', value.issue)

    def test_session_and_credential_history_budgets_fail_closed(self):
        for _ in range(session.MAX_SESSIONS - 1):
            self.owner.issue()
        self.rejects('SESSION_LIMIT', self.owner.issue)
        value = self.make_owner()
        credential = value.issue()
        for _ in range(session.MAX_CREDENTIAL_HISTORY - 1):
            credential = value.rotate(credential)
        self.rejects('CREDENTIAL_HISTORY_LIMIT', value.rotate, credential)
        self.assertEqual(value.authenticate('Bearer ' + credential.bearer).session_id, credential.session_id)

    def test_trusted_halt_is_latched_and_does_not_forge_public_ack(self):
        permit = self.reserve()
        status = self.owner.halt()
        self.assertTrue(status['stopped'])
        self.assertFalse(status['draining'])
        self.assertFalse(status['public_ack'])
        self.assertEqual(self.owner.permit_status(permit), 'CANCELED')
        self.rejects('REPLAY_STOPPED', self.reserve, command_id='command.next')


if __name__ == '__main__':
    unittest.main()
