#!/usr/bin/env python3
"""Assemble VF5-WP2 §18.3 evidence after official Skyline Relay runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF5WP2-20260830-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf5-wp2.skyline-relay.2"
WP = "VF5-WP2"
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
    "data/maps/schema.json",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/rooftops.json",
    "data/world/catalog.json",
    "tests/rooftop_cases.gd",
    "tests/run_rooftop.gd",
    "tests/check_rooftop.py",
    "tests/pack_rooftop_evidence.py",
    "tests/map_cases.gd",
    "tests/world_cases.gd",
    "tests/runtime_cases.gd",
    "tests/run_all.gd",
    "tests/_gen_map_layers.py",
    "docs/rooftop.md",
    "docs/maps.md",
    "docs/world.md",
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
    elev = outcome_verdict(outcomes, "elev")
    zone = outcome_verdict(outcomes, "zone")
    cover = outcome_verdict(outcomes, "cover")
    p1 = outcome_verdict(outcomes, "p1")
    p2 = outcome_verdict(outcomes, "p2")
    bot = outcome_verdict(outcomes, "bot")
    pit = outcome_verdict(outcomes, "pit")
    fallback = outcome_verdict(outcomes, "fallback")
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
        name_v == "pass"
        and elev == "pass"
        and zone == "pass"
        and cover == "pass"
        and p1 == "pass"
        and p2 == "pass"
        and bot == "pass"
        and pit == "pass"
        and fallback == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    live_row = outcomes.get("live", {}) if isinstance(outcomes.get("live"), dict) else {}
    p1_row = outcomes.get("p1", {}) if isinstance(outcomes.get("p1"), dict) else {}
    p2_row = outcomes.get("p2", {}) if isinstance(outcomes.get("p2"), dict) else {}
    bot_row = outcomes.get("bot", {}) if isinstance(outcomes.get("bot"), dict) else {}
    zone_row = outcomes.get("zone", {}) if isinstance(outcomes.get("zone"), dict) else {}
    cover_row = outcomes.get("cover", {}) if isinstance(outcomes.get("cover"), dict) else {}
    bridge_still = outcomes.get("bridge_still", {}) if isinstance(outcomes.get("bridge_still"), dict) else {}
    cover_still = outcomes.get("cover_still", {}) if isinstance(outcomes.get("cover_still"), dict) else {}
    live_real = str(live_row.get("hud", "")) == "Skyline Relay"
    cover_real = bool(cover_row.get("blocked_before", False)) and int(cover_row.get("breaks", 0)) >= 1
    p1_hits = p1_row.get("hits") if isinstance(p1_row.get("hits"), dict) else {}
    required_zones = (
        "west_deck",
        "mid_deck",
        "east_deck",
        "west_bridge",
        "east_bridge",
        "west_spire",
    )
    p1_all = all(bool(p1_hits.get(zid)) for zid in required_zones)
    climb_ok = int(zone_row.get("climb_up_on_ladder", 0) or p1_row.get("climb_up_on_ladder", 0)) >= 8
    spire_stand = bool(zone_row.get("west_spire_standing", False) or p1_row.get("west_spire_standing", False))
    east_live = bool(zone_row.get("east_deck_live", False) or p1_hits.get("east_deck", False))
    bridge_ok = (
        bool(bridge_still.get("alive", False))
        and bool(bridge_still.get("on_floor", False))
        and not bool(bridge_still.get("lose_visible", True))
        and str(bridge_still.get("zone", "")) in {"west_bridge", "east_bridge"}
    )
    cover_still_ok = (
        bool(cover_still.get("alive", False))
        and bool(cover_still.get("on_floor", False))
        and not bool(cover_still.get("lose_visible", True))
        and str(cover_still.get("zone", "")) == "west_spire"
    )
    live_reach_ok = p1_all and climb_ok and spire_stand and east_live and bridge_ok and cover_still_ok
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
    events_ok = bool({"roof_name", "roof_zone", "roof_p1", "roof_pit"} <= event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    title_png = pick_still(screens, "title")
    bridge_png = pick_still(screens, "bridge")
    cover_png = pick_still(screens, "cover")
    pit_png = pick_still(screens, "pit")
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, title_png, bridge_png, cover_png, pit_png) if p is not None]
    )
    if None in (setup_png, title_png, bridge_png, cover_png, pit_png):
        stills_ok = False
        still_errors.append("need setup/title/bridge/cover/pit window stills")
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and live_real
        and cover_real
        and events_ok
        and stills_ok
        and live_reach_ok
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
        ("run_rooftop.headless.log", Path(args.headless_log)),
        ("run_rooftop.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_rooftop.log", Path(args.check_log)),
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
        "schema": "vault-fighters.vf5-wp2.run.v1",
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
        "seed": 12,
        "map_id": "rooftops",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "outcomes": {
            "NAME": name_v,
            "ELEV": elev,
            "ZONE": zone,
            "COVER": cover,
            "P1": p1,
            "P2": p2,
            "BOT": bot,
            "PIT": pit,
            "FALLBACK": fallback,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "map_skyline_observed": False,
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
            "RL-MAP-SKYLINE",
            "RL-DELTA-MAP-NAMES",
            "RL-MAP-GRAPH",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_rooftop.py",
                "python godot/dogfood/superfighters/tests/check_map.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_rooftop.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_rooftop.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "roof_headless_exit": args.headless_exit,
            "roof_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "skyline": "assumption",
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

    verdict_md = f"""# VF5-WP2 verdict

{verdict} Skyline Relay rooftop/bridge arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP2)

Verify: P1/P2/bot reach all combat zones; pit and fallback tests; screenshot
landmarks; no copied billboard/geometry.

DoD: vertical scramble và high-ground tactics hoạt động.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `12`, mode `vs2`, map `rooftops` display **Skyline Relay**
- NAME={name_v} ELEV={elev} ZONE={zone} COVER={cover} P1={p1} P2={p2} BOT={bot} PIT={pit} FALLBACK={fallback} LIVE={live} REPLAY={replay}
- LIVE hud={live_row.get("hud")} real={live_real}
- P1 hits={p1_row.get("hits")} P2 hits={p2_row.get("hits")} BOT hits={bot_row.get("hits")}
- live_reach p1_all={p1_all} climb_up_on_ladder={climb_ok} west_spire_standing={spire_stand} east_deck={east_live}
- bridge_still={bridge_still} cover_still={cover_still} bridge_ok={bridge_ok} cover_still_ok={cover_still_ok}
- COVER blocked_before={cover_row.get("blocked_before")} breaks={cover_row.get("breaks")} real={cover_real}
- events kinds include name/zone/p1/pit={events_ok} kinds={sorted(event_kinds)}
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `RooftopCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_rooftop.py
python godot/dogfood/superfighters/tests/check_map.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_rooftop.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_rooftop.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Skyline Relay topology stays assumption (`ledger:RL-MAP-SKYLINE`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
  Additive ladders, including a west_spire climb, make high ground reachable
  without rewriting that envelope into observed Y8.
- ZONE / P1 / P2 / BOT are live body positions during apply_frames.
  MapGraph is a helper only. Official routes hold `up` on ladder cells.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` still paint as tiles on other maps. This WP placed original
  breakable cover on Skyline Relay only.
- Machines / water / toxic / lifts / doors stay fixture-only. Ladders satisfy
  the ladder/elevator-or-moving-route beat.
- Display names Storage / Police Station / Hazardous stay
  `ledger:RL-DELTA-MAP-NAMES` debt until VF5-WP3+.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
- Not Y8 parity. Not V0.
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
        ("run_rooftop.headless.log", Path(args.headless_log)),
        ("run_rooftop.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_rooftop.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  NAME={name_v} ELEV={elev} ZONE={zone} COVER={cover} "
        f"P1={p1} P2={p2} BOT={bot} PIT={pit} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    print(
        f"  live_reach={live_reach_ok} p1_all={p1_all} climb={climb_ok} "
        f"spire_stand={spire_stand} east_deck={east_live} "
        f"bridge_ok={bridge_ok} cover_still_ok={cover_still_ok}"
    )
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
