"""hh blender: JSON recipes for the pinned Blender (primitives, materials, rigs, sprites, GLB).

``hh blender run <recipe.json> --out-dir <dir>`` validates the recipe on the host
before Blender starts. The runner writes ``<out-dir>/manifest.json``; the host
re-hashes every listed output and only then returns ok.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from pathlib import Path
from typing import Any

from . import common as C

SCHEMA = "hh-blender-recipe-1"
MANIFEST_SCHEMA = "hh-blender-manifest-1"
MANIFEST_NAME = "manifest.json"
MAX_STEPS = 200
MAX_KEYS = 512
MAX_BONES = 64
MAX_SPRITE_CELLS = 128
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_IMPORT_SEG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

PRIMITIVE_TYPES = ("cube", "uv_sphere", "ico_sphere", "cylinder", "cone", "torus", "plane", "monkey")
MODIFIER_TYPES = ("bevel", "subsurf", "mirror", "array", "solidify", "decimate", "weld", "triangulate")
IMPORT_FORMATS = ("gltf", "obj", "fbx", "stl")
INTERPOLATIONS = ("LINEAR", "BEZIER", "CONSTANT")
ENGINES = ("workbench", "eevee", "cycles")

# Fields a primitive may carry besides the shared transform.
_PRIM_FIELDS: dict[str, tuple[str, ...]] = {
    "cube": ("size",),
    "plane": ("size",),
    "monkey": ("size",),
    "uv_sphere": ("radius", "segments"),
    "ico_sphere": ("radius", "segments"),
    "cylinder": ("radius", "depth", "segments"),
    "cone": ("radius", "depth", "segments"),
    "torus": ("radius", "size", "segments"),
}
_SEGMENT_RANGE = {
    "uv_sphere": (3, 64),
    "ico_sphere": (1, 5),
    "cylinder": (3, 64),
    "cone": (3, 64),
    "torus": (3, 48),
}
_TRANSFORM_FIELDS = ("location", "rotation_deg", "scale")

# (kind, lo, hi) or (kind, choices). kind is int|num|bool|enum|vec.
_MODIFIER_PARAMS: dict[str, dict[str, tuple]] = {
    "bevel": {
        "width": ("num", 1e-5, 10.0),
        "segments": ("int", 1, 6),
        "affect": ("enum", ("VERTICES", "EDGES")),
        "limit_method": ("enum", ("NONE", "ANGLE", "WEIGHT", "VGROUP")),
        "offset_type": ("enum", ("OFFSET", "WIDTH", "DEPTH", "PERCENT", "ABSOLUTE")),
        "profile": ("num", 0.0, 1.0),
    },
    "subsurf": {
        "levels": ("int", 0, 3),
        "render_levels": ("int", 0, 3),
        "subdivision_type": ("enum", ("CATMULL_CLARK", "SIMPLE")),
    },
    "mirror": {
        "use_x": ("bool",),
        "use_y": ("bool",),
        "use_z": ("bool",),
        "use_clip": ("bool",),
        "use_mirror_merge": ("bool",),
        "merge_threshold": ("num", 0.0, 1.0),
    },
    "array": {
        "count": ("int", 1, 50),
        "use_relative_offset": ("bool",),
        "relative_offset": ("vec", -100.0, 100.0),
        "use_constant_offset": ("bool",),
        "constant_offset": ("vec", -100.0, 100.0),
    },
    "solidify": {
        "thickness": ("num", -10.0, 10.0),
        "offset": ("num", -1.0, 1.0),
        "use_rim": ("bool",),
    },
    "decimate": {
        "ratio": ("num", 0.01, 1.0),
        "decimate_type": ("enum", ("COLLAPSE", "UNSUBDIV", "DISSOLVE")),
        "iterations": ("int", 0, 6),
    },
    "weld": {
        "merge_threshold": ("num", 0.0, 10.0),
        "mode": ("enum", ("ALL", "CONNECTED")),
    },
    "triangulate": {
        "quad_method": ("enum", ("BEAUTY", "FIXED", "FIXED_ALTERNATE", "SHORTEST_DIAGONAL", "LONGEST_DIAGONAL")),
        "ngon_method": ("enum", ("BEAUTY", "CLIP")),
        "min_vertices": ("int", 3, 8),
    },
}

_OPS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "clear": ((), ()),
    "primitive": (("type", "name"), ("size", "radius", "depth", "segments", "location", "rotation_deg", "scale")),
    "modifier": (("object", "type"), ("params",)),
    "apply_modifiers": (("object",), ()),
    "material": (("object", "name"), ("base_color", "metallic", "roughness", "emission", "emission_strength")),
    "transform": (("object",), ("location", "rotation_deg", "scale")),
    "join": (("objects", "name"), ()),
    "parent": (("child", "parent"), ()),
    "import": (("path", "format"), ()),
    "armature": (("name", "bones"), ()),
    "skin": (("mesh", "armature"), ()),
    "keyframes": (("object", "action", "fps", "interpolation", "keys"), ("bone",)),
    "render_sprites": (("target", "directions", "frames", "size", "ortho_scale", "elevation_deg", "out"),
                       ("action", "engine", "transparent")),
    "export_gltf": (("out",), ("objects", "animations")),
    "save_blend": (("out",), ()),
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _num(value: Any, where: str, lo: float, hi: float, *, lo_open: bool = False) -> float:
    if not _is_num(value):
        _fail(where, "expected a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        _fail(where, "non-finite number")
    number = float(value)
    if lo_open:
        ok = lo < number <= hi
    else:
        ok = lo <= number <= hi
    if not ok:
        _fail(where, f"{number} is outside {lo}..{hi}")
    return number


def _integer(value: Any, where: str, lo: int, hi: int) -> int:
    if not _is_int(value):
        _fail(where, "expected an integer")
    if value < lo or value > hi:
        _fail(where, f"{value} is outside {lo}..{hi}")
    return value


def _vec3(value: Any, where: str, lo: float, hi: float) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        _fail(where, "expected a list of 3 numbers")
    return [_num(item, f"{where}[{i}]", lo, hi) for i, item in enumerate(value)]


def _scale(value: Any, where: str) -> list[float]:
    vec = _vec3(value, where, -1000.0, 1000.0)
    for i, item in enumerate(vec):
        if abs(item) < 1e-4:
            _fail(f"{where}[{i}]", "scale component is too close to 0")
    return vec


def _color(value: Any, where: str, count: int) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        _fail(where, f"expected {count} numbers in 0..1")
    return [_num(item, f"{where}[{i}]", 0.0, 1.0) for i, item in enumerate(value)]


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or NAME_RE.fullmatch(value) is None or value in {".", ".."}:
        _fail(where, "name must match [A-Za-z0-9_.-]{1,64}")
    return value


def _names(value: Any, where: str, lo: int, hi: int) -> list[str]:
    if not isinstance(value, list) or not lo <= len(value) <= hi:
        _fail(where, f"expected {lo}..{hi} names")
    names = [_name(item, f"{where}[{i}]") for i, item in enumerate(value)]
    if len(set(names)) != len(names):
        _fail(where, "duplicate name")
    return names


def _plain_file(value: Any, where: str, suffix: str, claimed: set[str]) -> str:
    if not isinstance(value, str) or any(sep in value for sep in ("/", "\\", ":")) or value in {".", ".."}:
        _fail(where, "output file name must be a plain file name", "BAD_PATH")
    if NAME_RE.fullmatch(value) is None or ".." in value or value.startswith("."):
        _fail(where, "output file name must match [A-Za-z0-9_.-]{1,64}", "BAD_PATH")
    if not value.endswith(suffix) or value == suffix:
        _fail(where, f"output file must end with {suffix}")
    if value == MANIFEST_NAME:
        _fail(where, "manifest.json is reserved")
    if value in claimed:
        _fail(where, f"output {value!r} is already used by another step")
    claimed.add(value)
    return value


def _import_file(value: Any, where: str, recipe_dir: Path) -> Path:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        _fail(where, "import path must be relative to the recipe file", "BAD_PATH")
    parts = re.split(r"[/\\]", value)
    if any(part in ("", ".", "..") or _IMPORT_SEG_RE.fullmatch(part) is None for part in parts):
        _fail(where, "import path must stay inside the recipe folder (no '..', no absolute)", "BAD_PATH")
    full = recipe_dir.joinpath(*parts)
    if not C.is_within(full, recipe_dir):
        _fail(where, "import path escapes the recipe folder", "BAD_PATH")
    if full.is_symlink():
        _fail(where, "import path is a symlink", "BAD_PATH")
    if not full.is_file():
        _fail(where, f"import file not found: {value}", "NOT_FOUND")
    return full


def _modifier_params(value: Any, mod_type: str, where: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        _fail(where, "params must be an object")
    spec = _MODIFIER_PARAMS[mod_type]
    extra = sorted(set(value) - set(spec))
    if extra:
        _fail(where, f"unknown params {extra}")
    for key, item in value.items():
        kind = spec[key]
        item_where = f"{where}.{key}"
        if kind[0] == "bool":
            if not isinstance(item, bool):
                _fail(item_where, "expected a boolean")
        elif kind[0] == "int":
            _integer(item, item_where, kind[1], kind[2])
        elif kind[0] == "num":
            _num(item, item_where, kind[1], kind[2])
        elif kind[0] == "enum":
            if item not in kind[1]:
                _fail(item_where, f"expected one of {list(kind[1])}")
        elif kind[0] == "vec":
            _vec3(item, item_where, kind[1], kind[2])


def _positive_size(value: Any, where: str) -> None:
    _num(value, where, 0.0, 100.0, lo_open=True)


def _primitive(step: dict[str, Any], where: str) -> None:
    prim = step.get("type")
    if prim not in PRIMITIVE_TYPES:
        _fail(f"{where}.type", f"expected one of {list(PRIMITIVE_TYPES)}")
    _name(step.get("name"), f"{where}.name")
    allowed = set(_PRIM_FIELDS[prim]) | set(_TRANSFORM_FIELDS)
    extra = sorted(set(step) - {"op", "type", "name"} - allowed)
    if extra:
        _fail(where, f"fields {extra} are not used by primitive {prim}")
    for key in ("size", "radius", "depth"):
        if key in step:
            _positive_size(step[key], f"{where}.{key}")
    if "segments" in step:
        lo, hi = _SEGMENT_RANGE[prim]
        _integer(step["segments"], f"{where}.segments", lo, hi)
    _transform_fields(step, where)


def _transform_fields(step: dict[str, Any], where: str) -> None:
    if "location" in step:
        _vec3(step["location"], f"{where}.location", -10000.0, 10000.0)
    if "rotation_deg" in step:
        _vec3(step["rotation_deg"], f"{where}.rotation_deg", -3600.0, 3600.0)
    if "scale" in step:
        _scale(step["scale"], f"{where}.scale")


def _bones(value: Any, where: str) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_BONES:
        _fail(where, f"expected 1..{MAX_BONES} bones")
    names: list[str] = []
    parents: dict[str, str] = {}
    for i, bone in enumerate(value):
        bone_where = f"{where}[{i}]"
        if not isinstance(bone, dict):
            _fail(bone_where, "bone must be an object")
        extra = sorted(set(bone) - {"name", "head", "tail", "parent"})
        if extra:
            _fail(bone_where, f"unknown fields {extra}")
        for key in ("name", "head", "tail"):
            if key not in bone:
                _fail(bone_where, f"missing {key}")
        bone_name = _name(bone["name"], f"{bone_where}.name")
        head = _vec3(bone["head"], f"{bone_where}.head", -1000.0, 1000.0)
        tail = _vec3(bone["tail"], f"{bone_where}.tail", -1000.0, 1000.0)
        if sum((a - b) ** 2 for a, b in zip(head, tail)) < 1e-8:
            _fail(bone_where, "bone head and tail are the same point")
        if "parent" in bone:
            parent = _name(bone["parent"], f"{bone_where}.parent")
            if parent == bone_name:
                _fail(bone_where, "bone cannot parent itself")
            parents[bone_name] = parent
        names.append(bone_name)
    if len(set(names)) != len(names):
        _fail(where, "duplicate bone name")
    known = set(names)
    for bone_name, parent in parents.items():
        if parent not in known:
            _fail(where, f"bone {bone_name!r} parents unknown bone {parent!r}")
        seen: set[str] = set()
        current: str | None = bone_name
        while current in parents:
            if current in seen:
                _fail(where, "bone parent cycle")
            seen.add(current)
            current = parents[current]


def _keys(value: Any, where: str) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_KEYS:
        _fail(where, f"expected 1..{MAX_KEYS} keys")
    for i, key in enumerate(value):
        key_where = f"{where}[{i}]"
        if not isinstance(key, dict):
            _fail(key_where, "key must be an object")
        extra = sorted(set(key) - {"frame", "location", "rotation_deg", "scale"})
        if extra:
            _fail(key_where, f"unknown fields {extra}")
        if "frame" not in key:
            _fail(key_where, "missing frame")
        _integer(key["frame"], f"{key_where}.frame", 0, 100_000)
        channels = [name for name in ("location", "rotation_deg", "scale") if name in key]
        if not channels:
            _fail(key_where, "key needs location, rotation_deg, or scale")
        if "location" in key:
            _vec3(key["location"], f"{key_where}.location", -10000.0, 10000.0)
        if "rotation_deg" in key:
            _vec3(key["rotation_deg"], f"{key_where}.rotation_deg", -3600.0, 3600.0)
        if "scale" in key:
            _scale(key["scale"], f"{key_where}.scale")


def _frame_count(value: Any, where: str) -> int:
    if not isinstance(value, list) or len(value) != 3:
        _fail(where, "frames must be [start, end, step]")
    start = _integer(value[0], f"{where}[0]", 0, 100_000)
    end = _integer(value[1], f"{where}[1]", 0, 100_000)
    stride = _integer(value[2], f"{where}[2]", 1, 1000)
    if end < start:
        _fail(where, "frame end is before start")
    count = (end - start) // stride + 1
    if count > 32:
        _fail(where, "at most 32 frames per direction")
    return count


def _validate_step(step: Any, index: int, recipe_dir: Path, claimed: set[str]) -> None:
    where = f"steps[{index}]"
    if not isinstance(step, dict) or not isinstance(step.get("op"), str):
        _fail(where, "step must be an object with an op string")
    op = step["op"]
    if op not in _OPS:
        _fail(where, f"unknown op {op!r}", extra_known=True)
    req, opt = _OPS[op]
    for key in req:
        if key not in step:
            _fail(where, f"missing {key!r}")
    # primitive allows only the fields for its type; checked below.
    if op != "primitive":
        extra = sorted(set(step) - set(req) - set(opt) - {"op"})
        if extra:
            _fail(where, f"unknown fields {extra}")
    if op == "clear":
        return
    if op == "primitive":
        _primitive(step, where)
        return
    if op == "modifier":
        _name(step["object"], f"{where}.object")
        if step["type"] not in MODIFIER_TYPES:
            _fail(f"{where}.type", f"expected one of {list(MODIFIER_TYPES)}")
        _modifier_params(step.get("params", {}), step["type"], f"{where}.params")
        return
    if op == "apply_modifiers":
        _name(step["object"], f"{where}.object")
        return
    if op == "material":
        _name(step["object"], f"{where}.object")
        _name(step["name"], f"{where}.name")
        if "base_color" in step:
            _color(step["base_color"], f"{where}.base_color", 4)
        if "metallic" in step:
            _num(step["metallic"], f"{where}.metallic", 0.0, 1.0)
        if "roughness" in step:
            _num(step["roughness"], f"{where}.roughness", 0.0, 1.0)
        if "emission" in step:
            _color(step["emission"], f"{where}.emission", 3)
        if "emission_strength" in step:
            _num(step["emission_strength"], f"{where}.emission_strength", 0.0, 100.0)
        return
    if op == "transform":
        _name(step["object"], f"{where}.object")
        if not any(key in step for key in _TRANSFORM_FIELDS):
            _fail(where, "transform needs location, rotation_deg, or scale")
        _transform_fields(step, where)
        return
    if op == "join":
        _names(step["objects"], f"{where}.objects", 2, 32)
        _name(step["name"], f"{where}.name")
        return
    if op == "parent":
        child = _name(step["child"], f"{where}.child")
        parent = _name(step["parent"], f"{where}.parent")
        if child == parent:
            _fail(where, "cannot parent an object to itself")
        return
    if op == "import":
        _import_file(step["path"], f"{where}.path", recipe_dir)
        if step["format"] not in IMPORT_FORMATS:
            _fail(f"{where}.format", f"expected one of {list(IMPORT_FORMATS)}")
        return
    if op == "armature":
        _name(step["name"], f"{where}.name")
        _bones(step["bones"], f"{where}.bones")
        return
    if op == "skin":
        _name(step["mesh"], f"{where}.mesh")
        _name(step["armature"], f"{where}.armature")
        return
    if op == "keyframes":
        _name(step["object"], f"{where}.object")
        if "bone" in step:
            _name(step["bone"], f"{where}.bone")
        _name(step["action"], f"{where}.action")
        _integer(step["fps"], f"{where}.fps", 1, 120)
        if step["interpolation"] not in INTERPOLATIONS:
            _fail(f"{where}.interpolation", f"expected one of {list(INTERPOLATIONS)}")
        _keys(step["keys"], f"{where}.keys")
        return
    if op == "render_sprites":
        _name(step["target"], f"{where}.target")
        if "action" in step:
            _name(step["action"], f"{where}.action")
        directions = _integer(step["directions"], f"{where}.directions", 1, 16)
        count = _frame_count(step["frames"], f"{where}.frames")
        if directions * count > MAX_SPRITE_CELLS:
            _fail(where, f"at most {MAX_SPRITE_CELLS} sprite cells")
        if not isinstance(step["size"], list) or len(step["size"]) != 2:
            _fail(f"{where}.size", "expected [width, height]")
        width = _integer(step["size"][0], f"{where}.size[0]", 1, 512)
        height = _integer(step["size"][1], f"{where}.size[1]", 1, 512)
        if width * count > 4096 or height * directions > 4096:
            _fail(f"{where}.size", "sprite sheet would be larger than 4096 px on one side")
        _num(step["ortho_scale"], f"{where}.ortho_scale", 0.0, 1000.0, lo_open=True)
        _num(step["elevation_deg"], f"{where}.elevation_deg", -90.0, 90.0)
        engine = step.get("engine", "workbench")
        if engine not in ENGINES:
            _fail(f"{where}.engine", f"expected one of {list(ENGINES)}")
        if "transparent" in step and not isinstance(step["transparent"], bool):
            _fail(f"{where}.transparent", "expected a boolean")
        png = _plain_file(step["out"], f"{where}.out", ".png", claimed)
        sidecar = Path(png).stem + ".json"
        _plain_file(sidecar, f"{where}.out", ".json", claimed)
        return
    if op == "export_gltf":
        _plain_file(step["out"], f"{where}.out", ".glb", claimed)
        if "objects" in step:
            _names(step["objects"], f"{where}.objects", 1, 64)
        if "animations" in step and not isinstance(step["animations"], bool):
            _fail(f"{where}.animations", "expected a boolean")
        return
    if op == "save_blend":
        _plain_file(step["out"], f"{where}.out", ".blend", claimed)


def _fail(where: str, detail: str, code: str = "VALIDATION_FAILED", extra_known: bool = False) -> None:
    extra: dict[str, Any] = {}
    if extra_known:
        extra["known_ops"] = sorted(_OPS)
    raise C.GamekitError(code, f"{where}: {detail}" if where else detail, **extra)


def validate_recipe(data: Any, recipe_dir: Path) -> dict[str, Any]:
    """Reject a bad recipe before any Blender process is started.

    ``recipe_dir`` is the folder that relative ``import`` paths are resolved against
    (the directory that contains the recipe file).
    """
    recipe_dir = Path(recipe_dir)
    if not isinstance(data, dict):
        raise C.GamekitError("BAD_REQUEST", "recipe must be a JSON object")
    extra = sorted(set(data) - {"schema", "name", "steps"})
    if extra:
        _fail("", f"unknown recipe fields {extra}")
    if data.get("schema") != SCHEMA:
        raise C.GamekitError("BAD_REQUEST", f"schema must be {SCHEMA!r}")
    _name(data.get("name"), "name")
    steps = data.get("steps")
    if not isinstance(steps, list):
        _fail("steps", "must be a list")
    if not steps:
        _fail("steps", "must not be empty")
    if len(steps) > MAX_STEPS:
        _fail("steps", f"at most {MAX_STEPS} steps")
    claimed: set[str] = set()
    for index, step in enumerate(steps):
        _validate_step(step, index, recipe_dir, claimed)
    return data


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed")


def _parse_float(text: str) -> float:
    """Reject overflow such as ``1e309``. ``parse_constant`` never sees those strings."""
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"non-finite number {text} is not allowed")
    return number


def _read_recipe_json(path: Path) -> Any:
    """Parse one recipe file. ``C.read_json`` stays unchanged for every other caller."""
    if not path.is_file():
        raise C.GamekitError("NOT_FOUND", f"json file missing: {path}")
    size = path.stat().st_size
    if size > C.MAX_JSON_BYTES:
        raise C.GamekitError("BAD_REQUEST", f"json file too large ({size} bytes): {path}")
    try:
        return json.loads(
            path.read_bytes().decode("utf-8-sig"),
            parse_float=_parse_float,
            parse_constant=_reject_constant,
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise C.GamekitError("BAD_REQUEST", f"invalid json in {path}: {exc}") from exc


def load_recipe(path: str | Path) -> tuple[Path, dict[str, Any]]:
    """Load a recipe. Junctions, ``studio/.local`` and ``private.raw`` are refused before open."""
    recipe_path = C.refuse_unsafe_host_path(Path(path), what="recipe")
    reason = C.forbidden_reason(recipe_path)
    if reason:
        raise C.GamekitError("BAD_PATH", reason)
    data = _read_recipe_json(recipe_path)
    validate_recipe(data, recipe_path.parent)
    return recipe_path, data


def _prepare_out_dir(path: str | Path) -> Path:
    """Create ``out-dir`` only when it is a real directory, not a symlink or junction."""
    out = C.refuse_unsafe_host_path(Path(path), what="out-dir")
    reason = C.forbidden_reason(out)
    if reason:
        raise C.GamekitError("BAD_PATH", reason)
    if out.exists() and not out.is_dir():
        raise C.GamekitError("BAD_PATH", "out-dir is not a directory")
    out = C.refuse_unsafe_host_path(out, what="out-dir")
    out.mkdir(parents=True, exist_ok=True)
    return C.refuse_unsafe_host_path(out, what="out-dir")


def _check_timeout(timeout: float) -> float:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(float(timeout)):
        raise C.GamekitError("BAD_REQUEST", "timeout must be a finite number of seconds")
    if not 1 <= float(timeout) <= 3600:
        raise C.GamekitError("BAD_REQUEST", "timeout must be between 1 and 3600 seconds")
    return float(timeout)


def _verify_manifest(out_dir: Path, manifest: Any, recipe_name: str) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise C.GamekitError("VALIDATION_FAILED", "manifest schema mismatch")
    if manifest.get("name") != recipe_name:
        raise C.GamekitError("VALIDATION_FAILED", "manifest name does not match the recipe")
    stats = manifest.get("stats")
    if not isinstance(stats, dict):
        raise C.GamekitError("VALIDATION_FAILED", "manifest stats missing")
    for key in ("objects", "meshes", "triangles", "bones"):
        if not _is_int(stats.get(key)) or stats[key] < 0:
            raise C.GamekitError("VALIDATION_FAILED", f"manifest stats.{key} is not a count")
    actions = stats.get("actions")
    if not isinstance(actions, list):
        raise C.GamekitError("VALIDATION_FAILED", "manifest stats.actions must be a list")
    for i, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("name"), str):
            raise C.GamekitError("VALIDATION_FAILED", f"manifest action {i} is malformed")
        if not _is_int(action.get("frame_start")) or not _is_int(action.get("frame_end")):
            raise C.GamekitError("VALIDATION_FAILED", f"manifest action {action.get('name')!r} has no frame range")
    if not isinstance(stats.get("sprite_sheets"), list):
        raise C.GamekitError("VALIDATION_FAILED", "manifest stats.sprite_sheets must be a list")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        raise C.GamekitError("VALIDATION_FAILED", "manifest outputs must be a list")
    verified: list[dict[str, Any]] = []
    seen: set[str] = set()
    out_abs = Path(os.path.abspath(str(out_dir)))
    for item in outputs:
        if not isinstance(item, dict) or not isinstance(item.get("file"), str):
            raise C.GamekitError("VALIDATION_FAILED", "manifest output is malformed")
        name = item["file"]
        if name in seen or name == MANIFEST_NAME or any(sep in name for sep in ("/", "\\", ":")) or ".." in name:
            raise C.GamekitError("BAD_PATH", f"manifest output escapes out-dir: {name!r}")
        if NAME_RE.fullmatch(name) is None or name.startswith("."):
            raise C.GamekitError("BAD_PATH", f"manifest output is not a plain file name: {name!r}")
        path = out_dir / name
        if path.is_symlink() or not path.is_file():
            raise C.GamekitError("VALIDATION_FAILED", f"output missing: {name}")
        if Path(os.path.abspath(str(path.parent))) != out_abs:
            raise C.GamekitError("BAD_PATH", f"output is not inside out-dir: {name}")
        digest = C.sha256_file(path)
        size = path.stat().st_size
        if item.get("sha256") != digest or item.get("bytes") != size:
            raise C.GamekitError("VALIDATION_FAILED", f"output hash mismatch for {name}")
        seen.add(name)
        verified.append({"file": name, "sha256": digest, "bytes": size})
    return verified


def run_recipe(recipe: str | Path, out_dir: str | Path, timeout: float = 600) -> dict[str, Any]:
    """Validate ``recipe``, run it in pinned Blender, and re-hash the outputs."""
    recipe_path, data = load_recipe(recipe)
    timeout = _check_timeout(timeout)
    out = _prepare_out_dir(out_dir)
    script = C.GAMEKIT_DIR / "blender" / "recipe_runner.py"
    if not script.is_file():
        raise C.GamekitError("TOOL_MISSING", f"recipe runner missing: {script}")
    previous = os.environ.get("PYTHONDONTWRITEBYTECODE")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        run = C.run_blender(
            script,
            ["--recipe", str(recipe_path), "--out", str(out)],
            timeout=timeout,
        )
    finally:
        if previous is None:
            os.environ.pop("PYTHONDONTWRITEBYTECODE", None)
        else:
            os.environ["PYTHONDONTWRITEBYTECODE"] = previous
    if run.timed_out:
        raise C.GamekitError("TIMEOUT", f"blender timed out after {run.seconds:.0f}s", process=run.summary())
    tail = (run.stdout + "\n" + run.stderr)[-2000:]
    if run.result is None or not run.result.get("ok"):
        detail = "blender produced no result" if run.result is None else str(run.result.get("detail") or "blender recipe failed")
        code = "BLENDER_FAILED" if run.result is None else str(run.result.get("error") or "BLENDER_FAILED")
        raise C.GamekitError(code, detail, process=run.summary(), tail=tail)
    if run.exit_code != 0:
        raise C.GamekitError("BLENDER_FAILED", f"blender exited {run.exit_code}", process=run.summary(), tail=tail)
    manifest_path = out / MANIFEST_NAME
    if not manifest_path.is_file():
        raise C.GamekitError("BLENDER_FAILED", "blender reported ok but wrote no manifest", process=run.summary())
    manifest = C.read_json(manifest_path)
    outputs = _verify_manifest(out, manifest, data["name"])
    declared = run.result.get("outputs")
    if isinstance(declared, list) and sorted(declared) != sorted(item["file"] for item in outputs):
        raise C.GamekitError("VALIDATION_FAILED", "runner output list does not match the manifest")
    return {"ok": True, "outputs": outputs, "manifest": manifest, "process": run.summary()}


def _cmd_run(args: argparse.Namespace) -> dict[str, Any]:
    return run_recipe(args.recipe, args.out_dir, timeout=args.timeout)


def _cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    _path, data = load_recipe(args.recipe)
    return {"ok": True, "name": data["name"], "steps": len(data["steps"])}


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("blender", help="run a Blender JSON recipe")
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run", help="validate a recipe, run Blender, rehash outputs")
    run.add_argument("recipe", help="path to a hh-blender-recipe-1 JSON file")
    run.add_argument("--out-dir", required=True, help="directory for GLB, PNG, and manifest.json")
    run.add_argument("--timeout", type=float, default=600, help="seconds before the Blender process is killed")
    run.set_defaults(func=_cmd_run)
    validate = commands.add_parser("validate", help="validate a recipe without launching Blender")
    validate.add_argument("recipe")
    validate.set_defaults(func=_cmd_validate)
