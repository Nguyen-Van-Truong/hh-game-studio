"""Fail-closed checks for the P7 raw verifier. Not a native acceptance run."""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from studio.package.release_contract import canonical, digest_bytes, digest_file, verify_package
from studio.package.trust import load_trust
from studio.tests.conformance.gt10pc_p7_verify import verify_p7
from studio.tests.conformance.run_gt10pc_p7 import (
    CASES, _job_process_tree, make_packages,
)
from studio.build.bootstrap.run_fixture import _close_job, _job_for_process

PLUGIN = "payload/studio/godot-addon/addons/hh_studio/plugin.gd"
EXECUTOR = "payload/studio/godot-addon/linux_executor.py"
TARGET = CASES[6:][0][0]


def _dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _lifecycle() -> str:
    world = {"avatar_asset_loaded": True, "sprite_asset_loaded": True, "marker": 1}
    rows = [
        ("menu", "MENU", False), ("start", "PLAYING", False),
        ("pause", "PAUSED", True), ("resume", "PLAYING", False),
        ("restart", "PLAYING", False), ("pause", "PAUSED", True),
        ("resume", "PLAYING", False), ("quit", "QUIT", False),
    ]
    lines = []
    for event, phase, paused in rows:
        lines.append("HH_FIXTURE_LIFECYCLE_STATE " + json.dumps({
            "event": event, "freeze_errors": 0, "phase": phase, "seed": 90127,
            "tree_paused": paused, "world": world}, sort_keys=True))
    for index in range(20):
        lines.append("HH_FIXTURE_LIFECYCLE_INPUT " + json.dumps(
            {"edge": index, "seed": 90127}, sort_keys=True))
    lines.append("HH_FIXTURE_LIFECYCLE_SUMMARY " + json.dumps({
        "freeze_errors": 0, "input_edges": 20, "lifecycle_complete": True,
        "mode": "smoke", "pause_frames": 2, "reason": "input_quit", "seed": 90127,
        "state_observations": 8,
        "transitions": ["start", "pause", "resume", "restart", "pause", "resume", "quit"],
    }, sort_keys=True))
    return "\n".join(lines) + "\n"


def _process(base: Path, label: str, pid: int, stdout: str) -> dict:
    base.mkdir(parents=True, exist_ok=True)
    (base / (label + "-stdout.txt")).write_text(stdout, encoding="utf-8")
    (base / (label + "-stderr.txt")).write_bytes(b"")
    _dump(base / (label + "-host.json"), {"exit_code": 0, "target_pid": pid})
    return {"exit_code": 0, "host": label + "-host.json", "ownership": "gated_job_kill_on_close",
            "stderr": label + "-stderr.txt", "stdout": label + "-stdout.txt",
            "target_pid": pid, "timed_out": False, "tree_verified": True, "wrapper_exit_code": 0}


def _profile(manifest: dict, members: dict) -> dict:
    declarations = ast.parse(members[EXECUTOR].decode("utf-8"))
    inventories = [ast.literal_eval(node.value) for node in declarations.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == "GAMEPLAY_RUNTIME_FILES"
                       for target in node.targets)]
    files = {name: manifest["files"]["payload/studio/" + name]["sha256"] for name in inventories[0]}
    closure = digest_bytes(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    body = {"authority": 0, "client_versions": ["pc-godot-4.7.2"],
            "operations": ["scene.node.create", "scene.node.update", "scene.resource.create",
                           "gameplay-source.inspect", "gameplay-source.publish"],
            "profile": "hh-godot-gameplay-source-1", "project_id": "project.registered.arena",
            "root_type": "Node2D", "schema": "hh-gameplay-fixture-host-config-1", "version": 1}
    digest = digest_bytes(canonical(body))
    descriptor = {**body, "catalog_digest": "sha256:" + digest,
                  "config_sha256": files["godot-addon/fixture_profile.json"],
                  "module_sha256": files["godot-addon/gameplay_fixture_profile.py"],
                  "profile_digest": digest, "public_runtime_enabled": False, "script_enabled": True}
    empty = {"fixture_enabled": False, "profiles": []}
    return {"default": empty, "other": empty,
            "own": {"fixture_enabled": True, "profiles": [descriptor],
                    "project_id": "project.registered.arena"},
            "runtime_files": files, "runtime_source_closure_sha256": closure}


class JobTreeTests(unittest.TestCase):
    def test_assigned_pid_is_listed(self) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        job = _job_for_process(process)
        try:
            self.assertIn(process.pid, _job_process_tree(job))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            _close_job(job)


class VerifyP7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="hh-p7-verify-")
        root = Path(cls.tmp.name)
        key = Ed25519PrivateKey.generate()
        private = root / "private.raw"
        private.write_bytes(key.private_bytes_raw())
        public = key.public_key().public_bytes_raw()
        trust = root / "trust.json"
        trust.write_bytes(json.dumps({
            "key_id": "gt10pc-p7-unit", "public_key_hex": public.hex(),
            "schema": "hh-local-publisher-trust-1"}, sort_keys=True, separators=(",", ":")).encode())
        cls.trust, cls.trust_sha = trust, digest_file(trust)
        built_old, built_new, _keys = make_packages(
            root / "built", trust=trust, private=private, trust_sha256=cls.trust_sha)
        keys = load_trust(trust, expected_sha256=cls.trust_sha)
        cls.old_path = Path(built_old["artifact_path"])
        cls.new_path = Path(built_new["artifact_path"])
        cls.old = verify_package(cls.old_path, trusted_keys=keys, target="Windows", expected_version="0.1.0")
        cls.new = verify_package(cls.new_path, trusted_keys=keys, target="Windows", expected_version="0.1.1")
        plugin = cls.old["members"][PLUGIN]
        suffix = b"\n# GT10PC_P7_VARIANT=old\n"
        if not plugin.endswith(suffix):
            raise AssertionError("old variant suffix missing")
        members = dict(cls.old["members"])
        members[PLUGIN] = plugin[:-len(suffix)]
        cls.release = {"manifest": cls.old["manifest"], "members": members}
        cls.root = root / "p7"
        cls._build()
        cls.p7_bytes = (cls.root / "p7.json").read_bytes()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    @classmethod
    def _build(cls) -> None:
        root = cls.root
        if root.exists():
            shutil.rmtree(root)
        root.mkdir()
        evidence = {}
        cases = []
        project = cls._project_ledger()
        profile = _profile(cls.old["manifest"], cls.old["members"])
        lifecycle = _lifecycle()
        for index, (name, action, phase, disposition) in enumerate(CASES[6:]):
            case = root / "cases" / name
            victim = 4242 + index
            command_id = "p7." + name
            receipt = {"action": action, "command_id": command_id, "status": "COMMITTED"}
            body = {"active": cls.old["manifest_sha256"], "commands": {
                "seed-old": {"receipt": {"command_id": "seed-old"}, "request_digest": "a" * 64},
                command_id: {"receipt": receipt, "request_digest": "b" * 64}},
                    "previous": None, "revision": 5, "schema": "hh-studio-install-4",
                    "target": "Windows"}
            raw = canonical(body) + b"\n"
            state = {**body, "state_sha256": digest_bytes(raw)}
            (case / "install").mkdir(parents=True)
            (case / "install" / ".install.json").write_bytes(raw)
            (case / "install-before-reopen.json").write_bytes(raw)
            last_good = case / "install" / "releases" / cls.old["manifest_sha256"]
            with zipfile.ZipFile(cls.old_path) as archive:
                for member in archive.namelist():
                    target = last_good / member
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
            _dump(case / "applicability.json", {
                "network_loss": {"reason": "local lifecycle WAL; no network client in this phase",
                                 "status": "NOT_APPLICABLE"},
                "token_rotation": {"reason": "no session token; state_sha256 is a local CAS digest",
                                   "status": "NOT_APPLICABLE"}})
            cut = {"action": action, "disposition": disposition, "phase": phase, "pid": victim}
            _dump(case / "cut.json", cut)
            _dump(case / "request.json", {"command_id": command_id})
            stdout, stderr = b"parked\n", b""
            (case / "worker-stdout.txt").write_bytes(stdout)
            (case / "worker-stderr.txt").write_bytes(stderr)
            host = {"actual_exit": 1 if disposition == "kill" else 0, "disposition": disposition,
                    "exit_code": 1 if disposition == "kill" else 0,
                    "kill_epoch": 1700000000.5 if disposition == "kill" else None,
                    "killer_pid": 7001, "pid": victim, "process_tree": [victim, victim + 50],
                    "schema": "hh-gt10pc-p7-worker-host-2",
                    "stderr_sha256": digest_bytes(stderr),
                    "stdout_sha256": digest_bytes(stdout),
                    "stop_epoch": None if disposition == "kill" else 1700000001.5,
                    "victim_pid": victim}
            _dump(case / "worker-host.json", host)
            proof_project = dict(project)
            proof_project[".godot/cache.json"] = {"sha256": "ab" * 32, "size": 1}
            _dump(case / "retry-proof.json", {
                "first": receipt, "install_after": {"marker": {"sha256": "cd" * 32, "size": 1}},
                "install_before": {"marker": {"sha256": "cd" * 32, "size": 1}},
                "lookup_before_retry": receipt, "project_after": proof_project,
                "project_before": project, "second": receipt, "state": state,
                "state_after_second_retry": state})
            _dump(case / "project-before.json", {
                key: value for key, value in project.items() if not key.startswith("addons/")})
            _dump(case / "project-final.json", project)
            native = case / "native"
            driver = _process(case / "native-driver", "driver", 1100 + index, "ok\n")
            parse = _process(native, "parse", 1200 + index, "ok\n")
            godot = _process(native, "godot", 1300 + index, lifecycle)
            native_receipt = {"active_release": cls.old["manifest_sha256"], "parse": parse,
                              "probe_sha256": cls.old["manifest"]["files"][
                                  "payload/studio/package/installed_probe.py"]["sha256"],
                              "process": godot, "profile": profile,
                              "schema": "hh-installed-native-probe-2",
                              "version": cls.old["manifest"]["version"]}
            _dump(native / "receipt.json", native_receipt)
            cases.append({"action": action, "after_recovery": state, "before": state,
                          "disposition": disposition, "final": state,
                          "install_before_reopen_sha256": digest_bytes(raw),
                          "lookup": receipt, "name": name,
                          "native": {"driver": driver, "receipt": native_receipt},
                          "phase": phase, "retry": receipt,
                          "worker": {"cut": cut, "host_sha256": digest_file(case / "worker-host.json")}})
        for path in root.rglob("*"):
            if path.is_file() and "releases" not in path.relative_to(root).parts:
                evidence[path.relative_to(root).as_posix()] = digest_file(path)
        _dump(root / "p7.json", {
            "acceptance": False, "authority": 0, "case_group": "third", "cases": cases,
            "evidence": evidence, "native_required": True,
            "new_artifact_sha256": cls.new["archive_sha256"],
            "new_manifest_sha256": cls.new["manifest_sha256"],
            "old_artifact_sha256": cls.old["archive_sha256"],
            "old_manifest_sha256": cls.old["manifest_sha256"],
            "schema": "hh-gt10pc-p7-native-recovery-2"})
        packaged = root / "artifacts"
        packaged.mkdir()
        shutil.copyfile(cls.old_path, packaged / "old.hhpkg")
        shutil.copyfile(cls.new_path, packaged / "new.hhpkg")

    @classmethod
    def _project_ledger(cls) -> dict:
        manifest = cls.old["manifest"]["files"]
        prefix = "payload/studio/fixtures/gt09-arena/"
        # Baseline uses the unpatched release manifest. Fixture bytes match the old package.
        core = {key[len(prefix):]: value for key, value in cls.release["manifest"]["files"].items()
                if key.startswith(prefix)}
        core["owner-save.dat"] = {"sha256": digest_bytes(b"p7-owner-save\n"), "size": 14}
        addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
        addon = {"addons/hh_studio/" + key[len(addon_prefix):]: value
                 for key, value in manifest.items() if key.startswith(addon_prefix)}
        addon["addons/hh_studio/jcs_godot.gd"] = manifest["payload/studio/protocol/jcs_godot.gd"]
        addon["addons/hh_studio/owner-manual-note.txt"] = {
            "sha256": digest_bytes(b"p7 manual survives\n"), "size": len(b"p7 manual survives\n")}
        return {**core, **addon}

    def setUp(self) -> None:
        type(self)._build()
        type(self).p7_bytes = (self.root / "p7.json").read_bytes()
        self._write_addons()

    def _write_addons(self) -> None:
        members = self.old["members"]
        addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
        for name, _action, _phase, _disposition in CASES[6:]:
            destination = self.root / "cases" / name / "project" / "addons" / "hh_studio"
            if destination.exists():
                shutil.rmtree(destination)
            destination.mkdir(parents=True)
            for key, data in members.items():
                if key.startswith(addon_prefix):
                    path = destination / key[len(addon_prefix):]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            (destination / "jcs_godot.gd").write_bytes(
                members["payload/studio/protocol/jcs_godot.gd"])
            (destination / "owner-manual-note.txt").write_bytes(b"p7 manual survives\n")

    def _verify(self, group_host: dict | None = None) -> dict:
        return verify_p7(self.root, trust=self.trust, trust_sha256=self.trust_sha,
                         group="third", release=self.release, group_host=group_host)

    def _doc(self) -> dict:
        return json.loads((self.root / "p7.json").read_bytes())

    def _save(self, doc: dict) -> None:
        _dump(self.root / "p7.json", doc)

    def test_positive_with_and_without_group_host(self) -> None:
        self.assertEqual(self._verify()["status"], "P7_RAW_VERIFIED")
        self.assertEqual(self._verify({"target_pid": 7001})["cases"], 2)

    def test_missing_applicability_is_rejected(self) -> None:
        doc = self._doc()
        key = "cases/" + TARGET + "/applicability.json"
        doc["evidence"].pop(key)
        self._save(doc)
        path = self.root / key
        path.unlink()
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("applicability.json", str(caught.exception))

    def test_victim_pid_mismatch_is_rejected(self) -> None:
        doc = self._doc()
        cut_key = "cases/" + TARGET + "/cut.json"
        cut = json.loads((self.root / cut_key).read_text(encoding="utf-8"))
        cut["pid"] = 1
        _dump(self.root / cut_key, cut)
        doc["evidence"][cut_key] = digest_file(self.root / cut_key)
        doc["cases"][0]["worker"]["cut"] = cut
        self._save(doc)
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_WORKER", str(caught.exception))

    def test_tampered_before_reopen_is_rejected(self) -> None:
        doc = self._doc()
        key = "cases/" + TARGET + "/install-before-reopen.json"
        path = self.root / key
        path.write_bytes(path.read_bytes() + b" ")
        doc["evidence"][key] = digest_file(path)
        self._save(doc)
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_BEFORE_REOPEN", str(caught.exception))

    def test_last_good_release_file_tampered_is_rejected(self) -> None:
        release = self.root / "cases" / TARGET / "install" / "releases" / self.old["manifest_sha256"]
        (release / PLUGIN).write_bytes((release / PLUGIN).read_bytes() + b"\n# tampered\n")
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_LAST_GOOD_FILE", str(caught.exception))

    def test_last_good_selector_moved_is_rejected(self) -> None:
        key = "cases/" + TARGET + "/install-before-reopen.json"
        body = json.loads((self.root / key).read_bytes())
        body["active"] = self.new["manifest_sha256"]
        raw = canonical(body) + b"\n"
        (self.root / key).write_bytes(raw)
        doc = self._doc()
        doc["evidence"][key] = digest_bytes(raw)
        doc["cases"][0]["install_before_reopen_sha256"] = digest_bytes(raw)
        self._save(doc)
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_LAST_GOOD_SELECTOR", str(caught.exception))

    def test_wrong_addon_hash_is_rejected(self) -> None:
        plugin = self.root / "cases" / TARGET / "project/addons/hh_studio/plugin.gd"
        plugin.write_bytes(plugin.read_bytes() + b"\n")
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_ADDON_DISK", str(caught.exception))

    def test_second_command_row_is_rejected(self) -> None:
        name = TARGET
        path = self.root / "cases" / name / "install" / ".install.json"
        body = json.loads(path.read_bytes())
        command_id = "p7." + name
        body["commands"]["p7-duplicate"] = {"receipt": {"command_id": command_id},
                                             "request_digest": "c" * 64}
        raw = canonical(body) + b"\n"
        path.write_bytes(raw)
        state = {**body, "state_sha256": digest_bytes(raw)}
        doc = self._doc()
        install_key = path.relative_to(self.root).as_posix()
        doc["evidence"][install_key] = digest_file(path)
        row = doc["cases"][0]
        for label in ("before", "after_recovery", "final"):
            row[label] = state
        proof_path = self.root / "cases" / name / "retry-proof.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["state"] = state
        proof["state_after_second_retry"] = state
        _dump(proof_path, proof)
        doc["evidence"][proof_path.relative_to(self.root).as_posix()] = digest_file(proof_path)
        self._save(doc)
        with self.assertRaises(ValueError) as caught:
            self._verify()
        self.assertIn("P7_VERIFY_COMMAND_ROW", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
