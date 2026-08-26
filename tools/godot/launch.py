#!/usr/bin/env python3
"""R9-WP2: launch installed sidecar (and optional Godot) for a user project.

--provider plan stays when the host launcher is used. Does not invent an API key.
Does not tick the plan. Current-user only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import studio_bundle as studio


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Launch installed HH Godot Agent sidecar.")
    p.add_argument("--project", required=True, help="user Godot project")
    p.add_argument("--install-root", default="")
    p.add_argument("--godot", action="store_true", help="also start the pinned Godot GUI editor")
    p.add_argument("--sidecar-only", action="store_true")
    p.add_argument("--host", action="store_true", help="start host with --provider plan")
    p.add_argument("--provider", default="plan", help="host provider (default plan; do not invent keys)")
    return p.parse_args()


def pinned_gui() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise studio.BundleError("LOCALAPPDATA missing", do="run as the current user")
    return (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64.exe"
    )


def main() -> int:
    args = parse_args()
    if args.provider != "plan" and args.host:
        print("launch: FAIL: --provider plan stays; do not invent an API key", file=sys.stderr)
        return 2
    install_root = Path(args.install_root).resolve() if args.install_root else studio.default_install_root()
    project = Path(args.project).resolve()
    try:
        sidecar = studio.sidecar_main(install_root)
        node = studio.node_bin()
        cmd = [node, str(sidecar), "--project", str(project)]
        print(f"launch: sidecar {sidecar}")
        print(f"launch: project {project}")
        print("launch: signing=unsigned privileges=current-user CLEAN_VM stays unproven")
        if args.host:
            host = studio.launcher_main(install_root)
            env = os.environ.copy()
            env["HH_BRIDGE_MAIN"] = str(sidecar)
            host_cmd = [node, str(host), "--provider", "plan", "--mode", "persistent"]
            print(f"launch: host --provider plan {host}")
            print(f"launch: HH_BRIDGE_MAIN bundled sidecar (not repo bridge/dist)")
            subprocess.Popen(host_cmd, cwd=str(host.parent), env=env)
        if args.godot and not args.sidecar_only:
            gui = pinned_gui()
            if not gui.is_file():
                raise studio.BundleError(
                    "pinned Godot GUI missing",
                    do="python tools/godot/doctor.py --install",
                )
            subprocess.Popen([str(gui), "--editor", "--path", str(project)])
            print(f"launch: godot --path {project}")
        if args.sidecar_only or not args.godot:
            return subprocess.call(cmd, cwd=str(sidecar.parent))
        subprocess.Popen(cmd, cwd=str(sidecar.parent))
        return 0
    except studio.BundleError as exc:
        print(f"launch: FAIL: {exc}", file=sys.stderr)
        if exc.do:
            print(f"launch: do: {exc.do}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
