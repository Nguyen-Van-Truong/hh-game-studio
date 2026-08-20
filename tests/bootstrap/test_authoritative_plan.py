#!/usr/bin/env python3
"""Singleton check for AUTHORITATIVE_PLAN markers.

Fails (exit != 0) if:
  - more than one walked file has a line exactly `AUTHORITATIVE_PLAN=1`
  - the 20-8 plan lacks that line
  - either 16-8 plan lacks a line exactly `AUTHORITATIVE_PLAN=0`

Walks the repo; skips `.git/` and `target/`. Stdlib only. Do not use cargo.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIR_NAMES = {".git", "target"}

PLAN_20_8 = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLANS_16_8 = (
    REPO_ROOT / "zdocs" / "16-8-game-studio-execution-plan-cho-ai-agent.txt",
    REPO_ROOT
    / "zdocs"
    / "16-8-game-studio-ai-native-ide-2d-first-master-plan.txt",
)

MARKER_ON = "AUTHORITATIVE_PLAN=1"
MARKER_OFF = "AUTHORITATIVE_PLAN=0"


def iter_repo_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def has_exact_marker_line(text: str, marker: str) -> bool:
    return any(line.strip() == marker for line in text.splitlines())


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    errors: list[str] = []

    text_20 = read_text(PLAN_20_8)
    if text_20 is None:
        errors.append(f"missing 20-8 plan: {rel(PLAN_20_8)}")
    elif not has_exact_marker_line(text_20, MARKER_ON):
        errors.append(f"{rel(PLAN_20_8)} lacks a line {MARKER_ON}")

    for plan in PLANS_16_8:
        text = read_text(plan)
        if text is None:
            errors.append(f"missing 16-8 plan: {rel(plan)}")
        elif not has_exact_marker_line(text, MARKER_OFF):
            errors.append(f"{rel(plan)} lacks a line {MARKER_OFF}")

    on_hits: list[Path] = []
    for path in iter_repo_files(REPO_ROOT):
        text = read_text(path)
        if text is None:
            continue
        if has_exact_marker_line(text, MARKER_ON):
            on_hits.append(path)

    if len(on_hits) != 1:
        names = [rel(p) for p in on_hits]
        errors.append(
            f"expected exactly one file with a line {MARKER_ON}, "
            f"found {len(on_hits)}: {names}"
        )
    elif on_hits[0].resolve() != PLAN_20_8.resolve():
        errors.append(
            f"{MARKER_ON} must live only in {rel(PLAN_20_8)}, "
            f"found in {rel(on_hits[0])}"
        )

    if errors:
        print("FAIL: AUTHORITATIVE_PLAN check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print("PASS: AUTHORITATIVE_PLAN singleton OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
