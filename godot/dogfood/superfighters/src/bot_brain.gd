class_name BotBrain
extends RefCounted

var fire_hold: float = 0.0
var holding_fire: bool = false
var nade_hold: float = 0.0
var holding_nade: bool = false


func think(bot: Fighter, others: Array, pickups: Array, delta: float) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	if bot == null or bot.dead:
		return cmd
	var has_gun: bool = str(WeaponDefs.data(bot.gun_id).get("kind", "")) == "gun" and bot.ammo > 0
	var nearest_pick: Pickup = _nearest_pickup(bot, pickups)
	if (not has_gun) and nearest_pick != null:
		return _go_to(bot, nearest_pick.global_position, true)
	var foe: Fighter = _nearest_foe(bot, others)
	if foe == null:
		return cmd
	var to: Vector2 = foe.global_position - bot.global_position
	var dist: float = to.length()
	if has_gun and dist < 260.0 and dist > 36.0:
		if not holding_fire:
			holding_fire = true
			fire_hold = 0.0
		fire_hold += delta
		cmd["fire_held"] = true
		cmd["x"] = 0.0
		if to.y < -18.0:
			cmd["jump"] = true
		elif to.y > 18.0:
			cmd["crouch"] = true
		if bool(WeaponDefs.data(bot.gun_id).get("auto", false)):
			if fire_hold >= 0.45:
				holding_fire = false
				fire_hold = 0.0
		elif fire_hold >= 0.28:
			cmd["fire_released"] = true
			holding_fire = false
			fire_hold = 0.0
		if to.x != 0.0:
			bot.facing = signf(to.x)
		return cmd
	holding_fire = false
	if dist < 22.0:
		cmd["melee"] = true
		if to.x != 0.0:
			cmd["x"] = signf(to.x)
		return cmd
	if bot.grenades > 0 and dist > 70.0 and dist < 160.0:
		if not holding_nade:
			holding_nade = true
			nade_hold = 0.0
		nade_hold += delta
		cmd["grenade_held"] = true
		if to.y < -12.0:
			cmd["jump"] = true
		if nade_hold >= 0.22:
			cmd["grenade_released"] = true
			holding_nade = false
			nade_hold = 0.0
		if to.x != 0.0:
			bot.facing = signf(to.x)
		return cmd
	return _go_to(bot, foe.global_position, false)


func _go_to(bot: Fighter, target: Vector2, pickup: bool) -> Dictionary:
	var cmd: Dictionary = InputActions.empty_cmd()
	var dx: float = target.x - bot.global_position.x
	var dy: float = target.y - bot.global_position.y
	if absf(dx) > 6.0:
		cmd["x"] = signf(dx)
	if dy < -28.0 or _wall_ahead(bot, float(cmd.get("x", 0.0))):
		cmd["jump"] = true
		cmd["jump_pressed"] = bot.is_on_floor()
	if pickup and absf(dx) < 16.0 and absf(dy) < 18.0:
		cmd["crouch"] = true
		cmd["melee"] = true
	if not _floor_ahead(bot, float(cmd.get("x", 0.0))):
		if dy > 20.0:
			pass
		else:
			cmd["x"] = 0.0
			cmd["jump"] = true
			cmd["jump_pressed"] = bot.is_on_floor()
	return cmd


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


func _nearest_pickup(bot: Fighter, pickups: Array) -> Pickup:
	var best: Pickup = null
	var best_d: float = 140.0
	var i: int = 0
	while i < pickups.size():
		var p: Pickup = pickups[i] as Pickup
		i += 1
		if p == null or not is_instance_valid(p):
			continue
		var d: float = bot.global_position.distance_to(p.global_position)
		if d < best_d:
			best_d = d
			best = p
	return best


func _floor_ahead(bot: Fighter, dir: float) -> bool:
	if dir == 0.0:
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
