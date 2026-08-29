#!/usr/bin/env python3
"""Assemble VF3-WP1 §18.3 evidence after official melee runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF3WP1-20260829-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf3-wp1.melee-phases.1"
WP = "VF3-WP1"
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
    "src/sim/combat.gd",
    "src/sim/locomotion.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "src/sim/sim_validator.gd",
    "src/runtime/runtime_checkpoint.gd",
    "src/runtime/runtime_api.gd",
    "data/sim/combat.json",
    "data/sim/locomotion.json",
    "data/sim/schema.json",
    "tests/combat_cases.gd",
    "tests/run_combat.gd",
    "tests/check_combat.py",
    "tests/pack_combat_evidence.py",
    "tests/run_all.gd",
    "docs/combat.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/combat/melee_hit.json",
    "tests/traces/combat/melee_miss.json",
    "tests/traces/combat/melee_behind.json",
    "tests/traces/combat/melee_above.json",
    "tests/traces/combat/melee_below.json",
    "tests/traces/combat/melee_once.json",
    "tests/traces/combat/melee_crouch.json",
    "tests/traces/combat/melee_kick.json",
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
    hit = outcome_verdict(outcomes, "hit")
    miss = outcome_verdict(outcomes, "miss")
    behind = outcome_verdict(outcomes, "behind")
    above = outcome_verdict(outcomes, "above")
    below = outcome_verdict(outcomes, "below")
    once = outcome_verdict(outcomes, "once")
    snap = outcome_verdict(outcomes, "snap")
    pause = outcome_verdict(outcomes, "pause")
    live = outcome_verdict(outcomes, "live")
    replay = outcome_verdict(outcomes, "replay")
    phases = outcome_verdict(outcomes, "phases")
    reach = outcome_verdict(outcomes, "reach")
    ff = outcome_verdict(outcomes, "ff")
    hitstop = outcome_verdict(outcomes, "hitstop")
    crouch = outcome_verdict(outcomes, "crouch")
    kick = outcome_verdict(outcomes, "kick")
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
        hit == "pass"
        and miss == "pass"
        and behind == "pass"
        and above == "pass"
        and below == "pass"
        and once == "pass"
        and snap == "pass"
        and pause == "pass"
        and live == "pass"
        and replay == "match"
        and phases == "pass"
        and reach == "pass"
        and ff == "pass"
        and hitstop == "pass"
        and crouch == "pass"
        and kick == "pass"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    hit_row = outcomes.get("hit", {}) if isinstance(outcomes.get("hit"), dict) else {}
    hp0 = float(hit_row.get("hp0", 0.0) or 0.0)
    hp1 = float(hit_row.get("hp1", 0.0) or 0.0)
    damage = float(hit_row.get("damage", hp0 - hp1) or 0.0)
    expected = float(hit_row.get("expected", 10.0) or 10.0)
    press_phase = str(hit_row.get("press_phase", ""))
    hit_real = abs(damage - expected) <= 0.01 and press_phase == "startup" and abs(float(hit_row.get("startup_hp", hp0)) - hp0) <= 0.01
    miss_real = True
    for key, kind in (("miss", "reach"), ("behind", "behind"), ("above", "above"), ("below", "below")):
        row = outcomes.get(key, {}) if isinstance(outcomes.get(key), dict) else {}
        if abs(float(row.get("hp1", 1.0) or 1.0) - float(row.get("hp0", 0.0) or 0.0)) > 0.01:
            miss_real = False
        if str(row.get("miss_kind", "")) != kind:
            miss_real = False
        if int(row.get("hit_events", 1)) != 0:
            miss_real = False
    once_row = outcomes.get("once", {}) if isinstance(outcomes.get("once"), dict) else {}
    once_real = int(once_row.get("hit_events", 0) or 0) == 1 and abs(float(once_row.get("damage", 0.0) or 0.0) - expected) <= 0.01
    pause_row = outcomes.get("pause", {}) if isinstance(outcomes.get("pause"), dict) else {}
    pause_real = (
        int(pause_row.get("tick0", -1)) == int(pause_row.get("tick1", -2))
        and str(pause_row.get("phase0", "")) == str(pause_row.get("phase1", "x"))
        and abs(float(pause_row.get("hp_paused", 1.0) or 1.0) - float(pause_row.get("hp0", 0.0) or 0.0)) <= 0.01
        and float(pause_row.get("hp_end", 0.0) or 0.0) < float(pause_row.get("hp0", 0.0) or 0.0) - 0.01
    )
    reach_row = outcomes.get("reach", {}) if isinstance(outcomes.get("reach"), dict) else {}
    reach_real = bool(reach_row.get("fists_miss", False)) and bool(reach_row.get("pipe_hit", False))
    ff_row = outcomes.get("ff", {}) if isinstance(outcomes.get("ff"), dict) else {}
    ff_real = bool(ff_row.get("vs1_block", False)) and bool(ff_row.get("vs2_hit", False))
    hitstop_row = outcomes.get("hitstop", {}) if isinstance(outcomes.get("hitstop"), dict) else {}
    hitstop_real = int(hitstop_row.get("hitstop_left", 0) or 0) > 0 and int(hitstop_row.get("tick1", 0) or 0) == int(hitstop_row.get("tick0", -1) or -1) + 1
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
    events_ok = {"startup", "active", "hit"}.issubset(event_kinds)
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and hit_real
        and miss_real
        and once_real
        and pause_real
        and reach_real
        and ff_real
        and hitstop_real
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
        "schema": "vault-fighters.vf3-wp1.run.v1",
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
            "HIT": hit,
            "MISS": miss,
            "BEHIND": behind,
            "ABOVE": above,
            "BELOW": below,
            "ONCE": once,
            "SNAP": snap,
            "PAUSE": pause,
            "LIVE": live,
            "REPLAY": replay,
            "PHASES": phases,
            "REACH": reach,
            "FF": ff,
            "HITSTOP": hitstop,
            "CROUCH": crouch,
            "KICK": kick,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "hold_to_aim_observed": False,
            "phases_observed": False,
            "hitbox_observed": False,
            "ff_observed": False,
            "hitstop_observed": False,
            "kick_observed": False,
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
            "RL-HIT-PHASES",
            "RL-HIT-BOX",
            "RL-HIT-FF",
            "RL-HIT-HITSTOP",
            "RL-MOVE-JUMP-KICK",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_combat.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_combat.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_combat.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "melee_headless_exit": args.headless_exit,
            "melee_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "hold_to_aim": "assumption",
            "phases": "assumption",
            "hitbox": "assumption",
            "ff": "assumption",
            "hitstop": "assumption",
            "kick": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF3-WP1 verdict

{verdict} melee phase / hitbox evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP1)

Verify: frame-by-frame trace cho miss/hit/behind/above/below; one hit per
active window; damage/knockback snapshot; pause trong attack an toàn.

DoD: melee không còn là distance check đơn giản không có phase.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_melee_close`
- HIT={hit} MISS={miss} BEHIND={behind} ABOVE={above} BELOW={below} ONCE={once} SNAP={snap} PAUSE={pause} LIVE={live} REPLAY={replay} PHASES={phases} REACH={reach} FF={ff} HITSTOP={hitstop} CROUCH={crouch} KICK={kick}
- HIT hp0={hp0} hp1={hp1} damage={damage} expected={expected} press_phase={press_phase} real={hit_real}
- MISS geometry kinds + unchanged HP={miss_real}
- ONCE hit_events={once_row.get("hit_events")} damage={once_row.get("damage")} real={once_real}
- PAUSE tick {pause_row.get("tick0")}->{pause_row.get("tick1")} phase {pause_row.get("phase0")} real={pause_real}
- REACH fists_miss={reach_row.get("fists_miss")} pipe_hit={reach_row.get("pipe_hit")}
- FF vs1_block={ff_row.get("vs1_block")} vs2_hit={ff_row.get("vs2_hit")}
- HITSTOP left={hitstop_row.get("hitstop_left")} clock {hitstop_row.get("tick0")}->{hitstop_row.get("tick1")}
- events kinds include startup/active/hit={events_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `CombatCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_combat.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_combat.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_combat.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Phases stay `ledger:RL-HIT-PHASES` assumption, not observed.
- Boxes stay `ledger:RL-HIT-BOX` assumption, not observed.
- Friendly-fire stays `ledger:RL-HIT-FF` assumption, not observed.
- Hitstop stays `ledger:RL-HIT-HITSTOP` assumption, presentation only.
- Kick stays `ledger:RL-MOVE-JUMP-KICK` assumption, not observed.
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
        ("run_combat.headless.log", Path(args.headless_log)),
        ("run_combat.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_combat.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  HIT={hit} MISS={miss} BEHIND={behind} ABOVE={above} BELOW={below} "
        f"ONCE={once} SNAP={snap} PAUSE={pause} LIVE={live} REPLAY={replay} "
        f"PHASES={phases} REACH={reach} FF={ff} HITSTOP={hitstop} "
        f"CROUCH={crouch} KICK={kick} APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
