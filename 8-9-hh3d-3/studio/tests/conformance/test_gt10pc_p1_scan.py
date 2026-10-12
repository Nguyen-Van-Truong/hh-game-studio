import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from studio.package.release_contract import PackageError
from studio.tests.conformance.gt10pc_matrix_verify import _row
from studio.tests.conformance.gt10pc_p1_scan import scan_archive

CLEAN = {
    "manifest.json": b'{"monetization":"OFF","failpoint":"DISABLED"}',
    "payload/studio/package/release_contract.py": b'need(body.get("monetization") == "OFF")',
    "payload/studio/host/core/gt07_failpoints.py": b'_SCHEMA = "HH-GT07-FAILPOINT-1"',
    "payload/studio/tests/jobs/test_gt07_failpoints.py": b'{"schema": "HH-GT07-FAILPOINT-1", "enabled": True}',
}


class P1ScanTests(unittest.TestCase):
    def archive(self, extra: dict[str, bytes]) -> Path:
        path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "release.hhpkg"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in {**CLEAN, **extra}.items():
                archive.writestr(name, data)
        return path

    def test_clean_archive_passes_with_policy_and_harness_mentions(self) -> None:
        result = scan_archive(self.archive({}))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["members"], len(CLEAN))

    def test_payment_surface_rejected(self) -> None:
        with self.assertRaisesRegex(PackageError, "GT10PC_P1_PAYMENT_SURFACE"):
            scan_archive(self.archive({"payload/studio/shop.gd": b"func refund(order):"}))

    def test_monetization_outside_policy_rejected(self) -> None:
        with self.assertRaisesRegex(PackageError, "GT10PC_P1_MONETIZATION_SURFACE"):
            scan_archive(self.archive({"docs/runbook.md": b"Monetization: ads"}))

    def test_armed_failpoint_document_rejected(self) -> None:
        armed = json.dumps({"schema": "HH-GT07-FAILPOINT-1", "enabled": True}).encode()
        with self.assertRaisesRegex(PackageError, "GT10PC_P1_FAILPOINT_ARMED"):
            scan_archive(self.archive({"payload/studio/config/cut.json": armed}))

    def test_failpoint_arm_file_name_rejected(self) -> None:
        with self.assertRaisesRegex(PackageError, "GT10PC_P1_FAILPOINT_ARMED"):
            scan_archive(self.archive({"payload/studio/gt07-failpoint-reached.json": b"{}"}))

    def test_row_guard_records_failure_and_continues(self) -> None:
        errors: dict[str, str] = {}
        with _row(errors, "P1"):
            raise PackageError("GT10PC_VERIFY_P1_SCAN")
        with _row(errors, "P2"):
            pass
        self.assertEqual(errors, {"P1": "PackageError: GT10PC_VERIFY_P1_SCAN"})


if __name__ == "__main__":
    unittest.main()
