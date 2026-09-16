@tool
extends EditorPlugin
## Internal editor adapter. A trusted host must validate/authenticate the shared
## envelope before supplying a projection. No public transport or save ACK here.

const SceneCommands = preload("res://addons/hh_studio/scene_commands.gd")

signal adapter_ready(snapshot: Dictionary)

var _commands: SceneCommands
var _bound_root: Node3D
var _generation: int = 0
var _last_bind: Dictionary = {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}


func _enter_tree() -> void:
	if not scene_changed.is_connected(_scene_changed):
		scene_changed.connect(_scene_changed)
	call_deferred("_bind_current")


func _exit_tree() -> void:
	if scene_changed.is_connected(_scene_changed):
		scene_changed.disconnect(_scene_changed)
	_commands = null
	_bound_root = null


func _scene_changed(_scene: Node) -> void:
	_bind_current()


func _bind_current() -> void:
	var current: Node = EditorInterface.get_edited_scene_root()
	if current == _bound_root and _commands != null:
		return
	_commands = null
	_bound_root = null
	if current == null or not current is Node3D:
		_last_bind = {"ok": false, "code": "EDITOR_APPROVED_SCENE_REQUIRED"}
		return
	_generation += 1
	_bound_root = current as Node3D
	_commands = SceneCommands.new()
	_last_bind = _commands.initialize(_bound_root, get_undo_redo(), _generation)
	adapter_ready.emit(_last_bind.duplicate(true))


func inspect_scene(offset: int = 0, limit: int = 64) -> Dictionary:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return {"ok": false, "code": "EDITOR_MAIN_THREAD_REQUIRED"}
	if _commands == null or not is_instance_valid(_bound_root):
		return {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}
	if _bound_root != EditorInterface.get_edited_scene_root():
		return {"ok": false, "code": "EDITOR_SCENE_RELOADED"}
	return _commands.inspect(offset, limit)


func preview_projection(projection: Dictionary) -> Dictionary:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return {"ok": false, "code": "EDITOR_MAIN_THREAD_REQUIRED"}
	if _commands == null or _bound_root != EditorInterface.get_edited_scene_root():
		return {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}
	return _commands.preview(projection)


func apply_projection(projection: Dictionary) -> Dictionary:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return {"ok": false, "code": "EDITOR_MAIN_THREAD_REQUIRED"}
	if _commands == null or _bound_root != EditorInterface.get_edited_scene_root():
		return {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}
	# Match fixed operations only; never call a request-provided method name.
	match projection.get("operation", ""):
		"scene.node.create", "scene.node.update", "scene.node.remove":
			return _commands.apply(projection)
		"scene.undo":
			return _commands.undo(projection)
		"scene.redo":
			return _commands.redo(projection)
		_:
			return {"ok": false, "code": "EDITOR_OPERATION_NOT_IMPLEMENTED"}


func transition_result() -> Dictionary:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return {"ok": false, "code": "EDITOR_MAIN_THREAD_REQUIRED"}
	return _commands.last_transition() if _commands != null else {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}
