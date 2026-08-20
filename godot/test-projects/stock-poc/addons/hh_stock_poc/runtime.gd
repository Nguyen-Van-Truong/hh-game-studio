extends Node

## Game-process playtest (A11). Does nothing in the editor.
## Injects a fixed input timeline, records position delta, attempts a screenshot.

const PLAYER_GROUP: String = "hh_stock_poc_player"
const INJECT_FRAMES: int = 30

var _playtest: bool = false
var _frame: int = 0
var _player: CharacterBody2D
var _pos0: Vector2 = Vector2.ZERO
var _pos1: Vector2 = Vector2.ZERO
var _done: bool = false
var _settling: bool = false


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	if OS.get_environment("HH_STOCK_POC_PLAYTEST") != "1":
		return
	_playtest = true
	print("[hh_stock_poc] event=runtime_ready")


func _physics_process(_delta: float) -> void:
	if not _playtest or _done:
		return
	_frame += 1
	if _player == null:
		_player = _find_player()
		if _player == null:
			if _frame >= 120:
				_finish(false, "player_not_found")
			return
	if _frame == 8:
		_pos0 = _player.global_position
		Input.action_press("move_right")
		print("[hh_stock_poc] event=inject action=move_right")
		return
	if _frame == 8 + INJECT_FRAMES:
		Input.action_release("move_right")
		_pos1 = _player.global_position
		_settling = true
		return
	if _settling and _frame >= 8 + INJECT_FRAMES + 6:
		_finish(true, "ok")


func _find_player() -> CharacterBody2D:
	var grouped: Array[Node] = get_tree().get_nodes_in_group(PLAYER_GROUP)
	if not grouped.is_empty():
		return grouped[0] as CharacterBody2D
	var found: Node = get_tree().get_root().find_child("Player", true, false)
	return found as CharacterBody2D


func _finish(ok: bool, reason: String) -> void:
	if _done:
		return
	_done = true
	if InputMap.has_action("move_right"):
		Input.action_release("move_right")
	var dx: float = _pos1.x - _pos0.x
	var dy: float = _pos1.y - _pos0.y
	print("[hh_stock_poc] event=playtest_done ok=%s reason=%s dx=%s dy=%s" % [ok, reason, dx, dy])
	var shot: Dictionary = _capture_screenshot()
	_write_play_json(ok, reason, dx, dy, shot)
	get_tree().quit()


func _capture_screenshot() -> Dictionary:
	var out_dir: String = OS.get_environment("HH_STOCK_POC_OUT")
	var result: Dictionary = {
		"attempted": true,
		"path": "",
		"width": 0,
		"height": 0,
		"bytes": 0,
		"reason": "",
	}
	if out_dir.is_empty():
		result["reason"] = "HH_STOCK_POC_OUT unset"
		return result
	var vp: Viewport = get_viewport()
	if vp == null:
		result["reason"] = "no_viewport"
		return result
	var tex: ViewportTexture = vp.get_texture()
	if tex == null:
		result["reason"] = "no_viewport_texture"
		return result
	var img: Image = tex.get_image()
	if img == null:
		result["reason"] = "no_image"
		return result
	var path: String = "%s/screenshot.png" % out_dir
	var err: Error = img.save_png(path)
	if err != OK:
		result["reason"] = "save_png_failed"
		return result
	result["path"] = path
	result["width"] = img.get_width()
	result["height"] = img.get_height()
	if FileAccess.file_exists(path):
		result["bytes"] = FileAccess.get_file_as_bytes(path).size()
	result["reason"] = "wrote"
	print("[hh_stock_poc] event=screenshot width=%s height=%s bytes=%s" % [result["width"], result["height"], result["bytes"]])
	return result


func _write_play_json(ok: bool, reason: String, dx: float, dy: float, shot: Dictionary) -> void:
	var out_dir: String = OS.get_environment("HH_STOCK_POC_OUT")
	if out_dir.is_empty():
		return
	var payload: Dictionary = {
		"ok": ok,
		"reason": reason,
		"pos0": {"x": _pos0.x, "y": _pos0.y},
		"pos1": {"x": _pos1.x, "y": _pos1.y},
		"delta": {"x": dx, "y": dy},
		"inject_frames": INJECT_FRAMES,
		"screenshot": shot,
	}
	var path: String = "%s/play.json" % out_dir
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		print("[hh_stock_poc] event=play_json_failed")
		return
	f.store_string(JSON.stringify(payload))
	f.flush()
	f.close()
	print("[hh_stock_poc] event=play_json_wrote")
