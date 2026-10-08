"""Build a fail-closed GT09 MCP/client capability matrix.

This verifier consumes an already completed private-adapter receipt and an
optional measured external-stdio receipt.  It does not start Godot, Blender,
Docker, an MCP server, or a network client.  The
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
EXTERNAL_SPIKE_SCHEMA = "hh-gt09-mcp-external-spike-1"
NATIVE_ATTEMPT_SCHEMA = "hh-gt09-mcp-native-attempt-1"
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


def verify_external_receipt(path: Path) -> dict[str, Any]:
    """Validate a bounded, transport-only external MCP probe.

    This deliberately does *not* turn a successful stdio handshake into product
    support.  Both pinned repositories must have real process exits and a
    reconnect/context-reset lookup, while the native fixture and lease gates
    remain explicitly open.  The receipt is produced by
    ``run_gt09_mcp_spike.py`` and contains no raw environment secrets.
    """
    result = _load(path)
    required = {"schema", "run_id", "authority", "transport", "engine_launched",
                "host", "client", "servers", "scope"}
    _need(required <= set(result), "external_receipt_missing:" + ",".join(sorted(required - set(result))))
    _need(result["schema"] == EXTERNAL_SPIKE_SCHEMA, "external_receipt_schema")
    _need(result["authority"] == 0, "external_receipt_authority")
    _need(result["transport"] == "stdio", "external_receipt_transport")
    _need(result["engine_launched"] is False, "external_receipt_engine")
    _need(result["scope"] == "transport_only_no_native_fixture", "external_receipt_scope")
    _need(type(result["run_id"]) is str and result["run_id"], "external_receipt_run_id")
    client = result["client"]
    _need(type(client) is dict and client.get("name") and client.get("version")
          and client.get("model") == "UNSPECIFIED", "external_receipt_client")
    host = result["host"]
    _need(type(host) is dict and host.get("os") and host.get("architecture")
          and host.get("python_version") and host.get("node_version"), "external_receipt_host")
    servers = result["servers"]
    _need(type(servers) is list and len(servers) == 2, "external_receipt_servers")
    expected = {item["name"]: item["pin"] for item in PINNED_EXTERNAL}
    seen: set[str] = set()
    summaries: list[dict[str, Any]] = []
    for server in servers:
        _need(type(server) is dict, "external_receipt_server_type")
        name = server.get("name")
        _need(name in expected and name not in seen, "external_receipt_server_id")
        seen.add(name)
        _need(server.get("pin") == expected[name], f"external_receipt_pin:{name}")
        _need(server.get("server_version"), f"external_receipt_version:{name}")
        _need(server.get("transport") == "stdio", f"external_receipt_server_transport:{name}")
        _need(server.get("mutation_calls") == [], f"external_receipt_mutations:{name}")
        runs = server.get("runs")
        _need(type(runs) is list and len(runs) == 2, f"external_receipt_runs:{name}")
        for index, run in enumerate(runs):
            _need(type(run) is dict, f"external_receipt_run_type:{name}:{index}")
            _need(run.get("timed_out") is False and run.get("exit_code") == 0,
                  f"external_receipt_exit:{name}:{index}")
            _need(type(run.get("duration_ms")) in (int, float) and run["duration_ms"] >= 0,
                  f"external_receipt_duration:{name}:{index}")
            _need(run.get("initialize_ok") is True and run.get("tools_list_ok") is True,
                  f"external_receipt_protocol:{name}:{index}")
            _need(run.get("lookup_only") is True, f"external_receipt_lookup:{name}:{index}")
            _need(run.get("unsupported_client") == "NOT_RUN_IN_MUTATING_SESSION",
                  f"external_receipt_unsupported_scope:{name}:{index}")
            wire = run.get("wire")
            _need(type(wire) is dict and type(wire.get("initialize_response")) is dict
                  and type(wire.get("tools_list_response")) is dict,
                  f"external_receipt_wire:{name}:{index}")
            _need(wire["tools_list_response"].get("response_sha256") == run.get("tools_response_sha256"),
                  f"external_receipt_wire_hash:{name}:{index}")
        negative = server.get("negative")
        _need(type(negative) is dict and negative.get("outcome") in {"NEGOTIATED", "REJECTED"}
              and negative.get("exit_code") == 0 and negative.get("timed_out") is False,
              f"external_receipt_negative:{name}")
        _need(type(negative.get("response")) is dict,
              f"external_receipt_negative_wire:{name}")
        summary = server.get("summary")
        _need(type(summary) is dict, f"external_receipt_summary:{name}")
        for key in ("initialize", "tools_list", "reconnect", "context_reset_lookup_only"):
            _need(summary.get(key) is True, f"external_receipt_summary:{name}:{key}")
        _need(type(summary.get("read_only_surface")) is bool,
              f"external_receipt_summary:{name}:read_only_surface")
        _need(summary.get("unsupported_outcome") in {"NEGOTIATED", "REJECTED"},
              f"external_receipt_summary:{name}:unsupported")
        summaries.append({"name": name, "pin": server["pin"], "summary": summary,
                          "server_version": server["server_version"],
                          "tool_count": server.get("tool_count", 0)})
    _need(seen == set(expected), "external_receipt_server_set")
    return {"path": path.as_posix(), "sha256": _sha256(path), "run_id": result["run_id"],
            "servers": summaries, "client": client, "host": host}


def verify_native_attempt(path: Path) -> dict[str, Any]:
    """Validate a bounded external-server/native-editor attempt.

    This is intentionally a *failure-preserving* verifier.  A successful MCP
    request is only a native observation when the editor bridge reports a
    connected editor and a read-only operation returns a non-error result.  A
    scripted stdio client does not own HH Studio's lease, journal, or semantic
    command-id protocol; those fields therefore must remain explicit
    ``UNMEASURED`` markers.  In particular, this function never promotes an
    MCP request id, process exit, or model label into a native command id.
    """
    result = _load(path)
    required = {
        "schema", "authority", "acceptance", "run_id", "server", "server_pin",
        "transport", "client", "host", "adapter", "source_closure", "calls",
        "native_observation", "godot", "mcp", "status",
    }
    _need(required <= set(result), "native_attempt_missing:" + ",".join(
        sorted(required - set(result))))
    _need(result["schema"] == NATIVE_ATTEMPT_SCHEMA, "native_attempt_schema")
    _need(result["authority"] == 0 and result["acceptance"] is False,
          "native_attempt_authority")
    _need(type(result["run_id"]) is str and result["run_id"],
          "native_attempt_run_id")
    _need(result["server"] == "hybridindie/godot-mcp",
          "native_attempt_server")
    expected_pin = next(item["pin"] for item in PINNED_EXTERNAL
                        if item["name"] == result["server"])
    _need(result["server_pin"] == expected_pin, "native_attempt_pin")
    _need(result["transport"] == "stdio", "native_attempt_transport")

    client = result["client"]
    _need(type(client) is dict and client.get("name") and client.get("version")
          and client.get("protocol") and client.get("model") == "UNSPECIFIED",
          "native_attempt_client")
    host = result["host"]
    _need(type(host) is dict and host.get("os") and host.get("platform")
          and host.get("python") and host.get("godot_binary"),
          "native_attempt_host")
    adapter = result["adapter"]
    _need(type(adapter) is dict and adapter.get("addon") == result["server"]
          and adapter.get("bridge_url", "").startswith("ws://127.0.0.1:")
          and adapter.get("fixture"), "native_attempt_adapter")

    closure = result["source_closure"]
    _need(type(closure) is dict and closure.get("addon_commit") == expected_pin,
          "native_attempt_closure_pin")
    for field in ("probe_sha256", "fixture_project_sha256", "sha256"):
        _need(type(closure.get(field)) is str and len(closure[field]) == 64,
              f"native_attempt_closure:{field}")

    calls = result["calls"]
    _need(type(calls) is list and calls, "native_attempt_calls")
    allowed = {
        "godot_health_check", "godot_get_server_info",
        "godot_inspection_get_project_info", "godot_inspection_get_scene_tree",
    }
    request_ids: set[int] = set()
    readback_success = False
    for index, item in enumerate(calls):
        _need(type(item) is dict and type(item.get("request")) is dict
              and type(item.get("response")) is dict,
              f"native_attempt_call:{index}")
        request = item["request"]
        _need(type(request.get("id")) is int and request["id"] not in request_ids,
              f"native_attempt_request:{index}")
        request_ids.add(request["id"])
        method = request.get("method")
        _need(method in {"initialize", "tools/list", "tools/call"},
              f"native_attempt_method:{index}")
        params = request.get("params")
        if method == "tools/call":
            _need(type(params) is dict and params.get("name") in allowed,
                  f"native_attempt_operation:{index}")
        response = item["response"]
        _need(response.get("jsonrpc") == "2.0"
              and response.get("id") == request["id"],
              f"native_attempt_response:{index}")
        # FastMCP wraps tool outcomes in a JSON-RPC result.  Error results are
        # useful raw evidence but cannot count as a readback postcondition.
        if (method == "tools/call"
                and params["name"] == "godot_inspection_get_project_info"
                and type(response.get("result")) is dict
                and response["result"].get("isError") is False
                and type(response["result"].get("structuredContent")) is dict):
            readback_success = True

    native = result["native_observation"]
    _need(type(native) is dict and type(native.get("bridge_connected_observed")) is bool,
          "native_attempt_observation")
    _need(native.get("lease") == "UNMEASURED"
          and native.get("journal") == "UNMEASURED"
          and native.get("command_id") == "MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID",
          "native_attempt_ownership_markers")
    if native["bridge_connected_observed"]:
        _need(readback_success and native.get("postcondition_readback")
              == "MEASURED_FOR_READ_ONLY_PROJECT_AND_SCENE",
              "native_attempt_readback")
    else:
        _need(not readback_success and native.get("postcondition_readback") == "UNMEASURED",
              "native_attempt_unconnected_readback")

    for name in ("godot", "mcp"):
        process = result[name]
        _need(type(process) is dict and type(process.get("exit_code")) is int
              and type(process.get("stdout_sha256")) is str
              and len(process["stdout_sha256"]) == 64
              and type(process.get("stderr_sha256")) is str
              and len(process["stderr_sha256"]) == 64,
              f"native_attempt_process:{name}")
    _need(result["mcp"].get("timed_out") is False,
          "native_attempt_mcp_timeout")
    _need(result["status"] == "NATIVE_READONLY_ATTEMPT_UNSUPPORTED_LEASE",
          "native_attempt_status")
    return {
        "path": path.as_posix(), "sha256": _sha256(path),
        "run_id": result["run_id"], "server": result["server"],
        "server_pin": result["server_pin"], "client": client, "host": host,
        "fixture": adapter["fixture"],
        "bridge_connected": native["bridge_connected_observed"],
        "readback": native["postcondition_readback"],
        "lease": native["lease"], "journal": native["journal"],
        "command_id": native["command_id"],
        "godot_exit": result["godot"]["exit_code"],
        "mcp_exit": result["mcp"]["exit_code"],
        "status": result["status"],
    }


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


def _external_row(item: dict[str, Any], external: dict[str, Any]) -> dict[str, Any]:
    measured = next(server for server in external["servers"] if server["name"] == item["name"])
    return {
        "id": item["name"],
        "status": "MEASURED_TRANSPORT_ONLY",
        "authority": 0,
        "transport": "stdio",
        "pin": item["pin"],
        "server_version": measured["server_version"],
        "client": external["client"],
        "host": external["host"],
        "receipt": {"path": external["path"], "sha256": external["sha256"],
                    "run_id": external["run_id"]},
        "capabilities": {
            "stdio_initialize": True,
            "tools_list": True,
            "read_only_lookup_surface": measured["summary"].get("read_only_surface", False),
            "reconnect_retry": True,
            "context_reset_lookup_only": True,
            "unsupported_client_rejected": False,
            "native_postcondition_readback": "UNMEASURED",
            "arbitrary_code_denial": "UNMEASURED",
        },
        "limits": [
            "transport handshake/list/reconnect only; no Godot editor or fixture",
            "unsupported protocol was negotiated by the server, not rejected",
            "native postcondition, lease, hash and critic gates remain open",
        ],
    }


def build_matrix(receipt: Path, external_receipt: Path | None = None) -> dict[str, Any]:
    private = verify_private_receipt(receipt)
    external = verify_external_receipt(external_receipt) if external_receipt else None
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
        if external:
            rows.append(_external_row(item, external))
        else:
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
        "status": "COMPLETE" if complete else (
            "EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN" if external else "INCOMPLETE_EXTERNAL_SPIKE"
        ),
        "generated_by": "gt09_mcp_compatibility.py",
        "private_receipt": private,
        "rows": rows,
        "requirements": {
            "external_pinned_mcp_spike": "MEASURED_TRANSPORT_ONLY" if external else "OPEN",
            "model_host_capability_matrix": "OPEN",
            "two_critics_same_final_hash": "OPEN",
        },
        "interpretation": (
            ("Private adapter and pinned external stdio transport facts are measured; native "
             "fixture compatibility and public capability remain unclaimed.") if external else
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
        if row.get("id") != "hh-private-python-adapter" and row.get("id") in {item["name"] for item in PINNED_EXTERNAL} and row.get("status") not in {"UNMEASURED", "MEASURED_TRANSPORT_ONLY"}:
            errors.append("external_status")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--external-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    matrix = build_matrix(args.receipt, args.external_receipt)
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
