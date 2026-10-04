"""Engine-free failpoint admission and phase-hook tests."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from studio.host.core import gt07_failpoints as module


class GT07FailpointTests(unittest.TestCase):
    def test_absent_or_disabled_config_is_safe(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            module.assert_disabled(base)
            path = module.config_path(base)
            path.parent.mkdir()
            path.write_text('{"schema":"HH-GT07-FAILPOINT-1","enabled":false}', encoding="utf-8")
            module.assert_disabled(base)
            module.hit(base, "PREPARED")

    def test_enabled_config_blocks_admission_and_wait_timeout_never_continues(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            path = module.config_path(base)
            path.parent.mkdir()
            path.write_text(json.dumps({"schema": "HH-GT07-FAILPOINT-1", "enabled": True,
                                        "phase": "PREPARED", "action": "pause",
                                        "run_id": "gt07-failpoint-unit", "wait_seconds": 1}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ENABLED"):
                module.assert_disabled(base)
            with patch.object(module.time, "monotonic", side_effect=[0, 2]):
                with self.assertRaises(module.FailpointTimeout):
                    module.hit(base, "PREPARED")
            receipt = json.loads(path.with_name("gt07-failpoint-reached.json").read_bytes())
            self.assertEqual(receipt["phase"], "PREPARED")
            self.assertEqual(receipt["pid"], module.os.getpid())
            self.assertEqual(receipt["run_id"], "gt07-failpoint-unit")

    def test_unknown_phase_or_unsafe_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            path = module.config_path(base)
            path.parent.mkdir()
            path.write_text('{"schema":"HH-GT07-FAILPOINT-1","enabled":true,'
                            '"phase":"NOPE","action":"crash"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "INVALID"):
                module.assert_disabled(base)


if __name__ == "__main__":
    unittest.main()
