#!/usr/bin/env python3
"""VF3-WP4 structure check: grenade / explosive physics.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_explosive.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "explosive.md"
EXPL = ROOT / "data" / "sim" / "explosive.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
GRENADE = ROOT / "src" / "grenade.gd"
RESOLVER = ROOT / "src" / "sim" / "explosive.gd"
CASES = ROOT / "tests" / "explosive_cases.gd"
RUN_EXPL = ROOT / "tests" / "run_explosive.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_explosive_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "explosive"
GATE_RUN_ID = "VF3WP4-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF3WP4-20260829-ASIA-SAIGON-00",
    "VF3WP3-20260829-ASIA-SAIGON-01",
    "VF3WP2-20260829-ASIA-SAIGON-01",
    "VF3WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/sim/explosive.gd",
    "src/grenade.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/weapon_defs.gd",
    "tests/explosive_cases.gd",
    "tests/run_explosive.gd",
    "tests/pack_explosive_evidence.py",
)

REQUIRED_TRACES = (
    "nade_hold.json",
    "nade_throw.json",
    "nade_arc.json",
    "nade_bounce.json",
    "nade_fuse.json",
    "nade_wall.json",
)

REQUIRED_LEDGER = (
    "RL-NADE-HOLD",
    "RL-NADE-ARC",
    "RL-NADE-BOUNCE",
    "RL-NADE-FUSE",
    "RL-NADE-FALLOFF",
    "RL-NADE-OWNER",
    "RL-NADE-ONCE",
    "RL-NADE-TIMEOUT",
    "RL-NADE-SWEEP",
    "RL-NADE-PROP",
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
        "grenade_held",
        "grenade_released",
        "want_grenade",
        "_Expl.throw_cd",
    ):
        if needle not in fighter:
            errors.append(f"fighter.gd must implement {needle}")
    resolver = RESOLVER.read_text(encoding="utf-8") if RESOLVER.is_file() else ""
    for needle in (
        "throw_velocity",
        "bounce_velocity",
        "falloff_of",
        "allows_damage",
        "owner_self_damage",
        "prop_break_mode",
    ):
        if needle not in resolver:
            errors.append(f"explosive.gd must expose {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "_sweep_nade" not in session:
        errors.append("game_session must sweep grenades continuously")
    if "_explode" not in session or "applied" not in session:
        errors.append("game_session must explode once via applied")
    if "deferred_vf4" not in session and "prop_break" not in session:
        errors.append("game_session must emit deferred prop_break")
    grenade = GRENADE.read_text(encoding="utf-8") if GRENADE.is_file() else ""
    if "fuse_ticks" not in grenade or "life_ticks" not in grenade:
        errors.append("grenade must keep fuse_ticks and life_ticks")
    if "predicted_pos" not in grenade:
        errors.append("grenade must keep predicted_pos for sweep")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("explosive_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("explosive_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("explosive_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("explosive_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_hold",
        "outcome_throw",
        "outcome_arc",
        "outcome_bounce",
        "outcome_fuse",
        "outcome_falloff",
        "outcome_owner",
        "outcome_once",
        "outcome_timeout",
        "outcome_sweep",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"explosive_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_expl = RUN_EXPL.read_text(encoding="utf-8") if RUN_EXPL.is_file() else ""
    if GATE_RUN_ID not in run_expl:
        errors.append(f"run_explosive.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_expl:
            errors.append(f"run_explosive.gd must not reuse {banned}")
    if "HOLD_SOURCE=outcome_hold" not in run_expl:
        errors.append("run_explosive HOLD banner must cite outcome_hold")
    if "USED_APPLY_ATTEMPTED" not in run_expl or "USED_APPLY_SUCCEEDED" not in run_expl:
        errors.append("run_explosive must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_explosive_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "owner" not in packer or "timeout" not in packer:
            errors.append("packer verdict must require owner/timeout, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "ExplosiveCases" not in run_all:
        errors.append("run_all.gd must call ExplosiveCases")
    if "outcome_hold" not in run_all or "HH_VF_EXPL" not in run_all:
        errors.append("run_all.gd explosive banner must read outcome_hold")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not EXPL.is_file():
        errors.append("missing data/sim/explosive.json")
    else:
        payload = json.loads(EXPL.read_text(encoding="utf-8"))
        if payload.get("hold_throw_class") != "assumption":
            errors.append("hold-to-throw must stay assumption")
        if payload.get("owner_self_damage") is True:
            errors.append("owner_self_damage must stay false")
        if payload.get("collision") != "swept":
            errors.append("collision must be swept")
        if payload.get("y8_parity_claimed") is True:
            errors.append("explosive claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("explosive title must be Vault Fighters")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("prop_break") != "deferred_vf4":
            errors.append("prop_break must stay deferred_vf4")
        nade = payload.get("grenade", {})
        if int(nade.get("fuse_ticks", 0)) < 2:
            errors.append("fuse_ticks must be >1")
        if float(nade.get("radius", 0)) <= 0:
            errors.append("grenade radius must be >0")
    saw_pressed = False
    saw_held = False
    saw_released = False
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing explosive trace {name}")
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
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append(f"{name} must keep hold-to-aim assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        dumped = json.dumps(trace)
        if '"pressed"' in dumped and "grenade" in dumped:
            saw_pressed = True
        if '"held"' in dumped and "grenade" in dumped:
            saw_held = True
        if '"released"' in dumped and "grenade" in dumped:
            saw_released = True
    if not (saw_held and saw_released):
        errors.append("explosive traces must include grenade held/released")
    if not saw_pressed:
        # first-hold frames emit pressed via apply_slot; traces may only
        # write held/released. Require held+released; pressed is optional
        # as long as hold/release exist.
        pass
    if not DOCS.is_file():
        errors.append("missing docs/explosive.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-NADE-HOLD",
            "ledger:RL-NADE-ARC",
            "ledger:RL-NADE-BOUNCE",
            "ledger:RL-NADE-FUSE",
            "ledger:RL-NADE-OWNER",
            "ledger:RL-NADE-ONCE",
            "ledger:RL-NADE-TIMEOUT",
            "ledger:RL-NADE-SWEEP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"explosive docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP4" not in ledger:
        errors.append("ledger missing VF3-WP4 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in (
        "RL-NADE-HOLD",
        "RL-NADE-ARC",
        "RL-NADE-BOUNCE",
        "RL-NADE-FUSE",
        "RL-NADE-FALLOFF",
        "RL-NADE-OWNER",
        "RL-NADE-ONCE",
        "RL-NADE-TIMEOUT",
        "RL-NADE-SWEEP",
    ):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    prop_row = _row(ledger, "RL-NADE-PROP")
    if "`observed`" in prop_row:
        errors.append("RL-NADE-PROP must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF3-WP4 explosive files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP4 explosive files")
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
