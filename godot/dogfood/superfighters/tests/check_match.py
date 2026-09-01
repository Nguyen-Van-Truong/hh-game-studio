#!/usr/bin/env python3
"""VF6-WP1 structure check: canonical match state machine.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_match.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "match.md"
MATCH = ROOT / "data" / "sim" / "match.json"
CASES = ROOT / "tests" / "match_cases.gd"
RUN = ROOT / "tests" / "run_match.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_match_evidence.py"
SESSION = ROOT / "src" / "game_session.gd"
MACHINE = ROOT / "src" / "sim" / "match.gd"
GATE_RUN_ID = "VF6WP1-20260901-ASIA-SAIGON-04"
COMMAND_ID = "cmd.vf6-wp1.match-machine.4"
FORBIDDEN_RUN_IDS = (
    "VF6WP1-20260901-ASIA-SAIGON-03",
    "VF6WP1-20260901-ASIA-SAIGON-02",
    "VF6WP1-20260901-ASIA-SAIGON-01",
    "VF6WP1-20260831-ASIA-SAIGON-01",
    "VF6WP1-20260831-ASIA-SAIGON-02",
    "VF6WP1-20260831-ASIA-SAIGON-03",
    "VF5WP6-20260831-ASIA-SAIGON-02",
    "VF5WP6-20260831-ASIA-SAIGON-01",
    "VF5WP5-20260831-ASIA-SAIGON-07",
)

REQUIRED_SCRIPTS = (
    "src/sim/match.gd",
    "src/game_session.gd",
    "src/app.gd",
    "src/ui/pause_screen.gd",
    "src/ui/tie_screen.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "data/sim/match.json",
    "data/sim/schema.json",
    "tests/match_cases.gd",
    "tests/run_match.gd",
    "tests/check_match.py",
    "tests/pack_match_evidence.py",
    "tests/run_all.gd",
    "tests/traces/match/match_win.json",
    "tests/traces/match/match_lose.json",
    "tests/traces/match/match_tie.json",
    "tests/traces/match/match_quit.json",
    "tests/traces/match/match_restart.json",
    "tests/traces/match/match_pause.json",
    "docs/match.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-MATCH-MACHINE",
    "RL-MATCH-TEAMS",
    "RL-MATCH-LAST",
    "RL-MATCH-SEED",
    "RL-MATCH-TIMER",
    "RL-MATCH-COUNTDOWN",
    "RL-SIM-FIXED-60",
    "RL-CTRL-HOLD-AIM",
    "RL-MOVE-ROLL-DIVE",
    "RL-HIT-FF",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")
TRACES = (
    "match_win",
    "match_lose",
    "match_tie",
    "match_quit",
    "match_restart",
    "match_pause",
)


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
        if TRADEMARK.search(text) and "trademark" not in text.lower():
            errors.append(f"{rel} contains Superfighters trademark")
    title = TITLE.read_text(encoding="utf-8") if TITLE.is_file() else ""
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if not MATCH.is_file():
        errors.append("missing data/sim/match.json")
        print_errors(errors)
        return 1
    match = json.loads(MATCH.read_text(encoding="utf-8"))
    if match.get("schema") != "vf.sim.match.v1":
        errors.append("match schema id mismatch")
    if match.get("title") != "Vault Fighters":
        errors.append("match title must be Vault Fighters")
    if match.get("y8_parity_claimed", True):
        errors.append("match must not claim Y8 parity")
    if match.get("timer_observed", True):
        errors.append("round timer must not be marked observed")
    if not match.get("canonical", False):
        errors.append("match machine must be canonical")
    modes = match.get("modes", {})
    vs2 = modes.get("vs2", {})
    vs1 = modes.get("vs1", {})
    survival = modes.get("survival", {})
    if not vs2.get("uses_machine", False) or not vs2.get("official_lifecycle", False):
        errors.append("vs2 must use the machine as official lifecycle")
    if not vs1.get("uses_machine", False):
        errors.append("vs1 must construct the machine when started")
    if survival.get("uses_machine", False) or survival.get("shipped", False):
        errors.append("survival must stay unshipped and off uses_machine")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if "window_menu_e2e" not in cases or "parse_input_event" not in cases:
        errors.append("match_cases must prove window/menu E2E")
    if "title_visible_after" not in cases:
        errors.append("match_cases must record title_visible_after")
    if "apply_frames" not in cases:
        errors.append("match_cases must use apply_frames")
    if "force_kill" not in cases or "used_force_kill" not in cases:
        errors.append("match_cases must forbid official force_kill")
    for needle in (
        "outcome_win",
        "outcome_lose",
        "outcome_tie",
        "outcome_quit",
        "outcome_restart",
        "outcome_pause",
        "outcome_signal",
        "used_apply_frames",
        "P2_COVERAGE" if False else "timeout",
        "PHASE_PAUSED",
    ):
        if needle not in cases:
            errors.append(f"match_cases missing {needle}")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "_Match.evaluate" not in session and "MatchRules.evaluate" not in session:
        errors.append("game_session must resolve through MatchRules.evaluate")
    if "func force_kill" not in session or "Fixture-only" not in session:
        errors.append("force_kill must stay fixture-only")
    machine = MACHINE.read_text(encoding="utf-8") if MACHINE.is_file() else ""
    if "class_name MatchRules" not in machine:
        errors.append("match.gd must define MatchRules")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_match.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_match.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_match must use command_id {COMMAND_ID}")
    if "P2_COVERAGE=smoke" not in run or "BOT_COVERAGE=smoke" not in run:
        errors.append("run_match banners must mark P2/BOT as smoke")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_match banners must keep honesty flags")
    if "FORCE_KILL_OFFICIAL=0" not in run:
        errors.append("run_match must declare force_kill off official path")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "MatchCasesScript" not in run_all or "HH_VF_MATCH" not in run_all:
        errors.append("run_all.gd must wire VF6-WP1 match cases")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "approximation" not in docs:
        errors.append("docs/match.md must name Vault Fighters and label timer approximation")
    ledger = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    for row in REQUIRED_LEDGER:
        if row not in ledger:
            errors.append(f"ledger missing {row}")
    for name in TRACES:
        path = ROOT / "tests" / "traces" / "match" / f"{name}.json"
        if not path.is_file():
            errors.append(f"missing trace {name}")
            continue
        raw = path.read_text(encoding="utf-8")
        if "force_kill" in raw or "teleport" in raw:
            errors.append(f"{name} official text contains fixture op")
        trace = json.loads(raw)
        if trace.get("kind") != "official":
            errors.append(f"{name} must be official")
        if trace.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        if trace.get("y8_parity_claimed", True):
            errors.append(f"{name} must not claim Y8 parity")
    packer = PACKER.read_text(encoding="utf-8") if PACKER.is_file() else ""
    if GATE_RUN_ID not in packer or "leftover" not in packer:
        errors.append("packer must pin run_id and leftover proof")
    if "PASS: Vault Fighters match state machine" in packer and "parse_exit_from_log" in packer:
        if "FINISHED=1" not in packer:
            errors.append("packer must not treat a PASS banner as host exit")
    if "win64_console.exe" not in packer:
        errors.append("packer must require the Godot console twin")
    if errors:
        print_errors(errors)
        return 1
    print("PASS: VF6-WP1 match structure")
    print(f"RUN_ID={GATE_RUN_ID}")
    print(f"COMMAND_ID={COMMAND_ID}")
    return 0


def print_errors(errors: list[str]) -> None:
    print("FAIL: VF6-WP1 match structure")
    for item in errors:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
