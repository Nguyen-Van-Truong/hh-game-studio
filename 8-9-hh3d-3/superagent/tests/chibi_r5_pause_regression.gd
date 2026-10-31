extends SceneTree
## FIXTURE_ONLY / NOT_E2E: uses Godot's InputMap and MatchController hotkey
## handler in-process, without desktop input. Verifies pause/resume freezes the
## simulation clock and HUD-facing state; it is not a full menu/restart oracle.

const MatchScript: Script = preload("res://game/core/match_controller.gd")

var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _world: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	_run()
	if _world != null and is_instance_valid(_world):
		_world.free()
	Input.action_release("ui_cancel")
	print("[CHIBI R5 PAUSE] FIXTURE_ONLY=1 NOT_E2E=1 " + ("PASS" if _failures == 0 else "FAIL") + " checks=" + str(_checks) + " failures=" + str(_failures))
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	_world = MatchScript.new() as Node2D
	_world.name = "ChibiPauseFixtureWorld"
	root.add_child(_world)
	_world.call("start_match", {"mode": "vs", "map_id": "rooftops", "two_player": false, "p1_char": "johnny", "p2_char": "agent", "bot_count": 1})
	_world.call("_physics_process", 1.0 / 60.0)
	var timer_before: float = float(_world.get("banner_timer"))
	var speed_before: float = float(_world.get("game_speed"))
	var first: Node2D = _first_fighter()
	var rig: Node = first.get("rig_view") as Node if first != null else null
	var source_before: float = float(rig.get("source_motion_frame")) if rig != null else 0.0
	var expr_before: String = str(rig.get("_current_expr_id")) if rig != null else ""
	var hud: Node = _world.get("hud_controller") as Node
	_check(rig != null and hud != null, "pause fixture has a real rig and HUD")
	if hud != null:
		hud.call("_process", 1.0 / 60.0)
	_world.set("active_cutin", {"timer": 4.0, "kind": "pause_fixture"})
	var cutin_before: float = float((_world.get("active_cutin") as Dictionary).get("timer", 0.0))
	var hud_trailing_before: Dictionary = hud.get("_trailing_hp_by_id").duplicate() as Dictionary if hud != null else {}
	_check(not bool(_world.get("is_paused")), "match starts unpaused")

	Input.action_press("ui_cancel")
	_world.call("_physics_process", 1.0 / 60.0)
	Input.action_release("ui_cancel")
	_check(bool(_world.get("is_paused")), "ui_cancel enters paused state through MatchController hotkey path")
	_check(is_equal_approx(float(_world.get("game_speed")), speed_before), "pause preserves game speed")
	var paused_timer: float = float(_world.get("banner_timer"))
	var paused_position: Vector2 = _first_fighter_position()
	for i: int in range(6):
		_world.call("_physics_process", 1.0 / 60.0)
		if hud != null:
			hud.call("_process", 1.0 / 60.0)
	_check(is_equal_approx(float(_world.get("banner_timer")), paused_timer), "paused simulation timer does not advance")
	_check(_first_fighter_position().distance_to(paused_position) <= 0.001, "paused fighter position does not advance")
	_check(rig == null or is_equal_approx(float(rig.get("source_motion_frame")), source_before), "pause freezes chibi source presentation frame")
	_check(rig == null or str(rig.get("_current_expr_id")) == expr_before, "pause freezes chibi expression state")
	_check(is_equal_approx(float((_world.get("active_cutin") as Dictionary).get("timer", 0.0)), cutin_before), "pause freezes cut-in timer")
	if hud != null:
		_check((hud.get("_trailing_hp_by_id") as Dictionary) == hud_trailing_before, "pause freezes HUD trailing HP state")

	Input.action_press("ui_cancel")
	_world.call("_physics_process", 1.0 / 60.0)
	Input.action_release("ui_cancel")
	_check(not bool(_world.get("is_paused")), "ui_cancel resumes through the same hotkey path")
	_world.call("_physics_process", 1.0 / 60.0)
	_check(float(_world.get("banner_timer")) < paused_timer, "resumed simulation timer advances")
	_check(float(_world.get("banner_timer")) < timer_before, "pause/resume does not reset round timer")


func _first_fighter_position() -> Vector2:
	var first: Node2D = _first_fighter()
	return first.global_position if first != null else Vector2.ZERO


func _first_fighter() -> Node2D:
	var fighters: Array = _world.get("fighters") as Array
	if fighters.is_empty() or not is_instance_valid(fighters[0]):
		return null
	return fighters[0] as Node2D


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R5 PAUSE] " + label)
