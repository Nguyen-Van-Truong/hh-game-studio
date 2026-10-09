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
    command_prefix = "recipe." if name == "arena" else "room."
    handoff = {"schema": "hh-catalog-gameplay-handoff-1", "authority": 0,
               "public_ack": False, "transaction_digest": transaction,
               "command_ids": [f"{command_prefix}node.{name}"],
               "provenance": {"transaction_digest": transaction, "authority": 0,
                              "public_ack": False}}
    handoff_key = "catalog_handoff" if name == "arena" else "catalog_room_handoff"
    scene_prefix = "catalog_room_scene" if name == "room" else "catalog_scene"
    return _write(path, {"status": "DIAGNOSTIC_PASS", "authority": 0,
                         "public_ack": False, "source_closure_sha256": closure,
                         handoff_key: handoff,
                         scene_prefix + "_instantiation_observed": True,
                         scene_prefix + "_provenance_unchanged": True,
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


def _author(path: Path, arena: Path, room: Path, registered: Path, closure: str) -> Path:
    arena_doc = json.loads(arena.read_text(encoding="utf-8"))
    room_doc = json.loads(room.read_text(encoding="utf-8"))
    registered_doc = json.loads(registered.read_text(encoding="utf-8"))
    events = [
        {"kind": "recipe", "fixture": "arena",
         "payload": {"command_ids": arena_doc["catalog_handoff"]["command_ids"],
                     "transaction_digest": arena_doc["catalog_handoff"]["transaction_digest"]},
         "receipt_sha256": probe._sha(arena)},
        {"kind": "recipe", "fixture": "room",
         "payload": {"command_ids": room_doc["catalog_room_handoff"]["command_ids"],
                     "transaction_digest": room_doc["catalog_room_handoff"]["transaction_digest"]},
         "receipt_sha256": probe._sha(room)},
        {"kind": "repair_batch", "fixture": "room",
         "payload": {"command_ids": [registered_doc["registered_route"]["command_id"],
                                       registered_doc["repair_route"]["command_id"]],
                     "repair_batch_applied": True, "repair_replay_observed": True,
                     "checkpoint_verified": True},
         "receipt_sha256": probe._sha(registered)},
    ]
    for event in events:
        event["payload_sha256"] = probe._canonical_sha(event["payload"])
    author = {"client": {"name": "Codex", "version": "desktop", "protocol": "codex-task"},
              "model": "gpt-6-astra", "reasoning_effort": "xhigh", "task_id": "test-k13"}
    transcript = {"author": author, "events": events, "source_closure_sha256": closure}
    return _write(path, {"schema": probe.AUTHOR_SCHEMA, "authority": 0, "public_ack": False,
                         "acceptance": False, "author": author,
                         "source_closure_sha256": closure, "events": events,
                         "receipt_bindings": {"arena": {"sha256": probe._sha(arena)},
                                              "room": {"sha256": probe._sha(room)},
                                              "registered": {"sha256": probe._sha(registered)}},
                         "transcript": transcript,
                         "transcript_sha256": probe._canonical_sha(transcript)})


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

    def test_k8_k9_without_current_author_transcript_is_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "e" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            out = root / "client.json"
            code = probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--k13-evidence", str(external), "--output", str(out)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["error_code"],
                             "K13_AUTHOR_PROVENANCE_REQUIRED")

    def test_measured_row_hashes_exact_receipts_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "a" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            author = _author(root / "author.json", arena, room, registered, closure)
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--author-provenance", str(author),
                "--k13-evidence", str(external), "--output", str(out)]), 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "MEASURED_INCOMPATIBLE")
            self.assertEqual(report["client"]["name"], "Codex")
            self.assertEqual(report["model"], "gpt-6-astra")
            self.assertEqual(report["external_client"]["name"], "measured-client")
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
            author = _author(root / "author.json", arena, room, registered, closure)
            value = json.loads(arena.read_text(encoding="utf-8"))
            value["catalog_handoff"]["command_ids"] = ["caller.claimed.recipe"]
            arena.write_text(json.dumps(value), encoding="utf-8")
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--author-provenance", str(author),
                "--k13-evidence", str(external), "--output", str(out)]), 2)
            self.assertEqual(json.loads(out.read_text())["error_code"], "K8_ARENA_RECIPE_COMMAND_IDS")

    def test_room_publication_requires_room_handoff_field(self):
        """A room result must use the fixture-specific K8 publication field."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "c" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            author = _author(root / "author.json", arena, room, registered, closure)
            value = json.loads(room.read_text(encoding="utf-8"))
            value["catalog_handoff"] = value.pop("catalog_room_handoff")
            room.write_text(json.dumps(value), encoding="utf-8")
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--author-provenance", str(author),
                "--k13-evidence", str(external), "--output", str(out)]), 2)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["error_code"],
                             "K8_ROOM_CATALOG_HANDOFF_MISSING")

    def test_author_transcript_payload_hash_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closure = "sha256:" + "d" * 64
            arena = _publication(root / "arena.json", closure, "arena")
            room = _publication(root / "room.json", closure, "room")
            registered = _registered(root / "registered.json", closure)
            external = _external(root / "external.json")
            author = _author(root / "author.json", arena, room, registered, closure)
            value = json.loads(author.read_text(encoding="utf-8"))
            value["events"][0]["payload"]["command_ids"] = ["recipe.tampered"]
            author.write_text(json.dumps(value), encoding="utf-8")
            out = root / "client.json"
            self.assertEqual(probe.main([
                "--run-id", "gt09-k13-client-test", "--arena-publication", str(arena),
                "--room-publication", str(room), "--registered-result", str(registered),
                "--author-provenance", str(author), "--k13-evidence", str(external),
                "--output", str(out)]), 2)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["error_code"],
                             "K13_AUTHOR_EVENT_PAYLOAD_HASH")


if __name__ == "__main__":
    unittest.main()
