"""Focused contract checks for the private registered O2 owner."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
