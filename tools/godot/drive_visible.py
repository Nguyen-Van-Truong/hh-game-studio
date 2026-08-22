#!/usr/bin/env python3
"""Drive the already-open plugin-project Godot GUI (G2 watch).

Starts the sidecar only. Does NOT launch a second Godot. Does NOT tick G2.
Keep hh-godot-editor.bat on minimal-2d.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "bootstrap"))
import test_scene_lifecycle as life
import test_session as sess

SCENE = "res://r4w6/visible.tscn"
TEX = "res://r4w6/sprite_tex.tres"
SCRIPT = "res://r4w6/visible_sprite.gd"
WATCH_NAME = "VisibleSprite"
SCRIPT_TEXT = "extends Sprite2D\n\nfunc _ready() -> void:\n\tpass\n"
SCHEMA = "hh-godot-variant/1"
WATCH = {"mode": "watch"}
PAUSE_S = 4.5
PLUGIN_PROJECT = REPO_ROOT / "godot" / "plugin-project"
REVIEW_DIR = PLUGIN_PROJECT / ".hh-agent" / "review"
REPORT_PATH = REVIEW_DIR / "g2_report.json"
TSCN_ABS = PLUGIN_PROJECT / "r4w6" / "visible.tscn"
NODE_HEADER_RE = re.compile(r'\[node name="([^"]+)"([^\]]*)\]')
DUPES = [
    "VisibleSprite2",
    "VisibleS",
    "VisibleSprite2D",
    "WatchMe",
    "WatchMe2",
    "WatchMe3",
    "WatchMe4",
]


def announce(msg: str) -> None:
    print(f"[drive] {msg}", flush=True)


def err_code(body: dict) -> str:
    err = body.get("error") if isinstance(body.get("error"), dict) else {}
    return str(err.get("code") or "")


def wait_live_hello(proc, req_id: int, timeout: float = 45.0) -> tuple[int, bool, dict]:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        if proc.poll() is not None:
            return req_id, False, {"error": {"code": "E_UNCERTAIN", "message": "sidecar exited"}}
        last = life.body_of(life.mcp_call(proc, req_id, "hh.plugin_noop", {}))
        req_id += 1
        if last.get("ok") is True and (last.get("postcondition") or {}).get("checks") == ["noop"]:
            return req_id, True, last
        time.sleep(0.4)
    return req_id, False, last


def call(proc, req_id: int, method: str, action: str, params: dict, timeout: float = 30.0):
    cid = life.new_ulid()
    resp = life.mcp_call(
        proc,
        req_id,
        method,
        {"action": action, "params": params, "command_id": cid, "presentation": WATCH},
        timeout,
    )
    return req_id + 1, cid, life.body_of(resp)


def must_ok(body: dict, label: str, secret: str) -> None:
    if body.get("ok") is True:
        announce(f"OK {label}")
        return
    raise RuntimeError(f"{label} failed: {sess.redact(json.dumps(body), secret)}")


def added_name_of(body: dict) -> str:
    after = body.get("after") if isinstance(body.get("after"), dict) else {}
    name = str(after.get("name") or "")
    if name:
        return name
    path_s = str(after.get("path") or "")
    if not path_s:
        return ""
    return path_s.rsplit("/", 1)[-1]


def refuse_renamed_sibling(body: dict, secret: str) -> None:
    got = added_name_of(body)
    if got == WATCH_NAME:
        return
    raise RuntimeError(
        f"node.add renamed sibling {got!r}; refusing as {WATCH_NAME}: "
        f"{sess.redact(json.dumps(body), secret)}"
    )


def remove_leftovers(proc, req_id: int) -> int:
    for name in DUPES:
        req_id, _, body = call(
            proc, req_id, "godot.node", "remove", {"scene": SCENE, "node_path": name}
        )
        if body.get("ok") is True:
            announce(f"removed leftover {name}")
        else:
            announce(f"skip leftover {name}")
    return req_id


def visible_tscn_leftover_fail(text: str) -> str:
    """Structural leftover scan of saved visible.tscn. Not a finite DUPES list."""
    headers = NODE_HEADER_RE.findall(text)
    if not headers:
        return "visible.tscn has no [node name= headers"
    children: list[str] = []
    for name, rest in headers:
        if "parent=" in rest:
            children.append(name)
    if len(children) > 1:
        return (
            "visible.tscn has more than one [node name= child besides root: "
            + ", ".join(children)
        )
    if "VisibleSprite2" in text:
        return "VisibleSprite2 appear in visible.tscn"
    if "WatchMe" in text:
        return "WatchMe appear in visible.tscn"
    return ""


def fail_if_saved_tscn_dirty() -> str:
    if not TSCN_ABS.is_file():
        return f"visible.tscn missing after scene.save: {TSCN_ABS.as_posix()}"
    text = TSCN_ABS.read_text(encoding="utf-8", errors="replace")
    return visible_tscn_leftover_fail(text)


def present_sprite(proc, req_id: int) -> int:
    """Select + focus Inspector on VisibleSprite, stay on 2D, frame the view."""
    req_id, _, sel = call(
        proc,
        req_id,
        "godot.editor",
        "select",
        {"scene": SCENE, "node_path": WATCH_NAME, "property": "position"},
    )
    announce(f"editor.select {WATCH_NAME} ok={sel.get('ok')} err={err_code(sel)}")
    req_id, _, focused = call(
        proc, req_id, "godot.editor", "focus", {"scene": SCENE, "node_path": WATCH_NAME}
    )
    announce(f"editor.focus {WATCH_NAME} ok={focused.get('ok')} err={err_code(focused)}")
    req_id, _, screen = call(proc, req_id, "godot.editor", "main_screen", {"screen": "2D"})
    announce(f"editor.main_screen 2D ok={screen.get('ok')} err={err_code(screen)}")
    req_id, _, framed = call(
        proc, req_id, "godot.editor", "frame_view", {"scene": SCENE, "node_path": WATCH_NAME}
    )
    announce(f"editor.frame_view {WATCH_NAME} ok={framed.get('ok')} err={err_code(framed)}")
    return req_id


def checkpoint_ref_of(body: dict) -> str:
    after = body.get("after") if isinstance(body.get("after"), dict) else {}
    for key in ("checkpoint_id", "git_ref", "ref"):
        raw = after.get(key)
        if raw:
            return str(raw)
        raw = body.get(key)
        if raw:
            return str(raw)
    return ""


def print_checklist() -> None:
    announce("CHECKLIST for the human reviewer:")
    announce("  1. Look at res://r4w6/visible.tscn (this scene only).")
    announce("  2. Confirm ONE VisibleSprite selected, Inspector shows Sprite2D,")
    announce("     cyan overlay on the sprite, and timeline rows in HH Agent dock.")
    announce("  3. Press Pause / Replay / Revert yourself on the dock.")
    announce("  4. Revert should use the drive checkpoint of visible.tscn, not snake.")
    announce("  5. This run does not sign G2. Play is Alternative (not success).")


def write_unsigned_report(payload: dict) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    announce(f"wrote unsigned report {REPORT_PATH.as_posix()}")


def main() -> int:
    announce("starting sidecar for godot/plugin-project (no second Godot)")
    announce("look at Godot: HH Agent Activity dock should flip to bridge: connected")
    print_checklist()
    proc, _desc_path, secret, err_lines = life.start_sidecar()
    req_id = 2
    last_mutate_id = ""
    replay_id = ""
    checkpoint_command_id = ""
    checkpoint_ref = ""
    checkpoint_ok = False
    checkpoint_err = ""
    alternatives: list[dict] = []
    play_code = "E_UNVERIFIED"
    replay_ok = False
    replay_code = ""
    pause_note = ""
    try:
        announce("If dock still says disconnected: Godot menu Project -> Reload Current Project")
        req_id, hello, last = wait_live_hello(proc, req_id, timeout=120.0)
        if not hello:
            announce("plugin did not hello. Keep hh-godot-g2.bat Godot open.")
            announce(f"last={sess.redact(json.dumps(last), secret)}")
            announce(f"sidecar_err={''.join(err_lines)[-800:]}")
            return 2
        announce("CONNECTED. Watch the left dock + 2D viewport + Inspector.")
        announce(f"Scene under review: {SCENE}")
        announce("Opening visible.tscn first so first paint is not last-scene snake.")

        req_id, open_id, opened = call(proc, req_id, "godot.scene", "open", {"path": SCENE})
        if opened.get("ok") is True:
            announce("OK scene.open first (visible.tscn)")
            last_mutate_id = open_id
        else:
            announce(
                f"scene.open first failed err={err_code(opened)}; create then open anyway"
            )
            req_id, create_id, created = call(
                proc, req_id, "godot.scene", "create", {"path": SCENE, "root_class": "Node2D"}
            )
            if err_code(created) != "E_CONFLICT":
                must_ok(created, "scene.create", secret)
                last_mutate_id = create_id
            req_id, open_id, opened = call(proc, req_id, "godot.scene", "open", {"path": SCENE})
            must_ok(opened, "scene.open after create", secret)
            last_mutate_id = open_id
        req_id = remove_leftovers(proc, req_id)
        req_id = present_sprite(proc, req_id)

        req_id, checkpoint_command_id, ckpt = call(
            proc,
            req_id,
            "godot.git",
            "checkpoint",
            {
                "message": "r4w6-visible-g2-watch",
                "paths": [SCENE, SCRIPT, TEX],
            },
        )
        checkpoint_ok = ckpt.get("ok") is True
        checkpoint_ref = checkpoint_ref_of(ckpt)
        checkpoint_err = err_code(ckpt)
        if checkpoint_ok:
            announce(
                f"OK git.checkpoint command_id={checkpoint_command_id} ref={checkpoint_ref}"
            )
        else:
            announce(
                "git.checkpoint FAILED "
                f"command_id={checkpoint_command_id} err={checkpoint_err} "
                f"body={sess.redact(json.dumps(ckpt), secret)}"
            )
            announce("continuing without inventing a checkpoint success")
        time.sleep(PAUSE_S)

        req_id, add_id, added = call(
            proc,
            req_id,
            "godot.node",
            "add",
            {"scene": SCENE, "parent": ".", "class_name": "Sprite2D", "name": WATCH_NAME},
        )
        if err_code(added) == "E_CONFLICT":
            announce(f"node.add {WATCH_NAME} E_CONFLICT (node already there); skip")
            req_id, open2_id, opened = call(proc, req_id, "godot.scene", "open", {"path": SCENE})
            must_ok(opened, "scene.open after VisibleSprite exists", secret)
            last_mutate_id = open2_id
        else:
            must_ok(added, f"node.add {WATCH_NAME}", secret)
            refuse_renamed_sibling(added, secret)
            last_mutate_id = add_id
            replay_id = add_id
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, _, tex = call(
            proc,
            req_id,
            "godot.resource",
            "create",
            {"path": TEX, "class_name": "PlaceholderTexture2D"},
        )
        if err_code(tex) != "E_CONFLICT":
            must_ok(tex, "resource.create texture", secret)
        req_id, size_id, sized = call(
            proc,
            req_id,
            "godot.resource",
            "edit",
            {
                "path": TEX,
                "property": "size",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 96, "y": 96}},
            },
        )
        must_ok(sized, "resource.edit PlaceholderTexture2D.size", secret)
        last_mutate_id = size_id
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, assign_id, assigned = call(
            proc,
            req_id,
            "godot.resource",
            "assign",
            {
                "scene": SCENE,
                "node_path": WATCH_NAME,
                "property": "texture",
                "resource": TEX,
            },
        )
        must_ok(assigned, "resource.assign texture", secret)
        last_mutate_id = assign_id
        replay_id = assign_id
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, jump_id, jumped = call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": SCENE,
                "node_path": WATCH_NAME,
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 80, "y": 80}},
            },
        )
        must_ok(jumped, "property.set position 80,80 (watch the pink square move)", secret)
        last_mutate_id = jump_id
        replay_id = jump_id
        req_id = present_sprite(proc, req_id)
        announce("HUMAN: press Pause on the dock NOW. You have 10 seconds.")
        announce("If Pause works, the next move will NOT happen.")
        time.sleep(10.0)
        req_id, probe_id, probed = call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": SCENE,
                "node_path": WATCH_NAME,
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 260, "y": 160}},
            },
        )
        if err_code(probed) == "E_PAUSED" or probed.get("ok") is not True:
            pause_note = f"human Pause blocked move err={err_code(probed)}"
            announce("Pause WORKED — pink square stayed. HUMAN: press Resume NOW (8 seconds).")
            time.sleep(8.0)
            resume_body = life.body_of(life.mcp_call(proc, req_id, "hh.resume", {}))
            req_id += 1
            announce(
                f"hh.resume ok={resume_body.get('ok')} paused={resume_body.get('paused')} "
                f"err={err_code(resume_body)}"
            )
        else:
            pause_note = "human Pause was not on; probe move applied"
            announce("Pause was not pressed in time; square moved. That is OK, keep watching.")
            last_mutate_id = probe_id
            replay_id = probe_id
        req_id = present_sprite(proc, req_id)

        req_id, move_id, moved = call(
            proc,
            req_id,
            "godot.property",
            "set",
            {
                "scene": SCENE,
                "node_path": WATCH_NAME,
                "property": "position",
                "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 180, "y": 120}},
            },
        )
        if err_code(moved) == "E_PAUSED":
            announce("still paused — press Resume on the dock")
            time.sleep(6.0)
            life.body_of(life.mcp_call(proc, req_id, "hh.resume", {}))
            req_id += 1
            req_id, move_id, moved = call(
                proc,
                req_id,
                "godot.property",
                "set",
                {
                    "scene": SCENE,
                    "node_path": WATCH_NAME,
                    "property": "position",
                    "value": {"schema": SCHEMA, "type": "Vector2", "value": {"x": 180, "y": 120}},
                },
            )
        must_ok(moved, "property.set position 180,120", secret)
        last_mutate_id = move_id
        replay_id = move_id
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, write_id, wrote = call(
            proc,
            req_id,
            "godot.script",
            "write",
            {"path": SCRIPT, "contents": SCRIPT_TEXT},
        )
        must_ok(wrote, "script.write", secret)
        last_mutate_id = write_id
        announce("script.write may open Script editor; returning to main_screen 2D")
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, attach_id, attached = call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": SCENE, "node_path": WATCH_NAME, "path": SCRIPT},
        )
        must_ok(attached, "script.attach", secret)
        last_mutate_id = attach_id
        replay_id = attach_id
        req_id = present_sprite(proc, req_id)
        time.sleep(PAUSE_S)

        req_id, save_id, saved = call(proc, req_id, "godot.scene", "save", {"path": SCENE})
        must_ok(saved, "scene.save", secret)
        last_mutate_id = save_id
        req_id = present_sprite(proc, req_id)
        announce("scanning visible.tscn for leftover [node name= children")
        leftover = fail_if_saved_tscn_dirty()
        if leftover:
            announce(f"FAIL: {leftover}")
            return 2
        announce("OK visible.tscn one [node name= child besides root")

        replay_target = replay_id or last_mutate_id or life.new_ulid()
        req_id, _, replayed = call(
            proc, req_id, "godot.editor", "replay", {"command_id": replay_target}
        )
        replay_ok = replayed.get("ok") is True
        replay_code = err_code(replayed)
        announce(f"editor.replay ok={replayed.get('ok')} err={replay_code} changed={replayed.get('changed')}")
        req_id = present_sprite(proc, req_id)

        req_id, _, play_body = call(
            proc,
            req_id,
            "godot.play",
            "start",
            {"scene": SCENE, "mode": "play"},
        )
        play_code = err_code(play_body) or "E_UNVERIFIED"
        if play_body.get("ok") is True:
            announce("play.start returned ok=true; still Alternative, not a signed Play.")
        else:
            announce(f"play.start Alternative err={play_code} (expected E_UNVERIFIED; not success)")
        alternatives.append(
            {
                "action": "play.start",
                "native_ui": "Editor Play (F5) / play current scene",
                "reason": play_code,
                "paper_ack": False,
            }
        )

        report = {
            "schema": "hh-g2-visible-e2e/1",
            "g2_signed": False,
            "screenshots": "SKIP",
            "video": "SKIP",
            "human_start": "hh-godot-g2.bat",
            "scene": SCENE,
            "checkpoint_command_id": checkpoint_command_id,
            "checkpoint_ref": checkpoint_ref,
            "checkpoint_ok": checkpoint_ok,
            "checkpoint_error": checkpoint_err,
            "pause": pause_note,
            "replay_ok": replay_ok,
            "replay_error": replay_code,
            "alternatives": alternatives,
            "gaps": [
                "play.start is Alternative (E_UNVERIFIED / not dispatched)",
                "screenshots=SKIP video=SKIP; no dummy PNG",
                "this harness does not sign G2",
            ],
        }
        write_unsigned_report(report)

        announce("DONE. Timeline should have rows. Replay is presentation-only.")
        print_checklist()
        announce("sidecar stays up. Leave this window open. Ctrl+C to stop.")
        while proc.poll() is None:
            time.sleep(2.0)
        return 0
    finally:
        life.stop_proc(proc)


if __name__ == "__main__":
    raise SystemExit(main())
