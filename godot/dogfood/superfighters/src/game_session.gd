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


func setup(p_mode: String, p_map: String, p_stage: int) -> void:
	name = "GameSession"
	process_mode = Node.PROCESS_MODE_PAUSABLE
	mode = p_mode
	map_id = p_map
	stage_index = p_stage
	outcome = "play"
	rng.seed = 7 + p_stage * 13
	arena = Arena.new()
	world = arena.build(map_id)
	add_child(world)
	_spawn_fighters()
	_spawn_weapons()
	hud = Hud.new()
	add_child(hud)
	hud.set_map_name(Maps.display_name(map_id))
	hud.set_hint("Last standing wins · crouch+N pickup · hold M fire · hold comma throw")
	pause_screen = PauseScreen.new()
	pause_screen.resume_pressed.connect(set_paused.bind(false))
	add_child(pause_screen)
	sfx = SfxBank.new()
	add_child(sfx)
	if not test_driven:
		sfx.start_music()
	camera = Camera2D.new()
	camera.name = "ArenaCam"
	add_child(camera)
	_fit_camera()
	hud.refresh(fighters)


func _physics_process(delta: float) -> void:
	if test_driven:
		return
	var tree: SceneTree = get_tree()
	if tree != null and tree.paused:
		return
	if outcome != "play":
		return
	var cmds: Array[Dictionary] = []
	var i: int = 0
	while i < fighters.size():
		var f: Fighter = fighters[i]
		if f.is_bot:
			if i >= brains.size():
				brains.append(BotBrain.new())
			cmds.append(brains[i].think(f, fighters, pickups, delta))
		elif f.slot == 0:
			cmds.append(InputActions.read_player(0))
		elif f.slot == 1 and f.is_human:
			cmds.append(InputActions.read_player(1))
		else:
			cmds.append(InputActions.empty_cmd())
		i += 1
	step_fixed(delta, cmds)


func step_fixed(delta: float, cmds: Array[Dictionary]) -> void:
	if outcome != "play":
		return
	var tree: SceneTree = get_tree()
	if tree != null and tree.paused:
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
		f.step(delta, cmd, kill_plane)
		if f.last_jump and before_y >= 0.0 and f.velocity.y < 0.0 and sfx != null:
			sfx.play("jump")
		if f.want_melee:
			_do_melee(f)
		if f.want_fire:
			_do_fire(f)
		if f.want_grenade:
			_do_grenade(f)
		i += 1
	_step_respawns(delta)
	_step_bullets(delta)
	_step_grenades(delta)
	_resolve_end()
	if hud != null:
		hud.refresh(fighters)
	_fit_camera()


func set_paused(active: bool) -> void:
	if outcome != "play" and active:
		return
	var tree: SceneTree = get_tree()
	if tree == null:
		return
	tree.paused = active
	if sfx != null:
		sfx.duck(active)
	if active:
		pause_screen.show_pause()
	else:
		pause_screen.hide_pause()


func snapshot() -> Dictionary:
	var living: int = 0
	var i: int = 0
	while i < fighters.size():
		if not fighters[i].dead:
			living += 1
		i += 1
	var p1: Fighter = player1()
	return {
		"outcome": outcome,
		"map_id": map_id,
		"mode": mode,
		"living": living,
		"p1_hp": p1.health if p1 != null else 0.0,
		"p1_dead": p1.dead if p1 != null else true,
		"p1_weapon": p1.weapon_id if p1 != null else "",
		"p1_gun": p1.gun_id if p1 != null else "",
		"p1_melee": p1.melee_id if p1 != null else "",
		"p1_nades": p1.grenades if p1 != null else 0,
		"p1_x": p1.global_position.x if p1 != null else 0.0,
		"p1_y": p1.global_position.y if p1 != null else 0.0,
		"win": outcome == "win",
	}


func player1() -> Fighter:
	if fighters.is_empty():
		return null
	return fighters[0]


func force_kill(slot: int) -> void:
	var i: int = 0
	while i < fighters.size():
		if fighters[i].slot == slot:
			fighters[i].kill()
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
			_splat(f.global_position)


func _resolve_end() -> void:
	if outcome != "play":
		return
	var p1: Fighter = player1()
	if p1 != null and p1.dead:
		outcome = "lose"
		lose_title = "Down"
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
		if sfx != null:
			sfx.play("win")
		won.emit()


func _fit_camera() -> void:
	if camera == null:
		return
	var size: Vector2 = Maps.pixel_size(map_id)
	camera.position = size * 0.5
	var vp: Viewport = get_viewport()
	var view: Vector2 = Maps.DESIGNED_VIEW
	if vp != null:
		view = vp.get_visible_rect().size
	var zx: float = view.x / maxf(size.x, 1.0)
	var zy: float = view.y / maxf(size.y, 1.0)
	var z: float = minf(zx, zy)
	camera.zoom = Vector2(z, z)
	if is_inside_tree():
		camera.make_current()


func _splat(at: Vector2) -> void:
	var spr: Sprite2D = Sprite2D.new()
	spr.texture = load(Visuals.BLOOD) as Texture2D
	spr.centered = true
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.global_position = at
	add_child(spr)
	var tree: SceneTree = get_tree()
	if tree != null:
		var timer: SceneTreeTimer = tree.create_timer(0.35)
		timer.timeout.connect(spr.queue_free)


func _muzzle(at: Vector2) -> void:
	var spr: Sprite2D = Sprite2D.new()
	spr.texture = load(Visuals.MUZZLE) as Texture2D
	spr.centered = true
	spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	spr.global_position = at
	add_child(spr)
	var tree: SceneTree = get_tree()
	if tree != null:
		var timer: SceneTreeTimer = tree.create_timer(0.08)
		timer.timeout.connect(spr.queue_free)
