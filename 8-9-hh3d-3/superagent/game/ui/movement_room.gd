class_name MovementRoom
extends Node2D
## Provisional two-player SA-03 room. Simulation is the only movement authority.

const FIXED_STEP: float = 1.0 / 60.0
const WORLD_SIZE := Vector2(1600.0, 900.0)
const SIMULATION_SCRIPT = preload("res://game/core/simulation.gd")
const BUFFER_SCRIPT = preload("res://game/core/input_buffer.gd")

signal fixed_step_completed(frame: InputFrame)

var simulation: Simulation
var input_buffer: InputBuffer
var _last_frame: InputFrame
var _accumulator: float = 0.0
var _label: Label
var _p1: FighterView
var _p2: FighterView
var _world_snapshot: Dictionary = {}

func _ready() -> void:
	# Keep the room's semantic input path explicit in headless and windowed runs.
	set_process_input(true)
	simulation = SIMULATION_SCRIPT.new(1)
	input_buffer = BUFFER_SCRIPT.new()
	_p1 = get_node("Fighter1") as FighterView
	_p2 = get_node("Fighter2") as FighterView
	var char_width: int = int(simulation.tuning.get(&"char_width", 28))
	var char_height: int = int(simulation.tuning.get(&"char_height", 48))
	_p1.configure(1, char_width, char_height)
	_p2.configure(2, char_width, char_height)
	_label = get_node("CanvasLayer/Status") as Label
	_update_world()
	_update_views()
	_update_transform()

func _input(event: InputEvent) -> void:
	if event is InputEventKey:
		var key_event := event as InputEventKey
		if key_event.pressed and not key_event.echo and key_event.keycode == KEY_ESCAPE:
			get_tree().change_scene_to_file("res://main.tscn")
			return
		if key_event.pressed and not key_event.echo and key_event.keycode == KEY_R:
			_reset_room()
			return
	input_buffer.accept_event(event)

func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT and input_buffer != null:
		input_buffer.cancel_all()

func _physics_process(delta: float) -> void:
	_accumulator = minf(_accumulator + delta, 0.25)
	while _accumulator >= FIXED_STEP:
		_last_frame = input_buffer.build_frame(simulation.tick)
		if not simulation.step(_last_frame):
			push_error("Movement room rejected its fixed-step input frame")
			return
		_accumulator -= FIXED_STEP
		_update_views()
		fixed_step_completed.emit(_last_frame)

func _process(_delta: float) -> void:
	_update_transform()

func read_snapshot() -> Dictionary:
	return simulation.snapshot()

func read_last_frame() -> InputFrame:
	return _last_frame

func _reset_room() -> void:
	input_buffer.cancel_all()
	# Reset starts a fresh input session. Drop cancellation edges from the old
	# session so the first new simulation tick cannot replay stale held input.
	input_buffer = BUFFER_SCRIPT.new()
	simulation = SIMULATION_SCRIPT.new(1)
	_accumulator = 0.0
	_last_frame = null
	_update_world()
	_update_views()

func _update_world() -> void:
	_world_snapshot = simulation.snapshot().get(&"world", {})
	queue_redraw()

func _update_views() -> void:
	if simulation == null or simulation.fighters.size() < 2:
		return
	_p1.apply_state(simulation.fighters[0].snapshot())
	_p2.apply_state(simulation.fighters[1].snapshot())
	_world_snapshot = simulation.snapshot().get(&"world", {})
	if _label != null:
		var state_1: Dictionary = simulation.fighters[0].snapshot()
		var state_2: Dictionary = simulation.fighters[1].snapshot()
		_label.text = "SA-03 MOVEMENT LAB  |  PROVISIONAL TUNING\n" + \
			"P1 WASD  •  P2 arrows  •  R reset lab  •  Esc menu\n" + \
			"Punch / Shoot / Throw / Power: P1 J / K / L / ;  •  P2 NumPad 1 / 2 / 3 / 4 (Num Lock on)\n" + \
			"tick %d   P1 %s (%d,%d)   P2 %s (%d,%d)" % [
				simulation.tick, String(state_1.get(&"action", &"idle")), int(state_1.get(&"x", 0)), int(state_1.get(&"y", 0)),
				String(state_2.get(&"action", &"idle")), int(state_2.get(&"x", 0)), int(state_2.get(&"y", 0))]
	queue_redraw()

func _update_transform() -> void:
	var viewport_size: Vector2 = get_viewport_rect().size
	var scale_factor: float = minf(viewport_size.x / WORLD_SIZE.x, viewport_size.y / WORLD_SIZE.y)
	scale = Vector2.ONE * scale_factor
	position = (viewport_size - WORLD_SIZE * scale_factor) * 0.5

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, WORLD_SIZE), Color("#0b1220"), true)
	var platforms: Array = _world_snapshot.get(&"platforms", [])
	for platform: Dictionary in platforms:
		var rect := Rect2(float(platform[&"left"]), float(platform[&"y"]), float(platform[&"right"]) - float(platform[&"left"]), 12.0)
		draw_rect(rect, Color("#2a6a85"), true)
		draw_line(Vector2(rect.position.x, rect.position.y), Vector2(rect.end.x, rect.position.y), Color("#8ee8ff"), 3.0)
	var solids: Array = _world_snapshot.get(&"solids", [])
	for solid: Dictionary in solids:
		var solid_rect := Rect2(float(solid[&"left"]), float(solid[&"top"]), float(solid[&"right"]) - float(solid[&"left"]), float(solid[&"bottom"]) - float(solid[&"top"]))
		draw_rect(solid_rect, Color("#385064"), true)
		draw_rect(solid_rect, Color("#9bb4c4"), false, 2.0)
	var ladders: Array = _world_snapshot.get(&"ladders", [])
	for ladder: Dictionary in ladders:
		var x: float = float(ladder[&"x"])
		var top: float = float(ladder[&"top"])
		var bottom: float = float(ladder[&"bottom"])
		draw_line(Vector2(x - 12.0, top), Vector2(x - 12.0, bottom), Color("#dfba67"), 4.0)
		draw_line(Vector2(x + 12.0, top), Vector2(x + 12.0, bottom), Color("#dfba67"), 4.0)
		for rung: int in range(int(top) + 10, int(bottom), 18):
			draw_line(Vector2(x - 12.0, rung), Vector2(x + 12.0, rung), Color("#dfba67"), 3.0)
	var pits: Array = _world_snapshot.get(&"pits", [])
	for pit: Dictionary in pits:
		var pit_rect := Rect2(float(pit[&"left"]), 740.0, float(pit[&"right"]) - float(pit[&"left"]), 160.0)
		draw_rect(pit_rect, Color("#190e2e"), true)
		draw_line(pit_rect.position, Vector2(pit_rect.end.x, pit_rect.position.y), Color("#d05cff"), 3.0)
