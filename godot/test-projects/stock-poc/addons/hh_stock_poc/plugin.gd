@tool
extends EditorPlugin

## Disposable R1-WP4 command plugin. Stock Godot Editor API + UndoRedo.
## Not MCP. Not hh_agent. Do not copy into godot/plugin-project/.

const NetScript: GDScript = preload("res://addons/hh_stock_poc/net.gd")
const OverlayScript: GDScript = preload("res://addons/hh_stock_poc/overlay.gd")
const DockScript: GDScript = preload("res://addons/hh_stock_poc/dock.gd")
const PLAYER_GROUP: String = "hh_stock_poc_player"
const MAIN_SCENE: String = "res://main.tscn"
const PLAYER_SCRIPT: String = "res://player.gd"
const TEMPLATE_SCRIPT: String = "res://addons/hh_stock_poc/templates/player_move.gd"
const PLACEHOLDER_PNG: String = "res://player_placeholder.png"
const EMPTY_SCENE: String = "[gd_scene format=3]\n\n[node name=\"Main\" type=\"Node2D\"]\n"

var _net: RefCounted
var _busy: bool = false
var _paused: bool = false
var _overlay: Control
var _dock: Control
var _session_token: String = ""


func _enter_tree() -> void:
	set_process(true)
	_install_ui()
	_maybe_listen()
	_note("plugin_enter")


func _exit_tree() -> void:
	if _overlay != null:
		remove_control_from_container(CONTAINER_CANVAS_EDITOR_BOTTOM, _overlay)
		_overlay.queue_free()
		_overlay = null
	if _dock != null:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
	if _net != null:
		_net.call("close")
		_net = null


func _process(_delta: float) -> void:
	if _net == null:
		return
	_net.call("poll_io")
	if _busy:
		return
	var item: Dictionary = _net.call("take_line")
	if item.is_empty():
		return
	_busy = true
	await _handle_line(item.get("peer"), str(item.get("line", "")))
	_busy = false


func _install_ui() -> void:
	_overlay = OverlayScript.new() as Control
	add_control_to_container(CONTAINER_CANVAS_EDITOR_BOTTOM, _overlay)
	_dock = DockScript.new() as Control
	add_control_to_dock(DOCK_SLOT_LEFT_UL, _dock)


func _maybe_listen() -> void:
	var port_s: String = OS.get_environment("HH_STOCK_POC_PORT")
	_session_token = OS.get_environment("HH_STOCK_POC_TOKEN")
	if port_s.is_empty():
		return
	if _session_token.is_empty():
		_write_listen({"error": "TOKEN_REQUIRED", "bind": "127.0.0.1"})
		return
	_net = NetScript.new()
	var want: int = int(port_s)
	var got: int = int(_net.call("listen_loopback", want))
	if got < 0:
		_write_listen({"error": "LISTEN_FAILED", "bind": "127.0.0.1"})
		_net = null
		return
	_write_listen({"bind": "127.0.0.1", "port": got})
	print("[hh_stock_poc] event=listen bind=127.0.0.1 port=%s" % got)


func _write_listen(payload: Dictionary) -> void:
	var out_dir: String = OS.get_environment("HH_STOCK_POC_OUT")
	if out_dir.is_empty():
		return
	var path: String = "%s/editor.listen.json" % out_dir
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return
	f.store_string(JSON.stringify(payload))
	f.flush()
	f.close()


func _note(text: String) -> void:
	print("[hh_stock_poc] event=%s" % text)
	if _overlay != null and _overlay.has_method("record"):
		_overlay.call("record", text)
	if _dock != null and _dock.has_method("record"):
		_dock.call("record", text)


func _handle_line(peer: StreamPeerTCP, line: String) -> void:
	var parsed: Variant = JSON.parse_string(line)
	if typeof(parsed) != TYPE_DICTIONARY:
		_reply(peer, {"status": "error", "code": "WRONG_SCHEMA", "message": "request must be a JSON object"})
		return
	var msg: Dictionary = parsed
	var req_id: String = str(msg.get("id", ""))
	var command: String = str(msg.get("command", ""))
	var command_id: String = str(msg.get("command_id", ""))
	var token: String = str(msg.get("token", ""))
	if token != _session_token:
		_reply(peer, {
			"id": req_id,
			"status": "error",
			"code": "AUTH_FAILED",
			"message": "missing or invalid session token",
			"command_id": command_id,
		})
		return
	var params: Variant = msg.get("params", {})
	if typeof(params) != TYPE_DICTIONARY:
		_reply(peer, {
			"id": req_id,
			"status": "error",
			"code": "WRONG_SCHEMA",
			"message": "params must be an object",
			"command_id": command_id,
		})
		return
	var mutating: bool = command in [
		"build_slice", "select_player", "save_scene", "reopen_scene", "setup_input_map"
	]
	if _paused and mutating:
		_reply(peer, {
			"id": req_id,
			"status": "error",
			"code": "PAUSED",
			"message": "mutating command refused while paused",
			"command_id": command_id,
		})
		return
	var result: Dictionary = await _dispatch(command, params, command_id)
	result["id"] = req_id
	result["command_id"] = command_id
	_reply(peer, result)
	if command == "quit":
		await get_tree().process_frame
		get_tree().quit()


func _reply(peer: StreamPeerTCP, payload: Dictionary) -> void:
	if _net == null or peer == null:
		return
	_net.call("send_line", peer, JSON.stringify(payload))


func _dispatch(command: String, params: Dictionary, command_id: String) -> Dictionary:
	match command:
		"ping":
			return _ok({"pong": true, "plugin": "hh_stock_poc", "paused": _paused})
		"pause":
			_paused = true
			_note("pause_ack")
			return _ok({"paused": true, "draining": true, "acked": true})
		"resume":
			_paused = false
			_note("resume")
			return _ok({"paused": false})
		"build_slice":
			return await _cmd_build_slice(command_id)
		"select_player":
			return _cmd_select_player()
		"save_scene":
			return _cmd_save_scene()
		"reopen_scene":
			return await _cmd_reopen_scene()
		"query_tree":
			return _cmd_query_tree()
		"quit":
			_note("quit")
			return _ok({"quit": true})
		_:
			return {
				"status": "error",
				"code": "UNKNOWN_COMMAND",
				"message": "unknown command",
				"command": command,
			}


func _ok(result: Dictionary) -> Dictionary:
	return {"status": "success", "result": result}


func _err(code: String, message: String) -> Dictionary:
	return {"status": "error", "code": code, "message": message}


func _cmd_build_slice(command_id: String) -> Dictionary:
	_note("build_slice")
	var opened: Dictionary = await _ensure_main_scene()
	if str(opened.get("status", "")) == "error":
		return opened
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return _err("NO_SCENE", "edited scene root is null")
	root.name = "Main"
	var player: Node = await _ensure_player(root, command_id)
	_ensure_floor(root, command_id)
	_ensure_hud(root, command_id)
	_setup_input_map()
	_set_main_scene_setting()
	var saved: Dictionary = _cmd_save_scene()
	var tree: Dictionary = _cmd_query_tree()
	var selected: Dictionary = _cmd_select_player()
	return _ok({
		"root": root.name,
		"player": str(player.get_path()) if player else "",
		"save": saved.get("result", {}),
		"tree": tree.get("result", {}),
		"select": selected.get("result", {}),
		"input_actions": _list_move_actions(),
		"main_scene": String(ProjectSettings.get_setting("application/run/main_scene")),
		"command_id": command_id,
		"overlay_hook": _overlay != null,
		"timeline_hook": _dock != null,
	})


func _ensure_main_scene() -> Dictionary:
	if not FileAccess.file_exists(MAIN_SCENE):
		var wr: Error = _atomic_write_text(MAIN_SCENE, EMPTY_SCENE)
		if wr != OK:
			return _err("WRITE_FAILED", "could not write empty main.tscn")
	var fs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	fs.update_file(MAIN_SCENE)
	await _wait_fs()
	EditorInterface.open_scene_from_path(MAIN_SCENE)
	var n: int = 0
	while EditorInterface.get_edited_scene_root() == null and n < 60:
		await get_tree().process_frame
		n += 1
	if EditorInterface.get_edited_scene_root() == null:
		return _err("OPEN_FAILED", "open_scene_from_path did not yield a root")
	return _ok({"opened": MAIN_SCENE})


func _ensure_player(root: Node, command_id: String) -> Node:
	var player: Node = _get_or_add(root, root, "Player", "CharacterBody2D", command_id)
	if player is Node2D:
		(player as Node2D).position = Vector2(80, 80)
	if player is CharacterBody2D:
		(player as CharacterBody2D).motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	player.add_to_group(PLAYER_GROUP, true)
	var sprite: Node = _get_or_add(player, root, "Sprite2D", "Sprite2D", command_id)
	if sprite is Sprite2D:
		(sprite as Sprite2D).texture = _make_placeholder_texture()
		(sprite as Sprite2D).centered = true
	var col: Node = _get_or_add(player, root, "CollisionShape2D", "CollisionShape2D", command_id)
	if col is CollisionShape2D:
		var shape: RectangleShape2D = RectangleShape2D.new()
		shape.size = Vector2(48, 48)
		(col as CollisionShape2D).shape = shape
	var cam: Node = _get_or_add(player, root, "Camera2D", "Camera2D", command_id)
	if cam is Camera2D:
		(cam as Camera2D).enabled = true
		(cam as Camera2D).make_current()
	await _attach_player_script(player)
	return player


func _ensure_floor(root: Node, command_id: String) -> void:
	var floor_n: Node = _get_or_add(root, root, "Floor", "StaticBody2D", command_id)
	if floor_n is Node2D:
		(floor_n as Node2D).position = Vector2(80, 200)
	var shape_n: Node = _get_or_add(floor_n, root, "FloorShape", "CollisionShape2D", command_id)
	if shape_n is CollisionShape2D:
		var shape: RectangleShape2D = RectangleShape2D.new()
		shape.size = Vector2(480, 24)
		(shape_n as CollisionShape2D).shape = shape


func _ensure_hud(root: Node, command_id: String) -> void:
	var hud: Node = _get_or_add(root, root, "Hud", "CanvasLayer", command_id)
	var label: Node = _get_or_add(hud, root, "StatusLabel", "Label", command_id)
	if label is Label:
		(label as Label).text = "HH R1-WP4 stock-poc"
		(label as Label).position = Vector2(12, 12)


func _attach_player_script(player: Node) -> void:
	if not FileAccess.file_exists(TEMPLATE_SCRIPT):
		return
	var src: String = FileAccess.get_file_as_string(TEMPLATE_SCRIPT)
	var wr: Error = _atomic_write_text(PLAYER_SCRIPT, src)
	if wr != OK:
		return
	var fs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	fs.update_file(PLAYER_SCRIPT)
	await _wait_fs()
	var script: Script = load(PLAYER_SCRIPT) as Script
	if script == null:
		return
	var ur: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	var previous: Variant = player.get_script()
	ur.create_action("HH Stock POC attach player script", UndoRedo.MERGE_DISABLE, player)
	ur.add_do_method(player, "set_script", script)
	ur.add_undo_method(player, "set_script", previous)
	ur.commit_action()


func _make_placeholder_texture() -> Texture2D:
	var img: Image = Image.create(48, 48, false, Image.FORMAT_RGBA8)
	for y: int in range(48):
		for x: int in range(48):
			var color: Color
			if x < 2 or x > 45 or y < 2 or y > 45:
				color = Color(0.05, 0.05, 0.08, 1.0)
			elif y < 16:
				color = Color(0.15, 0.9, 0.95, 1.0)
			else:
				color = Color(0.95, 0.15, 0.55, 1.0)
			img.set_pixel(x, y, color)
	img.save_png(PLACEHOLDER_PNG)
	return ImageTexture.create_from_image(img)


func _setup_input_map() -> void:
	_register_action("move_left", KEY_A)
	_register_action("move_right", KEY_D)
	_register_action("move_up", KEY_W)
	_register_action("move_down", KEY_S)
	ProjectSettings.save()
	_note("input_map")


func _register_action(action: String, keycode: Key) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	else:
		InputMap.action_erase_events(action)
	var ev: InputEventKey = InputEventKey.new()
	ev.keycode = keycode
	ev.physical_keycode = keycode
	InputMap.action_add_event(action, ev)
	var setting: Dictionary = {
		"deadzone": 0.5,
		"events": InputMap.action_get_events(action),
	}
	ProjectSettings.set_setting("input/%s" % action, setting)


func _list_move_actions() -> Array[String]:
	var names: Array[String] = ["move_left", "move_right", "move_up", "move_down"]
	var present: Array[String] = []
	for action: String in names:
		if InputMap.has_action(action):
			present.append(action)
	return present


func _set_main_scene_setting() -> void:
	ProjectSettings.set_setting("application/run/main_scene", MAIN_SCENE)
	ProjectSettings.save()


func _cmd_select_player() -> Dictionary:
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return _err("NO_SCENE", "no edited scene")
	var player: Node = root.find_child("Player", true, false)
	if player == null:
		return _err("NODE_NOT_FOUND", "Player missing")
	EditorInterface.set_main_screen_editor("2D")
	var selection: EditorSelection = EditorInterface.get_selection()
	selection.clear()
	selection.add_node(player)
	EditorInterface.edit_node(player)
	EditorInterface.inspect_object(player)
	_note("select_player")
	var selected_names: Array[String] = []
	for node: Node in selection.get_selected_nodes():
		selected_names.append(node.name)
	var inspected: Object = EditorInterface.get_inspector().get_edited_object()
	var inspected_name: String = ""
	if inspected is Node:
		inspected_name = (inspected as Node).name
	# Headless cannot show Inspector to a human (R4). API readback only.
	var headless: bool = DisplayServer.get_name() == "headless"
	return _ok({
		"selected": selected_names,
		"inspector_object": inspected_name,
		"inspector_visible_to_human": not headless,
		"inspector_gap": headless,
		"overlay_hook": _overlay != null,
	})


func _cmd_save_scene() -> Dictionary:
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return _err("NO_SCENE", "no edited scene to save")
	var err: Error = EditorInterface.save_scene()
	_note("save_scene")
	if err != OK:
		return _err("SAVE_FAILED", "save_scene error %s" % err)
	return _ok({
		"path": MAIN_SCENE,
		"exists": FileAccess.file_exists(MAIN_SCENE),
	})


func _cmd_reopen_scene() -> Dictionary:
	_note("reopen_scene")
	if not FileAccess.file_exists(MAIN_SCENE):
		return _err("FILE_NOT_FOUND", "main.tscn missing")
	EditorInterface.reload_scene_from_path(MAIN_SCENE)
	var n: int = 0
	while EditorInterface.get_edited_scene_root() == null and n < 60:
		await get_tree().process_frame
		n += 1
	if EditorInterface.get_edited_scene_root() == null:
		EditorInterface.open_scene_from_path(MAIN_SCENE)
		n = 0
		while EditorInterface.get_edited_scene_root() == null and n < 60:
			await get_tree().process_frame
			n += 1
	if EditorInterface.get_edited_scene_root() == null:
		return _err("OPEN_FAILED", "reopen did not yield a root")
	return _cmd_query_tree()


func _cmd_query_tree() -> Dictionary:
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return _err("NO_SCENE", "no edited scene")
	var nodes: Array[Dictionary] = []
	_collect_nodes(root, nodes)
	var dupes: Array[String] = []
	_collect_dupes(root, dupes)
	var names: Array[String] = []
	for row: Dictionary in nodes:
		names.append(str(row.get("name", "")))
	return _ok({
		"root": root.name,
		"root_type": root.get_class(),
		"count": nodes.size(),
		"nodes": nodes,
		"names": names,
		"duplicate_sibling_names": dupes,
		"has_player": root.find_child("Player", true, false) != null,
	})


func _collect_nodes(node: Node, acc: Array[Dictionary]) -> void:
	acc.append({
		"name": String(node.name),
		"type": node.get_class(),
		"path": str(node.get_path()),
	})
	for child: Node in node.get_children():
		_collect_nodes(child, acc)


func _collect_dupes(node: Node, found: Array[String]) -> void:
	var seen: Dictionary = {}
	for child: Node in node.get_children():
		var child_name: String = String(child.name)
		if seen.has(child_name):
			found.append(child_name)
		seen[child_name] = true
		_collect_dupes(child, found)


func _get_or_add(parent: Node, owner: Node, node_name: String, type_name: String, command_id: String) -> Node:
	var existing: Node = parent.get_node_or_null(NodePath(node_name))
	if existing != null:
		return existing
	var child: Node = ClassDB.instantiate(type_name) as Node
	if child == null:
		return null
	child.name = node_name
	var ur: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	ur.create_action("HH Stock POC [%s] add %s" % [command_id, node_name], UndoRedo.MERGE_DISABLE, owner)
	ur.add_do_method(self, "_do_add_owned", parent, child, owner)
	ur.add_undo_method(self, "_undo_add_owned", parent, child)
	ur.add_do_reference(child)
	ur.commit_action()
	return child


func _do_add_owned(parent: Node, child: Node, owner: Node) -> void:
	parent.add_child(child)
	child.owner = owner


func _undo_add_owned(parent: Node, child: Node) -> void:
	if child.get_parent() == parent:
		parent.remove_child(child)


func _atomic_write_text(res_path: String, text: String) -> Error:
	var abs_path: String = ProjectSettings.globalize_path(res_path).simplify_path()
	var root: String = ProjectSettings.globalize_path("res://").simplify_path()
	if not abs_path.begins_with(root):
		return ERR_FILE_BAD_PATH
	var tmp: String = abs_path + ".tmp"
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return FileAccess.get_open_error()
	f.store_string(text)
	f.flush()
	f.close()
	if FileAccess.file_exists(abs_path):
		DirAccess.remove_absolute(abs_path)
	return DirAccess.rename_absolute(tmp, abs_path)


func _wait_fs() -> void:
	var fs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	fs.scan()
	var n: int = 0
	while fs.is_scanning() and n < 180:
		await get_tree().process_frame
		n += 1
	var extra: int = 0
	while extra < 8:
		await get_tree().process_frame
		extra += 1
