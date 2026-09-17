"""Read-only admission of the closed GT06 default-trace native observation.

The host separately proves actual process exit, owned-tree cleanup, stdout
marker, executable and complete immutable source map. This verifier binds that
trusted host context to native callbacks, postconditions and fixed output PNGs.
It neither launches an engine nor proves an editor repair from a speed change.
Native JSON snapshot strings are hashed verbatim, never reserialized as JCS.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
from typing import Any
import zlib

from studio.pipeline.png_decode import decode_png, PNGRejected
from .trace import ValidatedTrace, default_trace, validate_trace

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_PNG_BYTES = 1024 * 1024
MAX_NATIVE_FRAMES = 1200
UTC_TOLERANCE_MS = 2000
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_BIND = {"run_id", "command_id", "runtime_instance_id", "source_closure_sha256",
         "runtime_snapshot_sha256", "trace_sha256", "glb_sha256", "generation"}
_INPUTS = {"trace_sha256": ("input/trace.json", 262144), "glb_sha256": ("input/fixture.glb", 1048576),
           "config_sha256": ("config/fixture_actor.gd", 65536),
           "producer_report_sha256": ("input/producer-report.json", 1048576),
           "asset_manifest_sha256": ("input/manifest.json", 1048576), "run_sha256": ("input/run.json", 16384)}
_STATE = set("phase sim_tick ui_tick move_speed body_position body_velocity avatar_position animation outfit_visible emote_remaining emote_count emote_bone emote_pose_xyzw prop_active prop_spin_tick prop_count prop_rotation prop_position last_prop_hit camera focus tree_paused".split())
_CAMERA = set("stable_id bookmark position rotation_xyzw projection size near far target".split())
_COUNTERS = {"triangles", "draw_calls", "render_primitives", "texture_bytes"}
_REPORT = set("schema_id schema_version binding native inputs seed fps observations input_events callbacks transitions captures native_frames frame_start_monotonic_us frame_end_monotonic_us counter_definitions final completed public_ack formal_acceptance".split())
_REPORT |= {"trace_start", "perf_measurement_start_monotonic_us", "perf_measurement_start_frame_index"}
_NATIVE = set("pid window_id native_window_handle engine display_server started_unix started_monotonic_us physics_hz process_role editor_hint main_thread configuration".split())
_FRAME = set("monotonic_us frame_time_us process_frame rendered_frame trace_tick sim_tick ui_tick phase state_json state_snapshot_sha256 hash_domain frame_hook counters".split())
_FRAME |= {"counter_readiness", "raw_counter_readback", "measurement_eligible"}
_CAPTURE = set("label requested_tick observed_tick requested_monotonic_us monotonic_us minimum_rendered_frame minimum_process_frame rendered_frame process_frame captured_at_unix pid window_id native_window_handle camera state_json state_snapshot_sha256 hash_domain sha256 size_bytes width height sim_tick ui_tick phase counters".split()) | _BIND
_CAPTURE |= {"requested_phase", "requested_camera_json", "requested_camera_sha256"}
_CONFIGURATION = set("rendering_method rendering_method_supported rendering_driver rendering_driver_supported viewport_resolution vsync_mode max_fps physics_hz time_scale debug_build delta_smoothing_supported delta_smoothing fixed_fps_flag".split())


class ObservationRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(value, code):
    if not value:
        raise ObservationRejected(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _int(value, low=0, high=(1 << 53) - 1):
    return type(value) is int and low <= value <= high


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= (1 << 53) - 1


def _fields(value, fields, code="OBS_FIELDS"):
    _need(type(value) is dict and set(value) == fields, code)
    return value


def _binding_matches(value, binding):
    # Godot's JSON parser represents the input generation as 1.0. Accept that
    # exact integer value, while excluding Python's True == 1 equivalence.
    return (type(value) is dict and set(value) == _BIND
            and _number(value["generation"]) and value["generation"] == binding["generation"]
            and all(type(value[k]) is str and value[k] == binding[k] for k in _BIND - {"generation"}))


def _strict(raw, cap=MAX_REPORT_BYTES):
    _need(type(raw) is bytes and 0 < len(raw) <= cap, "OBS_JSON_BYTES")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise ObservationRejected("OBS_JSON_UTF8") from None
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            _need(depth <= 16, "OBS_JSON_DEPTH")
        elif char in "]}":
            depth -= 1
            _need(depth >= 0, "OBS_JSON_SYNTAX")
    def pairs(rows):
        _need(len(rows) <= 64, "OBS_JSON_MEMBERS")
        result = {}
        for key, value in rows:
            _need(key not in result, "OBS_JSON_DUPLICATE")
            result[key] = value
        return result
    def number(token, factory):
        _need(len(token) <= 64, "OBS_JSON_NUMBER")
        value = factory(token)
        _need(_number(value), "OBS_JSON_NUMBER")
        return value
    def constant(_):
        raise ObservationRejected("OBS_JSON_NONFINITE")
    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant,
                           parse_int=lambda v: number(v, int), parse_float=lambda v: number(v, float))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ObservationRejected("OBS_JSON_SYNTAX") from None
    _need(type(value) is dict, "OBS_JSON_OBJECT")
    pending, count = [value], 0
    while pending:
        item = pending.pop(); count += 1
        _need(count <= 250000, "OBS_JSON_VALUES")
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            _need(len(item) <= 7200, "OBS_JSON_ARRAY")
            pending.extend(item)
        elif type(item) is str:
            _need(len(item) <= 16384 and not any(0xD800 <= ord(c) <= 0xDFFF for c in item), "OBS_JSON_STRING")
    return value


def _read_regular(project, relative, cap):
    # All relative names here are fixed literals or validated trace labels.
    path = project / relative
    try:
        for parent in (path, *path.parents):
            info = parent.lstat()
            _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                  "OBS_REPARSE")
        entry = path.stat()
        _need(stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1 and 0 < entry.st_size <= cap, "OBS_FILE_SIZE_OR_KIND")
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(cap + 1)
            after = os.fstat(stream.fileno())
        current = path.stat()
        identity = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns, v.st_nlink)
        _need(identity(entry) == identity(before) == identity(after) == identity(current)
              and len(raw) == entry.st_size, "OBS_FILE_CHANGED")
        return raw
    except OSError:
        raise ObservationRejected("OBS_FILE_UNREADABLE") from None


def _near(a, b, epsilon=.001, code="OBS_NUMERIC"):
    _need(_number(a) and _number(b) and abs(a - b) <= epsilon, code)


def _vector(value, size=3):
    _need(type(value) is list and len(value) == size and all(_number(v) and abs(v) <= 10000 for v in value), "OBS_VECTOR")
    return value


def _camera(value):
    _fields(value, _CAMERA)
    _need(value["stable_id"] == "review.camera" and _int(value["bookmark"], 0, 1)
          and _int(value["projection"], 1, 1), "OBS_CAMERA")
    expected = [5.2, 4.0, 7.5] if value["bookmark"] == 0 else [-5.2, 3.5, 7.5]
    for a, b in zip(_vector(value["position"]), expected):
        _near(a, b)
    for a, b in zip(_vector(value["target"]), [0, .9, 0]):
        _near(a, b)
    for field, expected_number in (("size", 7.5), ("near", .05), ("far", 50)):
        _near(value[field], expected_number, .0001)
    q = _vector(value["rotation_xyzw"], 4)
    _near(sum(v * v for v in q), 1, .0001, "OBS_CAMERA_ROTATION")
    x, y, z, w = q
    forward = [-2 * (x*z + w*y), -2 * (y*z - w*x), -(1 - 2*(x*x + y*y))]
    target = [b-a for a, b in zip(value["position"], value["target"])]
    length = math.sqrt(sum(v*v for v in target))
    _need(sum(a*b/length for a, b in zip(forward, target)) >= math.cos(math.radians(.1)), "OBS_CAMERA_DIRECTION")


def _state(value, speed):
    _fields(value, _STATE)
    _need(value["phase"] in ("MENU", "PLAY", "PAUSED", "QUITTING"), "OBS_PHASE")
    for key in ("sim_tick", "emote_count", "prop_spin_tick", "prop_count"):
        _need(_int(value[key], 0, 600), "OBS_STATE_COUNTER")
    _need(_int(value["ui_tick"], 0, MAX_NATIVE_FRAMES + 600) and _int(value["emote_remaining"], 0, 90), "OBS_STATE_COUNTER")
    _near(value["move_speed"], speed, .000001, "OBS_CONFIG_SPEED")
    for key in ("body_position", "body_velocity", "avatar_position", "prop_rotation", "prop_position"):
        _vector(value[key])
    for key in ("outfit_visible", "prop_active", "tree_paused"):
        _need(type(value[key]) is bool, "OBS_STATE_BOOL")
    _need(value["tree_paused"] is (value["phase"] == "PAUSED"), "OBS_PAUSED_PHASE")
    _fields(value["animation"], {"clip", "position"})
    _need(value["animation"]["clip"] in ("idle", "walk") and _number(value["animation"]["position"])
          and 0 <= value["animation"]["position"] <= 1.001, "OBS_ANIMATION")
    _need(value["emote_bone"] == "bn_upperarm_r" and value["focus"] in ("", "StartButton", "QuitButton"), "OBS_STATE_TARGET")
    _near(sum(v*v for v in _vector(value["emote_pose_xyzw"], 4)), 1, .0001, "OBS_POSE_ROTATION")
    hit = value["last_prop_hit"]
    _need(type(hit) is dict, "OBS_PROP_HIT")
    if hit:
        _fields(hit, {"distance_m", "hit", "matched_prop", "collider", "position"})
        _need(_number(hit["distance_m"]) and 0 <= hit["distance_m"] <= 2.5 and hit["hit"] is True
              and hit["matched_prop"] is True and hit["collider"] == "prp_fixture_crate_collider_body", "OBS_PROP_HIT")
        _vector(hit["position"])
    _camera(value["camera"])
    return value


def _snapshot(row, digest_field, speed, adjacent=None):
    _need(row["hash_domain"] == "native-json-utf8" and type(row["state_json"]) is str, "OBS_SNAPSHOT_DOMAIN")
    raw = row["state_json"].encode("utf-8")
    _need(_sha(raw) == row[digest_field], "OBS_SNAPSHOT_HASH")
    state = _state(_strict(raw, 16384), speed)
    if adjacent is not None:
        _state(adjacent, speed)
        _need(state == adjacent, "OBS_SNAPSHOT_VALUE")
    return state


def _decode_capture_png(raw):
    # Godot's screenshot encoder adds one sRGB intent=0 chunk immediately after
    # IHDR. Validate that exact bounded extension without widening GT05's asset
    # decoder profile. Original file bytes/hash remain the capture identity;
    # removing color metadata only in memory preserves all encoded sample data.
    view = raw
    if raw[37:41] == b"sRGB":
        _need(len(raw) >= 46 and raw[:8] == b"\x89PNG\r\n\x1a\n"
              and raw[8:16] == b"\0\0\0\rIHDR" and raw[33:37] == b"\0\0\0\1"
              and raw[41] == 0 and struct.unpack(">I", raw[42:46])[0] == zlib.crc32(raw[37:42]) & 0xffffffff,
              "OBS_PNG_SRGB")
        view = raw[:33] + raw[46:]
    try:
        return decode_png(view)
    except PNGRejected:
        raise ObservationRejected("OBS_PNG_DECODE") from None


def _physics_equal(a, b):
    # Render/UI frames can advance after the last physics observation. Focus may
    # change as a disabled button relinquishes focus during GUI processing.
    return {k: v for k, v in a.items() if k not in ("ui_tick", "focus")} == {
        k: v for k, v in b.items() if k not in ("ui_tick", "focus")}


def _process_context(process, native):
    _fields(process, {"identity", "samples", "errors", "started_utc_ms", "ended_utc_ms", "host_start_mono_us", "host_end_mono_us"})
    _fields(process["identity"], {"pid", "process_start"})
    _need(process["errors"] == [] and _int(process["identity"]["pid"], 1, 0xffffffff)
          and process["identity"]["pid"] == native["pid"] and type(process["identity"]["process_start"]) is str
          and re.fullmatch(r"windows:[1-9][0-9]{0,19}", process["identity"]["process_start"]), "OBS_PROCESS_IDENTITY")
    for key in ("started_utc_ms", "ended_utc_ms", "host_start_mono_us", "host_end_mono_us"):
        _need(_int(process[key], 1), "OBS_HOST_CLOCK")
    _need(0 < process["ended_utc_ms"] - process["started_utc_ms"] <= 25000
          and 0 < process["host_end_mono_us"] - process["host_start_mono_us"] <= 25000000, "OBS_HOST_INTERVAL")
    rows = process["samples"]
    _need(type(rows) is list and 1 <= len(rows) <= 1000, "OBS_PROCESS_SAMPLES")
    previous = process["host_start_mono_us"] - 1
    handles = set()
    for row in rows:
        _fields(row, {"host_mono_us", "rss_bytes", "visible_window_handles"})
        _need(_int(row["host_mono_us"]) and previous < row["host_mono_us"] <= process["host_end_mono_us"]
              and _int(row["rss_bytes"], 1, 1 << 43), "OBS_PROCESS_SAMPLE")
        previous = row["host_mono_us"]
        values = row["visible_window_handles"]
        _need(type(values) is list and len(values) <= 64 and all(type(v) is str and re.fullmatch(r"[1-9][0-9]{0,19}", v) for v in values)
              and len(set(values)) == len(values), "OBS_WINDOW_HANDLES")
        handles.update(values)
    _need(type(native["native_window_handle"]) is str and native["native_window_handle"] in handles, "OBS_NATIVE_WINDOW")


def _utc(value, process):
    _need(_number(value) and process["started_utc_ms"] - UTC_TOLERANCE_MS <= value * 1000
          <= process["ended_utc_ms"] + UTC_TOLERANCE_MS, "OBS_UTC_INTERVAL")


def _counters(value):
    _fields(value, _COUNTERS)
    _need(all(_int(value[k], 1, (1 << 40)) for k in _COUNTERS), "OBS_RENDER_COUNTERS")


def _native(native, process):
    _fields(native, _NATIVE)
    _need(_int(native["pid"], 1, 0xffffffff) and _int(native["window_id"], 0, 1000)
          and _int(native["started_monotonic_us"], 1) and native["physics_hz"] == 60
          and type(native["physics_hz"]) is int and native["process_role"] == "play"
          and native["editor_hint"] is False and native["main_thread"] is True
          and native["display_server"] == "Windows", "OBS_NATIVE_CONTEXT")
    engine = native["engine"]
    _need(type(engine) is dict and all(type(engine.get(k)) is int and engine[k] == v for k, v in (("major", 4), ("minor", 7), ("patch", 2)))
          and engine.get("status") == "stable" and type(engine.get("hash")) is str and engine["hash"].startswith("ed1daf0bf"), "OBS_ENGINE_PIN")
    config = _fields(native["configuration"], _CONFIGURATION)
    _need(config["viewport_resolution"] == [960, 640] and all(type(v) is int for v in config["viewport_resolution"])
          and _int(config["vsync_mode"], 0, 3) and _int(config["max_fps"], 60, 60)
          and _int(config["physics_hz"], 60, 60) and _number(config["time_scale"]) and config["time_scale"] == 1
          and type(config["debug_build"]) is bool and config["fixed_fps_flag"] is False, "OBS_CONFIGURATION")
    for label in ("rendering_method", "rendering_driver", "delta_smoothing"):
        supported = config[label + "_supported"]
        _need(type(supported) is bool and ((config[label] is None and not supported)
              or (supported and (type(config[label]) is bool if label == "delta_smoothing" else type(config[label]) is str and 0 < len(config[label]) <= 128))), "OBS_CONFIGURATION_SUPPORT")
    _process_context(process, native)
    _utc(native["started_unix"], process)


def _semantics(report, trace, speed):
    observations = report["observations"]
    _need(type(observations) is list and len(observations) == len(trace.value["frames"]), "OBS_TRACE_COMPLETENESS")
    events = [{"event_index": index, **row} for index, row in enumerate(
        {"trace_tick": frame["tick"], "key": key, "pressed": pressed,
         "window_id": report["native"]["window_id"], "reason": "trace"}
        for frame in trace.value["frames"] for edge, pressed in (("released", False), ("pressed", True)) for key in frame[edge])]
    _need(report["input_events"] == events and all(type(r.get("pressed")) is bool
          and all(_int(r[k]) for k in ("event_index", "trace_tick", "window_id"))
          for r in report["input_events"]), "OBS_INPUT_EVENTS")
    callbacks = report["callbacks"]
    _need(type(callbacks) is list and len(callbacks) == len(events) + 1, "OBS_CALLBACK_COUNT")
    callback_events, transitions, phases, actions = [], [], {}, {}
    phase, last_tick, start_count = "MENU", -1, 0
    for callback in callbacks:
        tick = callback.get("trace_tick") if type(callback) is dict else None
        _need(_int(tick, 0, len(observations)-1) and tick >= last_tick, "OBS_CALLBACK_ORDER")
        last_tick = tick
        _need(callback.get("phase_before") == phase, "OBS_CALLBACK_PHASE")
        destination = trigger = None
        if callback.get("callback") == "_input":
            _fields(callback, {"callback", "trace_tick", "key", "pressed", "phase_before", "window_id"})
            index = len(callback_events)
            _need(index < len(events) and all(callback[k] == events[index][k] for k in ("trace_tick", "key", "pressed", "window_id"))
                  and type(callback["pressed"]) is bool and _int(callback["window_id"]), "OBS_CALLBACK_EVENT")
            callback_events.append(callback)
            if callback["pressed"]:
                key = callback["key"]
                actions.setdefault(tick, []).append((key, phase))
                if key == "Q":
                    destination, trigger = "QUITTING", "key.Q"
                elif key == "ESCAPE" and phase in ("PLAY", "PAUSED"):
                    destination, trigger = ("PAUSED" if phase == "PLAY" else "PLAY"), "key.ESCAPE"
        else:
            _fields(callback, {"callback", "trace_tick", "phase_before"})
            _need(callback["callback"] == "StartButton.pressed" and phase == "MENU"
                  and any(e["trace_tick"] == tick and e["key"] == "ENTER" for e in events), "OBS_MENU_CALLBACK")
            start_count += 1
            destination, trigger = "PLAY", "button.Start"
        if destination:
            transitions.append({"trace_tick": tick, "from": phase, "to": destination, "trigger": trigger})
            phase = destination
            phases[tick] = phase
    _need(len(callback_events) == len(events) and start_count == 1 and report["transitions"] == transitions
          and all(_int(row["trace_tick"]) for row in report["transitions"])
          and [(r["from"], r["to"]) for r in transitions] == [("MENU", "PLAY"), ("PLAY", "PAUSED"), ("PAUSED", "PLAY"), ("PLAY", "QUITTING")], "OBS_TRANSITIONS")
    states, physics_frame = [], -1
    phase, sim, outfit, emotes, remaining, prop, spins, bookmark = "MENU", 0, True, 0, 0, False, 0, 0
    x = 0.0
    for tick, row in enumerate(observations):
        _fields(row, {"trace_tick", "state", "state_json", "snapshot_sha256", "hash_domain", "held_keys", "physics_frame"})
        _need(type(row["trace_tick"]) is int and row["trace_tick"] == tick and row["held_keys"] == list(trace.value["frames"][tick]["held"])
              and _int(row["physics_frame"], 1) and row["physics_frame"] > physics_frame, "OBS_OBSERVATION_ORDER")
        physics_frame = row["physics_frame"]
        state = _snapshot(row, "snapshot_sha256", speed, row["state"])
        phase = phases.get(tick, phase)
        for key, callback_phase in actions.get(tick, []):
            if key == "O" and callback_phase == "PLAY": outfit = not outfit
            if key == "M" and callback_phase == "PLAY": emotes += 1; remaining = 90
            if key == "E" and callback_phase == "PLAY": prop = not prop
            if key == "C" and callback_phase != "QUITTING": bookmark = 1 - bookmark
        if phase == "PLAY":
            sim += 1
            if "RIGHT" in row["held_keys"]: x += speed / 60
            remaining = max(0, remaining - 1)
            if prop: spins += 1
        _need(state["phase"] == phase and state["sim_tick"] == sim, "OBS_POST_DESTINATION")
        _near(state["body_position"][0], x, .001, "OBS_MOVEMENT")
        _near(state["body_position"][2], 0, .001, "OBS_MOVEMENT")
        for axis in (0, 2):
            _near(state["avatar_position"][axis], state["body_position"][axis], .001, "OBS_AVATAR_FOLLOWS_BODY")
        if phase != "MENU":
            _near(state["body_position"][1] - state["avatar_position"][1], .925, .001, "OBS_AVATAR_FOLLOWS_BODY")
        _need(state["outfit_visible"] is outfit and state["emote_count"] == emotes and state["emote_remaining"] == remaining
              and state["prop_active"] is prop and state["prop_count"] == int(prop)
              and state["prop_spin_tick"] == spins and bool(state["last_prop_hit"]) is prop
              and state["camera"]["bookmark"] == bookmark, "OBS_ACTION_POSTCONDITION")
        if states:
            _need(state["ui_tick"] >= states[-1]["ui_tick"], "OBS_UI_CLOCK")
        if phase == "PAUSED":
            for field in ("sim_tick", "body_position", "body_velocity", "avatar_position", "animation", "emote_pose_xyzw", "emote_remaining", "prop_rotation", "prop_spin_tick"):
                _need(state[field] == states[-1][field], "OBS_PAUSE_FROZEN")
        if phase == "PLAY":
            expected_clip = "walk" if "RIGHT" in row["held_keys"] and speed > 0 else "idle"
            _need(state["animation"]["clip"] == expected_clip, "OBS_ANIMATION_INPUT")
            _near(state["body_velocity"][0], speed if "RIGHT" in row["held_keys"] else 0, .001, "OBS_MOVEMENT_VELOCITY")
            if states and state["animation"]["clip"] == states[-1]["animation"]["clip"]:
                difference = state["animation"]["position"] - states[-1]["animation"]["position"] - 1/60
                _need(min(abs(difference), abs(difference + 1), abs(difference - 1)) <= .001, "OBS_ANIMATION_ADVANCE")
        states.append(state)
    _need(states[0]["phase"] == "MENU" and states[0]["focus"] == "StartButton", "OBS_MENU_FOCUS")
    _need(states[175]["ui_tick"] > states[165]["ui_tick"] and states[210]["sim_tick"] > states[199]["sim_tick"], "OBS_PAUSE_RESUME_CLOCK")
    _need(states[125]["emote_pose_xyzw"] != states[119]["emote_pose_xyzw"] and states[125]["prop_rotation"] != states[79]["prop_rotation"], "OBS_ANIMATED_INTERACTION")
    final = _fields(report["final"], {"phase", "trace_ticks", "sim_tick", "held_keys", "pending_captures", "state"})
    _state(final["state"], speed)
    _need(final["phase"] == "QUITTING" and _int(final["trace_ticks"], len(states), len(states))
          and type(final["sim_tick"]) is int and final["sim_tick"] == states[-1]["sim_tick"]
          and final["held_keys"] == [] and _int(final["pending_captures"], 0, 0)
          and _physics_equal(final["state"], states[-1]) and final["state"]["ui_tick"] >= states[-1]["ui_tick"], "OBS_FINAL_DRAIN")
    return states


def validate_observation(report_raw: bytes, *, trace: ValidatedTrace, binding: dict,
                         config_speed: float, project: Path, process: dict) -> dict:
    """Return checked completion/postconditions; reject malformed or unbound proof.

    Only the current deterministic 360-frame fixture is supported. A correctly
    observed speed=0 run returns complete=True, all_postconditions=False and
    movement_fault_observed=True. A speed=3 run can satisfy postconditions, but
    this function never claims that a managed editor repair occurred.
    """
    try:
        _need(type(trace) is ValidatedTrace, "OBS_VALIDATED_TRACE")
        checked = validate_trace(trace.raw)
        _need(checked.raw_sha256 == trace.raw_sha256 and checked.value == trace.value, "OBS_TRACE_OBJECT")
        _need(checked.value == default_trace(checked.value["seed"]).value, "OBS_TRACE_PROFILE")
        _need(type(config_speed) in (int, float) and config_speed in (0.0, 3.0), "OBS_SPEED_PROFILE")
        _fields(binding, _BIND)
        _need(all(type(binding[k]) is str and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", binding[k]) for k in ("run_id", "command_id", "runtime_instance_id"))
              and all(type(binding[k]) is str and _HASH.fullmatch(binding[k]) for k in _BIND if k.endswith("sha256"))
              and _int(binding["generation"], 1, 2147483647) and binding["trace_sha256"] == trace.raw_sha256, "OBS_BINDING")
        project = Path(project)
        _need(project.is_absolute() and ".." not in project.parts, "OBS_PROJECT_PATH")
        report = _fields(_strict(report_raw), _REPORT)
        _need(report["schema_id"] == "hh-studio.play-observation" and report["schema_version"] == "1.0.0"
              and _binding_matches(report["binding"], binding) and _int(report["fps"], 60, 60)
              and _int(report["seed"], 0, (1 << 32)-1) and report["seed"] == trace.value["seed"], "OBS_REPORT_BINDING")
        _need(report["completed"] is True and report["public_ack"] is False and report["formal_acceptance"] is False, "OBS_COMPLETION_SCOPE")
        _fields(report["inputs"], set(_INPUTS))
        files = {key: _read_regular(project, name, cap) for key, (name, cap) in _INPUTS.items()}
        _need(report["inputs"] == {k: _sha(v) for k, v in files.items()} and files["trace_sha256"] == trace.raw
              and _binding_matches(_strict(files["run_sha256"], 16384), binding)
              and _sha(files["glb_sha256"]) == binding["glb_sha256"], "OBS_INPUT_HASH")
        expected_config = ("extends Node3D\n@export var fixture_value: int = 1\n"
                           "@export var move_speed: float = " + str(float(config_speed)) + "\n").encode()
        _need(files["config_sha256"] == expected_config, "OBS_CONFIG_PROFILE")
        _native(report["native"], process)
        states = _semantics(report, trace, config_speed)
        native = report["native"]
        frame_rows = report["native_frames"]
        _need(type(frame_rows) is list and 1 <= len(frame_rows) <= MAX_NATIVE_FRAMES
              and _int(report["frame_start_monotonic_us"], native["started_monotonic_us"])
              and _int(report["frame_end_monotonic_us"], report["frame_start_monotonic_us"] + 1), "OBS_NATIVE_FRAMES")
        previous_us, previous_process, previous_render, previous_tick = report["frame_start_monotonic_us"], -1, -1, -1
        by_frame = {}
        start_index = report["perf_measurement_start_frame_index"]
        _need(_int(start_index, 2, len(frame_rows)-1), "OBS_MEASUREMENT_START")
        first_qualified = None
        for index, frame in enumerate(frame_rows):
            _fields(frame, _FRAME)
            _need(_int(frame["monotonic_us"], previous_us + 1) and _int(frame["frame_time_us"], 1)
                  and frame["frame_time_us"] == frame["monotonic_us"] - previous_us
                  and _int(frame["process_frame"], previous_process + 1) and _int(frame["rendered_frame"], previous_render + 1)
                  and _int(frame["trace_tick"], previous_tick, len(states)-1) and frame["frame_hook"] == "frame_post_draw", "OBS_NATIVE_FRAME_ORDER")
            state = _snapshot(frame, "state_snapshot_sha256", config_speed)
            _need(all(frame[k] == state[k] and type(frame[k]) is type(state[k]) for k in ("phase", "sim_tick", "ui_tick")), "OBS_NATIVE_FRAME_STATE")
            _need((frame["trace_tick"] == -1 and state["phase"] == "MENU" and state["sim_tick"] == 0)
                  or (frame["trace_tick"] >= 0 and _physics_equal(state, states[frame["trace_tick"]])
                      and state["ui_tick"] >= states[frame["trace_tick"]]["ui_tick"]), "OBS_RENDER_PHYSICS_BINDING")
            qualified = frame["rendered_frame"] >= 2 and index >= 1
            _fields(frame["counter_readiness"], {"qualified", "reason"})
            _need(frame["counter_readiness"]["qualified"] is qualified
                  and frame["counter_readiness"]["reason"] == ("qualified" if qualified else "startup_not_qualified")
                  and frame["measurement_eligible"] is (index >= start_index), "OBS_COUNTER_READINESS")
            if qualified:
                first_qualified = index if first_qualified is None else first_qualified
                _counters(frame["counters"])
                _need(frame["raw_counter_readback"] is None, "OBS_COUNTER_READINESS")
            else:
                _fields(frame["counters"], _COUNTERS)
                _fields(frame["raw_counter_readback"], _COUNTERS)
                _need(all(v is None for v in frame["counters"].values())
                      and all(_int(v, 0, 1 << 40) for v in frame["raw_counter_readback"].values()), "OBS_COUNTER_READINESS")
            _need(index >= start_index or frame["trace_tick"] == -1, "OBS_TRACE_STARTED_EARLY")
            by_frame[frame["monotonic_us"]] = frame
            previous_us, previous_process, previous_render, previous_tick = (frame[k] for k in ("monotonic_us", "process_frame", "rendered_frame", "trace_tick"))
        _need(previous_us == report["frame_end_monotonic_us"] and previous_us - native["started_monotonic_us"] <= 14000000, "OBS_NATIVE_INTERVAL")
        anchor = frame_rows[start_index - 1]
        start = _fields(report["trace_start"], {"monotonic_us", "process_frame", "rendered_frame", "ready_frame_count", "rendered"})
        _need(first_qualified == start_index - 1 and start["rendered"] is True
              and _int(start["ready_frame_count"], start_index, start_index)
              and _int(start["rendered_frame"], 2)
              and all(_int(start[k]) and start[k] == anchor[k] for k in ("monotonic_us", "process_frame", "rendered_frame"))
              and _int(report["perf_measurement_start_monotonic_us"], anchor["monotonic_us"], anchor["monotonic_us"]), "OBS_TRACE_READINESS")
        _fields(report["counter_definitions"], _COUNTERS)
        _need(all(type(v) is str and 1 <= len(v) <= 256 for v in report["counter_definitions"].values()), "OBS_COUNTER_DEFINITIONS")
        requests = {c["label"]: c["tick"] for c in trace.value["captures"]}
        _fields(report["captures"], set(requests), "OBS_CAPTURE_SET")
        capture_hashes = {}
        phases = {"menu": "MENU", "moved": "PLAY", "interact": "PLAY", "paused_a": "PAUSED", "paused_b": "PAUSED", "resumed": "PLAY", "camera": "PLAY"}
        for label, tick in requests.items():
            cap = _fields(report["captures"][label], _CAPTURE)
            _need(cap["label"] == label and _int(cap["requested_tick"], tick, tick)
                  and _int(cap["observed_tick"], tick, len(states)-1) and _binding_matches({k: cap[k] for k in _BIND}, binding)
                  and all(cap[k] == native[k] and type(cap[k]) is type(native[k]) for k in ("pid", "window_id", "native_window_handle")), "OBS_CAPTURE_BINDING")
            _need(_int(cap["requested_monotonic_us"], start["monotonic_us"] + 1) and _int(cap["monotonic_us"], cap["requested_monotonic_us"])
                  and _int(cap["minimum_rendered_frame"], start["rendered_frame"]) and _int(cap["minimum_process_frame"], start["process_frame"])
                  and _int(cap["rendered_frame"], cap["minimum_rendered_frame"] + 1)
                  and _int(cap["process_frame"], cap["minimum_process_frame"] + 1), "OBS_CAPTURE_FENCE")
            frame = by_frame.get(cap["monotonic_us"])
            _need(frame is not None and cap["observed_tick"] == frame["trace_tick"]
                  and all(cap[k] == frame[k] and type(cap[k]) is type(frame[k]) for k in ("rendered_frame", "process_frame", "state_json", "state_snapshot_sha256", "hash_domain", "sim_tick", "ui_tick", "phase", "counters")), "OBS_CAPTURE_FRAME")
            state = _snapshot(cap, "state_snapshot_sha256", config_speed)
            _camera(cap["camera"])
            _counters(cap["counters"])
            _need(cap["camera"] == state["camera"] and cap["phase"] == phases[label], "OBS_CAPTURE_POSTCONDITION")
            _need(type(cap["requested_camera_json"]) is str, "OBS_CAPTURE_REQUEST_CAMERA")
            camera_raw = cap["requested_camera_json"].encode("utf-8")
            requested_camera = _strict(camera_raw, 4096)
            _camera(requested_camera)
            _need(_sha(camera_raw) == cap["requested_camera_sha256"]
                  and requested_camera == states[tick]["camera"] == cap["camera"]
                  and cap["requested_phase"] == states[tick]["phase"] == cap["phase"], "OBS_CAPTURE_REQUEST_CAMERA")
            _utc(cap["captured_at_unix"], process)
            _near(cap["captured_at_unix"] - native["started_unix"], (cap["monotonic_us"] - native["started_monotonic_us"]) / 1000000, UTC_TOLERANCE_MS / 1000, "OBS_CAPTURE_CLOCK")
            png = _read_regular(project, "out/" + label + ".png", MAX_PNG_BYTES)
            _need(_int(cap["size_bytes"], 1, MAX_PNG_BYTES) and cap["size_bytes"] == len(png) and cap["sha256"] == _sha(png)
                  and _int(cap["width"], 960, 960) and _int(cap["height"], 640, 640), "OBS_PNG_BINDING")
            decoded = _decode_capture_png(png)
            _need(decoded.width == 960 and decoded.height == 640, "OBS_PNG_DIMENSIONS")
            capture_hashes[label] = cap["sha256"]
        fault = config_speed == 0.0
        return {"complete": True, "all_postconditions": not fault, "movement_fault_observed": fault,
                "report_sha256": _sha(report_raw), "trace_sha256": trace.raw_sha256, "capture_hashes": capture_hashes,
                "semantic_checks": {"input_callbacks": True, "menu_start": True, "movement_matches_config": True,
                    "movement_positive": not fault, "interactions": True, "pause_frozen_ui_advances": True,
                    "resume": True, "camera": True, "quit_drained": True, "fresh_captures": True},
                "expected_movement_m": 30 * config_speed / 60,
                "observed_movement_m": states[61]["body_position"][0] - states[29]["body_position"][0],
                "native_frames": len(frame_rows), "formal_acceptance": False, "managed_repair_proven": False}
    except ObservationRejected:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, RecursionError):
        raise ObservationRejected("OBS_SCHEMA") from None
