#!/usr/bin/env python3
"""R1-WP2: MCP bake-off scorecard + pin/license + no plugin-project addons.

Fails (exit != 0) if:
  - MCP_BAKEOFF.md missing required candidate headings / shortlist / fail-hard
  - a PIN.json SHA is missing from the bake-off or is not 40 hex chars
  - a staged LICENSE does not look like MIT
  - godot/plugin-project contains an enabled addon (plugin.cfg / plugin.gd)
  - bake-off tells us to npx -y latest or to buy Beckett Full
  - shortlist names more than two bake-off candidates

Stdlib only. Do not use cargo. Does not enable plugins or run E2E (R1-WP3).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BAKEOFF = REPO_ROOT / "docs" / "godot-agent" / "MCP_BAKEOFF.md"
STAGING = REPO_ROOT / "third_party" / "mcp-staging"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"

CANDIDATES = (
    {
        "id": "A",
        "dir": "satelliteoflove-godot-mcp",
        "heading": "satelliteoflove/godot-mcp",
        "commit": "1b7d40537240fd54300f54bf6fda1ea91f06c878",
        "shortlist": True,
        "fail_hard": False,
    },
    {
        "id": "B",
        "dir": "keeveeg-godot-mcp",
        "heading": "KeeVeeG/godot-mcp",
        "commit": "9ea1a41b9ed6cd819c602a37cc111c50017707d8",
        "shortlist": False,
        "fail_hard": True,
    },
    {
        "id": "C",
        "dir": "beckett-godot-mcp-lite",
        "heading": "beckettlab/beckett-godot-mcp",
        "commit": "efb81dec03ba0af2b7a6dce0e4678bdbde5e454d",
        "shortlist": True,
        "fail_hard": False,
    },
    {
        "id": "D",
        "dir": "sods2-godot-mcp",
        "heading": "Sods2/godot-mcp",
        "commit": "78b2cee00d697f117d6875e07675101b867efe70",
        "shortlist": False,
        "fail_hard": True,
    },
)

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MIT_HEAD = "MIT License"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    errors: list[str] = []

    if not BAKEOFF.is_file():
        print(f"FAIL: missing {rel(BAKEOFF)}", file=sys.stderr)
        return 1
    text = BAKEOFF.read_text(encoding="utf-8")

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Do **not**") or stripped.startswith("Do not"):
            continue
        if re.search(r"npx\s+-y\s+latest", stripped):
            errors.append("bake-off contains npx -y latest command")
            break
    if "do not buy" not in text.lower():
        errors.append("bake-off must refuse buying Beckett Full")

    shortlist_names = []
    for cand in CANDIDATES:
        if cand["heading"] not in text:
            errors.append(f"bake-off missing heading for {cand['heading']}")
        if cand["commit"] not in text:
            errors.append(f"bake-off missing pin SHA {cand['commit']}")
        pin_path = STAGING / cand["dir"] / "PIN.json"
        lic_path = STAGING / cand["dir"] / "LICENSE"
        if not pin_path.is_file():
            errors.append(f"missing {rel(pin_path)}")
            continue
        if not lic_path.is_file():
            errors.append(f"missing {rel(lic_path)}")
        else:
            lic = lic_path.read_text(encoding="utf-8", errors="replace")
            if not lic.lstrip().startswith(MIT_HEAD):
                errors.append(f"{rel(lic_path)} does not start with {MIT_HEAD!r}")
        try:
            pin = json.loads(pin_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{rel(pin_path)} invalid JSON: {exc}")
            continue
        commit = str(pin.get("commit", ""))
        if not SHA_RE.fullmatch(commit):
            errors.append(f"{rel(pin_path)} commit is not a 40-char SHA")
        elif commit != cand["commit"]:
            errors.append(
                f"{rel(pin_path)} commit {commit} != bake-off pin {cand['commit']}"
            )
        if str(pin.get("spdx", "")).upper() != "MIT":
            errors.append(f"{rel(pin_path)} SPDX is not MIT")
        if pin.get("cloned_into_plugin_project") is not False:
            errors.append(f"{rel(pin_path)} must set cloned_into_plugin_project false")
        if cand["id"] == "C":
            if str(pin.get("edition", "")).lower() != "lite":
                errors.append(f"{rel(pin_path)} must record edition Lite")

        if cand["shortlist"]:
            shortlist_names.append(cand["heading"])

    if "shortlist (max two)" not in text.lower():
        errors.append("bake-off missing shortlist (max two) verdict")
    if "A `satelliteoflove/godot-mcp`, C Beckett **Lite**" not in text:
        errors.append("bake-off must name shortlist A satelliteoflove and C Lite")

    if "KeeVeeG" not in text or "Sods2" not in text:
        errors.append("bake-off must name eliminated KeeVeeG and Sods2")
    if "E2" not in text:
        errors.append("bake-off must mark Beckett Full as E2 fail-hard")

    if PLUGIN_PROJECT.is_dir():
        for marker in PLUGIN_PROJECT.rglob("*"):
            if not marker.is_file():
                continue
            if any(part == ".godot" for part in marker.parts):
                continue
            name = marker.name.lower()
            if name in {"plugin.cfg", "plugin.gd"}:
                errors.append(
                    f"plugin-project must not contain addon files: {rel(marker)}"
                )
        addons = PLUGIN_PROJECT / "addons"
        if addons.is_dir():
            leftover = [
                p
                for p in addons.rglob("*")
                if p.is_file() and ".godot" not in p.parts
            ]
            if leftover:
                errors.append(
                    "godot/plugin-project/addons/ must stay empty; found "
                    + ", ".join(rel(p) for p in leftover[:8])
                )

    if len(shortlist_names) > 2:
        errors.append(f"shortlist coding error: {shortlist_names}")

    if errors:
        print("FAIL: MCP bake-off check", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: MCP bake-off 4 MIT pins, shortlist A+C Lite, "
        "fail-hard B/D/Full, plugin-project has no addons"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
