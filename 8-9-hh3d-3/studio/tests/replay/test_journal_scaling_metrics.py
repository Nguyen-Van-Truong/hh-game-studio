"""Pure tests for the bounded O7 retained-probe verifier.

All data here is synthetic and lives in temporary directories.  The tests
exercise the evidence binding and finite workload gate without launching the
engine, a probe, a Docker container, or a measurement campaign.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from studio.tests.replay import journal_scaling_metrics as scaling
from studio.tests.replay import residency_metrics


def _stats(values):
    return scaling.stats(list(values))


def _probe_fixture():
    """Return a complete retained probe with truthful raw statistics."""
    blocks = []
    rng = random.Random(scaling.ORDER_SEED)
    for round_id in range(scaling.ROUNDS):
        order = [(seed, interval) for seed in scaling.SEEDS
                 for interval in scaling.INTERVALS]
        rng.shuffle(order)
        for seed, interval in order:
            # Interval 1 is the production trim and is intentionally slower for
            # the large seed by 10%.  Interval 64 is a valid, excluded control.
            factor = 1.10 if seed == "late" else 1.0
            if interval == 64:
                factor += 0.35
            lookup = [round(1.0 * factor, 6)] * scaling.OPERATION_COUNTS["lookup_ms"]
            append = [round(2.0 * factor, 6)] * scaling.OPERATION_COUNTS["append_ms"]
            blocks.append({
                "round": round_id, "seed": seed, "interval": interval,
                "system_cpu_percent": 40.0,
                "wall_seconds": 0.2,
                "lookup_ms": lookup, "append_ms": append,
                "metrics": {"lookup_ms": _stats(lookup), "append_ms": _stats(append)},
            })
    summaries = []
    for seed in scaling.SEEDS:
        for interval in scaling.INTERVALS:
            chosen = [b for b in blocks if (b["seed"], b["interval"]) == (seed, interval)]
            summaries.append({"seed": seed, "interval": interval, "metrics": {
                operation: _stats([v for b in chosen for v in b[operation]])
                for operation in scaling.OPERATION_COUNTS
            }})
    return {"authority": 0, "acceptance": False, "blocks": blocks,
            "summary": summaries, "source_after_equal": True,
            "seed_unchanged": True}


def _refresh_stats(probe):
    """Keep claims truthful when a test deliberately changes measured arrays."""
    for block in probe["blocks"]:
        block["metrics"] = {op: _stats(block[op]) for op in scaling.OPERATION_COUNTS}
    for summary in probe["summary"]:
        chosen = [b for b in probe["blocks"]
                  if (b["seed"], b["interval"]) == (summary["seed"], summary["interval"])]
        summary["metrics"] = {
            op: _stats([v for b in chosen for v in b[op]])
            for op in scaling.OPERATION_COUNTS}


def _write_bound_fixture(root):
    """Small original seeds bound to a retained source journal and its sizes."""
    probe = root / "probe-result.json"
    code = root / "probe.py"
    seeds, source, soak = (root / name for name in ("seeds", "source", "soak"))
    seeds.mkdir()
    (soak / "commands").mkdir(parents=True)
    code.write_text("probe", encoding="utf-8")
    lines = [json.dumps({"command_id": f"cmd.{index}"}).encode() + b"\n"
             for index in range(7)]
    early_bytes, late_bytes = lines[0], b"".join(lines[:6])
    (seeds / "early.jsonl").write_bytes(early_bytes)
    (seeds / "late.jsonl").write_bytes(late_bytes)
    journal = soak / "commands" / "commands.jsonl"
    journal.write_bytes(b"".join(lines))
    names = ("host/core/journal.py", "host/replay/verified_journal.py",
             "host/replay/disk_journal_index.py")
    manifest = {}
    for name in names:
        path = source / Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
        manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = _probe_fixture()
    payload.update({
        "source_before": manifest,
        "source_closure": scaling.source_closure(manifest),
        "seed_hashes": {
            seed: hashlib.sha256((seeds / f"{seed}.jsonl").read_bytes()).hexdigest()
            for seed in scaling.SEEDS},
    })
    probe.write_text(json.dumps(payload), encoding="utf-8")
    (soak / "source-files.json").write_text(json.dumps(manifest), encoding="utf-8")
    soak_result = {"run_id": soak.name, "completed": True,
                   "source_unchanged": True, "formal_acceptance": False,
                   "source_closure_sha256": scaling.source_closure(manifest)}
    (soak / "result.json").write_text(json.dumps(soak_result), encoding="utf-8")
    for index, raw in ((4, early_bytes), (34, late_bytes)):
        (soak / f"summary-{index:02}.json").write_text(
            json.dumps({"journal_bytes": len(raw)}), encoding="utf-8")
    return {"probe": probe, "code": code,
            "probe_sha": hashlib.sha256(code.read_bytes()).hexdigest(),
            "seeds": seeds, "source": source, "soak": soak, "manifest": manifest,
            "journal": journal, "early_bytes": early_bytes, "late_bytes": late_bytes,
            "payload": payload}


class JournalScalingMetricTests(unittest.TestCase):
    def test_full_six_round_order_and_counts_are_required(self):
        probe = _probe_fixture()
        report = scaling.calculate_probe(probe)
        self.assertEqual(report["rounds"], 6)
        self.assertEqual(report["baseline_interval"], 1)
        self.assertEqual(report["excluded_experimental_interval"], 64)
        self.assertEqual(report["baseline_blocks"], 12)
        self.assertEqual(report["blocks_per_seed"], 6)
        self.assertEqual(report["excluded_experimental_blocks"], 12)
        self.assertEqual(len(report["baseline_block_observations"]), 12)
        self.assertEqual(report["checks"], {"lookup": True, "append": True})
        self.assertAlmostEqual(report["latency"]["lookup"]["large_over_small_median_percent"], 110.0)
        self.assertAlmostEqual(report["latency"]["append"]["large_over_small_median_percent"], 110.0)

        missing = copy.deepcopy(probe)
        missing["blocks"].pop()
        with self.assertRaisesRegex(ValueError, "PROBE_ROUND_COVERAGE"):
            scaling.calculate_probe(missing)
        reordered = copy.deepcopy(probe)
        reordered["blocks"][0], reordered["blocks"][1] = reordered["blocks"][1], reordered["blocks"][0]
        with self.assertRaisesRegex(ValueError, "PROBE_RANDOMIZED_ORDER"):
            scaling.calculate_probe(reordered)

    def test_only_production_interval_one_gates_and_summary_is_recomputed(self):
        probe = _probe_fixture()
        # The excluded interval is deliberately very slow; it cannot change
        # the interval=1 gate.
        for block in probe["blocks"]:
            if block["interval"] == 64:
                block["lookup_ms"] = [100.0] * 50
                block["append_ms"] = [100.0] * 75
        # Caller summaries are never trusted by the verifier.
        probe["summary"][0]["metrics"]["lookup_ms"]["median_ms"] = 0.001
        with self.assertRaisesRegex(ValueError, "PROBE_FORGED_STATS"):
            scaling.calculate_probe(probe)
        probe = _probe_fixture()
        report = scaling.calculate_probe(probe)
        self.assertTrue(all(report["checks"].values()))
        self.assertEqual(report["excluded_experimental_blocks"], 12)

    def test_fast_experiment_cannot_mask_failing_production_interval(self):
        probe = _probe_fixture()
        for block in probe["blocks"]:
            if block["seed"] == "late":
                factor = 1.31 if block["interval"] == 1 else 0.01
                block["lookup_ms"] = [factor] * scaling.OPERATION_COUNTS["lookup_ms"]
                block["append_ms"] = [2 * factor] * scaling.OPERATION_COUNTS["append_ms"]
        _refresh_stats(probe)
        report = scaling.calculate_probe(probe)
        self.assertEqual(report["checks"], {"lookup": False, "append": False})
        self.assertEqual(report["latency"]["lookup"]["large_over_small_median_percent"], 131.0)

    def test_probe_shape_rejects_nonfinite_boolean_and_missing_fields(self):
        for mutate, code in (
            (lambda p: p["blocks"][0].update(system_cpu_percent=True), "PROBE_CPU"),
            (lambda p: p["blocks"][0].update(wall_seconds=float("inf")), "PROBE_WALL_WINDOW"),
            (lambda p: p["blocks"][0]["lookup_ms"].append(1.0), "PROBE_OPERATION_COVERAGE"),
            (lambda p: p["blocks"][0]["metrics"]["append_ms"].update(n=1), "PROBE_FORGED_STATS"),
        ):
            probe = _probe_fixture()
            mutate(probe)
            with self.subTest(code=code):
                with self.assertRaisesRegex(ValueError, code):
                    scaling.calculate_probe(probe)

    def test_complete_o7_file_binding_rejects_missing_or_altered_probe_seed_and_source(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _write_bound_fixture(Path(td))
            with mock.patch.object(scaling, "INSPECTED_PROBE_SHA256", paths["probe_sha"]), \
                 mock.patch.object(scaling, "current_probe_sources", return_value=paths["manifest"]):
                result = scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                                  source_root=paths["source"], soak_root=paths["soak"])
                self.assertTrue(result["checks"]["lookup"])
                self.assertEqual(result["baseline_blocks"], 12)
                self.assertEqual(result["evidence_binding"]["current_source_graph_consistent"], True)

                with self.assertRaisesRegex(ValueError, "PROBE_INSPECTED_CODE_CHANGED"):
                    paths["code"].write_text("altered", encoding="utf-8")
                    scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                              source_root=paths["source"], soak_root=paths["soak"])
                paths["code"].write_text("probe", encoding="utf-8")
                paths["probe"].write_text(json.dumps({**paths["payload"], "seed_unchanged": False}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "PROBE_UNCHANGED_FLAGS"):
                    scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                              source_root=paths["source"], soak_root=paths["soak"])

                paths["probe"].write_text(json.dumps(paths["payload"]), encoding="utf-8")
                paths["seeds"].joinpath("early.jsonl").write_bytes(b"x")
                with self.assertRaisesRegex(ValueError, "PROBE_SEED_HASH"):
                    scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                              source_root=paths["source"], soak_root=paths["soak"])

                paths["seeds"].joinpath("early.jsonl").write_bytes(paths["early_bytes"])
                # Rehashing a caller supplied claim cannot authorize a mutated
                # seed: the retained journal prefix is the independent anchor.
                mutated = b'{"command_id": "cmd.9"}\n'
                self.assertEqual(len(mutated), len(paths["early_bytes"]))
                paths["seeds"].joinpath("early.jsonl").write_bytes(mutated)
                changed_payload = copy.deepcopy(paths["payload"])
                changed_payload["seed_hashes"]["early"] = hashlib.sha256(mutated).hexdigest()
                paths["probe"].write_text(json.dumps(changed_payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "PROBE_SEED_PREFIX"):
                    scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                              source_root=paths["source"], soak_root=paths["soak"])
                paths["seeds"].joinpath("early.jsonl").write_bytes(paths["early_bytes"])
                paths["probe"].write_text(json.dumps(paths["payload"]), encoding="utf-8")
                source_file = paths["source"] / "host" / "core" / "journal.py"
                source_file.write_text("changed", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "PROBE_SOURCE_CHANGED"):
                    scaling.read_bound_probe(paths["probe"], paths["seeds"],
                                              source_root=paths["source"], soak_root=paths["soak"])

    def test_missing_probe_is_rejected_before_o7_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "INTERLEAVED_PROBE_REQUIRED"):
                residency_metrics.from_run(Path(td), policy=residency_metrics.O7_POLICY)


if __name__ == "__main__":
    unittest.main()
