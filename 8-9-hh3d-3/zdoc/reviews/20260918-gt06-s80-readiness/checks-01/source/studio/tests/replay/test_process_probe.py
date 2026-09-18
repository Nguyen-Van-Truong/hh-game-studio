"""Native identity/read-only memory and failed-handle ownership regressions."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay.process_probe import ProcessProbe, ProbeError, HELD_PROBES


class FakeKernel:
    def __init__(self, results):
        self.results, self.calls = list(results), 0

    def CloseHandle(self, _):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class ProbeTests(unittest.TestCase):
    def tearDown(self):
        # Only fake owners are deliberately retained by these unit tests.
        for owner in tuple(HELD_PROBES):
            if isinstance(owner.k, FakeKernel):
                HELD_PROBES.remove(owner)
        self.assertEqual([], HELD_PROBES)

    def fake(self, results):
        owner = object.__new__(ProcessProbe)
        owner.k, owner.handle, owner.close_uncertain = FakeKernel(results), 123, False
        return owner

    def test_checked_close_failure_retains_owner_and_can_retry(self):
        owner = self.fake([False, True])
        with self.assertRaises(ProbeError) as caught:
            owner.close()
        self.assertIs(caught.exception.cleanup_owner, owner)
        self.assertIn(owner, HELD_PROBES)
        self.assertEqual(123, owner.handle)
        owner.close()
        owner.close()
        self.assertIsNone(owner.handle)
        self.assertEqual(2, owner.k.calls)

    def test_interrupted_close_never_reuses_uncertain_handle(self):
        owner = self.fake([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):
            owner.close()
        with self.assertRaisesRegex(ProbeError, 'PROBE_CLOSE_UNCERTAIN'):
            owner.close()
        self.assertEqual(1, owner.k.calls)
        self.assertIn(owner, HELD_PROBES)

    def test_held_cleanup_blocks_new_probe(self):
        owner = self.fake([False, True])
        with self.assertRaises(ProbeError):
            owner.close()
        with self.assertRaisesRegex(ProbeError, 'PROBE_CLEANUP_HELD'):
            ProcessProbe(os.getpid(), Path(sys.executable))
        owner.close()

    def test_invalid_pid_never_opens(self):
        for pid in (False, 0, -1, 2**32, '1'):
            with self.subTest(pid=pid), self.assertRaises(ProbeError):
                ProcessProbe(pid, Path(sys.executable))

    @unittest.skipUnless(os.name == 'nt', 'Windows process API')
    def test_actual_retained_process_identity_and_memory(self):
        with ProcessProbe(os.getpid(), Path(sys.executable)) as owner:
            first, second = owner.sample(), owner.sample()
            self.assertRegex(owner.process_start, r'^windows:[0-9]+$')
            self.assertGreater(first['rss_bytes'], 0)
            self.assertGreater(second['host_mono_us'], first['host_mono_us'])
            self.assertEqual(os.getpid(), owner.pid)
        self.assertIsNone(owner.handle)

    @unittest.skipUnless(os.name == 'nt', 'Windows process API')
    def test_actual_foreign_image_expectation_rejected_and_closed(self):
        with self.assertRaisesRegex(ProbeError, 'PROBE_IMAGE_IDENTITY'):
            ProcessProbe(os.getpid(), Path(sys.executable).with_name('not-the-owned-image.exe'))
        self.assertFalse(HELD_PROBES)


if __name__ == '__main__':
    unittest.main()
