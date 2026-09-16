"""Real registered session authority with inert recovery owners; no engine proof."""
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('gt03_recovery_authority_tests',STUDIO/'godot-addon/publication_recovery.py')
recovery=importlib.util.module_from_spec(spec);sys.modules[spec.name]=recovery;spec.loader.exec_module(recovery)
auth=recovery.session_model


class ReconciliationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-recovery-authority-');self.addCleanup(self.temp.cleanup)
        self.catalog='sha256:'+'1'*64;self.digest='sha256:'+'2'*64
        self.sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),self.catalog,minimum_fencing_epoch=10)
        self.credential=self.sessions.issue(operations=frozenset({'project.reconcile','control.stop'}))
        self.grant=self.sessions.authorize('Bearer '+self.credential.bearer,'project.reconcile',
            project_id='project.fixture',catalog_digest=self.catalog)
        self.lease=self.sessions.lease(self.grant,ttl_ms=30000)
        self.value=recovery.ReconciliationAuthority(self.sessions,self.grant,self.lease)
        self.owner=object.__new__(recovery.PublicationRecovery)
        self.owner._lock=threading.RLock();self.owner._held=self.owner._closed=False
        self.context={'storage_id':'a'*32,'project_id':'project.fixture','source_closure_sha256':'3'*64,
            'editor_engine_sha256':'4'*64,'publication_prefix_sha256':'5'*64,
            'native_head':{'sequence':20,'sha256':'6'*64,'size':12345},
            'selected':{'descriptor':'inert-unit-fixture'},'minimum_authority_epoch':10}
        # Deliberately inert journal boundary. No native or engine proof is claimed.
        self.owner.authority_context=lambda:copy.deepcopy(self.context)
        self.owner._journal=mock.Mock()
        self.owner._journal.snapshot.return_value={'stopped':False,'held':False,'last_good':{'descriptor':'different-selection'}}
        self.owner._journal.lookup.return_value={'phase':'SELECTED'}
        self.deadline=min(self.lease.expires_ms,recovery._now()+20000)

    def bind(self):return self.value.bind(self.owner,'command.recover',self.digest,deadline_ms=self.deadline)

    def test_real_registered_session_and_epoch_required(self):
        for sessions,grant,lease in ((mock.Mock(),self.grant,self.lease),(self.sessions,replace(self.grant),self.lease),
                                      (self.sessions,self.grant,replace(self.lease))):
            with self.subTest(sessions=type(sessions).__name__),self.assertRaises(Exception):
                recovery.ReconciliationAuthority(sessions,grant,lease)
        self.context['minimum_authority_epoch']=self.lease.fencing_epoch
        with self.assertRaisesRegex(recovery.RecoveryError,'EPOCH'):self.bind()

    def test_saved_publication_grant_does_not_gain_reconciliation(self):
        sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),self.catalog)
        credential=sessions.issue(operations=frozenset({'scene.save'}))
        grant=sessions.authorize('Bearer '+credential.bearer,'scene.save',project_id='project.fixture',catalog_digest=self.catalog)
        lease=sessions.lease(grant)
        with self.assertRaisesRegex(auth.PublicationSessionError,'FORBIDDEN'):
            recovery.ReconciliationAuthority(sessions,grant,lease)

    def test_one_shot_owner_binding_and_copied_permit_reject(self):
        permit=self.bind();effect=mock.Mock()
        with self.assertRaisesRegex(recovery.RecoveryError,'ALREADY_BOUND'):self.bind()
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED'):
            self.value._phase(replace(permit),'capture',effect)
        effect.assert_not_called()
        object.__setattr__(permit,'digest','sha256:'+'9'*64)
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED'):self.value._phase(permit,'capture',effect)
        effect.assert_not_called()

    def test_native_head_or_selected_source_change_denies_before_effect(self):
        permit=self.bind();effect=mock.Mock()
        for key,value in [('native_head',{'sequence':21,'sha256':'7'*64,'size':12350}),
                          ('selected',{'descriptor':'substituted'}),('source_closure_sha256','8'*64),('storage_id','b'*32)]:
            prior=self.context[key];self.context[key]=value
            with self.subTest(key=key),self.assertRaises(recovery.RecoveryError):self.value._phase(permit,'capture',effect)
            self.context[key]=prior
        effect.assert_not_called()

    def test_phase_order_once_and_known_head_advancement(self):
        permit=self.bind();effect=mock.Mock()
        with self.assertRaisesRegex(recovery.RecoveryError,'ORDER'):self.value._phase(permit,'adopt',effect)
        effect.assert_not_called()
        def capture():
            self.context['native_head']={'sequence':21,'sha256':'a'*64,'size':13000}
            self.context['minimum_authority_epoch']=self.lease.fencing_epoch
            return 'admitted'
        self.assertEqual(self.value._phase(permit,'capture',capture),'admitted')
        with self.assertRaisesRegex(recovery.RecoveryError,'ORDER'):self.value._phase(permit,'capture',effect)
        self.value._phase(permit,'adopt',lambda:'actual-readback-placeholder')
        self.value._phase(permit,'commit',lambda:'durable-terminal-placeholder')
        with self.assertRaisesRegex(recovery.RecoveryError,'ORDER'):self.value._phase(permit,'commit',effect)
        self.assertFalse(self.sessions.status()['draining'])

    def test_revoke_between_phases_prevents_next_effect(self):
        permit=self.bind();self.value._phase(permit,'capture',lambda:None)
        self.sessions.revoke(self.credential);effect=mock.Mock()
        with self.assertRaises(Exception):self.value._phase(permit,'adopt',effect)
        effect.assert_not_called()

    def test_stop_during_effect_reports_draining_and_prevents_next_phase(self):
        permit=self.bind();observed=[]
        def capture():observed.append(self.sessions.stop(self.grant))
        self.value._phase(permit,'capture',capture)
        self.assertTrue(observed[0]['draining']);self.assertTrue(observed[0]['stopped'])
        effect=mock.Mock()
        with self.assertRaisesRegex(auth.PublicationSessionError,'STOPPED'):self.value._phase(permit,'adopt',effect)
        effect.assert_not_called();self.assertFalse(self.sessions.status()['draining'])

    def test_unknown_effect_latches_both_authorities(self):
        permit=self.bind()
        with self.assertRaises(OSError):self.value._phase(permit,'capture',lambda:(_ for _ in ()).throw(OSError('injected')))
        self.assertTrue(self.sessions.status()['held']);self.assertTrue(self.value._held)
        with self.assertRaises(recovery.RecoveryError):self.value._phase(permit,'capture',lambda:None)

    def test_stopped_unknown_and_expired_binding_never_schedules(self):
        for field in ('stopped','held'):
            self.owner._journal.snapshot.return_value[field]=True
            with self.subTest(field=field),self.assertRaises(recovery.RecoveryError):self.bind()
            self.owner._journal.snapshot.return_value[field]=False
        self.owner._journal.lookup.return_value={'phase':'UNKNOWN'}
        with self.assertRaises(recovery.RecoveryError):self.bind()
        self.owner._journal.lookup.return_value={'phase':'SELECTED'}
        self.deadline=recovery._now()-1
        with self.assertRaisesRegex(recovery.RecoveryError,'DEADLINE'):self.bind()

    def test_unknown_only_restores_exact_last_good_with_explicit_fresh_authority(self):
        self.owner._journal.lookup.return_value={'phase':'UNKNOWN'}
        self.owner._journal.snapshot.return_value.update(held=True,last_good=copy.deepcopy(self.context['selected']))
        permit=self.bind()
        self.assertIs(self.value._permit,permit)
        self.owner._journal.snapshot.return_value['stopped']=True
        sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),self.catalog,minimum_fencing_epoch=10)
        credential=sessions.issue(operations=frozenset({'project.reconcile'}))
        grant=sessions.authorize('Bearer '+credential.bearer,'project.reconcile',project_id='project.fixture',catalog_digest=self.catalog)
        value=recovery.ReconciliationAuthority(sessions,grant,sessions.lease(grant,ttl_ms=30000))
        with self.assertRaisesRegex(recovery.RecoveryError,'STOP_OR_UNKNOWN'):
            value.bind(self.owner,'command.recover',self.digest,deadline_ms=self.deadline)


if __name__=='__main__':unittest.main(verbosity=2)
