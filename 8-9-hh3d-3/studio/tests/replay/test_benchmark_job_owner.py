"""Inert owner regressions; no subprocess, engine, or native handle call.

These synthetic artifacts are never acceptance evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_job as owner


class InertHandle(int):
    """Mirror CPython's close flag, without ever touching a real OS handle."""
    def __new__(cls, value=987654321):
        instance = int.__new__(cls, value)
        instance.closed = False
        instance.automatic_close_calls = []
        return instance

    def Close(self):
        if not self.closed:
            self.closed = True
            self.automatic_close_calls.append(int(self))


def inert_process():
    return SimpleNamespace(_handle=InertHandle(), returncode=0,
        stdin=None, stdout=None, stderr=None,
        poll=Mock(return_value=0), wait=Mock(return_value=0))


def inert_job():
    job = SimpleNamespace(closed=True, zero_observed=True, tainted=False)
    job.close = Mock()
    job.snapshot = lambda: {'closed': True, 'zero_observed': True,
        'handle_retained': False, 'tainted': False}
    return job


class OwnerCloseTests(unittest.TestCase):
    def setUp(self):
        registry = patch.object(owner, 'HELD_OWNERS', [])
        registry.start()
        self.addCleanup(registry.stop)
        directory = tempfile.TemporaryDirectory(prefix='gt06-inert-owner-')
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)

    def make_owner(self):
        value = owner.BenchmarkProcess.__new__(owner.BenchmarkProcess)
        value.process, value.job = inert_process(), inert_job()
        value.closed = value.released = False
        value._finishing = True
        value._failure_code = None
        value._report_number = 0
        value._cleanup_lock = threading.RLock()
        value._process_handle = None
        value._process_handle_closed = False
        value._process_handle_close_uncertain = False
        value.output = self.output
        value.threads, value.errors = [], []
        owner.HELD_OWNERS.append(value)
        return value

    def test_success_closes_native_handle_once_and_proves_it_in_cleanup(self):
        value = self.make_owner()
        handle = value.process._handle
        with patch.object(owner, 'close_process_handle_native', return_value=True) as native:
            self.assertTrue(value.close())
            self.assertTrue(value.close())
        native.assert_called_once_with(int(handle))
        self.assertIs(value._process_handle, handle)
        self.assertTrue(handle.closed)
        self.assertEqual(value.process_handle_snapshot(), {
            'required': True, 'closed': True,
            'close_uncertain': False, 'handle_retained': False})
        proof = json.loads((self.output / 'cleanup-001.json').read_bytes())
        self.assertEqual(proof['wrapper_process_handle'], value.process_handle_snapshot())
        self.assertFalse(proof['completed'])
        self.assertNotIn(value, owner.HELD_OWNERS)
        # Simulate Handle.__del__; it must not issue a second close.
        handle.Close()
        self.assertEqual(handle.automatic_close_calls, [])

    def test_checked_false_retains_exact_handle_until_successful_retry(self):
        value = self.make_owner()
        handle = value.process._handle
        with patch.object(owner, 'close_process_handle_native', side_effect=[False, True]) as native:
            with self.assertRaisesRegex(owner.BenchmarkJobError, 'BENCHMARK_CLEANUP_HELD') as caught:
                value.close()
            self.assertIs(caught.exception.cleanup_owner, value)
            self.assertEqual(caught.exception.__cause__.code, 'BENCHMARK_PROCESS_HANDLE_CLOSE')
            self.assertIs(value._process_handle, handle)
            self.assertIs(value.process._handle, handle)
            self.assertFalse(handle.closed)
            self.assertFalse(value.closed)
            self.assertEqual(value.process_handle_snapshot(), {
                'required': True, 'closed': False,
                'close_uncertain': False, 'handle_retained': True})
            self.assertIn(value, owner.HELD_OWNERS)
            self.assertFalse(list(self.output.glob('cleanup-*.json')))
            self.assertTrue(value.close())
            self.assertEqual([call.args for call in native.call_args_list], [(int(handle),), (int(handle),)])
        self.assertNotIn(value, owner.HELD_OWNERS)
        # Cleaning up a failed owner must not turn that owner into a successful run.
        with self.assertRaisesRegex(owner.BenchmarkJobError, 'BENCHMARK_PROCESS_HANDLE_CLOSE'):
            value.finish()

    def test_unknown_native_result_blocks_retry_and_automatic_destructor_close(self):
        value = self.make_owner()
        handle = value.process._handle
        interrupted = KeyboardInterrupt('native return was not observed')
        with patch.object(owner, 'close_process_handle_native', side_effect=interrupted) as native:
            with self.assertRaises(owner.BenchmarkJobError) as caught:
                value.close()
            self.assertIs(caught.exception.cleanup_owner, value)
            self.assertIs(caught.exception.__cause__, interrupted)
            waits = value.process.wait.call_count
            with self.assertRaises(owner.BenchmarkJobError) as second:
                value.close()
            self.assertEqual(second.exception.__cause__.code, 'BENCHMARK_PROCESS_HANDLE_CLOSE_UNCERTAIN')
            self.assertEqual(value.process.wait.call_count, waits)
            native.assert_called_once_with(int(handle))
        self.assertIs(value._process_handle, handle)
        self.assertFalse(value.closed)
        self.assertIn(value, owner.HELD_OWNERS)
        self.assertEqual(value.process_handle_snapshot(), {
            'required': True, 'closed': False,
            'close_uncertain': True, 'handle_retained': True})
        handle.Close()
        self.assertEqual(handle.automatic_close_calls, [])
        self.assertFalse(list(self.output.glob('cleanup-*.json')))

    def test_cleanup_evidence_failure_after_native_close_does_not_double_close(self):
        value = self.make_owner()
        actual_write = owner.write
        attempts = []
        def write_after_first_failure(path, body):
            attempts.append(path.name)
            if len(attempts) == 1:
                raise OSError('synthetic write failure before creating file')
            actual_write(path, body)
        with patch.object(owner, 'close_process_handle_native', return_value=True) as native, \
             patch.object(owner, 'write', side_effect=write_after_first_failure):
            with self.assertRaises(owner.BenchmarkJobError) as caught:
                value.close()
            self.assertIs(caught.exception.cleanup_owner, value)
            self.assertFalse(value.closed)
            self.assertTrue(value.process_handle_snapshot()['closed'])
            self.assertIn(value, owner.HELD_OWNERS)
            self.assertTrue(value.close())
            native.assert_called_once()
        self.assertEqual(attempts, ['cleanup-001.json', 'cleanup-002.json'])
        self.assertNotIn(value, owner.HELD_OWNERS)

    def test_changed_handle_after_failed_close_is_never_closed_by_number(self):
        value = self.make_owner()
        original = value.process._handle
        with patch.object(owner, 'close_process_handle_native', return_value=False) as native:
            with self.assertRaises(owner.BenchmarkJobError):
                value.close()
            value.process._handle = InertHandle(int(original))
            with self.assertRaises(owner.BenchmarkJobError) as caught:
                value.close()
            self.assertEqual(caught.exception.__cause__.code, 'BENCHMARK_PROCESS_HANDLE_CHANGED')
            native.assert_called_once_with(int(original))
        self.assertIs(value._process_handle, original)
        self.assertIn(value, owner.HELD_OWNERS)


class ConstructorProofTests(unittest.TestCase):
    def setUp(self):
        registry = patch.object(owner, 'HELD_OWNERS', [])
        registry.start()
        self.addCleanup(registry.stop)

    def exercise_constructor(self, close_results):
        process, job = inert_process(), inert_job()
        original = owner.BenchmarkJobError('BENCHMARK_JOB_CONFIGURE')
        original_cause = OSError('original configure failure')
        original.__cause__ = original_cause
        binary = b'inert binary; must never be launched'
        with tempfile.TemporaryDirectory(prefix='gt06-inert-constructor-') as directory, ExitStack() as stack:
            root = Path(directory)
            stack.enter_context(patch.object(owner, 'check_path'))
            stack.enter_context(patch.object(owner.BenchmarkProcess, 'check_sources'))
            stack.enter_context(patch.object(Path, 'mkdir'))
            stack.enter_context(patch.object(Path, 'read_bytes', return_value=binary))
            evidence = stack.enter_context(patch.object(owner, 'write'))
            stack.enter_context(patch.object(owner, 'isolated_env', return_value={}))
            launch = stack.enter_context(patch.object(owner.subprocess, 'Popen', return_value=process))
            stack.enter_context(patch.object(owner.cli_job, 'create', return_value=job))
            stack.enter_context(patch.object(owner, 'configure', side_effect=original))
            native = stack.enter_context(patch.object(owner, 'close_process_handle_native', side_effect=close_results))
            # The installed Windows runtime supplies CREATE_NO_WINDOW. Every
            # launch and native close is nevertheless replaced with inert doubles.
            with self.assertRaises(owner.BenchmarkJobError) as caught:
                owner.BenchmarkProcess([str(root / 'inert.exe')], cwd=root,
                    output=root / 'owner', source_root=root,
                    source_files={'fixture.py': hashlib.sha256(b'fixture').hexdigest()},
                    binary_sha256=hashlib.sha256(binary).hexdigest())
            self.assertIs(caught.exception, original)
            self.assertIs(original.__cause__, original_cause)
            retained = original.cleanup_owner
            self.assertIs(retained.process, process)
            launch.assert_called_once()
            if len(close_results) == 1:
                self.assertTrue(retained.closed)
                self.assertTrue(retained.job.zero_observed)
                self.assertNotIn(retained, owner.HELD_OWNERS)
                self.assertFalse(hasattr(original, 'cleanup_error'))
                proof = evidence.call_args.args[1]
                self.assertTrue(proof['closed'])
                self.assertTrue(proof['job']['zero_observed'])
            else:
                self.assertFalse(retained.closed)
                self.assertIn(retained, owner.HELD_OWNERS)
                self.assertIs(original.cleanup_error.cleanup_owner, retained)
                # This is the parent's retry of retained cleanup, not rerunning
                # the constructor or silently promoting the failed attempt.
                self.assertTrue(retained.close())
                self.assertTrue(retained.job.zero_observed)
                self.assertNotIn(retained, owner.HELD_OWNERS)
                self.assertIs(original.__cause__, original_cause)
            self.assertEqual(native.call_count, len(close_results))
            self.assertEqual(retained._failure_code, 'BENCHMARK_JOB_CONFIGURE')

    def test_setup_error_exposes_owner_even_after_successful_cleanup(self):
        self.exercise_constructor([True])

    def test_cleanup_failure_keeps_initiating_exception_and_original_cause(self):
        self.exercise_constructor([False, True])


class CaptureHandleProofTests(unittest.TestCase):
    """Rehashed synthetic reports cannot bypass the new checked-close proof."""
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix='gt06-synthetic-handle-proof-')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.output = self.root / 'capture'
        self.output.mkdir()
        self.binary = self.root / 'inert.exe'
        self.binary.write_bytes(b'not executable')
        self.binary_hash = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        (self.root / 'fixture.py').write_bytes(b'# inert source\n')
        self.sources = {'fixture.py': hashlib.sha256((self.root / 'fixture.py').read_bytes()).hexdigest()}
        invocation = {'argv': [str(self.binary)], 'cwd': str(self.root), 'source_root': str(self.root),
            'source_files': self.sources, 'binary_sha256': self.binary_hash,
            'profile': owner.PROFILE, 'formal_acceptance': False}
        owner.write(self.output / 'invocation.json', invocation)
        launched, actual = {'pid': 123}, {'pid': 123, 'exit_code': 0}
        owner.write(self.output / 'process-start.json', launched)
        owner.write(self.output / 'process-exit.json', actual)
        for name in ('stdout.txt', 'stderr.txt'):
            (self.output / name).write_bytes(b'')
        self.capture = {'schema': 'HH-GT06-BENCHMARK-CAPTURE-2', **invocation,
            'completed': True, 'natural_tree_exit': True, 'source_unchanged': True,
            'actual_process_start': launched, 'actual_process_exit': actual, 'wrapper_exit_code': 0,
            'active_at_wrapper_exit': 0, 'active_before_cleanup': 0, 'elapsed_seconds': 1.0,
            'wrapper_process_handle': {'required': True, 'closed': True,
                'close_uncertain': False, 'handle_retained': False},
            'job': {'closed': True, 'zero_observed': True, 'tainted': False, 'handle_retained': False,
                'configured': True, 'assigned': True, 'active_count': 0,
                'create_uncertain': False, 'close_uncertain': False,
                'failed_operations': [], 'native_error': None},
            'limits': {'limit_flags': 0x2000 | 0x200 | 0x8 | 0x4,
                'active_process_limit': owner.PROFILE['process_limit'],
                'job_user_time_100ns': owner.PROFILE['cpu_seconds'] * 10_000_000,
                'job_memory_bytes': owner.PROFILE['memory_bytes']},
            'invocation_sha256': hashlib.sha256((self.output / 'invocation.json').read_bytes()).hexdigest(),
            'artifacts': {name: hashlib.sha256((self.output / name).read_bytes()).hexdigest()
                for name in ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json')}}

    def verify(self, capture):
        raw = (json.dumps(capture, sort_keys=True) + '\n').encode()
        (self.output / 'capture.json').write_bytes(raw)
        return owner.verify_capture(self.output, hashlib.sha256(raw).hexdigest(),
            source_root=self.root, expected_source_files=self.sources,
            expected_binary_sha256=self.binary_hash)

    def test_exact_checked_close_proof_is_required(self):
        self.assertEqual(self.verify(self.capture), self.capture)
        cases = [None,
            {'required': True, 'closed': False, 'close_uncertain': False, 'handle_retained': True},
            {'required': True, 'closed': False, 'close_uncertain': True, 'handle_retained': True},
            {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': 0}]
        for handle in cases:
            with self.subTest(handle=handle):
                capture = deepcopy(self.capture)
                if handle is None:
                    capture.pop('wrapper_process_handle')
                else:
                    capture['wrapper_process_handle'] = handle
                with self.assertRaisesRegex(owner.BenchmarkJobError, 'BENCHMARK_CAPTURE_PROCESS_HANDLE'):
                    self.verify(capture)


if __name__ == '__main__':
    unittest.main()
