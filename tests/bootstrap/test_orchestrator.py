#!/usr/bin/env python3
"""R7-WP2: Orchestrator state machine + bounded repair (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP2 [ ]; while unticked CURRENT_VALID_WP=R7-WP2; after tick allow R7-WP3+.
Must NOT lock [x] forever. Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable.
No skip-PASS. Does not start R7-WP3 or R8. Does not tick G4.
No snake demo. No R8 dogfood tree. No driver scripts for the snake demo.

Verify (encoded here; this file is the official harness):
  - kill/restart every state (inspect→plan→checkpoint→execute→verify→repair→review-ready)
  - dependency fail and cancel leave blocked/cancelled, not green done
  - infinite-repair fixture is blocked at the 4th same-error (not another silent patch)
  - resume after kill loads flushed state, continues the current task, does not replay ACKed commands
  - pause can stop the loop (A14)

Labels: KILL_RESTART, DEP_FAIL, CANCEL, REPAIR_CAP, RESUME
"""

from __future__ import annotations

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
TEMP_DIR = PLUGIN_PROJECT / "r7w2"
HARNESS = BRIDGE / "dist" / "orchestrator" / "harness.js"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
HOLD_STATES = ("inspect", "plan", "checkpoint", "execute", "verify", "repair", "review-ready")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP2 [ ]; while unticked require CURRENT_VALID_WP=R7-WP2."""
    errors: list[str] = []
    current = ""
    wp2 = None
    wp3 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP2\b", stripped):
            wp2 = stripped
        if re.match(r"^R7-WP3\b", stripped):
            wp3 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp2 is None:
        return ["plan missing R7-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R7-WP2 heading must keep [ ] until coordinator tick")
        if current != "R7-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP2 while WP2 is unticked)")
        if wp3 and re.search(r"\[x\]", wp3, re.IGNORECASE):
            errors.append("R7-WP3 must stay unticked; this WP does not start Git checkpoint")
    elif not re.match(r"^R7-WP([3-9]|\d{2,})$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP3+ after R7-WP2 tick)")
    if g4 is not None and re.search(r"\[x\]", g4, re.IGNORECASE):
        errors.append("official harness must not tick G4")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for folder in (TEMP_DIR,):
        for _ in range(6):
            if not folder.exists():
                break
            shutil.rmtree(folder, ignore_errors=True)
            time.sleep(0.2)
        if folder.exists():
            leftovers = [p.as_posix() for p in folder.rglob("*") if p.is_file()]
            if leftovers:
                errors.append(f"r7w2 leftover after cleanup: {leftovers[:8]}")
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
    for label in ("KILL_RESTART", "DEP_FAIL", "CANCEL", "REPAIR_CAP", "RESUME"):
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
    if '"--wait"' not in self_text and "'--wait'" not in self_text:
        errors.append("official test must invoke job.wait")
    if "stop_proc" not in self_text or "live-kill-exec" not in self_text:
        errors.append("official test must kill/restart Godot for at least execute")

    adapter = ADDON / "core" / "hh_orchestrator_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_orchestrator_adapter.gd")
    else:
        text = adapter.read_text(encoding="utf-8")
        if "illegal transition" not in text:
            errors.append("plugin orchestrator must name illegal transition")
        if "repair_cap" not in text:
            errors.append("plugin orchestrator must name repair_cap")
        if "r7w2/" not in text:
            errors.append("plugin orchestrator must jail under r7w2/")
        if ".tmp" not in text:
            errors.append("plugin orchestrator must tmp+rename")
        if "committed_command_ids" not in text:
            errors.append("plugin orchestrator must skip committed command_ids")
    machine = BRIDGE / "src" / "orchestrator" / "machine.ts"
    if not machine.is_file():
        errors.append("missing machine.ts")
    else:
        mtext = machine.read_text(encoding="utf-8")
        if "canTransition" not in mtext:
            errors.append("machine must type-check transitions")
        if "ORCH_MAX_SAME_REPAIR" not in mtext:
            errors.append("machine must cap same-error repair")
        if "committed_command_ids" not in mtext:
            errors.append("machine must skip ACKed command_ids")
        if "E_PAUSED" not in mtext:
            errors.append("machine must stop on pause")
        if "timeout_sec" not in mtext or "waitJob" not in mtext:
            errors.append("machine waitJob must honor timeout_sec")
        if "readEvidence" not in (BRIDGE / "src" / "orchestrator" / "store.ts").read_text(encoding="utf-8"):
            errors.append("store must read execute evidence back")
    store = BRIDGE / "src" / "orchestrator" / "store.ts"
    if not store.is_file():
        errors.append("missing store.ts")
    else:
        stext = store.read_text(encoding="utf-8")
        if "renameSync" not in stext:
            errors.append("store must tmp+rename")
        if ".hh-agent" not in stext:
            errors.append("store must refuse locked .hh-agent writes")
    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r7w2/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r7w2/")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if 'p.contains("/r7w2' not in export_gd and 'p.contains("r7w2' not in export_gd:
        errors.append("export _should_skip must contain() r7w2")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_orchestrator_adapter" not in router:
        errors.append("router must dispatch job.run through orchestrator adapter")
    dock = (ADDON / "ui" / "health" / "hh_activity_dock.gd").read_text(encoding="utf-8")
    if "orch:" not in dock:
        errors.append("activity dock must show orch state")
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


def run_harness(args: list[str], *, linger_ms: int = 0) -> subprocess.Popen[str] | dict:
    cmd = [node(), str(HARNESS), "--project", str(PLUGIN_PROJECT), *args]
    if linger_ms:
        proc = subprocess.Popen(
            [*cmd, "--linger", str(linger_ms)],
            cwd=str(BRIDGE),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        return proc
    proc = subprocess.run(
        cmd,
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    line = (proc.stdout or "").strip().splitlines()
    body = line[0] if line else "{}"
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "error": {"message": (proc.stderr or proc.stdout or body)[:400]}}
    return parsed if isinstance(parsed, dict) else {"ok": False}


def wait_ready(proc: subprocess.Popen[str], timeout: float) -> str:
    assert proc.stdout
    deadline = time.time() + timeout
    buf = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            rest = proc.stdout.read() or ""
            return buf + rest
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        buf += line
        if "READY" in line:
            return buf
    return buf


def state_path(job_id: str) -> Path:
    return TEMP_DIR / job_id / "state.json"


def read_state(job_id: str) -> dict:
    path = state_path(job_id)
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def kill_proc(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def fixture_for(state: str) -> str:
    if state == "repair":
        return "infinite_repair"
    return "ok_slice"


def kill_restart_errors() -> tuple[list[str], str, str]:
    errors: list[str] = []
    proven = "unproven"
    resume_l = "unproven"
    replay_ok = True
    restarted = 0
    for state in HOLD_STATES:
        job_id = f"kill-{state.replace('-', '')}"
        fixture = fixture_for(state)
        proc = run_harness(
            ["--job-id", job_id, "--fixture", fixture, "--hold-after", state],
            linger_ms=45_000,
        )
        if not isinstance(proc, subprocess.Popen):
            errors.append(f"KILL_RESTART {state}: failed to spawn linger harness")
            continue
        out = wait_ready(proc, 12.0)
        disk = read_state(job_id)
        if disk.get("state") != state:
            errors.append(f"KILL_RESTART {state}: flushed state={disk.get('state')!r} ready={out[-200:]}")
            kill_proc(proc)
            continue
        committed = list(disk.get("committed_command_ids") or [])
        task = str(disk.get("current_task_id") or "")
        kill_proc(proc)
        if proc.poll() is None:
            errors.append(f"KILL_RESTART {state}: process still alive after kill")
            continue
        restarted += 1
        resumed = run_harness(["--job-id", job_id, "--wait", "--timeout", "5", "--fixture", fixture])
        if not isinstance(resumed, dict):
            errors.append(f"RESUME {state}: harness returned {resumed}")
            replay_ok = False
            continue
        after = read_state(job_id)
        if not after:
            errors.append(f"RESUME {state}: missing state after restart")
            replay_ok = False
            continue
        if str(after.get("current_task_id") or "") == "" and task:
            errors.append(f"RESUME {state}: lost current task {task}")
            replay_ok = False
        after_committed = list(after.get("committed_command_ids") or [])
        if state == "execute" and committed:
            prefix = after_committed[: len(committed)]
            if prefix != committed:
                errors.append(f"RESUME {state}: replayed committed commands {committed} -> {after_committed}")
                replay_ok = False
            if len(after_committed) < len(committed):
                errors.append(f"RESUME {state}: lost ACKed command_ids")
                replay_ok = False
        if after.get("state") == "inspect" and state != "inspect":
            errors.append(f"RESUME {state}: restarted from inspect instead of {state}")
            replay_ok = False
        if fixture == "ok_slice" and after.get("state") not in {"done", "review-ready"}:
            errors.append(f"RESUME {state}: wait did not continue (state={after.get('state')!r})")
            replay_ok = False
        if fixture == "infinite_repair" and after.get("state") != "blocked":
            errors.append(f"RESUME {state}: repair wait must stay/reach blocked, got {after.get('state')!r}")
            replay_ok = False
    if restarted == len(HOLD_STATES) and not any("KILL_RESTART" in e for e in errors):
        proven = "proven"
    if replay_ok and restarted == len(HOLD_STATES) and not any("RESUME" in e for e in errors):
        resume_l = "proven"
    return errors, proven, resume_l


def dep_fail_errors() -> tuple[list[str], str]:
    errors: list[str] = []
    job_id = "dep-fail-1"
    first = run_harness(["--job-id", job_id, "--fixture", "dep_fail"])
    if not isinstance(first, dict):
        return ["DEP_FAIL harness failed"], "unproven"
    disk = read_state(job_id)
    if disk.get("state") == "done":
        errors.append("DEP_FAIL stamped green done")
    if disk.get("state") != "blocked":
        errors.append(f"DEP_FAIL state={disk.get('state')!r} (need blocked)")
    if str(disk.get("blocked_reason") or "") not in {"dependency_failed", "dependency_cancelled"}:
        errors.append(f"DEP_FAIL reason={disk.get('blocked_reason')!r}")
    status = disk.get("task_status") if isinstance(disk.get("task_status"), dict) else {}
    if status.get("task_b") not in {"skipped", "pending"}:
        errors.append(f"DEP_FAIL dependent not skipped: {status}")
    if status.get("task_b") == "ok":
        errors.append("DEP_FAIL ran dependent after parent fail")
    task_files = list((TEMP_DIR / job_id / "tasks").glob("task_a-*.json")) if (TEMP_DIR / job_id / "tasks").is_dir() else []
    if not task_files:
        errors.append("DEP_FAIL missing execute evidence on disk")
    else:
        body = json.loads(task_files[0].read_text(encoding="utf-8"))
        if not body.get("digest") or not body.get("command_id"):
            errors.append(f"DEP_FAIL execute evidence missing digest/command_id: {body}")
        seed_path = TEMP_DIR / job_id / "seed.json"
        if not seed_path.is_file():
            errors.append("DEP_FAIL missing plan seed.json")
        else:
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
            fails = seed.get("fail_tasks") if isinstance(seed.get("fail_tasks"), list) else []
            if "task_a" not in fails:
                errors.append(f"DEP_FAIL seed must name task_a as fail, got {seed}")
    proc = run_harness(["--job-id", job_id, "--resume"], linger_ms=20_000)
    if isinstance(proc, subprocess.Popen):
        wait_ready(proc, 8.0)
        kill_proc(proc)
    again = run_harness(["--job-id", job_id, "--wait", "--timeout", "3"])
    after = read_state(job_id)
    if after.get("state") == "done":
        errors.append("DEP_FAIL resume after kill became done")
    if after.get("state") != "blocked":
        errors.append(f"DEP_FAIL after kill/restart state={after.get('state')!r}")
    label = "proven" if not errors else "unproven"
    return errors, label


def cancel_errors() -> tuple[list[str], str]:
    errors: list[str] = []
    job_id = "cancel-1"
    held = run_harness(["--job-id", job_id, "--fixture", "ok_slice", "--hold-after", "execute"])
    if not isinstance(held, dict):
        return ["CANCEL harness failed"], "unproven"
    if read_state(job_id).get("state") != "execute":
        errors.append(f"CANCEL setup state={read_state(job_id).get('state')!r}")
    cancelled = run_harness(["--job-id", job_id, "--cancel"])
    disk = read_state(job_id)
    if not isinstance(cancelled, dict) or disk.get("state") != "cancelled":
        errors.append(f"CANCEL did not persist cancelled: {disk}")
    if disk.get("state") == "done":
        errors.append("CANCEL stamped green done")
    proc = run_harness(["--job-id", job_id, "--resume"], linger_ms=15_000)
    if isinstance(proc, subprocess.Popen):
        wait_ready(proc, 6.0)
        kill_proc(proc)
    resumed = run_harness(["--job-id", job_id, "--wait", "--timeout", "3"])
    after = read_state(job_id)
    if after.get("state") != "cancelled":
        errors.append(f"CANCEL resume after kill left {after.get('state')!r}")
    if after.get("state") == "done":
        errors.append("CANCEL resume became done")
    if isinstance(resumed, dict) and resumed.get("ok") is True and after.get("state") != "cancelled":
        errors.append(f"CANCEL resume executed after cancel: {resumed}")
    label = "proven" if not errors else "unproven"
    return errors, label


def repair_cap_errors() -> tuple[list[str], str]:
    errors: list[str] = []
    job_id = "repair-cap-1"
    first = run_harness(["--job-id", job_id, "--fixture", "infinite_repair", "--max-steps", "32"])
    disk = read_state(job_id)
    if disk.get("state") == "done":
        errors.append("REPAIR_CAP stamped done on infinite fixture")
    if disk.get("state") != "blocked":
        errors.append(f"REPAIR_CAP state={disk.get('state')!r} (need blocked)")
    if str(disk.get("blocked_reason") or "") != "repair_cap":
        errors.append(f"REPAIR_CAP reason={disk.get('blocked_reason')!r} first={first}")
    repair = disk.get("repair") if isinstance(disk.get("repair"), dict) else {}
    same_n = int(repair.get("same_error_count") or 0)
    if same_n <= 3:
        errors.append(f"REPAIR_CAP same_error_count={same_n} (need 4th same error to block)")
    loops = int(repair.get("loops") or 0)
    if loops > 3:
        errors.append(f"REPAIR_CAP applied {loops} silent patches (cap is 3)")
    proc = run_harness(["--job-id", job_id, "--resume"], linger_ms=15_000)
    if isinstance(proc, subprocess.Popen):
        wait_ready(proc, 6.0)
        kill_proc(proc)
    run_harness(["--job-id", job_id, "--wait", "--timeout", "3"])
    after = read_state(job_id)
    if after.get("state") != "blocked" or str(after.get("blocked_reason") or "") != "repair_cap":
        errors.append(f"REPAIR_CAP after kill/restart {after.get('state')} {after.get('blocked_reason')}")
    after_repair = after.get("repair") if isinstance(after.get("repair"), dict) else {}
    if int(after_repair.get("loops") or 0) > loops:
        errors.append("REPAIR_CAP resume applied another patch")
    label = "proven" if not errors else "unproven"
    return errors, label


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
                    "clientInfo": {"name": "test-orchestrator", "version": "0"},
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


def live_errors(exe: Path) -> tuple[list[str], str]:
    errors: list[str] = []
    live = "unrun"
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun"
    proc = None
    godot = None
    desc_path = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = start_sidecar()
        godot, godot_lines = pin.start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed"
        live = "ran"
        req_id, body = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-ok", "fixture": "ok_slice", "hold_after": "inspect"},
            timeout=30.0,
        )
        after = pin.after_of(body)
        if after.get("state") != "inspect":
            errors.append(f"live job.run hold inspect: {sess.redact(json.dumps(body), secret)}")
        req_id, st = pin.tool_call(proc, req_id, "godot.job", "status", {"job_id": "live-ok"}, timeout=15.0)
        if pin.after_of(st).get("state") != "inspect":
            errors.append(f"live job.status missed inspect: {st}")
        paused = pin.body_of(pin.mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if paused.get("ok") is not True and paused.get("paused") is not True:
            errors.append(f"hh.pause failed: {paused}")
        req_id, blocked = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-ok", "resume": True, "hold_after": "execute"},
            timeout=30.0,
        )
        berr = blocked.get("error") if isinstance(blocked.get("error"), dict) else {}
        after_p = pin.after_of(blocked)
        if str(berr.get("code") or "") != "E_PAUSED":
            errors.append(f"pause must E_PAUSED before mutate steps: {blocked}")
        if after_p.get("state") in {"checkpoint", "execute", "done", "review-ready"}:
            errors.append(f"pause advanced into mutate/done: {after_p.get('state')}")
        pin.body_of(pin.mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1
        req_id, cont = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-ok", "resume": True},
            timeout=30.0,
        )
        if pin.after_of(cont).get("state") not in {"done", "review-ready", "verify", "execute"}:
            if cont.get("ok") is not True and pin.after_of(cont).get("state") != "done":
                errors.append(f"live resume after pause failed: {sess.redact(json.dumps(cont), secret)}")
        req_id, listed = pin.tool_call(proc, req_id, "godot.job", "list", {"limit": 20}, timeout=15.0)
        jobs = pin.after_of(listed).get("jobs") if isinstance(pin.after_of(listed).get("jobs"), list) else []
        if not any(isinstance(j, dict) and (j.get("job_id") == "live-ok" or j.get("id") == "live-ok") for j in jobs):
            errors.append("live job.list missing orchestrator job")
        req_id, cbody = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-cancel", "fixture": "ok_slice", "hold_after": "plan"},
            timeout=30.0,
        )
        req_id, can = pin.tool_call(proc, req_id, "godot.job", "cancel", {"job_id": "live-cancel"}, timeout=15.0)
        if pin.after_of(can).get("state") != "cancelled" and can.get("ok") is not True:
            errors.append(f"live job.cancel failed: {can}")
        elif pin.after_of(can).get("state") == "done":
            errors.append("live job.cancel stamped done")
        req_id, timeline = pin.tool_call(
            proc, req_id, "godot.observer", "timeline", {"detail": "short", "limit": 20}, timeout=20.0
        )
        dock = pin.after_of(timeline).get("dock") if isinstance(pin.after_of(timeline).get("dock"), dict) else {}
        orch = dock.get("orch") if isinstance(dock.get("orch"), dict) else {}
        if not orch.get("state") and "orch:" not in json.dumps(pin.after_of(timeline)):
            errors.append("observer.timeline dock.orch empty — store/dock, not only job.run after")
        req_id, illegal = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-ok", "hold_after": "inspect"},
            timeout=20.0,
        )
        if illegal.get("ok") is True and pin.after_of(illegal).get("state") == "inspect" and read_state("live-ok").get("state") == "done":
            pass
        req_id, held = pin.tool_call(
            proc,
            req_id,
            "godot.job",
            "run",
            {"job_id": "live-kill-exec", "fixture": "ok_slice", "hold_after": "execute"},
            timeout=30.0,
        )
        held_after = pin.after_of(held)
        if held_after.get("state") != "execute":
            errors.append(f"live-kill-exec hold execute failed: {held}")
        committed = list(read_state("live-kill-exec").get("committed_command_ids") or [])
        if godot is not None:
            life.stop_proc(godot)
            godot = None
        if proc is not None:
            life.stop_proc(proc)
            proc = None
        time.sleep(1.0)
        pin.kill_plugin_project_holders(godot=True, node=True)
        time.sleep(1.0)
        proc, desc_path, secret, err_lines = start_sidecar()
        godot, godot_lines = pin.start_godot(exe, headless=True)
        req_id = 2
        req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"live kill/restart hello failed: {last2}")
        else:
            req_id, waited = pin.tool_call(
                proc,
                req_id,
                "godot.job",
                "wait",
                {"job_id": "live-kill-exec", "timeout_sec": 10},
                timeout=20.0,
            )
            disk = read_state("live-kill-exec")
            if disk.get("state") == "inspect":
                errors.append("LIVE kill/restart lost execute and restarted inspect")
            if disk.get("state") not in {"done", "review-ready"}:
                errors.append(f"LIVE kill/restart wait did not continue (state={disk.get('state')!r}): {waited}")
            after_c = list(disk.get("committed_command_ids") or [])
            if committed and after_c[: len(committed)] != committed:
                errors.append(f"LIVE kill/restart replayed commands {committed} -> {after_c}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live orchestrator failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        if godot is not None:
            life.stop_proc(godot)
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
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        errors.extend(pin.project_godot_leak_errors("after live"))
    return errors, live


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
    spec = actions.get("job.run") if isinstance(actions.get("job.run"), dict) else {}
    if spec.get("method") != "godot.job":
        errors.append("actions.json missing job.run")
    for verb in ("job.status", "job.list", "job.cancel", "job.wait"):
        if verb not in actions:
            errors.append(f"actions.json missing {verb}")

    illegal = run_harness(["--illegal", "--from", "inspect", "--to", "done"])
    if not isinstance(illegal, dict) or illegal.get("ok") is True:
        errors.append(f"illegal inspect→done must be typed reject, got {illegal}")
    elif str((illegal.get("error") or {}).get("code") or "") != "E_CONFLICT":
        errors.append(f"illegal transition must be E_CONFLICT, got {illegal}")

    errors.extend(cleanup_temp())
    kr_errs, kill_l, resume_l = kill_restart_errors()
    errors.extend(kr_errs)
    dep_errs, dep_l = dep_fail_errors()
    errors.extend(dep_errs)
    can_errs, can_l = cancel_errors()
    errors.extend(can_errs)
    cap_errs, cap_l = repair_cap_errors()
    errors.extend(cap_errs)

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live = live_errors(exe)
            errors.extend(live_errs)

    if kill_l != "proven":
        errors.append("KILL_RESTART not proven")
    if dep_l != "proven":
        errors.append("DEP_FAIL not proven")
    if can_l != "proven":
        errors.append("CANCEL not proven")
    if cap_l != "proven":
        errors.append("REPAIR_CAP not proven")
    if resume_l != "proven":
        errors.append("RESUME not proven")

    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.0)
    errors.extend(cleanup_temp())
    banner = (
        f"LIVE={live}; KILL_RESTART={kill_l}; DEP_FAIL={dep_l}; "
        f"CANCEL={can_l}; REPAIR_CAP={cap_l}; RESUME={resume_l}"
    )
    if errors:
        print(f"FAIL: orchestrator; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: orchestrator; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
