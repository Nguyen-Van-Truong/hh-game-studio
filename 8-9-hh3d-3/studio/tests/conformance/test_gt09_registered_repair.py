"""Tests for the registered K9 repair scenario orchestration."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("run_gt09_registered_repair.py")
spec = importlib.util.spec_from_file_location("gt09_registered_repair", MODULE)
assert spec and spec.loader
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def observed(fixture: str = "room") -> dict:
    if fixture == "arena":
        root_type, target, node_type, before, after = "Node2D", "player", "CharacterBody2D", [0, 0], [32, 174]
    else:
        root_type, target, node_type, before, after = "Node3D", "avatar", "CharacterBody3D", [0, 0, 0], [2, 0, 0]
    return {
        "authority": 0, "public_ack": False, "native_observed": True,
        "profile": repair._OWNER.PROFILE,
        "profile_catalog_digest": "sha256:" + "a" * 64,
        "source_closure_sha256": "sha256:" + "b" * 64,
        "input_trace": {"fps": 60, "seed": 17, "frames": []},
        "snapshot": {"nodes": [
            {"stable_id": "root", "parent_id": None, "node_type": root_type,
             "name": "Root", "properties": {"position": before}},
            {"stable_id": target, "parent_id": "root", "node_type": node_type,
             "name": target.title(), "properties": {"position": before}},
        ], "resources": []},
        "seeded_faults": [{"kind": "scene", "target_stable_id": target,
                           "property": "position", "before": before, "after": after}],
    }


class RegisteredRepairTests(unittest.TestCase):
    def test_dry_run_plans_registered_route_and_stays_open(self):
        report = repair.main(["--fixture", "room", "--run-id", "gt09-registered-repair-test", "--dry-run"])
        self.assertEqual(report, 2)
        batch = repair.build_repair_batch(fixture="room", observed={"authority": 0, "public_ack": False})
        self.assertEqual(batch["status"], "OPEN")
        self.assertTrue(any(row["code"] == "NATIVE_OBSERVATION_REQUIRED" for row in batch["gaps"]))

    def test_seeded_scene_fault_prepares_unique_registered_command(self):
        batch = repair.build_repair_batch(fixture="room", observed=observed())
        self.assertEqual(batch["status"], "READY")
        self.assertEqual(batch["commands"][0]["operation"], "scene.node.update")
        self.assertEqual(batch["commands"][0]["command_id"], "repair.room.scene.1")

    def test_script_and_resource_faults_are_explicit_gaps(self):
        value = observed("arena")
        value["seeded_faults"] = [
            {"kind": "resource", "resource_id": "shape.player"},
            {"kind": "script", "path": "scripts/player_controller.gd"},
        ]
        batch = repair.build_repair_batch(fixture="arena", observed=value)
        self.assertEqual(batch["commands"], [])
        codes = {row["code"] for row in batch["gaps"]}
        self.assertIn("REGISTERED_RESOURCE_ROUTE_DISABLED", codes)
        self.assertIn("REGISTERED_SCRIPT_ROUTE_DISABLED", codes)

    def test_missing_replay_and_checkpoint_never_promote_scene_batch(self):
        value = observed()

        def execute(transaction, admission, handoff):
            return {
                "transaction_digest": transaction.digest,
                "command_ids": list(transaction.command_ids),
                "authority": 0,
                "public_ack": False,
                "native_observed": True,
                "state_kind": repair._OWNER.STATE_KIND,
                "lease_id": admission.lease_id,
                "fencing_epoch": admission.fencing_epoch,
                "native_process": {"exit_code": 0, "timed_out": False},
                "blender_handoff": handoff.as_dict(),
                "readback_ack": True,
                "catalog_commands_executed": [
                    {"command_id": command.command_id,
                     "projection_sha256": command.projection_sha256,
                     "verified": True, "readback": {}}
                    for command in transaction.commands
                ],
            }

        result = repair.run_scenario(fixture="room", observed=value, execute=execute,
                                     run_id="gt09-registered-repair-test")
        self.assertEqual(result["status"], "OPEN")
        codes = {row["code"] for row in result["gaps"]}
        self.assertIn("REGISTERED_REPLAY_CALLBACK_MISSING", codes)
        self.assertIn("REGISTERED_CHECKPOINT_CALLBACK_MISSING", codes)
        self.assertIn("REGISTERED_SCRIPT_ROUTE_DISABLED", codes)


if __name__ == "__main__":
    unittest.main()
