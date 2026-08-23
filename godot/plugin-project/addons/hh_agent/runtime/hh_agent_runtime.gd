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
