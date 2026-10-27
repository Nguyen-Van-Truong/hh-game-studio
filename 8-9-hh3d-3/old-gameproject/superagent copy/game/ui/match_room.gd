class_name MatchRoom
extends Node2D
## Presentation shell for a Classic match.
##
## MatchSession owns all gameplay state and physics.  This node only samples
## input, advances one fixed step, and presents the immutable snapshot.

const FIXED_STEP: float = 1.0 / 60.0
const MATCH_SESSION_SCRIPT = preload("res://game/core/match_session.gd")
const BUFFER_SCRIPT = preload("res://game/core/input_buffer.gd")
const BOT_INPUT_SCRIPT = preload("res://game/core/bot_input.gd")
const BOT_SCRIPT = preload("res://game/ai/classic_bot.gd")
const WEAPON_VISUALS = preload("res://game/presentation/weapon_visuals.gd")
const PROP_VISUALS = preload("res://game/presentation/prop_visuals.gd")
const ARENA_SKIN = preload("res://game/presentation/arena_skin.gd")
const SF_BANK = preload("res://game/presentation/sf_classic_bank.gd")
const RELAY_YARD_BACKDROP: Texture2D = preload("res://art/backgrounds/relay_hall_v2.png")

signal fixed_step_completed(frame: InputFrame)

@export var opponent: StringName = &"two_player"
@export var seed: int = 1
@export var mode: StringName = &"vs"
@export var rule: StringName = &"infinite"
@export var map_id: StringName = &"relay_yard"
@export var bot_difficulty: StringName = &"normal"

var simulation: MatchSession
var input_buffer: InputBuffer
var bot_input: BotInput
var bot: ClassicBot
var _last_frame: InputFrame
var _snapshot: Dictionary = {}
var _world_snapshot: Dictionary = {}
var _camera: Camera2D
var _camera_near: bool = false
var _paused: bool = false
var _result_seen: bool = false
var _last_phase: StringName = &"playing"
var _world_size: Vector2 = Vector2(1600.0, 900.0)
var _camera_shake: float = 0.0
var _camera_phase: float = 0.0

@onready var _p1: FighterView = get_node_or_null("Fighter1") as FighterView
@onready var _p2: FighterView = get_node_or_null("Fighter2") as FighterView
@onready var _header: Label = get_node_or_null("CanvasLayer/Header") as Label
@onready var _p1_panel: Label = get_node_or_null("CanvasLayer/P1Panel") as Label
@onready var _p2_panel: Label = get_node_or_null("CanvasLayer/P2Panel") as Label
@onready var _status: Label = get_node_or_null("CanvasLayer/Status") as Label
@onready var _controls: Label = get_node_or_null("CanvasLayer/Controls") as Label
@onready var _overlay: Label = get_node_or_null("CanvasLayer/Overlay") as Label
@onready var _overlay_backdrop: ColorRect = get_node_or_null("CanvasLayer/OverlayBackdrop") as ColorRect
@onready var _footer: Label = get_node_or_null("CanvasLayer/Footer") as Label
@onready var _hud_bars: Node2D = get_node_or_null("CanvasLayer/HudBars") as Node2D
@onready var _arena_fx: Node2D = get_node_or_null("ArenaFx") as Node2D
@onready var _combat_audio: Node = get_node_or_null("CombatAudio") as Node

func _ready() -> void:
	set_process_input(true)
	# The two-player launcher opts into the classic Rooftops topology.  Tests
	# and callers that set superagent_map_id continue to select an explicit map.
	if OS.get_cmdline_args().has("--classic-rooftops") and not get_tree().has_meta(&"superagent_map_id"):
		map_id = &"classic_rooftops"
	var selected_map: Variant = get_tree().get_meta(&"superagent_map_id", map_id)
	if typeof(selected_map) == TYPE_STRING or typeof(selected_map) == TYPE_STRING_NAME:
		map_id = StringName(selected_map)
	input_buffer = BUFFER_SCRIPT.new()
	bot_input = BOT_INPUT_SCRIPT.new()
	bot = BOT_SCRIPT.new(bot_difficulty)
	_create_session()
	_camera = Camera2D.new()
	_camera.name = &"MatchCamera"
	_camera.position = _world_size * 0.5
	_camera.position_smoothing_enabled = false
	add_child(_camera)
	var requested_camera: Variant = get_tree().get_meta(&"superagent_camera_view", &"full")
	if typeof(requested_camera) == TYPE_STRING or typeof(requested_camera) == TYPE_STRING_NAME:
		_camera_near = StringName(requested_camera) == &"near"
	if _header != null:
		_header.text = "SUPERAGENT  •  CLASSIC ARENA"
	if _controls != null:
		_controls.text = _controls_text()
	if _footer != null:
		_footer.text = "Original procedural FX/SFX • prototype tuning in progress"
	if _arena_fx != null and _combat_audio != null:
		_arena_fx.connect("sound_requested", Callable(_combat_audio, "play_event"))
	if _arena_fx != null:
		_arena_fx.connect("camera_impulse", Callable(self, "_on_camera_impulse"))
	_update_presentation()

func _create_session() -> void:
	if simulation != null and is_instance_valid(simulation):
		if simulation.get_parent() == self:
			remove_child(simulation)
		simulation.free()
	simulation = MATCH_SESSION_SCRIPT.new(maxi(1, seed), opponent, mode, rule, map_id)
	add_child(simulation)
	input_buffer = BUFFER_SCRIPT.new()
	bot_input = BOT_INPUT_SCRIPT.new()
	bot = BOT_SCRIPT.new(bot_difficulty)
	_paused = false
	_result_seen = false
	_last_phase = &"playing"
	_last_frame = null
	_camera_shake = 0.0
	_camera_phase = 0.0
	_configure_fighters()

func _configure_fighters() -> void:
	if simulation == null:
		return
	var width: float = float(simulation.tuning.get(&"char_width", 28.0))
	var height: float = float(simulation.tuning.get(&"char_height", 48.0))
	var stamina: int = int(simulation.tuning.get(&"max_stamina", 600))
	if _p1 != null:
		_p1.configure(1, width, height, stamina)
	if _p2 != null:
		_p2.configure(2, width, height, stamina)

func _controls_text() -> String:
	var p2_line: String = "P2  Arrow keys move   Up / Down aim while NumPad 2 is held   NumPad 1 punch   NumPad 2 hold aim / release fire   NumPad 3 grenade   NumPad 4 power   NumPad 5 cycle slots"
	if opponent == &"bot":
		p2_line = "P2  deterministic classic bot   •   P1 controls the live fighter"
	return "P1  A / D move   W jump / S crouch or pickup; W / S aim while K is held   J punch/combo; Down + J kick   K hold aim / release fire   L grenade   ; power   Q cycle slots\n%s\nDouble-tap direction to sprint, then press Down to tackle/grab.  Hold Down + Punch near a pickup.  •  F6 camera detail   •  Esc pause" % p2_line

func _reset_input_session() -> void:
	if input_buffer != null:
		input_buffer.cancel_all()
	input_buffer = BUFFER_SCRIPT.new()

func _input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo:
			if _last_phase == &"round_result":
				if key_event.keycode == KEY_ENTER or key_event.keycode == KEY_R:
					if simulation.continue_round():
						bot_input.reset()
						bot = BOT_SCRIPT.new(bot_difficulty)
						_reset_input_session()
						_update_presentation()
					return
				if key_event.keycode == KEY_ESCAPE:
					_reset_input_session()
					get_tree().change_scene_to_file("res://main.tscn")
				return
			elif _last_phase == &"result":
				if key_event.keycode == KEY_ENTER or key_event.keycode == KEY_R:
					_create_session()
					_update_presentation()
					return
				if key_event.keycode == KEY_ESCAPE:
					_reset_input_session()
					get_tree().change_scene_to_file("res://main.tscn")
					return
			elif _last_phase == &"invalid":
				if key_event.keycode == KEY_ESCAPE:
					_reset_input_session()
					get_tree().change_scene_to_file("res://main.tscn")
				return
			elif key_event.keycode == KEY_ESCAPE:
				var desired_pause: bool = not _paused
				if simulation.set_paused(desired_pause):
					_paused = desired_pause
					_reset_input_session()
					_update_presentation()
				return
			elif key_event.keycode == KEY_F6:
				_camera_near = not _camera_near
				_update_camera()
				return
			elif _paused:
				if key_event.keycode == KEY_ENTER:
					if simulation.set_paused(false):
						_paused = false
						_reset_input_session()
						_update_presentation()
					return
				if key_event.keycode == KEY_BACKSPACE:
					_reset_input_session()
					get_tree().change_scene_to_file("res://main.tscn")
					return
	if _paused or _last_phase != &"playing":
		return
	input_buffer.accept_event(event)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and input_buffer != null:
		_reset_input_session()

func _physics_process(_delta: float) -> void:
	if simulation == null or _paused or _last_phase != &"playing":
		return
	var human_frame: InputFrame = input_buffer.build_frame(simulation.tick)
	var frame: InputFrame = human_frame
	if opponent != &"two_player":
		var desired: Dictionary = bot.desired_actions(simulation.snapshot(), 2)
		frame = bot_input.merge_player(human_frame, desired, 2)
	if frame == null or not simulation.step(frame):
		push_error("Match room rejected its fixed-step input frame")
		return
	_last_frame = frame
	_update_presentation()
	fixed_step_completed.emit(frame)

func _process(delta: float) -> void:
	_camera_phase += delta * 42.0
	_camera_shake = move_toward(_camera_shake, 0.0, delta * 28.0)
	_update_camera()

func _on_camera_impulse(strength: float) -> void:
	_camera_shake = minf(12.0, maxf(_camera_shake, clampf(strength, 0.0, 12.0)))

func read_snapshot() -> Dictionary:
	return _snapshot

func read_last_frame() -> InputFrame:
	return _last_frame

func _update_presentation() -> void:
	if simulation == null:
		return
	_snapshot = simulation.snapshot()
	_world_snapshot = _snapshot.get(&"world", {})
	_world_size = Vector2(float(_world_snapshot.get(&"width", 1600.0)), float(_world_snapshot.get(&"height", 900.0)))
	var fighters: Array = _snapshot.get(&"fighters", [])
	_last_phase = StringName(_snapshot.get(&"phase", &"playing"))
	if fighters.size() >= 2:
		if _p1 != null:
			_p1.apply_state(fighters[0], int(_snapshot.get(&"tick", 0)))
		if _p2 != null:
			_p2.apply_state(fighters[1], int(_snapshot.get(&"tick", 0)))
		_update_hud(fighters)
	if _hud_bars != null:
		_hud_bars.call("consume_snapshot", _snapshot)
	if _last_phase == &"result":
		_result_seen = true
	_update_overlay()
	_update_camera()
	if _arena_fx != null:
		_arena_fx.call("consume_snapshot", _snapshot)
	queue_redraw()

func _update_hud(fighters: Array) -> void:
	if _p1_panel != null:
		_p1_panel.text = _fighter_hud("P1  BLUE", fighters[0], Color("#72d5ff"))
	if _p2_panel != null:
		var title: String = "P2  ORANGE"
		if opponent != &"two_player":
			title = "P2  CLASSIC BOT"
		_p2_panel.text = _fighter_hud(title, fighters[1], Color("#ffc064"))
	if _status != null:
		var tick: int = int(_snapshot.get(&"tick", 0))
		var mode_snapshot_value: Variant = _snapshot.get(&"mode_rules", {})
		var mode_snapshot: Dictionary = mode_snapshot_value if mode_snapshot_value is Dictionary else {}
		var mode_name: String = String(mode_snapshot.get(&"mode", &"vs")).to_upper()
		var round_number: int = int(mode_snapshot.get(&"round_index", 0)) + 1
		var progress: String = ""
		if mode_name == "VS":
			var score_value: Variant = mode_snapshot.get(&"score", [0, 0])
			var score_array: Array = score_value if score_value is Array else [0, 0]
			progress = "SCORE %d-%d" % [int(score_array[0]), int(score_array[1])] if score_array.size() >= 2 else "SCORE 0-0"
		elif mode_name == "STAGE":
			progress = "STAGE %02d/12" % (int(mode_snapshot.get(&"stage_index", 0)) + 1)
		elif mode_name == "SURVIVAL":
			progress = "WAVE %02d" % int(mode_snapshot.get(&"survival_wave", 0))
		_status.text = "%s   •   ROUND %02d   •   %s   •   %s   •   TICK %06d" % [mode_name, round_number, progress, String(_last_phase).to_upper(), tick]

func _fighter_hud(title: String, fighter: Dictionary, tint: Color) -> String:
	var health: int = int(fighter.get(&"health", 0))
	var ammo: int = int(fighter.get(&"ammo", 0))
	var grenades: int = int(fighter.get(&"grenades", 0))
	var power_charges: int = int(fighter.get(&"power_charges", 0))
	var gun: String = String(fighter.get(&"gun_id", &"sidearm"))
	var melee: String = String(fighter.get(&"melee_id", &"fists"))
	var active_slot: int = int(fighter.get(&"active_slot", 1)) + 1
	var active_weapon: String = String(fighter.get(&"active_weapon_id", gun))
	var sprint_value: int = 0
	var sprint_value_variant: Variant = fighter.get(&"sprint", {})
	if typeof(sprint_value_variant) == TYPE_DICTIONARY:
		sprint_value = int(Dictionary(sprint_value_variant).get(&"stamina", 0))
	var aiming: bool = bool(fighter.get(&"aiming", false))
	var bullet_time_active: bool = bool(fighter.get(&"bullet_time_active", false))
	var burning: bool = int(fighter.get(&"burning_ticks", 0)) > 0
	var state_suffix: String = ""
	if burning:
		state_suffix = "  •  BURN"
	elif bullet_time_active:
		state_suffix = "  •  SLOW"
	elif aiming:
		state_suffix = "  •  AIM"
	return "%s\nHP %03d   ST %03d\nSLOT %d %s  •  AM %02d   G %d   P %d\nM:%s  G:%s%s" % [
		title, health, sprint_value, active_slot, active_weapon.to_upper(), ammo, grenades, power_charges, melee.to_upper(), gun.to_upper(),
		state_suffix]

func _update_overlay() -> void:
	if _overlay == null:
		return
	if _last_phase == &"invalid":
		_overlay.text = "MATCH INVALID\n\nThe authored map could not be loaded.\nESC  main menu"
		_overlay.visible = true
		if _overlay_backdrop != null:
			_overlay_backdrop.visible = true
	elif _last_phase == &"round_result":
		var round_winner: int = int(_snapshot.get(&"winner", 0))
		var round_text: String = "ROUND DRAW"
		if round_winner == 1:
			round_text = "P1 ROUND WIN"
		elif round_winner == 2:
			round_text = "P2 ROUND WIN"
		_overlay.text = "%s\n\nENTER  next round\nR  next round\nESC  main menu" % round_text
		_overlay.visible = true
		if _overlay_backdrop != null:
			_overlay_backdrop.visible = true
	elif _last_phase == &"result":
		var winner: int = int(_snapshot.get(&"winner", 0))
		var result_text: String = "DRAW"
		if winner == 1:
			result_text = "P1 WINS"
		elif winner == 2:
			result_text = "P2 WINS"
		_overlay.text = "%s\n\nENTER  rematch\nR  rematch\nESC  main menu" % result_text
		_overlay.visible = true
		if _overlay_backdrop != null:
			_overlay_backdrop.visible = true
	elif _paused:
		_overlay.text = "PAUSED\n\nENTER  resume\nBACKSPACE  main menu"
		_overlay.visible = true
		if _overlay_backdrop != null:
			_overlay_backdrop.visible = true
	else:
		_overlay.visible = false
		if _overlay_backdrop != null:
			_overlay_backdrop.visible = false

func _update_camera() -> void:
	if _camera == null:
		return
	var shake_amount: float = _camera_shake * minf(1.0, _camera_shake / 4.0)
	_camera.offset = Vector2(cos(_camera_phase * 1.13), sin(_camera_phase * 1.71)) * shake_amount
	var viewport_size: Vector2 = get_viewport_rect().size
	if viewport_size.x > 0.0 and viewport_size.y > 0.0:
		var full_zoom: float = minf(viewport_size.x / _world_size.x, viewport_size.y / _world_size.y)
		var zoom_scale: float = 1.0 if not _camera_near else 1.34
		var zoom_value: float = full_zoom * zoom_scale
		_camera.zoom = Vector2.ONE * zoom_value
		var target: Vector2 = _world_size * 0.5
		if _camera_near:
			var fighters: Array = _snapshot.get(&"fighters", [])
			if fighters.size() >= 2:
				var first: Dictionary = fighters[0] if fighters[0] is Dictionary else {}
				var second: Dictionary = fighters[1] if fighters[1] is Dictionary else {}
				var first_position := Vector2(float(first.get(&"x", target.x)), float(first.get(&"y", target.y)))
				var second_position := Vector2(float(second.get(&"x", target.x)), float(second.get(&"y", target.y)))
				target = (first_position + second_position) * 0.5 + Vector2(0.0, -96.0)
				# Keep both fighters and a short approach lane on-screen.  The
				# view only zooms when the live action is close enough to fit;
				# the opening cross-map spawn therefore remains a readable far
				# shot instead of clipping either fighter at the edge.
				var fighter_spread: float = absf(second_position.x - first_position.x)
				var fit_width: float = fighter_spread + 420.0
				var fit_height: float = absf(second_position.y - first_position.y) + 320.0
				var fit_zoom: float = minf(viewport_size.x / fit_width, viewport_size.y / fit_height)
				zoom_value = minf(zoom_value, maxf(full_zoom, fit_zoom))
				_camera.zoom = Vector2.ONE * zoom_value
			var visible_size: Vector2 = viewport_size / zoom_value
			var half_visible: Vector2 = visible_size * 0.5
			target.x = clampf(target.x, half_visible.x, _world_size.x - half_visible.x) if visible_size.x < _world_size.x else _world_size.x * 0.5
			target.y = clampf(target.y, half_visible.y, _world_size.y - half_visible.y) if visible_size.y < _world_size.y else _world_size.y * 0.5
		_camera.position = target

func _draw() -> void:
	var floor_y: float = float(_world_snapshot.get(&"floor_y", _world_size.y - 160.0))
	var classic_map: Texture2D = SF_BANK.map_texture()
	draw_rect(Rect2(Vector2.ZERO, _world_size), Color("#6ea0c8") if classic_map != null else Color("#0b111a"), true)
	if classic_map != null:
		var map_height: float = _world_size.x * float(classic_map.get_height()) / float(classic_map.get_width())
		var ground_ratio: float = 382.0 / 460.0
		var map_y: float = floor_y - map_height * ground_ratio
		draw_texture_rect(classic_map, Rect2(0.0, map_y, _world_size.x, map_height), false)
	else:
		draw_texture_rect(RELAY_YARD_BACKDROP, Rect2(Vector2.ZERO, _world_size), false)
		ARENA_SKIN.draw_foundation(self, _world_size, floor_y)
	_draw_world_geometry()
	_draw_props()
	_draw_pickups()
	_draw_projectiles()
	_draw_grenades()

func _draw_world_geometry() -> void:
	# Bitmap 2219 already contains the Rooftops art, including its floors,
	# ladders and walls.  The JSON topology remains active for physics, but
	# drawing its debug slabs over the classic bitmap makes the scene look like
	# two maps stacked together.
	if SF_BANK.map_texture() != null and String(map_id) == "classic_rooftops":
		return
	var floor_y: float = float(_world_snapshot.get(&"floor_y", _world_size.y - 160.0))
	for platform_value: Variant in _world_snapshot.get(&"platforms", []):
		var platform: Dictionary = platform_value
		var rect := Rect2(float(platform[&"left"]), float(platform[&"y"]), float(platform[&"right"]) - float(platform[&"left"]), 12.0)
		var classic_map: Texture2D = SF_BANK.map_texture()
		if classic_map != null and absf(float(platform[&"y"]) - floor_y) < 2.0:
			continue
		var slab: Color = Color("#b7b7b7") if classic_map != null else Color("#344d5a")
		var slab_top: Color = Color("#f2f2f2") if classic_map != null else Color("#82b9ad")
		var slab_shade: Color = Color("#6e6e6e") if classic_map != null else Color("#1b2b36")
		var slab_edge: Color = Color("#ffffff") if classic_map != null else Color("#d3f1d9")
		draw_rect(rect, slab, true)
		draw_rect(Rect2(rect.position + Vector2(0.0, 2.0), Vector2(rect.size.x, 3.0)), slab_top, true)
		draw_rect(Rect2(rect.position + Vector2(0.0, 7.0), Vector2(rect.size.x, 5.0)), slab_shade, true)
		draw_line(Vector2(rect.position.x, rect.position.y), Vector2(rect.end.x, rect.position.y), slab_edge, 2.0)
		for panel_x: float in range(rect.position.x + 12.0, rect.end.x - 4.0, 42.0):
			draw_line(Vector2(panel_x, rect.position.y + 3.0), Vector2(panel_x + 7.0, rect.position.y + 3.0), Color(0.74, 0.91, 0.84, 0.55), 1.0)
		for brace_x: float in range(rect.position.x + 24.0, rect.end.x, 56.0):
			draw_line(Vector2(brace_x, rect.end.y), Vector2(brace_x + 12.0, rect.end.y + 10.0), Color("#6e9a9b"), 2.0)
	for solid_value: Variant in _world_snapshot.get(&"solids", []):
		var solid: Dictionary = solid_value
		var rect := Rect2(float(solid[&"left"]), float(solid[&"top"]), float(solid[&"right"]) - float(solid[&"left"]), float(solid[&"bottom"]) - float(solid[&"top"]))
		PROP_VISUALS.draw_prop(self, &"cover", rect)
		draw_line(rect.position, Vector2(rect.end.x, rect.position.y), Color("#9fb4ba"), 2.0)

	for ladder_value: Variant in _world_snapshot.get(&"ladders", []):
		var ladder: Dictionary = ladder_value
		var x: float = float(ladder[&"x"])
		var top: float = float(ladder[&"top"])
		var bottom: float = float(ladder[&"bottom"])
		draw_line(Vector2(x - 12.0, top), Vector2(x - 12.0, bottom), Color("#825d3d"), 6.0)
		draw_line(Vector2(x + 12.0, top), Vector2(x + 12.0, bottom), Color("#825d3d"), 6.0)
		draw_line(Vector2(x - 12.0, top), Vector2(x - 12.0, bottom), Color("#e2c27c"), 3.0)
		draw_line(Vector2(x + 12.0, top), Vector2(x + 12.0, bottom), Color("#e2c27c"), 3.0)
		for rung: int in range(int(top) + 10, int(bottom), 18):
			draw_line(Vector2(x - 12.0, rung), Vector2(x + 12.0, rung), Color("#f0d690"), 3.0)
	for pit_value: Variant in _world_snapshot.get(&"pits", []):
		var pit: Dictionary = pit_value
		var pit_rect := Rect2(float(pit[&"left"]), floor_y, float(pit[&"right"]) - float(pit[&"left"]), _world_size.y - floor_y)
		draw_rect(pit_rect, Color("#211329"), true)
		draw_line(pit_rect.position, Vector2(pit_rect.end.x, pit_rect.position.y), Color("#e47b8b"), 3.0)
		for stripe_x: float in range(pit_rect.position.x + 10.0, pit_rect.end.x, 18.0):
			draw_line(Vector2(stripe_x, floor_y + 8.0), Vector2(stripe_x + 8.0, floor_y + 22.0), Color(0.92, 0.48, 0.58, 0.42), 2.0)

func _draw_pickups() -> void:
	for value: Variant in _snapshot.get(&"pickups", []):
		var pickup: Dictionary = value
		if not bool(pickup.get(&"active", true)):
			continue
		var point := Vector2(float(pickup.get(&"x", 0.0)), float(pickup.get(&"y", 0.0)))
		var kind: String = String(pickup.get(&"kind", &"item"))
		var is_airdrop: bool = bool(pickup.get(&"airdrop", false))
		var landed: bool = bool(pickup.get(&"landed", false))
		if is_airdrop:
			draw_line(point + Vector2(0.0, -34.0), point + Vector2(0.0, -6.0), Color("#b8ecf2", 0.72), 1.5)
			draw_arc(point + Vector2(0.0, -38.0), 18.0, PI, TAU, 18, Color("#b8ecf2", 0.8), 2.0)
			draw_line(point + Vector2(-18.0, -38.0), point + Vector2(0.0, -6.0), Color("#b8ecf2", 0.45), 1.0)
			draw_line(point + Vector2(18.0, -38.0), point + Vector2(0.0, -6.0), Color("#b8ecf2", 0.45), 1.0)
			_draw_airdrop_crate(point, String(pickup.get(&"crate_type", _crate_type_for_kind(kind))))
			if not landed:
				# Keep the crate silhouette alone in the air; the weapon icon appears
				# only after the box is on a reachable surface.
				continue
		var tint := Color("#70e0a0") if kind == "medkit" else Color("#f3cb6b") if kind == "grenades" else Color("#f7a76b") if kind == "shotgun" else Color("#d48cff") if kind.begins_with("bullet_time") or kind == "pill" else Color("#f3cb6b")
		if kind == "rocket_launcher":
			tint = Color("#ff7f75")
		elif kind == "pipe" or kind == "knife":
			tint = Color("#a9d9e8")
		var glow := tint
		glow.a = 0.16
		draw_circle(point, 15.0, glow)
		draw_arc(point, 18.0, -PI * 0.92, -PI * 0.08, 18, Color(tint, 0.45), 1.0)
		draw_circle(point, 10.0, Color("#18212a"))
		draw_arc(point, 13.0, -PI * 0.72, PI * 0.72, 16, tint, 2.0)
		_draw_pickup_icon(point, kind, tint)

func _crate_type_for_kind(kind: String) -> String:
	if kind in ["pipe", "knife"]:
		return "melee"
	if kind in ["pistol", "shotgun", "rocket_launcher"]:
		return "firearm"
	if kind == "grenades":
		return "explosive"
	if kind.begins_with("bullet_time") or kind == "pill":
		return "power"
	return "firearm"

func _draw_airdrop_crate(point: Vector2, crate_type: String) -> void:
	var accent: Color = Color("#e7b75b")
	var code: String = "GUN"
	match crate_type:
		"melee":
			accent = Color("#8ad6e8")
			code = "MELEE"
		"explosive":
			accent = Color("#ff796c")
			code = "BOMB"
		"power":
			accent = Color("#d395ff")
			code = "SLOW"
	var box := Rect2(point + Vector2(-22.0, -13.0), Vector2(44.0, 26.0))
	draw_rect(box, Color("#101923", 0.96), true)
	draw_rect(box, Color(accent, 0.94), false, 2.0)
	draw_line(box.position + Vector2(3.0, 4.0), box.end - Vector2(3.0, 4.0), Color(accent, 0.58), 1.2)
	draw_line(Vector2(box.end.x - 3.0, box.position.y + 4.0), Vector2(box.position.x + 3.0, box.end.y - 4.0), Color(accent, 0.58), 1.2)
	if crate_type == "melee":
		draw_line(point + Vector2(-13.0, 6.0), point + Vector2(7.0, -8.0), accent, 3.0)
		draw_line(point + Vector2(-6.0, -8.0), point + Vector2(13.0, 6.0), Color("#f5d27d"), 2.0)
	elif crate_type == "firearm":
		draw_rect(Rect2(point + Vector2(-13.0, -5.0), Vector2(19.0, 7.0)), accent, true)
		draw_line(point + Vector2(-3.0, 2.0), point + Vector2(-8.0, 9.0), accent, 3.0)
		draw_line(point + Vector2(7.0, -3.0), point + Vector2(15.0, -3.0), Color("#fff1b0"), 2.0)
	elif crate_type == "explosive":
		draw_circle(point + Vector2(-3.0, -1.0), 7.0, accent)
		draw_line(point + Vector2(3.0, -7.0), point + Vector2(9.0, -12.0), Color("#ffe59b"), 2.0)
	else:
		draw_circle(point + Vector2(-3.0, -1.0), 8.0, Color(accent, 0.22))
		draw_arc(point + Vector2(-3.0, -1.0), 7.0, -PI * 0.72, PI * 1.25, 14, accent, 2.0)
		draw_line(point + Vector2(-3.0, -1.0), point + Vector2(2.0, -6.0), Color("#fff1b0"), 1.5)
	draw_string(ThemeDB.fallback_font, point + Vector2(-21.0, 23.0), code, HORIZONTAL_ALIGNMENT_CENTER, 42.0, 7, Color(0.94, 0.97, 1.0, 0.94))

func _draw_pickup_icon(point: Vector2, kind: String, tint: Color) -> void:
	var classic_kind: StringName = &"grenade" if kind == "grenades" else StringName(kind)
	var classic_icon: Texture2D = SF_BANK.weapon_texture(classic_kind)
	if classic_icon != null:
		var icon_size: Vector2 = classic_icon.get_size() * 1.35
		draw_texture_rect(classic_icon, Rect2(point - icon_size * 0.5, icon_size), false)
		return
	if kind == "medkit":
		draw_rect(Rect2(point - Vector2(8.0, 6.0), Vector2(16.0, 12.0)), Color("#e7f4e6"), true)
		draw_rect(Rect2(point - Vector2(2.0, 6.0), Vector2(4.0, 12.0)), tint, true)
		draw_rect(Rect2(point - Vector2(8.0, 2.0), Vector2(16.0, 4.0)), tint, true)
	elif kind == "pill" or kind.begins_with("bullet_time"):
		draw_circle(point, 7.0, tint)
		draw_line(point + Vector2(-4.0, 4.0), point + Vector2(4.0, -4.0), Color("#fff1b8"), 2.0)
	else:
		var weapon: StringName = &"grenade" if kind == "grenades" else StringName(kind)
		WEAPON_VISUALS.draw_pickup(self, weapon, point, tint)

func _draw_props() -> void:
	for value: Variant in _world_snapshot.get(&"props", []):
		var prop: Dictionary = value
		if not bool(prop.get(&"active", true)):
			continue
		var point := Vector2(float(prop.get(&"x", 0.0)), float(prop.get(&"y", 0.0)))
		var kind: String = String(prop.get(&"kind", &"prop"))
		var health: float = clampf(float(prop.get(&"health", 1)) / maxf(1.0, float(prop.get(&"max_health", 1))), 0.25, 1.0)
		var size := Vector2(42.0, 34.0) if kind == "crate" else Vector2(30.0, 42.0) if kind == "barrel" else Vector2(40.0, 38.0)
		var bounds := Rect2(point - Vector2(size.x * 0.5, size.y), size)
		_draw_ellipse_shadow(point + Vector2(0.0, 2.0), size.x * 0.55, 5.0)
		var classic_prop: Texture2D = SF_BANK.prop_texture(StringName(kind))
		if classic_prop != null:
			draw_texture_rect(classic_prop, bounds, false, Color(1.0, 1.0, 1.0, health))
		else:
			PROP_VISUALS.draw_prop(self, StringName(kind), bounds, health)

func _draw_ellipse_shadow(center: Vector2, radius_x: float, radius_y: float) -> void:
	var points := PackedVector2Array()
	for index: int in range(20):
		var angle: float = TAU * float(index) / 20.0
		points.append(center + Vector2(cos(angle) * radius_x, sin(angle) * radius_y))
	draw_colored_polygon(points, Color(0.0, 0.0, 0.0, 0.26))

func _draw_grenades() -> void:
	for value: Variant in _snapshot.get(&"grenades", []):
		var grenade: Dictionary = value
		var point := Vector2(float(grenade.get(&"x", 0.0)), float(grenade.get(&"y", 0.0)))
		var kind: StringName = StringName(grenade.get(&"kind", &"grenade"))
		var grenade_tex: Texture2D = SF_BANK.frame_texture("wpn_grenade_thrown", 1) if kind == &"grenade" else SF_BANK.weapon_texture(kind)
		if grenade_tex == null:
			grenade_tex = SF_BANK.weapon_texture(&"grenade")
		if grenade_tex != null:
			var grenade_size: Vector2 = grenade_tex.get_size() * 1.2
			draw_texture_rect(grenade_tex, Rect2(point - grenade_size * 0.5, grenade_size), false)
		else:
			draw_circle(point, 8.0, Color("#d3e278"))
			draw_circle(point, 8.0, Color("#1a2528"), false, 2.0)
		var fuse: int = int(grenade.get(&"fuse", 0))
		draw_line(point + Vector2(5.0, -5.0), point + Vector2(10.0, -10.0), Color("#ffaf7a"), 2.0 if fuse % 2 == 0 else 1.0)

func _draw_projectiles() -> void:
	# Ranged shots are deliberately readable for a few fixed ticks.  The
	# projectile rows are presentation state emitted by MatchSession; damage was
	# already resolved by its deterministic hit ray and is never recomputed here.
	for value: Variant in _snapshot.get(&"projectiles", []):
		if typeof(value) != TYPE_DICTIONARY:
			continue
		var projectile: Dictionary = value
		var point := Vector2(float(projectile.get(&"x", 0.0)), float(projectile.get(&"y", 0.0)))
		var velocity := Vector2(float(projectile.get(&"vx", 0.0)), float(projectile.get(&"vy", 0.0)))
		var direction := velocity.normalized() if not velocity.is_zero_approx() else Vector2.RIGHT
		var kind: StringName = StringName(projectile.get(&"kind", &"bullet"))
		var radius: float = clampf(float(projectile.get(&"radius", 2.0)), 2.0, 7.0)
		var tint: Color = Color("#ffbd5c") if kind == &"bullet" else Color("#ff6338")
		var core: Color = Color("#fff3be") if kind == &"bullet" else Color("#ffe08b")
		var trail_length: float = 10.0 if kind == &"bullet" else 14.0
		draw_line(point - direction * trail_length, point, Color(tint, 0.42), radius * 2.4, true)
		draw_line(point - direction * trail_length * 0.55, point, Color(core, 0.92), maxf(1.0, radius * 0.9), true)
		draw_circle(point, radius, Color(core, 0.98))
		draw_circle(point, radius * 1.8, Color(tint, 0.22))
