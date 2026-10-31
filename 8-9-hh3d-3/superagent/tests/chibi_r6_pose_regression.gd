extends SceneTree
## Pure pose/style fixtures. No controller, match, input injection or screenshots.
## The coordinator runs this in the serial Godot verification sequence.

const Pose = preload("res://game/fighter/chibi_action_pose.gd")
const Painter = preload("res://game/fighter/chibi_brawler_rig_painter.gd")
const JOINTS: Array[String] = [
	"hip", "chest", "head", "shoulder_front", "shoulder_back",
	"elbow_front", "elbow_back", "hand_front", "hand_back",
	"hip_front", "hip_back", "knee_front", "knee_back", "ankle_front", "ankle_back",
]

var _checks: int = 0
var _failures: int = 0


func _initialize() -> void:
	_relaxed_idle_and_gaits()
	_air_phases_and_tumble()
	_burning_and_priority()
	_calibration_and_finiteness()
	_handwear_and_strike_timing()
	if _failures > 0:
		push_error("[CHIBI R6 POSE] FAIL: " + str(_failures) + "/" + str(_checks))
		quit(1)
	else:
		print("[CHIBI R6 POSE] PASS: " + str(_checks) + " checks")
		quit(0)


func _sample(state: String, source: float, motion: Dictionary = {}, carrying: bool = false) -> Dictionary:
	return Pose.sample(state, 1, 0.0, carrying, source, 0.0, "", motion)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R6 POSE] " + label)


func _distance(a: Dictionary, b: Dictionary, keys: Array[String]) -> float:
	var distance: float = 0.0
	for key: String in keys:
		distance += (a[key] as Vector2).distance_to(b[key] as Vector2)
	return distance


func _relaxed_idle_and_gaits() -> void:
	for source: float in [0.0, 7.5, 15.0, 30.0, 45.0, 60.0]:
		var idle: Dictionary = _sample("IDLE", source)
		for side: String in ["front", "back"]:
			_check((idle["hand_" + side] as Vector2).y > (idle["shoulder_" + side] as Vector2).y + 2.0, "idle " + side + " hand hangs below shoulder")
			_check((idle["hand_" + side] as Vector2).y > (idle["chest"] as Vector2).y, "idle " + side + " hand clears chest/face")
			_check(str(idle["hand_" + side + "_shape"]) == "relaxed", "idle has relaxed fingers")
		_check(absf((idle["hand_front"] as Vector2).y - (idle["hand_back"] as Vector2).y) > 0.2, "idle hand levels are asymmetric")
	for state: String in ["WALK", "RUN", "SPRINT"]:
		var length: float = float(Pose.STATE_LENGTHS[state])
		var first: Dictionary = _sample(state, length * 0.25)
		var second: Dictionary = _sample(state, length * 0.75)
		for side: String in ["front", "back"]:
			var hand_dx: float = (second["hand_" + side] as Vector2).x - (first["hand_" + side] as Vector2).x
			var foot_dx: float = (second["ankle_" + side] as Vector2).x - (first["ankle_" + side] as Vector2).x
			_check(hand_dx * foot_dx < 0.0, state + " " + side + " arm opposes its leg")
			_check(absf(hand_dx) > 1.0 and absf(foot_dx) > 1.0, state + " swings both limbs")
		for i: int in range(17):
			var pose: Dictionary = _sample(state, length * float(i) / 16.0)
			for side: String in ["front", "back"]:
				_check((pose["hand_" + side] as Vector2).y > (pose["shoulder_" + side] as Vector2).y, state + " hand pump stays below shoulder")
	var walk: Dictionary = _sample("WALK", 4.0)
	var run: Dictionary = _sample("RUN", 3.0)
	var sprint: Dictionary = _sample("SPRINT", 2.0)
	_check(_distance(walk, run, ["hand_front", "hand_back", "ankle_front", "ankle_back"]) > 2.0, "walk and run have distinct silhouette at the same gait phase")
	_check(_distance(run, sprint, ["chest", "hand_front", "hand_back", "ankle_front", "ankle_back"]) > 2.0, "sprint adds lean, reach and purposeful arm pump")
	var guard: Dictionary = _sample("AIM_FISTS", 0.0)
	_check((guard["hand_front"] as Vector2).y < (guard["shoulder_front"] as Vector2).y, "deliberate combat still raises a guard")
	_check(str(guard["hand_front_shape"]) == "fist", "guard closes the fist")


func _air_phases_and_tumble() -> void:
	var ascent: Dictionary = _sample("JUMP", 4.0, {"velocity": Vector2(2.0, -5.0), "grounded": false})
	var apex: Dictionary = _sample("JUMP", 4.0, {"velocity": Vector2(2.0, 0.0), "grounded": false})
	var descent: Dictionary = _sample("JUMP", 4.0, {"velocity": Vector2(2.0, 3.0), "grounded": false})
	var freefall: Dictionary = _sample("JUMP", 4.0, {"velocity": Vector2(2.0, 10.0), "grounded": false})
	var air_poses: Array[Dictionary] = [ascent, apex, descent, freefall]
	var phases: Array[String] = ["ascent", "apex", "descent", "freefall"]
	for index: int in range(air_poses.size()):
		_check(str(air_poses[index]["phase"]) == phases[index], "same JUMP state reads velocity phase " + phases[index])
		if index > 0:
			_check(_distance(air_poses[index - 1], air_poses[index], ["hand_front", "hand_back", "knee_front", "knee_back", "ankle_front", "ankle_back"]) > 2.0, "adjacent air phases change the articulated silhouette")
	_check((ascent["ankle_front"] as Vector2).y < (descent["ankle_front"] as Vector2).y - 1.0, "ascent drives a knee, descent extends a landing foot")
	_check((freefall["hand_front"] as Vector2).y < (descent["hand_front"] as Vector2).y, "dangerous freefall opens the arms above descent")
	var tumble: Dictionary = _sample("FALL_B", 4.0, {"velocity": Vector2(-3.0, 10.0), "grounded": false})
	_check(str(tumble["phase"]) == "hit_tumble_back", "impact tumble has an explicit phase")
	_check(_distance(tumble, freefall, ["hand_front", "hand_back", "knee_front", "knee_back"]) > 2.0 and absf(float(tumble["root_rotation_deg"])) > 1.0, "hit tumble has opened asymmetrical limbs and body rotation")
	var rotated: Dictionary = Pose.sample("FALL_B", 1, 0.0, false, 4.0, 90.0)
	var expected_origin: Vector2 = Pose.SOURCE_BODY_PIVOT + ((tumble["root_origin"] as Vector2) - Pose.SOURCE_BODY_PIVOT).rotated(PI * 0.5)
	_check((rotated["root_origin"] as Vector2).distance_to(expected_origin) < 0.001, "gameplay rotation still composes about the original source pivot")
	_check(_distance(_sample("JUMP", 0.0), _sample("FALL", 0.0), ["hand_front", "hand_back", "ankle_front", "ankle_back"]) > 2.0, "legacy calls without motion still distinguish jump from fall")


func _burning_and_priority() -> void:
	for state: String in ["IDLE", "WALK", "RUN", "SPRINT", "JUMP", "FALL", "CROUCH"]:
		var base: Dictionary = _sample(state, 1.75)
		var burning: Dictionary = _sample(state, 1.75, {"burning": true, "grounded": state not in ["JUMP", "FALL"]})
		_check(bool(burning["burning_overlay"]), state + " supports readable fire recoil")
		_check(_distance(base, burning, ["elbow_front", "elbow_back", "hand_front", "hand_back"]) > 2.0, state + " fire changes the pose, not only metadata")
		_check(str(burning["family"]) == str(base["family"]) and bool(burning["contact"]) == bool(base["contact"]), state + " fire preserves action family/contact")
		_check(str(burning["hand_front_shape"]) == "splayed", state + " fire opens the palm")
		_check(burning == _sample(state, 1.75, {"burning": true, "grounded": state not in ["JUMP", "FALL"]}), state + " frozen source frame repeats exactly")
	var flinch_a: Dictionary = _sample("IDLE", 1.75, {"burning": true})
	var flinch_b: Dictionary = _sample("IDLE", 5.25, {"burning": true})
	_check(_distance(flinch_a, flinch_b, ["hand_front", "hand_back"]) > 2.0, "panic alternates both arms on the source clock")
	# A conservative local head box includes the rendered skull plus palm
	# clearance. Panic hands must remain alongside it over the whole cycle.
	for index: int in range(29):
		var pose: Dictionary = _sample("IDLE", float(index) * 0.25, {"burning": true, "grounded": true})
		for side: String in ["front", "back"]:
			_check(absf((pose["hand_" + side] as Vector2).x - (pose["head"] as Vector2).x) > 4.5, "panic palm clears the head silhouette")
	for state: String in ["PUNCH_01", "PUNCH_02", "PUNCH_03", "AIM_PISTOL", "AIM_FISTS", "KICK", "SKILL_1", "THROW", "CLIMB", "ROLL", "HURT", "FALL_F", "FALL_B", "KNOCKDOWN", "DEAD", "WIN", "COVER", "UNKNOWN"]:
		_check(_sample(state, 3.5) == _sample(state, 3.5, {"burning": true}), state + " suppresses lower-priority panic")
	_check(_sample("RUN", 3.0, {}, true) == _sample("RUN", 3.0, {"burning": true}, true), "carry suppresses panic and retains its grip")


func _skull_top(pose: Dictionary) -> float:
	var skull: Rect2 = Pose.SKULL_LOCAL_RECT
	var top: float = INF
	var angle: float = deg_to_rad(float(pose["head_tilt_deg"]))
	for corner: Vector2 in [skull.position, Vector2(skull.end.x, skull.position.y), skull.end, Vector2(skull.position.x, skull.end.y)]:
		top = minf(top, ((pose["head"] as Vector2) + corner.rotated(angle)).y)
	return top


func _calibration_and_finiteness() -> void:
	_check(absf(_skull_top(_sample("IDLE", 0.0)) + 18.0) < 0.02, "neutral vulnerable skull-to-sole core remains 18 world units")
	for state: String in ["IDLE", "CROUCH", "COVER"]:
		for source: float in [0.0, 1.75, 5.25, 15.0, 22.5, 45.0]:
			for burning: bool in [false, true]:
				var pose: Dictionary = _sample(state, source, {"burning": burning, "grounded": true})
				_check(_skull_top(pose) >= (-18.0 if state == "IDLE" else -12.0) - 0.001, state + " maintains calibrated skull envelope")
	for state: String in ["IDLE", "WALK", "RUN", "SPRINT", "JUMP", "FALL", "FALL_F", "PUNCH_03", "CROUCH", "DEAD", "UNKNOWN"]:
		for bad_motion: Dictionary in [{"velocity": Vector2(NAN, INF), "burning": true}, {"velocity": "fast"}, {"velocity": Vector2(1e30, -1e30)}]:
			var pose: Dictionary = Pose.sample(state, 0, NAN, false, INF, INF, "", bad_motion)
			for key: String in JOINTS:
				var joint: Vector2 = pose[key]
				_check(is_finite(joint.x) and is_finite(joint.y), state + " malformed optional motion keeps " + key + " finite")
			_check(is_finite(float(pose["root_rotation_deg"])) and is_finite(float(pose["head_tilt_deg"])), state + " malformed motion keeps angles finite")
	var motion: Dictionary = {"velocity": Vector2(2.0, -5.0), "grounded": false, "burning": true}
	var original: Dictionary = motion.duplicate(true)
	_sample("JUMP", 2.0, motion)
	_check(motion == original, "sampling never mutates the caller's motion dictionary")


func _handwear_and_strike_timing() -> void:
	for identity: String in ["agent", "goku", "naruto", "luffy", "hideki", "blaire"]:
		_check(str(Painter.get_character_style(identity)["handwear"]) == "bare", identity + " exposes a natural palm")
	_check(str(Painter.get_character_style("saitama")["handwear"]) == "glove", "Saitama retains signature gloves")
	_check(str(Painter.get_character_style("atlas")["handwear"]) == "gauntlet", "Atlas retains armor handwear")
	_check(str(Painter.get_character_style("johnny")["handwear"]) == "fingerless", "Johnny keeps tactical handwear with visible fingers")
	_check(bool(Painter.get_character_style("goku")["wristband"]), "Goku keeps a wristband with bare fingers")
	var contacts: Array[Dictionary] = []
	for combo: int in range(1, 4):
		var hit: float = 3.0 + float(combo - 1) * 0.5
		var state: String = "PUNCH_0" + str(combo)
		var before: Dictionary = _sample(state, hit - 0.01)
		var contact: Dictionary = _sample(state, hit)
		var after: Dictionary = _sample(state, hit + 0.81)
		_check(not bool(before["contact"]) and bool(contact["contact"]) and not bool(after["contact"]), state + " preserves source contact at " + str(hit))
		_check(str(contact["hand_front_shape"]) == "fist" and str(contact["hand_back_shape"]) == "fist", state + " closes combat hands")
		contacts.append(contact)
	_check(_distance(contacts[0], contacts[1], ["hand_front", "hand_back"]) > 2.0 and _distance(contacts[1], contacts[2], ["hand_front", "hand_back"]) > 2.0, "three contacts retain distinct punch silhouettes")
