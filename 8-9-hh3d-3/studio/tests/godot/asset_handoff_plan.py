"""Authority-zero asset handoff plan for the O2 2D/3D fixture pair.

This document is intentionally static.  It binds the Blender export/sprite
render intent, geometry/material/UV profile labels and Godot readback
requirements to content-addressed artifacts without reading files or calling
Blender/Godot.  A row with ``asset_import_verified=False`` is a requirement,
not proof of import.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

STUDIO = Path(__file__).resolve().parents[2]
SCHEMA = "hh-o2-asset-handoff-plan-1"
DETACHED_MODE = "DETACHED_PLAN_ONLY"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_PATH = re.compile(r"assets/[a-z][a-z0-9._-]{0,63}\.(?:glb|png|json)\Z")
_FIXTURES = {"room_3d", "arena_2d"}


def _copy(value: Any) -> Any:
    import json
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sha(value: Any) -> str:
    import json
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _expect(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _asset(*, asset_id: str, fixture: str, path: str, fmt: str,
           manifest_path: str, steps: list[str], profiles: Mapping[str, str]) -> dict[str, Any]:
    return {
        "asset_id": asset_id, "fixture": fixture, "source": "Blender",
        "path": path, "format": fmt, "manifest_path": manifest_path,
        "sha256": "0" * 64, "manifest_sha256": "1" * 64,
        "pipeline_steps": list(steps), "pipeline_profiles": dict(profiles),
        "import_readback_required": True, "asset_import_verified": False,
        "native_observed": False,
    }


def build_plan() -> dict[str, Any]:
    """Build the deterministic 2D/3D asset handoff candidate."""
    assets = [
        _asset(asset_id="avatar_blender", fixture="room_3d",
               path="assets/avatar.glb", fmt="GLB",
               manifest_path="assets/manifest.json",
               steps=["geometry", "material", "uv", "export_glb", "godot_import_readback"],
               profiles={"geometry": "hh-blender-geometry-1",
                         "material": "hh-blender-material-pbr-1",
                         "uv": "hh-blender-uv-1",
                         "axis": "hh-blender-axis-zup-gltf-yup-1"}),
        _asset(asset_id="arena_sprite_atlas", fixture="arena_2d",
               path="assets/arena_sprite_atlas.png", fmt="PNG",
               manifest_path="assets/arena_sprite_atlas.json",
               steps=["pose_render", "sprite_sheet", "godot_texture_readback"],
               profiles={"render": "hh-blender-sprite-sheet-1",
                         "axis": "hh-blender-axis-zup-gltf-yup-1"}),
    ]
    body = {"authority": 0, "runtime_authorized": False,
            "native_observed": False, "execution": DETACHED_MODE,
            "schema": SCHEMA, "state_kind": "PLANNED_NOT_NATIVE",
            "fixtures": sorted(_FIXTURES), "assets": assets,
            "validation_scope": "STATIC_ASSET_HANDOFF_ONLY; Blender export and Godot import/readback remain pending"}
    body["canonical_sha256"] = _sha(body)
    return _copy(body)


def _validate_asset(row: object) -> None:
    fields = {"asset_id", "fixture", "source", "path", "format", "manifest_path",
              "sha256", "manifest_sha256", "pipeline_steps", "pipeline_profiles",
              "import_readback_required", "asset_import_verified", "native_observed"}
    _expect(type(row) is dict and set(row) == fields, "ASSET_ROW_SHAPE")
    row = row  # type: ignore[assignment]
    _expect(type(row["asset_id"]) is str and re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", row["asset_id"]), "ASSET_ID")
    _expect(row["fixture"] in _FIXTURES and row["source"] == "Blender", "ASSET_FIXTURE")
    _expect(row["format"] in ("GLB", "PNG") and _PATH.fullmatch(row["path"])
            and _PATH.fullmatch(row["manifest_path"]), "ASSET_PATH")
    _expect(_HEX.fullmatch(row["sha256"]) and _HEX.fullmatch(row["manifest_sha256"]), "ASSET_HASH")
    _expect(type(row["pipeline_steps"]) is list and row["pipeline_steps"] and
            all(type(step) is str and re.fullmatch(r"[a-z][a-z0-9_]{1,63}", step) for step in row["pipeline_steps"]), "ASSET_STEPS")
    _expect(type(row["pipeline_profiles"]) is dict and row["pipeline_profiles"], "ASSET_PROFILES")
    _expect(all(type(key) is str and type(value) is str and re.fullmatch(r"hh-[a-z0-9-]+", value)
                for key, value in row["pipeline_profiles"].items()), "ASSET_PROFILE_ID")
    _expect(type(row["import_readback_required"]) is bool and row["import_readback_required"] is True
            and row["asset_import_verified"] is False and row["native_observed"] is False,
            "ASSET_AUTHORITY")
    if row["format"] == "GLB":
        _expect(row["path"].endswith(".glb") and
                row["pipeline_steps"] == ["geometry", "material", "uv", "export_glb", "godot_import_readback"],
                "GLB_PIPELINE")
        _expect(set(row["pipeline_profiles"]) == {"geometry", "material", "uv", "axis"}, "GLB_PROFILE_KEYS")
    else:
        _expect(row["path"].endswith(".png") and
                row["pipeline_steps"] == ["pose_render", "sprite_sheet", "godot_texture_readback"],
                "SPRITE_PIPELINE")
        _expect(set(row["pipeline_profiles"]) == {"render", "axis"}, "SPRITE_PROFILE_KEYS")


def validate_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a static handoff and fail closed on claims or tampering."""
    _expect(type(value) is dict, "PLAN_TYPE")
    allowed = {"authority", "runtime_authorized", "native_observed", "execution",
               "schema", "state_kind", "fixtures", "assets", "validation_scope", "canonical_sha256"}
    _expect(set(value) == allowed, "PLAN_UNKNOWN_FIELD")
    _expect(value["authority"] == 0 and value["runtime_authorized"] is False
            and value["native_observed"] is False and value["execution"] == DETACHED_MODE
            and value["schema"] == SCHEMA and value["state_kind"] == "PLANNED_NOT_NATIVE"
            and value["fixtures"] == sorted(_FIXTURES), "PLAN_AUTHORITY")
    _expect(value["validation_scope"] == "STATIC_ASSET_HANDOFF_ONLY; Blender export and Godot import/readback remain pending", "PLAN_SCOPE")
    _expect(type(value["assets"]) is list and len(value["assets"]) == 2, "PLAN_ASSETS")
    ids = set()
    for row in value["assets"]:
        _validate_asset(row)
        _expect(row["asset_id"] not in ids, "ASSET_DUPLICATE")
        ids.add(row["asset_id"])
    _expect(ids == {"avatar_blender", "arena_sprite_atlas"}, "PLAN_ASSET_SET")
    expected = {key: value[key] for key in value if key != "canonical_sha256"}
    _expect(value["canonical_sha256"] == _sha(expected), "PLAN_HASH")
    return _copy(value)


def source_paths() -> tuple[str, ...]:
    return ("tests/godot/asset_handoff_plan.py", "tests/asset-profile.json",
            "blender-addon/export_profile.py", "blender-addon/material_profile.py",
            "host/blender/glb_preflight.py", "pipeline/glb_semantics.py")


if __name__ == "__main__":
    import json
    print(json.dumps(build_plan(), sort_keys=True, separators=(",", ":")))


