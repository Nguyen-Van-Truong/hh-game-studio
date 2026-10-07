"""Native authority-zero Blender -> Godot queue publication probe.

The Blender publication is an already verified terminal handoff.  This probe
binds that receipt as a durable dependency, runs exactly one gameplay-source
Godot publication, and records the queue result only after CURRENT/journal and
readback have been checked.  It is diagnostic evidence for M3, not acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.jobs.queue_owner import QueueOwner
from studio.host.core.gt07_failpoints import (arm as arm_failpoint,
                                               reached_path)
from studio.tests.jobs.cross_app_publication import (CrossAppPublicationCoordinator,
    ProducerReceipt)
from studio.tests.godot import run_gameplay_publication_probe as base


def _sha(raw: bytes) -> str:
    if isinstance(raw, Path):
        raw = raw.read_bytes()
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("CROSS_APP_HASH_BYTES_REQUIRED")
    return hashlib.sha256(raw).hexdigest()


def _save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def _producer_receipt_from_handoff(handoff_dir: Path, handoff: dict,
                                   artifact: bytes, manifest_raw: bytes) -> ProducerReceipt:
    """Bind the consumer to the producer's actual durable queue receipt.

    A producer run is a dependency only when its terminal queue row, command
    digest and receipt digest are read back from the immutable producer
    closeout.  Deriving those values from the run id would create a synthetic
    dependency that could never prove Blender->Godot fencing.
    """
    root = handoff_dir.parent
    wrapper = json.loads((root / "queue-native.json").read_bytes())
    child = wrapper.get("child")
    queue_id = child.get("queue_job_id") if isinstance(child, dict) else None
    rows = child.get("stop_snapshot", {}).get("receipts", []) if isinstance(child, dict) else []
    row = next((item for item in rows
                if isinstance(item, dict)
                and isinstance(item.get("job"), dict)
                and item["job"].get("job_id") == queue_id), None)
    if not isinstance(row, dict) or row.get("state") != "COMMITTED":
        raise RuntimeError("CROSS_APP_PRODUCER_QUEUE_RECEIPT_MISSING")
    job = row["job"]
    expected_manifest = handoff["manifest_sha256"]
    publication = child.get("publication", {})
    if (publication.get("manifest_sha256") != expected_manifest
            or publication.get("artifacts", {}).get("scene.glb", {}).get("sha256")
            != handoff["artifact"]["sha256"]):
        raise RuntimeError("CROSS_APP_PRODUCER_RECEIPT_BINDING")
    return ProducerReceipt(
        job_id=queue_id,
        project_id=job.get("project_id"),
        session_id=job.get("session_id"),
        command_sha256=row.get("command_sha256"),
        receipt_sha256=row.get("receipt_sha256"),
        artifact_sha256=handoff["artifact"]["sha256"],
        artifact_size=handoff["artifact"]["bytes"],
        manifest_sha256=expected_manifest)


def _snapshot_sources(output: Path, files: dict[str, str], closure: str) -> Path:
    """Freeze the exact owner/queue runner closure used by a crash child."""
    snapshot = output / "source" / "studio"
    for name, expected in sorted(files.items()):
        source = STUDIO / name
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if _sha(target.read_bytes()) != expected:
            raise RuntimeError("CROSS_APP_SOURCE_SNAPSHOT_MISMATCH")
    _save(output / "source-closure.json", {
        "schema": "gt07-cross-app-source-1", "source_closure_sha256": closure,
        "files": files, "authority": 0, "public_ack": False})
    return snapshot


def _probe_sources(owner_mod, fixture_args):
    files, closure = base._probe_sources(owner_mod, fixture_args)
    names = ["build/bootstrap/run_fixture.py", "tests/jobs/cross_app_publication.py",
             "tests/jobs/run_gt07_cross_app_probe.py", "tests/jobs/gt07_crash_process.py"]
    names.extend(path.relative_to(STUDIO).as_posix()
                 for path in (STUDIO / "host/jobs").glob("*.py"))
    for folder in ("tests/godot/gameplay_fixture", "tests/godot/fixtures"):
        for path in (STUDIO / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                names.append(path.relative_to(STUDIO).as_posix())
    for name in names:
        files[name] = _sha(STUDIO / name)
    return files, closure


def _cross_app_candidate(handoff_dir: Path):
    """Build the same immutable candidate as the normal consumer path."""
    fixture_args = SimpleNamespace(fixture="gameplay_source_assets",
                                   saved_arena=None,
                                   blender_published=handoff_dir)
    owner_mod = base.load("cross_app_owner", STUDIO / "godot-addon/gameplay_source_owner.py")
    fixtures = base.load("cross_app_fixtures", STUDIO / "tests/godot/linux_probe_fixtures.py")
    probe = base.load("cross_app_linux_probe", STUDIO / "tests/godot/run_linux_probe.py")
    artifact, manifest_raw, handoff = base.read_blender_handoff(handoff_dir)
    case = base._publication_case(fixture_args, owner_mod, fixtures, glb=artifact)
    candidate = probe.case_files(case)
    candidate.pop("project.godot")
    owner_mod._copy_source_bundle(owner_mod._load("gameplay_source_profile"),
                                  candidate, entrypoint=owner_mod.ENTRYPOINT)
    return owner_mod, candidate, artifact, manifest_raw, handoff


def _write_cut_state(output: Path, *, phase: str, run_id: str, closure: str,
                     owner, queue, reservation, producer: ProducerReceipt,
                     before: dict, request: dict, calls: list[str], **extra) -> None:
    root = owner._root
    request_summary = {key: value for key, value in request.items()
                       if key != "source_files"}
    request_summary["source_files_sha256"] = {
        name: _sha(raw) for name, raw in request.get("source_files", {}).items()}
    _save(output / "consumer-cut-state.json", {
        "schema": "gt07-cross-app-consumer-cut-1", "run_id": run_id,
        "phase": phase, "source_closure_sha256": closure,
        "queue_storage_id": queue.storage_id, "queue_job_id": reservation.job.job_id,
        "reservation_fence": {"stream_id": reservation.fence.stream_id,
                               "generation": reservation.fence.generation},
        "owner_root": str(root), "producer": {name: getattr(producer, name)
            for name in producer.__dataclass_fields__},
        "before": before, "current_before": (root / "CURRENT").read_bytes().hex(),
        "journal_before": (root / "journal.jsonl").read_bytes().hex(),
        "request": request_summary, "native_dispatch_count": len(calls), **extra})


def _consumer_cut_child(output: Path, handoff_dir: Path, run_id: str,
                        closure: str, phase: str) -> int:
    """Run one gated consumer cut; the host kills this process at the hook."""
    from studio.host.core.gt07_failpoints import hit as hit_failpoint
    owner_mod, candidate, artifact, manifest_raw, handoff = _cross_app_candidate(handoff_dir)
    files, observed_closure = owner_mod.runtime_source_closure()
    if observed_closure != closure:
        raise RuntimeError("CROSS_APP_CHILD_SOURCE_CHANGED")
    producer = _producer_receipt_from_handoff(handoff_dir, handoff, artifact, manifest_raw)
    (output / "queue").mkdir()
    queue = QueueOwner.create(output / "queue")
    owner = None
    calls: list[str] = []
    try:
        coordinator = CrossAppPublicationCoordinator(queue)
        coordinator.admit_producer(producer)
        reservation = coordinator.enqueue_consumer(
            job_id="consumer-" + run_id, producer=producer,
            command_sha256=_sha((run_id + ":consumer").encode()))
        initial = dict(candidate)
        initial[owner_mod.ENTRYPOINT] += b"\n# Initial unpublished cross-app fixture.\n"
        def run_native(project, **kwargs):
            if calls:
                raise RuntimeError("CROSS_APP_SECOND_NATIVE_DISPATCH")
            calls.append(str(kwargs["output"]))
            return owner_mod._load("linux_executor").run(project, **kwargs)
        owner = owner_mod.GameplaySourcePublicationOwner.create(
            output, project_id="project.cross-app", source_files=initial,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=closure,
            runner=run_native)
        first = owner.inspect()
        credential = owner.issue()
        grant = owner.authorize("Bearer " + credential.bearer, "scene.save")
        lease = owner.lease(grant)
        request = {"command_id": "command.cross-app.1",
                   "expected_project_revision": first["project_revision"],
                   "source_files": candidate, "entrypoint": owner_mod.ENTRYPOINT}
        request["digest"] = owner_mod.request_digest(project_id=owner.project_id,
                                                       **request)
        if phase == "RELOAD":
            original_select = owner._atomic_select
            def cut_select(revision, generation):
                _write_cut_state(output, phase=phase, run_id=run_id, closure=closure,
                                 owner=owner, queue=queue, reservation=reservation,
                                 producer=producer, before=first, request=request,
                                 calls=calls)
                hit_failpoint(output, phase)
                return original_select(revision, generation)
            owner._atomic_select = cut_select
        elif phase == "ACK":
            original_publish = owner.publish
            def cut_publish(*args, **kwargs):
                ack = original_publish(*args, **kwargs)
                observed = owner.inspect()
                _write_cut_state(output, phase=phase, run_id=run_id, closure=closure,
                                 owner=owner, queue=queue, reservation=reservation,
                                 producer=producer, before=first, request=request,
                                 calls=calls, ack=ack, observed=observed,
                                 current_after=(owner._root / "CURRENT").read_bytes().hex(),
                                 journal_after=(owner._root / "journal.jsonl").read_bytes().hex())
                hit_failpoint(output, phase)
                return ack
            owner.publish = cut_publish
        coordinator.publish_once(reservation, owner, request, grant, lease,
                                 artifact=artifact, manifest=manifest_raw,
                                 producer=producer, deadline_ms=lease.expires_ms,
                                 expected_generation=first["generation"])
        raise RuntimeError("CROSS_APP_CUT_NOT_REACHED")
    finally:
        if owner is not None:
            owner.close()
        queue.close()


def _cross_app_cut_recovery(output: Path, handoff_dir: Path, run_id: str,
                            closure: str) -> int:
    """Fresh process lookup/recovery for the two consumer cut contracts."""
    context = json.loads((output / "consumer-cut-state.json").read_bytes())
    if (context.get("schema") != "gt07-cross-app-consumer-cut-1"
            or context.get("run_id") != run_id
            or context.get("source_closure_sha256") != closure):
        raise RuntimeError("CROSS_APP_RECOVERY_CONTEXT_BINDING")
    producer = ProducerReceipt(**context["producer"])
    owner_mod, _, artifact, manifest_raw, handoff = _cross_app_candidate(handoff_dir)
    if producer != _producer_receipt_from_handoff(handoff_dir, handoff, artifact, manifest_raw):
        raise RuntimeError("CROSS_APP_RECOVERY_PRODUCER_CHANGED")
    def no_native(*_args, **_kwargs):
        raise RuntimeError("CROSS_APP_RECOVERY_NATIVE_REPLAY")
    queue = QueueOwner.reopen(context["queue_storage_id"])
    owner = None
    try:
        row = queue.broker.lookup(context["queue_job_id"])
        if (row is None or row.state not in ("RESERVED", "UNKNOWN")
                or row.receipt_sha256 is not None):
            raise RuntimeError("CROSS_APP_RECOVERY_QUEUE_NOT_HELD")
        reservations = tuple(item for item in queue.broker.snapshot().reservations
                             if item.job.job_id == context["queue_job_id"])
        if (len(reservations) != 1
                or {"stream_id": reservations[0].fence.stream_id,
                    "generation": reservations[0].fence.generation}
                   != context["reservation_fence"]):
            raise RuntimeError("CROSS_APP_RECOVERY_FENCE_CHANGED")
        phase = context["phase"]
        root = Path(context["owner_root"])
        if phase == "RELOAD":
            # The owner was killed after native stage but before CURRENT. Its
            # marker/run evidence is intentionally held as ambiguous; only
            # the selected last-good bytes may be claimed here.
            if not (root / "CURRENT").read_bytes() == bytes.fromhex(context["current_before"]):
                raise RuntimeError("CROSS_APP_LAST_GOOD_CURRENT_CHANGED")
            if not (root / "journal.jsonl").read_bytes() == bytes.fromhex(context["journal_before"]):
                raise RuntimeError("CROSS_APP_LAST_GOOD_JOURNAL_CHANGED")
            stage = tuple(path for path in (root / "runs").iterdir()
                          if path.name.startswith(owner_mod._STAGE_PREFIX))
            if not stage:
                raise RuntimeError("CROSS_APP_RELOAD_STAGE_NOT_HELD")
            try:
                owner = owner_mod.GameplaySourcePublicationOwner.reopen(
                    root, project_id="project.cross-app", source_closure_sha256=closure,
                    runner=no_native)
            except owner_mod.GameplaySourceOwnerError as error:
                if error.code != "GAMEPLAY_OWNER_STAGE_AMBIGUOUS":
                    raise
            else:
                raise RuntimeError("CROSS_APP_AMBIGUOUS_REOPEN_NOT_HELD")
            # Verify selected content as well as the selector, after the real
            # owner has refused ambiguous staging without dispatching anything.
            before = context["before"]
            revision = root / "revisions" / before["project_revision"].removeprefix("sha256:") / "project"
            if (any(_sha(revision / name) != expected for name, expected in before["files"].items())
                    or (root / "CURRENT").read_bytes().hex() != context["current_before"]
                    or (root / "journal.jsonl").read_bytes().hex() != context["journal_before"]):
                raise RuntimeError("CROSS_APP_LAST_GOOD_CONTENT_CHANGED")
            result = {"schema": "gt07-cross-app-recovery-1", "run_id": run_id,
                      "phase": phase, "status": "HELD_LAST_GOOD",
                      "owner_reopen": "AMBIGUOUS_STAGE_HELD",
                      "queue_state": row.state, "reservation_retained": True,
                      "last_good_preserved": True, "staging_not_active": True,
                      "native_dispatch_count": context["native_dispatch_count"],
                      "redispatched": False, "public_ack": False,
                      "authority": 0, "errors": []}
        elif phase == "ACK":
            owner = owner_mod.GameplaySourcePublicationOwner.reopen(
                root, project_id="project.cross-app", source_closure_sha256=closure,
                runner=no_native)
            coordinator = CrossAppPublicationCoordinator(queue)
            reservation = coordinator.recover_consumer(
                job_id=context["queue_job_id"], producer=producer,
                command_sha256=row.command_sha256)
            observed = owner.inspect()
            # Read the receipt rebuilt from the owner's verified durable
            # journal, not just the pre-crash harness copy.
            ack = owner._jobs.get(context["request"]["command_id"])
            if ack != context["ack"]:
                raise RuntimeError("CROSS_APP_RECOVERY_ACK_CHANGED")
            receipt = coordinator.reconcile_lookup_only(
                reservation, ack=ack, observed=observed, producer=producer)
            if (receipt.public_ack or receipt.artifact_sha256 != producer.artifact_sha256
                    or queue.broker.lookup(context["queue_job_id"]).state != "COMMITTED"
                    or (root / "CURRENT").read_bytes().hex() != context["current_after"]
                    or (root / "journal.jsonl").read_bytes().hex() != context["journal_after"]):
                raise RuntimeError("CROSS_APP_RECOVERY_READBACK_CHANGED")
            result = {"schema": "gt07-cross-app-recovery-1", "run_id": run_id,
                      "phase": phase, "status": "COMMITTED_LOOKUP_ONLY",
                      "owner_reopen": "DURABLE", "queue_state": "COMMITTED",
                      "reservation_retained": True, "last_good_preserved": False,
                      "staging_not_active": True, "native_dispatch_count": context["native_dispatch_count"],
                      "redispatched": False, "public_ack": False,
                      "receipt": {name: getattr(receipt, name)
                                  for name in receipt.__dataclass_fields__},
                      "authority": 0, "errors": []}
        else:
            raise RuntimeError("CROSS_APP_RECOVERY_PHASE_UNSUPPORTED")
        _save(output / "consumer-cut-recovery.json", result)
        return 0
    finally:
        if owner is not None:
            owner.close()
        queue.close()


def _run_consumer_cut(output: Path, handoff_dir: Path, run_id: str,
                      files: dict[str, str], closure: str, phase: str) -> int:
    """Freeze, cut one consumer process, and run its read-only recovery child."""
    snapshot = _snapshot_sources(output, files, closure)
    arm_failpoint(output, run_id=run_id, phase=phase)
    child = [sys.executable, "-B", str(snapshot / "tests/jobs/run_gt07_cross_app_probe.py"),
             "--frozen", "--output", str(output), "--run-id", run_id,
             "--blender-published", str(handoff_dir), "--closure", closure,
             "--failpoint-phase", phase]
    environment = os.environ.copy()
    environment["HH_GT07_FAILPOINT_ROOT"] = str(output)
    environment["HH_GT07_HANDOFF_ROOT"] = str(handoff_dir.parent.parent)
    environment.pop("HH_GT07_CRASH_GATE", None)
    from studio.tests.jobs.gt07_crash_process import run_cut
    host = run_cut(child, cwd=snapshot, output=output, env=environment,
                   receipt_path=reached_path(output), run_id=run_id, phase=phase)
    recovery_host = None
    recovery = None
    if host.get("cut_verified") is True:
        environment.pop("HH_GT07_FAILPOINT_ROOT", None)
        recovery_child = child + ["--recover-crash"]
        spec = importlib.util.spec_from_file_location(
            "gt07_cross_app_fixture_runner", snapshot / "build/bootstrap/run_fixture.py")
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        recovery_host = runner.run_process(recovery_child, cwd=snapshot, output=output,
                                           timeout=240, label="cross-app-recovery",
                                           env=environment)
        if (output / "consumer-cut-recovery.json").is_file():
            recovery = json.loads((output / "consumer-cut-recovery.json").read_bytes())
    source_unchanged = all(_sha(STUDIO / name) == expected
                           for name, expected in files.items())
    snapshot_unchanged = all(_sha(snapshot / name) == expected
                             for name, expected in files.items())
    report = {"schema": "gt07-cross-app-cut-wrapper-1", "run_id": run_id,
              "phase": phase, "authority": 0, "public_ack": False,
              "host": host, "recovery_host": recovery_host, "recovery": recovery,
              "passed": bool(source_unchanged and snapshot_unchanged
                  and host.get("cut_verified") is True and recovery
                  and recovery_host and recovery_host.get("exit_code") == 0
                  and recovery_host.get("wrapper_exit_code") == 0
                  and recovery_host.get("tree_verified") is True
                  and not recovery_host.get("timed_out")
                  and recovery.get("errors") == []),
              "source_snapshot": str(snapshot), "source_unchanged": source_unchanged,
              "snapshot_unchanged": snapshot_unchanged}
    _save(output / "consumer-cut.json", report)
    return 0 if report["passed"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--blender-published", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--failpoint-phase", choices=("RELOAD", "ACK"))
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--recover-crash", action="store_true")
    parser.add_argument("--closure")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"gt07-cross-app-[a-z0-9-]{1,64}", args.run_id):
        parser.error("use a fresh gt07-cross-app-* id")
    if args.recover_crash and not args.frozen:
        parser.error("--recover-crash is an internal frozen recovery stage")
    if args.frozen:
        if os.environ.get("HH_GT07_CRASH_GATE") == "1" and sys.stdin.readline() != "GO\n":
            return 74
        if not args.closure:
            parser.error("--closure is required for frozen consumer cuts")
        if args.output is None:
            parser.error("--output is required for frozen consumer cuts")
        if args.dry_run:
            parser.error("--dry-run is not valid for a frozen consumer cut")
        if args.recover_crash:
            return _cross_app_cut_recovery(args.output.resolve(),
                                           args.blender_published.resolve(),
                                           args.run_id, args.closure)
        if args.failpoint_phase is None:
            parser.error("--failpoint-phase is required for a frozen consumer cut")
        return _consumer_cut_child(args.output.resolve(),
                                   args.blender_published.resolve(),
                                   args.run_id, args.closure,
                                   args.failpoint_phase)
    if args.output is not None:
        parser.error("--output is internal to frozen consumer cuts")
    from studio.tests.jobs.run_gt07_scenarios import _native_measure_guard
    with _native_measure_guard():
        return _execute(args)


def _execute(args):
    os.environ.setdefault("HH_STUDIO_LINUX_GODOT", str(
        STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64"))
    output = STUDIO / ".local/reviews" / args.run_id
    admission = None
    if output.exists():
        if args.dry_run:
            raise RuntimeError("CROSS_APP_RUN_ID_USED")
        dry_run_path = output / "dry-run.json"
        if not dry_run_path.is_file():
            raise RuntimeError("CROSS_APP_RUN_ID_USED")
        try:
            admission = json.loads(dry_run_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RuntimeError("CROSS_APP_DRY_RUN_INVALID") from error
        if type(admission) is not dict or admission.get("run_id") != args.run_id:
            raise RuntimeError("CROSS_APP_DRY_RUN_INVALID")
    else:
        if not args.dry_run:
            raise RuntimeError("CROSS_APP_DRY_RUN_REQUIRED")
        output.mkdir(parents=True)
    handoff_dir = args.blender_published.absolute()
    artifact, manifest_raw, handoff = base.read_blender_handoff(handoff_dir)
    fixture_args = SimpleNamespace(fixture="gameplay_source_assets",
                                   saved_arena=None,
                                   blender_published=handoff_dir)
    owner_mod = base.load("cross_app_owner", STUDIO / "godot-addon/gameplay_source_owner.py")
    fixtures = base.load("cross_app_fixtures", STUDIO / "tests/godot/linux_probe_fixtures.py")
    probe = base.load("cross_app_linux_probe", STUDIO / "tests/godot/run_linux_probe.py")
    files, closure = _probe_sources(owner_mod, fixture_args)
    executor = owner_mod._load("linux_executor")
    executor._lock()
    binary = executor._binary()
    adapter_closure = _sha(json.dumps(files, sort_keys=True,
                                      separators=(",", ":")).encode())
    case = base._publication_case(fixture_args, owner_mod, fixtures, glb=artifact)
    candidate = probe.case_files(case)
    candidate.pop("project.godot")
    owner_mod._copy_source_bundle(owner_mod._load("gameplay_source_profile"),
                                  candidate, entrypoint=owner_mod.ENTRYPOINT)
    producer = _producer_receipt_from_handoff(
        handoff_dir, handoff, artifact, manifest_raw)
    producer_fields = {name: getattr(producer, name)
                       for name in producer.__dataclass_fields__}
    binding = {"run_id": args.run_id, "authority": 0, "public_ack": False,
               "failpoint_phase": args.failpoint_phase, "binary": str(binary),
               "binary_sha256": executor.BINARY_SHA256,
               "source_closure_sha256": closure, "blender_handoff": handoff,
               "producer_queue_receipt": producer_fields,
               "adapter_source_closure_sha256": adapter_closure,
               "adapter_source_files": files,
               "scope": "queue dependency + one gameplay-source publish; diagnostic only"}
    if admission is not None:
        if (admission.get("source_closure_sha256") != closure
                or (admission.get("blender_handoff") is not None
                    and admission.get("blender_handoff") != handoff)
                or admission.get("failpoint_phase") != args.failpoint_phase
                or admission.get("adapter_source_closure_sha256") != adapter_closure):
            raise RuntimeError("CROSS_APP_DRY_RUN_SOURCE_CHANGED")
        (output / "dry-run.json").replace(output / "admission-dry-run.json")
    _save(output / "binding.json", binding)
    if args.dry_run:
        _save(output / "dry-run.json", {**binding,
              "engine_started": False,
              "candidate_sha256": {name: _sha(raw) for name, raw in candidate.items()},
              "files": files})
        print(json.dumps({"run_id": args.run_id, "dry_run": True,
                          "engine_started": False, "source_closure_sha256": closure},
                         sort_keys=True))
        return 0

    if args.failpoint_phase:
        return _run_consumer_cut(output, handoff_dir, args.run_id, files,
                                 closure, args.failpoint_phase)

    # Match the existing gameplay-source runner's pinned local binary binding.
    # Without this explicit binding, a host-level tool lookup can select a
    # different mount context even when the digest happens to match.
    os.environ.setdefault("HH_STUDIO_LINUX_GODOT", str(
        STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64"))
    # Re-read the protected producer immediately before admitting the consumer.
    # The earlier dry-run/read is only a wiring check; it must not authorize a
    # changed GLB, manifest, or producer receipt.
    fresh_artifact, fresh_manifest, fresh_handoff = base.read_blender_handoff(handoff_dir)
    if (fresh_artifact != artifact or fresh_manifest != manifest_raw
            or fresh_handoff != handoff):
        raise RuntimeError("CROSS_APP_HANDOFF_CHANGED")
    queue_parent = output / "queue"
    queue_parent.mkdir()
    queue = QueueOwner.create(queue_parent)
    owner = reopened = None
    try:
        coordinator = CrossAppPublicationCoordinator(queue)
        coordinator.admit_producer(producer)
        command_sha = _sha((args.run_id + ":consumer").encode())
        reservation = coordinator.enqueue_consumer(job_id="consumer-" + args.run_id,
            producer=producer, command_sha256=command_sha)
        initial = dict(candidate)
        initial[owner_mod.ENTRYPOINT] += b"\n# Initial unpublished cross-app fixture.\n"
        # Keep the owner root directly under the run directory, matching the
        # already verified gameplay-source probe layout.  This also keeps the
        # executor's Windows bind source at the same path depth as its known
        # good counterpart.
        owner_parent = output
        calls = []
        def run_native(project, **kwargs):
            if calls:
                raise RuntimeError("CROSS_APP_SECOND_NATIVE_DISPATCH")
            calls.append(str(kwargs["output"]))
            return owner_mod._load("linux_executor").run(project, **kwargs)
        owner = owner_mod.GameplaySourcePublicationOwner.create(owner_parent,
            project_id="project.cross-app", source_files=initial,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=closure,
            runner=run_native)
        first = owner.inspect()
        credential = owner.issue()
        grant = owner.authorize("Bearer " + credential.bearer, "scene.save")
        lease = owner.lease(grant)
        request = {"command_id": "command.cross-app.1",
                   "expected_project_revision": first["project_revision"],
                   "source_files": candidate, "entrypoint": owner_mod.ENTRYPOINT}
        request["digest"] = owner_mod.request_digest(project_id=owner.project_id,
            **request)
        receipt = coordinator.publish_once(reservation, owner, request, grant, lease,
            artifact=artifact, manifest=manifest_raw, producer=producer,
            deadline_ms=lease.expires_ms, expected_generation=first["generation"])
        selected = owner.inspect()
        root = owner._root
        selected_current = (root / "CURRENT").read_bytes()
        selected_journal = (root / "journal.jsonl").read_bytes()
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(root,
            project_id=owner.project_id, source_closure_sha256=closure,
            runner=run_native)
        if reopened.inspect() != selected:
            raise RuntimeError("CROSS_APP_REOPEN_CHANGED")
        if (root / "CURRENT").read_bytes() != selected_current or (root / "journal.jsonl").read_bytes() != selected_journal:
            raise RuntimeError("CROSS_APP_REOPEN_BYTES_CHANGED")
        result = {"run_id": args.run_id, "authority": 0, "status": "DIAGNOSTIC_PASS",
                  "producer": producer.__dict__ if hasattr(producer, "__dict__") else {
                      name: getattr(producer, name) for name in producer.__dataclass_fields__},
                  "consumer": receipt.__dict__ if hasattr(receipt, "__dict__") else {
                      name: getattr(receipt, name) for name in receipt.__dataclass_fields__},
                  "native_dispatch_count": len(calls), "reopen_equal": True,
                  "public_ack": False, "queue_state": queue.broker.lookup(
                      reservation.job.job_id).state, "source_closure_sha256": closure,
                  "scope": "Blender receipt -> dependency -> one Godot gameplay publish/readback; no public acceptance"}
        _save(output / "result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 0
    finally:
        if reopened is not None:
            reopened.close()
        elif owner is not None:
            owner.close()
        queue.close()


if __name__ == "__main__":
    raise SystemExit(main())
