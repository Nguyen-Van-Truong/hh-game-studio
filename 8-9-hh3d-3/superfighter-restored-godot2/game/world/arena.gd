class_name VaultArena
extends Node2D

## Authored arena topology for the restore lab. The geometry is intentionally
## original while preserving the functional beats: platforms, ladder, pit,
## cover, fire and pickups.

var platform_rects: Array[Rect2] = []
var ladder_rects: Array[Rect2] = []
var fire_rects: Array[Rect2] = []
var pickup_items: Array[Dictionary] = []
var _bodies: Array[StaticBody2D] = []

func build() -> void:
	platform_rects = [
		Rect2(0.0, 650.0, 1280.0, 70.0),
		Rect2(84.0, 505.0, 370.0, 18.0),
		Rect2(822.0, 505.0, 374.0, 18.0),
		Rect2(440.0, 385.0, 400.0, 18.0),
		Rect2(70.0, 300.0, 250.0, 16.0),
		Rect2(960.0, 300.0, 250.0, 16.0),
	]
	ladder_rects = [Rect2(628.0, 402.0, 24.0, 248.0)]
	fire_rects = [Rect2(552.0, 610.0, 176.0, 40.0)]
	pickup_items = [
		{"kind": &"ammo", "pos": Vector2(170.0, 470.0), "active": true},
		{"kind": &"health", "pos": Vector2(1110.0, 470.0), "active": true},
		{"kind": &"grenade", "pos": Vector2(640.0, 350.0), "active": true},
		{"kind": &"power", "pos": Vector2(180.0, 265.0), "active": true},
		{"kind": &"ammo", "pos": Vector2(1090.0, 265.0), "active": true},
	]
	_create_collision(Rect2(0.0, 650.0, 1280.0, 70.0), false)
	for index: int in range(1, platform_rects.size()):
		_create_collision(platform_rects[index], true)
	_create_collision(Rect2(-30.0, 0.0, 30.0, 720.0), false)
	_create_collision(Rect2(1280.0, 0.0, 30.0, 720.0), false)
	queue_redraw()

func _create_collision(rect: Rect2, one_way: bool) -> void:
	var body := StaticBody2D.new()
	body.name = &"Platform_%d" % _bodies.size()
	body.position = rect.position + rect.size * 0.5
	body.collision_layer = 1
	body.collision_mask = 1
	var shape_node := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = rect.size
	shape_node.shape = shape
	shape_node.one_way_collision = one_way
	shape_node.one_way_collision_margin = 12.0
	body.add_child(shape_node)
	add_child(body)
	_bodies.append(body)

func ladder_at(point: Vector2) -> Rect2:
	for ladder: Rect2 in ladder_rects:
		if ladder.grow(16.0).has_point(point):
			return ladder
	return Rect2()

func fire_at(point: Vector2) -> bool:
	for fire: Rect2 in fire_rects:
		if fire.has_point(point):
			return true
	return false

func collect_at(point: Vector2) -> StringName:
	for item: Dictionary in pickup_items:
		if not bool(item.get("active", false)):
			continue
		var item_position: Vector2 = Vector2(item.get("pos", Vector2.ZERO))
		if point.distance_to(item_position) <= 42.0:
			item["active"] = false
			queue_redraw()
			return StringName(item.get("kind", &"none"))
	return &"none"

func respawn_pickups() -> void:
	for item: Dictionary in pickup_items:
		item["active"] = true
	queue_redraw()

func _draw() -> void:
	draw_rect(Rect2(0.0, 0.0, 1280.0, 720.0), Color("101a2b"))
	for y: int in range(0, 720, 40):
		draw_line(Vector2(0.0, float(y)), Vector2(1280.0, float(y)), Color(0.08, 0.13, 0.22, 0.42), 1.0)
	for x: int in range(0, 1280, 64):
		draw_line(Vector2(float(x), 0.0), Vector2(float(x), 720.0), Color(0.08, 0.13, 0.22, 0.30), 1.0)
	for index: int in range(platform_rects.size()):
		var rect: Rect2 = platform_rects[index]
		var color := Color("304c67") if index == 0 else Color("3a7180")
		draw_rect(rect, color)
		draw_line(rect.position, Vector2(rect.end.x, rect.position.y), Color("8fc5c0"), 3.0)
	for ladder: Rect2 in ladder_rects:
		draw_rect(ladder, Color("bd8d54"))
		for rung_y: float in range(int(ladder.position.y + 10.0), int(ladder.end.y), 22):
			draw_line(Vector2(ladder.position.x, rung_y), Vector2(ladder.end.x, rung_y), Color("e5bf78"), 3.0)
	for fire: Rect2 in fire_rects:
		draw_rect(fire, Color(0.68, 0.16, 0.07, 0.55))
		for flame_x: float in range(int(fire.position.x + 8.0), int(fire.end.x), 18):
			draw_colored_polygon(PackedVector2Array([
				Vector2(flame_x, fire.end.y), Vector2(flame_x + 7.0, fire.position.y + 4.0),
				Vector2(flame_x + 14.0, fire.end.y)
			]), Color("f08a35"))
	for item: Dictionary in pickup_items:
		if not bool(item.get("active", false)):
			continue
		var pos: Vector2 = Vector2(item.get("pos", Vector2.ZERO))
		var kind: StringName = StringName(item.get("kind", &"none"))
		var color := Color("63c9ff")
		if kind == &"health": color = Color("e56d7a")
		elif kind == &"grenade": color = Color("b68cff")
		elif kind == &"power": color = Color("f1d16c")
		draw_circle(pos, 13.0, Color(0.02, 0.04, 0.08, 0.8))
		draw_circle(pos, 9.0, color)
		draw_arc(pos, 15.0, 0.0, TAU, 20, Color(0.85, 0.95, 1.0, 0.7), 2.0)
	# Original cover props.
	for crate: Rect2 in [Rect2(350.0, 596.0, 54.0, 54.0), Rect2(866.0, 596.0, 54.0, 54.0), Rect2(585.0, 331.0, 46.0, 54.0), Rect2(720.0, 331.0, 46.0, 54.0)]:
		draw_rect(crate, Color("6e5548"))
		draw_line(crate.position, crate.end, Color("b88a68"), 2.0)
		draw_line(Vector2(crate.end.x, crate.position.y), Vector2(crate.position.x, crate.end.y), Color("b88a68"), 2.0)
