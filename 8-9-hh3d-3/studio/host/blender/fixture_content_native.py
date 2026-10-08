"""Pinned Blender main-thread producer for the GT-09 content fixture.

This module is executed by ``fixture_content_job`` in a fresh factory GUI
process. It intentionally has one closed recipe and one output directory. It
does not evaluate request text, open a caller supplied Blend, load external
libraries/images, or acknowledge publication. Every native result is written
as an observation for the host to validate independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def _need(value, code):
    if not value:
        raise RuntimeError(code)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalize_glb(path):
    """Normalize Blender's sampled walk clip to the closed fixture profile.

    Blender 5.2 exports the active layered action as ``Animation`` and samples
    the frame range at 1/24..25/24.  The fixture contract is a one-second
    ``walk`` clip with [0, 1] inputs and linear channels.  This transformation
    only rewrites the producer-owned JSON metadata and input time accessors;
    mesh, skin, animation output and all binary bounds remain unchanged.
    """
    raw = Path(path).read_bytes()
    _need(len(raw) >= 28 and struct.unpack_from("<4sII", raw) ==
          (b"glTF", 2, len(raw)), "CONTENT_NATIVE_GLB_HEADER")
    json_len, json_kind = struct.unpack_from("<II", raw, 12)
    _need(json_kind == 0x4E4F534A, "CONTENT_NATIVE_GLB_JSON")
    json_start = 20
    json_value = json.loads(raw[json_start:json_start + json_len].decode("utf-8"))
    bin_header = json_start + json_len
    bin_len, bin_kind = struct.unpack_from("<II", raw, bin_header)
    _need(bin_kind == 0x004E4942 and bin_header + 8 + bin_len == len(raw),
          "CONTENT_NATIVE_GLB_BINARY")
    binary = bytearray(raw[bin_header + 8:])
    animations = json_value.get("animations")
    _need(type(animations) is list and len(animations) == 1, "CONTENT_NATIVE_GLB_ANIMATION")
    animation = animations[0]
    animation["name"] = "walk"
    accessors = json_value.get("accessors", [])
    views = json_value.get("bufferViews", [])
    seen = set()
    for sampler in animation.get("samplers", []):
        sampler["interpolation"] = "LINEAR"
        accessor_id = sampler.get("input")
        _need(type(accessor_id) is int and 0 <= accessor_id < len(accessors),
              "CONTENT_NATIVE_GLB_INPUT")
        if accessor_id in seen:
            continue
        seen.add(accessor_id)
        accessor = accessors[accessor_id]
        _need(accessor.get("componentType") == 5126 and accessor.get("type") == "SCALAR",
              "CONTENT_NATIVE_GLB_INPUT_TYPE")
        view = views[accessor["bufferView"]]
        count = accessor["count"]
        base = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        values = [struct.unpack_from("<f", binary, base + 4 * i)[0] for i in range(count)]
        _need(count >= 2 and values[-1] > values[0], "CONTENT_NATIVE_GLB_INPUT_RANGE")
        span = values[-1] - values[0]
        for i, value in enumerate(values):
            struct.pack_into("<f", binary, base + 4 * i, (value - values[0]) / span)
        accessor["min"] = [0.0]
        accessor["max"] = [1.0]
    json_raw = json.dumps(json_value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    json_raw += b" " * ((4 - len(json_raw) % 4) % 4)
    out = bytearray(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(json_raw) + 8 + len(binary)))
    out.extend(struct.pack("<II", len(json_raw), 0x4E4F534A)); out.extend(json_raw)
    out.extend(struct.pack("<II", len(binary), 0x004E4942)); out.extend(binary)
    Path(path).write_bytes(bytes(out))


def _vec(value):
    return [float(value[0]), float(value[1]), float(value[2])]


def _cube_mesh(bpy, name):
    mesh = bpy.data.meshes.new(name + ".mesh")
    mesh.from_pydata(((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                      (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)), (),
                     ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                      (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)))
    mesh.update()
    return mesh


def _material(bpy, name, color):
    material = bpy.data.materials.new(name + ".material")
    material.use_nodes = True
    shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = 0.65
    material.diffuse_color = (*color, 1.0)
    return material


def _make_armature(bpy):
    armature = bpy.data.armatures.new("avatar.rig.data")
    obj = bpy.data.objects.new("avatar.rig", armature)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    rows = (("root", None, (0, 0, 0), (0, 0.8, 0)),
            ("spine", "root", (0, 0.8, 0), (0, 1.6, 0)),
            ("leg.l", "spine", (0, 0.8, 0), (-0.6, 0, 0)),
            ("leg.r", "spine", (0, 0.8, 0), (0.6, 0, 0)))
    created = {}
    try:
        for name, parent, head, tail in rows:
            bone = armature.edit_bones.new(name)
            bone.head = head
            bone.tail = tail
            created[name] = bone
        for name, parent, _head, _tail in rows:
            if parent is not None:
                created[name].parent = created[parent]
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def _make_avatar(bpy, armature):
    objects = []
    rows = (("torso", "spine", (0, 1.1, 0), (0.42, 0.5, 0.24), (0.9, 0.1, 0.1)),
            ("head", "spine", (0, 1.8, 0), (0.32, 0.28, 0.22), (0.1, 0.9, 0.1)),
            ("leg_left", "leg.l", (-0.3, 0.4, 0), (0.16, 0.38, 0.2), (0.1, 0.2, 0.9)),
            ("leg_right", "leg.r", (0.3, 0.4, 0), (0.16, 0.38, 0.2), (0.9, 0.8, 0.1)))
    for name, bone, location, scale, color in rows:
        mesh = _cube_mesh(bpy, name)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = location
        obj.scale = scale
        obj.parent = armature
        obj.data.materials.append(_material(bpy, name, color))
        group = obj.vertex_groups.new(name=bone)
        group.add(list(range(len(mesh.vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.new("avatar.skin", "ARMATURE")
        modifier.object = armature
        objects.append(obj)
    return objects


def _make_action(bpy, armature):
    armature.animation_data_create()
    action = bpy.data.actions.new("walk")
    armature.animation_data.action = action
    for frame, direction in ((1, -1), (13, 1), (25, -1)):
        for name, sign in (("leg.l", 1), ("leg.r", -1)):
            bone = armature.pose.bones[name]
            bone.rotation_mode = "XYZ"
            bone.rotation_euler = (0.45 * direction * sign, 0.0, 0.0)
            bone.keyframe_insert(data_path="rotation_euler", frame=frame, index=-1)
    # Blender 5.2 stores newly-created actions in layered channel bags; the
    # legacy ``action.fcurves`` collection no longer exists.  Walk the
    # immutable layer/strip/channelbag topology so the producer works against
    # the pinned binary and still forces deterministic interpolation.
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves.extend(bag.fcurves)
    _need(len(curves) == 6, "CONTENT_NATIVE_ACTION_CURVES")
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
    return action


def _make_sprite_scene(bpy, output):
    avatar_scene = bpy.context.scene
    scene = bpy.data.scenes.new("sprite.atlas")
    camera_data = bpy.data.cameras.new("sprite.camera.data")
    camera = bpy.data.objects.new("sprite.camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, 0.0, 10.0)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 4.0
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 128
    scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.show_specular_highlight = False
    scene.display.shading.show_object_outline = False
    for index, (position, color) in enumerate(zip(((-1, 1, 0), (1, 1, 0),
                                                   (-1, -1, 0), (1, -1, 0)),
                                                  ((0.9, 0.1, 0.1), (0.1, 0.9, 0.1),
                                                   (0.1, 0.2, 0.9), (0.9, 0.8, 0.1)))):
        mesh = bpy.data.meshes.new("atlas.cell.%d.mesh" % index)
        mesh.from_pydata(((-0.92, -0.92, 0), (0.92, -0.92, 0),
                          (0.92, 0.92, 0), (-0.92, 0.92, 0)), (), ((0, 1, 2, 3),))
        mesh.update()
        mesh.materials.append(_material(bpy, "atlas.cell.%d" % index, color))
        cell = bpy.data.objects.new("atlas.cell.%d" % index, mesh)
        cell.location = position
        scene.collection.objects.link(cell)
    target = output / "sprite_sheet.png"
    scene.render.filepath = str(target)
    bpy.context.window.scene = scene
    result = bpy.ops.render.render(write_still=True, scene=scene.name)
    _need(result == {"FINISHED"} and target.is_file(), "CONTENT_NATIVE_RENDER")
    image = bpy.data.images.load(str(target), check_existing=False)
    dimensions = (int(image.size[0]), int(image.size[1]), int(image.channels))
    bpy.data.images.remove(image)
    bpy.context.window.scene = avatar_scene
    return {"sha256": _sha(target), "size_bytes": target.stat().st_size,
            "dimensions": dimensions, "scene": scene.name}


def _readback(bpy, armature, action, objects):
    _need(armature.type == "ARMATURE", "CONTENT_NATIVE_ARMATURE")
    _need([bone.name for bone in armature.data.bones] == ["root", "spine", "leg.l", "leg.r"],
          "CONTENT_NATIVE_BONES")
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                curves.extend(bag.fcurves)
    _need(action.name == "walk" and len(curves) == 6, "CONTENT_NATIVE_ACTION")
    frames = sorted({float(point.co[0]) for curve in curves for point in curve.keyframe_points})
    _need(frames == [1.0, 13.0, 25.0], "CONTENT_NATIVE_KEYFRAMES")
    _need(len(objects) == 4 and all(obj.parent == armature and obj.find_armature() == armature for obj in objects),
          "CONTENT_NATIVE_SKIN_BINDING")
    return {"armature": armature.name, "bones": [bone.name for bone in armature.data.bones],
            "action": action.name, "fcurves": len(curves), "frames": frames,
            "objects": [obj.name for obj in objects], "main_thread": True, "public_ack": False}


def produce(output, recipe_sha256):
    import bpy
    _need(not bpy.app.background and tuple(bpy.app.version[:2]) == (5, 2), "CONTENT_NATIVE_PIN")
    _need(len(bpy.context.window_manager.windows) == 1 and bpy.context.window is not None,
          "CONTENT_NATIVE_WINDOW")
    output = Path(output).absolute()
    _need(output.is_dir() and not any(output.iterdir()), "CONTENT_NATIVE_OUTPUT")
    # Factory startup is the only admitted source. Delete default objects and
    # prove no linked libraries/images/scripts are inherited.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for datablocks in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                       bpy.data.materials, bpy.data.images, bpy.data.libraries):
        for value in list(datablocks):
            datablocks.remove(value)
    _need(not bpy.data.libraries and not bpy.data.images, "CONTENT_NATIVE_DEPENDENCY")
    avatar_scene = bpy.context.scene
    avatar_scene.name = "avatar.scene"
    avatar_scene.frame_start, avatar_scene.frame_end = 1, 25
    avatar_scene.render.fps = 24
    armature = _make_armature(bpy)
    objects = _make_avatar(bpy, armature)
    action = _make_action(bpy, armature)
    before = _readback(bpy, armature, action, objects)
    sprite = _make_sprite_scene(bpy, output)
    bpy.context.window.scene = avatar_scene
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    armature.select_set(True)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    glb = output / "scene.glb"
    result = bpy.ops.export_scene.gltf(
        filepath=str(glb), export_format="GLB", export_materials="EXPORT",
        export_animations=True, export_skins=True, export_morph=False,
        export_cameras=False, export_lights=False, export_extras=False,
        export_attributes=False, export_yup=True, export_normals=True,
        export_tangents=False, use_selection=True, use_active_scene=True,
        export_animation_mode="ACTIVE_ACTIONS", export_frame_range=True,
        export_force_sampling=True, export_bake_animation=True,
        export_def_bones=False, will_save_settings=False)
    _need(result == {"FINISHED"} and glb.is_file() and glb.stat().st_size <= 1024 * 1024,
          "CONTENT_NATIVE_EXPORT")
    _normalize_glb(glb)
    checkpoint = output / "checkpoint.blend"
    _need(bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint)) == {"FINISHED"}
          and checkpoint.is_file(), "CONTENT_NATIVE_SAVE")
    # Reopen the exact checkpoint before reporting. This catches non-durable
    # RNA-only claims and ensures the handoff is based on saved source.
    _need(bpy.ops.wm.open_mainfile(filepath=str(checkpoint), load_ui=False, use_scripts=False) == {"FINISHED"},
          "CONTENT_NATIVE_REOPEN")
    reopened_armature = bpy.data.objects.get("avatar.rig")
    reopened_action = reopened_armature.animation_data.action if reopened_armature and reopened_armature.animation_data else None
    reopened_objects = [bpy.data.objects.get(name) for name in ("torso", "head", "leg_left", "leg_right")]
    _need(reopened_armature is not None and reopened_action is not None and all(reopened_objects),
          "CONTENT_NATIVE_REOPEN_OBJECTS")
    after = _readback(bpy, reopened_armature, reopened_action, reopened_objects)
    transcript = {"schema": "HH-BLENDER-CONTENT-TRANSCRIPT-1", "profile": "hh-blender-gt09-fixture-content-1",
                  "recipe_sha256": recipe_sha256, "before": before, "after_reload": after,
                  "sprite": sprite, "glb_sha256": _sha(glb), "checkpoint_sha256": _sha(checkpoint),
                  "main_thread": True, "public_ack": False, "native_finished": True}
    (output / "transcript.json").write_text(json.dumps(transcript, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return transcript


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--recipe-sha256", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    transcript = produce(Path(args.output), args.recipe_sha256)
    print("HH_CONTENT_NATIVE_COMPLETE " + json.dumps(transcript, sort_keys=True), flush=True)
    # The host owns the GUI process and requires a real child exit receipt.
    # ``wm.quit_blender`` performs a lengthy GUI recovery save on this pinned
    # Windows build (well beyond the bounded Job wall), after all durable
    # artifacts have already been written.  Flush the transcript and terminate
    # this dedicated factory process directly; no user document or shared GUI
    # state is in scope for this producer.
    import os
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
