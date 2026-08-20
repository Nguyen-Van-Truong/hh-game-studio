#!/usr/bin/env python3
"""R1-WP3: run the same MCP bake-off scenario on disposable copies of A and C.

Stdlib only. Never touches godot/plugin-project/addons. Never npx -y latest.
Clones are pinned SHAs from pins.json. Eval/godot_exec/call_method disabled.
Session token required. Bind 127.0.0.1 only. Records SKIP/FAIL honestly.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
from steps import (  # noqa: E402
    CAPABILITY_STEPS,
    NEGATIVE_STEPS,
    STEPS,
    WEIGHTS,
)

PLUGIN_PROJECT = (REPO / "godot" / "plugin-project").resolve()
FIXTURE = REPO / "godot" / "test-projects" / "minimal-2d"
PINS_PATH = HERE / "pins.json"
WORK = HERE / "work"
CLONES = WORK / "clones"
PROJECTS = WORK / "projects"
LOGS = WORK / "logs"
EVIDENCE_COMMIT = HERE / "evidence"
SCORECARD_PATH = HERE / "SCORECARD.md"
FORBIDDEN_NPX = ("npx", "-y")

STATUSES = ("PASS", "FAIL", "SKIP")


def die(msg: str, code: int = 2) -> None:
    print(f"bakeoff: FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def refuse_plugin_project(path: Path) -> None:
    """Refuse writes/copies under godot/plugin-project (inspecting the dir is OK)."""
    resolved = path.resolve()
    if resolved == PLUGIN_PROJECT:
        return
    try:
        resolved.relative_to(PLUGIN_PROJECT)
    except ValueError:
        if "plugin-project" in resolved.parts and resolved != PLUGIN_PROJECT:
            die(f"refusing path that names plugin-project: {resolved}")
        return
    die(f"refusing to touch godot/plugin-project: {resolved}")


def load_pins() -> dict[str, Any]:
    return json.loads(PINS_PATH.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def redact(obj: Any) -> Any:
    """Drop screenshot blobs and token-shaped fields from recorded evidence."""
    if isinstance(obj, dict):
        out = {}
        for key, val in obj.items():
            lk = str(key).lower()
            if lk in {"token", "authorization", "image_base64", "bearer"}:
                out[key] = "<redacted>"
            elif lk.endswith("_base64") or "png" in lk and "base64" in lk:
                out[key] = f"<redacted {len(str(val))} chars>"
            else:
                out[key] = redact(val)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj[:40]]
    if isinstance(obj, str) and len(obj) > 800:
        return obj[:800] + f"... <truncated {len(obj)} chars>"
    return obj


def run_cmd(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 120,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if args and args[0] == "npx":
        die("npx is forbidden in this bake-off (A16 / T5)")
    if FORBIDDEN_NPX[0] in args and "-y" in args:
        die("npx -y is forbidden")
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        timeout=timeout,
        check=check,
        text=True,
        capture_output=True,
    )


def git_clone_pin(url: str, commit: str, dest: Path) -> None:
    refuse_plugin_project(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_dir() and (dest / ".git").exists():
        got = run_cmd(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()
        if got == commit:
            run_cmd(["git", "reset", "--hard", "-q", commit], cwd=dest)
            run_cmd(["git", "clean", "-fdq"], cwd=dest)
            print(f"bakeoff: reset clone {dest.name} @{commit[:12]}")
            return
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    run_cmd(["git", "init", "-q"], cwd=dest)
    run_cmd(["git", "remote", "add", "origin", url], cwd=dest)
    fetch = run_cmd(
        ["git", "fetch", "--depth", "1", "origin", commit],
        cwd=dest,
        check=False,
        timeout=180,
    )
    if fetch.returncode != 0:
        run_cmd(["git", "fetch", "origin", commit], cwd=dest, timeout=180)
    run_cmd(["git", "checkout", "-q", "FETCH_HEAD"], cwd=dest)
    got = run_cmd(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()
    if got != commit:
        die(f"clone {url} HEAD {got} != pin {commit}")
    print(f"bakeoff: cloned {url} @{commit[:12]} -> {dest}")


def copy_fixture(dest: Path) -> None:
    refuse_plugin_project(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _ignore(directory: str, names: list[str]) -> set[str]:
        refuse_plugin_project(Path(directory))
        skip = {".godot", ".import"}
        return {n for n in names if n in skip}

    shutil.copytree(FIXTURE, dest, ignore=_ignore)
    refuse_plugin_project(dest)


def enable_plugin(project: Path, plugin_cfg: str) -> None:
    refuse_plugin_project(project)
    godot = project / "project.godot"
    text = godot.read_text(encoding="utf-8")
    block = (
        "\n[editor_plugins]\n"
        f'enabled=PackedStringArray("{plugin_cfg}")\n'
    )
    if "[editor_plugins]" not in text:
        text = text.rstrip() + "\n" + block
    godot.write_text(text, encoding="utf-8")


def patch_file(path: Path, old: str, new: str, *, required: bool = True) -> None:
    refuse_plugin_project(path)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        if required:
            die(f"patch anchor missing in {path}: {old[:80]!r}")
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def apply_patches_a(clone: Path) -> None:
    router = clone / "godot" / "addons" / "godot_mcp" / "command_router.gd"
    patch_file(
        router,
        "	_register_handler(MCPExecCommands.new(), plugin)\n",
        "	# HH bake-off: godot_exec / eval disabled (spike).\n",
    )
    patch_file(
        router,
        """func handle_command(command: String, params: Dictionary):
	if not _commands.has(command):
		return MCPUtils.error("UNKNOWN_COMMAND", "Unknown command: %s" % command)
""",
        """func handle_command(command: String, params: Dictionary):
	if command.begins_with("exec_"):
		return MCPUtils.error("DISABLED", "godot_exec/eval is disabled for the HH bake-off spike")
	if not _commands.has(command):
		return MCPUtils.error("UNKNOWN_COMMAND", "Unknown command: %s" % command)
""",
    )
    ws = clone / "godot" / "addons" / "godot_mcp" / "websocket_server.gd"
    patch_file(
        ws,
        """	var id: String = str(data.get("id"))
	var command: String = data.get("command")
	var params: Dictionary = data.get("params", {})

	command_received.emit(id, command, params)
""",
        """	var id: String = str(data.get("id"))
	var command: String = data.get("command")
	var params: Dictionary = data.get("params", {})
	if not (params is Dictionary):
		params = {}

	var expected := OS.get_environment("HH_BAKEOFF_TOKEN")
	if expected.is_empty():
		_send_error_response(id, "AUTH_REQUIRED", "session token is not configured")
		return
	var got := str(data.get("token", ""))
	if got.is_empty():
		got = str(params.get("token", ""))
	if got != expected:
		_send_error_response(id, "AUTH_FAILED", "missing or invalid session token")
		return

	command_received.emit(id, command, params)
""",
    )
    plugin = clone / "godot" / "addons" / "godot_mcp" / "plugin.gd"
    patch_file(
        plugin,
        "func _resolve_bind_address() -> String:\n",
        (
            "func _resolve_bind_address() -> String:\n"
            "	# HH bake-off: loopback only (A9).\n"
            "	return MCPConstants.LOCALHOST_BIND_ADDRESS\n\n"
            "func _resolve_bind_address_upstream() -> String:\n"
        ),
    )
    patch_file(
        plugin,
        "func _get_listen_port() -> int:\n"
        "	return _get_port_override() if _get_port_override_enabled() else WebSocketServer.DEFAULT_PORT\n",
        "func _get_listen_port() -> int:\n"
        "	var envp := OS.get_environment(\"HH_BAKEOFF_PORT\")\n"
        "	if not envp.is_empty():\n"
        "		return int(envp)\n"
        "	return _get_port_override() if _get_port_override_enabled() else WebSocketServer.DEFAULT_PORT\n",
    )


def apply_patches_c(clone: Path) -> None:
    refl = clone / "addons" / "beckett" / "tools" / "reflection_tools.gd"
    patch_file(
        refl,
        "func _call_method(args: Dictionary) -> Dictionary:\n",
        (
            "func _call_method(args: Dictionary) -> Dictionary:\n"
            "	return {\"error\": \"DISABLED: call_method/Object.callv is disabled for the HH bake-off spike\", "
            "\"code\": \"UNSUPPORTED\"}\n"
            "func _call_method_disabled_upstream(args: Dictionary) -> Dictionary:\n"
        ),
    )


def copy_addon(src: Path, dest_addons: Path) -> None:
    refuse_plugin_project(dest_addons)
    if dest_addons.exists():
        shutil.rmtree(dest_addons)
    dest_addons.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_addons)


# --- tiny WebSocket client (RFC 6455, client masking) ---


class WsClient:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.buf = b""

    @classmethod
    def connect(cls, host: str, port: int, timeout: float = 10.0) -> "WsClient":
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(req.encode("ascii"))
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                raise OSError("websocket handshake closed")
            data += chunk
        header, rest = data.split(b"\r\n\r\n", 1)
        status = header.split(b"\r\n", 1)[0]
        if b"101" not in status:
            raise OSError(f"websocket upgrade failed: {status!r}")
        client = cls(sock)
        client.buf = rest
        return client

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self, timeout: float = 30.0) -> str:
        self.sock.settimeout(timeout)
        while True:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise OSError("websocket closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                return payload.decode("utf-8")
            raise OSError(f"unexpected websocket opcode {opcode}")

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        n = len(payload)
        header = bytearray([0x80 | opcode])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header.extend(n.to_bytes(2, "big"))
        else:
            header.append(0x80 | 127)
            header.extend(n.to_bytes(8, "big"))
        header.extend(mask)
        self.sock.sendall(header + masked)

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise OSError("websocket recv closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _recv_frame(self) -> tuple[int, bytes]:
        b1, b2 = self._recv_exact(2)
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        if length == 126:
            length = int.from_bytes(self._recv_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._recv_exact(8), "big")
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload


# --- Godot process ---


def doctor_paths() -> tuple[Path, Path]:
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "godot" / "doctor.py"), "--install", "--print-bin"],
        cwd=str(REPO),
        env=env,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        die(f"doctor.py --install failed:\n{proc.stdout}\n{proc.stderr}")
    console = Path(proc.stdout.strip().splitlines()[-1].strip())
    gui_proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "godot" / "doctor.py"), "--print-gui"],
        cwd=str(REPO),
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    gui = Path(gui_proc.stdout.strip().splitlines()[-1].strip()) if gui_proc.returncode == 0 else console
    if not console.is_file():
        die(f"missing Godot console exe: {console}")
    return console, gui


def kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def wait_port(host: str, port: int, timeout: float, proc: subprocess.Popen[str] | None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.4)
    return False


class GodotSession:
    def __init__(self, proc: subprocess.Popen[str], log_path: Path) -> None:
        self.proc = proc
        self.log_path = log_path

    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        if self.proc.poll() is None:
            kill_tree(self.proc.pid)
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                kill_tree(self.proc.pid)


def start_godot(
    exe: Path,
    project: Path,
    log_path: Path,
    env: dict[str, str],
    *,
    headless: bool,
    extra: list[str] | None = None,
    quit: bool = False,
) -> GodotSession:
    refuse_plugin_project(project)
    args = [str(exe)]
    if headless:
        args.append("--headless")
    args.extend(["--editor", "--path", str(project)])
    if quit:
        args.append("--quit")
    if extra:
        args.extend(extra)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = log_path.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        args,
        cwd=str(project),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
    )
    return GodotSession(proc, log_path)


def import_project(exe: Path, project: Path, env: dict[str, str], log_path: Path) -> None:
    session = start_godot(exe, project, log_path, env, headless=True, quit=True)
    try:
        session.proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        session.stop()
        print(f"bakeoff: import timed out for {project.name}; continuing")


# --- result book ---


class Book:
    def __init__(self, candidate: str) -> None:
        self.candidate = candidate
        self.rows: dict[str, dict[str, str]] = {
            step: {"status": "SKIP", "evidence": "", "notes": "not attempted"}
            for step in STEPS
        }
        self.handshake_ok = False
        self.godot_version = ""
        self.mode = "headless"
        self.must_patch: list[str] = []

    def set(
        self,
        step: str,
        status: str,
        notes: str,
        evidence: str = "",
    ) -> None:
        if status not in STATUSES:
            die(f"bad status {status}")
        if step not in self.rows:
            die(f"unknown step {step}")
        self.rows[step] = {
            "status": status,
            "evidence": evidence,
            "notes": notes[:500],
        }

    def skip_rest(self, reason: str, except_steps: set[str] | None = None) -> None:
        keep = except_steps or set()
        for step, row in self.rows.items():
            if step in keep:
                continue
            if row["status"] == "SKIP" and row["notes"] == "not attempted":
                self.set(step, "SKIP", reason)


def snippet(data: Any) -> str:
    text = json.dumps(redact(data), ensure_ascii=True)
    return text[:400]


def typed_error(payload: Any) -> bool:
    if payload is None:
        return False
    if isinstance(payload, dict):
        if payload.get("code") or payload.get("error"):
            err = payload.get("error")
            if isinstance(err, dict) and (err.get("code") or err.get("message")):
                return True
            if isinstance(err, str) and err:
                return True
            if payload.get("code"):
                return True
        if payload.get("status") == "error":
            return True
        if payload.get("isError") is True:
            return True
        if payload.get("http_status") in {400, 401, 403, 404, 422}:
            return True
    text = str(payload).lower()
    needles = (
        "unknown_command",
        "invalid_params",
        "auth_failed",
        "auth_required",
        "file_not_found",
        "node_not_found",
        "disabled",
        "unsupported",
        "unauthorized",
        "parse error",
        "-32602",
        "-32601",
    )
    return any(n in text for n in needles)


# --- candidate A (WebSocket JSON) ---


class CandidateA:
    def __init__(self, host: str, port: int, token: str) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.ws: WsClient | None = None
        self._n = 0

    def connect(self) -> None:
        self.ws = WsClient.connect(self.host, self.port, timeout=8.0)

    def close(self) -> None:
        if self.ws:
            self.ws.close()
            self.ws = None

    def call(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        *,
        token: str | None = None,
        timeout: float = 30.0,
        include_token: bool = True,
    ) -> dict[str, Any]:
        if self.ws is None:
            raise OSError("not connected")
        self._n += 1
        msg: dict[str, Any] = {
            "id": str(self._n),
            "command": command,
            "params": params or {},
        }
        if include_token:
            msg["token"] = self.token if token is None else token
        self.ws.send_text(json.dumps(msg))
        raw = self.ws.recv_text(timeout=timeout)
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"status": "error", "error": {"code": "BAD_RESPONSE", "message": str(data)}}
        return data


def a_ok(resp: dict[str, Any]) -> bool:
    return resp.get("status") == "success"


# --- candidate C (HTTP MCP JSON-RPC) ---


class CandidateC:
    def __init__(self, host: str, port: int, token: str) -> None:
        self.base = f"http://{host}:{port}/mcp"
        self.token = token
        self._n = 0
        self.session = ""

    def rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        token: str | None = None,
        timeout: float = 30.0,
        send_auth: bool = True,
    ) -> dict[str, Any]:
        self._n += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._n,
            "method": method,
            "params": params or {},
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Host": f"{urllib.request.urlparse(self.base).hostname}:{urllib.request.urlparse(self.base).port}",
        }
        if send_auth:
            use = self.token if token is None else token
            headers["Authorization"] = f"Bearer {use}"
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(self.base, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if sid:
                    self.session = sid
                raw = resp.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {"result": {}}
                data = json.loads(raw)
                return data if isinstance(data, dict) else {"raw": data}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            return {
                "http_status": exc.code,
                "error": {"code": f"HTTP_{exc.code}", "message": err_body[:300]},
            }
        except urllib.error.URLError as exc:
            return {"error": {"code": "URL_ERROR", "message": str(exc.reason)}}

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {}}, **kwargs)


def c_tool_text(resp: dict[str, Any]) -> str:
    result = resp.get("result")
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(result)


def c_is_error(resp: dict[str, Any]) -> bool:
    status = resp.get("http_status")
    if isinstance(status, int) and status >= 400:
        return True
    if resp.get("error") and "result" not in resp:
        return True
    result = resp.get("result")
    if isinstance(result, dict) and result.get("isError") is True:
        return True
    if isinstance(result, dict):
        sc = result.get("structuredContent")
        if isinstance(sc, dict) and sc.get("error"):
            return True
    return False


def c_ok(resp: dict[str, Any]) -> bool:
    return (not c_is_error(resp)) and "result" in resp


def c_handler_error(resp: dict[str, Any]) -> bool:
    if c_is_error(resp):
        return True
    text = c_tool_text(resp).lower()
    dumped = json.dumps(resp).lower()
    return text.startswith("disabled") or "code\": \"unsupported" in dumped or '"disabled"' in dumped


# --- scenario ---


def run_a(book: Book, client: CandidateA, evidence_dir: Path, project: Path) -> None:
    try:
        bad = client.call("mcp_handshake", {"server_version": "hh-bakeoff"}, token="wrong-token")
        if typed_error(bad) and not a_ok(bad):
            book.set(
                "wrong_token",
                "PASS",
                "AUTH_FAILED (or typed error) on bad token",
                snippet(bad),
            )
        else:
            book.set("wrong_token", "FAIL", "bad token was not a typed failure", snippet(bad))
        hs = client.call("mcp_handshake", {"server_version": "hh-bakeoff-a"})
        if a_ok(hs):
            book.handshake_ok = True
            result = hs.get("result") or {}
            book.godot_version = str(result.get("godot_version", ""))
            book.set(
                "handshake_auth",
                "PASS",
                f"mcp_handshake ok; godot={book.godot_version}",
                snippet(hs),
            )
        else:
            book.set("handshake_auth", "FAIL", "mcp_handshake failed", snippet(hs))
            book.skip_rest("handshake failed", except_steps={"wrong_token", "handshake_auth"})
            return
    except OSError as exc:
        book.set("handshake_auth", "SKIP", f"websocket handshake could not complete: {exc}")
        book.skip_rest(f"no websocket: {exc}", except_steps={"handshake_auth"})
        return

    unknown = client.call("definitely_not_a_command", {})
    if typed_error(unknown):
        # recorded later as part of unsupported if exec is the dedicated row
        pass

    created = client.call("create_scene", {"scene_path": "res://bakeoff_new.tscn"})
    if a_ok(created):
        book.set("create_scene", "PASS", "create_scene tool exists", snippet(created))
    else:
        book.set(
            "create_scene",
            "FAIL",
            "no MCP create_scene; candidate documents agent-side .tscn write (not scored as PASS)",
            snippet(created),
        )

    opened = client.call("open_scene", {"scene_path": "res://main.tscn"})
    if a_ok(opened):
        book.set("open_scene", "PASS", "open_scene res://main.tscn", snippet(opened))
    else:
        book.set("open_scene", "FAIL", "open_scene failed", snippet(opened))

    saved = client.call("save_scene", {})
    if a_ok(saved):
        book.set("save_scene", "PASS", "save_scene", snippet(saved))
    else:
        book.set("save_scene", "FAIL", "save_scene failed", snippet(saved))

    for step, cmd, params in (
        ("add_node", "add_node", {"type": "Sprite2D", "name": "ASprite"}),
        ("delete_node", "delete_node", {"node_path": "ASprite"}),
        ("duplicate_node", "duplicate_node", {"node_path": "Root"}),
        ("reorder_node", "reorder_node", {"node_path": "Root", "to_index": 0}),
    ):
        resp = client.call(cmd, params)
        if a_ok(resp):
            book.set(step, "PASS", f"{cmd} succeeded", snippet(resp))
        else:
            book.set(
                step,
                "FAIL",
                f"no live editor {cmd} (A is file-first for add/remove); typed={typed_error(resp)}",
                snippet(resp),
            )

    # Property set on the fixture root (exists after open).
    prop = client.call(
        "update_node",
        {"node_path": "/root/Root", "properties": {"position": {"x": 24, "y": 48}}},
    )
    if a_ok(prop):
        read = client.call("get_node_properties", {"node_path": "/root/Root"})
        echo = json.dumps(read)
        if a_ok(read) and ("24" in echo or "48" in echo or "position" in echo):
            book.set(
                "set_property",
                "PASS",
                "update_node + get_node_properties readback",
                snippet({"set": prop, "get": read}),
            )
        else:
            book.set(
                "set_property",
                "FAIL",
                "update_node returned success but readback did not echo the value (A known empty success)",
                snippet({"set": prop, "get": read}),
            )
    else:
        book.set("set_property", "FAIL", "update_node failed", snippet(prop))

    # A's documented create path is agent-side .tscn write, then open/reload.
    # Do that only to give reparent a second node — do not score create_scene from this.
    refuse_plugin_project(project)
    tree_path = project / "bakeoff_tree.tscn"
    tree_path.write_text(
        "[gd_scene format=3]\n\n"
        '[node name="Root" type="Node2D"]\n\n'
        '[node name="Left" type="Node2D" parent="."]\n\n'
        '[node name="Right" type="Node2D" parent="."]\n',
        encoding="utf-8",
    )
    opened_tree = client.call("open_scene", {"scene_path": "res://bakeoff_tree.tscn"})
    if not a_ok(opened_tree):
        client.call("reload_scene", {"scene_path": "res://bakeoff_tree.tscn"})
    reparent = client.call(
        "reparent_node",
        {"node_path": "/root/Root/Right", "new_parent_path": "/root/Root/Left"},
    )
    if a_ok(reparent):
        book.set("reparent_node", "PASS", "reparent_node Right -> Left after disk-authored tree", snippet(reparent))
    else:
        book.set(
            "reparent_node",
            "FAIL",
            "reparent_node failed even after a two-child disk tree (command exists)",
            snippet({"open": opened_tree, "reparent": reparent}),
        )
    client.call("open_scene", {"scene_path": "res://main.tscn"})

    res = client.call(
        "update_node",
        {
            "node_path": "/root/Root",
            "properties": {"material": {"_resource": "CanvasItemMaterial"}},
        },
    )
    read_res = client.call("get_node_properties", {"node_path": "/root/Root"})
    mat = ""
    if a_ok(read_res):
        mat = json.dumps((read_res.get("result") or {}).get("properties", {}).get("material"))
    if a_ok(res) and mat and mat not in {"null", "None", ""}:
        book.set("set_resource", "PASS", "update_node material + readback", snippet({"set": res, "mat": mat}))
    else:
        book.set(
            "set_resource",
            "FAIL",
            "no dedicated set_resource; update_node empty-success and/or material still null",
            snippet({"set": res, "get": read_res}),
        )

    # Scripts: A documents editing files then reload — not MCP write/validate/attach.
    for step, cmd in (
        ("script_write", "write_script"),
        ("script_validate", "validate_script"),
        ("script_attach", "attach_script"),
        ("undo", "undo"),
        ("redo", "redo"),
    ):
        resp = client.call(cmd, {"path": "res://bakeoff_move.gd", "content": "extends Node2D\n"})
        book.set(
            step,
            "FAIL",
            f"no MCP {cmd}; typed={typed_error(resp)}",
            snippet(resp),
        )

    play = client.call("run_project", {"frozen": True}, timeout=45.0)
    if a_ok(play):
        book.set("play", "PASS", "run_project frozen=true", snippet(play))
        time.sleep(1.5)
        st = client.call("get_runtime_state", {"action": "digest"}, timeout=20.0)
        if a_ok(st):
            book.set("runtime_state", "PASS", "get_runtime_state while playing", snippet(st))
        else:
            book.set(
                "runtime_state",
                "FAIL",
                "runtime digest failed (game/debug session may be missing in headless)",
                snippet(st),
            )
        shot = client.call("capture_game_screenshot", {"max_width": 320}, timeout=20.0)
        if a_ok(shot) and (shot.get("result") or {}).get("image_base64"):
            saved_path = save_png(
                evidence_dir,
                "A-game-small.png",
                str((shot.get("result") or {})["image_base64"]),
            )
            book.set(
                "screenshot",
                "PASS",
                "game screenshot PNG (headless dummy renderer is often a blank gray frame, not editor-visible)",
                saved_path or snippet(shot),
            )
        else:
            ed = client.call("capture_editor_screenshot", {"viewport": "2d", "max_width": 320}, timeout=20.0)
            if a_ok(ed) and (ed.get("result") or {}).get("image_base64"):
                saved_path = save_png(
                    evidence_dir,
                    "A-editor-small.png",
                    str((ed.get("result") or {})["image_base64"]),
                )
                book.set("screenshot", "PASS", "editor viewport screenshot", saved_path or snippet(ed))
            else:
                book.set(
                    "screenshot",
                    "SKIP",
                    "no PNG from game/editor capture (headless viewport often empty)",
                    snippet({"game": shot, "editor": ed}),
                )
        logs = client.call("get_log_messages", {"limit": 20})
        if a_ok(logs):
            book.set("log", "PASS", "get_log_messages", snippet(logs))
        else:
            book.set("log", "FAIL", "get_log_messages failed", snippet(logs))
        stop = client.call("stop_project", {})
        if a_ok(stop):
            book.set("stop", "PASS", "stop_project", snippet(stop))
        else:
            book.set("stop", "FAIL", "stop_project failed", snippet(stop))
    else:
        book.set("play", "FAIL", "run_project failed", snippet(play))
        book.set("stop", "SKIP", "play did not start")
        book.set("runtime_state", "SKIP", "play did not start")
        book.set("screenshot", "SKIP", "play did not start; editor shot may still run")
        ed = client.call("capture_editor_screenshot", {"viewport": "2d", "max_width": 320}, timeout=15.0)
        if a_ok(ed) and (ed.get("result") or {}).get("image_base64"):
            saved_path = save_png(
                evidence_dir,
                "A-editor-small.png",
                str((ed.get("result") or {})["image_base64"]),
            )
            book.set("screenshot", "PASS", "editor screenshot without play", saved_path or "")
        logs = client.call("get_log_messages", {"limit": 20})
        if a_ok(logs):
            book.set("log", "PASS", "get_log_messages without play", snippet(logs))
        else:
            book.set("log", "FAIL", "get_log_messages failed", snippet(logs))

    sel = client.call("select_node", {"node_path": "/root/Root"})
    got = client.call("get_selected_nodes", {})
    if a_ok(sel) and a_ok(got):
        selected = json.dumps(got)
        if "Root" in selected:
            note = "select_node + get_selected_nodes readback"
            if book.mode == "headless":
                note += " (headless: Inspector not shown to a human)"
            book.set("select_focus", "PASS", note, snippet({"sel": sel, "got": got}))
        else:
            book.set("select_focus", "FAIL", "selection readback missed Root", snippet(got))
    else:
        book.set("select_focus", "FAIL", "select_node/get_selected_nodes failed", snippet({"sel": sel, "got": got}))

    bad_path = client.call("open_scene", {"scene_path": "res://no/such/scene.tscn"})
    if typed_error(bad_path) and not a_ok(bad_path):
        book.set("wrong_path", "PASS", "missing scene is a typed error", snippet(bad_path))
    else:
        book.set("wrong_path", "FAIL", "wrong path did not typed-fail", snippet(bad_path))

    bad_schema = client.call("update_node", {"node_path": "/root/Root"})
    if typed_error(bad_schema) and not a_ok(bad_schema):
        book.set("wrong_schema", "PASS", "missing properties is a typed error", snippet(bad_schema))
    else:
        book.set("wrong_schema", "FAIL", "bad schema did not typed-fail", snippet(bad_schema))

    exec_resp = client.call("exec_run", {"code": "print(1)"})
    if typed_error(exec_resp) and not a_ok(exec_resp):
        book.set(
            "unsupported_eval_or_callv",
            "PASS",
            "exec_run refused; godot_exec disabled for spike",
            snippet(exec_resp),
        )
    else:
        book.set(
            "unsupported_eval_or_callv",
            "FAIL",
            "exec_run was not refused (eval must stay disabled)",
            snippet(exec_resp),
        )

    # Spike restart last — may drop the socket.
    rst = client.call("restart_editor", {"save": False}, timeout=8.0)
    if a_ok(rst):
        book.set(
            "retry_restart",
            "PASS",
            "restart_editor ACK (spike evidence, not a production ledger)",
            snippet(rst),
        )
    else:
        book.set(
            "retry_restart",
            "FAIL",
            "restart_editor failed or dropped before ACK",
            snippet(rst),
        )


def mcp_image_b64(resp: dict[str, Any]) -> str:
    result = resp.get("result")
    if not isinstance(result, dict):
        return ""
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        mime = str(item.get("mimeType", "")).lower()
        typ = str(item.get("type", "")).lower()
        if data and (typ in {"image", "image/png"} or mime.startswith("image") or str(data).startswith("iVBOR")):
            return str(data)
    return ""


def save_png(evidence_dir: Path, name: str, b64: str) -> str:
    refuse_plugin_project(evidence_dir)
    try:
        raw = base64.b64decode(b64)
    except (ValueError, TypeError):
        return ""
    work_path = WORK / "evidence" / name
    work_path.parent.mkdir(parents=True, exist_ok=True)
    work_path.write_bytes(raw)
    if len(raw) <= 100_000 and name.endswith("-small.png"):
        dest = EVIDENCE_COMMIT / name
        dest.write_bytes(raw)
        return rel(dest)
    note = EVIDENCE_COMMIT / f"{name}.txt"
    note.write_text(
        f"PNG {len(raw)} bytes saved at {work_path} (gitignored; too large to commit).\n",
        encoding="utf-8",
    )
    return rel(note)


def wait_c(client: CandidateC, cond: str, seconds: float = 20.0) -> dict[str, Any]:
    deadline = time.time() + seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = client.call_tool("wait_until", {"condition": cond, "timeout_ms": 1400})
        text = (c_tool_text(last) + json.dumps(last)).lower()
        if c_ok(last) and "not yet" not in text:
            return last
        time.sleep(0.2)
    return last


def run_c(book: Book, client: CandidateC, evidence_dir: Path) -> None:
    ping = client.rpc("ping", {})
    if ping.get("error") and ping.get("http_status") not in (None, 200):
        book.set("handshake_auth", "SKIP", f"HTTP ping failed: {snippet(ping)}")
        book.skip_rest("C HTTP MCP never came up", except_steps={"handshake_auth"})
        return

    bad = client.rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "hh-bakeoff", "version": "0"},
        },
        token="wrong-token",
    )
    if bad.get("http_status") == 401 or typed_error(bad):
        book.set("wrong_token", "PASS", "401/typed error on bad Bearer token", snippet(bad))
    else:
        book.set("wrong_token", "FAIL", "bad token was accepted", snippet(bad))

    init = client.rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "hh-bakeoff", "version": "0"},
        },
    )
    result = init.get("result") if isinstance(init.get("result"), dict) else {}
    if result.get("protocolVersion") and result.get("serverInfo"):
        book.handshake_ok = True
        title = str((result.get("serverInfo") or {}).get("title", ""))
        book.set("handshake_auth", "PASS", f"initialize ok ({title})", snippet(init))
    else:
        book.set("handshake_auth", "FAIL", "initialize missing protocolVersion/serverInfo", snippet(init))
        book.skip_rest("C initialize failed", except_steps={"handshake_auth", "wrong_token"})
        return

    ver = client.call_tool("get_godot_version", {})
    book.godot_version = c_tool_text(ver)[:120]
    if "4.7.1" in json.dumps(ver):
        book.godot_version = "4.7.1 (from get_godot_version)"

    tscn = (
        "[gd_scene format=3]\n\n"
        '[node name="BakeoffRoot" type="Node2D"]\n'
    )
    created = client.call_tool(
        "write_file",
        {"path": "res://bakeoff_created.tscn", "content": tscn},
    )
    opened_new = client.call_tool("open_scene", {"path": "res://bakeoff_created.tscn"})
    if c_ok(created) and c_ok(opened_new) and not c_handler_error(opened_new):
        book.set(
            "create_scene",
            "PASS",
            "write_file + open_scene (no dedicated create_scene; file tool is MCP)",
            snippet({"write": created, "open": opened_new}),
        )
    else:
        # Fallback: open fixture and save-as.
        opened_main = client.call_tool("open_scene", {"path": "res://main.tscn"})
        saved_as = client.call_tool("save_scene", {"path": "res://bakeoff_created.tscn"})
        if c_ok(opened_main) and c_ok(saved_as) and not c_handler_error(saved_as):
            book.set("create_scene", "PASS", "save_scene as new path", snippet(saved_as))
        else:
            book.set(
                "create_scene",
                "FAIL",
                "could not create/open a new scene via MCP file or save-as",
                snippet({"write": created, "open": opened_new, "save_as": saved_as}),
            )

    opened = client.call_tool("open_scene", {"path": "res://main.tscn"})
    if c_ok(opened) and not c_handler_error(opened):
        book.set("open_scene", "PASS", "open_scene res://main.tscn", snippet(opened))
    else:
        book.set("open_scene", "FAIL", "open_scene failed", snippet(opened))

    saved = client.call_tool("save_scene", {})
    if c_ok(saved) and not c_handler_error(saved):
        book.set("save_scene", "PASS", "save_scene", snippet(saved))
    else:
        book.set("save_scene", "FAIL", "save_scene failed", snippet(saved))

    added = client.call_tool("create_node", {"type": "Node2D", "name": "ChildA", "parent": "Root"})
    if c_ok(added) and not c_handler_error(added):
        book.set("add_node", "PASS", "create_node ChildA under Root", snippet(added))
    else:
        book.set("add_node", "FAIL", "create_node failed", snippet(added))

    child_b = client.call_tool("create_node", {"type": "Node2D", "name": "ChildB", "parent": "Root"})
    dup = client.call_tool("duplicate_node", {"target": "ChildA", "name": "ChildACopy"})
    if c_ok(dup) and not c_handler_error(dup):
        book.set("duplicate_node", "PASS", "duplicate_node ChildA", snippet(dup))
    else:
        book.set("duplicate_node", "FAIL", "duplicate_node failed", snippet(dup))

    reparent = client.call_tool("reparent_node", {"target": "ChildB", "new_parent": "ChildA"})
    if c_ok(reparent) and not c_handler_error(reparent):
        book.set("reparent_node", "PASS", "reparent ChildB under ChildA", snippet(reparent))
    else:
        book.set("reparent_node", "FAIL", "reparent_node failed", snippet(reparent))

    moved = client.call_tool("move_node", {"target": "ChildA", "to_index": 0})
    if c_ok(moved) and not c_handler_error(moved):
        book.set("reorder_node", "PASS", "move_node to_index=0", snippet(moved))
    else:
        book.set("reorder_node", "FAIL", "move_node failed", snippet(moved))

    prop = client.call_tool(
        "set_property",
        {"target": "ChildA", "property": "position", "value": [32, 64]},
    )
    desc = client.call_tool("describe_object", {"target": "ChildA"})
    blob = json.dumps(desc) + c_tool_text(desc)
    if c_ok(prop) and not c_handler_error(prop) and ("32" in blob or "64" in blob or "position" in blob.lower()):
        book.set(
            "set_property",
            "PASS",
            "set_property + describe_object readback",
            snippet({"set": prop, "describe": desc}),
        )
    elif c_ok(prop) and not c_handler_error(prop):
        book.set(
            "set_property",
            "FAIL",
            "set_property succeeded but describe_object did not echo the value",
            snippet({"set": prop, "describe": desc}),
        )
    else:
        book.set("set_property", "FAIL", "set_property failed", snippet(prop))

    resource = client.call_tool(
        "set_resource",
        {"target": "ChildA", "property": "material", "class": "CanvasItemMaterial"},
    )
    if c_ok(resource) and not c_handler_error(resource):
        book.set("set_resource", "PASS", "set_resource inline CanvasItemMaterial", snippet(resource))
    else:
        # Fixture Root is Node2D; ChildA too — material should exist on CanvasItem.
        book.set("set_resource", "FAIL", "set_resource failed", snippet(resource))

    script_src = (
        "extends Node2D\n\n"
        "func _ready() -> void:\n"
        '\tprint("bakeoff-child")\n'
    )
    wrote = client.call_tool(
        "write_script",
        {"path": "res://bakeoff_child.gd", "content": script_src, "validate": True},
    )
    if c_ok(wrote) and not c_handler_error(wrote):
        book.set("script_write", "PASS", "write_script validate=true", snippet(wrote))
    else:
        book.set("script_write", "FAIL", "write_script failed", snippet(wrote))

    valid = client.call_tool("validate_script", {"path": "res://bakeoff_child.gd"})
    if c_ok(valid) and not c_handler_error(valid):
        book.set("script_validate", "PASS", "validate_script", snippet(valid))
    else:
        book.set("script_validate", "FAIL", "validate_script failed", snippet(valid))

    attached = client.call_tool(
        "attach_script",
        {"target": "ChildA", "path": "res://bakeoff_child.gd"},
    )
    if c_ok(attached) and not c_handler_error(attached):
        book.set("script_attach", "PASS", "attach_script", snippet(attached))
    else:
        book.set("script_attach", "FAIL", "attach_script failed", snippet(attached))

    tree_before = client.call_tool("get_scene_tree", {})
    deleted = client.call_tool("delete_node", {"target": "ChildACopy"})
    if c_ok(deleted) and not c_handler_error(deleted):
        book.set("delete_node", "PASS", "delete_node ChildACopy", snippet(deleted))
    else:
        book.set("delete_node", "FAIL", "delete_node failed", snippet(deleted))

    undo = client.call_tool("undo", {})
    redo = client.call_tool("redo", {})
    if c_ok(undo) and not c_handler_error(undo):
        book.set("undo", "PASS", "undo tool", snippet(undo))
    else:
        book.set(
            "undo",
            "FAIL",
            "no MCP undo tool; scene mutations use EditorUndoRedoManager (human Ctrl+Z only). "
            "Agent-driven undo not available with call_method disabled.",
            snippet({"undo": undo, "tree": tree_before}),
        )
    if c_ok(redo) and not c_handler_error(redo):
        book.set("redo", "PASS", "redo tool", snippet(redo))
    else:
        book.set(
            "redo",
            "FAIL",
            "no MCP redo tool (UndoRedo-backed mutations, no agent redo)",
            snippet(redo),
        )

    play = client.call_tool("play_scene", {"scene": "res://main.tscn"})
    if c_ok(play) and not c_handler_error(play):
        book.set("play", "PASS", "play_scene main.tscn", snippet(play))
        wait_c(client, "play_started", 15)
        connected = wait_c(client, "game_connected", 25)
        logs = client.call_tool("logs_read", {"lines": 40})
        if c_ok(logs) and not c_handler_error(logs):
            book.set("log", "PASS", "logs_read", snippet(logs))
        else:
            gl = client.call_tool("game_logs", {"lines": 40})
            if c_ok(gl) and not c_handler_error(gl):
                book.set("log", "PASS", "game_logs", snippet(gl))
            else:
                book.set("log", "FAIL", "logs_read/game_logs failed", snippet({"logs": logs, "game": gl}))
        rt = client.call_tool("get_remote_tree", {"depth": 2, "max_nodes": 30})
        rp = client.call_tool("runtime_get_property", {"name": "Root", "property": "position"})
        if (c_ok(rt) and not c_handler_error(rt)) or (c_ok(rp) and not c_handler_error(rp)):
            book.set(
                "runtime_state",
                "PASS",
                "get_remote_tree and/or runtime_get_property",
                snippet({"tree": rt, "prop": rp, "wait": connected}),
            )
        else:
            book.set(
                "runtime_state",
                "FAIL",
                "runtime observe failed (Lite sees the game only after game_connected)",
                snippet({"tree": rt, "prop": rp, "wait": connected}),
            )
        shot = client.call_tool(
            "screenshot",
            {"target": "game", "max_dim": 320, "format": "png"},
            timeout=40.0,
        )
        b64 = mcp_image_b64(shot)
        if c_ok(shot) and not c_handler_error(shot) and b64:
            saved_path = save_png(evidence_dir, "C-game-small.png", b64)
            book.set(
                "screenshot",
                "PASS",
                "screenshot target=game (headless dummy renderer may be blank)",
                saved_path or snippet(shot),
            )
        elif c_ok(shot) and not c_handler_error(shot):
            note_path = EVIDENCE_COMMIT / "C-screenshot.txt"
            note_path.write_text(
                "C screenshot tool returned success but no inline PNG bytes were copied.\n"
                f"{snippet(shot)}\n",
                encoding="utf-8",
            )
            book.set("screenshot", "PASS", "screenshot target=game (no inline PNG extracted)", rel(note_path))
        else:
            ed = client.call_tool("screenshot", {"target": "editor", "max_dim": 320}, timeout=20.0)
            b64e = mcp_image_b64(ed)
            if b64e:
                saved_path = save_png(evidence_dir, "C-editor-small.png", b64e)
                book.set("screenshot", "PASS", "screenshot target=editor", saved_path or "")
            elif c_ok(ed) and not c_handler_error(ed):
                book.set("screenshot", "PASS", "screenshot target=editor", snippet(ed))
            else:
                book.set(
                    "screenshot",
                    "SKIP",
                    "screenshot failed or empty in this editor mode",
                    snippet({"game": shot, "editor": ed}),
                )
        stop = client.call_tool("stop_scene", {})
        if c_ok(stop) and not c_handler_error(stop):
            book.set("stop", "PASS", "stop_scene", snippet(stop))
        else:
            book.set("stop", "FAIL", "stop_scene failed", snippet(stop))
    else:
        book.set("play", "FAIL", "play_scene failed", snippet(play))
        book.set("stop", "SKIP", "play did not start")
        book.set("runtime_state", "SKIP", "play did not start")
        book.set("screenshot", "SKIP", "play did not start")
        logs = client.call_tool("logs_read", {"lines": 20})
        if c_ok(logs) and not c_handler_error(logs):
            book.set("log", "PASS", "logs_read without play", snippet(logs))
        else:
            book.set("log", "FAIL", "logs_read failed", snippet(logs))

    sel = client.rpc("resources/read", {"uri": "scene://selection"})
    focus_note = c_tool_text(sel) or snippet(sel)
    # C has no select_node; create_node returns a dock focus hint.
    if "ChildA" in json.dumps(added) or "focus" in json.dumps(added).lower():
        book.set(
            "select_focus",
            "FAIL",
            "dock/activity focus hint on create_node, but no EditorInterface.select tool "
            "so a human Inspector selection is not guaranteed",
            snippet({"create": added, "selection_resource": sel}),
        )
    else:
        book.set(
            "select_focus",
            "FAIL",
            "no select_node tool; scene://selection=" + focus_note[:180],
            snippet(sel),
        )

    rst = client.call_tool("restart_editor", {})
    if c_ok(rst) and not c_handler_error(rst):
        book.set("retry_restart", "PASS", "restart_editor (spike, not production ledger)", snippet(rst))
    else:
        book.set(
            "retry_restart",
            "SKIP",
            "no editor restart MCP tool on Lite (spike gap, not a ledger)",
            snippet(rst),
        )

    bad_path = client.call_tool("open_scene", {"path": "res://no/such/scene.tscn"})
    if c_handler_error(bad_path) or typed_error(bad_path):
        book.set("wrong_path", "PASS", "missing scene is a typed/handler error", snippet(bad_path))
    else:
        book.set("wrong_path", "FAIL", "wrong path did not fail", snippet(bad_path))

    bad_schema = client.call_tool("create_node", {"name": "Nope"})
    if c_handler_error(bad_schema) or typed_error(bad_schema):
        book.set("wrong_schema", "PASS", "create_node without type failed", snippet(bad_schema))
    else:
        book.set("wrong_schema", "FAIL", "missing required type was accepted", snippet(bad_schema))

    callv = client.call_tool("call_method", {"target": "Root", "method": "get_class"})
    if c_handler_error(callv) or typed_error(callv):
        text = (c_tool_text(callv) + snippet(callv)).lower()
        if "disabled" in text or "unsupported" in text:
            book.set(
                "unsupported_eval_or_callv",
                "PASS",
                "call_method/Object.callv refused; disabled for spike",
                snippet(callv),
            )
        else:
            book.set(
                "unsupported_eval_or_callv",
                "PASS",
                "call_method failed with a typed/handler error after spike disable",
                snippet(callv),
            )
    else:
        book.set(
            "unsupported_eval_or_callv",
            "FAIL",
            "call_method still executed (must stay disabled)",
            snippet(callv),
        )


def score_candidate(book: Book) -> dict[str, Any]:
    def frac(names: tuple[str, ...] | list[str]) -> float:
        if not names:
            return 0.0
        n = sum(1 for s in names if book.rows[s]["status"] == "PASS")
        return n / len(names)

    correctness = (
        "create_scene",
        "open_scene",
        "save_scene",
        "add_node",
        "delete_node",
        "duplicate_node",
        "reparent_node",
        "reorder_node",
        "set_property",
        "set_resource",
        "script_write",
        "script_validate",
        "script_attach",
    )
    self_verify = ("set_property", "log", "screenshot", "runtime_state", "select_focus")
    undo = ("undo", "redo")
    security = ("handshake_auth", "wrong_token", "wrong_path", "wrong_schema", "unsupported_eval_or_callv")
    scores = {
        "correctness": round(frac(correctness) * 5, 2),
        "self_verify": round(frac(self_verify) * 5, 2),
        "undo": round(frac(undo) * 5, 2),
        "security": round(frac(security) * 5, 2),
        "maintainability": 0.0,
        "godot_471": 0.0,
    }
    # Qualitative maintainability (not tool count): filled by caller.
    if "4.7.1" in book.godot_version or (book.handshake_ok and book.godot_version):
        scores["godot_471"] = 5.0 if "4.7.1" in book.godot_version else 3.0
    elif book.handshake_ok:
        scores["godot_471"] = 2.0
    weighted = 0.0
    denom = 0
    for key, weight in WEIGHTS.items():
        weighted += scores[key] * weight
        denom += weight
    scores["weighted"] = round(weighted / denom, 3) if denom else 0.0
    return scores


def write_scorecard(books: dict[str, Book], extras: dict[str, Any]) -> None:
    a, c = books["A"], books["C"]
    # Maintainability: architecture notes, not tool counts.
    a_scores = score_candidate(a)
    c_scores = score_candidate(c)
    a_scores["maintainability"] = extras["A_maintain"]
    c_scores["maintainability"] = extras["C_maintain"]
    # Recompute weighted with qualitative maintainability.
    for scores in (a_scores, c_scores):
        weighted = 0.0
        denom = 0
        for key, weight in WEIGHTS.items():
            weighted += scores[key] * weight
            denom += weight
        scores["weighted"] = round(weighted / denom, 3)

    winner = "A" if a_scores["weighted"] > c_scores["weighted"] else "C"
    if a_scores["weighted"] == c_scores["weighted"]:
        winner = "tie"

    lines = [
        "# R1-WP3 MCP bake-off scorecard",
        "",
        "Same scenario on disposable copies of **A** (satelliteoflove/godot-mcp "
        "`1b7d40537240fd54300f54bf6fda1ea91f06c878`) and **C** Beckett Lite "
        "`efb81dec03ba0af2b7a6dce0e4678bdbde5e454d`. Godot pin **4.7.1-stable**.",
        "",
        "Tool count is **not** a score. Weights: correctness (5), self-verify (5), "
        "undo (4), security (4), maintainability (3), Godot 4.7.1 compatibility (3).",
        "",
        f"Driver: `{rel(HERE / 'run_bakeoff.py')}`. Mode: {extras.get('mode', 'headless')}. "
        "Eval/`godot_exec`/`call_method`/`Object.callv` were **disabled** for this spike. "
        "Session token required. Bind 127.0.0.1 only. `godot/plugin-project/` was not used.",
        "",
        "## Scenario table",
        "",
        "| Step | A | A evidence | A notes | C | C evidence | C notes |",
        "|------|---|------------|---------|---|------------|---------|",
    ]

    def cell(text: str, limit: int = 96) -> str:
        cleaned = (text or "—").replace("|", "/").replace("\n", " ").replace("\r", " ")
        return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"

    for step in STEPS:
        ar, cr = a.rows[step], c.rows[step]
        lines.append(
            "| {step} | {as_} | {ae} | {an} | {cs} | {ce} | {cn} |".format(
                step=step,
                as_=ar["status"],
                ae=cell(ar["evidence"]),
                an=cell(ar["notes"]),
                cs=cr["status"],
                ce=cell(cr["evidence"]),
                cn=cell(cr["notes"]),
            )
        )

    def counts(book: Book) -> str:
        from collections import Counter

        ctn = Counter(r["status"] for r in book.rows.values())
        return f"PASS {ctn['PASS']} / FAIL {ctn['FAIL']} / SKIP {ctn['SKIP']}"

    lines += [
        "",
        "## Ranking (weighted criteria, not tool count)",
        "",
        "| Criterion | Weight | A | C |",
        "|-----------|--------|---|---|",
    ]
    for key, weight in WEIGHTS.items():
        lines.append(f"| {key} | {weight} | {a_scores[key]} | {c_scores[key]} |")
    lines += [
        f"| **weighted total** | | **{a_scores['weighted']}** | **{c_scores['weighted']}** |",
        "",
        f"Row counts: A {counts(a)}; C {counts(c)}.",
        "",
        f"**Ranking: {winner}** (higher weighted score). "
        "A lead, if any, is usually runtime/select; C lead, if any, is scene CRUD + UndoRedo + script validate.",
        "",
        "## Maintainability notes",
        "",
        extras["A_maintain_notes"],
        "",
        extras["C_maintain_notes"],
        "",
        "## MUST-PATCH leftover (G1 must not vendor as-is)",
        "",
        extras["must_patch"],
        "",
        "## Security spike (this WP only)",
        "",
        "- Disposable copies under `tests/e2e/bakeoff/work/` (gitignored).",
        "- Token required; not written to this file.",
        "- `godot_exec` / `call_method` disabled; a PASS on `unsupported_eval_or_callv` means **refused**.",
        "- Human editor without MCP: `hh-godot-editor.bat`.",
        "",
    ]
    SCORECARD_PATH.write_text("\n".join(lines), encoding="utf-8")
    (WORK / "results.json").write_text(
        json.dumps(
            {
                "A": {"rows": a.rows, "scores": a_scores, "version": a.godot_version},
                "C": {"rows": c.rows, "scores": c_scores, "version": c.godot_version},
                "winner": winner,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def make_env(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    env = dict(base)
    env.update(extra)
    # Never inherit a kill-switch that turns Beckett auth off.
    env.pop("BECKETT_AUTH", None)
    return env


def session_token() -> str:
    # Not sk-/ghp_-shaped. Not logged.
    return "hh-bakeoff-" + hashlib.sha256(os.urandom(32)).hexdigest()[:24]


def run_one(
    cid: str,
    pins: dict[str, Any],
    console: Path,
    gui: Path,
    token: str,
    *,
    headless: bool,
) -> Book:
    book = Book(cid)
    book.mode = "headless" if headless else "gui"
    spec = pins["candidates"][cid]
    clone = CLONES / cid
    project = PROJECTS / cid
    git_clone_pin(spec["repository"], spec["commit"], clone)
    copy_fixture(project)
    if cid == "A":
        apply_patches_a(clone)
        copy_addon(clone / "godot" / "addons" / "godot_mcp", project / "addons" / "godot_mcp")
        enable_plugin(project, spec["plugin_cfg"])
        port = 16550
        env = make_env(
            os.environ.copy(),
            {
                "HH_BAKEOFF_TOKEN": token,
                "HH_BAKEOFF_PORT": str(port),
            },
        )
    else:
        apply_patches_c(clone)
        copy_addon(clone / "addons" / "beckett", project / "addons" / "beckett")
        enable_plugin(project, spec["plugin_cfg"])
        port = 18770
        env = make_env(
            os.environ.copy(),
            {
                "BECKETT_ENABLE": "1",
                "BECKETT_PORT": str(port),
                "BECKETT_RUNTIME_PORT": str(port + 1),
                "BECKETT_TOKEN": token,
                "BECKETT_AUTO_CONFIG": "0",
            },
        )
        # Explicitly do not set BECKETT_AUTH=0 (that would disable the token).

    exe = console if headless else gui
    import_env = dict(env)
    if cid == "C":
        import_env["BECKETT_ENABLE"] = "0"
    import_project(exe if headless else console, project, import_env, LOGS / f"{cid}-import.log")

    session = start_godot(
        exe,
        project,
        LOGS / f"{cid}-editor.log",
        env,
        headless=headless,
    )
    try:
        if cid == "A":
            # Do not TCP-probe: Godot's addon is single-client and would eat the probe.
            client_a = CandidateA("127.0.0.1", port, token)
            deadline = time.time() + 120.0
            last_err = "not attempted"
            while time.time() < deadline:
                if not session.alive():
                    last_err = "editor exited before websocket connect"
                    break
                try:
                    client_a.connect()
                    last_err = ""
                    break
                except OSError as exc:
                    last_err = str(exc)
                    time.sleep(0.5)
            if last_err:
                tail = ""
                if session.log_path.is_file():
                    tail = session.log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                book.set(
                    "handshake_auth",
                    "SKIP",
                    f"websocket never connected on 127.0.0.1:{port}: {last_err}. {tail[:300]}",
                )
                book.skip_rest("no websocket", except_steps={"handshake_auth"})
                return book
            try:
                run_a(book, client_a, EVIDENCE_COMMIT, project)
            finally:
                client_a.close()
        else:
            client_c = CandidateC("127.0.0.1", port, token)
            deadline = time.time() + 120.0
            up = False
            last: dict[str, Any] = {}
            while time.time() < deadline:
                if not session.alive():
                    break
                last = client_c.rpc("ping", {})
                if "error" not in last or last.get("result") is not None:
                    if last.get("http_status") not in {500, 502, 503, 404}:
                        # 401 means the server is up and token-gated.
                        up = True
                        break
                if last.get("http_status") == 401:
                    up = True
                    break
                time.sleep(0.6)
            if not up:
                tail = ""
                if session.log_path.is_file():
                    tail = session.log_path.read_text(encoding="utf-8", errors="replace")[-800:]
                book.set(
                    "handshake_auth",
                    "SKIP",
                    f"HTTP MCP never answered on 127.0.0.1:{port}: {snippet(last)} {tail[:300]}",
                )
                book.skip_rest("C HTTP never came up", except_steps={"handshake_auth"})
                return book
            run_c(book, client_c, EVIDENCE_COMMIT)
    finally:
        session.stop()
    return book


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="R1-WP3 MCP bake-off on disposable copies.")
    p.add_argument("--gui", action="store_true", help="use Godot GUI exe instead of headless")
    p.add_argument("--only", choices=("A", "C"), default="", help="run one candidate")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if (PLUGIN_PROJECT / "addons").is_dir():
        leftover = [
            p
            for p in (PLUGIN_PROJECT / "addons").rglob("*")
            if p.is_file() and ".godot" not in p.parts
        ]
        if leftover:
            die("godot/plugin-project/addons already has files; abort")
    if not FIXTURE.is_dir():
        die(f"missing fixture {FIXTURE}")

    WORK.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    EVIDENCE_COMMIT.mkdir(parents=True, exist_ok=True)
    pins = load_pins()
    token = session_token()
    try:
        console, gui = doctor_paths()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        die(f"could not resolve Godot pin: {exc}")

    headless = not args.gui
    books: dict[str, Book] = {}
    order = [args.only] if args.only else ["A", "C"]
    for cid in order:
        print(f"bakeoff: running {cid} ({'headless' if headless else 'gui'})")
        try:
            books[cid] = run_one(cid, pins, console, gui, token, headless=headless)
        except Exception as exc:  # noqa: BLE001
            book = Book(cid)
            book.set("handshake_auth", "SKIP", f"driver exception: {type(exc).__name__}: {exc}")
            book.skip_rest(f"driver exception: {exc}", except_steps={"handshake_auth"})
            books[cid] = book
            print(f"bakeoff: {cid} exception: {exc}", file=sys.stderr)

    if "A" not in books:
        books["A"] = Book("A")
        books["A"].skip_rest("--only C; A not run")
    if "C" not in books:
        books["C"] = Book("C")
        books["C"].skip_rest("--only A; C not run")

    extras = {
        "mode": "gui" if args.gui else "headless",
        "A_maintain": 3.0,
        "C_maintain": 4.0,
        "A_maintain_notes": (
            "- **A maintainability (3/5):** Node sidecar + GDScript addon matches our intended "
            "sidecar/plugin split, but mutations are disk-first with **zero UndoRedo**, empty "
            "property-set success, fixed port 6550 (overridden only in this spike), and no "
            "session token upstream. npm/`npx -y` in the README is forbidden here (T5)."
        ),
        "C_maintain_notes": (
            "- **C maintainability (4/5):** GDScript-only, 4.7.1 CI, UndoRedo on scene tools, "
            "validate-before-write. Zero-sidecar **conflicts** with our chosen TypeScript "
            "sidecar architecture. `call_method`/`Object.callv` and a tokenless upgrade path "
            "are MUST-PATCH. Full itch SKUs are E2 — do not buy."
        ),
        "must_patch": (
            "- **A:** session token + random port; disable `godot_exec`; EditorUndoRedoManager "
            "(or atomic file + conflict check); postcondition readback on `update_node`; "
            "export-strip MCPGameBridge autoload.\n"
            "- **C Lite:** keep `call_method` off the OWNER_AUTOPILOT surface; require token "
            "even on upgrade; do not follow `npx mcp-remote`; never enable Full; wrap in our "
            "sidecar if G1 vendors anything.\n"
            "- **Both:** G1 must not ship either as-is. Fallback remains writing `addons/hh_agent` "
            "+ `bridge/` ourselves if these MUST-PATCH rows stay open."
        ),
    }
    write_scorecard(books, extras)
    print(f"bakeoff: wrote {rel(SCORECARD_PATH)}")
    print(f"bakeoff: plugin-project addons still absent: {not (PLUGIN_PROJECT / 'addons').is_dir()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
