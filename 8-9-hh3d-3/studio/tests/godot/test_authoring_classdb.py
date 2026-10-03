"""Synthetic reflection regressions; these are not native ClassDB evidence."""
import copy
from types import SimpleNamespace
import unittest

from tests.godot import run_authoring_classdb_probe as probe


class ResourceCompatibilityTests(unittest.TestCase):
    def setUp(self):
        prop = probe.contract.PropertySpec('resource', True, resource_base='ParticleProcessMaterial')
        self.catalog = SimpleNamespace(
            resource_bases=frozenset(('ParticleProcessMaterial',)),
            classes={'GPUParticles2D': SimpleNamespace(kind='node', properties={'process_material': prop})},
            as_dict=lambda: {'classes': [{'class_name': 'GPUParticles2D', 'native_base': 'Node2D'}]})
        self.observation = {
            'resource_types': [{'class_name': 'ParticleProcessMaterial', 'exists': True,
                                'inheritance': ['ParticleProcessMaterial', 'Material', 'Resource', 'RefCounted', 'Object']}],
            'classes': [{'class_name': 'GPUParticles2D', 'exists': True, 'parent': 'Node2D',
                         'can_instantiate': True, 'singleton': False,
                         'properties': [{'name': 'process_material', 'matches': [
                             {'name': 'process_material', 'type': 24, 'setter': 'set_process_material',
                              'hint': 17, 'hint_string': 'Material', 'usage': 6}]}]}]}

    def native_property(self, observation=None):
        return (observation or self.observation)['classes'][0]['properties'][0]['matches'][0]

    def test_narrow_resource_subtype_and_exact_type_are_admitted(self):
        self.assertEqual(probe.compare(self.catalog, self.observation), [])
        self.native_property()['hint_string'] = 'ParticleProcessMaterial'
        self.assertEqual(probe.compare(self.catalog, self.observation), [])

    def test_resource_hint_union_accepts_only_a_proven_ancestor(self):
        self.native_property()['hint_string'] = 'Texture2D,Material'
        self.assertEqual(probe.compare(self.catalog, self.observation), [])
        self.native_property()['hint_string'] = 'Texture2D,ShaderMaterial'
        self.assertEqual(probe.compare(self.catalog, self.observation)[0]['code'], 'RESOURCE_BASE')

    def test_candidate_cannot_widen_native_subtype_to_material(self):
        self.catalog.resource_bases = frozenset(('Material',))
        self.catalog.classes['GPUParticles2D'].properties['process_material'] = probe.contract.PropertySpec(
            'resource', True, resource_base='Material')
        self.observation['resource_types'][0].update(class_name='Material',
            inheritance=['Material', 'Resource', 'RefCounted', 'Object'])
        self.native_property()['hint_string'] = 'ParticleProcessMaterial'
        self.assertEqual(probe.compare(self.catalog, self.observation)[0]['code'], 'RESOURCE_BASE')

    def test_wrong_hint_kind_or_invalid_hint_does_not_prove_compatibility(self):
        for updates in ({'hint': 0}, {'hint': True}, {'hint_string': ''},
                        {'hint_string': 'Material,'}, {'hint_string': 17}):
            with self.subTest(updates=updates):
                observation = copy.deepcopy(self.observation)
                self.native_property(observation).update(updates)
                self.assertEqual(probe.compare(self.catalog, observation)[0]['code'], 'RESOURCE_BASE')

    def test_missing_duplicate_or_forged_resource_set_is_rejected(self):
        for rows in (None, [], self.observation['resource_types'] * 2,
                     [{'class_name': 'Other', 'exists': True, 'inheritance': ['Other', 'Object']}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                probe.compare(self.catalog, {**self.observation, 'resource_types': rows})

    def test_bad_lineage_is_rejected_and_unknown_class_is_a_finding(self):
        for changes in ({'exists': 1}, {'inheritance': ['Material', 'Object']},
                        {'inheritance': ['ParticleProcessMaterial', 'Resource']},
                        {'inheritance': ['ParticleProcessMaterial', 'Resource', 'Resource', 'Object']},
                        {'exists': False}):
            observation = copy.deepcopy(self.observation)
            observation['resource_types'][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                probe.compare(self.catalog, observation)
        self.observation['resource_types'][0].update(exists=False, inheritance=[])
        self.assertIn('NOT_NATIVE_RESOURCE', [r['code'] for r in probe.compare(self.catalog, self.observation)])

    def test_lineage_that_is_not_a_resource_fails_even_with_matching_hint(self):
        self.observation['resource_types'][0]['inheritance'] = ['ParticleProcessMaterial', 'Object']
        self.native_property()['hint_string'] = 'Object'
        self.assertEqual(probe.compare(self.catalog, self.observation)[0]['code'], 'NOT_NATIVE_RESOURCE')


if __name__ == '__main__':
    unittest.main()
