extends SceneTree
## FIXTURE_ONLY / NOT_E2E: deterministic FireHazardSystem particle physics and
## real Rooftops MapLoader support queries. No gameplay or parity acceptance.

const MapLoaderScript: Script = preload("res://game/world/map_loader.gd")
const HazardScript: Script = preload("res://game/world/fire_hazard_system.gd")
const PropScript: Script = preload("res://game/world/interactive_prop.gd")
const EPSILON: float = 0.001

class SupportWorld extends Node2D:
	var map_loader: Node2D = null
	var fighters: Array[Node2D] = []
	var props: Array[Node2D] = []

var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _world: SupportWorld = null
var _hazards: Node2D = null
var _loader: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run()
	if _world != null and is_instance_valid(_world):
		_world.free()
	_world = null
	_hazards = null
	_loader = null
	MapLoaderScript.cleanup_headless_singletons()
	print("[CHIBI R5 DEBRIS] FIXTURE_ONLY=1 NOT_E2E=1 ", "PASS" if _failures == 0 else "FAIL", " checks=", _checks, " failures=", _failures)
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	_world = SupportWorld.new()
	root.add_child(_world)
	_loader = MapLoaderScript.new() as Node2D
	_world.map_loader = _loader
	_loader.set("match_world", _world)
	_world.add_child(_loader)
	_loader.call("load_map", "rooftops")
	_hazards = HazardScript.new() as Node2D
	_hazards.set("match_world", _world)
	_world.add_child(_hazards)
	_check(str(_loader.get("current_map_id")) == "rooftops", "actual MapLoader loads Rooftops")
	_map_crossings()
	_prop_crossings()
	_left_entry_trajectory()
	_original_above_floor_trajectory()
	_default_floor_crossings()


func _floor(previous: Vector2, following: Vector2) -> float:
	return float(_hazards.call("_find_floor_y_between", previous, following))


func _map_crossings() -> void:
	_check(not bool(_hazards.call("_is_point_on_floor", Vector2(280.0, 160.0))), "original y160 point remains open air, not the default y154 floor")
	_check(absf(_floor(Vector2(270.0, 188.0), Vector2(270.0, 198.0)) - 194.0) <= EPSILON, "downward crossing finds the actual roof top y194")
	_check(absf(_floor(Vector2(270.0, 193.5), Vector2(270.0, 193.95)) - 194.0) <= EPSILON, "half-pixel roof contact remains stable for a settling particle")
	_check(is_inf(_floor(Vector2(270.0, 150.0), Vector2(270.0, 160.0))), "falling through y154 in map air has no artificial floor")
	_check(is_inf(_floor(Vector2(270.0, 210.0), Vector2(270.0, 190.0))), "upward movement through the roof underside is not a downward support hit")
	_check(is_inf(_floor(Vector2(270.0, 198.0), Vector2(270.0, 199.0))), "a point already inside the roof is not a new floor crossing")
	_check(is_inf(_floor(Vector2(190.0, 160.0), Vector2(186.0, 162.0))), "descending side entry into the tall left wall does not invent a floor at y162")
	_check(is_inf(_floor(Vector2(180.0, 160.0), Vector2(180.0, 161.0))), "falling inside the tall wall does not create an interior support")


func _prop_crossings() -> void:
	var crate: Node2D = PropScript.new() as Node2D
	_world.add_child(crate)
	crate.set("match_world", _world)
	crate.set("map_loader", _loader)
	crate.call("setup_prop", "CRATE", Vector2(270.0, 186.5), 0.0, "debris_support_fixture", 9501)
	crate.set("on_ground", true)
	_world.props.append(crate)
	_hazards.call("_rebuild_support_rects_cache")
	var support: Rect2 = crate.call("get_solid_support_rect") as Rect2
	_check(absf(support.position.y - 179.0) <= EPSILON, "real crate fixture rests flush on roof y194 with top y179")
	_check(absf(_floor(Vector2(270.0, 174.0), Vector2(270.0, 184.0)) - support.position.y) <= EPSILON, "a real grounded prop top stops a downward particle before the map roof")
	_check(is_inf(_floor(Vector2(258.0, 184.0), Vector2(265.0, 185.0))), "entering the crate side below its top does not become floor contact")
	_check(is_inf(_floor(Vector2(270.0, 187.0), Vector2(270.0, 188.0))), "crate interior is not a new support surface")
	_check(is_inf(_floor(Vector2(270.0, 190.0), Vector2(270.0, 175.0))), "ascending through the crate underside is not a downward support hit")
	_check(is_inf(_floor(Vector2(250.0, 174.0), Vector2(265.0, 184.0))), "diagonal side entry after missing the crate top does not invent support")
	_world.props.clear()
	crate.free()
	_hazards.call("_rebuild_support_rects_cache")


func _particle(pos: Vector2, vel: Vector2, category: String = "") -> Dictionary:
	var result: Dictionary = {
		"pos": pos, "vel": vel, "rot": 0.0, "rot_vel": 0.0,
		"age": 0.0, "max_age": 90.0,
	}
	if not category.is_empty():
		result["category"] = category
	return result


func _left_entry_trajectory() -> void:
	_hazards.call("clear_all")
	# All four values are interior to spawn_gibs()'s valid ranges for the master
	# fixture's (270,155) origin and (0,-1) impulse. The old endpoint fallback
	# settled this trajectory inside the left wall around y180 after 35 ticks.
	(_hazards.get("gibs") as Array).append(_particle(Vector2(266.426194, 147.707639), Vector2(-2.775515, -5.420414)))
	var rested_inside_wall: bool = false
	for _tick: int in range(42):
		_hazards.call("step_hazards", 1.0)
		var values: Array = _hazards.get("gibs") as Array
		if values.is_empty():
			continue
		var gib: Dictionary = values[0] as Dictionary
		var pos: Vector2 = gib["pos"] as Vector2
		if bool(gib.get("resting", false)) and bool(_loader.call("is_point_solid", pos, true)):
			rested_inside_wall = true
	var gibs: Array = _hazards.get("gibs") as Array
	_check(gibs.size() == 1, "known valid left-entry gib survives the 42-tick fixture")
	_check(not rested_inside_wall, "known left-entry gib never rests inside a map wall")
	if not gibs.is_empty():
		var final: Dictionary = gibs[0] as Dictionary
		var final_pos: Vector2 = final["pos"] as Vector2
		var final_vel: Vector2 = final["vel"] as Vector2
		_check(not bool(final.get("resting", false)) and final_vel.y > 0.0, "known left-entry gib keeps falling through the wall instead of falsely resting at its side")
		print("[CHIBI R5 DEBRIS] left_entry_final=", final_pos, " resting=", final.get("resting", false))


func _original_above_floor_trajectory() -> void:
	_hazards.call("clear_all")
	(_hazards.get("prop_debris") as Array).append(_particle(Vector2(270.0, 149.0), Vector2(0.0, -3.6), "crate"))
	(_hazards.get("gibs") as Array).append(_particle(Vector2(270.0, 143.0), Vector2(0.0, -5.6)))
	for _tick: int in range(42):
		_hazards.call("step_hazards", 1.0)
	var debris: Array = _hazards.get("prop_debris") as Array
	var gibs: Array = _hazards.get("gibs") as Array
	_check(debris.size() == 1 and gibs.size() == 1, "deterministic original-height debris and gib survive 42 ticks")
	if debris.size() == 1 and gibs.size() == 1:
		var debris_pos: Vector2 = (debris[0] as Dictionary)["pos"] as Vector2
		var gib_pos: Vector2 = (gibs[0] as Dictionary)["pos"] as Vector2
		_check(debris_pos.y >= 188.0 and gib_pos.y >= 188.0, "original 42-tick y188 acceptance remains unchanged for real roof trajectories")
		print("[CHIBI R5 DEBRIS] original_height_final debris=", debris_pos, " gib=", gib_pos)


func _default_floor_crossings() -> void:
	_world.map_loader = null
	_hazards.call("_rebuild_support_rects_cache")
	_check(absf(_floor(Vector2(0.0, 150.0), Vector2(0.0, 156.0)) - 154.0) <= EPSILON, "without a map API the default y154 top crossing remains available")
	_check(is_inf(_floor(Vector2(0.0, 160.0), Vector2(0.0, 161.0))), "default-floor fallback does not turn a point below the floor into new contact")
	_check(is_inf(_floor(Vector2(0.0, 160.0), Vector2(0.0, 150.0))), "default-floor fallback does not catch upward underside movement")
	_world.map_loader = _loader


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R5 DEBRIS] " + label)
