#!/usr/bin/env python3
"""R6-WP2: Runtime probe/autoload and structured state.

Does not tick the 20-8 plan. Does not change CURRENT_VALID_WP.
Keep R6-WP2 [ ]; while unticked CURRENT_VALID_WP=R6-WP2.
Pin 4.7.1-stable only. Refuse later 4.7 patches past .1-stable. No skip-PASS.
No dummy screenshot PNG. Do not paper-ACK runtime.tree from the editor scene.

Verify (encoded here; this file is the official harness):
  - debugger-channel paging, not get_edited_scene_root() as the game tree
  - 10k-node runtime query paging (page <= MAX_PAGE, total >= 10000)
  - secret property redaction
  - release scan negative (skip() + project.godot no HHAgentRuntime)
  - debug-only autoload, never persist after play.stop / suite
  - screenshots=SKIP; freeze/step/screenshot/perf stay E_UNVERIFIED

If headless --editor never flips is_playing_scene or never delivers hh_runtime
replies: label Alternative, do not invent remote_tree=true. Try exclusive GUI
Godot (same pin exe, --editor --path godot/plugin-project). Do not start a
second Godot if one is already on plugin-project. Kill leftover Godot/Node
on plugin-project before exclusive tests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_scene_lifecycle as life
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
ACTIONS_JSON = ADDON / "core" / "actions.json"
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r6w2"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCREENSHOTS = "SKIP"
RAW_SECRET = "R6WP2_RAW_SECRET_VALUE_DO_NOT_LEAK"
RAW_PASSWORD = "R6WP2_RAW_PASSWORD_VALUE_DO_NOT_LEAK"
RAW_TOKEN = "R6WP2_RAW_TOKEN_VALUE_DO_NOT_LEAK"
MAX_PAGE = 100
SPAWN_COUNT = 10000
VARIANT_SCHEMA = "hh-godot-variant/1"
PRODUCT_RUNTIME = ADDON / "runtime" / "hh_agent_runtime.gd"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R6-WP2 [ ]; while unticked require CURRENT_VALID_WP=R6-WP2."""
    errors: list[str] = []
    current = ""
    wp2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R6-WP2\b", stripped):
            wp2 = stripped
    if wp2 is None:
        return ["plan missing R6-WP2 heading"]
    ticked = bool(re.search(r"\[x\]", wp2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp2:
            errors.append("R6-WP2 heading must keep [ ] until coordinator tick")
        if current != "R6-WP2":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP2 while WP2 is unticked)")
    elif not re.match(r"^R6-WP([3-9]|\d{2,})$|^R[7-9]-WP\d+$|^RX-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R6-WP3+ after R6-WP2 tick)")
    return errors


def cleanup_temp() -> list[str]:
    errors: list[str] = []
    for _ in range(6):
        if not TEMP_DIR.exists():
            break
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        time.sleep(0.2)
    if TEMP_DIR.exists():
        for path in TEMP_DIR.rglob("*"):
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    pass
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    if TEMP_DIR.exists():
        leftovers = [p.as_posix() for p in TEMP_DIR.rglob("*")]
        errors.append(f"r6w2 fixture leftover after cleanup: {leftovers[:8]}")
    agent = PLUGIN_PROJECT / ".hh-agent"
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass
    return errors


def plugin_godot_busy() -> bool:
    needle = "plugin-project"
    if os.name == "nt":
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'Godot' } | "
                    "Select-Object -ExpandProperty CommandLine"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        return needle in blob.replace("\\", "/").lower()
    proc = subprocess.run(["ps", "-ax", "-o", "args="], capture_output=True, text=True, check=False)
    return needle in (proc.stdout or "").lower() and "godot" in (proc.stdout or "").lower()


def kill_plugin_project_holders(*, godot: bool = True, node: bool = True) -> None:
    """Kill leftover Godot/Node processes holding plugin-project.

    After the sidecar is up, only kill Godot — Node with plugin-project in
    argv is the live sidecar.
    """
    if os.name == "nt":
        name_match = []
        if godot:
            name_match.append("$_.Name -match 'Godot'")
        if node:
            name_match.append("$_.Name -match '^node'")
        if not name_match:
            return
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { "
                    f"({' -or '.join(name_match)}) -and "
                    "$_.CommandLine -and "
                    "(($_.CommandLine -replace '\\\\','/') -match 'plugin-project') "
                    "} | ForEach-Object { "
                    "Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
                    "}"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return
    proc = subprocess.run(["ps", "-ax", "-o", "pid=,args="], capture_output=True, text=True, check=False)
    for line in (proc.stdout or "").splitlines():
        lower = line.lower()
        if "plugin-project" not in lower.replace("\\", "/"):
            continue
        is_godot = "godot" in lower
        is_node = "node" in lower
        if (is_godot and godot) or (is_node and node):
            pid = line.strip().split(None, 1)[0]
            if pid.isdigit():
                subprocess.run(["kill", "-9", pid], capture_output=True, check=False)


def project_godot_text() -> str:
    path = PLUGIN_PROJECT / "project.godot"
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def project_godot_leak_errors(when: str) -> list[str]:
    text = project_godot_text()
    errors: list[str] = []
    if "HHAgentRuntime" in text:
        errors.append(f"project.godot leaked HHAgentRuntime {when}")
    if "hh_agent_runtime" in text:
        errors.append(f"project.godot leaked hh_agent_runtime {when}")
    return errors


def release_scan_errors() -> list[str]:
    """Fail if autoload/probe leaked or export skip() does not match paths."""
    errors: list[str] = []
    errors.extend(project_godot_leak_errors("release scan"))
    export_gd = ADDON / "core" / "hh_export_plugin.gd"
    if not export_gd.is_file():
        errors.append("missing hh_export_plugin.gd")
        return errors
    text = export_gd.read_text(encoding="utf-8")
    if "skip()" not in text:
        errors.append("export plugin must call skip()")
    for needle in (
        "HHAgentRuntime",
        "hh_agent_runtime",
        "addons/hh_agent/runtime",
        ".hh-agent",
        "addons/hh_agent",
        "r6w2",
    ):
        if needle not in text:
            errors.append(f"export skip() must match {needle}")
    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_export_plugin" not in plugin or "remove_export_plugin" not in plugin:
        errors.append("plugin.gd must register EditorExportPlugin")
    presets = PLUGIN_PROJECT / "export_presets.cfg"
    if presets.is_file():
        blob = presets.read_text(encoding="utf-8", errors="replace")
        if "HHAgentRuntime" in blob or "hh_agent_runtime" in blob:
            errors.append("export_presets.cfg leaked runtime probe")
    else:
        # Honest Alternative: no preset, so no dry export build.
        pass
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    self_text = Path(__file__).read_text(encoding="utf-8")
    if re.search(r"\.write_text\([^\n]*\.(?:tscn|tres|res|png|gd)", self_text):
        errors.append("official test writes a .tscn/.tres/.png/.gd path directly")
    if re.search(r"\.write_bytes\(|Image\.new\b", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if "screenshots=SKIP" not in self_text and 'SCREENSHOTS = "SKIP"' not in self_text:
        errors.append("official test must record screenshots=SKIP")
    if "Alternative" not in self_text:
        errors.append("official test must record headless/runtime Alternative honestly")
    if "paper-ACK" not in self_text:
        errors.append("official test must refuse to paper-ACK runtime.tree")
    if "skip-PASS" not in self_text and "No skip-PASS" not in self_text:
        errors.append("official test must refuse skip-PASS")
    if "10k" not in self_text and "10000" not in self_text:
        errors.append("official test must encode 10k-node paging")
    if "secret" not in self_text.lower() or "redact" not in self_text.lower():
        errors.append("official test must encode secret redaction")
    if "release scan" not in self_text:
        errors.append("official test must encode release scan negative")
    if "res://" + "snake" in self_text or "kho" + "-bi-an" in self_text:
        errors.append("official test must stay independent of demo game trees")
    if "4.7." + "2" in self_text:
        errors.append("official test must refuse Godot 4.7." + "2 pin")
    if "hh_play:" + "log" in self_text:
        errors.append("official fixtures must not print PARSER/stack needles")
    if "register_" + "message_capture" in self_text.split("def src_scan_errors")[0]:
        errors.append("official fixture must not implement hh_runtime capture; product autoload must")
    if "PROBE_" + "SCRIPT" in self_text:
        errors.append("official test must play the product runtime script, not a copied fixture protocol")
    if "PRODUCT_RUNTIME.read_text" not in self_text:
        errors.append("setup_scene must write PRODUCT_RUNTIME.read_text, not a fixture protocol")

    plugin = (ADDON / "plugin.gd").read_text(encoding="utf-8")
    if "add_debugger_plugin" not in plugin or "remove_debugger_plugin" not in plugin:
        errors.append("plugin.gd must register EditorDebuggerPlugin on enter/exit")
    if "hh_runtime_debugger" not in plugin:
        errors.append("plugin.gd must load hh_runtime_debugger")
    if "add_autoload_singleton(" in plugin:
        errors.append("plugin.gd must not call add_autoload_singleton (writes project.godot, kills Play)")
    if "remove_autoload_singleton" not in plugin:
        errors.append("plugin.gd must be able to drop a leaked HHAgentRuntime name")
    if "_restore_project_godot_if_leaked" not in plugin:
        errors.append("plugin.gd must strip a leaked HHAgentRuntime without ProjectSettings.save persist")
    if "add_export_plugin" not in plugin:
        errors.append("plugin.gd must register export plugin")

    runtime_gd = ADDON / "runtime" / "hh_agent_runtime.gd"
    if not runtime_gd.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
    else:
        rtext = runtime_gd.read_text(encoding="utf-8")
        if "Engine" + "Debugger" not in rtext:
            errors.append("game-side autoload must use debugger send_message")
        if "agent_observe" not in rtext:
            errors.append("runtime autoload must treat agent_observe as optional")
        if RAW_SECRET in rtext:
            errors.append("autoload must not embed the official-test raw secret")
        if "autoload" + "\": true" in rtext:
            errors.append("product hello must not stamp autoload:true")

    adapter = ADDON / "core" / "hh_runtime_adapter.gd"
    if not adapter.is_file():
        errors.append("missing hh_runtime_adapter.gd")
    else:
        atext = adapter.read_text(encoding="utf-8")
        if "get_edited_scene_root" in atext:
            errors.append("runtime adapter must not use get_edited_scene_root as the game tree")
        if "Engine" + "Debugger" in atext:
            errors.append("do not use the game-side debugger singleton in the editor runtime adapter")
        if "remote_tree" not in atext or "tree_kind" not in atext:
            errors.append("runtime adapter must label remote tree only after Play proof")
        if "hh_agent_runtime" not in atext:
            errors.append("runtime adapter must require product source hh_agent_runtime")

    reads = (ADDON / "core" / "hh_read_adapters.gd").read_text(encoding="utf-8")
    if "runtime freeze/step is R6-WP4" not in reads:
        errors.append("freeze/step must stay E_UNVERIFIED in this WP")
    if "_runtime_read" not in reads:
        errors.append("read adapters must dispatch runtime.tree/node/state")

    for dbg_name in ("hh_play_debugger.gd", "hh_runtime_debugger.gd"):
        dbg = ADDON / "core" / dbg_name
        if not dbg.is_file():
            errors.append(f"missing {dbg_name}")
            continue
        dtext = dbg.read_text(encoding="utf-8")
        if "func _has_capture" not in dtext or "func _capture" not in dtext:
            errors.append(f"{dbg_name} must implement _has_capture/_capture")
        if re.search(r"return true", dtext):
            errors.append(f"{dbg_name} must not contain return true")
        if "Engine" + "Debugger" in dtext:
            errors.append(f"do not use the game-side debugger singleton in {dbg_name}")
    runtime_dbg = ADDON / "core" / "hh_runtime_debugger.gd"
    if runtime_dbg.is_file():
        dtext = runtime_dbg.read_text(encoding="utf-8")
        if "hh_runtime" not in dtext:
            errors.append("runtime debugger _has_capture must be hh_runtime prefix")

    execute = (BRIDGE / "src" / "ledger" / "execute.ts").read_text(encoding="utf-8")
    if "runtimeApplyOk" in execute and "const runtimeFail = runtimeApplyOk" not in execute:
        errors.append("if runtimeApplyOk exists, call-site must use const runtimeFail = runtimeApplyOk")
    lifecycle = (BRIDGE / "src" / "ledger" / "scene_lifecycle.ts").read_text(encoding="utf-8")
    play_apply = lifecycle.split("PLAY_APPLY")[1].split("]")[0] if "PLAY_APPLY" in lifecycle else ""
    if "runtime.tree" in play_apply or "runtime.node" in play_apply:
        errors.append("runtime.tree/node are READS; do not put them in PLAY_APPLY")

    constants = (ADDON / "core" / "hh_constants.gd").read_text(encoding="utf-8")
    if "MAX_PAGE: int = 100" not in constants:
        errors.append("MAX_PAGE must stay 100")

    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def mcp_call(proc, req_id: int, name: str, arguments: dict, timeout: float = 60.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def tool_call(
    proc,
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 60.0,
) -> tuple[int, dict]:
    cid = life.new_ulid()
    resp = mcp_call(proc, req_id, name=method, arguments={"action": action, "params": params, "command_id": cid}, timeout=timeout)
    return req_id + 1, body_of(resp)


def ack_ok(body: dict, errors: list[str], verb: str) -> bool:
    if body.get("ok") is not True:
        errors.append(f"{verb} must ACK: {body}")
        return False
    post = body.get("postcondition") or {}
    if post.get("verified") is not True or not post.get("checks"):
        errors.append(f"{verb} paper postcondition: {body}")
        return False
    return True


def after_of(body: dict) -> dict:
    after = body.get("after") or {}
    return after if isinstance(after, dict) else {}


def start_godot(exe: Path, headless: bool) -> tuple[subprocess.Popen[str], list[str]]:
    env = os.environ.copy()
    env.pop("HH_AGENT_SELFTEST", None)
    env.pop("HH_AGENT_SELFTEST_OUT", None)
    env.pop("HH_AGENT_RELOAD_N", None)
    env.pop("HH_AGENT_RELOAD_OUT", None)
    env.pop("HH_READ_OPEN_SCENE", None)
    args = [str(exe)]
    if headless:
        args.append("--headless")
    args.extend(["--editor", "--path", str(PLUGIN_PROJECT)])
    godot = subprocess.Popen(
        args,
        cwd=str(REPO_ROOT),
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

    import threading

    threading.Thread(target=drain_out, daemon=True).start()
    threading.Thread(target=sess.drain_stderr, args=(godot, lines), daemon=True).start()
    return godot, lines


def write_script(proc, req_id: int, path: str, contents: str, errors: list[str]) -> int:
    req_id, body = tool_call(proc, req_id, "godot.script", "write", {"path": path, "contents": contents})
    ack_ok(body, errors, f"script.write {path}")
    return req_id


def attach_and_save(proc, req_id: int, scene: str, script: str, errors: list[str]) -> int:
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": script}
    )
    ack_ok(attached, errors, f"script.attach {script}")
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, f"scene.save {scene}")
    return req_id


def play_start(proc, req_id: int, scene: str, mode: str = "play") -> tuple[int, dict]:
    return tool_call(proc, req_id, "godot.play", "start", {"scene": scene, "mode": mode}, timeout=90.0)


def play_stop(proc, req_id: int, reason: str = "test", run_id: str | None = None) -> tuple[int, dict]:
    params: dict = {"reason": reason}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "stop", params, timeout=60.0)


def runtime_tree(proc, req_id: int, params: dict | None = None) -> tuple[int, dict]:
    body_params = {"detail": "short", "limit": MAX_PAGE}
    if params:
        body_params.update(params)
    return tool_call(proc, req_id, "godot.runtime", "tree", body_params, timeout=20.0)


def page_has_spawn(items: list) -> bool:
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name.startswith("N") and name[1:].isdigit():
            return True
    return False


def refuse_invented_remote(body: dict, errors: list[str], verb: str) -> None:
    after = after_of(body)
    if body.get("ok") is True and after.get("remote_tree") is True and after.get("tree_kind") == "remote":
        return
    if after.get("remote_tree") is True or after.get("tree_kind") == "remote":
        errors.append(f"{verb} invented remote_tree without ACK: {body}")


def expect_not_remote(body: dict, errors: list[str], verb: str) -> None:
    after = after_of(body)
    if body.get("ok") is True and after.get("remote_tree") is True:
        errors.append(f"{verb} paper-ACK remote_tree=true: {body}")
    if after.get("tree_kind") == "remote" and body.get("ok") is not True:
        errors.append(f"{verb} labeled tree_kind=remote without a proven reply: {body}")
    code = str((body.get("error") or {}).get("code") or "")
    if body.get("ok") is True:
        errors.append(f"{verb} must not ACK without Play: {body}")
    if code not in ("E_UNVERIFIED", "E_CONFLICT"):
        errors.append(f"{verb} must be E_UNVERIFIED/E_CONFLICT, got {body}")


def variant(typ: str, value) -> dict:
    return {"schema": VARIANT_SCHEMA, "type": typ, "value": value}


def setup_scene(proc, req_id: int, errors: list[str]) -> tuple[int, str, str]:
    scene = "res://r6w2/probe.tscn"
    script = "res://r6w2/probe.gd"
    if not PRODUCT_RUNTIME.is_file():
        errors.append("missing addons/hh_agent/runtime/hh_agent_runtime.gd")
        return req_id, scene, script
    product = PRODUCT_RUNTIME.read_text(encoding="utf-8")
    if "spawn_count" not in product or "ping_debugger" not in product:
        errors.append("product runtime script must own spawn_count + ping_debugger")
        return req_id, scene, script
    req_id, created = tool_call(proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"})
    if not ack_ok(created, errors, "scene.create"):
        return req_id, scene, script
    req_id = write_script(proc, req_id, script, product, errors)
    req_id, opened = tool_call(proc, req_id, "godot.scene", "open", {"path": scene})
    if opened.get("ok") is not True:
        errors.append(f"scene.open {scene}: {opened}")
        return req_id, scene, script
    req_id, attached = tool_call(
        proc, req_id, "godot.script", "attach", {"scene": scene, "node_path": ".", "path": script}
    )
    if not ack_ok(attached, errors, f"script.attach {script}"):
        return req_id, scene, script
    for prop, typ, value in (
        ("dummy_secret", "string", RAW_SECRET),
        ("dummy_password", "string", RAW_PASSWORD),
        ("dummy_token", "string", RAW_TOKEN),
        ("hp", "int", 42),
        ("spawn_count", "int", SPAWN_COUNT),
    ):
        req_id, posed = tool_call(
            proc,
            req_id,
            "godot.property",
            "set",
            {"scene": scene, "node_path": ".", "property": prop, "value": variant(typ, value)},
        )
        if not ack_ok(posed, errors, f"property.set {prop}"):
            return req_id, scene, script
    req_id, saved = tool_call(proc, req_id, "godot.scene", "save", {"path": scene})
    ack_ok(saved, errors, f"scene.save {scene}")
    return req_id, scene, script


def editor_scene_is_small(proc, req_id: int, scene: str, errors: list[str]) -> int:
    req_id, body = tool_call(proc, req_id, "godot.scene", "read", {"path": scene, "detail": "short", "limit": MAX_PAGE})
    if body.get("ok") is not True:
        errors.append(f"scene.read editor scene failed: {body}")
        return req_id
    tree = after_of(body).get("tree") or {}
    total = int(tree.get("total") or 0)
    items = tree.get("items") if isinstance(tree.get("items"), list) else []
    if total >= SPAWN_COUNT:
        errors.append(f"scene.read dumped 10k as the editor/runtime tree: {tree}")
    if len(items) > MAX_PAGE:
        errors.append(f"scene.read page exceeded MAX_PAGE: {len(items)}")
    if after_of(body).get("remote_tree") is True or after_of(body).get("tree_kind") == "remote":
        errors.append(f"scene.read must stay editor tree, not remote: {body}")
    return req_id


def play_status(proc, req_id: int, run_id: str | None = None) -> tuple[int, dict]:
    params: dict = {"detail": "short"}
    if run_id:
        params["run_id"] = run_id
    return tool_call(proc, req_id, "godot.play", "status", params)


def wait_runtime_tree(
    proc, req_id: int, run_id: str, errors: list[str]
) -> tuple[int, dict, bool]:
    deadline = time.time() + 25.0
    last: dict = {}
    first: dict = {}
    while time.time() < deadline:
        req_id, last = runtime_tree(proc, req_id, {"run_id": run_id, "limit": MAX_PAGE})
        if not first:
            first = last
        after = after_of(last)
        if (
            last.get("ok") is True
            and after.get("remote_tree") is True
            and after.get("tree_kind") == "remote"
            and int(after.get("total") or 0) >= SPAWN_COUNT
            and str(after.get("source") or "") == "hh_agent_runtime"
        ):
            items = after.get("items") if isinstance(after.get("items"), list) else []
            if len(items) > MAX_PAGE:
                errors.append(f"runtime.tree page exceeded MAX_PAGE: {len(items)}")
                return req_id, last, False
            if int(after.get("limit") or 0) > MAX_PAGE:
                errors.append(f"runtime.tree limit exceeded MAX_PAGE: {after}")
                return req_id, last, False
            if str(after.get("run_id") or "") != run_id:
                errors.append(f"runtime.tree run_id bind mismatch: {after}")
                return req_id, last, False
            return req_id, last, True
        msg = str((last.get("error") or {}).get("message") or "")
        if "requires Play process" in msg:
            req_id, st = play_status(proc, req_id, run_id)
            last = {"tree": last, "status": st, "first": first, "autoload": "HHAgentRuntime" in project_godot_text()}
            return req_id, last, False
        time.sleep(0.6)
    last = {"tree": last, "first": first, "autoload": "HHAgentRuntime" in project_godot_text()}
    return req_id, last, False


def verify_runtime_suite(proc, req_id: int, errors: list[str], scene: str) -> tuple[int, bool]:
    req_id, idle = runtime_tree(proc, req_id)
    expect_not_remote(idle, errors, "runtime.tree before Play")

    req_id = editor_scene_is_small(proc, req_id, scene, errors)

    req_id, start_body = play_start(proc, req_id, scene, mode="debug")
    if start_body.get("ok") is not True or after_of(start_body).get("playing") is not True:
        errors.append(f"play.start must ACK with playing=true after proven Play: {start_body}")
        return req_id, False
    if after_of(start_body).get("is_playing_scene") is not True:
        errors.append("play.start after.is_playing_scene must be true (no invented playing=true)")
    if after_of(start_body).get("debugger_attached") is not True:
        errors.append(f"runtime probe Play must attach a debugger session: {start_body}")
    run_id = str(after_of(start_body).get("run_id") or "")
    if len(run_id) != 26:
        errors.append(f"play.start must mint run_id: {start_body}")
    time.sleep(2.0)

    req_id, logs_body = tool_call(proc, req_id, "godot.play", "logs", {"limit": 50, "run_id": run_id})
    req_id, tree_body, proven = wait_runtime_tree(proc, req_id, run_id, errors)
    if not proven:
        req_id, logs_body = tool_call(proc, req_id, "godot.play", "logs", {"limit": 50, "run_id": run_id})
        tree_body = {"tree_wait": tree_body, "logs": after_of(logs_body)}
    if not proven:
        errors.append(
            "runtime.tree must page a proven remote tree "
            f"(total>={SPAWN_COUNT}, not editor scene): {tree_body}"
        )
        req_id, _ = play_stop(proc, req_id, run_id=run_id)
        errors.extend(project_godot_leak_errors("after play.stop (tree fail)"))
        return req_id, False
    after = after_of(tree_body)
    if str(after.get("source") or "") != "hh_agent_runtime":
        errors.append(f"runtime.tree must come from product hh_agent_runtime, not a fixture capture: {tree_body}")
    items = after.get("items") if isinstance(after.get("items"), list) else []
    if not items:
        errors.append(f"runtime.tree page was empty: {tree_body}")
    snap_tree = json.dumps(after, ensure_ascii=False)
    for raw in (RAW_SECRET, RAW_PASSWORD, RAW_TOKEN):
        if raw in snap_tree:
            errors.append("secret property redaction failed; raw value in runtime.tree snapshot")
    next_cursor = str(after.get("next_cursor") or "")
    page2_items: list = []
    if after.get("has_more") is True and next_cursor:
        req_id, page2 = runtime_tree(
            proc, req_id, {"run_id": run_id, "limit": MAX_PAGE, "cursor": next_cursor}
        )
        if page2.get("ok") is not True:
            errors.append(f"runtime.tree page 2 must ACK: {page2}")
        else:
            page2_after = after_of(page2)
            page2_items = page2_after.get("items") if isinstance(page2_after.get("items"), list) else []
            if len(page2_items) > MAX_PAGE:
                errors.append(f"runtime.tree page 2 exceeded MAX_PAGE: {len(page2_items)}")
            if page2_after.get("remote_tree") is not True:
                errors.append(f"runtime.tree page 2 must stay remote: {page2}")
            first = str((items[0] or {}).get("path") or "") if items else ""
            second = str((page2_items[0] or {}).get("path") or "") if page2_items else ""
            if first and second and first == second:
                errors.append("runtime.tree page 2 must advance past page 1")
    if not page_has_spawn(items) and not page_has_spawn(page2_items):
        last_off = max(0, int(after.get("total") or 0) - 20)
        req_id, spawn_page = runtime_tree(
            proc, req_id, {"run_id": run_id, "limit": MAX_PAGE, "offset": last_off}
        )
        spawn_items = after_of(spawn_page).get("items") if spawn_page.get("ok") is True else []
        if not isinstance(spawn_items, list) or not page_has_spawn(spawn_items):
            errors.append("runtime.tree must include spawned N{i} children, not only Play helpers")

    req_id = editor_scene_is_small(proc, req_id, scene, errors)

    req_id, node_body = tool_call(
        proc, req_id, "godot.runtime", "node", {"node_path": ".", "run_id": run_id}, timeout=20.0
    )
    if node_body.get("ok") is not True:
        errors.append(f"runtime.node must ACK on Play scene root: {node_body}")
    else:
        if after_of(node_body).get("remote_tree") is not True:
            errors.append(f"runtime.node must label remote_tree=true: {node_body}")
        snap = json.dumps(after_of(node_body), ensure_ascii=False)
        for raw in (RAW_SECRET, RAW_PASSWORD, RAW_TOKEN):
            if raw in snap:
                errors.append("secret property redaction failed; raw value in runtime.node snapshot")
        props = after_of(node_body).get("properties")
        if not isinstance(props, dict):
            errors.append(f"runtime.node must return properties: {node_body}")
        else:
            for key in ("dummy_secret", "dummy_password", "dummy_token"):
                if key not in props:
                    errors.append(f"runtime.node must include {key} so redaction is proven")
                elif props.get(key) != "***":
                    errors.append(f"secret property {key} must be ***, got {props.get(key)!r}")
            if "groups" not in after_of(node_body) or "signals" not in after_of(node_body):
                errors.append("runtime.node must include groups/signals")
            if "time" not in after_of(node_body):
                errors.append("runtime.node must include timeline ticks/frames")

    req_id, state_body = tool_call(
        proc, req_id, "godot.runtime", "state", {"key": "hp", "node_path": ".", "run_id": run_id}, timeout=20.0
    )
    if state_body.get("ok") is not True:
        errors.append(f"runtime.state key=hp must ACK without agent_observe: {state_body}")
    else:
        if after_of(state_body).get("found") is not True:
            errors.append(f"runtime.state hp must be found on base Node2D: {state_body}")
        if after_of(state_body).get("value") != 42:
            errors.append(f"runtime.state hp expected 42: {state_body}")
        if after_of(state_body).get("source") != "hh_agent_runtime":
            errors.append(f"runtime.state must keep product source: {state_body}")
        if after_of(state_body).get("value_source") == "agent_observe":
            errors.append("base Node2D must work WITHOUT agent_observe")
        if after_of(state_body).get("value_source") != "property":
            errors.append(f"runtime.state hp must come from a property, got {state_body}")

    for method, action, params, label in (
        ("godot.runtime", "freeze", {"frozen": True, "reason": "test"}, "runtime.freeze"),
        ("godot.runtime", "step", {"frames": 1}, "runtime.step"),
        ("godot.runtime", "screenshot", {"scale": 1}, "runtime.screenshot"),
        ("godot.runtime", "perf", {"detail": "short"}, "runtime.perf"),
    ):
        req_id, later = tool_call(proc, req_id, method, action, params)
        if later.get("ok") is True:
            errors.append(f"{label} must stay E_UNVERIFIED (do not ACK)")
        if str((later.get("error") or {}).get("code") or "") != "E_UNVERIFIED":
            errors.append(f"{label} must stay E_UNVERIFIED: {later}")

    req_id, _stopped = play_stop(proc, req_id, run_id=run_id)
    time.sleep(0.4)
    errors.extend(project_godot_leak_errors("after play.stop"))
    req_id, after_stop = runtime_tree(proc, req_id, {"run_id": run_id})
    expect_not_remote(after_stop, errors, "runtime.tree after play.stop")
    return req_id, True


def live_errors(exe: Path) -> tuple[list[str], str, str, str, str]:
    """Returns errors, LIVE, HEADLESS_PLAY, GUI_PLAY, REMOTE_TREE."""
    errors: list[str] = []
    live = "unrun"
    headless_play = "unproven"
    gui_play = "unrun"
    remote_tree = "unproven"
    kill_plugin_project_holders()
    time.sleep(1.0)
    if plugin_godot_busy():
        errors.append("LIVE_UNRUN: Godot already open on plugin-project (exclusive; no second instance)")
        return errors, "unrun", "unproven", "unrun", "unproven"
    errors.extend(cleanup_temp())
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc = None
    godot = None
    desc_path = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = start_godot(exe, headless=True)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, "failed", "unproven", "unrun", "unproven"
        live = "ran"
        req_id, idle = runtime_tree(proc, req_id)
        expect_not_remote(idle, errors, "headless runtime.tree before Play")
        req_id, scene, _script = setup_scene(proc, req_id, errors)
        if errors:
            return errors, live, headless_play, gui_play, remote_tree
        req_id, start_body = play_start(proc, req_id, scene)
        playing = start_body.get("ok") is True and after_of(start_body).get("playing") is True
        if playing:
            headless_play = "proven"
            run_id = str(after_of(start_body).get("run_id") or "")
            time.sleep(2.0)
            req_id, tree_body, proven = wait_runtime_tree(proc, req_id, run_id, errors)
            if proven:
                remote_tree = "proven"
            req_id, _ = play_stop(proc, req_id)
            req_id, after_headless = runtime_tree(proc, req_id, {"run_id": run_id})
            expect_not_remote(after_headless, errors, "runtime.tree after headless play.stop")
            errors.extend(project_godot_leak_errors("after headless play.stop"))
        elif start_body.get("ok") is True:
            errors.append(f"headless play.start paper-ACK playing=true: {start_body}")
            return errors, live, "unproven", gui_play, remote_tree
        else:
            headless_play = "unproven"
            code = str((start_body.get("error") or {}).get("code") or "")
            if code not in ("E_UNVERIFIED", "E_TIMEOUT", "E_BUSY"):
                errors.append(f"headless play.start must be typed fail, not invented ok: {start_body}")
        life.stop_proc(godot)
        godot = None
        time.sleep(1.0)
        kill_plugin_project_holders(godot=True, node=False)
        agent = PLUGIN_PROJECT / ".hh-agent"
        for name in ("file-leases.json", "writer.lock"):
            lock = agent / name
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        time.sleep(1.0)
        if plugin_godot_busy():
            errors.append("exclusive GUI Godot unavailable (plugin-project already held)")
            return errors, live, headless_play, "unrun", remote_tree
        godot, godot_lines = start_godot(exe, headless=False)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "GUI Godot hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, headless_play, "failed", remote_tree
        req_id, start_gui = play_start(proc, req_id, scene)
        if start_gui.get("ok") is True and after_of(start_gui).get("playing") is True:
            gui_play = "proven"
            req_id, _ = play_stop(proc, req_id)
            req_id, suite_proven = verify_runtime_suite(proc, req_id, errors, scene)
            if suite_proven:
                remote_tree = "proven"
        else:
            gui_play = "unproven"
            errors.append(
                "GUI play.start did not prove is_playing_scene "
                f"(Alternative): {sess.redact(json.dumps(start_gui), secret)}"
            )
        errors.extend(project_godot_leak_errors("after GUI suite"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"live runtime probe failed: {type(exc).__name__}: {exc}")
        live = "failed"
    finally:
        if godot is not None:
            try:
                tool_call(proc, req_id, "godot.play", "stop", {"reason": "test"}, timeout=10.0)
            except Exception:
                pass
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
        errors.extend(cleanup_temp())
        errors.extend(project_godot_leak_errors("after suite cleanup"))
    return errors, live, headless_play, gui_play, remote_tree


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    errors.extend(release_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    catalog = json.loads(ACTIONS_JSON.read_text(encoding="utf-8")) if ACTIONS_JSON.is_file() else {}
    actions = catalog.get("actions") if isinstance(catalog.get("actions"), dict) else {}
    for action_id, verb in (
        ("runtime.tree", "tree"),
        ("runtime.node", "node"),
        ("runtime.state", "state"),
    ):
        spec = actions.get(action_id) if isinstance(actions.get(action_id), dict) else {}
        if spec.get("method") != "godot.runtime" or spec.get("verb") != verb:
            errors.append(f"actions.json missing {action_id}")
        if spec.get("side_effect") != "read":
            errors.append(f"{action_id} must stay a READ")

    built = subprocess.run(
        ["npm.cmd" if os.name == "nt" else "npm", "run", "build"],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"bridge build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL")
        for item in errors:
            print(f"  - {item}")
        return 1

    exe, pin_reason = plug.find_pinned_godot()
    live = "unrun"
    headless_play = "unproven"
    gui_play = "unrun"
    remote_tree = "unproven"
    if exe is None:
        errors.append(f"pinned Godot required: {pin_reason}")
    else:
        version = plug.godot_version(exe)
        if version != PINNED_VERSION:
            errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        else:
            live_errs, live, headless_play, gui_play, remote_tree = live_errors(exe)
            errors.extend(live_errs)

    errors.extend(project_godot_leak_errors("after official test"))
    errors.extend(cleanup_temp())
    if errors:
        print(
            f"FAIL: runtime probe; LIVE={live}; HEADLESS_PLAY={headless_play}; "
            f"GUI_PLAY={gui_play}; REMOTE_TREE={remote_tree}; screenshots={SCREENSHOTS}"
        )
        for item in errors:
            print(f"  - {item}")
        return 1
    print(
        f"PASS: runtime.tree remote paging + secret redaction + export skip(); "
        f"LIVE={live}; HEADLESS_PLAY={headless_play}; GUI_PLAY={gui_play}; "
        f"REMOTE_TREE={remote_tree}; screenshots={SCREENSHOTS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
