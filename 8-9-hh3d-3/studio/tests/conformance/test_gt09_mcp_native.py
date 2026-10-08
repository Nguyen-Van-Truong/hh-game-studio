from __future__ import annotations

import io
from pathlib import Path
import queue
import tempfile
import unittest

from run_gt09_mcp_native import Wire, classify, payload


class FakeProcess:
    def __init__(self):
        self.stdin = io.BytesIO()

    def poll(self):
        return None


def wire():
    value = Wire.__new__(Wire)
    value.proc = FakeProcess()
    value.inbox = queue.Queue()
    value.calls = []
    value.next_id = 1
    value.overflow = False
    return value


def row(index, name, value, *, error=False):
    return {"request": {"id": index, "method": "tools/call", "params": {"name": name}},
            "response": {"id": index, "jsonrpc": "2.0", "result": {
                "isError": error, "structuredContent": value}}}


class NativeMcpTests(unittest.TestCase):
    def test_ids_do_not_overlap_health_retries_and_fixed_operations(self):
        peer = wire()
        for request_id in range(1, 32):
            peer.inbox.put({"id": request_id, "jsonrpc": "2.0", "result": {}})
            peer.call("godot_health_check" if request_id < 30 else "godot_get_server_info")
        self.assertEqual([r["request"]["id"] for r in peer.calls], list(range(1, 32)))

    def test_client_rejects_mutation_before_sending(self):
        peer = wire()
        with self.assertRaisesRegex(ValueError, "READ_ONLY_ALLOWLIST"):
            peer.call("godot_scene_edit_create_node")
        self.assertEqual(peer.proc.stdin.getvalue(), b"")
        self.assertEqual(peer.next_id, 1)

    def test_wrong_response_id_does_not_become_readback(self):
        peer = wire()
        peer.inbox.put({"id": 2, "jsonrpc": "2.0", "result": {}})
        with self.assertRaisesRegex(RuntimeError, "ID_MISMATCH"):
            peer.call("godot_health_check")
        self.assertIsNone(peer.calls[0]["response"])

    def test_error_result_cannot_count_as_connected_readback(self):
        response = row(1, "godot_health_check", {"bridge_connected": True}, error=True)["response"]
        self.assertEqual(payload(response), {})
        observed = classify([{"request": {"method": "tools/call", "params": {"name": "godot_health_check"}},
                              "response": response}], Path("."), {"observed_version": "4.7.2"})
        self.assertFalse(observed["native_readback"])

    def test_success_requires_both_native_pin_and_fixture_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            tree = {"name": "Arena", "type": "Node2D", "children": [
                {"name": "Player", "type": "CharacterBody2D"}, {"name": "Floor", "type": "StaticBody2D"}]}
            calls = [row(1, "godot_health_check", {"bridge_connected": True}),
                     row(2, "godot_inspection_get_project_info", {"godot_version": "4.7.2-stable (official)", "project_path": str(project)}),
                     row(3, "godot_inspection_get_active_scene", {"path": "res://scenes/arena.tscn", "is_open": True}),
                     row(4, "godot_inspection_get_scene_tree", {"tree": tree}),
                     row(5, "godot_inspection_get_node_property", {"exists": True, "value": "HP 3"}),
                     row(6, "godot_inspection_get_scene_tree", {"tree": tree})]
            pin = {"observed_version": "4.7.2.stable.official.ed1daf0bf", "version": "4.7.2-stable"}
            self.assertTrue(classify(calls, project, pin)["native_readback"])
            calls[1]["response"]["result"]["structuredContent"]["godot_version"] = "4.7.1.stable"
            self.assertFalse(classify(calls, project, pin)["native_readback"])
            calls[1]["response"]["result"]["structuredContent"]["godot_version"] = "4.7.2-stable (official)"
            calls[-1]["response"]["result"]["isError"] = True
            self.assertFalse(classify(calls, project, pin)["native_readback"])


if __name__ == "__main__":
    unittest.main()
