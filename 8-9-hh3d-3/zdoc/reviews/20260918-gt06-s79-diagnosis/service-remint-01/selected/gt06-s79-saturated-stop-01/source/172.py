"""Synthetic captured-stage tampering tests; no engine or .local fixture needed."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.pipeline.verify_run import (
    RunRejected, _Verifier, VALIDATION, DEPENDENCY_FILES, CONSUMER, AUTHORED, canonical, sha, strict, verify_chain,
)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else canonical(value) + b'\n'
    path.write_bytes(raw)
    return raw


def captured(root, files, argv, cwd, stdout=b'', binary='a'*64):
    """Independent test capture: an owned child, wrapper and natural Job exit."""
    put(root/'stdout.txt', stdout); put(root/'stderr.txt', b'')
    put(root/'process-start.json', {'pid': 7123})
    put(root/'process-exit.json', {'pid': 7123, 'exit_code': 0})
    report = {'completed': True, 'natural_tree_exit': True, 'active_before_cleanup': 0,
        'actual_process_exit': {'pid': 7123, 'exit_code': 0}, 'wrapper_exit_code': 0,
        'job': {'configured': True, 'assigned': True, 'closed': True, 'handle_retained': False,
            'tainted': False, 'zero_observed': True, 'active_count': 0, 'create_uncertain': False,
            'close_uncertain': False, 'failed_operations': []},
        'elapsed_seconds': 1.5, 'final_workspace_bytes': 10000,
        'limits': {'effective_wall_seconds': 20, 'wall_seconds': 20, 'job_memory_bytes': 2147483648,
            'job_user_time_100ns': 150000000, 'active_process_limit': 4,
            'each_log_capture_bytes': 262144, 'workspace_bytes_limit': 33554432},
        'artifacts': {name: sha((root/name).read_bytes()) for name in
            ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json')}}
    put(root/'invocation.json', {'argv': argv, 'cwd': str(cwd), 'binary_sha256': binary,
        'source_files': files, 'formal_acceptance': False})
    return sha(put(root/'capture.json', report))


class EvidenceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.studio = Path(self.temp.name)
        self.root = self.studio/'.local/reviews/gt05-validation-test'
        self.prefix = self.root.relative_to(self.studio).as_posix() + '/'

    def verify(self):
        return _Verifier(self.studio, True).validation('gt05-validation-test', self.producer)

    def make_validation(self):
        glb = b'captured synthetic payload; decoder is tested separately'
        p = {'profile_id': 'gt05-original-fixture-v1', 'license': 'original-fixture',
            'variant': 'baseline', 'pins': {}, 'catalog': {}, 'observed': {'images': {}},
            'artifacts': {'fixture.glb': {'sha256': sha(glb), 'bytes': len(glb)}}}
        producer_raw = canonical(p) + b'\n'
        self.producer = {'id': 'gt05-producer-test', 'report': p, 'raw': producer_raw,
                         'payloads': {'fixture.glb': glb}}
        semantic_raw = canonical({'nodes': [{'name': 'synthetic_mesh'}]}) + b'\n'
        preflight = {'artifact_sha256': sha(glb), 'artifact_bytes': len(glb), 'images': [],
            'semantic_sha256': sha(canonical(strict(semantic_raw))),
            'semantic_hash_domain': 'decoded-core-indexed-v1/json-sort-compact'}
        preflight_raw = canonical(preflight) + b'\n'
        for name in VALIDATION | {'pipeline/validate_glb.cjs', 'pipeline/admission_worker.py'}:
            put(self.studio/name, b'# fixed synthetic source\n')
        lock = {'name': 'gltf-validator', 'version': '2.0.0-dev.3.10',
            'files': {name: sha(name.encode()) for name in DEPENDENCY_FILES}}
        lock_raw = put(self.studio/'pipeline/dependencies/gltf-validator.lock.json', lock)
        put(self.studio/'pipeline/dependencies/node.lock.json', {'binary_sha256': 'a'*64})
        put(self.root/'gltf-validator.lock.json', lock_raw)
        for name in DEPENDENCY_FILES:
            put(self.root/'dependency'/name, name.encode())
        for name, raw in [('fixture.glb', glb), ('producer-report.json', producer_raw),
            ('preflight.json', preflight_raw), ('semantic.json', semantic_raw),
            ('admission/fixture.glb', glb), ('admission/preflight.json', preflight_raw),
            ('admission/semantic.json', semantic_raw)]:
            put(self.root/name, raw)
        put(self.root/'admission/expected.json', {'artifact_sha256': sha(glb)})
        put(self.root/'admission.json', {'schema': 'HH-GT05-VALIDATOR-INPUT-1', 'artifact_sha256': sha(glb)})
        names = set(VALIDATION) | {'pipeline/validate_glb.cjs', 'pipeline/dependencies/node.lock.json',
            'pipeline/dependencies/gltf-validator.lock.json'} | {self.prefix + name for name in
            ('fixture.glb', 'admission.json', 'gltf-validator.lock.json')} | {
            self.prefix + 'dependency/' + name for name in DEPENDENCY_FILES}
        self.files = {name: sha((self.studio/name).read_bytes()) for name in names}
        self.freeze(self.files, 'source-files.json', 'source')
        admission_names = set(VALIDATION) | {'pipeline/admission_worker.py',
            self.prefix + 'admission/expected.json', self.prefix + 'admission/fixture.glb'}
        self.admission_files = {name: sha((self.studio/name).read_bytes()) for name in admission_names}
        self.freeze(self.admission_files, 'admission-source-files.json', 'admission-source')
        validator = {'schema': 'HH-GT05-KHRONOS-1', 'artifact_sha256': sha(glb),
            'validator_version': lock['version'], 'dependency_lock_sha256': sha(lock_raw),
            'external_resource_requested': False, 'result': {'validatorVersion': lock['version'],
                'issues': {'numErrors': 0, 'numWarnings': 0, 'truncated': False, 'messages': []}}}
        validator_raw = put(self.root/'validator.json', validator)
        host_hash = captured(self.root/'host', self.files,
            ['node.exe', '--max-old-space-size=256', str(self.studio/'pipeline/validate_glb.cjs'), str(self.root)],
            self.root, b'GT05_KHRONOS_COMPLETE ' + canonical({'artifact_sha256': sha(glb),
                'report_sha256': sha(validator_raw)}) + b'\n')
        outputs = {'artifact_sha256': sha(glb), 'preflight_sha256': sha(preflight_raw), 'semantic_sha256': sha(semantic_raw)}
        admission_hash = captured(self.root/'admission-host', self.admission_files,
            ['python.exe', '-B', str(self.studio/'pipeline/admission_worker.py'), str(self.root/'admission')],
            self.root/'admission', b'GT05_ADMISSION_COMPLETE ' + canonical(outputs) + b'\n')
        manifest = {'schema': 'HH-GT05-ASSET-MANIFEST-1', 'profile_id': p['profile_id'], 'license': p['license'],
            'external_inputs': [], 'variant': p['variant'], 'source_pins': p['pins'], 'artifacts': p['artifacts'],
            'producer_report_sha256': sha(producer_raw), 'preflight_sha256': sha(preflight_raw),
            'validator_sha256': sha(validator_raw), 'semantic_sha256': preflight['semantic_sha256'],
            'semantic_hash_domain': preflight['semantic_hash_domain'], 'catalog': p['catalog'],
            'formal_acceptance': False, 'public_ack': False}
        manifest_raw = put(self.root/'manifest.json', manifest)
        put(self.root/'validation.json', {'run_id': 'gt05-validation-test', 'upstream_run_id': self.producer['id'],
            'manifest_sha256': sha(manifest_raw), 'host_capture_sha256': host_hash,
            'admission_capture_sha256': admission_hash, 'admission_outputs': outputs, 'completed': True})

    def freeze(self, files, map_name, folder):
        put(self.root/map_name, files)
        for name in files:
            put(self.root/folder/(sha(name.encode()) + Path(name).suffix), (self.studio/name).read_bytes())

    def reject(self, code, action):
        with self.assertRaises(RunRejected) as error:
            action()
        self.assertEqual(error.exception.code, code)

    def rewrite_capture(self, host='host'):
        path = self.root/host
        report = strict((path/'capture.json').read_bytes())
        report['artifacts'] = {name: sha((path/name).read_bytes()) for name in report['artifacts']}
        digest = sha(put(path/'capture.json', report))
        summary = strict((self.root/'validation.json').read_bytes())
        summary['host_capture_sha256' if host == 'host' else 'admission_capture_sha256'] = digest
        put(self.root/'validation.json', summary)

    def test_consistent_capture_is_read_only(self):
        self.make_validation()
        before = {p.relative_to(self.studio): p.read_bytes() for p in self.studio.rglob('*') if p.is_file()}
        result = self.verify()
        self.assertEqual(result['payloads']['fixture.glb'], self.producer['payloads']['fixture.glb'])
        self.assertEqual(before, {p.relative_to(self.studio): p.read_bytes() for p in self.studio.rglob('*') if p.is_file()})

    def test_pass_summary_cannot_hide_nonzero_actual_exit(self):
        self.make_validation()
        put(self.root/'host/process-exit.json', {'pid': 7123, 'exit_code': 9})
        self.rewrite_capture()
        self.reject('CAPTURE_PROCESS_BINDING', self.verify)

    def test_pid_mismatch_rejected_even_with_rehashed_capture(self):
        self.make_validation()
        put(self.root/'host/process-start.json', {'pid': 9999})
        self.rewrite_capture()
        self.reject('CAPTURE_PROCESS_BINDING', self.verify)

    def test_killed_tree_is_not_natural_completion(self):
        self.make_validation()
        report = strict((self.root/'host/capture.json').read_bytes())
        report.update(natural_tree_exit=False, active_before_cleanup=1)
        put(self.root/'host/capture.json', report); self.rewrite_capture()
        self.reject('CAPTURE_NATURAL_EXIT', self.verify)

    def test_unbound_admission_log_is_rejected(self):
        self.make_validation()
        put(self.root/'admission-host/stdout.txt', b'GT05_ADMISSION_COMPLETE {"PASS":true}\n')
        self.rewrite_capture('admission-host')
        self.reject('COMPLETION_MARKER', self.verify)

    def test_resealed_error_colon_stdout_cannot_hide_behind_success_marker(self):
        for host in ('admission-host', 'host'):
            with self.subTest(host=host):
                self.make_validation()
                log = self.root / host / 'stdout.txt'
                put(log, b'Error: native asset operation failed\n' + log.read_bytes())
                self.rewrite_capture(host)
                self.reject('CAPTURE_LOG', self.verify)

    def test_benign_error_counter_in_success_stdout_is_not_an_error_line(self):
        self.make_validation()
        log = self.root / 'host/stdout.txt'
        put(log, b'INFO: error_count=0; warning_count=0; LAST_ERROR_CODE=0\n' + log.read_bytes())
        self.rewrite_capture()
        self.assertEqual(self.verify()['payloads']['fixture.glb'], self.producer['payloads']['fixture.glb'])

    def test_validation_result_warning_rejected_before_summary_can_pass(self):
        self.make_validation()
        report = strict((self.root/'validator.json').read_bytes())
        report['result']['issues']['messages'] = [{'severity': 1, 'code': 'BAD_TEXTURE'}]
        put(self.root/'validator.json', report)
        self.reject('VALIDATOR_ISSUES', self.verify)

    def test_boolean_zero_is_not_validator_count(self):
        self.make_validation()
        report = strict((self.root/'validator.json').read_bytes())
        report['result']['issues']['numWarnings'] = False
        put(self.root/'validator.json', report)
        self.reject('VALIDATOR_ISSUES', self.verify)

    def test_required_source_subset_cannot_be_resealed(self):
        self.make_validation()
        self.files.pop('pipeline/accessor_values.py')
        put(self.root/'source-files.json', self.files)
        invocation = strict((self.root/'host/invocation.json').read_bytes())
        invocation['source_files'] = self.files; put(self.root/'host/invocation.json', invocation)
        self.reject('SOURCE_CLOSURE', self.verify)

    def test_empty_source_map_fails_closed(self):
        self.make_validation(); put(self.root/'source-files.json', {})
        self.reject('SOURCE_CLOSURE', self.verify)

    def test_dependency_lock_requires_all_nine_files(self):
        self.make_validation()
        lock = strict((self.root/'gltf-validator.lock.json').read_bytes())
        del lock['files']['package/module.mjs']; put(self.root/'gltf-validator.lock.json', lock)
        self.reject('DEPENDENCY_LOCK_SET', self.verify)

    def test_dependency_bytes_cannot_follow_forged_summary(self):
        self.make_validation()
        put(self.root/'dependency/package/index.js', b'altered dependency')
        self.reject('DEPENDENCY_HASH', self.verify)

    def test_wrong_payload_even_if_equal_length(self):
        self.make_validation()
        original = (self.root/'fixture.glb').read_bytes()
        put(self.root/'fixture.glb', b'x' + original[1:])
        self.reject('VALIDATION_PRODUCER_BINDING', self.verify)

    def test_changed_profile_pin_resealed_manifest_is_not_accepted(self):
        self.make_validation()
        manifest = strict((self.root/'manifest.json').read_bytes())
        manifest['source_pins'] = {'profile_sha256': '0'*64}
        raw = put(self.root/'manifest.json', manifest)
        summary = strict((self.root/'validation.json').read_bytes())
        summary['manifest_sha256'] = sha(raw); put(self.root/'validation.json', summary)
        self.reject('MANIFEST_BINDING', self.verify)

    def test_current_source_change_is_rejected(self):
        self.make_validation(); put(self.studio/'pipeline/preflight.py', b'changed')
        self.reject('SOURCE_STALE', self.verify)

    def test_stale_diagnostic_retains_recovery_qualification(self):
        self.make_validation(); put(self.studio/'pipeline/preflight.py', b'changed')
        recovery = {'mode': 'POST_EXECUTION_RECOVERY_FROM_EXACT_HASH_EQUAL_BYTES',
            'does_not_claim_pre_execution_copy': True, 'maps': {}}
        for map_name, folder, files in [('source-files.json', 'source', self.files),
            ('admission-source-files.json', 'admission-source', self.admission_files)]:
            recovery['maps'][map_name] = {'map_sha256': sha((self.root/map_name).read_bytes()), 'entries': {
                name: {'sha256': digest, 'snapshot': folder + '/' + sha(name.encode()) + Path(name).suffix}
                for name, digest in files.items()}}
        put(self.root/'snapshot-recovery.json', recovery)
        v = _Verifier(self.studio, False); v.validation('gt05-validation-test', self.producer)
        self.assertIn('pipeline/preflight.py', v.stale)
        self.assertEqual(set(v.qualifiers.values()), {'POST_EXECUTION_RECOVERY_FROM_EXACT_HASH_EQUAL_BYTES'})

    def test_duplicate_json_and_path_escape_rejected(self):
        self.reject('JSON_DUPLICATE_KEY', lambda: strict(b'{"completed":false,"completed":true}'))
        self.reject('RUN_ID', lambda: verify_chain(self.studio, '../outside', 'x', 'y'))

    def make_consumer(self):
        self.make_validation()
        validation = self.verify()
        root = self.studio/'.local/reviews/gt05-consumer-test'
        project = root/'project'; prefix = project.relative_to(self.studio).as_posix() + '/'
        for name in CONSUMER:
            if not (self.studio/name).exists():
                put(self.studio/name, b'# synthetic native source\n')
        put(self.studio/'toolchain.lock.json', {'godot': {'gui_sha256': 'b'*64}})
        pins = {field: sha((self.studio/name).read_bytes()) for field, name in
            [('profile_sha256', 'tests/asset-profile.json'), ('naming_sha256', 'contracts/naming-convention-v1.md'),
             ('toolchain_sha256', 'toolchain.lock.json')]}
        producer = copy.deepcopy(self.producer); producer['report']['pins'] = pins
        for name in AUTHORED:
            put(project/name, (self.studio/'pipeline/godot'/name).read_bytes())
        for name, raw in validation['payloads'].items():
            put(project/'input'/name, raw)
        seed = dict(pins, input_sha256={name: sha(raw) for name, raw in validation['payloads'].items()},
            authored_sha256={name: sha((project/name).read_bytes()) for name in AUTHORED},
            preset_sha256=sha(b'authored synthetic import preset'))
        seed_raw = put(project/'input/consumer.json', seed)
        names = set(CONSUMER) | {prefix + name for name in AUTHORED} | {
            prefix + 'input/' + name for name in (*validation['payloads'], 'consumer.json')}
        files = {name: sha((self.studio/name).read_bytes()) for name in names}
        put(root/'source-files.json', files)
        for name in files:
            put(root/'source'/(sha(name.encode()) + Path(name).suffix), (self.studio/name).read_bytes())
        observed = {'schema': 'HH-GT05-GODOT-OBSERVATION-1', 'phase': 'baseline', 'formal_acceptance': False,
            'pid': 7123, 'input_sha256': seed['input_sha256'], 'authored_sha256': seed['authored_sha256'],
            'consumer_sha256': sha(seed_raw), 'engine': {'major': 4, 'minor': 7, 'patch': 2, 'status': 'stable',
                'hash': 'ed1daf0bf'}, 'authored': {'script': 'res://authored.gd'}}
        raw = put(project/'out/baseline.json', observed)
        captures = {}
        for stage, argv in [('import', ['godot.exe', '--headless', '--editor', '--path', str(project), '--import']),
            ('baseline', ['godot.exe', '--headless', '--path', str(project), '--script', 'res://probe.gd',
                          '--', '--phase', 'baseline'])]:
            marker = b'' if stage == 'import' else b'GT05_GODOT_OBSERVED ' + canonical({
                'phase': 'baseline', 'pid': 7123, 'report_sha256': sha(raw), 'formal_acceptance': False}) + b'\n'
            captures[stage] = captured(root/(stage+'-host'), files, argv, project, marker, binary='b'*64)
        put(root/'consumer.json', {'schema': 'HH-GT05-CONSUMER-DIAGNOSTIC-1', 'run_id': root.name,
            'validator_run_id': validation['id'], 'host_captures': captures, 'observation_sha256': sha(raw),
            'import_preset_before_sha256': sha(put(root/'input-preset.snapshot', b'authored synthetic import preset')),
            'import_preset_after_sha256': sha(put(root/'imported-preset.snapshot', b'generated synthetic import config'))})
        # The historical comparator is deliberately unavailable. Diagnostic
        # binding must not execute today's comparator against this older source.
        put(self.studio/'pipeline/godot/consumer.py', b'# later comparator revision\n')
        return root, project, producer, validation

    def test_baseline_inputs_remain_frozen_after_same_project_reimport(self):
        root, project, producer, validation = self.make_consumer()
        put(project/'input/fixture.glb', b'edited source now occupies same project')
        put(project/'input/manifest.json', b'new manifest')
        result = _Verifier(self.studio, False).consumer(root.name, producer, validation)
        self.assertEqual(result['input_raw']['fixture.glb'], validation['payloads']['fixture.glb'])
        self.assertIsNone(result['checks'])
        self.assertFalse(result['comparable'])

    def test_baseline_frozen_input_cannot_be_replaced_by_current_project(self):
        root, project, producer, validation = self.make_consumer()
        logical = project.relative_to(self.studio).as_posix() + '/input/fixture.glb'
        put(root/'source'/(sha(logical.encode())+'.glb'), b'edited payload')
        self.reject('SOURCE_SNAPSHOT_HASH', lambda: _Verifier(self.studio, False).consumer(root.name, producer, validation))

    def test_import_preset_snapshot_cannot_be_substituted(self):
        root, _, producer, validation = self.make_consumer()
        put(root/'input-preset.snapshot', b'wrong importer configuration')
        self.reject('CONSUMER_PRESET_SNAPSHOT', lambda: _Verifier(self.studio, False).consumer(root.name, producer, validation))

    def test_already_stopped_raises_original_error_before_any_io(self):
        error = ValueError('SNAPSHOT_STOPPED')
        def guard():
            raise error
        with patch.object(Path, 'lstat', side_effect=AssertionError('unexpected stat')), \
             patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected read')):
            with self.assertRaises(ValueError) as rejected:
                verify_chain(self.studio, 'gt05-producer-test', 'gt05-validation-test',
                    'gt05-consumer-test', phase_guard=guard)
        self.assertIs(rejected.exception, error)

    def interrupted_after_first_read(self, error):
        first = self.studio/'.local/reviews/gt05-producer-test/diagnostic.json'
        put(first, {'placeholder': 'Stop must win before later evidence is examined'})
        stopped, reads = [False], []
        original = Path.read_bytes
        def guard():
            if stopped[0]:
                raise error
        def read(path):
            reads.append(path)
            value = original(path)
            stopped[0] = True
            return value
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaises(type(error)) as rejected:
                verify_chain(self.studio, 'gt05-producer-test', 'gt05-validation-test',
                    'gt05-consumer-test', phase_guard=guard)
        self.assertIs(rejected.exception, error)
        self.assertEqual(reads, [first])

    def test_midread_stop_prevents_every_later_read(self):
        self.interrupted_after_first_read(RuntimeError('SNAPSHOT_STOPPED'))

    def test_midread_deadline_value_error_is_not_wrapped_as_evidence_schema(self):
        # The public wrapper normally translates ValueError to EVIDENCE_SCHEMA.
        # Deadline errors belong to the owner and must preserve their identity.
        self.interrupted_after_first_read(ValueError('SNAPSHOT_DEADLINE_EXPIRED'))

    def test_stop_during_source_snapshot_prevents_current_source_read(self):
        self.make_validation()
        expired, reads = [False], []
        error = TimeoutError('SNAPSHOT_DEADLINE_EXPIRED')
        original = Path.read_bytes
        def guard():
            if expired[0]:
                raise error
        def read(path):
            reads.append(path)
            value = original(path)
            if path.parent == self.root/'source':
                expired[0] = True
            return value
        v = _Verifier(self.studio, True, phase_guard=guard)
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaises(TimeoutError) as rejected:
                v.source(self.root, VALIDATION)
        self.assertIs(rejected.exception, error)
        self.assertEqual(reads[0], self.root/'source-files.json')
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[1].parent, self.root/'source')


if __name__ == '__main__':
    unittest.main()
