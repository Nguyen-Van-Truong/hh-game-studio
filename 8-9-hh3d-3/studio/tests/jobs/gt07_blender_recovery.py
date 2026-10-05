"""Read-only producer recovery at real GT07 Blender publication crash cuts.

The native harness kills the host holding the phase. A fresh Python process
opens the protected publisher and queue, without starting Blender or resending
the command. This is a producer-side diagnostic, not cross-app recovery/ACK.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

PHASES = {"PREPARED": "INTENT", "VALIDATED": "STAGED",
          "ACTIVATING": "SELECTING", "COMMITTED": "TERMINAL", "ACK": "TERMINAL"}


def _value(value):
    return json.loads(json.dumps(value, sort_keys=True))


def _need(value, code):
    if not value:
        raise ValueError(code)


def observe(publisher):
    state = publisher._refresh()
    intent = state.get("intent")
    response = (publisher.lookup_bytes(intent["request"]["command_id"], intent["request_sha256"])
                if intent else None)
    files = {}
    for path in sorted(publisher.files.root.iterdir()):
        if path.name == ".writer":
            continue
        version, raw = publisher.files.read(path.name)
        publisher.files.confirm_barrier(path.name, version)
        files[path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    selected = None
    if state["phase"] == "TERMINAL":
        manifest, artifacts = publisher.read_selected()
        selected = {"manifest": manifest, "artifacts": {
            name: hashlib.sha256(raw).hexdigest() for name, raw in artifacts.items()}}
    return _value({"state": state, "head": asdict(publisher.log.binding().witnessed),
                   "response": json.loads(response) if response else None,
                   "files": files, "selected": selected})


def validate_cut(phase, observation):
    """Assert phase meaning, including the absence of an early active selector."""
    _need(phase in PHASES and observation["state"]["phase"] == PHASES[phase],
          "BLENDER_CUT_PHASE_MISMATCH")
    committed = PHASES[phase] == "TERMINAL"
    _need(observation["response"]["status"] == ("COMMITTED" if committed else "UNKNOWN"),
          "BLENDER_CUT_RESPONSE_MISMATCH")
    _need(observation["response"]["public_ack"] is False, "BLENDER_CUT_PUBLIC_ACK")
    _need(("active.json" in observation["files"]) == committed
          and (observation["selected"] is not None) == committed,
          "BLENDER_CUT_EARLY_SELECTION")
    if phase in ("VALIDATED", "ACTIVATING", "COMMITTED", "ACK"):
        _need({"checkpoint.blend", "scene.glb", "manifest.json"} <= set(observation["files"]),
              "BLENDER_CUT_STAGED_FILES_MISSING")


def capture(output, publisher, queue, job_id, *, run_id, closure, phase):
    observed = observe(publisher)
    validate_cut(phase, observed)
    record = queue.broker.lookup(job_id)
    _need(record is not None and record.state == "RESERVED" and record.receipt_sha256 is None,
          "BLENDER_CUT_QUEUE_ALREADY_ACKED")
    payload = {"run_id": run_id, "source_closure_sha256": closure, "phase": phase,
               "publisher_storage_id": publisher.storage_id, "queue_storage_id": queue.storage_id,
               "job_id": job_id, "queue_record": asdict(record),
               "queue_head": asdict(queue.log.binding().witnessed), "publication": observed}
    # Receipt is published by the existing failpoint only after this file closes.
    with (output / "blender-cut-state.json").open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2)
        stream.write("\n")


def recover(output, *, run_id, closure):
    from studio.host.blender.publication_owner import BlenderPublicationOwner
    from studio.host.blender.publication_state import PublicationError
    from studio.host.jobs.queue_owner import QueueOwner
    checks, errors = {}, []
    publisher = queue = None
    try:
        saved = json.loads((output / "blender-cut-state.json").read_bytes())
        _need(saved["run_id"] == run_id and saved["source_closure_sha256"] == closure,
              "BLENDER_RECOVERY_SOURCE_BINDING")
        publisher = BlenderPublicationOwner.reopen(saved["publisher_storage_id"])
        queue = QueueOwner.reopen(saved["queue_storage_id"])
        observed = observe(publisher)
        validate_cut(saved["phase"], observed)
        checks["publication_unchanged"] = observed == saved["publication"]
        row = queue.broker.lookup(saved["job_id"])
        checks["queue_record_unchanged"] = row is not None and _value(asdict(row)) == saved["queue_record"]
        checks["queue_head_unchanged"] = _value(asdict(queue.log.binding().witnessed)) == saved["queue_head"]
        reservations = queue.broker.snapshot().reservations
        checks["reservation_held_no_queue_ack"] = (len(reservations) == 1
            and reservations[0].job.job_id == saved["job_id"] and reservations[0].recovered
            and row is not None and row.state == "RESERVED" and row.receipt_sha256 is None)
        if observed["selected"] is None:
            try:
                publisher.read_selected()
            except PublicationError as error:
                checks["uncommitted_selection_rejected"] = error.code == "PUBLICATION_NOT_COMMITTED"
            else:
                checks["uncommitted_selection_rejected"] = False
        else:
            checks["committed_assets_read_back"] = set(observed["selected"]["artifacts"]) == {
                "checkpoint.blend", "scene.glb"}
        checks["read_only_no_engine"] = publisher._readonly and publisher.host is None and publisher.session is None
        checks["repeat_lookup_no_effect"] = observe(publisher) == observed
        checks["queue_still_held"] = (queue.broker.lookup(saved["job_id"]) == row
            and _value(asdict(queue.log.binding().witnessed)) == saved["queue_head"])
    except Exception as error:
        errors.append({"type": type(error).__name__, "code": getattr(error, "code", str(error))})
    finally:
        for owner in (queue, publisher):
            if owner is not None:
                try:
                    owner.close()
                except Exception as error:
                    errors.append({"type": type(error).__name__, "code": getattr(error, "code", str(error))})
    report = {"run_id": run_id, "source_closure_sha256": closure, "authority": 0,
              "formal_acceptance": False, "public_ack": False, "checks": checks,
              "errors": errors, "passed": bool(checks) and all(checks.values()) and not errors,
              "scope": "read-only producer recovery; cross-app last-good/reload/ACK unproven"}
    (output / "blender-crash-recovery.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1
