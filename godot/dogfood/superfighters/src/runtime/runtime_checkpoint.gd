class_name RuntimeCheckpoint
extends RefCounted

## Capture / restore session state. Restore hash must match capture hash.


static func capture(session: GameSession) -> Dictionary:
	var snap: Dictionary = session.snapshot()
	return {
		"schema": RuntimeConstants.CHECKPOINT_ID,
		"schema_version": RuntimeConstants.SCHEMA_VERSION,
		"snapshot": snap.duplicate(true),
		"snapshot_hash": SimSnapshot.stable_hash(snap),
		"pause_reason": session.pause_reason,
		"stage_index": session.stage_index,
		"rng_state": session.rng.state,
		"clock": {
			"tick": session.clock.tick if session.clock != null else 0,
			"accum": session.clock.accum if session.clock != null else 0.0,
			"paused": session.clock.paused if session.clock != null else false,
		},
		"ledger": session.ledger.to_array() if session.ledger != null else [],
		"last_reject": _packed_to_array(session.last_reject),
		"pickups_extra": _pickup_extras(session),
		"bullets_extra": _bullet_extras(session),
		"grenades_extra": _grenade_extras(session),
		"respawns": _respawn_rows(session),
		"fighters_extra": _fighter_extras(session),
	}


static func apply(session: GameSession, payload: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if session == null:
		errors.append("session missing")
		return errors
	var snap: Dictionary = payload.get("snapshot", {}) as Dictionary
	if snap.is_empty():
		errors.append("checkpoint missing snapshot")
		return errors
	session.outcome = str(snap.get("outcome", session.outcome))
	if session.match_rules != null:
		session.match_rules.outcome = session.outcome
		session.match_rules.phase = str(snap.get("phase", session.match_rules.phase))
		session.match_rules.end_reason = str(snap.get("end_reason", session.match_rules.end_reason))
		session.match_rules.round_id = int(snap.get("round_id", session.match_rules.round_id))
	session.sim_seed = int(snap.get("seed", session.sim_seed))
	session.rng.seed = session.sim_seed
	if payload.has("rng_state"):
		session.rng.state = int(payload.get("rng_state", session.rng.state))
	if session.clock != null:
		var clock_row: Dictionary = payload.get("clock", {}) as Dictionary
		session.clock.tick = int(clock_row.get("tick", snap.get("tick", session.clock.tick)))
		session.clock.accum = float(clock_row.get("accum", 0.0))
		session.clock.paused = bool(clock_row.get("paused", false))
	session.pause_reason = str(payload.get("pause_reason", ""))
	_apply_fighters(session, snap.get("fighters", []) as Array, payload.get("fighters_extra", []) as Array)
	session.replace_pickups(payload.get("pickups_extra", snap.get("pickups", [])) as Array)
	session.replace_bullets(payload.get("bullets_extra", snap.get("bullets", [])) as Array)
	session.replace_grenades(payload.get("grenades_extra", snap.get("grenades", [])) as Array)
	session.replace_respawns(payload.get("respawns", []) as Array)
	if session.ledger != null:
		session.ledger.reset()
		session.ledger.events = (payload.get("ledger", []) as Array).duplicate(true)
	session.last_reject = PackedStringArray()
	var rejects: Array = payload.get("last_reject", []) as Array
	var i: int = 0
	while i < rejects.size():
		session.last_reject.append(str(rejects[i]))
		i += 1
	return errors


static func persist_atomic(checkpoint_id: String, payload: Dictionary) -> String:
	if not RuntimeConstants.checkpoint_id_ok(checkpoint_id):
		return ""
	var rel: String = RuntimeConstants.STORE_DIR + checkpoint_id + ".json"
	var abs_dir: String = ProjectSettings.globalize_path(RuntimeConstants.STORE_DIR)
	DirAccess.make_dir_recursive_absolute(abs_dir)
	var tmp: String = rel + ".tmp"
	var file: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload))
	file.close()
	var abs_tmp: String = ProjectSettings.globalize_path(tmp)
	var abs_final: String = ProjectSettings.globalize_path(rel)
	if FileAccess.file_exists(rel):
		DirAccess.remove_absolute(abs_final)
	var err: Error = DirAccess.rename_absolute(abs_tmp, abs_final)
	if err != OK:
		DirAccess.remove_absolute(abs_tmp)
		return ""
	return rel


static func load_persisted(checkpoint_id: String) -> Dictionary:
	if not RuntimeConstants.checkpoint_id_ok(checkpoint_id):
		return {}
	var rel: String = RuntimeConstants.STORE_DIR + checkpoint_id + ".json"
	return SimConstants.load_json(rel)


static func _apply_fighters(session: GameSession, rows: Array, extras: Array) -> void:
	var extra_by_slot: Dictionary = {}
	var e: int = 0
	while e < extras.size():
		var extra: Dictionary = extras[e] as Dictionary
		extra_by_slot[int(extra.get("slot", -1))] = extra
		e += 1
	var i: int = 0
	while i < rows.size():
		var row: Dictionary = rows[i] as Dictionary
		var slot: int = int(row.get("slot", -1))
		var fighter: Fighter = session.fighter_at_slot(slot)
		if fighter != null:
			fighter.apply_runtime_row(row)
			if extra_by_slot.has(slot):
				fighter.apply_runtime_extra(extra_by_slot[slot] as Dictionary)
		i += 1


static func _pickup_extras(session: GameSession) -> Array:
	var out: Array = []
	var i: int = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop):
			out.append({
				"id": drop.weapon_id,
				"x": SimConstants.quantize(drop.global_position.x),
				"y": SimConstants.quantize(drop.global_position.y),
				"from_world": drop.from_world,
				"uid": drop.drop_uid,
				"home_x": SimConstants.quantize(drop.home.x),
				"home_y": SimConstants.quantize(drop.home.y),
			})
		i += 1
	return out


static func _bullet_extras(session: GameSession) -> Array:
	var out: Array = []
	var i: int = 0
	while i < session.bullets.size():
		var shot: Bullet = session.bullets[i]
		if shot != null and is_instance_valid(shot) and not shot.spent:
			out.append({
				"x": SimConstants.quantize(shot.global_position.x),
				"y": SimConstants.quantize(shot.global_position.y),
				"vx": SimConstants.quantize(shot.velocity.x),
				"vy": SimConstants.quantize(shot.velocity.y),
				"owner": shot.owner_slot,
				"team": shot.owner_team,
				"damage": SimConstants.quantize(shot.damage),
				"life": SimConstants.quantize(shot.life),
			})
		i += 1
	return out


static func _grenade_extras(session: GameSession) -> Array:
	var out: Array = []
	var i: int = 0
	while i < session.grenades.size():
		var nade: ThrownGrenade = session.grenades[i]
		if nade != null and is_instance_valid(nade) and not nade.exploded:
			out.append({
				"x": SimConstants.quantize(nade.global_position.x),
				"y": SimConstants.quantize(nade.global_position.y),
				"vx": SimConstants.quantize(nade.velocity.x),
				"vy": SimConstants.quantize(nade.velocity.y),
				"owner": nade.owner_slot,
				"team": nade.owner_team,
				"fuse": SimConstants.quantize(nade.fuse),
				"fuse_ticks": nade.fuse_ticks,
				"life_ticks": nade.life_ticks,
				"bounce_count": nade.bounce_count,
				"damage": SimConstants.quantize(nade.damage),
				"radius": SimConstants.quantize(nade.radius),
			})
		i += 1
	return out


static func _respawn_rows(session: GameSession) -> Array:
	var out: Array = []
	var i: int = 0
	while i < session.respawns.size():
		var rec: Dictionary = session.respawns[i]
		var pos: Vector2 = rec.get("pos", Vector2.ZERO) as Vector2
		out.append({
			"id": str(rec.get("id", "")),
			"x": SimConstants.quantize(pos.x),
			"y": SimConstants.quantize(pos.y),
			"t": SimConstants.quantize(float(rec.get("t", 0.0))),
		})
		i += 1
	return out


static func _fighter_extras(session: GameSession) -> Array:
	var out: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and is_instance_valid(f):
			out.append({
				"slot": f.slot,
				"is_bot": f.is_bot,
				"invuln": SimConstants.quantize(f.invuln),
				"melee_cd": SimConstants.quantize(f.melee_cd),
				"fire_cd": SimConstants.quantize(f.fire_cd),
				"grenade_cd": SimConstants.quantize(f.grenade_cd),
				"aim_x": SimConstants.quantize(f.aim_dir.x),
				"aim_y": SimConstants.quantize(f.aim_dir.y),
				"on_ladder": f.on_ladder,
				"climbing": f.climbing,
				"hanging": f.hanging,
				"climb_seq": f.climb_seq,
				"hang_seq": f.hang_seq,
				"contact_nx": SimConstants.quantize(f.last_contact_nx),
				"contact_ny": SimConstants.quantize(f.last_contact_ny),
				"sprinting": f.sprinting,
				"rolling": f.rolling,
				"roll_seq": f.roll_seq,
				"roll_time": SimConstants.quantize(f.roll_time),
				"diving": f.diving,
				"dive_seq": f.dive_seq,
				"dive_time": SimConstants.quantize(f.dive_time),
				"kicking": f.kicking,
				"kick_seq": f.kick_seq,
				"kick_time": SimConstants.quantize(f.kick_time),
				"explosive": f.explosive_id,
				"power": f.power_id,
				"reserve": f.reserve,
				"mag_size": f.mag_size,
				"reload_left": f.reload_left,
				"power_ammo": f.power_ammo,
				"attack_phase": f.attack_phase,
				"attack_seq": f.attack_seq,
				"attack_style": f.attack_style,
				"attack_weapon": f.attack_weapon,
				"attack_age": f.attack_age,
				"hitstop_left": f.hitstop_left,
				"knockdown_left": SimConstants.quantize(f.knockdown_left),
				"getup_left": SimConstants.quantize(f.getup_left),
				"hit_airborne": f.hit_airborne,
				"invuln_ticks": f.invuln_ticks,
				"fire_extinguish_count": f.fire_extinguish_count,
				"burning": f.burning,
				"wet": f.wet,
				"acid_contact": f.acid_contact,
			})
		i += 1
	return out


static func _packed_to_array(packed: PackedStringArray) -> Array:
	var out: Array = []
	var i: int = 0
	while i < packed.size():
		out.append(String(packed[i]))
		i += 1
	return out
