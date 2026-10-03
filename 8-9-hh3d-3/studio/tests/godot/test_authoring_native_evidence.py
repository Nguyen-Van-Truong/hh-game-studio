"""Negative evidence tests: partial native observations must never be PASS."""
import copy
from pathlib import Path
import tempfile
import unittest

from tests.godot import run_authoring_native_probe as probe


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.catalog = probe._CONTRACT.load_catalog().as_dict()
        labels = (probe.expected_labels(self.catalog) | probe.expected_edge_labels()
                  | probe.expected_resource_labels() | probe.expected_instance_labels()
                  | probe.expected_tilemap_labels() | probe.expected_animation_labels()
                  | probe.expected_behavior_labels() | probe.expected_script_labels())
        self.observation = {
            "schema": "hh-o2-native-authoring-observation-1",
            "actual_editor": True, "runtime_authorized": False,
            "native_mutation": True, "formal_acceptance": False,
            "failures": [], "checks": [{"label": label, "passed": True} for label in sorted(labels)],
            "isolation": {"project_under_run_root": True, "user_under_run_root": True,
                          "network_used": False, "arbitrary_script_loaded": False, "public_ack": False},
            "project_root": (self.root / "project").as_posix(),
            "user_root": (self.root / "user").as_posix(), "pid": 123,
        }
        for class_name in ("GPUParticles2D", "CPUParticles2D", "AudioStreamPlayer2D", "ProgressBar"):
            spec = next(row for row in self.catalog["classes"] if row["class_name"] == class_name)
            names = list(spec["properties"])
            for suffix in ("_readback_all_properties", "_undo_do_readback", "_undo_readback", "_redo_readback"):
                row = self.row("class_" + class_name + suffix)
                row["details"] = [{"name": name, "passed": True,
                                    "observed": {"synthetic": True}, "expected": {"synthetic": True}}
                                   for name in names]
        # Synthetic evidence for verifier unit tests, never a native execution claim.
        poses = {
            "motion2d": ((0, [1, 2], 0, [1, 1]), (1, [5, 4], 30, [1.5, 2]), (2, [9, 6], 60, [2, 3])),
            "motion3d": ((0, [0, 0, 0], [0, 0, 0], [1, 1, 1]),
                         (2, [2, 4, 6], [5, 20, 40], [1.5, 2, 2.5]),
                         (1, [1, 2, 3], [2.5, 10, 20], [1.25, 1.5, 1.75])),
        }
        for proposal in probe.animation_proposals():
            prefix = "animation_" + proposal["animation_id"]
            binding = {key: proposal[key] for key in ("command_id", "request_digest")}
            self.row(prefix + "_binding")["details"] = binding.copy()
            for suffix in ("_do_readback", "_redo_readback"):
                self.row(prefix + suffix)["details"] = {
                    "animation_id": proposal["animation_id"], "length": proposal["length"],
                    "loop_mode": proposal["loop_mode"], "tracks": [
                        {"path": spec["node_path"] + ":" + spec["property"], "type": 0,
                         "interpolation": 1, "keys": copy.deepcopy(spec["keys"])} for spec in proposal["tracks"]]}
            for suffix in ("_playback", "_redo_playback"):
                node = "actor2d" if proposal["animation_id"] == "motion2d" else "actor3d"
                self.row(prefix + suffix)["details"] = {
                    **binding, "samples": [{"position_seconds": time, "values": {
                        node + ":position": copy.deepcopy(position), node + ":rotation_degrees": copy.deepcopy(rotation),
                        node + ":scale": copy.deepcopy(scale)}} for time, position, rotation, scale in poses[proposal["animation_id"]]]}
        behavior = probe.behavior_proposals()[0]
        binding = {key: behavior[key] for key in ("command_id", "request_digest")}
        sequence = [
            {"state": "run", "position": [4.0, 0.0], "velocity": [4.0, 0.0],
             "rotation_degrees": 15.0, "signals": [], "animation": "run"},
            {"state": "jump", "position": [4.0, 0.0], "velocity": [3.0, -8.0],
             "rotation_degrees": 15.0, "signals": ["jumped"], "animation": "jump"},
            {"state": "idle", "position": [4.0, 0.0], "velocity": [0.0, 0.0],
             "rotation_degrees": 15.0, "signals": ["jumped", "landed"], "animation": "idle"},
        ]
        self.row("behavior_binding")["details"] = binding.copy()
        self.row("behavior_dispatch")["details"] = {**binding, "sequence": copy.deepcopy(sequence)}
        self.row("behavior_deterministic")["details"] = {
            **binding, "sequence": copy.deepcopy(sequence), "repeat_sequence": copy.deepcopy(sequence)}
        before = {"state": "idle", "position": [0.0, 0.0], "velocity": [0.0, 0.0],
                  "rotation_degrees": 0.0, "signals": [], "animation": ""}
        after_do = copy.deepcopy(sequence[0])
        self.row("behavior_undo_readback")["details"] = {
            "before": copy.deepcopy(before), "after_do": copy.deepcopy(after_do), "after_undo": copy.deepcopy(before)}
        self.row("behavior_redo_readback")["details"] = {
            "after_do": copy.deepcopy(after_do), "after_redo": copy.deepcopy(after_do)}
        for label in ("script_do_readback", "script_redo_readback"):
            self.row(label)["details"] = {"path": "res://o2_candidate_profile.gd",
                                            "fixture_value": 23, "move_speed": 7.0,
                                            "turn_speed": 90.125, "enabled": False}

    def row(self, label, observation=None):
        return next(row for row in (observation or self.observation)["checks"] if row["label"] == label)

    def validate(self, observation):
        return probe.validate_result(observation, self.catalog, {"target_pid": 123}, self.root)

    def test_complete_observation_is_only_a_diagnostic(self):
        self.assertEqual(self.validate(self.observation), (True, None))
        self.observation["formal_acceptance"] = True
        self.assertEqual(self.validate(self.observation), (False, "native-diagnostic-binding"))

    def test_each_resource_check_is_mandatory(self):
        for label in probe.expected_resource_labels():
            with self.subTest(label=label):
                observation = copy.deepcopy(self.observation)
                observation["checks"] = [row for row in observation["checks"] if row["label"] != label]
                self.assertFalse(self.validate(observation)[0])

    def test_duplicate_or_false_resource_checks_reject(self):
        resource_row = next(row for row in self.observation["checks"]
                            if row["label"] == "resource_RectangleShape2D_before")
        self.observation["checks"].append(resource_row.copy())
        self.assertFalse(self.validate(self.observation)[0])
        self.observation["checks"].pop()
        resource_row["passed"] = False
        self.assertEqual(self.validate(self.observation), (False, "check-failed"))

    def test_unbound_process_and_paths_reject(self):
        self.observation["pid"] = 124
        self.assertEqual(self.validate(self.observation), (False, "pid-binding"))
        self.observation["pid"] = 123
        self.observation["project_root"] = self.root.as_posix() + "-other/project"
        self.assertEqual(self.validate(self.observation), (False, "project_root"))

    def test_resource_proposals_carry_validated_create_operations(self):
        proposals = probe.resource_proposals()
        self.assertEqual(len(proposals), 4)
        self.assertEqual(len({row["command_id"] for row in proposals}), 4)
        for row in proposals:
            self.assertEqual(row["operation"], "scene.resource.create")
            self.assertEqual(row["expected_generation"], 4)
            self.assertNotIn("runtime_authorized", row)

    def test_animation_flags_cannot_replace_raw_readback(self):
        for label in probe.expected_animation_labels():
            with self.subTest(label=label):
                observation = copy.deepcopy(self.observation)
                observation["checks"] = [row for row in observation["checks"] if row["label"] != label]
                self.assertFalse(self.validate(observation)[0])
        for label in ("animation_motion2d_playback", "animation_motion3d_redo_playback"):
            observation = copy.deepcopy(self.observation)
            self.row(label, observation).pop("details")
            self.assertFalse(self.validate(observation)[0])

    def test_animation_wrong_pose_rejects_even_with_passed_true(self):
        for motion, actor in (("motion2d", "actor2d"), ("motion3d", "actor3d")):
            for suffix in ("_playback", "_redo_playback"):
                for sample_index in range(3):
                    for prop in ("position", "rotation_degrees", "scale"):
                        with self.subTest(motion=motion, suffix=suffix, sample=sample_index, prop=prop):
                            observation = copy.deepcopy(self.observation)
                            values = self.row("animation_" + motion + suffix, observation)["details"]["samples"][sample_index]["values"]
                            key = actor + ":" + prop
                            values[key] = [999] * len(values[key]) if type(values[key]) is list else 999
                            self.assertEqual(self.validate(observation), (False, "animation-playback-value"))

    def test_animation_malformed_values_and_sample_times_reject(self):
        for value in (None, True, "5", [], [float("nan"), 4], [float("inf"), 4], [True, 4], [5, 4, 0]):
            observation = copy.deepcopy(self.observation)
            self.row("animation_motion2d_playback", observation)["details"]["samples"][1]["values"]["actor2d:position"] = value
            self.assertFalse(self.validate(observation)[0])
        for field, value in (("position_seconds", 0), ("values", {})):
            observation = copy.deepcopy(self.observation)
            self.row("animation_motion3d_redo_playback", observation)["details"]["samples"][1][field] = value
            self.assertFalse(self.validate(observation)[0])

    def test_animation_stale_binding_and_resource_mismatches_reject(self):
        for suffix in ("_binding", "_playback", "_redo_playback"):
            for key in ("command_id", "request_digest"):
                observation = copy.deepcopy(self.observation)
                self.row("animation_motion2d" + suffix, observation)["details"][key] = "stale"
                self.assertFalse(self.validate(observation)[0])
        for suffix in ("_do_readback", "_redo_readback"):
            for field, value in (("path", "../Actor2D:position"), ("keys", [[0, [0, 0]], [2, [10, 0]]]),
                                 ("type", 1), ("interpolation", 0)):
                observation = copy.deepcopy(self.observation)
                self.row("animation_motion2d" + suffix, observation)["details"]["tracks"][0][field] = value
                self.assertFalse(self.validate(observation)[0])

    def test_script_rows_require_native_readback_details(self):
        for label in probe.expected_script_labels():
            with self.subTest(label=label):
                observation = copy.deepcopy(self.observation)
                observation["checks"] = [row for row in observation["checks"] if row["label"] != label]
                self.assertFalse(self.validate(observation)[0])
        for label in ("script_do_readback", "script_redo_readback"):
            observation = copy.deepcopy(self.observation)
            self.row(label, observation)["details"]["turn_speed"] = 91.0
            self.assertEqual(self.validate(observation), (False, "script-readback"))

    def test_script_profile_input_is_byte_validated_before_native_run(self):
        candidate = probe.script_input()
        self.assertEqual(candidate["profile"], "hh-godot-declarative-1")
        self.assertEqual(candidate["defaults"], {"fixture_value": 23, "move_speed": 7.0,
                                                   "turn_speed": 90.125, "enabled": False})
        self.assertNotIn("FileAccess", candidate["source"])
        self.assertNotIn("func ", candidate["source"])


if __name__ == "__main__":
    unittest.main()
