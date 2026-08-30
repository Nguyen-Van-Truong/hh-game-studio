#!/usr/bin/env python3
"""Assemble VF5-WP1 §18.3 evidence after official map runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF5WP1-20260830-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf5-wp1.map-schema.1"
WP = "VF5-WP1"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/maps/map_codec.gd",
    "src/maps/map_catalog.gd",
    "src/maps/map_graph.gd",
    "src/maps/map_validator.gd",
    "src/maps/map_author.gd",
    "src/maps/arena_spec.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/sim/sim_constants.gd",
    "data/maps/schema.json",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/rooftops.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/hazardous.json",
    "data/maps/arenas/fx_map_author.json",
    "tests/map_cases.gd",
    "tests/run_map.gd",
    "tests/check_map.py",
    "tests/pack_map_evidence.py",
    "tests/run_all.gd",
    "docs/maps.md",
    "docs/env.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/maps/map_author.json",
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
    schema_v = outcome_verdict(outcomes, "schema")
    roundtrip = outcome_verdict(outcomes, "roundtrip")
    graph = outcome_verdict(outcomes, "graph")
    reject = outcome_verdict(outcomes, "reject")
    author = outcome_verdict(outcomes, "author")
    width_v = outcome_verdict(outcomes, "width")
    spawn = outcome_verdict(outcomes, "spawn")
    pit = outcome_verdict(outcomes, "pit")
    camera = outcome_verdict(outcomes, "camera")
    overlap = outcome_verdict(outcomes, "overlap")
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
        schema_v == "pass"
        and roundtrip == "pass"
        and graph == "pass"
        and reject == "pass"
        and author == "pass"
        and width_v == "pass"
        and spawn == "pass"
        and pit == "pass"
        and camera == "pass"
        and overlap == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    live_row = outcomes.get("live", {}) if isinstance(outcomes.get("live"), dict) else {}
    author_row = outcomes.get("author", {}) if isinstance(outcomes.get("author"), dict) else {}
    live_real = bool(live_row.get("on_floor", False)) and bool(live_row.get("moved", False))
    author_real = str(author_row.get("hash", "")) != "" and str(author_row.get("hash", "")) == str(
        author_row.get("shipped", "x")
    )
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
    events_ok = bool({"map_roundtrip", "map_graph", "map_reject", "map_author"} <= event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    roof_png = pick_still(screens, "rooftops")
    storage_png = pick_still(screens, "storage")
    police_png = pick_still(screens, "police")
    haz_png = pick_still(screens, "hazardous")
    author_png = pick_still(screens, "author")
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, roof_png, storage_png, police_png, haz_png, author_png) if p is not None]
    )
    if None in (setup_png, roof_png, storage_png, police_png, haz_png, author_png):
        stills_ok = False
        still_errors.append("need setup/rooftops/storage/police/hazardous/author window stills")
    verdict = (
        "PASS"
        if exits_ok and outcomes_ok and live_real and author_real and events_ok and stills_ok
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
        ("run_map.headless.log", Path(args.headless_log)),
        ("run_map.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_map.log", Path(args.check_log)),
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
        "schema": "vault-fighters.vf5-wp1.run.v1",
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
        "seed": 11,
        "map_id": "rooftops",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "SCHEMA": schema_v,
            "ROUNDTRIP": roundtrip,
            "GRAPH": graph,
            "REJECT": reject,
            "AUTHOR": author,
            "WIDTH": width_v,
            "SPAWN": spawn,
            "PIT": pit,
            "CAMERA": camera,
            "OVERLAP": overlap,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "map_layers_observed": False,
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
            "RL-MAP-LAYERS",
            "RL-MAP-GRAPH",
            "RL-MAP-VALID",
            "RL-MAP-AUTHOR",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_map.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_map.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_map.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "map_headless_exit": args.headless_exit,
            "map_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "layers": "assumption",
            "graph": "assumption",
            "valid": "assumption",
            "author": "assumption",
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

    verdict_md = f"""# VF5-WP1 verdict

{verdict} layered map schema, topology validator, and semantic authoring (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP1)

Verify: serialize/deserialize hash; graph reaches every required platform;
validator bắt map hỏng; editor agent tạo map bằng semantic commands.

DoD: map không còn phụ thuộc chuỗi ký tự khó mở rộng.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `11`, mode `vs2`, map `rooftops` display **Rooftops**
- authored map `fx_map_author` display **Draft Yard**
- SCHEMA={schema_v} ROUNDTRIP={roundtrip} GRAPH={graph} REJECT={reject} AUTHOR={author} WIDTH={width_v} SPAWN={spawn} PIT={pit} CAMERA={camera} OVERLAP={overlap} LIVE={live} REPLAY={replay}
- LIVE on_floor={live_row.get("on_floor")} moved={live_row.get("moved")} author_on_floor={live_row.get("author_on_floor")} real={live_real}
- AUTHOR hash={author_row.get("hash")} shipped={author_row.get("shipped")} real={author_real}
- events kinds include schema/graph/reject/author={events_ok} kinds={sorted(event_kinds)}
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `MapCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_map.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_map.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_map.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Layer / graph / validator / author stay assumption
  (`ledger:RL-MAP-LAYERS`, `ledger:RL-MAP-GRAPH`,
  `ledger:RL-MAP-VALID`, `ledger:RL-MAP-AUTHOR`).
- Jump envelope is product tuning (dx=10 / dy=4), not observed Y8 reach.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` now live on prop/hazard layers but still paint as tiles.
- Combat/env fixture ASCII rows stay import-only; not a VF5-WP2..6 layout pass.
- Display names Rooftops/Storage/Police Station/Hazardous stay known debt
  (`ledger:RL-DELTA-MAP-NAMES`) until VF5-WP2+.
- Draft Yard is an original authoring demo, not a Y8 map name.
- Geometry of the four live maps is unchanged this WP (no new layout).
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
        ("run_map.headless.log", Path(args.headless_log)),
        ("run_map.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_map.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  SCHEMA={schema_v} ROUNDTRIP={roundtrip} GRAPH={graph} REJECT={reject} "
        f"AUTHOR={author} LIVE={live} REPLAY={replay} APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
