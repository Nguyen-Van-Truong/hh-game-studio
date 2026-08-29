#!/usr/bin/env python3
"""VF2-WP5 structure check: ladder/ledge/drop data, traces, honesty.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_traversal.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "traversal.md"
TRAV = ROOT / "data" / "sim" / "traversal.json"
LOCO = ROOT / "data" / "sim" / "locomotion.json"
FIGHTER = ROOT / "src" / "fighter.gd"
CASES = ROOT / "tests" / "traversal_cases.gd"
RUN_TRAV = ROOT / "tests" / "run_traversal.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_traversal_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "traversal"
GATE_RUN_ID = "VF2WP5-20260829-ASIA-SAIGON-03"
FORBIDDEN_RUN_IDS = (
    "VF2WP5-20260829-ASIA-SAIGON-00",
    "VF2WP5-20260829-ASIA-SAIGON-01",
    "VF2WP5-20260829-ASIA-SAIGON-02",
)

REQUIRED_SCRIPTS = (
    "src/sim/traversal.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/visuals.gd",
    "tests/traversal_cases.gd",
    "tests/run_traversal.gd",
    "tests/pack_traversal_evidence.py",
)

REQUIRED_TRACES = (
    "ladder_up_down.json",
    "ladder_block.json",
    "ledge_recover.json",
    "drop_through.json",
    "cross_dirs.json",
    "map_rooftops.json",
    "map_storage.json",
    "map_police.json",
    "map_hazardous.json",
)

REQUIRED_LEDGER = (
    "RL-MOVE-LADDER",
    "RL-MOVE-LEDGE",
    "RL-MOVE-DROP",
    "RL-MOVE-ROLL-DIVE",
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
    if "_tick_ladder" not in fighter:
        errors.append("fighter.gd must implement _tick_ladder")
    if "_try_ledge_grab" not in fighter:
        errors.append("fighter.gd must implement _try_ledge_grab")
    if "_tick_drop_through" not in fighter:
        errors.append("fighter.gd must implement _tick_drop_through")
    if "drop_hold" not in fighter:
        errors.append("drop-through must arm on crouch hold (drop_hold)")
    if "_apply_ledge_motion" not in fighter:
        errors.append("fighter.gd must step ledge recover via _apply_ledge_motion")
    if "global_position = hang_stand" in fighter:
        errors.append("ledge recover must not hard-assign hang_stand")
    if "global_position = hang_anchor" in fighter:
        errors.append("ledge grab must not hard-assign hang_anchor")
    if "_ledge_recover_target" not in fighter or "_ledge_recover_boarded" not in fighter:
        errors.append("ledge recover must path outside the lip then board")
    if "dist < float(Maps.TILE)" in fighter:
        errors.append("ledge recover must not re-arm only while leftover < TILE")
    arena = (ROOT / "src" / "arena.gd").read_text(encoding="utf-8")
    if "set_physics_layer_collision_layer(1, Maps.COL_PLATFORM)" not in arena:
        errors.append("arena must put one-way tiles on COL_PLATFORM physics layer 1")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if "or session.ledger.count_kind(\"drop_through\")" in cases:
        errors.append("DROP must not pass on drop_through event-only")
    if "x < p1.global_position.x + 40" in cases or "x < x0 + 80" in cases:
        errors.append("DIRS must not use tautological left checks")
    if "down_ok: bool = not p1.dead" in cases:
        errors.append("DIRS must not treat not-dead as down")
    if "dx_right" not in cases or "dy_down" not in cases:
        errors.append("DIRS must record real dx/dy displacements")
    if "events_all" not in cases:
        errors.append("traversal_cases must accumulate events_all")
    if "fixtures_only" not in cases:
        errors.append("MAPS must use fixtures_only, not stage pass")
    if "recover_max_step" not in cases:
        errors.append("LEDGE must measure recover_max_step")
    if "y1 < y_hang - 2.0 or p1.is_on_floor()" in cases:
        errors.append("LEDGE must not pass on rise-only theater")
    if "stand_dist" not in cases or "idle_wedged" not in cases or "boarded" not in cases:
        errors.append("LEDGE must require on_floor board, stand_dist, and idle not wedged")
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("traversal_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("traversal_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("traversal_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("traversal_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_ladder",
        "outcome_ledge",
        "outcome_drop",
        "outcome_block",
        "outcome_dirs",
        "outcome_maps",
        "outcome_stuck",
        "outcome_contact",
        "outcome_live",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"traversal_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_trav = RUN_TRAV.read_text(encoding="utf-8") if RUN_TRAV.is_file() else ""
    if GATE_RUN_ID not in run_trav:
        errors.append(f"run_traversal.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_trav:
            errors.append(f"run_traversal.gd must not reuse {banned}")
    if "outcome_ladder" not in run_trav or "outcome_ledge" not in run_trav:
        errors.append("run_traversal banners must read structured outcomes")
    if "USED_APPLY_ATTEMPTED" not in run_trav or "USED_APPLY_SUCCEEDED" not in run_trav:
        errors.append("run_traversal must print attempted/succeeded apply counters")
    if "LADDER_SOURCE=outcome_ladder" not in run_trav:
        errors.append("run_traversal LADDER banner must cite outcome_ladder")
    if "STAGE_NAV=not_claimed" not in run_trav:
        errors.append("run_traversal MAPS banner must say STAGE_NAV=not_claimed")
    if not PACKER.is_file():
        errors.append("missing tests/pack_traversal_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "TraversalCases" not in run_all:
        errors.append("run_all.gd must call TraversalCases")
    if "outcome_ladder" not in run_all:
        errors.append("run_all.gd traverse banner must read outcome_ladder")
    if "fixtures_only" not in run_all:
        errors.append("run_all.gd must accept MAPS=fixtures_only")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not TRAV.is_file():
        errors.append("missing data/sim/traversal.json")
    else:
        payload = json.loads(TRAV.read_text(encoding="utf-8"))
        if payload.get("ladder_class") != "assumption":
            errors.append("ladder must stay assumption")
        if payload.get("ledge_class") != "assumption":
            errors.append("ledge must stay assumption")
        if payload.get("drop_class") != "assumption":
            errors.append("drop must stay assumption")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("y8_parity_claimed") is True:
            errors.append("traversal claimed Y8 parity")
        if payload.get("input_ledge_reserved") is not True:
            errors.append("InputFrame ledge must stay reserved")
        movement = payload.get("movement", {})
        if not isinstance(movement, dict) or movement.get("recover_mode") != "velocity_step":
            errors.append("traversal recover_mode must be velocity_step")
        if not isinstance(movement, dict) or movement.get("recover_path") != "outside_then_board":
            errors.append("traversal recover_path must be outside_then_board")
        if not isinstance(movement, dict) or float(movement.get("recover_board_eps", 0) or 0) > 8.0001:
            errors.append("recover_board_eps must stay a small stand epsilon")
        if float(movement.get("drop_fall_min", 0) or 0) < 8.0:
            errors.append("drop_fall_min must be >= 8")
        if float(movement.get("drop_hold_min", 0) or 0) < 0.22:
            errors.append("drop_hold_min must stay above official crouch-trace length")
        fixtures = payload.get("fixtures", {})
        for name in ("fx_ladder", "fx_block", "fx_ledge", "fx_drop", "fx_cross"):
            if name not in fixtures:
                errors.append(f"missing fixture {name}")
    if LOCO.is_file():
        loco = json.loads(LOCO.read_text(encoding="utf-8"))
        reserved = loco.get("reserved_not_shipped", [])
        if "ledge" in reserved:
            errors.append("locomotion reserved must not keep shipped ledge")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing traversal trace {name}")
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
        if "assumption" not in str(trace.get("ladder", "")):
            errors.append(f"{name} must keep ladder assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
    if not DOCS.is_file():
        errors.append("missing docs/traversal.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MOVE-LADDER",
            "ledger:RL-MOVE-LEDGE",
            "ledger:RL-MOVE-DROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"traversal docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF2-WP5" not in ledger:
        errors.append("ledger missing VF2-WP5 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in ("RL-MOVE-LADDER", "RL-MOVE-LEDGE", "RL-MOVE-DROP"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF2-WP5 traversal files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF2-WP5 traversal files")
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
