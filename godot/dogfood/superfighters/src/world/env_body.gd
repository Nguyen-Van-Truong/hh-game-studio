class_name EnvBody
extends Node2D

## WorldOwner-owned instant / toxic / water / rotor. Deterministic.
## ledger:RL-ENV-INSTANT / RL-ENV-DEFER / RL-ENV-WATER /
## RL-ENV-ROTOR (assumption).

const GROUP: String = "vf_world_env"
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _View: GDScript = preload("res://src/world/prop_view.gd")
const _Env: GDScript = preload("res://src/world/env_spec.gd")

var placement_id: String = ""
var spec_id: String = ""
var kind: String = ""
var uid: int = 0
var angle: float = 0.0
var contact_ticks: Dictionary = {}
var view: Sprite2D
var area: Area2D
var spec_cache: Dictionary = {}
var _layer_bit: int = 0
var _mask_bits: int = 0
var _col_size: Vector2 = Vector2.ZERO


func setup(p_place: Dictionary, spec: Dictionary, p_uid: int, layers: Dictionary) -> PackedStringArray:
	placement_id = str(p_place.get("id", ""))
	spec_id = str(spec.get("id", ""))
	kind = str(spec.get("kind", ""))
	uid = p_uid
	spec_cache = spec.duplicate(true)
	name = "Env_%s_%d" % [placement_id, uid]
	add_to_group(GROUP)
	global_position = Vector2(float(p_place.get("x", 0.0)), float(p_place.get("y", 0.0)))
	angle = 0.0
	contact_ticks.clear()
	_layer_bit = int(_Spec.layer_bit(_Spec.layer_name(spec), layers))
	_mask_bits = int(_Spec.bits_of(_Spec.mask_names(spec), layers))
	_col_size = _Spec.size_of(spec) as Vector2
	var errors: PackedStringArray = _build_area()
	view = _View.new() as Sprite2D
	add_child(view)
	var vis_v: Variant = view.call("bind_visual", _Spec.visual_path(spec))
	if vis_v is PackedStringArray:
		_append(errors, vis_v as PackedStringArray)
	_apply_spin()
	return errors


func aabb() -> Rect2:
	return Rect2(global_position - _col_size * 0.5, _col_size)


func snapshot_row() -> Dictionary:
	return {
		"id": placement_id,
		"spec": spec_id,
		"kind": kind,
		"uid": uid,
		"x": SimConstants.quantize(global_position.x),
		"y": SimConstants.quantize(global_position.y),
		"angle": SimConstants.quantize(angle),
		"layer": _layer_bit,
		"mask": _mask_bits,
	}


func reset_motion() -> void:
	angle = 0.0
	contact_ticks.clear()
	_apply_spin()


func advance_spin() -> void:
	if kind != "rotor":
		return
	angle += float(_Env.rotor_deg())
	if angle >= 360.0:
		angle -= 360.0
	_apply_spin()


func bump_contact(slot: int) -> int:
	var n: int = int(contact_ticks.get(slot, 0)) + 1
	contact_ticks[slot] = n
	return n


func clear_contact(slot: int) -> void:
	if contact_ticks.has(slot):
		contact_ticks.erase(slot)


func _apply_spin() -> void:
	if view == null or not is_instance_valid(view):
		return
	if kind == "rotor":
		view.rotation_degrees = angle
	else:
		view.rotation_degrees = 0.0


func _build_area() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if _col_size.x <= 0.0 or _col_size.y <= 0.0:
		errors.append("env %s missing collision size" % placement_id)
		return errors
	var shape: RectangleShape2D = RectangleShape2D.new()
	shape.size = _col_size
	var col: CollisionShape2D = CollisionShape2D.new()
	col.name = "EnvShape"
	col.shape = shape
	area = Area2D.new()
	area.name = "EnvArea"
	area.collision_layer = _layer_bit
	area.collision_mask = 0
	area.monitoring = false
	area.monitorable = true
	area.add_child(col)
	add_child(area)
	return errors


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
