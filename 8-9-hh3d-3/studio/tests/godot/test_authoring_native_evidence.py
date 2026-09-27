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
                  | probe.expected_resource_labels())
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


if __name__ == "__main__":
    unittest.main()
