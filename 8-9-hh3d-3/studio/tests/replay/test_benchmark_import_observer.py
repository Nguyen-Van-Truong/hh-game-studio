"""Import-observation lifecycle tests; no subprocess, engine or global trace."""
from __future__ import annotations

import ctypes
import copy
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_import_observer as module


class FakeProbe:
    def __init__(self, pid, binary):
        self.pid, self.process_start, self.handle = pid, 'windows:123', object()
        self.close_uncertain = False
        self.exit_code = None
        self.close_count = 0
        self.fail_close = False
        self.fail_sample = False

    def observe(self):
        if self.fail_sample:
            raise OSError('not retained in evidence')
        return {'exited': False, 'user_100ns': 100} if self.exit_code is None else {
            'exited': True, 'exit_code': self.exit_code}

    def close(self):
        self.close_count += 1
        if self.fail_close:
            raise OSError('checked failure; ownership remains')
        self.handle = None


class ImportObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.stage, self.project = root / 'stage', root / 'project'
        self.stage.mkdir()
        self.project.mkdir()
        self.observer = module.ImportObserver(self.stage, self.project, Path(sys.executable))
        self.mock = patch.object(module, '_MetricsProbe', FakeProbe)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def receipt(self, raw=b'{"pid":123}'):
        (self.stage / 'process-start.json').write_bytes(raw)

    def test_partial_receipt_is_retryable_but_valid_receipt_binds_once(self):
        self.receipt(b'{"pid":')
        self.assertTrue(self.observer._poll())
        self.assertTrue(self.observer._receipt_partial)
        self.receipt()
        self.observer._poll()
        probe = self.observer._probe
        self.receipt(b'{"pid":456}')
        self.observer._poll()
        self.assertIs(self.observer._probe, probe)
        self.assertEqual(self.observer.snapshot()['target_identity']['pid'], 123)
        self.observer.close()

    def test_missed_short_process_is_explicit_and_not_reopened(self):
        self.receipt()
        with patch.object(module, '_MetricsProbe', side_effect=OSError) as opened:
            self.observer._poll()
            self.observer._poll()
        self.assertEqual(opened.call_count, 1)
        self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertIn('TARGET_HANDLE_NOT_BOUND_POSSIBLY_EXITED_BETWEEN_POLLS', snapshot['api_gaps'])
        self.assertEqual(snapshot['errors'][0]['phase'], 'target_bind')
        self.assertFalse(snapshot['handle_retained'])

    def test_no_receipt_never_claims_process_or_natural_exit(self):
        self.observer._poll()
        self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertIsNone(snapshot['target_identity'])
        self.assertIsNone(snapshot['target_exit_observed'])
        self.assertEqual(snapshot['natural_target_exit_status'], 'UNKNOWN')
        self.assertIn('NO_LIVE_TARGET_SAMPLE', snapshot['api_gaps'])

    def test_forced_exit_observed_on_close_stays_separate_from_natural_exit(self):
        self.receipt()
        self.observer._poll()
        self.observer._probe.exit_code = 2
        self.observer.close()
        self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertEqual(snapshot['target_exit_observed']['exit_code'], 2)
        self.assertEqual(snapshot['natural_target_exit_status'], 'UNKNOWN')
        self.assertEqual(self.observer._probe.close_count, 1)
        self.assertFalse(snapshot['handle_retained'])

    def test_checked_close_failure_retains_ownership_until_successful_retry(self):
        self.receipt()
        self.observer._poll()
        self.observer._probe.fail_close = True
        with self.assertRaises(OSError):
            self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertFalse(snapshot['closed'])
        self.assertTrue(snapshot['handle_retained'])
        self.observer._probe.fail_close = False
        self.observer.close()
        self.assertFalse(self.observer.snapshot()['handle_retained'])
        self.assertEqual(self.observer.snapshot()['error_count'], 1)

    def test_poll_failure_does_not_escape_worker_and_close_still_releases(self):
        self.receipt()
        self.observer._poll()
        self.observer._probe.fail_sample = True
        self.observer._run()
        self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertEqual([row['phase'] for row in snapshot['errors']], ['poll', 'final_observation'])
        self.assertFalse(snapshot['handle_retained'])

    def test_uncertain_handle_is_never_sampled_during_cleanup(self):
        self.receipt()
        self.observer._poll()
        probe = self.observer._probe
        probe.close_uncertain = True
        with patch.object(probe, 'observe', side_effect=AssertionError('unsafe query')) as observed:
            with patch.object(probe, 'close', side_effect=module.ImportObserverError('uncertain')):
                with self.assertRaises(module.ImportObserverError):
                    self.observer.close()
        observed.assert_not_called()
        self.assertTrue(self.observer.snapshot()['handle_close_uncertain'])
        probe.close_uncertain = False  # Inert double only; real uncertain handles cannot be rearmed.
        self.observer.close()

    def test_bound_and_snapshot_are_independent_of_caller_mutation(self):
        for _ in range(module.MAX_SAMPLES):
            self.assertTrue(self.observer._poll())
        self.assertFalse(self.observer._poll())
        snapshot = self.observer.snapshot()
        self.assertEqual(snapshot['sample_count'], 256)
        self.assertIn('SAMPLE_CAP_REACHED', snapshot['api_gaps'])
        snapshot['samples'][0]['milestones_observed'].append('invented')
        self.assertEqual(self.observer.snapshot()['samples'][0]['milestones_observed'], [])
        self.observer.close()

    def test_polling_thread_is_drained_and_lifecycle_cannot_restart(self):
        before = {thread.ident for thread in threading.enumerate()}
        self.observer.start()
        self.observer.close()
        snapshot = self.observer.snapshot()
        self.assertTrue(snapshot['closed'])
        self.assertFalse(snapshot['thread_alive'])
        self.assertEqual({thread.ident for thread in threading.enumerate()}, before)
        with self.assertRaises(module.ImportObserverError):
            self.observer.start()

    def test_file_byte_and_milestone_observations_are_literal(self):
        (self.stage / 'stdout.txt').write_bytes(b'abc')
        (self.project / '.godot').mkdir()
        (self.project / '.godot/.gdignore').write_bytes(b'\n')
        self.observer._poll()
        self.observer.close()
        sample = self.observer.snapshot()['samples'][0]
        self.assertEqual(sample['stdout_file_bytes'], 3)
        self.assertIsNone(sample['stderr_file_bytes'])
        self.assertEqual(sample['milestones_observed'], ['.godot/.gdignore'])


class ActualPythonMetricsTest(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows retained-handle ABI')
    def test_current_python_cpu_io_and_memory_abi_releases_handle(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], w.HANDLE
        kernel.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        kernel.GetProcessHandleCount.restype = w.BOOL
        def handles():
            value = w.DWORD()
            self.assertTrue(kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(value)))
            return value.value
        before = handles()
        probe = module._MetricsProbe(os.getpid(), Path(sys.executable))
        try:
            row = probe.observe()
            self.assertEqual(ctypes.sizeof(probe.IO), 48)
            self.assertFalse(row['exited'])
            self.assertGreater(row['working_set_bytes'], 0)
            self.assertGreater(row['private_commit_bytes'], 0)
            self.assertGreaterEqual(row['kernel_100ns'], 0)
            self.assertEqual(len(row['io']), 6)
        finally:
            probe.close()
        self.assertIsNone(probe.handle)
        self.assertFalse(module.HELD_PROBES)
        self.assertEqual(handles(), before)


class ImportSnapshotValidatorTests(unittest.TestCase):
    @staticmethod
    def absent():
        observer = module.ImportObserver(Path('unused'), Path('unused'), Path(sys.executable))
        observer._started_ns = 1
        observer._closed = True
        return observer.snapshot()

    @classmethod
    def complete(cls):
        value = cls.absent()
        value['target_identity'] = {'pid': 123, 'receipt_observed_ns': 2,
                                    'process_start': 'windows:123456', 'handle_bound_ns': 3}
        value['target_exit_observed'] = {'pid': 123, 'process_start': 'windows:123456',
                                         'exit_code': 2, 'observed_ns': 5}
        live = {'exited': False, 'user_100ns': 10, 'kernel_100ns': 5, 'page_faults': 2,
                'working_set_bytes': 4096, 'private_commit_bytes': 8192, 'priority_class': 32,
                'io': {name: 0 for name in ('read_ops', 'write_ops', 'other_ops',
                                            'read_bytes', 'write_bytes', 'other_bytes')}}
        value['samples'] = [
            {'mono_ns': 4, 'stdout_file_bytes': 0, 'stderr_file_bytes': None,
             'milestones_observed': ['.godot/.gdignore'], 'target': live},
            {'mono_ns': 5, 'stdout_file_bytes': 75, 'stderr_file_bytes': 0,
             'milestones_observed': list(module.MILESTONES), 'target': {'exited': True, 'exit_code': 2}},
        ]
        value['sample_count'] = 2
        value['api_gaps'] = []
        return value

    def test_closed_empty_short_target_snapshot_is_valid_with_explicit_gaps(self):
        value = self.absent()
        before = copy.deepcopy(value)
        self.assertIs(module.validate_import_snapshot(value), value)
        self.assertEqual(value, before)
        self.assertIn('TARGET_START_RECEIPT_NOT_OBSERVED', value['api_gaps'])
        self.assertIn('NO_LIVE_TARGET_SAMPLE', value['api_gaps'])

    def test_closed_unbound_target_gap_does_not_become_performance_failure(self):
        value = self.absent()
        value['target_identity'] = {'pid': 123, 'receipt_observed_ns': 2,
                                    'process_start': None, 'handle_bound_ns': None}
        value['api_gaps'] = ['TARGET_HANDLE_NOT_BOUND_POSSIBLY_EXITED_BETWEEN_POLLS', 'NO_LIVE_TARGET_SAMPLE']
        module.validate_import_snapshot(value)

    def test_forced_exit_is_valid_observation_and_never_promoted_to_natural(self):
        value = self.complete()
        module.validate_import_snapshot(value)
        self.assertEqual(value['natural_target_exit_status'], 'UNKNOWN')
        self.assertEqual(value['target_exit_observed']['exit_code'], 2)

    def test_target_already_exited_on_first_sample_preserves_visible_gap(self):
        value = self.complete()
        value['samples'] = value['samples'][1:]
        value['sample_count'] = 1
        value['api_gaps'] = ['NO_LIVE_TARGET_SAMPLE']
        module.validate_import_snapshot(value)

    def test_sample_cap_is_visible_and_bounded_not_a_performance_verdict(self):
        value = self.absent()
        value['samples'] = [{'mono_ns': n + 1, 'stdout_file_bytes': None, 'stderr_file_bytes': None,
                              'milestones_observed': [], 'target': None} for n in range(256)]
        value['sample_count'] = 256
        value['api_gaps'].append('SAMPLE_CAP_REACHED')
        module.validate_import_snapshot(value)

    def test_malformed_snapshots_all_raise_the_fixed_error(self):
        mutations = {
            'extra_key': lambda x: x.update(extra=True),
            'missing_key': lambda x: x.pop('clock'),
            'internal_error': lambda x: x.update(error_count=1, errors=[{'phase': 'poll'}]),
            'boolean_error_count': lambda x: x.update(error_count=False),
            'held_global_probe': lambda x: x.update(global_held_probe_count=1),
            'open': lambda x: x.update(closed=False),
            'thread': lambda x: x.update(thread_alive=True),
            'retained': lambda x: x.update(handle_retained=True),
            'uncertain': lambda x: x.update(handle_close_uncertain=True),
            'release_claim_false': lambda x: x.update(probe_handles_released=False),
            'interval': lambda x: x.update(sample_interval_seconds=.2),
            'cap': lambda x: x.update(sample_limit=257),
            'count': lambda x: x.update(sample_count=1),
            'overflow': lambda x: x.update(sample_count=257, samples=x['samples'] * 129),
            'row_extra_key': lambda x: x['samples'][0].update(extra=0),
            'negative_time': lambda x: x['samples'][0].update(mono_ns=-1),
            'time_before_bound': lambda x: x['samples'][0].update(mono_ns=2),
            'missing_bound_metrics': lambda x: x['samples'][0].update(target=None),
            'bad_pid_type': lambda x: x['target_identity'].update(pid=True),
            'bad_process_start': lambda x: x['target_identity'].update(process_start='windows:0'),
            'bound_before_receipt': lambda x: x['target_identity'].update(handle_bound_ns=1),
            'different_exit_pid': lambda x: x['target_exit_observed'].update(pid=321),
            'different_exit_code': lambda x: x['samples'][1]['target'].update(exit_code=0),
            'excess_log': lambda x: x['samples'][0].update(stdout_file_bytes=262145),
            'bad_milestone': lambda x: x['samples'][0].update(milestones_observed=['unknown']),
            'duplicate_milestone': lambda x: x['samples'][0].update(milestones_observed=['.godot/.gdignore'] * 2),
            'bad_target_enum': lambda x: x['samples'][0]['target'].update(exited=0),
            'bad_priority': lambda x: x['samples'][0]['target'].update(priority_class=0),
            'nan_cpu': lambda x: x['samples'][0]['target'].update(user_100ns=float('nan')),
            'negative_io': lambda x: x['samples'][0]['target']['io'].update(read_bytes=-1),
            'bool_io': lambda x: x['samples'][0]['target']['io'].update(read_ops=True),
            'unknown_gap': lambda x: x.update(api_gaps=['UNEXPLAINED']),
            'contradictory_gap': lambda x: x.update(api_gaps=['NO_LIVE_TARGET_SAMPLE']),
            'false_cap_gap': lambda x: x.update(api_gaps=['SAMPLE_CAP_REACHED']),
            'natural_claim': lambda x: x.update(natural_target_exit_status='PASS'),
            'new_limitation': lambda x: x['limitations'].append('unbound text'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value = self.complete()
                mutate(value)
                with self.assertRaisesRegex(ValueError, '^INVALID_IMPORT_OBSERVATION$'):
                    module.validate_import_snapshot(value)
        for value in (None, [], True, {}, 'unknown'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, '^INVALID_IMPORT_OBSERVATION$'):
                    module.validate_import_snapshot(value)


if __name__ == '__main__':
    unittest.main()
