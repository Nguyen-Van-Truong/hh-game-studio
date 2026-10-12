"""W2 selftest: build a small 2D arena with the 2D catalog and ops, read it back, run it 60 frames."""

from __future__ import annotations

from .. import common as C
from .. import scene as S
from . import Ctx, make_png

PALETTE = [(90, 160, 70, 255), (120, 90, 60, 255), (150, 150, 160, 255), (200, 180, 60, 255)]
SHADER = (
    "shader_type canvas_item;\n"
    "uniform vec4 tint : source_color = vec4(1.0, 0.8, 0.4, 1.0);\n"
    "void fragment() { COLOR = texture(TEXTURE, UV) * tint; }\n"
)


def _tiles(x: int, y: int) -> tuple[int, int, int, int]:
    base = PALETTE[x // 16]
    edge = x % 16 in (0, 15) or y in (0, 15)
    return tuple(max(0, c - 40) if edge and i < 3 else c for i, c in enumerate(base))  # type: ignore[return-value]


def _hero(x: int, y: int) -> tuple[int, int, int, int]:
    frame = (y // 16) * 4 + x // 16
    lx, ly = x % 16, y % 16
    inside = 4 <= lx <= 11 and 2 + (frame % 2) <= ly <= 15
    return (40 + frame * 25, 80, 200, 255) if inside else (0, 0, 0, 0)


def arena_ops() -> list[dict]:
    rect = lambda w, h: {"$type": "RectangleShape2D", "props": {"size": [w, h]}}  # noqa: E731
    return [
        {"op": "node.create", "parent": ".", "name": "Ground", "type": "TileMapLayer"},
        {"op": "tileset.from_atlas", "path": "Ground", "texture": "res://art/tiles.png", "tile_size": [16, 16],
         "collision": "all"},
        {"op": "tilemap.fill_rect", "path": "Ground", "rect": [0, 10, 30, 1], "atlas": [0, 0]},
        {"op": "tilemap.set_cells", "path": "Ground", "cells": [[5, 7, 0, 1, 0], [6, 7, 0, 1, 0], [7, 7, 0, 2, 0]]},
        {"op": "node.create", "parent": ".", "name": "Player", "type": "CharacterBody2D",
         "props": {"position": [80, 120], "collision_mask": [1]}},
        {"op": "node.create", "parent": "Player", "name": "Shape", "type": "CollisionShape2D",
         "props": {"shape": {"$type": "CapsuleShape2D", "props": {"radius": 6.0, "height": 20.0}}}},
        {"op": "node.create", "parent": "Player", "name": "Sprite", "type": "AnimatedSprite2D"},
        {"op": "spriteframes.from_sheet", "path": "Player/Sprite", "texture": "res://art/hero.png",
         "hframes": 4, "vframes": 2, "autoplay": "idle",
         "animations": {"idle": {"frames": [0, 1], "fps": 4, "loop": True},
                        "run": {"frames": [4, 5, 6, 7], "fps": 10, "loop": True}}},
        {"op": "node.create", "parent": "Player", "name": "Cam", "type": "Camera2D",
         "props": {"zoom": [2, 2], "position_smoothing_enabled": True, "limit_left": 0, "limit_bottom": 200}},
        {"op": "node.create", "parent": "Player", "name": "Agent", "type": "NavigationAgent2D",
         "props": {"path_desired_distance": 6.0}},
        {"op": "node.create", "parent": ".", "name": "Crate", "type": "RigidBody2D",
         "props": {"position": [200, 60], "mass": 2.0,
                   "physics_material_override": {"$type": "PhysicsMaterial", "props": {"bounce": 0.2, "friction": 0.6}}}},
        {"op": "node.create", "parent": "Crate", "name": "Shape", "type": "CollisionShape2D", "props": {"shape": rect(16, 16)}},
        {"op": "node.create", "parent": ".", "name": "Anchor", "type": "StaticBody2D", "props": {"position": [200, 20]}},
        {"op": "node.create", "parent": ".", "name": "Hinge", "type": "PinJoint2D",
         "props": {"position": [200, 20], "node_a": "../Anchor", "node_b": "../Crate"}},
        {"op": "node.create", "parent": ".", "name": "Dark", "type": "CanvasModulate", "props": {"color": [0.55, 0.55, 0.7, 1]}},
        {"op": "node.create", "parent": ".", "name": "Torch", "type": "PointLight2D",
         "props": {"position": [120, 100], "energy": 1.2, "color": "#ffcc88",
                   "texture": {"$type": "GradientTexture2D", "props": {
                       "width": 128, "height": 128, "fill": "Radial", "fill_from": [0.5, 0.5], "fill_to": [1.0, 0.5],
                       "gradient": {"$type": "Gradient", "props": {"offsets": [0.0, 1.0],
                                                                   "colors": [[1, 1, 1, 1], [1, 1, 1, 0]]}}}}}},
        {"op": "node.create", "parent": ".", "name": "Sparks", "type": "GPUParticles2D",
         "props": {"position": [120, 96], "amount": 32, "lifetime": 1.0,
                   "process_material": {"$type": "ParticleProcessMaterial", "props": {
                       "direction": [0, -1, 0], "spread": 30.0, "initial_velocity_min": 40.0,
                       "initial_velocity_max": 80.0, "gravity": [0, 98, 0]}}}},
        {"op": "node.create", "parent": ".", "name": "Glow", "type": "Sprite2D",
         "props": {"position": [40, 40], "texture": {"$res": "res://art/tiles.png"},
                   "material": {"$type": "ShaderMaterial", "props": {
                       "shader": {"$type": "Shader", "props": {"code": SHADER}}}}}},
        {"op": "node.create", "parent": ".", "name": "Far", "type": "Parallax2D",
         "props": {"scroll_scale": [0.3, 1.0], "repeat_size": [320, 0]}},
        {"op": "node.create", "parent": "Far", "name": "Hills", "type": "Sprite2D",
         "props": {"texture": {"$res": "res://art/tiles.png"}, "scale": [4, 2], "z_index": -10}},
        {"op": "node.create", "parent": ".", "name": "Route", "type": "Path2D",
         "props": {"curve": {"$type": "Curve2D", "props": {
             "point_count": 3, "point_0/position": [0, 0], "point_1/position": [100, -40], "point_2/position": [200, 0]}}}},
        {"op": "node.create", "parent": "Route", "name": "Walker", "type": "PathFollow2D", "props": {"loop": True}},
        {"op": "node.create", "parent": ".", "name": "Nav", "type": "NavigationRegion2D",
         "props": {"navigation_polygon": {"$type": "NavigationPolygon", "props": {"agent_radius": 6.0}}}},
        {"op": "node.create", "parent": ".", "name": "Pickup", "type": "Area2D", "props": {"position": [260, 140]}},
        {"op": "node.create", "parent": "Pickup", "name": "Shape", "type": "CollisionShape2D",
         "props": {"shape": {"$type": "CircleShape2D", "props": {"radius": 8.0}}}},
        {"op": "group.add", "path": "Pickup", "group": "pickups"},
        {"op": "node.create", "parent": ".", "name": "Sfx", "type": "AudioStreamPlayer2D", "props": {"volume_db": -6.0}},
        {"op": "node.create", "parent": ".", "name": "HUD", "type": "CanvasLayer"},
        {"op": "node.create", "parent": "HUD", "name": "Score", "type": "Label",
         "props": {"text": "Score: 0", "position": [8, 8]}},
        {"op": "node.create", "parent": "HUD", "name": "HP", "type": "ProgressBar",
         "props": {"value": 75.0, "position": [8, 30], "size": [100, 28], "show_percentage": False}},
        {"op": "node.create", "parent": ".", "name": "Anim", "type": "AnimationPlayer"},
        {"op": "animation.create", "player": "Anim", "name": "torch_flicker", "length": 1.0, "loop": "linear",
         "autoplay": True, "tracks": [
             {"path": "Torch:energy", "keys": [[0.0, 1.0], [0.5, 1.6], [1.0, 1.0]]},
             {"path": "Torch:color", "keys": [[0.0, "#ffcc88"], [0.5, "#ffaa66"], [1.0, "#ffcc88"]]},
             {"path": "Route/Walker:progress_ratio", "keys": [[0.0, 0.0], [1.0, 1.0]]}]},
    ]


def run(ctx: Ctx) -> None:
    project = ctx.project("gk-arena", {
        "art/tiles.png": make_png(64, 16, _tiles),
        "art/hero.png": make_png(64, 32, _hero),
    }, main_scene="res://arena.tscn")

    cat = ctx.guard("catalog check", lambda: S.catalog_check(project))
    ctx.check("all catalog classes exist in Godot 4.7.2", bool(cat and cat.get("ok")),
              missing=(cat or {}).get("missing"), wrong=(cat or {}).get("wrong_kind"))

    receipt = ctx.guard("build arena", lambda: S.apply(
        project, "res://arena.tscn", arena_ops(), "w2.arena.1",
        create={"root_type": "Node2D", "root_name": "Arena", "props": {}}))
    if receipt is None:
        return
    ctx.check("arena committed with fresh readback", receipt.get("readback") == "FRESH_PROCESS_MATCH",
              nodes=receipt.get("node_count"))

    view = S.inspect(project, "res://arena.tscn")
    nodes = {n["path"]: n for n in view["nodes"]}
    props = lambda p: nodes.get(p, {}).get("props", {})  # noqa: E731
    ground = props("Ground")
    ctx.check("tileset with collision saved", ground.get("tile_set", {}).get("$type") == "TileSet", keys=sorted(ground))
    ctx.check("tile cells saved", isinstance(ground.get("tile_map_data"), dict) and ground["tile_map_data"].get("$len", 0) > 0)
    frames = props("Player/Sprite").get("sprite_frames", {})
    ctx.check("sprite frames from sheet", frames.get("$type") == "SpriteFrames" and props("Player/Sprite").get("autoplay") == "idle")
    ctx.check("joint node paths", props("Hinge").get("node_a") == "../Anchor" and props("Hinge").get("node_b") == "../Crate")
    ctx.check("rigid body with physics material", props("Crate").get("mass") == 2.0
              and props("Crate").get("physics_material_override", {}).get("$type") == "PhysicsMaterial")
    ctx.check("light with gradient texture", props("Torch").get("texture", {}).get("$type") == "GradientTexture2D")
    ctx.check("particles with process material", props("Sparks").get("process_material", {}).get("$type") == "ParticleProcessMaterial")
    shader = props("Glow").get("material", {}).get("props", {}).get("shader", {})
    ctx.check("canvas shader saved", shader.get("$type") == "Shader" and "fragment" in str(shader.get("props", {}).get("code")))
    curve = props("Route").get("curve", {})
    ctx.check("path curve with 3 points", curve.get("$type") == "Curve2D", curve=curve)
    libs = [v for k, v in props("Anim").items() if k.startswith("libraries/")]
    ctx.check("animation library saved", any(isinstance(v, dict) and v.get("$type") == "AnimationLibrary" for v in libs)
              and props("Anim").get("autoplay") == "torch_flicker", keys=sorted(props("Anim")))
    ctx.check("HUD and pickup group", "HUD/Score" in nodes and "pickups" in nodes.get("Pickup", {}).get("groups", []))

    before = C.sha256_file(project.res_to_path("res://arena.tscn"))
    bad_ops = {
        "missing method": [{"op": "animation.create", "player": "Anim", "name": "bad", "tracks": [
            {"type": "method", "path": "Torch", "keys": [[0.1, {"method": "nope", "args": []}]]}]}],
        "frames not a list": [{"op": "spriteframes.from_sheet", "path": "Player/Sprite", "texture": "res://art/hero.png",
                               "hframes": 4, "vframes": 2, "animations": {"idle": {"frames": "0,1"}}}],
    }
    for label, ops in bad_ops.items():
        err = ctx.expect_error(f"rejects {label}", "VALIDATION_FAILED",
                               lambda ops=ops, label=label: S.apply(project, "res://arena.tscn", ops, f"w2.bad.{len(label)}"))
        ctx.check(f"{label}: scene bytes unchanged", C.sha256_file(project.res_to_path("res://arena.tscn")) == before,
                  detail=err.detail[:200] if err else None)

    run = C.run_godot(project.root, None, (), headless=True, timeout=90, extra=("--quit-after", "60"))
    ctx.check("arena runs 60 frames without errors", run.exit_code == 0 and not run.errors,
              exit_code=run.exit_code, errors=run.errors[:8])
    clean = S.check(project)
    ctx.check("project check clean", clean.get("clean") is True, problems=clean.get("problems"),
              errors=clean.get("godot_errors"))
