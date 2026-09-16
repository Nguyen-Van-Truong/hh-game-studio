"""Rejection regressions against saved native output; no engine launch here."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('gt03_profile_readback', STUDIO/'godot-addon/profile_readback.py')
readback = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = readback
SPEC.loader.exec_module(readback)
factory = readback.factory
codec = factory.bundle_codec
SCRIPT = (b'extends Node3D\n@export var fixture_value: int = 9\n'
    b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
    b'@export var enabled: bool = false\n')


class ProfileReadbackTests(unittest.TestCase):
    def setUp(self):
        self.bundle = factory.compose(factory.DEFAULT_SCENE, SCRIPT,
            scene_revision='sha256:'+'1'*64, engine_sha256='2'*64)
        self.saved = json.loads(Path(__file__).with_name('fixtures').joinpath('profile-readback-baseline.json').read_bytes())
        self.report = self.saved['observation']

    def test_actual_saved_observation_matches_without_public_or_process_claim(self):
        self.assertEqual({k:hashlib.sha256(v).hexdigest() for k,v in self.bundle.files.items()}, self.saved['input_hashes'])
        result = readback.compare_observation(self.bundle, self.report)
        self.assertEqual(result['status'], 'PROFILE_OBSERVATIONS_MATCH')
        for flag in ('public_ack','process_attribution_proven','sandbox_acceptance'):
            self.assertIs(result[flag], False)

    def test_each_required_top_level_observation_cannot_disappear(self):
        for key in self.report:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.report)
                del bad[key]
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle,bad)

    def test_clean_but_wrong_script_uid_hash_reload_and_defaults_rejected(self):
        patches = {'source_sha256':'a'*64,'disk_sha256':'a'*64,'reload_code':1,
            'resource_uid':'uid://ba','uid_source':'uid://ba\n','methods':['evil'],
            'signals':['evil'],'constants':['evil'],'base_type':'Object',
            'has_base_script':True,'can_instantiate':False,'is_tool':True}
        for key,value in patches.items():
            with self.subTest(key=key):
                bad=copy.deepcopy(self.report);bad['script'][key]=value
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle,bad)

    def test_fresh_instance_override_is_distinct_from_script_default(self):
        bad=copy.deepcopy(self.report)
        bad['instance_nodes'][0]['exports']['fixture_value']['value']=9
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle,bad)
        bad=copy.deepcopy(self.report)
        bad['fresh_script']['exports']['fixture_value']['value']=23
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle,bad)

    def test_scalar_float_does_not_inherit_binary32_transform_epsilon(self):
        bad=copy.deepcopy(self.report)
        bad['instance_nodes'][0]['exports']['turn_speed']['value']=90.00001
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle,bad)

    def test_tiny_admitted_export_cannot_collapse_to_zero(self):
        script=SCRIPT.replace(b'float = 2.25',b'float = 0.0000000000001')
        candidate=factory.compose(factory.DEFAULT_SCENE,script,
            scene_revision=self.bundle.scene_revision,engine_sha256=self.bundle.engine_sha256)
        good=copy.deepcopy(self.report)
        for key in ('source_sha256','disk_sha256'):good['script'][key]=candidate.script_sha256
        good['fresh_script']['source_sha256']=candidate.script_sha256
        good['instance_nodes'][0]['script_sha256']=candidate.script_sha256
        good['scene']['nodes'][0]['properties'][0]['value']['source_sha256']=candidate.script_sha256
        for exports in (good['script']['defaults'],good['fresh_script']['exports'],good['instance_nodes'][0]['exports']):
            exports['move_speed']['value']=1e-13
        self.assertEqual(readback.compare_observation(candidate,good)['status'],'PROFILE_OBSERVATIONS_MATCH')
        good['instance_nodes'][0]['exports']['move_speed']['value']=0.0
        with self.assertRaises(readback.ReadbackError):readback.compare_observation(candidate,good)

    def test_scene_aliases_owner_groups_and_injected_properties_rejected(self):
        cases=[('owner','foreign'),('path','foreign'),('stable_id','foreign'),
               ('script_sha256','a'*64),('type','Object'),('groups',['evil'])]
        for key,value in cases:
            with self.subTest(key=key):
                bad=copy.deepcopy(self.report);bad['instance_nodes'][0][key]=value
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle,bad)
        bad=copy.deepcopy(self.report)
        bad['scene']['nodes'][0]['properties'].append({'name':'foo','value':{'type':'int','value':1}})
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle,bad)

    def test_bool_cannot_stand_for_integer_and_nan_never_matches(self):
        for value in (True,float('nan'),float('inf')):
            bad=copy.deepcopy(self.report);bad['pid']=value
            with self.assertRaises(readback.ReadbackError):
                readback.compare_observation(self.bundle,bad)
        bad=copy.deepcopy(self.report)
        bad['instance_nodes'][0]['transform_rows_origin'][0]=float('nan')
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle,bad)

    def test_caller_can_rehash_untrusted_release_bytes_but_factory_rejects(self):
        for path in factory.trusted_files():
            with self.subTest(path=path):
                files=dict(self.bundle.files)
                files[path]=b'uid://ba\n' if path.endswith('.uid') else files[path]+b'\n'
                forged=codec.create_bundle(files,scene_revision=self.bundle.scene_revision,engine_sha256=self.bundle.engine_sha256)
                with self.assertRaises(factory.FixtureProfileError):
                    factory.qualify(forged)

    def test_candidate_scene_cannot_reuse_trusted_plugin_uid(self):
        uid=self.bundle.files['addons/hh_studio/plugin.gd.uid'].decode().strip()
        scene=factory.DEFAULT_SCENE.replace(b'format=3]',f'format=3 uid="{uid}"]'.encode())
        candidate=factory.compose(scene,SCRIPT,scene_revision=self.bundle.scene_revision,engine_sha256=self.bundle.engine_sha256)
        with self.assertRaises(factory.FixtureProfileError):
            factory.qualify(candidate)

    def test_release_source_pin_mismatch_fails_before_bundle_use(self):
        original=Path.read_bytes
        def changed(path):
            value=original(path)
            return value+b'\n' if path.as_posix().endswith('addons/hh_studio/plugin.gd') else value
        with mock.patch.object(Path,'read_bytes',changed):
            with self.assertRaises(factory.FixtureProfileError):
                factory.trusted_files()

    def test_script_replacement_keeps_uid_and_every_trusted_source(self):
        candidate=codec.replace_script(self.bundle, SCRIPT.replace(b'int = 9',b'int = 10'),
            expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256,expected_uid_sha256=self.bundle.uid_sha256)
        eligible=factory.qualify(candidate)
        self.assertNotEqual(eligible.bundle.project_revision,self.bundle.project_revision)
        for path in self.bundle.files:
            if path!=codec.SCRIPT_PATH:
                self.assertEqual(candidate.files[path],self.bundle.files[path])
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(candidate,self.report)


if __name__=='__main__':
    unittest.main(verbosity=2)
