#!/usr/bin/env python3
"""R2-WP2: sidecar session transport + stdio MCP.

Executes (does not merely comment) 100 reconnects against a live sidecar.
Stdlib only + the pinned bridge Node/tsc toolchain.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import re
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
PROTOCOL = "hh-godot-agent/1"
FORBIDDEN_SRC_PORTS = ("6550", "6008", "8770") + tuple(str(p) for p in range(6505, 6515))
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "dist",
    "__pycache__",
    ".godot",
    "target",
    "third_party",
    "experiments",
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def redact(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def plan_errors(text: str) -> list[str]:
    """Allow pre-tick (implementer) or post-tick (coordinator) plan state."""
    errors: list[str] = []
    current = ""
    wp2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP2\b", stripped):
            wp2 = stripped
    if wp2 is None:
        return ["plan missing R2-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R2-WP2 heading must keep [ ] until coordinator tick")
        if current != "R2-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP2 while WP2 is unticked)")
    elif not re.match(r"^R2-WP[3-9]$|^R2-WP\d{2,}$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP3+ after R2-WP2 tick)")
    return errors


def _readn(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("socket closed")
        buf += chunk
    return buf


def ws_connect(
    host: str, port: int, timeout: float = 3.0, origin: str | None = None
) -> socket.socket:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    extra = f"Origin: {origin}\r\n" if origin else ""
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"{extra}"
        f"\r\n"
    )
    sock.sendall(req.encode("ascii"))
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            sock.close()
            raise OSError("no websocket upgrade")
        data += chunk
    if b"101" not in data.split(b"\r\n", 1)[0]:
        sock.close()
        raise OSError("websocket upgrade refused")
    extra = data.split(b"\r\n\r\n", 1)[1]
    if extra:
        # leftover frames after the HTTP head (rare)
        sock = _PrefixedSocket(sock, extra)
    return sock


def ws_upgrade_status(
    host: str, port: int, timeout: float = 3.0, origin: str | None = None
) -> str:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    extra = f"Origin: {origin}\r\n" if origin else ""
    req = (
        f"GET / HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"{extra}"
        f"\r\n"
    )
    sock.sendall(req.encode("ascii"))
    data = b""
    try:
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()
    if not data:
        return ""
    return data.split(b"\r\n", 1)[0].decode("ascii", "replace")


class _PrefixedSocket:
    def __init__(self, sock: socket.socket, prefix: bytes) -> None:
        self._sock = sock
        self._prefix = prefix

    def recv(self, n: int) -> bytes:
        if self._prefix:
            out = self._prefix[:n]
            self._prefix = self._prefix[n:]
            return out
        return self._sock.recv(n)

    def sendall(self, data: bytes) -> None:
        self._sock.sendall(data)

    def close(self) -> None:
        self._sock.close()

    def settimeout(self, t: float) -> None:
        self._sock.settimeout(t)


def ws_send_text(sock: socket.socket | _PrefixedSocket, text: str) -> None:
    payload = text.encode("utf-8")
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytearray()
    header.append(0x81)
    ln = len(payload)
    if ln < 126:
        header.append(0x80 | ln)
    elif ln < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", ln))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", ln))
    sock.sendall(bytes(header) + mask + masked)


def ws_recv_text(sock: socket.socket | _PrefixedSocket) -> str:
    while True:
        hdr = _readn(sock, 2)
        opcode = hdr[0] & 0x0F
        masked = (hdr[1] & 0x80) != 0
        ln = hdr[1] & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", _readn(sock, 2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", _readn(sock, 8))[0]
        mask = _readn(sock, 4) if masked else b""
        data = _readn(sock, ln)
        if masked:
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        if opcode == 0x8:
            raise OSError("websocket closed")
        if opcode == 0x9:
            # ignore ping
            continue
        if opcode == 0xA:
            continue
        if opcode == 0x1:
            return data.decode("utf-8")


def hello_payload(project_id: str, secret: str, protocol: str = PROTOCOL) -> dict[str, str]:
    return {
        "type": "hello",
        "protocol": protocol,
        "project_id": project_id,
        "token": secret,
    }


def ws_hello(host: str, port: int, body: dict[str, str]) -> dict:
    sock = ws_connect(host, port)
    try:
        ws_send_text(sock, json.dumps(body))
        return json.loads(ws_recv_text(sock))
    finally:
        sock.close()


def find_descriptor(pid: int, timeout: float = 12.0) -> tuple[Path, dict]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is required")
    root = Path(local) / "HHGodotAgent" / "sessions"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if root.is_dir():
            for path in root.glob("*/session.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if int(data.get("pid") or 0) == pid:
                    return path, data
        time.sleep(0.05)
    raise RuntimeError("session descriptor not found")


def drain_stderr(proc: subprocess.Popen[str], bucket: list[str]) -> None:
    if proc.stderr is None:
        return
    for line in proc.stderr:
        bucket.append(line)


def readline_timeout(stream, timeout: float) -> str:
    q: queue.Queue[str] = queue.Queue()

    def reader() -> None:
        q.put(stream.readline())

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("stdio MCP read timed out")
    return q.get()


def run_harness(cmd: list[str]) -> dict:
    proc = subprocess.run(
        [node(), str(BRIDGE / "dist" / "session" / "harness.js"), *cmd],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    out = (proc.stdout or "").strip().splitlines()
    payload = {}
    for line in out:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {}
    if proc.returncode != 0 and not payload.get("ok"):
        raise RuntimeError(f"harness {cmd} failed: {proc.stdout} {proc.stderr}")
    return payload


def grep_token(root: Path, secret: str) -> list[str]:
    hits: list[str] = []
    if not secret or not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            blob = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in blob[:4096]:
            continue
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if secret in text:
            hits.append(str(path))
    return hits


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    src = BRIDGE / "src"
    for path in src.rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        posix = rel(path)
        for port in FORBIDDEN_SRC_PORTS:
            if port in text:
                errors.append(f"{posix} contains forbidden port {port}")
        if re.search(r"shell\s*:\s*true", text):
            errors.append(f"{posix} uses shell:true")
        if re.search(r"""from ["']node:child_process["'][\s\S]*\bexec\b""", text):
            errors.append(f"{posix} imports child_process exec")
        if re.search(r"""\b(?:execSync|execFile)\s*\(""", text):
            errors.append(f"{posix} uses execSync/execFile")
        if "Math.random" in text:
            errors.append(f"{posix} uses Math.random")
        if "randomUUID" in text:
            errors.append(f"{posix} uses randomUUID")
        if "-Command" in text:
            errors.append(f"{posix} uses powershell -Command")
        for needle in (
            "satelliteoflove",
            "MCPGameBridge",
            "godot_mcp",
            "call_method",
            "Object.callv",
            "evaluate_expression",
        ):
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
    return errors


def main() -> int:
    errors: list[str] = []

    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    errors.extend(src_scan_errors())

    built = subprocess.run(
        [npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: session transport", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    try:
        bind_ok = run_harness(["bind-ok"])
        if not bind_ok.get("ok") or bind_ok.get("host") != "127.0.0.1":
            errors.append(f"bind-ok failed: {bind_ok}")
        reject_any = run_harness(["bind-reject", "0.0.0.0"])
        if not reject_any.get("ok") or reject_any.get("code") != "E_BIND":
            errors.append(f"0.0.0.0 must reject with E_BIND: {reject_any}")
        reject_v6 = run_harness(["bind-reject", "::"])
        if not reject_v6.get("ok") or reject_v6.get("code") != "E_BIND":
            errors.append(f":: must reject with E_BIND: {reject_v6}")
        collision = run_harness(["collision"])
        if not collision.get("ok") or int(collision.get("attempts") or 0) < 2:
            errors.append(f"EADDRINUSE must retry listen(0): {collision}")
        token_shape = run_harness(["token"])
        if not token_shape.get("ok") or token_shape.get("bytes") != 32:
            errors.append(f"token must be 32 bytes: {token_shape}")
    except RuntimeError as exc:
        errors.append(str(exc))

    tmp = Path(tempfile.mkdtemp(prefix="hh-r2wp2-"))
    (tmp / "project.godot").write_text("; test fixture\nconfig_version=5\n", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    secret = ""
    err_lines: list[str] = []
    desc_path: Path | None = None
    try:
        proc = subprocess.Popen(
            [node(), str(BRIDGE / "dist" / "main.js"), "--project", str(tmp)],
            cwd=str(BRIDGE),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=drain_stderr, args=(proc, err_lines), daemon=True).start()
        desc_path, desc = find_descriptor(proc.pid)
        secret = str(desc.get("token") or "")
        host = str(desc.get("host") or "")
        port = int(desc.get("port") or 0)
        project_id = str(desc.get("project_id") or "")
        if host != "127.0.0.1" or port <= 0:
            errors.append("descriptor bind is not loopback OS-assigned")
        if len(secret) != 64:
            errors.append("descriptor token is not 256-bit hex")
        if not desc_path.resolve().as_posix().lower().endswith(
            f"/hhgodotagent/sessions/{project_id}/session.json".lower()
        ):
            errors.append("descriptor is not under LOCALAPPDATA/HHGodotAgent/sessions")

        bad_secret = secret[:-1] + ("0" if secret[-1:] != "0" else "1")
        bad_tok = ws_hello(host, port, hello_payload(project_id, bad_secret))
        if bad_tok.get("ok") is not False or (bad_tok.get("error") or {}).get("code") != "E_AUTH":
            errors.append(f"wrong token must be E_AUTH: {redact(json.dumps(bad_tok), secret)}")

        bad_proj = ws_hello(host, port, hello_payload("0" * 32, secret))
        if bad_proj.get("ok") is not False or (bad_proj.get("error") or {}).get("code") != "E_PROJECT_MISMATCH":
            errors.append(f"wrong project must be E_PROJECT_MISMATCH: {redact(json.dumps(bad_proj), secret)}")

        bad_proto = ws_hello(host, port, hello_payload(project_id, secret, "hh-godot-agent/2"))
        if bad_proto.get("ok") is not False or (bad_proto.get("error") or {}).get("code") != "E_PROTOCOL_VERSION":
            errors.append(f"wrong protocol must be E_PROTOCOL_VERSION: {redact(json.dumps(bad_proto), secret)}")

        evil = ws_upgrade_status(host, port, origin="https://evil.example")
        if "101" in evil:
            errors.append("Origin https://evil.example must not get 101")
        elif "403" not in evil:
            errors.append(f"Origin https://evil.example expected 403, got {evil!r}")

        good = ws_hello(host, port, hello_payload(project_id, secret))
        if good.get("ok") is not True:
            errors.append(f"good hello failed: {redact(json.dumps(good), secret)}")

        reconnects = 0
        for _ in range(100):
            again = ws_hello(host, port, hello_payload(project_id, secret))
            if again.get("ok") is not True:
                errors.append(f"reconnect failed at {reconnects}: {redact(json.dumps(again), secret)}")
                break
            reconnects += 1
        if reconnects != 100:
            errors.append(f"executed reconnects={reconnects} (need 100)")

        if proc.stdin and proc.stdout:
            init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-session", "version": "0"},
                },
            }
            proc.stdin.write(json.dumps(init) + "\n")
            proc.stdin.flush()
            init_line = readline_timeout(proc.stdout, 5.0)
            init_msg = json.loads(init_line)
            if "result" not in init_msg:
                errors.append(f"MCP initialize failed: {redact(init_line, secret)}")
            call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "godot.node",
                    "arguments": {
                        "action": "add",
                        "params": {
                            "scene": "res://main.tscn",
                            "parent": ".",
                            "class_name": "Node2D",
                            "name": "X",
                        },
                    },
                },
            }
            proc.stdin.write(json.dumps(call) + "\n")
            proc.stdin.flush()
            call_line = readline_timeout(proc.stdout, 5.0)
            call_msg = json.loads(call_line)
            body = ((call_msg.get("result") or {}).get("structuredContent")) or {}
            err = body.get("error") or {}
            if err.get("code") != "E_UNVERIFIED":
                errors.append(f"registry tool must be E_UNVERIFIED / not dispatched: {redact(call_line, secret)}")
            if call_msg.get("result", {}).get("isError") is not True:
                errors.append("live mutation must be isError")
            dumped = json.dumps(call_msg)
            if '"ok": true' in dumped or '"ok":true' in dumped:
                errors.append("mutation path returned ok true")

        doctor = subprocess.run(
            [node(), str(BRIDGE / "dist" / "main.js"), "--project", str(tmp), "--doctor"],
            cwd=BRIDGE,
            text=True,
            capture_output=True,
            check=False,
        )
        if secret and secret in (doctor.stdout or "") + (doctor.stderr or ""):
            errors.append("doctor leaked the session secret")
        try:
            doc = json.loads((doctor.stdout or "").strip().splitlines()[-1])
            if doc.get("token_in_report") is not False:
                errors.append("doctor must set token_in_report false")
            if "LOCALAPPDATA/HHGodotAgent" not in json.dumps(doc):
                errors.append("doctor must name LOCALAPPDATA/HHGodotAgent")
        except (json.JSONDecodeError, IndexError):
            errors.append(f"doctor stdout was not JSON: {redact(doctor.stdout or '', secret)}")

        project_hits = grep_token(tmp, secret)
        if project_hits:
            errors.append("session secret written into the Godot project tree")
        repo_hits: list[str] = []
        for tree in (
            REPO_ROOT / "bridge",
            REPO_ROOT / "tests",
            REPO_ROOT / "godot" / "plugin-project",
            REPO_ROOT / ".hh-agent",
            REPO_ROOT / "docs" / "godot-agent",
        ):
            repo_hits.extend(grep_token(tree, secret))
        if repo_hits:
            errors.append("session secret written into the git project")
        combined_err = "".join(err_lines)
        if secret and secret in combined_err:
            errors.append("session secret appeared in sidecar logs")
        if secret and desc_path and ".godot" in desc_path.as_posix():
            errors.append("descriptor landed under .godot")
        if secret and desc_path and ".hh-agent" in desc_path.as_posix():
            errors.append("descriptor landed under .hh-agent")

    except Exception as exc:  # noqa: BLE001 — surface the first transport failure
        errors.append(redact(f"sidecar run failed: {type(exc).__name__}: {exc}", secret))
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
            lock = desc_path.with_name("sidecar.lock")
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass

    if errors:
        print("FAIL: session transport", file=sys.stderr)
        for item in errors:
            print(f"  - {redact(item, secret)}", file=sys.stderr)
        return 1

    print(
        "PASS: loopback OS-assigned bind; typed rejects for token/project/protocol/non-loopback; "
        "EADDRINUSE retried listen(0); executed 100 reconnects; stdio MCP not-dispatched; "
        "token only under LOCALAPPDATA/HHGodotAgent; plan R2-WP2 progress consistent; "
        "plugin-project allows only hh_agent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
