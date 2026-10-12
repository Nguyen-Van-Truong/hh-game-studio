"""Fast unit tests (no Godot) for gamekit W6: percentiles, leak slope, budgets, violations."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from studio.gamekit import common as C
from studio.gamekit import perf as P
from studio.gamekit.hh import build_parser


def _samples(n: int = 20, **overrides: list[float]) -> dict[str, list[float]]:
    base = {
        "frame_ms": [1.0] * n,
        "process_ms": [0.2] * n,
        "physics_ms": [0.05] * n,
        "render_cpu_ms": [0.1] * n,
        "render_gpu_ms": [0.1] * n,
        "draw_calls": [10.0] * n,
        "primitives": [100.0] * n,
        "vram_bytes": [20 * 1024 * 1024] * n,
        "objects": [100.0] * n,
        "nodes": [50.0] * n,
        "orphans": [0.0] * n,
        "memory_static": [30 * 1024 * 1024] * n,
        "physics_2d": [0.0] * n,
        "physics_3d": [0.0] * n,
    }
    base.update(overrides)
    return base


def _leak(nodes: list[float], objects: list[float]) -> list[dict]:
    rows = []
    for i, (node, obj) in enumerate(zip(nodes, objects), start=1):
        rows.append({"cycle": i, "nodes": node, "objects": obj, "orphans": 0.0, "memory_static": 1000.0})
    return rows


def _flat_leak() -> list[dict]:
    return _leak([10, 10, 10, 10], [100, 100, 100, 100])


class PercentileTest(unittest.TestCase):
    def test_linear_interpolation(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(P.percentile(data, 0), 1.0)
        self.assertEqual(P.percentile(data, 50), 3.0)
        self.assertEqual(P.percentile(data, 100), 5.0)
        self.assertAlmostEqual(P.percentile(data, 95), 4.8)
        self.assertAlmostEqual(P.percentile(data, 99), 4.96)
        self.assertAlmostEqual(P.percentile([1.0, 3.0], 25), 1.5)

    def test_single_value_and_empty(self) -> None:
        self.assertEqual(P.percentile([7.0], 95), 7.0)
        with self.assertRaises(ValueError):
            P.percentile([], 50)
        with self.assertRaises(ValueError):
            P.percentile([1.0], -1)


class SlopeTest(unittest.TestCase):
    def test_slope_shapes(self) -> None:
        self.assertAlmostEqual(P.least_squares_slope([1, 2, 3, 4]), 1.0)
        self.assertAlmostEqual(P.least_squares_slope([5, 5, 5, 5]), 0.0)
        self.assertAlmostEqual(P.least_squares_slope([0, 2, 4, 6]), 2.0)
        self.assertIsNone(P.least_squares_slope([3.0]))
        self.assertIsNone(P.least_squares_slope([]))

    def test_cycle_one_is_excluded_from_the_leak_slope(self) -> None:
        # Cycle 1 spikes, cycles 2..4 are flat: not a leak.
        judged = P.judge(_samples(), _leak([1000, 10, 10, 10], [100, 100, 100, 100]), P.default_budget(), gpu_measured=True)
        self.assertFalse(judged["leak_suspected"])
        self.assertEqual(judged["leak"]["nodes_per_cycle"], 0.0)
        # Cycles 2..4 climb by 1 node each.
        leaked = P.judge(_samples(), _leak([10, 11, 12, 13], [80, 80, 80, 80]), P.default_budget(), gpu_measured=True)
        self.assertTrue(leaked["leak_suspected"])
        self.assertAlmostEqual(leaked["leak"]["nodes_per_cycle"], 1.0)
        self.assertFalse(leaked["ok"])
        self.assertTrue(any(v["metric"] == "leak_nodes_per_cycle_max" for v in leaked["violations"]))

    def test_orphan_growth_counts_as_a_node_leak(self) -> None:
        # OBJECT_NODE_COUNT stays flat; the leaked Node lives only in the orphan monitor.
        rows = []
        for i, orphans in enumerate([2.0, 3.0, 4.0, 5.0], start=1):
            rows.append({"cycle": i, "nodes": 3.0, "objects": 100.0 + i, "orphans": orphans, "memory_static": 1000.0})
        judged = P.judge(_samples(), rows, P.default_budget(), gpu_measured=True)
        self.assertAlmostEqual(judged["leak"]["nodes_per_cycle"], 1.0)
        self.assertTrue(judged["leak_suspected"])
        self.assertFalse(judged["ok"])


class BudgetTest(unittest.TestCase):
    def test_defaults_and_partial_merge(self) -> None:
        defaults = P.default_budget()
        self.assertEqual(defaults["frame_ms_p95"], 33.3)
        self.assertEqual(defaults["gpu_ms_p95"], 16.6)
        self.assertEqual(defaults["process_ms_p95"], 8.0)
        self.assertEqual(defaults["physics_ms_p95"], 8.0)
        self.assertEqual(defaults["draw_calls_max"], 5000.0)
        self.assertEqual(defaults["primitives_max"], 5000000.0)
        self.assertEqual(defaults["vram_mb_max"], 2048.0)
        self.assertEqual(defaults["nodes_max"], 10000.0)
        self.assertEqual(defaults["orphan_nodes_max"], 0.0)
        self.assertEqual(defaults["leak_nodes_per_cycle_max"], 0.5)
        self.assertEqual(defaults["leak_objects_per_cycle_max"], 20.0)
        self.assertEqual(defaults["memory_static_mb_max"], 1024.0)
        merged = P.merge_budget({"draw_calls_max": 0})
        self.assertEqual(merged["draw_calls_max"], 0.0)
        self.assertEqual(merged["frame_ms_p95"], 33.3)
        merged["nodes_max"] = -1
        self.assertEqual(P.default_budget()["nodes_max"], 10000.0)
        self.assertEqual(P.merge_budget({})["vram_mb_max"], 2048.0)
        self.assertEqual(P.merge_budget(None)["orphan_nodes_max"], 0.0)

    def test_unknown_and_bad_values(self) -> None:
        with self.assertRaises(C.GamekitError) as cm:
            P.merge_budget({"nope": 1, "frame_ms_p95": 1})
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        self.assertIn("nope", cm.exception.detail)
        for bad in (-1, True, False, "8", float("nan"), float("inf"), None):
            with self.assertRaises(C.GamekitError) as cm:
                P.merge_budget({"nodes_max": bad})
            self.assertEqual(cm.exception.code, "BAD_REQUEST", bad)
        with self.assertRaises(C.GamekitError):
            P.merge_budget(["draw_calls_max"])  # type: ignore[arg-type]


class JudgeTest(unittest.TestCase):
    def test_clean_scene_passes_and_peaks_are_maxes(self) -> None:
        samples = _samples(draw_calls=[3.0, 12.0, 9.0], frame_ms=[1.0, 2.0, 3.0, 4.0] * 5)
        judged = P.judge(samples, _flat_leak(), P.default_budget(), gpu_measured=True)
        self.assertTrue(judged["ok"])
        self.assertEqual(judged["violations"], [])
        self.assertFalse(judged["leak_suspected"])
        self.assertEqual(judged["draw_calls"], 12.0)
        self.assertEqual(judged["vram_mb"], 20.0)
        self.assertEqual(judged["gpu_ms"], 0.1)
        self.assertEqual(judged["gpu_ms_stats"]["p95"], 0.1)
        self.assertAlmostEqual(judged["fps"], 1000.0 / (sum(samples["frame_ms"]) / len(samples["frame_ms"])))

    def test_draw_call_budget_and_frame_budget(self) -> None:
        tight = P.merge_budget({"draw_calls_max": 0})
        judged = P.judge(_samples(), _flat_leak(), tight, gpu_measured=True)
        self.assertFalse(judged["ok"])
        self.assertEqual(judged["violations"], [{"metric": "draw_calls_max", "value": 10.0, "limit": 0.0}])
        slow = P.judge(_samples(frame_ms=[40.0] * 20), _flat_leak(), P.default_budget(), gpu_measured=True)
        hit = next(v for v in slow["violations"] if v["metric"] == "frame_ms_p95")
        self.assertAlmostEqual(hit["value"], 40.0)
        self.assertAlmostEqual(hit["limit"], 33.3)

    def test_headless_gpu_is_not_a_violation(self) -> None:
        budget = P.merge_budget({"gpu_ms_p95": 0})
        judged = P.judge(_samples(render_gpu_ms=[100.0] * 20), _flat_leak(), budget, gpu_measured=False)
        self.assertEqual(judged["gpu_ms"], "not_measured")
        self.assertEqual(judged["cpu_render_ms"], "not_measured")
        self.assertTrue(judged["ok"])
        self.assertTrue(all(v["metric"] != "gpu_ms_p95" for v in judged["violations"]))

    def test_object_growth_and_exact_limit(self) -> None:
        objects = P.judge(_samples(), _leak([10, 10, 10, 10], [0, 100, 121, 142]), P.default_budget(), gpu_measured=True)
        self.assertTrue(objects["leak_suspected"])
        self.assertAlmostEqual(objects["leak"]["objects_per_cycle"], 21.0)
        self.assertTrue(any(v["metric"] == "leak_objects_per_cycle_max" for v in objects["violations"]))
        # Slope of cycles 2..4 on [0, 0.5, 1.0] is exactly the 0.5 node limit: not a violation.
        on_limit = P.judge(_samples(), _leak([9, 0, 0.5, 1.0], [1, 1, 1, 1]), P.default_budget(), gpu_measured=True)
        self.assertAlmostEqual(on_limit["leak"]["nodes_per_cycle"], 0.5)
        self.assertFalse(on_limit["leak_suspected"])
        self.assertTrue(on_limit["ok"])

    def test_orphan_and_memory_peaks(self) -> None:
        judged = P.judge(
            _samples(orphans=[0.0, 2.0], memory_static=[2048 * 1024 * 1024] * 20),
            _flat_leak(),
            P.default_budget(),
            gpu_measured=True,
        )
        metrics = {v["metric"] for v in judged["violations"]}
        self.assertIn("orphan_nodes_max", metrics)
        self.assertIn("memory_static_mb_max", metrics)
        self.assertFalse(judged["ok"])


def _godot_result(n: int = 4, **overrides: list[float]) -> dict:
    series = {
        "frame_ms": [1.0] * n,
        "process_measured_ms": [0.2] * n,
        "process_monitor_ms": [50.0] * n,
        "physics_measured_ms": [0.05] * n,
        "physics_monitor_ms": [40.0] * n,
        "render_cpu_ms": [0.1] * n,
        "render_gpu_ms": [0.1] * n,
        "draw_calls": [4.0] * n,
        "primitives": [8.0] * n,
        "vram_bytes": [1024.0 * 1024] * n,
        "objects": [10.0] * n,
        "nodes": [6.0] * n,
        "orphans": [0.0] * n,
        "memory_static": [1024.0 * 1024] * n,
        "physics_2d": [0.0] * n,
        "physics_3d": [0.0] * n,
    }
    series.update(overrides)
    return {
        "ok": True,
        "gpu_measured": True,
        "trace_applied": 2,
        "sample_frames": n,
        "samples": series,
        "leak_samples": _flat_leak(),
    }


class NormalizeTest(unittest.TestCase):
    def test_renames_measured_series_and_keeps_monitors(self) -> None:
        norm = P.normalize_result(_godot_result(), frames=4, leak_cycles=4)
        self.assertEqual(norm["samples"]["process_ms"], [0.2, 0.2, 0.2, 0.2])
        self.assertEqual(norm["samples"]["physics_ms"], [0.05] * 4)
        self.assertEqual(norm["monitors"]["process_ms"]["p95"], 50.0)
        self.assertEqual(norm["trace_applied"], 2)
        self.assertTrue(norm["gpu_measured"])
        judged = P.judge(norm["samples"], norm["leak_samples"], P.default_budget(), gpu_measured=True)
        self.assertTrue(judged["ok"])
        self.assertLess(judged["process_ms"]["p95"], 8.0)

    def test_rejects_bad_shapes(self) -> None:
        short = _godot_result()
        short["samples"]["frame_ms"] = [1.0]
        with self.assertRaises(C.GamekitError) as cm:
            P.normalize_result(short, frames=4, leak_cycles=4)
        self.assertEqual(cm.exception.code, "GODOT_FAILED")
        missing = _godot_result()
        del missing["samples"]["draw_calls"]
        with self.assertRaises(C.GamekitError):
            P.normalize_result(missing, frames=4, leak_cycles=4)
        bad_cycles = _godot_result()
        bad_cycles["leak_samples"] = _leak([1, 1, 1], [1, 1, 1])
        with self.assertRaises(C.GamekitError):
            P.normalize_result(bad_cycles, frames=4, leak_cycles=4)


class CliAndRejectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._old_state = os.environ.get("HH_GAMEKIT_STATE")
        os.environ["HH_GAMEKIT_STATE"] = str(self.root / "state")
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "project.godot").write_text(
            'config_version=5\n\n[application]\n\nconfig/name="game"\nrun/main_scene="res://main.tscn"\n',
            encoding="utf-8",
        )
        (self.game / "main.tscn").write_text('[gd_scene format=3]\n\n[node name="Main" type="Node2D"]\n', encoding="utf-8")
        self.project = C.Project("game", self.game)

    def tearDown(self) -> None:
        if self._old_state is None:
            os.environ.pop("HH_GAMEKIT_STATE", None)
        else:
            os.environ["HH_GAMEKIT_STATE"] = self._old_state
        self.tmp.cleanup()

    def test_cli_registers_perf(self) -> None:
        args = build_parser().parse_args(["perf", "demo", "--frames", "9", "--warmup", "1", "--leak-cycles", "3",
                                          "--headless", "--resolution", "640x360"])
        self.assertEqual(args.command, "perf")
        self.assertEqual(args.frames, 9)
        self.assertEqual(args.leak_cycles, 3)
        self.assertTrue(args.headless)
        self.assertTrue(callable(args.func))

    def test_run_report_rejects_before_godot(self) -> None:
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=0, warmup=0, leak_cycles=3)
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=10, warmup=0, leak_cycles=2)
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=10, warmup=0, leak_cycles=3, resolution="big")
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        bad_budget = self.root / "bad.json"
        bad_budget.write_text('{"nope": 1}\n', encoding="utf-8")
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=10, warmup=0, leak_cycles=3, budget_path=bad_budget)
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        self.assertIn("nope", cm.exception.detail)
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=10, warmup=0, leak_cycles=3, out_path=self.game / "inside.json")
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        bad_trace = self.root / "trace.json"
        bad_trace.write_text('{"fps": 60, "events": [{"frame": 0, "action": "x", "pressed": 1}]}', encoding="utf-8")
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, frames=10, warmup=0, leak_cycles=3, trace_path=bad_trace)
        self.assertEqual(cm.exception.code, "BAD_REQUEST")
        with self.assertRaises(C.GamekitError) as cm:
            P.run_report(self.project, scene="res://missing.tscn", frames=10, warmup=0, leak_cycles=3)
        self.assertEqual(cm.exception.code, "NOT_FOUND")
        self.assertFalse((self.game / "inside.json").exists())


if __name__ == "__main__":
    unittest.main()
