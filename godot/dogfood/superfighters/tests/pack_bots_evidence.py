#!/usr/bin/env python3
"""Assemble VF6-WP5 evidence after official bot planner runs.

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

RUN_ID = "VF6WP5-20260904-ASIA-SAIGON-08"
COMMAND_ID = "cmd.vf6-wp5.bots.8"
WP = "VF6-WP5"
SAIGON = timezone(timedelta(hours=7))
SOURCE_SUFFIXES = {".gd", ".json", ".tscn", ".md"}
SOURCE_ROOTS = ("src", "data", "scenes")
SOURCE_EXTRA = (
    "tests/bot_cases.gd",
    "tests/run_bots.gd",
    "tests/check_bots.py",
    "tests/pack_bots_evidence.py",
    "tests/run_bots_official.ps1",
    "tests/run_all.gd",
    "tests/survival_cases.gd",
    "tests/stage_cases.gd",
    "tests/match_cases.gd",
    "docs/bots.md",
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
    prefix = "HH_VF_BOTS EVIDENCE_DIR="
    for line in log_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :]
    return ""


def now_saigon() -> str:
    return datetime.now(SAIGON).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def outcome_verdict(outcomes: dict, key: str) -> str:
    row = outcomes.get(key, {})
    if isinstance(row, dict):
        return str(row.get("verdict", "unproven"))
    return "unproven"


def log_unclean(text: str) -> bool:
    """Log cleanliness only. Never a host exit. Host exit is leftover_proof WaitForExit."""
    lowered = text.lower()
    if "hh_assert_fail" in lowered or "status=unproven" in lowered:
        return True
    if any(token in lowered for token in ("warning:", "error:", "script warning", "parse error")):
        return True
    if "FAIL: Vault Fighters" in text:
        return True
    return False


def _copy_if_different(src: Path, dst: Path) -> None:
    if not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    shutil.copy2(src, dst)


def write_freeze(product: Path, dest: Path) -> str:
    source_sha = {}
    for rel in iter_source_files(product):
        path = product / rel
        if path.is_file():
            source_sha[rel] = sha256_file(path)
    manifest_lines = [f"{digest}  {rel}" for rel, digest in sorted(source_sha.items())]
    source_tree = sha256_text("\n".join(manifest_lines) + "\n")
    payload = {
        "schema": "vault-fighters.freeze.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "frozen_at": now_saigon(),
        "file_count": len(source_sha),
        "source_tree_sha256": source_tree,
        "files": source_sha,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return source_tree


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
    parser.add_argument("--write-freeze", action="store_true")
    args = parser.parse_args()

    product = Path(args.product)
    evidence = Path(args.evidence)
    review = Path(args.review)
    headless_ev = Path(args.headless_evidence)
    window_ev = Path(args.window_evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "screens").mkdir(parents=True, exist_ok=True)

    if args.write_freeze:
        tree = write_freeze(product, Path(args.freeze))
        print(f"FREEZE {tree}")
        return 0

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

    keys = ("schema", "maps", "weapons", "finish", "greedy", "recover", "diff", "bound", "live")
    verdicts = {key: outcome_verdict(outcomes, key) for key in keys}
    apply_info = outcomes.get("apply", {})
    maps_row = outcomes.get("maps", {}) if isinstance(outcomes.get("maps"), dict) else {}
    weapons_row = outcomes.get("weapons", {}) if isinstance(outcomes.get("weapons"), dict) else {}
    finish_row = outcomes.get("finish", {}) if isinstance(outcomes.get("finish"), dict) else {}
    headless_log_text = Path(args.headless_log).read_text(encoding="utf-8", errors="replace") if Path(args.headless_log).is_file() else ""
    window_log_text = Path(args.window_log).read_text(encoding="utf-8", errors="replace") if Path(args.window_log).is_file() else ""
    run_all_log_text = Path(args.run_all_log).read_text(encoding="utf-8", errors="replace") if Path(args.run_all_log).is_file() else ""
    parsed_h = None
    parsed_w = None
    logs_unclean = log_unclean(headless_log_text) or log_unclean(window_log_text)
    dive_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_DIVE ")), "")
    vs_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS ") and "ROSTER=" in ln), "")
    match_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_MATCH ") and "MACHINE=" in ln), "")
    flow_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_VS2 ") and "FIRST=" in ln), "")
    stage_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_STAGE ") and "ADVANCE=" in ln), "")
    survival_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_SURVIVAL ") and "SCORE=" in ln), "")
    bots_banner = next((ln for ln in run_all_log_text.splitlines() if ln.startswith("HH_VF_BOTS ") and "MAPS=" in ln), "")
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
        and "MAPS=pass" in bots_banner
        and "GREEDY=pass" in bots_banner
        and "RECOVER=pass" in bots_banner
        and "status=proven" in bots_banner
        and "HH_VF_ALL FINISHED=1" in run_all_log_text
        and "PASS: Vault Fighters first playable" in run_all_log_text
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
        and int(_field(headless_log_text, "HH_VF_BOTS ", "USED_FORCE_KILL") or "1") == 0
        and int(_field(window_log_text, "HH_VF_BOTS ", "USED_FORCE_KILL") or "1") == 0
        and _field(headless_log_text, "HH_VF_BOTS HONESTY ", "NOT_AI") == "0"
        and _field(window_log_text, "HH_VF_BOTS HONESTY ", "BOT_COVERAGE") == "planner"
    )
    after_h = int(leftover_proof.get("after_headless", -1))
    after_w = int(leftover_proof.get("after_window", -1))
    after_a = int(leftover_proof.get("after_run_all", -1))
    leftover_computed = max(after_h, after_w, after_a)
    host_h = int(leftover_proof.get("headless_host_exit", -1))
    host_w = int(leftover_proof.get("window_host_exit", -1))
    host_a = int(leftover_proof.get("run_all_host_exit", -1))
    leftover_path = str(leftover_proof.get("counted_product_path") or leftover_proof.get("path") or "")
    leftover_host = str(leftover_proof.get("host", "")).lower()
    leftover_ok = (
        leftover_proof
        and leftover_computed == 0
        and leftover_computed == int(leftover_proof.get("leftover", -1))
        and leftover_computed == args.leftover
        and after_h == 0
        and after_w == 0
        and after_a == 0
        and "superfighters" in leftover_path.replace("\\", "/").lower()
        and str(leftover_proof.get("scan", "")) != ""
        and "waitforexit" in leftover_host
        and "console" in str(leftover_proof.get("window_exe", "")).lower()
        and host_h == 0
        and host_w == 0
        and host_a == 0
        and not logs_unclean
    )
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
        and host_h == 0
        and host_w == 0
        and host_a == 0
        and not log_unclean(run_all_log_text)
    )
    rows = maps_row.get("rows", {})
    if not isinstance(rows, dict):
        rows = {}
    six = ("rooftops", "storage", "police", "hazardous", "lantern", "gauge")

    LIP_ENGAGE_LO = 71.0
    LIP_ENGAGE_HI = 72.0

    def honest_reach(row: dict) -> bool:
        if bool(row.get("dead", False)):
            return False
        if float(row.get("goal_dist", 9999.0)) < 36.0:
            return True
        if float(row.get("engage_dist", 9999.0)) < 48.0:
            return True
        return bool(row.get("named_down", False)) and float(row.get("closest_engage", 9999.0)) < 48.0

    missing_maps = [mid for mid in six if not isinstance(rows.get(mid), dict)]
    if missing_maps:
        print("FAIL: packer missing map rows " + ",".join(missing_maps))
        return 1
    if "HH_VF_BOTS STEP=maps compact" in run_all_log_text or "HH_VF_BOTS_COMPACT=1" in run_all_log_text:
        print("FAIL: official run_all must not run HH_VF_BOTS_COMPACT=1")
        return 1
    lip_only = 0
    for mid in six:
        row = rows[mid]
        eng = float(row.get("engage_dist", 9999.0))
        if (
            str(row.get("reach_reason", "")) == "engage"
            and LIP_ENGAGE_LO <= eng < LIP_ENGAGE_HI
            and float(row.get("goal_dist", 9999.0)) >= 36.0
        ):
            lip_only += 1
    if lip_only >= 3:
        print(f"FAIL: engage in [71,72) as sole reach on {lip_only} maps")
        return 1
    six_ok = all(
        honest_reach(rows[mid])
        and bool(rows[mid].get("pit_ok"))
        and bool(rows[mid].get("aim_ok"))
        and bool(rows[mid].get("combat_ok"))
        and int(rows[mid].get("gun_used", 0)) + int(rows[mid].get("melee_used", 0)) > 0
        for mid in six
    )
    rooftops = rows.get("rooftops", {}) if isinstance(rows.get("rooftops"), dict) else {}
    rooftops_ok = honest_reach(rooftops) and (
        int(rooftops.get("gun_used", 0)) + int(rooftops.get("melee_used", 0)) > 0
    ) and (
        float(rooftops.get("goal_dist", 9999.0)) < 36.0
        or float(rooftops.get("waypoint_dist", 9999.0)) < 48.0
        or int(rooftops.get("pit_reroutes", 0)) >= 1
        or (
            float(rooftops.get("engage_dist", 9999.0)) < 48.0
            and float(rooftops.get("moved", 0.0)) >= 200.0
        )
    )
    ux_ok = (
        six_ok
        and rooftops_ok
        and int(weapons_row.get("classes", 0)) >= 2
        and int(weapons_row.get("gun_used", 0)) >= 1
        and (
            int(weapons_row.get("melee_used", 0)) >= 1
            or bool(weapons_row.get("nade_combat", False))
        )
        and str(finish_row.get("outcome", "play")) != "play"
        and int(finish_row.get("fighter_count", 0)) == 2
        and int(finish_row.get("spawned_count", 0)) == 2
        and int(finish_row.get("culled", 1)) == 0
        and int(finish_row.get("living", 0)) == 1
        and int(finish_row.get("unused_spawns", 1)) == 0
        and int(finish_row.get("pit_deaths", 1)) == 0
        and int(finish_row.get("damage_deaths", 0)) >= 1
        and int(finish_row.get("winner_shots", 0)) + int(finish_row.get("winner_melee", 0)) >= 1
        and float(finish_row.get("winner_moved", 0.0)) >= 16.0
        and int(apply_info.get("used_force_kill", 1)) == 0
        and int(apply_info.get("used_teleport", 1)) == 0
        and int(apply_info.get("used_apply_eval", 1)) == 0
    )
    outcomes_ok = all(verdicts[key] == "pass" for key in keys) and ux_ok
    window_screens = list((window_ev / "screens").glob("*.png")) if (window_ev / "screens").is_dir() else []
    required_stems = ("bots_title_", "bots_fight_")
    still_names = [png.name for png in window_screens]
    stills_ok = len(window_screens) >= 2 and all(
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
        "schema": "vault-fighters.vf6-wp5.pack.v1",
        "run_id": RUN_ID,
        "command_id": COMMAND_ID,
        "wp": WP,
        "packed_at": now_saigon(),
        "base_head": args.base_head,
        "source_tree_sha256": source_tree,
        "godot_sha256": godot_hash,
        "verdicts": verdicts,
        "maps": maps_row,
        "weapons": weapons_row,
        "finish": finish_row,
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
    for extra_name in ("events.jsonl", "snapshot_start.json", "snapshot_end.json"):
        extra_path = window_ev / extra_name
        if extra_path.is_file():
            shutil.copy2(extra_path, evidence / extra_name)
            shutil.copy2(extra_path, review / extra_name)
    _copy_if_different(Path(args.freeze), evidence / "freeze.json")
    _copy_if_different(Path(args.leftover_proof), evidence / "leftover_proof.json")
    _copy_if_different(Path(args.exits_proof), evidence / "exits_proof.json")
    shutil.copy2(Path(args.headless_log), evidence / "official_headless.log")
    shutil.copy2(Path(args.window_log), evidence / "official_window.log")
    shutil.copy2(Path(args.run_all_log), evidence / "official_run_all.log")
    for name in (
        "run.json",
        "outcomes.json",
        "freeze.json",
        "leftover_proof.json",
        "exits_proof.json",
    ):
        if (evidence / name).is_file():
            shutil.copy2(evidence / name, review / name)
    leftover_computed = leftover_computed
    verdict_ok = outcomes_ok and leftover_ok and exits_ok and live_logs_ok and run_all_ok and stills_ok
    verdict = (
        f"# VF6-WP5 verdict\n\n"
        f"RUN_ID={RUN_ID}\nCOMMAND_ID={COMMAND_ID}\n"
        f"SOURCE={source_tree}\n"
        f"PLANNER live; NOT_AI=0 on official bot harness only\n"
        f"WEAPONS classes={weapons_row.get('classes')} perfect_aim={weapons_row.get('perfect_aim_shots')}\n"
        f"FINISH outcome={finish_row.get('outcome')} pit_deaths={finish_row.get('pit_deaths')}\n"
        f"READY_FOR_CRITICS={'yes' if verdict_ok else 'no'}\n"
        f"29-8 still [ ]. Parent 59/60.\n"
    )
    (evidence / "verdict.md").write_text(verdict, encoding="utf-8")
    shutil.copy2(evidence / "verdict.md", review / "verdict.md")
    if not verdict_ok:
        print("FAIL: VF6-WP5 packer rejected official package")
        print(f"  outcomes_ok={outcomes_ok} leftover_ok={leftover_ok} exits_ok={exits_ok}")
        print(f"  live_logs_ok={live_logs_ok} run_all_ok={run_all_ok} stills_ok={stills_ok}")
        print(f"  six_ok={six_ok} logs_unclean={logs_unclean}")
        return 1
    print("PASS: VF6-WP5 evidence packed")
    print(f"RUN_ID={RUN_ID}")
    print(f"SOURCE_TREE={source_tree}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
