"""Build a fail-closed GT09 MCP/client capability matrix.

This verifier consumes an already completed private-adapter receipt.  It does
not start Godot, Blender, Docker, an MCP server, or a network client.  The
private Python adapter is deliberately kept separate from the two pinned
external MCP repositories: their README/security material is sequencing
input, not compatibility evidence.  Consequently this command normally
returns an incomplete matrix until a separately admitted external spike is
captured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "hh-gt09-mcp-capability-matrix-1"
PRIVATE_ADAPTER_SCHEMA = "hh-gameplay-source-adapter-1"
PINNED_EXTERNAL = (
    {
        "name": "NPGameDev/godot-mcp-toolkit",
        "pin": "10a4508e880244c66a3f04861b2e22872c307247",
        "transport": "external-mcp",
    },
    {
        "name": "hybridindie/godot-mcp",
        "pin": "48f34e7d28d65cfea456cc2641e13c3058caa3d6",
        "transport": "external-mcp",
    },
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"object required: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_private_receipt(path: Path) -> dict[str, Any]:
    """Check measured private-adapter facts without trusting status banners.

    The native result is still authority-zero.  Every field used here is a
    postcondition emitted by the owner/adapter probe and is cross-checked with
    actual native paths and exits.  A caller cannot turn a public discovery
    marker into a supported MCP capability.
    """
    result = _load(path)
    required = {
        "run_id", "status", "authority", "public_ack", "source_closure_sha256",
        "native_paths", "native_run_count", "native_exits", "native_fixture_observed",
        "context_reset_lookup_only", "reconnect_lookup_only",
        "unsupported_client_rejected", "public_discovery_empty",
        "owner_edit_preserved", "source_unchanged", "native_raw_unchanged",
        "durable_state_unchanged", "full_mcp_conformance", "parallel_native_conformance",
    }
    _need(required <= set(result), "private_receipt_missing:" + ",".join(sorted(required - set(result))))
    _need(type(result["run_id"]) is str and result["run_id"], "private_receipt_run_id")
    _need(result["status"] == "DIAGNOSTIC_PASS", "private_receipt_status")
    _need(result["authority"] == 0 and result["public_ack"] is False, "private_receipt_authority")
    _need(result["full_mcp_conformance"] is False, "private_receipt_mcp_claim")
    _need(result["parallel_native_conformance"] is False, "private_receipt_parallel_claim")
    _need(type(result["source_closure_sha256"]) is str and len(result["source_closure_sha256"]) == 64,
          "private_receipt_source_closure")
    paths = result["native_paths"]
    exits = result["native_exits"]
    _need(type(paths) is list and len(paths) == result["native_run_count"] == len(exits) >= 1,
          "private_receipt_native_count")
    for index, row in enumerate(exits):
        _need(type(row) is dict, f"private_receipt_exit:{index}")
        _need(row.get("command_host_exit") == 0 and row.get("container_exit") == 0
              and row.get("docker_wait_exit") == 0 and row.get("timed_out") is False,
              f"private_receipt_exit:{index}")
    for key in (
        "native_fixture_observed", "context_reset_lookup_only", "reconnect_lookup_only",
        "unsupported_client_rejected", "public_discovery_empty", "owner_edit_preserved",
        "source_unchanged", "native_raw_unchanged", "durable_state_unchanged",
    ):
        _need(result[key] is True, f"private_receipt_postcondition:{key}")
    return {
        "path": path.as_posix(),
        "sha256": _sha256(path),
        "run_id": result["run_id"],
        "source_closure_sha256": result["source_closure_sha256"],
        "native_run_count": result["native_run_count"],
    }


def _capabilities(private: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_discovery": False,
        "private_readback": True,
        "private_publish": True,
        "reconnect_lookup_only": True,
        "context_reset_lookup_only": True,
        "unsupported_client_rejected": True,
        "owner_edit_conflict_preserved": True,
        "duplicate_native_dispatch": False,
    }


def build_matrix(receipt: Path) -> dict[str, Any]:
    private = verify_private_receipt(receipt)
    rows: list[dict[str, Any]] = [{
        "id": "hh-private-python-adapter",
        "status": "MEASURED_PRIVATE",
        "authority": 0,
        "transport": "in-process-private-owner",
        "client": "hh-gameplay-source-adapter-1",
        "client_version": "pc-godot-4.7.2",
        "model": "UNSPECIFIED",
        "host": "UNSPECIFIED",
        "receipt": private,
        "capabilities": _capabilities(private),
        "limits": [
            "private adapter is not an MCP server/client compatibility claim",
            "public catalog remains disabled",
            "model and host were not recorded by this probe",
        ],
    }]
    for item in PINNED_EXTERNAL:
        rows.append({
            "id": item["name"],
            "status": "UNMEASURED",
            "authority": 0,
            "transport": item["transport"],
            "pin": item["pin"],
            "capabilities": {
                "read_only_default": "UNMEASURED",
                "authenticated_transport": "UNMEASURED",
                "postcondition_readback": "UNMEASURED",
                "reconnect_retry": "UNMEASURED",
                "unsupported_client_rejection": "UNMEASURED",
                "arbitrary_code_denial": "UNMEASURED",
            },
            "limits": [
                "pinned documentation is not a native fixture run",
                "not installed or executed by this package",
                "no HH lease/journal/command-ID mapping established",
            ],
        })
    rows.append({
        "id": "hh-public-catalog",
        "status": "DISABLED",
        "authority": 0,
        "transport": "catalog",
        "capabilities": {"public_discovery": False},
        "limits": ["adapter discovery returned an empty public capability tuple"],
    })
    complete = all(row["status"] not in {"UNMEASURED", "DISABLED"} for row in rows)
    return {
        "schema": SCHEMA,
        "authority": 0,
        "acceptance": False,
        "status": "COMPLETE" if complete else "INCOMPLETE_EXTERNAL_SPIKE",
        "generated_by": "gt09_mcp_compatibility.py",
        "private_receipt": private,
        "rows": rows,
        "requirements": {
            "external_pinned_mcp_spike": "OPEN",
            "model_host_capability_matrix": "OPEN",
            "two_critics_same_final_hash": "OPEN",
        },
        "interpretation": (
            "Private adapter reconnect and rejection facts are measured; no external MCP "
            "compatibility or public capability is claimed."
        ),
    }


def verify_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if matrix.get("schema") != SCHEMA:
        errors.append("schema")
    if matrix.get("authority") != 0 or matrix.get("acceptance") is not False:
        errors.append("authority_or_acceptance")
    rows = matrix.get("rows")
    if type(rows) is not list or len(rows) != 4:
        return errors + ["rows"]
    ids = {row.get("id") for row in rows if type(row) is dict}
    if ids != {"hh-private-python-adapter", "NPGameDev/godot-mcp-toolkit",
               "hybridindie/godot-mcp", "hh-public-catalog"}:
        errors.append("row_ids")
    for row in rows:
        if type(row) is not dict or row.get("authority") != 0:
            errors.append("row_authority")
        if row.get("id") != "hh-private-python-adapter" and row.get("status") != "UNMEASURED" and row.get("id") != "hh-public-catalog":
            errors.append("external_status")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    matrix = build_matrix(args.receipt)
    errors = verify_matrix(matrix)
    if errors:
        raise SystemExit("invalid_matrix:" + ",".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matrix, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps({"status": matrix["status"], "output": args.output.as_posix(),
                      "authority": matrix["authority"]}, sort_keys=True))
    # An incomplete external spike is an intentional non-zero gate result.
    return 0 if matrix["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
