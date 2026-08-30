class_name PropSpec
extends RefCounted

## Typed world prop contract (VF4-WP1..WP3). Break/throw/chain are live.
## ledger:RL-WORLD-SCHEMA (assumption). Not observed.

const _Paths: GDScript = preload("res://src/world/world_paths.gd")
static var KINDS: PackedStringArray = PackedStringArray([
	"static", "dynamic", "one-way", "breakable", "pickup", "explosive"
])


static func is_kind(kind: String) -> bool:
	return KINDS.has(kind)


static func layer_name(spec: Dictionary) -> String:
	return str(_dict(spec.get("collision", {})).get("layer", ""))


static func mask_names(spec: Dictionary) -> PackedStringArray:
	return _to_packed(_dict(spec.get("collision", {})).get("mask", []))


static func visual_path(spec: Dictionary) -> String:
	return str(_dict(spec.get("visual", {})).get("path", ""))


static func size_of(spec: Dictionary) -> Vector2:
	var col: Dictionary = _dict(spec.get("collision", {}))
	return Vector2(float(col.get("width", 0.0)), float(col.get("height", 0.0)))


static func health_of(spec: Dictionary) -> float:
	return float(spec.get("health", 0.0))


static func validate_row(spec: Dictionary, gate: Dictionary, layers: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var required: PackedStringArray = _to_packed(gate.get("required_spec_fields", []))
	var i: int = 0
	while i < required.size():
		var field: String = String(required[i])
		if not spec.has(field):
			errors.append("PropSpec missing %s" % field)
		i += 1
	var sid: String = str(spec.get("id", ""))
	if sid == "":
		errors.append("PropSpec missing id")
	var kind: String = str(spec.get("kind", ""))
	if not is_kind(kind):
		errors.append("PropSpec %s unknown kind %s" % [sid, kind])
	var name_v: String = str(spec.get("name", ""))
	if name_v == "":
		errors.append("PropSpec %s missing name" % sid)
	if name_v.to_lower().contains("superfighter"):
		errors.append("PropSpec %s uses Superfighters trademark" % sid)
	var col: Dictionary = _dict(spec.get("collision", {}))
	if col.is_empty():
		errors.append("PropSpec %s missing collision" % sid)
	var col_fields: PackedStringArray = _to_packed(gate.get("required_collision_fields", []))
	var c: int = 0
	while c < col_fields.size():
		var cf: String = String(col_fields[c])
		if not col.has(cf):
			errors.append("PropSpec %s missing collision.%s" % [sid, cf])
		c += 1
	if float(col.get("width", 0.0)) <= 0.0 or float(col.get("height", 0.0)) <= 0.0:
		errors.append("PropSpec %s collision size must be > 0" % sid)
	var shape: String = str(col.get("shape", ""))
	var allowed_shapes: PackedStringArray = _to_packed(gate.get("allowed_shapes", ["rect"]))
	if not allowed_shapes.has(shape):
		errors.append("PropSpec %s collision shape %s is not allowed" % [sid, shape])
	var vis: Dictionary = _dict(spec.get("visual", {}))
	if vis.is_empty() or not vis.has("path"):
		errors.append("PropSpec %s missing visual" % sid)
	var vpath: String = str(vis.get("path", ""))
	var path_err: String = str(_Paths.reject_reason(vpath))
	if path_err != "":
		errors.append("PropSpec %s visual %s" % [sid, path_err])
	_append(errors, _layer_contract(sid, kind, col, layers))
	return errors


static func _layer_contract(
	sid: String, kind: String, col: Dictionary, layers: Dictionary
) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var named: Dictionary = _dict(layers.get("layers", {}))
	var contracts: Dictionary = _dict(layers.get("prop_masks", {}))
	if not contracts.has(kind):
		errors.append("PropSpec %s has no layer contract for %s" % [sid, kind])
		return errors
	var want: Dictionary = _dict(contracts.get(kind, {}))
	var layer: String = str(col.get("layer", ""))
	if layer != str(want.get("layer", "")):
		errors.append("PropSpec %s layer %s != contract %s" % [sid, layer, str(want.get("layer", ""))])
	if not named.has(layer):
		errors.append("PropSpec %s unknown collision layer %s" % [sid, layer])
	var got: PackedStringArray = _to_packed(col.get("mask", []))
	var need: PackedStringArray = _to_packed(want.get("mask", []))
	if got.size() != need.size():
		errors.append("PropSpec %s mask size != contract" % sid)
	var n: int = 0
	while n < need.size():
		if not got.has(String(need[n])):
			errors.append("PropSpec %s mask missing %s" % [sid, String(need[n])])
		n += 1
	var m: int = 0
	while m < got.size():
		var bit: String = String(got[m])
		if not named.has(bit):
			errors.append("PropSpec %s unknown mask layer %s" % [sid, bit])
		m += 1
	return errors


static func bits_of(names: PackedStringArray, layers: Dictionary) -> int:
	var named: Dictionary = _dict(layers.get("layers", {}))
	var bits: int = 0
	var i: int = 0
	while i < names.size():
		var key: String = String(names[i])
		if named.has(key):
			bits |= int(named.get(key, 0))
		i += 1
	return bits


static func layer_bit(name: String, layers: Dictionary) -> int:
	var named: Dictionary = _dict(layers.get("layers", {}))
	return int(named.get(name, 0))


static func _to_packed(value: Variant) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if value is Array:
		var arr: Array = value as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	elif value is PackedStringArray:
		return value as PackedStringArray
	return out


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
