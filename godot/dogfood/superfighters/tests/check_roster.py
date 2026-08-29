#!/usr/bin/env python3
"""VF3-WP5 structure check: data-driven weapon roster / inventory.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_roster.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "roster.md"
ROSTER = ROOT / "data" / "weapons" / "roster.json"
SCHEMA = ROOT / "data" / "weapons" / "schema.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
SNAPSHOT = ROOT / "src" / "sim" / "sim_snapshot.gd"
HUD = ROOT / "src" / "hud.gd"
CASES = ROOT / "tests" / "roster_cases.gd"
RUN_ROSTER = ROOT / "tests" / "run_roster.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_roster_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "roster"
GATE_RUN_ID = "VF3WP5-20260829-ASIA-SAIGON-02"
FORBIDDEN_RUN_IDS = (
    "VF3WP5-20260829-ASIA-SAIGON-01",
    "VF3WP5-20260829-ASIA-SAIGON-00",
    "VF3WP4-20260829-ASIA-SAIGON-01",
    "VF3WP3-20260829-ASIA-SAIGON-01",
    "VF3WP2-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/data/weapons/roster.gd",
    "src/data/weapons/inventory.gd",
    "src/weapon_defs.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/hud.gd",
    "tests/roster_cases.gd",
    "tests/run_roster.gd",
    "tests/pack_roster_evidence.py",
)

REQUIRED_TRACES = (
    "roster_idle.json",
    "roster_keep.json",
    "roster_melee.json",
    "roster_throw.json",
)

REQUIRED_LEDGER = (
    "RL-ITEM-SLOTS-4",
    "RL-ITEM-ROSTER",
    "RL-ITEM-PICK-SLOT",
    "RL-ITEM-KEEP-GUN",
    "RL-ITEM-AMMO-RELOAD",
    "RL-SIM-FIXED-60",
)

REQUIRED_IDS = (
    "fists",
    "pipe",
    "knife",
    "baton",
    "pistol",
    "uzi",
    "shotgun",
    "rifle",
    "launcher",
    "grenade",
    "cinder",
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
        "explosive_id",
        "power_id",
        "power_ammo",
        "reload_left",
        "_Inv.give",
    ):
        if needle not in fighter:
            errors.append(f"fighter.gd must implement {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "dropped_on_pickup" not in session:
        errors.append("game_session must drop the replaced slot item")
    if "drop_held_slot" not in session:
        errors.append("game_session must expose drop_held_slot for singleton eject")
    drop_fn = session.split("func _drop_specific", 1)[-1].split("func ", 1)[0]
    if 'pid == "fists"' in drop_fn:
        errors.append("game_session _drop_specific must allow fists to drop as a world pickup")
    snapshot = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.is_file() else ""
    for needle in ('"explosive"', '"power"', '"reserve"', '"reload"'):
        if needle not in snapshot:
            errors.append(f"sim_snapshot fighter row must include {needle}")
    if "fighters" not in snapshot or "hash_payload" not in snapshot:
        errors.append("sim_snapshot must hash fighter rows")
    hud = HUD.read_text(encoding="utf-8") if HUD.is_file() else ""
    if "power" not in hud or "grenades" not in hud:
        errors.append("HUD must show firearm/explosive/power slots")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("roster_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("roster_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("roster_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("roster_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_schema",
        "outcome_spawn",
        "outcome_equip",
        "outcome_attack",
        "outcome_drop",
        "outcome_serialize",
        "outcome_keep",
        "outcome_ammo",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"roster_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    if "validate_payload" not in cases:
        errors.append("roster_cases must reject-invalid via validate_payload")
    if "_slot_restored" not in cases or "_uids_for" not in cases:
        errors.append("roster_cases must prove per-id drop uid and serialize restore")
    if "_world_ids" in cases:
        errors.append("roster_cases must spawn every roster id including fists")
    if re.search(r"p1\.reserve\s*=\s*8", cases) or re.search(r"p1\.mag_size\s*=\s*8", cases):
        errors.append("rifle reload must not force-set reserve/mag")
    if "p1._start_reload()" in cases:
        errors.append("rifle reload must use roster-copied reserve, not a poked _start_reload")
    if "roster-copied" not in cases and "roster reserve" not in cases:
        errors.append("ammo case must cite roster-copied reserve")
    roster_src = (ROOT / "src" / "data" / "weapons" / "roster.gd").read_text(encoding="utf-8")
    if "validate_payload" not in roster_src or "replacement_of" not in roster_src:
        errors.append("roster.gd must expose validate_payload and replacement_of")
    inv_src = (ROOT / "src" / "data" / "weapons" / "inventory.gd").read_text(encoding="utf-8")
    if "eject_slot" not in inv_src:
        errors.append("inventory.gd must expose eject_slot")
    if 'melee_id != "fists"' in inv_src:
        errors.append("inventory must allow fists to drop when replaced")
    run_roster = RUN_ROSTER.read_text(encoding="utf-8") if RUN_ROSTER.is_file() else ""
    if GATE_RUN_ID not in run_roster:
        errors.append(f"run_roster.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_roster:
            errors.append(f"run_roster.gd must not reuse {banned}")
    if "SCHEMA_SOURCE=outcome_schema" not in run_roster:
        errors.append("run_roster SCHEMA banner must cite outcome_schema")
    if "USED_APPLY_ATTEMPTED" not in run_roster or "USED_APPLY_SUCCEEDED" not in run_roster:
        errors.append("run_roster must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_roster_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "keep" not in packer or "serialize" not in packer:
            errors.append("packer verdict must require keep/serialize, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "RosterCases" not in run_all:
        errors.append("run_all.gd must call RosterCases")
    if "outcome_schema" not in run_all or "HH_VF_ROSTER" not in run_all:
        errors.append("run_all.gd roster banner must read outcome_schema")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not SCHEMA.is_file():
        errors.append("missing data/weapons/schema.json")
    if not ROSTER.is_file():
        errors.append("missing data/weapons/roster.json")
    else:
        payload = json.loads(ROSTER.read_text(encoding="utf-8"))
        if payload.get("slots_class") != "assumption":
            errors.append("slots must stay assumption")
        if payload.get("y8_parity_claimed") is True:
            errors.append("roster claimed Y8 parity")
        if payload.get("original_exact_numbers_claimed") is True:
            errors.append("roster claimed original exact numbers")
        if payload.get("title") != "Vault Fighters":
            errors.append("roster title must be Vault Fighters")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        pool = payload.get("spawn_pool", [])
        if "fists" not in pool:
            errors.append("spawn_pool must include fists")
        items = payload.get("items", {})
        for rid in REQUIRED_IDS:
            if rid not in items:
                errors.append(f"roster missing required id {rid}")
        slots = {items[rid].get("slot") for rid in items}
        if not {"melee", "firearm", "explosive", "power"}.issubset(slots):
            errors.append("roster must include melee/firearm/explosive/power")
        for rid, spec in items.items():
            name = str(spec.get("name", ""))
            if re.search(r"Superfighters|Super Fighter", name):
                errors.append(f"{rid} display name uses Superfighters trademark")
            for field in ("ammo", "reload_ticks", "cooldown", "weight", "icon"):
                if field not in spec:
                    errors.append(f"{rid} missing {field}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing roster trace {name}")
            continue
        raw = path.read_text(encoding="utf-8")
        trace = json.loads(raw)
        if trace.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append(f"{name} must set used_step_fixed false")
        if trace.get("y8_parity_claimed") is True:
            errors.append(f"{name} claimed Y8 parity")
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append(f"{name} must keep hold-to-aim assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        if "teleport" in raw or "force_kill" in raw:
            errors.append(f"{name} official trace contains teleport/force_kill")
    if not DOCS.is_file():
        errors.append("missing docs/roster.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-ITEM-SLOTS-4",
            "ledger:RL-ITEM-ROSTER",
            "ledger:RL-ITEM-PICK-SLOT",
            "ledger:RL-ITEM-KEEP-GUN",
            "ledger:RL-ITEM-AMMO-RELOAD",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"roster docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP5" not in ledger:
        errors.append("ledger missing VF3-WP5 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in (
        "RL-ITEM-SLOTS-4",
        "RL-ITEM-ROSTER",
        "RL-ITEM-PICK-SLOT",
        "RL-ITEM-KEEP-GUN",
        "RL-ITEM-AMMO-RELOAD",
    ):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    if errors:
        print("FAIL: Vault Fighters VF3-WP5 roster files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP5 roster files")
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
