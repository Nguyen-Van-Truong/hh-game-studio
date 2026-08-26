#!/usr/bin/env python3
"""R9-WP2: package exact addon/sidecar/launcher/checksum/licenses.

Does not tick the plan. Does not invent a signing cert. Unsigned internal only.
No online-latest bootstrap. PowerShell wrappers stay thin.
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
    p = argparse.ArgumentParser(description="Package HH Godot Agent (exact pins, unsigned).")
    p.add_argument("--out", required=True, help="destination bundle directory")
    p.add_argument("--version", default=studio.DEFAULT_VERSION)
    p.add_argument("--repo", default="", help="repo root (default: detected)")
    p.add_argument("--sign", action="store_true", help="refused: signing is E3")
    p.add_argument("--sign-cert", default="", help="refused unless a user-supplied E3 cert exists")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.sign or args.sign_cert:
        try:
            studio.refuse_signing_request()
        except studio.BundleError as exc:
            print(f"package: FAIL: {exc}", file=sys.stderr)
            if exc.do:
                print(f"package: do: {exc.do}", file=sys.stderr)
            return 2
    repo = studio.repo_root(Path(args.repo) if args.repo else None)
    out = Path(args.out)
    try:
        manifest = studio.build_package(repo, out, args.version)
    except studio.BundleError as exc:
        print(f"package: FAIL: {exc}", file=sys.stderr)
        if exc.do:
            print(f"package: do: {exc.do}", file=sys.stderr)
        return 1
    print(f"package: PASS {out}")
    print(f"package: version={manifest.get('version')} signing=unsigned privileges=current-user")
    print(f"package: files={len(manifest.get('files') or {})} CLEAN_VM stays unproven")
    print(json.dumps({"ok": True, "out": str(out.resolve()), "version": manifest.get("version")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
