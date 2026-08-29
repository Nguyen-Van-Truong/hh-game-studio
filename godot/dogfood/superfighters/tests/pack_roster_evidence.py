#!/usr/bin/env python3
"""Assemble VF3-WP5 §18.3 evidence after official roster runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN_ID = "VF3WP5-20260829-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf3-wp5.roster.2"
WP = "VF3-WP5"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/data/weapons/roster.gd",
    "src/data/weapons/inventory.gd",
    "src/weapon_defs.gd",
    "src/fighter.gd",
    "src/game_session.gd",
    "src/hud.gd",
    "src/grenade.gd",
    "src/maps.gd",
    "src/sim/aim.gd",
    "src/sim/explosive.gd",
    "src/sim/sim_constants.gd",
    "src/sim/sim_snapshot.gd",
    "src/runtime/runtime_checkpoint.gd",
    "data/weapons/roster.json",
    "data/weapons/schema.json",
    "data/sim/aim.json",
    "data/sim/combat.json",
    "data/sim/explosive.json",
    "data/sim/schema.json",
    "tests/roster_cases.gd",
    "tests/run_roster.gd",
    "tests/check_roster.py",
    "tests/pack_roster_evidence.py",
    "tests/run_all.gd",
    "docs/roster.md",
    "docs/reference-ledger.md",
    "project.godot",
)

TRACE_FILES = (
    "tests/traces/roster/roster_idle.json",
    "tests/traces/roster/roster_keep.json",
    "tests/traces/roster/roster_melee.json",
    "tests/traces/roster/roster_throw.json",
)

REQUIRED_LIFECYCLE = (
    "fists",
    "pipe",
    "knife",
    "baton",
    "pistol",
    "uzi",
    "shotgun",
    "rifle",
    "launcher",
    "grenade",
    "cinder",
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
    spawn = outcome_verdict(outcomes, "spawn")
    equip = outcome_verdict(outcomes, "equip")
    attack = outcome_verdict(outcomes, "attack")
    drop = outcome_verdict(outcomes, "drop")
    serialize = outcome_verdict(outcomes, "serialize")
    keep = outcome_verdict(outcomes, "keep")
    ammo = outcome_verdict(outcomes, "ammo")
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
        and spawn == "pass"
        and equip == "pass"
        and attack == "pass"
        and drop == "pass"
        and serialize == "pass"
        and keep == "pass"
        and ammo == "pass"
        and data == "pass"
        and live == "pass"
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    spawn_row = outcomes.get("spawn", {}) if isinstance(outcomes.get("spawn"), dict) else {}
    spawn_ids = [str(x) for x in (spawn_row.get("ids") or [])]
    spawn_real = int(spawn_row.get("spawned", 0)) >= 11 and "fists" in spawn_ids
    attack_row = outcomes.get("attack", {}) if isinstance(outcomes.get("attack"), dict) else {}
    attack_ids = [str(x) for x in (attack_row.get("ids") or [])]
    attack_real = int(attack_row.get("attacked", 0)) >= 11 and set(REQUIRED_LIFECYCLE).issubset(attack_ids)
    equip_row = outcomes.get("equip", {}) if isinstance(outcomes.get("equip"), dict) else {}
    equip_ids = [str(x) for x in (equip_row.get("ids") or [])]
    equip_real = int(equip_row.get("equipped", 0)) >= 11 and set(REQUIRED_LIFECYCLE).issubset(equip_ids)
    keep_row = outcomes.get("keep", {}) if isinstance(outcomes.get("keep"), dict) else {}
    keep_real = bool(keep_row.get("after_melee")) and bool(keep_row.get("after_nade"))
    drop_row = outcomes.get("drop", {}) if isinstance(outcomes.get("drop"), dict) else {}
    drop_ids = [str(x) for x in (drop_row.get("ids") or [])]
    drop_real = set(REQUIRED_LIFECYCLE).issubset(drop_ids)
    ser_row = outcomes.get("serialize", {}) if isinstance(outcomes.get("serialize"), dict) else {}
    ser_ids = [str(x) for x in (ser_row.get("ids") or [])]
    ser_real = set(REQUIRED_LIFECYCLE).issubset(ser_ids) and bool(ser_row.get("hash_fields"))
    ammo_row = outcomes.get("ammo", {}) if isinstance(outcomes.get("ammo"), dict) else {}
    ammo_real = (
        bool(ammo_row.get("empty_ok"))
        and bool(ammo_row.get("reload_ok"))
        and int(ammo_row.get("roster_reserve", 0)) > 0
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
    events_ok = "item_pickup" in event_kinds or "bullet" in event_kinds or "nade" in event_kinds
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    screen_ok = len(screens) >= 1
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and spawn_real
        and equip_real
        and attack_real
        and drop_real
        and keep_real
        and ser_real
        and ammo_real
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
        "schema": "vault-fighters.vf3-wp5.run.v1",
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
        "map_id": "fx_roster_open",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "trace_sha256": trace_sha,
        "outcomes": {
            "SCHEMA": schema,
            "SPAWN": spawn,
            "EQUIP": equip,
            "ATTACK": attack,
            "DROP": drop,
            "SERIALIZE": serialize,
            "KEEP": keep,
            "AMMO": ammo,
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
            "roster_observed": False,
            "slots_observed": False,
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
            "RL-ITEM-SLOTS-4",
            "RL-ITEM-ROSTER",
            "RL-ITEM-PICK-SLOT",
            "RL-ITEM-KEEP-GUN",
            "RL-ITEM-AMMO-RELOAD",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
            "RL-SIM-INPUT-FRAME",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_roster.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_roster.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_roster.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "roster_headless_exit": args.headless_exit,
            "roster_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "slots": "assumption",
            "roster": "assumption",
            "pickup": "assumption",
            "keep_gun": "assumption",
            "ammo_reload": "assumption",
            "hold_to_aim": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF3-WP5 verdict

{verdict} weapon roster / inventory evidence (V-A18 / §18.3).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF3-WP5)

Verify: schema validation; every roster item spawns, equips, attacks, drops,
serializes; no gun loss when grenade/melee picked; ammo edge cases.

DoD: roster đủ để tạo chiến thuật đa dạng; values là tuning, không claim
original exact numbers.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, map `fx_roster_open`
- SCHEMA={schema} SPAWN={spawn} EQUIP={equip} ATTACK={attack} DROP={drop} SERIALIZE={serialize} KEEP={keep} AMMO={ammo} DATA={data} LIVE={live} REPLAY={replay}
- SPAWN spawned={spawn_row.get("spawned")} ids={spawn_ids} expected={spawn_row.get("expected")} real={spawn_real}
- EQUIP ids={equip_ids} real={equip_real}
- ATTACK attacked={attack_row.get("attacked")} ids={attack_ids} real={attack_real}
- DROP ids={drop_ids} real={drop_real}
- KEEP melee={keep_row.get("after_melee")} nade={keep_row.get("after_nade")} power={keep_row.get("after_power")} real={keep_real}
- SERIALIZE ids={ser_ids} hash_fields={ser_row.get("hash_fields")} real={ser_real}
- AMMO empty={ammo_row.get("empty_ok")} reload={ammo_row.get("reload_ok")} roster_reserve={ammo_row.get("roster_reserve")} real={ammo_real}
- events kinds include pickup/fire/throw={events_ok}
- window screenshot={screen_ok}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- Banners copy `RosterCases.outcome_*`. They are not inferred from fail-substrings.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_roster.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot --path godot/dogfood/superfighters --script res://tests/run_roster.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Four slots stay `ledger:RL-ITEM-SLOTS-4` assumption, not observed.
- Roster stays `ledger:RL-ITEM-ROSTER` assumption; values are tuning.
- Pickup slot replace stays `ledger:RL-ITEM-PICK-SLOT` assumption, not observed.
- Keep-gun stays `ledger:RL-ITEM-KEEP-GUN` assumption, not observed.
- Ammo/reload stay `ledger:RL-ITEM-AMMO-RELOAD` assumption, not observed.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption, not observed.
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
        ("run_roster.headless.log", Path(args.headless_log)),
        ("run_roster.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_roster.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  SCHEMA={schema} SPAWN={spawn} EQUIP={equip} ATTACK={attack} "
        f"DROP={drop} KEEP={keep} AMMO={ammo} LIVE={live} REPLAY={replay} "
        f"APPLY={succeeded}/{attempted}"
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
