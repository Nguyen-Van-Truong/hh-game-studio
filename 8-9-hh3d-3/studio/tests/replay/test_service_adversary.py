"""Pure guards for the GT07 Play-mutation adversary lane.

These tests exercise only the owned-workspace boundary.  They do not launch
Godot or turn an adversary result into acceptance evidence.
"""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT.parent))
MODULE_PATH = Path(__file__).with_name("run_service_adversary.py")
SPEC = importlib.util.spec_from_file_location("gt07_service_adversary", MODULE_PATH)
ADVERSARY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ADVERSARY
SPEC.loader.exec_module(ADVERSARY)


class _Backend:
    def __init__(self, project, phase="RUNNING"):
        self.project = project
        self._phase = phase

    def status(self):
        return {"phase": self._phase, "runtime_instance_id": "gt06-test.runtime"}


class PlayMutationAdversaryTests(unittest.TestCase):
    def test_mode_is_explicitly_admitted(self):
        ADVERSARY._validate_arguments("gt06-test-play-mutation", "play-mutation")
        self.assertIn("play-mutation", ADVERSARY.MODES)

    def test_play_mutation_requires_running_backend(self):
        with tempfile.TemporaryDirectory() as temp:
            backend = _Backend(Path(temp) / "project", phase="COMPLETED")
            backend.project.joinpath("out").mkdir(parents=True)
            with self.assertRaises(ADVERSARY.native.ReplayError) as caught:
                ADVERSARY._mutate_editor_output_while_running(backend, Path(temp) / "evidence")
            self.assertEqual(str(caught.exception), "ADVERSARY_PLAY_MUTATION_NOT_RUNNING")

    def test_play_mutation_is_bound_to_owned_generated_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            backend = _Backend(root / "project")
            backend.project.joinpath("out").mkdir(parents=True)
            evidence = root / "evidence"
            evidence.mkdir()
            facts = ADVERSARY._mutate_editor_output_while_running(backend, evidence)
            marker = backend.project / "out/editor-mutation.json"
            self.assertEqual(facts["phase_before"], "RUNNING")
            self.assertEqual(facts["phase_after"], "RUNNING")
            self.assertEqual(facts["relative_path"], "project/out/editor-mutation.json")
            self.assertEqual(facts["sha256"], ADVERSARY.native.sha(marker.read_bytes()))
            self.assertTrue(marker.is_file())


if __name__ == "__main__":
    unittest.main()
