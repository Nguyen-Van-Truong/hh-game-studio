extends SceneTree
## FIXTURE_ONLY / NOT_E2E: real MapLoader + ProjectileManager stepping at
## 60 Hz (0.4 original 24 Hz frames). No screenshot or parity acceptance.

const MapScript: Script = preload("res://game/world/map_loader.gd")
const ProjectileScript: Script = preload("res://game/world/projectile_manager.gd")
const HazardScript: Script = preload("res://game/world/fire_hazard_system.gd")
const STEP: float = 0.4
const EPSILON: float = 0.001

class TestWorld extends Node2D:
	var map_loader: Node2D = null
	var projectile_manager: Node2D = null
	var fire_hazard_system: Node2D = null
	var fighters: Array[Node2D] = []
	var props: Array[Node2D] = []
	var pickups: Array[Dictionary] = []
	var game_speed: float = 1.0

var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _world: TestWorld = null
var _loader: Node2D = null
var _projectiles: Node2D = null
var _hazards: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run()
	_world.free()
	_world = null
	_loader = null
	_projectiles = null
	_hazards = null
	MapScript.cleanup_headless_singletons()
	print("[CHIBI R6 PROJECTILES] FIXTURE_ONLY=1 NOT_E2E=1 ", "PASS" if _failures == 0 else "FAIL", " checks=", _checks, " failures=", _failures)
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	seed(6282026)
	_world = TestWorld.new()
	root.add_child(_world)
	_loader = MapScript.new() as Node2D
	_world.map_loader = _loader
	_loader.set("match_world", _world)
	_world.add_child(_loader)
	_projectiles = ProjectileScript.new() as Node2D
	_world.projectile_manager = _projectiles
	_projectiles.set("match_world", _world)
	# This regression checks motion/contact, with no rendering requirements.
	_projectiles.set("_textures_loaded", true)
	_world.add_child(_projectiles)
	_hazards = HazardScript.new() as Node2D
	_hazards.set("match_world", _world)
	_hazards.set("_textures_loaded", true)
	_world.fire_hazard_system = _hazards
	_world.add_child(_hazards)
	_one_way_crossings()
	_throwable_crossings()
	_moving_lifts()
	_real_storage_slope()
	_real_screenshot_ladder()
	_real_portal_and_upward_ladder_throwables()
	_no_map_fallback()


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R6 PROJECTILES] " + label)


func _one_way(previous: Vector2, following: Vector2) -> Dictionary:
	return _loader.call("raycast_one_way", previous, following) as Dictionary


func _reset_geometry() -> void:
	_loader.call("_clear_map_state")
	_loader.set("map_bounds", Rect2(-500.0, -500.0, 1000.0, 1000.0))
	_projectiles.call("clear_all")
	_hazards.call("clear_all")


func _one_way_crossings() -> void:
	_reset_geometry()
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 20.0, 4.0, 2.0))
	var crossing: Dictionary = _one_way(Vector2(0.0, 10.0), Vector2(30.0, 40.0))
	_check(bool(crossing.get("hit", false)) and (crossing.get("pos", Vector2.ZERO) as Vector2).distance_to(Vector2(10.0, 20.0)) <= EPSILON, "narrow platform hit uses crossing x even when the endpoint has passed its edge")
	_check(not bool(_one_way(Vector2(0.0, 10.0), Vector2(12.0, 40.0)).get("hit", false)), "endpoint inside a platform does not invent contact after missing its top")
	_check(not bool(_one_way(Vector2(12.0, 21.0), Vector2(12.0, 23.0)).get("hit", false)), "falling below a one-way top does not snap upward")
	_check(not bool(_one_way(Vector2(12.0, 30.0), Vector2(12.0, 10.0)).get("hit", false)), "one-way underside remains open on ascent")
	_check(bool(_one_way(Vector2(12.0, 20.0), Vector2(12.0, 21.0)).get("hit", false)), "exact top contact remains stable")
	(_loader.get("cloud_rects") as Array).clear()
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 30.0, 4.0, 2.0))
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 20.0, 4.0, 2.0))
	var ordered: Dictionary = _one_way(Vector2(12.0, 10.0), Vector2(12.0, 40.0))
	_check(bool(ordered.get("hit", false)) and absf((ordered["pos"] as Vector2).y - 20.0) <= EPSILON, "earliest top wins independently of map array order")
	(_loader.get("cloud_rects") as Array).clear()
	(_loader.get("elevators") as Array).append({"rect": Rect2(10.0, 20.0, 4.0, 2.0)})
	_check(bool(_one_way(Vector2(12.0, 10.0), Vector2(12.0, 30.0)).get("hit", false)), "current lift top supports a descending throwable")
	_check(not bool(_one_way(Vector2(12.0, 30.0), Vector2(12.0, 10.0)).get("hit", false)), "lift underside remains open")


func _throw_entry(position: Vector2, velocity: Vector2, weapon: String = "GRENADE") -> Dictionary:
	return {"owner": null, "weapon_id": weapon, "pos": position, "prev_pos": position, "vel": velocity, "fuse_frames": 120.0, "age": 0.0, "rot": 0.0, "rot_vel": 0.25, "settled": false, "ignore_cover_id": -1}


func _throwable_crossings() -> void:
	_reset_geometry()
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 20.0, 4.0, 2.0))
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 10.0), Vector2(30.0, 29.55)))
	_projectiles.call("step_projectiles", 1.0)
	var values: Array = _projectiles.get("throwables") as Array
	_check(values.size() == 1, "fast grenade survives contact as a bouncing throwable")
	if values.size() == 1:
		var value: Dictionary = values[0] as Dictionary
		_check((value["pos"] as Vector2).distance_to(Vector2(10.0, 19.5)) <= EPSILON and (value["vel"] as Vector2).y < 0.0, "real projectile step catches the crossed platform and bounces above it")
	_projectiles.call("clear_all")
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 10.0), Vector2(12.0, 29.55)))
	_projectiles.call("step_projectiles", 1.0)
	values = _projectiles.get("throwables") as Array
	_check(values.size() == 1 and ((values[0] as Dictionary)["pos"] as Vector2).distance_to(Vector2(12.0, 40.0)) <= EPSILON, "real grenade falls beside a missed narrow top without teleporting onto it")
	_projectiles.call("clear_all")
	(_loader.get("cloud_rects") as Array).clear()
	(_loader.get("solid_rects") as Array).append(Rect2(10.0, 20.0, 4.0, 2.0))
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(12.0, 30.0), Vector2(0.0, -20.45)))
	_projectiles.call("step_projectiles", 1.0)
	values = _projectiles.get("throwables") as Array
	_check(values.size() == 1 and ((values[0] as Dictionary)["pos"] as Vector2).y > 22.0 and ((values[0] as Dictionary)["vel"] as Vector2).y > 0.0, "a solid ceiling remains blocking and reflects an ascending grenade down")
	_projectiles.call("clear_all")
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 21.0), Vector2(30.0, -0.45)))
	_projectiles.call("step_projectiles", 1.0)
	values = _projectiles.get("throwables") as Array
	_check(values.size() == 1 and ((values[0] as Dictionary)["pos"] as Vector2).x < 10.0 and ((values[0] as Dictionary)["vel"] as Vector2).x < 0.0, "swept wall collision prevents a fast grenade tunnelling through a thin solid")


func _lift(direction: String, speed: float) -> Dictionary:
	var lift: Dictionary = {
		"direction": direction, "speed": speed, "distance": 40.0,
		"phase": 0.0, "center_pos": Vector2(0.0, 30.0),
		"current_pos": Vector2(0.0, 30.0), "delta_pos": Vector2.ZERO,
		"w": 20.0, "h": 4.0, "rect": Rect2(-10.0, 28.0, 20.0, 4.0),
	}
	(_loader.get("elevators") as Array).append(lift)
	return lift


func _moving_lifts() -> void:
	for speed: float in [-12.0, 12.0]:
		_reset_geometry()
		var lift: Dictionary = _lift("vertical", speed)
		var grenade: Dictionary = _throw_entry(Vector2(0.0, 27.5), Vector2.ZERO)
		grenade["settled"] = true
		(_projectiles.get("throwables") as Array).append(grenade)
		var follows_lift: bool = true
		for _tick: int in range(6):
			_loader.call("step_map", STEP)
			_projectiles.call("step_projectiles", STEP)
			var values: Array = _projectiles.get("throwables") as Array
			if values.size() != 1:
				follows_lift = false
				break
			var position: Vector2 = (values[0] as Dictionary)["pos"] as Vector2
			var top: float = (lift["rect"] as Rect2).position.y
			follows_lift = follows_lift and absf(position.y - (top - 0.5)) <= EPSILON
		_check(follows_lift, "resting grenade follows a vertical lift exactly once per tick, speed=%s" % speed)
		(_loader.get("elevators") as Array).clear()
		var before: Vector2 = ((_projectiles.get("throwables") as Array)[0] as Dictionary)["pos"] as Vector2
		_loader.call("step_map", STEP)
		_projectiles.call("step_projectiles", STEP)
		var after: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
		_check((after["pos"] as Vector2).y > before.y and not bool(after["settled"]), "grenade resumes gravity when lift support disappears, speed=%s" % speed)
	_reset_geometry()
	var horizontal: Dictionary = _lift("horizontal", 12.0)
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 27.5), Vector2.ZERO))
	_loader.call("step_map", STEP)
	_projectiles.call("step_projectiles", STEP)
	var horizontal_grenade: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check((horizontal_grenade["pos"] as Vector2).distance_to((horizontal["current_pos"] as Vector2) + Vector2(0.0, -2.5)) <= EPSILON, "resting grenade follows horizontal lift displacement without double motion")
	_reset_geometry()
	var rising: Dictionary = _lift("vertical", -12.0)
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 27.0), Vector2.ZERO))
	_loader.call("step_map", STEP)
	_projectiles.call("step_projectiles", STEP)
	var caught: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check(absf((caught["pos"] as Vector2).y - ((rising["rect"] as Rect2).position.y - 0.5)) <= EPSILON, "relative sweep catches a grenade overtaken from above by a rising lift")
	_reset_geometry()
	_lift("vertical", -12.0)
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 29.0), Vector2.ZERO))
	_loader.call("step_map", STEP)
	_projectiles.call("step_projectiles", STEP)
	var below: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check((below["pos"] as Vector2).y > 29.0, "rising lift never pulls an underside grenade onto its top")
	_reset_geometry()
	_lift("vertical", -12.0)
	(_loader.get("solid_rects") as Array).append(Rect2(-20.0, 20.0, 40.0, 2.0))
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 27.5), Vector2.ZERO))
	for _tick: int in range(2):
		_loader.call("step_map", STEP)
		_projectiles.call("step_projectiles", STEP)
	var blocked: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check((blocked["pos"] as Vector2).y >= 22.5 - EPSILON and not bool(_loader.call("is_point_solid", blocked["pos"], false)), "lift carry cannot push a resting grenade through a solid ceiling")
	_reset_geometry()
	_lift("vertical", -24.0)
	(_loader.get("solid_rects") as Array).append(Rect2(-20.0, 20.0, 40.0, 2.0))
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 27.0), Vector2.ZERO))
	_loader.call("step_map", STEP)
	_projectiles.call("step_projectiles", STEP)
	var second_surface: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check((second_surface["pos"] as Vector2).y >= 22.5 - EPSILON and not bool(_loader.call("is_point_solid", second_surface["pos"], false)), "rising lift's post-impact remainder is blocked by the next solid ceiling")
	_reset_geometry()
	var static_after_step: Dictionary = _lift("vertical", -12.0)
	_loader.call("step_map", STEP)
	_projectiles.call("step_projectiles", STEP)
	var below_current: float = (static_after_step["rect"] as Rect2).position.y + 1.0
	_check(not bool(_one_way(Vector2(0.0, below_current), Vector2(0.0, below_current + 0.1)).get("hit", false)), "default one-way query uses the current lift rather than stale old motion")
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, below_current), Vector2.ZERO))
	_projectiles.call("step_projectiles", STEP)
	var repeated_step: Dictionary = (_projectiles.get("throwables") as Array)[0] as Dictionary
	_check((repeated_step["pos"] as Vector2).y > below_current, "second projectile step without a map step cannot replay the previous lift motion")


func _real_storage_slope() -> void:
	_projectiles.call("clear_all")
	_loader.call("load_map", "storage")
	var slope: Dictionary = {}
	for candidate: Dictionary in _loader.get("slope_polygons") as Array:
		if bool(candidate.get("is_cloud", false)):
			slope = candidate
			break
	_check(not slope.is_empty(), "real Storage data contains its tilted CLOUD stair")
	if slope.is_empty():
		return
	var points: PackedVector2Array = slope["world_points"] as PackedVector2Array
	var index: int = int(slope["top_edge_idx"])
	var edge: Vector2 = points[(index + 1) % points.size()] - points[index]
	var center: Vector2 = points[index] + edge * 0.5
	var normal: Vector2 = Vector2(edge.y, -edge.x).normalized()
	if normal.y > 0.0:
		normal = -normal
	_check(bool(_one_way(center + normal * 8.0, center - normal * 8.0).get("hit", false)), "real tilted CLOUD stair catches a crossing from its upper side")
	_check(not bool(_one_way(center - normal * 8.0, center + normal * 8.0).get("hit", false)), "real tilted CLOUD stair permits ascent from its underside")
	var solid_hit: Dictionary = _loader.call("raycast_solid", center + normal * 4.0, center - normal * 12.0, -1, false, false) as Dictionary
	_check(not bool(solid_hit.get("hit", false)), "tilted CLOUD does not become static solid for projectile queries")
	_projectiles.call("spawn_bullet", null, "SNIPER", center + normal * 4.0, rad_to_deg((-normal).angle()))
	_projectiles.call("step_projectiles", STEP)
	var shots: Array = _projectiles.get("bullets") as Array
	_check(shots.size() == 1 and ((shots[0] as Dictionary)["pos"] as Vector2).distance_to(center - normal * 12.0) <= EPSILON, "ordinary bullet remains straight and penetrates the real tilted CLOUD stair")


func _real_screenshot_ladder() -> void:
	_projectiles.call("clear_all")
	_loader.call("load_map", "steel_harbor")
	_check(str(_loader.get("current_map_id")) == "steel_harbor", "real screenshot map Steel Harbor loads")
	var ladder: Rect2 = _loader.call("get_ladder_at", Vector2(-298.0, -80.0)) as Rect2
	_check(ladder.has_point(Vector2(-298.0, -80.0)), "screenshot left tower ladder is a sensor at its authored coordinates")
	var across_ladder: Dictionary = _loader.call("raycast_solid", Vector2(-320.0, -80.0), Vector2(-280.0, -80.0), -1, false, false) as Dictionary
	_check(not bool(across_ladder.get("hit", false)), "ladder shaft is not a wall")
	_projectiles.call("spawn_bullet", null, "SNIPER", Vector2(-338.0, -120.5), 0.0)
	for _tick: int in range(6):
		_projectiles.call("step_projectiles", STEP)
	var shots: Array = _projectiles.get("bullets") as Array
	_check(shots.size() == 1 and ((shots[0] as Dictionary)["pos"] as Vector2).distance_to(Vector2(-242.0, -120.5)) <= EPSILON, "horizontal bullet crosses the screenshot ladder with unchanged height")
	_projectiles.call("clear_all")
	# Owner opened this ladder mouth and its intermediate grating. A dropped
	# throwable now traverses the shaft to the solid tower floor at y=12.
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(-298.0, -121.0), Vector2.ZERO))
	var reached_floor: bool = false
	var never_solid: bool = true
	for _tick: int in range(80):
		_projectiles.call("step_projectiles", STEP)
		var values: Array = _projectiles.get("throwables") as Array
		if values.size() != 1:
			break
		var value: Dictionary = values[0] as Dictionary
		var position: Vector2 = value["pos"] as Vector2
		reached_floor = reached_floor or position.y >= 11.0
		never_solid = never_solid and not bool(_loader.call("is_point_solid", position, false))
	_check(reached_floor and never_solid, "grenade falls through the real opened shaft and reaches the solid tower floor without penetration")
	_projectiles.call("clear_all")
	_projectiles.call("spawn_throwable", null, "MOLOTOV", Vector2(-298.0, -121.0), 90.0)
	var fire_before: int = int(_hazards.get("total_fire_bursts_triggered"))
	var curved_down: bool = false
	for _tick: int in range(60):
		_projectiles.call("step_projectiles", STEP)
		var values: Array = _projectiles.get("throwables") as Array
		if values.is_empty():
			break
		curved_down = curved_down or (((values[0] as Dictionary)["vel"] as Vector2).y > 4.3)
	var fire_at_floor: bool = not (_hazards.get("fire_particles") as Array).is_empty()
	for particle: Dictionary in _hazards.get("fire_particles") as Array:
		fire_at_floor = fire_at_floor and (particle["pos"] as Vector2).y >= 8.0 - EPSILON
	_check(curved_down and (_projectiles.get("throwables") as Array).is_empty() and int(_hazards.get("total_fire_bursts_triggered")) == fire_before + 1 and fire_at_floor, "real Molotov accelerates through the opened shaft then breaks into fire on the tower floor")


func _real_portal_and_upward_ladder_throwables() -> void:
	# 1. Upward bomb throw from bottom of Steel Harbor ladder reaches upper floor
	_projectiles.call("clear_all")
	_loader.call("load_map", "steel_harbor")
	_projectiles.call("spawn_throwable", null, "GRENADE", Vector2(-302.0, 2.0), -80.0)
	var reached_upper: bool = false
	for _tick: int in range(60):
		_projectiles.call("step_projectiles", STEP)
		var ths: Array = _projectiles.get("throwables") as Array
		if ths.size() == 1:
			var p: Vector2 = (ths[0] as Dictionary)["pos"] as Vector2
			if p.y <= -108.0:
				reached_upper = true
	_check(reached_upper, "grenade thrown upward from bottom of ladder ascends through shaft above upper floor")

	# 2. Portal Doorway bidirectional traversal (Top -> Bottom and Bottom -> Top) on Rooftops
	_projectiles.call("clear_all")
	_loader.call("load_map", "rooftops")
	var portals_arr: Array = _loader.get("portals") as Array
	_check(portals_arr.size() >= 2, "real Rooftops map contains linked portal doorways")
	if portals_arr.size() >= 2:
		var upper_p: Dictionary = portals_arr[0] as Dictionary
		var lower_p: Dictionary = portals_arr[1] as Dictionary
		for cand_p: Dictionary in portals_arr:
			var er: Rect2 = cand_p.get("entry_rect", Rect2()) as Rect2
			var xr: Rect2 = cand_p.get("exit_rect", Rect2()) as Rect2
			if er.position.y < xr.position.y:
				upper_p = cand_p
			elif er.position.y > xr.position.y:
				lower_p = cand_p
		var up_er: Rect2 = upper_p["entry_rect"] as Rect2
		var up_xr: Rect2 = upper_p["exit_rect"] as Rect2
		var up_dir: Vector2 = upper_p["dir"] as Vector2
		var start_top: Vector2 = Vector2(up_er.position.x - 6.0 if up_dir.x > 0.0 else up_er.end.x + 6.0, up_er.position.y + up_er.size.y * 0.5)
		(_projectiles.get("throwables") as Array).append(_throw_entry(start_top, Vector2(up_dir.x * 6.5, -0.5)))
		var tp_down_ok: bool = false
		for _t: int in range(10):
			_projectiles.call("step_projectiles", STEP)
			var ths: Array = _projectiles.get("throwables") as Array
			if ths.size() == 1:
				var p: Vector2 = (ths[0] as Dictionary)["pos"] as Vector2
				var v: Vector2 = (ths[0] as Dictionary)["vel"] as Vector2
				if absf(p.y - (up_xr.position.y + up_xr.size.y * 0.5)) <= 16.0 and v.x * up_dir.x < 0.0:
					tp_down_ok = true
					break
		_check(tp_down_ok, "grenade thrown into upper portal doorway teleports to lower portal doorway and reverses x velocity")

		_projectiles.call("clear_all")
		var low_er: Rect2 = lower_p["entry_rect"] as Rect2
		var low_xr: Rect2 = lower_p["exit_rect"] as Rect2
		var low_dir: Vector2 = lower_p["dir"] as Vector2
		var start_bot: Vector2 = Vector2(low_er.position.x - 6.0 if low_dir.x > 0.0 else low_er.end.x + 6.0, low_er.position.y + low_er.size.y * 0.5)
		(_projectiles.get("throwables") as Array).append(_throw_entry(start_bot, Vector2(low_dir.x * 6.5, -0.5)))
		var tp_up_ok: bool = false
		for _t2: int in range(10):
			_projectiles.call("step_projectiles", STEP)
			var ths2: Array = _projectiles.get("throwables") as Array
			if ths2.size() == 1:
				var p2: Vector2 = (ths2[0] as Dictionary)["pos"] as Vector2
				var v2: Vector2 = (ths2[0] as Dictionary)["vel"] as Vector2
				if absf(p2.y - (low_xr.position.y + low_xr.size.y * 0.5)) <= 16.0 and v2.x * low_dir.x < 0.0:
					tp_up_ok = true
					break
		_check(tp_up_ok, "grenade thrown into lower portal doorway teleports to upper portal doorway and reverses x velocity")


func _no_map_fallback() -> void:
	_projectiles.call("clear_all")
	_world.map_loader = null
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 160.0), Vector2(0.0, 1.0)))
	_projectiles.call("step_projectiles", STEP)
	var values: Array = _projectiles.get("throwables") as Array
	_check(values.size() == 1 and ((values[0] as Dictionary)["pos"] as Vector2).y > 160.0, "fallback floor does not teleport a throwable already below y154 upward")
	_projectiles.call("clear_all")
	(_projectiles.get("throwables") as Array).append(_throw_entry(Vector2(0.0, 150.0), Vector2(10.0, 9.55)))
	_projectiles.call("step_projectiles", 1.0)
	values = _projectiles.get("throwables") as Array
	_check(values.size() == 1 and ((values[0] as Dictionary)["pos"] as Vector2).distance_to(Vector2(4.0, 153.5)) <= EPSILON, "fallback floor uses the exact downward crossing with bounce separation")
	_world.map_loader = _loader
