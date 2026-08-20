#!/usr/bin/env python3
"""Parse docs/godot-agent/CAPABILITY_MATRIX.md (R1-WP1).

Fails (exit != 0) if:
  - unique CM-xxx IDs < 100
  - a WP group is missing
  - R8 traces section is missing or a required R8 keyword has no CM-ID
  - any row is Status=Supported and Pri=P0 without a stock 4.7.1 hint
    (EditorInterface, Godot CLI, or a godot/ path) in API/Notes/headless cells

Stdlib only. Do not use cargo.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "docs" / "godot-agent" / "CAPABILITY_MATRIX.md"

ID_RE = re.compile(r"^CM-\d{3,}$")
CM_IN_TEXT_RE = re.compile(r"CM-\d{3,}")

REQUIRED_GROUPS = (
    "project",
    "scene",
    "node",
    "inspector",
    "filesystem",
    "script",
    "TileMap",
    "animation",
    "UI",
    "audio",
    "physics/navigation",
    "Play/debug/export",
)

# Keywords from R1-WP1 / R8 Kho Bí Ẩn loop. Each must appear in the R8 traces
# section on a line that also contains a CM-xxx id.
R8_KEYWORDS = (
    "R8-WP1",
    "R8-WP2",
    "R8-WP3",
    "R8-WP4",
    "R8-WP5",
    "R8-WP6",
    "move",
    "interact",
    "key",
    "door",
    "NPC",
    "win/loss/restart",
    "keyboard+gamepad",
    "1280x720",
    "tilemap",
    "inventory",
    "save/load",
    "HUD",
    "audio",
    "export",
)

MIN_UNIQUE_IDS = 100
EXPECTED_COLS = 12

# Header names (lowercase) -> index in a matrix data row.
COL_ID = 0
COL_GROUP = 1
COL_API = 4
COL_HEADLESS = 8
COL_PRI = 9
COL_STATUS = 10
COL_NOTES = 11


def split_md_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_separator(cols: list[str]) -> bool:
    if not cols:
        return False
    return all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cols)


def parse_matrix_rows(text: str) -> list[list[str]]:
    """All pipe-table data rows whose first cell is CM-xxx (not the R8 map)."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        cols = split_md_row(line)
        if cols is None or is_separator(cols):
            continue
        if ID_RE.fullmatch(cols[0]):
            rows.append(cols)
    return rows


def r8_traces_section(text: str) -> str | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+R8 traces\s*$", line, re.IGNORECASE):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^##\s+", lines[j]) and not lines[j].startswith("###"):
            end = j
            break
    return "\n".join(lines[start:end])


def keyword_line_pattern(keyword: str) -> re.Pattern[str]:
    """Whole-token match so 'key' does not hit 'keyboard'."""
    if re.fullmatch(r"[A-Za-z0-9]+", keyword):
        return re.compile(rf"(?i)(?<![A-Za-z0-9_]){re.escape(keyword)}(?![A-Za-z0-9_])")
    return re.compile(re.escape(keyword), re.IGNORECASE)


def stock_hint(api: str, headless: str, notes: str) -> bool:
    blob = f"{api} {headless} {notes}"
    return (
        "EditorInterface" in blob
        or "Godot CLI" in blob
        or "godot/" in blob
    )


def main() -> int:
    errors: list[str] = []

    if not MATRIX.is_file():
        print(f"FAIL: missing {MATRIX.as_posix()}", file=sys.stderr)
        return 1

    text = MATRIX.read_text(encoding="utf-8")
    rows = parse_matrix_rows(text)
    ids = [r[0] for r in rows]
    unique = set(ids)

    if len(unique) < MIN_UNIQUE_IDS:
        errors.append(
            f"unique CM-xxx IDs = {len(unique)} (need >= {MIN_UNIQUE_IDS})"
        )

    dupes = [i for i in unique if ids.count(i) > 1]
    if dupes:
        errors.append(f"duplicate IDs: {sorted(dupes)}")

    for r in rows:
        if len(r) != EXPECTED_COLS:
            errors.append(
                f"{r[0] if r else '?'} has {len(r)} columns, expected {EXPECTED_COLS}"
            )

    groups = {r[COL_GROUP] for r in rows if len(r) > COL_GROUP}
    missing_groups = [g for g in REQUIRED_GROUPS if g not in groups]
    if missing_groups:
        errors.append(f"missing WP groups: {missing_groups}")

    for r in rows:
        if len(r) < EXPECTED_COLS:
            continue
        status = r[COL_STATUS]
        pri = r[COL_PRI]
        if status not in {"Supported", "Alternative", "Gap"}:
            errors.append(f"{r[COL_ID]} Status={status!r} not Supported/Alternative/Gap")
        if pri not in {"P0", "P1", "P2"}:
            errors.append(f"{r[COL_ID]} Pri={pri!r} not P0/P1/P2")
        if status == "Supported" and pri == "P0":
            if not stock_hint(r[COL_API], r[COL_HEADLESS], r[COL_NOTES]):
                errors.append(
                    f"{r[COL_ID]} Supported P0 lacks EditorInterface, Godot CLI, "
                    "or godot/ in API/Notes/headless"
                )

    traces = r8_traces_section(text)
    if traces is None:
        errors.append("missing section heading '## R8 traces'")
    else:
        matrix_ids = unique
        for kw in R8_KEYWORDS:
            pat = keyword_line_pattern(kw)
            found_ids: list[str] = []
            for line in traces.splitlines():
                if not pat.search(line):
                    continue
                found_ids.extend(CM_IN_TEXT_RE.findall(line))
            if not found_ids:
                errors.append(
                    f"R8 traces: keyword {kw!r} has no CM-ID on a matching line"
                )
                continue
            unknown = [i for i in found_ids if i not in matrix_ids]
            if unknown:
                errors.append(
                    f"R8 traces keyword {kw!r} references unknown IDs: {unknown}"
                )

    if errors:
        print("FAIL: capability matrix check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        f"PASS: capability matrix {len(unique)} unique IDs, "
        f"{len(REQUIRED_GROUPS)} groups, R8 traces OK"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
