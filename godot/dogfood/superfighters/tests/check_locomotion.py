#!/usr/bin/env python3
"""VF2-WP2 structure check: locomotion data, traces, honesty.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_locomotion.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "locomotion.md"
LOCO = ROOT / "data" / "sim" / "locomotion.json"
FIGHTER = ROOT / "src" / "fighter.gd"
CASES = ROOT / "tests" / "locomotion_cases.gd"
TRACE_DIR = ROOT / "tests" / "traces" / "locomotion"

REQUIRED_SCRIPTS = (
    "src/sim/locomotion.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "tests/locomotion_cases.gd",
    "tests/run_locomotion.gd",
)

REQUIRED_TRACES = (
    "walk_accel_friction.json",
    "crouch_shape.json",
    "pit_fall.json",
    "no_tunnel_solid.json",
    "no_tunnel_oneway.json",
    "variable_jump.json",
)

REQUIRED_LEDGER = (
    "RL-MOVE-LOCO-BASE",
    "RL-MOVE-JUMP-CROUCH",
    "RL-MOVE-ROLL-DIVE",
    "RL-CAM-ARENA",
    "RL-CTRL-HOLD-AIM",
    "RL-SIM-FIXED-60",
    "RL-SIM-INPUT-FRAME",
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
        if TRADEMARK.search(text) and "trademark" not in text.lower():
            errors.append(f"{rel} contains Superfighters trademark")
    fighter = FIGHTER.read_text(encoding="utf-8") if FIGHTER.is_file() else ""
    if "Locomotion.apply_to" not in fighter:
        errors.append("fighter.gd must load locomotion.json")
    if re.search(r"const GRAVITY", fighter):
        errors.append("fighter.gd still hardcodes GRAVITY")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("locomotion_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("locomotion_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("locomotion_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("locomotion_cases must prove live InputFrame stepping")
    if "parse_input_event" not in (ROOT / "src/input/input_injector.gd").read_text(encoding="utf-8"):
        errors.append("injector must use parse_input_event")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not LOCO.is_file():
        errors.append("missing data/sim/locomotion.json")
    else:
        try:
            payload = json.loads(LOCO.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"locomotion.json is not JSON: {exc}")
            payload = {}
        if payload:
            if payload.get("schema") != "vf.sim.locomotion.v1":
                errors.append("locomotion schema id mismatch")
            if payload.get("title") != "Vault Fighters":
                errors.append("locomotion title must be Vault Fighters")
            if payload.get("y8_parity_claimed") is True:
                errors.append("locomotion claimed Y8 parity")
            if payload.get("y8_tick_rate_claimed") is not False:
                errors.append("locomotion must set y8_tick_rate_claimed false")
            if payload.get("tick_hz") != 60:
                errors.append("locomotion tick_hz must be 60")
            if payload.get("epsilon") != 0.001:
                errors.append("locomotion epsilon must be 0.001")
            if payload.get("hold_to_aim_class") != "assumption":
                errors.append("hold-to-aim must stay assumption")
            if payload.get("roll_dive_class") != "unavailable":
                errors.append("roll/dive must stay unavailable")
            if payload.get("jump_crouch_class") != "assumption":
                errors.append("jump/crouch must stay assumption")
            if payload.get("camera_class") != "assumption":
                errors.append("camera must stay assumption")
            if payload.get("ledger_clock") != "RL-SIM-FIXED-60":
                errors.append("locomotion must cite RL-SIM-FIXED-60")
            cam = payload.get("camera", {})
            if cam.get("mode") != "arena_fit":
                errors.append("camera mode must be arena_fit")
            if cam.get("designed_view_x") != 1280.0:
                errors.append("designed view width must be 1280")
            move = payload.get("movement", {})
            for key in ("gravity", "jump_vel", "walk", "accel", "friction", "coyote", "jump_buf"):
                if key not in move:
                    errors.append(f"locomotion movement missing {key}")
            if TRADEMARK.search(json.dumps(payload)):
                errors.append("locomotion.json contains Superfighters trademark")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing locomotion trace {name}")
            continue
        try:
            trace = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not JSON: {exc}")
            continue
        if trace.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append(f"{name} must set used_step_fixed false")
        if trace.get("used_action_press") is not False:
            errors.append(f"{name} must set used_action_press false")
        if trace.get("y8_parity_claimed") is True:
            errors.append(f"{name} claimed Y8 parity")
        if "teleport" in json.dumps(trace) or "force_kill" in json.dumps(trace):
            errors.append(f"{name} official trace contains teleport/force_kill")
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append(f"{name} must keep hold-to-aim assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/locomotion.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MOVE-LOCO-BASE",
            "ledger:RL-CAM-ARENA",
            "ledger:RL-CTRL-HOLD-AIM",
            "ledger:RL-MOVE-ROLL-DIVE",
            "does **not** claim Y8 parity",
            "apply_frames",
            "arena_fit",
        ):
            if needle not in docs:
                errors.append(f"locomotion docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF2-WP2" not in ledger:
        errors.append("ledger missing VF2-WP2 section")
    if errors:
        print("FAIL: Vault Fighters VF2-WP2 locomotion files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF2-WP2 locomotion files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} traces={len(REQUIRED_TRACES)} ledger={len(REQUIRED_LEDGER)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
