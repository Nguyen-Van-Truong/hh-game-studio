class_name PropBreak
extends RefCounted

## Break / shove / throw helpers (VF4-WP2).
## ledger:RL-PROP-BREAK / RL-PROP-DYNAMIC (assumption). Not observed.
## RL-NADE-PROP stays deferred.

const _Catalog: GDScript = preload("res://src/world/world_catalog.gd")


static func material_of(spec: Dictionary) -> String:
	return str(spec.get("material", ""))


static func material_row(name: String) -> Dictionary:
	var mats: Dictionary = _dict(_Catalog.data().get("materials", {}))
	if mats.has(name):
		return _dict(mats.get(name, {}))
	return {}


static func bullet_mult(spec: Dictionary) -> float:
	var row: Dictionary = material_row(material_of(spec))
	return float(row.get("bullet_mult", 1.0))


static func melee_mult(spec: Dictionary) -> float:
	var row: Dictionary = material_row(material_of(spec))
	return float(row.get("melee_mult", 1.0))


static func debris_count(spec: Dictionary) -> int:
	var row: Dictionary = material_row(material_of(spec))
	return maxi(int(row.get("debris_count", 0)), 0)


static func debris_life(spec: Dictionary) -> int:
	var row: Dictionary = material_row(material_of(spec))
	return maxi(int(row.get("debris_life_ticks", 18)), 1)


static func debris_visual() -> String:
	return str(_Catalog.data().get("debris_visual", "res://assets/vfx/vfx_break.png"))


static func scale_damage(raw: float, spec: Dictionary, source: String) -> float:
	var mult: float = 1.0
	if source == "bullet":
		mult = bullet_mult(spec)
	elif source == "melee":
		mult = melee_mult(spec)
	return raw * mult


static func throw_speed() -> float:
	return float(_Catalog.data().get("throw_speed", 260.0))


static func throw_lift() -> float:
	return float(_Catalog.data().get("throw_lift", -160.0))


static func shove_speed() -> float:
	return float(_Catalog.data().get("shove_speed", 180.0))


static func gravity() -> float:
	return float(_Catalog.data().get("prop_gravity", 900.0))


static func friction() -> float:
	return float(_Catalog.data().get("prop_friction", 1400.0))


static func carry_radius() -> float:
	return float(_Catalog.data().get("carry_radius", 20.0))


static func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
