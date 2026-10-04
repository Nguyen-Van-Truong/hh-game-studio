"""Bounded native Blender queue integration probe.

The outer invocation freezes the exact source closure and runs the frozen
child through the existing Windows Job runner. The child performs one
authenticated ``mesh.create_box`` through the durable GT07 queue, verifies
fresh owner readback and the durable receipt, then stops and closes every
owned resource. This is diagnostic evidence for GT07, never acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict[str, str]:
    """Return only the runtime closure used by this probe and its owner."""
    names = ["build/bootstrap/run_fixture.py", "godot-addon/cli_job.py",
             "toolchain.lock.json"]
    paths = [root / name for name in names]
    for name in ("blender-addon", "host/blender", "host/core", "host/jobs",
                 "protocol", "tests/jobs"):
        base = root / name
        if base.exists():
            paths.extend(path for path in base.rglob("*") if path.is_file()
                         and path.suffix in (".py", ".json", ".gd", ".md")
                         and "__pycache__" not in path.parts)
    return {path.relative_to(root).as_posix(): _sha(path)
            for path in sorted(set(paths))}


def _closure(root: Path, source: dict[str, str]) -> str:
    runner = root / "build/bootstrap/run_fixture.py"
    spec = importlib.util.spec_from_file_location("gt07_queue_runner", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.source_closure_sha256(source)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                indent=2).encode("utf-8") + b"\n")


def _run_id(value: str) -> str:
    if not re.fullmatch(r"gt07-native-queue-[0-9]{8}-[0-9]{2}", value):
        raise argparse.ArgumentTypeError("invalid native queue run id")
    return value


def _safe_error(error: BaseException) -> dict[str, str]:
    code = getattr(error, "code", None)
    return {"type": type(error).__name__,
            "code": code if isinstance(code, str) else type(error).__name__}


def _child(output: Path, binary: Path, run_id: str,
           source: dict[str, str], closure: str) -> int:
    """Run inside the frozen snapshot; no source outside it is trusted."""
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.client_writer_owner import BlenderWriterClientOwner
    from studio.host.blender import client_write_catalog as catalog
    from studio.host.jobs.native_dispatch import BlenderOwnerBinding, NativeOwnerDispatcher
    from studio.host.jobs.queue_owner import QueueOwner
    from studio.host.core.transport import epoch_ms
    from studio.protocol.core import Request, Status, canonical_bytes, parse_json

    errors: list[dict[str, str]] = []
    gui = durable = owner = queue = dispatch = None
    response = None
    stop_snapshot = None
    cleanup = None
    stopped = False
    passed = False
    queue_row = None
    queue_state = None
    try:
        observed = _sources(STUDIO)
        if observed != source or _closure(STUDIO, observed) != closure:
            raise RuntimeError("FROZEN_SOURCE_CHANGED")
        output.mkdir(parents=True, exist_ok=True)
        queue_root = output / "queue"
        queue_root.mkdir(exist_ok=False)
        gui = BlenderUIHost(output, binary=binary, session_seconds=90)
        durable = DurableBlenderSession(gui.directory / "journal", host=gui)
        owner = BlenderWriterClientOwner.from_session(durable, publications={})
        operations = catalog.EDIT_OPERATIONS | {catalog.READ, "control.lookup", "control.stop"}
        writer = owner.sessions.issue(operations=operations, ttl_ms=60000)
        queue = QueueOwner.create(queue_root)
        dispatch = NativeOwnerDispatcher(queue)

        # Set the operation deadline only after the owned queue and GUI are up;
        # setup time can never silently consume the operation horizon.
        lease = owner.lease({"project_id": owner.project_id, "access": "write",
                             "ttl_ms": 30000}, authorization="Bearer " + writer.bearer,
                            catalog_digest=owner.catalog_digest)
        before = parse_json(owner._read_owner._baseline)
        payload = {"expected_context": before["context"],
                   "arguments": {"object_id": "queue_probe_box", "size": [1, 2, 3]}}
        request = Request(
            "QueueMeshCreate", owner.project_id, "mesh.create_box",
            lease["lease_id"], lease["fencing_epoch"], before["revision"],
            {"stable_id": catalog.TARGET}, payload,
            "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            epoch_ms() + catalog.MAX_UI_MS - 250)
        body = request.as_dict()
        binding = BlenderOwnerBinding.create(
            owner, body=body, authorization="Bearer " + writer.bearer,
            catalog_digest=owner.catalog_digest)
        dispatch.register(binding)
        queue_row = dispatch.enqueue(binding)
        reservation = dispatch.reserve()
        if reservation is None:
            raise RuntimeError("QUEUE_RESERVATION_MISSING")
        response = dispatch.advance(reservation)
        if response.status is not Status.COMMITTED:
            raise RuntimeError("NATIVE_QUEUE_NOT_COMMITTED")
        lookup = binding.lookup()
        if lookup.as_dict() != response.as_dict():
            raise RuntimeError("OWNER_LOOKUP_MISMATCH")
        observation = response.postconditions.get("observation", {})
        objects = observation.get("scene", {}).get("snapshot", {}).get("objects", [])
        box = next((item for item in objects if item.get("object_id") == "queue_probe_box"), None)
        vertices = box.get("vertices", []) if box is not None else []
        extents = ([max(row[i] for row in vertices) - min(row[i] for row in vertices)
                    for i in range(3)] if len(vertices) == 8 else [])
        if box is None or extents != [1, 2, 3]:
            raise RuntimeError("NATIVE_READBACK_GEOMETRY_MISMATCH")
        row = queue.broker.lookup(queue_row.job.job_id)
        if row is None or row.state != "COMMITTED":
            raise RuntimeError("DURABLE_RECEIPT_NOT_COMMITTED")
        queue_state = row.state
        passed = True
    except BaseException as error:
        errors.append(_safe_error(error))
    finally:
        if dispatch is not None:
            try:
                if not stopped:
                    stop_snapshot = dispatch.stop()
                    stopped = True
            except BaseException as error:
                errors.append(_safe_error(error))
            try:
                dispatch.close()
            except BaseException as error:
                errors.append(_safe_error(error))
        if queue is not None:
            try:
                queue.close()
            except BaseException as error:
                errors.append(_safe_error(error))
        if gui is not None:
            try:
                cleanup = gui.close()
            except BaseException as error:
                errors.append(_safe_error(error))

    report = {
        "schema": "gt07-native-queue-report-2", "run_id": run_id,
        "source_closure_sha256": closure, "authority": 0,
        "formal_acceptance": False, "public_ack": False,
        "passed": passed and not errors and stopped,
        "native_pid": getattr(gui, "pid", None),
        "generation": getattr(gui, "_session", None),
        "queue_job_id": queue_row.job.job_id if queue_row is not None else None,
        "queue_state": queue_state,
        "response": response.as_dict() if response is not None else None,
        "stop_snapshot": (asdict(stop_snapshot) if stop_snapshot is not None else None),
        "cleanup": cleanup, "errors": errors,
    }
    _write(output / "native-child.json", report)
    print("GT07_NATIVE_QUEUE_CHILD " + json.dumps({
        "run_id": run_id, "passed": report["passed"], "errors": len(errors)},
        separators=(",", ":")), flush=True)
    return 0 if report["passed"] else 1


def run(output: Path, binary: Path, run_id: str) -> int:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = _sources(STUDIO)
    closure = _closure(STUDIO, source)
    manifest = {"schema": "gt07-native-queue-source-2", "run_id": run_id,
                "source_closure_sha256": closure, "files": source,
                "authority": 0, "formal_acceptance": False,
                "public_ack": False}
    _write(output / "source-closure.json", manifest)
    snapshot = output / "source" / "studio"
    for name, expected in source.items():
        source_path = STUDIO / name
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        if _sha(target) != expected:
            raise RuntimeError("SOURCE_SNAPSHOT_MISMATCH")
    if _sources(STUDIO) != source or _sources(snapshot) != source:
        raise RuntimeError("SOURCE_CHANGED_DURING_FREEZE")
    runner_path = snapshot / "build/bootstrap/run_fixture.py"
    spec = importlib.util.spec_from_file_location("gt07_frozen_runner", runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    binary = binary.resolve()
    child = [sys.executable, "-B", str(snapshot / "tests/jobs/run_native_blender_queue_probe.py"),
             "--frozen", "--output", str(output), "--binary", str(binary),
             "--run-id", run_id]
    host = runner.run_process(child, cwd=snapshot, output=output, timeout=120,
                              label="native", env=os.environ.copy())
    child_report = json.loads((output / "native-child.json").read_bytes()) if (output / "native-child.json").is_file() else None
    report = {"schema": "gt07-native-queue-wrapper-2", "run_id": run_id,
              "source_closure_sha256": closure, "authority": 0,
              "formal_acceptance": False, "public_ack": False,
              "host": host, "child": child_report,
              "source_unchanged": _sources(STUDIO) == source,
              "snapshot_unchanged": _sources(snapshot) == source,
              "passed": bool(child_report and child_report.get("passed") is True
                             and host.get("exit_code") == 0
                             and host.get("wrapper_exit_code") == 0
                             and host.get("tree_verified") is True
                             and _sources(STUDIO) == source
                             and _sources(snapshot) == source)}
    _write(output / "queue-native.json", report)
    print("GT07_NATIVE_QUEUE_COMPLETE " + json.dumps({
        "run_id": run_id, "passed": report["passed"],
        "wrapper_exit": host.get("wrapper_exit_code"),
        "child_exit": host.get("exit_code")}, separators=(",", ":")), flush=True)
    return 0 if report["passed"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--run-id", type=_run_id, required=True)
    parser.add_argument("--frozen", action="store_true")
    args = parser.parse_args(argv)
    if args.frozen:
        manifest = json.loads((args.output / "source-closure.json").read_bytes())
        return _child(args.output.resolve(), args.binary.resolve(), args.run_id,
                      manifest["files"], manifest["source_closure_sha256"])
    return run(args.output, args.binary, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
