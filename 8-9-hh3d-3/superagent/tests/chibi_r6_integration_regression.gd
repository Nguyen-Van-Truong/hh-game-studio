extends SceneTree
## Real controller -> rig -> effect anchors. Fixture, not combat E2E.
const Fighter = preload("res://game/fighter/fighter_controller.gd")
const Hazards = preload("res://game/world/fire_hazard_system.gd")
var checks: int = 0
var failures: int = 0
var ran: bool = false

func _process(_dt: float) -> bool:
	if ran:
		return true
	ran = true
	var actor: Node2D = Fighter.new()
	root.add_child(actor)
	actor.set_process(false)
	actor.set_physics_process(false)
	actor.call("setup_fighter", 0, "johnny", Vector2(120.0, 200.0), false)
	var view: Node2D = actor.get("rig_view") as Node2D
	var fire: Node2D = Hazards.new()
	fire.set("_textures_loaded", true)
	root.add_child(fire)
	actor.set("on_ground", false)
	actor.call("_set_state", "JUMP", true)
	actor.set("air_velocity", Vector2(1.0, -4.0))
	actor.call("_sync_rig_view")
	var ascending: Dictionary = view.call("get_chibi_pose_snapshot") as Dictionary
	actor.set("air_velocity", Vector2(1.0, 5.0))
	actor.call("_sync_rig_view")
	var descending: Dictionary = view.call("get_chibi_pose_snapshot") as Dictionary
	_check(ascending["phase"] != descending["phase"], "real controller velocity changes air phase while same animation frame")
	_check(ascending["hand_front"] != descending["hand_front"], "ascent/descent hand silhouettes differ")
	_check((view.get("chibi_motion") as Dictionary).get("grounded") == false, "on_ground forwarded accurately")
	actor.call("_set_state", "IDLE", true)
	actor.set("on_ground", true)
	actor.set("burn_state", 35.0)
	actor.call("_sync_rig_view")
	_check(view.call("get_current_expression_id") == "WIDE_MOUTH_SHOUT", "burning neutral actor no longer smiles")
	var hp_before: float = float(actor.get("hp"))
	var spec: Array = fire.call("get_chibi_burn_draw_specs", actor, false) as Array
	_check(spec.size() == 3, "compact burn anchors attached to hip and both boots")
	var anchors: PackedVector2Array = view.call("get_chibi_burn_anchors") as PackedVector2Array
	for i: int in range(spec.size()):
		_check(((spec[i] as Dictionary)["position"] as Vector2).distance_to(anchors[i] + Vector2(0.0, 0.8)) < 0.001, "render spec follows posed anchor")
	actor.set("facing", -1)
	actor.call("_sync_rig_view")
	var mirrored: PackedVector2Array = view.call("get_chibi_burn_anchors") as PackedVector2Array
	for i: int in range(anchors.size()):
		_check(absf(anchors[i].x + mirrored[i].x - actor.global_position.x * 2.0) < 0.001, "burn anchors mirror with fighter")
	actor.call("_set_state", "ROLL", true)
	actor.call("_advance_animation", 2.0)
	actor.call("_sync_rig_view")
	var rolled: PackedVector2Array = view.call("get_chibi_burn_anchors") as PackedVector2Array
	_check(rolled != mirrored, "roll moves fire attachment instead of leaving it over standing body")
	_check(float(actor.get("hp")) == hp_before and float(actor.get("burn_state")) == 35.0, "presentation does not change burn damage/state")
	actor.set("hp", 0.0)
	actor.set("is_dead", true)
	actor.set("burned", true)
	actor.call("_set_state", "DEAD", true)
	actor.call("_sync_rig_view")
	_check(view.call("get_current_expression_id") == "KO_STARS", "KO overrides burning face")
	actor.set("is_gibbed", true)
	_check((fire.call("get_chibi_burn_draw_specs", actor, true) as Array).is_empty(), "removed body has no attached phantom fire")
	fire.set("external_fighters", [actor])
	fire.call("step_hazards", 1.0)
	_check((fire.get("flame_puffs") as Array).is_empty() and (fire.get("smoke_puffs") as Array).is_empty(), "gibbed body emits no new world-space flame or smoke")
	_check(not (fire.get("_fighter_burn_emit_state") as Dictionary).has(actor.get_instance_id()), "gibbed emitter does not retain timer state")
	actor.call("setup_fighter", 0, "johnny", Vector2(120.0, 200.0), false)
	actor.call("_sync_rig_view")
	_check(not bool((view.get("chibi_motion") as Dictionary).get("burning", true)), "fighter reuse clears burn context")
	fire.call("clear_all")
	fire.set("external_fighters", [])
	fire.call("spawn_melee_trace", Vector2(140.0, 180.0), 1, "SWORD", 1)
	_check((fire.get("melee_traces") as Array).size() == 1, "melee trace spawned")
	for _t: int in range(6):
		fire.call("step_hazards", 1.0)
	_check((fire.get("melee_traces") as Array).is_empty(), "melee trace expires and clears cleanly without sticking")
	# High-fall death regression: dead fighter falling from high altitude lands in normal dead state without gibbing into meat chunks
	actor.call("setup_fighter", 0, "johnny", Vector2(120.0, 60.0), false)
	actor.set("local_solid_rects", [Rect2(0.0, 200.0, 400.0, 24.0)] as Array[Rect2])
	actor.set("hp", 10.0)
	actor.set("on_ground", false)
	actor.set("falling", true)
	actor.call("apply_explosion_hit", -0.5, 4.0, 18.0)
	for _f_step: int in range(36):
		actor.call("step_fighter", 1.0, {})
		if bool(actor.get("on_ground")):
			break
	_check(bool(actor.get("is_dead")) and not bool(actor.get("is_gibbed")), "dead fighter falling from high altitude never gibs into meat chunks")
	_check(str(actor.get("current_state")) in ["DEATH_KNEEL", "DEAD", "LAY"], "dead fighter falling from high altitude lands in normal dead pose")
	# Ladder rear-view posture & stationary climb clock freeze regression
	actor.call("setup_fighter", 0, "johnny", Vector2(120.0, 120.0), false)
	actor.set("default_floor_y", 160.0)
	actor.set("local_solid_rects", [] as Array[Rect2])
	actor.set("local_ladder_rects", [Rect2(114.0, 60.0, 12.0, 100.0)] as Array[Rect2])
	actor.set("climbing", true)
	actor.set("on_ground", false)
	actor.call("step_fighter", 1.0, {"up": false})
	actor.call("_sync_rig_view")
	var climb_pose: Dictionary = view.call("get_chibi_pose_snapshot") as Dictionary
	_check(str(climb_pose.get("family", "")) == "climb", "ladder climbing uses climb pose family (back view)")
	_check(is_equal_approx(float((climb_pose["shoulder_front"] as Vector2).x), -float((climb_pose["shoulder_back"] as Vector2).x)), "ladder climb shoulders are symmetric for rear-view rendering")
	var stationary_clock: float = float(view.get("source_motion_frame"))
	actor.call("step_fighter", 1.0, {"up": false})
	actor.call("_sync_rig_view")
	_check(is_equal_approx(float(view.get("source_motion_frame")), stationary_clock), "stationary fighter on ladder holds climb frame without pedaling limbs in place")
	actor.call("step_fighter", 1.0, {"up": true})
	actor.call("_sync_rig_view")
	_check(float(view.get("source_motion_frame")) > stationary_clock, "climbing upward on ladder advances the climb animation clock")
	# 2-Stage burning progression: fire splash ignites Stage 1 (small fire) first, then escalates to Stage 2 (big fire) after a reasonable time without rolling
	fire.call("clear_all")
	actor.call("setup_fighter", 0, "johnny", Vector2(120.0, 200.0), false)
	actor.set("default_floor_y", 200.0)
	fire.set("external_fighters", [actor])
	fire.call("trigger_fire_burst", "MOLOTOV", Vector2(126.0, 196.0), 18)
	var b_stage1: float = float(actor.get("burn_state"))
	_check(b_stage1 >= 15.0 and b_stage1 < 100.0, "fire splash ignites Stage 1 small fire first (15 <= burn_state < 100)")
	for _b_tick: int in range(75):
		actor.call("step_fighter", 1.0, {})
	var b_stage2: float = float(actor.get("burn_state"))
	_check(b_stage2 >= 100.0, "Stage 1 small fire escalates into Stage 2 large fire after ~3s without rolling")
	actor.free()
	fire.free()
	print("[CHIBI R6 INTEGRATION] FIXTURE_ONLY=1 ", "PASS" if failures == 0 else "FAIL", " checks=", checks, " failures=", failures)
	quit(0 if failures == 0 else 1)
	return true

func _check(condition: bool, label: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error("[CHIBI R6 INTEGRATION] " + label)
