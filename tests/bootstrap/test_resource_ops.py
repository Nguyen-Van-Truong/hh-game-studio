#!/usr/bin/env python3
"""R3-WP4: resource/signal/group/dependency operations.

Does not tick the 20-8 plan. Does not start R3-WP5.
Pin missing is a hard FAIL. No skip-PASS.
"""

from __future__ import annotations

import hashlib
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
TEMP_DIR = PLUGIN_PROJECT / "r3w4"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R3-WP4 [ ] while unticked; after coordinator tick allow R3-WP5+."""
    errors: list[str] = []
    current = ""
    wp4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R3-WP4\b", stripped):
            wp4 = stripped
    if wp4 is None:
        return ["plan missing R3-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R3-WP4 heading must keep [ ] until coordinator tick")
        if current != "R3-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP4 while WP4 is unticked)")
    elif not re.match(r"^R3-WP([5-9]|\d{2,})$|^R[4-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R3-WP5+ after R3-WP4 tick)")
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
        if re.search(r"writeFile(?:Sync)?\([^)]*\.(?:tscn|tres|res)", text):
            errors.append(f"{posix} writes a scene/resource from the sidecar")
        if "ResourceSaver" in text:
            errors.append(f"{posix} uses ResourceSaver")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{posix} has a generic invoke path")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res)", self_text):
        errors.append("official test writes a .tscn/.tres/.res path directly")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_resource_adapter" not in router or "hh_signal_adapter" not in router:
        errors.append("router must dispatch resource/signal adapters")
    if "project.settings must stay" not in router or "resource.create must stay" in router:
        errors.append("unproven-mutate sentinel must stay on project.settings")
    resource = ADDON / "core" / "hh_resource_adapter.gd"
    signal = ADDON / "core" / "hh_signal_adapter.gd"
    reads = ADDON / "core" / "hh_read_adapters.gd"
    life_ts = BRIDGE / "src" / "ledger" / "scene_lifecycle.ts"
    if not resource.is_file():
        errors.append("missing resource adapter")
    else:
        text = resource.read_text(encoding="utf-8")
        if "ResourceSaver.save" not in text:
            errors.append("resource adapter must call ResourceSaver.save")
        if "get_file_as_bytes" not in text or "HASH_SHA256" not in text:
            errors.append("resource adapter must SHA-256 read file bytes after save")
        if "add_do_property" not in text or "UNDO_ACTION_PREFIX" not in text:
            errors.append("resource assign/edit must use Agent UndoRedo properties")
        if "shared" not in text or "E_CONFLICT" not in text:
            errors.append("resource adapter must refuse accidental shared mutation")
        if "rewrite_plan" not in text:
            errors.append("move/delete must require a rewrite plan when referenced")
        if "FileAccess.WRITE" in text:
            errors.append("resource adapter must not in-place FileAccess.WRITE rewrite")
        if "_cleanup_new_external" not in text:
            errors.append("failed create/unique must delete the new dest file")
        if "get_open_scenes" not in text:
            errors.append("shared owner count must include EditorInterface.get_open_scenes")
        if "ur.undo()" not in text:
            errors.append("unique+assign fail must history-undo the assign before dest cleanup")
        edit_entry = re.search(r"func _edit\b.*?func _unique_then_edit\b", text, re.S)
        if edit_entry is None:
            errors.append("missing _edit")
        elif "_walk_property" not in edit_entry.group(0):
            errors.append("_edit must walk nested externals before the shared/unique gate")
        uniq_fn = re.search(r"func _unique_then_edit\b.*?func _gated_edit_resource\b", text, re.S)
        if uniq_fn is None:
            uniq_fn = re.search(r"func _unique_then_edit\b.*?func _edit_resource\b", text, re.S)
        if uniq_fn is None:
            errors.append("missing _unique_then_edit")
        else:
            uniq_body = uniq_fn.group(0)
            if 'after["disk_hash"]' in uniq_body or "after['disk_hash']" in uniq_body:
                errors.append("unique edit must not stamp dest disk_hash from the pre-edit clone")
            if "_rollback_unique_assign" not in uniq_body and "ur.undo()" not in uniq_body:
                errors.append("unique+assign fail must undo assign then cleanup dest")
        edit_fn = re.search(r"func _edit_resource\b.*?func _save\b", text, re.S)
        if edit_fn is None:
            errors.append("missing _edit_resource")
        else:
            body = edit_fn.group(0)
            if "_persist_external" in body or "ResourceSaver.save" in body:
                errors.append("_edit_resource must not persist; disk write is resource.save")
        disk_fn = re.search(r"func _count_disk_scene_owners\b.*?func _cleanup_new_external\b", text, re.S)
        if disk_fn is None:
            errors.append("missing _count_disk_scene_owners")
        elif ".tres" not in disk_fn.group(0) or ".res" not in disk_fn.group(0):
            errors.append("disk owner scan must include .tres/.res referencers, not only .tscn")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("resource adapter has a generic invoke path")
    if reads.is_file():
        uid_fn = re.search(
            r"func _resource_uid\b.*?func _signal_list\b",
            reads.read_text(encoding="utf-8"),
            re.S,
        )
        if uid_fn is None:
            errors.append("missing _resource_uid")
        else:
            uid_body = uid_fn.group(0)
            if "_jail(" not in uid_body:
                errors.append("resource.uid must jail the mapped path")
            if "file_exists" not in uid_body:
                errors.append("resource.uid must FileAccess-check the mapped path")
    if life_ts.is_file():
        life_text = life_ts.read_text(encoding="utf-8")
        needs_fn = re.search(
            r"export function mutationNeedsDiskHash\b.*?^export function ",
            life_text,
            re.S | re.M,
        )
        if needs_fn is None:
            errors.append("missing mutationNeedsDiskHash")
        elif "params.unique === true" in needs_fn.group(0):
            errors.append(
                "mutationNeedsDiskHash must not durable-ACK unique dest "
                "(file copy + RAM edit; resource.save persists the field)"
            )
        if not re.search(r'actionId === "resource.edit"', life_text):
            errors.append("durableResPath must handle resource.edit dest after.path")
    if '"unique": True' not in self_text:
        errors.append("official test must send resource.edit unique=true + dest")
    if '"path": tex_unique' not in self_text:
        errors.append("official test must resource.save the unique dest after ACK")
    if "assign_property" not in self_text:
        errors.append("official test must unique=true + assign_property then fail and rollback")
    if "next_pass/" not in self_text:
        errors.append("official test must edit a nested external (next_pass/...) without flags")
    if not signal.is_file():
        errors.append("missing signal adapter")
    else:
        text = signal.read_text(encoding="utf-8")
        if "add_do_method" not in text or "add_undo_method" not in text:
            errors.append("signal adapter must use EditorUndoRedoManager add_do/undo_method")
        if ".connect(" in text:
            errors.append("signal adapter must not call Object.connect outside UndoRedo")
        if "CONNECT_PERSIST" not in text:
            errors.append("signal connect must persist with CONNECT_PERSIST")
        if "UNDO_ACTION_PREFIX" not in text:
            errors.append("signal adapter must name Agent UndoRedo actions")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append("signal adapter has a generic invoke path")
    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "Object.keys(requested)" not in execute and "encode-superset" not in execute:
        if "for (const key of Object.keys(requested))" not in execute:
            errors.append("ledger encodedClose must allow encode-superset of the request")
    for path in ADDON.rglob("*.gd"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bcallv\b", text) or "Object.call" in text:
            errors.append(f"{rel(path)} has a generic invoke path")
            break
    return errors


def variant(typ: str, value) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 40.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    tool: str,
    action: str,
    params: dict,
    timeout: float = 40.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, tool, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str, undo: bool = False) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    if undo:
        name = str(body.get("undo_action") or "")
        if not name.startswith("Agent:"):
            errors.append(f"{verb} missing Agent undo_action: {body}")
            return False
    return True


def expect_code(body: dict, codes: tuple[str, ...], errors: list[str], label: str) -> None:
    got = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True or got not in codes:
        errors.append(f"{label} expected {codes}, got {body}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def variant_xy(body: dict) -> tuple[float, float] | None:
    val = ((body.get("after") or {}).get("value") or {}).get("value") or {}
    if not isinstance(val, dict):
        return None
    return float(val.get("x") or 0), float(val.get("y") or 0)


def tres_has_vec2(text: str, x: float, y: float) -> bool:
    xs = {str(x), f"{x:g}"}
    ys = {str(y), f"{y:g}"}
    if float(x) == int(x):
        xs.add(str(int(x)))
        xs.add(f"{int(x)}.0")
    if float(y) == int(y):
        ys.add(str(int(y)))
        ys.add(f"{int(y)}.0")
    for xv in xs:
        for yv in ys:
            if f"Vector2({xv}, {yv})" in text or f"Vector2({xv},{yv})" in text:
                return True
    return False


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
    scene = "res://r3w4/main.tscn"
    tiles = "res://r3w4/tiles.tres"
    tex = "res://r3w4/tex.tres"
    tex2 = "res://r3w4/tex2.tres"
    tex_unique = "res://r3w4/tex_unique.tres"
    tex_orphan = "res://r3w4/tex_orphan.tres"
    undo_tex = "res://r3w4/undo_tex.tres"
    ghost = "res://r3w4/ghost.tres"
    other = "res://r3w4/other.tscn"
    box = "res://r3w4/box.tres"
    box2 = "res://r3w4/box2.tres"
    mat_a = "res://r3w4/mat_a.tres"
    mat_b = "res://r3w4/mat_b.tres"
    nest_inner = "res://r3w4/nest_inner.tres"
    nest_outer = "res://r3w4/nest_outer.tres"
    nest_outer2 = "res://r3w4/nest_outer2.tres"
    shared_tex = "res://r3w4/shared_tex.tres"
    atlas_a = "res://r3w4/atlas_a.tres"
    atlas_b = "res://r3w4/atlas_b.tres"
    tiles_abs = life.res_to_abs(tiles)
    tex_abs = life.res_to_abs(tex)
    tex2_abs = life.res_to_abs(tex2)
    tex_unique_abs = life.res_to_abs(tex_unique)
    tex_orphan_abs = life.res_to_abs(tex_orphan)
    undo_abs = life.res_to_abs(undo_tex)
    ghost_abs = life.res_to_abs(ghost)
    box2_abs = life.res_to_abs(box2)
    req_id = 2
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

        jail = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.resource",
                {
                    "action": "create",
                    "params": {"path": "res://../escape.tres", "class_name": "TileSet"},
                    "command_id": life.new_ulid(),
                },
            )
        )
        req_id += 1
        expect_code(jail, ("E_PATH",), errors, "escaped resource path")

        req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
        if not ack_ok(created, errors, "scene.create"):
            return errors
        for name, cls in (
            ("Sprite", "Sprite2D"),
            ("SpriteB", "Sprite2D"),
            ("Mark", "Sprite2D"),
            ("UndoSpr", "Sprite2D"),
            ("PeekSpr", "Sprite2D"),
            ("Clock", "Timer"),
        ):
            req_id, added = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": scene, "parent": ".", "class_name": cls, "name": name},
            )
            if not ack_ok(added, errors, f"node.add {name}", undo=True):
                return errors

        req_id, tiles_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": tiles, "class_name": "TileSet"}
        )
        if not ack_ok(tiles_body, errors, "resource.create TileSet"):
            return errors
        tiles_after = tiles_body.get("after") or {}
        tiles_uid = str(tiles_after.get("uid") or "")
        if not tiles_abs.is_file():
            errors.append("resource.create TileSet did not write the .tres")
            return errors
        if not tiles_uid.startswith("uid://"):
            errors.append(f"resource.create missing uid: {tiles_body}")
            return errors
        if str(tiles_after.get("disk_hash") or "") != sha256_file(tiles_abs):
            errors.append(f"create disk SHA mismatch: {tiles_after} vs {sha256_file(tiles_abs)}")

        req_id, loaded = tool_call(proc, req_id, "godot.resource", "load", {"path": tiles})
        if not ack_ok(loaded, errors, "resource.load"):
            return errors
        if str((loaded.get("after") or {}).get("uid") or "") != tiles_uid:
            errors.append(f"resource.load uid mismatch: {loaded}")
        req_id, uid_body = tool_call(proc, req_id, "godot.resource", "uid", {"uid": tiles_uid})
        if not ack_ok(uid_body, errors, "resource.uid"):
            return errors
        if str((uid_body.get("after") or {}).get("path") or "") != tiles:
            errors.append(f"resource.uid path mismatch: {uid_body}")

        req_id, fake_uid = tool_call(proc, req_id, "godot.resource", "uid", {"uid": "uid://zznotmappedxx"})
        expect_code(fake_uid, ("E_UNVERIFIED", "E_PATH"), errors, "fake/unmapped resource.uid")
        req_id, ghost_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": ghost, "class_name": "TileSet"}
        )
        ghost_uid = str((ghost_body.get("after") or {}).get("uid") or "")
        if ack_ok(ghost_body, errors, "resource.create ghost"):
            if ghost_abs.is_file():
                try:
                    ghost_abs.unlink()
                except OSError as exc:
                    errors.append(f"could not unlink ghost for mapped+missing uid test: {exc}")
            if ghost_uid.startswith("uid://"):
                req_id, missing_uid = tool_call(proc, req_id, "godot.resource", "uid", {"uid": ghost_uid})
                expect_code(missing_uid, ("E_UNVERIFIED", "E_PATH"), errors, "mapped+missing resource.uid")

        req_id, tex_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": tex, "class_name": "PlaceholderTexture2D"}
        )
        if not ack_ok(tex_body, errors, "resource.create PlaceholderTexture2D"):
            return errors
        tex_uid = str((tex_body.get("after") or {}).get("uid") or "")

        req_id, assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "Sprite", "property": "texture", "resource": tex},
        )
        if not ack_ok(assigned, errors, "resource.assign path", undo=True):
            return errors
        req_id, got_tex = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture"}
        )
        tex_val = ((got_tex.get("after") or {}).get("value") or {}).get("value") or {}
        if not isinstance(tex_val, dict) or tex not in str(tex_val.get("path") or ""):
            errors.append(f"property.get texture path mismatch: {got_tex}")
        if tex_uid and str(tex_val.get("uid") or "") not in ("", tex_uid) and tex_val.get("uid") != tex_uid:
            errors.append(f"property.get texture uid mismatch: {got_tex} vs {tex_uid}")

        req_id, assign_obj = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture",
                "resource": tex,
                "uid": tex_uid,
                "class_name": "PlaceholderTexture2D",
            },
        )
        if not ack_ok(assign_obj, errors, "resource.assign {path,uid,class_name}", undo=True):
            errors.append(f"path/uid/class_name assign must ACK: {assign_obj}")

        req_id, path_set = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "Sprite",
                "property": "texture",
                "value": variant("Resource", {"path": tex}),
            },
        )
        if not ack_ok(path_set, errors, "property.set Resource path", undo=True):
            errors.append(f"encodedClose leftover: path-assign must ACK: {path_set}")

        req_id, saved_main = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved_main, errors, "scene.save before two-scene share"):
            return errors
        req_id, other_body = tool_call(
            proc, req_id, "godot.scene", "create", {"path": other, "root_class": "Node2D"}
        )
        if not ack_ok(other_body, errors, "scene.create other"):
            return errors
        req_id, other_spr = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": other, "parent": ".", "class_name": "Sprite2D", "name": "Sprite"},
        )
        if not ack_ok(other_spr, errors, "node.add other Sprite", undo=True):
            return errors
        req_id, other_assign = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": other, "node_path": "Sprite", "property": "texture", "resource": tex},
        )
        if not ack_ok(other_assign, errors, "resource.assign other scene", undo=True):
            return errors
        req_id, saved_other = tool_call(proc, req_id, "godot.scene", "save", {"path": other})
        if not ack_ok(saved_other, errors, "scene.save other"):
            return errors
        req_id, two_scene_edit = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": tex, "property": "size", "value": variant("Vector2", {"x": 7, "y": 8})},
        )
        expect_code(two_scene_edit, ("E_CONFLICT",), errors, "two-scene shared edit without flags")
        req_id, back_main = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
        if not ack_ok(back_main, errors, "scene.open main after other"):
            return errors

        req_id, unique_orphan = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {
                "path": tex,
                "unique": True,
                "dest": tex_orphan,
                "scene": scene,
                "node_path": "Sprite",
                "assign_property": "texture",
                "property": "no_such_leaf",
                "value": variant("Vector2", {"x": 3, "y": 4}),
            },
        )
        expect_code(
            unique_orphan,
            ("E_UNVERIFIED", "E_MISSING_REQUIRED", "E_INVALID_TYPE"),
            errors,
            "unique=true assign_property then missing leaf",
        )
        req_id, still_tex = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture"}
        )
        still_val = ((still_tex.get("after") or {}).get("value") or {}).get("value") or {}
        still_path = str(still_val.get("path") or "") if isinstance(still_val, dict) else ""
        if tex not in still_path:
            errors.append(f"unique+assign fail must keep original node.texture: {still_tex}")
        if tex_orphan_abs.is_file():
            errors.append("unique+assign fail must not leave dest on disk while/after rollback")

        tex_hash_before_unique = sha256_file(tex_abs)
        req_id, size_before_unique = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture/size"}
        )
        before_xy = variant_xy(size_before_unique)
        req_id, unique_true = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {
                "path": tex,
                "unique": True,
                "dest": tex_unique,
                "property": "size",
                "value": variant("Vector2", {"x": 99, "y": 88}),
            },
        )
        if not ack_ok(unique_true, errors, "resource.edit unique=true dest", undo=True):
            return errors
        if str((unique_true.get("after") or {}).get("path") or "") != tex_unique:
            errors.append(f"unique=true after.path must be dest: {unique_true}")
        if not tex_unique_abs.is_file():
            errors.append("unique=true dest missing on disk")
        if sha256_file(tex_abs) != tex_hash_before_unique:
            errors.append("unique=true mutated the original .tres on disk")
        req_id, size_after_unique = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture/size"}
        )
        after_xy = variant_xy(size_after_unique)
        if before_xy is not None and after_xy == (99.0, 88.0):
            errors.append(f"unique=true mutated the original in-memory field: {size_after_unique}")
        if after_xy is not None and before_xy is not None and after_xy != before_xy:
            errors.append(f"unique=true changed original Sprite size {before_xy} -> {after_xy}")
        dest_before_save = tex_unique_abs.read_text(encoding="utf-8") if tex_unique_abs.is_file() else ""
        if tres_has_vec2(dest_before_save, 99, 88):
            errors.append("unique=true must not persist the dest field before resource.save")
        req_id, saved_unique = tool_call(proc, req_id, "godot.resource", "save", {"path": tex_unique})
        if not ack_ok(saved_unique, errors, "resource.save unique dest"):
            return errors
        req_id, peek_assign = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "PeekSpr", "property": "texture", "resource": tex_unique},
        )
        if ack_ok(peek_assign, errors, "assign unique dest after save", undo=True):
            req_id, peek_size = tool_call(
                proc,
                req_id,
                "godot.property",
                "get",
                {"scene": scene, "node_path": "PeekSpr", "property": "texture/size"},
            )
            if variant_xy(peek_size) != (99.0, 88.0):
                errors.append(f"resource.save dest must persist the unique edit field: {peek_size}")

        req_id, shared_tex_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": shared_tex, "class_name": "PlaceholderTexture2D"}
        )
        req_id, atlas_a_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": atlas_a, "class_name": "AtlasTexture"}
        )
        req_id, atlas_b_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": atlas_b, "class_name": "AtlasTexture"}
        )
        if (
            ack_ok(shared_tex_body, errors, "create shared_tex")
            and ack_ok(atlas_a_body, errors, "create atlas_a")
            and ack_ok(atlas_b_body, errors, "create atlas_b")
        ):
            req_id, link_atlas_a = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": atlas_a, "property": "atlas", "value": variant("Resource", {"path": shared_tex})},
            )
            req_id, link_atlas_b = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": atlas_b, "property": "atlas", "value": variant("Resource", {"path": shared_tex})},
            )
            if ack_ok(link_atlas_a, errors, "edit atlas_a.atlas", undo=True) and ack_ok(
                link_atlas_b, errors, "edit atlas_b.atlas", undo=True
            ):
                req_id, saved_atlas_a = tool_call(proc, req_id, "godot.resource", "save", {"path": atlas_a})
                req_id, saved_atlas_b = tool_call(proc, req_id, "godot.resource", "save", {"path": atlas_b})
                if ack_ok(saved_atlas_a, errors, "resource.save atlas_a") and ack_ok(
                    saved_atlas_b, errors, "resource.save atlas_b"
                ):
                    req_id, tex_shared_edit = tool_call(
                        proc,
                        req_id,
                        "godot.resource",
                        "edit",
                        {"path": shared_tex, "property": "size", "value": variant("Vector2", {"x": 5, "y": 6})},
                    )
                    expect_code(
                        tex_shared_edit,
                        ("E_CONFLICT",),
                        errors,
                        "two .tres owners of one texture without flags",
                    )
                    req_id, atlas_nested = tool_call(
                        proc,
                        req_id,
                        "godot.resource",
                        "edit",
                        {
                            "path": atlas_a,
                            "property": "atlas/size",
                            "value": variant("Vector2", {"x": 5, "y": 6}),
                        },
                    )
                    expect_code(
                        atlas_nested,
                        ("E_CONFLICT",),
                        errors,
                        "nested external atlas/ edit without flags",
                    )

        req_id, nest_inner_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": nest_inner, "class_name": "ShaderMaterial"}
        )
        req_id, nest_outer_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": nest_outer, "class_name": "ShaderMaterial"}
        )
        req_id, nest_outer2_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": nest_outer2, "class_name": "ShaderMaterial"}
        )
        if (
            ack_ok(nest_inner_body, errors, "create nest_inner")
            and ack_ok(nest_outer_body, errors, "create nest_outer")
            and ack_ok(nest_outer2_body, errors, "create nest_outer2")
        ):
            req_id, link_outer = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": nest_outer, "property": "next_pass", "value": variant("Resource", {"path": nest_inner})},
            )
            req_id, link_outer2 = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": nest_outer2, "property": "next_pass", "value": variant("Resource", {"path": nest_inner})},
            )
            if ack_ok(link_outer, errors, "edit nest_outer next_pass", undo=True) and ack_ok(
                link_outer2, errors, "edit nest_outer2 next_pass", undo=True
            ):
                req_id, inner_shared = tool_call(
                    proc,
                    req_id,
                    "godot.resource",
                    "edit",
                    {"path": nest_inner, "property": "render_priority", "value": variant("int", 4)},
                )
                expect_code(
                    inner_shared,
                    ("E_CONFLICT",),
                    errors,
                    "two .tres owners of inner without flags",
                )
                req_id, nested_shared = tool_call(
                    proc,
                    req_id,
                    "godot.resource",
                    "edit",
                    {
                        "path": nest_outer,
                        "property": "next_pass/render_priority",
                        "value": variant("int", 5),
                    },
                )
                expect_code(
                    nested_shared,
                    ("E_CONFLICT",),
                    errors,
                    "nested external next_pass/ edit without flags",
                )
                req_id, saved_outer = tool_call(proc, req_id, "godot.resource", "save", {"path": nest_outer})
                ack_ok(saved_outer, errors, "resource.save nest_outer")
                req_id, saved_outer2 = tool_call(proc, req_id, "godot.resource", "save", {"path": nest_outer2})
                ack_ok(saved_outer2, errors, "resource.save nest_outer2")

        req_id, undo_created = tool_call(
            proc, req_id, "godot.resource", "create", {"path": undo_tex, "class_name": "PlaceholderTexture2D"}
        )
        if not ack_ok(undo_created, errors, "resource.create undo_tex"):
            return errors
        req_id, undo_assigned = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "UndoSpr", "property": "texture", "resource": undo_tex},
        )
        if not ack_ok(undo_assigned, errors, "resource.assign undo_tex", undo=True):
            return errors
        req_id, undo_old = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "UndoSpr", "property": "texture/size"}
        )
        old_xy = variant_xy(undo_old)
        if old_xy is None:
            errors.append(f"undo_tex old size missing: {undo_old}")
            return errors
        undo_disk_before = sha256_file(undo_abs)
        req_id, undo_edit = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": undo_tex, "property": "size", "value": variant("Vector2", {"x": 20, "y": 21})},
        )
        if not ack_ok(undo_edit, errors, "resource.edit undo field", undo=True):
            return errors
        if sha256_file(undo_abs) != undo_disk_before:
            errors.append("resource.edit wrote the .tres; disk write must wait for resource.save")
        req_id, undo_now = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "UndoSpr", "property": "texture/size"}
        )
        if variant_xy(undo_now) != (20.0, 21.0):
            errors.append(f"edit did not set in-memory size: {undo_now}")
        req_id, undone_edit = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone_edit, errors, "node.undo after resource.edit"):
            return errors
        req_id, undo_restored = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "UndoSpr", "property": "texture/size"}
        )
        if variant_xy(undo_restored) != old_xy:
            errors.append(f"undo after edit did not restore in-memory field: {undo_restored} vs {old_xy}")
        req_id, undo_edit2 = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": undo_tex, "property": "size", "value": variant("Vector2", {"x": 22, "y": 23})},
        )
        if not ack_ok(undo_edit2, errors, "resource.edit before save", undo=True):
            return errors
        req_id, undo_saved = tool_call(proc, req_id, "godot.resource", "save", {"path": undo_tex})
        if not ack_ok(undo_saved, errors, "resource.save after edit"):
            return errors
        if str((undo_saved.get("after") or {}).get("disk_hash") or "") != sha256_file(undo_abs):
            errors.append(f"resource.save undo_tex disk SHA mismatch: {undo_saved}")

        req_id, dup = tool_call(proc, req_id, "godot.resource", "duplicate", {"path": tex, "dest": tex2})
        if not ack_ok(dup, errors, "resource.duplicate"):
            return errors
        if str((dup.get("after") or {}).get("uid") or "") == tex_uid:
            errors.append(f"duplicate uid must be distinct: {dup}")
        if not tex2_abs.is_file():
            errors.append("duplicate dest missing on disk")

        req_id, edit_dup = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": tex2, "property": "size", "value": variant("Vector2", {"x": 32, "y": 48})},
        )
        if not ack_ok(edit_dup, errors, "resource.edit duplicate", undo=True):
            return errors
        req_id, orig_size = tool_call(
            proc, req_id, "godot.resource", "load", {"path": tex}
        )
        req_id, got_orig = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture/size"}
        )
        orig_sz = ((got_orig.get("after") or {}).get("value") or {}).get("value") or {}
        if isinstance(orig_sz, dict) and float(orig_sz.get("x") or 0) == 32 and float(orig_sz.get("y") or 0) == 48:
            errors.append(f"edit of unique duplicate mutated the original: {got_orig}")

        req_id, assigned_b = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "SpriteB", "property": "texture", "resource": tex},
        )
        if not ack_ok(assigned_b, errors, "resource.assign shared SpriteB", undo=True):
            return errors
        req_id, shared_edit = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {
                "scene": scene,
                "path": tex,
                "property": "size",
                "value": variant("Vector2", {"x": 11, "y": 12}),
            },
        )
        expect_code(shared_edit, ("E_CONFLICT",), errors, "shared edit without flag")

        req_id, unique_assign = tool_call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "SpriteB", "property": "texture", "resource": tex2},
        )
        if not ack_ok(unique_assign, errors, "assign unique dest to SpriteB", undo=True):
            return errors
        req_id, edit_unique = tool_call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {"path": tex2, "property": "size", "value": variant("Vector2", {"x": 64, "y": 80})},
        )
        if not ack_ok(edit_unique, errors, "edit unique dest", undo=True):
            return errors
        req_id, size_a = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Sprite", "property": "texture/size"}
        )
        req_id, size_b = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "SpriteB", "property": "texture/size"}
        )
        sz_a = ((size_a.get("after") or {}).get("value") or {}).get("value") or {}
        sz_b = ((size_b.get("after") or {}).get("value") or {}).get("value") or {}
        if isinstance(sz_b, dict) and (float(sz_b.get("x") or 0) != 64 or float(sz_b.get("y") or 0) != 80):
            errors.append(f"unique edit did not change SpriteB only: {size_b}")
        if isinstance(sz_a, dict) and float(sz_a.get("x") or 0) == 64 and float(sz_a.get("y") or 0) == 80:
            errors.append(f"unique edit mutated the shared original owner: {size_a}")

        req_id, saved_tex = tool_call(proc, req_id, "godot.resource", "save", {"path": tex})
        if not ack_ok(saved_tex, errors, "resource.save"):
            return errors
        if str((saved_tex.get("after") or {}).get("disk_hash") or "") != sha256_file(tex_abs):
            errors.append(f"resource.save disk SHA mismatch: {saved_tex}")

        req_id, box_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": box, "class_name": "StyleBoxFlat"}
        )
        if not ack_ok(box_body, errors, "resource.create StyleBoxFlat"):
            return errors
        box_uid = str((box_body.get("after") or {}).get("uid") or "")
        req_id, moved = tool_call(proc, req_id, "godot.asset", "move", {"from": box, "to": box2})
        if not ack_ok(moved, errors, "asset.move unreferenced"):
            return errors
        if life.res_to_abs(box).is_file() or not box2_abs.is_file():
            errors.append("asset.move did not relocate the unreferenced resource")
        if str((moved.get("after") or {}).get("uid") or "") != box_uid:
            errors.append(f"move/rename UID drifted: {moved} vs {box_uid}")
        req_id, uid_moved = tool_call(proc, req_id, "godot.resource", "uid", {"uid": box_uid})
        if str((uid_moved.get("after") or {}).get("path") or "") != box2:
            errors.append(f"UID map after move is not the new path: {uid_moved}")

        req_id, move_ref = tool_call(proc, req_id, "godot.asset", "move", {"from": tex, "to": "res://r3w4/tex_moved.tres"})
        expect_code(move_ref, ("E_CONFLICT",), errors, "move still-referenced without rewrite_plan")
        req_id, rewrite = tool_call(
            proc,
            req_id,
            "godot.asset",
            "move",
            {"from": tex, "to": "res://r3w4/tex_moved.tres", "rewrite_plan": True},
        )
        expect_code(rewrite, ("E_UNVERIFIED",), errors, "rewrite_plan=true referenced move")
        if not tex_abs.is_file():
            errors.append("rewrite_plan refusal must not move the referenced file")

        req_id, mat_a_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": mat_a, "class_name": "ShaderMaterial"}
        )
        req_id, mat_b_body = tool_call(
            proc, req_id, "godot.resource", "create", {"path": mat_b, "class_name": "ShaderMaterial"}
        )
        if ack_ok(mat_a_body, errors, "create ShaderMaterial A") and ack_ok(mat_b_body, errors, "create ShaderMaterial B"):
            req_id, link_ab = tool_call(
                proc,
                req_id,
                "godot.resource",
                "edit",
                {"path": mat_a, "property": "next_pass", "value": variant("Resource", {"path": mat_b})},
            )
            if ack_ok(link_ab, errors, "edit next_pass A->B", undo=True):
                req_id, cycle = tool_call(
                    proc,
                    req_id,
                    "godot.resource",
                    "edit",
                    {"path": mat_b, "property": "next_pass", "value": variant("Resource", {"path": mat_a})},
                )
                expect_code(cycle, ("E_CONFLICT", "E_UNVERIFIED"), errors, "circular resource ref")

        req_id, builtin = tool_call(
            proc,
            req_id,
            "godot.resource",
            "create",
            {
                "path": scene,
                "class_name": "PlaceholderTexture2D",
                "builtin": True,
                "scene": scene,
                "node_path": "Mark",
                "property": "texture",
            },
        )
        if not ack_ok(builtin, errors, "builtin resource.create", undo=True):
            errors.append(f"builtin create/assign must ACK: {builtin}")

        req_id, grouped = tool_call(
            proc,
            req_id,
            "godot.node",
            "group",
            {"scene": scene, "node_path": "Sprite", "group": "r3w4_team", "op": "add"},
        )
        if not ack_ok(grouped, errors, "node.group add", undo=True):
            return errors

        req_id, connected = tool_call(
            proc,
            req_id,
            "godot.signal",
            "connect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "hide"},
        )
        if not ack_ok(connected, errors, "signal.connect", undo=True):
            return errors
        req_id, listed = tool_call(
            proc, req_id, "godot.signal", "list", {"scene": scene, "node_path": "Clock"}
        )
        if not ack_ok(listed, errors, "signal.list"):
            return errors
        if "timeout" not in (listed.get("after") or {}).get("signals", []):
            errors.append(f"signal.list missing timeout: {listed}")
        req_id, inspected = tool_call(
            proc, req_id, "godot.signal", "inspect", {"scene": scene, "node_path": "Clock", "signal": "timeout"}
        )
        if not ack_ok(inspected, errors, "signal.inspect"):
            return errors
        conns = (inspected.get("after") or {}).get("connections") or []
        if not any(str(row.get("method") or "") == "hide" for row in conns if isinstance(row, dict)):
            errors.append(f"signal.inspect missing hide connection: {inspected}")
        req_id, dup_conn = tool_call(
            proc,
            req_id,
            "godot.signal",
            "connect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "hide"},
        )
        expect_code(dup_conn, ("E_CONFLICT",), errors, "duplicate signal.connect")

        req_id, undone = tool_call(proc, req_id, "godot.node", "undo", {"scene": scene, "count": 1})
        if not ack_ok(undone, errors, "node.undo after signal.connect"):
            return errors
        req_id, after_undo = tool_call(
            proc, req_id, "godot.signal", "inspect", {"scene": scene, "node_path": "Clock", "signal": "timeout"}
        )
        undo_conns = (after_undo.get("after") or {}).get("connections") or []
        if any(str(row.get("method") or "") == "hide" for row in undo_conns if isinstance(row, dict)):
            errors.append(f"Undo did not remove the connection: {after_undo}")

        req_id, reconnected = tool_call(
            proc,
            req_id,
            "godot.signal",
            "connect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "hide"},
        )
        if not ack_ok(reconnected, errors, "signal.connect again", undo=True):
            return errors

        req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
        if not ack_ok(saved, errors, "scene.save"):
            return errors
        scene_text = life.res_to_abs(scene).read_text(encoding="utf-8")
        if "r3w4_team" not in scene_text:
            errors.append("group add did not persist into the packed scene")
        if "timeout" not in scene_text or "hide" not in scene_text:
            errors.append("signal connection did not persist into the packed scene")

        req_id, got_mark = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "Mark", "property": "texture"}
        )
        mark_val = ((got_mark.get("after") or {}).get("value") or {}).get("value") or {}
        if isinstance(mark_val, dict) and "::" not in str(mark_val.get("path") or ""):
            errors.append(f"built-in resource did not survive scene.save as SubResource: {got_mark}")

        life.stop_proc(godot)
        godot, godot_lines = life.start_godot(exe)
        req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"reopen hello failed: {last2}")
            return errors
        req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
        if not ack_ok(opened, errors, "scene.open after restart"):
            return errors
        req_id, queried = tool_call(
            proc, req_id, "godot.node", "query", {"scene": scene, "by": "group", "group": "r3w4_team"}
        )
        if not ack_ok(queried, errors, "node.query group after reopen"):
            return errors
        hits = (((queried.get("after") or {}).get("hits") or {}).get("items")) or []
        if not any(str(item.get("name") or "") == "Sprite" for item in hits if isinstance(item, dict)):
            errors.append(f"group membership lost after save/reopen: {queried}")
        req_id, reopen_undo = tool_call(
            proc, req_id, "godot.property", "get", {"scene": scene, "node_path": "UndoSpr", "property": "texture/size"}
        )
        if variant_xy(reopen_undo) != (22.0, 23.0):
            errors.append(f"edit+save+reopen did not keep new field: {reopen_undo}")
        req_id, unique_spr = tool_call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Sprite2D", "name": "UniqueSpr"},
        )
        if ack_ok(unique_spr, errors, "node.add UniqueSpr after reopen", undo=True):
            req_id, dest_assign = tool_call(
                proc,
                req_id,
                "godot.resource",
                "assign",
                {"scene": scene, "node_path": "UniqueSpr", "property": "texture", "resource": tex_unique},
            )
            if ack_ok(dest_assign, errors, "assign unique dest after reopen", undo=True):
                req_id, dest_reopen = tool_call(
                    proc,
                    req_id,
                    "godot.property",
                    "get",
                    {"scene": scene, "node_path": "UniqueSpr", "property": "texture/size"},
                )
                if variant_xy(dest_reopen) != (99.0, 88.0):
                    errors.append(f"reopen dest field != unique edit: {dest_reopen}")
        req_id, reopen_insp = tool_call(
            proc, req_id, "godot.signal", "inspect", {"scene": scene, "node_path": "Clock", "signal": "timeout"}
        )
        reopen_conns = (reopen_insp.get("after") or {}).get("connections") or []
        if not any(str(row.get("method") or "") == "hide" for row in reopen_conns if isinstance(row, dict)):
            errors.append(f"signal connection lost after save/reopen: {reopen_insp}")

        req_id, disconnected = tool_call(
            proc,
            req_id,
            "godot.signal",
            "disconnect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "hide"},
        )
        if not ack_ok(disconnected, errors, "signal.disconnect", undo=True):
            return errors
        req_id, gone = tool_call(
            proc, req_id, "godot.signal", "inspect", {"scene": scene, "node_path": "Clock", "signal": "timeout"}
        )
        gone_conns = (gone.get("after") or {}).get("connections") or []
        if any(str(row.get("method") or "") == "hide" for row in gone_conns if isinstance(row, dict)):
            errors.append(f"disconnect did not remove the connection: {gone}")
        req_id, missing_disc = tool_call(
            proc,
            req_id,
            "godot.signal",
            "disconnect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "hide"},
        )
        expect_code(missing_disc, ("E_CONFLICT",), errors, "disconnect missing connection")

        paused = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, paused_create = tool_call(
            proc, req_id, "godot.resource", "create", {"path": "res://r3w4/paused.tres", "class_name": "TileSet"}
        )
        expect_code(paused_create, ("E_PAUSED",), errors, "paused resource.create")
        req_id, paused_conn = tool_call(
            proc,
            req_id,
            "godot.signal",
            "connect",
            {"scene": scene, "source": "Clock", "signal": "timeout", "target": "Sprite", "method": "show"},
        )
        expect_code(paused_conn, ("E_PAUSED",), errors, "paused signal.connect")
        body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1

        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live resource ops failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: resource ops", file=sys.stderr)
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
        print("FAIL: resource ops", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: resource create/load/assign/duplicate/edit/save + UID; "
        "shared refuse / unique isolate; signal connect/undo/reopen; "
        "group persist; circular/move guards; Pause; plan progress consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
