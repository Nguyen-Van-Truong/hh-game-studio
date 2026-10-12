"""Run a hh-blender-recipe-1 file inside pinned Blender. Host-only launcher.

Prints one ``HHGK_RESULT {json}`` line. Blender 5.2 stores new actions in slots and
layers (``action.fcurves`` is gone); ``keyframe_insert`` creates the action, then this
runner renames it and sets ``use_fake_user`` so glTF ``export_animation_mode='ACTIONS'``
keeps that name.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import sys
import tempfile
import traceback
from pathlib import Path

sys.dont_write_bytecode = True

_NAME_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")


class RecipeFailure(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _fail(detail: str) -> None:
    raise RecipeFailure(detail)


def _emit(ok: bool, detail: str | None = None, outputs: list[str] | None = None) -> None:
    if ok:
        payload: dict = {"ok": True, "outputs": outputs or []}
    else:
        payload = {"ok": False, "error": "BLENDER_FAILED", "detail": (detail or "recipe failed").replace("\n", " | ")[:1500]}
    print("HHGK_RESULT " + json.dumps(payload, separators=(",", ":")), flush=True)


class RunState:
    def __init__(self) -> None:
        self.outputs: list[Path] = []
        self.sheets: list[dict] = []
        self.owners: dict[str, str] = {}
        self.frame_start: int | None = None
        self.frame_end: int | None = None


def _parse_args(argv: list[str]) -> tuple[Path, Path]:
    if "--" not in argv:
        _fail("missing --recipe/--out arguments")
    args = argv[argv.index("--") + 1 :]
    values: dict[str, str] = {}
    index = 0
    while index < len(args):
        key = args[index]
        if key not in ("--recipe", "--out") or index + 1 >= len(args):
            _fail("arguments must be --recipe <file> --out <dir>")
        values[key[2:]] = args[index + 1]
        index += 2
    if "recipe" not in values or "out" not in values:
        _fail("arguments must be --recipe <file> --out <dir>")
    return Path(values["recipe"]), Path(values["out"])


def _safe_name(name: str) -> None:
    if not isinstance(name, str) or not name or len(name) > 64 or any(ch not in _NAME_OK for ch in name) or name in {".", ".."}:
        _fail(f"unsafe name {name!r}")


def _is_junction(path: Path) -> bool:
    """Match the host helper. A directory junction is not ``Path.is_symlink()``."""
    is_junction = getattr(os.path, "isjunction", None)
    if is_junction is not None:
        return bool(is_junction(path))
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _has_reparse_point(path: Path) -> bool:
    """True if ``path`` or an existing ancestor is a symlink or junction."""
    current = Path(os.path.abspath(str(path)))
    while True:
        if current.exists() or current.is_symlink():
            if current.is_symlink() or _is_junction(current):
                return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _refuse_out_dir(out_dir: Path) -> Path:
    out_dir = Path(os.path.abspath(str(out_dir)))
    if _has_reparse_point(out_dir):
        _fail(f"out dir passes through a symlink or junction: {out_dir}")
    return out_dir


def _literal_parent_is(out_dir: Path, path: Path, name: str) -> None:
    """Require ``path`` to sit in ``out_dir`` by literal path, without following links."""
    parent_lit = os.path.normcase(os.path.abspath(str(path.parent)))
    out_lit = os.path.normcase(os.path.abspath(str(out_dir)))
    if parent_lit != out_lit:
        _fail(f"output {name!r} escapes the out dir")


def _reject_non_finite(name: str) -> None:
    _fail(f"non-finite number {name} is not allowed")


def _out_file(out_dir: Path, name: str) -> Path:
    _safe_name(name)
    if ".." in name or name == "manifest.json" or name.startswith("."):
        _fail(f"unsafe output name {name!r}")
    out_dir = _refuse_out_dir(out_dir)
    path = out_dir / name
    _literal_parent_is(out_dir, path, name)
    return path


def _import_file(recipe_dir: Path, raw: str) -> Path:
    parts = raw.replace("\\", "/").split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        _fail(f"unsafe import path {raw!r}")
    path = recipe_dir.joinpath(*parts).resolve()
    root = recipe_dir.resolve()
    if path != root and root not in path.parents:
        _fail(f"import path escapes the recipe folder: {raw!r}")
    if not path.is_file():
        _fail(f"import file missing: {raw!r}")
    return path


def _finished(result: set, what: str) -> None:
    if result != {"FINISHED"}:
        _fail(f"{what} returned {sorted(result)}")


def _object_mode(bpy) -> None:
    if bpy.context.mode == "OBJECT":
        return
    if bpy.context.view_layer.objects.active is None:
        _fail(f"cannot leave mode {bpy.context.mode}")
    _finished(bpy.ops.object.mode_set(mode="OBJECT"), "mode_set")


def _activate(bpy, obj) -> None:
    _object_mode(bpy)
    view = bpy.context.view_layer
    for other in view.objects:
        if other.select_get():
            other.select_set(False)
    obj.select_set(True)
    view.objects.active = obj


def _require(bpy, name: str, types: tuple[str, ...] | None = None):
    _safe_name(name)
    obj = bpy.data.objects.get(name)
    if obj is None:
        _fail(f"object {name!r} not found")
    if types is not None and obj.type not in types:
        _fail(f"object {name!r} is {obj.type}, expected {' or '.join(types)}")
    return obj


def _iter_fcurves(action):
    layers = getattr(action, "layers", None)
    if layers is not None:
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                bags = getattr(strip, "channelbags", None)
                if not bags:
                    continue
                try:
                    bag_list = list(bags)
                except TypeError:
                    bag_list = [bags]
                for bag in bag_list:
                    yield from getattr(bag, "fcurves", [])
        return
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        yield from legacy


def _curve_frames(action) -> list[float]:
    frames: list[float] = []
    for curve in _iter_fcurves(action):
        for point in curve.keyframe_points:
            frames.append(float(point.co[0]))
    return frames


def _bind_slot(ad, action) -> None:
    if not hasattr(ad, "action_slot"):
        return
    slots = list(getattr(action, "slots", []))
    if not slots:
        return
    current = getattr(ad, "action_slot", None)
    if current is None or current not in slots:
        ad.action_slot = slots[0]


def _note_frames(state: RunState, bpy, start: int, end: int) -> None:
    if state.frame_start is None:
        state.frame_start, state.frame_end = start, end
    else:
        state.frame_start = min(state.frame_start, start)
        state.frame_end = max(state.frame_end or end, end)
    scene = bpy.context.scene
    scene.frame_start = int(state.frame_start)
    scene.frame_end = int(state.frame_end)


def op_clear(bpy) -> None:
    _object_mode(bpy)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in list(bpy.data.actions):
        action.use_fake_user = False
        bpy.data.actions.remove(action)
    for attr in ("meshes", "curves", "metaballs", "armatures", "cameras", "lights", "materials", "images", "lattices"):
        coll = getattr(bpy.data, attr, None)
        if coll is None:
            continue
        for block in list(coll):
            if getattr(block, "users", 0) > 0:
                continue
            coll.remove(block)


def op_primitive(bpy, step: dict) -> None:
    name = step["name"]
    if bpy.data.objects.get(name) is not None:
        _fail(f"object {name!r} already exists")
    _object_mode(bpy)
    location = tuple(step.get("location", [0.0, 0.0, 0.0]))
    rotation = tuple(math.radians(float(v)) for v in step.get("rotation_deg", [0.0, 0.0, 0.0]))
    scale = tuple(step.get("scale", [1.0, 1.0, 1.0]))
    common = {"location": location, "rotation": rotation, "scale": scale}
    kind = step["type"]
    if kind == "cube":
        result = bpy.ops.mesh.primitive_cube_add(size=float(step.get("size", 2.0)), **common)
    elif kind == "plane":
        result = bpy.ops.mesh.primitive_plane_add(size=float(step.get("size", 2.0)), **common)
    elif kind == "monkey":
        result = bpy.ops.mesh.primitive_monkey_add(size=float(step.get("size", 2.0)), **common)
    elif kind == "uv_sphere":
        segments = int(step.get("segments", 32))
        result = bpy.ops.mesh.primitive_uv_sphere_add(
            radius=float(step.get("radius", 1.0)), segments=segments, ring_count=max(3, segments // 2), **common
        )
    elif kind == "ico_sphere":
        result = bpy.ops.mesh.primitive_ico_sphere_add(
            radius=float(step.get("radius", 1.0)), subdivisions=int(step.get("segments", 2)), **common
        )
    elif kind == "cylinder":
        result = bpy.ops.mesh.primitive_cylinder_add(
            radius=float(step.get("radius", 1.0)), depth=float(step.get("depth", 2.0)),
            vertices=int(step.get("segments", 16)), **common,
        )
    elif kind == "cone":
        result = bpy.ops.mesh.primitive_cone_add(
            radius1=float(step.get("radius", 1.0)), depth=float(step.get("depth", 2.0)),
            vertices=int(step.get("segments", 16)), **common,
        )
    elif kind == "torus":
        radius = float(step.get("radius", 1.0))
        result = bpy.ops.mesh.primitive_torus_add(
            major_radius=radius, minor_radius=float(step.get("size", radius * 0.25)),
            major_segments=int(step.get("segments", 24)), minor_segments=max(3, int(step.get("segments", 12)) // 2),
            **common,
        )
    else:
        _fail(f"unknown primitive {kind!r}")
        return
    _finished(result, f"primitive {kind}")
    obj = bpy.context.active_object
    if obj is None:
        _fail("primitive operator did not create an object")
    obj.name = name
    if obj.name != name:
        _fail(f"could not name object {name!r} (Blender used {obj.name!r})")
    if obj.data is not None:
        obj.data.name = name + "Mesh"


def _apply_modifier_params(mod, kind: str, params: dict) -> None:
    if kind == "bevel":
        if "width" in params:
            mod.width = float(params["width"])
        if "segments" in params:
            mod.segments = int(params["segments"])
        if "affect" in params:
            mod.affect = params["affect"]
        if "limit_method" in params:
            mod.limit_method = params["limit_method"]
        if "offset_type" in params:
            mod.offset_type = params["offset_type"]
        if "profile" in params:
            mod.profile = float(params["profile"])
    elif kind == "subsurf":
        if "subdivision_type" in params:
            mod.subdivision_type = params["subdivision_type"]
        if "levels" in params:
            mod.levels = int(params["levels"])
            if "render_levels" not in params:
                mod.render_levels = int(params["levels"])
        if "render_levels" in params:
            mod.render_levels = int(params["render_levels"])
    elif kind == "mirror":
        for index, key in enumerate(("use_x", "use_y", "use_z")):
            if key in params:
                mod.use_axis[index] = bool(params[key])
        if "use_clip" in params:
            mod.use_clip = bool(params["use_clip"])
        if "use_mirror_merge" in params:
            mod.use_mirror_merge = bool(params["use_mirror_merge"])
        if "merge_threshold" in params:
            mod.merge_threshold = float(params["merge_threshold"])
    elif kind == "array":
        if "count" in params:
            mod.count = int(params["count"])
        if "use_relative_offset" in params:
            mod.use_relative_offset = bool(params["use_relative_offset"])
        if "relative_offset" in params:
            mod.relative_offset_displace = params["relative_offset"]
        if "use_constant_offset" in params:
            mod.use_constant_offset = bool(params["use_constant_offset"])
        if "constant_offset" in params:
            mod.use_constant_offset = True
            mod.constant_offset_displace = params["constant_offset"]
    elif kind == "solidify":
        if "thickness" in params:
            mod.thickness = float(params["thickness"])
        if "offset" in params:
            mod.offset = float(params["offset"])
        if "use_rim" in params:
            mod.use_rim = bool(params["use_rim"])
    elif kind == "decimate":
        if "decimate_type" in params:
            mod.decimate_type = params["decimate_type"]
        if "ratio" in params:
            mod.ratio = float(params["ratio"])
        if "iterations" in params:
            mod.iterations = int(params["iterations"])
    elif kind == "weld":
        if "mode" in params:
            mod.mode = params["mode"]
        if "merge_threshold" in params:
            mod.merge_threshold = float(params["merge_threshold"])
    elif kind == "triangulate":
        if "quad_method" in params:
            mod.quad_method = params["quad_method"]
        if "ngon_method" in params:
            mod.ngon_method = params["ngon_method"]
        if "min_vertices" in params:
            mod.min_vertices = int(params["min_vertices"])


def op_modifier(bpy, step: dict) -> None:
    obj = _require(bpy, step["object"], ("MESH",))
    kind = step["type"]
    bl_type = {
        "bevel": "BEVEL", "subsurf": "SUBSURF", "mirror": "MIRROR", "array": "ARRAY",
        "solidify": "SOLIDIFY", "decimate": "DECIMATE", "weld": "WELD", "triangulate": "TRIANGULATE",
    }[kind]
    mod = obj.modifiers.new(kind, bl_type)
    _apply_modifier_params(mod, kind, step.get("params") or {})


def op_apply_modifiers(bpy, step: dict) -> None:
    obj = _require(bpy, step["object"], ("MESH",))
    _activate(bpy, obj)
    while obj.modifiers:
        name = obj.modifiers[0].name
        _finished(bpy.ops.object.modifier_apply(modifier=name), f"apply modifier {name}")


def op_material(bpy, step: dict) -> None:
    obj = _require(bpy, step["object"], ("MESH",))
    mat = bpy.data.materials.get(step["name"]) or bpy.data.materials.new(step["name"])
    if mat.node_tree is None:
        mat.use_nodes = True
    if mat.node_tree is None:
        _fail(f"material {step['name']!r} has no node tree")
    bsdf = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        _fail(f"material {step['name']!r} has no Principled BSDF")
    if "base_color" in step:
        color = tuple(float(v) for v in step["base_color"])
        bsdf.inputs["Base Color"].default_value = color
        mat.diffuse_color = color
    else:
        mat.diffuse_color = tuple(bsdf.inputs["Base Color"].default_value)
    if "metallic" in step:
        bsdf.inputs["Metallic"].default_value = float(step["metallic"])
    if "roughness" in step:
        bsdf.inputs["Roughness"].default_value = float(step["roughness"])
    emission_name = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
    if "emission" in step and emission_name in bsdf.inputs:
        red, green, blue = (float(v) for v in step["emission"])
        bsdf.inputs[emission_name].default_value = (red, green, blue, 1.0)
    strength_name = "Emission Strength" if "Emission Strength" in bsdf.inputs else None
    if "emission_strength" in step and strength_name is not None:
        bsdf.inputs[strength_name].default_value = float(step["emission_strength"])
    mesh = obj.data
    mesh.materials.clear()
    mesh.materials.append(mat)


def op_transform(bpy, step: dict) -> None:
    obj = _require(bpy, step["object"])
    if "location" in step:
        obj.location = step["location"]
    if "rotation_deg" in step:
        obj.rotation_mode = "XYZ"
        obj.rotation_euler = [math.radians(float(v)) for v in step["rotation_deg"]]
    if "scale" in step:
        obj.scale = step["scale"]


def op_join(bpy, step: dict) -> None:
    objs = [_require(bpy, name, ("MESH",)) for name in step["objects"]]
    target = step["name"]
    if bpy.data.objects.get(target) is not None and target not in step["objects"]:
        _fail(f"object {target!r} already exists")
    for obj in objs:
        _activate(bpy, obj)
        _finished(bpy.ops.object.transform_apply(location=False, rotation=True, scale=True), f"transform_apply {obj.name}")
    _activate(bpy, objs[0])
    for obj in objs:
        obj.select_set(True)
    _finished(bpy.ops.object.join(), "join")
    obj = bpy.context.active_object
    if obj is None:
        _fail("join produced no object")
    obj.name = target
    if obj.name != target:
        _fail(f"could not name joined object {target!r}")
    if obj.data is not None:
        obj.data.name = target + "Mesh"


def op_parent(bpy, step: dict) -> None:
    child = _require(bpy, step["child"])
    parent = _require(bpy, step["parent"])
    if child == parent:
        _fail("cannot parent an object to itself")
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world


def op_import(bpy, step: dict, recipe_dir: Path) -> None:
    path = _import_file(recipe_dir, step["path"])
    before = set(bpy.data.objects)
    kind = step["format"]
    if kind == "gltf":
        result = bpy.ops.import_scene.gltf(filepath=str(path))
    elif kind == "obj":
        result = bpy.ops.wm.obj_import(filepath=str(path))
    elif kind == "fbx":
        result = bpy.ops.import_scene.fbx(filepath=str(path))
    elif kind == "stl":
        result = bpy.ops.wm.stl_import(filepath=str(path))
    else:
        _fail(f"unknown import format {kind!r}")
        return
    _finished(result, f"import {kind}")
    created = [obj for obj in bpy.data.objects if obj not in before]
    if not created:
        _fail(f"import of {path.name} created no objects")


def op_armature(bpy, step: dict) -> None:
    name = step["name"]
    if bpy.data.objects.get(name) is not None:
        _fail(f"object {name!r} already exists")
    data = bpy.data.armatures.new(name + "Data")
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    _activate(bpy, obj)
    _finished(bpy.ops.object.mode_set(mode="EDIT"), "armature edit mode")
    created = {}
    try:
        for bone in step["bones"]:
            edit = data.edit_bones.new(bone["name"])
            if edit.name != bone["name"]:
                _fail(f"could not name bone {bone['name']!r}")
            edit.head = bone["head"]
            edit.tail = bone["tail"]
            edit.use_connect = False
            created[bone["name"]] = edit
        for bone in step["bones"]:
            parent = bone.get("parent")
            if parent:
                created[bone["name"]].parent = created[parent]
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    got = {bone.name for bone in data.bones}
    want = {bone["name"] for bone in step["bones"]}
    if got != want:
        _fail(f"armature bones {sorted(got)} != {sorted(want)}")


def op_skin(bpy, step: dict) -> None:
    mesh = _require(bpy, step["mesh"], ("MESH",))
    arm = _require(bpy, step["armature"], ("ARMATURE",))
    _activate(bpy, arm)
    mesh.select_set(True)
    arm.select_set(True)
    _finished(bpy.ops.object.parent_set(type="ARMATURE_AUTO"), "skin ARMATURE_AUTO")
    if mesh.parent != arm:
        _fail("automatic weights did not parent the mesh to the armature")
    if not any(mod.type == "ARMATURE" and mod.object == arm for mod in mesh.modifiers):
        _fail("automatic weights did not add an armature modifier")
    if len(mesh.vertex_groups) == 0:
        _fail("automatic weights created no vertex groups")


def op_keyframes(bpy, step: dict, state: RunState) -> None:
    obj = _require(bpy, step["object"])
    bone_name = step.get("bone")
    target = obj
    if bone_name:
        if obj.type != "ARMATURE" or obj.pose is None:
            _fail("bone keyframes require an armature")
        target = obj.pose.bones.get(bone_name)
        if target is None:
            _fail(f"bone {bone_name!r} not found on {obj.name!r}")
    if hasattr(target, "rotation_mode"):
        target.rotation_mode = "XYZ"
    action_name = step["action"]
    previous = state.owners.get(action_name)
    if previous is not None and previous != obj.name:
        _fail(f"action {action_name!r} is already keyed on {previous!r}")
    ad = obj.animation_data_create()
    existing = bpy.data.actions.get(action_name)
    if existing is not None:
        ad.action = existing
        _bind_slot(ad, existing)
    elif ad.action is not None and ad.action.name != action_name:
        ad.action = None
        if hasattr(ad, "action_slot"):
            ad.action_slot = None
    scene = bpy.context.scene
    scene.render.fps = int(step["fps"])
    scene.render.fps_base = 1.0
    keyed: list[int] = []
    for key in step["keys"]:
        frame = int(key["frame"])
        keyed.append(frame)
        if "location" in key:
            target.location = key["location"]
            target.keyframe_insert(data_path="location", frame=frame)
        if "rotation_deg" in key:
            target.rotation_euler = [math.radians(float(v)) for v in key["rotation_deg"]]
            target.keyframe_insert(data_path="rotation_euler", frame=frame)
        if "scale" in key:
            target.scale = key["scale"]
            target.keyframe_insert(data_path="scale", frame=frame)
    action = ad.action
    if action is None:
        _fail("keyframe_insert did not create an action")
    if action.name != action_name:
        clash = bpy.data.actions.get(action_name)
        if clash is not None and clash != action:
            _fail(f"action {action_name!r} already exists")
        action.name = action_name
    if action.name != action_name:
        _fail(f"could not rename action to {action_name!r} (got {action.name!r})")
    action.use_fake_user = True
    curves = list(_iter_fcurves(action))
    if not curves:
        _fail("action has no fcurves after keyframe_insert (Blender 5 slot/layer layout)")
    wanted = set(keyed)
    for curve in curves:
        for point in curve.keyframe_points:
            if int(round(float(point.co[0]))) in wanted:
                point.interpolation = step["interpolation"]
        if hasattr(curve, "update"):
            curve.update()
    frames = _curve_frames(action)
    start, end = int(min(frames)), int(max(frames))
    if hasattr(action, "use_frame_range"):
        action.use_frame_range = True
        action.frame_start = start
        action.frame_end = end
    _bind_slot(ad, action)
    _note_frames(state, bpy, start, end)
    state.owners[action_name] = obj.name


def _engine_id(bpy, scene, kind: str) -> str:
    if kind == "workbench":
        candidates = ["BLENDER_WORKBENCH"]
    elif kind == "cycles":
        candidates = ["CYCLES"]
    else:
        prop = bpy.types.RenderSettings.bl_rna.properties["engine"]
        found: list[str] = []
        for source in (prop.enum_items, getattr(prop, "enum_items_static", ())):
            for item in source:
                if item.identifier not in found:
                    found.append(item.identifier)
        # This pin's background enum_items often lists only the current engine.
        preferred = [item for item in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE") if item in found]
        candidates = preferred or ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]
    errors = []
    for candidate in candidates:
        try:
            scene.render.engine = candidate
        except (TypeError, ValueError) as exc:
            errors.append(f"{candidate}: {exc}")
            continue
        return candidate
    _fail("render engine rejected: " + "; ".join(errors))
    return ""


def _bounds_center(objects) -> object:
    from mathutils import Vector

    points = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((0.0, 0.0, 0.0))
    low = Vector((min(point[i] for point in points) for i in range(3)))
    high = Vector((max(point[i] for point in points) for i in range(3)))
    return (low + high) * 0.5


def _png_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _pack_sheet(bpy, cells: list[tuple[int, int, Path]], rows: int, cols: int, cell_w: int, cell_h: int, path: Path) -> None:
    import numpy as np

    sheet = np.zeros((rows * cell_h, cols * cell_w, 4), dtype=np.float32)
    for row, col, cell_path in cells:
        image = bpy.data.images.load(str(cell_path), check_existing=False)
        try:
            if tuple(int(v) for v in image.size) != (cell_w, cell_h):
                _fail(f"sprite cell is {tuple(image.size)}, expected {(cell_w, cell_h)}")
            buf = np.empty(cell_w * cell_h * image.channels, dtype=np.float32)
            image.pixels.foreach_get(buf)
            if image.channels == 4:
                pix = buf.reshape((cell_h, cell_w, 4))
            else:
                pix = np.ones((cell_h, cell_w, 4), dtype=np.float32)
                pix[:, :, : image.channels] = buf.reshape((cell_h, cell_w, image.channels))
        finally:
            bpy.data.images.remove(image)
        # Blender pixel row 0 is the bottom of the image. Direction 0 is the top PNG row.
        y = (rows - 1 - row) * cell_h
        x = col * cell_w
        sheet[y : y + cell_h, x : x + cell_w, :] = pix
    image = bpy.data.images.new("HHSpriteSheet", cols * cell_w, rows * cell_h, alpha=True)
    try:
        flat = np.ascontiguousarray(sheet, dtype=np.float32).reshape(-1)
        image.pixels.foreach_set(flat)
        image.filepath_raw = str(path)
        image.file_format = "PNG"
        image.save()
        if not path.is_file():
            image.save_render(str(path))
    finally:
        bpy.data.images.remove(image)
    size = _png_size(path)
    if size != (cols * cell_w, rows * cell_h):
        _fail(f"sprite sheet is {size}, expected {(cols * cell_w, rows * cell_h)}")


def op_render_sprites(bpy, step: dict, out_dir: Path, state: RunState) -> None:
    from mathutils import Vector

    target = _require(bpy, step["target"])
    directions = int(step["directions"])
    start, end, stride = (int(v) for v in step["frames"])
    frames = list(range(start, end + 1, stride))
    if not frames:
        _fail("sprite frame list is empty")
    cell_w, cell_h = int(step["size"][0]), int(step["size"][1])
    scene = bpy.context.scene
    action_name = step.get("action")
    if action_name:
        action = bpy.data.actions.get(action_name)
        if action is None:
            _fail(f"action {action_name!r} not found")
        host_name = state.owners.get(action_name)
        host = bpy.data.objects.get(host_name) if host_name else None
        if host is None:
            host = target if target.type == "ARMATURE" else (target.find_armature() or target)
        ad = host.animation_data_create()
        ad.action = action
        _bind_slot(ad, action)
    show: set = set()
    stack = [target]
    while stack:
        current = stack.pop()
        if current in show:
            continue
        show.add(current)
        stack.extend(list(current.children))
    arm = target if target.type == "ARMATURE" else target.find_armature()
    saved_hide = {obj: obj.hide_render for obj in scene.objects}
    saved = {
        "camera": scene.camera,
        "engine": scene.render.engine,
        "x": scene.render.resolution_x,
        "y": scene.render.resolution_y,
        "pct": scene.render.resolution_percentage,
        "film": scene.render.film_transparent,
        "format": scene.render.image_settings.file_format,
        "color": scene.render.image_settings.color_mode,
        "filepath": scene.render.filepath,
        "frame": scene.frame_current,
        "view": scene.view_settings.view_transform,
    }
    shading = scene.display.shading
    saved_shade = (shading.light, shading.color_type, shading.show_shadows)
    cam = None
    tmp: Path | None = None
    try:
        for obj in scene.objects:
            visible = obj in show and obj.type != "ARMATURE"
            obj.hide_render = not visible
        if arm is not None:
            arm.hide_render = True
        cam_data = bpy.data.cameras.new("HHSpriteCam")
        cam = bpy.data.objects.new("HHSpriteCam", cam_data)
        scene.collection.objects.link(cam)
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = float(step["ortho_scale"])
        cam_data.clip_start = 0.01
        cam_data.clip_end = 500.0
        scene.camera = cam
        kind = step.get("engine", "workbench")
        engine_id = _engine_id(bpy, scene, kind)
        scene.render.resolution_x = cell_w
        scene.render.resolution_y = cell_h
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = bool(step.get("transparent", True))
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.image_settings.color_depth = "8"
        scene.render.use_motion_blur = False
        try:
            scene.view_settings.view_transform = "Standard"
        except (TypeError, ValueError):
            pass
        if engine_id == "BLENDER_WORKBENCH":
            shading.light = "FLAT"
            shading.color_type = "MATERIAL"
            shading.show_shadows = False
            if hasattr(shading, "show_cavity"):
                shading.show_cavity = False
            if hasattr(shading, "show_specular_highlight"):
                shading.show_specular_highlight = False
            if hasattr(shading, "show_object_outline"):
                shading.show_object_outline = False
        elif engine_id == "CYCLES":
            scene.cycles.samples = 8
            if hasattr(scene.cycles, "use_denoising"):
                scene.cycles.use_denoising = False
        elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = 8
        scene.frame_set(frames[0])
        bpy.context.view_layer.update()
        meshes = [obj for obj in show if obj.type == "MESH"]
        center = _bounds_center(meshes) if meshes else target.matrix_world.translation.copy()
        elev = math.radians(float(step["elevation_deg"]))
        dist = max(float(step["ortho_scale"]) * 2.0, 4.0)
        tmp = Path(tempfile.mkdtemp(prefix="hhgk-cells-", dir=str(out_dir)))
        cells: list[tuple[int, int, Path]] = []
        for direction in range(directions):
            azimuth = math.radians(direction * (360.0 / directions))
            offset = Vector((
                dist * math.cos(elev) * math.sin(azimuth),
                -dist * math.cos(elev) * math.cos(azimuth),
                dist * math.sin(elev),
            ))
            cam.location = center + offset
            cam.rotation_euler = (Vector(center) - cam.location).to_track_quat("-Z", "Y").to_euler()
            for column, frame in enumerate(frames):
                scene.frame_set(int(frame))
                cell_path = tmp / f"d{direction:02d}f{column:02d}.png"
                scene.render.filepath = str(cell_path)
                _finished(bpy.ops.render.render(write_still=True), f"sprite d{direction} f{frame}")
                if not cell_path.is_file():
                    _fail(f"sprite render wrote no file for direction {direction} frame {frame}")
                cells.append((direction, column, cell_path))
        sheet = _out_file(out_dir, step["out"])
        _pack_sheet(bpy, cells, directions, len(frames), cell_w, cell_h, sheet)
        meta = {
            "hframes": len(frames),
            "vframes": directions,
            "frame_size": [cell_w, cell_h],
            "directions": directions,
            "frames": frames,
        }
        sidecar = _out_file(out_dir, Path(step["out"]).stem + ".json")
        sidecar.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
        state.outputs.extend((sheet, sidecar))
        state.sheets.append({"file": sheet.name, "grid": meta})
    finally:
        if cam is not None:
            data = cam.data
            bpy.data.objects.remove(cam, do_unlink=True)
            if data is not None and getattr(data, "users", 1) == 0:
                bpy.data.cameras.remove(data)
        for obj, hidden in saved_hide.items():
            if obj.name in bpy.data.objects:
                obj.hide_render = hidden
        scene.camera = saved["camera"] if saved["camera"] is not None and saved["camera"].name in bpy.data.objects else None
        try:
            scene.render.engine = saved["engine"]
        except (TypeError, ValueError):
            pass
        scene.render.resolution_x = saved["x"]
        scene.render.resolution_y = saved["y"]
        scene.render.resolution_percentage = saved["pct"]
        scene.render.film_transparent = saved["film"]
        scene.render.image_settings.file_format = saved["format"]
        scene.render.image_settings.color_mode = saved["color"]
        scene.render.filepath = saved["filepath"]
        shading.light, shading.color_type, shading.show_shadows = saved_shade
        try:
            scene.view_settings.view_transform = saved["view"]
        except (TypeError, ValueError):
            pass
        try:
            scene.frame_set(int(saved["frame"]))
        except (TypeError, ValueError, RuntimeError):
            pass
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def _read_glb(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        _fail(f"{path.name} is not a GLB")
    _magic, version, _length = struct.unpack_from("<4sII", data, 0)
    if version != 2:
        _fail(f"{path.name} GLB version is {version}")
    offset = 12
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.decode("utf-8").rstrip())
    _fail(f"{path.name} GLB has no JSON chunk")
    return {}


def op_export_gltf(bpy, step: dict, out_dir: Path, state: RunState) -> None:
    path = _out_file(out_dir, step["out"])
    scene = bpy.context.scene
    if state.frame_start is not None and state.frame_end is not None:
        scene.frame_start = int(state.frame_start)
        scene.frame_end = int(state.frame_end)
    selected = step.get("objects")
    use_selection = selected is not None
    if use_selection:
        wanted = set(selected)
        for name in list(wanted):
            obj = _require(bpy, name)
            arm = obj if obj.type == "ARMATURE" else obj.find_armature()
            if arm is not None:
                wanted.add(arm.name)
            if obj.parent is not None and obj.parent.type == "ARMATURE":
                wanted.add(obj.parent.name)
        for obj in scene.objects:
            obj.select_set(obj.name in wanted)
        _activate(bpy, _require(bpy, selected[0]))
    rna = bpy.ops.export_scene.gltf.get_rna_type().properties
    animations = bool(step.get("animations", True))
    mode_items = {item.identifier for item in rna["export_animation_mode"].enum_items}
    if mode_items and "ACTIONS" not in mode_items:
        _fail(f"glTF export_animation_mode ACTIONS missing, have {sorted(mode_items)}")
    kwargs = {
        "filepath": str(path),
        "export_format": "GLB",
        "export_animations": animations,
        "export_animation_mode": "ACTIONS",
        "export_apply": True,
        "export_yup": True,
        "export_skins": True,
        "use_selection": use_selection,
        "export_cameras": False,
        "export_lights": False,
        "export_frame_range": state.frame_start is not None,
        "will_save_settings": False,
        "check_existing": False,
    }
    missing = [key for key in ("export_format", "export_animations", "export_animation_mode", "export_apply", "export_yup") if key not in rna]
    if missing:
        _fail(f"glTF exporter is missing {missing}")
    kwargs = {key: value for key, value in kwargs.items() if key == "filepath" or key in rna}
    _finished(bpy.ops.export_scene.gltf(**kwargs), "export_gltf")
    if not path.is_file() or path.stat().st_size < 20:
        _fail("glTF export wrote no GLB")
    doc = _read_glb(path)
    if animations and state.owners:
        names = [anim.get("name") for anim in doc.get("animations", [])]
        missing_actions = [name for name in state.owners if name not in names]
        if missing_actions:
            _fail(f"GLB animations {names} missing {missing_actions}")
    skinned = False
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        if use_selection and not obj.select_get():
            continue
        if any(mod.type == "ARMATURE" for mod in obj.modifiers):
            skinned = True
    if skinned and len(doc.get("skins", [])) < 1:
        _fail("GLB export dropped the armature skin")
    state.outputs.append(path)


def op_save_blend(bpy, step: dict, out_dir: Path, state: RunState) -> None:
    path = _out_file(out_dir, step["out"])
    _finished(bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False, compress=True), "save_blend")
    if not path.is_file():
        _fail("save_blend wrote no file")
    state.outputs.append(path)


def _stats(bpy, state: RunState) -> dict:
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objects = list(scene.objects)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    triangles = 0
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            triangles += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    bones = sum(len(obj.data.bones) for obj in objects if obj.type == "ARMATURE")
    actions = []
    for action in bpy.data.actions:
        frames = _curve_frames(action)
        if not frames:
            continue
        actions.append({"name": action.name, "frame_start": int(min(frames)), "frame_end": int(max(frames))})
    actions.sort(key=lambda item: item["name"])
    return {
        "objects": len(objects),
        "meshes": len(meshes),
        "triangles": triangles,
        "bones": bones,
        "actions": actions,
        "sprite_sheets": state.sheets,
    }


def _sha(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _run() -> None:
    import bpy

    recipe_path, out_dir = _parse_args(sys.argv)
    if not recipe_path.is_file():
        _fail(f"recipe missing: {recipe_path}")
    out_dir = _refuse_out_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir = _refuse_out_dir(out_dir)
    recipe = json.loads(recipe_path.read_text(encoding="utf-8-sig"), parse_constant=_reject_non_finite)
    if not isinstance(recipe, dict) or not isinstance(recipe.get("steps"), list):
        _fail("recipe has no steps")
    state = RunState()
    recipe_dir = recipe_path.parent
    for index, step in enumerate(recipe["steps"]):
        op = step.get("op") if isinstance(step, dict) else None
        print(f"HHGK_STEP {index} {op}", flush=True)
        try:
            if op == "clear":
                op_clear(bpy)
            elif op == "primitive":
                op_primitive(bpy, step)
            elif op == "modifier":
                op_modifier(bpy, step)
            elif op == "apply_modifiers":
                op_apply_modifiers(bpy, step)
            elif op == "material":
                op_material(bpy, step)
            elif op == "transform":
                op_transform(bpy, step)
            elif op == "join":
                op_join(bpy, step)
            elif op == "parent":
                op_parent(bpy, step)
            elif op == "import":
                op_import(bpy, step, recipe_dir)
            elif op == "armature":
                op_armature(bpy, step)
            elif op == "skin":
                op_skin(bpy, step)
            elif op == "keyframes":
                op_keyframes(bpy, step, state)
            elif op == "render_sprites":
                op_render_sprites(bpy, step, out_dir, state)
            elif op == "export_gltf":
                op_export_gltf(bpy, step, out_dir, state)
            elif op == "save_blend":
                op_save_blend(bpy, step, out_dir, state)
            else:
                _fail(f"unknown op {op!r}")
        except RecipeFailure as exc:
            raise RecipeFailure(f"step {index} ({op}): {exc.detail}") from exc
    if len({path.name for path in state.outputs}) != len(state.outputs):
        _fail("two steps wrote the same output file")
    manifest = {
        "schema": "hh-blender-manifest-1",
        "name": recipe.get("name"),
        "blender": bpy.app.version_string,
        "outputs": [_sha(path) for path in state.outputs],
        "stats": _stats(bpy, state),
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out_dir = _refuse_out_dir(out_dir)
    target = out_dir / "manifest.json"
    _literal_parent_is(out_dir, target, "manifest.json")
    tmp = target.with_name(f".manifest.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    _emit(True, outputs=[item["file"] for item in manifest["outputs"]])


def main() -> None:
    try:
        _run()
    except RecipeFailure as exc:
        _emit(False, exc.detail)
        sys.exit(1)
    except Exception:
        _emit(False, traceback.format_exc()[-1500:])
        sys.exit(1)


if __name__ == "__main__":
    main()
