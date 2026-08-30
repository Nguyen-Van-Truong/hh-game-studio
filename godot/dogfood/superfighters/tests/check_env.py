#!/usr/bin/env python3
"""VF4-WP5 structure check: ArenaSpec, zones, water, rotor, fall.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_env.gd). Does not fetch Y8.
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
DOCS = ROOT / "docs" / "env.md"
CATALOG = ROOT / "data" / "world" / "catalog.json"
HAZARD = ROOT / "data" / "world" / "hazard.json"
ENV = ROOT / "data" / "world" / "env.json"
ARENA = ROOT / "data" / "maps" / "arena_spec.json"
CASES = ROOT / "tests" / "env_cases.gd"
RUN_ENV = ROOT / "tests" / "run_env.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_env_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "env"
GATE_RUN_ID = "VF4WP5-20260830-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    "VF4WP4-20260830-ASIA-SAIGON-02",
    "VF4WP4-20260830-ASIA-SAIGON-01",
    "VF4WP3-20260830-ASIA-SAIGON-02",
    "VF4WP3-20260830-ASIA-SAIGON-01",
    "VF4WP2-20260829-ASIA-SAIGON-01",
    "VF4WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/world/env_spec.gd",
    "src/world/env_body.gd",
    "src/maps/arena_spec.gd",
    "src/world/world_owner.gd",
    "src/maps.gd",
    "src/game_session.gd",
    "src/fighter.gd",
    "tests/env_cases.gd",
    "tests/run_env.gd",
    "tests/pack_env_evidence.py",
    "data/world/env.json",
    "data/maps/arena_spec.json",
    "assets/art/zone_acid.png",
    "assets/art/zone_water.png",
    "assets/art/zone_void.png",
    "assets/art/prop_rotor.png",
)

REQUIRED_TRACES = (
    "env_instant.json",
    "env_toxic.json",
    "env_toxic_death.json",
    "env_water.json",
    "env_rotor.json",
    "env_fall.json",
    "env_yard.json",
)

REQUIRED_LEDGER = (
    "RL-ENV-INSTANT",
    "RL-ENV-DEFER",
    "RL-ENV-WATER",
    "RL-ENV-ROTOR",
    "RL-ENV-SPAWN",
    "RL-ENV-ARENA",
    "RL-MOVE-FALL",
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
    owner = (ROOT / "src" / "world" / "world_owner.gd").read_text(encoding="utf-8")
    if "_step_envs" not in owner or "env_enter_events" not in owner:
        errors.append("world_owner must step env zones and count enter events")
    if "_spawn_env" not in owner:
        errors.append("world_owner must spawn env from env.json")
    session = (ROOT / "src" / "game_session.gd").read_text(encoding="utf-8")
    if "_spawn_crate" in session or "PropCrate" in session:
        errors.append("game_session must not name individual prop nodes")
    fighter = (ROOT / "src" / "fighter.gd").read_text(encoding="utf-8")
    if "take_env_tick" not in fighter or "die_env" not in fighter:
        errors.append("fighter must apply env ticks and instant die_env")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("env_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("env_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("env_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("env_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_instant",
        "outcome_toxic",
        "outcome_water",
        "outcome_rotor",
        "outcome_fall",
        "outcome_spawn",
        "outcome_pause",
        "outcome_reset",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"env_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_env = RUN_ENV.read_text(encoding="utf-8") if RUN_ENV.is_file() else ""
    if GATE_RUN_ID not in run_env:
        errors.append(f"run_env.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_env:
            errors.append(f"run_env.gd must not reuse {banned}")
    if "INSTANT_SOURCE=outcome_instant" not in run_env:
        errors.append("run_env INSTANT banner must cite outcome_instant")
    if "USED_APPLY_ATTEMPTED" not in run_env or "USED_APPLY_SUCCEEDED" not in run_env:
        errors.append("run_env must print attempted/succeeded apply counters")
    if "env_water" not in run_env or "env_rotor" not in run_env:
        errors.append("run_env must screenshot water and rotor")
    if "env_toxic" not in run_env or "env_instant" not in run_env or "env_fall" not in run_env:
        errors.append("run_env must screenshot toxic/instant/fall")
    if "env_rooftops" not in run_env or "env_hazardous" not in run_env:
        errors.append("run_env must screenshot live maps")
    if "frame_post_draw" not in run_env:
        errors.append("run_env must wait for frame_post_draw before DoD stills")
    if "SHOT_WATER" not in run_env or "SHOT_ROTOR" not in run_env or "SHOT_FALL" not in run_env:
        errors.append("run_env must print drawn-beat postconditions")
    if "cmd.vf4-wp5.env.1" not in run_env:
        errors.append("run_env must use command_id cmd.vf4-wp5.env.1")
    if not PACKER.is_file():
        errors.append("missing tests/pack_env_evidence.py")
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
            errors.append("packer must run stills_pairwise_distinct on beat stills")
        if "cmd.vf4-wp5.env.1" not in packer:
            errors.append("packer must use command_id cmd.vf4-wp5.env.1")
        if "on_floor" not in packer:
            errors.append("packer FALL must require on_floor")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "EnvCases" not in run_all:
        errors.append("run_all.gd must call EnvCases")
    if "outcome_instant" not in run_all or "HH_VF_ENV" not in run_all:
        errors.append("run_all.gd env banner must read outcome_instant")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not CATALOG.is_file():
        errors.append("missing data/world/catalog.json")
    else:
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        if payload.get("env_implemented") is not True:
            errors.append("catalog env_implemented must be true")
        if payload.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if payload.get("title") != "Vault Fighters":
            errors.append("catalog title must be Vault Fighters")
    if not HAZARD.is_file():
        errors.append("missing data/world/hazard.json")
    else:
        haz = json.loads(HAZARD.read_text(encoding="utf-8"))
        if haz.get("water_selected") is True:
            errors.append("hazard.json water_selected must stay false; water lives in env.json")
        if haz.get("extinguish_rule") != "roll":
            errors.append("hazard.json extinguish_rule must stay roll")
    if not ENV.is_file():
        errors.append("missing data/world/env.json")
    else:
        env = json.loads(ENV.read_text(encoding="utf-8"))
        if env.get("env_implemented") is not True:
            errors.append("env_implemented must be true")
        if env.get("water_extinguish") is not True:
            errors.append("env water_extinguish must be true")
        if env.get("nade_prop_class") != "deferred":
            errors.append("env RL-NADE-PROP must stay deferred")
        if env.get("title") != "Vault Fighters":
            errors.append("env title must be Vault Fighters")
        names = env.get("fixture_names") or {}
        if names.get("fx_env_instant") != "Void Cut":
            errors.append("instant fixture display name must be Void Cut")
        if names.get("fx_env_yard") != "Hazard Yard":
            errors.append("yard fixture display name must be Hazard Yard")
        for name in names.values():
            if TRADEMARK.search(str(name)):
                errors.append(f"env fixture name uses Superfighters trademark: {name}")
    if not ARENA.is_file():
        errors.append("missing data/maps/arena_spec.json")
    else:
        arena = json.loads(ARENA.read_text(encoding="utf-8"))
        if arena.get("env_implemented") is not True:
            errors.append("arena spec env_implemented must be true")
        if arena.get("live_c_b_tiles") is not True:
            errors.append("arena spec must keep live c/b tiles")
        maps = arena.get("maps") or {}
        for mid in ("rooftops", "storage", "police", "hazardous"):
            if mid not in maps:
                errors.append(f"arena spec missing live map {mid}")
        if "pit" not in (maps.get("rooftops") or {}).get("hazards", []):
            errors.append("rooftops must declare pit")
        if "instant" not in (maps.get("fx_env_instant") or {}).get("hazards", []):
            errors.append("Void Cut must declare instant")
        for spec in maps.values():
            if TRADEMARK.search(str((spec or {}).get("display_name", ""))):
                errors.append("arena spec display name uses Superfighters trademark")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing env trace {name}")
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
        errors.append("missing docs/env.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-ENV-INSTANT",
            "ledger:RL-ENV-DEFER",
            "ledger:RL-ENV-WATER",
            "ledger:RL-ENV-ROTOR",
            "ledger:RL-ENV-SPAWN",
            "ledger:RL-MOVE-FALL",
            "ledger:RL-NADE-PROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"env docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF4-WP5" not in ledger:
        errors.append("ledger missing VF4-WP5 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    ev_screens = ROOT / "docs" / "evidence" / GATE_RUN_ID / "screens"
    if ev_screens.is_dir():
        named = {
            "water": _pick_still(ev_screens, "water"),
            "rotor": _pick_still(ev_screens, "rotor"),
            "toxic": _pick_still(ev_screens, "toxic"),
            "instant": _pick_still(ev_screens, "instant"),
            "fall": _pick_still(ev_screens, "fall"),
            "setup": _pick_still(ev_screens, "setup"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    for rid in ("RL-ENV-INSTANT", "RL-ENV-DEFER", "RL-ENV-WATER", "RL-ENV-ROTOR", "RL-ENV-SPAWN"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF4-WP5 env files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF4-WP5 env files")
    print(f"  scripts={len(REQUIRED_SCRIPTS)} traces={len(REQUIRED_TRACES)} ledger={len(REQUIRED_LEDGER)}")
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
    beat = [digest for name, digest, _size in rows if "setup" not in name]
    if len(beat) >= 4 and len(set(beat)) < 4:
        errors.append("water/rotor/toxic/instant/fall hashes are not pairwise distinct")
    return errors


def _row(text: str, rid: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {rid} "):
            return line
    return ""


if __name__ == "__main__":
    sys.exit(main())
