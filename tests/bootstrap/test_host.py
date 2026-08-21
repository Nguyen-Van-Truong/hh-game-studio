#!/usr/bin/env python3
"""R2-WP7: Agent Host session, fake model, kill/resume, E_EXTERNAL.

Executes (does not merely comment) a second host process after kill.
Stdlib only + the pinned host Node/tsc toolchain.
Does not tick the 20-8 plan. Does not apply scene mutations.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST = REPO_ROOT / "host"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
SESSION_MS = 90 * 60 * 1000
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DUMMY_CRED = "dummy-host-credential-r2wp7"
VENDOR_NEEDLES = (
    "godot_mcp",
    "MCPGameBridge",
    "satelliteoflove",
    "KeeVeeG",
    "keeveeg",
    "evaluate_expression",
    "call_method",
    "Object.callv",
)
SKIP_DIR_NAMES = {".git", "node_modules", "dist", "__pycache__", ".godot"}


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def node() -> str:
    return "node.exe" if os.name == "nt" else "node"


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


def plan_errors(text: str) -> list[str]:
    """Keep R2-WP7 [ ] while unticked; after coordinator tick allow R2-WP8+ / R3+."""
    errors: list[str] = []
    current = ""
    wp7 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP7\b", stripped):
            wp7 = stripped
    if wp7 is None:
        return ["plan missing R2-WP7 heading"]
    ticked = bool(re.search(r"\[x\]", wp7, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp7:
            errors.append("R2-WP7 heading must keep [ ] until coordinator tick")
        if current != "R2-WP7":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP7 while WP7 is unticked)")
    elif not re.match(r"^R2-WP([89]|\d{2,})$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP8+ / R3+ after R2-WP7 tick)")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    src = HOST / "src"
    if not src.is_dir():
        return ["missing host/src"]
    for path in src.rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        posix = rel(path)
        if "0.0.0.0" in text:
            errors.append(f"{posix} mentions 0.0.0.0")
        if "npx -y" in text:
            errors.append(f"{posix} uses npx -y")
        if "Math.random" in text:
            errors.append(f"{posix} uses Math.random")
        if "randomUUID" in text:
            errors.append(f"{posix} uses randomUUID")
        if re.search(r"\bfetch\s*\(", text):
            errors.append(f"{posix} uses fetch(")
        if re.search(r"shell\s*:\s*true", text):
            errors.append(f"{posix} uses shell:true")
        for needle in ("openai", "anthropic"):
            if needle in text.lower():
                errors.append(f"{posix} mentions {needle} SDK")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    pkg = json.loads((HOST / "package.json").read_text(encoding="utf-8"))
    deps: dict = {}
    if isinstance(pkg.get("dependencies"), dict):
        deps.update(pkg["dependencies"])
    if isinstance(pkg.get("devDependencies"), dict):
        deps.update(pkg["devDependencies"])
    allowed = {"typescript", "@types/node"}
    extra = set(deps) - allowed
    if extra:
        errors.append(f"host/package.json added extra dep {sorted(extra)}")
    if str((pkg.get("engines") or {}).get("node")) != "24.19.0":
        errors.append("host engines.node must be 24.19.0")
    return errors


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


def drain_stderr(proc: subprocess.Popen[str], bucket: list[str]) -> None:
    if proc.stderr is None:
        return
    for line in proc.stderr:
        bucket.append(line)


def wait_held_state(path: Path, timeout: float = 12.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        if path.is_file():
            try:
                last = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                last = {}
            inflight = last.get("inflight") if isinstance(last.get("inflight"), dict) else {}
            if last.get("phase") == "held_after_decision" and inflight.get("command_id"):
                return last
        time.sleep(0.05)
    raise TimeoutError(f"host did not persist in-flight state: {last}")


def grep_blob(root: Path, secret: str) -> list[str]:
    hits: list[str] = []
    if not secret or not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if secret in text:
            hits.append(str(path))
    return hits


def tool_key(row: dict) -> dict:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    err = result.get("error") if isinstance(result.get("error"), dict) else {}
    return {
        "task_id": row.get("task_id"),
        "command_id": row.get("command_id"),
        "tool": row.get("tool"),
        "action": row.get("action"),
        "ok": result.get("ok"),
        "error_code": err.get("code"),
    }


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    if not HOST.is_dir():
        errors.append("missing host/")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(src_scan_errors())

    node_exe = shutil.which(node())
    if node_exe is None:
        errors.append("node missing (FAIL, not skip-PASS)")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    npm_exe = shutil.which(npm())
    if npm_exe is None:
        errors.append("npm missing (FAIL, not skip-PASS)")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    installed = subprocess.run(
        [npm(), "install"],
        cwd=HOST,
        text=True,
        capture_output=True,
        check=False,
    )
    if installed.returncode != 0:
        errors.append(f"npm install failed:\n{installed.stdout}\n{installed.stderr}")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    built = subprocess.run(
        [npm(), "run", "build"],
        cwd=HOST,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if not (HOST / "dist" / "main.js").is_file():
        errors.append("host build missing dist/main.js")
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    tmp_local = Path(tempfile.mkdtemp(prefix="hh-r2wp7-local-"))
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_local)
    env.pop("HH_HOST_CREDENTIAL", None)
    env.pop("HH_HOST_MODEL", None)

    session_id = new_ulid()
    task_id = new_ulid()
    command_id = new_ulid()
    persist = tmp_local / "HHGodotAgent" / "hosts" / session_id / "state.json"

    try:
        full = run_host(
            [
                "--provider",
                "fake",
                "--mode",
                "persistent",
                "--session-id",
                session_id,
                "--task-id",
                task_id,
                "--command-id",
                command_id,
            ],
            env,
        )
        body = last_json(full.stdout)
        if full.returncode != 0 or body.get("ok") is not True:
            errors.append(f"fake host run failed: rc={full.returncode} {full.stdout} {full.stderr}")
        if body.get("session_id") != session_id or body.get("task_id") != task_id:
            errors.append(f"fake host ids drifted: {body}")
        if body.get("command_id") != command_id:
            errors.append(f"fake host command_id drifted: {body}")
        if int(body.get("session_ms") or 0) != SESSION_MS:
            errors.append(f"session_ms {body.get('session_ms')!r} != {SESSION_MS}")
        if int(body.get("deadline_at") or 0) - int(body.get("started_at") or 0) != SESSION_MS:
            errors.append("deadline_at != started_at + 90 minutes")
        tools = body.get("tools") if isinstance(body.get("tools"), list) else []
        if len(tools) < 2:
            errors.append(f"fake script must execute two tools: {tools}")
        else:
            if tools[0].get("tool") != "godot.project" or tools[0].get("action") != "inspect":
                errors.append(f"first tool must be godot.project inspect: {tools[0]}")
            if tools[1].get("tool") != "godot.editor" or tools[1].get("action") != "state":
                errors.append(f"second tool must be godot.editor state: {tools[1]}")
            for row in tools:
                if row.get("command_id") != command_id or row.get("task_id") != task_id:
                    errors.append(f"tool row ids drifted: {row}")
        if not persist.is_file():
            errors.append("persistent host did not write state.json under HHGodotAgent/hosts")
        else:
            disk = json.loads(persist.read_text(encoding="utf-8"))
            posix = persist.resolve().as_posix().lower()
            if "/hhgodotagent/hosts/" not in posix:
                errors.append(f"persist path is not under HHGodotAgent/hosts: {persist}")
            if "plugin-project" in posix:
                errors.append("persist path landed under plugin-project")
            if disk.get("command_id") != command_id or disk.get("task_id") != task_id:
                errors.append(f"disk state lost ids: {disk}")
            if int(disk.get("deadline_at") or 0) - int(disk.get("started_at") or 0) != SESSION_MS:
                errors.append("disk deadline is not a 90-minute session")
            if DUMMY_CRED in persist.read_text(encoding="utf-8"):
                errors.append("dummy credential written into state.json")

        interactive_session = new_ulid()
        inter = run_host(
            [
                "--provider",
                "fake",
                "--mode",
                "interactive",
                "--session-id",
                interactive_session,
                "--task-id",
                task_id,
                "--command-id",
                command_id,
            ],
            env,
        )
        inter_body = last_json(inter.stdout)
        if inter.returncode != 0 or inter_body.get("ok") is not True:
            errors.append(f"interactive host failed: {inter.stdout} {inter.stderr}")
        persistent_keys = [tool_key(row) for row in tools if isinstance(row, dict)]
        interactive_keys = [
            tool_key(row) for row in (inter_body.get("tools") or []) if isinstance(row, dict)
        ]
        if persistent_keys != interactive_keys:
            errors.append(
                "interactive and persistent hosts diverged: "
                f"{persistent_keys} vs {interactive_keys}"
            )

        kill_session = new_ulid()
        kill_task = new_ulid()
        kill_cmd = new_ulid()
        kill_path = tmp_local / "HHGodotAgent" / "hosts" / kill_session / "state.json"
        err_lines: list[str] = []
        proc = subprocess.Popen(
            host_cmd(
                "--provider",
                "fake",
                "--mode",
                "persistent",
                "--session-id",
                kill_session,
                "--task-id",
                kill_task,
                "--command-id",
                kill_cmd,
                "--hold-after-decision",
            ),
            cwd=str(HOST),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        threading.Thread(target=drain_stderr, args=(proc, err_lines), daemon=True).start()
        first_pid = proc.pid
        try:
            held = wait_held_state(kill_path)
        except TimeoutError as exc:
            errors.append(str(exc))
            held = {}
        if held.get("session_id") != kill_session:
            errors.append(f"held session_id drifted: {held}")
        if held.get("task_id") != kill_task or held.get("command_id") != kill_cmd:
            errors.append(f"held task/command drifted: {held}")
        inflight = held.get("inflight") if isinstance(held.get("inflight"), dict) else {}
        if inflight.get("command_id") != kill_cmd:
            errors.append(f"in-flight command_id not persisted: {inflight}")
        if inflight.get("tool") != "godot.project":
            errors.append(f"in-flight tool should be godot.project: {inflight}")
        if proc.poll() is not None:
            errors.append("hold process exited before kill (in-process flip, not a real hold)")

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if proc.poll() is None:
            errors.append("failed to kill held host process")
        time.sleep(0.1)

        resume = run_host(["--resume", kill_session], env)
        resume_body = last_json(resume.stdout)
        if resume.returncode != 0 or resume_body.get("ok") is not True:
            errors.append(f"resume host failed: rc={resume.returncode} {resume.stdout} {resume.stderr}")
        if resume_body.get("session_id") != kill_session:
            errors.append(f"resume session_id drifted: {resume_body}")
        if resume_body.get("task_id") != kill_task or resume_body.get("command_id") != kill_cmd:
            errors.append(f"resume task/command drifted: {resume_body}")
        resume_tools = resume_body.get("tools") if isinstance(resume_body.get("tools"), list) else []
        if len(resume_tools) < 2:
            errors.append(f"resume did not continue to tool B: {resume_tools}")
        else:
            if resume_tools[0].get("tool") != "godot.project":
                errors.append(f"resumed tool A missing: {resume_tools[0]}")
            if resume_tools[1].get("tool") != "godot.editor":
                errors.append(f"resumed tool B missing: {resume_tools[1]}")
            for row in resume_tools:
                if row.get("command_id") != kill_cmd or row.get("task_id") != kill_task:
                    errors.append(f"resume tool row lost ids: {row}")
        if resume_body.get("phase") != "done":
            errors.append(f"resume phase {resume_body.get('phase')!r} (need done)")
        if first_pid and resume_body.get("session_id") == kill_session:
            disk_resume = json.loads(kill_path.read_text(encoding="utf-8")) if kill_path.is_file() else {}
            handoff = disk_resume.get("handoff") if isinstance(disk_resume.get("handoff"), dict) else {}
            if int(handoff.get("from_pid") or 0) != first_pid:
                errors.append(f"handoff from_pid != killed pid {first_pid}: {handoff}")
            if not disk_resume.get("wakeup_at"):
                errors.append("resume did not record wakeup_at")
            if int(disk_resume.get("writer_pid") or 0) == first_pid:
                errors.append("resume left writer_pid on the killed process")

        compact = run_host(["--compact", session_id], env)
        compact_body = last_json(compact.stdout)
        if compact.returncode != 0:
            errors.append(f"compact failed: {compact.stdout} {compact.stderr}")
        show = run_host(["--show", session_id], env)
        show_body = last_json(show.stdout)
        if show.returncode != 0:
            errors.append(f"reload after compact failed: {show.stdout} {show.stderr}")
        if show_body.get("task_id") != task_id or show_body.get("command_id") != command_id:
            errors.append(f"compact/reload lost task/command_id: {show_body}")
        if show_body.get("compacted") is not True:
            errors.append(f"compact flag missing after reload: {show_body}")
        if show_body.get("session_id") != session_id:
            errors.append(f"compact/reload lost session_id: {show_body}")
        reloaded = json.loads(persist.read_text(encoding="utf-8")) if persist.is_file() else {}
        if reloaded.get("transcript") not in ([], None):
            errors.append(f"compact left a transcript: {reloaded.get('transcript')}")

        absent = run_host(["--provider", "configured"], env)
        absent_body = last_json(absent.stdout)
        absent_err = absent_body.get("error") if isinstance(absent_body.get("error"), dict) else {}
        if absent.returncode == 0:
            errors.append("configured provider without credential must exit non-zero")
        if absent_err.get("code") != "E_EXTERNAL":
            errors.append(f"credential absent must be E_EXTERNAL: {absent_body} {absent.stderr}")
        if absent_err.get("path") != "credential":
            errors.append(f"credential absent path must be credential: {absent_err}")
        if "message" not in absent_err:
            errors.append(f"E_EXTERNAL missing message: {absent_err}")

        cred_env = env.copy()
        cred_env["HH_HOST_CREDENTIAL"] = DUMMY_CRED
        cred_session = new_ulid()
        cred_run = run_host(
            ["--provider", "configured", "--session-id", cred_session, "--task-id", task_id, "--command-id", command_id],
            cred_env,
        )
        cred_blob = (cred_run.stdout or "") + (cred_run.stderr or "")
        if DUMMY_CRED in cred_blob:
            errors.append("dummy credential appeared in host logs")
        cred_state = tmp_local / "HHGodotAgent" / "hosts" / cred_session / "state.json"
        if cred_state.is_file() and DUMMY_CRED in cred_state.read_text(encoding="utf-8"):
            errors.append("dummy credential written into state.json")
        cred_body = last_json(cred_run.stdout)
        cred_err = cred_body.get("error") if isinstance(cred_body.get("error"), dict) else {}
        if cred_run.returncode == 0:
            errors.append("configured provider must not claim a live model run")
        if cred_err.get("code") != "E_EXTERNAL":
            errors.append(f"configured-with-cred must stay E_EXTERNAL (no network): {cred_body}")

        mutate_script = tmp_local / "mutate-script.json"
        mutate_script.write_text(
            json.dumps(
                [
                    {
                        "kind": "tool",
                        "tool": "godot.node",
                        "action": "add",
                        "params": {
                            "scene": "res://main.tscn",
                            "parent": ".",
                            "class_name": "Node2D",
                            "name": "AgentWroteThis",
                        },
                    },
                    {"kind": "done", "summary": "mutate not applied"},
                ]
            ),
            encoding="utf-8",
        )
        mutate = run_host(
            [
                "--provider",
                "fake",
                "--script",
                str(mutate_script),
                "--session-id",
                new_ulid(),
                "--task-id",
                new_ulid(),
                "--command-id",
                new_ulid(),
            ],
            env,
        )
        mutate_body = last_json(mutate.stdout)
        mutate_tools = mutate_body.get("tools") if isinstance(mutate_body.get("tools"), list) else []
        mutate_result = (mutate_tools[0].get("result") if mutate_tools else {}) or {}
        mutate_err = mutate_result.get("error") if isinstance(mutate_result.get("error"), dict) else {}
        if mutate_err.get("code") != "E_UNVERIFIED":
            errors.append(f"godot.node add must stay E_UNVERIFIED: {mutate_body}")
        if mutate_result.get("ok") is True:
            errors.append("mutate path returned ok true")

        budget = run_host(
            ["--provider", "fake", "--budget", "0", "--session-id", new_ulid(), "--task-id", new_ulid(), "--command-id", new_ulid()],
            env,
        )
        budget_err = (last_json(budget.stdout).get("error") or {}) if last_json(budget.stdout) else {}
        if budget.returncode == 0 or budget_err.get("code") != "E_POLICY":
            errors.append(f"budget 0 must be E_POLICY: {budget.stdout} {budget.stderr}")

        cancel_id = new_ulid()
        seeded = run_host(
            ["--provider", "fake", "--session-id", cancel_id, "--task-id", new_ulid(), "--command-id", new_ulid()],
            env,
        )
        if seeded.returncode != 0:
            errors.append(f"seed session for cancel failed: {seeded.stdout}")
        cancelled = run_host(["--cancel", cancel_id], env)
        cancel_err = (last_json(cancelled.stdout).get("error") or {}) if last_json(cancelled.stdout) else {}
        if cancelled.returncode == 0 or cancel_err.get("code") != "E_CANCELLED":
            errors.append(f"cancel must be E_CANCELLED: {cancelled.stdout}")

        project_hits = grep_blob(PLUGIN_PROJECT, DUMMY_CRED)
        if project_hits:
            errors.append("credential written into plugin-project")
        if grep_blob(REPO_ROOT / "host" / "src", DUMMY_CRED):
            errors.append("dummy credential committed into host/src")

        mcp_probe = subprocess.run(
            [
                node(),
                "--input-type=module",
                "-e",
                "import { mcpToolsCall } from './dist/executor.js'; "
                "console.log(JSON.stringify(mcpToolsCall('godot.node','add',{scene:'res://main.tscn'},2)))",
            ],
            cwd=str(HOST),
            text=True,
            capture_output=True,
            check=False,
        )
        mcp_body = last_json(mcp_probe.stdout)
        params = ((mcp_body.get("params") or {}).get("arguments") or {}) if mcp_body else {}
        if mcp_body.get("method") != "tools/call" or params.get("action") != "add":
            errors.append(f"MCP tools/call envelope drifted from session contract: {mcp_probe.stdout}")

    except Exception as exc:  # noqa: BLE001
        errors.append(f"host verify failed: {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(tmp_local, ignore_errors=True)

    if errors:
        print("FAIL: agent host", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: fake deterministic host; kill/resume second process kept "
        "session/task/command_id; credential absent E_EXTERNAL; compact/reload "
        "kept ids; persist under LOCALAPPDATA/HHGodotAgent; mutate still "
        "E_UNVERIFIED; R2-WP7 stays [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
