import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("remint_plan", HERE / "remint_plan.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RemintPlanTests(unittest.TestCase):
    def test_identifiers_are_deterministic_and_redacted(self):
        godot = {
            "version": "4.7.2-stable",
            "console_executable": "Godot_v4.7.2-stable_win64_console.exe",
            "gui_executable": "Godot_v4.7.2-stable_win64.exe",
            "console_sha256": "a" * 64,
            "gui_sha256": "b" * 64,
            "observed_version": "4.7.2.stable.official.ed1daf0",
        }
        first = MODULE._redacted_plan("c" * 64, 20, godot, MODULE.DEFAULT_MANIFEST)
        second = MODULE._redacted_plan("c" * 64, 20, godot, MODULE.DEFAULT_MANIFEST)
        self.assertEqual(first, second)
        self.assertEqual(first["run_id"], "GT01-R16-cccccccccccc-OFFICIAL-01")
        self.assertNotIn("D:", json.dumps(first))
        self.assertIn("<GODOT_CONSOLE>", first["launch_command_redacted"])

    def test_binary_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            console = root / "Godot_v4.7.2-stable_win64_console.exe"
            gui = root / "Godot_v4.7.2-stable_win64.exe"
            console.write_bytes(b"console")
            gui.write_bytes(b"gui")
            lock = root / "toolchain.lock.json"
            lock.write_text(json.dumps({
                "schema": "HH-STUDIO-TOOLCHAIN-LOCK-2", "status": "CANDIDATE",
                "godot": {"version": "4.7.2-stable",
                          "console_executable": console.name, "gui_executable": gui.name,
                          "console_sha256": hashlib.sha256(b"wrong").hexdigest(),
                          "gui_sha256": hashlib.sha256(b"gui").hexdigest(),
                          "observed_version": "4.7.2.stable.official.ed1daf0"}}), encoding="utf-8")
            original = MODULE.LOCK
            MODULE.LOCK = lock
            try:
                with self.assertRaises(MODULE.RemintGap):
                    MODULE._verify_lock_and_binaries(console, gui)
            finally:
                MODULE.LOCK = original

    def test_reservation_is_exclusive(self):
        reservation = MODULE.HERE / "one-process.reservation"
        try:
            with MODULE._reservation():
                with self.assertRaises(MODULE.RemintGap):
                    with MODULE._reservation():
                        pass
        finally:
            reservation.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
