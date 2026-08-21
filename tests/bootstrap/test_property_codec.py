#!/usr/bin/env python3
"""R3-WP3: Variant codec + Inspector property set/batch/reset.

Does not tick the 20-8 plan. Does not start R3-WP4.
Pin missing is a hard FAIL. No skip-PASS.
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r3w3"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP3 [ ] while unticked; after coordinator tick allow R3-WP4+."""
    errors: list[str] = []
    current = ""
    wp3 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP3\b", stripped):
            wp3 = stripped
    if wp3 is None:
        return ["plan missing R3-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R3-WP3 heading must keep [ ] until coordinator tick")
        if current != "R3-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP3 while WP3 is unticked)")
    elif not re.match(r"^R3-WP([4-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP4+ after R3-WP3 tick)")
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


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if re.search(r"writeFile(?:Sync)?\([^)]*\.tscn", text):
            errors.append(f"{posix} writes a .tscn from the sidecar")
        if "ResourceSaver" in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{posix} has a generic invoke path")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.tscn", self_text):
        errors.append("official test writes a .tscn path directly")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_property_adapter" not in router:
        errors.append("router must dispatch through hh_property_adapter")
    adapter = ADDON / "core" / "hh_property_adapter.gd"
    codec = ADDON / "core" / "hh_variant_codec.gd"
    if not adapter.is_file():
        errors.append("missing property adapter")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "create_action" not in text or "add_do_property" not in text or "add_undo_property" not in text:
            errors.append("property adapter must use UndoRedo do/undo property")
        if "UNDO_ACTION_PREFIX" not in text:
            errors.append("property adapter must name Agent UndoRedo actions")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("property adapter has a generic invoke path")
        if re.search(r"if not res\.resource_path\.is_empty\(\)", text):
            errors.append(
                "named same-scene SubResource after save is built-in; "
                "do not treat every resource_path as external"
            )
        if "_is_current_scene_builtin" not in text or 'contains("::")' not in text:
            errors.append("property adapter must allow same-scene :: SubResource after save")
    if not codec.is_file():
        errors.append("missing variant codec")
    else:
        text = codec.read_text(encoding="utf-8")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("variant codec has a generic invoke path")
    for path in ADDON.rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{rel(path)} has a generic invoke path")
            break
    return errors


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
        return abs(float(a) - float(b)) <= 1e-5 * scale
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(left, right) for left, right in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_close(a[key], b[key]) for key in a)
    return a == b


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 30.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def prop_call(
    proc: subprocess.Popen[str],
    req_id: int,
    action: str,
    params: dict,
    precondition: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    args: dict = {"action": action, "params": params, "command_id": cid}
    if precondition:
        args["precondition"] = precondition
    resp = mcp_call(proc, req_id, "godot.property", args, timeout)
    return req_id + 1, body_of(resp)


def node_call(proc: subprocess.Popen[str], req_id: int, action: str, params: dict) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, "godot.node", {"action": action, "params": params, "command_id": cid})
    return req_id + 1, body_of(resp)


def scene_call(proc: subprocess.Popen[str], req_id: int, action: str, params: dict) -> tuple[int, dict]:
    req_id, _cid, body = life.scene_call(proc, req_id, action, params)
    return req_id, body


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    if verb in ("set", "batch", "reset"):
        undo = str(body.get("undo_action") or "")
        if not undo.startswith("Agent:"):
            errors.append(f"{verb} missing Agent undo_action: {body}")
            return False
        after = body.get("after") or {}
        if after.get("readback_equals") is not True:
            errors.append(f"{verb} missing readback_equals: {after}")
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
    scene = "res://r3w3/main.tscn"
    scene_abs = life.res_to_abs(scene)
    req_id = 2
    try:
        (TEMP_DIR / "external.tres").write_text(
            "[gd_resource type=\"PlaceholderTexture2D\" format=3]\n\n"
            "[resource]\nsize = Vector2(8, 8)\n",
            encoding="utf-8",
        )
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        jail = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.property",
                {
                    "action": "set",
                    "params": {
                        "scene": "res://../escape.tscn",
                        "node_path": ".",
                        "property": "visible",
                        "value": variant("bool", True),
                    },
                },
            )
        )
        req_id += 1
        if (jail.get("error") or {}).get("code") != "E_PATH":
            errors.append(f"escaped scene path must be E_PATH: {jail}")

        req_id, created = scene_call(proc, req_id, "create", {"path": scene, "root_class": "Node2D"})
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {created}")
            return errors
        for name, cls in (
            ("Actor", "Node2D"),
            ("Sprite", "Sprite2D"),
            ("Line", "Line2D"),
            ("Caption", "Label"),
            ("Edit", "CodeEdit"),
            ("List", "ItemList"),
            ("Space", "Node3D"),
            ("Ray", "RayCast3D"),
            ("Remote", "RemoteTransform2D"),
            ("Poly", "Polygon2D"),
        ):
            req_id, added = node_call(
                proc,
                req_id,
                "add",
                {"scene": scene, "parent": ".", "class_name": cls, "name": name},
            )
            if added.get("ok") is not True:
                errors.append(f"node.add {name} must ACK: {added}")
                return errors

        req_id, read0 = scene_call(proc, req_id, "read", {"path": scene, "detail": "short"})
        hist0 = str((read0.get("after") or {}).get("history_version") or "")
        req_id, pos0 = prop_call(proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"})
        old_pos = (pos0.get("after") or {}).get("value")
        if pos0.get("ok") is not True or not isinstance(old_pos, dict):
            errors.append(f"property.get position must ACK: {pos0}")
            return errors

        req_id, batch_fail = prop_call(
            proc,
            req_id,
            "batch",
            {
                "scene": scene,
                "items": [
                    {
                        "node_path": "Actor",
                        "property": "position",
                        "value": variant("Vector2", {"x": 64, "y": 96}),
                    },
                    {
                        "node_path": "Actor",
                        "property": "process_mode",
                        "value": variant("int", 99),
                    },
                ],
            },
        )
        expect_code(batch_fail, ("E_INVALID_VARIANT", "E_OUT_OF_BOUNDS"), errors, "batch second-item invalid")
        req_id, pos_after_fail = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        if not close((pos_after_fail.get("after") or {}).get("value"), old_pos):
            errors.append(f"batch rollback left position applied: {pos_after_fail} vs {old_pos}")
        req_id, read1 = scene_call(proc, req_id, "read", {"path": scene, "detail": "short"})
        hist1 = str((read1.get("after") or {}).get("history_version") or "")
        if hist0 and hist1 and hist0 != hist1:
            errors.append(f"failed batch changed Undo history {hist0} -> {hist1}")

        req_id, pos_before_undo = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        before_undo_pos = (pos_before_undo.get("after") or {}).get("value")
        set_undo_pos = variant("Vector2", {"x": 99, "y": 88})
        req_id, set_for_undo = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "position", "value": set_undo_pos},
        )
        if not ack_ok(set_for_undo, errors, "set"):
            errors.append(f"property.set Actor.position for undo must ACK: {set_for_undo}")
        req_id, pos_set_undo = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        if not close((pos_set_undo.get("after") or {}).get("value"), set_undo_pos):
            errors.append(f"pre-undo position was not set: {pos_set_undo}")
        req_id, undone_pos = node_call(proc, req_id, "undo", {"scene": scene, "count": 1})
        if undone_pos.get("ok") is not True:
            errors.append(f"godot.node undo after property.set must ACK: {undone_pos}")
        req_id, pos_after_undo = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        if not close((pos_after_undo.get("after") or {}).get("value"), before_undo_pos):
            errors.append(
                f"undo after property.set did not restore position: {pos_after_undo} vs {before_undo_pos}"
            )

        req_id, vis0 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "visible"}
        )
        req_id, pos_b0 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        batch_vis = variant("bool", False)
        batch_pos = variant("Vector2", {"x": 64, "y": 96})
        old_vis = (vis0.get("after") or {}).get("value")
        old_batch_pos = (pos_b0.get("after") or {}).get("value")
        req_id, batch_ok = prop_call(
            proc,
            req_id,
            "batch",
            {
                "scene": scene,
                "items": [
                    {"node_path": "Actor", "property": "position", "value": batch_pos},
                    {"node_path": "Actor", "property": "visible", "value": batch_vis},
                ],
            },
        )
        if not ack_ok(batch_ok, errors, "batch"):
            errors.append(f"successful property.batch must ACK: {batch_ok}")
        req_id, pos_b1 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        req_id, vis1 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "visible"}
        )
        if not close((pos_b1.get("after") or {}).get("value"), batch_pos):
            errors.append(f"batch did not set position: {pos_b1}")
        if not close((vis1.get("after") or {}).get("value"), batch_vis):
            errors.append(f"batch did not set visible: {vis1}")
        req_id, undone_batch = node_call(proc, req_id, "undo", {"scene": scene, "count": 1})
        if undone_batch.get("ok") is not True:
            errors.append(f"godot.node undo after property.batch must ACK: {undone_batch}")
        req_id, pos_b2 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        req_id, vis2 = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "visible"}
        )
        if not close((pos_b2.get("after") or {}).get("value"), old_batch_pos):
            errors.append(f"batch undo did not restore position: {pos_b2} vs {old_batch_pos}")
        if not close((vis2.get("after") or {}).get("value"), old_vis):
            errors.append(f"batch undo did not restore visible: {vis2} vs {old_vis}")

        theme_color = variant("Color", {"r": 0.1, "g": 0.2, "b": 0.9, "a": 1})
        poly_verts = variant(
            "TypedArray",
            {
                "element": "Vector2",
                "items": [{"x": 0, "y": 0}, {"x": 16, "y": 0}, {"x": 8, "y": 16}],
            },
        )
        poly_array = variant(
            "Array",
            [variant("TypedArray", {"element": "int", "items": [0, 1, 2]})],
        )
        corpus = [
            ("Actor", "visible", variant("bool", False)),
            ("Actor", "z_index", variant("int", 3)),
            ("Actor", "rotation", variant("float", 0.5)),
            ("Caption", "text", variant("string", "hello-agent")),
            ("Actor", "position", variant("Vector2", {"x": 8, "y": 12})),
            ("List", "fixed_icon_size", variant("Vector2i", {"x": 16, "y": 24})),
            ("Ray", "target_position", variant("Vector3", {"x": 1, "y": 2, "z": 3})),
            ("Sprite", "region_rect", variant("Rect2", {"x": 2, "y": 4, "w": 8, "h": 10})),
            (
                "Actor",
                "transform",
                variant(
                    "Transform2D",
                    {
                        "x": {"x": 1, "y": 0},
                        "y": {"x": 0, "y": 1},
                        "origin": {"x": 8, "y": 12},
                    },
                ),
            ),
            (
                "Space",
                "transform",
                variant(
                    "Transform3D",
                    {
                        "basis": {
                            "x": {"x": 1, "y": 0, "z": 0},
                            "y": {"x": 0, "y": 1, "z": 0},
                            "z": {"x": 0, "y": 0, "z": 1},
                        },
                        "origin": {"x": 4, "y": 5, "z": 6},
                    },
                ),
            ),
            ("Actor", "modulate", variant("Color", {"r": 0.25, "g": 0.5, "b": 0.75, "a": 1})),
            ("Caption", "theme_override_colors/font_color", theme_color),
            ("Remote", "remote_path", variant("NodePath", "Sprite")),
            ("Sprite", "texture", variant("Resource", {"class_name": "PlaceholderTexture2D"})),
            (
                "Line",
                "points",
                variant(
                    "TypedArray",
                    {
                        "element": "Vector2",
                        "items": [{"x": 0, "y": 0}, {"x": 16, "y": 32}, {"x": 32, "y": 0}],
                    },
                ),
            ),
            ("Poly", "polygon", poly_verts),
            ("Poly", "polygons", poly_array),
            (
                "Edit",
                "auto_brace_completion_pairs",
                variant(
                    "Dictionary",
                    {
                        "(": variant("string", ")"),
                        "<": variant("string", ">"),
                    },
                ),
            ),
        ]
        for node_path, prop, value in corpus:
            req_id, body = prop_call(
                proc,
                req_id,
                "set",
                {"scene": scene, "node_path": node_path, "property": prop, "value": value},
            )
            if not ack_ok(body, errors, "set"):
                errors.append(f"corpus {node_path}.{prop} failed: {body}")
                continue
            if not close((body.get("after") or {}).get("value"), value):
                errors.append(f"corpus {node_path}.{prop} readback mismatch: {body.get('after')} vs {value}")
            req_id, got = prop_call(
                proc, req_id, "get", {"scene": scene, "node_path": node_path, "property": prop}
            )
            if got.get("ok") is not True:
                errors.append(f"corpus get {node_path}.{prop} failed: {got}")
            elif not close((got.get("after") or {}).get("value"), value):
                errors.append(f"Inspector get {node_path}.{prop} != set: {got.get('after')} vs {value}")
            elif prop == "polygons":
                got_items = ((got.get("after") or {}).get("value") or {}).get("value")
                if not isinstance(got_items, list) or got_items == []:
                    errors.append(f"Array corpus {node_path}.{prop} readback must not be []: {got}")

        req_id, enum_bad = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "process_mode", "value": variant("int", 99)},
        )
        expect_code(enum_bad, ("E_INVALID_VARIANT", "E_OUT_OF_BOUNDS"), errors, "invalid enum process_mode")
        req_id, range_bad = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Sprite", "property": "hframes", "value": variant("int", 0)},
        )
        expect_code(range_bad, ("E_OUT_OF_BOUNDS",), errors, "out-of-range hframes")
        req_id, type_bad = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "position", "value": variant("bool", True)},
        )
        expect_code(type_bad, ("E_INVALID_TYPE",), errors, "wrong type on position")
        req_id, rid_set = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Actor",
                "property": "position",
                "value": variant("RID", "1"),
            },
        )
        expect_code(rid_set, ("E_UNVERIFIED",), errors, "RID set")
        req_id, n3d_pos = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Space",
                "property": "position",
                "value": variant("Vector3", {"x": 1, "y": 2, "z": 3}),
            },
        )
        expect_code(n3d_pos, ("E_INVALID_VARIANT",), errors, "Node3D.position editor-only")
        req_id, unknown = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Actor",
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Callable", "value": "nope"},
            },
        )
        expect_code(unknown, ("E_UNKNOWN_VARIANT_TYPE",), errors, "unsupported Callable")
        req_id, plane = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Actor",
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Plane", "value": {"x": 0, "y": 1, "z": 0, "d": 0}},
            },
        )
        expect_code(plane, ("E_UNKNOWN_VARIANT_TYPE",), errors, "unsupported Plane")
        req_id, null_color = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "modulate", "value": variant("Color", None)},
        )
        expect_code(null_color, ("E_INVALID_VARIANT", "E_INVALID_TYPE"), errors, "null Color")
        req_id, null_tex = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Sprite", "property": "texture", "value": variant("Resource", None)},
        )
        if not ack_ok(null_tex, errors, "set"):
            errors.append(f"null Resource texture must ACK: {null_tex}")
        req_id, restore_tex = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture",
                "value": variant("Resource", {"class_name": "PlaceholderTexture2D"}),
            },
        )
        if not ack_ok(restore_tex, errors, "set"):
            errors.append(f"restore PlaceholderTexture2D must ACK: {restore_tex}")
        req_id, sub = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture/size",
                "value": variant("Vector2", {"x": 32, "y": 48}),
            },
        )
        if not ack_ok(sub, errors, "set"):
            errors.append(f"subresource texture/size must ACK: {sub}")
        req_id, null_path = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Remote", "property": "remote_path", "value": variant("NodePath", None)},
        )
        if not ack_ok(null_path, errors, "set"):
            errors.append(f"null NodePath must ACK: {null_path}")
        req_id, restore_path = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Remote", "property": "remote_path", "value": variant("NodePath", "Sprite")},
        )
        if not ack_ok(restore_path, errors, "set"):
            errors.append(f"restore NodePath must ACK: {restore_path}")

        req_id, cur = prop_call(proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "z_index"})
        good_hash = str((cur.get("after") or {}).get("property_hash") or "")
        if len(good_hash) < 8:
            errors.append(f"property.get must return property_hash: {cur}")
        req_id, conflict = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Actor",
                "property": "z_index",
                "value": variant("int", 7),
                "expected_old_hash": "deadbeefdeadbeef",
            },
        )
        expect_code(conflict, ("E_CONFLICT",), errors, "expected-old-hash mismatch")
        if good_hash:
            req_id, hashed = prop_call(
                proc,
                req_id,
                "set",
                {
                    "scene": scene,
                    "node_path": "Actor",
                    "property": "z_index",
                    "value": variant("int", 7),
                    "expected_old_hash": good_hash,
                },
            )
            if not ack_ok(hashed, errors, "set"):
                errors.append(f"matching expected-old-hash must ACK: {hashed}")

        hdr = variant("Color", {"r": 2, "g": 0.5, "b": 0.25, "a": 1})
        req_id, hdr_set = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "modulate", "value": hdr},
        )
        if not ack_ok(hdr_set, errors, "set"):
            errors.append(f"HDR Color r=2 must ACK: {hdr_set}")
        req_id, hdr_get = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "modulate"}
        )
        hdr_got = (hdr_get.get("after") or {}).get("value")
        if not close(hdr_got, hdr):
            errors.append(f"HDR Color get != set: {hdr_get} vs {hdr}")
        req_id, hdr_again = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "modulate", "value": hdr_got},
        )
        if not ack_ok(hdr_again, errors, "set"):
            errors.append(f"HDR set-the-get must ACK: {hdr_again}")
        req_id, hdr_final = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "modulate"}
        )
        if not close((hdr_final.get("after") or {}).get("value"), hdr):
            errors.append(f"HDR set-the-get lost r=2: {hdr_final}")

        away = variant("Vector2", {"x": 40, "y": 50})
        default_pos = variant("Vector2", {"x": 0, "y": 0})
        req_id, away_set = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "position", "value": away},
        )
        if not ack_ok(away_set, errors, "set"):
            errors.append(f"position away from default must ACK: {away_set}")
        req_id, reset = prop_call(
            proc, req_id, "reset", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        if not ack_ok(reset, errors, "reset"):
            errors.append(f"property.reset must ACK after proven set: {reset}")
        req_id, reset_got = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Actor", "property": "position"}
        )
        if not close((reset_got.get("after") or {}).get("value"), default_pos):
            errors.append(f"property.reset readback != class default (0,0): {reset_got}")

        persist = [
            (node_path, prop, value)
            for node_path, prop, value in corpus
            if not (node_path == "Actor" and prop == "rotation")
        ] + [
            ("Sprite", "texture/size", variant("Vector2", {"x": 32, "y": 48})),
            ("Remote", "remote_path", variant("NodePath", "Sprite")),
        ]
        for node_path, prop, value in persist:
            req_id, body = prop_call(
                proc,
                req_id,
                "set",
                {"scene": scene, "node_path": node_path, "property": prop, "value": value},
            )
            if not ack_ok(body, errors, "set"):
                errors.append(f"persist {node_path}.{prop} failed: {body}")

        req_id, saved = scene_call(proc, req_id, "save", {"path": scene})
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {saved}")
            return errors
        if scene_abs.is_file() and "hello-agent" not in scene_abs.read_text(encoding="utf-8"):
            errors.append("save did not persist Caption text")

        life.stop_proc(godot)
        godot, godot_lines = life.start_godot(exe)
        req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"reopen hello failed: {last2}")
            return errors
        req_id, opened = scene_call(proc, req_id, "open", {"path": scene})
        if opened.get("ok") is not True:
            errors.append(f"scene.open after restart must ACK: {opened}")
            return errors
        reopen = [
            (node_path, prop, value)
            for node_path, prop, value in persist
            if prop != "texture"
        ]
        for node_path, prop, value in reopen:
            req_id, got = prop_call(proc, req_id, "get", {"scene": scene, "node_path": node_path, "property": prop})
            if got.get("ok") is not True:
                errors.append(f"reopen get {node_path}.{prop} failed: {got}")
            elif not close((got.get("after") or {}).get("value"), value):
                errors.append(f"disk reopen {node_path}.{prop} != set: {got.get('after')} vs {value}")

        reopen_size = variant("Vector2", {"x": 40, "y": 56})
        req_id, set_after_save = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture/size",
                "value": reopen_size,
            },
        )
        if not ack_ok(set_after_save, errors, "set"):
            errors.append(f"post-save builtin texture/size set must ACK: {set_after_save}")
        req_id, got_after_save = prop_call(
            proc, req_id, "get", {"scene": scene, "node_path": "Sprite", "property": "texture/size"}
        )
        if not close((got_after_save.get("after") or {}).get("value"), reopen_size):
            errors.append(f"post-save builtin texture/size get != set: {got_after_save}")

        req_id, assign_ext = prop_call(
            proc,
            req_id,
            "set",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture",
                "value": variant("Resource", {"path": "res://r3w3/external.tres"}),
            },
        )
        ext_ready = assign_ext.get("ok") is True
        if not ext_ready:
            req_id, tex_now = prop_call(
                proc, req_id, "get", {"scene": scene, "node_path": "Sprite", "property": "texture"}
            )
            tex_inner = ((tex_now.get("after") or {}).get("value") or {}).get("value")
            if isinstance(tex_inner, dict) and "external.tres" in str(tex_inner.get("path") or ""):
                ext_ready = True
        if ext_ready:
            req_id, ext_field = prop_call(
                proc,
                req_id,
                "set",
                {
                    "scene": scene,
                    "node_path": "Sprite",
                    "property": "texture/size",
                    "value": variant("Vector2", {"x": 9, "y": 10}),
                },
            )
            expect_code(ext_field, ("E_UNVERIFIED",), errors, "external Resource field mutate")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, blocked = prop_call(
            proc,
            req_id,
            "set",
            {"scene": scene, "node_path": "Actor", "property": "visible", "value": variant("bool", True)},
        )
        if (blocked.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"paused property.set must be E_PAUSED: {blocked}")
        body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live property codec failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: property codec", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
    elif version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    gen = subprocess.run(
        [sess.npm(), "run", "generate"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if gen.returncode != 0:
        errors.append(f"npm run generate failed:\n{gen.stdout}\n{gen.stderr}")
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
        print("FAIL: property codec", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: property Variant codec + Inspector set/batch/reset; "
        "corpus, invalid enum/range/type, batch rollback, save/reopen, "
        "post-save builtin SubResource set, Pause; "
        "R3-WP3 stays [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
