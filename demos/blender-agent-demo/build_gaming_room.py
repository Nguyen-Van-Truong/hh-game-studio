"""Build a cinematic cyberpunk gaming bedroom in Blender 4.5.

Run:
  blender --background --python build_gaming_room.py
"""
from __future__ import annotations

import math
import os
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

OUT_DIR = Path(os.environ.get("HH_BLENDER_OUT", r"D:\AI-Blender-Demo\out"))
WORKSPACE_COPY = Path(
    r"d:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio"
    r"\demos\blender-agent-demo"
)
BLEND_PATH = OUT_DIR / "gaming_room.blend"
PNG_PATH = OUT_DIR / "gaming_room_final.png"
GLB_PATH = OUT_DIR / "gaming_room.glb"

ROOM_W, ROOM_D, ROOM_H = 5.0, 4.0, 2.68
WALL_T = 0.10
SEED = 26


def reset_scene() -> None:
    master = bpy.context.scene.collection
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for datablock in (
        bpy.data.meshes,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.materials,
        bpy.data.curves,
        bpy.data.images,
    ):
        for item in list(datablock):
            datablock.remove(item)
    for col in list(bpy.data.collections):
        if col != master:
            bpy.data.collections.remove(col)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"


def collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def link(obj: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def shade_smooth(obj: bpy.types.Object) -> None:
    mesh = obj.data
    if hasattr(mesh, "polygons"):
        for poly in mesh.polygons:
            poly.use_smooth = True


def apply_bevel(obj: bpy.types.Object, width: float = 0.006, segments: int = 2) -> None:
    if obj.type != "MESH":
        return
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        pass
    obj.select_set(False)


def box(
    name: str,
    size: tuple[float, float, float],
    location: tuple[float, float, float],
    col: bpy.types.Collection,
    mat: bpy.types.Material | None = None,
    bevel: float | None = 0.005,
) -> bpy.types.Object:
    sx, sy, sz = size
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link(obj, col)
    if mat:
        obj.data.materials.append(mat)
    if bevel and bevel > 0:
        apply_bevel(obj, width=bevel)
    shade_smooth(obj)
    return obj


def cylinder(
    name: str,
    radius: float,
    depth: float,
    location: tuple[float, float, float],
    col: bpy.types.Collection,
    mat: bpy.types.Material | None = None,
    verts: int = 24,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=verts, radius=radius, depth=depth, location=location
    )
    obj = bpy.context.active_object
    obj.name = name
    link(obj, col)
    if mat:
        obj.data.materials.append(mat)
    shade_smooth(obj)
    return obj


def ico(
    name: str,
    radius: float,
    location: tuple[float, float, float],
    col: bpy.types.Collection,
    mat: bpy.types.Material | None = None,
    subdiv: int = 2,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=radius, location=location)
    obj = bpy.context.active_object
    obj.name = name
    link(obj, col)
    if mat:
        obj.data.materials.append(mat)
    shade_smooth(obj)
    return obj


def set_pbr(mat: bpy.types.Material, **kwargs) -> None:
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    mapping = {
        "base": "Base Color",
        "metallic": "Metallic",
        "roughness": "Roughness",
        "specular": "Specular IOR Level",
        "ior": "IOR",
        "transmission": "Transmission Weight",
        "emission": "Emission Color",
        "emission_strength": "Emission Strength",
        "alpha": "Alpha",
        "coat": "Coat Weight",
        "coat_roughness": "Coat Roughness",
    }
    for key, value in kwargs.items():
        socket = mapping.get(key, key)
        if socket in bsdf.inputs:
            bsdf.inputs[socket].default_value = value


def material(name: str, **kwargs) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    set_pbr(mat, **kwargs)
    if kwargs.get("alpha", 1.0) < 1.0 or kwargs.get("transmission", 0.0) > 0.0:
        mat.surface_render_method = "DITHERED"
        mat.use_transparency_overlap = True
    return mat


def screen_material(
    name: str, color: tuple[float, float, float], strength: float
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 18.0
    wave.inputs["Distortion"].default_value = 3.5
    wave.inputs["Detail"].default_value = 4.0
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 9.0
    brick.inputs["Mortar Size"].default_value = 0.08
    brick.inputs["Color1"].default_value = (*color, 1.0)
    brick.inputs["Color2"].default_value = (color[0] * 0.25, color[1] * 0.25, color[2] * 0.25, 1.0)
    brick.inputs["Mortar"].default_value = (0.01, 0.02, 0.03, 1.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["Factor"].default_value = 0.45
    nt.links.new(coord.outputs["UV"], wave.inputs["Vector"])
    nt.links.new(coord.outputs["UV"], brick.inputs["Vector"])
    nt.links.new(brick.outputs["Color"], mix.inputs["A"])
    nt.links.new(wave.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Emission Color"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.inputs["Roughness"].default_value = 0.22
    return mat


def emission_mat(name: str, color: tuple[float, float, float], strength: float) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.inputs["Roughness"].default_value = 0.35
    return mat


def floor_material() -> bpy.types.Material:
    mat = bpy.data.materials.new("Floor_DarkPanel")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexBrick")
    tex.location = (-420, 0)
    tex.inputs["Scale"].default_value = 7.5
    tex.inputs["Mortar Size"].default_value = 0.012
    tex.inputs["Color1"].default_value = (0.035, 0.038, 0.048, 1)
    tex.inputs["Color2"].default_value = (0.048, 0.042, 0.055, 1)
    tex.inputs["Mortar"].default_value = (0.012, 0.08, 0.09, 1)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    coord.location = (-640, 0)
    nt.links.new(coord.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Specular IOR Level"].default_value = 0.45
    bsdf.inputs["Coat Weight"].default_value = 0.12
    return mat


def look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area(
    name: str,
    location: tuple[float, float, float],
    col: bpy.types.Collection,
    energy: float,
    color: tuple[float, float, float],
    size: float,
    size_y: float | None = None,
    rot: tuple[float, float, float] = (0, 0, 0),
    shape: str = "RECTANGLE",
) -> bpy.types.Object:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = shape
    data.size = size
    if size_y is not None:
        data.size_y = size_y
    data.spread = math.radians(150)
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    obj.rotation_euler = rot
    col.objects.link(obj)
    return obj


def add_point(
    name: str,
    location: tuple[float, float, float],
    col: bpy.types.Collection,
    energy: float,
    color: tuple[float, float, float],
    radius: float = 0.08,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name, "POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = radius
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    col.objects.link(obj)
    return obj


def build_materials() -> dict[str, bpy.types.Material]:
    cyan = (0.15, 0.85, 1.0)
    magenta = (1.0, 0.18, 0.72)
    return {
        "wall": material(
            "Wall_Plaster",
            base=(0.10, 0.11, 0.13, 1),
            roughness=0.78,
            specular=0.25,
        ),
        "trim": material("Trim_Black", base=(0.02, 0.02, 0.025, 1), roughness=0.28, metallic=0.15),
        "floor": floor_material(),
        "ceiling": material("Ceiling_Dark", base=(0.03, 0.035, 0.045, 1), roughness=0.85),
        "desk": material(
            "Desk_MatteBlack",
            base=(0.018, 0.02, 0.024, 1),
            roughness=0.32,
            coat=0.35,
            coat_roughness=0.12,
        ),
        "wood": material("Desk_WoodEdge", base=(0.12, 0.06, 0.03, 1), roughness=0.45),
        "metal": material(
            "Metal_Brushed",
            base=(0.12, 0.13, 0.15, 1),
            metallic=0.85,
            roughness=0.28,
        ),
        "plastic": material("Plastic_Dark", base=(0.03, 0.03, 0.035, 1), roughness=0.4),
        "fabric": material("Fabric_Charcoal", base=(0.04, 0.045, 0.055, 1), roughness=0.9),
        "linen": material("Bed_Linen", base=(0.14, 0.10, 0.16, 1), roughness=0.68),
        "pillow": material("Pillow_Teal", base=(0.05, 0.16, 0.18, 1), roughness=0.8),
        "glass": material(
            "Glass_Dark",
            base=(0.05, 0.07, 0.09, 1),
            roughness=0.06,
            transmission=0.92,
            ior=1.45,
            alpha=0.12,
            metallic=0.0,
        ),
        "screen_c": emission_mat("Screen_Cyan", (0.35, 0.82, 1.0), 4.2),
        "screen_m": emission_mat("Screen_Magenta", (1.0, 0.28, 0.72), 3.8),
        "screen_w": emission_mat("Screen_Code", (0.45, 0.95, 0.55), 3.6),
        "neon_c": emission_mat("Neon_Cyan", cyan, 9.0),
        "neon_m": emission_mat("Neon_Magenta", magenta, 8.0),
        "neon_a": emission_mat("Neon_Amber", (1.0, 0.55, 0.18), 4.5),
        "led_pc": emission_mat("PC_Interior", (0.25, 0.55, 1.0), 3.5),
        "leaf": material("Plant_Leaf", base=(0.04, 0.16, 0.07, 1), roughness=0.55),
        "pot": material("Plant_Pot", base=(0.08, 0.04, 0.03, 1), roughness=0.6),
        "city": material("City_Concrete", base=(0.06, 0.07, 0.09, 1), roughness=0.62, metallic=0.08),
        "poster1": material("Poster_A", base=(0.45, 0.12, 0.38, 1), roughness=0.7, emission=(0.55, 0.12, 0.45, 1), emission_strength=0.8),
        "poster2": material("Poster_B", base=(0.12, 0.22, 0.45, 1), roughness=0.7, emission=(0.12, 0.35, 0.7, 1), emission_strength=0.6),
        "window_glow": emission_mat("City_Window", (1.0, 0.82, 0.52), 1.8),
        "window_cool": emission_mat("City_WindowCool", (0.45, 0.75, 1.0), 1.4),
        "pad": material("Mousepad", base=(0.04, 0.03, 0.05, 1), roughness=0.7, coat=0.2),
        "rug": material("Rug_Dark", base=(0.05, 0.04, 0.06, 1), roughness=0.95),
    }


def build_room(cols: dict, mats: dict) -> None:
    room = cols["ROOM"]
    # Floor and ceiling sit just outside the usable volume.
    box("Floor", (ROOM_W + 0.2, ROOM_D + 0.2, 0.08), (ROOM_W / 2, ROOM_D / 2, -0.04), room, mats["floor"], 0)
    box(
        "Ceiling",
        (ROOM_W + 0.2, ROOM_D + 0.2, 0.08),
        (ROOM_W / 2, ROOM_D / 2, ROOM_H + 0.04),
        room,
        mats["ceiling"],
        0,
    )

    # Left wall (X=0) full.
    box(
        "Wall_Left",
        (WALL_T, ROOM_D + WALL_T * 2, ROOM_H),
        (-WALL_T / 2, ROOM_D / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )
    # Right wall (X=5) full.
    box(
        "Wall_Right",
        (WALL_T, ROOM_D + WALL_T * 2, ROOM_H),
        (ROOM_W + WALL_T / 2, ROOM_D / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )

    # Front wall with door opening at X=0.55..1.50, Z=0..2.12
    door_x0, door_x1, door_h = 0.55, 1.50, 2.12
    box(
        "Wall_Front_L",
        (door_x0 + WALL_T, WALL_T, ROOM_H),
        ((-WALL_T + door_x0) / 2, -WALL_T / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )
    box(
        "Wall_Front_R",
        (ROOM_W - door_x1 + WALL_T, WALL_T, ROOM_H),
        ((door_x1 + ROOM_W + WALL_T) / 2, -WALL_T / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )
    box(
        "Wall_Front_Lintel",
        (door_x1 - door_x0, WALL_T, ROOM_H - door_h),
        ((door_x0 + door_x1) / 2, -WALL_T / 2, (door_h + ROOM_H) / 2),
        room,
        mats["wall"],
        0,
    )

    # Back wall with window X=0.70..3.40, Z=0.90..2.20
    wx0, wx1, wz0, wz1 = 0.70, 3.40, 0.90, 2.20
    box(
        "Wall_Back_L",
        (wx0 + WALL_T, WALL_T, ROOM_H),
        ((-WALL_T + wx0) / 2, ROOM_D + WALL_T / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )
    box(
        "Wall_Back_R",
        (ROOM_W - wx1 + WALL_T, WALL_T, ROOM_H),
        ((wx1 + ROOM_W + WALL_T) / 2, ROOM_D + WALL_T / 2, ROOM_H / 2),
        room,
        mats["wall"],
        0,
    )
    box(
        "Wall_Back_Sill",
        (wx1 - wx0, WALL_T, wz0),
        ((wx0 + wx1) / 2, ROOM_D + WALL_T / 2, wz0 / 2),
        room,
        mats["wall"],
        0,
    )
    box(
        "Wall_Back_Head",
        (wx1 - wx0, WALL_T, ROOM_H - wz1),
        ((wx0 + wx1) / 2, ROOM_D + WALL_T / 2, (wz1 + ROOM_H) / 2),
        room,
        mats["wall"],
        0,
    )

    # Window frame + mullions.
    frame = mats["metal"]
    fy = ROOM_D - 0.02
    box("WinFrame_B", (wx1 - wx0 + 0.08, 0.04, 0.05), ((wx0 + wx1) / 2, fy, wz0), room, frame, 0.002)
    box("WinFrame_T", (wx1 - wx0 + 0.08, 0.04, 0.05), ((wx0 + wx1) / 2, fy, wz1), room, frame, 0.002)
    box("WinFrame_L", (0.05, 0.04, wz1 - wz0 + 0.05), (wx0, fy, (wz0 + wz1) / 2), room, frame, 0.002)
    box("WinFrame_R", (0.05, 0.04, wz1 - wz0 + 0.05), (wx1, fy, (wz0 + wz1) / 2), room, frame, 0.002)
    box("WinMullion", (0.035, 0.03, wz1 - wz0), ((wx0 + wx1) / 2, fy, (wz0 + wz1) / 2), room, frame, 0.002)
    box(
        "WinNeon",
        (wx1 - wx0 + 0.12, 0.02, 0.02),
        ((wx0 + wx1) / 2, ROOM_D - 0.06, wz1 + 0.04),
        room,
        mats["neon_c"],
        0,
    )

    # Baseboards.
    for name, loc, size in (
        ("Base_Left", (0.02, ROOM_D / 2, 0.05), (0.03, ROOM_D, 0.10)),
        ("Base_Right", (ROOM_W - 0.02, ROOM_D / 2, 0.05), (0.03, ROOM_D, 0.10)),
        ("Base_Back", (ROOM_W / 2, ROOM_D - 0.02, 0.05), (ROOM_W, 0.03, 0.10)),
    ):
        box(name, size, loc, room, mats["trim"], 0.002)

    # Ceiling cove LED.
    box(
        "Cove_Front",
        (ROOM_W - 0.3, 0.04, 0.015),
        (ROOM_W / 2, 0.18, ROOM_H - 0.04),
        room,
        mats["neon_m"],
        0,
    )
    box(
        "Cove_Back",
        (ROOM_W - 0.3, 0.04, 0.015),
        (ROOM_W / 2, ROOM_D - 0.18, ROOM_H - 0.04),
        room,
        mats["neon_c"],
        0,
    )
    box(
        "Cove_Left",
        (0.04, ROOM_D - 0.36, 0.015),
        (0.18, ROOM_D / 2, ROOM_H - 0.04),
        room,
        mats["neon_c"],
        0,
    )


def build_desk(cols: dict, mats: dict) -> None:
    furn = cols["FURNITURE"]
    setup = cols["SETUP"]
    z_top = 0.74
    thick = 0.04

    # L-desk: long run along the window, return along the left wall.
    main = box("Desk_Main", (2.75, 0.72, thick), (1.80, 3.42, z_top - thick / 2), furn, mats["desk"], 0.004)
    ret = box("Desk_Return", (0.70, 1.55, thick), (0.55, 2.45, z_top - thick / 2), furn, mats["desk"], 0.004)
    box("Desk_WoodLip", (2.75, 0.03, 0.02), (1.80, 3.07, z_top + 0.005), furn, mats["wood"], 0.002)

    # Legs / cabinets.
    box("Desk_Cab_L", (0.42, 0.62, 0.62), (0.55, 3.38, 0.31), furn, mats["desk"], 0.004)
    box("Desk_Leg_R", (0.06, 0.06, 0.70), (3.08, 3.18, 0.35), furn, mats["metal"], 0.002)
    box("Desk_Leg_R2", (0.06, 0.06, 0.70), (3.08, 3.62, 0.35), furn, mats["metal"], 0.002)
    box("Desk_Leg_M", (0.06, 0.06, 0.70), (0.90, 1.78, 0.35), furn, mats["metal"], 0.002)

    # Cable tray + RGB underglow.
    box("Desk_RGB", (2.55, 0.04, 0.012), (1.80, 3.18, 0.62), setup, mats["neon_c"], 0)
    box("Desk_RGB2", (0.04, 1.35, 0.012), (0.88, 2.45, 0.62), setup, mats["neon_m"], 0)

    # Monitor arm + triple screens.
    box("Arm_Pole", (0.04, 0.04, 0.42), (1.85, 3.62, z_top + 0.21), setup, mats["metal"], 0.002)
    box("Arm_Bar", (1.55, 0.03, 0.03), (1.85, 3.62, z_top + 0.38), setup, mats["metal"], 0.002)

    screens = [
        ("Monitor_L", (1.05, 3.55, z_top + 0.38), -0.18, mats["screen_c"]),
        ("Monitor_C", (1.85, 3.58, z_top + 0.40), 0.0, mats["screen_w"]),
        ("Monitor_R", (2.65, 3.55, z_top + 0.38), 0.18, mats["screen_m"]),
    ]
    for name, loc, yaw, smat in screens:
        bezel = box(name, (0.62, 0.045, 0.36), loc, setup, mats["plastic"], 0.002)
        bezel.rotation_euler.z = yaw
        glass = box(name + "_Screen", (0.56, 0.01, 0.30), (loc[0], loc[1] - 0.028, loc[2]), setup, smat, 0)
        glass.rotation_euler.z = yaw

    # Keyboard, mouse, pad, speakers, mic.
    box("Mousepad", (0.78, 0.32, 0.008), (1.85, 3.22, z_top + 0.006), setup, mats["pad"], 0)
    box("Keyboard", (0.44, 0.14, 0.018), (1.72, 3.22, z_top + 0.018), setup, mats["plastic"], 0.002)
    box("KeysGlow", (0.40, 0.10, 0.004), (1.72, 3.22, z_top + 0.028), setup, mats["plastic"], 0)
    box("Mouse", (0.07, 0.11, 0.03), (2.12, 3.20, z_top + 0.02), setup, mats["plastic"], 0.004)
    box("Speaker_L", (0.09, 0.11, 0.18), (0.95, 3.28, z_top + 0.10), setup, mats["plastic"], 0.003)
    box("Speaker_R", (0.09, 0.11, 0.18), (2.72, 3.28, z_top + 0.10), setup, mats["plastic"], 0.003)
    cyl = cylinder("Headphone_Stand", 0.015, 0.28, (0.95, 3.08, z_top + 0.14), setup, mats["metal"], 12)
    box("Headphones", (0.16, 0.12, 0.08), (0.95, 3.08, z_top + 0.30), setup, mats["plastic"], 0.004)

    # PC tower with glass side, sitting on the return.
    case = box("PC_Case", (0.22, 0.46, 0.44), (0.55, 2.15, z_top + 0.22), setup, mats["metal"], 0.003)
    box("PC_Glass", (0.01, 0.40, 0.38), (0.66, 2.15, z_top + 0.22), setup, mats["glass"], 0)
    box("PC_GPU", (0.12, 0.28, 0.04), (0.55, 2.15, z_top + 0.16), setup, mats["led_pc"], 0)
    box("PC_Fans", (0.02, 0.12, 0.12), (0.44, 2.02, z_top + 0.28), setup, mats["neon_c"], 0)
    box("PC_Fans2", (0.02, 0.12, 0.12), (0.44, 2.28, z_top + 0.28), setup, mats["neon_m"], 0)

    _ = (main, ret, case, cyl)


def build_chair(cols: dict, mats: dict) -> None:
    furn = cols["FURNITURE"]
    x, y = 1.85, 2.42
    box("Chair_Seat", (0.46, 0.46, 0.08), (x, y, 0.48), furn, mats["fabric"], 0.008)
    box("Chair_Back", (0.46, 0.08, 0.58), (x, y + 0.22, 0.82), furn, mats["fabric"], 0.008)
    box("Chair_Lumbar", (0.36, 0.05, 0.12), (x, y + 0.18, 0.62), furn, mats["plastic"], 0.006)
    box("Chair_Piping", (0.40, 0.02, 0.50), (x, y + 0.26, 0.82), furn, mats["neon_c"], 0)
    box("Chair_Cushion", (0.40, 0.40, 0.04), (x, y, 0.53), furn, mats["fabric"], 0.01)
    cylinder("Chair_Pole", 0.03, 0.28, (x, y, 0.30), furn, mats["metal"], 16)
    cylinder("Chair_Hub", 0.07, 0.05, (x, y, 0.16), furn, mats["metal"], 16)
    for i, ang in enumerate((0, 72, 144, 216, 288)):
        rad = math.radians(ang)
        cx = x + math.cos(rad) * 0.28
        cy = y + math.sin(rad) * 0.28
        arm = box(f"Chair_Star{i}", (0.28, 0.05, 0.04), ((x + cx) / 2, (y + cy) / 2, 0.15), furn, mats["metal"], 0.002)
        arm.rotation_euler.z = rad
        cylinder(f"Chair_Wheel{i}", 0.035, 0.04, (cx, cy, 0.05), furn, mats["plastic"], 12)
    box("Chair_ArmL", (0.06, 0.28, 0.04), (x - 0.24, y - 0.02, 0.68), furn, mats["plastic"], 0.003)
    box("Chair_ArmR", (0.06, 0.28, 0.04), (x + 0.24, y - 0.02, 0.68), furn, mats["plastic"], 0.003)


def build_bed_and_storage(cols: dict, mats: dict) -> None:
    furn = cols["FURNITURE"]
    # Bed along the right wall.
    box("Bed_Frame", (1.42, 2.05, 0.18), (4.22, 1.55, 0.22), furn, mats["trim"], 0.006)
    box("Mattress", (1.32, 1.95, 0.16), (4.22, 1.55, 0.38), furn, mats["linen"], 0.01)
    box("Duvet", (1.22, 1.45, 0.07), (4.22, 1.38, 0.48), furn, mats["linen"], 0.012)
    box("Pillow_A", (0.52, 0.32, 0.12), (4.00, 2.32, 0.52), furn, mats["pillow"], 0.02)
    box("Pillow_B", (0.52, 0.32, 0.12), (4.44, 2.32, 0.52), furn, mats["pillow"], 0.02)
    box("Bed_RGB", (1.30, 1.90, 0.012), (4.22, 1.55, 0.08), furn, mats["neon_m"], 0)
    box("Rug", (2.2, 1.6, 0.02), (2.15, 2.15, 0.012), furn, mats["rug"], 0)

    # Nightstand + lamp.
    box("Nightstand", (0.42, 0.40, 0.48), (4.55, 0.42, 0.24), furn, mats["desk"], 0.004)
    cylinder("Lamp_Pole", 0.015, 0.22, (4.55, 0.42, 0.59), furn, mats["metal"], 12)
    shade = cylinder("Lamp_Shade", 0.09, 0.10, (4.55, 0.42, 0.74), furn, mats["neon_a"], 16)

    # Left-wall shelves.
    box("Shelf_1", (0.28, 1.10, 0.04), (0.18, 1.35, 1.55), furn, mats["wood"], 0.003)
    box("Shelf_2", (0.28, 1.10, 0.04), (0.18, 1.35, 1.95), furn, mats["wood"], 0.003)
    box("Book_A", (0.06, 0.18, 0.24), (0.18, 1.05, 1.69), furn, mats["poster1"], 0.002)
    box("Book_B", (0.06, 0.16, 0.20), (0.18, 1.22, 1.67), furn, mats["poster2"], 0.002)
    box("Figure", (0.08, 0.08, 0.16), (0.18, 1.55, 2.05), furn, mats["neon_c"], 0.004)
    box("MiniPlantPot", (0.09, 0.09, 0.08), (0.18, 1.70, 2.01), furn, mats["pot"], 0.003)
    ico("MiniPlant", 0.08, (0.18, 1.70, 2.12), furn, mats["leaf"], 1)

    # Door leaf slightly open.
    door = box("Door", (0.06, 0.88, 2.10), (0.55, 0.42, 1.06), furn, mats["desk"], 0.003)
    door.rotation_euler.z = math.radians(-28)
    _ = shade


def build_plants_and_posters(cols: dict, mats: dict) -> None:
    decor = cols["DECOR"]
    # Corner plant by the window.
    cylinder("Pot_A", 0.12, 0.18, (0.38, 3.78, 0.09), decor, mats["pot"], 16)
    ico("Foliage_A1", 0.22, (0.38, 3.78, 0.38), decor, mats["leaf"], 2)
    ico("Foliage_A2", 0.16, (0.28, 3.70, 0.52), decor, mats["leaf"], 2)
    ico("Foliage_A3", 0.14, (0.48, 3.84, 0.50), decor, mats["leaf"], 2)

    cylinder("Pot_B", 0.10, 0.16, (3.62, 3.78, 0.08), decor, mats["pot"], 16)
    ico("Foliage_B1", 0.18, (3.62, 3.78, 0.34), decor, mats["leaf"], 2)
    ico("Foliage_B2", 0.12, (3.72, 3.70, 0.46), decor, mats["leaf"], 2)

    # Posters on the right and left walls.
    box("Poster_Right", (0.02, 0.62, 0.88), (4.93, 3.15, 1.55), decor, mats["poster1"], 0)
    box("Poster_Right2", (0.02, 0.48, 0.62), (4.93, 2.45, 1.45), decor, mats["poster2"], 0)
    box("Poster_Left", (0.02, 0.55, 0.75), (0.06, 2.55, 1.70), decor, mats["poster2"], 0)

    # Neon wall sign on the right wall, facing into the room.
    curve = bpy.data.curves.new("NeonSignCurve", "FONT")
    curve.body = "NIGHT"
    curve.size = 0.20
    curve.extrude = 0.012
    curve.bevel_depth = 0.003
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    text = bpy.data.objects.new("NeonSign", curve)
    text.location = (4.90, 3.18, 1.62)
    text.rotation_euler = (math.radians(90), 0.0, math.radians(-90))
    cols["DECOR"].objects.link(text)
    bpy.context.view_layer.objects.active = text
    text.select_set(True)
    bpy.ops.object.convert(target="MESH")
    text = bpy.context.active_object
    text.data.materials.append(mats["neon_m"])
    text.select_set(False)


def build_city(cols: dict, mats: dict) -> None:
    city = cols["CITY"]
    rng = random.Random(SEED)
    # Ground plane of the night city just outside the window.
    box("City_Ground", (18.0, 14.0, 0.2), (2.5, 11.0, -0.4), city, mats["city"], 0)
    buildings = [
        (1.0, 9.4, 9.0, 2.2, 2.6, 11.0),
        (3.6, 8.8, 12.5, 2.4, 2.2, 14.5),
        (6.2, 10.5, 8.4, 1.8, 2.4, 9.0),
        (-1.4, 10.8, 11.0, 2.2, 2.4, 12.5),
        (0.2, 13.8, 16.0, 2.8, 2.6, 18.0),
        (5.0, 14.2, 18.5, 2.6, 3.0, 20.0),
        (8.0, 11.6, 13.0, 2.0, 2.4, 13.5),
        (-3.2, 9.2, 8.0, 1.8, 2.0, 8.5),
        (2.2, 12.0, 6.5, 1.6, 1.8, 7.5),
    ]
    for i, (x, y, z, sx, sy, sz) in enumerate(buildings):
        loc = (x, y, sz / 2)
        box(f"Bldg_{i}", (sx, sy, sz), loc, city, mats["city"], 0.01)
        cols_n = max(3, int(sx / 0.55))
        rows_n = max(5, int(sz / 0.7))
        for col_i in range(cols_n):
            for row_i in range(rows_n):
                if rng.random() < 0.52:
                    continue
                wx = x - sx / 2 + 0.28 + col_i * ((sx - 0.5) / max(1, cols_n - 1))
                wz = 0.55 + row_i * ((sz - 1.1) / max(1, rows_n - 1))
                glow = mats["window_glow"] if rng.random() < 0.55 else mats["window_cool"]
                box(
                    f"Win_{i}_{col_i}_{row_i}",
                    (0.14, 0.03, 0.22),
                    (wx, y - sy / 2 - 0.03, wz),
                    city,
                    glow,
                    0,
                )

    box("HorizonGlow", (28.0, 0.4, 2.4), (2.5, 22.0, 3.2), city, mats["poster1"], 0)


def build_lights(cols: dict) -> None:
    lights = cols["LIGHTS"]
    # Key: cool window fill.
    add_area(
        "L_Window",
        (2.05, 3.95, 1.55),
        lights,
        energy=38,
        color=(0.45, 0.72, 1.0),
        size=2.4,
        size_y=1.1,
        rot=(math.radians(-90), 0, 0),
    )
    # Warm practical over the desk.
    add_area(
        "L_DeskWarm",
        (1.85, 3.15, 1.55),
        lights,
        energy=16,
        color=(1.0, 0.72, 0.45),
        size=0.7,
        size_y=0.35,
        rot=(math.radians(0), 0, 0),
    )
    look_at(bpy.data.objects["L_DeskWarm"], (1.85, 3.35, 0.9))
    # Magenta rim from the bed / right wall.
    add_area(
        "L_BedRim",
        (4.35, 1.6, 1.35),
        lights,
        energy=10,
        color=(1.0, 0.25, 0.75),
        size=1.3,
        size_y=0.4,
        rot=(0, math.radians(-55), 0),
    )
    add_area(
        "L_ChairFill",
        (2.4, 1.7, 1.35),
        lights,
        energy=9,
        color=(0.85, 0.9, 1.0),
        size=0.8,
        size_y=0.5,
        rot=(math.radians(-35), math.radians(15), 0),
    )
    # Ceiling bounce.
    add_area(
        "L_Ceiling",
        (2.4, 2.0, 2.55),
        lights,
        energy=6,
        color=(0.55, 0.7, 1.0),
        size=2.8,
        size_y=2.2,
        rot=(math.radians(180), 0, 0),
    )
    add_point("L_PC", (0.62, 2.15, 0.95), lights, energy=4, color=(0.3, 0.6, 1.0), radius=0.06)
    add_point("L_Lamp", (4.55, 0.42, 0.78), lights, energy=22, color=(1.0, 0.62, 0.28), radius=0.08)
    add_point("L_Sign", (4.70, 3.18, 1.62), lights, energy=6, color=(1.0, 0.2, 0.7), radius=0.08)


def build_camera(cols: dict) -> bpy.types.Object:
    data = bpy.data.cameras.new("MainCam")
    data.lens = 32
    data.sensor_width = 36
    data.clip_start = 0.05
    data.clip_end = 80
    data.dof.use_dof = True
    data.dof.aperture_fstop = 2.2
    data.dof.focus_distance = 2.55
    cam = bpy.data.objects.new("MainCam", data)
    cols["CAMERAS"].objects.link(cam)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 360
    scene.render.fps = 30

    # Frame 1 — just inside the door.
    cam.location = (1.15, 0.42, 1.38)
    look_at(cam, (2.2, 2.6, 1.15))
    cam.keyframe_insert("location", frame=1)
    cam.keyframe_insert("rotation_euler", frame=1)

    # Frame 120 — approaching the desk.
    cam.location = (2.35, 1.35, 1.28)
    look_at(cam, (1.85, 3.35, 1.12))
    cam.keyframe_insert("location", frame=120)
    cam.keyframe_insert("rotation_euler", frame=120)

    # Frame 240 — slight orbit around the setup.
    cam.location = (3.15, 2.05, 1.22)
    look_at(cam, (1.70, 3.40, 1.08))
    cam.keyframe_insert("location", frame=240)
    cam.keyframe_insert("rotation_euler", frame=240)

    # Frame 360 — hero shot of monitors + PC.
    cam.location = (2.55, 2.55, 1.18)
    look_at(cam, (1.55, 3.45, 1.05))
    cam.keyframe_insert("location", frame=360)
    cam.keyframe_insert("rotation_euler", frame=360)

    # Smooth bezier.
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO_CLAMPED"
                kp.handle_right_type = "AUTO_CLAMPED"

    still_data = bpy.data.cameras.new("StillCam")
    still_data.lens = 24
    still_data.sensor_width = 36
    still_data.clip_start = 0.05
    still_data.clip_end = 80
    still_data.dof.use_dof = False
    still = bpy.data.objects.new("StillCam", still_data)
    cols["CAMERAS"].objects.link(still)
    still.location = (2.88, 0.62, 1.44)
    look_at(still, (2.35, 2.55, 1.02))
    scene.camera = still
    scene.frame_set(1)
    return still


def setup_world(scene: bpy.types.Scene) -> None:
    world = bpy.data.worlds.new("NightWorld")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.004, 0.006, 0.012, 1)
    bg.inputs["Strength"].default_value = 0.25


def setup_render(scene: bpy.types.Scene, png: Path) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(png)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.render.use_persistent_data = True

    eevee = scene.eevee
    eevee.taa_render_samples = 96
    eevee.use_shadows = True
    eevee.use_raytracing = True
    eevee.use_gtao = True
    eevee.gtao_distance = 0.35
    eevee.use_fast_gi = True
    eevee.fast_gi_quality = 0.5
    eevee.fast_gi_ray_count = 4
    eevee.shadow_ray_count = 2
    eevee.shadow_step_count = 8

    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.05
    scene.view_settings.gamma = 1.0

    scene.render.use_compositing = True
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (0, 0)
    glare = tree.nodes.new("CompositorNodeGlare")
    glare.location = (280, 0)
    if hasattr(glare, "glare_type"):
        try:
            glare.glare_type = "BLOOM"
        except TypeError:
            glare.glare_type = "FOG_GLOW"
    if "Threshold" in glare.inputs:
        glare.inputs["Threshold"].default_value = 1.35
    if "Size" in glare.inputs:
        glare.inputs["Size"].default_value = 4.0
    if hasattr(glare, "mix"):
        glare.mix = -0.55
    comp = tree.nodes.new("CompositorNodeComposite")
    comp.location = (560, 0)
    viewer = tree.nodes.new("CompositorNodeViewer")
    viewer.location = (560, -160)
    tree.links.new(rl.outputs["Image"], glare.inputs[0])
    tree.links.new(glare.outputs[0], comp.inputs[0])
    tree.links.new(glare.outputs[0], viewer.inputs[0])


def export_glb(path: Path) -> None:
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_apply=True,
        export_cameras=True,
        export_lights=True,
        export_animations=True,
    )


def copy_preview() -> None:
    WORKSPACE_COPY.mkdir(parents=True, exist_ok=True)
    for name in ("gaming_room_final.png", "gaming_room_desk.png"):
        src = OUT_DIR / name
        if src.exists():
            dest = WORKSPACE_COPY / name
            dest.write_bytes(src.read_bytes())
            print(f"COPIED_PNG={dest}")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reset_scene()
    cols = {
        "ROOM": collection("ROOM"),
        "FURNITURE": collection("FURNITURE"),
        "SETUP": collection("SETUP"),
        "DECOR": collection("DECOR"),
        "CITY": collection("CITY"),
        "LIGHTS": collection("LIGHTS"),
        "CAMERAS": collection("CAMERAS"),
    }
    mats = build_materials()
    build_room(cols, mats)
    build_desk(cols, mats)
    build_chair(cols, mats)
    build_bed_and_storage(cols, mats)
    build_plants_and_posters(cols, mats)
    build_city(cols, mats)
    build_lights(cols)
    build_camera(cols)
    scene = bpy.context.scene
    setup_world(scene)
    setup_render(scene, PNG_PATH)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    print(f"SAVED_BLEND={BLEND_PATH}")

    print("RENDER_START")
    bpy.ops.render.render(write_still=True)
    print(f"RENDER_WIDE exists={PNG_PATH.exists()} size={PNG_PATH.stat().st_size if PNG_PATH.exists() else 0}")

    still = bpy.data.objects.get("StillCam")
    if still is not None:
        still.location = (3.05, 1.55, 1.22)
        look_at(still, (1.70, 3.35, 1.08))
        still.data.lens = 35
        desk_png = OUT_DIR / "gaming_room_desk.png"
        scene.render.filepath = str(desk_png)
        bpy.ops.render.render(write_still=True)
        print(f"RENDER_DESK exists={desk_png.exists()} size={desk_png.stat().st_size if desk_png.exists() else 0}")
        still.location = (2.88, 0.62, 1.44)
        look_at(still, (2.35, 2.55, 1.02))
        still.data.lens = 24
        scene.render.filepath = str(PNG_PATH)
        scene.camera = still

    try:
        export_glb(GLB_PATH)
        print(f"SAVED_GLB={GLB_PATH}")
    except Exception as exc:
        print(f"GLB_EXPORT_FAIL {exc}")

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    copy_preview()
    print("OBJECT_COUNT", len(bpy.data.objects))
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
