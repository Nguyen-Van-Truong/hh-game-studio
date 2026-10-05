"""Engine-free contract checks for the GT-07 M5 storage diagnostics."""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.jobs import gt07_storage_faults as module


class GT07M5StorageContractTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'real Windows file sharing')
    def test_exclusive_holder_releases_exact_process_after_effect_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / 'owned.tscn'
            target.write_bytes(b'last-good')
            with self.assertRaisesRegex(RuntimeError, 'native effect failed'):
                with module.exclusive_file_holder(root / 'proof', target) as proof:
                    self.assertIn(proof['read_denial_winerror'], {5, 32, 33})
                    raise RuntimeError('native effect failed')
            self.assertTrue(proof['holder_live_after_save'])
            self.assertEqual(proof['holder_exit'], 0)
            self.assertTrue(proof['last_good_preserved'])
            self.assertEqual(target.read_bytes(), b'last-good')

    def test_dry_run_is_fresh_engine_free_and_authority_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary) / ".local" / "reviews"
            with patch.object(module, "REVIEWS", allowed):
                report = module.run_diagnostic(allowed, "gt07-m5-static-01", dry_run=True)
                self.assertEqual(report["authority"], 0)
                self.assertTrue(report["diagnostic_only"])
                self.assertFalse(report["engine_started"])
                self.assertTrue(report["dry_run"])
                self.assertTrue((allowed / "gt07-m5-static-01" / "report.json").is_file())
                with self.assertRaisesRegex(ValueError, "RUN_ID_USED"):
                    module.run_diagnostic(allowed, "gt07-m5-static-01", dry_run=True)

    def test_native_run_consumes_matching_dry_run_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            allowed = Path(temporary) / ".local" / "reviews"
            with patch.object(module, "REVIEWS", allowed):
                admitted = module.run_diagnostic(allowed, "gt07-m5-static-02", dry_run=True)
                output = allowed / "gt07-m5-static-02"
                consumed = module._reuse_dry_run(allowed, "gt07-m5-static-02")
                self.assertEqual(consumed, output)
                self.assertTrue((output / "dry-run-report.json").is_file())
                self.assertEqual(admitted["source_hashes"], module._source_hashes())
                with self.assertRaisesRegex(ValueError, "RUN_ID_USED"):
                    module._reuse_dry_run(allowed, "gt07-m5-static-02")

    def test_fsync_and_diskfull_fail_closed_keep_last_good(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for mode in ("fsync", "diskfull"):
                with self.subTest(mode=mode):
                    result = module._injected_write(output, mode)
                    self.assertTrue(result["verified"], result)
                    self.assertEqual(result["status"], "UNKNOWN")
                    self.assertEqual(result["mode"], "INJECTED")
                    self.assertEqual(result["receipt"], "ABSENT")
                    self.assertFalse(result["committed_proof"])

    def test_file_identity_has_explicit_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.bin"
            path.write_bytes(b"stable")
            identity = module._identity(path)
            self.assertIsInstance(identity, dict)
            self.assertIs(type(identity["volume"]), int)
            self.assertIs(type(identity["file_id"]), int)
            self.assertEqual(identity["size"], 6)

    def test_cross_volume_is_explicitly_skipped_when_unavailable(self):
        if os.name == "nt":
            self.skipTest("native volume discovery is tested only by the opt-in run")
        with tempfile.TemporaryDirectory() as temporary:
            result = module.run_cross_volume(Path(temporary))
            self.assertEqual(result["status"], "SKIPPED")
            self.assertEqual(result["reason"], "WINDOWS_REQUIRED")

    def test_source_closure_is_stable_and_bound_to_probe(self):
        values = module._source_hashes()
        self.assertEqual(len(values["source_closure_sha256"]), 64)
        self.assertIn("studio/tests/jobs/gt07_storage_faults.py", values)


@unittest.skipUnless(os.name == "nt" and os.environ.get("HH_GT07_M5_NATIVE") == "1",
                     "native M5 run is explicitly scheduled by the coordinator")
class GT07M5NativeTests(unittest.TestCase):
    def test_native_storage_matrix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / ".local" / "reviews"
            with patch.object(module, "REVIEWS", root):
                report = module.run_diagnostic(root, "gt07-m5-native-01")
            self.assertTrue(report["verified"], report)
            self.assertTrue(all(row.get("verified") is True or row.get("status") == "SKIPPED"
                                for row in report["scenarios"]), report)


if __name__ == "__main__":
    unittest.main()
