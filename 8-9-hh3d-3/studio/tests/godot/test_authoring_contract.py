"""O2 pure-Python contract tests. No native ClassDB/readback/undo claim."""
import copy
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
SPEC = importlib.util.spec_from_file_location('o2_authoring_contract', STUDIO / 'godot-addon/authoring_contract.py')
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class AuthoringContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = contract.load_catalog()

    def setUp(self):
        self.context = contract.ValidationContext(
            'project.fixture', 'sha256:' + '1' * 64, 'sha256:' + '2' * 64,
            1, 'lease.fixture', 7, 31000, 1000,
            (contract.NodeState('root', None, 'Node2D', 'Fixture'),
             contract.NodeState('actor', 'root', 'Sprite2D', 'Actor')),
            tuple(contract.ResourceState(base.lower(), base) for base in sorted(self.catalog.resource_bases)))

    def request(self, operation='scene.node.create', *, payload=None, target=None, **changes):
        if payload is None:
            payload = dict(stable_id='new.node', node_type='Node2D', name='NewNode', properties={'position': [1, 2]})
        payload = copy.deepcopy(payload)
        payload.setdefault('expected_generation', self.context.generation)
        payload.setdefault('expected_project_revision', self.context.project_revision)
        values = dict(command_id='command.fixture', project_id=self.context.project_id,
                      operation=operation, lease_id=self.context.lease_id, fencing_epoch=self.context.fencing_epoch,
                      expected_revision=self.context.revision, target=target or {'stable_id': 'root'},
                      payload=payload, payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                      deadline_ms=2000)
        values.update(changes)
        return Request(**values)

    def validate(self, request=None, context=None, catalog=None):
        return contract.validate_request(request or self.request(), context or self.context, catalog or self.catalog)

    def reject(self, request, code=None, *, context=None, catalog=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context, catalog)
        if code is not None:
            self.assertEqual(raised.exception.code, code)

    def payload(self, node_type, properties):
        return dict(stable_id='new.node', node_type=node_type, name='NewNode', properties=properties)

    def sample(self, spec):
        return {'bool': False, 'int': 0, 'float': 1.0, 'string': 'Original fixture',
                'vector2': [1.25, 2], 'vector3': [1, 2.5, 3], 'enum': 0,
                'resource': {'resource_id': (spec.resource_base or 'unused').lower()}}[spec.type]

    def test_each_candidate_node_accepts_own_and_inherited_typed_properties(self):
        seen = set()
        for name, spec in self.catalog.classes.items():
            if spec.kind != 'node':
                continue
            with self.subTest(node_type=name):
                properties = {p: self.sample(rule) for p, rule in spec.properties.items()}
                result = self.validate(self.request(payload=self.payload(name, properties)))
                self.assertEqual(result.projection['payload']['properties'], properties)
                self.assertFalse(result.preview['classdb_verified'])
                self.assertEqual(result.preview['native_tests_pending'], ['classdb_extraction', 'reject', 'readback', 'undo'])
                seen.add(name)
        self.assertEqual(len(seen), 20)
        self.assertIn('MeshInstance3D', seen)
        self.assertIn('position', self.catalog.classes['Button'].properties)
        self.assertIn('rotation', self.catalog.classes['CharacterBody2D'].properties)

    def test_every_class_rejects_unknown_property_or_non_node_creation(self):
        for name, spec in self.catalog.classes.items():
            with self.subTest(node_type=name):
                self.reject(self.request(payload=self.payload(name, {'unexpected': 1})),
                            'AUTHORING_PROPERTY_REJECTED' if spec.instantiable else 'AUTHORING_CLASS_REJECTED')
        self.reject(self.request(payload=self.payload('InputMap', {})), 'AUTHORING_CLASS_REJECTED')
        self.reject(self.request(payload=self.payload('EditorPlugin', {})), 'AUTHORING_CLASS_REJECTED')

    def test_every_property_rejects_wrong_variant_type(self):
        for name, spec in self.catalog.classes.items():
            for prop_name, rule in spec.properties.items():
                with self.subTest(node_type=name, property=prop_name):
                    bad = 123 if rule.type == 'string' else 'wrong-variant'
                    self.reject(self.request(payload=self.payload(name, {prop_name: bad})),
                                'AUTHORING_RESOURCE_REFERENCE' if rule.type == 'resource' else 'AUTHORING_PROPERTY_TYPE')

    def test_update_uses_observed_class_and_copies_the_request(self):
        request = self.request('scene.node.update', target={'stable_id': 'actor'},
                               payload={'changes': {'position': [3, 4], 'frame': 1}})
        result = self.validate(request)
        request.payload['changes']['position'][0] = 500
        first = result.projection
        self.assertEqual(first['payload']['changes']['position'], [3, 4])
        first['payload']['changes']['position'][0] = 600
        self.assertEqual(result.projection['payload']['changes']['position'], [3, 4])
        preview = result.preview
        preview['runtime_authorized'] = True
        self.assertFalse(result.preview['runtime_authorized'])
        self.assertNotIn('expected_project_revision', result.projection['payload'])
        self.assertEqual(result.preview['project_revision'], self.context.project_revision)

    def test_boolean_is_neither_integer_nor_enum_nor_vector_component(self):
        for cls, changes in [('Sprite2D', {'frame': True}), ('Camera3D', {'fov': True}),
                             ('Control', {'mouse_filter': True}), ('Node2D', {'position': [True, 1]})]:
            self.reject(self.request(payload=self.payload(cls, changes)), 'AUTHORING_PROPERTY_TYPE')

    def test_numeric_limits_vector_shape_and_enum_are_closed(self):
        for cls, changes in [('Sprite2D', {'frame': -1}), ('Sprite2D', {'frame': 65536}),
                             ('Sprite2D', {'frame': 1.5}), ('Camera3D', {'fov': 180}),
                             ('Node2D', {'position': [0, 10001]}), ('Node2D', {'position': [0, 1, 2]}),
                             ('Node2D', {'position': {'x': 0, 'y': 1}}),
                             ('CharacterBody2D', {'motion_mode': 2}), ('Control', {'mouse_filter': 'stop'})]:
            self.reject(self.request(payload=self.payload(cls, changes)), 'AUTHORING_PROPERTY_TYPE')
        for value in (float('nan'), float('inf'), -float('inf'), 2**1000):
            with self.assertRaises(ValidationError):
                self.request(payload=self.payload('Node2D', {'rotation': value}))

    def test_string_size_unicode_and_zero_byte(self):
        self.validate(self.request(payload=self.payload('Label', {'text': 'Đấu trường nguyên bản'})))
        for value in ('x' * 4097, 'bad\x00text'):
            self.reject(self.request(payload=self.payload('Label', {'text': value})), 'AUTHORING_PROPERTY_TYPE')
        with self.assertRaises(ValidationError):
            self.request(payload=self.payload('Label', {'text': '\ud800'}))

    def test_resources_resolve_only_trusted_manifest_ids_with_matching_base(self):
        for ref in ({'resource_id': 'missing'}, {'resource_id': 'shape3d'},
                    {'resource_id': '../texture'}, {'resource_id': 'texture2d', 'base': 'Texture2D'},
                    {'path': 'res://outside.tres'}, {'resource_id': []}, None):
            self.reject(self.request(payload=self.payload('Sprite2D', {'texture': ref})), 'AUTHORING_RESOURCE_REFERENCE')
        self.validate(self.request(payload=self.payload('Sprite2D', {'texture': {'resource_id': 'texture2d'}})))

    def test_no_hidden_profile_script_or_execution_flags(self):
        for field, value in [('profile', contract.PROFILE), ('script_enabled', True),
                             ('auth_evidence', {gate: 'PASS' for gate in contract.SCRIPT_GATES}), ('text', 'extends Node2D')]:
            payload = self.payload('Node2D', {})
            payload[field] = value
            self.reject(self.request(payload=payload), 'AUTHORING_INVALID_SHAPE')
        for changes in ({'script': 'res://script.gd'}, {'script': {'resource_id': 'texture2d'}}):
            self.reject(self.request(payload=self.payload('Node2D', changes)), 'AUTHORING_PROPERTY_REJECTED')
        self.reject(self.request('script_text.replace', target={'path': 'scripts/fixture_actor.gd'},
                                payload={'text': 'extends Node2D', 'profile': contract.PROFILE,
                                         'auth_evidence': {gate: 'PASS' for gate in contract.SCRIPT_GATES}}),
                    'AUTHORING_SCRIPT_PROFILE_DISABLED')

    def test_unsupported_mutations_and_fake_history_do_not_exist(self):
        for operation in ('scene.undo', 'scene.redo', 'scene.node.remove', 'node.create', 'resource.create', 'input.action.add'):
            self.reject(self.request(operation), 'AUTHORING_OPERATION_DISABLED')
        self.assertFalse(hasattr(contract, 'InMemoryAuthoringAdapter'))
        self.assertFalse(hasattr(contract, 'validate_readback'))

    def test_shared_request_payload_hash_and_digest_are_enforced(self):
        wire = self.request().as_dict()
        self.assertEqual(self.validate(wire).request_digest, self.request().digest)
        for field, value, code in [('digest', 'sha256:' + '0' * 64, 'DIGEST_MISMATCH'),
                                  ('payload_hash', 'sha256:' + '0' * 64, 'PAYLOAD_HASH_MISMATCH'),
                                  ('schema_version', 'other', 'UNSUPPORTED_SCHEMA')]:
            changed = copy.deepcopy(wire)
            changed[field] = value
            self.reject(changed, code)
        self.reject({**wire, 'class_name': 'Node2D'}, 'UNKNOWN_FIELD')
        self.reject({'command_id': 'cmd.flat', 'operation': 'node.create'})

    def test_all_authority_and_staleness_checks_fail_closed(self):
        cases = [({'project_id': 'project.other'}, 'AUTHORING_PROJECT_MISMATCH'),
                 ({'expected_revision': 'sha256:' + '3' * 64}, 'AUTHORING_STALE_REVISION'),
                 ({'lease_id': 'lease.other'}, 'AUTHORING_STALE_LEASE'),
                 ({'fencing_epoch': 8}, 'AUTHORING_STALE_LEASE'),
                 ({'deadline_ms': 1000}, 'AUTHORING_DEADLINE_EXPIRED'),
                 ({'deadline_ms': 31001}, 'AUTHORING_DEADLINE_EXPIRED')]
        for kwargs, code in cases:
            self.reject(self.request(**kwargs), code)
        for field, value, code in [('expected_generation', True, 'AUTHORING_STALE_GENERATION'),
                                  ('expected_generation', 2, 'AUTHORING_STALE_GENERATION'),
                                  ('expected_project_revision', 'sha256:' + '3' * 64, 'AUTHORING_STALE_PROJECT_REVISION')]:
            payload = self.payload('Node2D', {})
            payload[field] = value
            self.reject(self.request(payload=payload), code)
        self.reject(self.request(), 'AUTHORING_STOPPED', context=replace(self.context, stopped=True))
        self.reject(self.request(), 'AUTHORING_TRUSTED_CONTEXT_REQUIRED', context=replace(self.context, profile='hh-godot-declarative-1'))

    def test_payload_shape_target_and_stable_identity_reject(self):
        self.reject(self.request(target={'path': 'scenes/fixture.tscn'}), 'AUTHORING_INVALID_SHAPE')
        self.reject(self.request(target={'stable_id': 'missing'}), 'AUTHORING_STALE_STABLE_ID')
        for field, value, code in [('stable_id', 'actor', 'AUTHORING_DUPLICATE_STABLE_ID'),
                                  ('stable_id', '../child', 'AUTHORING_DUPLICATE_STABLE_ID'),
                                  ('name', 'aCtOr', 'AUTHORING_DUPLICATE_NAME')]:
            payload = self.payload('Node2D', {})
            payload[field] = value
            self.reject(self.request(payload=payload), code)
        self.reject(self.request('scene.node.update', payload={'changes': {}}), 'AUTHORING_EMPTY_UPDATE')
        self.reject(self.request('scene.node.update', payload={'changes': {}, 'node_type': 'Node2D'}), 'AUTHORING_INVALID_SHAPE')

    def test_context_hierarchy_resource_duplicates_and_caps(self):
        duplicate = self.context.nodes + (self.context.nodes[1],)
        self.reject(self.request(), 'AUTHORING_NODE_STATE', context=replace(self.context, nodes=duplicate))
        orphan = (self.context.nodes[0], contract.NodeState('orphan', 'missing', 'Node2D', 'Orphan'))
        self.reject(self.request(), 'AUTHORING_HIERARCHY', context=replace(self.context, nodes=orphan))
        cycle = (self.context.nodes[0], contract.NodeState('actor', 'actor', 'Node2D', 'Actor'))
        self.reject(self.request(), 'AUTHORING_HIERARCHY', context=replace(self.context, nodes=cycle))
        self.reject(self.request(), 'AUTHORING_RESOURCE_STATE', context=replace(self.context,
                    resources=self.context.resources + (self.context.resources[0],)))
        nodes = (self.context.nodes[0],) + tuple(contract.NodeState('n' + str(i), 'root', 'Node2D', 'N' + str(i)) for i in range(63))
        self.reject(self.request(), 'AUTHORING_NODE_LIMIT', context=replace(self.context, nodes=nodes))
        nodes = (self.context.nodes[0],) + tuple(contract.NodeState('n' + str(i), 'root' if i == 1 else 'n' + str(i - 1),
                                  'Node2D', 'N' + str(i)) for i in range(1, 16))
        self.reject(self.request(target={'stable_id': 'n15'}), 'AUTHORING_DEPTH_LIMIT', context=replace(self.context, nodes=nodes))

    def test_catalog_metadata_is_detached_and_never_enables_runtime(self):
        raw = self.catalog.as_dict()
        self.assertEqual(raw['required_script_gates'], list(contract.SCRIPT_GATES))
        self.assertFalse(raw['runtime_enabled'])
        self.assertFalse(raw['script_enabled'])
        self.assertEqual(raw['native_evidence'], 'UNVERIFIED')
        raw['classes'][0]['properties']['position']['minimum'] = 0
        self.assertEqual(self.catalog.classes['Node2D'].properties['position'].minimum, -10000)
        with self.assertRaises(TypeError):
            self.catalog.classes['Node2D'].properties['position'] = None
        result = self.validate()
        self.assertEqual(result.preview['catalog_digest'], self.catalog.digest)
        self.assertFalse(result.preview['changes_applied'])
        self.assertFalse(result.preview['runtime_authorized'])

    def mutated_catalog(self, mutate):
        document = json.loads(contract.SCHEMA_PATH.read_text(encoding='utf-8'))
        mutate(document['x-candidate'])
        with tempfile.TemporaryDirectory(prefix='hh-o2-catalog-') as directory:
            path = Path(directory) / 'catalog.json'
            path.write_text(json.dumps(document), encoding='utf-8')
            return contract.load_catalog(path)

    def test_catalog_rejects_unsafe_or_malformed_metadata(self):
        mutations = [lambda c: c.update(catalog_version=True), lambda c: c.update(catalog_version=2),
                     lambda c: c.update(script_enabled=True), lambda c: c.update(runtime_enabled=True),
                     lambda c: c.update(native_evidence='PASS'), lambda c: c.update(unexpected=True),
                     lambda c: c['classes'].append(c['classes'][0]),
                     lambda c: c['classes'][0].update(property_base='Missing'),
                     lambda c: c['classes'][0].update(property_base='Sprite2D'),
                     lambda c: c['classes'][0].update(instantiable='true'),
                     lambda c: c['classes'][0]['properties']['position'].update(type='callable'),
                     lambda c: c['classes'][0]['properties']['position'].update(writable='false'),
                     lambda c: c['classes'][0]['properties']['position'].update(minimum=20000),
                     lambda c: c['classes'][2]['properties']['texture'].update(resource_base='Script'),
                     lambda c: c['classes'][3]['properties']['animation'].update(values=[0]),
                     lambda c: c['classes'][5]['properties']['motion_mode'].update(values=[True]),
                     lambda c: c['classes'][-1].update(instantiable=True)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)), self.assertRaises(ValidationError):
                self.mutated_catalog(mutation)

    def test_read_only_descriptor_rejects_property_write(self):
        changed = self.mutated_catalog(lambda c: c['classes'][0]['properties']['position'].update(writable=False))
        self.reject(self.request(), 'AUTHORING_PROPERTY_READ_ONLY', catalog=changed)

    def test_duplicate_json_keys_are_rejected_by_shared_parser(self):
        text = contract.SCHEMA_PATH.read_text(encoding='utf-8')
        text = text.replace('"catalog_version": 1', '"catalog_version": 1, "catalog_version": 1')
        with tempfile.TemporaryDirectory(prefix='hh-o2-catalog-') as directory:
            path = Path(directory) / 'duplicate.json'
            path.write_text(text, encoding='utf-8')
            with self.assertRaises(ValidationError) as raised:
                contract.load_catalog(path)
        self.assertEqual(raised.exception.code, 'DUPLICATE_KEY')


if __name__ == '__main__':
    unittest.main()
