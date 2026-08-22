#!/usr/bin/env python3
"""R5-WP6: Audio, shader, particles and quality adapters.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.
Do not raw-edit .tscn/.tres/.gdshader bytes. Plugin is the only writer.
No dummy WAV/OGG bytes. Stream is AudioStreamGenerator builtin.

Verify (encoded here; this file is the official harness):
  - AudioStreamPlayer + AudioStreamGenerator + named SFX bus + volume_db
  - Not heard. Do not call play() as heard-SFX proof
  - Bus mute/volume set+get; layout .tres disk_hash if saved
  - Isolate r5w6 bus layout and restore
  - Good shader: canvas_item + required uniform; MODE_CANVAS_ITEM; param set/get
  - Bad shader: missing shader_type / garbage → not ok:true
  - GPUParticles2D amount/lifetime/process_material; invented_box!==true
  - Quality light/modulate + Compatibility glow/volumetric fallback honest
  - one Agent: UndoRedo
  - scene.save + reopen hash
  - do NOT call play.start

Honest Alternatives named here:
  - screenshots=SKIP (R6)
  - hearing SFX / particle screenshot/perf = deferred R6
  - playing==true is not heard; Alternative: editor assign only
  - play.start is not paper-ACK'd
  - license=AudioStreamGenerator builtin (not a fake CC license)

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
TEMP_DIR = PLUGIN_PROJECT / "r5w6"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"
AUDIO_MUTATES = ("audio.player", "audio.bus")
RENDER_MUTATES = ("render.shader", "render.particles", "render.quality")
AUDIO_VERBS = ("player", "bus", "preview")
RENDER_VERBS = ("shader", "particles", "quality")
GOOD_SHADER = """shader_type canvas_item;

uniform vec4 tint : source_color = vec4(1.0);

void fragment() {
	COLOR = texture(TEXTURE, UV) * tint;
}
"""
BAD_MISSING_TYPE = """void fragment() {
	COLOR = vec4(1.0);
}
"""
BAD_GARBAGE = "this is not a shader at all !!!"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP6 [ ]; while unticked require CURRENT_VALID_WP=R5-WP6."""
    errors: list[str] = []
    current = ""
    wp6 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP6\b", stripped):
            wp6 = stripped
    if wp6 is None:
        return ["plan missing R5-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R5-WP6 heading must keep [ ] until coordinator tick")
        if current != "R5-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP6 while WP6 is unticked)")
    elif not re.match(r"^R5-WP([7-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP7+ after R5-WP6 tick)")
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
    return {"schema": "hh-godot-variant/1", "type": typ, "value": value}


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
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png|gdshader|wav|ogg)", self_text):
        errors.append("official test writes a resource path directly")
    if re.search(r"\.write_bytes\(", self_text):
        errors.append("official test must not write dummy audio/image bytes")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record heard/screenshot Alternatives honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "deferred R6" not in self_text:
        errors.append("official test must defer hearing SFX / particle screenshot/perf to R6")
    if "AudioStreamGenerator builtin" not in self_text:
        errors.append("official test must label license=AudioStreamGenerator builtin")
    if "g2_" + "signed" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "godot.play" in self_text and "start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must not call play.start")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_audio_adapter" not in router:
        errors.append("router must dispatch through hh_audio_adapter")
    if "hh_render_adapter" not in router:
        errors.append("router must dispatch through hh_render_adapter")
    if "godot.audio" not in router:
        errors.append("router must name godot.audio")
    if "godot.render" not in router:
        errors.append("router must name godot.render")

    audio_adapter = ADDON / "core" / "hh_audio_adapter.gd"
    if not audio_adapter.is_file():
        errors.append("missing hh_audio_adapter.gd")
    else:
        text = audio_adapter.read_text(encoding="utf-8")
        for needle in (
            "AudioStreamGenerator",
            "set_bus_mute",
            "get_bus_volume_db",
            "generate_bus_layout",
            "UNDO_ACTION_PREFIX",
            "create_action",
            "is_bus_mute",
            "set_bus_volume_db",
            "get_bus_index",
            "add_bus",
            "set_bus_name",
            "set_bus_send",
        ):
            if needle not in text:
                errors.append(f"audio adapter must use {needle}")
        if "AudioStreamPlaceholder" in text:
            errors.append("audio adapter must not use AudioStreamPlaceholder")
        if "AudioStreamSample" in text:
            errors.append("audio adapter must not use Godot 3 AudioStreamSample")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("audio adapter has a generic invoke path")
        if "Vector2(32, 32)" in text:
            errors.append("audio adapter must not invent a 32px box")
        if "write_bytes" in text or ("RI" + "FF") in text:
            errors.append("audio adapter must not invent dummy WAV bytes")
        if "Alternative" not in text:
            errors.append("audio adapter must label heard Alternative honestly")
        if "AudioStreamGenerator builtin" not in text:
            errors.append("audio adapter must label license=AudioStreamGenerator builtin")

    render_adapter = ADDON / "core" / "hh_render_adapter.gd"
    if not render_adapter.is_file():
        errors.append("missing hh_render_adapter.gd")
    else:
        text = render_adapter.read_text(encoding="utf-8")
        for needle in (
            "get_mode",
            "get_shader_uniform_list",
            "set_shader_parameter",
            "get_shader_parameter",
            "GPUParticles2D",
            "ParticleProcessMaterial",
            "MODE_CANVAS_ITEM",
            "get_current_rendering_method",
            "UNDO_ACTION_PREFIX",
            "create_action",
            "get_rect",
        ):
            if needle not in text:
                errors.append(f"render adapter must use {needle}")
        if "set_shader_param" in text and "set_shader_parameter" not in text:
            errors.append("render adapter must not use Godot 3 set_shader_param")
        if "set_shader_param(" in text:
            errors.append("render adapter must not call set_shader_param")
        if "Particles2D" in text and "GPUParticles2D" not in text:
            errors.append("render adapter must not use Godot 3 Particles2D")
        if re.search(r"\bParticles2D\b", text):
            errors.append("render adapter must not use Particles2D")
        if "Shader.compile" in text or "has_compile_error" in text:
            errors.append("render adapter must not invent Shader.compile()")
        if "script.write" in text:
            errors.append("render adapter must not write .gdshader via script.write")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("render adapter has a generic invoke path")
        if "Vector2(32, 32)" in text:
            errors.append("render adapter must not invent a 32px particle box")
        if "VisualServer" in text:
            errors.append("render adapter must not use Godot 3 VisualServer")

    overlay = (ADDON / "ui" / "overlay" / "hh_overlay.gd").read_text(encoding="utf-8")
    if "godot.audio" not in overlay:
        errors.append("overlay must treat godot.audio as presentable")
    if "godot.render" not in overlay:
        errors.append("overlay must treat godot.render as presentable")
    if "engine_world_rect" not in overlay:
        errors.append("overlay must use engine AABB, invented_box=false")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("audio.player", "godot.audio", "player"),
            ("audio.bus", "godot.audio", "bus"),
            ("audio.preview", "godot.audio", "preview"),
            ("render.shader", "godot.render", "shader"),
            ("render.particles", "godot.render", "particles"),
            ("render.quality", "godot.render", "quality"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "AUDIO_APPLY" not in lifecycle or "isAudioApply" not in lifecycle:
        errors.append("scene_lifecycle must export AUDIO_APPLY / isAudioApply")
    if "RENDER_APPLY" not in lifecycle or "isRenderApply" not in lifecycle:
        errors.append("scene_lifecycle must export RENDER_APPLY / isRenderApply")
    if "isAudioApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isAudioApply")
    if "isRenderApply(actionId)" not in lifecycle:
        errors.append("isProvenEditorApply must include isRenderApply")
    for action_id in AUDIO_MUTATES + RENDER_MUTATES:
        if action_id not in lifecycle:
            errors.append(f"isProvenEditorApply must list {action_id}")
    audio_block = lifecycle.split("AUDIO_APPLY")[1].split("]")[0] if "AUDIO_APPLY" in lifecycle else ""
    if "audio.preview" in audio_block:
        errors.append("AUDIO_APPLY must not include preview")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function audioApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check audio apply")
    if "function renderApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check render apply")
    if "const audioFail = audioApplyOk" not in execute:
        errors.append("execute.ts must call audioApplyOk from applyMutateOnce")
    if "const renderFail = renderApplyOk" not in execute:
        errors.append("execute.ts must call renderApplyOk from applyMutateOnce")
    if '"audio"' not in execute:
        errors.append("execute.ts after_summary must use kind audio")
    if '"render"' not in execute:
        errors.append("execute.ts after_summary must use kind render")

    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if "isAudioApply(def.id)" not in resources or '"audio"' not in resources:
        errors.append("mcp_resources.ts must label audio apply as the audio adapter")
    if "isRenderApply(def.id)" not in resources or '"render"' not in resources:
        errors.append("mcp_resources.ts must label render apply as the render adapter")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("audio.player", "godot.audio", "player"),
        ("audio.bus", "godot.audio", "bus"),
        ("audio.preview", "godot.audio", "preview"),
        ("render.shader", "godot.render", "shader"),
        ("render.particles", "godot.render", "particles"),
        ("render.quality", "godot.render", "quality"),
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
    for domain_name, verbs in (("godot.audio", AUDIO_VERBS), ("godot.render", RENDER_VERBS)):
        domain = tool_enums.get(domain_name, [])
        for verb in verbs:
            if verb not in domain:
                errors.append(f"mcp-tools.json {domain_name} must enum {verb}")
        if domain_name not in tool_enums:
            errors.append(f"mcp-tools.json must expose {domain_name} as a domain tool")

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
    scene = "res://r5w6/stage.tscn"
    stream = "res://r5w6/sfx_gen.tres"
    shader_p = "res://r5w6/tint.gdshader"
    proc_mat = "res://r5w6/spark_proc.tres"
    tex = "res://r5w6/spark_tex.tres"
    env_p = "res://r5w6/world_env.tres"
    layout = "res://r5w6/buses.tres"
    restore_layout = "res://r5w6/buses_restore.tres"
    req_id = 2
    previous_layout = ""
    isolated = False
    # Honest Alternatives:
    # screenshots=SKIP (R6)
    # hearing SFX / particle screenshot/perf = deferred R6
    # playing==true is not heard; Alternative: editor assign only
    # play.start is not paper-ACK'd
    # license=AudioStreamGenerator builtin
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
            ("AudioStreamPlayer", "SFX", "."),
            ("Sprite2D", "Sprite", "."),
            ("GPUParticles2D", "Sparks", "."),
            ("PointLight2D", "Light", "."),
            ("CanvasModulate", "Modulate", "."),
            ("WorldEnvironment", "WorldEnv", "."),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": parent, "class_name": class_name, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {name}"):
                return errors

        req_id, gen = tool_call(
            proc, req_id, "godot.resource", "create", {"path": stream, "class_name": "AudioStreamGenerator"}
        )
        if not ack_ok(gen, errors, "resource.create AudioStreamGenerator"):
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

        req_id, bused = tool_call(
            proc,
            req_id,
            "godot.audio",
            "bus",
            {
                "bus": "R5W6SFX",
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
        ba = bused.get("after") or {}
        previous_layout = str(ba.get("previous_layout") or "")
        if ba.get("bus") != "R5W6SFX":
            errors.append(f"audio.bus name bind: {ba}")
        if ba.get("mute") is not False:
            errors.append(f"audio.bus mute bind: {ba}")
        if abs(float(ba.get("volume_db") or 0) + 6) > 0.01:
            errors.append(f"audio.bus volume_db bind: {ba}")
        if ba.get("durable") is True:
            if len(str(ba.get("disk_hash") or "")) < 16:
                errors.append(f"audio.bus layout missing disk_hash: {ba}")
        if not str(bused.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"audio.bus missing Agent undo: {bused}")

        req_id, muted = tool_call(
            proc,
            req_id,
            "godot.audio",
            "bus",
            {"bus": "R5W6SFX", "mute": True, "volume_db": -12, "layout": layout},
        )
        if not ack_ok(muted, errors, "audio.bus mute/volume"):
            return errors
        mu = muted.get("after") or {}
        if mu.get("mute") is not True or abs(float(mu.get("volume_db") or 0) + 12) > 0.01:
            errors.append(f"audio.bus mute/volume readback: {mu}")

        req_id, player = tool_call(
            proc,
            req_id,
            "godot.audio",
            "player",
            {"scene": scene, "node_path": "SFX", "stream": stream, "bus": "R5W6SFX", "volume_db": -4},
        )
        if not ack_ok(player, errors, "audio.player"):
            return errors
        pa = player.get("after") or {}
        if pa.get("stream_class") != "AudioStreamGenerator":
            errors.append(f"audio.player stream class: {pa}")
        if pa.get("bus") != "R5W6SFX":
            errors.append(f"audio.player bus: {pa}")
        if abs(float(pa.get("volume_db") or 0) + 4) > 0.01:
            errors.append(f"audio.player volume_db: {pa}")
        if pa.get("heard") is True:
            errors.append(f"audio.player must not claim heard SFX: {pa}")
        if pa.get("license") != "AudioStreamGenerator builtin":
            errors.append(f"audio.player license: {pa}")
        if not str(player.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"audio.player missing Agent undo: {player}")

        req_id, preview = tool_call(
            proc, req_id, "godot.audio", "preview", {"scene": scene, "node_path": "SFX"}
        )
        if not ack_ok(preview, errors, "audio.preview"):
            return errors
        pr = preview.get("after") or {}
        if pr.get("heard") is True or pr.get("heard_proven") is True:
            errors.append(f"audio.preview must not paper-ACK heard: {pr}")
        if "Alternative" not in json.dumps(pr):
            errors.append(f"audio.preview must label Alternative: {pr}")

        req_id, good = tool_call(
            proc,
            req_id,
            "godot.render",
            "shader",
            {
                "scene": scene,
                "node_path": "Sprite",
                "shader": shader_p,
                "code": GOOD_SHADER,
                "required_uniform": "tint",
                "mode": "canvas_item",
                "parameters": {"tint": {"r": 1, "g": 0.2, "b": 0.4, "a": 1}},
            },
        )
        if not ack_ok(good, errors, "render.shader good"):
            return errors
        ga = good.get("after") or {}
        if ga.get("shader") != shader_p:
            errors.append(f"good shader path: {ga}")
        if ga.get("mode") != "MODE_CANVAS_ITEM":
            errors.append(f"good shader mode: {ga}")
        uniforms = ga.get("uniforms") if isinstance(ga.get("uniforms"), list) else []
        if "tint" not in uniforms:
            errors.append(f"good shader uniform list missing tint: {ga}")
        if ga.get("invented_box") is True:
            errors.append(f"shader invented_box: {ga}")
        if not str(good.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"render.shader missing Agent undo: {good}")

        req_id, missing = tool_call(
            proc,
            req_id,
            "godot.render",
            "shader",
            {
                "scene": scene,
                "node_path": "Sprite",
                "shader": "res://r5w6/bad_missing.gdshader",
                "code": BAD_MISSING_TYPE,
                "required_uniform": "tint",
            },
        )
        if missing.get("ok") is True:
            errors.append(f"missing shader_type must not be ok:true: {missing}")

        req_id, garbage = tool_call(
            proc,
            req_id,
            "godot.render",
            "shader",
            {
                "scene": scene,
                "node_path": "Sprite",
                "shader": "res://r5w6/bad_garbage.gdshader",
                "code": BAD_GARBAGE,
            },
        )
        if garbage.get("ok") is True:
            errors.append(f"garbage shader must not be ok:true: {garbage}")

        req_id, parts = tool_call(
            proc,
            req_id,
            "godot.render",
            "particles",
            {
                "scene": scene,
                "node_path": "Sparks",
                "amount": 16,
                "lifetime": 0.5,
                "process_material": proc_mat,
                "texture": tex,
            },
        )
        if not ack_ok(parts, errors, "render.particles"):
            return errors
        pta = parts.get("after") or {}
        if int(pta.get("amount") or 0) != 16:
            errors.append(f"particles amount: {pta}")
        if abs(float(pta.get("lifetime") or 0) - 0.5) > 0.01:
            errors.append(f"particles lifetime: {pta}")
        if pta.get("process_material_class") != "ParticleProcessMaterial":
            errors.append(f"particles process_material: {pta}")
        if pta.get("invented_box") is True:
            errors.append(f"particles invented_box: {pta}")

        req_id, light = tool_call(
            proc,
            req_id,
            "godot.render",
            "quality",
            {
                "scene": scene,
                "node_path": "Light",
                "energy": 2,
                "color": {"r": 1, "g": 0.8, "b": 0.2, "a": 1},
                "shadow_enabled": True,
            },
        )
        if not ack_ok(light, errors, "render.quality Light"):
            return errors
        la = light.get("after") or {}
        if abs(float(la.get("energy") or 0) - 2) > 0.01:
            errors.append(f"light energy: {la}")
        if la.get("shadow_enabled") is not True:
            errors.append(f"light shadow: {la}")
        if not str(light.get("undo_action") or "").startswith("Agent: "):
            errors.append(f"render.quality missing Agent undo: {light}")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after quality"):
            errors.append(f"one-undo after quality must ACK: {undone}")
        req_id, after_undo = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "Light", "property": "energy"},
        )
        if ack_ok(after_undo, errors, "property.get Light.energy after undo"):
            got_u = (after_undo.get("after") or {}).get("value")
            val_u = got_u.get("value") if isinstance(got_u, dict) else got_u
            if abs(float(val_u or 0) - 2) < 0.01:
                errors.append(f"one Agent UndoRedo did not restore Light.energy: {after_undo}")

        req_id, redone = tool_call(proc, req_id, "godot.node", "redo", {"scene": scene, "count": 1})
        if not ack_ok(redone, errors, "node.redo after quality undo"):
            errors.append(f"one-redo after quality undo must ACK: {redone}")

        req_id, mod = tool_call(
            proc,
            req_id,
            "godot.render",
            "quality",
            {"scene": scene, "node_path": "Modulate", "color": {"r": 0.2, "g": 0.4, "b": 0.8, "a": 1}},
        )
        if not ack_ok(mod, errors, "render.quality Modulate"):
            return errors
        ma = mod.get("after") or {}
        col = ma.get("color") if isinstance(ma.get("color"), dict) else {}
        if abs(float(col.get("b") or 0) - 0.8) > 0.001:
            errors.append(f"modulate color: {ma}")

        req_id, env = tool_call(
            proc,
            req_id,
            "godot.render",
            "quality",
            {
                "scene": scene,
                "node_path": "WorldEnv",
                "environment": env_p,
                "glow": True,
                "volumetric": True,
            },
        )
        if not ack_ok(env, errors, "render.quality WorldEnv"):
            return errors
        ea = env.get("after") or {}
        method = str(ea.get("rendering_method") or "")
        if not method:
            errors.append(f"quality missing rendering_method: {ea}")
        if method == "gl_compatibility":
            if ea.get("fallback_applied") is not True:
                errors.append(f"Compatibility must set fallback_applied: {ea}")
            if ea.get("glow_applied") is True or ea.get("volumetric_applied") is True:
                errors.append(f"Compatibility must skip glow/volumetric: {ea}")
        elif ea.get("fallback_applied") is True and (ea.get("glow_applied") is True):
            errors.append(f"fallback_applied vs glow_applied inconsistent: {ea}")

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

        if isolated:
            restore_params = {
                "bus": "R5W6SFX",
                "restore": True,
                "restore_layout": restore_layout,
            }
            restore_params["previous_layout"] = previous_layout
            req_id, restored = tool_call(
                proc,
                req_id,
                "godot.audio",
                "bus",
                restore_params,
            )
            if not ack_ok(restored, errors, "audio.bus restore"):
                errors.append(f"must restore isolated bus layout: {restored}")
            isolated = False
            godot_txt = (PLUGIN_PROJECT / "project.godot").read_text(encoding="utf-8")
            if "r5w6" in godot_txt:
                errors.append("audio.bus restore left r5w6 bus layout in project.godot")

        if _screenshots != "SKIP":
            errors.append("audio/render screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live audio/render failed: {type(exc).__name__}: {exc}", secret))
    finally:
        if isolated and proc is not None and proc.poll() is None:
            try:
                restore_params = {
                    "bus": "R5W6SFX",
                    "restore": True,
                    "restore_layout": restore_layout,
                }
                restore_params["previous_layout"] = previous_layout
                tool_call(proc, 90, "godot.audio", "bus", restore_params)
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
        print("FAIL: audio_render", file=sys.stderr)
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
        print("FAIL: audio_render", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: audio player/bus + shader/particles/quality adapters; "
        f"bad shader refused; one-undo; screenshots={SCREENSHOTS}; "
        "heard SFX deferred R6; play.start not paper-ACK'd"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
