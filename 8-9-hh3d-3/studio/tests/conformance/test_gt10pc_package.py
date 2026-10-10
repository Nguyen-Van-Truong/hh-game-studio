"""Adversarial archive and transaction checks; not native GT-10 evidence."""
from __future__ import annotations
import tempfile
import unittest
import zipfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from package.release_contract import PackageError, build_package, verify_package
from package.consumer_install import ConsumerInstall

class GT10PCPackageTests(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parents[2]
        self.key = Ed25519PrivateKey.generate()
        self.keys = {"test": self.key.public_key().public_bytes_raw()}

    def make(self, path: Path, version="0.1.0"):
        return build_package(self.source, path, signer=self.key.sign, key_id="test", version=version)

    def test_verify_before_extract_rejects_truncate_and_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "release.hhpkg"
            self.make(artifact)
            self.assertGreater(len(verify_package(artifact, trusted_keys=self.keys)["members"]), 100)
            truncated = Path(td) / "truncated.hhpkg"
            truncated.write_bytes(artifact.read_bytes()[:-17])
            with self.assertRaises(PackageError): verify_package(truncated, trusted_keys=self.keys)
            tampered = Path(td) / "tampered.hhpkg"
            with zipfile.ZipFile(artifact) as source, zipfile.ZipFile(tampered, "w") as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename != "manifest.json": data = data + b"tamper"
                    target.writestr(info, data)
            with self.assertRaises(PackageError): verify_package(tampered, trusted_keys=self.keys)

    def test_immutable_upgrade_rollback_dedup_and_consumer_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); old, new = root / "old.hhpkg", root / "new.hhpkg"
            self.make(old); self.make(new, "0.1.1")
            consumer_project = root / "project"; consumer_project.mkdir()
            source = consumer_project / "game-source.txt"; save = consumer_project / "save.dat"
            source.write_text("owner source"); save.write_text("owner save")
            install = ConsumerInstall(root / "install", trusted_keys=self.keys)
            token = install.snapshot()["state_sha256"]
            a = install.install(old, command_id="install.old", expected_state_sha256=token)
            self.assertEqual(a, install.install(old, command_id="install.old", expected_state_sha256=token))
            token = install.snapshot()["state_sha256"]
            b = install.install(new, command_id="install.new", expected_state_sha256=token)
            token = install.snapshot()["state_sha256"]
            rolled = install.rollback(command_id="rollback.new", destination=a["active"], expected_state_sha256=token)
            self.assertEqual(rolled, install.rollback(command_id="rollback.new", destination=a["active"], expected_state_sha256=token))
            self.assertEqual(install.snapshot()["active"], a["active"])
            self.assertEqual(source.read_text(), "owner source"); self.assertEqual(save.read_text(), "owner save")
            self.assertTrue((install.versions / a["active"]).is_dir())
            self.assertTrue((install.versions / b["active"]).is_dir())

    def test_addon_repair_restores_owned_bytes_and_keeps_manual_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            project = root / "project"; project.mkdir()
            (project / "project.godot").write_text("[application]\n")
            install = ConsumerInstall(root / "install", trusted_keys=self.keys)
            receipt = install.install(artifact, command_id="install", expected_state_sha256=install.snapshot()["state_sha256"])
            install.install_addon(project, command_id="addon", expected_state_sha256=install.snapshot()["state_sha256"])
            owned = project / "addons" / "hh_studio" / "addons" / "hh_studio" / "plugin.cfg"
            expected = owned.read_bytes()
            owned.write_bytes(b"consumer changed package file\n")
            manual = project / "addons" / "hh_studio" / "owner-note.txt"
            manual.write_text("keep me")
            install.install_addon(project, command_id="repair", repair=True,
                                  expected_state_sha256=install.snapshot()["state_sha256"])
            self.assertEqual(owned.read_bytes(), expected)
            self.assertEqual(manual.read_text(), "keep me")

if __name__ == "__main__": unittest.main()
