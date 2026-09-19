"""Strict S107 artifact reader. Valid artifacts are not formal acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics

ROW_MARKER = "HH_GT06_S107_PREVIEW_COST "
COMPLETE_MARKER = "HH_GT06_S107_PREVIEW_COST_COMPLETE "
BINDINGS = ("run_id", "pid", "source_closure_sha256", "profile_sha256",
            "base_source_sha256", "recipe_sha256", "generated_overlay_sha256",
            "diagnostic_closure_sha256", "context_sha256")
HASH_FIELDS = ("scene_before_sha256", "scene_sha256", "script_sha256",
               "script_before_sha256", "scene_reloaded_sha256", "script_reloaded_sha256",
               "baseline_sha256", "before_sha256", "created_sha256",
               "undone_sha256", "reloaded_sha256")


def require(ok, message):
    if not ok:
        raise ValueError("S107_READER_" + message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def decode(data: bytes):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "DUPLICATE_KEY")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("S107_READER_NONFINITE")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=invalid_constant)


def is_hash(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def bound(record, expected):
    for key in BINDINGS:
        require(key in expected and record.get(key) == expected[key], "BINDING_" + key)
    require(record.get("formal_acceptance") is False and
            record.get("eligible_for_dataset") is False, "ACCEPTANCE_FLAGS")


def integer(record, key):
    value = record.get(key)
    require(type(value) is int and value >= 0, "INTEGER_" + key)
    return value


def distribution(values):
    ordered = sorted(values)
    return {"count": len(values), "min_ms": min(values),
            "median_ms": statistics.median(values),
            "p95_nearest_rank_ms": ordered[math.ceil(.95 * len(values)) - 1],
            "max_ms": max(values), "mean_ms": statistics.mean(values)}


def analyze(stdout: bytes, report: bytes, index: bytes, expected: dict) -> dict:
    """Validate exact artifacts, return all observations and paired differences.

    ``expected.pid`` must come from the retained owned-process receipt. Caller
    independently validates lifecycle, source pins, Stop and cleanup; this pure
    reader cannot infer them from artifact claims.
    """
    require(type(expected.get("pid")) is int and expected["pid"] > 0, "EXPECTED_PID")
    for key in BINDINGS[2:]:
        require(is_hash(expected.get(key)), "EXPECTED_HASH_" + key)
    rows, complete = [], []
    for line in stdout.decode("utf-8").splitlines():
        if line.startswith(ROW_MARKER):
            require(not complete, "ROW_AFTER_COMPLETE")
            rows.append(decode(line[len(ROW_MARKER):].encode()))
        elif line.startswith(COMPLETE_MARKER):
            complete.append(decode(line[len(COMPLETE_MARKER):].encode()))
    require(len(complete) == 1, "COMPLETE_COUNT")
    final = complete[0]
    data, native = decode(report), decode(index)
    bound(final, expected)
    bound(data, expected)
    require(final.get("schema_id") == "hh-studio.s107-preview-cost-complete" and
            final.get("schema_version") == "1.0.0", "COMPLETE_SCHEMA")
    require(data.get("schema_id") == "hh-studio.s107-preview-cost" and
            data.get("schema_version") == "1.0.0", "REPORT_SCHEMA")
    require(len(rows) == 40 and data.get("row_count") == 40 and
            final.get("row_count") == 40 and final.get("cycles") == 40,
            "ROW_COUNT")
    require(data.get("completed") is True and final.get("completed") is True,
            "INCOMPLETE")
    require(data.get("rows") == rows, "REPORT_STDOUT_ROWS")
    require(data.get("arms") == final.get("arms") == {"A": 20, "B": 20}, "ARMS")
    require(data.get("rows_sha256") == final.get("rows_sha256") == sha(canonical(rows)),
            "ROWS_HASH")
    require(final.get("report_file") == "preview-cost.json" and
            final.get("report_sha256") == sha(report) and
            final.get("report_size_bytes") == len(report) and
            final.get("index_sha256") == sha(index), "ARTIFACT_HASH")
    require(native.get("pid") == expected["pid"] and
            native.get("input", {}).get("run_id") == expected["run_id"] and
            native.get("completed") is True and
            native.get("formal_acceptance") is False and
            native.get("benchmark_complete") is False and
            native.get("host_integrated") is False and
            native.get("batches_completed") == 1 and
            native.get("cycles_per_batch") == 40, "NATIVE_INDEX")
    observed = []
    normalized_scene, script, baseline = None, None, None
    previous = None
    for number, row in enumerate(rows):
        bound(row, expected)
        require(row.get("schema_id") == "hh-studio.s107-preview-cost-cycle" and
                row.get("schema_version") == "1.0.0", "ROW_SCHEMA")
        arm = "ABBA"[number % 4]
        require(row.get("cycle") == number and row.get("group") == number // 4 and
                row.get("position") == number % 4 and row.get("arm") == arm,
                "ABBA_ORDER")
        require(row.get("method") == ("save_scene" if arm == "A" else "save_scene_as") and
                row.get("with_preview") is (arm == "A"), "METHOD")
        require((type(row.get("return_error")) is int and row["return_error"] == 0)
                if arm == "A" else ("return_error" in row and row["return_error"] is None),
                "RETURN_ERROR")
        require(row.get("completed") is True and row.get("effects") ==
                {"create": 1, "undo": 1, "save": 1, "reload": 1}, "EFFECTS")
        for key in HASH_FIELDS:
            require(is_hash(row.get(key)), "HASH_" + key)
        if number == 0:
            normalized_scene, script, baseline = (row["scene_sha256"],
                                                   row["script_sha256"], row["baseline_sha256"])
        require(row["scene_sha256"] == row["scene_reloaded_sha256"] == normalized_scene and
                row["script_before_sha256"] == row["script_sha256"] ==
                row["script_reloaded_sha256"] == script,
                "FILE_DRIFT")
        if number:
            require(row["scene_before_sha256"] == normalized_scene, "PRESAVE_DRIFT")
        require(row["baseline_sha256"] == row["before_sha256"] ==
                row["undone_sha256"] == row["reloaded_sha256"] == baseline and
                row["created_sha256"] != baseline, "SEMANTIC_READBACK")
        require(integer(row, "root_before") > 0 and integer(row, "root_after") > 0 and
                row["root_before"] != row["root_after"] and
                integer(row, "generation_after") == integer(row, "generation_before") + 1,
                "RELOAD_IDENTITY")
        require(integer(row, "signal_count_after") == integer(row, "signal_count_before") + 1,
                "SIGNAL_COUNT")
        times = [integer(row, key) for key in
                 ("process_entry_us", "save_start_us", "call_entry_us", "signal_us",
                  "call_return_us", "save_process_exit_us", "next_process_entry_us",
                  "readback_end_us", "next_process_exit_us")]
        require(times == sorted(times) and times[2] < times[4], "BOUNDARY_ORDER")
        frames = [integer(row, key) for key in
                  ("process_entry_frame", "signal_frame", "save_process_exit_frame",
                   "next_process_entry_frame", "next_process_exit_frame")]
        # Engine frame can advance within the synchronous stock save call.
        require(frames[0] <= frames[1] <= frames[2] < frames[3] == frames[4], "FRAME_ORDER")
        if previous:
            require(row["process_entry_us"] > previous["next_process_exit_us"] and
                    row["generation_before"] == previous["generation_after"] and
                    row["root_before"] == previous["root_after"], "CYCLE_CONTINUITY")
        previous = row
        observed.append({"cycle": number, "group": number // 4, "arm": arm,
                         "call_ms": (times[4] - times[2]) / 1000,
                         "signal_to_return_ms": (times[4] - times[3]) / 1000,
                         "return_to_next_dispatch_ms": (times[6] - times[4]) / 1000,
                         "save_phase_to_next_dispatch_ms": (times[6] - times[0]) / 1000})
    arms = {arm: {key: distribution([row[key] for row in observed if row["arm"] == arm])
                  for key in ("call_ms", "signal_to_return_ms", "return_to_next_dispatch_ms",
                              "save_phase_to_next_dispatch_ms")}
            for arm in ("A", "B")}
    paired = []
    for group in range(10):
        sample = observed[4 * group:4 * group + 4]
        paired.append({"group": group, "a_minus_b_call_ms":
                       statistics.mean([row["call_ms"] for row in sample if row["arm"] == "A"]) -
                       statistics.mean([row["call_ms"] for row in sample if row["arm"] == "B"])})
    return {"schema_id": "hh-studio.s107-preview-cost-derived", "schema_version": "1.0.0",
            "artifact_status": "VALIDATED", "formal_acceptance": False,
            "eligible_for_dataset": False, "root_cause_proven": False,
            "workload": "40 native cycles; 10 ABBA groups; no HTTP or PSS",
            "bindings": expected, "stdout_sha256": sha(stdout), "report_sha256": sha(report),
            "index_sha256": sha(index), "arms": arms, "paired_groups": paired,
            "observations": observed, "all_rows_retained": True,
            "limitations": ["Lifecycle and cleanup require independent retained receipts.",
                            "Preview contrast does not prove the cause of S102 residency latency.",
                            "No formal workload change or automatic retry is authorized by this reader."]}


def main():
    parser = argparse.ArgumentParser()
    for name in ("stdout", "report", "index", "context", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    result = analyze(args.stdout.read_bytes(), args.report.read_bytes(),
                     args.index.read_bytes(), decode(args.context.read_bytes()))
    with args.output.open("xb") as output:
        output.write(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False).encode() + b"\n")


if __name__ == "__main__":
    main()
