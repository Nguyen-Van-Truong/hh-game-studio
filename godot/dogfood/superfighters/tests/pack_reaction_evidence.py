#!/usr/bin/env python3
"""Assemble VF3-WP2 §18.3 evidence after official reaction runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF3WP2-20260829-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf3-wp2.knock-disarm.1"
WP = "VF3-WP2"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/fighter.gd",
    "src/game_session.gd",
    "src/pickup.gd",
    "src/maps.gd",
    "src/sim/combat.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "src/runtime/runtime_checkpoint.gd",
    "data/sim/combat.json",
    "data/sim/schema.json",
    "tests/reaction_cases.gd",
    "tests/run_reaction.gd",
    "tests/check_reaction.py",
    "tests/pack_reaction_evidence.py",
    "tests/run_all.gd",
    "docs/reaction.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/reaction/reaction_knock.json",
    "tests/traces/reaction/reaction_down.json",
    "tests/traces/reaction/reaction_invuln.json",
    "tests/traces/reaction/reaction_disarm.json",
    "tests/traces/reaction/reaction_drop.json",
    "tests/traces/reaction/reaction_chain.json",
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
    damage = outcome_verdict(outcomes, "damage")
    knock = outcome_verdict(outcomes, "knock")
    air = outcome_verdict(outcomes, "air")
    down = outcome_verdict(outcomes, "down")
    getup = outcome_verdict(outcomes, "getup")
    invuln = outcome_verdict(outcomes, "invuln")
    chain = outcome_verdict(outcomes, "chain")
    disarm = outcome_verdict(outcomes, "disarm")
    drop = outcome_verdict(outcomes, "drop")
    death = outcome_verdict(outcomes, "death")
    events = outcome_verdict(outcomes, "events")
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
        damage == "pass"
        and knock == "pass"
        and air == "pass"
        and down == "pass"
        and getup == "pass"
        and invuln == "pass"
        and chain == "pass"
        and disarm == "pass"
        and drop == "pass"
        and death == "pass"
        and events == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    dmg_row = outcomes.get("damage", {}) if isinstance(outcomes.get("damage"), dict) else {}
    hp0 = float(dmg_row.get("hp0", 0.0) or 0.0)
    hp1 = float(dmg_row.get("hp1", 0.0) or 0.0)
    dmg = float(dmg_row.get("damage", hp0 - hp1) or 0.0)
    expected = float(dmg_row.get("expected", 10.0) or 10.0)
    damage_real = abs(dmg - expected) <= 0.01
    knock_row = outcomes.get("knock", {}) if isinstance(outcomes.get("knock"), dict) else {}
    knock_real = float(knock_row.get("vx1", 0.0) or 0.0) > float(knock_row.get("vx0", 0.0) or 0.0) + 8.0
    inv_row = outcomes.get("invuln", {}) if isinstance(outcomes.get("invuln"), dict) else {}
    inv_real = (
        int(inv_row.get("armed_ticks", 0) or 0) == int(inv_row.get("expected_ticks", -1) or -1)
        and bool(inv_row.get("blocked_inside", False))
        and bool(inv_row.get("expired", False))
        and bool(inv_row.get("after_damaged", False))
    )
    disarm_row = outcomes.get("disarm", {}) if isinstance(outcomes.get("disarm"), dict) else {}
    disarm_real = (
        bool(disarm_row.get("held_before", False))
        and not bool(disarm_row.get("holds_after", True))
        and int(disarm_row.get("pick1", 0) or 0) == int(disarm_row.get("pick0", 0) or 0) + 1
    )
    drop_row = outcomes.get("drop", {}) if isinstance(outcomes.get("drop"), dict) else {}
    drop_real = (
        int(drop_row.get("after_hit", 0) or 0) == 1
        and int(drop_row.get("persist", 0) or 0) == 1
        and int(drop_row.get("uid0", 0) or 0) == int(drop_row.get("uid1", -1) or -1)
        and int(drop_row.get("after_pick", 1)) == 0
        and bool(drop_row.get("picked", False))
    )
    death_row = outcomes.get("death", {}) if isinstance(outcomes.get("death"), dict) else {}
    death_real = bool(death_row.get("dead", False)) and str(death_row.get("cause", "")) == "damage"
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
    events_ok = {"knockdown_start", "getup_end", "invuln_start", "disarm", "item_drop"}.issubset(event_kinds)
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and damage_real
        and knock_real
        and inv_real
        and disarm_real
        and drop_real
        and death_real
        and events_ok
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
        "schema": "vault-fighters.vf3-wp2.run.v1",
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
        "map_id": "fx_melee_close",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "DAMAGE": damage,
            "KNOCK": knock,
            "AIR": air,
            "DOWN": down,
            "GETUP": getup,
            "INVULN": invuln,
            "CHAIN": chain,
            "DISARM": disarm,
            "DROP": drop,
            "DEATH": death,
            "EVENTS": events,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "knock_observed": False,
            "down_observed": False,
            "invuln_observed": False,
            "disarm_observed": False,
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
            "RL-HIT-KNOCK",
            "RL-HIT-DOWN",
            "RL-HIT-INVULN",
            "RL-HIT-DISARM",
            "RL-HIT-PHASES",
            "RL-HIT-BOX",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_reaction.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_reaction.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_reaction.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "react_headless_exit": args.headless_exit,
            "react_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "knock": "assumption",
            "down": "assumption",
            "invuln": "assumption",
            "disarm": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF3-WP2 verdict

{verdict} knockback / knockdown / invuln / disarm evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP2)

Verify: damage/knockdown/disarm traces; invulnerability exact ticks;
dropped item không mất hoặc nhân đôi; death cause chỉ từ event hợp lệ.

DoD: các trạng thái có entry/exit event và replay hash.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_melee_close`
- DAMAGE={damage} KNOCK={knock} AIR={air} DOWN={down} GETUP={getup} INVULN={invuln} CHAIN={chain} DISARM={disarm} DROP={drop} DEATH={death} EVENTS={events} LIVE={live} REPLAY={replay}
- DAMAGE hp0={hp0} hp1={hp1} damage={dmg} expected={expected} real={damage_real}
- INVULN armed={inv_row.get("armed_ticks")} expected={inv_row.get("expected_ticks")} blocked={inv_row.get("blocked_inside")} expired={inv_row.get("expired")} real={inv_real}
- DISARM held_before={disarm_row.get("held_before")} holds_after={disarm_row.get("holds_after")} pick {disarm_row.get("pick0")}->{disarm_row.get("pick1")} real={disarm_real}
- DROP persist uid={drop_row.get("uid0")} after_pick={drop_row.get("after_pick")} real={drop_real}
- DEATH cause={death_row.get("cause")} dead={death_row.get("dead")} real={death_real}
- events include knockdown_start/getup_end/invuln_start/disarm/item_drop={events_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `ReactionCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_reaction.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_reaction.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Knockback stays `ledger:RL-HIT-KNOCK` assumption, not observed.
- Knockdown/getup stay `ledger:RL-HIT-DOWN` assumption, not observed.
- Hit invuln stays `ledger:RL-HIT-INVULN` assumption, not observed.
- Punch disarm stays `ledger:RL-HIT-DISARM` assumption, not observed.
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
        ("run_reaction.headless.log", Path(args.headless_log)),
        ("run_reaction.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_reaction.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  DAMAGE={damage} KNOCK={knock} AIR={air} DOWN={down} GETUP={getup} "
        f"INVULN={invuln} CHAIN={chain} DISARM={disarm} DROP={drop} DEATH={death} "
        f"EVENTS={events} LIVE={live} REPLAY={replay} APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
