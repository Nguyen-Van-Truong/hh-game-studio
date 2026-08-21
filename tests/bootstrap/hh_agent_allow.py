"""Allow only godot/plugin-project/addons/hh_agent. Still forbid vendor MCP addons."""

from __future__ import annotations

from pathlib import Path

ALLOWED_ADDON = "hh_agent"
SKIP_DIR_NAMES = {".godot"}


def rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def hh_agent_only_addon_errors(plugin_project: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not plugin_project.is_dir():
        return [f"missing {rel(plugin_project, repo_root)}"]
    addons = plugin_project / "addons"
    hh = addons / ALLOWED_ADDON
    if not hh.is_dir():
        errors.append(f"missing {rel(hh, repo_root)}")
    if not (hh / "plugin.cfg").is_file():
        errors.append(f"missing {rel(hh / 'plugin.cfg', repo_root)}")
    if addons.is_dir():
        for child in addons.iterdir():
            if child.name in SKIP_DIR_NAMES:
                continue
            if child.is_dir() and child.name != ALLOWED_ADDON:
                errors.append(
                    f"only addons/{ALLOWED_ADDON} is allowed, found {rel(child, repo_root)}"
                )
            elif child.is_file() and child.suffix.lower() != ".uid":
                errors.append(f"unexpected file in addons/: {rel(child, repo_root)}")
    for marker in plugin_project.rglob("*"):
        if not marker.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in marker.parts):
            continue
        name = marker.name.lower()
        posix = marker.as_posix().lower()
        if name in {"plugin.cfg", "plugin.gd"}:
            try:
                parts = marker.resolve().relative_to(plugin_project.resolve()).parts
            except ValueError:
                parts = marker.parts
            if parts[:2] != ("addons", ALLOWED_ADDON):
                errors.append(f"addon file outside hh_agent: {rel(marker, repo_root)}")
        if "hh_stock_poc" in posix:
            errors.append(f"hh_stock_poc must not be copied into plugin-project: {rel(marker, repo_root)}")
    if (repo_root / "godot" / "addons").exists():
        errors.append("godot/addons/ must not exist")
    return errors
