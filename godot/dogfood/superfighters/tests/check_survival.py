#!/usr/bin/env python3
"""VF6-WP4 structure check: Survival director.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
APP = ROOT / "src" / "app.gd"
DOCS = ROOT / "docs" / "survival.md"
SURVIVAL = ROOT / "data" / "sim" / "survival.json"
MATCH = ROOT / "data" / "sim" / "match.json"
CASES = ROOT / "tests" / "survival_cases.gd"
RUN = ROOT / "tests" / "run_survival.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_survival_evidence.py"
GATE_RUN_ID = "VF6WP4-20260903-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf6-wp4.survival.2"
FORBIDDEN_RUN_IDS = (
    "VF6WP4-20260903-ASIA-SAIGON-01",
    "VF6WP3-20260901-ASIA-SAIGON-03",
    "VF6WP3-20260901-ASIA-SAIGON-02",
    "VF6WP3-20260901-ASIA-SAIGON-01",
    "VF6WP2-20260901-ASIA-SAIGON-03",
)

REQUIRED_SCRIPTS = (
    "src/app.gd",
    "src/ui/title_screen.gd",
    "src/sim/survival.gd",
    "src/sim/match.gd",
    "src/game_session.gd",
    "data/sim/survival.json",
    "data/sim/schema.json",
    "tests/survival_cases.gd",
    "tests/run_survival.gd",
    "tests/check_survival.py",
    "tests/pack_survival_evidence.py",
    "tests/run_all.gd",
    "docs/survival.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-SURVIVAL-LOOP",
    "RL-SURVIVAL-WAVE",
    "RL-SURVIVAL-SCORE",
    "RL-SURVIVAL-SPAWN",
    "RL-SURVIVAL-RECORD",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED_SCRIPTS:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        if path.suffix == ".json":
            continue
        text = path.read_text(encoding="utf-8")
        if TRADEMARK.search(text) and "trademark" not in text.lower() and "reference" not in text.lower():
            errors.append(f"{rel} contains Superfighters trademark")
    title = TITLE.read_text(encoding="utf-8") if TITLE.is_file() else ""
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Survival" not in title or "survival_pressed" not in title:
        errors.append("title must expose Survival")
    app = APP.read_text(encoding="utf-8") if APP.is_file() else ""
    if 'start_fight("survival"' not in app:
        errors.append("app must start Survival")
    if 'mode == "survival"' not in app:
        errors.append("app must treat Survival rematch as a new run")
    if not SURVIVAL.is_file():
        errors.append("missing data/sim/survival.json")
        print_errors(errors)
        return 1
    row = json.loads(SURVIVAL.read_text(encoding="utf-8"))
    if row.get("schema") != "vf.sim.survival.v1":
        errors.append("survival schema id mismatch")
    if row.get("title") != "Vault Fighters":
        errors.append("survival title must be Vault Fighters")
    if row.get("y8_parity_claimed", True):
        errors.append("survival must not claim Y8 parity")
    if row.get("loop_class") != "approximation":
        errors.append("survival loop must stay approximation")
    if row.get("wave_class") != "approximation":
        errors.append("survival wave must stay approximation")
    match = json.loads(MATCH.read_text(encoding="utf-8")) if MATCH.is_file() else {}
    survival_mode = match.get("modes", {}).get("survival", {})
    if not survival_mode.get("shipped", False) or not survival_mode.get("uses_machine", False):
        errors.append("match.json survival must ship and use the machine")
    if survival_mode.get("official_lifecycle", False):
        errors.append("survival must not steal official_lifecycle")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    for needle in (
        "parse_input_event",
        "used_force_kill",
        "used_teleport",
        "distinct_from_stage",
        "score_and_spawn",
        "pause_resume",
        "gameover_restart",
        "soak_seconds",
        "timeline",
        "_click_control",
        "_hunt_roster",
        "wave_table",
        "score_from_kills",
        "spawn_denied",
        "living_cap",
        "pause_visible",
        "captured_while_frozen",
        "death_cause",
        "used_pit",
        "bot_min_hp",
    ):
        if needle not in cases:
            errors.append(f"survival_cases missing {needle}")
    if "force_kill(" in cases or "player1().global_position =" in cases:
        errors.append("survival_cases official path must not teleport or force_kill")
    if "match_rules.apply_eval" in cases or ".apply_eval(" in cases:
        errors.append("survival_cases official path must not use apply_eval")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_survival.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_survival.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_survival must use command_id {COMMAND_ID}")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_survival banners must keep honesty flags")
    if "SURVIVAL_SHIPPED=1" not in run:
        errors.append("run_survival must declare Survival shipped")
    if "TITLE_SURVIVAL_SHIPPED=1" not in run:
        errors.append("run_survival must declare Title Survival shipped")
    if "SURVIVAL_AS_STAGE=0" not in run:
        errors.append("run_survival must say Survival is not a Stage arena")
    if "cmd.vf6-wp4.survival.1" in run:
        errors.append("run_survival must not reuse cmd.vf6-wp4.survival.1")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "SurvivalCasesScript" not in run_all or "HH_VF_SURVIVAL" not in run_all:
        errors.append("run_all.gd must wire VF6-WP4 survival cases")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "approximation" not in docs:
        errors.append("docs/survival.md must name Vault Fighters and approximation")
    if "Stage" not in docs or "checkpoint" not in docs:
        errors.append("docs/survival.md must say Survival is not a Stage checkpoint")
    ledger = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    for row_id in REQUIRED_LEDGER:
        if row_id not in ledger:
            errors.append(f"ledger missing {row_id}")
    packer = PACKER.read_text(encoding="utf-8") if PACKER.is_file() else ""
    if GATE_RUN_ID not in packer or "leftover" not in packer:
        errors.append("packer must pin run_id and leftover proof")
    if "FINISHED=1" not in packer:
        errors.append("packer must not treat a PASS banner as host exit")
    if "win64_console.exe" not in packer:
        errors.append("packer must require the Godot console twin")
    if "600" not in packer or "300" not in packer:
        errors.append("packer must require 10-minute headless and 5-minute window")
    if "leftover_computed" not in packer or "headless_host_exit" not in packer:
        errors.append("packer must parse leftover and host exit independently of PROCESS_EXIT")
    if errors:
        print_errors(errors)
        return 1
    print("PASS: VF6-WP4 survival structure")
    print(f"RUN_ID={GATE_RUN_ID}")
    print(f"COMMAND_ID={COMMAND_ID}")
    return 0


def print_errors(errors: list[str]) -> None:
    print("FAIL: VF6-WP4 survival structure")
    for item in errors:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
