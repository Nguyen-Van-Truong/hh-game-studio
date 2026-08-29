#!/usr/bin/env python3
"""VF1-WP2 structure check: sim schema files exist and stay honest.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_sim_contract.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "src" / "sim"
DATA = ROOT / "data" / "sim"
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"

REQUIRED_SCRIPTS = (
    "sim_constants.gd",
    "input_frame.gd",
    "sim_clock.gd",
    "collision_layers.gd",
    "sim_events.gd",
    "sim_snapshot.gd",
    "sim_validator.gd",
    "sim_seed.gd",
)

REQUIRED_DATA = (
    "schema.json",
    "collision_layers.json",
    "input_actions.json",
    "event_order.json",
)


def main() -> int:
    errors: list[str] = []
    for name in REQUIRED_SCRIPTS:
        path = SIM / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
        else:
            text = path.read_text(encoding="utf-8")
            if re.search(r"Superfighters|Super Fighter", text):
                errors.append(f"{name} contains Superfighters trademark")
    for name in REQUIRED_DATA:
        path = DATA / name
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{name} must be an object")
    schema_path = DATA / "schema.json"
    if schema_path.is_file():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("tick_hz") != 60:
            errors.append("schema tick_hz must be 60")
        if schema.get("y8_tick_rate_claimed") is not False:
            errors.append("schema must set y8_tick_rate_claimed false")
        if schema.get("title") != "Vault Fighters":
            errors.append("schema title must be Vault Fighters")
        if schema.get("ledger_clock") != "RL-SIM-FIXED-60":
            errors.append("schema must cite ledger:RL-SIM-FIXED-60")
        reserved = schema.get("input_frame", {}).get("reserved_not_shipped", [])
        allowed = schema.get("input_frame", {}).get("allowed_actions", [])
        if "roll" not in allowed:
            errors.append("schema must allow shipped roll")
        if "roll" in reserved:
            errors.append("schema must not reserve shipped roll")
        for action in ("dive", "kick"):
            if action not in allowed:
                errors.append(f"schema must allow shipped {action}")
            if action in reserved:
                errors.append(f"schema must not reserve shipped {action}")
        if "ledge" not in reserved:
            errors.append("schema must reserve ledge as not shipped")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in ("RL-SIM-FIXED-60", "RL-CTRL-HOLD-AIM", "RL-MOVE-ROLL-DIVE"):
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "does **not** claim Y8 parity" not in ledger:
        errors.append("ledger lost honesty phrase")
    if errors:
        print("FAIL: Vault Fighters VF1-WP2 sim contract files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF1-WP2 sim contract files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} data={len(REQUIRED_DATA)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
