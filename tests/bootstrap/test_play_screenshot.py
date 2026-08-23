#!/usr/bin/env python3
"""R6-WP5: Play-process screenshot, visual diff, state assertions, perf.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP5 [ ]; while unticked CURRENT_VALID_WP=R6-WP5; after tick allow R6-WP6+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. No desktop OS inject / pixel RPA. No eval.
No add_autoload_singleton. State assertion remains the primary proof.

Verify (encoded here; this file is the official harness):
  - idle / no-Play screenshot+perf stay E_UNVERIFIED
  - Play + product runtime: screenshot ACK with a real file under project
    (.hh-agent/ or r6w5), not a repo-checked dummy
  - wait stable uses freeze/step or frame counters, not sleep 2s
  - seeded intentional visual PASS and FAIL (ColorRect color change)
  - GPU mask/tolerance path (do not claim bit-exact)
  - missing baseline → typed fail, never auto-bless
  - explicit reviewed baseline update (not implicit)
  - state assertion required for the suite proven label
  - perf: counters + hardware manifest; seeded spike exceeds budget → fail
  - if a monitor is unavailable, Alternative, not an invented number
  - screenshot/perf after play.stop → E_UNVERIFIED
  - leftover r6w5 cleanup fails if files remain

Headless capture: proven only if a real blit exists; else Alternative.
GUI path must prove a real viewport capture when Play is running.
Kill leftover Godot/Node on plugin-project first. One sidecar.
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
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r6w5"
SHOT_DIR = PLUGIN_PROJECT / ".hh-agent" / "r6w5"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
MAX_PAGE = 100
SEED = 4242
PLAY_ATTACH_SETUP_S = 1.0
VARIANT_SCHEMA = "hh-godot-variant/1"
BASELINE = "panel"
MISSING_BASELINE = "missing_panel"

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
	if not panel_ready.is_connected(_on_panel_ready):
		panel_ready.connect(_on_panel_ready)
	panel_ready.emit()

func _on_panel_ready() -> void:
	signal_emits += 1
	last_signal = "panel_ready"

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
	}
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP5 [ ]; while unticked require CURRENT_VALID_WP=R6-WP5."""
    errors: list[str] = []
    current = ""
    wp5 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP5\b", stripped):
            wp5 = stripped
    if wp5 is None:
        return ["plan missing R6-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R6-WP5 heading must keep [ ] until coordinator tick")
        if current != "R6-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP5 while WP5 is unticked)")
    elif not re.match(r"^R6-WP([6-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP6+ after R6-WP5 tick)")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for folder in (TEMP_DIR, SHOT_DIR):
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
            errors.append(f"r6w5 fixture leftover after cleanup: {leftovers[:8]}")
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
        errors.append("official test must record headless/CPU Alternative honestly")
    if "paper-ACK" not in self_text and "paper" not in self_text:
        errors.append("official test must refuse to paper-ACK editor-only blit")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "sleep 2s" not in self_text and "sleep 2" not in self_text:
        errors.append("official test must refuse sleep-2s observation")
    if "missing baseline" not in self_text:
        errors.append("official test must encode missing baseline fail")
    if "reviewed" not in self_text:
        errors.append("official test must encode explicit reviewed baseline update")
    if "state assertion" not in self_text.lower() and "STATE" not in self_text:
        errors.append("official test must keep state assertion as primary proof")
    if "bit-exact" not in self_text and "bit_exact" not in self_text:
        errors.append("official test must refuse bit-exact cross-GPU claims")
    if "png_region_mean" not in self_text or "Image.open" not in self_text:
        errors.append("official test must decode screenshot PNG pixels itself")
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

    runtime_gd = PRODUCT_RUNTIME
    if not runtime_gd.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    else:
        rtext = runtime_gd.read_text(encoding="utf-8")
        if "_viewport_image" not in rtext or "_wait_stable" not in rtext:
            errors.append("product runtime must own viewport capture + wait-stable frames")
        if "_diff_images" not in rtext or "_perf_async" not in rtext or "_assert_op" not in rtext:
            errors.append("product runtime must own diff / perf / assert")
        if "Engine" + "Debugger" not in rtext:
            errors.append("game-side autoload must use debugger send_message")
        if "used_sleep" not in rtext:
            errors.append("wait-stable must record that it did not sleep")
        if "bit_exact" not in rtext:
            errors.append("product runtime must refuse bit-exact claims")
        if "missing baseline" not in rtext:
            errors.append("product runtime must fail missing baseline")
        if "reviewed action" not in rtext:
            errors.append("product runtime must require reviewed baseline update")

    adapter = ADDON / "core" / "hh_runtime_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_runtime_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "begin_capture" not in atext:
            errors.append("runtime adapter must own begin_capture")
        if "Engine" + "Debugger" in atext:
            errors.append("do not use the game-side debugger singleton in the editor runtime adapter")
        if ("Send" + "Input") in atext:
            errors.append("runtime adapter must not call a desktop inject API")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "_capture_apply" not in router:
        errors.append("router must dispatch screenshot/perf when Play can be proven")
    if "runtime screenshot/perf idle must stay E_UNVERIFIED" not in router:
        errors.append("router self-test must keep idle/no-Play screenshot/perf E_UNVERIFIED")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "runtime screenshot/perf must use Play capture apply" not in reads:
        errors.append("read adapters must not paper-ACK screenshot/perf")

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
    if "function runtimeApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check runtime apply")
    if "const runtimeFail = runtimeApplyOk" not in execute:
        errors.append("execute.ts must call runtimeApplyOk from apply path")
    if "screenshot_artifact_present" not in execute or "perf_counters_present" not in execute:
        errors.append("execute.ts must check screenshot/perf apply postconditions")
    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "runtime.screenshot" not in lifecycle or "runtime.perf" not in lifecycle:
        errors.append("scene_lifecycle RUNTIME_APPLY must include screenshot/perf")
    proven = lifecycle.split("export function isProvenEditorApply")[-1]
    if "isRuntimeApply" in proven.split("{", 1)[-1].split("}", 1)[0]:
        errors.append("isRuntimeApply must NOT be inside isProvenEditorApply")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_autoload_singleton(" in plugin:
        errors.append("plugin.gd must not call add_autoload_singleton")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if "func _should_skip" not in export_gd or "skip()" not in export_gd:
        errors.append("export plugin must call skip() from _should_skip")
    skip_fn = export_gd.split("func _should_skip", 1)[-1]
    for needle in ("r6w5", "hh_agent_runtime", "addons/hh_agent", ".hh-agent"):
        if needle not in skip_fn:
            errors.append(f"export _should_skip must match {needle}")
    if 'p.contains("/r6w5' not in skip_fn and 'p.contains("r6w5' not in skip_fn:
        errors.append("export _should_skip must contain() r6w5, not a comment needle")

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


def variant(typ: str, value) -> dict:
    return {"schema": VARIANT_SCHEMA, "type": typ, "value": value}


def write_script_retry(proc, req_id: int, path: str, contents: str, errors: list[str]) -> int:
    last: dict = {}
    for attempt in range(3):
        req_id, last = tool_call(
            proc, req_id, "godot.script", "write", {"path": path, "contents": contents}, timeout=90.0
        )
        if last.get("ok") is True:
            return req_id
        if err_code(last) != "E_BUSY":
            break
        time.sleep(1.0)
    ack_ok(last, errors, f"script.write {path}")
    return req_id


def play_start(proc, req_id: int, scene: str, mode: str = "debug") -> tuple[int, dict]:
    return pin.play_start(proc, req_id, scene, mode)


def play_stop(proc, req_id: int, reason: str = "test", run_id: str | None = None) -> tuple[int, dict]:
    return pin.play_stop(proc, req_id, reason, run_id)


def wait_runtime_ready(proc, req_id: int, run_id: str) -> tuple[int, bool, dict]:
    return pin.wait_runtime_ready(proc, req_id, run_id)


def png_region_mean(
    path: Path, x: int = 40, y: int = 40, w: int = 256, h: int = 256
) -> tuple[float, float, float, int]:
    """Critic-owned pixel mean of the ColorRect region. Not the product stamp."""
    from PIL import Image
    from PIL import ImageStat

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        x1 = min(x + w, rgb.width)
        y1 = min(y + h, rgb.height)
        if x1 <= x or y1 <= y:
            return 0.0, 0.0, 0.0, 0
        crop = rgb.crop((x, y, x1, y1))
        n = crop.size[0] * crop.size[1]
        if n < 1:
            return 0.0, 0.0, 0.0, 0
        mean = ImageStat.Stat(crop).mean
    return float(mean[0]) / 255.0, float(mean[1]) / 255.0, float(mean[2]) / 255.0, n


def artifact_on_disk(after: dict) -> Path | None:
    path_s = str(after.get("path") or "").replace("\\", "/")
    if not path_s:
        return None
    if path_s.startswith("res://"):
        rel_p = path_s[6:]
        disk = PLUGIN_PROJECT / rel_p
        if disk.is_file() and disk.stat().st_size >= 200:
            return disk
    abs_s = str(after.get("abs_path") or "")
    if abs_s:
        disk = Path(abs_s)
        if disk.is_file() and disk.stat().st_size >= 200:
            return disk
    return None


def prove_shot_ack(body: dict, errors: list[str], verb: str) -> bool:
    if not ack_ok(body, errors, verb):
        return False
    after = after_of(body)
    if after.get("source") != "hh_agent_runtime":
        errors.append(f"{verb} must come from Play hh_agent_runtime: {body}")
        return False
    if after.get("is_playing_scene") is not True or after.get("playing") is not True:
        errors.append(f"{verb} ACK requires proven Play: {body}")
        return False
    if after.get("dummy") is True:
        errors.append(f"{verb} paper-ACK dummy PNG: {body}")
        return False
    if after.get("screenshot_artifact_present") is not True:
        errors.append(f"{verb} missing screenshot_artifact_present: {body}")
        return False
    disk = artifact_on_disk(after)
    if disk is None:
        errors.append(f"{verb} ACK without a real project file: {body}")
        return False
    if after.get("bit_exact") is True:
        errors.append(f"{verb} must not claim bit-exact: {body}")
        return False
    if int(after.get("width") or 0) < 16 or int(after.get("height") or 0) < 16:
        errors.append(f"{verb} blit is too small to be a Play viewport: {body}")
        return False
    if len(str(after.get("hash") or "")) < 32:
        errors.append(f"{verb} ACK missing capture hash: {body}")
        return False
    span = after.get("luminance_span")
    if not isinstance(span, (int, float)) or float(span) <= 0.05:
        errors.append(f"{verb} blit has no luminance span (flat/dummy viewport): {body}")
        return False
    return True


def observe(proc, req_id: int, run_id: str) -> tuple[int, dict]:
    for path in ("Fixture", "/root/shot/Fixture"):
        req_id, node_body = tool_call(
            proc, req_id, "godot.runtime", "node", {"node_path": path, "run_id": run_id}, timeout=20.0
        )
        after = after_of(node_body)
        obs = after.get("observe")
        if isinstance(obs, dict) and "panel_color" in obs:
            return req_id, obs
        props = after.get("properties")
        if isinstance(props, dict) and "panel_color" in props:
            merged = dict(props)
            if isinstance(obs, dict):
                merged.update(obs)
            return req_id, merged
    return req_id, {}


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
        {"scene": scene, "node_path": "Fixture/Panel", "property": "color", "value": variant("Color", color)},
    )
    if not ack_ok(body, errors, "property.set Panel.color"):
        return req_id
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, "scene.save after color")
    return req_id


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str]:
    scene = "res://r6w5/shot.tscn"
    runtime_script = "res://r6w5/runtime.gd"
    fixture_script = "res://r6w5/fixture.gd"
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
        return req_id, scene
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    if "_viewport_image" not in product or "_assert_op" not in product:
        errors.append("product runtime script must own screenshot/assert")
        return req_id, scene
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    (TEMP_DIR / "runtime.gd").write_text(product, encoding="utf-8")
    (TEMP_DIR / "fixture.gd").write_text(FIXTURE_SCRIPT, encoding="utf-8")
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene
    on_disk = (TEMP_DIR / "runtime.gd").read_text(encoding="utf-8").replace("\r\n", "\n")
    if on_disk != product.replace("\r\n", "\n"):
        errors.append("r6w5/runtime.gd is not PRODUCT_RUNTIME.read_text")
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
    req_id = set_panel_color(
        proc, req_id, scene, {"r": 0.85, "g": 0.12, "b": 0.12, "a": 1}, errors
    )
    return req_id, scene


def freeze_call(proc, req_id: int, run_id: str) -> tuple[int, dict]:
    return tool_call(
        proc,
        req_id,
        "godot.runtime",
        "freeze",
        {"frozen": True, "reason": "test", "seed": SEED, "physics_ticks": 60, "frame": 0, "run_id": run_id},
        timeout=40.0,
    )


def shot_params(run_id: str, extra: dict | None = None) -> dict:
    params = {
        "scale": 1,
        "target": "game",
        "stable_frames": 2,
        "region_x": 40,
        "region_y": 40,
        "region_w": 256,
        "region_h": 256,
        "mask_x": 40,
        "mask_y": 40,
        "mask_w": 8,
        "mask_h": 8,
        "tolerance": 0.12,
        "run_id": run_id,
    }
    if extra:
        params.update(extra)
    return params


def run_state_asserts(proc, req_id: int, run_id: str, errors: list[str], expect_color: str) -> tuple[int, bool]:
    """State assertion is the primary proof. Screenshot is supporting evidence."""
    ok = True
    req_id, obs = observe(proc, req_id, run_id)
    if obs.get("panel_color") != expect_color:
        errors.append(f"fixture agent_observe panel_color expected {expect_color}: {obs}")
        ok = False
    if int(obs.get("signal_emits") or 0) < 1 or obs.get("last_signal") != "panel_ready":
        errors.append(f"fixture must have emitted panel_ready, not listed-only: {obs}")
        ok = False
    if obs.get("last_audio") != "tone" or int(obs.get("audio_frames") or 0) < 64:
        errors.append(f"fixture audio must push generator frames, not a playing flag: {obs}")
        ok = False
    if int(obs.get("world_hits") or 0) < 1:
        errors.append(f"fixture Area2D overlap must be a real world hit: {obs}")
        ok = False
    for kind, params, label in (
        ("tree", {"kind": "tree", "node_path": "Fixture", "run_id": run_id}, "tree"),
        (
            "property",
            {
                "kind": "property",
                "node_path": "Fixture",
                "key": "panel_color",
                "op": "eq",
                "value_string": expect_color,
                "run_id": run_id,
            },
            "property",
        ),
        (
            "signal",
            {
                "kind": "signal",
                "node_path": "Fixture",
                "signal": "panel_ready",
                "value_int": 1,
                "run_id": run_id,
            },
            "signal",
        ),
        (
            "ui_layout",
            {"kind": "ui_layout", "node_path": "Fixture", "value_int": 256, "run_id": run_id},
            "ui_layout",
        ),
        (
            "audio_event",
            {
                "kind": "audio_event",
                "node_path": "Fixture",
                "key": "last_audio",
                "value_string": "tone",
                "run_id": run_id,
            },
            "audio_event",
        ),
        (
            "world",
            {
                "kind": "world",
                "node_path": "Fixture",
                "key": "world_hits",
                "op": "gte",
                "value_int": 1,
                "run_id": run_id,
            },
            "world",
        ),
    ):
        req_id, body = tool_call(proc, req_id, "godot.runtime", "assert", params, timeout=20.0)
        after = after_of(body)
        if body.get("ok") is not True or after.get("matched") is not True:
            errors.append(f"runtime.assert {label} must match (state assertion primary): {body}")
            ok = False
        if after.get("source") != "hh_agent_runtime":
            errors.append(f"runtime.assert {kind} must come from hh_agent_runtime: {body}")
            ok = False
        if kind == "signal" and int(after.get("emitted") or 0) < 1:
            errors.append(f"runtime.assert signal must prove emit, not list-only: {body}")
            ok = False
        if kind == "audio_event" and int(after.get("audio_frames") or 0) < 64:
            errors.append(f"runtime.assert audio must see generator frames, not .playing: {body}")
            ok = False
        if kind == "world" and int(after.get("world_hits") or 0) < 1:
            errors.append(f"runtime.assert world must see Area2D overlap hits: {body}")
            ok = False
    return req_id, ok


def start_play(proc, req_id: int, scene: str, errors: list[str]) -> tuple[int, str, bool]:
    req_id, start_body = play_start(proc, req_id, scene, mode="debug")
    if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
        errors.append(f"play.start must ACK with playing=true after proven Play: {start_body}")
        return req_id, "", False
    run_id = str(after_of(start_body).get("run_id") or "")
    if len(run_id) != 26:
        errors.append(f"play.start must mint run_id: {start_body}")
        return req_id, run_id, False
    time.sleep(PLAY_ATTACH_SETUP_S)
    req_id, ready, tree_body = wait_runtime_ready(proc, req_id, run_id)
    if not ready:
        errors.append(f"runtime.tree must ACK from hh_agent_runtime before capture: {tree_body}")
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, run_id, False
    req_id, fr = freeze_call(proc, req_id, run_id)
    if fr.get("ok") is not True:
        errors.append(f"runtime.freeze before capture must ACK: {fr}")
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, run_id, False
    req_id, st = tool_call(
        proc, req_id, "godot.runtime", "step", {"frames": 2, "run_id": run_id}, timeout=40.0
    )
    if st.get("ok") is not True:
        errors.append(f"runtime.step before capture must ACK: {st}")
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, run_id, False
    return req_id, run_id, True


def verify_shot_suite(
    proc, req_id: int, errors: list[str], scene: str
) -> tuple[int, bool, dict[str, str]]:
    labels = {
        "diff": "unproven",
        "missing_baseline": "unproven",
        "state": "unproven",
        "perf": "unproven",
        "cpu": "Alternative",
    }
    req_id, idle = tool_call(proc, req_id, "godot.runtime", "screenshot", {"scale": 1})
    if idle.get("ok") is True:
        errors.append("runtime.screenshot must stay E_UNVERIFIED when Play is not running (paper-ACK)")
    if err_code(idle) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play screenshot must be E_UNVERIFIED: {idle}")
    req_id, idle_perf = tool_call(proc, req_id, "godot.runtime", "perf", {"detail": "short"})
    if idle_perf.get("ok") is True or err_code(idle_perf) != "E_UNVERIFIED":
        errors.append(f"idle/no-Play perf must be E_UNVERIFIED: {idle_perf}")

    req_id, run_id, ready = start_play(proc, req_id, scene, errors)
    if not ready:
        return req_id, False, labels

    req_id, state_ok = run_state_asserts(proc, req_id, run_id, errors, "pass_red")
    if state_ok:
        labels["state"] = "proven"

    req_id, implicit = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "screenshot",
        shot_params(run_id, {"update_baseline": True, "baseline": BASELINE}),
        timeout=40.0,
    )
    if implicit.get("ok") is True:
        errors.append(f"baseline update without reviewed must not auto-bless: {implicit}")
    elif "reviewed" not in err_msg(implicit).lower():
        errors.append(f"implicit baseline update must name reviewed action: {implicit}")

    req_id, missing = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "screenshot",
        shot_params(run_id, {"compare": True, "baseline": MISSING_BASELINE}),
        timeout=40.0,
    )
    if missing.get("ok") is True:
        errors.append(f"missing baseline must FAIL, never auto-bless: {missing}")
    elif err_code(missing) != "E_UNVERIFIED":
        errors.append(f"missing baseline must be typed E_UNVERIFIED: {missing}")
    elif "missing baseline" not in err_msg(missing).lower():
        errors.append(f"missing baseline fail must name missing baseline: {missing}")
    else:
        labels["missing_baseline"] = "proven"

    req_id, bless = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "screenshot",
        shot_params(run_id, {"update_baseline": True, "reviewed": True, "baseline": BASELINE}),
        timeout=40.0,
    )
    if not prove_shot_ack(bless, errors, "runtime.screenshot baseline update"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    if after_of(bless).get("baseline_updated") is not True or after_of(bless).get("reviewed") is not True:
        errors.append(f"explicit reviewed baseline update must stamp baseline_updated: {bless}")

    req_id, passed = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "screenshot",
        shot_params(run_id, {"compare": True, "baseline": BASELINE}),
        timeout=40.0,
    )
    if not prove_shot_ack(passed, errors, "runtime.screenshot visual PASS"):
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        return req_id, False, labels
    if after_of(passed).get("visual_pass") is not True:
        errors.append(f"seeded visual PASS must set visual_pass: {passed}")
    if float(after_of(passed).get("region_mean_r") or 0) <= 0.6:
        errors.append(f"seeded visual PASS must see red ColorRect pixels in region: {passed}")
    pass_disk = artifact_on_disk(after_of(passed))
    if pass_disk is None:
        errors.append(f"seeded visual PASS missing PNG on disk: {passed}")
    else:
        pr, _pg, pb, pn = png_region_mean(pass_disk)
        if pn < 1000 or pr <= 0.6 or pb >= 0.4:
            errors.append(
                f"seeded visual PASS PNG region must be red (python mean): "
                f"r={pr} b={pb} n={pn} {pass_disk}"
            )

    req_id, perf_ok = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "perf",
        {"detail": "short", "warmup_frames": 4, "samples": 8, "run_id": run_id},
        timeout=40.0,
    )
    after_perf = after_of(perf_ok)
    counters_ok = (
        perf_ok.get("ok") is True
        and after_perf.get("perf_counters_present") is True
        and isinstance(after_perf.get("hardware_manifest"), dict)
        and after_perf.get("source") == "hh_agent_runtime"
    )
    if not counters_ok:
        errors.append(f"runtime.perf must ACK counters + hardware manifest: {perf_ok}")
    p95 = after_perf.get("p95_process_ms")
    if isinstance(p95, dict) and p95.get("status") == "Alternative":
        labels["cpu"] = "Alternative"
    unspiked = after_perf.get("spike") if isinstance(after_perf.get("spike"), dict) else {}
    unspiked_ms = float(unspiked.get("value") or 0)
    unspiked_elapsed = float(after_perf.get("fixture_spike_elapsed_ms") or 0)

    req_id, spike = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "perf",
        {
            "detail": "short",
            "warmup_frames": 1,
            "samples": 6,
            "budget_ms": 8,
            "inject_spike": True,
            "run_id": run_id,
        },
        timeout=40.0,
    )
    spiked = after_of(spike).get("spike") if isinstance(after_of(spike).get("spike"), dict) else {}
    spiked_ms = float(spiked.get("value") or 0)
    spiked_elapsed = float(after_of(spike).get("fixture_spike_elapsed_ms") or 0)
    if unspiked_elapsed != 0.0:
        errors.append(
            f"unspiked perf must not run the fixture loop: elapsed={unspiked_elapsed} {perf_ok}"
        )
    elif spike.get("ok") is True:
        errors.append(f"seeded fixture-loop spike must fail the budget (regression): {spike}")
    elif "perf regression" not in err_msg(spike).lower():
        errors.append(f"seeded spike must be a typed perf regression: {spike}")
    elif spiked_elapsed < 40.0:
        errors.append(
            f"perf regression must be the fixture _process spike, not ambient TIME_PROCESS: "
            f"unspiked_ms={unspiked_ms} spiked_ms={spiked_ms} "
            f"unspiked_elapsed={unspiked_elapsed} spiked_elapsed={spiked_elapsed} {spike}"
        )
    elif counters_ok:
        labels["perf"] = "proven"

    req_id, _ = play_stop(proc, req_id, run_id=run_id)
    time.sleep(0.3)
    req_id = set_panel_color(proc, req_id, scene, {"r": 0.12, "g": 0.18, "b": 0.85, "a": 1}, errors)
    req_id, run_id, ready = start_play(proc, req_id, scene, errors)
    if not ready:
        return req_id, False, labels
    req_id, failed = tool_call(
        proc,
        req_id,
        "godot.runtime",
        "screenshot",
        shot_params(run_id, {"compare": True, "baseline": BASELINE}),
        timeout=40.0,
    )
    if failed.get("ok") is True:
        errors.append(f"seeded visual FAIL must not paper-ACK: {failed}")
    elif "visual diff failed" not in err_msg(failed).lower():
        errors.append(f"seeded visual FAIL must name visual diff: {failed}")
    elif float(after_of(failed).get("region_mean_b") or 0) <= 0.6:
        errors.append(f"seeded visual FAIL must see blue ColorRect pixels in region: {failed}")
    else:
        fail_disk = artifact_on_disk(after_of(failed))
        if fail_disk is None:
            errors.append(f"seeded visual FAIL missing PNG on disk: {failed}")
        else:
            fr, _fg, fb, fn = png_region_mean(fail_disk)
            if fn < 1000 or fb <= 0.6 or fr >= 0.4:
                errors.append(
                    f"seeded visual FAIL PNG region must be blue (python mean): "
                    f"r={fr} b={fb} n={fn} {fail_disk}"
                )
            else:
                labels["diff"] = "proven"

    req_id, _ = play_stop(proc, req_id, run_id=run_id)
    time.sleep(0.3)
    errors.extend(pin.project_godot_leak_errors("after play.stop"))
    req_id, after_stop = tool_call(proc, req_id, "godot.runtime", "screenshot", {"scale": 1})
    if after_stop.get("ok") is True:
        errors.append("runtime.screenshot must return to E_UNVERIFIED after play.stop")
    if err_code(after_stop) != "E_UNVERIFIED":
        errors.append(f"screenshot after play.stop must be E_UNVERIFIED: {after_stop}")
    req_id, after_perf_stop = tool_call(proc, req_id, "godot.runtime", "perf", {"detail": "short"})
    if after_perf_stop.get("ok") is True or err_code(after_perf_stop) != "E_UNVERIFIED":
        errors.append(f"perf after play.stop must be E_UNVERIFIED: {after_perf_stop}")

    proven = (
        labels["state"] == "proven"
        and labels["missing_baseline"] == "proven"
        and labels["diff"] == "proven"
        and labels["perf"] == "proven"
    )
    if labels["diff"] == "proven" and labels["state"] != "proven":
        errors.append("screenshot-only pass without a state assertion is paper for DoD")
        proven = False
    return req_id, proven, labels


def live_errors(exe: Path) -> tuple[list[str], str, str, str, dict[str, str]]:
    errors: list[str] = []
    live = "unrun"
    headless_shot = "unproven"
    gui_shot = "unrun"
    labels = {
        "diff": "unproven",
        "missing_baseline": "unproven",
        "state": "unproven",
        "perf": "unproven",
        "cpu": "Alternative",
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
        req_id, idle = tool_call(proc, req_id, "godot.runtime", "screenshot", {"scale": 1})
        if idle.get("ok") is True or err_code(idle) != "E_UNVERIFIED":
            errors.append(f"headless idle screenshot must stay E_UNVERIFIED: {idle}")
        req_id, scene = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_shot, gui_shot, labels
        req_id, start_body = play_start(proc, req_id, scene)
        playing = start_body.get("ok") is True and after_of(start_body).get("playing") is True
        if playing:
            run_id = str(after_of(start_body).get("run_id") or "")
            time.sleep(PLAY_ATTACH_SETUP_S)
            req_id, ready, _tree = wait_runtime_ready(proc, req_id, run_id)
            if ready:
                req_id, fr = freeze_call(proc, req_id, run_id)
                req_id, st = tool_call(
                    proc, req_id, "godot.runtime", "step", {"frames": 2, "run_id": run_id}, timeout=40.0
                )
                req_id, shot = tool_call(
                    proc,
                    req_id,
                    "godot.runtime",
                    "screenshot",
                    shot_params(run_id),
                    timeout=40.0,
                )
                after = after_of(shot)
                disk = artifact_on_disk(after) if shot.get("ok") is True else None
                req_id, obs = observe(proc, req_id, run_id)
                span = after.get("luminance_span")
                py_r = py_b = 0.0
                py_n = 0
                if disk is not None:
                    py_r, _py_g, py_b, py_n = png_region_mean(disk)
                real_blit = (
                    shot.get("ok") is True
                    and after.get("source") == "hh_agent_runtime"
                    and after.get("screenshot_artifact_present") is True
                    and disk is not None
                    and fr.get("ok") is True
                    and st.get("ok") is True
                    and int(after.get("width") or 0) >= 16
                    and int(after.get("height") or 0) >= 16
                    and len(str(after.get("hash") or "")) >= 32
                    and isinstance(span, (int, float))
                    and float(span) > 0.05
                    and float(after.get("region_mean_r") or 0) > 0.6
                    and float(after.get("region_mean_b") or 1) < 0.4
                    and py_n >= 1000
                    and py_r > 0.6
                    and py_b < 0.4
                    and obs.get("panel_color") == "pass_red"
                )
                if real_blit:
                    headless_shot = "proven"
                else:
                    headless_shot = "Alternative"
                    if shot.get("ok") is True and not real_blit:
                        errors.append(f"headless screenshot paper-ACK without a real blit: {shot} obs={obs}")
                        headless_shot = "unproven"
            req_id, _ = play_stop(proc, req_id)
            errors.extend(pin.project_godot_leak_errors("after headless play.stop"))
        elif start_body.get("ok") is True:
            errors.append(f"headless play.start paper-ACK playing=true: {start_body}")
            return errors, live, "unproven", gui_shot, labels
        else:
            headless_shot = "Alternative"
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
            return errors, live, headless_shot, "unrun", labels
        godot, godot_lines = pin.start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_shot, "failed", labels
        req_id, suite_ok, labels = verify_shot_suite(proc, req_id, errors, scene)
        if suite_ok:
            gui_shot = "proven"
        else:
            gui_shot = "unproven"
        errors.extend(pin.project_godot_leak_errors("after GUI suite"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live play screenshot failed: {type(exc).__name__}: {exc}")
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
    return errors, live, headless_shot, gui_shot, labels


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
    for action_id in ("runtime.screenshot", "runtime.perf"):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.runtime":
            errors.append(f"actions.json missing {action_id}")
        if spec.get("side_effect") != "external":
            errors.append(f"{action_id} must be EXTERNAL apply")
    assert_spec = actions.get("runtime.assert") if isinstance(actions.get("runtime.assert"), dict) else {}
    if assert_spec.get("method") != "godot.runtime" or assert_spec.get("side_effect") != "read":
        errors.append("runtime.assert must be a Play-proven READ")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_shot = "unproven"
    gui_shot = "unrun"
    labels: dict[str, str] = {}
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_shot, gui_shot, labels = live_errors(exe)
            errors.extend(live_errs)

    errors.extend(pin.project_godot_leak_errors("after official test"))
    errors.extend(cleanup_temp())
    cpu = labels.get("cpu", "Alternative")
    banner = (
        f"LIVE={live}; HEADLESS_SHOT={headless_shot}; GUI_SHOT={gui_shot}; "
        f"DIFF={labels.get('diff', 'unrun')}; MISSING_BASELINE={labels.get('missing_baseline', 'unrun')}; "
        f"STATE={labels.get('state', 'unrun')}; PERF={labels.get('perf', 'unrun')}; CPU={cpu}"
    )
    if errors:
        print(f"FAIL: play screenshot; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(
        f"PASS: Play-process screenshot + visual diff + state + perf; {banner}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
