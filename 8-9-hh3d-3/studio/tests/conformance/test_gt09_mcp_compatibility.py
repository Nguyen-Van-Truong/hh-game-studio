from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

try:
    from .gt09_mcp_compatibility import build_matrix, verify_matrix, verify_private_receipt
except ImportError:  # direct ``python test_*.py`` invocation
    from gt09_mcp_compatibility import build_matrix, verify_matrix, verify_private_receipt


FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/o2-adapter-gt09-arena-20261007-01/result.json"


class Gt09McpCompatibilityTests(unittest.TestCase):
    def test_retained_private_receipt_is_measured_but_not_mcp(self):
        evidence = verify_private_receipt(FIXTURE)
        self.assertEqual(evidence["native_run_count"], 2)
        matrix = build_matrix(FIXTURE)
        self.assertEqual(matrix["status"], "INCOMPLETE_EXTERNAL_SPIKE")
        self.assertFalse(matrix["acceptance"])
        self.assertEqual(verify_matrix(matrix), [])
        by_id = {row["id"]: row for row in matrix["rows"]}
        self.assertEqual(by_id["NPGameDev/godot-mcp-toolkit"]["status"], "UNMEASURED")
        self.assertFalse(by_id["hh-public-catalog"]["capabilities"]["public_discovery"])

    def test_receipt_cannot_forge_reconnect_or_public_support(self):
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["public_discovery_empty"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "public_discovery_empty"):
                verify_private_receipt(path)

    def test_receipt_cannot_hide_nonzero_native_exit(self):
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["native_exits"][0]["command_host_exit"] = 17
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "private_receipt_exit:0"):
                verify_private_receipt(path)


if __name__ == "__main__":
    unittest.main()
