"""Native Godot publication through the durable coordinator queue.

This is a bounded GT07 diagnostic.  It freezes the owner, queue and protocol
closure, performs one authenticated typed scene update through
``NativeOwnerDispatcher``, verifies native editor readback plus the durable
publication response, then proves Stop and Windows Job cleanup.  It is not a
GT07 acceptance run until the Q03/Q04/Q08 matrix and two critics are complete.
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
    names = ["build/bootstrap/run_fixture.py", "toolchain.lock.json"]
    paths = [root / name for name in names]
    for name in ("godot-addon", "host/core", "host/jobs", "host/blender",
                 "blender-addon", "protocol", "tests/jobs"):
        base = root / name
        if base.exists():
            paths.extend(path for path in base.rglob("*") if path.is_file()
                         and path.suffix in (".py", ".json", ".gd", ".md", ".godot",
                                             ".uid", ".cfg", ".tres")
                         and "__pycache__" not in path.parts)
    return {path.relative_to(root).as_posix(): _sha(path)
            for path in sorted(set(paths))}


def _closure(root: Path, source: dict[str, str]) -> str:
    runner = root / "build/bootstrap/run_fixture.py"
    spec = importlib.util.spec_from_file_location("gt07_godot_queue_runner", runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.source_closure_sha256(source)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                indent=2).encode("utf-8") + b"\n")


def _run_id(value: str) -> str:
    if not re.fullmatch(r"gt07-native-godot-[0-9]{8}-[0-9]{2}", value):
        raise argparse.ArgumentTypeError("invalid native Godot queue run id")
    return value


def _safe_error(error: BaseException) -> dict[str, str]:
    code = getattr(error, "code", None)
    value = {"type": type(error).__name__,
             "code": code if isinstance(code, str) else type(error).__name__}
    if isinstance(error, FileNotFoundError):
        value["missing_basename"] = Path(error.filename or "").name
    return value


def _child(output: Path, binary: Path, run_id: str,
           source: dict[str, str], closure: str) -> int:
    from studio.host.core.transport import epoch_ms
    from studio.host.jobs.native_dispatch import GodotOwnerBinding, NativeOwnerDispatcher
    from studio.host.jobs.queue_owner import QueueOwner
    from studio.protocol.core import Request, Status, canonical_bytes

    owner_module = None
    owner = queue = dispatch = None
    editor = None
    response = None
    row = reservation = None
    editor_identity = None
    errors: list[dict[str, str]] = []
    stop_snapshot = None
    stop_persistence = None
    owner_stop_durable = False
    queue_state = None
    passed = False
    steps: list[str] = []
    try:
        steps.append("start")
        observed = _sources(STUDIO)
        if observed != source or _closure(STUDIO, observed) != closure:
            raise RuntimeError("FROZEN_SOURCE_CHANGED")
        output.mkdir(parents=True, exist_ok=True)
        steps.append("output")
        owner_module = importlib.util.spec_from_file_location(
            "gt07_frozen_publication_owner", STUDIO / "godot-addon/publication_owner.py")
        module = importlib.util.module_from_spec(owner_module)
        sys.modules[owner_module.name] = module
        owner_module.loader.exec_module(module)
        steps.append("module")
        validation = module._load("validation_owner")
        factory = validation.factory
        initial = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
            scene_revision="sha256:" + hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
            engine_sha256=validation.executor.BINARY_SHA256)
        steps.append("bundle:" + ",".join(sorted(initial.files)))
        workspace = output / "owned"
        workspace.mkdir()
        steps.append("workspace")
        owner = module.GodotPublicationOwner.create(
            workspace, project_id="project.fixture", initial_bundle=initial,
            editor_binary=binary, source_closure_sha256=closure)
        steps.append("owner")
        editor = owner._editor
        editor_identity = editor.identity
        before = owner.inspect()
        queue_root = output / "queue"
        queue_root.mkdir()
        queue = QueueOwner.create(queue_root)
        steps.append("queue")
        dispatch = NativeOwnerDispatcher(queue)
        steps.append("dispatch")
        credential = owner.sessions.issue()
        authorization = "Bearer " + credential.bearer
        lease = owner.lease(
            {"project_id": owner.project_id, "access": "write", "ttl_ms": 90_000},
            authorization=authorization, catalog_digest=owner.contract.CATALOG_DIGEST)
        payload = {"expected_generation": before["generation"],
                   "expected_project_revision": before["project_revision"],
                   "changes": {"position": [3, 4, 5]}}
        request = Request("queue.godot.update", owner.project_id,
            "scene.node.update", lease["lease_id"], lease["fencing_epoch"],
            before["revision"], {"stable_id": "root"}, payload,
            "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            # Edit horizon is 30 s; the 90 s lease does not extend it.
            min(lease["expires_ms"], epoch_ms() + 29_000))
        grant = owner.sessions.authorize(authorization, request.operation,
            project_id=owner.project_id, catalog_digest=owner.contract.CATALOG_DIGEST)
        owner.contract.validate_request(request,
            owner._context(before, owner._leases[grant.session_id]))
        binding = GodotOwnerBinding.create(owner, body=request.as_dict(),
            authorization=authorization, catalog_digest=owner.contract.CATALOG_DIGEST)
        steps.append("binding")
        dispatch.register(binding)
        row = dispatch.enqueue(binding)
        reservation = dispatch.reserve()
        if reservation is None:
            raise RuntimeError("QUEUE_RESERVATION_MISSING")
        steps.append("reserved")
        steps.append(f"deadline:{request.deadline_ms}")
        steps.append(f"now_before_advance:{epoch_ms()}")
        response = dispatch.advance(reservation)
        steps.append("advanced")
        steps.append(f"now_after_advance:{epoch_ms()}")
        if response.status is not Status.COMMITTED:
            raise RuntimeError("NATIVE_GODOT_QUEUE_NOT_COMMITTED")
        after = owner.inspect()
        root = next(item for item in after["state"]["nodes"] if item["stable_id"] == "root")
        if root["position"] != [3, 4, 5]:
            raise RuntimeError("NATIVE_GODOT_READBACK_POSITION_MISMATCH")
        lookup = binding.lookup()
        if lookup.as_dict() != response.as_dict():
            raise RuntimeError("NATIVE_GODOT_LOOKUP_MISMATCH")
        broker_row = queue.broker.lookup(row.job.job_id)
        if broker_row is None or broker_row.state != "COMMITTED":
            raise RuntimeError("DURABLE_GODOT_RECEIPT_NOT_COMMITTED")
        queue_state = broker_row.state
        passed = True
    except BaseException as error:
        errors.append(_safe_error(error))
    finally:
        if dispatch is not None:
            try:
                stop_snapshot = dispatch.stop()
                if owner is not None and owner._queue_dispatcher is dispatch:
                    dispatch.drain_stop()
                    stop_persistence = owner._stop_persistence
                    owner_stop_durable = owner._journal.snapshot()['stopped'] is True
            except BaseException as error:
                errors.append(_safe_error(error))
            try:
                dispatch.close()
            except BaseException as error:
                errors.append(_safe_error(error))
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(_safe_error(error))
        if queue is not None:
            try:
                queue.close()
            except BaseException as error:
                errors.append(_safe_error(error))

    report = {
        "schema": "gt07-native-godot-queue-report-1", "run_id": run_id,
        "source_closure_sha256": closure, "authority": 0,
        "formal_acceptance": False, "public_ack": False,
        "passed": (passed and not errors and stop_snapshot is not None
                   and stop_persistence == 'DURABLE' and owner_stop_durable),
        "editor_identity": editor_identity,
        "editor_cleanup": getattr(editor, '_cleanup', None),
        "owner_stop_persistence": stop_persistence,
        "owner_stop_durable": owner_stop_durable,
        "queue_job_id": row.job.job_id if row is not None else None,
        "queue_state": queue_state,
        "response": response.as_dict() if response is not None else None,
        "stop_snapshot": asdict(stop_snapshot) if stop_snapshot is not None else None,
        "errors": errors,
        "steps": steps,
    }
    _write(output / "native-child.json", report)
    print("GT07_NATIVE_GODOT_QUEUE_CHILD " + json.dumps(
        {"run_id": run_id, "passed": report["passed"], "errors": len(errors)},
        separators=(",", ":")), flush=True)
    return 0 if report["passed"] else 1


def run(output: Path, binary: Path, run_id: str) -> int:
    output = output.resolve()
    # The frozen child runs with its snapshot as cwd.  Keep the pinned editor
    # executable absolute so admission cannot silently resolve it under the
    # snapshot and report a misleading native launch failure.
    binary = binary.resolve()
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    if _sha(binary) != lock['gui_sha256']:
        raise ValueError('GODOT_GUI_PIN_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    source = _sources(STUDIO)
    closure = _closure(STUDIO, source)
    manifest = {"schema": "gt07-native-godot-queue-source-1", "run_id": run_id,
                "source_closure_sha256": closure, "files": source,
                "authority": 0, "formal_acceptance": False,
                "public_ack": False}
    _write(output / "source-closure.json", manifest)
    snapshot = output / "source" / "studio"
    for name, expected in source.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
        if _sha(target) != expected:
            raise RuntimeError("SOURCE_SNAPSHOT_MISMATCH")
    if _sources(STUDIO) != source or _sources(snapshot) != source:
        raise RuntimeError("SOURCE_CHANGED_DURING_FREEZE")
    runner_path = snapshot / "build/bootstrap/run_fixture.py"
    spec = importlib.util.spec_from_file_location("gt07_frozen_godot_runner", runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    child = [sys.executable, "-B", str(snapshot / "tests/jobs/run_native_godot_queue_probe.py"),
             "--frozen", "--output", str(output), "--binary", str(binary),
             "--run-id", run_id]
    environment = os.environ.copy()
    environment["HH_STUDIO_LINUX_GODOT"] = str(
        STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64")
    host = runner.run_process(child, cwd=snapshot, output=output, timeout=240,
                              label="native-godot", env=environment)
    child_report = json.loads((output / "native-child.json").read_bytes()) \
        if (output / "native-child.json").is_file() else None
    report = {"schema": "gt07-native-godot-queue-wrapper-1", "run_id": run_id,
              "source_closure_sha256": closure, "authority": 0,
              "formal_acceptance": False, "public_ack": False,
              "host": host, "child": child_report,
              "source_unchanged": _sources(STUDIO) == source,
              "snapshot_unchanged": _sources(snapshot) == source,
              "passed": bool(child_report and child_report.get("passed") is True
                  and host.get("exit_code") == 0 and host.get("wrapper_exit_code") == 0
                  and host.get("tree_verified") is True
                  and _sources(STUDIO) == source and _sources(snapshot) == source)}
    _write(output / "queue-native.json", report)
    print("GT07_NATIVE_GODOT_QUEUE_COMPLETE " + json.dumps(
        {"run_id": run_id, "passed": report["passed"],
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
