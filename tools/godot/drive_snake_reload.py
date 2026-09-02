#!/usr/bin/env python3
"""Reload the drawn snake into the already-open plugin-project GUI. Sidecar only."""

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


def main() -> int:
    script = (REPO_ROOT / "godot/plugin-project/snake/snake_game.gd").read_text(encoding="utf-8")
    proc, _desc, secret, err = life.start_sidecar()
    req = 2
    try:
        ok = False
        last: dict = {}
        deadline = time.time() + 90.0
        while time.time() < deadline:
            last = life.body_of(life.mcp_call(proc, req, "hh.plugin_noop", {}))
            req += 1
            if last.get("ok") is True:
                ok = True
                break
            time.sleep(0.4)
        if not ok:
            print("no plugin hello — Project -> Reload Current Project", flush=True)
            print(sess.redact(json.dumps(last), secret), flush=True)
            print("".join(err)[-400:], flush=True)
            return 2
        print("CONNECTED", flush=True)

        def call(method: str, action: str, params: dict, timeout: float = 40.0) -> dict:
            nonlocal req
            body = life.body_of(
                life.mcp_call(
                    proc,
                    req,
                    method,
                    {
                        "action": action,
                        "params": params,
                        "command_id": life.new_ulid(),
                        "presentation": WATCH,
                    },
                    timeout,
                )
            )
            req += 1
            print(action, "ok=" + str(body.get("ok")), flush=True)
            return body

        call("godot.scene", "open", {"path": SCENE})
        wrote = call("godot.script", "write", {"path": SCRIPT, "contents": script})
        if wrote.get("ok") is not True:
            print("script.write failed", sess.redact(json.dumps(wrote), secret), flush=True)
            return 2
        call("godot.editor", "main_screen", {"screen": "2D"})
        call("godot.editor", "select", {"scene": SCENE, "node_path": "."})
        call("godot.editor", "frame_view", {"scene": SCENE, "node_path": "."})
        call("godot.scene", "save", {"path": SCENE})
        print("DONE — zoom ~100 percent, then F6 to play", flush=True)
        time.sleep(20)
        return 0
    finally:
        life.stop_proc(proc)


if __name__ == "__main__":
    raise SystemExit(main())
