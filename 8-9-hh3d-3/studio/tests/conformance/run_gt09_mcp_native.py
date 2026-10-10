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
TOOLKIT_PIN = "10a4508e880244c66a3f04861b2e22872c307247"
SCHEMA = "hh-gt09-mcp-native-spike-2"
PROTOCOL = "2025-11-25"
DEADLINE_SECONDS = 110
HYBRID_TOOLS = {
    "godot_health_check", "godot_get_server_info",
    "godot_inspection_get_project_info", "godot_inspection_get_scene_tree",
    "godot_inspection_get_active_scene", "godot_inspection_get_node_property",
}
TOOLKIT_TOOLS = {"scene_get_tree", "node_get_property", "scene_open", "project_get_settings"}
TOOLS = HYBRID_TOOLS | TOOLKIT_TOOLS
TOOLKIT_PACKAGE = "@npgamedev/godot-mcp-server"
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


def toolkit_package() -> tuple[Path, Path, Path]:
    """Resolve the already-installed toolkit bridge without invoking npm/npx."""
    node_path = shutil.which("node")
    if not node_path:
        raise ValueError("NODE_EXECUTABLE_NOT_FOUND")
    node = regular(Path(node_path))
    cache = Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx"
    candidates = []
    for package_json in cache.glob(f"*/node_modules/{TOOLKIT_PACKAGE}/package.json"):
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
            if package.get("version") == "1.0.3":
                candidates.append(package_json)
        except (OSError, ValueError):
            continue
    if not candidates:
        raise ValueError("TOOLKIT_NODE_PACKAGE_NOT_INSTALLED")
    package_json = max(candidates, key=lambda p: p.stat().st_mtime)
    package_root = package_json.parent
    entry = package_root / "dist/index.js"
    return node, regular(package_root), regular(entry)


def source_hashes(repo: Path, fixture: Path, godot: Path, python: Path, *, adapter: str,
                  node: Path | None = None, package_root: Path | None = None,
                  server_entry: Path | None = None) -> dict[str, str]:
    paths = [Path(__file__).resolve(), STUDIO / "build/bootstrap/run_fixture.py",
             STUDIO / "toolchain.lock.json", godot, fixture / "project.godot"]
    if adapter == "hybridindie/godot-mcp":
        paths.append(python)
    addon = (repo / "godot/addons/godot_mcp" if adapter == "hybridindie/godot-mcp"
             else repo / "addons/godot_mcp_toolkit")
    bases = (repo / "mcp_server", addon, fixture / "scenes") if adapter == "hybridindie/godot-mcp" else (addon, fixture / "scenes")
    if adapter == "NPGameDev/godot-mcp-toolkit":
        if node is None or package_root is None or server_entry is None:
            raise ValueError("TOOLKIT_NODE_PACKAGE_NOT_INSTALLED")
        paths.extend((node, server_entry))
        bases = bases + (package_root,)
    for base in bases:
        paths.extend(p for p in base.rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".import"})
    return {str(regular(p)): sha(p) for p in sorted(set(paths))}


def verify_frozen(plan: dict, *, full: bool = True) -> None:
    if plan.get("schema") != SCHEMA or plan.get("dry_run") is not True:
        raise ValueError("DRY_RUN_REQUIRED")
    for path, expected in plan["source_hashes"].items():
        current = regular(Path(path))
        if not full:
            stat = current.stat()
            frozen_stat = plan.get("source_stats", {}).get(path, {})
            if stat.st_size != frozen_stat.get("size") or stat.st_mtime_ns != frozen_stat.get("mtime_ns"):
                raise ValueError("SOURCE_STAT_DRIFT:" + path)
            continue
        if sha(current) != expected:
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
         capture_output=True, text=True, timeout=30, check=True)
    if result.stdout.strip():
        raise ValueError("NATIVE_PROCESS_BUSY:" + result.stdout.strip())


def prepare(args) -> dict:
    if not re.fullmatch(r"gt09-mcp-native-[a-z0-9-]{1,60}", args.run_id):
        raise ValueError("RUN_ID")
    output = (STUDIO / ".local/reviews" / args.run_id).absolute()
    if output.exists():
        raise ValueError("RUN_ID_USED")
    repo, fixture, python = map(regular, (args.repo, args.fixture, args.python))
    if args.adapter not in {"hybridindie/godot-mcp", "NPGameDev/godot-mcp-toolkit"}:
        raise ValueError("ADAPTER")
    lock = json.loads((STUDIO / "toolchain.lock.json").read_text())["godot"]
    godot_key = "gui_executable" if args.adapter == "hybridindie/godot-mcp" else "console_executable"
    godot = regular(STUDIO / ".local/tooling" / ("godot-" + lock["version"]) / lock[godot_key])
    expected_godot_hash = lock["gui_sha256"] if godot_key == "gui_executable" else lock["console_sha256"]
    if sha(godot) != expected_godot_hash or lock["version"] != "4.7.2-stable":
        raise ValueError("GODOT_PIN")
    pin = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, timeout=10).strip()
    expected_pin = PIN if args.adapter == "hybridindie/godot-mcp" else TOOLKIT_PIN
    dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True, timeout=10)
    if pin != expected_pin or dirty:
        raise ValueError("EXTERNAL_PIN_OR_DIRTY")
    if not (fixture / "scenes/arena.tscn").is_file():
        raise ValueError("SAVED_ARENA_FIXTURE_REQUIRED")
    node = package_root = server_entry = None
    if args.adapter == "NPGameDev/godot-mcp-toolkit":
        node, package_root, server_entry = toolkit_package()
    sources = source_hashes(repo, fixture, godot, python, adapter=args.adapter,
                            node=node, package_root=package_root, server_entry=server_entry)
    plan = {"schema": SCHEMA, "dry_run": True, "run_id": args.run_id, "authority": 0,
            "created_at": datetime.now(timezone.utc).isoformat(), "repo": str(repo),
            "fixture": str(fixture), "python": str(python), "godot": str(godot),
            "node": str(node) if node else None,
            "toolkit_package": str(package_root) if package_root else None,
            "server_entry": str(server_entry) if server_entry else None,
            "godot_pin": lock, "source_hashes": sources,
            "source_stats": {path: {"size": Path(path).stat().st_size,
                                     "mtime_ns": Path(path).stat().st_mtime_ns}
                             for path in sources},
            "source_closure_sha256": digest(sources), "deadline_seconds": DEADLINE_SECONDS,
            "source_current_binding": True,
            "operation_allowlist": sorted(HYBRID_TOOLS if args.adapter == "hybridindie/godot-mcp" else TOOLKIT_TOOLS), "host_adapter_started": False,
            "client_model": "UNSPECIFIED", "adapter": args.adapter, "output": str(output)}
    output.mkdir(parents=True)
    write(output / "dry-run.json", plan)
    return plan


_UNTRUSTED = re.compile(r"^<untrusted-[0-9a-f]+(?:\s[^>]*)?>\s*(.*?)\s*</untrusted-[0-9a-f]+>$",
                        re.DOTALL)


def _decode_text(value: str) -> Any:
    """Decode toolkit text JSON and its nonce-tagged untrusted envelope."""
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        decoded = value
    if isinstance(decoded, str):
        match = _UNTRUSTED.fullmatch(decoded.strip())
        if match:
            try:
                return json.loads(match.group(1))
            except ValueError:
                return decoded
    return decoded


def payload(response: dict) -> dict:
    result = response.get("result", {})
    if result.get("isError") is True or "error" in response:
        return {}
    value = result.get("structuredContent")
    if type(value) is dict:
        return value
    # NPGameDev's bridge returns command payloads as one JSON object inside a
    # text content block. Decode only that bounded response; never interpret
    # arbitrary log text as structured state.
    for item in result.get("content", []):
        if not isinstance(item, dict) or item.get("type") != "text":
            continue
        decoded = _decode_text(item.get("text", ""))
        if isinstance(decoded, dict):
            for key, value in list(decoded.items()):
                if isinstance(value, str):
                    nested = _decode_text(value)
                    if nested is not value:
                        decoded[key] = nested
            if isinstance(decoded.get("data"), dict) and decoded.get("success") is True and len(decoded) == 2:
                return decoded["data"]
            return decoded
    return {}


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


def classify(calls: list[dict], project: Path, pin: dict,
             adapter: str = "hybridindie/godot-mcp") -> dict:
    if adapter == "NPGameDev/godot-mcp-toolkit":
        trees = []
        connected = property_ok = open_ok = settings_ok = False
        readonly_surface = True
        ownership_fields = set()
        for row in calls:
            request, response = row["request"], row.get("response") or {}
            method = request.get("params", {}).get("name")
            value = payload(response)
            if response.get("result", {}).get("isError") is not True and isinstance(value, dict):
                connected = True
            if request["method"] == "tools/list":
                for tool in response.get("result", {}).get("tools", []):
                    ownership_fields.update(set(tool.get("inputSchema", {}).get("properties", {})))
                    readonly_surface &= tool.get("annotations", {}).get("readOnlyHint") is True
            if method == "scene_get_tree":
                tree = value.get("tree") or {}
                if isinstance(tree, str):
                    tree = _decode_text(tree)
                if not isinstance(tree, dict):
                    tree = {}
                children = {node.get("name"): node.get("class", node.get("type"))
                            for node in tree.get("children", [])}
                trees.append(tree)
                row["postcondition"] = "ARENA_NODE_TYPES_MATCH" if (
                    tree.get("name") == "Arena" and children.get("Player") == "CharacterBody2D"
                    and children.get("Floor") == "StaticBody2D") else "NOT_OBSERVED"
            elif method == "node_get_property":
                property_ok |= value.get("value") == "HP 3"
                row["postcondition"] = "HUD_TEXT_MATCH" if value.get("value") == "HP 3" else "NOT_OBSERVED"
            elif method == "scene_open":
                open_ok |= value.get("path") == "res://scenes/arena.tscn"
                row["postcondition"] = "ARENA_OPEN" if open_ok else "NOT_OBSERVED"
            elif method == "project_get_settings":
                settings_ok |= (isinstance(value, dict) and isinstance(value.get("settings"), (dict, str))
                                and isinstance(value.get("count"), int) and value.get("count", 0) > 0)
        tree_ok = len(trees) == 2 and bool(trees[0]) and trees[0] == trees[1]
        return {"bridge_connected": connected, "project_info": settings_ok,
                "active_scene": open_ok, "scene_tree": tree_ok,
                "node_property": property_ok, "repeat_readback": tree_ok,
                "native_readback": all((settings_ok, open_ok, tree_ok, property_ok)),
                "server_read_only_surface": readonly_surface,
                "discovery_ownership_fields": sorted(ownership_fields & {"lease", "lease_id", "fencing_epoch", "command_id", "journal"}),
                "lease": "NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE", "journal": "NOT_TRAVERSED_EXTERNAL_DIRECT_ROUTE",
                "command_id": "MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID"}
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
    # The parent performed the full content hash immediately before entering
    # the gated worker. Recheck immutable source stats here without spending
    # the native wall budget rehashing multi-hundred-MB binaries.
    verify_frozen(plan, full=False)
    output = Path(plan["output"])
    project = output / "project"
    project.mkdir()
    shutil.copytree(Path(plan["fixture"]) / "scenes", project / "scenes")
    addon_name = "godot_mcp" if plan["adapter"] == "hybridindie/godot-mcp" else "godot_mcp_toolkit"
    addon_source = (Path(plan["repo"]) / "godot/addons/godot_mcp"
                    if plan["adapter"] == "hybridindie/godot-mcp"
                    else Path(plan["repo"]) / "addons/godot_mcp_toolkit")
    project_config = (
        'config_version=5\n[application]\nconfig/name="HH K13 MCP Arena Copy"\n'
        'run/main_scene="res://scenes/arena.tscn"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    (project / "project.godot").write_text(project_config, encoding="utf-8")
    host_localappdata = os.environ.get("LOCALAPPDATA", "")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GODOT_", "HH_", "PYTHON"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        path = output / "user" / key
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    with socket.socket() as sock:
        if plan["adapter"] == "NPGameDev/godot-mcp-toolkit":
            # The toolkit owns a fixed editor-port band and discovers the
            # project through its registry.  Pick one free port in that band
            # and bind the bridge to the same project explicitly.
            for candidate in range(6550, 6561):
                try:
                    sock.bind(("127.0.0.1", candidate))
                    port = candidate
                    break
                except OSError:
                    continue
            else:
                raise RuntimeError("TOOLKIT_EDITOR_PORT_BUSY")
        else:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
    env.update(GODOT_MCP_TRANSPORT="stdio", GODOT_MCP_CONFIG_VERSION="1",
               GODOT_MCP_READ_ONLY="1", GODOT_MCP_APPROVAL_REQUIRE="true",
               GODOT_MCP_APPROVAL_FAIL_OPEN="false")
    if plan["adapter"] == "NPGameDev/godot-mcp-toolkit":
        env.update(GODOT_MCP_EDITOR_PORT=str(port), GODOT_MCP_PROJECT_PATH=str(project))
        bridge_url = f"ws://127.0.0.1:{port}"
    else:
        env["GODOT_MCP_BRIDGE_URL"] = f"ws://127.0.0.1:{port}"
        bridge_url = env["GODOT_MCP_BRIDGE_URL"]
    result = {"schema": SCHEMA, "authority": 0, "acceptance": False, "run_id": plan["run_id"],
              "source_closure_sha256": plan["source_closure_sha256"],
              "server_pin": PIN if plan["adapter"] == "hybridindie/godot-mcp" else TOOLKIT_PIN,
              "host": {"os": platform.platform(), "python": sys.version.split()[0], "godot": plan["godot_pin"]},
              "client": {"name": "hh-k13-native-read-client", "version": "0.2.0", "model": "UNSPECIFIED", "protocol": PROTOCOL},
              "adapter": {"name": plan["adapter"], "bridge_url": bridge_url, "fixture": str(project)},
              "host_adapter_started": False, "status": "HARNESS_FAILURE", "calls": [],
              "discarded_probe_ids": [], "errors": []}
    peer = godot = None
    streams = []
    frozen: dict[str, str] = {}
    try:
        # The fixture contains only text scenes and no imported binary assets.
        # A separate --quit-after import worker races Godot's filesystem scan
        # and can abort it, leaving no native receipt.  Keep the required raw
        # import artifacts, but let the single native editor perform its own
        # deterministic scan and record that no separate import was needed.
        # The fixture contains only text scenes.  Its only authoritative
        # import/scan is performed by the one native editor process below;
        # there is deliberately no second Godot import worker to race it.
        (output / "import-stdout.txt").touch()
        (output / "import-stderr.txt").touch()
        result["import_exit"] = None
        result["import_mode"] = "NATIVE_EDITOR_SCAN"
        # Enable the native addon only in the single live editor process.
        shutil.copytree(addon_source, project / "addons" / addon_name,
                        ignore=shutil.ignore_patterns("*.import"))
        watchdog = project / "addons/host_watchdog"
        watchdog.mkdir()
        (watchdog / "plugin.gd").write_text(WATCHDOG, encoding="utf-8")
        (watchdog / "plugin.cfg").write_text('[plugin]\nname="K13 host stop"\ndescription="Bounded scratch lifecycle"\nauthor="HH Studio"\nversion="1"\nscript="plugin.gd"\n', encoding="utf-8")
        enabled_config = project_config + (
            '[editor_plugins]\n'
            f'enabled=PackedStringArray("res://addons/{addon_name}/plugin.cfg", '
            '"res://addons/host_watchdog/plugin.cfg")\n'
        )
        (project / "project.godot").write_text(enabled_config, encoding="utf-8")
        # Freeze authored runtime closure only. Godot writes project.godot
        # plugin settings and .godot caches during startup; those are runtime
        # state, not source mutation evidence.
        frozen = {p.relative_to(project).as_posix(): sha(p) for p in project.rglob("*")
                  if p.is_file() and ".godot" not in p.parts and p.name != "project.godot"}
        write(output / "project-freeze.json", frozen)
        server_cmd = ([plan["python"], "-m", "mcp_server.main"]
                      if plan["adapter"] == "hybridindie/godot-mcp" else
                       [plan["node"], plan["server_entry"]])
        server_cwd = Path(plan["repo"]) if plan["adapter"] == "hybridindie/godot-mcp" else STUDIO
        peer = Wire(server_cmd, server_cwd, env, output)
        # FastMCP startup imports a sizeable dependency graph on a cold worker;
        # the bounded outer Job still caps the complete probe at 110 seconds.
        # FastMCP registration is cold-start sensitive on a Windows worker.
        # Keep one bounded probe, but use a measured 60-second startup budget
        # instead of classifying a slow first import as transport failure.
        toolkit_timeout = 60
        peer.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                     "clientInfo": {"name": result["client"]["name"], "version": "0.2.0"}},
                     timeout=toolkit_timeout)
        peer.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        peer.request("tools/list", {}, timeout=toolkit_timeout)
        so = (output / "godot-stdout.txt").open("xb")
        se = (output / "godot-stderr.txt").open("xb")
        streams = [so, se]
        # Open the authored scene explicitly.  Headless editor startup with
        # only --path can finish its filesystem scan without activating the
        # addon bridge, making every health probe a false transport timeout.
        godot_command = [plan["godot"], "--headless", "--editor", "--path", str(project),
                         "res://scenes/arena.tscn"]
        godot = subprocess.Popen(godot_command, env=env, stdout=so, stderr=se,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + (25 if plan["adapter"] == "NPGameDev/godot-mcp-toolkit" else 22)
        while time.monotonic() < deadline:
            if godot.poll() is not None:
                raise RuntimeError("GODOT_EARLY_EXIT")
            if plan["adapter"] == "NPGameDev/godot-mcp-toolkit":
                startup = (output / "godot-stdout.txt").read_text(encoding="utf-8", errors="replace")
                ready = ("[MCPServer] listening on 127.0.0.1:" in startup
                         and "[MCPRegistry] registered " in startup)
            else:
                # A bridge can need several seconds after the stdio server is
                # ready.  Failed health probes are bounded and discarded from
                # the signed call transcript; only complete JSON responses are
                # part of the wire evidence.
                try:
                    ready = payload(peer.request(
                        "tools/call", {"name": "godot_health_check", "arguments": {}},
                        timeout=2.0)).get("bridge_connected") is True
                except (TimeoutError, RuntimeError):
                    if peer.calls and peer.calls[-1].get("response") is None:
                        result["discarded_probe_ids"].append(peer.calls[-1]["request"]["id"])
                        peer.calls.pop()
                    ready = False
                if ready:
                    # Bridge connection precedes editor scene activation during
                    # first filesystem scan.  Poll the real active-scene
                    # postcondition, but discard this readiness probe so the
                    # signed transcript retains the fixed operation sequence.
                    try:
                        scene_probe = peer.request(
                            "tools/call",
                            {"name": "godot_inspection_get_active_scene", "arguments": {}},
                            timeout=2.0)
                        ready = payload(scene_probe).get("is_open") is True
                    except (TimeoutError, RuntimeError):
                        ready = False
                    finally:
                        if peer.calls:
                            result["discarded_probe_ids"].append(peer.calls[-1]["request"]["id"])
                            peer.calls.pop()
            if ready:
                break
            time.sleep(.5)
        else:
            raise TimeoutError("BRIDGE_NOT_CONNECTED")
        if plan["adapter"] == "hybridindie/godot-mcp":
            peer.call("godot_get_server_info")
            peer.call("godot_inspection_get_project_info")
            peer.call("godot_inspection_get_active_scene")
            peer.call("godot_inspection_get_scene_tree", {"max_depth": 1, "lightweight": True})
            peer.call("godot_inspection_get_node_property", {"node_path": "HUD/Status", "property": "text"})
            peer.call("godot_inspection_get_scene_tree", {"max_depth": 1, "lightweight": True})
        else:
            peer.call("scene_open", {"file_path": "res://scenes/arena.tscn"})
            peer.call("project_get_settings", {"prefix": "application"})
            peer.call("scene_get_tree", {"max_depth": 1, "include_properties": False})
            peer.call("node_get_property", {"node_path": "HUD/Status", "property": "text"})
            peer.call("scene_get_tree", {"max_depth": 1, "include_properties": False})
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
                try:
                    code = godot.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # GUI editor processes can keep a child message loop after
                    # SIGKILL.  Kill the whole native tree, then retain the
                    # real wrapper result instead of losing the receipt in a
                    # second timeout.
                    subprocess.run(["taskkill", "/PID", str(godot.pid), "/T", "/F"],
                                   capture_output=True, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    try:
                        code = godot.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        code = -1
            result["godot"] = {"pid": godot.pid, "exit_code": code, "forced": forced}
        for stream in streams:
            stream.close()
        if peer is not None:
            result["mcp"] = peer.close()
            result["calls"] = peer.calls
        result["observation"] = classify(result["calls"], project, plan["godot_pin"], plan["adapter"])
        result["scratch_source_unchanged"] = all(sha(project / name) == value for name, value in frozen.items())
        try:
            verify_frozen(plan, full=False)
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
        # A clean native readback with real process exits is a measured external
        # limitation even when the external addon emits warnings/errors; those
        # diagnostics select native_gate=INCOMPATIBLE and remain in raw evidence.
        if native_ok and exits_ok and result["native_pin_banner"] and not result["errors"] and result["scratch_source_unchanged"] and result["input_source_unchanged"]:
            result["status"] = "MEASURED_EXTERNAL_NATIVE_LIMIT"
        write(output / "native.json", result)
    return 0 if result["status"] == "MEASURED_EXTERNAL_NATIVE_LIMIT" else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--adapter", choices=("hybridindie/godot-mcp", "NPGameDev/godot-mcp-toolkit"), default="hybridindie/godot-mcp")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fixture", type=Path, default=STUDIO / ".local/gt09-native-hybrid-20261008-03")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--python", type=Path, default=STUDIO / ".local/mcp-spike-20261008/venv/Scripts/python.exe")
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.repo is None:
        args.repo = (STUDIO / ".local/mcp-spike-20261008/godot-mcp-toolkit"
                     if args.adapter == "NPGameDev/godot-mcp-toolkit"
                     else STUDIO / ".local/mcp-spike-20261008/godot-mcp")
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
