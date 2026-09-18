"""Pure write-catalog boundaries and real private-validator/ledger composition."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))

from studio.host.blender import client_catalog as readonly
from studio.host.blender import client_ledger as ledger
from studio.host.blender import client_write_catalog as catalog
from studio.host.blender import publication_state
from studio.protocol.core import (
    Discovery, Request, SCHEMA_VERSION, ValidationError, canonical_bytes, parse_json,
)

PROJECT = "blender.catalog-test"
SOURCE = "sha256:" + "a" * 64
REVISION = "sha256:" + "b" * 64
SESSION = "session." + "c" * 32
BINDING = ledger.LedgerBinding(PROJECT, "d" * 32, SOURCE,
                               catalog.CATALOG_DIGEST, "sha256:" + "e" * 64)
CONTEXT = {"mode": "OBJECT", "active_id": "box", "selected_ids": ["box"]}
ARGUMENTS = {
    "mesh.create_box": {"object_id": "new_box", "size": [1, 2, 3]},
    "object.transform.set": {
        "object_id": "box", "location": [-1, 2, 3],
        "rotation": [0, 0.25, -0.5], "scale": [1, 2, 0.5],
    },
    "material.set_principled": {
        "object_id": "box", "material_id": "copper", "base_color": [0.5, 0.25, 0.1],
        "metallic": 0.8, "roughness": 0.3,
    },
}


def body(operation="mesh.create_box", **changes):
    payload = {} if operation == catalog.READ else {
        "expected_context": copy.deepcopy(CONTEXT),
        "arguments": copy.deepcopy(ARGUMENTS.get(operation, {})),
    }
    value = {
        "command_id": "Client:Box/One", "schema_version": SCHEMA_VERSION,
        "project_id": PROJECT, "operation": operation,
        "lease_id": "read.example" if operation == catalog.READ else "writer.example",
        "fencing_epoch": 0 if operation == catalog.READ else 1,
        "expected_revision": REVISION, "target": {"stable_id": catalog.TARGET},
        "payload": payload, "deadline_ms": 1_900_000_000_000,
    }
    value.update(changes)
    value["payload_hash"] = "sha256:" + hashlib.sha256(canonical_bytes(value["payload"])).hexdigest()
    return value


class WriteCatalogTests(unittest.TestCase):
    def validate(self, value):
        return catalog.validate_request(value, project_id=PROJECT, source_sha256=SOURCE)

    def translate(self, value, **kwargs):
        return catalog.translate(self.validate(value), binding=kwargs.get("binding", BINDING),
                                 session_id=kwargs.get("session_id", SESSION))

    def test_discovery_roundtrips_and_write_advertising_is_explicit(self):
        default = catalog.discovery(PROJECT, source_sha256=SOURCE)
        writer = catalog.discovery(PROJECT, source_sha256=SOURCE, readable=False, writable=True)
        self.assertEqual([cap.operation for cap in default.capabilities], [catalog.READ])
        self.assertEqual({cap.operation for cap in writer.capabilities}, catalog.WRITE_OPERATIONS)
        self.assertTrue(all(cap.write_scopes == ("blender.scene.write",) for cap in writer.capabilities))
        self.assertEqual(Discovery.from_dict(writer.as_dict()), writer)
        self.assertEqual(writer.schema_digest, catalog.CATALOG_DIGEST)
        self.assertEqual(catalog.discovery(PROJECT, source_sha256=SOURCE, readable=False).capabilities, ())
        self.assertTrue({"control.lookup", "control.stop"} <= catalog.OPERATIONS)

    def test_existing_readonly_catalog_remains_readonly(self):
        self.assertEqual(readonly.OPERATIONS, {catalog.READ, "control.lookup", "control.stop"})
        self.assertNotEqual(readonly.CATALOG_DIGEST, catalog.CATALOG_DIGEST)
        with self.assertRaisesRegex(ValidationError, "UNSUPPORTED_OPERATION"):
            readonly.validate_request(body(), project_id=PROJECT, source_sha256=SOURCE)

    def test_descriptor_persistence_and_diff_claims_are_bounded(self):
        self.assertTrue(catalog.DESCRIPTOR["integration_candidate"])
        self.assertFalse(catalog.DESCRIPTOR["public_ack"])
        self.assertTrue(catalog.DESCRIPTOR["native_checkpoint_protected_publication"])
        for operation in catalog.WRITE_OPERATIONS:
            declaration = catalog.DESCRIPTOR["operations"][operation]
            self.assertFalse(declaration["scene_state_durable"])
            self.assertFalse(declaration["public_ack"])
            self.assertTrue(declaration["diff_supported"])
            self.assertEqual(declaration["live_edits_unsaved"], operation in catalog.EDIT_OPERATIONS)
        self.assertEqual(catalog.DESCRIPTOR["external_inputs"], [])

    def test_discovery_has_no_mutable_limit_or_descriptor_authority(self):
        first = catalog.discovery(PROJECT, source_sha256=SOURCE)
        first.limits["max_commands"] = 9999
        first.capabilities[0].limits["max_pending"] = 9999
        with patch.dict(catalog.DESCRIPTOR["limits"], max_commands=9999):
            second = catalog.discovery(PROJECT, source_sha256=SOURCE)
        self.assertEqual(second.limits["max_commands"], ledger.MAX_COMMANDS)
        self.assertEqual(second.capabilities[0].limits["max_pending"], 1)

    def test_source_project_and_visibility_types_are_validated(self):
        for changes in ({"source_sha256": "unknown"}, {"readable": 1}, {"writable": "yes"}):
            kwargs = {"source_sha256": SOURCE, **changes}
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                catalog.discovery(PROJECT, **kwargs)
        with self.assertRaisesRegex(ValidationError, "INVALID_PROJECT"):
            catalog.discovery("../other", source_sha256=SOURCE)

    def test_request_roundtrip_detaches_nested_context_and_arguments(self):
        incoming = body()
        request = self.validate(incoming)
        incoming["payload"]["arguments"]["size"][0] = 99
        incoming["payload"]["expected_context"]["selected_ids"].clear()
        self.assertEqual(request.payload["arguments"]["size"], [1, 2, 3])
        self.assertEqual(request.payload["expected_context"]["selected_ids"], ["box"])
        self.assertEqual(Request.from_json(canonical_bytes(request.as_dict())), request)

    def test_real_validators_accept_all_translations_and_ledger_binds_exact_bytes(self):
        for operation in sorted(catalog.WRITE_OPERATIONS | {catalog.READ}):
            with self.subTest(operation=operation):
                request = self.validate(body(operation))
                raw = catalog.translate(request, binding=BINDING, session_id=SESSION)
                native = parse_json(raw)
                intent = ledger.make_intent(BINDING, SESSION, request, native)
                self.assertEqual(ledger.unchunk(intent["native_chunks"], catalog.queue.c.MAX_BYTES), raw)
                self.assertEqual(native["command_id"], ledger.private_alias(BINDING, SESSION, request.command_id))
                self.assertEqual(ledger.validate_intent(intent, BINDING), request)
                if operation == "export.publish":
                    self.assertEqual(publication_state.validate_request(native), native)
                else:
                    self.assertEqual(catalog.queue.parse(raw), native)

    def test_read_translation_uses_null_native_preconditions_but_requires_public_revision(self):
        native = parse_json(self.translate(body(catalog.READ)))
        self.assertIsNone(native["expected_revision"])
        self.assertIsNone(native["expected_context"])
        self.assertEqual(native["payload"], {})
        with self.assertRaisesRegex(ValidationError, "INVALID_REVISION"):
            self.validate(body(catalog.READ, expected_revision="unknown"))

    def test_save_slots_cannot_be_selected_by_client(self):
        for operation, slot in (("scene.save", "fixture"), ("checkpoint.save", "checkpoint")):
            native = parse_json(self.translate(body(operation)))
            self.assertEqual(native["operation"], "checkpoint.save")
            self.assertEqual(native["payload"], {"slot": slot})
            for arguments in ({"slot": slot}, {"path": "other.blend"}, {"slot": "../outside"}):
                with self.subTest(operation=operation, arguments=arguments), self.assertRaises(ValidationError):
                    self.validate(body(operation, payload={"expected_context": CONTEXT, "arguments": arguments}))

    def test_export_is_private_publication_request_not_ui_export_command(self):
        raw = self.translate(body("export.publish"))
        native = parse_json(raw)
        self.assertEqual(set(native), {"schema", "command_id", "expected_revision", "expected_context"})
        self.assertEqual(native["schema"], publication_state.SCHEMA)
        with self.assertRaises(catalog.queue.c.Rejected):
            catalog.queue.parse(raw)
        context = dict(CONTEXT, mode="EDIT_MESH")
        with self.assertRaisesRegex(ValidationError, "PUBLICATION_OBJECT_MODE_REQUIRED"):
            self.validate(body("export.publish", payload={"expected_context": context, "arguments": {}}))

    def test_full_public_identifier_alias_is_not_prefix_truncation_or_direct_forward(self):
        common = "A" * 126 + ":"
        left = parse_json(self.translate(body(command_id=common + "a")))["command_id"]
        right = parse_json(self.translate(body(command_id=common + "b")))["command_id"]
        other_session = parse_json(self.translate(body(command_id=common + "a"),
                                                  session_id="session." + "f" * 32))["command_id"]
        self.assertEqual(len({left, right, other_session}), 3)
        self.assertRegex(left, r"^client-[0-9a-f]{40}$")
        self.assertLessEqual(len(left), 48)

    def test_translation_requires_exact_binding_and_session(self):
        request = self.validate(body())
        with self.assertRaises(ValidationError):
            catalog.translate(request, binding={}, session_id=SESSION)
        with self.assertRaises(ValidationError):
            catalog.translate(request, binding=BINDING, session_id="forged-session")
        wrong_catalog = ledger.LedgerBinding(PROJECT, BINDING.generation, SOURCE,
                                             readonly.CATALOG_DIGEST, BINDING.owner_pin_sha256)
        with self.assertRaisesRegex(ValidationError, "CATALOG_MISMATCH"):
            catalog.translate(request, binding=wrong_catalog, session_id=SESSION)
        other = ledger.LedgerBinding("blender.other", BINDING.generation, SOURCE,
                                     catalog.CATALOG_DIGEST, BINDING.owner_pin_sha256)
        with self.assertRaisesRegex(ValidationError, "PROJECT_MISMATCH"):
            catalog.translate(request, binding=other, session_id=SESSION)

    def test_translation_revalidates_mutated_frozen_request(self):
        request = self.validate(body())
        request.payload["arguments"]["size"][0] = -1
        with self.assertRaises(ValidationError):
            catalog.translate(request, binding=BINDING, session_id=SESSION)

    def test_schema_digest_payload_hash_and_extra_fields_fail(self):
        for changes in ({"schema_version": "unknown"}, {"digest": "sha256:" + "0" * 64},
                        {"payload_hash": "sha256:" + "0" * 64}, {"raw_python": "print(1)"}):
            incoming = body()
            incoming.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.validate(incoming)

    def test_unsupported_operations_and_controls_cannot_enter_data_translation(self):
        for operation in ("object.delete", "file.open", "export.prepare", "control.lookup", "control.stop"):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValidationError, "UNSUPPORTED_OPERATION"):
                self.validate(body(operation))
        for operation in ("open_lane", "open_lane.python"):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValidationError, "UNSUPPORTED_OPEN_LANE"):
                self.validate(body(operation))

    def test_wrong_project_target_and_paths_reject(self):
        cases = [body(project_id="blender.other"), body(target={"stable_id": "blender.foreign"})]
        cases += [body(target={"path": path}) for path in
                  ("scene.blend", "../outside.blend", "C:/artist/scene.blend", "//server/artist.blend")]
        for incoming in cases:
            with self.subTest(target=incoming["target"]), self.assertRaises(ValidationError):
                self.validate(incoming)
        for identifier in ("../box", "C:/box", "box.py", "box:stream", "BOX", "é", "x" * 49):
            payload = {"expected_context": CONTEXT, "arguments": {"object_id": identifier, "size": [1, 1, 1]}}
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                self.validate(body(payload=payload))

    def test_payload_envelope_and_native_fields_are_exact(self):
        for payload in ({}, {"arguments": ARGUMENTS["mesh.create_box"]},
                        {"expected_context": CONTEXT, "arguments": {}, "path": "fixture.blend"},
                        {"expected_context": CONTEXT, "arguments": {**ARGUMENTS["mesh.create_box"], "script": "x"}},
                        {"expected_context": CONTEXT, "arguments": []}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.validate(body(payload=payload))
        with self.assertRaises(ValidationError):
            self.validate(body(catalog.READ, payload={"expected_context": CONTEXT}))

    def test_fence_and_absolute_deadline_syntax_do_not_grant_authority(self):
        for epoch in (0, -1, True, 1.0, 1.5, 2**53):
            incoming = body()
            incoming["fencing_epoch"] = epoch
            with self.subTest(epoch=epoch), self.assertRaises(ValidationError):
                self.validate(incoming)
        for deadline in (0, -1, True, "1900000000000", 2**53, 1.0, 1.5):
            incoming = body()
            incoming["deadline_ms"] = deadline
            with self.subTest(deadline=deadline), self.assertRaises(ValidationError):
                self.validate(incoming)
        with self.assertRaisesRegex(ValidationError, "READ_LEASE_REQUIRED"):
            self.validate(body(catalog.READ, fencing_epoch=1))
        # Expiry is an owner/native-clock decision; syntax helpers do not read a clock.
        self.assertEqual(self.validate(body(deadline_ms=1)).deadline_ms, 1)

    def test_context_shape_selection_mode_and_identifiers_are_native_validated(self):
        invalid = [None, {}, dict(CONTEXT, mode="SCULPT"), dict(CONTEXT, active_id=True),
                   dict(CONTEXT, selected_ids=["box", "box"]),
                   dict(CONTEXT, selected_ids=["z", "a"]),
                   dict(CONTEXT, selected_ids=["../box"]),
                   dict(CONTEXT, selected_ids=["a" + str(i) for i in range(17)]),
                   dict(CONTEXT, mode="EDIT_MESH", active_id=None),
                   dict(CONTEXT, mode="EDIT_MESH", active_id="missing"),
                   dict(CONTEXT, area="VIEW_3D")]
        for context in invalid:
            with self.subTest(context=context), self.assertRaisesRegex(ValidationError, "INVALID_PAYLOAD"):
                self.validate(body(payload={"expected_context": context, "arguments": ARGUMENTS["mesh.create_box"]}))
        self.validate(body(payload={"expected_context": dict(CONTEXT, mode="EDIT_MESH"),
                                    "arguments": ARGUMENTS["mesh.create_box"]}))

    def test_size_and_transform_vectors_reject_bad_types_lengths_and_ranges(self):
        cases = [
            ("mesh.create_box", "size", value) for value in
            ([1, 1], [True, 1, 1], ["1", 1, 1], [0, 1, 1], [1000.001, 1, 1], {})
        ]
        cases += [("object.transform.set", "location", [10000.1, 0, 0]),
                  ("object.transform.set", "rotation", [6.284, 0, 0]),
                  ("object.transform.set", "scale", [0, 1, 1])]
        for operation, field, value in cases:
            arguments = {**ARGUMENTS[operation], field: value}
            with self.subTest(operation=operation, field=field, value=value), self.assertRaises(ValidationError):
                self.validate(body(operation, payload={"expected_context": CONTEXT, "arguments": arguments}))
        self.validate(body(payload={"expected_context": CONTEXT,
                                    "arguments": {"object_id": "box", "size": [0.001, 1000, 1]}}))

    def test_material_numeric_and_identity_boundaries(self):
        for field, value in (("metallic", True), ("metallic", -0.1), ("roughness", 1.001),
                             ("roughness", "0.5"), ("base_color", [1, 1, 1, 1]),
                             ("base_color", [1.01, 0, 0]), ("material_id", "../copper")):
            arguments = {**ARGUMENTS["material.set_principled"], field: value}
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                self.validate(body("material.set_principled", payload={"expected_context": CONTEXT, "arguments": arguments}))

    def test_nonfinite_and_python_only_values_reject_before_native_serialization(self):
        for value in (float("nan"), float("inf"), -float("inf"), object()):
            incoming = body()
            incoming["payload"]["arguments"]["size"][0] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.validate(incoming)
        for field, value in (("size", (1, 2, 3)), ("size", {1, 2, 3})):
            incoming = body()
            incoming["payload"]["arguments"][field] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.validate(incoming)

    def test_history_arguments_cannot_smuggle_target_or_step_count(self):
        for operation in ("history.undo", "history.redo"):
            for arguments in ({"steps": 2}, {"object_id": "box"}, {"path": "fixture.blend"}):
                with self.subTest(operation=operation, arguments=arguments), self.assertRaises(ValidationError):
                    self.validate(body(operation, payload={"expected_context": CONTEXT, "arguments": arguments}))

    def test_public_size_depth_unicode_and_secret_limits(self):
        oversized = body()
        oversized["padding"] = "x" * 8000
        with self.assertRaisesRegex(ValidationError, "BLENDER_REQUEST_LIMIT"):
            self.validate(oversized)
        nested = body()
        value = nested["payload"]
        for _ in range(40):
            value["nested"] = {}
            value = value["nested"]
        with self.assertRaisesRegex(ValidationError, "DEPTH_LIMIT"):
            self.validate(nested)
        for name, value in (("password", "private"), ("extra", "\ud800")):
            incoming = body()
            incoming["payload"][name] = value
            with self.subTest(name=name), self.assertRaises(ValidationError):
                self.validate(incoming)

    def test_validator_and_translation_open_no_journal_or_backend(self):
        with patch.object(ledger.Journal, "__init__", side_effect=AssertionError("no storage")):
            self.assertIsInstance(self.translate(body()), bytes)


if __name__ == "__main__":
    unittest.main()
