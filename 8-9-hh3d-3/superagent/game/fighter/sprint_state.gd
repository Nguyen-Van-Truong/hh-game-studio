class_name SprintState
extends RefCounted
## Seeded Classic movement resource; not a hero skill or measured Y8 timing.
## A second directional press must finish held. Releasing/reversing stops sprint.

var stamina: int = 0
var direction: int = 0
var pending_direction: int = 0
var pending_ticks: int = 0

func reset(tuning: Dictionary) -> void:
	stamina = int(tuning[&"max_stamina"])
	cancel_gesture()

func cancel_gesture() -> void:
	direction = 0
	pending_direction = 0
	pending_ticks = 0

func step(actions: Dictionary, can_start: bool, can_continue: bool, stationary: bool, tuning: Dictionary) -> void:
	var left: bool = bool(actions.get(&"left_held", false))
	var right: bool = bool(actions.get(&"right_held", false))
	var axis: int = int(right) - int(left)
	var window_open: bool = pending_ticks > 0 and pending_direction == axis
	# A release is meaningful even when another press ends the same tick held.
	var active_released: bool = (direction > 0 and bool(actions.get(&"right_released", false))) or (direction < 0 and bool(actions.get(&"left_released", false)))
	if active_released:
		cancel_gesture()
		window_open = false
	if pending_ticks > 0:
		pending_ticks -= 1
	if pending_ticks == 0:
		pending_direction = 0
	if not can_continue or axis == 0 or direction != axis or stamina < int(tuning[&"sprint_drain_per_tick"]):
		direction = 0
	# Neutral release preserves a pending first tap; opposed keys cancel it.
	if not can_continue or (left and right):
		pending_ticks = 0
		pending_direction = 0
		window_open = false
	if can_start and can_continue and axis != 0:
		var count_key: StringName = &"right_press_count" if axis > 0 else &"left_press_count"
		var press_count: int = int(actions.get(count_key, 0))
		for _press: int in range(press_count):
			if window_open and stamina >= int(tuning[&"sprint_drain_per_tick"]):
				direction = axis
				pending_ticks = 0
				pending_direction = 0
				break
			pending_direction = axis
			pending_ticks = int(tuning[&"sprint_tap_window_ticks"])
			window_open = true
	if direction != 0:
		stamina = maxi(0, stamina - int(tuning[&"sprint_drain_per_tick"]))
		# Retain this tick's funded sprint; exhaustion takes effect next tick.
	else:
		var regen_key: StringName = &"stamina_idle_regen_per_tick" if stationary and axis == 0 else &"stamina_moving_regen_per_tick"
		stamina = mini(int(tuning[&"max_stamina"]), stamina + int(tuning[regen_key]))

func snapshot() -> Dictionary:
	var result: Dictionary = {&"stamina": stamina, &"direction": direction,
		&"pending_direction": pending_direction, &"pending_ticks": pending_ticks}
	result.make_read_only()
	return result

func canonical_fragment() -> String:
	return "sprint=%d,%d,%d,%d" % [stamina, direction, pending_direction, pending_ticks]
