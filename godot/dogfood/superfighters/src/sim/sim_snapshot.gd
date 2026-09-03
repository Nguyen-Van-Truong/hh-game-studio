class_name SimSnapshot
extends RefCounted

## Read-only snapshot + stable hash. Must not mutate session state.


static func from_session(session: GameSession) -> Dictionary:
	var living: int = 0
	var fighters_out: Array = []
	var i: int = 0
	while i < session.fighters.size():
		var f: Fighter = session.fighters[i]
		if f != null and not f.dead:
			living += 1
		fighters_out.append(_fighter_row(f))
		i += 1
	var pickups_out: Array = []
	i = 0
	while i < session.pickups.size():
		var drop: Pickup = session.pickups[i]
		if drop != null and is_instance_valid(drop):
			pickups_out.append({
				"id": drop.weapon_id,
				"uid": drop.drop_uid,
				"x": SimConstants.quantize(drop.global_position.x),
				"y": SimConstants.quantize(drop.global_position.y),
			})
		i += 1
	_sort_by_xy_id(pickups_out)
	var bullets_out: Array = []
	i = 0
	while i < session.bullets.size():
		var shot: Bullet = session.bullets[i]
		if shot != null and is_instance_valid(shot) and not shot.spent:
			bullets_out.append({
				"x": SimConstants.quantize(shot.global_position.x),
				"y": SimConstants.quantize(shot.global_position.y),
				"vx": SimConstants.quantize(shot.velocity.x),
				"vy": SimConstants.quantize(shot.velocity.y),
				"owner": shot.owner_slot,
			})
		i += 1
	_sort_by_xy_id(bullets_out)
	var nades_out: Array = []
	i = 0
	while i < session.grenades.size():
		var nade: ThrownGrenade = session.grenades[i]
		if nade != null and is_instance_valid(nade) and not nade.exploded:
			nades_out.append({
				"x": SimConstants.quantize(nade.global_position.x),
				"y": SimConstants.quantize(nade.global_position.y),
				"vx": SimConstants.quantize(nade.velocity.x),
				"vy": SimConstants.quantize(nade.velocity.y),
				"owner": nade.owner_slot,
				"team": nade.owner_team,
				"fuse_ticks": nade.fuse_ticks,
				"life_ticks": nade.life_ticks,
				"bounce": nade.bounce_count,
			})
		i += 1
	_sort_by_xy_id(nades_out)
	var p1: Fighter = session.player1()
	var tick: int = 0
	var seed_v: int = session.sim_seed
	if session.clock != null:
		tick = session.clock.tick
	var phase: String = "active"
	var end_reason: String = ""
	var round_id: int = 0
	var timer_enabled: int = 0
	var timer_left: int = -1
	var countdown_left: int = 0
	var winner_team: int = -1
	var alignment: String = ""
	if session.match_rules != null:
		phase = session.match_rules.phase
		end_reason = session.match_rules.end_reason
		round_id = session.match_rules.round_id
		timer_enabled = 1 if session.match_rules.timer_enabled else 0
		timer_left = session.match_rules.timer_left
		countdown_left = session.match_rules.countdown_left
		winner_team = session.match_rules.winner_team
		alignment = session.match_rules.alignment
	return {
		"schema": SimConstants.SNAPSHOT_ID,
		"schema_version": SimConstants.SCHEMA_VERSION,
		"tick": tick,
		"seed": seed_v,
		"epsilon": SimConstants.EPSILON,
		"event_order": SimEventOrder.SCHEMA_ID,
		"map_id": session.map_id,
		"mode": session.mode,
		"phase": phase,
		"end_reason": end_reason,
		"round_id": round_id,
		"timer_enabled": timer_enabled,
		"timer_left": timer_left,
		"countdown_left": countdown_left,
		"winner_team": winner_team,
		"alignment": alignment,
		"outcome": session.outcome,
		"living": living,
		"fighters": fighters_out,
		"pickups": pickups_out,
		"bullets": bullets_out,
		"grenades": nades_out,
		"respawn_count": session.respawns.size(),
		"p1_hp": p1.health if p1 != null else 0.0,
		"p1_dead": p1.dead if p1 != null else true,
		"p1_weapon": p1.weapon_id if p1 != null else "",
		"p1_gun": p1.gun_id if p1 != null else "",
		"p1_melee": p1.melee_id if p1 != null else "",
		"p1_nades": p1.grenades if p1 != null else 0,
		"p1_explosive": p1.explosive_id if p1 != null else "",
		"p1_power": p1.power_id if p1 != null else "",
		"p1_power_ammo": p1.power_ammo if p1 != null else 0,
		"p1_x": p1.global_position.x if p1 != null else 0.0,
		"p1_y": p1.global_position.y if p1 != null else 0.0,
		"win": session.outcome == "win",
		"survival": session.survival.snapshot_row() if session.survival != null else {},
	}


static func hash_payload(snap: Dictionary) -> Dictionary:
	## Physics/combat identity only. Lifecycle (phase/outcome/round_id)
	## lives on the snapshot document and on match transition rows.
	## Pause may change phase/UI without changing this digest (VF5 + VF6-WP1).
	return {
		"schema": str(snap.get("schema", "")),
		"schema_version": int(snap.get("schema_version", 0)),
		"tick": int(snap.get("tick", 0)),
		"seed": int(snap.get("seed", 0)),
		"epsilon": SimConstants.quantize(float(snap.get("epsilon", SimConstants.EPSILON))),
		"event_order": str(snap.get("event_order", "")),
		"map_id": str(snap.get("map_id", "")),
		"mode": str(snap.get("mode", "")),
		"living": int(snap.get("living", 0)),
		"fighters": snap.get("fighters", []),
		"pickups": snap.get("pickups", []),
		"bullets": snap.get("bullets", []),
		"grenades": snap.get("grenades", []),
		"respawn_count": int(snap.get("respawn_count", 0)),
	}


static func match_payload(snap: Dictionary) -> Dictionary:
	## Recomputable match-identity digest: physics plus destination lifecycle.
	var row: Dictionary = hash_payload(snap)
	row["phase"] = str(snap.get("phase", ""))
	row["end_reason"] = str(snap.get("end_reason", ""))
	row["round_id"] = int(snap.get("round_id", 0))
	row["timer_enabled"] = int(snap.get("timer_enabled", 0))
	row["timer_left"] = int(snap.get("timer_left", -1))
	row["countdown_left"] = int(snap.get("countdown_left", 0))
	row["winner_team"] = int(snap.get("winner_team", -1))
	row["alignment"] = str(snap.get("alignment", ""))
	row["outcome"] = str(snap.get("outcome", ""))
	return row


static func stable_hash(snap: Dictionary) -> String:
	return _sha256(canonical(hash_payload(snap)))


static func match_hash(snap: Dictionary) -> String:
	return _sha256(canonical(match_payload(snap)))


static func _sha256(text: String) -> String:
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(text.to_utf8_buffer())
	return ctx.finish().hex_encode()


static func canonical(value: Variant) -> String:
	var kind: int = typeof(value)
	if kind == TYPE_DICTIONARY:
		var d: Dictionary = value as Dictionary
		var keys: Array = d.keys()
		keys.sort()
		var parts: PackedStringArray = PackedStringArray()
		var i: int = 0
		while i < keys.size():
			var k: String = str(keys[i])
			parts.append("%s:%s" % [k, canonical(d[keys[i]])])
			i += 1
		return "{%s}" % ",".join(parts)
	if kind == TYPE_ARRAY:
		var arr: Array = value as Array
		var parts_a: PackedStringArray = PackedStringArray()
		var j: int = 0
		while j < arr.size():
			parts_a.append(canonical(arr[j]))
			j += 1
		return "[%s]" % ",".join(parts_a)
	if kind == TYPE_BOOL:
		return "1" if bool(value) else "0"
	if kind == TYPE_FLOAT:
		return str(SimConstants.quantize(float(value)))
	if kind == TYPE_NIL:
		return "null"
	return str(value)


static func _fighter_row(f: Fighter) -> Dictionary:
	if f == null or not is_instance_valid(f):
		return {"slot": -1, "dead": 1}
	return {
		"slot": f.slot,
		"team": f.team,
		"x": SimConstants.quantize(f.global_position.x),
		"y": SimConstants.quantize(f.global_position.y),
		"vx": SimConstants.quantize(f.velocity.x),
		"vy": SimConstants.quantize(f.velocity.y),
		"hp": SimConstants.quantize(f.health),
		"stamina": SimConstants.quantize(f.stamina),
		"dead": 1 if f.dead else 0,
		"death_cause": f.death_cause,
		"weapon": f.weapon_id,
		"gun": f.gun_id,
		"melee": f.melee_id,
		"explosive": f.explosive_id,
		"power": f.power_id,
		"power_ammo": f.power_ammo,
		"nades": f.grenades,
		"ammo": f.ammo,
		"reserve": f.reserve,
		"reload": f.reload_left,
		"facing": SimConstants.quantize(f.facing),
		"crouched": 1 if f.crouched else 0,
		"sprinting": 1 if f.sprinting else 0,
		"rolling": 1 if f.rolling else 0,
		"diving": 1 if f.diving else 0,
		"kicking": 1 if f.kicking else 0,
		"pose": f.current_pose(),
		"invuln": SimConstants.quantize(f.invuln),
		"invuln_ticks": f.invuln_ticks,
		"knockdown": 1 if f.knockdown_left > 0.0 else 0,
		"getup": 1 if f.getup_left > 0.0 else 0,
		"hit_airborne": 1 if f.hit_airborne else 0,
		"roll_seq": f.roll_seq,
		"dive_seq": f.dive_seq,
		"kick_seq": f.kick_seq,
		"attack_phase": f.attack_phase,
		"attack_seq": f.attack_seq,
		"attack_style": f.attack_style,
		"attack_age": f.attack_age,
		"on_ladder": 1 if f.on_ladder else 0,
		"climbing": 1 if f.climbing else 0,
		"hanging": 1 if f.hanging else 0,
		"climb_seq": f.climb_seq,
		"hang_seq": f.hang_seq,
		"contact_nx": SimConstants.quantize(f.last_contact_nx),
		"contact_ny": SimConstants.quantize(f.last_contact_ny),
		"wet": 1 if f.wet else 0,
		"acid": 1 if f.acid_contact else 0,
		"aiming": 1 if f.aiming else 0,
		"aim_x": SimConstants.quantize(f.aim_dir.x),
		"aim_y": SimConstants.quantize(f.aim_dir.y),
	}


static func _sort_by_xy_id(rows: Array) -> void:
	rows.sort_custom(_row_less)


static func _row_less(a: Variant, b: Variant) -> bool:
	var da: Dictionary = a as Dictionary
	var db: Dictionary = b as Dictionary
	var ax: int = int(da.get("x", 0))
	var bx: int = int(db.get("x", 0))
	if ax != bx:
		return ax < bx
	var ay: int = int(da.get("y", 0))
	var by: int = int(db.get("y", 0))
	if ay != by:
		return ay < by
	return str(da.get("id", da.get("owner", ""))) < str(db.get("id", db.get("owner", "")))
