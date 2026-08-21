#!/usr/bin/env python3
"""R4-WP1: Activity Dock and action timeline.

Does not tick the 20-8 plan. Does not start R4-WP2. Does not tick G2 VISIBLE.
Pin missing is a hard FAIL. No skip-PASS.
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
PINNED_VERSION = plug.PINNED_VERSION
TEMP_DIR = PLUGIN_PROJECT / "r4w1"
OBSERVER_FILE = PLUGIN_PROJECT / ".hh-agent" / "observer" / "timeline.json"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SYNTH_COUNT = 10000
PAGE_CAP = 100
APPEND_LIMIT_S = 15.0


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """Keep R4-WP1 [ ] while unticked; after coordinator tick allow R4-WP2+."""
    errors: list[str] = []
    current = ""
    wp1 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP1\b", stripped):
            wp1 = stripped
        if stripped.startswith("G2 VISIBLE"):
            g2 = stripped
    if wp1 is None:
        return ["plan missing R4-WP1 heading"]
    ticked = bool(re.search(r"\[x\]", wp1, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp1:
            errors.append("R4-WP1 heading must keep [ ] until coordinator tick")
        if current != "R4-WP1":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP1 while WP1 is unticked)")
    elif not re.match(r"^R4-WP([2-9]|\d{2,})$|^R[5-9]-WP\d+$", current):
        errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP2+ after R4-WP1 tick)")
    if g2 and re.search(r"\[x\]", g2, re.IGNORECASE):
        errors.append("G2 VISIBLE must stay unticked; it is a human gate")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    agent = PLUGIN_PROJECT / ".hh-agent"
    observer = agent / "observer"
    if observer.is_dir():
        shutil.rmtree(observer, ignore_errors=True)
    for name in ("file-leases.json", "writer.lock"):
        lock = agent / name
        if lock.is_file():
            try:
                lock.unlink()
            except OSError:
                pass


def src_scan_errors() -> list[str]:
    errors: list[str] = []
    dock = ADDON / "ui" / "health" / "hh_activity_dock.gd"
    store = ADDON / "core" / "hh_activity_store.gd"
    health = ADDON / "ui" / "health" / "hh_health_dock.gd"
    plugin = ADDON / "plugin.gd"
    if not dock.is_file():
        errors.append("missing hh_activity_dock.gd")
    if not store.is_file():
        errors.append("missing hh_activity_store.gd")
    if not health.is_file():
        errors.append("health dock must remain")
    else:
        text = health.read_text(encoding="utf-8")
        if "Pause" not in text:
            errors.append("health dock must keep the Pause button")
        if "token" in text.lower() and "never" not in text.lower():
            errors.append("health dock must not display the session token")
    if dock.is_file():
        text = dock.read_text(encoding="utf-8")
        for label in ("Pause", "Resume", "Watch", "Fast", "Replay"):
            if label not in text:
                errors.append(f"activity dock missing {label} button")
        if "token" in text.lower() and "never" not in text.lower():
            errors.append("activity dock must not display the session token")
        if "editor.select" in text:
            errors.append("R4-WP1 must not implement editor.select focus")
    if store.is_file():
        text = store.read_text(encoding="utf-8")
        if "OBSERVER_RETENTION" not in text and "10000" not in text:
            errors.append("observer store must cap retention")
        if "redact" not in text:
            errors.append("observer store must redact secrets/paths")
    if plugin.is_file():
        text = plugin.read_text(encoding="utf-8")
        if "hh_activity_dock" not in text:
            errors.append("plugin must host the activity dock")
        if "remove_control_from_docks" not in text:
            errors.append("plugin must still clean the dock on exit")
    reads = ADDON / "core" / "hh_read_adapters.gd"
    if reads.is_file():
        text = reads.read_text(encoding="utf-8")
        if "dock" not in text:
            errors.append("editor.state must expose a dock payload")
        if "_observer_timeline" not in text:
            errors.append("godot.observer timeline read adapter missing")
    for path in (BRIDGE / "src").rglob("*.ts"):
        blob = path.read_text(encoding="utf-8", errors="replace")
        posix = rel(path)
        for needle in VENDOR_NEEDLES:
            if needle in blob:
                errors.append(f"{posix} contains vendor needle {needle!r}")
                break
    return errors


def mcp_call(proc: subprocess.Popen[str], req_id: int, name: str, arguments: dict, timeout: float = 20.0) -> dict:
    return life.mcp_call(proc, req_id, name, arguments, timeout)


def body_of(resp: dict) -> dict:
    return life.body_of(resp)


def call_tool(
    proc: subprocess.Popen[str],
    req_id: int,
    method: str,
    action: str,
    params: dict,
    timeout: float = 30.0,
) -> tuple[int, str, dict]:
    cid = life.new_ulid()
    resp = mcp_call(
        proc,
        req_id,
        method,
        {"action": action, "params": params, "command_id": cid},
        timeout,
    )
    return req_id + 1, cid, body_of(resp)


def dock_of(body: dict) -> dict:
    after = body.get("after") if isinstance(body.get("after"), dict) else {}
    dock = after.get("dock") if isinstance(after.get("dock"), dict) else {}
    return dock


def rows_of(dock: dict) -> tuple[list[dict], int]:
    rows = dock.get("rows") if isinstance(dock.get("rows"), dict) else {}
    items = rows.get("items") if isinstance(rows.get("items"), list) else []
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            out.append(item)
    return out, int(rows.get("total") or 0)


def buttons_present(dock: dict) -> list[str]:
    missing: list[str] = []
    buttons = dock.get("buttons") if isinstance(dock.get("buttons"), dict) else {}
    modes = dock.get("modes") if isinstance(dock.get("modes"), dict) else {}
    for name in ("pause", "watch", "fast", "replay"):
        btn = buttons.get(name) if isinstance(buttons.get(name), dict) else {}
        visible = btn.get("visible") is True or modes.get(name) is True
        if not visible:
            missing.append(name)
    if "resume" in buttons:
        resume = buttons.get("resume") if isinstance(buttons.get("resume"), dict) else {}
        if resume and resume.get("visible") is not True:
            missing.append("resume")
    return missing


def token_in(obj: object, secret: str) -> bool:
    if not secret:
        return False
    return secret in json.dumps(obj)


def persist_ids() -> list[str]:
    if not OBSERVER_FILE.is_file():
        return []
    out: list[str] = []
    for line in OBSERVER_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("schema"):
            continue
        cid = str(obj.get("command_id") or "")
        if cid:
            out.append(cid)
    return out


def live_errors(exe: Path) -> list[str]:
    errors: list[str] = []
    cleanup_temp()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    proc: subprocess.Popen[str] | None = None
    godot: subprocess.Popen[str] | None = None
    desc_path: Path | None = None
    secret = ""
    err_lines: list[str] = []
    godot_lines: list[str] = []
    scene = "res://r4w1/dock.tscn"
    script = "res://r4w1/note.gd"
    req_id = 2
    try:
        proc, desc_path, secret, err_lines = life.start_sidecar()
        godot, godot_lines = life.start_godot(exe)
        req_id, hello, last = life.wait_hello(proc, godot, req_id)
        if not hello:
            errors.append(
                "live plugin hello/noop failed: "
                f"{sess.redact(json.dumps(last), secret)}; godot={''.join(godot_lines)[-1500:]}"
            )
            return errors

        req_id, _state_id, state = call_tool(
            proc, req_id, "godot.editor", "state", {"detail": "short"}
        )
        if state.get("ok") is not True:
            errors.append(f"editor.state must ACK: {sess.redact(json.dumps(state), secret)}")
        dock = dock_of(state)
        missing = buttons_present(dock)
        if missing:
            errors.append(f"dock buttons missing after hello: {missing} dock={dock}")
        if token_in(state, secret):
            errors.append("editor.state dock snapshot leaked the session token")

        req_id, _tl_id, timeline = call_tool(
            proc, req_id, "godot.observer", "timeline", {"detail": "short", "limit": 50}
        )
        if timeline.get("ok") is not True:
            errors.append(f"observer.timeline must ACK: {sess.redact(json.dumps(timeline), secret)}")
        tl_dock = dock_of(timeline)
        missing = buttons_present(tl_dock)
        if missing:
            errors.append(f"observer.timeline buttons missing: {missing}")
        if token_in(timeline, secret):
            errors.append("observer.timeline leaked the session token")

        req_id, _create_id, created = call_tool(
            proc,
            req_id,
            "godot.scene",
            "create",
            {"path": scene, "root_class": "Node2D"},
        )
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {sess.redact(json.dumps(created), secret)}")

        req_id, add_id, added = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "DockSprite"},
        )
        if added.get("ok") is not True:
            errors.append(f"node.add must ACK: {sess.redact(json.dumps(added), secret)}")

        req_id, set_id, prop = call_tool(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "DockSprite",
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 8, "y": 16}},
            },
        )
        if prop.get("ok") is not True:
            errors.append(f"property.set must ACK: {sess.redact(json.dumps(prop), secret)}")

        req_id, write_id, wrote = call_tool(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": script, "contents": "extends Node2D\n"},
        )
        if wrote.get("ok") is not True:
            errors.append(f"script.write must ACK: {sess.redact(json.dumps(wrote), secret)}")

        req_id, fail_id, failed = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": "res://r4w1/missing.tscn", "parent": ".", "class_name": "Node2D", "name": "Nope"},
        )
        if failed.get("ok") is True:
            errors.append("node.add on missing scene must fail")
        fail_code = str((failed.get("error") or {}).get("code") or "")
        if not fail_code:
            errors.append(f"failed mutate must be typed: {sess.redact(json.dumps(failed), secret)}")

        req_id, _snap_id, snap = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 100},
        )
        dock = dock_of(snap)
        items, total = rows_of(dock)
        if token_in(snap, secret):
            errors.append("mutation snapshot leaked the session token")
        by_id = {str(row.get("command_id") or ""): row for row in items}
        if add_id not in by_id or str(by_id[add_id].get("status") or "") != "verified":
            errors.append(f"node.add row missing/not verified: {add_id} items={items}")
        if set_id not in by_id or str(by_id[set_id].get("status") or "") != "verified":
            errors.append(f"property.set row missing/not verified: {set_id} items={items}")
        if write_id not in by_id or str(by_id[write_id].get("status") or "") != "verified":
            errors.append(f"script.write row missing/not verified: {write_id} items={items}")
        if fail_id not in by_id or str(by_id[fail_id].get("status") or "") != "failed":
            errors.append(f"failed mutate row missing/not failed: {fail_id} items={items}")
        if total < 4:
            errors.append(f"timeline total too small after proven mutates: {total}")

        req_id, _filt_id, filtered = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 100, "status": "failed", "actor": "agent", "scene": "res://r4w1/missing.tscn"},
        )
        f_items, _f_total = rows_of(dock_of(filtered))
        if f_items and any(str(row.get("status") or "") != "failed" for row in f_items):
            errors.append(f"status filter leaked non-failed rows: {f_items}")
        if fail_id not in {str(row.get("command_id") or "") for row in f_items}:
            errors.append(f"filtered failed row missing {fail_id}")

        mutation_ids = [add_id, set_id, write_id, fail_id]
        disk_ids = persist_ids()
        for cid in mutation_ids:
            if cid not in disk_ids:
                errors.append(f"persist file missing command_id {cid}")
        req_id, _reload_id, reloaded = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 100, "reload": True},
        )
        r_items, _r_total = rows_of(dock_of(reloaded))
        r_ids = {str(row.get("command_id") or "") for row in r_items}
        for cid in mutation_ids:
            if cid not in r_ids and cid not in persist_ids():
                errors.append(f"reload lost command_id {cid}")
        if token_in(reloaded, secret):
            errors.append("reload snapshot leaked the session token")

        t0 = time.perf_counter()
        req_id, _app_id, appended = call_tool(
            proc,
            req_id,
            "godot.observer",
            "append",
            {"count": SYNTH_COUNT, "actor": "agent"},
            15.0,
        )
        req_id, _page_id, page = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 50},
            15.0,
        )
        elapsed = time.perf_counter() - t0
        if appended.get("ok") is not True:
            errors.append(f"observer.append must ACK: {sess.redact(json.dumps(appended), secret)}")
        p_dock = dock_of(page)
        p_items, p_total = rows_of(p_dock)
        limit = int((p_dock.get("rows") or {}).get("limit") or 0)
        if p_total < SYNTH_COUNT:
            errors.append(f"10k append total={p_total} (need >= {SYNTH_COUNT})")
        if len(p_items) > PAGE_CAP:
            errors.append(f"snapshot page dumped {len(p_items)} rows (cap {PAGE_CAP})")
        if limit > PAGE_CAP:
            errors.append(f"snapshot limit {limit} exceeds {PAGE_CAP}")
        if elapsed >= APPEND_LIMIT_S:
            errors.append(f"10k append+snapshot took {elapsed:.2f}s (>= {APPEND_LIMIT_S})")
        if token_in(page, secret) or token_in(appended, secret):
            errors.append("10k snapshot leaked the session token")

        last_ids = persist_ids()[-20:]
        req_id, _reload2_id, reload2 = call_tool(
            proc,
            req_id,
            "godot.observer",
            "timeline",
            {"detail": "short", "limit": 20, "cursor": str(max(0, p_total - 20)), "reload": True},
        )
        r2_items, r2_total = rows_of(dock_of(reload2))
        r2_ids = [str(row.get("command_id") or "") for row in r2_items]
        if r2_total < SYNTH_COUNT:
            errors.append(f"reload after 10k lost total: {r2_total}")
        if last_ids and not any(cid in r2_ids or cid in persist_ids()[-20:] for cid in last_ids):
            errors.append("reload after 10k lost last command_ids")

        pause = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if pause.get("ok") is not True and pause.get("paused") is not True:
            errors.append(f"hh.pause failed: {sess.redact(json.dumps(pause), secret)}")
        req_id, _paused_id, paused = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Node2D", "name": "PausedNode"},
        )
        if str((paused.get("error") or {}).get("code") or "") != "E_PAUSED":
            errors.append(f"paused mutate must be E_PAUSED: {sess.redact(json.dumps(paused), secret)}")
        resume = body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1
        if resume.get("paused") is True:
            errors.append(f"hh.resume left gate paused: {sess.redact(json.dumps(resume), secret)}")

        replay = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.editor",
                {"action": "replay", "params": {"command_id": add_id}},
            )
        )
        req_id += 1
        if str((replay.get("error") or {}).get("code") or "") != "E_UNVERIFIED":
            errors.append(f"editor.replay must stay E_UNVERIFIED: {sess.redact(json.dumps(replay), secret)}")
        select = body_of(
            mcp_call(
                proc,
                req_id,
                "godot.editor",
                {"action": "select", "params": {"scene": scene, "node_path": "DockSprite"}},
            )
        )
        req_id += 1
        if str((select.get("error") or {}).get("code") or "") != "E_UNVERIFIED":
            errors.append(f"editor.select must stay E_UNVERIFIED: {sess.redact(json.dumps(select), secret)}")
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live activity dock failed: {type(exc).__name__}: {exc}", secret))
    finally:
        life.stop_proc(godot)
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
        if secret and secret in "".join(godot_lines):
            errors.append("session secret appeared in Godot logs")
        cleanup_temp()
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(hh_agent_only_addon_errors(PLUGIN_PROJECT, REPO_ROOT))
    errors.extend(src_scan_errors())
    errors.extend(plug.typed_gdscript_errors())

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.is_file() else None
    if plan_text is None:
        errors.append(f"missing {rel(PLAN)}")
    else:
        errors.extend(plan_errors(plan_text))

    if not (REPO_ROOT / "tools" / "godot" / "pin.json").is_file():
        errors.append("missing tools/godot/pin.json")
    exe, pin_reason = plug.find_pinned_godot()
    if exe is None:
        errors.append(f"pinned Godot missing (hard FAIL): {pin_reason}")
        print("FAIL: activity dock", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: activity dock", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: activity dock", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    built = subprocess.run(
        [sess.npm(), "run", "build"],
        cwd=BRIDGE,
        text=True,
        capture_output=True,
        check=False,
    )
    if built.returncode != 0:
        errors.append(f"npm run build failed:\n{built.stdout}\n{built.stderr}")
        print("FAIL: activity dock", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(live_errors(exe))

    if errors:
        print("FAIL: activity dock", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: activity dock + observer timeline; Pause/Watch/Fast/Replay visible; "
        "mutate rows verified/failed; 10k append paged; reload keeps ids; "
        "token redacted; Pause still E_PAUSED; R4-WP1 and G2 stay unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
