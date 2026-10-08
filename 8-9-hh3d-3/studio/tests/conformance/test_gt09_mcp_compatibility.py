from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

try:
    from .gt09_mcp_compatibility import (build_matrix, verify_external_receipt,
                                         verify_matrix, verify_native_attempt,
                                         verify_native_receipt,
                                         verify_private_receipt)
except ImportError:  # direct ``python test_*.py`` invocation
    from gt09_mcp_compatibility import (build_matrix, verify_external_receipt,
                                        verify_matrix, verify_native_attempt,
                                        verify_native_receipt,
                                        verify_private_receipt)


FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/o2-adapter-gt09-arena-20261007-01/result.json"
EXTERNAL_FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/gt09-mcp-spike-20261008.json"
NATIVE_FIXTURE = Path(__file__).resolve().parents[2] / ".local/reviews/gt09-mcp-native-hybrid-20261008-08/native.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_native(directory: str) -> Path:
    """Copy only raw evidence and frozen source, never cache/process state."""
    root = Path(directory)
    for path in NATIVE_FIXTURE.parent.iterdir():
        if path.is_file():
            shutil.copy2(path, root / path.name)
    frozen = json.loads((root / "project-freeze.json").read_text())
    for name in frozen:
        target = root / "project" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(NATIVE_FIXTURE.parent / "project" / name, target)
    return root / "native.json"


def _rewrite_native(path: Path, raw: dict) -> None:
    path.write_text(json.dumps(raw), encoding="utf-8")
    final_path = path.parent / "result.json"
    final = json.loads(final_path.read_text())
    final["native_sha256"] = _sha(path)
    final_path.write_text(json.dumps(final), encoding="utf-8")


def _native_attempt_receipt() -> dict:
    """Return a disconnected, read-only attempt with explicit raw errors."""
    pin = "48f34e7d28d65cfea456cc2641e13c3058caa3d6"
    def call(request_id: int, name: str, response: dict) -> dict:
        return {
            "request": {
                "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                "params": {"name": name, "arguments": {}},
            },
            "response": {"jsonrpc": "2.0", "id": request_id, **response},
        }

    return {
        "schema": "hh-gt09-mcp-native-attempt-1",
        "authority": 0,
        "acceptance": False,
        "run_id": "gt09-mcp-native-test-01",
        "server": "hybridindie/godot-mcp",
        "server_pin": pin,
        "transport": "stdio",
        "client": {
            "name": "hh-gt09-native-probe", "version": "0.1.0",
            "protocol": "2025-11-25", "model": "UNSPECIFIED",
        },
        "host": {
            "os": "nt", "platform": "win32", "python": "3.11.9",
            "godot_binary": "C:/Godot_v4.7.1-stable_win64_console.exe",
        },
        "adapter": {
            "addon": "hybridindie/godot-mcp",
            "bridge_url": "ws://127.0.0.1:19082",
            "fixture": "studio/.local/gt09-native-hybrid-test",
        },
        "source_closure": {
            "probe_sha256": "a" * 64,
            "fixture_project_sha256": "b" * 64,
            "addon_commit": pin,
            "sha256": "c" * 64,
        },
        "calls": [
            call(3, "godot_health_check", {
                "result": {
                    "isError": False,
                    "structuredContent": {"bridge_connected": False},
                },
            }),
            call(4, "godot_inspection_get_project_info", {
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "BRIDGE_DISCONNECTED"}],
                },
            }),
        ],
        "native_observation": {
            "bridge_connected_observed": False,
            "postcondition_readback": "UNMEASURED",
            "lease": "UNMEASURED",
            "journal": "UNMEASURED",
            "command_id": "MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID",
        },
        "godot": {
            "exit_code": 1, "stdout_sha256": "d" * 64, "stderr_sha256": "e" * 64,
        },
        "mcp": {
            "exit_code": 0, "timed_out": False,
            "stdout_sha256": "f" * 64, "stderr_sha256": "0" * 64,
        },
        "status": "NATIVE_READONLY_ATTEMPT_UNSUPPORTED_LEASE",
    }


class Gt09McpCompatibilityTests(unittest.TestCase):
    def test_retained_native_readback_admits_only_external_limit(self):
        evidence = verify_native_receipt(NATIVE_FIXTURE)
        self.assertEqual(evidence["native_gate"], "INCOMPATIBLE")
        self.assertFalse(evidence["supported"])
        self.assertTrue(evidence["observations"]["native_readback"])
        self.assertEqual(len(evidence["warnings"]), 2)
        self.assertEqual(evidence["client"]["model"], "UNSPECIFIED")
        self.assertTrue(all(not item["lease_traversed"] and not item["journal_traversed"]
                            for item in evidence["operations"]))

    def test_native_matrix_does_not_claim_model_or_external_support(self):
        matrix = build_matrix(FIXTURE, EXTERNAL_FIXTURE, NATIVE_FIXTURE)
        by_id = {row["id"]: row for row in matrix["rows"]}
        native = by_id["hybridindie/godot-mcp"]
        self.assertEqual(native["status"], "INCOMPATIBLE")
        self.assertFalse(native["supported"])
        self.assertEqual(native["capabilities"]["k8_k12_client_model_matrix"], "NOT_TESTED")
        self.assertEqual(by_id["NPGameDev/godot-mcp-toolkit"]["status"], "MEASURED_TRANSPORT_ONLY")
        self.assertEqual(matrix["status"], "EXTERNAL_NATIVE_LIMITS_MEASURED_CLIENT_OPEN")
        self.assertFalse(matrix["acceptance"])
        self.assertEqual(verify_matrix(matrix), [])
        native["capabilities"]["native_cleanup_clean"] = True
        self.assertIn("native_row_binding", verify_matrix(matrix))

    def test_native_receipt_rejects_forged_ready_despite_rehashed_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _copy_native(directory)
            raw = json.loads(path.read_text())
            # Forge the recorded response and its raw-hash binding too, retaining
            # the readiness flags. The raw bridge postcondition still fails.
            health_rows = [row for row in raw["calls"]
                           if row["request"].get("params", {}).get("name") == "godot_health_check"]
            for row in health_rows:
                row["response"]["result"]["structuredContent"]["bridge_connected"] = False
            stdout = path.parent / "mcp-stdout.txt"
            stdout.write_text("\n".join(json.dumps(row["response"]) for row in raw["calls"]) + "\n", encoding="utf-8")
            raw["raw_logs"]["mcp-stdout.txt"] = raw["mcp"]["stdout_sha256"] = _sha(stdout)
            self.assertTrue(raw["observation"]["bridge_connected"])
            self.assertTrue(raw["observation"]["native_readback"])
            _rewrite_native(path, raw)
            with self.assertRaisesRegex(ValueError, "native_receipt_bridge"):
                verify_native_receipt(path)

    def test_native_receipt_rejects_absent_raw_host_receipts(self):
        for name in ("native-host.json", "host-job.json", "result.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = _copy_native(directory)
                (path.parent / name).unlink()
                with self.assertRaisesRegex(ValueError, "native_receipt_raw_missing"):
                    verify_native_receipt(path)

    def test_native_receipt_rejects_host_exit_hidden_by_ready_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _copy_native(directory)
            host_path = path.parent / "native-host.json"
            host = json.loads(host_path.read_text())
            host["exit_code"] = 19
            host_path.write_text(json.dumps(host), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_receipt_host_exit"):
                verify_native_receipt(path)

    def test_native_receipt_rejects_cleanup_warning_claim_forgery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _copy_native(directory)
            raw = json.loads(path.read_text())
            raw["native_warning_error_lines"] = []
            raw["native_gate"] = "UNSUPPORTED"
            _rewrite_native(path, raw)
            with self.assertRaisesRegex(ValueError, "native_receipt_warning_claim"):
                verify_native_receipt(path)

    def test_native_receipt_rejects_altered_response_not_in_wire(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _copy_native(directory)
            raw = json.loads(path.read_text())
            raw["calls"][-1]["response"]["result"]["structuredContent"]["tree"] = None
            _rewrite_native(path, raw)
            with self.assertRaisesRegex(ValueError, "native_receipt_wire_binding"):
                verify_native_receipt(path)

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

    def test_native_attempt_keeps_disconnected_readback_unsupported(self):
        raw = _native_attempt_receipt()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            evidence = verify_native_attempt(path)
        self.assertFalse(evidence["bridge_connected"])
        self.assertEqual(evidence["readback"], "UNMEASURED")
        self.assertEqual(evidence["lease"], "UNMEASURED")
        self.assertEqual(evidence["journal"], "UNMEASURED")
        self.assertEqual(evidence["command_id"], "MCP_REQUEST_ID_ONLY_NO_HH_COMMAND_ID")
        self.assertEqual(evidence["godot_exit"], 1)
        self.assertEqual(evidence["mcp_exit"], 0)
        self.assertEqual(evidence["status"], "NATIVE_READONLY_ATTEMPT_UNSUPPORTED_LEASE")

    def test_native_attempt_rejects_scripted_model_claim(self):
        raw = _native_attempt_receipt()
        raw["client"]["model"] = "gpt-6.1-sol"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_attempt_client"):
                verify_native_attempt(path)

    def test_native_attempt_rejects_mutating_operation(self):
        raw = _native_attempt_receipt()
        raw["calls"][1]["request"]["params"]["name"] = "godot_undo"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_attempt_operation:1"):
                verify_native_attempt(path)

    def test_native_attempt_rejects_unproven_readback(self):
        raw = _native_attempt_receipt()
        raw["native_observation"]["postcondition_readback"] = (
            "MEASURED_FOR_READ_ONLY_PROJECT_AND_SCENE"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_attempt_unconnected_readback"):
                verify_native_attempt(path)

    def test_native_attempt_rejects_reused_request_id(self):
        raw = _native_attempt_receipt()
        raw["calls"][1]["request"]["id"] = raw["calls"][0]["request"]["id"]
        raw["calls"][1]["response"]["id"] = raw["calls"][0]["response"]["id"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_attempt_request:1"):
                verify_native_attempt(path)


if __name__ == "__main__":
    unittest.main()
