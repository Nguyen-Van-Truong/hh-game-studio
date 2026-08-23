#!/usr/bin/env python3
"""R7-WP4: Multi-agent scheduler + single mutation lane (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP4 [ ]; while unticked CURRENT_VALID_WP=R7-WP4; after tick allow R7-WP5+.
Must NOT lock [x] forever. Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable.
No skip-PASS. Does not start R7-WP5 or R8. Does not tick G4.
No snake demo. No R8 dogfood tree. No driver scripts for the snake demo.

Verify (encoded here; this file is the official harness):
  - 4 workers actually overlap in time (not sequential stamps)
  - lease expiry / crash releases the file so the next writer succeeds
  - same-file race: loser is E_LEASE/E_BUSY; winner content is not lost
  - independent-scene throughput: parallel non-mutate work is faster than the
    same corpus run serially (same cpuWork; do not sleep the serial path extra)
  - base-hash mismatch is conflict, not a green merge
  - LIVE path through real job.schedule (sidecar)

Labels: WORKERS4, LEASE_EXPIRY, CRASH, SAME_FILE, THROUGHPUT
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r7w4"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
ROLES = ("research", "code_staging", "asset_generation", "test_analysis")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP4 [ ]; while unticked require CURRENT_VALID_WP=R7-WP4."""
    errors: list[str] = []
    current = ""
    wp4 = None
    wp5 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP4\b", stripped):
            wp4 = stripped
        if re.match(r"^R7-WP5\b", stripped):
            wp5 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp4 is None:
        return ["plan missing R7-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R7-WP4 heading must keep [ ] until coordinator tick")
        if current != "R7-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP4 while WP4 is unticked)")
        if wp5 and re.search(r"\[x\]", wp5, re.IGNORECASE):
            errors.append("R7-WP5 must stay unticked; this WP does not start long-session soak")
    elif not re.match(r"^R7-WP([5-9]|\d{2,})$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP5+ after R7-WP4 tick)")
    if g4 is not None and re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("official harness must not tick G4")
    return errors


def _unlock_and_remove(func, path, _exc) -> None:
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def wipe_dir(folder: Path) -> None:
    if not folder.exists():
        return
    for child in folder.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                os.chmod(child, 0o700)
                child.unlink()
        except OSError:
            pass
    try:
        shutil.rmtree(folder, onexc=_unlock_and_remove)
    except TypeError:
        shutil.rmtree(folder, onerror=_unlock_and_remove)


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for _ in range(8):
        if not TEMP_DIR.exists():
            break
        wipe_dir(TEMP_DIR)
        time.sleep(0.25)
    if TEMP_DIR.exists():
        leftovers = [p.as_posix() for p in TEMP_DIR.rglob("*") if p.is_file()]
        if leftovers:
            errors.append(f"r7w4 leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in ("WORKERS4", "LEASE_EXPIRY", "CRASH", "SAME_FILE", "THROUGHPUT"):
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "No skip-PASS" not in self_text and "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "drive_" + "snake" in self_text:
        errors.append("official test must not include drive_" + "snake scripts")
    if "does not tick G4" not in self_text:
        errors.append("official test must refuse to tick G4")
    if "does not start R7-WP5" not in self_text:
        errors.append("official test must refuse to start R7-WP5")
    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r7w4/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r7w4/")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if 'p.contains("/r7w4' not in export_gd and 'p.contains("r7w4' not in export_gd:
        errors.append("export _should_skip must contain() r7w4")
    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "r7w4" not in constants:
        errors.append("hh_constants must name r7w4")
    adapter = ADDON / "core" / "hh_multi_agent_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_multi_agent_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        for role in ROLES:
            if role not in atext:
                errors.append(f"plugin adapter must name role {role}")
        if "r7w4" not in atext:
            errors.append("plugin adapter must jail under r7w4/")
        if ".tmp" not in atext:
            errors.append("plugin adapter must tmp+rename")
        if "base_hash" not in atext:
            errors.append("plugin adapter must merge by base_hash")
        if "E_LEASE" not in atext:
            errors.append("plugin adapter must use E_LEASE")
        if "coordinator" not in atext.lower() and "SCHED_COORDINATOR" not in atext:
            errors.append("plugin adapter must name coordinator ownership")
    machine = BRIDGE / "src" / "scheduler" / "machine.ts"
    workers = BRIDGE / "src" / "scheduler" / "workers.ts"
    leases = BRIDGE / "src" / "policy" / "leases.ts"
    if not machine.is_file():
        errors.append("missing scheduler/machine.ts")
    else:
        mtext = machine.read_text(encoding="utf-8")
        if "handleScheduleAction" not in mtext:
            errors.append("machine must export handleScheduleAction")
        if "dead_worker" not in mtext:
            errors.append("machine must implement crash holder / reap")
    if not workers.is_file():
        errors.append("missing scheduler/workers.ts")
    else:
        wtext = workers.read_text(encoding="utf-8")
        if "worker_threads" not in wtext and "Worker" not in wtext:
            errors.append("workers must use worker_threads")
        if "sleep" in wtext.lower() and "serial" in wtext.lower():
            if re.search(r"runThroughputSerial[\s\S]{0,400}sleep", wtext):
                errors.append("serial throughput must not insert sleep")
        for role in ROLES:
            if role not in wtext:
                errors.append(f"workers must name role {role}")
    if not leases.is_file():
        errors.append("missing leases.ts")
    else:
        ltext = leases.read_text(encoding="utf-8")
        if "heartbeat(" not in ltext:
            errors.append("LeaseTable must implement heartbeat")
        if "pidAlive" not in ltext:
            errors.append("file leases must reap dead pid (crash)")
        if "skipWriter" not in ltext:
            errors.append("file leases must allow per-file lock without project writer")
    store = BRIDGE / "src" / "scheduler" / "store.ts"
    if not store.is_file():
        errors.append("missing scheduler/store.ts")
    else:
        stext = store.read_text(encoding="utf-8")
        if "renameSync" not in stext:
            errors.append("store must tmp+rename")
        if ".hh-agent" not in stext:
            errors.append("store must refuse locked .hh-agent writes")
        if "generated" not in stext or "progress" not in stext:
            errors.append("store must name coordinator generated/progress")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_multi_agent_adapter" not in router:
        errors.append("router must dispatch job.schedule through multi-agent adapter")
    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
        if ("kho" + "-bi-an") in blob or ("/snake/") in blob.replace("\\", "/"):
            errors.append(f"{posix} mentions R8/snake trees")
    return errors


def start_sidecar() -> tuple[subprocess.Popen[str], Path, str, list[str]]:
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(PLUGIN_PROJECT)],
        cwd=str(BRIDGE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    err_lines: list[str] = []
    threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
    desc_path, desc = sess.find_descriptor(proc.pid)
    secret = str(desc.get("token") or "")
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-scheduler", "version": "0"},
                },
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    init_line = sess.readline_timeout(proc.stdout, 8.0)
    if "result" not in json.loads(init_line):
        raise RuntimeError(f"MCP initialize failed: {init_line}")
    return proc, desc_path, secret, err_lines


def stop_sidecar(proc: subprocess.Popen[str] | None, desc_path: Path | None) -> None:
    if proc is not None:
        life.stop_proc(proc)
    if desc_path and desc_path.is_file():
        try:
            desc_path.unlink()
        except OSError:
            pass
        lock = desc_path.with_name("sidecar.lock")
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def tool_job(
    proc: subprocess.Popen[str],
    req_id: int,
    action: str,
    params: dict,
    timeout: float = 60.0,
) -> tuple[int, dict]:
    return pin.tool_call(proc, req_id, "godot.job", action, params, timeout=timeout)


def after_of(body: dict) -> dict:
    return pin.after_of(body)


def err_code(body: dict) -> str:
    return pin.err_code(body)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return EMPTY_SHA256
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workers_overlap(stamps: list) -> bool:
    if len(stamps) < 4:
        return False
    starts = [int(row.get("started_at_ms") or 0) for row in stamps]
    ends = [int(row.get("ended_at_ms") or 0) for row in stamps]
    return max(starts) < min(ends)


def live_errors(exe: Path | None) -> tuple[list[str], str, str, str, str, str, str]:
    errors: list[str] = []
    live = "unrun"
    workers_l = "unproven"
    expiry_l = "unproven"
    crash_l = "unproven"
    same_l = "unproven"
    thru_l = "unproven"
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = start_sidecar()
        live = "sidecar"

        req_id, overlap = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "overlap1", "op": "run", "fixture": "overlap"},
            timeout=60.0,
        )
        ov = after_of(overlap)
        stamps = ov.get("workers") if isinstance(ov.get("workers"), list) else []
        roles = {str(row.get("role")) for row in stamps if isinstance(row, dict)}
        if overlap.get("ok") is not True:
            errors.append(f"WORKERS4 run failed: {sess.redact(json.dumps(overlap), secret)}")
        elif roles != set(ROLES):
            errors.append(f"WORKERS4 roles={roles}")
        elif not workers_overlap([row for row in stamps if isinstance(row, dict)]):
            errors.append(f"WORKERS4 stamps did not overlap: {stamps}")
        elif ov.get("overlap") is not True:
            errors.append("WORKERS4 after.overlap is not true")
        else:
            thread_ids = {int(row.get("thread_id") or 0) for row in stamps if isinstance(row, dict)}
            if len(thread_ids) < 4:
                errors.append(f"WORKERS4 need 4 distinct worker threads, got {thread_ids}")
            else:
                workers_l = "proven"
        req_id, dag = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "dag1", "op": "run", "fixture": "dag"},
            timeout=60.0,
        )
        dag_after = after_of(dag)
        dag_stamps = dag_after.get("workers") if isinstance(dag_after.get("workers"), list) else []
        by_role = {str(row.get("role")): row for row in dag_stamps if isinstance(row, dict)}
        if dag.get("ok") is not True or set(by_role) != set(ROLES):
            errors.append(f"WORKERS4 dag fixture failed: {sess.redact(json.dumps(dag), secret)}")
        else:
            research_end = int(by_role["research"].get("ended_at_ms") or 0)
            test_start = int(by_role["test_analysis"].get("started_at_ms") or 0)
            code_start = int(by_role["code_staging"].get("started_at_ms") or 0)
            if research_end > 0 and code_start > 0 and research_end > code_start:
                errors.append("WORKERS4 dag did not wait for research before code/assets")
            if test_start > 0 and research_end > 0 and test_start < research_end:
                errors.append("WORKERS4 dag ran test_analysis before research finished")
        req_id, status = tool_job(proc, req_id, "status", {"job_id": "overlap1"})
        if after_of(status).get("kind") != "scheduler" and after_of(status).get("overlap") is not True:
            if status.get("ok") is not True:
                errors.append(f"job.status scheduler miss: {sess.redact(json.dumps(status), secret)}")

        req_id, thru = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "thru1", "op": "run", "fixture": "throughput"},
            timeout=90.0,
        )
        th = after_of(thru)
        serial_ms = int(th.get("serial_ms") or 0)
        parallel_ms = int(th.get("parallel_ms") or 0)
        progress = th.get("progress") if isinstance(th.get("progress"), dict) else {}
        serial_d = progress.get("serial_digests") if isinstance(progress.get("serial_digests"), list) else []
        parallel_d = progress.get("parallel_digests") if isinstance(progress.get("parallel_digests"), list) else []
        if thru.get("ok") is not True:
            errors.append(f"THROUGHPUT run failed: {sess.redact(json.dumps(thru), secret)}")
        elif serial_ms <= 0 or parallel_ms <= 0:
            errors.append(f"THROUGHPUT missing times serial={serial_ms} parallel={parallel_ms}")
        elif parallel_ms >= serial_ms:
            errors.append(f"THROUGHPUT parallel {parallel_ms}ms not faster than serial {serial_ms}ms")
        elif not serial_d or not parallel_d:
            errors.append("THROUGHPUT missing corpus digests")
        elif serial_d != parallel_d:
            errors.append("THROUGHPUT serial/parallel digests differ — not the same corpus")
        else:
            thru_l = "proven"

        req_id, crash = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "crash1", "op": "run", "fixture": "crash"},
            timeout=30.0,
        )
        cr = after_of(crash)
        crp = cr.get("progress") if isinstance(cr.get("progress"), dict) else {}
        if crash.get("ok") is not True:
            errors.append(f"CRASH run failed: {sess.redact(json.dumps(crash), secret)}")
        elif crp.get("released") is not True:
            errors.append(f"CRASH next writer did not acquire: {crp}")
        elif crp.get("crashed_alive") is True:
            errors.append("CRASH holder pid still alive")
        elif crp.get("prior_writer") != "dead_worker":
            errors.append(f"CRASH prior_writer={crp.get('prior_writer')!r} (need dead_worker)")
        else:
            crash_l = "proven"

        race_rel = "res://r7w4/race1/same.txt"
        race_abs = TEMP_DIR / "race1" / "same.txt"
        req_id, seed = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "race1",
                "op": "merge",
                "writer_id": "coordinator",
                "path": race_rel,
                "base_hash": EMPTY_SHA256,
                "contents": "SEED\n",
            },
        )
        if seed.get("ok") is not True:
            errors.append(f"SAME_FILE seed merge failed: {sess.redact(json.dumps(seed), secret)}")
        req_id, _rel_seed = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "race1", "op": "release", "writer_id": "coordinator", "path": race_rel},
        )
        seed_hash = sha256_file(race_abs)
        req_id, hold = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "race1", "op": "lease", "writer_id": "writer_a", "path": race_rel, "ttl_ms": 30000},
        )
        if hold.get("ok") is not True:
            errors.append(f"SAME_FILE writer_a lease failed: {sess.redact(json.dumps(hold), secret)}")
        req_id, loser = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "race1", "op": "lease", "writer_id": "writer_b", "path": race_rel, "ttl_ms": 30000},
        )
        loser_code = err_code(loser)
        if loser.get("ok") is True:
            errors.append("SAME_FILE second writer was allowed to take the lease")
        elif loser_code not in {"E_LEASE", "E_BUSY"}:
            errors.append(f"SAME_FILE loser code={loser_code!r} (need E_LEASE/E_BUSY)")
        req_id, win = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "race1",
                "op": "merge",
                "writer_id": "writer_a",
                "path": race_rel,
                "base_hash": seed_hash,
                "contents": "WINNER-A\n",
            },
        )
        if win.get("ok") is not True:
            errors.append(f"SAME_FILE winner merge failed: {sess.redact(json.dumps(win), secret)}")
        req_id, lose_merge = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "race1",
                "op": "merge",
                "writer_id": "writer_b",
                "path": race_rel,
                "base_hash": seed_hash,
                "contents": "LOSER-B\n",
            },
        )
        lose_merge_code = err_code(lose_merge)
        text = race_abs.read_text(encoding="utf-8") if race_abs.is_file() else ""
        if "WINNER-A" not in text:
            errors.append(f"SAME_FILE winner content lost: {text!r}")
        if "LOSER-B" in text:
            errors.append("SAME_FILE silent overwrite by loser")
        if lose_merge.get("ok") is True:
            errors.append("SAME_FILE loser merge was green")
        elif lose_merge_code not in {"E_LEASE", "E_BUSY", "E_CONFLICT"}:
            errors.append(f"SAME_FILE loser merge code={lose_merge_code!r}")
        elif hold.get("ok") is True and win.get("ok") is True and "WINNER-A" in text:
            same_l = "proven"

        exp_rel = "res://r7w4/exp1/ttl.txt"
        req_id, exp_seed = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "exp1",
                "op": "merge",
                "writer_id": "coordinator",
                "path": exp_rel,
                "base_hash": EMPTY_SHA256,
                "contents": "TTL\n",
            },
        )
        if exp_seed.get("ok") is not True:
            errors.append(f"LEASE_EXPIRY seed failed: {sess.redact(json.dumps(exp_seed), secret)}")
        req_id, _rel_exp = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "exp1", "op": "release", "writer_id": "coordinator", "path": exp_rel},
        )
        req_id, first = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "exp1", "op": "lease", "writer_id": "expiring", "path": exp_rel, "ttl_ms": 250},
        )
        if first.get("ok") is not True:
            errors.append(f"LEASE_EXPIRY first lease failed: {sess.redact(json.dumps(first), secret)}")
        time.sleep(0.55)
        req_id, second = tool_job(
            proc,
            req_id,
            "schedule",
            {"job_id": "exp1", "op": "lease", "writer_id": "successor", "path": exp_rel, "ttl_ms": 5000},
        )
        if second.get("ok") is not True:
            errors.append(f"LEASE_EXPIRY successor failed: {sess.redact(json.dumps(second), secret)}")
        elif after_of(second).get("lease", {}).get("writer_id") != "successor":
            errors.append(f"LEASE_EXPIRY successor lease={after_of(second)}")
        else:
            expiry_l = "proven"

        bad_rel = "res://r7w4/conf1/code.gd"
        req_id, made = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "conf1",
                "op": "merge",
                "writer_id": "coordinator",
                "path": bad_rel,
                "base_hash": EMPTY_SHA256,
                "contents": "var n := 1\n",
            },
        )
        if made.get("ok") is not True:
            errors.append(f"conflict seed failed: {sess.redact(json.dumps(made), secret)}")
        before = (TEMP_DIR / "conf1" / "code.gd").read_text(encoding="utf-8") if (TEMP_DIR / "conf1" / "code.gd").is_file() else ""
        req_id, propose = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "conf1",
                "op": "propose",
                "writer_id": "code_staging",
                "role": "code_staging",
                "path": bad_rel,
                "base_hash": "aaaaaaaa",
                "contents": "var n := 99\n",
            },
        )
        if propose.get("ok") is not True:
            errors.append(f"propose failed: {sess.redact(json.dumps(propose), secret)}")
        req_id, conflict = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "conf1",
                "op": "merge",
                "writer_id": "coordinator",
                "path": bad_rel,
                "base_hash": "bbbbbbbb",
                "contents": "var n := 99\n",
            },
        )
        after_txt = (TEMP_DIR / "conf1" / "code.gd").read_text(encoding="utf-8") if (TEMP_DIR / "conf1" / "code.gd").is_file() else ""
        if conflict.get("ok") is True:
            errors.append("base-hash mismatch was green-merged")
        elif err_code(conflict) != "E_CONFLICT":
            errors.append(f"base-hash mismatch code={err_code(conflict)!r} (need E_CONFLICT)")
        elif after_txt != before:
            errors.append("conflict merge mutated the file")
        gen_rel = "res://r7w4/conf1/generated/stolen.json"
        req_id, stolen = tool_job(
            proc,
            req_id,
            "schedule",
            {
                "job_id": "conf1",
                "op": "merge",
                "writer_id": "code_staging",
                "path": gen_rel,
                "base_hash": EMPTY_SHA256,
                "contents": "{\"stolen\":true}\n",
            },
        )
        if stolen.get("ok") is True:
            errors.append("worker merged into coordinator generated/ (must propose)")
        elif err_code(stolen) != "E_POLICY":
            errors.append(f"coordinator-owned write code={err_code(stolen)!r} (need E_POLICY)")

        if exe is not None and not pin.plugin_godot_busy():
            godot, godot_lines = pin.start_godot(exe, headless=True)
            req_id, hello, last = life.wait_hello(proc, godot, req_id)
            if not hello:
                errors.append(
                    "GODOT_LANE hello failed: "
                    f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-800:]}"
                )
            else:
                req_id, hold_lane = tool_job(
                    proc, req_id, "schedule", {"job_id": "lane1", "op": "hold_lane", "writer_id": "coordinator"}
                )
                if hold_lane.get("ok") is not True:
                    errors.append(f"GODOT_LANE hold failed: {sess.redact(json.dumps(hold_lane), secret)}")
                req_id, blocked = pin.tool_call(
                    proc,
                    req_id,
                    "godot.scene",
                    "create",
                    {"path": "res://r7w4/lane1/Root.tscn", "root_class": "Node2D"},
                    timeout=20.0,
                )
                if err_code(blocked) != "E_BUSY":
                    errors.append(f"GODOT_LANE scene.create must be E_BUSY while held, got {blocked}")
                req_id, _rel_lane = tool_job(proc, req_id, "schedule", {"job_id": "lane1", "op": "release_lane"})
                req_id, created = pin.tool_call(
                    proc,
                    req_id,
                    "godot.scene",
                    "create",
                    {"path": "res://r7w4/lane1/Root.tscn", "root_class": "Node2D"},
                    timeout=20.0,
                )
                if created.get("ok") is not True:
                    errors.append(f"GODOT_LANE scene.create after release failed: {created}")
                else:
                    live = "plugin"
            life.stop_proc(godot)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live scheduler failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        stop_sidecar(proc, desc_path)
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        errors.extend(pin.project_godot_leak_errors("after live"))
    return errors, live, workers_l, expiry_l, crash_l, same_l, thru_l


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    built = subprocess.run(
        [npm(), "run", "generate"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge generate failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    spec = actions.get("job.schedule") if isinstance(actions.get("job.schedule"), dict) else {}
    if spec.get("method") != "godot.job":
        errors.append("actions.json missing job.schedule")

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    errors.extend(cleanup_temp())
    live = "unrun"
    workers_l = expiry_l = crash_l = same_l = thru_l = "unproven"
    if not any("bridge generate failed" in e for e in errors):
        live_errs, live, workers_l, expiry_l, crash_l, same_l, thru_l = live_errors(exe)
        errors.extend(live_errs)

    if workers_l != "proven":
        errors.append("WORKERS4 not proven")
    if expiry_l != "proven":
        errors.append("LEASE_EXPIRY not proven")
    if crash_l != "proven":
        errors.append("CRASH not proven")
    if same_l != "proven":
        errors.append("SAME_FILE not proven")
    if thru_l != "proven":
        errors.append("THROUGHPUT not proven")
    if live not in {"sidecar", "plugin"}:
        errors.append("LIVE path through real job.schedule is required (src_scan is not enough)")

    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.5)
    errors.extend(cleanup_temp())
    banner = (
        f"LIVE={live}; WORKERS4={workers_l}; LEASE_EXPIRY={expiry_l}; "
        f"CRASH={crash_l}; SAME_FILE={same_l}; THROUGHPUT={thru_l}"
    )
    if errors:
        print(f"FAIL: scheduler; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: scheduler; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
