"""Closed replay contract tests; no engine or authority claims."""
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import contract as c
from studio.protocol.core import Discovery, Request, SCHEMA_VERSION, canonical_bytes


def binding():
    return {'run_id': 'run.replay', 'command_id': 'command.run', 'runtime_instance_id': 'runtime.play',
            'source_closure_sha256': '1' * 64, 'runtime_snapshot_sha256': '2' * 64,
            'trace_sha256': '3' * 64, 'glb_sha256': '4' * 64, 'generation': 1}


def payload(operation):
    if operation == 'play.inspect':
        return {'expected': {'runtime_instance_id': 'runtime.play', 'generation': 1,
            'source_closure_sha256': '1' * 64, 'runtime_snapshot_sha256': '2' * 64,
            'report_sha256': '5' * 64, 'pid': 101, 'process_start': 'windows:134341240513428496'},
            'properties': ['sim_tick', 'phase']}
    value = {'expected_generation': 1, 'expected_snapshot_sha256': '2' * 64,
             'expected_source_sha256': '1' * 64}
    value.update({'trace_sha256': '3' * 64} if operation == 'play.start' else {'label': 'menu'})
    return value


class ReplayContractTests(unittest.TestCase):
    def setUp(self):
        self.prepared = c.PreparedRuntime(binding(), ('menu', 'moved'))
        self.context = c.ReplayContext('project.replay', self.prepared, 'lease.one', 1,
            30_000, 1000, runtime_enabled=c.OPERATIONS)

    def body(self, operation='play.start', value=None, **changes):
        value = payload(operation) if value is None else value
        fields = dict(command_id='command.one', project_id='project.replay', operation=operation,
            lease_id='lease.one', fencing_epoch=1, expected_revision=self.prepared.revision,
            target={'stable_id': 'runtime.play'}, payload=value,
            payload_hash='sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest(), deadline_ms=10_000)
        fields.update(changes)
        return Request(**fields).as_dict()

    def rejects(self, body, code=None, context=None):
        with self.assertRaises(c.ReplayContractError) as caught:
            c.validate_request(body, context or self.context)
        if code:
            self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_each_fixed_operation_reuses_accepted_request_and_copies_inputs(self):
        for operation in sorted(c.OPERATIONS):
            body = self.body(operation)
            result = c.validate_request(body, self.context)
            self.assertIs(type(result), Request)
            self.assertEqual(result.operation, operation)
            self.assertEqual(c.validate_request(canonical_bytes(body), self.context), result)
            body['payload'].clear()
            self.assertTrue(result.payload)

    def test_catalog_is_versioned_defensive_and_advertises_no_backend_by_default(self):
        value = c.catalog()
        self.assertEqual(value['schema_id'], 'hh-studio.replay-catalog')
        self.assertEqual(value['schema_version'], '1.0.0')
        self.assertEqual(c.CATALOG_DIGEST, 'sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest())
        self.assertFalse(value['operations']['play.inspect']['live_supported'])
        self.assertFalse(value['persistent_ack_or_durability_claim'])
        self.assertEqual(set(value['control_routes']), {'/v1/stop', '/v1/lookup'})
        self.assertFalse(c.discovery('project.replay').capabilities)
        discovery = c.discovery('project.replay', runtime_enabled=c.OPERATIONS)
        self.assertEqual(Discovery.from_dict(discovery.as_dict()), discovery)
        self.assertEqual({x.operation for x in discovery.capabilities}, c.OPERATIONS)
        value['operations'].clear()
        self.assertEqual(set(c.catalog()['operations']), c.OPERATIONS)
        self.assertEqual(c.MAX_ARRAY_ITEMS, 256)
        self.assertEqual(c.MAX_OBJECT_MEMBERS, 256)
        self.assertEqual(c.MAX_WIRE_BYTES, 262144)
        self.assertEqual(c.MAX_RESULT_BYTES, 262144)

    def test_prepared_binding_and_labels_are_immutable_and_closed(self):
        value = binding()
        prepared = c.PreparedRuntime(value, ('menu',))
        value['generation'] = 9
        result = prepared.binding
        result['run_id'] = 'changed'
        self.assertEqual(prepared.binding, binding())
        self.assertEqual(prepared.binding_sha256, hashlib.sha256(canonical_bytes(binding())).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            prepared.capture_labels = ('changed',)
        for labels in (['menu'], ('menu', 'menu'), ('../menu',), ('con',), ('a_',), tuple('label' + str(i) for i in range(17))):
            with self.subTest(labels=labels), self.assertRaises(c.ReplayContractError):
                c.PreparedRuntime(binding(), labels)
        for altered in ({}, {**binding(), 'extra': 1}, {**binding(), 'generation': True},
                        {**binding(), 'run_id': '../bad'}, {**binding(), 'trace_sha256': 'A' * 64}):
            with self.assertRaises(c.ReplayContractError):
                c.PreparedRuntime(altered, ())

    def test_unknown_envelope_payload_and_nested_fields_fail_closed(self):
        self.rejects({**self.body(), 'argv': ['--script', 'evil']}, 'UNKNOWN_FIELD')
        for operation in c.OPERATIONS:
            for key in ('script', 'path', 'project', 'argv', 'command', 'inline_bytes'):
                altered = payload(operation)
                altered[key] = 'anything'
                self.rejects(self.body(operation, altered), 'REPLAY_INVALID_PAYLOAD')
        altered = payload('play.inspect')
        altered['expected']['unexpected'] = 'anything'
        self.rejects(self.body('play.inspect', altered), 'REPLAY_INVALID_PAYLOAD')

    def test_secret_fields_and_sensitive_looking_path_inputs_are_not_executable(self):
        for key in ('password', 'token', 'credentials', 'api_key'):
            body = self.body()
            body['payload'][key] = 'do-not-echo-sensitive'
            error = self.rejects(json.dumps(body).encode(), 'SECRET_FIELD_FORBIDDEN')
            self.assertNotIn('do-not-echo-sensitive', str(error))
        for target in ({'path': 'C:/private/file'}, {'stable_id': 'runtime.other'}, {'path': '../outside'}):
            self.rejects(self.body(target=target), 'REPLAY_TARGET_MISMATCH')
        for command_id in ('command/other', 'C:/file', 'a' * 65):
            self.rejects(self.body(command_id=command_id), 'REPLAY_INVALID_COMMAND_ID')

    def test_stale_generation_snapshot_source_and_trace_rejected(self):
        for operation in ('play.start', 'play.capture'):
            for field, value, code in (('expected_generation', 2, 'REPLAY_STALE_GENERATION'),
                ('expected_snapshot_sha256', '8' * 64, 'REPLAY_STALE_SNAPSHOT'),
                ('expected_source_sha256', '8' * 64, 'REPLAY_STALE_SOURCE')):
                altered = payload(operation)
                altered[field] = value
                self.rejects(self.body(operation, altered), code)
        altered = payload('play.start')
        altered['trace_sha256'] = '8' * 64
        self.rejects(self.body(value=altered), 'REPLAY_STALE_TRACE')
        self.rejects(self.body(expected_revision='sha256:' + '8' * 64), 'REPLAY_STALE_REVISION')
        altered['expected_generation'] = True
        self.rejects(self.body(value=altered), 'REPLAY_INVALID_INTEGER')

    def test_capture_resolves_declared_label_only_and_never_a_path(self):
        for label in ('new_label', '../menu.png', 'out/menu.png', 'menu.png', 'MENU', 1, None):
            altered = payload('play.capture')
            altered['label'] = label
            self.rejects(self.body('play.capture', altered), 'REPLAY_UNDECLARED_CAPTURE')

    def test_exact_project_lease_fence_revision_and_deadline_are_required(self):
        for changes, code in (({'project_id': 'project.other'}, 'PROJECT_MISMATCH'),
            ({'lease_id': 'lease.other'}, 'REPLAY_STALE_LEASE'),
            ({'fencing_epoch': 2}, 'REPLAY_STALE_LEASE'),
            ({'deadline_ms': 21_001}, 'REPLAY_DEADLINE_OUT_OF_RANGE'),
            ({'deadline_ms': 1000}, 'DEADLINE_OUT_OF_RANGE')):
            self.rejects(self.body(**changes), code)
        self.rejects(self.body(), 'REPLAY_DEADLINE_OUT_OF_RANGE', replace(self.context, lease_expires_ms=5000))
        self.rejects(self.body(), 'REPLAY_STOPPED', replace(self.context, stopped=True))
        self.rejects(self.body(), 'REPLAY_INVALID_FENCE', replace(self.context, fencing_epoch=0))

    def test_unsupported_operations_and_disabled_capabilities_cannot_be_inferred(self):
        self.rejects(self.body(), 'UNSUPPORTED_OPERATION', replace(self.context, runtime_enabled=frozenset()))
        for operation in ('control.stop', 'control.lookup', 'fixture.set', 'play.live', 'open_lane'):
            self.rejects(self.body(operation=operation, value={}),
                         'UNSUPPORTED_OPEN_LANE' if operation == 'open_lane' else 'UNSUPPORTED_OPERATION')

    def test_inspect_expected_provenance_and_types_are_closed(self):
        for field, value, code in (
            ('runtime_instance_id', 'runtime.other', 'REPLAY_STALE_RUNTIME'),
            ('generation', 2, 'REPLAY_STALE_GENERATION'),
            ('source_closure_sha256', '8' * 64, 'REPLAY_STALE_SOURCE'),
            ('runtime_snapshot_sha256', '8' * 64, 'REPLAY_STALE_SNAPSHOT'),
            ('report_sha256', 'SHA256:bad', 'REPLAY_INVALID_HASH'),
            ('pid', True, 'REPLAY_INVALID_PID'), ('pid', 4294967296, 'REPLAY_INVALID_PID'),
            ('process_start', '134341240513428496', 'REPLAY_INVALID_PROCESS_START'),
            ('process_start', 'windows:18446744073709551616', 'REPLAY_INVALID_PROCESS_START')):
            altered = payload('play.inspect')
            altered['expected'][field] = value
            self.rejects(self.body('play.inspect', altered), code)

    def test_inspect_property_filter_page_and_tick_bounds_are_strict(self):
        for changes, code in (({'properties': []}, 'REPLAY_PROPERTY_LIMIT'),
            ({'properties': ['sim_tick'] * 12}, 'REPLAY_PROPERTY_LIMIT'),
            ({'properties': ['phase', 'phase']}, 'REPLAY_UNSUPPORTED_PROPERTY'),
            ({'properties': ['get_script']}, 'REPLAY_UNSUPPORTED_PROPERTY'),
            ({'phase': 'anything'}, 'REPLAY_INVALID_PHASE'), ({'phase': []}, 'REPLAY_INVALID_PHASE'),
            ({'page_size': 9}, 'REPLAY_PAGE_LIMIT'), ({'page_size': True}, 'REPLAY_PAGE_LIMIT'),
            ({'tick_min': -1}, 'REPLAY_TICK_RANGE'), ({'tick_max': 600}, 'REPLAY_TICK_RANGE'),
            ({'tick_min': 10, 'tick_max': 9}, 'REPLAY_TICK_RANGE')):
            altered = {**payload('play.inspect'), **changes}
            self.rejects(self.body('play.inspect', altered), code)
        good = {**payload('play.inspect'), 'properties': list(c.INSPECT_PROPERTIES),
                'phase': None, 'page_size': 8, 'tick_min': 0, 'tick_max': 599}
        c.validate_request(self.body('play.inspect', good), self.context)

    def test_cursor_syntax_is_bounded_but_authentication_belongs_to_inspector(self):
        for cursor in ('../cursor', 'Bearer ' + 'a' * 43, 'a.' + 'A' * 64, 'a' * 1984 + '.' + 'f' * 64, 0):
            altered = {**payload('play.inspect'), 'cursor': cursor}
            self.rejects(self.body('play.inspect', altered), 'REPLAY_INVALID_CURSOR')
        for cursor in (None, 'e30.' + 'f' * 64):
            c.validate_request(self.body('play.inspect', {**payload('play.inspect'), 'cursor': cursor}), self.context)

    def test_shared_wire_and_array_limits_remain_unchanged(self):
        raw = canonical_bytes(self.body())
        c.validate_request(raw + b' ' * (c.MAX_WIRE_BYTES - len(raw)), self.context)
        self.rejects(raw + b' ' * (c.MAX_WIRE_BYTES - len(raw) + 1), 'ENVELOPE_TOO_LARGE')
        body = self.body()
        body['payload']['huge'] = [0] * 257
        self.rejects(json.dumps(body).encode(), 'ARRAY_ITEM_LIMIT')
        body = self.body()
        body['payload'].update(a='x' * 9000, b='x' * 9000)
        body['payload_hash'] = 'sha256:' + hashlib.sha256(canonical_bytes(body['payload'])).hexdigest()
        body.pop('digest')
        self.rejects(body, 'REPLAY_PAYLOAD_LIMIT')

    def test_duplicate_members_schema_hash_and_digest_are_rejected(self):
        raw = canonical_bytes(self.body())
        self.rejects(raw.replace(b'"expected_generation":1', b'"expected_generation":1,"expected_generation":1'),
                     'DUPLICATE_KEY')
        self.rejects({**self.body(), 'schema_version': 'other'}, 'UNSUPPORTED_SCHEMA')
        self.rejects({**self.body(), 'payload_hash': 'sha256:' + '0' * 64}, 'PAYLOAD_HASH_MISMATCH')
        self.rejects({**self.body(), 'digest': 'sha256:' + '0' * 64}, 'DIGEST_MISMATCH')

    def test_artifacts_are_bounded_hash_references_with_no_inline_or_path_field(self):
        for kind in ('observation', 'capture', 'perf', 'process_metrics', 'trace'):
            result = c.artifact_reference(kind=kind, sha256='a' * 64, size_bytes=128)
            self.assertEqual(set(result), {'kind', 'sha256', 'size_bytes'})
        for fields in ({'kind': 'script'}, {'sha256': 'sha256:' + 'a' * 64}, {'size_bytes': True},
                       {'size_bytes': 0}, {'size_bytes': 1024 * 1024 + 1}):
            with self.assertRaises(c.ReplayContractError):
                c.artifact_reference(**({'kind': 'capture', 'sha256': 'a' * 64, 'size_bytes': 128} | fields))


if __name__ == '__main__':
    unittest.main()
