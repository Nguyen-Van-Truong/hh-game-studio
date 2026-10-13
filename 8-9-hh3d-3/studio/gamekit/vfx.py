"""hh vfx: small original particle packed scenes.

``hh vfx presets`` lists sparks, impact, smoke, and burst for 2D and 3D.
``hh vfx create`` builds one standalone packed scene by calling ``scene.apply``.
It does not write ``.tscn`` text itself. Godot 4.7.2 GPUParticles2D and
GPUParticles3D expose ``use_fixed_seed`` and ``seed``; pass ``seed`` when a
repeatable particle sequence is needed. Without it, Godot keeps its normal
non-fixed random sequence.

The packed scene can play alone because its preview camera is enabled (2D) or
current (3D). Godot exposes ``Camera2D.current`` as read-only in this pin, so
the 2D recipe uses the writable ``enabled`` property. After ``instance.add``
into a game, turn that camera off or it replaces the gameplay camera. Quality
worker registers this module from ``hh.py``.
"""

from __future__ import annotations

import argparse
import math
import re
from typing import Any

from . import common as C
from . import scene as S

SCHEMA = "hh-vfx-presets-2"
TEMPLATE_PATH = C.GAMEKIT_DIR / "effects" / "vfx_presets.json"
PRESET_IDS = (
    "sparks_2d", "impact_2d", "smoke_2d", "burst_2d",
    "sparks_3d", "impact_3d", "smoke_3d", "burst_3d",
)
_KIND_NAME = {"sparks": "Sparks", "impact": "Impact", "smoke": "Smoke", "burst": "Burst"}
_COLOR_RE = re.compile(r"^#[0-9a-f]{6}([0-9a-f]{2})?$")
_BASE_KEYS = {
    "id", "description", "dimension", "kind", "one_shot", "amount", "lifetime", "lifetime_min",
    "lifetime_max", "explosiveness", "color", "direction", "spread", "initial_velocity_min",
    "initial_velocity_max", "gravity", "scale_min", "scale_max", "shape",
}


def _fail(detail: str, code: str = "VALIDATION_FAILED") -> None:
    raise C.GamekitError(code, detail)


def _num(value: Any, name: str, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        _fail(f"{name} must be a finite number")
    number = float(value)
    if number < lo or number > hi:
        _fail(f"{name} must be in {lo}..{hi}")
    return number


def _int(value: Any, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{name} must be an integer")
    if value < lo or value > hi:
        _fail(f"{name} must be in {lo}..{hi}")
    return value


def _seed(value: Any, name: str = "seed") -> int:
    """Validate the unsigned 32-bit seed used by both GPUParticles classes."""
    return _int(value, name, 0, 0xFFFFFFFF)


def _vec(value: Any, name: str, size: int, lo: float, hi: float) -> list[float]:
    if not isinstance(value, list) or len(value) != size:
        _fail(f"{name} must be {size} numbers")
    return [_num(item, f"{name}[{i}]", lo, hi) for i, item in enumerate(value)]


def _color(value: Any, name: str = "color") -> str:
    if not isinstance(value, str):
        _fail(f"{name} must be #RRGGBB or #RRGGBBAA")
    color = value.lower()
    if not _COLOR_RE.match(color):
        _fail(f"{name} must be #RRGGBB or #RRGGBBAA")
    return color


def _rgba(color: str) -> list[float]:
    hex_digits = color[1:]
    if len(hex_digits) == 6:
        hex_digits += "ff"
    return [round(int(hex_digits[i : i + 2], 16) / 255.0, 6) for i in range(0, 8, 2)]


def _table() -> dict[str, Any]:
    data = C.read_json(TEMPLATE_PATH)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        _fail("vfx preset template is malformed")
    if data.get("seed_supported") is not True or not isinstance(data.get("seed_reason"), str):
        _fail("vfx template must say seed is supported")
    for key in ("renderer", "standalone", "integrate", "retrigger", "camera_limits", "limits", "presets"):
        if key not in data:
            _fail(f"vfx template is missing {key}")
    retrigger = data["retrigger"]
    if not isinstance(retrigger, dict) or retrigger.get("method") != "restart" or not retrigger.get("steps"):
        _fail("vfx retrigger must call restart(true) when preserving a fixed seed")
    camera = data["camera_limits"]
    if not isinstance(camera, dict) or "2d" not in camera or "3d" not in camera:
        _fail("vfx camera limits are missing")
    limits = data["limits"]
    if not isinstance(limits, dict):
        _fail("vfx limits are missing")
    count = limits.get("count")
    intensity = limits.get("intensity")
    life = limits.get("lifetime_seconds")
    seed = limits.get("seed")
    if not isinstance(count, dict) or not isinstance(intensity, dict) or not isinstance(life, dict) or not isinstance(seed, dict):
        _fail("vfx count, intensity, lifetime, or seed limits are missing")
    if count.get("property") != "amount" or intensity.get("property") != "explosiveness":
        _fail("vfx count maps to amount and intensity maps to explosiveness")
    count_min = _int(count.get("min"), "count min", 8, 8)
    count_max = _int(count.get("max"), "count max", 96, 96)
    intensity_min = _num(intensity.get("min"), "intensity min", 0.0, 0.0)
    intensity_max = _num(intensity.get("max"), "intensity max", 1.0, 1.0)
    life_min = _num(life.get("min"), "lifetime min", 0.15, 0.15)
    life_max = _num(life.get("max"), "lifetime max", 2.5, 2.5)
    if seed.get("property") != "seed":
        _fail("vfx seed maps to the GPUParticles seed property")
    _seed(seed.get("min"), "seed min")
    _seed(seed.get("max"), "seed max")
    if seed["min"] != 0 or seed["max"] != 0xFFFFFFFF:
        _fail("vfx seed limits must cover unsigned 32-bit values")
    texture_px = _int(limits.get("texture_px"), "texture_px", 32, 32)
    if texture_px not in (16, 32, 64):
        _fail("texture_px must be 16, 32, or 64")
    quad_max = _num(limits.get("quad_meters_max"), "quad_meters_max", 0.5, 0.5)
    travel_px = _num(limits.get("travel_px_max"), "travel_px_max", 90, 90)
    travel_m = _num(limits.get("travel_m_max"), "travel_m_max", 3.5, 3.5)
    rows = data["presets"]
    if not isinstance(rows, list) or [row.get("id") if isinstance(row, dict) else None for row in rows] != list(PRESET_IDS):
        _fail("vfx presets must list sparks, impact, smoke, and burst for 2D and 3D")
    for row in rows:
        _check_preset_row(row, count_min, count_max, intensity_min, intensity_max, life_min, life_max, quad_max, travel_px, travel_m)
    return data


def _check_preset_row(
    row: Any,
    count_min: int,
    count_max: int,
    intensity_min: float,
    intensity_max: float,
    life_min: float,
    life_max: float,
    quad_max: float,
    travel_px: float,
    travel_m: float,
) -> None:
    if not isinstance(row, dict):
        _fail("vfx preset record is malformed")
    preset_id = row.get("id")
    dimension = row.get("dimension")
    kind = row.get("kind")
    shape = row.get("shape")
    if dimension not in ("2d", "3d") or kind not in _KIND_NAME or shape not in ("point", "sphere", "box"):
        _fail(f"{preset_id}: dimension, kind, or shape is invalid")
    if preset_id != f"{kind}_{dimension}":
        _fail(f"{preset_id}: id must be {kind}_{dimension}")
    text = str(row.get("description", "")).lower()
    if "synthetic" not in text or "not a downloaded asset" not in text:
        _fail(f"{preset_id}: description must say synthetic and not a downloaded asset")
    if not isinstance(row.get("one_shot"), bool):
        _fail(f"{preset_id}: one_shot must be a boolean")
    amount = _int(row.get("amount"), f"{preset_id} amount", count_min, count_max)
    del amount
    lifetime = _num(row.get("lifetime"), f"{preset_id} lifetime", life_min, life_max)
    lo = _num(row.get("lifetime_min"), f"{preset_id} lifetime_min", life_min, life_max)
    hi = _num(row.get("lifetime_max"), f"{preset_id} lifetime_max", life_min, life_max)
    if not lo <= lifetime <= hi:
        _fail(f"{preset_id}: lifetime is outside its own range")
    _num(row.get("explosiveness"), f"{preset_id} explosiveness", intensity_min, intensity_max)
    _color(row.get("color"), f"{preset_id} color")
    _vec(row.get("direction"), f"{preset_id} direction", 3, -1.0, 1.0)
    _num(row.get("spread"), f"{preset_id} spread", 0.0, 180.0)
    vmin = _num(row.get("initial_velocity_min"), f"{preset_id} velocity", 0.0, 220.0 if dimension == "2d" else 8.0)
    vmax = _num(row.get("initial_velocity_max"), f"{preset_id} velocity", 0.0, 220.0 if dimension == "2d" else 8.0)
    if vmin > vmax:
        _fail(f"{preset_id}: velocity min is above max")
    budget = travel_px if dimension == "2d" else travel_m
    if vmax * hi > budget:
        _fail(f"{preset_id}: velocity times lifetime leaves the default visibility area")
    _vec(row.get("gravity"), f"{preset_id} gravity", 3, -400.0 if dimension == "2d" else -12.0, 400.0 if dimension == "2d" else 12.0)
    smin = _num(row.get("scale_min"), f"{preset_id} scale", 0.05, 2.5)
    smax = _num(row.get("scale_max"), f"{preset_id} scale", 0.05, 2.5)
    if smin > smax:
        _fail(f"{preset_id}: scale min is above max")
    allowed = set(_BASE_KEYS)
    if shape == "sphere":
        allowed.add("emission_sphere_radius")
        cap = 32.0 if dimension == "2d" else 1.0
        floor = 1.0 if dimension == "2d" else 0.01
        _num(row.get("emission_sphere_radius"), f"{preset_id} radius", floor, cap)
    elif shape == "box":
        allowed.add("emission_box_extents")
        cap = 32.0 if dimension == "2d" else 1.0
        floor = 1.0 if dimension == "2d" else 0.01
        _vec(row.get("emission_box_extents"), f"{preset_id} extents", 3, floor, cap)
    if dimension == "3d":
        allowed.add("quad_size")
        _vec(row.get("quad_size"), f"{preset_id} quad", 2, 0.02, quad_max)
    if set(row) != allowed:
        _fail(f"{preset_id}: unexpected or missing fields {sorted(set(row) ^ allowed)}")


def _preset(preset_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(preset_id, str):
        _fail("preset must be a string")
    table = _table()
    for row in table["presets"]:
        if row["id"] == preset_id:
            return table, row
    _fail(f"unknown vfx preset {preset_id!r}", "BAD_REQUEST")
    raise AssertionError("unreachable")


def _texture(color: str, size: int) -> dict[str, Any]:
    rgba = _rgba(color)
    return {
        "$type": "GradientTexture2D",
        "props": {
            "width": size,
            "height": size,
            "fill": "Radial",
            "fill_from": [0.5, 0.5],
            "fill_to": [1.0, 0.5],
            "gradient": {
                "$type": "Gradient",
                "props": {"offsets": [0.0, 1.0], "colors": [rgba, [rgba[0], rgba[1], rgba[2], 0.0]]},
            },
        },
    }


def _quad(color: str, size: list[float]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if _rgba(color)[3] < 0.999:
        props["transparency"] = "Alpha"
    props["shading_mode"] = "Unshaded"
    props["billboard_mode"] = "Particle Billboard"
    props["albedo_color"] = color
    return {
        "$type": "QuadMesh",
        "props": {"size": size, "material": {"$type": "StandardMaterial3D", "props": props}},
    }


def _material(row: dict[str, Any], color: str) -> dict[str, Any]:
    props: dict[str, Any] = {}
    shape = row["shape"]
    if shape == "point":
        props["emission_shape"] = "Point"
    elif shape == "sphere":
        props["emission_shape"] = "Sphere"
        props["emission_sphere_radius"] = float(row["emission_sphere_radius"])
    else:
        props["emission_shape"] = "Box"
        props["emission_box_extents"] = [float(v) for v in row["emission_box_extents"]]
    props.update({
        "direction": [float(v) for v in row["direction"]],
        "spread": float(row["spread"]),
        "initial_velocity_min": float(row["initial_velocity_min"]),
        "initial_velocity_max": float(row["initial_velocity_max"]),
        "gravity": [float(v) for v in row["gravity"]],
        "scale_min": float(row["scale_min"]),
        "scale_max": float(row["scale_max"]),
        "color": color,
    })
    return {"$type": "ParticleProcessMaterial", "props": props}


def _bounds(row: dict[str, Any], table: dict[str, Any], count: int | None, intensity: float | None,
            color: str | None, lifetime: float | None) -> tuple[int, float, str, float]:
    limits = table["limits"]
    used_count = row["amount"] if count is None else count
    used_count = _int(used_count, "count", limits["count"]["min"], limits["count"]["max"])
    used_intensity = row["explosiveness"] if intensity is None else intensity
    used_intensity = _num(used_intensity, "intensity", limits["intensity"]["min"], limits["intensity"]["max"])
    used_color = row["color"] if color is None else color
    used_color = _color(used_color)
    used_life = row["lifetime"] if lifetime is None else lifetime
    used_life = _num(used_life, "lifetime", float(row["lifetime_min"]), float(row["lifetime_max"]))
    return used_count, used_intensity, used_color, used_life


def plan(
    preset: str,
    *,
    count: int | None = None,
    intensity: float | None = None,
    color: str | None = None,
    lifetime: float | None = None,
    seed: int | None = None,
    scene: str | None = None,
) -> dict[str, Any]:
    """Build scene-apply ops for one preset. Does not launch Godot or write a scene."""
    table, row = _preset(preset)
    used_seed = None if seed is None else _seed(seed)
    used_count, used_intensity, used_color, used_life = _bounds(row, table, count, intensity, color, lifetime)
    dimension = row["dimension"]
    particle_name = _KIND_NAME[row["kind"]]
    root_name = particle_name + ("2D" if dimension == "2d" else "3D")
    particle_type = "GPUParticles2D" if dimension == "2d" else "GPUParticles3D"
    root_type = "Node2D" if dimension == "2d" else "Node3D"
    props: dict[str, Any] = {
        "emitting": True,
        "one_shot": row["one_shot"],
        "amount": used_count,
        "lifetime": used_life,
        "explosiveness": used_intensity,
        "process_material": _material(row, used_color),
    }
    if used_seed is not None:
        # Godot only promises reproducibility when the fixed-seed switch and
        # the seed are both set. Keep the normal random behavior when omitted.
        props["use_fixed_seed"] = True
        props["seed"] = used_seed
    if dimension == "2d":
        props["position"] = [0, 0]
        props["texture"] = _texture(used_color, int(table["limits"]["texture_px"]))
        camera = {
            "op": "node.create", "parent": ".", "name": "PreviewCamera", "type": "Camera2D",
            "props": {"enabled": True, "position": [0, 0], "zoom": [1, 1]},
        }
    else:
        props["position"] = [0, 0, 0]
        props["draw_pass_1"] = _quad(used_color, [float(v) for v in row["quad_size"]])
        camera = {
            "op": "node.create", "parent": ".", "name": "PreviewCamera", "type": "Camera3D",
            "props": {"current": True, "fov": 60.0, "position": [0.0, 0.55, 2.5], "rotation_degrees": [12, 0, 0]},
        }
    scene_path = scene or f"res://effects/{row['id']}.tscn"
    ops = [
        camera,
        {"op": "node.create", "parent": ".", "name": particle_name, "type": particle_type, "props": props},
        {"op": "group.add", "path": particle_name, "group": "hh_vfx"},
        {"op": "group.add", "path": particle_name, "group": f"hh_vfx_{row['kind']}"},
        {"op": "group.add", "path": "PreviewCamera", "group": "hh_vfx_preview_camera"},
    ]
    return {
        "preset": row["id"],
        "description": row["description"],
        "dimension": dimension,
        "kind": row["kind"],
        "particle_node": particle_name,
        "particle_type": particle_type,
        "count": used_count,
        "intensity": used_intensity,
        "color": used_color,
        "lifetime": used_life,
        "one_shot": row["one_shot"],
        "seed_supported": True,
        "seed": used_seed,
        "use_fixed_seed": used_seed is not None,
        "create": {"root_type": root_type, "root_name": root_name, "props": {}},
        "ops": ops,
        "retrigger": table["retrigger"],
        "camera_limits": table["camera_limits"],
        "integrate": table["integrate"],
        "renderer": table["renderer"],
        "instantiate": {"op": "instance.add", "parent": ".", "scene": scene_path, "name": root_name},
    }


def _check_scene(project: C.Project, scene: str) -> str:
    if not isinstance(scene, str) or not scene.endswith(".tscn"):
        raise C.GamekitError("BAD_PATH", "vfx scene must be a res:// path ending in .tscn")
    project.res_to_path(scene)
    return scene


def create(
    project: C.Project,
    scene: str,
    preset: str,
    command_id: str,
    *,
    count: int | None = None,
    intensity: float | None = None,
    color: str | None = None,
    lifetime: float | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Create one packed scene. Validation failures return before ``scene.apply``."""
    command_id = C.validate_command_id(command_id)
    _check_scene(project, scene)
    built = plan(
        preset, count=count, intensity=intensity, color=color, lifetime=lifetime, seed=seed, scene=scene,
    )
    catalog = S.load_catalog()
    if built["create"]["root_type"] not in catalog["classes"]:
        _fail("root type is not in the scene catalog")
    S.validate_ops(project, built["ops"], catalog)
    receipt = S.apply(project, scene, built["ops"], command_id, create=built["create"])
    if not isinstance(receipt, dict):
        raise C.GamekitError("GODOT_FAILED", "scene apply returned no receipt")
    out = dict(receipt)
    out["vfx"] = {
        "preset": built["preset"],
        "description": built["description"],
        "dimension": built["dimension"],
        "kind": built["kind"],
        "particle_node": built["particle_node"],
        "particle_type": built["particle_type"],
        "count": built["count"],
        "intensity": built["intensity"],
        "color": built["color"],
        "lifetime": built["lifetime"],
        "one_shot": built["one_shot"],
        "seed_supported": True,
        "seed": built["seed"],
        "use_fixed_seed": built["use_fixed_seed"],
        "retrigger": built["retrigger"],
        "camera_limits": built["camera_limits"],
        "integrate": built["integrate"],
        "renderer": built["renderer"],
        "instantiate": built["instantiate"],
        "create_semantics": (
            "Creates a new packed scene through scene.apply. The same command_id and request replay "
            "the journaled receipt. A new command_id against an existing scene conflicts instead of merging."
        ),
    }
    return out


def presets() -> dict[str, Any]:
    table = _table()
    listed = []
    for row in table["presets"]:
        built = plan(row["id"])
        listed.append({
            "id": row["id"],
            "description": row["description"],
            "dimension": row["dimension"],
            "kind": row["kind"],
            "one_shot": row["one_shot"],
            "count": built["count"],
            "intensity": built["intensity"],
            "color": built["color"],
            "lifetime": built["lifetime"],
            "lifetime_min": row["lifetime_min"],
            "lifetime_max": row["lifetime_max"],
            "particle_node": built["particle_node"],
            "particle_type": built["particle_type"],
            "suggested_scene": built["instantiate"]["scene"],
        })
    return {
        "ok": True,
        "kind": "vfx.presets",
        "schema": SCHEMA,
        "seed_supported": True,
        "seed_reason": table["seed_reason"],
        "seed_limits": table["limits"]["seed"],
        "renderer": table["renderer"],
        "standalone": table["standalone"],
        "integrate": table["integrate"],
        "retrigger": table["retrigger"],
        "camera_limits": table["camera_limits"],
        "limits": table["limits"],
        "presets": listed,
    }


def _cmd_presets(_a: argparse.Namespace) -> dict[str, Any]:
    return presets()


def _cmd_create(a: argparse.Namespace) -> dict[str, Any]:
    return create(
        C.get_project(a.project),
        a.scene,
        a.preset,
        a.command_id,
        count=a.count,
        intensity=a.intensity,
        color=a.color,
        lifetime=a.lifetime,
        seed=a.seed,
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("vfx", help="list or create original particle packed scenes")
    commands = parser.add_subparsers(dest="action", required=True)
    listed = commands.add_parser("presets", help="list 2D and 3D particle presets, retrigger, and camera limits")
    listed.set_defaults(func=_cmd_presets)
    make = commands.add_parser("create", help="create one standalone particle packed scene via scene apply")
    make.add_argument("--project", required=True)
    make.add_argument("--scene", required=True, help="res:// path of the new packed scene")
    make.add_argument("--preset", required=True)
    make.add_argument("--command-id", required=True)
    make.add_argument("--count", type=int, default=None, help="particle amount, 8..96")
    make.add_argument("--intensity", type=float, default=None, help="explosiveness, 0..1")
    make.add_argument("--color", default=None, help="#RRGGBB or #RRGGBBAA")
    make.add_argument("--lifetime", type=float, default=None, help="seconds, inside that preset's range")
    make.add_argument("--seed", type=int, default=None, help="unsigned 32-bit fixed particle seed")
    make.set_defaults(func=_cmd_create)
