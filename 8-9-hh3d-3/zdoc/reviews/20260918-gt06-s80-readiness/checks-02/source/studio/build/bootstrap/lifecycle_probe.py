"""GT-01 lifecycle probe using real cooperative child processes.

The probe is deliberately offline.  It creates two tiny, synthetic packages,
drives the shipped installer API, and reports observations rather than
promoting the toolchain.  Child processes are bounded and are owned by this
probe; no process enumeration or signal based liveness test is used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

HERE = Path(__file__).resolve()
PLAN_ROOT = HERE.parents[3]
INSTALL_PATH = HERE.with_name("install_toolchain.py")
VERIFY_PATH = HERE.with_name("verify_archive.py")
CASE_IDS = (
    "live_owner_guard_refusal",
    "crashed_owner_identity_cas_recovery",
    "replacement_lock_preserved",
    "manual_active_json_cas_preserved",
    "distinct_ab_activation_rollback",
)
CHILD_TIMEOUT = 10.0


def _load_installer():
    spec = importlib.util.spec_from_file_location("hh_lifecycle_installer", INSTALL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


inst = _load_installer()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _encode(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PLAN_ROOT.resolve()).as_posix()


def _source_hashes() -> dict[str, dict[str, str | int]]:
    paths = [INSTALL_PATH, VERIFY_PATH, HERE, PLAN_ROOT / "studio" / "tests" / "bootstrap" / "test_lifecycle_process.py"]
    result = {}
    for path in paths:
        data = path.read_bytes()
        result[_relative(path)] = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    return result


def _portable(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                assert "\\" not in key
            _portable(item)
    elif isinstance(value, list):
        for item in value:
            _portable(item)
    elif isinstance(value, str):
        assert not (len(value) >= 2 and value[1] == ":" and value[0].isalpha())
        assert not value.startswith(("/", "\\\\"))


def _write_json(path: Path, value) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_bytes(_encode(value))
    os.replace(temporary, path)


def _synthetic_input(base: Path, tag: str):
    """Return an archive, sums and lock accepted by the real verifier."""
    name = "Godot_v4.7.2-stable_win64_" + tag + ".zip"
    archive = base / name
    console = "Godot_v4.7.2-stable_win64_console.exe"
    gui = "Godot_v4.7.2-stable_win64.exe"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(console, ("console-" + tag).encode())
        zf.writestr(gui, ("gui-" + tag).encode())
        zf.writestr("LICENSE.txt", b"MIT")
    raw = archive.read_bytes()
    sums = base / ("SHA512-SUMS-" + tag + ".txt")
    sums.write_text(hashlib.sha512(raw).hexdigest() + "  " + name + "\n", encoding="utf-8")
    version = "4.7.2-stable"
    lock = {
        "schema": "HH-STUDIO-TOOLCHAIN-LOCK-2", "status": "CANDIDATE",
        "godot": {
            "version": version, "source_tag": version,
            "source": "https://github.com/godotengine/godot-builds/releases/tag/" + version,
            "source_commit": "a" * 40,
            "source_commit_url": "https://api.github.com/repos/godotengine/godot/git/ref/tags/" + version,
            "archive": {"name": name, "url": "https://github.com/godotengine/godot-builds/releases/download/" + version + "/" + name,
                        "sha256": hashlib.sha256(raw).hexdigest(), "sha512": hashlib.sha512(raw).hexdigest(), "size_bytes": len(raw)},
            "sha512_sums": {"url": "https://github.com/godotengine/godot-builds/releases/download/" + version + "/SHA512-SUMS.txt",
                            "sha256": _sha(sums)},
            "console_executable": console, "gui_executable": gui,
            "console_sha256": hashlib.sha256(("console-" + tag).encode()).hexdigest(),
            "gui_sha256": hashlib.sha256(("gui-" + tag).encode()).hexdigest(),
        },
    }
    lock_path = base / ("lock-" + tag + ".json")
    lock_path.write_bytes(_encode(lock))
    return archive, sums, lock_path


def _child_command(mode: str, root: Path) -> list[str]:
    return [sys.executable, "-I", str(HERE), "_child", mode, str(root)]


def _spawn(mode: str, root: Path):
    ready = root / "child-ready.json"
    control = root / "child-release"
    # The child imports the same absolute source file; its output is captured
    # only as a bounded, redacted event stream.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(_child_command(mode, root), stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=creationflags)
    try:
        deadline = time.monotonic() + CHILD_TIMEOUT
        while time.monotonic() < deadline and not ready.exists():
            if process.poll() is not None:
                break
            time.sleep(0.02)
        if not ready.exists():
            raise RuntimeError("child did not publish ready event")
        ready_data = json.loads(ready.read_text(encoding="utf-8"))
        return process, ready_data, control
    except Exception:
        _terminate_owned(process)
        raise


def _terminate_owned(process: subprocess.Popen) -> None:
    """Best-effort bounded cleanup for a process created by this probe."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _wait_owned(process: subprocess.Popen, control: Path | None = None) -> int:
    """Bound the wait and clean up a child that ignored its cooperative stop."""
    if control is not None and process.poll() is None:
        try:
            control.write_bytes(b"release\n")
        except OSError:
            pass
    try:
        return process.wait(timeout=CHILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        _terminate_owned(process)
        return process.returncode


def _child(mode: str, root: Path) -> int:
    root.mkdir(parents=True, exist_ok=True)
    try:
        with inst.lease(root):
            lock = root / ".mutation.lock"
            payload = json.loads(lock.read_text(encoding="utf-8"))
            _write_json(root / "child-ready.json", {"event": "READY", "mode": mode,
                       "pid": payload["pid"], "process_start": payload["process_start"],
                       "created_ns": payload["created_ns"], "lock_sha256": _sha(lock)})
            if mode == "crash":
                os._exit(23)
            deadline = time.monotonic() + CHILD_TIMEOUT
            while time.monotonic() < deadline and not (root / "child-release").exists():
                time.sleep(0.02)
        return 0
    except Exception:
        # Parent observes only the exit code and ready JSON, never host paths.
        return 42


def _case(case_id: str, checks: dict[str, bool], observed: dict) -> dict:
    result = {"case_id": case_id, "status": "PASS" if all(checks.values()) else "FAIL",
              "checks": checks, "observed": observed}
    result["evidence_sha256"] = hashlib.sha256(_encode({"case_id": case_id, "checks": checks, "observed": observed})).hexdigest()
    return result


def run_probe(work_root: Path, run_id: str) -> dict:
    work_root = Path(work_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    before = _source_hashes()
    cases = []

    live_root = work_root / "live-owner"
    live_root.mkdir()
    process, ready, control = _spawn("hold", live_root)
    try:
        lock = live_root / ".mutation.lock"
        token = _sha(lock)
        refused = False
        recovery_error = None
        try:
            inst.recover_lock(live_root, expected_lock=token, max_age_seconds=0)
        except inst.InstallError as exc:
            recovery_error = str(exc)
            refused = True
        owner_alive = process.poll() is None
        lock_unchanged = _sha(lock) == token
        exit_code = _wait_owned(process, control)
        cases.append(_case("live_owner_guard_refusal", {
            "recovery_refused_while_guard_held": refused, "owner_stayed_alive": owner_alive,
            "child_exited_cleanly": exit_code == 0, "lease_removed_after_release": not lock.exists()},
            {"child_pid": ready["pid"], "process_start": ready["process_start"], "lock_sha256_before": token,
             "lock_sha256_after_release": "ABSENT", "child_exit": exit_code,
             "owner_alive_during_guard": owner_alive, "lock_unchanged_during_guard": lock_unchanged,
             "recovery_error": recovery_error}))
    finally:
        if process.poll() is None:
            _wait_owned(process, control)

    crash_root = work_root / "crashed-owner"
    crash_root.mkdir()
    process, ready, _ = _spawn("crash", crash_root)
    lock = crash_root / ".mutation.lock"
    token = _sha(lock)
    exit_code = process.wait(timeout=CHILD_TIMEOUT)
    wrong = "0" * 64
    wrong_refused = False
    wrong_error = None
    try:
        inst.recover_lock(crash_root, expected_lock=wrong, max_age_seconds=0)
    except inst.InstallError as exc:
        wrong_error = str(exc)
        wrong_refused = True
    recovered = inst.recover_lock(crash_root, expected_lock=token, max_age_seconds=0)
    cases.append(_case("crashed_owner_identity_cas_recovery", {
        "child_crashed": exit_code == 23, "identity_metadata_preserved": ready["lock_sha256"] == token,
        "wrong_cas_refused": wrong_refused, "recovered_with_matching_cas": recovered["status"] == "STALE_LOCK_RECOVERED",
        "metadata_removed_after_recovery": not lock.exists()},
        {"child_pid": ready["pid"], "process_start": ready["process_start"], "lock_sha256_before": token,
         "child_exit": exit_code, "recovery_status": recovered["status"],
         "ready_lock_sha256": ready["lock_sha256"], "wrong_recovery_error": wrong_error,
         "lock_sha256_after_recovery": "ABSENT"}))

    replacement_root = work_root / "replacement-owner"
    replacement_root.mkdir()
    process, ready, control = _spawn("hold", replacement_root)
    lock = replacement_root / ".mutation.lock"
    old_token = _sha(lock)
    replacement = json.loads(lock.read_text(encoding="utf-8")); replacement["nonce"] = uuid.uuid4().hex
    _write_json(replacement_root / ".replacement", replacement)
    os.replace(replacement_root / ".replacement", lock)
    new_token = _sha(lock)
    exit_code = _wait_owned(process, control)
    cases.append(_case("replacement_lock_preserved", {
        "replacement_token_differs": old_token != new_token, "child_rejected_replacement": exit_code == 42,
        "replacement_bytes_preserved": _sha(lock) == new_token},
        {"child_pid": ready["pid"], "old_lock_sha256": old_token, "replacement_lock_sha256": new_token,
         "child_exit": exit_code, "replacement_bytes_sha256": _sha(lock)}))

    # Distinct A/B archives are installed through install(), then activated and
    # rolled back.  This root is also used to prove active-state CAS behavior.
    package_root = work_root / "packages-state"
    a = _synthetic_input(work_root, "a"); b = _synthetic_input(work_root, "b")
    ra = inst.install(*a, package_root)["receipt"]
    rb = inst.install(*b, package_root)["receipt"]
    first = inst.activate(package_root, ra, "NONE")
    second = inst.activate(package_root, rb, first["state_token"])
    before_manual = (package_root / inst.STATE).read_bytes()
    manual = json.loads(before_manual.decode()); manual["revision"] += 1
    manual["transition_id"] = uuid.uuid4().hex
    _write_json(package_root / inst.STATE, manual)
    edited_token = inst.state_token(package_root)
    stale_refused = False
    stale_error = None
    try:
        inst.activate(package_root, rb, second["state_token"])
    except inst.InstallError as exc:
        stale_error = str(exc)
        stale_refused = True
    manual_preserved = inst.state_token(package_root) == edited_token
    cases.append(_case("manual_active_json_cas_preserved", {
        "manual_edit_changed_token": edited_token != second["state_token"],
        "stale_cas_refused": stale_refused, "manual_state_preserved": manual_preserved,
        "edited_state_readable": inst.read_state(package_root, edited_token)["revision"] == manual["revision"]},
        {"state_sha256_before_edit": hashlib.sha256(before_manual).hexdigest(),
         "state_sha256_after_edit": hashlib.sha256((package_root / inst.STATE).read_bytes()).hexdigest(),
         "stale_expected_state": second["state_token"], "edited_state_token": edited_token,
         "stale_cas_error": stale_error, "state_sha256_after_stale_attempt": hashlib.sha256((package_root / inst.STATE).read_bytes()).hexdigest(),
         "edited_state_readable": inst.read_state(package_root, edited_token)["revision"] == manual["revision"]}))
    rolled = inst.rollback(package_root, edited_token, manual["transition_id"])
    cases.append(_case("distinct_ab_activation_rollback", {
        "a_and_b_distinct": ra["package"] != rb["package"], "activated_b": second["current"] == rb,
        "rollback_restored_a": rolled["current"] == ra, "rollback_postcondition_readable": inst.read_state(package_root, rolled["state_token"])["current"] == ra},
        {"package_a": ra, "package_b": rb, "activated_b_state": second["state_token"], "activated_b_current": second["current"],
         "rollback_state": rolled["state_token"], "rollback_current": rolled["current"], "rollback_readable": inst.read_state(package_root, rolled["state_token"])["current"] == ra}))

    after = _source_hashes()
    if after != before:
        raise RuntimeError("source changed during lifecycle run")
    # Persist raw observations. Verification hashes and re-reads these files;
    # case booleans are only a consistency projection, never proof.
    for case in cases:
        _write_json(work_root / ("case-" + case["case_id"] + ".json"),
                    {"schema": "HH3D-GT01-LIFECYCLE-CASE-1", "case_id": case["case_id"],
                     "observed": case["observed"]})
    logs = []
    for relative in ("live-owner/child-ready.json", "crashed-owner/child-ready.json", "replacement-owner/child-ready.json"):
        log_path = work_root / relative
        logs.append({"relative_path": relative, "sha256": _sha(log_path), "events": ["READY"]})
    report = {"schema": "HH3D-GT01-LIFECYCLE-1", "status": "CANDIDATE", "run_id": run_id,
              "source_hashes_before": before, "source_hashes_after": after,
              "cases": cases, "case_ids": list(CASE_IDS), "logs": logs,
              "limits": ["synthetic offline packages", "cooperative lock/process identity", "candidate evidence only"]}
    _portable(report)
    return report


def _parse_report(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)


def validate_report(report: dict, expected_source_hashes: dict | None = None, evidence_root: Path | None = None) -> None:
    """Validate a candidate against current source and bytes on disk."""
    if not isinstance(report, dict) or report.get("schema") != "HH3D-GT01-LIFECYCLE-1" or report.get("status") != "CANDIDATE":
        raise ValueError("report is not a candidate lifecycle record")
    if evidence_root is None:
        raise ValueError("evidence root is required")
    root = Path(evidence_root).resolve()
    if report.get("case_ids") != list(CASE_IDS) or not isinstance(report.get("cases"), list) or len(report["cases"]) != len(CASE_IDS):
        raise ValueError("missing or unexpected lifecycle case")
    current = _source_hashes()
    if report.get("source_hashes_before") != report.get("source_hashes_after") or report.get("source_hashes_after") != current:
        raise ValueError("source hash does not match current closure")
    if expected_source_hashes is not None and report["source_hashes_after"] != expected_source_hashes:
        raise ValueError("source hash does not match verifier input")
    logs = report.get("logs")
    expected_logs = ("live-owner/child-ready.json", "crashed-owner/child-ready.json", "replacement-owner/child-ready.json")
    if not isinstance(logs, list) or [x.get("relative_path") for x in logs] != list(expected_logs):
        raise ValueError("missing or non-relative child logs")
    disk_logs = {}
    for item in logs:
        rel = item.get("relative_path")
        if item.get("events") != ["READY"] or not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
            raise ValueError("invalid redacted child log")
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
            raw = path.read_bytes()
        except (OSError, ValueError):
            raise ValueError("child log unavailable")
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("child log digest does not match disk")
        value = _parse_report(path)
        if value.get("event") != "READY":
            raise ValueError("child log event mismatch")
        disk_logs[rel] = value
    seen = []
    for case in report["cases"]:
        if not isinstance(case, dict) or case.get("case_id") not in CASE_IDS or case["case_id"] in seen:
            raise ValueError("duplicate or unknown lifecycle case")
        cid = case["case_id"]; seen.append(cid)
        if case.get("status") != "PASS" or not isinstance(case.get("checks"), dict):
            raise ValueError("case did not pass observed checks")
        ep = (root / ("case-" + cid + ".json")).resolve()
        try:
            ep.relative_to(root); evidence = _parse_report(ep)
        except (OSError, ValueError):
            raise ValueError("case evidence unavailable")
        if evidence.get("schema") != "HH3D-GT01-LIFECYCLE-CASE-1" or evidence.get("case_id") != cid or evidence.get("observed") != case.get("observed"):
            raise ValueError("case observation differs from disk")
        observed = evidence["observed"]
        # Recompute every projection from captured facts; a caller-supplied
        # boolean or digest cannot turn an unobserved outcome into PASS.
        expected = dict(case["checks"])
        if cid == "live_owner_guard_refusal":
            expected.update(recovery_refused_while_guard_held=observed.get("recovery_error") in ("lock owner is still running", "mutation guard busy"), owner_stayed_alive=observed.get("owner_alive_during_guard") is True, child_exited_cleanly=observed.get("child_exit") == 0, lease_removed_after_release=observed.get("lock_sha256_after_release") == "ABSENT")
        elif cid == "replacement_lock_preserved":
            expected.update(replacement_token_differs=observed.get("old_lock_sha256") != observed.get("replacement_lock_sha256"), child_rejected_replacement=observed.get("child_exit") == 42, replacement_bytes_preserved=observed.get("replacement_bytes_sha256") == observed.get("replacement_lock_sha256"))
        elif cid == "crashed_owner_identity_cas_recovery":
            expected.update(child_crashed=observed.get("child_exit") == 23, identity_metadata_preserved=observed.get("ready_lock_sha256") == observed.get("lock_sha256_before"), wrong_cas_refused=observed.get("wrong_recovery_error") == "lock CAS mismatch", recovered_with_matching_cas=observed.get("recovery_status") == "STALE_LOCK_RECOVERED", metadata_removed_after_recovery=observed.get("lock_sha256_after_recovery") == "ABSENT")
        elif cid == "manual_active_json_cas_preserved":
            expected.update(manual_edit_changed_token=observed.get("state_sha256_before_edit") != observed.get("state_sha256_after_edit"), stale_cas_refused=observed.get("stale_cas_error") in ("active state CAS mismatch", "mutation guard busy"), manual_state_preserved=observed.get("state_sha256_after_edit") == observed.get("state_sha256_after_stale_attempt"), edited_state_readable=observed.get("edited_state_readable") is True)
        elif cid == "distinct_ab_activation_rollback":
            expected.update(a_and_b_distinct=observed.get("package_a", {}).get("package") != observed.get("package_b", {}).get("package"), activated_b=observed.get("activated_b_current") == observed.get("package_b"), rollback_restored_a=observed.get("rollback_current") == observed.get("package_a"), rollback_postcondition_readable=observed.get("rollback_readable") is True)
        if expected != case["checks"] or not all(expected.values()):
            raise ValueError("case checks are not supported by observed facts")
        digest = hashlib.sha256(_encode({"case_id": cid, "checks": case["checks"], "observed": observed})).hexdigest()
        if case.get("evidence_sha256") != digest:
            raise ValueError("case evidence digest mismatch")
    if seen != list(CASE_IDS):
        raise ValueError("case order mismatch")
    _portable(report)

def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("--work-root", type=Path, required=True); run.add_argument("--run-id", required=True); run.add_argument("--output", type=Path)
    verify = sub.add_parser("verify"); verify.add_argument("--report", type=Path, required=True); verify.add_argument("--work-root", type=Path, required=True)
    child = sub.add_parser("_child"); child.add_argument("mode", choices=("hold", "crash")); child.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    if args.command == "_child":
        return _child(args.mode, args.root)
    try:
        if args.command == "run":
            report = run_probe(args.work_root, args.run_id)
            output = args.output or (Path(args.work_root).resolve() / "report.json")
            if output.exists(): raise RuntimeError("refusing to overwrite existing report")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as handle:
                handle.write(_encode(report)); handle.flush(); os.fsync(handle.fileno())
            print(json.dumps(report, sort_keys=True, separators=(",", ":")))
            return 0
        # Recompute the closure at verification time; a report copied from a
        # prior source revision must never be promoted by its own hashes.
        report = _parse_report(args.report); validate_report(report, _source_hashes(), args.work_root)
        print(json.dumps({"status": "CANDIDATE_VERIFIED", "case_ids": list(CASE_IDS)}, separators=(",", ":")))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, AssertionError):
        print(json.dumps({"status": "REJECTED", "reason": "lifecycle evidence failed closed"}, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
