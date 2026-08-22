#!/usr/bin/env python3
"""R5-WP1: Transform/Canvas/Camera/visual 2D adapters.

Does not tick the 20-8 plan. G2 is not involved. Pin missing is a hard FAIL.
No skip-PASS. No dummy screenshot PNG. Do not paper-ACK play.start.

Verify (encoded here; this file is the official harness):
  - nested Node2D reparent keep_global_transform=true + global_position readback
  - negative scale + rotation
  - Camera2D.make_current as typed godot.camera / make_current (add_do_method)
  - TextureRect texture assign + flip
  - y_sort_enabled
  - camera screenshot Alternative: screenshots=SKIP (no fake PNG)

Generated plugin-validator.json / mcp-tools.json are coordinator-owned
(`npm run generate`). This WP registers verbs in actions.json + the live
TypeScript catalog. No extra codegen pipeline.
"""

from __future__ import annotations

import json
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
TEMP_DIR = PLUGIN_PROJECT / "r5w1"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCREENSHOTS = "SKIP"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R5-WP1 [ ] while unticked; after coordinator tick allow R5-WP2+."""
    errors: list[str] = []
    current = ""
    wp1 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R5-WP1\b", stripped):
            wp1 = stripped
    if wp1 is None:
        return ["plan missing R5-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R5-WP1 heading must keep [ ] until coordinator tick")
        if current != "R5-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP1 while WP1 is unticked)")
    elif not re.match(r"^R5-WP([2-9]|\d{2,})$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP2+ after R5-WP1 tick)")
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


def canon(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [canon(item) for item in value]
    if isinstance(value, dict):
        return {key: canon(value[key]) for key in sorted(value)}
    return value


def close(a, b) -> bool:
    return _close(canon(a), canon(b))


def _close(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        scale = max(abs(float(a)), abs(float(b)), 1.0)
        return abs(float(a) - float(b)) <= 1e-4 * scale
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(left, right) for left, right in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_close(a[key], b[key]) for key in a)
    return a == b


def xy_of(encoded) -> tuple[float, float] | None:
    if not isinstance(encoded, dict):
        return None
    inner = encoded.get("value") if encoded.get("type") else encoded
    if isinstance(inner, dict) and "type" in inner and "value" in inner:
        inner = inner.get("value")
    if not isinstance(inner, dict):
        return None
    if "x" not in inner or "y" not in inner:
        return None
    return float(inner["x"]), float(inner["y"])


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
        errors.append("official test must record camera screenshot Alternative honestly")
    if "play.start" in self_text and "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "keep_global_transform" not in self_text:
        errors.append("official test must encode reparent keep_global_transform=true")
    if "global_position" not in self_text:
        errors.append("official test must read back global_position")
    if "make_current" not in self_text:
        errors.append("official test must encode typed camera.make_current")
    if "y_sort_enabled" not in self_text:
        errors.append("official test must encode y_sort_enabled")
    if "TextureRect" not in self_text or "flip_h" not in self_text:
        errors.append("official test must encode TextureRect texture assign + flip")
    if "g2_" + "signed =" in self_text or "G2" + " VISIBLE" in self_text:
        errors.append("official test must stay independent of the visible gate")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if re.search(r'"type":\s*"String"', self_text):
        errors.append("variant string type must be lowercase string")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")

    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_canvas_adapter" not in router:
        errors.append("router must dispatch through hh_canvas_adapter")
    if "godot.camera" not in router:
        errors.append("router must name godot.camera")

    adapter = ADDON / "core" / "hh_canvas_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_canvas_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "get_global_transform" not in text or "get_rect" not in text:
            errors.append("canvas adapter must use engine get_global_transform/get_rect")
        if "get_global_rect" not in text:
            errors.append("canvas adapter must use Control.get_global_rect")
        if "make_current" not in text or "add_do_method" not in text:
            errors.append("camera.make_current must be a typed UndoRedo method")
        if re.search(r"\bcallv\b", text) or "Object.call" in text or "evaluate_expression" in text:
            errors.append("canvas adapter has a generic invoke path")
        if "Vector2(32, 32)" in text or "Vector2(16, 16)" in text:
            errors.append("canvas adapter must not invent a 32px box")
        if "layout_batch" not in text or "property" not in text:
            errors.append("canvas.layout_batch must wrap property.batch")
        if "plugin-validator" not in text and "coordinator" not in text:
            errors.append("canvas adapter must note coordinator-owned generated catalog")

    overlay = ADDON / "ui" / "overlay" / "hh_overlay.gd"
    if overlay.is_file():
        ov = overlay.read_text(encoding="utf-8")
        if "engine_world_rect" not in ov:
            errors.append("overlay frame-view must use engine_world_rect, not an invented 32px Sprite box")
        if '.call("get_rect")' in ov:
            errors.append("overlay must not generic-call get_rect")
        if 'action == "layout_batch"' not in ov or 'first.get("node_path"' not in ov:
            errors.append("overlay must bind layout_batch presentation to items[0].node_path")

    codec = (ADDON / "core" / "hh_variant_codec.gd").read_text(encoding="utf-8")
    if 'return _ok("string"' not in codec and '"string"' not in codec:
        errors.append("variant codec must use lowercase string type")
    if "editor-only property is rejected" not in codec:
        errors.append("Editor-only Control.size must stay rejected")

    if not ACTIONS_JSON.is_file():
        errors.append("missing actions.json")
    else:
        catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
        actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
        for action_id, method, verb in (
            ("canvas.bounds", "godot.canvas", "bounds"),
            ("canvas.layout_batch", "godot.canvas", "layout_batch"),
            ("camera.make_current", "godot.camera", "make_current"),
        ):
            spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
            if spec.get("method") != method or spec.get("verb") != verb:
                errors.append(f"actions.json missing {action_id}")

    catalog_ts = BRIDGE / "src" / "registry" / "catalog.ts"
    if catalog_ts.is_file():
        cat = catalog_ts.read_text(encoding="utf-8")
        if "canvas" not in cat or "make_current" not in cat:
            errors.append("live TypeScript catalog must list canvas/camera verbs")

    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    if "canvas.layout_batch" not in lifecycle or "camera.make_current" not in lifecycle:
        errors.append("isProvenEditorApply must list canvas.layout_batch and camera.make_current")
    if "isCanvasApply" not in lifecycle or "isCameraApply" not in lifecycle:
        errors.append("scene_lifecycle must export canvas/camera apply predicates")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "function canvasApplyOk" not in execute or "function cameraApplyOk" not in execute:
        errors.append("execute.ts must postcondition-check canvas/camera apply")
    if "canvas.layout_batch item" not in execute:
        errors.append("execute.ts must bind layout_batch item node_path/property/value")
    if "camera.make_current node bind mismatch" not in execute:
        errors.append("execute.ts must bind camera.make_current to params.node_path")

    validator = json.loads((BRIDGE / "generated" / "plugin-validator.json").read_text(encoding="utf-8"))
    validator_actions = validator.get("actions") if isinstance(validator.get("actions"), dict) else {}
    for action_id, method, verb in (
        ("canvas.bounds", "godot.canvas", "bounds"),
        ("canvas.layout_batch", "godot.canvas", "layout_batch"),
        ("camera.make_current", "godot.camera", "make_current"),
    ):
        spec = validator_actions.get(action_id) if isinstance(validator_actions.get(action_id), dict) else {}
        if spec.get("method") != method or spec.get("verb") != verb:
            errors.append(f"plugin-validator.json missing {action_id}")

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
    if "bounds" not in tool_enums.get("godot.canvas", []) or "layout_batch" not in tool_enums.get(
        "godot.canvas", []
    ):
        errors.append("mcp-tools.json godot.canvas must enum bounds and layout_batch")
    if "make_current" not in tool_enums.get("godot.camera", []):
        errors.append("mcp-tools.json godot.camera must enum make_current")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", blob) or "Object.callv" in blob or "evaluate_expression" in blob:
            errors.append(f"{posix} has a generic invoke path")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 30.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 30.0,
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


def expect_code(body: dict, codes: tuple[str, ...], errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r5w1/layout.tscn"
    tex = "res://r5w1/sprite_tex.tres"
    req_id = 2
    # Honest Alternative: a real editor/runtime viewport PNG is not available
    # here without dummy bytes (runtime.screenshot is R6 / E_UNVERIFIED).
    # screenshots=SKIP — do not write a fake PNG. Do not paper-ACK play.start.
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

        for name, parent, cls in (
            ("ParentA", ".", "Node2D"),
            ("ParentB", ".", "Node2D"),
            ("Child", "ParentA", "Node2D"),
            ("Sprite", "ParentA/Child", "Sprite2D"),
            ("Cam", ".", "Camera2D"),
            ("Hud", ".", "TextureRect"),
            ("SortRoot", ".", "Node2D"),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": parent, "class_name": cls, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {name}"):
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
            {"path": tex, "property": "size", "value": variant("Vector2", {"x": 48, "y": 24})},
        )
        if not ack_ok(tex_sized, errors, "resource.edit PlaceholderTexture2D.size"):
            return errors

        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "ParentA/Child/Sprite", "property": "texture", "resource": tex},
        )
        if not ack_ok(assigned, errors, "resource.assign Sprite.texture"):
            return errors
        req_id, hud_tex = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "Hud", "property": "texture", "resource": tex},
        )
        if not ack_ok(hud_tex, errors, "resource.assign TextureRect.texture"):
            return errors

        req_id, laid = tool_call(
            proc,
            req_id,
            "godot.canvas",
            "layout_batch",
            {
                "scene": scene,
                "items": [
                    {"node_path": "ParentA", "property": "position", "value": variant("Vector2", {"x": 0, "y": 0})},
                    {"node_path": "ParentB", "property": "position", "value": variant("Vector2", {"x": 100, "y": 0})},
                    {
                        "node_path": "ParentA/Child",
                        "property": "position",
                        "value": variant("Vector2", {"x": 10, "y": 20}),
                    },
                    {"node_path": "Hud", "property": "custom_minimum_size", "value": variant("Vector2", {"x": 48, "y": 24})},
                    {"node_path": "Hud", "property": "flip_h", "value": variant("bool", True)},
                    {"node_path": "SortRoot", "property": "y_sort_enabled", "value": variant("bool", True)},
                    {"node_path": "Cam", "property": "limit_left", "value": variant("int", -64)},
                    {"node_path": "Cam", "property": "limit_top", "value": variant("int", -32)},
                    {"node_path": "Cam", "property": "limit_right", "value": variant("int", 640)},
                    {"node_path": "Cam", "property": "limit_bottom", "value": variant("int", 360)},
                    {"node_path": "Cam", "property": "limit_enabled", "value": variant("bool", True)},
                ],
            },
        )
        if not ack_ok(laid, errors, "canvas.layout_batch"):
            return errors
        undo_name = str(laid.get("undo_action") or "")
        if "canvas.layout_batch" not in undo_name:
            errors.append(f"layout_batch must be one Agent UndoRedo: {laid}")
        checks = ((laid.get("postcondition") or {}).get("checks") or [])
        if "layout_batch_one_undo" not in checks:
            errors.append(f"layout_batch missing layout_batch_one_undo: {laid}")

        req_id, gp0 = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "ParentA/Child", "property": "global_position"},
        )
        if not ack_ok(gp0, errors, "property.get global_position before reparent"):
            return errors
        before_xy = xy_of((gp0.get("after") or {}).get("value"))
        if before_xy is None or not close(before_xy, (10.0, 20.0)):
            errors.append(f"Child global_position before reparent: {gp0}")

        req_id, reparented = tool_call(
            proc,
            req_id,
            "godot.node",
            "reparent",
            {
                "scene": scene,
                "node_path": "ParentA/Child",
                "new_parent": "ParentB",
                "keep_global_transform": True,
            },
        )
        if not ack_ok(reparented, errors, "node.reparent keep_global_transform"):
            return errors

        req_id, gp1 = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "ParentB/Child", "property": "global_position"},
        )
        if not ack_ok(gp1, errors, "property.get global_position after keep_global"):
            return errors
        after_xy = xy_of((gp1.get("after") or {}).get("value"))
        if after_xy is None or before_xy is None or not close(after_xy, before_xy):
            errors.append(f"keep_global_transform lost global_position {before_xy} -> {after_xy}: {gp1}")

        req_id, bounds_child = tool_call(
            proc,
            req_id,
            "godot.canvas",
            "bounds",
            {"scene": scene, "node_path": "ParentB/Child"},
        )
        if not ack_ok(bounds_child, errors, "canvas.bounds after keep_global"):
            return errors
        after_b = bounds_child.get("after") or {}
        if after_b.get("used_engine_transform") is not True or after_b.get("invented_box") is True:
            errors.append(f"canvas.bounds must use engine transform, not invented box: {after_b}")
        if after_b.get("source") != "engine":
            errors.append(f"canvas.bounds source must be engine: {after_b}")
        bounds_xy = xy_of(after_b.get("global_position"))
        if bounds_xy is None or before_xy is None or not close(bounds_xy, before_xy):
            errors.append(f"canvas.bounds global_position drifted after keep_global: {after_b}")

        rot = 0.35
        req_id, xform = tool_call(
            proc,
            req_id,
            "godot.canvas",
            "layout_batch",
            {
                "scene": scene,
                "items": [
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "scale",
                        "value": variant("Vector2", {"x": -1.5, "y": 0.5}),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "rotation",
                        "value": variant("float", rot),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "flip_v",
                        "value": variant("bool", True),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "region_enabled",
                        "value": variant("bool", True),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "region_rect",
                        "value": variant("Rect2", {"x": 0, "y": 0, "w": 24, "h": 16}),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "modulate",
                        "value": variant("Color", {"r": 1, "g": 0.4, "b": 0.2, "a": 1}),
                    },
                    {
                        "node_path": "ParentB/Child/Sprite",
                        "property": "z_index",
                        "value": variant("int", 3),
                    },
                ],
            },
        )
        if not ack_ok(xform, errors, "canvas.layout_batch negative scale/rotation"):
            return errors

        req_id, bounds_spr = tool_call(
            proc,
            req_id,
            "godot.canvas",
            "bounds",
            {"scene": scene, "node_path": "ParentB/Child/Sprite"},
        )
        if not ack_ok(bounds_spr, errors, "canvas.bounds Sprite after scale/rotation"):
            return errors
        spr_after = bounds_spr.get("after") or {}
        if spr_after.get("rect_source") != "get_rect":
            errors.append(f"Sprite bounds must use get_rect, not invented box: {spr_after}")
        if spr_after.get("invented_box") is True or spr_after.get("used_engine_transform") is not True:
            errors.append(f"Sprite bounds invented or not engine: {spr_after}")
        scale_xy = xy_of(spr_after.get("scale"))
        if scale_xy is None or not close(scale_xy, (-1.5, 0.5)):
            errors.append(f"negative scale readback: {spr_after}")
        if not close(float(spr_after.get("rotation") or 0.0), rot):
            errors.append(f"rotation readback: {spr_after}")
        if spr_after.get("flip_v") is not True or spr_after.get("region_enabled") is not True:
            errors.append(f"region/flip readback: {spr_after}")

        req_id, framed = tool_call(
            proc,
            req_id,
            "godot.editor",
            "frame_view",
            {"scene": scene, "node_path": "ParentB/Child/Sprite"},
        )
        if not ack_ok(framed, errors, "editor.frame_view"):
            errors.append(f"frame_view must ACK using engine bounds: {framed}")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after scale layout_batch"):
            errors.append(f"one-undo after layout_batch must ACK: {undone}")
        req_id, scale_back = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "ParentB/Child/Sprite", "property": "scale"},
        )
        if ack_ok(scale_back, errors, "property.get scale after undo") and not close(
            xy_of((scale_back.get("after") or {}).get("value")), (1.0, 1.0)
        ):
            errors.append(f"one UndoRedo layout_batch undo did not restore scale: {scale_back}")

        req_id, cam_cur = tool_call(
            proc,
            req_id,
            "godot.camera",
            "make_current",
            {"scene": scene, "node_path": "Cam"},
        )
        if not ack_ok(cam_cur, errors, "camera.make_current"):
            return errors
        if (cam_cur.get("after") or {}).get("is_current") is not True:
            errors.append(f"camera.make_current readback: {cam_cur}")
        if "callv" in json.dumps(cam_cur):
            errors.append("camera.make_current result must not mention callv")

        req_id, bounds_cam = tool_call(
            proc, req_id, "godot.canvas", "bounds", {"scene": scene, "node_path": "Cam"}
        )
        if not ack_ok(bounds_cam, errors, "canvas.bounds Camera2D"):
            return errors
        cam_after = bounds_cam.get("after") or {}
        if cam_after.get("is_current") is not True:
            errors.append(f"Camera2D bounds is_current: {cam_after}")
        if int(cam_after.get("limit_left") or 0) != -64 or int(cam_after.get("limit_right") or 0) != 640:
            errors.append(f"camera limits readback: {cam_after}")
        if cam_after.get("invented_box") is True:
            errors.append(f"Camera2D bounds invented a box: {cam_after}")

        req_id, cam_b = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Camera2D", "name": "CamB"},
        )
        if not ack_ok(cam_b, errors, "node.add CamB"):
            return errors
        req_id, cam_b_cur = tool_call(
            proc,
            req_id,
            "godot.camera",
            "make_current",
            {"scene": scene, "node_path": "CamB"},
        )
        if not ack_ok(cam_b_cur, errors, "camera.make_current CamB"):
            return errors
        if (cam_b_cur.get("after") or {}).get("is_current") is not True:
            errors.append(f"CamB make_current readback: {cam_b_cur}")
        req_id, cam_undo = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(cam_undo, errors, "node.undo after camera.make_current"):
            errors.append(f"camera undo must ACK: {cam_undo}")
        req_id, cam_back = tool_call(
            proc, req_id, "godot.canvas", "bounds", {"scene": scene, "node_path": "Cam"}
        )
        if ack_ok(cam_back, errors, "canvas.bounds Cam after camera undo"):
            if (cam_back.get("after") or {}).get("is_current") is not True:
                errors.append(f"camera undo did not restore Cam current: {cam_back}")
        req_id, camb_back = tool_call(
            proc, req_id, "godot.canvas", "bounds", {"scene": scene, "node_path": "CamB"}
        )
        if ack_ok(camb_back, errors, "canvas.bounds CamB after camera undo"):
            if (camb_back.get("after") or {}).get("is_current") is True:
                errors.append(f"CamB still current after undo: {camb_back}")

        req_id, bounds_hud = tool_call(
            proc, req_id, "godot.canvas", "bounds", {"scene": scene, "node_path": "Hud"}
        )
        if not ack_ok(bounds_hud, errors, "canvas.bounds TextureRect"):
            return errors
        hud_after = bounds_hud.get("after") or {}
        if hud_after.get("rect_source") != "get_global_rect":
            errors.append(f"TextureRect bounds must use get_global_rect: {hud_after}")
        if hud_after.get("flip_h") is not True:
            errors.append(f"TextureRect flip_h readback: {hud_after}")
        tex_enc = hud_after.get("texture") if isinstance(hud_after.get("texture"), dict) else {}
        tex_val = tex_enc.get("value") if isinstance(tex_enc.get("value"), dict) else {}
        if "sprite_tex.tres" not in str(tex_val.get("path") or tex_enc):
            errors.append(f"TextureRect texture assign readback: {hud_after}")

        req_id, ysort = tool_call(
            proc,
            req_id,
            "godot.property",
            "get",
            {"scene": scene, "node_path": "SortRoot", "property": "y_sort_enabled"},
        )
        if not ack_ok(ysort, errors, "property.get y_sort_enabled"):
            return errors
        y_val = (ysort.get("after") or {}).get("value")
        if not isinstance(y_val, dict) or y_val.get("value") is not True:
            errors.append(f"y_sort_enabled readback: {ysort}")

        req_id, size_rej = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "Hud",
                "property": "size",
                "value": variant("Vector2", {"x": 128, "y": 64}),
            },
        )
        expect_code(size_rej, ("E_INVALID_VARIANT",), errors, "Editor-only Control.size")

        if _screenshots != "SKIP":
            errors.append("camera screenshot Alternative must stay screenshots=SKIP")
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live transform 2d failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: transform 2d", file=sys.stderr)
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
        print("FAIL: transform 2d", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: canvas/camera 2D adapters; keep_global readback, negative scale, "
        f"typed make_current, TextureRect flip, y_sort; screenshots={SCREENSHOTS} Alternative; "
        "plan progress consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
