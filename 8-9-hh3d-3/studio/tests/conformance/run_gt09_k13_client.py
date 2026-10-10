"""Bind measured K13 client metadata to exact K8/K9 producer receipts.

This probe is read-only. K8 publication and K9 repair provenance are accepted
only from their hashed, native readback receipts; a caller supplied boolean or
the registered script's status cannot manufacture authorship.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
SCHEMA = "hh-gt09-mcp-client-receipt-1"
AUTHOR_SCHEMA = "hh-gt09-k13-author-provenance-1"
HEX64 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
RUN_ID = re.compile(r"^gt09-k13-client-[a-z0-9-]{1,80}$")
DEFAULT_EXTERNAL = STUDIO / ".local" / "reviews" / "gt09-mcp-capability-matrix-20261010-k13-v3.json"


class ProvenanceError(ValueError):
    """A missing or contradictory producer fact, reported as a stable code."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _read_json(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ProvenanceError(code + "_MISSING")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProvenanceError(code + "_INVALID_JSON") from exc
    if not isinstance(value, dict):
        raise ProvenanceError(code + "_NOT_OBJECT")
    return value, raw


def _need(value: Any, code: str) -> None:
    if not value:
        raise ProvenanceError(code)


def _hex(value: Any, code: str) -> str:
    _need(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value.removeprefix("sha256:")


def _hash_equals(value: Any, expected: str, code: str) -> None:
    """Require a digest field to bind exactly to an observed input."""
    _need(_hex(value, code) == expected.removeprefix("sha256:"), code)


def _publication(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    result, raw = _read_json(path, label + "_PUBLICATION")
    _need(result.get("status") == "DIAGNOSTIC_PASS", label + "_STATUS")
    _need(result.get("authority") == 0 and result.get("public_ack") is False,
          label + "_AUTHORITY")
    _hex(result.get("source_closure_sha256"), label + "_SOURCE_CLOSURE")
    # K8 emits fixture-specific publication fields.  Arena retains the
    # original ``catalog_handoff`` field, while the room publication is
    # intentionally namespaced as ``catalog_room_handoff``.  Select the
    # expected field explicitly so a room receipt cannot be accidentally
    # satisfied by an arena-shaped alias.
    handoff_key = {"K8_ARENA": "catalog_handoff",
                   "K8_ROOM": "catalog_room_handoff"}.get(label)
    _need(handoff_key is not None, label + "_CATALOG_HANDOFF_LABEL")
    handoff = result.get(handoff_key)
    _need(isinstance(handoff, dict), label + "_CATALOG_HANDOFF_MISSING")
    _need(handoff.get("schema") == "hh-catalog-gameplay-handoff-1",
          label + "_CATALOG_HANDOFF_SCHEMA")
    _need(handoff.get("authority") == 0 and handoff.get("public_ack") is False,
          label + "_HANDOFF_AUTHORITY")
    command_ids = handoff.get("command_ids")
    command_prefix = {"K8_ARENA": "recipe.", "K8_ROOM": "room."}.get(label)
    _need(command_prefix is not None, label + "_CATALOG_HANDOFF_LABEL")
    _need(isinstance(command_ids, list) and command_ids and
          len(command_ids) == len(set(command_ids)) and
          all(isinstance(item, str) and item.startswith(command_prefix) for item in command_ids),
          label + "_RECIPE_COMMAND_IDS")
    transaction = handoff.get("transaction_digest")
    _hex(transaction, label + "_TRANSACTION_DIGEST")
    provenance = handoff.get("provenance")
    _need(isinstance(provenance, dict), label + "_PROVENANCE_MISSING")
    _need(provenance.get("transaction_digest") == transaction and
          provenance.get("authority") == 0 and provenance.get("public_ack") is False,
          label + "_PROVENANCE_BINDING")
    scene_prefix = "catalog_room_scene" if label == "K8_ROOM" else "catalog_scene"
    _need(result.get(scene_prefix + "_instantiation_observed") is True and
          result.get(scene_prefix + "_provenance_unchanged") is True,
          label + "_RECIPE_READBACK")
    receipt = result.get("receipt")
    _need(isinstance(receipt, dict) and receipt.get("status") == "READBACK_ACK" and
          receipt.get("readback_ack") is True and receipt.get("public_ack") is False and
          isinstance(receipt.get("command_id"), str), label + "_RECEIPT")
    return result, raw


def _registered(path: Path) -> tuple[dict[str, Any], bytes]:
    result, raw = _read_json(path, "K9_REGISTERED")
    _need(result.get("schema") == "hh-gt09-registered-script-result-1" and
          result.get("status") == "DIAGNOSTIC_PASS" and
          result.get("authority") == 0 and result.get("public_ack") is False,
          "K9_RESULT_SCHEMA_OR_STATUS")
    _hex(result.get("source_closure_sha256"), "K9_SOURCE_CLOSURE")
    route, repair = result.get("registered_route"), result.get("repair_route")
    _need(isinstance(route, dict) and isinstance(repair, dict), "K9_ROUTE_RECEIPTS_MISSING")
    for name, row in (("ROUTE", route), ("REPAIR", repair)):
        _need(row.get("status") in ("READBACK_ACK", "APPLIED") and
              row.get("authority") == 0 and row.get("public_ack") is False and
              isinstance(row.get("command_id"), str), "K9_" + name + "_ROUTE")
        receipt = row.get("receipt")
        _need(isinstance(receipt, dict) and receipt.get("status") == "READBACK_ACK" and
              receipt.get("readback_ack") is True and receipt.get("public_ack") is False and
              receipt.get("command_id") == row.get("command_id"), "K9_" + name + "_READBACK")
    _need(route["command_id"] != repair["command_id"], "K9_COMMAND_ID_COLLISION")
    _need(result.get("repair_batch_applied") is True and
          result.get("repair_replay_observed") is True and
          result.get("checkpoint_verified") is True and
          isinstance(result.get("repair_replay"), dict) and
          result["repair_replay"].get("fixture_observed") is True,
          "K9_REPAIR_REPLAY_NOT_OBSERVED")
    _need(result.get("seeded_fault_observed") is True and
          isinstance(result.get("seed_error"), str) and
          isinstance(result.get("seed_native"), dict) and
          result["seed_native"].get("diagnostic_process_clean") is False,
          "K9_SEEDED_FAULT_NOT_OBSERVED")
    return result, raw


def _external(path: Path) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    doc, raw = _read_json(path, "K13_EXTERNAL")
    row: dict[str, Any] | None = None
    if doc.get("schema") == "hh-gt09-mcp-capability-matrix-1":
        rows = doc.get("rows")
        _need(isinstance(rows, list), "K13_EXTERNAL_ROWS")
        for candidate in rows:
            if isinstance(candidate, dict) and candidate.get("id") == "hybridindie/godot-mcp":
                row = candidate
                break
        _need(row is not None, "K13_EXTERNAL_HYBRID_ROW_MISSING")
        _need(doc.get("authority") == 0 and doc.get("acceptance") is False,
              "K13_EXTERNAL_AUTHORITY")
    elif doc.get("schema") == "hh-gt09-mcp-native-spike-2":
        row = doc
    else:
        raise ProvenanceError("K13_EXTERNAL_SCHEMA")
    _need(row.get("status") == "INCOMPATIBLE" or row.get("native_gate") == "INCOMPATIBLE",
          "K13_EXTERNAL_NOT_INCOMPATIBLE")
    _need(row.get("supported") is False or row.get("native_gate") == "INCOMPATIBLE",
          "K13_EXTERNAL_SUPPORT_UNPROVEN")
    _need(isinstance(row.get("client"), dict) and isinstance(row.get("host"), dict),
          "K13_EXTERNAL_CLIENT_HOST_MISSING")
    client = row["client"]
    _need(isinstance(client.get("name"), str) and isinstance(client.get("version"), str) and
          isinstance(client.get("model"), str) and isinstance(client.get("protocol"), str),
          "K13_EXTERNAL_CLIENT_METADATA")
    adapter_name = row.get("id") or (row.get("adapter") or {}).get("name")
    _need(isinstance(adapter_name, str) and adapter_name, "K13_EXTERNAL_ADAPTER_METADATA")
    _need(isinstance(row.get("limits"), list) and row.get("limits"), "K13_EXTERNAL_LIMIT_REASON")
    return doc, raw, row


def _author_provenance(path: Path, *, arena_path: Path, room_path: Path,
                       registered_path: Path, source_closure: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate the *actual* author transcript for K8/K9.

    The MCP spike is an adapter observation and cannot identify the client that
    authored K8/K9.  This separately supplied receipt is therefore mandatory
    for a measured client row.  Every event carries a canonical payload hash,
    and its input receipt hash is checked against the files supplied to this
    run.  No client/model value is inferred from the external spike.
    """
    doc, _ = _read_json(path, "K13_AUTHOR_PROVENANCE")
    _need(doc.get("schema") == AUTHOR_SCHEMA, "K13_AUTHOR_SCHEMA")
    _need(doc.get("authority") == 0 and doc.get("public_ack") is False and
          doc.get("acceptance") is False, "K13_AUTHOR_AUTHORITY")
    _hash_equals(doc.get("source_closure_sha256"), source_closure,
                 "K13_AUTHOR_SOURCE_CLOSURE")
    author = doc.get("author")
    _need(isinstance(author, dict), "K13_AUTHOR_MISSING")
    client = author.get("client")
    _need(isinstance(client, dict), "K13_AUTHOR_CLIENT_MISSING")
    for field in ("name", "version", "protocol"):
        _need(isinstance(client.get(field), str) and client[field].strip(),
              "K13_AUTHOR_CLIENT_" + field.upper())
    model = author.get("model")
    _need(isinstance(model, str) and model.strip() and model.upper() != "UNSPECIFIED",
          "K13_AUTHOR_MODEL_MISSING")
    _need(isinstance(author.get("reasoning_effort"), str) and
          author["reasoning_effort"].strip() and
          isinstance(author.get("task_id"), str) and author["task_id"].strip(),
          "K13_AUTHOR_IDENTITY_INCOMPLETE")

    bindings = doc.get("receipt_bindings")
    _need(isinstance(bindings, dict), "K13_AUTHOR_RECEIPT_BINDINGS_MISSING")
    paths = {"arena": arena_path, "room": room_path, "registered": registered_path}
    for label, input_path in paths.items():
        binding = bindings.get(label)
        _need(isinstance(binding, dict), "K13_AUTHOR_" + label.upper() + "_BINDING_MISSING")
        _hash_equals(binding.get("sha256"), _sha(input_path),
                     "K13_AUTHOR_" + label.upper() + "_BINDING_HASH")

    events = doc.get("events")
    _need(isinstance(events, list) and len(events) == 3, "K13_AUTHOR_EVENTS")
    by_kind: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        _need(isinstance(event, dict), "K13_AUTHOR_EVENT_OBJECT")
        kind, fixture = event.get("kind"), event.get("fixture")
        _need((kind, fixture) in (("recipe", "arena"), ("recipe", "room"),
                                  ("repair_batch", "room")),
              "K13_AUTHOR_EVENT_KIND")
        key = (kind, fixture)
        _need(key not in by_kind, "K13_AUTHOR_EVENT_DUPLICATE")
        payload = event.get("payload")
        _need(isinstance(payload, dict), "K13_AUTHOR_EVENT_PAYLOAD")
        payload_hash = _canonical_sha(payload)
        _hash_equals(event.get("payload_sha256"), payload_hash,
                     "K13_AUTHOR_EVENT_PAYLOAD_HASH")
        receipt_label = "arena" if fixture == "arena" else "room" if kind == "recipe" else "registered"
        _hash_equals(event.get("receipt_sha256"), bindings[receipt_label]["sha256"],
                     "K13_AUTHOR_EVENT_RECEIPT_HASH")
        by_kind[key] = event

    arena_event = by_kind[("recipe", "arena")]
    room_event = by_kind[("recipe", "room")]
    repair_event = by_kind[("repair_batch", "room")]
    # Bind event payloads to the exact command/transaction receipts.  A
    # caller cannot label arbitrary text as a recipe or repair batch.
    for event, result, handoff_key in ((arena_event, _publication(arena_path, "K8_ARENA")[0], "catalog_handoff"),
                                       (room_event, _publication(room_path, "K8_ROOM")[0], "catalog_room_handoff")):
        payload = event["payload"]
        handoff = result[handoff_key]
        _need(payload.get("command_ids") == handoff["command_ids"] and
              payload.get("transaction_digest") == handoff["transaction_digest"],
              "K13_AUTHOR_RECIPE_BINDING")
    registered = _registered(registered_path)[0]
    repair_payload = repair_event["payload"]
    _need(repair_payload.get("command_ids") == [registered["registered_route"]["command_id"],
                                                   registered["repair_route"]["command_id"]] and
          repair_payload.get("repair_batch_applied") is True and
          repair_payload.get("repair_replay_observed") is True and
          repair_payload.get("checkpoint_verified") is True,
          "K13_AUTHOR_REPAIR_BINDING")
    transcript = doc.get("transcript")
    _need(isinstance(transcript, dict) and transcript.get("events") == events and
          transcript.get("author") == author and
          transcript.get("source_closure_sha256") == doc.get("source_closure_sha256"),
          "K13_AUTHOR_TRANSCRIPT")
    _hash_equals(doc.get("transcript_sha256"), _canonical_sha(transcript),
                 "K13_AUTHOR_TRANSCRIPT_HASH")
    return doc, author


def _measure(*, run_id: str, arena_path: Path | None, room_path: Path | None,
             registered_path: Path | None, external_path: Path | None,
             author_path: Path | None) -> dict[str, Any]:
    if RUN_ID.fullmatch(run_id) is None:
        raise ProvenanceError("K13_RUN_ID")
    if not arena_path or not room_path or not registered_path:
        raise ProvenanceError("K13_CLIENT_PROVENANCE_ARGS_REQUIRED")
    if not author_path:
        raise ProvenanceError("K13_AUTHOR_PROVENANCE_REQUIRED")
    arena, _ = _publication(arena_path, "K8_ARENA")
    room, _ = _publication(room_path, "K8_ROOM")
    registered, _ = _registered(registered_path)
    external_path = external_path or DEFAULT_EXTERNAL
    _, _, external = _external(external_path)
    closures = {arena["source_closure_sha256"], room["source_closure_sha256"],
                registered["source_closure_sha256"]}
    _need(len(closures) == 1, "K13_SOURCE_CLOSURE_MISMATCH")
    source_closure = next(iter(closures))
    author_doc, author = _author_provenance(
        author_path, arena_path=arena_path, room_path=room_path,
        registered_path=registered_path, source_closure=source_closure)
    # The external spike describes only the transport adapter.  It is kept in
    # a separate field so its model cannot be mistaken for the K8/K9 author.
    client = dict(author["client"])
    client["model"] = author["model"]
    host = dict(external["host"])
    adapter = external.get("id") or (external.get("adapter") or {}).get("name")
    protocol = client["protocol"]
    transcript = {
        "author_transcript_sha256": _hex(author_doc["transcript_sha256"],
                                          "K13_AUTHOR_TRANSCRIPT_HASH"),
        "author_events": author_doc["events"],
        "author": author,
        "arena_receipt": arena["receipt"],
        "room_receipt": room["receipt"],
        "registered_receipts": {
            "registered": registered["registered_route"]["receipt"],
            "repair": registered["repair_route"]["receipt"],
        },
        "source_closure_sha256": source_closure,
        "adapter": adapter,
        "protocol": protocol,
    }
    return {
        "schema": SCHEMA, "run_id": run_id, "status": "MEASURED_INCOMPATIBLE",
        "authority": 0, "public_ack": False, "acceptance": False,
        "client": client, "model": author["model"], "author": author,
        "external_client": external["client"], "host": host,
        "adapter": adapter, "protocol": protocol,
        "external_protocol": external["client"].get("protocol"),
        "external_status": external.get("status") or external.get("native_gate"),
        "external_limits": list(external["limits"]),
        "external_evidence_sha256": _sha(external_path),
        "external_evidence": str(external_path.resolve()),
        "source_closure_sha256": source_closure,
        "recipe_observed": True, "batch_observed": True,
        "recipe_provenance": {
            "arena_result_sha256": _sha(arena_path), "room_result_sha256": _sha(room_path),
            "arena_transaction_digest": arena["catalog_handoff"]["transaction_digest"],
            "room_transaction_digest": room["catalog_room_handoff"]["transaction_digest"],
            "arena_command_ids": arena["catalog_handoff"]["command_ids"],
            "room_command_ids": room["catalog_room_handoff"]["command_ids"],
        },
        "batch_provenance": {
            "registered_result_sha256": _sha(registered_path),
            "command_ids": [registered["registered_route"]["command_id"],
                            registered["repair_route"]["command_id"]],
            "repair_batch_applied": registered["repair_batch_applied"],
            "repair_replay_observed": registered["repair_replay_observed"],
        },
        "author_provenance": {
            "path": str(author_path.resolve()), "sha256": _sha(author_path),
            "transcript_sha256": _hex(author_doc["transcript_sha256"],
                                       "K13_AUTHOR_TRANSCRIPT_HASH"),
        },
        "transcript_sha256": _canonical_sha(transcript), "transcript": transcript,
        "input_sha256": {
            "arena_publication": _sha(arena_path), "room_publication": _sha(room_path),
            "registered_result": _sha(registered_path), "external_evidence": _sha(external_path),
            "author_provenance": _sha(author_path),
        },
        "limitations": [
            "External adapter is measured INCOMPATIBLE because its native spike lacks the HH lease/journal/semantic command boundary.",
            "This authority-zero row binds producer receipts; it does not promote K8/K9 acceptance or claim public compatibility.",
        ],
        "remaining_native_external_work": [
            "NPGameDev/godot-mcp-toolkit remains transport-only; run its pinned native fixture with HH lease, journal, semantic command-ID and postcondition gates.",
            "The hybridindie/godot-mcp native row needs a clean rerun if compatibility is required, including the K8-K12 client/model matrix and cleanup proof.",
            "Record a non-UNSPECIFIED model and host transcript for each external native run; transport metadata cannot serve as authorship provenance.",
        ],
    }


def _failure(run_id: str, error: Exception) -> dict[str, Any]:
    code = str(error) if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", str(error)) else type(error).__name__
    return {"schema": SCHEMA, "run_id": run_id, "status": "DIAGNOSTIC_FAIL",
            "authority": 0, "public_ack": False, "acceptance": False,
            "recipe_observed": False, "batch_observed": False, "error_code": code,
            "reason": "K13 client row requires a current-task author transcript plus hashed K8 recipe and K9 repair provenance; provide the missing receipt or fix the reported binding."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arena-publication", type=Path)
    parser.add_argument("--room-publication", type=Path)
    parser.add_argument("--registered-result", type=Path)
    parser.add_argument("--author-provenance", type=Path,
                        help="hashed current-task transcript binding K8 recipes and K9 repair")
    parser.add_argument("--k13-evidence", "--external-evidence", dest="external_evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        report = _failure(args.run_id, ProvenanceError("K13_CLIENT_OUTPUT_EXISTS"))
        print(json.dumps(report, sort_keys=True))
        return 2
    try:
        report = _measure(run_id=args.run_id, arena_path=args.arena_publication,
                          room_path=args.room_publication, registered_path=args.registered_result,
                          external_path=args.external_evidence,
                          author_path=args.author_provenance)
        code = 0
    except Exception as error:
        report, code = _failure(args.run_id, error), 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    summary = {"schema": SCHEMA, "status": report["status"], "authority": 0}
    if "error_code" in report:
        summary["error_code"] = report["error_code"]
    print(json.dumps(summary, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
