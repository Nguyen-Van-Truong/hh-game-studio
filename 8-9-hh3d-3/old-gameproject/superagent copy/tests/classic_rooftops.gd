extends SceneTree
## Smoke checks for the classic Rooftops geometry port.  This verifies the
## live physics topology independently from the bitmap presentation.

const TRACE = preload("res://tests/trace_core.gd")
const MATCH = preload("res://game/core/match_session.gd")

var failures: int = 0
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var session := MATCH.new(909, &"two_player", &"vs", &"infinite", &"classic_rooftops")
	get_root().add_child(session)
	await process_frame
	await physics_frame
	_expect(session.phase == &"playing", "classic rooftops session starts")
	_expect(session.world.valid and session.world.width == 920.0 and session.world.height == 460.0, "classic stage dimensions are native bitmap space")
	_expect(session.world.floor_y == 400.0, "classic stage floor is aligned to Bitmap 2219 baseline")
	_expect(session.fighters[0].position == Vector2(94.0, 89.0) and session.fighters[1].position == Vector2(162.0, 89.0), "classic spawn pair comes from GenerateMapRooftops")
	_expect(session.world.ladder_at(194.0, 140.0), "classic ladder sensor is present")
	_expect(session.pickup_rows.size() == 5 and session.prop_rows.size() == 2, "classic room has authored item and prop rows")
	for tick_value: int in range(120):
		await physics_frame
		_expect(session.step(TRACE.build_frame(session.tick, {}, {})), "classic empty tick advances")
	_expect(session.fighters[0].grounded and session.fighters[1].grounded, "classic spawns settle on rooftop geometry")
	_expect(session.fighters[0].position.y < 401.0 and session.fighters[1].position.y < 401.0, "classic fighters remain above the pit")
	session.queue_free()
	await process_frame
	if failures == 0:
		print("Classic Rooftops PASS: %d assertions; GenerateMapRooftops geometry and live settling" % assertions)
	else:
		printerr("Classic Rooftops FAIL: %d of %d assertions" % [failures, assertions])
	quit(0 if failures == 0 else 1)

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		printerr("FAIL: %s" % message)
