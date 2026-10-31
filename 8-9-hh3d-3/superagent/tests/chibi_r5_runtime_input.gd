extends SceneTree
## Runtime input integration: actual main.tscn, normal 60 Hz world physics,
## and InputEventKey events delivered to this Godot process only.
## Coverage: MAIN -> Tutorial -> play -> pause -> resume -> return, with
## 20 Tutorial launch/return cycles. This is not full combat parity or FPS proof.

const MainScene: PackedScene = preload("res://scenes/main.tscn")
const OUT: String = "res://docs/chibi-r5/"
const CYCLES: int = 20
const TEST_SEED: int = 28052026
const EPSILON: float = 0.001
const HUD_MAPS: Array[String] = [
	"_last_hp_by_id", "_hp_bar_timer_by_id", "_trailing_hp_by_id",
	"_last_expr_by_id", "_expr_pop_timer_by_id",
]

var _main: Node2D = null
var _menu: Control = null
var _world: Node2D = null
var _checks: int = 0
var _failures: int = 0
var _completed_cycles: int = 0
var _started_usec: int = 0
var _cycle_rows: Array[Dictionary] = []
var _pause_evidence: Dictionary = {}
var _captures: Array[String] = []
var _input_trace: Array[Dictionary] = []


func _initialize() -> void:
	_started_usec = Time.get_ticks_usec()
	seed(TEST_SEED)
	root.size = Vector2i(1280, 720)
	root.content_scale_size = root.size
	call_deferred("_run")


func _run() -> void:
	var dir_error: Error = DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	_check(dir_error == OK, "viewport evidence directory exists")
	_check(Engine.physics_ticks_per_second == 60, "runtime physics uses the project 60 Hz clock")
	_check(not paused, "SceneTree physics is not globally paused")
	if DisplayServer.get_name() == "headless":
		_check(false, "rendered runtime test requires a window renderer for viewport captures")
		await _finish()
		return

	_main = MainScene.instantiate() as Node2D
	root.add_child(_main)
	current_scene = _main
	await _settle(2)
	_menu = _main.get("main_menu") as Control
	_world = _main.get("match_world") as Node2D
	_check(_menu != null and _world != null, "actual main scene creates its menu and match world")
	if _menu == null or _world == null:
		await _finish()
		return
	_check(_menu.visible and str(_menu.get("current_panel")) == "MAIN", "actual startup shows MAIN")
	_check(not _world.visible and _world.process_mode == Node.PROCESS_MODE_DISABLED, "startup match world is hidden and disabled")
	_check(int(_menu.get("selected_index")) == 0, "initial MAIN selection starts at the first choice")

	for cycle: int in range(1, CYCLES + 1):
		await _launch_tutorial(cycle)
		if not _world.visible or _menu.visible:
			break
		var row: Dictionary = _inspect_live_cycle(cycle)
		if cycle == 1:
			await _capture("runtime_play.png")
			await _exercise_pause_resume()
		await _return_by_input()
		await _settle(2)
		_check(_menu.visible and str(_menu.get("current_panel")) == "MAIN", "cycle %d Shift+Escape returns to MAIN" % cycle)
		_check(not _world.visible and _world.process_mode == Node.PROCESS_MODE_DISABLED, "cycle %d return hides and disables the match world" % cycle)
		var hud: CanvasLayer = _world.get("hud_controller") as CanvasLayer
		_check(hud != null and not hud.visible, "cycle %d return hides the CanvasLayer HUD" % cycle)
		row["menu_node_count"] = int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT))
		row["menu_orphan_count"] = int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT))
		_cycle_rows.append(row)
		_completed_cycles += 1
		print("[CHIBI R5 RUNTIME] CYCLE ", JSON.stringify(row))
		if cycle == 1:
			await _capture("runtime_menu.png")

	_check(_completed_cycles == CYCLES, "all 20 input-driven Tutorial launch/return cycles complete")
	_report_coarse_trend()
	await _finish()


func _launch_tutorial(cycle: int) -> void:
	_check(_menu.visible and str(_menu.get("current_panel")) == "MAIN", "cycle %d starts on the visible MAIN panel" % cycle)
	# The first launch must take the real Down, Down, Enter route. Later returns
	# may preserve selection; navigate using events rather than editing menu state.
	if cycle == 1:
		await _tap_key(KEY_DOWN)
		_check(int(_menu.get("selected_index")) == 1, "first Down selects 2 PLAYERS")
		await _tap_key(KEY_DOWN)
	else:
		for _step: int in range(4):
			if int(_menu.get("selected_index")) == 2:
				break
			await _tap_key(KEY_DOWN)
	_check(int(_menu.get("selected_index")) == 2, "cycle %d input selects Tutorial" % cycle)
	await _tap_key(KEY_ENTER)
	# Allow real world physics and HUD process callbacks to run twice after input.
	await _settle(2)
	_check(not _menu.visible and _world.visible, "cycle %d Enter switches menu to live match" % cycle)
	_check(_world.can_process() and _world.is_physics_processing(), "cycle %d live world physics is enabled" % cycle)
	_check(_world.process_mode == Node.PROCESS_MODE_INHERIT, "cycle %d match inherits runtime processing" % cycle)
	_check(not bool(_world.get("is_paused")), "cycle %d starts unpaused" % cycle)
	_check(str(_world.get("current_map_id")) == "storage", "cycle %d Tutorial loads Storage" % cycle)


func _inspect_live_cycle(cycle: int) -> Dictionary:
	var fighters: Array = _world.get("fighters") as Array
	var ids: Dictionary = {}
	var roster: Array[String] = []
	for value: Variant in fighters:
		if value is Node2D and is_instance_valid(value):
			var fighter: Node2D = value as Node2D
			ids[fighter.get_instance_id()] = true
			roster.append(str(fighter.get("character_id")))
	_check(fighters.size() == 2 and ids.size() == 2, "cycle %d has exactly two valid fighters" % cycle)
	_check(roster == ["johnny", "boris"], "cycle %d has the Tutorial Johnny/Boris roster" % cycle)
	var counts: Dictionary = {}
	var stale_ids: Array = []
	var hud: CanvasLayer = _world.get("hud_controller") as CanvasLayer
	_check(hud != null and hud.visible and hud.can_process(), "cycle %d live HUD is visible and processing" % cycle)
	if hud != null:
		for map_name: String in HUD_MAPS:
			var state: Dictionary = hud.get(map_name) as Dictionary
			counts[map_name] = state.size()
			_check(state.size() == ids.size(), "cycle %d %s has one row per current fighter after two frames" % [cycle, map_name])
			for id: Variant in state.keys():
				if not ids.has(id):
					stale_ids.append(id)
	_check(stale_ids.is_empty(), "cycle %d HUD maps contain no previous fighter IDs" % cycle)
	var loader: Node = _world.get("map_loader") as Node
	_check(loader != null and str(loader.get("current_map_id")) == "storage", "cycle %d map loader confirms Storage" % cycle)
	return {
		"cycle": cycle,
		"fighter_ids": ids.keys(),
		"roster": roster,
		"hud_map_counts": counts,
		"stale_hud_ids": stale_ids,
		"map_node_count": _count_subtree(loader),
		"prop_count": (_world.get("props") as Array).size(),
		"pickup_count": (_world.get("pickups") as Array).size(),
		"play_node_count": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"play_orphan_count": int(Performance.get_monitor(Performance.OBJECT_ORPHAN_NODE_COUNT)),
	}


func _exercise_pause_resume() -> void:
	var before_pause: Dictionary = _simulation_snapshot()
	await _tap_key(KEY_ESCAPE)
	_check(bool(_world.get("is_paused")), "Escape pauses through the real runtime hotkey path")
	_check(_world.is_physics_processing() and not paused, "pause test leaves normal SceneTree/world physics callbacks enabled")
	var pause_start: Dictionary = _simulation_snapshot()
	await _settle(6)
	var pause_end: Dictionary = _simulation_snapshot()
	_check(pause_start["fighters"] == pause_end["fighters"], "six paused physics frames preserve every fighter position, source frame and expression")
	_check(pause_start["banner_timer"] == pause_end["banner_timer"], "six paused physics frames preserve the banner timer")
	_check(pause_start["banner_text"] == pause_end["banner_text"], "six paused physics frames preserve the banner text")
	_check(pause_start["hud_maps"] == pause_end["hud_maps"], "six paused physics frames preserve HUD trailing HP and timer maps")
	_check(pause_start["active_cutin"] == pause_end["active_cutin"] and pause_start["active_cutins"] == pause_end["active_cutins"], "six paused physics frames preserve any naturally active cut-ins")
	await _capture("runtime_paused.png")
	await _tap_key(KEY_ESCAPE)
	_check(not bool(_world.get("is_paused")), "a released and repressed Escape resumes through runtime input")
	var source_progressed: bool = false
	for _sample: int in range(6):
		await _settle(1)
		var resumed: Dictionary = _simulation_snapshot()
		if _source_frames_differ(pause_end["fighters"] as Dictionary, resumed["fighters"] as Dictionary):
			source_progressed = true
	var after_resume: Dictionary = _simulation_snapshot()
	_check(float(after_resume["banner_timer"]) < float(pause_end["banner_timer"]) - EPSILON, "resumed runtime advances the live banner timer")
	_check(source_progressed, "resumed runtime advances a real fighter source animation frame")
	_check(float(after_resume["banner_timer"]) < float(before_pause["banner_timer"]), "pause/resume preserves rather than resets the round timer")
	_pause_evidence = {
		"before_input": before_pause,
		"paused_start": pause_start,
		"paused_after_six_physics_frames": pause_end,
		"after_resume": after_resume,
		"source_progress_observed": source_progressed,
		"cutin_coverage": "naturally present state only; none forced",
	}


func _simulation_snapshot() -> Dictionary:
	var actor_state: Dictionary = {}
	for value: Variant in (_world.get("fighters") as Array):
		if not value is Node2D or not is_instance_valid(value):
			continue
		var fighter: Node2D = value as Node2D
		var rig: Node = fighter.get("rig_view") as Node
		var pos: Vector2 = fighter.global_position
		actor_state[fighter.get_instance_id()] = {
			"position": [pos.x, pos.y],
			"state": str(fighter.get("current_state")),
			"source_frame": float(rig.get("source_motion_frame")) if rig != null else -1.0,
			"expression": str(rig.get("_current_expr_id")) if rig != null else "missing",
		}
	var hud_maps: Dictionary = {}
	var hud: CanvasLayer = _world.get("hud_controller") as CanvasLayer
	if hud != null:
		for map_name: String in HUD_MAPS:
			hud_maps[map_name] = (hud.get(map_name) as Dictionary).duplicate(true)
	return {
		"fighters": actor_state,
		"banner_timer": float(_world.get("banner_timer")),
		"banner_text": str(_world.get("banner_text")),
		"hud_maps": hud_maps,
		"active_cutin": (_world.get("active_cutin") as Dictionary).duplicate(true),
		"active_cutins": (_world.get("active_cutins") as Array).duplicate(true),
	}


func _source_frames_differ(first: Dictionary, second: Dictionary) -> bool:
	for id: Variant in first.keys():
		if not second.has(id):
			continue
		var previous: Dictionary = first[id] as Dictionary
		var current: Dictionary = second[id] as Dictionary
		if float(previous["source_frame"]) >= 0.0 and absf(float(previous["source_frame"]) - float(current["source_frame"])) > EPSILON:
			return true
	return false


func _return_by_input() -> void:
	_send_key(KEY_SHIFT, true, true)
	await _settle(1)
	_send_key(KEY_ESCAPE, true, true)
	await _settle(2)
	_send_key(KEY_ESCAPE, false, true)
	_send_key(KEY_SHIFT, false, false)
	await _settle(1)
	_check(not Input.is_key_pressed(KEY_ESCAPE) and not Input.is_key_pressed(KEY_SHIFT), "return hotkey releases both Escape and Shift")


func _tap_key(key: Key) -> void:
	_send_key(key, true)
	await _settle(1)
	_send_key(key, false)
	await _settle(1)


func _send_key(key: Key, pressed: bool, shift: bool = false) -> void:
	_input_trace.append({"physics_frame": Engine.get_physics_frames(), "keycode": int(key), "pressed": pressed, "shift": shift})
	var event: InputEventKey = InputEventKey.new()
	event.keycode = key
	event.physical_keycode = key
	event.pressed = pressed
	event.echo = false
	event.shift_pressed = shift
	Input.parse_input_event(event)


func _settle(physics_frames: int) -> void:
	for _frame: int in range(physics_frames):
		await physics_frame
		# physics_frame is emitted before node physics callbacks. Wait for the
		# subsequent process frame so observations include their completed work.
		await process_frame


func _capture(file: String) -> void:
	await RenderingServer.frame_post_draw
	var viewport_image: Image = root.get_texture().get_image()
	_check(viewport_image != null and not viewport_image.is_empty(), "viewport capture is nonempty: " + file)
	if viewport_image == null or viewport_image.is_empty():
		return
	var error: Error = viewport_image.save_png(OUT + file)
	_check(error == OK, "viewport capture saves: " + file)
	if error == OK:
		_captures.append(OUT + file)
	print("[CHIBI R5 RUNTIME] viewport_capture=", file, " save_error=", error)


func _count_subtree(node: Node) -> int:
	if node == null or not is_instance_valid(node):
		return 0
	var count: int = 1
	for child: Node in node.get_children():
		count += _count_subtree(child)
	return count


func _report_coarse_trend() -> void:
	if _cycle_rows.is_empty():
		return
	var first: Dictionary = _cycle_rows[0]
	var last: Dictionary = _cycle_rows[-1]
	var node_delta: int = int(last["menu_node_count"]) - int(first["menu_node_count"])
	var orphan_delta: int = int(last["menu_orphan_count"]) - int(first["menu_orphan_count"])
	# These are coarse observations. Audio players may be naturally transient;
	# exact object/AudioStream counts are deliberately not a leak oracle.
	print("[CHIBI R5 RUNTIME] COARSE_TREND menu_node_delta=", node_delta, " menu_orphan_delta=", orphan_delta, " samples=", _cycle_rows.size(), " exact_audio_object_count_claim=0")


func _finish() -> void:
	for key: Key in [KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_SHIFT]:
		_send_key(key, false)
	var audio: Node = root.get_node_or_null("AudioManager")
	if _main != null and is_instance_valid(_main):
		_main.process_mode = Node.PROCESS_MODE_DISABLED
	if audio != null and audio.has_method("stop_all_and_drain"):
		_check(bool(await audio.call("stop_all_and_drain")), "audio playbacks fully released before quit")
	if _main != null and is_instance_valid(_main):
		current_scene = null
		_main.queue_free()
	await _settle(2)
	var elapsed_ms: float = float(Time.get_ticks_usec() - _started_usec) / 1000.0
	var report: Dictionary = {
		"schema": "chibi-r5.runtime-input.v1",
		"timestamp_utc": Time.get_datetime_string_from_system(true) + "Z",
		"seed": TEST_SEED,
		"coverage": "actual main scene; MAIN keyboard Tutorial; live play; Escape pause/resume; Shift+Escape return; 20 launch/return cycles",
		"full_combat_parity": false,
		"fps_benchmark": false,
		"desktop_input": false,
		"world_physics_disabled_by_test": false,
		"elapsed_ms": elapsed_ms,
		"host_exit_evidence": "captured separately by host runner; no script-side actual_exit claim",
		"completed_cycles": _completed_cycles,
		"checks": _checks,
		"failures": _failures,
		"cycles": _cycle_rows,
		"pause": _pause_evidence,
		"input_trace": _input_trace,
		"viewport_captures": _captures,
	}
	var report_file: FileAccess = FileAccess.open(OUT + "runtime_input_report.json", FileAccess.WRITE)
	_check(report_file != null, "runtime report opens for writing")
	report["checks"] = _checks
	report["failures"] = _failures
	if report_file != null:
		report_file.store_string(JSON.stringify(report, "\t"))
		report_file.close()
	print("[CHIBI R5 RUNTIME] ", "PASS" if _failures == 0 else "FAIL", " checks=", _checks, " failures=", _failures, " cycles=", _completed_cycles, " elapsed_ms=", elapsed_ms, " coverage=menu_Tutorial_play_pause_resume_return process_exit_evidence=host_receipt full_combat_parity=0 fps_benchmark=0")
	quit(0 if _failures == 0 else 1)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if not condition:
		_failures += 1
		push_error("[CHIBI R5 RUNTIME] " + label)
