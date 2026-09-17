"""Frozen owned-GUI proof of the private absolute-deadline IPC component.

This is an internal fixture lease, not a public writer grant or GT04 acceptance.
Run only in the coordinator's native integration slot after source writers stop.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from run_blender_ipc_probe import load, sources
from run_client_ledger_probe import cleanup_passed, host_artifact_passed, safe_failure, write_json

UNIT_INVENTORY = "GT04_DEADLINE_UNIT_INVENTORY "
UNIT_COMPLETE = "GT04_DEADLINE_UNIT_COMPLETE "
NATIVE_COMPLETE = "GT04_DEADLINE_NATIVE_COMPLETE "
CHECK_MARKER = "GT04_DEADLINE_CHECK "
REPORT = "absolute-deadline-native.json"
REQUIRED_CHECKS = frozenset({
    "actual_owned_gui_and_job", "initial_empty_scene", "exact_native_fixture_lease_armed",
    "expired_create_sent_and_bounded_rejected", "expired_create_has_no_queue_row",
    "null_deadline_sent_and_bounded_rejected", "null_deadline_has_no_queue_row",
    "bool_deadline_sent_and_bounded_rejected", "bool_deadline_has_no_queue_row",
    "all_deadline_denials_leave_scene_unchanged", "valid_create_one_exact_native_effect",
    "original_deadline_actually_elapsed", "future_deadline_retry_returns_original_receipt",
    "past_deadline_retry_returns_original_receipt", "retries_leave_exactly_one_object",
    "bounded_native_stop_observed", "stop_preserves_original_receipt",
    "actual_gui_wrapper_exit_zero_and_owned_job_empty", "captured_secrets_absent",
})


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def valid_run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", value):
        raise argparse.ArgumentTypeError("bounded run identifier required")
    return value


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    value.add_argument("--output", type=Path, required=True)
    value.add_argument("--run-id", type=valid_run_id, required=True)
    value.add_argument("--binary", type=Path)
    value.add_argument("--unit-suite", choices=("focused", "all"), default="focused")
    return value


def unit_patterns(snapshot, suite):
    if suite == "all":
        return ["test_*.py"]
    patterns = ["test_absolute_deadline.py", "test_absolute_deadline_probe.py",
                "test_ui_queue.py", "test_client_write_catalog.py"]
    if any(not (snapshot / "tests/blender" / pattern).is_file() for pattern in patterns):
        raise ValueError("required focused deadline test source missing")
    writer = "test_client_writer_session.py"
    if (snapshot / "tests/blender" / writer).is_file():
        patterns.append(writer)
    return patterns


def unit_program(patterns):
    return """import json,sys,unittest
suite=unittest.TestSuite()
for pattern in PATTERNS:
    suite.addTests(unittest.defaultTestLoader.discover('tests/blender',pattern=pattern))
def flatten(value):
    for test in value:
        if isinstance(test,unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test.id()
ids=list(flatten(suite))
print(INVENTORY+json.dumps(ids),flush=True)
result=unittest.TextTestRunner(verbosity=2).run(suite)
counts={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}
print(COMPLETE+json.dumps(counts),flush=True)
sys.exit(not result.wasSuccessful())
""".replace("PATTERNS", repr(patterns)).replace("INVENTORY", repr(UNIT_INVENTORY)).replace("COMPLETE", repr(UNIT_COMPLETE))


def unit_completion(stdout):
    try:
        inventories = [json.loads(line[len(UNIT_INVENTORY):]) for line in stdout.splitlines()
                       if line.startswith(UNIT_INVENTORY)]
        completions = [json.loads(line[len(UNIT_COMPLETE):]) for line in stdout.splitlines()
                       if line.startswith(UNIT_COMPLETE)]
        if len(inventories) != 1 or len(completions) != 1:
            return False, completions
        ids = inventories[0]
        counts = completions[0]
        valid = type(ids) is list and bool(ids) and all(type(item) is str for item in ids)
        valid = valid and len(set(ids)) == len(ids)
        valid = valid and type(counts) is dict and all(type(counts.get(key)) is int
            for key in ("run", "failures", "errors", "skips"))
        valid = valid and counts == {"run": len(ids), "failures": 0, "errors": 0, "skips": 0}
        return bool(valid), completions
    except (ValueError, TypeError):
        return False, []


def wait_past_deadline(deadline_ms, *, wall, clock=time.monotonic, pause=time.sleep, timeout=4.0):
    """Bound real waiting independently of a backward wall-clock adjustment."""
    limit = clock() + timeout
    while True:
        now = wall()
        if now > deadline_ms:
            return now
        remaining = limit - clock()
        if remaining <= 0:
            raise TimeoutError("BLENDER_DEADLINE_PROBE_WAIT_BOUND")
        pause(min(0.02, remaining))


def command(key, operation, state=None, payload=None):
    return {
        "schema": "HH-BLENDER-UI-COMMAND-1", "command_id": key, "operation": operation,
        "expected_revision": state["revision"] if state else None,
        "expected_context": state["context"] if state else None,
        "payload": payload if payload is not None else {},
    }


def frozen(output, binary, run_id, source_closure_sha256):
    from studio.host.blender.ui_host import BlenderUIHost, HostError
    from studio.host.blender.durable_session import queue
    from studio.host.core.transport import epoch_ms
    from studio.protocol.core import canonical_bytes

    gui = None
    rows = []
    events = []
    secrets = []
    failure = None
    cleanup = None
    cleanup_errors = []
    started = utc_now()

    def record(label, condition):
        row = {"label": label, "passed": condition is True}
        rows.append(row)
        print(CHECK_MARKER + json.dumps(row), flush=True)
        return row["passed"]

    def check(label, condition):
        if not record(label, condition):
            raise AssertionError(label)

    def evidence(kind, request, result, **extra):
        request_raw = queue.c.canonical(request)
        result_raw = canonical_bytes(result)
        events.append({
            "kind": kind, "command_id": request["command_id"], "command": request,
            "command_sha256": sha(request_raw), "result": result,
            "result_sha256": sha(result_raw), "recorded_at": utc_now(), **extra,
        })

    def inspect(key):
        request = command(key, "scene.inspect")
        receipt = gui.execute(request, timeout=3, deadline_ms=epoch_ms() + 2000)
        if receipt.get("state") != "COMPLETED" or receipt.get("public_ack") is not False:
            raise AssertionError("native inspect incomplete")
        observed = receipt["result"]
        if queue.c.digest(observed["snapshot"]) != observed["revision"]:
            raise AssertionError("native snapshot hash mismatch")
        evidence("inspect", request, receipt)
        return observed

    def rejected(label, request, lease, deadline, *, raw_ipc):
        before_sent = gui.channels["data"].sent
        began = time.monotonic()
        try:
            if raw_ipc:
                gui._ask("data", "submit", {
                    "command": request, "ttl_ms": 5000, "lease": lease, "deadline_ms": deadline,
                }, timeout=2)
            else:
                gui.submit(request, lease=lease, deadline_ms=deadline)
        except HostError as error:
            denied = str(error) == "BLENDER_COMMAND_REJECTED"
        else:
            denied = False
        elapsed_ms = (time.monotonic() - began) * 1000
        result = {"rejected": denied, "elapsed_ms": elapsed_ms}
        evidence("deadline-denial", request, result, deadline_ms=deadline, raw_ipc=raw_ipc)
        check(label + "_sent_and_bounded_rejected", denied and elapsed_ms < 2500
              and gui.channels["data"].sent == before_sent + 1)
        try:
            gui.result(request["command_id"])
        except HostError as error:
            missing = str(error) == "BLENDER_COMMAND_REJECTED"
        else:
            missing = False
        check(label + "_has_no_queue_row", missing)

    try:
        try:
            gui = BlenderUIHost(output, binary=binary, session_seconds=90)
        except BaseException as error:
            retained = getattr(error, "cleanup_owner", None)
            if type(retained) is BlenderUIHost:
                gui = retained
            raise
        for channel in gui.channels.values():
            secrets.extend((bytes(channel.key), channel.key.hex().encode("ascii")))
        active = gui._job.active_count()
        check("actual_owned_gui_and_job", type(gui.pid) is int and gui.pid > 0
              and type(active) is int and active >= 2)
        before = inspect("deadline-initial")
        check("initial_empty_scene", before["snapshot"]["objects"] == [])
        lease = {"fencing_epoch": 1, "expires_ms": epoch_ms() + 30000}
        armed = gui.arm_lease(lease)
        check("exact_native_fixture_lease_armed", armed == lease)
        payload = {"object_id": "deadline_box", "size": [1, 2, 3]}
        rejected("expired_create", command("deadline-expired", "mesh.create_box", before, payload),
                 lease, epoch_ms() - 1, raw_ipc=False)
        rejected("null_deadline", command("deadline-null", "mesh.create_box", before, payload),
                 lease, None, raw_ipc=True)
        rejected("bool_deadline", command("deadline-bool", "mesh.create_box", before, payload),
                 lease, True, raw_ipc=True)
        check("all_deadline_denials_leave_scene_unchanged", inspect("deadline-after-denials") == before)

        create = command("deadline-create", "mesh.create_box", before, payload)
        absolute = epoch_ms() + 2500
        created = gui.execute(create, timeout=4, lease=lease, deadline_ms=absolute)
        evidence("valid-create", create, created, deadline_ms=absolute)
        after = created.get("result", {}).get("after", {})
        objects = after.get("snapshot", {}).get("objects", [])
        geometry = len(objects) == 1 and objects[0].get("object_id") == "deadline_box"
        if geometry:
            item = objects[0]
            vertices = item.get("vertices", [])
            geometry = len(vertices) == 8 and len(item.get("faces", [])) == 6
            geometry = geometry and item.get("location") == [0, 0, 0]
            geometry = geometry and item.get("rotation") == [0, 0, 0] and item.get("scale") == [1, 1, 1]
            geometry = geometry and [max(v[axis] for v in vertices) - min(v[axis] for v in vertices)
                                     for axis in range(3)] == [1, 2, 3]
        check("valid_create_one_exact_native_effect", created.get("state") == "COMPLETED"
              and created.get("public_ack") is False and geometry
              and after.get("context") == before["context"]
              and queue.c.digest(after["snapshot"]) == after["revision"])
        original_wire = canonical_bytes(created)
        observed_ms = wait_past_deadline(absolute, wall=epoch_ms)
        check("original_deadline_actually_elapsed", observed_ms > absolute)
        for label, retry_deadline in (("future", epoch_ms() + 2000), ("past", absolute)):
            retried = gui.execute(create, timeout=3, lease=lease, deadline_ms=retry_deadline)
            evidence(label + "-retry", create, retried, deadline_ms=retry_deadline,
                     original_deadline_ms=absolute, observed_after_original_ms=observed_ms)
            check(label + "_deadline_retry_returns_original_receipt", canonical_bytes(retried) == original_wire)
        check("retries_leave_exactly_one_object", inspect("deadline-after-retries") == after)
        began = time.monotonic()
        stopped = gui.stop()
        elapsed = (time.monotonic() - began) * 1000
        events.append({"kind": "stop", "result": stopped, "elapsed_ms": elapsed, "recorded_at": utc_now()})
        check("bounded_native_stop_observed", stopped == {"stopped": True, "public_ack": False} and elapsed < 2000)
        check("stop_preserves_original_receipt", canonical_bytes(gui.result(create["command_id"])) == original_wire)
    except BaseException as error:
        failure = safe_failure(error)
    finally:
        if gui is not None:
            for attempt in range(2):
                try:
                    if not gui._stopped:
                        gui.stop()
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
                try:
                    cleanup = gui.close()
                    break
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
        native_pid = getattr(gui, "pid", None)
        record("actual_gui_wrapper_exit_zero_and_owned_job_empty", cleanup_passed(cleanup, native_pid))

    directory = getattr(gui, "directory", None)
    clean_secrets = bool(secrets)
    try:
        evidence_raw = canonical_bytes(events)
        captured = [path for path in directory.rglob("*") if path.is_file()] if isinstance(directory, Path) else []
        for secret in secrets:
            clean_secrets = clean_secrets and bool(secret) and secret not in evidence_raw
            clean_secrets = clean_secrets and all(secret not in path.read_bytes() for path in captured)
    except Exception as error:
        clean_secrets = False
        cleanup_errors.append(safe_failure(error))
    record("captured_secrets_absent", clean_secrets)
    result = {
        "run_id": run_id, "started_at": started, "finished_at": utc_now(),
        "source_closure_sha256": source_closure_sha256,
        "passed": failure is None and {row["label"] for row in rows} == REQUIRED_CHECKS
                  and all(row["passed"] is True for row in rows),
        "checks": rows, "failure": failure, "cleanup_errors": cleanup_errors, "cleanup": cleanup,
        "probe_pid": os.getpid(), "native_pid": native_pid,
        "gui_directory": directory.name if isinstance(directory, Path) else None,
        "events": events, "public_ack": False, "public_write_facade": False,
        "private_fixture_lease_only": True, "live_state_durable": False, "formal_acceptance": False,
    }
    write_json(output, REPORT, result)
    print(NATIVE_COMPLETE + json.dumps({"passed": result["passed"], "checks": len(rows)}), flush=True)
    return int(not result["passed"])


def native_completion(output, host):
    """Require raw process/Job records and the complete, unique native checklist."""
    try:
        if not host_artifact_passed(output, host):
            return False
        report = json.loads((output / REPORT).read_bytes())
        manifest = json.loads((output / "source-closure.json").read_bytes())
        if report.get("run_id") != manifest.get("run_id") \
                or report.get("source_closure_sha256") != manifest.get("source_closure_sha256"):
            return False
        rows = report.get("checks")
        if type(rows) is not list or any(type(row) is not dict for row in rows):
            return False
        labels = [row.get("label") for row in rows]
        if len(labels) != len(REQUIRED_CHECKS) or set(labels) != REQUIRED_CHECKS:
            return False
        if any(row.get("passed") is not True for row in rows):
            return False
        directory = report.get("gui_directory")
        if type(directory) is not str or not re.fullmatch(r"blender-[0-9a-f]{32}", directory):
            return False
        raw_exit = json.loads((output / directory / "process-exit.json").read_bytes())
        raw_close = json.loads((output / directory / "close.json").read_bytes())
        stdout = (output / "native-stdout.txt").read_text(encoding="utf-8")
        markers = [json.loads(line[len(NATIVE_COMPLETE):]) for line in stdout.splitlines()
                   if line.startswith(NATIVE_COMPLETE)]
        return report.get("passed") is True and type(report.get("probe_pid")) is int \
            and report["probe_pid"] == host["target_pid"] \
            and report.get("public_ack") is False and report.get("public_write_facade") is False \
            and report.get("private_fixture_lease_only") is True and report.get("formal_acceptance") is False \
            and cleanup_passed(report.get("cleanup"), report.get("native_pid")) \
            and cleanup_passed(raw_close, report.get("native_pid")) \
            and type(raw_exit.get("exit_code")) is int and type(raw_exit.get("pid")) is int \
            and raw_exit == report["cleanup"]["actual_process_exit"] and raw_close == report["cleanup"] \
            and len(markers) == 1 and type(markers[0].get("checks")) is int \
            and markers == [{"passed": True, "checks": len(rows)}]
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError):
        return False


def evidence_inventory(output):
    result = {}
    for path in sorted(output.rglob("*")):
        relative = path.relative_to(output)
        if not path.is_file() or relative.parts[0] == "source":
            continue
        raw = path.read_bytes()
        result[relative.as_posix()] = {"bytes": len(raw), "sha256": sha(raw)}
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    runner = load(STUDIO / "build/bootstrap/run_fixture.py")
    runner._reject_reparse_ancestors(args.output)
    output = args.output.resolve()
    if args.frozen:
        manifest = json.loads((output / "source-closure.json").read_bytes())
        if STUDIO != output / "source/studio" or sources(STUDIO) != manifest["files"] \
                or runner.source_closure_sha256(manifest["files"]) != manifest["source_closure_sha256"] \
                or args.run_id != manifest["run_id"]:
            raise ValueError("deadline probe requires its exact frozen source")
        return frozen(output, args.binary, args.run_id, manifest["source_closure_sha256"])
    output.mkdir(exist_ok=False)
    original = sources(STUDIO)
    snapshot = output / "source/studio"
    for name in original:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    if sources(snapshot) != original:
        raise ValueError("deadline snapshot mismatch")
    closure = runner.source_closure_sha256(original)
    write_json(output, "source-closure.json", {
        "run_id": args.run_id, "recorded_at": utc_now(), "files": original, "source_closure_sha256": closure,
    })
    patterns = unit_patterns(snapshot, args.unit_suite)
    unit = runner.run_process([sys.executable, "-B", "-c", unit_program(patterns)],
                             cwd=snapshot, output=output, timeout=120, label="unit")
    unit_ok, counts = unit_completion((output / "unit-stdout.txt").read_text(encoding="utf-8"))
    host = None
    if host_artifact_passed(output, unit) and unit_ok:
        binary = args.binary or STUDIO / ".local/tooling/blender-5.2.1-windows-x64/blender.exe"
        host = runner.run_process([
            sys.executable, "-B", str(snapshot / "tests/blender/run_absolute_deadline_probe.py"),
            "--frozen", "--output", str(output), "--binary", str(binary.resolve()), "--run-id", args.run_id,
        ], cwd=snapshot, output=output, timeout=100, label="native")
    native_ok = native_completion(output, host)
    clean_logs = False
    if native_ok:
        report = json.loads((output / REPORT).read_bytes())
        directory = output / report["gui_directory"]
        clean_logs = runner._streams_clean(output, [{"stdout": "native-stdout.txt", "stderr": "native-stderr.txt"}])
        clean_logs = clean_logs and runner._streams_clean(directory, [{"stdout": "stdout.txt", "stderr": "stderr.txt"}])
    result = {
        "run_id": args.run_id, "finished_at": utc_now(), "source_closure_sha256": closure,
        "unit": unit, "unit_patterns": patterns, "unit_completion": unit_ok, "unit_counts": counts,
        "host": host, "native_completion": native_ok, "logs_clean": clean_logs,
        "source_unchanged": sources(STUDIO) == original, "snapshot_unchanged": sources(snapshot) == original,
        "public_ack": False, "public_write_facade": False, "private_fixture_lease_only": True,
        "formal_acceptance": False,
    }
    result["passed"] = host_artifact_passed(output, unit) and unit_ok and native_ok and clean_logs \
        and result["source_unchanged"] and result["snapshot_unchanged"]
    write_json(output, "capture.json", result)
    write_json(output, "evidence-inventory.json", evidence_inventory(output))
    print(json.dumps(result), flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
