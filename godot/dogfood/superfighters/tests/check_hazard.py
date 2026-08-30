#!/usr/bin/env python3
"""VF4-WP3 structure check: barrels, fire, hang, VFX cap.

Does not tick the 29-8 plan. Does not launch Godot (Godot verify is
tests/run_hazard.gd). Does not fetch Y8.
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
DOCS = ROOT / "docs" / "hazard.md"
CATALOG = ROOT / "data" / "world" / "catalog.json"
HAZARD = ROOT / "data" / "world" / "hazard.json"
CASES = ROOT / "tests" / "hazard_cases.gd"
RUN_HAZARD = ROOT / "tests" / "run_hazard.gd"
RUN_ALL = ROOT / "tests" / "run_all.gd"
PACKER = ROOT / "tests" / "pack_hazard_evidence.py"
TRACE_DIR = ROOT / "tests" / "traces" / "hazard"
GATE_RUN_ID = "VF4WP3-20260830-ASIA-SAIGON-02"
FORBIDDEN_RUN_IDS = (
    "VF4WP3-20260830-ASIA-SAIGON-01",
    "VF4WP2-20260829-ASIA-SAIGON-01",
    "VF4WP1-20260829-ASIA-SAIGON-01",
    "VF3WP6-20260829-ASIA-SAIGON-03",
    "VF3WP4-20260829-ASIA-SAIGON-01",
)

REQUIRED_SCRIPTS = (
    "src/world/prop_hazard.gd",
    "src/world/world_owner.gd",
    "src/world/prop_body.gd",
    "src/world/world_catalog.gd",
    "src/game_session.gd",
    "src/fighter.gd",
    "tests/hazard_cases.gd",
    "tests/run_hazard.gd",
    "tests/pack_hazard_evidence.py",
    "data/world/hazard.json",
    "assets/vfx/vfx_explode.png",
    "assets/vfx/vfx_fire.png",
)

REQUIRED_TRACES = (
    "hazard_chain.json",
    "hazard_fire.json",
    "hazard_roll.json",
    "hazard_hang.json",
)

REQUIRED_LEDGER = (
    "RL-PROP-EXPL",
    "RL-PROP-CHAIN",
    "RL-PROP-FIRE",
    "RL-PROP-HANG",
    "RL-PROP-EXTINGUISH",
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
    if "apply_blast" not in session or "explosive" not in session:
        errors.append("game_session must wire blast/explosive props to WorldOwner")
    if "_spawn_crate" in session or "PropCrate" in session:
        errors.append("game_session must not name individual prop nodes")
    fighter = (ROOT / "src" / "fighter.gd").read_text(encoding="utf-8")
    if "ignite_fire" not in fighter or "take_fire_tick" not in fighter:
        errors.append("fighter must implement ignite/tick burn")
    cases = CASES.read_text(encoding="utf-8") if CASES.is_file() else ""
    if re.search(r"step_fixed\s*\(", cases):
        errors.append("hazard_cases must not call step_fixed")
    if re.search(r"action_press\s*\(", cases):
        errors.append("hazard_cases must not call action_press")
    if "apply_frames" not in cases:
        errors.append("hazard_cases must use apply_frames")
    if "step_from_live_input" not in cases:
        errors.append("hazard_cases must prove live InputFrame stepping")
    for needle in (
        "used_apply_frames_attempted",
        "used_apply_frames_succeeded",
        "outcome_chain",
        "outcome_fire",
        "outcome_cleanup",
        "outcome_roll",
        "outcome_dup",
        "outcome_vfx",
        "outcome_hang",
        "outcome_replay",
        "_record_apply",
    ):
        if needle not in cases:
            errors.append(f"hazard_cases missing {needle}")
    if re.search(r"used_apply_frames\s*\+=", cases):
        errors.append("used_apply_frames must not increment blindly")
    run_hazard = RUN_HAZARD.read_text(encoding="utf-8") if RUN_HAZARD.is_file() else ""
    if GATE_RUN_ID not in run_hazard:
        errors.append(f"run_hazard.gd must use unique run_id {GATE_RUN_ID}")
    for banned in FORBIDDEN_RUN_IDS:
        if banned in run_hazard:
            errors.append(f"run_hazard.gd must not reuse {banned}")
    if "CHAIN_SOURCE=outcome_chain" not in run_hazard:
        errors.append("run_hazard CHAIN banner must cite outcome_chain")
    if "USED_APPLY_ATTEMPTED" not in run_hazard or "USED_APPLY_SUCCEEDED" not in run_hazard:
        errors.append("run_hazard must print attempted/succeeded apply counters")
    if "hazard_chain" not in run_hazard or "hazard_fire" not in run_hazard:
        errors.append("run_hazard must screenshot chain and fire")
    if "hazard_hang" not in run_hazard or "hazard_setup" not in run_hazard:
        errors.append("run_hazard must screenshot hang and setup")
    if "frame_post_draw" not in run_hazard:
        errors.append("run_hazard must wait for frame_post_draw before DoD stills")
    if "SHOT_CHAIN" not in run_hazard or "SHOT_FIRE" not in run_hazard or "SHOT_HANG" not in run_hazard:
        errors.append("run_hazard must print drawn-beat postconditions for chain/fire/hang")
    if "cmd.vf4-wp3.hazard.2" not in run_hazard:
        errors.append("run_hazard must use new command_id cmd.vf4-wp3.hazard.2")
    if not PACKER.is_file():
        errors.append("missing tests/pack_hazard_evidence.py")
    else:
        packer = PACKER.read_text(encoding="utf-8")
        if GATE_RUN_ID not in packer:
            errors.append(f"packer must use unique run_id {GATE_RUN_ID}")
        for banned in FORBIDDEN_RUN_IDS:
            if banned in packer:
                errors.append(f"packer must not reuse {banned}")
        if "chain" not in packer or "cleanup" not in packer:
            errors.append("packer verdict must require chain/cleanup, not events alone")
        if "identical sha256" not in packer or "size+hash" not in packer:
            errors.append("packer must fail identical chain/fire/hang hashes or size+hash")
        if "stills_pairwise_distinct" not in packer:
            errors.append("packer must run stills_pairwise_distinct on setup/chain/fire/hang")
    run_all = RUN_ALL.read_text(encoding="utf-8") if RUN_ALL.is_file() else ""
    if "HazardCases" not in run_all:
        errors.append("run_all.gd must call HazardCases")
    if "outcome_chain" not in run_all or "HH_VF_HAZARD" not in run_all:
        errors.append("run_all.gd hazard banner must read outcome_chain")
    title = TITLE.read_text(encoding="utf-8")
    if 'text = "Vault Fighters"' not in title:
        errors.append("title card is not Vault Fighters")
    if "Superfighters" in title or "Super Fighter" in title:
        errors.append("title_screen.gd contains Superfighters string")
    if not CATALOG.is_file():
        errors.append("missing data/world/catalog.json")
    else:
        payload = json.loads(CATALOG.read_text(encoding="utf-8"))
        if payload.get("chain_implemented") is not True:
            errors.append("catalog chain_implemented must be true")
        if payload.get("nade_prop_class") != "deferred":
            errors.append("RL-NADE-PROP must stay deferred")
        if payload.get("y8_parity_claimed") is True:
            errors.append("catalog claimed Y8 parity")
        if payload.get("title") != "Vault Fighters":
            errors.append("catalog title must be Vault Fighters")
        specs = payload.get("specs") or {}
        if not bool((specs.get("crate_hanging") or {}).get("hanging")):
            errors.append("crate_hanging must start hanging")
        if str((specs.get("barrel_explosive") or {}).get("name")) != "Blast Drum":
            errors.append("barrel display name must stay Blast Drum")
        for name in (payload.get("fixture_names") or {}).values():
            if TRADEMARK.search(str(name)):
                errors.append(f"fixture name uses Superfighters trademark: {name}")
    if not HAZARD.is_file():
        errors.append("missing data/world/hazard.json")
    else:
        haz = json.loads(HAZARD.read_text(encoding="utf-8"))
        if haz.get("extinguish_rule") != "roll":
            errors.append("extinguish rule must be roll")
        if haz.get("water_selected") is True:
            errors.append("water must stay unselected")
        if int(haz.get("chain_max_depth", 0)) != 2:
            errors.append("chain_max_depth must be 2")
        if int(haz.get("vfx_cap", 0)) != 4:
            errors.append("vfx_cap must be 4")
        if haz.get("nade_prop_class") != "deferred":
            errors.append("hazard RL-NADE-PROP must stay deferred")
        if haz.get("y8_parity_claimed") is True:
            errors.append("hazard claimed Y8 parity")
    for name in REQUIRED_TRACES:
        path = TRACE_DIR / name
        if not path.is_file():
            errors.append(f"missing hazard trace {name}")
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
        errors.append("missing docs/hazard.md")
    else:
        docs = DOCS.read_text(encoding="utf-8")
        for needle in (
            "ledger:RL-SIM-FIXED-60",
            "ledger:RL-PROP-EXPL",
            "ledger:RL-PROP-CHAIN",
            "ledger:RL-PROP-FIRE",
            "ledger:RL-PROP-HANG",
            "ledger:RL-PROP-EXTINGUISH",
            "ledger:RL-NADE-PROP",
            "does **not** claim Y8 parity",
            "apply_frames",
            GATE_RUN_ID,
            "roll",
        ):
            if needle not in docs:
                errors.append(f"hazard docs missing {needle}")
    ledger = LEDGER.read_text(encoding="utf-8")
    for rid in REQUIRED_LEDGER:
        if rid not in ledger:
            errors.append(f"ledger missing {rid}")
    if "VF4-WP3" not in ledger:
        errors.append("ledger missing VF4-WP3 section")
    if GATE_RUN_ID not in ledger:
        errors.append(f"ledger must cite unique run {GATE_RUN_ID}")
    ev_screens = ROOT / "docs" / "evidence" / GATE_RUN_ID / "screens"
    if ev_screens.is_dir():
        named = {
            "chain": _pick_still(ev_screens, "chain"),
            "fire": _pick_still(ev_screens, "fire"),
            "hang": _pick_still(ev_screens, "hang"),
            "setup": _pick_still(ev_screens, "setup"),
        }
        for key, path in named.items():
            if path is None:
                errors.append(f"evidence still missing {key}")
        present = [p for p in named.values() if p is not None]
        errors.extend(stills_pairwise_distinct(present))
    for rid in ("RL-PROP-EXPL", "RL-PROP-CHAIN", "RL-PROP-FIRE", "RL-PROP-HANG"):
        row = _row(ledger, rid)
        if "`observed`" in row and "not observed" not in row and "Do **not** cite as observed" not in row:
            errors.append(f"{rid} must not be marked observed")
    nade = _row(ledger, "RL-NADE-PROP")
    if "`deferred`" not in nade:
        errors.append("RL-NADE-PROP must stay deferred")
    if errors:
        print("FAIL: Vault Fighters VF4-WP3 hazard files")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PASS: Vault Fighters VF4-WP3 hazard files")
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
        errors.append("chain/fire/hang hashes are not pairwise distinct")
    return errors


def _row(text: str, rid: str) -> str:
    for line in text.splitlines():
        if line.startswith(f"| {rid} "):
            return line
    return ""


if __name__ == "__main__":
    sys.exit(main())
