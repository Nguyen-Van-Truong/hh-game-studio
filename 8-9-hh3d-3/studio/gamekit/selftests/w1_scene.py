"""W1 selftest: project registry, scene new/apply/inspect/undo, idempotency, rejects, check."""

from __future__ import annotations

from .. import common as C
from .. import scene as S
from . import Ctx

MAIN_TSCN = """[gd_scene format=3 uid="uid://bgkselftest01"]

[node name="Main" type="Node2D"]

[node name="Backdrop" type="ColorRect" parent="."]
offset_right = 320.0
offset_bottom = 180.0
color = Color(0.1, 0.1, 0.2, 1)
"""

PLAYER_GD = """extends CharacterBody2D

@export var speed: float = 120.0
var hits: int = 0


func _on_hit(_body: Node2D) -> void:
	hits += 1
"""

BROKEN_GD = """extends Node

func broken(:
	pass
"""


def _ops_player() -> list[dict]:
    return [
        {"op": "node.create", "parent": ".", "name": "Player", "type": "CharacterBody2D",
         "props": {"position": [100, 50], "collision_layer": [1, 2], "motion_mode": "Floating"}},
        {"op": "node.create", "parent": "Player", "name": "Shape", "type": "CollisionShape2D"},
        {"op": "resource.new", "path": "Player/Shape", "prop": "shape", "type": "RectangleShape2D",
         "props": {"size": [16, 32]}},
        {"op": "script.attach", "path": "Player", "script": "res://player.gd", "props": {"speed": 220.0}},
        {"op": "node.create", "parent": ".", "name": "Hitbox", "type": "Area2D"},
        {"op": "signal.connect", "from": "Hitbox", "signal": "body_entered", "to": "Player", "method": "_on_hit"},
        {"op": "group.add", "path": "Player", "group": "players"},
        {"op": "node.create", "parent": ".", "name": "Deco", "type": "Sprite2D", "props": {"modulate": "#ff8800"}},
        {"op": "node.rename", "path": "Deco", "name": "Decor"},
        {"op": "node.duplicate", "path": "Decor", "name": "Decor2", "props": {"position": [5, 5]}},
        {"op": "node.move", "path": "Decor2", "parent": "Player"},
        {"op": "node.delete", "path": "Decor"},
    ]


def run(ctx: Ctx) -> None:
    project = ctx.project("gk2d", {"main.tscn": MAIN_TSCN, "player.gd": PLAYER_GD}, main_scene="res://main.tscn")
    main_path = project.res_to_path("res://main.tscn")
    original = main_path.read_bytes()

    receipt = ctx.guard("apply player ops", lambda: S.apply(project, "res://main.tscn", _ops_player(), "w1.player.1"))
    if receipt is None:
        return
    ctx.check("apply committed with fresh readback", receipt.get("status") == "COMMITTED"
              and receipt.get("readback") == "FRESH_PROCESS_MATCH", receipt=receipt.get("status"))
    after = main_path.read_bytes()
    ctx.check("uid kept in header", b'uid="uid://bgkselftest01"' in after.split(b"\n", 1)[0])

    view = S.inspect(project, "res://main.tscn")
    nodes = {n["path"]: n for n in view["nodes"]}
    player = nodes.get("Player", {})
    ctx.check("player created with typed props", player.get("type") == "CharacterBody2D"
              and player.get("props", {}).get("position") == [100.0, 50.0]
              and player.get("props", {}).get("collision_layer") == 3
              and player.get("props", {}).get("motion_mode") == 1, player=player.get("props"))
    ctx.check("script attached and exported var set", player.get("props", {}).get("script") == {"$res": "res://player.gd"}
              and player.get("props", {}).get("speed") == 220.0)
    shape = nodes.get("Player/Shape", {}).get("props", {}).get("shape", {})
    ctx.check("sub-resource shape saved", shape.get("$type") == "RectangleShape2D"
              and shape.get("props", {}).get("size") == [16.0, 32.0], shape=shape)
    ctx.check("group saved", "players" in player.get("groups", []))
    ctx.check("signal saved", any(c["signal"] == "body_entered" and c["method"] == "_on_hit" for c in view["connections"]))
    ctx.check("rename/duplicate/move/delete applied", "Player/Decor2" in nodes and "Decor" not in nodes
              and "Deco" not in nodes, paths=sorted(nodes))

    again = S.apply(project, "res://main.tscn", _ops_player(), "w1.player.1")
    ctx.check("same command_id + same ops replays receipt", again.get("replayed") is True
              and again.get("after_sha256") == receipt.get("after_sha256"))
    ctx.check("replay did not rewrite the file", main_path.read_bytes() == after)
    ctx.expect_error("same command_id + different ops is CONFLICT", "CONFLICT", S.apply, project, "res://main.tscn",
                     [{"op": "node.delete", "path": "Hitbox"}], "w1.player.1")

    rejects = [
        ("unknown class rejected on host", "VALIDATION_FAILED",
         [{"op": "node.create", "parent": ".", "name": "X", "type": "EvilNode"}]),
        ("wrong property type rejected", "VALIDATION_FAILED",
         [{"op": "node.update", "path": "Player", "props": {"position": "left"}}]),
        ("unknown property rejected", "VALIDATION_FAILED",
         [{"op": "node.update", "path": "Player", "props": {"flying_speed": 3}}]),
        ("range violation rejected", "VALIDATION_FAILED",
         [{"op": "node.create", "parent": ".", "name": "T", "type": "Timer", "props": {"wait_time": -1.0}}]),
        ("bad enum name rejected", "VALIDATION_FAILED",
         [{"op": "node.update", "path": "Player", "props": {"motion_mode": "Swimming"}}]),
        ("path traversal rejected", "BAD_PATH",
         [{"op": "script.attach", "path": "Player", "script": "res://../evil.gd"}]),
        ("missing parent rejected", "VALIDATION_FAILED",
         [{"op": "node.create", "parent": "Nope", "name": "Y", "type": "Node2D"}]),
        ("duplicate sibling name rejected", "VALIDATION_FAILED",
         [{"op": "node.create", "parent": ".", "name": "Player", "type": "Node2D"}]),
    ]
    for i, (name, code, ops) in enumerate(rejects):
        ctx.expect_error(name, code, S.apply, project, "res://main.tscn", ops, f"w1.reject.{i}")
    ctx.check("rejected commands left the file unchanged", main_path.read_bytes() == after)
    ctx.expect_error("stale expect_sha256 rejected", "STALE", S.apply, project, "res://main.tscn",
                     [{"op": "node.update", "path": "Player", "props": {"speed": 1.0}}], "w1.stale.1",
                     expect_sha256="0" * 64)

    undone = ctx.guard("undo", lambda: S.undo(project, "w1.player.1"))
    ctx.check("undo restores original bytes", undone is not None and main_path.read_bytes() == original)
    again_undo = S.undo(project, "w1.player.1")
    ctx.check("undo is idempotent", again_undo.get("replayed") is True)

    created = ctx.guard("scene new 3D", lambda: S.apply(
        project, "res://world.tscn",
        [{"op": "node.create", "parent": ".", "name": "Box", "type": "MeshInstance3D",
          "props": {"mesh": {"$type": "BoxMesh", "props": {"size": [2, 1, 2]}},
                    "material_override": {"$type": "StandardMaterial3D", "props": {"albedo_color": [0.8, 0.2, 0.1, 1]}}}},
         {"op": "node.create", "parent": ".", "name": "Sun", "type": "DirectionalLight3D",
          "props": {"rotation_degrees": [-45, 30, 0], "shadow_enabled": True}}],
        "w1.world.1", create={"root_type": "Node3D", "root_name": "World", "props": {}}))
    ctx.check("new 3D scene committed", created is not None and created.get("created") is True
              and created.get("node_count") == 3)
    ctx.expect_error("scene new on existing file is CONFLICT", "CONFLICT", S.apply, project, "res://world.tscn", [],
                     "w1.world.2", create={"root_type": "Node3D", "root_name": "World"})

    clean = S.check(project)
    ctx.check("check passes on a clean project", clean.get("clean") is True, problems=clean.get("problems"),
              errors=clean.get("godot_errors"))
    project.res_to_path("res://broken.gd").write_text(BROKEN_GD, encoding="utf-8")
    dirty = S.check(project)
    ctx.check("check reports a broken script", dirty.get("clean") is False
              and any("broken.gd" in str(p) for p in dirty.get("problems", []) + dirty.get("godot_errors", [])))

    other = ctx.project("gk-other", {}, register=False)
    ctx.expect_error("same id registered to another root is CONFLICT", "CONFLICT", C.register_project, other.root, "gk2d")
    ctx.expect_error("forbidden scope path rejected", "FORBIDDEN_PATH", C.register_project,
                     ctx.project("godot/dogfood/kho-bi-an", {}, register=False).root, "kba")
