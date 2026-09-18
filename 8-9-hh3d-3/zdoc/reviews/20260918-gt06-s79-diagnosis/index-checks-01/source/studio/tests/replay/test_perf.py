"""GT-06 metric arithmetic, evidence bindings and closed artifact regressions."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay.perf import (ARTIFACT_KIND, MAX_ARTIFACT_BYTES, MAX_DURATION_MS,
    MAX_FRAMES, MAX_RSS_SAMPLES, SCHEMA_ID, SCHEMA_PATH, SCHEMA_SHA256, SCHEMA_VERSION,
    PerfError, build_artifact, parse_artifact, summarize, validate_artifact)


def sample_payload(times=(10.0, 20.0, 30.0)):
    """Complete synthetic contract example. Never native acceptance evidence."""
    digest = "a" * 64
    runtime_start, host_start = 1_000_000, 5_000_000
    elapsed = 0
    frames, counters = [], []
    for index, frame_ms in enumerate(times):
        elapsed += int(round(frame_ms * 1000))
        now = runtime_start + elapsed
        frames.append({"seq": index, "engine_process_frame": 100 + index,
            "engine_draw_frame": 80 + index, "runtime_mono_us": now,
            "frame_ms": frame_ms, "sim_tick": 10 + index, "ui_tick": 100 + index,
            "phase": "PLAY", "state_hash": digest})
        counters.append({"sample_seq": index, "frame_seq": index, "runtime_mono_us": now,
            "scene_triangles": 1200, "render_primitives": 7200,
            "draw_calls": 9, "texture_bytes": 65536})

    def definition(provider, unit, scope, freshness):
        return {"availability": "available", "provider": provider, "unit": unit,
                "scope": scope, "freshness": freshness, "reason": None}

    return {
        "provenance": {"run_id": "gt06.sample.1", "command_id": "cmd.gt06.sample.1",
            "project_id": "fixture.gt06", "runtime_instance_id": "runtime.gt06.1",
            "seed": 42, "input_hz": 60, "source_closure_sha256": digest,
            "runtime_snapshot_sha256": digest, "toolchain_lock_sha256": digest,
            "trace_sha256": digest, "profile_sha256": digest, "collector_sha256": digest},
        "process": {"pid": 1234, "process_start": "windows:133000000000000000",
            "role": "play", "executable_sha256": digest, "host_job_id": "job.gt06.1",
            "window_status": "available", "window_id": "0", "native_window_handle": "0x1234",
            "window_unavailable_reason": None},
        "configuration": {"godot_version": "4.7.2.stable", "godot_build": "fixture-contract-only",
            "platform": "windows", "device_profile_id": "workstation.gt01",
            "renderer": "gl_compatibility", "rendering_driver": "opengl3",
            "display_server": "windows", "resolution": [640, 360], "vsync_mode": "enabled",
            "max_fps": 60, "physics_hz": 60, "time_scale": 1.0, "build_mode": "debug",
            "fixed_fps": False, "delta_smoothing": False},
        "clock": {"started_utc_ms": 1_800_000_000_000,
            "ended_utc_ms": 1_800_000_000_000 + math.ceil(elapsed / 1000),
            "runtime_clock": "Godot.Time.get_ticks_usec", "host_clock": "host.monotonic_ns_div_1000",
            "runtime_start_mono_us": runtime_start, "runtime_end_mono_us": runtime_start + elapsed,
            "host_start_mono_us": host_start, "host_end_mono_us": host_start + elapsed},
        "sampling": {"metric": "runtime_frame_boundary_interval", "hook": "frame_post_draw",
            "warmup_ms": 500, "max_frames": MAX_FRAMES, "max_rss_samples": MAX_RSS_SAMPLES,
            "max_duration_ms": MAX_DURATION_MS, "max_artifact_bytes": MAX_ARTIFACT_BYTES,
            "counter_interval_frames": 1, "rss_interval_ms": 100, "captures_in_window": False,
            "complete": True, "dropped_frames": 0, "dropped_godot_counters": 0,
            "dropped_rss_samples": 0},
        "counter_definitions": {
            "scene_triangles": definition("runtime_mesh_surface_readback", "triangles",
                "loaded_instanced_active_lod_topology", "readback_topology"),
            "render_primitives": definition("Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME",
                "vertices_or_indices", "last_rendered_frame_including_passes", "native_monitor"),
            "draw_calls": definition("Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME", "calls",
                "last_rendered_frame_including_passes", "native_monitor"),
            "texture_bytes": definition("Performance.RENDER_TEXTURE_MEM_USED", "bytes",
                "allocated_texture_memory", "native_monitor_may_lag"),
            "rss_bytes": definition("GetProcessMemoryInfo.WorkingSetSize", "bytes",
                "runtime_process_resident_memory", "host_observed")},
        "frames": frames, "godot_counters": counters,
        "rss_samples": [{"sample_seq": 0, "host_mono_us": host_start, "rss_bytes": 100_000_000}],
        "references": [{"reference_id": "process.result", "role": "process_result",
            "path": "raw/process-result.json", "sha256": digest, "bytes": 256}],
    }


class StatisticsTests(unittest.TestCase):
    def test_type7_and_one_percent_goldens(self):
        for count in (1, 99, 100, 101, 200):
            with self.subTest(count=count):
                result = summarize(range(1, count + 1))
                self.assertEqual(result["sample_count"], count)
                self.assertEqual(result["duration_ms"], count * (count + 1) / 2)
                for label, p in (("p50_frame_ms", .50), ("p95_frame_ms", .95), ("p99_frame_ms", .99)):
                    self.assertAlmostEqual(result[label], 1 + (count - 1) * p)
                worst_count = 1 if count <= 100 else 2
                worst_mean = count - (worst_count - 1) / 2
                self.assertEqual(result["one_percent_sample_count"], worst_count)
                self.assertEqual(result["one_percent_mean_frame_ms"], worst_mean)
                self.assertAlmostEqual(result["one_percent_low_fps"], 1000 / worst_mean)

    def test_outlier_low_is_not_percentile_reciprocal_or_mean_fps(self):
        result = summarize([10] * 100 + [110])
        self.assertEqual(result["p99_frame_ms"], 10)
        self.assertEqual(result["one_percent_mean_frame_ms"], 60)
        self.assertAlmostEqual(result["one_percent_low_fps"], 1000 / 60)
        self.assertNotEqual(result["one_percent_low_fps"], 1000 / result["p99_frame_ms"])

    def test_ties_and_input_order(self):
        self.assertEqual(summarize([7, 7, 7, 7]), summarize([7] * 4))
        self.assertEqual(summarize([1, 100, 2]), summarize([2, 1, 100]))

    def test_invalid_raw_time_and_bounded_iterable(self):
        for values in ([], [True], [False], [0], [-1], [float("nan")], [float("inf")],
                       [10**400], ["1"], [1e-320], [1e308, 1e308]):
            with self.subTest(values=str(values)[:70]), self.assertRaises(PerfError):
                summarize(values)
        consumed = 0
        def infinite():
            nonlocal consumed
            while True:
                consumed += 1
                yield 1
        with self.assertRaises(PerfError):
            summarize(infinite())
        self.assertEqual(consumed, MAX_FRAMES + 1)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.artifact = build_artifact(sample_payload())

    def rejected(self, mutate, code=None):
        value = copy.deepcopy(self.artifact)
        mutate(value)
        with self.assertRaises(PerfError) as failure:
            validate_artifact(value)
        if code:
            self.assertEqual(failure.exception.code, code)

    def test_factory_parser_and_expected_native_bindings(self):
        expected = {"provenance": {"source_closure_sha256": "a" * 64},
                    "process": {"pid": 1234, "process_start": "windows:133000000000000000"}}
        decoded = parse_artifact(json.dumps(self.artifact).encode(), expected=expected)
        self.assertEqual(decoded, self.artifact)
        decoded["process"]["pid"] = 999
        self.assertEqual(self.artifact["process"]["pid"], 1234)
        for expected in ({"process": {"pid": 999}}, {"process": {"process_start": "windows:999"}},
                         {"provenance": {"source_closure_sha256": "b" * 64}},
                         {"provenance": {"trace_sha256": "c" * 64}},
                         {"provenance": {"runtime_instance_id": "stale.instance"}}):
            with self.subTest(expected=expected), self.assertRaises(PerfError) as failure:
                validate_artifact(self.artifact, expected=expected)
            self.assertEqual(failure.exception.code, "EXPECTED_BINDING_MISMATCH")

    def test_factory_never_silently_replaces_claimed_summary(self):
        with self.assertRaises(PerfError) as failure:
            build_artifact(self.artifact)
        self.assertEqual(failure.exception.code, "FACTORY_SUMMARY_FORBIDDEN")
        value = sample_payload()
        value["schema_version"] = "2.0.0"
        with self.assertRaises(PerfError):
            build_artifact(value)

    def test_required_identity_and_low_fields(self):
        for key in ("schema_id", "schema_version", "artifact_kind"):
            self.rejected(lambda x, key=key: x.pop(key), "MISSING_FIELD")
        self.rejected(lambda x: x["summary"].pop("one_percent_low_fps"), "MISSING_FIELD")
        for key, wrong in (("schema_id", "other"), ("schema_version", "1.1.0"),
                           ("artifact_kind", "TIME_PROCESS")):
            self.rejected(lambda x, key=key, wrong=wrong: x.__setitem__(key, wrong), "INVALID_CONSTANT")

    def test_all_summary_fields_recomputed(self):
        for key, original in self.artifact["summary"].items():
            if type(original) in (int, float):
                self.rejected(lambda x, key=key, original=original: x["summary"].__setitem__(key, original + 1))
        self.rejected(lambda x: x["summary"].__setitem__("percentile_method", "nearest_rank"))

    def test_boolean_nonfinite_unknown_and_oversized_integer_rejections(self):
        for value in (True, False, float("nan"), float("inf"), -1.0, "20"):
            self.rejected(lambda x, value=value: x["frames"][1].__setitem__("frame_ms", value))
        for value in (True, 1.0, 10**400):
            self.rejected(lambda x, value=value: x["process"].__setitem__("pid", value))
        self.rejected(lambda x: x["godot_counters"][0].__setitem__("draw_calls", True))
        self.rejected(lambda x: x["sampling"].__setitem__("dropped_frames", False))
        self.rejected(lambda x: x["configuration"].__setitem__("hidden_override", True), "UNKNOWN_FIELD")
        self.rejected(lambda x: x["process"].__setitem__("host_job_id", "bad\ud800"), "INVALID_UNICODE")

    def test_raw_time_sequence_and_window_gaps(self):
        self.rejected(lambda x: x["frames"][1].__setitem__("seq", 2), "FRAME_SEQUENCE")
        self.rejected(lambda x: x["frames"][1].__setitem__("engine_process_frame", 103), "ENGINE_FRAME_GAP")
        self.rejected(lambda x: x["frames"][1].__setitem__("engine_draw_frame", 83), "DRAW_FRAME_GAP")
        self.rejected(lambda x: x["frames"][1].__setitem__("runtime_mono_us", 1_010_000), "FRAME_CLOCK")
        self.rejected(lambda x: x["frames"][1].__setitem__("frame_ms", 19), "DERIVED_VALUE_MISMATCH")
        self.rejected(lambda x: x["clock"].__setitem__("runtime_end_mono_us", 1_060_001), "FRAME_WINDOW_INCOMPLETE")
        self.rejected(lambda x: x["clock"].__setitem__("host_end_mono_us", 1), "CLOCK_RANGE")
        self.rejected(lambda x: x["clock"].__setitem__("runtime_clock", "UTC"), "INVALID_CONSTANT")

    def test_simulation_pause_and_ui_clock(self):
        payload = sample_payload()
        for frame in payload["frames"]:
            frame["phase"], frame["sim_tick"] = "PAUSED", 10
        validate_artifact(build_artifact(payload))
        payload["frames"][1]["sim_tick"] = 11
        with self.assertRaises(PerfError) as failure:
            build_artifact(payload)
        self.assertEqual(failure.exception.code, "PAUSE_SIM_TICK_CHANGED")
        self.rejected(lambda x: x["frames"][1].__setitem__("ui_tick", 100), "RUNTIME_CLOCK_ORDER")

    def test_counter_gaps_alignment_and_units(self):
        self.rejected(lambda x: x["godot_counters"].pop(), "COUNTER_FRAME_COVERAGE")
        self.rejected(lambda x: x["godot_counters"][1].__setitem__("frame_seq", 0), "COUNTER_FRAME_BINDING")
        self.rejected(lambda x: x["godot_counters"][1].__setitem__("sample_seq", 2), "COUNTER_FRAME_BINDING")
        self.rejected(lambda x: x["godot_counters"][1].__setitem__("runtime_mono_us", 1), "COUNTER_FRAME_BINDING")
        self.rejected(lambda x: x["counter_definitions"]["scene_triangles"].__setitem__(
            "provider", "Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME"), "INVALID_VARIANT")
        self.rejected(lambda x: x["counter_definitions"]["render_primitives"].__setitem__("unit", "triangles"), "INVALID_VARIANT")

    def test_exact_native_viewport_definitions_and_cross_variant_rejection(self):
        payload = sample_payload()
        definitions = payload["counter_definitions"]
        definitions["scene_triangles"].update(provider="Mesh.get_faces",
            scope="visible_in_tree_mesh_topology_excludes_ui_and_gpu_culling")
        definitions["draw_calls"].update(provider="RenderingServer.viewport_get_render_info",
            scope="bound_viewport_visible_plus_shadow")
        definitions["render_primitives"].update(provider="RenderingServer.viewport_get_render_info",
            scope="bound_viewport_visible", unit="points_lines_or_triangles")
        artifact = build_artifact(payload)
        validate_artifact(artifact)
        for name, key, wrong in (("draw_calls", "scope", "last_rendered_frame_including_passes"),
                                 ("draw_calls", "scope", "bound_viewport_visible"),
                                 ("render_primitives", "unit", "vertices_or_indices"),
                                 ("render_primitives", "scope", "bound_viewport_visible_plus_shadow"),
                                 ("scene_triangles", "scope", "loaded_instanced_active_lod_topology")):
            bad = copy.deepcopy(artifact)
            bad["counter_definitions"][name][key] = wrong
            with self.subTest(name=name, key=key), self.assertRaises(PerfError) as failure:
                validate_artifact(bad)
            self.assertEqual(failure.exception.code, "INVALID_VARIANT")

    def test_explicit_unavailable_counter_and_rss(self):
        payload = sample_payload()
        for name in ("texture_bytes", "rss_bytes"):
            payload["counter_definitions"][name].update(availability="unavailable", reason="UNSUPPORTED_BY_PROVIDER")
        for row in payload["godot_counters"]:
            row["texture_bytes"] = None
        payload["rss_samples"] = []
        artifact = build_artifact(payload)
        validate_artifact(artifact)
        artifact["godot_counters"][0]["texture_bytes"] = 0
        with self.assertRaises(PerfError) as failure:
            validate_artifact(artifact)
        self.assertEqual(failure.exception.code, "COUNTER_AVAILABILITY")
        self.rejected(lambda x: x["counter_definitions"]["rss_bytes"].__setitem__("reason", "missing"), "COUNTER_AVAILABILITY")
        self.rejected(lambda x: x.__setitem__("rss_samples", []), "RSS_AVAILABILITY")

    def test_rss_sequence_clock_and_provider(self):
        self.rejected(lambda x: x["rss_samples"][0].__setitem__("sample_seq", 1), "RSS_SEQUENCE")
        self.rejected(lambda x: x["rss_samples"][0].__setitem__("host_mono_us", 1_020_000), "RSS_CLOCK")
        self.rejected(lambda x: x["rss_samples"].append({"sample_seq": 1, "host_mono_us": 5_000_000,
                                                     "rss_bytes": 1234}), "RSS_CLOCK")
        self.rejected(lambda x: x["counter_definitions"]["rss_bytes"].__setitem__(
            "provider", "proc_pid_statm.resident_pages"), "RSS_PROVIDER_PLATFORM")

    def test_process_and_native_window_identity(self):
        self.rejected(lambda x: x["process"].__setitem__("process_start", "1234"), "STRING_PATTERN")
        self.rejected(lambda x: x["process"].__setitem__("native_window_handle", "0"), "WINDOW_BINDING")
        self.rejected(lambda x: x["process"].__setitem__("native_window_handle", "18446744073709551616"), "WINDOW_BINDING")
        self.rejected(lambda x: x["process"].__setitem__("window_unavailable_reason", "unknown"), "WINDOW_BINDING")
        self.rejected(lambda x: x["configuration"].__setitem__("display_server", "headless"), "WINDOW_BINDING")
        payload = sample_payload()
        payload["configuration"]["display_server"] = "headless"
        payload["sampling"]["hook"] = "process_frame"
        payload["process"].update(window_status="unavailable", window_id=None,
                                  native_window_handle=None, window_unavailable_reason="HEADLESS")
        for frame in payload["frames"]:
            frame["engine_draw_frame"] = 0
        validate_artifact(build_artifact(payload))

    def test_android_battery_optional_and_time_bound(self):
        self.assertNotIn("battery", self.artifact)
        payload = sample_payload()
        payload["configuration"]["platform"] = "android"
        payload["process"]["process_start"] = "linux:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa:123"
        payload["counter_definitions"]["rss_bytes"]["provider"] = "proc_pid_statm.resident_pages"
        payload["battery"] = {"provider": "android.test", "started_host_mono_us": 5_000_000,
            "ended_host_mono_us": 5_060_000, "start_percent": 85.5, "end_percent": 85.0,
            "charging_start": False, "charging_end": False}
        artifact = build_artifact(payload)
        validate_artifact(artifact)
        for key, wrong in (("end_percent", 101), ("start_percent", True), ("ended_host_mono_us", 5_060_001)):
            bad = copy.deepcopy(artifact)
            bad["battery"][key] = wrong
            with self.assertRaises(PerfError):
                validate_artifact(bad)
        self.rejected(lambda x: x.__setitem__("battery", payload["battery"]), "BATTERY_PLATFORM")

    def test_references_closed_bounded_and_canonical(self):
        for path in ("../x", "a/../x", "/x", "a//x", "a/./x", "C:/x", "a\\x", "NUL.txt", "a/end."):
            with self.subTest(path=path):
                self.rejected(lambda x, path=path: x["references"][0].__setitem__("path", path))
        self.rejected(lambda x: x["references"].append(copy.deepcopy(x["references"][0])), "DUPLICATE_REFERENCE")
        self.rejected(lambda x: x.__setitem__("references", x["references"] * 33), "ARRAY_SIZE")
        self.rejected(lambda x: x["references"][0].__setitem__("sha256", "a" * 63), "STRING_LENGTH")
        self.rejected(lambda x: x["references"][0].__setitem__("path", "a" * 513), "STRING_LENGTH")

    def test_resource_caps_and_complete_status(self):
        for key, wrong in (("max_frames", MAX_FRAMES + 1), ("max_rss_samples", MAX_RSS_SAMPLES + 1),
                           ("max_duration_ms", MAX_DURATION_MS + 1), ("max_artifact_bytes", MAX_ARTIFACT_BYTES + 1)):
            self.rejected(lambda x, key=key, wrong=wrong: x["sampling"].__setitem__(key, wrong), "NUMBER_RANGE")
        self.rejected(lambda x: x["sampling"].__setitem__("max_frames", 2), "PROFILE_FRAME_LIMIT")
        self.rejected(lambda x: x["sampling"].__setitem__("max_duration_ms", 1), "CLOCK_RANGE")
        self.rejected(lambda x: x["sampling"].__setitem__("max_artifact_bytes", 50), "ARTIFACT_BYTE_LIMIT")
        self.rejected(lambda x: x["sampling"].__setitem__("complete", False), "INVALID_CONSTANT")
        self.rejected(lambda x: x["sampling"].__setitem__("dropped_frames", 1), "INVALID_CONSTANT")
        self.rejected(lambda x: x.__setitem__("frames", [x["frames"][0]] * (MAX_FRAMES + 1)), "ARRAY_SIZE")
        self.rejected(lambda x: x.__setitem__("rss_samples", [x["rss_samples"][0]] * (MAX_RSS_SAMPLES + 1)), "ARRAY_SIZE")

    def test_parse_duplicate_utf8_unicode_nan_and_profile_raw_byte_cap(self):
        for raw in (b"{\"schema_id\":\"x\",\"schema_id\":\"y\"}", b"\xff", "{\"x\":NaN}",
                    "{\"x\":Infinity}", "{\"x\":-Infinity}", "{\"x\":{\"y\":1,\"y\":2}}",
                    "[", "\ud800", "[" * 2000 + "]" * 2000):
            with self.subTest(raw=repr(raw)[:60]), self.assertRaises(PerfError):
                parse_artifact(raw)
        value = copy.deepcopy(self.artifact)
        value["sampling"]["max_artifact_bytes"] = 10_000
        validate_artifact(value)
        with self.assertRaises(PerfError) as failure:
            parse_artifact(json.dumps(value) + " " * 10_000)
        self.assertEqual(failure.exception.code, "ARTIFACT_BYTE_LIMIT")
        with self.assertRaises(PerfError):
            parse_artifact(b" " * (MAX_ARTIFACT_BYTES + 1))

    def test_schema_identity_and_shared_limits_unchanged(self):
        from studio.host.core.limits import DEFAULT_LIMITS
        from studio.protocol.core import MAX_ARRAY_ITEMS
        schema = json.loads(SCHEMA_PATH.read_bytes())
        self.assertEqual(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), SCHEMA_SHA256)
        self.assertEqual(schema["properties"]["schema_id"]["const"], SCHEMA_ID)
        self.assertEqual(schema["properties"]["schema_version"]["const"], SCHEMA_VERSION)
        self.assertEqual(schema["properties"]["artifact_kind"]["const"], ARTIFACT_KIND)
        self.assertEqual(DEFAULT_LIMITS.max_array_items, 256)
        self.assertEqual(DEFAULT_LIMITS.max_result_bytes, 256 * 1024)
        self.assertEqual(MAX_ARRAY_ITEMS, 256)

    def test_large_local_series_does_not_gain_wire_authority(self):
        from studio.protocol.core import ValidationError, canonical_bytes
        artifact = build_artifact(sample_payload([10.0] * 300))
        parsed = parse_artifact(json.dumps(artifact))
        self.assertEqual(parsed["summary"]["sample_count"], 300)
        with self.assertRaises(ValidationError) as failure:
            canonical_bytes({"frames": artifact["frames"]})
        self.assertEqual(failure.exception.code, "ARRAY_ITEM_LIMIT")

    def test_future_unsupported_schema_semantics_fail_closed(self):
        from studio.host.replay.perf import _check_schema_subset
        schema = json.loads(SCHEMA_PATH.read_bytes())
        schema["properties"]["frames"]["uniqueItems"] = True
        with self.assertRaises(RuntimeError):
            _check_schema_subset(schema)
        schema = json.loads(SCHEMA_PATH.read_bytes())
        schema["properties"]["process"]["additionalProperties"] = True
        with self.assertRaises(RuntimeError):
            _check_schema_subset(schema)


if __name__ == "__main__":
    unittest.main()
