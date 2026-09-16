"""Pure rejection of raw profile evidence; synthetic lifecycle is not engine proof."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


probe = load('gt03_profile_probe_evidence', Path(__file__).with_name('run_profile_probe.py'))
comparator = load('gt03_profile_probe_comparator', STUDIO/'godot-addon/profile_readback.py')
factory = comparator.factory
SCRIPT = (b'extends Node3D\n@export var fixture_value: int = 9\n'
    b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
    b'@export var enabled: bool = false\n')
PHASES = [item for phase in ('parse', 'import', 'readback')
          for item in ('HH_PROFILE_PHASE_BEGIN ' + phase, 'HH_PROFILE_PHASE_END ' + phase + ' 0')]


def raw_output(observation):
    # The fixed bootstrap emits inside the readback process, before the fixed
    # driver can report its exit. These raw records must retain that ordering.
    marker = 'HH_PROFILE_READBACK ' + json.dumps(observation, separators=(',', ':'))
    return '\n'.join(PHASES[:-1] + [marker, PHASES[-1]]) + '\n'


class ProfileProbeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.bundle = factory.compose(factory.DEFAULT_SCENE, SCRIPT,
            scene_revision='sha256:' + '1' * 64, engine_sha256='2' * 64)
        saved = json.loads((STUDIO/'tests/godot/fixtures/profile-readback-baseline.json').read_bytes())
        self.observation = saved['observation']
        hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in self.bundle.files.items()}
        # Historical S49 property rows remain historical. Only the synthetic
        # lifecycle below uses today's release hashes; it is not a new native
        # run and its v1 observation cannot supply a semantic revision.
        changed = 'addons/hh_studio/scene_commands.gd'
        self.assertEqual(set(hashes), set(saved['input_hashes']))
        self.assertEqual(saved['input_hashes'][changed],
                         'ac4bf9e239b082efe9dd542f14c6cb8e202597bdfa1b8160e5da7905413aa0ea')
        self.assertNotEqual(hashes[changed], saved['input_hashes'][changed])
        self.assertEqual({k:v for k,v in hashes.items() if k != changed},
                         {k:v for k,v in saved['input_hashes'].items() if k != changed})
        # Explicit synthetic lifecycle facts only. No Docker or engine starts.
        self.result = {
            'schema': 'hh-gt03-linux-diagnostic-1', 'mode': 'profile-validate',
            'public_ack': False, 'sandbox_acceptance': False,
            'diagnostic_process_clean': True, 'profile_eligible': True,
            'profile_harness_unchanged': True,
            'profile_harness_sha256': probe.sha(probe.STUDIO/'godot-addon/validation_bootstrap.gd'),
            'admission': {'acquired': True, 'maximum_active': 1},
            'owner_record_retained': False, 'errors': [],
            'owned_removed': True, 'input_unchanged': True, 'snapshot_unchanged': True,
            'binary_unchanged': True, 'log_clean': True,
            'container_state': {'ExitCode': 0, 'Running': False, 'Pid': 0, 'OOMKilled': False},
            'docker_wait_exit': 0,
            'command_host': {'exit_code': 0, 'job_active_count': 0, 'readers_stopped': True,
                'stream_reader_eof': [True, True], 'stream_reader_errors': [None, None],
                'timed_out': False, 'stream_cap_exceeded': False,
                'job_owner': {'configured': True, 'assigned': True, 'closed': True,
                    'zero_observed': True, 'tainted': False, 'handle_retained': False,
                    'active_count': 0, 'failed_operations': [], 'native_error': None}},
            'input_hashes_before': dict(hashes), 'input_hashes_after': dict(hashes),
            'snapshot_hashes_after': dict(hashes),
        }
        self.stdout = raw_output(self.observation)

    def evaluate(self, *, result=None, stdout=None, stderr='', bundle=None):
        return probe.evaluate(self.result if result is None else result,
            self.stdout if stdout is None else stdout, stderr,
            self.bundle if bundle is None else bundle, comparator)

    def rejected(self, **changes):
        verdict = self.evaluate(**changes)
        self.assertIs(verdict['passed'], False)
        self.assertIs(verdict['public_ack'], False)
        self.assertIs(verdict['sandbox_acceptance'], False)

    def test_consistent_replay_data_is_internal_comparison_only(self):
        verdict = self.evaluate()
        self.assertIs(verdict['passed'], True)
        self.assertIs(verdict['public_ack'], False)
        self.assertIs(verdict['sandbox_acceptance'], False)
        self.assertIs(verdict['comparison']['process_attribution_proven'], False)
        self.assertIs(verdict['comparison']['semantic_observed'], False)
        self.assertIsNone(verdict['comparison']['semantic_revision'])

    def test_each_missing_reordered_duplicate_or_failed_phase_rejected(self):
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.rejected(stdout=self.stdout.replace(phase + '\n', '', 1))
                self.rejected(stdout=phase + '\n' + self.stdout)
        self.rejected(stdout=self.stdout.replace('HH_PROFILE_PHASE_END import 0', 'HH_PROFILE_PHASE_END import 45'))
        self.rejected(stdout=self.stdout.replace('HH_PROFILE_PHASE_BEGIN parse', 'HH_PROFILE_PHASE_BEGIN other'))
        self.rejected(stdout=self.stdout.replace(PHASES[0], 'TEMP').replace(PHASES[1], PHASES[0]).replace('TEMP', PHASES[1]))

    def test_readback_marker_must_be_between_readback_begin_and_end(self):
        lines = self.stdout.splitlines()
        marker = next(line for line in lines if line.startswith('HH_PROFILE_READBACK '))
        phases = '\n'.join(PHASES) + '\n'
        self.rejected(stdout=marker + '\n' + phases)
        self.rejected(stdout=phases + marker + '\n')
        self.rejected(stdout='\n'.join(PHASES[:3] + [marker] + PHASES[3:]) + '\n')

    def test_missing_duplicate_malformed_or_duplicate_key_report_rejected(self):
        marker = next(line for line in self.stdout.splitlines() if line.startswith('HH_PROFILE_READBACK '))
        self.rejected(stdout=self.stdout.replace(marker + '\n', ''))
        self.rejected(stdout=self.stdout.replace(marker, marker + '\n' + marker))
        self.rejected(stdout=self.stdout.replace(marker, 'HH_PROFILE_READBACK broken'))
        duplicate = marker.replace('"ok":true', '"ok":true,"ok":true')
        self.assertNotEqual(duplicate, marker)
        self.rejected(stdout=self.stdout.replace(marker, duplicate))

    def test_missing_top_level_report_fact_or_nonfinite_value_rejected(self):
        for key in self.observation:
            bad = copy.deepcopy(self.observation)
            del bad[key]
            with self.subTest(key=key):
                self.rejected(stdout=raw_output(bad))
        bad = copy.deepcopy(self.observation)
        bad['instance_nodes'][0]['exports']['move_speed']['value'] = float('nan')
        self.rejected(stdout=raw_output(bad))

    def test_stale_missing_or_extra_input_hash_any_phase_rejected(self):
        for key in ('input_hashes_before', 'input_hashes_after', 'snapshot_hashes_after'):
            for change in ('stale', 'missing', 'extra'):
                bad = copy.deepcopy(self.result)
                if change == 'stale':
                    bad[key]['scripts/fixture_actor.gd.uid'] = 'a' * 64
                elif change == 'missing':
                    del bad[key]['addons/hh_studio/plugin.gd']
                else:
                    bad[key]['scripts/rogue.gd'] = 'a' * 64
                with self.subTest(key=key, change=change):
                    self.rejected(result=bad)

    def test_missing_actual_exit_or_wait_fact_rejected_despite_clean_flag(self):
        for container, key in (('container_state', 'ExitCode'), ('container_state', 'Pid'),
                               ('command_host', 'exit_code'), ('command_host', 'job_active_count')):
            bad = copy.deepcopy(self.result)
            del bad[container][key]
            with self.subTest(container=container, key=key):
                self.rejected(result=bad)
        bad = copy.deepcopy(self.result)
        del bad['docker_wait_exit']
        self.rejected(result=bad)

    def test_native_integer_facts_cannot_be_booleans_or_float_counts(self):
        for container, key in (('container_state', 'ExitCode'), ('container_state', 'Pid'),
                               ('command_host', 'exit_code'), ('command_host', 'job_active_count')):
            for value in (False, 0.0):
                bad = copy.deepcopy(self.result)
                bad[container][key] = value
                with self.subTest(container=container, key=key, value=value):
                    self.rejected(result=bad)
        for value in (False, 0.0):
            bad = copy.deepcopy(self.result)
            bad['docker_wait_exit'] = value
            self.rejected(result=bad)
        for value in (True, 1.0):
            bad = copy.deepcopy(self.result)
            bad['admission']['maximum_active'] = value
            self.rejected(result=bad)

    def test_wrong_schema_or_mode_cannot_transplant_profile_evidence(self):
        for key, value in (('schema', 'other'), ('mode', 'parse'), ('mode', 'import')):
            bad = copy.deepcopy(self.result)
            bad[key] = value
            with self.subTest(key=key, value=value):
                self.rejected(result=bad)

    def test_required_negative_stream_facts_and_boolean_eof_are_exact(self):
        for key in ('timed_out', 'stream_cap_exceeded'):
            bad = copy.deepcopy(self.result)
            del bad['command_host'][key]
            with self.subTest(key=key, change='missing'):
                self.rejected(result=bad)
            bad['command_host'][key] = 0
            with self.subTest(key=key, change='integer'):
                self.rejected(result=bad)
        for value in ([1, 1], [True, 1]):
            bad = copy.deepcopy(self.result)
            bad['command_host']['stream_reader_eof'] = value
            self.rejected(result=bad)

    def test_native_job_close_facts_are_required_and_cannot_be_overridden_by_clean_flag(self):
        for key, value in (('closed', False), ('zero_observed', False),
                           ('tainted', True), ('handle_retained', True)):
            bad = copy.deepcopy(self.result)
            bad['command_host']['job_owner'][key] = value
            with self.subTest(key=key, change='dirty'):
                self.rejected(result=bad)
            del bad['command_host']['job_owner'][key]
            with self.subTest(key=key, change='missing'):
                self.rejected(result=bad)
        bad = copy.deepcopy(self.result)
        del bad['command_host']['job_owner']
        self.rejected(result=bad)

    def test_missing_or_changed_lifecycle_checks_rejected(self):
        for key in ('diagnostic_process_clean', 'profile_eligible', 'profile_harness_unchanged',
                    'owned_removed', 'input_unchanged', 'snapshot_unchanged', 'binary_unchanged', 'log_clean'):
            bad = copy.deepcopy(self.result)
            del bad[key]
            with self.subTest(key=key):
                self.rejected(result=bad)
            bad[key] = False
            self.rejected(result=bad)
        for key, value in (('owner_record_retained', True), ('errors', ['uncertain'])):
            bad = copy.deepcopy(self.result)
            bad[key] = value
            self.rejected(result=bad)

    def test_harness_hash_is_actual_frozen_helper_hash(self):
        for value in (None, '', 'a' * 64):
            bad = copy.deepcopy(self.result)
            bad['profile_harness_sha256'] = value
            self.rejected(result=bad)

    def test_nonzero_exit_live_pid_oom_or_incomplete_stream_rejected(self):
        for container, key, value in (
            ('container_state', 'ExitCode', 7), ('container_state', 'Running', True),
            ('container_state', 'Pid', 123), ('container_state', 'OOMKilled', True),
            ('command_host', 'exit_code', 7), ('command_host', 'job_active_count', 1),
            ('command_host', 'readers_stopped', False), ('command_host', 'stream_reader_eof', [True, False]),
            ('command_host', 'stream_reader_errors', [None, 'OSError']), ('command_host', 'timed_out', True),
            ('command_host', 'stream_cap_exceeded', True), ('command_host', 'host_error', 'OSError'),
            ('command_host', 'evidence_write_error', 'OSError')):
            bad = copy.deepcopy(self.result)
            bad[container][key] = value
            with self.subTest(container=container, key=key):
                self.rejected(result=bad)

    def test_raw_warning_error_and_leak_in_either_stream_override_saved_clean_flag(self):
        for banner in ('ERROR: injected', 'SCRIPT ERROR: injected', 'WARNING: injected', 'ObjectDB instances leaked'):
            with self.subTest(banner=banner):
                self.rejected(stdout=self.stdout + banner + '\n')
                self.rejected(stderr=banner + '\n')

    def test_raw_wrong_uid_source_hash_type_and_value_rejected(self):
        for key, value in (('uid_source', 'uid://b\n'), ('resource_uid', 'uid://b'),
                           ('disk_sha256', 'a' * 64), ('source_sha256', 'a' * 64), ('is_tool', True)):
            bad = copy.deepcopy(self.observation)
            bad['script'][key] = value
            with self.subTest(key=key):
                self.rejected(stdout=raw_output(bad))
        for value in (23, True, 2.2501):
            bad = copy.deepcopy(self.observation)
            bad['instance_nodes'][0]['exports']['move_speed']['value'] = value
            self.rejected(stdout=raw_output(bad))

    def test_stale_raw_report_rejected_even_when_lifecycle_hashes_match_new_bundle(self):
        codec = factory.bundle_codec
        candidate = codec.replace_script(self.bundle, SCRIPT.replace(b'int = 9', b'int = 10'),
            expected_project_revision=self.bundle.project_revision,
            expected_script_sha256=self.bundle.script_sha256, expected_uid_sha256=self.bundle.uid_sha256)
        bad = copy.deepcopy(self.result)
        hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in candidate.files.items()}
        for key in ('input_hashes_before', 'input_hashes_after', 'snapshot_hashes_after'):
            bad[key] = dict(hashes)
        self.rejected(result=bad, bundle=candidate)


if __name__ == '__main__':
    unittest.main(verbosity=2)
