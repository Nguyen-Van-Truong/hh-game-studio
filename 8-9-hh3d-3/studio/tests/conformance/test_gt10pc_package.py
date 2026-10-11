"""Adversarial archive and transaction checks; not native GT-10 evidence."""
from __future__ import annotations
import tempfile
import unittest
import zipfile
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from package.release_contract import PackageError, build_package, verify_package
from package.consumer_install import ConsumerInstall
from package.consumer_support import consumer_fixture_smoke, preflight, support_bundle

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

    def test_missing_pinned_dependency_is_actionable(self):
        with tempfile.TemporaryDirectory() as td:
            artifact = Path(td) / "release.hhpkg"
            self.make(artifact)
            broken = Path(td) / "missing-lock.hhpkg"
            with zipfile.ZipFile(artifact) as source, zipfile.ZipFile(broken, "w") as target:
                for info in source.infolist():
                    if info.filename == "docs/compatibility-lock.json":
                        continue
                    target.writestr(info, source.read(info.filename))
            with self.assertRaisesRegex(PackageError, "missing pinned dependency"):
                verify_package(broken, trusted_keys=self.keys)

    def test_preflight_dependency_template_and_hash_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            with self.assertRaisesRegex(PackageError, "missing dependency godot"):
                preflight(artifact, trusted_keys=self.keys, target="Windows",
                          required=("godot",), paths={})
            bad_godot = root / "godot.exe"; bad_godot.write_bytes(b"wrong")
            with self.assertRaisesRegex(PackageError, "dependency version/hash mismatch for godot"):
                preflight(artifact, trusted_keys=self.keys, target="Windows",
                          required=("godot",), paths={"godot": bad_godot})
            bad_templates = root / "templates.tpz"; bad_templates.write_bytes(b"wrong")
            with self.assertRaisesRegex(PackageError, "dependency version/hash mismatch for export_templates"):
                preflight(artifact, trusted_keys=self.keys, target="Windows",
                          required=("export_templates",), paths={"export_templates": bad_templates})

    def test_independent_consumer_smoke_and_scrubbed_support_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            result = consumer_fixture_smoke(artifact, root / "consumer", trusted_keys=self.keys)
            self.assertFalse(result["acceptance"])
            self.assertTrue(result["consumer_save_preserved"])
            bundle_path = root / "support.json"
            summary = support_bundle(artifact, bundle_path, trusted_keys=self.keys,
                                     target="Windows")
            raw = bundle_path.read_text(encoding="utf-8")
            self.assertEqual(summary["scrub_policy"], "allowlist-no-raw-values-v1")
            self.assertNotIn("PRIVATE", raw)
            self.assertNotIn("TOKEN", raw)
            self.assertNotIn("consumer-owned-save", raw)

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

    @unittest.skipUnless(os.name == "nt", "Windows rename sharing-lock boundary")
    def test_windows_stage_publish_retries_transient_sharing_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            install = ConsumerInstall(root / "install", trusted_keys=self.keys)
            real_rename = os.rename
            attempts = []

            def flaky_rename(source, destination):
                attempts.append((source, destination))
                if len(attempts) <= 2:
                    raise PermissionError(13, "simulated antivirus share lock")
                return real_rename(source, destination)

            with mock.patch("package.consumer_install.os.rename", side_effect=flaky_rename):
                receipt = install.install(artifact, command_id="retry-stage",
                                          expected_state_sha256="ABSENT")
            self.assertEqual(receipt["status"], "COMMITTED")
            self.assertEqual(len(attempts), 3)
            self.assertTrue((install.versions / receipt["active"] / "manifest.json").is_file())

    def test_addon_repair_restores_owned_bytes_and_keeps_manual_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            project = root / "project"; project.mkdir()
            (project / "project.godot").write_text("[application]\n")
            install = ConsumerInstall(root / "install", trusted_keys=self.keys)
            receipt = install.install(artifact, command_id="install", expected_state_sha256=install.snapshot()["state_sha256"])
            first = install.install_addon(project, release=receipt["active"], command_id="addon", expected_state_sha256=install.snapshot()["state_sha256"])
            owned = project / "addons" / "hh_studio" / "plugin.cfg"
            expected = owned.read_bytes()
            owned.write_bytes(b"consumer changed package file\n")
            manual = project / "addons" / "hh_studio" / "owner-note.txt"
            manual.write_text("keep me")
            install.install_addon(project, release=receipt["active"], command_id="repair", repair=True,
                                  expected_state_sha256=install.snapshot()["state_sha256"])
            self.assertEqual(owned.read_bytes(), expected)
            self.assertEqual(manual.read_text(), "keep me")
            install.deactivate(command_id="deactivate", expected_state_sha256=install.snapshot()["state_sha256"])
            self.assertEqual(first, install.install_addon(project, release=receipt["active"], command_id="addon",
                             expected_state_sha256=install.snapshot()["state_sha256"]))

    def test_addon_unowned_collision_rejected_and_project_ownership_isolated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            install = ConsumerInstall(root / "install", trusted_keys=self.keys)
            release = install.install(artifact, command_id="install", expected_state_sha256="ABSENT")["active"]
            for name in ("a", "b"):
                project = root / name
                (project / "addons/hh_studio").mkdir(parents=True)
                (project / "project.godot").write_text("[application]\n")
            conflict = root / "a/addons/hh_studio/plugin.cfg"
            conflict.write_text("owner addon")
            token = install.snapshot()["state_sha256"]
            with self.assertRaisesRegex(PackageError, "unowned addon file conflict"):
                install.install_addon(root / "a", release=release, command_id="a", expected_state_sha256=token)
            self.assertEqual(token, install.snapshot()["state_sha256"])
            self.assertEqual(conflict.read_text(), "owner addon")
            install.install_addon(root / "b", release=release, command_id="b", expected_state_sha256=token)
            install.uninstall_addon(root / "a", command_id="uninstall-a", expected_state_sha256=install.snapshot()["state_sha256"])
            self.assertTrue((root / "b/addons/hh_studio/plugin.cfg").is_file())
            self.assertEqual(conflict.read_text(), "owner addon")

    def test_addon_recovers_four_real_process_kills_without_duplicate_command(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); artifact = root / "release.hhpkg"
            self.make(artifact)
            for phase in ("intent", "old-moved", "new-moved", "state-published"):
                with self.subTest(phase=phase):
                    case = root / phase
                    project = case / "project"
                    (project / "addons/hh_studio").mkdir(parents=True)
                    (project / "project.godot").write_text("[application]\n")
                    manual = project / "addons/hh_studio/owner.txt"
                    manual.write_text("preserved")
                    install = ConsumerInstall(case / "install", trusted_keys=self.keys)
                    release = install.install(artifact, command_id="release", expected_state_sha256="ABSENT")["active"]
                    token = install.snapshot()["state_sha256"]
                    marker = case / "marker.json"
                    request = case / "request.json"
                    request.write_text(json.dumps({"install": str(install.root), "project": str(project),
                        "release": release, "state": token, "phase": phase, "marker": str(marker),
                        "public_key": self.keys["test"].hex()}))
                    with (case / "worker.log").open("wb") as log:
                        proc = subprocess.Popen([sys.executable, "-B", str(Path(__file__).with_name("gt10pc_crash_worker.py")), str(request)],
                            stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                        try:
                            deadline = time.monotonic() + 20
                            while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
                                time.sleep(0.05)
                            self.assertTrue(marker.exists(), (case / "worker.log").read_text())
                            self.assertIsNone(proc.poll())
                            proc.kill()
                            self.assertNotEqual(proc.wait(timeout=10), 0)
                        finally:
                            if proc.poll() is None:
                                proc.kill(); proc.wait(timeout=10)
                    recovered = ConsumerInstall(case / "install", trusted_keys=self.keys)
                    receipt = recovered.lookup("crashed-addon")
                    self.assertIsNotNone(receipt)
                    self.assertEqual(receipt, recovered.install_addon(project, release=release,
                        command_id="crashed-addon", expected_state_sha256=token))
                    self.assertEqual(recovered.snapshot()["revision"], 2)
                    self.assertEqual(manual.read_text(), "preserved")
                    self.assertFalse((case / "install/.addon-pending.json").exists())
                    for name, data in recovered.addon_files(release).items():
                        self.assertEqual((project / "addons/hh_studio" / name).read_bytes(), data)

if __name__ == "__main__": unittest.main()
