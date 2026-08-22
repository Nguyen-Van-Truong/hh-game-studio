#!/usr/bin/env python3
"""R4-WP6: visible E2E harness (automated half). Does not sign G2.

Runs create scene → add Sprite2D → assign texture → move → script → Play
on plugin-project. Headless editor is OK for AUTOMATED coverage; this test
does not claim pixels or G2 VISIBLE. Play stays honest: if play.start /
play.input is E_UNVERIFIED, record Alternative — do not paper-ACK.

Does not tick the 20-8 plan. Does not tick G2 VISIBLE. Does not start R5.
Pin missing is a hard FAIL. No skip-PASS. No dummy screenshot PNGs.
"""

from __future__ import annotations

import hashlib
import json
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
TEMP_DIR = PLUGIN_PROJECT / "r4w6"
REVIEW_DIR = PLUGIN_PROJECT / ".hh-agent" / "review"
REPORT_PATH = REVIEW_DIR / "g2_report.json"
EDITOR_BAT = REPO_ROOT / "hh-godot-editor.bat"
G2_BAT = REPO_ROOT / "hh-godot-g2.bat"
VENDOR_NEEDLES = plug.VENDOR_NEEDLES
SCHEMA = "hh-godot-variant/1"
SCRIPT_TEXT = "extends Sprite2D\n\nfunc _ready() -> void:\n\tpass\n"


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def plan_errors(text: str) -> list[str]:
    """R4-WP6 [ ] until coordinator tick; after human G2 sign both WP6 and G2 are [x]."""
    errors: list[str] = []
    current = ""
    wp6 = None
    r5wp1 = None
    g2 = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("CURRENT_VALID_WP="):
            current = stripped.split("=", 1)[1].strip()
        if re.match(r"^R4-WP6\b", stripped):
            wp6 = stripped
        if re.match(r"^R5-WP1\b", stripped):
            r5wp1 = stripped
        if stripped.startswith("G2 VISIBLE") and ("[x]" in stripped or "[ ]" in stripped):
            if g2 is None:
                g2 = stripped
    if wp6 is None:
        return ["plan missing R4-WP6 heading"]
    ticked = bool(re.search(r"\[x\]", wp6, re.IGNORECASE))
    g2_ticked = bool(g2 and re.search(r"\[x\]", g2, re.IGNORECASE))
    if not ticked:
        if "[ ]" not in wp6:
            errors.append("R4-WP6 heading must keep [ ] until coordinator tick")
        if current != "R4-WP6":
            errors.append(f"CURRENT_VALID_WP={current!r} (need R4-WP6 while WP6 is unticked)")
        if r5wp1 and re.search(r"\[x\]", r5wp1, re.IGNORECASE):
            errors.append("R5-WP1 must stay unticked; R5 depends on human G2")
        if g2_ticked:
            errors.append("G2 VISIBLE must stay [ ] until human sign + coordinator tick")
    else:
        if not re.match(r"^R5-WP\d+$|^R[6-9]-WP\d+$|^RX-WP\d+$", current):
            errors.append(f"CURRENT_VALID_WP={current!r} (need R5-WP1+ after R4-WP6 tick)")
        if g2 is None:
            errors.append("plan missing G2 VISIBLE gate")
        elif not g2_ticked:
            errors.append("G2 VISIBLE must be [x] after human sign when R4-WP6 is ticked")
    if g2 is None:
        errors.append("plan missing G2 VISIBLE gate")
    return errors


def cleanup_temp() -> None:
    if TEMP_DIR.is_dir():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    if REPORT_PATH.is_file():
        try:
            REPORT_PATH.unlink()
        except OSError:
            pass
    if REVIEW_DIR.is_dir():
        shutil.rmtree(REVIEW_DIR, ignore_errors=True)
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
    self_text = Path(__file__).read_text(encoding="utf-8")
    if "g2_signed" not in self_text or 'g2_signed": false' not in self_text.replace("'", '"'):
        if "g2_signed" not in self_text or "False" not in self_text:
            errors.append("official test must write g2_signed false")
    if re.search(r"g2_signed\s*=\s*True|g2_signed\": true", self_text):
        errors.append("official test must not sign G2")
    if "screenshots" not in self_text or "SKIP" not in self_text:
        errors.append("official test must report screenshots=SKIP in headless")
    if re.search(r"\.write_bytes\(|Image\.new\b|write_text\([^\n]*\.png", self_text):
        errors.append("official test must not bless dummy screenshot PNGs")
    if self_text.count('"name": "VisibleSprite"') < 2:
        errors.append("official test must call node.add again with the same name VisibleSprite")
    if "E_CONFLICT" not in self_text:
        errors.append("official test must expect E_CONFLICT on second node.add same name")
    if "*2" not in self_text and "VisibleSprite2" not in self_text:
        errors.append("official test must fail if second add creates a *2 sibling")
    if "play.start" not in self_text or "play.input" not in self_text:
        errors.append("official test must run play.start and play.input")
    if "paper-ACK" not in self_text and "paper_ack" not in self_text:
        if "do not paper" not in self_text.lower() and "not paper-ACK" not in self_text:
            errors.append("official test must refuse to paper-ACK Play")
    if "hh.pause" not in self_text or "hh.resume" not in self_text:
        errors.append("official test must Pause mid-scenario and Resume")
    if "editor.replay" not in self_text and "godot.editor" not in self_text:
        errors.append("official test must Replay after the scenario")
    if "git.revert_checkpoint" not in self_text:
        errors.append("official test must Revert a checkpoint")
    if EDITOR_BAT.is_file():
        bat = EDITOR_BAT.read_text(encoding="utf-8", errors="replace")
        if "4.7.1" not in bat or "minimal-2d" not in bat:
            errors.append("hh-godot-editor.bat must stay pin 4.7.1 on minimal-2d")
        if "4.7.2" in bat:
            errors.append("hh-godot-editor.bat must not retarget 4.7.2")
        if "plugin-project" in bat:
            errors.append("hh-godot-editor.bat must not retarget the human fixture to plugin-project")
    else:
        errors.append("missing hh-godot-editor.bat")
    if not G2_BAT.is_file():
        errors.append("missing hh-godot-g2.bat (human Start on plugin-project)")
    else:
        g2 = G2_BAT.read_text(encoding="utf-8", errors="replace")
        if "4.7.1" not in g2:
            errors.append("hh-godot-g2.bat must stay on the 4.7.1 pin")
        if "4.7.2" in g2:
            errors.append("hh-godot-g2.bat must not bump 4.7.2")
        if "plugin-project" not in g2:
            errors.append("hh-godot-g2.bat must open godot/plugin-project")
        if re.search(r"--path.*minimal-2d", g2):
            errors.append("hh-godot-g2.bat must not steal the minimal-2d human fixture")
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
    presentation: dict | None = None,
) -> tuple[int, str, dict]:
    cid = life.new_ulid()
    arguments: dict = {"action": action, "params": params, "command_id": cid}
    if presentation:
        arguments["presentation"] = presentation
    resp = mcp_call(proc, req_id, method, arguments, timeout)
    return req_id + 1, cid, body_of(resp)


def after_of(body: dict) -> dict:
    after = body.get("after") if isinstance(body.get("after"), dict) else {}
    return after


def token_in(obj: object, secret: str) -> bool:
    if not secret:
        return False
    return secret in json.dumps(obj)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dock_of(body: dict) -> dict:
    after = after_of(body)
    dock = after.get("dock") if isinstance(after.get("dock"), dict) else {}
    return dock


def timeline_rows(body: dict) -> list[dict]:
    rows = dock_of(body).get("rows") if isinstance(dock_of(body).get("rows"), dict) else {}
    items = rows.get("items") if isinstance(rows.get("items"), list) else []
    out: list[dict] = []
    for item in items:
        if isinstance(item, dict):
            out.append(item)
    return out


def timeline_ids(body: dict) -> set[str]:
    return {str(row.get("command_id") or "") for row in timeline_rows(body) if row.get("command_id")}


def err_code(body: dict) -> str:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    return str(err.get("code") or "")


def second_add_same_name_errors(body: dict, secret: str, name: str) -> list[str]:
    """Second node.add of an existing sibling name must be E_CONFLICT, not ACK or *2."""
    found: list[str] = []
    after = after_of(body)
    got_name = str(after.get("name") or "")
    got_path = str(after.get("path") or after.get("node_path") or "")
    blob = sess.redact(json.dumps(body), secret)
    if body.get("ok") is True:
        found.append(
            f"second node.add same name {name} ACK-succeeded (must be E_CONFLICT): {blob}"
        )
    if err_code(body) != "E_CONFLICT":
        found.append(
            f"second node.add same name {name} error.code must be E_CONFLICT: {blob}"
        )
    two_name = f"{name}2"
    renamed = bool(got_name) and got_name != name
    if renamed or two_name in got_name or two_name in got_path:
        found.append(
            f"second node.add created *2 sibling name={got_name!r} path={got_path!r} "
            f"(must be E_CONFLICT)"
        )
    return found


def slim_focus(after: dict) -> dict:
    return {
        "selected_paths": after.get("selected_paths"),
        "inspector_class": after.get("inspector_class"),
        "inspector_path": after.get("inspector_path"),
        "script_path": after.get("script_path"),
        "script_line": after.get("script_line"),
        "main_screen": after.get("main_screen"),
    }


def slim_overlay(after: dict) -> dict:
    highlights = after.get("highlights") if isinstance(after.get("highlights"), list) else []
    return {
        "enabled": after.get("enabled"),
        "highlight_count": len(highlights),
        "last_replay": after.get("last_replay") if isinstance(after.get("last_replay"), dict) else {},
    }


def observe(
    proc: subprocess.Popen[str],
    req_id: int,
    command_id: str,
    secret: str,
    errors: list[str],
    label: str,
) -> tuple[int, dict]:
    ts_ms = int(time.time() * 1000)
    req_id, _tl_id, timeline = call_tool(
        proc, req_id, "godot.observer", "timeline", {"detail": "short", "limit": 100}
    )
    if timeline.get("ok") is not True:
        errors.append(f"observer.timeline after {label} must ACK: {sess.redact(json.dumps(timeline), secret)}")
    rows = timeline_rows(timeline)
    row = next((item for item in rows if str(item.get("command_id") or "") == command_id), None)
    req_id, _fc_id, focus = call_tool(proc, req_id, "godot.observer", "focus", {"detail": "short"})
    if focus.get("ok") is not True:
        errors.append(f"observer.focus after {label} must ACK: {sess.redact(json.dumps(focus), secret)}")
    req_id, _ov_id, overlay = call_tool(proc, req_id, "godot.observer", "overlay", {"detail": "short"})
    if overlay.get("ok") is not True:
        errors.append(f"observer.overlay after {label} must ACK: {sess.redact(json.dumps(overlay), secret)}")
    if token_in(timeline, secret) or token_in(focus, secret) or token_in(overlay, secret):
        errors.append(f"observer snapshot after {label} leaked the session token")
    step = {
        "name": label,
        "command_id": command_id,
        "ts_ms": ts_ms,
        "timeline": row is not None,
        "timeline_elapsed_ms": int((row or {}).get("elapsed_ms") or 0),
        "timeline_action": str((row or {}).get("action") or ""),
        "timeline_status": str((row or {}).get("status") or ""),
        "selection": slim_focus(after_of(focus)),
        "inspector": {
            "class": after_of(focus).get("inspector_class"),
            "path": after_of(focus).get("inspector_path"),
        },
        "overlay": slim_overlay(after_of(overlay)),
        "screenshot": "SKIP",
    }
    label_l = label.lower()
    if "play" not in label_l and "pause" not in label_l:
        selected = after_of(focus).get("selected_paths")
        inspector_class = after_of(focus).get("inspector_class")
        sel_empty = selected is None or selected == [] or selected == ""
        insp_empty = inspector_class is None or inspector_class == ""
        if sel_empty or insp_empty:
            errors.append(
                f"observer.focus after mutate {label} empty selected_paths or inspector_class: "
                f"selected_paths={selected!r} inspector_class={inspector_class!r}"
            )
    return req_id, step


def write_g2_report(payload: dict) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return REPORT_PATH


def report_errors(path: Path, secret: str, expect_coverage: float, replay_changed: bool) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"missing {rel(path)}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"g2_report.json is not JSON: {exc}"]
    if not isinstance(data, dict):
        return ["g2_report.json must be an object"]
    if data.get("g2_signed") is not False:
        errors.append(f"g2_signed must be false: {data.get('g2_signed')!r}")
    if data.get("screenshots") != "SKIP":
        errors.append(f"screenshots must be SKIP in headless: {data.get('screenshots')!r}")
    if data.get("video") != "SKIP":
        errors.append(f"video must be SKIP in headless: {data.get('video')!r}")
    coverage = data.get("coverage")
    if coverage != expect_coverage:
        errors.append(f"coverage {coverage!r} != {expect_coverage}")
    if data.get("replay_changed") is not replay_changed:
        errors.append(f"replay_changed {data.get('replay_changed')!r} != {replay_changed}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("g2_report.json missing steps[]")
    alts = data.get("alternatives")
    if not isinstance(alts, list) or not alts:
        errors.append("g2_report.json must list alternatives[] (do not hide gaps)")
    else:
        names = {str(item.get("action") or "") for item in alts if isinstance(item, dict)}
        if "play.start" not in names and not any("play.start" in str(item) for item in alts):
            errors.append("alternatives[] must name play.start when Play is unverified")
    raw = path.read_text(encoding="utf-8")
    if secret and secret in raw:
        errors.append("g2_report.json leaked the session token")
    return errors


def checkpoint_sha_errors(ckpt_id: str, dests: list[Path]) -> list[str]:
    man_path = PLUGIN_PROJECT / ".hh-agent" / "checkpoints" / ckpt_id / "manifest.json"
    if not man_path.is_file():
        return [f"checkpoint manifest missing after revert: {ckpt_id}"]
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"checkpoint manifest unreadable: {exc}"]
    by_rel = {
        str(row.get("rel") or ""): row
        for row in (man.get("files") or [])
        if isinstance(row, dict)
    }
    errors: list[str] = []
    root = PLUGIN_PROJECT.resolve()
    for dest in dests:
        rel_s = dest.resolve().relative_to(root).as_posix()
        row = by_rel.get(rel_s)
        if row is None:
            continue
        if row.get("missing") is True:
            if dest.is_file():
                errors.append(f"revert left unexpected dest {rel_s}")
            continue
        want = str(row.get("sha256") or "")
        got = sha256_file(dest)
        if got != want:
            errors.append(f"revert SHA mismatch {rel_s}: dest={got} snapshot={want}")
    return errors


def exclusive_green_errors() -> list[str]:
    errors: list[str] = []
    for name, script in (
        ("test_g1_base.py", REPO_ROOT / "tests" / "bootstrap" / "test_g1_base.py"),
        ("test_registry.py", REPO_ROOT / "tests" / "bootstrap" / "test_registry.py"),
        ("test_plugin_router.py", REPO_ROOT / "tests" / "bootstrap" / "test_plugin_router.py"),
    ):
        ran = subprocess.run(
            [sys.executable, str(script)],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if ran.returncode != 0:
            errors.append(
                f"keep-green {name} failed (exit {ran.returncode}):\n"
                f"{ran.stdout[-1500:]}\n{ran.stderr[-1500:]}"
            )
    return errors


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
    scene = "res://r4w6/visible.tscn"
    tex = "res://r4w6/sprite_tex.tres"
    script = "res://r4w6/visible_sprite.gd"
    scene_abs = PLUGIN_PROJECT / "r4w6" / "visible.tscn"
    script_abs = PLUGIN_PROJECT / "r4w6" / "visible_sprite.gd"
    req_id = 2
    steps: list[dict] = []
    alternatives: list[dict] = []
    mutate_ids: list[str] = []
    add_id = ""
    replay_changed = True
    revert_restored = False
    coverage = 0.0
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

        watch = {"mode": "watch"}

        req_id, create_id, created = call_tool(
            proc, req_id, "godot.scene", "create", {"path": scene, "root_class": "Node2D"}, presentation=watch
        )
        if created.get("ok") is not True:
            errors.append(f"scene.create must ACK: {sess.redact(json.dumps(created), secret)}")
            return errors
        mutate_ids.append(create_id)
        req_id, _sel0, _ = call_tool(
            proc, req_id, "godot.editor", "select", {"scene": scene, "node_path": "."}
        )
        req_id, step = observe(proc, req_id, create_id, secret, errors, "scene.create")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing scene.create {create_id}")
        steps.append(step)

        req_id, add_id, added = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Sprite2D", "name": "VisibleSprite"},
            presentation=watch,
        )
        if added.get("ok") is not True:
            errors.append(f"node.add Sprite2D must ACK: {sess.redact(json.dumps(added), secret)}")
            return errors
        mutate_ids.append(add_id)
        req_id, _sel1, _ = call_tool(
            proc, req_id, "godot.editor", "select", {"scene": scene, "node_path": "VisibleSprite"}
        )
        req_id, step = observe(proc, req_id, add_id, secret, errors, "node.add Sprite2D")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing node.add {add_id}")
        steps.append(step)

        req_id, add2_id, added2 = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Sprite2D", "name": "VisibleSprite"},
            presentation=watch,
        )
        errors.extend(second_add_same_name_errors(added2, secret, "VisibleSprite"))
        steps.append(
            {
                "name": "node.add VisibleSprite second (expect E_CONFLICT)",
                "command_id": add2_id,
                "ts_ms": int(time.time() * 1000),
                "ok": added2.get("ok") is True,
                "error": err_code(added2),
                "screenshot": "SKIP",
            }
        )

        req_id, tex_id, tex_body = call_tool(
            proc,
            req_id,
            "godot.resource",
            "create",
            {"path": tex, "class_name": "PlaceholderTexture2D"},
            presentation=watch,
        )
        if tex_body.get("ok") is not True:
            errors.append(f"resource.create PlaceholderTexture2D must ACK: {sess.redact(json.dumps(tex_body), secret)}")
            return errors
        mutate_ids.append(tex_id)
        req_id, step = observe(proc, req_id, tex_id, secret, errors, "resource.create texture")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing resource.create {tex_id}")
        steps.append(step)

        pause = body_of(mcp_call(proc, req_id, "hh.pause", {}))
        req_id += 1
        if pause.get("ok") is not True and pause.get("paused") is not True:
            errors.append(f"hh.pause failed: {sess.redact(json.dumps(pause), secret)}")
        req_id, paused_id, paused = call_tool(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "VisibleSprite", "property": "texture", "resource": tex},
        )
        if err_code(paused) != "E_PAUSED":
            errors.append(
                f"paused mutate must be E_PAUSED: {sess.redact(json.dumps(paused), secret)}"
            )
        steps.append(
            {
                "name": "resource.assign (paused)",
                "command_id": paused_id,
                "ts_ms": int(time.time() * 1000),
                "ok": False,
                "error": "E_PAUSED",
                "timeline": False,
                "screenshot": "SKIP",
            }
        )
        resume = body_of(mcp_call(proc, req_id, "hh.resume", {}))
        req_id += 1
        if resume.get("paused") is True:
            errors.append(f"hh.resume left gate paused: {sess.redact(json.dumps(resume), secret)}")

        req_id, assign_id, assigned = call_tool(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {"scene": scene, "node_path": "VisibleSprite", "property": "texture", "resource": tex},
            presentation=watch,
        )
        if assigned.get("ok") is not True:
            errors.append(f"resource.assign texture must ACK: {sess.redact(json.dumps(assigned), secret)}")
            return errors
        mutate_ids.append(assign_id)
        req_id, _sel2, _ = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene, "node_path": "VisibleSprite", "property": "texture"},
        )
        req_id, step = observe(proc, req_id, assign_id, secret, errors, "resource.assign texture")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing resource.assign {assign_id}")
        steps.append(step)

        req_id, move_id, moved = call_tool(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": scene,
                "node_path": "VisibleSprite",
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 48, "y": 32}},
            },
            presentation=watch,
        )
        if moved.get("ok") is not True:
            errors.append(f"property.set move must ACK: {sess.redact(json.dumps(moved), secret)}")
            return errors
        mutate_ids.append(move_id)
        req_id, _sel3, _ = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene, "node_path": "VisibleSprite", "property": "position"},
        )
        req_id, step = observe(proc, req_id, move_id, secret, errors, "property.set move")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing property.set {move_id}")
        steps.append(step)

        req_id, write_id, wrote = call_tool(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": script, "contents": SCRIPT_TEXT},
            presentation=watch,
        )
        if wrote.get("ok") is not True:
            errors.append(f"script.write must ACK: {sess.redact(json.dumps(wrote), secret)}")
            return errors
        mutate_ids.append(write_id)
        req_id, step = observe(proc, req_id, write_id, secret, errors, "script.write")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing script.write {write_id}")
        steps.append(step)

        req_id, attach_id, attached = call_tool(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": scene, "node_path": "VisibleSprite", "path": script},
            presentation=watch,
        )
        if attached.get("ok") is not True:
            errors.append(f"script.attach must ACK: {sess.redact(json.dumps(attached), secret)}")
            return errors
        mutate_ids.append(attach_id)
        req_id, _open, _ = call_tool(
            proc,
            req_id,
            "godot.editor",
            "select",
            {"scene": scene, "node_path": "VisibleSprite", "script_path": script, "script_line": 3},
        )
        req_id, step = observe(proc, req_id, attach_id, secret, errors, "script.attach")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing script.attach {attach_id}")
        steps.append(step)

        req_id, save_id, saved = call_tool(proc, req_id, "godot.scene", "save", {"path": scene}, presentation=watch)
        if saved.get("ok") is not True:
            errors.append(f"scene.save must ACK: {sess.redact(json.dumps(saved), secret)}")
            return errors
        if not scene_abs.is_file():
            errors.append(f"saved scene missing: {scene}")
            return errors
        mutate_ids.append(save_id)
        req_id, step = observe(proc, req_id, save_id, secret, errors, "scene.save")
        if step.get("timeline") is not True:
            errors.append(f"observer timeline missing scene.save {save_id}")
        steps.append(step)

        req_id, play_id, play_body = call_tool(
            proc,
            req_id,
            "godot.play",
            "start",
            {"scene": scene, "mode": "play"},
        )
        play_ok = play_body.get("ok") is True
        play_code = err_code(play_body)
        if play_ok:
            steps.append(
                {
                    "name": "play.start",
                    "command_id": play_id,
                    "ts_ms": int(time.time() * 1000),
                    "ok": True,
                    "screenshot": "SKIP",
                }
            )
        else:
            if play_code != "E_UNVERIFIED":
                errors.append(
                    f"play.start must stay E_UNVERIFIED or ACK honestly: "
                    f"{sess.redact(json.dumps(play_body), secret)}"
                )
            alternatives.append(
                {
                    "action": "play.start",
                    "native_ui": "Editor Play (F5) / play current scene",
                    "reason": play_code or "not dispatched",
                    "paper_ack": False,
                }
            )
            steps.append(
                {
                    "name": "play.start",
                    "command_id": play_id,
                    "ts_ms": int(time.time() * 1000),
                    "ok": False,
                    "error": play_code or "E_UNVERIFIED",
                    "alternative": True,
                    "screenshot": "SKIP",
                }
            )

        req_id, input_id, input_body = call_tool(
            proc,
            req_id,
            "godot.input",
            "action",
            {"action_name": "ui_accept", "phase": "press"},
        )
        input_ok = input_body.get("ok") is True
        input_code = err_code(input_body)
        if input_ok:
            errors.append("play.input inject must not paper-ACK: returned ok true")
        if input_code != "E_UNVERIFIED":
            errors.append(
                f"play.input inject must stay E_UNVERIFIED: {sess.redact(json.dumps(input_body), secret)}"
            )
        alternatives.append(
            {
                "action": "play.input",
                "native_ui": "Play process input / Editor debugger input",
                "reason": input_code or "E_UNVERIFIED",
                "paper_ack": False,
            }
        )
        steps.append(
            {
                "name": "play.input",
                "command_id": input_id,
                "ts_ms": int(time.time() * 1000),
                "ok": False,
                "error": input_code or "E_UNVERIFIED",
                "alternative": True,
                "screenshot": "SKIP",
            }
        )
        alternatives.append(
            {
                "action": "screenshots",
                "native_ui": "visible editor pixels / runtime.screenshot (R6)",
                "reason": "headless cannot capture; screenshots=SKIP; no dummy PNG",
                "paper_ack": False,
            }
        )

        req_id, _cov_id, cov_tl = call_tool(
            proc, req_id, "godot.observer", "timeline", {"detail": "short", "limit": 100}
        )
        present = timeline_ids(cov_tl)
        missing = [cid for cid in mutate_ids if cid not in present]
        coverage = (len(mutate_ids) - len(missing)) / len(mutate_ids) if mutate_ids else 0.0
        if missing:
            errors.append(
                f"timeline coverage missing command_ids {missing} "
                f"coverage={coverage:.0%} present={sorted(present)}"
            )
        if coverage != 1.0:
            errors.append(f"timeline coverage {coverage:.0%} != 100% of scenario mutates")

        before_sha = sha256_file(scene_abs)
        replay_target = add_id or mutate_ids[0]
        req_id, _rep_id, replayed = call_tool(
            proc, req_id, "godot.editor", "replay", {"command_id": replay_target}, presentation=watch
        )
        if replayed.get("ok") is not True:
            errors.append(f"editor.replay must ACK: {sess.redact(json.dumps(replayed), secret)}")
        if replayed.get("changed") is True:
            errors.append("editor.replay must not report a document change")
        after_replay = sha256_file(scene_abs)
        replay_changed = after_replay != before_sha
        if replay_changed:
            errors.append("replay changed scene SHA")
        if token_in(replayed, secret):
            errors.append("editor.replay leaked the session token")
        steps.append(
            {
                "name": "editor.replay",
                "command_id": replay_target,
                "ts_ms": int(time.time() * 1000),
                "ok": replayed.get("ok") is True,
                "replay_changed": replay_changed,
                "screenshot": "SKIP",
            }
        )

        req_id, _ckpt_id, ckpt = call_tool(
            proc,
            req_id,
            "godot.git",
            "checkpoint",
            {"message": "r4w6-visible-baseline", "paths": [scene, script]},
        )
        if ckpt.get("ok") is not True:
            errors.append(f"git.checkpoint must ACK: {sess.redact(json.dumps(ckpt), secret)}")
            return errors
        ckpt_ref = str((ckpt.get("after") or {}).get("checkpoint_id") or "")
        if len(ckpt_ref) < 7:
            errors.append(f"git.checkpoint missing checkpoint_id: {ckpt}")
            return errors
        dest_sha = sha256_file(scene_abs)

        req_id, _scratch_id, scratch = call_tool(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": scene, "parent": ".", "class_name": "Label", "name": "Scratch"},
        )
        if scratch.get("ok") is not True:
            errors.append(f"checkpoint-probe node.add must ACK: {sess.redact(json.dumps(scratch), secret)}")
        req_id, _save2_id, saved2 = call_tool(proc, req_id, "godot.scene", "save", {"path": scene})
        if saved2.get("ok") is not True:
            errors.append(f"checkpoint-probe save must ACK: {sess.redact(json.dumps(saved2), secret)}")
        if sha256_file(scene_abs) == dest_sha:
            errors.append("checkpoint-probe mutate did not change dest SHA")
        req_id, _rev_id, restored = call_tool(
            proc, req_id, "godot.git", "revert_checkpoint", {"ref": ckpt_ref}
        )
        if restored.get("ok") is not True:
            errors.append(f"git.revert_checkpoint must ACK: {sess.redact(json.dumps(restored), secret)}")
        errors.extend(checkpoint_sha_errors(ckpt_ref, [scene_abs, script_abs]))
        revert_sha = sha256_file(scene_abs)
        revert_restored = revert_sha == dest_sha
        if not revert_restored:
            errors.append(f"revert dest SHA {revert_sha} != checkpoint snapshot {dest_sha}")
        steps.append(
            {
                "name": "git.revert_checkpoint",
                "command_id": ckpt_ref,
                "ts_ms": int(time.time() * 1000),
                "ok": restored.get("ok") is True,
                "revert_restored": revert_restored,
                "screenshot": "SKIP",
            }
        )

        report = {
            "schema": "hh-g2-visible-e2e/1",
            "g2_signed": False,
            "screenshots": "SKIP",
            "video": "SKIP",
            "headless": True,
            "godot": PINNED_VERSION,
            "human_start": "hh-godot-g2.bat",
            "human_default_fixture": "hh-godot-editor.bat -> godot/test-projects/minimal-2d",
            "coverage": coverage,
            "replay_changed": replay_changed,
            "revert_restored": revert_restored,
            "mutate_command_ids": mutate_ids,
            "steps": steps,
            "alternatives": alternatives,
            "gaps": [
                "headless cannot capture pixels; G2 VISIBLE is a human gate",
                "play.start is E_UNVERIFIED (not dispatched) unless a later WP proves Play",
                "play.input inject stays E_UNVERIFIED",
                "this harness does not sign G2",
            ],
        }
        write_g2_report(report)
        if token_in(report, secret):
            errors.append("g2 report payload leaked the session token")
        errors.extend(report_errors(REPORT_PATH, secret, coverage, replay_changed))
    except Exception as exc:  # noqa: BLE001
        errors.append(sess.redact(f"live visible e2e failed: {type(exc).__name__}: {exc}", secret))
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
        print("FAIL: visible e2e", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    version = plug.godot_version(exe)
    if any(bad in version for bad in ("4.7.2", "4.8")):
        errors.append(f"refused Godot --version {version!r}")
        print("FAIL: visible e2e", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    if version != PINNED_VERSION:
        errors.append(f"Godot --version {version!r} != {PINNED_VERSION}")
        print("FAIL: visible e2e", file=sys.stderr)
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
        print("FAIL: visible e2e", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    errors.extend(live_errors(exe))
    if not errors:
        errors.extend(exclusive_green_errors())

    if errors:
        print("FAIL: visible e2e", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1

    print(
        "PASS: visible e2e harness; scenario mutates timeline coverage=100%; "
        "replay SHA stable; revert SHA restored; play.start/play.input listed as "
        "Alternative; screenshots=SKIP; g2_signed=false; R4-WP6 and G2 stay unticked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
