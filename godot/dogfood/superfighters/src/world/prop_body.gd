class_name PropBody
extends Node2D

## Owned world prop. Only WorldOwner may spawn or free this node.
## Break / throw / chain are schema fields, not behavior this WP.

const GROUP: String = "vf_world_prop"
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _View: GDScript = preload("res://src/world/prop_view.gd")

var placement_id: String = ""
var spec_id: String = ""
var kind: String = ""
var uid: int = 0
var health: float = 0.0
var alive: bool = true
var view: Sprite2D
var _layer_bit: int = 0
var _mask_bits: int = 0


func setup(p_place: Dictionary, spec: Dictionary, p_uid: int, layers: Dictionary) -> PackedStringArray:
	placement_id = str(p_place.get("id", ""))
	spec_id = str(spec.get("id", ""))
	kind = str(spec.get("kind", ""))
	uid = p_uid
	health = float(_Spec.health_of(spec))
	alive = true
	name = "Prop_%s_%d" % [placement_id, uid]
	add_to_group(GROUP)
	global_position = Vector2(float(p_place.get("x", 0.0)), float(p_place.get("y", 0.0)))
	_layer_bit = int(_Spec.layer_bit(_Spec.layer_name(spec), layers))
	_mask_bits = int(_Spec.bits_of(_Spec.mask_names(spec), layers))
	var errors: PackedStringArray = _build_collision(spec)
	view = _View.new() as Sprite2D
	add_child(view)
	var vis_v: Variant = view.call("bind_visual", _Spec.visual_path(spec))
	if vis_v is PackedStringArray:
		_append(errors, vis_v as PackedStringArray)
	return errors


func layer_bit() -> int:
	return _layer_bit


func mask_bits() -> int:
	return _mask_bits


func snapshot_row() -> Dictionary:
	return {
		"id": placement_id,
		"spec": spec_id,
		"kind": kind,
		"uid": uid,
		"x": SimConstants.quantize(global_position.x),
		"y": SimConstants.quantize(global_position.y),
		"alive": 1 if alive else 0,
		"health": SimConstants.quantize(health),
		"layer": _layer_bit,
		"mask": _mask_bits,
	}


func _build_collision(spec: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var size: Vector2 = _Spec.size_of(spec) as Vector2
	if size.x <= 0.0 or size.y <= 0.0:
		errors.append("prop %s missing collision size" % placement_id)
		return errors
	var shape: RectangleShape2D = RectangleShape2D.new()
	shape.size = size
	var col: CollisionShape2D = CollisionShape2D.new()
	col.shape = shape
	if kind == "one-way":
		col.one_way_collision = true
		col.one_way_collision_margin = 2.0
	if kind == "pickup":
		var area: Area2D = Area2D.new()
		area.name = "PropArea"
		area.collision_layer = _layer_bit
		area.collision_mask = _mask_bits
		area.monitoring = false
		area.monitorable = true
		area.add_child(col)
		add_child(area)
		return errors
	var body: StaticBody2D = StaticBody2D.new()
	body.name = "PropSolid"
	body.collision_layer = _layer_bit
	body.collision_mask = _mask_bits
	body.add_child(col)
	add_child(body)
	return errors


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
