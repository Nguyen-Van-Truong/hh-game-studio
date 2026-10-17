extends SceneTree
## Focused SA-05 catalog proof.  Values are implementation seeds, not parity.

const WeaponCatalogScript = preload("res://game/core/weapon_catalog.gd")
const MatchSessionScript = preload("res://game/core/match_session.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_expect(WeaponCatalogScript.validate(), "catalog rows satisfy the typed schema")
	var ids: Array[StringName] = WeaponCatalogScript.ids()
	_expect(ids.has(&"pistol"), "catalog includes pistol")
	_expect(ids.has(&"shotgun"), "catalog includes shotgun")
	_expect(ids.has(&"grenade"), "catalog includes grenade")
	_expect(ids.has(&"fists") and ids.has(&"pipe") and ids.has(&"knife"), "catalog includes melee variants")
	_expect(ids.has(&"rocket_launcher"), "catalog includes a rocket definition")

	var pistol := WeaponCatalogScript.get_weapon(&"pistol")
	_expect(pistol != null and pistol.ammo_capacity == 12 and pistol.magazine_size == 12, "pistol carries a twelve-round magazine")
	_expect(pistol != null and pistol.damage == 18 and is_equal_approx(pistol.knockback, 18.0), "pistol damage and knockback are authored")
	_expect(pistol != null and pistol.is_bullet() and pistol.projectile_kind == &"bullet" and pistol.projectile.get("kind") == "bullet", "pistol carries bullet metadata")
	_expect(pistol != null and float(pistol.projectile.get("speed", 0.0)) > 0.0 and int(pistol.projectile.get("lifetime_ticks", 0)) > 0, "bullet metadata has speed and lifetime")

	var shotgun := WeaponCatalogScript.get_weapon(&"shotgun")
	_expect(shotgun != null and shotgun.ammo_capacity == 4 and shotgun.pellet_count == 6, "shotgun carries four shells and six pellets")
	_expect(shotgun != null and shotgun.damage == 28 and is_equal_approx(shotgun.knockback, 24.0), "shotgun damage and knockback are distinct")
	_expect(shotgun != null and float(shotgun.spread_degrees) > 0.0 and shotgun.projectile_kind == &"bullet", "shotgun exposes spread and bullet metadata")

	var grenade := WeaponCatalogScript.get_weapon(&"grenade")
	_expect(grenade != null and grenade.starting_ammo == 3 and grenade.fuse_ticks == 30, "grenade carries three charges and a fuse")
	_expect(grenade != null and grenade.explosion_damage == 24 and is_equal_approx(grenade.explosion_radius, 72.0), "grenade exposes area damage metadata")
	_expect(grenade != null and grenade.projectile_kind == &"grenade" and float(grenade.projectile.get("gravity_per_tick", 0.0)) > 0.0, "grenade exposes arc metadata")

	var fists := WeaponCatalogScript.get_weapon(&"fists")
	var pipe := WeaponCatalogScript.get_weapon(&"pipe")
	_expect(fists != null and fists.is_melee() and fists.melee_reach == 56.0 and fists.melee_damage == 12, "fists expose melee reach and damage")
	_expect(pipe != null and pipe.is_melee() and pipe.melee_reach > fists.melee_reach and pipe.melee_damage > fists.melee_damage, "melee variants have distinct reach and damage")

	var rocket := WeaponCatalogScript.get_weapon(&"rocket_launcher")
	_expect(rocket != null and rocket.is_rocket() and rocket.projectile_kind == &"rocket" and rocket.projectile.get("kind") == "rocket", "rocket definition carries rocket metadata")
	_expect(rocket != null and rocket.is_explosive() and rocket.explosion_radius > grenade.explosion_radius, "rocket exposes a larger blast than grenade")
	_expect(WeaponCatalogScript.projectile_metadata(&"bullet").get("kind") == "bullet", "bullet metadata lookup is data-driven")
	_expect(WeaponCatalogScript.get_projectile_metadata(&"rocket").get("explodes", false), "rocket metadata lookup reports explosion")
	_expect(WeaponCatalogScript.projectile_metadata_for_weapon(&"shotgun").get("pellet_count", 0) == 6, "weapon-specific projectile metadata preserves shotgun pellets")

	var row: Dictionary = pistol.to_dictionary()
	_expect(row.is_read_only(), "definition snapshot is read-only")
	var projectile: Dictionary = WeaponCatalogScript.projectile_metadata(&"bullet")
	projectile["speed"] = -1.0
	_expect(float(WeaponCatalogScript.projectile_metadata(&"bullet").get("speed", 0.0)) > 0.0, "projectile metadata lookup returns defensive copies")
	var fingerprint: String = WeaponCatalogScript.fingerprint()
	_expect(fingerprint == WeaponCatalogScript.fingerprint(), "catalog fingerprint is deterministic")
	pistol.display_name = "Mutated test label"
	_expect(fingerprint != WeaponCatalogScript.fingerprint(), "catalog fingerprint changes when authored identity changes")
	pistol.display_name = "Sidearm Echo"
	await _test_live_match_authority(pistol, shotgun, grenade, fists)

	if failures == 0:
		print("SA-05 weapon catalog PASS: %d assertions; pistol/shotgun/grenade/melee/bullet/rocket" % assertions)
	else:
		printerr("SA-05 weapon catalog FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)

func _test_live_match_authority(pistol: WeaponCatalog.WeaponDefinition, shotgun: WeaponCatalog.WeaponDefinition, grenade: WeaponCatalog.WeaponDefinition, fists: WeaponCatalog.WeaponDefinition) -> void:
	var session: MatchSession = MatchSessionScript.new(701, &"two_player")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	var snapshot: Dictionary = session.snapshot()
	_expect(String(snapshot.get(&"weapon_catalog_fingerprint", "")) == WeaponCatalogScript.fingerprint(), "live match snapshot carries the catalog fingerprint")
	session.place_fighter(0, Vector2(940.0, session.world.floor_y))
	session.place_fighter(1, Vector2(1110.0, session.world.floor_y))
	session.gun_ids[0] = &"pistol"
	session.fighters[0].ammo = pistol.starting_ammo
	session.fighters[0].queued_attack = &"shoot"
	session.fighters[0].aim_angle = 0.0
	session.fighters[0].facing = 1
	session.fighters[1].health = 100
	session._resolve_attacks()
	_expect(session.fighters[1].health == 100 - pistol.damage, "live pistol hit uses catalog damage")
	session.place_fighter(1, Vector2(1110.0, session.world.floor_y))
	session.gun_ids[0] = &"shotgun"
	session.fighters[0].ammo = shotgun.starting_ammo
	session.fighters[0].queued_attack = &"shoot"
	session.fighters[1].health = 100
	session._resolve_attacks()
	_expect(session.fighters[1].health == 100 - shotgun.damage, "live shotgun hit uses catalog damage")
	session.place_fighter(1, Vector2(1000.0, session.world.floor_y))
	session.fighters[0].queued_attack = &"throw"
	session.fighters[0].facing = 1
	session._resolve_attacks()
	_expect(session.grenades.size() == 1, "live grenade attack creates a catalog-backed fuse row")
	if session.grenades.size() == 1:
		var row: Dictionary = session.grenades[0]
		_expect(int(row.get(&"fuse", 0)) == grenade.fuse_ticks and int(row.get(&"damage", 0)) == grenade.explosion_damage, "grenade row uses catalog fuse and damage")
		_expect(is_equal_approx(float(row.get(&"radius", 0.0)), grenade.explosion_radius), "grenade row uses catalog radius")
	session.gun_ids[0] = &"unknown_weapon"
	session.fighters[0].queued_attack = &"shoot"
	session.fighters[1].health = 100
	var prior_shots: int = session.shot_events.size()
	session._resolve_attacks()
	_expect(session.fighters[1].health == 100 and session.shot_events.size() == prior_shots, "unknown gun fails closed without a hit or shot event")
	session.gun_ids[0] = &"fists"
	session.fighters[0].queued_attack = &"punch"
	session.place_fighter(1, Vector2(980.0, session.world.floor_y))
	session.fighters[1].health = 100
	session._resolve_attacks()
	_expect(session.fighters[1].health == 100 - fists.melee_damage, "live melee hit uses catalog damage")
	session.queue_free()
	await process_frame
