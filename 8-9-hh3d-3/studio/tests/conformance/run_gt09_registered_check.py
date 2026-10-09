"""Host-side readback check for the two in-run registered catalog probes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _load(root: Path) -> dict:
    return json.loads((root / "registered-owner-result.json").read_text(encoding="utf-8"))


def _check(value: dict, fixture: str) -> None:
    if value.get("schema") != "hh-godot-registered-authoring-owner-1":
        raise ValueError("REGISTERED_CHECK_SCHEMA")
    if value.get("status") != "DIAGNOSTIC_PASS" or value.get("fixture") != fixture:
        raise ValueError("REGISTERED_CHECK_STATUS")
    if value.get("authority") != 0 or value.get("public_ack") is not False:
        raise ValueError("REGISTERED_CHECK_AUTHORITY")
    discovery = value.get("discovery") or {}
    profile = value.get("profile") or {}
    tx = value.get("transaction") or {}
    receipt = value.get("receipt") or {}
    if discovery.get("fixture_enabled") is not True or discovery.get("public_runtime_enabled") is not False:
        raise ValueError("REGISTERED_CHECK_DISCOVERY")
    if profile.get("script_enabled") is not True:
        raise ValueError("REGISTERED_CHECK_PROFILE")
    if not isinstance(tx.get("command_ids"), list) or len(tx["command_ids"]) < 3:
        raise ValueError("REGISTERED_CHECK_COMMANDS")
    if receipt.get("readback_ack") is not True or receipt.get("native_observed") is not True:
        raise ValueError("REGISTERED_CHECK_READBACK")
    if (receipt.get("native_process") or {}).get("exit_code") != 0:
        raise ValueError("REGISTERED_CHECK_EXIT")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arena-root", type=Path, required=True)
    parser.add_argument("--room-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("REGISTERED_CHECK_OUTPUT_EXISTS")
        arena = _load(args.arena_root.resolve())
        room = _load(args.room_root.resolve())
        _check(arena, "arena")
        _check(room, "room")
        if arena["transaction"]["command_ids"] == room["transaction"]["command_ids"]:
            raise ValueError("REGISTERED_CHECK_COMMAND_COLLISION")
        closures = {arena.get("source_closure_sha256"), room.get("source_closure_sha256")}
        if len(closures) != 1 or not next(iter(closures)).startswith("sha256:"):
            raise ValueError("REGISTERED_CHECK_CLOSURE")
        result = {
            "schema": "hh-gt09-registered-check-1", "run_id": args.run_id,
            "status": "DIAGNOSTIC_PASS", "authority": 0, "acceptance": False,
            "public_ack": False, "source_closure_sha256": next(iter(closures)),
            "arena_root": str(args.arena_root.resolve()),
            "room_root": str(args.room_root.resolve()),
            "transaction_ids_distinct": True,
            "readback_verified": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"schema": result["schema"], "status": result["status"], "authority": 0}, sort_keys=True))
        return 0
    except Exception as error:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = {"schema": "hh-gt09-registered-check-1", "run_id": args.run_id,
                  "status": "DIAGNOSTIC_FAIL", "authority": 0, "acceptance": False,
                  "public_ack": False, "error_code": str(error)}
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
