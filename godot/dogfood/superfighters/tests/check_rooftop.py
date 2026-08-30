#!/usr/bin/env python3
"""VF5-WP2 structure check: Skyline Relay rooftop arena.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_rooftop.gd). Does not fetch Y8.
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
DOCS = ROOT / "docs" / "rooftop.md"
MAPS_DOC = ROOT / "docs" / "maps.md"
CATALOG = ROOT / "data" / "maps" / "catalog.json"
ARENA = ROOT / "data" / "maps" / "arena_spec.json"
ROOF = ROOT / "data" / "maps" / "arenas" / "rooftops.json"
WORLD = ROOT / "data" / "world" / "catalog.json"
CASES = ROOT / "tests" / "rooftop_cases.gd"
RUN = ROOT / "tests" / "run_rooftop.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_rooftop_evidence.py"
MAP_CASES = ROOT / "tests" / "map_cases.gd"
GATE_RUN_ID = "VF5WP2-20260830-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf5-wp2.skyline-relay.2"
FORBIDDEN_RUN_IDS = (
    "VF5WP2-20260830-ASIA-SAIGON-01",
    "VF5WP1-20260830-ASIA-SAIGON-01",
    "VF4WP5-20260830-ASIA-SAIGON-01",
    "VF4WP4-20260830-ASIA-SAIGON-02",
    "VF4WP4-20260830-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/maps/arena_spec.gd",
    "src/maps/map_graph.gd",
    "src/maps/map_catalog.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/ui/title_screen.gd",
    "src/app.gd",
    "tests/rooftop_cases.gd",
    "tests/run_rooftop.gd",
    "tests/check_rooftop.py",
    "tests/pack_rooftop_evidence.py",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/rooftops.json",
    "docs/rooftop.md",
)

REQUIRED_LEDGER = (
    "RL-MAP-SKYLINE",
    "RL-DELTA-MAP-NAMES",
    "RL-SIM-FIXED-60",
    "RL-CTRL-HOLD-AIM",
    "RL-MOVE-ROLL-DIVE",
    "RL-NADE-PROP",
    "RL-MAP-GRAPH",
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
    if "Maps.display_name" not in title:
        errors.append("title map button must read Maps.display_name")
    if "Map: Rooftops" in title:
        errors.append("title still hardcodes Rooftops")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("rooftop_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("rooftop_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("rooftop_cases must use apply_frames")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_name",
        "outcome_zone",
        "outcome_cover",
        "outcome_p1",
        "outcome_p2",
        "outcome_bot",
        "outcome_pit",
        "outcome_fallback",
        "outcome_live",
        "outcome_replay",
        "Skyline Relay",
        "west_spire",
        "east_deck",
        "west_spire_standing",
        "climb_up_on_ladder",
        "apply_frames live body",
        'PackedStringArray(["up"])',
        "on_ladder",
    ):
        if needle not in cases:
            errors.append(f"rooftop_cases missing {needle}")
    run = RUN.read_text(encoding="utf-8") if RUN.is_file() else ""
    if GATE_RUN_ID not in run:
        errors.append(f"run_rooftop.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run:
            errors.append(f"run_rooftop.gd must not reuse {banned}")
    if COMMAND_ID not in run:
        errors.append(f"run_rooftop must use command_id {COMMAND_ID}")
    if "P1_SOURCE=outcome_p1" not in run or "BOT_SOURCE=outcome_bot" not in run:
        errors.append("run_rooftop banners must cite structured outcomes")
    if "rooftop_bridge" not in run or "rooftop_pit" not in run:
        errors.append("run_rooftop must screenshot landmarks")
    if "frame_post_draw" not in run:
        errors.append("run_rooftop must wait for frame_post_draw")
    if "await RooftopCasesScript.stage_bridge" not in run:
        errors.append("run_rooftop must await async stage_bridge")
    if "_assert_standing_still" not in run:
        errors.append("run_rooftop must reject lose-overlay landmark stills")
    if 'PackedStringArray(["up"])' not in cases and '["up"]' not in cases:
        errors.append("rooftop_cases must hold up on a ladder")
    if "await SimReplay.sync_physics(app)" not in cases:
        errors.append("stage_* must sync_physics before apply_frames")
    if not PACKER.is_file():
        errors.append("missing tests/pack_rooftop_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        if COMMAND_ID not in packer:
            errors.append(f"packer must use command_id {COMMAND_ID}")
        if "identical sha256" not in packer or "stills_pairwise_distinct" not in packer:
            errors.append("packer must fail identical still hashes")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "RooftopCases" not in run_all:
        errors.append("run_all.gd must call RooftopCases")
    if "HH_VF_ROOF" not in run_all:
        errors.append("run_all.gd must emit HH_VF_ROOF banner")
    map_cases = MAP_CASES.read_text(encoding="utf-8") if MAP_CASES.is_file() else ""
    if "Skyline Relay" not in map_cases:
        errors.append("map_cases must expect Skyline Relay")
    if not CATALOG.is_file() or not ARENA.is_file() or not ROOF.is_file():
        errors.append("missing rooftops catalog/spec/json")
    else:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        arena = json.loads(ARENA.read_text(encoding="utf-8"))
        roof = json.loads(ROOF.read_text(encoding="utf-8"))
        if roof.get("display_name") != "Skyline Relay":
            errors.append("rooftops.json display_name must be Skyline Relay")
        if roof.get("id") != "rooftops":
            errors.append("internal map id stays rooftops")
        if roof.get("y8_parity_claimed") is True:
            errors.append("rooftops claimed Y8 parity")
        if roof.get("title") != "Vault Fighters":
            errors.append("rooftops title must be Vault Fighters")
        roof_spec = (arena.get("maps") or {}).get("rooftops") or {}
        if roof_spec.get("display_name") != "Skyline Relay":
            errors.append("arena spec rooftops display must be Skyline Relay")
        if int(roof_spec.get("elevations") or 0) < 3:
            errors.append("arena spec must declare 3+ elevations")
        zones = roof_spec.get("combat_zones") or []
        if len(zones) < 3:
            errors.append("arena spec must list combat zones")
        ys = {int(z.get("y", -1)) for z in zones if isinstance(z, dict)}
        if len(ys) < 3:
            errors.append("combat zones must span 3+ elevations")
        if catalog.get("skyline_class") != "assumption":
            errors.append("catalog skyline_class must stay assumption")
        if catalog.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        for name in (
            (arena.get("maps") or {}).get("storage", {}).get("display_name"),
            (arena.get("maps") or {}).get("police", {}).get("display_name"),
            (arena.get("maps") or {}).get("hazardous", {}).get("display_name"),
        ):
            if TRADEMARK.search(str(name or "")):
                errors.append(f"remaining live display uses trademark: {name}")
    if not WORLD.is_file():
        errors.append("missing world catalog")
    else:
        world = json.loads(WORLD.read_text(encoding="utf-8"))
        places = (world.get("placements") or {}).get("rooftops") or []
        ids = {str(p.get("id")) for p in places if isinstance(p, dict)}
        specs = {str(p.get("spec")) for p in places if isinstance(p, dict)}
        if "sky_cover_wood" not in ids or "sky_cover_glass" not in ids:
            errors.append("world catalog must place Skyline Relay cover")
        if "crate_breakable" not in specs or "pane_glass" not in specs:
            errors.append("Skyline Relay cover must use original break specs")
    if not DOCS.is_file():
        errors.append("missing docs/rooftop.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "Skyline Relay",
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MAP-SKYLINE",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "RL-DELTA-MAP-NAMES",
        ):
            if needle not in docs:
                errors.append(f"rooftop docs missing {needle}")
    if MAPS_DOC.is_file():
        maps_doc = MAPS_DOC.read_text(encoding="utf-8")
        if "Skyline Relay" not in maps_doc:
            errors.append("maps.md must mention Skyline Relay")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF5-WP2" not in ledger:
        errors.append("ledger missing VF5-WP2 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    sky = _row(ledger, "RL-MAP-SKYLINE")
    if "`observed`" in sky and "not observed" not in sky and "Do **not** cite as observed" not in sky:
        errors.append("RL-MAP-SKYLINE must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    ev_screens = ROOT / "docs" / "evidence" / GATE_RUN_ID / "screens"
    if ev_screens.is_dir():
        named = {
            "setup": _pick_still(ev_screens, "setup"),
            "title": _pick_still(ev_screens, "title"),
            "bridge": _pick_still(ev_screens, "bridge"),
            "cover": _pick_still(ev_screens, "cover"),
            "pit": _pick_still(ev_screens, "pit"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    if errors:
        print("FAIL: Vault Fighters VF5-WP2 Skyline Relay files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF5-WP2 Skyline Relay files")
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
