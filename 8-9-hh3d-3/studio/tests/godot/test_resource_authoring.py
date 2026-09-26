"""Pure static tests for the O2 shape-resource candidate contract."""
from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location('o2_resource_authoring', STUDIO / 'godot-addon/resource_authoring.py')
resource = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = resource
SPEC.loader.exec_module(resource)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class ResourceAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.context = resource.ValidationContext(
            'project.fixture', 'sha256:' + '1' * 64, 'sha256:' + '2' * 64,
            4, 'lease.fixture', 9, 31000, 1000,
            (resource.NodeState('root', None, 'Node2D', 'Root'),
             resource.NodeState('collider', 'root', 'CollisionShape2D', 'Collider'),
             resource.NodeState('collider3d', 'root', 'CollisionShape3D', 'Collider3D')))

    def request(self, operation='scene.resource.create', *, payload=None, target=None, context=None, **changes):
        context = context or self.context
        if payload is None:
            payload = {'resource_id': 'shape.rect', 'resource_type': 'RectangleShape2D',
                       'properties': {'size': [8, 4]}}
        payload = copy.deepcopy(payload)
        payload.setdefault('expected_generation', context.generation)
        payload.setdefault('expected_project_revision', context.project_revision)
        values = dict(command_id='command.fixture', project_id=context.project_id,
                      operation=operation, lease_id=context.lease_id,
                      fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
                      target=target or {'stable_id': 'collider'}, payload=payload,
                      payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(), deadline_ms=2000)
        values.update(changes)
        return Request(**values)

    def validate(self, request=None, context=None):
        return resource.validate_request(request or self.request(), context or self.context)

    def reject(self, request, code=None, *, context=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context)
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_all_four_shape_types_and_dimensions(self):
        cases = [
            ('RectangleShape2D', {'size': [2, 3]}, 'collider'),
            ('CapsuleShape2D', {'radius': 2, 'height': 5}, 'collider'),
            ('BoxShape3D', {'size': [2, 3, 4]}, 'collider3d'),
            ('CapsuleShape3D', {'radius': 2.5, 'height': 5}, 'collider3d'),
        ]
        for shape, properties, node in cases:
            with self.subTest(shape=shape):
                result = self.validate(self.request(payload={'resource_id': 'shape.' + shape.lower(),
                    'resource_type': shape, 'properties': properties}, target={'stable_id': node}))
                self.assertEqual(result.projection['operation'], 'scene.resource.create')
                self.assertEqual(result.preview['authority'], 0)

    def test_capsule_requires_height_at_least_two_radii(self):
        for shape, node in [('CapsuleShape2D', 'collider'), ('CapsuleShape3D', 'collider3d')]:
            self.reject(self.request(payload={'resource_id': 'bad', 'resource_type': shape,
                                              'properties': {'radius': 3, 'height': 5}},
                                     target={'stable_id': node}), 'AUTHORING_CAPSULE_DIMENSIONS')

    def test_wrong_node_class_and_unknown_resource_type_reject(self):
        self.reject(self.request(target={'stable_id': 'collider3d'}), 'AUTHORING_RESOURCE_NODE_TYPE')
        self.reject(self.request(payload={'resource_id': 'x', 'resource_type': 'CircleShape2D',
                                          'properties': {'radius': 1}},), 'AUTHORING_RESOURCE_TYPE')
        self.reject(self.request(payload={'resource_id': 'x', 'resource_type': [],
                                          'properties': {'size': [1, 2]}}), 'AUTHORING_RESOURCE_TYPE')
        bad_state = resource.ResourceState('shape', 'collider', 'RectangleShape2D',
                                           properties={'size': [1, 2]})
        object.__setattr__(bad_state, 'resource_type', [])
        bad_context = replace(self.context, resources=(bad_state,))
        self.reject(self.request(context=bad_context), 'AUTHORING_RESOURCE_STATE', context=bad_context)

    def test_typed_finite_dimensions_and_bounds(self):
        for properties in ({'size': [True, 2]}, {'size': [0, 2]}, {'size': [1, 2, 3]},
                           {'size': [10001, 2]}):
            with self.subTest(properties=properties):
                request = self.request(payload={'resource_id': 'x', 'resource_type': 'RectangleShape2D',
                                                'properties': properties})
                self.reject(request, 'AUTHORING_RESOURCE_PROPERTY_TYPE')

    def test_extra_payload_and_extra_properties_reject(self):
        self.reject(self.request(payload={'resource_id': 'x', 'resource_type': 'RectangleShape2D',
                                          'properties': {'size': [1, 2]}, 'extra': 1}), 'AUTHORING_INVALID_SHAPE')
        self.reject(self.request(payload={'resource_id': 'x', 'resource_type': 'RectangleShape2D',
                                          'properties': {'size': [1, 2], 'radius': 1}}),
                    'AUTHORING_RESOURCE_PROPERTY_REJECTED')

    def test_create_duplicate_and_update_unknown(self):
        context = replace(self.context, resources=(resource.ResourceState('shape.rect', 'collider',
                            'RectangleShape2D', properties={'size': [1, 2]}),))
        self.reject(self.request(), 'AUTHORING_DUPLICATE_RESOURCE_ID', context=context)
        update = self.request('scene.resource.update', payload={'resource_id': 'missing',
            'resource_type': 'RectangleShape2D', 'changes': {'size': [1, 2]}})
        self.reject(update, 'AUTHORING_UNKNOWN_RESOURCE', context=context)

    def test_update_binds_owner_class_and_rejects_shared(self):
        state = resource.ResourceState('shape.rect', 'collider', 'RectangleShape2D',
                                       properties={'size': [1, 2]})
        context = replace(self.context, resources=(state,))
        update = self.request('scene.resource.update', payload={'resource_id': 'shape.rect',
            'resource_type': 'RectangleShape2D', 'changes': {'size': [4, 5]}})
        self.assertEqual(self.validate(update, context).preview['effective_properties']['size'], [4, 5])
        self.reject(update, 'AUTHORING_RESOURCE_OWNER_MISMATCH',
                    context=replace(context, resources=(resource.ResourceState('shape.rect', 'collider3d',
                        'RectangleShape2D', properties={'size': [1, 2]}),)))
        self.reject(update, 'AUTHORING_RESOURCE_SHARED',
                    context=replace(context, resources=(resource.ResourceState('shape.rect', 'collider',
                        'RectangleShape2D', True, {'size': [1, 2]}),)))
        self.reject(update, 'AUTHORING_RESOURCE_TYPE_MISMATCH',
                    context=replace(context, resources=(resource.ResourceState('shape.rect', 'collider',
                        'BoxShape3D', properties={'size': [1, 2, 3]}),)))

    def test_partial_capsule_update_checks_resulting_invariant(self):
        state = resource.ResourceState('cap', 'collider', 'CapsuleShape2D',
                                       properties={'radius': 2, 'height': 5})
        context = replace(self.context, resources=(state,))
        update = self.request('scene.resource.update', payload={'resource_id': 'cap',
            'resource_type': 'CapsuleShape2D', 'changes': {'radius': 3}})
        self.reject(update, 'AUTHORING_CAPSULE_DIMENSIONS', context=context)

    def test_stale_context_lease_revision_generation_deadline_and_stop(self):
        cases = [(replace(self.context, stopped=True), 'AUTHORING_STOPPED'),
                 (replace(self.context, generation=5), 'AUTHORING_STALE_GENERATION'),
                 (replace(self.context, revision='sha256:' + '3' * 64), 'AUTHORING_STALE_REVISION'),
                 (replace(self.context, fencing_epoch=10), 'AUTHORING_STALE_LEASE'),
                 (replace(self.context, lease_id='lease.other'), 'AUTHORING_STALE_LEASE'),
                 (replace(self.context, lease_expires_ms=1500), 'AUTHORING_DEADLINE_EXPIRED')]
        for context, code in cases:
            self.reject(self.request(), code, context=context)
        self.reject(self.request(expected_revision='sha256:' + '3' * 64), 'AUTHORING_STALE_REVISION')

    def test_context_rejects_untrusted_duplicate_or_unknown_resources(self):
        duplicate = resource.ResourceState('shape', 'collider', 'RectangleShape2D', properties={'size': [1, 2]})
        self.reject(self.request(), 'AUTHORING_RESOURCE_STATE',
                    context=replace(self.context, resources=(duplicate, duplicate)))
        bad_owner = resource.ResourceState('shape', 'missing', 'RectangleShape2D', properties={'size': [1, 2]})
        self.reject(self.request(), 'AUTHORING_RESOURCE_STATE', context=replace(self.context, resources=(bad_owner,)))

    def test_projection_and_preview_are_detached_and_authority_zero(self):
        result = self.validate()
        projection = result.projection
        projection['payload']['properties']['size'][0] = 999
        self.assertEqual(result.projection['payload']['properties']['size'], [8, 4])
        preview = result.preview
        preview['authority'] = 99
        self.assertEqual(result.preview['authority'], 0)
        self.assertFalse(result.preview['changes_applied'])
        self.assertFalse(result.preview['runtime_authorized'])

    def test_target_and_stopped_context_and_script_like_operations_reject(self):
        self.reject(self.request(target={'path': 'res://scene.tscn'}), 'AUTHORING_INVALID_SHAPE')
        self.reject(self.request('script_text.replace'), 'AUTHORING_OPERATION_DISABLED')
        self.reject(self.request('scene.resource.remove'), 'AUTHORING_OPERATION_DISABLED')

    def test_project_revision_and_payload_hash_checks(self):
        payload = {'resource_id': 'x', 'resource_type': 'RectangleShape2D', 'properties': {'size': [1, 2]},
                   'expected_generation': 8}
        self.reject(self.request(payload=payload), 'AUTHORING_STALE_GENERATION')
        self.reject(self.request(expected_revision='sha256:' + '3' * 64), 'AUTHORING_STALE_REVISION')
        wire = self.request().as_dict()
        wire['payload_hash'] = 'sha256:' + '0' * 64
        self.reject(wire, 'PAYLOAD_HASH_MISMATCH')


if __name__ == '__main__':
    unittest.main()
