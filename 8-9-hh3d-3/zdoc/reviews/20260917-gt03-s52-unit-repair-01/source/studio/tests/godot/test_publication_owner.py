"""Coordinator boundary regressions with inert owners; native proof is separate."""
import importlib.util
from dataclasses import make_dataclass
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s52_owner_test',STUDIO/'godot-addon/publication_owner.py')
owner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=owner;spec.loader.exec_module(owner)
auth=owner._load('publication_session')
from studio.protocol.core import Request, Status, canonical_bytes


class PublicationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-owner-unit-');self.addCleanup(self.temp.cleanup)
        self.value=object.__new__(owner.GodotPublicationOwner)
        self.value._lock=threading.RLock();self.value._work=threading.Lock()
        self.value.sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),'sha256:'+'1'*64)
        self.value._held=self.value._closed=False
        self.value._editor=self.value._validator=None
        self.value._journal=types.SimpleNamespace(lookup=lambda *_:{'phase':'COMMITTED','receipt_sha256':'2'*64})
        self.record={'status':'COMMITTED','code':'GODOT_MANAGED_SCENE_SAVED','digest':'sha256:'+'3'*64,
            'postconditions':{'public_ack':True,'durable_receipt_sha256':'2'*64}}

    def test_original_reply_requires_current_durable_receipt(self):
        result=self.value._reply('command.save',self.record)
        self.assertEqual(result.status,Status.COMMITTED)
        self.value._journal.lookup=lambda *_:None
        result=self.value._reply('command.save',self.record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertTrue(self.value._held)

    def test_different_durable_receipt_cannot_relabel_cached_ack(self):
        self.value._journal.lookup=lambda *_:{'phase':'COMMITTED','receipt_sha256':'4'*64}
        self.assertEqual(self.value._reply('command.save',self.record).status,Status.UNKNOWN)
        self.assertEqual(self.record['status'],'COMMITTED')  # Historical result preserved.

    def test_pending_lookup_does_not_wait_for_disk_effect(self):
        self.value._journal.lookup=lambda *_:(_ for _ in ()).throw(AssertionError('unexpected disk wait'))
        record={'status':'ACCEPTED_PENDING','code':'GODOT_SAVE_PENDING','digest':'sha256:'+'3'*64}
        self.assertEqual(self.value._reply('command.save',record).status,Status.ACCEPTED_PENDING)

    def test_close_stops_before_attempting_child_cleanup_and_retains_failed_owner(self):
        observed=[]
        def close_editor():
            observed.append(self.value.sessions.status()['stopped'])
            raise RuntimeError('inert owned close failure')
        editor=types.SimpleNamespace(close=close_editor)
        self.value._editor=editor
        with self.assertRaises(owner.PublicationOwnerError) as failure:
            self.value.close()
        self.assertEqual(observed,[True])
        self.assertIs(failure.exception.cleanup_owner,self.value)
        self.assertIs(self.value._editor,editor)

    def test_root_instance_strings_are_exact_safe_integers(self):
        self.assertEqual(self.value._instance('123456'),123456)
        for value in (123,True,'01','1e3','0',str(2**53)):
            with self.subTest(value=value),self.assertRaises(owner.PublicationOwnerError):
                self.value._instance(value)

    def test_reserved_phase_revocation_never_calls_effect(self):
        credential=self.value.sessions.issue()
        grant=self.value.sessions.authorize('Bearer '+credential.bearer,'scene.save',
            project_id='project.fixture',catalog_digest='sha256:'+'1'*64)
        lease=self.value.sessions.lease(grant)
        request=types.SimpleNamespace(command_id='command.save',digest='sha256:'+'2'*64,deadline_ms=lease.expires_ms)
        original=self.value.sessions.start_effect
        def revoke_first(permit):
            self.value.sessions.revoke(credential)
            return original(permit)
        self.value.sessions.start_effect=revoke_first
        calls=[]
        with self.assertRaises(auth.SafetyViolation):
            self.value._phase(request,grant,lease,'capture',lambda:calls.append(1))
        self.assertEqual(calls,[])

    def _inert_save(self):
        """Real admission/coordinator; mocked engine and disk are not native proof."""
        value=self.value
        credential=value.sessions.issue()
        grant=value.sessions.authorize('Bearer '+credential.bearer,'scene.save',
            project_id='project.fixture',catalog_digest='sha256:'+'1'*64)
        lease=value.sessions.lease(grant)
        request=types.SimpleNamespace(command_id='command.save',digest='sha256:'+'3'*64,
            deadline_ms=lease.expires_ms-1)
        before={'generation':1,'revision':'sha256:'+'4'*64,'root_instance_id':'1',
            'state':{},'working_files':{},'project_revision':'sha256:'+'5'*64}
        bundle=types.SimpleNamespace(files={'script':b'x'},engine_sha256='6'*64,
            project_revision='sha256:'+'7'*64,scene_revision=before['revision'])
        value._editor=Mock()
        value._editor.prepare_effect.return_value=types.SimpleNamespace(scratch_name='fixed.tscn')
        value._editor.captured_semantic.return_value=b'{}'
        value._capture_facts=Mock(return_value={})
        value._adoption_facts=Mock(return_value={'generation_after':2})
        value._same_release=Mock();value.inspect=Mock(return_value=before)
        value._validator=Mock()
        value._validator.bind_semantics.return_value=(bundle,make_dataclass('InertSemanticReceipt',[])())
        value._validator.semantic_observation.return_value={'semantic':{}}
        value.validation_model=types.SimpleNamespace(
            factory=types.SimpleNamespace(compose=Mock(return_value=bundle)),
            comparator=types.SimpleNamespace(semantic_state_bytes=Mock(return_value=b'{}')))
        value.contract=types.SimpleNamespace(SCRIPT_PATH='script')
        value._journal=Mock()
        value._journal.read_selected_bundle.return_value=bundle
        value._journal.selection_facts.return_value={'selector':{'selection':{}}}
        value._journal.lookup.return_value={'capture_prepared':{},'phase':'COMMITTED','receipt_sha256':'8'*64}
        value._journal.commit.return_value={'receipt':{'status':'COMMITTED'},'receipt_sha256':'8'*64}
        value.journal_model=types.SimpleNamespace(state_model=types.SimpleNamespace(
            activation_current=Mock(return_value={})))
        record={'digest':request.digest,'status':'UNKNOWN','code':'PENDING'}
        return request,grant,lease,before,record,credential

    def test_stop_during_durable_readback_reports_commit_draining(self):
        request,grant,lease,before,record,_=self._inert_save()
        stops=[]
        self.value._journal.readback.side_effect=lambda *a,**k:stops.append(self.value.sessions.stop(grant))
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(len(stops),1)
        self.assertEqual(stops[0],{'stopped':True,'held':False,'draining':True,'public_ack':False})
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertTrue(result.postconditions['public_ack'])
        self.value._journal.commit.assert_called_once()
        self.assertFalse(self.value.sessions.status()['draining'])
        self.assertTrue(self.value.sessions.status()['stopped'])

    def test_stop_before_commit_admission_prevents_readback_and_commit(self):
        request,grant,lease,before,record,_=self._inert_save()
        start=self.value.sessions.start_effect
        stops=[]
        def stop_before_commit(permit):
            if permit.phase=='commit':stops.append(self.value.sessions.stop(grant))
            return start(permit)
        self.value.sessions.start_effect=stop_before_commit
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(len(stops),1)
        self.assertFalse(stops[0]['draining'])
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.value._journal.readback.assert_not_called()
        self.value._journal.commit.assert_not_called()

    def test_revocation_during_readback_accounts_for_started_completion(self):
        request,grant,lease,before,record,credential=self._inert_save()
        drains=[]
        self.value._journal.readback.side_effect=lambda *a,**k:drains.append(self.value.sessions.revoke(credential))
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(len(drains),1)
        self.assertTrue(drains[0]['draining'])
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertFalse(self.value.sessions.status()['draining'])
        with self.assertRaises(auth.SafetyViolation):
            self.value.sessions.authorize('Bearer '+credential.bearer,'scene.save',
                project_id='project.fixture',catalog_digest='sha256:'+'1'*64)

    def test_uncertain_commit_never_returns_public_ack(self):
        request,grant,lease,before,record,_=self._inert_save()
        self.value._journal.commit.side_effect=OSError('inert append uncertainty')
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertTrue(self.value.sessions.status()['held'])
        self.assertTrue(self.value._held)
        self.value._journal.unknown.assert_called_once()

    def _inert_read_owner(self):
        value=self.value
        value.contract=owner._load('contract');value.project_id='project.fixture'
        value.sessions=auth.PublicationSession(value.project_id,Path(self.temp.name),value.contract.CATALOG_DIGEST)
        value._jobs={};value._leases={};value._read_leases={};value._same_release=Mock()
        snapshot={'generation':1,'revision':'sha256:'+'1'*64,'project_revision':'sha256:'+'2'*64,
            'state':{'nodes':[{'stable_id':'root','parent_id':None,'node_type':'Node3D','name':'Fixture',
                'position':[0,0,0],'rotation_degrees':[0,0,0],'scale':[1,1,1]}]},
            'working_files':{path:{'sha256':'3'*64} for path in (value.contract.SCENE_PATH,value.contract.SCRIPT_PATH)}}
        value.inspect=Mock(return_value=snapshot)
        return snapshot

    def _inspect_request(self,snapshot,lease):
        payload={'expected_generation':snapshot['generation'],'offset':0,'limit':64}
        return Request(command_id='command.inspect',project_id=self.value.project_id,operation='scene.inspect',
            lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=snapshot['revision'],
            target={'stable_id':'root'},payload=payload,
            payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=lease['expires_ms']-1)

    def test_inspect_only_grant_defaults_to_read_lease_and_cannot_lease_writes(self):
        snapshot=self._inert_read_owner()
        credential=self.value.sessions.issue(operations=frozenset({'scene.inspect'}))
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':self.value.contract.CATALOG_DIGEST}
        body={'project_id':self.value.project_id,'ttl_ms':10000}
        lease=self.value.lease(body,**arguments)
        self.assertTrue(lease['lease_id'].startswith('read.'))
        self.assertEqual(lease['fencing_epoch'],0)
        self.assertEqual(self.value._leases,{})
        result=self.value.submit(self._inspect_request(snapshot,lease).as_dict(),**arguments)
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertEqual(result.code,'GODOT_SCENE_INSPECTED')
        self.assertEqual(result.postconditions,snapshot)
        with self.assertRaises(auth.SafetyViolation):
            self.value.lease({**body,'access':'write'},**arguments)

    def test_explicit_read_lease_and_inspection_work_after_stop(self):
        snapshot=self._inert_read_owner()
        credential=self.value.sessions.issue()
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':self.value.contract.CATALOG_DIGEST}
        stopped=self.value.stop({'project_id':self.value.project_id,'command_id':'control.stop'},**arguments)
        self.assertTrue(stopped['stopped'])
        body={'project_id':self.value.project_id,'ttl_ms':10000,'access':'read'}
        first=self.value.lease(body,**arguments)
        renewed=self.value.lease(body,**arguments)
        self.assertNotEqual(first['lease_id'],renewed['lease_id'])
        result=self.value.submit(self._inspect_request(snapshot,renewed).as_dict(),**arguments)
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertEqual(self.value._leases,{})
        with self.assertRaises(auth.SafetyViolation):
            self.value.lease({**body,'access':'write'},**arguments)


if __name__=='__main__':unittest.main()
