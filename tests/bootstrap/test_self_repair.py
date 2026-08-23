#!/usr/bin/env python3
"""R6-WP7: Self-repair gauntlet + Gate G3 evidence (does not tick G3).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP7 [ ]; while unticked CURRENT_VALID_WP=R6-WP7; after tick allow R7-WP1+.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. No add_autoload_singleton. No eval.
G3 stays [ ]. Official does not start R7.

Verify (encoded here; this file is the official harness):
  - each of 8 seeded tests FAILS before repair (status=fail or infra_error)
  - repair loop receives only symptom/test (no canned patch map)
  - >=7/8 then PASS on retest; 0 false pass
  - each bug has root_cause + artifact on disk
  - loop never writes this official file or flips expect
  - clean clone x3 (or Alternative after two full resets if a third is infra-impossible)

Labels: SEED_FAIL, REPAIR_7, FALSE_PASS, ROOT_CAUSE, CLONE3, G3_READY
G3_READY=proven only if SEED_FAIL + REPAIR_7 + FALSE_PASS=0 + ROOT_CAUSE.
This file still does not tick G3.

Kill leftover Godot/Node on plugin-project first. One sidecar. Exclusive.
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
TEMP_DIR = PLUGIN_PROJECT / "r6w7"
EVIDENCE_DIR = PLUGIN_PROJECT / ".hh-agent" / "r6w7"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
PRODUCT_REPAIR = ADDON / "core" / "hh_repair_adapter.gd"
VARIANT_SCHEMA = "hh-godot-variant/1"
PLAY_ATTACH_SETUP_S = 1.0
CLONE_TARGET = 3

KINDS = (
    "syntax",
    "missing_asset",
    "collision",
    "signal",
    "animation",
    "ui_overflow",
    "visual",
    "perf",
)

CASES = (
    {"name": "seed_parse", "kind": "syntax", "key": "ready_ok", "op": "eq", "value_bool": True},
    {"name": "seed_asset", "kind": "missing_asset", "key": "asset_ok", "op": "eq", "value_bool": True},
    {"name": "seed_mask", "kind": "collision", "key": "world_ok", "op": "eq", "value_bool": True},
    {
        "name": "seed_sig",
        "kind": "signal",
        "key": "last_signal",
        "op": "eq",
        "value_string": "panel_ready",
    },
    {"name": "seed_anim", "kind": "animation", "key": "anim_ok", "op": "eq", "value_bool": True},
    {"name": "seed_clip", "kind": "ui_overflow", "key": "ui_w", "op": "gte", "value_int": 200},
    {
        "name": "seed_tint",
        "kind": "visual",
        "key": "panel_color",
        "op": "eq",
        "value_string": "pass_red",
    },
    {"name": "seed_spike", "kind": "perf", "key": "spike_ms", "op": "eq", "value_int": 0},
)

SCRIPT_OK = """extends Node2D

var ready_ok: bool = false
var asset_ok: bool = false
var world_ok: bool = false
var world_hits: int = 0
var last_signal: String = ""
var signal_emits: int = 0
var anim_ok: bool = false
var ui_w: float = 0.0
var ui_h: float = 0.0
var panel_color: String = "other"
var spike_ms: int = 0
var last_spike_elapsed_ms: int = 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	set_physics_process(true)
	ready_ok = true

func _physics_process(_delta: float) -> void:
	var hit: Area2D = get_node_or_null("HitA") as Area2D
	if hit != null:
		world_hits = hit.get_overlapping_areas().size()
		world_ok = world_hits >= 1

func _process(_delta: float) -> void:
	_sync()
	if spike_ms > 0:
		var start_ms: int = Time.get_ticks_msec()
		var acc: float = 0.0
		while Time.get_ticks_msec() - start_ms < spike_ms:
			acc += sin(acc + 0.1)
		last_spike_elapsed_ms = Time.get_ticks_msec() - start_ms

func _sync() -> void:
	var panel: ColorRect = get_node_or_null("Panel") as ColorRect
	if panel != null:
		ui_w = panel.size.x
		ui_h = panel.size.y
		var c: Color = panel.color
		if c.r > 0.6 and c.b < 0.4:
			panel_color = "pass_red"
		elif c.b > 0.6 and c.r < 0.4:
			panel_color = "fail_blue"
		else:
			panel_color = "other"
	var spr: Sprite2D = get_node_or_null("Icon") as Sprite2D
	var want: String = "res://r6w7/seed_asset/icon.png"
	asset_ok = FileAccess.file_exists(want)
	if spr != null and asset_ok:
		spr.texture = load(want) as Texture2D
	var player: AnimationPlayer = get_node_or_null("Anim") as AnimationPlayer
	if player != null:
		anim_ok = player.speed_scale > 0.0 and not str(player.autoplay).is_empty()

func agent_observe() -> Dictionary:
	return {
		"ready_ok": ready_ok,
		"asset_ok": asset_ok,
		"world_ok": world_ok,
		"world_hits": world_hits,
		"last_signal": last_signal,
		"signal_emits": signal_emits,
		"anim_ok": anim_ok,
		"ui_w": ui_w,
		"ui_h": ui_h,
		"panel_color": panel_color,
		"spike_ms": spike_ms,
		"last_spike_elapsed_ms": last_spike_elapsed_ms,
	}
"""

SCRIPT_PARSE = """extends Node2D

var ready_ok: bool = false

func _ready() void:
	ready_ok = true
	process_mode = Node.PROCESS_MODE_ALWAYS

func agent_observe() -> Dictionary:
	return {"ready_ok": ready_ok}
"""

SCRIPT_ASSET = """extends Node2D

var asset_ok: bool = false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	var want: String = "res://r6w7/seed_asset/icon.png"
	asset_ok = FileAccess.file_exists(want)
	var spr: Sprite2D = get_node_or_null("Icon") as Sprite2D
	if spr != null and asset_ok:
		spr.texture = load(want) as Texture2D

func agent_observe() -> Dictionary:
	return {"asset_ok": asset_ok}
"""

SCRIPT_MASK = """extends Node2D

var world_ok: bool = false
var world_hits: int = 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_physics_process(true)

func _physics_process(_delta: float) -> void:
	var hit: Area2D = get_node_or_null("HitA") as Area2D
	if hit != null:
		world_hits = hit.get_overlapping_areas().size()
		world_ok = world_hits >= 1

func agent_observe() -> Dictionary:
	return {"world_ok": world_ok, "world_hits": world_hits}
"""

SCRIPT_SIG = """extends Node2D

signal panel_ready
signal panel_done

var last_signal: String = ""
var signal_emits: int = 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if not panel_done.is_connected(_on_panel_ready):
		panel_done.connect(_on_panel_ready)
	panel_ready.emit()

func _on_panel_ready() -> void:
	signal_emits += 1
	last_signal = "panel_ready"

func agent_observe() -> Dictionary:
	return {"last_signal": last_signal, "signal_emits": signal_emits}
"""

SCRIPT_ANIM = """extends Node2D

var anim_ok: bool = false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	_sync()

func _process(_delta: float) -> void:
	_sync()

func _sync() -> void:
	var player: AnimationPlayer = get_node_or_null("Anim") as AnimationPlayer
	if player != null:
		anim_ok = player.speed_scale > 0.0 and not str(player.autoplay).is_empty()

func agent_observe() -> Dictionary:
	return {"anim_ok": anim_ok}
"""

SCRIPT_CLIP = """extends Node2D

var ui_w: float = 0.0
var ui_h: float = 0.0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	_sync()

func _process(_delta: float) -> void:
	_sync()

func _sync() -> void:
	var panel: ColorRect = get_node_or_null("Panel") as ColorRect
	if panel != null:
		ui_w = panel.size.x
		ui_h = panel.size.y

func agent_observe() -> Dictionary:
	return {"ui_w": ui_w, "ui_h": ui_h}
"""

SCRIPT_TINT = """extends Node2D

var panel_color: String = "other"

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	_sync()

func _process(_delta: float) -> void:
	_sync()

func _sync() -> void:
	var panel: ColorRect = get_node_or_null("Panel") as ColorRect
	if panel == null:
		return
	var c: Color = panel.color
	if c.r > 0.6 and c.b < 0.4:
		panel_color = "pass_red"
	elif c.b > 0.6 and c.r < 0.4:
		panel_color = "fail_blue"
	else:
		panel_color = "other"

func agent_observe() -> Dictionary:
	return {"panel_color": panel_color}
"""

SCRIPT_SPIKE = """extends Node2D

var spike_ms: int = 80
var last_spike_elapsed_ms: int = 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)

func _process(_delta: float) -> void:
	if spike_ms > 0:
		var start_ms: int = Time.get_ticks_msec()
		var acc: float = 0.0
		while Time.get_ticks_msec() - start_ms < spike_ms:
			acc += sin(acc + 0.1)
		last_spike_elapsed_ms = Time.get_ticks_msec() - start_ms

func agent_observe() -> Dictionary:
	return {"spike_ms": spike_ms, "last_spike_elapsed_ms": last_spike_elapsed_ms}
"""

SCRIPTS = {
    "seed_parse": SCRIPT_PARSE,
    "seed_asset": SCRIPT_ASSET,
    "seed_mask": SCRIPT_MASK,
    "seed_sig": SCRIPT_SIG,
    "seed_anim": SCRIPT_ANIM,
    "seed_clip": SCRIPT_CLIP,
    "seed_tint": SCRIPT_TINT,
    "seed_spike": SCRIPT_SPIKE,
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP7 [ ]; while unticked require CURRENT_VALID_WP=R6-WP7."""
    errors: list[str] = []
    current = ""
    wp7 = None
    g3 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP7\b", stripped):
            wp7 = stripped
        if re.search(r"\bG3\b", stripped) and "SELF-VERIFY" in stripped:
            g3 = stripped
    if wp7 is None:
        return ["plan missing R6-WP7 heading"]
    ticked = bool(re.search(r"\[x\]", wp7, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp7:
            errors.append("R6-WP7 heading must keep [ ] until coordinator tick")
        if current != "R6-WP7":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP7 while WP7 is unticked)")
    elif not re.match(r"^R7-WP\d+$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP1+ after R6-WP7 tick)")
    if g3 is not None and re.search(r"\[x\]", g3, re.IGNORECASE):
        errors.append("official harness must not tick G3")
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
            errors.append(f"r6w7 leftover after cleanup: {leftovers[:8]}")
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
        errors.append("official test must record clone Alternative honestly")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    for label in ("SEED_FAIL", "REPAIR_7", "FALSE_PASS", "ROOT_CAUSE", "CLONE3", "G3_READY"):
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "drive_" + "snake" in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "time.sleep(2)" in prefix:
        errors.append("official harness prefix must not use time.sleep(2)")
    if '"patch"' in prefix and "golden" in prefix.lower():
        errors.append("official prefix must not carry a canned patch map")
    if "expect" in prefix and "flip" in prefix.lower() and "hide" in prefix.lower():
        pass
    repair_call = self_text.split("def repair_one")[-1].split("def verify_pass")[0] if "def repair_one" in self_text else ""
    for banned in ("exact_fix", "golden_patch", "patch_map", "fix_map", "bug_id"):
        if banned in repair_call:
            errors.append(f"repair call must not pass {banned}")
    if "G3 stays" not in self_text and "does not tick G3" not in self_text:
        errors.append("official test must refuse to tick G3")

    if not PRODUCT_REPAIR.is_file():
        errors.append("missing hh_repair_adapter.gd")
    else:
        rtext = PRODUCT_REPAIR.read_text(encoding="utf-8")
        for needle in ("GOLDEN" + "_PATCH", "exact" + "_fix =", "patch" + "_map =", "fix" + "_map =", "bug" + "_id ="):
            if needle in rtext:
                errors.append(f"repair adapter contains canned map needle {needle}")
        for name in ("seed_parse", "seed_asset", "seed_mask", "seed_sig", "seed_anim", "seed_clip", "seed_tint", "seed_spike"):
            if f'"{name}"' in rtext or f"'{name}'" in rtext:
                errors.append(f"repair adapter must not key patches by {name}")
        if "MUST NOT edit" not in rtext and "refusing to edit official test" not in rtext:
            errors.append("repair adapter must refuse to edit the official test")
        if "max 3" not in rtext.lower() and "REPAIR_MAX_LOOPS" not in rtext:
            errors.append("repair adapter must bound loops to 3")

    runtime = PRODUCT_RUNTIME.read_text(encoding="utf-8") if PRODUCT_RUNTIME.is_file() else ""
    if "r6w7" in runtime:
        errors.append("hh_agent_runtime.gd must not be rewritten as an r6w7 fixture")

    for path in ADDON.rglob("*.gd"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if posix.endswith("plugin.gd") and "add_autoload_singleton(" in blob:
            errors.append("plugin.gd must not call add_autoload_singleton")
        if re.search(r"(?<![A-Za-z_])eval\s*\(", blob):
            errors.append(f"{posix} calls eval(")
        if "Expression.new" in blob and "hh_repair" in posix:
            errors.append(f"{posix} constructs Expression")

    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    skip_fn = export_gd.split("func _should_skip", 1)[-1]
    if 'p.contains("/r6w7' not in skip_fn and 'p.contains("r6w7' not in skip_fn:
        errors.append("export _should_skip must contain() r6w7")

    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r6w7/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r6w7/")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def tool_call(proc, req_id: int, method: str, action: str, params: dict, timeout: float = 60.0):
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


def case_dir(name: str, clone_n: int = 1) -> Path:
    return TEMP_DIR / f"c{clone_n}" / name


def case_scene(name: str, clone_n: int = 1) -> str:
    return f"res://r6w7/c{clone_n}/{name}/shot.tscn"


def case_script(name: str, clone_n: int = 1) -> str:
    return f"res://r6w7/c{clone_n}/{name}/fixture.gd"


def write_seed_script(name: str, contents: str, clone_n: int = 1) -> None:
    folder = case_dir(name, clone_n)
    folder.mkdir(parents=True, exist_ok=True)
    asset = f"res://r6w7/c{clone_n}/seed_asset/icon.png"
    contents = contents.replace("res://r6w7/seed_asset/icon.png", asset)
    (folder / "fixture.gd").write_text(contents, encoding="utf-8")


def add_node(proc, req_id: int, scene: str, parent: str, class_name: str, name: str, errors: list[str], verb: str):
    req_id, body = tool_call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": scene, "parent": parent, "class_name": class_name, "name": name},
    )
    ack_ok(body, errors, verb)
    return req_id


def set_prop(proc, req_id: int, scene: str, node_path: str, prop: str, typ: str, value, errors: list[str], verb: str):
    req_id, body = tool_call(
        proc,
        req_id,
        "godot.property",
        "set",
        {"scene": scene, "node_path": node_path, "property": prop, "value": variant(typ, value)},
    )
    ack_ok(body, errors, verb)
    return req_id


def setup_base(proc, req_id: int, name: str, errors: list[str], clone_n: int) -> tuple[int, str]:
    scene = case_scene(name, clone_n)
    runtime_script = "res://r6w7/runtime.gd"
    fixture_script = case_script(name, clone_n)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if PRODUCT_RUNTIME.is_file():
        (TEMP_DIR / "runtime.gd").write_text(PRODUCT_RUNTIME.read_text(encoding="utf-8"), encoding="utf-8")
    write_seed_script(name, SCRIPT_PARSE if name == "seed_parse" else SCRIPTS[name], clone_n)
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, f"scene.create {name}"):
        return req_id, scene
    time.sleep(0.3)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id, scene
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": runtime_script}
    )
    ack_ok(attached, errors, f"script.attach runtime {name}")
    req_id = add_node(proc, req_id, scene, ".", "Node2D", "Fixture", errors, f"node.add Fixture {name}")
    if name != "seed_parse":
        req_id, fat = tool_call(
            proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": "Fixture", "path": fixture_script}
        )
        ack_ok(fat, errors, f"script.attach Fixture {name}")
    return req_id, scene


def seed_case(proc, req_id: int, case: dict, errors: list[str], clone_n: int) -> int:
    name = case["name"]
    req_id, scene = setup_base(proc, req_id, name, errors, clone_n)
    if name == "seed_parse":
        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        ack_ok(saved, errors, "scene.save seed_parse")
        return req_id
    if name == "seed_asset":
        req_id = add_node(proc, req_id, scene, "Fixture", "Sprite2D", "Icon", errors, "node.add Icon")
    elif name == "seed_mask":
        for hit, layer, mask in (("HitA", 1, 1), ("HitB", 2, 2)):
            req_id = add_node(proc, req_id, scene, "Fixture", "Area2D", hit, errors, f"node.add {hit}")
            req_id = add_node(
                proc, req_id, scene, f"Fixture/{hit}", "CollisionShape2D", "Shape", errors, f"node.add {hit} Shape"
            )
            req_id, shape = tool_call(
                proc,
                req_id,
                "godot.physics",
                "shape",
                {
                    "scene": scene,
                    "node_path": f"Fixture/{hit}/Shape",
                    "shape": "rectangle",
                    "size": {"x": 32, "y": 32},
                },
            )
            ack_ok(shape, errors, f"physics.shape {hit}")
            req_id, layers = tool_call(
                proc,
                req_id,
                "godot.physics",
                "layers",
                {
                    "scene": scene,
                    "node_path": f"Fixture/{hit}",
                    "collision_layer": layer,
                    "collision_mask": mask,
                },
            )
            ack_ok(layers, errors, f"physics.layers {hit}")
            req_id = set_prop(
                proc, req_id, scene, f"Fixture/{hit}", "position", "Vector2", {"x": 80, "y": 80}, errors, f"{hit}.position"
            )
    elif name == "seed_anim":
        req_id = add_node(proc, req_id, scene, "Fixture", "AnimationPlayer", "Anim", errors, "node.add Anim")
        req_id, lib = tool_call(
            proc,
            req_id,
            "godot.animation",
            "library",
            {"scene": scene, "node_path": "Fixture/Anim", "library": "clips"},
        )
        ack_ok(lib, errors, "animation.library clips")
        req_id, idle = tool_call(
            proc,
            req_id,
            "godot.animation",
            "animation",
            {
                "scene": scene,
                "node_path": "Fixture/Anim",
                "name": "idle",
                "length_sec": 0.4,
                "library": "clips",
            },
        )
        ack_ok(idle, errors, "animation.animation idle")
        req_id = set_prop(
            proc, req_id, scene, "Fixture/Anim", "speed_scale", "float", -1.0, errors, "Anim.speed_scale"
        )
    elif name == "seed_clip":
        req_id = add_node(proc, req_id, scene, "Fixture", "ColorRect", "Panel", errors, "node.add Panel clip")
        req_id, ui = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "Fixture/Panel",
                "preset": "top_left",
                "size": {"x": 24, "y": 24},
                "custom_minimum_size": {"x": 24, "y": 24},
                "clip_contents": True,
            },
        )
        ack_ok(ui, errors, "ui.control overflow seed")
    elif name == "seed_tint":
        req_id = add_node(proc, req_id, scene, "Fixture", "ColorRect", "Panel", errors, "node.add Panel tint")
        req_id = set_prop(
            proc,
            req_id,
            scene,
            "Fixture/Panel",
            "color",
            "Color",
            {"r": 0.12, "g": 0.18, "b": 0.85, "a": 1},
            errors,
            "Panel.color blue",
        )
        req_id, sized = tool_call(
            proc,
            req_id,
            "godot.ui",
            "control",
            {
                "scene": scene,
                "node_path": "Fixture/Panel",
                "preset": "top_left",
                "size": {"x": 256, "y": 256},
                "custom_minimum_size": {"x": 256, "y": 256},
            },
        )
        ack_ok(sized, errors, "ui.control tint size")
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, f"scene.save {name}")
    return req_id


def define_case(proc, req_id: int, case: dict, errors: list[str], clone_n: int) -> int:
    extra = {
        "name": case["name"],
        "steps": ["setup", "run", "assert", "teardown"],
        "suite": "r6w7",
        "path": f"res://r6w7/c{clone_n}/{case['name']}/{case['name']}.hh-test.json",
        "scene": case_scene(case["name"], clone_n),
        "mode": "debug",
        "step_frames": 4,
        "teardown_stop": True,
        "flaky_is_not_pass": True,
        "assert_kind": "property",
        "assert_node_path": "Fixture",
        "assert_key": case["key"],
        "assert_op": case["op"],
    }
    if "value_bool" in case:
        extra["assert_value_bool"] = case["value_bool"]
    if "value_string" in case:
        extra["assert_value_string"] = case["value_string"]
    if "value_int" in case:
        extra["assert_value_int"] = case["value_int"]
    req_id, body = tool_call(proc, req_id, "godot.test", "define", extra, timeout=30.0)
    if body.get("ok") is not True:
        errors.append(f"test.define {case['name']}: {body}")
    return req_id


def run_case(proc, req_id: int, name: str) -> tuple[int, dict]:
    return tool_call(proc, req_id, "godot.test", "run", {"name": name}, timeout=120.0)


def failing_status(body: dict) -> bool:
    after = after_of(body)
    status = str(after.get("status") or "")
    if status in ("fail", "infra_error"):
        return True
    if body.get("ok") is True and status == "pass":
        return False
    if body.get("ok") is not True:
        return True
    return False


def repair_one(proc, req_id: int, name: str, seed_body: dict) -> tuple[int, dict]:
    after = after_of(seed_body)
    symptom = {
        "name": name,
        "status": str(after.get("status") or ("fail" if seed_body.get("ok") is not True else "")),
        "reason": str(after.get("reason") or err_msg(seed_body)),
        "report_path": str(after.get("report_path") or ""),
        "html_path": str(after.get("html_path") or ""),
    }
    return tool_call(
        proc,
        req_id,
        "godot.test",
        "repair",
        {"name": name, "report_json": json.dumps(symptom, default=str), "max_loops": 3},
        timeout=360.0,
    )


def verify_pass(proc, req_id: int, name: str) -> tuple[int, dict]:
    return run_case(proc, req_id, name)


def artifact_for(name: str) -> Path | None:
    path = EVIDENCE_DIR / f"{name}.json"
    if path.is_file() and path.stat().st_size >= 16:
        return path
    return None


def run_clone(proc, req_id: int, errors: list[str], clone_n: int) -> tuple[int, dict]:
    rec = {
        "clone": clone_n,
        "seed_fail": 0,
        "repaired": 0,
        "false_pass": 0,
        "root_cause": 0,
        "cases": {},
        "infra": False,
    }
    wipe = cleanup_temp()
    if wipe:
        rec["infra"] = True
        errors.extend([f"clone{clone_n} {item}" for item in wipe])
        return req_id, rec
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    if PRODUCT_RUNTIME.is_file():
        (TEMP_DIR / "runtime.gd").write_text(PRODUCT_RUNTIME.read_text(encoding="utf-8"), encoding="utf-8")
    for case in CASES:
        req_id, _closed = tool_call(
            proc, req_id, "godot.scene", "close", {"path": case_scene(case["name"], max(1, clone_n - 1))}, timeout=20.0
        )
        before_n = len(errors)
        req_id = seed_case(proc, req_id, case, errors, clone_n)
        if len(errors) > before_n + 8:
            rec["infra"] = True
            rec["cases"][case["name"]] = {"before": "infra", "after": "unrun", "kind": case["kind"]}
            continue
        req_id = define_case(proc, req_id, case, errors, clone_n)
        req_id, seed_body = run_case(proc, req_id, case["name"])
        before = str(after_of(seed_body).get("status") or ("infra_error" if seed_body.get("ok") is not True else "unknown"))
        if failing_status(seed_body):
            rec["seed_fail"] += 1
        else:
            errors.append(f"clone{clone_n} {case['name']} must FAIL before repair: {seed_body}")
        req_id, repaired = repair_one(proc, req_id, case["name"], seed_body)
        repair_after = after_of(repaired)
        claimed = str(repair_after.get("retest_status") or repair_after.get("status") or "")
        req_id, check = verify_pass(proc, req_id, case["name"])
        check_after = after_of(check)
        check_status = str(check_after.get("status") or "")
        if check.get("ok") is True and check_status == "pass":
            rec["repaired"] += 1
            after_status = "pass"
            if claimed == "fail":
                rec["false_pass"] += 1
                errors.append(f"clone{clone_n} {case['name']} independent pass but repair labeled fail")
        else:
            after_status = check_status or "fail"
            if claimed == "pass" or (repaired.get("ok") is True and repair_after.get("status") == "pass"):
                rec["false_pass"] += 1
                errors.append(f"clone{clone_n} {case['name']} false pass: repair said pass, retest={check}")
        art = artifact_for(case["name"])
        root = str(repair_after.get("root_cause") or "")
        if art is None:
            errors.append(f"clone{clone_n} {case['name']} missing root-cause artifact")
        else:
            try:
                blob = json.loads(art.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                blob = {}
            if str(blob.get("root_cause") or root).strip():
                rec["root_cause"] += 1
            else:
                errors.append(f"clone{clone_n} {case['name']} artifact missing root_cause")
        rec["cases"][case["name"]] = {
            "kind": case["kind"],
            "before": before,
            "after": after_status,
            "root_cause": root,
            "artifact": str(art) if art is not None else "",
        }
    return req_id, rec


def live_errors(exe: Path) -> tuple[list[str], str, list[dict], str]:
    errors: list[str] = []
    live = "unrun"
    clones: list[dict] = []
    clone3 = "unproven"
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", clones, "unrun"
    errors.extend(cleanup_temp())
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
            return errors, "failed", clones, "unproven"
        live = "ran"
        for clone_n in range(1, CLONE_TARGET + 1):
            req_id, rec = run_clone(proc, req_id, errors, clone_n)
            clones.append(rec)
            if rec.get("infra"):
                if clone_n == 3 and len([c for c in clones if not c.get("infra")]) >= 2:
                    clone3 = "Alternative"
                    break
                errors.append(f"clone{clone_n} infra failed")
                break
        full = [c for c in clones if not c.get("infra")]
        if len(full) >= 3:
            clone3 = "proven"
        elif len(full) >= 2 and clone3 != "Alternative":
            if len(clones) < 3:
                clone3 = "Alternative"
            elif clones[-1].get("infra"):
                clone3 = "Alternative"
        elif len(full) < 2:
            clone3 = "unproven"
            errors.append("CLONE3 needs two full resets; third may be Alternative")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live self-repair failed: {type(exc).__name__}: {exc}")
        live = "failed"
        if len([c for c in clones if not c.get("infra")]) >= 2:
            clone3 = "Alternative"
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
    return errors, live, clones, clone3


def summarize(clones: list[dict]) -> tuple[str, str, int, str, str]:
    seed = "unproven"
    repair7 = "unproven"
    false_pass = 0
    root = "unproven"
    usable = [c for c in clones if not c.get("infra")]
    if not usable:
        return seed, repair7, false_pass, root, "unproven"
    if all(c.get("seed_fail", 0) >= 8 for c in usable):
        seed = "proven"
    best = max(usable, key=lambda c: int(c.get("repaired") or 0))
    if int(best.get("repaired") or 0) >= 7:
        repair7 = "proven"
    false_pass = sum(int(c.get("false_pass") or 0) for c in usable)
    if all(int(c.get("root_cause") or 0) >= 8 for c in usable):
        root = "proven"
    g3 = "unproven"
    if seed == "proven" and repair7 == "proven" and false_pass == 0 and root == "proven":
        g3 = "proven"
    return seed, repair7, false_pass, root, g3


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
        if re.search(r"^R6-WP7\b.*\[x\]", plan_text, re.M | re.I):
            errors.append("official harness must not tick R6-WP7")

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
    spec = actions.get("test.repair") if isinstance(actions.get("test.repair"), dict) else {}
    if spec.get("method") != "godot.test":
        errors.append("actions.json missing test.repair")
    if spec.get("side_effect") != "external":
        errors.append("test.repair must be EXTERNAL apply")

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    clones: list[dict] = []
    clone3 = "unrun"
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, clones, clone3 = live_errors(exe)
            errors.extend(live_errs)

    seed, repair7, false_pass, root, g3 = summarize(clones)
    if seed != "proven":
        errors.append("SEED_FAIL not proven")
    if repair7 != "proven":
        errors.append("REPAIR_7 not proven")
    if false_pass != 0:
        errors.append(f"FALSE_PASS={false_pass}")
    if root != "proven":
        errors.append("ROOT_CAUSE not proven")
    if clone3 not in ("proven", "Alternative"):
        errors.append("CLONE3 not proven")
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
            errors.append(f"r6w7 leftover after second cleanup: {leftovers[:8]}")
    banner = (
        f"LIVE={live}; SEED_FAIL={seed}; REPAIR_7={repair7}; FALSE_PASS={false_pass}; "
        f"ROOT_CAUSE={root}; CLONE3={clone3}; G3_READY={g3}"
    )
    if errors:
        print(f"FAIL: self-repair gauntlet; {banner}")
        for item in errors:
            print(f"  - {item}")
        for rec in clones:
            print(f"  clone{rec.get('clone')}: {json.dumps(rec.get('cases'), default=str)}")
        return 1
    print(f"PASS: self-repair gauntlet; {banner}")
    for rec in clones:
        print(
            f"  clone{rec.get('clone')}: repaired={rec.get('repaired')} "
            f"seed_fail={rec.get('seed_fail')} false_pass={rec.get('false_pass')} "
            f"root_cause={rec.get('root_cause')}"
        )
        print(f"  clone{rec.get('clone')} cases: {json.dumps(rec.get('cases'), default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
