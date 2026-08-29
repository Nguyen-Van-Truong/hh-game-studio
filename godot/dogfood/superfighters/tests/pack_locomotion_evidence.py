#!/usr/bin/env python3
"""Assemble VF2-WP2 §18.3 evidence after official locomotion runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF2WP2-20260829-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf2-wp2.locomotion-evidence-gate.1"
WP = "VF2-WP2"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/fighter.gd",
    "src/game_session.gd",
    "src/maps.gd",
    "src/sim/locomotion.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_replay.gd",
    "src/sim/sim_snapshot.gd",
    "data/sim/locomotion.json",
    "tests/locomotion_cases.gd",
    "tests/run_locomotion.gd",
    "tests/check_locomotion.py",
    "tests/run_all.gd",
    "tests/pack_locomotion_evidence.py",
    "docs/locomotion.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/locomotion/walk_accel_friction.json",
    "tests/traces/locomotion/crouch_shape.json",
    "tests/traces/locomotion/pit_fall.json",
    "tests/traces/locomotion/no_tunnel_solid.json",
    "tests/traces/locomotion/no_tunnel_oneway.json",
    "tests/traces/locomotion/variable_jump.json",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--review", required=True)
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
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "screens").mkdir(parents=True, exist_ok=True)
    review.mkdir(parents=True, exist_ok=True)

    outcomes = load_json(evidence / "outcomes.json")
    partial = load_json(evidence / "run_partial.json")
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
    hash2 = str(outcomes.get("hash2", {}).get("verdict", "unproven"))
    tunnel = str(outcomes.get("tunnel", {}).get("verdict", "unproven"))
    camera = str(outcomes.get("camera", {}).get("verdict", "unproven"))
    succeeded = int(apply_info.get("succeeded", 0))
    attempted = int(apply_info.get("attempted", 0))
    exits_ok = (
        args.check_exit == 0
        and args.headless_exit == 0
        and args.window_exit == 0
        and args.run_all_exit == 0
        and args.leftover == 0
    )
    outcomes_ok = hash2 == "match" and tunnel == "none" and camera == "arena_fit" and succeeded > 0
    verdict = "PASS" if exits_ok and outcomes_ok else "FAIL"

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

    run = {
        "schema": "vault-fighters.vf2-wp2.run.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "timezone": "Asia/Saigon",
        "recorded_at": now_saigon(),
        "started_at": partial.get("started_at", ""),
        "ended_at": partial.get("ended_at", ""),
        "base_head": args.base_head,
        "godot": "4.7.1.stable.official.a13da4feb",
        "godot_exe_sha256": godot_hash,
        "os": platform.platform(),
        "seed": 1,
        "map_id": "police",
        "mode": "vs2",
        "camera_map": "rooftops",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "HASH2": hash2,
            "TUNNEL": tunnel,
            "CAMERA": camera,
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "hold_to_aim_observed": False,
            "roll_dive_observed": False,
            "in_game_y8_play": False,
            "game_package_fetched": False,
            "plan_checkbox_ticked": False,
            "implementer_commit": False,
            "r9_wp4": False,
            "g6": False,
            "gx": False,
            "progress_60_of_60": False,
            "correction_gate_cleared": False,
        },
        "ledger": [
            "RL-MOVE-LOCO-BASE",
            "RL-MOVE-JUMP-CROUCH",
            "RL-MOVE-ROLL-DIVE",
            "RL-CAM-ARENA",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_locomotion.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_locomotion.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_locomotion.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "locomotion_headless_exit": args.headless_exit,
            "locomotion_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": "headless",
            "display_window": "Windows",
            "hold_to_aim": "assumption",
            "roll": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF2-WP2 correction-gate verdict

{verdict} locomotion baseline evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. `CORRECTION_GATE_VF2_WP2` **not** cleared by implementer.

## DoD / Verify (quoted from 29-8 VF2-WP2)

Verify: 60-Hz trace + real window; no tunneling through solid/one-way surface;
snapshot positions within explicit epsilon across runs.

Correction gate: unique `run_id`; evidence layout §18.3; `HASH2` / `TUNNEL` /
`CAMERA` from structured outcomes; `USED_APPLY_FRAMES` counts successful
applies; independent viewport camera postcondition.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `1`, mode `vs2`, map `police`, camera map `rooftops`
- `HASH2={hash2}` `TUNNEL={tunnel}` `CAMERA={camera}`
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`

## Reproduction

```
python godot/dogfood/superfighters/tests/check_locomotion.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_locomotion.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim assumption. Roll/dive unavailable.
- Camera `arena_fit` assumption; independent viewport covers rooftops.
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
    ):
        src = evidence / name
        if src.is_file():
            (review / name).write_bytes(src.read_bytes())
    screens_src = evidence / "screens"
    screens_dst = review / "screens"
    if screens_src.is_dir():
        screens_dst.mkdir(parents=True, exist_ok=True)
        for png in screens_src.glob("*.png"):
            (screens_dst / png.name).write_bytes(png.read_bytes())
    for label, src in (
        ("run_locomotion.headless.log", Path(args.headless_log)),
        ("run_locomotion.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_locomotion.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(f"  HASH2={hash2} TUNNEL={tunnel} CAMERA={camera} APPLY={succeeded}/{attempted}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
