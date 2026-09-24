"""Verify sealed S232 diagnostic evidence without importing runtime code."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RAW = ROOT / "8-9-hh3d-3/studio/.local/reviews/gt06-s232-counter-probe-syntax-02"
ARCHIVE = ROOT / "8-9-hh3d-3/studio/.local/archives/gt06-s232-counter-probe-syntax-02-s233-terminal.zip"
RUN_ID = "gt06-s232-counter-probe-syntax-02"
MANIFEST_SHA256 = "b0eaf7b0b0e3bea91a7e03bc0be1dfac23d479d73b900e97cef6e09f4c79f6c8"
ARCHIVE_SHA256 = "5fb7abdbd037fb30f4e32aa0f9f15aaabc41d60e3bbb58d8a2ad905b92385022"
DECISION = "DIAGNOSTIC_TERMINAL_ONLY; POST_ACK_NOT_EXERCISED; NO_REPAIRED_BOUNDARY_PROVEN; NO_FORMAL_RETRY_AUTHORIZATION; FORMAL_GATE_UNCHANGED"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    value = {}
    for name, item in pairs:
        need(name not in value, "duplicate JSON key: " + name)
        value[name] = item
    return value


def document(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def relative(name):
    need(type(name) is str and name and "\\" not in name and ":" not in name, "invalid relative path")
    path = PurePosixPath(name)
    need(not path.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/")),
         "unsafe relative path: " + name)
    return path


def regular(path):
    for part in (path, *path.parents):
        info = part.lstat()
        need(not part.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400,
             "reparse path: " + str(part))
    need(path.is_file(), "not a file: " + str(path))
    return path.read_bytes()


def authority(value):
    need(type(value.get("authority")) is int and value["authority"] == 0
         and value.get("formal_acceptance") is False, "diagnostic authority")


def main():
    package = document(regular(HERE / "package-manifest.json"))
    authority(package)
    need(package["schema_id"] == "hh-studio.review-package-manifest"
         and package["schema_version"] == "1.0.0"
         and package["package_id"] == "gt06-s232-counter-probe-diagnostic", "package identity")
    packet_names = {"README.md", "analysis.json", "verify.py"}
    rows = package["files"]
    need(len(rows) == len(packet_names) and {row["path"] for row in rows} == packet_names,
         "packet membership")
    need({path.name for path in HERE.iterdir()} == packet_names | {"package-manifest.json"},
         "unexpected packet member")
    for row in rows:
        raw = regular(HERE / relative(row["path"]))
        need(type(row["size_bytes"]) is int and len(raw) == row["size_bytes"]
             and digest(raw) == row["sha256"], "packet hash: " + row["path"])
    analysis = document(regular(HERE / "analysis.json"))
    authority(analysis)
    need(analysis["run_id"] == RUN_ID and analysis["decision"] == DECISION, "diagnostic run or decision")

    manifest_raw = regular(RAW / "raw-manifest.json")
    need(digest(manifest_raw) == MANIFEST_SHA256 == analysis["raw_manifest_sha256"], "sealed manifest hash")
    archive_raw = regular(ARCHIVE)
    need(digest(archive_raw) == ARCHIVE_SHA256 == analysis["archive_sha256"], "sealed archive hash")
    manifest = document(manifest_raw)
    authority(manifest)
    need(manifest["run_id"] == RUN_ID, "manifest run")
    payload = {}
    for row in manifest["files"]:
        name = row["path"]
        relative(name)
        need(name.startswith("raw/") and name not in payload, "manifest membership")
        raw = regular(RAW / relative(name.removeprefix("raw/")))
        need(type(row["bytes"]) is int and len(raw) == row["bytes"]
             and digest(raw) == row["sha256"], "raw hash: " + name)
        payload[name] = raw
    raw_names = {"raw/" + path.relative_to(RAW).as_posix() for path in RAW.rglob("*") if path.is_file()}
    need(raw_names == set(payload) | {"raw/raw-manifest.json"}, "raw exact membership")
    with zipfile.ZipFile(ARCHIVE) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)) and set(names) == set(payload) | {"raw-manifest.json"},
             "archive exact membership")
        need(archive.read("raw-manifest.json") == manifest_raw, "archive manifest bytes")
        for name, raw in payload.items():
            need(archive.read(name) == raw, "archive payload bytes: " + name)
    need(type(analysis["verified_files"]) is int and len(payload) == analysis["verified_files"]
         and type(analysis["archive_members"]) is int and len(names) == analysis["archive_members"],
         "derived payload counts")

    def read(name):
        return payload["raw/" + name]

    def data(name):
        return document(read(name))

    sources = data("source-files.json")
    need(type(sources) is dict and sources, "source map")
    expected_sources = set()
    for name, expected in sources.items():
        relative(name)
        need(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected), "source digest")
        member = "raw/source/studio/" + name
        expected_sources.add(member)
        need(member in payload and digest(payload[member]) == expected, "source bytes: " + name)
    need({name for name in payload if name.startswith("raw/source/")} == expected_sources,
         "source exact membership")
    closure = digest("".join(name + "\0" + sources[name] + "\n" for name in sorted(sources)).encode())
    need(type(analysis["source_files"]) is int and len(sources) == analysis["source_files"], "source count")
    need(closure == analysis["source_closure_sha256"] == package["source_closure_sha256"], "source closure")
    invocation, capture = data("invocation.json"), data("capture.json")
    binding = data("project/benchmark/input.json")
    index, batch = data("project/benchmark/out/index.json"), data("project/benchmark/out/batch-00.json")
    need(invocation["source_files"] == sources and invocation["source_closure_sha256"] == closure,
         "invocation sources")
    need(binding == invocation["binding"] == capture["binding"] == index["input"]
         and binding["source_closure_sha256"] == closure and binding["run_id"] == RUN_ID, "runtime binding")
    need(binding["mode"] == "diagnostic" and binding["batch_barrier"] == "diagnostic_none"
         and binding["batch_start"] == "diagnostic_immediate", "diagnostic mode")
    need(digest(read("benchmark-profile.json")) == analysis["profile_sha256"]
         == invocation["benchmark_profile_sha256"] == capture["profile_sha256"] == binding["profile_sha256"],
         "profile binding")
    need(analysis["binary_sha256"] == invocation["binary_sha256"] == capture["binary_sha256"]
         == data("source/studio/toolchain.lock.json")["godot"]["gui_sha256"], "recorded binary binding")
    for name, field in (("project/benchmark/input.json", "input_sha256"),
                        ("project/benchmark/out/index.json", "index_sha256"),
                        ("project/benchmark/out/batch-00.json", "batch_sha256"),
                        ("process-metrics.json", "process_metrics_sha256")):
        need(digest(read(name)) == capture[field], "capture artifact: " + name)

    exits = {}
    for role in ("editor", "import"):
        prefix = role + "-host/"
        stage = data(prefix + "capture.json")
        start, end = data(prefix + "process-start.json"), data(prefix + "process-exit.json")
        need(set(start) == {"pid"} and type(start["pid"]) is int and start["pid"] > 0
             and set(end) == {"pid", "exit_code"} and type(end["pid"]) is int
             and type(end["exit_code"]) is int and end["pid"] == start["pid"], "target exit identity: " + role)
        need(end == stage["actual_process_exit"] == capture["actual_exits"][role]
             and end["exit_code"] == 0 and type(analysis[role + "_actual_exit"]) is int
             and analysis[role + "_actual_exit"] == end["exit_code"], "actual exit: " + role)
        need(type(stage["wrapper_exit_code"]) is int and stage["wrapper_exit_code"] == 0
             and stage["completed"] is True and stage["natural_tree_exit"] is True
             and stage["active_before_cleanup"] == 0 and stage["formal_acceptance"] is False,
             "stage completion: " + role)
        need(digest(read(prefix + "capture.json")) == capture["stage_captures"][role], "stage hash: " + role)
        need(set(stage["artifacts"]) == {"process-start.json", "process-exit.json", "stdout.txt", "stderr.txt"},
             "stage artifacts: " + role)
        for name, expected in stage["artifacts"].items():
            need(digest(read(prefix + name)) == expected, "stage artifact hash: " + role + "/" + name)
        job = stage["job"]
        need(job == capture["jobs"][role] and all(job[name] is True for name in ("configured", "assigned", "closed", "zero_observed"))
             and type(job["active_count"]) is int and job["active_count"] == 0
             and all(job[name] is False for name in ("handle_retained", "tainted", "create_uncertain", "close_uncertain"))
             and job["failed_operations"] == [] and job["native_error"] is None, "Job cleanup: " + role)
        need(analysis[role + "_job_zero_closed"] is True
             and analysis[role + "_job_handle_released"] is True, "derived Job claims: " + role)
        exits[role] = end

    need(capture["run_id"] == RUN_ID and capture["completed_diagnostic"] is True
         and capture["full_benchmark"] is False and capture["formal_acceptance"] is False
         and capture["host_integrated"] is False and capture["public_ack"] is False
         and analysis["completed_diagnostic"] is True and analysis["host_integrated"] is False,
         "diagnostic completion scope")
    need(index["pid"] == batch["pid"] == capture["process"]["pid"] == exits["editor"]["pid"]
         and index["completed"] is True and index["benchmark_complete"] is False
         and index["formal_acceptance"] is False and index["host_integrated"] is False
         and index["batches_completed"] == index["cycles_per_batch"] == 1
         and len(index["batches"]) == len(batch["cycles"]) == 1
         and batch["run_id"] == RUN_ID and batch["mode"] == "diagnostic"
         and index["host_barriers"] == index["start_permits"] == []
         and batch["barrier"] == {"mode": "diagnostic_none", "required": False}
         and batch["start_permit"] is None, "one-cycle diagnostic without host ACK")
    need({name for name in payload if name.startswith("raw/project/benchmark/out/")}
         == {"raw/project/benchmark/out/index.json", "raw/project/benchmark/out/batch-00.json"}
         and b"HH_GT06_BENCHMARK_ACK " not in read("editor-host/stdout.txt")
         and analysis["post_ack_probe_exercised"] is False, "post-ACK probe not exercised")
    print(json.dumps({"run_id": RUN_ID, "verified_files": len(payload), "archive_members": len(names),
        "verified_source_files": len(sources), "source_closure_sha256": closure,
        "package_manifest_sha256": digest(regular(HERE / "package-manifest.json")),
        "raw_manifest_sha256": digest(manifest_raw), "archive_sha256": digest(archive_raw),
        "actual_exits": exits, "post_ack_probe_exercised": False,
        "formal_retry_authorized": False, "formal_acceptance": False, "authority": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
