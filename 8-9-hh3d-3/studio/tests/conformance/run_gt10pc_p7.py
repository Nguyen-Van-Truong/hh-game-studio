"""GT-10-PC P7 process-crash and Stop recovery producer/verifier.

This is a bounded diagnostic producer.  Every case is a fresh consumer copy
with a trusted old release and a distinct signed new release.  The crash
worker parks immediately after the named filesystem phase; the parent either
kills that exact child PID or records an external Stop receipt and unparks it.
The producer then reopens the installer, checks recovery/readback, retries the
same command id, and optionally runs the installed Godot probe.  It never
turns these rows into release acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT))
from studio.build.bootstrap.run_fixture import run_process, _job_for_process, _job_active_count, _close_job, _terminate_job
from studio.package.consumer_install import ConsumerInstall
from studio.package.release_contract import (
    build_package, canonical, digest_bytes, digest_file, need, safe_path,
)
from studio.package.trust import load_trust
from studio.tests.conformance.gt10pc_signing import load_signer
from studio.tests.conformance.run_gt10pc_native_probe import project_ledger

WORKER = ROOT / "tests/conformance/gt10pc_lifecycle_crash_worker.py"
GODOT_WINDOWS = ROOT / ".local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe"

CASES = (
    ("install-release-renamed", "install", "release-renamed", "kill"),
    ("install-stop-staged", "install", "staged", "stop"),
    ("upgrade-selector-before-addon-intent", "upgrade", "selector-before-addon-intent", "kill"),
    ("upgrade-stop-addon-intent", "upgrade", "addon-intent", "stop"),
    ("upgrade-old-addon-moved", "upgrade", "old-addon-moved", "kill"),
    ("rollback-new-addon-moved", "rollback", "new-addon-moved", "kill"),
    ("rollback-stop-before-selector", "rollback", "before-selector", "stop"),
    ("rollback-journal-published", "rollback", "journal-published", "kill"),
)


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def ledger(root: Path) -> dict:
    result = {}
    if not root.exists():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(dirs)
        for name in sorted(files):
            path = safe_path(Path(directory) / name)
            result[path.relative_to(root).as_posix()] = {
                "sha256": digest_file(path), "size": path.stat().st_size,
            }
    return result


def state_digest(state: dict) -> str:
    body = {key: value for key, value in state.items() if key != "state_sha256"}
    return digest_bytes(canonical(body) + b"\n")


def variant_source(tag: str, parent: Path) -> Path:
    """Make a disposable source closure with one signed addon marker byte."""
    target = parent / ("source-" + tag)
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(
        ".local", ".godot", ".git", "__pycache__", "*.pyc", ".pytest_cache"))
    plugin = target / "godot-addon/addons/hh_studio/plugin.gd"
    plugin.write_bytes(plugin.read_bytes() + ("\n# GT10PC_P7_VARIANT=" + tag + "\n").encode())
    binding_path = target / "host/replay/execution-source.json"
    binding = json.loads(binding_path.read_bytes())
    key = "godot-addon/addons/hh_studio/plugin.gd"
    binding["source_files"][key] = digest_file(plugin)
    binding_path.write_bytes(canonical(binding) + b"\n")
    selector_path = target / "host/replay/execution-current.json"
    selector = json.loads(selector_path.read_bytes())
    selector["binding_sha256"] = digest_file(binding_path)
    selector_path.write_bytes(canonical(selector) + b"\n")
    return target


def make_packages(output: Path, *, trust: Path, private: Path,
                  trust_sha256: str) -> tuple[dict, dict, dict[str, bytes]]:
    keys = load_trust(trust, expected_sha256=trust_sha256)
    key_id, public = next(iter(keys.items()))
    signer = load_signer(private, public)
    with tempfile.TemporaryDirectory(prefix="hh-gt10pc-p7-source-") as td:
        parent = Path(td)
        old_source = variant_source("old", parent)
        new_source = variant_source("new", parent)
        old = build_package(old_source, output / "old.hhpkg", signer=signer,
                            key_id=key_id, version="0.1.0", target="Windows")
        new = build_package(new_source, output / "new.hhpkg", signer=signer,
                            key_id=key_id, version="0.1.1", target="Windows")
    need(old["manifest_sha256"] != new["manifest_sha256"], "P7_RELEASE_IDENTITIES_EQUAL")
    need(old["manifest"]["source_closure_sha256"] != new["manifest"]["source_closure_sha256"],
         "P7_SOURCE_CLOSURES_EQUAL")
    return old, new, keys


def seed_case(case: Path, old_path: Path, new_path: Path, *, keys: dict[str, bytes],
              action: str) -> tuple[ConsumerInstall, Path, dict, dict, str]:
    project = case / "project"
    shutil.copytree(ROOT / "fixtures/gt09-arena", project,
                    ignore=shutil.ignore_patterns(".godot", "__pycache__"))
    (project / "owner-save.dat").write_bytes(b"p7-owner-save\n")
    installer = ConsumerInstall(case / "install", trusted_keys=keys, target="Windows")
    old_receipt = installer.install(old_path, command_id="seed-old",
                                    expected_state_sha256="ABSENT")
    installer.install_addon(project, release=old_receipt["active"], command_id="seed-old-addon",
                            expected_state_sha256=installer.snapshot()["state_sha256"])
    manual = project / "addons/hh_studio/owner-manual-note.txt"
    manual.write_bytes(b"p7 manual survives\n")
    if action == "rollback":
        new_receipt = installer.install(new_path, command_id="seed-new",
                                        expected_state_sha256=installer.snapshot()["state_sha256"])
        installer.install_addon(project, release=new_receipt["active"], repair=True,
                                command_id="seed-new-addon",
                                expected_state_sha256=installer.snapshot()["state_sha256"])
    before = installer.snapshot()
    return installer, project, before, ledger(project), old_receipt["active"]


def launch_worker(request: Path, marker: Path, *, disposition: str,
                  installer_root: Path, output: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen([sys.executable, "-B", str(WORKER), str(request)],
                               cwd=REPO_ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    job = _job_for_process(process) if os.name == "nt" else None
    started = time.time()
    stop = None
    tree_verified = False
    try:
        deadline = time.monotonic() + 90
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        need(marker.exists(), "P7_CUT_MARKER_TIMEOUT")
        cut = json.loads(marker.read_bytes())
        need(cut.get("pid") == process.pid and process.poll() is None, "P7_CUT_PID_MISMATCH")
        if disposition == "kill":
            process.kill()
            code = process.wait(timeout=20)
            need(code != 0, "P7_KILLED_WORKER_EXITED_ZERO")
        else:
            stop = ConsumerInstall.stop_existing(installer_root, command_id="stop." + cut["action"] + "." + cut["phase"])
            need(stop.get("durable") is True and stop.get("stopped") is True,
                 "P7_STOP_NOT_DURABLE")
            write_new(output / "external-stop.json", stop)
            Path(request.parent / (marker.stem + ".unpark")).write_bytes(b"go\n")
            code = process.wait(timeout=90)
            need(code == 0, "P7_STOP_WORKER_EXIT")
        stdout, stderr = process.communicate()
        (output / "worker-stdout.txt").write_bytes(stdout)
        (output / "worker-stderr.txt").write_bytes(stderr)
        need(not stderr, "P7_WORKER_STDERR")
        # Windows can report the terminated worker in the job briefly after
        # wait() returns, especially when the producer itself is in a gated
        # outer job.  Poll the independent job count for a bounded interval;
        # a non-zero count still fails closed and is never treated as proof.
        tree_verified = False
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            tree_verified = (_job_active_count(job) == 0 if job
                             else process.poll() is not None)
            if tree_verified:
                break
            time.sleep(0.02)
        need(tree_verified, "P7_WORKER_TREE_NOT_ZERO")
        host = {"schema": "hh-gt10pc-p7-worker-host-1", "pid": process.pid,
                "actual_exit": code, "started_epoch": started, "finished_epoch": time.time(),
                "tree_verified": tree_verified, "disposition": disposition,
                "stdout_sha256": digest_bytes(stdout), "stderr_sha256": digest_bytes(stderr)}
        write_new(output / "worker-host.json", host)
        return {"disposition": disposition, "pid": process.pid, "exit_code": code,
                "cut": cut, "stop": stop, "host_sha256": digest_file(output / "worker-host.json")}
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=20)
        if job and not tree_verified:
            _terminate_job(job)
        _close_job(job)


def native_probe(case: Path, installer: ConsumerInstall, project: Path, *, godot: Path,
                 trust: Path, trust_sha256: str, fixture: str) -> dict:
    native = case / "native"
    driver = case / "native-driver"
    driver.mkdir(parents=True)
    env = os.environ.copy()
    active_parent = installer.active_path().parent
    need(active_parent.is_dir() and project.is_dir(), "P7_NATIVE_WORKDIR_MISSING")
    env["PYTHONPATH"] = str(active_parent)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-B", "-m", "studio.package.installed_probe",
               "--install-root", str(installer.root), "--project", str(project),
               "--godot", str(godot), "--output", str(native), "--fixture", fixture,
               "--target", "Windows", "--trust", str(trust), "--trust-sha256", trust_sha256]
    # Run from the consumer project, whose path is stable across lifecycle
    # recovery.  The installed payload remains the imported module via the
    # explicit PYTHONPATH binding; using the mutable release parent as cwd can
    # produce WinError 267 when this producer is nested in a gated job.
    process = run_process(command, cwd=project, output=driver,
                          timeout=100, label="driver", env=env)
    need(process["exit_code"] == 0 and process["wrapper_exit_code"] == 0
         and process["tree_verified"] is True and process["timed_out"] is False,
         "P7_NATIVE_DRIVER_EXIT")
    receipt = json.loads((native / "receipt.json").read_bytes())
    for name in ("parse", "process"):
        row = receipt[name]
        need(row["exit_code"] == 0 and row["wrapper_exit_code"] == 0
             and row["tree_verified"] is True and row["timed_out"] is False,
             "P7_NATIVE_" + name.upper() + "_EXIT")
    return {"driver": process, "receipt": receipt,
            "evidence": {str(path.relative_to(case)): digest_file(path)
                         for path in (*driver.glob("*"), *native.glob("*")) if path.is_file()}}


def run_case(root: Path, old: dict, new: dict, keys: dict[str, bytes], *, name: str,
             action: str, phase: str, disposition: str, old_path: Path, new_path: Path,
             trust: Path, trust_sha256: str, godot: Path | None) -> dict:
    case = root / "cases" / name
    case.mkdir(parents=True)
    installer, project, before, project_before, old_id = seed_case(
        case, old_path, new_path, keys=keys, action=action)
    project_core_before = {name: row for name, row in project_before.items()
                           if not name.startswith("addons/hh_studio/")}
    manual_path = project / "addons/hh_studio/owner-manual-note.txt"
    manual_bytes = manual_path.read_bytes()
    selected = old_id if action == "rollback" else installer.snapshot()["active"]
    if action == "rollback":
        selected = old_id
    command_id = "p7." + name
    state = installer.snapshot()["state_sha256"]
    marker = case / "cut.json"
    request = {
        "install": str(installer.root), "project": str(project), "package": str(new_path),
        "destination": selected, "command_id": command_id, "state": state,
        "phase": phase, "action": "rollback" if action == "rollback" else "install",
        "disposition": disposition, "marker": str(marker), "unpark": str(case / "cut.unpark"),
        "key_id": next(iter(keys)), "public_key": next(iter(keys.values())).hex(),
        "park_seconds": 90,
    }
    if action == "rollback":
        # Rollback must target the old release while new is active.
        request["package"] = str(old_path)
    write_new(case / "request.json", request)
    worker = launch_worker(case / "request.json", marker, disposition=disposition,
                           installer_root=installer.root, output=case)
    recovered = ConsumerInstall(installer.root, trusted_keys=keys, target="Windows")
    after = recovered.snapshot()
    project_after = ledger(project)
    # Cuts before the final selector publish are intentionally non-terminal:
    # the durable lifecycle WAL (or terminal command row for Stop) is the
    # recovery boundary.  A release rename or addon directory move alone must
    # therefore have no lookup yet; later cuts must retain one.
    lookup_before_retry = recovered.lookup(command_id)
    # Before the lifecycle WAL exists, a killed worker has no command lookup;
    # once that WAL is durable, reopening the installer completes it before
    # returning, even when the selector/addon directory cut itself was hit.
    early_cut = disposition == "kill" and phase in {
        "staged", "before-selector", "release-renamed"
    }
    need((lookup_before_retry is None) == early_cut,
         "P7_LOOKUP_BOUNDARY:" + name)
    retry_token = after["state_sha256"]
    if action == "rollback":
        retry = recovered.rollback_lifecycle(project, destination=selected,
                                             command_id=command_id, expected_state_sha256=retry_token)
    else:
        retry = recovered.install_lifecycle(project, new_path, command_id=command_id,
                                            expected_state_sha256=retry_token)
    lookup = recovered.lookup(command_id)
    need(lookup is not None and retry == lookup,
         "P7_RETRY_RECEIPT_DIFFERENT:" + name)
    revision_after_retry = recovered.snapshot()["revision"]
    expected_revision = after["revision"] + (1 if lookup_before_retry is None else 0)
    need(revision_after_retry == expected_revision, "P7_RETRY_EFFECT_DUPLICATED:" + name)
    if disposition == "stop":
        recovered.resume(command_id="resume." + name)
    project_core_after = {name: row for name, row in ledger(project).items()
                          if not name.startswith("addons/hh_studio/")}
    need(project_core_after == project_core_before and
         manual_path.is_file() and manual_path.read_bytes() == manual_bytes,
         "P7_PROJECT_SOURCE_SAVE_CHANGED:" + name)
    final_state = recovered.snapshot()
    need(state_digest(final_state) == final_state["state_sha256"], "P7_STATE_HASH:" + name)
    native = None
    if godot is not None:
        native = native_probe(case, recovered, project, godot=godot, trust=trust,
                              trust_sha256=trust_sha256, fixture="gt09-arena")
    return {"name": name, "action": action, "phase": phase, "disposition": disposition,
            "worker": worker, "before": before, "after_recovery": after,
            "final": final_state, "lookup": lookup, "retry": retry,
            "project_ledger_sha256": digest_bytes(canonical(project_after)), "native": native}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--trust-sha256", required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--godot", type=Path)
    args = parser.parse_args(argv)
    need(os.name == "nt", "P7_WINDOWS_NATIVE_HOST_REQUIRED")
    output = safe_path(args.output)
    need(not output.exists(), "P7_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    old, new, keys = make_packages(output / "artifacts", trust=safe_path(args.trust),
                                   private=safe_path(args.private_key), trust_sha256=args.trust_sha256)
    old_path, new_path = output / "old.hhpkg", output / "new.hhpkg"
    # build_package emitted into artifacts; make the package paths explicit in
    # the request and leave the signed bytes immutable.
    old_path = output / "artifacts/old.hhpkg"
    new_path = output / "artifacts/new.hhpkg"
    if args.godot is not None:
        need(safe_path(args.godot).is_file(), "P7_GODOT_PIN_REQUIRED")
    rows = []
    for name, action, phase, disposition in CASES:
        rows.append(run_case(output, old, new, keys, name=name, action=action,
                             phase=phase, disposition=disposition, old_path=old_path,
                             new_path=new_path, trust=safe_path(args.trust),
                             trust_sha256=args.trust_sha256,
                             godot=safe_path(args.godot) if args.godot else None))
    report = {"schema": "hh-gt10pc-p7-native-recovery-1", "authority": 0,
              "acceptance": False, "cases": rows,
              "old_artifact_sha256": digest_file(old_path),
              "new_artifact_sha256": digest_file(new_path),
              "old_manifest_sha256": old["manifest_sha256"],
              "new_manifest_sha256": new["manifest_sha256"],
              "native_required": args.godot is not None}
    write_new(output / "p7.json", report)
    print(json.dumps({"status": "P7_DIAGNOSTIC_PASS", "authority": 0,
                      "acceptance": False, "cases": len(rows),
                      "native": args.godot is not None}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
