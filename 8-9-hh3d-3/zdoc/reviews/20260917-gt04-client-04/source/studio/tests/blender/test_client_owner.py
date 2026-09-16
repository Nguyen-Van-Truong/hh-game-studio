"""Facade semantics with an explicit inert native double; no engine launched."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender import client_owner as module
from studio.host.blender.client_owner import BlenderClientOwner
from studio.host.blender.ui_host import BlenderUIHost
from studio.host.blender import client_catalog as catalog
from studio.protocol.core import Request,Response,Status,canonical_bytes
from studio.host.core.transport import epoch_ms
from studio.host.core.limits import SafetyViolation
from test_client_catalog import request_body

class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.sources=patch.object(module,'source_files',return_value={'owned.py':'a'*64});self.sources.start();self.addCleanup(self.sources.stop)
        self.host=object.__new__(BlenderUIHost);host=self.host
        host._process=Mock();host._process.poll.return_value=None;host._job=Mock()
        host._job.active_count.return_value=2
        host._job.snapshot.return_value={'assigned':True,'configured':True,'tainted':False,'closed':False,
            'handle_retained':True,'active_count':2}
        host.pid=12;host._session='a'*32;host._source={'owned.py':'a'*64};host._closed=host._held=host._stopped=False
        host._deadline=time.monotonic()+90;host.directory=Path(self.directory.name)
        snapshot={'schema':'HH-BLENDER-FIXTURE-SCENE-1','objects':[],'units':{'system':'METRIC','scale_length':1.0}}
        self.scene={'snapshot':snapshot,'revision':module.queue.c.digest(snapshot),
            'context':{'mode':'OBJECT','active_id':None,'selected_ids':[]},'public_ack':False,'undo_supported':True}
        def native(command,**kwargs):
            return {'state':'COMPLETED','command_id':command['command_id'],'command_digest':module.queue.c.digest(command),
                'result':copy.deepcopy(self.scene),'public_ack':False}
        self.native=native;host.submit=Mock(side_effect=native);host._ask=Mock()
        def stop():host._stopped=True;return {'stopped':True,'public_ack':False}
        host.stop=Mock(side_effect=stop)
        self.owner=BlenderClientOwner.from_host(host,project_id='blender.test')
        self.credential=self.owner.sessions.issue();self.auth='Bearer '+self.credential.bearer
        self.kw=dict(authorization=self.auth,catalog_digest=catalog.CATALOG_DIGEST)
        self.lease=self.owner.lease({'project_id':'blender.test','ttl_ms':10000,'access':'read'},**self.kw)
        host.submit.reset_mock()
    def body(self,**changes):
        values=dict(expected_revision=self.owner.revision,lease_id=self.lease['lease_id'],deadline_ms=epoch_ms()+1800)
        values.update(changes);return request_body(**values)
    def submit(self,**changes):return self.owner.submit(self.body(**changes),**self.kw)
    def lookup(self,key='read.1',**kwargs):
        return self.owner.lookup({'project_id':'blender.test','command_id':key},**(kwargs or self.kw))
    def test_exact_host_type_and_duplicate_registration(self):
        with self.assertRaisesRegex(SafetyViolation,'EXACT_HOST'):BlenderClientOwner.from_host({'pid':12})
        with self.assertRaisesRegex(SafetyViolation,'ALREADY_REGISTERED'):BlenderClientOwner.from_host(self.host)
        self.host.submit.assert_not_called()
    def test_discovery_and_read_lease_are_read_only_common_contract(self):
        value=self.owner.discover({'project_id':'blender.test'},**self.kw)
        self.assertEqual(value.schema_digest,catalog.CATALOG_DIGEST);self.assertEqual(len(value.capabilities),1)
        self.assertEqual(value.capabilities[0].write_scopes,());self.assertEqual(self.lease['revision'],self.owner.revision)
        with self.assertRaisesRegex(SafetyViolation,'READ_ONLY'):
            self.owner.lease({'project_id':'blender.test','ttl_ms':1000,'access':'write'},**self.kw)
        self.host.submit.assert_not_called()
    def test_read_observation_hash_native_revision_and_volatile_flags(self):
        value=self.submit();self.assertEqual(value.status,Status.COMMITTED)
        self.assertEqual(value.result_revision,self.scene['revision'])
        self.assertEqual(value.result_hash,module.digest(canonical_bytes(value.postconditions['observation'])))
        self.assertEqual(value.postconditions['hash_domain'],'jcs-observation-v1')
        self.assertFalse(value.postconditions['public_ack']);self.assertFalse(value.postconditions['durable'])
        self.assertTrue(value.postconditions['read_only']);self.assertEqual(self.host.submit.call_count,1)
        self.assertEqual(self.owner.sessions.encode_output(value.as_dict()),canonical_bytes(value.as_dict()))
    def test_sensitive_native_names_are_withheld_before_successful_publication(self):
        for index,name in enumerate(('C:/private/item','/private/item',self.credential.bearer)):
            # Supply the inert native registration baseline for this scene.
            self.scene['snapshot']['objects']=[{'name':name,'mesh_name':'safe'}]
            self.scene['revision']=module.queue.c.digest(self.scene['snapshot'])
            self.owner._baseline=canonical_bytes(self.scene);self.owner.revision=self.scene['revision']
            value=self.submit(command_id='sensitive.'+str(index))
            self.assertEqual(value.status,Status.REJECTED);self.assertEqual(value.code,'BLENDER_SENSITIVE_OBSERVATION')
            self.assertNotIn('observation',value.postconditions)
            self.assertIsNone(self.owner._active);self.assertIsNone(self.owner.sessions._active)
            self.assertEqual(self.lookup('sensitive.'+str(index)),value)
    def test_duplicate_and_lookup_exact_detached_responses(self):
        first=self.submit();wire=canonical_bytes(first.as_dict())
        first.postconditions['observation']['scene']['snapshot']['objects'].append({'evil':True})
        self.assertEqual(canonical_bytes(self.submit().as_dict()),wire)
        self.assertEqual(canonical_bytes(self.lookup().as_dict()),wire);self.assertEqual(self.host.submit.call_count,1)
    def test_changed_duplicate_conflicts_without_native_effect(self):
        self.submit();value=self.submit(operation='mesh.create_box')
        self.assertEqual(value.code,'COMMAND_CONFLICT');self.assertEqual(self.host.submit.call_count,1)
    def test_lookup_is_scoped_to_issuer_session(self):
        self.submit();second=self.owner.sessions.issue()
        value=self.lookup(authorization='Bearer '+second.bearer,catalog_digest=catalog.CATALOG_DIGEST)
        self.assertEqual(value.code,'COMMAND_NOT_FOUND')
    def test_rotation_keeps_own_history_but_invalidates_old_auth(self):
        before=self.submit();rotated=self.owner.sessions.rotate(self.credential)
        with self.assertRaises(SafetyViolation):self.lookup()
        value=self.lookup(authorization='Bearer '+rotated.bearer,catalog_digest=catalog.CATALOG_DIGEST)
        self.assertEqual(value,before)
    def test_bad_catalog_project_and_auth_have_no_native_effect(self):
        for kw in ({'authorization':'Bearer invalid','catalog_digest':catalog.CATALOG_DIGEST},
                   {'authorization':self.auth,'catalog_digest':'sha256:'+'0'*64}):
            with self.assertRaises(SafetyViolation):self.owner.submit(self.body(),**kw)
        with self.assertRaises(SafetyViolation):self.submit(project_id='other')
        self.host.submit.assert_not_called()
    def test_unsupported_mutating_and_open_lane_are_explicit(self):
        for op,code in [('mesh.create_box','UNSUPPORTED_OPERATION'),('open_lane.python','UNSUPPORTED_OPEN_LANE')]:
            self.assertEqual(self.submit(command_id=op,operation=op).code,code)
        self.host.submit.assert_not_called()
    def test_request_digest_target_and_schema_rejected_without_native_effect(self):
        for field,value in [('digest','sha256:'+'0'*64),('payload_hash','sha256:'+'0'*64),
                            ('schema_version','wrong'),('target',{'path':'foreign.blend'})]:
            body=self.body();body[field]=value
            self.assertEqual(self.owner.submit(body,**self.kw).status,Status.REJECTED)
        self.host.submit.assert_not_called()
    def test_stale_revision_and_invalid_read_lease_reject(self):
        self.assertEqual(self.submit(expected_revision='sha256:'+'0'*64).code,'BLENDER_STALE_REVISION')
        self.assertEqual(self.submit(command_id='bad-lease',lease_id='read.forged').code,'BLENDER_READ_LEASE_REQUIRED')
        self.host.submit.assert_not_called()
    def test_expired_deadline_has_no_native_effect(self):
        self.assertEqual(self.submit(deadline_ms=epoch_ms()-1).code,'BLENDER_DEADLINE_EXPIRED')
        self.host.submit.assert_not_called()
    def test_source_drift_blocks_read_but_stop_remains_available(self):
        self.host._source={'changed.py':'b'*64}
        self.assertEqual(self.submit().code,'BLENDER_SOURCE_CHANGED');self.host.submit.assert_not_called()
        stopped=self.owner.stop({'project_id':'blender.test','command_id':'stop'},**self.kw)
        self.assertEqual(stopped.status,Status.COMMITTED);self.host.stop.assert_called_once()
    def test_pid_generation_and_job_rechecked_before_read(self):
        for change in ('pid','generation','job'):
            with self.subTest(change=change):
                self.host.pid=12;self.host._session='a'*32;self.host._job.snapshot.return_value['active_count']=2
                if change=='pid':self.host.pid=13
                if change=='generation':self.host._session='b'*32
                if change=='job':self.host._job.snapshot.return_value['active_count']=0
                self.assertEqual(self.submit(command_id=change).status,Status.REJECTED)
        self.host.submit.assert_not_called()
    def test_source_pid_and_revision_drift_during_read_not_exposed(self):
        def native(command,**kwargs):
            result=self.native(command,**kwargs);self.host.pid=13;return result
        self.host.submit.side_effect=native
        value=self.submit();self.assertEqual(value.code,'BLENDER_OWNER_IDENTITY_CHANGED')
        self.assertNotIn('observation',value.postconditions)
    def test_manual_scene_change_after_registration_is_stale(self):
        self.scene['revision']='sha256:'+'0'*64
        self.assertEqual(self.submit().code,'BLENDER_STALE_REVISION')
    def test_deadline_expiring_during_read_not_exposed(self):
        deadline=epoch_ms()+1500
        def native(command,**kwargs):
            result=self.native(command,**kwargs)
            changed=patch.object(module,'epoch_ms',return_value=deadline+1);changed.start();self.addCleanup(changed.stop)
            return result
        self.host.submit.side_effect=native
        self.assertEqual(self.submit(deadline_ms=deadline).code,'BLENDER_DEADLINE_EXPIRED')
    def test_revoke_during_read_does_not_release_scene(self):
        def native(command,**kwargs):
            result=self.native(command,**kwargs);self.owner.sessions.revoke(self.credential);return result
        self.host.submit.side_effect=native
        value=self.submit();self.assertEqual(value.status,Status.REJECTED);self.assertNotIn('observation',value.postconditions)
    def test_native_ambiguous_read_is_unknown_and_not_replayed(self):
        self.host.submit.side_effect=RuntimeError('private native detail')
        value=self.submit();self.assertEqual(value.status,Status.UNKNOWN)
        self.assertNotIn('private native detail',canonical_bytes(value.as_dict()).decode())
        self.assertEqual(self.submit(),value);self.assertEqual(self.host.submit.call_count,1)
    def test_pending_native_timeout_holds_further_native_admission(self):
        def native(command,**kwargs):
            return {'state':'PENDING'}
        self.host.submit.side_effect=native
        self.host._ask.side_effect=SafetyViolation('BLENDER_DEADLINE_EXPIRED')
        first=self.submit();self.assertEqual(first.code,'BLENDER_DEADLINE_EXPIRED')
        self.assertTrue(self.owner._held);self.assertIsNone(self.owner._active)
        self.assertEqual(self.submit(command_id='later').code,'BLENDER_OWNER_HELD_OR_STOPPED')
        self.assertEqual(self.submit(),first);self.assertEqual(self.host.submit.call_count,1)
    def test_unexpected_final_native_check_records_unknown_and_releases_pending(self):
        original=self.owner._check_native;calls=[]
        def check(**kwargs):
            calls.append(None)
            if len(calls)==5:raise OSError('private job query detail')
            return original(**kwargs)
        with patch.object(self.owner,'_check_native',side_effect=check):value=self.submit()
        self.assertEqual(len(calls),5);self.assertEqual(value.status,Status.UNKNOWN)
        self.assertEqual(self.lookup(),value);self.assertIsNone(self.owner._active)
        self.assertIsNone(self.owner.sessions._active);self.assertTrue(self.owner._held)
        self.assertNotIn('private job query detail',canonical_bytes(value.as_dict()).decode())
        self.assertEqual(self.submit(),value);self.assertEqual(self.host.submit.call_count,1)
    def test_unexpected_native_stop_records_unknown_and_has_no_pending_latch(self):
        self.host.stop.side_effect=RuntimeError('private stop detail')
        value=self.owner.stop({'project_id':'blender.test','command_id':'stop'},**self.kw)
        self.assertEqual(value.status,Status.UNKNOWN);self.assertFalse(self.owner._stop_pending)
        retry=self.owner.stop({'project_id':'blender.test','command_id':'stop'},**self.kw)
        self.assertEqual(retry,value);self.host.stop.assert_called_once()
        self.assertNotIn('private stop detail',canonical_bytes(value.as_dict()).decode())
    def _assert_publication_precedes_invalidation(self,operation):
        publishing=threading.Event();release=threading.Event();invalidating=threading.Event()
        completed=threading.Event();replies=[];errors=[]
        test=self
        class GatedRows(dict):
            def __getitem__(self,key):
                publishing.set();test.assertTrue(release.wait(2));return super().__getitem__(key)
        self.owner._records=GatedRows(self.owner._records)
        grant=self.owner.sessions.authenticate(self.auth)
        def run_read():
            try:replies.append(self.submit())
            except Exception as error:errors.append(error)
        def run_invalidation():
            try:
                invalidating.set()
                if operation=='stop':self.owner.sessions.stop(grant)
                else:self.owner.sessions.revoke(self.credential)
                completed.set()
            except Exception as error:errors.append(error)
        reader=threading.Thread(target=run_read);invalidator=threading.Thread(target=run_invalidation)
        reader.start()
        try:
            self.assertTrue(publishing.wait(1));invalidator.start();self.assertTrue(invalidating.wait(1))
            self.assertFalse(completed.wait(.05),'invalidation bypassed the response publication guard')
        finally:
            release.set();reader.join(2)
            if invalidator.ident is not None:invalidator.join(2)
        self.assertFalse(reader.is_alive());self.assertFalse(invalidator.is_alive())
        self.assertEqual(errors,[]);self.assertTrue(completed.is_set())
        self.assertEqual(replies[0].status,Status.COMMITTED)
        self.assertIsNone(self.owner._active);self.assertIsNone(self.owner.sessions._active)
    def test_stop_cannot_overtake_response_publication(self):
        self._assert_publication_precedes_invalidation('stop')
    def test_revoke_cannot_overtake_response_publication(self):
        self._assert_publication_precedes_invalidation('revoke')
    def test_stop_is_independent_of_native_wait_and_preserves_lookup(self):
        entered=threading.Event();release=threading.Event();replies=[]
        def native(command,**kwargs):
            entered.set();self.assertTrue(release.wait(2));return self.native(command,**kwargs)
        self.host.submit.side_effect=native
        worker=threading.Thread(target=lambda:replies.append(self.submit()));worker.start()
        try:
            self.assertTrue(entered.wait(1));pending=self.lookup();self.assertEqual(pending.status,Status.ACCEPTED_PENDING)
            before=time.monotonic();stopped=self.owner.stop({'project_id':'blender.test','command_id':'stop'},**self.kw)
            self.assertLess(time.monotonic()-before,.3);self.assertEqual(stopped.status,Status.COMMITTED)
        finally:release.set();worker.join(2)
        self.assertFalse(worker.is_alive());self.assertEqual(replies[0].status,Status.CANCELED)
        self.assertEqual(self.lookup(),replies[0]);self.assertFalse(self.owner.discover({'project_id':'blender.test'},**self.kw).capabilities)
    def test_pending_duplicate_and_busy_read_have_no_second_dispatch(self):
        entered=threading.Event();release=threading.Event();replies=[]
        def native(command,**kwargs):entered.set();release.wait(2);return self.native(command,**kwargs)
        self.host.submit.side_effect=native
        worker=threading.Thread(target=lambda:replies.append(self.submit()));worker.start()
        try:
            self.assertTrue(entered.wait(1));self.assertEqual(self.submit().status,Status.ACCEPTED_PENDING)
            self.assertEqual(self.submit(command_id='read.2').code,'BLENDER_READ_BUSY')
        finally:release.set();worker.join(2)
        self.assertEqual(self.host.submit.call_count,1);self.assertEqual(replies[0].status,Status.COMMITTED)
    def test_budget_is_bounded_without_eviction(self):
        for index in range(catalog.MAX_COMMANDS):self.assertEqual(self.submit(command_id='r'+str(index)).status,Status.COMMITTED)
        self.assertEqual(self.submit(command_id='over').code,'BLENDER_COMMAND_LIMIT')
        self.assertEqual(self.lookup('r0').status,Status.COMMITTED);self.assertEqual(self.host.submit.call_count,catalog.MAX_COMMANDS)

if __name__=='__main__':unittest.main()
