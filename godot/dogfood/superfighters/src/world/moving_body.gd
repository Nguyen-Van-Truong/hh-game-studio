class_name MovingBody
extends Node2D

## WorldOwner-owned door / lift / trigger. Deterministic tick path.
## ledger:RL-WORLD-DOOR / RL-WORLD-LIFT / RL-WORLD-BOARD /
## RL-WORLD-TRIGGER (assumption).

const GROUP: String = "vf_world_mover"
const _Spec: GDScript = preload("res://src/world/prop_spec.gd")
const _View: GDScript = preload("res://src/world/prop_view.gd")
const _Moving: GDScript = preload("res://src/world/moving_spec.gd")

var placement_id: String = ""
var spec_id: String = ""
var kind: String = ""
var uid: int = 0
var target_id: String = ""
var door_open: bool = false
var path_from: Vector2 = Vector2.ZERO
var path_to: Vector2 = Vector2.ZERO
var path_tick: int = 0
var phase: String = "idle"
var hold_ticks: int = 0
var boarded: PackedInt32Array = PackedInt32Array()
var view: Sprite2D
var solid: CollisionObject2D
var spec_cache: Dictionary = {}
var _layer_bit: int = 0
var _mask_bits: int = 0
var _col_size: Vector2 = Vector2.ZERO


func setup(p_place: Dictionary, spec: Dictionary, p_uid: int, layers: Dictionary) -> PackedStringArray:
	placement_id = str(p_place.get("id", ""))
	spec_id = str(spec.get("id", ""))
	kind = str(spec.get("kind", ""))
	uid = p_uid
	target_id = str(p_place.get("target", ""))
	spec_cache = spec.duplicate(true)
	name = "Mover_%s_%d" % [placement_id, uid]
	add_to_group(GROUP)
	var origin: Vector2 = Vector2(float(p_place.get("x", 0.0)), float(p_place.get("y", 0.0)))
	path_from = Vector2(
		float(p_place.get("from_x", origin.x)),
		float(p_place.get("from_y", origin.y))
	)
	path_to = Vector2(
		float(p_place.get("to_x", origin.x)),
		float(p_place.get("to_y", origin.y))
	)
	global_position = origin
	door_open = false
	path_tick = 0
	phase = "idle"
	hold_ticks = 0
	boarded = PackedInt32Array()
	_layer_bit = int(_Spec.layer_bit(_Spec.layer_name(spec), layers))
	_mask_bits = int(_Spec.bits_of(_Spec.mask_names(spec), layers))
	_col_size = _Spec.size_of(spec) as Vector2
	var errors: PackedStringArray = _build_collision(spec)
	view = _View.new() as Sprite2D
	add_child(view)
	var vis_v: Variant = view.call("bind_visual", _Spec.visual_path(spec))
	if vis_v is PackedStringArray:
		_append(errors, vis_v as PackedStringArray)
	_apply_door_visual()
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
		"open": 1 if door_open else 0,
		"phase": phase,
		"path_tick": path_tick,
		"hold": hold_ticks,
		"boarded": boarded.size(),
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
	var shape: CollisionShape2D = solid.get_node_or_null("MoverShape") as CollisionShape2D
	if shape != null:
		shape.disabled = not enabled


func set_open(open_now: bool) -> bool:
	if kind != "door":
		return false
	if door_open == open_now:
		return false
	door_open = open_now
	set_solid_enabled(not open_now)
	_apply_door_visual()
	return true


func reset_motion() -> void:
	global_position = path_from
	path_tick = 0
	phase = "idle"
	hold_ticks = 0
	boarded = PackedInt32Array()
	if kind == "door":
		set_open(false)
		door_open = false
		set_solid_enabled(true)
		_apply_door_visual()


func advance_path() -> Vector2:
	if kind != "platform":
		return Vector2.ZERO
	if phase == "idle":
		return Vector2.ZERO
	var travel: int = int(_Moving.travel_ticks())
	var dwell: int = int(_Moving.dwell_ticks())
	var cap: float = float(_Moving.max_step_px())
	var old: Vector2 = global_position
	var dest: Vector2 = path_from
	if phase == "going":
		path_tick += 1
		var u: float = clampf(float(path_tick) / float(travel), 0.0, 1.0)
		dest = path_from.lerp(path_to, u)
		if path_tick >= travel:
			phase = "dwell"
			path_tick = 0
			dest = path_to
	elif phase == "dwell":
		path_tick += 1
		dest = path_to
		if path_tick >= dwell:
			phase = "returning"
			path_tick = 0
	elif phase == "returning":
		path_tick += 1
		var v: float = clampf(float(path_tick) / float(travel), 0.0, 1.0)
		dest = path_to.lerp(path_from, v)
		if path_tick >= travel:
			phase = "idle"
			path_tick = 0
			dest = path_from
	var delta: Vector2 = dest - old
	if delta.length() > cap:
		delta = delta.limit_length(cap)
		dest = old + delta
	global_position = dest
	return dest - old


func call_now() -> bool:
	if kind == "platform" and phase == "idle":
		phase = "going"
		path_tick = 0
		return true
	if kind == "door" and not door_open:
		return set_open(true)
	return false


func auto_call_on_board() -> bool:
	return bool(spec_cache.get("auto_call_on_board", false))


func _apply_door_visual() -> void:
	if view == null or not is_instance_valid(view):
		return
	if kind != "door":
		view.modulate = Color.WHITE
		view.visible = true
		return
	if door_open:
		view.modulate = Color(1.0, 1.0, 1.0, 0.22)
	else:
		view.modulate = Color.WHITE


func _build_collision(spec: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if _col_size.x <= 0.0 or _col_size.y <= 0.0:
		errors.append("mover %s missing collision size" % placement_id)
		return errors
	var shape: RectangleShape2D = RectangleShape2D.new()
	shape.size = _col_size
	var col: CollisionShape2D = CollisionShape2D.new()
	col.name = "MoverShape"
	col.shape = shape
	if kind == "trigger":
		var area: Area2D = Area2D.new()
		area.name = "MoverArea"
		area.collision_layer = _layer_bit
		area.collision_mask = 0
		area.monitoring = false
		area.monitorable = true
		area.add_child(col)
		add_child(area)
		solid = area
		return errors
	var body: StaticBody2D = StaticBody2D.new()
	body.name = "MoverSolid"
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
