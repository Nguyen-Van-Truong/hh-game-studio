#!/usr/bin/env python3
"""VF6-WP5 structure check: bot planner.

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
DOCS = ROOT / "docs" / "bots.md"
BOTS = ROOT / "data" / "sim" / "bots.json"
CASES = ROOT / "tests" / "bot_cases.gd"
RUN = ROOT / "tests" / "run_bots.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_bots_evidence.py"
BRAIN = ROOT / "src" / "bot_brain.gd"
INPUT = ROOT / "src" / "input_actions.gd"
GATE_RUN_ID = "VF6WP5-20260903-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf6-wp5.bots.3"
FORBIDDEN_RUN_IDS = (
    "VF6WP5-20260903-ASIA-SAIGON-01",
    "VF6WP5-20260903-ASIA-SAIGON-02",
    "VF6WP4-20260903-ASIA-SAIGON-02",
    "VF6WP4-20260903-ASIA-SAIGON-01",
    "VF6WP3-20260901-ASIA-SAIGON-03",
)

REQUIRED_SCRIPTS = (
    "src/bot_brain.gd",
    "src/bot/bot_rules.gd",
    "src/bot/bot_nav.gd",
    "src/game_session.gd",
    "src/maps/map_graph.gd",
    "data/sim/bots.json",
    "data/sim/schema.json",
    "tests/bot_cases.gd",
    "tests/run_bots.gd",
    "tests/check_bots.py",
    "tests/pack_bots_evidence.py",
    "tests/run_all.gd",
    "docs/bots.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-BOT-NAV",
    "RL-BOT-PLAN",
    "RL-BOT-AIM",
    "RL-BOT-PIT",
    "RL-BOT-RECOVER",
    "RL-BOT-DIFF",
    "RL-BOT-BOUND",
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
    if not BOTS.is_file():
        errors.append("missing data/sim/bots.json")
        print_errors(errors)
        return 1
    row = json.loads(BOTS.read_text(encoding="utf-8"))
    if row.get("schema") != "vf.sim.bots.v1":
        errors.append("bots schema id mismatch")
    if row.get("title") != "Vault Fighters":
        errors.append("bots title must be Vault Fighters")
    if row.get("y8_parity_claimed", True):
        errors.append("bots must not claim Y8 parity")
    if not row.get("no_teleport") or not row.get("no_perfect_aim") or not row.get("no_hidden_state"):
        errors.append("bots.json must forbid teleport, perfect aim, and hidden state")
    for key in ("recruit", "regular", "veteran"):
        spec = row.get("profiles", {}).get(key, {})
        if float(spec.get("aim_error_deg", 0)) < 4:
            errors.append(f"{key} aim error too small")
    brain = BRAIN.read_text(encoding="utf-8") if BRAIN.is_file() else ""
    if "think_greedy" not in brain or "BotNav.path_to" not in brain:
        errors.append("bot_brain must keep greedy baseline and use BotNav")
    if "global_position =" in brain:
        errors.append("bot_brain must not teleport")
    if "aim_x" not in brain or "_detour_x" not in brain or "pit_reroutes" not in brain:
        errors.append("bot_brain must apply analog aim and route around pits")
    if "return bot.global_position.distance_to(other.global_position) < 80.0" in brain:
        errors.append("bot_brain must not invent LOS when physics space is null")
    if "age <= 45" in brain:
        errors.append("bot_brain must not track last-seen through walls for 45 ticks")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    for needle in (
        "used_force_kill",
        "used_teleport",
        "maps_seeded",
        "weapons_and_aim",
        "finish_match",
        "greedy_compare",
        "knockdown_recovery",
        "difficulty_visible",
        "bounded_and_det",
        "think_greedy",
        "apply_frames",
        "_botify_all",
        "fire_spawn",
        "explosion",
        "toward > 40.0",
        "last_shot_off_deg",
        "greedy_pit_deaths",
    ):
        if needle not in cases:
            errors.append(f"bot_cases missing {needle}")
    if "force_kill(" in cases or "player1().global_position =" in cases:
        errors.append("bot_cases official path must not teleport or force_kill")
    if "moved > 18.0" in cases:
        errors.append("bot_cases must not accept a 18px shuffle as reach")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_bots.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_bots.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_bots must use command_id {COMMAND_ID}")
    if "NOT_AI=0" not in run or "BOT_COVERAGE=planner" not in run:
        errors.append("run_bots must drop NOT_AI only with planner coverage")
    if "NOT_Y8_PARITY=1" not in run:
        errors.append("run_bots must keep NOT_Y8_PARITY")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "BotCasesScript" not in run_all or "HH_VF_BOTS" not in run_all:
        errors.append("run_all.gd must wire VF6-WP5 bot cases")
    if 'OS.set_environment("HH_VF_BOTS_COMPACT", "1")' in run_all:
        errors.append("run_all.gd must not default HH_VF_BOTS_COMPACT=1")
    if "GREEDY=%s" not in run_all or "RECOVER=%s" not in run_all:
        errors.append("run_all.gd must print GREEDY and RECOVER bot outcomes")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "assumption" not in docs:
        errors.append("docs/bots.md must name Vault Fighters and assumption")
    if "perfect aim" not in docs.lower() and "perfect-aim" not in docs.lower():
        errors.append("docs/bots.md must say bots do not have perfect aim")
    if GATE_RUN_ID not in docs:
        errors.append("docs/bots.md must pin official -03 run id")
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
    if "leftover_computed" not in packer or "headless_host_exit" not in packer:
        errors.append("packer must parse leftover and host exit independently of PROCESS_EXIT")
    if "critic-vf6wp5" not in packer:
        errors.append("packer must require leftover scan exclude critic-vf6wp5")
    if 'HH_VF_BOTS PROCESS_EXIT=0' in packer:
        errors.append("packer must not treat log PROCESS_EXIT as host exit")
    if "GREEDY=pass" not in packer or "RECOVER=pass" not in packer:
        errors.append("packer must require full run_all GREEDY and RECOVER")
    input_src = INPUT.read_text(encoding="utf-8") if INPUT.is_file() else ""
    if 'cmd["aim_x"]' not in input_src:
        errors.append("input_actions must pass analog aim_x through frames")
    if errors:
        print_errors(errors)
        return 1
    print("PASS: VF6-WP5 bot planner structure")
    print(f"RUN_ID={GATE_RUN_ID}")
    print(f"COMMAND_ID={COMMAND_ID}")
    return 0


def print_errors(errors: list[str]) -> None:
    print("FAIL: VF6-WP5 bot planner structure")
    for item in errors:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
