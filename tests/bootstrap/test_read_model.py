#!/usr/bin/env python3
"""R2-WP6: read model, doctor E2E, MCP resources, 1k-node paging.

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

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hh_agent_allow import hh_agent_only_addon_errors
import test_plugin_router as plug
import test_session as sess

BRIDGE = REPO_ROOT / "bridge"
PLAN = REPO_ROOT / "zdocs" / "20-8-godot-agent-autopilot-plan.txt"
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
ADDON = PLUGIN_PROJECT / "addons" / "hh_agent"
EDITOR_BAT = REPO_ROOT / "hh-godot-editor.bat"
PINNED_VERSION = plug.PINNED_VERSION
PROTOCOL = "hh-godot-agent/1"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


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


VENDOR_NEEDLES = plug.VENDOR_NEEDLES
TREE_FIXTURE = PLUGIN_PROJECT / "fixtures" / "tree_1k.tscn"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R2-WP6 unticked for this implementer; allow R2-WP7+ after coordinator tick."""
    errors: list[str] = []
    current = ""
    wp6 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R2-WP6\b", stripped):
            wp6 = stripped
    if wp6 is None:
        return ["plan missing R2-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R2-WP6 heading must keep [ ] until coordinator tick")
        if current != "R2-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP6 while WP6 is unticked)")
    elif not re.match(r"^R2-WP[7-9]$|^R2-WP\d{2,}$|^R[3-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R2-WP7+ after R2-WP6 tick)")
    return errors


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    for path in (BRIDGE / "src").rglob("*.ts"):
        text = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        if "0.0.0.0" in text:
            errors.append(f"{posix} binds or mentions 0.0.0.0")
        if "npx -y" in text:
            errors.append(f"{posix} uses npx -y")
        for needle in VENDOR_NEEDLES:
            if needle in text:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    pkg = (BRIDGE / "package.json").read_text(encoding="utf-8")
    for extra in ("better-sqlite3", "godot-mcp", "ws"):
        if extra in pkg:
            errors.append(f"bridge/package.json added extra dep {extra}")
    if EDITOR_BAT.is_file():
        bat = EDITOR_BAT.read_text(encoding="utf-8", errors="replace")
        if "minimal-2d" not in bat:
            errors.append("hh-godot-editor.bat must stay on minimal-2d")
        if "plugin-project" in bat:
            errors.append("hh-godot-editor.bat must not retarget to plugin-project")
    if "no read adapter" in (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8"):
        if "return _reads.handle" not in (ADDON / "core" / "hh_router.gd").read_text(encoding="utf-8"):
            errors.append("router still auto-rejects every read")
    return errors


def write_tree_1k(path: Path) -> int:
    lines = ['[gd_scene format=3 uid="uid://hhreadtree1k000"]', "", '[node name="Tree1k" type="Node"]', ""]
    for i in range(1000):
        lines.append(f'[node name="N{i:04d}" type="Node" parent="."]')
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1001


def cleanup_tree_fixture() -> None:
    for extra in (
        TREE_FIXTURE,
        TREE_FIXTURE.with_suffix(".tscn.uid"),
        Path(str(TREE_FIXTURE) + ".uid"),
        Path(str(TREE_FIXTURE) + ".import"),
    ):
        if extra.is_file():
            extra.unlink()
    fixtures = TREE_FIXTURE.parent
    if fixtures.is_dir() and not any(fixtures.iterdir()):
        fixtures.rmdir()


def doctor_cli(project: Path, extra: list[str] | None = None) -> dict:
    cmd = [sess.node(), str(BRIDGE / "dist" / "main.js"), "--project", str(project), "--doctor"]
    if extra:
        cmd.extend(extra)
    proc = subprocess.run(
        cmd,
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
        timeout=40,
    )
    parsed: dict = {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            parsed = json.loads(line)
    parsed["_exit"] = proc.returncode
    parsed["_stderr"] = proc.stderr or ""
    return parsed


def mcp_rpc(proc: subprocess.Popen[str], req_id: int, method: str, params: dict | None = None) -> dict:
    assert proc.stdin and proc.stdout
    msg: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(sess.readline_timeout(proc.stdout, 12.0))


def resource_has_secret(body: dict, secret: str) -> bool:
    dumped = json.dumps(body)
    return bool(secret) and secret in dumped


def test_skew_and_static() -> list[str]:
    errors: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="hh-r2wp6-doctor-"))
    (tmp / "project.godot").write_text('; tmp\nconfig_version=5\n', encoding="utf-8")
    built = subprocess.run(
        [sess.npm(), "run", "generate"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run generate failed:\n{built.stdout}\n{built.stderr}")
        return errors
    built2 = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built2.returncode != 0:
        errors.append(f"npm run build failed:\n{built2.stdout}\n{built2.stderr}")
        return errors
    fake = tmp / ("fake-godot.cmd" if os.name == "nt" else "fake-godot")
    if os.name == "nt":
        fake.write_text("@echo 4.7.2.stable.official.deadbeef\r\n", encoding="utf-8")
    else:
        fake.write_text("#!/bin/sh\necho 4.7.2.stable.official.deadbeef\n", encoding="utf-8")
        fake.chmod(0o755)
    godot_skew = doctor_cli(tmp, ["--godot-exe", str(fake)])
    err = godot_skew.get("error") or {}
    if godot_skew.get("ok") is True:
        errors.append("wrong Godot --version must not report ok true")
    if err.get("code") != "E_VERSION_SKEW":
        errors.append(f"measured wrong Godot must be E_VERSION_SKEW: {godot_skew}")
    if godot_skew.get("_exit") == 0:
        errors.append("version skew doctor must exit non-zero")
    proto_root = Path(tempfile.mkdtemp(prefix="hh-r2wp6-proto-"))
    (proto_root / "project.godot").write_text("; proto\nconfig_version=5\n", encoding="utf-8")
    (proto_root / ".hh-agent").mkdir()
    (proto_root / ".hh-agent" / "protocol").write_text("hh-godot-agent/2\n", encoding="utf-8")
    proto = doctor_cli(proto_root)
    if proto.get("ok") is True or (proto.get("error") or {}).get("code") != "E_VERSION_SKEW":
        errors.append(f"planted protocol file must be E_VERSION_SKEW: {proto}")
    schema_root = Path(tempfile.mkdtemp(prefix="hh-r2wp6-schema-"))
    (schema_root / "project.godot").write_text("; schema\nconfig_version=5\n", encoding="utf-8")
    (schema_root / ".hh-agent").mkdir()
    (schema_root / ".hh-agent" / "schema-version").write_text("hh-godot-actions/99\n", encoding="utf-8")
    schema = doctor_cli(schema_root)
    if schema.get("ok") is True or (schema.get("error") or {}).get("code") != "E_VERSION_SKEW":
        errors.append(f"planted schema file must be E_VERSION_SKEW: {schema}")
    vendor_root = Path(tempfile.mkdtemp(prefix="hh-r2wp6-vendor-"))
    (vendor_root / "project.godot").write_text("; satelliteoflove vendor\nconfig_version=5\n", encoding="utf-8")
    vendor = doctor_cli(vendor_root)
    policy_row = next(
        (row for row in (vendor.get("check_details") or []) if isinstance(row, dict) and row.get("id") == "policy"),
        {},
    )
    if policy_row.get("ok") is not False:
        errors.append(f"vendor needle must fail policy: {vendor}")
    scan = subprocess.run(
        [
            sess.node(),
            "--input-type=module",
            "-e",
            "import { tokenAbsentFromBlob } from './dist/doctor/doctor.js'; "
            "console.log(JSON.stringify({ ok: tokenAbsentFromBlob(JSON.stringify({t:'SECRET64'}), 'SECRET64') }))",
        ],
        cwd=str(BRIDGE),
        text=True,
        capture_output=True,
        check=False,
    )
    scan_body = {}
    for line in (scan.stdout or "").splitlines():
        if line.startswith("{"):
            scan_body = json.loads(line)
    if scan_body.get("ok") is not False:
        errors.append(f"token scanner must fail when the secret is in the blob: {scan.stdout} {scan.stderr}")
    baseline = doctor_cli(PLUGIN_PROJECT)
    if baseline.get("token_in_report") is not False:
        errors.append("doctor must set token_in_report false")
    if "LOCALAPPDATA/HHGodotAgent" not in json.dumps(baseline):
        errors.append("doctor must name LOCALAPPDATA/HHGodotAgent")
    ids = {row.get("id") for row in (baseline.get("check_details") or []) if isinstance(row, dict)}
    for needed in (
        "binary",
        "templates",
        "plugin",
        "bridge",
        "token_redacted",
        "schema",
        "git",
        "policy",
        "protocol",
    ):
        if needed not in ids:
            errors.append(f"doctor missing check {needed}")
    policy_ok = next(
        (row for row in (baseline.get("check_details") or []) if isinstance(row, dict) and row.get("id") == "policy"),
        {},
    )
    if policy_ok.get("ok") is not True:
        errors.append(f"plugin-project policy should pass: {policy_ok}")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(proto_root, ignore_errors=True)
    shutil.rmtree(schema_root, ignore_errors=True)
    shutil.rmtree(vendor_root, ignore_errors=True)
    return errors


def run_live() -> tuple[list[str], str, str]:
    errors: list[str] = []
    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        return [f"live editor required (pin missing is a hard fail): {pin_reason}"], "failed", "failed"
    version = plug.godot_version(exe)
    if version != PINNED_VERSION:
        return [f"Godot --version {version!r} != {PINNED_VERSION}"], "failed", "failed"

    write_tree_1k(TREE_FIXTURE)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    live = "failed"
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
        secret = str(desc.get("token") or "")
        init = mcp_rpc(
            proc,
            1,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-read-model", "version": "0"},
            },
        )
        if "result" not in init:
            errors.append(f"MCP initialize failed: {init}")
        caps = (init.get("result") or {}).get("capabilities") or {}
        if "resources" not in caps:
            errors.append("initialize must advertise resources")

        env = os.environ.copy()
        env.pop("HH_AGENT_SELFTEST", None)
        env.pop("HH_AGENT_SELFTEST_OUT", None)
        env.pop("HH_AGENT_RELOAD_N", None)
        env.pop("HH_AGENT_RELOAD_OUT", None)
        env["HH_READ_OPEN_SCENE"] = "res://fixtures/tree_1k.tscn"
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

        hello = False
        deadline = time.time() + 30.0
        req_id = 2
        last: dict = {}
        while time.time() < deadline:
            if godot.poll() is not None or proc.poll() is not None:
                break
            last = plug.mcp_call(proc, req_id, "hh.plugin_noop", {})
            req_id += 1
            body = (last.get("result") or {}).get("structuredContent") or {}
            if body.get("ok") is True and (body.get("postcondition") or {}).get("checks") == ["noop"]:
                hello = True
                break
            time.sleep(0.25)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors, live, "live Godot connected=no"

        opened = False
        open_deadline = time.time() + 15.0
        while time.time() < open_deadline:
            state_wait = plug.mcp_call(
                proc,
                req_id,
                "godot.editor",
                {"action": "state", "params": {"detail": "short"}},
            )
            req_id += 1
            wait_body = (state_wait.get("result") or {}).get("structuredContent") or {}
            edited = str(((wait_body.get("after") or {}).get("edited_scene") or ""))
            if "tree_1k" in edited:
                opened = True
                break
            time.sleep(0.2)
        if not opened:
            errors.append("HH_READ_OPEN_SCENE did not make tree_1k the edited scene")

        listed = mcp_rpc(proc, req_id, "resources/list")
        req_id += 1
        resources = (listed.get("result") or {}).get("resources") or []
        uris = {row.get("uri") for row in resources if isinstance(row, dict)}
        for uri in ("project://summary", "editor://state", "capability://matrix"):
            if uri not in uris:
                errors.append(f"resources/list missing {uri}")
            read = mcp_rpc(proc, req_id, "resources/read", {"uri": uri})
            req_id += 1
            contents = (read.get("result") or {}).get("contents") or []
            if not contents:
                errors.append(f"resources/read {uri} empty: {read}")
                continue
            text = str(contents[0].get("text") or "")
            if secret and secret in text:
                errors.append(f"{uri} leaked the session token")
            if '"token":' in text and "[redacted]" not in text and uri != "capability://matrix":
                if re.search(r'"token":\s*"[^[]', text):
                    errors.append(f"{uri} contains a raw token field")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                errors.append(f"{uri} text was not JSON")
                payload = {}
            if uri == "capability://matrix" and payload.get("mutate_dispatched") is not False:
                errors.append("capability://matrix must declare mutate_dispatched false")
            if uri == "capability://matrix":
                select = next(
                    (
                        row
                        for row in (payload.get("actions") or [])
                        if isinstance(row, dict) and row.get("id") == "editor.select"
                    ),
                    {},
                )
                if select.get("adapter") != "view-state-mutate-not-wp6":
                    errors.append(f"editor.select must not be labeled a read adapter: {select}")
            if uri == "editor://state" and payload.get("connected") is not True:
                errors.append(f"editor://state must hit the live plugin: {payload}")
            if uri == "editor://state" and "tree_1k" not in str(payload.get("edited_scene") or ""):
                errors.append(f"editor://state must show the opened 1k fixture: {payload}")
            if uri == "project://summary":
                inspect = payload.get("inspect") if isinstance(payload.get("inspect"), dict) else {}
                if inspect.get("source") != "editor":
                    errors.append(f"project://summary must come from the live plugin: {payload}")

        doctor = plug.mcp_call(proc, req_id, "hh.doctor", {})
        req_id += 1
        doc = (doctor.get("result") or {}).get("structuredContent") or {}
        if resource_has_secret(doc, secret):
            errors.append("hh.doctor leaked the session token")
        if doc.get("token_in_report") is not False:
            errors.append("hh.doctor token_in_report must be false")
        if doc.get("pin_version_id") != PINNED_VERSION:
            errors.append(f"hh.doctor pin_version_id {doc.get('pin_version_id')!r}")

        inspect = plug.mcp_call(
            proc,
            req_id,
            "godot.project",
            {"action": "inspect", "params": {"detail": "short"}},
        )
        req_id += 1
        inspect_body = (inspect.get("result") or {}).get("structuredContent") or {}
        if inspect_body.get("ok") is not True:
            errors.append(f"live project.inspect must ACK: {sess.redact(json.dumps(inspect), secret)}")
        else:
            live = "ran"

        state = plug.mcp_call(
            proc,
            req_id,
            "godot.editor",
            {"action": "state", "params": {"detail": "short"}},
        )
        req_id += 1
        state_body = (state.get("result") or {}).get("structuredContent") or {}
        if state_body.get("ok") is not True:
            errors.append(f"live editor.state must ACK: {sess.redact(json.dumps(state), secret)}")
        after_state = state_body.get("after") or {}
        if after_state.get("godot") and after_state.get("godot") != PINNED_VERSION:
            errors.append(f"editor.state godot {after_state.get('godot')!r} != pin")

        describe = plug.mcp_call(
            proc,
            req_id,
            "godot.capabilities",
            {"action": "describe", "params": {"kind": "version", "limit": 8}},
        )
        req_id += 1
        describe_body = (describe.get("result") or {}).get("structuredContent") or {}
        if describe_body.get("ok") is not True:
            errors.append(f"live capabilities.describe failed: {sess.redact(json.dumps(describe), secret)}")
        classes = ((describe_body.get("after") or {}).get("classes") or {})
        items = classes.get("items") or []
        if len(items) > 8:
            errors.append(f"class page dumped {len(items)} entries")
        if int(classes.get("total") or 0) < 50:
            errors.append(f"ClassDB total too small: {classes}")
        if classes.get("has_more") is not True:
            errors.append("ClassDB page should have_more")

        page1 = plug.mcp_call(
            proc,
            req_id,
            "godot.scene",
            {
                "action": "read",
                "params": {"path": "res://fixtures/tree_1k.tscn", "detail": "short", "limit": 40},
            },
        )
        req_id += 1
        p1 = (page1.get("result") or {}).get("structuredContent") or {}
        tree1 = ((p1.get("after") or {}).get("tree") or {})
        items1 = tree1.get("items") or []
        if p1.get("ok") is not True:
            errors.append(f"1k scene.read page1 failed: {sess.redact(json.dumps(page1), secret)}")
        if (p1.get("after") or {}).get("source") != "edited":
            errors.append(f"1k scene.read must walk the edited tree, not instantiate: {p1.get('after')}")
        if len(items1) > 40:
            errors.append(f"1k page1 dumped {len(items1)} nodes")
        if int(tree1.get("total") or 0) < 1000:
            errors.append(f"1k tree total {tree1.get('total')} < 1000")
        cursor = str(tree1.get("next_cursor") or "")
        if not cursor:
            errors.append("1k page1 missing next_cursor")
        page2 = plug.mcp_call(
            proc,
            req_id,
            "godot.scene",
            {
                "action": "read",
                "params": {
                    "path": "res://fixtures/tree_1k.tscn",
                    "detail": "short",
                    "limit": 40,
                    "cursor": cursor or "40",
                },
            },
        )
        req_id += 1
        p2 = (page2.get("result") or {}).get("structuredContent") or {}
        tree2 = ((p2.get("after") or {}).get("tree") or {})
        items2 = tree2.get("items") or []
        paths1 = {row.get("path") for row in items1 if isinstance(row, dict)}
        paths2 = {row.get("path") for row in items2 if isinstance(row, dict)}
        if paths1 and paths2 and paths1 & paths2:
            errors.append("1k pages overlapped")
        if len(items2) > 40:
            errors.append(f"1k page2 dumped {len(items2)} nodes")

        prop = plug.mcp_call(
            proc,
            req_id,
            "godot.property",
            {
                "action": "get",
                "params": {
                    "scene": "res://fixtures/tree_1k.tscn",
                    "node_path": ".",
                    "property": "name",
                },
            },
        )
        req_id += 1
        prop_body = (prop.get("result") or {}).get("structuredContent") or {}
        if prop_body.get("ok") is not True:
            errors.append(f"live property.get must ACK: {sess.redact(json.dumps(prop), secret)}")
        query = plug.mcp_call(
            proc,
            req_id,
            "godot.node",
            {
                "action": "query",
                "params": {
                    "scene": "res://fixtures/tree_1k.tscn",
                    "by": "type",
                    "class_name": "Node",
                    "limit": 20,
                },
            },
        )
        req_id += 1
        query_body = (query.get("result") or {}).get("structuredContent") or {}
        if query_body.get("ok") is not True:
            errors.append(f"live node.query must ACK: {sess.redact(json.dumps(query), secret)}")
        script_read = plug.mcp_call(
            proc,
            req_id,
            "godot.script",
            {
                "action": "read",
                "params": {"path": "res://addons/hh_agent/plugin.gd", "limit": 8},
            },
        )
        req_id += 1
        script_body = (script_read.get("result") or {}).get("structuredContent") or {}
        if script_body.get("ok") is not True:
            errors.append(f"live script.read must ACK: {sess.redact(json.dumps(script_read), secret)}")
        play_status = plug.mcp_call(
            proc,
            req_id,
            "godot.play",
            {"action": "status", "params": {"detail": "short"}},
        )
        req_id += 1
        play_body = (play_status.get("result") or {}).get("structuredContent") or {}
        if play_body.get("ok") is not True:
            errors.append(f"live play.status must ACK: {sess.redact(json.dumps(play_status), secret)}")
        class_page = plug.mcp_call(
            proc,
            req_id,
            "godot.capabilities",
            {"action": "describe", "params": {"kind": "class", "class_name": "Node2D", "limit": 8}},
        )
        req_id += 1
        class_body = (class_page.get("result") or {}).get("structuredContent") or {}
        if class_body.get("ok") is not True:
            errors.append(f"live capabilities.describe class must ACK: {sess.redact(json.dumps(class_page), secret)}")
        diag = plug.mcp_call(
            proc,
            req_id,
            "godot.script",
            {"action": "diagnostics", "params": {"path": "res://addons/hh_agent/plugin.gd"}},
        )
        req_id += 1
        diag_body = (diag.get("result") or {}).get("structuredContent") or {}
        if (diag_body.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"script.diagnostics must stay E_UNVERIFIED: {diag_body}")
        logs = plug.mcp_call(
            proc,
            req_id,
            "hh.command",
            {
                "command_id": new_ulid(),
                "method": "godot.play",
                "action": "logs",
                "params": {"limit": 50},
            },
        )
        req_id += 1
        logs_body = (logs.get("result") or {}).get("structuredContent") or {}
        if (logs_body.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"play.logs must stay E_UNVERIFIED: {logs_body}")
        select = plug.mcp_call(
            proc,
            req_id,
            "godot.editor",
            {
                "action": "select",
                "params": {"scene": "res://fixtures/tree_1k.tscn", "node_path": "N0000"},
            },
        )
        req_id += 1
        select_body = (select.get("result") or {}).get("structuredContent") or {}
        if (select_body.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"editor.select must stay E_UNVERIFIED: {select_body}")

        mutate = plug.mcp_call(
            proc,
            req_id,
            "godot.node",
            {
                "action": "add",
                "params": {
                    "scene": "res://fixtures/tree_1k.tscn",
                    "parent": ".",
                    "class_name": "Node2D",
                    "name": "AgentWroteThis",
                },
            },
        )
        mutate_body = (mutate.get("result") or {}).get("structuredContent") or {}
        if (mutate_body.get("error") or {}).get("code") != "E_UNVERIFIED":
            errors.append(f"mutate must stay E_UNVERIFIED: {mutate_body}")
        if mutate_body.get("ok") is True:
            errors.append("mutate returned ok true")
        if TREE_FIXTURE.read_text(encoding="utf-8").count("AgentWroteThis"):
            errors.append("mutate wrote a node into the fixture scene")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live read-model run failed: {type(exc).__name__}: {exc}", secret))
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
            lock = desc_path.with_name("sidecar.lock")
            if lock.is_file():
                try:
                    lock.unlink()
                except OSError:
                    pass
        if secret and secret in "".join(err_lines):
            errors.append("session secret appeared in sidecar logs")
        cleanup_tree_fixture()
    return errors, live, "live Godot 4.7.1-stable editor + plugin"


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))
    errors.extend(test_skew_and_static())
    live_errors, live_editor, live_note = run_live()
    errors.extend(live_errors)
    if errors:
        print("FAIL: read model", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    print(
        "PASS: read adapters + doctor E2E + MCP resources; "
        f"LIVE_EDITOR={live_editor}; {live_note}; "
        "1k paging on edited tree; version skew from planted files/--version; "
        "mutate still not applied; R2-WP6 stays [ ]."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
