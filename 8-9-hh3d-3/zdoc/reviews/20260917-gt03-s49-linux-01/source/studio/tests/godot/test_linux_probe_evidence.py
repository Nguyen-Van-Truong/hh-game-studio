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
    @staticmethod
    def clean_result(timeout=20):
        container_id = 'c' * 64
        return {'schema': 'hh-gt03-linux-diagnostic-1', 'public_ack': False, 'sandbox_acceptance': False,
            'container_id': container_id, 'owner_record_retained': False, 'docker_wait_exit': 0, 'errors': [],
            'admission': {'acquired': True, 'released': True, 'maximum_active': 1},
            'supervisor': {'path': '/usr/bin/timeout', 'sha256': probe.SUPERVISOR_SHA256,
                'term_after_seconds': max(1, timeout - 1), 'kill_after_seconds': 1,
                'total_deadline_seconds': max(2, timeout), 'pid': 1, 'requires_yama_scope': [1, 2, 3],
                'host_death_acceptance': False},
            'toolchain': {'supervisor_path': '/usr/bin/timeout', 'supervisor_sha256': probe.SUPERVISOR_SHA256,
                'supervisor_bootstrap_sha256': probe.SUPERVISOR_BOOTSTRAP_SHA256,
                'docker_context': probe.DOCKER_CONTEXT, 'docker_endpoint': probe.DOCKER_ENDPOINT},
            'owned_removed': True, 'input_unchanged': True, 'snapshot_unchanged': True,
            'diagnostic_process_clean': True, 'binary_unchanged': True,
            'command_host': {'exit_code': 0, 'timed_out': False, 'stream_cap_exceeded': False,
                'argv': ['docker.exe', '--context', probe.DOCKER_CONTEXT, 'start', '--attach', container_id],
                'readers_stopped': True, 'job_active_count': 0, 'timeout_seconds': timeout + 2,
                'stream_reader_eof': [True, True], 'stream_reader_errors': [None, None],
                'job_owner': {'configured': True, 'assigned': True, 'closed': True, 'zero_observed': True,
                    'tainted': False, 'handle_retained': False, 'active_count': 0,
                    'failed_operations': [], 'native_error': None}},
            'container_state': {'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}}

    def setUp(self):
        self.result = self.clean_result()

    @staticmethod
    def evaluate(case, result, stdout='', stderr=''):
        return probe.evaluate({'timeout': 20, **case}, result, stdout, stderr)

    def watchdog_result(self, code=124, timeout=20):
        result = self.clean_result(timeout)
        result.update(diagnostic_process_clean=False, docker_wait_exit=code,
                      errors=['EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN'])
        result['command_host']['exit_code'] = result['container_state']['ExitCode'] = code
        return result

    def test_forged_success_marker_never_becomes_validation_or_public_ack(self):
        row = self.evaluate({'expect': 'untrusted_marker'}, self.result,
            'HH_ENGINE_VALIDATED {"parse_status":"PASS","public_ack":true}\n', '')
        self.assertTrue(row['fixture_observed'])
        self.assertFalse(row['public_ack'])
        self.assertFalse(row['sandbox_acceptance'])
        self.assertFalse(row['validation_attribution_proven'])

    def test_missing_or_duplicate_forged_marker_is_not_execution_evidence(self):
        valid = 'HH_ENGINE_VALIDATED {"public_ack":true}\n'
        for output in ('', valid + valid, 'HH_ENGINE_VALIDATED broken\n'):
            with self.subTest(output=output):
                self.assertFalse(self.evaluate({'expect': 'untrusted_marker'}, self.result,
                    output, '')['fixture_observed'])

    def test_dirty_container_or_changed_inputs_invalidates_fixture_evidence(self):
        for key in ('owned_removed', 'input_unchanged', 'snapshot_unchanged'):
            bad = copy.deepcopy(self.result)
            bad[key] = False
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])
        for key, value in (('Running', True), ('Pid', 1234)):
            bad = copy.deepcopy(self.result)
            bad['container_state'][key] = value
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])

    def test_error_banner_without_nonzero_actual_exit_is_not_parse_rejection(self):
        result = copy.deepcopy(self.result)
        result['diagnostic_process_clean'] = False
        self.assertFalse(self.evaluate({'expect': 'engine_rejection'}, result,
            'SCRIPT ERROR: Parse Error', '')['fixture_observed'])

    def test_timeout_without_tool_entry_is_not_watchdog_fixture_evidence(self):
        self.result['command_host'] = {'timed_out': True}
        self.result['diagnostic_process_clean'] = False
        self.assertFalse(self.evaluate({'expect': 'watchdog'}, self.result, '', '')['fixture_observed'])

    def test_disk_limit_boolean_masquerading_as_count_rejected(self):
        self.assertFalse(self.evaluate({'expect': 'disk_observation'}, self.result,
            'HH_PROBE_TMPFS {"full_files":true,"write_rejected":true}\n', '')['fixture_observed'])

    def test_clean_flag_cannot_override_actual_host_or_container_failure(self):
        for field, value in (('exit_code', 37), ('timed_out', True), ('stream_cap_exceeded', True)):
            bad = copy.deepcopy(self.result)
            bad['command_host'][field] = value
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad, '', '')['fixture_observed'])
        self.result['container_state']['ExitCode'] = 37
        self.assertFalse(self.evaluate({'expect': 'clean_process'}, self.result, '', '')['fixture_observed'])

    def test_tool_callback_needs_exact_marker_and_completed_process(self):
        self.assertFalse(self.evaluate({'expect': 'tool_callback'}, self.result,
            'prefix HH_PROBE_TOOL_ENTERED suffix\n', '')['fixture_observed'])
        self.result['command_host']['timed_out'] = True
        self.assertFalse(self.evaluate({'expect': 'tool_callback'}, self.result,
            'HH_PROBE_TOOL_ENTERED\n', '')['fixture_observed'])

    def test_reader_failure_cannot_turn_partial_marker_into_fixture_success(self):
        for key, value in (('stream_reader_eof', [True, False]),
                           ('stream_reader_errors', [None, 'OSError']),
                           ('host_error', 'RuntimeError'), ('evidence_write_error', 'OSError')):
            bad = copy.deepcopy(self.result)
            bad['command_host'][key] = value
            self.assertFalse(self.evaluate({'expect': 'tool_callback'}, bad,
                'HH_PROBE_TOOL_ENTERED\n', '')['fixture_observed'])

    def test_supervisor_watchdog_requires_native_timeout_and_clean_attach_lifecycle(self):
        for timeout in (1, 2, 3, 10, 20):
            for code in (124, 137):
                with self.subTest(timeout=timeout, code=code):
                    result = self.watchdog_result(code, timeout)
                    row = self.evaluate({'expect': 'watchdog', 'timeout': timeout}, result,
                                        'HH_PROBE_BUSY_ENTERED\n')
                    self.assertTrue(row['fixture_observed'])
                    self.assertTrue(row['supervisor_watchdog_observed'])
                    self.assertFalse(row['host_watchdog_observed'])
                    self.assertFalse(row['public_ack'])
                    self.assertFalse(row['sandbox_acceptance'])
                    self.assertFalse(row['validation_attribution_proven'])

    def test_host_watchdog_is_a_distinct_diagnostic_not_supervisor_evidence(self):
        result = self.watchdog_result(137)
        result['command_host'].update(timed_out=True, exit_code=2)
        row = self.evaluate({'expect': 'watchdog'}, result, 'HH_PROBE_BUSY_ENTERED\n')
        self.assertTrue(row['host_watchdog_observed'])
        self.assertFalse(row['supervisor_watchdog_observed'])
        self.assertFalse(row['fixture_observed'])

    def test_watchdog_missing_duplicate_or_embedded_callback_is_not_evidence(self):
        result = self.watchdog_result()
        for stdout in ('', 'prefix HH_PROBE_BUSY_ENTERED\n',
                       'HH_PROBE_BUSY_ENTERED suffix\n', 'HH_PROBE_BUSY_ENTERED\n' * 2):
            with self.subTest(stdout=stdout):
                self.assertFalse(self.evaluate({'expect': 'watchdog'}, result, stdout)['fixture_observed'])

    def test_watchdog_wrong_missing_or_inconsistent_native_exit_rejected(self):
        for code in (0, 1, 2, 125, True, 137.0, '124', None):
            with self.subTest(code=code):
                result = self.watchdog_result(code)
                self.assertFalse(self.evaluate({'expect': 'watchdog'}, result,
                    'HH_PROBE_BUSY_ENTERED\n')['fixture_observed'])
        for section, key, value in ((None, 'docker_wait_exit', 137),
                                   ('command_host', 'exit_code', 137),
                                   ('container_state', 'OOMKilled', True),
                                   ('container_state', 'Pid', 17),
                                   ('command_host', 'stream_cap_exceeded', True)):
            bad = self.watchdog_result()
            (bad if section is None else bad[section])[key] = value
            self.assertFalse(self.evaluate({'expect': 'watchdog'}, bad,
                'HH_PROBE_BUSY_ENTERED\n')['fixture_observed'])

    def test_supervisor_missing_or_tampered_policy_rejected_for_all_fixture_types(self):
        values = {'path': '/tmp/timeout', 'sha256': '0' * 64, 'term_after_seconds': 20,
            'kill_after_seconds': True, 'total_deadline_seconds': 20.0, 'pid': True,
            'requires_yama_scope': [True, 2, 3], 'host_death_acceptance': 0}
        for key, value in values.items():
            for missing in (False, True):
                with self.subTest(key=key, missing=missing):
                    bad = copy.deepcopy(self.result)
                    if missing:
                        del bad['supervisor'][key]
                    else:
                        bad['supervisor'][key] = value
                    row = self.evaluate({'expect': 'clean_process'}, bad)
                    self.assertFalse(row['fixture_observed'])
                    self.assertFalse(row['supervisor_binding_verified'])
        for timeout in (True, 0, 21, 20.0, '20', None):
            self.assertFalse(self.evaluate({'expect': 'clean_process', 'timeout': timeout},
                self.result)['fixture_observed'])

    def test_host_deadline_must_include_exact_two_second_attach_grace(self):
        for timeout in (None, 20, 21, 23, 22.0, True, '22'):
            bad = copy.deepcopy(self.result)
            if timeout is None:
                del bad['command_host']['timeout_seconds']
            else:
                bad['command_host']['timeout_seconds'] = timeout
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])

    def test_fixed_supervisor_bootstrap_and_context_must_match_attached_container(self):
        for key in ('supervisor_path', 'supervisor_sha256', 'supervisor_bootstrap_sha256',
                    'docker_context', 'docker_endpoint'):
            for missing in (False, True):
                bad = copy.deepcopy(self.result)
                if missing:
                    del bad['toolchain'][key]
                else:
                    bad['toolchain'][key] = 'other'
                self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])
        for argv in (None, [], ['docker.exe', 'start', '--attach', 'c' * 64],
                     ['docker.exe', '--context', 'other', 'start', '--attach', 'c' * 64],
                     ['docker.exe', '--context', probe.DOCKER_CONTEXT, 'start', '--attach', 'd' * 64]):
            bad = copy.deepcopy(self.result)
            bad['command_host']['argv'] = argv
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])

    def test_missing_or_uncertain_cli_job_owner_cannot_pass_with_zero_process_count(self):
        for key in self.result['command_host']['job_owner']:
            bad = copy.deepcopy(self.result)
            del bad['command_host']['job_owner'][key]
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])
        wrong = {'configured': 1, 'assigned': 1, 'closed': False, 'zero_observed': 1,
            'tainted': 0, 'handle_retained': True, 'active_count': False,
            'failed_operations': ['CLOSE'], 'native_error': 0}
        for key, value in wrong.items():
            bad = copy.deepcopy(self.result)
            bad['command_host']['job_owner'][key] = value
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])
        for owner in (None, [], True, 'closed'):
            bad = copy.deepcopy(self.result)
            bad['command_host']['job_owner'] = owner
            self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])

    def test_boolean_numbers_and_falsy_errors_do_not_bypass_cleanup_checks(self):
        for section, key, value in ((None, 'docker_wait_exit', False),
            (None, 'diagnostic_process_clean', 1), (None, 'owned_removed', 1),
            (None, 'owner_record_retained', 0), (None, 'errors', None),
            (None, 'errors', ['EXECUTOR_ADMISSION_CLOSE_UNCERTAIN']),
            ('admission', 'released', 1), ('admission', 'maximum_active', True),
            ('container_state', 'Pid', False), ('container_state', 'ExitCode', False),
            ('container_state', 'Running', 0), ('container_state', 'OOMKilled', 0),
            ('command_host', 'exit_code', False), ('command_host', 'job_active_count', False),
            ('command_host', 'timed_out', 0), ('command_host', 'stream_cap_exceeded', 0),
            ('command_host', 'stream_reader_eof', [1, 1]), ('command_host', 'host_error', False),
            ('command_host', 'evidence_write_error', '')):
            with self.subTest(section=section, key=key):
                bad = copy.deepcopy(self.result)
                (bad if section is None else bad[section])[key] = value
                self.assertFalse(self.evaluate({'expect': 'clean_process'}, bad)['fixture_observed'])

    def test_parse_rejection_needs_matching_attach_exit_and_not_a_supervisor_timeout(self):
        for code in (1, 124, 137):
            result = self.watchdog_result(code)
            row = self.evaluate({'expect': 'engine_rejection'}, result, 'SCRIPT ERROR: Parse Error\n')
            self.assertEqual(row['fixture_observed'], code == 1)
        result = self.watchdog_result(1)
        result['command_host']['exit_code'] = 0
        self.assertFalse(self.evaluate({'expect': 'engine_rejection'}, result,
            'SCRIPT ERROR: Parse Error\n')['fixture_observed'])

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
            self.result.update(input_hashes_before=manifest, input_hashes_after=manifest,
                               snapshot_hashes_after=manifest, mode='parse')
            probe.save(case_dir / 'result.json', self.result)
            binding = {'run_id': 'fixture', 'source_closure_sha256': 'a' * 64}
            observation = base / 'observation.json'
            good = probe.case_observation(case_dir, case, name='valid', binding=binding)
            probe.save(observation, good)
            self.assertTrue(probe.resume_case(case_dir, observation, case,
                name='valid', binding=binding)['fixture_observed'])
            for section, key, value in ((None, 'input_hashes_after', {}),
                (None, 'snapshot_hashes_after', {}), ('command_host', 'timeout_seconds', 20),
                ('supervisor', 'term_after_seconds', 20), ('supervisor', 'kill_after_seconds', 0),
                ('supervisor', 'total_deadline_seconds', 22), ('toolchain', 'docker_context', 'other')):
                bad = copy.deepcopy(self.result)
                (bad if section is None else bad[section])[key] = value
                probe.save(case_dir / 'result.json', bad)
                with self.assertRaises(ValueError):
                    probe.case_observation(case_dir, case, name='valid', binding=binding)
            probe.save(case_dir / 'result.json', self.result)
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
