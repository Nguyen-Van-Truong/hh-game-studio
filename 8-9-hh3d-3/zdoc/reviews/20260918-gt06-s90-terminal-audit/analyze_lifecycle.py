"""Bounded, read-only S90 prefix audit. Exit 0 verifies bindings, never acceptance.

No engine, runtime modules, network, process control, or source execution is used.
The JSON result binds derived lifecycle observations to raw bytes. Terminal files
are inventoried only: this verifier cannot certify process exits or a full run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

RUN = "gt06-s90-lifecycle-attribution-01"
SOURCE = "e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f"
PROFILE = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
EFFECTIVE = "af0cf5cb510e0d03f3f31c26f58e8ae3848cd1f5110be7c08929a144e58757ba"
HELPERS = {
    "zdoc/reviews/20260918-gt06-s90-lifecycle-attribution/diagnose_sequence_s90.py":
        "f92ca6c8db0c66f1f3f9ecabe11cd83313c48b676aee3fb64538b524a49d29c8",
    "zdoc/reviews/20260918-gt06-s90-lifecycle-attribution/lifecycle_probe_s90.gd":
        "879e445adf15b871544d881b2c3134f5b5a6e66cc043cc0155c00c20dd36b11e",
}
TERMINAL = (
    "supervisor-return.json", "child-terminal-cleanup.json", "child-result.json",
    "diagnostic-manifest.json", "host-owner/capture.json",
    "host-owner/process-exit.json", "editor-host/capture.json",
    "editor-host/process-exit.json", "import-host/capture.json",
    "import-host/process-exit.json",
)
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024


class InvalidEvidence(ValueError):
    pass


def need(condition, detail):
    if not condition:
        raise InvalidEvidence(detail)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def integer(value, name, minimum=0):
    need(type(value) is int and value >= minimum, "invalid integer: " + name)
    return value


class RawReader:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.artifacts = {}
        self.total = 0

    def path(self, name):
        rel = PurePosixPath(name)
        need(isinstance(name, str) and not rel.is_absolute() and
             all(p not in ("", ".", "..") for p in name.split("/")) and
             "\\" not in name and ":" not in name, "unsafe artifact path")
        path = self.root.joinpath(*rel.parts)
        need(path.resolve().is_relative_to(self.root), "artifact escapes raw root")
        for parent in (path, *path.parents):
            if parent == self.root:
                break
            need(not parent.is_symlink(), "symlink artifact: " + name)
        return path

    def exists(self, name):
        return self.path(name).is_file()

    def read(self, name):
        path = self.path(name)
        need(path.is_file(), "missing paired artifact: " + name)
        need(path.stat().st_size <= MAX_FILE_BYTES, "artifact too large: " + name)
        raw = path.read_bytes()
        need(len(raw) <= MAX_FILE_BYTES, "artifact grew beyond bound: " + name)
        self.total += len(raw)
        need(self.total <= MAX_TOTAL_BYTES, "total read bound exceeded")
        reference = {"sha256": sha(raw), "size_bytes": len(raw)}
        need(name not in self.artifacts or self.artifacts[name] == reference,
             "artifact changed during audit: " + name)
        self.artifacts[name] = reference
        return raw

    def obj(self, name, schema=None, version="1.0.0"):
        try:
            obj = json.loads(self.read(name), object_pairs_hook=unique_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(
                                 InvalidEvidence("nonfinite JSON: " + value)))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise InvalidEvidence("invalid JSON: " + name) from error
        need(type(obj) is dict, "expected JSON object: " + name)
        if schema:
            need(obj.get("schema_id") == schema and obj.get("schema_version") == version,
                 "schema mismatch: " + name)
        return obj

    def reference(self, ref, expected):
        need(type(ref) is dict and set(ref) == {"file", "sha256", "size_bytes"},
             "reference schema: " + expected)
        need(ref["file"] == expected, "reference path mismatch: " + expected)
        self.read(expected)
        need(ref["sha256"] == self.artifacts[expected]["sha256"] and
             type(ref["size_bytes"]) is int and
             ref["size_bytes"] == self.artifacts[expected]["size_bytes"],
             "reference hash/size mismatch: " + expected)


def identity(obj, label, index=None, key="index", bound=True):
    need(obj.get("run_id") == RUN, "run identity mismatch: " + label)
    if index is not None:
        need(type(obj.get(key)) is int and obj[key] == index, "batch identity mismatch: " + label)
    if bound:
        need(obj.get("source_closure_sha256") == SOURCE, "source binding mismatch: " + label)
        need(obj.get("profile_sha256") == PROFILE, "profile binding mismatch: " + label)


def counter(obj, key):
    value = obj[key]
    need(type(value) is dict and value.get("unavailable_reason") is None,
         "counter unavailable: " + key)
    return integer(value.get("value"), key)


def provenance(reader):
    diagnostic = reader.obj("diagnostic.json")
    context = reader.obj("context.json")
    identity(context, "context")
    need(diagnostic.get("run_id") == RUN and diagnostic.get("profile_sha256") == PROFILE and
         diagnostic.get("base_source_closure_sha256") == SOURCE, "diagnostic binding")
    for key in ("formal_acceptance", "eligible_for_dataset", "full_benchmark"):
        need(diagnostic.get(key) is False, "diagnostic exclusion missing: " + key)
    need(diagnostic.get("maximum_batches") == 35 and diagnostic.get("run_count") == 1 and
         diagnostic.get("http_commands_per_batch") == 1000 and
         diagnostic.get("native_cycles_per_batch") == 100, "diagnostic dimensions")
    need(context.get("campaign_sha256") == reader.artifacts["diagnostic.json"]["sha256"],
         "context diagnostic hash")
    files = reader.obj("source-files.json")
    need(len(files) == 51 and files == diagnostic.get("base_source_files") == context.get("source_files"),
         "source manifest disagreement")
    closure = sha("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode())
    need(closure == SOURCE, "source closure hash mismatch")
    for name, digest in files.items():
        need(sha(reader.read("source/studio/" + name)) == digest, "source file hash: " + name)
    need(diagnostic.get("helper_files") == HELPERS, "helper source identity mismatch")
    for name, digest in HELPERS.items():
        need(sha(reader.read("source/" + name)) == digest, "helper hash: " + name)
    reader.obj("benchmark-profile.json")
    need(reader.artifacts["benchmark-profile.json"]["sha256"] == PROFILE, "profile bytes hash")
    overlay = reader.obj("native-overlay.json")
    initial = reader.obj("initial-project-files.json")
    native_path = "project/addons/hh_benchmark/benchmark_native.gd"
    need(sha(reader.read(native_path)) == EFFECTIVE == overlay.get("effective_sha256") ==
         initial.get("addons/hh_benchmark/benchmark_native.gd"), "effective overlay hash mismatch")
    need(overlay.get("base_sha256") == files["tests/replay/benchmark_native.gd"] and
         overlay.get("probe_sha256") == HELPERS[next(k for k in HELPERS if k.endswith(".gd"))],
         "overlay source binding")
    for key in ("formal_acceptance", "eligible_for_dataset", "thresholds_modified", "runtime_source_modified"):
        need(overlay.get(key) is False, "overlay exclusion missing: " + key)
    input_path = "project/benchmark/input.json"
    binding = reader.obj(input_path, "hh-studio.native-cycle-benchmark-run", "1.2.0")
    identity(binding, "input")
    need(binding.get("mode") == "full" and binding.get("batch_start") == "host_permit_v1" and
         binding.get("batch_barrier") == "host_ack_v1", "input protocol")
    need(reader.artifacts[input_path]["sha256"] == initial.get("benchmark/input.json"), "initial input hash")
    return {"source_closure_sha256": closure, "profile_sha256": PROFILE,
            "source_file_count": len(files), "helper_files": HELPERS,
            "native_effective_sha256": EFFECTIVE}


def start_binding(reader, index):
    paths = {"ready": f"project/benchmark/out/ready-{index:02}.json",
             "start": f"project/benchmark/input/start-{index:02}.json",
             "command": f"command-{index:02}.json"}
    ready = reader.obj(paths["ready"], "hh-studio.native-cycle-batch-ready")
    start = reader.obj(paths["start"], "hh-studio.native-cycle-batch-start")
    command = reader.obj(paths["command"], "hh-studio.benchmark-command-batch", "1.1.0")
    identity(ready, "ready", index, "batch_index")
    identity(start, "start", index, "batch_index")
    identity(command, "command", index, bound=False)
    need(command.get("status") == "COMPLETE" and len(command["commands"]) == 1000 and
         command.get("complete_command_mix") is True, "command prefix incomplete")
    need(start["ready_sha256"] == reader.artifacts[paths["ready"]]["sha256"] and
         start["command_batch_sha256"] == reader.artifacts[paths["command"]]["sha256"],
         "start ready/command hash binding")
    need(start["deadline_mono_us"] == ready["deadline_mono_us"] and
         ready["start_file"] == paths["start"].removeprefix("project/"), "start deadline/path")
    return paths, ready, start, command


def batch(reader, index):
    paths, ready, start, command = start_binding(reader, index)
    paths.update({"lifecycle": f"project/benchmark/out/lifecycle-{index:02}.json",
                  "native": f"project/benchmark/out/batch-{index:02}.json",
                  "joint": f"joint-{index:02}.json", "capture": f"batch-capture-{index:02}.json",
                  "ack": f"project/benchmark/input/ack-{index:02}.json"})
    life = reader.obj(paths["lifecycle"], "hh-studio.gt06.s90-lifecycle")
    need(set(life) == {"schema_id", "schema_version", "run_id", "batch", "formal_acceptance",
         "eligible_for_dataset", "batch_publish_mono_us", "process_frame", "object_count_at_batch_publish",
         "resource_count_at_batch_publish", "object_count_at_ack_preopen", "object_count_after_file_close",
         "object_count_after_file_release", "object_delta_close_to_release", "object_count_after_fresh_ack",
         "resource_count_after_fresh_ack", "object_delta_batch_to_fresh_ack",
         "object_delta_ack_preopen_to_fresh_ack"}, "lifecycle field schema")
    integer(life["batch_publish_mono_us"], "batch_publish_mono_us")
    integer(life["process_frame"], "process_frame")
    native = reader.obj(paths["native"], "hh-studio.native-cycle-batch", "1.2.0")
    joint = reader.obj(paths["joint"], "hh-studio.benchmark-joint-observation")
    ack = reader.obj(paths["ack"], "hh-studio.native-cycle-batch-ack")
    capture = reader.obj(paths["capture"])
    identity(life, "lifecycle", index, "batch", False)
    identity(native, "native", index, bound=False)
    identity(joint, "joint", index)
    identity(ack, "ack", index, "batch_index")
    need(type(capture.get("index")) is int and capture["index"] == index, "capture index")
    need(set(capture) == {"index", "ready", "start", "command", "native", "joint", "ack"}, "capture field schema")
    for kind in ("ready", "start", "command", "native", "joint", "ack"):
        reader.reference(capture[kind], paths[kind])
    reader.reference(joint["ack_ref"], paths["ack"])
    need(life.get("formal_acceptance") is False and life.get("eligible_for_dataset") is False,
         "lifecycle exclusion")
    counts = {key: integer(value, key, -2147483648 if key.startswith("object_delta_") else 0)
              for key, value in life.items() if key.startswith(("object_", "resource_"))}
    for delta, after, before in (
        ("object_delta_close_to_release", "object_count_after_file_release", "object_count_after_file_close"),
        ("object_delta_batch_to_fresh_ack", "object_count_after_fresh_ack", "object_count_at_batch_publish"),
        ("object_delta_ack_preopen_to_fresh_ack", "object_count_after_fresh_ack", "object_count_at_ack_preopen"),
    ):
        need(counts[delta] == counts[after] - counts[before], "phase delta mismatch: " + delta)
    memory, barrier, permit = native["memory"], native["barrier"], native["start_permit"]
    fresh, observation = joint["barrier_receipt"], joint["editor"]["native_observation"]
    need(counts["object_count_at_batch_publish"] == counter(memory["editor"], "objects") and
         counts["resource_count_at_batch_publish"] == counter(memory["editor"], "resources"),
         "original batch counter mismatch")
    need(counts["object_count_after_fresh_ack"] == counter(fresh, "objects") == counter(observation, "objects") and
         counts["resource_count_after_fresh_ack"] == counter(fresh, "resources") == counter(observation, "resources"),
         "fresh ACK counter mismatch")
    need(life["batch_publish_mono_us"] == memory["monotonic_us"] == native["ended_mono_us"] ==
         barrier["issued_mono_us"] == fresh["issued_mono_us"], "publish clock binding")
    need(life["process_frame"] == fresh["process_frame"] == observation["process_frame"] and
         life["process_frame"] >= memory["process_frame"] and observation["source"] == "native_ack" and
         observation["native_mono_us"] == fresh["ack_observed_mono_us"], "fresh ACK frame/clock binding")
    native_sha = reader.artifacts[paths["native"]]["sha256"]
    need(native_sha == joint["native_batch_sha256"] == ack["native_batch_sha256"] ==
         fresh["native_batch_sha256"], "native batch hash binding")
    need(joint["command_batch_sha256"] == start["command_batch_sha256"] == permit["command_batch_sha256"],
         "joint command hash binding")
    for key in ("ready_sha256", "deadline_mono_us"):
        need(permit[key] == start[key], "start permit binding: " + key)
    need(permit["start_sha256"] == reader.artifacts[paths["start"]]["sha256"] and
         permit["start_size_bytes"] == reader.artifacts[paths["start"]]["size_bytes"] and
         permit["batch_index"] == index and permit["ready_file"] == paths["ready"].removeprefix("project/") and
         permit["start_file"] == paths["start"].removeprefix("project/"), "start permit receipt")
    for key in ("generation", "root_instance_id", "issued_mono_us"):
        need(permit[key] == ready[key], "ready permit binding: " + key)
    for key in ("generation", "root_instance_id", "deadline_mono_us", "issued_mono_us", "ack_file"):
        need(fresh[key] == barrier[key], "barrier fresh binding: " + key)
    need(fresh["batch_index"] == index and fresh["ack_sha256"] == reader.artifacts[paths["ack"]]["sha256"] and
         fresh["ack_size_bytes"] == reader.artifacts[paths["ack"]]["size_bytes"] and
         fresh["ack_file"] == paths["ack"].removeprefix("project/") and
         ack["deadline_mono_us"] == barrier["deadline_mono_us"], "fresh ACK receipt")
    need(ready["issued_mono_us"] <= permit["start_observed_mono_us"] < ready["deadline_mono_us"] and
         permit["start_observed_mono_us"] <= native["started_mono_us"] <= native["ended_mono_us"] <=
         fresh["ack_observed_mono_us"] < barrier["deadline_mono_us"], "native event order")
    need(native["pid"] == ready["pid"] == joint["processes"]["editor"]["pid"] and
         command["host_process"] == joint["processes"]["host"], "process identity binding")
    need(ready["baseline_sha256"] == permit["semantic_sha256"] == barrier["baseline_sha256"] ==
         fresh["semantic_sha256"], "semantic binding")
    need(native["mode"] == "full" and len(native["cycles"]) == 100 and len(native["raw_timings"]) == 100,
         "native prefix cycle count")
    need(native["warmup"] is (index < 5) and command["warmup"] is (index < 5), "warmup identity")
    need(joint["phase"] == memory["phase"] == "post_batch_quiescent", "quiescent phase")
    return {"index": index, "warmup": index < 5, **counts,
            "batch_publish_mono_us": life["batch_publish_mono_us"], "process_frame": life["process_frame"],
            "artifact_bindings": {key: {"file": path, **reader.artifacts[path]} for key, path in paths.items()}}


def analyze_reader(reader):
    provenance_binding = provenance(reader)
    rows = []
    for index in range(35):
        pair = (f"project/benchmark/out/lifecycle-{index:02}.json",
                f"project/benchmark/out/batch-{index:02}.json", f"joint-{index:02}.json",
                f"batch-capture-{index:02}.json")
        present = [reader.exists(name) for name in pair]
        if any(present):
            need(all(present), "missing pair at batch " + str(index))
            need(index == len(rows), "noncontiguous completed prefix")
            rows.append(batch(reader, index))
    need(rows, "no complete lifecycle pairs")
    pending = []
    for index in range(len(rows), 35):
        names = (f"project/benchmark/out/ready-{index:02}.json", f"project/benchmark/input/start-{index:02}.json",
                 f"command-{index:02}.json")
        present = [reader.exists(name) for name in names]
        if any(present):
            need(all(present), "incomplete ready/start/command prefix at batch " + str(index))
            need(index == len(rows), "unexpected later start prefix")
            start_binding(reader, index)
            pending.append({"index": index, "status": "started_without_completed_native_joint_lifecycle",
                            "artifacts": {name: reader.artifacts[name] for name in names}})
    terminal = {}
    for name in TERMINAL:
        if reader.exists(name):
            reader.read(name)
            terminal[name] = {"status": "present_not_terminal_validated", **reader.artifacts[name]}
        else:
            terminal[name] = {"status": "missing"}
    gaps = [name for name, row in terminal.items() if row["status"] == "missing"]
    result = {"schema_id": "hh-studio.gt06.s90-offline-lifecycle-analysis", "schema_version": "1.0.0",
              "run_id": RUN, "verification_status": "verified_partial_diagnostic_bindings" if len(rows) < 35 else
              "verified_diagnostic_bindings_terminal_unverified", "formal_acceptance": False,
              "eligible_for_dataset": False, "fullrun_pass": False, "terminal_verified": False,
              "complete_lifecycle_pair_count": len(rows), "warmup_pair_count": sum(r["warmup"] for r in rows),
              "measured_pair_count": sum(not r["warmup"] for r in rows), "required_batches_per_run": 35,
              "required_campaign_runs": 10, "required_campaign_batches": 350,
              "eligible_dataset_sample_count": 0, "provenance": provenance_binding,
              "lifecycle_rows": rows, "pending_prefix": pending, "terminal_inventory": terminal,
              "terminal_gaps": gaps, "supervisor_actual_exit": "not_certified_by_this_verifier",
              "interpretation_limit": "Phase counter differences describe this instrumented prefix only; no leak, root cause, repair, terminal exit, or benchmark acceptance conclusion.",
              "artifacts": dict(sorted(reader.artifacts.items()))}
    result["derived_payload_sha256"] = sha(encoded(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path, help="Existing gt06-s90-lifecycle-attribution-01 raw directory")
    args = parser.parse_args(argv)
    try:
        result = analyze_reader(RawReader(args.raw))
    except (InvalidEvidence, OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"verification_status": "invalid_evidence", "error": str(error),
                          "formal_acceptance": False, "eligible_for_dataset": False, "fullrun_pass": False}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
