"""Bounded K13 read-only MCP spike against a pinned native scratch editor.

Dry-run freezes the source and binary inputs. Native execution reuses the
bootstrap gated Windows Job owner, so an interrupted host also kills descendants.
External readback is measured separately from HH lease/journal conformance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
PIN = "48f34e7d28d65cfea456cc2641e13c3058caa3d6"
SCHEMA = "hh-gt09-mcp-native-spike-2"
PROTOCOL = "2025-11-25"
DEADLINE_SECONDS = 110
TOOLS = {
    "godot_health_check", "godot_get_server_info",
    "godot_inspection_get_project_info", "godot_inspection_get_scene_tree",
    "godot_inspection_get_active_scene", "godot_inspection_get_node_property",
}
WATCHDOG = '''@tool
extends EditorPlugin
var started: int = 0
var closing: bool = false
func _enter_tree() -> void:
    started = Time.get_ticks_msec()
    set_process(true)
func _process(_delta: float) -> void:
    if closing:
        return
    if FileAccess.file_exists("res://.probe-stop") or Time.get_ticks_msec() - started > 45000:
        closing = true
        get_tree().quit(0)
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bootstrap():
    spec = importlib.util.spec_from_file_location("k13_bootstrap", STUDIO / "build/bootstrap/run_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regular(path: Path) -> Path:
    path = path.absolute()
    for parent in (path, *path.parents):
        info = parent.stat(follow_symlinks=False)
        if parent.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("REPARSE_PATH")
    return path.resolve(strict=True)


def source_hashes(repo: Path, fixture: Path, godot: Path, python: Path) -> dict[str, str]:
    paths = [Path(__file__).resolve(), STUDIO / "build/bootstrap/run_fixture.py",
             STUDIO / "toolchain.lock.json", godot, python, fixture / "project.godot"]
    for base in (repo / "mcp_server", repo / "godot/addons/godot_mcp", fixture / "scenes"):
        paths.extend(p for p in base.rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".import"})
    return {str(regular(p)): sha(p) for p in sorted(set(paths))}


def verify_frozen(plan: dict) -> None:
    if plan.get("schema") != SCHEMA or plan.get("dry_run") is not True:
        raise ValueError("DRY_RUN_REQUIRED")
    for path, expected in plan["source_hashes"].items():
        if sha(regular(Path(path))) != expected:
            raise ValueError("SOURCE_DRIFT:" + path)
    if digest(plan["source_hashes"]) != plan["source_closure_sha256"]:
        raise ValueError("SOURCE_CLOSURE_DIGEST")


def guard_host() -> None:
    lock = Path(os.environ["LOCALAPPDATA"]) / "HHGodotAgent/measure-window.lock"
    if lock.exists():
        raise ValueError("MEASURE_WINDOW_LOCK_PRESENT:" + str(lock))
    # A scratch diagnostic waits for the shared native slot; it never closes user apps.
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-Process | Where-Object { $_.ProcessName -match '^(Godot|blender)' } | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True, timeout=10, check=True)
    if result.stdout.strip():
        raise ValueError("NATIVE_PROCESS_BUSY:" + result.stdout.strip())


def prepare(args) -> dict:
    if not re.fullmatch(r"gt09-mcp-native-[a-z0-9-]{1,60}", args.run_id):
        raise ValueError("RUN_ID")
    output = (STUDIO / ".local/reviews" / args.run_id).absolute()
    if output.exists():
        raise ValueError("RUN_ID_USED")
    repo, fixture, python = map(regular, (args.repo, args.fixture, args.python))
    lock = json.loads((STUDIO / "toolchain.lock.json").read_text())["godot"]
    godot = regular(STUDIO / ".local/tooling" / ("godot-" + lock["version"]) / lock["gui_executable"])
    if sha(godot) != lock["gui_sha256"] or lock["version"] != "4.7.2-stable":
        raise ValueError("GODOT_PIN")
    pin = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10).strip()
    dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True, timeout=10)
    if pin != PIN or dirty:
        raise ValueError("EXTERNAL_PIN_OR_DIRTY")
    if not (fixture / "scenes/arena.tscn").is_file():
        raise ValueError("SAVED_ARENA_FIXTURE_REQUIRED")
    sources = source_hashes(repo, fixture, godot, python)
    plan = {"schema": SCHEMA, "dry_run": True, "run_id": args.run_id, "authority": 0,
            "created_at": datetime.now(timezone.utc).isoformat(), "repo": str(repo),
            "fixture": str(fixture), "python": str(python), "godot": str(godot),
            "godot_pin": lock, "source_hashes": sources,
            "source_closure_sha256": digest(sources), "deadline_seconds": DEADLINE_SECONDS,
            "operation_allowlist": sorted(TOOLS), "host_adapter_started": False,
            "client_model": "UNSPECIFIED", "output": str(output)}
    output.mkdir(parents=True)
    write(output / "dry-run.json", plan)
    return plan


def payload(response: dict) -> dict:
    result = response.get("result", {})
    if result.get("isError") is True or "error" in response:
        return {}
    value = result.get("structuredContent")
    return value if type(value) is dict else {}


class Wire:
    """Small stdio client: unique ids, fixed read allowlist, complete bounded raw."""
    def __init__(self, command: list[str], cwd: Path, env: dict[str, str], output: Path):
        self.proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        self.output = output
        self.inbox: queue.Queue = queue.Queue()
        self.threads = []
        self.calls = []
        self.next_id = 1
        self.overflow = False
        for name, stream in (("stdout", self.proc.stdout), ("stderr", self.proc.stderr)):
            thread = threading.Thread(target=self._read, args=(name, stream), daemon=True)
            thread.start()
            self.threads.append(thread)

    def _read(self, name, stream):
        count = 0
        with (self.output / ("mcp-" + name + ".txt")).open("xb") as raw:
            for line in iter(stream.readline, b""):
                count += len(line)
                if count > 4 * 1024 * 1024:
                    self.overflow = True
                    continue
                raw.write(line)
                if name == "stdout":
                    try:
                        self.inbox.put(json.loads(line))
                    except (UnicodeError, ValueError):
                        pass

    def send(self, value: dict):
        self.proc.stdin.write((json.dumps(value) + "\n").encode())
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, *, timeout: float = 10) -> dict:
        if method == "tools/call" and params.get("name") not in TOOLS:
            raise ValueError("READ_ONLY_ALLOWLIST")
        if method not in {"initialize", "tools/list", "tools/call"}:
            raise ValueError("METHOD_ALLOWLIST")
        request_id = self.next_id
        self.next_id += 1
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self.send(request)
        row = {"request": request, "response": None, "lease_traversed": False,
               "journal_traversed": False, "postcondition": "NOT_OBSERVED"}
        self.calls.append(row)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.overflow:
                raise RuntimeError("MCP_OUTPUT_CAP")
            try:
                response = self.inbox.get(timeout=min(.2, max(.01, deadline - time.monotonic())))
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise RuntimeError("MCP_EARLY_EXIT")
                continue
            if response.get("id") != request_id:
                if "id" in response:
                    raise RuntimeError("MCP_RESPONSE_ID_MISMATCH")
                continue  # server notifications are retained in raw stdout
            row["response"] = response
            return response
        raise TimeoutError("MCP_RESPONSE_TIMEOUT:" + str(request_id))

    def call(self, name: str, arguments: dict | None = None) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> dict:
        if self.proc.stdin:
            self.proc.stdin.close()
        terminated = False
        try:
            code = self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            terminated = True
            self.proc.kill()
            code = self.proc.wait(timeout=3)
        for thread in self.threads:
            thread.join(timeout=2)
        return {"pid": self.proc.pid, "exit_code": code, "forced": terminated,
                "stdout_sha256": sha(self.output / "mcp-stdout.txt"),
                "stderr_sha256": sha(self.output / "mcp-stderr.txt"),
                "output_cap_exceeded": self.overflow}


def classify(calls: list[dict], project: Path, pin: dict) -> dict:
    connected = False
    info_ok = tree_ok = active_ok = property_ok = retry_ok = False
    trees = []
    ownership_fields = set()
    readonly_surface = True
    for row in calls:
        request, response = row["request"], row.get("response") or {}
        name = request.get("params", {}).get("name")
        value = payload(response)
        if request["method"] == "tools/list":
            for tool in response.get("result", {}).get("tools", []):
                ownership_fields.update(set(tool.get("inputSchema", {}).get("properties", {})))
                readonly_surface &= tool.get("annotations", {}).get("readOnlyHint") is True
        if name == "godot_health_check":
            connected |= value.get("bridge_connected") is True
        if name == "godot_inspection_get_project_info":
            # Engine.get_version_info().string is a display label; the binary
            # SHA and native startup banner independently bind the full commit.
            info_ok = (value.get("godot_version") == pin["version"] + " (official)"
                       and Path(value.get("project_path", "")).resolve() == project.resolve())
            row["postcondition"] = "PIN_AND_SCRATCH_ROOT_MATCH" if info_ok else "NOT_OBSERVED"
        if name == "godot_inspection_get_active_scene":
            active_ok = value.get("path") == "res://scenes/arena.tscn" and value.get("is_open") is True
            row["postcondition"] = "ARENA_OPEN" if active_ok else "NOT_OBSERVED"
        if name == "godot_inspection_get_scene_tree":
            tree = value.get("tree") or {}
            children = {node.get("name"): node.get("type") for node in tree.get("children", [])}
            tree_ok = (tree.get("name") == "Arena" and tree.get("type") == "Node2D"
                       and children.get("Player") == "CharacterBody2D"
                       and children.get("Floor") == "StaticBody2D")
            row["postcondition"] = "ARENA_NODE_TYPES_MATCH" if tree_ok else "NOT_OBSERVED"
            trees.append(tree)
        if name == "godot_inspection_get_node_property":
            property_ok = value.get("exists") is True and value.get("value") == "HP 3"
            row["postcondition"] = "HUD_TEXT_MATCH" if property_ok else "NOT_OBSERVED"
    retry_ok = len(trees) == 2 and trees[0] == trees[1] and bool(trees[0])
    return {"bridge_connected": connected, "project_info": info_ok, "active_scene": active_ok,
            "scene_tree": tree_ok, "node_property": property_ok, "repeat_readback": retry_ok,
            "native_readback": all((connected, info_ok, active_ok, tree_ok, property_ok, retry_ok)),
            "server_read_only_surface": readonly_surface,
            "discovery_ownership_fields": sorted(ownership_fields & {"lease", "lease_id", "fencing_epoch", "command_id", "journal"}),
            "lease": "NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE", "journal": "NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE",
            "command_id": "MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID"}


def worker(plan_path: Path) -> int:
    plan = json.loads(plan_path.read_text())
    verify_frozen(plan)
    output = Path(plan["output"])
    project = output / "project"
    project.mkdir()
    shutil.copytree(Path(plan["fixture"]) / "scenes", project / "scenes")
    shutil.copytree(Path(plan["repo"]) / "godot/addons/godot_mcp", project / "addons/godot_mcp",
                    ignore=shutil.ignore_patterns("*.import"))
    watchdog = project / "addons/host_watchdog"
    watchdog.mkdir()
    (watchdog / "plugin.gd").write_text(WATCHDOG, encoding="utf-8")
    (watchdog / "plugin.cfg").write_text('[plugin]\nname="K13 host stop"\ndescription="Bounded scratch lifecycle"\nauthor="HH Studio"\nversion="1"\nscript="plugin.gd"\n', encoding="utf-8")
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="HH K13 MCP Arena Copy"\n'
        'run/main_scene="res://scenes/arena.tscn"\n[editor_plugins]\n'
        'enabled=PackedStringArray("res://addons/godot_mcp/plugin.cfg", "res://addons/host_watchdog/plugin.cfg")\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding="utf-8")
    frozen = {p.relative_to(project).as_posix(): sha(p) for p in project.rglob("*") if p.is_file()}
    write(output / "project-freeze.json", frozen)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GODOT_", "HH_", "PYTHON"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        path = output / "user" / key
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env.update(GODOT_MCP_BRIDGE_URL=f"ws://127.0.0.1:{port}", GODOT_MCP_TRANSPORT="stdio",
               GODOT_MCP_APPROVAL_REQUIRE="true", GODOT_MCP_APPROVAL_FAIL_OPEN="false")
    result = {"schema": SCHEMA, "authority": 0, "acceptance": False, "run_id": plan["run_id"],
              "source_closure_sha256": plan["source_closure_sha256"], "server_pin": PIN,
              "host": {"os": platform.platform(), "python": sys.version.split()[0], "godot": plan["godot_pin"]},
              "client": {"name": "hh-k13-native-read-client", "version": "0.2.0", "model": "UNSPECIFIED", "protocol": PROTOCOL},
              "adapter": {"name": "hybridindie/godot-mcp", "bridge_url": env["GODOT_MCP_BRIDGE_URL"], "fixture": str(project)},
              "host_adapter_started": False, "status": "HARNESS_FAILURE", "calls": [], "errors": []}
    peer = godot = None
    streams = []
    try:
        # Populate Godot's class cache before the live editor. This is sequential,
        # and both native children remain in the outer gated Job.
        with (output / "import-stdout.txt").open("xb") as so, (output / "import-stderr.txt").open("xb") as se:
            imported = subprocess.run([plan["godot"], "--headless", "--editor", "--path", str(project), "--import", "--quit"],
                                      env=env, stdout=so, stderr=se, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        result["import_exit"] = imported.returncode
        if imported.returncode != 0:
            raise RuntimeError("IMPORT_EXIT")
        peer = Wire([plan["python"], "-m", "mcp_server.main"], Path(plan["repo"]), env, output)
        peer.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                    "clientInfo": {"name": result["client"]["name"], "version": "0.2.0"}})
        peer.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        peer.request("tools/list", {})
        so = (output / "godot-stdout.txt").open("xb")
        se = (output / "godot-stderr.txt").open("xb")
        streams = [so, se]
        godot = subprocess.Popen([plan["godot"], "--headless", "--editor", "--path", str(project),
                                  "res://scenes/arena.tscn"], env=env, stdout=so, stderr=se,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 22
        while time.monotonic() < deadline:
            if payload(peer.call("godot_health_check")).get("bridge_connected") is True:
                break
            if godot.poll() is not None:
                raise RuntimeError("GODOT_EARLY_EXIT")
            time.sleep(.5)
        else:
            raise TimeoutError("BRIDGE_NOT_CONNECTED")
        peer.call("godot_get_server_info")
        peer.call("godot_inspection_get_project_info")
        peer.call("godot_inspection_get_active_scene")
        peer.call("godot_inspection_get_scene_tree", {"max_depth": 1, "lightweight": True})
        peer.call("godot_inspection_get_node_property", {"node_path": "HUD/Status", "property": "text"})
        peer.call("godot_inspection_get_scene_tree", {"max_depth": 1, "lightweight": True})
    except Exception as error:
        result["errors"].append(type(error).__name__ + ":" + str(error))
    finally:
        if godot is not None:
            (project / ".probe-stop").write_text("stop\n")
            forced = False
            try:
                code = godot.wait(timeout=8)
            except subprocess.TimeoutExpired:
                forced = True
                godot.kill()
                code = godot.wait(timeout=3)
            result["godot"] = {"pid": godot.pid, "exit_code": code, "forced": forced}
        for stream in streams:
            stream.close()
        if peer is not None:
            result["mcp"] = peer.close()
            result["calls"] = peer.calls
        result["observation"] = classify(result["calls"], project, plan["godot_pin"])
        result["scratch_source_unchanged"] = all(sha(project / name) == value for name, value in frozen.items())
        try:
            verify_frozen(plan)
            result["input_source_unchanged"] = True
        except ValueError as error:
            result["input_source_unchanged"] = False
            result["errors"].append(str(error))
        logs = {p.name: sha(p) for p in output.glob("*-std*.txt")}
        result["raw_logs"] = logs
        native_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in output.glob("godot-std*.txt"))
        result["native_pin_banner"] = "Godot Engine v" + plan["godot_pin"]["observed_version"] + " - " in native_text
        result["native_warning_error_lines"] = [line for line in native_text.splitlines() if re.match(r"^(WARNING:|ERROR:|SCRIPT ERROR:)", line)]
        native_ok = result["observation"]["native_readback"]
        exits_ok = all(result.get(name, {}).get("exit_code") == 0 and result[name].get("forced") is False for name in ("godot", "mcp"))
        result["native_gate"] = "INCOMPATIBLE" if result["native_warning_error_lines"] else "UNSUPPORTED"
        result["native_gate_reasons"] = ["Fixed read operations use the external direct bridge without an HH lease, journal, or semantic command_id."]
        if result["native_warning_error_lines"]:
            result["native_gate_reasons"].append("The native editor with the pinned external addon emitted cleanup warnings/errors; raw retained.")
        if native_ok and exits_ok and result["native_pin_banner"] and not result["errors"] and result["scratch_source_unchanged"] and result["input_source_unchanged"]:
            result["status"] = "MEASURED_EXTERNAL_NATIVE_LIMIT"
        write(output / "native.json", result)
    return 0 if result["status"] == "MEASURED_EXTERNAL_NATIVE_LIMIT" else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture", type=Path, default=STUDIO / ".local/gt09-native-hybrid-20261008-03")
    parser.add_argument("--repo", type=Path, default=STUDIO / ".local/mcp-spike-20261008/godot-mcp")
    parser.add_argument("--python", type=Path, default=STUDIO / ".local/mcp-spike-20261008/venv/Scripts/python.exe")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker)
    if args.dry_run:
        plan = prepare(args)
        print(json.dumps({"status": "DRY_RUN_READY", "source_closure_sha256": plan["source_closure_sha256"], "output": plan["output"]}))
        return 0
    if not args.run_id or not re.fullmatch(r"gt09-mcp-native-[a-z0-9-]{1,60}", args.run_id):
        raise ValueError("RUN_ID")
    output = STUDIO / ".local/reviews" / args.run_id
    plan_path = output / "dry-run.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen(plan)
    if (output / "native.json").exists() or (output / "native-host.json").exists():
        raise ValueError("RUN_ID_USED")
    guard_host()
    result = bootstrap().run_process([sys.executable, str(Path(__file__).resolve()), "--worker", str(plan_path)],
                                      cwd=output, output=output, timeout=DEADLINE_SECONDS, label="native")
    write(output / "host-job.json", result)
    native = json.loads((output / "native.json").read_text()) if (output / "native.json").exists() else {}
    status = native.get("status", "HARNESS_FAILURE")
    good = (result.get("exit_code") == 0 and result.get("wrapper_exit_code") == 0
            and result.get("tree_verified") is True and result.get("timed_out") is False)
    write(output / "result.json", {"schema": SCHEMA, "run_id": args.run_id, "authority": 0, "acceptance": False,
                                   "status": status if good else "HARNESS_FAILURE", "host_job": result,
                                   "native_sha256": sha(output / "native.json") if native else None,
                                   "source_closure_sha256": plan["source_closure_sha256"]})
    print(json.dumps({"status": status if good else "HARNESS_FAILURE", "output": str(output), "job": result}))
    return 0 if good and status == "MEASURED_EXTERNAL_NATIVE_LIMIT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
