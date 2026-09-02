#!/usr/bin/env python3
"""Clean duplicate snake nodes and reload the drawn snake. Watch-mode, live GUI."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tests" / "bootstrap"))
import test_scene_lifecycle as life
import test_session as sess

SCENE = "res://snake/snake.tscn"
SCRIPT = "res://snake/snake_game.gd"
WATCH = {"mode": "watch"}
PAUSE = 1.6
DUPES = [
    "Board2",
    "Head2",
    "Food2",
    "Score2",
    "Board3",
    "Head3",
    "Food3",
    "Score3",
    "Board4",
    "Head",
    "Food",
    "Board",
]


def announce(msg: str) -> None:
    print(f"[polish] {msg}", flush=True)


def wait_hello(proc, req_id: int, timeout: float = 60.0):
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        if proc.poll() is not None:
            return req_id, False, last
        last = life.body_of(life.mcp_call(proc, req_id, "hh.plugin_noop", {}))
        req_id += 1
        if last.get("ok") is True:
            return req_id, True, last
        time.sleep(0.35)
    return req_id, False, last


def call(proc, req_id, method, action, params, timeout=30.0):
    cid = life.new_ulid()
    resp = life.mcp_call(
        proc,
        req_id,
        method,
        {"action": action, "params": params, "command_id": cid, "presentation": WATCH},
        timeout,
    )
    return req_id + 1, life.body_of(resp)


def main() -> int:
    script = (REPO_ROOT / "godot/plugin-project/snake/snake_game.gd").read_text(encoding="utf-8")
    proc, _desc, secret, err = life.start_sidecar()
    req = 2
    try:
        req, hello, last = wait_hello(proc, req)
        if not hello:
            announce("no plugin hello")
            announce(sess.redact(json.dumps(last), secret))
            announce("".join(err)[-400:])
            return 2
        announce("CONNECTED -- watch Scene tree: leftovers will disappear one by one")
        req, opened = call(proc, req, "godot.scene", "open", {"path": SCENE})
        if opened.get("ok") is not True:
            announce("open failed " + sess.redact(json.dumps(opened), secret))
            return 2
        req, _ = call(proc, req, "godot.editor", "main_screen", {"screen": "2D"})
        time.sleep(PAUSE)

        req, wrote = call(
            proc, req, "godot.script", "write", {"path": SCRIPT, "contents": script}
        )
        if wrote.get("ok") is not True:
            announce("script.write failed " + sess.redact(json.dumps(wrote), secret))
            return 2
        announce("OK script.write drawn snake (grid + body + eyes + food)")
        time.sleep(PAUSE)

        for name in DUPES:
            req, body = call(
                proc, req, "godot.node", "remove", {"scene": SCENE, "node_path": name}
            )
            if body.get("ok") is True:
                announce(f"removed {name}")
            else:
                announce(f"skip {name}")
            time.sleep(0.7)

        req, _ = call(proc, req, "godot.editor", "select", {"scene": SCENE, "node_path": "."})
        req, _ = call(proc, req, "godot.editor", "frame_view", {"scene": SCENE, "node_path": "."})
        req, saved = call(proc, req, "godot.scene", "save", {"path": SCENE})
        if saved.get("ok") is not True:
            announce("save failed " + sess.redact(json.dumps(saved), secret))
            return 2
        announce("DONE. Viewport should show a 16x12 grid, 4-long green snake, red food.")
        announce("F6 to play. This is a demo, not R8 dogfood. G2 not signed.")
        while proc.poll() is None:
            time.sleep(2.0)
        return 0
    finally:
        life.stop_proc(proc)


if __name__ == "__main__":
    raise SystemExit(main())
