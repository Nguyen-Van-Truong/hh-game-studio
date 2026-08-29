#!/usr/bin/env python3
"""VF3-WP6 structure check: chaos / combat balance harness.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_balance.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "balance.md"
BALANCE = ROOT / "data" / "sim" / "balance.json"
AIM = ROOT / "data" / "sim" / "aim.json"
ROSTER = ROOT / "data" / "weapons" / "roster.json"
FIGHTER = ROOT / "src" / "fighter.gd"
SESSION = ROOT / "src" / "game_session.gd"
CASES = ROOT / "tests" / "balance_cases.gd"
RUN_BAL = ROOT / "tests" / "run_balance.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_balance_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "balance"
GATE_RUN_ID = "VF3WP6-20260829-ASIA-SAIGON-03"
FORBIDDEN_RUN_IDS = (
    "VF3WP6-20260829-ASIA-SAIGON-02",
    "VF3WP6-20260829-ASIA-SAIGON-01",
    "VF3WP5-20260829-ASIA-SAIGON-02",
    "VF3WP5-20260829-ASIA-SAIGON-01",
    "VF3WP4-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/sim/balance.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "tests/balance_cases.gd",
    "tests/run_balance.gd",
    "tests/pack_balance_evidence.py",
)

REQUIRED_TRACES = (
    "balance_melee.json",
    "balance_high.json",
    "balance_pit.json",
    "balance_chain.json",
    "balance_ff.json",
)

REQUIRED_LEDGER = (
    "RL-MODE-CHAOS",
    "RL-BAL-CRIT",
    "RL-BAL-KNOCK-JITTER",
    "RL-BAL-SPREAD-RNG",
    "RL-BAL-CAP",
    "RL-BAL-STAMINA",
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
    for needle in ("damage_taken_tick", "Balance.clamp_hit", "tick_room", "last_incoming_raw", "last_applied_damage"):
        if needle not in fighter:
            errors.append(f"fighter.gd must implement {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    for needle in ("chaos_enabled", "chaos_rng", "reset_chaos_rng", "roll_hit", "jitter_dir", "_record_hit_cap", "last_hit_raw", "last_fire_raw_spawn"):
        if needle not in session:
            errors.append(f"game_session must implement {needle}")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("balance_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("balance_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("balance_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("balance_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_schema",
        "outcome_batch",
        "outcome_dist",
        "outcome_dom",
        "outcome_melee",
        "outcome_high",
        "outcome_overcap",
        "outcome_pit",
        "outcome_chain",
        "outcome_ff",
        "outcome_stamina",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
        "run_seeded_batch",
        "finalize_dom",
        "incoming_raw",
        "formula_rolls",
        "hardcoded_winners",
        "fire_path_overcap",
        "last_incoming_raw",
        "identity_clamp_would_fail",
        "max_win_rate_bar",
        "distinct_contexts",
    ):
        if needle not in cases:
            errors.append(f"balance_cases missing {needle}")
    if "if dmg <= 0.05" in cases:
        errors.append("HIGH must not waive the bound check on a miss")
    if "ok = fired and aimed" in cases:
        errors.append("HIGH must not pass on fired+aimed with zero damage")
    if "take_damage(999" in cases or "_probe_hit_cap" in cases:
        errors.append("cap proof must be a fire-path overcap, not take_damage(999)")
    if "win_rate >= 1.0" in cases and "max_win_rate_bar" not in cases:
        errors.append("DOM must not define dominates as win_rate >= 1.0")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_bal = RUN_BAL.read_text(encoding="utf-8") if RUN_BAL.is_file() else ""
    if GATE_RUN_ID not in run_bal:
        errors.append(f"run_balance.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_bal:
            errors.append(f"run_balance.gd must not reuse {banned}")
    if "SCHEMA_SOURCE=outcome_schema" not in run_bal:
        errors.append("run_balance SCHEMA banner must cite outcome_schema")
    if "USED_APPLY_ATTEMPTED" not in run_bal or "USED_APPLY_SUCCEEDED" not in run_bal:
        errors.append("run_balance must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_balance_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "batch" not in packer or "dom" not in packer:
            errors.append("packer verdict must require batch/dom, not events alone")
        if "high_real" not in packer or "chain_real" not in packer:
            errors.append("packer must require HIGH/CHAIN live damage, not events alone")
        if "overcap_real" not in packer:
            errors.append("packer must require fire-path OVERCAP raw>56 applied<=56")
        if 'get("damage", 0.0)' not in packer:
            errors.append("packer must read HIGH/CHAIN damage from outcomes")
        if "0.55" not in packer:
            errors.append("packer must enforce the published 0.55 dominance bar")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "BalanceCases" not in run_all:
        errors.append("run_all.gd must call BalanceCases")
    if "outcome_batch" not in run_all or "HH_VF_BALANCE" not in run_all:
        errors.append("run_all.gd balance banner must read outcome_batch")
    if "outcome_overcap" not in run_all or "OVERCAP" not in run_all:
        errors.append("run_all.gd must banner OVERCAP from outcome_overcap")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not BALANCE.is_file():
        errors.append("missing data/sim/balance.json")
    else:
        payload = json.loads(BALANCE.read_text(encoding="utf-8"))
        if payload.get("chaos_class") != "assumption":
            errors.append("chaos must stay assumption")
        if payload.get("y8_parity_claimed") is True:
            errors.append("balance claimed Y8 parity")
        if payload.get("copied_stat_table") is True:
            errors.append("balance claimed a copied stat table")
        if payload.get("original_exact_numbers_claimed") is True:
            errors.append("balance claimed original exact numbers")
        if payload.get("title") != "Vault Fighters":
            errors.append("balance title must be Vault Fighters")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if int(payload.get("scenario_count", 0)) < 1000:
            errors.append("scenario_count must be >= 1000")
        dominance = payload.get("dominance") or {}
        if float(dominance.get("max_win_rate", 1.0)) > 0.5501:
            errors.append("balance.json must keep the published 0.55 win_rate bar")
        if int(dominance.get("require_distinct_contexts", 0)) < 3:
            errors.append("balance.json must require >=3 distinct context_best")
        if dominance.get("hardcoded_winners") is True:
            errors.append("balance.json must not hard-code winners")
        overcap = payload.get("overcap") or {}
        if str(overcap.get("weapon_id", "")) != "overcap_rifle":
            errors.append("balance.json overcap weapon must be overcap_rifle")
        fixtures = payload.get("fixtures", {})
        chain = "".join(fixtures.get("fx_balance_chain") or [])
        if "=" in chain:
            errors.append("grenade chain fixture must not use = platforms")
        for name in (payload.get("fixture_names") or {}).values():
            if TRADEMARK.search(str(name)):
                errors.append(f"fixture name uses Superfighters trademark: {name}")
    if not AIM.is_file():
        errors.append("missing data/sim/aim.json")
    else:
        aim = json.loads(AIM.read_text(encoding="utf-8"))
        rifle = (aim.get("guns") or {}).get("overcap_rifle") or {}
        if float(rifle.get("damage", 0.0)) <= 56.0:
            errors.append("overcap_rifle must have fire-path raw damage > 56")
        if str(rifle.get("kind", "")) != "gun":
            errors.append("overcap_rifle must be a gun so _do_fire owns it")
    if ROSTER.is_file():
        roster = json.loads(ROSTER.read_text(encoding="utf-8"))
        pool = roster.get("spawn_pool") or []
        if "overcap_rifle" in pool:
            errors.append("overcap_rifle must not be in the roster spawn pool")
        if "overcap_rifle" in (roster.get("items") or {}):
            errors.append("overcap_rifle must stay test-only aim data, not a roster item")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing balance trace {name}")
            continue
        raw = path.read_text(encoding="utf-8")
        trace = json.loads(raw)
        if trace.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append(f"{name} must set used_step_fixed false")
        if trace.get("y8_parity_claimed") is True:
            errors.append(f"{name} claimed Y8 parity")
        if trace.get("chaos") is not True:
            errors.append(f"{name} must enable chaos")
        if "assumption" not in str(trace.get("hold_to_aim", "")):
            errors.append(f"{name} must keep hold-to-aim assumption")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        if "teleport" in raw or "force_kill" in raw:
            errors.append(f"{name} official trace contains teleport/force_kill")
    if not DOCS.is_file():
        errors.append("missing docs/balance.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MODE-CHAOS",
            "ledger:RL-BAL-CRIT",
            "ledger:RL-BAL-KNOCK-JITTER",
            "ledger:RL-BAL-SPREAD-RNG",
            "ledger:RL-BAL-CAP",
            "ledger:RL-BAL-STAMINA",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "1000",
            "formula",
            "per-hit",
            "0.55",
            "OVERCAP",
            "fire-path",
            "overcap_rifle",
        ):
            if needle not in docs:
                errors.append(f"balance docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF3-WP6" not in ledger:
        errors.append("ledger missing VF3-WP6 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in (
        "RL-BAL-CRIT",
        "RL-BAL-KNOCK-JITTER",
        "RL-BAL-SPREAD-RNG",
        "RL-BAL-CAP",
        "RL-BAL-STAMINA",
    ):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    chaos_row = _row(ledger, "RL-MODE-CHAOS")
    if "`observed`" in chaos_row and "not observed" not in chaos_row:
        errors.append("RL-MODE-CHAOS must not be marked observed this WP")
    if errors:
        print("FAIL: Vault Fighters VF3-WP6 balance files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF3-WP6 balance files")
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
