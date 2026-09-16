"""Pure rejection tests; constructed semantic rows are not native evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s51_semantic_comparator', STUDIO / 'godot-addon/profile_readback.py')
readback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readback)
factory = readback.factory
SCRIPT = (b'extends Node3D\n@export var fixture_value: int = 9\n'
          b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
          b'@export var enabled: bool = false\n')


def rehash(semantic):
    semantic['revision'] = 'sha256:' + hashlib.sha256(
        factory.bundle_codec.canonical_bytes(semantic['state'])).hexdigest()


class SemanticReadbackTests(unittest.TestCase):
    def setUp(self):
        self.bundle = factory.compose(factory.DEFAULT_SCENE, SCRIPT,
            scene_revision='sha256:' + '1' * 64, engine_sha256='2' * 64)
        self.report = json.loads(Path(__file__).with_name('fixtures').joinpath(
            'profile-readback-baseline.json').read_bytes())['observation']
        self.report['schema'] = readback.REPORT_SCHEMA
        stored = {'metadata/hh_studio_id': 'root', 'script': {'type': 'GDScript',
            'path': 'res://scripts/fixture_actor.gd', 'source_sha256': self.bundle.script_sha256},
            'fixture_value': 23, 'move_speed': 2.25, 'turn_speed': 90.0, 'enabled': False}
        self.report['semantic'] = {'schema': readback.SEMANTIC_SCHEMA,
            'context_kind': 'isolated_candidate',
            'serializer_sha256': hashlib.sha256(self.bundle.files['addons/hh_studio/scene_commands.gd']).hexdigest(),
            'jcs_sha256': hashlib.sha256(self.bundle.files['addons/hh_studio/jcs_godot.gd']).hexdigest(),
            'state': {'nodes': [{'node_type': 'Node3D', 'name': 'Fixture', 'stable_id': 'root',
                'parent_id': '', 'sibling_index': 0, 'owner_id': '', 'position': [0.0, 0.0, 0.0],
                'rotation_degrees': [0.0, 0.0, 0.0], 'scale': [1.0, 1.0, 1.0],
                'stored': stored, 'groups': []}]}}
        rehash(self.report['semantic'])

    def test_v2_has_exact_hash_but_never_process_or_editor_attribution(self):
        result = readback.compare_observation(self.bundle, self.report)
        self.assertTrue(result['semantic_observed'])
        self.assertEqual(result['semantic_revision'], self.report['semantic']['revision'])
        self.assertNotEqual(result['semantic_revision'], self.bundle.scene_revision)
        for flag in ('public_ack', 'process_attribution_proven', 'sandbox_acceptance'):
            self.assertIs(result[flag], False)

    def test_legacy_report_cannot_supply_candidate_revision(self):
        del self.report['semantic']
        self.report['schema'] = 'hh-godot-profile-readback-1'
        result = readback.compare_observation(self.bundle, self.report)
        self.assertIs(result['semantic_observed'], False)
        self.assertIsNone(result['semantic_revision'])

    def test_each_semantic_field_is_required(self):
        for key in self.report['semantic']:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.report)
                del bad['semantic'][key]
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle, bad)

    def test_v2_cannot_omit_semantic_or_add_editor_attestation(self):
        bad = copy.deepcopy(self.report)
        del bad['semantic']
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle, bad)
        self.report['semantic']['editor_session_id'] = 'fabricated'
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle, self.report)

    def test_fabricated_context_and_wrong_release_pins_rejected(self):
        for key, value in [('context_kind', 'live_editor'), ('serializer_sha256', '0' * 64),
                           ('jcs_sha256', '0' * 64), ('schema', 'other')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.report)
                bad['semantic'][key] = value
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle, bad)

    def test_rehashed_script_identity_still_must_match_candidate_bytes(self):
        self.report['semantic']['state']['nodes'][0]['stored']['script']['source_sha256'] = '0' * 64
        rehash(self.report['semantic'])
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle, self.report)

    def test_rehashed_export_and_owner_mismatch_rejected(self):
        for kind in ('export', 'owner', 'position'):
            with self.subTest(kind=kind):
                bad = copy.deepcopy(self.report)
                row = bad['semantic']['state']['nodes'][0]
                if kind == 'export': row['stored']['move_speed'] = 2.25000000000001
                elif kind == 'owner': row['owner_id'] = 'root'
                else: row['position'][0] = 1e-13
                rehash(bad['semantic'])
                with self.assertRaises(readback.ReadbackError):
                    readback.compare_observation(self.bundle, bad)

    def test_no_epsilon_for_semantic_hash_even_when_vector_delta_is_tiny(self):
        original = readback.semantic_state_bytes(self.report['semantic'])
        self.report['semantic']['state']['nodes'][0]['rotation_degrees'][0] = 1e-13
        with self.assertRaisesRegex(readback.ReadbackError, 'SEMANTIC_REVISION'):
            readback.semantic_state_bytes(self.report['semantic'])
        rehash(self.report['semantic'])
        self.assertNotEqual(original, readback.semantic_state_bytes(self.report['semantic']))

    def test_nonfinite_and_unbounded_tree_rejected(self):
        bad = copy.deepcopy(self.report['semantic'])
        bad['state']['nodes'][0]['stored']['bad'] = float('nan')
        with self.assertRaises(readback.ReadbackError): readback.semantic_state_bytes(bad)
        bad = copy.deepcopy(self.report['semantic'])
        bad['state']['nodes'] *= 65
        with self.assertRaises(readback.ReadbackError): readback.semantic_state_bytes(bad)

    def test_unknown_row_field_rejected_even_if_rehashed(self):
        self.report['semantic']['state']['nodes'][0]['invented'] = True
        rehash(self.report['semantic'])
        with self.assertRaises(readback.ReadbackError):
            readback.compare_observation(self.bundle, self.report)

    def test_eleven_input_files_still_qualify(self):
        self.assertEqual(len(self.bundle.files), 11)
        self.assertEqual(factory.qualify(self.bundle).bundle.files, self.bundle.files)


if __name__ == '__main__': unittest.main(verbosity=2)
