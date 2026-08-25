extends Node

## Debug-only Play autoload. Answers paged tree/node/state over the debugger
## channel. Never required on shipped games (export plugin skip() + no
## project.godot persist). Base Node2D works without agent_observe.

const CAPTURE: String = "hh_runtime"
const MAX_PAGE: int = 100
const REDACT: String = "***"
const HELLO_MS: int = 1000
const SHOT_DIR: String = ".hh-agent/r6w5"
const PINNED_ENGINE: String = "4.7.1.stable.official.a13da4feb"

var _last_hello_ms: int = 0
@export var dummy_secret: String = ""
@export var dummy_password: String = ""
@export var dummy_token: String = ""
@export var hp: int = 0
@export var spawn_count: int = 0
var _held: Dictionary = {}
var _seen_flush: bool = false
var _input_seen: int = 0
var _frozen: bool = false
var _seed: int = 0
var _seed_pinned: bool = false
var _fixed_step: bool = false
var _physics_hz: int = 0
var _events_subscribed: bool = false
var _event_count: int = 0
var _probe: Node
var _rng: RandomNumberGenerator
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
	_bind_clock()
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
		var snap: Dictionary = _time_snap()
		var extra: Dictionary = snap.duplicate(true)
		extra["ok"] = true
		extra["time"] = snap
		return _merge(base, extra)
	if op == "freeze" or op == "step":
		return _merge(base, _time_op(op, payload, base))
	if op == "screenshot" or op == "perf":
		return _merge(base, _capture_op(op, payload, base))
	if op == "assert":
		return _merge(base, _assert_op(payload))
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
		if _is_answer_map_name(key):
			return {
				"ok": true,
				"key": key,
				"found": true,
				"value": {"type": "PackedInt32Array"},
				"value_source": "property",
				"time": _time_snap(),
			}
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
	var tree: SceneTree = get_tree()
	var paused: bool = tree != null and tree.paused
	return {
		"ticks_msec": Time.get_ticks_msec(),
		"frames": Engine.get_process_frames(),
		"physics_frames": Engine.get_physics_frames(),
		"frozen": _frozen,
		"paused": paused,
		"seed": _seed,
		"seed_pinned": _seed_pinned,
		"fixed_step": _fixed_step,
		"physics_hz": _physics_hz,
		"events_subscribed": _events_subscribed,
		"event_count": _event_count,
		"probe_process": _probe_process(),
		"probe_physics": _probe_physics(),
		"editor_time_scale": false,
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
		if _is_answer_map_name(pname):
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
		or 		pname == "z_index"
		or pname == "text"
		or pname == "color"
		or pname == "size"
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


func _is_answer_map_name(name_s: String) -> bool:
	var lower: String = name_s.to_lower()
	return lower == "tiles" or lower == "revealed"


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
	if (
		kind == TYPE_PACKED_BYTE_ARRAY
		or kind == TYPE_PACKED_INT32_ARRAY
		or kind == TYPE_PACKED_INT64_ARRAY
	):
		return {"type": type_string(kind)}
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
	# OS window focus is reported on ACK. Agent parse_input_event /
	# action_press does not need the Play window focused. Only the
	# explicit editor_foreground steal path may return E_CONFLICT.
	if payload.get("editor_foreground", false) == true:
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
	return _input_ok(_seen_flush, evs.size(), op)


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
	if scope == "all" or scope == "keyboard":
		var mapped: PackedStringArray = InputMap.get_actions()
		var j: int = 0
		while j < mapped.size():
			var mapped_name: String = str(mapped[j])
			j += 1
			if Input.is_action_pressed(mapped_name):
				Input.action_release(mapped_name)
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


class TickProbe extends Node:
	signal physics_ticked

	var process_ticks: int = 0
	var physics_ticks: int = 0
	var arm_pause: bool = false

	func _ready() -> void:
		set_process(true)
		set_physics_process(true)

	func _process(_delta: float) -> void:
		process_ticks += 1

	func _physics_process(_delta: float) -> void:
		physics_ticks += 1
		physics_ticked.emit()
		if arm_pause:
			var tree: SceneTree = get_tree()
			if tree != null:
				tree.paused = true

	func agent_observe() -> Dictionary:
		return {
			"process_ticks": process_ticks,
			"physics_ticks": physics_ticks,
		}


func _bind_clock() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if _probe == null:
		_probe = TickProbe.new()
		_probe.name = "HHAgentTickProbe"
		_probe.process_mode = Node.PROCESS_MODE_PAUSABLE
		add_child(_probe)
	var tree: SceneTree = get_tree()
	if tree != null and not tree.node_added.is_connected(_on_tree_node_added):
		tree.node_added.connect(_on_tree_node_added)
		_events_subscribed = true
	_pin_descendants()


func _on_tree_node_added(node: Node) -> void:
	_event_count += 1
	if node == self or node == _probe:
		return
	if not _is_under_self(node):
		return
	if node.process_mode == Node.PROCESS_MODE_INHERIT:
		node.process_mode = Node.PROCESS_MODE_PAUSABLE


func _is_under_self(node: Node) -> bool:
	var cur: Node = node
	while cur != null:
		if cur == self:
			return true
		cur = cur.get_parent()
	return false


func _pin_descendants() -> void:
	var nodes: Array = _flatten()
	var i: int = 0
	while i < nodes.size():
		var node_v: Variant = nodes[i]
		i += 1
		if not (node_v is Node):
			continue
		var node: Node = node_v
		if node == self or node == _probe:
			continue
		if not _is_under_self(node):
			continue
		if node.process_mode == Node.PROCESS_MODE_INHERIT:
			node.process_mode = Node.PROCESS_MODE_PAUSABLE


func _probe_process() -> int:
	if _probe == null or not (_probe is TickProbe):
		return -1
	return (_probe as TickProbe).process_ticks


func _probe_physics() -> int:
	if _probe == null or not (_probe is TickProbe):
		return -1
	return (_probe as TickProbe).physics_ticks


func _pin_seed(seed_v: int) -> void:
	_seed = seed_v
	_seed_pinned = true
	seed(seed_v)
	if _rng == null:
		_rng = RandomNumberGenerator.new()
	_rng.seed = seed_v


func _pin_physics(ticks: int) -> void:
	if ticks < 1:
		ticks = 60
	if ticks > 240:
		ticks = 240
	Engine.physics_ticks_per_second = ticks
	Engine.max_physics_steps_per_frame = 1
	_physics_hz = ticks
	_fixed_step = true


func _time_op(op: String, payload: Dictionary, base: Dictionary) -> Dictionary:
	if op == "freeze":
		return _freeze_op(payload, base)
	return _step_op(payload, base)


func _apply_pins(payload: Dictionary) -> void:
	if payload.has("seed"):
		_pin_seed(int(payload.get("seed", 0)))
	if payload.has("physics_ticks"):
		_pin_physics(int(payload.get("physics_ticks", 60)))


func _freeze_op(payload: Dictionary, base: Dictionary) -> Dictionary:
	var want: bool = payload.get("frozen", true) == true
	_apply_pins(payload)
	if want and not _fixed_step:
		_pin_physics(60)
	_frozen = want
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = want
	_pin_descendants()
	if want:
		_kick_freeze_proof(base)
		return {"async": true}
	return _freeze_reply(false, _probe_physics(), _probe_physics(), true)


func _kick_freeze_proof(base: Dictionary) -> void:
	_run_freeze_proof(base.duplicate(true))


func _run_freeze_proof(base: Dictionary) -> void:
	var t0: int = _probe_physics()
	var p0: int = _probe_process()
	var tree: SceneTree = get_tree()
	if tree != null:
		# ignore_pause so this is not a running-game observation race.
		await tree.create_timer(0.04, true, true, true).timeout
	var t1: int = _probe_physics()
	var p1: int = _probe_process()
	var observed: bool = t1 == t0 and p1 == p0
	var extra: Dictionary = _freeze_reply(true, t0, t1, observed)
	EngineDebugger.send_message("%s:reply" % CAPTURE, [JSON.stringify(_merge(base, extra))])


func _freeze_reply(frozen: bool, before_n: int, after_n: int, observed: bool) -> Dictionary:
	var tree: SceneTree = get_tree()
	var paused: bool = tree != null and tree.paused
	var ok: bool = true
	var code: String = ""
	var message: String = ""
	if frozen and not observed:
		ok = false
		code = "E_UNVERIFIED"
		message = "Play freeze did not stop pausable ticks"
	if frozen and not paused:
		ok = false
		code = "E_UNVERIFIED"
		message = "Play SceneTree.paused was not set"
	var out: Dictionary = {
		"ok": ok,
		"frozen": frozen,
		"paused": paused,
		"observed_frozen": observed and frozen,
		"probe_before": before_n,
		"probe_after": after_n,
		"probe_process": _probe_process(),
		"probe_physics": _probe_physics(),
		"seed": _seed,
		"seed_pinned": _seed_pinned,
		"fixed_step": _fixed_step,
		"physics_hz": _physics_hz,
		"events_subscribed": _events_subscribed,
		"event_count": _event_count,
		"editor_time_scale": false,
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"time": _time_snap(),
	}
	if not ok:
		out["code"] = code
		out["message"] = message
	return out


func _step_op(payload: Dictionary, base: Dictionary) -> Dictionary:
	_apply_pins(payload)
	var pred_v: Variant = payload.get("until", {})
	var has_until: bool = typeof(pred_v) == TYPE_DICTIONARY and not (pred_v as Dictionary).is_empty()
	if has_until:
		var pred_err: Dictionary = _predicate_shape_fail(pred_v as Dictionary)
		if not pred_err.is_empty():
			return pred_err
	_kick_step(payload, base)
	return {"async": true}


func _kick_step(payload: Dictionary, base: Dictionary) -> void:
	_run_step(payload, base.duplicate(true))


func _run_step(payload: Dictionary, base: Dictionary) -> void:
	var extra: Dictionary = await _step_async(payload)
	EngineDebugger.send_message("%s:reply" % CAPTURE, [JSON.stringify(_merge(base, extra))])


func _step_async(payload: Dictionary) -> Dictionary:
	var frames: int = maxi(1, int(payload.get("frames", 1)))
	if payload.has("ms") and not payload.has("until"):
		var hz: int = _physics_hz
		if hz < 1:
			hz = Engine.physics_ticks_per_second
		if hz < 1:
			hz = 60
		frames = maxi(1, int(ceil(float(int(payload.get("ms", 1))) * float(hz) / 1000.0)))
	var pred_v: Variant = payload.get("until", {})
	var has_until: bool = typeof(pred_v) == TYPE_DICTIONARY and not (pred_v as Dictionary).is_empty()
	var timeout_ms: int = int(payload.get("timeout_ms", 2000 if has_until else 20000))
	if timeout_ms < 50:
		timeout_ms = 50
	var before: int = _probe_physics()
	var fixture_before: int = _fixture_physics(payload)
	var started_ms: int = Time.get_ticks_msec()
	if has_until:
		var pred: Dictionary = pred_v as Dictionary
		var first: Dictionary = _eval_predicate(pred)
		if first.get("ok", false) == true and first.get("matched", false) == true:
			return _step_reply(true, 0, before, _probe_physics(), fixture_before, true, false, "")
		var advanced: int = 0
		while Time.get_ticks_msec() - started_ms < timeout_ms:
			var one: int = await _step_physics(frames)
			advanced += one
			var now: Dictionary = _eval_predicate(pred)
			if now.get("ok", false) != true:
				return now
			if now.get("matched", false) == true:
				return _step_reply(true, advanced, before, _probe_physics(), fixture_before, true, false, "")
		return {
			"ok": false,
			"code": "E_TIMEOUT",
			"message": "step-until missed event: predicate never matched",
			"missed_event": true,
			"stepped": false,
			"matched": false,
			"frames_advanced": advanced,
			"probe_before": before,
			"probe_after": _probe_physics(),
			"editor_time_scale": false,
			"source": "hh_agent_runtime",
			"frozen": _frozen,
			"paused": get_tree() != null and get_tree().paused,
			"events_subscribed": _events_subscribed,
			"time": _time_snap(),
		}
	var advanced_n: int = await _step_physics(frames)
	var after_n: int = _probe_physics()
	var observed: int = after_n - before
	if observed < 1 and advanced_n < 1:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "Play step did not advance a pausable physics counter",
			"stepped": false,
			"frames_advanced": 0,
			"probe_before": before,
			"probe_after": after_n,
			"editor_time_scale": false,
			"source": "hh_agent_runtime",
			"time": _time_snap(),
		}
	return _step_reply(true, maxi(observed, advanced_n), before, after_n, fixture_before, false, false, "")


func _step_physics(frames: int) -> int:
	var tree: SceneTree = get_tree()
	if tree == null:
		return 0
	var start: int = _probe_physics()
	var i: int = 0
	while i < frames:
		await _step_one_physics()
		i += 1
	if _frozen:
		tree.paused = true
	return maxi(0, _probe_physics() - start)


func _step_one_physics() -> void:
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	var start: int = _probe_physics()
	if _probe is TickProbe:
		(_probe as TickProbe).arm_pause = true
	tree.paused = false
	var started_ms: int = Time.get_ticks_msec()
	# Poll process_frame (root is PROCESS_MODE_ALWAYS). A missed signal
	# must not hang the debugger capture. arm_pause re-pauses on the
	# same physics callback.
	while _probe_physics() <= start and Time.get_ticks_msec() - started_ms < 2000:
		await tree.process_frame
	tree.paused = true
	if _probe is TickProbe:
		(_probe as TickProbe).arm_pause = false


func _step_reply(
	ok: bool,
	advanced: int,
	before_n: int,
	after_n: int,
	fixture_before: int,
	matched: bool,
	_missed: bool,
	_message: String,
) -> Dictionary:
	return {
		"ok": ok,
		"stepped": ok and (advanced >= 1 or matched),
		"frames_advanced": advanced,
		"matched": matched,
		"missed_event": false,
		"probe_before": before_n,
		"probe_after": after_n,
		"fixture_before": fixture_before,
		"fixture_after": _fixture_physics({}),
		"frozen": _frozen,
		"paused": get_tree() != null and get_tree().paused,
		"seed": _seed,
		"seed_pinned": _seed_pinned,
		"fixed_step": _fixed_step,
		"physics_hz": _physics_hz,
		"events_subscribed": _events_subscribed,
		"event_count": _event_count,
		"editor_time_scale": false,
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"time": _time_snap(),
	}


func _fixture_physics(payload: Dictionary) -> int:
	var path_s: String = str(payload.get("node_path", "Fixture"))
	var node: Node = _resolve(path_s)
	if node == null:
		node = _resolve("/root")
	if node == null:
		return _probe_physics()
	var obs: Dictionary = _observe_of(node)
	if obs.has("physics_ticks"):
		return int(obs.get("physics_ticks"))
	if _has_property(node, "physics_ticks"):
		return int(node.get("physics_ticks"))
	return _probe_physics()


func _predicate_shape_fail(pred: Dictionary) -> Dictionary:
	var key: String = str(pred.get("key", ""))
	if key.is_empty() or not _ident_ok(key):
		return {
			"ok": false,
			"code": "E_INVALID_TYPE",
			"message": "predicate key is not an allowlisted identifier",
		}
	var op: String = str(pred.get("op", ""))
	if (
		op != "eq"
		and op != "neq"
		and op != "gt"
		and op != "gte"
		and op != "lt"
		and op != "lte"
	):
		return {
			"ok": false,
			"code": "E_INVALID_TYPE",
			"message": "predicate op is not allowlisted",
		}
	var n: int = 0
	if pred.has("value_int"):
		n += 1
	if pred.has("value_bool"):
		n += 1
	if pred.has("value_string"):
		n += 1
	if n != 1:
		return {
			"ok": false,
			"code": "E_INVALID_TYPE",
			"message": "predicate needs exactly one of value_int/value_bool/value_string",
		}
	return {}


func _ident_ok(name_s: String) -> bool:
	if name_s.is_empty():
		return false
	var i: int = 0
	while i < name_s.length():
		var code: int = name_s.unicode_at(i)
		var ok_ch: bool = (
			(code >= 65 and code <= 90)
			or (code >= 97 and code <= 122)
			or code == 95
			or (i > 0 and code >= 48 and code <= 57)
		)
		if not ok_ch:
			return false
		i += 1
	return true


func _eval_predicate(pred: Dictionary) -> Dictionary:
	# Allowlisted compare only. Never eval / Expression / GDScript inject.
	var shape: Dictionary = _predicate_shape_fail(pred)
	if not shape.is_empty():
		return shape
	var key: String = str(pred.get("key", ""))
	var op: String = str(pred.get("op", "eq"))
	var path_s: String = str(pred.get("node_path", "Fixture"))
	var node: Node = _resolve(path_s)
	if node == null:
		return {"ok": true, "matched": false, "found": false, "key": key}
	var got_v: Variant = null
	var found: bool = false
	var obs: Dictionary = _observe_of(node)
	if obs.has(key):
		got_v = obs[key]
		found = true
	elif _has_property(node, key):
		got_v = node.get(key)
		found = true
	if not found:
		return {"ok": true, "matched": false, "found": false, "key": key}
	var want_v: Variant = null
	if pred.has("value_int"):
		want_v = int(pred.get("value_int"))
	elif pred.has("value_bool"):
		want_v = pred.get("value_bool") == true
	else:
		want_v = str(pred.get("value_string", ""))
	var matched: bool = _compare_pred(got_v, op, want_v)
	return {
		"ok": true,
		"matched": matched,
		"found": true,
		"key": key,
		"got": _jsonable(got_v),
	}


func _compare_pred(got_v: Variant, op: String, want_v: Variant) -> bool:
	var gt: int = typeof(got_v)
	var wt: int = typeof(want_v)
	if wt == TYPE_BOOL:
		if gt != TYPE_BOOL:
			return false
		var gb: bool = got_v
		var wb: bool = want_v
		if op == "eq":
			return gb == wb
		if op == "neq":
			return gb != wb
		return false
	if wt == TYPE_STRING:
		if gt != TYPE_STRING:
			return false
		var gs: String = got_v
		var ws: String = want_v
		if op == "eq":
			return gs == ws
		if op == "neq":
			return gs != ws
		return false
	if wt == TYPE_INT or wt == TYPE_FLOAT:
		if gt != TYPE_INT and gt != TYPE_FLOAT:
			return false
		var gi: int = int(got_v)
		var wi: int = int(want_v)
		if op == "eq":
			return gi == wi
		if op == "neq":
			return gi != wi
		if op == "gt":
			return gi > wi
		if op == "gte":
			return gi >= wi
		if op == "lt":
			return gi < wi
		if op == "lte":
			return gi <= wi
	return false


func _capture_op(op: String, payload: Dictionary, base: Dictionary) -> Dictionary:
	_kick_capture(op, payload, base)
	return {"async": true}


func _kick_capture(op: String, payload: Dictionary, base: Dictionary) -> void:
	_run_capture(op, payload, base.duplicate(true))


func _run_capture(op: String, payload: Dictionary, base: Dictionary) -> void:
	var extra: Dictionary = await _capture_async(op, payload)
	EngineDebugger.send_message("%s:reply" % CAPTURE, [JSON.stringify(_merge(base, extra))])


func _capture_async(op: String, payload: Dictionary) -> Dictionary:
	var stable: Dictionary = await _wait_stable(maxi(1, int(payload.get("stable_frames", 2))))
	if op == "perf":
		return await _perf_async(payload, stable)
	return await _screenshot_async(payload, stable)


func _wait_stable(frames: int) -> Dictionary:
	# Frame wait then two blits. Not sleep 2s. Not a stamped true.
	var tree: SceneTree = get_tree()
	var start_f: int = Engine.get_process_frames()
	var waited: int = 0
	while waited < frames and tree != null:
		await tree.process_frame
		waited += 1
	var first: Image = _viewport_image(1.0)
	if tree != null:
		await tree.process_frame
		waited += 1
	var second: Image = _viewport_image(1.0)
	var h0: String = _sample_hash(first)
	var h1: String = _sample_hash(second)
	var pixel_stable: bool = not h0.is_empty() and h0 == h1
	return {
		"stable": pixel_stable,
		"pixel_stable": pixel_stable,
		"frames_waited": waited,
		"frames": Engine.get_process_frames(),
		"frames_before": start_f,
		"used_sleep": false,
		"frozen": _frozen,
	}


func _screenshot_async(payload: Dictionary, stable: Dictionary) -> Dictionary:
	var target: String = str(payload.get("target", "game"))
	if target != "game":
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "editor viewport blit is not owned by hh_agent_runtime; use target=game",
			"dummy": false,
			"source": "hh_agent_runtime",
			"playing": true,
			"is_playing_scene": true,
			"screenshot_artifact_present": false,
			"stable": stable,
			"time": _time_snap(),
		}
	if _is_headless():
		var headless_img: Image = _viewport_image(float(payload.get("scale", 1.0)))
		if headless_img == null or not _is_real_blit(headless_img):
			return {
				"ok": false,
				"code": "E_UNVERIFIED",
				"message": "headless DisplayServer cannot blit a Play viewport",
				"headless_shot": "Alternative",
				"dummy": false,
				"source": "hh_agent_runtime",
				"playing": true,
				"is_playing_scene": true,
				"screenshot_artifact_present": false,
				"stable": stable,
				"time": _time_snap(),
			}
	var img: Image = _viewport_image(float(payload.get("scale", 1.0)))
	if img == null or not _is_real_blit(img):
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "Play viewport blit was empty; refusing dummy PNG",
			"dummy": false,
			"source": "hh_agent_runtime",
			"playing": true,
			"is_playing_scene": true,
			"screenshot_artifact_present": false,
			"stable": stable,
			"time": _time_snap(),
		}
	var region: Dictionary = _region_mean(img, payload)
	var token: String = str(payload.get("token", ""))
	if token.is_empty():
		token = str(Time.get_ticks_msec())
	var rel_path: String = "%s/shot_%s.png" % [SHOT_DIR, token.substr(0, 12)]
	var saved: Dictionary = _save_png(img, "res://%s" % rel_path)
	if saved.get("ok", false) != true:
		return saved
	var update_b: bool = payload.get("update_baseline", false) == true
	var reviewed: bool = payload.get("reviewed", false) == true
	var compare: bool = payload.get("compare", false) == true or payload.has("baseline")
	if update_b and not reviewed:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "baseline update requires explicit reviewed action",
			"dummy": false,
			"path": str(saved.get("path", "")),
			"bytes": int(saved.get("bytes", 0)),
			"screenshot_artifact_present": true,
			"source": "hh_agent_runtime",
			"playing": true,
			"is_playing_scene": true,
			"stable": stable,
			"time": _time_snap(),
		}
	if update_b and reviewed:
		var base_path: String = _baseline_path_of(payload)
		var copied: Dictionary = _save_png(img, base_path)
		if copied.get("ok", false) != true:
			return copied
		return _shot_ok(saved, stable, img, _merge({
			"baseline": base_path,
			"baseline_updated": true,
			"reviewed": true,
			"visual_pass": true,
			"bit_exact": false,
		}, region))
	if compare:
		var base_path: String = _baseline_path_of(payload)
		var want: Image = _load_png(base_path)
		if want == null:
			return {
				"ok": false,
				"code": "E_UNVERIFIED",
				"message": "missing baseline",
				"dummy": false,
				"path": str(saved.get("path", "")),
				"bytes": int(saved.get("bytes", 0)),
				"screenshot_artifact_present": true,
				"baseline": base_path,
				"source": "hh_agent_runtime",
				"playing": true,
				"is_playing_scene": true,
				"stable": stable,
				"time": _time_snap(),
			}
		var diff: Dictionary = _diff_images(img, want, payload)
		if diff.get("visual_pass", false) != true:
			return _merge({
				"ok": false,
				"code": "E_UNVERIFIED",
				"message": "visual diff failed",
				"dummy": false,
				"path": str(saved.get("path", "")),
				"bytes": int(saved.get("bytes", 0)),
				"screenshot_artifact_present": true,
				"baseline": base_path,
				"visual_pass": false,
				"bit_exact": false,
				"diff": diff,
				"source": "hh_agent_runtime",
				"playing": true,
				"is_playing_scene": true,
				"stable": stable,
				"time": _time_snap(),
			}, region)
		return _shot_ok(saved, stable, img, _merge({
			"baseline": base_path,
			"visual_pass": true,
			"bit_exact": false,
			"diff": diff,
		}, region))
	return _shot_ok(saved, stable, img, region)


func _shot_ok(saved: Dictionary, stable: Dictionary, img: Image, extra: Dictionary) -> Dictionary:
	var out: Dictionary = {
		"ok": true,
		"dummy": false,
		"path": str(saved.get("path", "")),
		"abs_path": str(saved.get("abs_path", "")),
		"bytes": int(saved.get("bytes", 0)),
		"width": img.get_width(),
		"height": img.get_height(),
		"hash": str(saved.get("hash", "")),
		"screenshot_artifact_present": true,
		"bit_exact": false,
		"luminance_span": _blit_span(img),
		"region_mean_r": 0.0,
		"region_mean_g": 0.0,
		"region_mean_b": 0.0,
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"stable": stable,
		"headless_shot": (
			"proven"
			if _is_headless() and _blit_span(img) > 0.05
			else ("Alternative" if _is_headless() else "n/a")
		),
		"time": _time_snap(),
	}
	return _merge(out, extra)


func _viewport_image(scale: float) -> Image:
	var vp: Viewport = get_viewport()
	if vp == null:
		return null
	var tex: ViewportTexture = vp.get_texture()
	if tex == null:
		return null
	var img: Image = tex.get_image()
	if img == null or img.is_empty():
		return null
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	if scale > 0.0 and absf(scale - 1.0) > 0.001:
		var w: int = maxi(1, int(round(float(img.get_width()) * scale)))
		var h: int = maxi(1, int(round(float(img.get_height()) * scale)))
		img.resize(w, h, Image.INTERPOLATE_BILINEAR)
	return img


func _sample_hash(img: Image) -> String:
	if img == null or img.is_empty():
		return ""
	var acc: int = img.get_width() * 131 + img.get_height()
	var step_x: int = maxi(1, int(img.get_width() / 16))
	var step_y: int = maxi(1, int(img.get_height() / 16))
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			acc = (acc * 33 + int(c.r * 255.0) + int(c.g * 255.0) * 3 + int(c.b * 255.0) * 7) % 2147483647
			x += step_x
		y += step_y
	return "%08x" % acc


func _region_mean(img: Image, payload: Dictionary) -> Dictionary:
	var rx: int = int(payload.get("region_x", 0))
	var ry: int = int(payload.get("region_y", 0))
	var rw: int = int(payload.get("region_w", img.get_width()))
	var rh: int = int(payload.get("region_h", img.get_height()))
	if rx < 0:
		rx = 0
	if ry < 0:
		ry = 0
	if rx + rw > img.get_width():
		rw = img.get_width() - rx
	if ry + rh > img.get_height():
		rh = img.get_height() - ry
	var n: int = 0
	var sr: float = 0.0
	var sg: float = 0.0
	var sb: float = 0.0
	if rw > 0 and rh > 0:
		var step: int = maxi(1, int(mini(rw, rh) / 16))
		var y: int = ry
		while y < ry + rh:
			var x: int = rx
			while x < rx + rw:
				var c: Color = img.get_pixel(x, y)
				sr += c.r
				sg += c.g
				sb += c.b
				n += 1
				x += step
			y += step
	if n < 1:
		return {"region_mean_r": 0.0, "region_mean_g": 0.0, "region_mean_b": 0.0, "region_samples": 0}
	return {
		"region_mean_r": sr / float(n),
		"region_mean_g": sg / float(n),
		"region_mean_b": sb / float(n),
		"region_samples": n,
	}


func _blit_span(img: Image) -> float:
	if img == null or img.is_empty():
		return 0.0
	var min_l: float = 1.0
	var max_l: float = 0.0
	var step_x: int = maxi(1, int(img.get_width() / 16))
	var step_y: int = maxi(1, int(img.get_height() / 16))
	var y: int = 0
	while y < img.get_height():
		var x: int = 0
		while x < img.get_width():
			var c: Color = img.get_pixel(x, y)
			var lum: float = (c.r + c.g + c.b) / 3.0
			if lum < min_l:
				min_l = lum
			if lum > max_l:
				max_l = lum
			x += step_x
		y += step_y
	return max_l - min_l


func _is_real_blit(img: Image) -> bool:
	if img == null or img.is_empty():
		return false
	if img.get_width() < 16 or img.get_height() < 16:
		return false
	# Flat or near-black frames are not a Play viewport blit.
	return _blit_span(img) > 0.05


func _save_png(img: Image, res_path: String) -> Dictionary:
	var jailed: String = _artifact_jail(res_path)
	if jailed.is_empty():
		return {
			"ok": false,
			"code": "E_PATH",
			"message": "screenshot path is outside .hh-agent/ or r6w5/ or r6w6/",
			"dummy": false,
		}
	var abs_path: String = ProjectSettings.globalize_path(jailed)
	var dir_s: String = abs_path.get_base_dir()
	var mk: Error = DirAccess.make_dir_recursive_absolute(dir_s)
	if mk != OK and not DirAccess.dir_exists_absolute(dir_s):
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "could not create screenshot directory",
			"dummy": false,
		}
	var err: Error = img.save_png(abs_path)
	if err != OK:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "viewport image save_png failed",
			"dummy": false,
		}
	if not FileAccess.file_exists(abs_path):
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "screenshot file missing after save",
			"dummy": false,
		}
	var bytes: int = FileAccess.get_file_as_bytes(abs_path).size()
	if bytes < 32:
		return {
			"ok": false,
			"code": "E_UNVERIFIED",
			"message": "captured PNG too small; refusing dummy",
			"dummy": false,
		}
	return {
		"ok": true,
		"path": jailed,
		"abs_path": abs_path,
		"bytes": bytes,
		"hash": FileAccess.get_sha256(abs_path),
	}


func _load_png(res_path: String) -> Image:
	var jailed: String = _artifact_jail(res_path)
	if jailed.is_empty():
		return null
	var abs_path: String = ProjectSettings.globalize_path(jailed)
	if not FileAccess.file_exists(abs_path) and not FileAccess.file_exists(jailed):
		return null
	var img: Image = Image.new()
	var err: Error = img.load(abs_path if FileAccess.file_exists(abs_path) else jailed)
	if err != OK or img.is_empty():
		return null
	if img.get_format() != Image.FORMAT_RGBA8:
		img.convert(Image.FORMAT_RGBA8)
	return img


func _baseline_path_of(payload: Dictionary) -> String:
	var raw: String = str(payload.get("baseline", ""))
	if raw.is_empty():
		return "res://r6w5/baselines/default.png"
	if raw.begins_with("res://"):
		return raw
	if not _ident_ok(raw):
		return "res://r6w5/baselines/default.png"
	return "res://r6w5/baselines/%s.png" % raw


func _artifact_jail(path_s: String) -> String:
	var p: String = path_s.strip_edges().replace("\\", "/")
	if p.is_empty():
		return ""
	if not p.begins_with("res://"):
		if p.begins_with(".hh-agent/") or p.begins_with("r6w5/") or p.begins_with("r6w6/"):
			p = "res://%s" % p
		else:
			return ""
	var rest: String = p.substr(6)
	var parts: PackedStringArray = rest.split("/")
	var i: int = 0
	while i < parts.size():
		if parts[i] == "..":
			return ""
		i += 1
	if rest.begins_with(".hh-agent/") or rest.begins_with("r6w5/") or rest.begins_with("r6w6/"):
		return p
	return ""


func _diff_images(got: Image, want: Image, payload: Dictionary) -> Dictionary:
	# GPU variance: region/mask/tolerance. Never claim bit-exact.
	if got.get_width() != want.get_width() or got.get_height() != want.get_height():
		return {
			"visual_pass": false,
			"compared": 0,
			"mismatched": 0,
			"mismatch_ratio": 1.0,
			"max_delta": 1.0,
			"tolerance": 0.0,
			"bit_exact": false,
			"message": "baseline size mismatch",
		}
	var tolerance: float = 0.08
	if payload.has("tolerance"):
		tolerance = clampf(float(payload.get("tolerance")), 0.0, 1.0)
	var rx: int = 0
	var ry: int = 0
	var rw: int = got.get_width()
	var rh: int = got.get_height()
	if payload.has("region_w") and payload.has("region_h"):
		rx = maxi(0, int(payload.get("region_x", 0)))
		ry = maxi(0, int(payload.get("region_y", 0)))
		rw = maxi(1, int(payload.get("region_w")))
		rh = maxi(1, int(payload.get("region_h")))
	if rx >= got.get_width() or ry >= got.get_height():
		return {"visual_pass": false, "compared": 0, "mismatched": 0, "max_delta": 1.0, "tolerance": tolerance}
	rw = mini(rw, got.get_width() - rx)
	rh = mini(rh, got.get_height() - ry)
	var mx: int = -1
	var my: int = -1
	var mw: int = 0
	var mh: int = 0
	if payload.has("mask_w") and payload.has("mask_h"):
		mx = int(payload.get("mask_x", 0))
		my = int(payload.get("mask_y", 0))
		mw = int(payload.get("mask_w"))
		mh = int(payload.get("mask_h"))
	var compared: int = 0
	var mismatched: int = 0
	var max_delta: float = 0.0
	var y: int = ry
	while y < ry + rh:
		var x: int = rx
		while x < rx + rw:
			var masked: bool = mx >= 0 and x >= mx and x < mx + mw and y >= my and y < my + mh
			if not masked:
				var gc: Color = got.get_pixel(x, y)
				var wx: int = x
				var wy: int = y
				if wx >= want.get_width():
					wx = want.get_width() - 1
				if wy >= want.get_height():
					wy = want.get_height() - 1
				if wx < 0 or wy < 0:
					mismatched += 1
					compared += 1
				else:
					var wc: Color = want.get_pixel(wx, wy)
					var d: float = maxf(maxf(absf(gc.r - wc.r), absf(gc.g - wc.g)), absf(gc.b - wc.b))
					if d > max_delta:
						max_delta = d
					compared += 1
					if d > tolerance:
						mismatched += 1
			x += 1
		y += 1
	var ratio: float = 0.0
	if compared > 0:
		ratio = float(mismatched) / float(compared)
	return {
		"visual_pass": compared > 0 and ratio <= 0.02 and max_delta <= tolerance + 0.02,
		"compared": compared,
		"mismatched": mismatched,
		"mismatch_ratio": ratio,
		"max_delta": max_delta,
		"tolerance": tolerance,
		"bit_exact": false,
		"region": {"x": rx, "y": ry, "w": rw, "h": rh},
	}


func _perf_async(payload: Dictionary, stable: Dictionary) -> Dictionary:
	var warmup: int = maxi(0, int(payload.get("warmup_frames", 4)))
	var samples_n: int = maxi(1, int(payload.get("samples", 12)))
	var tree: SceneTree = get_tree()
	var was_paused: bool = tree != null and tree.paused
	if tree != null:
		tree.paused = false
	var fixture: Node = _resolve("Fixture")
	if fixture != null:
		fixture.set("last_spike_elapsed_ms", 0)
		if payload.get("inject_spike", false) == true:
			fixture.set("spike_ms", 50)
		else:
			fixture.set("spike_ms", 0)
	var i: int = 0
	while i < warmup and tree != null:
		await tree.process_frame
		i += 1
	var series: Array = []
	var process_ms: Array = []
	var fps_s: Array = []
	var mem_s: Array = []
	i = 0
	while i < samples_n and tree != null:
		var one: Dictionary = _perf_sample()
		series.append(one)
		if one.get("time_process_ms_status", "") == "computed":
			process_ms.append(float(one.get("time_process_ms", 0.0)))
		if one.get("fps_status", "") == "computed":
			fps_s.append(float(one.get("fps", 0.0)))
		if one.get("memory_static_status", "") == "computed":
			mem_s.append(int(one.get("memory_static", 0)))
		await tree.process_frame
		i += 1
	var fixture_elapsed: int = 0
	if fixture != null:
		fixture_elapsed = int(fixture.get("last_spike_elapsed_ms"))
		fixture.set("spike_ms", 0)
	if was_paused and tree != null:
		tree.paused = true
	var p95: Dictionary = _p95(process_ms)
	var spike: Dictionary = _spike_of(process_ms)
	var counters_present: bool = series.size() > 0
	var out: Dictionary = {
		"ok": counters_present,
		"dummy": false,
		"perf_counters_present": counters_present,
		"warmup_frames": warmup,
		"samples": series.size(),
		"series": series if str(payload.get("detail", "short")) == "full" else series.slice(0, mini(4, series.size())),
		"p95_process_ms": p95,
		"spike": spike,
		"fixture_spike_elapsed_ms": fixture_elapsed,
		"fps": _p95(fps_s),
		"memory": {
			"static_last": mem_s[mem_s.size() - 1] if mem_s.size() > 0 else 0,
			"status": "computed" if mem_s.size() > 0 else "Alternative",
		},
		"hardware_manifest": _hardware_manifest(),
		"stable": stable,
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"time": _time_snap(),
	}
	if not counters_present:
		out["code"] = "E_UNVERIFIED"
		out["message"] = "Play perf counters were not present"
		return out
	if payload.has("budget_ms"):
		var budget: float = float(payload.get("budget_ms"))
		var spike_v: float = float(spike.get("value", 0.0))
		var inject: bool = payload.get("inject_spike", false) == true
		if inject and fixture_elapsed < 40:
			out["ok"] = false
			out["code"] = "E_UNVERIFIED"
			out["message"] = "perf regression: fixture spike did not run"
			out["perf_pass"] = false
			out["budget_ms"] = budget
			return out
		var over: bool = spike.get("status", "") == "computed" and spike_v > budget
		if inject and float(fixture_elapsed) > budget:
			over = true
		if over:
			out["ok"] = false
			out["code"] = "E_UNVERIFIED"
			out["message"] = "perf regression: spike exceeded budget"
			out["perf_pass"] = false
			out["budget_ms"] = budget
			return out
		out["perf_pass"] = true
		out["budget_ms"] = budget
	return out


func _perf_sample() -> Dictionary:
	var process_s: float = Performance.get_monitor(Performance.TIME_PROCESS)
	var physics_s: float = Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS)
	var fps: float = Performance.get_monitor(Performance.TIME_FPS)
	var mem: int = int(Performance.get_monitor(Performance.MEMORY_STATIC))
	if mem <= 0:
		mem = int(OS.get_static_memory_usage())
	var objects: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
	var process_status: String = "computed" if process_s > 0.0 else "Alternative"
	var fps_status: String = "computed" if fps > 0.0 else "Alternative"
	var mem_status: String = "computed" if mem > 0 else "Alternative"
	return {
		"time_process_ms": process_s * 1000.0,
		"time_process_ms_status": process_status,
		"time_physics_ms": physics_s * 1000.0,
		"fps": fps,
		"fps_status": fps_status,
		"memory_static": mem,
		"memory_static_status": mem_status,
		"object_count": objects,
		"frames": Engine.get_process_frames(),
		"ticks_msec": Time.get_ticks_msec(),
	}


func _p95(values: Array) -> Dictionary:
	if values.size() < 5:
		return {"status": "Alternative", "reason": "too few samples", "value": null}
	var sorted: Array = values.duplicate()
	sorted.sort()
	var idx: int = int(ceil(0.95 * float(sorted.size()))) - 1
	if idx < 0:
		idx = 0
	if idx >= sorted.size():
		idx = sorted.size() - 1
	return {"status": "computed", "value": sorted[idx], "n": sorted.size()}


func _spike_of(values: Array) -> Dictionary:
	if values.is_empty():
		return {"status": "Alternative", "reason": "no samples", "value": null}
	var peak: float = float(values[0])
	var i: int = 1
	while i < values.size():
		var v: float = float(values[i])
		if v > peak:
			peak = v
		i += 1
	return {"status": "computed", "value": peak, "n": values.size()}


func _hardware_manifest() -> Dictionary:
	var info: Dictionary = Engine.get_version_info()
	var gpu: String = str(RenderingServer.get_video_adapter_name())
	return {
		"os": OS.get_name(),
		"processor": OS.get_processor_name(),
		"processor_count": OS.get_processor_count(),
		"display_server": DisplayServer.get_name(),
		"video_adapter": gpu,
		"gpu_status": "computed" if not gpu.is_empty() else "Alternative",
		"engine": PINNED_ENGINE,
		"engine_hash": str(info.get("hash", "")),
		"headless": _is_headless(),
	}


func _assert_op(payload: Dictionary) -> Dictionary:
	var kind: String = str(payload.get("kind", ""))
	var path_s: String = str(payload.get("node_path", "Fixture"))
	var node: Node = _resolve(path_s)
	var base: Dictionary = {
		"kind": kind,
		"node_path": path_s,
		"source": "hh_agent_runtime",
		"tree_kind": "remote",
		"remote_tree": true,
		"playing": true,
		"is_playing_scene": true,
		"time": _time_snap(),
	}
	if (
		kind != "tree"
		and kind != "property"
		and kind != "signal"
		and kind != "ui_layout"
		and kind != "audio_event"
		and kind != "world"
	):
		base["ok"] = false
		base["code"] = "E_INVALID_TYPE"
		base["message"] = "assert kind is not allowlisted"
		return base
	if kind == "tree":
		base["ok"] = true
		base["found"] = node != null
		base["matched"] = node != null
		return base
	if node == null:
		base["ok"] = true
		base["found"] = false
		base["matched"] = false
		base["message"] = "assert node not found"
		return base
	if kind == "signal":
		var sig: String = str(payload.get("signal", payload.get("key", "")))
		var listed: Array = _signals_of(node)
		var obs_s: Dictionary = _observe_of(node)
		var emits: int = int(obs_s.get("signal_emits", 0))
		var want_emits: int = int(payload.get("value_int", 1))
		base["ok"] = true
		base["found"] = listed.has(sig)
		base["matched"] = listed.has(sig) and emits >= want_emits
		base["key"] = sig
		base["emitted"] = emits
		return base
	if kind == "ui_layout":
		var w: float = 0.0
		var h: float = 0.0
		if node is Control:
			var ctrl: Control = node
			w = ctrl.size.x
			h = ctrl.size.y
		var obs: Dictionary = _observe_of(node)
		if obs.has("ui_w"):
			w = float(obs.get("ui_w"))
		if obs.has("ui_h"):
			h = float(obs.get("ui_h"))
		var want_w: int = int(payload.get("value_int", 0))
		var matched_ui: bool = w >= 1.0 and h >= 1.0
		if payload.has("value_int"):
			matched_ui = int(round(w)) == want_w or int(round(h)) == want_w
		base["ok"] = true
		base["found"] = true
		base["matched"] = matched_ui
		base["ui_w"] = w
		base["ui_h"] = h
		return base
	if kind == "audio_event":
		var obs_a: Dictionary = _observe_of(node)
		var key_a: String = str(payload.get("key", "last_audio"))
		var found_a: bool = obs_a.has(key_a)
		var got_a: Variant = obs_a.get(key_a, "")
		var want_a: String = str(payload.get("value_string", ""))
		var playing: bool = false
		var pos: float = float(obs_a.get("playback_pos", 0.0))
		var frames_a: int = int(obs_a.get("audio_frames", 0))
		var tone: Node = node.get_node_or_null("Tone")
		if tone is AudioStreamPlayer:
			var player: AudioStreamPlayer = tone as AudioStreamPlayer
			playing = player.playing
			pos = maxf(pos, player.get_playback_position())
		# Frames must come from fixture observe (generator push_frame), never WAV byte size.
		var matched_a: bool = found_a and str(got_a) == want_a and frames_a > 0
		base["ok"] = true
		base["found"] = found_a
		base["matched"] = matched_a
		base["key"] = key_a
		base["got"] = _jsonable(got_a)
		base["playing"] = playing
		base["playback_pos"] = pos
		base["audio_frames"] = frames_a
		return base
	if kind == "world":
		var hits: int = 0
		var area_n: Node = node.get_node_or_null("HitA")
		if area_n is Area2D:
			hits = (area_n as Area2D).get_overlapping_areas().size()
		var obs_hits: int = int(_observe_of(node).get("world_hits", 0))
		var live_hits: int = hits if hits > obs_hits else obs_hits
		var want_hits: int = int(payload.get("value_int", 1))
		base["ok"] = true
		base["found"] = true
		base["matched"] = live_hits >= want_hits
		base["key"] = "world_hits"
		base["got"] = live_hits
		base["world_hits"] = live_hits
		return base
	var key: String = str(payload.get("key", ""))
	var obs_p: Dictionary = _observe_of(node)
	var got_v: Variant = null
	var found: bool = false
	if obs_p.has(key):
		got_v = obs_p[key]
		found = true
	elif _has_property(node, key):
		got_v = node.get(key)
		found = true
	if not found:
		base["ok"] = true
		base["found"] = false
		base["matched"] = false
		base["key"] = key
		return base
	var compare_op: String = str(payload.get("compare_op", payload.get("op", "eq")))
	if compare_op == "assert" or compare_op.is_empty():
		compare_op = "eq"
	if compare_op == "exists":
		base["ok"] = true
		base["found"] = true
		base["matched"] = true
		base["key"] = key
		base["got"] = _jsonable(got_v)
		return base
	var pred_p: Dictionary = {"key": key, "op": compare_op, "node_path": path_s}
	if payload.has("value_int"):
		pred_p["value_int"] = int(payload.get("value_int"))
	elif payload.has("value_bool"):
		pred_p["value_bool"] = payload.get("value_bool") == true
	else:
		pred_p["value_string"] = str(payload.get("value_string", ""))
	var ev_p: Dictionary = _eval_predicate(pred_p)
	base["ok"] = ev_p.get("ok", false) == true
	base["found"] = true
	base["matched"] = ev_p.get("matched", false) == true
	base["key"] = key
	base["got"] = ev_p.get("got", _jsonable(got_v))
	return base
