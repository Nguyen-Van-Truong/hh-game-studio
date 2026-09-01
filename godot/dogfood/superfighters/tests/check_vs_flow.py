#!/usr/bin/env python3
"""VF6-WP2 structure check: VS 1P / local VS 2P production flow.

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
LOBBY = ROOT / "src" / "ui" / "lobby_screen.gd"
APP = ROOT / "src" / "app.gd"
WIN = ROOT / "src" / "ui" / "win_screen.gd"
DOCS = ROOT / "docs" / "vs_flow.md"
FLOW = ROOT / "data" / "sim" / "vs_flow.json"
CASES = ROOT / "tests" / "vs_flow_cases.gd"
RUN = ROOT / "tests" / "run_vs_flow.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_vs_flow_evidence.py"
GATE_RUN_ID = "VF6WP2-20260901-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf6-wp2.vs-flow.3"
FORBIDDEN_RUN_IDS = (
    "VF6WP2-20260901-ASIA-SAIGON-02",
    "VF6WP2-20260901-ASIA-SAIGON-01",
    "VF6WP1-20260901-ASIA-SAIGON-04",
    "VF6WP1-20260901-ASIA-SAIGON-03",
    "VF6WP1-20260901-ASIA-SAIGON-02",
    "VF6WP1-20260901-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/app.gd",
    "src/ui/title_screen.gd",
    "src/ui/lobby_screen.gd",
    "src/ui/win_screen.gd",
    "src/ui/lose_screen.gd",
    "src/ui/tie_screen.gd",
    "src/sim/vs_flow.gd",
    "data/sim/vs_flow.json",
    "data/sim/schema.json",
    "tests/vs_flow_cases.gd",
    "tests/run_vs_flow.gd",
    "tests/check_vs_flow.py",
    "tests/pack_vs_flow_evidence.py",
    "tests/run_all.gd",
    "docs/vs_flow.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-VS-FLOW",
    "RL-VS-READY",
    "RL-VS-ISOLATE",
    "RL-VS-REMATCH",
    "RL-VS-FIRST-RUN",
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
    if "Two taps" not in title:
        errors.append("title must advertise the two-tap first-run path")
    lobby = LOBBY.read_text(encoding="utf-8") if LOBBY.is_file() else ""
    if "class_name LobbyScreen" not in lobby or "start_pressed" not in lobby:
        errors.append("lobby must expose Start")
    app = APP.read_text(encoding="utf-8") if APP.is_file() else ""
    if "open_lobby" not in app or "restart_same" not in app:
        errors.append("app must open lobby and rematch same")
    if 'start_fight("survival"' in app:
        errors.append("app must not start Survival")
    win = WIN.read_text(encoding="utf-8") if WIN.is_file() else ""
    if "rematch_pressed" not in win or "hide_result" not in win:
        errors.append("win overlay must offer rematch and hide_result")
    if not FLOW.is_file():
        errors.append("missing data/sim/vs_flow.json")
        print_errors(errors)
        return 1
    flow = json.loads(FLOW.read_text(encoding="utf-8"))
    if flow.get("schema") != "vf.sim.vs_flow.v1":
        errors.append("vs_flow schema id mismatch")
    if flow.get("title") != "Vault Fighters":
        errors.append("vs_flow title must be Vault Fighters")
    if flow.get("y8_parity_claimed", True):
        errors.append("vs_flow must not claim Y8 parity")
    if flow.get("survival_shipped", True):
        errors.append("Survival must stay unshipped")
    first = flow.get("first_run", {})
    rematch = flow.get("rematch", {})
    if int(first.get("max_actions", 99)) > 3 or int(first.get("max_seconds", 99)) > 30:
        errors.append("first_run UX contract too loose")
    if int(rematch.get("max_actions", 99)) > 2 or int(rematch.get("max_seconds", 99)) > 5:
        errors.append("rematch UX contract too loose")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    for needle in (
        "parse_input_event",
        "used_force_kill",
        "used_teleport",
        "outcome_leak",
        "outcome_rematch",
        "first_run",
        "KEY_A",
        "KEY_RIGHT",
    ):
        if needle not in cases:
            errors.append(f"vs_flow_cases missing {needle}")
    if "force_kill(" in cases or "player1().global_position =" in cases or "p1.global_position =" in cases:
        errors.append("vs_flow_cases official path must not teleport or force_kill")
    if 'await _title_start_vs2(app, "rooftops")' in cases or "KEY_RIGHT, 160" in cases:
        errors.append("vs_flow_cases must not restart rooftops and pit-walk")
    if "fx_melee_close" not in cases or "p1_attacked" not in cases or "p2_attacked" not in cases:
        errors.append("vs_flow_cases must resolve both players on fx_melee_close")
    if 'death_cause == "damage"' not in cases or "used_pit_fallback" not in cases:
        errors.append("vs_flow_cases must require a damage KO and record no pit fallback")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_vs_flow.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_vs_flow.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_vs_flow must use command_id {COMMAND_ID}")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_vs_flow banners must keep honesty flags")
    if "SURVIVAL_SHIPPED=0" not in run:
        errors.append("run_vs_flow must declare Survival unshipped")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "VsFlowCasesScript" not in run_all or "HH_VF_VS2" not in run_all:
        errors.append("run_all.gd must wire VF6-WP2 vs flow cases")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "Rematch" not in docs:
        errors.append("docs/vs_flow.md must name Vault Fighters and rematch")
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
    print("PASS: VF6-WP2 vs flow structure")
    print(f"RUN_ID={GATE_RUN_ID}")
    print(f"COMMAND_ID={COMMAND_ID}")
    return 0


def print_errors(errors: list[str]) -> None:
    print("FAIL: VF6-WP2 vs flow structure")
    for item in errors:
        print(f"  - {item}")


if __name__ == "__main__":
    sys.exit(main())
