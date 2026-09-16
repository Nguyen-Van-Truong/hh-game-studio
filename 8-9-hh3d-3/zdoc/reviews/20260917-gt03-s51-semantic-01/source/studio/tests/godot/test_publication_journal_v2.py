"""Real protected journal/bootstrap bytes; engine metadata is synthetic."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import uuid

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);sys.modules[name]=result
    spec.loader.exec_module(result);return result
journal=load('gt03_journal_v2_tests',STUDIO/'godot-addon/publication_journal_v2.py')
legacy=load('gt03_journal_cleanup_helpers',Path(__file__).with_name('test_publication_journal.py'))
codec=journal.bundle_codec
from studio.protocol.core import parse_json
from studio.host.core.custody_registry import RegistryCustody

def sha(value):return hashlib.sha256(value.encode()).hexdigest()
def rev(value):return 'sha256:'+sha(value)
def bundle(scene='scene-one'):
    files={name: ('uid://abc123\n' if name.endswith('.uid') else 'synthetic '+name+'\n').encode() for name in codec.PATHS}
    files[codec.SCENE_PATH]=scene.encode()
    return codec.create_bundle(files,scene_revision=rev('scene-state'),engine_sha256=sha('engine'))
def configuration(value):
    return {'schema':journal.state_model.SCHEMA,'sequence':1,'kind':'CONFIG','project_id':'v2-journal-test',
        'observed_ms':100,'engine_sha256':value.engine_sha256,'source_closure_sha256':sha('source'),
        'initial':{'project_revision':value.project_revision,'scene_revision':value.scene_revision,
            'files':parse_json(value.manifest_bytes)['files'],'selection':{'generation':0,'identity':rev('initial')}}}
def prepared(owner,identifier='command.one'):
    s=owner.snapshot();before=s['last_good'];now=s['last_observed_ms']+1
    return {'schema':journal.state_model.SCHEMA,'kind':'PREPARED','sequence':s['event_count']+1,
        'project_id':s['project_id'],'observed_ms':now,'command_id':identifier,'digest':rev(identifier),
        'operation':'scene.save','candidate_id':'candidate-'+sha(identifier)[:32],
        'before_project_revision':before['project_revision'],'before_scene_revision':before['scene_revision'],
        'expected_files':before['files'],'parent_selection':before['selection'],'checkpoint_sha256':sha('checkpoint'),
        'script_input':None,'admission':{'lease_id':'lease.one','fencing_epoch':1,'admitted_ms':now,
            'deadline_ms':now+1000,'lease_expires_ms':10000,'editor_session_id':'synthetic.editor','editor_generation':1}}

@unittest.skipUnless(os.name=='nt','actual Windows protected native roots/Registry required')
class JournalV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):RegistryCustody.provision_base()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-gt03-journal-')
        self.base=Path(self.temp.name).resolve();self.storage_id=uuid.uuid4().hex;self.owners=[]
        self.addCleanup(lambda:legacy.PublicationJournalTests.cleanup(self))
    def create(self):
        value=bundle()
        try:owner=journal.PublicationJournalV2.create(self.base,storage_id=self.storage_id,config=configuration(value),initial_bundle=value)
        except journal.PublicationJournalV2Error as exc:
            if exc.cleanup_owner is not None:self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner);return owner
    def reopen(self):
        try:owner=journal.PublicationJournalV2.reopen(self.storage_id,project_id='v2-journal-test')
        except journal.PublicationJournalV2Error as exc:
            if exc.cleanup_owner is not None:self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner);return owner
    def test_bootstrap_durable_order_actual_selected_bundle_and_readonly_reopen(self):
        owner=self.create();state=owner.snapshot();current=owner.selected_bytes()
        self.assertEqual(state['journal_event_sequence'],5);self.assertEqual(state['event_count'],1)
        self.assertTrue(state['bootstrap_bytes_verified']);self.assertFalse(state['public_ack'])
        self.assertEqual(current.selection,state['last_good']['selection'])
        self.assertEqual(owner._store.read_descriptor(current.descriptor),bundle())
        events=[parse_json(row) for row in owner._native_events()]
        self.assertEqual([r['kind'] for r in events],[*journal._BOOT_KINDS,'CONFIG'])
        owner.close();reopened=self.reopen()
        self.assertEqual(reopened.selected_bytes().source_bytes,current.source_bytes)
        self.assertTrue(reopened.snapshot()['journal_read_only'])
        with self.assertRaisesRegex(journal.PublicationJournalV2Error,'READ_ONLY'):
            reopened.prepare(prepared(reopened),bundle('scene-two'))
    def test_actual_prepare_persisted_before_staging_and_descriptor_replays(self):
        owner=self.create();request=prepared(owner);count=len(list(owner._files.root.iterdir()))
        owner.prepare(request,bundle('scene-two'))
        self.assertEqual(len(list(owner._files.root.iterdir())),count)
        staged=owner.stage_prepared(request['command_id'],request['digest'],observed_ms=102)
        self.assertEqual(staged['commands'][-1]['phase'],'STAGED')
        self.assertEqual(len(list(owner._files.root.iterdir())),count+12)
        descriptor=staged['commands'][-1]['candidate']['descriptor']
        self.assertEqual(owner._store.read_descriptor(descriptor),bundle('scene-two'))
        baseline=owner.selected_bytes();owner.close();reopened=self.reopen()
        self.assertEqual(reopened.lookup(request['command_id'],request['digest'])['phase'],'STAGED')
        self.assertEqual(reopened.selected_bytes().source_bytes,baseline.source_bytes)
        self.assertEqual(reopened._store.read_descriptor(descriptor),bundle('scene-two'))
    def test_invalid_prepared_revision_cancels_reservation_without_file_write(self):
        owner=self.create();request=prepared(owner);request['before_project_revision']=rev('wrong')
        before={p.name for p in owner._files.root.iterdir()}
        with self.assertRaises(Exception):owner.prepare(request,bundle('scene-two'))
        self.assertEqual({p.name for p in owner._files.root.iterdir()},before)
        self.assertEqual(owner.snapshot()['event_count'],1)
        owner.prepare(prepared(owner,'command.two'),bundle('scene-two'))
    def test_bad_stage_time_rejects_before_files_and_preserves_prepared(self):
        owner=self.create();request=prepared(owner);owner.prepare(request,bundle('scene-two'))
        before={p.name for p in owner._files.root.iterdir()}
        for value in (False,-1,99,'102'):
            with self.assertRaisesRegex(journal.PublicationJournalV2Error,'STAGE_TIME'):
                owner.stage_prepared(request['command_id'],request['digest'],observed_ms=value)
        self.assertEqual({p.name for p in owner._files.root.iterdir()},before)
        self.assertEqual(owner.lookup(request['command_id'])['phase'],'PREPARED')
    def test_direct_synthetic_preparation_cannot_reach_native_log(self):
        owner=self.create();request=prepared(owner)
        request['planned_names']={name:'obj-'+sha(name)[:32] for name in (*codec.PATHS,'@manifest')}
        with self.assertRaisesRegex(journal.PublicationJournalV2Error,'OWNED_PREPARATION'):
            owner.append(request)
        self.assertEqual(owner.snapshot()['event_count'],1)
    def test_lost_bootstrap_select_result_prevents_config_and_restart(self):
        select=journal.store_model.ProtectedBundleStore.select
        def lost(store,intent):
            select(store,intent);raise OSError('injected lost return after actual selection')
        with mock.patch.object(journal.store_model.ProtectedBundleStore,'select',lost):
            with self.assertRaises(journal.PublicationJournalV2Error):self.create()
        with self.assertRaises(journal.PublicationJournalV2Error):self.reopen()
    def test_cancellation_during_native_bootstrap_preserved_after_cleanup(self):
        with mock.patch.object(journal.store_model.ProtectedBundleStore,'stage',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.create()
        with self.assertRaises(journal.PublicationJournalV2Error):self.reopen()

if __name__=='__main__':unittest.main()
