"""Closed profile compatibility and exact save translation; no native effects."""
import copy
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

import test_publication as fixture
from studio.host.blender import publication_state as model
from studio.host.blender.publication_owner import BlenderPublicationOwner
from studio.host.blender.export_job import ExportJob
from studio.protocol.core import canonical_bytes


class PublicationProfileTests(unittest.TestCase):
    def save(self, operation='scene.save'):
        return {'schema':model.queue.SCHEMA,'command_id':'save-one','operation':'checkpoint.save',
            'expected_revision':'sha256:'+'a'*64,
            'expected_context':{'mode':'OBJECT','active_id':None,'selected_ids':[]},
            'payload':{'slot':'fixture' if operation=='scene.save' else 'checkpoint'}}

    def test_legacy_config_remains_export_and_replays_exact_old_receipt(self):
        rows=fixture.events();state=fixture.replay(rows)
        self.assertEqual(model.profile(state['config']),'export.publish')
        self.assertEqual(state['terminal']['response'],rows[-1]['response'])
        self.assertEqual(model.preparation(state['config']),('export.prepare','export'))

    def test_three_profiles_have_exact_native_preparation_and_unchanged_history_states(self):
        for operation,expected in [('scene.save',('checkpoint.save','fixture')),
                                   ('checkpoint.save',('checkpoint.save','checkpoint')),
                                   ('export.publish',('export.prepare','export'))]:
            rows=fixture.events();rows[0]['publication_profile']=operation
            state=fixture.replay(rows)
            self.assertEqual(model.preparation(state['config']),expected)
            self.assertEqual(state['phase'],'TERMINAL')

    def test_unknown_null_boolean_or_container_profile_rejected_before_provisioning(self):
        for profile in ('arbitrary',None,True,{},[],1):
            with self.subTest(profile=profile), self.assertRaises(model.PublicationError):
                BlenderPublicationOwner.create('unused',session=None,profile=profile)

    def test_save_projection_binds_id_revision_context_and_no_callers_path(self):
        for operation in ('scene.save','checkpoint.save'):
            command=self.save(operation);projected=model.save_request(command,operation)
            self.assertEqual(projected,dict(schema=model.SCHEMA,command_id=command['command_id'],
                expected_revision=command['expected_revision'],expected_context=command['expected_context']))
            for invalid in (dict(command,path='C:/foreign'),dict(command,payload={'slot':'export'}),
                            dict(command,payload={'slot':'fixture' if operation=='checkpoint.save' else 'checkpoint'})):
                with self.assertRaises((model.PublicationError,ValueError)):model.save_request(invalid,operation)

    def test_save_object_profile_rejects_edit_context_without_storage_access(self):
        command=self.save();command['expected_context']={'mode':'EDIT_MESH','active_id':'box','selected_ids':['box']}
        with self.assertRaisesRegex(model.PublicationError,'OBJECT_MODE'):model.save_request(command,'scene.save')

    def test_save_forwards_original_deadline_guard_and_same_projected_request(self):
        owner=BlenderPublicationOwner();owner._state={'config':{'publication_profile':'checkpoint.save'}}
        owner.publish=Mock(return_value=b'receipt');lease=object();guard=Mock()
        command=self.save('checkpoint.save')
        self.assertEqual(owner.publish_save(command,lease,deadline_ms=123,phase_guard=guard),b'receipt')
        owner.publish.assert_called_once_with(model.save_request(command,'checkpoint.save'),lease,deadline_ms=123,phase_guard=guard)

    def test_native_prepare_uses_config_slot_with_original_fence_and_deadline(self):
        for profile,slot in (('scene.save','fixture'),('checkpoint.save','checkpoint'),('export.publish','export')):
            owner=BlenderPublicationOwner();owner._state={'config':{'publication_profile':profile}}
            owner.host=Mock();lease=SimpleNamespace(fencing_epoch=4,expires_ms=9000)
            request=fixture.request();operation,_=model.preparation(owner._state['config'])
            owner._native('native-save',operation,lease,request,deadline_ms=8000)
            command=owner.host.execute.call_args.args[0];options=owner.host.execute.call_args.kwargs
            self.assertEqual(command['payload'],{'slot':slot});self.assertEqual(command['operation'],operation)
            self.assertEqual(options,{'lease':{'fencing_epoch':4,'expires_ms':9000},'deadline_ms':8000})

    def test_background_input_names_cannot_include_paths_before_any_owner_access(self):
        for name in ('../export.blend','C:/fixture.blend','other.blend',None,True,[]):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'FIXED_INPUT'):
                ExportJob(None,None,input_name=name)

    def test_manifest_profile_mismatch_rejected_before_artifact_reads(self):
        owner=BlenderPublicationOwner();owner._state={'config':{'publication_profile':'scene.save'}}
        owner._read_protected=Mock(return_value=canonical_bytes({'publication_profile':'checkpoint.save'}))
        with self.assertRaisesRegex(model.PublicationError,'MANIFEST_PROFILE'):owner._read_bundle({'manifest':{}})
        owner._read_protected.assert_called_once()

    def test_stop_signals_active_job_before_blocking_on_durable_session(self):
        owner=BlenderPublicationOwner();owner._job=Mock();owner.session=Mock()
        owner.session.stop.side_effect=OSError('inert persistent stop wait')
        with self.assertRaises(OSError):owner.stop()
        self.assertTrue(owner._stop.is_set());owner._job.request_stop.assert_called_once()


if __name__=='__main__':unittest.main()
