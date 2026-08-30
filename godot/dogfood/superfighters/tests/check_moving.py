#!/usr/bin/env python3
"""VF4-WP4 structure check: doors, lifts, boarding, triggers.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_moving.gd). Does not fetch Y8.
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
DOCS = ROOT / "docs" / "moving.md"
CATALOG = ROOT / "data" / "world" / "catalog.json"
MOVING = ROOT / "data" / "world" / "moving.json"
CASES = ROOT / "tests" / "moving_cases.gd"
RUN_MOVING = ROOT / "tests" / "run_moving.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_moving_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "moving"
GATE_RUN_ID = "VF4WP4-20260830-ASIA-SAIGON-02"
SPENT_RUN_ID = "VF4WP4-20260830-ASIA-SAIGON-01"
FORBIDDEN_RUN_IDS = (
    SPENT_RUN_ID,
    "VF4WP3-20260830-ASIA-SAIGON-02",
    "VF4WP3-20260830-ASIA-SAIGON-01",
    "VF4WP2-20260829-ASIA-SAIGON-01",
    "VF4WP1-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/world/moving_spec.gd",
    "src/world/moving_body.gd",
    "src/world/world_owner.gd",
    "src/maps.gd",
    "src/game_session.gd",
    "tests/moving_cases.gd",
    "tests/run_moving.gd",
    "tests/pack_moving_evidence.py",
    "data/world/moving.json",
    "assets/art/prop_door.png",
    "assets/art/prop_lift.png",
    "assets/art/prop_trigger.png",
)

REQUIRED_TRACES = (
    "move_door.json",
    "move_ride.json",
    "move_drop.json",
    "move_yard.json",
)

REQUIRED_LEDGER = (
    "RL-WORLD-DOOR",
    "RL-WORLD-LIFT",
    "RL-WORLD-BOARD",
    "RL-WORLD-TRIGGER",
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
    if "_step_movers" not in owner or "board_events" not in owner:
        errors.append("world_owner must step movers and count board events")
    if "_spawn_mover" not in owner:
        errors.append("world_owner must spawn movers from moving.json")
    session = (ROOT / "src" / "game_session.gd").read_text(encoding="utf-8")
    if "_spawn_crate" in session or "PropCrate" in session:
        errors.append("game_session must not name individual prop nodes")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("moving_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("moving_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("moving_cases must use apply_frames")
    if "y_end > 110.0" in cases or "y_end <= 110.0" in cases:
        errors.append("moving_cases DROP must not treat hang y<=110 as pass")
    if "on_floor_end" not in cases or "hanging_end" not in cases:
        errors.append("moving_cases DROP must require on_floor and reject hang")
    if "max_board_dy" not in cases or "ride_warp" not in owner:
        errors.append("moving cases/owner must hunt Y warp, not only Maps.solid_at")
    if "platform_riding" not in owner:
        errors.append("world_owner must mark platform_riding so LEDGE cannot grab mid-ride")
    if "step_from_live_input" not in cases:
        errors.append("moving_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_ride",
        "outcome_carry",
        "outcome_drop",
        "outcome_door",
        "outcome_trigger",
        "outcome_pause",
        "outcome_reset",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"moving_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_moving = RUN_MOVING.read_text(encoding="utf-8") if RUN_MOVING.is_file() else ""
    if GATE_RUN_ID not in run_moving:
        errors.append(f"run_moving.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_moving:
            errors.append(f"run_moving.gd must not reuse {banned}")
    if "RIDE_SOURCE=outcome_ride" not in run_moving:
        errors.append("run_moving RIDE banner must cite outcome_ride")
    if "USED_APPLY_ATTEMPTED" not in run_moving or "USED_APPLY_SUCCEEDED" not in run_moving:
        errors.append("run_moving must print attempted/succeeded apply counters")
    if "move_door" not in run_moving or "move_ride" not in run_moving:
        errors.append("run_moving must screenshot door and ride")
    if "move_drop" not in run_moving or "move_setup" not in run_moving:
        errors.append("run_moving must screenshot drop and setup")
    if "frame_post_draw" not in run_moving:
        errors.append("run_moving must wait for frame_post_draw before DoD stills")
    if "SHOT_DOOR" not in run_moving or "SHOT_RIDE" not in run_moving or "SHOT_DROP" not in run_moving:
        errors.append("run_moving must print drawn-beat postconditions for door/ride/drop")
    if "cmd.vf4-wp4.moving.2" not in run_moving:
        errors.append("run_moving must use command_id cmd.vf4-wp4.moving.2")
    if "cmd.vf4-wp4.moving.1" in run_moving:
        errors.append("run_moving must not remint command_id cmd.vf4-wp4.moving.1")
    if not PACKER.is_file():
        errors.append("missing tests/pack_moving_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "identical sha256" not in packer or "size+hash" not in packer:
            errors.append("packer must fail identical door/ride/drop hashes or size+hash")
        if "stills_pairwise_distinct" not in packer:
            errors.append("packer must run stills_pairwise_distinct on setup/door/ride/drop")
        if "cmd.vf4-wp4.moving.2" not in packer:
            errors.append("packer must use command_id cmd.vf4-wp4.moving.2")
        if "y_end" in packer and "<= 110" in packer:
            errors.append("packer must not treat hang y<=110 as DROP pass")
        if '60.0 <= drop_y <= 76.0' not in packer:
            errors.append("packer DROP must require deck y band and on_floor")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "MovingCases" not in run_all:
        errors.append("run_all.gd must call MovingCases")
    if "outcome_ride" not in run_all or "HH_VF_MOVING" not in run_all:
        errors.append("run_all.gd moving banner must read outcome_ride")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not CATALOG.is_file():
        errors.append("missing data/world/catalog.json")
    else:
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        if payload.get("moving_implemented") is not True:
            errors.append("catalog moving_implemented must be true")
        if payload.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if payload.get("y8_parity_claimed") is True:
            errors.append("catalog claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("catalog title must be Vault Fighters")
        for name in (payload.get("fixture_names") or {}).values():
            if TRADEMARK.search(str(name)):
                errors.append(f"fixture name uses Superfighters trademark: {name}")
    if not MOVING.is_file():
        errors.append("missing data/world/moving.json")
    else:
        mov = json.loads(MOVING.read_text(encoding="utf-8"))
        if mov.get("moving_implemented") is not True:
            errors.append("moving_implemented must be true")
        if mov.get("nade_prop_class") != "deferred":
            errors.append("moving RL-NADE-PROP must stay deferred")
        if mov.get("y8_parity_claimed") is True:
            errors.append("moving claimed Y8 parity")
        if mov.get("title") != "Vault Fighters":
            errors.append("moving title must be Vault Fighters")
        if int(mov.get("travel_ticks", 0)) != 44:
            errors.append("travel_ticks must be 44")
        if float(mov.get("snap_eps", 99.0)) > 8.0:
            errors.append("snap_eps must stay <= 8")
        if float(mov.get("warp_px", 0.0)) < 16.0:
            errors.append("warp_px must stay >= 16")
        lift_place = ((mov.get("placements") or {}).get("fx_move_lift") or [{}])[0]
        if float(lift_place.get("to_x", 0.0)) < 184.0:
            errors.append("lift dest must dock over the right upper deck")
        names = mov.get("fixture_names") or {}
        if names.get("fx_move_door") != "Gate Hall":
            errors.append("door fixture display name must be Gate Hall")
        if names.get("fx_move_lift") != "Lift Shaft":
            errors.append("lift fixture display name must be Lift Shaft")
        if names.get("fx_move_yard") != "Relay Shaft":
            errors.append("yard fixture display name must be Relay Shaft")
        for name in names.values():
            if TRADEMARK.search(str(name)):
                errors.append(f"moving fixture name uses Superfighters trademark: {name}")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing moving trace {name}")
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
        errors.append("missing docs/moving.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-WORLD-DOOR",
            "ledger:RL-WORLD-LIFT",
            "ledger:RL-WORLD-BOARD",
            "ledger:RL-WORLD-TRIGGER",
            "ledger:RL-NADE-PROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
        ):
            if needle not in docs:
                errors.append(f"moving docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF4-WP4" not in ledger:
        errors.append("ledger missing VF4-WP4 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    ev_screens = ROOT / "docs" / "evidence" / GATE_RUN_ID / "screens"
    if ev_screens.is_dir():
        named = {
            "door": _pick_still(ev_screens, "door"),
            "ride": _pick_still(ev_screens, "ride"),
            "drop": _pick_still(ev_screens, "drop"),
            "setup": _pick_still(ev_screens, "setup"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    for rid in ("RL-WORLD-DOOR", "RL-WORLD-LIFT", "RL-WORLD-BOARD", "RL-WORLD-TRIGGER"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF4-WP4 moving files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF4-WP4 moving files")
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
    if len(beat) >= 3 and len(set(beat)) < 3:
        errors.append("door/ride/drop hashes are not pairwise distinct")
    return errors


def _row(text: str, rid: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {rid} "):
            return line
    return ""


if __name__ == "__main__":
    sys.exit(main())
