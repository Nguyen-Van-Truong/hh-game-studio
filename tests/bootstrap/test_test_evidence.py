#!/usr/bin/env python3
"""R6-WP6: Test manifest/runner/evidence bundle.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP6 [ ]; while unticked CURRENT_VALID_WP=R6-WP6; after tick allow R6-WP7+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. No add_autoload_singleton. No eval.
State assertion remains the primary proof. Agent must cite artifacts.

Verify (encoded here; this file is the official harness):
  - idle / no-Play test.run stays E_UNVERIFIED
  - one pass: Play + state assert match + evidence files exist + report cites them
  - logic fail: property/assert mismatch → status=fail, not pass, evidence present
  - visual fail: screenshot compare fail (ColorRect red vs blue) → fail + PNG on disk
  - perf fail: inject_spike / budget → fail + perf artifact
  - crash: Play parse/runtime crash or hang → infra_error or fail with logs
  - timeout: step-until/run timeout → typed fail or infra_error, not pass
  - flaky fixture: fail then pass on retry stays fail/flaky; retry must not
    silently become pass
  - leftover r6w6 / .hh-agent/r6w6 cleanup fails if files remain

Headless capture: proven only if a real run writes evidence; else Alternative.
GUI path must prove the required outcomes when Play is running.
Kill leftover Godot/Node on plugin-project first. One sidecar.
"""

from __future__ import annotations

import hashlib
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
import test_play_input as pin
import test_play_screenshot as shot
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r6w6"
EVIDENCE_DIR = PLUGIN_PROJECT / ".hh-agent" / "r6w6"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
PLAY_ATTACH_SETUP_S = 1.0
VARIANT_SCHEMA = "hh-godot-variant/1"

FIXTURE_SCRIPT = """extends Node2D

signal panel_ready

var physics_ticks: int = 0
var process_ticks: int = 0
var panel_color: String = "pass_red"
var last_signal: String = ""
var last_audio: String = "none"
var ui_w: float = 0.0
var ui_h: float = 0.0
var world_ok: bool = false
var world_hits: int = 0
var signal_emits: int = 0
var spike_ms: int = 0
var last_spike_elapsed_ms: int = 0
var playback_pos: float = 0.0
var audio_frames: int = 0
var phase: float = 0.0
var flaky_ok: bool = false
var never_flag: bool = false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	set_physics_process(true)
	var panel: ColorRect = get_node_or_null("Panel") as ColorRect
	if panel != null:
		panel.position = Vector2(40, 40)
		panel.size = Vector2(256, 256)
		panel.custom_minimum_size = Vector2(256, 256)
		_sync_panel(panel)
	_bind_tone()
	_bind_world()
	_load_flaky()
	if not panel_ready.is_connected(_on_panel_ready):
		panel_ready.connect(_on_panel_ready)
	panel_ready.emit()

func _on_panel_ready() -> void:
	signal_emits += 1
	last_signal = "panel_ready"

func _load_flaky() -> void:
	var path_s: String = "res://r6w6/flaky_token.txt"
	if FileAccess.file_exists(path_s):
		flaky_ok = true
	else:
		flaky_ok = false
		var f: FileAccess = FileAccess.open(path_s, FileAccess.WRITE)
		if f != null:
			f.store_string("seen")
			f.close()

func _bind_tone() -> void:
	var player: AudioStreamPlayer = AudioStreamPlayer.new()
	player.name = "Tone"
	var gen: AudioStreamGenerator = AudioStreamGenerator.new()
	gen.mix_rate = 22050.0
	gen.buffer_length = 0.2
	player.stream = gen
	player.process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(player)
	player.play()
	_fill_tone()

func _bind_world() -> void:
	_add_hit("HitA", Vector2(80, 80))
	_add_hit("HitB", Vector2(80, 80))

func _add_hit(name_s: String, pos: Vector2) -> void:
	var area: Area2D = Area2D.new()
	area.name = name_s
	area.monitoring = true
	area.monitorable = true
	area.position = pos
	var shape_n: CollisionShape2D = CollisionShape2D.new()
	var rect: RectangleShape2D = RectangleShape2D.new()
	rect.size = Vector2(32, 32)
	shape_n.shape = rect
	area.add_child(shape_n)
	add_child(area)

func _physics_process(_delta: float) -> void:
	physics_ticks += 1
	var panel: ColorRect = get_node_or_null("Panel") as ColorRect
	if panel != null:
		_sync_panel(panel)
	var hit: Area2D = get_node_or_null("HitA") as Area2D
	if hit != null:
		world_hits = hit.get_overlapping_areas().size()
		world_ok = world_hits >= 1

func _fill_tone() -> void:
	var tone: AudioStreamPlayer = get_node_or_null("Tone") as AudioStreamPlayer
	if tone == null:
		return
	var pb: AudioStreamGeneratorPlayback = tone.get_stream_playback() as AudioStreamGeneratorPlayback
	if pb == null:
		return
	var pushed: int = 0
	while pb.get_frames_available() > 0:
		var s: float = sin(phase)
		pb.push_frame(Vector2(s, s))
		phase += 0.12
		pushed += 1
	if pushed > 0:
		audio_frames += pushed
		playback_pos = float(audio_frames) / 22050.0
		last_audio = "tone"

func _process(_delta: float) -> void:
	process_ticks += 1
	_fill_tone()
	if spike_ms > 0:
		var start_ms: int = Time.get_ticks_msec()
		var acc: float = 0.0
		while Time.get_ticks_msec() - start_ms < spike_ms:
			acc += sin(acc + 0.1)
		last_spike_elapsed_ms = Time.get_ticks_msec() - start_ms

func _sync_panel(panel: ColorRect) -> void:
	ui_w = panel.size.x
	ui_h = panel.size.y
	var c: Color = panel.color
	if c.r > 0.6 and c.b < 0.4:
		panel_color = "pass_red"
	elif c.b > 0.6 and c.r < 0.4:
		panel_color = "fail_blue"
	else:
		panel_color = "other"

func agent_observe() -> Dictionary:
	return {
		"physics_ticks": physics_ticks,
		"process_ticks": process_ticks,
		"panel_color": panel_color,
		"last_signal": last_signal,
		"last_audio": last_audio,
		"ui_w": ui_w,
		"ui_h": ui_h,
		"world_ok": world_ok,
		"world_hits": world_hits,
		"signal_emits": signal_emits,
		"spike_ms": spike_ms,
		"last_spike_elapsed_ms": last_spike_elapsed_ms,
		"playback_pos": playback_pos,
		"audio_frames": audio_frames,
		"flaky_ok": flaky_ok,
		"never_flag": never_flag,
	}
"""

CRASH_SCRIPT = """extends Node2D

func _ready() -> void:
	print("hh_r6w6_crash")
	OS.crash("hh_r6w6_crash")
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP6 [ ]; while unticked require CURRENT_VALID_WP=R6-WP6."""
    errors: list[str] = []
    current = ""
    wp6 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP6\b", stripped):
            wp6 = stripped
    if wp6 is None:
        return ["plan missing R6-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R6-WP6 heading must keep [ ] until coordinator tick")
        if current != "R6-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP6 while WP6 is unticked)")
    elif not re.match(r"^R6-WP([7-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP7+ after R6-WP6 tick)")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for folder in (TEMP_DIR, EVIDENCE_DIR):
        for _ in range(6):
            if not folder.exists():
                break
            shutil.rmtree(folder, ignore_errors=True)
            time.sleep(0.2)
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file():
                    try:
                        path.unlink()
                    except OSError:
                        pass
            shutil.rmtree(folder, ignore_errors=True)
        if folder.exists():
            leftovers = [p.as_posix() for p in folder.rglob("*")]
            errors.append(f"r6w6 fixture leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    prefix = self_text.split("def src_scan_errors")[0]
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "Alternative" not in self_text:
        errors.append("official test must record headless Alternative honestly")
    if "paper-ACK" not in self_text and "paper" not in self_text:
        errors.append("official test must refuse to paper-ACK test.run")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "flaky" not in self_text.lower():
        errors.append("official test must encode flaky != silent pass")
    if "PASS_CASE" not in self_text or "LOGIC_FAIL" not in self_text:
        errors.append("official test must label PASS_CASE / LOGIC_FAIL")
    if "VISUAL_FAIL" not in self_text or "PERF_FAIL" not in self_text:
        errors.append("official test must label VISUAL_FAIL / PERF_FAIL")
    if "CRASH" not in self_text or "TIMEOUT" not in self_text or "FLAKY" not in self_text:
        errors.append("official test must label CRASH / TIMEOUT / FLAKY")
    if "EVIDENCE" not in self_text:
        errors.append("official test must label EVIDENCE")
    if 'op": "get"' not in self_text and "op': 'get'" not in self_text and '"op": "get"' not in self_text:
        errors.append("official test must fetch a cited artifact with test.evidence get")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "time.sleep(2)" in prefix:
        errors.append("official harness prefix must not use time.sleep(2)")
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
        if "evaluate_" + "expression" in blob:
            errors.append(f"{posix} evaluates expressions")
        if "Expression.new" in blob:
            errors.append(f"{posix} constructs Expression")
        if re.search(r"(?<![A-Za-z_])eval\s*\(", blob):
            errors.append(f"{posix} calls eval(")
        if posix.endswith("plugin.gd") and "add_autoload_singleton(" in blob:
            errors.append("plugin.gd must not call add_autoload_singleton")

    adapter = ADDON / "core" / "hh_test_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_test_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "flaky; retry must not become pass" not in atext:
            errors.append("test adapter must refuse silent flaky pass")
        if "infra_error" not in atext or 'STATUS_FAIL' not in atext:
            errors.append("test adapter must distinguish pass/fail/infra_error")
        if "report.html" not in atext or "evidence_index" not in atext:
            errors.append("test adapter must write HTML/JSON evidence that cites files")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "test.run idle/no-Play must stay E_UNVERIFIED" not in router:
        errors.append("router self-test must keep idle/no-Play test.run E_UNVERIFIED")
    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if 'method == "godot.test" or method == "godot.export"' in reads:
        errors.append("read adapters must not paper-reject godot.test with R2-WP6")
    if "_test_read" not in reads:
        errors.append("read adapters must route test.report/evidence to the test adapter")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function testApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check test apply")
    if "const testFail = testApplyOk" not in execute:
        errors.append("execute.ts must call testApplyOk from apply path")
    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "TEST_APPLY" not in lifecycle or "isTestApply" not in lifecycle:
        errors.append("scene_lifecycle must export TEST_APPLY / isTestApply")
    proven = lifecycle.split("export function isProvenEditorApply")[-1]
    if "isTestApply" in proven.split("{", 1)[-1].split("}", 1)[0]:
        errors.append("isTestApply must NOT be inside isProvenEditorApply")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_autoload_singleton(" in plugin:
        errors.append("plugin.gd must not call add_autoload_singleton")
    if "_hh_test_pending" not in plugin:
        errors.append("plugin.gd must poll test.run pending")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    skip_fn = export_gd.split("func _should_skip", 1)[-1]
    if 'p.contains("/r6w6' not in skip_fn and 'p.contains("r6w6' not in skip_fn:
        errors.append("export _should_skip must contain() r6w6, not a comment needle")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def tool_call(
    proc,
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 60.0,
) -> tuple[int, dict]:
    return pin.tool_call(proc, req_id, method, action, params, timeout)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    return pin.ack_ok(body, errors, verb)


def after_of(body: dict) -> dict:
    return pin.after_of(body)


def err_code(body: dict) -> str:
    return pin.err_code(body)


def err_msg(body: dict) -> str:
    return pin.err_msg(body)


def res_to_disk(res_path: str) -> Path | None:
    path_s = str(res_path or "").replace("\\", "/")
    if path_s.startswith("res://"):
        disk = PLUGIN_PROJECT / path_s[6:]
        if disk.is_file():
            return disk
    if path_s:
        disk = Path(path_s)
        if disk.is_file():
            return disk
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_files(after: dict) -> list[Path]:
    found: list[Path] = []
    for key in ("report_path", "html_path"):
        disk = res_to_disk(str(after.get(key) or ""))
        if disk is not None:
            found.append(disk)
    index = after.get("evidence_index")
    if isinstance(index, list):
        for item in index:
            if not isinstance(item, dict):
                continue
            disk = res_to_disk(str(item.get("uri") or ""))
            if disk is not None:
                found.append(disk)
    return found


def prove_bundle(after: dict, errors: list[str], verb: str, require_play: bool = True) -> bool:
    ok = True
    if require_play and after.get("play_proven") is not True:
        errors.append(f"{verb} missing play_proven: {after}")
        ok = False
    if after.get("invented_hashes") is True:
        errors.append(f"{verb} invented hashes: {after}")
        ok = False
    hashes = after.get("hashes") if isinstance(after.get("hashes"), dict) else {}
    if hashes.get("invented") is True:
        errors.append(f"{verb} hashes.invented: {after}")
        ok = False
    project_godot = PLUGIN_PROJECT / "project.godot"
    got = str(hashes.get("project_hash") or "")
    if project_godot.is_file() and got and got.lower() != sha256_file(project_godot).lower():
        errors.append(f"{verb} project_hash does not match project.godot sha256")
        ok = False
    report = res_to_disk(str(after.get("report_path") or ""))
    html = res_to_disk(str(after.get("html_path") or ""))
    if report is None or report.stat().st_size < 32:
        errors.append(f"{verb} missing report.json on disk: {after}")
        ok = False
    if html is None or html.stat().st_size < 32:
        errors.append(f"{verb} missing report.html on disk: {after}")
        ok = False
    else:
        html_text = html.read_text(encoding="utf-8", errors="replace")
        if "res://" not in html_text and "evidence" not in html_text.lower():
            errors.append(f"{verb} HTML report cites no file URIs: {html}")
            ok = False
        if after.get("status") == "pass" and "NO_FILE_URIS" in html_text:
            errors.append(f"{verb} HTML said pass with no file URIs")
            ok = False
    index = after.get("evidence_index")
    if not isinstance(index, list) or not index:
        errors.append(f"{verb} evidence_index missing: {after}")
        ok = False
    else:
        uri_hits = 0
        for item in index:
            if not isinstance(item, dict):
                continue
            disk = res_to_disk(str(item.get("uri") or ""))
            if disk is not None and disk.stat().st_size >= 1:
                uri_hits += 1
        if uri_hits < 1:
            errors.append(f"{verb} evidence URIs do not exist on disk: {after}")
            ok = False
    return ok


def define_test(proc, req_id: int, name: str, extra: dict, errors: list[str]) -> tuple[int, dict]:
    params = {
        "name": name,
        "steps": ["setup", "run", "assert", "teardown"],
        "suite": "r6w6",
        "scene": "res://r6w6/shot.tscn",
        "mode": "debug",
        "step_frames": 2,
        "teardown_stop": True,
        "flaky_is_not_pass": True,
    }
    params.update(extra)
    req_id, body = tool_call(proc, req_id, "godot.test", "define", params, timeout=30.0)
    if body.get("ok") is not True:
        errors.append(f"test.define {name}: {body}")
    return req_id, body


def run_test(proc, req_id: int, name: str, extra: dict | None = None) -> tuple[int, dict]:
    params = {"name": name}
    if extra:
        params.update(extra)
    return tool_call(proc, req_id, "godot.test", "run", params, timeout=120.0)


def set_panel_color(proc, req_id: int, scene: str, color: dict, errors: list[str]) -> int:
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open before color set: {opened}")
        return req_id
    req_id, body = tool_call(
        proc,
        req_id,
        "godot.property",
        "set",
        {"scene": scene, "node_path": "Fixture/Panel", "property": "color", "value": {"schema": VARIANT_SCHEMA, "type": "Color", "value": color}},
    )
    if not ack_ok(body, errors, "property.set Panel.color"):
        return req_id
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, "scene.save after color")
    return req_id


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str]:
    scene = "res://r6w6/shot.tscn"
    runtime_script = "res://r6w6/runtime.gd"
    fixture_script = "res://r6w6/fixture.gd"
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
        return req_id, scene
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (TEMP_DIR / "runtime.gd").write_text(product, encoding="utf-8")
    (TEMP_DIR / "fixture.gd").write_text(FIXTURE_SCRIPT, encoding="utf-8")
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene
    time.sleep(0.4)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id, scene
    attached: dict = {}
    for _try in range(4):
        req_id, attached = tool_call(
            proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": runtime_script}
        )
        if attached.get("ok") is True:
            break
        time.sleep(0.5)
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
    req_id, panel = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": scene, "parent": "Fixture", "class_name": "ColorRect", "name": "Panel"},
    )
    if not ack_ok(panel, errors, "node.add Panel"):
        return req_id, scene
    req_id = set_panel_color(proc, req_id, scene, {"r": 0.85, "g": 0.12, "b": 0.12, "a": 1}, errors)
    return req_id, scene


def setup_crash_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str]:
    scene = "res://r6w6/crash.tscn"
    runtime_script = "res://r6w6/runtime.gd"
    crash_script = "res://r6w6/crash_fix.gd"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (TEMP_DIR / "crash_fix.gd").write_text(CRASH_SCRIPT, encoding="utf-8")
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create crash"):
        return req_id, scene
    time.sleep(0.3)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open crash: {opened}")
        return req_id, scene
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": runtime_script}
    )
    ack_ok(attached, errors, "script.attach crash runtime")
    req_id, added = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "CrashFix"},
    )
    if ack_ok(added, errors, "node.add CrashFix"):
        req_id, fat = tool_call(
            proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": "CrashFix", "path": crash_script}
        )
        ack_ok(fat, errors, "script.attach CrashFix")
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, "scene.save crash")
    return req_id, scene


def verify_suite(proc, req_id: int, errors: list[str], scene: str) -> tuple[int, dict[str, str]]:
    labels = {
        "PASS_CASE": "unproven",
        "LOGIC_FAIL": "unproven",
        "VISUAL_FAIL": "unproven",
        "PERF_FAIL": "unproven",
        "CRASH": "unproven",
        "TIMEOUT": "unproven",
        "FLAKY": "unproven",
        "EVIDENCE": "unproven",
    }
    req_id, idle = tool_call(proc, req_id, "godot.test", "run", {"name": "idle_missing"})
    if idle.get("ok") is True:
        errors.append(f"test.run must stay E_UNVERIFIED when Play is not running (paper-ACK): {idle}")
    if err_code(idle) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play test.run must be E_UNVERIFIED: {idle}")
    req_id, idle_assert = tool_call(
        proc, req_id, "godot.test", "assert", {"name": "idle_assert", "expect": "true"}
    )
    if idle_assert.get("ok") is True or err_code(idle_assert) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play test.assert must be E_UNVERIFIED: {idle_assert}")
    req_id, implicit = tool_call(
        proc,
        req_id,
        "godot.test",
        "baseline",
        {"name": "panel", "hash": "deadbeefcafebabe"},
    )
    if implicit.get("ok") is True:
        errors.append(f"test.baseline without reviewed must not auto-bless: {implicit}")
    elif "reviewed" not in err_msg(implicit).lower():
        errors.append(f"implicit baseline update must name reviewed action: {implicit}")

    req_id, _ = define_test(
        proc,
        req_id,
        "pass_case",
        {
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "panel_color",
            "assert_op": "eq",
            "assert_value_string": "pass_red",
            "visual_update_baseline": True,
            "visual_reviewed": True,
            "visual_baseline": "panel",
            "visual_compare": False,
        },
        errors,
    )
    req_id, passed = run_test(proc, req_id, "pass_case")
    after_pass = after_of(passed)
    if passed.get("ok") is True and after_pass.get("status") == "pass" and prove_bundle(after_pass, errors, "PASS_CASE"):
        labels["PASS_CASE"] = "proven"
    else:
        errors.append(f"PASS_CASE must be status=pass with evidence: {passed}")

    req_id, start_body = pin.play_start(proc, req_id, scene, mode="debug")
    if start_body.get("ok") is True and after_of(start_body).get("playing") is True:
        run_id = str(after_of(start_body).get("run_id") or "")
        time.sleep(PLAY_ATTACH_SETUP_S)
        req_id, ready, _tree = pin.wait_runtime_ready(proc, req_id, run_id)
        if ready:
            req_id, live_assert = tool_call(
                proc,
                req_id,
                "godot.test",
                "assert",
                {
                    "name": "pass_case",
                    "expect": "pass_red",
                    "kind": "property",
                    "node_path": "Fixture",
                    "key": "panel_color",
                    "op": "eq",
                    "value_string": "pass_red",
                    "run_id": run_id,
                },
                timeout=20.0,
            )
            live_after = after_of(live_assert)
            if live_assert.get("ok") is not True or live_after.get("matched") is not True:
                errors.append(f"live test.assert must match (state assertion primary): {live_assert}")
            elif live_after.get("source") != "hh_agent_runtime":
                errors.append(f"live test.assert must come from hh_agent_runtime: {live_assert}")
        req_id, _ = pin.play_stop(proc, req_id, run_id=run_id)

    req_id, _ = define_test(
        proc,
        req_id,
        "logic_fail",
        {
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "panel_color",
            "assert_op": "eq",
            "assert_value_string": "fail_blue",
        },
        errors,
    )
    req_id, logic = run_test(proc, req_id, "logic_fail")
    after_logic = after_of(logic)
    if logic.get("ok") is True or after_logic.get("status") == "pass":
        errors.append(f"LOGIC_FAIL must not be pass: {logic}")
    elif after_logic.get("status") == "fail" and prove_bundle(after_logic, errors, "LOGIC_FAIL"):
        labels["LOGIC_FAIL"] = "proven"
    else:
        errors.append(f"LOGIC_FAIL must be status=fail with evidence: {logic}")

    req_id = set_panel_color(proc, req_id, scene, {"r": 0.12, "g": 0.18, "b": 0.85, "a": 1}, errors)
    req_id, _ = define_test(
        proc,
        req_id,
        "visual_fail",
        {
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "panel_color",
            "assert_op": "eq",
            "assert_value_string": "fail_blue",
            "visual_compare": True,
            "visual_baseline": "panel",
        },
        errors,
    )
    req_id, visual = run_test(proc, req_id, "visual_fail")
    after_visual = after_of(visual)
    pngs = [p for p in evidence_files(after_visual) if p.suffix.lower() == ".png" and p.stat().st_size >= 200]
    visual_ok = (
        visual.get("ok") is not True
        and after_visual.get("status") == "fail"
        and ("visual" in str(after_visual.get("reason") or "") or "visual" in err_msg(visual).lower())
        and prove_bundle(after_visual, errors, "VISUAL_FAIL")
        and pngs
    )
    if visual_ok:
        fr, _fg, fb, fn = shot.png_region_mean(pngs[0])
        if fn < 1000 or fb <= 0.6 or fr >= 0.4:
            errors.append(f"VISUAL_FAIL PNG region must be blue (python mean): r={fr} b={fb} n={fn} {pngs[0]}")
        else:
            labels["VISUAL_FAIL"] = "proven"
    else:
        errors.append(f"VISUAL_FAIL must be fail + PNG on disk: {visual}")

    req_id = set_panel_color(proc, req_id, scene, {"r": 0.85, "g": 0.12, "b": 0.12, "a": 1}, errors)
    req_id, _ = define_test(
        proc,
        req_id,
        "perf_fail",
        {
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "panel_color",
            "assert_op": "eq",
            "assert_value_string": "pass_red",
            "perf_inject_spike": True,
            "perf_budget_ms": 8,
        },
        errors,
    )
    req_id, perf = run_test(proc, req_id, "perf_fail")
    after_perf = after_of(perf)
    perf_files = [
        p
        for p in evidence_files(after_perf)
        if p.name == "perf.json" or (isinstance(p.suffix, str) and "perf" in p.name)
    ]
    if after_perf.get("status") != "fail" or perf.get("ok") is True:
        errors.append(f"PERF_FAIL must be status=fail, not pass: {perf}")
    elif not prove_bundle(after_perf, errors, "PERF_FAIL"):
        errors.append(f"PERF_FAIL missing evidence: {perf}")
    elif not perf_files and not any(
        isinstance(item, dict) and item.get("kind") == "perf"
        for item in (after_perf.get("evidence_index") or [])
    ):
        errors.append(f"PERF_FAIL missing perf artifact: {perf}")
    else:
        elapsed = float(after_perf.get("fixture_spike_elapsed_ms") or 0)
        for path in perf_files:
            try:
                blob = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(blob, dict):
                elapsed = max(elapsed, float(blob.get("fixture_spike_elapsed_ms") or 0))
        if elapsed < 40.0:
            errors.append(
                f"PERF_FAIL must be the fixture _process spike, not ambient TIME_PROCESS: "
                f"elapsed={elapsed} {perf}"
            )
        else:
            labels["PERF_FAIL"] = "proven"

    req_id, _ = define_test(
        proc,
        req_id,
        "timeout",
        {
            "until_key": "never_flag",
            "until_op": "eq",
            "until_value_bool": True,
            "step_timeout_ms": 2000,
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "never_flag",
            "assert_op": "eq",
            "assert_value_bool": True,
        },
        errors,
    )
    req_id, timed = run_test(proc, req_id, "timeout")
    after_time = after_of(timed)
    timed_status = str(after_time.get("status") or "")
    if timed.get("ok") is True or timed_status == "pass":
        errors.append(f"TIMEOUT must not be pass: {timed}")
    elif timed_status in ("fail", "infra_error") and (
        err_code(timed) == "E_TIMEOUT"
        or "timeout" in str(after_time.get("reason") or "")
        or "timeout" in err_msg(timed).lower()
        or "missed event" in err_msg(timed).lower()
    ):
        if prove_bundle(after_time, errors, "TIMEOUT"):
            labels["TIMEOUT"] = "proven"
        else:
            errors.append(f"TIMEOUT missing evidence: {timed}")
    else:
        errors.append(f"TIMEOUT must be typed fail/infra_error: {timed}")

    token = TEMP_DIR / "flaky_token.txt"
    if token.is_file():
        try:
            token.unlink()
        except OSError:
            pass
    req_id, _ = define_test(
        proc,
        req_id,
        "flaky",
        {
            "retry_max": 1,
            "flaky_is_not_pass": True,
            "assert_kind": "property",
            "assert_node_path": "Fixture",
            "assert_key": "flaky_ok",
            "assert_op": "eq",
            "assert_value_bool": True,
        },
        errors,
    )
    req_id, flaky = run_test(proc, req_id, "flaky")
    after_flaky = after_of(flaky)
    if after_flaky.get("status") == "pass" or flaky.get("ok") is True:
        errors.append(f"FLAKY retry must not silently become pass: {flaky}")
    elif int(after_flaky.get("attempt") or 0) < 2:
        errors.append(f"FLAKY must retry Play at least once (attempt>=2): {flaky}")
    elif after_flaky.get("status") in ("fail", "infra_error") and (
        after_flaky.get("flaky") is True
        or str(after_flaky.get("reason") or "") == "flaky"
        or "flaky" in err_msg(flaky).lower()
    ):
        if prove_bundle(after_flaky, errors, "FLAKY"):
            labels["FLAKY"] = "proven"
        else:
            errors.append(f"FLAKY missing evidence: {flaky}")
    else:
        errors.append(f"FLAKY must stay fail/flaky: {flaky}")

    req_id, crash_scene = setup_crash_scene(proc, req_id, errors)
    req_id, _ = define_test(
        proc,
        req_id,
        "crash",
        {"scene": crash_scene, "steps": ["setup", "run", "teardown"]},
        errors,
    )
    req_id, crashed = run_test(proc, req_id, "crash")
    after_crash = after_of(crashed)
    crash_status = str(after_crash.get("status") or "")
    log_blob = json.dumps(after_crash, default=str).lower()
    if crashed.get("ok") is True or crash_status == "pass":
        errors.append(f"CRASH must not paper pass: {crashed}")
    elif crash_status in ("infra_error", "fail") and (
        str(after_crash.get("reason") or "") in ("crash", "hang")
        or "hh_r6w6_crash" in log_blob
    ):
        if evidence_files(after_crash) or after_crash.get("evidence_index"):
            labels["CRASH"] = "proven"
        else:
            errors.append(f"CRASH must keep logs/evidence: {crashed}")
    else:
        errors.append(f"CRASH must be infra_error or fail with logs: {crashed}")

    req_id, report = tool_call(proc, req_id, "godot.test", "report", {"name": "pass_case"})
    req_id, evidence = tool_call(
        proc, req_id, "godot.test", "evidence", {"name": "pass_case", "op": "list", "retention_hours": 24}
    )
    report_after = after_of(report)
    ev_after = after_of(evidence)
    if report.get("ok") is True and evidence.get("ok") is True:
        if prove_bundle(report_after if report_after.get("evidence_index") else after_pass, errors, "EVIDENCE"):
            if not isinstance(ev_after.get("index"), list) or not ev_after.get("index"):
                errors.append(f"test.evidence list must return file URIs: {evidence}")
            else:
                cite = ""
                for item in ev_after.get("index") or []:
                    if isinstance(item, dict) and str(item.get("uri") or "").endswith(".json"):
                        cite = str(item.get("uri"))
                        break
                if not cite:
                    cite = str((ev_after.get("index") or [{}])[0].get("uri") or "")
                req_id, got = tool_call(
                    proc,
                    req_id,
                    "godot.test",
                    "evidence",
                    {"name": "pass_case", "op": "get", "uri": cite},
                    timeout=20.0,
                )
                got_after = after_of(got)
                disk = res_to_disk(cite)
                if got.get("ok") is not True or int(got_after.get("bytes") or 0) < 1:
                    errors.append(f"test.evidence get must return cited artifact bytes: {got}")
                elif disk is None or sha256_file(disk).lower() != str(got_after.get("hash") or "").lower():
                    errors.append(f"test.evidence get hash must match disk: {got} disk={disk}")
                else:
                    req_id, escaped = tool_call(
                        proc,
                        req_id,
                        "godot.test",
                        "evidence",
                        {"name": "pass_case", "op": "get", "uri": "res://.hh-agent/r6w6/../project.godot"},
                    )
                    if escaped.get("ok") is True or err_code(escaped) != "E_PATH":
                        errors.append(f"test.evidence get must jail .. : {escaped}")
                    else:
                        labels["EVIDENCE"] = "proven"
        else:
            errors.append(f"test.report must cite artifacts: {report}")
    else:
        errors.append(f"test.report/evidence must ACK real files: report={report} evidence={evidence}")

    errors.extend(pin.project_godot_leak_errors("after GUI suite"))
    return req_id, labels


def live_errors(exe: Path) -> tuple[list[str], str, str, str, dict[str, str]]:
    errors: list[str] = []
    live = "unrun"
    headless_pass = "unproven"
    gui_suite = "unrun"
    labels = {
        "PASS_CASE": "unproven",
        "LOGIC_FAIL": "unproven",
        "VISUAL_FAIL": "unproven",
        "PERF_FAIL": "unproven",
        "CRASH": "unproven",
        "TIMEOUT": "unproven",
        "FLAKY": "unproven",
        "EVIDENCE": "unproven",
    }
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
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
        godot, godot_lines = pin.start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed", "unproven", "unrun", labels
        live = "ran"
        req_id, idle = tool_call(proc, req_id, "godot.test", "run", {"name": "idle_missing"})
        if idle.get("ok") is True or err_code(idle) != "E_UNVERIFIED":
            errors.append(f"headless idle test.run must stay E_UNVERIFIED: {idle}")
        req_id, scene = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_pass, gui_suite, labels
        req_id, _ = define_test(
            proc,
            req_id,
            "pass_case",
            {
                "assert_kind": "property",
                "assert_node_path": "Fixture",
                "assert_key": "panel_color",
                "assert_op": "eq",
                "assert_value_string": "pass_red",
            },
            errors,
        )
        req_id, passed = run_test(proc, req_id, "pass_case")
        after = after_of(passed)
        if (
            passed.get("ok") is True
            and after.get("status") == "pass"
            and after.get("play_proven") is True
            and evidence_files(after)
        ):
            headless_pass = "proven"
        elif passed.get("ok") is True and after.get("status") == "pass" and after.get("play_proven") is not True:
            errors.append(f"headless test.run paper-ACK without Play: {passed}")
            headless_pass = "unproven"
        else:
            headless_pass = "Alternative"
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        pin.kill_plugin_project_holders(godot=True, node=False)
        agent = PLUGIN_PROJECT / ".hh-agent"
        for name in ("file-leases.json", "writer.lock"):
            lock = agent / name
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        time.sleep(1.0)
        if pin.plugin_godot_busy():
            errors.append("exclusive GUI Godot unavailable (plugin-project already held)")
            return errors, live, headless_pass, "unrun", labels
        godot, godot_lines = pin.start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_pass, "failed", labels
        req_id, labels = verify_suite(proc, req_id, errors, scene)
        required = ("PASS_CASE", "LOGIC_FAIL", "VISUAL_FAIL", "PERF_FAIL", "CRASH", "TIMEOUT", "FLAKY", "EVIDENCE")
        if all(labels.get(key) == "proven" for key in required):
            gui_suite = "proven"
        else:
            gui_suite = "unproven"
        errors.extend(pin.project_godot_leak_errors("after GUI suite"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live test evidence failed: {type(exc).__name__}: {exc}")
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
        errors.extend(pin.project_godot_leak_errors("after suite cleanup"))
    return errors, live, headless_pass, gui_suite, labels


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
    for action_id in ("test.define", "test.run", "test.assert", "test.report", "test.evidence", "test.baseline"):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.test":
            errors.append(f"actions.json missing {action_id}")
    if (actions.get("test.run") or {}).get("side_effect") != "external":
        errors.append("test.run must be EXTERNAL apply")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_pass = "unproven"
    gui_suite = "unrun"
    labels: dict[str, str] = {}
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_pass, gui_suite, labels = live_errors(exe)
            errors.extend(live_errs)

    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.0)
    errors.extend(cleanup_temp())
    if TEMP_DIR.exists() or EVIDENCE_DIR.exists():
        leftovers = []
        if TEMP_DIR.exists():
            leftovers.extend(p.as_posix() for p in TEMP_DIR.rglob("*") if p.is_file())
        if EVIDENCE_DIR.exists():
            leftovers.extend(p.as_posix() for p in EVIDENCE_DIR.rglob("*") if p.is_file())
        if leftovers:
            errors.append(f"r6w6 leftover after second cleanup: {leftovers[:8]}")
    banner = (
        f"LIVE={live}; HEADLESS_PASS={headless_pass}; GUI_SUITE={gui_suite}; "
        f"PASS_CASE={labels.get('PASS_CASE', 'unrun')}; LOGIC_FAIL={labels.get('LOGIC_FAIL', 'unrun')}; "
        f"VISUAL_FAIL={labels.get('VISUAL_FAIL', 'unrun')}; PERF_FAIL={labels.get('PERF_FAIL', 'unrun')}; "
        f"CRASH={labels.get('CRASH', 'unrun')}; TIMEOUT={labels.get('TIMEOUT', 'unrun')}; "
        f"FLAKY={labels.get('FLAKY', 'unrun')}; EVIDENCE={labels.get('EVIDENCE', 'unrun')}"
    )
    if errors:
        print(f"FAIL: test evidence; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: test manifest/runner/evidence bundle; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
