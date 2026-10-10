extends CanvasLayer
## Opt-in input lifecycle. Observations are untrusted; host evidence owns attribution.
## --fixture-lifecycle accepts external input for up to 16 minutes.
## --fixture-lifecycle-smoke injects a short input trace, never a playtest claim.
## --fixture-lifecycle-scripted runs the delegated 15-minute agent trace.

const SESSION_SECONDS: int = 960
const SEED: int = 90127
const MAX_INPUT_EDGES: int = 8192
const OBSERVE_EVERY_TICKS: int = 300
var phase: String = "MENU"
var wall_tick: int = 0
var _state: Callable
var _reset: Callable
var _label: Label
var _shade: ColorRect
var _started_ms: int = 0
var _held: Dictionary = {}
var _frozen: Dictionary = {}
var _counts: Dictionary = {"start": 0, "pause": 0, "resume": 0, "restart": 0, "quit": 0}
var _pause_frames: int = 0
var _freeze_errors: int = 0
var _edges: int = 0
var _pending: String = ""
var _smoke: bool = false
var _scripted: bool = false
var _finished: bool = false
var _state_observations: int = 0
var _transition_events: Array[String] = []
var _input_trace: Array[Dictionary] = []
var _scripted_edges: Dictionary = {}

static func requested() -> bool:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	return args.has("--fixture-lifecycle") or args.has("--fixture-lifecycle-smoke") \
		or args.has("--fixture-lifecycle-scripted")

func begin(state_readback: Callable, reset_world: Callable, title: String) -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 100
	_state = state_readback
	_reset = reset_world
	_smoke = OS.get_cmdline_user_args().has("--fixture-lifecycle-smoke")
	_scripted = OS.get_cmdline_user_args().has("--fixture-lifecycle-scripted")
	_started_ms = Time.get_ticks_msec()
	Input.use_accumulated_input = false
	_shade = ColorRect.new()
	_shade.color = Color(0.04, 0.06, 0.1, 0.88)
	_shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(_shade)
	_label = Label.new()
	_label.name = "LifecycleMenu"
	_label.position = Vector2(16.0, 16.0)
	_label.set_meta("fixture_title", title)
	add_child(_label)
	get_tree().paused = true
	_refresh()
	_observe("menu")

func _refresh() -> void:
	_shade.visible = phase != "PLAYING"
	_label.text = str(_label.get_meta("fixture_title")) + " / " + phase + "\n"
	_label.text += "Enter: start/resume | P/Esc: pause/resume | R: restart | Q: quit\n"
	_label.text += "A/D: move | Space: jump | F: shoot | E: interact"

func _input(event: InputEvent) -> void:
	if not _state.is_valid() or _finished or not event is InputEventKey:
		return
	var edge := event as InputEventKey
	if edge.echo:
		return
	var key: Key = edge.physical_keycode if edge.physical_keycode != 0 else edge.keycode
	if not key in [KEY_A, KEY_D, KEY_SPACE, KEY_F, KEY_E, KEY_ENTER, KEY_P, KEY_ESCAPE, KEY_R, KEY_Q]:
		return
	if edge.pressed == _held.has(key):
		return
	if edge.pressed:
		_held[key] = true
	else:
		_held.erase(key)
	_edges += 1
	var trace_row := {"edge": _edges, "wall_tick": wall_tick,
		"elapsed_ms": Time.get_ticks_msec() - _started_ms, "key": key,
		"state": "pressed" if edge.pressed else "released", "phase": phase}
	_input_trace.append(trace_row)
	print("HH_FIXTURE_LIFECYCLE_INPUT " + JSON.stringify(trace_row))
	if _edges > MAX_INPUT_EDGES:
		_finish("input_limit", 45)
		return
	if not edge.pressed:
		return
	if key == KEY_Q:
		_request("quit")
	elif key == KEY_R and phase in ["PLAYING", "PAUSED"]:
		_request("restart")
	elif key == KEY_ENTER and phase in ["MENU", "PAUSED"]:
		_request("start" if phase == "MENU" else "resume")
	elif key in [KEY_P, KEY_ESCAPE] and phase in ["PLAYING", "PAUSED"]:
		_request("pause" if phase == "PLAYING" else "resume")

func _request(command: String) -> void:
	if _pending.is_empty():
		_pending = command
		call_deferred("_apply_command", command)

func _apply_command(command: String) -> void:
	_pending = ""
	if _finished:
		return
	_check_frozen()
	_counts[command] += 1
	_transition_events.append(command)
	if command == "quit":
		_finish("input_quit", 0)
		return
	if command in ["start", "restart"]:
		# Deferred from the input edge so bodies are never removed during query flush.
		get_tree().paused = true
		if _reset.call() != true:
			_finish("reset_failed", 46)
			return
	phase = "PAUSED" if command == "pause" else "PLAYING"
	get_tree().paused = phase == "PAUSED"
	_frozen = _simulation_state() if phase == "PAUSED" else {}
	_refresh()
	_observe(command)

func _world() -> Dictionary:
	var value: Variant = _state.call()
	return value if value is Dictionary else {"readback_failed": true}

func _check_frozen() -> void:
	if phase == "PAUSED":
		_pause_frames += 1
		if _simulation_state() != _frozen or not get_tree().paused:
			_freeze_errors += 1

func _simulation_state() -> Dictionary:
	var result: Dictionary = _world().duplicate(true)
	# Physical key release remains observable while simulation is paused.
	for key: String in result.keys():
		if key.begins_with("input_"):
			result.erase(key)
	return result

func _physics_process(_delta: float) -> void:
	if not _state.is_valid() or _finished:
		return
	wall_tick += 1
	_check_frozen()
	if _smoke:
		_smoke_edge()
	elif _scripted:
		_scripted_edge()
	# Observe a second frozen world sample during the one-second scripted pause.
	# This node runs PROCESS_MODE_ALWAYS while the gameplay tree stays paused.
	if phase == "PAUSED" and wall_tick % 30 == 0:
		_observe("pause_sample")
	if wall_tick % OBSERVE_EVERY_TICKS == 0:
		_observe("sample")
	if Time.get_ticks_msec() - _started_ms >= SESSION_SECONDS * 1000:
		_finish("session_timeout", 43)

func _observe(event: String) -> void:
	_state_observations += 1
	print("HH_FIXTURE_LIFECYCLE_STATE " + JSON.stringify({"event": event,
		"phase": phase, "wall_tick": wall_tick,
		"elapsed_ms": Time.get_ticks_msec() - _started_ms, "seed": SEED,
		"tree_paused": get_tree().paused, "menu_visible": _shade.visible,
		"held_keys": _held.keys(), "world": _world(), "freeze_errors": _freeze_errors}))

func _finish(reason: String, exit_code: int) -> void:
	if _finished:
		return
	_check_frozen()
	_finished = true
	phase = "QUIT"
	get_tree().paused = true
	_refresh()
	_observe("quit" if reason == "input_quit" else reason)
	var complete: bool = _pause_frames > 1 and _freeze_errors == 0
	for command: String in _counts:
		complete = complete and int(_counts[command]) > 0
	print("HH_FIXTURE_LIFECYCLE_SUMMARY " + JSON.stringify({"schema": "hh-fixture-lifecycle-1",
		"authority": 0, "acceptance": false, "playtest_claim": false,
		"mode": "smoke" if _smoke else ("scripted" if _scripted else "external_input"),
		"reason": reason,
		"elapsed_ms": Time.get_ticks_msec() - _started_ms, "seed": SEED,
		"counts": _counts, "input_edges": _edges, "pause_frames": _pause_frames,
		"freeze_errors": _freeze_errors, "state_observations": _state_observations,
		"transitions": _transition_events, "lifecycle_complete": complete,
		"world": _world()}))
	get_tree().paused = false
	get_tree().quit(exit_code if exit_code != 0 else (0 if complete else 44))

func _key(key: Key, pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = pressed
	Input.parse_input_event(event)

func _smoke_edge() -> void:
	# Only this explicitly named short mode authors input. External mode never does.
	match wall_tick:
		2, 3: _key(KEY_ENTER, wall_tick == 2)
		8, 120: _key(KEY_D, wall_tick == 8)
		25, 26: _key(KEY_F, wall_tick == 25)
		28, 29: _key(KEY_SPACE, wall_tick == 28)
		40, 41: _key(KEY_P, wall_tick == 40)
		52, 53: _key(KEY_P, wall_tick == 52)
		160, 161: _key(KEY_R, wall_tick == 160)
		162, 240: _key(KEY_D, wall_tick == 162)
		180, 181: _key(KEY_E, wall_tick == 180)
		250, 251: _key(KEY_ESCAPE, wall_tick == 250)
		260, 261: _key(KEY_ENTER, wall_tick == 260)
		280: _key(KEY_Q, true)

func _scripted_once(label: String, key: Key, pressed: bool, at_seconds: float) -> void:
	if _scripted_edges.has(label):
		return
	if float(Time.get_ticks_msec() - _started_ms) / 1000.0 < at_seconds:
		return
	_scripted_edges[label] = true
	_key(key, pressed)

func _scripted_edge() -> void:
	# This trace is explicit and bounded. It is a delegated agent run, not a
	# human playtest and never changes the acceptance authority.
	_scripted_once("start_down", KEY_ENTER, true, 1.0)
	_scripted_once("start_up", KEY_ENTER, false, 1.1)
	_scripted_once("move_down", KEY_D, true, 2.0)
	_scripted_once("move_up", KEY_D, false, 9.0)
	_scripted_once("shoot_down", KEY_F, true, 3.0)
	_scripted_once("shoot_up", KEY_F, false, 3.1)
	_scripted_once("jump_down", KEY_SPACE, true, 4.0)
	_scripted_once("jump_up", KEY_SPACE, false, 4.1)
	_scripted_once("interact_down", KEY_E, true, 2.6)
	_scripted_once("interact_up", KEY_E, false, 2.7)
	_scripted_once("pause_down", KEY_P, true, 30.0)
	_scripted_once("pause_up", KEY_P, false, 30.1)
	_scripted_once("resume_down", KEY_P, true, 31.0)
	_scripted_once("resume_up", KEY_P, false, 31.1)
	_scripted_once("restart_down", KEY_R, true, 120.0)
	_scripted_once("restart_up", KEY_R, false, 120.1)
	# Replay gameplay after restart so the long delegated trace leaves a
	# post-reset interaction/readback, rather than only proving the reset UI.
	_scripted_once("move2_down", KEY_D, true, 121.0)
	_scripted_once("shoot2_down", KEY_F, true, 121.7)
	_scripted_once("shoot2_up", KEY_F, false, 121.8)
	_scripted_once("jump2_down", KEY_SPACE, true, 123.0)
	_scripted_once("jump2_up", KEY_SPACE, false, 123.1)
	_scripted_once("interact2_down", KEY_E, true, 121.8)
	_scripted_once("interact2_up", KEY_E, false, 121.9)
	_scripted_once("move2_up", KEY_D, false, 128.0)
	_scripted_once("pause2_down", KEY_ESCAPE, true, 300.0)
	_scripted_once("pause2_up", KEY_ESCAPE, false, 300.1)
	_scripted_once("resume2_down", KEY_ENTER, true, 301.0)
	_scripted_once("resume2_up", KEY_ENTER, false, 301.1)
	# Quit before the 960-second watchdog so the summary proves input quit.
	_scripted_once("quit_down", KEY_Q, true, 901.0)

static func paint_arena(arena: Node2D) -> void:
	# Minimal presentation of the existing collision geometry, without altering it.
	for actor: Node in arena.get_children():
		if not actor is CollisionObject2D:
			continue
		for child: Node in actor.get_children():
			if child is CollisionShape2D and (child as CollisionShape2D).shape is RectangleShape2D:
				var half: Vector2 = ((child as CollisionShape2D).shape as RectangleShape2D).size * 0.5
				var paint := Polygon2D.new()
				paint.polygon = PackedVector2Array([-half, Vector2(half.x, -half.y), half, Vector2(-half.x, half.y)])
				paint.color = Color(0.25, 0.75, 0.9) if actor is CharacterBody2D else Color(0.7, 0.6, 0.3)
				actor.add_child(paint)
