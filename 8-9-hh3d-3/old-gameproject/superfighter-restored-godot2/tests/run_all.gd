extends SceneTree

const GameScript = preload("res://game/ui/main.gd")

var failures: int = 0
var assertions: int = 0
var game: VaultGame

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	game = GameScript.new()
	root.add_child(game)
	await process_frame
	_expect(game.phase == VaultGame.Phase.MENU, "boot opens menu")
	game._start_match()
	await physics_frame
	await physics_frame
	_expect(game.phase == VaultGame.Phase.MATCH, "start enters match")
	_expect(game.fighters.size() == 2, "match has two fighters")
	_expect(game.arena.platform_rects.size() >= 5, "arena has authored platforms")
	_expect(game.arena.ladder_rects.size() == 1, "arena has ladder")
	_expect(game.arena.fire_rects.size() == 1, "arena has fire hazard")

	var p1: VaultFighter = game.fighters[0]
	var p2: VaultFighter = game.fighters[1]
	p1.position = Vector2(450.0, 620.0)
	p2.position = Vector2(500.0, 620.0)
	var health_before: int = p2.health
	game.resolve_punch(p1)
	_expect(p2.health < health_before, "punch applies damage")

	p1.attack_cooldown = 0.0
	var ammo_before: int = p1.ammo
	game.spawn_bullet(p1, Vector2.RIGHT)
	_expect(p1.ammo == ammo_before - 1, "shoot consumes ammo")
	_expect(game.projectiles.size() == 1, "shoot creates projectile")

	p1.attack_cooldown = 0.0
	var grenade_before: int = p1.grenades
	game.spawn_grenade(p1, Vector2.RIGHT)
	_expect(p1.grenades == grenade_before - 1, "throw consumes grenade")

	p1.position = Vector2(170.0, 470.0)
	var pickup_before: int = p1.ammo
	game._physics_process(1.0 / 60.0)
	_expect(p1.ammo > pickup_before, "pickup changes inventory")

	var hash_before: int = game.snapshot_hash()
	game.paused = true
	var paused_position: Vector2 = p1.position
	await physics_frame
	_expect(p1.position == paused_position, "pause freezes fighter position")
	game.paused = false
	_expect(hash_before != 0, "snapshot hash exists")

	game.fighter_fell(p1)
	_expect(game.phase == VaultGame.Phase.RESULT, "pit/fall enters result")
	_expect(game.winner_id == 2, "fall awards opponent win")
	game._show_menu()
	_expect(game.phase == VaultGame.Phase.MENU, "escape/menu lifecycle returns to menu")
	if failures == 0:
		print("RR_GAMEPLAY_TEST PASS assertions=%d" % assertions)
	else:
		printerr("RR_GAMEPLAY_TEST FAIL failures=%d assertions=%d" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)
