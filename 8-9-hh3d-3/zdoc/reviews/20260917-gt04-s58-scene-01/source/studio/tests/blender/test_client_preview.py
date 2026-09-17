"""Pure exact preview/diff models; no bpy, native owner, storage or authority."""
import copy
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender import client_preview as m
from studio.host.blender import client_write_catalog as catalog
from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

SOURCE = 'sha256:' + 'a'*64
GENERATION = 'b'*32
CONTEXT = {'mode': 'OBJECT', 'active_id': None, 'selected_ids': []}
PRIVATE_ID = 'client-' + 'c'*40


def box(key='box'):
    return {'object_id': key, 'name': 'GT04_'+key, 'mesh_name': 'GT04_mesh_'+key,
        'location': [0.0, 0.0, 0.0], 'rotation': [0.0, 0.0, 0.0], 'scale': [1.0, 1.0, 1.0],
        'vertices': [[-0.5, -1.0, -1.5], [0.5, -1.0, -1.5], [0.5, 1.0, -1.5], [-0.5, 1.0, -1.5],
                     [-0.5, -1.0, 1.5], [0.5, -1.0, 1.5], [0.5, 1.0, 1.5], [-0.5, 1.0, 1.5]],
        'faces': [list(face) for face in m.queue.base.FACES]}


def material(key='copper'):
    return {'material_id': key, 'name': 'HH_Material_'+key, 'base_color': [0.6, 0.25, 0.1, 1.0],
        'metallic': 0.8, 'roughness': 0.3, 'double_sided': True, 'alpha_mode': 'OPAQUE'}


def observed(rows=(), *, context=None, revision=None):
    snapshot = {'schema': 'HH-BLENDER-FIXTURE-SCENE-1', 'objects': copy.deepcopy(list(rows)),
                'units': {'system': 'METRIC', 'scale_length': 1.0}}
    return {'snapshot': snapshot, 'revision': revision or m.queue.c.digest(snapshot),
            'context': copy.deepcopy(context or CONTEXT), 'public_ack': False, 'undo_supported': True}


def request(before, operation='mesh.create_box', arguments=None, **changes):
    defaults = {
        'mesh.create_box': {'object_id': 'new_box', 'size': [1, 2, 3]},
        'object.transform.set': {'object_id': 'box', 'location': [1, 2, 3],
                                 'rotation': [0.1, 0.2, 0.3], 'scale': [1, 2, 1]},
        'material.set_principled': {'object_id': 'box', 'material_id': 'copper',
                                    'base_color': [0.6, 0.25, 0.1], 'metallic': 0.8, 'roughness': 0.3},
    }
    payload = {'expected_context': copy.deepcopy(before['context']),
               'arguments': copy.deepcopy(defaults.get(operation, {}) if arguments is None else arguments)}
    fields = {'command_id': 'Client:Preview/Create', 'project_id': 'blender.test', 'operation': operation,
        'lease_id': 'write.registered', 'fencing_epoch': 1, 'expected_revision': before['revision'],
        'target': {'stable_id': catalog.TARGET}, 'payload': payload, 'deadline_ms': 1_900_000_000_000}
    fields.update(changes); fields['payload_hash'] = m._sha(fields['payload'])
    return Request(**fields)


def native_command(value):
    return {'schema': m.queue.SCHEMA, 'command_id': PRIVATE_ID, 'operation': value.operation,
        'expected_revision': value.expected_revision, 'expected_context': copy.deepcopy(value.payload['expected_context']),
        'payload': copy.deepcopy(value.payload['arguments'])}


def response(command, before, target=None):
    return {'schema': m.PREVIEW_SCHEMA, 'command_id': command['command_id'],
        'command_digest': m.queue.c.digest(command), 'operation': command['operation'], 'before': copy.deepcopy(before),
        'requested_changes': copy.deepcopy(command['payload']), 'history_target': copy.deepcopy(target),
        'affected_files': [], 'undo_policy': m.UNDO_POLICY, 'value_policy': m.VALUE_POLICY,
        'no_effect': True, 'apply_id_reserved': False, 'public_ack': False, 'scene_state_durable': False}


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.before = observed()
        self.request = request(self.before)
        self.command = native_command(self.request)
        self.response = response(self.command, self.before)

    def normalize(self, value=None, command=None, result=None, **changes):
        options = dict(source_sha256=SOURCE, generation=GENERATION); options.update(changes)
        return m.normalize_preview(value or self.request, command or self.command,
                                   result or self.response, **options)

    def test_advisory_binds_exact_request_source_generation_without_authority_or_future_revision(self):
        value = self.normalize()
        self.assertEqual(value['schema'], 'HH-BLENDER-CLIENT-PREVIEW-1')
        self.assertEqual(value['command_id'], self.request.command_id)
        self.assertEqual(value['request_digest'], self.request.digest)
        self.assertEqual(value['request_sha256'], m._sha(self.request.as_dict()))
        self.assertEqual(value['native_command_digest'], m.queue.c.digest(self.command))
        self.assertEqual(value['source_sha256'], SOURCE); self.assertEqual(value['generation'], GENERATION)
        self.assertEqual(value['affected_files'], []); self.assertEqual(value['undo_policy'], m.UNDO_POLICY)
        self.assertTrue(value['no_effect']); self.assertFalse(value['apply_id_reserved'])
        self.assertFalse(value['authority_granted']); self.assertFalse(value['public_ack'])
        self.assertFalse(value['scene_state_durable']); self.assertNotIn('after_revision', value)
        self.assertNotIn('after', value['requested_diff'])
        self.assertEqual(value['requested_diff'], {'kind': 'create-box', 'object_id': 'new_box',
            'before': None, 'requested': {'size': [1, 2, 3]}})

    def test_native_float_revision_remains_opaque_after_received_jcs_normalization(self):
        native_revision = self.before['revision']
        self.response = parse_json(canonical_bytes(self.response))
        self.assertNotEqual(native_revision, m.queue.c.digest(self.response['before']['snapshot']))
        value = self.normalize()
        self.assertEqual(value['before']['revision'], native_revision)
        self.assertEqual(value['comparison_domain'], m.DIFF_DOMAIN)
        self.assertEqual(value['before_hash'], m._sha({'snapshot': value['before']['snapshot'],
                                                    'context': value['before']['context']}))

    def test_native_id_digest_operation_and_schema_false_binding_is_rejected(self):
        for field, replacement in (('command_id', 'other-private-command'), ('command_digest', 'sha256:'+'0'*64),
                                   ('operation', 'history.undo'), ('schema', 'other')):
            changed = copy.deepcopy(self.response); changed[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValidationError, 'NATIVE_BINDING'):
                self.normalize(result=changed)

    def test_no_effect_and_policy_claims_are_exact_not_truthy(self):
        for field, replacement in (('no_effect', 1), ('apply_id_reserved', True), ('public_ack', True),
                                   ('scene_state_durable', True), ('affected_files', ['artist.blend']),
                                   ('undo_policy', 'unconditional-undo'), ('value_policy', 'exact-predicted-floats')):
            changed = copy.deepcopy(self.response); changed[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValidationError, 'NO_EFFECT_REQUIRED'):
                self.normalize(result=changed)

    def test_extra_or_missing_preview_fields_are_rejected(self):
        for changed in (dict(self.response, future_revision='sha256:'+'0'*64),
                        {key: value for key, value in self.response.items() if key != 'no_effect'}):
            with self.assertRaisesRegex(ValidationError, 'SHAPE'):
                self.normalize(result=changed)

    def test_before_revision_or_context_cannot_substitute_another_observation(self):
        changed = copy.deepcopy(self.response); changed['before']['revision'] = 'sha256:'+'0'*64
        with self.assertRaisesRegex(ValidationError, 'BEFORE_BINDING'): self.normalize(result=changed)
        old = observed([box()]); value = request(old); command = native_command(value); changed = response(command, old)
        changed['before']['context'] = {'mode': 'OBJECT', 'active_id': 'box', 'selected_ids': ['box']}
        with self.assertRaisesRegex(ValidationError, 'BEFORE_BINDING'):
            self.normalize(value, command, changed)

    def test_private_translation_must_match_common_payload_revision_context_and_operation(self):
        for change in ({'payload': {'object_id': 'other', 'size': [1, 2, 3]}},
                       {'expected_revision': 'sha256:'+'0'*64},
                       {'expected_context': {'mode': 'OBJECT', 'active_id': 'box', 'selected_ids': ['box']}},
                       {'operation': 'history.undo', 'payload': {}}):
            altered = dict(self.command, **change)
            with self.subTest(change=change), self.assertRaisesRegex(ValidationError, 'REQUEST_BINDING'):
                self.normalize(command=altered, result=response(altered, self.before))

    def test_echoed_requested_changes_cannot_hide_changed_request(self):
        changed = copy.deepcopy(self.response); changed['requested_changes']['size'] = [3, 2, 1]
        with self.assertRaisesRegex(ValidationError, 'REQUEST_BINDING'): self.normalize(result=changed)

    def test_native_validator_rejects_out_of_range_parameters_and_common_target(self):
        value = request(self.before, arguments={'object_id': 'new_box', 'size': [1, 2, 0]})
        with self.assertRaisesRegex(ValidationError, 'INVALID_PAYLOAD'):
            self.normalize(value, native_command(value), response(native_command(value), self.before))
        with self.assertRaisesRegex(ValidationError, 'TARGET_MISMATCH'):
            self.normalize(request(self.before, target={'stable_id': 'foreign-scene'}))

    def test_invalid_owner_binding_and_unsupported_operation_are_rejected(self):
        for options in ({'source_sha256': 'a'*64}, {'generation': 'foreign'}, {'generation': True}):
            with self.subTest(options=options), self.assertRaisesRegex(ValidationError, 'OWNER_BINDING'):
                self.normalize(**options)
        for operation in ('scene.save', 'checkpoint.save', 'export.publish'):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValidationError, 'PREVIEW_OPERATION'):
                self.normalize(request(self.before, operation))

    def test_result_is_detached_from_native_and_request_mutations(self):
        value = self.normalize(); wire = canonical_bytes(value)
        self.response['before']['snapshot']['units']['scale_length'] = 12
        self.command['payload']['size'][0] = 9
        self.request.payload['arguments']['size'][0] = 8
        self.assertEqual(canonical_bytes(value), wire)

    def test_create_existing_object_or_full_scene_cannot_be_previewed_as_valid(self):
        for before in (observed([box('new_box')]), observed([box('b%02d'%i) for i in range(m.MAX_OBJECTS)])):
            value = request(before); command = native_command(value)
            with self.assertRaisesRegex(ValidationError, 'CREATE_PRECONDITION'):
                self.normalize(value, command, response(command, before))

    def test_transform_diff_shows_requested_values_not_fabricated_native_rounding(self):
        before = observed([box()])
        arguments = {'object_id': 'box', 'location': [1.234567891, 2, 3],
                     'rotation': [0.1, 0.2, 0.3], 'scale': [1, 2, 1]}
        value = request(before, 'object.transform.set', arguments); command = native_command(value)
        result = self.normalize(value, command, response(command, before))
        diff = result['requested_diff']
        self.assertEqual(diff['before']['location'], [0, 0, 0])
        self.assertEqual(diff['requested']['location'][0], arguments['location'][0])
        self.assertNotEqual(diff['requested']['location'][0], m.queue.base.materials.rounded(arguments['location'][0]))
        self.assertEqual(result['value_policy'], m.VALUE_POLICY); self.assertNotIn('after', diff)

    def test_material_preview_preserves_current_material_and_exact_requested_parameters(self):
        row = box(); row['material'] = material(); before = observed([row])
        value = request(before, 'material.set_principled'); command = native_command(value)
        result = self.normalize(value, command, response(command, before))
        self.assertEqual(result['requested_diff']['before'], parse_json(canonical_bytes(row['material'])))
        self.assertEqual(result['requested_diff']['requested']['base_color'], value.payload['arguments']['base_color'])
        self.assertEqual(len(result['requested_diff']['requested']['base_color']), 3)

    def test_missing_target_and_conflicting_material_are_rejected(self):
        value = request(self.before, 'object.transform.set'); command = native_command(value)
        with self.assertRaisesRegex(ValidationError, 'OBJECT_MISSING'):
            self.normalize(value, command, response(command, self.before))
        row = box(); row['material'] = material('other'); before = observed([row])
        value = request(before, 'material.set_principled'); command = native_command(value)
        with self.assertRaisesRegex(ValidationError, 'MATERIAL_PRECONDITION'):
            self.normalize(value, command, response(command, before))

    def test_history_target_is_known_observation_not_future_native_revision(self):
        before = observed([box()]); target = observed()
        for operation in ('history.undo', 'history.redo'):
            value = request(before, operation); command = native_command(value)
            result = self.normalize(value, command, response(command, before, target))
            self.assertEqual(result['history_target'], parse_json(canonical_bytes(target)))
            self.assertEqual(result['history_target_diff']['objects']['removed'][0]['object_id'], 'box')
            self.assertEqual(result['requested_diff']['direction'], operation.split('.')[1])
            self.assertNotIn('after_revision', result); self.assertFalse(result['apply_id_reserved'])

    def test_only_history_operations_may_supply_history_target(self):
        with self.assertRaisesRegex(ValidationError, 'HISTORY_TARGET'):
            self.normalize(result=dict(self.response, history_target=self.before))
        value = request(self.before, 'history.undo'); command = native_command(value)
        with self.assertRaisesRegex(ValidationError, 'HISTORY_TARGET'):
            self.normalize(value, command, response(command, self.before))

    def test_history_result_over_cap_fails_instead_of_truncating_rows(self):
        rows = [box('b%02d'%i) for i in range(m.MAX_OBJECTS)]
        for row in rows:
            row['name'] = 'n'*128; row['mesh_name'] = 'm'*128
        before = observed(rows); target = copy.deepcopy(before)
        for row in target['snapshot']['objects']:
            row['location'] = [1, 2, 3]
        target['revision'] = 'sha256:'+'d'*64
        value = request(before, 'history.undo'); command = native_command(value)
        native = response(command, before, target)
        self.assertLess(len(canonical_bytes(before)), m.MAX_OBSERVATION_BYTES)
        self.assertLess(len(canonical_bytes(native)), m.MAX_PREVIEW_BYTES)
        with self.assertRaisesRegex(ValidationError, 'RESULT_LIMIT'):
            self.normalize(value, command, native)


class ActualDiffTests(unittest.TestCase):
    def diff(self, before, after, operation='object.transform.set'):
        return m.actual_diff(before, after, operation=operation)

    def test_unchanged_jcs_state_has_no_diff_despite_different_opaque_native_revision(self):
        before = observed([box()]); after = parse_json(canonical_bytes(before)); after['revision'] = 'sha256:'+'e'*64
        diff = self.diff(before, after)
        self.assertFalse(diff['changed']); self.assertEqual(diff['before_hash'], diff['after_hash'])
        self.assertEqual(diff['native_revisions'], {'before': before['revision'], 'after': after['revision']})
        self.assertEqual(diff['comparison_domain'], 'received-jcs-snapshot-context-v1'); self.assertEqual(diff['epsilon'], 0)
        self.assertEqual(diff['objects'], {'added': [], 'removed': [], 'changed': []})

    def test_added_removed_and_changed_rows_are_complete_and_sorted(self):
        before = observed([box('a'), box('b')]); after = observed([box('b'), box('c'), box('d')])
        after['snapshot']['objects'][0]['location'][0] = 1.5
        diff = self.diff(before, after, 'history.undo')
        self.assertEqual([row['object_id'] for row in diff['objects']['added']], ['c', 'd'])
        self.assertEqual(diff['objects']['removed'], parse_json(canonical_bytes([box('a')])))
        changed, = diff['objects']['changed']
        self.assertEqual(changed['object_id'], 'b'); self.assertEqual(changed['changed_fields'], ['location'])
        self.assertEqual(changed['before'], parse_json(canonical_bytes(box('b'))))
        self.assertEqual(changed['after'], parse_json(canonical_bytes(after['snapshot']['objects'][0])))
        self.assertTrue(diff['changed']); self.assertEqual(diff['affected_files'], [])

    def test_material_add_update_remove_keep_exact_before_and_after(self):
        blank = observed([box()]); with_material = copy.deepcopy(blank)
        with_material['snapshot']['objects'][0]['material'] = material()
        updated = copy.deepcopy(with_material); updated['snapshot']['objects'][0]['material']['roughness'] = 0.75
        for before, after in ((blank, with_material), (with_material, updated), (updated, blank)):
            diff = self.diff(before, after, 'material.set_principled'); changed, = diff['objects']['changed']
            self.assertEqual(changed['changed_fields'], ['material'])
            self.assertEqual(changed['before'], parse_json(canonical_bytes(before['snapshot']['objects'][0])))
            self.assertEqual(changed['after'], parse_json(canonical_bytes(after['snapshot']['objects'][0])))

    def test_geometry_names_transforms_context_and_units_are_not_silently_omitted(self):
        before = observed([box()]); after = copy.deepcopy(before); row = after['snapshot']['objects'][0]
        row['name'] = 'Renamed'; row['mesh_name'] = 'ChangedMesh'; row['vertices'][0][0] = -0.75
        row['faces'][0] = list(reversed(row['faces'][0]))
        row['rotation'][1] = .125; row['scale'][2] = 2
        after['context'] = {'mode': 'EDIT_MESH', 'active_id': 'box', 'selected_ids': ['box']}
        after['snapshot']['units'] = {'system': 'IMPERIAL', 'scale_length': .01}
        diff = self.diff(before, after, 'history.redo')
        self.assertEqual(diff['objects']['changed'][0]['changed_fields'], ['faces', 'mesh_name', 'name', 'rotation', 'scale', 'vertices'])
        self.assertEqual(diff['context'], {'before': before['context'], 'after': after['context']})
        self.assertEqual(diff['units']['after'], after['snapshot']['units'])

    def test_duplicate_or_unsorted_object_ids_and_object_cap_are_rejected(self):
        for rows, code in (([box(), box()], 'OBJECT_IDS'), ([box('z'), box('a')], 'OBJECT_IDS'),
                           ([box('b%02d'%i) for i in range(m.MAX_OBJECTS+1)], 'OBJECT_LIMIT')):
            with self.subTest(code=code), self.assertRaisesRegex(ValidationError, code):
                self.diff(observed(), observed(rows))

    def test_duplicate_material_and_context_identifiers_are_rejected(self):
        a, b = box('a'), box('b'); a['material'] = material(); b['material'] = material()
        with self.assertRaisesRegex(ValidationError, 'MATERIAL_IDS'): m.observation(observed([a, b]))
        for context in ({'mode': 'OBJECT', 'active_id': 'box', 'selected_ids': ['box', 'box']},
                        {'mode': 'OBJECT', 'active_id': 'missing', 'selected_ids': []},
                        {'mode': 'EDIT_MESH', 'active_id': 'box', 'selected_ids': []}):
            with self.subTest(context=context), self.assertRaisesRegex(ValidationError, 'CONTEXT'):
                m.observation(observed([box()], context=context))

    def test_unexpected_observation_object_material_and_units_shapes_are_rejected(self):
        cases = []
        value = observed([box()]); value['snapshot']['objects'][0]['unreported'] = True; cases.append(value)
        value = observed([box()]); value['snapshot']['units']['extra'] = True; cases.append(value)
        value = observed([box()]); value['snapshot']['objects'][0]['material'] = dict(material(), texture='external.png'); cases.append(value)
        value = observed([box()]); del value['snapshot']['objects'][0]['vertices']; cases.append(value)
        for value in cases:
            with self.assertRaises(ValidationError): self.diff(observed(), value)

    def test_nonfinite_boolean_numbers_float_face_indices_and_python_containers_are_rejected(self):
        for mutate in (lambda row: row['location'].__setitem__(0, float('nan')),
                       lambda row: row['location'].__setitem__(0, True),
                       lambda row: row['faces'][0].__setitem__(0, 0.0),
                       lambda row: row.update(location=(0, 0, 0)),
                       lambda row: row['vertices'].append([0, 0, 0])):
            row = box(); mutate(row)
            with self.assertRaises(ValidationError):
                self.diff(observed(), observed([row], revision='sha256:'+'f'*64))

    def test_overlong_names_and_observation_bytes_fail_without_truncation(self):
        row = box(); row['name'] = 'n'*(m.MAX_NAME_BYTES+1)
        with self.assertRaisesRegex(ValidationError, 'NAME_LIMIT'): m.observation(observed([row]))
        rows = [box('b%02d'%i) for i in range(m.MAX_OBJECTS)]
        for row in rows:
            row['name'] = 'n'*m.MAX_NAME_BYTES; row['mesh_name'] = 'm'*m.MAX_NAME_BYTES
            row['vertices'] = [[123456.123456789, 123456.123456789, 123456.123456789] for _ in range(8)]
        with self.assertRaisesRegex(ValidationError, 'OBSERVATION_LIMIT'): m.observation(observed(rows))

    def test_output_is_detached_and_unsupported_diff_operation_is_rejected(self):
        before = observed(); after = observed([box()]); diff = self.diff(before, after, 'mesh.create_box')
        wire = canonical_bytes(diff); after['snapshot']['objects'][0]['name'] = 'changed afterward'
        self.assertEqual(canonical_bytes(diff), wire)
        for operation in ('scene.save', 'scene.inspect', {}):
            with self.assertRaisesRegex(ValidationError, 'PREVIEW_OPERATION'): self.diff(before, after, operation)


if __name__ == '__main__':
    unittest.main()
