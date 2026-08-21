#!/usr/bin/env python3
"""R2-WP4: command ledger, dedup, uncertain recovery.

Executes 200 randomized idempotent commands, crash hooks, and a .godot/
delete. Does not tick the 20-8 plan. Does not apply scene mutations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_session as sess

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
PROTOCOL = "hh-godot-agent/1"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
VENDOR_NEEDLES = (
    "satelliteoflove",
    "MCPGameBridge",
    "godot_mcp",
    "call_method",
    "Object.callv",
    "evaluate_expression",
)
FAULT_HOOKS = ("received", "validated", "applying", "verified")


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R2-WP4 unticked for this implementer; allow R2-WP5+ after coordinator tick."""
    errors: list[str] = []
    current = ""
    wp4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP4\b", stripped):
            wp4 = stripped
    if wp4 is None:
        return ["plan missing R2-WP4 heading"]
    ticked = bool(re.search(r"\[x\]", wp4, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp4:
            errors.append("R2-WP4 heading must keep [ ] until coordinator tick")
        if current != "R2-WP4":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP4 while WP4 is unticked)")
    elif not re.match(r"^R2-WP[5-9]$|^R2-WP\d{2,}$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP5+ after R2-WP4 tick)")
    return errors


def new_ulid() -> str:
    ms = int(time.time() * 1000)
    chars: list[str] = []
    t = ms
    for _ in range(10):
        chars.append(CROCKFORD[t % 32])
        t //= 32
    time_part = "".join(reversed(chars))
    acc = int.from_bytes(os.urandom(10), "big")
    rand: list[str] = []
    for _ in range(16):
        rand.append(CROCKFORD[acc % 32])
        acc //= 32
    return time_part + "".join(reversed(rand))


def project_id_for(root: Path) -> str:
    resolved = str(root.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:32]


def fixture_home() -> tuple[Path, str]:
    home = Path(tempfile.mkdtemp(prefix="hh-r2wp4-home-"))
    project_id = hashlib.sha256(os.urandom(16)).hexdigest()[:32]
    return home, project_id


def harness(
    cmd: str,
    payload: dict,
    env: dict | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [sess.node(), str(BRIDGE / "dist" / "ledger" / "harness.js"), cmd, json.dumps(payload)],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=run_env,
    )


def harness_json(cmd: str, payload: dict, env: dict | None = None) -> dict:
    proc = harness(cmd, payload, env=env)
    out = (proc.stdout or "").strip().splitlines()
    parsed: dict = {}
    for line in out:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                parsed = {}
    if not parsed:
        raise RuntimeError(f"harness {cmd} produced no JSON (exit {proc.returncode}): {proc.stdout} {proc.stderr}")
    parsed["_exit"] = proc.returncode
    parsed["_stderr"] = proc.stderr or ""
    return parsed


def noop_envelope(command_id: str, extra: dict | None = None) -> dict:
    body = {
        "protocol": PROTOCOL,
        "command_id": command_id,
        "method": "hh.plugin",
        "action": "noop",
        "params": extra or {},
    }
    return body


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if "better-sqlite3" in text:
            errors.append(f"{posix} adds better-sqlite3 (G1 allowlist forbids it)")
        if "0.0.0.0" in text:
            errors.append(f"{posix} binds or mentions 0.0.0.0")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    pkg = (BRIDGE / "package.json").read_text(encoding="utf-8")
    if "better-sqlite3" in pkg:
        errors.append("bridge/package.json added better-sqlite3")
    session = (BRIDGE / "src" / "session" / "session.ts").read_text(encoding="utf-8")
    if "sidecar:${sessionId}" in session or "sidecar:`" in session:
        errors.append("sidecar actor_id must not be minted from sessionId")
    if "durableActorId" not in session:
        errors.append("sidecar must bind durableActorId(projectId)")
    return errors


def sqlite_state(db_path: Path, command_id: str) -> dict | None:
    if not db_path.is_file():
        return None
    con = sqlite3.connect(str(db_path))
    try:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM commands WHERE command_id = ?", (command_id,)).fetchone()
        return dict(row) if row else None
    finally:
        con.close()


def apply_counts(log_path: Path, command_id: str) -> int:
    if not log_path.is_file():
        return 0
    return sum(1 for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip() == command_id)


def test_randomized(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    apply_log = Path(tempfile.mkdtemp(prefix="hh-r2wp4-apply-")) / "apply.log"
    env = {"HH_LEDGER_APPLY_LOG": str(apply_log)}
    for i in range(200):
        command_id = new_ulid()
        payload = {"n": i, "salt": os.urandom(8).hex()}
        base = {
            "home": home,
            "project_id": project_id,
            "actor": "actor-a",
            "policy": "OBSERVE",
            "envelope": noop_envelope(command_id, payload),
        }
        first = harness_json("submit", base, env=env)
        second = harness_json("submit", base, env=env)
        other_payload = {**base, "envelope": noop_envelope(command_id, {**payload, "n": i + 1000})}
        conflict_payload = harness_json("submit", other_payload, env=env)
        conflict_actor = harness_json(
            "submit",
            {**base, "actor": "actor-b"},
            env=env,
        )
        if first.get("ok") is not True:
            errors.append(f"rand[{i}] first submit failed: {first}")
            break
        if (first.get("ledger") or {}).get("state") != "committed_durable":
            errors.append(f"rand[{i}] first state {first.get('ledger')}")
            break
        if second.get("ok") is not True:
            errors.append(f"rand[{i}] cached retry failed: {second}")
            break
        if (second.get("ledger") or {}).get("apply_count") != 1:
            errors.append(f"rand[{i}] cached retry re-applied: {second.get('ledger')}")
            break
        if ((conflict_payload.get("result") or {}).get("error") or {}).get("code") != "E_IDEMPOTENCY_CONFLICT":
            errors.append(f"rand[{i}] different payload must conflict: {conflict_payload}")
            break
        if ((conflict_actor.get("result") or {}).get("error") or {}).get("code") != "E_IDEMPOTENCY_CONFLICT":
            errors.append(f"rand[{i}] different actor must conflict: {conflict_actor}")
            break
        if apply_counts(apply_log, command_id) != 1:
            errors.append(f"rand[{i}] apply log count={apply_counts(apply_log, command_id)}")
            break
    return errors


def test_godot_delete(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    proj = Path(tempfile.mkdtemp(prefix="hh-r2wp4-proj-"))
    godot = proj / ".godot" / "hh_agent"
    godot.mkdir(parents=True)
    (godot / "cache.txt").write_text("recreatable", encoding="utf-8")
    command_id = new_ulid()
    payload = {
        "home": home,
        "project_id": project_id,
        "actor": "actor-a",
        "policy": "OBSERVE",
        "envelope": noop_envelope(command_id, {"scene": "res://main.tscn"}),
    }
    first = harness_json("submit", payload)
    shutil.rmtree(proj / ".godot")
    second = harness_json("submit", payload)
    db = Path(home) / "projects" / project_id / "ledger.sqlite"
    if first.get("ok") is not True or second.get("ok") is not True:
        errors.append(f".godot delete lost dedup: first={first} second={second}")
    if (second.get("ledger") or {}).get("apply_count") != 1:
        errors.append(f".godot delete re-applied: {second.get('ledger')}")
    if not db.is_file():
        errors.append(f"ledger missing after .godot delete: {db}")
    if any(proj.rglob("ledger.sqlite")):
        errors.append("ledger was written into the Godot project")
    if (proj / ".godot").exists():
        errors.append(".godot delete did not remove the cache tree")
    shutil.rmtree(proj, ignore_errors=True)
    return errors


def test_kill_hooks(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    apply_dir = Path(tempfile.mkdtemp(prefix="hh-r2wp4-kill-"))
    killed: list[str] = []
    for hook in FAULT_HOOKS:
        command_id = new_ulid()
        apply_log = apply_dir / f"{hook}.log"
        payload = {
            "home": home,
            "project_id": project_id,
            "actor": "actor-a",
            "policy": "OBSERVE",
            "envelope": noop_envelope(command_id),
        }
        env = {
            "HH_LEDGER_FAULT_AT": hook,
            "HH_LEDGER_FAULT_MODE": "sidecar",
            "HH_LEDGER_APPLY_LOG": str(apply_log),
        }
        crashed = harness("submit", payload, env=env)
        if crashed.returncode != 99:
            errors.append(f"kill {hook}: expected exit 99, got {crashed.returncode} {crashed.stderr}")
            continue
        if f"hh-ledger-fault={hook}" not in (crashed.stderr or ""):
            errors.append(f"kill {hook}: missing fault marker in stderr")
        inspected = harness_json("inspect", {**payload, "command_id": command_id})
        state = (inspected.get("row") or {}).get("state")
        if state != hook and not (hook == "verified" and state == "verified"):
            errors.append(f"kill {hook}: persisted state={state!r}")
        applied_before = apply_counts(apply_log, command_id)
        if hook == "verified":
            if applied_before != 1:
                errors.append(f"kill verified: apply should have run once before the hook ({applied_before})")
        elif applied_before != 0:
            errors.append(f"kill {hook}: applied before the hook ({applied_before})")
        resumed = harness_json("submit", payload, env={"HH_LEDGER_APPLY_LOG": str(apply_log)})
        if resumed.get("ok") is not True:
            errors.append(f"resume after {hook} failed: {resumed}")
            continue
        if (resumed.get("result") or {}).get("ok") is not True:
            errors.append(f"resume after {hook} was not success: {resumed.get('result')}")
        if apply_counts(apply_log, command_id) != 1:
            errors.append(
                f"resume after {hook} apply_count_log={apply_counts(apply_log, command_id)} (need 1)"
            )
        if (resumed.get("ledger") or {}).get("apply_count") != 1:
            errors.append(f"resume after {hook} ledger apply_count={(resumed.get('ledger') or {}).get('apply_count')}")
        killed.append(hook)
    if killed != list(FAULT_HOOKS):
        errors.append(f"hooks actually killed={killed}")
    return errors


def test_uncertain(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    apply_log = Path(tempfile.mkdtemp(prefix="hh-r2wp4-unc-")) / "apply.log"
    command_id = new_ulid()
    payload = {
        "home": home,
        "project_id": project_id,
        "actor": "actor-a",
        "policy": "OBSERVE",
        "envelope": noop_envelope(command_id),
    }
    crashed = harness(
        "submit",
        payload,
        env={
            "HH_LEDGER_CRASH_AFTER_DISPATCH_ATTEMPT": "1",
            "HH_LEDGER_APPLY_LOG": str(apply_log),
        },
    )
    if crashed.returncode != 98:
        errors.append(f"dispatch-attempt crash expected 98, got {crashed.returncode} {crashed.stderr}")
    inspected = harness_json("inspect", {**payload, "command_id": command_id})
    state = (inspected.get("row") or {}).get("state")
    if state != "applying":
        errors.append(f"crash after attempt should stay applying, got {state!r}")
    if (inspected.get("row") or {}).get("dispatch_attempted") != 1:
        errors.append(f"dispatch_attempted not flushed: {inspected.get('row')}")
    resumed = harness_json("submit", payload, env={"HH_LEDGER_APPLY_LOG": str(apply_log)})
    code = ((resumed.get("result") or {}).get("error") or {}).get("code")
    if code != "E_UNCERTAIN":
        errors.append(f"resume after attempt crash must be E_UNCERTAIN: {resumed}")
    if resumed.get("ok") is True or (resumed.get("result") or {}).get("ok") is True:
        errors.append("restart turned uncertain into success")
    if apply_counts(apply_log, command_id) != 0:
        errors.append("attempt crash should not have dispatched (log written in mock before throw only if throw path)")
    # crash-after-attempt exits before dispatch(); apply log stays empty.
    again = harness_json("submit", payload, env={"HH_LEDGER_APPLY_LOG": str(apply_log)})
    if ((again.get("result") or {}).get("error") or {}).get("code") != "E_UNCERTAIN":
        errors.append(f"uncertain must stay sticky: {again}")
    if (again.get("result") or {}).get("ok") is True:
        errors.append("second resume turned uncertain into {ok:true}")
    if apply_counts(apply_log, command_id) != 0:
        errors.append("uncertain resume applied blind")

    throw_id = new_ulid()
    throw_payload = {
        "home": home,
        "project_id": project_id,
        "actor": "actor-a",
        "policy": "OBSERVE",
        "envelope": noop_envelope(throw_id),
    }
    thrown = harness_json(
        "submit",
        throw_payload,
        env={"HH_LEDGER_DISPATCH_THROW": "1", "HH_LEDGER_APPLY_LOG": str(apply_log)},
    )
    if ((thrown.get("result") or {}).get("error") or {}).get("code") != "E_UNCERTAIN":
        errors.append(f"dispatch throw must be E_UNCERTAIN: {thrown}")
    if apply_counts(apply_log, throw_id) != 1:
        errors.append(f"dispatch throw should apply once: {apply_counts(apply_log, throw_id)}")
    retry = harness_json("submit", throw_payload, env={"HH_LEDGER_APPLY_LOG": str(apply_log)})
    if ((retry.get("result") or {}).get("error") or {}).get("code") != "E_UNCERTAIN":
        errors.append(f"thrown uncertain must stick: {retry}")
    if (retry.get("result") or {}).get("ok") is True:
        errors.append("thrown uncertain became success")
    if apply_counts(apply_log, throw_id) != 1:
        errors.append("thrown uncertain was applied again")
    return errors


def test_blocked_and_compact(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    mutate_id = new_ulid()
    mutate = harness_json(
        "submit",
        {
            "home": home,
            "project_id": project_id,
            "actor": "actor-a",
            "policy": "OBSERVE",
            "envelope": {
                "protocol": PROTOCOL,
                "command_id": mutate_id,
                "method": "godot.node",
                "action": "add",
                "params": {
                    "scene": "res://main.tscn",
                    "parent": ".",
                    "class_name": "Node2D",
                    "name": "X",
                },
            },
        },
    )
    row = mutate.get("ledger") or {}
    if ((mutate.get("result") or {}).get("error") or {}).get("code") != "E_UNVERIFIED":
        errors.append(f"mutate must be E_UNVERIFIED: {mutate}")
    if row.get("state") == "applying" or row.get("apply_count"):
        errors.append(f"mutate entered applying: {row}")
    if row.get("state") != "failed":
        errors.append(f"mutate should ledger as failed, got {row.get('state')}")

    keep_id = new_ulid()
    keep = harness_json(
        "submit",
        {
            "home": home,
            "project_id": project_id,
            "actor": "actor-a",
            "policy": "OBSERVE",
            "envelope": noop_envelope(keep_id),
        },
    )
    if keep.get("ok") is not True:
        errors.append(f"compaction seed failed: {keep}")
    harness_json(
        "evidence",
        {"home": home, "project_id": project_id, "command_id": keep_id, "evidence": ["ev-keep"]},
    )
    drop_id = new_ulid()
    harness_json(
        "submit",
        {
            "home": home,
            "project_id": project_id,
            "actor": "actor-a",
            "policy": "OBSERVE",
            "envelope": noop_envelope(drop_id),
        },
    )
    harness_json(
        "checkpoint",
        {
            "home": home,
            "project_id": project_id,
            "checkpoint_id": "cp-keep",
            "command_id": keep_id,
            "evidence": ["ev-keep"],
        },
    )
    compacted = harness_json(
        "compact",
        {
            "home": home,
            "project_id": project_id,
            "max_age_ms": 0,
            "now_ms": int(time.time() * 1000) + 60_000,
        },
    )
    if compacted.get("ok") is not True:
        errors.append(f"compact failed: {compacted}")
    kept = harness_json("inspect", {"home": home, "project_id": project_id, "command_id": keep_id})
    dropped = harness_json("inspect", {"home": home, "project_id": project_id, "command_id": drop_id})
    if kept.get("row") is None:
        errors.append("compaction deleted evidence still referenced by a checkpoint")
    if dropped.get("row") is not None:
        errors.append("compaction did not drop an unreferenced committed command")
    return errors


def test_pragma(home: str, project_id: str) -> list[str]:
    errors: list[str] = []
    info = harness_json("pragma", {"home": home, "project_id": project_id})
    pragma = info.get("pragma") or {}
    if pragma.get("journal_mode") != "wal":
        errors.append(f"journal_mode={pragma.get('journal_mode')!r} (need wal)")
    if pragma.get("synchronous") != 2:
        errors.append(f"synchronous={pragma.get('synchronous')!r} (need 2/FULL)")
    path = str(info.get("path") or "")
    if "projects" not in path.replace("\\", "/") or not path.endswith("ledger.sqlite"):
        errors.append(f"unexpected ledger path {path}")
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict) -> dict:
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    line = sess.readline_timeout(proc.stdout, 8.0)
    return json.loads(line)


def test_sidecar_localappdata() -> tuple[list[str], str]:
    errors: list[str] = []
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return ["LOCALAPPDATA missing"], ""
    tmp = Path(tempfile.mkdtemp(prefix="hh-r2wp4-sid-"))
    (tmp / "project.godot").write_text("; r2-wp4 fixture\nconfig_version=5\n", encoding="utf-8")
    godot_cache = tmp / ".godot" / "hh_agent"
    godot_cache.mkdir(parents=True)
    (godot_cache / "cache.txt").write_text("ignore-me", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    err_lines: list[str] = []
    secret = ""
    ledger_path = ""
    try:
        proc = subprocess.Popen(
            [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(tmp)],
            cwd=str(BRIDGE),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
        desc_path, desc = sess.find_descriptor(proc.pid)
        secret = str(desc.get("token") or "")
        host = str(desc.get("host") or "")
        port = int(desc.get("port") or 0)
        sid_project = str(desc.get("project_id") or "")
        expected = Path(local) / "HHGodotAgent" / "projects" / sid_project / "ledger.sqlite"
        plugin_sock = sess.ws_connect(host, port)
        sess.ws_send_text(plugin_sock, json.dumps(sess.hello_payload(sid_project, secret)))
        hello_ok = json.loads(sess.ws_recv_text(plugin_sock))
        if hello_ok.get("ok") is not True:
            errors.append(f"plugin hello failed: {sess.redact(json.dumps(hello_ok), secret)}")

        last: dict = {}

        def plugin_loop() -> None:
            nonlocal last
            try:
                while True:
                    msg = json.loads(sess.ws_recv_text(plugin_sock))
                    last = msg
                    if msg.get("type") == "readback":
                        sess.ws_send_text(
                            plugin_sock,
                            json.dumps(
                                {
                                    "type": "readback_result",
                                    "command_id": msg.get("command_id"),
                                    "found": False,
                                    "ok": False,
                                    "postcondition": {"verified": False, "checks": []},
                                }
                            ),
                        )
                        continue
                    if msg.get("type") != "request":
                        continue
                    env = msg.get("envelope") if isinstance(msg.get("envelope"), dict) else {}
                    command_id = str(env.get("command_id") or "")
                    if env.get("method") == "hh.plugin" and env.get("action") == "noop":
                        sess.ws_send_text(
                            plugin_sock,
                            json.dumps(
                                {
                                    "type": "result",
                                    "ok": True,
                                    "command_id": command_id,
                                    "changed": False,
                                    "postcondition": {"verified": True, "checks": ["noop"]},
                                }
                            ),
                        )
                    else:
                        sess.ws_send_text(
                            plugin_sock,
                            json.dumps(
                                {
                                    "type": "result",
                                    "ok": False,
                                    "command_id": command_id,
                                    "changed": False,
                                    "postcondition": {"verified": False, "checks": []},
                                    "error": {
                                        "code": "E_UNVERIFIED",
                                        "message": "not dispatched",
                                        "path": "",
                                    },
                                }
                            ),
                        )
            except OSError:
                return

        threading.Thread(target=plugin_loop, daemon=True).start()
        time.sleep(0.15)
        if proc.stdin and proc.stdout:
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test-ledger", "version": "0"},
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            sess.readline_timeout(proc.stdout, 5.0)
            command_id = new_ulid()
            first = mcp_call(proc, 2, "hh.plugin_noop", {"command_id": command_id})
            body = (first.get("result") or {}).get("structuredContent") or {}
            if body.get("ok") is not True or (body.get("postcondition") or {}).get("checks") != ["noop"]:
                errors.append(f"sidecar noop through ledger failed: {sess.redact(json.dumps(first), secret)}")
            inspect = mcp_call(proc, 3, "hh.ledger_inspect", {"command_id": command_id})
            inspect_body = (inspect.get("result") or {}).get("structuredContent") or {}
            row = inspect_body.get("row") or {}
            ledger_path = str(inspect_body.get("path") or "")
            if row.get("state") != "committed_durable":
                errors.append(f"sidecar ledger state={row}")
            if Path(ledger_path).resolve() != expected.resolve():
                errors.append(f"ledger path {ledger_path} != {expected}")
            if not expected.is_file():
                errors.append(f"missing LocalAppData ledger {expected}")
            shutil.rmtree(tmp / ".godot", ignore_errors=True)
            second = mcp_call(proc, 4, "hh.plugin_noop", {"command_id": command_id})
            second_body = (second.get("result") or {}).get("structuredContent") or {}
            if second_body.get("ok") is not True:
                errors.append("dedup after deleting .godot failed")
            inspect2 = mcp_call(proc, 5, "hh.ledger_inspect", {"command_id": command_id})
            row2 = ((inspect2.get("result") or {}).get("structuredContent") or {}).get("row") or {}
            if row2.get("apply_count") != 1:
                errors.append(f"sidecar re-applied after .godot delete: {row2}")
            mutate_id = new_ulid()
            mutate = mcp_call(
                proc,
                6,
                "hh.command",
                {
                    "command_id": mutate_id,
                    "method": "godot.node",
                    "action": "add",
                    "params": {
                        "scene": "res://main.tscn",
                        "parent": ".",
                        "class_name": "Node2D",
                        "name": "X",
                    },
                },
            )
            mutate_body = (mutate.get("result") or {}).get("structuredContent") or {}
            if (mutate_body.get("error") or {}).get("code") != "E_UNVERIFIED":
                errors.append(f"sidecar mutate must stay unverified: {mutate_body}")
            inspect_m = mcp_call(proc, 7, "hh.ledger_inspect", {"command_id": mutate_id})
            mrow = ((inspect_m.get("result") or {}).get("structuredContent") or {}).get("row") or {}
            if mrow.get("state") == "applying":
                errors.append("sidecar mutate entered applying")
            if any(tmp.rglob("ledger.sqlite")):
                errors.append("sidecar wrote ledger into the git/temp project")
        plugin_sock.close()
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        if secret:
            hits = sess.grep_token(tmp, secret)
            if hits:
                errors.append("session secret written into the Godot project tree")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"sidecar ledger run failed: {type(exc).__name__}: {exc}", secret))
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
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
        shutil.rmtree(tmp, ignore_errors=True)
    return errors, ledger_path


def _stop_sidecar(proc: subprocess.Popen[str] | None, desc_path: Path | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
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


def _open_sidecar(
    project: Path, env: dict | None = None
) -> tuple[subprocess.Popen[str], Path, dict, socket.socket, list[str]]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    err_lines: list[str] = []
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(project)],
        cwd=str(BRIDGE),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=run_env,
    )
    threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
    desc_path, desc = sess.find_descriptor(proc.pid)
    host = str(desc.get("host") or "")
    port = int(desc.get("port") or 0)
    project_id = str(desc.get("project_id") or "")
    secret = str(desc.get("token") or "")
    sock = sess.ws_connect(host, port)
    sess.ws_send_text(sock, json.dumps(sess.hello_payload(project_id, secret)))
    hello = json.loads(sess.ws_recv_text(sock))
    if hello.get("ok") is not True:
        sock.close()
        raise RuntimeError(f"hello failed: {hello}")

    def plugin_loop() -> None:
        try:
            while True:
                msg = json.loads(sess.ws_recv_text(sock))
                if msg.get("type") == "readback":
                    sess.ws_send_text(
                        sock,
                        json.dumps(
                            {
                                "type": "readback_result",
                                "command_id": msg.get("command_id"),
                                "found": False,
                                "ok": False,
                                "postcondition": {"verified": False, "checks": []},
                            }
                        ),
                    )
                    continue
                if msg.get("type") != "request":
                    continue
                env_msg = msg.get("envelope") if isinstance(msg.get("envelope"), dict) else {}
                command_id = str(env_msg.get("command_id") or "")
                if env_msg.get("method") == "hh.plugin" and env_msg.get("action") == "noop":
                    sess.ws_send_text(
                        sock,
                        json.dumps(
                            {
                                "type": "result",
                                "ok": True,
                                "command_id": command_id,
                                "changed": False,
                                "postcondition": {"verified": True, "checks": ["noop"]},
                            }
                        ),
                    )
        except OSError:
            return

    threading.Thread(target=plugin_loop, daemon=True).start()
    time.sleep(0.1)
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
                    "clientInfo": {"name": "test-ledger-restart", "version": "0"},
                },
            }
        )
        + "\n"
    )
    proc.stdin.flush()
    sess.readline_timeout(proc.stdout, 5.0)
    return proc, desc_path, desc, sock, err_lines


def test_sidecar_restart() -> list[str]:
    """New sidecar process must resume/cache — not E_IDEMPOTENCY_CONFLICT."""
    errors: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="hh-r2wp4-restart-"))
    (tmp / "project.godot").write_text("; r2-wp4 restart\nconfig_version=5\n", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    sock: socket.socket | None = None
    try:
        proc, desc_path, desc, sock, _err = _open_sidecar(tmp)
        project_id = str(desc.get("project_id") or "")
        cached_id = new_ulid()
        first = mcp_call(proc, 2, "hh.plugin_noop", {"command_id": cached_id})
        body = (first.get("result") or {}).get("structuredContent") or {}
        if body.get("ok") is not True:
            errors.append(f"restart-test first noop failed: {body}")
        inspect = mcp_call(proc, 3, "hh.ledger_inspect", {"command_id": cached_id})
        row = ((inspect.get("result") or {}).get("structuredContent") or {}).get("row") or {}
        if row.get("state") != "committed_durable":
            errors.append(f"restart-test first state={row}")
        if not str(row.get("actor_id") or "").startswith("project:"):
            errors.append(f"actor_id must be project-stable, got {row.get('actor_id')!r}")
        if sock is not None:
            sock.close()
        _stop_sidecar(proc, desc_path)
        proc = None
        desc_path = None

        proc, desc_path, desc2, sock, _err2 = _open_sidecar(tmp)
        if str(desc2.get("project_id") or "") != project_id:
            errors.append("restart used a different project_id")
        cached = mcp_call(proc, 2, "hh.plugin_noop", {"command_id": cached_id})
        cached_body = (cached.get("result") or {}).get("structuredContent") or {}
        cached_err = (cached_body.get("error") or {}).get("code")
        if cached_err == "E_IDEMPOTENCY_CONFLICT":
            errors.append("sidecar restart treated a new session actor as idempotency conflict")
        if cached_body.get("ok") is not True:
            errors.append(f"sidecar restart lost cached durable result: {cached_body}")
        inspect2 = mcp_call(proc, 3, "hh.ledger_inspect", {"command_id": cached_id})
        row2 = ((inspect2.get("result") or {}).get("structuredContent") or {}).get("row") or {}
        if row2.get("apply_count") != 1:
            errors.append(f"sidecar restart re-applied cached noop: {row2}")

        applying_id = new_ulid()
        if sock is not None:
            sock.close()
            sock = None
        _stop_sidecar(proc, desc_path)
        proc = None
        desc_path = None

        proc, desc_path, _desc3, sock, _err3 = _open_sidecar(
            tmp, env={"HH_LEDGER_FAULT_AT": "applying", "HH_LEDGER_FAULT_MODE": "sidecar"}
        )
        try:
            mcp_call(proc, 2, "hh.plugin_noop", {"command_id": applying_id})
        except (OSError, RuntimeError, json.JSONDecodeError, TimeoutError):
            pass
        deadline = time.time() + 8.0
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.05)
        if proc.poll() != 99:
            errors.append(f"applying kill sidecar expected exit 99, got {proc.poll()}")
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
            sock = None
        _stop_sidecar(None, desc_path)
        desc_path = None
        proc = None

        proc, desc_path, _desc4, sock, _err4 = _open_sidecar(tmp)
        resumed = mcp_call(proc, 2, "hh.plugin_noop", {"command_id": applying_id})
        resumed_body = (resumed.get("result") or {}).get("structuredContent") or {}
        if (resumed_body.get("error") or {}).get("code") == "E_IDEMPOTENCY_CONFLICT":
            errors.append("sidecar restart after applying kill returned E_IDEMPOTENCY_CONFLICT")
        if resumed_body.get("ok") is not True:
            errors.append(f"sidecar restart after applying kill did not recover: {resumed_body}")
        inspect3 = mcp_call(proc, 3, "hh.ledger_inspect", {"command_id": applying_id})
        row3 = ((inspect3.get("result") or {}).get("structuredContent") or {}).get("row") or {}
        if row3.get("apply_count") != 1:
            errors.append(f"applying-kill resume apply_count={row3.get('apply_count')}")
        if row3.get("state") != "committed_durable":
            errors.append(f"applying-kill resume state={row3}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"sidecar restart test failed: {type(exc).__name__}: {exc}")
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        _stop_sidecar(proc, desc_path)
        shutil.rmtree(tmp, ignore_errors=True)
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: ledger", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    home, project_id = fixture_home()
    try:
        errors.extend(test_pragma(str(home), project_id))
        errors.extend(test_randomized(str(home), project_id))
        errors.extend(test_godot_delete(str(home), project_id))
        errors.extend(test_kill_hooks(str(home), project_id))
        errors.extend(test_uncertain(str(home), project_id))
        errors.extend(test_blocked_and_compact(str(home), project_id))
    finally:
        shutil.rmtree(home, ignore_errors=True)

    sidecar_errors, ledger_path = test_sidecar_localappdata()
    errors.extend(sidecar_errors)
    errors.extend(test_sidecar_restart())

    if errors:
        print("FAIL: ledger", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: 200 randomized idempotent commands; conflict on payload/actor; "
        ".godot delete keeps LocalAppData dedup; killed received/validated/applying/verified; "
        "uncertain stays unsuccessful; mutate never applying; compaction keeps checkpoint evidence; "
        f"sidecar ledger={ledger_path}; sidecar restart resumes/caches; "
        "plan R2-WP4 progress consistent."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
