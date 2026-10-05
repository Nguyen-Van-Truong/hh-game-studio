"""Engine-free checks for the GT07 scenario admission runner."""
from __future__ import annotations

import importlib.util
import argparse
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location(
    "gt07_scenarios", STUDIO / "tests/jobs/run_gt07_scenarios.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class GT07ScenarioAdmissionTests(unittest.TestCase):
    def test_matrix_is_explicit_and_deadlines_are_bounded(self):
        self.assertEqual(set(module.SCENARIOS), {
            "godot-edit", "godot-save", "godot-script", "godot-recovery",
            "blender-box", "blender-export"})
        self.assertEqual({row["max_horizon_ms"] for row in module.SCENARIOS.values()},
                         {5_000, 30_000, 90_000})

    def test_blender_contract_dry_run_is_engine_free(self):
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected engine")):
            result = module._contract_dry_run("blender-box", module.SCENARIOS["blender-box"])
        self.assertTrue(result["admission_validated"])
        self.assertTrue(result["public_lease_route_validated"])
        self.assertFalse(result["native_effect"])

    def test_lock_is_required_and_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            lock = Path(root) / "measure-window.lock"
            with patch.object(module, "default_path", return_value=lock):
                self.assertEqual(module._check_lock(None, native=True), str(lock.resolve()))
                with self.assertRaisesRegex(ValueError, "PATH_FORBIDDEN"):
                    module._check_lock(str(Path(root) / "other.lock"), native=True)
                lock.write_text("owner=fixture\n", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "MEASURE_WINDOW_BUSY"):
                    module._check_lock(str(lock), native=True)

    def test_oversized_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            lock = Path(root) / "measure-window.lock"
            # The runner refuses every existing marker, even a small one.  It
            # must never accept a caller-created marker as proof of custody.
            lock.write_bytes(b"x" * 4097)
            with patch.object(module, "default_path", return_value=lock):
                with self.assertRaisesRegex(ValueError, "MEASURE_WINDOW_BUSY"):
                    module._check_lock(str(lock), native=True)

    def test_fixed_guard_does_not_create_marker(self):
        with tempfile.TemporaryDirectory() as root:
            lock = Path(root) / "measure-window.lock"
            with patch.object(module, "default_path", return_value=lock):
                with module._native_measure_guard():
                    self.assertFalse(lock.exists())
                    self.assertTrue(lock.with_suffix(".guard").exists())
                self.assertFalse(lock.exists())

    def test_same_guard_refuses_a_second_holder(self):
        with tempfile.TemporaryDirectory() as root:
            lock = Path(root) / "measure-window.lock"
            with patch.object(module, "default_path", return_value=lock):
                with module._native_measure_guard():
                    with self.assertRaisesRegex(ValueError, "MEASURE_WINDOW_BUSY"):
                        with module._native_measure_guard():
                            self.fail("second holder admitted")

    def test_dry_run_requires_fresh_output_and_id_before_contract(self):
        with tempfile.TemporaryDirectory() as root:
            studio = Path(root) / "studio"
            args = argparse.Namespace(run_id=None, run_ids=[], output_root=studio / ".local/reviews")
            with patch.object(module, "STUDIO", studio), \
                    patch.object(module, "_contract_dry_run", side_effect=AssertionError("too early")):
                with self.assertRaisesRegex(ValueError, "RUN_ID_REQUIRED"):
                    module.dry_run("godot-edit", args)
                args.run_id = "gt07-native-godot-20261004-99"
                args.output_root = Path(root) / "elsewhere"
                with self.assertRaisesRegex(ValueError, "OUTPUT_ROOT_FORBIDDEN"):
                    module.dry_run("godot-edit", args)
                args.output_root = studio / ".local/reviews"
                old_raw = studio.parent / "zdoc/reviews" / args.run_id
                old_raw.mkdir(parents=True)
                with self.assertRaisesRegex(ValueError, "RUN_ID_ALREADY_USED"):
                    module.dry_run("godot-edit", args)

    def test_matrix_stops_after_first_failure(self):
        output = io.StringIO()
        with patch.object(module, "_output_for"), \
                patch.object(module, "_run_one", return_value={"exit_code": 1}) as run, \
                redirect_stdout(output):
            result = module.main(["--matrix", "godot-edit,godot-save", "--run-ids",
                                  "gt07-native-godot-20261004-98,gt07-native-godot-20261004-99"])
        self.assertEqual(result, 1)
        self.assertEqual(run.call_count, 1)
        self.assertIn("STOP_AFTER_FAILURE", output.getvalue())

    def test_blender_negative_deadlines_use_real_validator(self):
        from studio.host.blender.client_writer_session import BlenderWriterClientSession
        with patch.object(BlenderWriterClientSession, "check_write", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "DEADLINE_NOT_REJECTED"):
                module._contract_dry_run("blender-box", module.SCENARIOS["blender-box"])

    def test_failpoint_rejects_routes_without_a_publication_phase(self):
        with tempfile.TemporaryDirectory() as root:
            studio = Path(root) / "studio"
            args = argparse.Namespace(run_id="gt07-native-godot-20261004-97",
                                      run_ids=[], output_root=studio / ".local/reviews",
                                      failpoint_phase="PREPARED")
            with patch.object(module, "STUDIO", studio):
                with self.assertRaisesRegex(ValueError, "FAILPOINT_UNSUPPORTED"):
                    module.dry_run("godot-edit", args)
                args.run_id = "gt07-native-queue-20261004-97"
                with self.assertRaisesRegex(ValueError, "FAILPOINT_UNSUPPORTED"):
                    module.dry_run("blender-box", args)

    def test_blender_producer_rejects_godot_reload_phase(self):
        with tempfile.TemporaryDirectory() as root:
            studio = Path(root) / "studio"
            args = argparse.Namespace(run_id="gt07-native-queue-20261004-96",
                                      run_ids=[], output_root=studio / ".local/reviews",
                                      failpoint_phase="RELOAD")
            with patch.object(module, "STUDIO", studio):
                with self.assertRaisesRegex(ValueError, "FAILPOINT_UNSUPPORTED"):
                    module.dry_run("blender-export", args)


if __name__ == "__main__":
    unittest.main()
