from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

_RUNNER_PATH = Path(__file__).with_name("run_gt09_attribution_hostile.py")
_SPEC = importlib.util.spec_from_file_location("gt09_attribution_hostile_runner", _RUNNER_PATH)
_RUNNER = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(_RUNNER)
main = _RUNNER.main


class Gt09AttributionHostileTests(unittest.TestCase):
    def test_host_process_rejects_hostile_scope_without_effect(self):
        with tempfile.TemporaryDirectory(prefix="gt09-k12-") as directory:
            output = Path(directory) / "run"
            self.assertEqual(main(["--run-id", "gt09-k12-focused-1",
                                   "--output", str(output)]), 0)
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "DIAGNOSTIC_PASS")
            self.assertEqual(result["authority"], 0)
            self.assertFalse(result["acceptance"])
            self.assertFalse(result["public_ack"])
            self.assertEqual(result["scope_boundary"]["error_code"],
                             "FIXTURE_PROFILE_DISABLED")
            self.assertFalse(result["scope_boundary"]["accepted"])
            self.assertIs(result["scope_boundary"]["native_dispatch"], False)
            self.assertTrue(result["scope_boundary"]["no_effect"])
            self.assertTrue(result["hostile_inputs"]["treated_as_opaque_data"])
            host = result["command_host"]
            self.assertIsInstance(host["pid"], int)
            self.assertGreater(host["pid"], 0)
            self.assertEqual(host["exit_code"], 0)
            self.assertEqual(result["container_state"]["ExitCode"], host["exit_code"])
            self.assertEqual(result["container_state"]["kind"], "host-process")
            self.assertTrue((output / "host-stdout.txt").is_file())
            self.assertTrue((output / "host-stderr.txt").is_file())
            self.assertTrue(result["raw_rejection"]["stdout_base64"])

    def test_existing_output_fails_closed_without_replacing_prior_result(self):
        with tempfile.TemporaryDirectory(prefix="gt09-k12-existing-") as directory:
            output = Path(directory) / "run"
            output.mkdir()
            prior = output / "result.json"
            prior.write_text("prior\n", encoding="utf-8")
            self.assertEqual(main(["--run-id", "gt09-k12-focused-2",
                                   "--output", str(output)]), 2)
            self.assertEqual(prior.read_text(encoding="utf-8"), "prior\n")


if __name__ == "__main__":
    unittest.main()
