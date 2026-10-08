"""Run the bounded GT-09 external MCP stdio compatibility spike.

The probe intentionally starts only the pinned MCP bridge/server processes.  It
does not start Godot, Blender, Docker, or a project.  It exercises initialize,
tools/list, a lookup-only retry, a fresh reconnect/context reset, and a client
that advertises an unsupported protocol version.  A successful transport probe
is recorded as ``MEASURED_TRANSPORT_ONLY``; the native fixture/lease/hash gates
remain outside this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


SCHEMA = "hh-gt09-mcp-external-spike-1"
RUN_ID = "gt09-mcp-spike-20261008-01"
PROBE_VERSION = "0.1.0"
UNSUPPORTED_PROTOCOL = "9999-unsupported"
SUPPORTED_PROTOCOL = "2025-11-25"
TIMEOUT_SECONDS = 20.0

PINNED = {
    "NPGameDev/godot-mcp-toolkit": "10a4508e880244c66a3f04861b2e22872c307247",
    "hybridindie/godot-mcp": "48f34e7d28d65cfea456cc2641e13c3058caa3d6",
}


def _sha(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _json_hash(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _node_version() -> str:
    try:
        completed = subprocess.run(["node", "--version"], capture_output=True, text=True,
                                   timeout=5, check=False)
        return completed.stdout.strip() or "UNAVAILABLE"
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"


def _git_pin(repo: Path) -> str:
    completed = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=10, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"git_pin_failed:{repo}")
    return completed.stdout.strip()


def _stderr_markers(data: bytes) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    markers: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if "readonly=true" in lower or "readonly" in lower:
            markers.append("read_only")
        elif "disconnected" in lower or "bridge" in lower and "connect" in lower:
            markers.append("bridge_disconnected")
        elif "starting mcp" in lower or "starting godot-mcp" in lower:
            markers.append("server_started")
    return sorted(set(markers))


class _WireProcess:
    def __init__(self, command: list[str], cwd: Path, env: dict[str, str]) -> None:
        self.command = command
        self.proc = subprocess.Popen(command, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     bufsize=0)
        self.out: queue.Queue[bytes] = queue.Queue()
        self.err: queue.Queue[bytes] = queue.Queue()
        threading.Thread(target=self._read, args=(self.proc.stdout, self.out), daemon=True).start()
        threading.Thread(target=self._read, args=(self.proc.stderr, self.err), daemon=True).start()
        self.responses: list[dict[str, Any]] = []
        self.stderr = bytearray()

    @staticmethod
    def _read(stream: Any, target: queue.Queue[bytes]) -> None:
        if stream is None:
            return
        for line in iter(stream.readline, b""):
            target.put(line)

    def send(self, value: dict[str, Any]) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("stdio_closed")
        self.proc.stdin.write((json.dumps(value, separators=(",", ":")) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def read_response(self, request_id: int, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            try:
                line = self.out.get(timeout=min(0.25, remaining))
            except queue.Empty:
                self._drain_stderr()
                if self.proc.poll() is not None:
                    break
                continue
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                # A protocol peer may emit a blank line; retain no untrusted output.
                continue
            if message.get("id") == request_id:
                self.responses.append(message)
                self._drain_stderr()
                return message
        self._drain_stderr()
        raise TimeoutError(f"response_timeout:{request_id}")

    def _drain_stderr(self) -> None:
        while True:
            try:
                self.stderr.extend(self.err.get_nowait())
            except queue.Empty:
                return

    def close(self) -> tuple[int | None, bool]:
        self._drain_stderr()
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
        timed_out = False
        try:
            exit_code = self.proc.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            self.proc.kill()
            exit_code = self.proc.wait(timeout=5)
        self._drain_stderr()
        return exit_code, timed_out


def _run_once(spec: dict[str, Any], run_index: int) -> dict[str, Any]:
    started = time.monotonic()
    peer = _WireProcess(spec["command"], spec["cwd"], spec["env"])
    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    run_result: dict[str, Any] = {"run_index": run_index, "timed_out": False,
                                  "exit_code": None, "duration_ms": 0}
    try:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": SUPPORTED_PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "hh-gt09-stdio-probe", "version": PROBE_VERSION},
        }}
        requests.append(init)
        init_response = peer.send(init) or peer.read_response(1)
        # send() returns None; keeping the expression explicit prevents accidental
        # reliance on a server-side banner or exit integer.
        if init_response is None:
            init_response = peer.read_response(1)
        responses.append(init_response)
        peer.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        list_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        requests.append(list_request)
        list_response = peer.send(list_request) or peer.read_response(2)
        if list_response is None:
            list_response = peer.read_response(2)
        responses.append(list_response)
        tool_payload = list_response.get("result", {}).get("tools", [])
        tool_names = sorted(item.get("name", "") for item in tool_payload if isinstance(item, dict))
        retry_request = {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}
        requests.append(retry_request)
        retry_response = peer.send(retry_request) or peer.read_response(3)
        if retry_response is None:
            retry_response = peer.read_response(3)
        responses.append(retry_response)
        init_result = init_response.get("result")
        list_result = list_response.get("result")
        retry_result = retry_response.get("result")
        lookup_only = bool(tool_names) and not any(
            re.search(r"(write|create|delete|remove|set_|patch|execute|eval|run_)", name,
                      flags=re.IGNORECASE)
            for name in tool_names
        )
        run_result.update({
            "run_index": run_index,
            "timed_out": False,
            "exit_code": None,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "initialize_ok": isinstance(init_result, dict),
            "protocol_version": init_result.get("protocolVersion") if isinstance(init_result, dict) else None,
            "tools_list_ok": isinstance(list_result, dict) and isinstance(tool_payload, list),
            "retry_ok": isinstance(retry_result, dict) and _json_hash(retry_result) == _json_hash(list_result),
            "lookup_only": lookup_only,
            "tool_count": len(tool_names),
            "tool_names": tool_names,
            "tools_response_sha256": _json_hash(list_response),
            "unsupported_client": "NOT_RUN_IN_MUTATING_SESSION",
            "wire": {
                "requests": [{"id": m.get("id"), "method": m["method"],
                              "protocolVersion": m.get("params", {}).get("protocolVersion")}
                             for m in requests],
                "responses": [
                    {"id": m.get("id"), "has_result": "result" in m, "has_error": "error" in m,
                     "protocolVersion": m.get("result", {}).get("protocolVersion") if isinstance(m.get("result"), dict) else None,
                     "response_sha256": _json_hash(m)} for m in responses
                ],
            },
            "stderr_sha256": _sha(bytes(peer.stderr)),
            "stderr_markers": _stderr_markers(bytes(peer.stderr)),
        })
        return run_result
    finally:
        exit_code, timed_out = peer.close()
        # The finally block fills actual process facts even when a protocol call
        # fails.  The caller turns exceptions into an explicit failed receipt.
        run_result["exit_code"] = exit_code
        run_result["timed_out"] = timed_out
        run_result["duration_ms"] = round((time.monotonic() - started) * 1000, 2)


def _run_negative(spec: dict[str, Any]) -> dict[str, Any]:
    """Probe an unsupported protocol on a fresh session, then close it."""
    started = time.monotonic()
    peer = _WireProcess(spec["command"], spec["cwd"], spec["env"])
    response: dict[str, Any] = {}
    try:
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": UNSUPPORTED_PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "hh-gt09-negative-client", "version": "0.0.0"},
        }}
        peer.send(request)
        response = peer.read_response(1)
        outcome = "REJECTED" if "error" in response else "NEGOTIATED"
        result = response.get("result") if isinstance(response, dict) else None
        protocol = result.get("protocolVersion") if isinstance(result, dict) else None
    except Exception as exc:
        outcome, protocol = "REJECTED", None
        response = {"error_type": type(exc).__name__, "error": str(exc)}
    finally:
        exit_code, timed_out = peer.close()
    return {
        "request_protocol": UNSUPPORTED_PROTOCOL, "outcome": outcome,
        "response_protocol": protocol, "response_sha256": _json_hash(response),
        "exit_code": exit_code, "timed_out": timed_out,
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "stderr_sha256": _sha(bytes(peer.stderr)),
        "stderr_markers": _stderr_markers(bytes(peer.stderr)),
    }


def _probe_server(spec: dict[str, Any]) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    for index in (1, 2):
        try:
            result = _run_once(spec, index)
        except Exception as exc:  # evidence records failure; no fabricated pass
            result = {
                "run_index": index, "timed_out": False, "exit_code": None,
                "duration_ms": 0, "initialize_ok": False, "tools_list_ok": False,
                "retry_ok": False, "lookup_only": False,
                "unsupported_client": "REJECTED", "error": type(exc).__name__ + ":" + str(exc),
            }
        runs.append(result)
    negative = _run_negative(spec)
    server_version = spec["server_version"]
    summary = {
        "initialize": all(run.get("initialize_ok") for run in runs),
        "tools_list": all(run.get("tools_list_ok") for run in runs),
        "reconnect": len(runs) == 2 and all(run.get("exit_code") == 0 and not run.get("timed_out") for run in runs),
        "context_reset_lookup_only": len(runs) == 2 and all(run.get("lookup_only") for run in runs),
        "read_only_surface": bool(spec.get("read_only_default")) and all(run.get("lookup_only") for run in runs),
        "unsupported_outcome": negative["outcome"],
    }
    return {
        "name": spec["name"], "pin": spec["pin"], "server_version": server_version,
        "transport": "stdio", "command_scope": spec["command_scope"],
        "mutation_calls": [], "runs": runs, "negative": negative, "summary": summary,
        "tool_count": runs[0].get("tool_count", 0),
    }


def run_spike(toolkit_repo: Path, hybrid_repo: Path, venv_python: Path,
              npm_cache: Path, npm_version: str) -> dict[str, Any]:
    toolkit_pin = _git_pin(toolkit_repo)
    hybrid_pin = _git_pin(hybrid_repo)
    if toolkit_pin != PINNED["NPGameDev/godot-mcp-toolkit"]:
        raise RuntimeError("toolkit_pin_mismatch")
    if hybrid_pin != PINNED["hybridindie/godot-mcp"]:
        raise RuntimeError("hybrid_pin_mismatch")
    npm_cache.mkdir(parents=True, exist_ok=True)
    base_env = os.environ.copy()
    base_env.update({"GODOT_MCP_READ_ONLY": "1", "GODOT_MCP_CONFIG_VERSION": "1",
                     "GODOT_MCP_BRIDGE_URL": "ws://127.0.0.1:19080"})
    toolkit_command = ["cmd", "/d", "/s", "/c", "npx", "--yes", "--cache", str(npm_cache),
                       f"@npgamedev/godot-mcp-server@{npm_version}"]
    hybrid_command = [str(venv_python), "-m", "mcp_server.main"]
    specs = [
        {"name": "NPGameDev/godot-mcp-toolkit", "pin": toolkit_pin,
         "server_version": npm_version, "command": toolkit_command,
         "cwd": toolkit_repo, "env": base_env,
         "read_only_default": True,
         "command_scope": "npx bridge package only; no Godot editor"},
        {"name": "hybridindie/godot-mcp", "pin": hybrid_pin,
         "server_version": "2026.09.10", "command": hybrid_command,
         "cwd": hybrid_repo, "env": base_env,
         "read_only_default": False,
         "command_scope": "python stdio server only; no Godot editor"},
    ]
    servers = [_probe_server(spec) for spec in specs]
    return {
        "schema": SCHEMA, "run_id": RUN_ID, "authority": 0, "transport": "stdio",
        "scope": "transport_only_no_native_fixture", "engine_launched": False,
        "host": {"os": platform.system() + " " + platform.release(),
                  "architecture": platform.machine(), "python_version": platform.python_version(),
                  "node_version": _node_version()},
        "client": {"name": "hh-gt09-stdio-probe", "version": PROBE_VERSION,
                    "model": "UNSPECIFIED", "supported_protocol": SUPPORTED_PROTOCOL,
                    "unsupported_protocol": UNSUPPORTED_PROTOCOL},
        "servers": servers,
        "repro": {"command": "python studio/tests/conformance/run_gt09_mcp_spike.py",
                   "npm_bridge_version": npm_version},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--toolkit-repo", type=Path, required=True)
    parser.add_argument("--hybrid-repo", type=Path, required=True)
    parser.add_argument("--venv-python", type=Path, required=True)
    parser.add_argument("--npm-cache", type=Path, required=True)
    parser.add_argument("--npm-version", default="1.0.3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run_spike(args.toolkit_repo, args.hybrid_repo, args.venv_python,
                        args.npm_cache, args.npm_version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    print(json.dumps({"status": "MEASURED_TRANSPORT_ONLY", "output": args.output.as_posix(),
                      "run_id": receipt["run_id"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
