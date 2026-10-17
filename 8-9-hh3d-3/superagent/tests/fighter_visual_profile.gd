extends SceneTree

const PROFILE = preload("res://game/fighter/fighter_visual_profile.gd")
const SHEET = preload("res://game/fighter/fighter_pose_sheet.gd")
const FIGHTER_VIEW = preload("res://game/fighter/fighter_view.gd")
var assertions: int = 0

func _init() -> void:
	_expect(PROFILE.pose_for_state({&"action": &"idle", &"locomotion": 0, &"health": 100}) == &"idle", "standing state is idle")
	_expect(PROFILE.pose_for_state({&"action": &"crouch", &"locomotion": 0, &"health": 100}) == &"crouch", "crouch action selects crouch pose")
	_expect(PROFILE.pose_for_state({&"action": &"idle", &"locomotion": 0, &"vx": 2.0, &"health": 100}) == &"run", "moving state is run")
	_expect(PROFILE.pose_for_state({&"action": &"jump", &"locomotion": 1, &"health": 100}) == &"jump", "airborne state is jump")
	_expect(PROFILE.pose_for_state({&"action": &"dive", &"dive_low_posture": true, &"health": 100}) == &"dive", "dive state is dive")
	_expect(PROFILE.pose_for_state({&"action": &"idle", &"roll_low_posture": true, &"health": 100}) == &"roll", "low roll state is roll")
	_expect(PROFILE.pose_for_state({&"action": &"aim", &"aiming": true, &"health": 100}) == &"aim", "aiming state is aim")
	_expect(PROFILE.pose_for_state({&"action": &"defeated", &"locomotion": 4, &"health": 0}) == &"downed", "defeated state is downed")
	_expect(is_equal_approx(PROFILE.body_height_for_pose(55.2, &"idle"), 55.2), "standing height remains authored height")
	_expect(PROFILE.body_height_for_pose(55.2, &"roll") < 55.2 and PROFILE.body_height_for_pose(55.2, &"dive") < 55.2, "low poses shorten presentation")
	call_deferred("_test_authored_manifests")

func _test_authored_manifests() -> void:
	var courier: FighterView = FIGHTER_VIEW.new()
	var mechanic: FighterView = FIGHTER_VIEW.new()
	courier.configure(1, 36.0, 55.2, 600)
	mechanic.configure(2, 36.0, 55.2, 600)
	get_root().add_child(courier)
	get_root().add_child(mechanic)
	await process_frame
	_expect(courier._has_authored_pose(), "courier loads validated sidecar")
	_expect(mechanic._has_authored_pose(), "mechanic loads validated sidecar")
	_expect(is_equal_approx(float(courier._sheet[&"standing_height"]), 276.0), "courier standing height comes from sidecar")
	_expect(is_equal_approx(float(mechanic._sheet[&"standing_height"]), 309.0), "mechanic standing height comes from sidecar")
	var jump_kick: Dictionary = {&"action": &"jump_kick", &"attack": &"jump_kick", &"attack_timer_ticks": 6, &"locomotion": 1, &"health": 100}
	courier.apply_state(jump_kick, 100)
	_expect(courier._pose_frame_index() == 13, "jump kick selects authored jump-kick frame")
	var run_state: Dictionary = {&"action": &"idle", &"vx": 2.0, &"health": 100}
	courier.apply_state(run_state, 101)
	_expect(courier._pose_frame_index() == 4, "run starts at first frame")
	courier.apply_state(run_state, 109)
	_expect(courier._pose_frame_index() == 5, "run advances from simulation ticks")
	courier.apply_state(run_state, 109)
	_expect(courier._pose_frame_index() == 5, "paused redraw does not advance animation")
	courier.apply_state(run_state, 0)
	_expect(courier._pose_frame_index() == 4, "restart resets local animation phase")
	for kind: StringName in [&"shoot", &"throw", &"power", &"punch"]:
		courier.apply_state({&"action": &"idle", &"attack": kind, &"attack_timer_ticks": 6, &"health": 100}, 1)
		_expect(courier._clip == kind, "attack retains explicit clip: " + String(kind))
	courier.apply_state({&"action": &"idle", &"attack": &"punch", &"attack_timer_ticks": 0, &"vx": 3.0, &"health": 100}, 20)
	_expect(courier._clip == &"run", "expired attack history cannot freeze locomotion animation")
	courier.apply_state({&"aiming": true, &"health": 100}, 21)
	_expect(courier._pose_frame_index() == 16, "aim uses authored extended arms")
	var action_frame: Dictionary = courier._sheet[&"frames"][16]
	_expect(int(action_frame[&"atlas_index"]) == 1, "extension frames use the separate validated atlas")
	_expect(SHEET.frame_index(courier._sheet, &"throw", 100) == 2, "throw recovers without looping windup")
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/characters/courier/visual.json"))
	var atlas_sizes: Array[Vector2] = [Vector2(1280, 1280), Vector2(1774, 887)]
	_expect(not SHEET.validate_manifest(manifest, atlas_sizes[0], String(manifest["atlas"]), atlas_sizes).is_empty(), "valid multi-atlas manifest passes before negative cases")
	var broken: Dictionary = manifest.duplicate(true)
	broken["frames"][0]["region"][2] = 99999
	_expect(SHEET.validate_manifest(broken, Vector2(1280, 1280), String(manifest["atlas"]), atlas_sizes).is_empty(), "out-of-atlas region fails closed")
	broken = manifest.duplicate(true)
	var first_frame: Dictionary = broken["frames"][0]
	first_frame.erase("foot")
	broken["frames"][0] = first_frame
	_expect(SHEET.validate_manifest(broken, Vector2(1280, 1280), String(manifest["atlas"]), atlas_sizes).is_empty(), "missing foot anchor fails closed")
	broken = manifest.duplicate(true)
	var broken_clips: Dictionary = broken["clips"]
	broken_clips.erase("jump_kick")
	broken["clips"] = broken_clips
	_expect(SHEET.validate_manifest(broken, Vector2(1280, 1280), String(manifest["atlas"]), atlas_sizes).is_empty(), "missing action clip fails closed")
	courier.free()
	mechanic.free()
	print("SA-10 fighter visual profile PASS: %d assertions" % assertions)
	quit()

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)
