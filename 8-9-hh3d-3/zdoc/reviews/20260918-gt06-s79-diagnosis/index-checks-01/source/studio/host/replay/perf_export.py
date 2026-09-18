"""Postprocess frozen GT06 native evidence into the closed performance schema.

build_export(root, *, expected_capture_sha256, project_id, device_profile_id)
returns an export wrapper without writing. export_run has the same arguments
and exclusively creates root/perf-export-v1.json, preserving a GAP wrapper on
validation failure. It never launches an engine or rewrites captured evidence.
The two IDs are explicit caller routing labels, not native hardware discovery.
The mandatory expected capture digest is an independently supplied trust anchor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import perf

OUTPUT_NAME = "perf-export-v1.json"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_FILES = 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_COUNTER_TEXT = {
    "triangles": "loaded visible MeshInstance3D LOD topology; excludes UI and GPU culling",
    "draw_calls": "viewport visible plus shadow draw calls in this rendered frame",
    "render_primitives": "viewport visible render primitives; not converted to triangle count",
    "texture_bytes": "Godot Performance.RENDER_TEXTURE_MEM_USED; excludes host RSS",
}


class ExportError(ValueError):
    def __init__(self, code: str, path: str = "$") -> None:
        self.code, self.path = code, path
        super().__init__(f"{code}: {path}")


def need(value, code, path="$"):
    if not value:
        raise ExportError(code, path)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def closure(files):
    return sha("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode())


def _json(raw, path):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "DUPLICATE_KEY", path)
            result[key] = value
        return result

    def invalid(_):
        raise ExportError("NONFINITE_JSON", path)

    def walk(value, depth=0):
        need(depth <= 48, "JSON_DEPTH", path)
        if type(value) is float:
            need(math.isfinite(value), "NONFINITE_JSON", path)
        elif type(value) is str:
            need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "INVALID_UNICODE", path)
        elif type(value) is dict:
            for key, item in value.items():
                walk(key, depth + 1)
                walk(item, depth + 1)
        elif type(value) is list:
            need(len(value) <= 120_000, "JSON_ARRAY_CAP", path)
            for item in value:
                walk(item, depth + 1)
    try:
        value = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                           parse_constant=invalid)
        walk(value)
        return value
    except ExportError:
        raise
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ExportError("INVALID_JSON", path) from error


def _path(name):
    need(type(name) is str and 0 < len(name) <= 512 and "\\" not in name
         and ":" not in name and not name.startswith("/"), "RELATIVE_PATH")
    need(all(part not in ("", ".", "..") and not part.endswith((".", " "))
             for part in name.split("/")), "RELATIVE_PATH")
    return name


def _file(path):
    try:
        for parent in (path, *path.parents):
            info = parent.lstat()
            need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                 "REPARSE_PATH")
        before = path.stat()
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= MAX_FILE_BYTES,
             "FILE_POLICY")
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            need((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), "FILE_CHANGED")
            raw = stream.read(MAX_FILE_BYTES + 1)
            after_handle = os.fstat(stream.fileno())
        after = path.stat()
        signature = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_nlink)
        need(signature(before) == signature(opened) == signature(after_handle) == signature(after)
             and len(raw) == before.st_size, "FILE_CHANGED")
        return raw
    except ExportError:
        raise
    except OSError as error:
        raise ExportError("FILE_UNAVAILABLE") from error


class Evidence:
    def __init__(self, root):
        self.root = Path(root).absolute()
        self.files, self.bytes = {}, 0

    def read(self, name, expected=None):
        name = _path(name)
        raw = _file(self.root / name)
        digest = sha(raw)
        if expected is not None:
            need(type(expected) is str and _HASH.fullmatch(expected) and digest == expected,
                 "RAW_HASH_MISMATCH", name)
        if name in self.files:
            need(self.files[name] == digest, "READ_CHANGED", name)
        else:
            self.bytes += len(raw)
        self.files[name] = digest
        need(len(self.files) <= MAX_FILES and self.bytes <= MAX_TOTAL_BYTES, "EVIDENCE_CAP")
        return raw

    def json(self, name, expected=None):
        return _json(self.read(name, expected), name)

    def recheck(self):
        for name, digest in tuple(self.files.items()):
            self.read(name, digest)


def _source_map(value, code):
    need(type(value) is dict and 0 < len(value) <= 512, code)
    for name, digest in value.items():
        _path(name)
        need(type(digest) is str and _HASH.fullmatch(digest), code)
    return value


def _collector():
    names = ("host/replay/perf_export.py", "host/replay/perf.py", "contracts/perf-collector.schema.json")
    files = {name: sha(_file(STUDIO / name)) for name in names}
    need(files["contracts/perf-collector.schema.json"] == perf.SCHEMA_SHA256, "COLLECTOR_SCHEMA_CHANGED")
    return {"execution_role": "postprocess_only_not_native_runtime", "source_files": files,
            "closure_sha256": closure(files), "closure_domain": "sorted-path-NUL-sha256-LF-utf8",
            "schema_sha256": perf.SCHEMA_SHA256, "python_version": sys.version}


def _stage(evidence, phase, digest):
    prefix = phase + "-host/"
    capture = evidence.json(prefix + "capture.json", digest)
    names = {"process-start.json", "process-exit.json", "stdout.txt", "stderr.txt"}
    need(set(capture.get("artifacts", {})) == names, "STAGE_ARTIFACT_SET", phase)
    raw = {name: evidence.read(prefix + name, capture["artifacts"][name]) for name in names}
    started = _json(raw["process-start.json"], prefix + "process-start.json")
    exited = _json(raw["process-exit.json"], prefix + "process-exit.json")
    need(set(started) == {"pid"} and type(started["pid"]) is int and started["pid"] > 0,
         "STAGE_PID", phase)
    need(set(exited) == {"pid", "exit_code"} and type(exited["pid"]) is int
         and type(exited["exit_code"]) is int and exited == {"pid": started["pid"], "exit_code": 0}
         and capture.get("actual_process_exit") == exited, "STAGE_EXIT", phase)
    job = capture.get("job", {})
    need(capture.get("completed") is True and capture.get("natural_tree_exit") is True
         and type(capture.get("wrapper_exit_code")) is int and capture["wrapper_exit_code"] == 0
         and type(capture.get("active_before_cleanup")) is int and capture["active_before_cleanup"] == 0
         and job.get("closed") is True and job.get("zero_observed") is True
         and job.get("tainted") is False and job.get("handle_retained") is False
         and type(job.get("active_count")) is int and job["active_count"] == 0
         and job.get("failed_operations") == [], "STAGE_CLEANUP", phase)
    need(not raw["stderr.txt"].strip() and not re.search(rb"\b(?:WARNING|ERROR)\b|\bError:", raw["stdout.txt"]),
         "STAGE_LOG_ERROR", phase)
    invocation = evidence.json(prefix + "invocation.json")
    return capture, invocation, raw["stdout.txt"]


def _state(row):
    need(row.get("hash_domain") == "native-json-utf8" and type(row.get("state_json")) is str,
         "STATE_DOMAIN")
    raw = row["state_json"].encode("utf-8")
    need(sha(raw) == row.get("state_snapshot_sha256"), "STATE_HASH")
    state = _json(raw, "state_json")
    need(all(state.get(name) == row.get(name) for name in ("phase", "sim_tick", "ui_tick")), "STATE_FIELDS")
    return state


def _definition(provider, unit, scope, freshness):
    return {"availability": "available", "provider": provider, "unit": unit,
            "scope": scope, "freshness": freshness, "reason": None}


def _build_export(run_root, *, expected_capture_sha256, project_id, device_profile_id):
    """Verify frozen evidence, then export only its explicitly declared window."""
    need(type(expected_capture_sha256) is str and _HASH.fullmatch(expected_capture_sha256), "CAPTURE_ANCHOR")
    need(all(type(x) is str and _ID.fullmatch(x) for x in (project_id, device_profile_id)), "CALLER_CONTEXT")
    evidence = Evidence(run_root)
    collector = _collector()
    capture = evidence.json("capture.json", expected_capture_sha256)
    need(capture.get("schema") == "HH-GT06-NATIVE-CAPTURE-1" and capture.get("completed_native") is True
         and capture.get("formal_acceptance") is False and capture.get("public_ack") is False
         and capture.get("source_unchanged") is True,
         "NATIVE_CAPTURE_STATUS")
    binding = evidence.json("project/input/run.json")
    need(capture.get("binding") == binding and capture.get("run_id") == binding.get("run_id"), "RUN_BINDING")
    report = evidence.json("project/out/report.json", capture["report_sha256"])
    need(report.get("schema_id") == "hh-studio.play-observation" and report.get("schema_version") == "1.0.0"
         and report.get("completed") is True and report.get("binding") == binding
         and report.get("formal_acceptance") is False and report.get("public_ack") is False, "REPORT_BINDING")
    metrics = evidence.json("process-metrics.json", capture["process_metrics_sha256"])
    need(metrics.get("errors") == [] and metrics.get("identity") == capture.get("process"), "PROCESS_METRICS")
    native = report["native"]
    identity = metrics["identity"]
    need(native.get("pid") == identity["pid"] and native.get("process_role") == "play"
         and native.get("editor_hint") is False and native.get("main_thread") is True, "NATIVE_PROCESS")
    source = _source_map(evidence.json("source-files.json"), "SOURCE_MAP")
    invocation = evidence.json("invocation.json")
    need(invocation.get("source_files") == source and invocation.get("source_closure_sha256") == closure(source)
         and binding.get("source_closure_sha256") == closure(source)
         and invocation.get("run_id") == binding["run_id"], "SOURCE_CLOSURE")
    frozen_paths = {}
    for index, (name, digest) in enumerate(source.items()):
        frozen = "source/" + str(index) + Path(name).suffix
        evidence.read(frozen, digest)
        frozen_paths[name] = frozen
    need("toolchain.lock.json" in frozen_paths and "host/replay/profile.json" in frozen_paths, "FROZEN_PROFILE_MISSING")
    lock = evidence.json(frozen_paths["toolchain.lock.json"])
    profile = evidence.json(frozen_paths["host/replay/profile.json"])
    need(profile.get("schema") == "HH-GT06-PLAY-PROFILE-1"
         and profile.get("frame_hook") == "frame_post_draw"
         and profile.get("metric") == "runtime_frame_boundary_interval", "PROFILE_CONTRACT")
    snapshot = _source_map(evidence.json("runtime-snapshot.json"), "SNAPSHOT_MAP")
    need(binding.get("runtime_snapshot_sha256") == closure(snapshot), "SNAPSHOT_CLOSURE")
    for name, digest in snapshot.items():
        evidence.read("project/" + name, digest)
        source_name = ("godot-addon/" + name if name.startswith("observe/") else
                       "fixtures/play-observe/" + name)
        if source_name in source:
            need(source[source_name] == digest, "RUNTIME_SOURCE_COPY", name)
    actual = set()
    for directory, directories, files in os.walk(evidence.root / "project", followlinks=False):
        directories[:] = [name for name in directories if name not in (".godot", "out")]
        for name in directories:
            path = Path(directory) / name
            info = path.lstat()
            need(not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400, "REPARSE_PATH")
        for name in files:
            relative = (Path(directory) / name).relative_to(evidence.root / "project").as_posix()
            if relative != "input/run.json":
                actual.add(relative)
    need(actual == set(snapshot), "SNAPSHOT_FILE_SET")
    inputs = {"asset_manifest_sha256": "input/manifest.json", "config_sha256": "config/fixture_actor.gd",
              "glb_sha256": "input/fixture.glb", "producer_report_sha256": "input/producer-report.json",
              "trace_sha256": "input/trace.json", "run_sha256": "input/run.json"}
    need(set(report.get("inputs", {})) == set(inputs), "INPUT_SET")
    for label, name in inputs.items():
        need(report["inputs"][label] == sha(evidence.read("project/" + name)), "INPUT_HASH", name)
    need(binding["glb_sha256"] == snapshot["input/fixture.glb"]
         and binding["trace_sha256"] == snapshot["input/trace.json"], "ASSET_TRACE_BINDING")
    trace = evidence.json("project/input/trace.json")
    need(report["seed"] == trace["seed"] == invocation["seed"] and report["fps"] == trace["fps"] == 60,
         "TRACE_SEED_CLOCK")
    runtime_prefix = ".local/reviews/" + binding["run_id"] + "/project/"
    runtime_source = dict(source)
    runtime_source.update({runtime_prefix + name: digest for name, digest in snapshot.items()})
    runtime_source[runtime_prefix + "input/run.json"] = sha(evidence.read("project/input/run.json"))
    stdout = None
    for phase, expected_source in (("import", source), ("runtime", runtime_source)):
        stage, stage_invocation, stream = _stage(evidence, phase, capture[phase + "_capture_sha256"])
        need(stage_invocation.get("source_files") == expected_source
             and stage_invocation.get("binary_sha256") == lock["godot"]["gui_sha256"], "STAGE_SOURCE_BINARY", phase)
        argv = stage_invocation.get("argv")
        cwd = str(evidence.root / "project")
        arguments = ["--headless", "--editor", "--path", cwd, "--import"] if phase == "import" else ["--path", cwd]
        need(type(argv) is list and len(argv) == len(arguments) + 1 and argv[1:] == arguments
             and type(argv[0]) is str and Path(argv[0]).name == lock["godot"]["gui_executable"]
             and stage_invocation.get("cwd") == cwd and stage_invocation.get("formal_acceptance") is False,
             "STAGE_COMMAND", phase)
        if phase == "runtime":
            need(stage["actual_process_exit"]["pid"] == identity["pid"], "STAGE_RUNTIME_PID")
            stdout = stream
    markers = [_json(line.split(b" ", 1)[1], "complete_marker") for line in stdout.splitlines()
               if line.startswith(b"HH_GT06_COMPLETE ")]
    need(len(markers) == 1 and markers[0].get("report_sha256") == capture["report_sha256"]
         and markers[0].get("pid") == identity["pid"]
         and all(markers[0].get(k) == binding[k] for k in ("run_id", "command_id", "runtime_instance_id")), "COMPLETE_MARKER")
    rss = metrics.get("samples")
    need(type(rss) is list and rss and len(rss) <= profile["max_rss_samples"], "RSS_ROWS")
    need(str(native["native_window_handle"]) in {h for row in rss for h in row["visible_window_handles"]}, "NATIVE_WINDOW_OBSERVATION")
    captures = report.get("captures")
    need(type(captures) is dict and set(captures) == {item["label"] for item in trace["captures"]}
         and len(captures) <= profile["max_capture_requests"], "CAPTURE_SET")
    for label, shot in captures.items():
        need(re.fullmatch(r"[a-z][a-z0-9_]{0,63}", label) and shot.get("label") == label, "CAPTURE_LABEL")
        need(all(shot.get(k) == value for k, value in binding.items()), "SCREENSHOT_BINDING", label)
        need(shot.get("pid") == identity["pid"] and str(shot.get("native_window_handle")) == str(native["native_window_handle"])
             and shot.get("window_id") == native["window_id"], "SCREENSHOT_WINDOW", label)
        need(shot["monotonic_us"] > shot["requested_monotonic_us"]
             and shot["process_frame"] > shot["minimum_process_frame"]
             and shot["rendered_frame"] > shot["minimum_rendered_frame"]
             and shot["observed_tick"] >= shot["requested_tick"], "STALE_SCREENSHOT", label)
        state = _state(shot)
        need(state.get("camera") == shot.get("camera"), "SCREENSHOT_CAMERA", label)
        png = evidence.read("project/out/" + label + ".png", shot["sha256"])
        need(len(png) == shot["size_bytes"] and len(png) >= 24 and png[:8] == b"\x89PNG\r\n\x1a\n"
             and struct.unpack(">II", png[16:24]) == (shot["width"], shot["height"]), "SCREENSHOT_PNG", label)
    need(report.get("counter_definitions") == _COUNTER_TEXT, "COUNTER_DEFINITIONS")
    config = native.get("configuration", {})
    for field in ("rendering_method", "rendering_driver", "delta_smoothing"):
        need(config.get(field + "_supported") is True and config.get(field) is not None,
             "CONFIG_API_UNSUPPORTED", field)
    need(config.get("vsync_mode") in (0, 1, 2, 3) and type(config.get("vsync_mode")) is int, "VSYNC_MODE")
    need(native["engine"]["hash"] == lock["godot"]["source_commit"]
         and native["engine"]["string"].startswith(lock["godot"]["version"])
         and native["physics_hz"] == config["physics_hz"] == profile["physics_hz"] == 60,
         "ENGINE_CONFIGURATION")
    rows = report.get("native_frames")
    need(type(rows) is list and 0 < len(rows) <= profile["max_frames"], "NATIVE_FRAME_ROWS")
    previous = report["frame_start_monotonic_us"]
    previous_row = None
    for row in rows:
        need(type(row.get("frame_time_us")) is int and row["frame_time_us"] > 0
             and type(row.get("monotonic_us")) is int
             and row["frame_time_us"] == row["monotonic_us"] - previous
             and row.get("frame_hook") == "frame_post_draw", "RAW_FRAME_CLOCK")
        need(all(type(row.get(k)) is int and row[k] >= 0 for k in ("process_frame", "rendered_frame"))
             and (previous_row is None or all(row[k] == previous_row[k] + 1
                                              for k in ("process_frame", "rendered_frame"))), "RAW_FRAME_SEQUENCE")
        _state(row)
        previous = row["monotonic_us"]
        previous_row = row
    need(previous == report["frame_end_monotonic_us"], "RAW_FRAME_END")
    start_index = report.get("perf_measurement_start_frame_index")
    anchor_us = report.get("perf_measurement_start_monotonic_us")
    need(type(start_index) is int and 0 < start_index < len(rows) and type(anchor_us) is int,
         "VIEWPORT_COUNTER_READINESS_UNPROVEN")
    anchor = rows[start_index - 1]
    need(anchor["monotonic_us"] == anchor_us and anchor["rendered_frame"] == 2
         and anchor.get("counter_readiness") == {"qualified": True, "reason": "qualified"}
         and anchor.get("raw_counter_readback") is None
         and anchor.get("measurement_eligible") is False, "READINESS_ANCHOR")
    need(all(row.get("measurement_eligible") is False for row in rows[:start_index]), "STARTUP_WINDOW_DECLARATION")
    for row in rows[:start_index - 1]:
        need(row.get("counter_readiness") == {"qualified": False, "reason": "startup_not_qualified"}
             and row["rendered_frame"] < 2
             and set(row["counters"]) == {"triangles", "draw_calls", "render_primitives", "texture_bytes"}
             and all(value is None for value in row["counters"].values())
             and type(row.get("raw_counter_readback")) is dict, "STARTUP_COUNTER_QUALIFICATION")
    trace_start = report.get("trace_start", {})
    need(trace_start.get("monotonic_us") == anchor_us and trace_start.get("process_frame") == anchor["process_frame"]
         and trace_start.get("rendered_frame") == anchor["rendered_frame"] and trace_start.get("rendered") is True
         and type(trace_start.get("ready_frame_count")) is int and trace_start["ready_frame_count"] >= 3,
         "TRACE_START_ANCHOR")
    measured = rows[start_index:]
    by_frame = {(row["process_frame"], row["rendered_frame"], row["monotonic_us"]): row for row in measured}
    for label, shot in captures.items():
        requested_camera = shot.get("requested_camera_json")
        need(shot.get("requested_phase") == shot["phase"], "SCREENSHOT_PHASE_FENCE", label)
        need(type(requested_camera) is str and sha(requested_camera.encode("utf-8")) == shot.get("requested_camera_sha256")
             and _json(requested_camera.encode("utf-8"), "requested_camera_json") == shot["camera"],
             "SCREENSHOT_CAMERA_FENCE", label)
        observed = by_frame.get((shot["process_frame"], shot["rendered_frame"], shot["monotonic_us"]))
        need(observed is not None and observed["state_snapshot_sha256"] == shot["state_snapshot_sha256"]
             and observed["counters"] == shot["counters"], "CAPTURE_FRAME_BINDING", label)
    frames, counters = [], []
    for index, row in enumerate(measured):
        need(row.get("counter_readiness") == {"qualified": True, "reason": "qualified"}
             and row.get("raw_counter_readback") is None
             and row.get("measurement_eligible") is True and row["rendered_frame"] > anchor["rendered_frame"],
             "MEASURED_COUNTER_UNAVAILABLE")
        values = row.get("counters", {})
        need(set(values) == {"triangles", "draw_calls", "render_primitives", "texture_bytes"}
             and all(type(x) is int and x >= 0 for x in values.values()), "MEASURED_COUNTER_VALUES")
        frames.append({"seq": index, "engine_process_frame": row["process_frame"],
            "engine_draw_frame": row["rendered_frame"], "runtime_mono_us": row["monotonic_us"],
            "frame_ms": row["frame_time_us"] / 1000.0, "sim_tick": row["sim_tick"],
            "ui_tick": row["ui_tick"], "phase": row["phase"], "state_hash": row["state_snapshot_sha256"]})
        counters.append({"sample_seq": index, "frame_seq": index, "runtime_mono_us": row["monotonic_us"],
            "scene_triangles": values["triangles"], "draw_calls": values["draw_calls"],
            "render_primitives": values["render_primitives"], "texture_bytes": values["texture_bytes"]})
    refs = []
    for role, name in (("source_manifest", "source-files.json"), ("runtime_manifest", "runtime-snapshot.json"),
                       ("toolchain_lock", frozen_paths["toolchain.lock.json"]), ("profile", frozen_paths["host/replay/profile.json"]),
                       ("trace", "project/input/trace.json"), ("readback", "project/out/report.json"),
                       ("process_result", "runtime-host/capture.json"), ("process_result", "process-metrics.json")):
        raw = evidence.read(name)
        refs.append({"reference_id": "native." + str(len(refs)), "role": role, "path": name, "sha256": sha(raw), "bytes": len(raw)})
    for label in captures:
        name = "project/out/" + label + ".png"
        raw = evidence.read(name)
        refs.append({"reference_id": "capture." + label, "role": "capture", "path": name, "sha256": sha(raw), "bytes": len(raw)})
    payload = {"provenance": {**{k: binding[k] for k in ("run_id", "command_id", "runtime_instance_id",
                "source_closure_sha256", "runtime_snapshot_sha256", "trace_sha256")},
            "project_id": project_id, "seed": report["seed"], "input_hz": 60,
            "toolchain_lock_sha256": source["toolchain.lock.json"], "profile_sha256": source["host/replay/profile.json"],
            "collector_sha256": collector["closure_sha256"]},
        "process": {**identity, "role": "play", "executable_sha256": lock["godot"]["gui_sha256"],
            "host_job_id": binding["run_id"] + ".runtime-host", "window_status": "available",
            "window_id": str(native["window_id"]), "native_window_handle": str(native["native_window_handle"]),
            "window_unavailable_reason": None},
        "configuration": {"godot_version": native["engine"]["string"], "godot_build": native["engine"]["hash"],
            "platform": "windows", "device_profile_id": device_profile_id, "renderer": config["rendering_method"],
            "rendering_driver": config["rendering_driver"], "display_server": native["display_server"],
            "resolution": config["viewport_resolution"], "vsync_mode": ("disabled", "enabled", "adaptive", "mailbox")[config["vsync_mode"]],
            "max_fps": config["max_fps"], "physics_hz": config["physics_hz"], "time_scale": config["time_scale"],
            "build_mode": "debug" if config["debug_build"] is True else "release",
            "fixed_fps": config["fixed_fps_flag"], "delta_smoothing": config["delta_smoothing"]},
        "clock": {"started_utc_ms": metrics["started_utc_ms"], "ended_utc_ms": metrics["ended_utc_ms"],
            "runtime_clock": "Godot.Time.get_ticks_usec", "host_clock": "host.monotonic_ns_div_1000",
            "runtime_start_mono_us": anchor_us, "runtime_end_mono_us": report["frame_end_monotonic_us"],
            "host_start_mono_us": metrics["host_start_mono_us"], "host_end_mono_us": metrics["host_end_mono_us"]},
        "sampling": {**{k: profile[k] for k in ("metric", "warmup_ms", "max_frames", "max_rss_samples",
            "max_duration_ms", "max_artifact_bytes", "rss_interval_ms", "captures_in_window")},
            "hook": "frame_post_draw", "counter_interval_frames": 1, "complete": True,
            "dropped_frames": 0, "dropped_godot_counters": 0, "dropped_rss_samples": 0},
        "counter_definitions": {
            "scene_triangles": _definition("Mesh.get_faces", "triangles", "visible_in_tree_mesh_topology_excludes_ui_and_gpu_culling", "readback_topology"),
            "draw_calls": _definition("RenderingServer.viewport_get_render_info", "calls", "bound_viewport_visible_plus_shadow", "native_monitor"),
            "render_primitives": _definition("RenderingServer.viewport_get_render_info", "points_lines_or_triangles", "bound_viewport_visible", "native_monitor"),
            "texture_bytes": _definition("Performance.RENDER_TEXTURE_MEM_USED", "bytes", "allocated_texture_memory", "native_monitor_may_lag"),
            "rss_bytes": _definition("GetProcessMemoryInfo.WorkingSetSize", "bytes", "runtime_process_resident_memory", "host_observed")},
        "frames": frames, "godot_counters": counters,
        "rss_samples": [{"sample_seq": i, "host_mono_us": row["host_mono_us"], "rss_bytes": row["rss_bytes"]} for i, row in enumerate(rss)],
        "references": refs}
    need(type(config.get("debug_build")) is bool and native["display_server"].lower() == "windows", "NATIVE_PLATFORM_BUILD")
    artifact = perf.build_artifact(payload)
    evidence.recheck()
    need(_collector() == collector, "COLLECTOR_CHANGED")
    return {"schema": "HH-GT06-PERF-EXPORT-1", "status": "EXPORTED_DIAGNOSTIC", "formal_acceptance": False,
        "native_capture_sha256": expected_capture_sha256, "postprocess_collector": collector,
        "caller_context": {"project_id": project_id, "device_profile_id": device_profile_id,
            "origin": "explicit caller routing labels; not native hardware discovery"},
        "measurement_window": {"start_frame_index": start_index, "excluded_startup_rows": start_index,
            "raw_frame_count": len(rows), "measured_frame_count": len(measured),
            "original_start_mono_us": report["frame_start_monotonic_us"], "measurement_start_mono_us": anchor_us,
            "end_mono_us": report["frame_end_monotonic_us"], "whole_process_sampled": False,
            "rss_window": "full host observation window; not per-frame synchronized",
            "host_clock_provider": "time.perf_counter_ns divided by 1000; monotonic",
            "host_job_id_origin": "derived label for verified runtime-host stage, not an OS Job Object name"},
        "performance_claim": profile["performance_claim"], "raw_files": dict(sorted(evidence.files.items())),
        "perf_artifact": artifact}


def build_export(run_root, *, expected_capture_sha256, project_id, device_profile_id):
    """Read-only exporter; malformed or unsupported observations fail closed."""
    try:
        return _build_export(run_root, expected_capture_sha256=expected_capture_sha256,
                             project_id=project_id, device_profile_id=device_profile_id)
    except (ExportError, perf.PerfError):
        raise
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise ExportError("EVIDENCE_SHAPE") from error


def export_run(run_root, *, expected_capture_sha256, project_id, device_profile_id):
    """Exclusively create a diagnostic export or an explicit no-artifact GAP."""
    root = Path(run_root).absolute()
    need(root.is_dir(), "RUN_ROOT")
    try:
        result = build_export(root, expected_capture_sha256=expected_capture_sha256,
                              project_id=project_id, device_profile_id=device_profile_id)
    except (ExportError, perf.PerfError) as error:
        result = {"schema": "HH-GT06-PERF-EXPORT-1", "status": "GAP", "formal_acceptance": False,
            "native_capture_sha256": expected_capture_sha256, "postprocess_collector": _collector(),
            "gap": {"code": error.code, "path": error.path}, "perf_artifact": None}
    raw = encoded(result)
    need(len(raw) <= MAX_FILE_BYTES, "EXPORT_BYTE_CAP")
    for parent in (root, *root.parents):
        need(not parent.is_symlink() and not getattr(parent.lstat(), "st_file_attributes", 0) & 0x400, "REPARSE_PATH")
    with (root / OUTPUT_NAME).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(_file(root / OUTPUT_NAME) == raw, "EXPORT_READBACK")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--expected-capture-sha256", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--device-profile-id", required=True)
    args = parser.parse_args()
    result = export_run(args.run_root, expected_capture_sha256=args.expected_capture_sha256,
                        project_id=args.project_id, device_profile_id=args.device_profile_id)
    print(json.dumps({"status": result["status"], "gap": result.get("gap"), "output": str(args.run_root / OUTPUT_NAME)}))
    raise SystemExit(0 if result["status"] == "EXPORTED_DIAGNOSTIC" else 2)
