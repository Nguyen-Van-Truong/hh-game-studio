"""Lifecycle regressions using inert process/Job doubles; never launch engines."""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import hashlib
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_job as owner


class ConfigureReadbackTests(unittest.TestCase):
    @staticmethod
    def fixture(*, host=False, changed=None, active=0, assigned=False):
        from ctypes import wintypes as w

        class BasicLimit(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                        ('active_limit', w.DWORD), ('affinity', ctypes.c_size_t),
                        ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class ExtendedLimit(ctypes.Structure):
            _fields_ = [('basic', BasicLimit), ('io', ctypes.c_ulonglong * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        class FakeNative:
            pass

        FakeNative.ExtendedLimit = ExtendedLimit

        class ApiCall:
            def __init__(self, callback):
                self.callback = callback
                self.argtypes = None
                self.restype = None

            def __call__(self, *args):
                return self.callback(*args)

        class FakeKernel:
            def __init__(self):
                self.calls = 0
                self.limits = None
                self.SetInformationJobObject = ApiCall(self.set_information)
                self.QueryInformationJobObject = ApiCall(self.query_information)

            def set_information(self, _handle, _kind, limits, _size):
                self.calls += 1
                self.limits = limits._obj
                return True

            def query_information(self, _handle, _kind, observed, _size, returned):
                observed = observed._obj
                returned._obj.value = ctypes.sizeof(ExtendedLimit)
                observed.basic.flags = self.limits.basic.flags
                observed.basic.active_limit = self.limits.basic.active_limit
                observed.basic.job_time = self.limits.basic.job_time
                observed.job_memory = self.limits.job_memory
                if changed:
                    field, value = changed
                    if field == 'size': returned._obj.value = value
                    elif field == 'job_memory': observed.job_memory = value
                    else: setattr(observed.basic, field, value)
                return True

        kernel = FakeKernel()
        job = SimpleNamespace(_handle=123, _native=FakeNative(), assigned=assigned,
                              active_count=lambda: active)
        return job, kernel

    def test_both_roles_require_exact_single_readback(self):
        for host in (False, True):
            job, kernel = self.fixture(host=host)
            with patch.object(owner.ctypes, 'WinDLL', return_value=kernel):
                result = owner.configure(job, campaign_host=host)
            self.assertEqual(kernel.calls, 1)
            self.assertEqual(result, {'limit_flags':8716,
                'active_process_limit': 6 if host else 4,
                'job_user_time_100ns':72000000000,'job_memory_bytes':2147483648})

    def test_each_wrong_readback_field_is_rejected_without_retry(self):
        for changed in [('job_time',72000156250),('job_time',71999999999),
                        ('flags',8192),('active_limit',99),('job_memory',1),('size',0)]:
            with self.subTest(changed=changed):
                job, kernel = self.fixture(changed=changed)
                with patch.object(owner.ctypes, 'WinDLL', return_value=kernel):
                    with self.assertRaisesRegex(owner.BenchmarkJobError,'BENCHMARK_JOB_LIMIT_MISMATCH'):
                        owner.configure(job)
                self.assertEqual(kernel.calls,1)

    def test_assigned_or_nonempty_or_unknown_job_cannot_be_reconfigured(self):
        for active, assigned in [(1,False),(None,False),(0,True)]:
            job, kernel = self.fixture(active=active,assigned=assigned)
            with patch.object(owner.ctypes, 'WinDLL', return_value=kernel):
                with self.assertRaisesRegex(owner.BenchmarkJobError,'BENCHMARK_JOB_NOT_EMPTY'):
                    owner.configure(job)
            self.assertEqual(kernel.calls,0)


class InertProcessHandle(int):
    # Never wrap a real OS handle in lifecycle doubles. Native close must be
    # intercepted by any test that exercises cleanup of these process doubles.
    closed = False


class BenchmarkJobLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.registry = patch.object(owner, 'HELD_OWNERS', [])
        self.registry.start()
        self.addCleanup(self.registry.stop)

    @staticmethod
    def inert_owner(*, tainted=False):
        value = owner.BenchmarkProcess.__new__(owner.BenchmarkProcess)
        value.closed = value.released = False
        value._report_number = 0
        value.output = Path('unused-test-output')
        value.started = value._last_disk = time.monotonic()
        value.threads, value.errors = [], []
        value.overflow = threading.Event()
        value.process = None
        value.job = SimpleNamespace(closed=True, zero_observed=True, tainted=tainted,
            close=Mock(), snapshot=lambda: {'closed': True, 'zero_observed': True,
                                           'tainted': tainted, 'handle_retained': False})
        return value

    def test_verified_cleanup_releases_historical_taint_without_promoting_success(self):
        value = self.inert_owner(tainted=True)
        owner.HELD_OWNERS.append(value)
        with patch.object(owner, 'write') as evidence:
            self.assertTrue(value.close())
            self.assertTrue(value.close())
        self.assertTrue(value.closed)
        self.assertNotIn(value, owner.HELD_OWNERS)
        self.assertTrue(value.job.tainted, 'historical failure must remain visible')
        value.job.close.assert_called_once()
        self.assertEqual(evidence.call_count, 1)
        self.assertIsNot(evidence.call_args.args[1].get('completed'), True)

    def test_stop_observation_is_latched_even_when_later_poll_sees_exit_zero(self):
        value = self.inert_owner()
        value.process = SimpleNamespace(poll=lambda: 0, returncode=0,
            _handle=InertProcessHandle(900001), wait=Mock(return_value=0),
            stdin=None, stdout=None, stderr=None)
        with self.assertRaises(owner.BenchmarkJobError):
            value.tick(stop=True)
        with self.assertRaises(owner.BenchmarkJobError):
            value.tick(stop=False)

    def test_empty_source_closure_rejected_before_helper_creation(self):
        process = SimpleNamespace(stdin=Mock(), stdout=Mock(), stderr=Mock(),
            _handle=InertProcessHandle(900002), returncode=0, wait=Mock(return_value=0))
        fake_job = SimpleNamespace()
        # Every external effect is intercepted. The only successful behavior is
        # rejection before Popen; current code wrongly releases the mocked gate.
        with ExitStack() as stack:
            stack.enter_context(patch.object(owner, 'os', SimpleNamespace(name='nt')))
            stack.enter_context(patch.object(owner, 'check_path'))
            stack.enter_context(patch.object(Path, 'read_bytes', return_value=b'fixed-test-binary'))
            stack.enter_context(patch.object(Path, 'mkdir'))
            stack.enter_context(patch.object(owner, 'write'))
            launch = stack.enter_context(patch.object(owner.subprocess, 'Popen', return_value=process))
            stack.enter_context(patch.object(owner.cli_job, 'create', return_value=fake_job))
            stack.enter_context(patch.object(owner, 'configure'))
            stack.enter_context(patch.object(owner, 'isolated_env', return_value={}))
            stack.enter_context(patch.object(owner.threading, 'Thread'))
            with self.assertRaises(owner.BenchmarkJobError):
                owner.BenchmarkProcess(['fixed-test-engine'], cwd=Path('.'), output=Path('unused-output'),
                    source_root=Path('.'), source_files={},
                    binary_sha256=hashlib.sha256(b'fixed-test-binary').hexdigest())
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
