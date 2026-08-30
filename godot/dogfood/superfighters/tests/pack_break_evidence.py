#!/usr/bin/env python3
"""Assemble VF4-WP2 §18.3 evidence after official break runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF4WP2-20260829-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf4-wp2.break.1"
WP = "VF4-WP2"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/world/prop_break.gd",
    "src/world/prop_body.gd",
    "src/world/world_owner.gd",
    "src/world/world_catalog.gd",
    "src/world/prop_spec.gd",
    "src/world/prop_view.gd",
    "src/world/world_paths.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "data/world/catalog.json",
    "data/world/schema.json",
    "data/sim/schema.json",
    "tests/break_cases.gd",
    "tests/run_break.gd",
    "tests/check_break.py",
    "tests/pack_break_evidence.py",
    "tests/run_all.gd",
    "tests/world_cases.gd",
    "tests/check_world.py",
    "docs/break.md",
    "docs/world.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "assets/art/prop_glass.png",
    "assets/art/prop_glass.png.import",
    "assets/vfx/vfx_break.png",
    "assets/vfx/vfx_break.png.import",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/break/break_cover.json",
    "tests/traces/break/break_melee.json",
    "tests/traces/break/break_shove.json",
    "tests/traces/break/break_throw.json",
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
    data = outcome_verdict(outcomes, "data")
    brk = outcome_verdict(outcomes, "break")
    debris = outcome_verdict(outcomes, "debris")
    passv = outcome_verdict(outcomes, "pass")
    ghost = outcome_verdict(outcomes, "ghost")
    melee = outcome_verdict(outcomes, "melee")
    shove = outcome_verdict(outcomes, "shove")
    throwv = outcome_verdict(outcomes, "throw")
    tactic = outcome_verdict(outcomes, "tactic")
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
        and brk == "pass"
        and debris == "pass"
        and passv == "pass"
        and ghost == "pass"
        and melee == "pass"
        and shove == "pass"
        and throwv == "pass"
        and tactic == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    break_row = outcomes.get("break", {}) if isinstance(outcomes.get("break"), dict) else {}
    debris_row = outcomes.get("debris", {}) if isinstance(outcomes.get("debris"), dict) else {}
    pass_row = outcomes.get("pass", {}) if isinstance(outcomes.get("pass"), dict) else {}
    ghost_row = outcomes.get("ghost", {}) if isinstance(outcomes.get("ghost"), dict) else {}
    tactic_row = outcomes.get("tactic", {}) if isinstance(outcomes.get("tactic"), dict) else {}
    break_real = int(break_row.get("events", 0)) == 1
    debris_real = int(debris_row.get("count", 0)) == 6
    pass_real = bool(pass_row.get("blocked_before")) and float(pass_row.get("p2_hp_after", 99)) < float(
        pass_row.get("p2_hp_mid", 0)
    ) - 0.01
    ghost_real = not bool(ghost_row.get("cover_after", True))
    tactic_real = bool(tactic_row.get("lane_opens"))
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
    events_ok = "break" in event_kinds
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    before_ok = any("before" in png.name for png in screens)
    after_ok = any("after" in png.name for png in screens)
    screen_ok = before_ok and after_ok
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and break_real
        and debris_real
        and pass_real
        and ghost_real
        and tactic_real
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
        "schema": "vault-fighters.vf4-wp2.run.v1",
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
        "map_id": "fx_break_cover",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "DATA": data,
            "BREAK": brk,
            "DEBRIS": debris,
            "PASS": passv,
            "GHOST": ghost,
            "MELEE": melee,
            "SHOVE": shove,
            "THROW": throwv,
            "TACTIC": tactic,
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
            "break_observed": False,
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
            "RL-PROP-BREAK",
            "RL-PROP-DYNAMIC",
            "RL-NADE-PROP",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_break.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_break.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_break.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "break_headless_exit": args.headless_exit,
            "break_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "break": "assumption",
            "throw": "assumption",
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

    verdict_md = f"""# VF4-WP2 verdict

{verdict} breakable glass/wood and throwable/shootable props (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF4-WP2)

Verify: one break event, deterministic debris count, projectile passes only
after break, no collision ghost; screenshot before/after and replay hash.

DoD: destructibility changes tactics, not cosmetic-only animation.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_break_cover`
- DATA={data} BREAK={brk} DEBRIS={debris} PASS={passv} GHOST={ghost} MELEE={melee} SHOVE={shove} THROW={throwv} TACTIC={tactic} LIVE={live} REPLAY={replay}
- BREAK events={break_row.get("events")} real={break_real}
- DEBRIS count={debris_row.get("count")} real={debris_real}
- PASS blocked_before={pass_row.get("blocked_before")} p2_mid={pass_row.get("p2_hp_mid")} p2_after={pass_row.get("p2_hp_after")} real={pass_real}
- GHOST cover_after={ghost_row.get("cover_after")} real={ghost_real}
- TACTIC lane_opens={tactic_row.get("lane_opens")} real={tactic_real}
- events kinds include break={events_ok}
- window screenshot before={before_ok} after={after_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `BreakCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_break.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_break.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_break.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Break / material / debris stay `ledger:RL-PROP-BREAK` assumption.
- Shove / throw stay `ledger:RL-PROP-DYNAMIC` assumption.
- `ledger:RL-NADE-PROP` stays `deferred`. Nades do not destroy props this WP.
- Explosive chain stays unimplemented (`ledger:RL-PROP-EXPL`).
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Live maps still paint `c`/`b` as tiles; this WP does not migrate them.
- Official throw/shove uses `#` floors only. The VF3-WP4 `=` bounce residual is unchanged.
- Original glass/debris art only. Not a VF7 presentation rewrite. Not a Y8 rip.
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
        ("run_break.headless.log", Path(args.headless_log)),
        ("run_break.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_break.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  BREAK={brk} DEBRIS={debris} PASS={passv} GHOST={ghost} "
        f"THROW={throwv} TACTIC={tactic} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
