extends SceneTree

const MAP_SCRIPT = preload("res://game/world/map_catalog.gd")
var assertions: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scenes: Dictionary = {
		&"vs": "res://game/ui/match_room.tscn",
		&"stage": "res://game/ui/match_room_stage.tscn",
		&"survival": "res://game/ui/match_room_survival.tscn",
	}
	for entry: Dictionary in MAP_SCRIPT.entries():
		var map_id: StringName = StringName(entry[&"id"])
		for mode: StringName in scenes.keys():
			set_meta(&"superagent_map_id", map_id)
			change_scene_to_file(String(scenes[mode]))
			var ready: bool = await _wait_for_scene(&"MatchRoom")
			_expect(ready and current_scene != null, "scene loads for %s/%s" % [String(mode), String(map_id)])
			if not ready or current_scene == null:
				continue
			var room: MatchRoom = current_scene as MatchRoom
			_expect(room != null and room.simulation != null and room.simulation.phase == &"playing", "live session starts for %s/%s" % [String(mode), String(map_id)])
			if room != null and room.simulation != null:
				await physics_frame
				_expect(room.simulation.map_id == map_id and room.simulation.world.valid, "live session retains map for %s/%s" % [String(mode), String(map_id)])
	print("SA-09 live map mode matrix PASS: %d assertions" % assertions)
	quit()

func _wait_for_scene(expected: StringName) -> bool:
	for _attempt: int in range(120):
		if current_scene != null and StringName(current_scene.name) == expected:
			return true
		await process_frame
	return false

func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		push_error("FAIL: " + message)
		quit(1)
