"""Read S103 additive native save observations; never run an engine or mutate input.

Exit 0 means the supplied files were parsed, including a valid UNKNOWN report;
it is not benchmark acceptance. Exit 2 means malformed or mismatched evidence.
Missing call-return, incomplete observation, or unproven/forced target shutdown
remain UNKNOWN. Legacy S102 save/signal/heartbeat data cannot invent a return.
All intervals use native microseconds; no host/native clock subtraction occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ENTER = "HH_GT06_S103_SAVE_ENTER "
COMPLETE = "HH_GT06_S103_SAVE_COMPLETE "
SCHEMA = "hh-studio.s103-native-save"
MAX_FILE_BYTES = 16 * 1024 * 1024
# The overlay owns one bounded pending record at a time and allows at most
# seven diagnostic batches (0..6), with the normal 100-cycle batch shape.
MAX_EVENTS = 700
MAX_BATCHES = 7
MAX_CYCLES = 100
THRESHOLD_US = 2_000_000
IDENTITY = ("run_id", "pid", "batch", "cycle", "sequence",
            "source_closure_sha256", "profile_sha256", "probe_source_sha256")
ENTER_TIMES = ("save_start_us", "process_entry_us", "process_entry_frame", "entry_event_us")
COMPLETE_TIMES = ("call_entry_us", "call_return_us", "signal_us", "signal_frame",
                  "save_process_exit_us", "save_process_exit_frame",
                  "next_process_entry_us", "next_process_entry_frame",
                  "next_process_exit_us", "next_process_exit_frame", "readback_end_us")
HASH = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(EvidenceError(value)))
    except (ValueError, UnicodeError) as error:
        raise EvidenceError("invalid JSON: " + str(error)) from error


def read_file(path, evidence):
    path = Path(path)
    require(path.is_file(), "missing input: " + str(path))
    require(path.stat().st_size <= MAX_FILE_BYTES, "oversized input: " + str(path))
    raw = path.read_bytes()
    require(len(raw) <= MAX_FILE_BYTES, "oversized input: " + str(path))
    ref = {"file": str(path.absolute()), "size_bytes": len(raw),
           "sha256": hashlib.sha256(raw).hexdigest()}
    evidence.append(ref)
    return raw, ref


def validate_event(event, kind, native_sha):
    require(type(event) is dict, "event is not an object")
    required = {"schema_id", "schema_version", "event", "formal_acceptance", *IDENTITY, *ENTER_TIMES}
    if kind == "save_complete":
        required |= {*COMPLETE_TIMES, "save_result", "failed", "observation_complete"}
    require(set(event) == required, "unexpected event fields")
    require(event["schema_id"] == SCHEMA and event["schema_version"] == "1.0.0"
            and event["event"] == kind and event["formal_acceptance"] is False, "event schema/binding")
    require(type(event["run_id"]) is str and bool(event["run_id"]), "invalid run ID")
    require(integer(event["pid"], 1) and integer(event["batch"]) and event["batch"] < MAX_BATCHES
            and integer(event["cycle"]) and event["cycle"] < MAX_CYCLES
            and integer(event["sequence"], 1) and event["sequence"] <= MAX_EVENTS,
            "invalid event cycle identity")
    for field in ("source_closure_sha256", "profile_sha256", "probe_source_sha256"):
        require(type(event[field]) is str and HASH.fullmatch(event[field]), "invalid hash: " + field)
    require(event["probe_source_sha256"] == native_sha, "native source bytes do not match event")
    for field in ENTER_TIMES:
        require(integer(event[field], 1), "invalid entry boundary: " + field)
    require(event["process_entry_us"] <= event["save_start_us"] <= event["entry_event_us"],
            "entry boundary order")
    if kind == "save_complete":
        for field in COMPLETE_TIMES:
            require(integer(event[field]), "invalid completion boundary: " + field)
        require(type(event["failed"]) is bool and type(event["observation_complete"]) is bool
                and type(event["save_result"]) is int, "invalid completion flags")


def parse_markers(raw, native_sha):
    events = {}
    binding = None
    sequence_keys = {}
    last_sequence = 0
    for line_no, raw_line in enumerate(raw.splitlines(), 1):
        try:
            line = raw_line.decode("utf-8")
        except UnicodeError as error:
            raise EvidenceError("native stdout is not UTF-8") from error
        prefix = ENTER if line.startswith(ENTER) else COMPLETE if line.startswith(COMPLETE) else None
        if prefix is None:
            continue
        kind = "save_enter" if prefix == ENTER else "save_complete"
        event = decode(line[len(prefix):])
        validate_event(event, kind, native_sha)
        sequence = event["sequence"]
        current_key = (event["batch"], event["cycle"])
        prior_key = sequence_keys.get(sequence)
        require(prior_key is None or prior_key == current_key,
                "sequence reused for different cycle")
        sequence_keys[sequence] = current_key
        require(sequence >= last_sequence, "native event sequence regressed")
        last_sequence = sequence
        current = tuple(event[name] for name in ("run_id", "pid", "source_closure_sha256", "profile_sha256"))
        if binding is None:
            binding = current
        require(current == binding, "mixed run/PID/source/profile events")
        key = (event["batch"], event["cycle"])
        group = events.setdefault(key, {})
        require(kind not in group, "duplicate event for cycle")
        require(len(events) <= MAX_EVENTS, "native observation capacity exceeded")
        group[kind] = (event, line_no)
    for group in events.values():
        if "save_enter" in group and "save_complete" in group:
            enter, enter_line = group["save_enter"]
            complete, complete_line = group["save_complete"]
            require(enter_line < complete_line, "completion precedes enter marker")
            require(all(enter[name] == complete[name] for name in (*IDENTITY, *ENTER_TIMES)),
                    "enter/completion binding mismatch")
    return events, binding


def read_batches(paths, evidence):
    rows = {}
    bindings = set()
    for path in paths:
        raw, ref = read_file(path, evidence)
        batch = decode(raw)
        require(type(batch) is dict and batch.get("schema_id") == "hh-studio.native-cycle-batch"
                and integer(batch.get("index")) and batch["index"] < MAX_BATCHES
                and integer(batch.get("pid"), 1)
                and type(batch.get("run_id")) is str and bool(batch["run_id"])
                and type(batch.get("raw_timings")) is list,
                "invalid raw native batch")
        require(len(batch["raw_timings"]) <= 100, "raw cycle capacity exceeded")
        bindings.add((batch["run_id"], batch["pid"]))
        for timing in batch["raw_timings"]:
            require(type(timing) is dict and integer(timing.get("index"))
                    and timing["index"] < MAX_CYCLES, "invalid raw timing")
            key = (batch["index"], timing["index"])
            require(key not in rows, "duplicate raw cycle")
            save = timing.get("save")
            require(type(save) is dict and integer(save.get("start_us"), 1)
                    and integer(save.get("end_us"), 1)
                    and integer(timing.get("save_signal_mono_us"), 1)
                    and save["start_us"] <= timing["save_signal_mono_us"] <= save["end_us"],
                    "invalid raw save timing")
            rows[key] = {"run_id": batch["run_id"], "pid": batch["pid"], "timing": timing,
                         "evidence": ref}
    require(len(bindings) <= 1, "mixed raw run/PID")
    return rows, next(iter(bindings), None)


def lifecycle_state(path, pid, evidence):
    """Read lifecycle evidence without upgrading an exit from absence.

    Save-boundary rows are independent observations. An owner-close/forced
    stop is retained as its own lifecycle state and never turns a complete
    boundary row into UNKNOWN.
    """
    if path is None:
        return {"state": "UNKNOWN", "reason": "NO_INDEPENDENT_TARGET_EXIT_RECEIPT",
                "claim": "UNKNOWN"}
    raw, ref = read_file(path, evidence)
    capture = decode(raw)
    require(type(capture) is dict, "invalid lifecycle record")
    actual = capture.get("actual_process_exit")
    if actual is not None:
        require(type(actual) is dict and type(actual.get("pid")) is int and actual["pid"] == pid
                and type(actual.get("exit_code")) is int, "lifecycle target PID mismatch")
    job = capture.get("job", {})
    handle = capture.get("wrapper_process_handle", {})
    require(type(job) is dict and type(handle) is dict, "invalid lifecycle cleanup shape")
    natural = (capture.get("schema") == "HH-GT06-BENCHMARK-CAPTURE-2"
               and capture.get("completed") is True and capture.get("natural_tree_exit") is True
               and capture.get("wrapper_exit_code") == 0 and actual is not None
               and actual["exit_code"] == 0 and capture.get("active_before_cleanup") == 0
               and job.get("closed") is True and job.get("zero_observed") is True
               and job.get("active_count") == 0 and job.get("tainted") is False
               and job.get("handle_retained") is False and job.get("close_uncertain") is False
               and handle == {"required": True, "closed": True, "close_uncertain": False, "handle_retained": False})
    if natural:
        state, reason, claim = "NATURAL_TARGET_EXIT_RECORDED", None, "NATURAL_TARGET_EXIT"
    else:
        # An explicit owner-close receipt is a diagnostic stop. Scheduler
        # absence, a returned code, or PID polling alone is not one.
        explicit_forced = (capture.get("diagnostic_forced_stop") is True
                           or capture.get("forced_stop") is True
                           or capture.get("termination") == "forced")
        forced = (explicit_forced or
                  (capture.get("completed") is False
                   and type(capture.get("failure_code")) is str
                   and bool(capture.get("failure_code"))
                   and capture.get("job", {}).get("closed") is True
                   and capture.get("wrapper_process_handle", {}).get("closed") is True))
        if forced:
            state, reason, claim = ("DIAGNOSTIC_FORCED_STOP_RECORDED",
                                    "DIAGNOSTIC_OWNER_CLOSE_WITHOUT_TARGET_EXIT",
                                    "DIAGNOSTIC_FORCED_STOP")
        else:
            state, reason, claim = ("UNKNOWN", "FORCED_OR_UNPROVEN_NATURAL_TARGET_EXIT", "UNKNOWN")
    return {"state": state, "reason": reason, "claim": claim, "evidence": ref}


def classify_cycle(key, group, raw, lifecycle):
    enter = group.get("save_enter", (None, None))[0]
    complete = group.get("save_complete", (None, None))[0]
    event = complete or enter
    row = {"batch": key[0], "cycle": key[1], "classification": "UNKNOWN", "reasons": [],
           "line_numbers": {kind: value[1] for kind, value in group.items()},
           "intervals_us": {}, "frame_bounds": {}, "threshold_crossings": [],
           "raw_timing_matched": False, "signal_relation": "UNKNOWN"}
    if raw is not None:
        timing = raw["timing"]
        row["raw_timing_evidence"] = raw["evidence"]
        row["legacy_save_observation"] = {"start_us": timing["save"]["start_us"],
                                          "signal_us": timing["save_signal_mono_us"],
                                          "readback_end_us": timing["save"]["end_us"]}
        if event is not None:
            require((raw["run_id"], raw["pid"]) == (event["run_id"], event["pid"]), "raw event run/PID mismatch")
            require(timing["save"]["start_us"] == event["save_start_us"], "raw save start mismatch")
            if complete is not None:
                require(complete["signal_us"] in (0, timing["save_signal_mono_us"])
                        and complete["readback_end_us"] in (0, timing["save"]["end_us"]), "raw save completion mismatch")
            row["raw_timing_matched"] = True
    if enter is None:
        row["reasons"].append("MISSING_SAVE_ENTER_EVENT")
    if complete is None:
        row["reasons"].append("MISSING_CALL_RETURN_AND_COMPLETE_EVENT")
        return row
    if complete["failed"] or not complete["observation_complete"] or complete["save_result"] != 0:
        row["reasons"].append("FAILED_OR_INCOMPLETE_NATIVE_OBSERVATION")
    missing = [name for name in COMPLETE_TIMES if complete[name] == 0]
    if missing:
        row["missing_boundaries"] = missing
        row["reasons"].append("MISSING_NATIVE_BOUNDARY")
        return row
    e = complete
    require(e["entry_event_us"] <= e["call_entry_us"] <= e["call_return_us"] <= e["save_process_exit_us"]
            <= e["next_process_entry_us"] <= e["readback_end_us"] <= e["next_process_exit_us"],
            "save/process boundary order")
    # Godot may emit scene_saved synchronously or asynchronously after return.
    require(e["save_start_us"] <= e["signal_us"] <= e["readback_end_us"], "signal boundary order")
    require(e["process_entry_frame"] == e["save_process_exit_frame"]
            < e["next_process_entry_frame"] == e["next_process_exit_frame"]
            and e["process_entry_frame"] <= e["signal_frame"] <= e["next_process_exit_frame"], "frame boundary order")
    row["signal_relation"] = "INSIDE_SAVE_CALL" if e["signal_us"] <= e["call_return_us"] else "AFTER_SAVE_CALL_RETURN"
    row["intervals_us"] = {
        "entry_marker_to_call": e["call_entry_us"] - e["entry_event_us"],
        "save_call": e["call_return_us"] - e["call_entry_us"],
        "call_entry_to_signal": e["signal_us"] - e["call_entry_us"],
        "signal_to_call_return_signed": e["call_return_us"] - e["signal_us"],
        "after_call_in_save_dispatch": e["save_process_exit_us"] - e["call_return_us"],
        "between_process_dispatches": e["next_process_entry_us"] - e["save_process_exit_us"],
        "save_dispatch_outside_call": e["call_entry_us"] - e["process_entry_us"] + e["save_process_exit_us"] - e["call_return_us"],
        "next_process_dispatch": e["next_process_exit_us"] - e["next_process_entry_us"],
        "call_entry_to_next_process": e["next_process_entry_us"] - e["call_entry_us"],
        "save_to_readback": e["readback_end_us"] - e["save_start_us"],
    }
    row["frame_bounds"] = {name: e[name] for name in ("process_entry_frame", "signal_frame",
        "save_process_exit_frame", "next_process_entry_frame", "next_process_exit_frame")}
    for name in ("save_call", "between_process_dispatches", "save_dispatch_outside_call", "next_process_dispatch"):
        if row["intervals_us"][name] > THRESHOLD_US:
            row["threshold_crossings"].append(name)
    # Lifecycle is intentionally not a reason for a boundary row to become
    # UNKNOWN. A complete record observed before a diagnostic forced stop is
    # still a complete record; the separate lifecycle field carries the stop.
    blocking_reasons = [reason for reason in row["reasons"]
                        if reason != "MISSING_SAVE_ENTER_EVENT"]
    if not blocking_reasons:
        row["classification"] = ("OBSERVED_INTERVAL_OVER_THRESHOLD" if row["threshold_crossings"]
            else "COMBINED_INTERVAL_OVER_THRESHOLD" if row["intervals_us"]["call_entry_to_next_process"] > THRESHOLD_US
            else "NO_OBSERVED_INTERVAL_OVER_THRESHOLD")
    return row


def analyze(stdout_path, native_source, batch_paths=(), lifecycle_path=None, binding_path=None):
    evidence = []
    stdout, stdout_ref = read_file(stdout_path, evidence)
    _, source_ref = read_file(native_source, evidence)
    events, binding = parse_markers(stdout, source_ref["sha256"])
    raw_rows, raw_binding = read_batches(batch_paths, evidence)
    if binding is not None and raw_binding is not None:
        require(binding[:2] == raw_binding, "raw/native run/PID mismatch")
    if binding_path is not None:
        payload, _ = read_file(binding_path, evidence)
        expected = decode(payload)
        require(type(expected) is dict, "invalid expected input binding")
        if binding is not None:
            require(tuple(expected.get(name) for name in ("run_id", "source_closure_sha256", "profile_sha256"))
                    == (binding[0], binding[2], binding[3]), "input/event binding mismatch")
        elif raw_binding is not None:
            require(expected.get("run_id") == raw_binding[0], "input/raw run mismatch")
    pid = binding[1] if binding is not None else raw_binding[1] if raw_binding is not None else None
    lifecycle = lifecycle_state(lifecycle_path, pid, evidence)
    rows = [classify_cycle(key, events.get(key, {}), raw_rows.get(key), lifecycle)
            for key in sorted(set(events) | set(raw_rows))]
    return {"schema_id": "hh-studio.s103-native-save-reading", "schema_version": "1.0.0",
            "formal_acceptance": False, "eligible_for_dataset": False,
            "run_id": binding[0] if binding is not None else raw_binding[0] if raw_binding is not None else None,
            "pid": pid, "source_closure_sha256": binding[2] if binding else None,
            "profile_sha256": binding[3] if binding else None, "native_source": source_ref,
            "native_stdout": stdout_ref, "evidence": evidence, "lifecycle": lifecycle,
            "classification": "UNKNOWN" if not rows or any(row["classification"] == "UNKNOWN" for row in rows)
            else "OBSERVED_NATIVE_INTERVALS", "threshold_us": THRESHOLD_US,
            "cycle_count": len(rows), "cycles": rows,
            "limitations": ["Observed intervals do not establish disk, scheduler, renderer, or engine-internal causation.",
                "Entry-marker printing precedes call_entry; an entry marker alone does not prove save_scene began.",
                "Unchanged legacy save/signal/readback or heartbeat data cannot supply an absent call-return timestamp.",
                "No timing subtraction, acceptance override, benchmark PASS, or unobserved natural exit is inferred."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--native-source", required=True)
    parser.add_argument("--batch", action="append", default=[])
    parser.add_argument("--lifecycle")
    parser.add_argument("--binding")
    args = parser.parse_args(argv)
    try:
        result = analyze(args.stdout, args.native_source, args.batch, args.lifecycle, args.binding)
    except (EvidenceError, OSError) as error:
        print(json.dumps({"classification": "UNKNOWN", "error": str(error), "formal_acceptance": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
