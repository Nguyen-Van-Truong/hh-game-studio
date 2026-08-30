#!/usr/bin/env python3
"""Assemble VF5-WP3 §18.3 evidence after official Pallet Annex runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF5WP3-20260830-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf5-wp3.pallet-annex.1"
WP = "VF5-WP3"
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
    "data/maps/arenas/storage.json",
    "data/maps/arenas/rooftops.json",
    "data/world/catalog.json",
    "data/world/moving.json",
    "tests/warehouse_cases.gd",
    "tests/run_warehouse.gd",
    "tests/check_warehouse.py",
    "tests/pack_warehouse_evidence.py",
    "tests/map_cases.gd",
    "tests/world_cases.gd",
    "tests/run_all.gd",
    "tests/_gen_map_layers.py",
    "docs/warehouse.md",
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
    cover = outcome_verdict(outcomes, "cover")
    cargo = outcome_verdict(outcomes, "cargo")
    spawn = outcome_verdict(outcomes, "spawn")
    camera = outcome_verdict(outcomes, "camera")
    weapon = outcome_verdict(outcomes, "weapon")
    p1 = outcome_verdict(outcomes, "p1")
    p2 = outcome_verdict(outcomes, "p2")
    bot = outcome_verdict(outcomes, "bot")
    zone = outcome_verdict(outcomes, "zone")
    door = outcome_verdict(outcomes, "door")
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
        and cover == "pass"
        and cargo == "pass"
        and spawn == "pass"
        and camera == "pass"
        and weapon == "pass"
        and p1 == "pass"
        and p2 == "pass"
        and bot == "pass"
        and zone == "pass"
        and door == "pass"
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
    cargo_row = outcomes.get("cargo", {}) if isinstance(outcomes.get("cargo"), dict) else {}
    camera_row = outcomes.get("camera", {}) if isinstance(outcomes.get("camera"), dict) else {}
    weapon_row = outcomes.get("weapon", {}) if isinstance(outcomes.get("weapon"), dict) else {}
    catwalk_still = outcomes.get("catwalk_still", {}) if isinstance(outcomes.get("catwalk_still"), dict) else {}
    cover_still = outcomes.get("cover_still", {}) if isinstance(outcomes.get("cover_still"), dict) else {}
    cargo_still = outcomes.get("cargo_still", {}) if isinstance(outcomes.get("cargo_still"), dict) else {}
    office_still = outcomes.get("office_still", {}) if isinstance(outcomes.get("office_still"), dict) else {}
    live_real = str(live_row.get("hud", "")) == "Pallet Annex"
    cover_real = bool(cover_row.get("blocked_before", False)) and int(cover_row.get("breaks", 0)) >= 1
    cargo_real = bool(cargo_row.get("hung_before", False)) and int(cargo_row.get("drops", 0)) >= 1
    p1_hits = p1_row.get("hits") if isinstance(p1_row.get("hits"), dict) else {}
    required_zones = (
        "west_floor",
        "mid_floor",
        "east_floor",
        "office_loft",
        "west_catwalk",
        "mid_catwalk",
        "east_catwalk",
    )
    p1_all = all(bool(p1_hits.get(zid)) for zid in required_zones)
    climb_ok = int(zone_row.get("climb_up_on_ladder", 0) or p1_row.get("climb_up_on_ladder", 0)) >= 8
    office_stand = bool(zone_row.get("office_standing", False) or p1_row.get("office_standing", False))
    east_live = bool(zone_row.get("east_catwalk_live", False) or p1_hits.get("east_catwalk", False))
    catwalk_ok = (
        bool(catwalk_still.get("alive", False))
        and bool(catwalk_still.get("on_floor", False))
        and not bool(catwalk_still.get("lose_visible", True))
        and str(catwalk_still.get("zone", "")) in {"west_catwalk", "mid_catwalk", "east_catwalk"}
    )
    cover_still_ok = (
        bool(cover_still.get("alive", False))
        and bool(cover_still.get("on_floor", False))
        and not bool(cover_still.get("lose_visible", True))
    )
    cargo_still_ok = (
        bool(cargo_still.get("alive", False))
        and bool(cargo_still.get("on_floor", False))
        and not bool(cargo_still.get("lose_visible", True))
    )
    office_still_ok = (
        bool(office_still.get("alive", False))
        and bool(office_still.get("on_floor", False))
        and not bool(office_still.get("lose_visible", True))
        and str(office_still.get("zone", "")) == "office_loft"
    )
    live_reach_ok = (
        p1_all and climb_ok and office_stand and east_live
        and catwalk_ok and cover_still_ok and cargo_still_ok and office_still_ok
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
    events_ok = bool({"ware_name", "ware_zone", "ware_p1", "ware_cover", "ware_cargo"} <= event_kinds)
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    setup_png = pick_still(screens, "setup")
    title_png = pick_still(screens, "title")
    catwalk_png = pick_still(screens, "catwalk")
    cover_png = pick_still(screens, "cover")
    cargo_png = pick_still(screens, "cargo")
    office_png = pick_still(screens, "office")
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in (setup_png, title_png, catwalk_png, cover_png, cargo_png, office_png) if p is not None]
    )
    if None in (setup_png, title_png, catwalk_png, cover_png, cargo_png, office_png):
        stills_ok = False
        still_errors.append("need setup/title/catwalk/cover/cargo/office window stills")
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and live_real
        and cover_real
        and cargo_real
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
        ("run_warehouse.headless.log", Path(args.headless_log)),
        ("run_warehouse.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_warehouse.log", Path(args.check_log)),
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
        "schema": "vault-fighters.vf5-wp3.run.v1",
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
        "seed": 13,
        "map_id": "storage",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "outcomes": {
            "NAME": name_v,
            "COVER": cover,
            "CARGO": cargo,
            "SPAWN": spawn,
            "CAMERA": camera,
            "WEAPON": weapon,
            "P1": p1,
            "P2": p2,
            "BOT": bot,
            "ZONE": zone,
            "DOOR": door,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "map_pallet_observed": False,
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
            "RL-MAP-PALLET",
            "RL-DELTA-MAP-NAMES",
            "RL-MAP-GRAPH",
            "RL-WORLD-DOOR",
            "RL-WORLD-LIFT",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_warehouse.py",
                "python godot/dogfood/superfighters/tests/check_map.py",
                "python godot/dogfood/superfighters/tests/check_rooftop.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_warehouse.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_warehouse.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "ware_headless_exit": args.headless_exit,
            "ware_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "pallet": "assumption",
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

    verdict_md = f"""# VF5-WP3 verdict

{verdict} Pallet Annex warehouse/storage-like arena (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP3)

Verify: cover blocks then breaks, cargo interacts, all spawns reachable,
camera fits, weapon respawn positions safe.

DoD: close-quarters cover and vertical ambushes are functional.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `13`, mode `vs2`, map `storage` display **Pallet Annex**
- NAME={name_v} COVER={cover} CARGO={cargo} SPAWN={spawn} CAMERA={camera} WEAPON={weapon} P1={p1} P2={p2} BOT={bot} ZONE={zone} DOOR={door} LIVE={live} REPLAY={replay}
- LIVE hud={live_row.get("hud")} real={live_real}
- P1 hits={p1_row.get("hits")} P2 hits={p2_row.get("hits")} BOT hits={bot_row.get("hits")}
- live_reach p1_all={p1_all} climb_up_on_ladder={climb_ok} office_standing={office_stand} east_catwalk={east_live}
- catwalk_still={catwalk_still} cover_still={cover_still} cargo_still={cargo_still} office_still={office_still}
- COVER blocked_before={cover_row.get("blocked_before")} breaks={cover_row.get("breaks")} real={cover_real}
- CARGO hung_before={cargo_row.get("hung_before")} drops={cargo_row.get("drops")} real={cargo_real}
- CAMERA covers={camera_row.get("covers_arena")} WEAPON homes={weapon_row.get("homes_ok")}
- events kinds include name/zone/p1/cover/cargo={events_ok} kinds={sorted(event_kinds)}
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `WarehouseCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_warehouse.py
python godot/dogfood/superfighters/tests/check_map.py
python godot/dogfood/superfighters/tests/check_rooftop.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_warehouse.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_warehouse.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Pallet Annex topology stays assumption (`ledger:RL-MAP-PALLET`).
- Jump envelope is product tuning (dx=10 / dy=4); live apex is ~3.4 tiles.
- ZONE / P1 / P2 / BOT / SPAWN are live body positions during apply_frames.
  MapGraph is a helper only. Official routes hold `up` on ladder cells.
- `ledger:RL-NADE-PROP` stays `deferred`.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live `c`/`b` still paint as tiles. This WP placed original breakable
  cover, hanging cargo, door, and lift on Pallet Annex only.
- Machines / water / toxic stay fixture-only. Door/lift are placed here
  because VF5-WP3 asks for them.
- Skyline Relay is unchanged. Display names Police Station / Hazardous
  stay `ledger:RL-DELTA-MAP-NAMES` debt until VF5-WP4+.
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
        ("run_warehouse.headless.log", Path(args.headless_log)),
        ("run_warehouse.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_warehouse.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  NAME={name_v} COVER={cover} CARGO={cargo} SPAWN={spawn} "
        f"CAMERA={camera} WEAPON={weapon} P1={p1} P2={p2} BOT={bot} "
        f"ZONE={zone} DOOR={door} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    print(
        f"  live_reach={live_reach_ok} p1_all={p1_all} climb={climb_ok} "
        f"office_stand={office_stand} east_catwalk={east_live} "
        f"catwalk_ok={catwalk_ok} cover_still_ok={cover_still_ok}"
    )
    for err in still_errors:
        print(f"  still: {err}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
