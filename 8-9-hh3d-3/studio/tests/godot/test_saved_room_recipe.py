"""Pure saved-room recipe tests; no Godot/editor/import/native claim."""
import unittest
from unittest.mock import patch

from studio.tests.godot import saved_room_recipe as recipe
from studio.protocol.core import ValidationError, canonical_bytes, parse_json


class SavedRoomRecipeTests(unittest.TestCase):
    def admission(self):
        return {'project_id': 'project.live.room', 'revision': 'sha256:' + '1' * 64,
                'project_revision': 'sha256:' + '2' * 64, 'generation': 7,
                'lease_id': 'lease.live.room', 'fencing_epoch': 3,
                'lease_expires_ms': 50_000, 'now_ms': 1_000}

    def test_recipe_is_3d_typed_and_blender_reference_is_pending(self):
        value = recipe.build_recipe()
        self.assertEqual((len(value['node_commands']), len(value['resource_commands'])), (11, 3))
        self.assertEqual((len(value['expected_snapshot']['nodes']),
                          len(value['expected_snapshot']['resources'])), (9, 3))
        nodes = {row['stable_id']: row for row in value['expected_snapshot']['nodes']}
        self.assertEqual(nodes['root']['node_type'], 'Node3D')
        self.assertEqual(nodes['avatar']['node_type'], 'CharacterBody3D')
        self.assertEqual(nodes['avatar_mesh']['node_type'], 'MeshInstance3D')
        self.assertEqual(nodes['camera']['node_type'], 'Camera3D')
        self.assertEqual({nodes[key]['node_type'] for key in ('platform', 'trigger')}, {'Area3D'})
        self.assertEqual({nodes[key]['node_type'] for key in
                          ('avatar_shape', 'platform_shape', 'trigger_shape')}, {'CollisionShape3D'})
        resources = {row['resource_id']: row for row in value['expected_snapshot']['resources']}
        self.assertEqual(resources['shape.avatar']['resource_type'], 'CapsuleShape3D')
        self.assertEqual({resources[key]['resource_type'] for key in
                          ('shape.platform', 'shape.trigger')}, {'BoxShape3D'})
        asset = value['asset_bindings'][0]
        self.assertEqual(asset['path'], 'assets/avatar.glb')
        self.assertEqual(asset['source'], 'Blender')
        self.assertTrue(asset['import_readback_required'])
        self.assertFalse(asset['asset_import_verified'])
        self.assertFalse(asset['native_observed'])

    def test_binding_is_detached_and_requires_fresh_admission(self):
        admission = self.admission()
        value = recipe.bind_recipe_to_owner_admission(recipe.build_recipe(), admission)
        self.assertEqual(value['schema'], recipe.ADMISSION_SCHEMA)
        self.assertEqual(len(value['commands']), 14)
        self.assertFalse(value['runtime_authorized'])
        self.assertFalse(value['native_observed'])
        self.assertEqual(value['execution'], {
            'mode': 'DETACHED_PLAN_ONLY', 'sequential_apply_supported': False,
            'requires_fresh_owner_admission_per_effect': True})
        self.assertEqual({row['request']['expected_revision'] for row in value['commands']},
                         {admission['revision']})
        self.assertEqual({row['request']['payload']['expected_generation']
                          for row in value['commands']}, {admission['generation']})

    def test_recipe_is_canonical_and_reproducible(self):
        first = recipe.build_recipe()
        frozen = canonical_bytes(first)
        self.assertEqual(first, parse_json(frozen))
        self.assertEqual(frozen, canonical_bytes(recipe.build_recipe()))
        self.assertEqual(first['catalog_sha256'], recipe._NODE.load_catalog().digest[7:])
        self.assertEqual(first['asset_resource_refs'], {'mesh.avatar': 'avatar_blender'})

    def test_rejects_stale_admission_and_asset_traversal(self):
        value = recipe.build_recipe()
        with self.assertRaisesRegex(ValidationError, 'ROOM_ADMISSION_LIFETIME'):
            recipe.bind_recipe_to_owner_admission(value,
                {**self.admission(), 'now_ms': 50_000})
        altered = recipe.build_recipe()
        altered['asset_bindings'][0]['path'] = '../avatar.glb'
        with self.assertRaisesRegex(ValidationError, 'ROOM_ASSET_IDENTITY'):
            recipe.bind_recipe_to_owner_admission(altered, self.admission())
        altered = recipe.build_recipe()
        altered['asset_resource_refs']['mesh.avatar'] = 'other_asset'
        with self.assertRaisesRegex(ValidationError, 'ROOM_ASSET_REFERENCE'):
            recipe.bind_recipe_to_owner_admission(altered, self.admission())

    def test_rejects_tampered_class_and_dimensions(self):
        altered = recipe.build_recipe()
        altered['node_commands'][0]['payload']['node_type'] = 'EditorPlugin'
        with self.assertRaisesRegex(ValidationError, 'AUTHORING_CLASS_REJECTED'):
            recipe.bind_recipe_to_owner_admission(altered, self.admission())
        altered = recipe.build_recipe()
        for row in altered['resource_commands']:
            if row['payload']['resource_type'] == 'CapsuleShape3D':
                row['payload']['properties']['height'] = 0.1
        with self.assertRaisesRegex(ValidationError, 'AUTHORING_CAPSULE_DIMENSIONS'):
            recipe.bind_recipe_to_owner_admission(altered, self.admission())

    def test_resource_allowlist_accepts_3d_ancestors_and_rejects_broken_parent(self):
        value = recipe.build_recipe()
        resource_snapshot = {**value['expected_snapshot'], 'resources': []}
        context = recipe._resource_context(resource_snapshot,
                                            value['planned_project_revision'])
        command = value['resource_commands'][0]
        request = recipe._request(context, command['operation'], command['command_id'],
                                  command['target_stable_id'], command['payload'])
        recipe._RESOURCE.validate_request(request, context)
        broken = list(context.nodes)
        broken = tuple(recipe._RESOURCE.NodeState(n.stable_id, 'missing' if n.stable_id ==
                         'avatar_shape' else n.parent_id, n.node_type, n.name) for n in broken)
        invalid = context.__class__(context.project_id, context.revision,
            context.project_revision, context.generation, context.lease_id,
            context.fencing_epoch, context.lease_expires_ms, context.now_ms,
            broken, context.resources)
        with self.assertRaisesRegex(ValidationError, 'AUTHORING_HIERARCHY'):
            recipe._RESOURCE.validate_request(request, invalid)

    def test_all_node_and_resource_projections_reach_validators(self):
        with patch.object(recipe._NODE, 'validate_request', wraps=recipe._NODE.validate_request) as nodes, \
                patch.object(recipe._RESOURCE, 'validate_request',
                             wraps=recipe._RESOURCE.validate_request) as resources:
            value = recipe.build_recipe()
        self.assertEqual(nodes.call_count, 11)
        self.assertEqual(resources.call_count, 3)
        self.assertEqual(len(value['request_digests']), 14)


if __name__ == '__main__':
    unittest.main()
