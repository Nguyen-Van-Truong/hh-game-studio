#!/usr/bin/env python3
"""R9-WP2: current-user install/update/uninstall/rollback/doctor.

Keeps user projects. No admin. Tampered hashes reject. Signing is E3.
Does not tick the plan. Does not stamp CLEAN_VM as proven.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import studio_bundle as studio


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Install HH Godot Agent for the current user.")
    p.add_argument(
        "command",
        choices=("install", "update", "rollback", "uninstall", "enable-project", "setup", "doctor"),
    )
    p.add_argument("--from", dest="bundle", default="", help="bundle directory")
    p.add_argument("--install-root", default="", help="override current-user install root")
    p.add_argument("--project", default="", help="user Godot project (never under install-root)")
    p.add_argument("--sign", action="store_true", help="refused: signing is E3")
    return p.parse_args()


def root_of(args: argparse.Namespace) -> Path:
    if args.install_root:
        return Path(args.install_root).resolve()
    return studio.default_install_root()


def main() -> int:
    args = parse_args()
    if args.sign:
        try:
            studio.refuse_signing_request()
        except studio.BundleError as exc:
            print(f"install: FAIL: {exc}", file=sys.stderr)
            if exc.do:
                print(f"install: do: {exc.do}", file=sys.stderr)
            return 2
    install_root = root_of(args)
    try:
        if args.command in {"install", "update"}:
            if not args.bundle:
                raise studio.BundleError("missing --from <bundle>", do="pass the packaged directory")
            state = studio.install_bundle(Path(args.bundle), install_root)
            print(f"install: PASS version={state.get('version')} root={install_root}")
            print("install: privileges=current-user signing=unsigned CLEAN_VM stays unproven")
            return 0
        if args.command == "setup":
            if not args.bundle or not args.project:
                raise studio.BundleError(
                    "setup needs --from <bundle> and --project <dir>",
                    do="one command: install studio + enable the user project",
                )
            state = studio.setup(Path(args.bundle), install_root, Path(args.project))
            print(f"install: PASS setup version={state.get('version')} project={Path(args.project).resolve()}")
            print("install: user project kept outside install root; no extra folder copy")
            return 0
        if args.command == "enable-project":
            if not args.project:
                raise studio.BundleError("missing --project", do="pass the user game folder")
            plugin = studio.enable_project(Path(args.project), install_root)
            print(f"install: PASS enabled {plugin}")
            return 0
        if args.command == "rollback":
            state = studio.rollback_install(install_root)
            print(f"install: PASS rollback version={state.get('version')} previous={state.get('previous_version')}")
            return 0
        if args.command == "uninstall":
            kept = studio.uninstall(install_root)
            print("install: PASS uninstall; install root removed")
            for path in kept:
                print(f"install: kept user project {path}")
            return 0
        if args.command == "doctor":
            project = Path(args.project) if args.project else None
            report = studio.doctor_report(install_root, project)
            print(studio.format_doctor(report))
            print(json.dumps({k: report[k] for k in ("ok", "version", "clean_vm", "errors", "actions")}, sort_keys=True))
            return 0 if report.get("ok") else 1
    except studio.BundleError as exc:
        print(f"install: FAIL: {exc}", file=sys.stderr)
        if exc.do:
            print(f"install: do: {exc.do}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
