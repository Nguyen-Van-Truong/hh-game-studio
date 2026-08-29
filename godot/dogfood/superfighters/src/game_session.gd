class_name GameSession
extends Node2D

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
var hud: Hud
var pause_screen: PauseScreen
var sfx: SfxBank
var camera: Camera2D
var test_driven: bool = false
var rng: RandomNumberGenerator = RandomNumberGenerator.new()
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


func setup(p_mode: String, p_map: String, p_stage: int) -> void:
	name = "GameSession"
	process_mode = Node.PROCESS_MODE_PAUSABLE
	mode = p_mode
	map_id = p_map
	stage_index = p_stage
	outcome = "play"
	sim_seed = SimSeed.for_match(p_mode, p_map, p_stage)
	rng.seed = sim_seed
	clock.reset()
	pause_reason = ""
	last_reject = PackedStringArray()
	ledger = SimEventLedger.new()
	arena = Arena.new()
	world = arena.build(map_id)
	add_child(world)
	_spawn_fighters()
	_spawn_weapons()
	hud = Hud.new()
	add_child(hud)
	hud.set_map_name(Maps.display_name(map_id))
	hud.set_hint("Last standing · double-tap sprint · crouch-while-sprint rolls · hold M fire")
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
	var kill_plane: float = Maps.kill_y(map_id)
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		var cmd: Dictionary = InputActions.empty_cmd()
		if i < cmds.size():
			cmd = cmds[i]
		cmd["on_ladder"] = arena != null and arena.has_ladder_at(f.global_position)
		var before_y: float = f.velocity.y
		f.step(dt, cmd, kill_plane)
		_emit_loco_feedback(f)
		_log_death_if_new(f)
		if f.last_jump and before_y >= 0.0 and f.velocity.y < 0.0 and sfx != null:
			sfx.play("jump")
		if f.want_melee:
			_do_melee(f)
		if f.want_fire:
			_do_fire(f)
		if f.want_grenade:
			_do_grenade(f)
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
		if row.has("fuse"):
			nade.fuse = SimConstants.dequantize(int(row.get("fuse", 0)))
		if row.has("damage"):
			nade.damage = SimConstants.dequantize(int(row.get("damage", 0)))
		if row.has("radius"):
			nade.radius = SimConstants.dequantize(int(row.get("radius", 0)))
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
	var drop: Pickup = Pickup.new()
	drop.setup(pid, at)
	drop.from_world = from_world
	drop.home = at
	world.add_child(drop)
	pickups.append(drop)
	return drop


func _do_melee(f: Fighter) -> void:
	if f.crouched:
		if _try_pickup(f):
			return
	var spec: Dictionary = WeaponDefs.data(f.melee_id)
	if sfx != null:
		sfx.play("punch")
	var reach: float = float(spec.get("range", 18.0))
	var i: int = 0
	while i < fighters.size():
		var other: Fighter = fighters[i]
		i += 1
		if other == f or other.dead:
			continue
		var delta: Vector2 = other.global_position - f.global_position
		if absf(delta.y) > 16.0:
			continue
		if absf(delta.x) > reach + 4.0:
			continue
		if signf(delta.x) != 0.0 and signf(delta.x) != signf(f.facing):
			continue
		other.take_damage(float(spec.get("damage", 10.0)), Vector2(f.facing * 80.0, -40.0))
		ledger.push(clock.tick, "melee", "hit", {
			"attacker": f.slot,
			"target": other.slot,
			"damage": SimConstants.quantize(float(spec.get("damage", 10.0))),
		})
		_log_death_if_new(other)
		_splat(other.global_position)
		if sfx != null:
			sfx.play("hit")


func _try_pickup(f: Fighter) -> bool:
	if not f.crouched:
		return false
	var i: int = 0
	while i < pickups.size():
		var drop: Pickup = pickups[i]
		if drop != null and is_instance_valid(drop):
			if f.global_position.distance_to(drop.global_position) <= 28.0:
				var spec: Dictionary = WeaponDefs.data(drop.weapon_id)
				var slot_kind: String = str(spec.get("slot", "melee"))
				if slot_kind == "gun" and f.gun_id != "" and f.ammo > 0:
					_drop_specific(f.gun_id, f.global_position + Vector2(0, 8), false)
				elif slot_kind == "melee" and f.melee_id != "fists":
					_drop_specific(f.melee_id, f.global_position + Vector2(0, 8), false)
				if drop.from_world:
					respawns.append({
						"id": drop.weapon_id,
						"pos": drop.home,
						"t": Maps.WEAPON_RESPAWN,
					})
				f.give_weapon(drop.weapon_id)
				if sfx != null:
					sfx.play("pickup")
				drop.queue_free()
				pickups.remove_at(i)
				return true
		i += 1
	return false


func _drop_specific(pid: String, at: Vector2, from_world: bool) -> void:
	if pid == "" or pid == "fists":
		return
	_add_pickup(pid, at, from_world)


func _do_fire(f: Fighter) -> void:
	var spec: Dictionary = WeaponDefs.data(f.gun_id)
	if str(spec.get("kind", "")) != "gun" or f.ammo <= 0:
		return
	f.fire_cd = float(spec.get("cooldown", 0.4))
	var pellets: int = int(spec.get("pellets", 1))
	var spread: float = float(spec.get("spread", 0.0))
	var speed: float = float(spec.get("speed", 520.0))
	var dmg: float = float(spec.get("damage", 10.0))
	var base: Vector2 = f.aim_dir
	if base == Vector2.ZERO:
		base = Vector2(f.facing, 0.0)
	var p: int = 0
	while p < pellets:
		var ang: float = (float(p) - float(pellets - 1) * 0.5) * spread
		var dir: Vector2 = base.rotated(ang)
		var shot: Bullet = Bullet.new()
		var muzzle: Vector2 = f.global_position + dir * 14.0 + Vector2(0, -4)
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
	})
	if sfx != null:
		if f.gun_id == "shotgun":
			sfx.play("shotgun")
		else:
			sfx.play("shoot")
	_muzzle(f.global_position + base * 14.0)


func _do_grenade(f: Fighter) -> void:
	if f.grenades <= 0:
		return
	f.consume_grenade()
	var dir: Vector2 = f.aim_dir
	if dir == Vector2.ZERO:
		dir = Vector2(f.facing, -0.35)
	var nade: ThrownGrenade = ThrownGrenade.new()
	nade.setup(f.global_position + Vector2(f.facing * 10.0, -8.0), dir, f.slot, f.team)
	add_child(nade)
	grenades.append(nade)
	ledger.push(clock.tick, "grenade_spawn", "nade", {
		"owner": f.slot,
		"nades": f.grenades,
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
		shot.step(delta)
		if _bullet_blocked(shot) or _bullet_hit_fighter(shot):
			shot.spent = true
			shot.queue_free()
			bullets.remove_at(i)
			continue
		i += 1


func _bullet_blocked(shot: Bullet) -> bool:
	var space: PhysicsDirectSpaceState2D = get_world_2d().direct_space_state
	if space == null:
		return false
	var query: PhysicsRayQueryParameters2D = PhysicsRayQueryParameters2D.create(
		shot.global_position, shot.global_position + shot.velocity.normalized() * 4.0
	)
	query.collision_mask = Maps.COL_WORLD | Maps.COL_PROP
	var hit: Dictionary = space.intersect_ray(query)
	return not hit.is_empty()


func _bullet_hit_fighter(shot: Bullet) -> bool:
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		i += 1
		if f.dead or f.slot == shot.owner_slot:
			continue
		if f.global_position.distance_to(shot.global_position) <= 10.0:
			f.take_damage(shot.damage, shot.velocity.normalized() * 70.0 + Vector2(0, -30))
			_log_death_if_new(f)
			_splat(f.global_position)
			if sfx != null:
				sfx.play("hit")
			return true
	return false


func _step_grenades(delta: float) -> void:
	var i: int = 0
	while i < grenades.size():
		var nade: ThrownGrenade = grenades[i]
		if nade == null or not is_instance_valid(nade):
			grenades.remove_at(i)
			continue
		nade.step(delta)
		if nade.exploded:
			_explode(nade)
			nade.queue_free()
			grenades.remove_at(i)
			continue
		i += 1


func _explode(nade: ThrownGrenade) -> void:
	if sfx != null:
		sfx.play("explode")
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		i += 1
		if f.dead:
			continue
		var d: float = f.global_position.distance_to(nade.global_position)
		if d <= nade.radius:
			var falloff: float = 1.0 - (d / nade.radius)
			var dir: Vector2 = (f.global_position - nade.global_position).normalized()
			f.take_damage(nade.damage * falloff, dir * 140.0 + Vector2(0, -80))
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
