import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from studio.tests.replay import run_o9_quiet_chain as chain


class QuietChainTests(unittest.TestCase):
    def test_full_chain_uses_current_policy_and_dispatches_only_after_pass(self):
        from studio.tests.replay import run_command_residency as residency
        for pass_metrics in (True, False):
            with self.subTest(pass_metrics=pass_metrics), \
                 tempfile.TemporaryDirectory(dir=chain.REVIEWS) as temp, \
                 patch.object(chain, 'o7_readiness', return_value={'ready': True}), \
                 patch.object(chain, '_run_cpu_minute', return_value={}) as cpu, \
                 patch.object(chain.campaign.environment, 'require_infra_budget'), \
                 patch.object(residency, 'run', return_value=0), \
                 patch.object(chain, '_require_residency') as host, \
                 patch.object(chain, '_require_watchdog'), \
                 patch.object(chain.residency_metrics, 'from_run_with_retained_control') as metric, \
                 patch.object(chain.residency_metrics, 'from_run') as legacy, \
                 patch.object(chain, '_dispatch_formal') as dispatch:
                root = Path(temp) / 'gt06-o9-chain-test'
                host.return_value = Path(temp) / 'host'
                metric.return_value = {'status_gap_max_ms': 50, 'metrics_pass': pass_metrics,
                                       'additional_soak_required': False}
                dispatch.side_effect = lambda formal, out, binding: chain.write_new(
                    out / 'formal-dispatch.json', {'formal_id': formal,
                                                 'source_closure_sha256': binding['source_closure_sha256']})
                frozen = chain.dry_run(root.name, 'gt06-o4-formal-22', root)
                if pass_metrics:
                    self.assertEqual(chain.execute(root.name, 'gt06-o4-formal-22', root,
                                                   frozen_plan=frozen), 0)
                    self.assertEqual(cpu.call_count, 2)
                    dispatch.assert_called_once()
                    self.assertEqual(dispatch.call_args.args[2]['source_files'], frozen['source_files'])
                else:
                    with self.assertRaisesRegex(RuntimeError, 'O6_3_METRICS_NOT_PASS'):
                        chain.execute(root.name, 'gt06-o4-formal-22', root, frozen_plan=frozen)
                    dispatch.assert_not_called()
                    self.assertTrue((root / 'stage-04-metrics.json').is_file())
                metric.assert_called_once_with(host.return_value, interleaved_probe=chain.O7_PROBE,
                    seed_directory=chain.O7_SEEDS, reference_soak=chain.O7_REFERENCE_SOAK)
                legacy.assert_not_called()

    def test_scheduled_ids_are_exact_and_bounded(self):
        self.assertEqual(chain.formal_id_for('gt06-o9-chain-f22-r01'), 'gt06-o4-formal-22')
        for invalid in ('gt06-o9-chain-test', 'gt06-o9-chain-f21-r01', 'gt06-o9-chain-f22-../'):
            with self.assertRaises(RuntimeError):
                chain.formal_id_for(invalid)

    def test_stale_o7_blocks_full_chain_but_not_independent_host_diagnostic(self):
        with tempfile.TemporaryDirectory(dir=chain.REVIEWS) as temp, \
             patch.object(chain, 'o7_readiness', return_value={'ready': False, 'code': 'STALE'}):
            root = Path(temp) / 'gt06-o9-chain-test'
            plan = chain.dry_run(root.name, 'gt06-o4-formal-22', root)
            self.assertFalse(plan['executable'])
            host = chain.dry_run(root.name, 'gt06-o4-formal-22', root, host_only=True)
            self.assertTrue(host['executable'])
            self.assertNotIn('FORMAL_DISPATCH', host['stage_order'])

    def test_frozen_plan_drift_never_starts_work(self):
        with tempfile.TemporaryDirectory(dir=chain.REVIEWS) as temp, \
             patch.object(chain, '_run_cpu_minute') as start:
            root = Path(temp) / 'gt06-o9-chain-test'
            frozen = chain.dry_run(root.name, 'gt06-o4-formal-22', root, host_only=True)
            frozen['source_closure_sha256'] = '0' * 64
            with self.assertRaisesRegex(RuntimeError, 'CHAIN_FROZEN_PLAN_CHANGED'):
                chain.execute(root.name, 'gt06-o4-formal-22', root, frozen_plan=frozen)
            start.assert_not_called()
            self.assertFalse(root.exists())

    def test_host_only_scheduler_path_has_no_formal_dispatch_or_duplicate_soak(self):
        from studio.tests.replay import run_command_residency as residency
        with tempfile.TemporaryDirectory(dir=chain.REVIEWS) as temp, \
             patch.object(chain, '_run_cpu_minute', return_value={}), \
             patch.object(chain.campaign.environment, 'require_infra_budget'), \
             patch.object(residency, 'run', return_value=0) as run, \
             patch.object(chain, '_require_residency') as host, \
             patch.object(chain, '_require_watchdog') as watchdog, \
             patch.object(chain, '_dispatch_formal') as formal, \
             patch.object(chain.watchdog_soak, 'run') as extra:
            root = Path(temp) / 'gt06-o9-chain-test'
            raw = Path(temp) / 'host'
            raw.mkdir()
            (raw / 'result.json').write_text('{}')
            host.return_value = raw
            frozen = chain.dry_run(root.name, 'gt06-o4-formal-22', root, host_only=True)
            self.assertEqual(chain.execute(root.name, 'gt06-o4-formal-22', root,
                                          frozen_plan=frozen), 0)
            run.assert_called_once_with('gt06-o9-host-test', minimum_seconds=1800)
            watchdog.assert_called_once()
            formal.assert_not_called()
            extra.assert_not_called()
            self.assertFalse(json.loads((root / 'chain-complete.json').read_bytes())['formal_dispatched'])

    def test_gap_in_extension_batch_blocks_formal(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(chain, 'STUDIO', Path(temp)), \
             patch.object(chain.campaign, 'verify_capture'):
            root = Path(temp) / '.local/reviews/gt06-test'
            (root / 'owner').mkdir(parents=True)
            identity = {'pid': 12, 'process_start': 'test:1'}
            batches = []
            for index in range(36):
                row = {'index': index, 'host_process': identity,
                       'max_status_gap_ms': 1200 if index == 35 else 10}
                batches.append(row)
                (root / f'batch-{index:02d}.json').write_text(json.dumps(
                    {**row, 'run_id': root.name, 'commands': [None] * 1000,
                     'started_mono_us': index * 50_000_000, 'ended_mono_us': (index + 1) * 50_000_000}))
            (root / 'result.json').write_text(json.dumps({'run_id': root.name, 'completed': True,
                'formal_acceptance': False, 'source_closure_sha256': 'a' * 64,
                'source_unchanged': True, 'full_benchmark': False, 'batches': batches,
                'active_elapsed_seconds': 1801}))
            (root / 'owner/capture.json').write_text(json.dumps({
                'schema': 'HH-GT06-BENCHMARK-CAPTURE-2', 'completed': True,
                'actual_process_exit': {'exit_code': 0}, 'natural_tree_exit': True,
                'source_unchanged': True, 'formal_acceptance': False, 'elapsed_seconds': 1802}))
            with self.assertRaisesRegex(RuntimeError, 'HOST_STATUS_GAP_ONE_SECOND'):
                chain._require_residency(root, root.name, {
                    'source_closure_sha256': 'a' * 64, 'source_files': {}})

    def test_dry_run_binds_one_formal_closure_without_starting_work(self):
        with tempfile.TemporaryDirectory(dir=chain.REVIEWS, prefix='o9-test-') as temp:
            value = chain.dry_run('gt06-o9-chain-test', 'gt06-o4-formal-22',
                                  Path(temp) / 'gt06-o9-chain-test')
        self.assertFalse(value['commands_started'])
        self.assertEqual(value['formal_acceptance'], False)
        self.assertEqual(value['source_closure_sha256'], chain.campaign.closure(value['source_files']))
        self.assertIn('tests/replay/run_o9_quiet_chain.py', value['source_files'])

    def test_ids_and_mode_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'FORMAL_ID'):
            chain.validate_ids('gt06-o9-chain-test', 'formal22')
        with self.assertRaisesRegex(RuntimeError, 'CHAIN_MODE'):
            chain.require(False, 'CHAIN_MODE')
        with self.assertRaisesRegex(RuntimeError, 'CHAIN_OUTPUT_PATH'):
            chain.validate_output(Path(tempfile.gettempdir()) / 'gt06-o9-chain-test',
                                  'gt06-o9-chain-test')

    def test_cpu_minute_uses_exclusive_stage_receipts(self):
        binding = {'chain_id': 'gt06-o9-chain-test',
                   'source_closure_sha256': 'a' * 64,
                   'source_files': {}}
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(chain.campaign, 'environment_preflight', return_value={'ok': True}), \
                patch.object(chain.campaign, 'require_environment_preflight'), \
            patch.object(chain.campaign, 'observe_pair_launch') as observe:
            root = Path(temp) / 'out'
            root.mkdir()
            chain._run_cpu_minute(root, binding, 'o4.1-cpu-minute-before')
            chain._run_cpu_minute(root, binding, 'o4.1-cpu-minute-final')
            self.assertTrue((root / 'o4.1-cpu-minute-before').is_dir())
            self.assertTrue((root / 'o4.1-cpu-minute-final').is_dir())
            self.assertEqual(observe.call_count, 2)


if __name__ == '__main__':
    unittest.main()
