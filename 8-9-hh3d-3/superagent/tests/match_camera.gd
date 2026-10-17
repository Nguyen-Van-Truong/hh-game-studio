extends SceneTree
## Presentation fixture coverage, not an E2E or reference-parity claim.
## F6 must never become a simulation input or change a frozen match snapshot.

var _assertions: int = 0
var _failures: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	change_scene_to_file("res://game/ui/match_room.tscn")
	await process_frame
	await process_frame
	var room := current_scene as MatchRoom
	_expect(room != null, "match scene loads")
	if room == null:
		quit(1)
		return
	room.set_physics_process(false)
	var camera: Camera2D = room.get_node("MatchCamera") as Camera2D
	var before: Dictionary = room.read_snapshot()
	var before_text: String = JSON.stringify(before)
	var full_zoom: Vector2 = camera.zoom
	_press_camera_key(true)
	await process_frame
	_press_camera_key(false)
	await process_frame
	_expect(bool(room.get("_camera_near")), "F6 activates detail framing through SceneTree input")
	_expect(JSON.stringify(room.read_snapshot()) == before_text, "camera toggle leaves the frozen simulation snapshot unchanged")
	_expect(camera.zoom.is_equal_approx(full_zoom), "far opening spawns retain full-map zoom")
	_expect_fighters_visible(room, camera, "opening")
	room.simulation.place_fighter(0, Vector2(580.0, 740.0))
	room.simulation.place_fighter(1, Vector2(980.0, 740.0))
	room.call("_update_presentation")
	var close_before: String = JSON.stringify(room.read_snapshot())
	_expect(camera.zoom.x > full_zoom.x, "nearby fighters enable bounded detail zoom")
	_expect_fighters_visible(room, camera, "close ground")
	_press_camera_key(true)
	await process_frame
	_press_camera_key(false)
	await process_frame
	_expect(not bool(room.get("_camera_near")), "F6 restores full-map framing")
	_expect(camera.zoom.is_equal_approx(full_zoom), "restored full-map zoom matches baseline")
	_expect(JSON.stringify(room.read_snapshot()) == close_before, "restoring full framing leaves simulation snapshot unchanged")
	room.queue_free()
	await process_frame
	if _failures == 0:
		print("SA-10 match camera PASS: %d assertions; input toggle, framing and immutable snapshot" % _assertions)
	else:
		printerr("SA-10 match camera FAIL: %d of %d assertions" % [_failures, _assertions])
	quit(0 if _failures == 0 else 1)

func _expect_fighters_visible(room: MatchRoom, camera: Camera2D, label: String) -> void:
	var viewport_size: Vector2 = room.get_viewport_rect().size
	var fighters: Array = room.read_snapshot().get(&"fighters", [])
	for fighter: Dictionary in fighters:
		var feet := Vector2(float(fighter[&"x"]), float(fighter[&"y"]))
		var screen_feet: Vector2 = (feet - camera.position) * camera.zoom + viewport_size * 0.5
		var screen_head: Vector2 = screen_feet - Vector2(0.0, 60.0 * camera.zoom.y)
		_expect(screen_feet.x >= 28.0 and screen_feet.x <= viewport_size.x - 28.0, "%s fighter has horizontal edge clearance" % label)
		_expect(screen_head.y >= 200.0 and screen_feet.y <= viewport_size.y - 104.0, "%s fighter fits between HUD and controls" % label)

func _press_camera_key(pressed: bool) -> void:
	var event := InputEventKey.new()
	event.keycode = KEY_F6
	event.pressed = pressed
	Input.parse_input_event(event)

func _expect(condition: bool, message: String) -> void:
	_assertions += 1
	if not condition:
		_failures += 1
		printerr("FAIL: %s" % message)
