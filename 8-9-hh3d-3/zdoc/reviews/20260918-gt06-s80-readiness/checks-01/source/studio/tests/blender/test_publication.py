"""Interrupted publication prefixes and exact managed response invariants."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,MagicMock
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender import publication_state as model
from studio.host.blender.publication_owner import BlenderPublicationOwner
from studio.protocol.core import canonical_bytes

def request():
    return {'schema':model.SCHEMA,'command_id':'publish','expected_revision':'sha256:'+'1'*64,
        'expected_context':{'mode':'OBJECT','active_id':None,'selected_ids':[]}}
def descriptor(number):
    identity={'volume':'1','file_id':('%032x'%number),'size':8};sha='%064x'%number
    return {'object_id':'blob-'+('%032x'%number),'identity':identity,'sha256':sha,
        'file_version':{'identity':dict(identity,file_id='%032x'%(number+10)),'sha256':sha}}
def events():
    req=request();digest=model.sha(canonical_bytes(req))
    config={'schema':model.SCHEMA,'kind':'CONFIG','generation':'a'*32,'source_sha256':'b'*64,'binary_sha256':'c'*64}
    intent={'schema':model.SCHEMA,'kind':'INTENT','request':req,'request_sha256':digest,'lease_epoch':1}
    staged={'schema':model.SCHEMA,'kind':'STAGED','command_id':'publish','request_sha256':digest,
        'manifest':descriptor(3),'artifacts':dict(zip(model.NAMES,(descriptor(1),descriptor(2))))}
    selected=model.selection(staged)
    selecting={'schema':model.SCHEMA,'kind':'SELECTING','selector':selected}
    result=model.response(intent,staged,selected)
    terminal={'schema':model.SCHEMA,'kind':'TERMINAL','response':result,'response_sha256':model.sha(canonical_bytes(result)),
        'selector_version':{'identity':{'volume':'1','file_id':'f'*32,'size':len(canonical_bytes(selected))},
            'sha256':model.sha(canonical_bytes(selected))}}
    return [config,intent,staged,selecting,terminal]
def replay(rows):
    state={}
    for row in rows:state=model.reduce(state,row)
    return state

class PublicationTests(unittest.TestCase):
    def test_native_snapshot_revision_survives_jcs_integral_float_normalization(self):
        native={'location':[2.0,-3.0,4.0],'faces':[[0,1,2]],'metallic':0.0}
        revision=model.queue.c.digest(native);wire=model.snapshot_wire(native,revision)
        stored=model.parse_json(canonical_bytes({'snapshot':native,'snapshot_native_json':wire}))
        self.assertNotEqual(model.queue.c.digest(stored['snapshot']),revision)
        self.assertEqual(model.check_snapshot_wire(stored['snapshot_native_json'],stored['snapshot'],revision),native)
    def test_native_snapshot_wire_rejects_revision_content_and_format_changes(self):
        native={'location':[2.0,-3.0,4.0]};revision=model.queue.c.digest(native)
        wire=model.snapshot_wire(native,revision)
        for text,snapshot,digest in ((wire,{'location':[2,3,4]},revision),
                (wire,native,'sha256:'+'0'*64),(wire+' ',native,revision)):
            with self.assertRaises(model.PublicationError):model.check_snapshot_wire(text,snapshot,digest)
    def test_no_incomplete_prefix_can_return_committed(self):
        rows=events()
        for count in range(1,5):
            owner=BlenderPublicationOwner();owner._refresh=Mock(return_value=replay(rows[:count]))
            response=owner.lookup_bytes('publish')
            if count==1:self.assertIsNone(response)
            else:self.assertIn(b'"status":"UNKNOWN"',response)
        owner=BlenderPublicationOwner();owner._refresh=Mock(return_value=replay(rows))
        self.assertEqual(owner.lookup_bytes('publish'),canonical_bytes(rows[-1]['response']))
    def test_foreign_path_and_edit_mode_before_owner_access(self):
        owner=BlenderPublicationOwner();owner.lookup_bytes=Mock(side_effect=AssertionError('no owner effects'))
        for req in (dict(request(),path='C:/foreign.blend'),dict(request(),expected_context={'mode':'EDIT_MESH','active_id':'box','selected_ids':['box']})):
            with self.assertRaises((model.PublicationError,ValueError)):owner.publish(req,None)
        owner.lookup_bytes.assert_not_called()
    def test_direct_commit_without_staging_and_selector_is_rejected(self):
        rows=events()
        with self.assertRaises(model.PublicationError):replay(rows[:2]+rows[-1:])
    def test_terminal_response_and_file_version_are_bound(self):
        for field in ('public_ack','hash','version'):
            rows=events()
            if field=='public_ack':rows[-1]['response']['public_ack']=True
            elif field=='hash':rows[-1]['response_sha256']='0'*64
            else:rows[-1]['selector_version']['sha256']='0'*64
            with self.assertRaises(model.PublicationError):replay(rows)
    def test_blob_mirror_cannot_replace_protected_file_version(self):
        rows=events();del rows[2]['artifacts']['scene.glb']['file_version']
        with self.assertRaises(model.PublicationError):replay(rows)
    def test_manifest_foreign_request_digest_rejected(self):
        rows=events();rows[2]['request_sha256']='0'*64
        with self.assertRaises(model.PublicationError):replay(rows)
    def test_stop_prevents_later_effect_records_but_preserves_terminal(self):
        rows=events();stop={'schema':model.SCHEMA,'kind':'STOP'}
        for length in range(1,5):
            with self.assertRaises(model.PublicationError):replay(rows[:length]+[stop,rows[length]])
        self.assertEqual(replay(rows+[stop])['terminal'],rows[-1])
    def test_duplicate_terminal_no_native_or_file_effect(self):
        owner=BlenderPublicationOwner();state=replay(events());owner._refresh=Mock(return_value=state)
        owner._authorize=Mock(side_effect=AssertionError('no reauthorization/effect'))
        raw=owner.publish(request(),None)
        self.assertEqual(raw,canonical_bytes(state['terminal']['response']));owner._authorize.assert_not_called()
    def test_conflicting_id_fails_without_poison(self):
        owner=BlenderPublicationOwner();owner._refresh=Mock(return_value=replay(events()))
        changed=dict(request(),expected_revision='sha256:'+'2'*64)
        with self.assertRaisesRegex(model.PublicationError,'CONFLICT'):owner.publish(changed,None)
        self.assertFalse(owner._held)
    def test_unknown_prefix_duplicate_never_replays(self):
        owner=BlenderPublicationOwner();owner._refresh=Mock(return_value=replay(events()[:4]))
        owner._authorize=Mock(side_effect=AssertionError('no effect replay'))
        self.assertIn(b'"status":"UNKNOWN"',owner.publish(request(),None));owner._authorize.assert_not_called()
    def test_cleanup_retains_failed_native_owner_for_retry(self):
        owner=BlenderPublicationOwner();job=Mock();job.done.is_set.return_value=True
        job.retry_cleanup.side_effect=[OSError('native close'),{}];owner._job=job
        with self.assertRaises(model.PublicationError) as caught:owner.close()
        self.assertIs(caught.exception.cleanup_owner,owner);self.assertIs(owner._job,job)
        owner.close();self.assertIsNone(owner._job);self.assertTrue(owner._closed)
    def test_stop_signals_native_before_publication_lock(self):
        owner=BlenderPublicationOwner();owner.session=Mock();owner._job=Mock()
        owner._mutex=MagicMock();owner._mutex.__enter__.side_effect=RuntimeError('lock held')
        with self.assertRaises(RuntimeError):owner.stop()
        owner._job.request_stop.assert_called_once();owner.session.stop.assert_called_once()
    def test_capture_rejects_foreign_path_before_open(self):
        owner=BlenderPublicationOwner();owner._job=Mock(directory=Path('owned/export'));owner.host=Mock()
        with self.assertRaisesRegex(model.PublicationError,'FIXED_CAPTURE_PATH'):
            owner._owned_bytes(Path('foreign/input.blend'),'0'*64)
        owner.host._api.open.assert_not_called()
    def test_capture_acl_failure_closes_parent_before_file_read(self):
        owner=BlenderPublicationOwner();owner._job=Mock(directory=Path('owned/export'));owner.host=Mock()
        api=owner.host._api;api.open.return_value=123;api.check_security.side_effect=OSError('parent changed')
        with self.assertRaises(OSError):owner._owned_bytes(Path('owned/export/input.blend'),'0'*64)
        api.read.assert_not_called();api.close.assert_called_once_with(123)

if __name__=='__main__':unittest.main()
