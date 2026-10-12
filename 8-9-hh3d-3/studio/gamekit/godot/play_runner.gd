extends SceneTree
## gamekit play runner: load a scene, seed the RNG, and step physics at the host's --fixed-fps 60.
## Trace events are InputEventAction values parsed on the physics frame they name, then flushed
## so is_action_pressed / _input see them before nodes run _physics_process.

const HH = preload("hhgk.gd")
var sink: ErrorSink
var current: Node = null
var steps: int = 0
var target: int = 0
var every: int = 1
var observe: Array = []
var events_at: Dictionary = {}
var observations: Array = []
var ready: bool = false
var unknown_actions: Dictionary = {}


class ErrorSink extends Logger:
	var messages: Array = []

	func _log_error(function: String, file: String, line: int, code: String, rationale: String, _editor_notify: bool, error_type: int, script_backtraces: Array) -> void:
		if error_type == 1:
			return
		var text: String = code if rationale.is_empty() else "%s %s" % [code, rationale]
		messages.append({
			"file": file,
			"line": line,
			"function": function,
			"code": text,
			"error_type": error_type,
			"traces": script_backtraces.size(),
		})

	func _log_message(message: String, error: bool) -> void:
		if error:
			messages.append({"code": message, "error_type": 0})


func _initialize() -> void:
	sink = ErrorSink.new()
	if ClassDB.class_exists("Logger") and OS.has_method("add_logger"):
		OS.add_logger(sink)
	var req: Variant = HH.read_request()
	if not (req is Dictionary):
		_fail_setup("BAD_REQUEST", "missing or invalid --request file")
		return
	var body: Dictionary = req
	target = HH.variant_int(body.get("frames", 60))
	every = maxi(HH.variant_int(body.get("every", 1)), 1)
	observe = body.get("observe", [])
	if not (observe is Array):
		_fail_setup("BAD_REQUEST", "observe must be a list")
		return
	var raw_events: Variant = body.get("events", [])
	if raw_events is Array:
		for item: Variant in raw_events:
			if item is Dictionary:
				var spec_in: Dictionary = item
				var frame: int = HH.variant_int(spec_in.get("frame", 0))
				if not events_at.has(frame):
					events_at[frame] = []
				var bucket: Array = events_at[frame]
				bucket.append(item)
	var scene_path: String = str(body.get("scene", ""))
	if scene_path.is_empty():
		scene_path = str(ProjectSettings.get_setting("application/run/main_scene", ""))
	if scene_path.is_empty():
		_fail_setup("NOT_FOUND", "project has no main scene")
		return
	Engine.physics_ticks_per_second = 60
	Engine.time_scale = 1.0
	Input.set_use_accumulated_input(false)
	seed(HH.variant_int(body.get("seed", 0)))
	var loaded: Resource = load(scene_path)
	var packed: PackedScene = null
	if loaded is PackedScene:
		packed = loaded
	if packed == null:
		_fail_setup("NOT_FOUND", "cannot load scene " + scene_path)
		return
	var node: Node = packed.instantiate()
	if node == null:
		_fail_setup("GODOT_FAILED", "cannot instantiate " + scene_path)
		return
	root.add_child(node)
	current_scene = node
	current = node
	ready = true


func _fail_setup(code: String, detail: String) -> void:
	ready = false
	HH.emit(HH.fail(code, detail))
	quit(3)


func _physics_process(_delta: float) -> bool:
	if not ready or current == null:
		return true
	if steps % every == 0 or steps == target:
		_sample(steps)
	if steps >= target:
		_finish()
		return true
	_apply(steps)
	steps += 1
	return false


func _apply(frame: int) -> void:
	if not events_at.has(frame):
		return
	var batch: Array = events_at[frame]
	for item: Variant in batch:
		var spec: Dictionary = item
		var action_name: String = str(spec.get("action", ""))
		if action_name.is_empty():
			continue
		if not InputMap.has_action(action_name):
			if not unknown_actions.has(action_name):
				unknown_actions[action_name] = true
				sink.messages.append({"code": "unknown input action '%s'" % action_name, "error_type": 0})
			continue
		var action_event: InputEventAction = InputEventAction.new()
		action_event.action = action_name
		action_event.pressed = HH.variant_bool(spec.get("pressed", false))
		action_event.strength = HH.variant_float(spec.get("strength", 1.0))
		Input.parse_input_event(action_event)
		Input.flush_buffered_events()


func _sample(frame: int) -> void:
	var values: Dictionary = {}
	for item: Variant in observe:
		if not (item is Dictionary):
			continue
		var spec: Dictionary = item
		var label: String = str(spec.get("label", ""))
		var node: Node = current.get_node_or_null(NodePath(str(spec.get("node", ""))))
		if node == null:
			values[label] = null
		else:
			values[label] = HH.to_json(node.get(str(spec.get("prop", ""))))
	observations.append({"frame": frame, "values": values})


func _finish() -> void:
	var result: Dictionary = {
		"ok": sink.messages.is_empty(),
		"frames": steps,
		"observations": observations,
		"errors": sink.messages,
	}
	HH.emit(result)
	quit(0)
