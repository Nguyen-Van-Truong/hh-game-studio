extends Node
## Fixed trace adapter. Input goes through the same callbacks as keyboard input.
## No eval, node-call request, arbitrary output path or runtime property setter.

const OBSERVER_SCRIPT: Script = preload("res://observe/post_observer.gd")
const CAPTURE_SCRIPT: Script = preload("res://observe/capture.gd")
const KEYS: Dictionary = {"ENTER": KEY_ENTER, "TAB": KEY_TAB, "RIGHT": KEY_RIGHT,
	"LEFT": KEY_LEFT, "UP": KEY_UP, "DOWN": KEY_DOWN, "E": KEY_E, "O": KEY_O,
	"M": KEY_M, "ESCAPE": KEY_ESCAPE, "C": KEY_C, "Q": KEY_Q}
const RUN_FIELDS: Array[String] = ["run_id", "command_id", "runtime_instance_id", "source_closure_sha256",
	"runtime_snapshot_sha256", "trace_sha256", "glb_sha256", "generation"]
const INPUT_FILES: Dictionary = {"trace_sha256": "res://input/trace.json", "glb_sha256": "res://input/fixture.glb",
	"config_sha256": "res://config/fixture_actor.gd", "producer_report_sha256": "res://input/producer-report.json",
	"asset_manifest_sha256": "res://input/manifest.json", "run_sha256": "res://input/run.json"}
const MAX_REPORT_BYTES: int = 8388608

var fixture: Node3D
var run: Dictionary = {}
var trace: Dictionary = {}
var input_hashes: Dictionary = {}
var native: Dictionary = {}
var trace_start: Dictionary = {}
var trace_seed: int = 0
var current_tick: int = -1
var next_tick: int = 0
var last_observed_tick: int = -1
var held_keys: Array[String] = []
var observations: Array[Dictionary] = []
var input_events: Array[Dictionary] = []
var capture_node: Node
var observer: Node
var failed: bool = false
var active: bool = false
var finished: bool = false
var complete_scheduled: bool = false
var started_us: int = 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	process_physics_priority = -100
	set_physics_process(false)
	set_process(false)


func need(value: bool, code: String) -> bool:
	if not value:
		fail(code)
	return value


func fail(code: String) -> void:
	if failed or finished:
		return
	failed = true
	active = false
	set_physics_process(false)
	var input_readback: Dictionary = {}
	for key: String in KEYS:
		input_readback[key] = {"key": Input.is_key_pressed(int(KEYS[key]) as Key),
			"physical": Input.is_physical_key_pressed(int(KEYS[key]) as Key)}
	var failure_path: String = "res://out/failure.json"
	if not FileAccess.file_exists(failure_path):
		var failure_file: FileAccess = FileAccess.open(failure_path, FileAccess.WRITE)
		if failure_file != null:
			failure_file.store_string(JSON.stringify({"schema_id": "hh-studio.play-failure", "schema_version": "1.0.0",
				"code": code, "trace_tick": current_tick, "pid": OS.get_process_id(), "binding": run,
				"expected_held": held_keys, "input_readback": input_readback, "completed": false}) + "\n")
			failure_file.close()
	_release_all("failure")
	push_error(code)
	get_tree().quit(26)


func read_object(path: String, cap: int) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if not need(file != null, "GT06_INPUT_OPEN"):
		return {}
	if not need(file.get_length() > 0 and file.get_length() <= cap, "GT06_INPUT_BYTE_CAP"):
		file.close()
		return {}
	var raw: String = file.get_as_text()
	file.close()
	var parser: JSON = JSON.new()
	if not need(parser.parse(raw) == OK and parser.data is Dictionary, "GT06_INPUT_JSON"):
		return {}
	return parser.data as Dictionary


func _whole(value: Variant, low: int, high: int) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == float(int(value)) \
		and float(value) >= float(low) and float(value) <= float(high)


func _hash(value: Variant) -> bool:
	if not value is String or String(value).length() != 64:
		return false
	for character: String in String(value):
		if not character in "0123456789abcdef":
			return false
	return true


func _fields(value: Dictionary, expected: Array[String]) -> bool:
	if value.size() != expected.size():
		return false
	for key: String in expected:
		if not value.has(key):
			return false
	return true


func prepare(target: Node3D) -> bool:
	fixture = target
	run = read_object("res://input/run.json", 16384)
	trace = read_object("res://input/trace.json", 262144)
	if failed or not need(_fields(run, RUN_FIELDS), "GT06_RUN_FIELDS"):
		return false
	for key: String in ["run_id", "command_id", "runtime_instance_id"]:
		if not need(run[key] is String and String(run[key]).length() > 0 and String(run[key]).length() <= 128, "GT06_RUN_ID"):
			return false
	for key: String in ["source_closure_sha256", "runtime_snapshot_sha256", "trace_sha256", "glb_sha256"]:
		if not need(_hash(run[key]), "GT06_RUN_HASH"):
			return false
	if not need(_whole(run["generation"], 1, 2147483647), "GT06_RUN_GENERATION"):
		return false
	for key: String in INPUT_FILES:
		input_hashes[key] = FileAccess.get_sha256(INPUT_FILES[key])
		if not need(_hash(input_hashes[key]), "GT06_INPUT_HASH"):
			return false
	if not need(input_hashes["trace_sha256"] == run["trace_sha256"] and input_hashes["glb_sha256"] == run["glb_sha256"], "GT06_INPUT_BINDING"):
		return false
	if not _validate_trace():
		return false
	var version: Dictionary = Engine.get_version_info()
	if not need(version["major"] == 4 and version["minor"] == 7 and version["patch"] == 2
			and version["status"] == "stable" and String(version["hash"]).begins_with("ed1daf0bf"), "GT06_ENGINE_PIN"):
		return false
	var window_id: int = fixture.get_window().get_window_id()
	var native_handle: int = 0
	if DisplayServer.get_name() != "headless":
		native_handle = DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE, window_id)
		if not need(DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, window_id), "GT06_TRACE_WINDOW_FOCUS_POLICY"):
			return false
	if not need(trace["captures"].is_empty() or (DisplayServer.get_name() != "headless" and native_handle != 0), "GT06_REAL_WINDOW_REQUIRED"):
		return false
	started_us = Time.get_ticks_usec()
	native = {"pid": OS.get_process_id(), "window_id": window_id, "native_window_handle": str(native_handle),
		"engine": version, "display_server": DisplayServer.get_name(), "started_unix": Time.get_unix_time_from_system(),
		"started_monotonic_us": started_us, "physics_hz": Engine.physics_ticks_per_second,
		"process_role": "play", "editor_hint": Engine.is_editor_hint(), "main_thread": Thread.is_main_thread(),
		"configuration": _configuration(window_id)}
	return need(not Engine.is_editor_hint() and Thread.is_main_thread(), "GT06_PLAY_MAIN_THREAD")


func _configuration(window_id: int) -> Dictionary:
	var method_supported: bool = RenderingServer.has_method("get_current_rendering_method")
	var driver_supported: bool = RenderingServer.has_method("get_current_rendering_driver_name")
	var smoothing_supported: bool = OS.has_method("is_delta_smoothing_enabled")
	var fixed_fps_flag: bool = false
	for argument: String in OS.get_cmdline_args():
		if argument == "--fixed-fps" or argument.begins_with("--fixed-fps="):
			fixed_fps_flag = true
	var size: Vector2 = fixture.get_viewport().get_visible_rect().size
	return {"rendering_method": RenderingServer.call("get_current_rendering_method") if method_supported else null,
		"rendering_method_supported": method_supported,
		"rendering_driver": RenderingServer.call("get_current_rendering_driver_name") if driver_supported else null,
		"rendering_driver_supported": driver_supported, "viewport_resolution": [int(size.x), int(size.y)],
		"vsync_mode": DisplayServer.window_get_vsync_mode(window_id) if DisplayServer.get_name() != "headless" else null,
		"max_fps": Engine.max_fps, "physics_hz": Engine.physics_ticks_per_second, "time_scale": Engine.time_scale,
		"debug_build": OS.is_debug_build(), "delta_smoothing_supported": smoothing_supported,
		"delta_smoothing": OS.call("is_delta_smoothing_enabled") if smoothing_supported else null,
		"fixed_fps_flag": fixed_fps_flag}


func _key_array(value: Variant) -> bool:
	if not value is Array or value.size() > KEYS.size():
		return false
	var seen: Dictionary = {}
	for key: Variant in value:
		if not key is String or not KEYS.has(key) or seen.has(key):
			return false
		seen[key] = true
	return true


func _validate_trace() -> bool:
	if not need(_fields(trace, ["schema_id", "schema_version", "fps", "seed", "frames", "captures"])
			and trace["schema_id"] == "hh-studio.input-trace" and trace["schema_version"] == "1.0.0"
			and _whole(trace["fps"], 60, 60) and _whole(trace["seed"], 0, 4294967295)
			and trace["frames"] is Array and trace["frames"].size() > 0 and trace["frames"].size() <= 600
			and trace["captures"] is Array and trace["captures"].size() <= 16, "GT06_TRACE_SCHEMA"):
		return false
	trace_seed = int(trace["seed"])
	var previous: Dictionary = {}
	for index: int in range(trace["frames"].size()):
		var value: Variant = trace["frames"][index]
		if not need(value is Dictionary, "GT06_TRACE_FRAME_TYPE"):
			return false
		var row: Dictionary = value
		if not need(_fields(row, ["tick", "pressed", "held", "released"]) and _whole(row["tick"], index, index)
				and _key_array(row["pressed"]) and _key_array(row["held"]) and _key_array(row["released"]), "GT06_TRACE_FRAME"):
			return false
		for key: String in row["released"]:
			if not need(previous.has(key) and not key in row["pressed"], "GT06_TRACE_RELEASE"):
				return false
			previous.erase(key)
		for key: String in row["pressed"]:
			if not need(not previous.has(key), "GT06_TRACE_PRESS"):
				return false
			previous[key] = true
		if not need(previous.size() == row["held"].size(), "GT06_TRACE_HELD"):
			return false
		for key: String in row["held"]:
			if not need(previous.has(key), "GT06_TRACE_HELD"):
				return false
	if not need(previous.is_empty(), "GT06_TRACE_UNRELEASED"):
		return false
	var labels: Dictionary = {}
	var pattern: RegEx = RegEx.new()
	pattern.compile("^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
	var device_pattern: RegEx = RegEx.new()
	device_pattern.compile("^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$")
	for value: Variant in trace["captures"]:
		if not need(value is Dictionary, "GT06_CAPTURE_REQUEST"):
			return false
		var capture: Dictionary = value
		if not need(_fields(capture, ["tick", "label"]) and _whole(capture["tick"], 0, trace["frames"].size() - 1)
				and capture["label"] is String and String(capture["label"]).length() <= 48
				and pattern.search(capture["label"]) != null and device_pattern.search(capture["label"]) == null
				and not labels.has(capture["label"]), "GT06_CAPTURE_REQUEST"):
			return false
		labels[capture["label"]] = true
	return true


func begin() -> void:
	if failed:
		return
	capture_node = CAPTURE_SCRIPT.new() as Node
	capture_node.name = "FrameCapture"
	capture_node.set("bridge", self)
	capture_node.set("fixture", fixture)
	add_child(capture_node)
	observer = OBSERVER_SCRIPT.new() as Node
	observer.name = "AfterPhysicsObserver"
	observer.set("bridge", self)
	add_child(observer)
	# MENU and UI render before the authored 60 Hz trace clock is started.
	active = false
	set_physics_process(false)
	set_process(true)


func arm_trace(readiness: Dictionary) -> void:
	if failed or finished or not trace_start.is_empty():
		return
	var rendered: bool = bool(readiness.get("rendered", false))
	if not need(int(readiness.get("ready_frame_count", 0)) >= 2 and
			((rendered and int(readiness.get("rendered_frame", -1)) >= 2) or
			(not rendered and DisplayServer.get_name() == "headless" and trace["captures"].is_empty())), "GT06_TRACE_RENDER_READINESS"):
		return
	trace_start = readiness.duplicate(true)
	active = true
	set_physics_process(true)


func _process(_delta: float) -> void:
	if not finished and Time.get_ticks_usec() - started_us > 14000000:
		fail("GT06_RUNTIME_DEADLINE")
	if not active and not failed and not finished and next_tick == trace["frames"].size() \
			and capture_node != null and int(capture_node.call("pending_count")) == 0 and not complete_scheduled:
		complete_scheduled = true
		call_deferred("_complete")


func _physics_process(_delta: float) -> void:
	if not active or failed:
		return
	if next_tick >= trace["frames"].size():
		return
	current_tick = next_tick
	var row: Dictionary = trace["frames"][current_tick]
	for key: String in row["released"]:
		_emit_key(key, false, "trace")
	for key: String in row["pressed"]:
		_emit_key(key, true, "trace")
	held_keys.clear()
	for key: String in row["held"]:
		held_keys.append(key)
	# The pinned engine queues parse_input_event while input accumulation or
	# agile flushing is enabled. Explicitly dispatch this tick before the actor.
	Input.flush_buffered_events()


func _emit_key(key: String, pressed: bool, reason: String) -> void:
	var event: InputEventKey = InputEventKey.new()
	event.keycode = int(KEYS[key]) as Key
	event.physical_keycode = int(KEYS[key]) as Key
	event.pressed = pressed
	event.window_id = int(native.get("window_id", 0))
	event.echo = false
	input_events.append({"event_index": input_events.size(), "trace_tick": current_tick, "key": key,
		"pressed": pressed, "window_id": event.window_id, "reason": reason})
	Input.parse_input_event(event)


func _release_all(reason: String) -> void:
	var previous: Array[String] = held_keys.duplicate()
	held_keys.clear()
	for key: String in previous:
		_emit_key(key, false, reason)
	Input.flush_buffered_events()


func after_step() -> void:
	if not active or failed or current_tick < 0 or current_tick == last_observed_tick:
		return
	var row: Dictionary = trace["frames"][current_tick]
	for key: String in KEYS:
		if not need(Input.is_key_pressed(int(KEYS[key]) as Key) == (key in row["held"]), "GT06_INPUT_READBACK"):
			return
	var state: Dictionary = fixture.call("snapshot")
	var encoded: String = JSON.stringify(state)
	observations.append({"trace_tick": current_tick, "state": state, "state_json": encoded,
		"snapshot_sha256": encoded.sha256_text(), "hash_domain": "native-json-utf8",
		"held_keys": held_keys.duplicate(), "physics_frame": Engine.get_physics_frames()})
	last_observed_tick = current_tick
	for capture: Dictionary in trace["captures"]:
		if int(capture["tick"]) == current_tick:
			capture_node.call("enqueue", current_tick, String(capture["label"]))
	next_tick += 1
	if next_tick >= trace["frames"].size():
		active = false
		set_physics_process(false)


func inspect_target(stable_id: String, runtime_instance_id: String, generation: int) -> Dictionary:
	# Small read-only surface; resolve the current stable target on every request.
	if failed or finished or runtime_instance_id != run["runtime_instance_id"] or generation != int(run["generation"]):
		return {"ok": false, "code": "STALE_RUNTIME_CONTEXT"}
	if stable_id == "fixture":
		return {"ok": true, "state": fixture.call("snapshot"), "generation": generation}
	if stable_id == "review.camera" and fixture.get_node_or_null("ReviewCamera") is Camera3D:
		return {"ok": true, "state": fixture.call("camera_snapshot"), "generation": generation}
	return {"ok": false, "code": "UNSUPPORTED_STABLE_TARGET"}


func _complete() -> void:
	if failed or finished:
		return
	if not need(held_keys.is_empty() and observations.size() == trace["frames"].size(), "GT06_TRACE_COMPLETENESS"):
		return
	for key: String in INPUT_FILES:
		if not need(FileAccess.get_sha256(INPUT_FILES[key]) == input_hashes[key], "GT06_INPUT_CHANGED"):
			return
	var frame_report: Dictionary = capture_node.call("finish")
	if failed:
		return
	var final_state: Dictionary = fixture.call("snapshot")
	var report: Dictionary = {"schema_id": "hh-studio.play-observation", "schema_version": "1.0.0",
		"binding": run, "native": native, "inputs": input_hashes, "seed": trace_seed, "fps": 60, "trace_start": trace_start,
		"observations": observations, "input_events": input_events,
		"callbacks": fixture.get("callbacks"), "transitions": fixture.get("transitions"),
		"captures": frame_report["captures"], "native_frames": frame_report["native_frames"],
		"frame_start_monotonic_us": frame_report["frame_start_monotonic_us"],
		"frame_end_monotonic_us": frame_report["frame_end_monotonic_us"],
		"perf_measurement_start_monotonic_us": frame_report["perf_measurement_start_monotonic_us"],
		"perf_measurement_start_frame_index": frame_report["perf_measurement_start_frame_index"],
		"counter_definitions": frame_report["counter_definitions"],
		"final": {"phase": final_state["phase"], "trace_ticks": next_tick, "sim_tick": final_state["sim_tick"],
			"held_keys": held_keys, "pending_captures": 0, "state": final_state},
		"completed": true, "public_ack": false, "formal_acceptance": false}
	var path: String = "res://out/report.json"
	var encoded: String = JSON.stringify(report) + "\n"
	if not need(not FileAccess.file_exists(path) and encoded.to_utf8_buffer().size() <= MAX_REPORT_BYTES, "GT06_REPORT_CAP_OR_EXISTS"):
		return
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if not need(file != null, "GT06_REPORT_OPEN"):
		return
	file.store_string(encoded)
	file.flush()
	var write_error: Error = file.get_error()
	file.close()
	if not need(write_error == OK and FileAccess.get_sha256(path) == encoded.sha256_text(), "GT06_REPORT_READBACK"):
		return
	finished = true
	set_process(false)
	print("HH_GT06_COMPLETE " + JSON.stringify({"run_id": run["run_id"], "command_id": run["command_id"],
		"runtime_instance_id": run["runtime_instance_id"], "pid": OS.get_process_id(), "report_sha256": encoded.sha256_text()}))
	get_tree().paused = false
	get_tree().quit(0)
