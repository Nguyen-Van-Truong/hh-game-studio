#!/usr/bin/env python3
"""VF6-WP3 structure check: Stage progression.

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
DOCS = ROOT / "docs" / "stage.md"
STAGE = ROOT / "data" / "sim" / "stage.json"
CASES = ROOT / "tests" / "stage_cases.gd"
RUN = ROOT / "tests" / "run_stage.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_stage_evidence.py"
GATE_RUN_ID = "VF6WP3-20260901-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf6-wp3.stage.3"
FORBIDDEN_RUN_IDS = (
    "VF6WP3-20260901-ASIA-SAIGON-02",
    "VF6WP3-20260901-ASIA-SAIGON-01",
    "VF6WP2-20260901-ASIA-SAIGON-03",
    "VF6WP2-20260901-ASIA-SAIGON-02",
    "VF6WP2-20260901-ASIA-SAIGON-01",
    "VF6WP1-20260901-ASIA-SAIGON-04",
)

REQUIRED_SCRIPTS = (
    "src/app.gd",
    "src/ui/title_screen.gd",
    "src/sim/stage.gd",
    "data/sim/stage.json",
    "data/sim/schema.json",
    "tests/stage_cases.gd",
    "tests/run_stage.gd",
    "tests/check_stage.py",
    "tests/pack_stage_evidence.py",
    "tests/run_all.gd",
    "docs/stage.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-STAGE-ORDER",
    "RL-STAGE-PROGRESS",
    "RL-STAGE-SAVE",
    "RL-STAGE-REWARD",
    "RL-STAGE-TIER",
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
    if "Reset Stage" not in title or "reset_stage_pressed" not in title:
        errors.append("title must expose Reset Stage")
    app = APP.read_text(encoding="utf-8") if APP.is_file() else ""
    if "StageRules.record_win" not in app or "_advance_stage" not in app:
        errors.append("app must award and advance after a stage win")
    if "StageRules.map_at(stage_index)" not in app:
        errors.append("stage rematch must stay on current catalog map")
    if "start_fight(\"survival\"" not in app and "start_fight('survival'" not in app:
        errors.append("app must start Survival as a separate mode")
    if not STAGE.is_file():
        errors.append("missing data/sim/stage.json")
        print_errors(errors)
        return 1
    stage = json.loads(STAGE.read_text(encoding="utf-8"))
    if stage.get("schema") != "vf.sim.stage.v1":
        errors.append("stage schema id mismatch")
    if stage.get("title") != "Vault Fighters":
        errors.append("stage title must be Vault Fighters")
    if stage.get("y8_parity_claimed", True):
        errors.append("stage must not claim Y8 parity")
    if stage.get("y8_order_observed", True):
        errors.append("stage order must not be marked observed")
    if stage.get("order_class") != "approximation":
        errors.append("stage order must stay approximation")
    if stage.get("difficulty_class") != "approximation":
        errors.append("stage difficulty must stay approximation")
    if stage.get("survival_shipped", True):
        errors.append("stage.json must keep survival_shipped false (not a Stage arena)")
    if not stage.get("title_survival_shipped", False):
        errors.append("stage.json must set title_survival_shipped true")
    arenas = stage.get("arenas", [])
    want = ["rooftops", "storage", "police", "hazardous"]
    got = [row.get("map_id") for row in arenas]
    if got != want:
        errors.append(f"stage order must be {want} got {got}")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    for needle in (
        "parse_input_event",
        "used_force_kill",
        "used_teleport",
        "reward_hash",
        "death_cause",
        "hazardous",
        "timeline",
        "cold",
        "Continue Stage",
        "Reset Stage",
        "Confirm Reset",
        "last_error",
        "vs_map_id",
        "_click_control_only",
        "confirm_reset_btn",
    ):
        if needle not in cases:
            errors.append(f"stage_cases missing {needle}")
    if "_clinch_win" in cases or 'start_fight("stage", "fx_melee_close"' in cases:
        errors.append("stage_cases official wins must stay on catalog maps")
    if "match_rules.apply_eval" in cases or ".apply_eval(" in cases:
        errors.append("stage_cases official rematch must not use apply_eval")
    if "force_kill(" in cases or "player1().global_position =" in cases:
        errors.append("stage_cases official path must not teleport or force_kill")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_stage.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_stage.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_stage must use command_id {COMMAND_ID}")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_stage banners must keep honesty flags")
    if "SURVIVAL_SHIPPED=0" not in run:
        errors.append("run_stage must declare Survival is not a Stage arena")
    if "TITLE_SURVIVAL_SHIPPED=1" not in run:
        errors.append("run_stage must declare Title Survival shipped")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "StageCasesScript" not in run_all or "HH_VF_STAGE" not in run_all:
        errors.append("run_all.gd must wire VF6-WP3 stage cases")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "approximation" not in docs:
        errors.append("docs/stage.md must name Vault Fighters and approximation")
    if "rooftops" not in docs or "storage" not in docs:
        errors.append("docs/stage.md must list catalog map ids")
    ledger = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    for row in REQUIRED_LEDGER:
        if row not in ledger:
            errors.append(f"ledger missing {row}")
    packer = PACKER.read_text(encoding="utf-8") if PACKER.is_file() else ""
    if GATE_RUN_ID not in packer or "leftover" not in packer:
        errors.append("packer must pin run_id and leftover proof")
    if "FINISHED=1" not in packer:
        errors.append("packer must not treat a PASS banner as host exit")
    if "win64_console.exe" not in packer:
        errors.append("packer must require the Godot console twin")
    if errors:
        print_errors(errors)
        return 1
    print("PASS: VF6-WP3 stage structure")
    print(f"RUN_ID={GATE_RUN_ID}")
    print(f"COMMAND_ID={COMMAND_ID}")
    return 0


def print_errors(errors: list[str]) -> None:
    print("FAIL: VF6-WP3 stage structure")
    for item in errors:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
