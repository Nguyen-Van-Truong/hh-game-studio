#!/usr/bin/env python3
"""Assemble VF5-WP6 evidence after official six-map VS roster runs.

Does not tick the 29-8 plan. Does not launch Godot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF5WP6-20260831-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf5-wp6.vs-roster.2"
WP = "VF5-WP6"
SAIGON = timezone(timedelta(hours=7))

SOURCE_FILES = (
    "src/maps/arena_spec.gd",
    "src/maps/map_catalog.gd",
    "src/maps/map_graph.gd",
    "src/maps/map_codec.gd",
    "src/maps.gd",
    "src/arena.gd",
    "src/app.gd",
    "src/fighter.gd",
    "src/input_actions.gd",
    "src/ui/title_screen.gd",
    "src/hud.gd",
    "src/sim/sim_constants.gd",
    "src/sim/input_frame.gd",
    "src/world/env_body.gd",
    "src/world/env_spec.gd",
    "src/world/world_owner.gd",
    "src/game_session.gd",
    "data/maps/schema.json",
    "data/maps/catalog.json",
    "data/maps/arena_spec.json",
    "data/maps/arenas/hazardous.json",
    "data/maps/arenas/police.json",
    "data/maps/arenas/storage.json",
    "data/maps/arenas/rooftops.json",
    "data/maps/arenas/lantern.json",
    "data/maps/arenas/gauge.json",
    "data/world/catalog.json",
    "data/world/moving.json",
    "data/world/env.json",
    "tests/vs_roster_cases.gd",
    "tests/run_vs_roster.gd",
    "tests/check_vs_roster.py",
    "tests/pack_vs_roster_evidence.py",
    "tests/rooftop_cases.gd",
    "tests/warehouse_cases.gd",
    "tests/sewer_cases.gd",
    "tests/_gen_vs_arenas.py",
    "tests/map_cases.gd",
    "tests/run_all.gd",
    "docs/vs_roster.md",
    "docs/lantern.md",
    "docs/gauge.md",
    "docs/provenance.md",
    "docs/maps.md",
    "docs/world.md",
    "docs/env.md",
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


def _vs_field(log_text: str, key: str) -> str:
    prefix = "HH_VF_VS "
    needle = key + "="
    for line in log_text.splitlines():
        if not line.startswith(prefix):
            continue
        for part in line.split():
            if part.startswith(needle):
                return part.split("=", 1)[1]
    return ""


def _evidence_dir_value(log_text: str) -> str:
    prefix = "HH_VF_VS EVIDENCE_DIR="
    for line in log_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


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
    parser.add_argument("--leftover-proof", required=True)
    parser.add_argument("--exits-proof", required=True)
    args = parser.parse_args()

    product = Path(args.product)
    evidence = Path(args.evidence)
    review = Path(args.review)
    headless_ev = Path(args.headless_evidence)
    window_ev = Path(args.window_evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "screens").mkdir(parents=True, exist_ok=True)

    window_outcomes_path = window_ev / "outcomes.json"
    if not window_outcomes_path.is_file():
        print("FAIL: packed missing window outcomes.json (no headless fallback)")
        return 1
    outcomes = load_json(window_outcomes_path)
    partial_h = load_json(headless_ev / "run_partial.json")
    partial_w = load_json(window_ev / "run_partial.json")
    leftover_proof = load_json(Path(args.leftover_proof))
    exits_proof = load_json(Path(args.exits_proof))
    source_sha = {}
    missing_source: list[str] = []
    for rel in SOURCE_FILES:
        path = product / rel
        if path.is_file():
            source_sha[rel] = sha256_file(path)
        else:
            missing_source.append(rel)
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    godot_exe = Path(args.godot_exe)
    godot_hash = sha256_file(godot_exe) if godot_exe.is_file() else ""

    apply_info = outcomes.get("apply", {})
    keys = (
        "roster", "cycle", "load", "routes", "cover", "cargo", "door",
        "rotor", "toxic", "water", "lift", "lantern", "gauge", "p2",
        "bot", "camera", "live",
    )
    verdicts = {key: outcome_verdict(outcomes, key) for key in keys}
    replay = outcome_verdict(outcomes, "replay")
    succeeded = int(apply_info.get("succeeded", 0))
    attempted = int(apply_info.get("attempted", 0))
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    headless_pass = "PASS: Vault Fighters six-map VS roster" in headless_log_text
    window_pass = "PASS: Vault Fighters six-map VS roster" in window_log_text
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    sewer_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_SEWER ")), "")
    vs_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS ")), "")
    run_all_ok = (
        "PASS: Vault Fighters first playable" in run_all_log_text
        and "MAPS=pass" in dive_banner
        and "APPLY=1253/1253" in dive_banner
        and "status=proven" in dive_banner
        and "TACTIC=pass" in sewer_banner
        and "DIVE=pass" in sewer_banner
        and "status=proven" in sewer_banner
        and "ROSTER=pass" in vs_banner
        and "status=proven" in vs_banner
    )
    id_match = (
        RUN_ID in headless_log_text
        and RUN_ID in window_log_text
        and COMMAND_ID in headless_log_text
        and COMMAND_ID in window_log_text
        and str(partial_h.get("run_id", "")) == RUN_ID
        and str(partial_w.get("run_id", "")) == RUN_ID
        and int(partial_h.get("fail_count", 1)) == 0
        and int(partial_w.get("fail_count", 1)) == 0
    )
    headless_ev_dir = _evidence_dir_value(headless_log_text)
    window_ev_dir = _evidence_dir_value(window_log_text)
    banner_apply_h = int(_vs_field(headless_log_text, "USED_APPLY_FRAMES") or "-1")
    banner_apply_w = int(_vs_field(window_log_text, "USED_APPLY_FRAMES") or "-1")
    banner_step_h = int(_vs_field(headless_log_text, "USED_STEP_FIXED") or "1")
    banner_step_w = int(_vs_field(window_log_text, "USED_STEP_FIXED") or "1")
    live_logs_ok = (
        "Godot Engine v4.7.1" in headless_log_text
        and "Godot Engine v4.7.1" in window_log_text
        and "DISPLAY=headless" in headless_log_text
        and "DISPLAY=Windows" in window_log_text
        and RUN_ID in headless_ev_dir
        and RUN_ID in window_ev_dir
        and "PROBE" not in headless_ev_dir
        and "PROBE" not in window_ev_dir
        and banner_step_h == 0
        and banner_step_w == 0
        and banner_apply_h > 0
        and banner_apply_w > 0
        and banner_apply_h != int(apply_info.get("succeeded", 0) or 0)
        and banner_apply_w != int(apply_info.get("succeeded", 0) or 0)
    )
    godot_exe_ok = godot_exe.is_file() and godot_exe.stat().st_size >= 1_000_000
    step_fixed_ok = int(apply_info.get("used_step_fixed", 1)) == 0
    leftover_file = int(leftover_proof.get("leftover", -1)) if leftover_proof else -1
    leftover_ok = (
        leftover_proof
        and leftover_file == 0
        and args.leftover == leftover_file
        and int(leftover_proof.get("after_headless", -1)) == 0
        and int(leftover_proof.get("after_window", -1)) == 0
        and int(leftover_proof.get("after_run_all", -1)) == 0
    )
    exits_file_ok = (
        exits_proof
        and int(exits_proof.get("check", -1)) == args.check_exit
        and int(exits_proof.get("headless", -1)) == args.headless_exit
        and int(exits_proof.get("window", -1)) == args.window_exit
        and int(exits_proof.get("run_all", -1)) == args.run_all_exit
        and args.check_exit == 0
        and args.headless_exit == 0
        and args.window_exit == 0
        and args.run_all_exit == 0
    )
    source_closed = not missing_source
    exits_ok = (
        leftover_ok
        and exits_file_ok
        and source_closed
        and headless_pass
        and window_pass
        and run_all_ok
        and id_match
        and live_logs_ok
        and godot_exe_ok
        and step_fixed_ok
    )
    outcomes_ok = (
        all(verdicts[key] == "pass" for key in keys)
        and replay == "match"
        and succeeded > 0
        and succeeded == int(apply_info.get("used_apply_frames", -1))
    )
    water_row = outcomes.get("water", {}) if isinstance(outcomes.get("water"), dict) else {}
    lift_row = outcomes.get("lift", {}) if isinstance(outcomes.get("lift"), dict) else {}
    rotor_row = outcomes.get("rotor", {}) if isinstance(outcomes.get("rotor"), dict) else {}
    toxic_row = outcomes.get("toxic", {}) if isinstance(outcomes.get("toxic"), dict) else {}
    p2_row = outcomes.get("p2", {}) if isinstance(outcomes.get("p2"), dict) else {}
    bot_row = outcomes.get("bot", {}) if isinstance(outcomes.get("bot"), dict) else {}
    live_row = outcomes.get("live", {}) if isinstance(outcomes.get("live"), dict) else {}
    dx_dry = float(water_row.get("dx_dry", 0.0) or 0.0)
    dx_wet = float(water_row.get("dx_wet", 999.0) or 999.0)
    env_id = str(water_row.get("env_id", ""))
    water_real = (
        bool(water_row.get("wet_after", False))
        and not bool(water_row.get("wet_before", True))
        and dx_dry > 8.0
        and dx_wet < dx_dry * 0.85
        and bool(water_row.get("sprint_blocked", False))
        and env_id.startswith("cut_gutter")
    )
    lift_real = float(lift_row.get("y1", 999.0) or 999.0) < float(lift_row.get("y0", 0.0) or 0.0) - 16.0
    rotor_real = (
        not bool(rotor_row.get("used_give_weapon", True))
        and bool(rotor_row.get("jammed", False))
        and int(rotor_row.get("shots", 0) or 0) >= 1
        and "give_weapon" not in str(rotor_row.get("source", "")).replace("no give_weapon", "")
    )
    toxic_real = not bool(toxic_row.get("used_give_weapon", True))
    p2_smoke = str(p2_row.get("coverage", "")) == "smoke"
    bot_smoke = str(bot_row.get("coverage", "")) == "smoke"
    hud = live_row.get("hud") if isinstance(live_row.get("hud"), list) else []
    live_real = (
        hud
        == [
            "Skyline Relay",
            "Pallet Annex",
            "Signal Court",
            "Vitriol Sump",
            "Lantern Cut",
            "Gauge Deck",
        ]
        and str(live_row.get("source", "")) == "map_btn.pressed"
        and str(live_row.get("wrap_from", "")) == "gauge"
        and str(live_row.get("wrap_to", "")) == "rooftops"
    )
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    need = (
        "setup",
        "title",
        "rooftops",
        "storage",
        "police",
        "hazardous",
        "lantern_water",
        "gauge_lift",
        "vs_lantern_",
        "vs_gauge_",
    )
    # Map stills use vs_rooftops / vs_storage / ...; water/lift are extra.
    setup_png = pick_still(screens, "vs_setup") or pick_still(screens, "setup")
    title_png = pick_still(screens, "vs_title") or pick_still(screens, "title")
    roof_png = pick_still(screens, "vs_rooftops")
    store_png = pick_still(screens, "vs_storage")
    police_png = pick_still(screens, "vs_police")
    sewer_png = pick_still(screens, "vs_hazardous")
    lantern_png = next((p for p in screens if "vs_lantern_" in p.name and "water" not in p.name), None)
    gauge_png = next((p for p in screens if "vs_gauge_" in p.name and "lift" not in p.name), None)
    water_png = pick_still(screens, "lantern_water")
    lift_png = pick_still(screens, "gauge_lift")
    still_list = [
        setup_png, title_png, roof_png, store_png, police_png, sewer_png,
        lantern_png, gauge_png, water_png, lift_png,
    ]
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in still_list if p is not None]
    )
    if None in still_list:
        stills_ok = False
        still_errors.append("need setup/title/six maps/lantern_water/gauge_lift window stills")
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
    events_ok = bool({"roster", "cycle", "water", "lift", "cover", "toxic", "rotor", "live"} <= event_kinds)
    verdict = (
        "PASS"
        if exits_ok
        and outcomes_ok
        and water_real
        and lift_real
        and rotor_real
        and toxic_real
        and events_ok
        and stills_ok
        and live_real
        and p2_smoke
        and bot_smoke
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
    leftover_src = Path(args.leftover_proof)
    if leftover_src.is_file():
        (evidence / "leftover_proof.json").write_bytes(leftover_src.read_bytes())
    exits_src = Path(args.exits_proof)
    if exits_src.is_file():
        (evidence / "exits_proof.json").write_bytes(exits_src.read_bytes())
    screens_src = window_ev / "screens"
    if screens_src.is_dir():
        for png in screens_src.glob("*.png"):
            (evidence / "screens" / png.name).write_bytes(png.read_bytes())
    for label, src in (
        ("run_vs_roster.headless.log", Path(args.headless_log)),
        ("run_vs_roster.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_vs_roster.log", Path(args.check_log)),
    ):
        if src.is_file():
            (evidence / label).write_bytes(src.read_bytes())

    metrics = {
        "frame_budget_hz": 60,
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
        "P2_COVERAGE": "smoke",
        "BOT_COVERAGE": "smoke",
        "NOT_AI": 1,
        "NOT_Y8_PARITY": 1,
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    started_at = str(partial_h.get("started_at") or partial_w.get("started_at") or "")
    ended_at = str(partial_w.get("ended_at") or partial_h.get("ended_at") or now_saigon())
    run = {
        "schema": "vault-fighters.vf5-wp6.run.v1",
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
        "seed": 16,
        "map_id": "rooftops",
        "mode": "vs2",
        "tick_hz": 60,
        "epsilon": 0.001,
        "source_tree_sha256": source_tree,
        "source_sha256": source_sha,
        "outcomes": {
            **{key.upper(): verdicts[key] for key in keys},
            "REPLAY": replay,
            "P2_COVERAGE": "smoke",
            "BOT_COVERAGE": "smoke",
            "USED_APPLY_FRAMES": succeeded,
            "USED_APPLY_ATTEMPTED": attempted,
            "USED_APPLY_SUCCEEDED": succeeded,
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "map_lantern_observed": False,
            "map_gauge_observed": False,
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
            "RL-MAP-VS-ROSTER",
            "RL-MAP-LANTERN",
            "RL-MAP-GAUGE",
            "RL-DELTA-MAP-NAMES",
            "RL-MAP-GRAPH",
            "RL-CTRL-HOLD-AIM",
            "RL-SIM-FIXED-60",
        ],
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_vs_roster.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_vs_roster.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_vs_roster.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "vs_headless_exit": args.headless_exit,
            "vs_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
            "display_headless": str(partial_h.get("display", "headless")),
            "display_window": str(partial_w.get("display", "Windows")),
            "roster": "assumption",
            "graph": "assumption",
            "hold_to_aim": "assumption",
            "roll_dive": "unavailable",
        },
        "verdict": verdict,
    }
    (evidence / "run.json").write_text(
        json.dumps(run, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    verdict_md = f"""# VF5-WP6 verdict

{verdict} six-map VS roster (V-A18).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF5-WP6)

Verify: six maps load from clean project; each has >=2 routes, valid spawns,
weapon points, camera fit and one unique interaction; map-cycle wraps safely.

DoD: six-map VS coverage; no hidden map only in code.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `16`, mode `vs2`, setup map `rooftops`
- roster rooftops/Skyline Relay, storage/Pallet Annex, police/Signal Court, hazardous/Vitriol Sump, lantern/Lantern Cut, gauge/Gauge Deck
- Stage stays four. Draft Yard is author-only.
- ROSTER={verdicts['roster']} CYCLE={verdicts['cycle']} LOAD={verdicts['load']} ROUTES={verdicts['routes']} COVER={verdicts['cover']} CARGO={verdicts['cargo']} DOOR={verdicts['door']} ROTOR={verdicts['rotor']} TOXIC={verdicts['toxic']} WATER={verdicts['water']} LIFT={verdicts['lift']} LANTERN={verdicts['lantern']} GAUGE={verdicts['gauge']} CAMERA={verdicts['camera']} LIVE={verdicts['live']} REPLAY={replay}
- WATER wet_before={water_row.get('wet_before')} wet_after={water_row.get('wet_after')} dx_dry={water_row.get('dx_dry')} dx_wet={water_row.get('dx_wet')} sprint_blocked={water_row.get('sprint_blocked')} env_id={water_row.get('env_id')} real={water_real}
- LIFT y0={lift_row.get('y0')} y1={lift_row.get('y1')} boards={lift_row.get('boards')} real={lift_real}
- ROTOR give_weapon={rotor_row.get('used_give_weapon')} jammed={rotor_row.get('jammed')} shots={rotor_row.get('shots')} held={rotor_row.get('held_weapon')} real={rotor_real}
- TOXIC give_weapon={toxic_row.get('used_give_weapon')} real={toxic_real}
- LIVE hud={hud} wrap={live_row.get('wrap_from')}->{live_row.get('wrap_to')} source={live_row.get('source')} real={live_real}
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- `USED_APPLY_FRAMES={succeeded}` attempted={attempted}
- live stdout banners APPLY headless={banner_apply_h} window={banner_apply_w} (printed before still staging; packer copies logs verbatim and does not rewrite these lines)
- EVIDENCE_DIR headless=`{headless_ev_dir}` window=`{window_ev_dir}`
- source_tree_sha256 `{source_tree}`
- base_head `{args.base_head}`
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_vs_roster.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_vs_roster.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_vs_roster.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Lantern Cut / Gauge Deck / VS roster stay assumption
  (`ledger:RL-MAP-LANTERN`, `ledger:RL-MAP-GAUGE`, `ledger:RL-MAP-VS-ROSTER`).
- Jump envelope is product tuning (dx=10 / dy=4).
- Unique interactions are live `apply_frames` bodies.
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke: not AI and not Y8 parity.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Y8 roll/dive observation stays `ledger:RL-MOVE-ROLL-DIVE` unavailable.
- Art still VF7. Overlay Q2 854×480 contact sheet was not a second official size.
- No new in-game Y8 play this WP. Not a copied billboard or Y8 collision map.
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
        evidence / "leftover_proof.json",
        evidence / "exits_proof.json",
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
        "leftover_proof.json",
        "exits_proof.json",
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
        ("run_vs_roster.headless.log", Path(args.headless_log)),
        ("run_vs_roster.window.log", Path(args.window_log)),
        ("run_all.log", Path(args.run_all_log)),
        ("check_vs_roster.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())

    print(f"PASS: packed {RUN_ID}" if verdict == "PASS" else f"FAIL: packed {RUN_ID}")
    print(f"  verdict={verdict} source_tree_sha256={source_tree}")
    print(
        f"  leftover_ok={leftover_ok} exits_file_ok={exits_file_ok} "
        f"source_closed={source_closed} missing_source={missing_source} "
        f"water_real={water_real} rotor_real={rotor_real} live_real={live_real}"
    )
    print(
        f"  live_logs_ok={live_logs_ok} godot_exe_ok={godot_exe_ok} "
        f"step_fixed_ok={step_fixed_ok} "
        f"banner_apply_h={banner_apply_h} banner_apply_w={banner_apply_w} "
        f"partial_apply={int(apply_info.get('succeeded', 0) or 0)} "
        f"ev_h={headless_ev_dir} ev_w={window_ev_dir} "
        f"godot_exe_bytes={godot_exe.stat().st_size if godot_exe.is_file() else 0}"
    )
    print(f"  stills_pairwise_distinct={stills_ok} hashes={still_hashes}")
    for err in still_errors:
        print(f"  still: {err}")
    _ = need
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
