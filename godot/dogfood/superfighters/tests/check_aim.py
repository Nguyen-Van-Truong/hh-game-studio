#!/usr/bin/env python3
"""VF3-WP3 structure check: aim model and fire/release semantics.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_aim.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "aim.md"
AIM = ROOT / "data" / "sim" / "aim.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
BULLET = ROOT / "src" / "bullet.gd"
RESOLVER = ROOT / "src" / "sim" / "aim.gd"
CASES = ROOT / "tests" / "aim_cases.gd"
RUN_AIM = ROOT / "tests" / "run_aim.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_aim_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "aim"
GATE_RUN_ID = "VF3WP3-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF3WP3-20260829-ASIA-SAIGON-00",
    "VF3WP2-20260829-ASIA-SAIGON-01",
    "VF3WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/sim/aim.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/bullet.gd",
    "src/weapon_defs.gd",
    "tests/aim_cases.gd",
    "tests/run_aim.gd",
    "tests/pack_aim_evidence.py",
)

REQUIRED_TRACES = (
    "aim_hold.json",
    "aim_up.json",
    "aim_down.json",
    "fire_semi.json",
    "fire_edges.json",
    "fire_wall.json",
)

REQUIRED_LEDGER = (
    "RL-CTRL-HOLD-AIM",
    "RL-AIM-DIRS",
    "RL-FIRE-SEMI",
    "RL-FIRE-AUTO",
    "RL-FIRE-AMMO",
    "RL-FIRE-MUZZLE",
    "RL-FIRE-RECOIL",
    "RL-FIRE-BALLISTIC",
    "RL-FIRE-SWEEP",
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
        "_update_aim",
        "last_aim_dir",
        "fire_released",
        "want_fire",
        "_is_auto",
    ):
        if needle not in fighter:
            errors.append(f"fighter.gd must implement {needle}")
    resolver = RESOLVER.read_text(encoding="utf-8") if RESOLVER.is_file() else ""
    for needle in (
        "cadence_ticks",
        "muzzle_origin",
        "pellet_dir",
        "recoil_of",
        "projectile_mode",
    ):
        if needle not in resolver:
            errors.append(f"aim.gd must expose {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "_sweep_bullet" not in session:
        errors.append("game_session must sweep bullets continuously")
    if "muzzle_origin" not in session:
        errors.append("game_session must use data muzzle origin")
    if "cadence_ticks" not in session:
        errors.append("game_session must use data cadence")
    bullet = BULLET.read_text(encoding="utf-8") if BULLET.is_file() else ""
    if "last_pos" not in bullet or "predicted_pos" not in bullet:
        errors.append("bullet must keep last_pos and predicted_pos for sweep")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("aim_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("aim_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("aim_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("aim_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_hold",
        "outcome_dirs",
        "outcome_semi",
        "outcome_auto",
        "outcome_ammo",
        "outcome_muzzle",
        "outcome_recoil",
        "outcome_data",
        "outcome_sweep",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"aim_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_aim = RUN_AIM.read_text(encoding="utf-8") if RUN_AIM.is_file() else ""
    if GATE_RUN_ID not in run_aim:
        errors.append(f"run_aim.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_aim:
            errors.append(f"run_aim.gd must not reuse {banned}")
    if "HOLD_SOURCE=outcome_hold" not in run_aim:
        errors.append("run_aim HOLD banner must cite outcome_hold")
    if "USED_APPLY_ATTEMPTED" not in run_aim or "USED_APPLY_SUCCEEDED" not in run_aim:
        errors.append("run_aim must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_aim_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "semi" not in packer or "sweep" not in packer:
            errors.append("packer verdict must require semi/sweep, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "AimCases" not in run_all:
        errors.append("run_all.gd must call AimCases")
    if "outcome_hold" not in run_all:
        errors.append("run_all.gd aim banner must read outcome_hold")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not AIM.is_file():
        errors.append("missing data/sim/aim.json")
    else:
        payload = json.loads(AIM.read_text(encoding="utf-8"))
        if payload.get("hold_to_aim_class") != "assumption":
            errors.append("hold-to-aim must stay assumption")
        if payload.get("projectile_mode") != "ballistic":
            errors.append("projectile_mode must be ballistic")
        if payload.get("hitscan") is True:
            errors.append("hitscan must stay false")
        if payload.get("collision") != "swept":
            errors.append("collision must be swept")
        if payload.get("y8_parity_claimed") is True:
            errors.append("aim claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("aim title must be Vault Fighters")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        guns = payload.get("guns", {})
        pistol = guns.get("pistol", {})
        uzi = guns.get("uzi", {})
        shotgun = guns.get("shotgun", {})
        if pistol.get("auto") is True or uzi.get("auto") is not True:
            errors.append("pistol must be semi; uzi must be auto")
        if int(shotgun.get("pellets", 0)) < 3:
            errors.append("shotgun pellets must differ from pistol")
        if pistol.get("cadence_ticks") == uzi.get("cadence_ticks"):
            errors.append("pistol and uzi cadence must differ")
        if pistol.get("recoil") == shotgun.get("recoil"):
            errors.append("pistol and shotgun recoil must differ")
    saw_pressed = False
    saw_held = False
    saw_released = False
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing aim trace {name}")
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
        if '"pressed"' in dumped and "fire" in dumped:
            saw_pressed = True
        if '"held"' in dumped and "fire" in dumped:
            saw_held = True
        if '"released"' in dumped and "fire" in dumped:
            saw_released = True
    if not (saw_pressed and saw_held and saw_released):
        errors.append("aim traces must include fire pressed/held/released")
    if not DOCS.is_file():
        errors.append("missing docs/aim.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-CTRL-HOLD-AIM",
            "ledger:RL-AIM-DIRS",
            "ledger:RL-FIRE-SEMI",
            "ledger:RL-FIRE-AUTO",
            "ledger:RL-FIRE-SWEEP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"aim docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP3" not in ledger:
        errors.append("ledger missing VF3-WP3 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    hold_row = _row(ledger, "RL-CTRL-HOLD-AIM")
    if "`observed`" in hold_row and "not observed" not in hold_row and "Do **not** cite as observed" not in hold_row:
        errors.append("RL-CTRL-HOLD-AIM must not be marked observed")
    for rid in (
        "RL-AIM-DIRS",
        "RL-FIRE-SEMI",
        "RL-FIRE-AUTO",
        "RL-FIRE-AMMO",
        "RL-FIRE-MUZZLE",
        "RL-FIRE-RECOIL",
        "RL-FIRE-BALLISTIC",
        "RL-FIRE-SWEEP",
    ):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF3-WP3 aim files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP3 aim files")
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
