"""Grant/phase lifecycle tests; no mocked phase is engine evidence."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s52_publication_session_test', STUDIO/'godot-addon/publication_session.py')
session = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = session
spec.loader.exec_module(session)
CATALOG = 'sha256:' + '1'*64
DIGEST = 'sha256:' + '2'*64


class PublicationSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-godot-auth-')
        self.addCleanup(self.temp.cleanup)
        self.owner = session.PublicationSession('project.fixture', Path(self.temp.name), CATALOG)
        self.credential = self.owner.issue()
        self.grant = self.authorize()
        self.lease = self.owner.lease(self.grant)

    def authorize(self, credential=None, operation='scene.save', **changes):
        fields = dict(project_id='project.fixture', catalog_digest=CATALOG)
        fields.update(changes)
        return self.owner.authorize('Bearer ' + (credential or self.credential).bearer, operation, **fields)

    def permit(self, **changes):
        fields = dict(command_id='command.save', digest=DIGEST, phase='capture', deadline_ms=self.lease.expires_ms)
        fields.update(changes)
        return self.owner.reserve_phase(self.grant, self.lease, **fields)

    def test_fixture_bearer_and_unregistered_empty_scope_never_become_godot_grant(self):
        issuer = session.SessionAuthority('project.fixture', Path(self.temp.name), session.TransportLimits())
        for scopes in (frozenset({'fixture.write'}), frozenset()):
            with self.subTest(scopes=scopes), self.assertRaisesRegex(session.SafetyViolation, 'AUTH_REQUIRED'):
                self.authorize(issuer.issue(scopes=scopes))
        unregistered = self.owner._issuer.issue(scopes=frozenset())
        with self.assertRaisesRegex(session.SafetyViolation, 'GODOT_GRANT_REQUIRED'):
            self.authorize(unregistered)
        self.assertEqual(self.credential.scopes, frozenset())

    def test_catalog_project_and_operation_do_not_follow_caller_input(self):
        for fields in ({'project_id':'project.foreign'}, {'catalog_digest':'sha256:'+'3'*64}):
            with self.subTest(fields=fields), self.assertRaisesRegex(session.SafetyViolation, 'BINDING'):
                self.authorize(**fields)
        with self.assertRaisesRegex(session.SafetyViolation, 'OPERATION_FORBIDDEN'):
            self.authorize(operation='fixture.set')

    def test_copied_and_mutated_grant_and_lease_do_not_authorize(self):
        for grant, lease in ((replace(self.grant), self.lease), (self.grant, replace(self.lease))):
            with self.assertRaises(session.SafetyViolation):
                self.owner.check(grant, lease, deadline_ms=self.lease.expires_ms)
        object.__setattr__(self.lease, 'fencing_epoch', 100)
        with self.assertRaisesRegex(session.SafetyViolation, 'STALE_LEASE'):
            self.permit()
        object.__setattr__(self.grant, 'operations', ('scene.save',))
        with self.assertRaisesRegex(session.SafetyViolation, 'GRANT_REQUIRED'):
            self.authorize()

    def test_rotation_invalidates_reserved_phase_and_old_bearer(self):
        permit = self.permit()
        rotated = self.owner.rotate(self.credential)
        with self.assertRaisesRegex(session.SafetyViolation, 'AUTH_REQUIRED'):
            self.authorize()
        with self.assertRaisesRegex(session.SafetyViolation, 'PERMIT_ALREADY_USED'):
            self.owner.start_effect(permit)
        new_grant = self.authorize(rotated)
        new_lease = self.owner.lease(new_grant)
        self.assertGreater(new_lease.fencing_epoch, self.lease.fencing_epoch)

    def test_stop_before_start_cancels_without_inflight_claim(self):
        permit = self.permit()
        status = self.owner.stop(self.grant)
        self.assertTrue(status['stopped'])
        self.assertFalse(status['draining'])
        with self.assertRaisesRegex(session.SafetyViolation, 'PERMIT_ALREADY_USED'):
            self.owner.start_effect(permit)
        with self.assertRaisesRegex(session.SafetyViolation, 'STOPPED'):
            self.permit(phase='stage')

    def test_stop_during_started_effect_returns_promptly_and_blocks_next_phase(self):
        permit = self.permit()
        self.owner.start_effect(permit)
        outputs = []
        thread = threading.Thread(target=lambda: outputs.append(self.owner.stop(self.grant)))
        thread.start(); thread.join(timeout=1)
        self.assertFalse(thread.is_alive(), 'Stop must not wait for an external effect')
        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0]['draining'])
        self.owner.finish_effect(permit, known=True)
        self.assertFalse(self.owner.status()['draining'])
        with self.assertRaisesRegex(session.SafetyViolation, 'STOPPED'):
            self.permit(phase='select')

    def test_revoke_during_started_phase_cannot_claim_no_effect_and_cannot_reuse(self):
        permit = self.permit()
        self.owner.start_effect(permit)
        self.assertTrue(self.owner.revoke(self.credential)['draining'])
        self.owner.finish_effect(permit, known=True)
        with self.assertRaisesRegex(session.SafetyViolation, 'PERMIT_ALREADY_USED'):
            self.owner.start_effect(permit)
        with self.assertRaises(session.SafetyViolation):
            self.permit(phase='adopt')

    def test_deadline_is_rechecked_at_effect_not_only_reservation(self):
        permit = self.permit()
        with patch.object(session, 'epoch_ms', return_value=self.lease.expires_ms):
            with self.assertRaisesRegex(session.SafetyViolation, 'DEADLINE_EXPIRED'):
                self.owner.start_effect(permit)
        self.owner.cancel_reserved(permit)
        self.assertFalse(self.owner.status()['draining'])

    def test_unknown_effect_holds_all_further_mutation(self):
        permit = self.permit()
        self.owner.start_effect(permit)
        self.owner.finish_effect(permit, known=False)
        self.assertEqual(self.owner.status(), {'stopped':True,'held':True,'draining':False,'public_ack':False})
        with self.assertRaisesRegex(session.SafetyViolation, 'STOPPED'):
            self.permit(phase='adopt')
        with self.assertRaisesRegex(session.SafetyViolation, 'STOPPED'):
            self.owner.issue()

    def test_permit_copies_and_mutations_cannot_start_effect(self):
        permit = self.permit()
        with self.assertRaisesRegex(session.SafetyViolation, 'UNKNOWN_PERMIT'):
            self.owner.start_effect(replace(permit))
        object.__setattr__(permit, 'phase', 'select')
        with self.assertRaisesRegex(session.SafetyViolation, 'UNKNOWN_PERMIT'):
            self.owner.start_effect(permit)

    def test_one_live_lease_and_one_effect_then_exact_single_use(self):
        with self.assertRaisesRegex(session.SafetyViolation, 'LEASE_BUSY'):
            self.owner.lease(self.grant)
        permit = self.permit()
        with self.assertRaisesRegex(session.SafetyViolation, 'EFFECT_BUSY'):
            self.permit(phase='stage')
        self.owner.start_effect(permit)
        with self.assertRaisesRegex(session.SafetyViolation, 'EFFECT_DRAIN_REQUIRED'):
            self.owner.lease(self.grant)
        self.owner.finish_effect(permit, known=True)
        with self.assertRaisesRegex(session.SafetyViolation, 'EFFECT_NOT_STARTED'):
            self.owner.finish_effect(permit, known=True)

    def test_all_issued_secrets_remain_redacted_after_rotation_and_revoke(self):
        rotated = self.owner.rotate(self.credential)
        self.owner.revoke(rotated)
        result = repr(self.owner.redact_output({'old':self.credential.bearer,'new':rotated.bearer}))
        self.assertNotIn(self.credential.bearer, result)
        self.assertNotIn(rotated.bearer, result)
        self.assertNotIn(self.credential.bearer, repr(self.credential))


if __name__ == '__main__':
    unittest.main()
