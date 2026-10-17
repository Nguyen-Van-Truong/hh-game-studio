class_name HudBars
extends Node2D
## View-only HUD meters.  It reads the immutable match snapshot and never
## writes simulation state or replay data.

const WEAPON_VISUALS = preload("res://game/presentation/weapon_visuals.gd")

var _snapshot: Dictionary = {}

func consume_snapshot(snapshot: Dictionary) -> void:
	_snapshot = snapshot.duplicate(true)
	queue_redraw()

func _draw() -> void:
	var rows_value: Variant = _snapshot.get(&"fighters", [])
	if typeof(rows_value) != TYPE_ARRAY:
		return
	var rows: Array = Array(rows_value)
	var viewport_size := get_viewport_rect().size
	var meter_width: float = clampf(viewport_size.x * 0.24, 190.0, 330.0)
	var left_x: float = 24.0
	var right_x: float = maxf(left_x + meter_width + 40.0, viewport_size.x - meter_width - 24.0)
	for index: int in range(mini(rows.size(), 2)):
		if typeof(rows[index]) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = rows[index]
		var x: float = left_x if index == 0 else right_x
		var tint := Color("#45b8ff") if index == 0 else Color("#ffb23e")
		_draw_meter_group(row, x, 166.0, meter_width, tint)

func _draw_meter_group(row: Dictionary, x: float, y: float, width: float, tint: Color) -> void:
	var max_health: float = maxf(1.0, float(row.get(&"max_health", 100)))
	var health_ratio: float = clampf(float(row.get(&"health", 0)) / max_health, 0.0, 1.0)
	var sprint_value: Variant = row.get(&"sprint", {})
	var sprint: Dictionary = sprint_value if sprint_value is Dictionary else {}
	var max_stamina: float = maxf(1.0, float(sprint.get(&"capacity", 600)))
	var stamina_ratio: float = clampf(float(sprint.get(&"stamina", 0)) / max_stamina, 0.0, 1.0)
	var ammo_ratio: float = clampf(float(row.get(&"ammo", 0)) / 12.0, 0.0, 1.0)
	var health_fill := Color("#76e2a1").lerp(Color("#f06d72"), 1.0 - health_ratio)
	if bool(row.get(&"burning", false)) or int(row.get(&"burning_ticks", 0)) > 0:
		health_fill = Color("#ff8c4c")
	_draw_track(Rect2(x, y, width, 9.0), health_ratio, health_fill, tint)
	_draw_track(Rect2(x, y + 13.0, width * 0.70, 5.0), stamina_ratio, Color("#b6ed70"), tint.darkened(0.35))
	_draw_track(Rect2(x + width * 0.74, y + 13.0, width * 0.26, 5.0), ammo_ratio, Color("#ffe09a"), tint.darkened(0.45))
	var weapon_id: StringName = StringName(row.get(&"gun_id", &"pistol"))
	var icon_center := Vector2(x + width - 26.0, y - 11.0)
	WEAPON_VISUALS.draw_inventory_slots(self, row, Vector2(x + width - 181.0, y - 26.0), tint)
	WEAPON_VISUALS.draw_ammo_pips(self, icon_center + Vector2(0.0, 18.0), int(row.get(&"ammo", 0)), 12 if weapon_id == &"pistol" else 4 if weapon_id == &"shotgun" else 1, tint)
	if bool(row.get(&"bullet_time_active", false)):
		var pulse: float = 0.45 + 0.25 * sin(float(Time.get_ticks_msec()) * 0.008)
		draw_arc(Vector2(x + width * 0.5, y + 4.0), width * 0.52, PI, TAU, 24, Color(0.66, 0.89, 1.0, pulse), 2.0)

func _draw_track(rect: Rect2, ratio: float, fill: Color, accent: Color) -> void:
	draw_rect(rect, Color(0.02, 0.05, 0.08, 0.82), true)
	var filled := Rect2(rect.position, Vector2(rect.size.x * ratio, rect.size.y))
	if filled.size.x > 0.0:
		draw_rect(filled, Color(fill, 0.92), true)
		draw_line(filled.position + Vector2(0.0, 1.0), filled.end - Vector2(0.0, 1.0), Color(fill, 0.55), 1.0)
	draw_rect(rect, Color(accent, 0.72), false, 1.0)
