"""Focused tests for the trusted O2 scene/resource owner seam."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


owner = _load("hh_o2_authoring_owner_test", STUDIO / "godot-addon/authoring_owner.py")
from studio.protocol import core


class AuthoringOwnerTests(unittest.TestCase):
    def setUp(self):
        node = owner.NODE_CONTRACT
        resource = owner.RESOURCE_CONTRACT
        self.revision = "sha256:" + "1" * 64
        self.project_revision = "sha256:" + "2" * 64
        nodes = (
            node.NodeState("root", None, "Node3D", "Root"),
            node.NodeState("collider", "root", "CollisionShape3D", "Collider"),
        )
        resource_nodes = tuple(resource.NodeState(row.stable_id, row.parent_id,
                                                   row.node_type, row.name) for row in nodes)
        self.node_context = node.ValidationContext(
            "project.owner", self.revision, self.project_revision, 1, "lease.owner", 7,
            5000, 1000, nodes, ())
        self.resource_context = resource.ValidationContext(
            "project.owner", self.revision, self.project_revision, 1, "lease.owner", 7,
            5000, 1000, resource_nodes, ())
        self.inventory = owner.TrustedInventory(self.node_context, self.resource_context)
        self.native_calls = []

        def compile_native(transaction):
            self.native_calls.append(transaction)
            return {"schema": "hh-godot-authoring-native-receipt-1",
                    "transaction_digest": transaction.digest,
                    "command_ids": list(transaction.command_ids),
                    "authority": 0, "public_ack": False,
                    "state_kind": "PLANNED_NOT_NATIVE",
                    "native_observed": False}

        self.author = owner.AuthoringOwner(lambda: self.inventory, compile_native)
        self.addCleanup(self.author.close)

    def request(self, operation="scene.node.create", *, command="cmd.node.1",
                target="root", expected_revision=None, lease_id=None, payload=None):
        payload = copy.deepcopy(payload or {
            "stable_id": "actor", "node_type": "CharacterBody3D", "name": "Actor",
            "properties": {"position": [0, 0, 0], "rotation": [0, 0, 0],
                            "scale": [1, 1, 1], "visible": True},
        })
        payload.setdefault("expected_generation", self.node_context.generation)
        payload.setdefault("expected_project_revision", self.project_revision)
        return core.Request(
            command_id=command, project_id=self.node_context.project_id,
            operation=operation, lease_id=lease_id or self.node_context.lease_id,
            fencing_epoch=self.node_context.fencing_epoch,
            expected_revision=expected_revision or self.revision,
            target={"stable_id": target}, payload=payload,
            payload_hash="sha256:" + hashlib.sha256(core.canonical_bytes(payload)).hexdigest(),
            deadline_ms=2000)

    def test_prepare_binds_revision_and_command_projection(self):
        transaction = self.author.prepare([self.request()])
        self.assertEqual(transaction.authority, 0)
        self.assertEqual(transaction.state_kind, "PLANNED_NOT_NATIVE")
        self.assertFalse(transaction.public_ack)
        self.assertEqual(transaction.expected_revision, self.revision)
        self.assertEqual(transaction.command_ids, ("cmd.node.1",))
        self.assertEqual(transaction.commands[0].request_digest,
                         self.request().digest)
        self.assertTrue(transaction.commands[0].projection_sha256.startswith("sha256:"))
        self.assertEqual(transaction.digest, transaction.as_dict()["transaction_digest"])

    def test_exact_prepare_and_native_retry_are_idempotent(self):
        request = self.request()
        first = self.author.prepare([request])
        retried = self.author.prepare([request])
        self.assertEqual(first, retried)
        receipt = self.author.compile_native(first)
        self.assertEqual(self.author.compile_native(first), receipt)
        self.assertEqual(len(self.native_calls), 1)

    def test_same_command_changed_payload_is_conflict(self):
        self.author.prepare([self.request()])
        changed = self.request(payload={
            "stable_id": "actor", "node_type": "CharacterBody3D", "name": "Actor",
            "properties": {"position": [4, 0, 0]},
        })
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_COMMAND_CONFLICT"):
            self.author.prepare([changed])

    def test_stale_revision_and_lease_are_rejected_by_trusted_context(self):
        stale_revision = self.request(command="cmd.stale.revision", expected_revision="sha256:" + "3" * 64)
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_STALE_REVISION"):
            self.author.prepare([stale_revision])
        stale_lease = self.request(command="cmd.stale.lease", lease_id="lease.other")
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_STALE_LEASE"):
            self.author.prepare([stale_lease])

    def test_class_and_resource_inventory_rejections_are_fail_closed(self):
        bad_class = self.request(command="cmd.bad.class", payload={
            "stable_id": "editor", "node_type": "EditorPlugin", "name": "Editor",
            "properties": {},
        })
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_CLASS_REJECTED"):
            self.author.prepare([bad_class])
        bad_resource = self.request("scene.resource.create", command="cmd.bad.resource",
            target="root", payload={"resource_id": "shape", "resource_type": "BoxShape3D",
                                     "properties": {"size": [1, 2, 3]}})
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_RESOURCE_NODE_TYPE"):
            self.author.prepare([bad_resource])

    def test_valid_node_then_resource_commands_share_one_bound_transaction(self):
        node_request = self.request(command="cmd.node.create")
        # Resource creation targets an already observed CollisionShape3D.  A
        # real owner may later use the returned recipe's ordering to update
        # the node and resource atomically.
        resource_request = self.request(
            "scene.resource.create", command="cmd.resource.create", target="collider",
            payload={"resource_id": "shape.box", "resource_type": "BoxShape3D",
                     "properties": {"size": [2, 3, 4]}})
        transaction = self.author.prepare([node_request, resource_request])
        self.assertEqual(transaction.command_ids, ("cmd.node.create", "cmd.resource.create"))
        receipt = self.author.compile_native(transaction)
        self.assertEqual(receipt["command_ids"], list(transaction.command_ids))

    def test_native_callback_must_echo_transaction_and_cannot_grant_authority(self):
        transaction = self.author.prepare([self.request()])
        self.author.close()
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_OWNER_CLOSED"):
            self.author.compile_native(transaction)

        def forged(_transaction):
            return {"transaction_digest": _transaction.digest,
                    "command_ids": list(_transaction.command_ids),
                    "authority": 1, "public_ack": True,
                    "state_kind": "PLANNED_NOT_NATIVE", "native_observed": False}
        fresh = owner.AuthoringOwner(lambda: self.inventory, forged)
        self.addCleanup(fresh.close)
        prepared = fresh.prepare([self.request(command="cmd.forged")])
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_NATIVE_AUTHORITY"):
            fresh.compile_native(prepared)

    def test_native_unknown_transaction_and_bad_inventory_fail_closed(self):
        prepared = self.author.prepare([self.request(command="cmd.unknown.base")])
        unknown = owner.AuthoringTransaction(
            prepared.schema, prepared.profile, prepared.authority, prepared.state_kind,
            prepared.public_ack, prepared.project_id, prepared.expected_revision,
            prepared.project_revision, prepared.generation, prepared.lease_id,
            prepared.fencing_epoch, prepared.command_ids, prepared.commands,
            "sha256:" + "f" * 64)
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_TRANSACTION_UNKNOWN"):
            self.author.compile_native(unknown)
        wrong_resource = owner.RESOURCE_CONTRACT.ValidationContext(
            "project.other", self.revision, self.project_revision, 1, "lease.owner", 7,
            5000, 1000, self.resource_context.nodes, ())
        broken = owner.AuthoringOwner(lambda: owner.TrustedInventory(
            self.node_context, wrong_resource), lambda _tx: {})
        self.addCleanup(broken.close)
        with self.assertRaisesRegex(owner.AuthoringOwnerError, "AUTHORING_INVENTORY_MISMATCH"):
            broken.prepare([self.request(command="cmd.bad.inventory")])


if __name__ == "__main__":
    unittest.main()
