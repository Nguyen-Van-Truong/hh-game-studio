#!/usr/bin/env python3
"""R5-WP7: Capability coverage gauntlet and docs.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Museum is one sidecar under godot/plugin-project/r5w7/. Plugin is the only
.tscn writer. PlaceholderTexture2D + AudioStreamGenerator are honest
Alternatives for missing art/audio.

Verify (encoded here; this file is the official harness):
  - keep R5-WP7 [ ]; while unticked CURRENT_VALID_WP=R5-WP7
  - COVERAGE_2D.md traces every P0 2D row; P1 2D >=90%
  - museum via MCP: TileMapLayer+TileSet, AnimationPlayer/SpriteFrames,
    HUD/Control/theme, physics body+shape+layers, NavigationRegion2D,
    AudioStreamPlayer+bus, canvas_item shader
  - scene.save + reopen hash; structured readback per domain
  - do NOT call play.start (Play sạch is editor save/reopen, not F5)
  - cite existing official tests; do not re-run the R3-R5 gauntlet here

screenshots=SKIP. Heard SFX / runtime.screenshot / export build stay Alternative/Gap.

Generated plugin-validator.json / mcp-tools.json are coordinator-owned.
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
MATRIX = REPO_ROOT / "docs" / "godot-agent" / "CAPABILITY_MATRIX.md"
REPORT = REPO_ROOT / "docs" / "godot-agent" / "COVERAGE_2D.md"
CORPUS = REPO_ROOT / "tests" / "bootstrap" / "fixtures" / "r5w7_prompt_corpus.txt"
MCP_TOOLS = BRIDGE / "generated" / "mcp-tools.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r5w7"
SCREENSHOTS = "SKIP"
SCHEMA = "hh-godot-variant/1"
PROCESS_MODE_ALWAYS = 3
TWOD_GROUPS = (
    "project",
    "scene",
    "node",
    "inspector",
    "filesystem",
    "script",
    "TileMap",
    "animation",
    "UI",
    "audio",
    "physics/navigation",
)
P2_IDS = {"CM-048", "CM-072", "CM-089", "CM-110", "CM-141", "CM-158"}
ID_RE = re.compile(r"^CM-\d{3,}$")
OFFICIAL_TEST_RE = re.compile(r"tests/bootstrap/test_[a-z0-9_]+\.py")
OWNER_RE = re.compile(r"R[689](?:-WP\d+)?")
CITE_OFFICIAL = (
    "tests/bootstrap/test_project_settings.py",
    "tests/bootstrap/test_scene_lifecycle.py",
    "tests/bootstrap/test_node_crud.py",
    "tests/bootstrap/test_property_codec.py",
    "tests/bootstrap/test_resource_ops.py",
    "tests/bootstrap/test_script_write.py",
    "tests/bootstrap/test_asset_ingest.py",
    "tests/bootstrap/test_tilemap.py",
    "tests/bootstrap/test_animation.py",
    "tests/bootstrap/test_ui.py",
    "tests/bootstrap/test_audio_render.py",
    "tests/bootstrap/test_physics.py",
    "tests/bootstrap/test_transform_2d.py",
    "tests/bootstrap/test_editor_focus.py",
)
GOOD_SHADER = """shader_type canvas_item;

uniform vec4 tint : source_color = vec4(1.0);

void fragment() {
	COLOR = texture(TEXTURE, UV) * tint;
}
"""
SPARE_SCRIPT = """extends Node2D

func marker() -> void:
	pass
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP7 [ ]; while unticked require CURRENT_VALID_WP=R5-WP7."""
    errors: list[str] = []
    current = ""
    wp7 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP7\b", stripped):
            wp7 = stripped
    if wp7 is None:
        return ["plan missing R5-WP7 heading"]
    ticked = bool(re.search(r"\[x\]", wp7, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp7:
            errors.append("R5-WP7 heading must keep [ ] until coordinator tick")
        if current != "R5-WP7":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP7 while WP7 is unticked)")
    elif not re.match(r"^R6-WP\d+$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP1+ after R5-WP7 tick)")
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


def split_md_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def parse_matrix_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        cols = split_md_row(line)
        if cols is None or not ID_RE.fullmatch(cols[0]) or len(cols) < 11:
            continue
        rows.append(cols)
    return rows


def report_row_for(report: str, cid: str) -> str | None:
    for line in report.splitlines():
        cols = split_md_row(line)
        if cols and cols[0] == cid:
            return line
    return None


def row_is_traced(line: str) -> bool:
    if OFFICIAL_TEST_RE.search(line) or "Godot CLI" in line:
        return True
    if re.search(r"\b(Alternative|Gap)\b", line) and OWNER_RE.search(line):
        return True
    return False


def coverage_errors() -> list[str]:
    errors: list[str] = []
    if not REPORT.is_file():
        return ["missing docs/godot-agent/COVERAGE_2D.md"]
    if not MATRIX.is_file():
        return ["missing docs/godot-agent/CAPABILITY_MATRIX.md"]
    matrix = parse_matrix_rows(MATRIX.read_text(encoding="utf-8"))
    report = REPORT.read_text(encoding="utf-8")
    if "play.start" in report and "E_UNVERIFIED" not in report:
        errors.append("coverage report must keep play.start E_UNVERIFIED")
    if "paper-ACK" in report and "play.start" not in report:
        errors.append("coverage report must refuse paper-ACK of play.start")
    p0 = [
        r
        for r in matrix
        if r[1] in TWOD_GROUPS and r[9] == "P0" and r[0] not in P2_IDS
    ]
    p1 = [
        r
        for r in matrix
        if r[1] in TWOD_GROUPS and r[9] == "P1" and r[0] not in P2_IDS
    ]
    p0_traced = 0
    p1_traced = 0
    for row in p0:
        line = report_row_for(report, row[0])
        if line is None:
            errors.append(f"coverage missing P0 2D row {row[0]}")
            continue
        if row_is_traced(line):
            p0_traced += 1
        else:
            errors.append(f"P0 2D {row[0]} is not traced to action+test or Alternative/Gap+owner")
    if p0 and p0_traced != len(p0):
        errors.append(f"P0 2D traceable {p0_traced}/{len(p0)} (need 100%)")
    for row in p1:
        line = report_row_for(report, row[0])
        if line is None:
            errors.append(f"coverage missing P1 2D row {row[0]}")
            continue
        if row_is_traced(line):
            p1_traced += 1
        else:
            errors.append(f"P1 2D {row[0]} is not traced to action+test or Alternative/Gap+owner")
    if p1 and (100.0 * p1_traced / len(p1)) < 90.0:
        errors.append(f"P1 2D traceable {p1_traced}/{len(p1)} (need >=90%)")
    return errors


def corpus_errors() -> list[str]:
    errors: list[str] = []
    if not CORPUS.is_file():
        return ["missing tests/bootstrap/fixtures/r5w7_prompt_corpus.txt"]
    text = CORPUS.read_text(encoding="utf-8")
    if "mcp-tools.json" not in text:
        errors.append("corpus must measure counts from mcp-tools.json")
    if "Alternative" not in text or "no real perf harness" not in text:
        errors.append("corpus must label wall-clock benchmark Alternative")
    if re.search(r"p95\s*=|\b\d+\s*ms\b|wall-clock=\d", text, re.IGNORECASE):
        errors.append("corpus must not invent wall-clock timings")
    prompts = [ln for ln in text.splitlines() if re.match(r"^\d{2}\.\s+", ln) and "=>" in ln]
    if len(prompts) < 45:
        errors.append(f"corpus prompt titles={len(prompts)} (need ~50)")
    if not MCP_TOOLS.is_file():
        errors.append("missing bridge/generated/mcp-tools.json")
        return errors
    tools = json.loads(MCP_TOOLS.read_text(encoding="utf-8"))
    if int(tools.get("tool_count") or 0) < 10:
        errors.append(f"mcp-tools.json tool_count={tools.get('tool_count')}")
    if int(tools.get("action_count") or 0) < 100:
        errors.append(f"mcp-tools.json action_count={tools.get('action_count')}")
    if str(tools.get("tool_count")) not in text:
        errors.append("corpus must record measured tool_count from mcp-tools.json")
    if str(tools.get("action_count")) not in text:
        errors.append("corpus must record measured action_count from mcp-tools.json")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png|wav|ogg)", self_text):
        errors.append("official test writes a resource path directly")
    if re.search(r"\.write_bytes\(", self_text):
        errors.append("official test must not write dummy image/audio bytes")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record PlaceholderTexture2D / Play Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "do NOT call play.start" not in self_text:
        errors.append("official test must not call play.start")
    if "PlaceholderTexture2D" not in self_text or "AudioStreamGenerator" not in self_text:
        errors.append("official test must name PlaceholderTexture2D and AudioStreamGenerator")
    if "r5w7" not in self_text or "MCP" not in self_text:
        errors.append("official test must build the museum via plugin MCP under r5w7")
    if "COVERAGE_2D.md" not in self_text:
        errors.append("official test must require the TRACE REPORT")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if re.search(r"test_[a-z0-9_]+\.live_errors\(", self_text):
        errors.append("official test must cite R3-R5 tests, not re-run their live_errors")
    for cited in CITE_OFFICIAL:
        if cited not in self_text:
            errors.append(f"official test must cite {cited}")
        if not (REPO_ROOT / cited).is_file():
            errors.append(f"cited official test missing: {cited}")
    errors.extend(coverage_errors())
    errors.extend(corpus_errors())
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
    scene = "res://r5w7/museum.tscn"
    atlas = "res://r5w7/atlas_tex.tres"
    tileset = "res://r5w7/tiles.tres"
    frames = "res://r5w7/frames.tres"
    theme_p = "res://r5w7/theme.tres"
    stream = "res://r5w7/sfx_gen.tres"
    shader_p = "res://r5w7/tint.gdshader"
    key_tex = "res://r5w7/key.tres"
    script_p = "res://r5w7/spare.gd"
    layout = "res://r5w7/buses.tres"
    restore_layout = "res://r5w7/buses_restore.tres"
    req_id = 2
    isolated = False
    previous_layout = ""
    # Honest Alternatives:
    # screenshots=SKIP (R6)
    # Museum Play sạch = scene.save + reopen hash, not F5 / play.start
    # play.start is not paper-ACK'd
    # PlaceholderTexture2D / AudioStreamGenerator builtin
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
            ("TileMapLayer", "Ground", "."),
            ("AnimatedSprite2D", "PlayerSprite", "."),
            ("AnimatedSprite2D", "NpcSprite", "."),
            ("AnimationPlayer", "Anim", "."),
            ("CharacterBody2D", "Player", "."),
            ("CollisionShape2D", "Shape", "Player"),
            ("Camera2D", "Cam", "Player"),
            ("NavigationAgent2D", "Agent", "Player"),
            ("StaticBody2D", "Wall", "."),
            ("CollisionShape2D", "Shape", "Wall"),
            ("Area2D", "Interact", "."),
            ("CollisionShape2D", "Shape", "Interact"),
            ("NavigationRegion2D", "Nav", "."),
            ("AudioStreamPlayer", "SfxPlayer", "."),
            ("Sprite2D", "ShaderSprite", "."),
            ("Sprite2D", "KeyIcon", "."),
            ("CanvasLayer", "HUD", "."),
            ("Label", "KeyCount", "HUD"),
            ("Control", "PauseMenu", "HUD"),
            ("Button", "Resume", "HUD/PauseMenu"),
            ("Button", "Restart", "HUD/PauseMenu"),
            ("Button", "Quit", "HUD/PauseMenu"),
            ("Node2D", "Spare", "."),
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

        req_id, layer10 = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {"scene": scene, "node_path": "HUD", "property": "layer", "value": variant("int", 10)},
        )
        if not ack_ok(layer10, errors, "property.set HUD.layer"):
            return errors
        req_id, always = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "HUD/PauseMenu",
                "property": "process_mode",
                "value": variant("int", PROCESS_MODE_ALWAYS),
            },
        )
        if not ack_ok(always, errors, "property.set PauseMenu.process_mode"):
            return errors
        req_id, key_label = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {"scene": scene, "node_path": "HUD/KeyCount", "property": "text", "value": variant("string", "Keys 0")},
        )
        if not ack_ok(key_label, errors, "property.set KeyCount.text"):
            return errors

        req_id, tex = tool_call(proc, req_id, "godot.resource", "create", {"path": atlas, "class_name": "PlaceholderTexture2D"})
        if not ack_ok(tex, errors, "resource.create PlaceholderTexture2D"):
            return errors
        req_id, sized = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": atlas, "property": "size", "value": variant("Vector2", {"x": 32, "y": 16})},
        )
        if not ack_ok(sized, errors, "resource.edit atlas size"):
            return errors
        req_id, set_created = tool_call(proc, req_id, "godot.resource", "create", {"path": tileset, "class_name": "TileSet"})
        if not ack_ok(set_created, errors, "resource.create TileSet"):
            return errors
        req_id, sourced = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "source",
            {
                "tileset": tileset,
                "source_id": 0,
                "texture": atlas,
                "op": "add",
                "texture_region_size": 16,
                "create_tiles": True,
            },
        )
        if not ack_ok(sourced, errors, "tilemap.source"):
            return errors
        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "tileset",
            {"scene": scene, "node_path": "Ground", "tileset": tileset, "op": "assign", "tile_size": 16},
        )
        if not ack_ok(assigned, errors, "tilemap.tileset"):
            return errors
        req_id, walls = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "layer",
            {"scene": scene, "node_path": "Walls", "enabled": True, "op": "add", "name": "Walls", "parent": "."},
        )
        if not ack_ok(walls, errors, "tilemap.layer add Walls"):
            return errors
        req_id, filled = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "fill",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 0,
                "y": 0,
                "w": 4,
                "h": 3,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
            },
        )
        if not ack_ok(filled, errors, "tilemap.fill"):
            return errors
        req_id, painted = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "cell",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 1,
                "y": 1,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
            },
        )
        if not ack_ok(painted, errors, "tilemap.cell"):
            return errors
        req_id, erased = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "cell",
            {
                "scene": scene,
                "node_path": "Ground",
                "x": 3,
                "y": 2,
                "source_id": 0,
                "atlas_x": 0,
                "atlas_y": 0,
                "erase": True,
            },
        )
        if not ack_ok(erased, errors, "tilemap.cell erase"):
            return errors
        if (erased.get("after") or {}).get("erased") is not True:
            errors.append(f"tilemap.cell erase flag: {erased}")
        req_id, q_erase = tool_call(
            proc,
            req_id,
            "godot.tilemap",
            "query",
            {"scene": scene, "node_path": "Ground", "x": 3, "y": 2, "w": 1, "h": 1},
        )
        if ack_ok(q_erase, errors, "tilemap.query erased cell"):
            cells = (q_erase.get("after") or {}).get("cells")
            cell0 = cells[0] if isinstance(cells, list) and cells else {}
            if int((cell0 or {}).get("source_id", 0)) != -1:
                errors.append(f"erased cell still occupied: {q_erase}")

        for clip in ("idle", "walk"):
            req_id, framed = tool_call(
                proc,
                req_id,
                "godot.animation",
                "sprite_frames",
                {
                    "scene": scene,
                    "node_path": "PlayerSprite",
                    "animation": clip,
                    "path": frames,
                    "op": "add_animation",
                    "speed": 8,
                    "loop": True,
                    "frames": [{"texture": atlas, "duration": 1.0}],
                },
            )
            if not ack_ok(framed, errors, f"animation.sprite_frames {clip}"):
                return errors
        req_id, npc_frames = tool_call(
            proc,
            req_id,
            "godot.animation",
            "sprite_frames",
            {
                "scene": scene,
                "node_path": "NpcSprite",
                "animation": "idle",
                "path": frames,
                "op": "add_animation",
                "speed": 6,
                "loop": True,
                "frames": [{"texture": atlas, "duration": 1.0}],
            },
        )
        if not ack_ok(npc_frames, errors, "animation.sprite_frames NPC idle"):
            return errors
        req_id, lib = tool_call(
            proc, req_id, "godot.animation", "library", {"scene": scene, "node_path": "Anim", "library": "player"}
        )
        if not ack_ok(lib, errors, "animation.library"):
            return errors
        req_id, walk = tool_call(
            proc,
            req_id,
            "godot.animation",
            "animation",
            {
                "scene": scene,
                "node_path": "Anim",
                "name": "walk",
                "length_sec": 0.4,
                "library": "player",
                "loop": True,
            },
        )
        if not ack_ok(walk, errors, "animation.animation walk"):
            return errors

        req_id, theme_created = tool_call(proc, req_id, "godot.resource", "create", {"path": theme_p, "class_name": "Theme"})
        if not ack_ok(theme_created, errors, "resource.create Theme"):
            return errors
        req_id, themed = tool_call(
            proc,
            req_id,
            "godot.ui",
            "theme",
            {
                "scene": scene,
                "node_path": "HUD/PauseMenu",
                "theme": theme_p,
                "font_sizes": [{"name": "font_size", "theme_type": "Label", "size": 16}],
            },
        )
        if not ack_ok(themed, errors, "ui.theme"):
            return errors

        req_id, posed = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {"scene": scene, "node_path": "Player", "property": "position", "value": variant("Vector2", {"x": 80, "y": 80})},
        )
        if not ack_ok(posed, errors, "property.set Player.position"):
            return errors
        req_id, cam = tool_call(
            proc, req_id, "godot.camera", "make_current", {"scene": scene, "node_path": "Player/Cam"}
        )
        if not ack_ok(cam, errors, "camera.make_current"):
            return errors
        req_id, body = tool_call(
            proc,
            req_id,
            "godot.physics",
            "body",
            {"scene": scene, "node_path": "Player", "motion_mode": "floating"},
        )
        if not ack_ok(body, errors, "physics.body Player floating"):
            return errors
        if (body.get("after") or {}).get("motion_mode") != "floating":
            errors.append(f"physics.body motion_mode: {body}")
        req_id, pshape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {"scene": scene, "node_path": "Player/Shape", "shape": "rectangle", "size": {"x": 16, "y": 16}},
        )
        if not ack_ok(pshape, errors, "physics.shape Player"):
            return errors
        req_id, wshape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {"scene": scene, "node_path": "Wall/Shape", "shape": "rectangle", "size": {"x": 40, "y": 80}},
        )
        if not ack_ok(wshape, errors, "physics.shape Wall"):
            return errors
        req_id, ishape = tool_call(
            proc,
            req_id,
            "godot.physics",
            "shape",
            {"scene": scene, "node_path": "Interact/Shape", "shape": "circle", "radius": 12},
        )
        if not ack_ok(ishape, errors, "physics.shape Interact"):
            return errors
        for node_path, layer, mask, fixture in (
            ("Player", 1, 2, "player"),
            ("Wall", 2, 1, "world"),
            ("Interact", 4, 1, "interact"),
        ):
            req_id, layered = tool_call(
                proc,
                req_id,
                "godot.physics",
                "layers",
                {
                    "scene": scene,
                    "node_path": node_path,
                    "collision_layer": layer,
                    "collision_mask": mask,
                    "fixture": fixture,
                },
            )
            if not ack_ok(layered, errors, f"physics.layers {node_path}"):
                return errors
        req_id, nav = tool_call(
            proc,
            req_id,
            "godot.physics",
            "nav_region",
            {
                "scene": scene,
                "node_path": "Nav",
                "outline": [
                    {"x": 0, "y": 0},
                    {"x": 256, "y": 0},
                    {"x": 256, "y": 192},
                    {"x": 0, "y": 192},
                ],
            },
        )
        if not ack_ok(nav, errors, "physics.nav_region"):
            return errors
        req_id, agent = tool_call(
            proc,
            req_id,
            "godot.physics",
            "nav_agent",
            {"scene": scene, "node_path": "Player/Agent", "target_position": {"x": 200, "y": 80}},
        )
        if not ack_ok(agent, errors, "physics.nav_agent"):
            return errors

        req_id, gen = tool_call(
            proc, req_id, "godot.resource", "create", {"path": stream, "class_name": "AudioStreamGenerator"}
        )
        if not ack_ok(gen, errors, "resource.create AudioStreamGenerator"):
            return errors
        req_id, bused = tool_call(
            proc,
            req_id,
            "godot.audio",
            "bus",
            {
                "bus": "R5W7SFX",
                "add": True,
                "send": "Master",
                "mute": False,
                "volume_db": -6,
                "isolate": True,
                "layout": layout,
                "restore_layout": restore_layout,
            },
        )
        if not ack_ok(bused, errors, "audio.bus isolate"):
            return errors
        isolated = True
        previous_layout = str((bused.get("after") or {}).get("previous_layout") or "")
        req_id, player = tool_call(
            proc,
            req_id,
            "godot.audio",
            "player",
            {"scene": scene, "node_path": "SfxPlayer", "stream": stream, "bus": "R5W7SFX", "volume_db": -4},
        )
        if not ack_ok(player, errors, "audio.player"):
            return errors
        if (player.get("after") or {}).get("heard") is True:
            errors.append(f"audio.player must not claim heard SFX: {player}")

        req_id, shade = tool_call(
            proc,
            req_id,
            "godot.render",
            "shader",
            {
                "scene": scene,
                "node_path": "ShaderSprite",
                "shader": shader_p,
                "code": GOOD_SHADER,
                "required_uniform": "tint",
                "mode": "canvas_item",
            },
        )
        if not ack_ok(shade, errors, "render.shader canvas_item"):
            return errors
        if (shade.get("after") or {}).get("mode") != "MODE_CANVAS_ITEM":
            errors.append(f"shader mode: {shade}")

        req_id, wrote = tool_call(proc, req_id, "godot.script", "write", {"path": script_p, "contents": SPARE_SCRIPT})
        if not ack_ok(wrote, errors, "script.write"):
            return errors
        req_id, attached = tool_call(
            proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": "Spare", "path": script_p}
        )
        if not ack_ok(attached, errors, "script.attach"):
            return errors
        req_id, detached = tool_call(proc, req_id, "godot.script", "detach", {"scene": scene, "node_path": "Spare"})
        if not ack_ok(detached, errors, "script.detach"):
            return errors
        if (detached.get("after") or {}).get("attached") is not False:
            errors.append(f"script.detach still attached: {detached}")

        req_id, key_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": key_tex, "class_name": "PlaceholderTexture2D"}
        )
        if not ack_ok(key_created, errors, "resource.create key.tres"):
            return errors
        req_id, key_assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "KeyIcon", "property": "texture", "resource": key_tex},
        )
        if not ack_ok(key_assigned, errors, "resource.assign KeyIcon.texture"):
            return errors
        req_id, saved_for_rename = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved_for_rename, errors, "scene.save before rename"):
            return errors
        req_id, renamed = tool_call(
            proc,
            req_id,
            "godot.asset",
            "rename",
            {"path": key_tex, "name": "key_gold", "rewrite_plan": True},
        )
        if not ack_ok(renamed, errors, "asset.rename key_gold rewrite_plan"):
            return errors
        ra = renamed.get("after") or {}
        if ra.get("path") != "res://r5w7/key_gold.tres":
            errors.append(f"asset.rename dest: {ra}")
        if ra.get("old_path_absent") is not True:
            errors.append(f"asset.rename left the old path: {ra}")
        req_id, key_get = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "KeyIcon", "property": "texture"},
        )
        if ack_ok(key_get, errors, "property.get KeyIcon.texture after rename"):
            tex_v = (key_get.get("after") or {}).get("value")
            blob = json.dumps(tex_v)
            if "key_gold.tres" not in blob and "uid://" not in blob:
                errors.append(f"rename did not keep a live texture ref: {key_get}")

        req_id, screen = tool_call(proc, req_id, "godot.editor", "main_screen", {"screen": "2D"})
        if not ack_ok(screen, errors, "editor.main_screen 2D"):
            return errors
        req_id, selected = tool_call(
            proc, req_id, "godot.editor", "select", {"scene": scene, "node_path": "Player"}
        )
        if not ack_ok(selected, errors, "editor.select Player"):
            return errors
        req_id, focused = tool_call(
            proc, req_id, "godot.editor", "focus", {"scene": scene, "node_path": "Player"}
        )
        if not ack_ok(focused, errors, "editor.focus Player"):
            return errors

        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors
        hash_before = str((saved.get("after") or {}).get("disk_hash") or "")
        if len(hash_before) < 16:
            errors.append(f"scene.save missing disk_hash: {saved}")
        req_id, read_before = tool_call(
            proc, req_id, "godot.scene", "read", {"path": scene, "detail": "short"}
        )
        if not ack_ok(read_before, errors, "scene.read before reload"):
            return errors

        req_id, reloaded = tool_call(proc, req_id, "godot.scene", "reload", {"path": scene})
        if not ack_ok(reloaded, errors, "scene.reload"):
            return errors
        hash_after = str((reloaded.get("after") or {}).get("disk_hash") or "")
        if hash_before and hash_after and hash_before != hash_after:
            errors.append(f"save/reopen disk_hash drifted: {hash_before} -> {hash_after}")

        req_id, q_after = tool_call(
            proc, req_id, "godot.tilemap", "query", {"scene": scene, "node_path": "Ground", "x": 0, "y": 0, "w": 4, "h": 3}
        )
        if not ack_ok(q_after, errors, "tilemap.query after reload"):
            return errors
        req_id, hud_layer = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "HUD", "property": "layer"}
        )
        if ack_ok(hud_layer, errors, "property.get HUD.layer after reload"):
            got = (hud_layer.get("after") or {}).get("value")
            val = got.get("value") if isinstance(got, dict) else got
            if int(val or 0) != 10:
                errors.append(f"HUD layer readback: {hud_layer}")
        req_id, mode_get = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "HUD/PauseMenu", "property": "process_mode"},
        )
        if ack_ok(mode_get, errors, "property.get PauseMenu.process_mode after reload"):
            got = (mode_get.get("after") or {}).get("value")
            val = got.get("value") if isinstance(got, dict) else got
            if int(val or 0) != PROCESS_MODE_ALWAYS:
                errors.append(f"PauseMenu process_mode readback: {mode_get}")
        req_id, read_after = tool_call(
            proc, req_id, "godot.scene", "read", {"path": scene, "detail": "short"}
        )
        if not ack_ok(read_after, errors, "scene.read after reload"):
            return errors
        tree_blob = json.dumps(read_after.get("after") or {})
        for needle in (
            "Ground",
            "Anim",
            "HUD",
            "Player",
            "Nav",
            "SfxPlayer",
            "ShaderSprite",
            "PauseMenu",
            "KeyCount",
        ):
            if needle not in tree_blob:
                errors.append(f"scene.read missing {needle}: {read_after}")

        if isolated:
            restore_params = {
                "bus": "R5W7SFX",
                "restore": True,
                "restore_layout": restore_layout,
                "previous_layout": previous_layout,
            }
            req_id, restored = tool_call(proc, req_id, "godot.audio", "bus", restore_params)
            if not ack_ok(restored, errors, "audio.bus restore"):
                errors.append(f"must restore isolated bus layout: {restored}")
            isolated = False

        if _screenshots != "SKIP":
            errors.append("coverage screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live coverage museum failed: {type(exc).__name__}: {exc}", secret))
    finally:
        if isolated and proc is not None and proc.poll() is None:
            try:
                tool_call(
                    proc,
                    90,
                    "godot.audio",
                    "bus",
                    {
                        "bus": "R5W7SFX",
                        "restore": True,
                        "restore_layout": restore_layout,
                        "previous_layout": previous_layout,
                    },
                )
            except Exception:
                pass
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
        print("FAIL: coverage_2d", file=sys.stderr)
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
        print("FAIL: coverage_2d", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: 2D coverage TRACE REPORT P0=100% P1>=90%; museum via plugin; "
        f"save/reopen; screenshots={SCREENSHOTS}; play.start not paper-ACK'd"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
