#!/usr/bin/env python3
"""Assemble VF4-WP4 §18.3 evidence after official moving runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF4WP4-20260830-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf4-wp4.moving.2"
WP = "VF4-WP4"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/world/moving_spec.gd",
    "src/world/moving_body.gd",
    "src/world/world_owner.gd",
    "src/world/world_catalog.gd",
    "src/world/prop_spec.gd",
    "src/world/prop_view.gd",
    "src/game_session.gd",
    "src/fighter.gd",
    "src/maps.gd",
    "src/visuals.gd",
    "src/hud.gd",
    "src/sim/sim_constants.gd",
    "data/world/catalog.json",
    "data/world/schema.json",
    "data/world/moving.json",
    "data/sim/schema.json",
    "tests/moving_cases.gd",
    "tests/run_moving.gd",
    "tests/check_moving.py",
    "tests/pack_moving_evidence.py",
    "tests/run_all.gd",
    "tests/hazard_cases.gd",
    "tests/check_hazard.py",
    "tests/break_cases.gd",
    "tests/check_break.py",
    "tests/world_cases.gd",
    "tests/check_world.py",
    "docs/moving.md",
    "docs/hazard.md",
    "docs/break.md",
    "docs/world.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "assets/art/prop_door.png",
    "assets/art/prop_lift.png",
    "assets/art/prop_trigger.png",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/moving/move_door.json",
    "tests/traces/moving/move_ride.json",
    "tests/traces/moving/move_drop.json",
    "tests/traces/moving/move_yard.json",
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
    named = {name: digest for name, digest, _size in rows}
    beat = [digest for name, digest, _size in rows if "setup" not in name]
    if len(beat) >= 3 and len(set(beat)) < 3:
        errors.append("door/ride/drop hashes are not pairwise distinct")
    if "move_door" in "".join(named) and len({named.get(k, "") for k in named if "door" in k or "ride" in k or "drop" in k}) < 3:
        errors.append("door/ride/drop stills share a hash")
    return (not errors, hashes, errors)


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
    data = outcome_verdict(outcomes, "data")
    ride = outcome_verdict(outcomes, "ride")
    carry = outcome_verdict(outcomes, "carry")
    drop = outcome_verdict(outcomes, "drop")
    door = outcome_verdict(outcomes, "door")
    trigger = outcome_verdict(outcomes, "trigger")
    pause = outcome_verdict(outcomes, "pause")
    reset = outcome_verdict(outcomes, "reset")
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
        data == "pass"
        and ride == "pass"
        and carry == "pass"
        and drop == "pass"
        and door == "pass"
        and trigger == "pass"
        and pause == "pass"
        and reset == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    ride_row = outcomes.get("ride", {}) if isinstance(outcomes.get("ride"), dict) else {}
    carry_row = outcomes.get("carry", {}) if isinstance(outcomes.get("carry"), dict) else {}
    drop_row = outcomes.get("drop", {}) if isinstance(outcomes.get("drop"), dict) else {}
    door_row = outcomes.get("door", {}) if isinstance(outcomes.get("door"), dict) else {}
    trigger_row = outcomes.get("trigger", {}) if isinstance(outcomes.get("trigger"), dict) else {}
    ride_real = (
        float(ride_row.get("y1", 99)) < float(ride_row.get("y0", 0)) - 20.0
        and int(ride_row.get("tunnels", 1)) == 0
        and int(ride_row.get("owner_tunnels", 1)) == 0
        and not bool(ride_row.get("hanging", True))
        and str(ride_row.get("pose", "hang")) != "hang"
        and bool(ride_row.get("on_floor", False))
        and float(ride_row.get("max_board_dy", 99.0)) < 16.0
    )
    carry_real = (
        float(carry_row.get("ly1", 99)) < float(carry_row.get("ly0", 0)) - 20.0
        and int(carry_row.get("boards", 0)) >= 1
    )
    drop_y = float(drop_row.get("y_end", 999))
    drop_real = (
        bool(drop_row.get("on_floor", False))
        and not bool(drop_row.get("hanging", True))
        and str(drop_row.get("pose", "hang")) != "hang"
        and 60.0 <= drop_y <= 76.0
        and float(drop_row.get("ly_end", 0)) >= 140.0
        and int(drop_row.get("unboards", 0)) >= 1
        and float(drop_row.get("max_board_dy", 99.0)) < 16.0
    )
    door_real = (
        float(door_row.get("x_block", 999)) <= 240.0
        and float(door_row.get("x_open", 0)) >= 260.0
    )
    trigger_real = int(trigger_row.get("events", 0)) >= 1
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
    events_ok = bool({"door_open", "board", "unboard", "trigger_fire", "platform_call"} & event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    door_png = pick_still(screens, "door")
    ride_png = pick_still(screens, "ride")
    drop_png = pick_still(screens, "drop")
    door_ok = door_png is not None
    ride_ok = ride_png is not None
    drop_ok = drop_png is not None
    setup_ok = setup_png is not None
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, door_png, ride_png, drop_png) if p is not None]
    )
    if not setup_ok or not door_ok or not ride_ok or not drop_ok:
        stills_ok = False
        still_errors.append("need setup/door/ride/drop window stills")
    screen_ok = stills_ok
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and ride_real
        and carry_real
        and drop_real
        and door_real
        and trigger_real
        and events_ok
        and screen_ok
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
        ("run_moving.headless.log", Path(args.headless_log)),
        ("run_moving.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_moving.log", Path(args.check_log)),
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
            "travel_ticks": 44,
            "max_step_px": 3.0,
            "arm_ticks": 8,
        },
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf4-wp4.run.v1",
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
        "seed": 7,
        "map_id": "fx_move_yard",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "DATA": data,
            "RIDE": ride,
            "CARRY": carry,
            "DROP": drop,
            "DOOR": door,
            "TRIGGER": trigger,
            "PAUSE": pause,
            "RESET": reset,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "world_observed": False,
            "door_observed": False,
            "lift_observed": False,
            "board_observed": False,
            "trigger_observed": False,
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
            "RL-WORLD-DOOR",
            "RL-WORLD-LIFT",
            "RL-WORLD-BOARD",
            "RL-WORLD-TRIGGER",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_moving.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_moving.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_moving.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "moving_headless_exit": args.headless_exit,
            "moving_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "door": "assumption",
            "lift": "assumption",
            "board": "assumption",
            "trigger": "assumption",
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

    verdict_md = f"""# VF4-WP4 verdict

{verdict} doors, elevators/moving platforms, and traversal triggers (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP4)

Verify: actors ride without tunneling, platform carries/drop safely, door
blocks/opens at correct state, fixed-tick replay equal.

DoD: vertical map routes are functional rather than decorative.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_move_yard` display **Relay Shaft**
- DATA={data} RIDE={ride} CARRY={carry} DROP={drop} DOOR={door} TRIGGER={trigger} PAUSE={pause} RESET={reset} LIVE={live} REPLAY={replay}
- RIDE y0={ride_row.get("y0")} y1={ride_row.get("y1")} tunnels={ride_row.get("tunnels")} on_floor={ride_row.get("on_floor")} hang={ride_row.get("hanging")} pose={ride_row.get("pose")} max_dy={ride_row.get("max_board_dy")} real={ride_real}
- CARRY ly0={carry_row.get("ly0")} ly1={carry_row.get("ly1")} boards={carry_row.get("boards")} real={carry_real}
- DROP y_end={drop_row.get("y_end")} ly_end={drop_row.get("ly_end")} unboards={drop_row.get("unboards")} on_floor={drop_row.get("on_floor")} hang={drop_row.get("hanging")} pose={drop_row.get("pose")} max_dy={drop_row.get("max_board_dy")} real={drop_real}
- DOOR x_block={door_row.get("x_block")} x_open={door_row.get("x_open")} real={door_real}
- TRIGGER events={trigger_row.get("events")} real={trigger_real}
- events kinds include door/board/trigger={events_ok} kinds={sorted(event_kinds)}
- window stills setup={setup_ok} door={door_ok} ride={ride_ok} drop={drop_ok} pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `MovingCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_moving.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_moving.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_moving.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Door / lift / board / trigger stay assumption (`ledger:RL-WORLD-DOOR`,
  `ledger:RL-WORLD-LIFT`, `ledger:RL-WORLD-BOARD`,
  `ledger:RL-WORLD-TRIGGER`).
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Water is not selected (VF4-WP5).
- Original door/lift/trigger art only. Not a VF7 presentation rewrite. Not a Y8 rip.
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
        ("run_moving.headless.log", Path(args.headless_log)),
        ("run_moving.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_moving.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  RIDE={ride} CARRY={carry} DROP={drop} DOOR={door} "
        f"TRIGGER={trigger} PAUSE={pause} RESET={reset} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
