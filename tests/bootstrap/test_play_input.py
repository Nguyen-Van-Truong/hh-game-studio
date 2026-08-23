#!/usr/bin/env python3
"""R6-WP3: Play-process input injection (not desktop OS inject / pixel RPA).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP3 [ ]; while unticked CURRENT_VALID_WP=R6-WP3; after tick allow R6-WP4+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. Do not paper-ACK input from the editor process.

Verify (encoded here; this file is the official harness):
  - action press/strength, key+modifiers, mouse motion/click, wheel,
    joypad axes/buttons, touch; sequence by tick/time; release_all
  - input reaches the Play process (_input / InputMap), not the OS desktop
  - record/replay header: engine/project/run/seed/fixed-step; snapshot hashes
    stay Alternative (do not fake hashes)
  - movement OR action press seen by the fixture; typing or click fixture;
    release_all clears held; focus-loss typed fail; replay mismatch typed fail
  - freeze/step/screenshot/perf stay E_UNVERIFIED
  - screenshots=SKIP

If headless --editor never delivers game-window input: label Alternative,
do not invent ok=true. Try exclusive GUI Godot (same pin exe, --editor
--path godot/plugin-project). Do not start a second Godot if one is already
on plugin-project. Kill leftover Godot/Node on plugin-project first.
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
TEMP_DIR = PLUGIN_PROJECT / "r6w3"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"
VARIANT_SCHEMA = "hh-godot-variant/1"
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
MAX_PAGE = 100

FIXTURE_SCRIPT = """extends Node2D

var action_presses: int = 0
var key_presses: int = 0
var mouse_clicks: int = 0
var wheel_ticks: int = 0
var joy_buttons: int = 0
var joy_axes: int = 0
var touches: int = 0
var last_strength: float = 0.0
var shift_seen: bool = false
var typed: String = ""
var button_clicks: int = 0
var move_seen: int = 0
var held_count: int = 0

func _ready() -> void:
	set_process(true)
	set_process_input(true)
	if not InputMap.has_action("ui_right"):
		InputMap.add_action("ui_right")
	if not InputMap.has_action("ui_accept"):
		InputMap.add_action("ui_accept")
	var line: LineEdit = get_node_or_null("TypeBox") as LineEdit
	if line != null:
		line.position = Vector2(16, 16)
		line.size = Vector2(200, 40)
		line.custom_minimum_size = Vector2(200, 40)
		line.grab_focus()
	var btn: Button = get_node_or_null("ClickMe") as Button
	if btn != null:
		btn.position = Vector2(16, 80)
		btn.size = Vector2(160, 40)
		btn.custom_minimum_size = Vector2(160, 40)
		btn.text = "Click"
		if not btn.pressed.is_connected(_on_click):
			btn.pressed.connect(_on_click)

func _on_click() -> void:
	button_clicks += 1

func _input(event: InputEvent) -> void:
	if event is InputEventAction:
		var act: InputEventAction = event
		if act.pressed:
			action_presses += 1
			last_strength = act.strength
	elif event is InputEventKey:
		var key: InputEventKey = event
		if key.pressed and not key.echo:
			key_presses += 1
			if key.shift_pressed:
				shift_seen = true
	elif event is InputEventMouseButton:
		var mb: InputEventMouseButton = event
		if mb.button_index == MOUSE_BUTTON_WHEEL_UP or mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			if mb.pressed:
				wheel_ticks += 1
		elif mb.pressed:
			mouse_clicks += 1
	elif event is InputEventJoypadButton:
		if (event as InputEventJoypadButton).pressed:
			joy_buttons += 1
	elif event is InputEventJoypadMotion:
		joy_axes += 1
	elif event is InputEventScreenTouch:
		if (event as InputEventScreenTouch).pressed:
			touches += 1

func _process(_delta: float) -> void:
	var n: int = 0
	if Input.is_action_pressed("ui_right"):
		n += 1
		move_seen += 1
	if Input.is_action_pressed("ui_accept"):
		n += 1
	held_count = n
	var line: LineEdit = get_node_or_null("TypeBox") as LineEdit
	if line != null and not line.text.is_empty():
		typed = line.text

func agent_observe() -> Dictionary:
	var line_s: String = ""
	var line: LineEdit = get_node_or_null("TypeBox") as LineEdit
	if line != null:
		line_s = line.text
	return {
		"action_presses": action_presses,
		"key_presses": key_presses,
		"mouse_clicks": mouse_clicks,
		"wheel_ticks": wheel_ticks,
		"joy_buttons": joy_buttons,
		"joy_axes": joy_axes,
		"touches": touches,
		"last_strength": last_strength,
		"shift_seen": shift_seen,
		"typed": typed,
		"line_text": line_s,
		"button_clicks": button_clicks,
		"move_seen": move_seen,
		"held_count": held_count,
		"held_ui_right": Input.is_action_pressed("ui_right"),
		"held_ui_accept": Input.is_action_pressed("ui_accept"),
	}
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP3 [ ]; while unticked require CURRENT_VALID_WP=R6-WP3."""
    errors: list[str] = []
    current = ""
    wp3 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP3\b", stripped):
            wp3 = stripped
    if wp3 is None:
        return ["plan missing R6-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R6-WP3 heading must keep [ ] until coordinator tick")
        if current != "R6-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP3 while WP3 is unticked)")
    elif not re.match(r"^R6-WP([4-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP4+ after R6-WP3 tick)")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for _ in range(6):
        if not TEMP_DIR.exists():
            break
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        time.sleep(0.2)
    if TEMP_DIR.exists():
        for path in TEMP_DIR.rglob("*"):
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    if TEMP_DIR.exists():
        leftovers = [p.as_posix() for p in TEMP_DIR.rglob("*")]
        errors.append(f"r6w3 fixture leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


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


def kill_plugin_project_holders(*, godot: bool = True, node: bool = True) -> None:
    if os.name == "nt":
        name_match = []
        if godot:
            name_match.append("$_.Name -match 'Godot'")
        if node:
            name_match.append("$_.Name -match '^node'")
        if not name_match:
            return
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { "
                    f"({' -or '.join(name_match)}) -and "
                    "$_.CommandLine -and "
                    "(($_.CommandLine -replace '\\\\','/') -match 'plugin-project') "
                    "} | ForEach-Object { "
                    "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
                    "}"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return
    proc = subprocess.run(["ps", "-ax", "-o", "pid=,args="], capture_output=True, text=True, check=False)
    for line in (proc.stdout or "").splitlines():
        lower = line.lower()
        if "plugin-project" not in lower.replace("\\", "/"):
            continue
        is_godot = "godot" in lower
        is_node = "node" in lower
        if (is_godot and godot) or (is_node and node):
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], capture_output=True, check=False)


def project_godot_text() -> str:
    path = PLUGIN_PROJECT / "project.godot"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def project_godot_leak_errors(when: str) -> list[str]:
    text = project_godot_text()
    errors: list[str] = []
    if "HHAgentRuntime" in text:
        errors.append(f"project.godot leaked HHAgentRuntime {when}")
    if "hh_agent_runtime" in text:
        errors.append(f"project.godot leaked hh_agent_runtime {when}")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    prefix = self_text.split("def src_scan_errors")[0]
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record headless/input Alternative honestly")
    if "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK editor-only input")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "release_all" not in self_text:
        errors.append("official test must encode release_all")
    if "button_clicks" not in self_text or "last_strength" not in self_text:
        errors.append("official test must lock widget click + action strength")
    if "200, 40" not in self_text and "custom_minimum_size" not in self_text:
        errors.append("official fixture must size TypeBox/ClickMe")
    if "focus" not in self_text.lower():
        errors.append("official test must encode focus-loss")
    if "replay mismatch" not in self_text:
        errors.append("official test must encode replay mismatch")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "PROBE_" + "SCRIPT" in self_text:
        errors.append("official test must not contain the probe script needle")
    for needle in ("Send" + "Input", "mouse_" + "event", "user" + "32"):
        if needle in prefix:
            errors.append("official test must not name a desktop inject API in the harness prefix")

    for path in ADDON.rglob("*.gd"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in ("Send" + "Input", "mouse_" + "event", "keybd_" + "event"):
            if needle in blob:
                errors.append(f"{posix} contains desktop inject needle {needle!r}")
        if ("user" + "32") in blob.lower():
            errors.append(f"{posix} contains user32")

    runtime_gd = PRODUCT_RUNTIME
    if not runtime_gd.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    else:
        rtext = runtime_gd.read_text(encoding="utf-8")
        if "parse_input_event" not in rtext:
            errors.append("product runtime must parse_input_event on the Play process")
        if "Engine" + "Debugger" not in rtext:
            errors.append("game-side autoload must use debugger send_message")

    adapter = ADDON / "core" / "hh_runtime_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_runtime_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "begin_input" not in atext:
            errors.append("runtime adapter must own begin_input")
        if "Engine" + "Debugger" in atext:
            errors.append("do not use the game-side debugger singleton in the editor runtime adapter")
        if ("Send" + "Input") in atext:
            errors.append("runtime adapter must not call a desktop inject API")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "play.input inject must stay" not in router:
        errors.append("router self-test must keep idle/no-Play input E_UNVERIFIED")
    if "_input_apply" not in router:
        errors.append("router must dispatch godot.input when Play can be proven")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "runtime freeze/step is R6-WP4" not in reads:
        errors.append("freeze/step must stay E_UNVERIFIED in this WP")

    for dbg_name in ("hh_play_debugger.gd", "hh_runtime_debugger.gd"):
        dbg = ADDON / "core" / dbg_name
        if not dbg.is_file():
            errors.append(f"missing {dbg_name}")
            continue
        dtext = dbg.read_text(encoding="utf-8")
        if re.search(r"return true", dtext):
            errors.append(f"{dbg_name} must not contain return true")
        if "Engine" + "Debugger" in dtext:
            errors.append(f"do not use the game-side debugger singleton in {dbg_name}")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function inputApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check input apply")
    if "const inputFail = inputApplyOk" not in execute:
        errors.append("execute.ts must call inputApplyOk from apply path")
    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "INPUT_APPLY" not in lifecycle or "isInputApply" not in lifecycle:
        errors.append("scene_lifecycle must export INPUT_APPLY / isInputApply")
    proven = lifecycle.split("export function isProvenEditorApply")[-1]
    if "isInputApply" in proven.split("{", 1)[-1].split("}", 1)[0]:
        errors.append("isInputApply must NOT be inside isProvenEditorApply")
    play_apply = lifecycle.split("PLAY_APPLY")[1].split("]")[0] if "PLAY_APPLY" in lifecycle else ""
    if "input.action" in play_apply:
        errors.append("do not dump input verbs into PLAY_APPLY")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_autoload_singleton(" in plugin:
        errors.append("plugin.gd must not call add_autoload_singleton")

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
    resp = mcp_call(
        proc, req_id, name=method, arguments={"action": action, "params": params, "command_id": cid}, timeout=timeout
    )
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


def err_code(body: dict) -> str:
    return str((body.get("error") or {}).get("code") or "")


def err_msg(body: dict) -> str:
    return str((body.get("error") or {}).get("message") or "")


def variant(typ: str, value) -> dict:
    return {"schema": VARIANT_SCHEMA, "type": typ, "value": value}


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


def play_start(proc, req_id: int, scene: str, mode: str = "debug") -> tuple[int, dict]:
    return tool_call(proc, req_id, "godot.play", "start", {"scene": scene, "mode": mode}, timeout=90.0)


def play_stop(proc, req_id: int, reason: str = "test", run_id: str | None = None) -> tuple[int, dict]:
    params: dict = {"reason": reason}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "stop", params, timeout=60.0)


def runtime_state(proc, req_id: int, key: str, node_path: str, run_id: str) -> tuple[int, dict]:
    return tool_call(
        proc,
        req_id,
        "godot.runtime",
        "state",
        {"key": key, "node_path": node_path, "run_id": run_id},
        timeout=20.0,
    )


def observe(proc, req_id: int, run_id: str) -> tuple[int, dict]:
    """Full fixture agent_observe dict, not a single runtime.state value."""
    for path in ("Fixture", "/root/input/Fixture"):
        req_id, node_body = tool_call(
            proc, req_id, "godot.runtime", "node", {"node_path": path, "run_id": run_id}, timeout=20.0
        )
        after = after_of(node_body)
        obs = after.get("observe")
        if isinstance(obs, dict) and ("action_presses" in obs or "held_count" in obs):
            return req_id, obs
        props = after.get("properties")
        if isinstance(props, dict) and "action_presses" in props:
            merged = dict(props)
            if isinstance(obs, dict):
                merged.update(obs)
            return req_id, merged
    req_id, body = runtime_state(proc, req_id, "action_presses", "Fixture", run_id)
    after = after_of(body)
    if body.get("ok") is True and after.get("found") is True:
        return req_id, {str(after.get("key") or "action_presses"): after.get("value")}
    return req_id, after


def wait_runtime_ready(proc, req_id: int, run_id: str) -> tuple[int, bool, dict]:
    deadline = time.time() + 20.0
    last: dict = {}
    while time.time() < deadline:
        req_id, last = tool_call(
            proc,
            req_id,
            "godot.runtime",
            "tree",
            {"detail": "short", "limit": MAX_PAGE, "run_id": run_id},
            timeout=20.0,
        )
        after = after_of(last)
        if (
            last.get("ok") is True
            and after.get("remote_tree") is True
            and str(after.get("source") or "") == "hh_agent_runtime"
        ):
            return req_id, True, last
        time.sleep(0.5)
    return req_id, False, last


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str]:
    scene = "res://r6w3/input.tscn"
    runtime_script = "res://r6w3/runtime.gd"
    fixture_script = "res://r6w3/fixture.gd"
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
        return req_id, scene
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    if "parse_input_event" not in product:
        errors.append("product runtime script must own parse_input_event")
        return req_id, scene
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene
    req_id = write_script(proc, req_id, runtime_script, product, errors)
    req_id = write_script(proc, req_id, fixture_script, FIXTURE_SCRIPT, errors)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id, scene
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": runtime_script}
    )
    if not ack_ok(attached, errors, "script.attach runtime"):
        return req_id, scene
    req_id, added = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "Fixture"},
    )
    if not ack_ok(added, errors, "node.add Fixture"):
        return req_id, scene
    req_id, fat = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": "Fixture", "path": fixture_script}
    )
    if not ack_ok(fat, errors, "script.attach Fixture"):
        return req_id, scene
    for name, cls in (
        ("TypeBox", "LineEdit"),
        ("ClickMe", "Button"),
    ):
        req_id, child = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": "Fixture", "class_name": cls, "name": name},
        )
        if not ack_ok(child, errors, f"node.add {name}"):
            return req_id, scene
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, "scene.save")
    return req_id, scene


def verify_later_wps(proc, req_id: int, errors: list[str]) -> int:
    for method, action, params, label in (
        ("godot.runtime", "freeze", {"frozen": True, "reason": "test"}, "runtime.freeze"),
        ("godot.runtime", "step", {"frames": 1}, "runtime.step"),
        ("godot.runtime", "screenshot", {"scale": 1}, "runtime.screenshot"),
        ("godot.runtime", "perf", {"detail": "short"}, "runtime.perf"),
    ):
        req_id, later = tool_call(proc, req_id, method, action, params)
        if later.get("ok") is True:
            errors.append(f"{label} must stay E_UNVERIFIED (do not ACK)")
        if err_code(later) != "E_UNVERIFIED":
            errors.append(f"{label} must stay E_UNVERIFIED: {later}")
    return req_id


def verify_input_suite(
    proc, req_id: int, errors: list[str], scene: str
) -> tuple[int, bool, dict[str, str]]:
    labels = {
        "action": "unproven",
        "typing_or_click": "unproven",
        "release_all": "unproven",
        "focus_loss": "unproven",
        "replay": "unproven",
        "joy_touch": "unproven",
    }
    req_id, idle = tool_call(
        proc, req_id, "godot.input", "action", {"action_name": "ui_accept", "phase": "press"}
    )
    if idle.get("ok") is True:
        errors.append("play.input must stay E_UNVERIFIED when Play is not running (paper-ACK)")
    if err_code(idle) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play input must be E_UNVERIFIED: {idle}")

    req_id, start_body = play_start(proc, req_id, scene, mode="debug")
    if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
        errors.append(f"play.start must ACK with playing=true after proven Play: {start_body}")
        return req_id, False, labels
    run_id = str(after_of(start_body).get("run_id") or "")
    if len(run_id) != 26:
        errors.append(f"play.start must mint run_id: {start_body}")
        return req_id, False, labels
    time.sleep(1.5)
    req_id, ready, tree_body = wait_runtime_ready(proc, req_id, run_id)
    if not ready:
        errors.append(f"runtime.tree must ACK from hh_agent_runtime before input: {tree_body}")
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels

    req_id, act = tool_call(
        proc,
        req_id,
        "godot.input",
        "action",
        {"action_name": "ui_right", "phase": "press", "strength": 0.75, "run_id": run_id},
        timeout=30.0,
    )
    if not ack_ok(act, errors, "input.action ui_right"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    if after_of(act).get("seen") is not True or after_of(act).get("injected") is not True:
        errors.append(f"input.action must be seen by the Play process: {act}")
    if after_of(act).get("source") != "hh_agent_runtime":
        errors.append(f"input.action must come from Play hh_agent_runtime: {act}")
    if after_of(act).get("send_input") is True or after_of(act).get("rpa") is True:
        errors.append("input ACK must not claim desktop OS inject / pixel RPA")
    header = after_of(act).get("header")
    if not isinstance(header, dict):
        errors.append(f"input ACK must include record/replay header: {act}")
    else:
        if str(header.get("engine") or "") != PINNED_VERSION:
            errors.append(f"header.engine must be the pin, not a fake hash: {header}")
        if str(header.get("run_id") or "") != run_id:
            errors.append(f"header.run_id bind mismatch: {header}")
        project_h = str(header.get("project") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", project_h):
            errors.append(f"header.project must be project.godot SHA-256, got {header}")
        if header.get("seed") not in (0, None):
            errors.append(f"header.seed must stay unpinned 0: {header}")
        if header.get("fixed_step") not in (False, None):
            errors.append(f"header.fixed_step must stay unpinned false: {header}")
        if header.get("snapshot_status") != "Alternative" or header.get("snapshot_hashes") not in ({}, None):
            if header.get("snapshot_hashes"):
                errors.append("do not fake snapshot hashes; leave Alternative")
    time.sleep(0.15)
    req_id, obs = observe(proc, req_id, run_id)
    if "action_presses" not in obs and "move_seen" not in obs:
        errors.append(f"fixture observe missing action counters: {obs}")
    elif int(obs.get("action_presses") or 0) < 1 and int(obs.get("move_seen") or 0) < 1:
        errors.append(f"fixture must see action press or movement: {obs}")
    else:
        labels["action"] = "proven"
        try:
            strength = float(obs.get("last_strength") or 0)
        except (TypeError, ValueError):
            strength = 0.0
        if abs(strength - 0.75) > 0.05:
            errors.append(f"action strength 0.75 must reach the fixture, got last_strength={obs.get('last_strength')!r}")
    if obs.get("held_ui_right") is not True and int(obs.get("held_count") or 0) < 1:
        errors.append(f"held action must stay down until release_all: {obs}")

    req_id, rel_body = tool_call(
        proc, req_id, "godot.input", "release_all", {"scope": "all", "run_id": run_id}, timeout=30.0
    )
    if not ack_ok(rel_body, errors, "input.release_all"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    time.sleep(0.2)
    req_id, after_rel = observe(proc, req_id, run_id)
    if "held_ui_right" not in after_rel and "held_count" not in after_rel:
        errors.append(f"release_all observe missing held keys: {after_rel}")
    elif after_rel.get("held_ui_right") is True or int(after_rel.get("held_count") or 0) != 0:
        errors.append(f"release_all must leave no held actions: {after_rel}")
    else:
        labels["release_all"] = "proven"

    req_id, key_body = tool_call(
        proc,
        req_id,
        "godot.input",
        "key",
        {"keycode": "KEY_A", "phase": "press", "shift": True, "run_id": run_id},
        timeout=30.0,
    )
    req_id, key_b = tool_call(
        proc,
        req_id,
        "godot.input",
        "key",
        {"keycode": "KEY_B", "phase": "press", "run_id": run_id},
        timeout=30.0,
    )
    req_id, click = tool_call(
        proc,
        req_id,
        "godot.input",
        "mouse",
        {"button": "left", "x": 96, "y": 100, "phase": "press", "run_id": run_id},
        timeout=30.0,
    )
    req_id, click_up = tool_call(
        proc,
        req_id,
        "godot.input",
        "mouse",
        {"button": "left", "x": 96, "y": 100, "phase": "release", "run_id": run_id},
        timeout=30.0,
    )
    req_id, wheel = tool_call(
        proc,
        req_id,
        "godot.input",
        "mouse",
        {"button": "none", "x": 80, "y": 40, "wheel": "up", "run_id": run_id},
        timeout=30.0,
    )
    req_id, motion = tool_call(
        proc,
        req_id,
        "godot.input",
        "mouse",
        {"button": "none", "x": 90, "y": 50, "phase": "motion", "dx": 4, "dy": -2, "run_id": run_id},
        timeout=30.0,
    )
    typed_ok = key_body.get("ok") is True or key_b.get("ok") is True
    click_ok = click.get("ok") is True
    if not typed_ok and not click_ok:
        errors.append(f"typing or click fixture must ACK: key={key_body} click={click}")
    req_id, ui_obs = observe(proc, req_id, run_id)
    typed = str(ui_obs.get("typed") or "") + str(ui_obs.get("line_text") or "")
    clicks = int(ui_obs.get("button_clicks") or 0)
    if not typed:
        errors.append(f"LineEdit must receive typed text from Play input, got {ui_obs}")
    if clicks < 1:
        errors.append(f"Button must receive a Play click at its rect, got {ui_obs}")
    if typed and clicks >= 1:
        labels["typing_or_click"] = "proven"
    if ui_obs.get("shift_seen") is not True and key_body.get("ok") is True:
        errors.append(f"shift modifier must be seen by the fixture: {ui_obs}")
    if wheel.get("ok") is not True:
        errors.append(f"input.mouse wheel must ACK: {wheel}")
    elif int(ui_obs.get("wheel_ticks") or 0) < 1:
        errors.append(f"fixture must see wheel, not only injector ACK: {ui_obs}")
    if motion.get("ok") is not True:
        errors.append(f"input.mouse motion must ACK: {motion}")

    req_id, joy = tool_call(
        proc,
        req_id,
        "godot.input",
        "action",
        {"action_name": "ui_accept", "phase": "press", "button_index": 0, "run_id": run_id},
        timeout=30.0,
    )
    req_id, axis = tool_call(
        proc,
        req_id,
        "godot.input",
        "action",
        {"action_name": "ui_right", "phase": "press", "axis": 0, "axis_value": 1.0, "run_id": run_id},
        timeout=30.0,
    )
    req_id, touch = tool_call(
        proc,
        req_id,
        "godot.input",
        "touch",
        {"index": 0, "x": 40, "y": 40, "pressed": True, "run_id": run_id},
        timeout=30.0,
    )
    req_id, joy_obs = observe(proc, req_id, run_id)
    if (
        int(joy_obs.get("joy_buttons") or 0) >= 1
        or int(joy_obs.get("joy_axes") or 0) >= 1
        or int(joy_obs.get("touches") or 0) >= 1
    ):
        labels["joy_touch"] = "proven"
    else:
        errors.append(
            "controller/touch fixture must see joy/touch events, not an injector ACK: "
            f"joy={joy} axis={axis} touch={touch} obs={joy_obs}"
        )

    req_id, seq = tool_call(
        proc,
        req_id,
        "godot.input",
        "sequence",
        {
            "run_id": run_id,
            "steps": [
                {"action_name": "ui_accept", "phase": "press", "delay_ticks": 1},
                {"action_name": "ui_accept", "phase": "release"},
            ],
        },
        timeout=40.0,
    )
    if not ack_ok(seq, errors, "input.sequence"):
        pass

    req_id, _ = tool_call(
        proc, req_id, "godot.input", "release_all", {"scope": "all", "run_id": run_id}, timeout=30.0
    )

    req_id, replay = tool_call(
        proc,
        req_id,
        "godot.input",
        "sequence",
        {
            "run_id": run_id,
            "replay": True,
            "header": {"engine": "not-the-pinned-engine"},
            "steps": [{"action_name": "ui_accept", "phase": "press"}],
        },
        timeout=20.0,
    )
    req_id, empty_replay = tool_call(
        proc,
        req_id,
        "godot.input",
        "sequence",
        {
            "run_id": run_id,
            "replay": True,
            "header": {},
            "steps": [{"action_name": "ui_accept", "phase": "press"}],
        },
        timeout=20.0,
    )
    replay_ok = (
        replay.get("ok") is not True
        and err_code(replay) == "E_CONFLICT"
        and "replay mismatch" in err_msg(replay)
        and empty_replay.get("ok") is not True
        and err_code(empty_replay) == "E_CONFLICT"
        and "replay mismatch" in err_msg(empty_replay)
    )
    if replay.get("ok") is True or empty_replay.get("ok") is True:
        errors.append(f"replay mismatch must not paper-ACK: {replay} empty={empty_replay}")
    elif replay_ok:
        labels["replay"] = "proven"
    else:
        errors.append(f"replay mismatch must be typed E_CONFLICT: {replay} empty={empty_replay}")

    req_id, focus = tool_call(
        proc,
        req_id,
        "godot.input",
        "action",
        {
            "action_name": "ui_accept",
            "phase": "press",
            "run_id": run_id,
            "editor_foreground": True,
        },
        timeout=30.0,
    )
    if err_code(focus) == "E_CONFLICT" and "focus" in err_msg(focus).lower():
        labels["focus_loss"] = "proven"
    elif focus.get("ok") is True:
        labels["focus_loss"] = "Alternative"
    else:
        errors.append(f"focus-loss must be typed fail or honest Alternative, not a random error: {focus}")

    req_id = verify_later_wps(proc, req_id, errors)
    req_id, _ = play_stop(proc, req_id, run_id=run_id)
    time.sleep(0.3)
    errors.extend(project_godot_leak_errors("after play.stop"))
    req_id, after_stop = tool_call(
        proc, req_id, "godot.input", "action", {"action_name": "ui_accept", "phase": "press"}
    )
    if after_stop.get("ok") is True:
        errors.append("play.input must return to E_UNVERIFIED after play.stop")
    if err_code(after_stop) != "E_UNVERIFIED":
        errors.append(f"input after play.stop must be E_UNVERIFIED: {after_stop}")
    proven = (
        labels["action"] == "proven"
        and labels["release_all"] == "proven"
        and labels["typing_or_click"] == "proven"
        and labels["joy_touch"] == "proven"
        and labels["replay"] == "proven"
    )
    return req_id, proven, labels


def live_errors(exe: Path) -> tuple[list[str], str, str, str, dict[str, str]]:
    errors: list[str] = []
    live = "unrun"
    headless_input = "unproven"
    gui_input = "unrun"
    labels = {
        "action": "unproven",
        "typing_or_click": "unproven",
        "release_all": "unproven",
        "focus_loss": "unproven",
        "replay": "unproven",
        "joy_touch": "unproven",
    }
    kill_plugin_project_holders()
    time.sleep(1.0)
    if plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", "unproven", "unrun", labels
    errors.extend(cleanup_temp())
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
            return errors, "failed", "unproven", "unrun", labels
        live = "ran"
        req_id, idle = tool_call(
            proc, req_id, "godot.input", "action", {"action_name": "ui_accept", "phase": "press"}
        )
        if idle.get("ok") is True or err_code(idle) != "E_UNVERIFIED":
            errors.append(f"headless idle input must stay E_UNVERIFIED: {idle}")
        req_id, scene = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_input, gui_input, labels
        req_id, start_body = play_start(proc, req_id, scene)
        playing = start_body.get("ok") is True and after_of(start_body).get("playing") is True
        if playing:
            run_id = str(after_of(start_body).get("run_id") or "")
            time.sleep(1.5)
            req_id, ready, _tree = wait_runtime_ready(proc, req_id, run_id)
            if ready:
                req_id, act = tool_call(
                    proc,
                    req_id,
                    "godot.input",
                    "action",
                    {"action_name": "ui_right", "phase": "press", "run_id": run_id},
                    timeout=30.0,
                )
                req_id, head_obs = observe(proc, req_id, run_id)
                if int(head_obs.get("action_presses") or 0) >= 1 or int(head_obs.get("move_seen") or 0) >= 1:
                    headless_input = "proven"
                else:
                    headless_input = "unproven"
                    # Injector _input on the same node that called parse_input_event
                    # is circular self-seen. Do not stamp proven from ACK seen.
            req_id, _ = play_stop(proc, req_id)
            errors.extend(project_godot_leak_errors("after headless play.stop"))
        elif start_body.get("ok") is True:
            errors.append(f"headless play.start paper-ACK playing=true: {start_body}")
            return errors, live, "unproven", gui_input, labels
        else:
            headless_input = "unproven"
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        kill_plugin_project_holders(godot=True, node=False)
        agent = PLUGIN_PROJECT / ".hh-agent"
        for name in ("file-leases.json", "writer.lock"):
            lock = agent / name
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        time.sleep(1.0)
        if plugin_godot_busy():
            errors.append("exclusive GUI Godot unavailable (plugin-project already held)")
            return errors, live, headless_input, "unrun", labels
        godot, godot_lines = start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_input, "failed", labels
        req_id, suite_ok, labels = verify_input_suite(proc, req_id, errors, scene)
        if suite_ok:
            gui_input = "proven"
        else:
            gui_input = "unproven"
        errors.extend(project_godot_leak_errors("after GUI suite"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live play input failed: {type(exc).__name__}: {exc}")
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
        errors.extend(cleanup_temp())
        errors.extend(project_godot_leak_errors("after suite cleanup"))
    return errors, live, headless_input, gui_input, labels


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    built = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "generate"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge generate failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    for action_id in (
        "input.action",
        "input.key",
        "input.mouse",
        "input.touch",
        "input.sequence",
        "input.release_all",
    ):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.input":
            errors.append(f"actions.json missing {action_id}")
        if spec.get("side_effect") != "external":
            errors.append(f"{action_id} must stay EXTERNAL")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_input = "unproven"
    gui_input = "unrun"
    labels: dict[str, str] = {}
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_input, gui_input, labels = live_errors(exe)
            errors.extend(live_errs)

    errors.extend(project_godot_leak_errors("after official test"))
    errors.extend(cleanup_temp())
    if errors:
        print(
            f"FAIL: play input; LIVE={live}; HEADLESS_INPUT={headless_input}; "
            f"GUI_INPUT={gui_input}; ACTION={labels.get('action', 'unrun')}; "
            f"RELEASE_ALL={labels.get('release_all', 'unrun')}; "
            f"FOCUS={labels.get('focus_loss', 'unrun')}; "
            f"REPLAY={labels.get('replay', 'unrun')}; screenshots={SCREENSHOTS}"
        )
        for item in errors:
            print(f"  - {item}")
        return 1
    print(
        f"PASS: Play-process input + release_all + replay header; "
        f"LIVE={live}; HEADLESS_INPUT={headless_input}; GUI_INPUT={gui_input}; "
        f"ACTION={labels.get('action')}; TYPE_OR_CLICK={labels.get('typing_or_click')}; "
        f"RELEASE_ALL={labels.get('release_all')}; JOY_TOUCH={labels.get('joy_touch')}; "
        f"FOCUS={labels.get('focus_loss')}; REPLAY={labels.get('replay')}; "
        f"screenshots={SCREENSHOTS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
