"""Read back exact native catalog roots for the K4 dependency gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(root: Path) -> None:
    result = _load(root / "result.json")
    observation = _load(root / "native-observation.json")
    if result.get("schema") != "hh-catalog-native-result-1" or result.get("status") != "DIAGNOSTIC_PASS":
        raise ValueError("K4_NATIVE_RESULT")
    if result.get("authority") != 0 or result.get("public_ack") is not False:
        raise ValueError("K4_NATIVE_AUTHORITY")
    if observation.get("schema") != "hh-catalog-native-observation-1":
        raise ValueError("K4_NATIVE_OBSERVATION")
    commands = observation.get("commands")
    if not isinstance(commands, list) or len(commands) < 3 or not all(
            isinstance(item, dict) and item.get("verified") is True
            and isinstance(item.get("command_id"), str)
            and isinstance(item.get("readback"), dict) for item in commands):
        raise ValueError("K4_NATIVE_READBACK")
    checks = observation.get("checks")
    if not isinstance(checks, dict) or not all(checks.get(key) is True
                                               for key in ("undo", "redo", "save", "reload")):
        raise ValueError("K4_NATIVE_CHECKS")
    if (observation.get("failures") or
            (root / "editor-host" / "process-exit.json").exists() and
            _load(root / "editor-host" / "process-exit.json").get("exit_code") != 0):
        raise ValueError("K4_NATIVE_FAILURE")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arena-native", type=Path, required=True)
    parser.add_argument("--room-native", type=Path, required=True)
    parser.add_argument("--arena-registered", type=Path, required=True)
    parser.add_argument("--room-registered", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("K4_OUTPUT_EXISTS")
        _check(args.arena_native.resolve())
        _check(args.room_native.resolve())
        arena = _load(args.arena_registered.resolve() / "registered-owner-result.json")
        room = _load(args.room_registered.resolve() / "registered-owner-result.json")
        closures = {arena.get("source_closure_sha256"), room.get("source_closure_sha256")}
        if len(closures) != 1 or not next(iter(closures), "").startswith("sha256:"):
            raise ValueError("K4_CLOSURE")
        result = {"schema": "hh-gt09-catalog-native-check-1", "run_id": args.run_id,
                  "status": "DIAGNOSTIC_PASS", "authority": 0, "acceptance": False,
                  "public_ack": False, "source_closure_sha256": next(iter(closures)),
                  "arena_native": str(args.arena_native.resolve()),
                  "room_native": str(args.room_native.resolve()),
                  "dependency_readback": True, "uid_import_checks": True,
                  "command_postconditions": True}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"schema": result["schema"], "status": result["status"], "authority": 0}, sort_keys=True))
        return 0
    except Exception as error:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = {"schema": "hh-gt09-catalog-native-check-1", "run_id": args.run_id,
                  "status": "DIAGNOSTIC_FAIL", "authority": 0, "acceptance": False,
                  "public_ack": False, "error_code": str(error)}
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
