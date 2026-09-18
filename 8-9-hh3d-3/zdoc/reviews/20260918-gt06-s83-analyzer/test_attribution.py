"""Focused synthetic tests. No studio runtime import or native process launch."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("s83_attribution", BASE / "analyze_attribution.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-", dir=BASE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = {"id": "1", "class": "Tree", "name": "Inspector", "path": "/root/Inspector", "visible": True}
        self.item = {"id": "2", "class": "TreeItem", "owner_tree_id": "1", "relation": "tree_item:1"}
        counters = {"objects": 5, "cached_resources": 1, "tree_nodes": 1, "orphan_nodes": 0}
        self.baseline = {
            "schema_id": "hh-studio.object-attribution-diagnostic", "schema_version": "1.0.0",
            "run_id": A.RUN, "pid": 99, "sequence": 0, "label": "joint_baseline", "batch": 4,
            "formal_acceptance": False, "full_benchmark": False, "inventory_complete_objectdb": False,
            "initial_inventory_ids_omitted": False, "counters_before": counters,
            "counters_after": copy.deepcopy(counters), "counters_equal_across_collection": True,
            "inventory_count": 3, "class_counts": {"Tree": 1, "TreeItem": 1, "Resource": 1},
            "owner_tree_item_counts": {"1": 1}, "unattributed_object_count": 2,
            "initial_id_classes": {"1": "Tree", "2": "TreeItem", "-7": "Resource"},
            "added": [self.tree], "removed": [], "changed": [], "inventory_duration_us": 10, "mono_us": 10,
        }
        self.publish_point(self.baseline)

    def write(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def publish_point(self, point):
        batch = point["batch"]
        self.write(A.OUT + f"object-{point['sequence']:04d}.json", point)
        self.write(A.OUT + f"attribution-{batch:02d}.json", {
            "run_id": A.RUN, "batch": batch, "baseline_objects": 5, "formal_acceptance": False,
            "objects_before": point["counters_before"]["objects"],
            "objects_after_publication": point["counters_after"]["objects"],
        })
        native_name, ack_name = A.OUT + f"batch-{batch:02d}.json", A.IN + f"ack-{batch:02d}.json"
        self.write(native_name, {"run_id": A.RUN, "index": batch, "pid": 99})
        native_digest = A.digest((self.root / native_name).read_bytes())
        self.write(ack_name, {"run_id": A.RUN, "batch_index": batch, "native_batch_sha256": native_digest,
                              "source_closure_sha256": A.SOURCE, "profile_sha256": A.PROFILE})
        ack_raw = (self.root / ack_name).read_bytes()
        objects = {"value": point["counters_before"]["objects"], "unavailable_reason": None}
        self.write(f"joint-{batch:02d}.json", {"run_id": A.RUN, "index": batch,
            "source_closure_sha256": A.SOURCE, "profile_sha256": A.PROFILE,
            "native_batch_sha256": native_digest, "ack_ref": {
                "file": ack_name, "sha256": A.digest(ack_raw), "size_bytes": len(ack_raw)},
            "barrier_receipt": {"batch_index": batch, "ack_sha256": A.digest(ack_raw),
                "ack_size_bytes": len(ack_raw), "native_batch_sha256": native_digest, "objects": objects},
            "editor": {"native_observation": {"objects": objects}}})

    def growth(self, churn=False):
        point = copy.deepcopy(self.baseline)
        point.update(sequence=1, label="joint_growth", batch=5, mono_us=20, initial_id_classes={})
        point["counters_before"]["objects"] = point["counters_after"]["objects"] = 6
        if churn:
            point["added"] = [{**self.item, "id": "3"}]
            point["removed"] = [{**self.item, "still_valid": True}]
            point["changed"] = [{**self.tree, "name": "SceneTree"}]
            point["unattributed_object_count"] = 3
        else:
            point["added"] = [{"id": "-8", "class": "Resource", "relation": "incoming_signal_to:1"}]
            point["inventory_count"] = 4
            point["class_counts"]["Resource"] = 2
        self.publish_point(point)
        return point

    def analyze(self):
        return A.analyze_points(A.Reader(self.root), True, A.RUN, 99)

    def test_signed_ids_and_reject_malformed_or_out_of_range(self):
        for value in ("1", "-7", str(-(2**63)), str(2**63 - 1)):
            self.assertTrue(A.instance_id(value), value)
        for value in ("0", "-0", "+1", "01", "-01", " 1", "1.0", "1e3", True, 1,
                      str(2**63), str(-(2**63) - 1)):
            self.assertFalse(A.instance_id(value), value)

    def test_signed_baseline_is_not_growth(self):
        report = self.analyze()
        self.assertEqual(report["baseline_id_count"], 3)
        self.assertEqual(report["baseline_selected_descriptor_count"], 1)
        self.assertFalse(report["growth_observed"])
        self.assertIsNone(report["points"][0]["delta"])
        self.assertTrue(report["attribution_integrity_verified"])

    def test_signed_growth_reconciles_actual_counter_and_residual(self):
        self.growth()
        delta = self.analyze()["points"][1]["delta"]
        self.assertEqual((delta["objectdb_net"], delta["reachable_inventory_net"], delta["unattributed_residual_net"]), (1, 1, 0))
        self.assertEqual(delta["added_rows"][0]["id"], "-8")

    def test_churn_keeps_net_and_valid_removed_identity_distinct(self):
        self.growth(churn=True)
        delta = self.analyze()["points"][1]["delta"]
        self.assertEqual((delta["added_count"], delta["removed_count"], delta["changed_count"]), (1, 1, 1))
        self.assertEqual((delta["reachable_inventory_net"], delta["unattributed_residual_net"]), (0, 1))
        self.assertEqual(delta["removed_still_valid_count"], 1)
        self.assertEqual(delta["changed_rows"][0]["changed_fields"], ["name"])
        owner = delta["owner_tree_diff"]["rows"][0]
        self.assertEqual((owner["path"], owner["net"], owner["added"], owner["removed"]), ("/root/Inspector", 0, 1, 1))

    def test_malformed_counter_rejected(self):
        self.baseline["counters_before"]["objects"] = True
        self.publish_point(self.baseline)
        with self.assertRaisesRegex(A.Invalid, "counter objects"):
            self.analyze()

    def test_collection_counter_drift_rejected(self):
        self.baseline["counters_after"]["objects"] = 6
        self.publish_point(self.baseline)
        with self.assertRaisesRegex(A.Invalid, "changed across collection"):
            self.analyze()

    def test_class_census_mismatch_rejected(self):
        self.baseline["initial_id_classes"]["-7"] = "OtherResource"
        self.publish_point(self.baseline)
        with self.assertRaisesRegex(A.Invalid, "reconstructed ID/class census"):
            self.analyze()

    def test_digest_tamper_rejected(self):
        path = self.root / (A.IN + "ack-04.json")
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(A.Invalid, "reference digest/size mismatch"):
            self.analyze()

    def test_wrong_publication_run_rejected(self):
        path = A.OUT + "attribution-04.json"
        value = json.loads((self.root / path).read_bytes())
        value["run_id"] = "different-run"
        self.write(path, value)
        with self.assertRaisesRegex(A.Invalid, "publication receipt binding"):
            self.analyze()

    def test_growth_missing_publication_receipt_cannot_be_verified(self):
        self.growth()
        (self.root / (A.OUT + "attribution-05.json")).unlink()
        report = self.analyze()
        self.assertTrue(report["growth_observed"])
        self.assertFalse(report["attribution_integrity_verified"])
        self.assertIn({"sequence": 1, "code": "POST_PUBLICATION_RECEIPT_MISSING"}, report["integrity_gaps"])
        self.write("diagnostic.json", {"run_id": A.RUN, "base_source_closure_sha256": A.SOURCE,
            "profile_sha256": A.PROFILE, "formal_acceptance": False, "eligible_for_dataset": False})
        self.write("context.json", {"run_id": A.RUN, "source_closure_sha256": A.SOURCE, "profile_sha256": A.PROFILE})
        self.write("editor-host/process-start.json", {"pid": 99})
        with patch.object(A, "terminal_check", return_value={"child_primary_error": None}), \
             patch.object(A, "provenance", return_value={}), \
             patch.object(A, "full_completion", return_value={"verified": False, "joint_object_counts": []}):
            final = A.analyze(self.root, "terminal", True)
        self.assertEqual(final["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
