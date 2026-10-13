"""hh: gamekit command line. Run from 8-9-hh3d-3 as ``python -B -m studio.gamekit.hh <command>``
or through ``studio\\gamekit\\hh.cmd``. Every command prints one JSON object; exit 0 = ok,
1 = command ran but reported a failure (e.g. check found problems), 2 = refused or error."""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Any, Sequence

from . import common as C

# Each module exposes register(subparsers); modules that are not written yet are skipped.
MODULES = ("scene", "inputmap", "play", "bot", "shot", "perf", "asset", "blender_recipe", "kit", "export", "quality", "sfx", "vfx")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hh", description="HH gamekit: edit, play and check Godot game projects")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in MODULES:
        try:
            module = importlib.import_module(f"{__package__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"{__package__}.{name}":
                continue
            raise
        module.register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: dict[str, Any] = args.func(args)
    except C.GamekitError as exc:
        C.emit(exc.to_json())
        return 2
    C.emit(result)
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    sys.exit(main())
