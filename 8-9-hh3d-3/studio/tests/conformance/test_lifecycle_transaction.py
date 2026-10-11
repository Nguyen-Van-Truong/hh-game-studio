"""Focused host crash/Stop checks for the combined package lifecycle."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from package.consumer_install import ConsumerInstall
from package.release_contract import build_package
from tests.conformance.gt10pc_lifecycle_crash_worker import instrument


class LifecycleTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).resolve().parents[2]
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.key = Ed25519PrivateKey.generate()
        cls.public = cls.key.public_key().public_bytes_raw()
        cls.package = root / "release.hhpkg"
        build_package(cls.source, cls.package, signer=cls.key.sign, key_id="test", version="0.1.0")
        cls.upgrade = root / "upgrade.hhpkg"
        build_package(cls.source, cls.upgrade, signer=cls.key.sign, key_id="test", version="0.1.1")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fixture(self, name: str):
        root = Path(self.tmp.name) / name
        project = root / "project"
        (project / "addons/hh_studio").mkdir(parents=True)
        (project / "project.godot").write_text("[application]\n", encoding="utf-8")
        installer = ConsumerInstall(root / "install", trusted_keys={"test": self.public})
        return root, project, installer

    def test_selector_cut_recovers_and_same_id_is_exact_retry(self):
        root, project, installer = self.fixture("selector-cut")
        token = installer.snapshot()["state_sha256"]

        def cut(phase):
            if phase == "selector-before-addon-intent":
                raise RuntimeError("host cut")

        with self.assertRaisesRegex(RuntimeError, "host cut"), instrument(installer, "life.install", cut):
            installer.install_lifecycle(project, self.package, command_id="life.install",
                                        expected_state_sha256=token)
        recovered = ConsumerInstall(root / "install", trusted_keys={"test": self.public})
        receipt = recovered.lookup("life.install")
        self.assertEqual(receipt["status"], "COMMITTED")
        self.assertEqual(receipt, recovered.install_lifecycle(
            project, self.package, command_id="life.install", expected_state_sha256=token))
        self.assertEqual(recovered.snapshot()["revision"], 1)
        self.assertTrue((project / "addons/hh_studio/plugin.cfg").is_file())

    def test_stop_after_staging_cancels_without_selector_or_addon_effect(self):
        _, project, installer = self.fixture("stop-staged")
        token = installer.snapshot()["state_sha256"]
        stop = threading.Event()

        def mark(phase):
            if phase == "staged":
                stop.set()

        with instrument(installer, "life.stop", mark):
            receipt = installer.install_lifecycle(project, self.package, command_id="life.stop",
                                                   expected_state_sha256=token, stop_event=stop)
        self.assertEqual(receipt["status"], "CANCELLED")
        self.assertTrue(installer.stop(command_id="life.stop.request")["stopped"])
        self.assertIsNone(installer.snapshot()["active"])
        self.assertFalse((project / "addons/hh_studio/plugin.cfg").exists())
        self.assertEqual(receipt, installer.install_lifecycle(project, self.package,
                         command_id="life.stop", expected_state_sha256=token))
        with self.assertRaisesRegex(ValueError, "stop latch"):
            installer.install_lifecycle(project, self.package, command_id="life.later",
                                        expected_state_sha256=installer.snapshot()["state_sha256"])

    def test_real_worker_cut_after_new_addon_move_recovers_forward(self):
        root, project, installer = self.fixture("new-move-cut")
        token = installer.snapshot()["state_sha256"]
        # Install once so the crash path has a real old addon tree to back up.
        first = installer.install_lifecycle(project, self.package, command_id="life.old",
                                             expected_state_sha256=token)
        token = installer.snapshot()["state_sha256"]
        request = root / "request.json"
        marker = root / "marker.json"
        request.write_text(json.dumps({"install": str(root / "install"), "project": str(project),
            "package": str(self.package), "key_id": "test", "public_key": self.public.hex(),
            "state": token, "command_id": "life.new", "phase": "new-addon-moved",
            "marker": str(marker)}), encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.source)
        worker = Path(__file__).with_name("gt10pc_lifecycle_crash_worker.py")
        process = subprocess.Popen([os.fspath(Path(sys.executable)), "-B", str(worker), str(request)],
                                   cwd=str(self.source.parent), env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.kill_at_marker(process, marker)
        recovered = ConsumerInstall(root / "install", trusted_keys={"test": self.public})
        receipt = recovered.lookup("life.new")
        self.assertEqual(receipt["status"], "COMMITTED")
        self.assertEqual(recovered.snapshot()["active"], receipt["active"])
        self.assertTrue((project / "addons/hh_studio/plugin.cfg").is_file())
        self.assertEqual(recovered.snapshot()["revision"], 2)

    def test_real_worker_cuts_after_backup_and_journal_are_forward_recovered(self):
        for phase in ("old-addon-moved", "journal-published"):
            with self.subTest(phase=phase):
                root, project, installer = self.fixture("late-" + phase)
                token = installer.snapshot()["state_sha256"]
                installer.install_lifecycle(project, self.package, command_id="life.old",
                                             expected_state_sha256=token)
                token = installer.snapshot()["state_sha256"]
                request = root / "request.json"
                marker = root / "marker.json"
                request.write_text(json.dumps({"install": str(root / "install"), "project": str(project),
                    "package": str(self.package), "key_id": "test", "public_key": self.public.hex(),
                    "state": token, "command_id": "life.late", "phase": phase,
                    "marker": str(marker)}), encoding="utf-8")
                env = dict(os.environ)
                env["PYTHONPATH"] = str(self.source)
                worker = Path(__file__).with_name("gt10pc_lifecycle_crash_worker.py")
                process = subprocess.Popen([os.fspath(Path(sys.executable)), "-B", str(worker), str(request)],
                                           cwd=str(self.source.parent), env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.kill_at_marker(process, marker)
                recovered = ConsumerInstall(root / "install", trusted_keys={"test": self.public})
                receipt = recovered.lookup("life.late")
                self.assertEqual(receipt["status"], "COMMITTED")
                self.assertEqual(recovered.snapshot()["revision"], 2)
                self.assertTrue((project / "addons/hh_studio/plugin.cfg").is_file())

    def test_rollback_stop_before_selector_keeps_new_last_good(self):
        _, project, installer = self.fixture("rollback-stop")
        old = installer.install_lifecycle(project, self.package, command_id="life.old",
                                          expected_state_sha256=installer.snapshot()["state_sha256"])
        new = installer.install_lifecycle(project, self.upgrade, command_id="life.new",
                                          expected_state_sha256=installer.snapshot()["state_sha256"])
        stop = threading.Event()

        def mark(phase):
            if phase == "before-selector":
                stop.set()

        with instrument(installer, "life.rollback", mark):
            rolled = installer.rollback_lifecycle(
                project, destination=old["active"], command_id="life.rollback",
                expected_state_sha256=installer.snapshot()["state_sha256"], stop_event=stop)
        self.assertEqual(rolled["status"], "CANCELLED")
        self.assertEqual(installer.snapshot()["active"], new["active"])
        self.assertTrue((project / "addons/hh_studio/plugin.cfg").is_file())

    def kill_at_marker(self, process, marker):
        try:
            deadline = time.monotonic() + 60
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            self.assertTrue(marker.exists())
            self.assertIsNone(process.poll())
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
            self.assertNotEqual(process.returncode, 0, (stdout, stderr))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)

    def test_control_stop_replay_after_resume_has_no_new_effect(self):
        root, _, installer = self.fixture("control-retry")
        first = ConsumerInstall.stop_existing(root / "install", command_id="stop.one")
        installer.resume(command_id="resume.one")
        self.assertEqual(first, ConsumerInstall.stop_existing(root / "install", command_id="stop.one"))
        self.assertFalse(installer.lifecycle_status()["stopped"])


if __name__ == "__main__":
    unittest.main()
