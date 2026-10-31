extends SceneTree
## Real map/projectile/pickup simulation with prescribed spawn positions.
## Diagnostic trajectory visualization, not keyboard gameplay evidence.
const MatchScript = preload("res://game/core/match_controller.gd")
const OUT: String = "res://docs/chibi-r6/"
const STEP: float = 28.0 / 60.0
var failures: int = 0
var world: Node2D
var tracks: Dictionary = {"bullet": [], "grenade": [], "dropped_gun": []}
var paths: Dictionary = {}
var status: Label

func _initialize() -> void:
	root.size = Vector2i(1280, 720)
	root.content_scale_size = root.size
	DirAccess.make_dir_recursive_absolute(OUT)
	call_deferred("_run")

func _label(at: Vector2, text_value: String, font_size: int = 19) -> Label:
	var label := Label.new()
	label.position = at
	label.text = text_value
	label.add_theme_font_size_override("font_size", font_size)
	root.add_child(label)
	return label

func _run() -> void:
	seed(6282026)
	var back := ColorRect.new()
	back.size = Vector2(1280, 720)
	back.color = Color("101724")
	root.add_child(back)
	_label(Vector2(24, 15), "STEEL HARBOR / OPEN LADDER SHAFT", 27)
	_label(Vector2(26, 53), "Real map + projectile/pickup stepping / prescribed spawns / NOT gameplay E2E", 15)
	var container := SubViewportContainer.new()
	container.position = Vector2(20, 88)
	container.size = Vector2(620, 608)
	root.add_child(container)
	var viewport := SubViewport.new()
	viewport.size = Vector2i(620, 608)
	viewport.world_2d = World2D.new()
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(viewport)
	world = MatchScript.new()
	viewport.add_child(world)
	world.process_mode = Node.PROCESS_MODE_DISABLED
	world.call("start_match", {"mode": "vs", "map_id": "steel_harbor", "two_player": true, "bot_count": 0, "p1_char": "johnny", "p2_char": "agent"})
	for actor: Node2D in world.get("fighters"):
		actor.free()
	(world.get("fighters") as Array).clear()
	for prop: Node2D in world.get("props"):
		prop.free()
	(world.get("props") as Array).clear()
	for pickup: Dictionary in world.get("pickups"):
		var node: Node = pickup.get("node") as Node
		if is_instance_valid(node):
			node.free()
	(world.get("pickups") as Array).clear()
	(world.get("hud_controller") as CanvasLayer).visible = false
	(world.get("dynamic_camera") as Camera2D).enabled = false
	var camera := Camera2D.new()
	camera.position = Vector2(-266.0, -45.0)
	camera.zoom = Vector2(2.58, 2.58)
	viewport.add_child(camera)
	camera.make_current()
	var pm: Node2D = world.get("projectile_manager") as Node2D
	pm.call("clear_all")
	pm.call("spawn_bullet", null, "SNIPER", Vector2(-334, -132), 0.0)
	var colors: Dictionary = {"bullet": Color("88deb2"), "grenade": Color("f4b35c"), "dropped_gun": Color("81b9f4")}
	for key: String in tracks:
		var path := Line2D.new()
		path.width = 0.55
		path.default_color = colors[key]
		path.z_index = 100
		world.add_child(path)
		paths[key] = path
	_label(Vector2(686, 113), "BULLET", 23).modulate = colors["bullet"]
	_label(Vector2(686, 150), "Straight along the firing direction.\nNo artificial downward curve.", 18)
	_label(Vector2(686, 232), "GRENADE", 23).modulate = colors["grenade"]
	_label(Vector2(686, 269), "Gravity carries it through the open mouth.\nIt bounces on the solid floor below.", 18)
	_label(Vector2(686, 350), "DROPPED GUN", 23).modulate = colors["dropped_gun"]
	_label(Vector2(686, 387), "Falls through both ladder landings.\nThin walls and ceilings still block it.", 18)
	_label(Vector2(686, 487), "20u opening / 16u ladder sensor\nMatching artwork and collision\nMirrored left and right entrances", 18)
	status = _label(Vector2(686, 610), "", 18)
	for frame: int in range(60):
		if frame == 6:
			pm.call("spawn_throwable", null, "GRENADE", Vector2(-296, -128), 90.0, 600.0)
			world.call("spawn_dropped_weapon", "PISTOL", Vector2(-300, -128), 12, Vector2.ZERO)
		pm.call("step_projectiles", STEP)
		world.call("_step_pickups", STEP)
		_record("bullet", pm.get("bullets") as Array, frame)
		_record("grenade", pm.get("throwables") as Array, frame)
		_record("dropped_gun", world.get("pickups") as Array, frame)
		status.text = "Simulation step %02d / 59\nTrace lines show recorded positions." % frame
		await process_frame
		if frame in [8, 28, 56]:
			await RenderingServer.frame_post_draw
			var img: Image = root.get_texture().get_image()
			if img == null or img.is_empty() or img.save_png(OUT + ("hatch_%03d.png" % frame)) != OK:
				failures += 1
	for key: String in ["grenade", "dropped_gun"]:
		var deepest: float = -INF
		for item: Dictionary in tracks[key]:
			deepest = maxf(deepest, float(item["y"]))
		if deepest <= -48.0:
			push_error("Object did not pass both open landings: " + key)
			failures += 1
	var bounced_on_floor: bool = false
	var previous_y: float = -INF
	for point: Dictionary in tracks["grenade"]:
		var y: float = float(point["y"])
		if previous_y >= 10.5 and previous_y <= 12.01 and y < previous_y - 0.05:
			bounced_on_floor = true
		previous_y = y
	if not bounced_on_floor:
		push_error("Grenade trace did not show reversal at the solid tower floor y=12")
		failures += 1
	for point: Dictionary in tracks["bullet"]:
		if absf(float(point["y"]) - (-132.0)) > 0.001:
			push_error("Horizontal bullet changed height")
			failures += 1
			break
	var report := {"schema": "chibi-r6.hatch-capture.v1", "seed": 6282026, "source_step": STEP, "fixture_only": true, "failures": failures, "trajectories": tracks}
	var file: FileAccess = FileAccess.open(OUT + "hatch_trajectories.json", FileAccess.WRITE)
	if file == null:
		failures += 1
	else:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	world.free()
	var audio: Node = root.get_node_or_null("AudioManager")
	if audio != null and not bool(await audio.call("stop_all_and_drain")):
		failures += 1
	await process_frame
	print("[CHIBI R6 HATCH CAPTURE] ", "PASS" if failures == 0 else "FAIL", " captures=3 failures=", failures)
	quit(0 if failures == 0 else 1)

func _record(key: String, items: Array, frame: int) -> void:
	if items.is_empty():
		return
	var pos: Vector2 = (items[0] as Dictionary)["pos"]
	(tracks[key] as Array).append({"frame": frame, "x": pos.x, "y": pos.y})
	(paths[key] as Line2D).add_point(pos)
