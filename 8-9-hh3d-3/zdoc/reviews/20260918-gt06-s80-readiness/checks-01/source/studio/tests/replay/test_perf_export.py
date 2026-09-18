"""Synthetic evidence-graph tests; no fixtures here claim a native engine run."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import perf, perf_export as export


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def closure(files):
    return digest("".join(name + "\0" + files[name] + "\n" for name in sorted(files)).encode())


class SyntheticRun:
    def __init__(self, base):
        self.root = base / "gt06-synthetic"
        self.root.mkdir()
        self.identity = {"pid": 1234, "process_start": "windows:133000000000000000"}
        self.profile = {"schema": "HH-GT06-PLAY-PROFILE-1", "profile_id": "synthetic.profile",
            "physics_hz": 60, "max_trace_frames": 600, "max_capture_requests": 16,
            "max_frames": 1200, "max_rss_samples": 1000, "max_duration_ms": 20000,
            "max_artifact_bytes": 8388608, "rss_interval_ms": 25, "warmup_ms": 0,
            "frame_hook": "frame_post_draw", "captures_in_window": True,
            "metric": "runtime_frame_boundary_interval", "performance_claim": "synthetic contract fixture only"}
        self.lock = {"godot": {"gui_sha256": "b" * 64, "source_commit": "c" * 40,
                               "version": "4.7.2-stable", "gui_executable": "Godot_v4.7.2-stable_win64.exe"}}
        originals = {"toolchain.lock.json": raw(self.lock), "host/replay/profile.json": raw(self.profile),
                     "fixtures/play-observe/scripts/main.gd": b"# synthetic source, never executed\n"}
        self.source = {name: digest(data) for name, data in sorted(originals.items())}
        self.write("source-files.json", self.source)
        for index, name in enumerate(self.source):
            self.write("source/" + str(index) + Path(name).suffix, originals[name])
        inputs = {"config/fixture_actor.gd": b"# synthetic config\n", "input/fixture.glb": b"synthetic-glb",
            "input/manifest.json": b"{}\n", "input/producer-report.json": b"{}\n",
            "input/trace.json": raw({"fps": 60, "seed": 17, "captures": [{"label": "menu", "tick": 1}]}),
            "scripts/main.gd": originals["fixtures/play-observe/scripts/main.gd"]}
        self.snapshot = {name: digest(data) for name, data in sorted(inputs.items())}
        for name, data in inputs.items():
            self.write("project/" + name, data)
        self.write("runtime-snapshot.json", self.snapshot)
        self.binding = {"run_id": self.root.name, "command_id": self.root.name + ".play",
            "runtime_instance_id": self.root.name + ".runtime", "source_closure_sha256": closure(self.source),
            "runtime_snapshot_sha256": closure(self.snapshot), "trace_sha256": self.snapshot["input/trace.json"],
            "glb_sha256": self.snapshot["input/fixture.glb"], "generation": 1}
        self.write("project/input/run.json", self.binding)
        self.write("invocation.json", {"source_files": self.source, "source_closure_sha256": closure(self.source),
                                      "run_id": self.root.name, "seed": 17})
        self.metrics = {"identity": self.identity, "errors": [], "started_utc_ms": 1_800_000_000_000,
            "ended_utc_ms": 1_800_000_000_100, "host_start_mono_us": 500_000, "host_end_mono_us": 600_000,
            "samples": [{"host_mono_us": 500_000, "rss_bytes": 100_000, "visible_window_handles": ["555"]},
                        {"host_mono_us": 540_000, "rss_bytes": 110_000, "visible_window_handles": ["555"]}]}
        self.write("process-metrics.json", self.metrics)
        self.rows = []
        camera = {"stable_id": "review.camera", "bookmark": 0}
        counters = {"draw_calls": 3, "triangles": 2, "render_primitives": 2, "texture_bytes": 8}
        for i in range(5):
            state = {"phase": "PLAY", "sim_tick": i, "ui_tick": i + 1, "camera": camera}
            state_json = json.dumps(state, sort_keys=True, separators=(",", ":"))
            self.rows.append({"frame_hook": "frame_post_draw", "process_frame": i, "rendered_frame": i,
                "monotonic_us": 1000 + (i + 1) * 10_000, "frame_time_us": 10_000,
                "phase": state["phase"], "sim_tick": i, "ui_tick": i + 1,
                "hash_domain": "native-json-utf8", "state_json": state_json,
                "state_snapshot_sha256": digest(state_json.encode()),
                "counter_readiness": {"qualified": i >= 2, "reason": "qualified" if i >= 2 else "startup_not_qualified"},
                "measurement_eligible": i > 2, "counters": counters.copy() if i >= 2 else {k: None for k in counters},
                "raw_counter_readback": counters.copy() if i < 2 else None})
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(b"\0\xff\0\0")) + chunk(b"IEND", b"")
        self.write("project/out/menu.png", png)
        final = self.rows[-1]
        shot = {**self.binding, "label": "menu", "pid": 1234, "native_window_handle": "555", "window_id": 0,
            "monotonic_us": final["monotonic_us"], "requested_monotonic_us": final["monotonic_us"] - 1,
            "process_frame": 4, "minimum_process_frame": 3, "rendered_frame": 4, "minimum_rendered_frame": 3,
            "requested_tick": 1, "observed_tick": 2, "camera": camera,
            "requested_phase": "PLAY", "requested_camera_json": json.dumps(camera),
            "requested_camera_sha256": digest(json.dumps(camera).encode()),
            "sha256": digest(png), "size_bytes": len(png), "width": 1, "height": 1, "counters": counters}
        for name in ("phase", "sim_tick", "ui_tick", "hash_domain", "state_json", "state_snapshot_sha256"):
            shot[name] = final[name]
        self.report = {"schema_id": "hh-studio.play-observation", "schema_version": "1.0.0", "completed": True,
            "formal_acceptance": False, "public_ack": False, "binding": self.binding, "seed": 17, "fps": 60,
            "native": {"pid": 1234, "process_role": "play", "editor_hint": False, "main_thread": True,
                "native_window_handle": "555", "window_id": 0, "display_server": "Windows", "physics_hz": 60,
                "engine": {"hash": "c" * 40, "string": "4.7.2-stable (official)"},
                "configuration": {"rendering_method_supported": True, "rendering_method": "gl_compatibility",
                    "rendering_driver_supported": True, "rendering_driver": "opengl3", "delta_smoothing_supported": True,
                    "delta_smoothing": True, "vsync_mode": 1, "physics_hz": 60, "viewport_resolution": [1, 1],
                    "max_fps": 60, "time_scale": 1.0, "debug_build": True, "fixed_fps_flag": False}},
            "inputs": {}, "captures": {"menu": shot}, "native_frames": self.rows,
            "counter_definitions": dict(export._COUNTER_TEXT), "frame_start_monotonic_us": 1000,
            "frame_end_monotonic_us": 51000, "perf_measurement_start_frame_index": 3,
            "perf_measurement_start_monotonic_us": 31000,
            "trace_start": {"monotonic_us": 31000, "process_frame": 2, "rendered_frame": 2,
                            "rendered": True, "ready_frame_count": 3}}
        for label, name in {"asset_manifest_sha256": "input/manifest.json", "config_sha256": "config/fixture_actor.gd",
                "glb_sha256": "input/fixture.glb", "producer_report_sha256": "input/producer-report.json",
                "trace_sha256": "input/trace.json", "run_sha256": "input/run.json"}.items():
            self.report["inputs"][label] = digest((self.root / "project" / name).read_bytes())
        self.reseal_report()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if type(value) is bytes else raw(value))

    def reseal_report(self):
        """Synthetic adversarial fixture reseal, never used on real run evidence."""
        self.write("project/out/report.json", self.report)
        report_digest = digest((self.root / "project/out/report.json").read_bytes())
        runtime_sources = dict(self.source)
        prefix = ".local/reviews/" + self.root.name + "/project/"
        runtime_sources.update({prefix + k: v for k, v in self.snapshot.items()})
        runtime_sources[prefix + "input/run.json"] = digest((self.root / "project/input/run.json").read_bytes())
        stage_digests = {}
        for phase, source in (("import", self.source), ("runtime", runtime_sources)):
            pid = 1234 if phase == "runtime" else 1233
            prefix = phase + "-host/"
            self.write(prefix + "process-start.json", {"pid": pid})
            self.write(prefix + "process-exit.json", {"pid": pid, "exit_code": 0})
            marker = {"report_sha256": report_digest, "pid": pid,
                      **{k: self.binding[k] for k in ("run_id", "command_id", "runtime_instance_id")}}
            self.write(prefix + "stdout.txt", b"HH_GT06_COMPLETE " + raw(marker) if phase == "runtime" else b"")
            self.write(prefix + "stderr.txt", b"")
            cwd = str(self.root / "project")
            arguments = ["--headless", "--editor", "--path", cwd, "--import"] if phase == "import" else ["--path", cwd]
            self.write(prefix + "invocation.json", {"source_files": source, "binary_sha256": "b" * 64,
                "argv": [str(self.root / self.lock["godot"]["gui_executable"]), *arguments],
                "cwd": cwd, "formal_acceptance": False})
            stage = {"artifacts": {name: digest((self.root / prefix / name).read_bytes()) for name in
                                  ("process-start.json", "process-exit.json", "stdout.txt", "stderr.txt")},
                "completed": True, "natural_tree_exit": True, "actual_process_exit": {"pid": pid, "exit_code": 0},
                "wrapper_exit_code": 0, "active_before_cleanup": 0,
                "job": {"closed": True, "zero_observed": True, "tainted": False, "handle_retained": False,
                        "active_count": 0, "failed_operations": []}}
            self.write(prefix + "capture.json", stage)
            stage_digests[phase] = digest((self.root / prefix / "capture.json").read_bytes())
        capture = {"schema": "HH-GT06-NATIVE-CAPTURE-1", "completed_native": True, "formal_acceptance": False,
            "public_ack": False, "source_unchanged": True, "binding": self.binding, "run_id": self.root.name,
            "process": self.identity, "report_sha256": report_digest,
            "process_metrics_sha256": digest((self.root / "process-metrics.json").read_bytes()),
            "import_capture_sha256": stage_digests["import"], "runtime_capture_sha256": stage_digests["runtime"]}
        self.write("capture.json", capture)
        self.anchor = digest((self.root / "capture.json").read_bytes())

    def build(self):
        return export.build_export(self.root, expected_capture_sha256=self.anchor,
                                   project_id="fixture.gt06", device_profile_id="workstation.gt01")


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="gt06-perf-export-")
        self.addCleanup(self.directory.cleanup)
        self.fixture = SyntheticRun(Path(self.directory.name))

    def fails(self, code):
        with self.assertRaises((export.ExportError, perf.PerfError)) as caught:
            self.fixture.build()
        self.assertEqual(caught.exception.code, code)

    def test_declared_window_raw_rss_and_separate_postprocessor(self):
        result = self.fixture.build()
        artifact = result["perf_artifact"]
        self.assertEqual(result["status"], "EXPORTED_DIAGNOSTIC")
        self.assertFalse(result["formal_acceptance"])
        self.assertEqual(result["measurement_window"]["excluded_startup_rows"], 3)
        self.assertFalse(result["measurement_window"]["whole_process_sampled"])
        self.assertEqual(artifact["summary"]["sample_count"], 2)
        self.assertEqual(artifact["summary"]["one_percent_low_fps"], 100)
        self.assertEqual(artifact["frames"][0]["frame_ms"], 10)
        self.assertEqual(artifact["rss_samples"][1]["rss_bytes"], 110000)
        self.assertEqual(artifact["provenance"]["collector_sha256"], result["postprocess_collector"]["closure_sha256"])
        self.assertNotIn("host/replay/perf_export.py", self.fixture.source)
        self.assertIn("host/replay/perf_export.py", result["postprocess_collector"]["source_files"])
        self.assertEqual(result["raw_files"]["project/out/report.json"], digest((self.fixture.root / "project/out/report.json").read_bytes()))
        perf.validate_artifact(artifact)

    def test_external_anchor_rejects_replaced_top_capture(self):
        self.fixture.write("capture.json", {})
        self.fails("RAW_HASH_MISMATCH")

    def test_frozen_source_and_runtime_input_hashes(self):
        frozen = next((self.fixture.root / "source").iterdir())
        frozen.write_bytes(b"changed source")
        self.fails("RAW_HASH_MISMATCH")

    def test_runtime_input_tamper(self):
        self.fixture.write("project/input/fixture.glb", b"different")
        self.fails("RAW_HASH_MISMATCH")

    def test_extra_runtime_source_rejected(self):
        self.fixture.write("project/scripts/injected.gd", b"unexpected")
        self.fails("SNAPSHOT_FILE_SET")

    def test_metrics_tamper(self):
        self.fixture.write("process-metrics.json", {})
        self.fails("RAW_HASH_MISMATCH")

    def test_missing_native_configuration_is_not_defaulted(self):
        self.fixture.report["native"]["configuration"]["rendering_driver_supported"] = False
        self.fixture.report["native"]["configuration"]["rendering_driver"] = None
        self.fixture.reseal_report()
        self.fails("CONFIG_API_UNSUPPORTED")

    def test_unrecorded_runtime_flag_rejected(self):
        path = self.fixture.root / "runtime-host/invocation.json"
        invocation = json.loads(path.read_bytes())
        invocation["argv"].append("--fixed-fps")
        path.write_bytes(raw(invocation))
        self.fails("STAGE_COMMAND")

    def test_startup_frame_gap_rejected(self):
        self.fixture.rows[1]["process_frame"] += 1
        self.fixture.reseal_report()
        self.fails("RAW_FRAME_SEQUENCE")

    def test_missing_readiness_remains_gap(self):
        self.fixture.report.pop("perf_measurement_start_frame_index")
        self.fixture.report.pop("perf_measurement_start_monotonic_us")
        self.fixture.reseal_report()
        self.fails("VIEWPORT_COUNTER_READINESS_UNPROVEN")

    def test_unavailable_measured_counter_not_filled(self):
        self.fixture.report["native_frames"][3]["counters"]["draw_calls"] = None
        self.fixture.reseal_report()
        self.fails("MEASURED_COUNTER_VALUES")

    def test_startup_rows_not_silently_reclassified(self):
        self.fixture.report["native_frames"][1]["counter_readiness"]["qualified"] = True
        self.fixture.reseal_report()
        self.fails("STARTUP_COUNTER_QUALIFICATION")

    def test_anchor_and_trace_start_consistency(self):
        self.fixture.report["trace_start"]["monotonic_us"] += 1
        self.fixture.reseal_report()
        self.fails("TRACE_START_ANCHOR")

    def test_actual_exit_file_independent_of_pass_status(self):
        self.fixture.write("runtime-host/process-exit.json", {"pid": 1234, "exit_code": 86})
        self.fails("RAW_HASH_MISMATCH")

    def test_resealed_bad_exit_cannot_become_success(self):
        f = self.fixture
        f.write("runtime-host/process-exit.json", {"pid": 1234, "exit_code": 86})
        stage = json.loads((f.root / "runtime-host/capture.json").read_bytes())
        stage["artifacts"]["process-exit.json"] = digest((f.root / "runtime-host/process-exit.json").read_bytes())
        f.write("runtime-host/capture.json", stage)
        top = json.loads((f.root / "capture.json").read_bytes())
        top["runtime_capture_sha256"] = digest((f.root / "runtime-host/capture.json").read_bytes())
        f.write("capture.json", top)
        f.anchor = digest((f.root / "capture.json").read_bytes())
        self.fails("STAGE_EXIT")

    def test_capture_hash_and_stale_timestamp(self):
        self.fixture.report["captures"]["menu"]["requested_monotonic_us"] = 51000
        self.fixture.reseal_report()
        self.fails("STALE_SCREENSHOT")

    def test_capture_phase_fence(self):
        self.fixture.report["captures"]["menu"]["requested_phase"] = "PAUSED"
        self.fixture.reseal_report()
        self.fails("SCREENSHOT_PHASE_FENCE")

    def test_capture_camera_fence(self):
        self.fixture.report["captures"]["menu"]["requested_camera_json"] += " "
        self.fixture.reseal_report()
        self.fails("SCREENSHOT_CAMERA_FENCE")

    def test_direct_cli_bootstrap_outside_project(self):
        result = subprocess.run([sys.executable, "-B", str(STUDIO / "host/replay/perf_export.py"), "--help"],
                                cwd=self.directory.name, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--expected-capture-sha256", result.stdout)

    def test_png_tamper(self):
        self.fixture.write("project/out/menu.png", b"wrong")
        self.fails("RAW_HASH_MISMATCH")

    def test_state_json_rehash_required(self):
        self.fixture.report["native_frames"][3]["state_json"] += " "
        self.fixture.reseal_report()
        self.fails("STATE_HASH")

    def test_process_window_binding(self):
        self.fixture.report["native"]["native_window_handle"] = "999"
        self.fixture.reseal_report()
        self.fails("NATIVE_WINDOW_OBSERVATION")

    def test_closed_native_counter_semantics(self):
        self.fixture.report["counter_definitions"]["draw_calls"] = "global Performance total"
        self.fixture.reseal_report()
        self.fails("COUNTER_DEFINITIONS")

    def test_output_exclusive_create_and_gap_without_artifact(self):
        self.fixture.report.pop("perf_measurement_start_frame_index")
        self.fixture.reseal_report()
        arguments = dict(expected_capture_sha256=self.fixture.anchor,
                         project_id="fixture.gt06", device_profile_id="workstation.gt01")
        result = export.export_run(self.fixture.root, **arguments)
        self.assertEqual(result["status"], "GAP")
        self.assertIsNone(result["perf_artifact"])
        before = (self.fixture.root / export.OUTPUT_NAME).read_bytes()
        with self.assertRaises(FileExistsError):
            export.export_run(self.fixture.root, **arguments)
        self.assertEqual(before, (self.fixture.root / export.OUTPUT_NAME).read_bytes())


if __name__ == "__main__":
    unittest.main()
