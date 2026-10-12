"""hh kit: install self-written gameplay kits into a registered Godot project.

``kit add`` validates the manifest on the host, refuses to overwrite a different file unless
``--replace``, checkpoints ``project.godot`` and every file it will write, then asks Godot to
compile autoload scripts and ``ProjectSettings.save_custom`` a temp project file. The host
merges only the kit's owned keys into ``project.godot`` atomically and acknowledges only after a
fresh process reads the autoloads back, unrelated source stays unchanged and ``scene`` check is
clean. A failed readback restores the checkpoint.

``kit remove`` deletes the kit files and clears its autoloads. If the game has changed a kit
file since install, remove raises CONFLICT and writes nothing unless ``--force``.
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
from pathlib import Path
from typing import Any

from . import common as C
from . import project_config as PC

KITS_DIR = C.GAMEKIT_DIR / "kits"
KIT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,31}$")
AUTOLOAD_RE = re.compile(r"^[A-Z_][A-Za-z0-9_]{0,40}$")
_MANIFEST_KEYS = {"name", "version", "files", "autoloads", "requires"}
_FILE_EXTS = {".gd", ".tscn", ".tres", ".cfg", ".json", ".txt"}

AUDIO_KIT = "audio"
AUDIO_LAYOUT_RES = "res://default_bus_layout.tres"
AUDIO_SETTING = "audio/buses/default_bus_layout"
AUDIO_BUSES: list[dict[str, str]] = [
    {"name": "Master", "send": ""},
    {"name": "Music", "send": "Master"},
    {"name": "SFX", "send": "Master"},
]


def license_line(name: str) -> str:
    return f"# HH gamekit kit {name} v1 - self-made (HH Studio)"


def dest_res(kit_name: str, rel: str) -> str:
    return f"res://addons/hh_kits/{kit_name}/{rel}"


def _star(path: str) -> str:
    return path if path.startswith("*") else "*" + path


def audio_layout_ok(text: str) -> bool:
    """True when a saved AudioBusLayout text has Music and SFX sending to Master."""
    return (
        'type="AudioBusLayout"' in text
        and "bus/1/name" in text
        and '"Music"' in text
        and "bus/2/name" in text
        and '"SFX"' in text
        and '"Master"' in text
    )


def _safe_rel(rel: str) -> bool:
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or "\\" in rel:
        return False
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return False
    suffix = Path(rel).suffix.lower()
    return suffix in _FILE_EXTS


# ---------------------------------------------------------------- manifests


def validate_manifest(data: Any, directory: Path, *, folder_name: str | None = None) -> dict[str, Any]:
    """Validate a kit.json object against the files in ``directory``. No Godot."""
    if not isinstance(data, dict):
        raise C.GamekitError("VALIDATION_FAILED", "kit.json must be an object")
    extra = set(data) - _MANIFEST_KEYS
    if extra:
        raise C.GamekitError("VALIDATION_FAILED", f"kit.json has unknown fields {sorted(extra)}")
    missing = _MANIFEST_KEYS - set(data)
    if missing:
        raise C.GamekitError("VALIDATION_FAILED", f"kit.json missing {sorted(missing)}")
    name = data["name"]
    if not isinstance(name, str) or not KIT_NAME_RE.match(name):
        raise C.GamekitError("VALIDATION_FAILED", f"kit name must match {KIT_NAME_RE.pattern}")
    if folder_name is not None and name != folder_name:
        raise C.GamekitError("VALIDATION_FAILED", f"kit name {name!r} does not match folder {folder_name!r}")
    version = data["version"]
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise C.GamekitError("VALIDATION_FAILED", "kit version must be a short token")
    files = data["files"]
    if not isinstance(files, list) or any(not isinstance(rel, str) for rel in files):
        raise C.GamekitError("VALIDATION_FAILED", "files must be a list of relative paths")
    if len(files) != len(set(files)):
        raise C.GamekitError("VALIDATION_FAILED", "files contains duplicates")
    for rel in files:
        if not _safe_rel(rel):
            raise C.GamekitError("VALIDATION_FAILED", f"unsafe kit file {rel!r}")
        src = directory / rel
        if not src.is_file() or src.is_symlink():
            raise C.GamekitError("VALIDATION_FAILED", f"kit file missing: {rel}")
        if rel.endswith(".gd"):
            text = src.read_text(encoding="utf-8")
            prefix = license_line(name)
            if not text.startswith(prefix) or (len(text) > len(prefix) and text[len(prefix)] not in "\r\n"):
                raise C.GamekitError("VALIDATION_FAILED", f"{rel} must start with {prefix!r}")
        elif rel.endswith(".tscn"):
            body = src.read_text(encoding="utf-8")
            if not body.startswith("[gd_scene"):
                raise C.GamekitError("VALIDATION_FAILED", f"{rel} must be a Godot text scene")
            folder = f"res://addons/hh_kits/{name}/"
            if folder not in body:
                raise C.GamekitError("VALIDATION_FAILED", f"{rel} does not reference {folder}")
            for line in body.splitlines():
                if "path=" in line and ".gd" in line and folder not in line:
                    raise C.GamekitError("VALIDATION_FAILED", f"{rel} script path is outside the kit")
    autoloads = data["autoloads"]
    if not isinstance(autoloads, dict):
        raise C.GamekitError("VALIDATION_FAILED", "autoloads must be an object")
    normalized: dict[str, str] = {}
    for autoload_name, path in autoloads.items():
        if not isinstance(autoload_name, str) or not AUTOLOAD_RE.match(autoload_name):
            raise C.GamekitError("VALIDATION_FAILED", f"bad autoload name {autoload_name!r}")
        if not isinstance(path, str) or path.startswith("*"):
            raise C.GamekitError("VALIDATION_FAILED", f"autoload {autoload_name} path must be a res:// string")
        prefix = f"res://addons/hh_kits/{name}/"
        if not path.startswith(prefix) or not path.endswith(".gd") or ".." in path:
            raise C.GamekitError("VALIDATION_FAILED", f"autoload {autoload_name} must live under {prefix}")
        rel = path[len(prefix):]
        if rel not in files:
            raise C.GamekitError("VALIDATION_FAILED", f"autoload {autoload_name} file {rel} is not in files")
        normalized[autoload_name] = path
    requires = data["requires"]
    if not isinstance(requires, list) or any(not isinstance(req, str) for req in requires):
        raise C.GamekitError("VALIDATION_FAILED", "requires must be a list of kit names")
    if len(requires) != len(set(requires)):
        raise C.GamekitError("VALIDATION_FAILED", "requires contains duplicates")
    for req in requires:
        if not KIT_NAME_RE.match(req):
            raise C.GamekitError("VALIDATION_FAILED", f"bad required kit name {req!r}")
        if req == name:
            raise C.GamekitError("VALIDATION_FAILED", "a kit cannot require itself")
    from . import asset as asset_mod
    asset_mod.check_license("self-made", "HH Studio")
    return {
        "name": name,
        "version": version,
        "files": list(files),
        "autoloads": normalized,
        "requires": list(requires),
        "license": "self-made",
    }


def load_kit(name: str) -> dict[str, Any]:
    if not isinstance(name, str) or not KIT_NAME_RE.match(name):
        raise C.GamekitError("BAD_REQUEST", f"invalid kit name {name!r}")
    folder = KITS_DIR / name
    path = folder / "kit.json"
    if not path.is_file():
        raise C.GamekitError("NOT_FOUND", f"unknown kit {name!r}")
    return validate_manifest(C.read_json(path), folder, folder_name=name)


def list_kits() -> list[dict[str, Any]]:
    if not KITS_DIR.is_dir():
        return []
    names = sorted(p.name for p in KITS_DIR.iterdir() if (p / "kit.json").is_file())
    return [load_kit(name) for name in names]


def kit_installed(project: C.Project, name: str) -> bool:
    kit = load_kit(name)
    if name == AUDIO_KIT:
        path = project.res_to_path(AUDIO_LAYOUT_RES)
        if not path.is_file():
            return False
        return audio_layout_ok(path.read_text(encoding="utf-8", errors="replace"))
    if not kit["files"]:
        return False
    return all(project.res_to_path(dest_res(name, rel)).is_file() for rel in kit["files"])


def unmet_requires(project: C.Project, kit: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for req in kit["requires"]:
        try:
            present = kit_installed(project, req)
        except C.GamekitError:
            present = False
        if not present:
            missing.append(req)
    return missing


# ---------------------------------------------------------------- file plan (no Godot)


def plan_add(project: C.Project, kit: dict[str, Any], *, replace: bool) -> dict[str, Any]:
    """Plan copies into res://addons/hh_kits/<kit>/. Raises CONFLICT on a different existing file."""
    files: list[dict[str, Any]] = []
    for rel in kit["files"]:
        src = KITS_DIR / kit["name"] / rel
        res = dest_res(kit["name"], rel)
        dest = project.res_to_path(res)
        if dest.exists() and not dest.is_file():
            raise C.GamekitError("BAD_PATH", f"{res} exists and is not a file")
        existed = dest.is_file()
        same = existed and dest.read_bytes() == src.read_bytes()
        if existed and not same and not replace:
            raise C.GamekitError(
                "CONFLICT",
                f"{res} already exists with different content; pass --replace",
                res=res,
            )
        files.append({
            "rel": rel,
            "res": res,
            "src": src,
            "dest": dest,
            "existed": existed,
            "same": same,
            "write": not same,
        })
    autoloads = {name: _star(path) for name, path in kit["autoloads"].items()}
    settings: dict[str, str] = {}
    buses: list[dict[str, str]] | None = None
    audio_dest: Path | None = None
    audio_write = False
    if kit["name"] == AUDIO_KIT:
        audio_dest = project.res_to_path(AUDIO_LAYOUT_RES)
        if audio_dest.exists() and not audio_dest.is_file():
            raise C.GamekitError("BAD_PATH", f"{AUDIO_LAYOUT_RES} exists and is not a file")
        if audio_dest.is_file():
            current = audio_dest.read_text(encoding="utf-8", errors="replace")
            if audio_layout_ok(current):
                audio_write = False
            elif not replace:
                raise C.GamekitError(
                    "CONFLICT",
                    f"{AUDIO_LAYOUT_RES} already exists and is not the kit bus layout; pass --replace",
                    res=AUDIO_LAYOUT_RES,
                )
            else:
                audio_write = True
        else:
            audio_write = True
        settings[AUDIO_SETTING] = AUDIO_LAYOUT_RES
        buses = list(AUDIO_BUSES)
    return {
        "kit": kit["name"],
        "version": kit["version"],
        "files": files,
        "autoloads": autoloads,
        "settings": settings,
        "buses": buses,
        "audio_dest": audio_dest,
        "audio_write": audio_write,
        "touch_project": bool(autoloads or settings),
    }


def plan_remove(project: C.Project, kit: dict[str, Any]) -> dict[str, Any]:
    """Plan deletions. ``modified`` lists installed files that no longer match the kit."""
    files: list[dict[str, Any]] = []
    modified: list[str] = []
    for rel in kit["files"]:
        res = dest_res(kit["name"], rel)
        dest = project.res_to_path(res)
        existed = dest.is_file()
        changed = False
        if existed and dest.read_bytes() != (KITS_DIR / kit["name"] / rel).read_bytes():
            changed = True
            modified.append(res)
        files.append({"rel": rel, "res": res, "dest": dest, "existed": existed, "modified": changed})
    audio_dest: Path | None = None
    if kit["name"] == AUDIO_KIT:
        audio_dest = project.res_to_path(AUDIO_LAYOUT_RES)
        existed = audio_dest.is_file()
        changed = False
        text = audio_dest.read_text(encoding="utf-8", errors="replace") if existed else ""
        # Extra buses or effects are game work even when Music and SFX are still present.
        if existed and (not audio_layout_ok(text) or "bus/3/" in text or "/effect/" in text):
            changed = True
            modified.append(AUDIO_LAYOUT_RES)
        files.append({
            "rel": None,
            "res": AUDIO_LAYOUT_RES,
            "dest": audio_dest,
            "existed": existed,
            "modified": changed,
        })
    return {
        "kit": kit["name"],
        "files": files,
        "modified": modified,
        "autoloads_clear": list(kit["autoloads"]),
        "audio_dest": audio_dest,
        "touch_project": bool(kit["autoloads"]) or kit["name"] == AUDIO_KIT,
    }


def add_request_digest(kit_name: str, replace: bool) -> str:
    kit = load_kit(kit_name)
    files = {rel: C.sha256_file(KITS_DIR / kit_name / rel) for rel in kit["files"]}
    payload: dict[str, Any] = {
        "kind": "kit.add",
        "kit": kit_name,
        "version": kit["version"],
        "replace": bool(replace),
        "files": files,
        "autoloads": kit["autoloads"],
        "requires": kit["requires"],
    }
    if kit_name == AUDIO_KIT:
        payload["audio"] = {"layout": AUDIO_LAYOUT_RES, "buses": AUDIO_BUSES, "setting": AUDIO_SETTING}
    return C.digest(payload)


def remove_request_digest(kit_name: str, force: bool = False) -> str:
    kit = load_kit(kit_name)
    return C.digest({
        "kind": "kit.remove",
        "kit": kit_name,
        "version": kit["version"],
        "force": bool(force),
        "files": [dest_res(kit_name, rel) for rel in kit["files"]],
        "autoloads": sorted(kit["autoloads"]),
        "audio": kit_name == AUDIO_KIT,
    })


# ---------------------------------------------------------------- Godot apply / readback


def _temp_res(kind: str, suffix: str) -> str:
    return f"res://hhgk_{kind}_{secrets.token_hex(4)}{suffix}"


def _cleanup(paths: list[Path]) -> None:
    for path in paths:
        if path.is_file():
            path.unlink()
        uid = path.with_name(path.name + ".uid")
        if uid.is_file():
            uid.unlink()


def _apply_settings_tool(project: C.Project, request: dict[str, Any], timeout: float) -> dict[str, Any]:
    run = C.run_godot_tool(project.root, "settings_tool.gd", request, headless=True, timeout=timeout)
    if run.errors:
        raise C.GamekitError("GODOT_FAILED", "settings tool reported errors", process=run.summary())
    result = C.require_result(run, "kit settings")
    result["process"] = run.summary()
    return result


def _readback(project: C.Project, request: dict[str, Any], timeout: float) -> dict[str, Any]:
    run = C.run_godot_tool(project.root, "settings_tool.gd", request, headless=True, timeout=timeout)
    if run.errors:
        raise C.GamekitError(
            "READBACK_MISMATCH",
            "readback process reported errors",
            process=run.summary(),
        )
    result = C.require_result(run, "kit readback")
    result["process"] = run.summary()
    return result


def _scene_clean(project: C.Project, timeout: float) -> dict[str, Any]:
    run = C.run_godot_tool(project.root, "scene_tool.gd", {"mode": "check"}, headless=True, timeout=timeout)
    result = C.require_result(run, "kit scene check")
    clean = bool(result.get("clean")) and not run.errors
    if not clean:
        raise C.GamekitError(
            "READBACK_MISMATCH",
            "scene check is not clean",
            problems=result.get("problems", [])[:20],
            errors=run.errors[:20],
        )
    return {"clean": True, "files_checked": result.get("files_checked"), "process": run.summary()}


def _prune_empty(start: Path, stop: Path) -> None:
    current = start
    stop_norm = os.path.normcase(os.path.abspath(str(stop)))
    while os.path.normcase(os.path.abspath(str(current))) != stop_norm:
        if not current.is_dir():
            break
        try:
            current.rmdir()
        except OSError:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent


def _expect_autoloads(got: dict[str, Any], expected: dict[str, str]) -> list[str]:
    problems = []
    for name, path in expected.items():
        have = str(got.get(name, ""))
        if _star(have) != _star(path):
            problems.append(f"autoload {name} is {have!r}, expected {path!r}")
    return problems


def _expect_absent(got: dict[str, Any], names: list[str]) -> list[str]:
    return [f"autoload {name} is still {got.get(name)!r}" for name in names if name in got and str(got.get(name))]


def _expect_compiles(rows: list[dict[str, Any]]) -> list[str]:
    return [f"{row.get('path')} does not compile" for row in rows if not row.get("compiles")]


def _expect_buses(got: list[dict[str, Any]]) -> list[str]:
    if len(got) != len(AUDIO_BUSES):
        return [f"bus count is {len(got)}, expected {len(AUDIO_BUSES)}"]
    problems = []
    for have, want in zip(got, AUDIO_BUSES):
        if have.get("name") != want["name"]:
            problems.append(f"bus {want['name']} missing (got {have.get('name')!r})")
        elif want["name"] != "Master" and have.get("send") != want["send"]:
            problems.append(f"bus {want['name']} sends to {have.get('send')!r}")
    return problems


def _project_drop_keys(plan: dict[str, Any], *, removing: bool = False) -> set[str]:
    """Keys owned by a kit transaction when merging Godot's project output.

    ``ProjectSettings.save_custom`` can omit unrelated sections (notably custom
    display/i18n/physics settings).  The host therefore overlays the generated
    file onto the pre-command source and only lets the kit's explicit autoload
    and setting keys change.
    """
    keys = {f"autoload/{name}" for name in (plan.get("autoloads") or {})}
    keys.update(f"autoload/{name}" for name in (plan.get("autoloads_clear") or []))
    keys.update(str(key) for key in (plan.get("settings") or {}))
    if removing and plan.get("kit") == AUDIO_KIT:
        # The audio layout file is deleted below, so its project pointer must
        # be owned by the remove transaction as well.
        keys.add(AUDIO_SETTING)
    return keys


# ---------------------------------------------------------------- commands


def add_kit(
    project: C.Project,
    kit_name: str,
    command_id: str,
    *,
    replace: bool = False,
    allow_open_editor: bool = False,
    timeout: float = 180.0,
) -> dict[str, Any]:
    C.validate_command_id(command_id)
    load_kit(kit_name)
    journal = C.Journal(project)
    with C.project_lock(project, "kit.add", wait_seconds=30):
        kit = load_kit(kit_name)
        request_digest = add_request_digest(kit_name, replace)
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        C.refuse_if_editor_open(project, allow_open_editor)
        missing = unmet_requires(project, kit)
        if missing:
            raise C.GamekitError("VALIDATION_FAILED", "missing required kits: " + ", ".join(missing), missing=missing)
        plan = plan_add(project, kit, replace=replace)
        return _commit_add(project, kit, plan, command_id, request_digest, journal, replace, timeout)


def _commit_add(
    project: C.Project,
    kit: dict[str, Any],
    plan: dict[str, Any],
    command_id: str,
    request_digest: str,
    journal: C.Journal,
    replace: bool,
    timeout: float,
) -> dict[str, Any]:
    paths: list[Path] = []
    if plan["touch_project"]:
        paths.append(project.root / "project.godot")
    for item in plan["files"]:
        if item["write"]:
            paths.append(item["dest"])
    if plan["audio_write"] and plan["audio_dest"] is not None:
        paths.append(plan["audio_dest"])
    # Unique, stable order.
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    temps: list[Path] = []
    checkpointed = False
    original_project_bytes = (project.root / "project.godot").read_bytes()
    try:
        C.checkpoint(project, command_id, unique)
        checkpointed = True
        for item in plan["files"]:
            if item["write"]:
                C.atomic_write_bytes(item["dest"], item["src"].read_bytes())
        settings_res = ""
        bus_res = ""
        if plan["touch_project"] or plan["audio_write"]:
            settings_res = _temp_res("settings", ".godot")
            request: dict[str, Any] = {
                "mode": "apply",
                "temp_out": settings_res,
                "autoloads_set": plan["autoloads"],
                "autoloads_clear": [],
                "settings": plan["settings"],
            }
            temps.append(project.res_to_path(settings_res))
            if plan["audio_write"]:
                bus_res = _temp_res("buses", ".tres")
                request["buses"] = plan["buses"]
                request["bus_temp_out"] = bus_res
                temps.append(project.res_to_path(bus_res))
            try:
                _apply_settings_tool(project, request, timeout)
            except C.GamekitError:
                raise
            settings_path = project.res_to_path(settings_res)
            if not settings_path.is_file():
                raise C.GamekitError("GODOT_FAILED", "settings tool wrote no project file")
            if (project.root / "project.godot").read_bytes() != original_project_bytes:
                raise C.GamekitError("GODOT_FAILED", "settings tool modified project.godot directly")
            project_bytes = PC.merge_project_godot(
                original_project_bytes,
                settings_path.read_bytes(),
                drop_keys=_project_drop_keys(plan),
            )
            if b"config_version=" not in project_bytes:
                raise C.GamekitError("GODOT_FAILED", "saved project file has no config_version")
            if plan["audio_write"]:
                bus_path = project.res_to_path(bus_res)
                if not bus_path.is_file():
                    raise C.GamekitError("GODOT_FAILED", "settings tool wrote no bus layout")
                bus_bytes = bus_path.read_bytes()
                if b"AudioBusLayout" not in bus_bytes:
                    raise C.GamekitError("GODOT_FAILED", "bus layout is not an AudioBusLayout")
                C.atomic_write_bytes(plan["audio_dest"], bus_bytes)
            C.atomic_write_bytes(project.root / "project.godot", project_bytes)
        _cleanup(temps)
        temps.clear()
        read_request: dict[str, Any] = {
            "mode": "readback",
            "scripts": [item["res"] for item in plan["files"] if str(item["res"]).endswith(".gd")],
            "scenes": [item["res"] for item in plan["files"] if str(item["res"]).endswith(".tscn")],
            "setting_keys": list(plan["settings"]),
        }
        readback = _readback(project, read_request, timeout)
        problems = _expect_autoloads(readback.get("autoloads", {}), plan["autoloads"])
        problems += _expect_compiles(readback.get("scripts", []))
        problems += _expect_compiles(readback.get("scenes", []))
        if plan["audio_write"] or kit["name"] == AUDIO_KIT:
            problems += _expect_buses(readback.get("buses", []))
            got_setting = str(readback.get("settings", {}).get(AUDIO_SETTING, ""))
            if got_setting != AUDIO_LAYOUT_RES:
                problems.append(f"{AUDIO_SETTING} is {got_setting!r}")
        if problems:
            raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:8]), problems=problems[:40])
        _scene_clean(project, timeout)
        PC.require_preserved(original_project_bytes, (project.root / "project.godot").read_bytes(), _project_drop_keys(plan))
    except C.GamekitError:
        if checkpointed:
            C.restore_checkpoint(project, command_id)
        _cleanup(temps)
        raise
    except Exception:
        if checkpointed:
            C.restore_checkpoint(project, command_id)
        _cleanup(temps)
        raise
    receipt = {
        "ok": True,
        "status": "COMMITTED",
        "kind": "kit.add",
        "command_id": command_id,
        "project": project.project_id,
        "kit": kit["name"],
        "version": kit["version"],
        "license": "self-made",
        "files": [item["res"] for item in plan["files"]],
        "autoloads": plan["autoloads"],
        "replaced": bool(replace),
        "readback": "FRESH_PROCESS_MATCH",
        "at": C.now_iso(),
    }
    if kit["name"] == AUDIO_KIT:
        receipt["buses"] = [bus["name"] for bus in AUDIO_BUSES]
        receipt["files"] = list(receipt["files"]) + [AUDIO_LAYOUT_RES]
    journal.append(command_id, request_digest, receipt)
    return receipt


def remove_kit(
    project: C.Project,
    kit_name: str,
    command_id: str,
    *,
    force: bool = False,
    allow_open_editor: bool = False,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """Delete kit files and clear autoloads. Refuses when the game changed a file unless ``force``."""
    C.validate_command_id(command_id)
    load_kit(kit_name)
    journal = C.Journal(project)
    with C.project_lock(project, "kit.remove", wait_seconds=30):
        kit = load_kit(kit_name)
        request_digest = remove_request_digest(kit_name, force)
        prior = journal.replay_or_conflict(command_id, request_digest)
        if prior is not None:
            return prior
        C.refuse_if_editor_open(project, allow_open_editor)
        plan = plan_remove(project, kit)
        if plan["modified"] and not force:
            changed = list(plan["modified"])
            listed = ", ".join(changed)
            raise C.GamekitError(
                "CONFLICT",
                f"{len(changed)} kit file(s) changed since install: {listed}; keep them or pass --force",
                modified=changed,
            )
        return _commit_remove(
            project, kit, plan, command_id, request_digest, journal, timeout, force=force,
        )


def _commit_remove(
    project: C.Project,
    kit: dict[str, Any],
    plan: dict[str, Any],
    command_id: str,
    request_digest: str,
    journal: C.Journal,
    timeout: float,
    *,
    force: bool,
) -> dict[str, Any]:
    paths: list[Path] = []
    if plan["touch_project"] or kit["name"] == AUDIO_KIT:
        paths.append(project.root / "project.godot")
    for item in plan["files"]:
        if item["existed"]:
            paths.append(item["dest"])
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    temps: list[Path] = []
    checkpointed = False
    original_project_bytes = (project.root / "project.godot").read_bytes()
    try:
        C.checkpoint(project, command_id, unique)
        checkpointed = True
        if plan["touch_project"]:
            settings_res = _temp_res("settings", ".godot")
            temps.append(project.res_to_path(settings_res))
            _apply_settings_tool(project, {
                "mode": "apply",
                "temp_out": settings_res,
                "autoloads_set": {},
                "autoloads_clear": plan["autoloads_clear"],
                "settings": {},
                "settings_clear": [AUDIO_SETTING] if kit["name"] == AUDIO_KIT else [],
            }, timeout)
            settings_path = project.res_to_path(settings_res)
            if (project.root / "project.godot").read_bytes() != original_project_bytes:
                raise C.GamekitError("GODOT_FAILED", "settings tool modified project.godot directly")
            project_bytes = PC.merge_project_godot(
                original_project_bytes,
                settings_path.read_bytes(),
                drop_keys=_project_drop_keys(plan, removing=True),
            )
            if b"config_version=" not in project_bytes:
                raise C.GamekitError("GODOT_FAILED", "saved project file has no config_version")
            C.atomic_write_bytes(project.root / "project.godot", project_bytes)
        for item in plan["files"]:
            if item["dest"].is_file():
                item["dest"].unlink()
        if kit["name"] != AUDIO_KIT:
            _prune_empty(project.root / "addons" / "hh_kits" / kit["name"], project.root)
        _cleanup(temps)
        temps.clear()
        readback = _readback(project, {"mode": "readback", "scripts": [], "scenes": [], "setting_keys": []}, timeout)
        problems = _expect_absent(readback.get("autoloads", {}), plan["autoloads_clear"])
        if kit["name"] == AUDIO_KIT:
            buses = readback.get("buses", [])
            if len(buses) != 1 or buses[0].get("name") != "Master":
                problems.append(f"audio buses after remove are {buses!r}")
            if plan["audio_dest"] is not None and plan["audio_dest"].exists():
                problems.append("bus layout file still exists")
        for item in plan["files"]:
            if item["dest"].exists():
                problems.append(f"{item['res']} still exists")
        if problems:
            raise C.GamekitError("READBACK_MISMATCH", "; ".join(problems[:8]), problems=problems[:40])
        _scene_clean(project, timeout)
        PC.require_preserved(original_project_bytes, (project.root / "project.godot").read_bytes(), _project_drop_keys(plan, removing=True))
    except C.GamekitError:
        if checkpointed:
            C.restore_checkpoint(project, command_id)
        _cleanup(temps)
        raise
    except Exception:
        if checkpointed:
            C.restore_checkpoint(project, command_id)
        _cleanup(temps)
        raise
    receipt = {
        "ok": True,
        "status": "COMMITTED",
        "kind": "kit.remove",
        "command_id": command_id,
        "project": project.project_id,
        "kit": kit["name"],
        "removed": [item["res"] for item in plan["files"]],
        "autoloads_cleared": plan["autoloads_clear"],
        "forced": bool(force),
        "modified": list(plan["modified"]),
        "readback": "FRESH_PROCESS_MATCH",
        "at": C.now_iso(),
    }
    journal.append(command_id, request_digest, receipt)
    return receipt


# ---------------------------------------------------------------- CLI


def _cmd_list(_args: argparse.Namespace) -> dict[str, Any]:
    return {"ok": True, "kits": list_kits()}


def _cmd_add(args: argparse.Namespace) -> dict[str, Any]:
    return add_kit(
        C.get_project(args.project),
        args.kit,
        args.command_id,
        replace=args.replace,
        allow_open_editor=args.allow_open_editor,
    )


def _cmd_remove(args: argparse.Namespace) -> dict[str, Any]:
    return remove_kit(
        C.get_project(args.project),
        args.kit,
        args.command_id,
        force=args.force,
        allow_open_editor=args.allow_open_editor,
    )


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("kit", help="list / add / remove gameplay kits")
    ps = p.add_subparsers(dest="action", required=True)
    pl = ps.add_parser("list", help="list kits shipped with gamekit")
    pl.set_defaults(func=_cmd_list)
    pa = ps.add_parser("add", help="copy a kit into res://addons/hh_kits and register its autoloads")
    pa.add_argument("project")
    pa.add_argument("kit")
    pa.add_argument("--command-id", required=True)
    pa.add_argument("--replace", action="store_true", help="overwrite kit files that differ")
    pa.add_argument("--allow-open-editor", action="store_true")
    pa.set_defaults(func=_cmd_add)
    pr = ps.add_parser("remove", help="remove a kit's files and autoloads")
    pr.add_argument("project")
    pr.add_argument("kit")
    pr.add_argument("--command-id", required=True)
    pr.add_argument("--force", action="store_true", help="delete kit files even if the game changed them")
    pr.add_argument("--allow-open-editor", action="store_true")
    pr.set_defaults(func=_cmd_remove)
