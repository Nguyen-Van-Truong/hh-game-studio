#!/usr/bin/env python3
"""Switch the live editor to snake and prove F6-equivalent play.

Sidecar only. Does not launch a second editor. Does not tick G2.
play.start is tried once and reported honestly (still Alternative).
"""

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
WATCH = {"mode": "watch"}
SCHEMA = "hh-godot-variant/1"


def main() -> int:
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
            err_code = str((body.get("error") or {}).get("code", ""))
            print(f"{method} {action} ok={body.get('ok')} err={err_code}", flush=True)
            return body

        call("godot.scene", "open", {"path": SCENE})
        call("godot.editor", "main_screen", {"screen": "2D"})
        call("godot.editor", "select", {"scene": SCENE, "node_path": "."})
        call("godot.editor", "frame_view", {"scene": SCENE, "node_path": "."})
        for prop, val in (
            ("offset_left", 24.0),
            ("offset_top", 12.0),
            ("offset_right", 792.0),
            ("offset_bottom", 48.0),
        ):
            call(
                "godot.property",
                "set",
                {
                    "scene": SCENE,
                    "node_path": "Score",
                    "property": prop,
                    "value": {"schema": SCHEMA, "type": "float", "value": val},
                },
            )
        play = call(
            "godot.play",
            "start",
            {"scene": SCENE, "mode": "play"},
        )
        print("play.start body=" + sess.redact(json.dumps(play), secret)[:400], flush=True)
        call("godot.scene", "save", {"path": SCENE})
        print("EDITOR now on snake.tscn — look at the 2D tab named snake", flush=True)
        time.sleep(8)
        return 0
    finally:
        life.stop_proc(proc)


if __name__ == "__main__":
    raise SystemExit(main())
