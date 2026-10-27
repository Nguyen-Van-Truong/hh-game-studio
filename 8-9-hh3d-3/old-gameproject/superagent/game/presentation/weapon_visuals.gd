class_name WeaponVisuals
extends RefCounted
## Small, data-driven weapon renderer used by FighterView and pickup previews.
##
## The definitions below are presentation-only.  They deliberately share the
## weapon ids from WeaponCatalog, while keeping silhouettes and anchor math in
## one place so a new firearm does not require another branch in the fighter
## presenter or map renderer.

const OUTLINE := Color("#101622")
const METAL := Color("#b7c9c7")
const METAL_DARK := Color("#3a4b5a")
const BRASS := Color("#e5ae62")
const RUBBER := Color("#18232d")
const RED := Color("#d65c55")
const ROCKET := Color("#77c5b6")

static func direction_for(facing: int, aim_angle: float, aiming: bool) -> Vector2:
	if not aiming:
		return Vector2(float(facing), 0.18).normalized()
	return Vector2(cos(aim_angle) * float(facing), sin(aim_angle)).normalized()

static func grip_for(body_width: float, visual_height: float, facing: int, aiming: bool) -> Vector2:
	var y: float = -visual_height * (0.55 if aiming else 0.50)
	return Vector2(float(facing) * maxf(8.0, body_width * 0.34), y)

static func draw_held(canvas: CanvasItem, weapon_id: StringName, grip: Vector2, direction: Vector2, size_scale: float, recoil: float, team_tint: Color) -> void:
	var d: Vector2 = direction.normalized()
	if d.is_zero_approx():
		d = Vector2.RIGHT
	# Local +Y is the top of the gun, mirrored without turning it upside down.
	var n := Vector2(d.y, -d.x) * (1.0 if d.x >= 0.0 else -1.0)
	var scale: float = clampf(size_scale, 0.70, 1.80)
	var rest_grip := grip - d * recoil
	match weapon_id:
		&"shotgun":
			_draw_shotgun(canvas, rest_grip, d, n, scale, team_tint)
		&"rocket_launcher":
			_draw_rocket(canvas, rest_grip, d, n, scale, team_tint)
		&"grenade":
			_draw_grenade(canvas, rest_grip, d, n, scale, team_tint)
		&"pistol", &"sidearm":
			_draw_pistol(canvas, rest_grip, d, n, scale, team_tint)
		&"pipe", &"knife":
			_line(canvas, rest_grip - d * 5.0 * scale, rest_grip + d * 19.0 * scale, OUTLINE, 5.0 * scale)
			_line(canvas, rest_grip, rest_grip + d * 19.0 * scale, METAL if weapon_id == &"knife" else BRASS, 3.0 * scale)

static func draw_pickup(canvas: CanvasItem, weapon_id: StringName, center: Vector2, tint: Color) -> void:
	# Pickups are intentionally larger than held weapons.  The dark plate and
	# contrasting silhouette make the item readable against both floor and pit
	# backdrops, including when the cargo is still descending.
	var size: float = 1.30 if weapon_id == &"shotgun" else 1.22 if weapon_id == &"rocket_launcher" else 1.46 if weapon_id == &"pistol" else 1.30
	canvas.draw_circle(center + Vector2(0.0, 2.0), 18.0, Color(0.02, 0.04, 0.07, 0.82))
	canvas.draw_arc(center + Vector2(0.0, 2.0), 18.0, -PI * 0.86, PI * 0.86, 18, Color(tint, 0.92), 2.0)
	draw_held(canvas, weapon_id, center - Vector2(10.0, 0.0), Vector2.RIGHT, size, 0.0, tint)
	var font: Font = ThemeDB.fallback_font
	canvas.draw_string(font, center + Vector2(-22.0, 26.0), _short_label(weapon_id), HORIZONTAL_ALIGNMENT_CENTER, 44.0, 8, Color(0.94, 0.97, 1.0, 0.94))
	if weapon_id == &"pistol":
		canvas.draw_circle(center + Vector2(13.0, -7.0), 2.0, Color("#fff1b0"))
	elif weapon_id == &"shotgun":
		canvas.draw_circle(center + Vector2(-13.0, 7.0), 2.0, Color("#f0c56d"))

static func draw_inventory_slots(canvas: CanvasItem, row: Dictionary, origin: Vector2, tint: Color) -> void:
	var active: int = int(row.get(&"active_slot", row.get(&"active_weapon_slot", 1)))
	var melee: StringName = StringName(row.get(&"melee_id", &"fists"))
	var gun: StringName = StringName(row.get(&"gun_id", &"none"))
	var slots: Array[StringName] = [melee, gun, &"grenade", &"bullet_time"]
	var labels: Array[String] = ["M", "G", "B", "T"]
	for index: int in range(slots.size()):
		var center := origin + Vector2(float(index) * 43.0 + 18.0, 14.0)
		var box := Rect2(origin + Vector2(float(index) * 43.0, 0.0), Vector2(38.0, 29.0))
		var border: Color = Color("#fff0a3") if index == active else Color(tint, 0.64)
		canvas.draw_rect(box, Color(0.02, 0.04, 0.07, 0.94), true)
		canvas.draw_rect(box, border, false, 1.5 if index == active else 1.0)
		if index == 2:
			_draw_grenade(canvas, center + Vector2(-3.0, -2.0), Vector2.RIGHT, Vector2.UP, 0.52, tint)
		elif index == 3:
			canvas.draw_circle(center + Vector2(-3.0, -2.0), 7.0, Color(tint, 0.22))
			canvas.draw_arc(center + Vector2(-3.0, -2.0), 6.0, -PI * 0.7, PI * 1.3, 12, tint, 1.6)
			canvas.draw_line(center + Vector2(-3.0, -2.0), center + Vector2(1.0, -6.0), Color("#fff0a3"), 1.2)
		elif slots[index] != &"none" and slots[index] != &"fists":
			draw_held(canvas, slots[index], center + Vector2(-5.0, -2.0), Vector2.RIGHT, 0.72, 0.0, tint)
		else:
			canvas.draw_circle(center + Vector2(-4.0, -2.0), 4.0, tint)
		canvas.draw_string(ThemeDB.fallback_font, center + Vector2(9.0, 8.0), labels[index], HORIZONTAL_ALIGNMENT_LEFT, 10.0, 8, Color(0.95, 0.97, 1.0, 0.88))

static func _short_label(weapon_id: StringName) -> String:
	match weapon_id:
		&"pistol":
			return "PISTOL"
		&"shotgun":
			return "SHOTGUN"
		&"rocket_launcher":
			return "ROCKET"
		&"pipe":
			return "PIPE"
		&"knife":
			return "KNIFE"
		&"grenade":
			return "BOMB"
		&"bullet_time", &"bullet_time_5", &"bullet_time_10":
			return "SLOW"
		&"fists":
			return "FISTS"
	return String(weapon_id).to_upper()

static func draw_hud_icon(canvas: CanvasItem, weapon_id: StringName, center: Vector2, tint: Color) -> void:
	canvas.draw_rect(Rect2(center - Vector2(25.0, 17.0), Vector2(50.0, 34.0)), Color(0.02, 0.04, 0.07, 0.92), true)
	canvas.draw_rect(Rect2(center - Vector2(25.0, 17.0), Vector2(50.0, 34.0)), Color(tint, 0.72), false, 1.5)
	draw_held(canvas, weapon_id, center - Vector2(7.0, 0.0), Vector2.RIGHT, 1.04 if weapon_id == &"pistol" else 0.86, 0.0, tint)

static func draw_ammo_pips(canvas: CanvasItem, center: Vector2, ammo: int, capacity: int, tint: Color) -> void:
	var count: int = clampi(capacity, 1, 12)
	var filled: int = clampi(ammo, 0, count)
	var start_x: float = center.x - float(count - 1) * 2.35
	for index: int in range(count):
		var pip_color: Color = Color("#ffe7a1") if index < filled else Color(0.28, 0.34, 0.40, 0.74)
		canvas.draw_rect(Rect2(Vector2(start_x + float(index) * 4.7, center.y), Vector2(3.0, 4.0)), pip_color, true)

static func muzzle_for(weapon_id: StringName, grip: Vector2, direction: Vector2, size: float) -> Vector2:
	var length: float = 27.0 if weapon_id == &"shotgun" else 25.0 if weapon_id == &"rocket_launcher" else 20.0
	return grip + direction * length * size

static func tracer_color(weapon_id: StringName) -> Color:
	match weapon_id:
		&"shotgun":
			return Color("#ffb86b")
		&"rocket_launcher":
			return Color("#9fe7cd")
		&"grenade":
			return Color("#d7e77f")
		_:
			return Color("#ffe9a6")

static func _line(canvas: CanvasItem, from_point: Vector2, to_point: Vector2, color: Color, width: float) -> void:
	canvas.draw_line(from_point, to_point, color, width, true)

static func _poly(canvas: CanvasItem, points: PackedVector2Array, fill: Color, edge: Color = OUTLINE, edge_width: float = 1.6) -> void:
	canvas.draw_colored_polygon(points, fill)
	var closed: PackedVector2Array = points.duplicate()
	closed.append(points[0])
	canvas.draw_polyline(closed, edge, edge_width, false)

static func _draw_pistol(canvas: CanvasItem, grip: Vector2, d: Vector2, n: Vector2, scale: float, team_tint: Color) -> void:
	var body_start := grip - d * (1.0 * scale)
	var body_end := grip + d * (16.0 * scale)
	var body := PackedVector2Array([
		body_start + n * (4.0 * scale), body_end + n * (3.0 * scale),
		body_end - n * (3.0 * scale), body_start - n * (4.0 * scale)
	])
	_poly(canvas, body, METAL_DARK)
	_line(canvas, body_start + n * 1.0 * scale, body_end + n * 1.0 * scale, team_tint.lightened(0.28), 1.7 * scale)
	var slide := PackedVector2Array([
		grip - d * (2.0 * scale) + n * (4.0 * scale),
		grip + d * (14.0 * scale) + n * (3.0 * scale),
		grip + d * (14.0 * scale) - n * (1.0 * scale),
		grip - d * (2.0 * scale) - n * (1.0 * scale)
	])
	_poly(canvas, slide, team_tint.darkened(0.15), OUTLINE, 1.1 * scale)
	# Rear sight and front sight provide a crisp, recognisable sidearm profile.
	_line(canvas, grip + d * 2.0 * scale + n * 4.0 * scale, grip + d * 2.0 * scale + n * 6.0 * scale, OUTLINE, 1.4 * scale)
	_line(canvas, body_end - d * 1.5 * scale + n * 3.0 * scale, body_end - d * 1.5 * scale + n * 5.0 * scale, OUTLINE, 1.4 * scale)
	var grip_end := grip - d * (3.0 * scale) - n * (10.0 * scale)
	var grip_poly := PackedVector2Array([
		grip - n * (3.0 * scale), grip - d * (1.0 * scale) - n * (3.0 * scale),
		grip_end - d * (2.0 * scale) + n * (3.0 * scale), grip_end + n * (4.0 * scale)
	])
	_poly(canvas, grip_poly, RUBBER, OUTLINE, 1.2 * scale)
	_line(canvas, grip - d * 1.0 * scale - n * 2.0 * scale, grip - d * 5.0 * scale + n * 1.0 * scale, BRASS, 1.1 * scale)
	_line(canvas, body_end - n * 2.0 * scale, body_end + d * 4.0 * scale - n * 2.0 * scale, BRASS, 1.5 * scale)
	canvas.draw_circle(grip + d * 5.0 * scale, 1.6 * scale, Color("#eff8e2"))

static func _draw_shotgun(canvas: CanvasItem, grip: Vector2, d: Vector2, n: Vector2, scale: float, team_tint: Color) -> void:
	var stock := grip - d * (11.0 * scale)
	_line(canvas, stock - n * 4.0 * scale, grip + d * (20.0 * scale) - n * 4.0 * scale, OUTLINE, 8.0 * scale)
	_line(canvas, stock - n * 4.0 * scale, grip + d * (20.0 * scale) - n * 4.0 * scale, METAL_DARK, 5.0 * scale)
	_line(canvas, grip + n * 3.0 * scale, grip + d * (27.0 * scale) + n * 3.0 * scale, OUTLINE, 6.0 * scale)
	_line(canvas, grip + n * 3.0 * scale, grip + d * (27.0 * scale) + n * 3.0 * scale, team_tint.lightened(0.10), 3.0 * scale)
	_line(canvas, grip - n * 3.0 * scale, grip + d * (27.0 * scale) - n * 3.0 * scale, BRASS, 1.4 * scale)
	_line(canvas, grip - d * 5.0 * scale, grip - d * 10.0 * scale + n * 1.0 * scale, RUBBER, 4.0 * scale)
	canvas.draw_circle(grip + d * 20.0 * scale, 2.0 * scale, Color("#fff0b8"))

static func _draw_rocket(canvas: CanvasItem, grip: Vector2, d: Vector2, n: Vector2, scale: float, team_tint: Color) -> void:
	var rear := grip - d * (11.0 * scale)
	var nose := grip + d * (25.0 * scale)
	var tube := PackedVector2Array([
		rear + n * (6.0 * scale), nose - d * (4.0 * scale) + n * (6.0 * scale),
		nose - d * (4.0 * scale) - n * (6.0 * scale), rear - n * (6.0 * scale)
	])
	_poly(canvas, tube, METAL_DARK, OUTLINE, 2.0 * scale)
	_line(canvas, rear + n * 3.5 * scale, nose - d * 4.0 * scale + n * 3.5 * scale, ROCKET, 2.5 * scale)
	_line(canvas, rear - n * 3.5 * scale, nose - d * 4.0 * scale - n * 3.5 * scale, team_tint, 1.2 * scale)
	var fin_a := PackedVector2Array([rear + d * 2.0 * scale + n * 5.0 * scale, rear + d * 9.0 * scale + n * 11.0 * scale, rear + d * 12.0 * scale + n * 3.0 * scale])
	var fin_b := PackedVector2Array([rear + d * 2.0 * scale - n * 5.0 * scale, rear + d * 9.0 * scale - n * 11.0 * scale, rear + d * 12.0 * scale - n * 3.0 * scale])
	_poly(canvas, fin_a, RED, OUTLINE, 1.0 * scale)
	_poly(canvas, fin_b, RED, OUTLINE, 1.0 * scale)
	canvas.draw_circle(nose, 3.2 * scale, Color("#f4d28a"))

static func _draw_grenade(canvas: CanvasItem, grip: Vector2, d: Vector2, n: Vector2, scale: float, team_tint: Color) -> void:
	var center := grip + d * (5.0 * scale)
	canvas.draw_circle(center, 7.0 * scale, OUTLINE)
	canvas.draw_circle(center, 5.2 * scale, team_tint.darkened(0.18))
	_line(canvas, center - n * 4.0 * scale, center + n * 4.0 * scale, team_tint.lightened(0.28), 1.5 * scale)
	_line(canvas, center + n * 4.0 * scale, center + n * 7.0 * scale - d * 2.0 * scale, BRASS, 1.6 * scale)
	canvas.draw_circle(center + n * 8.0 * scale - d * 2.0 * scale, 1.7 * scale, Color("#ff8c69"))
