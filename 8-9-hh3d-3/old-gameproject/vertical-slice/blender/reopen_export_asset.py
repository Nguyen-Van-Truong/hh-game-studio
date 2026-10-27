"""Reopen the saved Blender file in a fresh bpy process, validate, and export GLB."""

import bpy
import hashlib
import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSET_DIR = os.path.join(ROOT, "assets")
BLEND_PATH = os.path.join(ASSET_DIR, "pickup_original.blend")
GLB_PATH = os.path.join(ASSET_DIR, "pickup_original.glb")

bpy.ops.wm.open_mainfile(filepath=BLEND_PATH)
required_objects = {"OriginalPickupCore", "OriginalPickupRing"}
if not required_objects.issubset(set(bpy.data.objects.keys())):
    raise RuntimeError("saved blend is missing original pickup objects")
required_materials = {"PickupAzure", "PickupGold"}
if not required_materials.issubset(set(bpy.data.materials.keys())):
    raise RuntimeError("saved blend is missing original materials")
bpy.ops.export_scene.gltf(filepath=GLB_PATH, export_format="GLB")
with open(GLB_PATH, "rb") as stream:
    digest = hashlib.sha256(stream.read()).hexdigest()
print("BLENDER_REOPEN_EXPORT_PASS", digest)
