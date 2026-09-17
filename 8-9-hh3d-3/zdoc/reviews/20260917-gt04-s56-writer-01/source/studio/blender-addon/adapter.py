"""Main-thread, trusted-background fixture adapter. No public ACK or IPC."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import threading

_path = Path(__file__).with_name("contract.py")
_spec = importlib.util.spec_from_file_location("_gt04_contract_" + hashlib.sha256(_path.read_bytes()).hexdigest(), _path)
contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(contract)
Rejected = contract.Rejected
_material_path=Path(__file__).with_name('material_profile.py')
_material_spec=importlib.util.spec_from_file_location('_gt04_material_profile',_material_path)
materials=importlib.util.module_from_spec(_material_spec);_material_spec.loader.exec_module(materials)
STABLE_ID = "hh_gt04_id"
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def main_thread():
    # This test MUST precede importing or reading bpy on every entry point.
    if threading.current_thread() is not threading.main_thread():
        raise Rejected("MAIN_THREAD_REQUIRED")


class FixtureAdapter:
    def __init__(self):
        main_thread()
        import bpy
        if bpy.app.version[:3] != (5, 2, 1) or not bpy.app.background:
            raise Rejected("PINNED_BACKGROUND_FIXTURE_REQUIRED")
        self.bpy = bpy
        self._commands = {}
        self._held = False
        self._stopped = False
        self.inspect()

    def _guard(self):
        main_thread()
        if self._held:
            raise Rejected("OWNER_HELD")

    def _objects(self):
        bpy = self.bpy
        if (len(bpy.data.scenes) != 1 or len(bpy.data.objects) > contract.MAX_OBJECTS or
                bpy.data.libraries or bpy.data.texts or bpy.data.node_groups or
                bpy.data.actions or bpy.data.images or bpy.data.worlds):
            raise Rejected("UNSUPPORTED_DEPENDENCY")
        try:materials.scene_materials(bpy)
        except materials.MaterialRejected as exc:raise Rejected(str(exc)) from exc
        result = {}
        for obj in bpy.data.objects:
            stable_id = contract.identifier(obj.get(STABLE_ID))
            if (stable_id in result or obj.type != "MESH" or obj.library or obj.data.library or
                    obj.parent or obj.constraints or obj.modifiers or obj.animation_data or
                    obj.data.animation_data or obj.data.shape_keys or
                    obj.rotation_mode != "XYZ" or obj.hide_viewport or obj.hide_get() or
                    obj not in list(bpy.context.scene.objects) or len(obj.users_collection) != 1):
                raise Rejected("UNSUPPORTED_OBJECT")
            if (len(obj.data.vertices) != 8 or len(obj.data.polygons) != 6 or len(obj.data.edges) != 12 or
                    obj.data.users != 1 or obj.data.uv_layers or obj.data.color_attributes):
                raise Rejected("UNSUPPORTED_MESH")
            if (tuple(obj.delta_location) != (0.0, 0.0, 0.0) or tuple(obj.delta_rotation_euler) != (0.0, 0.0, 0.0)
                    or tuple(obj.delta_scale) != (1.0, 1.0, 1.0)):
                raise Rejected("UNSUPPORTED_DELTA_TRANSFORM")
            result[stable_id] = obj
        if len(bpy.data.meshes) != len(result):
            raise Rejected("UNOWNED_MESH")
        return result

    def _context(self, objects):
        bpy = self.bpy
        mode = bpy.context.mode
        if mode not in ("OBJECT", "EDIT_MESH"):
            raise Rejected("UNSUPPORTED_MODE")
        active = bpy.context.view_layer.objects.active
        if active is not None and active not in objects.values():
            raise Rejected("UNOWNED_ACTIVE_OBJECT")
        return {"mode": mode, "active_id": None if active is None else active[STABLE_ID],
                "selected_ids": sorted(obj[STABLE_ID] for obj in bpy.context.selected_objects)}

    def _mode(self, mode):
        bpy = self.bpy
        active = bpy.context.view_layer.objects.active
        if active is None:
            raise Rejected("ACTIVE_OBJECT_REQUIRED")
        with bpy.context.temp_override(object=active, active_object=active,
                                       selected_objects=list(bpy.context.selected_objects),
                                       selected_editable_objects=list(bpy.context.selected_objects)):
            if not bpy.ops.object.mode_set.poll():
                raise Rejected("MODE_CONTEXT_REJECTED")
            if bpy.ops.object.mode_set(mode=mode) != {"FINISHED"}:
                raise Rejected("MODE_CHANGE_FAILED")

    @contextmanager
    def _object_context(self):
        objects = self._objects()
        original = self._context(objects)
        if original["mode"] == "EDIT_MESH":
            self._mode("OBJECT")
        try:
            yield original
        finally:
            try:
                # Resolve again after mode changes; mesh RNA arrays are not cached.
                objects = self._objects()
                for obj in objects.values():
                    obj.select_set(False)
                for stable_id in original["selected_ids"]:
                    objects[stable_id].select_set(True)
                self.bpy.context.view_layer.objects.active = objects.get(original["active_id"])
                if original["mode"] == "EDIT_MESH":
                    self._mode("EDIT")
                if self._context(objects) != original:
                    raise Rejected("CONTEXT_RESTORE_FAILED")
            except BaseException:
                self._held = True
                raise

    def _snapshot(self):
        objects = self._objects()
        rows = []
        for stable_id, obj in sorted(objects.items()):
            row = {"object_id": stable_id, "name": obj.name, "mesh_name": obj.data.name,
                   "location": list(obj.location), "rotation": list(obj.rotation_euler), "scale": list(obj.scale),
                   "vertices": [list(vertex.co) for vertex in obj.data.vertices],
                   "faces": [list(poly.vertices) for poly in obj.data.polygons]}
            numbers = row["location"] + row["rotation"] + row["scale"] + [x for v in row["vertices"] for x in v]
            if any(not math.isfinite(x) for x in numbers):
                raise Rejected("NONFINITE_NATIVE_STATE")
            if obj.data.materials:row['material']=materials.inspect_material(obj.data.materials[0])
            rows.append(row)
        units = self.bpy.context.scene.unit_settings
        return {"schema": "HH-BLENDER-FIXTURE-SCENE-1", "objects": rows,
                "units": {"system": units.system, "scale_length": units.scale_length}}

    def inspect(self):
        self._guard()
        with self._object_context() as context:
            snapshot = self._snapshot()
        return {"revision": contract.digest(snapshot), "context": context, "snapshot": snapshot,
                "public_ack": False, "undo_supported": False}

    def stop(self):
        self._guard()
        self._stopped = True

    def execute(self, raw):
        self._guard()
        command = contract.parse(raw)
        if command["operation"] == "scene.inspect":
            return self.inspect()
        command_id = command["command_id"]
        digest = contract.digest(command)
        if command_id in self._commands:
            original_digest, receipt = self._commands[command_id]
            if digest != original_digest:
                raise Rejected("COMMAND_CONFLICT")
            return json.loads(contract.canonical(receipt))
        if self._stopped:
            raise Rejected("STOPPED")
        if len(self._commands) >= contract.MAX_COMMANDS:
            raise Rejected("COMMAND_CAPACITY")
        before = self.inspect()
        if command["expected_revision"] != before["revision"]:
            raise Rejected("STALE_REVISION")
        if command["expected_context"] != before["context"]:
            raise Rejected("CONTEXT_DRIFT")
        operation, payload = command["operation"], command["payload"]
        objects = self._objects()
        stable_id = payload["object_id"]
        if operation == "mesh.create_box" and (stable_id in objects or len(objects) >= contract.MAX_OBJECTS):
            raise Rejected("OBJECT_ID_OR_CAPACITY")
        if operation in ("object.transform.set","material.set_principled") and stable_id not in objects:
            raise Rejected("OBJECT_MISSING")
        if operation=='material.set_principled':
            target=objects[stable_id]
            if target.data.materials:
                if target.data.materials[0].get(materials.STABLE_ID)!=payload['material_id']:
                    raise Rejected('MATERIAL_ID_CONFLICT')
            elif (len(self.bpy.data.materials)>=materials.MAX_MATERIALS or
                  any(material.get(materials.STABLE_ID)==payload['material_id'] for material in self.bpy.data.materials)):
                raise Rejected('MATERIAL_ID_OR_CAPACITY')
        # After the first native effect, any unexpected exception holds the owner.
        # No retries/rollback claims are made from an uncertain partial mutation.
        try:
            with self._object_context():
                if operation == "mesh.create_box":
                    x, y, z = [v / 2.0 for v in payload["size"]]
                    vertices = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                                (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
                    mesh = self.bpy.data.meshes.new("GT04_mesh_" + stable_id)
                    mesh.from_pydata(vertices, [], FACES)
                    mesh.update()
                    obj = self.bpy.data.objects.new("GT04_" + stable_id, mesh)
                    obj[STABLE_ID] = stable_id
                    self.bpy.context.scene.collection.objects.link(obj)
                elif operation=='material.set_principled':
                    materials.apply(self.bpy,self._objects()[stable_id],payload)
                else:
                    obj = self._objects()[stable_id]
                    obj.location = payload["location"]
                    obj.rotation_euler = payload["rotation"]
                    obj.scale = payload["scale"]
                self.bpy.context.view_layer.update()
            after = self.inspect()
            row = next(row for row in after["snapshot"]["objects"] if row["object_id"] == stable_id)
            if operation == "mesh.create_box":
                if row["vertices"] != [list(v) for v in vertices] or row["faces"] != [list(v) for v in FACES]:
                    # Native vertices use binary32; compare exact rounded values.
                    import struct
                    rounded = [[struct.unpack("f", struct.pack("f", x))[0] for x in v] for v in vertices]
                    if row["vertices"] != rounded or row["faces"] != [list(v) for v in FACES]:
                        raise Rejected("CREATE_READBACK_MISMATCH")
            elif operation=='material.set_principled':
                observed=row['material']
                if (observed['material_id']!=payload['material_id'] or
                    observed['base_color']!=[materials.rounded(x) for x in payload['base_color']]+[1.0] or
                    any(observed[name]!=materials.rounded(payload[name]) for name in ('metallic','roughness'))):
                    raise Rejected('MATERIAL_READBACK_MISMATCH')
            else:
                import struct
                for field in ("location", "rotation", "scale"):
                    rounded = [struct.unpack("f", struct.pack("f", x))[0] for x in payload[field]]
                    if row[field] != rounded:
                        raise Rejected("TRANSFORM_READBACK_MISMATCH")
            if after["context"] != before["context"]:
                raise Rejected("CONTEXT_RESTORE_MISMATCH")
            receipt = {"command_id": command_id, "command_digest": digest, "operation": operation,
                       "before_revision": before["revision"], "after": after, "public_ack": False,
                       "status": "INTERNAL_READBACK", "durable_dedupe": False}
            self._commands[command_id] = (digest, receipt)
            return json.loads(contract.canonical(receipt))
        except BaseException:
            self._held = True
            raise
