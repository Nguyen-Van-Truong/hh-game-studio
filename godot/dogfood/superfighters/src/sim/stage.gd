class_name StageRules
extends RefCounted

## Stage campaign: four arenas, persist, reset/continue.
## Order and tiers are ledger:RL-STAGE-ORDER / RL-STAGE-TIER
## (approximation, not observed). Survival stays VF6-WP4.

const PATH: String = "res://data/sim/stage.json"
const SCHEMA_ID: String = "vf.sim.stage.v1"
const STORE_DIR: String = "user://vf_stage/"
const STORE_FILE: String = "progress.json"

static var _cache: Dictionary = {}
static var last_error: String = ""
static var last_save_path: String = ""


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = data()
	if row.is_empty():
		errors.append("missing data/sim/stage.json")
		return errors
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("stage schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("stage title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("stage must not claim Y8 parity")
	if bool(row.get("y8_order_observed", true)):
		errors.append("stage order must not be marked observed")
	if str(row.get("order_class", "")) != "approximation":
		errors.append("stage order must stay approximation")
	if str(row.get("difficulty_class", "")) != "approximation":
		errors.append("stage difficulty must stay approximation")
	if bool(row.get("difficulty_observed", true)):
		errors.append("stage difficulty must not be marked observed")
	if bool(row.get("survival_shipped", true)):
		errors.append("stage must not ship Survival")
	if not bool(row.get("canonical", false)):
		errors.append("stage catalog must be canonical")
	var arenas: Array = _array(row.get("arenas", []))
	if arenas.size() != 4:
		errors.append("stage must list four core arenas")
	var expected: PackedStringArray = Maps.stage_ids()
	var i: int = 0
	while i < arenas.size():
		var arena: Dictionary = _dict(arenas[i])
		if int(arena.get("index", -1)) != i:
			errors.append("stage arena index must be sequential")
		if i < expected.size() and str(arena.get("map_id", "")) != String(expected[i]):
			errors.append("stage map %d must be %s" % [i, String(expected[i])])
		if int(arena.get("bots", 0)) < 1:
			errors.append("stage %d must list a bot roster" % i)
		if str(arena.get("tier_id", "")) == "":
			errors.append("stage %d missing tier_id" % i)
		i += 1
	return errors


static func arena_ids() -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var arenas: Array = _array(data().get("arenas", []))
	var i: int = 0
	while i < arenas.size():
		out.append(str(_dict(arenas[i]).get("map_id", "")))
		i += 1
	return out


static func stage_count() -> int:
	return _array(data().get("arenas", [])).size()


static func map_at(index: int) -> String:
	var arena: Dictionary = arena_at(index)
	var mid: String = str(arena.get("map_id", ""))
	if mid != "":
		return mid
	return Maps.stage_map_at(index)


static func arena_at(index: int) -> Dictionary:
	var arenas: Array = _array(data().get("arenas", []))
	if index < 0:
		index = 0
	if index >= arenas.size():
		index = arenas.size() - 1
	if index < 0 or index >= arenas.size():
		return {}
	return _dict(arenas[index])


static func bot_count(index: int) -> int:
	return maxi(int(arena_at(index).get("bots", 1)), 1)


static func tier_id(index: int) -> String:
	return str(arena_at(index).get("tier_id", "tier_1"))


static func score_for(index: int) -> int:
	return maxi(int(arena_at(index).get("score", 0)), 0)


static func unlock_for(index: int) -> String:
	return str(arena_at(index).get("unlock", ""))


static func store_filename() -> String:
	var env: String = OS.get_environment("HH_VF_STAGE_STORE")
	if env != "" and not env.contains("..") and not env.contains("/") and not env.contains("\\"):
		return env
	return STORE_FILE


static func store_rel() -> String:
	return STORE_DIR + store_filename()


static func empty_progress() -> Dictionary:
	var row: Dictionary = {
		"schema": SCHEMA_ID,
		"title": "Vault Fighters",
		"schema_version": 1,
		"current_index": 0,
		"score": 0,
		"awarded": [],
		"unlocks": [],
		"cleared": false,
		"y8_parity_claimed": false,
	}
	row["reward_hash"] = compute_hash(row)
	return row


static func load_or_empty() -> Dictionary:
	var rel: String = store_rel()
	var loaded: Dictionary = _load_progress_file(rel)
	if not loaded.is_empty():
		return loaded
	loaded = _load_progress_file(rel + ".tmp")
	if not loaded.is_empty():
		return loaded
	loaded = _load_progress_file(rel + ".bak")
	if not loaded.is_empty():
		return loaded
	return empty_progress()


static func _load_progress_file(rel: String) -> Dictionary:
	if not FileAccess.file_exists(rel):
		return {}
	var loaded: Dictionary = SimConstants.load_json(rel)
	if loaded.is_empty() or str(loaded.get("schema", "")) != SCHEMA_ID:
		return {}
	if str(loaded.get("title", "")) != "Vault Fighters":
		return {}
	return loaded


static func reset_progress() -> Dictionary:
	var row: Dictionary = empty_progress()
	if persist_atomic(row) == "":
		return load_or_empty()
	return row


static func record_win(won_index: int) -> Dictionary:
	last_error = ""
	var progress: Dictionary = load_or_empty()
	var current: int = int(progress.get("current_index", 0))
	var awarded: Array = _array(progress.get("awarded", []))
	var already: bool = _has_int(awarded, won_index)
	if not already and won_index != current:
		last_error = "stage win index mismatch"
		last_save_path = ""
		return progress
	if already:
		progress["reward_hash"] = compute_hash(progress)
		if persist_atomic(progress) == "":
			return load_or_empty()
		return load_or_empty()
	var next: Dictionary = progress.duplicate(true)
	var next_awarded: Array = _array(next.get("awarded", [])).duplicate()
	next_awarded.append(won_index)
	next["score"] = int(next.get("score", 0)) + score_for(won_index)
	var unlock: String = unlock_for(won_index)
	var unlocks: Array = _array(next.get("unlocks", [])).duplicate()
	if unlock != "" and not unlocks.has(unlock):
		unlocks.append(unlock)
	next["unlocks"] = unlocks
	next["awarded"] = next_awarded
	var last: int = stage_count() - 1
	if won_index >= last:
		next["current_index"] = last
		next["cleared"] = true
	else:
		next["current_index"] = won_index + 1
		next["cleared"] = false
	next["reward_hash"] = compute_hash(next)
	if persist_atomic(next) == "":
		return progress
	return load_or_empty()


static func persist_atomic(payload: Dictionary) -> String:
	last_error = ""
	last_save_path = ""
	if str(payload.get("schema", "")) != SCHEMA_ID:
		last_error = "stage save schema mismatch"
		return ""
	if str(payload.get("title", "")) != "Vault Fighters":
		last_error = "stage save title must be Vault Fighters"
		return ""
	if bool(payload.get("y8_parity_claimed", false)):
		last_error = "stage save must not claim Y8 parity"
		return ""
	var name: String = store_filename()
	if name.contains("..") or name.contains("/") or name.contains("\\"):
		last_error = "illegal stage filename"
		return ""
	var to_write: Dictionary = payload.duplicate(true)
	to_write["schema_hash"] = FileAccess.get_sha256(PATH)
	to_write["title"] = "Vault Fighters"
	to_write["y8_parity_claimed"] = false
	to_write["reward_hash"] = compute_hash(to_write)
	var dir_abs: String = ProjectSettings.globalize_path(STORE_DIR)
	DirAccess.make_dir_recursive_absolute(dir_abs)
	var rel: String = STORE_DIR + name
	var tmp: String = rel + ".tmp"
	var file: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		last_error = "stage tmp open failed"
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
			last_error = "stage old bak remove failed"
			last_save_path = ""
			return ""
	if FileAccess.file_exists(rel):
		var parked: Error = DirAccess.rename_absolute(abs_final, abs_bak)
		if parked != OK:
			DirAccess.remove_absolute(abs_tmp)
			last_error = "stage bak park failed"
			last_save_path = ""
			return ""
	var err: Error = DirAccess.rename_absolute(abs_tmp, abs_final)
	if err != OK:
		if FileAccess.file_exists(rel + ".bak"):
			DirAccess.rename_absolute(abs_bak, abs_final)
		DirAccess.remove_absolute(abs_tmp)
		last_error = "stage rename failed"
		last_save_path = ""
		return ""
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(abs_tmp)
	var verify: Dictionary = _load_progress_file(rel)
	if verify.is_empty() or str(verify.get("reward_hash", "")) != str(to_write.get("reward_hash", "")):
		last_error = "stage persist verify failed"
		last_save_path = ""
		return ""
	last_save_path = rel
	return rel


static func compute_hash(progress: Dictionary) -> String:
	var awarded: Array = _array(progress.get("awarded", [])).duplicate()
	awarded.sort()
	var unlocks: Array = _array(progress.get("unlocks", [])).duplicate()
	unlocks.sort()
	var awarded_s: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < awarded.size():
		awarded_s.append(str(int(awarded[i])))
		i += 1
	var unlock_s: PackedStringArray = PackedStringArray()
	i = 0
	while i < unlocks.size():
		unlock_s.append(str(unlocks[i]))
		i += 1
	var canonical: String = "%s|%d|%d|%s|%s|%d" % [
		SCHEMA_ID,
		int(progress.get("current_index", 0)),
		int(progress.get("score", 0)),
		",".join(awarded_s),
		",".join(unlock_s),
		1 if bool(progress.get("cleared", false)) else 0,
	]
	var ctx: HashingContext = HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	ctx.update(canonical.to_utf8_buffer())
	return ctx.finish().hex_encode()


static func caption_for(progress: Dictionary) -> String:
	if bool(progress.get("cleared", false)):
		return "Stage (cleared)"
	if int(progress.get("current_index", 0)) > 0:
		return "Continue Stage"
	return "Stage"


static func _has_int(rows: Array, value: int) -> bool:
	var i: int = 0
	while i < rows.size():
		if int(rows[i]) == value:
			return true
		i += 1
	return false


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}


static func _array(value: Variant) -> Array:
	if value is Array:
		return value as Array
	return []
