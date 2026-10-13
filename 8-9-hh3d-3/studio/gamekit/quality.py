"""hh quality: conservative Godot 4.7 renderer profiles.

``quality profiles`` lists the managed ProjectSettings. ``quality inspect`` reads them
from a fresh Godot process. ``quality apply`` validates, checkpoints ``project.godot``,
asks ``settings_tool.gd`` to serialize the profile into a temp file, and merges only the
managed keys. A failed readback restores the checkpoint byte for byte. The same
``command_id`` and payload replays; a different payload conflicts. ``--dry-run`` does
not take the command id and does not write.

Profiles do not make a game look better and do not turn on costly effects. Property
names and engine defaults are the Godot 4.7 ProjectSettings class reference. The pin
is Godot 4.7.2-stable.
"""

from __future__ import annotations

import argparse
import secrets
from pathlib import Path
from typing import Any, Sequence

from . import common as C
from . import project_config as PC

# Godot 4.7 ProjectSettings. Do not add a key that is not in that class reference.
MANAGED_KEYS: tuple[str, ...] = (
    "rendering/renderer/rendering_method",
    "rendering/renderer/rendering_method.mobile",
    "rendering/anti_aliasing/quality/msaa_2d",
    "rendering/anti_aliasing/quality/msaa_3d",
    "rendering/anti_aliasing/quality/screen_space_aa",
    "rendering/anti_aliasing/quality/use_taa",
    "rendering/lights_and_shadows/directional_shadow/size",
    "rendering/lights_and_shadows/directional_shadow/size.mobile",
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality",
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile",
    "rendering/lights_and_shadows/positional_shadow/atlas_size",
    "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile",
    "rendering/2d/shadow_atlas/size",
)

# Defaults published for Godot 4.7. Non-string values that equal these may be
# omitted by save_custom; inspect still reports the live value.
ENGINE_DEFAULTS: dict[str, Any] = {
    "rendering/renderer/rendering_method": "forward_plus",
    "rendering/renderer/rendering_method.mobile": "mobile",
    "rendering/anti_aliasing/quality/msaa_2d": 0,
    "rendering/anti_aliasing/quality/msaa_3d": 0,
    "rendering/anti_aliasing/quality/screen_space_aa": 0,
    "rendering/anti_aliasing/quality/use_taa": False,
    "rendering/lights_and_shadows/directional_shadow/size": 4096,
    "rendering/lights_and_shadows/directional_shadow/size.mobile": 2048,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality": 2,
    "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile": 0,
    "rendering/lights_and_shadows/positional_shadow/atlas_size": 4096,
    "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile": 2048,
    "rendering/2d/shadow_atlas/size": 2048,
}

# Real 4.7 settings this command deliberately does not write.
NOT_MANAGED: tuple[str, ...] = (
    "rendering/renderer/rendering_method.web",
    "rendering/anti_aliasing/quality/use_debanding",
    "rendering/scaling_3d/mode",
    "rendering/scaling_3d/scale",
    "rendering/environment/ssao/quality",
    "rendering/environment/glow/upscale_mode",
    "rendering/environment/volumetric_fog/volume_size",
    "rendering/lights_and_shadows/positional_shadow/soft_shadow_filter_quality",
    "rendering/lights_and_shadows/positional_shadow/soft_shadow_filter_quality.mobile",
    "rendering/textures/vram_compression/import_etc2_astc",
    "rendering/textures/vram_compression/import_s3tc_bptc",
)

WEB_KEY = "rendering/renderer/rendering_method.web"
_RENDERERS = {"forward_plus", "mobile", "gl_compatibility"}
_SHADOW_SIZES = {256, 512, 1024, 2048, 4096, 8192}

BEAUTY_NOTE = (
    "Switching renderer or these settings does not make a game look better. "
    "Art, lighting, materials, and resolution are unchanged."
)
COSTLY_NOTE = (
    "This profile does not enable TAA, MSAA, FXAA, SMAA, debanding, 3D resolution scaling, "
    "SSAO, glow, or volumetric fog."
)
STORAGE_NOTE = (
    "Renderer method strings are stored explicitly. Other managed values that equal the "
    "Godot 4.7 default may be omitted from project.godot; inspect still reports the live value."
)
_SHARED_LIMITATIONS = (
    BEAUTY_NOTE,
    COSTLY_NOTE,
    "config/features is not rewritten. An editor session may refresh that list later.",
    "rendering/renderer/rendering_method.web is not managed.",
    "These ProjectSettings apply on the next launch. They do not restyle scenes, materials, or assets.",
    "The running renderer can still differ if the engine falls back or the process uses --rendering-method.",
    STORAGE_NOTE,
)


def _settings(
    renderer: str,
    mobile: str,
    *,
    directional: int,
    directional_mobile: int,
    soft: int,
    soft_mobile: int,
    atlas: int,
    atlas_mobile: int,
    shadow_2d: int,
) -> dict[str, Any]:
    raw = {
        "rendering/renderer/rendering_method": renderer,
        "rendering/renderer/rendering_method.mobile": mobile,
        "rendering/anti_aliasing/quality/msaa_2d": 0,
        "rendering/anti_aliasing/quality/msaa_3d": 0,
        "rendering/anti_aliasing/quality/screen_space_aa": 0,
        "rendering/anti_aliasing/quality/use_taa": False,
        "rendering/lights_and_shadows/directional_shadow/size": directional,
        "rendering/lights_and_shadows/directional_shadow/size.mobile": directional_mobile,
        "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality": soft,
        "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile": soft_mobile,
        "rendering/lights_and_shadows/positional_shadow/atlas_size": atlas,
        "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile": atlas_mobile,
        "rendering/2d/shadow_atlas/size": shadow_2d,
    }
    missing = [key for key in MANAGED_KEYS if key not in raw]
    extra = [key for key in raw if key not in MANAGED_KEYS]
    if missing or extra or tuple(raw) != MANAGED_KEYS:
        raise RuntimeError(f"quality profile key drift missing={missing} extra={extra}")
    return {key: raw[key] for key in MANAGED_KEYS}


def _profile(
    name: str,
    renderer: str,
    mobile: str,
    settings: dict[str, Any],
    *,
    intent: str,
    capabilities: tuple[str, ...],
    costs: tuple[str, ...],
    limitations: tuple[str, ...],
    aa: str,
    shadows: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "renderer": renderer,
        "mobile_renderer": mobile,
        "intent": intent,
        "settings": settings,
        "capabilities": capabilities,
        "costs": costs,
        "limitations": _SHARED_LIMITATIONS + limitations,
        "headroom": {"aa": aa, "shadows": shadows},
    }


PROFILES: dict[str, dict[str, Any]] = {
    "compatibility": _profile(
        "compatibility",
        "gl_compatibility",
        "gl_compatibility",
        _settings(
            "gl_compatibility",
            "gl_compatibility",
            directional=1024,
            directional_mobile=1024,
            soft=0,
            soft_mobile=0,
            atlas=1024,
            atlas_mobile=1024,
            shadow_2d=1024,
        ),
        intent="Broad 2D and low-end devices, including older GPUs. Compatibility on desktop and mobile.",
        capabilities=(
            "Compatibility renderer for broad 2D and older or low-end hardware.",
            "OpenGL 3.3 / OpenGL ES 3.0 / WebGL 2 class feature set, with a low per-mesh light cap.",
        ),
        costs=(
            "Lowest base overhead of the three profiles.",
            "3D lighting is calculated in nonlinear sRGB, so it is less accurate than Mobile or Forward+.",
            "Directional and positional shadow maps are 1024, with hard filtering, on both the base setting and the mobile override.",
        ),
        limitations=(
            "Both the base renderer and the mobile override are gl_compatibility.",
            "MSAA 2D, screen-space AA, and TAA are not supported by Compatibility. MSAA 3D is supported but left disabled.",
        ),
        aa="msaa_2d, msaa_3d, and screen_space_aa are 0. use_taa is false. Compatibility cannot do MSAA 2D, FXAA, SMAA, or TAA. MSAA 3D headroom exists (1 = 2x, 2 = 4x, 3 = 8x) and is not turned on.",
        shadows="Directional and positional shadow maps, including their .mobile overrides, are 1024. The 2D shadow atlas is 1024. Soft filtering is 0 (Hard) on both the base setting and the mobile override. 2048, 4096, and 8192, and soft steps 1 through 5, are headroom and are not enabled.",
    ),
    "mobile": _profile(
        "mobile",
        "mobile",
        "mobile",
        _settings(
            "mobile",
            "mobile",
            directional=2048,
            directional_mobile=2048,
            soft=0,
            soft_mobile=0,
            atlas=2048,
            atlas_mobile=2048,
            shadow_2d=2048,
        ),
        intent="Simple 3D. The Mobile renderer is used for the base project and for the mobile override.",
        capabilities=(
            "Mobile renderer for simple 3D, with lower base overhead than Forward+.",
            "The renderer supports MSAA 2D, MSAA 3D, FXAA, and SMAA. This profile leaves all of them off.",
        ),
        costs=(
            "Does not scale to large scenes the way Forward+ does.",
            "Directional and positional shadow maps are 2048. Soft filtering is hard (0), including the mobile overrides.",
        ),
        limitations=(
            "Both the base renderer and the mobile override are mobile.",
            "TAA is not supported by the Mobile renderer and is left false.",
        ),
        aa="msaa_2d, msaa_3d, and screen_space_aa are 0. use_taa is false. Mobile can use MSAA (1 = 2x, 2 = 4x, 3 = 8x), FXAA (screen_space_aa 1), and SMAA (screen_space_aa 2). None of those are enabled. TAA is unsupported.",
        shadows="Directional and positional maps, including .mobile overrides, are 2048. The 2D shadow atlas stays at the engine default 2048. Soft filtering is 0 (Hard), matching Godot's mobile filter default rather than the desktop default of 2 (Soft Low).",
    ),
    "desktop": _profile(
        "desktop",
        "forward_plus",
        "mobile",
        _settings(
            "forward_plus",
            "mobile",
            directional=4096,
            directional_mobile=2048,
            soft=2,
            soft_mobile=0,
            atlas=4096,
            atlas_mobile=2048,
            shadow_2d=2048,
        ),
        intent="Forward+ for a desktop PC. The mobile export override stays on the Mobile renderer.",
        capabilities=(
            "Forward+ for desktop. Higher base overhead, and it scales to more complex 3D than Mobile.",
            "Forward+ supports MSAA, FXAA, SMAA, and TAA. This profile leaves all of them off.",
        ),
        costs=(
            "Highest base overhead of the three profiles.",
            "PC shadow maps stay at the engine default 4096 with Soft Low filtering (2). Mobile overrides stay at 2048 and Hard (0).",
        ),
        limitations=(
            "The base renderer is forward_plus. The mobile override is mobile, matching Godot's Forward+ project default. Android and iOS are not switched to Forward+.",
            "TAA, MSAA, FXAA, and SMAA stay off. Soft High and Soft Ultra stay off.",
        ),
        aa="msaa_2d, msaa_3d, and screen_space_aa are 0. use_taa is false. Forward+ headroom is MSAA 2x/4x/8x, FXAA, SMAA, and TAA. None of it is enabled.",
        shadows="Base directional and positional maps stay at the engine default 4096. Their .mobile overrides stay at 2048. Directional soft filtering stays at 2 (Soft Low) on PC and 0 (Hard) on the mobile override. 8192 maps and soft steps above 2 are not enabled. The 2D shadow atlas stays at 2048.",
    ),
}


def _assert_catalog() -> None:
    if tuple(ENGINE_DEFAULTS) != MANAGED_KEYS:
        raise RuntimeError("quality engine defaults do not match the managed keys")
    if set(NOT_MANAGED) & set(MANAGED_KEYS):
        raise RuntimeError("quality not_managed overlaps managed keys")
    for name, spec in PROFILES.items():
        settings = spec["settings"]
        if tuple(settings) != MANAGED_KEYS:
            raise RuntimeError(f"profile {name} does not own the managed key set")
        if spec["renderer"] not in _RENDERERS or spec["mobile_renderer"] not in _RENDERERS:
            raise RuntimeError(f"profile {name} has an unknown renderer")
        if settings["rendering/renderer/rendering_method"] != spec["renderer"]:
            raise RuntimeError(f"profile {name} renderer drift")
        if settings["rendering/renderer/rendering_method.mobile"] != spec["mobile_renderer"]:
            raise RuntimeError(f"profile {name} mobile override drift")
        for key in ("rendering/anti_aliasing/quality/msaa_2d", "rendering/anti_aliasing/quality/msaa_3d"):
            if settings[key] != 0:
                raise RuntimeError(f"profile {name} enables MSAA")
        if settings["rendering/anti_aliasing/quality/screen_space_aa"] != 0:
            raise RuntimeError(f"profile {name} enables screen-space AA")
        if settings["rendering/anti_aliasing/quality/use_taa"] is not False:
            raise RuntimeError(f"profile {name} enables TAA")
        for key, value in settings.items():
            sample = ENGINE_DEFAULTS[key]
            if type(value) is not type(sample):
                raise RuntimeError(f"profile {name} type drift on {key}")
        for key in (
            "rendering/lights_and_shadows/directional_shadow/size",
            "rendering/lights_and_shadows/directional_shadow/size.mobile",
            "rendering/lights_and_shadows/positional_shadow/atlas_size",
            "rendering/lights_and_shadows/positional_shadow/atlas_size.mobile",
            "rendering/2d/shadow_atlas/size",
        ):
            if settings[key] not in _SHADOW_SIZES or settings[key] > 4096:
                raise RuntimeError(f"profile {name} shadow size {key} is not conservative")
        for key in (
            "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality",
            "rendering/lights_and_shadows/directional_shadow/soft_shadow_filter_quality.mobile",
        ):
            if settings[key] not in range(6) or settings[key] > 2:
                raise RuntimeError(f"profile {name} soft shadow {key} is not conservative")
        if spec["limitations"][0] != BEAUTY_NOTE:
            raise RuntimeError(f"profile {name} is missing the beauty limitation")


_assert_catalog()


def _copy_settings(settings: dict[str, Any]) -> dict[str, Any]:
    return {key: settings[key] for key in MANAGED_KEYS}


def _public_profile(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": spec["name"],
        "renderer": spec["renderer"],
        "mobile_renderer": spec["mobile_renderer"],
        "intent": spec["intent"],
        "settings": _copy_settings(spec["settings"]),
        "capabilities": list(spec["capabilities"]),
        "costs": list(spec["costs"]),
        "limitations": list(spec["limitations"]),
        "headroom": {"aa": spec["headroom"]["aa"], "shadows": spec["headroom"]["shadows"]},
        "beauty_guarantee": False,
        "costly_effects_enabled": False,
    }


def _require_profile(name: str) -> dict[str, Any]:
    if not isinstance(name, str) or name not in PROFILES:
        known = ", ".join(PROFILES)
        raise C.GamekitError("VALIDATION_FAILED", f"unknown quality profile {name!r}; known: {known}")
    return PROFILES[name]


def list_profiles() -> dict[str, Any]:
    """Return the stable profile catalog. Does not read or write a project."""
    return {
        "ok": True,
        "kind": "quality.profiles",
        "pin": {"godot": C.GODOT_VERSION, "blender": C.BLENDER_VERSION},
        "managed_keys": list(MANAGED_KEYS),
        "engine_defaults": _copy_settings(ENGINE_DEFAULTS),
        "not_managed": list(NOT_MANAGED),
        "profiles": [_public_profile(spec) for spec in PROFILES.values()],
        "beauty_guarantee": False,
        "storage_note": STORAGE_NOTE,
        "note": BEAUTY_NOTE,
    }


def _parse_string(key: str, raw: Any) -> str:
    if not isinstance(raw, str):
        raise C.GamekitError("READBACK_MISMATCH", f"{key} read back {raw!r}")
    text = raw.strip()
    if not text or len(text) > 64 or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in text):
        raise C.GamekitError("READBACK_MISMATCH", f"{key} read back {raw!r}")
    return text


def _parse_bool(key: str, raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip() in ("true", "false"):
        return raw.strip() == "true"
    raise C.GamekitError("READBACK_MISMATCH", f"{key} read back {raw!r}")


def _parse_int(key: str, raw: Any) -> int:
    if isinstance(raw, bool):
        raise C.GamekitError("READBACK_MISMATCH", f"{key} read back {raw!r}")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdecimal():
        return int(raw.strip())
    raise C.GamekitError("READBACK_MISMATCH", f"{key} read back {raw!r}")


def _parse(key: str, raw: Any) -> Any:
    if key == WEB_KEY or isinstance(ENGINE_DEFAULTS.get(key), str):
        return _parse_string(key, raw)
    sample = ENGINE_DEFAULTS[key]
    if isinstance(sample, bool):
        return _parse_bool(key, raw)
    if isinstance(sample, int):
        return _parse_int(key, raw)
    raise C.GamekitError("READBACK_MISMATCH", f"{key} has no parser")


def _match_profile(parsed: dict[str, Any]) -> str | None:
    for name, spec in PROFILES.items():
        if all(parsed[key] == spec["settings"][key] for key in MANAGED_KEYS):
            return name
    return None


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if not value.isascii() or any(ch in value for ch in '"\\\n\r'):
            raise C.GamekitError("VALIDATION_FAILED", f"unsupported setting string {value!r}")
        return f'"{value}"'
    raise C.GamekitError("VALIDATION_FAILED", "profile values must be bool, int, or string")


def _assigned(entry_text: str) -> str:
    lines = entry_text.splitlines()
    if not lines or "=" not in lines[0]:
        return ""
    return lines[0].split("=", 1)[1].strip()


def _require_persisted(generated: bytes, settings: dict[str, Any]) -> None:
    """Non-default values, and every renderer string, must be in Godot's temp file.

    ``save_custom`` may omit a bool or int that equals the engine default. Missing
    owned keys are then removals. A missing non-default would silently drop the profile.
    """
    _lines, entries, _ends = PC._document(generated)
    problems = []
    for key, value in settings.items():
        entry = entries.get(key)
        optional = not isinstance(value, str) and value == ENGINE_DEFAULTS[key]
        if entry is None:
            if not optional:
                problems.append(f"{key} missing from Godot project output")
            continue
        if _assigned(entry.text) != _literal(value):
            problems.append(f"{key} serialized as {entry.text.strip()!r}")
    if problems:
        raise C.GamekitError("GODOT_FAILED", "; ".join(problems[:6]), problems=problems[:40])


def _tool(project: C.Project, request: dict[str, Any], timeout: float, *, readback: bool) -> dict[str, Any]:
    run = C.run_godot_tool(project.root, "settings_tool.gd", request, headless=True, timeout=timeout)
    what = "quality readback" if readback else "quality apply"
    if run.errors:
        code = "READBACK_MISMATCH" if readback else "GODOT_FAILED"
        detail = "readback process reported errors" if readback else "settings tool reported errors"
        raise C.GamekitError(code, detail, process=run.summary())
    result = C.require_result(run, what)
    result["process"] = run.summary()
    return result


def _read_settings(project: C.Project, keys: Sequence[str], timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    result = _tool(
        project,
        {"mode": "readback", "setting_keys": list(keys), "scripts": [], "scenes": []},
        timeout,
        readback=True,
    )
    raw = result.get("settings")
    if not isinstance(raw, dict):
        raise C.GamekitError("READBACK_MISMATCH", "settings readback is not an object")
    parsed: dict[str, Any] = {}
    problems: list[str] = []
    for key in keys:
        if key not in raw:
            problems.append(f"{key} missing from readback")
            continue
        try:
            parsed[key] = _parse(key, raw[key])
        except C.GamekitError as exc:
            problems.append(exc.detail)
    if problems:
        raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:8]), problems=problems[:40])
    process = result.get("process")
    return parsed, process if isinstance(process, dict) else {}


def _compare(expected: dict[str, Any], raw: Any) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(raw, dict):
        return {}, ["settings readback is not an object"]
    parsed: dict[str, Any] = {}
    problems: list[str] = []
    for key, want in expected.items():
        if key not in raw:
            problems.append(f"{key} missing from readback")
            continue
        try:
            got = _parse(key, raw[key])
        except C.GamekitError as exc:
            problems.append(exc.detail)
            continue
        parsed[key] = got
        if got != want:
            problems.append(f"{key} is {raw[key]!r}, expected {want!r}")
    return parsed, problems


def _project_file(project: C.Project) -> Path:
    path = project.root / "project.godot"
    if not path.is_file():
        raise C.GamekitError("NOT_FOUND", "project.godot is missing")
    return path


def _discard(path: Path) -> None:
    for candidate in (path, Path(str(path) + ".uid")):
        if candidate.is_file():
            candidate.unlink()


def _file_settings(data: bytes) -> dict[str, Any]:
    """Effective managed values of a project.godot image.

    A missing key is the Godot 4.7 default. This is the preimage used for
    ``changed_keys``; the committed values still come from the fresh readback.
    """
    _lines, entries, _ends = PC._document(data)
    parsed: dict[str, Any] = {}
    for key in MANAGED_KEYS:
        entry = entries.get(key)
        if entry is None:
            parsed[key] = ENGINE_DEFAULTS[key]
            continue
        assigned = _assigned(entry.text)
        sample = ENGINE_DEFAULTS[key]
        if isinstance(sample, str):
            if len(assigned) < 2 or assigned[0] != '"' or assigned[-1] != '"':
                raise C.GamekitError("GODOT_FAILED", f"{key} in project.godot is {assigned!r}")
            parsed[key] = _parse_string(key, assigned[1:-1])
        elif isinstance(sample, bool):
            parsed[key] = _parse_bool(key, assigned)
        else:
            parsed[key] = _parse_int(key, assigned)
    return parsed


def inspect_quality(project: C.Project, timeout: float = 120.0) -> dict[str, Any]:
    """Read managed settings from a fresh process. Does not write the project."""
    _project_file(project)
    keys = list(MANAGED_KEYS) + [WEB_KEY]
    with C.project_lock(project, "quality.inspect", wait_seconds=30):
        parsed, process = _read_settings(project, keys, timeout)
    managed = {key: parsed[key] for key in MANAGED_KEYS}
    matched = _match_profile(managed)
    if matched is None:
        capabilities: list[str] = []
        costs: list[str] = []
        limitations = [
            BEAUTY_NOTE,
            "Current managed settings are not the compatibility, mobile, or desktop profile.",
            STORAGE_NOTE,
        ]
        headroom = None
    else:
        spec = PROFILES[matched]
        capabilities = list(spec["capabilities"])
        costs = list(spec["costs"])
        limitations = list(spec["limitations"])
        headroom = {"aa": spec["headroom"]["aa"], "shadows": spec["headroom"]["shadows"]}
    return {
        "ok": True,
        "kind": "quality.inspect",
        "project": project.project_id,
        "renderer": managed["rendering/renderer/rendering_method"],
        "mobile_renderer": managed["rendering/renderer/rendering_method.mobile"],
        "web_renderer": parsed[WEB_KEY],
        "settings": managed,
        "matched_profile": matched,
        "known_profiles": list(PROFILES),
        "capabilities": capabilities,
        "costs": costs,
        "limitations": limitations,
        "headroom": headroom,
        "beauty_guarantee": False,
        "storage_note": STORAGE_NOTE,
        "readback": "FRESH_PROCESS_MATCH",
        "process": process,
        "at": C.now_iso(),
    }


def _dry_run(
    project: C.Project,
    spec: dict[str, Any],
    settings: dict[str, Any],
    command_id: str,
    timeout: float,
) -> dict[str, Any]:
    _project_file(project)
    with C.project_lock(project, "quality.dry_run", wait_seconds=30):
        current, process = _read_settings(project, MANAGED_KEYS, timeout)
    changed = [key for key in MANAGED_KEYS if current[key] != settings[key]]
    body = _public_profile(spec)
    body.update({
        "ok": True,
        "status": "DRY_RUN",
        "kind": "quality.apply",
        "dry_run": True,
        "profile": spec["name"],
        "command_id": command_id,
        "project": project.project_id,
        "settings": _copy_settings(settings),
        "current_settings": current,
        "current_renderer": current["rendering/renderer/rendering_method"],
        "current_mobile_renderer": current["rendering/renderer/rendering_method.mobile"],
        "changed_keys": changed,
        "current_readback": "FRESH_PROCESS_MATCH",
        "process": process,
        "at": C.now_iso(),
    })
    return body


def _commit(
    project: C.Project,
    spec: dict[str, Any],
    settings: dict[str, Any],
    command_id: str,
    *,
    allow_open_editor: bool,
    timeout: float,
) -> dict[str, Any]:
    request_digest = C.digest({"kind": "quality.apply", "profile": spec["name"], "settings": settings})
    journal = C.Journal(project)
    godot_file = _project_file(project)
    temp_res = f"res://hh_quality_tmp_{secrets.token_hex(4)}.godot"
    temp = project.res_to_path(temp_res)
    owned = set(MANAGED_KEYS)
    try:
        with C.project_lock(project, "quality.apply", wait_seconds=30):
            prior = journal.replay_or_conflict(command_id, request_digest)
            if prior is not None:
                return prior
            C.refuse_if_editor_open(project, allow_open_editor)
            original = godot_file.read_bytes()
            before_sha = C.sha256_bytes(original)
            C.checkpoint(project, command_id, [godot_file])
            try:
                before_effective = _file_settings(original)
                request = {
                    "mode": "apply",
                    "temp_out": temp_res,
                    "settings": settings,
                    "autoloads_set": {},
                    "autoloads_clear": [],
                    "settings_clear": [],
                }
                applied = _tool(project, request, timeout, readback=False)
                if godot_file.read_bytes() != original:
                    raise C.GamekitError("GODOT_FAILED", "settings tool modified project.godot directly")
                if not temp.is_file():
                    raise C.GamekitError("GODOT_FAILED", "quality apply reported ok but wrote no project file")
                generated = temp.read_bytes()
                _require_persisted(generated, settings)
                merged = PC.merge_project_godot(original, generated, drop_keys=owned)
                if b"config_version=" not in merged:
                    raise C.GamekitError("GODOT_FAILED", "saved project file has no config_version")
                C.atomic_write_bytes(godot_file, merged)
                _discard(temp)
                readback = _tool(
                    project,
                    {"mode": "readback", "setting_keys": list(MANAGED_KEYS), "scripts": [], "scenes": []},
                    timeout,
                    readback=True,
                )
                PC.require_preserved(original, godot_file.read_bytes(), owned)
                confirmed, problems = _compare(settings, readback.get("settings"))
                if problems:
                    raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:6]), problems=problems[:40])
            except Exception:
                C.restore_checkpoint(project, command_id)
                raise
            receipt = _public_profile(spec)
            receipt.update({
                "ok": True,
                "status": "COMMITTED",
                "kind": "quality.apply",
                "dry_run": False,
                "profile": spec["name"],
                "command_id": command_id,
                "project": project.project_id,
                "settings": confirmed,
                "changed_keys": [key for key in MANAGED_KEYS if before_effective[key] != confirmed[key]],
                "changed_keys_basis": "project.godot before this command; a missing managed key counts as the Godot 4.7 default",
                "before_sha256": before_sha,
                "after_sha256": C.sha256_file(godot_file),
                "readback": "FRESH_PROCESS_MATCH",
                "storage_note": STORAGE_NOTE,
                "apply_process": applied.get("process"),
                "readback_process": readback.get("process"),
                "at": C.now_iso(),
            })
            journal.append(command_id, request_digest, receipt)
            return receipt
    finally:
        _discard(temp)


def apply_profile(
    project: C.Project,
    profile: str,
    command_id: str,
    *,
    dry_run: bool = False,
    allow_open_editor: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Apply one profile, or preview it when ``dry_run`` is true.

    Dry-run reads the current managed settings and writes nothing. It does not
    consume ``command_id``. A real apply journals only after a fresh readback
    matches the profile. Failure restores the original ``project.godot`` bytes.
    """
    command_id = C.validate_command_id(command_id)
    if not isinstance(dry_run, bool) or not isinstance(allow_open_editor, bool):
        raise C.GamekitError("BAD_REQUEST", "dry_run and allow_open_editor must be booleans")
    spec = _require_profile(profile)
    settings = _copy_settings(spec["settings"])
    if dry_run:
        return _dry_run(project, spec, settings, command_id, timeout)
    return _commit(
        project,
        spec,
        settings,
        command_id,
        allow_open_editor=allow_open_editor,
        timeout=timeout,
    )


def _cmd_profiles(_args: argparse.Namespace) -> dict[str, Any]:
    return list_profiles()


def _cmd_inspect(args: argparse.Namespace) -> dict[str, Any]:
    return inspect_quality(C.get_project(args.project))


def _cmd_apply(args: argparse.Namespace) -> dict[str, Any]:
    return apply_profile(
        C.get_project(args.project),
        args.profile,
        args.command_id,
        dry_run=bool(args.dry_run),
        allow_open_editor=bool(args.allow_open_editor),
    )


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("quality", help="list, inspect, and apply conservative renderer profiles")
    commands = parser.add_subparsers(dest="action", required=True)
    listing = commands.add_parser("profiles", help="list compatibility, mobile, and desktop profiles")
    listing.set_defaults(func=_cmd_profiles)
    inspect = commands.add_parser("inspect", help="read the current renderer and managed settings")
    inspect.add_argument("--project", required=True)
    inspect.set_defaults(func=_cmd_inspect)
    apply = commands.add_parser("apply", help="write one profile into project.godot")
    apply.add_argument("--project", required=True)
    apply.add_argument("--profile", required=True, choices=tuple(PROFILES))
    apply.add_argument("--command-id", required=True)
    apply.add_argument("--dry-run", action="store_true", help="report the change and do not write")
    apply.add_argument("--allow-open-editor", action="store_true")
    apply.set_defaults(func=_cmd_apply)
