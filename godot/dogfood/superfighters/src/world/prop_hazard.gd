class_name PropHazard
extends RefCounted

## Barrel chain, burn timer, roll extinguish, hanging drop (VF4-WP3).
## ledger:RL-PROP-EXPL / RL-PROP-CHAIN / RL-PROP-FIRE /
## RL-PROP-HANG / RL-PROP-EXTINGUISH (assumption). Not observed.
## Extinguish rule is roll. Water is not selected (VF4-WP5).
## RL-NADE-PROP stays deferred for glass/wood.

const PATH: String = "res://data/world/hazard.json"
const SCHEMA_ID: String = "vf.world.hazard.v1"
const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")

static var _cache: Dictionary = {}


static func data() -> Dictionary:
	if _cache.is_empty():
		_cache = SimConstants.load_json(PATH)
	return _cache


static func validate() -> PackedStringArray:
	return validate_payload(data())


static func validate_payload(row: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(row.get("schema", "")) != SCHEMA_ID:
		errors.append("hazard schema id mismatch")
	if str(row.get("title", "")) != "Vault Fighters":
		errors.append("hazard title must be Vault Fighters")
	if bool(row.get("y8_parity_claimed", true)):
		errors.append("hazard must not claim Y8 parity")
	if bool(row.get("original_exact_numbers_claimed", true)):
		errors.append("hazard must not claim original exact numbers")
	if not bool(row.get("values_are_tuning", false)):
		errors.append("hazard values must be marked tuning")
	if not bool(row.get("chain_implemented", false)):
		errors.append("hazard chain must be implemented this WP")
	if int(row.get("chain_max_depth", 0)) < 1:
		errors.append("hazard chain_max_depth must be >= 1")
	if int(row.get("vfx_cap", 0)) < 1:
		errors.append("hazard vfx_cap must be >= 1")
	if str(row.get("extinguish_rule", "")) != "roll":
		errors.append("hazard extinguish rule must be roll")
	if bool(row.get("water_selected", true)):
		errors.append("water extinguish must stay unselected")
	if str(row.get("nade_prop_class", "")) != "deferred":
		errors.append("RL-NADE-PROP must stay deferred")
	if str(row.get("expl_class", "")) != "assumption":
		errors.append("explosive chain must stay assumption")
	if str(row.get("hold_to_aim_class", "")) != "assumption":
		errors.append("hold-to-aim must stay assumption")
	if str(row.get("roll_dive_class", "")) != "unavailable":
		errors.append("Y8 roll/dive observation must stay unavailable")
	if str(row.get("title", "")).to_lower().contains("superfighter"):
		errors.append("hazard title uses Superfighters trademark")
	return errors


static func chain_max_depth() -> int:
	return maxi(int(data().get("chain_max_depth", 2)), 0)


static func chain_radius() -> float:
	return float(data().get("chain_radius", 40.0))


static func explode_damage() -> float:
	return float(data().get("explode_damage", 12.0))


static func explode_radius() -> float:
	return float(data().get("explode_radius", 40.0))


static func fire_radius() -> float:
	return float(data().get("fire_radius", 40.0))


static func burn_ticks() -> int:
	return maxi(int(data().get("burn_ticks", 48)), 1)


static func burn_interval() -> int:
	return maxi(int(data().get("burn_interval", 12)), 1)


static func burn_damage() -> float:
	return float(data().get("burn_damage", 3.0))


static func vfx_cap() -> int:
	return maxi(int(data().get("vfx_cap", 4)), 1)


static func vfx_per_explode() -> int:
	return maxi(int(data().get("vfx_per_explode", 2)), 1)


static func vfx_life() -> int:
	return maxi(int(data().get("vfx_life_ticks", 18)), 1)


static func drop_impulse() -> float:
	return float(data().get("drop_impulse", 280.0))


static func explode_visual() -> String:
	return str(data().get("explode_visual", "res://assets/vfx/vfx_explode.png"))


static func fire_visual() -> String:
	return str(data().get("fire_visual", "res://assets/vfx/vfx_fire.png"))


static func is_hanging_spec(spec: Dictionary) -> bool:
	return bool(spec.get("hanging", false))


static func is_flammable_spec(spec: Dictionary) -> bool:
	if spec.has("flammable"):
		return bool(spec.get("flammable", false))
	var mats: Dictionary = _dict(_Catalog.data().get("materials", {}))
	var mat: Dictionary = _dict(mats.get(str(spec.get("material", "")), {}))
	return bool(mat.get("flammable", false))


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
