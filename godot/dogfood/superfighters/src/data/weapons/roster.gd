class_name WeaponRoster
extends RefCounted

## Data-driven weapon roster (VF3-WP5). Values are tuning.
## Does not claim original Y8 numbers. Slots stay
## ledger:RL-ITEM-SLOTS-4 (assumption). Roster stays
## ledger:RL-ITEM-ROSTER (assumption). Pickup slot replace
## stays ledger:RL-ITEM-PICK-SLOT (assumption). Keep-gun
## stays ledger:RL-ITEM-KEEP-GUN (assumption). Ammo/reload
## stay ledger:RL-ITEM-AMMO-RELOAD (assumption). Hold-to-aim
## stays ledger:RL-CTRL-HOLD-AIM (assumption). Y8 roll/dive
## stays ledger:RL-MOVE-ROLL-DIVE (unavailable).

const PATH: String = "res://data/weapons/roster.json"
const SCHEMA_PATH: String = "res://data/weapons/schema.json"
const SCHEMA_ID: String = "vf.weapons.roster.v1"
const GATE_SCHEMA_ID: String = "vf.weapons.schema.v1"

static var _cache: Dictionary = {}
static var _schema_cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func schema() -> Dictionary:
	if _schema_cache.is_empty():
		_schema_cache = SimConstants.load_json(SCHEMA_PATH)
	return _schema_cache


static func item(weapon_id: String) -> Dictionary:
	var items: Dictionary = _dict(data().get("items", {}))
	if items.has(weapon_id):
		return _dict(items.get(weapon_id, {}))
	return {}


static func ids() -> PackedStringArray:
	var items: Dictionary = _dict(data().get("items", {}))
	var keys: Array = items.keys()
	keys.sort()
	var out: PackedStringArray = PackedStringArray()
	var i: int = 0
	while i < keys.size():
		out.append(str(keys[i]))
		i += 1
	return out


static func spawn_pool() -> PackedStringArray:
	var raw: Variant = data().get("spawn_pool", [])
	var out: PackedStringArray = PackedStringArray()
	if raw is Array:
		var arr: Array = raw as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	return out


static func start_row() -> Dictionary:
	return _dict(data().get("start", {}))


static func start_melee() -> String:
	return str(start_row().get("melee", "fists"))


static func start_gun() -> String:
	return str(start_row().get("firearm", "pistol"))


static func start_ammo() -> int:
	return int(start_row().get("ammo", 12))


static func start_nades() -> int:
	return int(start_row().get("nades", 3))


static func start_explosive() -> String:
	return str(start_row().get("explosive", "grenade"))


static func start_power() -> String:
	return str(start_row().get("power", ""))


static func canonicalize_slot(raw: String) -> String:
	if raw == "gun":
		return "firearm"
	if raw == "nade":
		return "explosive"
	return raw


static func slot_of(weapon_id: String) -> String:
	return canonicalize_slot(str(item(weapon_id).get("slot", "melee")))


static func replacement_of(weapon_id: String) -> String:
	var slot: String = slot_of(weapon_id)
	var all: PackedStringArray = ids()
	var i: int = 0
	while i < all.size():
		var other: String = String(all[i])
		if other != weapon_id and slot_of(other) == slot:
			return other
		i += 1
	return ""


static func is_throw(weapon_id: String) -> bool:
	return str(item(weapon_id).get("kind", "")) == "throw"


static func is_gun(weapon_id: String) -> bool:
	return str(item(weapon_id).get("kind", "")) == "gun"


static func is_melee(weapon_id: String) -> bool:
	return str(item(weapon_id).get("kind", "")) == "melee"


static func fixtures() -> Dictionary:
	return _dict(data().get("fixtures", {}))


static func fixture_names() -> Dictionary:
	return _dict(data().get("fixture_names", {}))


static func has_fixture(map_id: String) -> bool:
	return fixtures().has(map_id)


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(row: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	var gate: Dictionary = schema()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("roster schema id mismatch")
	if str(gate.get("schema", "")) != GATE_SCHEMA_ID:
		errors.append("weapons schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("roster title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("roster must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("roster must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("roster values must be marked tuning")
	if str(row.get("slots_class", "")) != "assumption":
		errors.append("slots must stay assumption")
	if str(row.get("roster_class", "")) != "assumption":
		errors.append("roster class must stay assumption")
	if str(row.get("pickup_class", "")) != "assumption":
		errors.append("pickup slot replace must stay assumption")
	if str(row.get("keep_gun_class", "")) != "assumption":
		errors.append("keep-gun must stay assumption")
	if str(row.get("ammo_class", "")) != "assumption":
		errors.append("ammo/reload must stay assumption")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	var allowed: PackedStringArray = _to_packed(gate.get("allowed_slots", []))
	var required_fields: PackedStringArray = _to_packed(gate.get("required_item_fields", []))
	var required_ids: PackedStringArray = _to_packed(gate.get("required_ids", []))
	var items: Dictionary = _dict(row.get("items", {}))
	var i: int = 0
	while i < required_ids.size():
		var rid: String = String(required_ids[i])
		if not items.has(rid):
			errors.append("roster missing required id %s" % rid)
		i += 1
	var keys: Array = items.keys()
	keys.sort()
	var seen: Dictionary = {}
	var k: int = 0
	while k < keys.size():
		var wid: String = str(keys[k])
		var spec: Dictionary = _dict(items.get(wid, {}))
		if seen.has(wid):
			errors.append("duplicate roster id %s" % wid)
		seen[wid] = true
		if str(spec.get("id", "")) != wid:
			errors.append("roster item %s id mismatch" % wid)
		var name_v: String = str(spec.get("name", ""))
		if name_v == "":
			errors.append("roster item %s missing name" % wid)
		if name_v.to_lower().contains("superfighter"):
			errors.append("roster item %s uses Superfighters trademark" % wid)
		var slot: String = canonicalize_slot(str(spec.get("slot", "")))
		if not allowed.has(slot):
			errors.append("roster item %s slot %s is not allowed" % [wid, slot])
		var f: int = 0
		while f < required_fields.size():
			var field: String = String(required_fields[f])
			if not spec.has(field):
				errors.append("roster item %s missing %s" % [wid, field])
			f += 1
		var icon: String = str(spec.get("icon", ""))
		if icon == "" or not icon.begins_with("res://"):
			errors.append("roster item %s icon must be a res:// path" % wid)
		if float(spec.get("weight", -1.0)) < 0.0:
			errors.append("roster item %s weight must be >= 0" % wid)
		if int(spec.get("reload_ticks", -1)) < 0:
			errors.append("roster item %s reload_ticks must be >= 0" % wid)
		k += 1
	if not _dict(row.get("fixtures", {})).has("fx_roster_open"):
		errors.append("roster fixture fx_roster_open missing")
	return errors


static func _to_packed(value: Variant) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	if value is Array:
		var arr: Array = value as Array
		var i: int = 0
		while i < arr.size():
			out.append(str(arr[i]))
			i += 1
	elif value is PackedStringArray:
		return value as PackedStringArray
	return out


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
