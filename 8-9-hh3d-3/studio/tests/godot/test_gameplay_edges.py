"""Authority-0 gameplay-edge candidate tests; no Godot process or writes."""
from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
SPEC = importlib.util.spec_from_file_location("gameplay_edges", STUDIO / "godot-addon/gameplay_edges.py")
edges = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = edges
SPEC.loader.exec_module(edges)
from studio.protocol.core import Request, ValidationError, canonical_bytes


class GameplayEdgeTests(unittest.TestCase):
    def setUp(self):
        self.context = edges.EdgeContext(
            "project.fixture", "sha256:" + "1" * 64, 3, "lease.fixture", 7, 31000, 1000,
            (edges.EdgeNode("root"), edges.EdgeNode("actor"), edges.EdgeNode("bot")),
            signals=(edges.SignalEdge("actor", "pressed", "bot", "on_pressed"),),
            groups=(edges.GroupEdge("actor", "fighters"),),
            inputs=(edges.InputAction("move_left", 65, 0.5),))

    def request(self, operation, payload, target=None, **changes):
        payload = dict(payload)
        payload.setdefault("expected_generation", self.context.generation)
        values = dict(command_id="edge.command", project_id=self.context.project_id,
                      operation=operation, lease_id=self.context.lease_id,
                      fencing_epoch=self.context.fencing_epoch, expected_revision=self.context.revision,
                      target=target or {"stable_id": "actor"}, payload=payload,
                      payload_hash="sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                      deadline_ms=2000)
        values.update(changes)
        return Request(**values)

    def reject(self, request, code):
        with self.assertRaises(ValidationError) as raised:
            edges.validate_request(request, self.context)
        self.assertEqual(raised.exception.code, code)

    def test_signal_group_and_input_proposals_are_immutable_diagnostics(self):
        rows = (
            self.request("scene.signal.connect", {"signal_name": "released", "target_stable_id": "bot", "method": "on_released"}),
            self.request("scene.group.assign", {"group_name": "targets"}),
            self.request("input.action.define", {"action_name": "jump", "physical_key": 32, "deadzone": 0.25}, {"stable_id": "root"}),
        )
        for request in rows:
            with self.subTest(operation=request.operation):
                result = edges.validate_request(request, self.context)
                self.assertFalse(result.projection["changes_applied"])
                self.assertFalse(result.projection["runtime_authorized"])
                self.assertFalse(result.projection["native_verified"])

    def test_duplicate_edges_and_unknown_nodes_are_rejected(self):
        self.reject(self.request("scene.signal.connect", {"signal_name": "pressed", "target_stable_id": "bot", "method": "on_pressed"}), "EDGE_DUPLICATE_SIGNAL")
        self.reject(self.request("scene.group.assign", {"group_name": "fighters"}), "EDGE_DUPLICATE_GROUP")
        self.reject(self.request("input.action.define", {"action_name": "move_left", "physical_key": 65, "deadzone": 0.5}, {"stable_id": "root"}), "EDGE_DUPLICATE_INPUT")
        self.reject(self.request("scene.signal.connect", {"signal_name": "pressed", "target_stable_id": "missing", "method": "on_pressed"}), "EDGE_SIGNAL")

    def test_stale_generation_lease_revision_and_deadline_reject(self):
        request = self.request("scene.group.assign", {"group_name": "targets"})
        stale_payload = {**request.payload, "expected_generation": 2}
        self.reject(replace(request, payload=stale_payload,
                            payload_hash="sha256:" + hashlib.sha256(canonical_bytes(stale_payload)).hexdigest()),
                    "EDGE_STALE_GENERATION")
        self.reject(replace(request, fencing_epoch=8), "EDGE_STALE_LEASE")
        self.reject(replace(request, expected_revision="sha256:" + "2" * 64), "EDGE_STALE_REVISION")
        self.reject(replace(request, deadline_ms=1000), "EDGE_DEADLINE")

    def test_input_values_are_closed_and_boolean_is_not_integer(self):
        for payload in (
            {"action_name": "bad name", "physical_key": 1, "deadzone": 0.5},
            {"action_name": "jump", "physical_key": True, "deadzone": 0.5},
            {"action_name": "jump", "physical_key": 1, "deadzone": 1},
        ):
            self.reject(self.request("input.action.define", payload, {"stable_id": "root"}), "EDGE_INPUT")
        with self.assertRaises(ValidationError):
            self.request("input.action.define", {"action_name": "jump", "physical_key": 1,
                                                   "deadzone": float("nan")}, {"stable_id": "root"})

    def test_request_and_context_are_copied(self):
        request = self.request("scene.group.assign", {"group_name": "targets"})
        result = edges.validate_request(request, self.context)
        request.payload["group_name"] = "mutated"
        self.assertEqual(result.projection["after"]["group_name"], "targets")
        projection = result.projection
        projection["runtime_authorized"] = True
        self.assertFalse(result.projection["runtime_authorized"])
        self.assertEqual(result.projection["profile"], edges.PROFILE)


if __name__ == "__main__":
    unittest.main()
