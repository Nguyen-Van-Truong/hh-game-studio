"""Run gamekit quick selftests: ``python -B -m studio.gamekit.selftest w1 [w2 ...] | all [--keep]``.

Each selftest builds throwaway projects under %TEMP%/hh-gamekit-selftest with isolated gamekit
state, drives the pinned Godot/Blender and prints one JSON summary. Exit 0 only if every check
passed. Temp folders are removed on success unless --keep is given; failures keep them.
"""

from __future__ import annotations

import importlib
import json
import shutil
import sys
import time
import traceback
from typing import Any

from . import common as C
from .selftests import Ctx

SELFTESTS = {
    "w1": "w1_scene",
    "w2": "w2_2d",
    "w3": "w3_3d",
    "w4": "w4_play",
    "w5": "w5_visual",
    "w6": "w6_perf",
    "w7": "w7_asset",
    "w8": "w8_blender",
    "w9": "w9_kit",
    "w10": "w10_export",
    "strict": "strict",
    "config": "config",
    "observe": "observe",
    "clips": "blender_clips",
    "replay": "replay",
    "save_bot": "save_bot",
    # Short native quality/effects smokes are opt-in by name. They are not
    # folded into the historical W12 acceptance counts or long matrices.
    "quality": "quality_smoke",
    "effects": "effects_smoke",
}


def run_one(name: str, keep: bool) -> dict[str, Any]:
    module_name = SELFTESTS[name]
    started = time.monotonic()
    ctx = Ctx(name)
    try:
        module = importlib.import_module(f"{__package__}.selftests.{module_name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__package__}.selftests.{module_name}":
            return {"selftest": name, "ok": False, "status": "NOT_WRITTEN", "checks": []}
        raise
    try:
        module.run(ctx)
    except C.GamekitError as exc:
        ctx.check("unexpected GamekitError", False, error=exc.to_json())
    except Exception as exc:  # noqa: BLE001 - a crashed selftest is a failed selftest
        ctx.check("unexpected exception", False, error=repr(exc)[:500], trace=traceback.format_exc()[-2000:])
    ok = ctx.ok()
    out = {
        "selftest": name,
        "ok": ok,
        "seconds": round(time.monotonic() - started, 1),
        "passed": sum(1 for c in ctx.checks if c["ok"]),
        "failed": [c for c in ctx.checks if not c["ok"]],
        "checks": len(ctx.checks),
        "temp": str(ctx.root),
    }
    if ok and not keep:
        shutil.rmtree(ctx.root, ignore_errors=True)
        out["temp"] = "removed"
    return out


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    keep = "--keep" in args
    names = [a for a in args if not a.startswith("--")] or ["all"]
    if names == ["all"]:
        names = list(SELFTESTS)
    unknown = [n for n in names if n not in SELFTESTS]
    if unknown:
        C.emit({"ok": False, "error": "BAD_REQUEST", "detail": f"unknown selftests {unknown}", "known": list(SELFTESTS)})
        return 2
    results = [run_one(n, keep) for n in names]
    summary = {"ok": all(r["ok"] for r in results), "at": C.now_iso(), "results": results}
    C.emit(json.loads(json.dumps(summary)))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
