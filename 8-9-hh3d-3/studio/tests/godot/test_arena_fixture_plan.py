"""Pure composition tests for the detached 2D arena fixture plan."""
import unittest

from studio.protocol.core import ValidationError, canonical_bytes, parse_json
from studio.tests.godot import arena_fixture_plan as plan


class ArenaFixturePlanTests(unittest.TestCase):
    def test_plan_is_canonical_detached_and_hash_bound(self):
        value = plan.build_plan()
        self.assertEqual(value, parse_json(canonical_bytes(value)))
        self.assertEqual(value["canonical_sha256"], plan._sha({k: v for k, v in value.items()
                         if k != "canonical_sha256"}))
        self.assertEqual(value["schema"], plan.SCHEMA)
        self.assertEqual(value["execution"], plan.DETACHED_MODE)
        self.assertEqual((value["authority"], value["runtime_authorized"],
                          value["native_observed"]), (0, False, False))

    def test_tilemap_platform_cells_are_validated_and_hash_bound(self):
        tilemap = plan.build_plan()["tilemap"]
        self.assertEqual(tilemap["profile"], "hh-godot-tilemap-cell-1")
        self.assertEqual(tilemap["cell_count"], 9)
        self.assertIn([2, 5], tilemap["cells"])
        self.assertEqual(len({row["projection_sha256"] for row in tilemap["commands"]}), 9)
        self.assertEqual(tilemap["execution"], plan.DETACHED_MODE)
        self.assertFalse(any(row["projection"].get("native_verified") for row in tilemap["commands"]))

    def test_edges_cover_pickup_bot_and_lifecycle_inputs(self):
        edges = plan.build_plan()["edges"]
        self.assertEqual(edges["command_count"], 8)
        operations = [row["operation"] for row in edges["commands"]]
        self.assertEqual(operations.count("scene.signal.connect"), 3)
        self.assertEqual(operations.count("input.action.define"), 3)
        actions = {row["projection"]["after"]["action_name"] for row in edges["commands"]
                   if row["operation"] == "input.action.define"}
        self.assertEqual(actions, {"arena_pause", "arena_restart", "arena_respawn"})
        self.assertEqual(edges["execution"], plan.DETACHED_MODE)

    def test_gameplay_source_references_are_typed_and_not_observed(self):
        gameplay = plan.build_plan()["gameplay"]
        self.assertEqual(gameplay["command_count"], 3)
        self.assertEqual({row["projection"]["behavior_id"] for row in gameplay["commands"]},
                         {"player_controller", "pickup_controller", "bot_controller"})
        self.assertEqual(len(gameplay["source_references"]), 4)
        self.assertTrue(all(row["typed"] and row["native_observed"] is False
                            and row["source_bytes_observed"] is False
                            and row["execution"] == plan.DETACHED_MODE
                            for row in gameplay["source_references"]))
        lifecycle = next(row for row in gameplay["source_references"] if row["owner"] == "root")
        self.assertEqual(set(lifecycle["semantics"]), {"pause", "restart", "respawn"})

    def test_rebuild_is_reproducible(self):
        self.assertEqual(plan.build_plan(), plan.build_plan())

    def test_offline_verifier_accepts_only_the_frozen_plan(self):
        value = plan.build_plan()
        self.assertEqual(plan.validate_plan(value), value)
        altered = dict(value)
        altered["unexpected"] = True
        with self.assertRaisesRegex(ValidationError, "ARENA_PLAN_UNKNOWN_FIELD"):
            plan.validate_plan(altered)

    def test_offline_verifier_rejects_tampered_projection_hash(self):
        value = plan.build_plan()
        altered = parse_json(canonical_bytes(value))
        altered["edges"]["commands"][0]["projection_sha256"] = "sha256:" + "0" * 64
        altered["canonical_sha256"] = plan._sha({k: altered[k] for k in altered
                                                   if k != "canonical_sha256"})
        with self.assertRaisesRegex(ValidationError, "ARENA_PLAN_PROJECTION"):
            plan.validate_plan(altered)

    def test_validator_rejection_is_not_hidden_by_composition(self):
        value = plan.build_plan()
        altered = value["tilemap"]["commands"][0]["request"]
        altered["payload"]["cell"] = [99999, 0]
        with self.assertRaises(ValidationError):
            plan._TILEMAP.validate_request(altered,
                plan._TILEMAP.ValidationContext(
                    value["admission"]["project_id"], value["admission"]["revision"],
                    value["admission"]["project_revision"], 1,
                    value["admission"]["lease_id"], 1, 30000, 1000,
                    (plan._TILEMAP.NodeState("root", None, "Node2D", "Arena"),
                     plan._TILEMAP.NodeState("platforms", "root", "TileMapLayer", "Platforms")),
                    (plan._TILEMAP.TileSourceState(0, value["tilemap"]["source"]["atlas_revision"],
                                                    ((0, 0), (1, 0)), (0,)),)))


if __name__ == "__main__":
    unittest.main()
