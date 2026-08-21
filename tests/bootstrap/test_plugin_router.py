#!/usr/bin/env python3
"""R2-WP3: EditorPlugin router, health dock, sidecar forward.

Honest about Godot: 50× editor enable/disable runs only if the pinned
4.7.1-stable console exe is already installed. This test never downloads
Godot and never claims a skipped reload as executed.
"""

from __future__ import annotations

import json
import os
import re
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
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
PLUGIN_CFG = ADDON / "plugin.cfg"
VALIDATOR = BRIDGE / "generated" / "plugin-validator.json"
ACTIONS_JSON = ADDON / "core" / "actions.json"
MINIMAL_2D = REPO_ROOT / "godot" / "test-projects" / "minimal-2d"
STOCK_POC = REPO_ROOT / "godot" / "test-projects" / "stock-poc"
EDITOR_BAT = REPO_ROOT / "hh-godot-editor.bat"
GODOT_PIN = REPO_ROOT / "tools" / "godot" / "pin.json"
PINNED_VERSION = "4.7.1.stable.official.a13da4feb"
VENDOR_NEEDLES = (
    "satelliteoflove",
    "MCPGameBridge",
    "godot_mcp",
    "call_method",
    "Object.callv",
    "evaluate_expression",
)
PUBLIC_FUNC_RE = re.compile(
    r"^func\s+([A-Za-z][A-Za-z0-9_]*)\s*\((.*)\)\s*(->\s*[A-Za-z0-9_.]+)?\s*:",
    re.MULTILINE,
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    errors: list[str] = []
    current = ""
    wp3 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP3\b", stripped):
            wp3 = stripped
    if wp3 is None:
        return ["plan missing R2-WP3 heading"]
    ticked = bool(re.search(r"\[x\]", wp3, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp3:
            errors.append("R2-WP3 heading must keep [ ] until coordinator tick")
        if current != "R2-WP3":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP3 while WP3 is unticked)")
    elif not re.match(r"^R2-WP[4-9]$|^R2-WP\d{2,}$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP4+ after R2-WP3 tick)")
    return errors


def typed_gdscript_errors() -> list[str]:
    errors: list[str] = []
    for path in ADDON.rglob("*.gd"):
        text = path.read_text(encoding="utf-8")
        posix = rel(path)
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r"var\s+\w+\s*:=", stripped):
                errors.append(f"{posix}:{i} inferred declaration (A20)")
            if re.match(r"var\s+\w+\s*=", stripped):
                errors.append(f"{posix}:{i} untyped var (A20)")
        for match in PUBLIC_FUNC_RE.finditer(text):
            name, args, ret = match.group(1), match.group(2), match.group(3)
            if not ret:
                errors.append(f"{posix} public {name}() missing return type")
            for part in args.split(","):
                part = part.strip()
                if not part:
                    continue
                if ":" not in part:
                    errors.append(f"{posix} public {name}() untyped arg {part!r}")
    return errors


def vendor_needle_errors() -> list[str]:
    errors: list[str] = []
    trees = (ADDON, BRIDGE / "src", MINIMAL_2D)
    skip = {".godot", "node_modules", "dist", "__pycache__"}
    for root in trees:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or any(part in skip for part in path.parts):
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                blob = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for needle in VENDOR_NEEDLES:
                if needle in blob:
                    errors.append(f"{rel(path)} contains vendor needle {needle!r}")
                    break
    return errors


def catalog_errors() -> list[str]:
    errors: list[str] = []
    if not ACTIONS_JSON.is_file():
        return [f"missing {rel(ACTIONS_JSON)}"]
    if not VALIDATOR.is_file():
        return [f"missing {rel(VALIDATOR)}"]
    slim = json.loads(ACTIONS_JSON.read_text(encoding="utf-8"))
    full = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    if slim.get("protocol") != full.get("protocol"):
        errors.append("actions.json protocol drifted from plugin-validator.json")
    env = slim.get("envelope") if isinstance(slim.get("envelope"), dict) else {}
    full_env = full.get("envelope") if isinstance(full.get("envelope"), dict) else {}
    if env.get("allowed") != full_env.get("allowed"):
        errors.append("actions.json envelope.allowed drifted")
    if env.get("forbidden_client_fields") != full_env.get("forbidden_client_fields"):
        errors.append("actions.json forbidden_client_fields drifted")
    slim_actions = slim.get("actions") if isinstance(slim.get("actions"), dict) else {}
    full_actions = full.get("actions") if isinstance(full.get("actions"), dict) else {}
    if set(slim_actions) != set(full_actions):
        errors.append("actions.json action ids drifted from plugin-validator.json")
    for action_id, spec in slim_actions.items():
        src = full_actions.get(action_id) if isinstance(full_actions.get(action_id), dict) else {}
        if not isinstance(spec, dict):
            errors.append(f"actions.json {action_id} is not an object")
            continue
        for key in ("method", "verb", "side_effect", "timeout_ms"):
            if spec.get(key) != src.get(key):
                errors.append(f"actions.json {action_id}.{key} drifted")
    return errors


def lifecycle_source_errors() -> list[str]:
    errors: list[str] = []
    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    client = (ADDON / "core" / "hh_bridge_client.gd").read_text(encoding="utf-8")
    if "@tool" not in plugin:
        errors.append("plugin.gd must be @tool")
    if "extends EditorPlugin" not in plugin:
        errors.append("plugin.gd must extend EditorPlugin")
    for needle in (
        "func _enter_tree",
        "func _exit_tree",
        "remove_control_from_docks",
        "queue_free",
        "set_process(false)",
    ):
        if needle not in plugin:
            errors.append(f"plugin.gd missing lifecycle cleanup {needle!r}")
    if "func close" not in client or "_ws = null" not in client:
        errors.append("bridge client must null the WebSocketPeer on close")
    dock = (ADDON / "ui" / "health" / "hh_health_dock.gd").read_text(encoding="utf-8")
    for field in ("version", "project", "bridge", "policy", "queue", "pause"):
        if field not in dock.lower() and f'"{field}"' not in plugin and field not in plugin:
            if field not in dock and field not in plugin:
                errors.append(f"health dock missing {field} status")
    if "token" in dock.lower() and "never" not in dock.lower():
        errors.append("health dock must not display the session token")
    return errors


def enablement_errors() -> list[str]:
    errors: list[str] = []
    host = (PLUGIN_PROJECT / "project.godot").read_text(encoding="utf-8")
    if 'res://addons/hh_agent/plugin.cfg' not in host:
        errors.append("plugin-project must enable res://addons/hh_agent/plugin.cfg")
    if "until R2" in host:
        errors.append("plugin-project description still says do not add hh_agent until R2")
    for project in (MINIMAL_2D / "project.godot", STOCK_POC / "project.godot"):
        text = project.read_text(encoding="utf-8")
        if "res://addons/hh_agent/plugin.cfg" in text:
            errors.append(f"{rel(project)} must not enable hh_agent")
    if EDITOR_BAT.is_file():
        bat = EDITOR_BAT.read_text(encoding="utf-8", errors="replace")
        if "minimal-2d" not in bat:
            errors.append("hh-godot-editor.bat must stay on minimal-2d")
        if "plugin-project" in bat:
            errors.append("hh-godot-editor.bat must not retarget to plugin-project")
    cfg = PLUGIN_CFG.read_text(encoding="utf-8")
    if not re.search(r'(?m)^name="hh_agent"', cfg):
        errors.append('plugin.cfg name must be "hh_agent"')
    return errors


def find_pinned_godot() -> tuple[Path | None, str]:
    if not GODOT_PIN.is_file():
        return None, "missing tools/godot/pin.json"
    pin = json.loads(GODOT_PIN.read_text(encoding="utf-8"))
    engine = pin.get("godot") if isinstance(pin.get("godot"), dict) else {}
    version_id = str(engine.get("version_id", ""))
    if any(bad in version_id for bad in ("4.7.2", "4.8")):
        return None, f"refused Godot {version_id}"
    if version_id != PINNED_VERSION:
        return None, f"pin version_id {version_id!r} != {PINNED_VERSION}"
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
    return exe, version_id


def godot_version(exe: Path) -> str:
    proc = subprocess.run(
        [str(exe), "--version"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return text.splitlines()[0].strip() if text else ""


def run_godot(exe: Path, args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), *args],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def run_godot_checks() -> tuple[list[str], str, str]:
    errors: list[str] = []
    exe, pin_reason = find_pinned_godot()
    if exe is None:
        return errors, f"skipped ({pin_reason})", f"skipped ({pin_reason})"
    version = godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        return [f"refused Godot --version {version!r}"], "failed", "failed"
    if version != PINNED_VERSION:
        return [f"Godot --version {version!r} != {PINNED_VERSION}"], "failed", "failed"
    selftest_status = "failed"
    reload_status = "failed"
    selftest_dir = Path(tempfile.mkdtemp(prefix="hh-r2wp3-selftest-"))
    try:
        env = os.environ.copy()
        env["HH_AGENT_SELFTEST"] = "1"
        env["HH_AGENT_SELFTEST_OUT"] = str(selftest_dir)
        selftest = subprocess.run(
            [
                str(exe),
                "--headless",
                "--editor",
                "--path",
                str(PLUGIN_PROJECT),
                "--quit-after",
                "20",
            ],
            cwd=str(REPO_ROOT),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env=env,
        )
        out = (selftest.stdout or "") + (selftest.stderr or "")
        marker = selftest_dir / "hh_agent_selftest.txt"
        marker_text = marker.read_text(encoding="utf-8") if marker.is_file() else ""
        if "HH_AGENT_SELFTEST=PASS" not in out and "HH_AGENT_SELFTEST=PASS" not in marker_text:
            errors.append(
                f"Godot editor selftest failed (exit {selftest.returncode}): {out[-2000:]}"
            )
        else:
            selftest_status = "ran"
    except subprocess.TimeoutExpired:
        errors.append("Godot editor selftest timed out")
    reloads = 0
    try:
        run_godot(
            exe,
            ["--headless", "--path", str(PLUGIN_PROJECT), "--import"],
            180,
        )
        for i in range(50):
            cycle = run_godot(
                exe,
                [
                    "--headless",
                    "--editor",
                    "--path",
                    str(PLUGIN_PROJECT),
                    "--quit-after",
                    "5",
                ],
                90,
            )
            if cycle.returncode != 0:
                errors.append(f"Godot editor reload {i + 1}/50 exited {cycle.returncode}")
                reload_status = f"failed after {reloads}"
                return errors, selftest_status, reload_status
            reloads += 1
        reload_status = "ran"
    except subprocess.TimeoutExpired:
        errors.append(f"Godot editor reload timed out after {reloads}")
        reload_status = f"failed after {reloads}"
    return errors, selftest_status, reload_status


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


def main() -> int:
    errors: list[str] = []
    godot_reload = "skipped"
    godot_selftest = "skipped"
    secret = ""

    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(enablement_errors())
    errors.extend(typed_gdscript_errors())
    errors.extend(vendor_needle_errors())
    errors.extend(catalog_errors())
    errors.extend(lifecycle_source_errors())

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: plugin router", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    discovered = sess.run_harness(["discover", str(PLUGIN_PROJECT)])
    if not discovered.get("ok") or not discovered.get("project_id"):
        errors.append(f"harness discover failed: {discovered}")
    project_id = str(discovered.get("project_id") or "")

    tmp = Path(tempfile.mkdtemp(prefix="hh-r2wp3-"))
    (tmp / "project.godot").write_text("; test fixture\nconfig_version=5\n", encoding="utf-8")
    proc: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    err_lines: list[str] = []
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
        good = sess.ws_hello(host, port, sess.hello_payload(sid_project, secret))
        if good.get("ok") is not True:
            errors.append(f"hello failed: {sess.redact(json.dumps(good), secret)}")

        if project_id and project_id == sid_project:
            errors.append("temp fixture project_id collided with plugin-project")

        plugin_sock = sess.ws_connect(host, port)
        sess.ws_send_text(plugin_sock, json.dumps(sess.hello_payload(sid_project, secret)))
        hello_ok = json.loads(sess.ws_recv_text(plugin_sock))
        if hello_ok.get("ok") is not True:
            errors.append(f"plugin hello failed: {sess.redact(json.dumps(hello_ok), secret)}")

        inbound: list[dict] = []

        def plugin_loop() -> None:
            try:
                while True:
                    msg = json.loads(sess.ws_recv_text(plugin_sock))
                    if msg.get("type") != "request":
                        continue
                    env = msg.get("envelope") if isinstance(msg.get("envelope"), dict) else {}
                    inbound.append(env)
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
                                        "message": "no read adapter",
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
            init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-plugin-router", "version": "0"},
                },
            }
            proc.stdin.write(json.dumps(init) + "\n")
            proc.stdin.flush()
            init_line = sess.readline_timeout(proc.stdout, 5.0)
            if "result" not in json.loads(init_line):
                errors.append(f"MCP initialize failed: {sess.redact(init_line, secret)}")

            before = len(inbound)
            mutate = mcp_call(
                proc,
                2,
                "godot.node",
                {"action": "add", "params": {"class": "Node2D"}},
            )
            body = (mutate.get("result") or {}).get("structuredContent") or {}
            err = body.get("error") or {}
            if err.get("code") != "E_UNVERIFIED":
                errors.append(f"mutate must stay E_UNVERIFIED: {sess.redact(json.dumps(mutate), secret)}")
            if mutate.get("result", {}).get("isError") is not True:
                errors.append("mutate must be isError")
            dumped = json.dumps(mutate)
            if '"ok": true' in dumped or '"ok":true' in dumped:
                errors.append("mutate path returned ok true")
            time.sleep(0.2)
            if len(inbound) != before:
                errors.append("mutate must not be forwarded to the plugin")

            noop = mcp_call(proc, 3, "hh.plugin_noop", {})
            noop_body = (noop.get("result") or {}).get("structuredContent") or {}
            deadline = time.time() + 4.0
            while time.time() < deadline and not inbound:
                time.sleep(0.05)
            if noop_body.get("ok") is not True:
                errors.append(f"noop must ACK through plugin: {sess.redact(json.dumps(noop), secret)}")
            post = noop_body.get("postcondition") or {}
            if post.get("verified") is not True or post.get("checks") != ["noop"]:
                errors.append("noop postcondition must be verified with checks=['noop']")
            if not any(row.get("action") == "noop" for row in inbound):
                errors.append("noop was not forwarded over the plugin socket")

            read = mcp_call(
                proc,
                4,
                "godot.project",
                {"action": "inspect", "params": {"detail": "short"}},
            )
            read_body = (read.get("result") or {}).get("structuredContent") or {}
            read_err = read_body.get("error") or {}
            if read_err.get("code") != "E_UNVERIFIED":
                errors.append(
                    f"read without adapter must be E_UNVERIFIED: {sess.redact(json.dumps(read), secret)}"
                )

        plugin_sock.close()
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"sidecar/plugin run failed: {type(exc).__name__}: {exc}", secret))
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

    if secret and secret in "".join(err_lines):
        errors.append("session secret appeared in sidecar logs")

    godot_errors, godot_selftest, godot_reload = run_godot_checks()
    errors.extend(godot_errors)

    if errors:
        print("FAIL: plugin router", file=sys.stderr)
        for item in errors:
            print(f"  - {sess.redact(item, secret)}", file=sys.stderr)
        return 1

    print(
        "PASS: hh_agent router + health dock; envelope second pass; "
        "sidecar hello + noop forward; mutate not dispatched; "
        f"GODOT_SELFTEST={godot_selftest}; GODOT_RELOAD_50={godot_reload}; "
        "R2-WP3 stays unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
