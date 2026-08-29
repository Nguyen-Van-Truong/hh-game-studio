#!/usr/bin/env python3
"""VF2-WP3 structure check: sprint/roll data, traces, honesty.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_sprint.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "sprint-roll.md"
LOCO = ROOT / "data" / "sim" / "locomotion.json"
FIGHTER = ROOT / "src" / "fighter.gd"
CASES = ROOT / "tests" / "sprint_cases.gd"
RUN_SPRINT = ROOT / "tests" / "run_sprint.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_sprint_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "sprint"
GATE_RUN_ID = "VF2WP3-20260829-ASIA-SAIGON-02"
FORBIDDEN_RUN_IDS = (
    "VF2WP3-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/sim/locomotion.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/visuals.gd",
    "tests/sprint_cases.gd",
    "tests/run_sprint.gd",
    "tests/pack_sprint_evidence.py",
)

REQUIRED_TRACES = (
    "double_tap_sprint.json",
    "tap_window_miss.json",
    "crouch_roll.json",
    "stamina_drain.json",
)

REQUIRED_LEDGER = (
    "RL-MOVE-SPRINT",
    "RL-MOVE-ROLL",
    "RL-MOVE-ROLL-DIVE",
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
    if "extinguish_fire" not in fighter:
        errors.append("fighter.gd must expose extinguish-fire hook")
    if "roll_started" not in fighter:
        errors.append("fighter.gd must track roll_started")
    if "_try_start_roll" not in fighter:
        errors.append("fighter.gd must implement _try_start_roll")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("sprint_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("sprint_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("sprint_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("sprint_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_tap",
        "outcome_stamina",
        "outcome_roll",
        "outcome_invuln",
        "outcome_dup",
        "outcome_live",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"sprint_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_sprint = RUN_SPRINT.read_text(encoding="utf-8") if RUN_SPRINT.is_file() else ""
    if GATE_RUN_ID not in run_sprint:
        errors.append(f"run_sprint.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_sprint:
            errors.append(f"run_sprint.gd must not reuse {banned}")
    for banned_infer in (
        '_count("window")',
        '_count("stamina")',
        '_count("roll ")',
        '_count("ROLL")',
        '_count("invuln")',
        '_count("projectile")',
        '_count("duplicat")',
        '_count("double-tap")',
    ):
        if banned_infer in run_sprint:
            errors.append(f"run_sprint must not infer banners from {banned_infer}")
    if "outcome_tap" not in run_sprint or "outcome_roll" not in run_sprint:
        errors.append("run_sprint banners must read structured outcomes")
    if "USED_APPLY_ATTEMPTED" not in run_sprint or "USED_APPLY_SUCCEEDED" not in run_sprint:
        errors.append("run_sprint must print attempted/succeeded apply counters")
    if "TAP_SOURCE=outcome_tap" not in run_sprint:
        errors.append("run_sprint TAP banner must cite outcome_tap")
    if not PACKER.is_file():
        errors.append("missing tests/pack_sprint_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "SprintCases" not in run_all:
        errors.append("run_all.gd must call SprintCases")
    if "outcome_tap" not in run_all:
        errors.append("run_all.gd sprint banner must read outcome_tap")
    if '"pass" if _sprint == "proven"' in run_all:
        errors.append("run_all.gd must not derive TAP/ROLL from _sprint==proven")
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
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("dive_class") != "assumption":
            errors.append("product dive must stay assumption")
        if payload.get("kick_class") != "assumption":
            errors.append("product kick must stay assumption")
        if payload.get("y8_parity_claimed") is True:
            errors.append("locomotion claimed Y8 parity")
        reserved = payload.get("reserved_not_shipped", [])
        if "roll" in reserved or "dive" in reserved or "kick" in reserved:
            errors.append("roll/dive/kick must be shipped")
        if "ledge" not in reserved:
            errors.append("ledge must stay reserved")
        move = payload.get("movement", {})
        for key in (
            "tap_window",
            "stamina_sprint_drain",
            "stamina_recover",
            "stamina_roll_cost",
            "roll_duration",
            "roll_invuln",
            "roll_size",
        ):
            if key not in move:
                errors.append(f"locomotion movement missing {key}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing sprint trace {name}")
            continue
        trace = json.loads(path.read_text(encoding="utf-8"))
        if trace.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append(f"{name} must set used_step_fixed false")
        if trace.get("y8_parity_claimed") is True:
            errors.append(f"{name} claimed Y8 parity")
        if "teleport" in json.dumps(trace) or "force_kill" in json.dumps(trace):
            errors.append(f"{name} official trace contains teleport/force_kill")
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append(f"{name} must keep hold-to-aim assumption")
        if "assumption" not in str(trace.get("roll", "")):
            errors.append(f"{name} must keep roll assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/sprint-roll.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MOVE-SPRINT",
            "ledger:RL-MOVE-ROLL",
            "ledger:RL-CTRL-HOLD-AIM",
            "does **not** claim Y8 parity",
            "apply_frames",
            "extinguish",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"sprint-roll docs missing {needle}")
        if GATE_RUN_ID not in docs:
            errors.append(f"sprint-roll docs must cite unique run {GATE_RUN_ID}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF2-WP3" not in ledger:
        errors.append("ledger missing VF2-WP3 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    if "| RL-MOVE-ROLL |" in ledger and "`observed`" in _row(ledger, "RL-MOVE-ROLL"):
        if "not observed" not in _row(ledger, "RL-MOVE-ROLL"):
            errors.append("RL-MOVE-ROLL must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF2-WP3 sprint/roll files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF2-WP3 sprint/roll files")
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
