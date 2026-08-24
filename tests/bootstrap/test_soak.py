#!/usr/bin/env python3
"""R7-WP5: Long-session soak, context compaction, resume (does not tick the plan).

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R7-WP5 [ ]; while unticked CURRENT_VALID_WP=R7-WP5; after tick allow R7-WP6+.
Must NOT lock [x] forever. Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable.
No skip-PASS. Does not start R7-WP6 or R8. Does not tick G4.
No snake demo. No R8 dogfood tree. No driver scripts for the snake demo.
Do not paper-ACK play.start.

Verify (encoded here; this file is the official harness):
  - DURATION: live sidecar+Godot+host wall clock >= 7200s. Remaining Play spread
    across the wait with periodic scene.read — not wake+sleep only.
    HH_SOAK_FAST must not prove DURATION. Sleep with no process is not duration.
  - RESTART3: sidecar, Godot editor, and agent/host at three distinct points; reconnect/version/hash
  - COMPACT: jailed r7w5 state resource; a new process reads task/command_id/brief/progress
    without the transcript (host --compact is not enough by itself)
  - NODUP: retry committed command_id is cached, not a second apply
  - LEAK: event/evidence/cache after rotate within the stated budget below;
    plus Godot/sidecar/host WorkingSet/private/handle samples after warmup
    must not explode (4x WS + 512MiB, or 5x handles + 2000).
    Godot RSS must be Godot_v4.7.1-stable_win64.exe, not the console wrapper.
  - EQUAL: final r7w5/soak slice equals uninterrupted r7w5/ref corpus
    after the live 2h wait (not only mid-session)
    (normalized node-name list + script sha256). Lost/duplicate nodes fail.
  - LIVE: plugin (Godot+sidecar) required. src_scan is not enough.
  - After compact, idle/wake/monitor stay running/idle/done — not blocked.

Honesty: 2h is wall-clock of the live session with host held and real reads/Play
spread across the wait, not deadline math and not wake+sleep only.
Play count is real processes (runtime reply hh_agent_runtime), not ok:true without a run.
Compaction is a state resource, not only --compact dropping a transcript flag.
Deterministic host/orchestrator state — not an LLM context window.

LEAK budgets (stated and enforced):
  events+rotated logs <= 2 MiB
  evidence dir        <= 4 MiB
  cache dir           <= 2 MiB
  current events.jsonl <= 256 lines after rotate
  cache files         <= 512
  rotate.json keeps checkpoint_refs
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_play_input as pin
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
HOST = REPO_ROOT / "host"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r7w5"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"

SOAK_JOB = "soak1"
SOAK_WALL_SEC = 7200
NODE_COUNT = 160
PLAY_COUNT = 20
# Stated LEAK budgets — same numbers as bridge/src/soak/types.ts
SOAK_EVENT_BUDGET_BYTES = 2 * 1024 * 1024
SOAK_EVIDENCE_BUDGET_BYTES = 4 * 1024 * 1024
SOAK_CACHE_BUDGET_BYTES = 2 * 1024 * 1024
SOAK_CACHE_MAX = 512
SOAK_EVENT_MAX_LINES = 256
GODOT_EDITOR_MIN_WS = 32 * 1024 * 1024
GODOT_EDITOR_IMAGE = "Godot_v4.7.1-stable_win64.exe"

PLAY_SCRIPT = 'extends "res://addons/hh_agent/runtime/hh_agent_runtime.gd"\n'

SLICE_SCRIPT = """extends Node2D

func _ready() -> void:
	pass
"""


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


def plan_errors(text: str) -> list[str]:
    """Keep R7-WP5 [ ]; while unticked require CURRENT_VALID_WP=R7-WP5."""
    errors: list[str] = []
    current = ""
    wp5 = None
    wp6 = None
    g4 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R7-WP5\b", stripped):
            wp5 = stripped
        if re.match(r"^R7-WP6\b", stripped):
            wp6 = stripped
        if "G4 AUTONOMY" in stripped or stripped.startswith("G4 "):
            if g4 is None:
                g4 = stripped
    if wp5 is None:
        return ["plan missing R7-WP5 heading"]
    ticked = bool(re.search(r"\[x\]", wp5, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp5:
            errors.append("R7-WP5 heading must keep [ ] until coordinator tick")
        if current != "R7-WP5":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP5 while WP5 is unticked)")
        if wp6 and re.search(r"\[x\]", wp6, re.IGNORECASE):
            errors.append("R7-WP6 must stay unticked; this WP does not start zero-touch autonomy")
    elif not re.match(r"^R7-WP([6-9]|\d{2,})$|^R[8-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R7-WP6+ after R7-WP5 tick)")
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
            errors.append(f"r7w5 leftover after cleanup: {leftovers[:8]}")
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
    for label in ("DURATION", "COMMANDS500", "PLAY20", "RESTART3", "COMPACT", "NODUP", "LEAK", "EQUAL"):
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
    if "does not start R7-WP6" not in self_text:
        errors.append("official test must refuse to start R7-WP6")
    if "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK play.start")
    if "HH_SOAK_FAST must not prove DURATION" not in self_text:
        errors.append("official test must encode that HH_SOAK_FAST must not prove DURATION")
    if "LEAK after the live 2h wait" not in self_text:
        errors.append("LEAK must be measured after the live 2h wait, not before idle wakes")
    if "soak_cached" not in self_text or "durable dedup" not in self_text:
        errors.append("NODUP must require ok+soak_cached durable replay")
    if "EQUAL at end of live 2h" not in self_text:
        errors.append("EQUAL must be proven after the live 2h wait")
    if "WorkingSetSize" not in self_text and "WorkingSet" not in self_text:
        errors.append("LEAK must sample process WorkingSet/private/handles")
    if "source_snapshot" not in self_text:
        errors.append("official must hash HEAD + soak source at start and end")
    if "execute.ts" not in self_text:
        errors.append("source_snapshot must include ledger execute.ts")
    if "not the console wrapper" not in self_text:
        errors.append("LEAK must sample the editor exe, not the console wrapper")
    if "remaining Play spread" not in self_text:
        errors.append("PLAY20 must spread remaining Play across the wait")
    live_src = self_text.split("def live_errors")[-1]
    if "agent host restarted and held" not in live_src:
        errors.append("DURATION wait must keep a live host after RESTART3")
    if re.search(r"time\.sleep\(\s*7200", live_src):
        errors.append("must not fake DURATION with time.sleep(7200) and no live processes")
    if "session://state" not in self_text:
        errors.append("official test must read session://state from a second process")
    if "hh_agent_runtime" not in self_text:
        errors.append("PLAY20 must require hh_agent_runtime")
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    gitignore = (PLUGIN_PROJECT / ".gitignore").read_text(encoding="utf-8")
    if "r7w5/" not in gitignore:
        errors.append("plugin-project .gitignore must ignore r7w5/")
    export_gd = (ADDON / "core" / "hh_export_plugin.gd").read_text(encoding="utf-8")
    if 'p.contains("/r7w5' not in export_gd and 'p.contains("r7w5' not in export_gd:
        errors.append("export _should_skip must contain() r7w5")
    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "r7w5" not in constants:
        errors.append("hh_constants must name r7w5")
    adapter = ADDON / "core" / "hh_soak_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_soak_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "r7w5" not in atext:
            errors.append("plugin soak adapter must jail under r7w5/")
        if ".tmp" not in atext:
            errors.append("plugin soak adapter must tmp+rename")
        if ".hh-agent" not in atext:
            errors.append("plugin soak adapter must refuse .hh-agent writes")
    host_compact = (HOST / "src" / "host.ts").read_text(encoding="utf-8")
    if "writeHostSoakResource" not in host_compact:
        errors.append("host --compact must write the jailed state resource")
    soak_ts = BRIDGE / "src" / "soak" / "store.ts"
    if not soak_ts.is_file():
        errors.append("missing soak/store.ts")
    else:
        stext = soak_ts.read_text(encoding="utf-8")
        if "renameSync" not in stext:
            errors.append("soak store must tmp+rename")
        if ".hh-agent" not in stext:
            errors.append("soak store must refuse locked .hh-agent writes")
        if "lookupSoakCached" not in stext:
            errors.append("soak store must cache command_ids across sidecar restart")
    resources = (BRIDGE / "src" / "resources" / "mcp_resources.ts").read_text(encoding="utf-8")
    if "session://state" not in resources:
        errors.append("MCP resources must list session://state")
    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "lookupSoakCached" not in execute:
        errors.append("ledger must return soak-cached command_ids (NODUP across sidecar restart)")
    if "handleSoakAction" not in execute:
        errors.append("ledger must dispatch job.compact")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "hh_soak_adapter" not in router:
        errors.append("router must dispatch job.compact through soak adapter")
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


def variant(typ: str, value) -> dict:
    return {"schema": "hh-godot-variant/1", "type": typ, "value": value}


def after_of(body: dict) -> dict:
    after = body.get("after") or {}
    return after if isinstance(after, dict) else {}


def tool_call(
    proc,
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 60.0,
    command_id: str | None = None,
) -> tuple[int, str, dict]:
    cid = command_id or life.new_ulid()
    resp = life.mcp_call(proc, req_id, method, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, cid, life.body_of(resp)


def mcp_rpc(proc, req_id: int, method: str, params: dict | None = None, timeout: float = 20.0) -> tuple[int, dict]:
    assert proc.stdin and proc.stdout
    proc.stdin.write(
        json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}) + "\n"
    )
    proc.stdin.flush()
    line = sess.readline_timeout(proc.stdout, timeout)
    return req_id + 1, json.loads(line)


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
    threading_drain(proc, err_lines)
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
                    "clientInfo": {"name": "test-soak", "version": "0"},
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


def threading_drain(proc: subprocess.Popen[str], err_lines: list[str]) -> None:
    import threading

    threading.Thread(target=sess.drain_stderr, args=(proc, err_lines), daemon=True).start()


def host_cmd(*args: str) -> list[str]:
    return [node(), str(HOST / "dist" / "main.js"), *args]


def run_host(args: list[str], env: dict[str, str], timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        host_cmd(*args),
        cwd=str(HOST),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
        env=env,
    )


def last_json(stdout: str) -> dict:
    parsed: dict = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
    return parsed


def start_host_held(session_id: str, task_id: str, command_id: str, env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        host_cmd(
            "--provider",
            "fake",
            "--mode",
            "persistent",
            "--hold-after-decision",
            "--session-id",
            session_id,
            "--task-id",
            task_id,
            "--command-id",
            command_id,
        ),
        cwd=str(HOST),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def slice_fingerprint(folder: str) -> dict:
    root = TEMP_DIR / folder
    names: list[str] = []
    scripts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_p = path.relative_to(root).as_posix()
        if path.suffix == ".gd":
            scripts[rel_p] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix == ".tscn":
            text = path.read_text(encoding="utf-8", errors="replace")
            names.extend(re.findall(r'name="(Node_\d+)"', text))
    names_sorted = sorted(names)
    payload = json.dumps({"names": names_sorted, "scripts": scripts}, sort_keys=True).encode("utf-8")
    return {
        "hash": hashlib.sha256(payload).hexdigest(),
        "names": names_sorted,
        "scripts": scripts,
        "count": len(names_sorted),
    }


def dir_bytes(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    total = 0
    for path in folder.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def node_names_on_disk(scene_rel: str) -> list[str]:
    path = PLUGIN_PROJECT / scene_rel
    if not path.is_file():
        return []
    return re.findall(r'name="(Node_\d+)"', path.read_text(encoding="utf-8", errors="replace"))


def file_sha(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot() -> dict[str, str]:
    """HEAD + soak product/harness bytes. Official start and end must match."""
    head = ""
    try:
        got = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        if got.returncode == 0:
            head = got.stdout.strip()
    except OSError:
        head = ""
    digest = hashlib.sha256()
    digest.update(head.encode("utf-8"))
    files: list[Path] = [
        Path(__file__).resolve(),
        REPO_ROOT / "host" / "src" / "soak_resource.ts",
        ADDON / "core" / "hh_soak_adapter.gd",
        BRIDGE / "src" / "ledger" / "execute.ts",
    ]
    soak_dir = BRIDGE / "src" / "soak"
    if soak_dir.is_dir():
        files.extend(sorted(p for p in soak_dir.rglob("*") if p.is_file()))
    for path in files:
        if not path.is_file():
            continue
        digest.update(rel(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return {"head": head, "tree": digest.hexdigest()}


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def win_process_entries() -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    if snap in (0, wintypes.HANDLE(-1).value):
        return []
    entry = _PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
    out: list[dict[str, object]] = []
    if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
        while True:
            out.append(
                {
                    "pid": int(entry.th32ProcessID),
                    "ppid": int(entry.th32ParentProcessID),
                    "name": str(entry.szExeFile),
                }
            )
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snap)
    return out


def godot_editor_pid(wrapper_pid: int) -> int:
    """Real editor exe, not the console wrapper."""
    if wrapper_pid <= 0:
        return 0
    entries = win_process_entries()
    want = GODOT_EDITOR_IMAGE.lower()
    self = next((row for row in entries if int(row["pid"]) == wrapper_pid), None)
    if self and str(self["name"]).lower() == want:
        return wrapper_pid
    for row in entries:
        if int(row["ppid"]) != wrapper_pid:
            continue
        if str(row["name"]).lower() == want:
            return int(row["pid"])
    for child in [row for row in entries if int(row["ppid"]) == wrapper_pid]:
        for row in entries:
            if int(row["ppid"]) == int(child["pid"]) and str(row["name"]).lower() == want:
                return int(row["pid"])
    return 0


def win_pid_image(pid: int) -> str:
    if os.name != "nt" or pid <= 0:
        return ""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return ""
    buf = ctypes.create_unicode_buffer(32768)
    size = wintypes.DWORD(32768)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    if not ok:
        return ""
    return Path(buf.value).name


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def win_pid_stats(pid: int) -> dict[str, int] | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        access = 0x0410  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        handle = kernel32.OpenProcess(access, False, int(pid))
        if not handle:
            handle = kernel32.OpenProcess(0x1000, False, int(pid))  # LIMITED
        if handle:
            counters = _PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS_EX)
            ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            handles = wintypes.DWORD(0)
            kernel32.GetProcessHandleCount(handle, ctypes.byref(handles))
            kernel32.CloseHandle(handle)
            if ok:
                return {
                    "ws": int(counters.WorkingSetSize),
                    "private": int(counters.PrivateUsage),
                    "handles": int(handles.value),
                    "image": win_pid_image(pid),
                }
        try:
            got = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        f"(Get-Process -Id {int(pid)} -ErrorAction Stop | "
                        "Select-Object WorkingSet64,PrivateMemorySize64,HandleCount | "
                        "ConvertTo-Json -Compress)"
                    ),
                ],
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )
            if got.returncode == 0 and got.stdout.strip():
                data = json.loads(got.stdout)
                return {
                    "ws": int(data.get("WorkingSet64") or 0),
                    "private": int(data.get("PrivateMemorySize64") or 0),
                    "handles": int(data.get("HandleCount") or 0),
                    "image": win_pid_image(pid),
                }
        except (OSError, json.JSONDecodeError, ValueError, subprocess.TimeoutExpired):
            return None
        return None
    status = Path(f"/proc/{int(pid)}/status")
    if not status.is_file():
        return None
    rss = 0
    text = status.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                rss = int(parts[1]) * 1024
    return {"ws": rss, "private": rss, "handles": 0, "image": ""}


def fmt_stats(st: dict | None) -> str:
    if not st:
        return "n/a"
    image = str(st.get("image") or "")
    extra = f" image={image}" if image else ""
    return f"ws={st['ws']} priv={st['private']} h={st['handles']}{extra}"


def rss_exploded(samples: list[dict], role: str) -> str | None:
    series = [row.get(role) for row in samples if isinstance(row.get(role), dict)]
    if len(series) < 4:
        return f"LEAK {role} samples={len(series)} (need >=4 WorkingSet samples after warmup)"
    warm = series[1]
    last = series[-1]
    if not isinstance(warm, dict) or not isinstance(last, dict):
        return f"LEAK {role} samples missing WorkingSet"
    ws0 = int(warm.get("ws") or 0)
    ws1 = int(last.get("ws") or 0)
    h0 = int(warm.get("handles") or 0)
    h1 = int(last.get("handles") or 0)
    if ws0 > 0 and ws1 > ws0 * 4 and (ws1 - ws0) > 512 * 1024 * 1024:
        return f"LEAK {role} WorkingSet exploded {ws0}->{ws1}"
    if h0 > 0 and h1 > h0 * 5 and (h1 - h0) > 2000:
        return f"LEAK {role} handles exploded {h0}->{h1}"
    return None


def write_jailed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def processes_up(
    proc: subprocess.Popen[str] | None,
    godot: subprocess.Popen[str] | None,
    host: subprocess.Popen[str] | None = None,
    require_host: bool = False,
) -> bool:
    if proc is None or proc.poll() is not None:
        return False
    if godot is None or godot.poll() is not None:
        return False
    if require_host and (host is None or host.poll() is not None):
        return False
    return True


def prove_play_runs(
    proc: subprocess.Popen[str],
    req_id: int,
    play_scene: str,
    applied: list[str],
    errors: list[str],
    label: str,
    already: int,
    reconnect=None,
    target: int | None = None,
) -> tuple[int, int]:
    """Real Play via plugin debug + hh_agent_runtime on the played scene (A10)."""
    play_ok = already
    want = PLAY_COUNT if target is None else target
    reconnects = 0
    try:
        while play_ok < want:
            req_id, start_cid, start_body = tool_call(
                proc,
                req_id,
                "godot.play",
                "start",
                {"scene": play_scene, "mode": "debug"},
                timeout=90.0,
            )
            after_start = after_of(start_body)
            if start_body.get("ok") is True and after_start.get("playing") is not True:
                errors.append(f"paper-ACK play.start {label} #{play_ok}: {start_body}")
                break
            if start_body.get("ok") is not True or after_start.get("is_playing_scene") is not True:
                msg = str((start_body.get("error") or {}).get("message") or "")
                if msg == "no plugin" and reconnect is not None and reconnects < 2:
                    reconnects += 1
                    req_id, ok = reconnect(req_id)
                    if ok:
                        print(f"soak: {label} replay after no-plugin reconnect #{reconnects}", flush=True)
                        continue
                errors.append(f"{label} play.start not proven: {start_body}")
                break
            if start_body.get("ok") is True:
                applied.append(start_cid)
            run_id = str(after_start.get("run_id") or "")
            if len(run_id) != 26:
                errors.append(f"{label} play.start missing run_id: {start_body}")
                break
            time.sleep(1.5)
            req_id, ready, tree_body = pin.wait_runtime_ready(proc, req_id, run_id)
            if not ready or after_of(tree_body).get("source") != "hh_agent_runtime":
                errors.append(f"{label} play #{play_ok} missing hh_agent_runtime: {tree_body}")
                try:
                    req_id, _cid, _ = tool_call(
                        proc, req_id, "godot.play", "stop", {"reason": "test", "run_id": run_id}, timeout=60.0
                    )
                except TimeoutError:
                    pass
                break
            play_ok += 1
            print(f"soak: {label} play {play_ok}/{PLAY_COUNT} run_id={run_id}", flush=True)
            req_id, stop_cid, stop_body = tool_call(
                proc, req_id, "godot.play", "stop", {"reason": "test", "run_id": run_id}, timeout=60.0
            )
            if stop_body.get("ok") is True:
                applied.append(stop_cid)
            time.sleep(0.3)
    except TimeoutError as exc:
        errors.append(f"{label} play MCP timeout: {exc}")
    return req_id, play_ok


def live_errors(exe: Path | None) -> tuple[list[str], dict[str, str]]:
    labels = {
        "LIVE": "unrun",
        "DURATION": "unproven",
        "COMMANDS500": "unproven",
        "PLAY20": "unproven",
        "RESTART3": "unproven",
        "COMPACT": "unproven",
        "NODUP": "unproven",
        "LEAK": "unproven",
        "EQUAL": "unproven",
    }
    errors: list[str] = []
    snap_start = source_snapshot()
    if exe is None:
        errors.append("pinned Godot required for LIVE soak")
        return errors, labels
    pin.kill_plugin_project_holders()
    time.sleep(1.0)
    if pin.plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, labels
    errors.extend(cleanup_temp())
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    skip_wait = os.environ.get("HH_SOAK_FAST") == "1"
    session_id = life.new_ulid()
    task_id = life.new_ulid()
    host_command_id = life.new_ulid()
    applied: list[str] = []
    play_ok = 0
    restarts = {"sidecar": 0, "editor": 0, "host": 0}
    nodup_ok = True
    compact_ok = False
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    host_proc: subprocess.Popen[str] | None = None
    used_headless = False
    secret = ""
    req_id = 2
    t0 = 0.0
    try:
        host_proc = start_host_held(session_id, task_id, host_command_id, env)
        time.sleep(1.0)
        proc, _desc, secret, _err = start_sidecar()
        godot, _glines = pin.start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            life.stop_proc(godot)
            godot = None
            time.sleep(1.0)
            pin.kill_plugin_project_holders(godot=True, node=False)
            time.sleep(1.0)
            godot, _glines = pin.start_godot(exe, headless=False)
            req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            life.stop_proc(godot)
            godot = None
            time.sleep(1.0)
            pin.kill_plugin_project_holders(godot=True, node=False)
            time.sleep(1.0)
            godot, _glines = pin.start_godot(exe, headless=True)
            used_headless = True
            req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(f"live plugin hello/noop failed: {sess.redact(json.dumps(last), secret)}")
            return errors, labels
        t0 = time.time()
        labels["LIVE"] = "plugin"
        editor_pid = 0

        def refresh_editor_pid() -> int:
            nonlocal editor_pid
            if godot is None:
                return editor_pid
            found = godot_editor_pid(godot.pid)
            if found:
                editor_pid = found
            return editor_pid

        refresh_editor_pid()
        print(
            f"soak: godot wrapper pid={godot.pid if godot else 0} "
            f"editor pid={editor_pid} image={win_pid_image(editor_pid)}",
            flush=True,
        )

        def reconnect_plugin(next_id: int) -> tuple[int, bool]:
            nonlocal godot
            if exe is None or proc is None:
                return next_id, False
            life.stop_proc(godot)
            godot = None
            time.sleep(1.0)
            pin.kill_plugin_project_holders(godot=True, node=False)
            time.sleep(1.0)
            godot, _glines = pin.start_godot(exe, headless=False)
            nxt, hello, _last = life.wait_hello(proc, godot, next_id)
            if hello:
                refresh_editor_pid()
                print("soak: Godot reconnected after no-plugin", flush=True)
                return nxt, True
            life.stop_proc(godot)
            godot = None
            return nxt, False

        def apply(
            method: str,
            action: str,
            params: dict,
            timeout: float = 60.0,
            command_id: str | None = None,
        ) -> dict:
            nonlocal req_id
            req_id, cid, body = tool_call(proc, req_id, method, action, params, timeout, command_id)
            msg = str((body.get("error") or {}).get("message") or "")
            if body.get("ok") is not True and msg == "no plugin":
                req_id, ok = reconnect_plugin(req_id)
                if ok:
                    req_id, cid, body = tool_call(proc, req_id, method, action, params, timeout, command_id)
            if body.get("ok") is True:
                applied.append(cid)
            return body

        def persist(op: str = "note", **extra: object) -> dict:
            params: dict = {
                "job_id": SOAK_JOB,
                "op": op,
                "session_id": session_id,
                "task_id": task_id,
                "command_id": host_command_id,
                "brief": "R7-WP5 soak corpus: 160 nodes + 20 play",
                "progress": {
                    "applied": len(set(applied)),
                    "play_runs": play_ok,
                    "next_step": len(set(applied)),
                    "restarts": dict(restarts),
                },
                "committed_command_ids": list(dict.fromkeys(applied)),
                "checkpoint_refs": [f"r7w5/{SOAK_JOB}/state.json"],
            }
            params.update(extra)
            return apply("godot.job", "compact", params)

        print(
            f"soak: live session started head={snap_start['head'][:12]} tree={snap_start['tree'][:12]}",
            flush=True,
        )
        persist("compact", phase="running")
        ref_scene = "res://r7w5/ref/Root.tscn"
        soak_scene = "res://r7w5/soak/Root.tscn"
        play_scene = "res://r7w5/play/Play.tscn"
        ref_script = "res://r7w5/ref/code.gd"
        soak_script = "res://r7w5/soak/code.gd"
        play_script = "res://r7w5/play/play.gd"
        if not PRODUCT_RUNTIME.is_file():
            errors.append("missing product hh_agent_runtime.gd for PLAY20")
            return errors, labels
        write_jailed(TEMP_DIR / "play" / "play.gd", PRODUCT_RUNTIME.read_text(encoding="utf-8"))
        for scene, script, contents in (
            (play_scene, play_script, None),
            (ref_scene, ref_script, SLICE_SCRIPT),
            (soak_scene, soak_script, SLICE_SCRIPT),
        ):
            created = apply("godot.scene", "create", {"path": scene, "root_class": "Node2D"})
            if created.get("ok") is not True:
                errors.append(f"scene.create {scene}: {created}")
                return errors, labels
            if contents is not None:
                written = apply("godot.script", "write", {"path": script, "contents": contents})
                if written.get("ok") is not True:
                    errors.append(f"script.write {script}: {written}")
                    return errors, labels
            apply("godot.scene", "open", {"path": scene})
            attached = apply("godot.script", "attach", {"scene": scene, "node_path": ".", "path": script})
            if attached.get("ok") is not True and scene == play_scene:
                written = apply("godot.script", "write", {"path": play_script, "contents": PLAY_SCRIPT})
                if written.get("ok") is not True:
                    errors.append(f"script.write play wrapper: {written}; attach={attached}")
                    return errors, labels
                attached = apply(
                    "godot.script", "attach", {"scene": play_scene, "node_path": ".", "path": play_script}
                )
            if attached.get("ok") is not True:
                errors.append(f"script.attach {script}: {attached}")
                return errors, labels
            apply("godot.scene", "save", {"path": scene})

        if used_headless:
            errors.append("GUI Godot required for PLAY20; headless fallback cannot prove hh_agent_runtime")
        else:
            req_id, play_ok = prove_play_runs(
                proc,
                req_id,
                play_scene,
                applied,
                errors,
                "early",
                play_ok,
                reconnect_plugin,
                target=PLAY_COUNT // 2,
            )

        first_soak_cid = ""
        expected_names = [f"Node_{i:03d}" for i in range(NODE_COUNT)]
        for i in range(NODE_COUNT):
            name = expected_names[i]
            added = apply(
                "godot.node",
                "add",
                {"scene": ref_scene, "parent": ".", "class_name": "Node2D", "name": name},
            )
            if added.get("ok") is not True:
                errors.append(f"ref node.add {name}: {added}")
                return errors, labels
        apply("godot.scene", "save", {"path": ref_scene})
        time.sleep(0.4)
        ref_fp = slice_fingerprint("ref")
        print(f"soak: ref corpus nodes={ref_fp['count']} applied={len(set(applied))}", flush=True)
        if ref_fp["names"] != expected_names or ref_fp["count"] != NODE_COUNT:
            errors.append(
                f"ref corpus incomplete names={len(ref_fp['names'])} (need {NODE_COUNT} {expected_names[0]}..{expected_names[-1]})"
            )
            return errors, labels

        def add_soak_node(i: int) -> str:
            name = f"Node_{i:03d}"
            before = len(applied)
            body = apply(
                "godot.node",
                "add",
                {"scene": soak_scene, "parent": ".", "class_name": "Node2D", "name": name},
            )
            if body.get("ok") is not True:
                errors.append(f"soak node.add {name}: {body}")
            return applied[-1] if len(applied) > before else ""

        for i in range(60):
            cid = add_soak_node(i)
            if i == 0:
                first_soak_cid = cid
        apply(
            "godot.property",
            "set",
            {
                "scene": soak_scene,
                "node_path": "Node_000",
                "property": "position",
                "value": variant("Vector2", {"x": 8, "y": 0}),
            },
        )
        apply("godot.scene", "save", {"path": soak_scene})
        before_side = list(node_names_on_disk("r7w5/soak/Root.tscn"))
        persist("compact", phase="running", scene_hash=file_sha(TEMP_DIR / "soak" / "Root.tscn"))

        # RESTART3 point 1 — sidecar
        life.stop_proc(proc)
        proc = None
        time.sleep(1.0)
        pin.kill_plugin_project_holders(godot=False, node=True)
        time.sleep(1.0)
        proc, _desc, secret, _err = start_sidecar()
        req_id = 2
        req_id, hello2, last2 = life.wait_hello(proc, godot, req_id)
        if not hello2:
            errors.append(f"sidecar restart hello failed: {last2}")
            return errors, labels
        restarts["sidecar"] = 1
        print("soak: sidecar restarted and reconnected", flush=True)
        req_id, _cid, ver_body = tool_call(proc, req_id, "godot.capabilities", "describe", {"kind": "version", "limit": 8})
        if PINNED_VERSION not in json.dumps(ver_body) and PINNED_VERSION not in json.dumps(after_of(ver_body)):
            if ver_body.get("ok") is not True:
                errors.append(f"version reconcile after sidecar restart: {ver_body}")
        req_id, read_id = mcp_rpc(proc, req_id, "resources/read", {"uri": "session://state"})
        contents = ((read_id.get("result") or {}).get("contents") or [])
        payload = {}
        if contents:
            try:
                payload = json.loads(str(contents[0].get("text") or "{}"))
            except json.JSONDecodeError:
                payload = {}
        if (
            payload.get("session_id") == session_id
            and payload.get("task_id") == task_id
            and payload.get("command_id") == host_command_id
            and payload.get("compacted") is True
            and payload.get("transcript") in ([], None)
            and payload.get("brief")
        ):
            compact_ok = True
        else:
            errors.append(f"COMPACT new sidecar session://state: {payload}")
        req_id, _cid, st = tool_call(proc, req_id, "godot.job", "status", {"job_id": SOAK_JOB})
        st_after = after_of(st)
        if st_after.get("task_id") != task_id or st_after.get("command_id") != host_command_id:
            errors.append(f"job.status after sidecar restart lost ids: {st}")
        if st_after.get("phase") == "blocked" or st_after.get("state") == "blocked":
            errors.append(f"status flipped blocked after sidecar restart: {st}")
        after_names = node_names_on_disk("r7w5/soak/Root.tscn")
        if after_names != before_side:
            errors.append(f"sidecar restart lost/changed soak nodes: {len(after_names)} vs {len(before_side)}")
        if first_soak_cid:
            req_id, _cid, replay = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": soak_scene, "parent": ".", "class_name": "Node2D", "name": "Node_000"},
                command_id=first_soak_cid,
            )
            replay_after = after_of(replay)
            replay_names = node_names_on_disk("r7w5/soak/Root.tscn")
            if replay.get("ok") is not True or replay_after.get("soak_cached") is not True:
                nodup_ok = False
                errors.append(
                    f"NODUP sidecar: replay must be ok+soak_cached (durable dedup), got {replay}"
                )
            elif replay_names.count("Node_000") != before_side.count("Node_000"):
                nodup_ok = False
                errors.append("NODUP sidecar: replay mutated Node_000 count")
            persist("note")

        for i in range(60, 120):
            add_soak_node(i)
        apply("godot.scene", "save", {"path": soak_scene})
        before_editor = list(node_names_on_disk("r7w5/soak/Root.tscn"))
        scene_hash_before = file_sha(TEMP_DIR / "soak" / "Root.tscn")
        persist("note", scene_hash=scene_hash_before)

        # RESTART3 point 2 — Godot editor
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        pin.kill_plugin_project_holders(godot=True, node=False)
        time.sleep(1.0)
        godot, _glines = pin.start_godot(exe, headless=False)
        req_id, hello3, last3 = life.wait_hello(proc, godot, req_id)
        if not hello3:
            life.stop_proc(godot)
            godot = None
            time.sleep(1.0)
            pin.kill_plugin_project_holders(godot=True, node=False)
            time.sleep(1.0)
            godot, _glines = pin.start_godot(exe, headless=False)
            req_id, hello3, last3 = life.wait_hello(proc, godot, req_id)
        if not hello3:
            life.stop_proc(godot)
            godot = None
            godot, _glines = pin.start_godot(exe, headless=True)
            used_headless = True
            req_id, hello3, last3 = life.wait_hello(proc, godot, req_id)
        if not hello3:
            errors.append(f"editor restart hello failed: {last3}")
            return errors, labels
        restarts["editor"] = 1
        refresh_editor_pid()
        print(
            f"soak: Godot editor restarted and reconnected editor pid={editor_pid} "
            f"image={win_pid_image(editor_pid)}",
            flush=True,
        )
        req_id, _cid, ver2 = tool_call(proc, req_id, "godot.capabilities", "describe", {"kind": "version", "limit": 8})
        if PINNED_VERSION not in json.dumps(ver2) and PINNED_VERSION not in json.dumps(after_of(ver2)):
            if ver2.get("ok") is not True:
                errors.append(f"version reconcile after editor restart: {ver2}")
        after_editor = node_names_on_disk("r7w5/soak/Root.tscn")
        if after_editor != before_editor:
            errors.append(f"editor restart lost soak nodes: {len(after_editor)} vs {len(before_editor)}")
        if first_soak_cid:
            count_before = after_editor.count("Node_000")
            req_id, _cid, replay2 = tool_call(
                proc,
                req_id,
                "godot.node",
                "add",
                {"scene": soak_scene, "parent": ".", "class_name": "Node2D", "name": "Node_000"},
                command_id=first_soak_cid,
            )
            replay2_after = after_of(replay2)
            count_after = node_names_on_disk("r7w5/soak/Root.tscn").count("Node_000")
            if replay2.get("ok") is not True or replay2_after.get("soak_cached") is not True:
                nodup_ok = False
                errors.append(
                    f"NODUP editor: replay must be ok+soak_cached (durable dedup), got {replay2}"
                )
            elif count_after != count_before:
                nodup_ok = False
                errors.append("NODUP editor: replay mutated Node_000 count")

        for i in range(120, NODE_COUNT):
            add_soak_node(i)
        for i in range(1, 80):
            apply(
                "godot.property",
                "set",
                {
                    "scene": soak_scene,
                    "node_path": f"Node_{i:03d}",
                    "property": "visible",
                    "value": variant("bool", True),
                },
            )
        apply("godot.scene", "save", {"path": soak_scene})
        for i in range(40):
            apply("godot.scene", "read", {"path": soak_scene, "detail": "short"})
            apply(
                "godot.property",
                "get",
                {"scene": soak_scene, "node_path": f"Node_{i:03d}", "property": "visible"},
            )

        persist("compact", phase="idle")
        soak_fp = slice_fingerprint("soak")
        # Mid-session snapshot only. EQUAL is proven after the live 2h wait.

        # RESTART3 point 3 — agent/host
        if host_proc is not None and host_proc.poll() is None:
            host_proc.terminate()
            try:
                host_proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                host_proc.kill()
        host_proc = None
        compact_host = run_host(
            ["--compact", session_id, "--project", str(PLUGIN_PROJECT), "--job-id", SOAK_JOB],
            env,
        )
        show_host = run_host(["--show", session_id], env)
        compact_body = last_json(compact_host.stdout)
        show_body = last_json(show_host.stdout)
        if (
            show_body.get("session_id") == session_id
            and show_body.get("task_id") == task_id
            and show_body.get("command_id") == host_command_id
            and show_body.get("compacted") is True
        ):
            restarts["host"] = 1
        else:
            errors.append(f"host restart --show lost ids: {show_body} {compact_host.stderr}")
        host_proc = start_host_held(session_id, task_id, host_command_id, env)
        print("soak: agent host restarted and held", flush=True)
        persist("wake", phase="idle")
        req_id, _cid, idle_st = tool_call(proc, req_id, "godot.job", "status", {"job_id": SOAK_JOB})
        idle_phase = str(after_of(idle_st).get("phase") or after_of(idle_st).get("state") or "")
        if idle_phase == "blocked":
            errors.append(f"idle/wake flipped blocked: {idle_st}")
        elif idle_phase not in {"running", "idle", "done"}:
            errors.append(f"idle status not running/idle/done: {idle_st}")

        if skip_wait and play_ok < PLAY_COUNT and not used_headless:
            apply("godot.scene", "open", {"path": play_scene})
            apply("godot.scene", "save", {"path": play_scene})
            req_id, play_ok = prove_play_runs(
                proc, req_id, play_scene, applied, errors, "fast", play_ok, reconnect_plugin
            )

        unique = len(set(applied))
        print(f"soak: unique_command_ids={unique} play_ok={play_ok} restarts={restarts}", flush=True)
        if restarts["sidecar"] == 1 and restarts["editor"] == 1 and restarts["host"] == 1:
            labels["RESTART3"] = "proven"
        else:
            errors.append(f"RESTART3 incomplete: {restarts}")
        if compact_ok:
            labels["COMPACT"] = "proven"
        if nodup_ok and first_soak_cid:
            labels["NODUP"] = "proven"
        elif nodup_ok:
            errors.append("NODUP unproven: missing first soak command_id")

        # DURATION: sidecar+Godot+host stay up. Remaining Play spread across the wait.
        # HH_SOAK_FAST must not prove DURATION.
        rss_samples: list[dict] = []
        tick = 0
        while True:
            elapsed = time.time() - t0
            if host_proc is None or host_proc.poll() is not None:
                host_proc = start_host_held(session_id, task_id, host_command_id, env)
                print("soak: host respawned during wait", flush=True)
            if not processes_up(proc, godot, host_proc, require_host=True):
                errors.append("live sidecar+Godot+host died before DURATION")
                break
            req_id, _cid, wake_body = tool_call(proc, req_id, "godot.job", "compact", {"job_id": SOAK_JOB, "op": "wake"})
            phase = str(after_of(wake_body).get("phase") or after_of(wake_body).get("state") or "")
            if phase == "blocked":
                errors.append(f"monitor flipped blocked while idle: {wake_body}")
                break
            apply(
                "godot.property",
                "get",
                {"scene": soak_scene, "node_path": "Node_000", "property": "visible"},
            )
            if play_ok < PLAY_COUNT and not used_headless and not skip_wait and tick % 12 == 11:
                apply("godot.scene", "open", {"path": play_scene})
                apply("godot.scene", "save", {"path": play_scene})
                req_id, play_ok = prove_play_runs(
                    proc,
                    req_id,
                    play_scene,
                    applied,
                    errors,
                    "spread",
                    play_ok,
                    reconnect_plugin,
                    target=play_ok + 1,
                )
            if tick % 12 == 0:
                persist("note")
            refresh_editor_pid()
            rss_samples.append(
                {
                    "t": elapsed,
                    "sidecar": win_pid_stats(proc.pid if proc is not None else 0),
                    "godot": win_pid_stats(editor_pid),
                    "host": win_pid_stats(host_proc.pid if host_proc is not None else 0),
                }
            )
            if tick % 10 == 0:
                last = rss_samples[-1]
                print(
                    f"soak: rss tick={tick} sidecar={fmt_stats(last['sidecar'])} "
                    f"godot={fmt_stats(last['godot'])} host={fmt_stats(last['host'])}",
                    flush=True,
                )
            tick += 1
            if skip_wait:
                break
            if elapsed >= SOAK_WALL_SEC:
                break
            time.sleep(30.0)
        elapsed = time.time() - t0
        live_up = processes_up(proc, godot, host_proc, require_host=True)
        if elapsed >= SOAK_WALL_SEC and live_up and not skip_wait:
            labels["DURATION"] = "proven"
        else:
            errors.append(
                f"DURATION live_wall={elapsed:.1f}s live_up={live_up} skip_wait={skip_wait} "
                "(HH_SOAK_FAST must not prove DURATION)"
            )

        unique = len(set(applied))
        print(f"soak: after wait unique_command_ids={unique} play_ok={play_ok}", flush=True)
        if unique >= 500:
            labels["COMMANDS500"] = "proven"
        else:
            errors.append(f"COMMANDS500 unique applied={unique} (need >=500)")
        if play_ok >= PLAY_COUNT:
            labels["PLAY20"] = "proven"
        else:
            errors.append(f"PLAY20 proven runs={play_ok} (need >=20 real hh_agent_runtime)")

        # LEAK after the live 2h wait — do not stamp proven from pre-idle sizes.
        ev = TEMP_DIR / SOAK_JOB / "logs"
        evidence = TEMP_DIR / SOAK_JOB / "evidence"
        cache = TEMP_DIR / SOAK_JOB / "cache"
        events_file = ev / "events.jsonl"
        rotate_index = ev / "rotate.json"
        event_bytes = dir_bytes(ev)
        evidence_bytes = dir_bytes(evidence)
        cache_bytes = dir_bytes(cache)
        cache_files = len(list(cache.glob("*.json"))) if cache.is_dir() else 0
        current_lines = 0
        if events_file.is_file():
            current_lines = len(
                [ln for ln in events_file.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            )
        rotate_refs: object = []
        if rotate_index.is_file():
            try:
                rotate_refs = json.loads(rotate_index.read_text(encoding="utf-8")).get("checkpoint_refs") or []
            except json.JSONDecodeError:
                rotate_refs = []
        leak_ok = (
            event_bytes <= SOAK_EVENT_BUDGET_BYTES
            and evidence_bytes <= SOAK_EVIDENCE_BUDGET_BYTES
            and cache_bytes <= SOAK_CACHE_BUDGET_BYTES
            and cache_files <= SOAK_CACHE_MAX
            and current_lines <= SOAK_EVENT_MAX_LINES
        )
        if not leak_ok:
            errors.append(
                f"LEAK over budget events={event_bytes} evidence={evidence_bytes} "
                f"cache={cache_bytes}/{cache_files} lines={current_lines}"
            )
        if not skip_wait:
            godot_series = [row.get("godot") for row in rss_samples if isinstance(row.get("godot"), dict)]
            if editor_pid <= 0:
                leak_ok = False
                errors.append("LEAK godot editor PID unresolved (console wrapper only)")
            for sample in godot_series:
                if not isinstance(sample, dict):
                    continue
                image = str(sample.get("image") or "")
                ws = int(sample.get("ws") or 0)
                if "_console" in image.lower():
                    leak_ok = False
                    errors.append(f"LEAK sampled console wrapper image={image}")
                    break
                if image and image.lower() != GODOT_EDITOR_IMAGE.lower():
                    leak_ok = False
                    errors.append(f"LEAK godot image {image!r} is not the editor exe, not the console wrapper")
                    break
                if ws and ws < GODOT_EDITOR_MIN_WS:
                    leak_ok = False
                    errors.append(
                        f"LEAK godot WorkingSet {ws} below editor floor {GODOT_EDITOR_MIN_WS} "
                        "(sampled console wrapper)"
                    )
                    break
            for role in ("sidecar", "godot", "host"):
                hole = rss_exploded(rss_samples, role)
                if hole:
                    leak_ok = False
                    errors.append(hole)
        if leak_ok:
            labels["LEAK"] = "proven"
        if rotate_index.is_file() and not isinstance(rotate_refs, list):
            errors.append("rotate.json lost checkpoint_refs")
        elif rotate_index.is_file() and isinstance(rotate_refs, list) and len(rotate_refs) == 0:
            errors.append("rotate.json checkpoint_refs empty after live wait")

        # EQUAL at end of live 2h — not only before the idle wait.
        final_soak = slice_fingerprint("soak")
        final_ref = slice_fingerprint("ref")
        if (
            final_soak["names"] == expected_names
            and final_ref["names"] == expected_names
            and final_soak["scripts"] == final_ref["scripts"]
            and final_soak["count"] == NODE_COUNT
            and len(set(final_soak["names"])) == NODE_COUNT
        ):
            labels["EQUAL"] = "proven"
        else:
            labels["EQUAL"] = "unproven"
            errors.append(
                f"EQUAL final soak!=ref names={len(final_soak['names'])}/{len(final_ref['names'])} "
                f"hash={final_soak['hash'][:8]} vs {final_ref['hash'][:8]}"
            )
        snap_end = source_snapshot()
        if snap_end != snap_start:
            errors.append(
                f"soak source changed during official "
                f"head={snap_start['head'][:12]}->{snap_end['head'][:12]} "
                f"tree={snap_start['tree'][:12]}->{snap_end['tree'][:12]}"
            )
    except Exception as exc:  # noqa: BLE001 — official harness records the hole
        errors.append(f"LIVE exception: {exc}")
    finally:
        if host_proc is not None:
            life.stop_proc(host_proc)
        life.stop_proc(godot)
        life.stop_proc(proc)
        pin.kill_plugin_project_holders(godot=True, node=True)
    return errors, labels


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
        print("FAIL: soak; LIVE=unrun")
        for item in errors:
            print(f"  - {item}")
        return 1
    host_built = subprocess.run(
        [npm(), "run", "build"],
        cwd=str(HOST),
        text=True,
        capture_output=True,
        check=False,
    )
    if host_built.returncode != 0:
        errors.append(f"host build failed:\n{host_built.stdout}\n{host_built.stderr}")
        print("FAIL: soak; LIVE=unrun")
        for item in errors:
            print(f"  - {item}")
        return 1

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    spec = actions.get("job.compact") if isinstance(actions.get("job.compact"), dict) else {}
    if spec.get("method") != "godot.job":
        errors.append("actions.json missing job.compact")

    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")

    live_errs, labels = live_errors(exe)
    errors.extend(live_errs)
    if labels["LIVE"] != "plugin":
        errors.append("LIVE path through plugin (Godot+sidecar) is required (src_scan is not enough)")
    for key in ("DURATION", "COMMANDS500", "PLAY20", "RESTART3", "COMPACT", "NODUP", "LEAK", "EQUAL"):
        if labels[key] != "proven":
            errors.append(f"{key} not proven")
    errors.extend(pin.project_godot_leak_errors("after official test"))
    pin.kill_plugin_project_holders(godot=True, node=True)
    time.sleep(1.0)
    banner = (
        f"LIVE={labels['LIVE']}; DURATION={labels['DURATION']}; COMMANDS500={labels['COMMANDS500']}; "
        f"PLAY20={labels['PLAY20']}; RESTART3={labels['RESTART3']}; COMPACT={labels['COMPACT']}; "
        f"NODUP={labels['NODUP']}; LEAK={labels['LEAK']}; EQUAL={labels['EQUAL']}"
    )
    if errors:
        print(f"FAIL: soak; {banner}")
        for item in errors:
            print(f"  - {item}")
        return 1
    print(f"PASS: soak; {banner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
