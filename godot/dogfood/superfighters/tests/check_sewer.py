#!/usr/bin/env python3
"""VF5-WP5 structure check: Vitriol Sump sewer arena.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_sewer.gd). Does not fetch Y8.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "reference-ledger.md"
TITLE = ROOT / "src" / "ui" / "title_screen.gd"
DOCS = ROOT / "docs" / "sewer.md"
MAPS_DOC = ROOT / "docs" / "maps.md"
CATALOG = ROOT / "data" / "maps" / "catalog.json"
ARENA = ROOT / "data" / "maps" / "arena_spec.json"
SUMP = ROOT / "data" / "maps" / "arenas" / "hazardous.json"
WORLD = ROOT / "data" / "world" / "catalog.json"
ENV = ROOT / "data" / "world" / "env.json"
CASES = ROOT / "tests" / "sewer_cases.gd"
RUN = ROOT / "tests" / "run_sewer.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_sewer_evidence.py"
MAP_CASES = ROOT / "tests" / "map_cases.gd"
ROOF = ROOT / "data" / "maps" / "arenas" / "rooftops.json"
STORE = ROOT / "data" / "maps" / "arenas" / "storage.json"
POLICE = ROOT / "data" / "maps" / "arenas" / "police.json"
GATE_RUN_ID = "VF5WP5-20260831-ASIA-SAIGON-07"
COMMAND_ID = "cmd.vf5-wp5.vitriol-sump.8"
FORBIDDEN_RUN_IDS = (
    "VF5WP5-20260831-ASIA-SAIGON-06",
    "VF5WP5-20260831-ASIA-SAIGON-05",
    "VF5WP5-20260831-ASIA-SAIGON-04",
    "VF5WP5-20260831-ASIA-SAIGON-03",
    "VF5WP5-20260831-ASIA-SAIGON-02",
    "VF5WP5-20260831-ASIA-SAIGON-01",
    "VF5WP5-20260830-ASIA-SAIGON-01",
    "VF5WP4-20260830-ASIA-SAIGON-01",
    "VF5WP3-20260830-ASIA-SAIGON-01",
    "VF5WP2-20260830-ASIA-SAIGON-02",
    "VF5WP2-20260830-ASIA-SAIGON-01",
    "VF5WP1-20260830-ASIA-SAIGON-01",
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
    "tests/sewer_cases.gd",
    "tests/run_sewer.gd",
    "tests/check_sewer.py",
    "tests/pack_sewer_evidence.py",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/hazardous.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/rooftops.json",
    "data/world/catalog.json",
    "data/world/env.json",
    "docs/sewer.md",
    "docs/provenance.md",
)

REQUIRED_LEDGER = (
    "RL-MAP-SUMP",
    "RL-DELTA-MAP-NAMES",
    "RL-SIM-FIXED-60",
    "RL-CTRL-HOLD-AIM",
    "RL-MOVE-ROLL-DIVE",
    "RL-NADE-PROP",
    "RL-MAP-GRAPH",
    "RL-MAP-PALLET",
    "RL-MAP-SKYLINE",
    "RL-MAP-SIGNAL",
    "RL-ENV-DEFER",
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
        if TRADEMARK.search(text) and "trademark" not in text.lower():
            errors.append(f"{rel} contains Superfighters trademark")
    title = TITLE.read_text(encoding="utf-8") if TITLE.is_file() else ""
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("sewer_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("sewer_cases must not call action_press")
    if re.search(r"\.give_weapon\s*\(", cases):
        errors.append("sewer_cases must not cheat inventory with give_weapon")
    if re.search(r"fire_cd\s*=", cases):
        errors.append("sewer_cases must not poke fire_cd as tactic proof")
    if "apply_frames" not in cases:
        errors.append("sewer_cases must use apply_frames")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_name",
        "outcome_graph",
        "outcome_toxic",
        "outcome_dive",
        "outcome_roll",
        "outcome_cargo",
        "outcome_spawn",
        "outcome_camera",
        "outcome_tactic",
        "outcome_p1",
        "outcome_p2",
        "outcome_bot",
        "outcome_live",
        "outcome_replay",
        "outcome_variants",
        "trajectory",
        "coverage",
        "replay live",
        "apply_frames replay hash",
        "three apply_frames morphologies",
        "Vitriol Sump",
        "Hazardous",
        "sump_lip",
        "sump_wade",
        "sump_cargo_hang",
        "climb_up_on_ladder",
        "apply_frames live body",
        'PackedStringArray(["up"])',
        "on_ladder",
        "take_env_tick ignores invuln",
        "pickup_id",
        "used_give_weapon",
        "acid_at_kill",
        "item_pickup",
        "world pickup",
    ):
        if needle not in cases:
            errors.append(f"sewer_cases missing {needle}")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_sewer.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_sewer.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_sewer must use command_id {COMMAND_ID}")
    if "P1_SOURCE=outcome_p1" not in run or "TOXIC_SOURCE=outcome_toxic" not in run:
        errors.append("run_sewer banners must cite structured outcomes")
    if "P2_COVERAGE=smoke" not in run or "BOT_COVERAGE=smoke" not in run:
        errors.append("run_sewer banners must mark P2/BOT as smoke")
    if "NOT_AI=1" not in run or "NOT_Y8_PARITY=1" not in run:
        errors.append("run_sewer banners must stay honest about AI/parity")
    if "VARIANTS_SOURCE=outcome_variants" not in run:
        errors.append("run_sewer banners must cite variants")
    if "sewer_pipes" not in run or "sewer_toxic" not in run:
        errors.append("run_sewer must screenshot pipes and toxic landmarks")
    if "frame_post_draw" not in run:
        errors.append("run_sewer must wait for frame_post_draw")
    if "_assert_standing_still" not in run:
        errors.append("run_sewer must reject lose-overlay landmark stills")
    if not PACKER.is_file():
        errors.append("missing tests/pack_sewer_evidence.py")
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
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "SewerCases" not in run_all:
        errors.append("run_all.gd must call SewerCases")
    if "HH_VF_SEWER" not in run_all:
        errors.append("run_all.gd must emit HH_VF_SEWER banner")
    if "P2_COVERAGE=smoke" not in run_all or "BOT_COVERAGE=smoke" not in run_all:
        errors.append("run_all sewer banner must mark P2/BOT smoke")
    map_cases = MAP_CASES.read_text(encoding="utf-8") if MAP_CASES.is_file() else ""
    if "Vitriol Sump" not in map_cases:
        errors.append("map_cases must expect Vitriol Sump")
    if "Signal Court" not in map_cases:
        errors.append("map_cases must keep Signal Court")
    if "Pallet Annex" not in map_cases:
        errors.append("map_cases must keep Pallet Annex")
    if "Skyline Relay" not in map_cases:
        errors.append("map_cases must keep Skyline Relay")
    if not CATALOG.is_file() or not ARENA.is_file() or not SUMP.is_file():
        errors.append("missing hazardous catalog/spec/json")
    else:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        arena = json.loads(ARENA.read_text(encoding="utf-8"))
        sump = json.loads(SUMP.read_text(encoding="utf-8"))
        if sump.get("display_name") != "Vitriol Sump":
            errors.append("hazardous.json display_name must be Vitriol Sump")
        if sump.get("display_name") == "Hazardous":
            errors.append("must retire Hazardous display")
        if sump.get("id") != "hazardous":
            errors.append("internal map id stays hazardous")
        if sump.get("y8_parity_claimed") is True:
            errors.append("hazardous claimed Y8 parity")
        if sump.get("title") != "Vault Fighters":
            errors.append("hazardous title must be Vault Fighters")
        spec = (arena.get("maps") or {}).get("hazardous") or {}
        if spec.get("display_name") != "Vitriol Sump":
            errors.append("arena spec hazardous display must be Vitriol Sump")
        if int(spec.get("elevations") or 0) < 3:
            errors.append("arena spec must declare 3+ elevations")
        hazards = spec.get("hazards") or []
        if "toxic" not in hazards:
            errors.append("arena spec must declare toxic")
        zones = spec.get("combat_zones") or []
        if len(zones) < 6:
            errors.append("arena spec must list combat zones")
        zids = {str(z.get("id")) for z in zones if isinstance(z, dict)}
        for zid in ("sump_lip", "sump_wade", "mid_west", "west_high"):
            if zid not in zids:
                errors.append(f"arena spec missing combat zone {zid}")
        if catalog.get("sump_class") != "assumption":
            errors.append("catalog sump_class must stay assumption")
        if catalog.get("sump_ledger") != "RL-MAP-SUMP":
            errors.append("catalog must cite RL-MAP-SUMP")
        if catalog.get("signal_class") != "assumption":
            errors.append("catalog signal_class must stay assumption")
        if catalog.get("pallet_class") != "assumption":
            errors.append("catalog pallet_class must stay assumption")
        if catalog.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if (arena.get("maps") or {}).get("rooftops", {}).get("display_name") != "Skyline Relay":
            errors.append("Skyline Relay display must stay")
        if (arena.get("maps") or {}).get("storage", {}).get("display_name") != "Pallet Annex":
            errors.append("Pallet Annex display must stay")
        if (arena.get("maps") or {}).get("police", {}).get("display_name") != "Signal Court":
            errors.append("Signal Court display must stay")
    if ROOF.is_file():
        roof = json.loads(ROOF.read_text(encoding="utf-8"))
        if roof.get("display_name") != "Skyline Relay":
            errors.append("must not rewrite Skyline Relay display")
    if STORE.is_file():
        store = json.loads(STORE.read_text(encoding="utf-8"))
        if store.get("display_name") != "Pallet Annex":
            errors.append("must not rewrite Pallet Annex display")
    if POLICE.is_file():
        police = json.loads(POLICE.read_text(encoding="utf-8"))
        if police.get("display_name") != "Signal Court":
            errors.append("must not rewrite Signal Court display")
    if not WORLD.is_file():
        errors.append("missing world catalog")
    else:
        world = json.loads(WORLD.read_text(encoding="utf-8"))
        places = (world.get("placements") or {}).get("hazardous") or []
        ids = {str(p.get("id")) for p in places if isinstance(p, dict)}
        if "sump_cargo_hang" not in ids:
            errors.append("world catalog must place hanging cargo")
        roof_ids = {
            str(p.get("id"))
            for p in (world.get("placements") or {}).get("rooftops") or []
            if isinstance(p, dict)
        }
        if "sky_cover_wood" not in roof_ids:
            errors.append("must keep Skyline Relay cover placements")
        store_ids = {
            str(p.get("id"))
            for p in (world.get("placements") or {}).get("storage") or []
            if isinstance(p, dict)
        }
        if "pallet_cover_wood" not in store_ids:
            errors.append("must keep Pallet Annex cover placements")
        police_ids = {
            str(p.get("id"))
            for p in (world.get("placements") or {}).get("police") or []
            if isinstance(p, dict)
        }
        if "signal_cover_wood" not in police_ids:
            errors.append("must keep Signal Court cover placements")
    if not ENV.is_file():
        errors.append("missing env.json")
    else:
        env = json.loads(ENV.read_text(encoding="utf-8"))
        acids = [
            p
            for p in (env.get("placements") or {}).get("hazardous") or []
            if isinstance(p, dict) and str(p.get("spec", "")) == "acid_trench"
        ]
        if len(acids) < 8:
            errors.append("env.json must place a wide toxic pool on hazardous")
        police_env = {
            str(p.get("id"))
            for p in (env.get("placements") or {}).get("police") or []
            if isinstance(p, dict)
        }
        if "signal_rotor" not in police_env:
            errors.append("must keep Signal Court rotor")
    if not DOCS.is_file():
        errors.append("missing docs/sewer.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "Vitriol Sump",
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MAP-SUMP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "RL-DELTA-MAP-NAMES",
            "P2/bot",
        ):
            if needle not in docs:
                errors.append(f"sewer docs missing {needle}")
        if "Hazardous" in docs and "retire" not in docs.lower() and "retired" not in docs.lower():
            errors.append("sewer docs must retire Hazardous display")
    if MAPS_DOC.is_file():
        maps_doc = MAPS_DOC.read_text(encoding="utf-8")
        if "Vitriol Sump" not in maps_doc:
            errors.append("maps.md must mention Vitriol Sump")
        if "Signal Court" not in maps_doc:
            errors.append("maps.md must keep Signal Court")
        if "Pallet Annex" not in maps_doc:
            errors.append("maps.md must keep Pallet Annex")
        if "Skyline Relay" not in maps_doc:
            errors.append("maps.md must keep Skyline Relay")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF5-WP5" not in ledger:
        errors.append("ledger missing VF5-WP5 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    if "Vitriol Sump" not in ledger:
        errors.append("ledger must name Vitriol Sump")
    sump_row = _row(ledger, "RL-MAP-SUMP")
    if "`observed`" in sump_row and "not observed" not in sump_row and "Do **not** cite as observed" not in sump_row:
        errors.append("RL-MAP-SUMP must not be marked observed")
    delta = _row(ledger, "RL-DELTA-MAP-NAMES")
    if "Vitriol Sump" not in delta:
        errors.append("RL-DELTA-MAP-NAMES must resolve Hazardous to Vitriol Sump")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    ev_dir = ROOT / "docs" / "evidence" / GATE_RUN_ID
    for log_name in ("run_sewer.headless.log", "run_sewer.window.log"):
        log_path = ev_dir / log_name
        if not log_path.is_file():
            continue
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "Godot Engine v4.7.1" not in log_text:
            errors.append(f"{log_name} is not live Godot stdout")
        ev_line = ""
        for line in log_text.splitlines():
            if line.startswith("HH_VF_STAT EVIDENCE_DIR="):
                ev_line = line.split("=", 1)[1]
                break
        if GATE_RUN_ID not in ev_line:
            errors.append(f"{log_name} EVIDENCE_DIR must be official {GATE_RUN_ID}")
        if "PROBE" in ev_line:
            errors.append(f"{log_name} EVIDENCE_DIR must not use PROBE")
        if "USED_STEP_FIXED=0" not in log_text:
            errors.append(f"{log_name} must print used_step_fixed=0")
    ev_screens = ev_dir / "screens"
    if ev_screens.is_dir():
        named = {
            "setup": _pick_still(ev_screens, "setup"),
            "title": _pick_still(ev_screens, "title"),
            "pipes": _pick_still(ev_screens, "pipes"),
            "crossing": _pick_still(ev_screens, "crossing"),
            "cargo": _pick_still(ev_screens, "cargo"),
            "lip": _pick_still(ev_screens, "lip"),
            "toxic": _pick_still(ev_screens, "toxic"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    if errors:
        print("FAIL: Vault Fighters VF5-WP5 Vitriol Sump files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF5-WP5 Vitriol Sump files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} ledger={len(REQUIRED_LEDGER)}")
    print(f"  run_id={GATE_RUN_ID}")
    return 0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pick_still(folder: Path, needle: str) -> Path | None:
    matches = sorted(folder.glob(f"*{needle}*.png"))
    return matches[0] if matches else None


def stills_pairwise_distinct(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    rows: list[tuple[str, str, int]] = []
    for path in paths:
        if path is None or not path.is_file():
            errors.append(f"missing still {path}")
            continue
        digest = _sha256_file(path)
        size = path.stat().st_size
        rows.append((path.name, digest, size))
    i = 0
    while i < len(rows):
        j = i + 1
        while j < len(rows):
            if rows[i][1] == rows[j][1]:
                errors.append(
                    f"{rows[i][0]} and {rows[j][0]} identical sha256 {rows[i][1]}"
                )
            if rows[i][1] == rows[j][1] and rows[i][2] == rows[j][2]:
                errors.append(
                    f"{rows[i][0]} and {rows[j][0]} identical size+hash"
                )
            j += 1
        i += 1
    return errors


def _row(text: str, rid: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {rid} "):
            return line
    return ""


if __name__ == "__main__":
    sys.exit(main())
