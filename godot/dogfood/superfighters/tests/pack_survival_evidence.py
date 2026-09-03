#!/usr/bin/env python3
"""Assemble VF6-WP4 evidence after official Survival runs.

Does not tick the 29-8 plan. Does not launch Godot.
Fail-closed: window outcomes required, leftover/exits from proof files,
source list frozen, no caller-only exit trust.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN_ID = "VF6WP4-20260903-ASIA-SAIGON-02"
COMMAND_ID = "cmd.vf6-wp4.survival.2"
WP = "VF6-WP4"
SAIGON = timezone(timedelta(hours=7))
HEADLESS_SOAK = 600
WINDOW_SOAK = 300
SOURCE_SUFFIXES = {".gd", ".json", ".tscn", ".md"}
SOURCE_ROOTS = ("src", "data", "scenes")
SOURCE_EXTRA = (
    "tests/survival_cases.gd",
    "tests/run_survival.gd",
    "tests/check_survival.py",
    "tests/pack_survival_evidence.py",
    "tests/run_all.gd",
    "tests/stage_cases.gd",
    "tests/match_cases.gd",
    "docs/survival.md",
    "docs/stage.md",
    "docs/match.md",
    "docs/vs_flow.md",
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
    prefix = "HH_VF_SURVIVAL EVIDENCE_DIR="
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


def parse_exit_from_log(text: str) -> int | None:
    lowered = text.lower()
    if "hh_assert_fail" in lowered or "status=unproven" in lowered:
        return None
    if any(token in lowered for token in ("warning:", "error:", "script warning", "parse error")):
        return None
    if "FAIL: Vault Fighters survival director" in text:
        return 1
    if "HH_VF_SURVIVAL FINISHED=1" in text and "HH_VF_SURVIVAL PROCESS_EXIT=0" in text:
        return 0
    if "HH_VF_SURVIVAL FINISHED=1" in text and "HH_VF_SURVIVAL PROCESS_EXIT=1" in text:
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
    if missing_source:
        print("FAIL: missing frozen source " + ",".join(missing_source[:8]))
        return 1
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    freeze_tree = str(freeze.get("source_tree_sha256", ""))
    if not freeze_tree or freeze_tree != source_tree:
        print("FAIL: source drifted from freeze or freeze missing")
        print(f"  freeze={freeze_tree}")
        print(f"  now={source_tree}")
        return 1
    godot_exe = Path(args.godot_exe)
    if "win64_console.exe" not in godot_exe.name.lower():
        print("FAIL: official window must use Godot_v4.7.1-stable_win64_console.exe")
        return 1
    godot_hash = sha256_file(godot_exe) if godot_exe.is_file() else ""

    keys = ("schema", "load", "distinct", "score", "spawn", "pause", "restart", "live")
    verdicts = {key: outcome_verdict(outcomes, key) for key in keys}
    apply_info = outcomes.get("apply", {})
    score_row = outcomes.get("score", {}) if isinstance(outcomes.get("score"), dict) else {}
    spawn_row = outcomes.get("spawn", {}) if isinstance(outcomes.get("spawn"), dict) else {}
    distinct_row = outcomes.get("distinct", {}) if isinstance(outcomes.get("distinct"), dict) else {}
    restart_row = outcomes.get("restart", {}) if isinstance(outcomes.get("restart"), dict) else {}
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    parsed_h = parse_exit_from_log(headless_log_text)
    parsed_w = parse_exit_from_log(window_log_text)
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    vs_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS ") and "ROSTER=" in ln), "")
    match_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_MATCH ") and "MACHINE=" in ln), "")
    flow_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS2 ") and "FIRST=" in ln), "")
    stage_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_STAGE ") and "ADVANCE=" in ln), "")
    survival_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_SURVIVAL ") and "SCORE=" in ln), "")
    run_all_ok = (
        "PASS: Vault Fighters first playable" in run_all_log_text
        and "HH_ASSERT_FAIL" not in run_all_log_text
        and "FAIL: Vault Fighters" not in run_all_log_text
        and "MAPS=pass" in dive_banner
        and "APPLY=1253/1253" in dive_banner
        and "status=proven" in dive_banner
        and "ROSTER=pass" in vs_banner
        and "status=proven" in vs_banner
        and "WIN=pass" in match_banner
        and "FORCE_KILL=0" in match_banner
        and "status=proven" in match_banner
        and "FIRST=pass" in flow_banner
        and "LEAK=pass" in flow_banner
        and "REMATCH=pass" in flow_banner
        and "status=proven" in flow_banner
        and "ADVANCE=pass" in stage_banner
        and "LOSS=pass" in stage_banner
        and "HASH=pass" in stage_banner
        and "status=proven" in stage_banner
        and "SCORE=pass" in survival_banner
        and "SPAWN=pass" in survival_banner
        and "status=proven" in survival_banner
        and "HH_VF_ALL FINISHED=1" in run_all_log_text
        and "HH_VF_ALL PROCESS_EXIT=0" in run_all_log_text
    )
    live_logs_ok = (
        "Godot Engine v4.7.1" in headless_log_text
        and "Godot Engine v4.7.1" in window_log_text
        and "DISPLAY=headless" in headless_log_text
        and "DISPLAY=Windows" in window_log_text
        and RUN_ID in headless_log_text
        and RUN_ID in window_log_text
        and COMMAND_ID in headless_log_text
        and COMMAND_ID in window_log_text
        and RUN_ID in _evidence_dir_value(headless_log_text)
        and RUN_ID in _evidence_dir_value(window_log_text)
        and int(_field(headless_log_text, "HH_VF_SURVIVAL ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(window_log_text, "HH_VF_SURVIVAL ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(headless_log_text, "HH_VF_SURVIVAL ", "USED_FORCE_KILL") or "1") == 0
        and int(_field(window_log_text, "HH_VF_SURVIVAL ", "USED_FORCE_KILL") or "1") == 0
    )
    headless_elapsed = float(leftover_proof.get("headless_elapsed_sec", -1))
    window_elapsed = float(leftover_proof.get("window_elapsed_sec", -1))
    soak_ok = headless_elapsed >= HEADLESS_SOAK and window_elapsed >= WINDOW_SOAK
    after_h = int(leftover_proof.get("after_headless", -1))
    after_w = int(leftover_proof.get("after_window", -1))
    after_a = int(leftover_proof.get("after_run_all", -1))
    leftover_computed = max(after_h, after_w, after_a)
    host_h = int(leftover_proof.get("headless_host_exit", -1))
    host_w = int(leftover_proof.get("window_host_exit", -1))
    host_a = int(leftover_proof.get("run_all_host_exit", -1))
    leftover_ok = (
        leftover_proof
        and leftover_computed == 0
        and leftover_computed == int(leftover_proof.get("leftover", -1))
        and leftover_computed == args.leftover
        and after_h == 0
        and after_w == 0
        and after_a == 0
        and "console" in str(leftover_proof.get("window_exe", "")).lower()
        and host_h == 0
        and host_w == 0
        and host_a == 0
        and soak_ok
    )
    parsed_all = None
    if "HH_VF_ALL FINISHED=1" in run_all_log_text and "HH_VF_ALL PROCESS_EXIT=0" in run_all_log_text:
        parsed_all = 0
    elif "HH_VF_ALL FINISHED=1" in run_all_log_text and "HH_VF_ALL PROCESS_EXIT=1" in run_all_log_text:
        parsed_all = 1
    exits_ok = (
        exits_proof
        and int(exits_proof.get("check", -1)) == 0
        and int(exits_proof.get("headless", -1)) == host_h
        and int(exits_proof.get("window", -1)) == host_w
        and int(exits_proof.get("run_all", -1)) == host_a
        and args.check_exit == 0
        and args.headless_exit == host_h
        and args.window_exit == host_w
        and args.run_all_exit == host_a
        and parsed_h == host_h
        and parsed_w == host_w
        and parsed_all == host_a
        and parsed_h == 0
        and parsed_w == 0
        and parsed_all == 0
    )
    events_path = window_ev / "events.jsonl"
    events_text = events_path.read_text(encoding="utf-8", errors="replace") if events_path.is_file() else ""
    timeline_rows = outcomes.get("timeline", [])
    events_ok = (
        events_path.is_file()
        and events_path.stat().st_size > 0
        and isinstance(timeline_rows, list)
        and len(timeline_rows) >= 4
    )
    living_seen = spawn_row.get("living_seen", [])
    if not isinstance(living_seen, list):
        living_seen = []
    living_ints = [int(v) for v in living_seen if str(v).lstrip("-").isdigit()]
    events_have_spawn = "spawn" in events_text
    events_have_deny = "spawn_denied" in events_text and "living_cap" in events_text
    kill_score_ok = (
        int(score_row.get("kills", 0)) >= 3
        and int(score_row.get("score_from_kills", 0)) >= 100
        and int(score_row.get("last_wave", 0)) >= 2
        and int(score_row.get("last", -1)) >= int(score_row.get("first", 0)) + 100
    )
    roster_ok = (
        1 in living_ints
        and 2 in living_ints
        and 3 in living_ints
        and int(spawn_row.get("max_living_bots", 0)) >= 3
        and int(spawn_row.get("max_living_bots", 99)) <= int(spawn_row.get("cap_living_bots", 0))
    )
    cap_ok = (
        int(spawn_row.get("max_living_bots", 0)) >= 6
        and int(spawn_row.get("refused_cap", 0)) >= 1
        and int(spawn_row.get("cap_denied_living", 0)) >= 6
        and str(spawn_row.get("last_deny_reason", "")) == "living_cap"
        and events_have_deny
    )
    ux_ok = (
        str(distinct_row.get("survival_mode", "")) == "survival"
        and str(distinct_row.get("stage_hash_before", "")) != ""
        and str(distinct_row.get("stage_hash_before", "")) == str(distinct_row.get("stage_hash_after", ""))
        and kill_score_ok
        and roster_ok
        and cap_ok
        and events_have_spawn
        and bool(restart_row.get("lost", False))
        and bool(restart_row.get("cleared", False))
        and str(restart_row.get("death_cause", "")) == "damage"
        and not bool(restart_row.get("used_pit", True))
        and float(restart_row.get("bot_min_hp", 100.0)) < 99.5
        and bool(outcomes.get("pause", {}).get("pause_visible", False) if isinstance(outcomes.get("pause"), dict) else False)
        and bool(outcomes.get("pause", {}).get("captured_while_frozen", False) if isinstance(outcomes.get("pause"), dict) else False)
        and int(apply_info.get("used_force_kill", 1)) == 0
        and int(apply_info.get("used_teleport", 1)) == 0
        and int(apply_info.get("used_step_fixed", 1)) == 0
        and int(apply_info.get("used_apply_eval", 1)) == 0
        and events_ok
    )
    outcomes_ok = all(verdicts[key] == "pass" for key in keys) and ux_ok
    window_screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    required_stems = (
        "survival_title_",
        "survival_fight_",
        "survival_pause_",
        "survival_lose_",
        "survival_restart_",
        "survival_title_after_",
    )
    still_names = [png.name for png in window_screens]
    stills_ok = len(window_screens) >= 5 and all(
        any(name.startswith(stem) for name in still_names) for stem in required_stems
    )
    review.mkdir(parents=True, exist_ok=True)
    (review / "screens").mkdir(parents=True, exist_ok=True)
    for png in window_screens:
        if png.stat().st_size <= 0:
            stills_ok = False
            continue
        shutil.copy2(png, evidence / "screens" / png.name)
        shutil.copy2(png, review / "screens" / png.name)

    packed = {
        "schema": "vault-fighters.vf6-wp4.pack.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "packed_at": now_saigon(),
        "base_head": args.base_head,
        "source_tree_sha256": source_tree,
        "godot_sha256": godot_hash,
        "verdicts": verdicts,
        "score": score_row,
        "spawn": spawn_row,
        "distinct": distinct_row,
        "restart": restart_row,
        "leftover": leftover_proof,
        "exits": exits_proof,
        "live_logs_ok": live_logs_ok,
        "run_all_ok": run_all_ok,
        "soak_ok": soak_ok,
        "stills": [p.name for p in window_screens],
    }
    (evidence / "run.json").write_text(json.dumps(packed, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(window_outcomes_path, evidence / "outcomes.json")
    if (window_ev / "run_partial.json").is_file():
        shutil.copy2(window_ev / "run_partial.json", evidence / "run_partial.json")
    for extra_name in ("events.jsonl", "snapshot_start.json", "snapshot_end.json"):
        extra_path = window_ev / extra_name
        if extra_path.is_file():
            shutil.copy2(extra_path, evidence / extra_name)
            shutil.copy2(extra_path, review / extra_name)
    shutil.copy2(Path(args.freeze), evidence / "freeze.json")
    shutil.copy2(Path(args.leftover_proof), evidence / "leftover_proof.json")
    shutil.copy2(Path(args.exits_proof), evidence / "exits_proof.json")
    shutil.copy2(Path(args.headless_log), evidence / "official_headless.log")
    shutil.copy2(Path(args.window_log), evidence / "official_window.log")
    shutil.copy2(Path(args.run_all_log), evidence / "official_run_all.log")
    review.mkdir(parents=True, exist_ok=True)
    for name in (
        "run.json",
        "outcomes.json",
        "freeze.json",
        "leftover_proof.json",
        "exits_proof.json",
    ):
        if (evidence / name).is_file():
            shutil.copy2(evidence / name, review / name)
    verdict_ok = outcomes_ok and leftover_ok and exits_ok and live_logs_ok and run_all_ok and stills_ok
    verdict = (
        f"# VF6-WP4 verdict\n\n"
        f"RUN_ID={RUN_ID}\nCOMMAND_ID={COMMAND_ID}\n"
        f"SOURCE={source_tree}\n"
        f"SURVIVAL != Stage checkpoint; rematch clears director\n"
        f"SCORE {score_row.get('first')}→{score_row.get('last')} "
        f"kills={score_row.get('kills')} from_kills={score_row.get('score_from_kills')} "
        f"wave={score_row.get('last_wave')} "
        f"SPAWN max={spawn_row.get('max_living_bots')} cap={spawn_row.get('cap_living_bots')} "
        f"refused_cap={spawn_row.get('refused_cap')} deny={spawn_row.get('last_deny_reason')}\n"
        f"SOAK headless={headless_elapsed:.1f}s window={window_elapsed:.1f}s "
        f"(need {HEADLESS_SOAK}/{WINDOW_SOAK})\n"
        f"READY_FOR_CRITICS={'yes' if verdict_ok else 'no'}\n"
        f"29-8 still [ ]. Parent 59/60.\n"
    )
    (evidence / "verdict.md").write_text(verdict, encoding="utf-8")
    shutil.copy2(evidence / "verdict.md", review / "verdict.md")
    if not verdict_ok:
        print("FAIL: VF6-WP4 packer rejected official package")
        print(f"  outcomes_ok={outcomes_ok} leftover_ok={leftover_ok} exits_ok={exits_ok}")
        print(f"  live_logs_ok={live_logs_ok} run_all_ok={run_all_ok} stills_ok={stills_ok} soak_ok={soak_ok}")
        print(f"  kill_score_ok={kill_score_ok} roster_ok={roster_ok} cap_ok={cap_ok}")
        print(f"  parsed_h={parsed_h} parsed_w={parsed_w}")
        print(f"  headless_elapsed={headless_elapsed} window_elapsed={window_elapsed}")
        return 1
    print("PASS: VF6-WP4 evidence packed")
    print(f"RUN_ID={RUN_ID}")
    print(f"SOURCE_TREE={source_tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
