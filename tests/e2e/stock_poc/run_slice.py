#!/usr/bin/env python3
"""R1-WP4: stock-only vertical slice on disposable copies of stock-poc.

Stdlib only. Never touches godot/plugin-project/addons. Never vendors MCP/GUT.
Pinned Godot 4.7.1-stable via tools/godot/doctor.py. Honest SKIP for dummy screenshots.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PLUGIN_PROJECT = (REPO / "godot" / "plugin-project").resolve()
FIXTURE = REPO / "godot" / "test-projects" / "stock-poc"
WORK = HERE / "work"
RESULT_MD = HERE / "RESULT.md"
RESULT_JSON = HERE / "results.json"

MIN_VISIBLE_PNG = 2048
MIN_DIM = 128
MIN_UNIQUE_COLORS = 5
POS_DELTA_MIN = 20.0
REQUIRED_TSCN = (
    ('name="Player" type="CharacterBody2D"', "CharacterBody2D Player"),
    ('name="Sprite2D" type="Sprite2D"', "Sprite2D"),
    ('name="CollisionShape2D" type="CollisionShape2D"', "player collision"),
    ('name="Camera2D" type="Camera2D"', "Camera2D"),
    ('name="StatusLabel" type="Label"', "UI Label"),
    ('name="Floor" type="StaticBody2D"', "collision floor"),
    ('name="Hud" type="CanvasLayer"', "HUD"),
)
FORBIDDEN_DUP = re.compile(
    r"^(Main|Player|Sprite2D|Camera2D|Hud|StatusLabel|Floor|FloorShape)\d+$"
)
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def die(msg: str, code: int = 2) -> None:
    print(f"stock-poc: FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def refuse_plugin_project(path: Path) -> None:
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


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def ulid() -> str:
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    val = (ms << 80) | rand
    chars: list[str] = []
    for _ in range(26):
        chars.append(CROCKFORD[val & 31])
        val >>= 5
    return "".join(reversed(chars))


def session_token() -> str:
    return "hh-stock-poc-" + os.urandom(32).hex()


def free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def doctor_paths() -> tuple[Path, Path]:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "godot" / "doctor.py"), "--install", "--print-bin"],
        cwd=str(REPO),
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


def copy_fixture(dest: Path) -> None:
    refuse_plugin_project(dest)
    if dest.exists():
        shutil.rmtree(dest)

    def _ignore(directory: str, names: list[str]) -> set[str]:
        refuse_plugin_project(Path(directory))
        return {n for n in names if n in {".godot", ".import"}}

    shutil.copytree(FIXTURE, dest, ignore=_ignore)
    refuse_plugin_project(dest)


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


class Proc:
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
    editor: bool,
    extra: list[str] | None = None,
) -> Proc:
    refuse_plugin_project(project)
    args = [str(exe), "--headless"]
    if editor:
        args.append("--editor")
    args.extend(["--path", str(project)])
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
    return Proc(proc, log_path)


class JsonLineClient:
    def __init__(self) -> None:
        self.sock: socket.socket | None = None
        self.buf = b""
        self.n = 0
        self.token = ""

    def connect(self, host: str, port: int, timeout: float = 8.0) -> None:
        self.close()
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = sock
        self.buf = b""

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def call(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 90.0,
        token: str | None = None,
    ) -> dict[str, Any]:
        if self.sock is None:
            raise OSError("not connected")
        self.n += 1
        msg = {
            "id": str(self.n),
            "command": command,
            "command_id": ulid(),
            "params": params or {},
            "token": self.token if token is None else token,
        }
        self.sock.settimeout(timeout)
        self.sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        line = self._recv_line(timeout)
        data = json.loads(line)
        if not isinstance(data, dict):
            return {"status": "error", "code": "BAD_RESPONSE", "message": str(data)}
        return data

    def _recv_line(self, timeout: float) -> str:
        assert self.sock is not None
        deadline = time.time() + timeout
        while True:
            if b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                return line.decode("utf-8", errors="replace").strip()
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError("JSON-line reply timed out")
            self.sock.settimeout(remaining)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise OSError("connection closed")
            self.buf += chunk


def wait_connect(host: str, port: int, timeout: float, proc: Proc) -> JsonLineClient:
    client = JsonLineClient()
    deadline = time.time() + timeout
    last = "not attempted"
    while time.time() < deadline:
        if not proc.alive():
            raise OSError(f"editor exited before listen: {last}")
        try:
            client.connect(host, port, timeout=1.5)
            return client
        except OSError as exc:
            last = str(exc)
            time.sleep(0.35)
    raise OSError(f"never connected to {host}:{port}: {last}")


def ok(resp: dict[str, Any]) -> bool:
    return resp.get("status") == "success"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def wait_file(path: Path, timeout: float, proc: Proc | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.is_file() and path.stat().st_size > 2:
            return True
        if proc is not None and not proc.alive() and not path.is_file():
            return False
        time.sleep(0.2)
    return path.is_file()


def png_ihdr(path: Path) -> dict[str, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != PNG_SIG:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return {"w": int(width), "h": int(height)}


def png_unique_colors(path: Path, cap: int = 64) -> int | None:
    """Decode 8-bit RGB/RGBA PNGs enough to count unique colors. None if unsupported."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:8] != PNG_SIG:
        return None
    pos = 8
    width = height = bit_depth = color_type = 0
    idat = b""
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if width <= 0 or height <= 0 or bit_depth != 8 or color_type not in (2, 6):
        return None
    try:
        raw = zlib.decompress(idat)
    except zlib.error:
        return None
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    rows: list[bytes] = []
    i = 0
    prev = bytearray(stride)
    for _ in range(height):
        if i >= len(raw):
            return None
        ftype = raw[i]
        i += 1
        row = bytearray(raw[i : i + stride])
        i += stride
        if len(row) < stride:
            return None
        if ftype == 1:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + left) & 255
        elif ftype == 2:
            for x in range(stride):
                row[x] = (row[x] + prev[x]) & 255
        elif ftype == 3:
            for x in range(stride):
                left = row[x - bpp] if x >= bpp else 0
                row[x] = (row[x] + ((left + prev[x]) // 2)) & 255
        elif ftype == 4:
            for x in range(stride):
                a = row[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[x] = (row[x] + pr) & 255
        elif ftype != 0:
            return None
        rows.append(bytes(row))
        prev = row
    colors: set[tuple[int, int, int]] = set()
    step = max(1, height // 48)
    for y in range(0, height, step):
        row = rows[y]
        for x in range(0, width, step):
            o = x * bpp
            colors.add((row[o], row[o + 1], row[o + 2]))
            if len(colors) >= cap:
                return cap
    return len(colors)


def classify_screenshot(path: Path) -> tuple[str, str]:
    if not path.is_file():
        return "SKIP", "no screenshot file (not a player frame)"
    size = path.stat().st_size
    ihdr = png_ihdr(path)
    if ihdr is None:
        return "SKIP", f"{size} bytes, not a PNG"
    w, h = ihdr["w"], ihdr["h"]
    if size < MIN_VISIBLE_PNG or w < MIN_DIM or h < MIN_DIM:
        return (
            "SKIP",
            f"{w}x{h} {size}B dummy/headless viewport (not a player screenshot)",
        )
    ncolors = png_unique_colors(path)
    if ncolors is None:
        return (
            "SKIP",
            f"{w}x{h} {size}B could not verify pixel variety (not marked PASS)",
        )
    if ncolors < MIN_UNIQUE_COLORS:
        return (
            "SKIP",
            f"{w}x{h} {size}B nearly-uniform ({ncolors} colors), not a player frame",
        )
    return "PASS", f"{w}x{h} {size}B {ncolors} colors treated as visible player frame"


def tscn_problems(text: str) -> list[str]:
    problems: list[str] = []
    names = re.findall(r'\[node name="([^"]+)"', text)
    counts = Counter(names)
    for needle, label in REQUIRED_TSCN:
        if needle not in text:
            problems.append(f"missing {label}")
    if counts.get("Player", 0) != 1:
        problems.append(f"Player count={counts.get('Player', 0)}")
    for name, n in counts.items():
        if FORBIDDEN_DUP.match(name):
            problems.append(f"duplicate-style name {name}")
        if name == "Player" and n > 1:
            problems.append("Player appears more than once")
    return problems


def log_problems(log_path: Path, token: str) -> list[str]:
    if not log_path.is_file():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    problems: list[str] = []
    if token and token in text:
        problems.append("session token leaked into log")
    if "SCRIPT ERROR" in text:
        problems.append("SCRIPT ERROR in log")
    if re.search(r"^ERROR: ", text, re.MULTILINE):
        snippet = [
            ln
            for ln in text.splitlines()
            if ln.startswith("ERROR: ") and 'Parameter "t" is null' not in ln
        ]
        if snippet:
            problems.append("engine ERROR: " + " | ".join(snippet[:3])[:240])
    return problems


def plugin_project_dirty() -> list[str]:
    errors: list[str] = []
    addons = PLUGIN_PROJECT / "addons"
    if addons.is_dir():
        leftover = [p for p in addons.rglob("*") if p.is_file() and ".godot" not in p.parts]
        if leftover:
            errors.append(
                "plugin-project/addons has files: "
                + ", ".join(rel(p) for p in leftover[:8])
            )
    forbidden = (
        "godot_mcp",
        "beckett",
        "gut",
        "keeveeg",
        "sods2",
        "satelliteoflove",
        "hh_stock_poc",
        "plugin.cfg",
    )
    for marker in PLUGIN_PROJECT.rglob("*"):
        if not marker.is_file() or any(part == ".godot" for part in marker.parts):
            continue
        blob = marker.name.lower()
        if blob in {"plugin.cfg", "plugin.gd"}:
            errors.append(f"plugin-project contains addon file {rel(marker)}")
        if any(name in marker.as_posix().lower() for name in forbidden if name not in {"plugin.cfg"}):
            if "plugin.cfg" in blob or "plugin.gd" in blob or "mcp" in blob or "beckett" in blob:
                errors.append(f"plugin-project looks like MCP/addon leak: {rel(marker)}")
    return errors


def editor_session(
    exe: Path,
    project: Path,
    out_dir: Path,
    log_path: Path,
    token: str,
    commands: list[tuple[str, dict[str, Any] | None, float]],
) -> dict[str, Any]:
    port = free_port()
    env = os.environ.copy()
    env["HH_STOCK_POC_PORT"] = str(port)
    env["HH_STOCK_POC_TOKEN"] = token
    env["HH_STOCK_POC_OUT"] = str(out_dir.resolve()).replace("\\", "/")
    env.pop("HH_STOCK_POC_PLAYTEST", None)
    session = start_godot(exe, project, log_path, env, editor=True)
    replies: dict[str, dict[str, Any]] = {}
    client: JsonLineClient | None = None
    try:
        client = wait_connect("127.0.0.1", port, 180.0, session)
        client.token = token
        bad = client.call("ping", token="wrong-token", timeout=15.0)
        replies["wrong_token"] = bad
        ping = client.call("ping", timeout=15.0)
        replies["ping"] = ping
        if not ok(ping):
            raise OSError(f"ping failed: {ping}")
        for command, params, timeout in commands:
            replies[command] = client.call(command, params, timeout=timeout)
    finally:
        if client is not None:
            try:
                if session.alive():
                    client.call("quit", timeout=10.0)
            except (OSError, TimeoutError, json.JSONDecodeError):
                pass
            client.close()
        deadline = time.time() + 12.0
        while session.alive() and time.time() < deadline:
            time.sleep(0.2)
        session.stop()
    replies["_log"] = str(log_path)
    return replies


def run_one(run_id: int, console: Path, token: str) -> dict[str, Any]:
    run_dir = WORK / f"run-{run_id:02d}"
    project = run_dir / "project"
    out_dir = run_dir / "out"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copy_fixture(project)
    record: dict[str, Any] = {
        "run": run_id,
        "project": rel(project),
        "gameplay": "FAIL",
        "unique_nodes": "FAIL",
        "position_delta": "FAIL",
        "screenshot": "SKIP",
        "inspector": "GAP",
        "overall": "FAIL",
        "notes": [],
        "delta_x": 0.0,
    }

    dirty = plugin_project_dirty()
    if dirty:
        record["notes"].extend(dirty)
        record["overall"] = "FAIL"
        return record

    try:
        build = editor_session(
            console,
            project,
            out_dir,
            out_dir / "editor-build.log",
            token,
            [
                ("build_slice", {}, 180.0),
                ("select_player", {}, 30.0),
                ("save_scene", {}, 30.0),
                ("query_tree", {}, 30.0),
            ],
        )
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        record["notes"].append(f"editor build: {type(exc).__name__}: {exc}")
        record["notes"].extend(log_problems(out_dir / "editor-build.log", token))
        return record

    record["wrong_token_typed"] = (build.get("wrong_token") or {}).get("code") == "AUTH_FAILED"
    if not ok(build.get("build_slice") or {}):
        record["notes"].append(f"build_slice failed: {build.get('build_slice')}")
        record["notes"].extend(log_problems(out_dir / "editor-build.log", token))
        return record
    if not ok(build.get("save_scene") or {}):
        record["notes"].append(f"save_scene failed: {build.get('save_scene')}")
        return record

    select = (build.get("select_player") or {}).get("result") or {}
    if select.get("inspector_gap") is True or select.get("inspector_visible_to_human") is False:
        record["inspector"] = "GAP"
        record["inspector_note"] = "headless EditorInterface select/inspect ran; Inspector not shown to a human"
    elif select.get("inspector_object") == "Player" and "Player" in json.dumps(select.get("selected")):
        record["inspector"] = "PASS"
        record["inspector_note"] = "Inspector object is Player (GUI session)"
    else:
        record["inspector"] = "GAP"
        record["inspector_note"] = f"select readback incomplete in this mode: {select}"

    tscn = project / "main.tscn"
    if not tscn.is_file():
        record["notes"].append("main.tscn was not saved")
        return record
    tscn_text = tscn.read_text(encoding="utf-8", errors="replace")
    uniq = tscn_problems(tscn_text)
    project_godot = (project / "project.godot").read_text(encoding="utf-8", errors="replace")
    if "move_right" not in project_godot:
        uniq.append("InputMap move_right not persisted to project.godot")
    player_gd = project / "player.gd"
    if not player_gd.is_file():
        uniq.append("player.gd missing")
    else:
        src = player_gd.read_text(encoding="utf-8")
        if "extends CharacterBody2D" not in src or "func _physics_process(_delta: float) -> void:" not in src:
            uniq.append("player.gd is not typed movement script")

    env = os.environ.copy()
    env["HH_STOCK_POC_PLAYTEST"] = "1"
    env["HH_STOCK_POC_OUT"] = str(out_dir.resolve()).replace("\\", "/")
    env["HH_STOCK_POC_TOKEN"] = token
    env.pop("HH_STOCK_POC_PORT", None)
    game = start_godot(
        console,
        project,
        out_dir / "game.log",
        env,
        editor=False,
        extra=["--fixed-fps", "60"],
    )
    play_path = out_dir / "play.json"
    try:
        wait_file(play_path, 60.0, game)
        deadline = time.time() + 8.0
        while game.alive() and time.time() < deadline:
            time.sleep(0.2)
    finally:
        game.stop()

    play = read_json(play_path)
    dx = float(((play.get("delta") or {}).get("x") or 0.0))
    record["delta_x"] = dx
    if play.get("ok") is True and dx >= POS_DELTA_MIN:
        record["gameplay"] = "PASS"
        record["position_delta"] = "PASS"
    elif play.get("ok") is True:
        record["position_delta"] = "FAIL"
        record["notes"].append(f"position delta {dx} < {POS_DELTA_MIN}")
    else:
        record["notes"].append(f"playtest failed: {play or 'no play.json'}")
        record["notes"].extend(log_problems(out_dir / "game.log", token))

    shot_path = out_dir / "screenshot.png"
    shot_status, shot_note = classify_screenshot(shot_path)
    record["screenshot"] = shot_status
    record["screenshot_note"] = shot_note

    try:
        reopen = editor_session(
            console,
            project,
            out_dir,
            out_dir / "editor-reopen.log",
            token,
            [
                ("reopen_scene", {}, 90.0),
                ("query_tree", {}, 30.0),
            ],
        )
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        record["notes"].append(f"reopen: {type(exc).__name__}: {exc}")
        record["unique_nodes"] = "FAIL"
        return record

    tree = ((reopen.get("query_tree") or reopen.get("reopen_scene") or {}).get("result") or {})
    dupes = tree.get("duplicate_sibling_names") or []
    names = tree.get("names") or []
    if dupes:
        uniq.append(f"editor duplicate siblings: {dupes}")
    if any(FORBIDDEN_DUP.match(str(n)) for n in names):
        uniq.append(f"editor names include numbered dupes: {names}")
    if not tree.get("has_player"):
        uniq.append("reopen query_tree missing Player")
    tscn_text = tscn.read_text(encoding="utf-8", errors="replace")
    uniq.extend(tscn_problems(tscn_text))
    uniq = sorted(set(uniq))
    if uniq:
        record["unique_nodes"] = "FAIL"
        record["notes"].extend(uniq)
    else:
        record["unique_nodes"] = "PASS"

    record["notes"].extend(log_problems(out_dir / "editor-build.log", token))
    record["notes"].extend(log_problems(out_dir / "editor-reopen.log", token))
    record["notes"].extend(log_problems(out_dir / "game.log", token))

    gameplay_ok = record["gameplay"] == "PASS" and record["position_delta"] == "PASS"
    unique_ok = record["unique_nodes"] == "PASS"
    token_leak = any("token leaked" in n for n in record["notes"])
    script_err = any("SCRIPT ERROR" in n for n in record["notes"])
    if gameplay_ok and unique_ok and not token_leak and not script_err:
        record["overall"] = "PASS"
    else:
        record["overall"] = "FAIL"
    return record


def write_results(rows: list[dict[str, Any]], extras: dict[str, Any]) -> None:
    passed = sum(1 for r in rows if r.get("overall") == "PASS")
    failed = len(rows) - passed
    payload = {
        "wp": "R1-WP4",
        "godot": extras.get("godot", ""),
        "runs": len(rows),
        "passed": passed,
        "failed": failed,
        "plugin_project_clean": extras.get("plugin_project_clean", False),
        "screenshot_policy": (
            "PASS only if PNG >= 2048B, >=128px, and >=5 unique colors; "
            "headless dummy gray is SKIP, never PASS"
        ),
        "inspector_policy": "GAP in headless (EditorInterface select/inspect only; no human Inspector)",
        "human_launcher": "hh-godot-editor.bat -> godot/test-projects/minimal-2d (no MCP)",
        "poc_gui": "hh-stock-poc.bat -> godot/test-projects/stock-poc (stock plugin, no MCP)",
        "rows": rows,
    }
    RESULT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# R1-WP4 stock-only vertical slice",
        "",
        f"STOCK_POC_OVERALL={passed}/{len(rows)}",
        f"STOCK_POC_FAILS={failed}",
        f"STOCK_POC_SCREENSHOT={_majority(rows, 'screenshot')}",
        f"STOCK_POC_INSPECTOR={_majority(rows, 'inspector')}",
        "",
        f"Godot pin: {extras.get('godot', '')}.",
        "Fixture copies under `tests/e2e/stock_poc/work/` (gitignored).",
        "`godot/plugin-project/` was not used and must stay without addons/.",
        "Human editor: `hh-godot-editor.bat` (minimal-2d, no MCP).",
        "Optional POC GUI: `hh-stock-poc.bat` (this fixture, stock plugin only).",
        "",
        "Screenshot: dummy/headless gray frames are **SKIP**, never PASS.",
        "Inspector: headless is **GAP**; selection/inspect API still runs.",
        "",
        "| run | overall | gameplay | unique_nodes | position_delta | screenshot | inspector | notes |",
        "|-----|---------|----------|--------------|----------------|------------|-----------|-------|",
    ]

    def cell(text: str, limit: int = 80) -> str:
        cleaned = (text or "—").replace("|", "/").replace("\n", " ")
        return cleaned if len(cleaned) <= limit else cleaned[: limit - 1] + "…"

    for row in rows:
        notes = "; ".join(str(n) for n in row.get("notes") or [])
        if row.get("screenshot_note"):
            notes = (notes + "; " if notes else "") + str(row["screenshot_note"])
        if row.get("inspector_note"):
            notes = (notes + "; " if notes else "") + str(row["inspector_note"])
        lines.append(
            "| {run} | {overall} | {game} | {uniq} | {dx} | {shot} | {insp} | {notes} |".format(
                run=row.get("run"),
                overall=row.get("overall"),
                game=row.get("gameplay"),
                uniq=row.get("unique_nodes"),
                dx=f"{row.get('position_delta')} ({row.get('delta_x')})",
                shot=row.get("screenshot"),
                insp=row.get("inspector"),
                notes=cell(notes),
            )
        )
    lines += [
        "",
        f"**Overall: {passed}/{len(rows)} {'PASS' if failed == 0 and len(rows) else 'FAIL'}**.",
        "",
    ]
    RESULT_MD.write_text("\n".join(lines), encoding="utf-8")


def _majority(rows: list[dict[str, Any]], key: str) -> str:
    counts = Counter(str(r.get(key, "SKIP")) for r in rows)
    if not counts:
        return "SKIP"
    return counts.most_common(1)[0][0]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="R1-WP4 stock-only vertical slice.")
    p.add_argument("--runs", type=int, default=20, help="clean-copy iterations (default 20)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        die("--runs must be >= 1")
    if not FIXTURE.is_dir():
        die(f"missing fixture {FIXTURE}")
    if not (FIXTURE / "addons" / "hh_stock_poc" / "plugin.cfg").is_file():
        die("stock-poc missing addons/hh_stock_poc/plugin.cfg")
    dirty = plugin_project_dirty()
    if dirty:
        die("; ".join(dirty))
    WORK.mkdir(parents=True, exist_ok=True)
    try:
        console, _gui = doctor_paths()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        die(f"could not resolve Godot pin: {exc}")
    version_proc = subprocess.run(
        [str(console), "--version"],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    version = (version_proc.stdout or version_proc.stderr).strip().splitlines()[0] if version_proc.returncode == 0 else ""
    if "4.7.1" not in version:
        die(f"refusing Godot version {version!r}; need 4.7.1-stable")
    token = session_token()
    rows: list[dict[str, Any]] = []
    for i in range(1, args.runs + 1):
        print(f"stock-poc: run {i}/{args.runs}")
        row = run_one(i, console, token)
        rows.append(row)
        print(
            f"stock-poc: run {i} overall={row['overall']} "
            f"game={row['gameplay']} uniq={row['unique_nodes']} "
            f"dx={row['delta_x']} shot={row['screenshot']} insp={row['inspector']}"
        )
        if row["notes"]:
            print(f"stock-poc: notes: {row['notes'][:4]}")
    extras = {
        "godot": version,
        "plugin_project_clean": not plugin_project_dirty(),
    }
    write_results(rows, extras)
    passed = sum(1 for r in rows if r.get("overall") == "PASS")
    print(f"stock-poc: wrote {rel(RESULT_MD)} {passed}/{len(rows)}")
    print(f"stock-poc: plugin-project clean: {extras['plugin_project_clean']}")
    if passed != len(rows) or not extras["plugin_project_clean"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
