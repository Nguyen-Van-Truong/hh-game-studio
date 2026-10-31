extends SceneTree
## FIXTURE_ONLY / NOT_E2E: real MatchController dropped-gun spawning/stepping
## with real MapLoader queries and InteractiveProp geometry. No input parity claim.

const MatchScript: Script = preload("res://game/core/match_controller.gd")
const MapScript: Script = preload("res://game/world/map_loader.gd")
const PropScript: Script = preload("res://game/world/interactive_prop.gd")
const STEP: float = 0.4
const EPSILON: float = 0.001

var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _match: Node2D = null
var _loader: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run()
	_match.free()
	_match = null
	_loader = null
	MapScript.cleanup_headless_singletons()
	print("[CHIBI R6 PICKUPS] FIXTURE_ONLY=1 NOT_E2E=1 ", "PASS" if _failures == 0 else "FAIL", " checks=", _checks, " failures=", _failures)
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	seed(6282026)
	_match = MatchScript.new() as Node2D
	_match.set_physics_process(false)
	root.add_child(_match)
	_match.set_physics_process(false)
	_match.set_process(false)
	_loader = _match.get("map_loader") as Node2D
	_check(_loader != null and _match.get("_pickups_container") != null, "actual MatchController creates its pickup subsystem once")
	_pit_and_one_way()
	_swept_narrow_edges()
	_wall_and_ceiling()
	_solid_props()
	_lost_support()
	_moving_lifts()
	_real_ladder_shafts()
	_horizontal_glass_and_prop_support()
	_below_world_cleanup()


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R6 PICKUPS] " + label)


func _reset() -> void:
	_match.call("_clear_match_entities")
	_loader.call("_clear_map_state")
	_loader.set("map_bounds", Rect2(-500.0, -500.0, 1000.0, 1000.0))


func _drop(position: Vector2, velocity: Vector2) -> void:
	_match.call("spawn_dropped_weapon", "PISTOL", position, 12, velocity)


func _pickups() -> Array:
	return _match.get("pickups") as Array


func _first() -> Dictionary:
	var values: Array = _pickups()
	return values[0] as Dictionary if not values.is_empty() else {}


func _step(count: int = 1, step_size: float = STEP) -> void:
	for _tick: int in range(count):
		_match.call("_step_pickups", step_size)


func _pit_and_one_way() -> void:
	_reset()
	_drop(Vector2(0.0, 148.0), Vector2(0.0, 5.0))
	_step(12)
	var value: Dictionary = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).y > 170.0 and not bool(value["settled"]), "a dropped gun keeps falling through open map air past y154")
	_reset()
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 20.0, 20.0, 2.0))
	_drop(Vector2(20.0, 21.0), Vector2(0.0, 1.0))
	_step()
	value = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).y > 21.0 and (value["vel"] as Vector2).y > 0.0, "a gun already below a one-way top does not snap upward")
	_match.call("_clear_match_entities")
	_drop(Vector2(20.0, 30.0), Vector2(0.0, -20.0))
	_step(2)
	value = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).y < 20.0 and (value["vel"] as Vector2).y < 0.0, "a gun ascending from below passes through a one-way platform")


func _swept_narrow_edges() -> void:
	_reset()
	(_loader.get("cloud_rects") as Array).append(Rect2(10.0, 20.0, 4.0, 2.0))
	_drop(Vector2(0.0, 16.0), Vector2(30.0 / 0.985, 8.58))
	_step(1, 1.0)
	var value: Dictionary = _first()
	_check(not value.is_empty() and absf((value["pos"] as Vector2).y - 19.98) <= EPSILON and (value["pos"] as Vector2).x >= 10.0 and (value["pos"] as Vector2).x <= 14.0 and (value["vel"] as Vector2).y < 0.0, "swept dropped gun lands on a narrow top even when its endpoint passed the edge")
	_match.call("_clear_match_entities")
	_drop(Vector2(0.0, 18.0), Vector2(12.0 / 0.985, 8.58))
	_step(1, 1.0)
	value = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).distance_to(Vector2(12.0, 27.0)) <= EPSILON, "endpoint above a platform footprint does not invent contact after missing its top")
	_reset()
	(_loader.get("cloud_rects") as Array).append(Rect2(0.0, 20.0, 10.0, 2.0))
	_drop(Vector2(9.5, 19.98), Vector2(4.0, 0.0))
	_step(8)
	value = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).x > 10.0 and (value["pos"] as Vector2).y > 20.0 and not bool(value["settled"]), "a moving gun leaves a platform edge and resumes falling")


func _wall_and_ceiling() -> void:
	_reset()
	(_loader.get("solid_rects") as Array).append(Rect2(10.0, -50.0, 2.0, 100.0))
	_drop(Vector2.ZERO, Vector2(100.0, 0.0))
	_step(1, 1.0)
	var value: Dictionary = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).x < 10.0 and (value["pos"] as Vector2).x > 9.9 and (value["vel"] as Vector2).x < 0.0, "a fast dropped gun reflects from a thin solid wall without tunnelling")
	_reset()
	(_loader.get("solid_rects") as Array).append(Rect2(-50.0, 20.0, 100.0, 2.0))
	_drop(Vector2(0.0, 30.0), Vector2(0.0, -30.0))
	_step()
	value = _first()
	_check(not value.is_empty() and absf((value["pos"] as Vector2).y - 26.02) <= EPSILON and (value["vel"] as Vector2).y > 0.0, "gun upper body contacts a solid ceiling before its foot enters the ceiling")


func _solid_props() -> void:
	_reset()
	var crate: Node2D = PropScript.new() as Node2D
	_match.add_child(crate)
	crate.set("match_world", _match)
	crate.set("map_loader", _loader)
	crate.call("setup_prop", "CRATE", Vector2(0.0, 20.0), 0.0, "pickup_ceiling_fixture", 9601)
	(_match.get("props") as Array).append(crate)
	var solid_rect: Rect2 = crate.call("get_solid_support_rect") as Rect2
	_check(solid_rect.size.x > 0.0 and solid_rect.size.y > 0.0, "real crate exposes its solid support rectangle")
	_drop(Vector2(0.0, 40.0), Vector2(0.0, -100.0))
	_step()
	var value: Dictionary = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).y >= solid_rect.end.y + 4.0 and (value["vel"] as Vector2).y > 0.0, "gun upper body contacts a crate underside without entering the crate")
	# Keep the real prop instance but make it non-solid to exercise filtering.
	var values: Array = _pickups()
	for pickup: Dictionary in values:
		var node: Node2D = pickup.get("node") as Node2D
		if node != null and is_instance_valid(node):
			node.free()
	values.clear()
	crate.set("has_solid_hitbox", false)
	_drop(Vector2(0.0, 40.0), Vector2(0.0, -100.0))
	_step()
	value = _first()
	_check(not value.is_empty() and (value["pos"] as Vector2).y < solid_rect.position.y and (value["vel"] as Vector2).y < 0.0, "non-solid prop does not become an invisible ceiling")


func _lost_support() -> void:
	_reset()
	(_loader.get("cloud_rects") as Array).append(Rect2(-10.0, 20.0, 20.0, 2.0))
	_drop(Vector2(0.0, 19.98), Vector2.ZERO)
	_step()
	_check(not _first().is_empty() and bool(_first()["settled"]), "low-speed gun settles on a real top contact")
	(_loader.get("cloud_rects") as Array).clear()
	_step(3)
	var value: Dictionary = _first()
	_check(not value.is_empty() and not bool(value["settled"]) and (value["pos"] as Vector2).y > 20.0, "settled gun resumes gravity when its support disappears")


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
		_reset()
		var lift: Dictionary = _lift("vertical", speed)
		_drop(Vector2(0.0, 27.98), Vector2.ZERO)
		_first()["settled"] = true
		var follows_lift: bool = true
		for _tick: int in range(6):
			_loader.call("step_map", STEP)
			_step()
			var value: Dictionary = _first()
			if value.is_empty():
				follows_lift = false
				break
			follows_lift = follows_lift and bool(value["settled"]) and absf((value["pos"] as Vector2).y - ((lift["rect"] as Rect2).position.y - 0.02)) <= EPSILON
		_check(follows_lift, "settled gun follows a vertical lift exactly once each tick, speed=%s" % speed)
		(_loader.get("elevators") as Array).clear()
		var before: Vector2 = _first()["pos"] as Vector2
		_loader.call("step_map", STEP)
		_step(3)
		var after: Dictionary = _first()
		_check(not after.is_empty() and (after["pos"] as Vector2).y > before.y and not bool(after["settled"]), "gun resumes falling after lift removal, speed=%s" % speed)
	_reset()
	var horizontal: Dictionary = _lift("horizontal", 12.0)
	_drop(Vector2(0.0, 27.98), Vector2.ZERO)
	_first()["settled"] = true
	_loader.call("step_map", STEP)
	_step()
	_check(not _first().is_empty() and (_first()["pos"] as Vector2).distance_to((horizontal["current_pos"] as Vector2) + Vector2(0.0, -2.02)) <= EPSILON, "settled gun follows horizontal lift once without extra motion")
	_reset()
	var rising: Dictionary = _lift("vertical", -12.0)
	_drop(Vector2(0.0, 27.0), Vector2.ZERO)
	_loader.call("step_map", STEP)
	_step()
	var caught: Dictionary = _first()
	_check(not caught.is_empty() and bool(caught["settled"]) and absf((caught["pos"] as Vector2).y - ((rising["rect"] as Rect2).position.y - 0.02)) <= EPSILON, "relative lift sweep catches a previously airborne gun from above")
	_reset()
	_lift("vertical", -12.0)
	_drop(Vector2(0.0, 29.0), Vector2.ZERO)
	_loader.call("step_map", STEP)
	_step()
	_check(not _first().is_empty() and (_first()["pos"] as Vector2).y > 29.0, "rising lift does not snap an underside gun onto its top")
	_reset()
	_lift("vertical", -12.0)
	(_loader.get("solid_rects") as Array).append(Rect2(-20.0, 20.0, 40.0, 2.0))
	_drop(Vector2(0.0, 27.98), Vector2.ZERO)
	_first()["settled"] = true
	_loader.call("step_map", STEP)
	_step()
	_check(not _first().is_empty() and (_first()["pos"] as Vector2).y >= 26.0 and not bool(_first()["settled"]), "settled carried gun is blocked below a solid ceiling by its upper body")
	_reset()
	_lift("vertical", -24.0)
	(_loader.get("solid_rects") as Array).append(Rect2(-20.0, 20.0, 40.0, 2.0))
	_drop(Vector2(0.0, 27.0), Vector2.ZERO)
	_loader.call("step_map", STEP)
	_step()
	_check(not _first().is_empty() and (_first()["pos"] as Vector2).y >= 26.0 and not bool(_loader.call("is_point_solid", (_first()["pos"] as Vector2) + Vector2(0.0, -4.0), false)), "rising lift's post-impact carry cannot move a gun upper body through the next ceiling")
	_reset()
	var static_after_step: Dictionary = _lift("vertical", -12.0)
	_loader.call("step_map", STEP)
	# Consume the map interval with an unrelated airborne pickup, then replace
	# it without stepping the map. The next query must use the current lift.
	_drop(Vector2(100.0, 10.0), Vector2.ZERO)
	_step()
	_match.call("_clear_match_entities")
	var below_current: float = (static_after_step["rect"] as Rect2).position.y + 1.0
	_drop(Vector2(0.0, below_current), Vector2.ZERO)
	_step()
	_check(not _first().is_empty() and (_first()["pos"] as Vector2).y > below_current, "second pickup step without map step cannot replay an old rising lift")


func _real_ladder_shafts() -> void:
	for shaft_x: float in [-298.0, 298.0]:
		_reset()
		_loader.call("load_map", "steel_harbor")
		_drop(Vector2(shaft_x, -121.0), Vector2.ZERO)
		var reached_floor: bool = false
		var outside_solids: bool = true
		for _tick: int in range(120):
			_step()
			var value: Dictionary = _first()
			if value.is_empty():
				break
			var position: Vector2 = value["pos"] as Vector2
			reached_floor = reached_floor or position.y >= 11.0
			outside_solids = outside_solids and not bool(_loader.call("is_point_solid", position, false)) and not bool(_loader.call("is_point_solid", position + Vector2(0.0, -4.0), false))
		_check(reached_floor and outside_solids, "real dropped gun falls through opened Steel Harbor shaft x=%s to tower floor y12" % shaft_x)


func _horizontal_glass_and_prop_support() -> void:
	# 1. Pickups spawned or dropped over intact horizontal glass on steel_harbor (x=-14..14, y=-52)
	# must land and remain settled on the glass instead of falling through into the central abyss.
	_reset()
	_loader.call("load_map", "steel_harbor")
	_match.call("spawn_weapon_pickup", "MEDKIT", Vector2(0.0, -52.0), 1, 0, true)
	_step(24)
	var medkit: Dictionary = _first()
	_check(not medkit.is_empty() and bool(medkit["settled"]) and absf((medkit["pos"] as Vector2).y - (-52.02)) <= 0.1, "pickup spawned on Steel Harbor cyan horizontal glass bridge lands and stays on the glass")
	# Shattering the glass bridge via damage_glass_in_rect causes the settled pickup to lose support and fall
	_loader.call("damage_glass_in_rect", Rect2(-14.0, -56.0, 28.0, 8.0), 100.0, Vector2(0.0, 5.0))
	_step(6)
	medkit = _first()
	_check(not medkit.is_empty() and not bool(medkit["settled"]) and (medkit["pos"] as Vector2).y > -51.5, "pickup resting on horizontal glass bridge resumes falling once the glass shatters")
	# 2. Settled pickup on top of an intact solid crate stays settled until crate breaks
	_reset()
	var crate: Node2D = PropScript.new() as Node2D
	_match.add_child(crate)
	crate.set("match_world", _match)
	crate.set("map_loader", _loader)
	crate.call("setup_prop", "CRATE", Vector2(0.0, 20.0), 0.0, "pickup_top_support_fixture", 9602)
	(_match.get("props") as Array).append(crate)
	var srect: Rect2 = crate.call("get_solid_support_rect") as Rect2
	_drop(Vector2(srect.get_center().x, srect.position.y - 0.02), Vector2.ZERO)
	_step(6)
	var on_crate: Dictionary = _first()
	_check(not on_crate.is_empty() and bool(on_crate["settled"]) and absf((on_crate["pos"] as Vector2).y - (srect.position.y - 0.02)) <= 0.1, "dropped weapon lands and stays settled on top of an intact solid crate")
	crate.set("is_destroyed", true)
	_step(4)
	on_crate = _first()
	_check(not on_crate.is_empty() and not bool(on_crate["settled"]) and (on_crate["pos"] as Vector2).y > srect.position.y, "weapon resting on solid crate resumes falling when crate breaks")


func _below_world_cleanup() -> void:
	_reset()
	_loader.set("map_bounds", Rect2(-50.0, -50.0, 100.0, 100.0))
	_drop(Vector2(0.0, 111.0), Vector2(0.0, 1.0))
	var node: Node2D = _first().get("node") as Node2D
	_step()
	_check(_pickups().is_empty() and not is_instance_valid(node), "gun below map death margin is removed with its visual node")
