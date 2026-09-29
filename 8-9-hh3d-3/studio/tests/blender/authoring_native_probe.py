"""Disposable O2 Blender authoring probe.

This is diagnostic evidence only. It uses Blender's native bpy API in a
factory-startup process, but never enables the authoring profile or emits an
application ACK. All writes are confined to the supplied disposable output
directory.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import threading

import bpy


SCHEMA = "hh-o2-blender-native-observation-1"


@contextmanager
def _undo_context():
    """Resolve a real UI context for Blender's native history operators."""
    windows = list(bpy.context.window_manager.windows)
    if len(windows) != 1:
        raise RuntimeError("ONE_NATIVE_WINDOW_REQUIRED")
    window = windows[0]
    areas = [area for area in window.screen.areas if area.type == "VIEW_3D"]
    if not areas:
        raise RuntimeError("VIEW_3D_CONTEXT_REQUIRED")
    area = areas[0]
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None:
        raise RuntimeError("WINDOW_REGION_REQUIRED")
    with bpy.context.temp_override(window=window, area=area, region=region):
        yield


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vec(value) -> list[float]:
    return [float(value[0]), float(value[1]), float(value[2])]


def _curves(obj: bpy.types.Object, action: bpy.types.Action | None) -> list:
    if action is None or obj.animation_data is None:
        return []
    try:
        from io_scene_gltf2.blender.com.data_path import get_channelbag_for_slot
        slot = obj.animation_data.action_slot
        bag = get_channelbag_for_slot(action, slot)
        return list(bag.fcurves) if bag is not None else []
    except (ImportError, AttributeError):
        return []


def _snapshot(obj: bpy.types.Object, action: bpy.types.Action | None) -> dict:
    armature = obj.data
    bones = []
    for bone in armature.bones:
        bones.append({
            "name": bone.name,
            "parent": bone.parent.name if bone.parent else None,
            "head": _vec(bone.head_local),
            "tail": _vec(bone.tail_local),
        })
    fcurves = []
    if action is not None:
        for curve in _curves(obj, action):
            fcurves.append({
                "path": curve.data_path,
                "index": curve.array_index,
                "frames": [float(point.co[0]) for point in curve.keyframe_points],
                "values": [float(point.co[1]) for point in curve.keyframe_points],
            })
    return {"object": obj.name, "bones": bones, "fcurves": fcurves}


def _mesh_snapshot(obj: bpy.types.Object) -> dict:
    mesh = obj.data
    material = mesh.materials[0] if mesh.materials else None
    shader = (next((node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
              if material else None)
    base_color = (list(shader.inputs["Base Color"].default_value)
                  if shader is not None else None)
    return {
        "object": obj.name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "uv_layers": [layer.name for layer in mesh.uv_layers],
        "material": material.name if material else None,
        "base_color": [float(value) for value in base_color] if base_color is not None else None,
    }


def _create_mesh_asset(output: Path, rows: list[dict], failures: list[str]) -> dict:
    """Create a small authored quad and export it through Blender's GLB exporter."""
    mesh = bpy.data.meshes.new("O2_AvatarQuadMesh")
    mesh.from_pydata(((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0),
                     (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0)), (), ((0, 1, 2, 3),))
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        uv.data[loop.index].uv = ((0.0, 0.0), (1.0, 0.0),
                                  (1.0, 1.0), (0.0, 1.0))[loop.vertex_index]
    material = bpy.data.materials.new("O2_AvatarMaterial")
    shader = next(node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = (0.2, 0.55, 0.9, 1.0)
    shader.inputs["Roughness"].default_value = 0.65
    mesh.materials.append(material)
    obj = bpy.data.objects.new("O2_AvatarQuad", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    observed = _mesh_snapshot(obj)
    _check(rows, failures, "mesh_geometry_readback",
           observed["vertices"] == 4 and observed["polygons"] == 1, observed=observed)
    _check(rows, failures, "mesh_uv_readback", observed["uv_layers"] == ["UVMap"], observed=observed)
    _check(rows, failures, "mesh_material_readback",
           observed["material"] == "O2_AvatarMaterial"
           and all(abs(a - b) < 1e-5 for a, b in zip(observed["base_color"], (0.2, 0.55, 0.9, 1.0))),
           observed=observed)
    target = output / "avatar.glb"
    with _undo_context():
        result = bpy.ops.export_scene.gltf(
            filepath=str(target), export_format="GLB", export_materials="EXPORT",
            export_animations=False, export_skins=False, export_morph=False,
            export_cameras=False, export_lights=False, export_extras=False,
            export_attributes=False, will_save_settings=False, use_selection=True,
            export_yup=True, export_normals=True, export_tangents=False)
    _check(rows, failures, "glb_export_readback",
           result == {"FINISHED"} and target.is_file() and 0 < target.stat().st_size <= 4 * 1024 * 1024,
           result=sorted(result), size_bytes=target.stat().st_size if target.is_file() else None)
    return {"snapshot": observed, "sha256": _sha(target), "size_bytes": target.stat().st_size}


def _load_catalog(source_root: Path) -> dict:
    path = source_root / "contracts" / "blender-authoring-schema-v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    return document["x-candidate"]


def _check(rows: list[dict], failures: list[str], label: str, passed: bool, **detail) -> None:
    row = {"label": label, "passed": passed is True}
    if detail:
        row.update(detail)
    rows.append(row)
    print("O2_BLENDER_CHECK " + json.dumps(row, sort_keys=True), flush=True)
    if passed is not True:
        failures.append(label)


def _create_authoring(template: dict, rows: list[dict], failures: list[str]):
    """Create the complete armature/action as one native atomic operator."""
    class O2_OT_create_authoring(bpy.types.Operator):
        bl_idname = "o2_native.create_authoring"
        bl_label = "O2 native authoring create"
        bl_options = {"REGISTER", "UNDO", "INTERNAL"}

        def execute(self, context):
            armature = bpy.data.armatures.new("O2_TemplateArmatureData")
            obj = bpy.data.objects.new("O2_TemplateArmature", armature)
            bpy.context.scene.collection.objects.link(obj)
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            edit_bones = armature.edit_bones
            created = {}
            try:
                for row in template["bones"]:
                    bone = edit_bones.new(row["bone_id"])
                    bone.head = row["head"]
                    bone.tail = row["tail"]
                    created[row["bone_id"]] = bone
                for row in template["bones"]:
                    parent = row["parent_id"]
                    if parent is not None:
                        created[row["bone_id"]].parent = created[parent]
            finally:
                bpy.ops.object.mode_set(mode="OBJECT")
            obj.animation_data_create()
            action = bpy.data.actions.new("O2_TemplateAction")
            obj.animation_data.action = action
            pose = obj.pose.bones["spine"]
            pose.rotation_mode = "XYZ"
            pose.rotation_euler = (0.0, 0.0, 0.0)
            pose.keyframe_insert(data_path="rotation_euler", frame=1, index=-1)
            pose.rotation_euler = (0.0, 0.0, 0.75)
            pose.keyframe_insert(data_path="rotation_euler", frame=12, index=-1)
            return {"FINISHED"}

    bpy.utils.register_class(O2_OT_create_authoring)
    try:
        with _undo_context():
            # Explicit EXEC_DEFAULT + undo flag mirrors the trusted GT04 UI
            # owner; omitting the second argument can skip Blender history.
            result = bpy.ops.o2_native.create_authoring("EXEC_DEFAULT", True)
        if result != {"FINISHED"}:
            raise RuntimeError("AUTHORING_OPERATOR_INCOMPLETE")
        obj = bpy.data.objects.get("O2_TemplateArmature")
        if obj is None or obj.animation_data is None or obj.animation_data.action is None:
            raise RuntimeError("AUTHORING_OBJECT_OR_ACTION_MISSING")
    except BaseException:
        bpy.utils.unregister_class(O2_OT_create_authoring)
        raise
    armature = obj.data
    names = [bone.name for bone in armature.bones]
    _check(rows, failures, "template_native_construct", obj.type == "ARMATURE")
    _check(rows, failures, "template_bone_names_readback",
           names == [row["bone_id"] for row in template["bones"]], observed=names)
    expected_parent = {row["bone_id"]: row["parent_id"] for row in template["bones"]}
    observed_parent = {bone.name: bone.parent.name if bone.parent else None for bone in armature.bones}
    _check(rows, failures, "template_parent_readback", observed_parent == expected_parent,
           expected=expected_parent, observed=observed_parent)
    expected_heads = {row["bone_id"]: [float(x) for x in row["head"]] for row in template["bones"]}
    observed_heads = {bone.name: _vec(bone.head_local) for bone in armature.bones}
    _check(rows, failures, "template_geometry_readback",
           all(abs(observed_heads[name][axis] - expected_heads[name][axis]) < 1e-5
               for name in expected_heads for axis in range(3)),
           expected=expected_heads, observed=observed_heads)
    action = obj.animation_data.action
    curves = _curves(obj, action)
    frames = sorted({float(point.co[0]) for curve in curves for point in curve.keyframe_points})
    _check(rows, failures, "action_native_construct", obj.animation_data.action == action)
    _check(rows, failures, "action_keyframe_readback", len(curves) == 3 and frames == [1.0, 12.0],
           curve_count=len(curves), frames=frames)
    # Keep the operator registered through undo/redo; Blender's redo replays
    # the operator identity even though the object is restored from history.
    return obj, action, O2_OT_create_authoring


def _run_authoring(output: Path, source_root: Path) -> dict:
    rows: list[dict] = []
    failures: list[str] = []
    _check(rows, failures, "actual_blender", (not bpy.app.background) and tuple(bpy.app.version[:2]) == (5, 2))
    _check(rows, failures, "main_thread", threading.current_thread() is threading.main_thread())
    _check(rows, failures, "native_window_context", len(bpy.context.window_manager.windows) == 1)
    # Factory startup may materialize Blender's default camera/light/cube;
    # remove only those disposable datablocks before establishing our baseline.
    for value in list(bpy.data.objects):
        bpy.data.objects.remove(value, do_unlink=True)
    _check(rows, failures, "factory_scene_empty", len(bpy.data.objects) == 0)
    with _undo_context():
        baseline_pushed = bpy.ops.ed.undo_push(message="O2 empty authoring baseline") == {"FINISHED"}
    _check(rows, failures, "native_undo_baseline", baseline_pushed)
    catalog = _load_catalog(source_root)
    template = catalog["templates"][0]
    obj, action, operator_type = _create_authoring(template, rows, failures)
    before = _snapshot(obj, action)

    # The complete armature/action create is one native operator transaction;
    # undo removes that transaction and redo restores it from Blender history.
    undo_ok = False
    redo_ok = False
    try:
        with _undo_context():
            _check(rows, failures, "native_undo_available", bpy.ops.ed.undo.poll())
        with _undo_context():
            undone = bpy.ops.ed.undo() == {"FINISHED"}
        after_undo_names = sorted(obj.name for obj in bpy.data.objects)
        _check(rows, failures, "native_undo_state_readback", undone and "O2_TemplateArmature" not in after_undo_names,
               observed=after_undo_names)
        undo_ok = undone and bpy.data.objects.get("O2_TemplateArmature") is None
        with _undo_context():
            _check(rows, failures, "native_redo_available", bpy.ops.ed.redo.poll())
            redone = bpy.ops.ed.redo() == {"FINISHED"}
        after_redo_names = sorted(obj.name for obj in bpy.data.objects)
        _check(rows, failures, "native_redo_state_readback", redone and "O2_TemplateArmature" in after_redo_names,
               observed=after_redo_names)
        restored = bpy.data.objects.get("O2_TemplateArmature")
        restored_action = restored.animation_data.action if restored and restored.animation_data else None
        after_redo = _snapshot(restored, restored_action) if restored and restored_action else None
        redo_ok = redone and after_redo == before
        obj, action = restored, restored_action
    except Exception as exc:  # pragma: no cover - native diagnostic detail
        _check(rows, failures, "undo_exception_absent", False, error=type(exc).__name__ + ": " + str(exc))
    finally:
        try:
            bpy.utils.unregister_class(operator_type)
        except RuntimeError:
            pass
    _check(rows, failures, "native_undo_readback", undo_ok)
    _check(rows, failures, "native_redo_readback", redo_ok)

    asset = _create_mesh_asset(output, rows, failures)

    checkpoint = output / "checkpoint.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint))
    _check(rows, failures, "checkpoint_under_output", checkpoint.is_file() and checkpoint.parent == output)
    expected = {"snapshot": _snapshot(obj, action), "asset": asset,
                "sha256": _sha(checkpoint), "template_id": template["template_id"]}
    (output / "expected.json").write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    report = {"schema": SCHEMA, "actual_blender": True, "version": "5.2.1",
              "runtime_authorized": False, "native_mutation": True, "formal_acceptance": False,
              "checks": rows, "failures": failures, "snapshot": expected["snapshot"],
              "checkpoint_sha256": expected["sha256"], "source_root": source_root.as_posix(),
              "output_root": output.as_posix()}
    (output / "native.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    bpy.ops.wm.quit_blender()
    return report


def _run_reopen(output: Path) -> int:
    expected = json.loads((output / "expected.json").read_text(encoding="utf-8"))
    checkpoint = output / "checkpoint.blend"
    if _sha(checkpoint) != expected["sha256"]:
        raise RuntimeError("checkpoint_hash_changed")
    if bpy.ops.wm.open_mainfile(filepath=str(checkpoint), load_ui=False, use_scripts=False) != {"FINISHED"}:
        raise RuntimeError("reopen_failed")
    obj = bpy.data.objects.get("O2_TemplateArmature")
    observed = _snapshot(obj, obj.animation_data.action if obj and obj.animation_data else None)
    asset_obj = bpy.data.objects.get("O2_AvatarQuad")
    observed_asset = _mesh_snapshot(asset_obj) if asset_obj else None
    asset_path = output / "avatar.glb"
    asset_ok = (asset_obj is not None and observed_asset == expected["asset"]["snapshot"]
                and asset_path.is_file() and _sha(asset_path) == expected["asset"]["sha256"])
    report = {"schema": SCHEMA, "actual_blender": True, "version": "5.2.1",
              "runtime_authorized": False, "formal_acceptance": False,
              "reopened": observed == expected["snapshot"] and asset_ok, "observed": observed,
              "expected": expected["snapshot"], "asset_reopened": asset_ok,
              "asset_observed": observed_asset}
    (output / "reopen.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                         encoding="utf-8")
    print("O2_BLENDER_REOPEN " + json.dumps(report, sort_keys=True), flush=True)
    bpy.ops.wm.quit_blender()
    return 0 if report["reopened"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reopen", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else None)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    def callback():
        try:
            if args.reopen:
                _run_reopen(output)
            else:
                report = _run_authoring(output, args.source_root.resolve())
                print("O2_BLENDER_COMPLETE " + json.dumps({"passed": not report["failures"],
                                                           "checks": len(report["checks"])}, sort_keys=True), flush=True)
        except BaseException as exc:
            (output / "probe-exception.txt").write_text(
                type(exc).__name__ + ": " + str(exc) + "\n", encoding="utf-8")
            print("O2_BLENDER_EXCEPTION " + type(exc).__name__ + ": " + str(exc), flush=True)
            bpy.ops.wm.quit_blender()
        return None

    # Blender's editor history operators require the fully initialized window
    # event loop; the timer is the same main-thread boundary used by GT04 UI.
    bpy.app.timers.register(callback, first_interval=0.20, persistent=False)
    return 0


if __name__ == "__main__":
    main()
