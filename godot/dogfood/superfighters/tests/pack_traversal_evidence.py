#!/usr/bin/env python3
"""Assemble VF2-WP5 §18.3 evidence after official traversal runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF2WP5-20260829-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf2-wp5.ladder-ledge.3"
WP = "VF2-WP5"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/hud.gd",
    "src/visuals.gd",
    "src/sfx_bank.gd",
    "src/input_actions.gd",
    "src/sim/traversal.gd",
    "src/sim/locomotion.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "src/sim/sim_validator.gd",
    "src/runtime/runtime_checkpoint.gd",
    "src/runtime/runtime_api.gd",
    "data/sim/traversal.json",
    "data/sim/locomotion.json",
    "data/sim/schema.json",
    "tests/traversal_cases.gd",
    "tests/run_traversal.gd",
    "tests/check_traversal.py",
    "tests/pack_traversal_evidence.py",
    "tests/run_all.gd",
    "docs/traversal.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/traversal/ladder_up_down.json",
    "tests/traces/traversal/ladder_block.json",
    "tests/traces/traversal/ledge_recover.json",
    "tests/traces/traversal/drop_through.json",
    "tests/traces/traversal/cross_dirs.json",
    "tests/traces/traversal/map_rooftops.json",
    "tests/traces/traversal/map_storage.json",
    "tests/traces/traversal/map_police.json",
    "tests/traces/traversal/map_hazardous.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    review.mkdir(parents=True, exist_ok=True)

    outcomes = load_json(window_ev / "outcomes.json") or load_json(headless_ev / "outcomes.json")
    partial_h = load_json(headless_ev / "run_partial.json")
    partial_w = load_json(window_ev / "run_partial.json")
    source_sha = {}
    for rel in SOURCE_FILES:
        path = product / rel
        if path.is_file():
            source_sha[rel] = sha256_file(path)
    trace_sha = {}
    for rel in TRACE_FILES:
        path = product / rel
        if path.is_file():
            trace_sha[rel] = sha256_file(path)
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    godot_exe = Path(args.godot_exe)
    godot_hash = sha256_file(godot_exe) if godot_exe.is_file() else ""

    apply_info = outcomes.get("apply", {})
    ladder = outcome_verdict(outcomes, "ladder")
    ledge = outcome_verdict(outcomes, "ledge")
    drop = outcome_verdict(outcomes, "drop")
    block = outcome_verdict(outcomes, "block")
    dirs = outcome_verdict(outcomes, "dirs")
    maps = outcome_verdict(outcomes, "maps")
    stuck = outcome_verdict(outcomes, "stuck")
    contact = outcome_verdict(outcomes, "contact")
    live = outcome_verdict(outcomes, "live")
    replay = outcome_verdict(outcomes, "replay")
    succeeded = int(apply_info.get("succeeded", 0))
    attempted = int(apply_info.get("attempted", 0))
    exits_ok = (
        args.check_exit == 0
        and args.headless_exit == 0
        and args.window_exit == 0
        and args.run_all_exit == 0
        and args.leftover == 0
    )
    outcomes_ok = (
        ladder == "pass"
        and ledge == "pass"
        and drop == "pass"
        and block == "pass"
        and dirs == "pass"
        and maps == "fixtures_only"
        and stuck == "pass"
        and contact == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    drop_row = outcomes.get("drop", {}) if isinstance(outcomes.get("drop"), dict) else {}
    y0 = float(drop_row.get("y0", 0.0) or 0.0)
    y1 = float(drop_row.get("y1", 0.0) or 0.0)
    drop_eps = float(drop_row.get("drop_eps", 8.0) or 8.0)
    drop_fell = y1 > y0 + drop_eps
    ledge_row = outcomes.get("ledge", {}) if isinstance(outcomes.get("ledge"), dict) else {}
    ledge_boarded = bool(ledge_row.get("boarded", False)) and bool(ledge_row.get("on_floor", False))
    ledge_near = bool(ledge_row.get("near_stand", False))
    ledge_idle_ok = bool(ledge_row.get("idle_boarded", False)) and not bool(ledge_row.get("idle_wedged", True))
    stand_dist = float(ledge_row.get("stand_dist", 99.0) or 99.0)
    dirs_row = outcomes.get("dirs", {}) if isinstance(outcomes.get("dirs"), dict) else {}
    dir_fixtures = dirs_row.get("fixtures", []) if isinstance(dirs_row.get("fixtures"), list) else []
    dirs_real = True
    for row in dir_fixtures:
        if not isinstance(row, dict):
            dirs_real = False
            break
        if abs(float(row.get("dx_right", 0.0) or 0.0)) < 4.0:
            dirs_real = False
        if abs(float(row.get("dx_left", 0.0) or 0.0)) < 4.0:
            dirs_real = False
        if abs(float(row.get("dy_up", 0.0) or 0.0)) < 4.0:
            dirs_real = False
        if abs(float(row.get("dy_down", 0.0) or 0.0)) < 4.0:
            dirs_real = False
    if not dir_fixtures:
        dirs_real = False
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
    events_ok = {"drop_through", "ledge_grab", "ledge_recover"}.issubset(event_kinds)
    maps_row = outcomes.get("maps", {}) if isinstance(outcomes.get("maps"), dict) else {}
    maps_honest = maps == "fixtures_only" and maps_row.get("stage_navigated") is False
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and drop_fell
        and dirs_real
        and events_ok
        and maps_honest
        and ledge_boarded
        and ledge_near
        and ledge_idle_ok
        and stand_dist < 8.0001
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
        },
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf2-wp5.run.v1",
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
        "seed": 1,
        "map_id": "fx_ladder",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "LADDER": ladder,
            "LEDGE": ledge,
            "DROP": drop,
            "BLOCK": block,
            "DIRS": dirs,
            "MAPS": maps,
            "STUCK": stuck,
            "CONTACT": contact,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "hold_to_aim_observed": False,
            "sprint_observed": False,
            "roll_observed": False,
            "dive_observed": False,
            "kick_observed": False,
            "fall_observed": False,
            "ladder_observed": False,
            "ledge_observed": False,
            "drop_observed": False,
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
            "RL-MOVE-LADDER",
            "RL-MOVE-LEDGE",
            "RL-MOVE-DROP",
            "RL-MOVE-ROLL-DIVE",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_traversal.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_traversal.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_traversal.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "traverse_headless_exit": args.headless_exit,
            "traverse_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "hold_to_aim": "assumption",
            "ladder": "assumption",
            "ledge": "assumption",
            "drop": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF2-WP5 verdict

{verdict} ladder, ledge, and drop-through evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF2-WP5)

Verify: traverse up/down/all four directions on every map fixture; no stuck,
teleport or ladder climb through solid; replay hash stable.

DoD: topology can actually be navigated, not merely drawn.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `1`, mode `vs2`, map `fx_ladder`
- LADDER={ladder} LEDGE={ledge} DROP={drop} BLOCK={block} DIRS={dirs} MAPS={maps} STUCK={stuck} CONTACT={contact} LIVE={live} REPLAY={replay}
- LEDGE boarded={ledge_boarded} on_floor={ledge_row.get("on_floor")} stand_dist={stand_dist:.3f} end=({ledge_row.get("end_x")}, {ledge_row.get("end_y")}) stand=({ledge_row.get("stand_x")}, {ledge_row.get("stand_y")}) idle_wedged={ledge_row.get("idle_wedged")} pose={ledge_row.get("pose")}
- DROP y0={y0} y1={y1} dy={y1 - y0:.3f} eps={drop_eps} fell={drop_fell}
- DIRS measured displacements={dirs_real}
- events kinds include drop_through/ledge_grab/ledge_recover={events_ok}
- MAPS stage_navigated=false (fixtures-only; rooftops/storage/police/hazardous not claimed)
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `TraversalCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_traversal.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_traversal.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Ladder stays `ledger:RL-MOVE-LADDER` assumption, not observed.
- Ledge stays `ledger:RL-MOVE-LEDGE` assumption, not observed.
- Drop stays `ledger:RL-MOVE-DROP` assumption, not observed.
- InputFrame action `ledge` stays reserved.
- Sprint / roll / dive / kick / fall stay assumption.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- No new in-game Y8 play this WP.
- Not Y8 parity. Not V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.
"""
    (evidence / "verdict.md").write_text(verdict_md, encoding="utf-8")

    hash_rows: list[str] = [f"# {RUN_ID}", "# SHA-256; hashes.txt not self-hashed"]
    for rel, digest in sorted({**source_sha, **trace_sha}.items()):
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
        ("run_traversal.headless.log", Path(args.headless_log)),
        ("run_traversal.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_traversal.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  LADDER={ladder} LEDGE={ledge} DROP={drop} BLOCK={block} "
        f"DIRS={dirs} MAPS={maps} STUCK={stuck} CONTACT={contact} LIVE={live} "
        f"REPLAY={replay} APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
