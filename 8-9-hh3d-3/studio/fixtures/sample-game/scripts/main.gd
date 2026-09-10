extends Control
class_name Gt01Fixture

enum Phase { MENU, PLAY, PAUSED, QUITTING }

var phase: Phase = Phase.MENU
var body_position: Vector2 = Vector2(320.0, 220.0)
var sim_tick: int = 0
var start_button: Button
var quit_button: Button
var status_label: Label
var instruction_label: Label
signal transitioned(name: String)

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_build_ui()
	_update_ui()
	queue_redraw()

func _build_ui() -> void:
	var panel := VBoxContainer.new()
	panel.position = Vector2(24.0, 24.0)
	panel.custom_minimum_size = Vector2(280.0, 150.0)
	add_child(panel)
	var title := Label.new()
	title.text = "HH Studio GT-01 fixture"
	panel.add_child(title)
	status_label = Label.new()
	panel.add_child(status_label)
	instruction_label = Label.new()
	instruction_label.text = "Enter: Start   Arrows: Move   Esc: Pause   Q: Quit"
	panel.add_child(instruction_label)
	start_button = Button.new()
	start_button.name = "StartButton"
	start_button.text = "Start"
	start_button.focus_mode = Control.FOCUS_ALL
	start_button.pressed.connect(_on_start_pressed)
	panel.add_child(start_button)
	quit_button = Button.new()
	quit_button.name = "QuitButton"
	quit_button.text = "Quit"
	quit_button.focus_mode = Control.FOCUS_ALL
	quit_button.pressed.connect(_quit_fixture)
	panel.add_child(quit_button)
	start_button.grab_focus()

func _physics_process(delta: float) -> void:
	if phase == Phase.PLAY:
		sim_tick += 1
		var direction := Input.get_axis("ui_left", "ui_right")
		body_position.x = clampf(body_position.x + direction * 180.0 * delta, 80.0, 560.0)
		queue_redraw()

func _input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key_event := event as InputEventKey
	if key_event.keycode == KEY_ESCAPE and phase == Phase.PLAY:
		phase = Phase.PAUSED
		_update_ui()
		queue_redraw()
	elif key_event.keycode == KEY_ESCAPE and phase == Phase.PAUSED:
		phase = Phase.PLAY
		_update_ui()
		queue_redraw()
	elif key_event.keycode == KEY_Q:
		_quit_fixture()

func _on_start_pressed() -> void:
	if phase == Phase.MENU:
		phase = Phase.PLAY
		_update_ui()
		transitioned.emit(phase_name())
		queue_redraw()

func _quit_fixture() -> void:
	phase = Phase.QUITTING
	_update_ui()
	transitioned.emit(phase_name())
	get_tree().quit(0)

func phase_name() -> String:
	return Phase.keys()[phase]

func snapshot() -> Dictionary:
	return {"phase": phase_name(), "body_position": body_position, "sim_tick": sim_tick}

func focus_name() -> String:
	var focus_control := get_viewport().gui_get_focus_owner()
	return focus_control.name if focus_control else ""

func _update_ui() -> void:
	if status_label:
		status_label.text = "Phase: %s" % phase_name()
	if start_button:
		start_button.disabled = phase != Phase.MENU

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color("172033"))
	draw_rect(Rect2(60.0, 270.0, 520.0, 4.0), Color("5f759c"))
	var avatar_color := Color("62d3ff") if phase != Phase.PAUSED else Color("f2c14e")
	draw_rect(Rect2(body_position - Vector2(16.0, 32.0), Vector2(32.0, 32.0)), avatar_color)
	draw_circle(Vector2(500.0, 255.0), 14.0, Color("e98275"))
