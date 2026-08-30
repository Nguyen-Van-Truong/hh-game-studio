class_name PropBody
extends Node2D

## Owned world prop. Only WorldOwner may spawn, break, shove, or throw.
## ledger:RL-WORLD-OWN / RL-PROP-BREAK (assumption).

const GROUP: String = "vf_world_prop"
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _View: GDScript = preload("res://src/world/prop_view.gd")
const _Break: GDScript = preload("res://src/world/prop_break.gd")
const _Hazard: GDScript = preload("res://src/world/prop_hazard.gd")

var placement_id: String = ""
var spec_id: String = ""
var kind: String = ""
var uid: int = 0
var health: float = 0.0
var alive: bool = true
var movable: bool = false
var hanging: bool = false
var exploded: bool = false
var burning: bool = false
var burn_left: int = 0
var flammable: bool = false
var mat_id: String = ""
var view: Sprite2D
var solid: CollisionObject2D
var velocity: Vector2 = Vector2.ZERO
var carried_by: int = -1
var debris: Array = []
var debris_left: int = 0
var last_hit_slot: int = -1
var last_hit_seq: int = -1
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
	health = float(_Spec.health_of(spec))
	alive = true
	movable = bool(spec.get("movable", false)) or kind == "dynamic"
	hanging = bool(_Hazard.is_hanging_spec(spec))
	exploded = false
	burning = false
	burn_left = 0
	flammable = bool(_Hazard.is_flammable_spec(spec))
	mat_id = str(_Break.material_of(spec))
	name = "Prop_%s_%d" % [placement_id, uid]
	add_to_group(GROUP)
	global_position = Vector2(float(p_place.get("x", 0.0)), float(p_place.get("y", 0.0)))
	_layer_bit = int(_Spec.layer_bit(_Spec.layer_name(spec), layers))
	_mask_bits = int(_Spec.bits_of(_Spec.mask_names(spec), layers))
	_col_size = _Spec.size_of(spec) as Vector2
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


func aabb() -> Rect2:
	return Rect2(global_position - _col_size * 0.5, _col_size)


func already_hit(slot: int, seq: int) -> bool:
	return last_hit_slot == slot and last_hit_seq == seq


func mark_hit(slot: int, seq: int) -> void:
	last_hit_slot = slot
	last_hit_seq = seq


func snapshot_row() -> Dictionary:
	return {
		"id": placement_id,
		"spec": spec_id,
		"kind": kind,
		"uid": uid,
		"x": SimConstants.quantize(global_position.x),
		"y": SimConstants.quantize(global_position.y),
		"vx": SimConstants.quantize(velocity.x),
		"vy": SimConstants.quantize(velocity.y),
		"alive": 1 if alive else 0,
		"health": SimConstants.quantize(health),
		"debris": debris.size(),
		"carried": carried_by,
		"material": mat_id,
		"layer": _layer_bit,
		"mask": _mask_bits,
	}


func set_solid_enabled(enabled: bool) -> void:
	if solid == null or not is_instance_valid(solid):
		return
	if enabled:
		solid.collision_layer = _layer_bit
		solid.collision_mask = _mask_bits
	else:
		solid.collision_layer = 0
		solid.collision_mask = 0
	var shape: CollisionShape2D = solid.get_node_or_null("PropShape") as CollisionShape2D
	if shape != null:
		shape.disabled = not enabled


func disable_cover() -> void:
	alive = false
	set_solid_enabled(false)
	if view != null and is_instance_valid(view):
		view.visible = false


func spawn_debris() -> int:
	_clear_debris()
	var count: int = int(_Break.debris_count(spec_cache))
	var tex_path: String = str(_Break.debris_visual())
	var tex: Texture2D = _View.load_texture(tex_path)
	var i: int = 0
	while i < count:
		var spr: Sprite2D = Sprite2D.new()
		spr.name = "Debris_%d" % i
		spr.centered = true
		spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		spr.texture = tex
		spr.position = Vector2(
			float((i * 5) % 11) - 5.0,
			float((i * 3) % 9) - 4.0
		)
		add_child(spr)
		debris.append(spr)
		i += 1
	debris_left = int(_Break.debris_life(spec_cache))
	return debris.size()


func tick_debris() -> void:
	if debris.is_empty():
		return
	debris_left -= 1
	if debris_left > 0:
		return
	_clear_debris()


func _clear_debris() -> void:
	var i: int = 0
	while i < debris.size():
		var spr: Node = debris[i] as Node
		if spr != null and is_instance_valid(spr):
			spr.queue_free()
		i += 1
	debris.clear()
	debris_left = 0


func _build_collision(spec: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var size: Vector2 = _Spec.size_of(spec) as Vector2
	if size.x <= 0.0 or size.y <= 0.0:
		errors.append("prop %s missing collision size" % placement_id)
		return errors
	var shape: RectangleShape2D = RectangleShape2D.new()
	shape.size = size
	var col: CollisionShape2D = CollisionShape2D.new()
	col.name = "PropShape"
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
		solid = area
		return errors
	var body: StaticBody2D = StaticBody2D.new()
	body.name = "PropSolid"
	body.collision_layer = _layer_bit
	body.collision_mask = _mask_bits
	body.add_child(col)
	add_child(body)
	solid = body
	return errors


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
