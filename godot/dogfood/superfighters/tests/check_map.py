#!/usr/bin/env python3
"""VF5-WP1 structure check: layered maps, validator, semantic author.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_map.gd). Does not fetch Y8.
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
DOCS = ROOT / "docs" / "maps.md"
CATALOG = ROOT / "data" / "maps" / "catalog.json"
SCHEMA = ROOT / "data" / "maps" / "schema.json"
ARENA = ROOT / "data" / "maps" / "arena_spec.json"
CASES = ROOT / "tests" / "map_cases.gd"
RUN_MAP = ROOT / "tests" / "run_map.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_map_evidence.py"
MAPS_GD = ROOT / "src" / "maps.gd"
TRACE = ROOT / "tests" / "traces" / "maps" / "map_author.json"
GATE_RUN_ID = "VF5WP1-20260830-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF4WP5-20260830-ASIA-SAIGON-01",
    "VF4WP4-20260830-ASIA-SAIGON-02",
    "VF4WP4-20260830-ASIA-SAIGON-01",
    "VF4WP3-20260830-ASIA-SAIGON-02",
    "VF4WP3-20260830-ASIA-SAIGON-01",
    "VF4WP2-20260829-ASIA-SAIGON-01",
    "VF4WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/maps/map_codec.gd",
    "src/maps/map_catalog.gd",
    "src/maps/map_graph.gd",
    "src/maps/map_validator.gd",
    "src/maps/map_author.gd",
    "src/maps/arena_spec.gd",
    "src/maps.gd",
    "src/arena.gd",
    "tests/map_cases.gd",
    "tests/run_map.gd",
    "tests/pack_map_evidence.py",
    "data/maps/schema.json",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/rooftops.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/hazardous.json",
    "data/maps/arenas/fx_map_author.json",
)

REQUIRED_LEDGER = (
    "RL-MAP-LAYERS",
    "RL-MAP-GRAPH",
    "RL-MAP-VALID",
    "RL-MAP-AUTHOR",
    "RL-SIM-FIXED-60",
    "RL-CTRL-HOLD-AIM",
    "RL-MOVE-ROLL-DIVE",
    "RL-NADE-PROP",
)

TRADEMARK = re.compile(r"Superfighters|Super Fighter")
ASCII_HARDCODE = re.compile(
    r'return PackedStringArray\(\[\s*"\.\.\.\.\.\.\.\.'
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
    maps_gd = MAPS_GD.read_text(encoding="utf-8") if MAPS_GD.is_file() else ""
    if "func _rooftops(" in maps_gd or "func _storage(" in maps_gd:
        errors.append("maps.gd must not keep hardcoded ASCII arena functions")
    if ASCII_HARDCODE.search(maps_gd):
        errors.append("maps.gd still embeds a 64-wide ASCII prototype")
    if "MapCatalog.has_id" not in maps_gd:
        errors.append("maps.gd must read layered catalog first")
    arena = (ROOT / "src" / "arena.gd").read_text(encoding="utf-8")
    if "MapCatalog.document" not in arena or "_paint_layer" not in arena:
        errors.append("arena.gd must paint from layered documents")
    if "Maps.grid(map_id)" in arena and "_paint_layer" not in arena:
        errors.append("arena.gd still paints only from ASCII grid")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("map_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("map_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("map_cases must use apply_frames")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_schema",
        "outcome_roundtrip",
        "outcome_graph",
        "outcome_reject",
        "outcome_author",
        "outcome_live",
        "outcome_replay",
    ):
        if needle not in cases:
            errors.append(f"map_cases missing {needle}")
    run_map = RUN_MAP.read_text(encoding="utf-8") if RUN_MAP.is_file() else ""
    if GATE_RUN_ID not in run_map:
        errors.append(f"run_map.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_map:
            errors.append(f"run_map.gd must not reuse {banned}")
    if "ROUNDTRIP_SOURCE=outcome_roundtrip" not in run_map:
        errors.append("run_map ROUNDTRIP banner must cite outcome_roundtrip")
    if "AUTHOR_SOURCE=outcome_author" not in run_map:
        errors.append("run_map AUTHOR banner must cite outcome_author")
    if "cmd.vf5-wp1.map-schema.1" not in run_map:
        errors.append("run_map must use command_id cmd.vf5-wp1.map-schema.1")
    if "map_author" not in run_map or "map_rooftops" not in run_map:
        errors.append("run_map must screenshot authored and live maps")
    if "frame_post_draw" not in run_map:
        errors.append("run_map must wait for frame_post_draw before DoD stills")
    if "on_floor" not in run_map:
        errors.append("run_map DoD stills must require on_floor")
    if not PACKER.is_file():
        errors.append("missing tests/pack_map_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "identical sha256" not in packer or "size+hash" not in packer:
            errors.append("packer must fail identical still hashes or size+hash")
        if "stills_pairwise_distinct" not in packer:
            errors.append("packer must run stills_pairwise_distinct")
        if "cmd.vf5-wp1.map-schema.1" not in packer:
            errors.append("packer must use command_id cmd.vf5-wp1.map-schema.1")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "MapCases" not in run_all:
        errors.append("run_all.gd must call MapCases")
    if "outcome_roundtrip" not in run_all or "HH_VF_MAP" not in run_all:
        errors.append("run_all.gd map banner must read outcome_roundtrip")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not CATALOG.is_file() or not SCHEMA.is_file():
        errors.append("missing map catalog/schema")
    else:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        if catalog.get("title") != "Vault Fighters" or schema.get("title") != "Vault Fighters":
            errors.append("map catalog/schema title must be Vault Fighters")
        if catalog.get("layered_maps") is not True:
            errors.append("catalog layered_maps must be true")
        if catalog.get("ascii_maps_kept") is not False:
            errors.append("catalog ascii_maps_kept must be false")
        if catalog.get("live_c_b_tiles") is not True:
            errors.append("catalog must keep live c/b tiles")
        if catalog.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        maps = catalog.get("maps") or {}
        for mid in (
            "rooftops",
            "storage",
            "police",
            "hazardous",
            "lantern",
            "gauge",
            "fx_map_author",
        ):
            if mid not in maps:
                errors.append(f"catalog missing {mid}")
        layers = schema.get("layers") or []
        for layer in ("solid", "one_way", "ladder", "hazard", "prop", "spawn", "pickup"):
            if layer not in layers:
                errors.append(f"schema missing layer {layer}")
    if not ARENA.is_file():
        errors.append("missing arena_spec.json")
    else:
        arena_spec = json.loads(ARENA.read_text(encoding="utf-8"))
        if arena_spec.get("ascii_maps_kept") is not False:
            errors.append("arena spec ASCII source must be retired")
        if arena_spec.get("layered_maps") is not True:
            errors.append("arena spec must use layered maps")
        if arena_spec.get("live_c_b_tiles") is not True:
            errors.append("arena spec must keep live c/b tiles")
        names = {
            mid: (row or {}).get("display_name", "")
            for mid, row in (arena_spec.get("maps") or {}).items()
        }
        if names.get("fx_map_author") != "Draft Yard":
            errors.append("authored map display name must be Draft Yard")
        for name in names.values():
            if TRADEMARK.search(str(name)):
                errors.append(f"arena spec display name uses Superfighters trademark: {name}")
    if not TRACE.is_file():
        errors.append("missing map_author command trace")
    else:
        raw = TRACE.read_text(encoding="utf-8")
        trace = json.loads(raw)
        if trace.get("kind") != "official":
            errors.append("map_author kind must be official")
        if trace.get("used_step_fixed") is not False:
            errors.append("map_author must set used_step_fixed false")
        if trace.get("y8_parity_claimed") is True:
            errors.append("map_author claimed Y8 parity")
        if trace.get("title") != "Vault Fighters":
            errors.append("map_author title must be Vault Fighters")
        if "teleport" in raw or "force_kill" in raw:
            errors.append("map_author official trace contains teleport/force_kill")
        if not trace.get("commands"):
            errors.append("map_author must list semantic commands")
    if not DOCS.is_file():
        errors.append("missing docs/maps.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-MAP-LAYERS",
            "ledger:RL-MAP-GRAPH",
            "ledger:RL-MAP-VALID",
            "ledger:RL-MAP-AUTHOR",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "Draft Yard",
        ):
            if needle not in docs:
                errors.append(f"map docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF5-WP1" not in ledger:
        errors.append("ledger missing VF5-WP1 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    ev_screens = ROOT / "docs" / "evidence" / GATE_RUN_ID / "screens"
    if ev_screens.is_dir():
        named = {
            "setup": _pick_still(ev_screens, "setup"),
            "rooftops": _pick_still(ev_screens, "rooftops"),
            "storage": _pick_still(ev_screens, "storage"),
            "police": _pick_still(ev_screens, "police"),
            "hazardous": _pick_still(ev_screens, "hazardous"),
            "author": _pick_still(ev_screens, "author"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    for rid in ("RL-MAP-LAYERS", "RL-MAP-GRAPH", "RL-MAP-VALID", "RL-MAP-AUTHOR"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF5-WP1 map files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF5-WP1 map files")
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
