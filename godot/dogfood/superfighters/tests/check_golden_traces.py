#!/usr/bin/env python3
"""VF1-WP3 structure check: official InputFrame traces vs fixture.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_golden_traces.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "tests" / "traces" / "official"
FIXTURE = ROOT / "tests" / "traces" / "fixture"
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
TRACE_SCHEMA = ROOT / "data" / "sim" / "trace.json"
HARNESS = ROOT.parents[2] / "tools" / "godot" / "vf_trace_harness.py"

REQUIRED_OFFICIAL = (
    "title_fight_restart.json",
    "walk_jump_crouch.json",
    "fire_throw.json",
    "death_lose.json",
    "win_restart.json",
)

REQUIRED_SCRIPTS = (
    "src/sim/sim_trace.gd",
    "src/sim/sim_ledger.gd",
    "src/sim/sim_recorder.gd",
    "src/sim/sim_replay.gd",
    "tests/trace_cases.gd",
    "tests/run_golden_traces.gd",
)


def main() -> int:
    errors: list[str] = []
    if not TRACE_SCHEMA.is_file():
        errors.append("missing data/sim/trace.json")
    else:
        schema = json.loads(TRACE_SCHEMA.read_text(encoding="utf-8"))
        if schema.get("schema") != "vf.sim.trace.v1":
            errors.append("trace schema id mismatch")
        if schema.get("y8_tick_rate_claimed") is not False:
            errors.append("trace schema must set y8_tick_rate_claimed false")
        if schema.get("title") != "Vault Fighters":
            errors.append("trace schema title must be Vault Fighters")
        if schema.get("ledger_clock") != "RL-SIM-FIXED-60":
            errors.append("trace schema must cite RL-SIM-FIXED-60")
        if "teleport" not in schema.get("official_forbids", []):
            errors.append("trace schema must forbid teleport in official")
        if "force_kill" not in schema.get("official_forbids", []):
            errors.append("trace schema must forbid force_kill in official")
    for rel in REQUIRED_SCRIPTS:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
        else:
            text = path.read_text(encoding="utf-8")
            if re.search(r"Superfighters|Super Fighter", text):
                errors.append(f"{rel} contains Superfighters trademark")
    if not HARNESS.is_file():
        errors.append("missing tools/godot/vf_trace_harness.py")
    for name in REQUIRED_OFFICIAL:
        path = OFFICIAL / name
        if not path.is_file():
            errors.append(f"missing official {name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not JSON: {exc}")
            continue
        dumped = json.dumps(payload)
        if payload.get("kind") != "official":
            errors.append(f"{name} kind must be official")
        if payload.get("title") != "Vault Fighters":
            errors.append(f"{name} title must be Vault Fighters")
        if payload.get("tick_hz") != 60:
            errors.append(f"{name} tick_hz must be 60")
        if payload.get("y8_tick_rate_claimed") is not False:
            errors.append(f"{name} must not claim a Y8 tick rate")
        if payload.get("y8_parity_claimed") is not False:
            errors.append(f"{name} must not claim Y8 parity")
        if payload.get("ledger_clock") != "RL-SIM-FIXED-60":
            errors.append(f"{name} must cite ledger:RL-SIM-FIXED-60")
        if payload.get("fixture_ops"):
            errors.append(f"{name} official must not include fixture_ops")
        if "teleport" in dumped or "force_kill" in dumped:
            errors.append(f"{name} official text contains teleport or force_kill")
        if not payload.get("segments") and not payload.get("frames"):
            errors.append(f"{name} missing InputFrame segments/frames")
        if "Superfighters" in dumped or "Super Fighter" in dumped:
            errors.append(f"{name} contains Superfighters trademark")
    fixture = FIXTURE / "teleport_force_kill.json"
    if not fixture.is_file():
        errors.append("missing fixture teleport_force_kill.json")
    else:
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        if payload.get("kind") != "fixture":
            errors.append("fixture kind must be fixture")
        ops = {str(op.get("op")) for op in payload.get("fixture_ops", [])}
        if "teleport" not in ops or "force_kill" not in ops:
            errors.append("fixture must demonstrate teleport and force_kill")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in ("RL-SIM-FIXED-60", "RL-SIM-INPUT-FRAME", "RL-SIM-TRACE-REPLAY"):
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if errors:
        print("FAIL: Vault Fighters VF1-WP3 golden traces")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF1-WP3 golden traces")
    print(f"  official={len(REQUIRED_OFFICIAL)} fixture=1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
