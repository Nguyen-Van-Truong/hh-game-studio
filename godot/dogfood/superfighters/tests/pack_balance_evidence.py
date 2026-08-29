#!/usr/bin/env python3
"""Assemble VF3-WP6 §18.3 evidence after official balance runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF3WP6-20260829-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf3-wp6.balance.3"
WP = "VF3-WP6"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/sim/balance.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/sim/aim.gd",
    "src/sim/combat.gd",
    "src/sim/explosive.gd",
    "src/sim/locomotion.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "data/sim/balance.json",
    "data/sim/schema.json",
    "data/sim/locomotion.json",
    "tests/balance_cases.gd",
    "tests/run_balance.gd",
    "tests/check_balance.py",
    "tests/pack_balance_evidence.py",
    "tests/run_all.gd",
    "docs/balance.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/balance/balance_melee.json",
    "tests/traces/balance/balance_high.json",
    "tests/traces/balance/balance_pit.json",
    "tests/traces/balance/balance_chain.json",
    "tests/traces/balance/balance_ff.json",
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
    batch = outcome_verdict(outcomes, "batch")
    dist = outcome_verdict(outcomes, "dist")
    dom = outcome_verdict(outcomes, "dom")
    melee = outcome_verdict(outcomes, "melee")
    high = outcome_verdict(outcomes, "high")
    overcap = outcome_verdict(outcomes, "overcap")
    pit = outcome_verdict(outcomes, "pit")
    chain = outcome_verdict(outcomes, "chain")
    ff = outcome_verdict(outcomes, "ff")
    stamina = outcome_verdict(outcomes, "stamina")
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
        and batch == "pass"
        and dist == "pass"
        and dom == "pass"
        and melee == "pass"
        and high == "pass"
        and overcap == "pass"
        and pit == "pass"
        and chain == "pass"
        and ff == "pass"
        and stamina == "pass"
        and data == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    batch_row = outcomes.get("batch", {}) if isinstance(outcomes.get("batch"), dict) else {}
    batch_real = int(batch_row.get("count", 0)) >= 1000 and bool(batch_row.get("replay"))
    dist_row = outcomes.get("dist", {}) if isinstance(outcomes.get("dist"), dict) else {}
    dist_real = int(dist_row.get("n", 0)) >= 1000
    dom_row = outcomes.get("dom", {}) if isinstance(outcomes.get("dom"), dict) else {}
    dom_rate = float(dom_row.get("win_rate_max", 1.0) or 1.0)
    dom_real = (
        int(dom_row.get("distinct_winners", 0)) >= 2
        and int(dom_row.get("distinct_contexts", 0)) >= 3
        and dom_rate < 0.55
        and not bool(dom_row.get("hardcoded_winners", True))
        and "formula" in str(dom_row.get("method", ""))
        and int(dom_row.get("live_weapon_count", 0)) >= 2
    )
    melee_row = outcomes.get("melee", {}) if isinstance(outcomes.get("melee"), dict) else {}
    melee_real = float(melee_row.get("damage", 0.0) or 0.0) > 0.05
    high_row = outcomes.get("high", {}) if isinstance(outcomes.get("high"), dict) else {}
    high_real = float(high_row.get("damage", 0.0) or 0.0) > 0.05
    overcap_row = outcomes.get("overcap", {}) if isinstance(outcomes.get("overcap"), dict) else {}
    overcap_real = (
        str(overcap_row.get("path", "")) == "bullet"
        and float(overcap_row.get("incoming_raw", 0.0) or 0.0) > 56.0
        and float(overcap_row.get("applied", 0.0) or 0.0) > 0.05
        and float(overcap_row.get("applied", 99.0) or 99.0) <= 56.001
        and float(overcap_row.get("spawn_raw", 0.0) or 0.0) > 56.0
        and bool(overcap_row.get("identity_clamp_would_fail", False))
        and bool(overcap_row.get("alive", False))
    )
    chain_row = outcomes.get("chain", {}) if isinstance(outcomes.get("chain"), dict) else {}
    chain_real = (
        int(chain_row.get("explosions", 0)) >= 2
        and float(chain_row.get("damage", 0.0) or 0.0) > 0.05
        and bool(chain_row.get("once_per_nade", False))
    )
    pit_row = outcomes.get("pit", {}) if isinstance(outcomes.get("pit"), dict) else {}
    pit_real = bool(pit_row.get("dead")) and str(pit_row.get("cause")) == "pit"
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
    events_ok = "hit" in event_kinds or "explosion" in event_kinds or "bullet" in event_kinds
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    screen_ok = len(screens) >= 1
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and batch_real
        and dist_real
        and dom_real
        and melee_real
        and high_real
        and overcap_real
        and chain_real
        and pit_real
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
        "distribution": {
            "n": dist_row.get("n"),
            "mean": dist_row.get("mean"),
            "p50": dist_row.get("p50"),
            "p95": dist_row.get("p95"),
            "max": dist_row.get("max"),
        },
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf3-wp6.run.v1",
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
        "map_id": "fx_balance_melee",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "SCHEMA": schema,
            "BATCH": batch,
            "DIST": dist,
            "DOM": dom,
            "MELEE": melee,
            "HIGH": high,
            "OVERCAP": overcap,
            "PIT": pit,
            "CHAIN": chain,
            "FF": ff,
            "STAMINA": stamina,
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
            "chaos_observed": False,
            "crit_observed": False,
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
            "RL-MODE-CHAOS",
            "RL-BAL-CRIT",
            "RL-BAL-KNOCK-JITTER",
            "RL-BAL-SPREAD-RNG",
            "RL-BAL-CAP",
            "RL-BAL-STAMINA",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_balance.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_balance.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_balance.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "balance_headless_exit": args.headless_exit,
            "balance_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "chaos": "assumption",
            "crit": "assumption",
            "hold_to_aim": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF3-WP6 verdict

{verdict} critical/chaos tuning and combat balance harness (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP6)

Verify: 1000 seeded scenarios no NaN/infinite damage; distribution report,
no weapon always dominates; all scenarios replayable; no copied stat table.

DoD: combat feels chaotic yet bounded, with documented tuning rationale.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_balance_melee`
- SCHEMA={schema} BATCH={batch} DIST={dist} DOM={dom} MELEE={melee} HIGH={high} OVERCAP={overcap} PIT={pit} CHAIN={chain} FF={ff} STAMINA={stamina} DATA={data} LIVE={live} REPLAY={replay}
- BATCH count={batch_row.get("count")} replay={batch_row.get("replay")} real={batch_real}
- DIST n={dist_row.get("n")} mean={dist_row.get("mean")} p95={dist_row.get("p95")} real={dist_real}
- DOM leader={dom_row.get("win_leader")} rate={dom_row.get("win_rate_max")} winners={dom_row.get("distinct_winners")} contexts={dom_row.get("distinct_contexts")} live={dom_row.get("live_weapon_count")} method={dom_row.get("method")} real={dom_real}
- MELEE damage={melee_row.get("damage")} real={melee_real}
- HIGH damage={high_row.get("damage")} real={high_real}
- OVERCAP path={overcap_row.get("path")} spawn={overcap_row.get("spawn_raw")} raw={overcap_row.get("incoming_raw")} applied={overcap_row.get("applied")} real={overcap_real}
- CHAIN explosions={chain_row.get("explosions")} damage={chain_row.get("damage")} once={chain_row.get("once_per_nade")} real={chain_real}
- PIT dead={pit_row.get("dead")} cause={pit_row.get("cause")} real={pit_real}
- events kinds include hit/explosion/bullet={events_ok}
- window screenshot={screen_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `BalanceCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_balance.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_balance.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Chaos / crit / knock jitter / spread jitter stay assumption
  (`ledger:RL-MODE-CHAOS`, `ledger:RL-BAL-CRIT`,
  `ledger:RL-BAL-KNOCK-JITTER`, `ledger:RL-BAL-SPREAD-RNG`).
  Developer note “IT AIN'T FAIR” is designer intent, not an RNG spec.
- Damage caps stay `ledger:RL-BAL-CAP` assumption.
  Hit cap is per-hit (`clamp_hit`); tick cap is per-tick (`tick_room`).
  OVERCAP is a fire-path `overcap_rifle` shot, not `take_damage(999)`.
- 1000-batch is formula rolls, not 1000 live matches.
  Published bar: `win_rate_max < 0.55` and `>=3` distinct `context_best`.
- Stamina numbers stay `ledger:RL-BAL-STAMINA` assumption; same VF2-WP3
  drain/recover so official sprint hashes do not drift.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- All RL-ITEM-* / RL-NADE-* / RL-FIRE-* rows stay assumption.
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
        ("run_balance.headless.log", Path(args.headless_log)),
        ("run_balance.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_balance.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  SCHEMA={schema} BATCH={batch} DIST={dist} DOM={dom} "
        f"MELEE={melee} PIT={pit} CHAIN={chain} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
