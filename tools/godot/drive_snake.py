#!/usr/bin/env python3
"""Watch-mode snake demo on the already-open plugin-project Godot GUI.

Starts sidecar only. Does NOT launch a second Godot. Does NOT tick G2.
play.start stays Alternative -- human presses F6 on snake.tscn.
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
SCRIPT = "res://snake/snake_game.gd"
POLISH_MARK = "@tool"
SCHEMA = "hh-godot-variant/1"
WATCH = {"mode": "watch"}
PAUSE_S = 2.8

SCRIPT_TEXT = """extends Node2D

const CELL: int = 32
const COLS: int = 16
const ROWS: int = 12

var _dir: Vector2i = Vector2i(1, 0)
var _pending: Vector2i = Vector2i(1, 0)
var _body: Array[Vector2i] = [Vector2i(4, 6), Vector2i(3, 6), Vector2i(2, 6)]
var _food: Vector2i = Vector2i(10, 6)
var _accum: float = 0.0
var _step: float = 0.16
var _alive: bool = true
var _score: int = 0


func _ready() -> void:
	_paint()


func _process(delta: float) -> void:
	if not _alive:
		return
	if Input.is_key_pressed(KEY_UP) and _dir.y == 0:
		_pending = Vector2i(0, -1)
	elif Input.is_key_pressed(KEY_DOWN) and _dir.y == 0:
		_pending = Vector2i(0, 1)
	elif Input.is_key_pressed(KEY_LEFT) and _dir.x == 0:
		_pending = Vector2i(-1, 0)
	elif Input.is_key_pressed(KEY_RIGHT) and _dir.x == 0:
		_pending = Vector2i(1, 0)
	_accum += delta
	if _accum < _step:
		return
	_accum = 0.0
	_dir = _pending
	var head: Vector2i = _body[0] + _dir
	if head.x < 0 or head.y < 0 or head.x >= COLS or head.y >= ROWS or _body.has(head):
		_alive = false
		_set_score_text("Game over  %d  (F6 replay)" % _score)
		return
	_body.insert(0, head)
	if head == _food:
		_score += 1
		_food = _spawn_food()
	else:
		_body.pop_back()
	_paint()


func _spawn_food() -> Vector2i:
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var tries: int = 0
	while tries < 128:
		var cell := Vector2i(rng.randi_range(0, COLS - 1), rng.randi_range(0, ROWS - 1))
		if not _body.has(cell):
			return cell
		tries += 1
	return Vector2i(1, 1)


func _paint() -> void:
	_place("Head", _body[0], Color(0.2, 0.9, 0.3, 1.0))
	_place("Food", _food, Color(0.95, 0.2, 0.2, 1.0))
	_set_score_text("Score %d   arrows to steer" % _score)


func _place(name_s: String, cell: Vector2i, tint: Color) -> void:
	var node: Node = get_node_or_null(name_s)
	if node is ColorRect:
		var box: ColorRect = node
		box.position = Vector2(float(cell.x * CELL), float(cell.y * CELL))
		box.size = Vector2(float(CELL - 2), float(CELL - 2))
		box.color = tint


func _set_score_text(text: String) -> void:
	var label: Node = get_node_or_null("Score")
	if label is Label:
		(label as Label).text = text
"""


def variant(typ: str, value: object) -> dict:
    return {"schema": SCHEMA, "type": typ, "value": value}


def announce(msg: str) -> None:
    print(f"[snake] {msg}", flush=True)


def wait_live_hello(proc, req_id: int, timeout: float = 90.0):
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        if proc.poll() is not None:
            return req_id, False, {"error": {"message": "sidecar exited"}}
        last = life.body_of(life.mcp_call(proc, req_id, "hh.plugin_noop", {}))
        req_id += 1
        if last.get("ok") is True:
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
        announce(f"OK  {label}")
        return
    raise RuntimeError(f"{label} failed: {sess.redact(json.dumps(body), secret)}")


def step_pause(label: str) -> None:
    announce(f"watch: {label}")
    time.sleep(PAUSE_S)


def set_prop(proc, req_id, secret, node_path: str, prop: str, typ: str, value, label: str):
    req_id, _, body = call(
        proc,
        req_id,
        "godot.property",
        "set",
        {
            "scene": SCENE,
            "node_path": node_path,
            "property": prop,
            "value": variant(typ, value),
        },
    )
    must_ok(body, label, secret)
    return req_id


def add_node(proc, req_id, secret, class_name: str, name: str, parent: str = "."):
    req_id, _, body = call(
        proc,
        req_id,
        "godot.node",
        "add",
        {"scene": SCENE, "parent": parent, "class_name": class_name, "name": name},
    )
    if (body.get("error") or {}).get("code") == "E_CONFLICT":
        announce(f"skip add {name} (exists)")
        return req_id
    must_ok(body, f"node.add {name}", secret)
    req_id, _, _ = call(
        proc, req_id, "godot.editor", "select", {"scene": SCENE, "node_path": name}
    )
    req_id, _, _ = call(
        proc, req_id, "godot.editor", "frame_view", {"scene": SCENE, "node_path": name}
    )
    return req_id


def main() -> int:
    existing = (REPO_ROOT / "godot/plugin-project/snake/snake_game.gd").read_text(encoding="utf-8")
    if POLISH_MARK in existing:
        announce("refusing: drawn @tool snake already on disk")
        announce("re-running this script would add Board/Head ColorRects and wipe the polish")
        announce("use tools/godot/drive_snake_polish.py to reload the drawn script")
        return 3
    announce("Watch the Godot window. Each step waits so the dock + viewport update.")
    announce("play.start is still Alternative -- after DONE press F6 on snake.tscn")
    proc, _desc, secret, err_lines = life.start_sidecar()
    req_id = 2
    try:
        req_id, hello, last = wait_live_hello(proc, req_id)
        if not hello:
            announce("plugin did not hello. Keep Godot open; Project -> Reload Current Project")
            announce(sess.redact(json.dumps(last), secret))
            announce("".join(err_lines)[-600:])
            return 2
        announce("CONNECTED -- look at HH Agent Activity + 2D view")

        req_id, _, created = call(
            proc, req_id, "godot.scene", "create", {"path": SCENE, "root_class": "Node2D"}
        )
        if (created.get("error") or {}).get("code") == "E_CONFLICT":
            req_id, _, created = call(proc, req_id, "godot.scene", "open", {"path": SCENE})
            must_ok(created, "scene.open snake", secret)
        else:
            must_ok(created, "scene.create snake", secret)
        req_id, _, _ = call(proc, req_id, "godot.editor", "main_screen", {"screen": "2D"})
        step_pause("scene snake.tscn open")

        req_id = add_node(proc, req_id, secret, "ColorRect", "Board")
        # Control.size/position are editor-only; persist via offsets.
        req_id = set_prop(proc, req_id, secret, "Board", "offset_right", "float", 512, "Board.offset_right")
        req_id = set_prop(proc, req_id, secret, "Board", "offset_bottom", "float", 384, "Board.offset_bottom")
        req_id = set_prop(
            proc,
            req_id,
            secret,
            "Board",
            "color",
            "Color",
            {"r": 0.08, "g": 0.1, "b": 0.14, "a": 1},
            "Board.color",
        )
        step_pause("dark board 512x384")

        req_id = add_node(proc, req_id, secret, "ColorRect", "Head")
        req_id = set_prop(proc, req_id, secret, "Head", "offset_left", "float", 128, "Head.offset_left")
        req_id = set_prop(proc, req_id, secret, "Head", "offset_top", "float", 192, "Head.offset_top")
        req_id = set_prop(proc, req_id, secret, "Head", "offset_right", "float", 158, "Head.offset_right")
        req_id = set_prop(proc, req_id, secret, "Head", "offset_bottom", "float", 222, "Head.offset_bottom")
        req_id = set_prop(
            proc,
            req_id,
            secret,
            "Head",
            "color",
            "Color",
            {"r": 0.2, "g": 0.9, "b": 0.3, "a": 1},
            "Head.color green",
        )
        step_pause("green snake head")

        req_id = add_node(proc, req_id, secret, "ColorRect", "Food")
        req_id = set_prop(proc, req_id, secret, "Food", "offset_left", "float", 320, "Food.offset_left")
        req_id = set_prop(proc, req_id, secret, "Food", "offset_top", "float", 192, "Food.offset_top")
        req_id = set_prop(proc, req_id, secret, "Food", "offset_right", "float", 350, "Food.offset_right")
        req_id = set_prop(proc, req_id, secret, "Food", "offset_bottom", "float", 222, "Food.offset_bottom")
        req_id = set_prop(
            proc,
            req_id,
            secret,
            "Food",
            "color",
            "Color",
            {"r": 0.95, "g": 0.2, "b": 0.2, "a": 1},
            "Food.color red",
        )
        step_pause("red food")

        req_id = add_node(proc, req_id, secret, "Label", "Score")
        req_id = set_prop(proc, req_id, secret, "Score", "offset_left", "float", 8, "Score.offset_left")
        req_id = set_prop(proc, req_id, secret, "Score", "offset_top", "float", 388, "Score.offset_top")
        req_id = set_prop(proc, req_id, secret, "Score", "offset_right", "float", 400, "Score.offset_right")
        req_id = set_prop(proc, req_id, secret, "Score", "offset_bottom", "float", 420, "Score.offset_bottom")
        # Label.text via property.set is flaky on the sidecar type enum; script sets it.
        step_pause("score label")

        req_id, _, wrote = call(
            proc, req_id, "godot.script", "write", {"path": SCRIPT, "contents": SCRIPT_TEXT}
        )
        must_ok(wrote, "script.write snake_game.gd", secret)
        step_pause("script written")

        req_id, _, attached = call(
            proc,
            req_id,
            "godot.script",
            "attach",
            {"scene": SCENE, "node_path": ".", "path": SCRIPT},
        )
        must_ok(attached, "script.attach root", secret)
        req_id, _, saved = call(proc, req_id, "godot.scene", "save", {"path": SCENE})
        must_ok(saved, "scene.save", secret)
        req_id, _, _ = call(
            proc, req_id, "godot.editor", "select", {"scene": SCENE, "node_path": "Head"}
        )
        req_id, _, _ = call(
            proc, req_id, "godot.editor", "frame_view", {"scene": SCENE, "node_path": "Board"}
        )

        announce("DONE. Timeline should show Board / Head / Food / Score / script.")
        announce("To play: click snake.tscn in FileSystem, then F6 (Play Scene).")
        announce("Arrows steer. play.start is Alternative (R6), not paper-ACK.")
        announce("Sidecar stays up. Ctrl+C to stop.")
        while proc.poll() is None:
            time.sleep(2.0)
        return 0
    finally:
        life.stop_proc(proc)


if __name__ == "__main__":
    raise SystemExit(main())
