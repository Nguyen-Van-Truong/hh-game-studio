"""Offline mutation tests against the retained S90 raw prefix; never write raw.

Run with Python -B to avoid generating bytecode in the evidence directory.
The original bytes remain the fixture; mutations exist only in reader memory.
"""
from pathlib import Path
import json
import unittest

import analyze_lifecycle as audit


RAW = Path(__file__).resolve().parents[3] / "studio/.local/reviews" / audit.RUN
LIFE = "project/benchmark/out/lifecycle-02.json"


class MutatedReader(audit.RawReader):
    def __init__(self, replacements=None, missing=()):
        super().__init__(RAW)
        self.replacements = replacements or {}
        self.missing = set(missing)

    def exists(self, name):
        return name not in self.missing and super().exists(name)

    def read(self, name):
        audit.need(name not in self.missing, "missing paired artifact: " + name)
        if name not in self.replacements:
            return super().read(name)
        raw = self.replacements[name]
        self.total += len(raw)
        audit.need(self.total <= audit.MAX_TOTAL_BYTES, "total read bound exceeded")
        self.artifacts[name] = {"sha256": audit.sha(raw), "size_bytes": len(raw)}
        return raw


def changed(name, **fields):
    obj = json.loads((RAW / name).read_bytes())
    obj.update(fields)
    return {name: audit.encoded(obj)}


class LifecycleAuditTests(unittest.TestCase):
    def reject(self, replacements=None, missing=(), pattern=None):
        with self.assertRaisesRegex(audit.InvalidEvidence, pattern or "."):
            audit.analyze_reader(MutatedReader(replacements, missing))

    def test_retained_prefix_is_five_warmup_pairs_and_never_acceptance(self):
        result = audit.analyze_reader(audit.RawReader(RAW))
        self.assertEqual(result["verification_status"], "verified_partial_diagnostic_bindings")
        self.assertEqual(result["complete_lifecycle_pair_count"], 5)
        self.assertEqual(result["warmup_pair_count"], 5)
        self.assertEqual(result["measured_pair_count"], 0)
        self.assertEqual(result["eligible_dataset_sample_count"], 0)
        self.assertEqual(result["pending_prefix"][0]["index"], 5)
        self.assertFalse(result["formal_acceptance"])
        self.assertFalse(result["eligible_for_dataset"])
        self.assertFalse(result["fullrun_pass"])
        self.assertFalse(result["terminal_verified"])
        self.assertIn("supervisor-return.json", result["terminal_gaps"])
        self.assertIn("editor-host/process-exit.json", result["terminal_gaps"])
        self.assertEqual(result["provenance"]["source_file_count"], 51)
        self.assertEqual(len(result["provenance"]["helper_files"]), 2)
        for row in result["lifecycle_rows"]:
            self.assertEqual(row["object_delta_close_to_release"], -1)
            self.assertEqual(row["object_delta_batch_to_fresh_ack"], 0)
            self.assertEqual(row["object_count_at_batch_publish"], 71127)
        digest = result.pop("derived_payload_sha256")
        self.assertEqual(digest, audit.sha(audit.encoded(result)))

    def test_stale_run_rejected(self):
        self.reject(changed(LIFE, run_id="gt06-s88-object-attribution-01"), pattern="run identity")

    def test_stale_batch_rejected(self):
        self.reject(changed(LIFE, batch=1), pattern="batch identity")

    def test_stale_source_binding_rejected(self):
        name = "project/benchmark/out/ready-02.json"
        self.reject(changed(name, source_closure_sha256="0" * 64), pattern="source binding")

    def test_stale_profile_binding_rejected(self):
        name = "project/benchmark/input/start-02.json"
        self.reject(changed(name, profile_sha256="0" * 64), pattern="profile binding")

    def test_phase_delta_tamper_rejected(self):
        self.reject(changed(LIFE, object_delta_close_to_release=0), pattern="phase delta")

    def test_self_consistent_tamper_cannot_replace_original_batch_counter(self):
        self.reject(changed(LIFE, object_count_at_batch_publish=71128,
                            object_delta_batch_to_fresh_ack=-1), pattern="original batch counter")

    def test_self_consistent_tamper_cannot_replace_fresh_ack_counter(self):
        self.reject(changed(LIFE, object_count_after_fresh_ack=71128,
                            object_delta_batch_to_fresh_ack=1,
                            object_delta_ack_preopen_to_fresh_ack=1), pattern="fresh ACK counter")

    def test_missing_joint_pair_rejected(self):
        self.reject(missing=("joint-02.json",), pattern="missing pair")

    def test_missing_ack_rejected(self):
        self.reject(missing=("project/benchmark/input/ack-02.json",), pattern="missing paired artifact")

    def test_stale_capture_hash_rejected(self):
        name = "batch-capture-02.json"
        obj = json.loads((RAW / name).read_bytes())
        obj["native"]["sha256"] = "0" * 64
        self.reject({name: audit.encoded(obj)}, pattern="reference hash/size")

    def test_frozen_source_file_tamper_rejected(self):
        self.reject({"source/studio/tests/replay/benchmark_native.gd": b"tampered"}, pattern="source file hash")

    def test_frozen_helper_tamper_rejected(self):
        helper = next(k for k in audit.HELPERS if k.endswith(".gd"))
        self.reject({"source/" + helper: b"tampered"}, pattern="helper hash")

    def test_effective_overlay_tamper_rejected(self):
        self.reject({"project/addons/hh_benchmark/benchmark_native.gd": b"tampered"}, pattern="effective overlay hash")

    def test_duplicate_json_key_rejected(self):
        self.reject({LIFE: b'{"batch":2,"batch":1}'}, pattern="duplicate JSON key")

    def test_boolean_is_not_a_counter(self):
        self.reject(changed(LIFE, object_count_after_file_close=True), pattern="invalid integer")

    def test_path_traversal_rejected(self):
        with self.assertRaisesRegex(audit.InvalidEvidence, "unsafe artifact path"):
            audit.RawReader(RAW).read("../diagnostic.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
