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


def _request_for(*, before, lease, project_id, now_ms, operation="mesh.create_box"):
    """Use the same command recipe in dry-run and native admission."""
    from studio.host.blender import client_write_catalog as catalog
    from studio.protocol.core import Request, canonical_bytes
    if operation not in ("mesh.create_box", "object.transform.set", "export.publish"):
        raise ValueError("BLENDER_SCENARIO_UNSUPPORTED")
    export = operation == "export.publish"
    transform = operation == "object.transform.set"
    arguments = ({} if export else
                 {"object_id": "queue_probe_box", "location": [3, 4, 5],
                  "rotation": [0, 0, 0], "scale": [1, 1, 1]} if transform else
                 {"object_id": "queue_probe_box", "size": [1, 2, 3]})
    payload = {"expected_context": before["context"],
               "arguments": arguments}
    maximum = catalog.MAX_LEASE_MS if export else catalog.MAX_UI_MS
    expires_ms = (lease.expires_ms if hasattr(lease, "expires_ms")
                  else lease["expires_ms"])
    return Request("QueueExport" if export else ("QueueTransform" if transform else "QueueMeshCreate"), project_id, operation,
                   lease["lease_id"], lease["fencing_epoch"], before["revision"],
                   {"stable_id": catalog.TARGET}, payload,
                   "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                   min(expires_ms, now_ms + maximum - 250))


def dry_run_contract(operation="mesh.create_box", recover_after_loss=False):
    """Real public admission over the existing explicitly inert owner fixture.

    Native process/Job/journal backends are modeled by the GT04 test fixture;
    public authentication, lease registration and deadline validation are real.
    This grants no Blender execution or native durability claim.
    """
    from unittest.mock import patch
    from studio.host.blender import client_write_catalog as catalog
    from studio.host.blender import client_session, client_writer_session
    from studio.host.core.limits import SafetyViolation
    from studio.host.core.transport import epoch_ms
    from studio.protocol.core import parse_json
    if recover_after_loss or operation not in ("mesh.create_box", "object.transform.set", "export.publish"):
        raise ValueError("BLENDER_SCENARIO_UNSUPPORTED")
    # Reuse the maintained inert integration fixture, not another mock owner.
    # Its bare test_client_ledger import is resolved only during this import.
    old_path = sys.path[:]
    try:
        sys.path.insert(0, str(STUDIO / "tests/blender"))
        from studio.tests.blender.test_client_writer_owner import WriterOwnerTests
        from studio.tests.blender.test_client_writer_publication import PublicationClientTests
    finally:
        sys.path[:] = old_path
    fixture = PublicationClientTests() if operation == "export.publish" else WriterOwnerTests()
    try:
        fixture.setUp()
        owner = fixture.owner
        lease = owner.lease({"project_id": owner.project_id, "access": "write", "ttl_ms": 30_000},
                            **fixture.kw)
        now = epoch_ms()
        request = _request_for(before=parse_json(owner._read_owner._baseline), lease=lease,
                               project_id=owner.project_id, now_ms=now, operation=operation)
        if operation not in owner._supported:
            raise RuntimeError("SCENARIO_PUBLICATION_NOT_CONNECTED")
        checked = catalog.validate_request(request.as_dict(), project_id=owner.project_id,
                                           source_sha256=owner._source_sha256)
        grant = owner.sessions.authorize(fixture.auth, request.operation,
                                        project_id=owner.project_id,
                                        catalog_digest=owner.catalog_digest)
        resolved = owner.sessions.resolve_writer_lease(grant, request.lease_id, request.fencing_epoch)
        rejected = []
        maximum = catalog.MAX_LEASE_MS if operation == "export.publish" else catalog.MAX_UI_MS
        with patch.object(client_session, "epoch_ms", return_value=now), \
                patch.object(client_writer_session, "epoch_ms", return_value=now):
            # The native owner deadline can be a few milliseconds shorter
            # than the catalog maximum.  Validate the exact admitted upper
            # bound instead of assuming the nominal maximum is reachable.
            valid_upper = request.deadline_ms - now
            if valid_upper <= 1:
                raise RuntimeError("SCENARIO_DEADLINE_WINDOW_TOO_SHORT")
            for offset in (1, valid_upper):
                owner.sessions.check_write(grant, resolved, operation=request.operation,
                                            deadline_ms=now + offset)
            for offset in (0, maximum + 1):
                try:
                    owner.sessions.check_write(grant, resolved, operation=request.operation,
                                                deadline_ms=now + offset)
                except SafetyViolation as error:
                    if error.code != "BLENDER_DEADLINE_EXPIRED":
                        raise
                    rejected.append(offset)
                else:
                    raise RuntimeError("SCENARIO_DEADLINE_NOT_REJECTED")
        fixture.host.execute.assert_not_called()
        return {"operation": checked.operation, "request_digest": checked.digest,
                "admission_validated": True, "public_lease_route_validated": True,
                "deadline_lower_bound_rejected": rejected[0] == 0,
                "deadline_upper_bound_rejected": rejected[1] == maximum + 1,
                "synthetic_state": True, "native_effect": False,
                "modeled_backends": ["native_process", "Job", "writer_journal", "ledger"]}
    finally:
        fixture.doCleanups()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict[str, str]:
    """Return only the runtime closure used by this probe and its owner."""
    names = ["build/bootstrap/run_fixture.py", "godot-addon/cli_job.py",
             "toolchain.lock.json", "tests/replay/measure_window.py",
             "tests/replay/benchmark_job.py", "pipeline/native_job.py",
             "tests/blender/test_client_writer_owner.py", "tests/blender/test_client_ledger.py",
             "tests/blender/test_client_writer_publication.py"]
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
           source: dict[str, str], closure: str, operation="mesh.create_box",
           failpoint_phase: str | None = None) -> int:
    """Run inside the frozen snapshot; no source outside it is trusted."""
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.publication_owner import BlenderPublicationOwner
    from studio.host.blender.client_writer_owner import BlenderWriterClientOwner
    from studio.host.blender import client_write_catalog as catalog
    from studio.host.jobs.native_dispatch import BlenderOwnerBinding, NativeOwnerDispatcher
    from studio.host.jobs.queue_owner import QueueOwner
    from studio.host.core.transport import epoch_ms
    from studio.protocol.core import Request, Status, canonical_bytes, parse_json

    errors: list[dict[str, str]] = []
    gui = durable = owner = queue = dispatch = publisher = None
    publication_proof = None
    conflict_proof = None
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
        publications = {}
        if operation == "export.publish":
            publisher = BlenderPublicationOwner.create(output, session=durable)
            publications[operation] = publisher
        owner = BlenderWriterClientOwner.from_session(durable, publications=publications)
        operations = catalog.EDIT_OPERATIONS | {catalog.READ, "control.lookup", "control.stop"}
        if publisher is not None:
            operations |= {operation}
        writer = owner.sessions.issue(operations=operations, ttl_ms=60000)
        queue = QueueOwner.create(queue_root)
        dispatch = NativeOwnerDispatcher(queue)

        # Set the operation deadline only after the owned queue and GUI are up;
        # setup time can never silently consume the operation horizon.
        lease = owner.lease({"project_id": owner.project_id, "access": "write",
                             "ttl_ms": 30000}, authorization="Bearer " + writer.bearer,
                            catalog_digest=owner.catalog_digest)
        before = parse_json(owner._read_owner._baseline)
        request = _request_for(before=before, lease=lease, project_id=owner.project_id, now_ms=epoch_ms())
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
        if operation == "object.transform.set":
            # The queue request below keeps this owner's pre-edit revision.
            # A direct UI command then edits and saves the native .blend while
            # that request is reserved.  This is the manual-writer boundary;
            # it bypasses the public ledger but uses the already armed native
            # fence and fixed save slot.
            before_manual = parse_json(owner._read_owner._baseline)
            lease_row = next(iter(owner.sessions._writer_leases.values()))
            native_lease = lease_row["native"]
            native_fence = {"fencing_epoch": native_lease.fencing_epoch,
                            "expires_ms": native_lease.expires_ms}
            request = _request_for(before=before_manual, lease=lease,
                project_id=owner.project_id, now_ms=epoch_ms(), operation=operation)
            binding = BlenderOwnerBinding.create(owner, body=request.as_dict(),
                authorization="Bearer " + writer.bearer,
                catalog_digest=owner.catalog_digest)
            dispatch.register(binding)
            queue_row = dispatch.enqueue(binding)
            reservation = dispatch.reserve()
            if reservation is None:
                raise RuntimeError("QUEUE_CONFLICT_RESERVATION_MISSING")
            manual_edit = {"schema": catalog.queue.SCHEMA,
                "command_id": "manual-blend-edit", "operation": operation,
                "expected_revision": before_manual["revision"],
                "expected_context": before_manual["context"],
                "payload": {"object_id": "queue_probe_box", "location": [8, 8, 8],
                            "rotation": [0, 0, 0], "scale": [1, 1, 1]}}
            edited = gui.execute(manual_edit, lease=native_fence,
                                 deadline_ms=epoch_ms() + catalog.MAX_UI_MS)
            if edited.get("state") != "COMPLETED":
                raise RuntimeError("NATIVE_MANUAL_EDIT_NOT_COMMITTED")
            manual_after = edited.get("result", {}).get("after")
            if not isinstance(manual_after, dict):
                raise RuntimeError("NATIVE_MANUAL_EDIT_READBACK_MISSING")
            checkpoint = {"schema": catalog.queue.SCHEMA,
                "command_id": "manual-blend-checkpoint", "operation": "checkpoint.save",
                "expected_revision": manual_after["revision"],
                "expected_context": manual_after["context"],
                "payload": {"slot": "checkpoint"}}
            saved = gui.execute(checkpoint, lease=native_fence,
                                deadline_ms=epoch_ms() + catalog.MAX_UI_MS)
            if saved.get("state") != "COMPLETED":
                raise RuntimeError("NATIVE_MANUAL_BLEND_SAVE_NOT_COMMITTED")
            artifact = saved.get("result", {}).get("artifact")
            if not isinstance(artifact, dict) or artifact.get("name") != "checkpoint.blend":
                raise RuntimeError("NATIVE_MANUAL_BLEND_ARTIFACT_MISSING")
            response = dispatch.advance(reservation)
            if (response.status is not Status.UNKNOWN
                    or response.code != "BLENDER_MANUAL_EDIT_RECONCILE_REQUIRED"
                    or response.postconditions.get("next_action") != "lookup.reconcile"
                    or response.postconditions.get("manual_state_preserved") is not True):
                raise RuntimeError("NATIVE_BLENDER_CONFLICT_NOT_UNKNOWN")
            lookup = binding.lookup()
            if lookup.as_dict() != response.as_dict():
                raise RuntimeError("NATIVE_BLENDER_CONFLICT_LOOKUP_MISMATCH")
            live = gui.execute({"schema": catalog.queue.SCHEMA,
                "command_id": "manual-blend-inspect", "operation": "scene.inspect",
                "expected_revision": None, "expected_context": None, "payload": {}})
            live_scene = live.get("result")
            objects = live_scene.get("snapshot", {}).get("objects", []) if isinstance(live_scene, dict) else []
            box = next((item for item in objects if item.get("object_id") == "queue_probe_box"), None)
            if box is None or box.get("location") != [8.0, 8.0, 8.0]:
                raise RuntimeError("NATIVE_MANUAL_BLENDER_STATE_NOT_PRESERVED")
            row = queue.broker.lookup(queue_row.job.job_id)
            if row is None or row.state != "UNKNOWN":
                raise RuntimeError("NATIVE_BLENDER_CONFLICT_NOT_DURABLE")
            conflict_proof = {"manual_edit": edited, "manual_save": saved,
                              "checkpoint_artifact": artifact,
                              "manual_revision": live_scene["revision"],
                              "owner_response_code": response.code,
                              "next_action": response.postconditions["next_action"],
                              "queue_state": row.state, "public_ack": False}
            queue_state = row.state
            passed = True
        elif publisher is not None:
            # The producer setup is an ordinary queued command. Re-admit the
            # publication against its actual observation and a fresh lease.
            lease = owner.lease({"project_id": owner.project_id, "access": "write",
                                 "ttl_ms": 30000}, authorization="Bearer " + writer.bearer,
                                catalog_digest=owner.catalog_digest)
            request = _request_for(before=observation["scene"], lease=lease,
                project_id=owner.project_id, now_ms=epoch_ms(), operation=operation)
            binding = BlenderOwnerBinding.create(owner, body=request.as_dict(),
                authorization="Bearer " + writer.bearer, catalog_digest=owner.catalog_digest)
            dispatch.register(binding)
            queue_row = dispatch.enqueue(binding)
            reservation = dispatch.reserve()
            if reservation is None:
                raise RuntimeError("QUEUE_EXPORT_RESERVATION_MISSING")
            if failpoint_phase is not None:
                if failpoint_phase not in ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "ACK"):
                    raise RuntimeError("BLENDER_FAILPOINT_PHASE_INVALID")
                from studio.tests.jobs.gt07_blender_recovery import capture
                original_failpoint = publisher._failpoint
                def captured_failpoint(phase):
                    if phase == failpoint_phase:
                        capture(output, publisher, queue, queue_row.job.job_id,
                                run_id=run_id, closure=closure, phase=phase)
                    original_failpoint(phase)
                publisher._failpoint = captured_failpoint
            response = dispatch.advance(reservation)
            if response.status is not Status.COMMITTED or binding.lookup() != response:
                raise RuntimeError("NATIVE_EXPORT_NOT_COMMITTED")
            manifest, artifacts = publisher.read_selected()
            if manifest["snapshot"] != observation["scene"]["snapshot"]:
                raise RuntimeError("NATIVE_EXPORT_SNAPSHOT_CHANGED")
            captured = output / "published"
            captured.mkdir()
            for name, raw in artifacts.items():
                (captured / name).write_bytes(raw)
                if _sha(captured / name) != manifest["artifacts"][name]["sha256"]:
                    raise RuntimeError("NATIVE_EXPORT_CAPTURE_CHANGED")
            _write(captured / "manifest.json", manifest)
            publication_proof = {"storage_id": publisher.storage_id,
                "manifest_sha256": _sha(captured / "manifest.json"),
                "artifacts": {name: {"sha256": _sha(captured / name), "bytes": len(raw)}
                              for name, raw in artifacts.items()},
                "export_cleanup": parse_json(publisher._job._cleanup_result),
                "godot_import_readback": False, "public_ack": False}
            cleanup_export = publication_proof["export_cleanup"]
            if (cleanup_export["actual_process_exit"]["exit_code"] != 0
                    or cleanup_export["wrapper_exit_code"] != 0
                    or cleanup_export["cleanup_held"]
                    or not cleanup_export["job"]["closed"]
                    or not cleanup_export["job"]["zero_observed"]
                    or cleanup_export["job"]["handle_retained"]):
                raise RuntimeError("NATIVE_EXPORT_CLEANUP_UNPROVEN")
        row = queue.broker.lookup(queue_row.job.job_id)
        expected_state = "UNKNOWN" if operation == "object.transform.set" else "COMMITTED"
        if row is None or row.state != expected_state:
            raise RuntimeError("DURABLE_RECEIPT_NOT_COMMITTED" if expected_state == "COMMITTED"
                               else "NATIVE_BLENDER_CONFLICT_NOT_DURABLE")
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
        if publisher is not None:
            try:
                publisher.close()
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
        "operation": operation, "publication": publication_proof,
        "conflict": conflict_proof,
        "response": response.as_dict() if response is not None else None,
        "stop_snapshot": (asdict(stop_snapshot) if stop_snapshot is not None else None),
        "cleanup": cleanup, "errors": errors,
    }
    _write(output / "native-child.json", report)
    print("GT07_NATIVE_QUEUE_CHILD " + json.dumps({
        "run_id": run_id, "passed": report["passed"], "errors": len(errors)},
        separators=(",", ":")), flush=True)
    return 0 if report["passed"] else 1


def run(output: Path, binary: Path, run_id: str, operation="mesh.create_box",
        failpoint_phase: str | None = None) -> int:
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
             "--run-id", run_id, "--operation", operation]
    if failpoint_phase is not None:
        if operation != "export.publish":
            raise ValueError("FAILPOINT_EXPORT_ONLY")
        from studio.host.core.gt07_failpoints import arm as arm_failpoint, reached_path
        arm_failpoint(output, run_id=run_id, phase=failpoint_phase)
        child.extend(["--failpoint-phase", failpoint_phase])
        environment = os.environ.copy()
        environment["HH_GT07_FAILPOINT_ROOT"] = str(output)
        from studio.tests.jobs.gt07_crash_process import run_cut
        host = run_cut(child, cwd=snapshot, output=output, env=environment,
                       receipt_path=reached_path(output), run_id=run_id,
                       phase=failpoint_phase, timeout=240)
        environment.pop("HH_GT07_FAILPOINT_ROOT", None)
        recovery_child = child + ["--recover-crash"]
        recovery_host = runner.run_process(recovery_child, cwd=snapshot, output=output,
                                           timeout=120, label="crash-recovery", env=environment)
        _write(output / "crash-recovery-host.json", recovery_host)
    else:
        host = runner.run_process(child, cwd=snapshot, output=output, timeout=120,
                                  label="native", env=os.environ.copy())
        recovery_host = None
    child_report = json.loads((output / "native-child.json").read_bytes()) if (output / "native-child.json").is_file() else None
    recovery_report = json.loads((output / "blender-crash-recovery.json").read_bytes()) \
        if (output / "blender-crash-recovery.json").is_file() else None
    failpoint_passed = bool(failpoint_phase is not None and host.get("cut_verified") is True
                            and recovery_host and recovery_host.get("exit_code") == 0
                            and recovery_host.get("wrapper_exit_code") == 0
                            and recovery_host.get("tree_verified") is True
                            and recovery_report and recovery_report.get("passed") is True)
    report = {"schema": "gt07-native-queue-wrapper-2", "run_id": run_id,
              "source_closure_sha256": closure, "authority": 0,
              "formal_acceptance": False, "public_ack": False,
              "host": host, "child": child_report,
              "failpoint": {"phase": failpoint_phase, "passed": failpoint_passed,
                            "recovery_host": recovery_host, "recovery": recovery_report}
                            if failpoint_phase is not None else None,
              "source_unchanged": _sources(STUDIO) == source,
              "snapshot_unchanged": _sources(snapshot) == source,
              "passed": (failpoint_passed if failpoint_phase is not None else bool(
                             child_report and child_report.get("passed") is True
                             and host.get("exit_code") == 0
                             and host.get("wrapper_exit_code") == 0
                             and host.get("tree_verified") is True
                             and _sources(STUDIO) == source
                             and _sources(snapshot) == source))}
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
    parser.add_argument("--operation", choices=("mesh.create_box", "object.transform.set", "export.publish"), default="mesh.create_box")
    parser.add_argument("--failpoint-phase", choices=("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "ACK"))
    parser.add_argument("--recover-crash", action="store_true")
    args = parser.parse_args(argv)
    if args.frozen:
        manifest = json.loads((args.output / "source-closure.json").read_bytes())
        if args.recover_crash:
            from studio.tests.jobs.gt07_blender_recovery import recover
            return recover(args.output.resolve(), run_id=args.run_id,
                           closure=manifest["source_closure_sha256"])
        return _child(args.output.resolve(), args.binary.resolve(), args.run_id,
                      manifest["files"], manifest["source_closure_sha256"], args.operation,
                      args.failpoint_phase)
    if args.output.name != args.run_id:
        parser.error("output basename must equal the run ID")
    from studio.tests.jobs.run_gt07_scenarios import main as scenario_main
    scenario = ("blender-export" if args.operation == "export.publish"
                else "blender-conflict" if args.operation == "object.transform.set"
                else "blender-box")
    argv = ["--scenario", scenario, "--blender-binary", str(args.binary),
            "--run-id", args.run_id, "--output-root", str(args.output.parent)]
    if args.failpoint_phase:
        argv.extend(["--failpoint-phase", args.failpoint_phase])
    return scenario_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
