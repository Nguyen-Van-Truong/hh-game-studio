"""hh doctor: fast health and hash check for the pinned Godot + Blender toolchain."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from . import common as C
from . import export as E


def _check_binary(path: Path, expected_sha256: str, *, verify_hashes: bool, env_var: str) -> dict[str, Any]:
    overridden = bool(os.environ.get(env_var)) if env_var else False
    exists = path.is_file() and not path.is_symlink()
    info: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "env_override": overridden,
        "expected_sha256": expected_sha256,
    }
    if not exists:
        info["ok"] = False
        return info
    info["bytes"] = path.stat().st_size
    if verify_hashes and not overridden:
        actual = C.sha256_file(path)
        info["actual_sha256"] = actual
        info["sha256_match"] = actual == expected_sha256
        info["ok"] = actual == expected_sha256
    else:
        info["ok"] = True
    return info


def run_doctor(*, verify_hashes: bool = False) -> dict[str, Any]:
    lock = C.toolchain_lock()
    godot_lock = lock["godot"]
    godot_tag = str(godot_lock["version"])
    gui_exe = C.TOOLING_DIR / f"godot-{godot_tag}" / str(godot_lock["gui_executable"])

    godot_console = _check_binary(
        C.godot_exe(), C.GODOT_CONSOLE_SHA256, verify_hashes=verify_hashes, env_var="HH_GODOT"
    )
    godot_gui = _check_binary(
        gui_exe, C.GODOT_GUI_SHA256, verify_hashes=verify_hashes, env_var=""
    )
    blender_bin = _check_binary(
        C.blender_exe(), C.BLENDER_EXE_SHA256, verify_hashes=verify_hashes, env_var="HH_BLENDER"
    )
    templates = E.templates(install=False, platform="all")

    measure_clear = True
    try:
        C.assert_measure_window_clear()
    except C.GamekitError:
        measure_clear = False

    archive_present = bool(templates.get("archive") and Path(str(templates["archive"])).is_file())
    ok = (
        godot_console["ok"]
        and godot_gui["ok"]
        and blender_bin["ok"]
        and archive_present
        and measure_clear
    )
    return {
        "ok": ok,
        "kind": "doctor",
        "pin": {"godot": C.GODOT_VERSION, "blender": C.BLENDER_VERSION},
        "toolchain_lock": str(C.TOOLCHAIN_LOCK_PATH),
        "verify_hashes": bool(verify_hashes),
        "godot_console": godot_console,
        "godot_gui": godot_gui,
        "blender": blender_bin,
        "export_templates": {
            "version": E.VERSION_TEXT,
            "archive_present": archive_present,
            "installed": bool(templates.get("installed")),
            "platforms": templates.get("platforms", {}),
        },
        "measure_window_clear": measure_clear,
    }


def _cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    return run_doctor(verify_hashes=bool(args.verify_hashes))


def register(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("doctor", help="check pinned Godot, Blender, and export template health")
    parser.add_argument(
        "--verify-hashes",
        action="store_true",
        help="re-hash the default Godot and Blender binaries against toolchain.lock.json",
    )
    parser.set_defaults(func=_cmd_doctor)
