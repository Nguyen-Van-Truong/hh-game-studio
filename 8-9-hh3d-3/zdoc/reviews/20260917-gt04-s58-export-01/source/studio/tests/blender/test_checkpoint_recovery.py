"""Recovery grants/readback guards without loading Blender or native storage."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender import recovery_owner as recovery
from studio.host.blender.ui_host import BlenderUIHost,HostError,ipc
from studio.protocol.core import canonical_bytes
from studio.host.core.safe_open import FileIdentity

class SeedTests(unittest.TestCase):
    def tearDown(self):recovery._SEEDS.clear()
    def test_forged_seed_has_no_authority(self):
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED_SEED'):recovery._claim_seed(recovery._Seed())
    def test_registered_seed_is_consumed_once_and_descriptor_is_copied(self):
        seed=recovery._Seed();original={'readonly':True}
        recovery._SEEDS[id(seed)]=(seed,b'checkpoint',canonical_bytes(original))
        raw,descriptor=recovery._claim_seed(seed);descriptor['readonly']=False
        self.assertEqual(raw,b'checkpoint');self.assertTrue(original['readonly'])
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED_SEED'):recovery._claim_seed(seed)
    def test_new_seed_cannot_copy_registration(self):
        seed=recovery._Seed();other=recovery._Seed();recovery._SEEDS[id(other)]=(seed,b'checkpoint',b'{}')
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED_SEED'):recovery._claim_seed(other)

class BoundaryTests(unittest.TestCase):
    def test_publication_dictionary_rejected_before_readback(self):
        with self.assertRaisesRegex(recovery.RecoveryError,'READONLY_PUBLICATION'):
            recovery._descriptor({'path':'C:/foreign.blend'},None)
    def test_live_predecessor_cannot_authorize_recovery(self):
        gui=object.__new__(BlenderUIHost);gui._session='a'*32;gui._closed=False
        with self.assertRaisesRegex(recovery.RecoveryError,'CLOSED_PREDECESSOR'):recovery._retired(gui,'a'*32)
    def test_predecessor_job_zero_and_actual_exit_both_required(self):
        gui=object.__new__(BlenderUIHost);gui._session='a'*32;gui._closed=True;gui.pid=12
        gui._process=Mock();gui._process.poll.return_value=0
        gui._cleanup={'closed':True,'actual_process_exit':None,'wrapper_exit_code':0,
            'job':{'zero_observed':True,'active_count':0,'closed':True,'handle_retained':False}}
        with self.assertRaisesRegex(recovery.RecoveryError,'PREDECESSOR_EXIT'):recovery._retired(gui,'a'*32)
        gui._cleanup['actual_process_exit']={'pid':12,'exit_code':0};recovery._retired(gui,'a'*32)
        gui._cleanup['job']['active_count']=1
        with self.assertRaisesRegex(recovery.RecoveryError,'PREDECESSOR_EXIT'):recovery._retired(gui,'a'*32)
    def test_host_readonly_blocks_edit_and_lease_before_any_native_request(self):
        gui=object.__new__(BlenderUIHost);gui._recovery_readonly=True;gui._ask=Mock()
        with self.assertRaisesRegex(HostError,'RECOVERY_READONLY'):gui.arm_lease({'fencing_epoch':1,'expires_ms':99})
        for operation in ('mesh.create_box','history.undo','export.prepare','checkpoint.save'):
            with self.assertRaisesRegex(HostError,'RECOVERY_READONLY'):gui.submit({'operation':operation})
        gui._ask.assert_not_called()
    def test_native_readonly_gate_rejects_edit_and_lease(self):
        client=object.__new__(ipc.Client);client.recovery={'readonly':True};client.welcomed={'data','control'}
        client.owner=Mock();client.ui=Mock();client.ui.c.Rejected=type('Rejected',(ValueError,),{})
        client.channels={'data':Mock(),'control':Mock()}
        client.dispatch('data',{'kind':'submit','sequence':1,'body':{'command':{'operation':'mesh.create_box'},'ttl_ms':1000}})
        client.dispatch('control',{'kind':'lease','sequence':1,'body':{'lease':{}}})
        client.owner.queue.submit.assert_not_called();client.owner.queue.arm_lease.assert_not_called()
        self.assertFalse(client.channels['data'].queue.call_args.args[1]['ok'])
        self.assertFalse(client.channels['control'].queue.call_args.args[1]['ok'])
    def test_input_descriptor_rejects_path_field_before_filesystem(self):
        client=object.__new__(ipc.Client)
        with self.assertRaises(ipc.IPCError):client.load_checkpoint({'path':'C:/foreign.blend'})
    def test_recovery_initialize_preserves_loaded_scene(self):
        client=object.__new__(ipc.Client);client.recovery={'readonly':True};client.owner=object()
        client.bpy=Mock();client.initialize();client.bpy.data.objects.remove.assert_not_called()
    def test_failed_gui_constructor_retains_exact_cleanup_owner(self):
        failed=object.__new__(BlenderUIHost);failed.close=Mock(side_effect=[OSError('retained handle'),None])
        error=HostError('BLENDER_HELD',cleanup_owner=failed)
        with patch.object(recovery,'_descriptor',return_value=(b'checkpoint',{'readonly':True})),\
                patch.object(BlenderUIHost,'__init__',side_effect=error):
            with self.assertRaises(recovery.RecoveryError) as caught:
                recovery.CheckpointRecoveryOwner.open(Path('owned'),binary=Path('blender.exe'),publication=None,predecessor=None)
        owner=caught.exception.cleanup_owner;self.assertIs(owner._host,failed);self.assertFalse(owner._closed)
        owner.close();self.assertTrue(owner._closed);self.assertFalse(recovery._SEEDS)

class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.descriptor={'schema':recovery.SCHEMA,'checkpoint_sha256':'a'*64,'source_sha256':'b'*64,
            'revision':'sha256:'+'c'*64,'snapshot_native_json':'{"value":2.0}','context':{'mode':'OBJECT'},
            'profile':{'objects':1},'readonly':True,'public_ack':False}
        self.observed=dict(self.descriptor,pid=123,descriptor_sha256='d'*64,undo_history_restored=False)
    def test_exact_authenticated_readback_fields(self):
        recovery.validate_observation(self.observed,self.descriptor,pid=123,descriptor_sha256='d'*64)
    def test_pid_scene_descriptor_grants_and_undo_claim_tamper_rejected(self):
        for field,value in (('pid',124),('snapshot_native_json','{"value":2}'),('descriptor_sha256','e'*64),
                ('readonly',False),('public_ack',True),('undo_history_restored',True),('profile',{'objects':2})):
            changed=copy.deepcopy(self.observed);changed[field]=value
            with self.assertRaisesRegex(recovery.RecoveryError,'READBACK_MISMATCH'):
                recovery.validate_observation(changed,self.descriptor,pid=123,descriptor_sha256='d'*64)

class StagingCleanupTests(unittest.TestCase):
    class Api:
        def __init__(self,*,write_error=False,close_error=False):
            self.owned=set();self.data={};self.next=1;self.write_error=write_error;self.close_error=close_error
        def mkdir(self,path):path.mkdir()
        def open(self,path,**kwargs):
            handle=self.next;self.next+=1;self.owned.add(handle);self.data[handle]=b'';return handle
        def check_security(self,handle):assert handle in self.owned
        def inspect(self,handle,path,**kwargs):return FileIdentity(1,'%032x'%handle,len(self.data[handle]))
        def write(self,handle,raw):
            if self.write_error:raise OSError('injected staging write failure')
            self.data[handle]=raw
        def flush(self,handle):assert handle in self.owned
        def read(self,handle,cap):return self.data[handle]
        def close(self,handle):
            if self.close_error:raise OSError('injected retained close failure')
            self.owned.remove(handle)
        def close_owned(self):
            failed=False
            for handle in tuple(self.owned):
                try:self.close(handle)
                except OSError:failed=True
            if failed:raise OSError('retained exact staging API handles')
    def host(self,directory,api):
        host=object.__new__(BlenderUIHost);host.directory=Path(directory);host._api=api;host._source={}
        host._closed=host._held=False;host._stopped=False;host._root=None;host._process=None;host._job=None
        host.channels={};host.listeners={};host.threads=[];host._export_job=None;host._cleanup=None
        host._done=threading.Event();host._overflow=threading.Event();host._close_lock=threading.Lock()
        host._export_lock=threading.Lock();host._key=b''
        return host
    def descriptor(self,raw):return {'checkpoint_sha256':hashlib.sha256(raw).hexdigest(),
        'source_sha256':hashlib.sha256(canonical_bytes({})).hexdigest(),'binary_sha256':recovery.BLENDER_SHA256}
    def test_intermediate_write_failure_keeps_parent_registered_until_host_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            api=self.Api(write_error=True);host=self.host(directory,api)
            with self.assertRaisesRegex(OSError,'staging write'):host._prepare_recovery_input(b'checkpoint',self.descriptor(b'checkpoint'))
            self.assertEqual(api.owned,{1})  # File handle closed; parent remains in the native API registry.
            host.close();self.assertFalse(api.owned);self.assertTrue(host._closed)
    def test_intermediate_close_failure_retains_file_and_parent_for_exact_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            api=self.Api(close_error=True);host=self.host(directory,api)
            with self.assertRaisesRegex(OSError,'retained close'):host._prepare_recovery_input(b'checkpoint',self.descriptor(b'checkpoint'))
            self.assertEqual(api.owned,{1,2})
            with self.assertRaisesRegex(OSError,'exact staging'):host.close()
            self.assertFalse(host._closed);self.assertEqual(api.owned,{1,2})
            api.close_error=False;host.close();self.assertFalse(api.owned);self.assertTrue(host._closed)

if __name__=='__main__':unittest.main()
