#!/usr/bin/env python3
"""VF3-WP2 structure check: knockback, knockdown, invuln, disarm.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_reaction.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "reaction.md"
COMBAT = ROOT / "data" / "sim" / "combat.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
RESOLVER = ROOT / "src" / "sim" / "combat.gd"
CASES = ROOT / "tests" / "reaction_cases.gd"
RUN_REACT = ROOT / "tests" / "run_reaction.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_reaction_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "reaction"
GATE_RUN_ID = "VF3WP2-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF3WP2-20260829-ASIA-SAIGON-00",
    "VF3WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/sim/combat.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/pickup.gd",
    "tests/reaction_cases.gd",
    "tests/run_reaction.gd",
    "tests/pack_reaction_evidence.py",
)

REQUIRED_TRACES = (
    "reaction_knock.json",
    "reaction_down.json",
    "reaction_invuln.json",
    "reaction_disarm.json",
    "reaction_drop.json",
    "reaction_chain.json",
)

REQUIRED_LEDGER = (
    "RL-HIT-KNOCK",
    "RL-HIT-DOWN",
    "RL-HIT-INVULN",
    "RL-HIT-DISARM",
    "RL-SIM-FIXED-60",
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
    for needle in (
        "apply_impulse",
        "apply_knockdown",
        "grant_invuln_ticks",
        "disarm_gun",
        "reaction_locked",
        "getup_left",
        "invuln_ticks",
    ):
        if needle not in fighter:
            errors.append(f"fighter.gd must implement {needle}")
    resolver = RESOLVER.read_text(encoding="utf-8") if RESOLVER.is_file() else ""
    for needle in (
        "hit_invuln_ticks",
        "knockdown_ticks",
        "getup_ticks",
        "style_disarms",
        "valid_death_cause",
    ):
        if needle not in resolver:
            errors.append(f"combat.gd must expose {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "_drop_disarmed" not in session:
        errors.append("game_session must drop disarmed guns")
    if "_emit_reaction_feedback" not in session:
        errors.append("game_session must emit reaction entry/exit events")
    if "item_drop" not in session or "item_pickup" not in session:
        errors.append("game_session must log item_drop/item_pickup")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("reaction_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("reaction_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("reaction_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("reaction_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_damage",
        "outcome_knock",
        "outcome_air",
        "outcome_down",
        "outcome_getup",
        "outcome_invuln",
        "outcome_chain",
        "outcome_disarm",
        "outcome_drop",
        "outcome_death",
        "outcome_events",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"reaction_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_react = RUN_REACT.read_text(encoding="utf-8") if RUN_REACT.is_file() else ""
    if GATE_RUN_ID not in run_react:
        errors.append(f"run_reaction.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_react:
            errors.append(f"run_reaction.gd must not reuse {banned}")
    if "DAMAGE_SOURCE=outcome_damage" not in run_react:
        errors.append("run_reaction DAMAGE banner must cite outcome_damage")
    if "USED_APPLY_ATTEMPTED" not in run_react or "USED_APPLY_SUCCEEDED" not in run_react:
        errors.append("run_reaction must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_reaction_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "damage" not in packer or "disarm" not in packer:
            errors.append("packer verdict must require damage/disarm, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "ReactionCases" not in run_all:
        errors.append("run_all.gd must call ReactionCases")
    if "outcome_damage" not in run_all:
        errors.append("run_all.gd react banner must read outcome_damage")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not COMBAT.is_file():
        errors.append("missing data/sim/combat.json")
    else:
        payload = json.loads(COMBAT.read_text(encoding="utf-8"))
        if payload.get("knock_class") != "assumption":
            errors.append("knockback must stay assumption")
        if payload.get("down_class") != "assumption":
            errors.append("knockdown must stay assumption")
        if payload.get("invuln_class") != "assumption":
            errors.append("hit invuln must stay assumption")
        if payload.get("disarm_class") != "assumption":
            errors.append("disarm must stay assumption")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("y8_parity_claimed") is True:
            errors.append("combat claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("combat title must be Vault Fighters")
        reaction = payload.get("hit_reaction", {})
        if int(reaction.get("hit_invuln_ticks", 0)) < 1:
            errors.append("hit_invuln_ticks missing")
        if reaction.get("chain_lock_block") is not True:
            errors.append("chain_lock_block must be true")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing reaction trace {name}")
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
        if "assumption" not in str(trace.get("knock", "")):
            errors.append(f"{name} must keep knock assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/reaction.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-HIT-KNOCK",
            "ledger:RL-HIT-DOWN",
            "ledger:RL-HIT-INVULN",
            "ledger:RL-HIT-DISARM",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"reaction docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP2" not in ledger:
        errors.append("ledger missing VF3-WP2 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in ("RL-HIT-KNOCK", "RL-HIT-DOWN", "RL-HIT-INVULN", "RL-HIT-DISARM"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF3-WP2 reaction files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP2 reaction files")
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
