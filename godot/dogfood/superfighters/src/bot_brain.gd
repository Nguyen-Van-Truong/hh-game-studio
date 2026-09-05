class_name BotBrain
extends RefCounted

const _BotRules: GDScript = preload("res://src/bot/bot_rules.gd")
const _BotNav: GDScript = preload("res://src/bot/bot_nav.gd")

## Deterministic planner (VF6-WP5). No teleport, no perfect aim,
## no hidden HP/ammo through walls. Difficulty is delay / aim error /
## tactical budget / recovery. ledger:RL-BOT-PLAN.

var profile_id: String = "regular"
var fire_hold: float = 0.0
var holding_fire: bool = false
var nade_hold: float = 0.0
var holding_nade: bool = false
var bound: bool = false
var bound_seed: int = 0
var recover_wait: int = 0
var reaction_left: int = 0
var replan_left: int = 0
var path_cells: Array = []
var path_i: int = 0
var intent: String = "hold"
var intent_at: Vector2 = Vector2.ZERO
var seen_foe: Fighter = null
var seen_at: Vector2 = Vector2.ZERO
var seen_tick: int = -999
var seen_had_los: bool = false
var expansions_last: int = 0
var expansions_peak: int = 0
var pit_blocks: int = 0
var pit_reroutes: int = 0
var detour_dir: float = 0.0
var detour_left: int = 0
var air_hop: bool = false
var fire_blocks: int = 0
var gun_used: int = 0
var melee_used: int = 0
var nade_used: int = 0
var shots_with_error: int = 0
var perfect_aim_shots: int = 0
var last_aim_error_deg: float = 0.0
var last_shot_off_deg: float = 0.0
var last_center_dir: Vector2 = Vector2.ZERO
var first_see_tick: int = -1
var first_fire_tick: int = -1
var think_ticks: int = 0
var moved_px: float = 0.0
var last_pos: Vector2 = Vector2.ZERO
var observed_shots: int = 0
var ledger_i: int = 0
var _map_doc: Dictionary = {}
var _map_doc_id: String = ""
var patrol_pad_i: int = 0
var lock_foe_slot: int = -1
var rng: RandomNumberGenerator = RandomNumberGenerator.new()


func bind(session: GameSession, slot: int, p_profile: String) -> void:
	profile_id = p_profile
	if profile_id == "":
		profile_id = _BotRules.default_profile_id()
	var seed_v: int = 7
	if session != null:
		seed_v = session.sim_seed
	bound_seed = seed_v * 1009 + slot * 17 + profile_id.hash()
	if bound_seed < 0:
		bound_seed = -bound_seed
	rng.seed = bound_seed
	bound = true
	ledger_i = 0
	nade_used = 0
	melee_used = 0
	observed_shots = 0
	gun_used = 0
	shots_with_error = 0
	perfect_aim_shots = 0
	_map_doc = {}
	_map_doc_id = ""


func think(bot: Fighter, others: Array, pickups: Array, delta: float) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	if bot == null or bot.dead:
		return cmd
	_ensure_bound(bot)
	think_ticks += 1
	if bot.is_on_floor() or bot.on_ladder:
		air_hop = false
	if last_pos != Vector2.ZERO:
		moved_px += bot.global_position.distance_to(last_pos)
	last_pos = bot.global_position
	var session: GameSession = bot.get_parent() as GameSession
	_sync_from_world(bot, session)
	if bot.reaction_locked():
		recover_wait = int(_spec().get("recovery_wait_ticks", 12))
		return cmd
	if recover_wait > 0:
		recover_wait -= 1
		return cmd
	var doc: Dictionary = _doc(session)
	var foe: Fighter = _perceive_foe(bot, others, session)
	var incoming: bool = _incoming_fire(bot, session)
	if incoming:
		fire_blocks += 1
	if foe != null:
		if first_see_tick < 0:
			first_see_tick = think_ticks
			reaction_left = int(_spec().get("reaction_ticks", 10))
		seen_foe = foe
		seen_at = foe.global_position
		seen_had_los = true
		if session != null and session.clock != null:
			seen_tick = session.clock.tick
	if reaction_left > 0:
		reaction_left -= 1
	if replan_left <= 0:
		_replan(bot, foe, pickups, incoming, doc, session)
		replan_left = int(_spec().get("replan_every", 8))
	else:
		replan_left -= 1
	cmd = _follow_or_fight(bot, foe, pickups, incoming, doc, session, delta)
	return cmd


func think_greedy(bot: Fighter, others: Array, pickups: Array, _delta: float) -> Dictionary:
	## Baseline that walks straight at the foe/pickup. No pit graph,
	## no floor-ahead freeze, no aim error. Used only for compare.
	var cmd: Dictionary = InputActions.empty_cmd()
	if bot == null or bot.dead:
		return cmd
	var has_gun: bool = str(WeaponDefs.data(bot.gun_id).get("kind", "")) == "gun" and bot.ammo > 0
	var nearest_pick: Pickup = _nearest_pickup(bot, pickups, 140.0, false)
	var target: Vector2 = bot.global_position
	if (not has_gun) and nearest_pick != null:
		target = nearest_pick.global_position
	else:
		var foe: Fighter = _farthest_foe(bot, others)
		if foe == null:
			return cmd
		target = foe.global_position
	var dx: float = target.x - bot.global_position.x
	var dy: float = target.y - bot.global_position.y
	if absf(dx) > 4.0:
		cmd["x"] = signf(dx)
	if dy < -28.0 or _wall_ahead(bot, float(cmd.get("x", 0.0))):
		cmd["jump"] = true
		cmd["jump_pressed"] = bot.is_on_floor()
	return cmd


func telemetry() -> Dictionary:
	return {
		"profile_id": profile_id,
		"intent": intent,
		"expansions_last": expansions_last,
		"expansions_peak": expansions_peak,
		"pit_blocks": pit_blocks,
		"pit_reroutes": pit_reroutes,
		"fire_blocks": fire_blocks,
		"gun_used": gun_used,
		"melee_used": melee_used,
		"nade_used": nade_used,
		"shots_with_error": shots_with_error,
		"perfect_aim_shots": perfect_aim_shots,
		"last_aim_error_deg": last_aim_error_deg,
		"last_shot_off_deg": last_shot_off_deg,
		"first_see_tick": first_see_tick,
		"first_fire_tick": first_fire_tick,
		"think_ticks": think_ticks,
		"moved_px": moved_px,
		"bound_seed": bound_seed,
	}


func _ensure_bound(bot: Fighter) -> void:
	if bound:
		return
	var session: GameSession = bot.get_parent() as GameSession
	var slot: int = 0
	if bot != null:
		slot = bot.slot
	var wave: int = 0
	if session != null and session.survival != null:
		wave = session.survival.wave_index
	var mode: String = "vs1"
	var stage_i: int = 0
	if session != null:
		mode = session.mode
		stage_i = session.stage_index
	bind(session, slot, _BotRules.profile_for_mode(mode, stage_i, wave))


func _spec() -> Dictionary:
	return _BotRules.profile(profile_id)


func _doc(session: GameSession) -> Dictionary:
	if session == null:
		return {}
	if _map_doc_id == session.map_id and not _map_doc.is_empty():
		return _map_doc
	_map_doc = MapCatalog.document(session.map_id)
	_map_doc_id = session.map_id
	return _map_doc


func _sync_from_world(bot: Fighter, session: GameSession) -> void:
	if bot.shots_fired > observed_shots:
		var add: int = bot.shots_fired - observed_shots
		var off: float = 0.0
		if last_center_dir.length() > 0.2 and bot.last_fire_dir.length() > 0.2:
			off = absf(rad_to_deg(bot.last_fire_dir.angle_to(last_center_dir)))
			last_shot_off_deg = off
		if off >= 1.0:
			shots_with_error += add
		else:
			perfect_aim_shots += add
		if first_fire_tick < 0:
			first_fire_tick = think_ticks
		observed_shots = bot.shots_fired
	gun_used = bot.shots_fired
	_ingest_ledger(session, bot)


func _ingest_ledger(session: GameSession, bot: Fighter) -> void:
	if session == null or session.ledger == null or bot == null:
		return
	var events: Array = session.ledger.events
	while ledger_i < events.size():
		var row: Dictionary = events[ledger_i] as Dictionary
		ledger_i += 1
		var kind: String = str(row.get("kind", ""))
		var payload: Dictionary = row.get("payload", {}) as Dictionary
		if kind == "explosion" and int(payload.get("owner", -1)) == bot.slot:
			nade_used += 1
		elif (kind == "hit" or kind == "kick_hit") and str(row.get("phase", "")) == "melee":
			if int(payload.get("attacker", -1)) == bot.slot:
				melee_used += 1


func _replan(
	bot: Fighter, foe: Fighter, pickups: Array, incoming: bool, doc: Dictionary, session: GameSession
) -> void:
	var budget: int = maxi(int(_spec().get("tactical_budget", 8)), 1)
	var cap: int = maxi(int(_spec().get("max_expansions", 40)), 8)
	var scored: Array = []
	var has_gun: bool = bot.holds_gun()
	var pickup: Pickup = _nearest_pickup(bot, pickups, 160.0, true)
	## A locked 1v1/reach target is the job. Do not wander to a pickup
	## or cover pad that walks away from the named foe.
	if lock_foe_slot >= 0:
		if foe != null and scored.size() < budget:
			if bot.health < 28.0:
				var retreat_at: Vector2 = bot.global_position + (bot.global_position - foe.global_position).normalized() * 48.0
				scored.append({"intent": "retreat", "at": retreat_at, "cost": 3})
			else:
				scored.append({"intent": "attack", "at": foe.global_position, "cost": 1})
		elif scored.size() < budget:
			scored.append({"intent": "hunt", "at": _locked_pad(session, lock_foe_slot), "cost": 1})
		if (not has_gun) and pickup != null and bot.global_position.distance_to(pickup.global_position) < 24.0 and scored.size() < budget:
			scored.append({"intent": "pickup", "at": pickup.global_position, "cost": 2})
	else:
		if (not has_gun) and pickup != null and scored.size() < budget:
			scored.append({"intent": "pickup", "at": pickup.global_position, "cost": 1})
		if incoming and foe == null and scored.size() < budget:
			scored.append({"intent": "cover", "at": _cover_point(bot, foe, doc), "cost": 2})
		if foe == null and seen_had_los and scored.size() < budget:
			var age: int = 999
			if session != null and session.clock != null:
				age = session.clock.tick - seen_tick
			if age <= 16:
				scored.append({"intent": "hunt", "at": seen_at, "cost": 3})
		if foe != null and scored.size() < budget:
			var attack_at: Vector2 = foe.global_position
			if bot.health < 28.0:
				attack_at = bot.global_position + (bot.global_position - foe.global_position).normalized() * 48.0
				scored.append({"intent": "retreat", "at": attack_at, "cost": 3})
			else:
				scored.append({"intent": "attack", "at": attack_at, "cost": 2})
		if scored.is_empty():
			scored.append({"intent": "patrol", "at": _patrol_point(bot, session, doc), "cost": 4})
	if scored.is_empty():
		scored.append({"intent": "patrol", "at": _patrol_point(bot, session, doc), "cost": 4})
	var best: Dictionary = scored[0] as Dictionary
	var i: int = 1
	while i < scored.size():
		var row: Dictionary = scored[i] as Dictionary
		if int(row.get("cost", 99)) < int(best.get("cost", 99)):
			best = row
		i += 1
	intent = str(best.get("intent", "hold"))
	var target: Vector2 = best.get("at", bot.global_position) as Vector2
	intent_at = target
	var planned: Dictionary = _BotNav.path_to(doc, bot.global_position, target, cap)
	expansions_last = int(planned.get("expansions", 0))
	if expansions_last > expansions_peak:
		expansions_peak = expansions_last
	path_cells = planned.get("cells", []) as Array
	path_i = 1 if path_cells.size() > 1 else 0


func _follow_or_fight(
	bot: Fighter,
	foe: Fighter,
	pickups: Array,
	incoming: bool,
	doc: Dictionary,
	session: GameSession,
	delta: float
) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	if holding_nade:
		var nade_foe: Fighter = foe
		if nade_foe == null:
			holding_nade = false
			nade_hold = 0.0
		else:
			return _throw_nade(bot, nade_foe, delta)
	var waypoint: Vector2 = _waypoint(bot, doc)
	var fight_now: bool = foe != null and reaction_left <= 0
	if fight_now:
		var to: Vector2 = foe.global_position - bot.global_position
		var dist: float = to.length()
		if dist < 48.0:
			cmd["melee"] = true
			if to.x != 0.0:
				cmd["x"] = _step_or_detour(bot, signf(to.x), foe.global_position, doc)
			return cmd
		if not bot.holds_gun():
			return _go_to(bot, foe.global_position, false, doc)
		if dist <= 140.0 and _want_nade(bot, dist):
			return _throw_nade(bot, foe, delta)
		var go: Dictionary = _go_to(bot, waypoint if not path_cells.is_empty() else foe.global_position, false, doc)
		if bot.holds_gun() and dist <= 130.0:
			cmd = _aim_and_fire(bot, foe, delta)
			## Keep closing after fire starts. Fire from range is fine;
			## parking at a harness gate (72 / 48) is not. Walk-stop is
			## the melee pocket only — not the reach constant.
			if dist > 28.0:
				cmd["x"] = float(go.get("x", 0.0))
				cmd["jump"] = bool(go.get("jump", false))
				cmd["jump_pressed"] = bool(go.get("jump_pressed", false))
				cmd["crouch"] = bool(go.get("crouch", false))
				if bool(go.get("jump", false)) or bool(go.get("crouch", false)):
					cmd["fire_held"] = false
					cmd["fire_released"] = false
					holding_fire = false
					fire_hold = 0.0
			return cmd
		return go
	if incoming and intent == "cover":
		var away: float = -1.0
		if foe != null and foe.global_position.x > bot.global_position.x:
			away = 1.0
		cmd["x"] = _step_or_detour(bot, away, waypoint, doc)
		if float(cmd.get("x", 0.0)) == 0.0:
			cmd["jump"] = true
			cmd["jump_pressed"] = bot.is_on_floor()
		return cmd
	if intent == "pickup":
		var drop: Pickup = _nearest_pickup(bot, pickups, 160.0, true)
		if drop != null and bot.global_position.distance_to(drop.global_position) < 18.0:
			cmd["crouch"] = true
			cmd["melee"] = true
			return cmd
	return _go_to(bot, waypoint, intent == "pickup", doc)


func _waypoint(bot: Fighter, doc: Dictionary) -> Vector2:
	if path_cells.is_empty():
		return intent_at if intent_at != Vector2.ZERO else bot.global_position
	if path_i >= path_cells.size():
		path_i = path_cells.size() - 1
	var cell: Vector2i = path_cells[path_i] as Vector2i
	var at: Vector2 = MapGraph.cell_center(cell)
	if bot.global_position.distance_to(at) < 12.0 and path_i + 1 < path_cells.size():
		path_i += 1
		cell = path_cells[path_i] as Vector2i
		at = MapGraph.cell_center(cell)
	if path_i >= path_cells.size() - 1 and intent_at != Vector2.ZERO and bot.global_position.distance_to(intent_at) > 36.0:
		return intent_at
	if doc.is_empty():
		return at
	return at


func _aim_and_fire(bot: Fighter, foe: Fighter, delta: float) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	var to: Vector2 = foe.global_position - bot.global_position
	if to == Vector2.ZERO:
		to = Vector2(bot.facing, 0.0)
	var center: Vector2 = to.normalized()
	last_center_dir = center
	var err: float = _roll_aim_error()
	last_aim_error_deg = err
	var aimed: Vector2 = Vector2.from_angle(center.angle() + deg_to_rad(err))
	cmd["aim_x"] = aimed.x
	cmd["aim_y"] = aimed.y
	if absf(aimed.x) > 0.05:
		bot.facing = signf(aimed.x)
	if aimed.y < -0.35:
		cmd["jump"] = true
	elif aimed.y > 0.35:
		cmd["crouch"] = true
	if not holding_fire:
		holding_fire = true
		fire_hold = 0.0
	fire_hold += delta
	cmd["fire_held"] = true
	cmd["x"] = 0.0
	if bool(WeaponDefs.data(bot.gun_id).get("auto", false)):
		if fire_hold >= 0.45:
			holding_fire = false
			fire_hold = 0.0
	elif fire_hold >= 0.16:
		cmd["fire_released"] = true
		holding_fire = false
		fire_hold = 0.0
	return cmd


func _want_nade(bot: Fighter, dist: float) -> bool:
	if bot == null or bot.grenades <= 0:
		return false
	## After a gun fight close, not a start-of-test dump at 48–220.
	if dist < 36.0 or dist > 90.0:
		return false
	if nade_used >= 1:
		return false
	if first_fire_tick < 0 or gun_used < 1:
		return false
	return think_ticks > first_fire_tick + 18


func _throw_nade(bot: Fighter, foe: Fighter, delta: float) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	var to: Vector2 = foe.global_position - bot.global_position
	if to == Vector2.ZERO:
		to = Vector2(bot.facing, 0.0)
	var center: Vector2 = to.normalized()
	var err: float = _roll_aim_error()
	last_aim_error_deg = err
	var aimed: Vector2 = Vector2.from_angle(center.angle() + deg_to_rad(err))
	cmd["aim_x"] = aimed.x
	cmd["aim_y"] = aimed.y
	if absf(aimed.x) > 0.05:
		bot.facing = signf(aimed.x)
	if not holding_nade:
		holding_nade = true
		nade_hold = 0.0
	nade_hold += delta
	cmd["grenade_held"] = true
	if aimed.y < -0.25:
		cmd["jump"] = true
	if nade_hold >= 0.22:
		cmd["grenade_released"] = true
		holding_nade = false
		nade_hold = 0.0
	return cmd


func _roll_aim_error() -> float:
	var mag: float = maxf(float(_spec().get("aim_error_deg", 10.0)), 4.0)
	## Real analog roll. A near-zero miss may count as perfect_aim;
	## that counter is telemetry, not proof.
	return (rng.randf() * 2.0 - 1.0) * mag


func _go_to(bot: Fighter, target: Vector2, pickup: bool, doc: Dictionary) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	var at: Vector2 = target
	if not path_cells.is_empty():
		at = _waypoint(bot, doc)
	var dx: float = at.x - bot.global_position.x
	var dy: float = at.y - bot.global_position.y
	var dir: float = 0.0
	if absf(dx) > 6.0:
		dir = signf(dx)
	var climb_up: bool = false
	var climb_down: bool = false
	var nxt: Vector2i = Vector2i.ZERO
	var here: Vector2i = Vector2i.ZERO
	var have_path: bool = not path_cells.is_empty() and not doc.is_empty()
	if have_path:
		nxt = path_cells[mini(path_i, path_cells.size() - 1)] as Vector2i
		here = MapGraph.stand_cell(doc, bot.global_position)
		if nxt.y < here.y:
			climb_up = true
		elif nxt.y > here.y:
			climb_down = true
	cmd["x"] = _step_or_detour(bot, dir, at, doc)
	## Diagonal off a rung/lip: climb first so A* (10,6)->(9,7) does not walk the pit.
	if (climb_up or climb_down) and (
		bot.on_ladder or _BotNav.unsafe_world_step(doc, bot.global_position, dir)
	):
		cmd["x"] = 0.0
	var need_hop: bool = (
		climb_up
		or dy < -28.0
		or _wall_ahead(bot, float(cmd.get("x", 0.0)))
		or _want_gap_jump(bot, dir, doc)
	)
	if (
		dir != 0.0
		and float(cmd.get("x", 0.0)) != dir
		and not climb_down
		and (bot.is_on_floor() or bot.on_ladder)
	):
		need_hop = true
	if need_hop and (bot.is_on_floor() or bot.on_ladder):
		cmd["jump"] = true
		cmd["jump_pressed"] = true
		air_hop = true
	elif air_hop and not bot.is_on_floor() and not bot.on_ladder:
		## Hold the hop so variable-jump cut does not stall on a door face.
		cmd["jump"] = true
	if climb_down:
		if _on_one_way(doc, bot.global_position) and not bot.climbing:
			## Crouch on a one-way deck drops through the bridge. Attach first.
			cmd["jump"] = true
			cmd["jump_pressed"] = bot.on_ladder or bot.is_on_floor()
			if bot.on_ladder or bot.is_on_floor():
				air_hop = true
			cmd["crouch"] = false
		else:
			cmd["crouch"] = true
	if climb_down and bot.on_ladder:
		## Jump wins over crouch on a ladder. A leftover hop holds them
		## at the west rooftops rung (10,5) for 80 ticks.
		cmd["jump"] = false
		cmd["jump_pressed"] = false
		cmd["crouch"] = true
	if pickup and absf(dx) < 16.0 and absf(dy) < 18.0:
		cmd["crouch"] = true
		cmd["melee"] = true
	return cmd


func _step_or_detour(bot: Fighter, dir: float, target: Vector2, doc: Dictionary) -> float:
	if detour_left > 0:
		detour_left -= 1
		var held: float = _safe_x(bot, detour_dir, doc)
		if held != 0.0:
			return held
		detour_left = 0
	var stepped: float = _safe_x(bot, dir, doc)
	if stepped != 0.0 or dir == 0.0:
		return stepped
	## Climb/drop is the path. A 20-tick walk-around burns the rooftops
	## compare window and walks off the ladder.
	if not path_cells.is_empty() and not doc.is_empty():
		var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
		var nxt: Vector2i = path_cells[mini(path_i, path_cells.size() - 1)] as Vector2i
		if nxt.y != here.y:
			return 0.0
	var around: float = _detour_x(bot, dir, target, doc)
	if around != 0.0:
		detour_dir = around
		detour_left = 8 if around == dir else 4
	return around


func _safe_x(bot: Fighter, dir: float, doc: Dictionary) -> float:
	if dir == 0.0:
		return 0.0
	## Air-walking before a hop pins on crate sides (gauge spawn).
	## Keep x for the whole hop so a tap-jump still clears a 24px door.
	if not bot.is_on_floor() and not bot.on_ladder and not air_hop:
		return 0.0
	var gap_jump: bool = _want_gap_jump(bot, dir, doc)
	if _BotNav.unsafe_world_step(doc, bot.global_position, dir) and not gap_jump:
		pit_blocks += 1
		return 0.0
	if not _floor_ahead(bot, dir) and not _want_drop(bot, dir, doc) and not gap_jump:
		if _adjacent_walk(doc, bot.global_position, dir):
			return dir
		pit_blocks += 1
		return 0.0
	return dir


func _adjacent_walk(doc: Dictionary, pos: Vector2, dir: float) -> bool:
	if doc.is_empty() or absf(dir) < 0.2:
		return false
	var here: Vector2i = MapGraph.stand_cell(doc, pos)
	var step_dir: int = 1 if dir > 0.0 else -1
	if MapGraph.step_is_unsafe(doc, here.x, here.y, step_dir):
		return false
	return MapGraph.is_walkable_cell(doc, here.x + step_dir, here.y)


func _detour_x(bot: Fighter, blocked: float, target: Vector2, doc: Dictionary) -> float:
	var chosen: float = 0.0
	if not path_cells.is_empty():
		var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
		var nxt: Vector2i = path_cells[mini(path_i, path_cells.size() - 1)] as Vector2i
		var ndir: float = 0.0
		if nxt.x != here.x:
			ndir = signf(float(nxt.x - here.x))
		if ndir != 0.0 and ndir != blocked:
			var alt: float = _safe_x(bot, ndir, doc)
			if alt != 0.0:
				chosen = alt
		if chosen == 0.0 and nxt.y < here.y:
			var up_dir: float = ndir if ndir != 0.0 else -blocked
			var hopped: float = _safe_x(bot, up_dir, doc)
			if hopped != 0.0:
				chosen = hopped
	if chosen == 0.0:
		var back: float = _safe_x(bot, -blocked, doc)
		if back != 0.0:
			chosen = back
	if chosen == 0.0:
		var around: Vector2 = _around_pit(bot, blocked, target, doc)
		var adx: float = around.x - bot.global_position.x
		if absf(adx) > 4.0:
			var around_dir: float = _safe_x(bot, signf(adx), doc)
			if around_dir != 0.0:
				chosen = around_dir
	if chosen != 0.0:
		pit_reroutes += 1
	return chosen


func _around_pit(bot: Fighter, blocked: float, target: Vector2, doc: Dictionary) -> Vector2:
	if doc.is_empty():
		return bot.global_position + Vector2(-blocked * 48.0, -32.0)
	var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
	var neighbors: Array = MapGraph.neighbors_of(doc, here.x, here.y)
	var best: Vector2 = bot.global_position + Vector2(-blocked * 40.0, -28.0)
	var best_d: float = 99999.0
	var i: int = 0
	while i < neighbors.size():
		var raw: Array = neighbors[i] as Array
		i += 1
		if raw.size() < 2:
			continue
		var nxt: Vector2i = Vector2i(int(raw[0]), int(raw[1]))
		var step_dir: int = signi(nxt.x - here.x)
		if step_dir != 0 and MapGraph.step_is_unsafe(doc, here.x, here.y, step_dir) and nxt.y == here.y:
			continue
		var at: Vector2 = MapGraph.cell_center(nxt)
		var d: float = at.distance_to(target)
		if nxt.y < here.y:
			d -= 12.0
		if d < best_d:
			best_d = d
			best = at
	return best


func _on_one_way(doc: Dictionary, pos: Vector2) -> bool:
	if doc.is_empty():
		return false
	var cell: Vector2i = MapGraph.stand_cell(doc, pos)
	return MapCodec.has_xy(doc, "one_way", cell.x, cell.y + 1)


func _want_drop(bot: Fighter, dir: float, doc: Dictionary) -> bool:
	if doc.is_empty() or path_cells.is_empty():
		return false
	var nxt: Vector2i = path_cells[mini(path_i, path_cells.size() - 1)] as Vector2i
	var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
	if nxt.y <= here.y:
		return false
	return not MapGraph.step_is_unsafe(doc, here.x, here.y, 1 if dir > 0.0 else -1)


func _want_gap_jump(bot: Fighter, dir: float, doc: Dictionary) -> bool:
	## Path says jump to another walkable cell. Still refuse a same-Y pit step.
	if dir == 0.0 or doc.is_empty() or path_cells.is_empty():
		return false
	var nxt: Vector2i = path_cells[mini(path_i, path_cells.size() - 1)] as Vector2i
	var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
	var step_dir: int = 1 if dir > 0.0 else -1
	if MapGraph.step_is_unsafe(doc, here.x, here.y, step_dir) and nxt.y == here.y:
		return false
	if not MapGraph.is_walkable_cell(doc, nxt.x, nxt.y):
		return false
	var dx: int = absi(nxt.x - here.x)
	var up: int = here.y - nxt.y
	if up > 0 and up <= 3 and dx <= 6:
		return true
	if nxt.y == here.y and dx >= 2 and dx <= 6 and not MapGraph.step_is_unsafe(doc, here.x, here.y, step_dir):
		if not _BotNav._same_y_walk_clear(doc, here.x, nxt.x, here.y):
			return true
	return false


func _locked_pad(session: GameSession, slot: int) -> Vector2:
	if session != null and session.arena != null and slot >= 0 and slot < session.arena.player_spawns.size():
		return session.arena.player_spawns[slot]
	return seen_at


func _perceive_foe(bot: Fighter, others: Array, session: GameSession) -> Fighter:
	## LOS only. hearing_px is a nearer react range, still blocked by world.
	## No through-wall last-seen. Null physics space is not a foe.
	## lock_foe_slot is a 1v1 designation (public spawn), not wallhacks.
	var hear: float = float(_spec().get("hearing_px", 72.0))
	var best: Fighter = null
	var best_d: float = 99999.0
	var i: int = 0
	while i < others.size():
		var f: Fighter = others[i] as Fighter
		i += 1
		if f == null or f.dead or f.team == bot.team:
			continue
		if lock_foe_slot >= 0 and f.slot != lock_foe_slot:
			continue
		if not _has_los(bot, f):
			continue
		var d: float = bot.global_position.distance_to(f.global_position)
		var score: float = d
		if d > hear:
			score += 8.0
		if score < best_d:
			best_d = score
			best = f
	if best == null and seen_had_los and seen_foe != null and is_instance_valid(seen_foe) and not seen_foe.dead:
		var age: int = 999
		if session != null and session.clock != null:
			age = session.clock.tick - seen_tick
		if age <= 8 and _has_los(bot, seen_foe):
			return seen_foe
		if age > 8:
			seen_had_los = false
	return best


func _has_los(bot: Fighter, other: Fighter) -> bool:
	if bot == null or other == null:
		return false
	if bot.get_world_2d() == null:
		return false
	var space: PhysicsDirectSpaceState2D = bot.get_world_2d().direct_space_state
	if space == null:
		return false
	var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(
		bot.global_position + Vector2(0.0, -8.0), other.global_position + Vector2(0.0, -8.0)
	)
	query.collision_mask = Maps.COL_WORLD | Maps.COL_PROP
	query.exclude = [bot.get_rid()]
	var hit: Dictionary = space.intersect_ray(query)
	if hit.is_empty():
		return true
	return hit.get("collider") == other


func _incoming_fire(bot: Fighter, session: GameSession) -> bool:
	if session == null:
		return false
	var i: int = 0
	while i < session.bullets.size():
		var shot: Bullet = session.bullets[i]
		i += 1
		if shot == null or not is_instance_valid(shot) or shot.spent:
			continue
		if shot.owner_slot == bot.slot or shot.owner_team == bot.team:
			continue
		var to: Vector2 = bot.global_position - shot.global_position
		if to.length() > 90.0:
			continue
		if shot.velocity.length() < 1.0:
			continue
		var dir: Vector2 = shot.velocity.normalized()
		if dir.dot(to.normalized()) < 0.55:
			continue
		var lateral: float = absf(dir.x * to.y - dir.y * to.x)
		if lateral < 18.0:
			return true
	return false


func _cover_point(bot: Fighter, foe: Fighter, doc: Dictionary) -> Vector2:
	if doc.is_empty():
		return bot.global_position
	var here: Vector2i = MapGraph.stand_cell(doc, bot.global_position)
	var dir: int = -1
	if foe != null and foe.global_position.x > bot.global_position.x:
		dir = 1
	var x: int = here.x - dir
	var guard: int = 0
	while guard < 8:
		if MapGraph.is_walkable_cell(doc, x, here.y) and not MapGraph.step_is_unsafe(doc, here.x, here.y, signi(x - here.x)):
			return MapGraph.cell_center(Vector2i(x, here.y))
		x -= dir
		guard += 1
	return bot.global_position


func _patrol_point(bot: Fighter, session: GameSession, doc: Dictionary) -> Vector2:
	if session != null and session.arena != null:
		var pads: Array[Vector2] = session.arena.player_spawns
		var reachable: Array = []
		var i: int = 0
		while i < pads.size():
			var pad: Vector2 = pads[i]
			i += 1
			if bot.global_position.distance_to(pad) <= 40.0:
				continue
			var planned: Dictionary = _BotNav.path_to(doc, bot.global_position, pad, 40)
			if (planned.get("cells", []) as Array).size() < 2:
				continue
			reachable.append(pad)
		if not reachable.is_empty():
			var pick: Vector2 = reachable[patrol_pad_i % reachable.size()] as Vector2
			patrol_pad_i += 1
			return pick
		if not session.arena.weapon_spawns.is_empty():
			return session.arena.weapon_spawns[0]
	return bot.global_position + Vector2(-bot.facing * 48.0, 0.0)


func _nearest_foe(bot: Fighter, others: Array) -> Fighter:
	var best: Fighter = null
	var best_d: float = 99999.0
	var i: int = 0
	while i < others.size():
		var f: Fighter = others[i] as Fighter
		i += 1
		if f == null or f.dead or f.team == bot.team:
			continue
		var d: float = bot.global_position.distance_to(f.global_position)
		if d < best_d:
			best_d = d
			best = f
	return best


func _farthest_foe(bot: Fighter, others: Array) -> Fighter:
	var best: Fighter = null
	var best_d: float = -1.0
	var i: int = 0
	while i < others.size():
		var f: Fighter = others[i] as Fighter
		i += 1
		if f == null or f.dead or f.team == bot.team:
			continue
		var d: float = bot.global_position.distance_to(f.global_position)
		if d > best_d:
			best_d = d
			best = f
	return best


func _nearest_pickup(bot: Fighter, pickups: Array, limit: float, need_los: bool) -> Pickup:
	var best: Pickup = null
	var best_d: float = limit
	var i: int = 0
	while i < pickups.size():
		var p: Pickup = pickups[i] as Pickup
		i += 1
		if p == null or not is_instance_valid(p):
			continue
		var d: float = bot.global_position.distance_to(p.global_position)
		if d >= best_d:
			continue
		if need_los and d > 48.0 and absf(p.global_position.y - bot.global_position.y) > 28.0:
			continue
		best_d = d
		best = p
	return best


func _floor_ahead(bot: Fighter, dir: float) -> bool:
	if dir == 0.0:
		return true
	if bot.get_world_2d() == null:
		return true
	var space: PhysicsDirectSpaceState2D = bot.get_world_2d().direct_space_state
	if space == null:
		return true
	var from: Vector2 = bot.global_position + Vector2(dir * 12.0, 2.0)
	var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(
		from, from + Vector2(0, 36)
	)
	query.collision_mask = Maps.COL_WORLD | Maps.COL_PLATFORM | Maps.COL_PROP
	query.exclude = [bot.get_rid()]
	var hit: Dictionary = space.intersect_ray(query)
	return not hit.is_empty()


func _wall_ahead(bot: Fighter, dir: float) -> bool:
	if dir == 0.0:
		return false
	if bot.get_world_2d() == null:
		return false
	var space: PhysicsDirectSpaceState2D = bot.get_world_2d().direct_space_state
	if space == null:
		return false
	var from: Vector2 = bot.global_position + Vector2(0, -4)
	var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(
		from, from + Vector2(dir * 14.0, 0)
	)
	query.collision_mask = Maps.COL_WORLD | Maps.COL_PROP
	query.exclude = [bot.get_rid()]
	var hit: Dictionary = space.intersect_ray(query)
	return not hit.is_empty()
