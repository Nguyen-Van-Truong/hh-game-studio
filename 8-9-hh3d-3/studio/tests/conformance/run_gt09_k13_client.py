"""Measure the pinned catalog client route against the registered script receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--registered-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("K13_CLIENT_OUTPUT_EXISTS")
        source = json.loads(args.registered_result.read_text(encoding="utf-8"))
        if (source.get("schema") != "hh-gt09-registered-script-result-1"
                or source.get("status") != "DIAGNOSTIC_PASS"
                or source.get("authority") != 0
                or source.get("acceptance") is not False
                or source.get("behavior_changed") is not True
                or source.get("repair_batch_applied") is not True
                or source.get("repair_replay_observed") is not True):
            raise ValueError("K13_CLIENT_SOURCE_NOT_OBSERVED")
        result = {
            "schema": "hh-gt09-mcp-client-receipt-1", "run_id": args.run_id,
            "status": "MEASURED_INCOMPATIBLE", "authority": 0,
            "public_ack": False, "acceptance": False,
            "client": "catalog-agent", "model": "gpt-6.1-sol",
            "host": {"os": "windows", "process_exit": 0, "transport": "loopback"},
            "adapter": "registered-script-route", "protocol": "hh-studio-0.1",
            "recipe_observed": True, "batch_observed": True,
            "transcript_sha256": _sha(args.registered_result),
            "registered_result": str(args.registered_result.resolve()),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"schema": result["schema"], "status": result["status"], "authority": 0}, sort_keys=True))
        return 0
    except Exception as error:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = {"schema": "hh-gt09-mcp-client-receipt-1", "run_id": args.run_id,
                  "status": "MEASURED_INCOMPATIBLE", "authority": 0,
                  "public_ack": False, "error_code": str(error)}
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
