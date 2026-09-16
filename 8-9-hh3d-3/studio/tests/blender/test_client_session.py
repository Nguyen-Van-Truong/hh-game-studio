"""Pure bearer lifecycle and registered Blender-only read authority."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.client_session import BlenderClientSession,BlenderReadLease
from studio.host.blender import client_catalog as catalog
from studio.host.core.transport import epoch_ms
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.session=BlenderClientSession('blender.test',Path('owned'),owner_deadline_ms=epoch_ms()+90000)
        self.credential=self.session.issue();self.auth='Bearer '+self.credential.bearer
        self.grant=self.session.authenticate(self.auth)
    def test_empty_fixture_scopes_and_registered_blender_grant(self):
        self.assertEqual(self.credential.scopes,frozenset())
        self.assertEqual(self.session.authorize(self.auth,'scene.inspect',project_id='blender.test',catalog_digest=catalog.CATALOG_DIGEST),self.grant)
    def test_issuer_only_token_cannot_grant_blender_authority(self):
        foreign=self.session._issuer.issue(scopes=frozenset({'fixture.read'}))
        with self.assertRaisesRegex(SafetyViolation,'GRANT_REQUIRED'):self.session.authenticate('Bearer '+foreign.bearer)
    def test_wrong_project_catalog_and_operation_rejected(self):
        for changes in ({'project_id':'other'},{'catalog_digest':'sha256:'+'0'*64},{'operation':'mesh.create_box'}):
            args=dict(operation='scene.inspect',project_id='blender.test',catalog_digest=catalog.CATALOG_DIGEST);args.update(changes)
            with self.subTest(changes=changes),self.assertRaises(SafetyViolation):self.session.authorize(self.auth,**args)
    def test_grant_copy_and_field_tamper_rejected(self):
        with self.assertRaisesRegex(SafetyViolation,'GRANT_REQUIRED'):self.session.read_lease(copy.copy(self.grant),ttl_ms=1000)
        object.__setattr__(self.grant,'operations',('mesh.create_box',))
        with self.assertRaisesRegex(SafetyViolation,'GRANT_REQUIRED'):self.session.authenticate(self.auth)
    def test_lease_registration_and_wrong_session(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000)
        with self.assertRaisesRegex(SafetyViolation,'READ_LEASE_REQUIRED'):
            self.session.check_read(self.grant,copy.copy(lease),deadline_ms=epoch_ms()+500)
        second=self.session.issue();other=self.session.authenticate('Bearer '+second.bearer)
        with self.assertRaisesRegex(SafetyViolation,'READ_LEASE_REQUIRED'):self.session.resolve_lease(other,lease.lease_id,0)
    def test_lease_mutation_is_not_authority(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000);object.__setattr__(lease,'expires_ms',lease.expires_ms+1)
        with self.assertRaisesRegex(SafetyViolation,'READ_LEASE_REQUIRED'):self.session.resolve_lease(self.grant,lease.lease_id,0)
    def test_expired_and_overlong_deadlines_rejected(self):
        lease=self.session.read_lease(self.grant,ttl_ms=10000)
        for deadline in (epoch_ms()-1,epoch_ms()+catalog.MAX_READ_MS+100):
            with self.assertRaisesRegex(SafetyViolation,'DEADLINE_EXPIRED'):self.session.check_read(self.grant,lease,deadline_ms=deadline)
    def test_read_lease_never_outlives_owned_gui(self):
        self.session._owner_deadline_ms=epoch_ms()+1000
        lease=self.session.read_lease(self.grant,ttl_ms=30000)
        self.assertLessEqual(lease.expires_ms,self.session._owner_deadline_ms)
    def test_rotate_invalidates_old_bearer_grant_and_lease(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000);rotated=self.session.rotate(self.credential)
        with self.assertRaises(SafetyViolation):self.session.authenticate(self.auth)
        current=self.session.authenticate('Bearer '+rotated.bearer)
        with self.assertRaises(SafetyViolation):self.session.resolve_lease(current,lease.lease_id,0)
        with self.assertRaises(SafetyViolation):self.session.read_lease(self.grant,ttl_ms=1000)
    def test_revoke_denies_future_reads_and_reports_started_read(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000)
        permit=self.session.start_read(self.grant,lease,deadline_ms=epoch_ms()+500)
        self.assertTrue(self.session.revoke(self.credential)['read_draining'])
        with self.assertRaises(SafetyViolation):self.session.check_read(self.grant,lease,deadline_ms=epoch_ms()+100)
        self.session.finish_read(permit)
    def test_stop_denies_new_read_but_keeps_lookup_auth(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000);self.session.stop(self.grant)
        with self.assertRaisesRegex(SafetyViolation,'STOPPED'):self.session.start_read(self.grant,lease,deadline_ms=epoch_ms()+100)
        self.session.authorize(self.auth,'control.lookup',project_id='blender.test',catalog_digest=catalog.CATALOG_DIGEST)
    def test_publication_guard_rechecks_expired_lease_and_replaced_grant(self):
        lease=self.session.read_lease(self.grant,ttl_ms=1000)
        with self.assertRaisesRegex(SafetyViolation,'DEADLINE_EXPIRED'):
            with self.session.publish_read(self.grant,lease,deadline_ms=epoch_ms()-1):
                self.fail('expired observation was published')
        self.session.rotate(self.credential)
        with self.assertRaisesRegex(SafetyViolation,'GRANT_REQUIRED'):
            with self.session.publish_read(self.grant,lease,deadline_ms=epoch_ms()+100):
                self.fail('revoked observation was published')
    def test_secret_identifier_and_old_bearer_redaction(self):
        self.session.rotate(self.credential)
        with self.assertRaises(SafetyViolation):self.session.validate_public_identifier(self.credential.bearer)
        self.assertNotIn(self.credential.bearer,self.session.encode_output({'error':self.credential.bearer}).decode())
    def test_read_response_cannot_be_silently_changed_by_output_redaction(self):
        for name in ('C:/private/item','/private/item',self.credential.bearer):
            value={'code':'BLENDER_READ_CONFIRMED','postconditions':{'observation':{'name':name}}}
            with self.subTest(kind='path-or-token'),self.assertRaisesRegex(SafetyViolation,'SENSITIVE_OBSERVATION'):
                self.session.encode_output(value)
    def test_new_secret_history_rejects_old_observation_instead_of_rehashing(self):
        future_bearer='z'*43
        value={'code':'BLENDER_READ_CONFIRMED','postconditions':{'observation':{'name':future_bearer}}}
        before=canonical_bytes(value)
        self.assertEqual(self.session.encode_output(value),before)
        with patch('studio.host.core.transport.secrets.token_urlsafe',return_value=future_bearer):
            self.session.issue()
        with self.assertRaisesRegex(SafetyViolation,'SENSITIVE_OBSERVATION'):self.session.encode_output(value)
        self.assertEqual(canonical_bytes(value),before)
    def test_budget_has_no_lease_eviction_replay(self):
        for _ in range(32):self.session.read_lease(self.grant,ttl_ms=1000)
        with self.assertRaisesRegex(SafetyViolation,'LEASE_LIMIT'):self.session.read_lease(self.grant,ttl_ms=1000)

if __name__=='__main__':unittest.main()
