"""Static fail-closed tests for the O2 PackedScene instance candidate."""
from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("o2_scene_instance", STUDIO / "godot-addon/scene_instance.py")
scene = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scene
SPEC.loader.exec_module(scene)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class SceneInstanceTests(unittest.TestCase):
    def setUp(self):
        self.context = scene.ValidationContext(
            "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
            4, "lease.fixture", 9, 31000, 1000,
            (scene.NodeState("root", None, "Node2D", "Root"),
             scene.NodeState("platforms", "root", "Node2D", "Platforms")),
            (scene.SceneSourceState("arena", "scenes/arena.tscn", "sha256:" + "3" * 64, "Node2D"),))

    def request(self, operation="scene.instance.create", *, payload=None, target=None, context=None):
        context = context or self.context
        payload = copy.deepcopy(payload or {
            "scene_id": "arena", "instance_stable_id": "arena_01", "instance_name": "Arena01",
            "position": [10, 20], "rotation_degrees": [0], "scale": [1, 1],
        })
        payload.setdefault("expected_generation", context.generation)
        payload.setdefault("expected_project_revision", context.project_revision)
        return Request(command_id="instance.fixture", project_id=context.project_id,
                       operation=operation, lease_id=context.lease_id,
                       fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
                       target=target or {"stable_id": "root"}, payload=payload,
                       payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                       deadline_ms=2000)

    def validate(self, request=None, context=None):
        return scene.validate_request(request or self.request(), context or self.context)

    def reject(self, request, code=None, *, context=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context)
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_create_2d_projection_is_detached_and_authority_zero(self):
        result = self.validate()
        self.assertEqual(result.projection["source_revision"], "sha256:" + "3" * 64)
        self.assertEqual(result.preview["source_path"], "scenes/arena.tscn")
        projection = result.projection
        projection["payload"]["position"][0] = 999
        self.assertEqual(result.projection["payload"]["position"], [10, 20])
        self.assertEqual(result.preview["authority"], 0)
        self.assertFalse(result.preview["changes_applied"])

    def test_create_3d_uses_3d_parent_and_transform(self):
        context = replace(self.context,
                          nodes=(scene.NodeState("root", None, "Node3D", "Root"),),
                          scenes=(scene.SceneSourceState("room", "scenes/room.tscn", "sha256:" + "4" * 64, "Node3D"),))
        request = self.request(payload={"scene_id": "room", "instance_stable_id": "room_01",
            "instance_name": "Room01", "position": [1, 2, 3], "rotation_degrees": [0, 90, 0],
            "scale": [1, 1, 1]}, context=context)
        self.assertEqual(self.validate(request, context).projection["scene_id"], "room")

    def test_remove_binds_existing_instance_and_source_revision(self):
        instance = scene.InstanceState("arena_01", "arena", "root", "Arena01", "sha256:" + "3" * 64)
        context = replace(self.context, instances=(instance,))
        request = self.request("scene.instance.remove", payload={"instance_stable_id": "arena_01"},
                               target={"stable_id": "arena_01"}, context=context)
        self.assertEqual(self.validate(request, context).projection["parent_stable_id"], "root")
        wrong_target = self.request("scene.instance.remove", payload={"instance_stable_id": "arena_01"},
                                    target={"stable_id": "root"}, context=context)
        self.reject(wrong_target, "INSTANCE_TARGET", context=context)

    def test_rejects_path_traversal_external_path_and_unknown_scene(self):
        for path in ("../arena.tscn", "scenes/../arena.tscn", "res://scenes/arena.tscn", "scenes/arena.glb"):
            context = replace(self.context, scenes=(scene.SceneSourceState("arena", path,
                "sha256:" + "3" * 64, "Node2D"),))
            self.reject(self.request(context=context), "INSTANCE_SCENE_STATE", context=context)
        self.reject(self.request(payload={"scene_id": "missing", "instance_stable_id": "x",
            "instance_name": "X", "position": [0, 0], "rotation_degrees": [0], "scale": [1, 1]}),
                    "INSTANCE_SCENE_UNKNOWN")

    def test_rejects_wrong_parent_transform_duplicate_and_unknown_fields(self):
        context = replace(self.context, nodes=(scene.NodeState("root", None, "Node3D", "Root"),))
        self.reject(self.request(context=context), "INSTANCE_PARENT_TYPE", context=context)
        bad = self.request(payload={"scene_id": "arena", "instance_stable_id": "x", "instance_name": "X",
            "position": [0, 0], "rotation_degrees": [0, 0], "scale": [1, 1]})
        self.reject(bad, "INSTANCE_TRANSFORM")
        existing = scene.InstanceState("arena_01", "arena", "root", "Arena01", "sha256:" + "3" * 64)
        self.reject(self.request(context=replace(self.context, instances=(existing,))), "INSTANCE_DUPLICATE_ID",
                    context=replace(self.context, instances=(existing,)))
        extra = self.request()
        extra.payload["unknown"] = True
        extra = replace(extra, payload_hash="sha256:" + hashlib.sha256(canonical_bytes(extra.payload)).hexdigest())
        self.reject(extra, "INSTANCE_CREATE_SHAPE")

    def test_rejects_stale_lease_revision_generation_deadline_and_stop(self):
        cases = [(replace(self.context, stopped=True), "INSTANCE_STOPPED"),
                 (replace(self.context, generation=5), "INSTANCE_STALE_GENERATION"),
                 (replace(self.context, revision="sha256:" + "5" * 64), "INSTANCE_STALE_REVISION"),
                 (replace(self.context, fencing_epoch=10), "INSTANCE_STALE_LEASE"),
                 (replace(self.context, lease_expires_ms=1500), "INSTANCE_DEADLINE")]
        for context, code in cases:
            with self.subTest(code=code):
                self.reject(self.request(), code, context=context)


if __name__ == "__main__":
    unittest.main()
