"""Static fail-closed tests for declarative gameplay behavior."""
from dataclasses import replace
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("o2_gameplay_behavior", STUDIO / "godot-addon/gameplay_behavior.py")
behavior = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = behavior
SPEC.loader.exec_module(behavior)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class GameplayBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.context = behavior.ValidationContext(
            "project.fixture", "sha256:" + "1" * 64, "sha256:" + "2" * 64,
            4, "lease.fixture", 9, 31000, 1000,
            (behavior.NodeState("root", "Node2D"), behavior.NodeState("actor", "CharacterBody2D")))

    def request(self, operation="scene.behavior.create", *, payload=None, target=None, context=None):
        context = context or self.context
        payload = copy.deepcopy(payload or {"behavior_id": "fighter", "states": ["idle", "run", "jump"],
            "initial_state": "idle", "transitions": [
                {"from_state": "idle", "action": "move_left", "to_state": "run",
                 "effects": [{"kind": "move", "params": {"speed": 4.0}}]},
                {"from_state": "run", "action": "jump", "to_state": "jump",
                 "effects": [{"kind": "jump", "params": {"velocity_y": -8.0}}]}]})
        payload.setdefault("expected_generation", context.generation)
        payload.setdefault("expected_project_revision", context.project_revision)
        return Request(command_id="behavior.fixture", project_id=context.project_id,
                       operation=operation, lease_id=context.lease_id,
                       fencing_epoch=context.fencing_epoch, expected_revision=context.revision,
                       target=target or {"stable_id": "actor"}, payload=payload,
                       payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                       deadline_ms=2000)

    def validate(self, request=None, context=None):
        return behavior.validate_request(request or self.request(), context or self.context)

    def reject(self, request, code=None, *, context=None):
        with self.assertRaises(ValidationError) as raised:
            self.validate(request, context)
        if code:
            self.assertEqual(raised.exception.code, code)

    def test_create_is_detached_authority_zero_and_binds_revisions(self):
        result = self.validate()
        self.assertEqual(result.projection["states"], ["idle", "run", "jump"])
        self.assertEqual(result.projection["project_revision"], self.context.project_revision)
        self.assertFalse(result.projection["runtime_authorized"])
        projection = result.projection
        projection["states"][0] = "corrupt"
        self.assertEqual(result.projection["states"][0], "idle")

    def test_remove_requires_existing_owner(self):
        state = behavior.BehaviorState("fighter", "actor", ("idle",), "idle")
        context = replace(self.context, behaviors=(state,))
        request = self.request("scene.behavior.remove", payload={"behavior_id": "fighter"}, context=context)
        self.assertEqual(self.validate(request, context).projection["behavior_id"], "fighter")
        self.reject(self.request("scene.behavior.remove", payload={"behavior_id": "missing"}),
                    "BEHAVIOR_REMOVE_SHAPE")
        self.reject(self.request("scene.behavior.remove", payload={"behavior_id": "fighter"},
                                 target={"stable_id": "root"}, context=context),
                    "BEHAVIOR_REMOVE_SHAPE", context=context)

    def test_rejects_unknown_effects_params_states_and_duplicate_transitions(self):
        base = {"behavior_id": "x", "states": ["idle", "run"], "initial_state": "idle", "transitions": []}
        for effect in ({"kind": "eval", "params": {}}, {"kind": "move", "params": {"script": 1}},
                       {"kind": "jump", "params": {"velocity_y": "fast"}}):
            payload = {**base, "transitions": [{"from_state": "idle", "action": "go", "to_state": "run",
                                                   "effects": [effect]}]}
            self.reject(self.request(payload=payload), "BEHAVIOR_EFFECT_SHAPE" if effect["kind"] == "eval" or "script" in effect["params"] else "BEHAVIOR_EFFECT_VALUE")
        duplicate = {**base, "transitions": [
            {"from_state": "idle", "action": "go", "to_state": "run", "effects": []},
            {"from_state": "idle", "action": "go", "to_state": "idle", "effects": []}]}
        self.reject(self.request(payload=duplicate), "BEHAVIOR_DUPLICATE_TRANSITION")
        for states, initial in ((["idle", "idle"], "idle"), (["idle", "bad state"], "idle"), (["idle"], "run")):
            self.reject(self.request(payload={**base, "states": states, "initial_state": initial}), "BEHAVIOR_STATES")

    def test_rejects_arbitrary_code_paths_and_stale_context(self):
        payload = {"behavior_id": "x", "states": ["idle"], "initial_state": "idle",
                   "transitions": [{"from_state": "idle", "action": "go", "to_state": "idle",
                                    "effects": [{"kind": "emit_signal", "params": {"signal": "../x"}}]}]}
        self.reject(self.request(payload=payload), "BEHAVIOR_EFFECT_VALUE")
        payload = {"behavior_id": "x", "states": ["idle"], "initial_state": "idle",
                   "transitions": [{"from_state": "idle", "action": "go", "to_state": "idle",
                                    "effects": [{"kind": "play_animation", "params": {"animation": "run"}}]}]}
        self.assertEqual(self.validate(self.request(payload=payload)).projection["transitions"][0]["effects"][0]["params"], {"animation": "run"})
        for context, code in ((replace(self.context, generation=5), "BEHAVIOR_STALE_GENERATION"),
                              (replace(self.context, stopped=True), "BEHAVIOR_STOPPED"),
                              (replace(self.context, project_revision="sha256:" + "8" * 64), "BEHAVIOR_STALE_PROJECT_REVISION")):
            self.reject(self.request(), code, context=context)

    def test_limits_and_unknown_fields_fail_closed(self):
        payload = self.request().payload | {"extra": True}
        request = replace(self.request(), payload=payload,
                          payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest())
        self.reject(request, "BEHAVIOR_CREATE_SHAPE")
        payload = {"behavior_id": "x", "states": ["idle"], "initial_state": "idle",
                   "transitions": [{"from_state": "idle", "action": "go", "to_state": "idle", "effects": [
                       {"kind": "move", "params": {"speed": 1}}] * 9}]}
        self.reject(self.request(payload=payload), "BEHAVIOR_EFFECT_SHAPE")

    def test_effects_use_exact_typed_parameter_schemas(self):
        for kind, params in (("move", {"velocity_x": 1}),
                             ("jump", {"speed": 1}),
                             ("set_velocity", {"velocity_x": 1}),
                             ("face", {"angle": 1, "speed": 2}),
                             ("emit_signal", {}),
                             ("play_animation", {"animation": "run", "signal": "done"})):
            payload = {"behavior_id": "x", "states": ["idle", "run"], "initial_state": "idle",
                       "transitions": [{"from_state": "idle", "action": "go", "to_state": "run",
                                        "effects": [{"kind": kind, "params": params}]}]}
            self.reject(self.request(payload=payload), "BEHAVIOR_EFFECT_SHAPE")
        payload = {"behavior_id": "x", "states": ["idle"], "initial_state": "idle",
                   "transitions": [{"from_state": "idle", "action": "go", "to_state": "idle",
                                    "effects": [{"kind": "emit_signal", "params": {"signal": "land"}}]}]}
        self.assertEqual(self.validate(self.request(payload=payload)).projection["transitions"][0]["effects"][0]["params"], {"signal": "land"})

    def test_malformed_effect_containers_fail_as_validation_errors(self):
        for kind, params in (([], {}), ({}, {}), ("move", []), ("move", {"speed": []}),
                             ("emit_signal", {"signal": []}), ("play_animation", {"animation": []})):
            effect = {"kind": kind, "params": params}
            payload = {"behavior_id": "x", "states": ["idle"], "initial_state": "idle",
                       "transitions": [{"from_state": "idle", "action": "go", "to_state": "idle",
                                        "effects": [effect]}]}
            self.reject(self.request(payload=payload), "BEHAVIOR_EFFECT_SHAPE" if not isinstance(kind, str) or isinstance(params, list) else "BEHAVIOR_EFFECT_VALUE")


if __name__ == "__main__":
    unittest.main()
