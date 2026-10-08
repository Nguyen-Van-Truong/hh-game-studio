"""Focused contract checks for the private registered O2 owner."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _load(name: str, relative: str):
    path = STUDIO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


owner = _load("hh_registered_owner_test", "godot-addon/registered_authoring_owner.py")
runner = _load("hh_registered_owner_runner_test", "tests/godot/run_registered_authoring_probe.py")
recipe = _load("hh_registered_owner_recipe_test", "tests/godot/saved_room_recipe.py")
from studio.protocol.core import PROTOCOL_VERSION, ValidationError, canonical_bytes


class RegisteredOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-registered-owner-")
        self.root = Path(self.temp.name)
        self.glb = self.root / "scene.glb"
        self.glb.write_bytes(b"trusted glb bytes")
        manifest = {
            "schema": "HH-BLENDER-PUBLICATION-1",
            "command_id": "client-blender-1",
            "native": {"glb_sha256": hashlib.sha256(self.glb.read_bytes()).hexdigest()},
        }
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.handoff = owner.inspect_blender_handoff(self.root)
        value = recipe.build_recipe()
        now = int(time.time() * 1000)
        self.admission = owner.make_admission(
            project_id="project.registered.room",
            revision=runner._sha(value["initial_snapshot"]),
            project_revision=value["planned_project_revision"],
            lease_id="lease.registered.room", now_ms=now, ttl_ms=120_000)
        self.recipe = value
        self.inventory = runner._inventory(value, self.admission)
        self.requests = runner._bound_requests(value, self.admission)

    def tearDown(self):
        self.temp.cleanup()

    def test_profile_is_candidate_only_and_catalog_bound(self):
        profile = owner.register_profile()
        self.assertEqual(profile.profile, owner.PROFILE)
        self.assertEqual(profile.authority, 0)
        self.assertFalse(profile.runtime_enabled)
        self.assertFalse(profile.script_enabled)
        self.assertRegex(profile.catalog_digest, r"^sha256:[0-9a-f]{64}$")

    def test_prepare_and_native_receipt_are_transaction_bound(self):
        calls = []

        def apply(transaction, admission, handoff):
            calls.append(transaction.digest)
            return {
                "transaction_digest": transaction.digest,
                "command_ids": list(transaction.command_ids),
                "authority": 0, "public_ack": False,
                "native_observed": True,
                "state_kind": owner.STATE_KIND,
                "lease_id": admission.lease_id,
                "fencing_epoch": admission.fencing_epoch,
                "blender_handoff": handoff.as_dict(),
            }

        actor = owner.RegisteredAuthoringOwner(admission=self.admission,
                                               blender=self.handoff, native_apply=apply)
        self.addCleanup(actor.close)
        transaction = actor.prepare(self.requests, inventory=self.inventory)
        self.assertEqual(len(transaction.command_ids), 14)
        self.assertEqual(transaction.authority, 0)
        receipt = actor.apply(transaction)
        self.assertTrue(receipt["native_observed"])
        self.assertEqual(actor.apply(transaction), receipt)
        self.assertEqual(calls, [transaction.digest])

    def test_changed_transaction_and_fence_are_rejected(self):
        def apply(transaction, admission, handoff):
            return {"transaction_digest": transaction.digest,
                    "command_ids": list(transaction.command_ids),
                    "authority": 0, "public_ack": False,
                    "native_observed": True, "state_kind": owner.STATE_KIND,
                    "lease_id": admission.lease_id,
                    "fencing_epoch": admission.fencing_epoch,
                    "blender_handoff": handoff.as_dict()}

        actor = owner.RegisteredAuthoringOwner(admission=self.admission,
                                               blender=self.handoff, native_apply=apply)
        self.addCleanup(actor.close)
        transaction = actor.prepare(self.requests, inventory=self.inventory)
        object.__setattr__(transaction, "fencing_epoch", transaction.fencing_epoch + 1)
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_TRANSACTION_CHANGED"):
            actor.apply(transaction)

    def test_blender_hash_or_schema_cannot_be_forged(self):
        (self.root / "scene.glb").write_bytes(b"changed")
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_HANDOFF_GLB_HASH"):
            owner.inspect_blender_handoff(self.root)

    def actor(self, callback=None, admission=None):
        callback = callback or Mock(side_effect=AssertionError("unexpected native effect"))
        actor = owner.RegisteredAuthoringOwner(admission=admission or self.admission,
                                               blender=self.handoff, native_apply=callback)
        self.addCleanup(actor.close)
        return actor

    def test_discovery_is_fixture_scoped_with_profile_version_and_digest(self):
        actor = self.actor()
        discovered = actor.discovery(project_id=self.admission.project_id)
        self.assertTrue(discovered["fixture_enabled"])
        self.assertFalse(discovered["public_runtime_enabled"])
        self.assertEqual(discovered["protocol_version"], PROTOCOL_VERSION)
        self.assertEqual(discovered["profiles"][0]["version"], 1)
        self.assertEqual(discovered["profiles"][0]["catalog_digest"], actor.profile.catalog_digest)
        self.assertEqual(actor.discovery(project_id="project.ungranted")["profiles"], [])
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "UNSUPPORTED_CLIENT_VERSION"):
            actor.discovery(project_id=self.admission.project_id, protocol_version="unsupported")
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_PROFILE_UNKNOWN"):
            actor.discovery(project_id=self.admission.project_id, profile="other")
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_FIXTURE_PROJECT"):
            self.actor(admission=replace(self.admission, project_id="project.other"))

    def test_arena_catalog_admission_has_18_ordered_commands(self):
        module = runner._ARENA
        arena = module.build_recipe()
        admission = replace(self.admission, project_id="project.registered.arena",
            lease_id="lease.registered.arena", revision=runner._sha(arena["initial_snapshot"]),
            project_revision=arena["planned_project_revision"])
        actor = self.actor(admission=admission)
        requests = runner._bound_requests(arena, admission, module)
        transaction = actor.prepare(requests, inventory=runner._inventory(arena, admission))
        self.assertEqual(len(transaction.commands), 18)
        self.assertEqual(transaction.commands[0].projection["payload"]["node_type"], "CharacterBody2D")
        self.assertEqual(transaction.commands[-1].projection["payload"]["resource_type"], "RectangleShape2D")
        self.assertEqual(actor.prepare(requests, inventory=runner._inventory(arena, admission)).digest,
                         transaction.digest)

    def test_inventory_revision_or_root_cannot_select_a_different_fixture(self):
        actor = self.actor()
        for field, value in (("revision", "sha256:" + "9" * 64), ("generation", 8)):
            changed = owner._PLANNER.TrustedInventory(
                replace(self.inventory.node_context, **{field: value}),
                replace(self.inventory.resource_context, **{field: value}))
            with self.subTest(field=field), self.assertRaisesRegex(
                    owner.RegisteredAuthoringOwnerError, "REGISTERED_INVENTORY_ADMISSION"):
                actor.prepare(self.requests, inventory=changed)
        root = owner._NODE.NodeState("root", None, "Node2D", "Arena")
        resource_root = owner._RESOURCE.NodeState("root", None, "Node2D", "Arena")
        changed = owner._PLANNER.TrustedInventory(
            replace(self.inventory.node_context, nodes=(root,)),
            replace(self.inventory.resource_context, nodes=(resource_root,)))
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_FIXTURE_ROOT"):
            actor.prepare(self.requests, inventory=changed)

    def test_retry_cannot_reorder_truncate_extend_or_change_a_batch(self):
        actor = self.actor()
        first = actor.prepare(self.requests, inventory=self.inventory)
        self.assertEqual(actor.prepare(self.requests, inventory=self.inventory), first)
        changed = copy.deepcopy(self.requests)
        changed[0]["payload"]["name"] = "Different"
        changed[0]["payload_hash"] = "sha256:" + hashlib.sha256(
            canonical_bytes(changed[0]["payload"])).hexdigest()
        # ``digest`` is a derived readback field; remove it so the trusted
        # parser recomputes the changed request identity.
        changed[0].pop("digest", None)
        for batch in (list(reversed(self.requests)), self.requests[:-1], changed):
            with self.subTest(batch=batch[0]["command_id"]), self.assertRaisesRegex(
                    owner.RegisteredAuthoringOwnerError, "AUTHORING_COMMAND_CONFLICT"):
                actor.prepare(batch, inventory=self.inventory)

    def test_callback_failure_is_uncertain_and_never_replayed(self):
        callback = Mock(side_effect=RuntimeError("lost native response"))
        actor = self.actor(callback)
        transaction = actor.prepare(self.requests, inventory=self.inventory)
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_NATIVE_CALLBACK_FAILED"):
            actor.apply(transaction)
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_RECONCILE_REQUIRED"):
            actor.apply(transaction)
        self.assertEqual(callback.call_count, 1)

    def test_malformed_receipt_is_uncertain_and_never_replayed(self):
        callback = Mock(return_value={"transaction_digest": "wrong"})
        actor = self.actor(callback)
        transaction = actor.prepare(self.requests, inventory=self.inventory)
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_NATIVE_TRANSACTION_MISMATCH"):
            actor.apply(transaction)
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, "REGISTERED_RECONCILE_REQUIRED"):
            actor.apply(transaction)
        self.assertEqual(callback.call_count, 1)

    def test_unknown_operations_classes_properties_and_bad_values_have_no_native_effect(self):
        callback = Mock(side_effect=AssertionError("unexpected native effect"))
        actor = self.actor(callback)
        mutations = [
            lambda row: row.update(operation="script_text.replace"),
            lambda row: row["payload"].update(node_type="EditorPlugin"),
            lambda row: row["payload"]["properties"].update(unknown_property=1),
            lambda row: row["payload"]["properties"].update(position="wrong"),
            lambda row: row["payload"]["properties"].update(position=[100000000, 0, 0]),
            lambda row: row["payload"]["properties"].update(position=[0, 0]),
            lambda row: row.update(expected_revision="sha256:" + "8" * 64),
            lambda row: row.update(target={"stable_id": "outside"}),
            lambda row: row["payload"]["properties"].update(motion_mode=99),
        ]
        for index, mutate in enumerate(mutations):
            requests = copy.deepcopy(self.requests)
            mutate(requests[0])
            requests[0]["payload_hash"] = "sha256:" + hashlib.sha256(
                canonical_bytes(requests[0]["payload"])).hexdigest()
            with self.subTest(index=index), self.assertRaises(ValidationError):
                actor.prepare(requests, inventory=self.inventory)
            self.assertEqual(actor._transactions, {})
        callback.assert_not_called()

    def adapter(self, actor=None, *, enabled=True, files=None):
        actor = actor or self.actor()
        profile = owner.load_fixture_host_profile(self.admission.project_id)
        files = files if files is not None else {
            'godot-addon/fixture_profile.json': profile.config_sha256,
            'godot-addon/gameplay_fixture_profile.py': profile.module_sha256}
        return owner.RegisteredAuthoringAdapter(actor, inventory=self.inventory,
            source_files=files, host_profile=profile if enabled else None)

    def test_registered_adapter_requires_host_policy_and_binds_both_catalogs(self):
        hidden = self.adapter(enabled=False)
        self.assertEqual(hidden.discovery()['profiles'], [])
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, 'FIXTURE_PROFILE_DISABLED'):
            hidden.prepare(self.requests, profile_digest='sha256:' + '0' * 64)
        client = self.adapter()
        discovery = client.discovery()
        profile = discovery['profiles'][0]
        self.assertTrue(discovery['fixture_enabled'])
        self.assertFalse(discovery['public_runtime_enabled'])
        self.assertTrue(profile['script_enabled'])
        self.assertEqual(profile['node_catalog_digest'], client.owner.profile.catalog_digest)
        self.assertNotEqual(profile['catalog_digest'], profile['node_catalog_digest'])
        self.assertEqual(client.discovery(project_id='project.other')['profiles'], [])
        self.assertEqual(len(client.prepare(self.requests,
            profile_digest=profile['catalog_digest']).commands), 14)

    def test_registered_adapter_rejects_unbound_config_and_request_identity(self):
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, 'FIXTURE_PROFILE_CLOSURE'):
            self.adapter(files={})
        callback = Mock(side_effect=AssertionError('unexpected native effect'))
        client = self.adapter(self.actor(callback))
        digest = client.discovery()['profiles'][0]['catalog_digest']
        for override, code in (
                ({'profile_digest': 'sha256:' + '0' * 64}, 'FIXTURE_PROFILE_DIGEST'),
                ({'profile_version': True}, 'FIXTURE_PROFILE_VERSION'),
                ({'profile': 'unknown'}, 'REGISTERED_PROFILE_UNKNOWN'),
                ({'protocol_version': '2.0'}, 'UNSUPPORTED_CLIENT_VERSION')):
            with self.subTest(code=code), self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, code):
                client.execute(self.requests, **({'profile_digest': digest} | override))
        callback.assert_not_called()

    def test_registered_adapter_requires_every_readback_and_caches_retry(self):
        calls = []

        def apply(transaction, admission, handoff):
            calls.append(transaction.digest)
            data = runner._NATIVE.make_input(transaction, admission, self.recipe['root'],
                                            owner._NODE.load_catalog(), {})
            rows, _ = runner._NATIVE.expected_readbacks(data)
            return {'transaction_digest': transaction.digest,
                    'command_ids': list(transaction.command_ids),
                    'authority': 0, 'public_ack': False, 'native_observed': True,
                    'state_kind': owner.STATE_KIND, 'lease_id': admission.lease_id,
                    'fencing_epoch': admission.fencing_epoch, 'blender_handoff': handoff.as_dict(),
                    'readback_ack': True, 'catalog_commands_executed': rows}

        actor = self.actor(apply)
        client = self.adapter(actor)
        identity = {'profile_digest': client.discovery()['profiles'][0]['catalog_digest']}
        receipt = client.execute(self.requests, **identity)
        self.assertEqual(client.execute(self.requests, **identity), receipt)
        self.assertEqual(len(calls), 1)
        stored = actor._receipts[calls[0]]
        stored['catalog_commands_executed'][0]['verified'] = False
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError, 'REGISTERED_COMMAND_READBACK'):
            client.execute(self.requests, **identity)
        self.assertEqual(len(calls), 1)

    def test_registered_script_route_is_typed_idempotent_and_native_bound(self):
        """The fixture script seam delegates to a durable source owner."""
        profile = owner.load_fixture_host_profile(self.admission.project_id)
        current = self.admission.project_revision
        calls = []

        class SourceOwner:
            _project_revision = current
            project_id = "project.registered.room"

        class SourceAdapter:
            _owner = SourceOwner()

            def profile_discovery(self, **_kwargs):
                return {"fixture_enabled": True, "public_runtime_enabled": False,
                        "authority": 0, "public_ack": False,
                        "profiles": [profile.as_dict()]}

            def execute(self, request, *, grant, lease):
                calls.append(request.digest)
                if request.operation == "gameplay-source.inspect":
                    return {"schema": "hh-gameplay-source-readback-1",
                            "project_id": self._owner.project_id,
                            "project_revision": current,
                            "selected_revision": current,
                            "source_sha256": "sha256:" + "1" * 64,
                            "public_ack": False}
                return {"status": "READBACK_ACK", "command_id": request.command_id,
                        "request_digest": request.digest, "readback_ack": True,
                        "public_ack": False, "native_run_id": "source-native-1"}

        actor = self.actor()
        route = owner.RegisteredScriptRoute(actor, adapter=SourceAdapter(),
                                            grant=object(), lease=object(),
                                            host_profile=profile)
        discovered = route.discovery()
        self.assertEqual(discovered["schema"], owner.SCRIPT_ROUTE_SCHEMA)
        self.assertEqual(discovered["operations"], list(owner.SCRIPT_OPERATIONS))
        self.assertEqual(discovered["authority"], 0)
        self.assertFalse(discovered["public_ack"])
        payload = {"profile": owner.PROFILE, "profile_version": profile.version,
                   "profile_digest": profile.as_dict()["catalog_digest"],
                   "entrypoint": "scripts/fixture_actor.gd",
                   "expected_project_revision": current,
                   "source_files": {"scripts/fixture_actor.gd": "ZXh0ZW5kcyBOb2RlMwo="}}
        request = {
            "command_id": "registered.script.1",
            "project_id": self.admission.project_id,
            "operation": "gameplay-source.publish",
            "lease_id": self.admission.lease_id,
            "fencing_epoch": self.admission.fencing_epoch,
            "expected_revision": current,
            "target": {"path": "scripts/fixture_actor.gd"},
            "payload": payload,
            "payload_hash": "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            "deadline_ms": self.admission.lease_expires_ms,
            "schema_version": self.requests[0]["schema_version"],
        }
        first = route.execute(request)
        self.assertTrue(first["native_observed"])
        self.assertEqual(first["status"], "READBACK_ACK")
        self.assertEqual(first["command_id"], request["command_id"])
        self.assertEqual(route.execute(request), first)
        self.assertEqual(len(calls), 1)
        inspect_payload = {"profile": owner.PROFILE,
                           "profile_version": profile.version,
                           "profile_digest": profile.as_dict()["catalog_digest"]}
        inspect_request = {**request, "command_id": "registered.script.inspect",
                           "operation": "gameplay-source.inspect",
                           "payload": inspect_payload,
                           "payload_hash": "sha256:" + hashlib.sha256(
                               canonical_bytes(inspect_payload)).hexdigest()}
        inspected = route.execute(inspect_request)
        self.assertEqual(inspected["status"], "READBACK_ACK")
        self.assertFalse(inspected["native_observed"])
        self.assertTrue(inspected["readback_observed"])
        self.assertEqual(route.execute(inspect_request), inspected)
        self.assertEqual(len(calls), 2)
        changed = dict(request)
        changed["payload"] = {**payload, "source_files": {
            "scripts/fixture_actor.gd": "ZXh0ZW5kcyBOb2RlMgo="}}
        changed["payload_hash"] = "sha256:" + hashlib.sha256(
            canonical_bytes(changed["payload"])).hexdigest()
        with self.assertRaisesRegex(owner.RegisteredAuthoringOwnerError,
                                    "REGISTERED_SCRIPT_COMMAND_CONFLICT"):
            route.execute(changed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
