"""Read-only S140 terminal analysis; output is diagnostic, never acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

METRICS = ("private_commit_bytes", "working_set_bytes", "allocated_blocks", "page_fault_count")
PHASES = ("command_completed", "command_released_gc", "native_batch_marker",
          "native_validated_before_editor", "editor_sample", "ack_received",
          "assembly_before", "assembly_after", "screen_sample", "assembly_released_gc")


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def delta(first, last):
    return {key: last[key] - first[key]
            if type(first.get(key)) is int and type(last.get(key)) is int else None
            for key in METRICS}


def analyze(run):
    summary = read(run / "diagnostic-summary.json")
    phases = read(run / "phase-memory.json")
    result = read(run / "result.json")
    context = read(run / "attempt/context.json")
    cleanup = read(run / "attempt/child-terminal-cleanup.json")
    assert summary["phase_sha256"] == digest(run / "phase-memory.json")
    assert summary["run_id"] == result["run_id"] == run.name
    assert context["run_id"] == phases["run_id"] == cleanup["run_id"]
    assert phases["formal_acceptance"] is False and phases["rows_dropped"] == 0
    assert summary["phase_rows"] == len(phases["rows"]) == phases["row_count"]
    grouped = {}
    prior = -1
    for seq, row in enumerate(phases["rows"]):
        assert row["sequence"] == seq and row["mono_us"] >= prior
        prior = row["mono_us"]
        assert row["host_identity"] == phases["identities"]["host"]
        assert row["host_memory"]["unavailable_reason"] is None
        if row["editor_identity"] is not None:
            assert row["editor_identity"] == phases["identities"]["editor"]
            assert row["editor_memory"]["unavailable_reason"] is None
            assert row["editor_memory"]["allocated_blocks"] is None
        batch = grouped.setdefault(row["index"], {})
        assert row["phase"] not in batch
        batch[row["phase"]] = row
    table = []
    for index, batch in sorted(grouped.items()):
        observed_order = list(batch)
        expected = list(PHASES)
        if "screen_rejected" in batch:
            expected = list(PHASES[:8]) + ["screen_rejected"]
        assert observed_order == expected, (index, observed_order)
        joint = read(run / "attempt" / f"joint-{index:02d}.json")
        assert joint["processes"] == phases["identities"]
        assert joint["run_id"] == phases["run_id"]
        command = read(run / "attempt" / f"command-{index:02d}.json")
        assert command["index"] == index
        points = {phase: row["host_memory"] for phase, row in batch.items()}
        table.append({"index": index, "gate_rejected": "screen_rejected" in batch,
            "phase_host_memory": points,
            "native_interval": delta(points["command_released_gc"], points["native_batch_marker"]),
            "native_validation_interval": delta(points["native_batch_marker"], points["native_validated_before_editor"]),
            "artifact_binding_interval": delta(points["ack_received"], points["assembly_before"]),
            "assembly_interval": delta(points["assembly_before"], points["assembly_after"]),
            "released_end_minus_command_gc": delta(points["command_released_gc"], points["assembly_released_gc"])
                if "assembly_released_gc" in points else None,
            "joint_host_rss": joint["host"]["counters"]["rss_bytes"]["value"],
            "effect_count": joint["host_effect_count"],
            "raw_refs": {name: {"file": str(path.relative_to(run)), "sha256": digest(path)}
                         for name, path in (("joint", run/"attempt"/f"joint-{index:02d}.json"),
                                            ("command", run/"attempt"/f"command-{index:02d}.json"))}})
    comparison = {}
    if 4 in grouped and 5 in grouped:
        for phase in PHASES:
            if phase in grouped[4] and phase in grouped[5]:
                comparison[phase] = delta(grouped[4][phase]["host_memory"], grouped[5][phase]["host_memory"])
    return {"schema": "HH-GT06-S140-phase-analysis-1", "authority": 0,
        "run_id": run.name, "formal_acceptance": False, "eligible_for_dataset": False,
        "status": summary["status"], "primary_error": summary["primary_error"],
        "source_unchanged": result["observations"]["source_unchanged"],
        "execution_unchanged": result["observations"]["execution_unchanged"],
        "completed_batches": cleanup["completed_batches"], "batches": table,
        "batch5_minus_batch4": comparison,
        "max_measurement_overhead_us": max((r["measurement_overhead_us"] for r in phases["rows"]), default=None),
        "receipts": {name: digest(run/name) for name in ("phase-memory.json", "diagnostic-summary.json", "result.json", "attempt/child-terminal-cleanup.json")},
        "limits": ["Instrumented process; no overhead subtraction.",
                   "Phase intervals include stock work between hooks, not per-function attribution.",
                   "Private commit, working set and allocated blocks are distinct metrics.",
                   "No leak/root-cause or formal PASS inference; terminal lifecycle must be reviewed separately."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = analyze(args.run.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"analysis": str(args.output), "batches": len(value["batches"]), "status": value["status"]}))
