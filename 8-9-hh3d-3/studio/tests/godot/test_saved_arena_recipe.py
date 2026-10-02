"""Static recipe and contract tests; no Godot, file publication or native claim."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from studio.tests.godot import saved_arena_recipe as recipe
from studio.protocol.core import ValidationError, canonical_bytes, parse_json


class SavedArenaRecipeTests(unittest.TestCase):
    def test_document_is_reproducible_detached_and_explicitly_planned(self):
        first = recipe.build_recipe()
        frozen = canonical_bytes(first)
        self.assertEqual(first, parse_json(frozen))
        self.assertEqual(frozen, canonical_bytes(recipe.build_recipe()))
        self.assertEqual(first['schema'], 'hh-o2-saved-arena-recipe-1')
        self.assertEqual(first['state_kind'], 'PLANNED_NOT_NATIVE')
        self.assertEqual(first['authority'], 0)
        for key in ('runtime_authorized', 'public_ack', 'native_observed'):
            self.assertIs(first[key], False)
        self.assertEqual(first['root_bootstrap'], {
            'kind': 'FIXED_SCRIPT_FREE_ROOT', 'create_command': False,
            'properties_are_planned_defaults': True, 'native_readback_required': True})
        self.assertEqual(first['ownership'], {'root_owner': None, 'descendant_owner_stable_id': 'root'})
        self.assertEqual(first['catalog_sha256'], recipe._NODE.load_catalog().digest[7:])
        first['node_commands'][0]['payload']['properties']['position'][0] = 999
        first['expected_snapshot']['resources'][0]['properties']['size'][0] = 999
        self.assertEqual(frozen, canonical_bytes(recipe.build_recipe()))

    def test_every_node_and_resource_request_reaches_existing_validator(self):
        with patch.object(recipe._NODE, 'validate_request', wraps=recipe._NODE.validate_request) as nodes, \
                patch.object(recipe._RESOURCE, 'validate_request',
                             wraps=recipe._RESOURCE.validate_request) as resources:
            value = recipe.build_recipe()
        self.assertEqual(nodes.call_count, 6)
        self.assertEqual(resources.call_count, 3)
        for calls, commands in ((nodes.call_args_list, value['node_commands']),
                                (resources.call_args_list, value['resource_commands'])):
            for call, command in zip(calls, commands):
                request, context = call.args[:2]
                self.assertEqual(command['command_id'], request.command_id)
                self.assertEqual(value['request_digests'][request.command_id], request.digest)
                self.assertEqual(command['expected_revision'], context.revision)
                self.assertNotIn('expected_project_revision', command['payload'])
                self.assertEqual(command['payload']['expected_generation'], 1)
        # Each resource sees the full real planned ancestry, never a collider
        # relabeled as a direct child of root to bypass the context contract.
        for call in resources.call_args_list:
            context = call.args[1]
            identities = {node.stable_id: node for node in context.nodes}
            for parent, kind in (('player', 'CharacterBody2D'), ('floor', 'StaticBody2D'),
                                 ('wall', 'StaticBody2D')):
                self.assertEqual(identities[parent].node_type, kind)
                self.assertEqual(identities[parent + '_shape'].parent_id, parent)

    def test_expected_geometry_preserves_physics_fixture_world(self):
        value = recipe.build_recipe()
        nodes = {row['stable_id']: row for row in value['expected_snapshot']['nodes']}
        shapes = {row['owner_stable_id']: row for row in value['expected_snapshot']['resources']}
        self.assertEqual(len(nodes), 7)
        self.assertEqual(len(shapes), 3)
        self.assertEqual(nodes['root'], {**value['root'], 'parent_id': None})
        for identity, position, size, layer in (
                ('player', [32, 174], [16, 32], 2),
                ('floor', [200, 200], [400, 20], 1),
                ('wall', [300, 110], [20, 160], 1)):
            self.assertEqual(nodes[identity]['properties']['position'], position)
            self.assertEqual(nodes[identity]['properties']['collision_layer'], layer)
            self.assertEqual(nodes[identity]['properties']['collision_mask'], 1)
            self.assertEqual(nodes[identity + '_shape']['name'], 'Shape')
            self.assertNotIn('shape', nodes[identity + '_shape']['properties'])
            self.assertEqual(shapes[identity + '_shape'], {
                'resource_id': 'shape.' + identity, 'owner_stable_id': identity + '_shape',
                'resource_type': 'RectangleShape2D', 'properties': {'size': size}})

    def test_body_collision_fields_require_uint32_in_both_candidate_classes(self):
        value = recipe.build_recipe()
        context = recipe._planned_context(recipe._NODE, value['initial_snapshot'],
                                          value['planned_project_revision'])
        for kind in ('CharacterBody2D', 'StaticBody2D'):
            for field in ('collision_layer', 'collision_mask'):
                for number in (0, 4294967295, -1, 4294967296, True, 1.5):
                    request = recipe._request(context, 'scene.node.create', 'recipe.test.body', 'root',
                        {'stable_id': 'body', 'node_type': kind, 'name': 'Body', 'properties': {field: number}})
                    with self.subTest(kind=kind, field=field, number=number):
                        if type(number) is int and 0 <= number <= 4294967295:
                            recipe._NODE.validate_request(request, context)
                        else:
                            with self.assertRaises(ValidationError) as raised:
                                recipe._NODE.validate_request(request, context)
                            self.assertEqual(raised.exception.code, 'AUTHORING_PROPERTY_TYPE')

    def test_resource_ancestor_support_keeps_class_and_hierarchy_rejections(self):
        value = recipe.build_recipe()
        context = recipe._planned_context(recipe._RESOURCE, value['expected_snapshot'],
                                          value['planned_project_revision'])
        request = recipe._request(context, 'scene.resource.create', 'recipe.test.shape', 'player_shape',
            {'resource_id': 'shape.new', 'resource_type': 'RectangleShape2D', 'properties': {'size': [16, 32]}})
        recipe._RESOURCE.validate_request(request, context)
        for change, code in (({'node_type': 'EditorPlugin'}, 'AUTHORING_NODE_STATE'),
                             ({'parent_id': 'missing'}, 'AUTHORING_HIERARCHY')):
            changed = replace(context, nodes=tuple(replace(node, **change) if node.stable_id == 'player'
                                                  else node for node in context.nodes))
            with self.subTest(change=change), self.assertRaises(ValidationError) as raised:
                recipe._RESOURCE.validate_request(request, changed)
            self.assertEqual(raised.exception.code, code)

    def test_validator_rejection_cannot_return_partial_recipe(self):
        with patch.object(recipe._RESOURCE, 'validate_request', side_effect=RuntimeError('REJECT_RECIPE')):
            with self.assertRaisesRegex(RuntimeError, '^REJECT_RECIPE$'):
                recipe.build_recipe()

    def test_source_manifest_names_every_recipe_input_under_studio(self):
        paths = recipe.source_paths()
        self.assertEqual(len(paths), len(set(paths)))
        for name in paths:
            path = (recipe.STUDIO / name).resolve(strict=True)
            self.assertTrue(path.is_relative_to(recipe.STUDIO))
            self.assertTrue(path.is_file())


if __name__ == '__main__':
    unittest.main()
