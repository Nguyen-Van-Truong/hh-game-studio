"""Build a fail-closed GT09 MCP/client capability matrix.

This verifier consumes an already completed private-adapter receipt and an
optional measured external-stdio/native receipts. It does not start Godot, Blender,
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
import re
from typing import Any
from urllib.parse import urlparse


SCHEMA = "hh-gt09-mcp-capability-matrix-1"
PRIVATE_ADAPTER_SCHEMA = "hh-gameplay-source-adapter-1"
EXTERNAL_SPIKE_SCHEMA = "hh-gt09-mcp-external-spike-1"
NATIVE_ATTEMPT_SCHEMA = "hh-gt09-mcp-native-attempt-1"
NATIVE_SPIKE_SCHEMA = "hh-gt09-mcp-native-spike-2"
NATIVE_OPERATIONS = {
    "godot_health_check", "godot_get_server_info",
    "godot_inspection_get_project_info", "godot_inspection_get_scene_tree",
    "godot_inspection_get_active_scene", "godot_inspection_get_node_property",
}
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


def verify_native_receipt(path: Path) -> dict[str, Any]:
    """Re-derive the v2 spike from raw wire, frozen files, and host Job receipt.

    This admits a measured external limitation, never SUPPORTED. The old v1
    disconnected attempt remains historical and cannot enter this native lane.
    ``native.json`` contains child exits captured by the frozen worker; the
    independent helper sidecar binds that worker's actual exit/PID to its Job.
    """
    root = path.absolute().parent

    def artifact(name: str) -> Path:
        relative = Path(name)
        _need(not relative.is_absolute() and ".." not in relative.parts,
              "native_receipt_artifact_path")
        candidate = root / relative
        _need(candidate.is_file() and not candidate.is_symlink()
              and candidate.resolve().is_relative_to(root.resolve()),
              "native_receipt_raw_missing:" + name)
        return candidate

    _need(path.name == "native.json", "native_receipt_filename")
    result = _load(artifact("native.json"))
    final = _load(artifact("result.json"))
    job = _load(artifact("host-job.json"))
    host_exit = _load(artifact("native-host.json"))
    dry = _load(artifact("dry-run.json"))
    frozen = _load(artifact("project-freeze.json"))
    for label, value in (("native", result), ("result", final), ("dry", dry)):
        _need(value.get("schema") == NATIVE_SPIKE_SCHEMA and value.get("authority") == 0,
              "native_receipt_schema:" + label)
        _need(value.get("run_id") == result.get("run_id") and type(value.get("run_id")) is str
              and bool(value["run_id"]), "native_receipt_run_id:" + label)
    _need(result.get("acceptance") is False and final.get("acceptance") is False
          and dry.get("dry_run") is True, "native_receipt_authority")
    _need(result.get("status") == final.get("status") == "MEASURED_EXTERNAL_NATIVE_LIMIT",
          "native_receipt_status")
    _need(final.get("native_sha256") == _sha256(path), "native_receipt_native_hash")
    _need(final.get("host_job") == job, "native_receipt_job_binding")
    _need(job.get("host") == "native-host.json" and job.get("stdout") == "native-stdout.txt"
          and job.get("stderr") == "native-stderr.txt", "native_receipt_host_names")
    for key in ("target_pid", "wrapper_pid"):
        _need(type(job.get(key)) is int and job[key] > 0, "native_receipt_job_pid")
    _need(type(host_exit.get("target_pid")) is int and host_exit["target_pid"] == job["target_pid"]
          and type(host_exit.get("exit_code")) is int and host_exit["exit_code"] == 0
          and type(job.get("exit_code")) is int and job["exit_code"] == 0
          and type(job.get("wrapper_exit_code")) is int and job["wrapper_exit_code"] == 0
          and job.get("timed_out") is False and job.get("tree_verified") is True
          and job.get("ownership") == "gated_job_kill_on_close", "native_receipt_host_exit")
    _need(job.get("argv", [])[1:] == ["run_gt09_mcp_native.py", "--worker", "$SNAPSHOT/dry-run.json"],
          "native_receipt_worker_command")
    source_hashes = dry.get("source_hashes")
    _need(type(source_hashes) is dict and bool(source_hashes), "native_receipt_sources")
    closure = hashlib.sha256(json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    _need(result.get("source_closure_sha256") == final.get("source_closure_sha256")
          == dry.get("source_closure_sha256") == closure, "native_receipt_closure")
    # These are original run inputs, not the current repository-wide closure.
    # A subsequent unrelated implementation change cannot relabel this spike.
    for name, expected in source_hashes.items():
        source = Path(name)
        _need(source.is_file() and not source.is_symlink() and _sha256(source) == expected,
              "native_receipt_source_hash:" + name)
    pin = _load(Path(__file__).resolve().parents[2] / "toolchain.lock.json")["godot"]
    _need(dry.get("godot_pin") == result.get("host", {}).get("godot") == pin
          and pin["version"] == "4.7.2-stable"
          and source_hashes.get(dry.get("godot")) == pin["gui_sha256"], "native_receipt_godot_pin")
    external_pin = next(item["pin"] for item in PINNED_EXTERNAL if item["name"] == "hybridindie/godot-mcp")
    _need(result.get("server_pin") == external_pin, "native_receipt_addon_pin")
    addon_source = Path(dry["repo"]) / "godot/addons/godot_mcp"
    _need(any(Path(name).is_relative_to(addon_source) for name in source_hashes), "native_receipt_addon_sources")
    for name, expected in frozen.items():
        _need(_sha256(artifact("project/" + name)) == expected, "native_receipt_scratch_hash:" + name)
        if name.startswith("addons/godot_mcp/"):
            source = addon_source / name.removeprefix("addons/godot_mcp/")
            _need(source_hashes.get(str(source)) == expected, "native_receipt_addon_copy:" + name)
    _need(result.get("scratch_source_unchanged") is True and result.get("input_source_unchanged") is True
          and result.get("errors") == [], "native_receipt_source_claim")
    _need(result.get("host_adapter_started") is False and dry.get("host_adapter_started") is False,
          "native_receipt_route")
    _need(dry.get("operation_allowlist") == sorted(NATIVE_OPERATIONS), "native_receipt_allowlist")
    client = result.get("client", {})
    _need(client == {"name": "hh-k13-native-read-client", "version": "0.2.0", "model": "UNSPECIFIED",
                     "protocol": "2025-11-25"}, "native_receipt_client")
    adapter = result.get("adapter", {})
    bridge = urlparse(adapter.get("bridge_url", ""))
    _need(adapter.get("name") == "hybridindie/godot-mcp" and bridge.scheme == "ws"
          and bridge.hostname == "127.0.0.1" and bridge.port is not None, "native_receipt_adapter")
    _need(Path(adapter.get("fixture", "")).resolve() == (Path(dry["output"]) / "project").resolve(),
          "native_receipt_scratch_binding")
    raw_names = {f"{stage}-{stream}.txt" for stage in ("godot", "mcp", "import", "native")
                 for stream in ("stdout", "stderr")}
    _need(type(result.get("raw_logs")) is dict and set(result["raw_logs"]) == raw_names,
          "native_receipt_raw_set")
    for name, expected in result["raw_logs"].items():
        _need(_sha256(artifact(name)) == expected, "native_receipt_raw_hash:" + name)
    for name in ("godot", "mcp"):
        process = result.get(name, {})
        _need(type(process.get("pid")) is int and process["pid"] > 0
              and type(process.get("exit_code")) is int and process["exit_code"] == 0
              and process.get("forced") is False, "native_receipt_child_exit:" + name)
    _need(type(result.get("import_exit")) is int and result["import_exit"] == 0
          and result["mcp"].get("output_cap_exceeded") is False, "native_receipt_import_exit")
    for stream in ("stdout", "stderr"):
        _need(result["mcp"].get(stream + "_sha256") == result["raw_logs"]["mcp-" + stream + ".txt"],
              "native_receipt_mcp_hash")

    # The response stored alongside a request must be byte-content-equivalent
    # to the independently drained raw MCP stream; banner flags do not count.
    wire = [json.loads(line) for line in artifact("mcp-stdout.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    raw_responses = [message for message in wire if "id" in message]
    calls = result.get("calls")
    _need(type(calls) is list and len(calls) >= 9, "native_receipt_calls")
    _need([row.get("response") for row in calls] == raw_responses, "native_receipt_wire_binding")
    _need([row.get("request", {}).get("id") for row in calls] == list(range(1, len(calls) + 1)),
          "native_receipt_request_ids")
    tool_calls: dict[str, list[dict]] = {}
    operations = []
    for row in calls:
        request, response = row["request"], row["response"]
        _need(request.get("jsonrpc") == response.get("jsonrpc") == "2.0"
              and response.get("id") == request["id"] and "error" not in response,
              "native_receipt_response")
        _need(row.get("lease_traversed") is False and row.get("journal_traversed") is False,
              "native_receipt_operation_ownership")
        method = request.get("method")
        _need(method in {"initialize", "tools/list", "tools/call"}, "native_receipt_method")
        if method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            _need(name in NATIVE_OPERATIONS and response.get("result", {}).get("isError") is False,
                  "native_receipt_operation")
            expected_arguments = ({"max_depth": 1, "lightweight": True}
                                  if name == "godot_inspection_get_scene_tree" else
                                  {"node_path": "HUD/Status", "property": "text"}
                                  if name == "godot_inspection_get_node_property" else {})
            _need(params.get("arguments") == expected_arguments, "native_receipt_operation_arguments")
            value = response["result"].get("structuredContent")
            _need(type(value) is dict, "native_receipt_structured_readback")
            tool_calls.setdefault(name, []).append(value)
            operations.append({"request_id": request["id"], "operation": name,
                               "lease_traversed": False, "journal_traversed": False})
    _need(calls[0]["request"]["method"] == "initialize" and calls[1]["request"]["method"] == "tools/list",
          "native_receipt_initialize")
    _need(all(row["request"]["method"] == "tools/call" for row in calls[2:]), "native_receipt_call_sequence")
    _need(calls[0]["request"]["params"].get("clientInfo") == {"name": client["name"], "version": client["version"]}
          and calls[0]["request"]["params"].get("protocolVersion") == client["protocol"]
          and calls[0]["response"]["result"].get("protocolVersion") == client["protocol"], "native_receipt_protocol")
    expected_tail = ["godot_get_server_info", "godot_inspection_get_project_info", "godot_inspection_get_active_scene",
                     "godot_inspection_get_scene_tree", "godot_inspection_get_node_property", "godot_inspection_get_scene_tree"]
    names = [row["operation"] for row in operations]
    _need(names[-6:] == expected_tail and names[:-6] and set(names[:-6]) == {"godot_health_check"},
          "native_receipt_fixed_operations")
    health = tool_calls["godot_health_check"][-1]
    _need(health.get("bridge_connected") is True and health.get("bridge_url") == adapter["bridge_url"],
          "native_receipt_bridge")
    info = tool_calls["godot_inspection_get_project_info"][0]
    _need(info.get("godot_version") == pin["version"] + " (official)"
          and Path(info.get("project_path", "")).resolve() == Path(adapter["fixture"]).resolve()
          and info.get("main_scene") == "res://scenes/arena.tscn", "native_receipt_project_readback")
    active = tool_calls["godot_inspection_get_active_scene"][0]
    _need(active.get("is_open") is True and active.get("path") == "res://scenes/arena.tscn",
          "native_receipt_active_readback")
    trees = [value.get("tree", {}) for value in tool_calls["godot_inspection_get_scene_tree"]]
    children = {node.get("name"): node.get("type") for node in trees[0].get("children", [])}
    _need(trees[0] == trees[1] and trees[0].get("name") == "Arena" and trees[0].get("type") == "Node2D"
          and children.get("Player") == "CharacterBody2D" and children.get("Floor") == "StaticBody2D",
          "native_receipt_scene_readback")
    prop = tool_calls["godot_inspection_get_node_property"][0]
    _need(prop.get("exists") is True and prop.get("value") == "HP 3", "native_receipt_property_readback")
    tools = calls[1]["response"]["result"].get("tools", [])
    _need(type(tools) is list and tools, "native_receipt_tools")
    tool_by_name = {tool.get("name"): tool for tool in tools}
    _need(all(name in tool_by_name and tool_by_name[name].get("annotations", {}).get("readOnlyHint") is True
              for name in NATIVE_OPERATIONS), "native_receipt_read_only_tools")
    readonly = all(tool.get("annotations", {}).get("readOnlyHint") is True for tool in tools)
    fields = {name for tool in tools for name in tool.get("inputSchema", {}).get("properties", {})}
    ownership_fields = sorted(fields & {"lease", "lease_id", "fencing_epoch", "command_id", "journal"})
    observed = {key: True for key in ("active_scene", "bridge_connected", "native_readback", "node_property",
                                    "project_info", "repeat_readback", "scene_tree")}
    observed.update(server_read_only_surface=readonly, discovery_ownership_fields=ownership_fields,
                    lease="NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE", journal="NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE",
                    command_id="MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID")
    _need(result.get("observation") == observed, "native_receipt_observation_claim")
    native_text = artifact("godot-stdout.txt").read_text(encoding="utf-8") + "\n" + artifact("godot-stderr.txt").read_text(encoding="utf-8")
    _need("Godot Engine v" + pin["observed_version"] + " - " in native_text
          and result.get("native_pin_banner") is True, "native_receipt_pin_banner")
    warnings = [line for line in native_text.splitlines() if re.match(r"^(WARNING:|ERROR:|SCRIPT ERROR:)", line)]
    _need(result.get("native_warning_error_lines") == warnings, "native_receipt_warning_claim")
    gate = "INCOMPATIBLE" if warnings else "UNSUPPORTED"
    _need(result.get("native_gate") == gate, "native_receipt_gate_claim")
    return {"path": path.as_posix(), "sha256": _sha256(path), "run_id": result["run_id"],
            "server": adapter["name"], "server_pin": external_pin, "client": client, "host": result["host"],
            "fixture": adapter["fixture"], "source_closure_sha256": closure, "observations": observed,
            "operations": operations, "native_gate": gate, "supported": False,
            "warnings": warnings, "host_job_sha256": _sha256(artifact("host-job.json")),
            "host_exit_sha256": _sha256(artifact("native-host.json")), "result_sha256": _sha256(artifact("result.json")),
            "limits": ["The measured read operations use the external bridge without HH lease/journal/semantic command_id gates."]
                      + (["Native editor cleanup emitted warnings/errors; raw logs are retained."] if warnings else []),
            "client_scope": "SCRIPTED_READ_ONLY_SPIKE_ONLY; K8_K12_MODEL_MATRIX_NOT_TESTED"}


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


def _native_external_row(native: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": native["server"], "status": native["native_gate"], "authority": 0,
        "transport": "stdio", "pin": native["server_pin"], "supported": False,
        "client": native["client"], "host": native["host"], "native_receipt": native,
        "capabilities": {
            "stdio_initialize": True, "tools_list": True,
            "read_only_lookup_surface": native["observations"]["server_read_only_surface"],
            "client_read_only_allowlist": True, "native_postcondition_readback": True,
            "repeat_readback": True, "native_cleanup_clean": not native["warnings"],
            "hh_lease": False, "hh_journal": False, "hh_semantic_command_id": False,
            "native_reconnect_retry": "NOT_TESTED", "context_reset": "NOT_TESTED",
            "unsupported_client_rejection": "NOT_TESTED", "arbitrary_code_denial": "NOT_TESTED",
            "k8_k12_client_model_matrix": "NOT_TESTED",
        },
        "limits": native["limits"],
    }


def build_matrix(receipt: Path, external_receipt: Path | None = None,
                 native_receipt: Path | None = None) -> dict[str, Any]:
    private = verify_private_receipt(receipt)
    external = verify_external_receipt(external_receipt) if external_receipt else None
    native = verify_native_receipt(native_receipt) if native_receipt else None
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
        if native and item["name"] == native["server"]:
            rows.append(_native_external_row(native))
        elif external:
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
        "status": "EXTERNAL_NATIVE_LIMITS_MEASURED_CLIENT_OPEN" if native else "COMPLETE" if complete else (
            "EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN" if external else "INCOMPLETE_EXTERNAL_SPIKE"
        ),
        "generated_by": "gt09_mcp_compatibility.py",
        "private_receipt": private,
        "rows": rows,
        "requirements": {
            "external_pinned_mcp_spike": ("HYBRID_NATIVE_LIMIT_MEASURED_OTHER_NATIVE_OPEN" if native
                                           else "MEASURED_TRANSPORT_ONLY" if external else "OPEN"),
            "model_host_capability_matrix": "OPEN",
            "two_critics_same_final_hash": "OPEN",
        },
        "interpretation": (
            "Hybridindie native readback and limitations are measured. This scripted client/model "
            "has no K8-K12 conformance claim; the other external native row remains untested."
            if native else
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
        if row.get("id") != "hh-private-python-adapter" and row.get("id") in {item["name"] for item in PINNED_EXTERNAL} and row.get("status") not in {"UNMEASURED", "MEASURED_TRANSPORT_ONLY", "UNSUPPORTED", "INCOMPATIBLE"}:
            errors.append("external_status")
        if row.get("status") in {"UNSUPPORTED", "INCOMPATIBLE"}:
            try:
                native = verify_native_receipt(Path(row["native_receipt"]["path"]))
                if row != _native_external_row(native):
                    errors.append("native_row_binding")
            except (OSError, ValueError, KeyError, TypeError):
                errors.append("native_row_evidence")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--external-receipt", type=Path)
    parser.add_argument("--native-receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    matrix = build_matrix(args.receipt, args.external_receipt, args.native_receipt)
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
