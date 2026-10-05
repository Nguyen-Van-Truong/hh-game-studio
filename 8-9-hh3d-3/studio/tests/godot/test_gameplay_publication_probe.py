"""Pure arena publication composition checks; never start an engine or Docker."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from studio.tests.godot import linux_probe_fixtures as fixtures
from studio.tests.godot import run_gameplay_publication_probe as probe
from studio.tests.godot import run_linux_probe as linux_probe


class ArenaPublicationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.case = copy.deepcopy(fixtures.FIXTURES[probe.ARENA_FIXTURE])
        self.case.update(scene=fixtures.SCENE, project='config_version=5\n')
        self.candidate = linux_probe.case_files(self.case)
        self.candidate.pop('project.godot')
        temp = tempfile.TemporaryDirectory(prefix='hh-arena-publication-')
        self.addCleanup(temp.cleanup)
        self.source = Path(temp.name) / 'source'
        self.frozen = Path(temp.name) / 'frozen'
        self.hashes = {}
        for name in probe.ARENA_SOURCE_FILES.values():
            self.write_source(name, (probe.STUDIO / name).read_bytes())

    def write_source(self, name, raw):
        for root in (self.source, self.frozen):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.hashes[name] = hashlib.sha256(raw).hexdigest()

    def verify_sources(self):
        probe.verify_fixture_sources(probe.ARENA_FIXTURE, self.case, self.candidate,
                                     self.hashes, source_root=self.source,
                                     frozen_root=self.frozen)

    def test_selector_adds_only_exact_arena_and_preserves_previous_cases(self):
        for name in fixtures.FIXTURES:
            self.assertEqual(probe.publication_fixture_allowed(name, fixtures.FIXTURES),
                             name.startswith('gameplay_source_') or name == probe.ARENA_FIXTURE)
        for name in ('gameplay_arena_physics_other', 'gameplay_source_unknown'):
            self.assertFalse(probe.publication_fixture_allowed(name, fixtures.FIXTURES))
        self.assertFalse(probe.publication_fixture_allowed('gameplay_arena_physics_other',
                                                          {'gameplay_arena_physics_other': {}}))

    def test_arena_policy_cannot_disable_or_trim_dependency_readback(self):
        self.assertEqual(probe.publication_dependency_policy(probe.ARENA_FIXTURE, self.case),
                         {'dependency_observation_required': True,
                          'dependency_observation_files': probe.ARENA_DEPENDENCY_FILES})
        for changes in ({'dependency_observation': False}, {'dependency_observation': 1},
                        {'dependency_files': probe.ARENA_DEPENDENCY_FILES[:-1]},
                        {'dependency_files': probe.ARENA_DEPENDENCY_FILES + ('scripts/extra.gd',)}):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(RuntimeError, '^ARENA_DEPENDENCY_POLICY_REQUIRED$'):
                    probe.publication_dependency_policy(probe.ARENA_FIXTURE, {**self.case, **changes})

    def test_real_loaded_templates_match_freeze_with_lf_or_crlf(self):
        self.verify_sources()
        self.assertLessEqual(len(self.candidate['scripts/fixture_actor.gd']), 16_384)
        for target, source in probe.ARENA_SOURCE_FILES.items():
            self.write_source(source, self.candidate[target].replace(b'\n', b'\r\n'))
        self.verify_sources()

    def test_missing_projectile_or_unfrozen_input_rejects(self):
        original = self.candidate.pop('scenes/projectile.tscn')
        with self.assertRaisesRegex(RuntimeError, '^ARENA_TEMPLATE_FREEZE_MISMATCH$'):
            self.verify_sources()
        self.candidate['scenes/projectile.tscn'] = original
        self.hashes.pop(probe.ARENA_SOURCE_FILES['scenes/projectile.tscn'])
        with self.assertRaisesRegex(RuntimeError, '^ARENA_SOURCE_BINDING_MISSING$'):
            self.verify_sources()

    def test_stale_imported_template_rejects_even_when_live_bytes_match_freeze(self):
        self.case['script'] += '# stale imported template\n'
        self.candidate['scripts/fixture_actor.gd'] = self.case['script'].encode()
        with self.assertRaisesRegex(RuntimeError, '^ARENA_TEMPLATE_FREEZE_MISMATCH$'):
            self.verify_sources()

    def test_current_or_frozen_source_drift_rejects(self):
        for root in (self.source, self.frozen):
            for name in probe.ARENA_SOURCE_FILES.values():
                with self.subTest(root=root.name, name=name):
                    path = root / name
                    original = path.read_bytes()
                    path.write_bytes(original + b'# drift\n')
                    with self.assertRaisesRegex(RuntimeError, '^ARENA_SOURCE_CHANGED$'):
                        self.verify_sources()
                    path.write_bytes(original)

    def graph(self):
        edges = {'scenes/fixture.tscn': [{'kind': 'scene_ext_resource',
                                        'target': 'scripts/fixture_actor.gd'}],
                 'scripts/fixture_actor.gd': [{'kind': 'script_preload',
                                             'target': 'scenes/projectile.tscn'}],
                 'scenes/projectile.tscn': []}
        if probe.SAVED_ARENA_PATH in self.candidate:
            edges['scenes/fixture.tscn'].append({'kind': 'scene_ext_resource',
                                               'target': probe.SAVED_ARENA_PATH})
            edges[probe.SAVED_ARENA_PATH] = []
        return {'schema': 'hh-gameplay-dependency-observation-1', 'version': 1,
                'entrypoint': 'scenes/fixture.tscn',
                'nodes': [{'path': path, 'kind': 'script' if path.endswith('.gd') else 'scene',
                           'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                           'edges': edges[path]} for path, raw in self.candidate.items()]}

    def parse_graph(self, graph):
        return linux_probe.dependency_observation.parse_dependency_observation(
            'HH_PROBE_DEPENDENCY ' + json.dumps(graph) + '\n', self.candidate)

    def test_exact_graph_uses_byte_bound_contract_and_retains_authority_zero(self):
        report = self.parse_graph(self.graph())
        probe.verify_fixture_observation(probe.ARENA_FIXTURE,
                                         {'fixture_observed': True, 'dependency_observation': report})
        self.assertEqual(report['authority'], 0)
        self.assertFalse(report['dependency_closure_verified'])
        self.assertFalse(report['public_ack'])
        with self.assertRaisesRegex(RuntimeError, '^NATIVE_FIXTURE_NOT_OBSERVED$'):
            probe.verify_fixture_observation(probe.ARENA_FIXTURE,
                                             {'fixture_observed': False, 'dependency_observation': report})
        report['observation']['nodes'][1]['edges'] = []
        with self.assertRaisesRegex(RuntimeError, '^ARENA_DEPENDENCY_GRAPH_MISMATCH$'):
            probe.verify_fixture_observation(probe.ARENA_FIXTURE,
                                             {'fixture_observed': True, 'dependency_observation': report})

    def test_missing_or_stale_projectile_native_observation_rejects(self):
        for defect in ('missing', 'stale'):
            graph = self.graph()
            node = next(row for row in graph['nodes'] if row['path'] == 'scenes/projectile.tscn')
            if defect == 'missing':
                graph['nodes'].remove(node)
            else:
                node['sha256'] = '0' * 64
            with self.subTest(defect=defect), self.assertRaises(ValueError):
                self.parse_graph(graph)

    def saved_case(self):
        # Opaque verifier output, deliberately not a hand-authored runnable arena.
        raw = b'; native builder bytes stand-in for a pure composition test\n'
        self.case = probe.saved_arena_case(probe.ARENA_FIXTURE, self.case, raw)
        self.candidate = linux_probe.case_files(self.case)
        self.candidate.pop('project.godot')
        return raw

    def test_saved_arena_composition_preserves_bytes_and_requires_four_file_policy(self):
        original = copy.deepcopy(self.case)
        raw = self.saved_case()
        self.assertEqual(self.candidate[probe.SAVED_ARENA_PATH], raw)
        self.assertEqual(set(self.candidate), set(probe.SAVED_ARENA_DEPENDENCY_FILES))
        self.assertIn('type="PackedScene" path="res://scenes/arena.tscn"', self.case['scene'])
        self.assertIn('saved_world = ExtResource("2_world")', self.case['scene'])
        self.assertTrue(self.case['expected_state']['saved_world_instantiated'])
        self.assertTrue(self.case['expected_state']['saved_actors_resolved'])
        self.assertTrue(self.case['expected_state']['saved_hud_resolved'])
        self.assertEqual(self.case['expected_state']['saved_world_path'], 'res://scenes/arena.tscn')
        self.assertEqual(self.case['expected_state']['saved_actor_paths'],
                         {'pickup': 'Pickup', 'bot': 'Bot', 'camera': 'Camera'})
        self.assertNotIn('saved_world_instantiated', original['expected_state'])
        self.assertEqual(probe.publication_dependency_policy(probe.ARENA_FIXTURE,
            self.case, saved_arena=True)['dependency_observation_files'],
            probe.SAVED_ARENA_DEPENDENCY_FILES)
        with self.assertRaisesRegex(RuntimeError, 'ARENA_DEPENDENCY_POLICY_REQUIRED'):
            probe.publication_dependency_policy(probe.ARENA_FIXTURE, self.case)
        with self.assertRaisesRegex(RuntimeError, 'ARENA_DEPENDENCY_POLICY_REQUIRED'):
            probe.publication_dependency_policy(probe.ARENA_FIXTURE, original, saved_arena=True)
        with self.assertRaisesRegex(RuntimeError, 'SAVED_ARENA_FIXTURE_REQUIRED'):
            probe.saved_arena_case('gameplay_source_multifile', original, raw)

    def test_saved_arena_cli_rejects_other_fixture_before_admission(self):
        with mock.patch('sys.argv', ['probe', '--run-id', 'o2-publication-pure',
                '--saved-arena', 'builder-run']), mock.patch.object(probe, 'idle_window') as idle:
            with self.assertRaises(SystemExit) as error:
                probe.main()
        self.assertEqual(error.exception.code, 2)
        idle.assert_not_called()

    def test_saved_arena_native_graph_requires_instanced_scene_and_no_scene_dependencies(self):
        self.saved_case()
        graph = self.graph()
        graph['nodes'][0]['edges'].reverse()
        report = self.parse_graph(graph)
        observation = {'fixture_observed': True, 'dependency_observation': report}
        probe.verify_fixture_observation(probe.ARENA_FIXTURE, observation, saved_arena=True)
        for defect in ('missing_world', 'scene_dependency'):
            bad = copy.deepcopy(observation)
            nodes = bad['dependency_observation']['observation']['nodes']
            if defect == 'missing_world':
                nodes[:] = [row for row in nodes if row['path'] != probe.SAVED_ARENA_PATH]
            else:
                next(row for row in nodes if row['path'] == probe.SAVED_ARENA_PATH)['edges'] = [
                    {'kind': 'scene_ext_resource', 'target': 'scripts/fixture_actor.gd'}]
            with self.subTest(defect=defect), self.assertRaisesRegex(
                    RuntimeError, 'ARENA_DEPENDENCY_GRAPH_MISMATCH'):
                probe.verify_fixture_observation(probe.ARENA_FIXTURE, bad, saved_arena=True)

    def builder_proof(self):
        raw = self.saved_case()
        directory = self.source.parent / 'builder-run'
        directory.mkdir()
        contents = {'binding.json': b'{"test":"source binding"}\n',
                    'native-observation.json': b'{"test":"semantic observation"}\n'}
        for name, content in contents.items():
            (directory / name).write_bytes(content)
        provenance = {'schema': 'pure-test-provenance', 'run_id': 'builder-pure',
                      'files': {name: hashlib.sha256(value).hexdigest()
                                for name, value in contents.items()}}
        builder = mock.Mock()
        builder.verify_saved_arena.return_value = raw
        builder.saved_arena_provenance.return_value = provenance
        frozen = self.source.parent / 'saved-arena'
        returned, binding = probe.freeze_saved_arena(probe.ARENA_FIXTURE,
                                                     directory, frozen, builder)
        self.assertEqual(returned, raw)
        return directory, frozen, builder, binding

    def test_builder_verifier_and_exact_provenance_are_rechecked_before_use(self):
        directory, frozen, builder, binding = self.builder_proof()
        probe.verify_saved_arena_binding(directory, frozen, binding, builder, self.candidate)
        self.assertEqual(builder.verify_saved_arena.call_count, 2)
        self.assertEqual((frozen / 'arena.tscn').read_bytes(), self.candidate[probe.SAVED_ARENA_PATH])
        for name, digest in binding['provenance']['files'].items():
            self.assertEqual(hashlib.sha256((frozen / 'provenance' / name).read_bytes()).hexdigest(), digest)
        builder.verify_saved_arena.side_effect = RuntimeError('BUILDER_SOURCE_CHANGED')
        with self.assertRaisesRegex(RuntimeError, 'BUILDER_SOURCE_CHANGED'):
            probe.verify_saved_arena_binding(directory, frozen, binding, builder, self.candidate)

    def test_saved_arena_or_provenance_drift_rejects_before_dispatch(self):
        directory, frozen, builder, binding = self.builder_proof()
        def verify():
            probe.verify_saved_arena_binding(directory, frozen, binding, builder, self.candidate)
        for path in (directory / 'native-observation.json',
                     frozen / 'provenance/native-observation.json', frozen / 'arena.tscn'):
            original = path.read_bytes()
            path.write_bytes(original + b'changed\n')
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError,
                    'SAVED_ARENA_(PROVENANCE|SOURCE)_CHANGED'):
                verify()
            path.write_bytes(original)
        self.candidate[probe.SAVED_ARENA_PATH] += b'changed\n'
        with self.assertRaisesRegex(RuntimeError, 'SAVED_ARENA_SOURCE_CHANGED'):
            verify()

    def test_saved_arena_provenance_cannot_escape_its_directory(self):
        for name in ('../outside', '/outside', 'C:outside', 'a\\outside'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError,
                    'SAVED_ARENA_PROVENANCE_PATH'):
                probe._provenance_file(self.source, name)


if __name__ == '__main__':
    unittest.main()
