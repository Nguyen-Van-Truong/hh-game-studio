"""Static fail-closed tests for the O2 AnimationPlayer candidate."""
from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("o2_animation_authoring", STUDIO / "godot-addon/animation_authoring.py")
animation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = animation
SPEC.loader.exec_module(animation)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class AnimationAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.context = animation.ValidationContext(
            "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
            4, "lease.fixture", 9, 31000, 1000,
            (animation.NodeState("root", None, "Node2D", "Root"),
             animation.NodeState("actor", "root", "Node2D", "Actor"),
             animation.NodeState("player", "root", "AnimationPlayer", "Player")))

    def request(self, operation="scene.animation.create", *, payload=None, target=None, context=None):
        context = context or self.context
        payload = copy.deepcopy(payload or {"animation_id": "idle", "length": 1.0,
            "loop_mode": 1, "tracks": [{"node_stable_id": "actor", "property": "position",
                "keys": [[0.0, [0, 0]], [1.0, [10, 0]]]}]})
        payload.setdefault("expected_generation", context.generation)
        payload.setdefault("expected_project_revision", context.project_revision)
        return Request(command_id="animation.fixture", project_id=context.project_id,
                       operation=operation, lease_id=context.lease_id,
                       fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
                       target=target or {"stable_id": "player"}, payload=payload,
                       payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                       deadline_ms=2000)

    def validate(self, request=None, context=None):
        return animation.validate_request(request or self.request(), context or self.context)

    def reject(self, request, code=None, *, context=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context)
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_create_projection_preserves_tracks_and_is_detached(self):
        result = self.validate()
        self.assertEqual(result.projection["tracks"][0]["keys"][1], [1.0, [10, 0]])
        self.assertEqual(result.preview["authority"], 0)
        projection = result.projection
        projection["tracks"][0]["keys"][0][1][0] = 99
        self.assertEqual(result.projection["tracks"][0]["keys"][0][1], [0, 0])

    def test_remove_requires_existing_animation(self):
        state = animation.AnimationState("idle", "player", 1.0, 1, ())
        context = replace(self.context, animations=(state,))
        request = self.request("scene.animation.remove", payload={"animation_id": "idle"}, context=context)
        self.assertEqual(self.validate(request, context).projection["animation_id"], "idle")
        self.reject(self.request("scene.animation.remove", payload={"animation_id": "missing"}),
                    "ANIMATION_REMOVE_SHAPE")

    def test_rejects_bad_tracks_times_vectors_duplicates_and_unknown_fields(self):
        bad = self.request(payload={"animation_id": "idle", "length": 1.0, "loop_mode": 1,
            "tracks": [{"node_stable_id": "actor", "property": "position",
                        "keys": [[0.5, [0, 0]], [0.4, [1, 1]]]}]})
        self.reject(bad, "ANIMATION_KEY_SHAPE")
        for prop in ("unknown", "position"):
            payload = {"animation_id": "idle", "length": 1.0, "loop_mode": 1,
                       "tracks": [{"node_stable_id": "actor", "property": prop,
                                   "keys": [[0.0, [0, 0]], [1.0, [1, 1, 1]]]}]}
            if prop == "unknown":
                self.reject(self.request(payload=payload), "ANIMATION_TRACK_TARGET")
            else:
                self.reject(self.request(payload=payload), "ANIMATION_KEY_SHAPE")
        duplicate = {"animation_id": "idle", "length": 1.0, "loop_mode": 1,
            "tracks": [{"node_stable_id": "actor", "property": "position", "keys": [[0.0, [0, 0]]] },
                        {"node_stable_id": "actor", "property": "position", "keys": [[1.0, [1, 1]]]}]}
        self.reject(self.request(payload=duplicate), "ANIMATION_DUPLICATE_TRACK")
        extra = self.request()
        payload = extra.payload | {"extra": True}
        extra = replace(extra, payload=payload,
                        payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest())
        self.reject(extra, "ANIMATION_CREATE_SHAPE")

    def test_rejects_duplicate_id_target_and_stale_context(self):
        state = animation.AnimationState("idle", "player", 1.0, 1, ())
        context = replace(self.context, animations=(state,))
        self.reject(self.request(context=context), "ANIMATION_PROPERTIES", context=context)
        self.reject(self.request(target={"stable_id": "actor"}), "ANIMATION_TARGET_TYPE")
        for stale, code in ((replace(self.context, generation=5), "ANIMATION_STALE_GENERATION"),
                            (replace(self.context, stopped=True), "ANIMATION_STOPPED"),
                            (replace(self.context, revision="sha256:" + "5" * 64), "ANIMATION_STALE_REVISION")):
            self.reject(self.request(), code, context=stale)

    def track_request(self, property_name, values, *, node="actor", context=None):
        return self.request(context=context, payload={"animation_id": "clip", "length": 2,
            "loop_mode": 0, "tracks": [{"node_stable_id": node, "property": property_name,
                                       "keys": [[0, values[0]], [2, values[1]]]}]})

    def test_rotation_types_match_native_domains_and_scale_stays_positive(self):
        result = self.validate(self.track_request("rotation_degrees", (0, 45)))
        self.assertEqual(result.projection["tracks"][0]["keys"], [[0, 0], [2, 45]])
        self.reject(self.track_request("rotation_degrees", ([0, 0], [45, 0])), "ANIMATION_KEY_SHAPE")
        context = replace(self.context, nodes=self.context.nodes + (
            animation.NodeState("actor3d", "root", "Node3D", "Actor3D"),))
        result = self.validate(self.track_request("rotation_degrees", ([0, 0, 0], [0, 45, 0]),
            node="actor3d", context=context), context)
        self.assertEqual(result.projection["tracks"][0]["node_type"], "Node3D")
        for values in (([0, 1], [1, 1]), ([-1, 1], [1, 1])):
            self.reject(self.track_request("scale", values), "ANIMATION_KEY_SHAPE")

    def test_unknown_property_types_and_nontransform_nodes_reject(self):
        for property_name in ([], {}, True, "script", "../position"):
            self.reject(self.track_request(property_name, ([0, 0], [1, 1])), "ANIMATION_TRACK_TARGET")
        self.reject(self.track_request("position", ([0, 0, 0], [1, 1, 1]), node="player"),
                    "ANIMATION_TRACK_TARGET")

    def test_remove_rejects_foreign_player(self):
        context = replace(self.context, nodes=self.context.nodes + (
            animation.NodeState("other", "root", "AnimationPlayer", "Other"),),
            animations=(animation.AnimationState("idle", "player", 1, 0, ()),))
        self.reject(self.request("scene.animation.remove", context=context,
            payload={"animation_id": "idle"}, target={"stable_id": "other"}),
            "ANIMATION_OWNER_MISMATCH", context=context)

    def test_rejects_invalid_tree_and_derives_track_paths_from_trusted_nodes(self):
        bad_nodes = [
            self.context.nodes + (animation.NodeState("orphan", "missing", "Node2D", "Orphan"),),
            self.context.nodes + (animation.NodeState("loop", "loop", "Node2D", "Loop"),),
            self.context.nodes + (animation.NodeState("secondroot", None, "Node2D", "Second"),),
        ]
        for nodes in bad_nodes:
            context = replace(self.context, nodes=nodes)
            self.reject(self.request(), "ANIMATION_HIERARCHY", context=context)
        context = replace(self.context, nodes=self.context.nodes + (
            animation.NodeState("hand", "actor", "Node2D", "Hand"),))
        result = self.validate(self.track_request("position", ([0, 0], [1, 1]),
            node="hand", context=context), context)
        self.assertEqual(result.projection["tracks"][0]["node_path"], "Actor/Hand")

    def test_observed_tracks_must_have_closed_immutable_typed_keys(self):
        track = animation.AnimationTrackState("actor", "rotation_degrees", ((0, 0), (1, 90)))
        state = animation.AnimationState("idle", "player", 1, 0, (track,))
        context = replace(self.context, animations=(state,))
        self.validate(self.request("scene.animation.remove", context=context, payload={"animation_id": "idle"}), context)
        for tracks in ([track], (replace(track, keys=([0, 0],)),), (replace(track, property=[]),)):
            malformed = replace(context, animations=(replace(state, tracks=tracks),))
            self.reject(self.request(), context=malformed)

    def test_binding_carries_both_revisions_and_rejects_stale_project(self):
        projection = self.validate().projection
        self.assertEqual(projection["project_revision"], self.context.project_revision)
        self.assertEqual(projection["scene_revision"], self.context.revision)
        self.assertFalse(projection["runtime_authorized"])
        self.assertFalse(projection["changes_applied"])
        self.reject(self.request(), "ANIMATION_STALE_PROJECT_REVISION",
                    context=replace(self.context, project_revision="sha256:" + "8" * 64))


if __name__ == "__main__":
    unittest.main()
