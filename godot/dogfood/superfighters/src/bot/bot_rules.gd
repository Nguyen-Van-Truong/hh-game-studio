class_name BotRules
extends RefCounted

## Seeded bot difficulty profiles (VF6-WP5).
## Difficulty is reaction delay, aim error, tactical budget,
## and recovery wait. Not observed Y8. ledger:RL-BOT-DIFF.

const PATH: String = "res://data/sim/bots.json"
const SCHEMA_ID: String = "vf.sim.bots.v1"

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func reload() -> void:
	_cache = {}


static func validate() -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var row: Dictionary = data()
	if row.is_empty():
		errors.append("missing data/sim/bots.json")
		return errors
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("bots schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("bots title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("bots must not claim Y8 parity")
	if str(row.get("planner_class", "")) != "assumption":
		errors.append("bot planner must stay assumption")
	if bool(row.get("planner_observed", true)):
		errors.append("bot planner must not be marked observed")
	if not bool(row.get("no_teleport", false)):
		errors.append("bots must forbid teleport")
	if not bool(row.get("no_perfect_aim", false)):
		errors.append("bots must forbid perfect aim")
	if not bool(row.get("no_hidden_state", false)):
		errors.append("bots must forbid hidden omniscient state")
	if not bool(row.get("not_omniscient", false)):
		errors.append("bots must be marked not omniscient")
	var profiles: Dictionary = _dict(row.get("profiles", {}))
	if not profiles.has("recruit") or not profiles.has("regular") or not profiles.has("veteran"):
		errors.append("bots must list recruit/regular/veteran")
	var ids: PackedStringArray = PackedStringArray(["recruit", "regular", "veteran"])
	var i: int = 0
	while i < ids.size():
		var spec: Dictionary = _dict(profiles.get(String(ids[i]), {}))
		if float(spec.get("aim_error_deg", 0.0)) < 4.0:
			errors.append("%s aim_error_deg must stay visible" % String(ids[i]))
		if int(spec.get("reaction_ticks", 0)) < 4:
			errors.append("%s reaction_ticks must stay visible" % String(ids[i]))
		if int(spec.get("tactical_budget", 0)) < 1:
			errors.append("%s missing tactical_budget" % String(ids[i]))
		if int(spec.get("max_expansions", 0)) > int(row.get("max_expansions_cap", 64)):
			errors.append("%s expansions exceed cap" % String(ids[i]))
		i += 1
	return errors


static func profile_ids() -> PackedStringArray:
	var keys: Array = _dict(data().get("profiles", {})).keys()
	keys.sort()
	var out: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < keys.size():
		out.append(str(keys[i]))
		i += 1
	return out


static func profile(profile_id: String) -> Dictionary:
	var profiles: Dictionary = _dict(data().get("profiles", {}))
	var key: String = profile_id
	if not profiles.has(key):
		key = str(data().get("default_profile", "regular"))
	return _dict(profiles.get(key, {})).duplicate(true)


static func default_profile_id() -> String:
	return str(data().get("default_profile", "regular"))


static func profile_for_tier(tier_id: String) -> String:
	var mapped: Dictionary = _dict(data().get("tier_map", {}))
	if mapped.has(tier_id):
		return str(mapped.get(tier_id, "regular"))
	return default_profile_id()


static func profile_for_wave(wave_index: int) -> String:
	var mapped: Dictionary = _dict(data().get("wave_map", {}))
	var key: String = str(maxi(wave_index, 0))
	if mapped.has(key):
		return str(mapped.get(key, "regular"))
	if wave_index >= 4:
		return "veteran"
	if wave_index >= 2:
		return "regular"
	return "recruit"


static func profile_for_mode(mode: String, stage_index: int, wave_index: int) -> String:
	if mode == "stage":
		return profile_for_tier(StageRules.tier_id(stage_index))
	if mode == "survival":
		return profile_for_wave(wave_index)
	return default_profile_id()


static func hud_line(profile_id: String) -> String:
	var spec: Dictionary = profile(profile_id)
	return "Bot skill %s · delay %d · aim±%.0f° · budget %d" % [
		profile_id,
		int(spec.get("reaction_ticks", 0)),
		float(spec.get("aim_error_deg", 0.0)),
		int(spec.get("tactical_budget", 0)),
	]


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
