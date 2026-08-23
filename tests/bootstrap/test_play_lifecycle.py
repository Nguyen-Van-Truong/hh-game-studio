#!/usr/bin/env python3
"""R6-WP1: Play/debug process lifecycle and log/diagnostics.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP1 [ ]; while unticked CURRENT_VALID_WP=R6-WP1.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS. No dummy screenshot PNG.
Do not paper-ACK play.start. Plugin is the only .tscn/.gd writer.

Verify (encoded here; this file is the official harness):
  - parse error on Play → logs have PARSER + res://:line
  - runtime exception + stack
  - crash OR hang → watchdog stop, not playing
  - play.restart new run_id, first dead
  - stale run A rejected after run B
  - screenshots=SKIP; no dummy PNG

If headless --editor never flips is_playing_scene: label Alternative,
headless_play=unproven, do not invent playing=true. Try exclusive GUI
Godot (same pin exe, --editor --path godot/plugin-project). Do not start
a second Godot if one is already on plugin-project.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r6w1"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"

OK_SCRIPT = """extends Node2D

func _ready() -> void:
	print("hh_play_alive")
"""

PARSE_SCRIPT = """extends Node2D

func _ready() -> void:
	await get_tree().create_timer(0.6).timeout
	var path_s: String = "res://r6w1/parse_bad.gd"
	var f: FileAccess = FileAccess.open(path_s, FileAccess.WRITE)
	if f != null:
		f.store_string("extends Node\\nfunc _init() -> void:\\n\\tthis is not valid gd\\n")
		f.close()
	var _scr: Resource = ResourceLoader.load(path_s)
"""

RUNTIME_SCRIPT = """extends Node2D

func _ready() -> void:
	await get_tree().create_timer(0.6).timeout
	var missing: Node = null
	missing.get_path()
"""

HANG_SCRIPT = """extends Node2D

func _ready() -> void:
	while true:
		pass
"""

CRASH_SCRIPT = """extends Node2D

func _ready() -> void:
	OS.crash("hh_play_crash")
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP1 [ ]; while unticked require CURRENT_VALID_WP=R6-WP1."""
    errors: list[str] = []
    current = ""
    wp1 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP1\b", stripped):
            wp1 = stripped
    if wp1 is None:
        return ["plan missing R6-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R6-WP1 heading must keep [ ] until coordinator tick")
        if current != "R6-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP1 while WP1 is unticked)")
    elif not re.match(r"^R6-WP([2-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP2+ after R6-WP1 tick)")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def plugin_godot_busy() -> bool:
    needle = "plugin-project"
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'Godot' } | "
                    "Select-Object -ExpandProperty CommandLine"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        return needle in blob.replace("\\", "/").lower()
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    return needle in (proc.stdout or "").lower() and "godot" in (proc.stdout or "").lower()


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png|gd)", self_text):
        errors.append("official test writes a .tscn/.tres/.png/.gd path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record headless_play Alternative honestly")
    if "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "PARSER" not in self_text or "res://" not in self_text:
        errors.append("official test must encode PARSER + res://:line")
    if "stale run" not in self_text:
        errors.append("official test must encode stale run A rejected after run B")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "hh_play:" + "log" in self_text or "Engine" + "Debugger.send_message" in self_text:
        errors.append("official fixtures must not print PARSER/stack needles")
    if "this-run" not in self_text or "parse_bad.gd" not in self_text:
        errors.append("official test must bind this-run parse_bad.gd / engine text")
    if '"stack" not in ' + 'rt_blob' in self_text:
        errors.append("runtime verify must not pass on JSON key stack alone")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_play_adapter" not in router:
        errors.append("router must dispatch through hh_play_adapter")
    if "godot.play" not in router:
        errors.append("router must name godot.play")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_debugger_plugin" not in plugin or "remove_debugger_plugin" not in plugin:
        errors.append("plugin.gd must register EditorDebuggerPlugin on enter/exit")
    if "hh_play_debugger" not in plugin:
        errors.append("plugin.gd must load hh_play_debugger")

    adapter = ADDON / "core" / "hh_play_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_play_adapter.gd")
        return errors
    text = adapter.read_text(encoding="utf-8")
    for needle in (
        "play_main_scene",
        "play_current_scene",
        "play_custom_scene",
        "stop_playing_scene",
        "is_playing_scene",
        "get_playing_scene",
        "release_all",
    ):
        if needle not in text:
            errors.append(f"play adapter must use {needle}")
    if "play_" + "debug_scene" in text:
        errors.append("there is no dedicated debug-scene API; debug = start + session")
    if "OS." + "execute" in text or "create_" + "process" in text or "--" + "quit-after" in text:
        errors.append("play.start must not spawn a second Godot / quit-after CLI")
    if "OS." + "get_process_id" in text:
        errors.append("must not use the editor process id as play PID")
    if "Engine" + "Debugger" in text:
        errors.append("game-side debugger singleton in the editor plugin is not debug attached")
    if "get_edited_scene_root() as the game" in text or "invent playing" in text.lower():
        pass
    if "Movie Maker" not in text and "movie_maker" in text:
        errors.append("play adapter must not use Movie Maker")
    if "headless_play" not in text:
        errors.append("play adapter must label headless_play proven|unproven")

    dbg = ADDON / "core" / "hh_play_debugger.gd"
    if not dbg.is_file():
        errors.append("missing hh_play_debugger.gd")
    else:
        dtext = dbg.read_text(encoding="utf-8")
        if "func _setup_session" not in dtext:
            errors.append("debugger plugin must implement _setup_session")
        if "func _has_capture" not in dtext:
            errors.append("debugger plugin must implement _has_capture")
        if "func _capture" not in dtext:
            errors.append("debugger plugin must implement _capture")
        if "Engine" + "Debugger" in dtext:
            errors.append("do not use the game-side debugger singleton in the editor debugger plugin")
        if re.search(r"return true", dtext):
            errors.append("debugger _capture must not return true on built-in error/output")

    errors_gd = (ADDON / "core" / "hh_errors.gd").read_text(encoding="utf-8")
    if "E_TIMEOUT" not in errors_gd:
        errors.append("plugin hh_errors.gd must add E_TIMEOUT")
    err_ts = (BRIDGE / "src" / "registry" / "errors.ts").read_text(encoding="utf-8")
    if "E_TIMEOUT" not in err_ts:
        errors.append("bridge errors.ts must add E_TIMEOUT")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "PLAY_APPLY" not in lifecycle or "isPlayApply" not in lifecycle:
        errors.append("scene_lifecycle must export PLAY_APPLY / isPlayApply")
    proven = lifecycle.split("export function isProvenEditorApply")[-1]
    if "isPlayApply" in proven.split("{", 1)[-1].split("}", 1)[0]:
        errors.append("isPlayApply must NOT be inside isProvenEditorApply (EXTERNAL, not UndoRedo)")
    for action_id in ("play.start", "play.stop", "play.restart", "play.debug"):
        if action_id not in lifecycle:
            errors.append(f"PLAY_APPLY must list {action_id}")
    if "play.status" in lifecycle.split("PLAY_APPLY")[1].split("]")[0]:
        errors.append("PLAY_APPLY must not include play.status/logs")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function playApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check play apply")
    if "const playFail = playApplyOk" not in execute:
        errors.append("execute.ts must call playApplyOk from apply path")
    if "isPlayApply(accepted.action_id)" not in execute and "isPlayApply(accepted.action_id)" not in execute.replace(
        "\n", " "
    ):
        if "isPlayApply(" not in execute:
            errors.append("classify must dispatch isPlayApply EXTERNAL apply")
    if '"play"' not in execute:
        errors.append("execute.ts after_summary must use kind play")
    if "get_playing_scene bind mismatch" not in execute:
        errors.append("execute.ts must bind get_playing_scene")
    if "invented playing=true" not in execute:
        errors.append("execute.ts must refuse invented playing=true")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "play logs require the Play process log ring (R6)" in reads:
        errors.append("play.logs must use the Play log ring, not the old unverified stub")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def mcp_call(proc, req_id: int, name: str, arguments: dict, timeout: float = 60.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc,
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 60.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, method, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    return True


def after_of(body: dict) -> dict:
    after = body.get("after") or {}
    return after if isinstance(after, dict) else {}


def start_godot(exe: Path, headless: bool) -> tuple[subprocess.Popen[str], list[str]]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_AGENT_RELOAD_OUT", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    args = [str(exe)]
    if headless:
        args.append("--headless")
    args.extend(["--editor", "--path", str(PLUGIN_PROJECT)])
    godot = subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    lines: list[str] = []

    def drain_out() -> None:
        if godot.stdout is None:
            return
        for line in godot.stdout:
            lines.append(line)

    import threading

    threading.Thread(target=drain_out, daemon=True).start()
    threading.Thread(target=sess.drain_stderr, args=(godot, lines), daemon=True).start()
    return godot, lines


def write_script(proc, req_id: int, path: str, contents: str, errors: list[str]) -> int:
    req_id, body = tool_call(proc, req_id, "godot.script", "write", {"path": path, "contents": contents})
    ack_ok(body, errors, f"script.write {path}")
    return req_id


def attach_and_save(proc, req_id: int, scene: str, script: str, errors: list[str]) -> int:
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": script}
    )
    ack_ok(attached, errors, f"script.attach {script}")
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, f"scene.save {scene}")
    return req_id


def play_start(proc, req_id: int, scene: str, mode: str = "play") -> tuple[int, dict]:
    return tool_call(proc, req_id, "godot.play", "start", {"scene": scene, "mode": mode}, timeout=90.0)


def play_stop(proc, req_id: int, reason: str = "test", run_id: str | None = None) -> tuple[int, dict]:
    params: dict = {"reason": reason}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "stop", params, timeout=60.0)


def play_status(proc, req_id: int, run_id: str | None = None) -> tuple[int, dict]:
    params: dict = {"detail": "short"}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "status", params)


def play_logs(proc, req_id: int, run_id: str | None = None, limit: int = 50) -> tuple[int, dict]:
    params: dict = {"limit": limit}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "logs", params)


def logs_blob(body: dict) -> str:
    after = after_of(body)
    return json.dumps(after, ensure_ascii=False).lower()


def log_items(body: dict) -> list[dict]:
    after = after_of(body)
    items = after.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def item_messages(body: dict, run_id: str | None = None) -> str:
    parts: list[str] = []
    for item in log_items(body):
        if run_id and str(item.get("run_id") or "") != run_id:
            continue
        parts.append(str(item.get("message") or ""))
        parts.append(str(item.get("path") or ""))
    return "\n".join(parts).lower()


def wait_not_playing(proc, req_id: int, seconds: float) -> tuple[int, dict]:
    deadline = time.time() + seconds
    last: dict = {}
    while time.time() < deadline:
        req_id, last = play_status(proc, req_id)
        if after_of(last).get("playing") is not True:
            return req_id, last
        time.sleep(0.5)
    return req_id, last


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str, str]:
    scene = "res://r6w1/play.tscn"
    script = "res://r6w1/ok.gd"
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene, script
    req_id = write_script(proc, req_id, script, OK_SCRIPT, errors)
    req_id = attach_and_save(proc, req_id, scene, script, errors)
    return req_id, scene, script


def verify_play_suite(proc, req_id: int, errors: list[str], scene: str, script: str) -> int:
    # Honest Alternatives: screenshots=SKIP; play.input stays E_UNVERIFIED
    req_id, start_body = play_start(proc, req_id, scene)
    if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
        errors.append(f"play.start must ACK with playing=true after proven Play: {start_body}")
        return req_id
    if after_of(start_body).get("is_playing_scene") is not True:
        errors.append("play.start after.is_playing_scene must be true (no invented playing=true)")
    run_a = str(after_of(start_body).get("run_id") or "")
    if len(run_a) != 26:
        errors.append(f"play.start must mint run_id: {start_body}")
    bind = str(after_of(start_body).get("playing_scene") or after_of(start_body).get("scene") or "")
    if "r6w1/play.tscn" not in bind.replace("\\", "/"):
        errors.append(f"get_playing_scene bind mismatch: {start_body}")
    if after_of(start_body).get("tree_kind") == "remote":
        errors.append("play.start must not claim editor tree is remote")
    if after_of(start_body).get("pid_source") == "editor":
        errors.append("must not report editor PID as play PID")

    req_id, jobs = tool_call(proc, req_id, "godot.job", "list", {"limit": 20})
    job_blob = json.dumps(after_of(jobs), ensure_ascii=False)
    if run_a and run_a not in job_blob:
        errors.append(f"job.list must show play run_id: {jobs}")

    req_id, busy = play_start(proc, req_id, scene)
    busy_code = str((busy.get("error") or {}).get("code") or "")
    if busy.get("ok") is True:
        errors.append("second play.start while playing must not ACK")
    if busy_code not in ("E_BUSY", "E_CONFLICT"):
        errors.append(f"second play.start while playing must be E_BUSY/E_CONFLICT: {busy}")

    req_id, restarted = tool_call(
        proc, req_id, "godot.play", "restart", {"scene": scene}, timeout=90.0
    )
    if not ack_ok(restarted, errors, "play.restart"):
        return req_id
    run_b = str(after_of(restarted).get("run_id") or "")
    if not run_b or run_b == run_a:
        errors.append(f"play.restart must mint a new run_id (A dead): {restarted}")
    if after_of(restarted).get("previous_alive") is True:
        errors.append("play.restart must mark first run dead")

    req_id, stale_logs = play_logs(proc, req_id, run_id=run_a)
    stale_code = str((stale_logs.get("error") or {}).get("code") or "")
    if stale_logs.get("ok") is True:
        errors.append("stale run A play.logs must be rejected after run B")
    if stale_code not in ("E_CONFLICT", "E_UNVERIFIED"):
        errors.append(f"stale run A rejected after run B, got {stale_logs}")

    req_id, stale_stop = play_stop(proc, req_id, run_id=run_a)
    stale_stop_code = str((stale_stop.get("error") or {}).get("code") or "")
    if stale_stop.get("ok") is True:
        errors.append("stale run A play.stop must be rejected after run B")
    if stale_stop_code not in ("E_CONFLICT", "E_UNVERIFIED"):
        errors.append(f"stale run A stop rejected after run B, got {stale_stop}")

    req_id, live_b = play_status(proc, req_id, run_id=run_b)
    if after_of(live_b).get("playing") is not True:
        errors.append(f"run B must still be playing after stale A reject: {live_b}")

    req_id, _stopped = play_stop(proc, req_id, run_id=run_b)

    req_id, debug_body = tool_call(
        proc, req_id, "godot.play", "debug", {"scene": scene}, timeout=90.0
    )
    if not ack_ok(debug_body, errors, "play.debug"):
        return req_id
    if after_of(debug_body).get("debugger_attached") is not True:
        errors.append(f"play.debug must attach a debugger session: {debug_body}")
    req_id, _ = play_stop(proc, req_id)

    req_id = write_script(proc, req_id, script, PARSE_SCRIPT, errors)
    req_id = attach_and_save(proc, req_id, scene, script, errors)
    req_id, parse_start = play_start(proc, req_id, scene)
    parse_run = str(after_of(parse_start).get("run_id") or "")
    time.sleep(4.0)
    req_id, _ = play_stop(proc, req_id)
    time.sleep(0.4)
    req_id, parse_logs = play_logs(proc, req_id)
    parse_msg = item_messages(parse_logs, parse_run)
    if "parse error" not in parse_msg and "parse_bad.gd" not in parse_msg:
        errors.append(
            "parse error on Play must be this-run engine text "
            f"(parse_bad.gd / Parse Error), not kind=PARSER: {parse_logs}"
        )
    if "res://r6w1/parse_bad.gd" not in parse_msg:
        errors.append(f"parse error on Play must include res://r6w1/parse_bad.gd: {parse_logs}")

    req_id = write_script(proc, req_id, script, RUNTIME_SCRIPT, errors)
    req_id = attach_and_save(proc, req_id, scene, script, errors)
    req_id, _rt_start = play_start(proc, req_id, scene)
    rt_run = str(after_of(_rt_start).get("run_id") or "")
    time.sleep(5.0)
    req_id, _ = play_stop(proc, req_id)
    time.sleep(0.5)
    req_id, rt_logs = play_logs(proc, req_id)
    rt_msg = item_messages(rt_logs, rt_run)
    if "get_path" not in rt_msg and "script error" not in rt_msg:
        errors.append(
            "runtime exception must be this-run engine SCRIPT ERROR/get_path "
            f"(not stale dated logs): {rt_logs}"
        )
    if "res://r6w1/ok.gd" not in rt_msg:
        errors.append(f"runtime exception must include this-run res://r6w1/ok.gd: {rt_logs}")

    req_id = write_script(proc, req_id, script, CRASH_SCRIPT, errors)
    req_id = attach_and_save(proc, req_id, scene, script, errors)
    req_id, _crash_start = play_start(proc, req_id, scene)
    crash_run = str(after_of(_crash_start).get("run_id") or "")
    req_id, after_crash = wait_not_playing(proc, req_id, 8.0)
    crashed = after_of(after_crash).get("playing") is not True
    req_id, crash_logs = play_logs(proc, req_id)
    crash_msg = item_messages(crash_logs, crash_run)
    if crash_run and "get_path" in crash_msg:
        errors.append(
            "next run_id must not inherit previous SCRIPT ERROR get_path: "
            f"{crash_logs}"
        )
    if not crashed:
        req_id, _ = play_stop(proc, req_id)
        req_id = write_script(proc, req_id, script, HANG_SCRIPT, errors)
        req_id = attach_and_save(proc, req_id, scene, script, errors)
        req_id, _hang_start = play_start(proc, req_id, scene)
        req_id, after_hang = wait_not_playing(proc, req_id, 16.0)
        if after_of(after_hang).get("playing") is True:
            errors.append(f"crash OR hang watchdog must stop Play: {after_hang}")
            req_id, _ = play_stop(proc, req_id)
        elif after_of(after_hang).get("stop_reason") not in ("hang", "crash", "error", "test"):
            # watchdog stop is enough; reason is diagnostic
            pass

    req_id, input_body = tool_call(
        proc, req_id, "godot.input", "action", {"action_name": "ui_accept", "phase": "press"}
    )
    if input_body.get("ok") is True:
        errors.append("play.input inject must stay E_UNVERIFIED (do not ACK)")
    if str((input_body.get("error") or {}).get("code") or "") != "E_UNVERIFIED":
        errors.append(f"play.input must stay E_UNVERIFIED: {input_body}")
    return req_id


def live_errors(exe: Path) -> tuple[list[str], str, str, str]:
    """Returns errors, LIVE, HEADLESS_PLAY, GUI_PLAY."""
    errors: list[str] = []
    live = "unrun"
    headless_play = "unproven"
    gui_play = "unrun"
    if plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", "unproven", "unrun"
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc = None
    godot = None
    desc_path = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed", "unproven", "unrun"
        live = "ran"
        req_id, scene, script = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_play, gui_play
        req_id, start_body = play_start(proc, req_id, scene)
        playing = start_body.get("ok") is True and after_of(start_body).get("playing") is True
        if playing:
            headless_play = "proven"
            req_id, _ = play_stop(proc, req_id)
        elif start_body.get("ok") is True:
            errors.append(f"headless play.start paper-ACK playing=true: {start_body}")
            return errors, live, "unproven", gui_play
        else:
            headless_play = "unproven"
            code = str((start_body.get("error") or {}).get("code") or "")
            if code not in ("E_UNVERIFIED", "E_TIMEOUT", "E_BUSY"):
                errors.append(f"headless play.start must be typed fail, not invented ok: {start_body}")
        # Parse/runtime Output is not delivered to EditorDebuggerPlugin in
        # headless --editor. Diagnostic suite runs on exclusive GUI Godot.
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        if plugin_godot_busy():
            errors.append("exclusive GUI Godot unavailable (plugin-project already held)")
            return errors, live, headless_play, "unrun"
        godot, godot_lines = start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_play, "failed"
        req_id, start_gui = play_start(proc, req_id, scene)
        if start_gui.get("ok") is True and after_of(start_gui).get("playing") is True:
            gui_play = "proven"
            req_id, _ = play_stop(proc, req_id)
            req_id = verify_play_suite(proc, req_id, errors, scene, script)
        else:
            gui_play = "unproven"
            errors.append(
                "GUI play.start did not prove is_playing_scene "
                f"(Alternative): {sess.redact(json.dumps(start_gui), secret)}"
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live play lifecycle failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        if godot is not None:
            try:
                tool_call(proc, req_id, "godot.play", "stop", {"reason": "test"}, timeout=10.0)
            except Exception:
                pass
            life.stop_proc(godot)
        if proc is not None:
            life.stop_proc(proc)
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
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        cleanup_temp()
    return errors, live, headless_play, gui_play


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    for action_id, verb in (
        ("play.start", "start"),
        ("play.stop", "stop"),
        ("play.restart", "restart"),
        ("play.debug", "debug"),
        ("play.status", "status"),
        ("play.logs", "logs"),
    ):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.play" or spec.get("verb") != verb:
            errors.append(f"actions.json missing {action_id}")

    built = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "build"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_play = "unproven"
    gui_play = "unrun"
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_play, gui_play = live_errors(exe)
            errors.extend(live_errs)

    if errors:
        print(
            f"FAIL: play lifecycle; LIVE={live}; HEADLESS_PLAY={headless_play}; "
            f"GUI_PLAY={gui_play}; screenshots={SCREENSHOTS}"
        )
        for item in errors:
            print(f"  - {item}")
        return 1
    print(
        f"PASS: play.start EXTERNAL apply + debugger logs; LIVE={live}; "
        f"HEADLESS_PLAY={headless_play}; GUI_PLAY={gui_play}; "
        f"screenshots={SCREENSHOTS}; play.input stays E_UNVERIFIED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
