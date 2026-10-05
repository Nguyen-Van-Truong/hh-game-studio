"""Native authority-zero Blender -> Godot queue publication probe.

The Blender publication is an already verified terminal handoff.  This probe
binds that receipt as a durable dependency, runs exactly one gameplay-source
Godot publication, and records the queue result only after CURRENT/journal and
readback have been checked.  It is diagnostic evidence for M3, not acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.jobs.queue_owner import QueueOwner
from studio.tests.jobs.cross_app_publication import (CrossAppPublicationCoordinator,
    ProducerReceipt)
from studio.tests.godot import run_gameplay_publication_probe as base


def _sha(raw: bytes) -> str:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--blender-published", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.run_id.startswith("gt07-cross-app-"):
        parser.error("use a fresh gt07-cross-app-* id")
    output = STUDIO / ".local/reviews" / args.run_id
    if output.exists():
        raise RuntimeError("CROSS_APP_RUN_ID_USED")
    output.mkdir(parents=True)
    handoff_dir = args.blender_published.absolute()
    artifact, manifest_raw, handoff = base.read_blender_handoff(handoff_dir)
    fixture_args = SimpleNamespace(fixture="gameplay_source_assets",
                                   saved_arena=None,
                                   blender_published=handoff_dir)
    owner_mod = base.load("cross_app_owner", STUDIO / "godot-addon/gameplay_source_owner.py")
    fixtures = base.load("cross_app_fixtures", STUDIO / "tests/godot/linux_probe_fixtures.py")
    probe = base.load("cross_app_linux_probe", STUDIO / "tests/godot/run_linux_probe.py")
    files, closure = base._probe_sources(owner_mod, fixture_args)
    files["tests/jobs/cross_app_publication.py"] = _sha(
        (STUDIO / "tests/jobs/cross_app_publication.py").read_bytes())
    # The adapter imports the durable queue directly.  Keep those trusted
    # runtime files in the diagnostic closure instead of hashing only the
    # gameplay owner fixture and silently allowing queue drift.
    for name in (
            "tests/jobs/run_gt07_cross_app_probe.py",
            "host/jobs/queue_owner.py", "host/jobs/durable_broker.py",
            "host/jobs/dispatch_policy.py", "host/jobs/native_dispatch.py",
            "host/core/private_events.py", "host/core/private_store.py",
            "host/core/custody.py", "host/core/custody_registry.py",
            "host/core/safe_replace.py", "host/core/safe_open.py",
            "host/core/limits.py", "host/core/transport.py"):
        files[name] = _sha((STUDIO / name).read_bytes())
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
               "source_closure_sha256": closure, "blender_handoff": handoff,
               "producer_queue_receipt": producer_fields,
               "adapter_source_closure_sha256": adapter_closure,
               "adapter_source_files": files,
               "scope": "queue dependency + one gameplay-source publish; diagnostic only"}
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

    # Match the existing gameplay-source runner's pinned local binary binding.
    # Without this explicit binding, a host-level tool lookup can select a
    # different mount context even when the digest happens to match.
    import os
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
