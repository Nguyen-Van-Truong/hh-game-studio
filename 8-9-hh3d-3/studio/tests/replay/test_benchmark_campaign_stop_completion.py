"""Deterministic Stop completion races; no native process or engine.
These tests isolate coordinator routing with inert owner/assembly doubles;
synthetic artifacts never substitute for actual exit/ownership evidence.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
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


STOP_CODE = r'(?:BENCHMARK_STOPPED|CAMPAIGN_STOP_LATCHED)'


def publish_stop(output, binding):
    campaign.publish(output / 'stop-request.json', {
        'schema': 'HH-GT06-CAMPAIGN-STOP-1',
        'run_id': binding['run_id'],
        'source_closure_sha256': binding['source_closure_sha256'],
        'campaign_sha256': binding['campaign_sha256'],
        'reason': 'OPERATOR_STOP',
    })


class CampaignStopCompletionTests(unittest.TestCase):
    def test_late_stop_on_prior_run_interrupts_current_run_polling(self):
        with tempfile.TemporaryDirectory(prefix='gt06-stop-prior-run-') as directory:
            root = Path(directory)
            prior = root / 'run-00-attempt-01'
            active = root / 'run-01-attempt-01'
            prior.mkdir()
            active.mkdir()
            binding = {'run_id': 'gt06-stop-completion.r01.a01',
                'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
            def tick(*, stop=False):
                self.assertFalse(stop)
                publish_stop(prior, {**binding, 'run_id': 'gt06-stop-completion.r00.a01'})
                return None
            owner = SimpleNamespace(tick=Mock(side_effect=tick))
            with patch.object(campaign.time, 'sleep'):
                with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_STOP_LATCHED'):
                    campaign.wait_owned_run(owner, active, **binding,
                        check_campaign_stop=lambda: campaign.require_campaign_running(root, active=active))
            owner.tick.assert_called_once_with(stop=False)

    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory(prefix='gt06-stop-completion-') as directory, ExitStack() as stack:
            studio = Path(directory) / 'studio'
            studio.mkdir()
            (studio / 'toolchain.lock.json').write_bytes(b'{}')
            (studio / 'fixture.py').write_bytes(b'inert fixture')
            executable = studio / 'inert-python.exe'
            executable.write_bytes(b'never executable')
            files = {'fixture.py': campaign.sha(b'inert fixture')}
            stack.enter_context(patch.object(campaign, 'STUDIO', studio))
            stack.enter_context(patch.object(campaign, 'sys', SimpleNamespace(executable=str(executable))))
            stack.enter_context(patch.object(campaign, 'load_fixture'))
            stack.enter_context(patch.object(campaign, 'source_files', return_value=files))
            stack.enter_context(patch.object(campaign, 'workstation_profile', return_value={'synthetic': True}))
            # Watchdog policy has its own tests. This fixture isolates Stop
            # publication during assembly with an inert, already exited Job.
            stack.enter_context(patch.object(campaign.environment, 'Watchdog'))
            stack.enter_context(patch.object(campaign.environment, 'verify_watchdog'))
            stack.enter_context(patch.object(campaign, 'environment_preflight', return_value={
                'schema_id': 'hh-studio.benchmark-environment-preflight', 'schema_version': '1.2.0',
                'pass': True, 'available_memory_bytes': 8 * 1024**3,
                'commit_total_bytes': 80, 'commit_limit_bytes': 100, 'heavy_processes': [], 'required_heavy_processes_closed': False, 'foreign_engines': []}))
            # Every process launch is intercepted, including accidental next-run
            # launch. Existing owner/assembly tests verify their own contracts.
            from studio.tests.replay.test_launch_observation import collect_synthetic
            observe = stack.enter_context(patch.object(campaign, 'observe_pair_launch', side_effect=collect_synthetic))
            launch = stack.enter_context(patch.object(campaign, 'BenchmarkProcess'))
            yield SimpleNamespace(root=studio / 'raw', campaign_id='gt06-stop-completion',
                                  stack=stack, launch=launch, observe=observe)

    def test_stop_published_by_terminal_tick_is_not_lost(self):
        with tempfile.TemporaryDirectory(prefix='gt06-stop-terminal-tick-') as directory:
            output = Path(directory)
            binding = {'run_id': 'gt06-stop-completion.r00.a01',
                'source_closure_sha256': 'a' * 64, 'campaign_sha256': 'b' * 64}
            calls = []
            def tick(*, stop=False):
                calls.append(stop)
                if stop:
                    raise BenchmarkJobError('BENCHMARK_STOPPED')
                if len(calls) > 1:
                    raise AssertionError('terminal tick must not enter a polling loop')
                # Deterministically place the request after the pre-poll check
                # but before that same poll reports exit zero. No sleep/race.
                publish_stop(output, binding)
                return 0
            retained = SimpleNamespace(tick=Mock(side_effect=tick))
            with patch.object(campaign.time, 'sleep', side_effect=AssertionError('terminal path must not sleep')):
                with self.assertRaisesRegex(BenchmarkJobError, STOP_CODE):
                    campaign.wait_owned_run(retained, output, **binding)
            self.assertTrue((output / 'stop-request.json').is_file())
            self.assertLessEqual(retained.tick.call_count, 2)

    def test_stop_during_assembly_prevents_capture_and_next_launch(self):
        with self.fixture() as fixture:
            processes = {'host': {'pid': 100, 'process_start': 'windows:1000'},
                         'editor': {'pid': 101, 'process_start': 'windows:1001'}}
            retained = SimpleNamespace(closed=True, job=SimpleNamespace(zero_observed=True))
            retained.tick = Mock(return_value=0)
            retained.close = Mock(return_value=True)
            retained.finish = Mock(return_value={
                'elapsed_seconds': 5.0,
                'actual_process_exit': {'pid': 100, 'exit_code': 0},
                'job': {'zero_observed': True}})
            def launch(*_args, **kwargs):
                if fixture.launch.call_count != 1:
                    raise AssertionError('Stop during assembly must prevent the next run')
                output = kwargs['cwd']
                binding = json.loads((output / 'context.json').read_bytes())
                campaign.write(output / 'child-result.json', {
                    'processes': processes, 'batches': [],
                    'cleanup': {'editor_exit_code': 0, 'editor_owned_tree_zero': True, 'held_handles': 0}})
                self.assertEqual(binding['index'], 0)
                return retained
            fixture.launch.side_effect = launch
            # A route-only assembly double: no fake rows are passed to the real
            # assembly verifier or promoted into a benchmark dataset.
            def assemble(output, _manifest):
                binding = json.loads((output / 'context.json').read_bytes())
                publish_stop(output, binding)
                return SimpleNamespace(value={'run': {'synthetic': True}})
            assembled = fixture.stack.enter_context(patch.object(campaign, 'assemble_run', side_effect=assemble))
            fixture.stack.enter_context(patch.object(campaign, 'verify_run_capture'))
            fixture.stack.enter_context(patch.object(campaign, 'reference', side_effect=lambda root, path: {
                'file': path.relative_to(root).as_posix(), 'sha256': 'c' * 64, 'size_bytes': 1}))
            with self.assertRaisesRegex(BenchmarkJobError, STOP_CODE):
                campaign.run_campaign(fixture.campaign_id, fixture.root)
            assembled.assert_called_once()
            fixture.launch.assert_called_once()
            retained.close.assert_called()
            output = fixture.root / 'run-00-attempt-01'
            self.assertFalse((output / 'run-capture.json').exists())
            self.assertFalse((fixture.root / 'run-01-attempt-01').exists())
            self.assertFalse((fixture.root / 'campaign-capture.json').exists())
            failure = json.loads((output / 'parent-failure.json').read_bytes())
            self.assertFalse(failure['completed'])
            self.assertTrue(failure['owner_closed'])
            self.assertTrue(failure['owned_tree_zero'])

    def test_stop_on_completed_attempt_blocks_resume_before_any_launch(self):
        with self.fixture() as fixture:
            # Let production code create its own exact freeze/context instead
            # of duplicating the campaign manifest in this routing test.
            fixture.launch.side_effect = BenchmarkJobError('SYNTHETIC_SEED_ONLY')
            with self.assertRaisesRegex(BenchmarkJobError, 'SYNTHETIC_SEED_ONLY'):
                campaign.run_campaign(fixture.campaign_id, fixture.root)
            output = fixture.root / 'run-00-attempt-01'
            binding = json.loads((output / 'context.json').read_bytes())
            campaign.write(output / 'run-capture.json', {
                'index': 0, 'run_id': binding['run_id'], 'completed': True,
                'processes': {'host': {'pid': 100, 'process_start': 'windows:1000'},
                              'editor': {'pid': 101, 'process_start': 'windows:1001'}}})
            publish_stop(output, binding)
            fixture.stack.enter_context(patch.object(campaign, 'verify_run_capture'))
            fixture.launch.reset_mock()
            fixture.launch.side_effect = AssertionError('completed-attempt Stop must block resume')
            with self.assertRaisesRegex(BenchmarkJobError, STOP_CODE):
                campaign.run_campaign(fixture.campaign_id, fixture.root)
            fixture.launch.assert_not_called()
            self.assertFalse((fixture.root / 'run-01-attempt-01').exists())
            self.assertFalse((fixture.root / 'campaign-capture.json').exists())

    def test_completed_pair_measurements_block_next_launch_on_fail_or_gap(self):
        from studio.tests.replay.test_benchmark_profile import synthetic_dataset
        for status in ('PASS', 'FAIL', 'GAP'):
            with self.subTest(status=status), self.fixture() as fixture:
                run = synthetic_dataset()['runs'][0]
                if status == 'FAIL':
                    run['samples'][34]['memory']['host']['private_commit_bytes']['value'] = 1200
                elif status == 'GAP':
                    run['samples'][10]['memory']['editor']['resources'] = {
                        'value': None, 'unavailable_reason': 'unavailable'}
                retained = SimpleNamespace(closed=True, job=SimpleNamespace(zero_observed=True))
                retained.tick = Mock(return_value=0)
                retained.close = Mock(return_value=True)
                retained.finish = Mock(return_value={
                    'elapsed_seconds': 5.0,
                    'actual_process_exit': {'pid': run['processes']['host']['pid'], 'exit_code': 0},
                    'job': {'zero_observed': True}})

                def launch(*_args, **kwargs):
                    if fixture.launch.call_count > 1:
                        raise BenchmarkJobError('SYNTHETIC_SECOND_LAUNCH')
                    output = kwargs['cwd']
                    binding = json.loads((output / 'context.json').read_bytes())
                    run['run_id'] = binding['run_id']
                    campaign.write(output / 'child-result.json', {
                        'processes': run['processes'], 'batches': [],
                        'cleanup': {'editor_exit_code': 0, 'editor_owned_tree_zero': True,
                                    'held_handles': 0}})
                    return retained

                fixture.launch.side_effect = launch
                # Native assembly/ownership is inert here; the real O1 evaluator
                # receives all 35 synthetic samples, including the failing row.
                fixture.stack.enter_context(patch.object(campaign, 'assemble_run',
                    return_value=SimpleNamespace(value={'run': run})))
                fixture.stack.enter_context(patch.object(campaign, 'verify_run_capture'))
                fixture.stack.enter_context(patch.object(campaign, 'reference',
                    side_effect=lambda root, path: {
                        'file': path.relative_to(root).as_posix(), 'sha256': 'c' * 64,
                        'size_bytes': 1}))
                expected = 'SYNTHETIC_SECOND_LAUNCH' if status == 'PASS' else 'CAMPAIGN_RUN_MEASUREMENTS_NOT_PASS'
                with self.assertRaisesRegex(BenchmarkJobError, expected):
                    campaign.run_campaign(fixture.campaign_id, fixture.root)
                output = fixture.root / 'run-00-attempt-01'
                self.assertTrue((output / 'run-capture.json').is_file())
                summary = json.loads((output / 'measurement-summary.json').read_bytes())
                self.assertEqual(summary['status'], status)
                self.assertFalse(summary['formal_acceptance'])
                capture = json.loads((output / 'run-capture.json').read_bytes())
                self.assertEqual(capture['artifacts']['measurement-summary.json'],
                                 campaign.sha((output / 'measurement-summary.json').read_bytes()))
                self.assertEqual(fixture.launch.call_count, 2 if status == 'PASS' else 1)
                self.assertEqual(fixture.observe.call_count, fixture.launch.call_count)
                observed_runs = [call.args[1]['run_id'] for call in fixture.observe.call_args_list]
                self.assertEqual(len(set(observed_runs)), len(observed_runs))
                if status != 'PASS':
                    self.assertFalse((fixture.root / 'run-01-attempt-01').exists())
                    failure = json.loads((output / 'parent-failure.json').read_bytes())
                    self.assertEqual(failure['classification'], 'PRODUCT_FAIL')
                    self.assertTrue(failure['owned_tree_zero'])
                self.assertFalse((fixture.root / 'campaign-capture.json').exists())


if __name__ == '__main__':
    unittest.main()
