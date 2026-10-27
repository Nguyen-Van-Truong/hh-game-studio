class_name MatchSession
extends Simulation
## First playable Classic round. The base Simulation remains the fixed-step
## authority; this layer adds match state, pickups and a second firearm.

const MAP_PATH: String = "res://data/relay_yard.json"
const MATCH_SCHEMA: StringName = &"sa05.match.v1"
const MODE_RULES_SCRIPT = preload("res://game/core/classic_mode_rules.gd")
const MAP_CATALOG_SCRIPT = preload("res://game/world/map_catalog.gd")
const WEAPON_CATALOG_SCRIPT = preload("res://game/core/weapon_catalog.gd")

var opponent: StringName = &"two_player"
var map_id: StringName = &"relay_yard"
var map_path: String = MAP_PATH
var phase: StringName = &"playing"
var winner: int = 0
var error: StringName = &""
var melee_ids: Array[StringName] = [&"fists", &"fists"]
var gun_ids: Array[StringName] = [&"pistol", &"pistol"]
var active_weapon_slots: Array[int] = [1, 1]
var pickup_rows: Array[Dictionary] = []
var prop_rows: Array[Dictionary] = []
var shot_events: Array[Dictionary] = []
var explosion_events: Array[Dictionary] = []
var weapon_events: Array[Dictionary] = []
var prop_events: Array[Dictionary] = []
var fire_events: Array[Dictionary] = []
var airdrop_serial: int = 0
var burning_ticks: Array[int] = [0, 0]
var burn_elapsed_ticks: Array[int] = [0, 0]
var bullet_time_owner: int = -1
var bullet_time_ticks: int = 0
var bullet_time_duration_ticks: int = 0
var mode_rules: ClassicModeRules
var weapon_catalog_fingerprint: String = ""

func _init(seed_input: int = 1, opponent_input: StringName = &"two_player", mode_input: StringName = &"vs", rule_input: StringName = &"infinite", map_id_input: StringName = &"relay_yard") -> void:
	super(seed_input)
	opponent = opponent_input if opponent_input == &"bot" or opponent_input == &"two_player" else &"two_player"
	map_id = map_id_input
	if not WEAPON_CATALOG_SCRIPT.validate():
		phase = &"invalid"
		error = &"invalid_weapon_catalog"
		return
	weapon_catalog_fingerprint = WEAPON_CATALOG_SCRIPT.fingerprint()
	var map_entry: Dictionary = MAP_CATALOG_SCRIPT.resolve(map_id_input)
	var map_valid: bool = not map_entry.is_empty()
	if map_valid:
		map_path = String(map_entry[&"path"])
	mode_rules = MODE_RULES_SCRIPT.new(mode_input, rule_input)
	world = ArenaState.new(seed_input, map_path)
	if not map_valid:
		phase = &"invalid"
		error = &"invalid_map"
	elif mode_rules.phase == &"invalid":
		phase = &"invalid"
		error = mode_rules.error
	elif not world.valid:
		phase = &"invalid"
		error = world.load_error
	else:
		mode_rules.begin()
	for fighter: FighterState in fighters:
		fighter.position = world.spawn_for_player(fighter.player_id)
		fighter.grounded = true
		fighter.locomotion = FighterState.Locomotion.GROUNDED
		fighter.active_weapon_slot = 1
		fighter.ammo = _starting_ammo(&"pistol", fighter.ammo)
	var world_rows: Variant = world.snapshot().get(&"pickups", [])
	if typeof(world_rows) == TYPE_ARRAY:
		for value: Variant in Array(world_rows):
			if typeof(value) == TYPE_DICTIONARY:
				var row: Dictionary = Dictionary(value).duplicate(true)
				row[&"active"] = bool(row.get(&"active", true))
				pickup_rows.append(row)
	var prop_values: Variant = world.snapshot().get(&"props", [])
	if typeof(prop_values) == TYPE_ARRAY:
		for value: Variant in Array(prop_values):
			if typeof(value) != TYPE_DICTIONARY:
				continue
			var prop: Dictionary = Dictionary(value).duplicate(true)
			var maximum: int = _prop_max_health(StringName(prop.get(&"kind", &"prop")))
			prop[&"active"] = bool(prop.get(&"active", true))
			prop[&"max_health"] = maxi(1, int(prop.get(&"max_health", maximum)))
			prop[&"health"] = clampi(int(prop.get(&"health", prop[&"max_health"])), 0, int(prop[&"max_health"]))
			prop[&"material"] = StringName(prop.get(&"material", &"generic"))
			prop[&"explosive"] = bool(prop.get(&"explosive", prop.get(&"kind", &"") == &"barrel"))
			prop_rows.append(prop)

func step(frame: InputFrame) -> bool:
	if phase != &"playing" or frame == null or frame.tick() != tick:
		return false
	var prior_shot_count: int = shot_events.size()
	var prior_explosion_count: int = explosion_events.size()
	var prior_weapon_event_count: int = weapon_events.size()
	var prior_prop_event_count: int = prop_events.size()
	var prior_fire_event_count: int = fire_events.size()
	_apply_weapon_switches(frame)
	var advanced: bool = super(frame)
	if not advanced:
		return false
	_configure_bullet_time_tempo()
	for index: int in range(mini(prior_shot_count, shot_events.size())):
		shot_events[index][&"ttl"] = int(shot_events[index].get(&"ttl", 0)) - 1
	for index: int in range(mini(prior_explosion_count, explosion_events.size())):
		explosion_events[index][&"ttl"] = int(explosion_events[index].get(&"ttl", 0)) - 1
	for index: int in range(mini(prior_weapon_event_count, weapon_events.size())):
		weapon_events[index][&"ttl"] = int(weapon_events[index].get(&"ttl", 0)) - 1
	for index: int in range(mini(prior_prop_event_count, prop_events.size())):
		prop_events[index][&"ttl"] = int(prop_events[index].get(&"ttl", 0)) - 1
	for index: int in range(mini(prior_fire_event_count, fire_events.size())):
		fire_events[index][&"ttl"] = int(fire_events[index].get(&"ttl", 0)) - 1
	_step_airdrops()
	_collect_pickups(frame)
	_step_burning(frame)
	_check_result()
	if bullet_time_owner >= 0:
		bullet_time_ticks = maxi(0, bullet_time_ticks - 1)
		if bullet_time_ticks == 0:
			_end_bullet_time()
	shot_events = shot_events.filter(func(row: Dictionary) -> bool: return int(row.get(&"ttl", 0)) > 0)
	explosion_events = explosion_events.filter(func(row: Dictionary) -> bool: return int(row.get(&"ttl", 0)) > 0)
	weapon_events = weapon_events.filter(func(row: Dictionary) -> bool: return int(row.get(&"ttl", 0)) > 0)
	prop_events = prop_events.filter(func(row: Dictionary) -> bool: return int(row.get(&"ttl", 0)) > 0)
	fire_events = fire_events.filter(func(row: Dictionary) -> bool: return int(row.get(&"ttl", 0)) > 0)
	return true

func continue_round() -> bool:
	if phase != &"round_result" or not mode_rules.next_round():
		return false
	for index: int in range(fighters.size()):
		fighters[index].reset_for_round(tuning)
		place_fighter(index, world.spawn_for_player(index + 1), Vector2.ZERO, true)
	melee_ids = [&"fists", &"fists"]
	gun_ids = [&"pistol", &"pistol"]
	active_weapon_slots = [1, 1]
	for fighter: FighterState in fighters:
		fighter.active_weapon_slot = 1
		fighter.ammo = _starting_ammo(&"pistol", int(fighter.ammo))
	pickup_rows = _reset_active_rows(pickup_rows)
	prop_rows = _reset_prop_rows(prop_rows)
	shot_events.clear()
	explosion_events.clear()
	weapon_events.clear()
	prop_events.clear()
	fire_events.clear()
	airdrop_serial = 0
	grenades.clear()
	burning_ticks = [0, 0]
	burn_elapsed_ticks = [0, 0]
	bullet_time_owner = -1
	bullet_time_ticks = 0
	bullet_time_duration_ticks = 0
	round_timer_ticks = 0
	winner = 0
	phase = &"playing"
	return true

func set_paused(value: bool) -> bool:
	if value:
		if phase != &"playing" or not mode_rules.set_paused(true):
			return false
		phase = &"paused"
		return true
	if phase != &"paused" or not mode_rules.set_paused(false):
		return false
	phase = &"playing"
	return true

func snapshot() -> Dictionary:
	var base: Dictionary = super()
	var result: Dictionary = base.duplicate(true)
	var fighter_rows: Array = result.get(&"fighters", [])
	for index: int in range(mini(fighter_rows.size(), gun_ids.size())):
		var row: Dictionary = Dictionary(fighter_rows[index]).duplicate(true)
		row[&"gun_id"] = gun_ids[index]
		row[&"melee_id"] = melee_ids[index]
		row[&"active_slot"] = active_weapon_slots[index]
		row[&"active_weapon_id"] = _active_weapon_id(index)
		row[&"aiming"] = fighters[index].aiming
		row[&"aim_angle"] = fighters[index].aim_angle
		row[&"burning_ticks"] = burning_ticks[index]
		row[&"burn_elapsed_ticks"] = burn_elapsed_ticks[index]
		row.make_read_only()
		fighter_rows[index] = row
	fighter_rows.make_read_only()
	var pickup_snapshot: Array[Dictionary] = _copy_rows(pickup_rows)
	var shot_snapshot: Array[Dictionary] = _copy_rows(shot_events)
	var explosion_snapshot: Array[Dictionary] = _copy_rows(explosion_events)
	var weapon_snapshot: Array[Dictionary] = _copy_rows(weapon_events)
	var prop_snapshot: Array[Dictionary] = _copy_rows(prop_rows)
	var prop_event_snapshot: Array[Dictionary] = _copy_rows(prop_events)
	var fire_snapshot: Array[Dictionary] = _copy_rows(fire_events)
	result[&"fighters"] = fighter_rows
	result[&"schema"] = MATCH_SCHEMA
	result[&"phase"] = phase
	result[&"winner"] = winner
	result[&"opponent"] = opponent
	result[&"map_id"] = map_id
	result[&"map_path"] = map_path
	result[&"error"] = error
	result[&"pickups"] = pickup_snapshot
	result[&"shot_events"] = shot_snapshot
	result[&"explosions"] = explosion_snapshot
	result[&"weapon_events"] = weapon_snapshot
	result[&"props"] = prop_snapshot
	result[&"prop_events"] = prop_event_snapshot
	result[&"fire_events"] = fire_snapshot
	result[&"burn_elapsed_ticks"] = burn_elapsed_ticks.duplicate()
	result[&"bullet_time_owner"] = bullet_time_owner
	result[&"bullet_time_ticks"] = bullet_time_ticks
	result[&"bullet_time_duration_ticks"] = bullet_time_duration_ticks
	result[&"weapon_catalog_fingerprint"] = weapon_catalog_fingerprint
	result[&"mode_rules"] = mode_rules.snapshot()
	var world_value: Variant = result.get(&"world", {})
	if typeof(world_value) == TYPE_DICTIONARY:
		var world_snapshot: Dictionary = Dictionary(world_value).duplicate(true)
		world_snapshot[&"pickups"] = pickup_snapshot
		world_snapshot[&"props"] = prop_snapshot
		for world_key: StringName in [&"platforms", &"ladders", &"pits", &"solids", &"spawns", &"props"]:
			var rows_value: Variant = world_snapshot.get(world_key, [])
			if typeof(rows_value) != TYPE_ARRAY:
				continue
			var rows: Array[Dictionary] = []
			for row_value: Variant in Array(rows_value):
				if typeof(row_value) == TYPE_DICTIONARY:
					rows.append(Dictionary(row_value))
			world_snapshot[world_key] = _copy_rows(rows)
		world_snapshot.make_read_only()
		result[&"world"] = world_snapshot
	result.make_read_only()
	return result

func canonical_snapshot() -> String:
	var base: String = super()
	var pickups: Array[String] = []
	for row: Dictionary in pickup_rows:
		pickups.append("%s,%s,%s,%.3f,%.3f,%d,%d,%d,%d,%.3f" % [String(row.get(&"id", &"")), String(row.get(&"kind", &"")), String(row.get(&"crate_type", &"")), float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0)), int(bool(row.get(&"active", false))), int(row.get(&"duration_ticks", 0)), int(bool(row.get(&"airdrop", false))), int(bool(row.get(&"landed", false))), float(row.get(&"target_y", 0.0))])
	var weapon_parts: Array[String] = []
	for event: Dictionary in weapon_events:
		weapon_parts.append("%s,%d,%d,%d" % [String(event.get(&"kind", &"")), int(event.get(&"attacker", 0)), int(event.get(&"target", 0)), int(event.get(&"ttl", 0))])
	var shot_parts: Array[String] = []
	for event: Dictionary in shot_events:
		var from_point: Vector2 = Vector2(event.get(&"from", Vector2.ZERO))
		var to_point: Vector2 = Vector2(event.get(&"to", Vector2.ZERO))
		var target_point: Vector2 = Vector2(event.get(&"target", Vector2.ZERO))
		shot_parts.append("%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.5f,%s,%d" % [int(event.get(&"attacker", 0)), from_point.x, from_point.y, to_point.x, to_point.y, target_point.x, target_point.y, float(event.get(&"angle", 0.0)), String(event.get(&"gun", &"")), int(event.get(&"ttl", 0))])
	var explosion_parts: Array[String] = []
	for event: Dictionary in explosion_events:
		explosion_parts.append("%.3f,%.3f,%.3f,%s,%d" % [float(event.get(&"x", 0.0)), float(event.get(&"y", 0.0)), float(event.get(&"radius", 0.0)), String(event.get(&"source", &"")), int(event.get(&"ttl", 0))])
	var prop_parts: Array[String] = []
	for prop: Dictionary in prop_rows:
		prop_parts.append("%s,%s,%s,%d,%.3f,%.3f,%d,%d,%d" % [String(prop.get(&"id", &"")), String(prop.get(&"kind", &"")), String(prop.get(&"material", &"generic")), int(bool(prop.get(&"explosive", false))), float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0)), int(bool(prop.get(&"active", false))), int(prop.get(&"max_health", 0)), int(prop.get(&"health", 0))])
	var prop_event_parts: Array[String] = []
	for event: Dictionary in prop_events:
		prop_event_parts.append("%s,%s,%d,%s,%d,%d" % [String(event.get(&"kind", &"")), String(event.get(&"prop_id", &"")), int(event.get(&"source", 0)), String(event.get(&"cause", &"")), int(event.get(&"health", -1)), int(event.get(&"ttl", 0))])
	var fire_parts: Array[String] = []
	for event: Dictionary in fire_events:
		fire_parts.append("%s,%d,%d,%d,%d" % [String(event.get(&"kind", &"")), int(event.get(&"player", 0)), int(event.get(&"damage", 0)), int(event.get(&"health", -1)), int(event.get(&"ttl", 0))])
	return "%s|map=%s,%s|catalog=%s|match=%s,%d,%s,%s|mode_rules=%s|melee=%s|guns=%s|slots=%s|pickups=%s|weapons=%s|shots=%s|explosions=%s|props=%s|prop_events=%s|burn=%d,%d,%d,%d|fire_events=%s|bullet=%d,%d,%d" % [base, String(map_id), map_path, weapon_catalog_fingerprint, String(phase), winner, String(opponent), String(error), mode_rules.canonical_snapshot(), ",".join(melee_ids.map(func(g: StringName) -> String: return String(g))), ",".join(gun_ids.map(func(g: StringName) -> String: return String(g))), ",".join(active_weapon_slots.map(func(slot: int) -> String: return str(slot))), ";".join(pickups), ";".join(weapon_parts), ";".join(shot_parts), ";".join(explosion_parts), ";".join(prop_parts), ";".join(prop_event_parts), burning_ticks[0], burning_ticks[1], burn_elapsed_ticks[0], burn_elapsed_ticks[1], ";".join(fire_parts), bullet_time_owner, bullet_time_ticks, bullet_time_duration_ticks]

func _resolve_attacks() -> void:
	var queued: Array[StringName] = []
	for fighter: FighterState in fighters:
		queued.append(fighter.consume_attack())
	for index: int in range(queued.size()):
		var attack: StringName = queued[index]
		if attack == &"none":
			continue
		var attacker: FighterState = fighters[index]
		var target: FighterState = fighters[1 - index]
		if attacker.health <= 0 or attacker.in_pit:
			continue
		if attack == &"power":
			if bullet_time_owner == index:
				_end_bullet_time()
			elif attacker.power_charges > 0:
				attacker.power_charges -= 1
				bullet_time_owner = index
				bullet_time_duration_ticks = maxi(1, attacker.power_duration_ticks)
				bullet_time_ticks = bullet_time_duration_ticks
			continue
		if attack == &"throw":
			var grenade_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(&"grenade")
			if grenade_definition == null or not grenade_definition.is_explosive():
				continue
			grenades.append({&"owner": attacker.player_id, &"x": attacker.position.x, &"y": attacker.position.y - 24.0, &"vx": attacker.facing * grenade_definition.projectile_speed, &"vy": -6.0, &"fuse": grenade_definition.fuse_ticks, &"radius": grenade_definition.explosion_radius, &"damage": grenade_definition.explosion_damage})
			continue
		var fists_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(&"fists")
		if fists_definition == null:
			continue
		var held_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(gun_ids[index])
		var melee_definition: WeaponCatalog.WeaponDefinition = fists_definition
		var melee_slot_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(melee_ids[index])
		if active_weapon_slots[index] == 0 and melee_slot_definition != null and melee_slot_definition.is_melee():
			melee_definition = melee_slot_definition
		elif held_definition != null and held_definition.is_melee():
			# Compatibility for older traces that placed a melee id in gun_ids.
			melee_definition = held_definition
		var distance_x: float = target.position.x - attacker.position.x
		var held_target: bool = attack == &"grab_punch" or attack == &"grab_throw"
		held_target = held_target and target.grabbed_by == attacker.player_id
		var range_limit: float = melee_definition.range_limit
		var damage: int = melee_definition.melee_damage
		var knockback: float = melee_definition.knockback
		if attack == &"jump_kick":
			damage = int(tuning[&"jump_kick_damage"])
			range_limit = float(tuning[&"punch_range"])
		elif attack == &"punch_combo":
			damage = int(tuning[&"punch_damage"]) + 3
		elif attack == &"kick":
			range_limit = float(tuning.get(&"combo_kick_range", tuning[&"punch_range"]))
			damage = int(tuning.get(&"combo_kick_damage", tuning[&"jump_kick_damage"]))
			knockback = float(tuning[&"melee_knockback"]) * 1.3
		elif attack == &"dive":
			range_limit = float(tuning[&"punch_range"]) + 12.0
			damage = int(tuning.get(&"dive_damage", tuning[&"punch_damage"]))
			knockback = float(tuning[&"melee_knockback"]) * 1.25
		elif attack == &"tackle":
			range_limit = float(tuning[&"char_width"]) + 18.0
			damage = int(tuning.get(&"tackle_damage", tuning[&"punch_damage"]))
			knockback = float(tuning[&"melee_knockback"]) * 1.6
		elif attack == &"grab_punch":
			# Classic tackle follow-up: a held opponent can be punched for the
			# same close-range damage as the documented grab hit.
			range_limit = float(tuning.get(&"combo_kick_range", tuning[&"punch_range"]))
			damage = int(tuning.get(&"grab_punch_damage", 17))
			knockback = float(tuning[&"melee_knockback"]) * 0.75
		elif attack == &"grab_throw":
			range_limit = float(tuning.get(&"combo_kick_range", tuning[&"punch_range"]))
			damage = int(tuning.get(&"grab_throw_damage", 6))
			knockback = float(tuning[&"melee_knockback"]) * 2.25
		elif attack == &"shoot":
			var firearm_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(gun_ids[index])
			if firearm_definition == null or firearm_definition.is_melee() or not firearm_definition.has_projectile() or not firearm_definition.has_ammo():
				continue
			range_limit = firearm_definition.range_limit
			damage = firearm_definition.damage
			knockback = firearm_definition.knockback
		var shot_origin := attacker.position + Vector2(float(attacker.facing) * 10.0, -float(tuning[&"char_height"]) * 0.5)
		var target_point := target.position + Vector2(0.0, -float(tuning[&"char_height"]) * 0.5)
		var shot_direction := Vector2(cos(attacker.aim_angle) * float(attacker.facing), sin(attacker.aim_angle)).normalized()
		var target_delta: Vector2 = target_point - shot_origin
		var forward_distance: float = shot_direction.dot(target_delta)
		var lateral_distance: float = absf(shot_direction.cross(target_delta))
		var target_hit: bool = forward_distance >= 0.0 and forward_distance <= range_limit and lateral_distance <= float(tuning[&"char_height"]) * 0.5
		if attack == &"shoot":
			shot_events.append({&"attacker": attacker.player_id, &"from": shot_origin, &"to": shot_origin + shot_direction * range_limit, &"target": target.position, &"angle": attacker.aim_angle, &"ttl": 5, &"gun": gun_ids[index], &"recoil": 1.0 if gun_ids[index] == &"pistol" else 1.5, &"eject": gun_ids[index] == &"pistol"})
		_resolve_prop_attack(index, attack, shot_origin, shot_direction, range_limit, damage)
		if (attack == &"shoot" and target_hit) or (attack != &"shoot" and held_target) or (attack != &"shoot" and distance_x * attacker.facing > 0.0 and absf(target.position.y - attacker.position.y) <= float(tuning[&"char_height"]) and absf(distance_x) <= range_limit):
			var knockdown: bool = attack == &"jump_kick" or attack == &"kick" or attack == &"dive" or attack == &"tackle" or attack == &"grab_throw" or (attack == &"shoot" and (world.rng_state % 4 == 0))
			var hit_applied: bool = target.apply_hit(damage, attacker.facing * knockback, knockdown, attack, tuning)
			if hit_applied and attack == &"tackle":
				target.begin_grab(attacker.player_id, int(tuning.get(&"grab_duration_ticks", 18)))
				attacker.begin_hold(target.player_id, int(tuning.get(&"grab_duration_ticks", 18)))
				weapon_events.append({&"kind": &"tackle_grab", &"attacker": attacker.player_id, &"target": target.player_id, &"ttl": 18})
			elif hit_applied and attack == &"grab_throw":
				target.grabbed_ticks = 0
				target.grabbed_by = 0
				weapon_events.append({&"kind": &"grab_throw", &"attacker": attacker.player_id, &"target": target.player_id, &"ttl": 18})
			if hit_applied and (attack == &"punch" or attack == &"punch_combo" or attack == &"kick" or attack == &"jump_kick" or attack == &"grab_punch") and target.aiming and gun_ids[1 - index] != &"none":
				gun_ids[1 - index] = &"none"
				if active_weapon_slots[1 - index] == 1:
					active_weapon_slots[1 - index] = 0
					fighters[1 - index].active_weapon_slot = 0
				target.ammo = 0
				weapon_events.append({&"kind": &"disarm", &"attacker": attacker.player_id, &"target": target.player_id, &"ttl": 12})

func _step_grenades() -> void:
	var remaining: Array[Dictionary] = []
	for grenade: Dictionary in grenades:
		grenade[&"x"] = float(grenade[&"x"]) + float(grenade[&"vx"])
		grenade[&"y"] = float(grenade[&"y"]) + float(grenade[&"vy"])
		grenade[&"vy"] = float(grenade[&"vy"]) + 1.0
		if float(grenade[&"y"]) >= world.floor_y:
			grenade[&"y"] = world.floor_y
			grenade[&"vy"] = 0.0
		grenade[&"fuse"] = int(grenade[&"fuse"]) - 1
		if int(grenade[&"fuse"]) > 0:
			remaining.append(grenade)
			continue
		var center := Vector2(float(grenade[&"x"]), float(grenade[&"y"]))
		var radius: float = float(grenade.get(&"radius", tuning[&"grenade_radius"]))
		var damage: int = int(grenade.get(&"damage", tuning[&"grenade_damage"]))
		explosion_events.append({&"x": center.x, &"y": center.y, &"radius": radius, &"ttl": 8})
		_damage_props_at(center, radius, damage, 0, &"grenade")
		for target: FighterState in fighters:
			var delta: Vector2 = target.position - center
			if delta.length_squared() <= radius * radius:
				target.apply_hit(damage, 20.0 if delta.x >= 0.0 else -20.0, true, &"grenade", tuning)
	grenades = remaining

func _apply_weapon_switches(frame: InputFrame) -> void:
	for index: int in range(fighters.size()):
		if not _switch_pressed(frame, fighters[index].player_id):
			continue
		var current: int = active_weapon_slots[index]
		for offset: int in range(1, 5):
			var candidate: int = (current + offset) % 4
			if not _slot_available(index, candidate):
				continue
			active_weapon_slots[index] = candidate
			fighters[index].active_weapon_slot = candidate
			if candidate != 1:
				fighters[index].aiming = false
			break

func _switch_pressed(frame: InputFrame, player: int) -> bool:
	var expected: StringName = StringName("p%d_switch" % player)
	for record: Dictionary in frame.records():
		if StringName(record.get(&"action", &"")) == expected and bool(record.get(&"pressed", false)):
			return true
	return false

func _slot_available(index: int, slot: int) -> bool:
	if slot == 0:
		return true
	if slot == 1:
		return gun_ids[index] != &"none"
	if slot == 2:
		return fighters[index].grenades > 0
	return fighters[index].power_charges > 0 or fighters[index].bullet_time_active

func _active_weapon_id(index: int) -> StringName:
	match active_weapon_slots[index]:
		0:
			return melee_ids[index]
		1:
			return gun_ids[index]
		2:
			return &"grenade"
		3:
			return &"bullet_time"
	return &"fists"

func _step_airdrops() -> void:
	# Original authored supply points are supplemented by a deterministic sky
	# drop cadence.  The row is still a normal pickup, so collection, replay and
	# reset use the same semantic path as floor items.
	if tick >= 120 and (tick - 120) % 360 == 0:
		var spawn_xs: Array[float] = [260.0, 800.0, 1340.0]
		var drop_cycle: Array[Dictionary] = [
			{&"kind": &"shotgun", &"crate_type": &"firearm"},
			{&"kind": &"pipe", &"crate_type": &"melee"},
			{&"kind": &"grenades", &"crate_type": &"explosive"},
			{&"kind": &"bullet_time_5", &"crate_type": &"power"},
			{&"kind": &"pistol", &"crate_type": &"firearm"},
			{&"kind": &"knife", &"crate_type": &"melee"},
			{&"kind": &"grenades", &"crate_type": &"explosive"},
			{&"kind": &"bullet_time_10", &"crate_type": &"power"},
		]
		var slot: int = airdrop_serial % spawn_xs.size()
		var drop: Dictionary = drop_cycle[airdrop_serial % drop_cycle.size()]
		var kind: StringName = StringName(drop[&"kind"])
		var crate_type: StringName = StringName(drop[&"crate_type"])
		var row_id := StringName("airdrop_%03d" % airdrop_serial)
		var landing: Vector2 = world.supply_drop_target(spawn_xs[slot])
		# A slower, readable descent gives both players time to decide whether to
		# contest the drop, while the normal pickup row remains collectible.
		pickup_rows.append({&"id": row_id, &"kind": kind, &"crate_type": crate_type, &"x": landing.x, &"y": -72.0, &"target_y": landing.y, &"fall_speed": 3.6, &"active": true, &"airdrop": true, &"landed": false})
		weapon_events.append({&"kind": &"airdrop", &"pickup_id": row_id, &"weapon": kind, &"x": landing.x, &"y": -72.0, &"ttl": 24})
		airdrop_serial += 1
	for row: Dictionary in pickup_rows:
		if not bool(row.get(&"active", false)) or not bool(row.get(&"airdrop", false)) or bool(row.get(&"landed", false)):
			continue
		var next_y: float = minf(float(row.get(&"target_y", world.floor_y)), float(row.get(&"y", -72.0)) + float(row.get(&"fall_speed", 5.5)))
		row[&"y"] = next_y
		if next_y >= float(row.get(&"target_y", world.floor_y)):
			row[&"landed"] = true
			weapon_events.append({&"kind": &"airdrop_land", &"pickup_id": row.get(&"id", &""), &"weapon": row.get(&"kind", &""), &"x": row.get(&"x", 0.0), &"y": next_y, &"ttl": 18})

func _prop_max_health(kind: StringName) -> int:
	if kind == &"crate":
		return 30
	if kind == &"barrel":
		return 20
	if kind == &"glass":
		return 10
	return 20

func _resolve_prop_attack(attacker_index: int, attack: StringName, origin: Vector2, direction: Vector2, range_limit: float, damage: int) -> void:
	var attacker: FighterState = fighters[attacker_index]
	var best_index: int = -1
	var best_forward: float = INF
	for index: int in range(prop_rows.size()):
		var prop: Dictionary = prop_rows[index]
		if not bool(prop.get(&"active", false)):
			continue
		var point := Vector2(float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0)))
		var target_delta: Vector2 = point - origin
		var forward: float = direction.dot(target_delta)
		var lateral: float = absf(direction.cross(target_delta))
		var hit: bool = false
		if attack == &"shoot":
			hit = forward >= 0.0 and forward <= range_limit and lateral <= 24.0
		else:
			var distance_x: float = point.x - attacker.position.x
			var prop_range: float = range_limit + float(tuning[&"char_width"]) * 0.5
			hit = distance_x * attacker.facing > 0.0 and absf(point.y - attacker.position.y) <= float(tuning[&"char_height"]) and absf(distance_x) <= prop_range
			forward = absf(distance_x)
		if hit and forward < best_forward:
			best_forward = forward
			best_index = index
	if best_index >= 0:
		_damage_prop(best_index, damage, attacker.player_id, attack)

func _damage_props_at(center: Vector2, radius: float, damage: int, source: int, cause: StringName) -> void:
	for index: int in range(prop_rows.size()):
		var prop: Dictionary = prop_rows[index]
		if not bool(prop.get(&"active", false)):
			continue
		var point := Vector2(float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0)))
		if point.distance_squared_to(center) <= radius * radius:
			_damage_prop(index, damage, source, cause)

func _damage_prop(index: int, damage: int, source: int, cause: StringName) -> void:
	if index < 0 or index >= prop_rows.size():
		return
	var prop: Dictionary = prop_rows[index]
	if not bool(prop.get(&"active", false)):
		return
	var prop_id: StringName = StringName(prop.get(&"id", &""))
	prop[&"health"] = maxi(0, int(prop.get(&"health", 0)) - maxi(0, damage))
	prop_events.append({&"kind": &"prop_hit", &"prop_id": prop_id, &"source": source, &"cause": cause, &"health": int(prop[&"health"]), &"ttl": 12})
	if int(prop[&"health"]) > 0:
		return
	prop[&"active"] = false
	prop_events.append({&"kind": &"prop_destroyed", &"prop_id": prop_id, &"source": source, &"cause": cause, &"ttl": 18})
	var point := Vector2(float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0)))
	if bool(prop.get(&"explosive", false)):
		var radius: float = 84.0
		explosion_events.append({&"x": point.x, &"y": point.y, &"radius": radius, &"ttl": 10, &"source": &"barrel"})
		_damage_props_at(point, radius, 20, source, &"barrel_chain")
		for target: FighterState in fighters:
			var delta: Vector2 = target.position - point
			if delta.length_squared() <= radius * radius:
				target.apply_hit(20, 20.0 if delta.x >= 0.0 else -20.0, true, &"barrel", tuning)
				_ignite_fighter(target.player_id)

func _ignite_fighter(player_id: int) -> void:
	var index: int = player_id - 1
	if index < 0 or index >= burning_ticks.size():
		return
	if fighters[index].health <= 0:
		return
	if burning_ticks[index] <= 0:
		fire_events.append({&"kind": &"ignite", &"player": player_id, &"ttl": 18})
		burn_elapsed_ticks[index] = 0
	burning_ticks[index] = maxi(burning_ticks[index], int(tuning.get(&"burn_duration_ticks", 90)))

func _step_burning(_frame: InputFrame) -> void:
	for index: int in range(burning_ticks.size()):
		if burning_ticks[index] <= 0:
			continue
		var player_id: int = index + 1
		if fighters[index].health <= 0:
			burning_ticks[index] = 0
			burn_elapsed_ticks[index] = 0
			continue
		if fighters[index].roll_ticks > 0 and fighters[index].grounded:
			burning_ticks[index] = 0
			burn_elapsed_ticks[index] = 0
			fire_events.append({&"kind": &"extinguish", &"player": player_id, &"ttl": 18})
			continue
		burning_ticks[index] = maxi(0, burning_ticks[index] - 1)
		burn_elapsed_ticks[index] += 1
		var interval: int = maxi(1, int(tuning.get(&"burn_interval_ticks", 15)))
		if burn_elapsed_ticks[index] % interval == 0:
			var applied: bool = fighters[index].apply_burn_damage(int(tuning.get(&"burn_damage", 3)), tuning)
			if applied:
				fire_events.append({&"kind": &"burn", &"player": player_id, &"damage": int(tuning.get(&"burn_damage", 3)), &"health": fighters[index].health, &"ttl": 12})
			if fighters[index].health <= 0:
				burning_ticks[index] = 0
				burn_elapsed_ticks[index] = 0
			elif burning_ticks[index] == 0:
				burn_elapsed_ticks[index] = 0

func _collect_pickups(frame: InputFrame) -> void:
	for row: Dictionary in pickup_rows:
		if not bool(row.get(&"active", false)):
			continue
		var pickup_position := Vector2(float(row.get(&"x", 0.0)), float(row.get(&"y", 0.0)))
		for index: int in range(fighters.size()):
			if fighters[index].position.distance_to(pickup_position) > 32.0:
				continue
			var kind: StringName = StringName(row.get(&"kind", &""))
			var pickup_definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(kind)
			var interaction_pickup: bool = pickup_definition != null or kind == &"grenades" or kind == &"bullet_time" or kind == &"bullet_time_5" or kind == &"bullet_time_10"
			if interaction_pickup and not _pickup_interaction_pressed(frame, fighters[index].player_id):
				continue
			if kind == &"pill":
				fighters[index].health = mini(int(tuning[&"max_health"]), fighters[index].health + 25)
			elif kind == &"medkit":
				fighters[index].health = mini(int(tuning[&"max_health"]), fighters[index].health + 50)
			elif kind == &"grenades":
				fighters[index].grenades += 2
				active_weapon_slots[index] = 2
				fighters[index].active_weapon_slot = 2
			elif pickup_definition != null and (pickup_definition.is_melee() or pickup_definition.has_projectile()):
				if pickup_definition.is_melee():
					melee_ids[index] = kind
					fighters[index].ammo = 0
					active_weapon_slots[index] = 0
					fighters[index].active_weapon_slot = 0
				else:
					gun_ids[index] = kind
					fighters[index].ammo = pickup_definition.starting_ammo
					active_weapon_slots[index] = 1
					fighters[index].active_weapon_slot = 1
				if pickup_definition == null:
					continue
			elif kind == &"bullet_time" or kind == &"bullet_time_5" or kind == &"bullet_time_10":
				fighters[index].power_charges = 1
				fighters[index].power_duration_ticks = int(row.get(&"duration_ticks", 300 if kind != &"bullet_time_10" else 600))
				active_weapon_slots[index] = 3
				fighters[index].active_weapon_slot = 3
			else:
				continue
			row[&"active"] = false
			# Down+melee doubles as the Classic pickup gesture.  A grounded
			# fighter may expose the contextual kick pose for that same input, but
			# collecting an item must not consume the next combat window.
			if interaction_pickup and fighters[index].attack_name == &"kick":
				fighters[index].attack_name = &"none"
				fighters[index].attack_timer_ticks = 0
				fighters[index].attack_cooldown_ticks = 0
				fighters[index].queued_attack = &"none"
			break

func _starting_ammo(weapon_id: StringName, fallback: int = 0) -> int:
	var definition: WeaponCatalog.WeaponDefinition = WEAPON_CATALOG_SCRIPT.definition_for(weapon_id)
	if definition == null or not definition.has_ammo():
		return fallback
	return maxi(0, definition.starting_ammo)

func _pickup_interaction_pressed(frame: InputFrame, player: int) -> bool:
	var down_held: bool = false
	var punch_pressed: bool = false
	for record: Dictionary in frame.records():
		if int(record.get(&"player", 0)) != player:
			continue
		var action: StringName = StringName(record.get(&"action", &""))
		if action == StringName("p%d_down" % player):
			down_held = bool(record.get(&"held", false))
		elif action == StringName("p%d_punch" % player):
			punch_pressed = bool(record.get(&"pressed", false))
	return down_held and punch_pressed

func _copy_rows(source: Array[Dictionary]) -> Array[Dictionary]:
	var copied: Array[Dictionary] = []
	for row: Dictionary in source:
		var copy: Dictionary = row.duplicate(true)
		copy.make_read_only()
		copied.append(copy)
	copied.make_read_only()
	return copied

func _reset_active_rows(source: Array[Dictionary]) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for row: Dictionary in source:
		if bool(row.get(&"airdrop", false)):
			continue
		var copy: Dictionary = row.duplicate(true)
		copy[&"active"] = true
		result.append(copy)
	return result

func _reset_prop_rows(source: Array[Dictionary]) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for row: Dictionary in source:
		var copy: Dictionary = row.duplicate(true)
		copy[&"active"] = true
		copy[&"health"] = int(copy.get(&"max_health", _prop_max_health(StringName(copy.get(&"kind", &"prop")))))
		result.append(copy)
	return result

func _check_result() -> void:
	if phase != &"playing":
		return
	var p1_dead: bool = fighters[0].health <= 0
	var p2_dead: bool = fighters[1].health <= 0
	if not p1_dead and not p2_dead:
		return
	_end_bullet_time()
	winner = 0 if p1_dead and p2_dead else 2 if p1_dead else 1
	if not mode_rules.record_round(winner):
		phase = &"invalid"
		error = &"mode_round_rejected"
		return
	phase = &"round_result" if mode_rules.phase == &"round_result" else &"result"

func _configure_bullet_time_tempo() -> void:
	for index: int in range(fighters.size()):
		var active: bool = bullet_time_owner == index and bullet_time_ticks > 0
		fighters[index].bullet_time_active = active
		fighters[index].set_tempo_divisor(1 if bullet_time_owner < 0 or active else 2)

func _end_bullet_time() -> void:
	bullet_time_owner = -1
	bullet_time_ticks = 0
	bullet_time_duration_ticks = 0
	for fighter: FighterState in fighters:
		fighter.bullet_time_active = false
		fighter.set_tempo_divisor(1)
		fighter.tempo_pending_actions.clear()
