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
OFFICIAL = ROOT / "tests" / "run_bots_official.ps1"
BRAIN = ROOT / "src" / "bot_brain.gd"
SESSION = ROOT / "src" / "game_session.gd"
APP = ROOT / "src" / "app.gd"
INPUT = ROOT / "src" / "input_actions.gd"
GATE_RUN_ID = "VF6WP5-20260904-ASIA-SAIGON-08"
COMMAND_ID = "cmd.vf6-wp5.bots.8"
FORBIDDEN_RUN_IDS = (
    "VF6WP5-20260903-ASIA-SAIGON-01",
    "VF6WP5-20260903-ASIA-SAIGON-02",
    "VF6WP5-20260903-ASIA-SAIGON-03",
    "VF6WP5-20260903-ASIA-SAIGON-04",
    "VF6WP5-20260904-ASIA-SAIGON-01",
    "VF6WP5-20260904-ASIA-SAIGON-02",
    "VF6WP5-20260904-ASIA-SAIGON-03",
    "VF6WP5-20260904-ASIA-SAIGON-04",
    "VF6WP5-20260904-ASIA-SAIGON-05",
    "VF6WP5-20260904-ASIA-SAIGON-06",
    "VF6WP5-20260904-ASIA-SAIGON-07",
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
    "tests/run_bots_official.ps1",
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
    if "if dist > 72.0" in brain:
        errors.append("bot_brain must not zero walk at the 72 lip")
    if re.search(r"if dist > 48\.0:", brain):
        errors.append("bot_brain walk-stop must not equal reach constant 48")
    if "if absf(err) < 3.0" in brain:
        errors.append("aim error must allow a real near-zero roll")
    if "aim_x" not in brain or "_detour_x" not in brain or "pit_reroutes" not in brain:
        errors.append("bot_brain must apply analog aim and route around pits")
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    app_src = APP.read_text(encoding="utf-8") if APP.is_file() else ""
    if "vs1_bot_count" not in session or "vs1_bot_count" not in app_src:
        errors.append("vs1 must support a 2-body spawn")
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
        "waypoint_dist",
        "REACH_GOAL_PX",
        "REACH_ENGAGE_PX",
        "last_shot_off_deg",
        "greedy_pit_deaths",
        "vs1_bot_count",
        "spawned_count",
        "closest_engage",
        "closed_then_down",
        "reach_reason",
        "fighter_count",
        "_explosion_after_bullet",
        "LIP_ENGAGE_LO",
        "force_draw",
    ):
        if needle not in cases:
            errors.append(f"bot_cases missing {needle}")
    fin_idx = cases.find("static func finish_match")
    fin_end = cases.find("static func greedy_compare")
    fin_body = cases[fin_idx:fin_end] if fin_idx >= 0 and fin_end > fin_idx else ""
    if "_keep_exactly_two" in fin_body:
        errors.append("finish must spawn exactly two, not cull extras after sync")
    if "vs1_bot_count = 1" not in fin_body:
        errors.append("finish must use a 2-body vs1 spawn")
    if "force_kill(" in cases or "player1().global_position =" in cases:
        errors.append("bot_cases official path must not teleport or force_kill")
    if "moved > 18.0" in cases:
        errors.append("bot_cases must not accept a 18px shuffle as reach")
    if "engage_dist < 300.0" in cases or "engage_dist < 240" in cases:
        errors.append("bot_cases must not accept long-range gun as reach")
    if "engage_dist < 72.0" in cases or "closest_engage < 72.0" in cases:
        errors.append("bot_cases must not accept engage < 72 as reach")
    if "p_engage < 72.0" in cases:
        errors.append("greedy arrive must not use the 72 gate")
    if "gun_n > 0 and named_down" in cases:
        errors.append("bot_cases must not treat a long-range named_down as reach")
    if "gun&&engage" in cases or "gun && engage" in cases:
        errors.append("bot_cases must not keep gun&&engage reach")
    if re.search(r"named_down\s*and\s+gun", cases) or "named_down and gun_n" in cases:
        errors.append("bot_cases must not keep named_down+gun reach")
    if "pit_reroutes" in cases and "pit_reroutes\", 0)) < 1" in cases:
        errors.append("bot_cases must not treat pit_reroutes as rooftops arrival")
    if "planner must arrive on rooftops compare" not in cases:
        errors.append("bot_cases greedy compare must require planner arrival")
    if "pit_deaths + fire_deaths" in cases:
        errors.append("bot_cases must not count fire deaths as pit")
    nav = (ROOT / "src" / "bot" / "bot_nav.gd").read_text(encoding="utf-8") if (ROOT / "src" / "bot" / "bot_nav.gd").is_file() else ""
    if "step_is_unsafe" not in nav or "nxt.y == cur.y" not in nav:
        errors.append("bot_nav must treat same-y unsafe lips as non-neighbors")
    detour_idx = brain.find("func _detour_x")
    if detour_idx < 0:
        errors.append("bot_brain missing _detour_x")
    else:
        detour_end = brain.find("\nfunc ", detour_idx + 8)
        if detour_end < 0:
            detour_end = detour_idx + 2400
        detour_body = brain[detour_idx:detour_end]
        first_incr = detour_body.find("pit_reroutes += 1")
        chosen_ok = detour_body.find("if chosen != 0.0:")
        if first_incr < 0 or chosen_ok < 0 or first_incr < chosen_ok:
            errors.append("bot_brain must count pit_reroutes only after a successful detour")
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
    if "official run_all must not set HH_VF_BOTS_COMPACT=1" not in run_all:
        errors.append("run_all.gd must error when HH_VF_BOTS_COMPACT=1")
    if "GREEDY=%s" not in run_all or "RECOVER=%s" not in run_all:
        errors.append("run_all.gd must print GREEDY and RECOVER bot outcomes")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Vault Fighters" not in docs or "assumption" not in docs:
        errors.append("docs/bots.md must name Vault Fighters and assumption")
    if "perfect aim" not in docs.lower() and "perfect-aim" not in docs.lower():
        errors.append("docs/bots.md must say bots do not have perfect aim")
    if GATE_RUN_ID not in docs:
        errors.append(f"docs/bots.md must pin official {GATE_RUN_ID}")
    ledger = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    for row_id in REQUIRED_LEDGER:
        if row_id not in ledger:
            errors.append(f"ledger missing {row_id}")
    packer = PACKER.read_text(encoding="utf-8") if PACKER.is_file() else ""
    if GATE_RUN_ID not in packer or "leftover" not in packer:
        errors.append("packer must pin run_id and leftover proof")
    if "win64_console.exe" not in packer:
        errors.append("packer must require the Godot console twin")
    if "leftover_computed" not in packer or "headless_host_exit" not in packer:
        errors.append("packer must parse leftover and host exit independently of PROCESS_EXIT")
    if "waitforexit" not in packer.lower():
        errors.append("packer must require leftover host WaitForExit")
    if 'critic-vf6wp5" in leftover_excl' in packer or '"critic-vf6wp5" in leftover_excl' in packer:
        errors.append("packer must not require critic-exclude")
    if "HH_VF_BOTS FINISHED=1" in packer and "return 0" in packer:
        parse_idx = packer.find("def parse_exit_from_log")
        parse_end = packer.find("def write_freeze")
        parse_body = packer[parse_idx:parse_end] if parse_idx >= 0 else packer
        if "FINISHED=1" in parse_body and "return 0" in parse_body:
            errors.append("packer must not treat PASS+FINISHED as host exit 0")
    if 'HH_VF_BOTS PROCESS_EXIT=0' in packer:
        errors.append("packer must not treat log PROCESS_EXIT as host exit")
    if "GREEDY=pass" not in packer or "RECOVER=pass" not in packer:
        errors.append("packer must require full run_all GREEDY and RECOVER")
    if "LIP_ENGAGE" not in packer and "71.0" not in packer:
        errors.append("packer must reject engage in [71,72) as sole reach")
    if "engage_dist" in packer and "< 72.0" in packer:
        errors.append("packer reach must not be engage < 72")
    official = OFFICIAL.read_text(encoding="utf-8") if OFFICIAL.is_file() else ""
    if not official:
        errors.append("missing tests/run_bots_official.ps1")
    else:
        if GATE_RUN_ID not in official or COMMAND_ID not in official:
            errors.append(f"official host script must pin {GATE_RUN_ID} run/command id")
        if "WaitForExit" not in official:
            errors.append("official leftover must use host WaitForExit")
        if "Start-Process" in official:
            errors.append("official must not use Start-Process (null ExitCode)")
        if "HhGodotHost" not in official and "ProcessStartInfo" not in official:
            errors.append("official must host Godot via .NET Process WaitForExit")
        if "critic-vf6wp5" in official:
            errors.append("official leftover must not require critic-exclude")
        if "PASS: Vault Fighters" in official and "$code = 0" in official:
            errors.append("official host must not remap banner to exit 0")
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
