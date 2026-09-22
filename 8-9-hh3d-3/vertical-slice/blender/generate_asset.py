"""Run inside Blender 4.x to create the original decorative pickup asset."""

import bpy
import os


def make_material(name, color, metallic=0.0, roughness=0.45):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.metallic = metallic
    material.roughness = roughness
    return material


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

body_material = make_material("PickupAzure", (0.08, 0.72, 0.86), metallic=0.2)
accent_material = make_material("PickupGold", (1.0, 0.63, 0.08), metallic=0.55)

bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.7, location=(0, 0, 0))
body = bpy.context.object
body.name = "OriginalPickupCore"
body.data.materials.append(body_material)

bpy.ops.mesh.primitive_torus_add(major_radius=0.95, minor_radius=0.12, location=(0, 0, 0))
ring = bpy.context.object
ring.name = "OriginalPickupRing"
ring.rotation_euler[0] = 0.35
ring.data.materials.append(accent_material)

bpy.ops.object.select_all(action="SELECT")
for obj in bpy.context.selected_objects:
    obj.select_set(True)

output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
os.makedirs(output_dir, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(output_dir, "pickup_original.blend"))
bpy.ops.export_scene.gltf(filepath=os.path.join(output_dir, "pickup_original.glb"), export_format="GLB")
print("BLENDER_ASSET_PASS", os.path.join(output_dir, "pickup_original.glb"))
