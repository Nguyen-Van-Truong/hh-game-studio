"""O2 static validation only; no bpy, actual readback or UndoRedo claim."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('o2_blender_authoring', STUDIO / 'blender-addon/authoring_contract.py')
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class BlenderAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.catalog = c.load_catalog()
        self.template = self.catalog.as_dict()['templates'][0]
        self.arm = c.ArmatureState('hero', self.template['template_id'], self.template['template_sha256'])
        self.ctx = c.ValidationContext('project.fixture', 'sha256:'+'1'*64, 1, 'lease.fixture', 7, 31000, 1000,
                                       (self.arm,), (c.ActionState('idle', 'hero'),))

    def request(self, op='armature.from_template', target='root', payload=None, **overrides):
        if payload is None:
            payload = dict(stable_id='new.rig', template_id=self.template['template_id'],
                           template_sha256=self.template['template_sha256'])
        payload = dict(payload)
        payload.setdefault('expected_generation', 1)
        values = dict(command_id='cmd.fixture', project_id=self.ctx.project_id, operation=op,
                      lease_id=self.ctx.lease_id, fencing_epoch=7, expected_revision=self.ctx.revision,
                      target={'stable_id':target}, payload=payload,
                      payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(), deadline_ms=2000)
        values.update(overrides)
        return Request(**values)

    def key(self, **changes):
        p = dict(bone_id='root', channel='location', frame=1, values=[0, 1, 0], interpolation='LINEAR')
        p.update(changes)
        return self.request('animation.keyframe.set', 'idle', p)

    def validate(self, request=None, context=None):
        return c.validate_request(request or self.request(), context or self.ctx, self.catalog).proposal

    def reject(self, request, code=None, context=None):
        with self.assertRaises(ValidationError) as error:
            self.validate(request, context)
        if code:
            self.assertEqual(error.exception.code, code)

    def test_each_template_binds_bones_hash_and_undo_proposal(self):
        for t in self.catalog.as_dict()['templates']:
            with self.subTest(template=t['template_id']):
                out = self.validate(self.request(payload=dict(stable_id='new.rig', template_id=t['template_id'],
                                                              template_sha256=t['template_sha256'])))
                self.assertEqual(out['after']['bones'], t['bones'])
                self.assertEqual(out['after']['template_sha256'], t['template_sha256'])
                self.assertEqual(out['undo_policy'], 'remove_created_armature_if_revision_matches')
                self.assertFalse(out['runtime_authorized'])
                self.assertFalse(out['native_verified'])

    def test_action_create_is_owned_empty_and_not_active(self):
        out = self.validate(self.request('animation.action.create', 'hero', dict(stable_id='walk')))
        self.assertEqual(out['after'], dict(stable_id='walk', armature_id='hero', keyframes=[]))
        self.assertEqual(out['undo_policy'], 'remove_created_action_if_revision_matches')
        self.assertFalse(out['changes_applied'])

    def test_all_channels_and_interpolations_have_typed_proposals(self):
        for channel in c._CHANNELS:
            for interpolation in ('LINEAR', 'CONSTANT'):
                with self.subTest(channel=channel, interpolation=interpolation):
                    out = self.validate(self.key(channel=channel, values=[1, 1, 1], interpolation=interpolation))
                    self.assertEqual(out['after']['channel'], channel)
                    self.assertIsNone(out['before'])
                    self.assertEqual(out['undo_policy'], 'remove_created_keyframe')

    def test_replacing_key_preserves_prior_values_for_undo(self):
        old = c.KeyframeState('root','location',1,(9, 8, 7),'CONSTANT')
        ctx = replace(self.ctx, actions=(c.ActionState('idle','hero',(old,)),))
        out = self.validate(self.key(), ctx)
        self.assertEqual(out['before']['values'], [9, 8, 7])
        self.assertEqual(out['before']['interpolation'], 'CONSTANT')
        self.assertEqual(out['undo_policy'], 'restore_prior_keyframe')
        self.assertEqual(ctx.actions[0].keyframes[0], old)

    def test_proposal_does_not_alias_request_or_catalog(self):
        r = self.request()
        result = c.validate_request(r, self.ctx, self.catalog)
        r.payload['stable_id'] = 'changed'
        first = result.proposal
        first['after']['bones'][0]['head'][0] = 999
        self.assertEqual(result.proposal['after']['stable_id'], 'new.rig')
        self.assertEqual(result.proposal['after']['bones'][0]['head'][0], 0)
        self.assertEqual(self.catalog.as_dict()['templates'][0]['bones'][0]['head'][0], 0)

    def test_script_driver_path_and_extra_fields_reject(self):
        for operation in ('python.eval', 'script_text.replace', 'animation.driver.create'):
            self.reject(self.request(op=operation), 'BLEND_AUTH_OPERATION_DISABLED')
        self.reject(self.key(data_path='pose.bones[0]'), 'BLEND_AUTH_SHAPE')
        self.reject(self.key(channel='custom_property'), 'BLEND_AUTH_CHANNEL')
        with self.assertRaises(ValidationError):
            self.request(target={'path':'../outside'})

    def test_wrong_templates_hashes_and_ids_reject(self):
        base = self.request().payload
        for field, value, code in [('template_id','unknown','BLEND_AUTH_TEMPLATE_UNKNOWN'),
                                   ('template_sha256','sha256:'+'0'*64,'BLEND_AUTH_TEMPLATE_HASH'),
                                   ('stable_id','hero','BLEND_AUTH_DUPLICATE_ID'),
                                   ('stable_id','root','BLEND_AUTH_DUPLICATE_ID'),
                                   ('stable_id','../escape','BLEND_AUTH_DUPLICATE_ID')]:
            self.reject(self.request(payload={**base,field:value}), code)
        self.reject(self.request('animation.action.create','root',dict(stable_id='walk')), 'BLEND_AUTH_TARGET')
        self.reject(self.request('animation.action.create','hero',dict(stable_id='hero')), 'BLEND_AUTH_DUPLICATE_ID')

    def test_keyframe_invalid_types_ranges_and_bone_reject(self):
        cases = [('bone_id','missing'), ('channel',[]), ('values',[True,0,0]), ('values',[1,2]),
                 ('values',[0,0,1001]), ('frame',True), ('frame',1.5), ('frame',-1),
                 ('frame',10001), ('interpolation','BEZIER')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.reject(self.key(**{field:value}))
        self.reject(self.key(channel='scale',values=[0,1,1]))
        self.reject(self.key(channel='rotation_euler',values=[0,7,0]))
        for invalid in (float('nan'),float('inf'),-float('inf')):
            with self.assertRaises(ValidationError):
                self.key(values=[invalid,0,0])

    def test_stale_lease_revision_generation_deadline_stop_reject(self):
        for override, code in [({'expected_revision':'sha256:'+'2'*64},'BLEND_AUTH_STALE_REVISION'),
                               ({'lease_id':'other'},'BLEND_AUTH_STALE_LEASE'),
                               ({'fencing_epoch':8},'BLEND_AUTH_STALE_LEASE'),
                               ({'project_id':'other'},'BLEND_AUTH_PROJECT'),
                               ({'deadline_ms':1000},'BLEND_AUTH_DEADLINE'),
                               ({'deadline_ms':31001},'BLEND_AUTH_DEADLINE')]:
            self.reject(self.request(**override),code)
        self.reject(self.request(payload={**self.request().payload,'expected_generation':2}), 'BLEND_AUTH_STALE_GENERATION')
        self.reject(self.request(), 'BLEND_AUTH_STOPPED', replace(self.ctx,stopped=True))
        self.reject(self.request(), 'BLEND_AUTH_CONTEXT', replace(self.ctx,mode='EDIT_ARMATURE'))

    def test_armature_and_action_caps_reject_creates(self):
        arms = tuple(replace(self.arm, stable_id='rig.'+str(i)) for i in range(16))
        self.reject(self.request(), 'BLEND_AUTH_ARMATURE_LIMIT', replace(self.ctx, armatures=arms, actions=()))
        actions = tuple(c.ActionState('action.'+str(i),'hero') for i in range(32))
        self.reject(self.request('animation.action.create','hero',dict(stable_id='new.action')),
                    'BLEND_AUTH_ACTION_LIMIT', replace(self.ctx,actions=actions))

    def test_keyframe_limit_allows_replacement_but_not_extra_key(self):
        keys = tuple(c.KeyframeState('root','location',i,(0,0,0)) for i in range(256))
        ctx = replace(self.ctx,actions=(c.ActionState('idle','hero',keys),))
        self.validate(self.key(frame=255),ctx)
        self.reject(self.key(frame=256),'BLEND_AUTH_KEYFRAME_LIMIT',ctx)
        duplicate = replace(self.ctx,actions=(c.ActionState('idle','hero',(keys[0],keys[0])),))
        self.reject(self.key(),'BLEND_AUTH_DUPLICATE_KEYFRAME',duplicate)

    def test_observed_action_ownership_and_armature_hash_reject(self):
        self.reject(self.key(), 'BLEND_AUTH_ACTION_STATE',
                    replace(self.ctx,actions=(c.ActionState('idle','missing'),)))
        self.reject(self.key(), 'BLEND_AUTH_TEMPLATE_HASH',
                    replace(self.ctx,armatures=(replace(self.arm,template_sha256='sha256:'+'0'*64),)))

    def test_catalog_rejects_tamper_cycles_zero_bones_and_capability_claim(self):
        original=json.loads(c.SCHEMA_PATH.read_text(encoding='utf-8'))
        def tamper(doc, which):
            meta=doc['x-candidate']; t=meta['templates'][0]
            if which=='hash': t['bones'][0]['head'][0]=1
            if which=='cycle': t['bones'][0]['parent_id']='spine'
            if which=='zero': t['bones'][0]['tail']=t['bones'][0]['head'][:]
            if which=='capability': meta['runtime_enabled']=True
            if which=='limit': meta['limits']['max_armatures']=True
            if which=='duplicate': t['bones'][1]['bone_id']='root'
        for kind in ('hash','cycle','zero','capability','limit','duplicate'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                doc=json.loads(json.dumps(original)); tamper(doc,kind)
                p=Path(tmp)/'catalog.json'; p.write_text(json.dumps(doc),encoding='utf-8')
                with self.assertRaises(ValidationError): c.load_catalog(p)

    def test_candidate_stays_unregistered_and_script_disabled(self):
        out=self.validate()
        self.assertFalse(out['script_enabled'])
        self.assertEqual(out['native_gates_pending'],list(c.NATIVE_GATES))
        self.assertNotIn('COMMITTED',out.values())
        self.assertNotIn('bpy',sys.modules)


if __name__ == '__main__':
    unittest.main()
