#!/usr/bin/env python3
"""Assemble VF3-WP3 §18.3 evidence after official aim/fire runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF3WP3-20260829-ASIA-SAIGON-01"
COMMAND_ID = "cmd.vf3-wp3.aim-fire.1"
WP = "VF3-WP3"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/fighter.gd",
    "src/game_session.gd",
    "src/bullet.gd",
    "src/weapon_defs.gd",
    "src/maps.gd",
    "src/sim/aim.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "src/runtime/runtime_checkpoint.gd",
    "data/sim/aim.json",
    "data/sim/schema.json",
    "tests/aim_cases.gd",
    "tests/run_aim.gd",
    "tests/check_aim.py",
    "tests/pack_aim_evidence.py",
    "tests/run_all.gd",
    "docs/aim.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/aim/aim_hold.json",
    "tests/traces/aim/aim_up.json",
    "tests/traces/aim/aim_down.json",
    "tests/traces/aim/fire_semi.json",
    "tests/traces/aim/fire_edges.json",
    "tests/traces/aim/fire_wall.json",
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
    hold = outcome_verdict(outcomes, "hold")
    dirs = outcome_verdict(outcomes, "dirs")
    semi = outcome_verdict(outcomes, "semi")
    auto = outcome_verdict(outcomes, "auto")
    ammo = outcome_verdict(outcomes, "ammo")
    muzzle = outcome_verdict(outcomes, "muzzle")
    recoil = outcome_verdict(outcomes, "recoil")
    data = outcome_verdict(outcomes, "data")
    sweep = outcome_verdict(outcomes, "sweep")
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
        hold == "pass"
        and dirs == "pass"
        and semi == "pass"
        and auto == "pass"
        and ammo == "pass"
        and muzzle == "pass"
        and recoil == "pass"
        and data == "pass"
        and sweep == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    hold_row = outcomes.get("hold", {}) if isinstance(outcomes.get("hold"), dict) else {}
    hold_real = bool(hold_row.get("aiming", False)) and int(hold_row.get("spawns", 1)) == 0
    semi_row = outcomes.get("semi", {}) if isinstance(outcomes.get("semi"), dict) else {}
    semi_real = int(semi_row.get("during", 1)) == 0 and int(semi_row.get("after", 0)) == 1
    ammo_row = outcomes.get("ammo", {}) if isinstance(outcomes.get("ammo"), dict) else {}
    ammo_real = int(ammo_row.get("shots", 1)) == 0 and int(ammo_row.get("spawns", 1)) == 0
    sweep_row = outcomes.get("sweep", {}) if isinstance(outcomes.get("sweep"), dict) else {}
    sweep_real = int(sweep_row.get("past_wall", 1)) == 0 and abs(
        float(sweep_row.get("hp0", 0.0)) - float(sweep_row.get("hp1", 1.0))
    ) <= 0.01
    muzzle_row = outcomes.get("muzzle", {}) if isinstance(outcomes.get("muzzle"), dict) else {}
    muzzle_real = float(muzzle_row.get("dir_y", 0.0)) < -0.4
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
    events_ok = "bullet" in event_kinds
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and hold_real
        and semi_real
        and ammo_real
        and sweep_real
        and muzzle_real
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
        "schema": "vault-fighters.vf3-wp3.run.v1",
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
        "map_id": "fx_aim_open",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "HOLD": hold,
            "DIRS": dirs,
            "SEMI": semi,
            "AUTO": auto,
            "AMMO": ammo,
            "MUZZLE": muzzle,
            "RECOIL": recoil,
            "DATA": data,
            "SWEEP": sweep,
            "LIVE": live,
            "REPLAY": replay,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "hold_aim_observed": False,
            "aim_dirs_observed": False,
            "semi_observed": False,
            "auto_observed": False,
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
            "RL-CTRL-HOLD-AIM",
            "RL-AIM-DIRS",
            "RL-FIRE-SEMI",
            "RL-FIRE-AUTO",
            "RL-FIRE-AMMO",
            "RL-FIRE-MUZZLE",
            "RL-FIRE-RECOIL",
            "RL-FIRE-BALLISTIC",
            "RL-FIRE-SWEEP",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_aim.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_aim.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_aim.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "aim_headless_exit": args.headless_exit,
            "aim_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "hold_to_aim": "assumption",
            "aim_dirs": "assumption",
            "semi": "assumption",
            "auto": "assumption",
            "ballistic": "assumption",
            "sweep": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF3-WP3 verdict

{verdict} aim model and fire/release evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP3)

Verify: pressed/held/released trace; 0 ammo không bắn; projectile collision
continuous (không xuyên vật thể ở tốc độ cao); aim pose/hit direction đúng.

DoD: pistol/SMG/shotgun khác nhau bằng data, không copy stat mù quáng.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_aim_open`
- HOLD={hold} DIRS={dirs} SEMI={semi} AUTO={auto} AMMO={ammo} MUZZLE={muzzle} RECOIL={recoil} DATA={data} SWEEP={sweep} LIVE={live} REPLAY={replay}
- HOLD aiming={hold_row.get("aiming")} spawns={hold_row.get("spawns")} real={hold_real}
- SEMI during={semi_row.get("during")} after={semi_row.get("after")} real={semi_real}
- AMMO shots={ammo_row.get("shots")} spawns={ammo_row.get("spawns")} real={ammo_real}
- MUZZLE dir_y={muzzle_row.get("dir_y")} real={muzzle_real}
- SWEEP past_wall={sweep_row.get("past_wall")} hp0={sweep_row.get("hp0")} hp1={sweep_row.get("hp1")} real={sweep_real}
- events include bullet={events_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `AimCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_aim.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_aim.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_aim.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
- Aim dirs stay `ledger:RL-AIM-DIRS` assumption, not observed.
- Semi release stays `ledger:RL-FIRE-SEMI` assumption, not observed.
- Auto cadence stays `ledger:RL-FIRE-AUTO` assumption, not observed.
- Empty ammo stays `ledger:RL-FIRE-AMMO` assumption, not observed.
- Muzzle stays `ledger:RL-FIRE-MUZZLE` assumption, not observed.
- Recoil/spread stay `ledger:RL-FIRE-RECOIL` assumption, not observed.
- Guns are ballistic, not hitscan (`ledger:RL-FIRE-BALLISTIC` assumption).
- Swept collision stays `ledger:RL-FIRE-SWEEP` assumption, not observed.
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
        ("run_aim.headless.log", Path(args.headless_log)),
        ("run_aim.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_aim.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  HOLD={hold} DIRS={dirs} SEMI={semi} AUTO={auto} AMMO={ammo} "
        f"MUZZLE={muzzle} RECOIL={recoil} DATA={data} SWEEP={sweep} "
        f"LIVE={live} REPLAY={replay} APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
