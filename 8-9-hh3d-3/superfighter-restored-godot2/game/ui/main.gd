class_name VaultGame
extends Node2D

const FighterScript = preload("res://game/fighter/fighter.gd")
const ArenaScript = preload("res://game/world/arena.gd")
const ProjectileScript = preload("res://game/combat/projectile.gd")

enum Phase { MENU, MATCH, RESULT }

var phase: Phase = Phase.MENU
var paused: bool = false
var round_over: bool = false
var winner_id: int = 0
var arena: VaultArena
var fighters: Array[VaultFighter] = []
var projectiles: Array[VaultProjectile] = []
var world_layer: Node2D
var actor_layer: Node2D
var projectile_layer: Node2D
var ui_layer: CanvasLayer
var title_label: Label
var info_label: Label
var hud_label: Label
var prompt_label: Label
var phase_ticks: int = 0

func _ready() -> void:
	_build_ui()
	_show_menu()

func _physics_process(_delta: float) -> void:
	phase_ticks += 1
	if phase != Phase.MATCH or paused or round_over:
		return
	for fighter: VaultFighter in fighters:
		if not is_instance_valid(fighter):
			continue
		var item_kind: StringName = arena.collect_at(fighter.position + Vector2(0.0, -28.0))
		if item_kind != &"none":
			_apply_pickup(fighter, item_kind)
		if arena.fire_at(fighter.position + Vector2(0.0, -12.0)) and fighter.roll_timer > 0.0:
			fighter.burning = 0.0
	_update_ui()

func _unhandled_input(event: InputEvent) -> void:
	if event is not InputEventKey:
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return
	if key_event.keycode == KEY_ENTER or key_event.keycode == KEY_KP_ENTER:
		if phase == Phase.MENU or phase == Phase.RESULT:
			_start_match()
	elif key_event.keycode == KEY_P and phase == Phase.MATCH and not round_over:
		paused = not paused
		_update_ui()
	elif key_event.keycode == KEY_R and phase == Phase.RESULT:
		_start_match()
	elif key_event.keycode == KEY_ESCAPE:
		if phase == Phase.MATCH or phase == Phase.RESULT:
			_show_menu()

func _build_ui() -> void:
	ui_layer = CanvasLayer.new()
	add_child(ui_layer)
	title_label = Label.new()
	title_label.position = Vector2(46.0, 30.0)
	title_label.add_theme_font_size_override("font_size", 42)
	title_label.add_theme_color_override("font_color", Color("d9f0ff"))
	ui_layer.add_child(title_label)
	info_label = Label.new()
	info_label.position = Vector2(50.0, 102.0)
	info_label.add_theme_font_size_override("font_size", 19)
	info_label.add_theme_color_override("font_color", Color("b8cce0"))
	ui_layer.add_child(info_label)
	hud_label = Label.new()
	hud_label.position = Vector2(46.0, 20.0)
	hud_label.add_theme_font_size_override("font_size", 18)
	hud_label.add_theme_color_override("font_color", Color("e5f2ff"))
	hud_label.visible = false
	ui_layer.add_child(hud_label)
	prompt_label = Label.new()
	prompt_label.position = Vector2(50.0, 610.0)
	prompt_label.add_theme_font_size_override("font_size", 21)
	prompt_label.add_theme_color_override("font_color", Color("f1d16c"))
	ui_layer.add_child(prompt_label)

func _show_menu() -> void:
	phase = Phase.MENU
	paused = false
	round_over = false
	winner_id = 0
	_clear_match()
	title_label.visible = true
	info_label.visible = true
	hud_label.visible = false
	prompt_label.visible = true
	title_label.text = "VAULT FIGHTERS"
	info_label.text = "Two-player arena restore lab\n\nP1  WASD move / J punch / K fire / L grenade / ; power\nP2  Arrows move / Num1 punch / Num2 fire / Num3 grenade / Num4 power\n\nEnter  Start match\nEsc    Return to menu"
	prompt_label.text = "FUNCTIONAL RESTORE BUILD  •  Enter to begin"
	queue_redraw()

func _start_match() -> void:
	_clear_match()
	phase = Phase.MATCH
	paused = false
	round_over = false
	winner_id = 0
	world_layer = Node2D.new()
	world_layer.name = &"World"
	add_child(world_layer)
	arena = ArenaScript.new()
	world_layer.add_child(arena)
	arena.build()
	projectile_layer = Node2D.new()
	projectile_layer.name = &"Projectiles"
	world_layer.add_child(projectile_layer)
	actor_layer = Node2D.new()
	actor_layer.name = &"Fighters"
	world_layer.add_child(actor_layer)
	var p1_controls := {"left": KEY_A, "right": KEY_D, "up": KEY_W, "down": KEY_S, "jump": KEY_W, "punch": KEY_J, "shoot": KEY_K, "throw": KEY_L, "power": KEY_SEMICOLON}
	var p2_controls := {"left": KEY_LEFT, "right": KEY_RIGHT, "up": KEY_UP, "down": KEY_DOWN, "jump": KEY_UP, "punch": KEY_KP_1, "shoot": KEY_KP_2, "throw": KEY_KP_3, "power": KEY_KP_4}
	_spawn_fighter(1, Vector2(250.0, 640.0), Color("5bc0eb"), p1_controls)
	_spawn_fighter(2, Vector2(1030.0, 640.0), Color("e56d7a"), p2_controls)
	title_label.visible = false
	info_label.visible = false
	hud_label.visible = true
	prompt_label.visible = true
	prompt_label.text = "P pause   R restart after result   Esc menu"
	_update_ui()

func _spawn_fighter(id: int, start: Vector2, color: Color, controls: Dictionary) -> void:
	var fighter: VaultFighter = FighterScript.new()
	fighter.configure(id, start, color, controls, self)
	actor_layer.add_child(fighter)
	fighters.append(fighter)

func _clear_match() -> void:
	fighters.clear()
	projectiles.clear()
	if is_instance_valid(world_layer):
		world_layer.queue_free()
	world_layer = null
	arena = null
	actor_layer = null
	projectile_layer = null

func is_match_paused() -> bool:
	return paused or round_over or phase != Phase.MATCH

func resolve_punch(attacker: VaultFighter) -> void:
	if attacker.attack_cooldown > 0.0 or round_over:
		return
	attacker.attack_cooldown = 0.24
	for target: VaultFighter in fighters:
		if target == attacker or target.health <= 0:
			continue
		var delta := target.position - attacker.position
		if absf(delta.x) <= 68.0 and absf(delta.y) <= 52.0 and signf(delta.x) == float(attacker.facing):
			target.take_damage(13, Vector2(float(attacker.facing) * 190.0, -100.0), attacker.player_id)
			return

func spawn_bullet(owner: VaultFighter, direction: Vector2) -> void:
	if owner.ammo <= 0 or owner.attack_cooldown > 0.0 or round_over:
		return
	owner.ammo -= 1
	owner.attack_cooldown = 0.16
	var projectile: VaultProjectile = ProjectileScript.new()
	projectile_layer.add_child(projectile)
	projectile.configure(self, owner.player_id, &"bullet", owner.position + Vector2(float(owner.facing) * 28.0, -38.0), direction * 760.0, 18)
	projectiles.append(projectile)

func spawn_grenade(owner: VaultFighter, direction: Vector2) -> void:
	if owner.grenades <= 0 or owner.attack_cooldown > 0.0 or round_over:
		return
	owner.grenades -= 1
	owner.attack_cooldown = 0.30
	var projectile: VaultProjectile = ProjectileScript.new()
	projectile_layer.add_child(projectile)
	projectile.configure(self, owner.player_id, &"grenade", owner.position + Vector2(float(owner.facing) * 24.0, -36.0), direction * 470.0 + Vector2(0.0, -170.0), 28)
	projectiles.append(projectile)

func power_blast(owner: VaultFighter) -> void:
	if owner.power <= 0 or owner.attack_cooldown > 0.0 or round_over:
		return
	owner.power -= 1
	owner.attack_cooldown = 0.55
	for target: VaultFighter in fighters:
		if target == owner or target.health <= 0:
			continue
		if target.position.distance_to(owner.position) <= 190.0:
			target.take_damage(24, Vector2(float(owner.facing) * 260.0, -160.0), owner.player_id)

func resolve_projectile(projectile: VaultProjectile) -> bool:
	if projectile.kind == &"grenade" and arena.fire_at(projectile.position):
		_explode(projectile.position, projectile.damage, projectile.owner_id)
		return true
	for fighter: VaultFighter in fighters:
		if fighter.player_id == projectile.owner_id or fighter.health <= 0:
			continue
		if fighter.position.distance_to(projectile.position + Vector2(0.0, 20.0)) <= 34.0:
			fighter.take_damage(projectile.damage, Vector2(signf(projectile.velocity.x) * 240.0, -80.0), projectile.owner_id)
			if projectile.kind == &"grenade":
				_explode(projectile.position, 12, projectile.owner_id)
			return true
	if projectile.position.y >= 640.0:
		if projectile.kind == &"grenade":
			_explode(projectile.position, 12, projectile.owner_id)
		return true
	return false

func _explode(at: Vector2, damage: int, source_id: int) -> void:
	for fighter: VaultFighter in fighters:
		if fighter.player_id == source_id or fighter.health <= 0:
			continue
		var distance := fighter.position.distance_to(at)
		if distance <= 120.0:
			var scale := 1.0 - distance / 160.0
			fighter.take_damage(maxi(4, int(float(damage) * scale)), (fighter.position - at).normalized() * 180.0 + Vector2.UP * 100.0, source_id)

func _apply_pickup(fighter: VaultFighter, kind: StringName) -> void:
	if kind == &"ammo": fighter.give_ammo(8)
	elif kind == &"health": fighter.heal(28)
	elif kind == &"grenade": fighter.give_grenade(2)
	elif kind == &"power": fighter.give_power(1)

func fighter_fell(fighter: VaultFighter) -> void:
	if not round_over:
		fighter_fighter_defeated(fighter, 0)

func fighter_defeated(fighter: VaultFighter, source_id: int) -> void:
	fighter_fighter_defeated(fighter, source_id)

func fighter_fighter_defeated(fighter: VaultFighter, _source_id: int) -> void:
	if round_over:
		return
	round_over = true
	winner_id = 2 if fighter.player_id == 1 else 1
	phase = Phase.RESULT
	paused = false
	_update_ui()

func snapshot() -> Dictionary:
	var fighter_rows: Array[Dictionary] = []
	for fighter: VaultFighter in fighters:
		fighter_rows.append(fighter.snapshot())
	return {"phase": int(phase), "paused": paused, "round_over": round_over, "winner": winner_id, "tick": phase_ticks, "fighters": fighter_rows}

func snapshot_hash() -> int:
	return hash(JSON.stringify(snapshot()))

func _update_ui() -> void:
	if not is_instance_valid(hud_label):
		return
	if phase == Phase.MATCH:
		var p1 := fighters[0] if fighters.size() > 0 else null
		var p2 := fighters[1] if fighters.size() > 1 else null
		var pause_text := "  || PAUSED" if paused else ""
		hud_label.text = "P1  HP %3d  AMMO %2d  G %d  P %d      |      P2  HP %3d  AMMO %2d  G %d  P %d%s" % [p1.health if p1 else 0, p1.ammo if p1 else 0, p1.grenades if p1 else 0, p1.power if p1 else 0, p2.health if p2 else 0, p2.ammo if p2 else 0, p2.grenades if p2 else 0, p2.power if p2 else 0, pause_text]
		if paused:
			prompt_label.text = "PAUSED  •  press P to resume  •  Esc menu"
		elif not round_over:
			prompt_label.text = "P pause   P1 WASD/J/K/L/;   P2 arrows/Num1-4   Esc menu"
	elif phase == Phase.RESULT:
		title_label.visible = true
		info_label.visible = true
		hud_label.visible = false
		prompt_label.visible = true
		title_label.text = "PLAYER %d WINS" % winner_id
		info_label.text = "Round complete\nSnapshot hash: %d\n\nEnter or R  rematch\nEsc             menu" % snapshot_hash()
		prompt_label.text = "REMATCH READY"
