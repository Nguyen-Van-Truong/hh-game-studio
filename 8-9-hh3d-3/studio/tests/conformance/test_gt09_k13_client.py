import json
from pathlib import Path
import tempfile
import unittest

from tests.conformance import run_gt09_k13_client as probe


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return path


def _publication(path: Path, closure: str, name: str) -> Path:
    receipt = {"command_id": f"command.{name}", "status": "READBACK_ACK",
               "readback_ack": True, "public_ack": False}
    transaction = "sha256:" + (("a" if name == "arena" else "b") * 64)
    handoff = {"schema": "hh-catalog-gameplay-handoff-1", "authority": 0,
               "public_ack": False, "transaction_digest": transaction,
               "command_ids": [f"recipe.node.{name}"],
               "provenance": {"transaction_digest": transaction, "authority": 0,
                              "public_ack": False}}
    return _write(path, {"status": "DIAGNOSTIC_PASS", "authority": 0,
                         "public_ack": False, "source_closure_sha256": closure,
                         "catalog_handoff": handoff,
                         "catalog_scene_instantiation_observed": True,
                         "catalog_scene_provenance_unchanged": True,
                         "receipt": receipt})


def _registered(path: Path, closure: str) -> Path:
    def route(command):
        receipt = {"command_id": command, "status": "READBACK_ACK",
                   "readback_ack": True, "public_ack": False}
        return {"command_id": command, "status": "READBACK_ACK", "authority": 0,
                "public_ack": False, "receipt": receipt}
    return _write(path, {"schema": "hh-gt09-registered-script-result-1",
                         "status": "DIAGNOSTIC_PASS", "authority": 0,
                         "public_ack": False, "source_closure_sha256": closure,
                         "registered_route": route("registered.script.k3"),
                         "repair_route": route("registered.script.k9.repair"),
                         "repair_batch_applied": True,
                         "repair_replay_observed": True,
                         "checkpoint_verified": True,
                         "repair_replay": {"fixture_observed": True},
                         "seeded_fault_observed": True, "seed_error": "seed",
                         "seed_native": {"diagnostic_process_clean": False}})


def _external(path: Path) -> Path:
    return _write(path, {"schema": "hh-gt09-mcp-native-spike-2",
                         "status": "MEASURED_EXTERNAL_NATIVE_LIMIT",
                         "native_gate": "INCOMPATIBLE", "supported": False,
                         "client": {"name": "measured-client", "version": "1",
                                    "model": "measured-model", "protocol": "p"},
                         "host": {"os": "test"}, "adapter": {"name": "measured-adapter"},
                         "limits": ["lease boundary absent"]})


class K13ClientProvenanceTests(unittest.TestCase):
    def test_missing_k8_or_k9_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "client.json"
            code = probe.main(["--run-id", "gt09-k13-client-test", "--output", str(out)])
            self.assertEqual(code, 2)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "DIAGNOSTIC_FAIL")
            self.assertEqual(report["error_code"], "K13_CLIENT_PROVENANCE_ARGS_REQUIRED")
            self.assertFalse(report["recipe_observed"])
            self.assertFalse(report["batch_observed"])

    def test_measured_row_hashes_exact_receipts_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "a" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--k13-evidence", str(external), "--output", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "MEASURED_INCOMPATIBLE")
            self.assertEqual(report["client"]["name"], "measured-client")
            self.assertTrue(len(report["transcript_sha256"]) == 64)
            self.assertTrue(report["recipe_observed"])
            self.assertTrue(report["batch_observed"])

    def test_tampered_recipe_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "b" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            value = json.loads(arena.read_text(encoding="utf-8"))
            value["catalog_handoff"]["command_ids"] = ["caller.claimed.recipe"]
            arena.write_text(json.dumps(value), encoding="utf-8")
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--k13-evidence", str(external), "--output", str(out)]), 2)
            self.assertEqual(json.loads(out.read_text())["error_code"], "K8_ARENA_RECIPE_COMMAND_IDS")


if __name__ == "__main__":
    unittest.main()
