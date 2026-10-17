class_name FighterVisualProfile
extends RefCounted
## Presentation-only pose selection. It never participates in simulation or hashes.

const LOCOMOTION_GROUNDED: int = 0
const LOCOMOTION_AIRBORNE: int = 1
const LOCOMOTION_CLIMBING: int = 2
const LOCOMOTION_FALLING: int = 3
const LOCOMOTION_DOWNED: int = 4

static func pose_for_state(state: Dictionary) -> StringName:
	var action: StringName = StringName(state.get(&"action", &"idle"))
	if int(state.get(&"health", 1)) <= 0 or int(state.get(&"locomotion", LOCOMOTION_GROUNDED)) == LOCOMOTION_DOWNED or action in [&"defeated", &"pit_fall", &"respawn"]:
		return &"downed"
	if bool(state.get(&"roll_low_posture", false)) or action in [&"roll", &"roll_recover"]:
		return &"roll"
	if bool(state.get(&"dive_low_posture", false)) or bool(state.get(&"tackle_low_posture", false)) or action in [&"dive", &"dive_recover", &"tackle", &"tackle_recover"]:
		return &"dive"
	if int(state.get(&"locomotion", LOCOMOTION_GROUNDED)) == LOCOMOTION_CLIMBING or action == &"climb":
		return &"climb"
	if action == &"crouch":
		return &"crouch"
	if bool(state.get(&"aiming", false)):
		return &"aim"
	# attack retains the last action in snapshots after its timer expires. It is
	# history, not a persistent pose: otherwise one punch freezes the run cycle.
	if action in [&"hit", &"knockdown", &"grabbed", &"grab"] or (int(state.get(&"attack_timer_ticks", 0)) > 0 and StringName(state.get(&"attack", &"none")) != &"none"):
		return &"attack"
	var locomotion: int = int(state.get(&"locomotion", LOCOMOTION_GROUNDED))
	if locomotion == LOCOMOTION_AIRBORNE:
		return &"jump"
	if locomotion == LOCOMOTION_FALLING:
		return &"fall"
	if absf(float(state.get(&"vx", 0.0))) > 0.1:
		return &"run"
	return &"idle"

static func body_height_for_pose(height: float, pose: StringName) -> float:
	if pose == &"roll" or pose == &"dive":
		return minf(height, maxf(16.0, height * 0.48))
	if pose == &"downed":
		return minf(height, maxf(14.0, height * 0.35))
	return height
