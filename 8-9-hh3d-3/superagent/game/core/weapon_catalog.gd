class_name WeaponCatalog
extends RefCounted
## Typed, data-driven weapon definitions for the Classic prototype.
##
## This file is deliberately self-contained: gameplay systems can consume the
## definitions without importing presentation assets or reference-game data.
## Values are deterministic engineering seeds and are not parity claims.

const SCHEMA_VERSION: int = 1
const FIXED_HZ: int = 60

class WeaponDefinition extends RefCounted:
	var id: StringName = &""
	var display_name: String = ""
	var slot: StringName = &""
	var category: StringName = &""
	var tags: Array[StringName] = []

	# Shared combat values.  Melee entries use melee_reach/melee_damage;
	# firearms and explosives use damage and projectile metadata.
	var damage: int = 0
	var melee_damage: int = 0
	var melee_reach: float = 0.0
	var knockback: float = 0.0
	var cooldown_ticks: int = 0
	var range_limit: float = 0.0

	# Resource values are explicit for every entry, including melee weapons.
	var ammo_capacity: int = 0
	var magazine_size: int = 0
	var starting_ammo: int = 0
	var reserve_ammo: int = 0

	# Hitscan/projectile tuning.  A projectile dictionary carries the complete
	# bullet or rocket contract so future simulation code does not infer fields.
	var projectile_kind: StringName = &"none"
	var projectile_speed: float = 0.0
	var projectile_radius: float = 0.0
	var projectile_lifetime_ticks: int = 0
	var projectile_gravity_per_tick: float = 0.0
	var pellet_count: int = 1
	var spread_degrees: float = 0.0
	var projectile: Dictionary = {}

	# Explosive values are zero for non-explosive weapons.
	var fuse_ticks: int = 0
	var explosion_radius: float = 0.0
	var explosion_damage: int = 0

	func _init(source: Dictionary = {}) -> void:
		id = StringName(String(source.get("id", "")))
		display_name = String(source.get("display_name", ""))
		slot = StringName(String(source.get("slot", "")))
		category = StringName(String(source.get("category", "")))
		damage = int(source.get("damage", 0))
		melee_damage = int(source.get("melee_damage", damage))
		melee_reach = float(source.get("melee_reach", 0.0))
		knockback = float(source.get("knockback", 0.0))
		cooldown_ticks = int(source.get("cooldown_ticks", 0))
		range_limit = float(source.get("range_limit", 0.0))
		ammo_capacity = int(source.get("ammo_capacity", source.get("magazine_size", 0)))
		magazine_size = int(source.get("magazine_size", ammo_capacity))
		starting_ammo = int(source.get("starting_ammo", ammo_capacity))
		reserve_ammo = int(source.get("reserve_ammo", 0))
		projectile_kind = StringName(String(source.get("projectile_kind", "none")))
		projectile_speed = float(source.get("projectile_speed", 0.0))
		projectile_radius = float(source.get("projectile_radius", 0.0))
		projectile_lifetime_ticks = int(source.get("projectile_lifetime_ticks", 0))
		projectile_gravity_per_tick = float(source.get("projectile_gravity_per_tick", 0.0))
		pellet_count = maxi(1, int(source.get("pellet_count", 1)))
		spread_degrees = float(source.get("spread_degrees", 0.0))
		fuse_ticks = int(source.get("fuse_ticks", 0))
		explosion_radius = float(source.get("explosion_radius", 0.0))
		explosion_damage = int(source.get("explosion_damage", 0))

		var source_tags: Variant = source.get("tags", [])
		if typeof(source_tags) == TYPE_ARRAY:
			for value: Variant in Array(source_tags):
				tags.append(StringName(String(value)))
		tags.make_read_only()

		var source_projectile: Variant = source.get("projectile", {})
		if typeof(source_projectile) == TYPE_DICTIONARY:
			projectile = Dictionary(source_projectile).duplicate(true)
		else:
			projectile = {}
		projectile.make_read_only()

	func is_melee() -> bool:
		return category == &"melee"

	func is_explosive() -> bool:
		return category == &"explosive" or explosion_radius > 0.0

	func has_ammo() -> bool:
		return ammo_capacity > 0 or starting_ammo > 0 or reserve_ammo > 0

	func has_projectile() -> bool:
		return projectile_kind != &"none"

	func is_bullet() -> bool:
		return projectile_kind == &"bullet"

	func is_rocket() -> bool:
		return projectile_kind == &"rocket"

	func projectile_metadata() -> Dictionary:
		return projectile.duplicate(true)

	func to_dictionary() -> Dictionary:
		var result: Dictionary = {
			&"id": id,
			&"display_name": display_name,
			&"slot": slot,
			&"category": category,
			&"tags": tags.duplicate(),
			&"damage": damage,
			&"melee_damage": melee_damage,
			&"melee_reach": melee_reach,
			&"knockback": knockback,
			&"cooldown_ticks": cooldown_ticks,
			&"range_limit": range_limit,
			&"ammo_capacity": ammo_capacity,
			&"magazine_size": magazine_size,
			&"starting_ammo": starting_ammo,
			&"reserve_ammo": reserve_ammo,
			&"projectile_kind": projectile_kind,
			&"projectile_speed": projectile_speed,
			&"projectile_radius": projectile_radius,
			&"projectile_lifetime_ticks": projectile_lifetime_ticks,
			&"projectile_gravity_per_tick": projectile_gravity_per_tick,
			&"pellet_count": pellet_count,
			&"spread_degrees": spread_degrees,
			&"projectile": projectile.duplicate(true),
			&"fuse_ticks": fuse_ticks,
			&"explosion_radius": explosion_radius,
			&"explosion_damage": explosion_damage,
		}
		result.make_read_only()
		return result


# The raw rows are the only authored source of values.  Keeping them in one
# table makes adding a weapon a data change rather than a branch in combat.
const _RAW_DEFINITIONS: Array[Dictionary] = [
	{
		"id": "fists",
		"display_name": "Vault Fists",
		"slot": "melee",
		"category": "melee",
		"tags": ["melee", "unarmed"],
		"damage": 12,
		"melee_damage": 12,
		"melee_reach": 56.0,
		"knockback": 10.0,
		"cooldown_ticks": 8,
		"range_limit": 56.0,
	},
	{
		"id": "pipe",
		"display_name": "Copper Pipe",
		"slot": "melee",
		"category": "melee",
		"tags": ["melee", "heavy"],
		"damage": 20,
		"melee_damage": 20,
		"melee_reach": 64.0,
		"knockback": 14.0,
		"cooldown_ticks": 12,
		"range_limit": 64.0,
	},
	{
		"id": "knife",
		"display_name": "Utility Knife",
		"slot": "melee",
		"category": "melee",
		"tags": ["melee", "light"],
		"damage": 24,
		"melee_damage": 24,
		"melee_reach": 48.0,
		"knockback": 8.0,
		"cooldown_ticks": 10,
		"range_limit": 48.0,
	},
	{
		"id": "pistol",
		"display_name": "Sidearm Echo",
		"slot": "firearm",
		"category": "firearm",
		"tags": ["firearm", "hitscan", "bullet"],
		"damage": 18,
		"knockback": 18.0,
		"cooldown_ticks": 20,
		"range_limit": 300.0,
		"ammo_capacity": 12,
		"magazine_size": 12,
		"starting_ammo": 12,
		"reserve_ammo": 24,
		"projectile_kind": "bullet",
		"projectile_speed": 24.0,
		"projectile_radius": 2.0,
		"projectile_lifetime_ticks": 30,
		"projectile": {
			"kind": "bullet",
			"speed": 24.0,
			"radius": 2.0,
			"lifetime_ticks": 30,
			"gravity_per_tick": 0.0,
			"pierces": 0,
			"explodes": false,
		},
	},
	{
		"id": "shotgun",
		"display_name": "Scatterline",
		"slot": "firearm",
		"category": "firearm",
		"tags": ["firearm", "pellet", "bullet"],
		"damage": 28,
		"knockback": 24.0,
		"cooldown_ticks": 12,
		"range_limit": 220.0,
		"ammo_capacity": 4,
		"magazine_size": 4,
		"starting_ammo": 4,
		"reserve_ammo": 12,
		"pellet_count": 6,
		"spread_degrees": 8.0,
		"projectile_kind": "bullet",
		"projectile_speed": 22.0,
		"projectile_radius": 2.5,
		"projectile_lifetime_ticks": 24,
		"projectile": {
			"kind": "bullet",
			"speed": 22.0,
			"radius": 2.5,
			"lifetime_ticks": 24,
			"gravity_per_tick": 0.0,
			"pierces": 0,
			"explodes": false,
			"pellet_count": 6,
			"spread_degrees": 8.0,
		},
	},
	{
		"id": "grenade",
		"display_name": "Arc Charge",
		"slot": "explosive",
		"category": "explosive",
		"tags": ["throwable", "explosive", "area"],
		"damage": 24,
		"knockback": 20.0,
		"cooldown_ticks": 30,
		"range_limit": 72.0,
		"ammo_capacity": 3,
		"starting_ammo": 3,
		"reserve_ammo": 0,
		"fuse_ticks": 30,
		"explosion_radius": 72.0,
		"explosion_damage": 24,
		"projectile_kind": "grenade",
		"projectile_speed": 8.0,
		"projectile_radius": 5.0,
		"projectile_lifetime_ticks": 30,
		"projectile_gravity_per_tick": 1.0,
		"projectile": {
			"kind": "grenade",
			"speed": 8.0,
			"radius": 5.0,
			"lifetime_ticks": 30,
			"gravity_per_tick": 1.0,
			"fuse_ticks": 30,
			"explodes": true,
			"explosion_radius": 72.0,
			"explosion_damage": 24,
		},
	},
	{
		"id": "rocket_launcher",
		"display_name": "Signal Rocket",
		"slot": "firearm",
		"category": "launcher",
		"tags": ["firearm", "rocket", "explosive"],
		"damage": 40,
		"knockback": 28.0,
		"cooldown_ticks": 24,
		"range_limit": 300.0,
		"ammo_capacity": 1,
		"magazine_size": 1,
		"starting_ammo": 1,
		"reserve_ammo": 4,
		"fuse_ticks": 0,
		"explosion_radius": 88.0,
		"explosion_damage": 40,
		"projectile_kind": "rocket",
		"projectile_speed": 12.0,
		"projectile_radius": 4.0,
		"projectile_lifetime_ticks": 90,
		"projectile": {
			"kind": "rocket",
			"speed": 12.0,
			"radius": 4.0,
			"lifetime_ticks": 90,
			"gravity_per_tick": 0.0,
			"pierces": 0,
			"explodes": true,
			"explosion_radius": 88.0,
			"explosion_damage": 40,
		},
	},
]

static var _cache: Dictionary = {}

static func _definitions() -> Dictionary:
	if not _cache.is_empty():
		return _cache
	for source: Dictionary in _RAW_DEFINITIONS:
		var definition := WeaponDefinition.new(source)
		_cache[definition.id] = definition
	return _cache

static func ids() -> Array[StringName]:
	var result: Array[StringName] = []
	for source: Dictionary in _RAW_DEFINITIONS:
		result.append(StringName(String(source["id"])))
	result.make_read_only()
	return result

static func all() -> Array[WeaponDefinition]:
	var result: Array[WeaponDefinition] = []
	for source: Dictionary in _RAW_DEFINITIONS:
		var definition: WeaponDefinition = definition_for(StringName(String(source["id"])))
		if definition != null:
			result.append(definition)
	result.make_read_only()
	return result

static func definition_for(weapon_id: StringName) -> WeaponDefinition:
	var definitions: Dictionary = _definitions()
	var value: Variant = definitions.get(weapon_id, null)
	if value is WeaponDefinition:
		return value
	return null

static func get_weapon(weapon_id: StringName) -> WeaponDefinition:
	return definition_for(weapon_id)

static func find(weapon_id: StringName) -> WeaponDefinition:
	return definition_for(weapon_id)

static func weapon(weapon_id: StringName) -> WeaponDefinition:
	return definition_for(weapon_id)

static func by_id(weapon_id: StringName) -> WeaponDefinition:
	return definition_for(weapon_id)

static func has_weapon(weapon_id: StringName) -> bool:
	return definition_for(weapon_id) != null

static func rows() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for definition: WeaponDefinition in all():
		result.append(definition.to_dictionary())
	result.make_read_only()
	return result

static func projectile_metadata(projectile_kind: StringName) -> Dictionary:
	for definition: WeaponDefinition in all():
		if definition.projectile_kind == projectile_kind:
			return definition.projectile_metadata()
	return {}

static func projectile_metadata_for_weapon(weapon_id: StringName) -> Dictionary:
	var definition: WeaponDefinition = definition_for(weapon_id)
	if definition == null:
		return {}
	return definition.projectile_metadata()

static func get_projectile_metadata(projectile_kind: StringName) -> Dictionary:
	return projectile_metadata(projectile_kind)

static func get_projectile_metadata_for_weapon(weapon_id: StringName) -> Dictionary:
	return projectile_metadata_for_weapon(weapon_id)

static func validate() -> bool:
	if not _raw_schema_valid():
		return false
	var seen: Dictionary = {}
	for definition: WeaponDefinition in all():
		if definition == null or definition.id == &"" or seen.has(definition.id):
			return false
		seen[definition.id] = true
		if definition.display_name.is_empty() or definition.slot == &"" or definition.category == &"":
			return false
		if definition.cooldown_ticks < 1 or definition.knockback < 0.0 or definition.range_limit <= 0.0:
			return false
		if definition.ammo_capacity < 0 or definition.magazine_size < 0 or definition.starting_ammo < 0 or definition.reserve_ammo < 0:
			return false
		if definition.is_melee():
			if definition.melee_reach <= 0.0 or definition.melee_damage <= 0 or definition.has_ammo() or definition.has_projectile():
				return false
		else:
			if definition.damage <= 0 or not definition.has_ammo() or not definition.has_projectile():
				return false
		if definition.has_projectile():
			if definition.projectile_speed <= 0.0 or definition.projectile_radius <= 0.0 or definition.projectile_lifetime_ticks <= 0:
				return false
			if StringName(String(definition.projectile.get("kind", ""))) != definition.projectile_kind:
				return false
		if definition.is_explosive() and (definition.explosion_radius <= 0.0 or definition.explosion_damage <= 0):
			return false
	return seen.size() == _RAW_DEFINITIONS.size()

static func fingerprint() -> String:
	var parts: Array[String] = []
	for definition: WeaponDefinition in all():
		# Serialize every authored field so a change to display identity, slot,
		# tags, cooldown, ammo, pellet/spread or explosive values changes the
		# source fingerprint used by evidence and replay manifests.
		parts.append(JSON.stringify(definition.to_dictionary()))
	return "weapon-catalog-v%d|%s" % [SCHEMA_VERSION, "|".join(parts)]

static func _raw_schema_valid() -> bool:
	var numeric_keys: Array[String] = [
		"damage", "melee_damage", "melee_reach", "knockback", "cooldown_ticks",
		"ammo_capacity", "magazine_size", "starting_ammo", "reserve_ammo",
		"projectile_speed", "projectile_radius", "projectile_lifetime_ticks",
		"projectile_gravity_per_tick", "pellet_count", "spread_degrees",
		"fuse_ticks", "explosion_radius", "explosion_damage",
	]
	for row: Dictionary in _RAW_DEFINITIONS:
		for key: String in ["id", "display_name", "slot", "category"]:
			if typeof(row.get(key, null)) != TYPE_STRING:
				return false
		if typeof(row.get("tags", null)) != TYPE_ARRAY or typeof(row.get("projectile", {})) != TYPE_DICTIONARY:
			return false
		for value: Variant in Array(row.get("tags", [])):
			if typeof(value) != TYPE_STRING:
				return false
		for key: String in numeric_keys:
			if row.has(key) and typeof(row[key]) != TYPE_INT and typeof(row[key]) != TYPE_FLOAT:
				return false
	return true
