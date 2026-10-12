"""W4 selftest: InputMap readback, 60 Hz trace, replay, and gray-box stuck/coverage."""

from __future__ import annotations

from .. import bot as B
from .. import inputmap as IM
from .. import play as P
from . import Ctx

PLAYER_GD = """extends CharacterBody2D

const SPEED: float = 200.0


func _physics_process(_delta: float) -> void:
	var axis: float = Input.get_axis("move_left", "move_right")
	velocity = Vector2(axis * SPEED, 0.0)
	move_and_slide()
"""

BOOM_GD = """extends Node2D

var tick: int = 0


func _physics_process(_delta: float) -> void:
	tick += 1
	if tick == 30:
		var missing: Node = null
		missing.queue_free()
"""

MAIN_TSCN = """[gd_scene load_steps=4 format=3 uid="uid://w4main0000001"]

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(16, 16)

[sub_resource type="RectangleShape2D" id="wall_shape"]
size = Vector2(400, 32)

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
motion_mode = 1
script = ExtResource("1_player")

[node name="Shape" type="CollisionShape2D" parent="Player"]
shape = SubResource("player_shape")

[node name="Wall" type="StaticBody2D" parent="."]
position = Vector2(0, 400)

[node name="Shape" type="CollisionShape2D" parent="Wall"]
shape = SubResource("wall_shape")
"""

BOX_TSCN = """[gd_scene load_steps=5 format=3 uid="uid://w4box00000001"]

[ext_resource type="Script" path="res://player.gd" id="1_player"]

[sub_resource type="RectangleShape2D" id="player_shape"]
size = Vector2(16, 16)

[sub_resource type="RectangleShape2D" id="wall_v"]
size = Vector2(20, 80)

[sub_resource type="RectangleShape2D" id="wall_h"]
size = Vector2(80, 20)

[node name="Box" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
motion_mode = 1
position = Vector2(20, 20)
script = ExtResource("1_player")

[node name="Shape" type="CollisionShape2D" parent="Player"]
shape = SubResource("player_shape")

[node name="Walls" type="StaticBody2D" parent="."]

[node name="Left" type="CollisionShape2D" parent="Walls"]
position = Vector2(-10, 20)
shape = SubResource("wall_v")

[node name="Right" type="CollisionShape2D" parent="Walls"]
position = Vector2(50, 20)
shape = SubResource("wall_v")

[node name="Top" type="CollisionShape2D" parent="Walls"]
position = Vector2(20, -10)
shape = SubResource("wall_h")

[node name="Bottom" type="CollisionShape2D" parent="Walls"]
position = Vector2(20, 50)
shape = SubResource("wall_h")
"""

BOOM_TSCN = """[gd_scene load_steps=2 format=3 uid="uid://w4boom0000001"]

[ext_resource type="Script" path="res://boom.gd" id="1_boom"]

[node name="Boom" type="Node2D"]
script = ExtResource("1_boom")
"""

ACTIONS = {
    "move_left": {"deadzone": 0.5, "events": [{"key": "A"}, {"joy_button": 0}]},
    "move_right": {"deadzone": 0.5, "events": [{"physical_key": "D"}, {"joy_axis": 0, "value": -1.0}, {"mouse_button": 1}]},
    "jump": {"deadzone": 0.5, "events": [{"key": "Space"}]},
}

HOLD_RIGHT = {
    "fps": 60,
    "events": [
        {"frame": 0, "action": "move_right", "pressed": True, "strength": 1.0},
        {"frame": 60, "action": "move_right", "pressed": False, "strength": 1.0},
    ],
}


def _at(observations: list, frame: int, label: str):
    for row in observations:
        if row.get("frame") == frame:
            return (row.get("values") or {}).get(label)
    return None


def run(ctx: Ctx) -> None:
    project = ctx.project(
        "w4arena",
        {
            "player.gd": PLAYER_GD,
            "boom.gd": BOOM_GD,
            "main.tscn": MAIN_TSCN,
            "box.tscn": BOX_TSCN,
            "boom.tscn": BOOM_TSCN,
        },
        main_scene="res://main.tscn",
    )
    godot_file = project.res_to_path("res://project.godot")
    receipt = ctx.guard("input set", lambda: IM.set_actions(project, ACTIONS, "w4.input.1"))
    if not isinstance(receipt, dict):
        return
    names = {item["name"] for item in receipt.get("actions", [])}
    ctx.check(
        "input set fresh readback lists the actions",
        receipt.get("status") == "COMMITTED" and receipt.get("readback") == "FRESH_PROCESS_MATCH"
        and {"move_left", "move_right", "jump"} <= names,
        names=sorted(names),
    )
    by_name = {item["name"]: item for item in receipt.get("actions", [])}
    ctx.check(
        "readback events match the request",
        by_name.get("move_left", {}).get("events") == [{"key": "A"}, {"joy_button": 0}]
        and by_name.get("move_right", {}).get("events") == [{"physical_key": "D"}, {"joy_axis": 0, "value": -1.0}, {"mouse_button": 1}]
        and by_name.get("jump", {}).get("events") == [{"key": "Space"}],
        left=by_name.get("move_left"),
        right=by_name.get("move_right"),
    )
    listed = ctx.guard("input list", lambda: IM.list_actions(project))
    if isinstance(listed, dict):
        listed_names = {item["name"] for item in listed.get("actions", [])}
        ctx.check("list hides built-in ui actions", listed_names == {"move_left", "move_right", "jump"}
                  and not any(name.startswith("ui_") for name in listed_names), names=sorted(listed_names))
    committed = godot_file.read_bytes()
    again = IM.set_actions(project, ACTIONS, "w4.input.1")
    ctx.check("same command_id + same actions replays", again.get("replayed") is True
              and again.get("after_sha256") == receipt.get("after_sha256"))
    ctx.check("replay did not rewrite project.godot", godot_file.read_bytes() == committed)
    other = {
        "move_left": ACTIONS["move_left"],
        "move_right": ACTIONS["move_right"],
        "jump": {"deadzone": 0.2, "events": [{"key": "Space"}]},
    }
    ctx.expect_error("same command_id + different actions is CONFLICT", "CONFLICT", IM.set_actions, project, other, "w4.input.1")
    ctx.check("conflict left project.godot unchanged", godot_file.read_bytes() == committed)

    played = ctx.guard("play hold right", lambda: P.play(
        project, scene="res://main.tscn", trace=HOLD_RIGHT, frames=60, seed=1, observe="Player:position", every=60))
    if not isinstance(played, dict):
        return
    start = _at(played.get("observations", []), 0, "Player:position")
    end = _at(played.get("observations", []), 60, "Player:position")
    moved = None if not (isinstance(start, list) and isinstance(end, list)) else end[0] - start[0]
    ctx.check(
        "60 frames of move_right moves about +200 px",
        played.get("ok") is True and moved is not None and abs(moved - 200.0) <= 10.0 and abs(end[1] - start[1]) < 1.0,
        moved=moved, start=start, end=end, errors=played.get("errors"), warnings=(played.get("process") or {}).get("warnings"),
    )
    again_play = P.play(project, scene="res://main.tscn", trace=HOLD_RIGHT, frames=60, seed=1, observe="Player:position", every=60)
    ctx.check(
        "same trace twice has the same trace_hash",
        again_play.get("ok") is True and again_play.get("trace_hash") == played.get("trace_hash")
        and isinstance(played.get("trace_hash"), str) and len(played.get("trace_hash")) == 64,
        first=played.get("trace_hash"), second=again_play.get("trace_hash"),
    )
    ctx.check("play left project.godot untouched", godot_file.read_bytes() == committed)

    boxed = ctx.guard("bot in box", lambda: B.run_bot(
        project, scene="res://box.tscn", frames=100, seed=2, actions="move_left,move_right", track="Player",
        hold_min=36, hold_max=60, stuck_frames=20, stuck_dist=4, cell=32))
    if isinstance(boxed, dict):
        ctx.check(
            "enclosed box reports a stuck interval",
            boxed.get("ok") is True and boxed.get("crashed") is False and len(boxed.get("stuck") or []) >= 1,
            stuck=boxed.get("stuck"), errors=boxed.get("errors"), coverage=boxed.get("coverage"), bbox=boxed.get("bbox"),
        )
    opened = ctx.guard("bot in open area", lambda: B.run_bot(
        project, scene="res://main.tscn", frames=300, seed=1, actions="move_left,move_right", track="Player",
        hold_min=10, hold_max=25, stuck_frames=20, stuck_dist=4, cell=32))
    if isinstance(opened, dict):
        ctx.check(
            "open area covers at least 3 cells",
            opened.get("ok") is True and opened.get("coverage", 0) >= 3 and opened.get("bbox") is not None,
            coverage=opened.get("coverage"), bbox=opened.get("bbox"), errors=opened.get("errors"), stuck=len(opened.get("stuck") or []),
        )
        ctx.check("bot trace is replayable", opened.get("trace", {}).get("fps") == 60 and opened.get("trace", {}).get("events"))

    boom = ctx.guard("play script error", lambda: P.play(project, scene="res://boom.tscn", frames=40, seed=1))
    if isinstance(boom, dict):
        blob = " ".join(boom.get("errors") or [])
        ctx.check(
            "script error at frame 30 is ok false",
            boom.get("ok") is False and boom.get("crashed") is False and "queue_free" in blob.lower(),
            errors=boom.get("errors"),
        )
    ctx.check("runs left project.godot untouched", godot_file.read_bytes() == committed)

    ctx.expect_error(
        "unknown key is rejected",
        "VALIDATION_FAILED",
        IM.set_actions,
        project,
        {"move_left": {"deadzone": 0.5, "events": [{"key": "NotARealKey"}]}},
        "w4.badkey.1",
    )
    ctx.check("unknown key left project.godot unchanged", godot_file.read_bytes() == committed)

    replaced = ctx.guard("input replace", lambda: IM.set_actions(
        project,
        {"move_left": ACTIONS["move_left"], "move_right": ACTIONS["move_right"]},
        "w4.replace.1",
        replace=True,
    ))
    if isinstance(replaced, dict):
        replaced_names = {item["name"] for item in replaced.get("actions", [])}
        ctx.check("replace drops unlisted non-ui actions", replaced.get("ok") is True and replaced_names == {"move_left", "move_right"},
                  names=sorted(replaced_names))
    listed_all = ctx.guard("input list --all", lambda: IM.list_actions(project, include_all=True))
    if isinstance(listed_all, dict):
        all_names = {item["name"] for item in listed_all.get("actions", [])}
        ctx.check("built-in ui actions remain after replace", "ui_accept" in all_names and "jump" not in all_names)

    _check_settings_kept(ctx)


KEPT_SETTINGS = (
    '[autoload]\n\nHHState="*res://state.gd"\n\n'
    "[display]\n\nwindow/size/viewport_width=320\nwindow/size/viewport_height=180\n\n"
    '[hh_game]\n\ncustom/difficulty=3\ncustom/title="Arena"\n'
)


def _check_settings_kept(ctx: Ctx) -> None:
    """input set rewrites project.godot through Godot; every other game setting must survive."""
    project = ctx.project("w4settings", {"state.gd": "extends Node\n", "main.tscn": MAIN_TSCN, "player.gd": PLAYER_GD},
                         main_scene="res://main.tscn", settings=KEPT_SETTINGS)
    godot_file = project.res_to_path("res://project.godot")
    original = [line for line in godot_file.read_text(encoding="utf-8").splitlines()
                if "=" in line and not line.startswith(("config_version", "config/features", ";"))]
    receipt = ctx.guard("input set on a project with autoload/display/custom settings",
                        lambda: IM.set_actions(project, {"jump": {"deadzone": 0.5, "events": [{"key": "Space"}]}},
                                               "w4.kept.1"))
    if not isinstance(receipt, dict):
        return
    after = godot_file.read_text(encoding="utf-8").splitlines()
    lost = [line for line in original if line not in after]
    ctx.check("input set keeps every other project setting", receipt.get("status") == "COMMITTED" and not lost,
              lost=lost)
