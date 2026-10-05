"""Engine-free contract checks for Blender producer crash-cut recovery."""
from __future__ import annotations

import sys
from pathlib import Path
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.tests.jobs.gt07_blender_recovery import validate_cut


def _observation(phase: str) -> dict:
    terminal = phase in ("COMMITTED", "ACK")
    files = {"checkpoint.blend": {}, "scene.glb": {}, "manifest.json": {}}
    if terminal:
        files["active.json"] = {}
    return {
        "state": {"phase": {"PREPARED": "INTENT", "VALIDATED": "STAGED",
                              "ACTIVATING": "SELECTING", "COMMITTED": "TERMINAL",
                              "ACK": "TERMINAL"}[phase]},
        "response": {"status": "COMMITTED" if terminal else "UNKNOWN",
                      "public_ack": False},
        "files": files,
        "selected": {} if terminal else None,
    }


class GT07BlenderRecoveryContractTests(unittest.TestCase):
    def test_each_cut_phase_has_explicit_state_boundary(self):
        for phase in ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "ACK"):
            with self.subTest(phase=phase):
                self.assertIsNone(validate_cut(phase, _observation(phase)))

    def test_recovery_contract_rejects_early_active_selector(self):
        observation = _observation("PREPARED")
        observation["files"]["active.json"] = {}
        with self.assertRaisesRegex(ValueError, "BLENDER_CUT_EARLY_SELECTION"):
            validate_cut("PREPARED", observation)

    def test_recovery_contract_rejects_public_ack_at_cut(self):
        observation = _observation("VALIDATED")
        observation["response"]["public_ack"] = True
        with self.assertRaisesRegex(ValueError, "BLENDER_CUT_PUBLIC_ACK"):
            validate_cut("VALIDATED", observation)


if __name__ == "__main__":
    unittest.main()
