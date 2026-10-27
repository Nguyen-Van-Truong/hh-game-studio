class_name ArenaFx
extends Node2D
## Presentation-only combat effects.
##
## MatchSession remains the deterministic authority.  This node consumes the
## immutable snapshot and keeps a short-lived effect list that is deliberately
## excluded from snapshots, replay hashes and gameplay collision.

signal sound_requested(kind: StringName, position: Vector2, pitch_scale: float)
signal camera_impulse(strength: float)

const MAX_EFFECTS: int = 128
const WEAPON_VISUALS = preload("res://game/presentation/weapon_visuals.gd")

var _effects: Array[Dictionary] = []
var _seen_events: Dictionary = {}
var _previous_pickups: Dictionary = {}
var _previous_fighters: Array[Dictionary] = []
var _last_tick: int = -1
var _sound_budget: int = 0
var _advancing: bool = true

func consume_snapshot(snapshot: Dictionary) -> void:
	if snapshot.is_empty():
		return
	_advancing = StringName(snapshot.get(&"phase", &"playing")) != &"paused"
	var tick: int = int(snapshot.get(&"tick", -1))
	if tick < 0 or tick == _last_tick:
		return
	if tick < _last_tick:
		_effects.clear()
		_seen_events.clear()
		_previous_fighters.clear()
		_previous_pickups.clear()
	_last_tick = tick
	# Bound dedup memory during long manual sessions; active rows refresh their tick.
	for key: Variant in _seen_events.keys():
		if tick - int(Dictionary(_seen_events[key]).get(&"tick", tick)) > 180:
			_seen_events.erase(key)
	_sound_budget = 4
	_consume_fighter_deltas(snapshot.get(&"fighters", []))
	_consume_pickups(snapshot.get(&"pickups", []))
	_consume_event_rows(snapshot.get(&"shot_events", []), &"shot", tick, snapshot)
	_consume_event_rows(snapshot.get(&"explosions", []), &"explosion", tick, snapshot)
	_consume_event_rows(snapshot.get(&"prop_events", []), &"prop", tick, snapshot)
	_consume_event_rows(snapshot.get(&"fire_events", []), &"fire", tick, snapshot)
	_consume_event_rows(snapshot.get(&"weapon_events", []), &"weapon", tick, snapshot)
	queue_redraw()

func _process(delta: float) -> void:
	if not _advancing:
		return
	for index: int in range(_effects.size() - 1, -1, -1):
		var effect: Dictionary = _effects[index]
		var age: float = float(effect.get(&"age", 0.0)) + delta
		effect[&"age"] = age
		var position: Vector2 = Vector2(effect.get(&"position", Vector2.ZERO))
		var velocity: Vector2 = Vector2(effect.get(&"velocity", Vector2.ZERO))
		effect[&"position"] = position + velocity * delta
		if age >= float(effect.get(&"life", 0.1)):
			_effects.remove_at(index)
	queue_redraw()

func _draw() -> void:
	for effect: Dictionary in _effects:
		var life: float = maxf(0.001, float(effect.get(&"life", 0.1)))
		var age: float = clampf(float(effect.get(&"age", 0.0)) / life, 0.0, 1.0)
		var alpha: float = 1.0 - age
		var color: Color = Color(effect.get(&"color", Color.WHITE))
		color.a *= alpha
		var position: Vector2 = Vector2(effect.get(&"position", Vector2.ZERO))
		var scale: float = float(effect.get(&"scale", 1.0))
		var kind: StringName = StringName(effect.get(&"kind", &""))
		if kind == &"tracer":
			var from_point: Vector2 = Vector2(effect.get(&"from", position))
			var to_point: Vector2 = Vector2(effect.get(&"to", position))
			draw_line(from_point, to_point, Color(color, alpha * 0.22), 9.0 * scale)
			draw_line(from_point, to_point, Color(color, alpha), 2.0 * scale)
		elif kind == &"muzzle":
			var facing: float = float(effect.get(&"facing", 1))
			var forward := Vector2(facing, -0.10).normalized()
			var normal := Vector2(-forward.y, forward.x)
			var muzzle_shape := PackedVector2Array([
				position - forward * 4.0 * scale,
				position + forward * 17.0 * scale + normal * 5.0 * scale,
				position + forward * 25.0 * scale,
				position + forward * 17.0 * scale - normal * 5.0 * scale,
			])
			draw_colored_polygon(muzzle_shape, Color("#ffb84d", alpha * 0.78))
			draw_polyline(muzzle_shape, Color("#fff6bc", alpha), 1.5 * scale, true)
			draw_line(position - normal * 9.0 * scale, position + normal * 9.0 * scale, Color("#fff6bc", alpha * 0.70), 1.5 * scale)
		elif kind == &"burst":
			var radius: float = scale * (14.0 + 58.0 * age)
			var burst_points := PackedVector2Array()
			for spoke: int in range(10):
				var burst_angle: float = float(spoke) * TAU / 10.0 - 0.12
				burst_points.append(position + Vector2.from_angle(burst_angle) * radius * (1.0 if spoke % 2 == 0 else 0.42))
			draw_colored_polygon(burst_points, Color(color, alpha * 0.22))
			draw_polyline(burst_points, Color(color, alpha * 0.92), 3.0 * scale, true)
			draw_arc(position, radius * 0.58, 0.15, TAU - 0.15, 18, Color("#fff1a6", alpha), 2.0 * scale)
			draw_circle(position, radius * 0.14, Color("#fff9d0", alpha * 0.9))
		elif kind == &"ring":
			var ring_radius: float = scale * (8.0 + 26.0 * age)
			draw_arc(position, ring_radius, 0.0, TAU, 24, Color(color, alpha), 3.0)
		elif kind == &"impact":
			var radius: float = scale * (7.0 + age * 19.0)
			var star := PackedVector2Array()
			for spoke: int in range(12):
				var angle: float = float(spoke) * TAU / 12.0 + 0.2
				star.append(position + Vector2.from_angle(angle) * radius * (1.0 if spoke % 2 == 0 else 0.25))
			draw_colored_polygon(star, Color(color, alpha))
			draw_polyline(star, Color("#fff5c2", alpha * 0.90), 1.2 * scale, true)
			draw_colored_polygon(PackedVector2Array([
				position + Vector2(-radius * 0.18, 0.0),
				position + Vector2(0.0, -radius * 0.18),
				position + Vector2(radius * 0.18, 0.0),
				position + Vector2(0.0, radius * 0.18),
			]), Color("#fff5c2", alpha))
		elif kind == &"spark":
			var velocity: Vector2 = Vector2(effect.get(&"velocity", Vector2.RIGHT * 20.0))
			draw_line(position, position - velocity * 0.07, Color(color, alpha), maxf(1.0, 2.5 * scale))
		elif kind == &"casing":
			draw_circle(position, 2.0 * scale * (1.0 - age * 0.25), Color(color, alpha))
			draw_line(position, position + Vector2(2.0, 1.0) * scale, Color("#fff0a8", alpha * 0.75), 1.0 * scale)
		elif kind == &"debris":
			var rotation: float = float(effect.get(&"rotation", 0.0)) + age * 4.0
			var span: float = 5.0 * scale * (1.0 - age * 0.25)
			draw_line(position - Vector2.RIGHT.rotated(rotation) * span, position + Vector2.RIGHT.rotated(rotation) * span, Color(color, alpha), 2.0)
		elif kind == &"flame":
			var pulse: float = 1.0 + sin((age + float(effect.get(&"seed", 0))) * 24.0) * 0.18
			var flame_center := position + Vector2(0.0, -8.0 * age)
			var flame_shape := PackedVector2Array([
				flame_center + Vector2(-6.0, 5.0) * scale * pulse,
				flame_center + Vector2(-2.0, -8.0) * scale * pulse,
				flame_center + Vector2(3.0, -14.0) * scale * pulse,
				flame_center + Vector2(7.0, 4.0) * scale * pulse,
			])
			draw_colored_polygon(flame_shape, Color("#ff6b35", alpha * 0.76))
			draw_colored_polygon(PackedVector2Array([
				flame_center + Vector2(-2.0, 4.0) * scale,
				flame_center + Vector2(2.0, -8.0) * scale * pulse,
				flame_center + Vector2(5.0, 4.0) * scale,
			]), Color("#ffe08a", alpha))
		elif kind == &"pickup":
			var pickup_radius: float = scale * (10.0 + 8.0 * age)
			draw_arc(position, pickup_radius, -PI * 0.8, PI * 0.8, 20, Color(color, alpha), 2.0)
			var diamond := PackedVector2Array([
				position + Vector2(0.0, -5.0) * scale,
				position + Vector2(5.0, 0.0) * scale,
				position + Vector2(0.0, 5.0) * scale,
				position + Vector2(-5.0, 0.0) * scale,
			])
			draw_colored_polygon(diamond, Color(color, alpha * 0.82))
			draw_polyline(diamond, Color("#fff3bb", alpha * 0.80), 1.0 * scale, true)

func _consume_fighter_deltas(value: Variant) -> void:
	if typeof(value) != TYPE_ARRAY:
		return
	var current: Array[Dictionary] = []
	for raw: Variant in Array(value):
		if typeof(raw) == TYPE_DICTIONARY:
			current.append(Dictionary(raw).duplicate(true))
	if _previous_fighters.size() == current.size():
		for index: int in range(current.size()):
			var prior: Dictionary = _previous_fighters[index]
			var next: Dictionary = current[index]
			if int(next.get(&"health", 0)) < int(prior.get(&"health", 0)):
				var point: Vector2 = _fighter_position(next)
				_add_effect(&"impact", point, 0.14, Color("#ffc887"), 0.85)
				for spark: int in range(5):
					_add_effect(&"spark", point, 0.20, Color("#fff0be"), 0.7, Vector2.from_angle(float(spark) * TAU / 5.0) * 105.0)
				_emit_sound(StringName("hit_" + String(next.get(&"last_hit_kind", &"punch"))), point, 1.0 + float(index) * 0.04)
				camera_impulse.emit(2.0)
	_previous_fighters = current

func _consume_pickups(value: Variant) -> void:
	if typeof(value) != TYPE_ARRAY:
		return
	var current: Dictionary = {}
	for raw: Variant in Array(value):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = raw
		var id: StringName = StringName(row.get(&"id", row.get(&"kind", &"pickup")))
		var active: bool = bool(row.get(&"active", true))
		var point := Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0)))
		current[id] = {&"active": active, &"position": point}
		var previous: Variant = _previous_pickups.get(id, null)
		if previous is Dictionary and bool(Dictionary(previous).get(&"active", true)) and not active:
			_add_effect(&"pickup", point, 0.30, Color("#9fffe1"), 1.0)
			_emit_sound(&"pickup", point, 1.0)
	_previous_pickups = current

func _consume_event_rows(value: Variant, kind: StringName, tick: int, snapshot: Dictionary) -> void:
	if typeof(value) != TYPE_ARRAY:
		return
	for raw: Variant in Array(value):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = raw
		var identity: String = "%s|%s" % [String(kind), _event_identity(row)]
		var ttl: int = int(row.get(&"ttl", 0))
		var previous_value: Variant = _seen_events.get(identity, null)
		var previous_ttl: int = -1
		var previous_tick: int = -1000
		if previous_value is Dictionary:
			previous_ttl = int(Dictionary(previous_value).get(&"ttl", -1))
			previous_tick = int(Dictionary(previous_value).get(&"tick", -1000))
		var is_new: bool = previous_value == null or ttl > previous_ttl or (tick - previous_tick > 1 and ttl >= previous_ttl)
		_seen_events[identity] = {&"ttl": ttl, &"tick": tick}
		if is_new:
			_spawn_event(kind, row, snapshot)

func _spawn_event(kind: StringName, row: Dictionary, snapshot: Dictionary) -> void:
	if kind == &"shot":
		var from_point: Vector2 = Vector2(row.get(&"from", Vector2.ZERO))
		var to_point: Vector2 = Vector2(row.get(&"to", from_point))
		var facing: int = 1 if to_point.x >= from_point.x else -1
		var gun: StringName = StringName(row.get(&"gun", &"pistol"))
		var tracer: Color = WEAPON_VISUALS.tracer_color(gun)
		_add_effect(&"tracer", from_point, 0.13, tracer, 1.0, Vector2.ZERO, 0.0, from_point, to_point)
		_add_effect(&"muzzle", from_point, 0.10, tracer.lightened(0.08), 1.0, Vector2.ZERO, 0.0, Vector2.ZERO, Vector2.ZERO, facing)
		if bool(row.get(&"eject", false)):
			_add_effect(&"casing", from_point + Vector2(0.0, -3.0), 0.34, Color("#e1b85b"), 0.9, Vector2(-float(facing) * 22.0, -34.0), 0.0)
		if gun == &"shotgun":
			var shot_direction := (to_point - from_point).normalized()
			for pellet: int in range(1, 3):
				var spread: Vector2 = shot_direction.rotated(0.08 * float(-1 if pellet == 1 else 1))
				_add_effect(&"tracer", from_point + spread * 5.0, 0.10, Color("#ffd38a"), 0.62, Vector2.ZERO, 0.0, from_point + spread * 5.0, from_point + spread * 120.0)
		_emit_sound(StringName("shot_%s" % String(gun)), from_point, 0.95 + float(abs(int(row.get(&"attacker", 1)))) * 0.03)
	elif kind == &"explosion":
		var point := Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0)))
		var radius: float = float(row.get(&"radius", 24.0))
		_add_effect(&"burst", point, 0.38, Color("#ff8b42"), clampf(radius / 70.0, 0.7, 1.8))
		for index: int in range(10):
			var angle: float = _seed_angle(index + int(point.x) + int(point.y))
			var speed: float = 36.0 + float((index * 17) % 36)
			_add_effect(&"spark", point, 0.32 + float(index % 3) * 0.05, Color("#ffd166"), 1.0, Vector2.from_angle(angle) * speed)
		_emit_sound(&"explosion", point, 0.9 + fmod(absf(point.x), 80.0) / 800.0)
		camera_impulse.emit(clampf(radius * 0.10, 4.0, 10.0))
	elif kind == &"prop":
		var prop_id: StringName = StringName(row.get(&"prop_id", &""))
		var point: Vector2 = _prop_position(snapshot, prop_id)
		var destroyed: bool = StringName(row.get(&"kind", &"")) == &"prop_destroyed"
		_add_effect(&"impact", point, 0.16 if not destroyed else 0.25, Color("#cfe8ff"), 0.7 if not destroyed else 1.1)
		if destroyed:
			for index: int in range(5):
				_add_effect(&"debris", point + Vector2(float(index - 2) * 4.0, -8.0), 0.4, Color("#d6a56a"), 1.0, Vector2(float(index - 2) * 18.0, -36.0 - float(index) * 6.0), float(index))
			camera_impulse.emit(3.5)
		_emit_sound(&"prop_destroyed" if destroyed else &"prop_hit", point, 0.92 + float(int(row.get(&"source", 0))) * 0.03)
	elif kind == &"fire":
		var player: int = int(row.get(&"player", 1))
		var point: Vector2 = _fighter_position_from_snapshot(snapshot, player)
		var fire_kind: StringName = StringName(row.get(&"kind", &"burn"))
		if fire_kind == &"ignite":
			_add_effect(&"flame", point + Vector2(0.0, -40.0), 0.55, Color("#ff7043"), 1.1, Vector2.ZERO, 0.0, Vector2.ZERO, Vector2.ZERO, player)
		_emit_sound(&"ignite" if fire_kind == &"ignite" else &"burn", point, 1.0)
		if fire_kind == &"extinguish":
			_add_effect(&"ring", point + Vector2(0.0, -28.0), 0.24, Color("#9ed9ff"), 0.8)
			_emit_sound(&"extinguish", point, 1.05)
	elif kind == &"weapon":
		var event_kind: StringName = StringName(row.get(&"kind", &"disarm"))
		if event_kind == &"airdrop" or event_kind == &"airdrop_land":
			var drop_point := Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0)))
			_add_effect(&"ring", drop_point, 0.30, Color("#a5f0ff"), 1.0)
			_add_effect(&"pickup", drop_point, 0.34, Color("#ffd36e"), 1.0)
			_emit_sound(&"airdrop", drop_point, 0.92 if event_kind == &"airdrop" else 1.04)
		elif event_kind == &"tackle_grab":
			var target: int = int(row.get(&"target", 1))
			var grab_point: Vector2 = _fighter_position_from_snapshot(snapshot, target)
			_add_effect(&"impact", grab_point, 0.22, Color("#ffd36e"), 1.15)
			_add_effect(&"ring", grab_point, 0.28, Color("#ff9c6e"), 0.9)
			_emit_sound(&"tackle", grab_point, 0.95)
		elif event_kind == &"grab_throw":
			var thrown: int = int(row.get(&"target", 1))
			var throw_point: Vector2 = _fighter_position_from_snapshot(snapshot, thrown)
			_add_effect(&"burst", throw_point, 0.24, Color("#ffd36e"), 0.72)
			_add_effect(&"ring", throw_point, 0.30, Color("#ff9c6e"), 1.0)
			_emit_sound(&"hit_grab_throw", throw_point, 0.98)
		else:
			var player: int = int(row.get(&"target", 1))
			var point: Vector2 = _fighter_position_from_snapshot(snapshot, player)
			_add_effect(&"pickup", point + Vector2(0.0, -24.0), 0.28, Color("#ffcf67"), 0.9)
			_emit_sound(&"disarm", point, 1.08)

func _add_effect(kind: StringName, position: Vector2, life: float, color: Color, scale: float = 1.0, velocity: Vector2 = Vector2.ZERO, rotation: float = 0.0, from_point: Vector2 = Vector2.ZERO, to_point: Vector2 = Vector2.ZERO, facing: int = 1) -> void:
	var effect: Dictionary = {
		&"kind": kind,
		&"position": position,
		&"life": maxf(0.02, life),
		&"age": 0.0,
		&"color": color,
		&"scale": scale,
		&"velocity": velocity,
		&"rotation": rotation,
		&"from": from_point,
		&"to": to_point,
		&"facing": facing,
		&"seed": _effects.size()
	}
	_effects.append(effect)
	while _effects.size() > MAX_EFFECTS:
		_effects.pop_front()

func _emit_sound(kind: StringName, position: Vector2, pitch_scale: float) -> void:
	if _sound_budget <= 0:
		return
	_sound_budget -= 1
	sound_requested.emit(kind, position, clampf(pitch_scale, 0.65, 1.45))

func _fighter_position(row: Dictionary) -> Vector2:
	return Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0))) + Vector2(0.0, -20.0)

func _fighter_position_from_snapshot(snapshot: Dictionary, player: int) -> Vector2:
	var rows_value: Variant = snapshot.get(&"fighters", [])
	if typeof(rows_value) == TYPE_ARRAY:
		var rows: Array = Array(rows_value)
		var index: int = player - 1
		if index >= 0 and index < rows.size() and typeof(rows[index]) == TYPE_DICTIONARY:
			return _fighter_position(Dictionary(rows[index]))
	return Vector2.ZERO

func _prop_position(snapshot: Dictionary, prop_id: StringName) -> Vector2:
	var rows_value: Variant = snapshot.get(&"props", null)
	if typeof(rows_value) != TYPE_ARRAY:
		var world_value: Variant = snapshot.get(&"world", {})
		if typeof(world_value) == TYPE_DICTIONARY:
			rows_value = Dictionary(world_value).get(&"props", [])
	if typeof(rows_value) == TYPE_ARRAY:
		for raw: Variant in Array(rows_value):
			if typeof(raw) == TYPE_DICTIONARY:
				var row: Dictionary = raw
				if StringName(row.get(&"id", &"")) == prop_id:
					return Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0))) + Vector2(0.0, -16.0)
	return Vector2.ZERO

func _event_identity(row: Dictionary) -> String:
	var explicit_id: Variant = row.get(&"event_id", null)
	if explicit_id != null and str(explicit_id) != "":
		return "event:%s" % str(explicit_id)
	var parts: Array[String] = []
	for key: Variant in row.keys():
		if StringName(key) == &"ttl":
			continue
		parts.append("%s=%s" % [String(key), str(row[key])])
	parts.sort()
	return ";".join(parts)

func _seed_angle(seed: int) -> float:
	return fmod(absf(float(seed) * 2.399963), TAU)
