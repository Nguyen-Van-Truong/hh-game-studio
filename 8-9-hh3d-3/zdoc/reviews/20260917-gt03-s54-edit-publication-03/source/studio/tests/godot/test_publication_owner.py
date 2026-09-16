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
from studio.protocol.core import Request, Response, Status, canonical_bytes


class PublicationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-owner-unit-');self.addCleanup(self.temp.cleanup)
        self.value=object.__new__(owner.GodotPublicationOwner)
        self.value._lock=threading.RLock();self.value._work=threading.Lock()
        self.value.sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),'sha256:'+'1'*64)
        self.value._held=self.value._closed=False
        self.value._editor=self.value._validator=None
        self.value._retired_editors=[];self.value._cleanup_owners=[]
        self.value._journal=types.SimpleNamespace(lookup=lambda *_:{'phase':'COMMITTED','receipt_sha256':'2'*64})
        self.record={'status':'COMMITTED','code':'GODOT_MANAGED_SCENE_SAVED','digest':'sha256:'+'3'*64,
            'postconditions':{'public_ack':True,'durable_receipt_sha256':'2'*64}}
        self.record['postconditions']['request_digest']=self.record['digest']
        self.raw=canonical_bytes(Response(Status.COMMITTED,self.record['code'],'command.save',
            postconditions=self.record['postconditions']).as_dict())
        self.record['durable_response_sha256']=hashlib.sha256(self.raw).hexdigest()
        self.value._journal.lookup_response=lambda *_:self.raw

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
        self.value._journal.lookup_response=self.value._journal.lookup
        record={'status':'ACCEPTED_PENDING','code':'GODOT_SAVE_PENDING','digest':'sha256:'+'3'*64}
        self.assertEqual(self.value._reply('command.save',record).status,Status.ACCEPTED_PENDING)

    def test_reply_is_original_durable_bytes_not_cached_field_reconstruction(self):
        self.record['code']='NOT_THE_ORIGINAL_CODE'
        self.record['postconditions']={'public_ack':False}
        self.assertEqual(canonical_bytes(self.value._reply('command.save',self.record).as_dict()),self.raw)
        self.value._journal.lookup_response=lambda *_:self.raw+b' '
        self.assertEqual(self.value._reply('command.save',self.record).status,Status.UNKNOWN)

    def test_durable_unknown_replays_exact_response(self):
        raw=canonical_bytes(Response(Status.UNKNOWN,'GODOT_PUBLICATION_RECONCILE_REQUIRED','command.save',
            postconditions={'request_digest':self.record['digest'],'public_ack':False,
                            'reason':'owner.effect.uncertain','next_action':'lookup.reconcile'}).as_dict())
        self.value._journal.lookup_response=lambda *_:raw
        self.value._remember_response('command.save',self.record)
        self.assertEqual(canonical_bytes(self.value._reply('command.save',self.record).as_dict()),raw)

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
        request=types.SimpleNamespace(command_id='command.save',digest='sha256:'+'2'*64,
            deadline_ms=lease.expires_ms,operation='scene.save')
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
            deadline_ms=lease.expires_ms-1,operation='scene.save',payload={})
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
        value._journal.lookup.return_value={'capture_prepared':{},'phase':'CAPTURED'}
        def committed(*args,**kwargs):
            value._journal.lookup.return_value={'capture_prepared':{},'phase':'COMMITTED','receipt_sha256':'8'*64}
            return {'receipt':{'status':'COMMITTED'},'receipt_sha256':'8'*64}
        value._journal.commit.side_effect=committed
        reply=canonical_bytes(Response(Status.COMMITTED,'GODOT_MANAGED_SCENE_SAVED',request.command_id,
            postconditions={'request_digest':request.digest,'public_ack':True,
                            'durable_receipt_sha256':'8'*64}).as_dict())
        value._journal.lookup_response.return_value=reply
        def make_unknown(*args,**kwargs):
            value._journal.lookup_response.return_value=canonical_bytes(Response(Status.UNKNOWN,
                'GODOT_PUBLICATION_RECONCILE_REQUIRED',request.command_id,
                postconditions={'request_digest':request.digest,'public_ack':False,
                                'next_action':'lookup.reconcile'}).as_dict())
        value._journal.unknown.side_effect=make_unknown
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

    def test_lost_return_after_durable_commit_recovers_original_reply(self):
        request,grant,lease,before,record,_=self._inert_save()
        finish=self.value.sessions.finish_effect
        def lose_reply(permit,**kwargs):
            result=finish(permit,**kwargs)
            if permit.phase=='commit':raise OSError('inert return lost after committed journal')
            return result
        self.value.sessions.finish_effect=lose_reply
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertEqual(canonical_bytes(result.as_dict()),self.value._journal.lookup_response.return_value)
        self.value._journal.commit.assert_called_once()
        self.value._journal.unknown.assert_not_called()
        self.assertTrue(self.value._held)
        self.assertEqual(self.value._reply(request.command_id,record),result)

    def test_unsupported_script_is_typed_rejection(self):
        self.value.validation_model=types.SimpleNamespace(factory=types.SimpleNamespace(
            _sibling=lambda name:owner._load(name)))
        with self.assertRaises(owner.PublicationOwnerError) as rejected:
            self.value._qualify_script(b'extends Node3D\nfunc _ready():\n    pass\n')
        self.assertEqual(rejected.exception.code,'GODOT_SCRIPT_PROFILE_REJECTED')

    def _inert_script(self):
        request,grant,lease,before,record,credential=self._inert_save()
        request.operation='script_text.replace'
        request.payload={'text':'extends Node3D\n','expected_sha256':'1'*64}
        value=self.value
        value.contract.SCENE_PATH='scene'
        bundle=value._journal.read_selected_bundle.return_value
        bundle.files={'script':request.payload['text'].encode(),'scene':b'captured scene'}
        value._editor.capture_bytes.return_value=b'captured scene'
        value._retirement_facts=Mock(return_value={})
        value._fresh_adoption_facts=Mock(return_value={'generation_after':2})
        value._editor_parent=Path(self.temp.name)
        value._editor_binary=Path(self.temp.name)/'inert-editor.exe'
        value.editor_model=types.SimpleNamespace(EditorOwner=Mock())
        successor=Mock()
        value.editor_model.EditorOwner.open_selected_generation.return_value=(successor,object())
        return request,grant,lease,before,record,credential,successor

    def _inert_edit(self):
        request,grant,lease,before,record,credential=self._inert_save()
        request.operation='scene.node.update'
        before['working_files']={'scene':{'sha256':'5'*64,'size_bytes':1}}
        self.value._fact_identity=Mock()
        facts={'working_files':before['working_files'],'generation_after':before['generation'],
            'root_after':before['root_instance_id'],'files_saved':False,'live_state_durable':False}
        self.value._editor.observation.return_value=facts
        self.value._journal.lookup.return_value={'phase':'EDIT_READY'}
        def committed(*args,**kwargs):
            self.value._journal.lookup.return_value={'phase':'COMMITTED','receipt_sha256':'8'*64}
        self.value._journal.edit_committed.side_effect=committed
        validated=types.SimpleNamespace(projection={'operation':request.operation})
        self.value._journal.lookup_response.return_value=canonical_bytes(Response(Status.COMMITTED,
            'GODOT_EDITOR_EDITED',request.command_id,postconditions={'request_digest':request.digest,
                'durable_receipt_sha256':'8'*64,'public_ack':True,'files_saved':False,
                'live_state_durable':False,'effect_scope':'editor_session'}).as_dict())
        return request,grant,lease,before,validated,record,credential

    def test_edit_records_checkpoint_before_effect_and_keeps_native_history(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        trace=[]
        self.value._journal.edit_checkpoint.side_effect=lambda *a,**k:trace.append('checkpoint')
        self.value._editor.apply_edit.side_effect=lambda *a,**k:trace.append('edit')
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(trace,['checkpoint','edit'])
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertFalse(result.postconditions['files_saved'])
        self.assertFalse(result.postconditions['live_state_durable'])
        self.value._validator.validate.assert_not_called()
        self.value._editor.adopt.assert_not_called()
        self.value._journal.select_prepared.assert_not_called()

    def test_edit_checkpoint_failure_never_prepares_or_applies_mutation(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        self.value._journal.edit_checkpoint.side_effect=OSError('inert checkpoint barrier')
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.value._editor.prepare_edit.assert_not_called()
        self.value._editor.apply_edit.assert_not_called()
        self.value._journal.edit_committed.assert_not_called()

    def test_stop_before_edit_phase_does_not_send_engine_mutation(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        start=self.value.sessions.start_effect
        def stop_before(permit):
            if permit.phase=='edit':self.value.sessions.stop(grant)
            return start(permit)
        self.value.sessions.start_effect=stop_before
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.value._journal.edit_checkpoint.assert_called_once()
        self.value._editor.prepare_edit.assert_not_called()
        self.value._editor.apply_edit.assert_not_called()

    def test_stop_during_edit_accounts_for_effect_and_requires_reconcile(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        drains=[]
        self.value._editor.apply_edit.side_effect=lambda *a,**k:drains.append(self.value.sessions.stop(grant))
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertEqual(len(drains),1)
        self.assertTrue(drains[0]['draining'])
        self.assertFalse(self.value.sessions.status()['draining'])
        self.value._journal.edit_committed.assert_not_called()

    def test_edit_manual_change_before_receipt_commit_never_acks_stale_observation(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        observation=self.value._editor.observation.return_value
        self.value._editor.observation.side_effect=[observation,owner.PublicationOwnerError('EDITOR_EDIT_NO_LONGER_CURRENT')]
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.value._editor.apply_edit.assert_called_once()
        self.value._journal.edit_committed.assert_not_called()

    def test_edit_lost_return_after_durable_commit_preserves_original_ack(self):
        request,grant,lease,before,validated,record,_=self._inert_edit()
        finish=self.value.sessions.finish_effect
        def lose_return(permit,**kwargs):
            result=finish(permit,**kwargs)
            if permit.phase=='commit':raise OSError('inert reply lost')
            return result
        self.value.sessions.finish_effect=lose_return
        result=self.value._edit(request,grant,lease,before,validated,record)
        self.assertEqual(result.status,Status.COMMITTED)
        self.assertEqual(canonical_bytes(result.as_dict()),self.value._journal.lookup_response.return_value)
        self.value._journal.unknown.assert_not_called()
        self.value._editor.apply_edit.assert_called_once()

    def test_stop_during_retirement_prevents_select_or_new_editor(self):
        request,grant,lease,before,record,_,_=self._inert_script()
        old=self.value._editor
        old.retire_for_replacement.side_effect=lambda *a,**k:self.value.sessions.stop(grant)
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.value._journal.select_prepared.assert_not_called()
        self.value.editor_model.EditorOwner.open_selected_generation.assert_not_called()
        self.assertIn(old,self.value._retired_editors)
        self.assertFalse(self.value.sessions.status()['draining'])

    def test_new_editor_is_retained_before_phase_completion_can_fail(self):
        request,grant,lease,before,record,_,successor=self._inert_script()
        finish=self.value.sessions.finish_effect
        def fail_after_adoption(permit,**kwargs):
            result=finish(permit,**kwargs)
            if permit.phase=='adopt':raise OSError('inert completion failure')
            return result
        self.value.sessions.finish_effect=fail_after_adoption
        old=self.value._editor
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertIs(self.value._editor,successor)
        self.assertIn(old,self.value._retired_editors)
        self.value._journal.commit.assert_not_called()
        self.value.close()
        successor.close.assert_called_once()
        old.close.assert_called_once()

    def test_failed_new_editor_constructor_retains_cleanup_owner_until_close(self):
        request,grant,lease,before,record,_,_=self._inert_script()
        child=Mock()
        error=owner.PublicationOwnerError('GODOT_NEW_EDITOR_FAILED',cleanup_owner=child)
        self.value.editor_model.EditorOwner.open_selected_generation.side_effect=error
        result=self.value._save(request,grant,lease,before,None,record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertIn(child,self.value._cleanup_owners)
        child.close.side_effect=RuntimeError('inert pending cleanup')
        with self.assertRaises(owner.PublicationOwnerError):self.value.close()
        self.assertIn(child,self.value._cleanup_owners)
        child.close.side_effect=None
        self.value.close()
        self.assertEqual(self.value._cleanup_owners,[])

    def _inert_read_owner(self):
        value=self.value
        value.contract=owner._load('contract');value.project_id='project.fixture'
        value.sessions=auth.PublicationSession(value.project_id,Path(self.temp.name),value.contract.CATALOG_DIGEST)
        value._jobs={};value._leases={};value._read_leases={};value._same_release=Mock()
        snapshot={'generation':1,'revision':'sha256:'+'1'*64,'project_revision':'sha256:'+'2'*64,
            'can_undo':False,'can_redo':False,
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

    def test_admission_preserves_last_two_editor_slots_for_save(self):
        snapshot=self._inert_read_owner()
        value=self.value;value.auth_model=auth
        credential=value.sessions.issue()
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':value.contract.CATALOG_DIGEST}
        lease=value.lease({'project_id':value.project_id,'ttl_ms':30000},**arguments)
        value.editor_model=types.SimpleNamespace(MAX_EFFECTS=16)
        value._editor=types.SimpleNamespace(_intents=dict.fromkeys(range(14)))
        value._validator=Mock();value._validator.snapshot.return_value={'attempts':[]}
        value.validation_model=types.SimpleNamespace(MAX_RUNS=10)
        def request(operation,payload):
            payload={'expected_generation':1,'expected_project_revision':snapshot['project_revision'],**payload}
            return Request(command_id='command.budget',project_id=value.project_id,operation=operation,
                lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=snapshot['revision'],
                target={'stable_id':'root'},payload=payload,
                payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                deadline_ms=lease['expires_ms']-1)
        edit=request('scene.node.update',{'changes':{'position':[1,2,3]}})
        with self.assertRaisesRegex(owner.SafetyViolation,'EDITOR_EFFECT_BUDGET_EXHAUSTED'):
            value.submit(edit.as_dict(),**arguments)
        self.assertEqual(value._jobs,{})
        value._save=Mock(return_value=Response(Status.UNKNOWN,'INERT_SAVE','command.budget'))
        save=request('scene.save',{'expected_files':{path:row['sha256'] for path,row in snapshot['working_files'].items()}})
        value.submit(save.as_dict(),**arguments)
        value._save.assert_called_once()

    def test_context_carries_native_undo_and_redo_availability(self):
        snapshot=self._inert_read_owner();snapshot.update(can_undo=True,can_redo=False)
        context=self.value._context(snapshot,types.SimpleNamespace(lease_id='lease.test',fencing_epoch=1,expires_ms=123))
        self.assertTrue(context.can_undo)
        self.assertFalse(context.can_redo)

    def test_edit_requires_remaining_validation_capacity_for_save(self):
        snapshot=self._inert_read_owner()
        value=self.value;value.auth_model=auth
        credential=value.sessions.issue()
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':value.contract.CATALOG_DIGEST}
        lease=value.lease({'project_id':value.project_id,'ttl_ms':30000},**arguments)
        value.editor_model=types.SimpleNamespace(MAX_EFFECTS=16)
        value._editor=types.SimpleNamespace(_intents={})
        value._validator=Mock();value._validator.snapshot.return_value={'attempts':[1,2,3,4]}
        value.validation_model=types.SimpleNamespace(MAX_RUNS=4)
        value._edit=Mock(return_value=Response(Status.UNKNOWN,'INERT_EDIT','command.capacity'))
        payload={'expected_generation':1,'expected_project_revision':snapshot['project_revision'],
            'changes':{'position':[1,2,3]}}
        request=Request(command_id='command.capacity',project_id=value.project_id,operation='scene.node.update',
            lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=snapshot['revision'],
            target={'stable_id':'root'},payload=payload,
            payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),deadline_ms=lease['expires_ms']-1)
        with self.assertRaisesRegex(owner.SafetyViolation,'GODOT_VALIDATION_BUDGET_EXHAUSTED'):
            value.submit(request.as_dict(),**arguments)
        value._edit.assert_not_called()
        self.assertEqual(value._jobs,{})
        value._validator.snapshot.return_value={'attempts':[1,2,3]}
        value.submit(request.as_dict(),**arguments)
        value._edit.assert_called_once()

    def test_idle_stop_persists_once_off_the_control_lane(self):
        self._inert_read_owner()
        value=self.value;value._journal=Mock();value._journal.snapshot.return_value={'stopped':False}
        entered=threading.Event();release=threading.Event()
        def persist(**kwargs):
            entered.set()
            if not release.wait(2):raise TimeoutError('inert stop barrier')
            value._journal.snapshot.return_value={'stopped':True}
        value._journal.stop.side_effect=persist
        credential=value.sessions.issue()
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':value.contract.CATALOG_DIGEST}
        body={'project_id':value.project_id,'command_id':'control.stop'}
        try:
            result=value.stop(body,**arguments)
            self.assertTrue(result['stopped'])
            self.assertEqual(result['stop_persistence'],'PENDING')
            self.assertTrue(entered.wait(1))
            value.stop(body,**arguments)
            self.assertEqual(value._journal.stop.call_count,1)
        finally:
            release.set();value._stop_thread.join(3)
        self.assertFalse(value._stop_thread.is_alive())
        self.assertEqual(value.stop(body,**arguments)['stop_persistence'],'DURABLE')

    def test_stop_barrier_failure_stays_unknown_and_retains_resources(self):
        self._inert_read_owner()
        value=self.value;value._journal=Mock();value._journal.snapshot.return_value={'stopped':False}
        value._journal.stop.side_effect=OSError('inert barrier failure')
        credential=value.sessions.issue()
        value.stop({'project_id':value.project_id,'command_id':'control.stop'},
            authorization='Bearer '+credential.bearer,catalog_digest=value.contract.CATALOG_DIGEST)
        value._stop_thread.join(3)
        self.assertEqual(value._stop_persistence,'UNKNOWN')
        self.assertTrue(value._held)
        self.assertIsNotNone(value._journal)

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
        self.value._journal=Mock()
        self.value._journal.snapshot.return_value={'stopped':False}
        def persist_stop(**kwargs):
            self.value._journal.snapshot.return_value={'stopped':True}
        self.value._journal.stop.side_effect=persist_stop
        credential=self.value.sessions.issue()
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':self.value.contract.CATALOG_DIGEST}
        stopped=self.value.stop({'project_id':self.value.project_id,'command_id':'control.stop'},**arguments)
        self.value._stop_thread.join(3)
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

    def test_preview_only_read_lease_returns_diff_without_editor_or_journal_effect(self):
        snapshot=self._inert_read_owner()
        source=b'extends Node3D\n@export var fixture_value: int = 7\n'
        digest=hashlib.sha256(source).hexdigest()
        snapshot['working_files'][self.value.contract.SCRIPT_PATH]['sha256']=digest
        self.value._editor=Mock()
        self.value._journal=Mock()
        self.value._journal.read_selected_bundle.return_value=types.SimpleNamespace(
            files={self.value.contract.SCRIPT_PATH:source})
        self.value.validation_model=types.SimpleNamespace(factory=types.SimpleNamespace(
            _sibling=lambda name:owner._load(name)))
        credential=self.value.sessions.issue(operations=frozenset({'scene.preview'}))
        arguments={'authorization':'Bearer '+credential.bearer,'catalog_digest':self.value.contract.CATALOG_DIGEST}
        lease=self.value.lease({'project_id':self.value.project_id,'ttl_ms':10000},**arguments)
        self.value.sessions.halt()
        payload={'expected_generation':1,'expected_project_revision':snapshot['project_revision'],
            'operation':'script_text.replace','target':{'path':self.value.contract.SCRIPT_PATH},
            'payload':{'expected_generation':1,'expected_project_revision':snapshot['project_revision'],
                'expected_sha256':digest,'text':'extends Node3D\n@export var fixture_value: int = 9\n'}}
        request=Request(command_id='command.preview',project_id=self.value.project_id,operation='scene.preview',
            lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=snapshot['revision'],
            target={'stable_id':'root'},payload=payload,
            payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),deadline_ms=lease['expires_ms']-1)
        response=self.value.submit(request.as_dict(),**arguments)
        self.assertEqual(response.code,'GODOT_PREVIEW_READY')
        self.assertIn('+@export var fixture_value: int = 9\n',
            response.postconditions['diff'][0]['unified_diff'])
        self.assertFalse(response.postconditions['changes_applied'])
        self.assertFalse(response.postconditions['runtime_authorized'])
        self.assertEqual(self.value._jobs,{})
        self.assertEqual(self.value._editor.mock_calls,[])
        self.value._journal.capture_prepared.assert_not_called()


if __name__=='__main__':unittest.main()
