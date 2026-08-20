#!/usr/bin/env python3
"""R1-WP3 guard: bake-off scorecard exists for A+C; plugin-project stays addon-free.

Fails (exit != 0) if:
  - godot/plugin-project gained addons/plugin.cfg
  - SCORECARD.md missing A or C columns or required scenario rows
  - scorecard claims PASS for eval/shell/godot_exec/call_method without noting it was disabled

Stdlib only. Does not enable plugins. Does not fetch GitHub.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "e2e" / "bakeoff"))
from steps import STEPS  # noqa: E402

PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
SCORECARD = REPO_ROOT / "tests" / "e2e" / "bakeoff" / "SCORECARD.md"
README = REPO_ROOT / "tests" / "e2e" / "bakeoff" / "README.md"

EVAL_RE = re.compile(
    r"godot_exec|call_method|object\.callv|evaluate_expression|os\.execute",
    re.IGNORECASE,
)
DISABLED_RE = re.compile(
    r"disabled|refused|reject|UNSUPPORTED|AUTH_FAILED|spike",
    re.IGNORECASE,
)
ROW_RE = re.compile(
    r"^\|\s*(?P<step>[a-z0-9_]+)\s*\|"
    r"\s*(?P<a_status>PASS|FAIL|SKIP)\s*\|"
    r"(?P<a_ev>[^|]*)\|"
    r"(?P<a_notes>[^|]*)\|"
    r"\s*(?P<c_status>PASS|FAIL|SKIP)\s*\|"
    r"(?P<c_ev>[^|]*)\|"
    r"(?P<c_notes>[^|]*)\|"
    r"\s*$"
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def plugin_project_errors() -> list[str]:
    errors: list[str] = []
    if not PLUGIN_PROJECT.is_dir():
        return [f"missing {rel(PLUGIN_PROJECT)}"]
    addons = PLUGIN_PROJECT / "addons"
    if addons.is_dir():
        leftover = [
            p for p in addons.rglob("*") if p.is_file() and ".godot" not in p.parts
        ]
        if leftover:
            errors.append(
                "godot/plugin-project/addons/ must stay empty; found "
                + ", ".join(rel(p) for p in leftover[:8])
            )
    for marker in PLUGIN_PROJECT.rglob("*"):
        if not marker.is_file() or any(part == ".godot" for part in marker.parts):
            continue
        if marker.name.lower() in {"plugin.cfg", "plugin.gd"}:
            errors.append(f"plugin-project must not contain addon files: {rel(marker)}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(plugin_project_errors())

    if not README.is_file():
        errors.append(f"missing {rel(README)}")
    if not SCORECARD.is_file():
        errors.append(f"missing {rel(SCORECARD)}")
        print("FAIL: bake-off guard", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    text = SCORECARD.read_text(encoding="utf-8")
    if re.search(r"npx\s+-y\s+latest", text) and "forbidden" not in text.lower():
        errors.append("scorecard must not instruct npx -y latest")
    if "A" not in text or "C" not in text:
        errors.append("SCORECARD.md must name candidates A and C")
    if "tool count" not in text.lower() and "not a score" not in text.lower():
        errors.append("SCORECARD.md must say tool count is not the score")

    parsed: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        match = ROW_RE.match(line.strip())
        if not match:
            continue
        parsed[match.group("step")] = {
            "A": match.group("a_status"),
            "C": match.group("c_status"),
            "a_notes": match.group("a_notes"),
            "c_notes": match.group("c_notes"),
        }

    missing = [s for s in STEPS if s not in parsed]
    if missing:
        errors.append(f"SCORECARD.md missing scenario rows: {missing[:8]}")

    for step, row in parsed.items():
        for side in ("A", "C"):
            notes = row["a_notes"] if side == "A" else row["c_notes"]
            blob = f"{step} {notes}"
            if row[side] != "PASS":
                continue
            if not EVAL_RE.search(blob) and not EVAL_RE.search(step):
                continue
            if step == "unsupported_eval_or_callv":
                if not DISABLED_RE.search(notes):
                    errors.append(
                        f"{side} {step} PASS must note eval/call_method was disabled"
                    )
                continue
            if not DISABLED_RE.search(notes):
                errors.append(
                    f"{side} {step} claims PASS for eval/shell without noting it was disabled"
                )

    # Capability rows must not celebrate a live exec/callv.
    for step in ("unsupported_eval_or_callv",):
        if step not in parsed:
            continue
        for side, notes_key in (("A", "a_notes"), ("C", "c_notes")):
            notes = parsed[step][notes_key]
            if parsed[step][side] == "PASS" and not DISABLED_RE.search(notes):
                errors.append(f"{side} {step} PASS without disabled/refused note")

    if errors:
        print("FAIL: bake-off guard", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: plugin-project has no addons; SCORECARD has A+C rows; "
        "eval/call_method PASS only as disabled refusal"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
