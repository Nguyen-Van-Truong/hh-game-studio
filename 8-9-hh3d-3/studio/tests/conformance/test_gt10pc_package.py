"""Focused unit checks for the GT-10-PC package contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from package.release_contract import ConsumerInstall, PackageError, build_package, verify_package


class GT10PCPackageTests(unittest.TestCase):
    def test_verify_before_extract_rejects_traversal_and_tamper(self) -> None:
        root = Path(__file__).resolve().parents[3] / "studio"
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "release.hhpkg"
            build_package(root, artifact)
            self.assertTrue(verify_package(artifact)["manifest"]["package_id"])
            broken = Path(td) / "broken.hhpkg"
            broken.write_bytes(artifact.read_bytes()[: len(artifact.read_bytes()) // 2])
            with self.assertRaises(PackageError):
                verify_package(broken)

    def test_command_dedup_rollback_and_source_save_preservation(self) -> None:
        root = Path(__file__).resolve().parents[3] / "studio"
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "release.hhpkg"
            build_package(root, artifact)
            consumer = ConsumerInstall(Path(td) / "consumer")
            source, save = consumer.source.read_bytes(), consumer.save.read_bytes()
            first = consumer.install(artifact, command_id="test.install")
            self.assertEqual(first, consumer.install(artifact, command_id="test.install"))
            self.assertEqual(source, consumer.source.read_bytes())
            self.assertEqual(save, consumer.save.read_bytes())
            self.assertEqual(consumer.smoke()["active"], first["active"])


if __name__ == "__main__":
    unittest.main()
