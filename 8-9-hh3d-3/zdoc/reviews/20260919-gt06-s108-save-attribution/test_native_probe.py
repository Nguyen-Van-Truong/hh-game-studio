"""Static transformation/provenance checks; no Godot or runtime import."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def module(path):
    result = types.ModuleType(path.stem)
    exec(compile(path.read_bytes(), str(path), "exec"), result.__dict__)
    return result


subject = module(HERE / "native_probe.py")


def functions(raw):
    text = raw.decode()
    matches = list(re.finditer(r"^func (\w+)\([^\n]*\n", text, re.MULTILINE))
    boundaries = [m.start() for m in matches]
    boundaries.extend(m.start() for m in re.finditer(r"^# BEGIN ", text, re.MULTILINE))
    boundaries.append(len(text))
    return {m.group(1): text[m.start():min(i for i in boundaries if i > m.start())].rstrip()
            for m in matches}


class NativeProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        historical = REPO / "zdoc/reviews/20260919-gt06-s103-status-gap/native_probe.py"
        if hashlib.sha256(historical.read_bytes()).hexdigest() != subject.S103_HELPER_SHA256:
            raise AssertionError("S103_HELPER_PIN")
        cls.base = (REPO / "studio/tests/replay/benchmark_native.gd").read_bytes()
        cls.s103 = module(historical).transform(cls.base)
        cls.generated = subject.build_overlay(cls.base, cls.s103)
        cls.before, cls.after = functions(cls.s103), functions(cls.generated)

    def test_exact_inputs_deterministic_output(self):
        self.assertEqual(hashlib.sha256(self.base).hexdigest(), subject.BASE_SOURCE_SHA256)
        self.assertEqual(hashlib.sha256(self.s103).hexdigest(), subject.S103_OVERLAY_SHA256)
        self.assertEqual(subject.transform(self.base, self.s103), self.generated)
        self.assertNotIn(b"\r", self.generated)
        self.assertNotIn(b"@@", self.generated)

    def test_rejects_drift_wrong_types_and_repeated_transform(self):
        for value in (b"", self.base + b"\n", b"\xef\xbb\xbf" + self.base, self.base.replace(b"\n", b"\r\n")):
            with self.assertRaisesRegex(subject.ProbeError, "SOURCE_HASH"):
                subject.build_overlay(value, self.s103)
        for value in (self.base, self.s103 + b"\n", self.s103.replace(b"\n", b"\r\n"), self.generated):
            with self.assertRaisesRegex(subject.ProbeError, "S103_OVERLAY_HASH"):
                subject.build_overlay(self.base, value)
        for bad in (None, "text", bytearray(self.base), memoryview(self.base)):
            with self.assertRaisesRegex(subject.ProbeError, "SOURCE_TYPE"):
                subject.build_overlay(bad, self.s103)
            with self.assertRaisesRegex(subject.ProbeError, "SOURCE_TYPE"):
                subject.build_overlay(self.base, bad)

    def test_anchor_count_fails_before_output_even_with_test_pin(self):
        for old, _ in subject._REPLACEMENTS:
            for changed in (self.s103.replace(old, b"# absent\n", 1), self.s103 + old):
                with patch.object(subject, "S103_OVERLAY_SHA256", hashlib.sha256(changed).hexdigest()):
                    with self.assertRaisesRegex(subject.ProbeError, "SOURCE_ANCHOR"):
                        subject.build_overlay(self.base, changed)

    def test_only_two_additions_and_suffix_are_exactly_reversible(self):
        self.assertTrue(self.generated.endswith(subject._SUFFIX))
        restored = self.generated[:-len(subject._SUFFIX)]
        for old, new in reversed(subject._REPLACEMENTS):
            self.assertEqual(restored.count(new), 1)
            restored = restored.replace(new, old, 1)
        self.assertEqual(restored, self.s103)
        for name in self.before:
            if name != "_initialize":
                self.assertEqual(self.before[name], self.after[name], name)

    def test_original_save_timing_workload_and_gates_are_unchanged(self):
        for name in ("_save", "_on_scene_saved", "_process", "_hh_s103_process_dispatch",
                     "_hh_s103_enter_save", "_heartbeat", "_wait_host_start", "_wait_host_ack", "_finish"):
            self.assertEqual(self.before[name], self.after[name], name)
        self.assertEqual(self.generated.count(b"EditorInterface.save_scene()"), self.s103.count(b"EditorInterface.save_scene()"))
        self.assertNotIn(b"save_scene_as", self.generated)
        pattern = rb"^const (?:FULL_BATCHES|FULL_CYCLES|WARMUP_BATCHES|.*TIMEOUT_US|HEARTBEAT_US|SETTLE_FRAMES|SETTLE_US).*"
        self.assertEqual(re.findall(pattern, self.base, re.M), re.findall(pattern, self.generated, re.M))

    def test_announcement_after_settled_startup_before_ready_and_one_marker(self):
        initialize = self.after["_initialize"]
        self.assertLess(initialize.index('_startup_readiness["settled"] = settled'), initialize.index("_s108_announce_main_window()"))
        self.assertLess(initialize.index("_s108_announce_main_window()"), initialize.index("_begin_batch()"))
        self.assertEqual(self.before["_begin_batch"], self.after["_begin_batch"])
        self.assertEqual(self.generated.count(subject.WINDOW_MARKER.encode()), 1)
        announce = self.after["_s108_announce_main_window"]
        self.assertIn("if _s108_window_announced:", announce)
        self.assertLess(announce.index("_s108_window_announced = true"), announce.index("print("))
        self.assertIn('if _mode != "full"', announce)

    def test_requires_actual_windows_main_window_and_does_not_invent_windows_tid(self):
        announce = self.after["_s108_announce_main_window"]
        self.assertIn('not Thread.is_main_thread() or DisplayServer.get_name() != "Windows"', announce)
        self.assertIn("DisplayServer.get_window_list().has(DisplayServer.MAIN_WINDOW_ID)", announce)
        self.assertIn("DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE, DisplayServer.MAIN_WINDOW_ID)", announce)
        self.assertIn("if hwnd <= 0:", announce)
        self.assertIn('"windows_thread_id": null', announce)
        self.assertIn('"logical_thread": "godot_editor_main"', announce)
        self.assertIn('"main_thread": true', announce)
        for code in ("S108_MAIN_WINDOW_PLATFORM_THREAD", "S108_MAIN_WINDOW_MISSING", "S108_MAIN_WINDOW_HANDLE"):
            self.assertLess(announce.index(code), announce.index("print("))

    def test_context_pins_and_stability_map_are_required_before_marker(self):
        announce = self.after["_s108_announce_main_window"]
        for key in subject.CONTEXT_FIELDS:
            self.assertIn('"' + key + '"', announce)
        self.assertIn("parsed.size() != fields.size()", announce)
        self.assertIn("size > 8192", announce)
        self.assertIn('parsed.generated_overlay_sha256 != _source_hashes["res://addons/hh_benchmark/benchmark_native.gd"]', announce)
        self.assertIn("parsed.base_source_closure_sha256 != S108_BASE_CLOSURE_SHA256", announce)
        self.assertIn("parsed.profile_sha256 != S108_PROFILE_SHA256", announce)
        self.assertIn("FileAccess.get_sha256(S108_CONTEXT) != _source_hashes[S108_CONTEXT]", announce)
        self.assertIn(b'INPUT, EVIDENCE_IGNORE, "res://benchmark/s108-context.json"]', self.generated)
        self.assertIn('"context_sha256": _source_hashes[S108_CONTEXT]', announce)
        self.assertIn('"formal_acceptance": false, "eligible_for_dataset": false', announce)
        for forbidden in ("Thread.new", "OS.delay", "HTTP", "Pss", "_last_heartbeat_us =", "_batch_status_gap_us =", "get_tree().quit(0)"):
            self.assertNotIn(forbidden, subject._SUFFIX.decode())


if __name__ == "__main__":
    unittest.main()
