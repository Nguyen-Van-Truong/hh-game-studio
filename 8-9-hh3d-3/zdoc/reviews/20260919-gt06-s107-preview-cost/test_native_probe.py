"""Static S107 transformation/contract checks; never starts Godot."""
from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("s107_native_probe_test_subject", HERE / "native_probe.py")
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
SOURCE = HERE.parents[2] / "studio/tests/replay/benchmark_native.gd"


def functions(raw):
    text = raw.decode()
    matches = list(re.finditer(r"^func (\w+)\([^\n]*\n", text, re.MULTILINE))
    return {match.group(1): text[match.start():matches[i + 1].start() if i + 1 < len(matches) else len(text)].rstrip()
            for i, match in enumerate(matches)}


class NativeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SOURCE.read_bytes()
        cls.generated = subject.build_overlay(cls.base)
        cls.before, cls.after = functions(cls.base), functions(cls.generated)

    def test_exact_pin_deterministic_bytes_and_recipe(self):
        self.assertEqual(hashlib.sha256(self.base).hexdigest(), subject.BASE_SOURCE_SHA256)
        self.assertEqual(subject.build_overlay(self.base), self.generated)
        self.assertNotIn(b"\r", self.generated)
        self.assertNotIn(b"@@", self.generated)
        self.assertEqual(json.loads(subject.RECIPE_BYTES), subject.RECIPE)
        self.assertEqual(hashlib.sha256(subject.RECIPE_BYTES).hexdigest(), subject.RECIPE_SHA256)

    def test_rejects_source_drift_bom_line_endings_and_repeat(self):
        for bad in (b"", self.base + b"\n", b"\xef\xbb\xbf" + self.base,
                    self.base.replace(b"\n", b"\r\n"), self.generated,
                    self.base.replace(b"HEARTBEAT_US: int = 500000", b"HEARTBEAT_US: int = 499999")):
            with self.subTest(digest=hashlib.sha256(bad).hexdigest()):
                with self.assertRaisesRegex(subject.ProbeError, "SOURCE_HASH"):
                    subject.build_overlay(bad)
        for bad in (None, "text", bytearray(self.base), memoryview(self.base)):
            with self.assertRaisesRegex(subject.ProbeError, "SOURCE_TYPE"):
                subject.build_overlay(bad)

    def test_anchor_absence_or_duplication_fails_even_with_test_pin(self):
        for old, _ in subject._REPLACEMENTS:
            for mutation in (self.base.replace(old, b"# absent\n", 1), self.base + old):
                with patch.object(subject, "BASE_SOURCE_SHA256", hashlib.sha256(mutation).hexdigest()):
                    with self.assertRaisesRegex(subject.ProbeError, "SOURCE_ANCHOR"):
                        subject.build_overlay(mutation)

    def test_all_transformations_are_exactly_reversible(self):
        prefix = self.generated.split(b"\n\n\n# BEGIN HH_S107_DIAGNOSTIC_PREVIEW_COST_V1", 1)[0]
        for old, new in reversed(subject._REPLACEMENTS):
            self.assertEqual(prefix.count(new), 1)
            prefix = prefix.replace(new, old, 1)
        self.assertEqual(prefix, self.base)

    def test_original_heartbeat_deadlines_phase_dispatch_and_semantics_retained(self):
        for method in ("_heartbeat", "_initialize", "_begin_cycle", "_create", "_undo", "_reload", "_wait_reload",
                       "_begin_batch", "_wait_host_start", "_start_native_batch", "_wait_host_ack", "_write_batch",
                       "_record_time", "_set_phase"):
            self.assertEqual(self.before[method], self.after[method], method)
        self.assertEqual(self.before["_process"].replace("func _process(", "func _s107_dispatch(", 1),
                         self.after["_s107_dispatch"])
        before_constants = re.findall(rb"^const (?:.*TIMEOUT_US|HEARTBEAT_US|SETTLE_FRAMES|SETTLE_US).*", self.base, re.M)
        after_constants = re.findall(rb"^const (?:.*TIMEOUT_US|HEARTBEAT_US|SETTLE_FRAMES|SETTLE_US).*", self.generated, re.M)
        self.assertEqual(before_constants, after_constants)
        self.assertNotIn("_heartbeat(", subject._SUFFIX_TEMPLATE)

    def test_exact_40_cycle_abba_recipe_and_diagnostic_only_guard(self):
        arms = [subject.expected_arm(i) for i in range(40)]
        self.assertEqual(arms, list("ABBA" * 10))
        self.assertEqual(Counter(arms), {"A": 20, "B": 20})
        for bad in (-1, 40, 41, True, 1.0, "0"):
            with self.assertRaisesRegex(subject.ProbeError, "CYCLE_RANGE"):
                subject.expected_arm(bad)
        self.assertIn('if _mode != "diagnostic":', self.after["_boot"])
        self.assertIn("_cycle_limit = S107_RECORD_CAP", self.after["_boot"])
        self.assertIn('"ABBA".substr(_cycle % 4, 1)', self.after["_s107_begin_save"])
        self.assertIn("_s107_rows.size() != _cycle", self.after["_s107_begin_save"])
        self.assertIn("_s107_rows.size() >= S107_RECORD_CAP", self.after["_s107_complete_cycle"])

    def test_void_arm_cannot_report_ok_and_both_calls_are_observed(self):
        save = self.after["_save"]
        a, b = save.split("    else:\n", 1)
        self.assertEqual(a.count("EditorInterface.save_scene()"), 1)
        self.assertEqual(b.count("EditorInterface.save_scene_as(SCENE, false)"), 1)
        self.assertIn("return_error = int(result)", a)
        self.assertIn('if result != OK:\n            _fail("BENCHMARK_SAVE_CALL")', a)
        self.assertIn("return_error = null", b)
        self.assertNotIn("return_error = 0", save)
        self.assertNotIn("save_result", save)
        for branch, call in ((a, "EditorInterface.save_scene()"), (b, "EditorInterface.save_scene_as(SCENE, false)")):
            self.assertLess(branch.index("call_entry_us = Time.get_ticks_usec()"), branch.index(call))
            self.assertLess(branch.index(call), branch.index("call_return_us = Time.get_ticks_usec()"))

    def test_exact_byte_and_reload_evidence_required_before_completed_row(self):
        readback = self.after["_s107_save_readback"]
        self.assertIn('script_hash != _source_hashes["res://scripts/fixture_actor.gd"]', readback)
        self.assertIn("scene_hash != _s107_saved_scene_sha256", readback)
        complete = self.after["_s107_complete_cycle"]
        self.assertIn("S107_BOUNDARY_MISSING", complete)
        self.assertIn("S107_SIGNAL_COUNT", complete)
        self.assertIn("S107_RELOAD_BYTES", complete)
        self.assertLess(complete.index("S107_RELOAD_BYTES"), complete.index("_s107_current.completed = true"))
        self.assertLess(complete.index("_s107_current.completed = true"), complete.index("_s107_rows.append"))
        settle = self.after["_settle_cycle"]
        self.assertLess(settle.index("BENCHMARK_POST_RELOAD_DRIFT"), settle.index("_s107_complete_cycle()"))
        self.assertLess(settle.index("_s107_complete_cycle()"), settle.index("_cycles.append"))

    def test_context_binding_is_exact_and_in_source_stability_map(self):
        context = self.after["_s107_bind_context"]
        for field in ("schema_id", "schema_version", "run_id", "base_source_closure_sha256",
                      "profile_sha256", "recipe_sha256", "generated_overlay_sha256", "diagnostic_closure_sha256"):
            self.assertIn('"' + field + '"', context)
        self.assertIn("parsed.size() != fields.size()", context)
        self.assertIn('parsed.generated_overlay_sha256 != _source_hashes["res://addons/hh_benchmark/benchmark_native.gd"]', context)
        self.assertIn('INPUT, EVIDENCE_IGNORE, "res://benchmark/s107-context.json"]', self.generated.decode())
        self.assertIn('"context_sha256": _source_hashes.get(S107_CONTEXT, "")', self.after["_s107_binding"])

    def test_fixed_buffer_flush_after_cycles_and_completion_after_index(self):
        flush = self.after["_s107_flush"]
        self.assertIn("if _s107_flushed:", flush)
        self.assertIn("rows.size() < S107_RECORD_CAP", flush)
        self.assertIn("rows.size() > S107_RECORD_CAP", flush)
        self.assertEqual(self.generated.count(subject.ROW_MARKER.encode()), 1)
        self.assertNotIn("print(", self.after["_save"])
        finish = self.after["_finish"]
        self.assertLess(finish.index("_s107_rows.size() != S107_RECORD_CAP"), finish.index("_s107_flush(true)"))
        self.assertLess(finish.index('BENCHMARK_INDEX_WRITE'), finish.index("_s107_emit_complete"))
        self.assertLess(finish.index("_s107_emit_complete"), finish.index("get_tree().quit(0)"))
        self.assertIn("_s107_flush(false)", self.after["_fail"])

    def test_supplement_has_no_artificial_pressure_http_pss_or_mutated_clock(self):
        added = subject._SUFFIX_TEMPLATE + subject._SAVE_NEW.decode()
        for forbidden in ("OS.delay", "Thread.new", "HTTPRequest", "Pss", "SeDebugPrivilege", "resize(100000",
                          "_last_heartbeat_us =", "_batch_status_gap_us =", "set_low_processor_usage_mode",
                          "set_process_thread_group", "get_tree().quit(0)"):
            self.assertNotIn(forbidden, added)
        self.assertFalse(subject.RECIPE["artificial_pressure"])
        self.assertFalse(subject.RECIPE["formal_acceptance"])
        self.assertFalse(subject.RECIPE["eligible_for_dataset"])
        self.assertEqual(subject.RECIPE["host_commands"], 0)
        self.assertEqual(subject.RECIPE["pss_captures"], 0)


if __name__ == "__main__":
    unittest.main()
