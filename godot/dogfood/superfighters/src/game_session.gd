class_name GameSession
extends Node2D

const _Traversal: GDScript = preload("res://src/sim/traversal.gd")
const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _Aim: GDScript = preload("res://src/sim/aim.gd")
const _Expl: GDScript = preload("res://src/sim/explosive.gd")
const _Inv: GDScript = preload("res://src/data/weapons/inventory.gd")
const _Bal: GDScript = preload("res://src/sim/balance.gd")
const _WorldOwner: GDScript = preload("res://src/world/world_owner.gd")

signal won
signal lost

var mode: String = "vs1"
var map_id: String = "rooftops"
var stage_index: int = 0
var outcome: String = "play"
var fighters: Array[Fighter] = []
var pickups: Array[Pickup] = []
var bullets: Array[Bullet] = []
var grenades: Array[ThrownGrenade] = []
var brains: Array[BotBrain] = []
var respawns: Array[Dictionary] = []
var arena: Arena
var world: Node2D
var world_owner: RefCounted
var hud: Hud
var pause_screen: PauseScreen
var sfx: SfxBank
var camera: Camera2D
var test_driven: bool = false
var rng: RandomNumberGenerator = RandomNumberGenerator.new()
var chaos_rng: RandomNumberGenerator = RandomNumberGenerator.new()
var chaos_enabled: bool = false
var win_title: String = "Last standing"
var lose_title: String = "Down"
var _fx: Array[Sprite2D] = []
var _fx_life: Array[float] = []
var _shut_down: bool = false
var _resume_cb: Callable = Callable()
var clock: SimClock = SimClock.new()
var sim_seed: int = 0
var last_reject: PackedStringArray = PackedStringArray()
var ledger: SimEventLedger = SimEventLedger.new()
var recorder: SimRecorder = null
var pause_reason: String = ""
var pickup_seq: int = 0
var last_hit_raw: float = 0.0
var last_hit_applied: float = 0.0
var last_hit_path: String = ""
var last_hit_weapon: String = ""
var last_fire_weapon: String = ""
var last_fire_raw_spawn: float = 0.0


func setup(p_mode: String, p_map: String, p_stage: int) -> void:
	name = "GameSession"
	process_mode = Node.PROCESS_MODE_PAUSABLE
	mode = p_mode
	map_id = p_map
	stage_index = p_stage
	outcome = "play"
	sim_seed = SimSeed.for_match(p_mode, p_map, p_stage)
	rng.seed = sim_seed
	chaos_enabled = not test_driven
	reset_chaos_rng()
	clock.reset()
	pause_reason = ""
	last_reject = PackedStringArray()
	ledger = SimEventLedger.new()
	pickup_seq = 0
	arena = Arena.new()
	world = arena.build(map_id)
	add_child(world)
	world_owner = _WorldOwner.new()
	world_owner.call("bind", self)
	world_owner.call("attach", world)
	# world_owner.spawn_map — catalog placements, no per-node GameSession hard-code
	world_owner.call("spawn_map", map_id)
	_spawn_fighters()
	_spawn_weapons()
	hud = Hud.new()
	add_child(hud)
	hud.set_map_name(Maps.display_name(map_id))
	hud.set_hint("Last standing · sprint+crouch dive in air · aerial melee kicks · hold M fire")
	pause_screen = PauseScreen.new()
	_resume_cb = set_paused.bind(false)
	pause_screen.resume_pressed.connect(_resume_cb)
	add_child(pause_screen)
	sfx = SfxBank.new()
	sfx.muted = test_driven
	add_child(sfx)
	if not test_driven:
		sfx.start_music()
	camera = Camera2D.new()
	camera.name = "ArenaCam"
	add_child(camera)
	_fit_camera()
	InputActions.reset_edges()
	hud.refresh(fighters)


func _physics_process(delta: float) -> void:
	if test_driven:
		return
	if _is_sim_paused():
		return
	if outcome != "play":
		return
	var steps: int = clock.feed(delta)
	var s: int = 0
	while s < steps:
		if recorder != null and recorder.active:
			if not recorder.step_session(self):
				break
		else:
			_step_one_tick(_gather_live_cmds())
		s += 1


func step_fixed(_delta: float, cmds: Array[Dictionary]) -> void:
	if _is_sim_paused():
		return
	_step_one_tick(cmds)


func step_from_live_input() -> bool:
	if _is_sim_paused():
		last_reject = PackedStringArray(["paused"])
		return false
	var frames: Array = []
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		if f.is_bot:
			if i >= brains.size():
				brains.append(BotBrain.new())
			frames.append(InputActions.frame_from_cmd(
				brains[i].think(f, fighters, pickups, SimConstants.TICK_DT),
				clock.tick,
				f.slot
			))
		else:
			frames.append(InputActions.read_player_frame(f.slot, clock.tick))
		i += 1
	return apply_frames(frames)


func reset_chaos_rng() -> void:
	var mixed: int = sim_seed + _Bal.chaos_salt()
	if mixed < 0:
		mixed = 0
	chaos_rng.seed = mixed


func enable_chaos() -> void:
	chaos_enabled = true
	reset_chaos_rng()


func apply_frames(frames: Array) -> bool:
	last_reject = PackedStringArray()
	if _is_sim_paused():
		last_reject.append("paused")
		return false
	var errors: PackedStringArray = SimValidator.validate_bundle(frames, clock.tick, fighters.size())
	if not errors.is_empty():
		last_reject = errors
		ledger.push(clock.tick, "input_validate", "reject", {
			"count": errors.size(),
		})
		return false
	var cmds: Array[Dictionary] = []
	var i: int = 0
	while i < frames.size():
		cmds.append(InputActions.cmd_from_variant(frames[i]))
		i += 1
	_step_one_tick(cmds)
	return true


func _is_sim_paused() -> bool:
	if clock != null and clock.paused:
		return true
	var tree: SceneTree = get_tree()
	return tree != null and tree.paused


func _gather_live_cmds() -> Array[Dictionary]:
	var cmds: Array[Dictionary] = []
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		if f.is_bot:
			if i >= brains.size():
				brains.append(BotBrain.new())
			cmds.append(brains[i].think(f, fighters, pickups, SimConstants.TICK_DT))
		elif f.slot == 0:
			cmds.append(InputActions.cmd_from_frame(InputActions.read_player_frame(0, clock.tick)))
		elif f.slot == 1 and f.is_human:
			cmds.append(InputActions.cmd_from_frame(InputActions.read_player_frame(1, clock.tick)))
		else:
			cmds.append(InputActions.empty_cmd())
		i += 1
	return cmds


func _step_one_tick(cmds: Array[Dictionary]) -> void:
	var dt: float = SimConstants.TICK_DT
	_tick_fx(dt)
	if outcome != "play":
		return
	var r: int = 0
	while r < fighters.size():
		fighters[r].damage_taken_tick = 0.0
		fighters[r].last_crit = false
		r += 1
	var kill_plane: float = Maps.kill_y(map_id)
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		var cmd: Dictionary = InputActions.empty_cmd()
		if i < cmds.size():
			cmd = cmds[i]
		var sample: Dictionary = _Traversal.sample(arena, f)
		cmd["on_ladder"] = bool(sample.get("on_ladder", false))
		cmd["ladder_snap_x"] = float(sample.get("snap_x", f.global_position.x))
		cmd["climb_up_blocked"] = bool(sample.get("climb_up_blocked", false))
		cmd["climb_down_blocked"] = bool(sample.get("climb_down_blocked", false))
		cmd["one_way_under"] = bool(sample.get("one_way_under", false))
		cmd["ledge"] = sample.get("ledge", {})
		var before_y: float = f.velocity.y
		f.step(dt, cmd, kill_plane)
		_emit_loco_feedback(f)
		_log_death_if_new(f)
		if f.last_jump and before_y >= 0.0 and f.velocity.y < 0.0 and sfx != null:
			sfx.play("jump")
		if f.want_melee:
			_try_start_melee(f)
		i += 1
	i = 0
	while i < fighters.size():
		var actor: Fighter = fighters[i]
		_resolve_attack(actor)
		if actor.diving and not actor.dive_did_tackle:
			_try_dive_tackle(actor)
		if actor.want_fire:
			_do_fire(actor)
		if actor.want_grenade:
			_do_grenade(actor)
		i += 1
	i = 0
	while i < fighters.size():
		_emit_reaction_feedback(fighters[i])
		fighters[i].clear_reaction_pulse()
		i += 1
	_step_respawns(dt)
	_step_bullets(dt)
	_step_grenades(dt)
	_resolve_end()
	clock.advance()
	if hud != null:
		hud.refresh(fighters)
	_fit_camera()


func set_paused(active: bool, reason: String = "") -> void:
	if outcome != "play" and active:
		return
	if active:
		clock.pause()
		if reason != "":
			pause_reason = reason
		elif pause_reason == "":
			pause_reason = RuntimeConstants.REASON_PLAYER
	else:
		clock.resume()
		pause_reason = ""
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	tree.paused = active
	if sfx != null:
		sfx.duck(active)
	if pause_screen == null:
		return
	if active:
		pause_screen.show_pause()
	else:
		pause_screen.hide_pause()


func snapshot() -> Dictionary:
	return SimSnapshot.from_session(self)


func snapshot_hash() -> String:
	return SimSnapshot.stable_hash(snapshot())


func fighter_at_slot(slot: int) -> Fighter:
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		if f != null and f.slot == slot:
			return f
		i += 1
	return null


func replace_pickups(rows: Array) -> void:
	var i: int = 0
	while i < pickups.size():
		_free_node(pickups[i])
		i += 1
	pickups.clear()
	i = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		var at: Vector2 = Vector2(
			SimConstants.dequantize(int(row.get("x", 0))),
			SimConstants.dequantize(int(row.get("y", 0)))
		)
		var drop: Pickup = _add_pickup(str(row.get("id", "pistol")), at, bool(row.get("from_world", true)))
		if row.has("uid"):
			drop.drop_uid = int(row.get("uid", drop.drop_uid))
			if drop.drop_uid > pickup_seq:
				pickup_seq = drop.drop_uid
		drop.global_position = at
		if row.has("home_x") or row.has("home_y"):
			drop.home = Vector2(
				SimConstants.dequantize(int(row.get("home_x", 0))),
				SimConstants.dequantize(int(row.get("home_y", 0)))
			)
		i += 1


func replace_bullets(rows: Array) -> void:
	var i: int = 0
	while i < bullets.size():
		_free_node(bullets[i])
		i += 1
	bullets.clear()
	i = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		var shot: Bullet = Bullet.new()
		var at: Vector2 = Vector2(
			SimConstants.dequantize(int(row.get("x", 0))),
			SimConstants.dequantize(int(row.get("y", 0)))
		)
		var vel: Vector2 = Vector2(
			SimConstants.dequantize(int(row.get("vx", 0))),
			SimConstants.dequantize(int(row.get("vy", 0)))
		)
		shot.setup(
			at,
			Vector2.RIGHT,
			1.0,
			SimConstants.dequantize(int(row.get("damage", SimConstants.quantize(10.0)))),
			int(row.get("owner", -1)),
			int(row.get("team", -1))
		)
		add_child(shot)
		shot.global_position = at
		shot.last_pos = at
		shot.velocity = vel
		if row.has("life"):
			shot.life = SimConstants.dequantize(int(row.get("life", 0)))
		bullets.append(shot)
		i += 1


func replace_grenades(rows: Array) -> void:
	var i: int = 0
	while i < grenades.size():
		_free_node(grenades[i])
		i += 1
	grenades.clear()
	i = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		var nade: ThrownGrenade = ThrownGrenade.new()
		var at: Vector2 = Vector2(
			SimConstants.dequantize(int(row.get("x", 0))),
			SimConstants.dequantize(int(row.get("y", 0)))
		)
		nade.setup(at, Vector2.RIGHT, int(row.get("owner", -1)), int(row.get("team", -1)))
		add_child(nade)
		nade.global_position = at
		nade.velocity = Vector2(
			SimConstants.dequantize(int(row.get("vx", 0))),
			SimConstants.dequantize(int(row.get("vy", 0)))
		)
		if row.has("fuse_ticks"):
			nade.fuse_ticks = maxi(int(row.get("fuse_ticks", nade.fuse_ticks)), 0)
			nade.fuse = float(nade.fuse_ticks) * SimConstants.TICK_DT
		elif row.has("fuse"):
			nade.fuse = SimConstants.dequantize(int(row.get("fuse", 0)))
			nade.fuse_ticks = maxi(int(round(nade.fuse / SimConstants.TICK_DT)), 0)
		if row.has("life_ticks"):
			nade.life_ticks = maxi(int(row.get("life_ticks", nade.life_ticks)), 0)
		if row.has("damage"):
			nade.damage = SimConstants.dequantize(int(row.get("damage", 0)))
		if row.has("radius"):
			nade.radius = SimConstants.dequantize(int(row.get("radius", 0)))
		if row.has("bounce_count"):
			nade.bounce_count = maxi(int(row.get("bounce_count", 0)), 0)
		nade.exploded = bool(row.get("exploded", false))
		nade.applied = bool(row.get("applied", false))
		nade.last_pos = at
		grenades.append(nade)
		i += 1


func replace_respawns(rows: Array) -> void:
	respawns.clear()
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		respawns.append({
			"id": str(row.get("id", "pistol")),
			"pos": Vector2(
				SimConstants.dequantize(int(row.get("x", 0))),
				SimConstants.dequantize(int(row.get("y", 0)))
			),
			"t": SimConstants.dequantize(int(row.get("t", 0))),
		})
		i += 1


func player1() -> Fighter:
	if fighters.is_empty():
		return null
	return fighters[0]


func force_kill(slot: int) -> void:
	ledger.push(clock.tick, "fixture", "force_kill", {"slot": slot})
	var i: int = 0
	while i < fighters.size():
		if fighters[i].slot == slot:
			fighters[i].kill()
			_log_death_if_new(fighters[i])
		i += 1
	_resolve_end()


func _spawn_fighters() -> void:
	var p1: Fighter = Fighter.new()
	p1.setup(0, 0, false)
	p1.global_position = _spawn_at(0) + Vector2(0, -8)
	p1.facing = 1.0
	add_child(p1)
	fighters.append(p1)
	brains.append(BotBrain.new())
	if mode == "vs2":
		var p2: Fighter = Fighter.new()
		p2.setup(1, 1, false)
		p2.global_position = _spawn_at(1) + Vector2(0, -8)
		p2.facing = -1.0
		add_child(p2)
		fighters.append(p2)
		brains.append(BotBrain.new())
		return
	var bots: int = 2
	if mode == "stage":
		bots = 1 + mini(stage_index, 2)
	var b: int = 0
	while b < bots:
		var bot: Fighter = Fighter.new()
		var team: int = 1 + (b % 3)
		bot.setup(b + 1, team, true)
		bot.global_position = _spawn_at(b + 1) + Vector2(0, -8)
		bot.facing = -1.0
		add_child(bot)
		fighters.append(bot)
		brains.append(BotBrain.new())
		b += 1


func _spawn_at(index: int) -> Vector2:
	var spawns: Array[Vector2] = arena.player_spawns
	if index < spawns.size():
		return spawns[index]
	if spawns.is_empty():
		return Vector2(120, 80)
	return spawns[spawns.size() - 1] + Vector2(float(index) * 24.0, 0)


func _spawn_weapons() -> void:
	var spots: Array[Vector2] = arena.weapon_spawns
	var i: int = 0
	while i < spots.size():
		var pid: String = WeaponDefs.random_id(rng)
		_add_pickup(pid, spots[i] + Vector2(0, 2), true)
		i += 1


func _add_pickup(pid: String, at: Vector2, from_world: bool) -> Pickup:
	pickup_seq += 1
	var drop: Pickup = Pickup.new()
	drop.setup(pid, at, pickup_seq)
	drop.from_world = from_world
	drop.home = at
	world.add_child(drop)
	pickups.append(drop)
	return drop


func _try_start_melee(f: Fighter) -> void:
	if f.crouched:
		if _try_pickup(f):
			return
	if f.attack_phase != "idle":
		return
	var style: String = "crouch" if f.crouched else "melee"
	f.begin_attack(style)


func _resolve_attack(f: Fighter) -> void:
	if f.attack_started:
		var kind: String = "startup"
		if f.attack_style == "kick":
			kind = "kick_start"
			if sfx != null:
				sfx.play("kick")
		else:
			if sfx != null:
				sfx.play("punch")
			_spawn_melee_fx(f)
		ledger.push(clock.tick, "melee", kind, {
			"attacker": f.slot,
			"style": f.attack_style,
			"weapon": f.attack_weapon,
			"seq": f.attack_seq,
			"seed": sim_seed,
		})
	if f.attack_active_entered:
		ledger.push(clock.tick, "melee", "active", {
			"attacker": f.slot,
			"style": f.attack_style,
			"weapon": f.attack_weapon,
			"seq": f.attack_seq,
			"seed": sim_seed,
		})
	if f.attack_phase == "active":
		_resolve_hitbox(f)
	if f.attack_recovery_entered:
		ledger.push(clock.tick, "melee", "recovery", {
			"attacker": f.slot,
			"style": f.attack_style,
			"weapon": f.attack_weapon,
			"seq": f.attack_seq,
			"seed": sim_seed,
		})
	if f.attack_missed:
		ledger.push(clock.tick, "melee", "miss", {
			"attacker": f.slot,
			"style": f.attack_style,
			"weapon": f.attack_weapon,
			"seq": f.attack_seq,
			"seed": sim_seed,
		})


func _resolve_hitbox(f: Fighter) -> void:
	var box: Rect2 = _Combat.hitbox_rect(f)
	var i: int = 0
	while i < fighters.size():
		var other: Fighter = fighters[i]
		i += 1
		if other == f or other.dead:
			continue
		if f.already_hit(other.slot):
			continue
		if not _Combat.allows_hit(mode, f, other):
			if other.team == f.team:
				ledger.push(clock.tick, "melee", "friendly_block", {
					"attacker": f.slot,
					"target": other.slot,
					"mode": mode,
					"seed": sim_seed,
				})
				f.mark_hit(other.slot)
			continue
		if not _Combat.overlaps(box, _Combat.hurtbox_rect(other)):
			continue
		if other.invuln_ticks > 0 or other.invuln > 0.0:
			continue
		var dmg: float = _Combat.damage_of(f.attack_weapon, f.attack_style)
		var knock: Vector2 = _Combat.knock_of(f.attack_style, f.facing)
		var rolled: Dictionary = _Bal.roll_hit(chaos_rng, chaos_enabled, dmg, knock)
		var raw: float = float(rolled.get("raw", dmg))
		dmg = float(rolled.get("damage", dmg))
		knock = rolled.get("knock", knock) as Vector2
		other.last_crit = bool(rolled.get("crit", false))
		var hp0: float = other.health
		other.take_damage(raw, knock)
		_record_hit_cap(other, raw, hp0, "melee", f.attack_weapon)
		var landed: bool = other.health < hp0 - 0.01 or other.dead
		if landed and _Combat.style_knocks_down(f.attack_style):
			if other.apply_knockdown(Vector2(f.facing * 70.0, 20.0)):
				ledger.push(clock.tick, "melee", "knockdown", {
					"attacker": f.slot,
					"target": other.slot,
					"source": f.attack_style,
					"seed": sim_seed,
				})
			else:
				ledger.push(clock.tick, "melee", "knockdown_block", {
					"attacker": f.slot,
					"target": other.slot,
					"source": f.attack_style,
					"seed": sim_seed,
				})
		if landed and _Combat.style_disarms(f.attack_style):
			var dropped: String = other.disarm_gun()
			if dropped != "":
				_drop_disarmed(other, dropped)
		f.mark_hit(other.slot)
		f.hitstop_left = maxi(f.hitstop_left, _Combat.hitstop_ticks())
		other.hitstop_left = maxi(other.hitstop_left, _Combat.hitstop_ticks())
		var kind: String = "kick_hit" if f.attack_style == "kick" else "hit"
		ledger.push(clock.tick, "melee", kind, {
			"attacker": f.slot,
			"target": other.slot,
			"style": f.attack_style,
			"weapon": f.attack_weapon,
			"damage": SimConstants.quantize(dmg),
			"knock_x": SimConstants.quantize(knock.x),
			"knock_y": SimConstants.quantize(knock.y),
			"crit": 1 if other.last_crit else 0,
			"seq": f.attack_seq,
			"seed": sim_seed,
		})
		if other.last_crit:
			ledger.push(clock.tick, "combat", "crit", {
				"attacker": f.slot,
				"target": other.slot,
				"weapon": f.attack_weapon,
				"seed": sim_seed,
			})
		_log_death_if_new(other)
		_splat(other.global_position)
		if sfx != null:
			sfx.play("hit")


func _spawn_melee_fx(f: Fighter) -> void:
	var box: Rect2 = _Combat.hitbox_rect(f)
	_attach_fx_sprite(Visuals.melee_flash_tex(), box.get_center(), 0.10)


func _try_dive_tackle(f: Fighter) -> void:
	if f == null or not f.diving or f.dead:
		return
	var i: int = 0
	while i < fighters.size():
		var other: Fighter = fighters[i]
		i += 1
		if other == f or other.dead:
			continue
		var delta: Vector2 = other.global_position - f.global_position
		if absf(delta.y) > 20.0:
			continue
		if absf(delta.x) > 22.0:
			continue
		other.take_damage(f.dive_tackle_damage, Vector2(f.facing * 120.0, 30.0))
		other.apply_knockdown(Vector2(f.facing * 80.0, 24.0))
		ledger.push(clock.tick, "locomotion", "dive_tackle", {
			"attacker": f.slot,
			"target": other.slot,
			"seq": f.dive_seq,
			"damage": SimConstants.quantize(f.dive_tackle_damage),
		})
		ledger.push(clock.tick, "melee", "knockdown", {
			"attacker": f.slot,
			"target": other.slot,
			"source": "dive",
		})
		_log_death_if_new(other)
		_splat(other.global_position)
		if sfx != null:
			sfx.play("hit")
		f.dive_did_tackle = true
		return


func _try_pickup(f: Fighter) -> bool:
	if not f.crouched:
		return false
	var best_i: int = -1
	var best_d: float = 28.0001
	var i: int = 0
	while i < pickups.size():
		var drop: Pickup = pickups[i]
		if drop != null and is_instance_valid(drop):
			var dist: float = f.global_position.distance_to(drop.global_position)
			if dist <= 28.0 and dist < best_d:
				best_d = dist
				best_i = i
		i += 1
	if best_i < 0:
		return false
	var chosen: Pickup = pickups[best_i]
	var dropped: String = _Inv.dropped_on_pickup(f, chosen.weapon_id)
	if dropped != "":
		_drop_specific(dropped, f.global_position + Vector2(0, 8), false)
	if chosen.from_world:
		respawns.append({
			"id": chosen.weapon_id,
			"pos": chosen.home,
			"t": Maps.WEAPON_RESPAWN,
		})
	var picked: String = chosen.weapon_id
	var uid: int = chosen.drop_uid
	f.give_weapon(picked)
	ledger.push(clock.tick, "melee", "item_pickup", {
		"slot": f.slot,
		"id": picked,
		"uid": uid,
		"seed": sim_seed,
	})
	if sfx != null:
		sfx.play("pickup")
	chosen.queue_free()
	pickups.remove_at(best_i)
	return true


func _drop_specific(pid: String, at: Vector2, from_world: bool) -> Pickup:
	if pid == "":
		return null
	return _add_pickup(pid, at, from_world)


func drop_held_slot(f: Fighter, slot: String) -> Pickup:
	if f == null:
		return null
	var dropped: String = _Inv.eject_slot(f, slot)
	if dropped == "":
		return null
	return _drop_specific(dropped, f.global_position + Vector2(0, 8), false)


func _drop_disarmed(f: Fighter, pid: String) -> void:
	if pid == "" or pid == "fists":
		return
	var at: Vector2 = f.global_position + Vector2(0.0, 8.0)
	var drop: Pickup = _add_pickup(pid, at, false)
	ledger.push(clock.tick, "melee", "disarm", {
		"slot": f.slot,
		"item": pid,
		"uid": drop.drop_uid,
		"seed": sim_seed,
	})
	ledger.push(clock.tick, "melee", "item_drop", {
		"id": pid,
		"uid": drop.drop_uid,
		"x": SimConstants.quantize(at.x),
		"y": SimConstants.quantize(at.y),
		"source": "disarm",
		"seed": sim_seed,
	})


func _do_fire(f: Fighter) -> void:
	var spec: Dictionary = WeaponDefs.data(f.gun_id)
	if str(spec.get("kind", "")) != "gun" or f.ammo <= 0:
		return
	var cadence: int = _Aim.cadence_ticks(f.gun_id)
	f.fire_cd = float(cadence) * SimConstants.TICK_DT
	var pellets: int = _Aim.pellets(f.gun_id)
	var spread: float = _Aim.spread(f.gun_id)
	var speed: float = _Aim.speed(f.gun_id)
	var dmg: float = _Aim.damage(f.gun_id)
	last_fire_weapon = f.gun_id
	last_fire_raw_spawn = dmg
	var base: Vector2 = f.aim_dir
	if base == Vector2.ZERO:
		base = Vector2(f.facing, 0.0)
	base = base.normalized()
	var posed: Vector2 = _Aim.muzzle_origin(f)
	var muzzle: Vector2 = _uncollide_point(posed, base)
	f.last_muzzle = posed
	f.last_fire_dir = base
	f.last_fire_gun = f.gun_id
	f.shots_fired += 1
	var recoil: float = _Aim.recoil_of(f.gun_id)
	if recoil > 0.0:
		f.velocity += -base * recoil
	var p: int = 0
	while p < pellets:
		var dir: Vector2 = _Aim.pellet_dir(base, p, pellets, spread)
		dir = _Bal.jitter_dir(chaos_rng, dir, spread, chaos_enabled)
		var shot: Bullet = Bullet.new()
		shot.setup(muzzle, dir, speed, dmg, f.slot, f.team)
		add_child(shot)
		bullets.append(shot)
		p += 1
	f.consume_ammo()
	ledger.push(clock.tick, "fire_spawn", "bullet", {
		"owner": f.slot,
		"gun": f.gun_id,
		"ammo": f.ammo,
		"pellets": pellets,
		"mode": _Aim.fire_mode(f.gun_id),
		"dir_x": SimConstants.quantize(base.x),
		"dir_y": SimConstants.quantize(base.y),
		"muzzle_x": SimConstants.quantize(muzzle.x),
		"muzzle_y": SimConstants.quantize(muzzle.y),
		"recoil": SimConstants.quantize(recoil),
	})
	if sfx != null:
		if f.gun_id == "shotgun":
			sfx.play("shotgun")
		else:
			sfx.play("shoot")
	_muzzle(muzzle)


func _do_grenade(f: Fighter) -> void:
	var payload_id: String = ""
	if f.grenades > 0:
		f.consume_grenade()
		payload_id = f.explosive_id if f.explosive_id != "" else "grenade"
	elif _Inv.power_throw_ready(f):
		payload_id = f.power_id
		f.consume_power()
	else:
		return
	var dir: Vector2 = _Expl.throw_dir(f)
	var posed: Vector2 = _Expl.throw_origin(f)
	var origin: Vector2 = _uncollide_point(posed, dir)
	var nade: ThrownGrenade = ThrownGrenade.new()
	nade.setup(origin, dir, f.slot, f.team, payload_id)
	add_child(nade)
	grenades.append(nade)
	ledger.push(clock.tick, "grenade_spawn", "nade", {
		"owner": f.slot,
		"team": f.team,
		"nades": f.grenades,
		"power": f.power_id,
		"payload": payload_id,
		"dir_x": SimConstants.quantize(dir.x),
		"dir_y": SimConstants.quantize(dir.y),
		"x": SimConstants.quantize(origin.x),
		"y": SimConstants.quantize(origin.y),
		"fuse_ticks": nade.fuse_ticks,
	})


func _step_respawns(delta: float) -> void:
	var i: int = 0
	while i < respawns.size():
		var rec: Dictionary = respawns[i]
		rec["t"] = float(rec.get("t", 0.0)) - delta
		respawns[i] = rec
		if float(rec["t"]) <= 0.0:
			_add_pickup(str(rec.get("id", "pistol")), rec["pos"] as Vector2, true)
			respawns.remove_at(i)
			continue
		i += 1


func _step_bullets(delta: float) -> void:
	var i: int = 0
	while i < bullets.size():
		var shot: Bullet = bullets[i]
		if shot == null or not is_instance_valid(shot) or shot.spent:
			if shot != null and is_instance_valid(shot):
				shot.queue_free()
			bullets.remove_at(i)
			continue
		var from: Vector2 = shot.global_position
		var to: Vector2 = shot.predicted_pos(delta)
		var sweep: Dictionary = _sweep_bullet(shot, from, to)
		var kind: String = str(sweep.get("kind", ""))
		if kind == "world" or kind == "fighter":
			shot.commit_step(sweep.get("point", from) as Vector2, delta)
			shot.spent = true
			if kind == "fighter":
				_apply_bullet_hit(shot, sweep.get("fighter") as Fighter)
			shot.queue_free()
			bullets.remove_at(i)
			continue
		shot.commit_step(to, delta)
		if shot.spent:
			shot.queue_free()
			bullets.remove_at(i)
			continue
		i += 1


func _sweep_bullet(shot: Bullet, from: Vector2, to: Vector2) -> Dictionary:
	var best: Dictionary = {"kind": "", "t": 2.0, "point": to, "fighter": null}
	var travel: float = from.distance_to(to)
	if travel <= SimConstants.EPSILON:
		return best
	var space: PhysicsDirectSpaceState2D = get_world_2d().direct_space_state
	if space != null:
		var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(from, to)
		query.collision_mask = Maps.COL_WORLD | Maps.COL_PROP
		query.collide_with_bodies = true
		query.collide_with_areas = true
		query.hit_from_inside = false
		query.exclude = [shot.get_rid()]
		var hit: Dictionary = space.intersect_ray(query)
		if not hit.is_empty():
			var at: Vector2 = hit.get("position", to) as Vector2
			var t_wall: float = from.distance_to(at) / travel
			best = {"kind": "world", "t": t_wall, "point": at, "fighter": null}
	var grid_hit: Dictionary = _grid_block_t(from, to)
	if str(grid_hit.get("kind", "")) == "world" and float(grid_hit.get("t", 2.0)) < float(best.get("t", 2.0)):
		best = grid_hit
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		i += 1
		if f == null or f.dead or f.slot == shot.owner_slot:
			continue
		var t_f: float = _segment_fighter_t(from, to, f)
		if t_f < 0.0:
			continue
		if t_f < float(best.get("t", 2.0)):
			var at_f: Vector2 = from.lerp(to, t_f)
			best = {"kind": "fighter", "t": t_f, "point": at_f, "fighter": f}
	return best


func _uncollide_point(from: Vector2, dir: Vector2) -> Vector2:
	# Muzzle pose can clip the floor tile the shooter stands on.
	# Lift, then step back along -aim, so spawn-overlap is not a
	# world hit. High-speed entry into a new solid still counts.
	var at: Vector2 = from
	var n: int = 0
	while n < 12 and Maps.solid_at(map_id, at):
		at.y -= 1.0
		n += 1
	if not Maps.solid_at(map_id, at):
		return at
	var back: Vector2 = -dir
	if back == Vector2.ZERO:
		back = Vector2.UP
	back = back.normalized()
	at = from
	n = 0
	while n < 16 and Maps.solid_at(map_id, at):
		at += back
		n += 1
	return at


func _grid_block_t(from: Vector2, to: Vector2) -> Dictionary:
	var delta: Vector2 = to - from
	var dist: float = delta.length()
	if dist <= SimConstants.EPSILON:
		return {"kind": "", "t": 2.0, "point": to, "fighter": null}
	var step: float = 2.0 / dist
	var t: float = 0.0
	var prev_solid: bool = Maps.solid_at(map_id, from)
	while t <= 1.0001:
		var at: Vector2 = from.lerp(to, clampf(t, 0.0, 1.0))
		var now_solid: bool = Maps.solid_at(map_id, at)
		if now_solid and not prev_solid:
			return {"kind": "world", "t": clampf(t, 0.0, 1.0), "point": at, "fighter": null}
		prev_solid = now_solid
		t += step
	return {"kind": "", "t": 2.0, "point": to, "fighter": null}


func _segment_fighter_t(from: Vector2, to: Vector2, f: Fighter) -> float:
	var target: Vector2 = f.global_position
	var delta: Vector2 = to - from
	var len2: float = delta.length_squared()
	var t: float = 0.0
	if len2 > SimConstants.EPSILON:
		t = clampf((target - from).dot(delta) / len2, 0.0, 1.0)
	var closest: Vector2 = from.lerp(to, t)
	if closest.distance_to(target) > 10.0:
		return -1.0
	return t


func _apply_bullet_hit(shot: Bullet, f: Fighter) -> void:
	if f == null or f.dead:
		return
	if f.invuln_ticks > 0 or f.invuln > 0.0:
		return
	var knock: Vector2 = shot.velocity.normalized() * 70.0 + Vector2(0, -30)
	var rolled: Dictionary = _Bal.roll_hit(chaos_rng, chaos_enabled, shot.damage, knock)
	var raw: float = float(rolled.get("raw", shot.damage))
	f.last_crit = bool(rolled.get("crit", false))
	var hp0: float = f.health
	f.take_damage(raw, rolled.get("knock", knock) as Vector2)
	_record_hit_cap(f, raw, hp0, "bullet", last_fire_weapon)
	if f.last_crit:
		ledger.push(clock.tick, "combat", "crit", {
			"attacker": shot.owner_slot,
			"target": f.slot,
			"weapon": "bullet",
			"seed": sim_seed,
		})
	_log_death_if_new(f)
	_splat(f.global_position)
	if sfx != null:
		sfx.play("hit")


func _bullet_blocked(shot: Bullet) -> bool:
	var sweep: Dictionary = _sweep_bullet(shot, shot.last_pos, shot.global_position)
	return str(sweep.get("kind", "")) == "world"


func _bullet_hit_fighter(shot: Bullet) -> bool:
	var sweep: Dictionary = _sweep_bullet(shot, shot.last_pos, shot.global_position)
	if str(sweep.get("kind", "")) != "fighter":
		return false
	_apply_bullet_hit(shot, sweep.get("fighter") as Fighter)
	return true


func _step_grenades(delta: float) -> void:
	var i: int = 0
	while i < grenades.size():
		var nade: ThrownGrenade = grenades[i]
		if nade == null or not is_instance_valid(nade):
			grenades.remove_at(i)
			continue
		if nade.applied:
			nade.queue_free()
			grenades.remove_at(i)
			continue
		_advance_nade(nade, delta)
		if nade.exploded:
			_explode(nade)
			nade.queue_free()
			grenades.remove_at(i)
			continue
		i += 1


func _advance_nade(nade: ThrownGrenade, delta: float) -> void:
	var from: Vector2 = nade.global_position
	var to: Vector2 = nade.predicted_pos(delta)
	var next_vel: Vector2 = nade.predicted_vel(delta)
	var sweep: Dictionary = _sweep_nade(nade, from, to)
	if str(sweep.get("kind", "")) == "world":
		var hit: Vector2 = sweep.get("point", from) as Vector2
		var travel: Vector2 = to - from
		if travel.length() > SimConstants.EPSILON:
			hit = hit - travel.normalized() * 1.5
		var bounced: Vector2 = _nade_bounce(nade, next_vel, hit)
		nade.commit_step(hit, bounced, delta)
		nade.bounce_count += 1
		return
	nade.commit_step(to, next_vel, delta)


func _sweep_nade(nade: ThrownGrenade, from: Vector2, to: Vector2) -> Dictionary:
	var best: Dictionary = {"kind": "", "t": 2.0, "point": to}
	var travel: float = from.distance_to(to)
	if travel <= SimConstants.EPSILON:
		return best
	var space: PhysicsDirectSpaceState2D = get_world_2d().direct_space_state
	if space != null:
		var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(from, to)
		query.collision_mask = Maps.COL_WORLD | Maps.COL_PROP
		query.collide_with_bodies = true
		query.collide_with_areas = true
		query.hit_from_inside = false
		query.exclude = [nade.get_rid()]
		var hit: Dictionary = space.intersect_ray(query)
		if not hit.is_empty():
			var at: Vector2 = hit.get("position", to) as Vector2
			var t_wall: float = from.distance_to(at) / travel
			best = {"kind": "world", "t": t_wall, "point": at}
	var grid_hit: Dictionary = _grid_block_t(from, to)
	if str(grid_hit.get("kind", "")) == "world" and float(grid_hit.get("t", 2.0)) < float(best.get("t", 2.0)):
		best = {"kind": "world", "t": float(grid_hit.get("t", 2.0)), "point": grid_hit.get("point", to)}
	return best


func _nade_bounce(nade: ThrownGrenade, incoming: Vector2, at: Vector2) -> Vector2:
	var hit_floor: bool = Maps.solid_at(map_id, at + Vector2(0.0, 2.0))
	var hit_ceil: bool = Maps.solid_at(map_id, at + Vector2(0.0, -2.0))
	var hit_wall: bool = (
		Maps.solid_at(map_id, at + Vector2(2.0, 0.0))
		or Maps.solid_at(map_id, at + Vector2(-2.0, 0.0))
	)
	return _Expl.bounce_velocity(incoming, hit_floor, hit_ceil, hit_wall)


func _explode(nade: ThrownGrenade) -> void:
	if nade == null or nade.applied:
		return
	nade.applied = true
	nade.exploded = true
	ledger.push(clock.tick, "explosives", "explosion", {
		"owner": nade.owner_slot,
		"team": nade.owner_team,
		"x": SimConstants.quantize(nade.global_position.x),
		"y": SimConstants.quantize(nade.global_position.y),
		"radius": SimConstants.quantize(nade.radius),
		"damage": SimConstants.quantize(nade.damage),
		"prop_break": _Expl.prop_break_mode(),
		"once": true,
	})
	if sfx != null:
		sfx.play("explode")
	_splat(nade.global_position)
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		i += 1
		if not _Expl.allows_damage(mode, nade.owner_slot, nade.owner_team, f):
			continue
		if f.invuln_ticks > 0 or f.invuln > 0.0:
			continue
		var d: float = f.global_position.distance_to(nade.global_position)
		if d > nade.radius:
			continue
		var blast: float = _Expl.blast_damage_of(nade.damage, d, nade.radius)
		var knock: Vector2 = _Expl.blast_knock_of(nade.global_position, f.global_position, d, nade.radius)
		var rolled: Dictionary = _Bal.roll_hit(chaos_rng, chaos_enabled, blast, knock)
		var raw: float = float(rolled.get("raw", blast))
		f.last_crit = bool(rolled.get("crit", false))
		var hp0: float = f.health
		f.take_damage(raw, rolled.get("knock", knock) as Vector2)
		_record_hit_cap(f, raw, hp0, "blast", nade.payload_id)
		if f.last_crit:
			ledger.push(clock.tick, "combat", "crit", {
				"attacker": nade.owner_slot,
				"target": f.slot,
				"weapon": "nade",
				"seed": sim_seed,
			})
		_log_death_if_new(f)
		_splat(f.global_position)


func _resolve_end() -> void:
	if outcome != "play":
		return
	var p1: Fighter = player1()
	if p1 != null and p1.dead:
		outcome = "lose"
		lose_title = "Down"
		ledger.push(clock.tick, "match_resolve", "lose", {
			"cause": p1.death_cause if p1 != null else "",
		})
		if sfx != null:
			sfx.play("lose")
		lost.emit()
		return
	var foes_alive: int = 0
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		if f != p1 and not f.dead:
			if mode == "vs2" or f.team != p1.team:
				foes_alive += 1
		i += 1
	if foes_alive == 0:
		outcome = "win"
		win_title = "Last standing"
		ledger.push(clock.tick, "match_resolve", "win", {})
		if sfx != null:
			sfx.play("win")
		won.emit()


func _fit_camera() -> void:
	if camera == null:
		return
	var size: Vector2 = Maps.pixel_size(map_id)
	camera.position = size * 0.5
	var vp: Viewport = get_viewport()
	var view: Vector2 = Locomotion.designed_view()
	if vp != null:
		var vis: Vector2 = vp.get_visible_rect().size
		if vis.x > 1.0 and vis.y > 1.0:
			view = vis
	var zx: float = view.x / maxf(size.x, 1.0)
	var zy: float = view.y / maxf(size.y, 1.0)
	var z: float = minf(zx, zy)
	camera.zoom = Vector2(z, z)
	if is_inside_tree():
		camera.make_current()


func camera_framing() -> Dictionary:
	_fit_camera()
	var size: Vector2 = Maps.pixel_size(map_id)
	var view: Vector2 = Locomotion.designed_view()
	var vp: Viewport = get_viewport()
	if vp != null:
		var vis: Vector2 = vp.get_visible_rect().size
		if vis.x > 1.0 and vis.y > 1.0:
			view = vis
	var pos: Vector2 = Vector2.ZERO
	var zoom: Vector2 = Vector2.ONE
	if camera != null:
		pos = camera.position
		zoom = camera.zoom
	var zx: float = maxf(zoom.x, 0.0001)
	var zy: float = maxf(zoom.y, 0.0001)
	var visible: Vector2 = Vector2(view.x / zx, view.y / zy)
	var eps: float = Locomotion.epsilon()
	var covers: bool = visible.x + eps >= size.x and visible.y + eps >= size.y
	var centered: bool = absf(pos.x - size.x * 0.5) <= 1.0 and absf(pos.y - size.y * 0.5) <= 1.0
	return {
		"position": pos,
		"zoom": zoom,
		"arena_size": size,
		"view_size": view,
		"visible_world": visible,
		"covers_arena": covers,
		"centered": centered,
		"mode": str(Locomotion.camera().get("mode", "arena_fit")),
		"ledger": "RL-CAM-ARENA",
	}


func shutdown() -> void:
	if _shut_down:
		return
	_shut_down = true
	set_physics_process(false)
	set_process(false)
	var tree: SceneTree = get_tree()
	if tree != null:
		tree.paused = false
	if pause_screen != null and is_instance_valid(pause_screen):
		if _resume_cb.is_valid() and pause_screen.resume_pressed.is_connected(_resume_cb):
			pause_screen.resume_pressed.disconnect(_resume_cb)
	if sfx != null and is_instance_valid(sfx):
		sfx.shutdown()
	_free_fx()
	if world_owner != null:
		world_owner.call("clear")
		world_owner = null
	pickups.clear()
	fighters.clear()
	brains.clear()
	respawns.clear()
	bullets.clear()
	grenades.clear()
	if clock != null:
		clock.reset()
	pause_reason = ""
	last_reject = PackedStringArray()
	if ledger != null:
		ledger.reset()
	recorder = null
	if arena != null:
		arena.layer = null
		arena.world = null
		arena = null
	world = null
	hud = null
	pause_screen = null
	camera = null
	sfx = null


func _exit_tree() -> void:
	shutdown()


func _splat(at: Vector2) -> void:
	_spawn_fx(Visuals.BLOOD, at, 0.35)


func _muzzle(at: Vector2) -> void:
	_spawn_fx(Visuals.MUZZLE, at, 0.08)


func _spawn_fx(tex_path: String, at: Vector2, life: float) -> void:
	if not ResourceLoader.exists(tex_path):
		return
	var tex: Texture2D = load(tex_path) as Texture2D
	if tex == null:
		return
	_attach_fx_sprite(tex, at, life)


func _spawn_roll_fx(at: Vector2) -> void:
	if ResourceLoader.exists(Visuals.ROLL):
		_spawn_fx(Visuals.ROLL, at, 0.18)
	else:
		_attach_fx_sprite(Visuals.roll_flash_tex(), at, 0.18)


func _attach_fx_sprite(tex: Texture2D, at: Vector2, life: float) -> void:
	if tex == null:
		return
	var spr: Sprite2D = Sprite2D.new()
	spr.texture = tex
	spr.centered = true
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.global_position = at
	add_child(spr)
	_fx.append(spr)
	_fx_life.append(life)


func _tick_fx(delta: float) -> void:
	var i: int = 0
	while i < _fx.size():
		_fx_life[i] = _fx_life[i] - delta
		if _fx_life[i] <= 0.0:
			_free_node(_fx[i])
			_fx.remove_at(i)
			_fx_life.remove_at(i)
			continue
		i += 1


func _free_fx() -> void:
	var i: int = 0
	while i < _fx.size():
		_free_node(_fx[i])
		i += 1
	_fx.clear()
	_fx_life.clear()


func _emit_loco_feedback(f: Fighter) -> void:
	if f == null:
		return
	if f.sprint_started:
		ledger.push(clock.tick, "locomotion", "sprint_start", {
			"slot": f.slot,
			"stamina": SimConstants.quantize(f.stamina),
		})
	if f.sprint_ended:
		ledger.push(clock.tick, "locomotion", "sprint_end", {
			"slot": f.slot,
			"stamina": SimConstants.quantize(f.stamina),
		})
	if f.roll_started:
		ledger.push(clock.tick, "locomotion", "roll_start", {
			"slot": f.slot,
			"seq": f.roll_seq,
			"invuln": SimConstants.quantize(f.invuln),
		})
		ledger.push(clock.tick, "locomotion", "roll_extinguish", {
			"slot": f.slot,
			"seq": f.roll_seq,
			"count": f.fire_extinguish_count,
		})
		if sfx != null:
			sfx.play("roll")
		_spawn_roll_fx(f.global_position + Vector2(0.0, 8.0))
	if f.roll_ended:
		ledger.push(clock.tick, "locomotion", "roll_end", {
			"slot": f.slot,
			"seq": f.roll_seq,
		})
	if f.dive_started:
		ledger.push(clock.tick, "locomotion", "dive_start", {
			"slot": f.slot,
			"seq": f.dive_seq,
			"invuln": SimConstants.quantize(f.invuln),
		})
		ledger.push(clock.tick, "locomotion", "dive_extinguish", {
			"slot": f.slot,
			"seq": f.dive_seq,
			"count": f.fire_extinguish_count,
		})
		if sfx != null:
			sfx.play("dive")
		_spawn_roll_fx(f.global_position + Vector2(0.0, 10.0))
	if f.dive_ended:
		ledger.push(clock.tick, "locomotion", "dive_end", {
			"slot": f.slot,
			"seq": f.dive_seq,
			"fall_immune": 1 if f.fall_immune_landed else 0,
		})
	if f.kick_started:
		if sfx != null and sfx.last_id != "kick":
			sfx.play("kick")
	if f.fall_damage_applied:
		ledger.push(clock.tick, "locomotion", "fall_damage", {
			"slot": f.slot,
			"hp": SimConstants.quantize(f.health),
		})
	if f.fall_immune_landed:
		ledger.push(clock.tick, "locomotion", "fall_immune", {
			"slot": f.slot,
			"seq": f.dive_seq,
		})
	if f.attach_started:
		ledger.push(clock.tick, "locomotion", "ladder_attach", {
			"slot": f.slot,
			"seq": f.climb_seq,
			"x": SimConstants.quantize(f.global_position.x),
		})
		if sfx != null:
			sfx.play("climb")
	if f.detach_started:
		ledger.push(clock.tick, "locomotion", "ladder_detach", {
			"slot": f.slot,
			"seq": f.climb_seq,
			"block": f.last_climb_block,
		})
	if f.climb_blocked_now:
		ledger.push(clock.tick, "locomotion", "ladder_block", {
			"slot": f.slot,
			"nx": SimConstants.quantize(f.last_contact_nx),
			"ny": SimConstants.quantize(f.last_contact_ny),
		})
	if f.hang_started:
		ledger.push(clock.tick, "locomotion", "ledge_grab", {
			"slot": f.slot,
			"seq": f.hang_seq,
			"nx": SimConstants.quantize(f.last_contact_nx),
			"ny": SimConstants.quantize(f.last_contact_ny),
		})
		if sfx != null:
			sfx.play("ledge")
	if f.recover_started:
		ledger.push(clock.tick, "locomotion", "ledge_recover", {
			"slot": f.slot,
			"seq": f.hang_seq,
		})
		if sfx != null:
			sfx.play("climb")
	if f.hang_ended and not f.recover_started:
		ledger.push(clock.tick, "locomotion", "ledge_drop", {
			"slot": f.slot,
			"seq": f.hang_seq,
		})
	if f.drop_started:
		ledger.push(clock.tick, "locomotion", "drop_through", {
			"slot": f.slot,
		})
		if sfx != null:
			sfx.play("drop")


func _emit_reaction_feedback(f: Fighter) -> void:
	if f == null:
		return
	if f.knockback_started:
		ledger.push(clock.tick, "melee", "knockback_start", {
			"slot": f.slot,
			"vx": SimConstants.quantize(f.velocity.x),
			"vy": SimConstants.quantize(f.velocity.y),
		})
	if f.knockback_ended:
		ledger.push(clock.tick, "melee", "knockback_end", {
			"slot": f.slot,
		})
	if f.hit_airborne_started:
		ledger.push(clock.tick, "melee", "airborne_start", {
			"slot": f.slot,
		})
	if f.hit_airborne_ended:
		ledger.push(clock.tick, "melee", "airborne_end", {
			"slot": f.slot,
		})
	if f.knockdown_started:
		ledger.push(clock.tick, "melee", "knockdown_start", {
			"slot": f.slot,
		})
	if f.knockdown_ended:
		ledger.push(clock.tick, "melee", "knockdown_end", {
			"slot": f.slot,
		})
	if f.knockdown_blocked:
		ledger.push(clock.tick, "melee", "knockdown_block", {
			"slot": f.slot,
		})
	if f.getup_started:
		ledger.push(clock.tick, "melee", "getup_start", {
			"slot": f.slot,
		})
	if f.getup_ended:
		ledger.push(clock.tick, "melee", "getup_end", {
			"slot": f.slot,
		})
	if f.invuln_started:
		ledger.push(clock.tick, "melee", "invuln_start", {
			"slot": f.slot,
			"ticks": f.invuln_ticks,
		})
	if f.invuln_ended:
		ledger.push(clock.tick, "melee", "invuln_end", {
			"slot": f.slot,
		})


func _record_hit_cap(target: Fighter, raw: float, hp0: float, path: String, weapon: String) -> void:
	if target == null:
		return
	var applied: float = hp0 - target.health
	last_hit_raw = raw
	last_hit_applied = applied
	last_hit_path = path
	last_hit_weapon = weapon
	if raw > _Bal.hit_cap() + 0.001:
		ledger.push(clock.tick, "combat", "clamp", {
			"target": target.slot,
			"path": path,
			"weapon": weapon,
			"raw": SimConstants.quantize(raw),
			"applied": SimConstants.quantize(applied),
			"cap": SimConstants.quantize(_Bal.hit_cap()),
			"incoming": SimConstants.quantize(target.last_incoming_raw),
		})


func _log_death_if_new(f: Fighter) -> void:
	if f == null or not f.dead:
		return
	if ledger.has_death(f.slot):
		return
	ledger.push(clock.tick, "match_resolve", "death", {
		"slot": f.slot,
		"cause": f.death_cause,
	})


func _free_node(node: Node) -> void:
	if node == null or not is_instance_valid(node):
		return
	var parent: Node = node.get_parent()
	if parent != null:
		parent.remove_child(node)
	node.free()
