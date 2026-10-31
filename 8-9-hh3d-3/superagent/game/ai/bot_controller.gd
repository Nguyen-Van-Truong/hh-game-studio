class_name BotController
extends RefCounted
## Tactical AI Bot Brain & A* Pathfinding Controller ported from BotState.as & Player.as (SF-M5).
## Supports 3 difficulty levels (1: Easy, 2: Medium, 3: Hard), graph pathfinding over
## map_loader.ai_nodes & ai_binds (ROAD, JUMP, SPRINTJUMP, DIVE, LADDER, PORTAL, CLOUDDOWN),
## emergency Roll to extinguish fire (burn_state >= 15), weapon scavenging, cover usage,
## explosive barrel sniping near enemies, ranged aiming, throwables, and melee/dive-grab combos.

const DIFF_EASY: int = 1
const DIFF_MEDIUM: int = 2
const DIFF_HARD: int = 3

const PHASE_IDLE: int = 0
const PHASE_AIM: int = 1
const PHASE_SHOOT: int = 2
const PHASE_FOLLOW_PATH: int = 4
const PHASE_GRAB_WEAPON: int = 5
const PHASE_MELEE: int = 6

var difficulty: int = DIFF_MEDIUM
var update_delay: int = 6
var aim_delay: int = 9
var can_sprint: bool = true
var can_roll_dive: bool = true
var can_use_cover: bool = true
var can_shoot_barrels: bool = false

var current_phase: int = PHASE_IDLE
var current_path: Array[Dictionary] = []
var current_path_index: int = 0
var target_fighter: Node2D = null
var target_hazard_prop: Node2D = null

var _aim_timer: float = 0.0
var _path_recalc_timer: float = 0.0
var _melee_combo_toggle: bool = false
var _jump_pulse_toggle: bool = false
var _last_bot_pos: Vector2 = Vector2.ZERO
var _last_decision_summary: String = "IDLE"
var _ladder_exit_hold: bool = false
var _ladder_exit_goal: Vector2 = Vector2.ZERO


func _init(p_difficulty: int = DIFF_MEDIUM) -> void:
	set_difficulty(p_difficulty)


func set_difficulty(p_difficulty: int) -> void:
	difficulty = clampi(p_difficulty, DIFF_EASY, DIFF_HARD)
	match difficulty:
		DIFF_EASY:
			update_delay = 8
			aim_delay = 12
			can_sprint = false
			can_roll_dive = false
			can_use_cover = false
			can_shoot_barrels = false
		DIFF_MEDIUM:
			update_delay = 6
			aim_delay = 9
			can_sprint = true
			can_roll_dive = true
			can_use_cover = true
			can_shoot_barrels = false
		DIFF_HARD:
			update_delay = 1
			aim_delay = 5
			can_sprint = true
			can_roll_dive = true
			can_use_cover = true
			can_shoot_barrels = true


func compute_bot_input(fighter: Node2D, match_world: Node2D, step_24hz: float = 0.4) -> Dictionary:
	var input: Dictionary = _make_empty_input()
	if fighter == null or not is_instance_valid(fighter):
		return input
	if bool(fighter.get("is_dead")):
		return input

	var f_diff: Variant = fighter.get("bot_difficulty")
	if typeof(f_diff) == TYPE_INT and int(f_diff) != difficulty:
		set_difficulty(int(f_diff))

	var my_pos: Vector2 = fighter.global_position
	var burn_state: float = float(fighter.get("burn_state")) if fighter.get("burn_state") != null else 0.0
	var burned: bool = bool(fighter.get("burned"))

	# 1. HIGHEST PRIORITY: Extinguish fire immediately by Rolling when burn_state >= 15!
	if burn_state >= 15.0 or burned:
		current_phase = PHASE_IDLE
		_last_decision_summary = "ROLL_EXTINGUISH"
		var roll_dir: int = int(fighter.get("facing")) if fighter.get("facing") != null else 1
		if match_world != null and is_instance_valid(match_world):
			var ml: Node2D = match_world.get("map_loader") as Node2D
			if ml != null and is_instance_valid(ml) and ml.has_method("is_point_solid"):
				var probe: Vector2 = my_pos + Vector2(float(roll_dir) * 14.0, -4.0)
				if bool(ml.call("is_point_solid", probe, false)):
					roll_dir = -roll_dir
		if roll_dir < 0:
			input["left"] = true
		else:
			input["right"] = true
		input["down"] = true
		input["sprint"] = false # Roll requires Down + Left/Right without Sprint
		return input

	if match_world == null or not is_instance_valid(match_world):
		return input

	var map_loader: Node2D = match_world.get("map_loader") as Node2D

	# 2. Check if unarmed and a weapon pickup is available nearby
	var is_unarmed: bool = _is_fighter_unarmed(fighter)
	var nearest_pickup: Dictionary = _find_best_weapon_pickup(fighter, match_world)
	if is_unarmed and not nearest_pickup.is_empty():
		var ppos: Vector2 = nearest_pickup.get("pos", my_pos) as Vector2
		var dist_to_wpn: float = my_pos.distance_to(ppos)
		if dist_to_wpn <= 18.0:
			current_phase = PHASE_GRAB_WEAPON
			_last_decision_summary = "PICKUP_WEAPON"
			input["down"] = true
			if match_world.has_method("try_pickup_near"):
				match_world.call("try_pickup_near", fighter)
			return input
		elif dist_to_wpn <= 260.0:
			current_phase = PHASE_GRAB_WEAPON
			_last_decision_summary = "PATH_TO_WEAPON"
			return _follow_path_towards(fighter, ppos, map_loader, step_24hz)

	# 3. Acquire best enemy target
	target_fighter = _find_best_enemy(fighter, match_world)
	if target_fighter == null or not is_instance_valid(target_fighter):
		current_phase = PHASE_IDLE
		_last_decision_summary = "NO_TARGET"
		return input

	var enemy_pos: Vector2 = target_fighter.global_position
	var dx: float = enemy_pos.x - my_pos.x
	var dy: float = enemy_pos.y - my_pos.y
	var abs_dx: float = absf(dx)
	var abs_dy: float = absf(dy)

	# 3b. Powered Fighter AI Skill Casting (EC-27): bots playing any of the 8 Powered Fighters actively cast skills 1..4!
	if bool(fighter.get("is_powered_fighter")) and not bool(fighter.get("is_summoned_clone")):
		var sk_input: Dictionary = _evaluate_powered_bot_skills(fighter, target_fighter, abs_dx, abs_dy, dx)
		if not sk_input.is_empty():
			_last_decision_summary = "POWERED_SKILL"
			return sk_input

	# 4. Check if we have a loaded gun or throwable
	var has_gun: bool = _fighter_has_loaded_gun(fighter)
	var has_throwable: bool = _fighter_has_throwable(fighter)

	# 5. Check if an explosive barrel / gascan is right next to the enemy and in line of sight
	target_hazard_prop = null
	if has_gun and (can_shoot_barrels or difficulty >= DIFF_MEDIUM):
		target_hazard_prop = _find_explosive_prop_near(enemy_pos, match_world, 75.0)

	var aim_world_target: Vector2 = enemy_pos + Vector2(0.0, -8.0)
	if target_hazard_prop != null and is_instance_valid(target_hazard_prop):
		aim_world_target = target_hazard_prop.global_position

	var has_los: bool = _has_line_of_sight(my_pos + Vector2(0.0, -10.0), aim_world_target, map_loader, int(fighter.get("cover_object_id")) if fighter.get("cover_object_id") != null else -1)

	# 6. Ranged Gun Engagement (AS3 Weapons.as ShootRange: 140 for FLAMETHROWER, 400 for BAZOOKA, 900 for firearms)
	var active_wid: String = str(fighter.call("get_active_weapon_id")).to_upper() if fighter.has_method("get_active_weapon_id") else ""
	var max_shoot_dx: float = 900.0
	if active_wid == "FLAMETHROWER":
		max_shoot_dx = 140.0
	elif active_wid == "BAZOOKA":
		max_shoot_dx = 400.0
	if has_gun and abs_dx >= 26.0 and abs_dx <= max_shoot_dx and abs_dy <= 160.0 and has_los:
		current_phase = PHASE_AIM
		_last_decision_summary = "SHOOT_BARREL" if target_hazard_prop != null else "RANGED_AIM_SHOOT"
		return _execute_ranged_aim_and_shoot(fighter, aim_world_target, map_loader, step_24hz)

	# 7. Throwable Engagement (Grenade / Molotov) at medium distance
	if has_throwable and difficulty >= DIFF_MEDIUM and abs_dx >= 75.0 and abs_dx <= 210.0 and abs_dy <= 80.0 and has_los:
		_last_decision_summary = "THROW_EXPLOSIVE"
		input["slot_4"] = true
		if dx < 0.0:
			input["left"] = true
		else:
			input["right"] = true
		var hold_throw: bool = int(_aim_timer) % 4 < 2
		input["attack"] = hold_throw
		input["throw"] = hold_throw
		_aim_timer += step_24hz
		return input

	# 8. Close-quarters Melee / Dive-Grab Engagement
	if abs_dx <= 24.0 and abs_dy <= 20.0:
		current_phase = PHASE_MELEE
		_last_decision_summary = "MELEE_COMBO"
		input["slot_1"] = true
		if dx < -3.0:
			input["left"] = true
		elif dx > 3.0:
			input["right"] = true
		_melee_combo_toggle = not _melee_combo_toggle
		input["attack"] = _melee_combo_toggle
		if can_roll_dive and abs_dx >= 14.0 and randf() < 0.2:
			input["sprint"] = true
			input["down"] = true
		return input

	# 9. Navigate towards enemy using A* over map_loader.ai_nodes & ai_binds
	current_phase = PHASE_FOLLOW_PATH
	_last_decision_summary = "FOLLOW_PATH"
	return _follow_path_towards(fighter, enemy_pos, map_loader, step_24hz)


func _execute_ranged_aim_and_shoot(
	fighter: Node2D,
	aim_target: Vector2,
	map_loader: Node2D,
	step_24hz: float
) -> Dictionary:
	var input: Dictionary = _make_empty_input()
	var my_pos: Vector2 = fighter.global_position
	var shoulder_pos: Vector2 = my_pos + Vector2(0.0, -12.0)
	var dx: float = aim_target.x - shoulder_pos.x
	var dy: float = aim_target.y - shoulder_pos.y
	var desired_dir: int = 1 if dx >= 0.0 else -1
	var cur_facing: int = int(fighter.get("facing")) if fighter.get("facing") != null else 1

	# Face the target first
	if cur_facing != desired_dir:
		if desired_dir < 0:
			input["left"] = true
		else:
			input["right"] = true
		return input

	# Select best available gun slot (prefer Primary slot 3 over Sidearm slot 2)
	var inv_ammo: Dictionary = fighter.get("inventory_ammo") as Dictionary if typeof(fighter.get("inventory_ammo")) == TYPE_DICTIONARY else {}
	if int(inv_ammo.get(3, 0)) > 0:
		input["slot_3"] = true
	elif int(inv_ammo.get(2, 0)) > 0:
		input["slot_2"] = true

	# Compute desired aim pitch in degrees [-80, +80]
	var desired_pitch: float = clampf(rad_to_deg(atan2(dy, maxf(4.0, absf(dx)))), -80.0, 80.0)
	var cur_pitch: float = float(fighter.get("current_aim_pitch")) if fighter.get("current_aim_pitch") != null else 0.0
	var pitch_err: float = desired_pitch - cur_pitch

	# If near cover prop and difficulty allows, crouch into cover when not adjusting pitch downward
	if can_use_cover and map_loader != null and is_instance_valid(map_loader) and map_loader.has_method("find_cover_prop_near"):
		var cov_id: int = int(map_loader.call("find_cover_prop_near", my_pos, desired_dir))
		if cov_id != -1 and absf(pitch_err) <= 6.0:
			input["down"] = true

	_aim_timer += step_24hz
	if absf(pitch_err) > 4.0:
		input["aim"] = true
		input["attack"] = true
		if pitch_err < 0.0:
			input["up"] = true
		else:
			input["down"] = true
	else:
		# Hold aim until aim_delay elapsed, then release/pulse attack to trigger shot
		if _aim_timer < float(aim_delay):
			input["aim"] = true
			input["attack"] = true
		else:
			current_phase = PHASE_SHOOT
			var fire_pulse: bool = (int(_aim_timer) % 2 == 0)
			input["aim"] = true
			input["attack"] = fire_pulse
			if _aim_timer >= float(aim_delay + 4):
				_aim_timer = 0.0

	return input


func find_path(from_pos: Vector2, to_pos: Vector2, map_loader: Node2D) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if map_loader == null or not is_instance_valid(map_loader):
		return result

	var nodes: Array = map_loader.get("ai_nodes") as Array if typeof(map_loader.get("ai_nodes")) == TYPE_ARRAY else []
	var binds: Array = map_loader.get("ai_binds") as Array if typeof(map_loader.get("ai_binds")) == TYPE_ARRAY else []
	if nodes.is_empty():
		return result

	var min_valid_x: float = 18.0
	if map_loader.get("map_bounds") is Rect2:
		var mb: Rect2 = map_loader.get("map_bounds") as Rect2
		if mb.size.x > 0.0:
			min_valid_x = mb.position.x + 18.0

	var start_idx: int = _find_closest_node_index(from_pos, nodes, min_valid_x)
	var goal_idx: int = _find_closest_node_index(to_pos, nodes, min_valid_x)
	if start_idx < 0 or goal_idx < 0 or start_idx == goal_idx:
		return result

	# Build adjacency list from ai_binds
	var adj: Dictionary = {}
	for b_var: Variant in binds:
		if typeof(b_var) != TYPE_DICTIONARY:
			continue
		var b: Dictionary = b_var as Dictionary
		var u: int = int(b.get("from", -1))
		var v: int = int(b.get("to", -1))
		if u < 0 or v < 0 or u >= nodes.size() or v >= nodes.size():
			continue
		if not adj.has(u):
			adj[u] = []
		(adj[u] as Array).append(b)

	# A* search over ai_nodes
	var open_list: Array[int] = [start_idx]
	var came_from_bind: Dictionary = {}
	var came_from_node: Dictionary = {}
	var g_score: Dictionary = {start_idx: 0.0}
	var f_score: Dictionary = {start_idx: _node_pos(nodes, start_idx).distance_to(_node_pos(nodes, goal_idx))}
	var closed: Dictionary = {}

	while not open_list.is_empty():
		var best_i: int = 0
		var current: int = open_list[0]
		var best_f: float = float(f_score.get(current, INF))
		for i: int in range(1, open_list.size()):
			var cand: int = open_list[i]
			var cf: float = float(f_score.get(cand, INF))
			if cf < best_f:
				best_f = cf
				current = cand
				best_i = i

		if current == goal_idx:
			return _reconstruct_path(nodes, came_from_node, came_from_bind, start_idx, goal_idx)

		open_list.remove_at(best_i)
		closed[current] = true

		var edges: Array = adj.get(current, []) as Array
		var cur_pos: Vector2 = _node_pos(nodes, current)
		for edge_var: Variant in edges:
			var edge: Dictionary = edge_var as Dictionary
			var neighbor: int = int(edge.get("to", -1))
			if closed.has(neighbor):
				continue
			var npos: Vector2 = _node_pos(nodes, neighbor)
			var action: String = str(edge.get("action", "ROAD"))
			var step_cost: float = cur_pos.distance_to(npos)
			if action == "PORTAL":
				step_cost = 18.0
			elif action in ["JUMP", "SPRINTJUMP", "DIVE"]:
				step_cost *= 1.15
			var tentative_g: float = float(g_score.get(current, INF)) + step_cost
			if tentative_g < float(g_score.get(neighbor, INF)):
				came_from_node[neighbor] = current
				came_from_bind[neighbor] = edge
				g_score[neighbor] = tentative_g
				f_score[neighbor] = tentative_g + npos.distance_to(_node_pos(nodes, goal_idx))
				if not (neighbor in open_list):
					open_list.append(neighbor)

	return result


func _reconstruct_path(
	nodes: Array,
	came_from_node: Dictionary,
	came_from_bind: Dictionary,
	start_idx: int,
	goal_idx: int
) -> Array[Dictionary]:
	var steps: Array[Dictionary] = []
	var cur: int = goal_idx
	var guard: int = 0
	while cur != start_idx and came_from_node.has(cur) and guard < 128:
		var prev: int = int(came_from_node[cur])
		var bind: Dictionary = came_from_bind[cur] as Dictionary
		var tpos: Vector2 = _node_pos(nodes, cur)
		steps.push_front({
			"from": prev,
			"to": cur,
			"from_pos": _node_pos(nodes, prev),
			"target_pos": tpos,
			"action": str(bind.get("action", "ROAD")),
			"mode": str(bind.get("mode", "STATIC")),
		})
		cur = prev
		guard += 1
	return steps


func _find_closest_node_index(pos: Vector2, nodes: Array, min_valid_x: float = 18.0) -> int:
	var best_idx: int = -1
	var best_score: float = INF
	for i: int in range(nodes.size()):
		var npos: Vector2 = _node_pos(nodes, i)
		# Skip virtual out-of-map portal dummy nodes (e.g. x < 15 or x > 590 on hazardous) as start/goal anchors
		if npos.x < min_valid_x:
			continue
		var dx: float = absf(npos.x - pos.x)
		var dy: float = absf(npos.y - pos.y)
		# Weight vertical difference higher so the bot picks nodes on its own floor
		var score: float = dx + dy * 2.8
		if score < best_score:
			best_score = score
			best_idx = i
	return best_idx


func _node_pos(nodes: Array, idx: int) -> Vector2:
	if idx < 0 or idx >= nodes.size():
		return Vector2.ZERO
	var nd: Dictionary = nodes[idx] as Dictionary
	return Vector2(float(nd.get("x", 0.0)), float(nd.get("y", 0.0)))


func _follow_path_towards(
	fighter: Node2D,
	goal_pos: Vector2,
	map_loader: Node2D,
	step_24hz: float
) -> Dictionary:
	var input: Dictionary = _make_empty_input()
	var my_pos: Vector2 = fighter.global_position
	var on_ground: bool = bool(fighter.get("on_ground"))
	if _ladder_exit_hold:
		if bool(fighter.get("climbing")) or not on_ground or goal_pos.distance_to(_ladder_exit_goal) > 8.0 or absf(my_pos.y - _ladder_exit_goal.y) > 14.0 or absf(my_pos.x - _ladder_exit_goal.x) > 20.0:
			_ladder_exit_hold = false
		else:
			return input

	# Immediately invalidate path if teleported through a portal (position jumped > 32px)
	if _last_bot_pos != Vector2.ZERO and my_pos.distance_to(_last_bot_pos) > 32.0:
		current_path.clear()
		_path_recalc_timer = 0.0
	_last_bot_pos = my_pos

	_path_recalc_timer -= step_24hz
	# Do not replace an active ladder route while the fighter is climbing. A
	# partial recalc can map the fighter's in-shaft position to no graph node,
	# dropping the final LADDER edge and stopping the Up input before dismount.
	var preserve_climb_route: bool = bool(fighter.get("climbing")) and not current_path.is_empty() and current_path_index < current_path.size()
	if not preserve_climb_route and current_path_index < current_path.size() and current_path_index >= current_path.size() - 1:
		var exit_step: Dictionary = current_path[current_path_index]
		var exit_action: String = str(exit_step.get("action", "ROAD")).to_upper()
		var exit_target: Vector2 = exit_step.get("target_pos", goal_pos) as Vector2
		preserve_climb_route = exit_action == "LADDER" and not bool(fighter.get("climbing")) and absf(my_pos.x - exit_target.x) <= 16.0 and absf(my_pos.y - exit_target.y) <= 14.0
	if (not preserve_climb_route and _path_recalc_timer <= 0.0) or current_path_index >= current_path.size():
		current_path = find_path(my_pos, goal_pos, map_loader)
		current_path_index = 0
		_path_recalc_timer = float(max(8, update_delay * 3))

	var step_from: Vector2 = my_pos
	var step_target: Vector2 = goal_pos
	var action: String = "ROAD"
	var advanced_this_tick: bool = false

	if not current_path.is_empty() and current_path_index < current_path.size():
		var step_data: Dictionary = current_path[current_path_index]
		step_from = step_data.get("from_pos", my_pos) as Vector2
		step_target = step_data.get("target_pos", goal_pos) as Vector2
		action = str(step_data.get("action", "ROAD")).to_upper()
		# Keep the final LADDER edge active until the controller actually
		# dismounts. Advancing while still climbing leaves an empty path on the
		# next tick, which freezes the bot just below an open ladder mouth.
		var holding_final_ladder: bool = action == "LADDER" and current_path_index >= current_path.size() - 1 and bool(fighter.get("climbing"))
		var grounded_ladder_exit: bool = action == "LADDER" and on_ground and not bool(fighter.get("climbing"))
		if not holding_final_ladder and not grounded_ladder_exit and absf(my_pos.x - step_target.x) <= 8.0 and absf(my_pos.y - step_target.y) <= 14.0:
			current_path_index += 1
			advanced_this_tick = true
			if current_path_index < current_path.size():
				step_data = current_path[current_path_index]
				step_from = step_data.get("from_pos", my_pos) as Vector2
				step_target = step_data.get("target_pos", goal_pos) as Vector2
				action = str(step_data.get("action", "ROAD")).to_upper()
	# An open ladder mouth has no center floor at its target Y. The controller
	# intentionally dismounts onto a neighbouring slab (or starts falling), so
	# do not steer back toward the missing center tile after the ladder action
	# has reached its authored height.
	if not advanced_this_tick and action == "LADDER" and not bool(fighter.get("climbing")) and on_ground and absf(my_pos.y - step_target.y) <= 14.0 and absf(my_pos.x - step_target.x) <= 16.0:
		current_path_index += 1
		if current_path_index < current_path.size():
			var next_step: Dictionary = current_path[current_path_index]
			step_from = next_step.get("from_pos", my_pos) as Vector2
			step_target = next_step.get("target_pos", goal_pos) as Vector2
			action = str(next_step.get("action", "ROAD")).to_upper()
		else:
			# The final ladder edge ended on a supported neighbouring slab. Treat
			# that side dismount as route completion instead of steering back into
			# the intentionally empty mouth center.
			_ladder_exit_hold = true
			_ladder_exit_goal = goal_pos
			current_path.clear()
			current_path_index = 0
			return input
	# A ladder that ends at an open mouth can dismount into air instead of a
	# support slab. Keep the controller neutral during that short exit so a
	# positive dy does not press Down and immediately re-grab the ladder.
	if action == "LADDER" and not on_ground and not bool(fighter.get("climbing")) and step_target.y < step_from.y and current_path_index >= current_path.size() - 1 and absf(my_pos.x - step_target.x) <= 16.0 and my_pos.y <= step_target.y + 6.0:
		_ladder_exit_hold = true
		_ladder_exit_goal = goal_pos
		current_path.clear()
		current_path_index = 0
		return input

	var dx: float = step_target.x - my_pos.x
	var dy: float = step_target.y - my_pos.y
	_jump_pulse_toggle = not _jump_pulse_toggle

	match action:
		"LADDER":
			var is_climbing_now: bool = bool(fighter.get("climbing"))
			var need_align_x: bool = (not is_climbing_now and absf(dx) > 4.0) or (is_climbing_now and absf(dy) <= 10.0 and absf(dx) > 3.0)
			if need_align_x:
				if dx < 0.0:
					input["left"] = true
				else:
					input["right"] = true
			if not need_align_x or is_climbing_now:
				var hold_final_ladder_up: bool = is_climbing_now and current_path_index >= current_path.size() - 1 and step_target.y < step_from.y
				if dy < -2.0 or hold_final_ladder_up:
					input["up"] = true
				elif dy > 2.0:
					input["down"] = true
		"JUMP":
			if dx < -2.0:
				input["left"] = true
			elif dx > 2.0:
				input["right"] = true
			var j_dir_x: float = signf(step_target.x - step_from.x)
			var at_takeoff: bool = ((step_from.x - my_pos.x) * j_dir_x <= 5.0) if absf(j_dir_x) > 0.1 else (absf(my_pos.x - step_from.x) <= 8.0)
			input["jump"] = on_ground and at_takeoff and _jump_pulse_toggle
		"SPRINTJUMP":
			if dx < -2.0:
				input["left"] = true
			elif dx > 2.0:
				input["right"] = true
			input["sprint"] = true
			var sj_dir_x: float = signf(step_target.x - step_from.x)
			var at_sj_takeoff: bool = ((step_from.x - my_pos.x) * sj_dir_x <= 6.0) if absf(sj_dir_x) > 0.1 else (absf(my_pos.x - step_from.x) <= 8.0)
			input["jump"] = on_ground and at_sj_takeoff and _jump_pulse_toggle
		"DIVE":
			if dx < -2.0:
				input["left"] = true
			elif dx > 2.0:
				input["right"] = true
			if can_roll_dive:
				input["sprint"] = true
				input["down"] = absf(dx) <= 36.0
				input["jump"] = absf(dx) > 36.0
			else:
				input["jump"] = true
		"CLOUDDOWN":
			input["down"] = true
			input["jump"] = true
		"PORTAL", "ROAD", _:
			if dx < -3.0:
				input["left"] = true
			elif dx > 3.0:
				input["right"] = true
			if can_sprint and absf(dx) > 55.0:
				input["sprint"] = true
			if dy < -18.0 and absf(dx) < 28.0:
				input["jump"] = true

	return input


func _is_fighter_unarmed(fighter: Node2D) -> bool:
	var inv_var: Variant = fighter.get("inventory")
	var ammo_var: Variant = fighter.get("inventory_ammo")
	if typeof(inv_var) == TYPE_DICTIONARY and typeof(ammo_var) == TYPE_DICTIONARY:
		var inv: Dictionary = inv_var as Dictionary
		var ammo: Dictionary = ammo_var as Dictionary
		var w2: String = str(inv.get(2, ""))
		var w3: String = str(inv.get(3, ""))
		var w1: String = str(inv.get(1, "FISTS"))
		if (not w2.is_empty() and int(ammo.get(2, 0)) > 0) or (not w3.is_empty() and int(ammo.get(3, 0)) > 0):
			return false
		if w1 != "" and w1 != "FISTS":
			return false
	return true


func _fighter_has_loaded_gun(fighter: Node2D) -> bool:
	var inv_var: Variant = fighter.get("inventory")
	var ammo_var: Variant = fighter.get("inventory_ammo")
	if typeof(inv_var) == TYPE_DICTIONARY and typeof(ammo_var) == TYPE_DICTIONARY:
		var inv: Dictionary = inv_var as Dictionary
		var ammo: Dictionary = ammo_var as Dictionary
		if not str(inv.get(2, "")).is_empty() and int(ammo.get(2, 0)) > 0:
			return true
		if not str(inv.get(3, "")).is_empty() and int(ammo.get(3, 0)) > 0:
			return true
	return false


func _fighter_has_throwable(fighter: Node2D) -> bool:
	var inv_var: Variant = fighter.get("inventory")
	var ammo_var: Variant = fighter.get("inventory_ammo")
	if typeof(inv_var) == TYPE_DICTIONARY and typeof(ammo_var) == TYPE_DICTIONARY:
		var inv: Dictionary = inv_var as Dictionary
		var ammo: Dictionary = ammo_var as Dictionary
		if not str(inv.get(4, "")).is_empty() and int(ammo.get(4, 0)) > 0:
			return true
	return false


func _find_best_weapon_pickup(fighter: Node2D, match_world: Node2D) -> Dictionary:
	var pickups_var: Variant = match_world.get("pickups")
	if typeof(pickups_var) != TYPE_ARRAY:
		return {}
	var my_pos: Vector2 = fighter.global_position
	var best_p: Dictionary = {}
	var best_dist: float = INF
	for p_var: Variant in pickups_var as Array:
		if typeof(p_var) != TYPE_DICTIONARY:
			continue
		var p: Dictionary = p_var as Dictionary
		var ppos: Vector2 = p.get("pos", Vector2.ZERO) as Vector2
		var d: float = my_pos.distance_to(ppos)
		if d < best_dist:
			best_dist = d
			best_p = p
	return best_p


func _find_best_enemy(fighter: Node2D, match_world: Node2D) -> Node2D:
	var fighters_var: Variant = match_world.get("fighters")
	if typeof(fighters_var) != TYPE_ARRAY:
		return null
	var my_pos: Vector2 = fighter.global_position
	var my_team: int = int(fighter.get("team_id")) if fighter.get("team_id") != null else 0
	var best_enemy: Node2D = null
	var best_score: float = INF

	for f_var: Variant in fighters_var as Array:
		if not is_instance_valid(f_var) or not (f_var is Node2D) or f_var == fighter:
			continue
		var other: Node2D = f_var as Node2D
		if bool(other.get("is_dead")):
			continue
		var other_team: int = int(other.get("team_id")) if other.get("team_id") != null else 0
		if my_team != 0 and my_team == other_team:
			continue
		var dist: float = my_pos.distance_to(other.global_position) + absf(my_pos.y - other.global_position.y) * 0.8
		if dist < best_score:
			best_score = dist
			best_enemy = other

	return best_enemy


func _find_explosive_prop_near(target_pos: Vector2, match_world: Node2D, max_radius: float = 75.0) -> Node2D:
	var props_var: Variant = match_world.get("props")
	if typeof(props_var) != TYPE_ARRAY:
		return null
	var best_prop: Node2D = null
	var best_dist: float = max_radius
	for p_var: Variant in props_var as Array:
		if not is_instance_valid(p_var) or not (p_var is Node2D):
			continue
		var prop: Node2D = p_var as Node2D
		if bool(prop.get("is_destroyed")):
			continue
		var ptype: String = str(prop.get("prop_type"))
		if ptype in ["BARREL_EXPLOSIVE", "GASCAN", "BARREL_WRECK"]:
			var d: float = prop.global_position.distance_to(target_pos)
			if d <= best_dist:
				best_dist = d
				best_prop = prop
	return best_prop


func _has_line_of_sight(from_pt: Vector2, to_pt: Vector2, map_loader: Node2D, ignore_cover_id: int = -1) -> bool:
	if map_loader == null or not is_instance_valid(map_loader) or not map_loader.has_method("raycast_solid"):
		return true
	var hit: Dictionary = map_loader.call("raycast_solid", from_pt, to_pt, ignore_cover_id, false, false) as Dictionary
	if not bool(hit.get("hit", false)):
		return true
	var hit_prop: Node2D = hit.get("prop", null) as Node2D
	if hit_prop != null and str(hit_prop.get("prop_type")) in ["BARREL_EXPLOSIVE", "GASCAN", "BARREL_WRECK"]:
		return true
	var hit_pos: Vector2 = hit.get("pos", to_pt) as Vector2
	return hit_pos.distance_to(to_pt) <= 14.0


func _evaluate_powered_bot_skills(
	fighter: Node2D,
	enemy: Node2D,
	abs_dx: float,
	abs_dy: float,
	dx: float
) -> Dictionary:
	if not fighter.has_method("can_cast_skill_slot"):
		return {}
	var face_left: bool = dx < 0.0
	var face_right: bool = dx >= 0.0
	# 1. Check Ultimate (Skill 4) when enemy is in range and aligned
	if abs_dx <= 180.0 and abs_dy <= 42.0 and bool(fighter.call("can_cast_skill_slot", 4)):
		if difficulty >= DIFF_MEDIUM or randf() < 0.35:
			var inp4: Dictionary = _make_empty_input()
			inp4["left"] = face_left
			inp4["right"] = face_right
			inp4["skill_4"] = true
			inp4["skill_4_just_pressed"] = true
			return inp4
	# 2. Check Gap-closer / Summon / Mobility (Skill 3) when at medium-far distance
	if abs_dx >= 48.0 and abs_dx <= 170.0 and abs_dy <= 55.0 and bool(fighter.call("can_cast_skill_slot", 3)):
		if randf() < 0.45:
			var inp3: Dictionary = _make_empty_input()
			inp3["left"] = face_left
			inp3["right"] = face_right
			inp3["skill_3"] = true
			inp3["skill_3_just_pressed"] = true
			return inp3
	# 3. Check Utility / Parry / Charge (Skill 2) when close or low resource
	if abs_dx <= 95.0 and abs_dy <= 38.0 and bool(fighter.call("can_cast_skill_slot", 2)):
		if randf() < 0.40:
			var inp2: Dictionary = _make_empty_input()
			inp2["left"] = face_left
			inp2["right"] = face_right
			inp2["skill_2"] = true
			inp2["skill_2_just_pressed"] = true
			return inp2
	# 4. Check Primary Strike / Projectile (Skill 1)
	if abs_dx <= 135.0 and abs_dy <= 36.0 and bool(fighter.call("can_cast_skill_slot", 1)):
		var inp1: Dictionary = _make_empty_input()
		inp1["left"] = face_left
		inp1["right"] = face_right
		inp1["skill_1"] = true
		inp1["skill_1_just_pressed"] = true
		return inp1
	return {}


func _make_empty_input() -> Dictionary:
	return {
		"left": false,
		"right": false,
		"up": false,
		"down": false,
		"jump": false,
		"attack": false,
		"sprint": false,
		"powerup": false,
		"skill_1": false,
		"skill_2": false,
		"skill_3": false,
		"skill_4": false,
		"slot_1": false,
		"slot_2": false,
		"slot_3": false,
		"slot_4": false,
	}
