#!/usr/bin/env python3
"""Assemble VF6-WP2 evidence after official vs-flow runs.

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

RUN_ID = "VF6WP2-20260901-ASIA-SAIGON-03"
COMMAND_ID = "cmd.vf6-wp2.vs-flow.3"
WP = "VF6-WP2"
SAIGON = timezone(timedelta(hours=7))
SOURCE_SUFFIXES = {".gd", ".json", ".tscn", ".md"}
SOURCE_ROOTS = ("src", "data", "scenes")
SOURCE_EXTRA = (
    "tests/vs_flow_cases.gd",
    "tests/run_vs_flow.gd",
    "tests/check_vs_flow.py",
    "tests/pack_vs_flow_evidence.py",
    "tests/run_all.gd",
    "tests/match_cases.gd",
    "docs/vs_flow.md",
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
    prefix = "HH_VF_VS2 EVIDENCE_DIR="
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
    if "FAIL: Vault Fighters vs production flow" in text:
        return 1
    if "HH_VF_VS2 FINISHED=1" in text and "HH_VF_VS2 PROCESS_EXIT=0" in text:
        return 0
    if "HH_VF_VS2 FINISHED=1" in text and "HH_VF_VS2 PROCESS_EXIT=1" in text:
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

    keys = ("schema", "first", "ready", "leak", "play", "rematch", "overlay", "feedback", "live")
    verdicts = {key: outcome_verdict(outcomes, key) for key in keys}
    apply_info = outcomes.get("apply", {})
    first_row = outcomes.get("first", {}) if isinstance(outcomes.get("first"), dict) else {}
    rematch_row = outcomes.get("rematch", {}) if isinstance(outcomes.get("rematch"), dict) else {}
    leak_row = outcomes.get("leak", {}) if isinstance(outcomes.get("leak"), dict) else {}
    play_row = outcomes.get("play", {}) if isinstance(outcomes.get("play"), dict) else {}
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    parsed_h = parse_exit_from_log(headless_log_text)
    parsed_w = parse_exit_from_log(window_log_text)
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    vs_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS ") and "ROSTER=" in ln), "")
    match_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_MATCH ") and "MACHINE=" in ln), "")
    flow_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS2 ") and "FIRST=" in ln), "")
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
        and int(_field(headless_log_text, "HH_VF_VS2 ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(window_log_text, "HH_VF_VS2 ", "USED_STEP_FIXED") or "1") == 0
        and int(_field(headless_log_text, "HH_VF_VS2 ", "USED_FORCE_KILL") or "1") == 0
        and int(_field(window_log_text, "HH_VF_VS2 ", "USED_FORCE_KILL") or "1") == 0
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
        and parsed_h == 0
        and parsed_w == 0
    )
    ux_ok = (
        int(first_row.get("vs1_actions", 99)) <= 3
        and int(first_row.get("vs2_actions", 99)) <= 3
        and float(first_row.get("vs1_seconds", 99.0)) <= 30.0
        and float(first_row.get("vs2_seconds", 99.0)) <= 30.0
        and int(rematch_row.get("actions", 99)) <= 2
        and float(rematch_row.get("seconds", 99.0)) <= 5.0
        and bool(leak_row.get("p1_moved", False))
        and bool(leak_row.get("p2_still_on_p1", False))
        and bool(leak_row.get("p2_moved", False))
        and bool(leak_row.get("p1_still_on_p2", False))
        and int(apply_info.get("used_force_kill", 1)) == 0
        and int(apply_info.get("used_teleport", 1)) == 0
        and int(apply_info.get("used_step_fixed", 1)) == 0
        and bool(play_row.get("moved", False))
        and bool(play_row.get("died", False))
        and bool(play_row.get("p1_moved", False))
        and bool(play_row.get("p2_moved", False))
        and bool(play_row.get("p1_attacked", False))
        and bool(play_row.get("p2_attacked", False))
        and bool(play_row.get("hit_landed", False))
        and str(play_row.get("death_cause", "")) == "damage"
        and str(play_row.get("map_id", "")) == "fx_melee_close"
        and int(play_row.get("used_pit_fallback", 1)) == 0
        and str(play_row.get("death_cause", "")) != "pit"
    )
    outcomes_ok = all(verdicts[key] == "pass" for key in keys) and ux_ok
    window_screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    required_stems = (
        "vs_flow_title_",
        "vs_flow_lobby_",
        "vs_flow_fight_",
        "vs_flow_result_",
        "vs_flow_rematch_",
        "vs_flow_title_after_",
    )
    still_names = [png.name for png in window_screens]
    stills_ok = len(window_screens) >= 6 and all(
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
        "schema": "vault-fighters.vf6-wp2.pack.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "packed_at": now_saigon(),
        "base_head": args.base_head,
        "source_tree_sha256": source_tree,
        "godot_sha256": godot_hash,
        "verdicts": verdicts,
        "first": first_row,
        "rematch": rematch_row,
        "leak": leak_row,
        "leftover": leftover_proof,
        "exits": exits_proof,
        "live_logs_ok": live_logs_ok,
        "run_all_ok": run_all_ok,
        "stills": [p.name for p in window_screens],
    }
    (evidence / "run.json").write_text(json.dumps(packed, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(window_outcomes_path, evidence / "outcomes.json")
    if (window_ev / "run_partial.json").is_file():
        shutil.copy2(window_ev / "run_partial.json", evidence / "run_partial.json")
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
        f"# VF6-WP2 verdict\n\n"
        f"RUN_ID={RUN_ID}\nCOMMAND_ID={COMMAND_ID}\n"
        f"SOURCE={source_tree}\n"
        f"FIRST vs1={first_row.get('vs1_actions')}a/{first_row.get('vs1_seconds')}s "
        f"vs2={first_row.get('vs2_actions')}a/{first_row.get('vs2_seconds')}s\n"
        f"REMATCH={rematch_row.get('actions')}a/{rematch_row.get('seconds')}s\n"
        f"LEAK={verdicts.get('leak')} PLAY={verdicts.get('play')} "
        f"MAP={play_row.get('map_id')} DEATH={play_row.get('death_cause')}\n"
        f"READY_FOR_CRITICS={'yes' if verdict_ok else 'no'}\n"
        f"29-8 still [ ]. Parent 59/60.\n"
    )
    (evidence / "verdict.md").write_text(verdict, encoding="utf-8")
    shutil.copy2(evidence / "verdict.md", review / "verdict.md")
    if not verdict_ok:
        print("FAIL: VF6-WP2 packer rejected official package")
        print(f"  outcomes_ok={outcomes_ok} leftover_ok={leftover_ok} exits_ok={exits_ok}")
        print(f"  live_logs_ok={live_logs_ok} run_all_ok={run_all_ok} stills_ok={stills_ok}")
        print(f"  parsed_h={parsed_h} parsed_w={parsed_w}")
        return 1
    print("PASS: VF6-WP2 evidence packed")
    print(f"RUN_ID={RUN_ID}")
    print(f"SOURCE_TREE={source_tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
