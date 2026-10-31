extends SceneTree
## Live integration diagnostic. Engine-local InputMap actions, normal match
## stepping, no desktop input, forced pose, teleport, kill or other-app capture.
## This is viewport evidence and a manual CPU sample, not an FPS benchmark.

const MatchScript: Script = preload("res://game/core/match_controller.gd")
const MenuScript: Script = preload("res://game/ui/main_menu_controller.gd")
const OUT: String = "res://docs/chibi-r5/"
const ACTIONS: Array[String] = ["p1_right", "p1_left", "p1_up", "p1_attack", "p1_aim", "p1_skill_1", "p2_left", "p2_attack", "p2_skill_1"]

var _captures: Array[String] = []


func _initialize() -> void:
	seed(28052026)
	root.size = Vector2i(1280, 720)
	root.content_scale_size = root.size
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	call_deferred("_run")


func _run() -> void:
	var menu: Control = MenuScript.new() as Control
	root.add_child(menu)
	for _frame: int in range(6):
		await process_frame
	if not await _capture("05_menu.png"):
		menu.free()
		await _finish(false)
		return
	menu.free()
	await process_frame
	for mode_index: int in range(1, 4):
		if not await _run_mode(mode_index):
			await _finish(false)
			return
	await _finish(true)


func _finish(success: bool) -> void:
	for action: String in ACTIONS:
		Input.action_release(action)
	var audio: Node = root.get_node_or_null("AudioManager")
	var drained: bool = true
	if audio != null and audio.has_method("stop_all_and_drain"):
		drained = bool(await audio.call("stop_all_and_drain"))
	if success and drained:
		print("[R5 LIVE] complete: viewport-only integration diagnostics, not full E2E/benchmark acceptance")
	quit(0 if success and drained else 1)


func _run_mode(mode_index: int) -> bool:
	if mode_index == 3:
		root.size = Vector2i(960, 540)
		root.content_scale_size = root.size
	var world: Node2D = MatchScript.new() as Node2D
	root.add_child(world)
	world.call("start_match", {
		"mode": "vs", "map_id": "rooftops", "two_player": true,
		"p1_char": "johnny" if mode_index == 1 else "goku",
		"p2_char": "agent" if mode_index == 1 else "naruto",
		"bot_count": 0 if mode_index == 1 else 6,
	})
	var timings: Array[float] = []
	var states_seen: Dictionary = {}
	for frame: int in range(1, 421):
		for action: String in ACTIONS:
			Input.action_release(action)
		if frame > 80 and frame < 180:
			Input.action_press("p1_right")
			Input.action_press("p2_left")
		if frame > 180 and frame < 310 and frame % 14 < 5:
			Input.action_press("p1_attack")
		if frame > 310 and frame < 390 and frame % 20 < 10:
			Input.action_press("p1_aim")
		if frame in [210, 270, 330]:
			Input.action_press("p1_up")
		if mode_index >= 2 and frame in [220, 280, 360]:
			Input.action_press("p1_skill_1")
			Input.action_press("p2_skill_1")
		var before: int = Time.get_ticks_usec()
		world.call("step_match", 28.0 / 60.0 * float(world.get("game_speed")))
		var elapsed_ms: float = float(Time.get_ticks_usec() - before) / 1000.0
		if frame > 60:
			timings.append(elapsed_ms)
		for fighter: Node2D in world.get("fighters"):
			states_seen[str(fighter.get("current_state"))] = true
		var hud: Node = world.get("hud_controller") as Node
		if hud != null:
			hud.call("_process", 1.0 / 60.0)
			hud.call("update_hud")
		if frame == 245 or frame == 355:
			if not await _capture("0" + str(5 + mode_index) + "_live_" + str(root.size.x) + "_f" + str(frame) + ".png"):
				world.free()
				await process_frame
				return false
		await process_frame
	timings.sort()
	var p95: float = timings[clampi(int(float(timings.size()) * 0.95), 0, timings.size() - 1)] if not timings.is_empty() else 0.0
	print("[R5 LIVE] mode=", mode_index, " viewport=", root.size, " CPU_manual_tick_p95_ms=", p95, " states=", states_seen.keys(), " GPU_FRAME_TIME=NOT_MEASURED")
	world.free()
	await process_frame
	return true


func _capture(file: String) -> bool:
	await RenderingServer.frame_post_draw
	var image: Image = root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("Empty viewport " + file)
		return false
	var error: Error = image.save_png(OUT + file)
	print("[R5 LIVE] saved ", file, " error=", error)
	if error == OK:
		_captures.append(OUT + file)
	return error == OK
