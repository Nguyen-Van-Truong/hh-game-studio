#!/usr/bin/env python3
"""R9-WP3: compatibility/update matrix — old/new lock, downgrade, copy, broken API.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R9-WP3 [ ]; CURRENT_VALID_WP=R9-WP3; progress stays 58/60.
Does not start R9-WP4. Does not start Superfighter.
Does not tick G6 or GX. Does not invent an API key. --provider plan stays.
Does not poke relic_reached. Does not regress kho-bi-an or R9-WP1/WP2 honesty.
No snake demo. No r7w6 trial. No secret material. No skip-PASS.
Does not invent Hyper-V. Does not stamp CLEAN_VM=proven on this Godot/Node machine.

Official verify (plan R9-WP3 Verify, Godot §7.3 sequential):
  kill leftover Godot first
  one sidecar / one --path
  old/new lock (candidate keeps the official pin; never write the repo lock)
  downgrade restores the old lock on the copy
  project migration copy (source untouched)
  minimal editor project (do not copytree plugin-project)
  strip .hh-agent from the broken fixture
  --import the editor project
  intentionally broken API fixture → Observe/Doctor only
  probe latest is non-blocking and not applied
  contract/E2E/visible/headless/export required before apply
  CLEAN_VM stays unproven; this Godot/Node machine is not a clean VM.
  not_g6=1

Labels: OLD_LOCK, NEW_LOCK, DOWNGRADE, MIGRATE, BROKEN_API, CLEAN_VM
"""

from __future__ import annotations

import importlib.util
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
import test_scene_lifecycle as life
import test_session as sess

PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
DOGFOOD = REPO_ROOT / "godot" / "dogfood" / "kho-bi-an"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
MINIMAL = REPO_ROOT / "godot" / "test-projects" / "minimal-2d"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
TOOLS = REPO_ROOT / "tools" / "godot"
COMPAT_PY = TOOLS / "compat.py"
MATRIX = TOOLS / "compatibility_matrix.json"
PROBE_FIXTURE = TOOLS / "probe_latest.fixture.json"
PLAYBOOK = REPO_ROOT / "docs" / "godot-agent" / "COMPATIBILITY.md"
REPO_LOCK = REPO_ROOT / ".hh-agent" / "capability-lock.json"
EXPORT_TOOL = TOOLS / "export_job.py"
BRIDGE = REPO_ROOT / "bridge"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
PINNED = "4.7.1-stable"
LABELS = ("OLD_LOCK", "NEW_LOCK", "DOWNGRADE", "MIGRATE", "BROKEN_API", "CLEAN_VM")
REQUIRED_PROVEN = ("OLD_LOCK", "NEW_LOCK", "DOWNGRADE", "MIGRATE", "BROKEN_API")
BROKEN_PROTOCOL = "hh-godot-agent/broken"


def official_home() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        raise RuntimeError("LOCALAPPDATA missing")
    return Path(local) / "HHGodotAgent" / "compat" / "r9-wp3"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def emit(text: str) -> None:
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    stream.write("\n")


def load_export_job():
    spec = importlib.util.spec_from_file_location("export_job", EXPORT_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load export_job.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_compat():
    spec = importlib.util.spec_from_file_location("hh_compat", COMPAT_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load compat.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp3 = None
    g6 = None
    gx = None
    total = None
    r9_row = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R9-WP3\b", stripped):
            wp3 = stripped
        if "G6 RELEASE" in stripped or stripped.startswith("G6 "):
            if g6 is None:
                g6 = stripped
        if "GX FORK" in stripped or stripped.startswith("GX "):
            if gx is None:
                gx = stripped
        if stripped.startswith("Tiến độ tổng:") or stripped.startswith("Tien do tong:"):
            total = stripped
        if "| 9 |" in stripped and "G6" in stripped:
            r9_row = stripped
    if current != "R9-WP3":
        errors.append(f"CURRENT_VALID_WP={current!r} (must stay R9-WP3)")
    if wp3 is None:
        errors.append("plan missing R9-WP3 heading")
    elif re.search(r"\[x\]", wp3, re.I):
        errors.append("R9-WP3 must stay unticked")
    if total and "58/60" not in total:
        errors.append(f"progress must stay 58/60 while R9-WP3 is unticked: {total}")
    if r9_row and not re.search(r"\[\s*\]\s*2/4", r9_row):
        errors.append(f"R9 row must stay 2/4 while WP3 is unticked: {r9_row}")
    if g6 is not None and re.search(r"\[x\]", g6, re.I):
        errors.append("official harness must not tick G6")
    if gx is not None and re.search(r"\[x\]", gx, re.I):
        errors.append("official harness must not touch GX")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    for label in LABELS:
        if label not in self_text:
            errors.append(f"official test must label {label}")
    if "skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "Does not tick G6" not in self_text:
        errors.append("official test must refuse to tick G6")
    if "Does not tick GX" not in self_text:
        errors.append("official test must refuse to touch GX")
    if "does not start superfighter" not in self_text.lower():
        errors.append("official test must refuse Superfighter")
    if "does not invent an api key" not in self_text.lower():
        errors.append("official test must refuse invented API keys")
    if "--provider plan stays" not in self_text:
        errors.append("official test must keep --provider plan")
    if "does not poke relic_reached" not in self_text.lower():
        errors.append("official test must refuse to poke relic_reached")
    if "does not invent hyper-v" not in self_text.lower():
        errors.append("official test must refuse invented Hyper-V")
    if ("labels[\"CLEAN_VM\"]" + " = \"proven\"") in self_text or ("labels['CLEAN_VM']" + " = 'proven'") in self_text:
        errors.append("official test must not assign CLEAN_VM=proven")
    if "CLEAN_VM stays unproven" not in self_text:
        errors.append("official test must keep CLEAN_VM=unproven")
    if "kill leftover Godot first" not in self_text:
        errors.append("official test must kill leftover Godot first")
    if "one sidecar / one --path" not in self_text:
        errors.append("official test must keep one sidecar / one --path")
    if "minimal editor project" not in self_text:
        errors.append("official test must use a minimal editor project")
    if "do not copytree plugin-project" not in self_text:
        errors.append("official test must refuse copytree of plugin-project")
    if "strip .hh-agent" not in self_text:
        errors.append("official test must strip .hh-agent from the broken fixture")
    if "--import" not in self_text:
        errors.append("official test must --import the editor project")
    compact = re.sub(r"\s+", "", self_text)
    if ("copytree(" + "PLUGIN_PROJECT") in compact:
        errors.append("broken fixture must not copytree plugin-project")
    if "project migration copy" not in self_text:
        errors.append("official test must migrate a project copy")
    if "intentionally broken API fixture" not in self_text:
        errors.append("official test must include a broken API fixture")
    if "Observe/Doctor only" not in self_text:
        errors.append("official test must keep Observe/Doctor only")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if ("relic_reached" + " =") in self_text:
        errors.append("official test must not assign relic_reached")
    if not COMPAT_PY.is_file():
        errors.append("missing tools/godot/compat.py")
    else:
        compat_text = COMPAT_PY.read_text(encoding="utf-8")
        for needle in (
            "Observe/Doctor only",
            "non-blocking",
            "do-not-patch-vendor",
            "mid-session",
            "project migration copy",
            "CLEAN_VM stays unproven",
            "--provider plan stays",
            "Does not stamp CLEAN_VM as proven",
            "minimal editor project",
            "do not copytree plugin-project",
            "strip .hh-agent",
        ):
            if needle not in compat_text:
                errors.append(f"compat.py must mention {needle}")
        if "CLEAN_VM=proven" in compat_text:
            errors.append("compat.py must not stamp CLEAN_VM=proven")
    if not MATRIX.is_file():
        errors.append("missing compatibility_matrix.json")
    else:
        matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
        ids = [
            str(item.get("id"))
            for item in (matrix.get("required_suites_before_patch_or_minor") or [])
            if isinstance(item, dict)
        ]
        for suite in ("contract", "e2e", "visible", "headless", "export"):
            if suite not in ids:
                errors.append(f"matrix must require {suite} before upgrade")
        if matrix.get("auto_apply") is not False:
            errors.append("matrix auto_apply must be false")
        if matrix.get("probe_latest") != "non-blocking":
            errors.append("matrix probe_latest must be non-blocking")
    if not PLAYBOOK.is_file():
        errors.append("missing docs/godot-agent/COMPATIBILITY.md")
    else:
        play = PLAYBOOK.read_text(encoding="utf-8")
        for needle in (
            "Observe/Doctor only",
            "non-blocking",
            "--provider plan stays",
            "CLEAN_VM stays unproven",
            "do-not-patch-vendor",
            "minimal editor project",
            "--import",
        ):
            if needle not in play:
                errors.append(f"COMPATIBILITY.md must mention {needle}")
    if not (ADDON / "core" / "hh_compat.gd").is_file():
        errors.append("missing hh_compat.gd")
    else:
        compat_gd = (ADDON / "core" / "hh_compat.gd").read_text(encoding="utf-8")
        if "Observe/Doctor only" not in compat_gd:
            errors.append("hh_compat.gd must say Observe/Doctor only")
    router = (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8")
    if "observe_only_reason" not in router:
        errors.append("router must gate mutations on observe_only_reason")
    engine = (REPO_ROOT / "bridge" / "src" / "policy" / "engine.ts").read_text(encoding="utf-8")
    if "observeOnlyReason" not in engine:
        errors.append("sidecar mutation gate must call observeOnlyReason")
    if (REPO_ROOT / "godot" / "superfighter").exists() or (REPO_ROOT / "godot" / "dogfood" / "superfighter").exists():
        errors.append("must not start a Superfighter folder")
    return errors


def banner_for(labels: dict[str, str]) -> str:
    return "; ".join(f"{k}={labels[k]}" for k in LABELS)


def leftover_count(export_job, project: Path) -> int:
    return int(export_job.leftover_godot_count(project))


def kill_project(export_job, project: Path) -> int:
    export_job.kill_godot_for_project(project)
    n = leftover_count(export_job, project)
    if n != 0:
        export_job.kill_godot_for_project(project)
        n = leftover_count(export_job, project)
    return n


def kill_known(export_job, extra: list[Path] | None = None) -> int:
    leftover = 0
    leftover += kill_project(export_job, DOGFOOD)
    leftover += kill_project(export_job, PLUGIN_PROJECT)
    leftover += kill_project(export_job, MINIMAL)
    for path in extra or []:
        leftover += kill_project(export_job, path)
    export_job.kill_leftover_game()
    return leftover


def drain_leftover(export_job, extra: list[Path] | None = None, attempts: int = 8) -> int:
    leftover = 0
    for _ in range(attempts):
        leftover = kill_known(export_job, extra)
        if leftover == 0:
            return 0
        time.sleep(0.35)
    return leftover


def run_godot_quit(exe: Path, args: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    return subprocess.run(
        [str(exe), *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def find_pinned_godot() -> tuple[Path | None, str]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None, "LOCALAPPDATA missing"
    exe = (
        Path(local)
        / "HHGodotAgent"
        / "tooling"
        / "godot-4.7.1-stable"
        / "bin"
        / "Godot_v4.7.1-stable_win64_console.exe"
    )
    if not exe.is_file():
        return None, "pinned 4.7.1-stable console exe is not installed"
    return exe, PINNED_VERSION


def start_sidecar(project: Path):
    proc = subprocess.Popen(
        [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(project)],
        cwd=str(BRIDGE / "dist"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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
                    "clientInfo": {"name": "test-compat-update", "version": "0"},
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


def start_godot(exe: Path, project: Path):
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    godot = subprocess.Popen(
        [str(exe), "--headless", "--editor", "--path", str(project)],
        cwd=str(project),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    lines: list[str] = []

    def drain_out() -> None:
        if godot.stdout is None:
            return
        for line in godot.stdout:
            lines.append(line)

    threading.Thread(target=drain_out, daemon=True).start()
    threading.Thread(target=sess.drain_stderr, args=(godot, lines), daemon=True).start()
    return godot, lines


def wait_hello(proc: subprocess.Popen[str], godot: subprocess.Popen[str], req_id: int) -> tuple[int, bool, dict]:
    deadline = time.time() + 90.0
    last: dict = {}
    while time.time() < deadline:
        if godot.poll() is not None or proc.poll() is not None:
            break
        try:
            last = life.body_of(life.mcp_call(proc, req_id, "hh.plugin_noop", {}, timeout=8.0))
        except TimeoutError:
            time.sleep(0.25)
            continue
        req_id += 1
        if last.get("ok") is True and (last.get("postcondition") or {}).get("checks") == ["noop"]:
            return req_id, True, last
        time.sleep(0.25)
    return req_id, False, last


def stop_proc(proc: subprocess.Popen[str] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def tool_call(
    proc: subprocess.Popen[str],
    req_id: int,
    tool: str,
    action: str,
    params: dict,
    timeout: float = 40.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = life.mcp_call(proc, req_id, tool, {"action": action, "params": params, "command_id": cid}, timeout)
    return req_id + 1, life.body_of(resp)


def doctor_call(proc: subprocess.Popen[str], req_id: int) -> tuple[int, dict]:
    resp = life.mcp_call(proc, req_id, "hh.doctor", {}, timeout=20.0)
    return req_id + 1, life.body_of(resp)


def plant_live_session(project: Path) -> Path:
    local = os.environ.get("LOCALAPPDATA") or ""
    dest = Path(local) / "HHGodotAgent" / "sessions" / ("c" * 32) / "session.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {
                "protocol": "hh-godot-agent/1",
                "project_id": "c" * 32,
                "project_root": str(project.resolve()),
                "host": "127.0.0.1",
                "port": 1,
                "pid": 1,
                "started_at": "2026-08-26T00:00:00Z",
                "token": "0" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return dest


def main() -> int:
    labels = {key: "unproven" for key in LABELS}
    labels["CLEAN_VM"] = "unproven"
    errors: list[str] = []
    leftover = -1
    official_cmd = (
        f"python {rel(Path(__file__))}  "
        f"# sequential: godot --headless --path <migration-copy> --quit ; "
        f"godot --headless --editor --path <broken-api-copy> --import --quit ; "
        f"one sidecar / one --path: godot --headless --editor --path <broken-api-copy>"
    )
    if not PLAN.is_file():
        emit("FAIL: R9-WP3 compatibility matrix; missing plan")
        return 1
    plan_text = PLAN.read_text(encoding="utf-8")
    errors.extend(plan_errors(plan_text))
    errors.extend(src_scan_errors())
    if not os.environ.get("LOCALAPPDATA"):
        errors.append("LOCALAPPDATA missing; official home cannot be LocalAppData compat")
    if errors:
        emit(f"FAIL: R9-WP3 compatibility matrix; {banner_for(labels)}")
        for item in errors:
            emit(f"  - {item}")
        return 1

    try:
        export_job = load_export_job()
        compat = load_compat()
    except (OSError, RuntimeError) as exc:
        emit(f"FAIL: R9-WP3 compatibility matrix; {banner_for(labels)}")
        emit(f"  - load tools: {exc}")
        return 1

    home = official_home()
    migrate_copy = home / "migrate-copy"
    broken_copy = home / "broken-api"
    leftover = drain_leftover(export_job, [migrate_copy, broken_copy] if home.exists() else None)
    if leftover != 0:
        emit(f"FAIL: R9-WP3 compatibility matrix; {banner_for(labels)}")
        emit(f"  - leftover Godot before start={leftover}")
        return 1

    if home.exists():
        shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True, exist_ok=True)

    old_lock = compat.load_json(REPO_LOCK)
    old_errors = compat.pin_ok(old_lock)
    if old_errors:
        errors.extend(old_errors)
    else:
        old_path = home / "old-lock.json"
        compat.dump_json(old_path, old_lock)
        if old_path.is_file() and compat.lock_godot(old_lock).get("version_id") == PINNED_VERSION:
            labels["OLD_LOCK"] = "proven"

    try:
        probe = compat.probe_latest(fixture=PROBE_FIXTURE, apply=False)
        if probe.get("approved") is True or probe.get("applied") is True or probe.get("blocking") is True:
            errors.append(f"probe must stay non-blocking/unapproved: {probe}")
        try:
            compat.probe_latest(fixture=PROBE_FIXTURE, apply=True)
            errors.append("probe --apply must be refused")
        except compat.CompatError:
            pass
    except compat.CompatError as exc:
        errors.append(f"probe: {exc}")

    mcp = compat.mcp_sync_review(REPO_ROOT)
    if not mcp.get("ok"):
        errors.append(f"mcp-sync: {mcp}")
    if mcp.get("reapplied"):
        errors.append("mcp-sync must not reapply a vendor patch queue")

    new_lock = compat.candidate_lock(old_lock)
    new_path = home / "new-lock.json"
    compat.dump_json(new_path, new_lock)
    if (
        compat.lock_revision(new_lock) > compat.lock_revision(old_lock)
        and compat.lock_godot(new_lock).get("version_id") == PINNED_VERSION
        and compat.pin_ok(new_lock) == []
        and new_path.is_file()
    ):
        labels["NEW_LOCK"] = "proven"
    else:
        errors.append("new lock must bump revision without changing the Godot pin")

    try:
        compat.refuse_apply(lock_path=REPO_LOCK, suites_path=None, project=None, approved=False)
        errors.append("apply must refuse the live repo lock")
    except compat.CompatError as exc:
        if "refuse" not in str(exc).lower() and "missing suites" not in str(exc).lower():
            errors.append(f"apply refuse wording: {exc}")

    planted_session = plant_live_session(migrate_copy)
    try:
        compat.refuse_apply(
            lock_path=new_path,
            suites_path=None,
            project=migrate_copy,
            approved=False,
        )
        errors.append("mid-session apply must be refused")
    except compat.CompatError as exc:
        if "mid-session" not in str(exc):
            errors.append(f"mid-session refuse: {exc}")
    finally:
        if planted_session.exists():
            planted_session.unlink()
        if planted_session.parent.exists():
            shutil.rmtree(planted_session.parent, ignore_errors=True)

    if not MINIMAL.is_dir():
        errors.append("missing minimal-2d fixture")
    else:
        try:
            migrated = compat.migrate_copy(MINIMAL, migrate_copy, new_lock)
            dest_lock = migrate_copy / ".hh-agent" / "capability-lock.json"
            if not dest_lock.is_file():
                errors.append("migration copy missing new lock")
            elif (MINIMAL / ".hh-agent" / "capability-lock.json").is_file():
                errors.append("migration must not plant a lock on the source fixture")
            elif compat.lock_revision(compat.load_json(dest_lock)) != compat.lock_revision(new_lock):
                errors.append("migration copy lock revision mismatch")
            elif not migrated.get("source_untouched"):
                errors.append("migration reported a mutated source")
            else:
                exe, ver = find_pinned_godot()
                if exe is None:
                    errors.append(ver)
                else:
                    headless = subprocess.run(
                        [str(exe), "--headless", "--path", str(migrate_copy), "--quit"],
                        cwd=str(migrate_copy),
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=90,
                    )
                    leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
                    if leftover != 0:
                        errors.append(f"leftover Godot after migrate headless={leftover}")
                    elif headless.returncode != 0:
                        errors.append(f"migrate headless --quit failed: {headless.stderr[-400:]}")
                    else:
                        labels["MIGRATE"] = "proven"
        except (compat.CompatError, OSError, subprocess.TimeoutExpired) as exc:
            leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
            errors.append(f"migrate: {exc}")

    if migrate_copy.is_dir():
        try:
            down = compat.downgrade_lock(migrate_copy, old_lock)
            restored = compat.load_json(migrate_copy / ".hh-agent" / "capability-lock.json")
            if (
                down.get("ok")
                and compat.lock_revision(restored) == compat.lock_revision(old_lock)
                and compat.lock_godot(restored).get("version_id") == PINNED_VERSION
            ):
                labels["DOWNGRADE"] = "proven"
            else:
                errors.append(f"downgrade did not restore old lock: {down}")
        except compat.CompatError as exc:
            errors.append(f"downgrade: {exc}")

    exe, ver = find_pinned_godot()
    if exe is None:
        errors.append(ver)
    else:
        built = subprocess.run(
            [sess.npm(), "run", "build"],
            cwd=str(BRIDGE),
            text=True,
            capture_output=True,
            check=False,
        )
        if built.returncode != 0:
            errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        else:
            leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
            if leftover != 0:
                errors.append(f"leftover Godot before broken fixture={leftover}")
            else:
                try:
                    planted = compat.stage_broken_editor(broken_copy, ADDON)
                    if (
                        not planted.get("ok")
                        or planted.get("protocol") != BROKEN_PROTOCOL
                        or planted.get("minimal") is not True
                    ):
                        errors.append(f"stage-broken: {planted}")
                    agent_files = [
                        p for p in (broken_copy / ".hh-agent").rglob("*") if p.is_file()
                    ]
                    if len(agent_files) > 8:
                        errors.append(f"broken fixture .hh-agent is not minimal: {len(agent_files)}")
                    assessed = compat.assess_lock(broken_copy)
                    if not assessed.get("mismatch") or assessed.get("mode") != "Observe/Doctor only":
                        errors.append(f"broken fixture must be Observe/Doctor only: {assessed}")
                    sidecar_proc = None
                    godot_proc = None
                    try:
                        imported = run_godot_quit(
                            exe,
                            [
                                "--headless",
                                "--editor",
                                "--path",
                                str(broken_copy),
                                "--import",
                                "--quit",
                            ],
                            broken_copy,
                            180.0,
                        )
                        leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
                        if leftover != 0:
                            errors.append(f"leftover Godot after broken --import={leftover}")
                        elif leftover == 0:
                            sidecar_proc, _desc, secret, err_lines = start_sidecar(broken_copy)
                            godot_proc, godot_lines = start_godot(exe, broken_copy)
                            req_id, hello_ok, hello = wait_hello(sidecar_proc, godot_proc, 2)
                            if not hello_ok:
                                errors.append(
                                    f"broken fixture plugin_noop: {sess.redact(json.dumps(hello), secret)}"
                                )
                                if err_lines:
                                    errors.append(
                                        "sidecar: " + sess.redact("".join(err_lines[-8:]), secret)
                                    )
                                if godot_lines:
                                    errors.append(
                                        "godot: " + sess.redact("".join(godot_lines[-8:]), secret)
                                    )
                                if imported.returncode != 0:
                                    errors.append(
                                        f"broken --import exit {imported.returncode}: "
                                        f"{(imported.stderr or imported.stdout or '')[-400:]}"
                                    )
                            else:
                                req_id, doctor_body = doctor_call(sidecar_proc, req_id)
                                doctor_err = doctor_body.get("error") if isinstance(doctor_body, dict) else {}
                                doctor_skew = (doctor_err or {}).get("code") == "E_VERSION_SKEW"
                                if doctor_body.get("ok") is True:
                                    errors.append("hh.doctor must report lock/protocol mismatch")
                                elif not doctor_skew:
                                    errors.append(
                                        f"hh.doctor must be E_VERSION_SKEW: {sess.redact(json.dumps(doctor_body), secret)}"
                                    )
                                req_id, inspected = tool_call(
                                    sidecar_proc,
                                    req_id,
                                    "godot.project",
                                    "inspect",
                                    {"detail": "short"},
                                )
                                if inspected.get("ok") is not True:
                                    errors.append(
                                        f"Observe project.inspect must still work: {sess.redact(json.dumps(inspected), secret)}"
                                    )
                                req_id, mutated = tool_call(
                                    sidecar_proc,
                                    req_id,
                                    "godot.project",
                                    "settings",
                                    {
                                        "key": "application/config/name",
                                        "op": "set",
                                        "value": {
                                            "schema": "hh-godot-variant/1",
                                            "type": "string",
                                            "value": "broken-api",
                                        },
                                    },
                                )
                                mut_err = mutated.get("error") if isinstance(mutated, dict) else {}
                                mut_msg = str((mut_err or {}).get("message") or "")
                                mutate_skew = (mut_err or {}).get("code") == "E_VERSION_SKEW"
                                if mutated.get("ok") is True:
                                    errors.append("broken fixture must block mutate")
                                elif not mutate_skew:
                                    errors.append(
                                        f"mutate must be E_VERSION_SKEW: {sess.redact(json.dumps(mutated), secret)}"
                                    )
                                elif "Observe/Doctor only" not in mut_msg:
                                    errors.append(f"mutate message must say Observe/Doctor only: {mut_msg}")
                                elif doctor_skew and mutate_skew:
                                    labels["BROKEN_API"] = "proven"
                    finally:
                        stop_proc(godot_proc)
                        stop_proc(sidecar_proc)
                        leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
                        if leftover != 0:
                            errors.append(f"leftover Godot after broken fixture={leftover}")
                except (compat.CompatError, OSError, RuntimeError, TimeoutError) as exc:
                    leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
                    errors.append(f"broken API fixture: {exc}")

    leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
    if leftover != 0:
        errors.append(f"leftover Godot after verify={leftover}")
    if labels["CLEAN_VM"] == "proven":
        errors.append("must not stamp CLEAN_VM=proven on this Godot/Node machine")
    if (REPO_LOCK.read_text(encoding="utf-8").find("lock_revision") != -1) and "compat_note" in REPO_LOCK.read_text(
        encoding="utf-8"
    ):
        errors.append("must not write a candidate lock into the repo capability-lock")

    if errors or any(labels[key] != "proven" for key in REQUIRED_PROVEN) or labels["CLEAN_VM"] != "unproven":
        emit(f"FAIL: R9-WP3 compatibility matrix; {banner_for(labels)}")
        emit(f"  leftover_godot={leftover} not_g6=1 official={official_cmd}")
        for item in errors:
            emit(f"  - {item}")
        leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
        return 1

    leftover = drain_leftover(export_job, [migrate_copy, broken_copy])
    if leftover != 0:
        emit(f"FAIL: R9-WP3 compatibility matrix; {banner_for(labels)}")
        emit(f"  - leftover Godot={leftover}")
        return 1

    emit(f"PASS: R9-WP3 compatibility matrix; {banner_for(labels)}")
    emit(f"  official={official_cmd}")
    emit(
        f"  pin={PINNED} godot={PINNED_VERSION} leftover_godot=0 "
        f"probe=non-blocking mcp=do-not-patch-vendor"
    )
    emit(
        f"  home={home} smoke!=VM not_g6=1 HUMAN=unproven CLEAN_VM stays unproven"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
