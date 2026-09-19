"""Artifact mutations exercise reader boundaries; no Godot/process launch."""
import copy
import unittest

import read_preview as reader


def fixture():
    expected = {key: "a" * 64 for key in reader.BINDINGS[2:]}
    expected.update(run_id="gt06-s107-preview-unit", pid=123)
    binding = dict(expected, formal_acceptance=False, eligible_for_dataset=False)
    rows = []
    for number in range(40):
        arm = "ABBA"[number % 4]
        row = dict(binding, schema_id="hh-studio.s107-preview-cost-cycle", schema_version="1.0.0",
                   cycle=number, group=number // 4, position=number % 4, arm=arm,
                   method="save_scene" if arm == "A" else "save_scene_as", with_preview=arm == "A",
                   return_error=0 if arm == "A" else None, completed=True,
                   effects={"create": 1, "undo": 1, "save": 1, "reload": 1},
                   root_before=100+number, root_after=101+number,
                   generation_before=number, generation_after=number+1,
                   signal_count_before=number, signal_count_after=number+1)
        row.update({key: "b" * 64 for key in reader.HASH_FIELDS})
        row["created_sha256"] = "c" * 64
        # Startup normalization is visible, never discarded as a warmup row.
        if number == 0:
            row["scene_before_sha256"] = "d" * 64
        for key, offset in zip(("process_entry_us", "save_start_us", "call_entry_us", "signal_us",
                                "call_return_us", "save_process_exit_us", "next_process_entry_us",
                                "readback_end_us", "next_process_exit_us"),
                               (1, 2, 3, 4, 10 if arm == "A" else 6, 11, 12, 13, 14)):
            row[key] = number*100 + offset
        for key, offset in zip(("process_entry_frame", "signal_frame", "save_process_exit_frame",
                                "next_process_entry_frame", "next_process_exit_frame"), (1, 2, 3, 4, 4)):
            row[key] = number*10 + offset
        rows.append(row)
    native = {"pid": 123, "input": {"run_id": expected["run_id"]}, "completed": True,
              "formal_acceptance": False, "benchmark_complete": False, "host_integrated": False,
              "batches_completed": 1, "cycles_per_batch": 40}
    return expected, binding, rows, native


def packet(expected, binding, rows, native):
    index = reader.canonical(native)
    rows_hash = reader.sha(reader.canonical(rows))
    report = reader.canonical(dict(binding, schema_id="hh-studio.s107-preview-cost", schema_version="1.0.0",
                                   completed=True, rows=rows, row_count=len(rows), arms={"A":20,"B":20},
                                   rows_sha256=rows_hash))
    complete = dict(binding, schema_id="hh-studio.s107-preview-cost-complete", schema_version="1.0.0",
                    completed=True, cycles=40, row_count=40, arms={"A":20,"B":20}, rows_sha256=rows_hash,
                    report_file="preview-cost.json", report_sha256=reader.sha(report),
                    report_size_bytes=len(report), index_sha256=reader.sha(index))
    stdout = b"".join(reader.ROW_MARKER.encode() + reader.canonical(row) + b"\n" for row in rows)
    stdout += reader.COMPLETE_MARKER.encode() + reader.canonical(complete) + b"\n"
    return stdout, report, index, expected


class ReaderTests(unittest.TestCase):
    def test_all_40_kept_and_void_is_null(self):
        result = reader.analyze(*packet(*fixture()))
        self.assertEqual(result["artifact_status"], "VALIDATED")
        self.assertEqual(len(result["observations"]), 40)
        self.assertEqual(len(result["paired_groups"]), 10)
        self.assertFalse(result["formal_acceptance"])
        self.assertFalse(result["root_cause_proven"])
        self.assertAlmostEqual(result["paired_groups"][0]["a_minus_b_call_ms"], .004)

    def test_independent_semantic_and_boundary_mutations(self):
        cases = [("return_error", 0, 1), ("return_error", None, 0), ("arm", "A", 1),
                 ("cycle", 3, 1), ("position", 0, 1), ("method", "save_scene", 1),
                 ("with_preview", True, 1), ("call_return_us", None, 1),
                 ("call_return_us", 99, 1), ("signal_count_after", 4, 1),
                 ("next_process_entry_frame", 10, 1), ("undone_sha256", "e"*64, 1),
                 ("script_reloaded_sha256", "e"*64, 1), ("scene_reloaded_sha256", "e"*64, 1),
                 ("scene_before_sha256", "e"*64, 1), ("generation_after", 99, 1),
                 ("root_before", 999, 1), ("source_closure_sha256", "e"*64, 1),
                 ("context_sha256", "e"*64, 1), ("completed", False, 1),
                 ("formal_acceptance", True, 1), ("effects", {"save":1}, 1)]
        for key, value, number in cases:
            with self.subTest(key=key, value=value, cycle=number):
                data = fixture()
                data[2][number][key] = value
                with self.assertRaises(ValueError):
                    reader.analyze(*packet(*data))

    def test_raw_bytes_are_not_canonical_artifact_hash(self):
        args = list(packet(*fixture()))
        args[1] += b"\n"
        with self.assertRaisesRegex(ValueError, "ARTIFACT_HASH"):
            reader.analyze(*args)

    def test_report_stdout_mismatch(self):
        args = list(packet(*fixture()))
        args[0] = args[0].replace(b'"return_error":0', b'"return_error":7', 1)
        with self.assertRaisesRegex(ValueError, "REPORT_STDOUT_ROWS"):
            reader.analyze(*args)

    def test_missing_duplicate_or_late_completion(self):
        args = list(packet(*fixture()))
        lines = args[0].splitlines(keepends=True)
        for stdout in (b"".join(lines[:-1]), args[0] + lines[-1], args[0] + lines[0]):
            with self.subTest(stdout_length=len(stdout)), self.assertRaises(ValueError):
                reader.analyze(stdout, *args[1:])

    def test_index_is_not_allowed_to_claim_formal_workload(self):
        for key, value in (("benchmark_complete", True), ("host_integrated", True), ("pid", 999),
                           ("cycles_per_batch", 100), ("batches_completed", 35), ("completed", False)):
            with self.subTest(key=key):
                data = fixture()
                data[3][key] = value
                with self.assertRaisesRegex(ValueError, "NATIVE_INDEX"):
                    reader.analyze(*packet(*data))

    def test_json_duplicate_keys_and_nonfinite_rejected(self):
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                reader.decode(data)

    def test_counts_and_binding_required(self):
        data = fixture()
        data[2].pop()
        with self.assertRaisesRegex(ValueError, "ROW_COUNT"):
            reader.analyze(*packet(*data))
        args = list(packet(*fixture()))
        args[3] = copy.copy(args[3])
        del args[3]["context_sha256"]
        with self.assertRaises(ValueError):
            reader.analyze(*args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
