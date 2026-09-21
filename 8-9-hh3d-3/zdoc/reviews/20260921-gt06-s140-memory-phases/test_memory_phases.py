"""Isolated S140 wrapper tests; no Godot/process launch."""
from __future__ import annotations

import gc
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import memory_phases as mp


class FakeProbe:
    def __init__(self, pid=41, start="windows:41"):
        self.pid, self.process_start, self.handle = pid, start, object()

    def sample_private_memory(self):
        return {
            "private_commit_bytes": 101,
            "working_set_bytes": 202,
            "page_fault_count": 3,
            "allocated_blocks": 4,
            "unavailable_reason": None,
        }


def _campaign(*, screen=None):
    events = []
    probe = FakeProbe()
    class Producer:
        def __init__(self):
            self.identity = {"pid": 41, "process_start": "windows:41"}
            self.observer = SimpleNamespace(probe=probe)
        def run_batch(self, index):
            events.append(("command", index))
            return {"index": index}
    class NativeLog:
        def wait(self, suffix, index, timeout):
            events.append((suffix, index))
            return {"index": index}
    def sample_editor(value):
        events.append(("editor", value.pid))
        return {"visible_window_handles": ["1"]}
    def assemble_sample(*, index=None):
        events.append(("assemble", index))
        return {"index": index}
    def original_screen(value, baseline):
        events.append(("screen-original", value["index"]))
        if screen is not None:
            return screen(value, baseline)
        return None
    def run_child(root):
        producer = Producer()
        producer.run_batch(0)
        campaign.gc.collect()
        log = NativeLog()
        log.wait("BATCH", 0, 1)
        campaign.sample_editor(probe)
        log.wait("ACK", 0, 1)
        campaign.assemble_sample(index=0)
        campaign.screen_sample({"index": 0}, None)
        campaign.gc.collect()
    campaign = SimpleNamespace(
        CampaignProducer=Producer, NativeLog=NativeLog,
        sample_editor=sample_editor, assemble_sample=assemble_sample,
        screen_sample=original_screen, gc=gc, run_child=run_child,
        events=events,
    )
    return campaign


class PhaseMemoryTests(unittest.TestCase):
  def test_recorder_has_fixed_capacity_and_tracks_drops(self):
    recorder = mp.PhaseMemoryRecorder("s140-capacity", 1)
    for index in range(250):
        recorder.record("command_completed", index)
    self.assertEqual(recorder.row_count, 200)
    self.assertEqual(recorder.dropped_rows, 50)
    self.assertEqual(recorder.report()["rows_seen"], 250)
    self.assertEqual(recorder.report()["max_rows"], 200)


  def test_prefix_and_run_id_are_bounded(self):
    with self.assertRaises(ValueError):
        mp.PhaseMemoryRecorder("x", 2)
    with self.assertRaises(ValueError):
        mp.PhaseMemoryRecorder("", 1)
    with self.assertRaises(ValueError):
        mp.PhaseMemoryRecorder("x", 1, max_rows=201)


  def test_phase_order_and_gc_proxy_are_local(self):
    campaign = _campaign()
    original_gc = campaign.gc
    original_collect = gc.collect
    recorder = mp.PhaseMemoryRecorder("s140-order", 1)
    with self.assertRaises(mp.BoundedPhaseStop):
        with mp.install_phase_memory_wrappers(campaign, recorder):
            campaign.run_child(Path("."))
            self.assertIsNot(campaign.gc, original_gc)
            self.assertIs(gc.collect, original_collect)
    self.assertIs(campaign.gc, original_gc)
    self.assertIs(gc.collect, original_collect)
    self.assertEqual([row[2] for row in recorder.rows], list(mp.PHASE_ORDER))
    self.assertEqual(recorder.rows[0][7], {"pid": 41, "process_start": "windows:41"})
    editor_rows = [row for row in recorder.rows if row[8] is not None]
    self.assertTrue(editor_rows)
    self.assertEqual(editor_rows[0][8], {"pid": 41, "process_start": "windows:41"})


  def test_original_screen_gate_exception_is_not_replaced(self):
    class OriginalGate(RuntimeError):
        pass
    def fail(_sample, _baseline):
        raise OriginalGate("CAMPAIGN_RSS_GROWTH")
    campaign = _campaign(screen=fail)
    recorder = mp.PhaseMemoryRecorder("s140-gate", 1)
    with self.assertRaisesRegex(OriginalGate, "CAMPAIGN_RSS_GROWTH"):
        with mp.install_phase_memory_wrappers(campaign, recorder):
            campaign.screen_sample({"index": 0}, None)
    self.assertEqual(recorder.row_count, 1)
    self.assertEqual(recorder.report()["rows"][0]["phase"], "screen_rejected")
    self.assertFalse(getattr(campaign, "_s140_phase_memory_active", False))


  def test_finally_persists_bounded_stop_report(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        campaign = _campaign()
        target = root / "phase-memory.json"
        result = mp.run_child_with_phase_memory(
            campaign, root / "unused-root", run_id="s140-finally", prefix=1, output=target
        )
        self.assertEqual(result["status"], "BOUNDED_STOP")
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(saved["formal_acceptance"])
        self.assertTrue(saved["diagnostic_only"])
        self.assertEqual(saved["run_id"], "s140-finally")
        self.assertEqual([row["phase"] for row in saved["rows"]], list(mp.PHASE_ORDER))
        self.assertTrue(all(row["measurement_overhead_us"] >= 0 for row in saved["rows"]))


  def test_original_run_failure_is_rethrown_but_report_is_persisted(self):
    class Gate(RuntimeError):
        code = "FIRST_GATE"
    campaign = _campaign()
    def failing_run_child(_root):
        raise Gate("preserve")
    campaign.run_child = failing_run_child
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "failure.json"
        with self.assertRaises(Gate):
            mp.run_child_with_phase_memory(
                campaign, root / "unused-root", run_id="s140-error", prefix=7, output=target
            )
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "ORIGINAL_GATE_FAILURE")
        self.assertEqual(saved["error_code"], "FIRST_GATE")


  def test_identity_cannot_rebind_to_another_process(self):
    recorder = mp.PhaseMemoryRecorder("s140-id", 1)
    recorder.bind_host(FakeProbe())
    with self.assertRaisesRegex(RuntimeError, "IDENTITY_CHANGED"):
        recorder.bind_host(FakeProbe(pid=42))
    with self.assertRaisesRegex(RuntimeError, "IDENTITY_MISMATCH"):
        recorder.bind_editor(FakeProbe(), {"pid": 1, "process_start": "windows:1"})

  def test_boundary_waits_for_original_post_assembly_gc(self):
    campaign = _campaign()
    recorder = mp.PhaseMemoryRecorder("s140-gc-boundary", 1)
    with mp.install_phase_memory_wrappers(campaign, recorder):
        campaign.CampaignProducer().run_batch(0)
        campaign.screen_sample({"index": 0}, None)
        self.assertEqual(recorder.rows[-1][2], "screen_sample")
        with self.assertRaises(mp.BoundedPhaseStop):
            campaign.gc.collect()
        self.assertEqual(recorder.rows[-1][2], "assembly_released_gc")

  def test_stock_composition_and_native_counter_layout(self):
    import os
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from studio.tests.replay import run_benchmark_campaign as campaign
    from studio.host.replay.process_probe import ProcessProbe
    producer = campaign.CampaignProducer
    original_method = producer.run_batch
    recorder = mp.PhaseMemoryRecorder("s140-stock-composition", 1)
    with mp.install_phase_memory_wrappers(campaign, recorder):
        self.assertIs(campaign.CampaignProducer, producer)
        self.assertIsNot(producer.run_batch, original_method)
    self.assertIs(producer.run_batch, original_method)
    self.assertNotIn("run_batch", vars(producer))
    if os.name == "nt":
        with ProcessProbe(os.getpid(), Path(sys.executable)) as probe:
            signature = probe.p.GetProcessMemoryInfo.argtypes
            counters = mp._read_private_counters(probe)
            self.assertIsNone(counters.unavailable_reason)
            self.assertGreater(counters.private_commit_bytes, 0)
            self.assertGreater(counters.working_set_bytes, 0)
            self.assertGreater(counters.allocated_blocks, 0)
            self.assertEqual(probe.p.GetProcessMemoryInfo.argtypes, signature)
            self.assertGreater(probe.sample()["rss_bytes"], 0)

if __name__ == "__main__":
    unittest.main()

