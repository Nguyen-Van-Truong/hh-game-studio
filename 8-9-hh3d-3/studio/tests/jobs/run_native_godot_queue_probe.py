"""Native Godot publication through the durable coordinator queue.

This is a bounded GT07 diagnostic.  It freezes the owner, queue and protocol
closure, performs one authenticated typed scene update through
``NativeOwnerDispatcher``, verifies native editor readback plus the durable
publication response, then proves Stop and Windows Job cleanup.  It is not a
GT07 acceptance run until the Q03/Q04/Q08 matrix and two critics are complete.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.gt07_failpoints import arm as arm_failpoint, reached_path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict[str, str]:
    names = ["build/bootstrap/run_fixture.py", "toolchain.lock.json",
             "tests/replay/measure_window.py", "tests/replay/benchmark_job.py",
             "pipeline/native_job.py"]
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


def _event_head(event_log) -> dict[str, object]:
    """Return the durable event head without mutating or replaying anything."""
    head = event_log.binding().witnessed
    return {"sequence": head.sequence, "sha256": head.sha256, "size": head.size}


_DURABLE_PHASES = frozenset(("COMMITTED", "FAILED", "UNKNOWN"))


def _durable_response(journal, command_id: str, digest: str):
    """Read a response only after the journal has made it durable.

    ``lookup_response`` deliberately rejects PREPARED/STAGED/SELECTED records.
    The crash snapshot is also taken at those phases, so probing it eagerly
    turns a valid failpoint cut into a harness failure before the receipt is
    written. A nonterminal response is absent; terminal response validation
    still belongs to the journal and must fail if its receipt is malformed.
    """
    command = journal.lookup(command_id, digest)
    if not isinstance(command, dict):
        raise RuntimeError("CRASH_SNAPSHOT_COMMAND_MISSING")
    if command.get("phase") not in _DURABLE_PHASES:
        return None
    return journal.lookup_response(command_id, digest)


def _load_owner():
    name = "gt07_frozen_publication_owner"
    spec = importlib.util.spec_from_file_location(name, STUDIO / "godot-addon/publication_owner.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _request_for(operation, *, before, lease, contract, default_script, now_ms,
                 project_id="project.fixture"):
    """One request recipe for native and engine-free admission."""
    from studio.protocol.core import Request, canonical_bytes
    payload = {"expected_generation": before["generation"],
               "expected_project_revision": before["project_revision"]}
    target = {"stable_id": "root"}
    if operation == "scene.node.update":
        payload["changes"] = {"position": [3, 4, 5]}
        command_id, horizon = "queue.godot.update", 29_000
    elif operation == "scene.save":
        payload["expected_files"] = {path: before["working_files"][path]["sha256"]
                                      for path in (contract.SCENE_PATH, contract.SCRIPT_PATH)}
        command_id, horizon = "queue.godot.save", 89_000
    elif operation == "script_text.replace":
        payload.update(expected_sha256=before["working_files"][contract.SCRIPT_PATH]["sha256"],
                       text=default_script.replace(b"int = 7", b"int = 9").decode("utf-8"))
        target = {"path": contract.SCRIPT_PATH}
        command_id, horizon = "queue.godot.script", 89_000
    else:
        raise ValueError("SCENARIO_OPERATION_UNSUPPORTED")
    return Request(command_id, project_id, operation, lease["lease_id"], lease["fencing_epoch"],
                   before["revision"], target, payload,
                   "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                   min(lease["expires_ms"], now_ms + horizon))


def dry_run_contract(operation, recover_after_loss=False):
    """Exercise public lease registration and exact request recipe, no engine.

    The editor state is explicitly synthetic. This checks harness wiring,
    schema and both deadline bounds; it grants no native/public ACK.
    """
    from studio.host.core.transport import epoch_ms
    if recover_after_loss and operation != "script_text.replace":
        raise ValueError("RECOVERY_PROBE_REQUIRES_SCRIPT_REPLACEMENT")
    module = _load_owner()
    contract, auth = module._load("contract"), module._load("publication_session")
    factory = module._load("validation_owner").factory
    with tempfile.TemporaryDirectory(prefix="gt07-admission-") as root:
        owner = object.__new__(module.GodotPublicationOwner)
        owner._lock = threading.RLock()
        owner._closed = owner._held = False
        owner._leases = {}
        owner.project_id, owner.contract = "project.fixture", contract
        owner.sessions = auth.PublicationSession(owner.project_id, Path(root), contract.CATALOG_DIGEST)
        try:
            credential = owner.sessions.issue()
            authorization = "Bearer " + credential.bearer
            lease = owner.lease({"project_id": owner.project_id, "access": "write", "ttl_ms": 90_000},
                                authorization=authorization, catalog_digest=contract.CATALOG_DIGEST)
            before = {"revision": "sha256:" + "1" * 64, "project_revision": "sha256:" + "2" * 64,
                      "generation": 1, "can_undo": False, "can_redo": False,
                      "state": {"nodes": [contract.NodeState("root", None, "Node3D", "Fixture").as_dict()]},
                      "working_files": {contract.SCENE_PATH: {"sha256": "3" * 64},
                                        contract.SCRIPT_PATH: {"sha256": hashlib.sha256(factory.DEFAULT_SCRIPT).hexdigest()}}}
            request = _request_for(operation, before=before, lease=lease, contract=contract,
                                   default_script=factory.DEFAULT_SCRIPT, now_ms=epoch_ms())
            grant = owner.sessions.authorize(authorization, operation,
                        project_id=owner.project_id, catalog_digest=contract.CATALOG_DIGEST)
            context = owner._context(before, owner._leases[grant.session_id])
            result = contract.validate_request(request, context)
            maximum = 30_000 if operation == "scene.node.update" else 90_000
            # A longer synthetic lease keeps the upper-bound test specific to
            # the operation limit rather than merely exceeding lease expiry.
            bounds = replace(context, lease_expires_ms=context.now_ms + 120_000)
            for offset in (1, maximum):
                contract.validate_request(replace(request, deadline_ms=bounds.now_ms + offset), bounds)
            rejected = []
            for offset in (0, maximum + 1):
                try:
                    contract.validate_request(replace(request, deadline_ms=bounds.now_ms + offset), bounds)
                except contract.ContractError as error:
                    if error.code != "GODOT_DEADLINE_EXPIRED":
                        raise
                    rejected.append(offset)
                else:
                    raise RuntimeError("SCENARIO_DEADLINE_NOT_REJECTED")
            return {"operation": operation, "request_digest": result.request_digest,
                    "admission_validated": True, "public_lease_route_validated": True,
                    "deadline_lower_bound_rejected": rejected[0] == 0,
                    "deadline_upper_bound_rejected": rejected[1] == maximum + 1,
                    "synthetic_state": True, "native_effect": False}
        finally:
            owner.sessions.halt()


def _editor_close_proof(cleanup: object, identity: object) -> dict[str, object]:
    """Validate the host/editor close receipt independently of its banner."""
    result = {"present": isinstance(cleanup, dict), "identity": identity,
              "pid_match": False, "actual_exit": None, "wrapper_exit": None,
              "job_clean": False, "valid": False}
    if not isinstance(cleanup, dict) or not isinstance(identity, dict):
        return result
    actual = cleanup.get("actual_process_exit")
    job = cleanup.get("job")
    result["actual_exit"] = actual
    result["wrapper_exit"] = cleanup.get("wrapper_exit_code")
    result["pid_match"] = (isinstance(actual, dict)
                            and type(actual.get("pid")) is int
                            and type(identity.get("pid")) is int
                            and actual["pid"] == identity["pid"])
    result["job_clean"] = (isinstance(job, dict)
                           and all(job.get(key) is True for key in
                                   ("configured", "assigned", "closed", "zero_observed"))
                           and all(job.get(key) is False for key in
                                   ("tainted", "handle_retained", "close_uncertain", "create_uncertain"))
                           and type(job.get("active_count")) is int and job["active_count"] == 0
                           and job.get("failed_operations") == []
                           and job.get("native_error") is None)
    result["valid"] = (cleanup.get("closed") is True
                        and cleanup.get("held") is False
                        and cleanup.get("logs_overflow") is False
                        and result["pid_match"]
                        and isinstance(actual, dict) and type(actual.get("exit_code")) is int
                        and actual["exit_code"] == 0
                        and type(cleanup.get("wrapper_exit_code")) is int
                        and cleanup["wrapper_exit_code"] == 0
                        and result["job_clean"])
    return result


def _recovery_evidence_complete(recover_after_loss: bool,
                                proof: object) -> bool:
    """Fail closed unless the loss boundary and lookup-only invariants hold."""
    if not recover_after_loss:
        return True
    if not isinstance(proof, dict):
        return False
    try:
        return (proof["receipt_boundary"] == "record_owner_result"
                and proof["injection_count"] == 1
                and proof["reconciled_status"] == "COMMITTED"
                and proof["response_before"] == proof["response_after"]
                and proof["response_before"]["status"] == "COMMITTED"
                and proof["submit_calls_before"] == proof["submit_calls_after"] == 1
                and proof["fence_before"] == proof["fence_after"]
                and proof["queue_before_loss"] == proof["queue_after_loss"] == proof["queue_reopened"]
                and proof["queue_after_reconcile"]["sequence"] == proof["queue_after_loss"]["sequence"] + 1
                and proof["queue_result_event"] == proof["expected_queue_result_event"]
                and proof["journal_after_loss"]["sequence"] > proof["journal_before_loss"]["sequence"]
                and proof["journal_after_reconcile"] == proof["journal_after_loss"]
                and proof["native_before_reconcile"] == proof["native_after_reconcile"])
    except (KeyError, TypeError):
        return False


def _native_recovery_state(owner) -> dict[str, object]:
    """Fresh no-effect reads around reconciliation, before the Stop event."""
    return {"editor": owner._editor.identity, "scene": owner.inspect(),
            "selection": owner._journal.selection_facts()}


def _child(output: Path, binary: Path, run_id: str, operation: str,
           recover_after_loss: bool, source: dict[str, str], closure: str,
           failpoint_phase: str | None = None) -> int:
    from studio.host.core.transport import epoch_ms
    from studio.host.jobs.native_dispatch import GodotOwnerBinding, NativeOwnerDispatcher
    from studio.host.jobs.queue_owner import QueueOwner
    from studio.protocol.core import Request, Status, canonical_bytes, parse_json

    owner_module = None
    owner = queue = dispatch = None
    editor = None
    successor_editor = None
    response = None
    row = reservation = None
    editor_identity = None
    errors: list[dict[str, str]] = []
    stop_snapshot = None
    stop_persistence = None
    owner_stop_durable = False
    queue_state = None
    passed = False
    recovery_proof = None
    editor_cleanup_proof = []
    journal_before_loss = journal_after_loss = journal_after_reconcile = None
    queue_before_loss = queue_after_loss = queue_after_reconcile = None
    reservation_fence = None
    successor_identity = None
    submit_calls = 0
    injection_count = 0
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
        if operation == "scene.save":
            changed = owner._editor.apply_projection({"operation": "scene.node.update",
                "command_id": "queue.dirty", "expected_revision": before["revision"],
                "expected_generation": before["generation"], "target_stable_id": "root",
                "payload": {"expected_generation": before["generation"],
                            "changes": {"position": [6, 7, 8]}}})
            if changed.get("ok") is not True:
                raise RuntimeError("NATIVE_GODOT_DIRTY_SETUP_FAILED")
            before = owner.inspect()
        request = _request_for(operation, before=before, lease=lease, contract=owner.contract,
                               default_script=factory.DEFAULT_SCRIPT, now_ms=epoch_ms(),
                               project_id=owner.project_id)
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
        reservation_fence = asdict(reservation.fence)
        steps.append("reserved")
        steps.append(f"deadline:{request.deadline_ms}")
        steps.append(f"now_before_advance:{epoch_ms()}")
        if failpoint_phase is not None:
            context = {"run_id": run_id, "source_closure_sha256": closure,
                "storage_id": owner.storage_id, "project_id": owner.project_id,
                "queue_storage_id": queue.storage_id, "queue_job_id": row.job.job_id,
                "queue_head": _event_head(queue.log), "reservation_fence": reservation_fence,
                "request": request.as_dict(), "digest": request.digest,
                "before": before, "editor_identity": editor_identity,
                "selection": owner._journal.selection_facts()}
            _write(output / "recovery-context.json", context)
            original_failpoint = owner._failpoint
            def captured_failpoint(phase):
                if phase == failpoint_phase:
                    bundle = owner._journal.read_selected_bundle()
                    terminal_raw = _durable_response(owner._journal, request.command_id, request.digest)
                    _write(output / "cut-state.json", {"phase": phase,
                        "journal": owner._journal.snapshot(),
                        "command": owner._journal.lookup(request.command_id, request.digest),
                        "selection": owner._journal.selection_facts(),
                        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(),
                                         "size_bytes": len(data)} for name, data in bundle.files.items()},
                        "original_response": parse_json(terminal_raw) if terminal_raw else None,
                        "queue_head": _event_head(queue.log)})
                original_failpoint(phase)
            owner._failpoint = captured_failpoint
        if recover_after_loss:
            if operation != "script_text.replace":
                raise RuntimeError("RECOVERY_PROBE_REQUIRES_SCRIPT_REPLACEMENT")
            original_record = queue.broker.record_owner_result
            original_submit = owner.submit
            def counted_submit(*args, **kwargs):
                nonlocal submit_calls
                submit_calls += 1
                return original_submit(*args, **kwargs)
            owner.submit = counted_submit
            journal_before_loss = _event_head(owner._journal._log)
            queue_before_loss = _event_head(queue.log)
            class ReceiptLossInjected(OSError):
                pass
            def lost_collection(*_args, **_kwargs):
                nonlocal injection_count
                injection_count += 1
                # Inject only at the queue receipt boundary, after native
                # submit/readback has returned a terminal response.
                raise ReceiptLossInjected("injected queue receipt loss after native effect")
            queue.broker.record_owner_result = lost_collection
            try:
                try:
                    dispatch.advance(reservation)
                except ReceiptLossInjected:
                    journal_after_loss = _event_head(owner._journal._log)
                    queue_after_loss = _event_head(queue.log)
                    native_before_reconcile = _native_recovery_state(owner)
                    lost_response = binding.lookup()
                    if lost_response.status is not Status.COMMITTED:
                        raise RuntimeError("RECOVERY_NATIVE_EFFECT_NOT_COMMITTED")
                    recovery_proof = {"receipt_boundary": "record_owner_result",
                                      "native_effect_committed": journal_after_loss != journal_before_loss,
                                      "queue_receipt_lost": True,
                                      "lookup_after_loss_status": lost_response.status.value,
                                      "response_before": lost_response.as_dict(),
                                      "submit_calls_before": submit_calls,
                                      "injection_count": injection_count}
            finally:
                queue.broker.record_owner_result = original_record
            if recovery_proof is None:
                raise RuntimeError("RECOVERY_LOST_COLLECTION_NOT_REPRODUCED")
            storage_id = queue.storage_id
            dispatch.close()
            dispatch = None
            queue.close()
            queue = QueueOwner.reopen(storage_id)
            dispatch = NativeOwnerDispatcher(queue)
            dispatch.register_recovery(binding)
            queue_reopened = _event_head(queue.log)
            recovered = queue.broker.snapshot().reservations
            if (len(recovered) != 1 or not recovered[0].recovered
                    or asdict(recovered[0].fence) != reservation_fence):
                raise RuntimeError("RECOVERY_RESERVATION_NOT_RETAINED")
            reconciled = dispatch.reconcile(recovered[0], binding)
            response = binding.lookup()
            native_after_reconcile = _native_recovery_state(owner)
            journal_after_reconcile = _event_head(owner._journal._log)
            queue_after_reconcile = _event_head(queue.log)
            queue_result_event = parse_json(queue.log.read(queue_after_reconcile["sequence"]).event)
            recovery_proof.update({"reopened_reservation": True,
                                   "lookup_only_reconcile": True,
                                   "reconciled_status": reconciled.state,
                                   "fence_before": reservation_fence,
                                   "fence_after": asdict(recovered[0].fence),
                                   "fence_continuity": asdict(recovered[0].fence) == reservation_fence,
                                   "journal_before_loss": journal_before_loss,
                                   "journal_after_loss": journal_after_loss,
                                   "journal_after_reconcile": journal_after_reconcile,
                                   "journal_unchanged_during_reconcile": journal_after_reconcile == journal_after_loss,
                                   "queue_before_loss": queue_before_loss,
                                   "queue_after_loss": queue_after_loss,
                                   "queue_reopened": queue_reopened,
                                   "queue_after_reconcile": queue_after_reconcile,
                                   "queue_unchanged_during_reopen": queue_reopened == queue_after_loss,
                                   "queue_result_event": queue_result_event,
                                   "expected_queue_result_event": {"schema": "hh-durable-dispatch-1",
                                                                    "kind": "OWNER_RESULT",
                                                                    "job_id": row.job.job_id,
                                                                    "fence": reservation_fence,
                                                                    "outcome": "COMMITTED",
                                                                    "command_sha256": binding.command_sha256,
                                                                    "receipt_sha256": hashlib.sha256(
                                                                        canonical_bytes(response.as_dict())).hexdigest()},
                                   "response_after": response.as_dict(),
                                   "submit_calls_after": submit_calls,
                                   "native_before_reconcile": native_before_reconcile,
                                   "native_after_reconcile": native_after_reconcile,
                                   "no_native_replay": (journal_after_reconcile == journal_after_loss
                                                         and queue_reopened == queue_after_loss
                                                         and submit_calls == 1
                                                         and asdict(recovered[0].fence) == reservation_fence)})
        else:
            response = dispatch.advance(reservation)
        steps.append("advanced")
        steps.append(f"now_after_advance:{epoch_ms()}")
        if response.status is not Status.COMMITTED:
            raise RuntimeError("NATIVE_GODOT_QUEUE_NOT_COMMITTED")
        after = owner.inspect()
        root = next(item for item in after["state"]["nodes"] if item["stable_id"] == "root")
        if operation == "scene.node.update" and root["position"] != [3, 4, 5]:
            raise RuntimeError("NATIVE_GODOT_READBACK_POSITION_MISMATCH")
        if operation == "scene.save" and (response.code != "GODOT_MANAGED_SCENE_SAVED"
                or root["position"] != [6, 7, 8]
                or after["generation"] <= before["generation"]
                or after["can_undo"] is not False or after["can_redo"] is not False):
            raise RuntimeError("NATIVE_GODOT_SCENE_SAVE_READBACK_MISMATCH")
        if operation == "script_text.replace" and (response.code != "GODOT_MANAGED_SCRIPT_REPLACED"
                or after["generation"] <= before["generation"]
                or after["working_files"][owner.contract.SCRIPT_PATH]["sha256"] !=
                   hashlib.sha256(request.payload["text"].encode("utf-8")).hexdigest()):
            raise RuntimeError("NATIVE_GODOT_SCRIPT_REPLACE_READBACK_MISMATCH")
        successor_editor = owner._editor
        successor_identity = successor_editor.identity
        lookup = binding.lookup()
        if lookup.as_dict() != response.as_dict():
            raise RuntimeError("NATIVE_GODOT_LOOKUP_MISMATCH")
        broker_row = queue.broker.lookup(row.job.job_id)
        if broker_row is None or broker_row.state != "COMMITTED":
            raise RuntimeError("DURABLE_GODOT_RECEIPT_NOT_COMMITTED")
        queue_state = broker_row.state
        if recover_after_loss:
            if response.status is not Status.COMMITTED or response.code != "GODOT_MANAGED_SCRIPT_REPLACED":
                raise RuntimeError("RECOVERY_TERMINAL_READBACK_MISMATCH")
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
            # Retain the current editor even when an earlier verifier raised.
            # Owner.close() clears its references as each resource drains.
            if owner._editor is not None:
                successor_editor = owner._editor
                successor_identity = successor_editor.identity
            try:
                owner.close()
            except BaseException as error:
                errors.append(_safe_error(error))
            for role, resource, identity in (
                    [("original", editor, editor_identity)]
                    + ([("successor", successor_editor, successor_identity)]
                       if successor_editor is not None and successor_editor is not editor else [])):
                proof = _editor_close_proof(getattr(resource, "_cleanup", None), identity)
                proof["role"] = role
                editor_cleanup_proof.append(proof)
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
        "successor_identity": successor_identity,
        "editor_cleanup_proof": editor_cleanup_proof,
        "owner_stop_persistence": stop_persistence,
        "owner_stop_durable": owner_stop_durable,
        "queue_job_id": row.job.job_id if row is not None else None,
        "queue_state": queue_state,
        "recovery_proof": recovery_proof,
        "response": response.as_dict() if response is not None else None,
        "stop_snapshot": asdict(stop_snapshot) if stop_snapshot is not None else None,
        "errors": errors,
        "steps": steps,
    }
    required_cleanup = 2 if operation == "script_text.replace" else 1
    report["editor_cleanup_complete"] = (len(editor_cleanup_proof) == required_cleanup
                                         and all(item["valid"] for item in editor_cleanup_proof))
    recovery_ok = _recovery_evidence_complete(recover_after_loss, recovery_proof)
    report["recovery_evidence_complete"] = recovery_ok
    report["passed"] = bool(report["passed"] and report["editor_cleanup_complete"]
                             and report["recovery_evidence_complete"])
    _write(output / "native-child.json", report)
    print("GT07_NATIVE_GODOT_QUEUE_CHILD " + json.dumps(
        {"run_id": run_id, "passed": report["passed"], "errors": len(errors)},
        separators=(",", ":")), flush=True)
    return 0 if report["passed"] else 1


def _recover_crash(output: Path, binary: Path, run_id: str, source: dict, closure: str) -> int:
    """Fresh-process authenticated recovery of a real cut; never resubmit."""
    from studio.host.core.transport import epoch_ms
    from studio.host.jobs.queue_owner import QueueOwner
    from studio.protocol.core import canonical_bytes
    actor = queue = editor = None
    report = {"schema": "gt07-crash-recovery-1", "run_id": run_id, "authority": 0,
              "checks": {}, "errors": [], "passed": False}
    def check(name, condition):
        report["checks"][name] = bool(condition)
        if not condition:
            raise RuntimeError("CRASH_RECOVERY_" + name.upper())
    try:
        check("source_unchanged", _sources(STUDIO) == source and _closure(STUDIO, source) == closure)
        original = json.loads((output / "recovery-context.json").read_bytes())
        cut = json.loads((output / "cut-state.json").read_bytes())
        request = original["request"]
        command, digest = request["command_id"], original["digest"]
        check("context_binding", original["run_id"] == run_id and original["source_closure_sha256"] == closure)
        queue = QueueOwner.reopen(original["queue_storage_id"])
        record = queue.broker.lookup(original["queue_job_id"])
        check("queue_reservation_retained", record is not None
              and record.fence is not None and asdict(record.fence) == original["reservation_fence"]
              and _event_head(queue.log) == original["queue_head"] == cut["queue_head"])
        owner_module = _load_owner()
        module = owner_module._load("recovery_host")
        work = output / "recovered"
        work.mkdir()
        actor = module.GodotRecoveryHost.open(work, storage_id=original["storage_id"],
            project_id=original["project_id"], expected_source_closure_sha256=closure, editor_binary=binary)
        credential = actor.sessions.issue(operations=module.GRANTS)
        auth = {"authorization": "Bearer " + credential.bearer, "catalog_digest": module.CATALOG_DIGEST}
        lookup_body = {"project_id": actor.project_id, "command_id": command}
        initial = actor.lookup(lookup_body, **auth).as_dict()
        journal = actor._recovery._journal
        selected = journal.selection_facts()
        check("selected_version_preserved", selected == cut["selection"])
        if cut["original_response"] is not None:
            check("original_ack_preserved", initial == cut["original_response"])
        else:
            check("no_premature_ack", initial["status"] != "COMMITTED")
        lease = actor.lease({"project_id": actor.project_id, "ttl_ms": 30_000}, **auth)
        check("new_fencing_epoch", lease["fencing_epoch"] > request["fencing_epoch"])
        body = {**lookup_body, "digest": digest, "lease_id": lease["lease_id"],
            "fencing_epoch": lease["fencing_epoch"], "deadline_ms": min(lease["expires_ms"], epoch_ms() + 29_000)}
        response = actor.reconcile(body, **auth).as_dict()
        report.update(initial_lookup=initial, response=response)
        restored = selected == original["selection"] and cut["original_response"] is None
        check("expected_terminal", response["status"] == ("REJECTED" if restored else "COMMITTED"))
        check("durable_response", journal.recovered_response(command, digest) == canonical_bytes(response))
        if cut["original_response"] is not None:
            check("same_ack_after_reconcile", response == cut["original_response"])
        editor = actor._recovery._editor
        observation = editor.script_observation()
        report["editor_identity"] = editor.identity
        check("fresh_editor", editor.identity["session_id"] != original["editor_identity"]["session_id"]
              and (editor.identity["pid"], editor.identity["creation_filetime"]) !=
                  (original["editor_identity"]["pid"], original["editor_identity"]["creation_filetime"]))
        check("native_readback_files", observation["snapshot"]["working_files"] == cut["files"])
        state = journal.snapshot()
        check("retry_no_effect", actor.reconcile(body, **auth).as_dict() == response
              and actor._recovery._editor is editor and journal.snapshot() == state)
        check("lookup_exact", actor.lookup(lookup_body, **auth).as_dict() == response)
        check("selection_unchanged_after_recovery", journal.selection_facts() == selected)
        check("queue_not_redispatched", _event_head(queue.log) == original["queue_head"])
        actor.close()
        actor = None
        cleanup = _editor_close_proof(editor._cleanup, report["editor_identity"])
        report["editor_cleanup"] = cleanup
        check("recovery_editor_clean", cleanup["valid"])
        restart = output / "lookup-restart"
        restart.mkdir()
        actor = module.GodotRecoveryHost.open(restart, storage_id=original["storage_id"],
            project_id=original["project_id"], expected_source_closure_sha256=closure, editor_binary=binary)
        credential = actor.sessions.issue(operations=module.GRANTS)
        auth["authorization"] = "Bearer " + credential.bearer
        journal = actor._recovery._journal
        state = journal.snapshot()
        check("reopen_lookup_and_retry_no_engine", actor.lookup(lookup_body, **auth).as_dict() == response
              and actor.reconcile(body, **auth).as_dict() == response
              and actor._recovery._editor is None and journal.snapshot() == state
              and journal.selection_facts() == selected)
        report["passed"] = True
    except Exception as error:
        report["errors"].append(_safe_error(error))
        report["failure_code"] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
    finally:
        for resource in (actor, queue):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    report["errors"].append(_safe_error(error))
        report["passed"] = bool(report["passed"] and not report["errors"])
        _write(output / "crash-recovery.json", report)
    return 0 if report["passed"] else 1


def run(output: Path, binary: Path, run_id: str, operation: str,
        recover_after_loss: bool, failpoint_phase: str | None = None) -> int:
    output = output.resolve()
    # The frozen child runs with its snapshot as cwd.  Keep the pinned editor
    # executable absolute so admission cannot silently resolve it under the
    # snapshot and report a misleading native launch failure.
    binary = binary.resolve()
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    if _sha(binary) != lock['gui_sha256']:
        raise ValueError('GODOT_GUI_PIN_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    if failpoint_phase is not None:
        arm_failpoint(output, run_id=run_id, phase=failpoint_phase)
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
             "--run-id", run_id, "--operation", operation]
    if recover_after_loss:
        child.append("--recover-after-loss")
    if failpoint_phase is not None:
        child.extend(["--failpoint-phase", failpoint_phase])
    environment = os.environ.copy()
    environment["HH_STUDIO_LINUX_GODOT"] = str(
        STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64")
    environment.pop("HH_GT07_FAILPOINT_ROOT", None)
    environment.pop("HH_GT07_CRASH_GATE", None)
    recovery_host = recovery_report = None
    if failpoint_phase is not None:
        from studio.tests.jobs.gt07_crash_process import run_cut
        environment["HH_GT07_FAILPOINT_ROOT"] = str(output)
        host = run_cut(child, cwd=snapshot, output=output, timeout=240, env=environment,
            receipt_path=reached_path(output), run_id=run_id, phase=failpoint_phase)
        _write(output / "crash-host.json", host)
        if host["cut_verified"]:
            environment.pop("HH_GT07_FAILPOINT_ROOT")
            recovery_child = child[:]
            recovery_child.append("--recover-crash")
            recovery_host = runner.run_process(recovery_child, cwd=snapshot, output=output,
                timeout=240, label="crash-recovery", env=environment)
            if (output / "crash-recovery.json").is_file():
                recovery_report = json.loads((output / "crash-recovery.json").read_bytes())
    else:
        host = runner.run_process(child, cwd=snapshot, output=output, timeout=240,
                                  label="native-godot", env=environment)
    child_report = json.loads((output / "native-child.json").read_bytes()) \
        if (output / "native-child.json").is_file() else None
    failpoint_passed = bool(
        failpoint_phase is not None and host.get("cut_verified") is True
        and recovery_host and recovery_host.get("exit_code") == 0
        and recovery_host.get("wrapper_exit_code") == 0
        and recovery_host.get("tree_verified") is True and not recovery_host.get("timed_out")
        and recovery_report and recovery_report.get("passed") is True)
    report = {"schema": "gt07-native-godot-queue-wrapper-1", "run_id": run_id,
              "source_closure_sha256": closure, "authority": 0,
              "formal_acceptance": False, "public_ack": False,
              "host": host, "child": child_report,
              "failpoint": {"phase": failpoint_phase, "passed": failpoint_passed,
                            "recovery_host": recovery_host, "recovery": recovery_report}
                            if failpoint_phase is not None else None,
              "source_unchanged": _sources(STUDIO) == source,
              "snapshot_unchanged": _sources(snapshot) == source,
              "passed": bool(failpoint_phase is None and child_report and child_report.get("passed") is True
                  and host.get("exit_code") == 0 and host.get("wrapper_exit_code") == 0
                  and host.get("timed_out") is False
                  and host.get("tree_verified") is True
                  and _sources(STUDIO) == source and _sources(snapshot) == source)}
    _write(output / "queue-native.json", report)
    print("GT07_NATIVE_GODOT_QUEUE_COMPLETE " + json.dumps(
        {"run_id": run_id, "passed": report["passed"],
         "wrapper_exit": host.get("wrapper_exit_code"),
         "child_exit": host.get("exit_code")}, separators=(",", ":")), flush=True)
    # A deliberate cut has a forced process exit, separate from the recovery
    # child's natural exit. Keep crash/recovery proof distinct from normal ACK.
    if failpoint_phase is not None:
        report["passed"] = False
        report["failpoint_passed"] = bool(failpoint_passed and report["source_unchanged"]
                                          and report["snapshot_unchanged"])
        _write(output / "queue-native.json", report)
        return 0 if report["failpoint_passed"] else 1
    return 0 if report["passed"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--run-id", type=_run_id, required=True)
    parser.add_argument("--operation", choices=("scene.node.update", "scene.save",
                                                 "script_text.replace"),
                        default="scene.node.update")
    parser.add_argument("--recover-after-loss", action="store_true")
    parser.add_argument("--failpoint-phase", choices=("PREPARED", "VALIDATED", "ACTIVATING",
                                                        "COMMITTED", "RELOAD", "ACK"))
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--recover-crash", action="store_true")
    args = parser.parse_args(argv)
    if args.recover_crash and not args.frozen:
        parser.error("--recover-crash is an internal frozen recovery stage")
    if args.frozen:
        if os.environ.get("HH_GT07_CRASH_GATE") == "1" and sys.stdin.readline() != "GO\n":
            return 74
        manifest = json.loads((args.output / "source-closure.json").read_bytes())
        if args.recover_crash:
            return _recover_crash(args.output.resolve(), args.binary.resolve(), args.run_id,
                                  manifest["files"], manifest["source_closure_sha256"])
        return _child(args.output.resolve(), args.binary.resolve(), args.run_id,
                      args.operation, args.recover_after_loss,
                      manifest["files"], manifest["source_closure_sha256"], args.failpoint_phase)
    if args.output.name != args.run_id:
        parser.error("output basename must equal the run ID")
    if args.recover_after_loss and args.operation != "script_text.replace":
        parser.error("recovery requires script_text.replace")
    from studio.tests.jobs.run_gt07_scenarios import main as scenario_main
    scenario = "godot-recovery" if args.recover_after_loss else {
        "scene.node.update": "godot-edit", "scene.save": "godot-save",
        "script_text.replace": "godot-script"}[args.operation]
    return scenario_main(["--scenario", scenario, "--godot-binary", str(args.binary),
                          "--run-id", args.run_id, "--output-root", str(args.output.parent),
                          *( ["--failpoint-phase", args.failpoint_phase] if args.failpoint_phase else [] )])


if __name__ == "__main__":
    raise SystemExit(main())
