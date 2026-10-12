extends SceneTree
## Performance and leak runner. The host (studio/gamekit/perf.py) passes a JSON request.
## Returning false from _process keeps the real frame running (nodes, physics, then draw).
## Godot 4.7.2 freezes Performance.TIME_PROCESS, TIME_PHYSICS_PROCESS and TIME_FPS after the
## first frame when this script overrides _process, so process time is the gap from this
## function to a last-priority sentinel, and physics time is the gap from physics_frame
## to that sentinel. The raw monitors are still sampled and returned as *_monitor_ms.

const SENTINEL_SRC: String = "extends Node\nsignal pulse\nsignal phys_pulse\n\nfunc _process(_d: float) -> void:\n\tpulse.emit()\n\nfunc _physics_process(_d: float) -> void:\n\tphys_pulse.emit()\n"
const LEAK_ALIVE_FRAMES: int = 10
const LEAK_WAIT_FRAMES: int = 3

const HH = preload("hhgk.gd")
var boot_error: String = ""
var finished: bool = false

var scene_path: String = ""
var measure_frames: int = 300
var warmup_frames: int = 60
var leak_cycles: int = 5
var headless: bool = false
var gpu_measured: bool = false
var trace_events: Array = []
var trace_applied: int = 0

var packed: PackedScene
var phase: String = "boot"
var frame_i: int = 0
var warmup_left: int = 0
var last_usec: int = 0
var leak_cycle: int = 0
var leak_hold: int = 0
var leak_node: Node = null
var leak_samples: Array = []

var phys_us: int = 0
var phys_open: int = -1
var armed: bool = false
var armed_at: int = 0
var armed_frame_ms: float = 0.0
var armed_physics_ms: float = 0.0
var armed_counts: Dictionary = {}

var frame_ms_s: Array[float] = []
var process_measured_s: Array[float] = []
var process_monitor_s: Array[float] = []
var physics_measured_s: Array[float] = []
var physics_monitor_s: Array[float] = []
var render_cpu_s: Array[float] = []
var render_gpu_s: Array[float] = []
var draw_calls_s: Array[float] = []
var primitives_s: Array[float] = []
var vram_s: Array[float] = []
var objects_s: Array[float] = []
var nodes_s: Array[float] = []
var orphans_s: Array[float] = []
var memory_s: Array[float] = []
var physics_2d_s: Array[float] = []
var physics_3d_s: Array[float] = []


func _initialize() -> void:
	var req: Variant = HH.read_request()
	if req == null or not (req is Dictionary):
		boot_error = "missing or invalid --request file"
		return
	var r: Dictionary = req
	scene_path = str(r.get("scene", ""))
	measure_frames = HH.variant_int(r.get("frames", 300))
	warmup_frames = HH.variant_int(r.get("warmup", 60))
	leak_cycles = HH.variant_int(r.get("leak_cycles", 5))
	headless = HH.variant_bool(r.get("headless", false))
	var trace_body: Variant = r.get("trace", {})
	if trace_body is Dictionary:
		var trace_d: Dictionary = trace_body
		var evs: Variant = trace_d.get("events", [])
		if evs is Array:
			var ev_list: Array = evs
			trace_events = ev_list
	if scene_path.is_empty():
		boot_error = "scene missing"
	elif measure_frames < 1 or warmup_frames < 0 or leak_cycles < 1:
		boot_error = "frames, warmup or leak_cycles out of range"
	else:
		phase = "boot"
		last_usec = Time.get_ticks_usec()


func _process(_delta: float) -> bool:
	if finished:
		return true
	if boot_error != "":
		_finish(HH.fail("BAD_REQUEST", boot_error))
		return true
	return _tick()


func _tick() -> bool:
	var now: int = Time.get_ticks_usec()
	var frame_ms: float = float(now - last_usec) / 1000.0
	last_usec = now
	var physics_ms: float = _take_physics_ms()
	if phase == "boot":
		return _tick_boot()
	if phase == "warmup" or phase == "measure":
		_apply_trace(frame_i)
		frame_i += 1
	if phase == "warmup":
		warmup_left -= 1
		if warmup_left <= 0:
			phase = "measure"
		return false
	if phase == "measure":
		if armed:
			_finish(HH.fail("GODOT_FAILED", "perf sentinel missed a frame"))
			return true
		_arm(now, frame_ms, physics_ms)
		return false
	if phase == "leak_spawn":
		return _tick_leak_spawn()
	if phase == "leak_run":
		return _tick_leak_run()
	if phase == "leak_wait":
		return _tick_leak_wait()
	_finish(HH.fail("GODOT_FAILED", "perf runner lost its phase"))
	return true


func _tick_boot() -> bool:
	var err: String = _boot()
	if err != "":
		_finish(HH.fail("GODOT_FAILED", err))
		return true
	_apply_trace(0)
	frame_i = 1
	last_usec = Time.get_ticks_usec()
	if warmup_frames > 0:
		phase = "warmup"
		warmup_left = warmup_frames
	else:
		phase = "measure"
	return false


func _tick_leak_spawn() -> bool:
	if leak_cycle >= leak_cycles:
		_finish_ok()
		return true
	if packed == null:
		_finish(HH.fail("GODOT_FAILED", "scene was not loaded"))
		return true
	leak_node = packed.instantiate()
	if leak_node == null:
		_finish(HH.fail("GODOT_FAILED", "leak instantiate failed"))
		return true
	leak_node.name = "HHLeakCycle" + str(leak_cycle + 1)
	root.add_child(leak_node)
	leak_hold = LEAK_ALIVE_FRAMES
	phase = "leak_run"
	return false


func _tick_leak_run() -> bool:
	leak_hold -= 1
	if leak_hold <= 0:
		if leak_node != null and is_instance_valid(leak_node):
			leak_node.queue_free()
		leak_node = null
		leak_hold = LEAK_WAIT_FRAMES
		phase = "leak_wait"
	return false


func _tick_leak_wait() -> bool:
	leak_hold -= 1
	if leak_hold <= 0:
		leak_cycle += 1
		leak_samples.append(_leak_row(leak_cycle))
		phase = "leak_spawn"
	return false


func _boot() -> String:
	if root == null:
		return "scene tree root is not ready"
	OS.low_processor_usage_mode = false
	Engine.max_fps = 0
	if headless or DisplayServer.get_name() == "headless":
		headless = true
		gpu_measured = false
	else:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
		gpu_measured = true
	var scr: GDScript = _sentinel_script()
	if scr == null:
		return "perf sentinel script failed to compile"
	var sentinel: Node = Node.new()
	sentinel.name = "HHPerfSentinel"
	sentinel.process_mode = Node.PROCESS_MODE_ALWAYS
	sentinel.process_priority = 1000000000
	sentinel.set_physics_process_priority(1000000000)
	sentinel.set_script(scr)
	root.add_child(sentinel)
	if sentinel.connect("pulse", Callable(self, "_on_sentinel_process")) != OK:
		return "cannot connect perf sentinel"
	if sentinel.connect("phys_pulse", Callable(self, "_on_sentinel_physics")) != OK:
		return "cannot connect perf physics sentinel"
	if physics_frame.connect(Callable(self, "_on_physics_frame")) != OK:
		return "cannot connect physics_frame"
	if not ResourceLoader.exists(scene_path):
		return "scene does not exist: " + scene_path
	var loaded: Resource = load(scene_path)
	packed = loaded as PackedScene
	if packed == null:
		return "not a packed scene: " + scene_path
	var inst: Node = packed.instantiate()
	if inst == null:
		return "cannot instantiate " + scene_path
	root.add_child(inst)
	return ""


func _sentinel_script() -> GDScript:
	var scr: GDScript = GDScript.new()
	scr.source_code = SENTINEL_SRC
	if scr.reload() != OK:
		return null
	return scr


func _on_physics_frame() -> void:
	var now: int = Time.get_ticks_usec()
	if phys_open >= 0:
		phys_us += now - phys_open
	phys_open = now


func _on_sentinel_physics() -> void:
	if phys_open < 0:
		return
	phys_us += Time.get_ticks_usec() - phys_open
	phys_open = -1


func _take_physics_ms() -> float:
	var ms: float = _finite(float(phys_us) / 1000.0)
	phys_us = 0
	phys_open = -1
	return ms


func _on_sentinel_process() -> void:
	if finished or not armed:
		return
	var process_ms: float = _finite(float(Time.get_ticks_usec() - armed_at) / 1000.0)
	_push(process_ms)
	armed = false
	if phase == "measure" and frame_ms_s.size() >= measure_frames:
		phase = "leak_spawn"


func _arm(started_at: int, frame_ms: float, physics_ms: float) -> void:
	armed = true
	armed_at = started_at
	armed_frame_ms = frame_ms
	armed_physics_ms = physics_ms
	armed_counts = _counts()


func _counts() -> Dictionary:
	var cpu_ms: float = 0.0
	var gpu_ms: float = 0.0
	if gpu_measured:
		var vp: RID = root.get_viewport_rid()
		cpu_ms = RenderingServer.viewport_get_measured_render_time_cpu(vp)
		gpu_ms = RenderingServer.viewport_get_measured_render_time_gpu(vp)
	return {
		"render_cpu_ms": cpu_ms,
		"render_gpu_ms": gpu_ms,
		"draw_calls": Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
		"primitives": Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
		"vram_bytes": Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED),
		"objects": Performance.get_monitor(Performance.OBJECT_COUNT),
		"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
		"orphans": Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT),
		"memory_static": Performance.get_monitor(Performance.MEMORY_STATIC),
		"physics_2d": Performance.get_monitor(Performance.PHYSICS_2D_ACTIVE_OBJECTS),
		"physics_3d": Performance.get_monitor(Performance.PHYSICS_3D_ACTIVE_OBJECTS),
		"process_monitor_ms": Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
		"physics_monitor_ms": Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0,
	}


func _push(process_ms: float) -> void:
	var c: Dictionary = armed_counts
	var process_monitor_ms: float = c["process_monitor_ms"]
	var physics_monitor_ms: float = c["physics_monitor_ms"]
	var render_cpu_ms: float = c["render_cpu_ms"]
	var render_gpu_ms: float = c["render_gpu_ms"]
	var draw_calls: float = c["draw_calls"]
	var primitives: float = c["primitives"]
	var vram_bytes: float = c["vram_bytes"]
	var objects: float = c["objects"]
	var nodes: float = c["nodes"]
	var orphans: float = c["orphans"]
	var memory_static: float = c["memory_static"]
	var physics_2d: float = c["physics_2d"]
	var physics_3d: float = c["physics_3d"]
	frame_ms_s.append(_finite(armed_frame_ms))
	process_measured_s.append(process_ms)
	process_monitor_s.append(_finite(process_monitor_ms))
	physics_measured_s.append(_finite(armed_physics_ms))
	physics_monitor_s.append(_finite(physics_monitor_ms))
	render_cpu_s.append(_finite(render_cpu_ms))
	render_gpu_s.append(_finite(render_gpu_ms))
	draw_calls_s.append(_finite(draw_calls))
	primitives_s.append(_finite(primitives))
	vram_s.append(_finite(vram_bytes))
	objects_s.append(_finite(objects))
	nodes_s.append(_finite(nodes))
	orphans_s.append(_finite(orphans))
	memory_s.append(_finite(memory_static))
	physics_2d_s.append(_finite(physics_2d))
	physics_3d_s.append(_finite(physics_3d))


func _leak_row(cycle: int) -> Dictionary:
	return {
		"cycle": cycle,
		"objects": _finite(Performance.get_monitor(Performance.OBJECT_COUNT)),
		"nodes": _finite(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"orphans": _finite(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)),
		"memory_static": _finite(Performance.get_monitor(Performance.MEMORY_STATIC)),
	}


func _apply_trace(frame: int) -> void:
	for item: Variant in trace_events:
		if not (item is Dictionary):
			continue
		var ev: Dictionary = item
		var frame_n: int = ev.get("frame", -1)
		if frame_n != frame:
			continue
		var action_ev: InputEventAction = InputEventAction.new()
		action_ev.action = StringName(str(ev.get("action", "")))
		action_ev.pressed = HH.variant_bool(ev.get("pressed", false))
		action_ev.strength = 1.0 if action_ev.pressed else 0.0
		Input.parse_input_event(action_ev)
		trace_applied += 1


func _finite(v: float) -> float:
	if is_nan(v) or is_inf(v):
		return 0.0
	return v


func _plain(values: Array[float]) -> Array:
	var out: Array = []
	for v: float in values:
		out.append(v)
	return out


func _success() -> Dictionary:
	return {
		"ok": true,
		"scene": scene_path,
		"headless": headless,
		"gpu_measured": gpu_measured,
		"trace_applied": trace_applied,
		"sample_frames": frame_ms_s.size(),
		"samples": {
			"frame_ms": _plain(frame_ms_s),
			"process_measured_ms": _plain(process_measured_s),
			"process_monitor_ms": _plain(process_monitor_s),
			"physics_measured_ms": _plain(physics_measured_s),
			"physics_monitor_ms": _plain(physics_monitor_s),
			"render_cpu_ms": _plain(render_cpu_s),
			"render_gpu_ms": _plain(render_gpu_s),
			"draw_calls": _plain(draw_calls_s),
			"primitives": _plain(primitives_s),
			"vram_bytes": _plain(vram_s),
			"objects": _plain(objects_s),
			"nodes": _plain(nodes_s),
			"orphans": _plain(orphans_s),
			"memory_static": _plain(memory_s),
			"physics_2d": _plain(physics_2d_s),
			"physics_3d": _plain(physics_3d_s),
		},
		"leak_samples": leak_samples,
	}


func _finish_ok() -> void:
	if frame_ms_s.size() != measure_frames or leak_samples.size() != leak_cycles:
		_finish(HH.fail("GODOT_FAILED", "perf sample count mismatch: frames %d/%d leak %d/%d" % [
			frame_ms_s.size(), measure_frames, leak_samples.size(), leak_cycles]))
		return
	_finish(_success())


func _finish(result: Dictionary) -> void:
	if finished:
		return
	finished = true
	HH.emit(result)
	var ok_flag: bool = result.get("ok", false)
	quit(0 if ok_flag else 3)
