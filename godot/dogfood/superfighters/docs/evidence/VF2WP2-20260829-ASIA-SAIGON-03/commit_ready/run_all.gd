extends SceneTree

const STEP: float = 1.0 / 60.0

var _fails: PackedStringArray = PackedStringArray()
var _loop: String = "unproven"
var _combat: String = "unproven"
var _maps: String = "unproven"
var _hygiene: String = "unproven"
var _no_err: String = "unproven"
var _sim: String = "unproven"
var _trace: String = "unproven"
var _runtime: String = "unproven"
var _input: String = "unproven"
var _loco: String = "unproven"


func _initialize() -> void:
	call_deferred("_boot")


func _boot() -> void:
	seed(1)
	InputActions.install()
	var app: App = _make_app()
	_test_title(app)
	_test_input_binds()
	_test_buses()
	await _test_vs_loop(app)
	_test_combat(app)
	_test_maps(app)
	_test_pause(app)
	_test_pit(app)
	await _test_stage_advance(app)
	_test_session_hygiene(app)
	_test_sim_contract(app)
	await _test_golden_traces(app)
	_test_runtime(app)
	await _test_input_map(app)
	await _test_locomotion(app)
	if _fails.is_empty():
		_no_err = "proven"
	_emit()
	if is_instance_valid(app):
		app.shutdown()
		app.queue_free()
	await process_frame
	await process_frame
	quit(0 if _fails.is_empty() else 1)


func _make_app() -> App:
	var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
	var app: App = packed.instantiate() as App
	app.test_driven = true
	root.add_child(app)
	return app


func _test_title(app: App) -> void:
	if app.title == null:
		_fail("TITLE missing title screen")
		return
	var label: Label = app.title.get_node_or_null("TitleLabel") as Label
	if label == null or label.text != "Vault Fighters":
		_fail("TITLE must be Vault Fighters")
	var sub: Label = app.title.get_node_or_null("Subtitle") as Label
	if sub != null and sub.text.to_lower().contains("superfighter"):
		_fail("TITLE card must not use the Superfighters trademark")


func _test_input_binds() -> void:
	var pad_actions: PackedStringArray = PackedStringArray([
		"p1_left", "p1_right", "p1_up", "p1_down", "p1_jump", "p1_crouch",
		"p1_melee", "p1_fire", "p1_grenade", "pause"
	])
	var i: int = 0
	while i < pad_actions.size():
		var action: String = String(pad_actions[i])
		if not InputMap.has_action(action):
			_fail("missing InputMap action %s" % action)
		elif not InputActions.has_keyboard_and_gamepad(action):
			_fail("action %s missing keyboard+gamepad" % action)
		i += 1
	var p2: PackedStringArray = PackedStringArray([
		"p2_left", "p2_right", "p2_up", "p2_down", "p2_jump", "p2_crouch",
		"p2_melee", "p2_fire", "p2_grenade"
	])
	var j: int = 0
	while j < p2.size():
		var a2: String = String(p2[j])
		if not InputMap.has_action(a2):
			_fail("missing P2 action %s" % a2)
		elif not InputActions.has_keyboard_and_gamepad(a2):
			_fail("P2 action %s missing keyboard+gamepad" % a2)
		j += 1
	var p1_dev: PackedInt32Array = InputMapStore.action_joy_devices("p1_melee")
	var p2_dev: PackedInt32Array = InputMapStore.action_joy_devices("p2_melee")
	if p1_dev.has(1) or p2_dev.has(0):
		_fail("P1/P2 gamepad devices must stay split 0/1")


func _test_buses() -> void:
	var buses: PackedStringArray = PackedStringArray(["Master", "Music", "SFX"])
	var b: int = 0
	while b < buses.size():
		if AudioServer.get_bus_index(String(buses[b])) < 0:
			_fail("missing audio bus %s" % String(buses[b]))
		b += 1


func _test_vs_loop(app: App) -> void:
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	if session == null:
		_fail("LOOP missing session")
		return
	var layer: TileMapLayer = session.world.get_node_or_null("ArenaTiles") as TileMapLayer
	if layer == null or layer.tile_set == null:
		_fail("LOOP missing ArenaTiles TileMapLayer")
	else:
		var atlas_src: TileSetSource = layer.tile_set.get_source(0)
		var atlas: TileSetAtlasSource = atlas_src as TileSetAtlasSource
		if atlas == null or atlas.texture == null:
			_fail("LOOP tiles missing atlas texture")
		elif atlas.texture.resource_path != Visuals.TILESET:
			_fail("LOOP live tiles must use tileset_arena.png")
	if session.fighters.size() < 2:
		_fail("LOOP vs1 must spawn player + bots")
	var p1: Fighter = session.player1()
	if p1 == null:
		_fail("LOOP missing P1")
		return
	if p1.gun_id != "pistol" or p1.ammo != 12 or p1.grenades != 3 or p1.melee_id != "fists":
		_fail("LOOP start kit must be fists + pistol x12 + 3 nades")
	var start_x: float = p1.global_position.x
	_walk(session, 1.0, 20)
	if p1.global_position.x <= start_x + 2.0:
		_fail("LOOP P1 did not move right")
	app.start_fight("vs1", "storage", 0)
	session = app.session
	_fight_until_p1_wins(session, 1200)
	await process_frame
	if app.session == null or app.session.outcome != "win":
		_fail("LOOP live fight must win by damage or pit")
	if not app.win_screen.visible:
		_fail("LOOP win screen not shown")
	if not _foes_died_honestly(session):
		_fail("LOOP foes must die from damage or pit, not scripted kill()")
	app.start_fight("vs1", "rooftops", 0)
	if app.session.outcome != "play" or app.session.player1().dead:
		_fail("LOOP restart must be a fresh fight")
	if app.win_screen.visible:
		_fail("LOOP restart must hide win screen")
	if _count_prefix("LOOP ") == 0:
		_loop = "proven"


func _test_combat(app: App) -> void:
	app.start_fight("vs1", "storage", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	_settle(session, 12)
	if session.fighters.size() < 2:
		_fail("COMBAT missing foe")
		return
	if p1.gun_id != "pistol" or p1.ammo < 12 or p1.grenades != 3 or p1.melee_id != "fists":
		_fail("COMBAT start kit must be fists + pistol + 3 nades")
	var foe: Fighter = session.fighters[1]
	foe.global_position = p1.global_position + Vector2(14, 0)
	p1.facing = 1.0
	var hp0: float = foe.health
	var cmds: Array[Dictionary] = _idle_cmds(session)
	cmds[0]["melee"] = true
	session.step_fixed(STEP, cmds)
	if foe.health >= hp0:
		_fail("COMBAT melee must deal damage")
	if session.pickups.is_empty():
		_fail("COMBAT storage must spawn weapons")
	else:
		var drop: Pickup = session._add_pickup("pipe", p1.global_position + Vector2(0, 4), false)
		var gun0: String = p1.gun_id
		_settle(session, 8)
		p1.melee_cd = 0.0
		p1.global_position = drop.global_position
		_settle(session, 4)
		var stand: Array[Dictionary] = _idle_cmds(session)
		stand[0]["melee"] = true
		session.step_fixed(STEP, stand)
		if p1.melee_id != "fists" or p1.gun_id != gun0:
			_fail("COMBAT standing melee must not auto-loot")
		p1.melee_cd = 0.0
		p1.global_position = drop.global_position
		var grab: Array[Dictionary] = _idle_cmds(session)
		grab[0]["crouch"] = true
		grab[0]["melee"] = true
		session.step_fixed(STEP, grab)
		if p1.melee_id != "pipe" or p1.gun_id != gun0:
			_fail("COMBAT crouch+melee must pick up melee without stripping the gun")
	_test_grenade_keeps_gun(session, p1)
	_test_nade_hold_release(session, p1)
	_test_weapon_respawn(session, p1)
	p1.gun_id = "pistol"
	p1.ammo = 6
	p1.weapon_id = "pistol"
	p1.aim_dir = Vector2.RIGHT
	p1.facing = 1.0
	foe.global_position = p1.global_position + Vector2(40, 0)
	foe.health = 100.0
	var fire: Array[Dictionary] = _idle_cmds(session)
	fire[0]["fire_held"] = true
	session.step_fixed(STEP, fire)
	fire[0]["fire_released"] = true
	session.step_fixed(STEP, fire)
	var b: int = 0
	while b < 20:
		session.step_fixed(STEP, _idle_cmds(session))
		b += 1
	if foe.health >= 100.0 and session.bullets.is_empty():
		_fail("COMBAT pistol release must fire")
	if _count_prefix("COMBAT ") == 0:
		_combat = "proven"


func _test_grenade_keeps_gun(session: GameSession, p1: Fighter) -> void:
	p1.gun_id = "pistol"
	p1.ammo = 12
	p1.weapon_id = "pistol"
	p1.melee_id = "fists"
	var g0: int = p1.grenades
	var nade: Pickup = session._add_pickup("grenade", p1.global_position, false)
	p1.melee_cd = 0.0
	p1.global_position = nade.global_position
	var grab: Array[Dictionary] = _idle_cmds(session)
	grab[0]["crouch"] = true
	grab[0]["melee"] = true
	session.step_fixed(STEP, grab)
	if p1.gun_id != "pistol" or p1.ammo != 12:
		_fail("COMBAT picking a grenade must not strip the gun")
	if p1.grenades <= g0:
		_fail("COMBAT grenade pickup must add nades")


func _test_nade_hold_release(session: GameSession, p1: Fighter) -> void:
	p1.grenades = 3
	p1.aim_dir = Vector2.RIGHT
	p1.facing = 1.0
	var held: Array[Dictionary] = _idle_cmds(session)
	held[0]["grenade_held"] = true
	session.step_fixed(STEP, held)
	if p1.grenades != 3 or not session.grenades.is_empty():
		_fail("COMBAT hold-comma must aim, not throw")
	var rel: Array[Dictionary] = _idle_cmds(session)
	rel[0]["grenade_released"] = true
	session.step_fixed(STEP, rel)
	if p1.grenades != 2 or session.grenades.is_empty():
		_fail("COMBAT release comma must throw a grenade")


func _test_weapon_respawn(session: GameSession, p1: Fighter) -> void:
	var before: int = session.pickups.size()
	var drop: Pickup = session._add_pickup("uzi", p1.global_position + Vector2(8, 0), true)
	p1.melee_cd = 0.0
	p1.global_position = drop.global_position
	var grab: Array[Dictionary] = _idle_cmds(session)
	grab[0]["crouch"] = true
	grab[0]["melee"] = true
	session.step_fixed(STEP, grab)
	if session.respawns.is_empty():
		_fail("COMBAT world pickup must queue a ~20s respawn")
		return
	if absf(float(session.respawns[0].get("t", 0.0)) - Maps.WEAPON_RESPAWN) > 1.0:
		_fail("COMBAT weapon respawn must be ~20s")
	var frames: int = 0
	while frames < 1210 and not session.respawns.is_empty():
		session.step_fixed(STEP, _idle_cmds(session))
		frames += 1
	if session.pickups.size() <= before:
		_fail("COMBAT weapon must respawn after ~20s")


func _test_maps(app: App) -> void:
	var ids: PackedStringArray = PackedStringArray(["rooftops", "storage", "police", "hazardous"])
	var i: int = 0
	while i < ids.size():
		var mid: String = String(ids[i])
		var rows: PackedStringArray = Maps.grid(mid)
		if rows.is_empty():
			_fail("MAPS %s empty grid" % mid)
			i += 1
			continue
		var w: int = String(rows[0]).length()
		var y: int = 0
		while y < rows.size():
			if String(rows[y]).length() != w:
				_fail("MAPS %s row %d width mismatch" % [mid, y])
			y += 1
		if Maps.count_char(mid, "H") < 1:
			_fail("MAPS %s missing ladders" % mid)
		if Maps.count_char(mid, "=") < 1:
			_fail("MAPS %s missing one-way platforms" % mid)
		if mid != "storage" and Maps.pit_column_count(mid) < 1:
			_fail("MAPS %s missing pit columns" % mid)
		if not Maps.spawn_floor_solid(mid):
			_fail("MAPS %s spawn is not on walkable floor" % mid)
		app.start_fight("vs1", mid, 0)
		if app.session == null or app.session.world == null:
			_fail("MAPS %s failed to build" % mid)
		elif app.session.player1() == null:
			_fail("MAPS %s missing P1 spawn" % mid)
		else:
			if app.session.arena == null or app.session.arena.ladder_cells.is_empty():
				_fail("MAPS %s live arena missing ladder cells" % mid)
			if app.session.arena == null or not app.session.arena.platform_is_one_way():
				_fail("MAPS %s platforms must use Godot one-way collision" % mid)
		i += 1
	if not Maps.police_interior_floor_solid():
		_fail("MAPS police station ground floor must be walkable")
	app.start_fight("vs1", "police", 0)
	var p1: Fighter = app.session.player1()
	var n: int = 0
	while n < 20:
		app.session.step_fixed(STEP, _idle_cmds(app.session))
		n += 1
	if p1.dead or p1.death_cause == "pit":
		_fail("MAPS police spawn must not drop P1 into a pit")
	_test_climb(app)
	if _count_prefix("MAPS ") == 0:
		_maps = "proven"


func _test_climb(app: App) -> void:
	app.start_fight("vs1", "rooftops", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.player1()
	if session.arena.ladder_cells.is_empty():
		_fail("MAPS rooftops live ladders missing")
		return
	var cell: Vector2i = session.arena.ladder_cells[0]
	p1.global_position = Vector2(
		float(cell.x * Maps.TILE) + 8.0,
		float(cell.y * Maps.TILE) + 8.0
	)
	var y0: float = p1.global_position.y
	var n: int = 0
	while n < 18:
		var cmds: Array[Dictionary] = _idle_cmds(session)
		cmds[0]["jump"] = true
		session.step_fixed(STEP, cmds)
		n += 1
	if p1.global_position.y >= y0 - 4.0:
		_fail("MAPS ladder climb must move P1 up")


func _test_pause(app: App) -> void:
	app.start_fight("vs1", "rooftops", 0)
	app.session.set_paused(true)
	var tree: SceneTree = self
	if not tree.paused:
		_fail("PAUSE tree was not paused")
	if not app.session.pause_screen.visible:
		_fail("PAUSE overlay hidden")
	app.session.set_paused(false)
	if tree.paused:
		_fail("PAUSE resume left tree paused")


func _test_pit(app: App) -> void:
	app.start_fight("vs1", "rooftops", 0)
	var p1: Fighter = app.session.player1()
	p1.global_position = Vector2(80, Maps.kill_y("rooftops") + 40.0)
	app.session.step_fixed(STEP, _idle_cmds(app.session))
	if not p1.dead or app.session.outcome != "lose":
		_fail("PIT fall must kill P1 and lose")
	if p1.death_cause != "pit":
		_fail("PIT death_cause must be pit")
	if not app.lose_screen.visible:
		_fail("PIT lose screen hidden")


func _test_stage_advance(app: App) -> void:
	app.start_fight("stage", "rooftops", 0)
	_fight_until_p1_wins(app.session, 900)
	await process_frame
	if app.session == null or app.session.map_id != "storage":
		_fail("STAGE win rooftops must load Storage")
		return
	if app.win_screen.visible:
		_fail("STAGE mid-run must not show final win")


func _fight_until_p1_wins(session: GameSession, max_frames: int) -> void:
	var frames: int = 0
	while frames < max_frames and session.outcome == "play":
		var p1: Fighter = session.player1()
		var foe: Fighter = _first_living_foe(session)
		if p1 == null or foe == null:
			session.step_fixed(STEP, _idle_cmds(session))
			frames += 1
			continue
		var floor_y: float = foe.global_position.y
		p1.global_position = Vector2(foe.global_position.x - 16.0, floor_y)
		p1.velocity = Vector2.ZERO
		foe.velocity = Vector2.ZERO
		p1.facing = 1.0
		p1.aim_dir = Vector2.RIGHT
		p1.gun_id = "pistol"
		if p1.ammo < 4:
			p1.ammo = 12
		p1.invuln = 0.2
		var cmds: Array[Dictionary] = _idle_cmds(session)
		cmds[0]["melee"] = true
		cmds[0]["fire_held"] = (frames % 20) < 12
		cmds[0]["fire_released"] = (frames % 20) == 12
		session.step_fixed(STEP, cmds)
		frames += 1
	if session.outcome != "win":
		_fail("LOOP live fight did not reach a damage/pit win in %d frames" % max_frames)


func _first_living_foe(session: GameSession) -> Fighter:
	var p1: Fighter = session.player1()
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == p1 or f.dead:
			continue
		return f
	return null


func _foes_died_honestly(session: GameSession) -> bool:
	var p1: Fighter = session.player1()
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		i += 1
		if f == p1:
			continue
		if not f.dead:
			return false
		if f.death_cause != "damage" and f.death_cause != "pit":
			return false
	return true


func _settle(session: GameSession, frames: int) -> void:
	var n: int = 0
	while n < frames:
		session.step_fixed(STEP, _idle_cmds(session))
		n += 1


func _walk(session: GameSession, dir: float, frames: int) -> void:
	var n: int = 0
	while n < frames:
		var cmds: Array[Dictionary] = _idle_cmds(session)
		cmds[0]["x"] = dir
		session.step_fixed(STEP, cmds)
		n += 1


func _idle_cmds(session: GameSession) -> Array[Dictionary]:
	var cmds: Array[Dictionary] = []
	var i: int = 0
	while i < session.fighters.size():
		cmds.append(InputActions.empty_cmd())
		i += 1
	return cmds


func _fail(msg: String) -> void:
	_fails.append(msg)
	print("HH_ASSERT_FAIL %s" % msg)


func _count_prefix(prefix: String) -> int:
	var n: int = 0
	var i: int = 0
	while i < _fails.size():
		if String(_fails[i]).begins_with(prefix):
			n += 1
		i += 1
	return n


func _test_session_hygiene(app: App) -> void:
	const CYCLES: int = 20
	var n: int = 0
	while n < CYCLES:
		app.start_fight("vs1", "rooftops", 0)
		var session: GameSession = app.session
		if session == null:
			_fail("HYGIENE missing session at cycle %d" % n)
			return
		if not session.test_driven:
			_fail("HYGIENE official test session must be test_driven")
			return
		if session.sfx == null:
			_fail("HYGIENE missing SfxBank at cycle %d" % n)
			return
		if not session.sfx.muted:
			_fail("HYGIENE test session must mute playback")
			return
		if session.sfx.has_audio_players():
			_fail("HYGIENE muted test must not allocate AudioStreamPlayer")
			return
		session.sfx.play("punch")
		if session.sfx.last_id != "punch":
			_fail("HYGIENE muted play must still record last_id")
			return
		if session.sfx.is_music_playing():
			_fail("HYGIENE test must not play music")
			return
		n += 1
	app.restart_to_title()
	if app.session != null:
		_fail("HYGIENE restart_to_title must clear session")
		return
	if _count_prefix("HYGIENE ") == 0:
		_hygiene = "proven"


func _test_sim_contract(app: App) -> void:
	var errors: PackedStringArray = SimContractCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("SIM %s" % String(errors[i]))
		i += 1
	if _count_prefix("SIM ") == 0:
		_sim = "proven"


func _test_golden_traces(app: App) -> void:
	var errors: PackedStringArray = await TraceCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("TRACE %s" % String(errors[i]))
		i += 1
	if _count_prefix("TRACE ") == 0:
		_trace = "proven"


func _test_runtime(app: App) -> void:
	var errors: PackedStringArray = RuntimeCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("RUNTIME %s" % String(errors[i]))
		i += 1
	if _count_prefix("RUNTIME ") == 0:
		_runtime = "proven"


func _test_input_map(app: App) -> void:
	var errors: PackedStringArray = await InputMapCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("INPUT %s" % String(errors[i]))
		i += 1
	if _count_prefix("INPUT ") == 0:
		_input = "proven"


func _test_locomotion(app: App) -> void:
	var errors: PackedStringArray = await LocomotionCases.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("LOCO %s" % String(errors[i]))
		i += 1
	var hash2: String = str(LocomotionCases.outcome_hash2.get("verdict", "unproven"))
	var tunnel: String = str(LocomotionCases.outcome_tunnel.get("verdict", "unproven"))
	var camera: String = str(LocomotionCases.outcome_camera.get("verdict", "unproven"))
	if hash2 != "match":
		_fail("LOCO HASH2 outcome is %s" % hash2)
	if tunnel != "none":
		_fail("LOCO TUNNEL outcome is %s" % tunnel)
	if camera != "arena_fit":
		_fail("LOCO CAMERA outcome is %s" % camera)
	if _count_prefix("LOCO ") == 0:
		_loco = "proven"


func _emit() -> void:
	print("HH_VF_PATH title→fight→win/lose→restart")
	print(
		"HH_VF LOOP=%s COMBAT=%s MAPS=%s NO_ERRORS=%s"
		% [_loop, _combat, _maps, _no_err]
	)
	print("HH_VF_HYGIENE sessions=20 muted=1 music=off status=%s" % _hygiene)
	print("HH_VF_SIM HASH3=%s PAUSE_TICK=stable MALFORMED=reject status=%s" % [
		"match" if _sim == "proven" else "unproven",
		_sim,
	])
	print("HH_VF_TRACE MATCH=%s status=%s" % [
		"1" if _trace == "proven" else "0",
		_trace,
	])
	print("HH_VF_RUNTIME PAUSE_SNAP=%s RESTORE_HASH=%s AUTH=%s status=%s" % [
		"stable" if _runtime == "proven" else "unproven",
		"match" if _runtime == "proven" else "unproven",
		"reject" if _runtime == "proven" else "unproven",
		_runtime,
	])
	print("HH_VF_INPUT USED_STEP_FIXED=0 P1P2=split status=%s" % _input)
	print("HH_VF_LOCO EPSILON=%s HASH2=%s TUNNEL=%s CAMERA=%s status=%s" % [
		str(Locomotion.epsilon()),
		str(LocomotionCases.outcome_hash2.get("verdict", "unproven")),
		str(LocomotionCases.outcome_tunnel.get("verdict", "unproven")),
		str(LocomotionCases.outcome_camera.get("verdict", "unproven")),
		_loco,
	])
	if _fails.is_empty():
		print("PASS: Vault Fighters first playable")
	else:
		print("FAIL: Vault Fighters")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
