extends SceneTree
## FIXTURE_ONLY / NOT_E2E: real FighterController animation/sync exercised by
## authored source-frame calls. No keyboard, live combat or match acceptance.

const FighterScript: Script = preload("res://game/fighter/fighter_controller.gd")
const RegistryScript: Script = preload("res://game/core/sf_data_registry.gd")
const PoseScript: Script = preload("res://game/fighter/chibi_action_pose.gd")
const STEP: float = 0.4666667
const EPSILON: float = 0.001

var _ran: bool = false
var _checks: int = 0
var _failures: int = 0
var _registry: Node = null
var _fighter: Node2D = null
var _rig: Node2D = null


func _process(_delta: float) -> bool:
	if _ran:
		return true
	_ran = true
	print("[CHIBI R5 TEMPORAL] FIXTURE_ONLY=1 NOT_E2E=1 source_step=" + str(STEP))
	_run()
	if _fighter != null:
		_fighter.free()
	print("[CHIBI R5 TEMPORAL] " + ("PASS" if _failures == 0 else "FAIL") + " checks=" + str(_checks) + " failures=" + str(_failures))
	quit(0 if _failures == 0 else 1)
	return true


func _run() -> void:
	_registry = root.get_node_or_null("SFDataRegistry")
	if _registry == null:
		_registry = RegistryScript.new() as Node
		_registry.name = "SFDataRegistry"
		root.add_child(_registry)
	_registry.call("ensure_loaded")
	_fighter = FighterScript.new() as Node2D
	_fighter.name = "ChibiTemporalFixtureFighter"
	root.add_child(_fighter)
	_fighter.set_process(false)
	_fighter.set_physics_process(false)
	_fighter.call("setup_fighter", 0, "johnny", Vector2(160.0, 160.0), false)
	_rig = _fighter.get("rig_view") as Node2D
	_check(_rig != null, "actual FighterController creates its FighterRigView")
	if _rig == null:
		return
	_nonloop_clock("ROLL")
	_nonloop_clock("KNOCKDOWN")
	_loop_clock()
	_sync_clock_credit()
	_hitstop_freeze()
	_dead_flash_expires()
	_setup_reset()
	_skull_and_stance_envelopes()


func _duration(state: String) -> float:
	var data: Dictionary = _registry.call("get_state_data", state) as Dictionary
	var total: float = 0.0
	for value: Variant in data.get("keyframes", []):
		total += maxf(0.5, float((value as Dictionary).get("duration", 1.0)))
	return total


func _clock() -> float:
	return float(_rig.get("source_motion_frame"))


func _enter(state: String) -> void:
	_fighter.call("_set_state", state, true)
	_fighter.call("_sync_rig_view")


func _advance() -> void:
	_fighter.call("_advance_animation", STEP)
	_fighter.call("_sync_rig_view")


func _nonloop_clock(state: String) -> void:
	var duration: float = _duration(state)
	_check(duration > 0.0, state + " has an independently read compiled duration")
	_enter(state)
	_check(absf(_clock()) <= EPSILON, state + " force reset starts the source clock at zero")
	var previous: float = _clock()
	var monotonic: bool = true
	var bounded: bool = true
	var samples: int = int(ceil((duration + 12.0) / STEP))
	for i: int in range(samples):
		_advance()
		var current: float = _clock()
		monotonic = monotonic and is_finite(current) and current + EPSILON >= previous
		bounded = bounded and current >= -EPSILON and current <= duration + EPSILON
		previous = current
	_check(monotonic, state + " actual controller source time never jumps backward past its final keyframe")
	_check(bounded, state + " actual controller source time stays inside [0, compiled duration]")
	_check(absf(_clock() - duration) <= EPSILON, state + " final source time clamps at the authored duration")
	var frozen: float = _clock()
	for i: int in range(8):
		_advance()
	_check(absf(_clock() - frozen) <= EPSILON, state + " further advances preserve the terminal sample")
	_enter(state)
	_check(absf(_clock()) <= EPSILON, state + " restart clears the previous terminal clock")
	_advance()
	_check(absf(_clock() - STEP) <= EPSILON, state + " restart advances from zero")


func _loop_clock() -> void:
	# The current compiled controller calls walking locomotion RUN; WALK is a
	# presentation alias only. Exercise the actual looping state from registry.
	var data: Dictionary = _registry.call("get_state_data", "RUN") as Dictionary
	_check(bool(data.get("loop", false)), "walking locomotion RUN is a compiled loop")
	var duration: float = _duration("RUN")
	_enter("RUN")
	var previous: float = _clock()
	var wraps: int = 0
	var bounded: bool = true
	for i: int in range(int(ceil(duration * 2.5 / STEP))):
		_advance()
		var current: float = _clock()
		if current + EPSILON < previous:
			wraps += 1
		bounded = bounded and is_finite(current) and current >= -EPSILON and current < duration + EPSILON
		previous = current
	_check(wraps == 2, "walking locomotion wraps exactly twice over two and a half compiled cycles")
	_check(bounded, "loop time wraps within the authored cycle rather than using the terminal clamp")
	_enter("RUN")
	_check(absf(_clock()) <= EPSILON, "loop restart returns to frame zero")


func _expression_snapshot() -> Array:
	return [_rig.get("_breath_phase"), _rig.get("_blink_timer"), _rig.get("_is_blinking"), _rig.get("_expr_hold_timer"), _rig.get("_current_expr_id")]


func _sync_clock_credit() -> void:
	_enter("IDLE")
	var before: Array = _expression_snapshot()
	for i: int in range(12):
		_fighter.call("_sync_rig_view")
	_check(_expression_snapshot() == before, "repeated sync without a controller step never advances expression, breath or blink")
	_fighter.set("_presentation_step_seconds", 0.02)
	_fighter.call("_sync_rig_view")
	var after_step: Array = _expression_snapshot()
	_check(after_step != before, "one explicit fixture step credit advances the presentation clock")
	_check(absf(float(_fighter.get("_presentation_step_seconds"))) <= EPSILON, "sync consumes the controller presentation step credit")
	for i: int in range(12):
		_fighter.call("_sync_rig_view")
	_check(_expression_snapshot() == after_step, "consumed presentation credit cannot be spent by another sync")


func _hitstop_freeze() -> void:
	_enter("IDLE")
	_rig.set("_blink_timer", 0.44)
	_rig.set("_is_blinking", false)
	_rig.set("_expr_hold_timer", 0.31)
	_fighter.set("_hitstop_ticks", 2)
	_fighter.set("_hit_flash_timer", 0.29)
	var before: Array = [_rig.get("_blink_timer"), _rig.get("_is_blinking"), _rig.get("_expr_hold_timer"), _fighter.get("_hit_flash_timer")]
	_fighter.call("step_fighter", STEP, {})
	_check(_rig.get("_blink_timer") == before[0] and _rig.get("_is_blinking") == before[1] and _rig.get("_expr_hold_timer") == before[2], "hitstop freezes presentation expression clocks")
	_check(is_equal_approx(float(_fighter.get("_hit_flash_timer")), float(before[3])), "hitstop freezes hit flash timer")
	_check(int(_fighter.get("_hitstop_ticks")) == 1, "hitstop consumes exactly one freeze tick")
	_fighter.set("_hitstop_ticks", 0)


func _dead_flash_expires() -> void:
	_fighter.set("is_dead", true)
	_fighter.set("hp", 0.0)
	_fighter.set("_hit_flash_timer", 0.045)
	_fighter.set("_afterimage_trail", [{"timer": 0.12, "world_pos": Vector2(155.0, 160.0)}] as Array[Dictionary])
	_fighter.set("awakening_timer", 4.0)
	_fighter.set("overheat_timer", 2.0)
	_fighter.set("bullet_deflect_timer", 1.0)
	_fighter.call("step_fighter", STEP, {})
	_check((_fighter.get("_afterimage_trail") as Array).is_empty(), "a dead powered actor cannot retain permanent dash ghosts")
	_check(is_zero_approx(float(_fighter.get("awakening_timer"))) and is_zero_approx(float(_fighter.get("overheat_timer"))) and is_zero_approx(float(_fighter.get("bullet_deflect_timer"))), "death cancels transient powered aura and deflect visuals")
	_check(float(_fighter.get("_hit_flash_timer")) > 0.0 and float(_fighter.get("_hit_flash_timer")) < 0.045, "a lethal impact flash starts expiring during corpse simulation")
	for i: int in range(4):
		_fighter.call("step_fighter", STEP, {})
	_check(is_zero_approx(float(_fighter.get("_hit_flash_timer"))), "a non-burned corpse cannot retain a permanent impact-white flash")
	_check(str(_rig.get("_current_expr_id")) == "KO_STARS", "expired corpse flash retains the KO expression")


func _setup_reset() -> void:
	_rig.set("_breath_phase", 5.0)
	_rig.set("_blink_timer", 0.01)
	_rig.set("_is_blinking", true)
	_rig.set("_expr_hold_timer", 1.0)
	_rig.set("_current_expr_id", "DIZZY_SPIRAL_HURT")
	_rig.set("source_motion_frame", 123.0)
	_fighter.set("_presentation_step_seconds", 0.6)
	_fighter.call("setup_fighter", 0, "johnny", Vector2(160.0, 160.0), false)
	_check(absf(_clock()) <= EPSILON, "fighter setup clears a stale source visual clock")
	_check(absf(float(_rig.get("_breath_phase"))) <= EPSILON, "fighter setup clears stale breath phase")
	_check(absf(float(_rig.get("_blink_timer")) - 2.8) <= EPSILON and not bool(_rig.get("_is_blinking")), "fighter setup restores the initial blink state")
	_check(absf(float(_rig.get("_expr_hold_timer"))) <= EPSILON and str(_rig.get("_current_expr_id")) == "CHEEKY_SMIRK", "fighter setup clears the old held expression")
	_check(absf(float(_fighter.get("_presentation_step_seconds"))) <= EPSILON, "fighter setup clears unconsumed presentation credit")


func _skull_and_stance_envelopes() -> void:
	# Skull bounds are the atlas manifest's measured reference rectangle, not
	# transparent cell margins or extra hair. This is a pure geometry fixture.
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://assets/sprites/chibi_brawler/r5_heads/manifest.json"))
	_check(raw is Dictionary, "skull envelope reads the authored atlas manifest")
	if not raw is Dictionary:
		return
	var manifest: Dictionary = raw as Dictionary
	var rect_px: Array = manifest.get("skull_reference_rect_px", []) as Array
	var pivot_px: Array = manifest.get("pivot_px", []) as Array
	_check(rect_px.size() == 4 and pivot_px.size() == 2, "manifest exposes skull bounds and skull pivot")
	if rect_px.size() != 4 or pivot_px.size() != 2:
		return
	var units: float = float(manifest.get("units_per_pixel", 0.0))
	var rect: Rect2 = Rect2((Vector2(float(rect_px[0]), float(rect_px[1])) - Vector2(float(pivot_px[0]), float(pivot_px[1]))) * units, Vector2(float(rect_px[2]), float(rect_px[3])) * units)
	for state: String in ["IDLE", "CROUCH", "COVER"]:
		var pose: Dictionary = PoseScript.sample(state, 1, 0.0, false, 0.0, 0.0)
		var top: float = _skull_top(pose, rect)
		_check(top >= (-18.0 if state == "IDLE" else -12.0) - EPSILON, state + " tilted skull corners stay inside the standing/crouched envelope")
		if state == "IDLE":
			_check(absf(top + 18.0) <= 0.02, "IDLE neutral skull-to-sole calibration is 18 world units")
	var aimed_cover: Dictionary = PoseScript.sample("AIM_PISTOL", 1, 0.0, false, 0.0, 0.0, "COVER")
	_check(bool(aimed_cover.get("split_arms", false)), "aiming in cover retains the split weapon arms")
	_check(_skull_top(aimed_cover, rect) >= -12.0 - EPSILON, "aiming in cover retains the crouched skull envelope")
	for pitch: float in [-90.0, -45.0, 45.0, 90.0]:
		var angled_cover: Dictionary = PoseScript.sample("AIM_PISTOL", 1, pitch, false, 0.0, 0.0, "COVER")
		_check(_skull_top(angled_cover, rect) >= -12.0 - EPSILON, "aiming cover skull corners stay bounded at pitch " + str(pitch))


func _skull_top(pose: Dictionary, skull: Rect2) -> float:
	var angle: float = deg_to_rad(float(pose.get("head_tilt_deg", 0.0)) + float(pose.get("root_rotation_deg", 0.0)))
	var center: Vector2 = (pose.get("root_origin", Vector2.ZERO) as Vector2) + (pose.get("head", Vector2.ZERO) as Vector2).rotated(deg_to_rad(float(pose.get("root_rotation_deg", 0.0))))
	var top: float = INF
	for corner: Vector2 in [skull.position, Vector2(skull.end.x, skull.position.y), skull.end, Vector2(skull.position.x, skull.end.y)]:
		top = minf(top, (center + corner.rotated(angle)).y)
	return top


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R5 TEMPORAL] " + label)
