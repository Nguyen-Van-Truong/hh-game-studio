class_name SurvivalRules
extends RefCounted

## Survival director: endless wave/score loop, not a Stage checkpoint.
## Loop/wave/score/spawn are ledger:RL-SURVIVAL-* (approximation).
## Records persist best score only. Restart clears the run.

const PATH: String = "res://data/sim/survival.json"
const SCHEMA_ID: String = "vf.sim.survival.v1"
const STORE_DIR: String = "user://vf_survival/"
const STORE_FILE: String = "records.json"

static var _cache: Dictionary = {}
static var last_error: String = ""
static var last_save_path: String = ""

var score: int = 0
var wave_index: int = 0
var combo: int = 0
var combo_ticks_left: int = 0
var kills: int = 0
var kills_this_wave: int = 0
var survive_accum: int = 0
var next_spawn_tick: int = 0
var next_weapon_tick: int = 0
var next_prop_tick: int = 0
var spawned_this_wave: int = 0
var weapon_respawns: int = 0
var prop_respawns: int = 0
var refused_spawns: int = 0
var refused_cap: int = 0
var last_deny_reason: String = ""
var last_deny_living: int = 0
var score_from_kills: int = 0
var score_from_combo: int = 0
var score_from_wave: int = 0
var score_from_survive: int = 0
var max_living_bots: int = 0
var max_pickups: int = 0
var max_fighters: int = 0
var score_samples: Array = []
var finished: bool = false
var last_run_score: int = 0
var seed_used: int = 7


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = data()
	if row.is_empty():
		errors.append("missing data/sim/survival.json")
		return errors
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("survival schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("survival title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("survival must not claim Y8 parity")
	if str(row.get("loop_class", "")) != "approximation":
		errors.append("survival loop must stay approximation")
	if str(row.get("wave_class", "")) != "approximation":
		errors.append("survival wave must stay approximation")
	if str(row.get("score_class", "")) != "approximation":
		errors.append("survival score must stay approximation")
	if str(row.get("spawn_class", "")) != "approximation":
		errors.append("survival spawn must stay approximation")
	if bool(row.get("loop_observed", true)):
		errors.append("survival loop must not be marked observed")
	if not bool(row.get("canonical", false)):
		errors.append("survival catalog must be canonical")
	if bool(row.get("not_ai", false)) != true:
		errors.append("survival bots must stay smoke / NOT_AI")
	var caps: Dictionary = _dict(row.get("entity_caps", {}))
	if int(caps.get("living_bots", 0)) < 1:
		errors.append("survival must cap living bots")
	var waves: Array = _array(row.get("waves", []))
	if waves.size() < 2:
		errors.append("survival must list escalating waves")
	var prev: int = 0
	var i: int = 0
	while i < waves.size():
		var wave: Dictionary = _dict(waves[i])
		var bots: int = int(wave.get("bots", 0))
		if bots < 1:
			errors.append("survival wave %d missing bots" % i)
		if i > 0 and bots < prev:
			errors.append("survival waves must escalate or hold")
		prev = bots
		i += 1
	return errors


static func caps() -> Dictionary:
	return _dict(data().get("entity_caps", {}))


static func cap_living_bots() -> int:
	return maxi(int(caps().get("living_bots", 6)), 1)


static func cap_fighters() -> int:
	return maxi(int(caps().get("fighters", 8)), 2)


static func cap_pickups() -> int:
	return maxi(int(caps().get("pickups", 12)), 1)


static func wave_at(index: int) -> Dictionary:
	var waves: Array = _array(data().get("waves", []))
	if waves.is_empty():
		return {"index": 0, "bots": 1, "interval_ticks": 180, "quota": 1, "score": 50}
	if index < 0:
		index = 0
	if index < waves.size():
		return _dict(waves[index])
	var last: Dictionary = _dict(waves[waves.size() - 1]).duplicate(true)
	last["index"] = index
	last["bots"] = cap_living_bots()
	return last


static func initial_bots() -> int:
	return maxi(int(wave_at(0).get("bots", 1)), 1)


static func store_filename() -> String:
	var env: String = OS.get_environment("HH_VF_SURVIVAL_STORE")
	if env != "" and not env.contains("..") and not env.contains("/") and not env.contains("\\"):
		return env
	return STORE_FILE


static func store_rel() -> String:
	return STORE_DIR + store_filename()


static func empty_records() -> Dictionary:
	var row: Dictionary = {
		"schema": SCHEMA_ID,
		"title": "Vault Fighters",
		"schema_version": 1,
		"best_score": 0,
		"best_wave": 0,
		"best_combo": 0,
		"runs": 0,
		"y8_parity_claimed": false,
	}
	row["record_hash"] = compute_hash(row)
	return row


static func load_records() -> Dictionary:
	var rel: String = store_rel()
	var loaded: Dictionary = _load_file(rel)
	if not loaded.is_empty():
		return loaded
	loaded = _load_file(rel + ".tmp")
	if not loaded.is_empty():
		return loaded
	loaded = _load_file(rel + ".bak")
	if not loaded.is_empty():
		return loaded
	return empty_records()


static func _load_file(rel: String) -> Dictionary:
	if not FileAccess.file_exists(rel):
		return {}
	var loaded: Dictionary = SimConstants.load_json(rel)
	if loaded.is_empty() or str(loaded.get("schema", "")) != SCHEMA_ID:
		return {}
	if str(loaded.get("title", "")) != "Vault Fighters":
		return {}
	return loaded


static func persist_records(payload: Dictionary) -> String:
	last_error = ""
	last_save_path = ""
	if str(payload.get("schema", "")) != SCHEMA_ID:
		last_error = "survival save schema mismatch"
		return ""
	if str(payload.get("title", "")) != "Vault Fighters":
		last_error = "survival save title must be Vault Fighters"
		return ""
	if bool(payload.get("y8_parity_claimed", false)):
		last_error = "survival save must not claim Y8 parity"
		return ""
	var name: String = store_filename()
	if name.contains("..") or name.contains("/") or name.contains("\\"):
		last_error = "illegal survival filename"
		return ""
	var to_write: Dictionary = payload.duplicate(true)
	to_write["schema_hash"] = FileAccess.get_sha256(PATH)
	to_write["title"] = "Vault Fighters"
	to_write["y8_parity_claimed"] = false
	to_write["record_hash"] = compute_hash(to_write)
	var dir_abs: String = ProjectSettings.globalize_path(STORE_DIR)
	DirAccess.make_dir_recursive_absolute(dir_abs)
	var rel: String = STORE_DIR + name
	var tmp: String = rel + ".tmp"
	var file: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		last_error = "survival tmp open failed"
		return ""
	file.store_string(JSON.stringify(to_write))
	file.flush()
	file.close()
	var abs_tmp: String = ProjectSettings.globalize_path(tmp)
	var abs_final: String = ProjectSettings.globalize_path(rel)
	var abs_bak: String = abs_final + ".bak"
	if FileAccess.file_exists(rel + ".bak"):
		var cleared: Error = DirAccess.remove_absolute(abs_bak)
		if cleared != OK:
			DirAccess.remove_absolute(abs_tmp)
			last_error = "survival old bak remove failed"
			return ""
	if FileAccess.file_exists(rel):
		var parked: Error = DirAccess.rename_absolute(abs_final, abs_bak)
		if parked != OK:
			DirAccess.remove_absolute(abs_tmp)
			last_error = "survival bak park failed"
			return ""
	var err: Error = DirAccess.rename_absolute(abs_tmp, abs_final)
	if err != OK:
		if FileAccess.file_exists(rel + ".bak"):
			DirAccess.rename_absolute(abs_bak, abs_final)
		DirAccess.remove_absolute(abs_tmp)
		last_error = "survival rename failed"
		return ""
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(abs_tmp)
	var verify: Dictionary = _load_file(rel)
	if verify.is_empty() or str(verify.get("record_hash", "")) != str(to_write.get("record_hash", "")):
		last_error = "survival persist verify failed"
		return ""
	last_save_path = rel
	return rel


static func compute_hash(progress: Dictionary) -> String:
	var canonical: String = "%s|%d|%d|%d|%d" % [
		SCHEMA_ID,
		int(progress.get("best_score", 0)),
		int(progress.get("best_wave", 0)),
		int(progress.get("best_combo", 0)),
		int(progress.get("runs", 0)),
	]
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(canonical.to_utf8_buffer())
	return ctx.finish().hex_encode()


static func record_finish(run_score: int, run_wave: int, run_combo: int) -> Dictionary:
	var rec: Dictionary = load_records()
	var next: Dictionary = rec.duplicate(true)
	next["runs"] = int(next.get("runs", 0)) + 1
	if run_score > int(next.get("best_score", 0)):
		next["best_score"] = run_score
	if run_wave > int(next.get("best_wave", 0)):
		next["best_wave"] = run_wave
	if run_combo > int(next.get("best_combo", 0)):
		next["best_combo"] = run_combo
	next["record_hash"] = compute_hash(next)
	if persist_records(next) == "":
		return rec
	return load_records()


static func reset_records() -> Dictionary:
	var row: Dictionary = empty_records()
	if persist_records(row) == "":
		return load_records()
	return row


static func caption_best() -> String:
	var rec: Dictionary = load_records()
	return "Survival best %d" % int(rec.get("best_score", 0))


func reset_run() -> void:
	score = 0
	wave_index = 0
	combo = 0
	combo_ticks_left = 0
	kills = 0
	kills_this_wave = 0
	survive_accum = 0
	next_spawn_tick = 0
	next_weapon_tick = int(data().get("weapon_respawn_ticks", 1200))
	next_prop_tick = int(data().get("prop_respawn_ticks", 1800))
	spawned_this_wave = 0
	weapon_respawns = 0
	prop_respawns = 0
	refused_spawns = 0
	refused_cap = 0
	last_deny_reason = ""
	last_deny_living = 0
	score_from_kills = 0
	score_from_combo = 0
	score_from_wave = 0
	score_from_survive = 0
	max_living_bots = 0
	max_pickups = 0
	max_fighters = 0
	score_samples.clear()
	finished = false
	last_run_score = 0
	seed_used = 7


func begin(session: GameSession) -> void:
	reset_run()
	if session != null:
		seed_used = session.sim_seed
		next_spawn_tick = session.clock.tick if session.clock != null else 0
		_refresh_hud(session)


func tick(session: GameSession) -> void:
	if session == null or finished or session.outcome != "play":
		return
	if session.mode != "survival":
		return
	var tick_n: int = session.clock.tick if session.clock != null else 0
	if combo_ticks_left > 0:
		combo_ticks_left -= 1
		if combo_ticks_left <= 0:
			combo = 0
	survive_accum += 1
	var every: int = maxi(int(_dict(data().get("score", {})).get("survive_every_ticks", 60)), 1)
	var pts: int = maxi(int(_dict(data().get("score", {})).get("survive_points", 1)), 0)
	if survive_accum >= every:
		survive_accum = 0
		_add_score(pts, "survive")
	_note_caps(session)
	if tick_n >= next_spawn_tick:
		session.spawn_survival_bot()
		next_spawn_tick = tick_n + interval_ticks()
	if tick_n >= next_weapon_tick:
		if session.survival_drop_weapon():
			weapon_respawns += 1
		next_weapon_tick = tick_n + maxi(int(data().get("weapon_respawn_ticks", 1200)), 60)
	if tick_n >= next_prop_tick:
		if session.survival_drop_prop():
			prop_respawns += 1
		next_prop_tick = tick_n + maxi(int(data().get("prop_respawn_ticks", 1800)), 60)
	_maybe_advance_wave(session)
	if tick_n % 30 == 0:
		score_samples.append({"tick": tick_n, "score": score, "bots": session.living_bot_count()})
	_refresh_hud(session)


func on_death(session: GameSession, fighter: Fighter) -> void:
	if session == null or fighter == null or finished:
		return
	if fighter.is_bot:
		kills += 1
		kills_this_wave += 1
		var window: int = maxi(int(_dict(data().get("score", {})).get("combo_window_ticks", 180)), 1)
		if combo_ticks_left > 0:
			combo += 1
		else:
			combo = 1
		combo_ticks_left = window
		var kill_pts: int = maxi(int(_dict(data().get("score", {})).get("kill", 100)), 0)
		var step: int = maxi(int(_dict(data().get("score", {})).get("combo_step", 25)), 0)
		var combo_pts: int = step * maxi(combo - 1, 0)
		_add_score(kill_pts, "kill")
		_add_score(combo_pts, "combo")
		_maybe_advance_wave(session)
		_refresh_hud(session)
		return
	if fighter.slot == 0:
		finish_run(session)


func finish_run(session: GameSession) -> Dictionary:
	if finished:
		return load_records()
	finished = true
	last_run_score = score
	var rec: Dictionary = record_finish(score, wave_index, combo)
	if session != null:
		_refresh_hud(session)
	return rec


func interval_ticks() -> int:
	return maxi(int(wave_at(wave_index).get("interval_ticks", 180)), 30)


func target_bots() -> int:
	return mini(maxi(int(wave_at(wave_index).get("bots", 1)), 1), cap_living_bots())


func hud_line() -> String:
	var rec: Dictionary = load_records()
	return "Survival · Wave %d · Score %d · Combo x%d · Best %d" % [
		wave_index + 1,
		score,
		combo,
		int(rec.get("best_score", 0)),
	]


func snapshot_row() -> Dictionary:
	return {
		"score": score,
		"wave": wave_index,
		"combo": combo,
		"kills": kills,
		"kills_this_wave": kills_this_wave,
		"weapon_respawns": weapon_respawns,
		"prop_respawns": prop_respawns,
		"refused_spawns": refused_spawns,
		"refused_cap": refused_cap,
		"last_deny_reason": last_deny_reason,
		"last_deny_living": last_deny_living,
		"score_from_kills": score_from_kills,
		"score_from_combo": score_from_combo,
		"score_from_wave": score_from_wave,
		"score_from_survive": score_from_survive,
		"max_living_bots": max_living_bots,
		"max_pickups": max_pickups,
		"max_fighters": max_fighters,
		"finished": finished,
		"last_run_score": last_run_score,
		"seed": seed_used,
	}


func _maybe_advance_wave(session: GameSession) -> void:
	var quota: int = maxi(int(wave_at(wave_index).get("quota", 1)), 1)
	if kills_this_wave < quota:
		return
	var bonus: int = maxi(int(_dict(data().get("score", {})).get("wave_clear", 50)), 0)
	bonus += maxi(int(wave_at(wave_index).get("score", 0)), 0)
	_add_score(bonus, "wave")
	wave_index += 1
	kills_this_wave = 0
	spawned_this_wave = 0
	if session != null and session.clock != null:
		next_spawn_tick = session.clock.tick
	if session != null:
		session.ledger.push(session.clock.tick if session.clock != null else 0, "survival", "wave", {
			"wave": wave_index,
			"score": score,
			"seed": seed_used,
		})


func note_denied(reason: String, living: int) -> void:
	refused_spawns += 1
	last_deny_reason = reason
	last_deny_living = living
	if reason == "living_cap":
		refused_cap += 1


func _add_score(amount: int, source: String = "") -> void:
	if amount <= 0 or finished:
		return
	score += amount
	if source == "kill":
		score_from_kills += amount
	elif source == "combo":
		score_from_combo += amount
	elif source == "wave":
		score_from_wave += amount
	elif source == "survive":
		score_from_survive += amount


func _note_caps(session: GameSession) -> void:
	if session == null:
		return
	max_living_bots = maxi(max_living_bots, session.living_bot_count())
	max_pickups = maxi(max_pickups, session.pickups.size())
	max_fighters = maxi(max_fighters, session.fighters.size())


func _refresh_hud(session: GameSession) -> void:
	if session == null or session.hud == null:
		return
	session.hud.set_stage_line(hud_line())


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []
