extends SceneTree
## FIXTURE_ONLY / NOT_E2E: real Steel Harbor geometry and ladder-entry checks.
## The six authored ladder mouths must be open to downward rays while adjacent
## slabs remain solid. A single real FighterController climb supplements the
## geometry checks; this fixture does not claim visual or Y8 parity.

const MapLoaderScript: Script = preload("res://game/world/map_loader.gd")
const FighterScript: Script = preload("res://game/fighter/fighter_controller.gd")
const BotControllerScript: Script = preload("res://game/ai/bot_controller.gd")
const EPSILON: float = 0.01


class HatchWorld extends Node2D:
	var map_loader: Node2D = null
	var fighters: Array[Node2D] = []
	var props: Array[Node2D] = []


var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _world: HatchWorld = null
var _loader: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run()
	if _world != null and is_instance_valid(_world):
		_world.free()
	_world = null
	_loader = null
	MapLoaderScript.cleanup_headless_singletons()
	print("[CHIBI R6 HATCH] FIXTURE_ONLY=1 NOT_E2E=1 ", "PASS" if _failures == 0 else "FAIL", " checks=", _checks, " failures=", _failures)
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	_world = HatchWorld.new()
	root.add_child(_world)
	_loader = MapLoaderScript.new() as Node2D
	_loader.set("match_world", _world)
	_world.map_loader = _loader
	_world.add_child(_loader)
	_loader.call("load_map", "steel_harbor")
	_check(str(_loader.get("current_map_id")) == "steel_harbor", "real Steel Harbor map loads")
	_open_mouths()
	_side_floors_and_ceiling()
	_ladder_sensors()
	_controller_climb()
	_bot_route_audit()


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R6 HATCH] " + label)


func _ray_solid(from_pt: Vector2, to_pt: Vector2) -> Dictionary:
	# Exclude props and one-way slope clouds: these are authored static mouth/slab checks.
	return _loader.call("raycast_solid", from_pt, to_pt, -1, false, false) as Dictionary


func _open_mouths() -> void:
	# Two crane mouths, two tower-roof mouths, and two deck mouths = six openings.
	var mouths: Array[Dictionary] = [
		{"label": "left crane mouth", "x": -298.0, "from_y": -120.0, "to_y": -100.0, "floor_y": 12.0},
		{"label": "right crane mouth", "x": 298.0, "from_y": -120.0, "to_y": -100.0, "floor_y": 12.0},
		{"label": "left tower-roof mouth", "x": -298.0, "from_y": -64.0, "to_y": -40.0, "floor_y": 12.0},
		{"label": "right tower-roof mouth", "x": 298.0, "from_y": -64.0, "to_y": -40.0, "floor_y": 12.0},
		{"label": "left deck mouth", "x": -68.0, "from_y": 70.0, "to_y": 90.0, "floor_y": 140.0},
		{"label": "right deck mouth", "x": 68.0, "from_y": 70.0, "to_y": 90.0, "floor_y": 140.0},
	]
	for mouth: Dictionary in mouths:
		var x: float = float(mouth["x"])
		var from_pt := Vector2(x, float(mouth["from_y"]))
		var to_pt := Vector2(x, float(mouth["to_y"]))
		var one_way: Dictionary = _loader.call("raycast_one_way", from_pt, to_pt) as Dictionary
		_check(not bool(one_way.get("hit", false)), str(mouth["label"]) + " has no CLOUD grating")
		var solid: Dictionary = _ray_solid(from_pt, to_pt)
		_check(not bool(solid.get("hit", false)), str(mouth["label"]) + " has no solid blocker")
		var floor_hit: Dictionary = _ray_solid(from_pt, Vector2(x, float(mouth["floor_y"])))
		_check(bool(floor_hit.get("hit", false)), str(mouth["label"]) + " downward ray reaches the next solid floor")


func _side_floors_and_ceiling() -> void:
	# Each side of the four slab openings remains a real solid surface.
	var side_rays: Array[Dictionary] = [
		{"label": "left tower-roof flank", "from": Vector2(-320.0, -70.0), "to": Vector2(-320.0, -40.0), "top_y": -56.0},
		{"label": "right tower-roof flank", "from": Vector2(-276.0, -70.0), "to": Vector2(-276.0, -40.0), "top_y": -56.0},
		{"label": "left deck flank", "from": Vector2(-88.0, 70.0), "to": Vector2(-88.0, 110.0), "top_y": 76.0},
		{"label": "right deck flank", "from": Vector2(-50.0, 70.0), "to": Vector2(-50.0, 110.0), "top_y": 76.0},
	]
	for ray: Dictionary in side_rays:
		var hit: Dictionary = _ray_solid(ray["from"] as Vector2, ray["to"] as Vector2)
		var hit_pos: Vector2 = hit.get("pos", Vector2(INF, INF)) as Vector2
		_check(bool(hit.get("hit", false)) and absf(hit_pos.y - float(ray["top_y"])) <= EPSILON, str(ray["label"]) + " still collides at its authored top")

	# The roof is still closed beside the ladder mouth; only its 20u shaft is open.
	for x: float in [-320.0, 320.0]:
		var hit: Dictionary = _ray_solid(Vector2(x, -120.0), Vector2(x, -40.0))
		var hit_pos: Vector2 = hit.get("pos", Vector2(INF, INF)) as Vector2
		_check(bool(hit.get("hit", false)) and absf(hit_pos.y - (-56.0)) <= EPSILON, "tower roof has no ceiling hole at x=" + str(x))


func _ladder_sensors() -> void:
	var ladders: Array[Dictionary] = [
		{"label": "left upper", "x": -298.0, "y": -80.0, "h": 132.0},
		{"label": "right upper", "x": 298.0, "y": -80.0, "h": 132.0},
		{"label": "left pit", "x": -68.0, "y": 110.0, "h": 76.0},
		{"label": "right pit", "x": 68.0, "y": 110.0, "h": 76.0},
	]
	for ladder_spec: Dictionary in ladders:
		var rect: Rect2 = _loader.call("get_ladder_at", Vector2(float(ladder_spec["x"]), float(ladder_spec["y"]))) as Rect2
		_check(rect.size.x == 16.0 and rect.size.y == float(ladder_spec["h"]), str(ladder_spec["label"]) + " ladder sensor stays 16u wide")


func _controller_climb() -> void:
	# This uses the production controller's input path. The upper mouth is open,
	# so the controller should grab the ladder and reach its open crane entry.
	var fighter: Node2D = FighterScript.new() as Node2D
	fighter.set("match_world", _world)
	fighter.set("map_loader_override", _loader)
	_world.add_child(fighter)
	_world.fighters.append(fighter)
	fighter.call("setup_fighter", 0, "johnny", Vector2(-298.0, 12.0), false, 0, 2)
	var grabbed: bool = false
	var highest_y: float = 12.0
	for tick: int in range(100):
		var tap: bool = tick == 0
		fighter.call("step_fighter", 1.0, {"up": true, "up_just_pressed": tap, "jump": true, "jump_just_pressed": tap})
		grabbed = grabbed or bool(fighter.get("climbing"))
		highest_y = minf(highest_y, fighter.global_position.y)
	_check(grabbed, "real FighterController grabs the left upper ladder")
	_check(highest_y <= -100.0, "real FighterController climbs through the opened crane mouth")


func _bot_route_audit() -> void:
	# Diagnostic coverage for the production A* + controller handoff. The route
	# report is intentionally separate from acceptance checks: it records whether
	# a bot is steered back toward a hole-center node after a side dismount.
	var bot: RefCounted = BotControllerScript.new(2)
	var upper_path: Array = bot.call("find_path", Vector2(298.0, 12.0), Vector2(298.0, -108.0), _loader) as Array
	var upper_ladder_steps: int = 0
	for step_data: Dictionary in upper_path:
		if str(step_data.get("action", "")).to_upper() == "LADDER":
			upper_ladder_steps += 1
	_check(not upper_path.is_empty() and upper_ladder_steps >= 2, "BotController right upper route keeps both authored LADDER edges")

	var upper_fighter: Node2D = FighterScript.new() as Node2D
	upper_fighter.set("match_world", _world)
	upper_fighter.set("map_loader_override", _loader)
	_world.add_child(upper_fighter)
	_world.fighters.append(upper_fighter)
	upper_fighter.call("setup_fighter", 1, "johnny", Vector2(298.0, 12.0), true, 0, 2)
	var upper_exit_x: float = NAN
	var upper_exit_tick: int = -1
	var upper_steered_to_center: bool = false
	var upper_fell_after_exit: bool = false
	for upper_tick: int in range(180):
		var input: Dictionary = bot.call("_follow_path_towards", upper_fighter, Vector2(298.0, -108.0), _loader, 1.0) as Dictionary
		upper_fighter.call("step_fighter", 1.0, input)
		var upper_y: float = upper_fighter.global_position.y
		var upper_climbing: bool = bool(upper_fighter.get("climbing"))
		if upper_y <= -104.0:
			if not upper_climbing and is_nan(upper_exit_x):
				upper_exit_x = upper_fighter.global_position.x
				upper_exit_tick = upper_tick
			if upper_exit_tick >= 0 and upper_tick > upper_exit_tick and not upper_climbing and absf(upper_fighter.global_position.x - 298.0) > 8.0:
				var steer_left: bool = bool(input.get("left", false)) and upper_fighter.global_position.x > 298.0
				var steer_right: bool = bool(input.get("right", false)) and upper_fighter.global_position.x < 298.0
				upper_steered_to_center = upper_steered_to_center or steer_left or steer_right
		if upper_exit_tick >= 0 and upper_tick > upper_exit_tick and upper_y > -80.0:
			upper_fell_after_exit = true
	_check(not is_nan(upper_exit_x), "BotController exits the right upper ladder")
	_check(not upper_steered_to_center, "BotController does not steer back into the right upper mouth")
	_check(not upper_fell_after_exit, "BotController remains supported after the right upper dismount")
	# Changing the goal must release the side-exit hold and allow descent.
	# Pin the authored reverse LADDER edges in this fixture: the unrestricted
	# A* prefers a portal, whose map stepping is deliberately outside this test.
	var reverse_path: Array[Dictionary] = [
		{"from_pos": Vector2(298.0, -108.0), "target_pos": Vector2(298.0, -56.0), "action": "LADDER"},
		{"from_pos": Vector2(298.0, -56.0), "target_pos": Vector2(298.0, 12.0), "action": "LADDER"},
	]
	bot.set("current_path", reverse_path)
	bot.set("current_path_index", 0)
	bot.set("_path_recalc_timer", 1000.0)
	var descended: bool = false
	for _down_tick: int in range(180):
		var descent_input: Dictionary = bot.call("_follow_path_towards", upper_fighter, Vector2(298.0, 12.0), _loader, 1.0) as Dictionary
		upper_fighter.call("step_fighter", 1.0, descent_input)
		if bool(upper_fighter.get("on_ground")) and absf(upper_fighter.global_position.y - 12.0) <= 1.5:
			descended = true
			break
	_check(descended, "BotController changes goal and descends from the supported upper exit; pos=" + str(upper_fighter.global_position) + " climb=" + str(upper_fighter.get("climbing")) + " path=" + str(bot.get("current_path")))

	var cross_bot: RefCounted = BotControllerScript.new(2)
	var cross_fighter: Node2D = FighterScript.new() as Node2D
	cross_fighter.set("match_world", _world)
	cross_fighter.set("map_loader_override", _loader)
	_world.add_child(cross_fighter)
	_world.fighters.append(cross_fighter)
	cross_fighter.call("setup_fighter", 0, "johnny", Vector2(50.0, 76.0), true, 0, 2)
	var crossed_deck_mouth: bool = false
	var fell_in_deck_mouth: bool = false
	for _cross_tick: int in range(100):
		var cross_input: Dictionary = cross_bot.call("_follow_path_towards", cross_fighter, Vector2(164.0, 76.0), _loader, 1.0) as Dictionary
		cross_fighter.call("step_fighter", 1.0, cross_input)
		if cross_fighter.global_position.x >= 80.0:
			crossed_deck_mouth = true
		if crossed_deck_mouth and cross_fighter.global_position.y > 100.0:
			fell_in_deck_mouth = true

	print("[CHIBI R6 HATCH BOT AUDIT] upper_path_steps=", upper_path.size(), " upper_ladder_steps=", upper_ladder_steps, " upper_exit_x=", upper_exit_x, " steered_to_center=", upper_steered_to_center, " fell_after_exit=", upper_fell_after_exit, " deck_crossed=", crossed_deck_mouth, " deck_fell=", fell_in_deck_mouth)

