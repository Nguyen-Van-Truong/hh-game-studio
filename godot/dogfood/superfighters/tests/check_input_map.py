#!/usr/bin/env python3
"""VF2-WP1 structure check: input map, remap schema, P1/P2 split.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_input_map.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "input-mapping.md"
ACTIONS = ROOT / "data" / "sim" / "input_actions.json"
SCHEMA = ROOT / "data" / "input" / "remap_schema.json"
DEFAULTS = ROOT / "data" / "input" / "default_bindings.json"
TRACE = ROOT / "tests" / "traces" / "input" / "p1_p2_independent.json"
INJECTOR = ROOT / "src" / "input" / "input_injector.gd"
CASES = ROOT / "tests" / "input_map_cases.gd"

REQUIRED_SCRIPTS = (
    "src/input/input_constants.gd",
    "src/input/input_injector.gd",
    "src/input/input_map_store.gd",
    "src/input_actions.gd",
    "src/ui/remap_screen.gd",
    "tests/input_map_cases.gd",
    "tests/run_input_map.gd",
)

REQUIRED_LEDGER = (
    "RL-CTRL-P1-MOVE",
    "RL-CTRL-P1-PUNCH",
    "RL-CTRL-P1-SHOOT",
    "RL-CTRL-P1-NADE",
    "RL-CTRL-P2-MOVE",
    "RL-CTRL-P2-ATK",
    "RL-CTRL-FULLSCREEN",
    "RL-CTRL-HOLD-AIM",
    "RL-CTRL-DEADZONE",
    "RL-CTRL-DEVICE-SPLIT",
    "RL-CTRL-REMAP",
    "RL-CTRL-SYNTH-PAD",
    "RL-SIM-FIXED-60",
    "RL-SIM-INPUT-FRAME",
    "RL-MOVE-ROLL-DIVE",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED_SCRIPTS:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        if TRADEMARK.search(text):
            errors.append(f"{rel} contains Superfighters trademark")
    injector = INJECTOR.read_text(encoding="utf-8") if INJECTOR.is_file() else ""
    if "parse_input_event" not in injector:
        errors.append("injector must use parse_input_event")
    if re.search(r"action_press\s*\(", injector):
        errors.append("injector must not call action_press")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("input_map_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("input_map_cases must not call action_press")
    if "step_from_live_input" not in cases:
        errors.append("input_map_cases must prove live InputFrame stepping")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if "controls_pressed" not in title:
        errors.append("title missing Controls signal")
    for path, schema_id in (
        (SCHEMA, "vf.input.remap.v1"),
        (DEFAULTS, "vf.input.remap.v1"),
        (TRACE, "vf.input.event_trace.v1"),
        (ACTIONS, "vf.sim.input_actions.v1"),
    ):
        if not path.is_file():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name} is not JSON: {exc}")
            continue
        dumped = json.dumps(payload)
        if payload.get("schema") != schema_id:
            errors.append(f"{path.name} schema id mismatch")
        if payload.get("title") != "Vault Fighters" and path != ACTIONS:
            errors.append(f"{path.name} title must be Vault Fighters")
        if payload.get("y8_parity_claimed") is True:
            errors.append(f"{path.name} claimed Y8 parity")
        if TRADEMARK.search(dumped):
            errors.append(f"{path.name} contains Superfighters trademark")
    if SCHEMA.is_file():
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        if schema.get("deadzone") != 0.25:
            errors.append("remap schema deadzone must be 0.25")
        if schema.get("p1_device") != 0 or schema.get("p2_device") != 1:
            errors.append("remap schema devices must be P1=0 P2=1")
        if schema.get("atomic_save") != "temp_rename":
            errors.append("remap schema must declare temp_rename")
        if schema.get("hold_to_aim_class") != "assumption":
            errors.append("hold-to-aim must stay assumption")
        if "F11" not in schema.get("forbidden_fighter_keys", []):
            errors.append("remap schema must forbid F11")
        if schema.get("ledger_clock") != "RL-SIM-FIXED-60":
            errors.append("remap schema must cite RL-SIM-FIXED-60")
    if DEFAULTS.is_file():
        defaults = json.loads(DEFAULTS.read_text(encoding="utf-8"))
        actions = defaults.get("actions", {})
        for name, device in (("p1_melee", 0), ("p2_melee", 1)):
            joy = [row for row in actions.get(name, []) if row.get("kind") == "joy_button"]
            if not joy or joy[0].get("device") != device:
                errors.append(f"{name} default pad device must be {device}")
        if any(row.get("physical") == "F11" for rows in actions.values() for row in rows):
            errors.append("defaults bind F11")
    if TRACE.is_file():
        trace = json.loads(TRACE.read_text(encoding="utf-8"))
        if trace.get("used_step_fixed") is not False:
            errors.append("input trace must set used_step_fixed false")
        if trace.get("used_action_press") is not False:
            errors.append("input trace must set used_action_press false")
        if trace.get("gamepad", {}).get("non_hardware") is not True:
            errors.append("input trace must mark synthetic pad non-hardware")
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append("input trace must keep hold-to-aim assumption")
        if trace.get("y8_tick_rate_claimed") is not False:
            errors.append("input trace must not claim a Y8 tick rate")
        ids = {str(step.get("id")) for step in trace.get("steps", [])}
        for sid in ("p1_right_press", "p2_d_press", "p1_pad_jump", "p2_pad_jump", "p1_stick_dead", "f11_not_fighter"):
            if sid not in ids:
                errors.append(f"input trace missing step {sid}")
    if ACTIONS.is_file():
        actions = json.loads(ACTIONS.read_text(encoding="utf-8"))
        if actions.get("deadzone") != 0.25:
            errors.append("input_actions.json deadzone must be 0.25")
        if actions.get("p1_device") != 0 or actions.get("p2_device") != 1:
            errors.append("input_actions.json devices must split 0/1")
        if actions.get("hold_to_aim_class") != "assumption":
            errors.append("input_actions.json hold-to-aim must stay assumption")
    if not DOCS.is_file():
        errors.append("missing docs/input-mapping.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-CTRL-P1-MOVE",
            "ledger:RL-CTRL-HOLD-AIM",
            "does **not** claim Y8 parity",
            "parse_input_event",
            "non-hardware",
            "temp+rename",
        ):
            if needle not in docs:
                errors.append(f"input docs missing {needle}")
        if TRADEMARK.search(docs) and "Superfighters trademark" not in docs:
            # Honesty mention of the reference title is OK only if we also
            # refuse the product name. The doc should not ship the trademark
            # as a display title.
            if "title card" not in docs.lower():
                errors.append("input docs mention Superfighters without honesty")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF2-WP1" not in ledger:
        errors.append("ledger missing VF2-WP1 section")
    if errors:
        print("FAIL: Vault Fighters VF2-WP1 input files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF2-WP1 input files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} ledger={len(REQUIRED_LEDGER)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
