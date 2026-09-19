"""Static overlay boundary checks; no Godot or campaign is launched."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("s103_native_probe_subject", HERE / "native_probe.py")
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
SOURCE = HERE.parents[2] / "studio/tests/replay/benchmark_native.gd"


def functions(raw):
    text = raw.decode("utf-8")
    starts = list(re.finditer(r"^func (\w+)\([^\n]*\n", text, re.MULTILINE))
    return {match.group(1): text[match.start():starts[index + 1].start() if index + 1 < len(starts) else len(text)]
            for index, match in enumerate(starts)}


class ExactSourceOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SOURCE.read_bytes()
        cls.overlaid = subject.transform(cls.raw)

    def test_frozen_hash_and_deterministic_output(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), subject.SOURCE_SHA256)
        self.assertEqual(subject.transform(self.raw), self.overlaid)
        self.assertFalse(self.overlaid.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", self.overlaid)

    def test_rejects_stale_source_bom_newline_drift_and_repeat_transform(self):
        bad = [b"", self.raw + b"\n", b"\xef\xbb\xbf" + self.raw,
               self.raw.replace(b"\n", b"\r\n"), self.raw.replace(b"500000", b"500001", 1),
               self.overlaid]
        for raw in bad:
            with self.subTest(sha=hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(subject.ProbeError, "S103_NATIVE_SOURCE_HASH"):
                    subject.transform(raw)
        for raw in (None, "source", bytearray(self.raw), memoryview(self.raw)):
            with self.assertRaisesRegex(subject.ProbeError, "S103_NATIVE_SOURCE_TYPE"):
                subject.transform(raw)

    def test_only_three_additive_edits_and_suffix_recover_exact_source(self):
        self.assertTrue(self.overlaid.endswith(subject._SUFFIX))
        restored = self.overlaid[:-len(subject._SUFFIX)]
        for new, old in ((subject._DISPATCH, subject._PROCESS),
                         (subject._SAVE_OBSERVED, subject._SAVE_CALL),
                         (subject._SIGNAL_OBSERVED, subject._SIGNAL)):
            self.assertEqual(restored.count(new), 1)
            restored = restored.replace(new, old, 1)
        self.assertEqual(restored, self.raw)

    def test_original_process_body_preserves_every_early_return_and_dispatch(self):
        before, after = functions(self.raw), functions(self.overlaid)
        self.assertEqual(before["_process"].replace("func _process(", "func _hh_s103_process_dispatch(", 1),
                         after["_hh_s103_process_dispatch"])
        self.assertEqual(after["_process"].count("_hh_s103_process_dispatch(_delta)"), 1)
        self.assertLess(after["_process"].index("var entered:"), after["_process"].index("_hh_s103_process_dispatch(_delta)"))
        self.assertLess(after["_process"].index("_hh_s103_process_dispatch(_delta)"), after["_process"].index("var exited:"))

    def test_acceptance_sensitive_methods_and_constants_unchanged(self):
        before, after = functions(self.raw), functions(self.overlaid)
        for name in ("_heartbeat", "_begin_batch", "_wait_host_start", "_start_native_batch",
                     "_wait_save", "_wait_reload", "_wait_host_ack", "_write_batch", "_finish"):
            with self.subTest(method=name):
                self.assertEqual(before[name], after[name])
        original_prefix = self.raw.split(b"func _process", 1)[0]
        self.assertTrue(self.overlaid.startswith(original_prefix))
        self.assertNotIn(b"_heartbeat(", subject._SUFFIX)
        for forbidden in (b"_phase =", b"_set_phase(", b"_fail(", b"get_tree().quit", b"await ",
                          b"OS.delay", b"FileAccess", b"HEARTBEAT_US =", b"_last_heartbeat_us ="):
            self.assertNotIn(forbidden, subject._SUFFIX)

    def test_enter_print_precedes_measured_call_and_return_precedes_result_handling(self):
        after = functions(self.overlaid)
        save = after["_save"]
        order = [save.index(text) for text in ("_hh_s103_enter_save()", "call_entry_us = Time.get_ticks_usec()",
                  "EditorInterface.save_scene()", "hh_s103_call_return_us: int = Time.get_ticks_usec()",
                  "call_return_us = hh_s103_call_return_us", "if result != OK:")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(save.count("EditorInterface.save_scene()"), 1)
        self.assertIn("signal_us = _save_signal_us", after["_on_scene_saved"])
        self.assertLess(after["_on_scene_saved"].index("_save_signal_us = Time.get_ticks_usec()"),
                        after["_on_scene_saved"].index("signal_us = _save_signal_us"))

    def test_observer_has_one_pending_record_and_bounded_pair_emission(self):
        suffix = subject._SUFFIX.decode("utf-8")
        self.assertEqual(subject.MAX_SAVE_RECORDS, 700)
        self.assertIn("const HH_S103_SAVE_RECORD_CAP: int = 700", suffix)
        self.assertIn("if _hh_s103_save_records >= HH_S103_SAVE_RECORD_CAP:\n        return", suffix)
        self.assertEqual(suffix.count('print("HH_GT06_S103_SAVE_ENTER '), 1)
        self.assertEqual(suffix.count('print("HH_GT06_S103_SAVE_COMPLETE '), 1)
        self.assertIn('print("HH_GT06_S103_SAVE_COMPLETE " + JSON.stringify(_hh_s103_save))\n        _hh_s103_save = {}', suffix)
        self.assertNotIn(".append(", suffix)
        self.assertNotIn("Array", suffix)
        self.assertIn('"formal_acceptance": false', suffix)
        self.assertIn("if readback_end > 0 or _failed:", suffix)
        self.assertIn("and readback_end > 0 and not _failed", suffix)

    def test_source_anchor_guard_remains_fail_closed(self):
        mutated = self.raw.replace(subject._SAVE_CALL, b"    # deliberately absent test anchor\n")
        with patch.object(subject, "SOURCE_SHA256", hashlib.sha256(mutated).hexdigest()):
            with self.assertRaisesRegex(subject.ProbeError, "S103_NATIVE_SOURCE_ANCHOR"):
                subject.transform(mutated)


if __name__ == "__main__":
    unittest.main()
