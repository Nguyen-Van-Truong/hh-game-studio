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
	var profile: String = str(body.get("user_profile", "")).replace("\\", "/").simplify_path().trim_suffix("/")
	var user_dir: String = OS.get_user_data_dir().replace("\\", "/").simplify_path()
	if OS.get_name() == "Windows":
		profile = profile.to_lower()
		user_dir = user_dir.to_lower()
	if profile.is_empty() or not user_dir.begins_with(profile + "/"):
		_fail_setup("USER_DATA_ISOLATION_FAILED", "user:// is outside the requested run profile")
		return
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
		var node: Node = _observe_node(str(spec.get("node", "")))
		if node == null:
			values[label] = null
		else:
			values[label] = _observe_value(node, str(spec.get("prop", "")))
	observations.append({"frame": frame, "values": values})


## Resolve a probe relative to the instantiated scene.  The instantiated
## scene itself is a valid target, so both ``Root:flag`` and ``.:flag``
## observe the root instead of looking for a child named Root.  Accepting a
## root-name prefix also makes probes copied from editor paths stable.
func _observe_node(path: String) -> Node:
	if current == null:
		return null
	if path.is_empty() or path == "." or path == str(current.name):
		return current
	var relative: String = path
	var root_prefix: String = str(current.name) + "/"
	if relative.begins_with(root_prefix):
		relative = relative.substr(root_prefix.length())
	if relative.is_empty() or relative == ".":
		return current
	return current.get_node_or_null(NodePath(relative))


## Godot exposes AnimationTree parameters as property names containing '/'.
## Native const boolean queries (for example is_on_floor) are also probes;
## arbitrary script methods and methods that accept arguments are not called.
func _observe_value(node: Node, prop: String) -> Variant:
	if prop.is_empty():
		return null
	if not prop.contains("/") and node.has_method(prop):
		for method: Dictionary in ClassDB.class_get_method_list(node.get_class()):
			if str(method.get("name", "")) != prop:
				continue
			var args: Array = method.get("args", [])
			var returns: Dictionary = method.get("return", {})
			var flags: int = HH.variant_int(method.get("flags", 0))
			if args.is_empty() and HH.variant_int(returns.get("type", TYPE_NIL)) == TYPE_BOOL and (flags & METHOD_FLAG_CONST) != 0:
				return HH.to_json(node.call(prop))
		# A script method is deliberately not read through Object.get: Godot
		# exposes it as a Callable, which would make an arbitrary mutator look
		# like a successful observation.  Probes stay read-only.
		return null
	return HH.to_json(node.get(prop))


func _finish() -> void:
	var result: Dictionary = {
		"ok": sink.messages.is_empty(),
		"frames": steps,
		"observations": observations,
		"errors": sink.messages,
		"user_data_dir": OS.get_user_data_dir(),
	}
	HH.emit(result)
	quit(0)
