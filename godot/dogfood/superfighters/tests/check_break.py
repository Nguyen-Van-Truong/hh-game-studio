#!/usr/bin/env python3
"""VF4-WP2 structure check: breakable glass/wood and throw/shove.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_break.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "break.md"
CATALOG = ROOT / "data" / "world" / "catalog.json"
CASES = ROOT / "tests" / "break_cases.gd"
RUN_BREAK = ROOT / "tests" / "run_break.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_break_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "break"
GATE_RUN_ID = "VF4WP2-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF4WP1-20260829-ASIA-SAIGON-01",
    "VF3WP6-20260829-ASIA-SAIGON-03",
    "VF3WP6-20260829-ASIA-SAIGON-02",
    "VF3WP6-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/world/prop_break.gd",
    "src/world/prop_body.gd",
    "src/world/world_owner.gd",
    "src/world/world_catalog.gd",
    "src/game_session.gd",
    "tests/break_cases.gd",
    "tests/run_break.gd",
    "tests/pack_break_evidence.py",
    "assets/art/prop_glass.png",
    "assets/vfx/vfx_break.png",
)

REQUIRED_TRACES = (
    "break_cover.json",
    "break_melee.json",
    "break_shove.json",
    "break_throw.json",
)

REQUIRED_LEDGER = (
    "RL-PROP-BREAK",
    "RL-PROP-DYNAMIC",
    "RL-NADE-PROP",
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
        if path.suffix in {".png"}:
            continue
        text = path.read_text(encoding="utf-8")
        if TRADEMARK.search(text) and "trademark" not in text.lower():
            errors.append(f"{rel} contains Superfighters trademark")
    session = (ROOT / "src" / "game_session.gd").read_text(encoding="utf-8")
    if "apply_damage" not in session or "try_throw" not in session:
        errors.append("game_session must wire bullet/melee/throw to WorldOwner")
    if "_spawn_crate" in session or "PropCrate" in session:
        errors.append("game_session must not name individual prop nodes")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("break_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("break_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("break_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("break_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_break",
        "outcome_debris",
        "outcome_pass",
        "outcome_ghost",
        "outcome_throw",
        "outcome_tactic",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"break_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_break = RUN_BREAK.read_text(encoding="utf-8") if RUN_BREAK.is_file() else ""
    if GATE_RUN_ID not in run_break:
        errors.append(f"run_break.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_break:
            errors.append(f"run_break.gd must not reuse {banned}")
    if "BREAK_SOURCE=outcome_break" not in run_break:
        errors.append("run_break BREAK banner must cite outcome_break")
    if "USED_APPLY_ATTEMPTED" not in run_break or "USED_APPLY_SUCCEEDED" not in run_break:
        errors.append("run_break must print attempted/succeeded apply counters")
    if "break_before" not in run_break or "break_after" not in run_break:
        errors.append("run_break must screenshot before/after")
    if not PACKER.is_file():
        errors.append("missing tests/pack_break_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "debris" not in packer or "ghost" not in packer:
            errors.append("packer verdict must require debris/ghost, not events alone")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "BreakCases" not in run_all:
        errors.append("run_all.gd must call BreakCases")
    if "outcome_break" not in run_all or "HH_VF_BREAK" not in run_all:
        errors.append("run_all.gd break banner must read outcome_break")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not CATALOG.is_file():
        errors.append("missing data/world/catalog.json")
    else:
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        if payload.get("break_implemented") is not True:
            errors.append("catalog break_implemented must be true")
        if payload.get("throw_implemented") is not True:
            errors.append("catalog throw_implemented must be true")
        if payload.get("chain_implemented") is not True:
            errors.append("catalog chain must be implemented")
        if payload.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if payload.get("y8_parity_claimed") is True:
            errors.append("catalog claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("catalog title must be Vault Fighters")
        specs = payload.get("specs") or {}
        if str((specs.get("pane_glass") or {}).get("material")) != "glass":
            errors.append("pane_glass must be glass")
        if str((specs.get("crate_breakable") or {}).get("material")) != "wood":
            errors.append("crate_breakable must be wood")
        mats = payload.get("materials") or {}
        if int((mats.get("glass") or {}).get("debris_count", 0)) != 6:
            errors.append("glass debris_count must be 6")
        if int((mats.get("wood") or {}).get("debris_count", 0)) != 4:
            errors.append("wood debris_count must be 4")
        for name in (payload.get("fixture_names") or {}).values():
            if TRADEMARK.search(str(name)):
                errors.append(f"fixture name uses Superfighters trademark: {name}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing break trace {name}")
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
        errors.append("missing docs/break.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-PROP-BREAK",
            "ledger:RL-PROP-DYNAMIC",
            "ledger:RL-NADE-PROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "debris",
        ):
            if needle not in docs:
                errors.append(f"break docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF4-WP2" not in ledger:
        errors.append("ledger missing VF4-WP2 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in ("RL-PROP-BREAK", "RL-PROP-DYNAMIC"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF4-WP2 break files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF4-WP2 break files")
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
