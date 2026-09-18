"""Synthetic unit witnesses exercise rejection sites; no native proof is forged."""
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay.trace import default_trace
from studio.host.replay.observation import ObservationRejected, validate_observation, MAX_REPORT_BYTES


def encoded(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def png(width=960, height=640):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    pixels = b"\0" + b"\x50\x96\xc8\xff" * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels * height)) + chunk(b"IEND", b"")


def camera(bookmark):
    position = [5.2, 4.0, 7.5] if bookmark == 0 else [-5.2, 3.5, 7.5]
    target = [0.0, .9, 0.0]
    normalize = lambda v: [x / math.sqrt(sum(a*a for a in v)) for x in v]
    cross = lambda a, b: [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
    z = normalize([a-b for a, b in zip(position, target)])
    x = normalize(cross([0, 1, 0], z)); y = cross(z, x)
    matrix = list(zip(x, y, z))
    root = math.sqrt(1 + matrix[0][0] + matrix[1][1] + matrix[2][2]) * 2
    q = [(matrix[2][1]-matrix[1][2])/root, (matrix[0][2]-matrix[2][0])/root,
         (matrix[1][0]-matrix[0][1])/root, root/4]
    return {"stable_id": "review.camera", "bookmark": bookmark, "position": position,
            "rotation_xyzw": q, "projection": 1, "size": 7.5, "near": .05, "far": 50.0, "target": target}


def state(tick, speed, seed):
    phase = "MENU" if tick < 11 else "PLAY" if tick < 150 else "PAUSED" if tick < 200 else "PLAY" if tick < 350 else "QUITTING"
    sim = max(0, min(tick, 149) - 10) + max(0, min(tick, 349) - 199)
    emote_elapsed = max(0, min(tick, 149) - 119) + max(0, min(tick, 349) - 199)
    remaining = max(0, 90-emote_elapsed) if tick >= 120 else 0
    spins = max(0, min(tick, 149)-79) + max(0, min(tick, 349)-199)
    x = max(0, min(tick - 29, 30)) * speed / 60
    angle = .5 if remaining > 0 else 0
    return {"phase": phase, "sim_tick": sim, "ui_tick": tick+1, "move_speed": speed,
        "body_position": [x, 1.0, 0.0], "body_velocity": [speed if 30 <= tick < 60 else 0.0, 0.0, 0.0], "avatar_position": [x, .075, 0.0],
        "animation": {"clip": "walk" if 30 <= tick < 60 and speed > 0 else "idle", "position": (sim % 60)/60},
        "outfit_visible": tick < 100, "emote_remaining": remaining, "emote_count": int(tick >= 120),
        "emote_bone": "bn_upperarm_r", "emote_pose_xyzw": [0.0, 0.0, math.sin(angle/2), math.cos(angle/2)],
        "prop_active": tick >= 80, "prop_spin_tick": spins, "prop_count": int(tick >= 80),
        "prop_rotation": [0.0, spins*(.0125+(seed % 11)*.025), 0.0], "prop_position": [2.2, .3, 0.0],
        "last_prop_hit": {"distance_m": 1.0, "hit": True, "matched_prop": True,
                          "collider": "prp_fixture_crate_collider_body", "position": [2.0, .3, 0.0]} if tick >= 80 else {},
        "camera": camera(int(tick >= 230)), "focus": "StartButton" if tick < 11 else "", "tree_paused": phase == "PAUSED"}


def fixture(project, speed=3.0):
    trace = default_trace(17)
    inputs = {"input/trace.json": trace.raw, "input/fixture.glb": b"synthetic GLB bytes: native validation is a separate layer",
              "input/producer-report.json": b"{}\n", "input/manifest.json": b"{}\n",
              "config/fixture_actor.gd": ("extends Node3D\n@export var fixture_value: int = 1\n@export var move_speed: float = " + str(speed) + "\n").encode()}
    binding = {"run_id": "gt06-unit", "command_id": "gt06-unit.play", "runtime_instance_id": "gt06-unit.runtime",
               "source_closure_sha256": "1"*64, "runtime_snapshot_sha256": "2"*64,
               "trace_sha256": trace.raw_sha256, "glb_sha256": sha(inputs["input/fixture.glb"]), "generation": 1}
    inputs["input/run.json"] = encoded(binding)
    for name, raw in inputs.items():
        target = project/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    process = {"identity": {"pid": 1234, "process_start": "windows:123456789"}, "errors": [],
               "started_utc_ms": 1000000000000, "ended_utc_ms": 1000000008000,
               "host_start_mono_us": 80000000, "host_end_mono_us": 88000000,
               "samples": [{"host_mono_us": 80100000, "rss_bytes": 123456, "visible_window_handles": ["42"]}]}
    native = {"pid": 1234, "window_id": 0, "native_window_handle": "42", "display_server": "Windows",
              "engine": {"major": 4, "minor": 7, "patch": 2, "status": "stable", "hash": "ed1daf0bf-unit"},
              "started_unix": 1000000000.1, "started_monotonic_us": 1000000, "physics_hz": 60,
              "process_role": "play", "editor_hint": False, "main_thread": True,
              "configuration": {"rendering_method": "gl_compatibility", "rendering_method_supported": True,
                  "rendering_driver": "opengl3", "rendering_driver_supported": True, "viewport_resolution": [960, 640],
                  "vsync_mode": 1, "max_fps": 60, "physics_hz": 60, "time_scale": 1.0, "debug_build": False,
                  "delta_smoothing_supported": False, "delta_smoothing": None, "fixed_fps_flag": False}}
    observations, frames, events, callbacks = [], [], [], []
    counter = {"triangles": 998, "draw_calls": 15, "render_primitives": 1010, "texture_bytes": 2048}
    current_phase = "MENU"
    for tick in range(360):
        value = state(tick, speed, trace.value["seed"])
        native_json = encoded(value).decode()
        observations.append({"trace_tick": tick, "state": value, "state_json": native_json,
                             "snapshot_sha256": sha(native_json.encode()), "hash_domain": "native-json-utf8",
                             "held_keys": list(trace.value["frames"][tick]["held"]), "physics_frame": tick+5})
        frames.append({"monotonic_us": 1000100+(tick+3)*16667, "frame_time_us": 16667,
                       "process_frame": tick+10, "rendered_frame": tick+8, "trace_tick": tick,
                       "sim_tick": value["sim_tick"], "ui_tick": value["ui_tick"], "phase": value["phase"],
                       "state_json": native_json, "state_snapshot_sha256": sha(native_json.encode()),
                       "hash_domain": "native-json-utf8", "frame_hook": "frame_post_draw", "counters": counter.copy(),
                       "counter_readiness": {"qualified": True, "reason": "qualified"},
                       "raw_counter_readback": None, "measurement_eligible": True})
        for edge, pressed in (("released", False), ("pressed", True)):
            for key in trace.value["frames"][tick][edge]:
                events.append({"event_index": len(events), "trace_tick": tick, "key": key,
                               "pressed": pressed, "window_id": 0, "reason": "trace"})
                callbacks.append({"callback": "_input", "trace_tick": tick, "key": key,
                                  "pressed": pressed, "window_id": 0, "phase_before": current_phase})
                if pressed and key == "ESCAPE": current_phase = "PAUSED" if current_phase == "PLAY" else "PLAY"
                if pressed and key == "Q": current_phase = "QUITTING"
        if tick == 11:
            callbacks.append({"callback": "StartButton.pressed", "trace_tick": tick, "phase_before": "MENU"})
            current_phase = "PLAY"
    image = png(); (project/"out").mkdir(exist_ok=True)
    captures = {}
    for request in trace.value["captures"]:
        tick, label = request["tick"], request["label"]
        frame, snapshot = frames[tick], observations[tick]["state"]
        (project/"out"/(label+".png")).write_bytes(image)
        captures[label] = {**binding, "label": label, "requested_tick": tick, "observed_tick": tick,
            "requested_monotonic_us": frame["monotonic_us"]-8000, "monotonic_us": frame["monotonic_us"],
            "minimum_rendered_frame": frame["rendered_frame"]-1, "minimum_process_frame": frame["process_frame"]-1,
            "rendered_frame": frame["rendered_frame"], "process_frame": frame["process_frame"],
            "captured_at_unix": native["started_unix"]+(frame["monotonic_us"]-native["started_monotonic_us"])/1000000,
            "pid": 1234, "window_id": 0, "native_window_handle": "42", "camera": snapshot["camera"],
            "requested_phase": snapshot["phase"], "requested_camera_json": encoded(snapshot["camera"]).decode(),
            "requested_camera_sha256": sha(encoded(snapshot["camera"])),
            "state_json": frame["state_json"], "state_snapshot_sha256": frame["state_snapshot_sha256"],
            "hash_domain": "native-json-utf8", "sha256": sha(image), "size_bytes": len(image), "width": 960, "height": 640,
            "sim_tick": snapshot["sim_tick"], "ui_tick": snapshot["ui_tick"], "phase": snapshot["phase"], "counters": counter.copy()}
    final_state = copy.deepcopy(observations[-1]["state"]); final_state["ui_tick"] += 1
    startup = []
    for index in range(2):
        value = state(-1, speed, trace.value["seed"]); raw = encoded(value)
        startup.append({"monotonic_us": 1000100+(index+1)*16667, "frame_time_us": 16667,
            "process_frame": index+5, "rendered_frame": index*2, "trace_tick": -1,
            "sim_tick": 0, "ui_tick": 0, "phase": "MENU", "state_json": raw.decode(),
            "state_snapshot_sha256": sha(raw), "hash_domain": "native-json-utf8", "frame_hook": "frame_post_draw",
            "counters": counter.copy() if index else {k: None for k in counter},
            "counter_readiness": {"qualified": bool(index), "reason": "qualified" if index else "startup_not_qualified"},
            "raw_counter_readback": None if index else {**counter, "draw_calls": 9}, "measurement_eligible": False})
    frames = startup + frames
    report = {"schema_id": "hh-studio.play-observation", "schema_version": "1.0.0", "binding": binding,
              "native": native, "seed": trace.value["seed"], "fps": 60, "observations": observations,
              "input_events": events, "callbacks": callbacks,
              "inputs": {key: sha(inputs[path]) for key, path in (("trace_sha256", "input/trace.json"),
                  ("glb_sha256", "input/fixture.glb"), ("config_sha256", "config/fixture_actor.gd"),
                  ("producer_report_sha256", "input/producer-report.json"), ("asset_manifest_sha256", "input/manifest.json"),
                  ("run_sha256", "input/run.json"))},
              "transitions": [{"trace_tick": tick, "from": a, "to": b, "trigger": trigger} for tick, a, b, trigger in
                  ((11, "MENU", "PLAY", "button.Start"), (150, "PLAY", "PAUSED", "key.ESCAPE"),
                   (200, "PAUSED", "PLAY", "key.ESCAPE"), (350, "PLAY", "QUITTING", "key.Q"))],
              "captures": captures, "native_frames": frames, "frame_start_monotonic_us": 1000100,
              "frame_end_monotonic_us": frames[-1]["monotonic_us"],
              "perf_measurement_start_monotonic_us": startup[-1]["monotonic_us"], "perf_measurement_start_frame_index": 2,
              "trace_start": {k: startup[-1][k] for k in ("monotonic_us", "process_frame", "rendered_frame")},
              "counter_definitions": {key: "Synthetic unit counter, not measured" for key in counter},
              "final": {"phase": "QUITTING", "trace_ticks": 360, "sim_tick": final_state["sim_tick"],
                        "held_keys": [], "pending_captures": 0, "state": final_state},
              "completed": True, "public_ack": False, "formal_acceptance": False}
    report["trace_start"].update(ready_frame_count=2, rendered=True)
    return trace, binding, process, report


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-gt06-observation-unit-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.trace, self.binding, self.process, self.report = fixture(self.project)

    def verify(self, raw=None, speed=3.0):
        return validate_observation(encoded(self.report) if raw is None else raw, trace=self.trace,
            binding=self.binding, config_speed=speed, project=self.project, process=self.process)

    def rejects(self, code=None, raw=None):
        with self.assertRaises(ObservationRejected) as error:
            self.verify(raw)
        if code:
            self.assertEqual(error.exception.code, code)

    def reseal(self, tick):
        row = self.report["observations"][tick]
        row["state_json"] = encoded(row["state"]).decode()
        row["snapshot_sha256"] = sha(row["state_json"].encode())

    def test_complete_positive_fixture_and_identical_static_pngs_are_allowed(self):
        result = self.verify()
        self.assertTrue(result["complete"] and result["all_postconditions"])
        self.assertFalse(result["movement_fault_observed"])
        self.assertFalse(result["managed_repair_proven"])
        self.assertEqual(result["observed_movement_m"], 1.5)
        self.assertEqual(len(result["capture_hashes"]), 7)
        self.assertEqual(len(set(result["capture_hashes"].values())), 1)

    def test_completed_zero_speed_is_explicit_fault_not_repair_pass(self):
        self.trace, self.binding, self.process, self.report = fixture(self.project, 0.0)
        result = self.verify(speed=0.0)
        self.assertTrue(result["complete"] and result["movement_fault_observed"])
        self.assertFalse(result["all_postconditions"] or result["managed_repair_proven"])
        self.assertEqual(result["observed_movement_m"], 0)

    def test_raw_snapshot_hash_includes_native_whitespace(self):
        row = self.report["observations"][2]
        row["state_json"] = " \n" + row["state_json"] + "\t"
        row["snapshot_sha256"] = sha(row["state_json"].encode())
        self.assertTrue(self.verify()["complete"])
        row["snapshot_sha256"] = sha(encoded(row["state"]))
        self.rejects("OBS_SNAPSHOT_HASH")

    def test_snapshot_parsed_value_cannot_disagree_with_adjacent_state(self):
        self.report["observations"][2]["state"]["ui_tick"] += 1
        self.rejects("OBS_SNAPSHOT_VALUE")

    def test_resealed_wrong_postdestination_phase_cannot_pass(self):
        self.report["observations"][11]["state"]["phase"] = "MENU"
        self.reseal(11)
        self.rejects("OBS_POST_DESTINATION")

    def test_resealed_movement_and_configuration_faults_cannot_hide(self):
        self.report["observations"][40]["state"]["body_position"][0] = 0
        self.reseal(40)
        self.rejects("OBS_MOVEMENT")
        self.report["observations"][40]["state"]["move_speed"] = 0
        self.reseal(40)
        self.rejects("OBS_CONFIG_SPEED")

    def test_pause_body_animation_and_simulation_changes_rejected(self):
        original = copy.deepcopy(self.report)
        for field, value in (("body_position", [1.5, 1.01, 0]), ("animation", {"clip": "idle", "position": .2}),
                             ("emote_pose_xyzw", [0, 0, 0, 1])):
            self.report = copy.deepcopy(original)
            self.report["observations"][165]["state"][field] = value
            if field == "body_position":
                self.report["observations"][165]["state"]["avatar_position"][1] += .01
            self.reseal(165)
            self.rejects("OBS_PAUSE_FROZEN")

    def test_ui_must_advance_during_pause(self):
        for tick in range(150, 200):
            self.report["observations"][tick]["state"]["ui_tick"] = 150
            self.reseal(tick)
        self.rejects("OBS_PAUSE_RESUME_CLOCK")

    def test_resume_must_advance_simulation(self):
        self.report["observations"][200]["state"]["sim_tick"] -= 1
        self.reseal(200)
        self.rejects("OBS_POST_DESTINATION")

    def test_interaction_needs_native_hit_and_changed_outfit_emote(self):
        original = copy.deepcopy(self.report)
        for key, value, expected in (("last_prop_hit", {}, "OBS_ACTION_POSTCONDITION"),
                                     ("outfit_visible", True, "OBS_ACTION_POSTCONDITION"),
                                     ("emote_count", 0, "OBS_ACTION_POSTCONDITION")):
            self.report = copy.deepcopy(original)
            self.report["observations"][125]["state"][key] = value
            self.reseal(125)
            self.rejects(expected)

    def test_input_event_callback_and_real_menu_button_are_required(self):
        original = copy.deepcopy(self.report)
        self.report["input_events"][0]["reason"] = "direct-call"
        self.rejects("OBS_INPUT_EVENTS")
        self.report = copy.deepcopy(original)
        self.report["callbacks"][0]["key"] = "TAB"
        self.rejects("OBS_CALLBACK_EVENT")
        self.report = copy.deepcopy(original)
        self.report["callbacks"][2]["callback"] = "signal.emit"
        self.rejects("OBS_MENU_CALLBACK")

    def test_duplicate_or_missing_observation_and_held_readback_fail(self):
        original = copy.deepcopy(self.report)
        self.report["observations"].pop()
        self.rejects("OBS_TRACE_COMPLETENESS")
        self.report = copy.deepcopy(original)
        self.report["observations"][1]["trace_tick"] = 0
        self.rejects("OBS_OBSERVATION_ORDER")
        self.report = copy.deepcopy(original)
        self.report["observations"][165]["held_keys"] = []
        self.rejects("OBS_OBSERVATION_ORDER")

    def test_quit_must_drain_releases_and_captures(self):
        self.report["final"]["held_keys"] = ["Q"]
        self.rejects("OBS_FINAL_DRAIN")
        self.report["final"]["held_keys"] = []
        self.report["final"]["pending_captures"] = 1
        self.rejects("OBS_FINAL_DRAIN")

    def test_stale_native_pid_window_or_source_binding_rejected(self):
        original = copy.deepcopy(self.report)
        self.report["native"]["pid"] += 1
        self.rejects("OBS_PROCESS_IDENTITY")
        self.report = copy.deepcopy(original)
        self.report["native"]["native_window_handle"] = "99"
        self.rejects("OBS_NATIVE_WINDOW")
        self.report = copy.deepcopy(original)
        self.report["captures"]["moved"]["source_closure_sha256"] = "0"*64
        self.rejects("OBS_CAPTURE_BINDING")

    def test_input_bytes_and_report_config_hash_are_checked(self):
        (self.project/"config/fixture_actor.gd").write_bytes(b"changed after launch")
        self.rejects("OBS_INPUT_HASH")

    def test_capture_request_tick_frame_fence_and_native_frame_binding(self):
        original = copy.deepcopy(self.report)
        self.report["captures"]["moved"]["requested_tick"] -= 1
        self.rejects("OBS_CAPTURE_BINDING")
        self.report = copy.deepcopy(original)
        cap = self.report["captures"]["moved"]
        cap["minimum_rendered_frame"] = cap["rendered_frame"]
        self.rejects("OBS_CAPTURE_FENCE")
        self.report = copy.deepcopy(original)
        self.report["captures"]["moved"]["monotonic_us"] += 1
        self.rejects("OBS_CAPTURE_FRAME")

    def test_camera_and_png_bytes_not_only_metadata_are_checked(self):
        self.report["captures"]["camera"]["camera"] = camera(0)
        self.rejects("OBS_CAPTURE_POSTCONDITION")
        self.report["captures"]["camera"]["camera"] = camera(1)
        (self.project/"out/menu.png").write_bytes(b"not a PNG")
        self.rejects("OBS_PNG_BINDING")
        data = b"not a PNG"
        self.report["captures"]["menu"].update(sha256=sha(data), size_bytes=len(data))
        self.rejects("OBS_PNG_DECODE")

    def test_decoded_png_dimensions_checked_after_resealed_file_hash(self):
        image = png(16, 16)
        (self.project/"out/menu.png").write_bytes(image)
        self.report["captures"]["menu"].update(sha256=sha(image), size_bytes=len(image))
        self.rejects("OBS_PNG_DIMENSIONS")

    def test_native_frame_clock_order_and_duration_are_recomputed(self):
        original = copy.deepcopy(self.report)
        self.report["native_frames"][1]["frame_time_us"] += 1
        self.rejects("OBS_NATIVE_FRAME_ORDER")
        self.report = copy.deepcopy(original)
        self.report["native_frames"][1]["rendered_frame"] = self.report["native_frames"][0]["rendered_frame"]
        self.rejects("OBS_NATIVE_FRAME_ORDER")
        self.report = copy.deepcopy(original)
        self.report["frame_end_monotonic_us"] += 1
        self.rejects("OBS_NATIVE_INTERVAL")

    def test_host_clocks_are_independent_and_utc_outside_interval_rejected(self):
        self.process["host_start_mono_us"] += 1000000000
        self.process["host_end_mono_us"] += 1000000000
        self.process["samples"][0]["host_mono_us"] += 1000000000
        self.assertTrue(self.verify()["complete"])
        self.report["captures"]["menu"]["captured_at_unix"] += 1000
        self.rejects("OBS_UTC_INTERVAL")

    def test_unknown_fields_nonfinite_duplicate_keys_depth_and_byte_caps(self):
        self.report["source_ok"] = True
        self.rejects("OBS_FIELDS")
        del self.report["source_ok"]
        raw = encoded(self.report)
        self.rejects("OBS_JSON_DUPLICATE", raw.replace(b'"completed":true', b'"completed":true,"completed":true'))
        self.rejects("OBS_JSON_NONFINITE", raw.replace(b'"fps":60', b'"fps":NaN'))
        self.rejects("OBS_JSON_DEPTH", b"["*100 + b"0" + b"]"*100)
        self.rejects("OBS_JSON_BYTES", b" "*(MAX_REPORT_BYTES+1))

    def test_unexplained_process_error_headless_or_editor_cannot_pass(self):
        self.process["errors"] = ["probe failed"]
        self.rejects("OBS_PROCESS_IDENTITY")
        self.process["errors"] = []
        self.report["native"]["display_server"] = "headless"
        self.rejects("OBS_NATIVE_CONTEXT")

    def test_boolean_integer_aliases_cannot_enter_native_identity_or_events(self):
        original = copy.deepcopy(self.report)
        for area, field, expected in (("binding", "generation", "OBS_REPORT_BINDING"),
                                      ("event", "event_index", "OBS_INPUT_EVENTS"),
                                      ("callback", "window_id", "OBS_CALLBACK_EVENT")):
            self.report = copy.deepcopy(original)
            row = self.report[area] if area == "binding" else self.report["input_events" if area == "event" else "callbacks"][0]
            row[field] = bool(row[field])
            self.rejects(expected)

    def test_godot_integral_float_generation_remains_valid(self):
        self.report["binding"] = {**self.binding, "generation": 1.0}
        for cap in self.report["captures"].values():
            cap["generation"] = 1.0
        self.assertTrue(self.verify()["complete"])

    def test_avatar_cannot_stay_behind_moving_body(self):
        self.report["observations"][40]["state"]["avatar_position"][0] = 0
        self.reseal(40)
        self.rejects("OBS_AVATAR_FOLLOWS_BODY")

    def test_animation_cannot_freeze_while_play_simulation_advances(self):
        self.report["observations"][40]["state"]["animation"] = self.report["observations"][39]["state"]["animation"].copy()
        self.reseal(40)
        self.rejects("OBS_ANIMATION_ADVANCE")

    def test_startup_readback_retained_but_not_admitted_as_measured_counter(self):
        self.assertEqual(self.report["native_frames"][0]["raw_counter_readback"]["draw_calls"], 9)
        self.assertTrue(self.verify()["complete"])
        self.report["native_frames"][0]["measurement_eligible"] = True
        self.rejects("OBS_COUNTER_READINESS")

    def test_measurement_anchor_cannot_be_shifted_to_discard_slow_frames(self):
        self.report["perf_measurement_start_frame_index"] += 1
        self.rejects("OBS_COUNTER_READINESS")

    def test_trace_cannot_begin_before_bound_render_readiness(self):
        self.report["trace_start"]["monotonic_us"] += 1
        self.rejects("OBS_TRACE_READINESS")

    def test_capture_camera_hash_binds_exact_raw_string_and_requested_value(self):
        cap = self.report["captures"]["menu"]
        cap["requested_camera_json"] = "\n" + cap["requested_camera_json"]
        cap["requested_camera_sha256"] = sha(cap["requested_camera_json"].encode())
        self.assertTrue(self.verify()["complete"])
        cap["requested_camera_sha256"] = sha(encoded(camera(0)))
        self.rejects("OBS_CAPTURE_REQUEST_CAMERA")
        cap["requested_camera_json"] = encoded(camera(1)).decode()
        cap["requested_camera_sha256"] = sha(cap["requested_camera_json"].encode())
        self.rejects("OBS_CAPTURE_REQUEST_CAMERA")

    def test_resealed_late_menu_capture_still_rejects_phase_drift(self):
        cap = self.report["captures"]["menu"]
        frame = self.report["native_frames"][13]  # Startup rows + trace tick 11, now PLAY.
        cap["observed_tick"] = 11
        for key in ("monotonic_us", "rendered_frame", "process_frame", "state_json", "state_snapshot_sha256",
                    "hash_domain", "sim_tick", "ui_tick", "phase", "counters"):
            cap[key] = frame[key]
        self.rejects("OBS_CAPTURE_POSTCONDITION")

    def test_godot_srgb_extension_is_closed_crc_checked_and_sample_preserving(self):
        from studio.host.replay.observation import _decode_capture_png
        from studio.pipeline.png_decode import decode_png, PNGRejected
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
        raw = png(16, 16)
        srgb = chunk(b"sRGB", b"\0")
        native = raw[:33] + srgb + raw[33:]
        self.assertEqual(_decode_capture_png(native).rgba8, decode_png(raw).rgba8)
        with self.assertRaises(PNGRejected):
            decode_png(native)  # The GT05 asset profile remains unchanged.
        corrupt = bytearray(native); corrupt[45] ^= 1
        wrong_intent = raw[:33] + chunk(b"sRGB", b"\1") + raw[33:]
        duplicate = raw[:33] + srgb + srgb + raw[33:]
        after_idat = raw[:-12] + srgb + raw[-12:]
        unknown = raw[:33] + chunk(b"tEXt", b"key\0value") + raw[33:]
        for malformed in (bytes(corrupt), wrong_intent, duplicate, after_idat, unknown):
            with self.subTest(malformed=sha(malformed)):
                with self.assertRaises(ObservationRejected):
                    _decode_capture_png(malformed)


def retained_native_suite(run_root, speed):
    """Opt-in read-only regression on a retained run; never manufacture native proof."""
    class RetainedNativeTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            from studio.host.replay.trace import validate_trace
            cls.project = run_root.resolve()/"project"
            cls.raw = (cls.project/"out/report.json").read_bytes()
            if len(cls.raw) > MAX_REPORT_BYTES:
                raise ValueError("Retained report exceeds cap")
            cls.trace = validate_trace((cls.project/"input/trace.json").read_bytes())
            cls.binding = json.loads((cls.project/"input/run.json").read_bytes())
            cls.process = json.loads((run_root/"process-metrics.json").read_bytes())

        def verify(self, raw=None):
            return validate_observation(self.raw if raw is None else raw, trace=self.trace,
                binding=self.binding, config_speed=speed, project=self.project, process=self.process)

        def test_retained_native_run_meets_semantics_with_explicit_fault_status(self):
            result = self.verify()
            self.assertTrue(result["complete"])
            self.assertEqual(result["all_postconditions"], speed == 3.0)
            self.assertEqual(result["movement_fault_observed"], speed == 0.0)
            self.assertAlmostEqual(result["observed_movement_m"], speed*.5, places=3)
            self.assertEqual(len(result["capture_hashes"]), 7)

        def test_retained_capture_cannot_be_rebound_to_stale_source(self):
            report = json.loads(self.raw)
            report["captures"]["menu"]["source_closure_sha256"] = "0"*64
            with self.assertRaisesRegex(ObservationRejected, "OBS_CAPTURE_BINDING"):
                self.verify(encoded(report))

        def test_retained_pause_cannot_hide_resealed_body_motion(self):
            report = json.loads(self.raw)
            row = report["observations"][165]
            row["state"]["body_position"][1] += .1
            row["state"]["avatar_position"][1] += .1
            row["state_json"] = encoded(row["state"]).decode()
            row["snapshot_sha256"] = sha(row["state_json"].encode())
            with self.assertRaisesRegex(ObservationRejected, "OBS_PAUSE_FROZEN"):
                self.verify(encoded(report))

        def test_retained_native_snapshot_hash_cannot_use_an_alternate_serialization(self):
            report = json.loads(self.raw)
            row = report["observations"][40]
            # Python's compact serialization can happen to match some Godot
            # snapshots byte-for-byte. A different valid serialization must
            # still fail, even though its parsed value is exactly the same.
            replacement = sha(json.dumps(row["state"], indent=2, allow_nan=False).encode())
            self.assertNotEqual(replacement, row["snapshot_sha256"])
            row["snapshot_sha256"] = replacement
            with self.assertRaisesRegex(ObservationRejected, "OBS_SNAPSHOT_HASH"):
                self.verify(encoded(report))

    return unittest.defaultTestLoader.loadTestsFromTestCase(RetainedNativeTests)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-run", type=Path, help="Read-only retained run root with project/ and process-metrics.json")
    parser.add_argument("--native-speed", type=float, choices=(0.0, 3.0), default=3.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ObservationTests)
    if args.native_run:
        suite.addTests(retained_native_suite(args.native_run, args.native_speed))
    result = unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
