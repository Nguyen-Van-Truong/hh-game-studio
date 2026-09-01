#!/usr/bin/env python3
"""Assemble VF6-WP1 evidence after official match-machine runs.

Does not tick the 29-8 plan. Does not launch Godot.
Fail-closed: window outcomes required, leftover/exits from proof files,
source list frozen, no caller-only exit trust.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF6WP1-20260901-ASIA-SAIGON-04"
COMMAND_ID = "cmd.vf6-wp1.match-machine.4"
WP = "VF6-WP1"
SAIGON = timezone(timedelta(hours=7))
SOURCE_SUFFIXES = {".gd", ".json", ".tscn", ".md"}
SOURCE_ROOTS = ("src", "data", "scenes")
SOURCE_EXTRA = (
    "tests/match_cases.gd",
    "tests/run_match.gd",
    "tests/check_match.py",
    "tests/pack_match_evidence.py",
    "tests/run_all.gd",
    "tests/traces/match/match_win.json",
    "tests/traces/match/match_lose.json",
    "tests/traces/match/match_tie.json",
    "tests/traces/match/match_quit.json",
    "tests/traces/match/match_restart.json",
    "tests/traces/match/match_pause.json",
    "tests/traces/README.md",
    "docs/match.md",
    "docs/reference-ledger.md",
    "KNOWN_ISSUES.md",
    "PROJECT_BRIEF.md",
    "project.godot",
)


def iter_source_files(product: Path) -> tuple[str, ...]:
    found: set[str] = set(SOURCE_EXTRA)
    for root_name in SOURCE_ROOTS:
        root = product / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            found.add(path.relative_to(product).as_posix())
    return tuple(sorted(found))


SOURCE_FILES = SOURCE_EXTRA


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _field(log_text: str, prefix: str, key: str) -> str:
    needle = key + "="
    for line in log_text.splitlines():
        if not line.startswith(prefix):
            continue
        for part in line.split():
            if part.startswith(needle):
                return part.split("=", 1)[1]
    return ""


def _evidence_dir_value(log_text: str) -> str:
    prefix = "HH_VF_MATCH EVIDENCE_DIR="
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
                errors.append(f"{rows[i][0]} and {rows[j][0]} identical sha256")
            j += 1
        i += 1
    return (not errors, hashes, errors)


def parse_exit_from_log(text: str) -> int | None:
    # Host WaitForExit is the authority. A PASS banner alone is never
    # treated as process exit 0 (HH leftover-0 / Verify hung-process).
    lowered = text.lower()
    if "hh_assert_fail" in lowered or "status=unproven" in lowered:
        return None
    if any(token in lowered for token in ("warning:", "error:", "script warning", "parse error")):
        return None
    if "FAIL: Vault Fighters match state machine" in text:
        return 1
    if "HH_VF_MATCH FINISHED=1" in text and "HH_VF_MATCH PROCESS_EXIT=0" in text:
        return 0
    if "HH_VF_MATCH FINISHED=1" in text and "HH_VF_MATCH PROCESS_EXIT=1" in text:
        return 1
    return None


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
    parser.add_argument("--freeze", required=True)
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
    freeze = load_json(Path(args.freeze))
    leftover_proof = load_json(Path(args.leftover_proof))
    exits_proof = load_json(Path(args.exits_proof))
    # Transition evidence must carry a post-state hash for every lifecycle
    # edge; a banner or start/end snapshot alone is insufficient.
    transition_path = window_ev / "events.jsonl"
    if not transition_path.is_file():
        transition_path = headless_ev / "events.jsonl"
    transition_errors: list[str] = []
    if transition_path.is_file():
        for line_no, line in enumerate(transition_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                transition_errors.append(f"events.jsonl line {line_no} invalid JSON")
                continue
            if row.get("phase") == "match_phase" and row.get("kind") == "transition":
                payload = row.get("payload", {})
                for key in ("from", "to", "reason", "round_id", "post_hash", "post_phase", "match_hash"):
                    if key not in payload or payload.get(key) in ("", None):
                        transition_errors.append(f"transition line {line_no} missing {key}")
    else:
        transition_errors.append("missing events.jsonl transition evidence")
    source_sha = {}
    missing_source: list[str] = []
    source_list = iter_source_files(product)
    if len(source_list) < 80:
        print(f"FAIL: source closure too small ({len(source_list)} files)")
        return 1
    for rel in source_list:
        path = product / rel
        if path.is_file():
            source_sha[rel] = sha256_file(path)
        else:
            missing_source.append(rel)
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    freeze_tree = str(freeze.get("source_tree_sha256", ""))
    if not freeze_tree or freeze_tree != source_tree:
        print("FAIL: source drifted from freeze or freeze missing")
        print(f"  freeze={freeze_tree}")
        print(f"  now={source_tree}")
        return 1
    godot_exe = Path(args.godot_exe)
    godot_hash = sha256_file(godot_exe) if godot_exe.is_file() else ""

    apply_info = outcomes.get("apply", {})
    keys = (
        "schema", "machine", "win", "lose", "tie", "quit",
        "restart", "pause", "signal", "seed", "ff", "live",
    )
    verdicts = {key: outcome_verdict(outcomes, key) for key in keys}
    replay = outcome_verdict(outcomes, "replay")
    succeeded = int(apply_info.get("succeeded", 0))
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    parsed_h = parse_exit_from_log(headless_log_text)
    parsed_w = parse_exit_from_log(window_log_text)
    headless_pass = parsed_h == 0
    window_pass = parsed_w == 0
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    sewer_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_SEWER ")), "")
    vs_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS ")), "")
    match_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_MATCH ") and "MACHINE=" in ln), "")
    run_all_ok = (
        "PASS: Vault Fighters first playable" in run_all_log_text
        and "HH_ASSERT_FAIL" not in run_all_log_text
        and "FAIL: Vault Fighters" not in run_all_log_text
        and "MAPS=pass" in dive_banner
        and "APPLY=1253/1253" in dive_banner
        and "status=proven" in dive_banner
        and "TACTIC=pass" in sewer_banner
        and "status=proven" in sewer_banner
        and "ROSTER=pass" in vs_banner
        and "status=proven" in vs_banner
        and "WIN=pass" in match_banner
        and "TIE=pass" in match_banner
        and "PAUSE=pass" in match_banner
        and "FORCE_KILL=0" in match_banner
        and "status=proven" in match_banner
    )
    id_match = (
        RUN_ID in headless_log_text
        and RUN_ID in window_log_text
        and COMMAND_ID in headless_log_text
        and COMMAND_ID in window_log_text
    )
    live_logs_ok = (
        "Godot Engine v4.7.1" in headless_log_text
        and "Godot Engine v4.7.1" in window_log_text
        and "DISPLAY=headless" in headless_log_text
        and "DISPLAY=Windows" in window_log_text
        and RUN_ID in _evidence_dir_value(headless_log_text)
        and RUN_ID in _evidence_dir_value(window_log_text)
        and int(_field(headless_log_text, "HH_VF_MATCH ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(window_log_text, "HH_VF_MATCH ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(headless_log_text, "HH_VF_MATCH ", "USED_FORCE_KILL") or "1") == 0
        and int(_field(window_log_text, "HH_VF_MATCH ", "USED_FORCE_KILL") or "1") == 0
    )
    leftover_ok = (
        leftover_proof
        and int(leftover_proof.get("leftover", -1)) == 0
        and args.leftover == 0
        and int(leftover_proof.get("after_headless", -1)) == 0
        and int(leftover_proof.get("after_window", -1)) == 0
        and int(leftover_proof.get("after_run_all", -1)) == 0
        and "console" in str(leftover_proof.get("window_exe", "")).lower()
        and int(leftover_proof.get("window_host_exit", -1)) == 0
        and float(leftover_proof.get("window_elapsed_sec", 999)) <= 240.0
        and int(leftover_proof.get("run_all_host_exit", -1)) == 0
    )
    exits_ok = (
        exits_proof
        and int(exits_proof.get("check", -1)) == 0
        and int(exits_proof.get("headless", -1)) == 0
        and int(exits_proof.get("window", -1)) == 0
        and int(exits_proof.get("run_all", -1)) == 0
        and args.check_exit == 0
        and args.headless_exit == 0
        and args.window_exit == 0
        and args.run_all_exit == 0
        and parsed_h == args.headless_exit
        and parsed_w == args.window_exit
    )
    machine_row = outcomes.get("machine", {}) if isinstance(outcomes.get("machine"), dict) else {}
    machine_modes = [str(m) for m in machine_row.get("modes", [])]
    win_src = str(outcomes.get("win", {}).get("source", "") if isinstance(outcomes.get("win"), dict) else "")
    lose_src = str(outcomes.get("lose", {}).get("source", "") if isinstance(outcomes.get("lose"), dict) else "")
    tie_src = str(outcomes.get("tie", {}).get("source", "") if isinstance(outcomes.get("tie"), dict) else "")
    quit_src = str(outcomes.get("quit", {}).get("source", "") if isinstance(outcomes.get("quit"), dict) else "")
    restart_src = str(outcomes.get("restart", {}).get("source", "") if isinstance(outcomes.get("restart"), dict) else "")
    pause_src = str(outcomes.get("pause", {}).get("source", "") if isinstance(outcomes.get("pause"), dict) else "")
    live_row = outcomes.get("live", {}) if isinstance(outcomes.get("live"), dict) else {}
    e2e_ok = (
        "survival" not in machine_modes
        and "vs2" in machine_modes
        and "apply_frames match_win.json" not in win_src
        and ("parse_input_event" in win_src or "title" in win_src.lower())
        and "apply_frames match_lose.json" not in lose_src
        and ("parse_input_event" in lose_src or "title" in lose_src.lower())
        and "apply_frames match_tie.json" not in tie_src
        and "title" in tie_src.lower()
        and "title" in quit_src.lower()
        and "Restart" in restart_src
        and "push_input" in pause_src
        and bool(live_row.get("title_visible_after", False))
    )
    outcomes_ok = (
        all(verdicts[key] == "pass" for key in keys)
        and replay == "match"
        and succeeded > 0
        and int(apply_info.get("used_force_kill", 1)) == 0
        and int(apply_info.get("used_step_fixed", 1)) == 0
        and e2e_ok
    )
    screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    still_list = [
        pick_still(screens, "match_setup") or pick_still(screens, "setup"),
        pick_still(screens, "match_title") or pick_still(screens, "title"),
        pick_still(screens, "match_win"),
        pick_still(screens, "match_lose"),
        pick_still(screens, "match_tie"),
        pick_still(screens, "match_pause"),
        pick_still(screens, "match_quit"),
        pick_still(screens, "match_restart"),
    ]
    stills_ok, still_hashes, still_errors = stills_pairwise_distinct(
        [p for p in still_list if p is not None]
    )
    if None in still_list:
        stills_ok = False
        still_errors.append("need setup/title/win/lose/tie/pause/quit/restart window stills")
    packed_ok = (
        leftover_ok
        and exits_ok
        and not missing_source
        and headless_pass
        and window_pass
        and run_all_ok
        and id_match
        and live_logs_ok
        and outcomes_ok
        and stills_ok
        and godot_exe.is_file()
        and not transition_errors
    )
    evidence.joinpath("source_manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
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
    freeze_src = Path(args.freeze)
    if freeze_src.is_file():
        (evidence / "freeze.json").write_bytes(freeze_src.read_bytes())
    screens_src = window_ev / "screens"
    if screens_src.is_dir():
        for png in screens_src.glob("*.png"):
            (evidence / "screens" / png.name).write_bytes(png.read_bytes())
    for label, src in (
        ("run_match.headless.log", Path(args.headless_log)),
        ("run_match.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_match.log", Path(args.check_log)),
    ):
        if src.is_file():
            (evidence / label).write_bytes(src.read_bytes())

    apply_attempted = int(apply_info.get("attempted", 0))
    metrics = {
        "frame_budget_hz": 60,
        "apply_attempted": apply_attempted,
        "apply_succeeded": succeeded,
        "os": platform.platform(),
        "python": platform.python_version(),
        "process_rss_hint": "see host leftover-0 check; Godot process ended",
        "budgets": {
            "epsilon": 0.001,
            "leftover_godot": args.leftover,
        },
        "P2_COVERAGE": "smoke",
        "BOT_COVERAGE": "smoke",
        "NOT_AI": 1,
        "NOT_Y8_PARITY": 1,
        "FORCE_KILL_OFFICIAL": 0,
        "TIMER": "assumption",
        "COUNTDOWN": "assumption",
    }
    (evidence / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    started_at = ""
    ended_at = now_saigon()
    partial_h = load_json(headless_ev / "run_partial.json")
    partial_w = load_json(window_ev / "run_partial.json")
    if partial_h:
        started_at = str(partial_h.get("started_at", started_at))
    if partial_w:
        ended_at = str(partial_w.get("ended_at", ended_at))
        if not started_at:
            started_at = str(partial_w.get("started_at", started_at))
    verdict = "PASS" if packed_ok else "FAIL"
    run_doc = {
        "schema": "vault-fighters.vf6-wp1.run.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "timezone": "Asia/Saigon",
        "packed_at": now_saigon(),
        "started_at": started_at,
        "ended_at": ended_at,
        "base_head": args.base_head,
        "godot": "4.7.1.stable.official.a13da4feb",
        "godot_exe_sha256": godot_hash,
        "source_tree_sha256": source_tree,
        "freeze_source_tree_sha256": freeze_tree,
        "source_sha256": source_sha,
        "verdicts": verdicts,
        "replay": replay,
        "stills": still_hashes,
        "packed_ok": packed_ok,
        "verdict": verdict,
        "honesty": {
            "p2_coverage": "smoke",
            "bot_coverage": "smoke",
            "not_ai": True,
            "not_y8_parity": True,
            "timer": "assumption",
            "countdown": "assumption",
            "force_kill_official": False,
            "clock": "RL-SIM-FIXED-60 assumption",
            "hold_to_aim": "RL-CTRL-HOLD-AIM assumption",
        },
        "claims": {
            "y8_parity": False,
            "y8_tick_rate": False,
            "plan_checkbox_ticked": False,
            "implementer_commit": False,
            "r9_wp4": False,
            "g6": False,
            "gx": False,
            "progress_60_of_60": False,
        },
        "verify": {
            "official": [
                "python godot/dogfood/superfighters/tests/check_match.py",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_match.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_match.gd",
                "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
            ],
            "file_check_exit": args.check_exit,
            "match_headless_exit": args.headless_exit,
            "match_window_exit": args.window_exit,
            "run_all_exit": args.run_all_exit,
            "leftover_godot": args.leftover,
        },
        "repro": [
            "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_match.gd",
            "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --path <worktree>/godot/dogfood/superfighters --script res://tests/run_match.gd",
            "%LOCALAPPDATA%\\HHGodotAgent\\tooling\\godot-4.7.1-stable\\bin\\Godot_v4.7.1-stable_win64_console.exe --headless --path <worktree>/godot/dogfood/superfighters --script res://tests/run_all.gd",
        ],
    }
    (evidence / "run.json").write_text(json.dumps(run_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    verdict_md = f"""# VF6-WP1 verdict

{verdict} one canonical match state machine (V-A18).
Not Y8 parity. Not V0. Plan checkbox **not** ticked. No implementer commit.

## DoD / Verify (quoted from 29-8 VF6-WP1)

Verify: real typed input traces plus real window/menu/input E2E for
win/loss/tie/quit/restart/pause; no direct apply_eval, private method,
synthetic .pressed.emit() or force_kill may be the sole proof. Pause
must not advance sim. Host captures actual Godot process exits; hung/killed is FAIL.

DoD: one canonical match state machine used by every mode.

## Run

- `run_id`: `{RUN_ID}`
- `command_id`: `{COMMAND_ID}`
- seed `7`, mode `vs2`, setup map `police` / Signal Court
- SCHEMA={verdicts['schema']} MACHINE={verdicts['machine']} WIN={verdicts['win']} LOSE={verdicts['lose']} TIE={verdicts['tie']} QUIT={verdicts['quit']} RESTART={verdicts['restart']} PAUSE={verdicts['pause']} SIGNAL={verdicts['signal']} SEED={verdicts['seed']} FF={verdicts['ff']} LIVE={verdicts['live']} REPLAY={replay}
- `USED_APPLY_FRAMES={succeeded}` attempted={apply_attempted} `USED_FORCE_KILL=0` `USED_STEP_FIXED=0`
- window stills pairwise_distinct={stills_ok}
- still hashes: {still_hashes}
- still errors: {still_errors}
- EVIDENCE_DIR headless=`{headless_ev}` window=`{window_ev}`
- source_tree_sha256 `{source_tree}`
- freeze `{freeze_tree}`
- base_head `{args.base_head}`
- window.log / headless.log are live process stdout/stderr, not rebuilt from `run_partial`.

## Reproduction

```
python godot/dogfood/superfighters/tests/check_match.py
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_match.gd
$godot_console --path godot/dogfood/superfighters --script res://tests/run_match.gd
$godot_console --headless --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

EXIT {args.check_exit} / {args.headless_exit} / {args.window_exit} / {args.run_all_exit}. leftover Godot on product `--path` = {args.leftover}.

## Honesty

- 60 Hz is `ledger:RL-SIM-FIXED-60` assumption, not observed Y8 clock.
- Hold-to-aim stays `ledger:RL-CTRL-HOLD-AIM` assumption.
- Round timer / countdown stay assumption, not observed. Official tie is a labeled timeout approximation (`round_timer_ticks=36`).
- P2_COVERAGE=smoke and BOT_COVERAGE=smoke until VF6-WP5. Not AI. Not Y8 parity.
- `force_kill` remains fixture-only. Official MATCH traces and `apply_frames` do not call it.
- Art still VF7.
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
        evidence / "freeze.json",
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
        "freeze.json",
        "hashes.txt",
        "source_manifest.txt",
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
        ("run_match.headless.log", Path(args.headless_log)),
        ("run_match.window.log", Path(args.window_log)),
        ("run_all.headless.log", Path(args.run_all_log)),
        ("check_match.log", Path(args.check_log)),
    ):
        if src.is_file():
            (review / label).write_bytes(src.read_bytes())
    if not packed_ok:
        print("FAIL: VF6-WP1 packer rejected the package")
        if missing_source:
            print("  missing " + ",".join(missing_source))
        if still_errors:
            print("  stills " + " | ".join(still_errors))
        if not leftover_ok:
            print("  leftover proof failed")
        if not exits_ok:
            print("  exits proof failed or mismatched parsed logs")
        if not run_all_ok:
            print("  run_all missing PASS/DIVE 1253/VS/MATCH banners")
        if not outcomes_ok:
            print("  window outcomes incomplete or apply_frames-only E2E")
            print("  e2e_ok=%s modes=%s title_after=%s" % (
                e2e_ok,
                machine_modes,
                live_row.get("title_visible_after"),
            ))
        return 1
    print("PASS: VF6-WP1 evidence packed")
    print(f"SOURCE_TREE={source_tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
