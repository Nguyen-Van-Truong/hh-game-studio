"""Lifecycle regressions using inert process/Job doubles; never launch engines."""
from __future__ import annotations

from contextlib import ExitStack
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
