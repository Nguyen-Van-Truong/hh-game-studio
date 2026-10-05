"""Static and native tests for the GT-07 M8 process diagnostic."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.jobs import gt07_process_ownership as module


class GT07M8ProcessOwnershipContractTests(unittest.TestCase):
    def test_identity_mismatch_is_rejected_without_a_kill(self):
        expected = {"pid": 41, "creation_filetime": 100}
        observed = {"pid": 41, "creation_filetime": 101}
        self.assertFalse(module._identity_matches(expected, observed))

    def test_injected_job_query_cannot_produce_verified_identity(self):
        class Owner:
            _handle = 77
        result = module._job_identity(
            Owner(), {"pid": 41, "creation_filetime": 100},
            query=lambda _handle: (_ for _ in ()).throw(RuntimeError("QUERY_INJECTED")))
        self.assertFalse(result["verified"])
        self.assertIn("QUERY_INJECTED", result["error"])

    def test_memory_cap_is_the_real_job_range(self):
        self.assertGreaterEqual(module.MEMORY_CAP, 64 * 1024 * 1024)
        self.assertLessEqual(module.MEMORY_CAP, 128 * 1024 * 1024)
        self.assertTrue(module.JOB_OBJECT_LIMIT_JOB_MEMORY)

    def test_dry_run_is_fresh_and_authority_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allowed = root / ".local" / "reviews"
            with patch.object(module, "REVIEWS", allowed):
                report = module.run_diagnostic(allowed, "gt07-m8-static-01", dry_run=True)
            self.assertEqual(report["authority"], 0)
            self.assertTrue(report["diagnostic_only"])
            self.assertTrue((allowed / "gt07-m8-static-01" / "report.json").is_file())
            with patch.object(module, "REVIEWS", allowed):
                with self.assertRaisesRegex(ValueError, "RUN_ID_USED"):
                    module.run_diagnostic(allowed, "gt07-m8-static-01", dry_run=True)


@unittest.skipUnless(os.name == "nt" and os.environ.get("HH_GT07_M8_NATIVE") == "1",
                     "native M8 run is explicitly scheduled by the coordinator")
class GT07M8NativeProcessTests(unittest.TestCase):
    def _run(self, function):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker = module._write_worker(root)
            return function(root, worker)

    def test_held_pid_start_and_forged_start_refusal(self):
        report = self._run(module.run_held_identity)
        self.assertTrue(report["verified"], report)
        self.assertTrue(report["job"]["verified"])
        self.assertTrue(report["forged_kill_refused"])
        self.assertTrue(report["alive_before_cleanup"])

    def test_timeout_terminates_owned_tree_and_preserves_sentinel(self):
        report = self._run(module.run_owned_timeout)
        self.assertTrue(report["verified"], report)
        self.assertTrue(report["timed_out"])
        self.assertNotEqual(report["actual_exits"]["root"], module.STILL_ACTIVE)
        self.assertNotEqual(report["actual_exits"]["descendant"], module.STILL_ACTIVE)
        self.assertTrue(report["sentinel_alive_before_cleanup"])
        self.assertTrue(report["sentinel_alive_after_cleanup"])

    def test_job_memory_limit_denies_virtualalloc(self):
        report = self._run(module.run_memory_limit)
        self.assertTrue(report["verified"], report)
        self.assertEqual(report["limits"]["job_memory_limit"], module.MEMORY_CAP)
        self.assertTrue(report["allocation"]["native_virtualalloc_denied"])
        self.assertFalse(report["allocation"]["python_memory_error"])


if __name__ == "__main__":
    unittest.main()
