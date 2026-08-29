#!/usr/bin/env python3
"""VF4-WP1 structure check: world/prop schema and collision ownership.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_world.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "world.md"
CATALOG = ROOT / "data" / "world" / "catalog.json"
GATE = ROOT / "data" / "world" / "schema.json"
LAYERS = ROOT / "data" / "sim" / "collision_layers.json"
SESSION = ROOT / "src" / "game_session.gd"
CASES = ROOT / "tests" / "world_cases.gd"
RUN_WORLD = ROOT / "tests" / "run_world.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_world_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "world"
GATE_RUN_ID = "VF4WP1-20260829-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF3WP6-20260829-ASIA-SAIGON-03",
    "VF3WP6-20260829-ASIA-SAIGON-02",
    "VF3WP6-20260829-ASIA-SAIGON-01",
    "VF3WP5-20260829-ASIA-SAIGON-02",
    "VF3WP5-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/world/prop_spec.gd",
    "src/world/world_catalog.gd",
    "src/world/world_owner.gd",
    "src/world/world_paths.gd",
    "src/world/prop_body.gd",
    "src/world/prop_view.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "tests/world_cases.gd",
    "tests/run_world.gd",
    "tests/pack_world_evidence.py",
)

REQUIRED_TRACES = (
    "world_idle.json",
    "world_walk.json",
)

REQUIRED_LEDGER = (
    "RL-WORLD-SCHEMA",
    "RL-WORLD-LAYERS",
    "RL-WORLD-OWN",
    "RL-PROP-STATIC",
    "RL-PROP-DYNAMIC",
    "RL-PROP-ONEWAY",
    "RL-PROP-BREAK",
    "RL-PROP-PICKUP",
    "RL-PROP-EXPL",
    "RL-NADE-PROP",
    "RL-SIM-FIXED-60",
)

REQUIRED_KINDS = (
    "static",
    "dynamic",
    "one-way",
    "breakable",
    "pickup",
    "explosive",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")
HARD_SPAWN = re.compile(r"_spawn_(crate|barrel|glass|prop)\b")


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
    session = SESSION.read_text(encoding="utf-8") if SESSION.is_file() else ""
    if "world_owner.spawn_map" not in session:
        errors.append("game_session must spawn props through WorldOwner.spawn_map")
    if HARD_SPAWN.search(session):
        errors.append("game_session must not hard-code per-prop spawn helpers")
    if "_spawn_crate" in session or "PropCrate" in session:
        errors.append("game_session must not name individual prop nodes")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("world_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("world_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("world_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("world_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_schema",
        "outcome_layers",
        "outcome_spawn",
        "outcome_hash",
        "outcome_orphan",
        "outcome_path",
        "outcome_present",
        "outcome_author",
        "outcome_live",
        "outcome_replay",
        "events_all",
        "_record_apply",
        "reject_missing_collision",
        "reject_missing_visual",
        "res://../",
        "is_instance_id_valid",
        "presentation cannot",
    ):
        if needle not in cases:
            errors.append(f"world_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_world = RUN_WORLD.read_text(encoding="utf-8") if RUN_WORLD.is_file() else ""
    if GATE_RUN_ID not in run_world:
        errors.append(f"run_world.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_world:
            errors.append(f"run_world.gd must not reuse {banned}")
    if "SCHEMA_SOURCE=outcome_schema" not in run_world:
        errors.append("run_world SCHEMA banner must cite outcome_schema")
    if "USED_APPLY_ATTEMPTED" not in run_world or "USED_APPLY_SUCCEEDED" not in run_world:
        errors.append("run_world must print attempted/succeeded apply counters")
    if not PACKER.is_file():
        errors.append("missing tests/pack_world_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "orphan" not in packer or "path" not in packer:
            errors.append("packer verdict must require orphan/path, not events alone")
        if "hash" not in packer:
            errors.append("packer must require a stable prop hash")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "WorldCases" not in run_all:
        errors.append("run_all.gd must call WorldCases")
    if "outcome_orphan" not in run_all or "HH_VF_WORLD" not in run_all:
        errors.append("run_all.gd world banner must read outcome_orphan")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not GATE.is_file():
        errors.append("missing data/world/schema.json")
    else:
        gate = json.loads(GATE.read_text(encoding="utf-8"))
        if gate.get("schema") != "vf.world.schema.v1":
            errors.append("world schema id mismatch")
        if gate.get("title") != "Vault Fighters":
            errors.append("world schema title must be Vault Fighters")
        if gate.get("y8_parity_claimed") is True:
            errors.append("world schema claimed Y8 parity")
        for kind in REQUIRED_KINDS:
            if kind not in (gate.get("allowed_kinds") or []):
                errors.append(f"world schema missing kind {kind}")
    if not CATALOG.is_file():
        errors.append("missing data/world/catalog.json")
    else:
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        if payload.get("schema_class") != "assumption":
            errors.append("world schema must stay assumption")
        if payload.get("y8_parity_claimed") is True:
            errors.append("catalog claimed Y8 parity")
        if payload.get("original_exact_numbers_claimed") is True:
            errors.append("catalog claimed original exact numbers")
        if payload.get("title") != "Vault Fighters":
            errors.append("catalog title must be Vault Fighters")
        if payload.get("roll_dive_class") != "unavailable":
            errors.append("Y8 roll/dive observation must stay unavailable")
        if payload.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if payload.get("break_implemented") is True:
            errors.append("break must stay unimplemented this WP")
        if payload.get("chain_implemented") is True:
            errors.append("chain must stay unimplemented this WP")
        specs = payload.get("specs") or {}
        kinds = {str((specs[k] or {}).get("kind", "")) for k in specs}
        for kind in REQUIRED_KINDS:
            if kind not in kinds:
                errors.append(f"catalog missing a spec for kind {kind}")
        for spec in specs.values():
            if not isinstance(spec, dict):
                continue
            if "collision" not in spec:
                errors.append(f"{spec.get('id')} missing collision")
            if "visual" not in spec:
                errors.append(f"{spec.get('id')} missing visual")
            vis = str(((spec.get("visual") or {}).get("path")) or "")
            if not vis.startswith("res://"):
                errors.append(f"{spec.get('id')} visual is not res://")
            if ".." in vis:
                errors.append(f"{spec.get('id')} visual escapes with ..")
            name = str(spec.get("name", ""))
            if TRADEMARK.search(name):
                errors.append(f"spec name uses Superfighters trademark: {name}")
        places = (payload.get("placements") or {}).get("fx_world_open") or []
        if len(places) < 6:
            errors.append("fx_world_open must place all six kinds")
        for name in (payload.get("fixture_names") or {}).values():
            if TRADEMARK.search(str(name)):
                errors.append(f"fixture name uses Superfighters trademark: {name}")
    if not LAYERS.is_file():
        errors.append("missing collision_layers.json")
    else:
        layers = json.loads(LAYERS.read_text(encoding="utf-8"))
        masks = layers.get("prop_masks") or {}
        for kind in REQUIRED_KINDS:
            if kind not in masks:
                errors.append(f"collision_layers missing prop_masks.{kind}")
        if int((layers.get("layers") or {}).get("prop", 0)) != 32:
            errors.append("prop layer bit must stay 32")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing world trace {name}")
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
        errors.append("missing docs/world.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-WORLD-SCHEMA",
            "ledger:RL-WORLD-LAYERS",
            "ledger:RL-WORLD-OWN",
            "ledger:RL-PROP-BREAK",
            "ledger:RL-NADE-PROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "product root",
            "orphan",
        ):
            if needle not in docs:
                errors.append(f"world docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF4-WP1" not in ledger:
        errors.append("ledger missing VF4-WP1 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    for rid in (
        "RL-WORLD-SCHEMA",
        "RL-WORLD-LAYERS",
        "RL-WORLD-OWN",
        "RL-PROP-STATIC",
        "RL-PROP-DYNAMIC",
        "RL-PROP-ONEWAY",
        "RL-PROP-BREAK",
        "RL-PROP-PICKUP",
        "RL-PROP-EXPL",
    ):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF4-WP1 world files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF4-WP1 world files")
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
