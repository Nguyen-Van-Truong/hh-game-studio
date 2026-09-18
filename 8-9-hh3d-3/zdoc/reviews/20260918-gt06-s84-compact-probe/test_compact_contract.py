"""Synthetic published-census contract checks; do not execute/claim Godot proof."""
import copy
import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("compact_contract", BASE / "check_compact_snapshots.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


def baseline():
    return {"collector_variant": "compact_ids_summaries_v1", "sequence": 0, "run_id": "synthetic", "pid": 123,
        "retained_ordinary_descriptors": 0, "ordinary_baseline_content_changes_observed": False,
        "counters_before": {"objects": 5}, "counters_after": {"objects": 5},
        "counters_equal_across_collection": True, "inventory_count": 3,
        "class_counts": {"Tree": 1, "TreeItem": 1, "Resource": 1}, "owner_tree_item_counts": {"1": 1},
        "retained_identity_count": 3, "retained_summary_count": 1, "unattributed_object_count": 2,
        "initial_id_classes": {"1": "Tree", "2": "TreeItem", "-7": "Resource"},
        "added": [{"id": "1", "class": "Tree", "name": "Editor"}], "removed": [], "changed": []}


class CompactContractTests(unittest.TestCase):
    def test_baseline_negative_ids_are_inventory_not_growth(self):
        report = C.reconstruct([baseline()])
        self.assertIsNone(report["snapshots"][0]["delta"])
        self.assertEqual(report["snapshots"][0]["reachable"], 3)
        self.assertFalse(report["ordinary_content_changes_observed"])
        self.assertFalse(report["godot_execution_verified"])

    def test_churn_and_objectdb_residual_are_separate(self):
        first = baseline()
        second = copy.deepcopy(first)
        second.update(sequence=1, initial_id_classes={}, added=[{"id": "3", "class": "TreeItem", "owner_tree_id": "1"}],
            removed=[{"id": "2", "class": "TreeItem", "still_valid": True,
                      "old_metadata_available": False, "old_metadata_scope": "not_retained"}],
            changed=[{"id": "1", "class": "Tree", "name": "RenamedEditor"}], unattributed_object_count=3)
        second["counters_before"]["objects"] = second["counters_after"]["objects"] = 6
        delta = C.reconstruct([first, second])["snapshots"][1]["delta"]
        self.assertEqual((delta["added_count"], delta["removed_count"], delta["changed_summary_count"]), (1, 1, 1))
        self.assertEqual((delta["objectdb_net"], delta["reachable_net"], delta["unattributed_net"]), (1, 0, 1))
        self.assertEqual(delta["owner_tree_count_net"], {})
        self.assertEqual(delta["removed_still_valid"], ["2"])
        self.assertEqual(delta["removed_ids_with_unknown_prior_metadata"], ["2"])

    def test_added_negative_id_then_unknown_old_metadata_removal(self):
        first = baseline()
        second = copy.deepcopy(first)
        second.update(sequence=1, initial_id_classes={}, inventory_count=4, retained_identity_count=4,
            added=[{"id": "-8", "class": "Resource", "resource_path": "res://new.tres"}])
        second["class_counts"]["Resource"] = 2
        second["counters_before"]["objects"] = second["counters_after"]["objects"] = 6
        third = copy.deepcopy(first)
        third.update(sequence=2, initial_id_classes={}, added=[], removed=[{"id": "-8", "class": "Resource",
            "still_valid": False, "old_metadata_available": False, "old_metadata_scope": "not_retained"}])
        report = C.reconstruct([first, second, third])["snapshots"]
        self.assertEqual(report[1]["delta"]["class_net"], {"Resource": 1})
        self.assertEqual(report[2]["delta"]["class_net"], {"Resource": -1})
        self.assertEqual(report[2]["delta"]["removed_ids_with_unknown_prior_metadata"], ["-8"])

    def test_counter_drift_rejected(self):
        point = baseline()
        point["counters_after"]["objects"] = 6
        with self.assertRaisesRegex(ValueError, "counter drift"):
            C.reconstruct([point])

    def test_owner_counts_must_cover_treeitems(self):
        point = baseline()
        point["owner_tree_item_counts"]["1"] = 2
        with self.assertRaisesRegex(ValueError, "owner TreeItem count"):
            C.reconstruct([point])

    def test_ordinary_content_change_claim_rejected(self):
        first = baseline()
        second = copy.deepcopy(first)
        second.update(sequence=1, initial_id_classes={}, added=[], changed=[{"id": "-7", "class": "Resource"}])
        with self.assertRaisesRegex(ValueError, "outside summary coverage"):
            C.reconstruct([first, second])

    def test_malformed_signed_id_rejected(self):
        for value in ("0", "-0", "+1", "01", "-01", "-1.0", str(2**63), str(-(2**63) - 1)):
            self.assertFalse(C.valid_id(value), value)
        for value in ("1", "-1", str(-(2**63)), str(2**63 - 1)):
            self.assertTrue(C.valid_id(value), value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
