"""Fault injection for diagnostic cleanup, persistence, and scheduler binding."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
        self.producer.run_batch = Mock(return_value={'host_process': {'pid': os.getpid()},
            'ended_mono_us': 100, 'started_mono_us': 0, 'commands': [None] * 1000,
            'journal_bytes': 1, 'max_status_gap_ms': 1, 'memory_after': {},
            'latency_ms': {'inspect': [1]}, 'cancel': {'receipt_ms': 1}})
        self.producer._observe = lambda: {'counters': {'rss_bytes': {'value': 1}}}
        with patch.object(residency, 'STUDIO', self.root), \
             patch.object(residency, 'source_files', return_value={}), \
             patch.object(residency, 'CommandProducer', return_value=self.producer), \
             patch('builtins.print'):
            with self.assertRaises(FileExistsError):
                residency.child('gt06-test')
        self.assertEqual(self.producer.run_batch.call_count, 35)
        self.producer.close.assert_called_once()
        self.assertFalse((root / 'result.json').exists())
        self.assertEqual(json.loads((root / 'failure.json').read_text())['completed_batches'], 35)

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
