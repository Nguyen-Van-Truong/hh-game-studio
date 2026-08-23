extends Node

## Debug-only Play autoload. Answers paged tree/node/state over the debugger
## channel. Never required on shipped games (export plugin skip() + no
## project.godot persist). Base Node2D works without agent_observe.

const CAPTURE: String = "hh_runtime"
const MAX_PAGE: int = 100
const REDACT: String = "***"
const HELLO_MS: int = 1000

var _last_hello_ms: int = 0
@export var dummy_secret: String = ""
@export var dummy_password: String = ""
@export var dummy_token: String = ""
@export var hp: int = 0
@export var spawn_count: int = 0
var _held: Dictionary = {}
var _seen_flush: bool = false
var _input_seen: int = 0
var _secret_needles: PackedStringArray = PackedStringArray([
	"password",
	"passwd",
	"secret",
	"token",
	"api_key",
	"apikey",
	"access_key",
	"private_key",
])


func _ready() -> void:
	set_process_input(true)
	_bind_debugger()
	if spawn_count > 0:
		var i: int = 0
		while i < spawn_count:
			var node: Node = Node.new()
			node.name = "N%d" % i
			add_child(node)
			i += 1
	ping_debugger()
	await _spawn_nothing()


func _bind_debugger() -> void:
	EngineDebugger.register_message_capture(CAPTURE, Callable(self, "_on_capture"))
	var active: bool = EngineDebugger.is_active()
	print("hh_runtime bind active=%s" % str(active))
	if active:
		EngineDebugger.send_message("%s:hello" % CAPTURE, [JSON.stringify({"ok": true, "source": "hh_agent_runtime"})])


func ping_debugger() -> void:
	_last_hello_ms = 0
	_process(0.0)


func _process(_delta: float) -> void:
	var now: int = Time.get_ticks_msec()
	if _last_hello_ms > 0 and now - _last_hello_ms < HELLO_MS:
		return
	if not EngineDebugger.is_active():
		return
	_last_hello_ms = now
	EngineDebugger.send_message("%s:hello" % CAPTURE, [JSON.stringify({"ok": true, "source": "hh_agent_runtime"})])


func _spawn_nothing() -> void:
	# Yield one frame so the debugger session can finish attach before queries.
	var tree: SceneTree = get_tree()
	if tree != null:
		await tree.process_frame


func _on_capture(message: String, data: Array) -> bool:
	# Capture callbacks receive the suffix after "hh_runtime:".
	var rest: String = message
	if message.begins_with("%s:" % CAPTURE):
		rest = message.substr(CAPTURE.length() + 1)
	var payload: Dictionary = _payload_of(data)
	var op: String = str(payload.get("op", ""))
	if op.is_empty():
		op = rest
	if op.is_empty() and payload.is_empty():
		return false
	var reply: Dictionary = _dispatch(op, payload)
	print("hh_runtime capture op=%s" % op)
	if reply.get("async", false) == true:
		return not op.is_empty()
	EngineDebugger.send_message("%s:reply" % CAPTURE, [JSON.stringify(reply)])
	return not op.is_empty()


func _dispatch(op: String, payload: Dictionary) -> Dictionary:
	var token: String = str(payload.get("token", ""))
	var run_id: String = str(payload.get("run_id", ""))
	var base: Dictionary = {
		"token": token,
		"run_id": run_id,
		"op": op,
		"tree_kind": "remote",
		"remote_tree": true,
		"source": "hh_agent_runtime",
	}
	if op == "tree":
		return _merge(base, _tree_page(payload))
	if op == "node":
		return _merge(base, _node_snap(payload))
	if op == "state":
		return _merge(base, _state_snap(payload))
	if op == "time":
		return _merge(base, _time_snap())
	if (
		op == "action"
		or op == "key"
		or op == "mouse"
		or op == "touch"
		or op == "sequence"
		or op == "release_all"
	):
		return _merge(base, _input_op(op, payload, base))
	base["ok"] = false
	base["message"] = "unknown runtime op"
	return base


func _tree_page(payload: Dictionary) -> Dictionary:
	var nodes: Array = _flatten()
	var total: int = nodes.size()
	var limit: int = _limit_of(payload)
	var offset: int = _offset_of(payload)
	var items: Array = []
	var i: int = offset
	var end: int = mini(offset + limit, total)
	while i < end:
		items.append(_brief(nodes[i]))
		i += 1
	var next_cursor: String = ""
	if end < total:
		next_cursor = str(end)
	return {
		"ok": true,
		"items": items,
		"total": total,
		"offset": offset,
		"limit": limit,
		"next_cursor": next_cursor,
		"has_more": end < total,
		"time": _time_snap(),
	}


func _node_snap(payload: Dictionary) -> Dictionary:
	var path_s: String = str(payload.get("node_path", "."))
	var node: Node = _resolve(path_s)
	if node == null:
		return {"ok": false, "message": "remote node not found", "node_path": path_s}
	var props: Dictionary = _properties_of(node)
	var observe: Dictionary = _observe_of(node)
	return {
		"ok": true,
		"node_path": str(node.get_path()),
		"name": str(node.name),
		"class": node.get_class(),
		"groups": _groups_of(node),
		"signals": _signals_of(node),
		"properties": props,
		"observe": observe,
		"time": _time_snap(),
	}


func _state_snap(payload: Dictionary) -> Dictionary:
	var key: String = str(payload.get("key", ""))
	var path_s: String = str(payload.get("node_path", "."))
	var node: Node = _resolve(path_s)
	if node == null:
		return {"ok": false, "message": "runtime state node not found", "key": key}
	var observe: Dictionary = _observe_of(node)
	if observe.has(key):
		return {
			"ok": true,
			"key": key,
			"found": true,
			"value": _redact_value(key, observe[key]),
			"value_source": "agent_observe",
			"time": _time_snap(),
		}
	if _has_property(node, key):
		return {
			"ok": true,
			"key": key,
			"found": true,
			"value": _redact_value(key, node.get(key)),
			"value_source": "property",
			"time": _time_snap(),
		}
	return {
		"ok": true,
		"key": key,
		"found": false,
		"value": null,
		"value_source": "missing",
		"time": _time_snap(),
	}


func _time_snap() -> Dictionary:
	return {
		"ticks_msec": Time.get_ticks_msec(),
		"frames": Engine.get_process_frames(),
		"physics_frames": Engine.get_physics_frames(),
	}


func _flatten() -> Array:
	var out: Array = []
	var tree: SceneTree = get_tree()
	if tree == null or tree.root == null:
		return out
	var stack: Array = []
	stack.append(tree.root)
	while not stack.is_empty():
		var node_v: Variant = stack[0]
		stack.remove_at(0)
		if not (node_v is Node):
			continue
		var node: Node = node_v
		out.append(node)
		var i: int = 0
		while i < node.get_child_count():
			stack.append(node.get_child(i))
			i += 1
	return out


func _brief(node: Node) -> Dictionary:
	return {
		"path": str(node.get_path()),
		"name": str(node.name),
		"class": node.get_class(),
	}


func _resolve(path_s: String) -> Node:
	var tree: SceneTree = get_tree()
	if tree == null:
		return null
	if path_s.is_empty() or path_s == ".":
		if tree.current_scene != null:
			return tree.current_scene
		return tree.root
	var abs_n: Node = tree.root.get_node_or_null(NodePath(path_s))
	if abs_n != null:
		return abs_n
	if tree.current_scene != null:
		var rel_n: Node = tree.current_scene.get_node_or_null(NodePath(path_s))
		if rel_n != null:
			return rel_n
		if str(tree.current_scene.name) == path_s:
			return tree.current_scene
	return null


func _properties_of(node: Node) -> Dictionary:
	var out: Dictionary = {}
	var listed: Array = node.get_property_list()
	var i: int = 0
	while i < listed.size():
		var item_v: Variant = listed[i]
		i += 1
		if typeof(item_v) != TYPE_DICTIONARY:
			continue
		var item: Dictionary = item_v
		var usage: int = int(item.get("usage", 0))
		var pname: String = str(item.get("name", ""))
		if pname.is_empty():
			continue
		var script_var: bool = (usage & PROPERTY_USAGE_SCRIPT_VARIABLE) == PROPERTY_USAGE_SCRIPT_VARIABLE
		var editor_var: bool = (usage & PROPERTY_USAGE_EDITOR) == PROPERTY_USAGE_EDITOR
		if not script_var and not _allowlisted_prop(pname):
			if not editor_var:
				continue
			if not _allowlisted_prop(pname):
				continue
		if not node.has_method("get"):
			continue
		if _is_secret_name(pname):
			out[pname] = REDACT
			continue
		out[pname] = _jsonable(node.get(pname))
	return out


func _allowlisted_prop(pname: String) -> bool:
	return (
		pname == "visible"
		or pname == "position"
		or pname == "rotation"
		or pname == "scale"
		or pname == "modulate"
		or pname == "process_mode"
		or pname == "z_index"
		or pname == "text"
	)


func _observe_of(node: Node) -> Dictionary:
	if not node.has_method("agent_observe"):
		return {}
	var raw: Variant = node.call("agent_observe")
	if typeof(raw) != TYPE_DICTIONARY:
		return {}
	return _redact_dict(raw)


func _groups_of(node: Node) -> Array:
	var out: Array = []
	var groups: PackedStringArray = node.get_groups()
	var i: int = 0
	while i < groups.size() and i < MAX_PAGE:
		out.append(str(groups[i]))
		i += 1
	return out


func _signals_of(node: Node) -> Array:
	var out: Array = []
	var listed: Array = node.get_signal_list()
	var i: int = 0
	while i < listed.size() and i < MAX_PAGE:
		var item_v: Variant = listed[i]
		i += 1
		if typeof(item_v) == TYPE_DICTIONARY:
			out.append(str((item_v as Dictionary).get("name", "")))
	return out


func _has_property(node: Node, key: String) -> bool:
	var listed: Array = node.get_property_list()
	var i: int = 0
	while i < listed.size():
		var item_v: Variant = listed[i]
		i += 1
		if typeof(item_v) == TYPE_DICTIONARY and str((item_v as Dictionary).get("name", "")) == key:
			return true
	return false


func _redact_dict(raw: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	var keys: Array = raw.keys()
	var ki: int = 0
	while ki < keys.size():
		var key: String = str(keys[ki])
		out[key] = _redact_value(key, raw[key])
		ki += 1
	return out


func _redact_value(key: String, value: Variant) -> Variant:
	if _is_secret_name(key):
		return REDACT
	return _jsonable(value)


func _is_secret_name(name_s: String) -> bool:
	var lower: String = name_s.to_lower()
	var i: int = 0
	while i < _secret_needles.size():
		if _secret_needles[i] in lower:
			return true
		i += 1
	return false


func _jsonable(value: Variant) -> Variant:
	var kind: int = typeof(value)
	if kind == TYPE_NIL or kind == TYPE_BOOL or kind == TYPE_INT or kind == TYPE_FLOAT or kind == TYPE_STRING:
		return value
	if kind == TYPE_STRING_NAME:
		return str(value)
	if kind == TYPE_VECTOR2:
		var v2: Vector2 = value
		return {"x": v2.x, "y": v2.y}
	if kind == TYPE_VECTOR2I:
		var v2i: Vector2i = value
		return {"x": v2i.x, "y": v2i.y}
	if kind == TYPE_COLOR:
		var c: Color = value
		return {"r": c.r, "g": c.g, "b": c.b, "a": c.a}
	if kind == TYPE_ARRAY:
		var arr: Array = []
		var src: Array = value
		var i: int = 0
		while i < src.size() and i < MAX_PAGE:
			arr.append(_jsonable(src[i]))
			i += 1
		return arr
	if kind == TYPE_DICTIONARY:
		return _redact_dict(value)
	return {"type": type_string(kind)}


func _payload_of(data: Array) -> Dictionary:
	if data.is_empty():
		return {}
	if typeof(data[0]) == TYPE_DICTIONARY:
		return data[0]
	if typeof(data[0]) == TYPE_STRING:
		var parsed: Variant = JSON.parse_string(str(data[0]))
		if parsed is Dictionary:
			return parsed
	return {}


func _limit_of(payload: Dictionary) -> int:
	var limit: int = 50
	if payload.has("limit"):
		limit = int(payload.get("limit"))
	if limit < 1:
		limit = 1
	if limit > MAX_PAGE:
		limit = MAX_PAGE
	return limit


func _offset_of(payload: Dictionary) -> int:
	if payload.has("offset"):
		return maxi(0, int(payload.get("offset")))
	if payload.has("cursor"):
		var raw: String = str(payload.get("cursor"))
		if raw.is_valid_int():
			return maxi(0, int(raw))
	return 0


func _merge(base: Dictionary, extra: Dictionary) -> Dictionary:
	var out: Dictionary = base.duplicate(true)
	var keys: Array = extra.keys()
	var ki: int = 0
	while ki < keys.size():
		out[keys[ki]] = extra[keys[ki]]
		ki += 1
	return out


func _input(event: InputEvent) -> void:
	_seen_flush = true
	_input_seen += 1


func _input_op(op: String, payload: Dictionary, base: Dictionary) -> Dictionary:
	var replay_fail: Dictionary = _replay_fail(payload)
	if not replay_fail.is_empty():
		return replay_fail
	if payload.get("internal", false) != true:
		var focus_fail: Dictionary = _focus_fail()
		if not focus_fail.is_empty():
			return focus_fail
	if op == "sequence" and _sequence_needs_wait(payload):
		_kick_sequence(payload, base)
		return {"async": true}
	if op == "release_all":
		return _do_release_all(str(payload.get("scope", "all")))
	if op == "sequence":
		return _apply_steps(payload.get("steps", []), true)
	return _apply_verb(op, payload)


func _kick_sequence(payload: Dictionary, base: Dictionary) -> void:
	_run_sequence(payload, base.duplicate(true))


func _run_sequence(payload: Dictionary, base: Dictionary) -> void:
	var extra: Dictionary = await _apply_steps_async(payload.get("steps", []))
	EngineDebugger.send_message("%s:reply" % CAPTURE, [JSON.stringify(_merge(base, extra))])


func _sequence_needs_wait(payload: Dictionary) -> bool:
	var steps_v: Variant = payload.get("steps", [])
	if not (steps_v is Array):
		return false
	var steps: Array = steps_v
	var i: int = 0
	while i < steps.size():
		var step_v: Variant = steps[i]
		i += 1
		if typeof(step_v) != TYPE_DICTIONARY:
			continue
		var step: Dictionary = step_v
		if int(step.get("delay_ms", 0)) > 0 or int(step.get("delay_ticks", 0)) > 0:
			return true
	return false


func _apply_steps_async(steps_v: Variant) -> Dictionary:
	var applied: int = 0
	var seen: bool = false
	if steps_v is Array:
		var steps: Array = steps_v
		var i: int = 0
		while i < steps.size():
			var step_v: Variant = steps[i]
			i += 1
			if typeof(step_v) != TYPE_DICTIONARY:
				continue
			var one: Dictionary = _apply_verb("action", step_v)
			if one.get("ok", false) == true:
				applied += 1
			if one.get("seen", false) == true:
				seen = true
			var ticks: int = int((step_v as Dictionary).get("delay_ticks", 0))
			var ms: int = int((step_v as Dictionary).get("delay_ms", 0))
			var tree: SceneTree = get_tree()
			while ticks > 0 and tree != null:
				await tree.process_frame
				ticks -= 1
			if ms > 0 and tree != null:
				await tree.create_timer(float(ms) / 1000.0).timeout
	return _input_ok(seen or applied > 0, applied, "sequence")


func _apply_steps(steps_v: Variant, _sync: bool) -> Dictionary:
	var applied: int = 0
	var seen: bool = false
	if steps_v is Array:
		var steps: Array = steps_v
		var i: int = 0
		while i < steps.size():
			var step_v: Variant = steps[i]
			i += 1
			if typeof(step_v) != TYPE_DICTIONARY:
				continue
			var one: Dictionary = _apply_verb("action", step_v)
			if one.get("ok", false) == true:
				applied += 1
			if one.get("seen", false) == true:
				seen = true
	return _input_ok(seen or applied > 0, applied, "sequence")


func _apply_verb(op: String, payload: Dictionary) -> Dictionary:
	var evs: Array = _events_of(op, payload)
	if evs.is_empty():
		return {
			"ok": false,
			"code": "E_INVALID_TYPE",
			"message": "could not build Play input event",
			"injected": false,
			"seen": false,
		}
	_seen_flush = false
	if op == "action":
		var action_name: String = str(payload.get("action_name", ""))
		if not action_name.is_empty():
			if str(payload.get("phase", "press")) != "release":
				Input.action_press(action_name, float(payload.get("strength", 1.0)))
			else:
				Input.action_release(action_name)
	var i: int = 0
	while i < evs.size():
		var ev_v: Variant = evs[i]
		i += 1
		if ev_v is InputEvent:
			Input.parse_input_event(ev_v as InputEvent)
	Input.flush_buffered_events()
	var seen: bool = _seen_flush
	return _input_ok(seen, evs.size(), op)


func _events_of(op: String, payload: Dictionary) -> Array:
	var out: Array = []
	if op == "action":
		if payload.has("axis"):
			var axis_ev: InputEventJoypadMotion = InputEventJoypadMotion.new()
			axis_ev.device = int(payload.get("device", 0))
			axis_ev.axis = int(payload.get("axis", 0)) as JoyAxis
			axis_ev.axis_value = float(payload.get("axis_value", 0.0))
			out.append(axis_ev)
			_hold_rec("axis:%s" % str(payload.get("axis", 0)), {
				"kind": "axis",
				"device": axis_ev.device,
				"axis": int(payload.get("axis", 0)),
			})
		if payload.has("button_index"):
			var joy: InputEventJoypadButton = InputEventJoypadButton.new()
			joy.device = int(payload.get("device", 0))
			joy.button_index = int(payload.get("button_index", 0)) as JoyButton
			joy.pressed = str(payload.get("phase", "press")) != "release"
			out.append(joy)
			_track("joy:%s" % str(payload.get("button_index", 0)), {
				"kind": "joy",
				"device": joy.device,
				"button_index": int(payload.get("button_index", 0)),
			}, joy.pressed)
		var action_name: String = str(payload.get("action_name", ""))
		if not action_name.is_empty():
			var act: InputEventAction = InputEventAction.new()
			act.action = action_name
			act.pressed = str(payload.get("phase", "press")) != "release"
			act.strength = float(payload.get("strength", 1.0 if act.pressed else 0.0))
			out.append(act)
			_track("action:%s" % action_name, {
				"kind": "action",
				"name": action_name,
			}, act.pressed)
		return out
	if op == "key":
		var code: int = _keycode_of(str(payload.get("keycode", "")))
		if code < 0:
			return out
		var key: InputEventKey = InputEventKey.new()
		key.keycode = code as Key
		key.physical_keycode = code as Key
		key.pressed = str(payload.get("phase", "press")) != "release"
		key.echo = false
		key.shift_pressed = payload.get("shift", false) == true
		key.ctrl_pressed = payload.get("ctrl", false) == true
		key.alt_pressed = payload.get("alt", false) == true
		key.meta_pressed = payload.get("meta", false) == true
		if key.pressed:
			if key.shift_pressed and code >= int(KEY_A) and code <= int(KEY_Z):
				key.unicode = code
			elif code >= int(KEY_A) and code <= int(KEY_Z):
				key.unicode = code + 32
			elif code == int(KEY_SPACE):
				key.unicode = 32
		out.append(key)
		_track("key:%s" % str(payload.get("keycode", "")), {
			"kind": "key",
			"keycode": code,
			"shift": key.shift_pressed,
			"ctrl": key.ctrl_pressed,
			"alt": key.alt_pressed,
			"meta": key.meta_pressed,
		}, key.pressed)
		return out
	if op == "mouse":
		var wheel: String = str(payload.get("wheel", ""))
		var phase: String = str(payload.get("phase", ""))
		var x: float = float(payload.get("x", 0))
		var y: float = float(payload.get("y", 0))
		var pos: Vector2 = Vector2(x, y)
		if phase == "motion" or (str(payload.get("button", "none")) == "none" and wheel.is_empty()):
			var motion: InputEventMouseMotion = InputEventMouseMotion.new()
			motion.position = pos
			motion.global_position = pos
			motion.relative = Vector2(float(payload.get("dx", 0)), float(payload.get("dy", 0)))
			out.append(motion)
			return out
		var btn: InputEventMouseButton = InputEventMouseButton.new()
		btn.position = pos
		btn.global_position = pos
		btn.pressed = phase != "release"
		if wheel == "up":
			btn.button_index = MOUSE_BUTTON_WHEEL_UP
		elif wheel == "down":
			btn.button_index = MOUSE_BUTTON_WHEEL_DOWN
		else:
			btn.button_index = _mouse_button_of(str(payload.get("button", "left")))
		out.append(btn)
		if (
			btn.button_index != MOUSE_BUTTON_WHEEL_UP
			and btn.button_index != MOUSE_BUTTON_WHEEL_DOWN
		):
			_track("mouse:%s" % str(payload.get("button", "left")), {
				"kind": "mouse",
				"button": str(payload.get("button", "left")),
				"x": x,
				"y": y,
			}, btn.pressed)
		return out
	if op == "touch":
		var touch: InputEventScreenTouch = InputEventScreenTouch.new()
		touch.index = int(payload.get("index", 0))
		touch.position = Vector2(float(payload.get("x", 0)), float(payload.get("y", 0)))
		touch.pressed = payload.get("pressed", true) == true
		out.append(touch)
		_track("touch:%s" % str(payload.get("index", 0)), {
			"kind": "touch",
			"index": touch.index,
			"x": touch.position.x,
			"y": touch.position.y,
		}, touch.pressed)
	return out


func _do_release_all(scope: String) -> Dictionary:
	var keys: Array = _held.keys()
	var i: int = 0
	_seen_flush = false
	while i < keys.size():
		var rec_v: Variant = _held[keys[i]]
		i += 1
		if typeof(rec_v) != TYPE_DICTIONARY:
			continue
		var rec: Dictionary = rec_v
		var kind: String = str(rec.get("kind", ""))
		if scope == "keyboard" and kind != "key" and kind != "action":
			continue
		if scope == "mouse" and kind != "mouse":
			continue
		_emit_release(rec)
	Input.flush_buffered_events()
	_held.clear()
	return {
		"ok": true,
		"injected": true,
		"released": true,
		"seen": true,
		"held": [],
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"focus": _window_focused(),
		"headless_input": _headless_label(),
		"time": _time_snap(),
	}


func _emit_release(rec: Dictionary) -> void:
	var kind: String = str(rec.get("kind", ""))
	if kind == "action":
		var act: InputEventAction = InputEventAction.new()
		act.action = str(rec.get("name", ""))
		act.pressed = false
		act.strength = 0.0
		if not act.action.is_empty():
			Input.action_release(act.action)
		Input.parse_input_event(act)
		return
	if kind == "key":
		var key: InputEventKey = InputEventKey.new()
		key.keycode = int(rec.get("keycode", 0)) as Key
		key.physical_keycode = key.keycode
		key.pressed = false
		key.shift_pressed = rec.get("shift", false) == true
		key.ctrl_pressed = rec.get("ctrl", false) == true
		key.alt_pressed = rec.get("alt", false) == true
		key.meta_pressed = rec.get("meta", false) == true
		Input.parse_input_event(key)
		return
	if kind == "mouse":
		var btn: InputEventMouseButton = InputEventMouseButton.new()
		btn.button_index = _mouse_button_of(str(rec.get("button", "left")))
		btn.position = Vector2(float(rec.get("x", 0)), float(rec.get("y", 0)))
		btn.global_position = btn.position
		btn.pressed = false
		Input.parse_input_event(btn)
		return
	if kind == "joy":
		var joy: InputEventJoypadButton = InputEventJoypadButton.new()
		joy.device = int(rec.get("device", 0))
		joy.button_index = int(rec.get("button_index", 0)) as JoyButton
		joy.pressed = false
		Input.parse_input_event(joy)
		return
	if kind == "axis":
		var axis_ev: InputEventJoypadMotion = InputEventJoypadMotion.new()
		axis_ev.device = int(rec.get("device", 0))
		axis_ev.axis = int(rec.get("axis", 0)) as JoyAxis
		axis_ev.axis_value = 0.0
		Input.parse_input_event(axis_ev)
		return
	if kind == "touch":
		var touch: InputEventScreenTouch = InputEventScreenTouch.new()
		touch.index = int(rec.get("index", 0))
		touch.position = Vector2(float(rec.get("x", 0)), float(rec.get("y", 0)))
		touch.pressed = false
		Input.parse_input_event(touch)


func _input_ok(seen: bool, count: int, op: String) -> Dictionary:
	var headless: bool = _is_headless()
	if not seen and not headless:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "Play process did not see parsed input in _input",
			"injected": count > 0,
			"seen": false,
			"source": "hh_agent_runtime",
			"held": _held_names(),
			"headless_input": _headless_label(),
			"focus": _window_focused(),
			"time": _time_snap(),
		}
	if not seen and headless:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "headless Play did not deliver game-window input; Alternative: exclusive GUI Godot --editor",
			"injected": count > 0,
			"seen": false,
			"source": "hh_agent_runtime",
			"held": _held_names(),
			"headless_input": "unproven",
			"focus": _window_focused(),
			"time": _time_snap(),
		}
	return {
		"ok": true,
		"injected": true,
		"released": op == "release_all",
		"seen": true,
		"count": count,
		"held": _held_names(),
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"focus": _window_focused(),
		"headless_input": _headless_label(),
		"input_seen": _input_seen,
		"time": _time_snap(),
	}


func _focus_fail() -> Dictionary:
	if _is_headless():
		return {}
	if _window_focused():
		return {}
	return {
		"ok": false,
		"code": "E_CONFLICT",
		"message": "focus loss: game window is not focused",
		"injected": false,
		"seen": false,
		"focus": false,
		"source": "hh_agent_runtime",
	}


func _replay_fail(payload: Dictionary) -> Dictionary:
	if payload.get("replay", false) != true:
		return {}
	var header_v: Variant = payload.get("header", {})
	if typeof(header_v) != TYPE_DICTIONARY:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: header missing",
			"injected": false,
		}
	var header: Dictionary = header_v
	var engine_s: String = str(header.get("engine", ""))
	var info: Dictionary = Engine.get_version_info()
	var hash_s: String = str(info.get("hash", ""))
	if hash_s.length() > 9:
		hash_s = hash_s.substr(0, 9)
	var live_engine: String = "%s.%s.%s.%s.%s.%s" % [
		str(info.get("major", 0)),
		str(info.get("minor", 0)),
		str(info.get("patch", 0)),
		str(info.get("status", "")),
		str(info.get("build", "")),
		hash_s,
	]
	if engine_s.is_empty() or engine_s != live_engine:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: engine header",
			"injected": false,
		}
	var want_run: String = str(header.get("run_id", ""))
	var live_run: String = str(payload.get("run_id", ""))
	if not want_run.is_empty() and not live_run.is_empty() and want_run != live_run:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: run_id header",
			"injected": false,
		}
	var want_project: String = str(header.get("project", ""))
	var live_project: String = _project_hash()
	if not want_project.is_empty() and not live_project.is_empty() and want_project != live_project:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: project header",
			"injected": false,
		}
	if header.has("seed") and int(header.get("seed", 0)) != 0:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: seed header (seed unpinned)",
			"injected": false,
		}
	if header.get("fixed_step", false) == true:
		return {
			"ok": false,
			"code": "E_CONFLICT",
			"message": "replay mismatch: fixed-step header (unpinned until later WP)",
			"injected": false,
		}
	return {}


func _project_hash() -> String:
	if not FileAccess.file_exists("res://project.godot"):
		return ""
	return FileAccess.get_sha256("res://project.godot")


func _window_focused() -> bool:
	if _is_headless():
		return true
	return DisplayServer.window_is_focused()


func _is_headless() -> bool:
	return str(DisplayServer.get_name()).to_lower() == "headless"


func _headless_label() -> String:
	if _is_headless():
		return "proven" if _seen_flush else "unproven"
	return "n/a"


func _track(key: String, rec: Dictionary, pressed: bool) -> void:
	if pressed:
		_held[key] = rec
	elif _held.has(key):
		_held.erase(key)


func _hold_rec(key: String, rec: Dictionary) -> void:
	_held[key] = rec


func _held_names() -> Array:
	var out: Array = []
	var keys: Array = _held.keys()
	var i: int = 0
	while i < keys.size():
		out.append(str(keys[i]))
		i += 1
	return out


func _mouse_button_of(name_s: String) -> MouseButton:
	if name_s == "right":
		return MOUSE_BUTTON_RIGHT
	if name_s == "middle":
		return MOUSE_BUTTON_MIDDLE
	return MOUSE_BUTTON_LEFT


func _keycode_of(name_s: String) -> int:
	if name_s == "KEY_SPACE":
		return KEY_SPACE
	if name_s == "KEY_ENTER":
		return KEY_ENTER
	if name_s == "KEY_ESCAPE":
		return KEY_ESCAPE
	if name_s == "KEY_LEFT":
		return KEY_LEFT
	if name_s == "KEY_RIGHT":
		return KEY_RIGHT
	if name_s == "KEY_UP":
		return KEY_UP
	if name_s == "KEY_DOWN":
		return KEY_DOWN
	if name_s.length() == 5 and name_s.begins_with("KEY_"):
		var ch: String = name_s.substr(4, 1)
		if ch >= "A" and ch <= "Z":
			return int(KEY_A) + (ch.unicode_at(0) - 65)
		if ch >= "0" and ch <= "9":
			return int(KEY_0) + (ch.unicode_at(0) - 48)
	return -1
