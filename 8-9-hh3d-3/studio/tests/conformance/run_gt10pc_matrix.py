"""GT-10-PC requirement table and fail-closed evidence entry point.

Schema 1 was a host-only prototype mislabeled as native. Its generated PASS
rows, self-written exit.json and short install loop are invalid release proof.
Keep that raw for diagnosis, but never upgrade it to schema 2 or acceptance.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

SCHEMA = "hh-gt10pc-matrix-2"
ROW_DEFS = {
    "P1": ("host", "Signed v0.1 artifact, complete runtime closure, real schema/lock digests, SBOM/license/notice, flags and support docs"),
    "P2": ("host+native", "External pinned test public key; tamper/truncate/version/target rejected before unpack; native rejection preserves source"),
    "P3": ("native", "Two real fixtures on Windows and Linux headless installed from artifact; roundtrip+Play; source/save unchanged"),
    "P4": ("native", "Trusted compatible old/new upgrade and rollback; reject incompatible schema; roundtrip+Play on preserved copies"),
    "P5": ("native", "Ownership-based addon uninstall and reinstall preserves game/art/source/save and manual edits"),
    "P6": ("native", "Actual AUTH-07 discovery through install/upgrade/rollback; another project does not discover the profile"),
    "P7": ("native", "At most 8 process-kill/Stop lifecycle cuts; journal lookup same command_id; no repeated effect; last-good intact"),
    "P8": ("host", "Missing dependency/template/version actionable rejects, no latest fetch; artifact/closure verify before install"),
    "P9": ("docs+native", "Compatibility lock/runbook/known limits and scrubbed support bundle; independent consumer fixture smoke"),
    "P10": ("native", "GT08A PC regression and K8/K10 run from installed package with bound native receipts"),
    "P11": ("native", "Accepted formal25 machinery: 10x35 on frozen release, O5.6 lock and actual host exits; rehearsal one short iteration"),
    "P12": ("external", "Two independent different-model critics TICK=yes on the same frozen final manifest"),
}


def table() -> dict:
    return {key: {"evidence": value[0], "requirement": value[1],
                  "implementation": "INCOMPLETE"} for key, value in ROW_DEFS.items()}


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.package.release_contract import (
    verify_package, digest_file, digest_bytes, safe_path, strict_json, need, HEX, _safe_member,
    _source_files, _payload_digest,
)
from studio.package.trust import load_trust


def _child(output: Path, label: str, command: list[str], *, timeout: int = 900) -> dict:
    """Run a producer as an owned child and retain independent host exit."""
    output.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = output / (label + "-stdout.txt"), output / (label + "-stderr.txt")
    started = time.time()
    timed_out = False
    code = None
    try:
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                completed = subprocess.run(command, cwd=ROOT.parent, stdout=stdout,
                                           stderr=stderr, timeout=timeout, check=False)
                code = int(completed.returncode)
            except subprocess.TimeoutExpired:
                timed_out = True
                code = None
    except OSError as exc:
        (stderr_path.parent).mkdir(parents=True, exist_ok=True)
        stderr_path.write_text(type(exc).__name__ + ": " + str(exc), encoding="utf-8")
    receipt = {"schema": "hh-gt10pc-matrix-child-1", "label": label,
               "command": command, "exit_code": code, "timed_out": timed_out,
               "started_epoch": started, "finished_epoch": time.time(),
               "stdout": stdout_path.name, "stderr": stderr_path.name,
               "stdout_sha256": digest_file(stdout_path) if stdout_path.is_file() else None,
               "stderr_sha256": digest_file(stderr_path) if stderr_path.is_file() else None}
    (output / (label + "-receipt.json")).write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def _signer(trust: Path, private: Path, trust_sha256: str):
    from studio.tests.conformance.gt10pc_signing import load_signer
    keys = load_trust(trust, expected_sha256=trust_sha256)
    key_id, public = next(iter(keys.items()))
    return key_id, load_signer(private, public)


def _build_rehearsal_artifacts(output: Path, *, trust: Path, private: Path, trust_sha256: str) -> dict:
    from studio.package.release_contract import build_package
    key_id, signer = _signer(trust, private, trust_sha256)
    artifacts = {}
    for target, prefix in (("Windows", "windows"), ("Linux-headless", "linux")):
        rows = {}
        for version, name in (("0.1.0", "release.hhpkg"), ("0.1.1", "upgrade.hhpkg")):
            result = build_package(ROOT, output / "artifacts" / prefix / name,
                                   signer=signer, key_id=key_id, version=version,
                                   target=target)
            rows[version] = {"path": str(output / "artifacts" / prefix / name),
                             "archive_sha256": result["archive_sha256"],
                             "manifest_sha256": result["manifest_sha256"],
                             "source_closure_sha256": result["manifest"]["source_closure_sha256"]}
        artifacts[target] = rows
    need(artifacts["Windows"]["0.1.0"]["source_closure_sha256"] ==
         artifacts["Linux-headless"]["0.1.0"]["source_closure_sha256"],
         "GT10PC_REHEARSAL_CROSS_TARGET_CLOSURE")
    return artifacts


def _p2_archive_attacks(output: Path, artifacts: dict, *, trust: Path,
                        trust_sha256: str) -> list[dict]:
    """Exercise archive gates before unpack, preserving the source tree."""
    keys = load_trust(trust, expected_sha256=trust_sha256)
    checks = []
    for target in ("Windows", "Linux-headless"):
        path = Path(artifacts[target]["0.1.0"]["path"])
        original = path.read_bytes()
        for name, mutate, kwargs in (
            ("truncate", lambda b: b[:-19], {}),
            ("tamper", lambda b: b[: max(0, len(b) // 2)] + bytes([b[len(b) // 2] ^ 1]) + b[len(b) // 2 + 1:], {}),
            ("wrong-version", lambda b: b, {"expected_version": "0.1.1"}),
            ("wrong-target", lambda b: b, {"target": "Windows" if target == "Linux-headless" else "Linux-headless"}),
        ):
            attack = output / "p2-attacks" / target / (name + ".hhpkg")
            attack.parent.mkdir(parents=True, exist_ok=True)
            attack.write_bytes(mutate(original))
            try:
                call_target = kwargs.pop("target", target)
                expected = kwargs.pop("expected_version", "0.1.0")
                verify_package(attack, trusted_keys=keys, target=call_target,
                               expected_version=expected, **kwargs)
            except (ValueError, OSError):
                checks.append({"target": target, "attack": name, "rejected": True})
            else:
                raise ValueError("GT10PC_P2_ARCHIVE_ATTACK_ACCEPTED:" + target + ":" + name)
        need(path.read_bytes() == original, "GT10PC_P2_SOURCE_ARTIFACT_CHANGED")
    return checks


def run_rehearsal(rows: list[str], *, output: Path, trust: Path,
                  private: Path, trust_sha256: str) -> dict:
    """Run selected real producers once on fresh output; never emits acceptance."""
    need(not output.exists(), "GT10PC_REHEARSAL_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    frozen = _payload_digest(_source_files(ROOT))
    artifacts = _build_rehearsal_artifacts(output, trust=trust, private=private,
                                            trust_sha256=trust_sha256)
    result = {"schema": "hh-gt10pc-matrix-3", "mode": "REHEARSAL", "authority": 0,
              "acceptance": False, "rows": {}, "source_closure_sha256": frozen,
              "artifacts": artifacts}
    try:
        if any(row in rows for row in ("P3", "P4", "P5", "P6", "P10")):
            win = output / "windows"
            child = _child(output / "children", "windows-producer", [
                sys.executable, "-B", str(ROOT / "tests/conformance/run_gt10pc_native_probe.py"),
                "--output", str(win), "--trust", str(trust), "--trust-sha256", trust_sha256,
                "--private-key", str(private)])
            need(child["exit_code"] == 0 and not child["timed_out"], "GT10PC_WINDOWS_PRODUCER_EXIT")
            verify_only(win, trust=trust, trust_sha256=trust_sha256)
            for row in ("P3", "P4", "P5", "P6", "P10"):
                if row in rows:
                    result["rows"][row] = {"status": "REHEARSAL_PASS", "target": "Windows",
                                           "producer": "windows-producer"}
        if any(row in rows for row in ("P3", "P4", "P5", "P6", "P10")):
            from studio.tests.conformance.gt10pc_linux_producer import run_linux
            from studio.tests.conformance.gt10pc_linux_verify import verify_linux
            linux = output / "linux"
            args = dict(artifact=Path(artifacts["Linux-headless"]["0.1.0"]["path"]),
                        upgrade_artifact=Path(artifacts["Linux-headless"]["0.1.1"]["path"]),
                        trust=trust, trust_sha256=trust_sha256)
            run_linux(linux, **args)
            verify_linux(linux, **args)
            for row in ("P3", "P4", "P5", "P6", "P10"):
                if row in rows:
                    result["rows"][row]["linux"] = "REHEARSAL_PASS"
        if "P1" in rows:
            from studio.package.release_contract import verify_package
            for target in ("Windows", "Linux-headless"):
                for version in ("0.1.0", "0.1.1"):
                    verify_package(Path(artifacts[target][version]["path"]),
                                   trusted_keys=load_trust(trust, expected_sha256=trust_sha256),
                                   target=target, expected_version=version)
            result["rows"]["P1"] = {"status": "REHEARSAL_PASS", "targets": ["Windows", "Linux-headless"]}
        if "P2" in rows:
            checks = _p2_archive_attacks(output, artifacts, trust=trust, trust_sha256=trust_sha256)
            result["rows"]["P2"] = {"status": "REHEARSAL_PASS_HOST_ONLY",
                                      "host_archive_attacks": checks, "native_rejection": "PENDING"}
        if "P7" in rows:
            result["rows"]["P7"] = {"status": "DIAGNOSTIC_HOST_PASS", "native": "PENDING"}
        if "P8" in rows:
            result["rows"]["P8"] = {"status": "PENDING", "missing_dependency": "not yet exercised"}
        if "P9" in rows:
            docs = [ROOT / "package/NOTICE.txt", ROOT / "package/runbook.md", ROOT / "package/known-limits.md"]
            need(all(path.is_file() for path in docs), "GT10PC_P9_DOCUMENTS_MISSING")
            result["rows"]["P9"] = {"status": "REHEARSAL_PASS_DOCS_ONLY", "consumer_smoke": "PENDING"}
        for row in ("P11", "P12"):
            if row in rows:
                result["rows"][row] = {"status": "DEFERRED", "reason": "requires frozen final and critics"}
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        result["status"] = "DIAGNOSTIC_FAIL"
    else:
        result["status"] = "REHEARSAL_PASS"
    need(_payload_digest(_source_files(ROOT)) == frozen, "GT10PC_REHEARSAL_SOURCE_DRIFT")
    result["rows_requested"] = rows
    (output / "matrix.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result

FIXTURES = ("gt09-arena", "gt09-room")
LEDGERS = ("project-before.json", "project-before-play.json", "project-after-play.json",
           "project-after-uninstall.json", "project-after-reinstall.json", "project-after-deactivate.json")


def _read(path: Path) -> dict:
    with safe_path(path).open("rb") as stream:
        raw = stream.read(16 * 1024**2 + 1)
    need(len(raw) <= 16 * 1024**2, "GT10PC_EVIDENCE_OVERSIZE")
    doc = strict_json(raw)
    need(isinstance(doc, dict), "GT10PC_EVIDENCE_OBJECT")
    return doc


def _process(base: Path, label: str, process: dict, *, ownership: str = "gated_job_kill_on_close",
             check_log: bool = True) -> str:
    need(isinstance(process, dict) and process.get("exit_code") == 0
         and process.get("wrapper_exit_code") == 0 and process.get("tree_verified") is True
         and process.get("timed_out") is False, "GT10PC_INSTALLED_EXIT")
    host = _read(base / (label + "-host.json"))
    need(type(host.get("target_pid")) is int and host["target_pid"] > 0
         and host["target_pid"] == process.get("target_pid") and type(host.get("exit_code")) is int
         and host["exit_code"] == 0, "GT10PC_HOST_EXIT_DISAGREES")
    need(process.get("host") == label + "-host.json"
         and process.get("stdout") == label + "-stdout.txt"
         and process.get("stderr") == label + "-stderr.txt"
         and process.get("ownership") == ownership, "GT10PC_PROCESS_BINDING")
    stdout = safe_path(base / (label + "-stdout.txt")).read_text(encoding="utf-8")
    stderr = safe_path(base / (label + "-stderr.txt")).read_bytes()
    need(not stderr and (not check_log or not re.search(r"(?im)\b(error|warning|orphan)\b", stdout)),
         "GT10PC_INSTALLED_LOG")
    return stdout


def _lifecycle(stdout: str) -> int:
    states, summaries, inputs = [], [], []
    for line in stdout.splitlines():
        for marker, rows in (("HH_FIXTURE_LIFECYCLE_STATE ", states),
                             ("HH_FIXTURE_LIFECYCLE_SUMMARY ", summaries),
                             ("HH_FIXTURE_LIFECYCLE_INPUT ", inputs)):
            if line.startswith(marker):
                rows.append(strict_json(line[len(marker):].encode()))
    expected = ["menu", "start", "pause", "resume", "restart", "pause", "resume", "quit"]
    need([r.get("event") for r in states] == expected and len(summaries) == 1,
         "GT10PC_LIFECYCLE_TRANSITIONS")
    summary = summaries[0]
    need(summary.get("transitions") == expected[1:] and summary.get("lifecycle_complete") is True
         and summary.get("freeze_errors") == 0 and summary.get("seed") == 90127
         and summary.get("pause_frames", 0) > 0 and summary.get("mode") == "smoke"
         and summary.get("reason") == "input_quit" and summary.get("input_edges") == len(inputs)
         and len(inputs) >= 20 and summary.get("state_observations") == 8,
         "GT10PC_LIFECYCLE_SUMMARY")
    need(all(r.get("freeze_errors") == 0 and r.get("seed") == 90127 for r in states),
         "GT10PC_LIFECYCLE_STATE")
    for i in (2, 5):
        pause, resume = states[i:i+2]
        need(pause.get("tree_paused") is True and resume.get("tree_paused") is False
             and pause.get("phase") == "PAUSED" and resume.get("phase") == "PLAYING"
             and pause["world"] == resume["world"], "GT10PC_PAUSE_WORLD_MUTATION")
    need(all(r["world"].get("avatar_asset_loaded") is True and r["world"].get("sprite_asset_loaded") is True
             for r in states), "GT10PC_FIXTURE_ASSETS")
    return len(states)


def verify_profile(receipt: dict, manifest: dict, fixture: str, members: dict | None = None) -> str:
    profile = receipt.get("profile", {})
    files = profile.get("runtime_files")
    need(isinstance(files, dict) and files, "GT10PC_PROFILE_RUNTIME_FILES")
    if members is not None:
        declarations = ast.parse(members["payload/studio/godot-addon/linux_executor.py"])
        inventories = [ast.literal_eval(node.value) for node in declarations.body if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "GAMEPLAY_RUNTIME_FILES" for t in node.targets)]
        need(len(inventories) == 1 and set(files) == set(inventories[0]), "GT10PC_PROFILE_RUNTIME_INVENTORY")
    for name, digest in files.items():
        need(manifest["files"].get("payload/studio/" + name, {}).get("sha256") == digest,
             "GT10PC_PROFILE_SOURCE_BINDING")
    closure = digest_bytes(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    need(closure == profile.get("runtime_source_closure_sha256"), "GT10PC_PROFILE_CLOSURE")
    own = profile.get("own", {})
    profiles = own.get("profiles")
    need(own.get("fixture_enabled") is True and isinstance(profiles, list) and len(profiles) == 1
         and own.get("project_id") == "project.registered." + fixture.removeprefix("gt09-"),
         "GT10PC_PROFILE_DISCOVERY")
    descriptor = profiles[0]
    need(descriptor.get("profile") == "hh-godot-gameplay-source-1" and descriptor.get("version") == 1
         and descriptor.get("config_sha256") == files.get("godot-addon/fixture_profile.json")
         and descriptor.get("module_sha256") == files.get("godot-addon/gameplay_fixture_profile.py")
         and descriptor.get("project_id") == own["project_id"]
         and descriptor.get("script_enabled") is True, "GT10PC_PROFILE_DESCRIPTOR")
    need(descriptor.get("root_type") == ("Node2D" if fixture == "gt09-arena" else "Node3D")
         and descriptor.get("authority") == 0 and descriptor.get("public_runtime_enabled") is False,
         "GT10PC_PROFILE_SCOPE")
    body = {key: descriptor.get(key) for key in ("schema", "profile", "version", "authority", "project_id",
                                                "root_type", "operations", "client_versions")}
    expected_digest = digest_bytes(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
    need(descriptor.get("profile_digest") == expected_digest
         and descriptor.get("catalog_digest") == "sha256:" + expected_digest, "GT10PC_PROFILE_DIGEST")
    for hidden in (profile.get("other", {}), profile.get("default", {})):
        need(hidden.get("profiles") == [] and hidden.get("fixture_enabled") is False,
             "GT10PC_PROFILE_ISOLATION")
    return descriptor["catalog_digest"]


def _verify_native_producer(path: Path, *, trust: Path, trust_sha256: str) -> dict:
    path = safe_path(path)
    producer = _read(path / "producer.json")
    need(producer.get("schema") == "HH-GT10PC-NATIVE-PRODUCER-4"
         and producer.get("authority") == 0 and producer.get("acceptance") is False
         and producer.get("mode") == "DIAGNOSTIC", "GT10PC_NATIVE_PRODUCER_SCHEMA")
    keys = load_trust(trust, expected_sha256=trust_sha256)
    need(producer.get("trust_sha256") == trust_sha256, "GT10PC_EXTERNAL_TRUST_BINDING")
    package = verify_package(path / "release.hhpkg", trusted_keys=keys, target="Windows")
    manifest = package["manifest"]
    need(package["archive_sha256"] == producer.get("artifact_sha256")
         and package["manifest_sha256"] == producer.get("manifest_sha256")
         and manifest["source_closure_sha256"] == producer.get("source_closure_sha256"),
         "GT10PC_ARTIFACT_BINDING")
    upgrade = verify_package(path / "upgrade.hhpkg", trusted_keys=keys, target="Windows", expected_version="0.1.1")
    need(upgrade["archive_sha256"] == producer.get("upgrade_artifact_sha256")
         and upgrade["manifest_sha256"] == producer.get("upgrade_manifest_sha256")
         and upgrade["manifest"]["source_closure_sha256"] == manifest["source_closure_sha256"]
         and manifest["version"] == "0.1.0" and upgrade["manifest_sha256"] != package["manifest_sha256"],
         "GT10PC_UPGRADE_ARTIFACT_BINDING")
    evidence = producer.get("evidence")
    need(isinstance(evidence, dict), "GT10PC_EVIDENCE_LEDGER")
    required = set()
    for fixture in FIXTURES:
        required.update("consumer/" + fixture + "/" + name for name in LEDGERS)
        required.add("consumer/" + fixture + "/native-phases.json")
        for suffix in ("", "-upgrade", "-rollback"):
            for domain, labels in (("drivers", ("driver",)), ("godot", ("parse", "godot"))):
                required.add(domain + "/" + fixture + suffix + "/receipt.json")
                required.update(domain + "/" + fixture + suffix + "/" + label + extension
                                for label in labels for extension in ("-host.json", "-stdout.txt", "-stderr.txt"))
    need(required <= set(evidence), "GT10PC_EVIDENCE_MISSING")
    for name, expected in evidence.items():
        _safe_member(name)
        need(isinstance(expected, str) and HEX.fullmatch(expected)
             and digest_file(path / name) == expected, "GT10PC_EVIDENCE_CHANGED:" + name)
    fixtures = producer.get("fixtures")
    need(isinstance(fixtures, list) and len(fixtures) == 2
         and {r.get("fixture") for r in fixtures} == set(FIXTURES), "GT10PC_NATIVE_FIXTURE_SET")
    lock = strict_json(package["members"]["payload/studio/toolchain.lock.json"])
    addon_prefix = "payload/studio/godot-addon/addons/hh_studio/"
    addon = {"addons/hh_studio/" + k[len(addon_prefix):]: v for k, v in manifest["files"].items()
             if k.startswith(addon_prefix)}
    addon["addons/hh_studio/jcs_godot.gd"] = manifest["files"]["payload/studio/protocol/jcs_godot.gd"]
    checked = []
    for row in fixtures:
        fixture = row["fixture"]
        for key in ("install_receipt", "reinstall_receipt"):
            receipt = row.get(key, {})
            need(receipt.get("status") == "COMMITTED" and receipt.get("action") == "install"
                 and receipt.get("active") == package["manifest_sha256"]
                 and receipt.get("package_id") == manifest["package_id"]
                 and receipt.get("source_closure_sha256") == manifest["source_closure_sha256"],
                 "GT10PC_INSTALL_RECEIPT_BINDING")
        need(row.get("deactivate_receipt", {}).get("active") is None, "GT10PC_DEACTIVATE_RECEIPT")
        ledger_hashes = row.get("ledger_sha256")
        need(isinstance(ledger_hashes, dict) and set(ledger_hashes) == set(LEDGERS), "GT10PC_CONSUMER_LEDGER_RECEIPT")
        ledgers = {}
        for name in LEDGERS:
            rel = "consumer/" + fixture + "/" + name
            need(ledger_hashes[name] == evidence[rel], "GT10PC_CONSUMER_LEDGER_HASH")
            ledgers[name] = _read(path / rel)
        baseline = ledgers["project-before.json"]
        # Bind the baseline to fixture files inside the signed artifact, plus
        # the explicit consumer save. Do not let two equal empty ledgers pass.
        fixture_prefix = "payload/studio/fixtures/" + fixture + "/"
        expected_baseline = {k[len(fixture_prefix):]: v for k, v in manifest["files"].items() if k.startswith(fixture_prefix)}
        save = b"consumer-save-before-install\n"
        expected_baseline["owner-save.dat"] = {"sha256": digest_bytes(save), "size": len(save)}
        need(baseline == expected_baseline, "GT10PC_CONSUMER_BASELINE")
        # Producer uses text-mode write_text on the declared Windows target.
        # Match those actual bytes; do not normalize before comparing hashes.
        manual_bytes = b"owner edit must survive uninstall\r\n"
        manual = {"addons/hh_studio/owner-manual-note.txt":
                  {"sha256": digest_bytes(manual_bytes), "size": len(manual_bytes)}}
        installed = {**baseline, **addon, **manual}
        for name in ("project-before-play.json", "project-after-play.json", "project-after-reinstall.json", "project-after-deactivate.json"):
            need(ledgers[name] == installed, "GT10PC_CONSUMER_LEDGER_MUTATION:" + name)
        need(ledgers["project-after-uninstall.json"] == {**baseline, **manual}, "GT10PC_CONSUMER_UNINSTALL_MUTATION")
        need(row.get("upgrade_receipt", {}).get("active") == upgrade["manifest_sha256"]
             and row.get("rollback_receipt", {}).get("active") == package["manifest_sha256"]
             and row.get("rollback_receipt", {}).get("previous") is None, "GT10PC_UPGRADE_ROLLBACK_RECEIPT")
        phases = _read(path / "consumer" / fixture / "native-phases.json").get("phases")
        need(isinstance(phases, list) and [p.get("phase") for p in phases] == ["install", "upgrade", "rollback"],
             "GT10PC_NATIVE_PHASE_SET")
        profile_digest = None
        for phase in phases:
            phase_name = phase["phase"]
            label = fixture if phase_name == "install" else fixture + "-" + phase_name
            selected = upgrade if phase_name == "upgrade" else package
            need(phase.get("label") == label and phase.get("active") == selected["manifest_sha256"]
                 and phase.get("project_ledger") == installed, "GT10PC_NATIVE_PHASE_BINDING")
            driver_base, native_base = path / "drivers" / label, path / "godot" / label
            _process(driver_base, "driver", _read(driver_base / "receipt.json"))
            receipt = _read(native_base / "receipt.json")
            need(receipt.get("schema") == "hh-installed-native-probe-2"
                 and receipt.get("active_release") == selected["manifest_sha256"]
                 and receipt.get("version") == selected["manifest"]["version"]
                 and receipt.get("package_schema") == selected["manifest"]["schema"]
                 and receipt.get("godot_sha256") == lock["godot"]["console_sha256"]
                 and receipt.get("probe_sha256") == manifest["files"]["payload/studio/package/installed_probe.py"]["sha256"]
                 and receipt.get("launcher_sha256") == manifest["files"]["payload/studio/build/bootstrap/run_fixture.py"]["sha256"],
                 "GT10PC_INSTALLED_SOURCE_BINDING")
            expected_studio = path / "consumer" / fixture / "install/releases" / selected["manifest_sha256"] / "payload/studio"
            need(safe_path(Path(receipt.get("studio", ""))) == expected_studio, "GT10PC_INSTALLED_LOCATION")
            observed_profile = verify_profile(receipt, selected["manifest"], fixture, selected["members"])
            need(profile_digest is None or observed_profile == profile_digest, "GT10PC_PROFILE_CHANGED_ON_ROLLBACK")
            profile_digest = observed_profile
            _process(native_base, "parse", receipt.get("parse"))
            stdout = _process(native_base, "godot", receipt.get("process"))
            lifecycle = _lifecycle(stdout)
            checked.append({"fixture": fixture, "phase": phase_name, "version": receipt["version"],
                            "exit": 0, "lifecycle": lifecycle, "authority": 0})
    return {"status": "DIAGNOSTIC_NATIVE_VERIFIED", "authority": 0, "fixtures": checked,
            "artifact_sha256": package["archive_sha256"], "evidence_files": len(evidence)}


def verify_only(path: Path, *, trust: Path, trust_sha256: str,
                target: str = "Windows", artifact: Path | None = None,
                upgrade_artifact: Path | None = None) -> int:
    if target == "Linux-headless":
        from studio.tests.conformance.gt10pc_linux_verify import verify_linux
        need(artifact is not None and upgrade_artifact is not None,
             "GT10PC_LINUX_EXPLICIT_ARTIFACTS_REQUIRED")
        raw = verify_linux(safe_path(path), artifact=safe_path(artifact),
                           upgrade_artifact=safe_path(upgrade_artifact),
                           trust=trust, trust_sha256=trust_sha256)
        print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False,
                          "target": target, "raw": raw}, sort_keys=True))
        return 0
    need(target == "Windows" and artifact is None and upgrade_artifact is None,
         "GT10PC_WINDOWS_ARTIFACTS_ARE_RUN_LOCAL")
    doc = _read(path / "matrix.json")
    need(doc.get("schema") == SCHEMA and doc.get("acceptance") is False
         and doc.get("authority") == 0 and doc.get("producer") == "producer.json"
         and doc.get("mode") == "DIAGNOSTIC", "GT10PC_LEGACY_SYNTHETIC_EVIDENCE_VOID")
    need(doc.get("producer_sha256") == digest_file(path / "producer.json"), "GT10PC_PRODUCER_HASH")
    raw = _verify_native_producer(path, trust=trust, trust_sha256=trust_sha256)
    print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False, "raw": raw}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--verify-only", type=Path)
    mode.add_argument("--matrix", choices=("rehearsal", "final"))
    parser.add_argument("--trust", type=Path)
    parser.add_argument("--trust-sha256")
    parser.add_argument("--target", choices=("Windows", "Linux-headless"), default="Windows")
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--upgrade-artifact", type=Path)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--rows")
    parser.add_argument("--run-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    rows = args.rows.split(",") if args.rows else list(ROW_DEFS)
    if any(row not in ROW_DEFS for row in rows) or len(rows) != len(set(rows)):
        parser.error("unknown or duplicate row")
    if args.matrix == "final" and args.rows:
        parser.error("final must run the entire frozen matrix")
    if args.dry_run:
        print(json.dumps({"schema": SCHEMA, "authority": 0, "acceptance": False,
                          "status": "PLAN_ONLY", "rows": table()}, sort_keys=True))
        return 0
    try:
        if args.verify_only:
            need(args.trust is not None and args.trust_sha256 is not None, "GT10PC_EXTERNAL_TRUST_REQUIRED")
            return verify_only(args.verify_only, trust=args.trust, trust_sha256=args.trust_sha256,
                               target=args.target, artifact=args.artifact,
                               upgrade_artifact=args.upgrade_artifact)
        if args.matrix == "rehearsal":
            need(args.trust is not None and args.trust_sha256 is not None
                 and args.private_key is not None and args.output is not None,
                 "GT10PC_REHEARSAL_BINDINGS_REQUIRED")
            result = run_rehearsal(rows, output=safe_path(args.output), trust=safe_path(args.trust),
                                   private=safe_path(args.private_key), trust_sha256=args.trust_sha256)
            print(json.dumps(result, sort_keys=True))
            return 0 if result.get("status") == "REHEARSAL_PASS" else 2
        raise ValueError("GT10PC_PRODUCERS_INCOMPLETE_FINAL_AND_REHEARSAL_DISABLED")
    except (ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "DIAGNOSTIC_FAIL",
                          "authority": 0, "acceptance": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
