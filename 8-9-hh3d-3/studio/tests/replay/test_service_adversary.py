"""Pure guards for the GT07 Play-mutation adversary lane.

These tests exercise only the owned-workspace boundary.  They do not launch
Godot or turn an adversary result into acceptance evidence.
"""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest
from unittest import mock

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


class DryRunAdversaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.review_root = Path(self.temp.name) / "reviews"
        self.review_root.mkdir()
        self.source = {
            "build/bootstrap/run_fixture.py": "a" * 64,
            "host/replay/service.py": "b" * 64,
        }
        self.patches = mock.patch.multiple(
            ADVERSARY,
            REVIEWS=self.review_root,
        )
        self.patches.start()
        self.source_patches = mock.patch.multiple(
            ADVERSARY.native,
            accepted_inputs=mock.Mock(return_value=({}, {"source_files": self.source})),
            sources=mock.Mock(return_value=self.source),
            run_trusted_stage=mock.Mock(side_effect=AssertionError("engine launched")),
        )
        self.source_patches.start()

    def tearDown(self):
        self.source_patches.stop()
        self.patches.stop()
        self.temp.cleanup()

    def test_dry_run_binds_source_and_driver_without_backend(self):
        run_id = "gt06-dry-run-contract"
        with mock.patch.object(ADVERSARY.PreparedPlay, "prepare",
                               side_effect=AssertionError("backend prepared")) as prepare:
            result = ADVERSARY.dry_run(run_id, "play-mutation", output_root=self.review_root)
        self.assertEqual(result["schema"], ADVERSARY.DRY_RUN_SCHEMA)
        self.assertEqual(result["run_id"], run_id)
        self.assertEqual(result["mode"], "play-mutation")
        self.assertRegex(result["source_closure_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(result["driver_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["source_files"], len(self.source))
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["commands_started"])
        self.assertFalse(result["backend_started"])
        self.assertFalse(result["native_process_started"])
        prepare.assert_not_called()

    def test_dry_run_rejects_unowned_review_root_and_existing_output(self):
        with self.assertRaises(ADVERSARY.native.ReplayError) as caught:
            ADVERSARY.dry_run("gt06-dry-run-root", "stale-capture",
                              output_root=Path(self.temp.name) / "elsewhere")
        self.assertEqual(str(caught.exception), "ADVERSARY_REVIEW_ROOT")
        (self.review_root / "gt06-dry-run-existing").mkdir()
        with self.assertRaises(ADVERSARY.native.ReplayError) as caught:
            ADVERSARY.dry_run("gt06-dry-run-existing", "stale-capture",
                              output_root=self.review_root)
        self.assertEqual(str(caught.exception), "ADVERSARY_OUTPUT_EXISTS")

    def test_dry_run_validates_frozen_hashes(self):
        result = ADVERSARY.dry_run("gt06-dry-run-hash", "revoked-result",
                                   output_root=self.review_root)
        with self.assertRaises(ADVERSARY.native.ReplayError) as caught:
            ADVERSARY.dry_run("gt06-dry-run-source-mismatch", "revoked-result",
                              output_root=self.review_root,
                              expected_source_closure_sha256="0" * 64)
        self.assertEqual(str(caught.exception), "ADVERSARY_SOURCE_CLOSURE_MISMATCH")
        with self.assertRaises(ADVERSARY.native.ReplayError) as caught:
            ADVERSARY.dry_run("gt06-dry-run-driver-mismatch", "revoked-result",
                              output_root=self.review_root,
                              expected_driver_sha256="0" * 64)
        self.assertEqual(str(caught.exception), "ADVERSARY_DRIVER_HASH_MISMATCH")
        self.assertEqual(result["source_closure_sha256"],
                         ADVERSARY.native.closure(self.source))

    def test_cli_dry_run_does_not_delegate_to_bounded_runner(self):
        expected = {"dry_run": True, "engine_started": False}
        with mock.patch.object(ADVERSARY, "dry_run", return_value=expected), \
             mock.patch.object(ADVERSARY, "bounded_run",
                               side_effect=AssertionError("native path entered")), \
             mock.patch.object(sys, "argv", ["run_service_adversary", "--run-id",
                                               "gt06-cli-dry-run", "--mode", "saturated-stop",
                                               "--dry-run", "--output-root", str(self.review_root)]), \
             mock.patch("builtins.print") as printed:
            self.assertEqual(ADVERSARY.main(), 0)
        printed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
