class_name RosterCases
extends RefCounted

const _Combat: GDScript = preload("res://src/sim/combat.gd")
const _Aim: GDScript = preload("res://src/sim/aim.gd")
const _Roster: GDScript = preload("res://src/data/weapons/roster.gd")
const _Inv: GDScript = preload("res://src/data/weapons/inventory.gd")

## VF3-WP5 official roster / inventory cases.
## Proof is InputFrame apply_frames plus live InputEvent inject.
## 60 Hz is ledger:RL-SIM-FIXED-60 (assumption).
## Slots stay ledger:RL-ITEM-SLOTS-4 (assumption).
## Roster stays ledger:RL-ITEM-ROSTER (assumption).
## Pickup slot replace stays ledger:RL-ITEM-PICK-SLOT (assumption).
## Keep-gun stays ledger:RL-ITEM-KEEP-GUN (assumption).
## Ammo/reload stay ledger:RL-ITEM-AMMO-RELOAD (assumption).
## Hold-to-aim stays ledger:RL-CTRL-HOLD-AIM (assumption).
## Y8 roll/dive stays unavailable. USED_APPLY_FRAMES counts success only.

static var used_step_fixed: int = 0
static var used_apply_frames: int = 0
static var used_apply_frames_attempted: int = 0
static var used_apply_frames_succeeded: int = 0
static var used_parse_input_event: int = 0
static var used_action_press: int = 0
static var outcome_schema: Dictionary = {}
static var outcome_spawn: Dictionary = {}
static var outcome_equip: Dictionary = {}
static var outcome_attack: Dictionary = {}
static var outcome_drop: Dictionary = {}
static var outcome_serialize: Dictionary = {}
static var outcome_keep: Dictionary = {}
static var outcome_ammo: Dictionary = {}
static var outcome_data: Dictionary = {}
static var outcome_live: Dictionary = {}
static var outcome_replay: Dictionary = {}
static var snapshot_start: Dictionary = {}
static var snapshot_end: Dictionary = {}
static var events_end: Array = []
static var events_all: Array = []


static func run_all(app: App) -> PackedStringArray:
	used_step_fixed = 0
	used_apply_frames = 0
	used_apply_frames_attempted = 0
	used_apply_frames_succeeded = 0
	used_parse_input_event = 0
	used_action_press = 0
	outcome_schema = {"verdict": "unproven"}
	outcome_spawn = {"verdict": "unproven"}
	outcome_equip = {"verdict": "unproven"}
	outcome_attack = {"verdict": "unproven"}
	outcome_drop = {"verdict": "unproven"}
	outcome_serialize = {"verdict": "unproven"}
	outcome_keep = {"verdict": "unproven"}
	outcome_ammo = {"verdict": "unproven"}
	outcome_data = {"verdict": "unproven"}
	outcome_live = {"verdict": "unproven"}
	outcome_replay = {"verdict": "unproven", "pairs": []}
	snapshot_start = {}
	snapshot_end = {}
	events_end = []
	events_all = []
	var errors: PackedStringArray = PackedStringArray()
	_append(errors, schema_and_data())
	_append(errors, await _capture_start(app))
	_append(errors, await replay_traces_twice(app))
	_append(errors, await every_item_spawns(app))
	_append(errors, await every_item_equips(app))
	_append(errors, await every_item_attacks(app))
	_append(errors, await every_item_drops(app))
	_append(errors, await serialize_roundtrip(app))
	_append(errors, await keep_gun_on_other_slots(app))
	_append(errors, await ammo_edges(app))
	_append(errors, await live_roster(app))
	_append(errors, _require_outcomes())
	return errors


static func schema_and_data() -> PackedStringArray:
	var errors: PackedStringArray = _Roster.validate()
	if not Maps.has_fixture("fx_roster_open"):
		errors.append("roster fixture missing from Maps")
	var ids: PackedStringArray = _Roster.ids()
	var required: PackedStringArray = PackedStringArray([
		"fists", "pipe", "knife", "baton", "pistol", "uzi", "shotgun",
		"rifle", "launcher", "grenade", "cinder"
	])
	var i: int = 0
	while i < required.size():
		if not ids.has(String(required[i])):
			errors.append("roster missing %s" % String(required[i]))
		i += 1
	var slots: Dictionary = {}
	i = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		slots[_Roster.slot_of(wid)] = true
		i += 1
	if not slots.has("melee") or not slots.has("firearm") or not slots.has("explosive") or not slots.has("power"):
		errors.append("roster must cover melee/firearm/explosive/power")
	var pistol: Dictionary = _Roster.item("pistol")
	var rifle: Dictionary = _Roster.item("rifle")
	var launcher: Dictionary = _Roster.item("launcher")
	if float(pistol.get("weight", 0.0)) == float(rifle.get("weight", 0.0)):
		errors.append("pistol/rifle weight must differ")
	if int(rifle.get("reserve", 0)) <= 0:
		errors.append("rifle reserve must allow reload proof")
	if int(launcher.get("ammo", 0)) == int(pistol.get("ammo", 0)):
		errors.append("launcher mag must differ from pistol")
	var live: Dictionary = _Roster.data()
	var missing_id: Dictionary = live.duplicate(true)
	var missing_items: Dictionary = missing_id.get("items", {}) as Dictionary
	var pistol_row: Dictionary = missing_items.get("pistol", {}) as Dictionary
	pistol_row.erase("id")
	var rejected_id: PackedStringArray = _Roster.validate_payload(missing_id)
	if rejected_id.is_empty():
		errors.append("SCHEMA must reject a payload whose pistol id is missing")
	var bad_weight: Dictionary = live.duplicate(true)
	var weight_items: Dictionary = bad_weight.get("items", {}) as Dictionary
	var pipe_row: Dictionary = weight_items.get("pipe", {}) as Dictionary
	pipe_row["weight"] = -1.0
	var rejected_weight: PackedStringArray = _Roster.validate_payload(bad_weight)
	if rejected_weight.is_empty():
		errors.append("SCHEMA must reject a payload whose pipe weight is invalid")
	outcome_schema = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"ids": ids.size(),
		"reject_missing_id": not rejected_id.is_empty(),
		"reject_bad_weight": not rejected_weight.is_empty(),
		"source": "data/weapons/roster.json + schema.json + validate_payload reject-invalid",
	}
	outcome_data = {
		"verdict": "pass" if errors.is_empty() else "fail",
		"tuning": true,
		"original_exact_numbers_claimed": false,
		"source": "roster values are tuning",
	}
	return errors


static func replay_traces_twice(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var paths: PackedStringArray = SimTrace.list_dir(SimConstants.ROSTER_TRACE_DIR)
	if paths.size() < 4:
		errors.append("expected >=4 roster traces, got %d" % paths.size())
	var required: PackedStringArray = PackedStringArray([
		"roster_idle", "roster_keep", "roster_melee", "roster_throw"
	])
	var names: PackedStringArray = PackedStringArray()
	var pairs: Array = []
	var i: int = 0
	while i < paths.size():
		var path: String = String(paths[i])
		var trace: Dictionary = SimTrace.load_path(path)
		_append(errors, SimTrace.validate(trace))
		if bool(trace.get("used_step_fixed", true)):
			errors.append("%s must set used_step_fixed false" % path.get_file())
		if bool(trace.get("y8_parity_claimed", true)):
			errors.append("%s claimed Y8 parity" % path.get_file())
		if "assumption" not in str(trace.get("hold_to_aim", "")):
			errors.append("%s must keep hold-to-aim assumption" % path.get_file())
		names.append(str(trace.get("name", path.get_file())))
		await _drain_physics(app)
		var a: Dictionary = await SimReplay.play_path(app, path)
		await _drain_physics(app)
		var b: Dictionary = await SimReplay.play_path(app, path)
		_record_apply_batch(int(a.get("ticks", 0)), bool(a.get("ok", false)))
		_record_apply_batch(int(b.get("ticks", 0)), bool(b.get("ok", false)))
		if not bool(a.get("ok", false)):
			errors.append("roster %s run1 failed: %s" % [path.get_file(), _join(a)])
		if not bool(b.get("ok", false)):
			errors.append("roster %s run2 failed: %s" % [path.get_file(), _join(b)])
		if not bool(a.get("used_apply_frames", false)) or bool(a.get("used_cmd_dicts", true)):
			errors.append("roster %s MATCH used cmd dicts" % path.get_file())
		var hash_a: String = str(a.get("final_hash", ""))
		var hash_b: String = str(b.get("final_hash", ""))
		var match_ok: bool = hash_a != "" and hash_a == hash_b
		if not match_ok:
			errors.append("roster %s replay hashes differ" % path.get_file())
		pairs.append({
			"name": str(trace.get("name", path.get_file())),
			"hash_match": match_ok,
			"ok_a": bool(a.get("ok", false)),
			"ok_b": bool(b.get("ok", false)),
			"hash_a": hash_a,
			"hash_b": hash_b,
		})
		_remember_end(a)
		_append_events(a.get("events", []) as Array)
		i += 1
	i = 0
	while i < required.size():
		if not names.has(String(required[i])):
			errors.append("missing roster trace %s" % String(required[i]))
		i += 1
	var all_match: bool = pairs.size() >= 4
	var p: int = 0
	while p < pairs.size():
		var row: Dictionary = pairs[p] as Dictionary
		if not bool(row.get("hash_match", false)):
			all_match = false
		p += 1
	outcome_replay = {
		"verdict": "match" if all_match and errors.is_empty() else "fail",
		"pairs": pairs,
		"source": "apply_frames roster traces twice",
	}
	return errors


static func every_item_spawns(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
	if p1.melee_id != "fists":
		errors.append("SPAWN fists must be default-equip at start")
	var ids: PackedStringArray = _Roster.ids()
	var spawned: PackedStringArray = PackedStringArray()
	var uids: PackedInt32Array = PackedInt32Array()
	var i: int = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		var drop: Pickup = session._add_pickup(wid, p1.global_position + Vector2(24.0 + float(i) * 2.0, 4.0), false)
		if drop == null or drop.weapon_id != wid or drop.drop_uid <= 0:
			errors.append("SPAWN failed for %s" % wid)
		else:
			if uids.has(drop.drop_uid):
				errors.append("SPAWN cloned uid %d for %s" % [drop.drop_uid, wid])
			else:
				uids.append(drop.drop_uid)
				spawned.append(wid)
		i += 1
	outcome_spawn = {
		"verdict": "pass" if spawned.size() == ids.size() else "fail",
		"spawned": spawned.size(),
		"ids": spawned,
		"expected": ids.size(),
		"default_equip": PackedStringArray(["fists"]),
		"source": "default-equip fists plus _add_pickup every roster id",
	}
	_remember_session(session)
	return errors


static func every_item_equips(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
	var ids: PackedStringArray = _Roster.ids()
	var equipped: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		p1.give_weapon(wid)
		if not _holds(p1, wid):
			errors.append("EQUIP failed for %s" % wid)
		else:
			equipped.append(wid)
		i += 1
	outcome_equip = {
		"verdict": "pass" if equipped.size() == ids.size() else "fail",
		"equipped": equipped.size(),
		"ids": equipped,
		"expected": ids.size(),
		"source": "give_weapon every roster id",
	}
	_remember_session(session)
	return errors


static func every_item_attacks(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var attacked: PackedStringArray = PackedStringArray()
	var ids: PackedStringArray = _Roster.ids()
	var i: int = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		app.start_fight("vs2", "fx_roster_open", 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var p1: Fighter = session.fighter_at_slot(0)
		var p2: Fighter = session.fighter_at_slot(1)
		_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
		p1.give_weapon(wid)
		p1.facing = 1.0
		p1.aim_dir = Vector2.RIGHT
		p1.last_aim_dir = Vector2.RIGHT
		var ok: bool = false
		var slot: String = _Roster.slot_of(wid)
		if slot == "melee":
			p2.global_position = p1.global_position + Vector2(14.0, 0.0)
			var hp0: float = p2.health
			_apply_slot(session, 0, PackedStringArray(["melee"]), 1, 0.0)
			var wait: int = _Combat.total_ticks(wid, "melee") + 2
			_apply_idle(session, wait)
			ok = p2.health < hp0
		elif slot == "firearm":
			p1.fire_cd = 0.0
			var shots0: int = p1.shots_fired
			_apply_slot(session, 0, PackedStringArray(["fire"]), 6, 0.0)
			if not bool(_Roster.item(wid).get("auto", false)):
				_apply_release(session, 0, "fire")
			_apply_idle(session, 4)
			ok = p1.shots_fired > shots0
		else:
			p1.grenades = 0
			if slot == "explosive":
				p1.grenades = 2
				p1.explosive_id = wid
			else:
				p1.power_id = wid
				p1.power_ammo = 1
			var n0: int = session.grenades.size()
			_apply_slot(session, 0, PackedStringArray(["grenade"]), 4, 0.0)
			_apply_release(session, 0, "grenade")
			ok = session.grenades.size() > n0
		if not ok:
			errors.append("ATTACK failed for %s" % wid)
		else:
			attacked.append(wid)
		_remember_session(session)
		i += 1
	outcome_attack = {
		"verdict": "pass" if attacked.size() == ids.size() else "fail",
		"attacked": attacked.size(),
		"ids": attacked,
		"expected": ids.size(),
		"source": "apply_frames melee/fire/throw per roster id",
	}
	return errors


static func every_item_drops(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var dropped: PackedStringArray = PackedStringArray()
	var rows: Array = []
	var ids: PackedStringArray = _Roster.ids()
	var i: int = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		app.start_fight("vs2", "fx_roster_open", 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var p1: Fighter = session.fighter_at_slot(0)
		_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
		if not _holds(p1, wid):
			p1.give_weapon(wid)
		if not _holds(p1, wid):
			errors.append("DROP setup failed to hold %s" % wid)
			i += 1
			continue
		var partner: String = _Roster.replacement_of(wid)
		var slot: String = _Roster.slot_of(wid)
		var before: PackedInt32Array = _uids_for(session, wid)
		var path: String = "pickup_replace"
		if partner != "":
			_pickup_id(session, p1, partner)
			if not _holds(p1, partner):
				errors.append("DROP %s did not equip partner %s" % [wid, partner])
		else:
			path = "held_eject"
			var eject: Pickup = session.drop_held_slot(p1, slot)
			if eject == null:
				errors.append("DROP eject failed for %s" % wid)
				i += 1
				continue
			if _holds(p1, wid):
				errors.append("DROP eject left %s equipped (clone)" % wid)
		var after: PackedInt32Array = _uids_for(session, wid)
		var fresh: PackedInt32Array = _new_uids(before, after)
		if not _uids_unique(after):
			errors.append("DROP %s cloned uids" % wid)
		elif fresh.size() != 1:
			errors.append("DROP %s expected one world uid, got %d" % [wid, fresh.size()])
		else:
			dropped.append(wid)
			rows.append({
				"id": wid,
				"uid": int(fresh[0]),
				"path": path,
				"clones": 0,
			})
		_remember_session(session)
		i += 1
	outcome_drop = {
		"verdict": "pass" if dropped.size() == ids.size() else "fail",
		"ids": dropped,
		"expected": ids.size(),
		"rows": rows,
		"source": "pickup-replace when a same-slot partner exists; held_eject via drop_held_slot/_drop_specific for singleton slots",
	}
	return errors


static func serialize_roundtrip(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var restored: PackedStringArray = PackedStringArray()
	var rows: Array = []
	var ids: PackedStringArray = _Roster.ids()
	var hash_fields: bool = false
	var i: int = 0
	while i < ids.size():
		var wid: String = String(ids[i])
		app.start_fight("vs2", "fx_roster_open", 0)
		await SimReplay.sync_physics(app)
		var session: GameSession = app.session
		var p1: Fighter = session.fighter_at_slot(0)
		_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
		p1.give_weapon(wid)
		if not _holds(p1, wid):
			errors.append("SERIALIZE setup failed to hold %s" % wid)
			i += 1
			continue
		var snap: Dictionary = _Inv.snapshot(p1)
		var session_snap: Dictionary = session.snapshot()
		var fighters: Array = session_snap.get("fighters", []) as Array
		if fighters.is_empty():
			errors.append("SERIALIZE snapshot missing fighters for %s" % wid)
			i += 1
			continue
		var frow: Dictionary = fighters[0] as Dictionary
		if not _row_has_inv(frow):
			errors.append("SERIALIZE fighter row missing explosive/power/reserve/reload for %s" % wid)
		var payload: Dictionary = SimSnapshot.hash_payload(session_snap)
		var hashed: Array = payload.get("fighters", []) as Array
		if hashed.is_empty() or not _row_has_inv(hashed[0] as Dictionary):
			errors.append("SERIALIZE hash_payload omitted inventory fields for %s" % wid)
		if wid == "grenade":
			var h0: String = SimSnapshot.stable_hash(session_snap)
			p1.reserve = p1.reserve + 1
			var h1: String = SimSnapshot.stable_hash(session.snapshot())
			if h0 == h1:
				errors.append("SERIALIZE reserve must change hash_payload")
			p1.explosive_id = ""
			var h2: String = SimSnapshot.stable_hash(session.snapshot())
			if h0 == h2:
				errors.append("SERIALIZE explosive must change hash_payload")
			hash_fields = h0 != h1 and h0 != h2
		p1.give_weapon("knife")
		p1.give_weapon("pistol")
		p1.explosive_id = ""
		p1.grenades = 0
		p1.power_id = ""
		p1.power_ammo = 0
		p1.ammo = 0
		p1.reserve = 0
		p1.reload_left = 99
		_Inv.apply_snapshot(p1, snap)
		var back: Dictionary = _Inv.snapshot(p1)
		var ok: bool = _slot_restored(wid, snap, back)
		if not ok:
			errors.append("SERIALIZE roundtrip lost %s" % wid)
		else:
			restored.append(wid)
		rows.append({
			"id": wid,
			"ok": ok,
			"snap": snap,
			"back": back,
		})
		_remember_session(session)
		i += 1
	if not hash_fields:
		errors.append("SERIALIZE must prove explosive/reserve sit in hash_payload")
	outcome_serialize = {
		"verdict": "pass" if restored.size() == ids.size() and hash_fields and errors.is_empty() else "fail",
		"ids": restored,
		"expected": ids.size(),
		"rows": rows,
		"hash_fields": hash_fields,
		"source": "per-id _Inv.snapshot / apply_snapshot after disturbing melee/firearm/explosive/power/ammo/reserve/reload",
	}
	return errors


static func keep_gun_on_other_slots(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
	p1.gun_id = "pistol"
	p1.ammo = 12
	p1.weapon_id = "pistol"
	p1.melee_id = "fists"
	p1.grenades = 3
	p1.power_id = ""
	p1.power_ammo = 0
	_pickup_id(session, p1, "pipe")
	var after_melee: bool = p1.gun_id == "pistol" and p1.ammo == 12 and p1.melee_id == "pipe"
	_pickup_id(session, p1, "grenade")
	var after_nade: bool = p1.gun_id == "pistol" and p1.ammo == 12 and p1.grenades > 3
	_pickup_id(session, p1, "cinder")
	var after_power: bool = p1.gun_id == "pistol" and p1.ammo == 12 and p1.power_id == "cinder"
	if not after_melee:
		errors.append("KEEP melee pickup stripped the gun")
	if not after_nade:
		errors.append("KEEP grenade pickup stripped the gun")
	if not after_power:
		errors.append("KEEP power pickup stripped the gun")
	outcome_keep = {
		"verdict": "pass" if after_melee and after_nade and after_power else "fail",
		"after_melee": after_melee,
		"after_nade": after_nade,
		"after_power": after_power,
		"source": "crouch pickup pipe/grenade/cinder keeps pistol",
	}
	_remember_session(session)
	return errors


static func ammo_edges(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	_apply_slot(session, 0, PackedStringArray(), 4, 0.0)
	p1.give_weapon("pistol")
	p1.ammo = 0
	p1.reload_left = 0
	p1.fire_cd = 0.0
	var shots0: int = p1.shots_fired
	_apply_slot(session, 0, PackedStringArray(["fire"]), 6, 0.0)
	_apply_release(session, 0, "fire")
	var empty_ok: bool = p1.shots_fired == shots0 and p1.gun_id == "pistol"
	p1.give_weapon("rifle")
	var spec: Dictionary = _Roster.item("rifle")
	var roster_reserve: int = int(spec.get("reserve", 0))
	var roster_mag: int = int(spec.get("mag_size", 0))
	var roster_reload: int = int(spec.get("reload_ticks", 0))
	if p1.reserve != roster_reserve or p1.mag_size != roster_mag:
		errors.append("AMMO rifle give_weapon must copy roster reserve/mag got reserve=%d mag=%d" % [
			p1.reserve, p1.mag_size
		])
	p1.ammo = 1
	p1.fire_cd = 0.0
	p1.reload_left = 0
	_apply_slot(session, 0, PackedStringArray(["fire"]), 1, 0.0)
	_apply_release(session, 0, "fire")
	if p1.ammo != 0:
		errors.append("AMMO rifle last roster round must consume ammo=%d" % p1.ammo)
	var need: int = p1.reload_left
	if need <= 0:
		errors.append("AMMO rifle must start reload from roster-copied reserve")
	if p1.reserve != roster_reserve or p1.mag_size != roster_mag:
		errors.append("AMMO rifle must keep roster reserve/mag through the last shot")
	_apply_idle(session, maxi(need, roster_reload) + 2)
	var reload_ok: bool = (
		p1.ammo == roster_mag
		and p1.reserve == 0
		and p1.gun_id == "rifle"
		and p1.mag_size == roster_mag
	)
	if not empty_ok:
		errors.append("AMMO empty pistol must not fire and must stay equipped")
	if not reload_ok:
		errors.append("AMMO rifle reload from roster reserve failed ammo=%d reserve=%d" % [p1.ammo, p1.reserve])
	outcome_ammo = {
		"verdict": "pass" if empty_ok and reload_ok and errors.is_empty() else "fail",
		"empty_ok": empty_ok,
		"reload_ok": reload_ok,
		"reload_ticks": need,
		"ammo": p1.ammo,
		"reserve": p1.reserve,
		"roster_reserve": roster_reserve,
		"roster_mag": roster_mag,
		"copied_reserve": p1.reserve == 0 and roster_reserve > 0,
		"source": "0 ammo no fire; empty gun stays; rifle reload from roster-copied reserve/mag",
	}
	_remember_session(session)
	return errors


static func live_roster(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	var session: GameSession = app.session
	var p1: Fighter = session.fighter_at_slot(0)
	var viewport: Viewport = app.get_viewport()
	await SimReplay.sync_physics(app)
	InputInjector.release_known(viewport)
	InputActions.reset_edges()
	used_parse_input_event += 1
	_apply_slot(session, 0, PackedStringArray(), 6, 0.0)
	p1.give_weapon("pipe")
	var drop: Pickup = session._add_pickup("uzi", p1.global_position, false)
	p1.global_position = drop.global_position
	InputInjector.inject_key(KEY_DOWN, true, viewport)
	InputInjector.inject_key(KEY_N, true, viewport)
	var n: int = 0
	while n < 4:
		session.step_from_live_input()
		n += 1
	InputInjector.inject_key(KEY_N, false, viewport)
	InputInjector.inject_key(KEY_DOWN, false, viewport)
	session.step_from_live_input()
	var live_ok: bool = p1.gun_id == "uzi" and p1.melee_id == "pipe"
	if not live_ok:
		errors.append("LIVE crouch+N must swap the firearm slot and keep melee")
	InputInjector.release_known(viewport)
	outcome_live = {
		"verdict": "pass" if live_ok else "fail",
		"gun": p1.gun_id,
		"melee": p1.melee_id,
		"source": "parse_input_event KEY_DOWN+KEY_N + step_from_live_input",
	}
	_remember_session(session)
	return errors


static func _require_outcomes() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var labels: PackedStringArray = PackedStringArray([
		"SCHEMA", "SPAWN", "EQUIP", "ATTACK", "DROP", "SERIALIZE", "KEEP", "AMMO", "DATA", "LIVE"
	])
	var rows: Array = [
		outcome_schema, outcome_spawn, outcome_equip, outcome_attack, outcome_drop,
		outcome_serialize, outcome_keep, outcome_ammo, outcome_data, outcome_live
	]
	var ki: int = 0
	while ki < labels.size():
		var row: Dictionary = rows[ki] as Dictionary
		if str(row.get("verdict", "")) != "pass":
			errors.append("%s outcome is %s" % [String(labels[ki]), str(row.get("verdict", "unproven"))])
		ki += 1
	if str(outcome_replay.get("verdict", "")) != "match":
		errors.append("REPLAY outcome is %s" % str(outcome_replay.get("verdict", "unproven")))
	if used_apply_frames_succeeded <= 0 or used_apply_frames != used_apply_frames_succeeded:
		errors.append("USED_APPLY_FRAMES must count successful applies got=%d attempted=%d" % [
			used_apply_frames_succeeded, used_apply_frames_attempted
		])
	return errors


static func _holds(fighter: Fighter, weapon_id: String) -> bool:
	var slot: String = _Roster.slot_of(weapon_id)
	if slot == "melee":
		return fighter.melee_id == weapon_id
	if slot == "firearm":
		return fighter.gun_id == weapon_id
	if slot == "explosive":
		return fighter.explosive_id == weapon_id and fighter.grenades > 0
	if slot == "power":
		return fighter.power_id == weapon_id and fighter.power_ammo > 0
	return false


static func _pickup_id(session: GameSession, p1: Fighter, wid: String) -> void:
	var drop: Pickup = session._add_pickup(wid, p1.global_position, false)
	p1.melee_cd = 0.0
	p1.global_position = drop.global_position
	_apply_slot(session, 0, PackedStringArray(["crouch", "melee"]), 1, 0.0)


static func _live_pickups(session: GameSession) -> int:
	var n: int = 0
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop):
			n += 1
		i += 1
	return n


static func _has_pickup(session: GameSession, wid: String) -> bool:
	return not _uids_for(session, wid).is_empty()


static func _uids_for(session: GameSession, wid: String) -> PackedInt32Array:
	var out: PackedInt32Array = PackedInt32Array()
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop) and drop.weapon_id == wid:
			out.append(drop.drop_uid)
		i += 1
	return out


static func _new_uids(before: PackedInt32Array, after: PackedInt32Array) -> PackedInt32Array:
	var out: PackedInt32Array = PackedInt32Array()
	var i: int = 0
	while i < after.size():
		if not before.has(after[i]):
			out.append(after[i])
		i += 1
	return out


static func _uids_unique(uids: PackedInt32Array) -> bool:
	var seen: Dictionary = {}
	var i: int = 0
	while i < uids.size():
		var uid: int = int(uids[i])
		if seen.has(uid):
			return false
		seen[uid] = true
		i += 1
	return true


static func _row_has_inv(row: Dictionary) -> bool:
	return (
		row.has("explosive")
		and row.has("power")
		and row.has("reserve")
		and row.has("reload")
	)


static func _slot_restored(wid: String, snap: Dictionary, back: Dictionary) -> bool:
	var slot: String = _Roster.slot_of(wid)
	if slot == "melee":
		return str(back.get("melee", "")) == wid
	if slot == "firearm":
		return (
			str(back.get("firearm", "")) == wid
			and int(back.get("ammo", -1)) == int(snap.get("ammo", -2))
			and int(back.get("reserve", -1)) == int(snap.get("reserve", -2))
			and int(back.get("reload_left", -1)) == int(snap.get("reload_left", -2))
		)
	if slot == "explosive":
		return (
			str(back.get("explosive", "")) == wid
			and int(back.get("nades", -1)) == int(snap.get("nades", -2))
		)
	if slot == "power":
		return (
			str(back.get("power", "")) == wid
			and int(back.get("power_ammo", -1)) == int(snap.get("power_ammo", -2))
		)
	return false


static func _apply_release(session: GameSession, slot: int, action: String) -> void:
	var frames: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
		if i == slot:
			raw["released"] = [action]
		frames.append(InputFrame.from_dict(raw))
		i += 1
	_record_apply(session.apply_frames(frames))


static func _apply_slot(session: GameSession, slot: int, held: PackedStringArray, ticks: int, move_x: float) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			var raw: Dictionary = InputActions.empty_frame(session.clock.tick, i)
			if i == slot:
				raw["held"] = Array(held)
				raw["move_x"] = move_x
				if n == 0 and not held.is_empty():
					raw["pressed"] = Array(held)
			frames.append(InputFrame.from_dict(raw))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _apply_idle(session: GameSession, ticks: int) -> void:
	var n: int = 0
	while n < ticks:
		var frames: Array = []
		var i: int = 0
		while i < session.fighters.size():
			frames.append(InputFrame.from_dict(InputActions.empty_frame(session.clock.tick, i)))
			i += 1
		_record_apply(session.apply_frames(frames))
		n += 1


static func _drain_physics(app: App) -> void:
	InputActions.reset_edges()
	await SimReplay.sync_physics(app)
	await SimReplay.sync_physics(app)


static func _capture_start(app: App) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	app.start_fight("vs2", "fx_roster_open", 0)
	await SimReplay.sync_physics(app)
	var session: GameSession = app.session
	if session == null:
		errors.append("start snapshot missing session")
		return errors
	snapshot_start = session.snapshot()
	if session.ledger != null:
		events_end = session.ledger.to_array()
	return errors


static func _record_apply(ok: bool) -> bool:
	used_apply_frames_attempted += 1
	if ok:
		used_apply_frames_succeeded += 1
		used_apply_frames = used_apply_frames_succeeded
	return ok


static func _record_apply_batch(succeeded_ticks: int, ok: bool) -> void:
	var attempts: int = succeeded_ticks
	if not ok:
		attempts += 1
	if attempts < 0:
		attempts = 0
	if succeeded_ticks < 0:
		succeeded_ticks = 0
	used_apply_frames_attempted += attempts
	used_apply_frames_succeeded += succeeded_ticks
	used_apply_frames = used_apply_frames_succeeded


static func _remember_end(played: Dictionary) -> void:
	var state: Dictionary = played.get("final_state", {}) as Dictionary
	if not state.is_empty():
		snapshot_end = state
	var events: Array = played.get("events", []) as Array
	if not events.is_empty():
		events_end = events


static func _remember_session(session: GameSession) -> void:
	if session == null:
		return
	snapshot_end = session.snapshot()
	if session.ledger != null:
		events_end = session.ledger.to_array()


static func _append_events(events: Array) -> void:
	var i: int = 0
	while i < events.size():
		events_all.append(events[i])
		i += 1


static func _join(played: Dictionary) -> String:
	var errs: Variant = played.get("errors", PackedStringArray())
	if errs is PackedStringArray:
		return ",".join(errs as PackedStringArray)
	if errs is Array:
		var parts: PackedStringArray = PackedStringArray()
		var i: int = 0
		var arr: Array = errs as Array
		while i < arr.size():
			parts.append(str(arr[i]))
			i += 1
		return ",".join(parts)
	return str(errs)


static func _append(target: PackedStringArray, extra: PackedStringArray) -> void:
	var i: int = 0
	while i < extra.size():
		target.append(String(extra[i]))
		i += 1
