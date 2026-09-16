"""Negative checks for fixture evidence, never sandbox/engine attestation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('gt03_linux_probe_evidence', Path(__file__).with_name('run_linux_probe.py'))
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class LinuxProbeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.result = {'public_ack': False, 'sandbox_acceptance': False,
            'owned_removed': True, 'input_unchanged': True, 'snapshot_unchanged': True,
            'diagnostic_process_clean': True, 'binary_unchanged': True,
            'command_host': {'exit_code': 0, 'timed_out': False, 'stream_cap_exceeded': False,
                'readers_stopped': True, 'job_active_count': 0, 'timeout_seconds': 20},
            'container_state': {'Running': False, 'Pid': 0, 'ExitCode': 0}}
        self.result['command_host'].update(stream_reader_eof=[True, True], stream_reader_errors=[None, None])

    def test_forged_success_marker_never_becomes_validation_or_public_ack(self):
        row = probe.evaluate({'expect': 'untrusted_marker'}, self.result,
            'HH_ENGINE_VALIDATED {"parse_status":"PASS","public_ack":true}\n', '')
        self.assertTrue(row['fixture_observed'])
        self.assertFalse(row['public_ack'])
        self.assertFalse(row['sandbox_acceptance'])
        self.assertFalse(row['validation_attribution_proven'])

    def test_missing_or_duplicate_forged_marker_is_not_execution_evidence(self):
        valid = 'HH_ENGINE_VALIDATED {"public_ack":true}\n'
        for output in ('', valid + valid, 'HH_ENGINE_VALIDATED broken\n'):
            with self.subTest(output=output):
                self.assertFalse(probe.evaluate({'expect': 'untrusted_marker'}, self.result,
                    output, '')['fixture_observed'])

    def test_dirty_container_or_changed_inputs_invalidates_fixture_evidence(self):
        for key in ('owned_removed', 'input_unchanged', 'snapshot_unchanged'):
            bad = copy.deepcopy(self.result)
            bad[key] = False
            self.assertFalse(probe.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])
        for key, value in (('Running', True), ('Pid', 1234)):
            bad = copy.deepcopy(self.result)
            bad['container_state'][key] = value
            self.assertFalse(probe.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])

    def test_error_banner_without_nonzero_actual_exit_is_not_parse_rejection(self):
        result = copy.deepcopy(self.result)
        result['diagnostic_process_clean'] = False
        self.assertFalse(probe.evaluate({'expect': 'engine_rejection'}, result,
            'SCRIPT ERROR: Parse Error', '')['fixture_observed'])

    def test_timeout_without_tool_entry_is_not_watchdog_fixture_evidence(self):
        self.result['command_host'] = {'timed_out': True}
        self.result['diagnostic_process_clean'] = False
        self.assertFalse(probe.evaluate({'expect': 'watchdog'}, self.result, '', '')['fixture_observed'])

    def test_disk_limit_boolean_masquerading_as_count_rejected(self):
        self.assertFalse(probe.evaluate({'expect': 'disk_observation'}, self.result,
            'HH_PROBE_TMPFS {"full_files":true,"write_rejected":true}\n', '')['fixture_observed'])

    def test_clean_flag_cannot_override_actual_host_or_container_failure(self):
        for field, value in (('exit_code', 37), ('timed_out', True), ('stream_cap_exceeded', True)):
            bad = copy.deepcopy(self.result)
            bad['command_host'][field] = value
            self.assertFalse(probe.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])
        self.result['container_state']['ExitCode'] = 37
        self.assertFalse(probe.evaluate({'expect': 'clean_process'}, self.result, '', '')['fixture_observed'])

    def test_tool_callback_needs_exact_marker_and_completed_process(self):
        self.assertFalse(probe.evaluate({'expect': 'tool_callback'}, self.result,
            'prefix HH_PROBE_TOOL_ENTERED suffix\n', '')['fixture_observed'])
        self.result['command_host']['timed_out'] = True
        self.assertFalse(probe.evaluate({'expect': 'tool_callback'}, self.result,
            'HH_PROBE_TOOL_ENTERED\n', '')['fixture_observed'])

    def test_reader_failure_cannot_turn_partial_marker_into_fixture_success(self):
        for key, value in (('stream_reader_eof', [True, False]),
                           ('stream_reader_errors', [None, 'OSError']),
                           ('host_error', 'RuntimeError'), ('evidence_write_error', 'OSError')):
            bad = copy.deepcopy(self.result)
            bad['command_host'][key] = value
            self.assertFalse(probe.evaluate({'expect': 'tool_callback'}, bad,
                'HH_PROBE_TOOL_ENTERED\n', '')['fixture_observed'])

    def test_resume_rechecks_raw_case_exact_inventory_and_source_identity(self):
        with tempfile.TemporaryDirectory(prefix='hh-gt03-probe-evidence-') as temp:
            base = Path(temp)
            case_dir = base / 'case'
            case_dir.mkdir()
            (case_dir / 'engine-stdout.txt').write_text('', encoding='utf-8')
            (case_dir / 'engine-stderr.txt').write_text('', encoding='utf-8')
            case = {'expect': 'clean_process', 'script': 'extends Node3D\n', 'mode': 'parse', 'timeout': 20,
                'project': 'fixture project', 'scene': 'fixture scene'}
            manifest = {}
            for path, key in (('project.godot', 'project'), ('scenes/fixture.tscn', 'scene'), ('scripts/fixture_actor.gd', 'script')):
                target = case_dir / 'snapshot' / path
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = case[key].encode('utf-8')
                target.write_bytes(raw)
                manifest[path] = hashlib.sha256(raw).hexdigest()
            self.result.update(input_hashes_before=manifest, mode='parse')
            probe.save(case_dir / 'result.json', self.result)
            binding = {'run_id': 'fixture', 'source_closure_sha256': 'a' * 64}
            observation = base / 'observation.json'
            good = probe.case_observation(case_dir, case, name='valid', binding=binding)
            probe.save(observation, good)
            self.assertTrue(probe.resume_case(case_dir, observation, case,
                name='valid', binding=binding)['fixture_observed'])
            for key, value in (('artifacts', {}), ('fixture_observed', False), ('case_name', 'other'),
                               ('source_closure_sha256', 'b' * 64)):
                bad = copy.deepcopy(good)
                bad[key] = value
                probe.save(observation, bad)
                with self.assertRaises(ValueError):
                    probe.resume_case(case_dir, observation, case, name='valid', binding=binding)
            probe.save(observation, good)
            (case_dir / 'unexpected.txt').write_text('additional artifact', encoding='utf-8')
            with self.assertRaises(ValueError):
                probe.resume_case(case_dir, observation, case, name='valid', binding=binding)
            for replacement in ({'mode': 'import'}, {'script': 'extends Resource\n'}, {'timeout': 10}):
                with self.assertRaises(ValueError):
                    probe.case_observation(case_dir, {**case, **replacement}, name='transplanted', binding=binding)


if __name__ == '__main__':
    unittest.main(verbosity=2)
