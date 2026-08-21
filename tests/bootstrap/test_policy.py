#!/usr/bin/env python3
"""R2-WP5: policy profiles, path jail, leases, recovery checkpoint, Pause ACK.

Keeps the R0-WP4 TOML self-test. Does not tick the 20-8 plan.
Does not apply scene mutations. Pause ACK is measured, not slept.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "tools" / "godot"))
from hh_agent_allow import hh_agent_only_addon_errors
import test_session as sess
import policy_validate  # noqa: E402
BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
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
HARNESS = BRIDGE / "dist" / "policy" / "harness.js"
PAUSE_BUDGET_MS = 250.0


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R2-WP5 unticked for this implementer; allow R2-WP6+ after coordinator tick."""
    errors: list[str] = []
    current = ""
    wp5 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP5\b", stripped):
            wp5 = stripped
    if wp5 is None:
        return ["plan missing R2-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R2-WP5 heading must keep [ ] until coordinator tick")
        if current != "R2-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP5 while WP5 is unticked)")
    elif not re.match(r"^R2-WP[6-9]$|^R2-WP\d{2,}$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP6+ after R2-WP5 tick)")
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


def harness(cmd: str, payload: dict, timeout: float = 20.0) -> dict:
    proc = subprocess.run(
        [sess.node(), str(HARNESS), cmd, json.dumps(payload)],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
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


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if "0.0.0.0" in text:
            errors.append(f"{posix} binds or mentions 0.0.0.0")
        if re.search(r"spawn\([^;]*shell\s*:\s*true", text):
            errors.append(f"{posix} enables shell:true spawn")
        if "npx -y" in text or "npx -y" in text:
            errors.append(f"{posix} uses npx -y")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    pkg = (BRIDGE / "package.json").read_text(encoding="utf-8")
    for extra in ("better-sqlite3", "godot-mcp", "ws"):
        if extra in pkg:
            errors.append(f"bridge/package.json added extra dep {extra}")
    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "_paused" not in plugin or "_on_pause_requested" not in plugin:
        errors.append("plugin.gd does not wire _paused / Pause")
    if "HH_PAUSE_WIRE" not in plugin or 'emit_signal("pause_requested")' not in plugin:
        errors.append("plugin.gd missing dock-signal Pause wire bench")
    dock = (ADDON / "ui" / "health" / "hh_health_dock.gd").read_text(encoding="utf-8")
    if "Pause" not in dock or "font_color" not in dock or "pause_requested" not in dock:
        errors.append("health dock missing red Pause button")
    self_text = Path(__file__).read_text(encoding="utf-8")
    if "dist/main.js" not in self_text.replace("\\", "/") and "dist\\\\main.js" not in self_text:
        if 'dist / "main.js"' not in self_text:
            errors.append("official Pause test must start sidecar main.js")
    if '"hh.pause"' not in self_text:
        errors.append("official Pause test must call live hh.pause")
    return errors


def make_project(prefix: str = "hh-r2wp5-") -> Path:
    root = Path(tempfile.mkdtemp(prefix=prefix))
    (root / "project.godot").write_text("; r2-wp5 fixture\nconfig_version=5\n", encoding="utf-8")
    (root / "assets").mkdir()
    return root


def git_init_clean(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "project.godot"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=r2wp5@example.invalid", "-c", "user.name=r2wp5", "commit", "-m", "ckpt-base"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )


def try_junction(link: Path, target: Path) -> str:
    if os.name == "nt":
        proc = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and link.exists():
            return "junction"
        return ""
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except OSError:
        return ""


def find_pinned_godot() -> Path | None:
    if not GODOT_PIN.is_file():
        return None
    pin = json.loads(GODOT_PIN.read_text(encoding="utf-8"))
    engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    if str(engine.get("version_id", "")) != PINNED_VERSION:
        return None
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    exe = (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64_console.exe"
    )
    return exe if exe.is_file() else None


def test_path_escape(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    cases: list[str] = []
    outside = Path(tempfile.mkdtemp(prefix="hh-r2wp5-out-"))
    secret = outside / "secret.txt"
    secret.write_text("outside", encoding="utf-8")
    corpus = [
        ("dotdot", "../secret.txt"),
        ("dotdot-res", "res://../secret.txt"),
        ("absolute-win", r"C:\Windows\notepad.exe" if os.name == "nt" else "/etc/passwd"),
        ("absolute-posix", "/etc/passwd"),
        ("device", "res://CON.txt"),
        ("reserved-nul", "NUL"),
        ("overlong", "a" * 300),
        ("locked-addon", "res://addons/hh_agent/plugin.gd"),
        ("locked-agent", ".hh-agent/policy.toml"),
        ("locked-lock", ".hh-agent/capability-lock.json"),
    ]
    for name, raw in corpus:
        got = harness("jail", {"project_root": str(root), "path": raw})
        cases.append(name)
        if got.get("ok") is True:
            errors.append(f"jail {name} should reject {raw!r}: {got}")
        elif (got.get("error") or {}).get("code") not in {"E_PATH", "E_POLICY"}:
            errors.append(f"jail {name} expected E_PATH/E_POLICY: {got}")
    ok = harness("jail", {"project_root": str(root), "path": "res://assets/ok.txt"})
    if ok.get("ok") is not True:
        errors.append(f"in-jail asset path must pass: {ok}")
    link_kind = try_junction(root / "escape", outside)
    if link_kind:
        cases.append(link_kind)
        escaped = harness("jail", {"project_root": str(root), "path": "escape/secret.txt"})
        if escaped.get("ok") is True:
            errors.append(f"{link_kind} escape was allowed: {escaped}")
    else:
        cases.append("junction/symlink-skipped")
    escape = root / "escape"
    if escape.exists() or escape.is_symlink():
        try:
            escape.rmdir()
        except OSError:
            try:
                escape.unlink()
            except OSError:
                pass
    shutil.rmtree(outside, ignore_errors=True)
    return errors, cases


def test_writer_and_drift(root: Path) -> list[str]:
    errors: list[str] = []
    target = root / "assets" / "leased.txt"
    target.write_text("v1", encoding="utf-8")
    first = harness("writer", {"project_root": str(root), "writer_id": "writer-a", "ttl_ms": 8000})
    if first.get("ok") is not True:
        return [f"first writer failed: {first}"]
    hold = subprocess.Popen(
        [
            sess.node(),
            str(HARNESS),
            "writer-hold",
            json.dumps(
                {"project_root": str(root), "writer_id": "writer-a", "ttl_ms": 8000, "hold_ms": 2500}
            ),
        ],
        cwd=str(BRIDGE),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    lock = root / ".hh-agent" / "writer.lock"
    deadline = time.time() + 5.0
    while time.time() < deadline and not lock.is_file():
        time.sleep(0.02)
    second = harness("writer", {"project_root": str(root), "writer_id": "writer-b", "ttl_ms": 8000})
    if (second.get("error") or {}).get("code") != "E_BUSY":
        errors.append(f"second writer must be E_BUSY: {second}")
    hold.terminate()
    try:
        hold.wait(timeout=3)
    except subprocess.TimeoutExpired:
        hold.kill()
    leased = harness(
        "lease",
        {"project_root": str(root), "writer_id": "writer-a", "path": "res://assets/leased.txt", "ttl_ms": 8000},
    )
    if leased.get("ok") is not True:
        errors.append(f"lease acquire failed: {leased}")
        return errors
    target.write_text("human-edit", encoding="utf-8")
    drifted = harness(
        "lease",
        {"project_root": str(root), "writer_id": "writer-a", "path": "res://assets/leased.txt", "ttl_ms": 8000},
    )
    if (drifted.get("error") or {}).get("code") != "E_CONFLICT":
        errors.append(f"human-edit drift must be E_CONFLICT: {drifted}")
    return errors


def test_checkpoint(root: Path) -> list[str]:
    errors: list[str] = []
    asset = root / "assets" / "tmp_PLACEHOLDER.png"
    asset.write_bytes(b"png-bytes")
    (root / "scenes").mkdir(exist_ok=True)
    (root / "scenes" / "ref.tscn").write_text(
        '[gd_scene]\n[node name="X"]\ntexture = "res://assets/tmp_PLACEHOLDER.png"\n',
        encoding="utf-8",
    )
    git_init_clean(root)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=r2wp5@example.invalid", "-c", "user.name=r2wp5", "commit", "-m", "assets"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    home = Path(tempfile.mkdtemp(prefix="hh-r2wp5-home-"))
    project_id = hashlib.sha256(os.urandom(16)).hexdigest()[:32]
    command_id = new_ulid()
    submitted = harness(
        "submit",
        {
            "home": str(home),
            "project_id": project_id,
            "project_root": str(root),
            "actor": "writer-a",
            "writer_id": "writer-a",
            "policy": "OWNER_AUTOPILOT",
            "envelope": {
                "protocol": PROTOCOL,
                "command_id": command_id,
                "method": "godot.asset",
                "action": "delete",
                "params": {"path": "res://assets/tmp_PLACEHOLDER.png"},
            },
        },
    )
    err = (submitted.get("result") or {}).get("error") or {}
    row = submitted.get("ledger") or {}
    if err.get("code") != "E_UNVERIFIED":
        errors.append(f"OWNER destructive must stay unverified after checkpoint: {submitted}")
    if row.get("state") == "applying" or row.get("apply_count"):
        errors.append(f"destructive entered applying: {row}")
    if not asset.is_file():
        errors.append("hard-deleted the last referenced asset")
    after = row.get("after_summary") or ""
    if "checkpoint_id" not in str(after):
        errors.append(f"successful checkpoint not recorded: {row}")
    ckpt_dirs = list((root / ".hh-agent" / "checkpoints").glob("*")) if (root / ".hh-agent" / "checkpoints").is_dir() else []
    if not ckpt_dirs:
        errors.append("no checkpoint directory was written")
        shutil.rmtree(home, ignore_errors=True)
        return errors
    manifest = ckpt_dirs[0] / "manifest.json"
    if not manifest.is_file():
        errors.append("checkpoint missing manifest.json")
        shutil.rmtree(home, ignore_errors=True)
        return errors
    man = json.loads(manifest.read_text(encoding="utf-8"))
    if man.get("hard_delete_blocked") is not True:
        errors.append(f"referenced asset must block hard-delete: {man}")
    asset.write_bytes(b"killed")
    restored = harness("restore", {"manifest_path": str(manifest)})
    if restored.get("ok") is not True:
        errors.append(f"checkpoint restore failed: {restored}")
    if asset.read_bytes() != b"png-bytes":
        errors.append("restore did not return the quarantined bytes")

    blocked_root = make_project("hh-r2wp5-ckptfail-")
    victim = blocked_root / "assets" / "keep.bin"
    victim.write_bytes(b"keep")
    hh = blocked_root / ".hh-agent"
    hh.mkdir()
    (hh / "checkpoints").write_text("not-a-dir", encoding="utf-8")
    fail_id = new_ulid()
    failed = harness(
        "submit",
        {
            "home": str(home),
            "project_id": hashlib.sha256(os.urandom(16)).hexdigest()[:32],
            "project_root": str(blocked_root),
            "actor": "writer-a",
            "writer_id": "writer-a",
            "policy": "OWNER_AUTOPILOT",
            "envelope": {
                "protocol": PROTOCOL,
                "command_id": fail_id,
                "method": "godot.asset",
                "action": "delete",
                "params": {"path": "res://assets/keep.bin"},
            },
        },
    )
    ferr = (failed.get("result") or {}).get("error") or {}
    frow = failed.get("ledger") or {}
    if ferr.get("code") != "E_CHECKPOINT":
        errors.append(f"checkpoint flush failure must block: {failed}")
    if frow.get("state") == "applying":
        errors.append("checkpoint-fail command entered applying")
    if not victim.is_file() or victim.read_bytes() != b"keep":
        errors.append("checkpoint-fail still mutated the target")
    shutil.rmtree(blocked_root, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)
    return errors


def test_profiles(root: Path) -> list[str]:
    errors: list[str] = []
    (root / "assets" / "x.txt").write_text("x", encoding="utf-8")
    home = Path(tempfile.mkdtemp(prefix="hh-r2wp5-prof-"))
    destroy_params = {"path": "res://assets/x.txt"}
    for policy, expect in (("OBSERVE", "E_POLICY"), ("EDIT", "E_POLICY")):
        got = harness(
            "submit",
            {
                "home": str(home),
                "project_id": hashlib.sha256(os.urandom(8)).hexdigest()[:32],
                "project_root": str(root),
                "policy": policy,
                "approved_destructive": True,
                "envelope": {
                    "protocol": PROTOCOL,
                    "command_id": new_ulid(),
                    "method": "godot.asset",
                    "action": "delete",
                    "params": destroy_params,
                },
            },
        )
        code = ((got.get("result") or {}).get("error") or {}).get("code")
        if code != expect:
            errors.append(f"{policy} destructive expected {expect}, got {got}")
    edit_id = new_ulid()
    envelope = {
        "protocol": PROTOCOL,
        "command_id": edit_id,
        "method": "godot.asset",
        "action": "delete",
        "params": destroy_params,
    }
    minted = harness(
        "approve",
        {"project_root": str(root), "actor": "writer-a", "envelope": envelope},
    )
    if minted.get("ok") is not True or not minted.get("approval"):
        errors.append(f"approve bind failed: {minted}")
    bound = harness(
        "submit",
        {
            "home": str(home),
            "project_id": hashlib.sha256(os.urandom(8)).hexdigest()[:32],
            "project_root": str(root),
            "actor": "writer-a",
            "writer_id": "writer-a",
            "policy": "EDIT",
            "approval": minted.get("approval"),
            "envelope": envelope,
        },
    )
    bcode = ((bound.get("result") or {}).get("error") or {}).get("code")
    if bcode != "E_UNVERIFIED":
        errors.append(f"EDIT with issued bind must pass profile (E_UNVERIFIED): {bound}")
    forged = harness(
        "submit",
        {
            "home": str(home),
            "project_id": hashlib.sha256(os.urandom(8)).hexdigest()[:32],
            "project_root": str(root),
            "actor": "writer-a",
            "writer_id": "writer-a",
            "policy": "EDIT",
            "approval": "0" * 64,
            "envelope": {
                "protocol": PROTOCOL,
                "command_id": new_ulid(),
                "method": "godot.asset",
                "action": "delete",
                "params": destroy_params,
            },
        },
    )
    if ((forged.get("result") or {}).get("error") or {}).get("code") != "E_POLICY":
        errors.append(f"forged approval token must be E_POLICY: {forged}")
    defaulted = harness("default-policy", {})
    if defaulted.get("default_policy") != "OWNER_AUTOPILOT" or defaulted.get("normalized_empty") != "OWNER_AUTOPILOT":
        errors.append(f"default policy must be OWNER_AUTOPILOT: {defaulted}")
    paused = harness(
        "submit",
        {
            "home": str(home),
            "project_id": hashlib.sha256(os.urandom(8)).hexdigest()[:32],
            "project_root": str(root),
            "policy": "OWNER_AUTOPILOT",
            "paused": True,
            "envelope": {
                "protocol": PROTOCOL,
                "command_id": new_ulid(),
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
    if ((paused.get("result") or {}).get("error") or {}).get("code") != "E_PAUSED":
        errors.append(f"paused mutate must be E_PAUSED: {paused}")
    shutil.rmtree(home, ignore_errors=True)
    return errors


def test_allowlist() -> list[str]:
    errors: list[str] = []
    shell = harness("allowlist", {"kind": "process", "file": "git", "argv": ["status"], "shell": True})
    if (shell.get("error") or {}).get("code") not in {"E_PATH", "E_POLICY"}:
        errors.append(f"shell:true must be rejected: {shell}")
    bad = harness("allowlist", {"kind": "process", "file": "cmd.exe", "argv": ["/c", "dir"]})
    if (bad.get("error") or {}).get("code") != "E_POLICY":
        errors.append(f"cmd.exe must be denied: {bad}")
    good = harness("allowlist", {"kind": "process", "file": "git", "argv": ["status"]})
    if good.get("ok") is not True:
        errors.append(f"git must be allowed: {good}")
    live_cmd = harness("supervisor", {"file": "cmd.exe", "argv": ["/c", "dir"]})
    if (live_cmd.get("error") or {}).get("code") != "E_POLICY":
        errors.append(f"live runSync cmd.exe must be E_POLICY: {live_cmd}")
    live_git = harness("supervisor", {"file": "git", "argv": ["--version"]})
    if live_git.get("ok") is not True:
        errors.append(f"live runSync git must be allowed: {live_git}")
    net = harness("allowlist", {"kind": "net", "host": "1.1.1.1"})
    if (net.get("error") or {}).get("code") != "E_BIND":
        errors.append(f"non-loopback host must be E_BIND: {net}")
    loop = harness("allowlist", {"kind": "net", "host": "127.0.0.1"})
    if loop.get("ok") is not True:
        errors.append(f"loopback must be allowed: {loop}")
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


def mcp_body(resp: dict) -> dict:
    body = (resp.get("result") or {}).get("structuredContent")
    return body if isinstance(body, dict) else {}


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    sorted_s = sorted(samples)
    idx = max(0, math.ceil(0.95 * len(sorted_s)) - 1)
    if idx >= len(sorted_s):
        idx = len(sorted_s) - 1
    return float(sorted_s[idx])


def test_pause() -> tuple[list[str], dict]:
    """Live sidecar hh.pause/hh.resume + dock-signal plugin _apply_pause. Not a bool flip."""
    errors: list[str] = []
    info: dict = {"sidecar_samples": [], "sidecar_p95": None, "plugin_p95": None, "godot_measured": False}
    tmp = make_project("hh-r2wp5-livepause-")
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    err_lines: list[str] = []
    plugin_events: list[dict] = []
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
        plugin_sock = sess.ws_connect(host, port)
        sess.ws_send_text(plugin_sock, json.dumps(sess.hello_payload(sid_project, secret)))
        hello_ok = json.loads(sess.ws_recv_text(plugin_sock))
        if hello_ok.get("ok") is not True:
            errors.append(f"live pause hello failed: {sess.redact(json.dumps(hello_ok), secret)}")

        def plugin_loop() -> None:
            try:
                while True:
                    msg = json.loads(sess.ws_recv_text(plugin_sock))
                    plugin_events.append(msg)
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
            except OSError:
                return

        threading.Thread(target=plugin_loop, daemon=True).start()
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
                            "clientInfo": {"name": "test-policy-pause", "version": "0"},
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            sess.readline_timeout(proc.stdout, 5.0)

        samples: list[float] = []
        req_id = 2
        for _ in range(40):
            before_pause = len(plugin_events)
            t0 = time.perf_counter()
            paused = mcp_body(mcp_call(proc, req_id, "hh.pause", {}))
            req_id += 1
            elapsed = (time.perf_counter() - t0) * 1000.0
            ack = paused.get("ack_ms")
            samples.append(float(ack) if isinstance(ack, (int, float)) else elapsed)
            if paused.get("paused") is not True or paused.get("state") != "draining":
                errors.append(f"live hh.pause did not ACK draining: {paused}")
            if "mutate-lane" not in (paused.get("cancelled_jobs") or []):
                errors.append(f"live hh.pause did not cancel mutate-lane: {paused}")
            deadline = time.time() + 2.0
            saw_plugin_pause = False
            while time.time() < deadline:
                extra = plugin_events[before_pause:]
                if any(m.get("type") == "pause" and m.get("paused") is True for m in extra):
                    saw_plugin_pause = True
                    break
                time.sleep(0.01)
            if not saw_plugin_pause:
                errors.append("sidecar hh.pause did not send plugin WS pause")
            resumed = mcp_body(mcp_call(proc, req_id, "hh.resume", {}))
            req_id += 1
            if resumed.get("paused") is True:
                errors.append(f"live hh.resume left gate paused: {resumed}")

        info["sidecar_samples"] = samples
        info["sidecar_p95"] = _p95(samples)
        if info["sidecar_p95"] > PAUSE_BUDGET_MS:
            errors.append(f"live sidecar Pause ACK p95 {info['sidecar_p95']} > {PAUSE_BUDGET_MS}")

        mcp_call(proc, req_id, "hh.pause", {})
        req_id += 1
        mutate = mcp_body(
            mcp_call(
                proc,
                req_id,
                "hh.command",
                {
                    "command_id": new_ulid(),
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
        )
        req_id += 1
        if (mutate.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"live paused mutate must be E_PAUSED: {mutate}")
        mcp_call(proc, req_id, "hh.resume", {})
        req_id += 1
        before_ws = len(plugin_events)
        sess.ws_send_text(plugin_sock, json.dumps({"type": "pause", "paused": True}))
        deadline = time.time() + 2.0
        saw_ack = False
        while time.time() < deadline:
            extra = plugin_events[before_ws:]
            if any(m.get("type") == "pause_ack" for m in extra):
                saw_ack = True
                break
            time.sleep(0.01)
        if not saw_ack:
            errors.append("plugin WS pause did not receive pause_ack")
        again = mcp_body(
            mcp_call(
                proc,
                req_id,
                "hh.command",
                {
                    "command_id": new_ulid(),
                    "method": "godot.asset",
                    "action": "delete",
                    "params": {"path": "res://assets/x.txt"},
                },
            )
        )
        if (again.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"plugin WS pause must E_PAUSED: {again}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live sidecar Pause failed: {type(exc).__name__}: {exc}")
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
        shutil.rmtree(tmp, ignore_errors=True)

    godot_errors, plugin_p95, godot_measured = test_godot_dock_pause()
    errors.extend(godot_errors)
    info["plugin_p95"] = plugin_p95
    info["godot_measured"] = godot_measured
    return errors, info


def test_godot_dock_pause() -> tuple[list[str], float | None, bool]:
    """Measure plugin.gd _apply_pause via the health-dock signal on a live sidecar."""
    errors: list[str] = []
    exe = find_pinned_godot()
    if exe is None:
        return ["Godot pin missing; dock Pause wire bench is required"], None, False
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    godot_lines: list[str] = []
    err_lines: list[str] = []
    plugin_p95: float | None = None
    try:
        proc = subprocess.Popen(
            [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(PLUGIN_PROJECT)],
            cwd=str(BRIDGE),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()
        desc_path, desc = sess.find_descriptor(proc.pid)
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
                            "clientInfo": {"name": "test-policy-dock", "version": "0"},
                        },
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            sess.readline_timeout(proc.stdout, 5.0)
        env = os.environ.copy()
        env["HH_PAUSE_WIRE_BENCH"] = "1"
        env.pop("HH_AGENT_SELFTEST", None)
        godot = subprocess.Popen(
            [str(exe), "--headless", "--editor", "--path", str(PLUGIN_PROJECT)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        def drain_out() -> None:
            if godot is None or godot.stdout is None:
                return
            for line in godot.stdout:
                godot_lines.append(line)

        threading.Thread(target=drain_out, daemon=True).start()
        threading.Thread(target=sess.drain_stderr, args=(godot, godot_lines), daemon=True).start()
        blob = ""
        deadline = time.time() + 30.0
        while time.time() < deadline:
            joined = "".join(godot_lines)
            for line in joined.splitlines():
                if "HH_PAUSE_WIRE " in line:
                    blob = line.split("HH_PAUSE_WIRE ", 1)[1].strip()
                    break
            if blob:
                break
            if godot.poll() is not None or (proc and proc.poll() is not None):
                break
            time.sleep(0.1)
        if not blob:
            errors.append(f"Godot dock Pause wire produced no HH_PAUSE_WIRE: {''.join(godot_lines)[-2000:]}")
            return errors, None, True
        parsed = json.loads(blob)
        plugin_p95 = parsed.get("p95")
        if "pause_requested" not in str(parsed.get("path", "")):
            errors.append(f"plugin Pause path is not dock signal: {parsed}")
        if not isinstance(plugin_p95, (int, float)) or float(plugin_p95) > PAUSE_BUDGET_MS:
            errors.append(f"plugin dock _apply_pause p95 {plugin_p95} > {PAUSE_BUDGET_MS}")
        time.sleep(0.25)
        paused = mcp_body(
            mcp_call(
                proc,
                2,
                "hh.command",
                {
                    "command_id": new_ulid(),
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
        )
        if (paused.get("error") or {}).get("code") != "E_PAUSED":
            errors.append(f"dock Pause must close sidecar gate (E_PAUSED): {paused}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Godot dock Pause failed: {type(exc).__name__}: {exc}")
    finally:
        if godot and godot.poll() is None:
            godot.terminate()
            try:
                godot.wait(timeout=8)
            except subprocess.TimeoutExpired:
                godot.kill()
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
    return errors, plugin_p95, True


def no_scene_write_errors(roots: list[Path]) -> list[str]:
    errors: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            found = list(root.rglob("*.tscn"))
        except OSError:
            continue
        for path in found:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "Node2D" in text and 'name = "X"' in text:
                errors.append(f"scene mutation leaked into {path}")
    return errors


def main() -> int:
    errors: list[str] = []
    pause_info: dict = {}
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())
    toml_rc = policy_validate.self_test()
    if toml_rc != 0:
        errors.append(f"policy_validate.self_test exited {toml_rc}")

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: policy", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    root = make_project()
    extra_roots: list[Path] = [root]
    try:
        jail_errors, jail_cases = test_path_escape(root)
        errors.extend(jail_errors)
        errors.extend(test_writer_and_drift(root))
        ckpt_root = make_project("hh-r2wp5-ckpt-")
        extra_roots.append(ckpt_root)
        errors.extend(test_checkpoint(ckpt_root))
        errors.extend(test_profiles(root))
        errors.extend(test_allowlist())
        pause_errors, pause_info = test_pause()
        errors.extend(pause_errors)
        errors.extend(no_scene_write_errors(extra_roots))
    finally:
        for item in extra_roots:
            shutil.rmtree(item, ignore_errors=True)

    if errors:
        print("FAIL: policy", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    samples = pause_info.get("sidecar_samples") or []
    print(
        "PASS: R0 TOML fixtures; path-escape corpus; concurrent E_BUSY; "
        "human-edit E_CONFLICT; checkpoint restore + fail-blocks; "
        f"live sidecar hh.pause p95={pause_info.get('sidecar_p95')}ms n={len(samples)} "
        f"(dock _apply_pause p95={pause_info.get('plugin_p95')}, "
        f"godot={pause_info.get('godot_measured')}); "
        "EDIT bind is actor/hash/revision; mutate never writes scenes; "
        "plan R2-WP5 still [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
