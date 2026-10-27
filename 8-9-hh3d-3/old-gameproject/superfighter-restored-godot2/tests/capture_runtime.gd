extends SceneTree

const GameScript = preload("res://game/ui/main.gd")

func _init() -> void:
	call_deferred("_capture")

func _capture() -> void:
	var game: VaultGame = GameScript.new()
	root.add_child(game)
	await process_frame
	game._start_match()
	for _index: int in range(12):
		await process_frame
	var image := get_root().get_texture().get_image()
	image.save_png("res://evidence/RR-WP10/runtime-match.png")
	print("RR_RUNTIME_CAPTURE path=evidence/RR-WP10/runtime-match.png size=%dx%d" % [image.get_width(), image.get_height()])
	quit(0)
