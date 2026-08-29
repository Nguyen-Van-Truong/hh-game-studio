#!/usr/bin/env python3
"""Assemble VF4-WP1 §18.3 evidence after official world runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF4WP1-20260829-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf4-wp1.world.1"
WP = "VF4-WP1"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/world/prop_spec.gd",
    "src/world/world_catalog.gd",
    "src/world/world_owner.gd",
    "src/world/world_paths.gd",
    "src/world/prop_body.gd",
    "src/world/prop_view.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "src/runtime/runtime_api.gd",
    "data/world/catalog.json",
    "data/world/schema.json",
    "data/sim/collision_layers.json",
    "data/sim/schema.json",
    "tests/world_cases.gd",
    "tests/run_world.gd",
    "tests/check_world.py",
    "tests/pack_world_evidence.py",
    "tests/run_all.gd",
    "docs/world.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/world/world_idle.json",
    "tests/traces/world/world_walk.json",
)

REQUIRED_KINDS = (
    "static",
    "dynamic",
    "one-way",
    "breakable",
    "pickup",
    "explosive",
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
    schema = outcome_verdict(outcomes, "schema")
    layers = outcome_verdict(outcomes, "layers")
    spawn = outcome_verdict(outcomes, "spawn")
    hashv = outcome_verdict(outcomes, "hash")
    orphan = outcome_verdict(outcomes, "orphan")
    pathv = outcome_verdict(outcomes, "path")
    present = outcome_verdict(outcomes, "present")
    author = outcome_verdict(outcomes, "author")
    data = outcome_verdict(outcomes, "data")
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
        schema == "pass"
        and layers == "pass"
        and spawn == "pass"
        and hashv == "pass"
        and orphan == "pass"
        and pathv == "pass"
        and present == "pass"
        and author == "pass"
        and data == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    schema_row = outcomes.get("schema", {}) if isinstance(outcomes.get("schema"), dict) else {}
    schema_real = bool(schema_row.get("reject_missing_collision")) and bool(
        schema_row.get("reject_missing_visual")
    )
    spawn_row = outcomes.get("spawn", {}) if isinstance(outcomes.get("spawn"), dict) else {}
    spawn_kinds = [str(x) for x in (spawn_row.get("kinds") or [])]
    spawn_real = int(spawn_row.get("count", 0)) >= 6 and set(REQUIRED_KINDS).issubset(spawn_kinds)
    hash_row = outcomes.get("hash", {}) if isinstance(outcomes.get("hash"), dict) else {}
    hash_real = bool(hash_row.get("idle")) and bool(hash_row.get("reboot"))
    orphan_row = outcomes.get("orphan", {}) if isinstance(outcomes.get("orphan"), dict) else {}
    orphan_real = int(orphan_row.get("title_leftover", 1)) == 0 and int(
        orphan_row.get("old_count", 0)
    ) >= 6
    path_row = outcomes.get("path", {}) if isinstance(outcomes.get("path"), dict) else {}
    path_real = (
        bool(path_row.get("reject_traversal"))
        and bool(path_row.get("reject_absolute"))
        and bool(path_row.get("accept_product"))
    )
    present_row = outcomes.get("present", {}) if isinstance(outcomes.get("present"), dict) else {}
    present_real = "cannot" in str(present_row.get("despawn", ""))
    author_row = outcomes.get("author", {}) if isinstance(outcomes.get("author"), dict) else {}
    author_real = int(author_row.get("rooftops", -1)) == 0 and int(
        author_row.get("fixture", 0)
    ) == int(author_row.get("placements", -1))
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
    events_ok = "prop_spawn" in event_kinds
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    screen_ok = len(screens) >= 1
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and schema_real
        and spawn_real
        and hash_real
        and orphan_real
        and path_real
        and present_real
        and author_real
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
        "schema": "vault-fighters.vf4-wp1.run.v1",
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
        "map_id": "fx_world_open",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "SCHEMA": schema,
            "LAYERS": layers,
            "SPAWN": spawn,
            "HASH": hashv,
            "ORPHAN": orphan,
            "PATH": pathv,
            "PRESENT": present,
            "AUTHOR": author,
            "DATA": data,
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
            "break_implemented": False,
            "chain_implemented": False,
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
            "RL-WORLD-SCHEMA",
            "RL-WORLD-LAYERS",
            "RL-WORLD-OWN",
            "RL-PROP-STATIC",
            "RL-PROP-DYNAMIC",
            "RL-PROP-ONEWAY",
            "RL-PROP-BREAK",
            "RL-PROP-PICKUP",
            "RL-PROP-EXPL",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_world.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_world.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_world.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "world_headless_exit": args.headless_exit,
            "world_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "schema": "assumption",
            "layers": "assumption",
            "own": "assumption",
            "break": "assumption",
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

    verdict_md = f"""# VF4-WP1 verdict

{verdict} world/prop schema and collision ownership (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP1)

Verify: schema rejects missing collision/visual; prop snapshot/hash stable;
no orphan after restart; editor/runtime paths remain inside product root.

DoD: map authoring không cần hard-code từng node trong GameSession.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_world_open`
- SCHEMA={schema} LAYERS={layers} SPAWN={spawn} HASH={hashv} ORPHAN={orphan} PATH={pathv} PRESENT={present} AUTHOR={author} DATA={data} LIVE={live} REPLAY={replay}
- SCHEMA reject_collision={schema_row.get("reject_missing_collision")} reject_visual={schema_row.get("reject_missing_visual")} real={schema_real}
- SPAWN count={spawn_row.get("count")} kinds={spawn_kinds} real={spawn_real}
- HASH idle={hash_row.get("idle")} reboot={hash_row.get("reboot")} real={hash_real}
- ORPHAN leftover={orphan_row.get("title_leftover")} old={orphan_row.get("old_count")} real={orphan_real}
- PATH traversal={path_row.get("reject_traversal")} absolute={path_row.get("reject_absolute")} real={path_real}
- PRESENT despawn={present_row.get("despawn")} real={present_real}
- AUTHOR rooftops={author_row.get("rooftops")} fixture={author_row.get("fixture")} real={author_real}
- events kinds include prop_spawn={events_ok}
- window screenshot={screen_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `WorldCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_world.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_world.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_world.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- World schema / layers / ownership stay assumption
  (`ledger:RL-WORLD-SCHEMA`, `ledger:RL-WORLD-LAYERS`,
  `ledger:RL-WORLD-OWN`).
- Static / dynamic / one-way / pickup stay assumption.
  Dynamic throw waits VF4-WP2.
- Breakable is schema only (`ledger:RL-PROP-BREAK`). Destroy waits VF4-WP2.
- Explosive prop is schema only (`ledger:RL-PROP-EXPL`). Chain waits VF4-WP3.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
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
        ("run_world.headless.log", Path(args.headless_log)),
        ("run_world.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_world.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  SCHEMA={schema} SPAWN={spawn} HASH={hashv} ORPHAN={orphan} "
        f"PATH={pathv} PRESENT={present} AUTHOR={author} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
