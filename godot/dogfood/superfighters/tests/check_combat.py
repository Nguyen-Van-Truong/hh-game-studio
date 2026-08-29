#!/usr/bin/env python3
"""VF3-WP1 structure check: melee phases, hitboxes, honesty.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_combat.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "combat.md"
COMBAT = ROOT / "data" / "sim" / "combat.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
RESOLVER = ROOT / "src" / "sim" / "combat.gd"
CASES = ROOT / "tests" / "combat_cases.gd"
RUN_COMBAT = ROOT / "tests" / "run_combat.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_combat_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "combat"
GATE_RUN_ID = "VF3WP1-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF3WP1-20260829-ASIA-SAIGON-00",
)

REQUIRED_SCRIPTS = (
    "src/sim/combat.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/hud.gd",
    "src/visuals.gd",
    "tests/combat_cases.gd",
    "tests/run_combat.gd",
    "tests/pack_combat_evidence.py",
)

REQUIRED_TRACES = (
    "melee_hit.json",
    "melee_miss.json",
    "melee_behind.json",
    "melee_above.json",
    "melee_below.json",
    "melee_once.json",
    "melee_crouch.json",
    "melee_kick.json",
)

REQUIRED_LEDGER = (
    "RL-HIT-PHASES",
    "RL-HIT-BOX",
    "RL-HIT-FF",
    "RL-HIT-HITSTOP",
    "RL-MOVE-JUMP-KICK",
    "RL-CTRL-HOLD-AIM",
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
    if "begin_attack" not in fighter:
        errors.append("fighter.gd must implement begin_attack")
    if "_advance_attack" not in fighter:
        errors.append("fighter.gd must implement _advance_attack")
    if 'attack_phase = "startup"' not in fighter:
        errors.append("fighter must enter startup, not same-tick hit")
    resolver = RESOLVER.read_text(encoding="utf-8") if RESOLVER.is_file() else ""
    if "hitbox_rect" not in resolver or "hurtbox_rect" not in resolver:
        errors.append("combat.gd must expose hitbox/hurtbox rects")
    if "classify_miss" not in resolver:
        errors.append("combat.gd must classify miss geometry")
    if "allows_hit" not in resolver:
        errors.append("combat.gd must enforce friendly-fire")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "_resolve_hitbox" not in session:
        errors.append("game_session must resolve overlap, not distance melee")
    if "func _do_melee" in session:
        errors.append("game_session must not keep _do_melee distance check")
    if "distance_to" in session and "_resolve_hitbox" in session:
        # pickup / dive tackle may still use distance; melee resolve must not
        hitbox_fn = session.split("func _resolve_hitbox", 1)[-1].split("func ", 1)[0]
        if "distance_to" in hitbox_fn or "absf(delta.x)" in hitbox_fn:
            errors.append("_resolve_hitbox must not be a distance check")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if "or session.ledger.count_kind" in cases:
        errors.append("HIT/MISS must not pass on event-only count_kind")
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("combat_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("combat_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("combat_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("combat_cases must prove live InputFrame stepping")
    if "classify_miss" not in cases:
        errors.append("MISS geometry must use classify_miss")
    if 'press_phase' not in cases or '"startup"' not in cases:
        errors.append("HIT must require press tick is startup")
    if "hp0" not in cases or "damage" not in cases:
        errors.append("HIT must record HP delta, not events alone")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_hit",
        "outcome_miss",
        "outcome_behind",
        "outcome_above",
        "outcome_below",
        "outcome_once",
        "outcome_snap",
        "outcome_pause",
        "outcome_live",
        "outcome_replay",
        "outcome_phases",
        "outcome_reach",
        "outcome_ff",
        "outcome_hitstop",
        "outcome_crouch",
        "outcome_kick",
        "events_all",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"combat_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_combat = RUN_COMBAT.read_text(encoding="utf-8") if RUN_COMBAT.is_file() else ""
    if GATE_RUN_ID not in run_combat:
        errors.append(f"run_combat.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_combat:
            errors.append(f"run_combat.gd must not reuse {banned}")
    if "HIT_SOURCE=outcome_hit" not in run_combat:
        errors.append("run_combat HIT banner must cite outcome_hit")
    if "USED_APPLY_ATTEMPTED" not in run_combat or "USED_APPLY_SUCCEEDED" not in run_combat:
        errors.append("run_combat must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_combat_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "damage" not in packer or "hp0" not in packer:
            errors.append("packer verdict must require HP/geometry, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "CombatCases" not in run_all:
        errors.append("run_all.gd must call CombatCases")
    if "outcome_hit" not in run_all:
        errors.append("run_all.gd melee banner must read outcome_hit")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not COMBAT.is_file():
        errors.append("missing data/sim/combat.json")
    else:
        payload = json.loads(COMBAT.read_text(encoding="utf-8"))
        if payload.get("phases_class") != "assumption":
            errors.append("phases must stay assumption")
        if payload.get("hitbox_class") != "assumption":
            errors.append("hitbox must stay assumption")
        if payload.get("ff_class") != "assumption":
            errors.append("friendly-fire must stay assumption")
        if payload.get("hitstop_class") != "assumption":
            errors.append("hitstop must stay assumption")
        if payload.get("hitstop_clock") != "presentation_only":
            errors.append("hitstop must stay presentation_only")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("y8_parity_claimed") is True:
            errors.append("combat claimed Y8 parity")
        if payload.get("one_hit_per_window") is not True:
            errors.append("one_hit_per_window must be true")
        if payload.get("title") != "Vault Fighters":
            errors.append("combat title must be Vault Fighters")
        fixtures = payload.get("fixtures", {})
        for name in (
            "fx_melee_close",
            "fx_melee_far",
            "fx_melee_behind",
            "fx_melee_above",
            "fx_melee_below",
            "fx_melee_mid",
        ):
            if name not in fixtures:
                errors.append(f"missing fixture {name}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing combat trace {name}")
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
        if "assumption" not in str(trace.get("phases", "")):
            errors.append(f"{name} must keep phases assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/combat.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-HIT-PHASES",
            "ledger:RL-HIT-BOX",
            "ledger:RL-HIT-FF",
            "ledger:RL-HIT-HITSTOP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"combat docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP1" not in ledger:
        errors.append("ledger missing VF3-WP1 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in ("RL-HIT-PHASES", "RL-HIT-BOX", "RL-HIT-FF", "RL-HIT-HITSTOP"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF3-WP1 combat files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP1 combat files")
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
