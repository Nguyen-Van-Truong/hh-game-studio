"""Engine-free campaign boundary regressions; synthetic rows are never evidence."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_job import BenchmarkJobError
from studio.tests.replay.benchmark_http_phases import PhaseRecorder
from studio.tests.replay.benchmark_import_observer import ImportObserver


class CampaignResumeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='gt06-campaign-test-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        # Owner verifier has its own raw/native tests. These fixtures isolate
        # campaign routing and artifact binding, and never launch a process.
        verifier = patch.object(campaign, 'verify_owner_captures')
        self.owner_verifier = verifier.start()
        self.addCleanup(verifier.stop)
        self.campaign_id = 'gt06-synthetic-regression'
        self.run_id = self.campaign_id + '.r00.a01'
        self.files = {'fixture.py': campaign.sha(b'fixture')}
        self.digest = campaign.closure(self.files)
        self.campaign_sha = campaign.sha(b'synthetic campaign')
        self.processes = {'host': {'pid': 100, 'process_start': 'windows:1000'},
                          'editor': {'pid': 101, 'process_start': 'windows:1001'}}
        self.put('context.json', {'run_id': self.run_id, 'index': 0, 'attempt': 1,
            'source_files': self.files, 'source_closure_sha256': self.digest,
            'profile_sha256': campaign.profile.PROFILE_SHA256, 'campaign_sha256': self.campaign_sha})
        self.child = {'run_id': self.run_id, 'index': 0, 'completed': True,
            'source_closure_sha256': self.digest, 'profile_sha256': campaign.profile.PROFILE_SHA256,
            'processes': self.processes, 'batches': [{'index': i} for i in range(35)]}
        self.put('child-result.json', self.child)
        for role, directory in (('host', 'host-owner'), ('editor', 'editor-host')):
            pid = self.processes[role]['pid']
            self.put(directory + '/process-start.json', {'pid': pid})
            actual = {'pid': pid, 'exit_code': 0}
            self.put(directory + '/process-exit.json', actual)
            self.put(directory + '/stdout.txt', b'')
            self.put(directory + '/stderr.txt', b'')
            self.put(directory + '/capture.json', {'completed': True,
                'source_unchanged': True, 'wrapper_exit_code': 0, 'actual_process_exit': actual,
                'natural_tree_exit': True, 'formal_acceptance': False,
                'job': {'closed': True, 'zero_observed': True, 'tainted': False},
                'wrapper_process_handle': {'required': True, 'closed': True,
                    'handle_retained': False, 'close_uncertain': False},
                'artifacts': {name: campaign.sha((self.root / directory / name).read_bytes())
                    for name in ('process-start.json', 'process-exit.json', 'stdout.txt', 'stderr.txt')}})
        self.put('import-host/process-start.json', {'pid': 99})
        self.put('import-host/process-exit.json', {'pid': 99, 'exit_code': 0})
        released_probe = {'present': True, 'handle_retained': False, 'close_uncertain': False}
        editor = json.loads((self.root / 'editor-host/capture.json').read_bytes())
        targets = {}
        for role, pid in [('editor', 101), ('import', 99)]:
            targets[role + '_target'] = {'actual_target_exit': {'pid': pid, 'exit_code': 0},
                'start': campaign.reference(self.root, self.root / f'{role}-host/process-start.json'),
                'exit': campaign.reference(self.root, self.root / f'{role}-host/process-exit.json'),
                'missing_reason': None, 'natural_exit_not_inferred': True}
        self.terminal = {'schema_id': 'hh-studio.benchmark-child-terminal-cleanup', 'schema_version': '1.0.0',
            'run_id': self.run_id, 'source_closure_sha256': self.digest,
            'profile_sha256': campaign.profile.PROFILE_SHA256,
            'context': campaign.reference(self.root, self.root / 'context.json'),
            'completed_batches': 35, 'primary_error': None, 'errors': [], 'formal_acceptance': False,
            'host_actual_exit': None, 'supervisor_actual_exit': None,
            'observations': {'heartbeat_alive': False, 'editor_probe': deepcopy(released_probe),
                'producer': {'present': True, 'closed': True, 'failed': True,
                    'observer_probe': deepcopy(released_probe), 'host': {'stopped': True, 'closing': True,
                        'threads_alive': [False, False, False], 'main_socket_closed': True, 'control_socket_closed': True},
                    'journal': {'cache_closed': True, 'index_retained': False,
                        'database_retained': False, 'directory_retained': False}},
                'editor_owner': {'present': True, 'closed': True, 'helper_pid': 102, 'helper_exit_code': 0,
                    'drain_threads_alive': [False, False], 'job': editor['job'],
                    'wrapper_process_handle': editor['wrapper_process_handle']}, **targets}}
        self.put('child-terminal-cleanup.json', self.terminal)
        context = json.loads((self.root / 'context.json').read_bytes())
        recorder = PhaseRecorder(event_capacity=8192, active_capacity=64)
        recorder._pid = 100
        campaign._write_observation(self.root, context, 'http', recorder.snapshot())
        imported = ImportObserver(self.root, self.root, self.root)
        imported._started_ns, imported._closed = 1, True
        campaign._write_observation(self.root, context, 'import', imported.snapshot())
        self.terminal['observations']['import_observer'] = campaign._import_cleanup_state(imported)
        self.put('child-terminal-cleanup.json', self.terminal)
        self.put('commands/journal.guard', b'')
        self.captured = {'schema_id': 'hh-studio.benchmark-owned-run', 'schema_version': '1.0.0',
            'completed': True, 'run_id': self.run_id, 'index': 0,
            'source_closure_sha256': self.digest, 'profile_sha256': campaign.profile.PROFILE_SHA256,
            'processes': deepcopy(self.processes), 'artifacts': {}}
        self.rebind_artifacts()

    def put(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else campaign.encoded(value))

    def rebind_artifacts(self):
        self.captured['artifacts'] = {p.relative_to(self.root).as_posix(): campaign.sha(p.read_bytes())
            for p in self.root.rglob('*') if p.is_file()}

    def verify(self, **overrides):
        arguments = {'campaign_id': self.campaign_id, 'index': 0, 'attempt': 1,
                     'campaign_sha256': self.campaign_sha}
        arguments.update(overrides)
        return campaign.verify_run_capture(self.root, self.captured, self.digest, **arguments)

    def test_matching_capture_including_empty_logs_and_guard_is_resumable(self):
        self.assertEqual(self.verify(), self.child)
        self.owner_verifier.assert_called_once()
        self.assertEqual(campaign.artifact_bytes(self.root / 'host-owner/stderr.txt'), b'')

    def test_owner_verifier_failure_cannot_be_promoted_by_campaign_metadata(self):
        self.owner_verifier.side_effect = BenchmarkJobError('RAW_EXIT_MISMATCH')
        with self.assertRaisesRegex(BenchmarkJobError, 'RAW_EXIT_MISMATCH'):
            self.verify()

    def test_copied_success_cannot_fill_a_different_run_slot(self):
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_SLOT'):
            self.verify(index=1)

    def test_copied_success_cannot_fill_a_new_attempt(self):
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_SLOT'):
            self.verify(attempt=2)

    def test_capture_cannot_cross_campaigns(self):
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_SLOT'):
            self.verify(campaign_id='gt06-other-regression')

    def test_context_is_bound_to_exact_campaign_bytes(self):
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_CONTEXT'):
            self.verify(campaign_sha256=campaign.sha(b'different campaign'))

    def test_rehashed_context_cannot_claim_a_false_source_digest(self):
        context = json.loads((self.root / 'context.json').read_bytes())
        context['source_files']['fixture.py'] = campaign.sha(b'different fixture')
        self.put('context.json', context)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_CONTEXT'):
            self.verify()

    def test_changed_raw_exit_rejected_before_resume(self):
        self.put('editor-host/process-exit.json', {'pid': 101, 'exit_code': 7})
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_ARTIFACT_CHANGED'):
            self.verify()

    def test_required_empty_log_cannot_be_omitted_from_manifest(self):
        del self.captured['artifacts']['editor-host/stderr.txt']
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_MISSING_ARTIFACTS'):
            self.verify()

    def test_terminal_receipt_cannot_be_omitted_from_manifest(self):
        del self.captured['artifacts']['child-terminal-cleanup.json']
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_MISSING_ARTIFACTS'):
            self.verify()

    def test_observation_cannot_be_omitted_from_manifest(self):
        for name in ('http-phases-final.json', 'import-observation.json'):
            with self.subTest(name=name):
                self.rebind_artifacts()
                del self.captured['artifacts'][name]
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_MISSING_ARTIFACTS'):
                    self.verify()

    def test_rehashed_observation_from_other_run_is_rejected(self):
        name = 'http-phases-final.json'
        value = json.loads((self.root / name).read_bytes())
        value['run_id'] += '.other'
        self.put(name, value)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_OBSERVATION_BINDING'):
            self.verify()

    def test_rehashed_observation_from_other_host_is_rejected(self):
        name = 'http-phases-final.json'
        value = json.loads((self.root / name).read_bytes())
        value['observation']['pid'] = 999
        self.put(name, value)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_OBSERVATION_HOST_IDENTITY'):
            self.verify()

    def test_missing_terminal_receipt_is_not_legacy_success(self):
        (self.root / 'child-terminal-cleanup.json').unlink()
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_MISSING_ARTIFACTS'):
            self.verify()

    def test_rehashed_import_observation_cannot_hide_internal_error(self):
        value = json.loads((self.root / 'import-observation.json').read_bytes())
        value['observation']['error_count'] = 1
        self.put('import-observation.json', value)
        self.rebind_artifacts()
        with self.assertRaisesRegex(ValueError, 'INVALID_IMPORT_OBSERVATION'):
            self.verify()

    def test_rehashed_import_cleanup_cannot_hide_retained_handle(self):
        self.terminal['observations']['import_observer']['handle_retained'] = True
        self.put('child-terminal-cleanup.json', self.terminal)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_IMPORT_OBSERVER_HELD'):
            self.verify()

    def test_terminal_bytes_and_current_context_are_bound(self):
        modified = deepcopy(self.terminal)
        modified['source_closure_sha256'] = 'a' * 64
        self.put('child-terminal-cleanup.json', modified)
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_ARTIFACT_CHANGED'):
            self.verify()
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_BINDING'):
            self.verify()
        self.put('child-terminal-cleanup.json', self.terminal)
        context = json.loads((self.root / 'context.json').read_bytes())
        context['additional_marker'] = 'changed bytes'
        self.put('context.json', context)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_BINDING'):
            self.verify()

    def test_rehashed_terminal_cannot_hide_retained_or_uncertain_resources(self):
        for role, key, value in [('editor_probe', 'handle_retained', True),
                                  ('editor_probe', 'close_uncertain', True),
                                  ('editor_probe', 'handle_retained', 0),
                                  ('editor_owner', 'closed', False),
                                  ('producer', 'closed', False)]:
            with self.subTest(role=role, key=key, value=value):
                modified = deepcopy(self.terminal)
                modified['observations'][role][key] = value
                self.put('child-terminal-cleanup.json', modified)
                self.rebind_artifacts()
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_.*HELD'):
                    self.verify()

    def test_terminal_target_and_helper_exits_must_match_their_own_receipts(self):
        for section, field, value in [('editor_owner', 'helper_exit_code', 2),
                                      ('editor_owner', 'helper_exit_code', False),
                                      ('editor_owner', 'helper_pid', 101),
                                      ('editor_target', 'actual_target_exit', {'pid': 102, 'exit_code': 0})]:
            with self.subTest(section=section, field=field):
                modified = deepcopy(self.terminal)
                modified['observations'][section][field] = value
                self.put('child-terminal-cleanup.json', modified)
                self.rebind_artifacts()
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_'):
                    self.verify()

    def test_rehashed_actual_exit_mismatch_cannot_use_stale_terminal_receipt(self):
        self.put('editor-host/process-exit.json', {'pid': 101, 'exit_code': 86})
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_TERMINAL_TARGET_EXIT'):
            self.verify()

    def test_artifact_traversal_rejected(self):
        self.captured['artifacts']['../foreign.json'] = campaign.sha(b'foreign')
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_ARTIFACT_PATH'):
            self.verify()

    def test_child_slot_cannot_disagree_after_rehash(self):
        self.child['index'] = 1
        self.put('child-result.json', self.child)
        self.rebind_artifacts()
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RESUME_CHILD_SLOT'):
            self.verify()


class CampaignOwnershipTests(unittest.TestCase):
    def test_constructor_retained_owner_is_closed_and_primary_error_preserved(self):
        with tempfile.TemporaryDirectory(prefix='gt06-campaign-owner-') as directory, ExitStack() as stack:
            studio = Path(directory) / 'studio'
            studio.mkdir()
            (studio / 'toolchain.lock.json').write_bytes(b'{}')
            (studio / 'fixture.py').write_bytes(b'fixture')
            executable = studio / 'inert-python.exe'
            executable.write_bytes(b'never executable')
            files = {'fixture.py': campaign.sha(b'fixture')}
            root = studio / 'raw'
            retained = SimpleNamespace(closed=False, job=SimpleNamespace(zero_observed=False))
            def close():
                retained.closed = retained.job.zero_observed = True
            retained.close = Mock(side_effect=close)
            original = BenchmarkJobError('BENCHMARK_CLEANUP_HELD', cleanup_owner=retained)
            stack.enter_context(patch.object(campaign, 'STUDIO', studio))
            stack.enter_context(patch.object(campaign, 'sys', SimpleNamespace(executable=str(executable))))
            stack.enter_context(patch.object(campaign, 'load_fixture'))
            stack.enter_context(patch.object(campaign, 'source_files', return_value=files))
            stack.enter_context(patch.object(campaign, 'workstation_profile', return_value={'synthetic': True}))
            launch = stack.enter_context(patch.object(campaign, 'BenchmarkProcess', side_effect=original))
            with self.assertRaises(BenchmarkJobError) as caught:
                campaign.run_campaign('gt06-synthetic-owner', root)
            self.assertIs(caught.exception, original)
            self.assertEqual(launch.call_count, 1)
            self.assertTrue(retained.close.called)
            failure = json.loads((root / 'run-00-attempt-01/parent-failure.json').read_bytes())
            self.assertTrue(failure['owner_closed'])
            self.assertTrue(failure['owned_tree_zero'])
            self.assertFalse(failure['completed'])
            self.assertFalse((root / 'campaign-capture.json').exists())
            self.assertFalse((root / 'run-00-attempt-01/run-capture.json').exists())
            frozen_profile = (root / 'benchmark-profile.json').read_bytes()
            self.assertEqual(campaign.sha(frozen_profile), campaign.profile.PROFILE_SHA256)
            # A closed/zero failed attempt must not silently override a Stop.
            (root / 'run-00-attempt-01/stop-request.json').write_bytes(b'{}')
            with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_STOP_LATCHED'):
                campaign.run_campaign('gt06-synthetic-owner', root)
            launch.assert_called_once()

    def test_parent_cleanup_failure_preserves_primary_artifact_and_held_owner(self):
        with tempfile.TemporaryDirectory(prefix='gt06-campaign-held-') as directory, ExitStack() as stack:
            studio = Path(directory) / 'studio'
            studio.mkdir()
            (studio / 'toolchain.lock.json').write_bytes(b'{}')
            (studio / 'fixture.py').write_bytes(b'fixture')
            executable = studio / 'inert-python.exe'
            executable.write_bytes(b'never executable')
            files = {'fixture.py': campaign.sha(b'fixture')}
            root = studio / 'raw'
            original = BenchmarkJobError('BENCHMARK_WALL_LIMIT')
            retained = SimpleNamespace(closed=False, job=SimpleNamespace(zero_observed=False),
                                       tick=Mock(side_effect=original))
            cleanup = BenchmarkJobError('BENCHMARK_CLEANUP_HELD', cleanup_owner=retained)
            retained.close = Mock(side_effect=cleanup)
            stack.enter_context(patch.object(campaign, 'STUDIO', studio))
            stack.enter_context(patch.object(campaign, 'sys', SimpleNamespace(executable=str(executable))))
            stack.enter_context(patch.object(campaign, 'load_fixture'))
            stack.enter_context(patch.object(campaign, 'source_files', return_value=files))
            stack.enter_context(patch.object(campaign, 'workstation_profile', return_value={'synthetic': True}))
            launch = stack.enter_context(patch.object(campaign, 'BenchmarkProcess', return_value=retained))
            with self.assertRaises(BenchmarkJobError) as caught:
                campaign.run_campaign('gt06-synthetic-held', root)
            self.assertIs(caught.exception, original)
            self.assertIs(original.__cause__, cleanup)
            self.assertIs(original.__cause__.cleanup_owner, retained)
            retained.close.assert_called_once()
            self.assertFalse(retained.closed)
            failure = json.loads((root / 'run-00-attempt-01/parent-failure.json').read_bytes())
            self.assertEqual(failure['code'], 'BENCHMARK_WALL_LIMIT')
            self.assertEqual(failure['cleanup_error'], 'BenchmarkJobError')
            self.assertFalse(failure['completed'])
            self.assertFalse(failure['owner_closed'])
            self.assertFalse(failure['owned_tree_zero'])
            self.assertFalse((root / 'campaign-capture.json').exists())
            self.assertFalse((root / 'run-00-attempt-01/run-capture.json').exists())
            # A second invocation must not launch while the saved failure
            # cannot prove cleanup. The retained owner still needs attention.
            with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_PRIOR_OWNER_HELD'):
                campaign.run_campaign('gt06-synthetic-held', root)
            launch.assert_called_once()
            retained.close.assert_called_once()

    def test_editor_observation_uses_the_assembly_counter_contract(self):
        def count_handles(_handle, pointer):
            pointer._obj.value = 17
            return True
        probe = SimpleNamespace(handle=object(), k=SimpleNamespace(GetProcessHandleCount=Mock(side_effect=count_handles)),
            sample=lambda: {'host_mono_us': 12345, 'rss_bytes': 4096, 'visible_window_handles': ['101']})
        result = campaign.sample_editor(probe)
        self.assertEqual(result['rss_bytes'], {'value': 4096, 'unavailable_reason': None})
        self.assertEqual(result['held_handles'], {'value': 17, 'unavailable_reason': None})
        self.assertEqual(result['host_mono_us'], 12345)
        self.assertEqual(result['visible_window_handles'], ['101'])


class CampaignScreenTests(unittest.TestCase):
    @staticmethod
    def memory():
        def counter(value):
            return {'value': value, 'unavailable_reason': None}
        return {'host': {'rss_bytes': counter(1000), 'held_handles': counter(10),
                         'objects': {'value': None, 'unavailable_reason': 'NOT_APPLICABLE_PYTHON_HOST'},
                         'resources': {'value': None, 'unavailable_reason': 'NOT_APPLICABLE_PYTHON_HOST'}},
                'editor': {'rss_bytes': counter(2000), 'objects': counter(200),
                           'resources': counter(50), 'held_handles': counter(12)}}

    def sample(self, index=5):
        return {'index': index, 'memory': self.memory(), 'max_status_gap_ms': 2000}

    def test_exact_110_percent_rss_is_allowed_but_one_byte_above_fails(self):
        for role in ('host', 'editor'):
            for original in (1000, 1001, 8_000_000_000_000_000):
                with self.subTest(role=role, baseline=original):
                    baseline = self.memory()
                    baseline[role]['rss_bytes']['value'] = original
                    sample = self.sample()
                    limit = original * 110 // 100
                    sample['memory'][role]['rss_bytes']['value'] = limit
                    campaign.screen_sample(sample, baseline)
                    sample['memory'][role]['rss_bytes']['value'] = limit + 1
                    with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RSS_GROWTH'):
                        campaign.screen_sample(sample, baseline)

    def test_each_applicable_retained_counter_cannot_grow_after_warmup(self):
        for role, name in (('host', 'held_handles'), ('editor', 'held_handles'),
                           ('editor', 'objects'), ('editor', 'resources')):
            with self.subTest(role=role, counter=name):
                baseline = self.memory()
                sample = self.sample()
                campaign.screen_sample(sample, baseline)
                sample['memory'][role][name]['value'] -= 1
                campaign.screen_sample(sample, baseline)
                sample['memory'][role][name]['value'] = baseline[role][name]['value'] + 1
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_RETAINED_COUNTER_GROWTH'):
                    campaign.screen_sample(sample, baseline)

    def test_warmup_does_not_apply_growth_or_status_gap_limits_before_baseline(self):
        for index in range(5):
            with self.subTest(index=index):
                sample = self.sample(index)
                sample['max_status_gap_ms'] = 9000
                for role in ('host', 'editor'):
                    for row in sample['memory'][role].values():
                        if row['value'] is not None:
                            row['value'] += 1_000_000
                campaign.screen_sample(sample, None)

    def test_unavailable_applicable_counter_rejected_even_during_warmup(self):
        for index in (0, 4, 5, 34):
            for role, name in (('host', 'rss_bytes'), ('host', 'held_handles'),
                               ('editor', 'rss_bytes'), ('editor', 'held_handles'),
                               ('editor', 'objects'), ('editor', 'resources')):
                with self.subTest(index=index, role=role, counter=name):
                    sample = self.sample(index)
                    sample['memory'][role][name] = {'value': None, 'unavailable_reason': 'observation failed'}
                    with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_COUNTER_UNAVAILABLE'):
                        campaign.screen_sample(sample, self.memory() if index >= 5 else None)

    def test_boolean_is_not_an_observed_counter(self):
        sample = self.sample()
        sample['memory']['editor']['resources']['value'] = True
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_COUNTER_UNAVAILABLE'):
            campaign.screen_sample(sample, self.memory())

    def test_status_gap_boundary_is_inclusive_for_measured_samples(self):
        sample = self.sample()
        campaign.screen_sample(sample, self.memory())
        sample['max_status_gap_ms'] = 2000.001
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_STATUS_GAP'):
            campaign.screen_sample(sample, self.memory())


if __name__ == '__main__':
    unittest.main()
