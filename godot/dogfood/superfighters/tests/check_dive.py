#!/usr/bin/env python3
"""VF2-WP4 structure check: dive/kick/fall data, traces, honesty.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_dive.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "dive-kick.md"
LOCO = ROOT / "data" / "sim" / "locomotion.json"
FIGHTER = ROOT / "src" / "fighter.gd"
CASES = ROOT / "tests" / "dive_cases.gd"
RUN_DIVE = ROOT / "tests" / "run_dive.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_dive_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "dive"
GATE_RUN_ID = "VF2WP4-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF2WP4-20260829-ASIA-SAIGON-00",
)

REQUIRED_SCRIPTS = (
    "src/sim/locomotion.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/visuals.gd",
    "tests/dive_cases.gd",
    "tests/run_dive.gd",
    "tests/pack_dive_evidence.py",
)

REQUIRED_TRACES = (
    "dive_sprint_crouch.json",
    "jump_kick.json",
    "dive_pit.json",
    "dive_rooftops.json",
    "dive_storage.json",
    "dive_hazardous.json",
)

REQUIRED_LEDGER = (
    "RL-MOVE-DIVE",
    "RL-MOVE-JUMP-KICK",
    "RL-MOVE-FALL",
    "RL-MOVE-ROLL-DIVE",
    "RL-MOVE-SPRINT",
    "RL-MOVE-ROLL",
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
    if "_try_start_dive" not in fighter:
        errors.append("fighter.gd must implement _try_start_dive")
    if "_try_start_kick" not in fighter:
        errors.append("fighter.gd must implement _try_start_kick")
    if "apply_knockdown" not in fighter:
        errors.append("fighter.gd must expose knockdown hook")
    if "fall_immune_landed" not in fighter:
        errors.append("fighter.gd must track dive fall immunity")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("dive_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("dive_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("dive_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("dive_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_dive",
        "outcome_kick",
        "outcome_tackle",
        "outcome_fall",
        "outcome_pit",
        "outcome_dodge",
        "outcome_invuln",
        "outcome_dist",
        "outcome_maps",
        "outcome_live",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"dive_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_dive = RUN_DIVE.read_text(encoding="utf-8") if RUN_DIVE.is_file() else ""
    if GATE_RUN_ID not in run_dive:
        errors.append(f"run_dive.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_dive:
            errors.append(f"run_dive.gd must not reuse {banned}")
    for banned_infer in (
        '_count("dive")',
        '_count("kick")',
        '_count("tackle")',
        '_count("fall")',
        '_count("invuln")',
        '_count("DIVE")',
        '_count("KICK")',
        '_count("PIT")',
    ):
        if banned_infer in run_dive:
            errors.append(f"run_dive must not infer banners from {banned_infer}")
    if "outcome_dive" not in run_dive or "outcome_kick" not in run_dive:
        errors.append("run_dive banners must read structured outcomes")
    if "USED_APPLY_ATTEMPTED" not in run_dive or "USED_APPLY_SUCCEEDED" not in run_dive:
        errors.append("run_dive must print attempted/succeeded apply counters")
    if "DIVE_SOURCE=outcome_dive" not in run_dive:
        errors.append("run_dive DIVE banner must cite outcome_dive")
    if not PACKER.is_file():
        errors.append("missing tests/pack_dive_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "DiveCases" not in run_all:
        errors.append("run_all.gd must call DiveCases")
    if "outcome_dive" not in run_all:
        errors.append("run_all.gd dive banner must read outcome_dive")
    if '"pass" if _dive == "proven"' in run_all:
        errors.append("run_all.gd must not derive DIVE from _dive==proven")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not LOCO.is_file():
        errors.append("missing data/sim/locomotion.json")
    else:
        payload = json.loads(LOCO.read_text(encoding="utf-8"))
        if payload.get("sprint_class") != "assumption":
            errors.append("sprint must stay assumption")
        if payload.get("roll_class") != "assumption":
            errors.append("roll must stay assumption")
        if payload.get("hold_to_aim_class") != "assumption":
            errors.append("hold-to-aim must stay assumption")
        if payload.get("dive_class") != "assumption":
            errors.append("product dive must stay assumption")
        if payload.get("kick_class") != "assumption":
            errors.append("product kick must stay assumption")
        if payload.get("fall_class") != "assumption":
            errors.append("product fall must stay assumption")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("y8_parity_claimed") is True:
            errors.append("locomotion claimed Y8 parity")
        reserved = payload.get("reserved_not_shipped", [])
        if "roll" in reserved or "dive" in reserved or "kick" in reserved:
            errors.append("roll/dive/kick must be shipped")
        if "ledge" not in reserved:
            errors.append("ledge must stay reserved")
        move = payload.get("movement", {})
        for key in (
            "stamina_dive_cost",
            "dive_duration",
            "dive_invuln",
            "dive_size",
            "kick_impulse_x",
            "kick_impulse_y",
            "fall_drop_min",
            "knockdown_time",
        ):
            if key not in move:
                errors.append(f"locomotion movement missing {key}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing dive trace {name}")
            continue
        raw = path.read_text(encoding="utf-8")
        trace = json.loads(raw)
        if trace.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append(f"{name} must set used_step_fixed false")
        if trace.get("y8_parity_claimed") is True:
            errors.append(f"{name} claimed Y8 parity")
        if "teleport" in raw or "force_kill" in raw:
            errors.append(f"{name} official trace contains teleport/force_kill")
        if "assumption" not in str(trace.get("dive", "")):
            errors.append(f"{name} must keep dive assumption")
        if "assumption" not in str(trace.get("kick", "")):
            errors.append(f"{name} must keep kick assumption")
        if "assumption" not in str(trace.get("sprint", "")):
            errors.append(f"{name} must keep sprint assumption")
        if "assumption" not in str(trace.get("roll", "")):
            errors.append(f"{name} must keep roll assumption")
        if "unavailable" not in str(trace.get("roll_dive", "")):
            errors.append(f"{name} must keep Y8 roll/dive unavailable")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/dive-kick.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MOVE-DIVE",
            "ledger:RL-MOVE-JUMP-KICK",
            "ledger:RL-MOVE-FALL",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"dive-kick docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF2-WP4" not in ledger:
        errors.append("ledger missing VF2-WP4 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in ("RL-MOVE-DIVE", "RL-MOVE-JUMP-KICK", "RL-MOVE-FALL"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF2-WP4 dive/kick files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF2-WP4 dive/kick files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} traces={len(REQUIRED_TRACES)} ledger={len(REQUIRED_LEDGER)}")
    print(f"  run_id={GATE_RUN_ID}")
    return 0


def _row(text: str, rid: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {rid} "):
            return line
    return ""


if __name__ == "__main__":
    sys.exit(main())
