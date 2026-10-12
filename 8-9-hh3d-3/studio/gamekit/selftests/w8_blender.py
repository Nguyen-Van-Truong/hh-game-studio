"""W8 selftest: Blender recipes export a GLB and a sprite sheet; Godot instances the GLB."""

from __future__ import annotations

import json
import struct
from pathlib import Path

from .. import asset as A
from .. import blender_recipe as B
from .. import common as C
from .. import scene as S
from . import Ctx

MAIN_TSCN = """[gd_scene format=3 uid="uid://bw8blend0001"]

[node name="Main" type="Node3D"]
"""

EXAMPLES = C.GAMEKIT_DIR / "blender" / "examples"


def _glb_document(path: Path) -> tuple[bytes, int, dict]:
    data = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    offset = 12
    document = None
    while offset + 8 <= len(data) and offset + 8 <= max(length, len(data)):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8").rstrip())
            break
    return magic, version, document or {}


def _triangle_count(document: dict) -> int:
    accessors = document.get("accessors", [])
    total = 0
    for mesh in document.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4:
                continue
            if "indices" in prim:
                total += accessors[prim["indices"]]["count"] // 3
            else:
                total += accessors[prim["attributes"]["POSITION"]]["count"] // 3
    return total


def _png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _rejects(ctx: Ctx, calls: dict) -> None:
    before = calls["n"]
    bad = ctx.root / "bad"
    out = ctx.root / "reject-out"
    _write(bad / "unknown.json", json.dumps(
        {"schema": B.SCHEMA, "name": "bad", "steps": [{"op": "explode"}]}))
    _write(bad / "range.json", json.dumps(
        {"schema": B.SCHEMA, "name": "bad", "steps": [{"op": "primitive", "type": "cube", "name": "Box", "size": -1}]}))
    _write(bad / "dotdot.json", json.dumps(
        {"schema": B.SCHEMA, "name": "bad", "steps": [{"op": "import", "path": "../secret.obj", "format": "obj"}]}))
    _write(bad / "nan.json",
           '{"schema":"hh-blender-recipe-1","name":"bad","steps":[{"op":"primitive","type":"cube","name":"Box","size":NaN}]}')
    ctx.expect_error("unknown op rejected before Blender", "VALIDATION_FAILED",
                     B.run_recipe, bad / "unknown.json", out)
    ctx.expect_error("out-of-range number rejected before Blender", "VALIDATION_FAILED",
                     B.run_recipe, bad / "range.json", out)
    ctx.expect_error("import path .. rejected before Blender", "BAD_PATH",
                     B.run_recipe, bad / "dotdot.json", out)
    ctx.expect_error("NaN JSON rejected before Blender", "BAD_REQUEST",
                     B.run_recipe, bad / "nan.json", out)
    ctx.expect_error("NaN value rejected by validator", "VALIDATION_FAILED", B.validate_recipe, {
        "schema": B.SCHEMA, "name": "bad",
        "steps": [{"op": "primitive", "type": "cube", "name": "Box", "size": float("nan")}],
    }, bad)
    ctx.check("validation did not start Blender", calls["n"] == before, started=calls["n"])


def _crate(ctx: Ctx) -> Path | None:
    out = ctx.root / "crate-out"
    result = ctx.guard("run crate recipe", lambda: B.run_recipe(EXAMPLES / "crate.json", out))
    if not isinstance(result, dict):
        return None
    glb = out / "crate.glb"
    magic, version, document = _glb_document(glb) if glb.is_file() else (b"", 0, {})
    triangles = _triangle_count(document) if document else 0
    names = [item["file"] for item in result.get("outputs", [])]
    ctx.check("crate recipe ok", result.get("ok") is True and result.get("process", {}).get("exit_code") == 0
              and result.get("process", {}).get("timed_out") is False, files=names, process=result.get("process"))
    ctx.check("crate.glb is glTF version 2", magic == b"glTF" and version == 2, magic=magic.decode("latin1", "replace"), version=version)
    ctx.check("crate.glb has at least 12 triangles", triangles >= 12, triangles=triangles)
    ctx.check("crate bevel added triangles", triangles > 12, triangles=triangles)
    ctx.check("host rehashed crate.glb", any(item["file"] == "crate.glb" and len(item["sha256"]) == 64 for item in result.get("outputs", [])))
    return glb if glb.is_file() else None


def _walker(ctx: Ctx) -> Path | None:
    out = ctx.root / "walker-out"
    result = ctx.guard("run walker recipe", lambda: B.run_recipe(EXAMPLES / "walker.json", out))
    if not isinstance(result, dict):
        return None
    glb = out / "walker.glb"
    sheet = out / "walker_walk.png"
    meta_path = out / "walker_walk.json"
    magic, version, document = _glb_document(glb) if glb.is_file() else (b"", 0, {})
    anims = [item.get("name") for item in document.get("animations", [])] if document else []
    skins = len(document.get("skins", [])) if document else 0
    size = _png_size(sheet) if sheet.is_file() else None
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    stats = result.get("manifest", {}).get("stats", {})
    action_names = {item.get("name"): item for item in stats.get("actions", []) if isinstance(item, dict)}
    ctx.check("walker recipe ok", result.get("ok") is True and result.get("process", {}).get("exit_code") == 0,
              process=result.get("process"))
    ctx.check("walker.glb is glTF version 2", magic == b"glTF" and version == 2)
    ctx.check("walker.glb has one skin and a Walk clip", skins == 1 and anims == ["Walk"], skins=skins, anims=anims)
    ctx.check("walker sprite sheet is 8 by 6 cells of 64", size == (6 * 64, 8 * 64), size=size)
    ctx.check("walker sprite json matches the sheet", meta.get("hframes") == 6 and meta.get("vframes") == 8
              and meta.get("frame_size") == [64, 64] and meta.get("directions") == 8
              and meta.get("frames") == [1, 5, 9, 13, 17, 21], meta=meta)
    walk = action_names.get("Walk", {})
    ctx.check("manifest Walk frame range is 1..24", stats.get("bones") == 3 and walk.get("frame_start") == 1
              and walk.get("frame_end") == 24, actions=stats.get("actions"), bones=stats.get("bones"))
    return glb if glb.is_file() else None


def _godot(ctx: Ctx, glb: Path) -> None:
    project = ctx.project("gk-blend", {"main.tscn": MAIN_TSCN}, main_scene="res://main.tscn")
    added = ctx.guard("asset add walker.glb (W7 gate)", lambda: A.add(
        project, glb, "res://assets/walker.glb", "self-made", "HH gamekit selftest", command_id="w8.asset.1"))
    ctx.check("walker.glb entered through the W7 license gate and Godot import",
              isinstance(added, dict) and added.get("status") == "COMMITTED"
              and isinstance(added.get("import"), dict) and added["import"].get("imported") is True,
              added=added if not isinstance(added, dict) else {k: added.get(k) for k in ("status", "import")})
    receipt = ctx.guard(
        "instance walker",
        lambda: S.apply(
            project, "res://main.tscn",
            [{"op": "instance.add", "parent": ".", "name": "Walker", "scene": "res://assets/walker.glb"}],
            "w8.instance.1",
        ),
    )
    ctx.check("godot instanced the Blender GLB", isinstance(receipt, dict) and receipt.get("status") == "COMMITTED"
              and receipt.get("readback") == "FRESH_PROCESS_MATCH",
              status=None if not isinstance(receipt, dict) else receipt.get("status"))


def run(ctx: Ctx) -> None:
    calls = {"n": 0}
    original = C.run_blender

    def _spy(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    C.run_blender = _spy
    try:
        _rejects(ctx, calls)
        _crate(ctx)
        glb = _walker(ctx)
        if glb is not None:
            _godot(ctx, glb)
        else:
            ctx.check("godot instanced the Blender GLB", False, error="walker.glb was not produced")
    finally:
        C.run_blender = original
