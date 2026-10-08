from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

try:
    from .gt09_mcp_compatibility import (build_matrix, verify_external_receipt,
                                         verify_matrix, verify_private_receipt)
except ImportError:  # direct ``python test_*.py`` invocation
    from gt09_mcp_compatibility import (build_matrix, verify_external_receipt,
                                        verify_matrix, verify_private_receipt)


FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/o2-adapter-gt09-arena-20261007-01/result.json"
EXTERNAL_FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/gt09-mcp-spike-20261008.json"


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

    def test_external_receipt_measures_transport_but_keeps_native_gate_open(self):
        evidence = verify_external_receipt(EXTERNAL_FIXTURE)
        self.assertEqual(len(evidence["servers"]), 2)
        self.assertEqual({row["summary"]["unsupported_outcome"] for row in evidence["servers"]},
                         {"NEGOTIATED"})
        matrix = build_matrix(FIXTURE, EXTERNAL_FIXTURE)
        self.assertEqual(matrix["status"], "EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN")
        self.assertFalse(matrix["acceptance"])
        self.assertEqual(verify_matrix(matrix), [])
        self.assertTrue(all(row["status"] == "MEASURED_TRANSPORT_ONLY"
                            for row in matrix["rows"] if row["id"] in {
                                "NPGameDev/godot-mcp-toolkit", "hybridindie/godot-mcp"}))

    def test_external_receipt_rejects_stale_process_exit(self):
        raw = json.loads(EXTERNAL_FIXTURE.read_text(encoding="utf-8"))
        raw["servers"][0]["runs"][1]["exit_code"] = 9
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "external.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "external_receipt_exit"):
                verify_external_receipt(path)


if __name__ == "__main__":
    unittest.main()
