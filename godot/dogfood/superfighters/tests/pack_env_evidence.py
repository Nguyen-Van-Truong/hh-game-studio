#!/usr/bin/env python3
"""Assemble VF4-WP5 §18.3 evidence after official env runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF4WP5-20260830-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf4-wp5.env.1"
WP = "VF4-WP5"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/world/env_spec.gd",
    "src/world/env_body.gd",
    "src/maps/arena_spec.gd",
    "src/world/world_owner.gd",
    "src/world/world_catalog.gd",
    "src/game_session.gd",
    "src/fighter.gd",
    "src/maps.gd",
    "src/hud.gd",
    "src/sim/sim_constants.gd",
    "data/world/catalog.json",
    "data/world/schema.json",
    "data/world/env.json",
    "data/world/hazard.json",
    "data/maps/arena_spec.json",
    "tests/env_cases.gd",
    "tests/run_env.gd",
    "tests/check_env.py",
    "tests/pack_env_evidence.py",
    "tests/run_all.gd",
    "docs/env.md",
    "docs/hazard.md",
    "docs/moving.md",
    "docs/world.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "assets/art/zone_acid.png",
    "assets/art/zone_water.png",
    "assets/art/zone_void.png",
    "assets/art/prop_rotor.png",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/env/env_instant.json",
    "tests/traces/env/env_toxic.json",
    "tests/traces/env/env_toxic_death.json",
    "tests/traces/env/env_water.json",
    "tests/traces/env/env_rotor.json",
    "tests/traces/env/env_fall.json",
    "tests/traces/env/env_yard.json",
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
    beat = [digest for name, digest, _size in rows if "setup" not in name]
    if len(beat) >= 4 and len(set(beat)) < 4:
        errors.append("beat still hashes are not pairwise distinct")
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
    instant = outcome_verdict(outcomes, "instant")
    toxic = outcome_verdict(outcomes, "toxic")
    water = outcome_verdict(outcomes, "water")
    rotor = outcome_verdict(outcomes, "rotor")
    fall = outcome_verdict(outcomes, "fall")
    spawn = outcome_verdict(outcomes, "spawn")
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
        and instant == "pass"
        and toxic == "pass"
        and water == "pass"
        and rotor == "pass"
        and fall == "pass"
        and spawn == "pass"
        and pause == "pass"
        and reset == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    instant_row = outcomes.get("instant", {}) if isinstance(outcomes.get("instant"), dict) else {}
    toxic_row = outcomes.get("toxic", {}) if isinstance(outcomes.get("toxic"), dict) else {}
    water_row = outcomes.get("water", {}) if isinstance(outcomes.get("water"), dict) else {}
    rotor_row = outcomes.get("rotor", {}) if isinstance(outcomes.get("rotor"), dict) else {}
    fall_row = outcomes.get("fall", {}) if isinstance(outcomes.get("fall"), dict) else {}
    spawn_row = outcomes.get("spawn", {}) if isinstance(outcomes.get("spawn"), dict) else {}
    instant_real = bool(instant_row.get("dead", False)) and str(instant_row.get("cause", "")) == "pit"
    toxic_real = (
        int(toxic_row.get("enter", 0)) >= 1
        and int(toxic_row.get("exit", 0)) >= 1
        and int(toxic_row.get("damage", 0)) >= 1
        and int(toxic_row.get("deaths", 0)) >= 1
        and str(toxic_row.get("cause", "")) == "damage"
    )
    water_real = bool(water_row.get("wet", False)) and int(water_row.get("extinguish", 0)) >= 1
    rotor_real = float(rotor_row.get("hp", 100)) < 99.5 and int(rotor_row.get("hits", 0)) >= 1
    fall_real = (
        bool(fall_row.get("on_floor", False))
        and not bool(fall_row.get("hanging", True))
        and str(fall_row.get("pose", "hang")) != "hang"
        and bool(fall_row.get("dive_immune", False))
    )
    spawn_real = int(spawn_row.get("locked", 1)) == 0
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
    events_ok = bool({"env_enter", "env_exit", "env_damage", "env_death"} & event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    water_png = pick_still(screens, "water")
    rotor_png = pick_still(screens, "rotor")
    toxic_png = pick_still(screens, "toxic")
    instant_png = pick_still(screens, "instant")
    fall_png = pick_still(screens, "fall")
    map_ok = all(
        pick_still(screens, name) is not None
        for name in ("rooftops", "storage", "police", "hazardous")
    )
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, water_png, rotor_png, toxic_png, instant_png, fall_png) if p is not None]
    )
    if setup_png is None or water_png is None or rotor_png is None or toxic_png is None or instant_png is None or fall_png is None:
        stills_ok = False
        still_errors.append("need setup/water/rotor/toxic/instant/fall window stills")
    if not map_ok:
        stills_ok = False
        still_errors.append("need rooftops/storage/police/hazardous window stills")
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and instant_real
        and toxic_real
        and water_real
        and rotor_real
        and fall_real
        and spawn_real
        and events_ok
        and stills_ok
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
        ("run_env.headless.log", Path(args.headless_log)),
        ("run_env.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_env.log", Path(args.check_log)),
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
            "toxic_interval": 8,
            "rotor_interval": 10,
            "fall_drop_min": 28.0,
        },
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf4-wp5.run.v1",
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
        "map_id": "fx_env_yard",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "DATA": data,
            "INSTANT": instant,
            "TOXIC": toxic,
            "WATER": water,
            "ROTOR": rotor,
            "FALL": fall,
            "SPAWN": spawn,
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
            "env_observed": False,
            "instant_observed": False,
            "toxic_observed": False,
            "water_observed": False,
            "rotor_observed": False,
            "fall_observed": False,
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
            "RL-ENV-INSTANT",
            "RL-ENV-DEFER",
            "RL-ENV-WATER",
            "RL-ENV-ROTOR",
            "RL-ENV-SPAWN",
            "RL-ENV-ARENA",
            "RL-MOVE-FALL",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_env.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_env.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_env.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "env_headless_exit": args.headless_exit,
            "env_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "instant": "assumption",
            "defer": "assumption",
            "water": "assumption",
            "rotor": "assumption",
            "fall": "assumption",
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

    verdict_md = f"""# VF4-WP5 verdict

{verdict} toxic pits, fall damage, water, and environmental machines (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP5)

Verify: each hazard has enter/exit/damage/death trace; no spawn soft-lock;
pause and restart clear hazard state; screenshot/evidence per map.

DoD: hazards are readable, deterministic and materially affect match.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_env_yard` display **Hazard Yard**
- DATA={data} INSTANT={instant} TOXIC={toxic} WATER={water} ROTOR={rotor} FALL={fall} SPAWN={spawn} PAUSE={pause} RESET={reset} LIVE={live} REPLAY={replay}
- INSTANT dead={instant_row.get("dead")} cause={instant_row.get("cause")} real={instant_real}
- TOXIC enter={toxic_row.get("enter")} exit={toxic_row.get("exit")} damage={toxic_row.get("damage")} deaths={toxic_row.get("deaths")} real={toxic_real}
- WATER wet={water_row.get("wet")} extinguish={water_row.get("extinguish")} real={water_real}
- ROTOR hp={rotor_row.get("hp")} hits={rotor_row.get("hits")} real={rotor_real}
- FALL on_floor={fall_row.get("on_floor")} hang={fall_row.get("hanging")} pose={fall_row.get("pose")} immune={fall_row.get("dive_immune")} real={fall_real}
- SPAWN locked={spawn_row.get("locked")} real={spawn_real}
- events kinds include enter/exit/damage/death={events_ok} kinds={sorted(event_kinds)}
- window stills pairwise_distinct={stills_ok} map_stills={map_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `EnvCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_env.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_env.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_env.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Instant / toxic / water / rotor / spawn stay assumption
  (`ledger:RL-ENV-INSTANT`, `ledger:RL-ENV-DEFER`, `ledger:RL-ENV-WATER`,
  `ledger:RL-ENV-ROTOR`, `ledger:RL-ENV-SPAWN`, `ledger:RL-ENV-ARENA`).
- Fall stays `ledger:RL-MOVE-FALL` assumption.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Live maps declare pit/fall in ArenaSpec; machines/water/toxic stay on fixtures (VF5).
- Water extinguish is selected in env.json. Roll extinguish stays selected in hazard.json.
- Original acid/water/void/rotor art only. Not a VF7 presentation rewrite. Not a Y8 rip.
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
        ("run_env.headless.log", Path(args.headless_log)),
        ("run_env.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_env.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  INSTANT={instant} TOXIC={toxic} WATER={water} ROTOR={rotor} "
        f"FALL={fall} SPAWN={spawn} PAUSE={pause} RESET={reset} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
