"""Quick HH World regressions: root, slash properties, and native bool probes."""

from __future__ import annotations

from .. import play as P
from . import Ctx


ROOT_GD = """extends Node3D

var root_flag: bool = true
var call_count: int = 0

func mutating_probe() -> bool:
\tcall_count += 1
\treturn true
"""

BODY_GD = """extends CharacterBody3D

func _physics_process(delta: float) -> void:
\tvelocity.y -= 9.8 * delta
\tmove_and_slide()
"""

MAIN_TSCN = """[gd_scene load_steps=7 format=3]

[ext_resource type="Script" path="res://root.gd" id="1_root"]
[ext_resource type="Script" path="res://body.gd" id="2_body"]

[sub_resource type="SphereShape3D" id="body_shape"]
radius = 0.5

[sub_resource type="BoxShape3D" id="floor_shape"]
size = Vector3(10, 1, 10)

[sub_resource type="AnimationNodeTimeScale" id="speed"]

[sub_resource type="AnimationNodeBlendTree" id="tree"]
nodes/Speed/node = SubResource("speed")

[node name="Probe" type="Node3D"]
script = ExtResource("1_root")

[node name="Body" type="CharacterBody3D" parent="."]
position = Vector3(0, 0.51, 0)
script = ExtResource("2_body")

[node name="Shape" type="CollisionShape3D" parent="Body"]
shape = SubResource("body_shape")

[node name="Floor" type="StaticBody3D" parent="."]
position = Vector3(0, -0.5, 0)

[node name="Shape" type="CollisionShape3D" parent="Floor"]
shape = SubResource("floor_shape")

[node name="Anim" type="AnimationTree" parent="."]
tree_root = SubResource("tree")
parameters/Speed/scale = 1.75
"""


def run(ctx: Ctx) -> None:
    for bad in ("../Probe:root_flag", "/root/Probe:root_flag", "Probe:parameters/../scale",
                "Probe:parameters//scale", "Probe:mutating_probe()", "Probe:"):
        ctx.expect_error(f"reject unsafe probe {bad}", "VALIDATION_FAILED", P.parse_observe, bad)
    project = ctx.project("observe", {"root.gd": ROOT_GD, "body.gd": BODY_GD, "main.tscn": MAIN_TSCN},
                          main_scene="res://main.tscn")
    result = ctx.guard("observe native and root values", lambda: P.play(
        project, frames=12, every=12,
        observe="Probe:root_flag,.:root_flag,Body:is_on_floor,Probe/Body:is_on_floor,"
                "Anim:parameters/Speed/scale,Probe:mutating_probe,Probe:call_count"))
    if not isinstance(result, dict):
        return
    rows = result.get("observations", [])
    first = rows[0].get("values", {}) if rows else {}
    last = rows[-1].get("values", {}) if rows else {}
    ctx.check("observe completes without runner errors", result.get("ok") is True
              and result.get("process", {}).get("exit_code") == 0, errors=result.get("errors"))
    ctx.check("scene root name and dot address the same root", last.get("Probe:root_flag") is True
              and last.get(".:root_flag") is True, values=last)
    ctx.check("floor probe calls the native bool query", first.get("Body:is_on_floor") is False
              and last.get("Body:is_on_floor") is True
              and last.get("Probe/Body:is_on_floor") is True, first=first, last=last)
    ctx.check("AnimationTree slash property returns the real parameter", last.get("Anim:parameters/Speed/scale") == 1.75,
              values=last)
    ctx.check("observe never invokes arbitrary script methods", last.get("Probe:mutating_probe") is None
              and last.get("Probe:call_count") == 0, values=last)
