extends SceneTree

const STEP: float = 1.0 / 60.0
const SprintCasesScript: GDScript = preload("res://tests/sprint_cases.gd")
const DiveCasesScript: GDScript = preload("res://tests/dive_cases.gd")
const TraversalCasesScript: GDScript = preload("res://tests/traversal_cases.gd")
const CombatCasesScript: GDScript = preload("res://tests/combat_cases.gd")
const ReactionCasesScript: GDScript = preload("res://tests/reaction_cases.gd")
const AimCasesScript: GDScript = preload("res://tests/aim_cases.gd")
const ExplosiveCasesScript: GDScript = preload("res://tests/explosive_cases.gd")
const RosterCasesScript: GDScript = preload("res://tests/roster_cases.gd")
const BalanceCasesScript: GDScript = preload("res://tests/balance_cases.gd")
const WorldCasesScript: GDScript = preload("res://tests/world_cases.gd")
const BreakCasesScript: GDScript = preload("res://tests/break_cases.gd")
const HazardCasesScript: GDScript = preload("res://tests/hazard_cases.gd")
const MovingCasesScript: GDScript = preload("res://tests/moving_cases.gd")
const EnvCasesScript: GDScript = preload("res://tests/env_cases.gd")
const MapCasesScript: GDScript = preload("res://tests/map_cases.gd")
const _Combat: GDScript = preload("res://src/sim/combat.gd")

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
var _sprint: String = "unproven"
var _dive: String = "unproven"
var _trav: String = "unproven"
var _melee: String = "unproven"
var _react: String = "unproven"
var _aim: String = "unproven"
var _expl: String = "unproven"
var _roster: String = "unproven"
var _balance: String = "unproven"
var _world: String = "unproven"
var _break: String = "unproven"
var _hazard: String = "unproven"
var _moving: String = "unproven"
var _env: String = "unproven"
var _mapschema: String = "unproven"


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
	await _test_sprint(app)
	await _test_dive(app)
	await _test_traversal(app)
	await _test_melee(app)
	await _test_react(app)
	await _test_aim(app)
	await _test_expl(app)
	await _test_roster(app)
	await _test_balance(app)
	await _test_world(app)
	await _test_break(app)
	await _test_hazard(app)
	await _test_moving(app)
	await _test_env(app)
	await _test_mapschema(app)
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
	await process_frame
	await process_frame
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
	var wait: int = 0
	var startup: int = _Combat.startup_ticks(p1.melee_id, "melee")
	var active: int = _Combat.active_ticks(p1.melee_id, "melee")
	while wait < startup + active + 2 and foe.health >= hp0:
		session.step_fixed(STEP, _idle_cmds(session))
		wait += 1
	if foe.health >= hp0:
		_fail("COMBAT melee must deal damage after startup/active")
	if p1.attack_phase == "idle" and wait < startup:
		_fail("COMBAT melee must spend startup frames before damage")
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
	await process_frame
	await process_frame
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
		_place_duel(session, p1, foe)
		p1.facing = 1.0
		p1.aim_dir = Vector2.RIGHT
		p1.last_aim_dir = Vector2.RIGHT
		p1.gun_id = "pistol"
		if p1.ammo < 4:
			p1.ammo = 12
		p1.invuln = 0.2
		p1.grant_invuln_ticks(3)
		var cmds: Array[Dictionary] = _idle_cmds(session)
		cmds[0]["fire_held"] = (frames % 16) < 10
		cmds[0]["fire_released"] = (frames % 16) == 10
		cmds[0]["melee"] = (frames % 8) == 0
		session.step_fixed(STEP, cmds)
		frames += 1
	if session.outcome != "win":
		_fail("LOOP live fight did not reach a damage/pit win in %d frames" % max_frames)


func _place_duel(session: GameSession, p1: Fighter, foe: Fighter) -> void:
	var base: Vector2 = Vector2(80.0, 80.0)
	if session.arena != null and not session.arena.player_spawns.is_empty():
		base = session.arena.player_spawns[0] + Vector2(0.0, -8.0)
	var n: int = 0
	while n < 8 and Maps.solid_at(session.map_id, base):
		base.y -= 1.0
		n += 1
	p1.global_position = base
	foe.global_position = base + Vector2(16.0, 0.0)
	p1.velocity = Vector2.ZERO
	foe.velocity = Vector2.ZERO


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


func _test_sprint(app: App) -> void:
	var errors: PackedStringArray = await SprintCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("SPRINT %s" % String(errors[i]))
		i += 1
	var tap: String = str(SprintCasesScript.outcome_tap.get("verdict", "unproven"))
	var stamina: String = str(SprintCasesScript.outcome_stamina.get("verdict", "unproven"))
	var roll: String = str(SprintCasesScript.outcome_roll.get("verdict", "unproven"))
	var invuln: String = str(SprintCasesScript.outcome_invuln.get("verdict", "unproven"))
	var dup: String = str(SprintCasesScript.outcome_dup.get("verdict", "unproven"))
	var live: String = str(SprintCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(SprintCasesScript.outcome_replay.get("verdict", "unproven"))
	if tap != "pass":
		_fail("SPRINT TAP outcome is %s" % tap)
	if stamina != "pass":
		_fail("SPRINT STAMINA outcome is %s" % stamina)
	if roll != "pass":
		_fail("SPRINT ROLL outcome is %s" % roll)
	if invuln != "pass":
		_fail("SPRINT INVULN outcome is %s" % invuln)
	if dup != "pass":
		_fail("SPRINT DUP outcome is %s" % dup)
	if live != "pass":
		_fail("SPRINT LIVE outcome is %s" % live)
	if replay != "match":
		_fail("SPRINT REPLAY outcome is %s" % replay)
	if _count_prefix("SPRINT ") == 0:
		_sprint = "proven"


func _test_dive(app: App) -> void:
	var errors: PackedStringArray = await DiveCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("DIVE %s" % String(errors[i]))
		i += 1
	var dive: String = str(DiveCasesScript.outcome_dive.get("verdict", "unproven"))
	var kick: String = str(DiveCasesScript.outcome_kick.get("verdict", "unproven"))
	var tackle: String = str(DiveCasesScript.outcome_tackle.get("verdict", "unproven"))
	var fall: String = str(DiveCasesScript.outcome_fall.get("verdict", "unproven"))
	var pit: String = str(DiveCasesScript.outcome_pit.get("verdict", "unproven"))
	var dodge: String = str(DiveCasesScript.outcome_dodge.get("verdict", "unproven"))
	var invuln: String = str(DiveCasesScript.outcome_invuln.get("verdict", "unproven"))
	var dist: String = str(DiveCasesScript.outcome_dist.get("verdict", "unproven"))
	var maps: String = str(DiveCasesScript.outcome_maps.get("verdict", "unproven"))
	var live: String = str(DiveCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(DiveCasesScript.outcome_replay.get("verdict", "unproven"))
	if dive != "pass":
		_fail("DIVE DIVE outcome is %s" % dive)
	if kick != "pass":
		_fail("DIVE KICK outcome is %s" % kick)
	if tackle != "pass":
		_fail("DIVE TACKLE outcome is %s" % tackle)
	if fall != "pass":
		_fail("DIVE FALL outcome is %s" % fall)
	if pit != "pass":
		_fail("DIVE PIT outcome is %s" % pit)
	if dodge != "pass":
		_fail("DIVE DODGE outcome is %s" % dodge)
	if invuln != "pass":
		_fail("DIVE INVULN outcome is %s" % invuln)
	if dist != "pass":
		_fail("DIVE DIST outcome is %s" % dist)
	if maps != "pass":
		_fail("DIVE MAPS outcome is %s" % maps)
	if live != "pass":
		_fail("DIVE LIVE outcome is %s" % live)
	if replay != "match":
		_fail("DIVE REPLAY outcome is %s" % replay)
	if _count_prefix("DIVE ") == 0:
		_dive = "proven"


func _test_traversal(app: App) -> void:
	var errors: PackedStringArray = await TraversalCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("TRAV %s" % String(errors[i]))
		i += 1
	var ladder: String = str(TraversalCasesScript.outcome_ladder.get("verdict", "unproven"))
	var ledge: String = str(TraversalCasesScript.outcome_ledge.get("verdict", "unproven"))
	var drop: String = str(TraversalCasesScript.outcome_drop.get("verdict", "unproven"))
	var block: String = str(TraversalCasesScript.outcome_block.get("verdict", "unproven"))
	var dirs: String = str(TraversalCasesScript.outcome_dirs.get("verdict", "unproven"))
	var maps: String = str(TraversalCasesScript.outcome_maps.get("verdict", "unproven"))
	var stuck: String = str(TraversalCasesScript.outcome_stuck.get("verdict", "unproven"))
	var contact: String = str(TraversalCasesScript.outcome_contact.get("verdict", "unproven"))
	var live: String = str(TraversalCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(TraversalCasesScript.outcome_replay.get("verdict", "unproven"))
	if ladder != "pass":
		_fail("TRAV LADDER outcome is %s" % ladder)
	if ledge != "pass":
		_fail("TRAV LEDGE outcome is %s" % ledge)
	if drop != "pass":
		_fail("TRAV DROP outcome is %s" % drop)
	if block != "pass":
		_fail("TRAV BLOCK outcome is %s" % block)
	if dirs != "pass":
		_fail("TRAV DIRS outcome is %s" % dirs)
	if maps != "fixtures_only":
		_fail("TRAV MAPS outcome is %s (stage maps not claimed)" % maps)
	if stuck != "pass":
		_fail("TRAV STUCK outcome is %s" % stuck)
	if contact != "pass":
		_fail("TRAV CONTACT outcome is %s" % contact)
	if live != "pass":
		_fail("TRAV LIVE outcome is %s" % live)
	if replay != "match":
		_fail("TRAV REPLAY outcome is %s" % replay)
	if _count_prefix("TRAV ") == 0:
		_trav = "proven"


func _test_melee(app: App) -> void:
	var errors: PackedStringArray = await CombatCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("MELEE %s" % String(errors[i]))
		i += 1
	var hit: String = str(CombatCasesScript.outcome_hit.get("verdict", "unproven"))
	var miss: String = str(CombatCasesScript.outcome_miss.get("verdict", "unproven"))
	var behind: String = str(CombatCasesScript.outcome_behind.get("verdict", "unproven"))
	var above: String = str(CombatCasesScript.outcome_above.get("verdict", "unproven"))
	var below: String = str(CombatCasesScript.outcome_below.get("verdict", "unproven"))
	var once: String = str(CombatCasesScript.outcome_once.get("verdict", "unproven"))
	var snap: String = str(CombatCasesScript.outcome_snap.get("verdict", "unproven"))
	var pause: String = str(CombatCasesScript.outcome_pause.get("verdict", "unproven"))
	var live: String = str(CombatCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(CombatCasesScript.outcome_replay.get("verdict", "unproven"))
	var phases: String = str(CombatCasesScript.outcome_phases.get("verdict", "unproven"))
	var reach: String = str(CombatCasesScript.outcome_reach.get("verdict", "unproven"))
	var ff: String = str(CombatCasesScript.outcome_ff.get("verdict", "unproven"))
	var hitstop: String = str(CombatCasesScript.outcome_hitstop.get("verdict", "unproven"))
	var crouch: String = str(CombatCasesScript.outcome_crouch.get("verdict", "unproven"))
	var kick: String = str(CombatCasesScript.outcome_kick.get("verdict", "unproven"))
	if hit != "pass":
		_fail("MELEE HIT outcome is %s" % hit)
	if miss != "pass":
		_fail("MELEE MISS outcome is %s" % miss)
	if behind != "pass":
		_fail("MELEE BEHIND outcome is %s" % behind)
	if above != "pass":
		_fail("MELEE ABOVE outcome is %s" % above)
	if below != "pass":
		_fail("MELEE BELOW outcome is %s" % below)
	if once != "pass":
		_fail("MELEE ONCE outcome is %s" % once)
	if snap != "pass":
		_fail("MELEE SNAP outcome is %s" % snap)
	if pause != "pass":
		_fail("MELEE PAUSE outcome is %s" % pause)
	if live != "pass":
		_fail("MELEE LIVE outcome is %s" % live)
	if replay != "match":
		_fail("MELEE REPLAY outcome is %s" % replay)
	if phases != "pass":
		_fail("MELEE PHASES outcome is %s" % phases)
	if reach != "pass":
		_fail("MELEE REACH outcome is %s" % reach)
	if ff != "pass":
		_fail("MELEE FF outcome is %s" % ff)
	if hitstop != "pass":
		_fail("MELEE HITSTOP outcome is %s" % hitstop)
	if crouch != "pass":
		_fail("MELEE CROUCH outcome is %s" % crouch)
	if kick != "pass":
		_fail("MELEE KICK outcome is %s" % kick)
	if _count_prefix("MELEE ") == 0:
		_melee = "proven"


func _test_react(app: App) -> void:
	var errors: PackedStringArray = await ReactionCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("REACT %s" % String(errors[i]))
		i += 1
	var damage: String = str(ReactionCasesScript.outcome_damage.get("verdict", "unproven"))
	var knock: String = str(ReactionCasesScript.outcome_knock.get("verdict", "unproven"))
	var air: String = str(ReactionCasesScript.outcome_air.get("verdict", "unproven"))
	var down: String = str(ReactionCasesScript.outcome_down.get("verdict", "unproven"))
	var getup: String = str(ReactionCasesScript.outcome_getup.get("verdict", "unproven"))
	var invuln: String = str(ReactionCasesScript.outcome_invuln.get("verdict", "unproven"))
	var chain: String = str(ReactionCasesScript.outcome_chain.get("verdict", "unproven"))
	var disarm: String = str(ReactionCasesScript.outcome_disarm.get("verdict", "unproven"))
	var drop: String = str(ReactionCasesScript.outcome_drop.get("verdict", "unproven"))
	var death: String = str(ReactionCasesScript.outcome_death.get("verdict", "unproven"))
	var events: String = str(ReactionCasesScript.outcome_events.get("verdict", "unproven"))
	var live: String = str(ReactionCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(ReactionCasesScript.outcome_replay.get("verdict", "unproven"))
	if damage != "pass":
		_fail("REACT DAMAGE outcome is %s" % damage)
	if knock != "pass":
		_fail("REACT KNOCK outcome is %s" % knock)
	if air != "pass":
		_fail("REACT AIR outcome is %s" % air)
	if down != "pass":
		_fail("REACT DOWN outcome is %s" % down)
	if getup != "pass":
		_fail("REACT GETUP outcome is %s" % getup)
	if invuln != "pass":
		_fail("REACT INVULN outcome is %s" % invuln)
	if chain != "pass":
		_fail("REACT CHAIN outcome is %s" % chain)
	if disarm != "pass":
		_fail("REACT DISARM outcome is %s" % disarm)
	if drop != "pass":
		_fail("REACT DROP outcome is %s" % drop)
	if death != "pass":
		_fail("REACT DEATH outcome is %s" % death)
	if events != "pass":
		_fail("REACT EVENTS outcome is %s" % events)
	if live != "pass":
		_fail("REACT LIVE outcome is %s" % live)
	if replay != "match":
		_fail("REACT REPLAY outcome is %s" % replay)
	if _count_prefix("REACT ") == 0:
		_react = "proven"


func _test_aim(app: App) -> void:
	var errors: PackedStringArray = await AimCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("AIM %s" % String(errors[i]))
		i += 1
	var hold: String = str(AimCasesScript.outcome_hold.get("verdict", "unproven"))
	var dirs: String = str(AimCasesScript.outcome_dirs.get("verdict", "unproven"))
	var semi: String = str(AimCasesScript.outcome_semi.get("verdict", "unproven"))
	var auto: String = str(AimCasesScript.outcome_auto.get("verdict", "unproven"))
	var ammo: String = str(AimCasesScript.outcome_ammo.get("verdict", "unproven"))
	var muzzle: String = str(AimCasesScript.outcome_muzzle.get("verdict", "unproven"))
	var recoil: String = str(AimCasesScript.outcome_recoil.get("verdict", "unproven"))
	var data: String = str(AimCasesScript.outcome_data.get("verdict", "unproven"))
	var sweep: String = str(AimCasesScript.outcome_sweep.get("verdict", "unproven"))
	var live: String = str(AimCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(AimCasesScript.outcome_replay.get("verdict", "unproven"))
	if hold != "pass":
		_fail("AIM HOLD outcome is %s" % hold)
	if dirs != "pass":
		_fail("AIM DIRS outcome is %s" % dirs)
	if semi != "pass":
		_fail("AIM SEMI outcome is %s" % semi)
	if auto != "pass":
		_fail("AIM AUTO outcome is %s" % auto)
	if ammo != "pass":
		_fail("AIM AMMO outcome is %s" % ammo)
	if muzzle != "pass":
		_fail("AIM MUZZLE outcome is %s" % muzzle)
	if recoil != "pass":
		_fail("AIM RECOIL outcome is %s" % recoil)
	if data != "pass":
		_fail("AIM DATA outcome is %s" % data)
	if sweep != "pass":
		_fail("AIM SWEEP outcome is %s" % sweep)
	if live != "pass":
		_fail("AIM LIVE outcome is %s" % live)
	if replay != "match":
		_fail("AIM REPLAY outcome is %s" % replay)
	if _count_prefix("AIM ") == 0:
		_aim = "proven"


func _test_expl(app: App) -> void:
	var errors: PackedStringArray = await ExplosiveCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("EXPL %s" % String(errors[i]))
		i += 1
	var hold: String = str(ExplosiveCasesScript.outcome_hold.get("verdict", "unproven"))
	var throwv: String = str(ExplosiveCasesScript.outcome_throw.get("verdict", "unproven"))
	var arc: String = str(ExplosiveCasesScript.outcome_arc.get("verdict", "unproven"))
	var bounce: String = str(ExplosiveCasesScript.outcome_bounce.get("verdict", "unproven"))
	var fuse: String = str(ExplosiveCasesScript.outcome_fuse.get("verdict", "unproven"))
	var falloff: String = str(ExplosiveCasesScript.outcome_falloff.get("verdict", "unproven"))
	var owner: String = str(ExplosiveCasesScript.outcome_owner.get("verdict", "unproven"))
	var once: String = str(ExplosiveCasesScript.outcome_once.get("verdict", "unproven"))
	var timeout: String = str(ExplosiveCasesScript.outcome_timeout.get("verdict", "unproven"))
	var sweep: String = str(ExplosiveCasesScript.outcome_sweep.get("verdict", "unproven"))
	var data: String = str(ExplosiveCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(ExplosiveCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(ExplosiveCasesScript.outcome_replay.get("verdict", "unproven"))
	if hold != "pass":
		_fail("EXPL HOLD outcome is %s" % hold)
	if throwv != "pass":
		_fail("EXPL THROW outcome is %s" % throwv)
	if arc != "pass":
		_fail("EXPL ARC outcome is %s" % arc)
	if bounce != "pass":
		_fail("EXPL BOUNCE outcome is %s" % bounce)
	if fuse != "pass":
		_fail("EXPL FUSE outcome is %s" % fuse)
	if falloff != "pass":
		_fail("EXPL FALLOFF outcome is %s" % falloff)
	if owner != "pass":
		_fail("EXPL OWNER outcome is %s" % owner)
	if once != "pass":
		_fail("EXPL ONCE outcome is %s" % once)
	if timeout != "pass":
		_fail("EXPL TIMEOUT outcome is %s" % timeout)
	if sweep != "pass":
		_fail("EXPL SWEEP outcome is %s" % sweep)
	if data != "pass":
		_fail("EXPL DATA outcome is %s" % data)
	if live != "pass":
		_fail("EXPL LIVE outcome is %s" % live)
	if replay != "match":
		_fail("EXPL REPLAY outcome is %s" % replay)
	if _count_prefix("EXPL ") == 0:
		_expl = "proven"


func _test_roster(app: App) -> void:
	var errors: PackedStringArray = await RosterCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("ROSTER %s" % String(errors[i]))
		i += 1
	var schema: String = str(RosterCasesScript.outcome_schema.get("verdict", "unproven"))
	var spawn: String = str(RosterCasesScript.outcome_spawn.get("verdict", "unproven"))
	var equip: String = str(RosterCasesScript.outcome_equip.get("verdict", "unproven"))
	var attack: String = str(RosterCasesScript.outcome_attack.get("verdict", "unproven"))
	var dropv: String = str(RosterCasesScript.outcome_drop.get("verdict", "unproven"))
	var ser: String = str(RosterCasesScript.outcome_serialize.get("verdict", "unproven"))
	var keep: String = str(RosterCasesScript.outcome_keep.get("verdict", "unproven"))
	var ammo: String = str(RosterCasesScript.outcome_ammo.get("verdict", "unproven"))
	var data: String = str(RosterCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(RosterCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(RosterCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("ROSTER SCHEMA outcome is %s" % schema)
	if spawn != "pass":
		_fail("ROSTER SPAWN outcome is %s" % spawn)
	if equip != "pass":
		_fail("ROSTER EQUIP outcome is %s" % equip)
	if attack != "pass":
		_fail("ROSTER ATTACK outcome is %s" % attack)
	if dropv != "pass":
		_fail("ROSTER DROP outcome is %s" % dropv)
	if ser != "pass":
		_fail("ROSTER SERIALIZE outcome is %s" % ser)
	if keep != "pass":
		_fail("ROSTER KEEP outcome is %s" % keep)
	if ammo != "pass":
		_fail("ROSTER AMMO outcome is %s" % ammo)
	if data != "pass":
		_fail("ROSTER DATA outcome is %s" % data)
	if live != "pass":
		_fail("ROSTER LIVE outcome is %s" % live)
	if replay != "match":
		_fail("ROSTER REPLAY outcome is %s" % replay)
	if _count_prefix("ROSTER ") == 0:
		_roster = "proven"


func _test_balance(app: App) -> void:
	var errors: PackedStringArray = await BalanceCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("BALANCE %s" % String(errors[i]))
		i += 1
	var schema: String = str(BalanceCasesScript.outcome_schema.get("verdict", "unproven"))
	var batch: String = str(BalanceCasesScript.outcome_batch.get("verdict", "unproven"))
	var dist: String = str(BalanceCasesScript.outcome_dist.get("verdict", "unproven"))
	var dom: String = str(BalanceCasesScript.outcome_dom.get("verdict", "unproven"))
	var melee: String = str(BalanceCasesScript.outcome_melee.get("verdict", "unproven"))
	var high: String = str(BalanceCasesScript.outcome_high.get("verdict", "unproven"))
	var overcap: String = str(BalanceCasesScript.outcome_overcap.get("verdict", "unproven"))
	var pit: String = str(BalanceCasesScript.outcome_pit.get("verdict", "unproven"))
	var chain: String = str(BalanceCasesScript.outcome_chain.get("verdict", "unproven"))
	var ff: String = str(BalanceCasesScript.outcome_ff.get("verdict", "unproven"))
	var stamina: String = str(BalanceCasesScript.outcome_stamina.get("verdict", "unproven"))
	var data: String = str(BalanceCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(BalanceCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(BalanceCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("BALANCE SCHEMA outcome is %s" % schema)
	if batch != "pass":
		_fail("BALANCE BATCH outcome is %s" % batch)
	if dist != "pass":
		_fail("BALANCE DIST outcome is %s" % dist)
	if dom != "pass":
		_fail("BALANCE DOM outcome is %s" % dom)
	if melee != "pass":
		_fail("BALANCE MELEE outcome is %s" % melee)
	if high != "pass":
		_fail("BALANCE HIGH outcome is %s" % high)
	if overcap != "pass":
		_fail("BALANCE OVERCAP outcome is %s" % overcap)
	if pit != "pass":
		_fail("BALANCE PIT outcome is %s" % pit)
	if chain != "pass":
		_fail("BALANCE CHAIN outcome is %s" % chain)
	if ff != "pass":
		_fail("BALANCE FF outcome is %s" % ff)
	if stamina != "pass":
		_fail("BALANCE STAMINA outcome is %s" % stamina)
	if data != "pass":
		_fail("BALANCE DATA outcome is %s" % data)
	if live != "pass":
		_fail("BALANCE LIVE outcome is %s" % live)
	if replay != "match":
		_fail("BALANCE REPLAY outcome is %s" % replay)
	if _count_prefix("BALANCE ") == 0:
		_balance = "proven"


func _test_world(app: App) -> void:
	var errors: PackedStringArray = await WorldCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("WORLD %s" % String(errors[i]))
		i += 1
	var schema: String = str(WorldCasesScript.outcome_schema.get("verdict", "unproven"))
	var layers: String = str(WorldCasesScript.outcome_layers.get("verdict", "unproven"))
	var spawn: String = str(WorldCasesScript.outcome_spawn.get("verdict", "unproven"))
	var hashv: String = str(WorldCasesScript.outcome_hash.get("verdict", "unproven"))
	var orphan: String = str(WorldCasesScript.outcome_orphan.get("verdict", "unproven"))
	var pathv: String = str(WorldCasesScript.outcome_path.get("verdict", "unproven"))
	var present: String = str(WorldCasesScript.outcome_present.get("verdict", "unproven"))
	var author: String = str(WorldCasesScript.outcome_author.get("verdict", "unproven"))
	var data: String = str(WorldCasesScript.outcome_data.get("verdict", "unproven"))
	var live: String = str(WorldCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(WorldCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema != "pass":
		_fail("WORLD SCHEMA outcome is %s" % schema)
	if layers != "pass":
		_fail("WORLD LAYERS outcome is %s" % layers)
	if spawn != "pass":
		_fail("WORLD SPAWN outcome is %s" % spawn)
	if hashv != "pass":
		_fail("WORLD HASH outcome is %s" % hashv)
	if orphan != "pass":
		_fail("WORLD ORPHAN outcome is %s" % orphan)
	if pathv != "pass":
		_fail("WORLD PATH outcome is %s" % pathv)
	if present != "pass":
		_fail("WORLD PRESENT outcome is %s" % present)
	if author != "pass":
		_fail("WORLD AUTHOR outcome is %s" % author)
	if data != "pass":
		_fail("WORLD DATA outcome is %s" % data)
	if live != "pass":
		_fail("WORLD LIVE outcome is %s" % live)
	if replay != "match":
		_fail("WORLD REPLAY outcome is %s" % replay)
	if _count_prefix("WORLD ") == 0:
		_world = "proven"


func _test_break(app: App) -> void:
	var errors: PackedStringArray = await BreakCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("BREAK %s" % String(errors[i]))
		i += 1
	var data: String = str(BreakCasesScript.outcome_data.get("verdict", "unproven"))
	var brk: String = str(BreakCasesScript.outcome_break.get("verdict", "unproven"))
	var debris: String = str(BreakCasesScript.outcome_debris.get("verdict", "unproven"))
	var passv: String = str(BreakCasesScript.outcome_pass.get("verdict", "unproven"))
	var ghost: String = str(BreakCasesScript.outcome_ghost.get("verdict", "unproven"))
	var melee: String = str(BreakCasesScript.outcome_melee.get("verdict", "unproven"))
	var shove: String = str(BreakCasesScript.outcome_shove.get("verdict", "unproven"))
	var throwv: String = str(BreakCasesScript.outcome_throw.get("verdict", "unproven"))
	var tactic: String = str(BreakCasesScript.outcome_tactic.get("verdict", "unproven"))
	var live: String = str(BreakCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(BreakCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("BREAK DATA outcome is %s" % data)
	if brk != "pass":
		_fail("BREAK BREAK outcome is %s" % brk)
	if debris != "pass":
		_fail("BREAK DEBRIS outcome is %s" % debris)
	if passv != "pass":
		_fail("BREAK PASS outcome is %s" % passv)
	if ghost != "pass":
		_fail("BREAK GHOST outcome is %s" % ghost)
	if melee != "pass":
		_fail("BREAK MELEE outcome is %s" % melee)
	if shove != "pass":
		_fail("BREAK SHOVE outcome is %s" % shove)
	if throwv != "pass":
		_fail("BREAK THROW outcome is %s" % throwv)
	if tactic != "pass":
		_fail("BREAK TACTIC outcome is %s" % tactic)
	if live != "pass":
		_fail("BREAK LIVE outcome is %s" % live)
	if replay != "match":
		_fail("BREAK REPLAY outcome is %s" % replay)
	if _count_prefix("BREAK ") == 0:
		_break = "proven"


func _test_hazard(app: App) -> void:
	var errors: PackedStringArray = await HazardCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("HAZARD %s" % String(errors[i]))
		i += 1
	var data: String = str(HazardCasesScript.outcome_data.get("verdict", "unproven"))
	var chain: String = str(HazardCasesScript.outcome_chain.get("verdict", "unproven"))
	var fire: String = str(HazardCasesScript.outcome_fire.get("verdict", "unproven"))
	var cleanup: String = str(HazardCasesScript.outcome_cleanup.get("verdict", "unproven"))
	var roll: String = str(HazardCasesScript.outcome_roll.get("verdict", "unproven"))
	var dup: String = str(HazardCasesScript.outcome_dup.get("verdict", "unproven"))
	var vfx: String = str(HazardCasesScript.outcome_vfx.get("verdict", "unproven"))
	var hang: String = str(HazardCasesScript.outcome_hang.get("verdict", "unproven"))
	var live: String = str(HazardCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(HazardCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("HAZARD DATA outcome is %s" % data)
	if chain != "pass":
		_fail("HAZARD CHAIN outcome is %s" % chain)
	if fire != "pass":
		_fail("HAZARD FIRE outcome is %s" % fire)
	if cleanup != "pass":
		_fail("HAZARD CLEANUP outcome is %s" % cleanup)
	if roll != "pass":
		_fail("HAZARD ROLL outcome is %s" % roll)
	if dup != "pass":
		_fail("HAZARD DUP outcome is %s" % dup)
	if vfx != "pass":
		_fail("HAZARD VFX outcome is %s" % vfx)
	if hang != "pass":
		_fail("HAZARD HANG outcome is %s" % hang)
	if live != "pass":
		_fail("HAZARD LIVE outcome is %s" % live)
	if replay != "match":
		_fail("HAZARD REPLAY outcome is %s" % replay)
	if _count_prefix("HAZARD ") == 0:
		_hazard = "proven"


func _test_moving(app: App) -> void:
	var errors: PackedStringArray = await MovingCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("MOVING %s" % String(errors[i]))
		i += 1
	var data: String = str(MovingCasesScript.outcome_data.get("verdict", "unproven"))
	var ride: String = str(MovingCasesScript.outcome_ride.get("verdict", "unproven"))
	var carry: String = str(MovingCasesScript.outcome_carry.get("verdict", "unproven"))
	var drop: String = str(MovingCasesScript.outcome_drop.get("verdict", "unproven"))
	var door: String = str(MovingCasesScript.outcome_door.get("verdict", "unproven"))
	var trigger: String = str(MovingCasesScript.outcome_trigger.get("verdict", "unproven"))
	var pause: String = str(MovingCasesScript.outcome_pause.get("verdict", "unproven"))
	var reset: String = str(MovingCasesScript.outcome_reset.get("verdict", "unproven"))
	var live: String = str(MovingCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(MovingCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("MOVING DATA outcome is %s" % data)
	if ride != "pass":
		_fail("MOVING RIDE outcome is %s" % ride)
	if carry != "pass":
		_fail("MOVING CARRY outcome is %s" % carry)
	if drop != "pass":
		_fail("MOVING DROP outcome is %s" % drop)
	if door != "pass":
		_fail("MOVING DOOR outcome is %s" % door)
	if trigger != "pass":
		_fail("MOVING TRIGGER outcome is %s" % trigger)
	if pause != "pass":
		_fail("MOVING PAUSE outcome is %s" % pause)
	if reset != "pass":
		_fail("MOVING RESET outcome is %s" % reset)
	if live != "pass":
		_fail("MOVING LIVE outcome is %s" % live)
	if replay != "match":
		_fail("MOVING REPLAY outcome is %s" % replay)
	if _count_prefix("MOVING ") == 0:
		_moving = "proven"


func _test_env(app: App) -> void:
	var errors: PackedStringArray = await EnvCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("ENV %s" % String(errors[i]))
		i += 1
	var data: String = str(EnvCasesScript.outcome_data.get("verdict", "unproven"))
	var instant: String = str(EnvCasesScript.outcome_instant.get("verdict", "unproven"))
	var toxic: String = str(EnvCasesScript.outcome_toxic.get("verdict", "unproven"))
	var water: String = str(EnvCasesScript.outcome_water.get("verdict", "unproven"))
	var rotor: String = str(EnvCasesScript.outcome_rotor.get("verdict", "unproven"))
	var fall: String = str(EnvCasesScript.outcome_fall.get("verdict", "unproven"))
	var spawn: String = str(EnvCasesScript.outcome_spawn.get("verdict", "unproven"))
	var pause: String = str(EnvCasesScript.outcome_pause.get("verdict", "unproven"))
	var reset: String = str(EnvCasesScript.outcome_reset.get("verdict", "unproven"))
	var live: String = str(EnvCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(EnvCasesScript.outcome_replay.get("verdict", "unproven"))
	if data != "pass":
		_fail("ENV DATA outcome is %s" % data)
	if instant != "pass":
		_fail("ENV INSTANT outcome is %s" % instant)
	if toxic != "pass":
		_fail("ENV TOXIC outcome is %s" % toxic)
	if water != "pass":
		_fail("ENV WATER outcome is %s" % water)
	if rotor != "pass":
		_fail("ENV ROTOR outcome is %s" % rotor)
	if fall != "pass":
		_fail("ENV FALL outcome is %s" % fall)
	if spawn != "pass":
		_fail("ENV SPAWN outcome is %s" % spawn)
	if pause != "pass":
		_fail("ENV PAUSE outcome is %s" % pause)
	if reset != "pass":
		_fail("ENV RESET outcome is %s" % reset)
	if live != "pass":
		_fail("ENV LIVE outcome is %s" % live)
	if replay != "match":
		_fail("ENV REPLAY outcome is %s" % replay)
	if _count_prefix("ENV ") == 0:
		_env = "proven"


func _test_mapschema(app: App) -> void:
	var errors: PackedStringArray = await MapCasesScript.run_all(app)
	var i: int = 0
	while i < errors.size():
		_fail("MAPSCHEMA %s" % String(errors[i]))
		i += 1
	var schema_v: String = str(MapCasesScript.outcome_schema.get("verdict", "unproven"))
	var roundtrip: String = str(MapCasesScript.outcome_roundtrip.get("verdict", "unproven"))
	var graph: String = str(MapCasesScript.outcome_graph.get("verdict", "unproven"))
	var reject: String = str(MapCasesScript.outcome_reject.get("verdict", "unproven"))
	var author: String = str(MapCasesScript.outcome_author.get("verdict", "unproven"))
	var width_v: String = str(MapCasesScript.outcome_width.get("verdict", "unproven"))
	var spawn_v: String = str(MapCasesScript.outcome_spawn.get("verdict", "unproven"))
	var pit_v: String = str(MapCasesScript.outcome_pit.get("verdict", "unproven"))
	var camera_v: String = str(MapCasesScript.outcome_camera.get("verdict", "unproven"))
	var overlap_v: String = str(MapCasesScript.outcome_overlap.get("verdict", "unproven"))
	var live: String = str(MapCasesScript.outcome_live.get("verdict", "unproven"))
	var replay: String = str(MapCasesScript.outcome_replay.get("verdict", "unproven"))
	if schema_v != "pass":
		_fail("MAPSCHEMA SCHEMA outcome is %s" % schema_v)
	if roundtrip != "pass":
		_fail("MAPSCHEMA ROUNDTRIP outcome is %s" % roundtrip)
	if graph != "pass":
		_fail("MAPSCHEMA GRAPH outcome is %s" % graph)
	if reject != "pass":
		_fail("MAPSCHEMA REJECT outcome is %s" % reject)
	if author != "pass":
		_fail("MAPSCHEMA AUTHOR outcome is %s" % author)
	if width_v != "pass":
		_fail("MAPSCHEMA WIDTH outcome is %s" % width_v)
	if spawn_v != "pass":
		_fail("MAPSCHEMA SPAWN outcome is %s" % spawn_v)
	if pit_v != "pass":
		_fail("MAPSCHEMA PIT outcome is %s" % pit_v)
	if camera_v != "pass":
		_fail("MAPSCHEMA CAMERA outcome is %s" % camera_v)
	if overlap_v != "pass":
		_fail("MAPSCHEMA OVERLAP outcome is %s" % overlap_v)
	if live != "pass":
		_fail("MAPSCHEMA LIVE outcome is %s" % live)
	if replay != "match":
		_fail("MAPSCHEMA REPLAY outcome is %s" % replay)
	if _count_prefix("MAPSCHEMA ") == 0:
		_mapschema = "proven"


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
	print(
		"HH_VF_SPRINT TAP=%s STAMINA=%s ROLL=%s INVULN=%s DUP=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(SprintCasesScript.outcome_tap.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_stamina.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_roll.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_invuln.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_dup.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_live.get("verdict", "unproven")),
			str(SprintCasesScript.outcome_replay.get("verdict", "unproven")),
			SprintCasesScript.used_apply_frames_succeeded,
			SprintCasesScript.used_apply_frames_attempted,
			_sprint,
		]
	)
	print(
		"HH_VF_DIVE DIVE=%s KICK=%s TACKLE=%s FALL=%s PIT=%s DODGE=%s INVULN=%s DIST=%s MAPS=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(DiveCasesScript.outcome_dive.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_kick.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_tackle.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_fall.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_pit.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_dodge.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_invuln.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_dist.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_maps.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_live.get("verdict", "unproven")),
			str(DiveCasesScript.outcome_replay.get("verdict", "unproven")),
			DiveCasesScript.used_apply_frames_succeeded,
			DiveCasesScript.used_apply_frames_attempted,
			_dive,
		]
	)
	print(
		"HH_VF_MELEE HIT=%s MISS=%s BEHIND=%s ABOVE=%s BELOW=%s ONCE=%s SNAP=%s PAUSE=%s LIVE=%s REPLAY=%s PHASES=%s REACH=%s FF=%s HITSTOP=%s CROUCH=%s KICK=%s APPLY=%d/%d status=%s"
		% [
			str(CombatCasesScript.outcome_hit.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_miss.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_behind.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_above.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_below.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_once.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_snap.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_pause.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_live.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_replay.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_phases.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_reach.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_ff.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_hitstop.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_crouch.get("verdict", "unproven")),
			str(CombatCasesScript.outcome_kick.get("verdict", "unproven")),
			CombatCasesScript.used_apply_frames_succeeded,
			CombatCasesScript.used_apply_frames_attempted,
			_melee,
		]
	)
	print(
		"HH_VF_REACT DAMAGE=%s KNOCK=%s AIR=%s DOWN=%s GETUP=%s INVULN=%s CHAIN=%s DISARM=%s DROP=%s DEATH=%s EVENTS=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(ReactionCasesScript.outcome_damage.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_knock.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_air.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_down.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_getup.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_invuln.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_chain.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_disarm.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_drop.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_death.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_events.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_live.get("verdict", "unproven")),
			str(ReactionCasesScript.outcome_replay.get("verdict", "unproven")),
			ReactionCasesScript.used_apply_frames_succeeded,
			ReactionCasesScript.used_apply_frames_attempted,
			_react,
		]
	)
	print(
		"HH_VF_AIM HOLD=%s DIRS=%s SEMI=%s AUTO=%s AMMO=%s MUZZLE=%s RECOIL=%s DATA=%s SWEEP=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(AimCasesScript.outcome_hold.get("verdict", "unproven")),
			str(AimCasesScript.outcome_dirs.get("verdict", "unproven")),
			str(AimCasesScript.outcome_semi.get("verdict", "unproven")),
			str(AimCasesScript.outcome_auto.get("verdict", "unproven")),
			str(AimCasesScript.outcome_ammo.get("verdict", "unproven")),
			str(AimCasesScript.outcome_muzzle.get("verdict", "unproven")),
			str(AimCasesScript.outcome_recoil.get("verdict", "unproven")),
			str(AimCasesScript.outcome_data.get("verdict", "unproven")),
			str(AimCasesScript.outcome_sweep.get("verdict", "unproven")),
			str(AimCasesScript.outcome_live.get("verdict", "unproven")),
			str(AimCasesScript.outcome_replay.get("verdict", "unproven")),
			AimCasesScript.used_apply_frames_succeeded,
			AimCasesScript.used_apply_frames_attempted,
			_aim,
		]
	)
	print(
		"HH_VF_EXPL HOLD=%s THROW=%s ARC=%s BOUNCE=%s FUSE=%s FALLOFF=%s OWNER=%s ONCE=%s TIMEOUT=%s SWEEP=%s DATA=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(ExplosiveCasesScript.outcome_hold.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_throw.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_arc.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_bounce.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_fuse.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_falloff.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_owner.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_once.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_timeout.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_sweep.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_data.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_live.get("verdict", "unproven")),
			str(ExplosiveCasesScript.outcome_replay.get("verdict", "unproven")),
			ExplosiveCasesScript.used_apply_frames_succeeded,
			ExplosiveCasesScript.used_apply_frames_attempted,
			_expl,
		]
	)
	print(
		"HH_VF_ROSTER SCHEMA=%s SPAWN=%s EQUIP=%s ATTACK=%s DROP=%s SERIALIZE=%s KEEP=%s AMMO=%s DATA=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(RosterCasesScript.outcome_schema.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_spawn.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_equip.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_attack.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_drop.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_serialize.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_keep.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_ammo.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_data.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_live.get("verdict", "unproven")),
			str(RosterCasesScript.outcome_replay.get("verdict", "unproven")),
			RosterCasesScript.used_apply_frames_succeeded,
			RosterCasesScript.used_apply_frames_attempted,
			_roster,
		]
	)
	print(
		"HH_VF_BALANCE SCHEMA=%s BATCH=%s DIST=%s DOM=%s MELEE=%s HIGH=%s OVERCAP=%s PIT=%s CHAIN=%s FF=%s STAMINA=%s DATA=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(BalanceCasesScript.outcome_schema.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_batch.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_dist.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_dom.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_melee.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_high.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_overcap.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_pit.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_chain.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_ff.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_stamina.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_data.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_live.get("verdict", "unproven")),
			str(BalanceCasesScript.outcome_replay.get("verdict", "unproven")),
			BalanceCasesScript.used_apply_frames_succeeded,
			BalanceCasesScript.used_apply_frames_attempted,
			_balance,
		]
	)
	print(
		"HH_VF_WORLD SCHEMA=%s LAYERS=%s SPAWN=%s HASH=%s ORPHAN=%s PATH=%s PRESENT=%s AUTHOR=%s DATA=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(WorldCasesScript.outcome_schema.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_layers.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_spawn.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_hash.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_orphan.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_path.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_present.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_author.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_data.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_live.get("verdict", "unproven")),
			str(WorldCasesScript.outcome_replay.get("verdict", "unproven")),
			WorldCasesScript.used_apply_frames_succeeded,
			WorldCasesScript.used_apply_frames_attempted,
			_world,
		]
	)
	print(
		"HH_VF_BREAK DATA=%s BREAK=%s DEBRIS=%s PASS=%s GHOST=%s MELEE=%s SHOVE=%s THROW=%s TACTIC=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(BreakCasesScript.outcome_data.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_break.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_debris.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_pass.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_ghost.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_melee.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_shove.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_throw.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_tactic.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_live.get("verdict", "unproven")),
			str(BreakCasesScript.outcome_replay.get("verdict", "unproven")),
			BreakCasesScript.used_apply_frames_succeeded,
			BreakCasesScript.used_apply_frames_attempted,
			_break,
		]
	)
	print(
		"HH_VF_HAZARD DATA=%s CHAIN=%s FIRE=%s CLEANUP=%s ROLL=%s DUP=%s VFX=%s HANG=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(HazardCasesScript.outcome_data.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_chain.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_fire.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_cleanup.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_roll.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_dup.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_vfx.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_hang.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_live.get("verdict", "unproven")),
			str(HazardCasesScript.outcome_replay.get("verdict", "unproven")),
			HazardCasesScript.used_apply_frames_succeeded,
			HazardCasesScript.used_apply_frames_attempted,
			_hazard,
		]
	)
	print(
		"HH_VF_MOVING DATA=%s RIDE=%s RIDE_SOURCE=outcome_ride CARRY=%s DROP=%s DOOR=%s TRIGGER=%s PAUSE=%s RESET=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(MovingCasesScript.outcome_data.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_ride.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_carry.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_drop.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_door.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_trigger.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_pause.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_reset.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_live.get("verdict", "unproven")),
			str(MovingCasesScript.outcome_replay.get("verdict", "unproven")),
			MovingCasesScript.used_apply_frames_succeeded,
			MovingCasesScript.used_apply_frames_attempted,
			_moving,
		]
	)
	print(
		"HH_VF_ENV DATA=%s INSTANT=%s INSTANT_SOURCE=outcome_instant TOXIC=%s WATER=%s ROTOR=%s FALL=%s SPAWN=%s PAUSE=%s RESET=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(EnvCasesScript.outcome_data.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_instant.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_toxic.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_water.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_rotor.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_fall.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_spawn.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_pause.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_reset.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_live.get("verdict", "unproven")),
			str(EnvCasesScript.outcome_replay.get("verdict", "unproven")),
			EnvCasesScript.used_apply_frames_succeeded,
			EnvCasesScript.used_apply_frames_attempted,
			_env,
		]
	)
	print(
		"HH_VF_MAP SCHEMA=%s SCHEMA_SOURCE=outcome_schema ROUNDTRIP=%s ROUNDTRIP_SOURCE=outcome_roundtrip GRAPH=%s GRAPH_SOURCE=outcome_graph REJECT=%s REJECT_SOURCE=outcome_reject AUTHOR=%s AUTHOR_SOURCE=outcome_author WIDTH=%s SPAWN=%s PIT=%s CAMERA=%s OVERLAP=%s LIVE=%s REPLAY=%s REPLAY_SOURCE=outcome_replay APPLY=%d/%d status=%s"
		% [
			str(MapCasesScript.outcome_schema.get("verdict", "unproven")),
			str(MapCasesScript.outcome_roundtrip.get("verdict", "unproven")),
			str(MapCasesScript.outcome_graph.get("verdict", "unproven")),
			str(MapCasesScript.outcome_reject.get("verdict", "unproven")),
			str(MapCasesScript.outcome_author.get("verdict", "unproven")),
			str(MapCasesScript.outcome_width.get("verdict", "unproven")),
			str(MapCasesScript.outcome_spawn.get("verdict", "unproven")),
			str(MapCasesScript.outcome_pit.get("verdict", "unproven")),
			str(MapCasesScript.outcome_camera.get("verdict", "unproven")),
			str(MapCasesScript.outcome_overlap.get("verdict", "unproven")),
			str(MapCasesScript.outcome_live.get("verdict", "unproven")),
			str(MapCasesScript.outcome_replay.get("verdict", "unproven")),
			MapCasesScript.used_apply_frames_succeeded,
			MapCasesScript.used_apply_frames_attempted,
			_mapschema,
		]
	)
	print(
		"HH_VF_TRAV LADDER=%s LEDGE=%s DROP=%s BLOCK=%s DIRS=%s MAPS=%s STUCK=%s CONTACT=%s LIVE=%s REPLAY=%s APPLY=%d/%d status=%s"
		% [
			str(TraversalCasesScript.outcome_ladder.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_ledge.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_drop.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_block.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_dirs.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_maps.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_stuck.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_contact.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_live.get("verdict", "unproven")),
			str(TraversalCasesScript.outcome_replay.get("verdict", "unproven")),
			TraversalCasesScript.used_apply_frames_succeeded,
			TraversalCasesScript.used_apply_frames_attempted,
			_trav,
		]
	)
	if _fails.is_empty():
		print("PASS: Vault Fighters first playable")
	else:
		print("FAIL: Vault Fighters")
		var i: int = 0
		while i < _fails.size():
			print("  - %s" % String(_fails[i]))
			i += 1
