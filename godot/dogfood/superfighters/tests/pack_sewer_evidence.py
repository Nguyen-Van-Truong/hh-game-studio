#!/usr/bin/env python3
"""Assemble VF5-WP5 §18.3 evidence after official Vitriol Sump runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF5WP5-20260831-ASIA-SAIGON-07"
COMMAND_ID = "cmd.vf5-wp5.vitriol-sump.8"
WP = "VF5-WP5"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/maps/arena_spec.gd",
    "src/maps/map_catalog.gd",
    "src/maps/map_graph.gd",
    "src/maps/map_codec.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/app.gd",
    "src/ui/title_screen.gd",
    "src/sim/sim_constants.gd",
    "src/world/env_body.gd",
    "src/world/world_owner.gd",
    "src/game_session.gd",
    "data/maps/schema.json",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/hazardous.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/rooftops.json",
    "data/world/catalog.json",
    "data/world/moving.json",
    "data/world/env.json",
    "tests/sewer_cases.gd",
    "tests/run_sewer.gd",
    "tests/check_sewer.py",
    "tests/pack_sewer_evidence.py",
    "tests/map_cases.gd",
    "tests/world_cases.gd",
    "tests/run_all.gd",
    "tests/_gen_map_layers.py",
    "docs/sewer.md",
    "docs/provenance.md",
    "docs/provenance-manifest.json",
    "docs/maps.md",
    "docs/world.md",
    "docs/env.md",
    "docs/station.md",
    "docs/warehouse.md",
    "docs/rooftop.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "project.godot",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stat_field(log_text: str, key: str) -> str:
    prefix = "HH_VF_STAT "
    needle = key + "="
    for line in log_text.splitlines():
        if not line.startswith(prefix):
            continue
        for part in line.split():
            if part.startswith(needle):
                return part.split("=", 1)[1]
    return ""


def _evidence_dir_value(log_text: str) -> str:
    prefix = "HH_VF_STAT EVIDENCE_DIR="
    for line in log_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def now_saigon() -> str:
    return datetime.now(SAIGON).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def outcome_verdict(outcomes: dict, key: str) -> str:
    row = outcomes.get(key, {})
    if isinstance(row, dict):
        return str(row.get("verdict", "unproven"))
    return "unproven"


def pick_still(screens: list[Path], needle: str) -> Path | None:
    matches = [png for png in screens if needle in png.name]
    return matches[0] if matches else None


def stills_pairwise_distinct(paths: list[Path]) -> tuple[bool, dict, list[str]]:
    errors: list[str] = []
    hashes: dict[str, dict] = {}
    rows: list[tuple[str, str, int]] = []
    for path in paths:
        if path is None or not path.is_file():
            errors.append(f"missing still {path}")
            continue
        digest = sha256_file(path)
        size = path.stat().st_size
        hashes[path.name] = {"sha256": digest, "bytes": size}
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
    return (not errors, hashes, errors)


def _still_ok(row: dict, zones: set[str] | None = None, allow_lose: bool = False) -> bool:
    lose_ok = (not bool(row.get("lose_visible", True))) or allow_lose
    if allow_lose:
        ok = lose_ok
    else:
        ok = (
            bool(row.get("alive", False))
            and bool(row.get("on_floor", False))
            and lose_ok
        )
    if zones is not None:
        ok = ok and str(row.get("zone", "")) in zones
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--headless-evidence", required=True)
    parser.add_argument("--window-evidence", required=True)
    parser.add_argument("--base-head", required=True)
    parser.add_argument("--godot-exe", required=True)
    parser.add_argument("--headless-log", required=True)
    parser.add_argument("--window-log", required=True)
    parser.add_argument("--run-all-log", required=True)
    parser.add_argument("--check-log", required=True)
    parser.add_argument("--headless-exit", type=int, required=True)
    parser.add_argument("--window-exit", type=int, required=True)
    parser.add_argument("--run-all-exit", type=int, required=True)
    parser.add_argument("--check-exit", type=int, required=True)
    parser.add_argument("--leftover", type=int, required=True)
    args = parser.parse_args()

    product = Path(args.product)
    evidence = Path(args.evidence)
    review = Path(args.review)
    headless_ev = Path(args.headless_evidence)
    window_ev = Path(args.window_evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "screens").mkdir(parents=True, exist_ok=True)

    outcomes = load_json(window_ev / "outcomes.json") or load_json(headless_ev / "outcomes.json")
    partial_h = load_json(headless_ev / "run_partial.json")
    partial_w = load_json(window_ev / "run_partial.json")
    source_sha = {}
    for rel in SOURCE_FILES:
        path = product / rel
        if path.is_file():
            source_sha[rel] = sha256_file(path)
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    godot_exe = Path(args.godot_exe)
    godot_hash = sha256_file(godot_exe) if godot_exe.is_file() else ""

    apply_info = outcomes.get("apply", {})
    name_v = outcome_verdict(outcomes, "name")
    graph = outcome_verdict(outcomes, "graph")
    toxic = outcome_verdict(outcomes, "toxic")
    dive = outcome_verdict(outcomes, "dive")
    roll = outcome_verdict(outcomes, "roll")
    cargo = outcome_verdict(outcomes, "cargo")
    spawn = outcome_verdict(outcomes, "spawn")
    camera = outcome_verdict(outcomes, "camera")
    tactic = outcome_verdict(outcomes, "tactic")
    p1 = outcome_verdict(outcomes, "p1")
    p2 = outcome_verdict(outcomes, "p2")
    bot = outcome_verdict(outcomes, "bot")
    zone = outcome_verdict(outcomes, "zone")
    live = outcome_verdict(outcomes, "live")
    replay = outcome_verdict(outcomes, "replay")
    variants = outcome_verdict(outcomes, "variants")
    succeeded = int(apply_info.get("succeeded", 0))
    attempted = int(apply_info.get("attempted", 0))
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    headless_pass = "PASS: Vault Fighters Vitriol Sump sewer arena" in headless_log_text
    window_pass = "PASS: Vault Fighters Vitriol Sump sewer arena" in window_log_text
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    sewer_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_SEWER ")), "")
    run_all_ok = (
        "PASS: Vault Fighters first playable" in run_all_log_text
        and "MAPS=pass" in dive_banner
        and "APPLY=1253/1253" in dive_banner
        and "status=proven" in dive_banner
        and "TACTIC=pass" in sewer_banner
        and "DIVE=pass" in sewer_banner
        and "status=proven" in sewer_banner
    )
    id_match = (
        RUN_ID in headless_log_text
        and RUN_ID in window_log_text
        and COMMAND_ID in headless_log_text
        and COMMAND_ID in window_log_text
        and str(partial_h.get("run_id", "")) == RUN_ID
        and str(partial_w.get("run_id", "")) == RUN_ID
        and int(partial_h.get("fail_count", 1)) == 0
        and int(partial_w.get("fail_count", 1)) == 0
    )
    headless_ev_dir = _evidence_dir_value(headless_log_text)
    window_ev_dir = _evidence_dir_value(window_log_text)
    banner_apply_h = int(_stat_field(headless_log_text, "USED_APPLY_FRAMES") or "-1")
    banner_apply_w = int(_stat_field(window_log_text, "USED_APPLY_FRAMES") or "-1")
    banner_step_h = int(_stat_field(headless_log_text, "USED_STEP_FIXED") or "1")
    banner_step_w = int(_stat_field(window_log_text, "USED_STEP_FIXED") or "1")
    live_logs_ok = (
        "Godot Engine v4.7.1" in headless_log_text
        and "Godot Engine v4.7.1" in window_log_text
        and "DISPLAY=headless" in headless_log_text
        and "DISPLAY=Windows" in window_log_text
        and RUN_ID in headless_ev_dir
        and RUN_ID in window_ev_dir
        and "PROBE" not in headless_ev_dir
        and "PROBE" not in window_ev_dir
        and banner_step_h == 0
        and banner_step_w == 0
        and banner_apply_h > 0
        and banner_apply_w > 0
        and banner_apply_h != int(apply_info.get("succeeded", 0) or 0)
        and banner_apply_w != int(apply_info.get("succeeded", 0) or 0)
    )
    godot_exe_ok = godot_exe.is_file() and godot_exe.stat().st_size >= 1_000_000
    step_fixed_ok = int(apply_info.get("used_step_fixed", 1)) == 0
    exits_ok = (
        args.check_exit == 0
        and args.headless_exit == 0
        and args.window_exit == 0
        and args.run_all_exit == 0
        and args.leftover == 0
        and headless_pass
        and window_pass
        and run_all_ok
        and id_match
        and live_logs_ok
        and godot_exe_ok
        and step_fixed_ok
    )
    outcomes_ok = (
        name_v == "pass"
        and graph == "pass"
        and toxic == "pass"
        and dive == "pass"
        and roll == "pass"
        and cargo == "pass"
        and spawn == "pass"
        and camera == "pass"
        and tactic == "pass"
        and p1 == "pass"
        and p2 == "pass"
        and bot == "pass"
        and zone == "pass"
        and live == "pass"
        and replay == "match"
        and variants == "pass"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    live_row = outcomes.get("live", {}) if isinstance(outcomes.get("live"), dict) else {}
    p1_row = outcomes.get("p1", {}) if isinstance(outcomes.get("p1"), dict) else {}
    p2_row = outcomes.get("p2", {}) if isinstance(outcomes.get("p2"), dict) else {}
    bot_row = outcomes.get("bot", {}) if isinstance(outcomes.get("bot"), dict) else {}
    zone_row = outcomes.get("zone", {}) if isinstance(outcomes.get("zone"), dict) else {}
    toxic_row = outcomes.get("toxic", {}) if isinstance(outcomes.get("toxic"), dict) else {}
    dive_row = outcomes.get("dive", {}) if isinstance(outcomes.get("dive"), dict) else {}
    roll_row = outcomes.get("roll", {}) if isinstance(outcomes.get("roll"), dict) else {}
    cargo_row = outcomes.get("cargo", {}) if isinstance(outcomes.get("cargo"), dict) else {}
    tactic_row = outcomes.get("tactic", {}) if isinstance(outcomes.get("tactic"), dict) else {}
    variants_row = outcomes.get("variants", {}) if isinstance(outcomes.get("variants"), dict) else {}
    replay_row = outcomes.get("replay", {}) if isinstance(outcomes.get("replay"), dict) else {}
    pipes_still = outcomes.get("pipes_still", {}) if isinstance(outcomes.get("pipes_still"), dict) else {}
    crossing_still = outcomes.get("crossing_still", {}) if isinstance(outcomes.get("crossing_still"), dict) else {}
    cargo_still = outcomes.get("cargo_still", {}) if isinstance(outcomes.get("cargo_still"), dict) else {}
    lip_still = outcomes.get("lip_still", {}) if isinstance(outcomes.get("lip_still"), dict) else {}
    toxic_still = outcomes.get("toxic_still", {}) if isinstance(outcomes.get("toxic_still"), dict) else {}
    live_real = str(live_row.get("hud", "")) == "Vitriol Sump"
    toxic_real = bool(toxic_row.get("dead", False)) and str(toxic_row.get("cause", "")) in ("damage", "pit")
    tactic_real = (
        bool(tactic_row.get("floor_dead", False))
        and bool(tactic_row.get("pipe_alive", False))
        and bool(tactic_row.get("pipe_fired", False))
        and bool(tactic_row.get("item_pickup", False))
        and not bool(tactic_row.get("used_give_weapon", True))
        and int(tactic_row.get("pickup_id", 0) or 0) > 0
        and str(tactic_row.get("weapon_id", "")) != ""
        and int(tactic_row.get("pickup_tick", 0) or 0) > 0
    )
    dive_traj = dive_row.get("trajectory") if isinstance(dive_row.get("trajectory"), dict) else {}
    dive_real = (
        bool(dive_row.get("dived", False))
        and bool(dive_row.get("acid", False))
        and bool(dive_row.get("acid_at_kill", False))
        and bool(dive_row.get("dead", False))
        and str(dive_row.get("cause", "")) == "damage"
        and float(dive_row.get("y_at_kill", dive_traj.get("y1", 999.0)) or 999.0) <= 250.0
    )
    p2_smoke = str(p2_row.get("coverage", "")) == "smoke"
    bot_smoke = str(bot_row.get("coverage", "")) == "smoke"
    replay_live = int(replay_row.get("frames", 0) or 0) >= 8 and str(replay_row.get("live_hash", "")) != ""
    variants_real = variants == "pass" and isinstance(variants_row.get("morphs"), list) and len(variants_row.get("morphs") or []) >= 3
    toxic_traj = outcomes.get("toxic", {}) if isinstance(outcomes.get("toxic"), dict) else {}
    traj_ok = int((toxic_traj.get("trajectory") or {}).get("samples", 0) if isinstance(toxic_traj.get("trajectory"), dict) else 0) >= 8
    cargo_real = not bool(cargo_row.get("hung_after", True)) and int(cargo_row.get("drops", 0)) >= 1
    p1_hits = p1_row.get("hits") if isinstance(p1_row.get("hits"), dict) else {}
    required_zones = (
        "west_bank",
        "west_span",
        "west_high",
        "west_mid",
        "mid_west",
        "mid_east",
        "mid_low",
        "east_high",
        "east_bank",
        "sump_lip",
    )
    p1_all = all(bool(p1_hits.get(zid)) for zid in required_zones)
    climb_ok = int(zone_row.get("climb_up_on_ladder", 0) or p1_row.get("climb_up_on_ladder", 0)) >= 8
    stills_live = (
        _still_ok(pipes_still, {"west_high", "mid_west", "west_mid"})
        and _still_ok(crossing_still, {"mid_east", "mid_west", "mid_low"})
        and _still_ok(cargo_still, {"mid_west", "west_high"})
        and _still_ok(lip_still, {"sump_lip"})
        and _still_ok(toxic_still, allow_lose=True)
    )
    live_reach_ok = p1_all and climb_ok and stills_live
    events_path = window_ev / "events.jsonl"
    if not events_path.is_file():
        events_path = headless_ev / "events.jsonl"
    event_kinds: set[str] = set()
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                event_kinds.add(str(row.get("kind", "")))
    events_ok = bool({"stat_name", "stat_zone", "stat_p1", "stat_toxic", "stat_tactic"} <= event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    title_png = pick_still(screens, "title")
    pipes_png = pick_still(screens, "pipes")
    crossing_png = pick_still(screens, "crossing")
    cargo_png = pick_still(screens, "cargo")
    lip_png = pick_still(screens, "lip")
    toxic_png = pick_still(screens, "toxic")
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, title_png, pipes_png, crossing_png, cargo_png, lip_png, toxic_png) if p is not None]
    )
    if None in (setup_png, title_png, pipes_png, crossing_png, cargo_png, lip_png, toxic_png):
        stills_ok = False
        still_errors.append("need setup/title/pipes/crossing/cargo/lip/toxic window stills")
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and live_real
        and toxic_real
        and tactic_real
        and dive_real
        and cargo_real
        and events_ok
        and stills_ok
        and live_reach_ok
        and p2_smoke
        and bot_smoke
        and replay_live
        and variants_real
        and traj_ok
        else "FAIL"
    )

    for name in (
        "outcomes.json",
        "snapshot_start.json",
        "snapshot_end.json",
        "state_hashes.json",
        "events.jsonl",
        "run_partial.json",
    ):
        src = window_ev / name
        if not src.is_file():
            src = headless_ev / name
        if src.is_file():
            (evidence / name).write_bytes(src.read_bytes())
    if (headless_ev / "run_partial.json").is_file():
        (evidence / "run_partial_headless.json").write_bytes(
            (headless_ev / "run_partial.json").read_bytes()
        )
    if (window_ev / "run_partial.json").is_file():
        (evidence / "run_partial_window.json").write_bytes(
            (window_ev / "run_partial.json").read_bytes()
        )
    screens_src = window_ev / "screens"
    if screens_src.is_dir():
        for png in screens_src.glob("*.png"):
            (evidence / "screens" / png.name).write_bytes(png.read_bytes())
    for label, src in (
        ("run_sewer.headless.log", Path(args.headless_log)),
        ("run_sewer.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_sewer.log", Path(args.check_log)),
    ):
        if src.is_file():
            (evidence / label).write_bytes(src.read_bytes())

    metrics = {
        "frame_budget_hz": 60,
        "entities_end": len((load_json(evidence / "snapshot_end.json").get("fighters") or [])),
        "apply_attempted": attempted,
        "apply_succeeded": succeeded,
        "os": platform.platform(),
        "python": platform.python_version(),
        "process_rss_hint": "see host leftover-0 check; Godot process ended",
        "budgets": {
            "epsilon": 0.001,
            "leftover_godot": args.leftover,
            "jump_dx": 10,
            "jump_dy": 4,
        },
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf5-wp5.run.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "timezone": "Asia/Saigon",
        "recorded_at": now_saigon(),
        "started_at": started_at,
        "ended_at": ended_at,
        "base_head": args.base_head,
        "godot": "4.7.1.stable.official.a13da4feb",
        "godot_exe_sha256": godot_hash,
        "os": platform.platform(),
        "seed": 15,
        "map_id": "hazardous",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "outcomes": {
            "NAME": name_v,
            "GRAPH": graph,
            "TOXIC": toxic,
            "DIVE": dive,
            "ROLL": roll,
            "CARGO": cargo,
            "SPAWN": spawn,
            "CAMERA": camera,
            "TACTIC": tactic,
            "P1": p1,
            "P2": p2,
            "BOT": bot,
            "ZONE": zone,
            "LIVE": live,
            "REPLAY": replay,
            "VARIANTS": variants,
            "P2_COVERAGE": "smoke",
            "BOT_COVERAGE": "smoke",
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "map_sump_observed": False,
            "in_game_y8_play": False,
            "game_package_fetched": False,
            "plan_checkbox_ticked": False,
            "implementer_commit": False,
            "r9_wp4": False,
            "g6": False,
            "gx": False,
            "progress_60_of_60": False,
        },
        "ledger": [
            "RL-MAP-SUMP",
            "RL-DELTA-MAP-NAMES",
            "RL-MAP-GRAPH",
            "RL-ENV-DEFER",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_sewer.py",
                "python godot/dogfood/superfighters/tests/check_station.py",
                "python godot/dogfood/superfighters/tests/check_warehouse.py",
                "python godot/dogfood/superfighters/tests/check_rooftop.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_sewer.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_sewer.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "stat_headless_exit": args.headless_exit,
            "stat_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "sump": "assumption",
            "graph": "assumption",
            "nade_prop": "deferred",
            "hold_to_aim": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF5-WP5 verdict

{verdict} Vitriol Sump sewer arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP5)

Verify: toxic contact/death, dive/roll edge cases, route connectivity,
suspended object collision, camera bounds.

DoD: hazard changes movement and weapon strategy.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `15`, mode `vs2`, map `hazardous` display **Vitriol Sump**
- NAME={name_v} GRAPH={graph} TOXIC={toxic} DIVE={dive} ROLL={roll} CARGO={cargo} SPAWN={spawn} CAMERA={camera} TACTIC={tactic} P1={p1} P2={p2} BOT={bot} ZONE={zone} LIVE={live} REPLAY={replay} VARIANTS={variants}
- LIVE hud={live_row.get("hud")} real={live_real}
- P1 hits={p1_row.get("hits")} P2 hits={p2_row.get("hits")} BOT hits={bot_row.get("hits")}
- live_reach p1_all={p1_all} climb_up_on_ladder={climb_ok}
- pipes_still={pipes_still} crossing={crossing_still} cargo_still={cargo_still} lip={lip_still} toxic_still={toxic_still}
- TOXIC dead={toxic_row.get("dead")} cause={toxic_row.get("cause")} real={toxic_real}
- DIVE dived={dive_row.get("dived")} acid={dive_row.get("acid")} acid_at_kill={dive_row.get("acid_at_kill")} cause={dive_row.get("cause")} y={dive_row.get("y_at_kill")} real={dive_real}
- ROLL rolled={roll_row.get("rolled")} acid={roll_row.get("acid")}
- CARGO hung_after={cargo_row.get("hung_after")} drops={cargo_row.get("drops")} real={cargo_real}
- TACTIC floor_dead={tactic_row.get("floor_dead")} pipe_alive={tactic_row.get("pipe_alive")} pickup_id={tactic_row.get("pickup_id")} weapon={tactic_row.get("weapon_id")} tick={tactic_row.get("pickup_tick")} give_weapon={tactic_row.get("used_give_weapon")} real={tactic_real}
- events kinds include name/zone/p1/toxic/tactic={events_ok} kinds={sorted(event_kinds)}
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- live stdout banners APPLY headless={banner_apply_h} window={banner_apply_w} (printed before still staging; packer copies logs verbatim and does not rewrite these lines)
- EVIDENCE_DIR headless=`{headless_ev_dir}` window=`{window_ev_dir}`
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `SewerCases.outcome_*`. They are not inferred from fail-substrings.
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_sewer.py
python godot/dogfood/superfighters/tests/check_station.py
python godot/dogfood/superfighters/tests/check_warehouse.py
python godot/dogfood/superfighters/tests/check_rooftop.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_sewer.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_sewer.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Vitriol Sump topology stays assumption (`ledger:RL-MAP-SUMP`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
- ZONE / P1 / P2 / BOT / SPAWN / TOXIC / DIVE / ROLL / CARGO / TACTIC
  are live body positions during apply_frames. MapGraph is a helper only.
  Official routes hold `up` on ladder cells. Dive/roll invuln does not
  cancel toxic (`take_env_tick` ignores invuln).
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke: preset ladder / short chase,
  not AI and not Y8 parity. P1 tours every safe combat zone.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Hazardous display is retired to **Vitriol Sump**
  (`ledger:RL-DELTA-MAP-NAMES`). Internal id stays `hazardous`.
- Water stays fixture-only. Signal Court rotor is VF5-WP4 and is not
  reminted. Unused `annex_lift` / `signal_lift` stay honesty nits.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0. No legal self-conclusion that the layout is
  close enough to Y8 to ship.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.
"""
    (evidence / "verdict.md").write_text(verdict_md, encoding="utf-8")

    hash_rows: list[str] = [f"# {RUN_ID}", "# SHA-256; hashes.txt not self-hashed"]
    for rel, digest in sorted(source_sha.items()):
        hash_rows.append(f"{digest}  {rel}")
    extra = [
        evidence / "run.json",
        evidence / "outcomes.json",
        evidence / "snapshot_start.json",
        evidence / "snapshot_end.json",
        evidence / "state_hashes.json",
        evidence / "events.jsonl",
        evidence / "metrics.json",
        evidence / "verdict.md",
        Path(args.headless_log),
        Path(args.window_log),
        Path(args.run_all_log),
        Path(args.check_log),
    ]
    extra.extend(sorted((evidence / "screens").glob("*.png")))
    for path in extra:
        if path.is_file():
            hash_rows.append(f"{sha256_file(path)}  {path.as_posix()}")
    (evidence / "hashes.txt").write_text("\n".join(hash_rows) + "\n", encoding="utf-8")

    review.mkdir(parents=True, exist_ok=True)
    for name in (
        "run.json",
        "outcomes.json",
        "snapshot_start.json",
        "snapshot_end.json",
        "state_hashes.json",
        "events.jsonl",
        "metrics.json",
        "verdict.md",
        "hashes.txt",
        "run_partial.json",
        "run_partial_headless.json",
        "run_partial_window.json",
    ):
        src = evidence / name
        if src.is_file():
            (review / name).write_bytes(src.read_bytes())
    screens_dst = review / "screens"
    screens_dst.mkdir(parents=True, exist_ok=True)
    for png in (evidence / "screens").glob("*.png"):
        (screens_dst / png.name).write_bytes(png.read_bytes())
    for label, src in (
        ("run_sewer.headless.log", Path(args.headless_log)),
        ("run_sewer.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_sewer.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  live_logs_ok={live_logs_ok} godot_exe_ok={godot_exe_ok} "
        f"step_fixed_ok={step_fixed_ok} "
        f"banner_apply_h={banner_apply_h} banner_apply_w={banner_apply_w} "
        f"partial_apply={int(apply_info.get('succeeded', 0) or 0)} "
        f"ev_h={headless_ev_dir} ev_w={window_ev_dir} "
        f"godot_exe_bytes={godot_exe.stat().st_size if godot_exe.is_file() else 0}"
    )
    print(
        f"  NAME={name_v} GRAPH={graph} TOXIC={toxic} DIVE={dive} ROLL={roll} "
        f"CARGO={cargo} SPAWN={spawn} CAMERA={camera} TACTIC={tactic} "
        f"P1={p1} P2={p2} BOT={bot} ZONE={zone} LIVE={live} REPLAY={replay} "
        f"VARIANTS={variants} "
        f"APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    print(
        f"  live_reach={live_reach_ok} p1_all={p1_all} climb={climb_ok} "
        f"toxic_real={toxic_real} tactic_real={tactic_real} cargo_real={cargo_real}"
    )
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
