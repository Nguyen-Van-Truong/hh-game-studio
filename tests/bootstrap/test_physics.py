#!/usr/bin/env python3
"""R5-WP5: Physics/navigation/collision adapters.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Do not raw-edit .tscn/.tres bytes. Plugin is the only writer.

Verify (encoded here; this file is the official harness):
  - CharacterBody2D + explicit/asset-bounds shape
  - StaticBody2D wall
  - Area2D sensor + signal.connect (configuration only)
  - RigidBody2D projectile CONFIG only (no flight)
  - layer matrix player=1 / world=2 / interact=4
  - NavigationRegion2D walkable outline + wall obstruction, sync bake
  - shape geometry + matrix + lint
  - path query if map_get_iteration_id>0 else Alternative/E_UNVERIFIED
  - one Agent: UndoRedo
  - scene.save + reopen hash
  - do NOT call play.start

Honest Alternatives named here:
  - screenshots=SKIP (R6)
  - move-and-slide / sensor fire / projectile flight / nav walking = deferred R6
  - map_get_path may be E_UNVERIFIED if editor nav map not synced
  - play.start is not paper-ACK'd
  - SystemFont N/A; no dummy PNG
  - debug_collisions_hint / Visible Collision Shapes not proven (CM-139 Gap)

Generated plugin-validator.json / mcp-tools.json are coordinator-owned
(`npm run generate`). This WP registers verbs in actions.json + the live
TypeScript catalog. No extra codegen pipeline.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
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
TEMP_DIR = PLUGIN_PROJECT / "r5w5"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCREENSHOTS = "SKIP"
PHYSICS_MUTATES = (
    "physics.body",
    "physics.shape",
    "physics.layers",
    "physics.nav_region",
    "physics.nav_agent",
)
PHYSICS_VERBS = (
    "body",
    "shape",
    "layers",
    "nav_region",
    "nav_agent",
    "path",
    "lint",
    "debug",
)
EXIST_APIS = (
    "set_collision_layer_value",
    "add_outline",
    "bake_navigation_polygon",
    "map_get_path",
    "get_polygon_count",
)
BAN_NEEDLES = (
    "KinematicBody2D",
    "Navigation2D",
    "get_simple_path",
    "RectangleShape2D.extents",
    "PhysicsMaterial2D",
    "Physics2DServer",
    "set_target_location",
    "get_next_location",
    "make_polygons_from_outlines",
    "Vector2(32, 32)",
    "move_and_slide",
)
SENSOR_SCRIPT = """extends Area2D

func _on_body_entered(_body: Node2D) -> void:
	pass
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP5 [ ]; while unticked require CURRENT_VALID_WP=R5-WP5."""
    errors: list[str] = []
    current = ""
    wp5 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP5\b", stripped):
            wp5 = stripped
    if wp5 is None:
        return ["plan missing R5-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R5-WP5 heading must keep [ ] until coordinator tick")
        if current != "R5-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP5 while WP5 is unticked)")
    elif not re.match(r"^R5-WP([6-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP6+ after R5-WP5 tick)")
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


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def plugin_godot_busy() -> bool:
    """True when an existing Godot process already holds plugin-project."""
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
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png)", self_text):
        errors.append("official test writes a .tscn/.tres/.png path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record path/Play/screenshot Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "deferred R6" not in self_text:
        errors.append("official test must defer move-and-slide / sensor fire / projectile / nav walking to R6")
    if "E_UNVERIFIED" not in self_text:
        errors.append("official test must allow map_get_path E_UNVERIFIED")
    if "SystemFont N/A" not in self_text:
        errors.append("official test must name SystemFont N/A")
    if "CM-139" not in self_text:
        errors.append("official test must name CM-139 Gap for Visible Collision Shapes")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "godot.play" in self_text and "start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must not call play.start")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_physics_adapter" not in router:
        errors.append("router must dispatch through hh_physics_adapter")
    if "godot.physics" not in router:
        errors.append("router must name godot.physics")

    adapter = ADDON / "core" / "hh_physics_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_physics_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        for needle in EXIST_APIS:
            if needle not in text:
                errors.append(f"physics adapter must use {needle}")
        for needle in (
            "UNDO_ACTION_PREFIX",
            "create_action",
            "set_collision_mask_value",
            "get_collision_layer_value",
            "get_outline_count",
            "target_position",
            "get_rect",
            "get_size",
            "bake_navigation_polygon(false)",
            "is_baking_navigation_polygon",
            "map_is_active",
            "map_get_iteration_id",
            "PhysicsMaterial",
        ):
            if needle not in text:
                errors.append(f"physics adapter must use {needle}")
        if "extents" in text:
            errors.append("physics adapter must not use RectangleShape2D.extents")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("physics adapter has a generic invoke path")
        for banned in BAN_NEEDLES:
            if banned in text:
                errors.append(f"physics adapter must not use {banned}")
        if "plugin-validator" not in text and "coordinator" not in text:
            errors.append("physics adapter must note coordinator-owned generated catalog")
        if "Alternative" not in text:
            errors.append("physics adapter must label editor nav map Alternative honestly")
        if "CM-139" not in text:
            errors.append("physics adapter must name CM-139 Gap")

    overlay = (ADDON / "ui" / "overlay" / "hh_overlay.gd").read_text(encoding="utf-8")
    if "godot.physics" not in overlay:
        errors.append("overlay must treat godot.physics as presentable")
    if "engine_world_rect" not in overlay:
        errors.append("overlay must use engine AABB, invented_box=false")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("physics.body", "godot.physics", "body"),
            ("physics.shape", "godot.physics", "shape"),
            ("physics.layers", "godot.physics", "layers"),
            ("physics.nav_region", "godot.physics", "nav_region"),
            ("physics.nav_agent", "godot.physics", "nav_agent"),
            ("physics.path", "godot.physics", "path"),
            ("physics.lint", "godot.physics", "lint"),
            ("physics.debug", "godot.physics", "debug"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "PHYSICS_APPLY" not in lifecycle or "isPhysicsApply" not in lifecycle:
        errors.append("scene_lifecycle must export PHYSICS_APPLY / isPhysicsApply")
    if "isPhysicsApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isPhysicsApply")
    for action_id in PHYSICS_MUTATES:
        if action_id not in lifecycle:
            errors.append(f"isProvenEditorApply must list {action_id}")
    if "physics.path" in lifecycle.split("PHYSICS_APPLY")[1].split("]")[0]:
        errors.append("PHYSICS_APPLY must not include path/lint/debug")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function physicsApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check physics apply")
    if "const physicsFail = physicsApplyOk" not in execute:
        errors.append("execute.ts must call physicsApplyOk from applyMutateOnce")
    if '"physics"' not in execute:
        errors.append("execute.ts after_summary must use kind physics")
    if "physics node_path bind mismatch" not in execute:
        errors.append("execute.ts must bind physics node_path")
    if "physics invented a bounds box" not in execute:
        errors.append("execute.ts must refuse invented_box")
    if "refusing RAM-only physics durable ACK" not in execute:
        errors.append("execute.ts must refuse RAM-only physics durable ACK")

    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if "isPhysicsApply(def.id)" not in resources or '"physics"' not in resources:
        errors.append("mcp_resources.ts must label physics apply as the physics adapter")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("physics.body", "godot.physics", "body"),
        ("physics.shape", "godot.physics", "shape"),
        ("physics.layers", "godot.physics", "layers"),
        ("physics.nav_region", "godot.physics", "nav_region"),
        ("physics.nav_agent", "godot.physics", "nav_agent"),
        ("physics.path", "godot.physics", "path"),
        ("physics.lint", "godot.physics", "lint"),
        ("physics.debug", "godot.physics", "debug"),
    ):
        spec = validator_actions.get(action_id) if isinstance(validator_actions.get(action_id), dict) else {}
        if spec.get("method") != method or spec.get("verb") != verb:
            errors.append(f"plugin-validator.json missing dotted id {action_id}")

    mcp_tools = json.loads((BRIDGE / "generated" / "mcp-tools.json").read_text(encoding="utf-8"))
    tool_enums: dict[str, list[str]] = {}
    for tool in mcp_tools.get("tools") if isinstance(mcp_tools.get("tools"), list) else []:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "")
        schema = tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {}
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        action = props.get("action") if isinstance(props.get("action"), dict) else {}
        enum = action.get("enum") if isinstance(action.get("enum"), list) else []
        tool_enums[name] = [str(item) for item in enum]
    domain = tool_enums.get("godot.physics", [])
    for verb in PHYSICS_VERBS:
        if verb not in domain:
            errors.append(f"mcp-tools.json godot.physics must enum {verb}")
    if "godot.physics" not in tool_enums:
        errors.append("mcp-tools.json must expose godot.physics as a domain tool")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", blob) or "evaluate_expression" in blob:
            errors.append(f"{posix} has a generic invoke path")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 45.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 45.0,
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


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    if plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r5w5/arena.tscn"
    tex = "res://r5w5/player_tex.tres"
    script_p = "res://r5w5/sensor.gd"
    req_id = 2
    # Honest Alternatives:
    # screenshots=SKIP (R6)
    # move-and-slide / sensor fire / projectile flight / nav walking = deferred R6
    # map_get_path may be E_UNVERIFIED if editor nav map not synced
    # play.start is not paper-ACK'd
    # SystemFont N/A; no dummy PNG
    _screenshots = SCREENSHOTS
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
        if not ack_ok(created, errors, "scene.create"):
            return errors

        for class_name, name, parent in (
            ("CharacterBody2D", "Player", "."),
            ("CollisionShape2D", "Shape", "Player"),
            ("Sprite2D", "Sprite", "Player"),
            ("NavigationAgent2D", "Agent", "Player"),
            ("StaticBody2D", "Wall", "."),
            ("CollisionShape2D", "Shape", "Wall"),
            ("Area2D", "Sensor", "."),
            ("CollisionShape2D", "Shape", "Sensor"),
            ("RigidBody2D", "Projectile", "."),
            ("CollisionShape2D", "Shape", "Projectile"),
            ("StaticBody2D", "Gem", "."),
            ("CollisionShape2D", "Shape", "Gem"),
            ("StaticBody2D", "Poly", "."),
            ("CollisionPolygon2D", "Shape", "Poly"),
            ("StaticBody2D", "Bare", "."),
            ("NavigationRegion2D", "Nav", "."),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": parent, "class_name": class_name, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {parent}/{name}"):
                return errors

        for node_path, x, y in (
            ("Player", 80, 180),
            ("Wall", 320, 180),
            ("Sensor", 200, 180),
            ("Projectile", 80, 80),
            ("Gem", 140, 260),
            ("Poly", 480, 260),
            ("Bare", 40, 40),
        ):
            req_id, posed = tool_call(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": scene,
                    "node_path": node_path,
                    "property": "position",
                    "value": variant("Vector2", {"x": x, "y": y}),
                },
            )
            if not ack_ok(posed, errors, f"property.set {node_path}.position"):
                return errors

        req_id, scaled = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "Bare",
                "property": "scale",
                "value": variant("Vector2", {"x": 2, "y": 1}),
            },
        )
        if not ack_ok(scaled, errors, "property.set Bare.scale"):
            return errors

        req_id, tex_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": tex, "class_name": "PlaceholderTexture2D"}
        )
        if not ack_ok(tex_created, errors, "resource.create PlaceholderTexture2D"):
            return errors
        req_id, tex_sized = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": tex, "property": "size", "value": variant("Vector2", {"x": 16, "y": 16})},
        )
        if not ack_ok(tex_sized, errors, "resource.edit PlaceholderTexture2D.size"):
            return errors
        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "Player/Sprite", "property": "texture", "resource": tex},
        )
        if not ack_ok(assigned, errors, "resource.assign Player/Sprite.texture"):
            return errors

        req_id, player_body = tool_call(
            proc,
            req_id,
            "godot.physics",
            "body",
            {
                "scene": scene,
                "node_path": "Player",
                "motion_mode": "grounded",
                "velocity": {"x": 80, "y": 0},
            },
        )
        if not ack_ok(player_body, errors, "physics.body Player"):
            return errors
        pb = player_body.get("after") or {}
        if pb.get("class_name") != "CharacterBody2D":
            errors.append(f"physics.body Player class: {pb}")
        if pb.get("motion_mode") != "grounded":
            errors.append(f"physics.body motion_mode: {pb}")
        if pb.get("invented_box") is True:
            errors.append(f"physics.body invented_box: {pb}")
        if not str(player_body.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"physics.body missing Agent undo: {player_body}")

        req_id, player_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {
                "scene": scene,
                "node_path": "Player/Shape",
                "shape": "rectangle",
                "from_sprite": "Player/Sprite",
            },
        )
        if not ack_ok(player_shape, errors, "physics.shape Player from_sprite"):
            return errors
        ps = player_shape.get("after") or {}
        geom = ps.get("geometry") if isinstance(ps.get("geometry"), dict) else {}
        size = geom.get("size") if isinstance(geom.get("size"), dict) else {}
        if float(size.get("x") or 0) != 16 or float(size.get("y") or 0) != 16:
            errors.append(f"Player shape must use Sprite2D.get_rect 16x16, not invented: {ps}")
        if ps.get("shape_class") != "RectangleShape2D":
            errors.append(f"Player shape_class: {ps}")

        req_id, wall_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {
                "scene": scene,
                "node_path": "Wall/Shape",
                "shape": "rectangle",
                "size": {"x": 40, "y": 200},
            },
        )
        if not ack_ok(wall_shape, errors, "physics.shape Wall"):
            return errors

        req_id, sensor_body = tool_call(
            proc,
            req_id,
            "godot.physics",
            "body",
            {"scene": scene, "node_path": "Sensor", "monitoring": True, "monitorable": True},
        )
        if not ack_ok(sensor_body, errors, "physics.body Sensor"):
            return errors
        req_id, sensor_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {"scene": scene, "node_path": "Sensor/Shape", "shape": "circle", "radius": 12},
        )
        if not ack_ok(sensor_shape, errors, "physics.shape Sensor"):
            return errors
        sg = (sensor_shape.get("after") or {}).get("geometry") or {}
        if float(sg.get("radius") or 0) != 12:
            errors.append(f"Sensor circle radius bind: {sensor_shape}")

        req_id, proj = tool_call(
            proc,
            req_id,
            "godot.physics",
            "body",
            {
                "scene": scene,
                "node_path": "Projectile",
                "mass": 0.4,
                "gravity_scale": 0.5,
                "linear_velocity": {"x": 120, "y": 0},
                "contact_monitor": True,
                "max_contacts_reported": 4,
                "freeze": True,
            },
        )
        if not ack_ok(proj, errors, "physics.body Projectile CONFIG"):
            return errors
        pa = proj.get("after") or {}
        if pa.get("freeze") is not True or pa.get("class_name") != "RigidBody2D":
            errors.append(f"projectile CONFIG bind: {pa}")
        req_id, proj_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {
                "scene": scene,
                "node_path": "Projectile/Shape",
                "shape": "capsule",
                "radius": 6,
                "height": 20,
            },
        )
        if not ack_ok(proj_shape, errors, "physics.shape Projectile"):
            return errors

        req_id, gem_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {
                "scene": scene,
                "node_path": "Gem/Shape",
                "shape": "convex",
                "points": [
                    {"x": 0, "y": -8},
                    {"x": 8, "y": 0},
                    {"x": 0, "y": 8},
                    {"x": -8, "y": 0},
                ],
            },
        )
        if not ack_ok(gem_shape, errors, "physics.shape Gem convex"):
            return errors

        req_id, poly_shape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {
                "scene": scene,
                "node_path": "Poly/Shape",
                "shape": "polygon",
                "points": [
                    {"x": -10, "y": -10},
                    {"x": 10, "y": -10},
                    {"x": 10, "y": 10},
                    {"x": -10, "y": 10},
                ],
            },
        )
        if not ack_ok(poly_shape, errors, "physics.shape Poly polygon"):
            return errors

        req_id, wall_layers = tool_call(
            proc,
            req_id,
            "godot.physics",
            "layers",
            {
                "scene": scene,
                "node_path": "Wall",
                "collision_layer": 2,
                "collision_mask": 1,
                "fixture": "world",
            },
        )
        if not ack_ok(wall_layers, errors, "physics.layers Wall"):
            return errors
        wl = wall_layers.get("after") or {}
        if wl.get("collision_layer") != 2 or wl.get("collision_mask") != 1:
            errors.append(f"Wall layer matrix: {wl}")
        layer_values = wl.get("layer_values") if isinstance(wl.get("layer_values"), dict) else {}
        if layer_values.get("2") is not True:
            errors.append(f"Wall get_collision_layer_value(2): {wl}")
        if not str(wall_layers.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"physics.layers missing Agent undo: {wall_layers}")

        req_id, layer_get = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "Wall", "property": "collision_layer"},
        )
        if ack_ok(layer_get, errors, "property.get Wall.collision_layer"):
            got = (layer_get.get("after") or {}).get("value")
            if isinstance(got, dict) and int(got.get("value") or 0) != 2 and got.get("value") != 2:
                if got != 2:
                    errors.append(f"Wall collision_layer get: {layer_get}")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after physics.layers"):
            errors.append(f"one-undo after layers must ACK: {undone}")
        req_id, after_undo = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "Wall", "property": "collision_layer"},
        )
        if ack_ok(after_undo, errors, "property.get after layers undo"):
            got_u = (after_undo.get("after") or {}).get("value")
            val_u = got_u.get("value") if isinstance(got_u, dict) else got_u
            if int(val_u or 0) == 2:
                errors.append(f"one Agent UndoRedo did not restore Wall layer: {after_undo}")

        req_id, redone = tool_call(proc, req_id, "godot.node", "redo", {"scene": scene, "count": 1})
        if not ack_ok(redone, errors, "node.redo after layers undo"):
            errors.append(f"one-redo after layers undo must ACK: {redone}")

        for node_path, layer, mask, fixture in (
            ("Player", 1, 2, "player"),
            ("Sensor", 4, 1, "interact"),
            ("Projectile", 1, 2, "player"),
            ("Gem", 2, 1, "world"),
            ("Poly", 2, 1, "world"),
            ("Bare", 0, 0, ""),
        ):
            params = {
                "scene": scene,
                "node_path": node_path,
                "collision_layer": layer,
                "collision_mask": mask,
            }
            if fixture:
                params["fixture"] = fixture
            req_id, layered = tool_call(proc, req_id, "godot.physics", "layers", params)
            if not ack_ok(layered, errors, f"physics.layers {node_path}"):
                return errors
            la = layered.get("after") or {}
            if la.get("collision_layer") != layer or la.get("collision_mask") != mask:
                errors.append(f"{node_path} layer matrix: {la}")

        req_id, wrote = tool_call(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": script_p, "contents": SENSOR_SCRIPT},
        )
        if not ack_ok(wrote, errors, "script.write sensor"):
            return errors
        req_id, attached = tool_call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": scene, "node_path": "Sensor", "path": script_p},
        )
        if not ack_ok(attached, errors, "script.attach Sensor"):
            return errors
        req_id, connected = tool_call(
            proc,
            req_id,
            "godot.signal",
            "connect",
            {
                "scene": scene,
                "source": "Sensor",
                "signal": "body_entered",
                "target": "Sensor",
                "method": "_on_body_entered",
            },
        )
        if not ack_ok(connected, errors, "signal.connect Sensor.body_entered"):
            return errors

        req_id, baked = tool_call(
            proc,
            req_id,
            "godot.physics",
            "nav_region",
            {
                "scene": scene,
                "node_path": "Nav",
                "outline": [
                    {"x": 0, "y": 0},
                    {"x": 640, "y": 0},
                    {"x": 640, "y": 360},
                    {"x": 0, "y": 360},
                ],
                "obstructions": [
                    [
                        {"x": 300, "y": 80},
                        {"x": 340, "y": 80},
                        {"x": 340, "y": 280},
                        {"x": 300, "y": 280},
                    ]
                ],
                "parse_static_colliders": True,
            },
        )
        if not ack_ok(baked, errors, "physics.nav_region"):
            return errors
        na = baked.get("after") or {}
        if int(na.get("outline_count") or 0) < 1:
            errors.append(f"nav outline_count: {na}")
        if na.get("is_baking") is True:
            errors.append(f"sync bake still running: {na}")
        if not str(baked.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"nav_region missing Agent undo: {baked}")

        req_id, agent = tool_call(
            proc,
            req_id,
            "godot.physics",
            "nav_agent",
            {
                "scene": scene,
                "node_path": "Player/Agent",
                "target_position": {"x": 500, "y": 180},
            },
        )
        if not ack_ok(agent, errors, "physics.nav_agent"):
            return errors
        ag = agent.get("after") or {}
        tp = ag.get("target_position") if isinstance(ag.get("target_position"), dict) else {}
        if float(tp.get("x") or 0) != 500 or float(tp.get("y") or 0) != 180:
            errors.append(f"nav_agent target bind: {ag}")

        req_id, linted = tool_call(proc, req_id, "godot.physics", "lint", {"scene": scene})
        if not ack_ok(linted, errors, "physics.lint"):
            return errors
        issues = (linted.get("after") or {}).get("issues")
        if not isinstance(issues, list):
            errors.append(f"lint missing issues: {linted}")
        else:
            codes = {str(item.get("code")) for item in issues if isinstance(item, dict)}
            if "null_shape" not in codes:
                errors.append(f"lint must report Bare null_shape: {issues}")
            if "layer0" not in codes or "mask0" not in codes:
                errors.append(f"lint must report Bare layer0/mask0: {issues}")
            if "non_uniform_scale" not in codes:
                errors.append(f"lint must report Bare non_uniform_scale: {issues}")

        req_id, debug = tool_call(proc, req_id, "godot.physics", "debug", {"scene": scene})
        if not ack_ok(debug, errors, "physics.debug"):
            return errors
        dbg = debug.get("after") or {}
        if dbg.get("invented_box") is True:
            errors.append(f"physics.debug invented_box: {dbg}")
        if dbg.get("visible_collision_shapes_proven") is True:
            errors.append("must not claim Visible Collision Shapes proven (CM-139 Gap)")
        items = dbg.get("items") if isinstance(dbg.get("items"), list) else []
        if not items:
            errors.append(f"physics.debug missing engine bounds: {dbg}")

        req_id, path_body = tool_call(
            proc,
            req_id,
            "godot.physics",
            "path",
            {
                "scene": scene,
                "node_path": "Nav",
                "from": {"x": 80, "y": 180},
                "to": {"x": 500, "y": 180},
                "optimize": True,
            },
        )
        if path_body.get("ok") is True:
            p_after = path_body.get("after") or {}
            points = p_after.get("points") if isinstance(p_after.get("points"), list) else []
            if len(points) < 2:
                errors.append(f"map_get_path ACK with empty/invented polyline: {path_body}")
            if p_after.get("invented_polyline") is True:
                errors.append(f"path invented polyline: {p_after}")
        else:
            err = path_body.get("error") if isinstance(path_body.get("error"), dict) else {}
            if err.get("code") != "E_UNVERIFIED":
                errors.append(f"unsynced map_get_path must be E_UNVERIFIED Alternative: {path_body}")
            blob = json.dumps(path_body)
            if "Alternative" not in blob:
                errors.append(f"map_get_path E_UNVERIFIED must label Alternative: {path_body}")

        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors
        hash_before = str((saved.get("after") or {}).get("disk_hash") or "")
        if len(hash_before) < 16:
            errors.append(f"scene.save missing disk_hash: {saved}")

        req_id, reloaded = tool_call(proc, req_id, "godot.scene", "reload", {"path": scene})
        if not ack_ok(reloaded, errors, "scene.reload"):
            return errors
        hash_after = str((reloaded.get("after") or {}).get("disk_hash") or "")
        if hash_before and hash_after and hash_before != hash_after:
            errors.append(f"save/reopen disk_hash drifted: {hash_before} -> {hash_after}")

        req_id, re_layers = tool_call(
            proc,
            req_id,
            "godot.physics",
            "layers",
            {"scene": scene, "node_path": "Player", "collision_layer": 1, "collision_mask": 2},
        )
        if ack_ok(re_layers, errors, "physics.layers Player after reload"):
            rl = re_layers.get("after") or {}
            if rl.get("collision_layer") != 1 or rl.get("collision_mask") != 2:
                errors.append(f"save/reopen lost layer matrix: {rl}")

        if _screenshots != "SKIP":
            errors.append("physics screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live physics failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
        life.stop_proc(proc)
        if desc_path and desc_path.is_file():
            try:
                desc_path.unlink()
            except OSError:
                pass
        cleanup_temp()
    return errors


def main() -> int:
    errors: list[str] = []
    if not PLAN.is_file():
        print("FAIL: missing authoritative 20-8 plan", file=sys.stderr)
        return 1
    errors.extend(plan_errors(PLAN.read_text(encoding="utf-8")))
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required (no skip-PASS): {pin_reason}")
        print("FAIL: physics", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")

    if not errors:
        errors.extend(live_errors(exe))

    if errors:
        print("FAIL: physics", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: physics body/shape/layers/nav adapters; layer matrix 1/2/4; "
        f"sync bake; path Alternative; one-undo; screenshots={SCREENSHOTS}; "
        "move-and-slide deferred R6; play.start not paper-ACK'd"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
