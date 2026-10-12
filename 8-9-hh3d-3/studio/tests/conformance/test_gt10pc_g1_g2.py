"""Synthetic checks for P11 host process-exit binding and P4 refusal receipts."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import PackageError, build_package, digest_file
from studio.tests.conformance import run_gt10pc_matrix as matrix
from studio.tests.conformance.gt10pc_p4_negative import (
    RECEIPT_SCHEMA, SCHEMA_ERROR, ROLLBACK_ERROR, run_negative, verify_negative,
    build_bad_artifacts,
)


def _dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value).encode("utf-8") + b"\n")


class P11ProcessExitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.studio = Path(self.tmp.name)
        self.run_id = "gt06-p11-short-synthetic"
        self.run = self.studio / ".local" / "reviews" / self.run_id
        self.pids = {"import": 37680, "editor": 20620}
        capture = {
            "schema_id": "hh-studio.native-cycle-diagnostic-capture",
            "run_id": self.run_id,
            "completed_diagnostic": True,
            "full_benchmark": False,
            "formal_acceptance": False,
            "source_unchanged": True,
            "actual_exits": {
                "import": {"exit_code": 0, "pid": self.pids["import"]},
                "editor": {"exit_code": 0, "pid": self.pids["editor"]},
            },
            "jobs": {
                name: {"closed": True, "zero_observed": True, "handle_retained": False}
                for name in ("import", "editor")
            },
        }
        _dump(self.run / "capture.json", capture)
        for name, pid in self.pids.items():
            _dump(self.run / (name + "-host") / "process-exit.json", {"pid": pid, "exit_code": 0})
        self.row = {
            "status": "REHEARSAL_PASS",
            "evidence_kind": "native",
            "coverage": "one-real-Godot-cycle",
            "full_benchmark": False,
            "run_id": self.run_id,
            "capture": str(self.run / "capture.json"),
        }

    def verify(self) -> dict:
        with mock.patch.object(matrix, "ROOT", self.studio):
            return matrix._verify_p11_short_row(self.studio, self.row)

    def test_host_process_exits_match_capture_pids(self) -> None:
        result = self.verify()
        self.assertEqual(set(result["process_exit_sha256"]), {"import", "editor"})
        for name in ("import", "editor"):
            path = self.run / (name + "-host") / "process-exit.json"
            self.assertEqual(result["process_exit_sha256"][name], digest_file(path))
            self.assertEqual(result["actual_exits"][name]["pid"], self.pids[name])
            self.assertEqual(result["actual_exits"][name]["exit_code"], 0)

    def test_missing_process_exit_is_rejected(self) -> None:
        (self.run / "import-host" / "process-exit.json").unlink()
        with self.assertRaisesRegex(PackageError, r"^GT10PC_P11_VERIFY_PROCESS_EXIT$"):
            self.verify()

    def test_pid_mismatch_is_rejected(self) -> None:
        _dump(self.run / "editor-host" / "process-exit.json", {"pid": 20621, "exit_code": 0})
        with self.assertRaisesRegex(PackageError, r"^GT10PC_P11_VERIFY_PROCESS_EXIT$"):
            self.verify()

    def test_exit_code_mismatch_is_rejected(self) -> None:
        _dump(self.run / "import-host" / "process-exit.json", {"pid": self.pids["import"], "exit_code": 1})
        with self.assertRaisesRegex(PackageError, r"^GT10PC_P11_VERIFY_PROCESS_EXIT$"):
            self.verify()


class P4ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.key = Ed25519PrivateKey.generate()
        cls.keys = {"test": cls.key.public_key().public_bytes_raw()}
        source = Path(__file__).resolve().parents[2]
        good = root / "good.hhpkg"
        upgrade = root / "upgrade.hhpkg"
        built_good = build_package(source, good, signer=cls.key.sign, key_id="test")
        built_upgrade = build_package(source, upgrade, signer=cls.key.sign, key_id="test", version="0.1.1")
        cls.install_root = root / "install"
        install = ConsumerInstall(cls.install_root, trusted_keys=cls.keys, target="Windows")
        install.install(good, command_id="seed.install",
                        expected_state_sha256=install.snapshot()["state_sha256"])
        install.install(upgrade, command_id="seed.upgrade",
                        expected_state_sha256=install.snapshot()["state_sha256"])
        cls.out = root / "negative"
        artifacts = build_bad_artifacts(good, cls.key.sign, cls.out)
        run_negative(cls.install_root, cls._open, artifacts, cls.out)
        cls.good_active = built_upgrade["manifest_sha256"]
        cls.good_previous = built_good["manifest_sha256"]

    @classmethod
    def _open(cls) -> ConsumerInstall:
        return ConsumerInstall(cls.install_root, trusted_keys=cls.keys, target="Windows")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def copy_out(self) -> Path:
        dest = Path(tempfile.mkdtemp())
        copied = dest / "negative"
        shutil.copytree(self.out, copied)
        self.addCleanup(lambda: shutil.rmtree(dest, ignore_errors=True))
        return copied

    def test_each_case_has_one_child_receipt(self) -> None:
        result = verify_negative(self.out, self.keys)
        self.assertEqual(result["status"], "P4_NEG_VERIFIED")
        self.assertIs(result["acceptance"], False)
        names = sorted(path.name for path in (self.out / "receipts").glob("*.json"))
        self.assertEqual(names, ["incompatible-schema.json", "untrusted-rollback.json"])
        expected = {
            "incompatible-schema": SCHEMA_ERROR,
            "untrusted-rollback": ROLLBACK_ERROR,
        }
        for case, error in expected.items():
            receipt_path = self.out / "receipts" / (case + ".json")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["schema"], RECEIPT_SCHEMA)
            self.assertEqual(receipt["case"], case)
            self.assertIs(receipt["refused"], True)
            self.assertGreater(receipt["pid"], 0)
            self.assertNotEqual(receipt["pid"], os.getpid())
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["error_code"], error)
            self.assertLessEqual(receipt["started_at"], receipt["ended_at"])
            stdout = self.out / receipt["stdout_file"]
            self.assertEqual(stdout.read_bytes(), (error + "\n").encode("ascii"))
            self.assertEqual(digest_file(stdout), receipt["stdout_sha256"])

    def test_missing_and_extra_receipts_are_rejected(self) -> None:
        missing = self.copy_out()
        (missing / "receipts" / "incompatible-schema.json").unlink()
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPT$"):
            verify_negative(missing, self.keys)
        extra = self.copy_out()
        (extra / "receipts" / "other.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPT$"):
            verify_negative(extra, self.keys)

    def test_pid_exit_stdout_and_error_mismatches_are_rejected(self) -> None:
        cases = (
            ("incompatible-schema.json", "pid", 0),
            ("untrusted-rollback.json", "exit_code", 3),
            ("incompatible-schema.json", "error_code", "other refusal"),
        )
        for name, field, value in cases:
            copied = self.copy_out()
            path = copied / "receipts" / name
            receipt = json.loads(path.read_text(encoding="utf-8"))
            receipt[field] = value
            path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPT$"):
                verify_negative(copied, self.keys)
        copied = self.copy_out()
        stdout = copied / "receipts" / "incompatible-schema.stdout"
        stdout.write_bytes(stdout.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPT$"):
            verify_negative(copied, self.keys)

    def test_legacy_raw_without_receipts_requires_the_keyword(self) -> None:
        copied = self.copy_out()
        shutil.rmtree(copied / "receipts")
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPTS_ABSENT$"):
            verify_negative(copied, self.keys)
        legacy = verify_negative(copied, self.keys, legacy_ok_without_receipts=True)
        self.assertEqual(legacy["status"], "P4_NEG_VERIFIED")
        self.assertEqual(legacy["cases"]["incompatible-schema"]["active"], self.good_active)
        self.assertEqual(legacy["cases"]["incompatible-schema"]["previous"], self.good_previous)
        present = self.copy_out()
        (present / "receipts" / "incompatible-schema.json").unlink()
        with self.assertRaisesRegex(ValueError, r"^P4_NEG_RECEIPT$"):
            verify_negative(present, self.keys, legacy_ok_without_receipts=True)


if __name__ == "__main__":
    unittest.main()
