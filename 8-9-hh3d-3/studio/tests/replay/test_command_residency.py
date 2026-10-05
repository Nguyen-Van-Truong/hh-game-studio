"""Fault injection for diagnostic cleanup, persistence, and scheduler binding."""
import json
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import run_command_residency as residency
from studio.tests.replay import run_campaign_task as task
from studio.tests.replay.benchmark_commands import CommandError
from studio.tests.replay.benchmark_http_phases import PhaseRecorder


class ResidencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.producer = SimpleNamespace(
            close=Mock(), phase_snapshot=Mock(return_value=PhaseRecorder().snapshot()),
            host=SimpleNamespace(diagnostics=(b'{"kind":"log","payload":{"code":"TRANSPORT_DISCONNECTED"}}',)))

    def finalize(self):
        return residency.finalize(self.root, 'gt06-test', {}, self.producer,
                                  threading.Event(), threading.Thread())

    def fake_batches(self, seconds=50):
        identity = {'pid': os.getpid(), 'process_start': 'test:fixed'}

        def batch(index):
            self.producer.close.assert_not_called()
            return {'index': index, 'run_id': 'gt06-test', 'host_process': identity,
                'ended_mono_us': (index + 1) * seconds * 1_000_000,
                'started_mono_us': index * seconds * 1_000_000,
                'commands': [None] * 1000, 'journal_bytes': index + 1,
                'max_status_gap_ms': 1, 'memory_after': {},
                'latency_ms': {'inspect': [1]}, 'cancel': {'receipt_ms': 1}}

        self.producer.run_batch = Mock(side_effect=batch)
        self.producer._observe = Mock(return_value={
            'process': identity, 'counters': {'rss_bytes': {'value': 1}}})
        self.producer.journal_timing_batch = Mock(return_value={'diagnostic_test': True})
        return batch

    def child_patches(self):
        stack = ExitStack()
        stack.enter_context(patch.object(residency, 'STUDIO', self.root))
        stack.enter_context(patch.object(residency, 'source_files', return_value={}))
        factory = stack.enter_context(patch.object(residency, 'CommandProducer', return_value=self.producer))
        stack.enter_context(patch.object(residency.gc, 'collect'))
        stack.enter_context(patch('builtins.print'))
        return stack, factory

    def test_failed_phase_write_cannot_skip_close_or_other_observation(self):
        (self.root / 'http-phases-final.json').write_text('existing evidence')
        errors = self.finalize()
        self.producer.close.assert_called_once()
        self.assertEqual([stage for stage, _ in errors], ['http_observation'])
        self.assertEqual((self.root / 'http-phases-final.json').read_text(), 'existing evidence')
        self.assertEqual(json.loads((self.root / 'host-diagnostics.json').read_text())['codes'],
                         ['TRANSPORT_DISCONNECTED'])

    def test_held_close_still_captures_phases_and_never_claims_cleanup(self):
        self.producer.close.side_effect = CommandError('CLEANUP_HELD', cleanup_owner=self.producer)
        errors = self.finalize()
        self.assertEqual(errors[0][0], 'producer_close')
        self.assertIs(errors[0][1].cleanup_owner, self.producer)
        self.producer.phase_snapshot.assert_called_once()
        self.assertFalse(json.loads((self.root / 'http-phases-final.json').read_text())['formal_acceptance'])

    def test_diagnostics_export_only_codes_not_arbitrary_payloads(self):
        self.producer.host.diagnostics = (b'{"payload":{"code":"ERROR","secret":"sentinel"}}',
            b'not-json-sentinel', b'[]', b'{"kind":"log","payload":{"code":[]}}')
        self.assertEqual(residency._diagnostic_codes(self.producer), ['INVALID_DIAGNOSTIC_SHAPE'] * 4)

    def test_primary_failure_survives_cleanup_failure(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        primary = CommandError('HOST_DIAGNOSTICS', report={'commands': ['partial']})
        self.producer.run_batch = Mock(side_effect=primary)
        self.producer.close.side_effect = CommandError('CLEANUP_HELD', cleanup_owner=self.producer)
        with patch.object(residency, 'STUDIO', self.root), \
             patch.object(residency, 'source_files', return_value={}), \
             patch.object(residency, 'CommandProducer', return_value=self.producer):
            with self.assertRaises(CommandError) as caught:
                residency.child('gt06-test')
        self.assertIs(caught.exception, primary)
        failure = json.loads((root / 'failure.json').read_text())
        self.assertEqual(failure['code'], 'HOST_DIAGNOSTICS')
        self.assertEqual(failure['partial_batch'], primary.report)
        self.assertEqual(failure['cleanup_errors'][0]['code'], 'CLEANUP_HELD')
        self.assertFalse((root / 'result.json').exists())

    def test_completed_batches_cannot_pass_when_observation_write_fails(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        (root / 'http-phases-final.json').write_text('preserved')
        self.fake_batches()
        stack, _ = self.child_patches()
        with stack:
            with self.assertRaises(FileExistsError):
                residency.child('gt06-test')
        self.assertEqual(self.producer.run_batch.call_count, 35)
        self.producer.close.assert_called_once()
        self.assertFalse((root / 'result.json').exists())
        self.assertEqual(json.loads((root / 'failure.json').read_text())['completed_batches'], 35)

    def test_default_is_exactly_35_batches_without_diagnostic_opt_in(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        self.fake_batches(seconds=1)
        stack, factory = self.child_patches()
        with stack:
            residency.child('gt06-test')
        factory.assert_called_once_with(root / 'commands', 'gt06-test')
        self.assertEqual(self.producer.run_batch.call_args_list, [call(i) for i in range(35)])
        self.assertEqual(len(list(root.glob('batch-*.json'))), 35)
        value = json.loads((root / 'result.json').read_bytes())
        self.assertEqual(value['completed_batches'], 35)
        self.assertEqual(value['diagnostic_extension']['batch_count'], 0)
        self.assertEqual(value['active_elapsed_seconds'], 35)

    def test_floor_extends_active_same_producer_and_preserves_every_raw_batch(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        self.fake_batches(seconds=50)
        stack, factory = self.child_patches()
        with stack:
            residency.child('gt06-test', minimum_seconds=1800)
        factory.assert_called_once_with(root / 'commands', 'gt06-test',
                                        max_batches=residency.MAX_DIAGNOSTIC_BATCHES)
        self.assertEqual(self.producer.run_batch.call_args_list, [call(i) for i in range(36)])
        self.producer.close.assert_called_once()
        value = json.loads((root / 'result.json').read_bytes())
        self.assertEqual(value['completed_batches'], 36)
        self.assertEqual(value['active_elapsed_seconds'], 1800)
        self.assertEqual(value['metric_batch_count'], 35)
        self.assertEqual(value['diagnostic_extension']['batch_count'], 1)
        self.assertFalse(value['formal_acceptance'])
        self.assertEqual(len(list(root.glob('batch-*.json'))), 36)
        self.assertEqual(len(list(root.glob('journal-timing-*.json'))), 36)
        self.assertEqual(len(list(root.glob('summary-*.json'))), 36)
        self.assertNotIn('scope', json.loads((root / 'summary-34.json').read_bytes()))
        self.assertIn('diagnostic extension', json.loads((root / 'summary-35.json').read_bytes())['scope'])
        self.assertEqual(value['batches'][0]['host_process'], value['batches'][-1]['host_process'])

    def test_floor_unmet_at_diagnostic_bound_preserves_prefix_and_cannot_pass(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        self.fake_batches(seconds=1)
        stack, _ = self.child_patches()
        with stack, self.assertRaisesRegex(RuntimeError, 'RESIDENCY_MINIMUM_UNMET'):
            residency.child('gt06-test', minimum_seconds=1800)
        self.assertEqual(self.producer.run_batch.call_count, residency.MAX_DIAGNOSTIC_BATCHES)
        self.producer.close.assert_called_once()
        self.assertFalse((root / 'result.json').exists())
        failure = json.loads((root / 'failure.json').read_bytes())
        self.assertEqual(failure['active_elapsed_seconds'], residency.MAX_DIAGNOSTIC_BATCHES)
        self.assertEqual(failure['completed_batches'], residency.MAX_DIAGNOSTIC_BATCHES)
        self.assertEqual(len(list(root.glob('batch-*.json'))), residency.MAX_DIAGNOSTIC_BATCHES)

    def test_extension_rejects_changed_host_identity_and_keeps_raw_row(self):
        root = self.root / '.local/reviews/gt06-test'
        root.mkdir(parents=True)
        original = self.fake_batches()

        def changed(index):
            value = original(index)
            if index == 35:
                value['host_process'] = {'pid': os.getpid() + 1, 'process_start': 'test:replacement'}
            return value

        self.producer.run_batch.side_effect = changed
        stack, _ = self.child_patches()
        with stack, self.assertRaisesRegex(RuntimeError, 'RESIDENCY_HOST_CHANGED'):
            residency.child('gt06-test', minimum_seconds=1800)
        self.assertTrue((root / 'batch-35.json').is_file())
        self.assertFalse((root / 'result.json').exists())

    def test_cli_forwards_floor_to_child_and_parent(self):
        with patch.object(residency, 'child') as child:
            self.assertEqual(residency.main(['--child', '--run-id', 'gt06-test',
                                             '--minimum-seconds', '1800']), 0)
        child.assert_called_once_with('gt06-test', minimum_seconds=1800)
        with patch.object(residency, 'run', return_value=7) as run:
            self.assertEqual(residency.main(['--run-id', 'gt06-test', '--minimum-seconds', '1800']), 7)
        run.assert_called_once_with('gt06-test', minimum_seconds=1800)

    def test_invalid_floor_rejected_before_child_or_parent_artifacts(self):
        for value in (True, -1, 1.5):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, 'RESIDENCY_MINIMUM_SECONDS'):
                    residency.child('gt06-test', minimum_seconds=value)
                with self.assertRaisesRegex(RuntimeError, 'RESIDENCY_MINIMUM_SECONDS'):
                    residency._run_in_window('gt06-test', minimum_seconds=value)
        self.assertEqual(list(self.root.iterdir()), [])

    def run_mock_owner(self, *, active_elapsed=1800, verify_error=None,
                       real_watchdog=False, observation_only=False, missing_events=False):
        root = self.root / '.local/reviews/gt06-test'
        root.parent.mkdir(parents=True)
        minimum_seconds = 5 if real_watchdog else 1800
        if real_watchdog:
            active_elapsed = minimum_seconds
        capture = {'elapsed_seconds': minimum_seconds + 5, 'actual_process_exit': {'exit_code': 0}}
        owner = SimpleNamespace(job=SimpleNamespace(_handle=123, snapshot=Mock(return_value={})),
                                close=Mock())

        def finish():
            (root / 'owner').mkdir()
            residency.write(root / 'owner/capture.json', capture)
            return capture

        owner.finish = Mock(side_effect=finish)

        def wait(*args, **kwargs):
            if real_watchdog:
                for _ in range(3):
                    kwargs['watchdog'].poll(force=True)
                if missing_events:
                    kwargs['watchdog'].close()
                    (root / 'environment-events.jsonl').unlink()
            residency.write(root / 'result.json', {'completed': True, 'run_id': 'gt06-test',
                'source_closure_sha256': residency.closure({}), 'source_unchanged': True,
                'formal_acceptance': False, 'minimum_seconds': minimum_seconds,
                'active_elapsed_seconds': active_elapsed, 'completed_batches': 36})

        watchdog = SimpleNamespace(stream=SimpleNamespace(closed=False),
            observation_only=False, poll=Mock())

        def close_watchdog():
            watchdog.stream.closed = True

        watchdog.close = Mock(side_effect=close_watchdog)
        watchdog_class = residency.environment.Watchdog

        def make_watchdog(*args, **kwargs):
            nonlocal watchdog
            watchdog = watchdog_class(*args, **kwargs, observation_only=observation_only)
            return watchdog

        with ExitStack() as stack:
            stack.enter_context(patch.object(residency, 'STUDIO', self.root))
            stack.enter_context(patch.object(residency, 'source_files', return_value={}))
            stack.enter_context(patch.object(residency, 'environment_preflight', return_value={}))
            stack.enter_context(patch.object(residency, 'require_environment_preflight'))
            factory = stack.enter_context(patch.object(residency, 'BenchmarkProcess', return_value=owner))
            if real_watchdog:
                from studio.tests.replay.test_benchmark_environment import sample
                stack.enter_context(patch.object(residency, 'environment_snapshot',
                    side_effect=[sample(0), sample(5), sample(10)]))
                stack.enter_context(patch.object(residency.environment, 'running_containers', return_value=[]))
                stack.enter_context(patch.object(residency.environment, 'Watchdog', side_effect=make_watchdog))
            else:
                stack.enter_context(patch.object(residency.environment, 'Watchdog', return_value=watchdog))
            stack.enter_context(patch.object(residency.environment, 'failure_classification', return_value='HARNESS_FAIL'))
            verifier = stack.enter_context(patch.object(residency.environment, 'verify_watchdog',
                side_effect=verify_error,
                **({'wraps': residency.environment.verify_watchdog} if real_watchdog else {})))
            waiter = stack.enter_context(patch.object(residency, 'wait_owned_run', side_effect=wait))
            stack.enter_context(patch('builtins.print'))
            code = residency._run_in_window('gt06-test', minimum_seconds=minimum_seconds)
        return code, root, factory, waiter, verifier, watchdog

    def test_owner_forwards_floor_verifies_default_stream_and_binds_combined_soak(self):
        code, root, factory, waiter, verifier, watchdog = self.run_mock_owner()
        self.assertEqual(code, 0)
        self.assertEqual(factory.call_args.args[0][-2:], ['--minimum-seconds', '1800'])
        waiter.assert_called_once()
        watchdog.poll.assert_not_called()  # no dead-child parent padding
        self.assertEqual(verifier.call_count, 1)
        self.assertFalse(verifier.call_args_list[0].kwargs.get('observation_only', False))
        value = json.loads((root / 'soak-result.json').read_bytes())
        self.assertEqual(value['schema'], residency.SOAK_SCHEMA)
        self.assertEqual(value['active_elapsed_seconds'], 1800)
        self.assertTrue(value['verified_watchdog'])
        self.assertTrue(value['sample_stream_closed'])
        self.assertTrue(value['event_stream_closed'])
        self.assertFalse(value['watchdog_observation_only'])
        self.assertFalse(value['formal_acceptance'])
        self.assertEqual(value['source_closure_sha256'], residency.closure({}))
        self.assertEqual(value['owner_capture_sha256'],
                         residency.hashlib.sha256((root / 'owner/capture.json').read_bytes()).hexdigest())
        self.assertEqual(value['result_sha256'],
                         residency.hashlib.sha256((root / 'result.json').read_bytes()).hexdigest())

    def test_owner_replays_real_watchdog_in_both_modes(self):
        # Synthetic OS samples and child receipt keep this short; Watchdog,
        # durable streams and both replay verifiers execute real code.
        for observer in (False, True):
            with self.subTest(observation_only=observer), \
                 patch.object(self, 'root', self.root / str(observer)):
                code, root, _, _, verifier, watchdog = self.run_mock_owner(
                    real_watchdog=True, observation_only=observer)
                self.assertEqual(code, 0)
                self.assertEqual(verifier.call_count, 2 if observer else 1)
                self.assertEqual((root / 'environment-events.jsonl').exists(), observer)
                self.assertEqual(hasattr(watchdog, 'event_stream'), observer)
                self.assertTrue(watchdog.stream.closed)
                value = json.loads((root / 'soak-result.json').read_bytes())
                self.assertEqual(value['watchdog_observation_only'], observer)
                self.assertFalse(value['formal_acceptance'])

    def test_owner_missing_real_observer_stream_cannot_publish_receipt(self):
        code, root, _, _, _, watchdog = self.run_mock_owner(
            real_watchdog=True, observation_only=True, missing_events=True)
        self.assertEqual(code, 1)
        self.assertTrue(watchdog.stream.closed)
        self.assertFalse((root / 'soak-result.json').exists())
        failure = json.loads((root / 'owner-failure.json').read_bytes())
        self.assertEqual(failure['code'], 'CAMPAIGN_WATCHDOG_EVENTS_MISSING')

    def test_owner_cannot_credit_long_process_lifetime_for_short_active_mix(self):
        code, root, _, _, _, _ = self.run_mock_owner(active_elapsed=1799)
        self.assertEqual(code, 1)
        self.assertFalse((root / 'soak-result.json').exists())
        failure = json.loads((root / 'owner-failure.json').read_bytes())
        self.assertEqual(failure['code'], 'RESIDENCY_MINIMUM_UNMET')

    def test_unverified_watchdog_cannot_write_successful_soak_receipt(self):
        code, root, _, _, _, _ = self.run_mock_owner(verify_error=RuntimeError('bad stream'))
        self.assertEqual(code, 1)
        self.assertFalse((root / 'soak-result.json').exists())
        self.assertTrue((root / 'owner-failure.json').exists())

    def test_scheduler_residency_delegates_only_to_resident_command_runner(self):
        with patch.object(residency, 'run', return_value=7) as run:
            self.assertEqual(task.execute('gt06-test', 'residency', self.root, 'unused'), 7)
        run.assert_called_once_with('gt06-test')
        with self.assertRaisesRegex(ValueError, 'TASK_MODE'):
            task.execute('gt06-test', 'unknown', self.root, 'unused')

    def test_scheduler_parent_child_freeze_identical_source_maps(self):
        maps = []
        for prefix in ('from studio.tests.replay import run_campaign_task; ', ''):
            result = subprocess.run([sys.executable, '-B', '-c',
                'import json; ' + prefix + 'from studio.tests.replay import run_command_residency as r; '
                'print(json.dumps(r.source_files(),sort_keys=True))'],
                cwd=residency.STUDIO.parent, capture_output=True, text=True, timeout=20, check=True)
            self.assertEqual(result.stderr, '')
            maps.append(json.loads(result.stdout))
        self.assertEqual(maps[0], maps[1])
        for name in ('run_campaign_task.py', 'campaign_task.ps1', 'run_command_residency.py'):
            self.assertIn('tests/replay/' + name, maps[0])


if __name__ == '__main__':
    unittest.main()
