"""W3 selftest: build a small 3D room with the 3D catalog and ops, read it back, run it 60 frames."""

from __future__ import annotations

from .. import common as C
from .. import scene as S
from . import Ctx

ORB_SHADER = (
    "shader_type spatial;\n"
    "uniform vec3 tint : source_color = vec3(0.2, 0.8, 1.0);\n"
    "void fragment() { ALBEDO = tint; EMISSION = tint * 0.5; }\n"
)
TRIGGER_GD = (
    "extends Area3D\n\n"
    "var hits: int = 0\n\n\n"
    "func _on_body_entered(_body: Node3D) -> void:\n"
    "\thits += 1\n\n\n"
    "func ping() -> void:\n"
    "\thits += 1\n"
)


def _mat(color: str, **extra: object) -> dict:
    return {"$type": "StandardMaterial3D", "props": {"albedo_color": color, **extra}}


def room_ops() -> list[dict]:
    return [
        {"op": "node.create", "parent": ".", "name": "Env", "type": "WorldEnvironment",
         "props": {"environment": {"$type": "Environment", "props": {
             "background_mode": "Sky",
             "sky": {"$type": "Sky", "props": {"sky_material": {"$type": "ProceduralSkyMaterial", "props": {
                 "sky_top_color": "#3a5f9e", "ground_bottom_color": "#2b2b2b"}}}},
             "ambient_light_source": "Sky", "tonemap_mode": "ACES", "glow_enabled": True,
             "fog_enabled": True, "fog_density": 0.01, "sdfgi_enabled": True}}}},
        {"op": "node.create", "parent": ".", "name": "Sun", "type": "DirectionalLight3D",
         "props": {"rotation_degrees": [-50, 30, 0], "shadow_enabled": True, "light_energy": 1.0}},
        {"op": "node.create", "parent": ".", "name": "Lamp", "type": "OmniLight3D",
         "props": {"position": [0, 2.5, 0], "omni_range": 6.0, "light_color": "#ffd9a0"}},
        {"op": "node.create", "parent": ".", "name": "Spot", "type": "SpotLight3D",
         "props": {"position": [3, 3, 3], "rotation_degrees": [-60, 45, 0], "spot_angle": 30.0}},
        {"op": "node.create", "parent": ".", "name": "Floor", "type": "CSGBox3D",
         "props": {"size": [12, 0.5, 12], "position": [0, -0.25, 0], "use_collision": True,
                   "material": _mat("#777777", roughness=0.9)}},
        {"op": "node.create", "parent": ".", "name": "Walls", "type": "CSGCombiner3D", "props": {"use_collision": True}},
        {"op": "node.create", "parent": "Walls", "name": "Wall", "type": "CSGBox3D",
         "props": {"size": [12, 3, 0.3], "position": [0, 1.5, -6], "material": _mat("#a08060")}},
        {"op": "node.create", "parent": "Walls", "name": "Door", "type": "CSGBox3D",
         "props": {"operation": "Subtraction", "size": [1.2, 2.2, 1], "position": [0, 1.1, -6]}},
        {"op": "node.create", "parent": ".", "name": "Pillar", "type": "MeshInstance3D",
         "props": {"position": [3, 1.5, -3],
                   "mesh": {"$type": "CylinderMesh", "props": {"top_radius": 0.3, "bottom_radius": 0.35, "height": 3.0}},
                   "material_override": {"$type": "ORMMaterial3D", "props": {
                       "albedo_color": "#c0c0c8", "uv1_scale": [2, 2, 2]}}}},
        {"op": "node.create", "parent": ".", "name": "Orb", "type": "MeshInstance3D",
         "props": {"position": [-2, 1, -2], "mesh": {"$type": "SphereMesh", "props": {"radius": 0.4, "height": 0.8}},
                   "material_override": {"$type": "ShaderMaterial", "props": {
                       "shader": {"$type": "Shader", "props": {"code": ORB_SHADER}}}}}},
        {"op": "node.create", "parent": ".", "name": "Dust", "type": "GPUParticles3D",
         "props": {"amount": 64, "lifetime": 2.0,
                   "process_material": {"$type": "ParticleProcessMaterial", "props": {
                       "emission_shape": "Box", "emission_box_extents": [4, 1, 4], "gravity": [0, -0.2, 0]}},
                   "draw_pass_1": {"$type": "QuadMesh", "props": {"size": [0.05, 0.05]}}}},
        {"op": "node.create", "parent": ".", "name": "Ball", "type": "RigidBody3D",
         "props": {"position": [0, 3, 1], "mass": 1.5}},
        {"op": "node.create", "parent": "Ball", "name": "Shape", "type": "CollisionShape3D",
         "props": {"shape": {"$type": "SphereShape3D", "props": {"radius": 0.3}}}},
        {"op": "node.create", "parent": "Ball", "name": "Mesh", "type": "MeshInstance3D",
         "props": {"mesh": {"$type": "SphereMesh", "props": {"radius": 0.3, "height": 0.6}}}},
        {"op": "node.create", "parent": ".", "name": "Trigger", "type": "Area3D", "props": {"position": [4, 1, 4]}},
        {"op": "node.create", "parent": "Trigger", "name": "Shape", "type": "CollisionShape3D",
         "props": {"shape": {"$type": "BoxShape3D", "props": {"size": [2, 2, 2]}}}},
        {"op": "script.attach", "path": "Trigger", "script": "res://scripts/trigger.gd"},
        {"op": "signal.connect", "from": "Trigger", "signal": "body_entered", "to": "Trigger", "method": "_on_body_entered"},
        {"op": "group.add", "path": "Trigger", "group": "triggers"},
        {"op": "node.create", "parent": ".", "name": "Nav", "type": "NavigationRegion3D",
         "props": {"navigation_mesh": {"$type": "NavigationMesh", "props": {"agent_radius": 0.4, "cell_size": 0.25}}}},
        {"op": "node.create", "parent": "Nav", "name": "Guard", "type": "CharacterBody3D", "props": {"position": [-4, 0.9, 4]}},
        {"op": "node.create", "parent": "Nav/Guard", "name": "Shape", "type": "CollisionShape3D",
         "props": {"shape": {"$type": "CapsuleShape3D", "props": {"radius": 0.35, "height": 1.6}}}},
        {"op": "node.create", "parent": "Nav/Guard", "name": "Body", "type": "MeshInstance3D",
         "props": {"mesh": {"$type": "CapsuleMesh", "props": {"radius": 0.35, "height": 1.6}}}},
        {"op": "node.create", "parent": "Nav/Guard", "name": "Agent", "type": "NavigationAgent3D",
         "props": {"path_desired_distance": 0.5}},
        {"op": "node.create", "parent": ".", "name": "Rail", "type": "Path3D",
         "props": {"curve": {"$type": "Curve3D", "props": {
             "point_count": 3, "point_0/position": [-4, 2, -4], "point_1/position": [0, 3, -4],
             "point_2/position": [4, 2, -4]}}}},
        {"op": "node.create", "parent": "Rail", "name": "Cart", "type": "PathFollow3D", "props": {"loop": True}},
        {"op": "node.create", "parent": ".", "name": "Rig", "type": "Node3D", "props": {"position": [0, 1.6, 6]}},
        {"op": "node.create", "parent": "Rig", "name": "Arm", "type": "SpringArm3D",
         "props": {"spring_length": 3.0, "rotation_degrees": [-15, 0, 0]}},
        {"op": "node.create", "parent": "Rig/Arm", "name": "Cam", "type": "Camera3D", "props": {"current": True, "fov": 70.0}},
        {"op": "node.create", "parent": ".", "name": "Probe", "type": "ReflectionProbe",
         "props": {"size": [12, 4, 12], "position": [0, 2, 0]}},
        {"op": "node.create", "parent": ".", "name": "Hum", "type": "AudioStreamPlayer3D",
         "props": {"position": [0, 2.5, 0], "unit_size": 4.0, "max_distance": 20.0}},
        {"op": "node.create", "parent": ".", "name": "Anim", "type": "AnimationPlayer"},
        {"op": "animation.create", "player": "Anim", "name": "pulse", "length": 2.0, "loop": "pingpong",
         "autoplay": True, "tracks": [
             {"path": "Lamp:light_energy", "keys": [[0.0, 1.0], [1.0, 2.5], [2.0, 1.0]]},
             {"path": "Rail/Cart:progress_ratio", "keys": [[0.0, 0.0], [2.0, 1.0]]},
             {"path": "Pillar:rotation_degrees", "keys": [[0.0, [0, 0, 0]], [2.0, [0, 90, 0]]]},
             {"type": "method", "path": "Trigger", "keys": [[0.5, {"method": "ping", "args": []}]]}]},
        {"op": "node.create", "parent": ".", "name": "Tree", "type": "AnimationTree",
         "props": {"anim_player": "../Anim", "active": False,
                   "tree_root": {"$type": "AnimationNodeAnimation", "props": {"animation": "pulse"}}}},
    ]


def run(ctx: Ctx) -> None:
    project = ctx.project("gk-room", {"scripts/trigger.gd": TRIGGER_GD}, main_scene="res://room.tscn")

    receipt = ctx.guard("build room", lambda: S.apply(
        project, "res://room.tscn", room_ops(), "w3.room.1",
        create={"root_type": "Node3D", "root_name": "Room", "props": {}}))
    if receipt is None:
        return
    ctx.check("room committed with fresh readback", receipt.get("readback") == "FRESH_PROCESS_MATCH",
              nodes=receipt.get("node_count"))

    view = S.inspect(project, "res://room.tscn")
    nodes = {n["path"]: n for n in view["nodes"]}
    props = lambda p: nodes.get(p, {}).get("props", {})  # noqa: E731
    env = props("Env").get("environment", {})
    env_props = env.get("props", {})
    ctx.check("environment with procedural sky", env.get("$type") == "Environment" and env_props.get("background_mode") == 2
              and env_props.get("sky", {}).get("props", {}).get("sky_material", {}).get("$type") == "ProceduralSkyMaterial",
              env=str(env)[:300])
    ctx.check("glow, fog, tonemap and sdfgi saved", env_props.get("glow_enabled") is True
              and env_props.get("fog_enabled") is True and env_props.get("sdfgi_enabled") is True
              and env_props.get("tonemap_mode") == 3)
    ctx.check("three light kinds", all(p in nodes for p in ("Sun", "Lamp", "Spot")) and props("Sun").get("shadow_enabled") is True)
    ctx.check("CSG door subtraction", props("Walls/Door").get("operation") == 2 and props("Walls").get("use_collision") is True)
    ctx.check("ORM and shader materials", props("Pillar").get("material_override", {}).get("$type") == "ORMMaterial3D"
              and props("Orb").get("material_override", {}).get("$type") == "ShaderMaterial")
    ctx.check("3D particles with draw pass", props("Dust").get("draw_pass_1", {}).get("$type") == "QuadMesh")
    ctx.check("navigation agent under region", "Nav/Guard/Agent" in nodes and props("Nav").get("navigation_mesh", {}).get("$type")
              == "NavigationMesh")
    ctx.check("curve3d path", props("Rail").get("curve", {}).get("$type") == "Curve3D")
    ctx.check("spring arm camera current", props("Rig/Arm/Cam").get("current") is True)
    conns = [(c.get("from"), c.get("signal"), c.get("method")) for c in view.get("connections", [])]
    ctx.check("trigger signal wired to script", ("Trigger", "body_entered", "_on_body_entered") in conns, conns=conns)
    ctx.check("animation tree root", props("Tree").get("tree_root", {}).get("$type") == "AnimationNodeAnimation")

    run = C.run_godot(project.root, None, (), headless=True, timeout=90, extra=("--quit-after", "60"))
    ctx.check("room runs 60 frames without errors", run.exit_code == 0 and not run.errors,
              exit_code=run.exit_code, errors=run.errors[:8])
    clean = S.check(project)
    ctx.check("project check clean", clean.get("clean") is True, problems=clean.get("problems"),
              errors=clean.get("godot_errors"))
