#!/usr/bin/env python3
"""VF5-WP6 structure check: six-map VS roster.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_vs_roster.gd). Does not fetch Y8.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "vs_roster.md"
MAPS_DOC = ROOT / "docs" / "maps.md"
CATALOG = ROOT / "data" / "maps" / "catalog.json"
SCHEMA = ROOT / "data" / "maps" / "schema.json"
ARENA = ROOT / "data" / "maps" / "arena_spec.json"
CASES = ROOT / "tests" / "vs_roster_cases.gd"
RUN = ROOT / "tests" / "run_vs_roster.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_vs_roster_evidence.py"
MAPS_GD = ROOT / "src" / "maps.gd"
LANTERN = ROOT / "data" / "maps" / "arenas" / "lantern.json"
GAUGE = ROOT / "data" / "maps" / "arenas" / "gauge.json"
GATE_RUN_ID = "VF5WP6-20260831-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf5-wp6.vs-roster.2"
FORBIDDEN_RUN_IDS = (
    "VF5WP6-20260831-ASIA-SAIGON-01",
    "VF5WP5-20260831-ASIA-SAIGON-07",
    "VF5WP5-20260831-ASIA-SAIGON-06",
    "VF5WP5-20260831-ASIA-SAIGON-05",
    "VF5WP5-20260831-ASIA-SAIGON-01",
    "VF5WP4-20260830-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/maps/arena_spec.gd",
    "src/maps/map_catalog.gd",
    "src/maps.gd",
    "src/app.gd",
    "src/ui/title_screen.gd",
    "src/world/env_body.gd",
    "src/world/world_owner.gd",
    "src/game_session.gd",
    "tests/vs_roster_cases.gd",
    "tests/run_vs_roster.gd",
    "tests/check_vs_roster.py",
    "tests/pack_vs_roster_evidence.py",
    "data/maps/catalog.json",
    "data/maps/schema.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/lantern.json",
    "data/maps/arenas/gauge.json",
    "data/maps/arenas/rooftops.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/hazardous.json",
    "data/world/catalog.json",
    "data/world/env.json",
    "data/world/moving.json",
    "docs/vs_roster.md",
    "docs/lantern.md",
    "docs/gauge.md",
    "docs/maps.md",
    "docs/reference-ledger.md",
)

REQUIRED_LEDGER = (
    "RL-MAP-LANTERN",
    "RL-MAP-GAUGE",
    "RL-MAP-VS-ROSTER",
    "RL-DELTA-MAP-NAMES",
    "RL-SIM-FIXED-60",
    "RL-CTRL-HOLD-AIM",
    "RL-MOVE-ROLL-DIVE",
    "RL-MAP-SUMP",
    "RL-MAP-SKYLINE",
    "RL-MAP-PALLET",
    "RL-MAP-SIGNAL",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")
VS_ORDER = ("rooftops", "storage", "police", "hazardous", "lantern", "gauge")
DISPLAY = {
    "rooftops": "Skyline Relay",
    "storage": "Pallet Annex",
    "police": "Signal Court",
    "hazardous": "Vitriol Sump",
    "lantern": "Lantern Cut",
    "gauge": "Gauge Deck",
}


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
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("vs_roster_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("vs_roster_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("vs_roster_cases must use apply_frames")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_roster",
        "outcome_cycle",
        "outcome_load",
        "outcome_routes",
        "outcome_cover",
        "outcome_cargo",
        "outcome_door",
        "outcome_rotor",
        "outcome_toxic",
        "outcome_water",
        "outcome_lift",
        "outcome_lantern",
        "outcome_gauge",
        "outcome_p2",
        "outcome_bot",
        "outcome_camera",
        "outcome_live",
        "outcome_replay",
        "Lantern Cut",
        "Gauge Deck",
        "Draft Yard",
        "vs_ids",
        "stage_ids",
        "next_vs_map",
        "fighter.wet",
        "dx_dry",
        "dx_wet",
        "sprint_blocked",
        "map_btn.pressed",
        "used_give_weapon",
        "gauge_lift",
        "apply_frames live body",
        "P2_COVERAGE",
        "NOT_AI",
        "coverage",
    ):
        if needle not in cases:
            errors.append(f"vs_roster_cases missing {needle}")
    if re.search(r"give_weapon\s*\(", cases):
        errors.append("vs_roster_cases must not call give_weapon")
    if "app._on_map_cycle()" in cases:
        errors.append("vs_roster_cases must wrap through map_btn.pressed, not _on_map_cycle")
    if 'stage_ids().size() != 4' not in cases and "stage_ids must stay four" not in cases:
        errors.append("vs_roster_cases must keep Stage at four ids")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_vs_roster.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_vs_roster.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_vs_roster must use command_id {COMMAND_ID}")
    if "ROSTER_SOURCE=outcome_roster" not in run or "WATER_SOURCE=outcome_water" not in run:
        errors.append("run_vs_roster banners must cite structured outcomes")
    if "P2_COVERAGE=smoke" not in run or "BOT_COVERAGE=smoke" not in run:
        errors.append("run_vs_roster banners must mark P2/BOT as smoke")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_vs_roster banners must stay honest about AI/parity")
    if "vs_lantern_water" not in run or "vs_gauge_lift" not in run:
        errors.append("run_vs_roster must screenshot lantern water and gauge lift")
    if "frame_post_draw" not in run:
        errors.append("run_vs_roster must wait for frame_post_draw")
    if "_assert_standing_still" not in run:
        errors.append("run_vs_roster must reject lose-overlay landmark stills")
    if not PACKER.is_file():
        errors.append("missing tests/pack_vs_roster_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        if COMMAND_ID not in packer:
            errors.append(f"packer must use command_id {COMMAND_ID}")
        if "identical sha256" not in packer or "stills_pairwise_distinct" not in packer:
            errors.append("packer must fail identical still hashes")
        if "P2_COVERAGE" not in packer or "smoke" not in packer:
            errors.append("packer must record P2/BOT smoke honesty")
        if "live_logs_ok" not in packer:
            errors.append("packer must require live stdout logs")
        if "PROBE" not in packer:
            errors.append("packer must reject PROBE evidence dirs")
        if "1_000_000" not in packer:
            errors.append("packer must reject a stub godot_exe hash")
        if "HH_VF_DIVE" not in packer or "APPLY=1253/1253" not in packer:
            errors.append("packer must keep sewer DIVE MAPS 1253 gate")
        if "src/fighter.gd" not in packer:
            errors.append("packer SOURCE_FILES must include fighter.gd")
        if "leftover_proof" not in packer or "exits_proof" not in packer:
            errors.append("packer must fail-closed on leftover/exit proof files")
        if "dx_wet" not in packer or "map_btn.pressed" not in packer:
            errors.append("packer must require water loco delta and map_btn.pressed wrap")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "VsRosterCases" not in run_all:
        errors.append("run_all.gd must call VsRosterCases")
    if "HH_VF_VS" not in run_all:
        errors.append("run_all.gd must emit HH_VF_VS banner")
    if "P2_COVERAGE=smoke" not in run_all or "BOT_COVERAGE=smoke" not in run_all:
        errors.append("run_all must mark P2/BOT smoke")
    maps_gd = MAPS_GD.read_text(encoding="utf-8") if MAPS_GD.is_file() else ""
    if "func vs_ids()" not in maps_gd:
        errors.append("maps.gd must expose vs_ids")
    if 'return PackedStringArray(["rooftops", "storage", "police", "hazardous"])' not in maps_gd:
        errors.append("maps.gd stage_ids must stay the four Stage maps")
    vs_block = maps_gd[maps_gd.find("func vs_ids()") : maps_gd.find("func next_vs_map(")]
    for mid in VS_ORDER:
        if f'"{mid}"' not in vs_block:
            errors.append(f"maps.gd vs_ids missing {mid}")
    if vs_block.find('"lantern"') > vs_block.find('"gauge"') and '"gauge"' in vs_block:
        errors.append("vs_ids must not be filesystem/alpha order (gauge before lantern)")
    if not CATALOG.is_file() or not ARENA.is_file() or not LANTERN.is_file() or not GAUGE.is_file():
        errors.append("missing lantern/gauge catalog/spec/json")
    else:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        arena = json.loads(ARENA.read_text(encoding="utf-8"))
        lantern = json.loads(LANTERN.read_text(encoding="utf-8"))
        gauge = json.loads(GAUGE.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8")) if SCHEMA.is_file() else {}
        if lantern.get("display_name") != "Lantern Cut":
            errors.append("lantern.json display_name must be Lantern Cut")
        if gauge.get("display_name") != "Gauge Deck":
            errors.append("gauge.json display_name must be Gauge Deck")
        if lantern.get("id") != "lantern" or gauge.get("id") != "gauge":
            errors.append("internal ids stay lantern/gauge")
        if lantern.get("y8_parity_claimed") is True or gauge.get("y8_parity_claimed") is True:
            errors.append("new arenas claimed Y8 parity")
        if lantern.get("title") != "Vault Fighters" or gauge.get("title") != "Vault Fighters":
            errors.append("new arenas title must be Vault Fighters")
        if lantern.get("width") == 64 or gauge.get("width") == 64:
            errors.append("new arenas must not clone the 64-wide Stage silhouette")
        if lantern.get("height") == 16 or gauge.get("height") == 16:
            errors.append("new arenas must not clone the 16-tall Stage silhouette")
        spec_l = (arena.get("maps") or {}).get("lantern") or {}
        spec_g = (arena.get("maps") or {}).get("gauge") or {}
        if spec_l.get("display_name") != "Lantern Cut":
            errors.append("arena spec lantern display must be Lantern Cut")
        if spec_g.get("display_name") != "Gauge Deck":
            errors.append("arena spec gauge display must be Gauge Deck")
        if len(spec_l.get("combat_zones") or []) < 4:
            errors.append("lantern needs 4+ combat zones")
        if len(spec_g.get("combat_zones") or []) < 4:
            errors.append("gauge needs 4+ combat zones")
        if "water" not in (spec_l.get("hazards") or []):
            errors.append("lantern must declare water")
        if catalog.get("lantern_class") != "assumption":
            errors.append("catalog lantern_class must stay assumption")
        if catalog.get("gauge_class") != "assumption":
            errors.append("catalog gauge_class must stay assumption")
        if catalog.get("vs_class") != "assumption":
            errors.append("catalog vs_class must stay assumption")
        required = schema.get("required_live_ids") or []
        for mid in VS_ORDER:
            if mid not in required:
                errors.append(f"schema required_live_ids missing {mid}")
            if mid not in (catalog.get("maps") or {}):
                errors.append(f"catalog missing {mid}")
        if "fx_map_author" not in (catalog.get("maps") or {}):
            errors.append("catalog must keep Draft Yard author map")
        maps = catalog.get("maps") or {}
        extra = [k for k in maps if k not in VS_ORDER and k != "fx_map_author"]
        if extra:
            errors.append(f"hidden catalog maps {extra}")
        for mid, name in DISPLAY.items():
            row = (arena.get("maps") or {}).get(mid) or {}
            if row.get("display_name") != name:
                errors.append(f"arena spec {mid} display must stay {name}")
    ledger = LEDGER.read_text(encoding="utf-8") if LEDGER.is_file() else ""
    for row in REQUIRED_LEDGER:
        if row not in ledger:
            errors.append(f"ledger missing {row}")
    if "Lantern Cut" not in ledger or "Gauge Deck" not in ledger:
        errors.append("ledger must name Lantern Cut and Gauge Deck")
    docs = DOCS.read_text(encoding="utf-8") if DOCS.is_file() else ""
    if "Lantern Cut" not in docs or "Gauge Deck" not in docs:
        errors.append("vs_roster.md must name both new arenas")
    if "Draft Yard" not in docs:
        errors.append("vs_roster.md must say Draft Yard is not VS")
    if "assumption" not in docs:
        errors.append("vs_roster.md must keep assumption honesty")
    maps_doc = MAPS_DOC.read_text(encoding="utf-8") if MAPS_DOC.is_file() else ""
    if "Lantern Cut" not in maps_doc or "Gauge Deck" not in maps_doc:
        errors.append("maps.md must list the two new VS arenas")
    if errors:
        print("FAIL: VF5-WP6 vs roster structure")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: VF5-WP6 vs roster structure")
    print(f"  run_id={GATE_RUN_ID} command_id={COMMAND_ID}")
    print("  vs=rooftops,storage,police,hazardous,lantern,gauge stage=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
