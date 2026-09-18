extends Node
## Bounded rendering observer. Frame post-draw owns both the image and its facts.

const MAX_FRAMES: int = 1200
const MAX_PNG_BYTES: int = 1048576
var bridge: Node
var fixture: Node3D
var pending: Array[Dictionary] = []
var captures: Dictionary = {}
var native_frames: Array[Dictionary] = []
var frame_start_monotonic_us: int = 0
var previous_monotonic_us: int = 0
var previous_rendered_frame: int = -1
var perf_measurement_start_monotonic_us: int = 0
var perf_measurement_start_frame_index: int = -1
var stopped: bool = false
var headless: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	headless = DisplayServer.get_name() == "headless"
	frame_start_monotonic_us = Time.get_ticks_usec()
	previous_monotonic_us = frame_start_monotonic_us
	if not headless:
		RenderingServer.frame_post_draw.connect(_frame_post_draw)
	set_process(headless)


func enqueue(tick: int, label: String) -> void:
	if not _need(not stopped and not headless and pending.size() + captures.size() < 16
			and not captures.has(label), "GT06_CAPTURE_CAPACITY"):
		return
	var requested_camera_json: String = JSON.stringify(fixture.call("camera_snapshot"))
	pending.append({"requested_tick": tick, "label": label,
		"minimum_rendered_frame": Engine.get_frames_drawn(), "minimum_process_frame": Engine.get_process_frames(),
		"requested_monotonic_us": Time.get_ticks_usec(), "requested_phase": fixture.get("phase"),
		"requested_camera_json": requested_camera_json, "requested_camera_sha256": requested_camera_json.sha256_text()})


func pending_count() -> int:
	return pending.size()


func _need(value: bool, code: String) -> bool:
	return bool(bridge.call("need", value, code))


func _process(_delta: float) -> void:
	# Diagnostic-only headless traces have no captures and claim no rendered frame.
	if headless:
		_observe_frame(false)


func _frame_post_draw() -> void:
	_observe_frame(true)


func _observe_frame(rendered: bool) -> void:
	if stopped or bool(bridge.get("failed")) or not bool(fixture.get("ready_for_trace")):
		return
	var monotonic_us: int = Time.get_ticks_usec()
	var rendered_frame: int = Engine.get_frames_drawn()
	if rendered and rendered_frame == previous_rendered_frame:
		return
	if not _need(monotonic_us > previous_monotonic_us and native_frames.size() < MAX_FRAMES, "GT06_FRAME_CAP_OR_CLOCK"):
		return
	var state: Dictionary = fixture.call("snapshot")
	var state_json: String = JSON.stringify(state)
	var digest: String = state_json.sha256_text()
	var trace_tick: int = int(bridge.get("last_observed_tick"))
	var viewport: Viewport = fixture.get_viewport()
	var visible_calls: int = 0
	var shadow_calls: int = 0
	var primitives: int = 0
	if rendered:
		visible_calls = RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),
			RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
		shadow_calls = RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),
			RenderingServer.VIEWPORT_RENDER_INFO_TYPE_SHADOW, RenderingServer.VIEWPORT_RENDER_INFO_DRAW_CALLS_IN_FRAME)
		primitives = RenderingServer.viewport_get_render_info(viewport.get_viewport_rid(),
			RenderingServer.VIEWPORT_RENDER_INFO_TYPE_VISIBLE, RenderingServer.VIEWPORT_RENDER_INFO_PRIMITIVES_IN_FRAME)
	var raw_counters: Dictionary = {"triangles": int(fixture.call("visible_triangle_count")),
		"draw_calls": visible_calls + shadow_calls, "render_primitives": primitives,
		"texture_bytes": int(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED))}
	var qualified: bool = rendered and rendered_frame >= 2 and native_frames.size() >= 1
	var eligible: bool = qualified and perf_measurement_start_frame_index >= 0
	var counters: Dictionary = raw_counters if qualified else {"triangles": null, "draw_calls": null,
		"render_primitives": null, "texture_bytes": null}
	native_frames.append({"monotonic_us": monotonic_us, "frame_time_us": monotonic_us - previous_monotonic_us,
		"process_frame": Engine.get_process_frames(), "rendered_frame": rendered_frame, "trace_tick": trace_tick,
		"sim_tick": state["sim_tick"], "ui_tick": state["ui_tick"], "phase": state["phase"],
		"state_json": state_json, "state_snapshot_sha256": digest, "hash_domain": "native-json-utf8",
		"frame_hook": "frame_post_draw" if rendered else "process_headless_diagnostic", "counters": counters,
		"counter_readiness": {"qualified": qualified, "reason": "qualified" if qualified else "startup_not_qualified"},
		"raw_counter_readback": raw_counters if not qualified else null, "measurement_eligible": eligible})
	previous_monotonic_us = monotonic_us
	previous_rendered_frame = rendered_frame
	if qualified and perf_measurement_start_frame_index < 0:
		perf_measurement_start_monotonic_us = monotonic_us
		perf_measurement_start_frame_index = native_frames.size()
		bridge.call("arm_trace", {"monotonic_us": monotonic_us, "process_frame": Engine.get_process_frames(),
			"rendered_frame": rendered_frame, "ready_frame_count": native_frames.size(), "rendered": true})
	elif headless and native_frames.size() == 2:
		bridge.call("arm_trace", {"monotonic_us": monotonic_us, "process_frame": Engine.get_process_frames(),
			"rendered_frame": rendered_frame, "ready_frame_count": native_frames.size(), "rendered": false})
	var ready: Array[Dictionary] = []
	for request: Dictionary in pending:
		if rendered_frame > int(request["minimum_rendered_frame"]) \
				and Engine.get_process_frames() > int(request["minimum_process_frame"]) \
				and trace_tick >= int(request["requested_tick"]):
			ready.append(request)
	if ready.is_empty():
		return
	if not _need(qualified, "GT06_CAPTURE_RENDER_NOT_QUALIFIED"):
		return
	var image: Image = viewport.get_texture().get_image()
	if not _need(not image.is_empty() and image.get_width() == 960 and image.get_height() == 640
			and visible_calls > 0, "GT06_CAPTURE_RENDER_READBACK"):
		return
	var now_unix: float = Time.get_unix_time_from_system()
	for request: Dictionary in ready:
		if not _need(request["requested_phase"] == state["phase"] and request["requested_camera_sha256"] ==
				JSON.stringify(fixture.call("camera_snapshot")).sha256_text(), "GT06_CAPTURE_CONTEXT_CHANGED"):
			return
		var label: String = request["label"]
		var path: String = "res://out/" + label + ".png"
		if not _need(not FileAccess.file_exists(path), "GT06_CAPTURE_ALREADY_EXISTS"):
			return
		if not _need(image.save_png(path) == OK, "GT06_CAPTURE_WRITE"):
			return
		var file: FileAccess = FileAccess.open(path, FileAccess.READ)
		if not _need(file != null, "GT06_CAPTURE_READBACK"):
			return
		var size_bytes: int = file.get_length()
		file.close()
		if not _need(size_bytes > 0 and size_bytes <= MAX_PNG_BYTES, "GT06_CAPTURE_BYTE_CAP"):
			return
		var binding: Dictionary = bridge.get("run")
		var native: Dictionary = bridge.get("native")
		captures[label] = {"label": label, "requested_tick": request["requested_tick"], "observed_tick": trace_tick,
			"requested_phase": request["requested_phase"], "requested_camera_json": request["requested_camera_json"],
			"requested_camera_sha256": request["requested_camera_sha256"],
			"requested_monotonic_us": request["requested_monotonic_us"], "monotonic_us": monotonic_us,
			"minimum_rendered_frame": request["minimum_rendered_frame"], "minimum_process_frame": request["minimum_process_frame"],
			"rendered_frame": rendered_frame, "process_frame": Engine.get_process_frames(), "captured_at_unix": now_unix,
			"pid": OS.get_process_id(), "window_id": native["window_id"], "native_window_handle": native["native_window_handle"],
			"run_id": binding["run_id"], "command_id": binding["command_id"], "runtime_instance_id": binding["runtime_instance_id"],
			"generation": binding["generation"], "source_closure_sha256": binding["source_closure_sha256"],
			"runtime_snapshot_sha256": binding["runtime_snapshot_sha256"], "trace_sha256": binding["trace_sha256"],
			"glb_sha256": binding["glb_sha256"], "camera": fixture.call("camera_snapshot"),
			"state_json": state_json, "state_snapshot_sha256": digest, "hash_domain": "native-json-utf8",
			"sha256": FileAccess.get_sha256(path), "size_bytes": size_bytes, "width": image.get_width(), "height": image.get_height(),
			"sim_tick": state["sim_tick"], "ui_tick": state["ui_tick"], "phase": state["phase"], "counters": counters}
		pending.erase(request)


func finish() -> Dictionary:
	stopped = true
	if RenderingServer.frame_post_draw.is_connected(_frame_post_draw):
		RenderingServer.frame_post_draw.disconnect(_frame_post_draw)
	set_process(false)
	if not _need(pending.is_empty() and not native_frames.is_empty(), "GT06_RENDER_COMPLETENESS"):
		return {}
	return {"captures": captures, "native_frames": native_frames,
		"frame_start_monotonic_us": frame_start_monotonic_us, "frame_end_monotonic_us": previous_monotonic_us,
		"perf_measurement_start_monotonic_us": perf_measurement_start_monotonic_us,
		"perf_measurement_start_frame_index": perf_measurement_start_frame_index,
		"counter_definitions": {"triangles": "loaded visible MeshInstance3D LOD topology; excludes UI and GPU culling",
			"draw_calls": "viewport visible plus shadow draw calls in this rendered frame",
			"render_primitives": "viewport visible render primitives; not converted to triangle count",
			"texture_bytes": "Godot Performance.RENDER_TEXTURE_MEM_USED; excludes host RSS"}}


func _exit_tree() -> void:
	if RenderingServer.frame_post_draw.is_connected(_frame_post_draw):
		RenderingServer.frame_post_draw.disconnect(_frame_post_draw)
