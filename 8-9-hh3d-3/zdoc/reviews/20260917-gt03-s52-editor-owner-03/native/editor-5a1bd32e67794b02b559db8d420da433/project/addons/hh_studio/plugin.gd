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
	call_deferred("_ipc_start")


func _exit_tree() -> void:
	if _ipc != null:
		_ipc.disconnect_from_host()
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
	if _commands == null or not is_instance_valid(_bound_root) or _bound_root != EditorInterface.get_edited_scene_root():
		return {"ok": false, "code": "EDITOR_SCENE_UNBOUND"}
	return _commands.preview(projection)


func apply_projection(projection: Dictionary) -> Dictionary:
	if OS.get_thread_caller_id() != OS.get_main_thread_id():
		return {"ok": false, "code": "EDITOR_MAIN_THREAD_REQUIRED"}
	if _commands == null or not is_instance_valid(_bound_root) or _bound_root != EditorInterface.get_edited_scene_root():
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


# Fixed internal bridge, enabled only by the owned editor launch environment.
# This channel authenticates the host/editor pair, not a user's publication grant.
const IPC_LIMIT: int = 1572864
const INPUT_PATHS: Array[String] = ["addons/hh_studio/jcs_godot.gd", "addons/hh_studio/jcs_godot.gd.uid",
	"addons/hh_studio/plugin.cfg", "addons/hh_studio/plugin.gd", "addons/hh_studio/plugin.gd.uid",
	"addons/hh_studio/scene_commands.gd", "addons/hh_studio/scene_commands.gd.uid", "project.godot",
	"scenes/fixture.tscn", "scripts/fixture_actor.gd", "scripts/fixture_actor.gd.uid"]
var _ipc: StreamPeerTCP
var _ipc_rx: PackedByteArray = PackedByteArray()
var _ipc_tx: PackedByteArray = PackedByteArray()
var _ipc_session: String = ""
var _ipc_token: String = ""
var _ipc_scratch: String = ""
var _ipc_hello: bool = false
var _ipc_sequence: int = 0
var _ipc_stopped: bool = false
var _ipc_prepared: Dictionary = {}
var _ipc_adopting: Dictionary = {}
var _ipc_used: Dictionary = {}


func _ipc_start() -> void:
	_ipc_token = OS.get_environment("HH_EDITOR_TOKEN")
	if _ipc_token.is_empty():
		return
	_ipc_session = OS.get_environment("HH_EDITOR_SESSION")
	_ipc_scratch = OS.get_environment("HH_EDITOR_SCRATCH")
	var port: int = OS.get_environment("HH_EDITOR_PORT").to_int()
	OS.unset_environment("HH_EDITOR_TOKEN")
	if _ipc_token.length() != 64 or _ipc_session.length() != 39 or not _ipc_scratch.is_absolute_path() or port < 1024 or port > 65535:
		_ipc_abort()
		return
	_ipc = StreamPeerTCP.new()
	if _ipc.connect_to_host("127.0.0.1", port) != OK:
		_ipc_abort()
	set_process(true)


func _ipc_abort() -> void:
	_ipc_stopped = true
	_ipc_prepared.clear()
	if _ipc != null:
		_ipc.disconnect_from_host()
	get_tree().quit(72)


func _ipc_queue(value: Dictionary) -> void:
	var raw: PackedByteArray = (JSON.stringify(value, "", true, true) + "\n").to_utf8_buffer()
	if raw.size() > IPC_LIMIT or _ipc_tx.size() + raw.size() > IPC_LIMIT:
		_ipc_abort()
		return
	_ipc_tx.append_array(raw)


func _process(_delta: float) -> void:
	if _ipc == null:
		return
	_ipc.poll()
	if _ipc.get_status() == StreamPeerTCP.STATUS_CONNECTING:
		return
	if _ipc.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		_ipc_abort()
		return
	if not _ipc_hello:
		_ipc_hello = true
		_ipc_queue({"kind": "hello", "token": _ipc_token, "editor_session_id": _ipc_session,
			"pid": OS.get_process_id(), "project_root": ProjectSettings.globalize_path("res://"),
			"editor_hint": Engine.is_editor_hint(), "main_thread": OS.get_thread_caller_id() == OS.get_main_thread_id(),
			"version": Engine.get_version_info().string})
		_ipc_token = ""
	if not _ipc_tx.is_empty():
		var sent: Array = _ipc.put_partial_data(_ipc_tx.slice(0, mini(65536, _ipc_tx.size())))
		if sent[0] != OK:
			_ipc_abort()
			return
		_ipc_tx = _ipc_tx.slice(int(sent[1]))
	var available: int = mini(_ipc.get_available_bytes(), 65536)
	if available > 0:
		var received: Array = _ipc.get_partial_data(available)
		if received[0] != OK:
			_ipc_abort()
			return
		_ipc_rx.append_array(received[1])
	if _ipc_rx.size() > IPC_LIMIT:
		_ipc_abort()
		return
	var newline: int = _ipc_rx.find(10)
	if newline >= 0:
		var decoded: Variant = JSON.parse_string(_ipc_rx.slice(0, newline).get_string_from_utf8())
		_ipc_rx = _ipc_rx.slice(newline + 1)
		if not decoded is Dictionary:
			_ipc_abort()
			return
		_ipc_dispatch(decoded)
	if not _ipc_adopting.is_empty():
		_ipc_finish_adoption()


func _ipc_reply(sequence: int, result: Dictionary) -> void:
	_ipc_queue({"sequence": sequence, "editor_session_id": _ipc_session, "result": result})


func _ipc_files() -> Dictionary:
	var rows: Dictionary = {}
	var total: int = 0
	for path: String in INPUT_PATHS:
		var file: FileAccess = FileAccess.open("res://" + path, FileAccess.READ)
		if file == null:
			return {}
		var size: int = file.get_length()
		file.close()
		total += size
		if size <= 0 or size > 1048576 or total > 2097152:
			return {}
		rows[path] = {"sha256": FileAccess.get_sha256("res://" + path), "size_bytes": size}
	return rows


func _ipc_snapshot() -> Dictionary:
	var value: Dictionary = inspect_scene()
	if not value.get("ok", false):
		return value
	var history: UndoRedo = get_undo_redo().get_history_undo_redo(int(value.history_id))
	value["editor_session_id"] = _ipc_session
	value["root_instance_id"] = str(_bound_root.get_instance_id())
	value["scene_path"] = _bound_root.scene_file_path
	value["working_files"] = _ipc_files()
	value["can_undo"] = history != null and history.has_undo()
	value["can_redo"] = history != null and history.has_redo()
	if value.working_files.size() != INPUT_PATHS.size():
		return {"ok": false, "code": "EDITOR_INPUT_FILES"}
	return value


func _ipc_dispatch(message: Dictionary) -> void:
	if message.keys().size() != 4 or not message.has_all(["sequence", "editor_session_id", "kind", "body"]):
		_ipc_abort()
		return
	if message.editor_session_id != _ipc_session or not message.body is Dictionary or not _ipc_integer(message.sequence) or int(message.sequence) != _ipc_sequence + 1 or _ipc_sequence >= 128:
		_ipc_abort()
		return
	_ipc_sequence += 1
	var body: Dictionary = message.body
	if message.kind == "stop":
		_ipc_stopped = true
		_ipc_prepared.clear()
		_ipc_reply(_ipc_sequence, {"ok": true, "code": "EDITOR_STOPPED"})
		return
	if message.kind == "close":
		_ipc_stopped = true
		get_tree().quit(0)
		return
	if not _ipc_adopting.is_empty():
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPTION_PENDING"})
		return
	if message.kind == "inspect" and body.is_empty():
		_ipc_reply(_ipc_sequence, _ipc_snapshot())
		return
	if _ipc_stopped:
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_STOPPED"})
		return
	if message.kind == "projection" and body.keys() == ["projection"]:
		_ipc_reply(_ipc_sequence, apply_projection(body.projection))
		return
	if message.kind == "prepare":
		var required: Array[String] = ["intent_id", "command_id", "request_digest", "kind", "expected_generation", "expected_revision", "deadline_ms"]
		if body.size() != required.size() or not body.has_all(required) or body.kind not in ["capture", "adopt"] or not _ipc_prepared.is_empty() or _ipc_used.has(body.intent_id) or not _ipc_hex(body.intent_id, 32) or not body.command_id is String or not body.request_digest is String or not body.expected_revision is String or not _ipc_integer(body.expected_generation) or not _ipc_integer(body.deadline_ms) or _ipc_used.size() >= 16:
			_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_INTENT_SHAPE"})
			return
		var before: Dictionary = _ipc_snapshot()
		if not _ipc_precondition(before, body):
			_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_STALE_PRECONDITION"})
			return
		_ipc_prepared = {"intent": body.duplicate(true), "before": before}
		_ipc_reply(_ipc_sequence, {"ok": true, "code": "EDITOR_PREPARED", "before": before})
		return
	if message.kind == "consume":
		_ipc_consume(body)
		return
	_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_OPERATION_FORBIDDEN"})


func _ipc_integer(value: Variant) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value)) and value == int(value) and absf(float(value)) < 9007199254740992.0


func _ipc_hex(value: Variant, length: int) -> bool:
	if not value is String or value.length() != length:
		return false
	for character: String in value:
		if not character in "0123456789abcdef":
			return false
	return true


func _ipc_precondition(snapshot: Dictionary, intent: Dictionary) -> bool:
	var now: int = int(Time.get_unix_time_from_system() * 1000.0)
	return snapshot.get("ok", false) and OS.get_thread_caller_id() == OS.get_main_thread_id() and Engine.is_editor_hint() and snapshot.editor_session_id == _ipc_session and snapshot.scene_path == "res://scenes/fixture.tscn" and snapshot.generation == intent.expected_generation and snapshot.revision == intent.expected_revision and now < intent.deadline_ms and intent.deadline_ms <= now + 30000


func _ipc_consume(body: Dictionary) -> void:
	if _ipc_prepared.is_empty() or body.get("intent_id", "") != _ipc_prepared.intent.intent_id:
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_INTENT_NOT_REGISTERED"})
		return
	var prepared: Dictionary = _ipc_prepared
	_ipc_prepared = {}
	_ipc_used[prepared.intent.intent_id] = true
	var before: Dictionary = _ipc_snapshot()
	if not _ipc_precondition(before, prepared.intent) or before.get("root_instance_id") != prepared.before.root_instance_id or before.get("working_files") != prepared.before.working_files:
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_STALE_PRECONDITION"})
		return
	# No await between the final main-thread guard and fixed native effect.
	var started_ms: int = int(Time.get_unix_time_from_system() * 1000.0)
	if prepared.intent.kind == "capture" and body.size() == 1:
		var path: String = _ipc_scratch.path_join("capture-" + str(body.intent_id) + ".tscn")
		if FileAccess.file_exists(path):
			_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_CAPTURE_EXISTS"})
			return
		var packed := PackedScene.new()
		if packed.pack(_bound_root) != OK or ResourceSaver.save(packed, path) != OK:
			_ipc_stopped = true
			_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_CAPTURE_UNKNOWN"})
			return
		var after: Dictionary = _ipc_snapshot()
		_ipc_reply(_ipc_sequence, {"ok": true, "code": "EDITOR_CAPTURED", "before": before, "after": after,
			"scene_sha256": FileAccess.get_sha256(path), "effect_started_ms": started_ms,
			"effect_completed_ms": int(Time.get_unix_time_from_system() * 1000.0)})
		return
	if prepared.intent.kind != "adopt" or body.size() != 4 or not body.has_all(["intent_id", "scene_base64", "scene_sha256", "expected_semantic_revision"]):
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPT_SHAPE"})
		return
	var raw: PackedByteArray = Marshalls.base64_to_raw(body.scene_base64)
	var hasher := HashingContext.new()
	hasher.start(HashingContext.HASH_SHA256)
	hasher.update(raw)
	if raw.is_empty() or raw.size() > 1048576 or hasher.finish().hex_encode() != body.scene_sha256:
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPT_BYTES"})
		return
	var stage: String = "res://scenes/.hh-adopt-" + str(body.intent_id) + ".tscn"
	if FileAccess.file_exists(stage):
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPT_EXISTS"})
		return
	var file: FileAccess = FileAccess.open(stage, FileAccess.WRITE)
	if file == null:
		_ipc_stopped = true
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPT_UNKNOWN"})
		return
	file.store_buffer(raw)
	file.flush()
	file.close()
	if FileAccess.get_sha256(stage) != body.scene_sha256 or DirAccess.rename_absolute(stage, "res://scenes/fixture.tscn") != OK:
		_ipc_stopped = true
		_ipc_reply(_ipc_sequence, {"ok": false, "code": "EDITOR_ADOPT_UNKNOWN"})
		return
	get_undo_redo().clear_history(int(before.history_id), false)
	_ipc_adopting = {"sequence": _ipc_sequence, "before": before, "scene_sha256": body.scene_sha256,
		"expected_revision": body.expected_semantic_revision, "effect_started_ms": started_ms, "frames": 0}
	EditorInterface.reload_scene_from_path("res://scenes/fixture.tscn")


func _ipc_finish_adoption() -> void:
	_ipc_adopting.frames += 1
	var after: Dictionary = _ipc_snapshot()
	if after.get("ok", false) and after.generation > _ipc_adopting.before.generation and after.root_instance_id != _ipc_adopting.before.root_instance_id:
		var good: bool = after.revision == _ipc_adopting.expected_revision and after.working_files["scenes/fixture.tscn"].sha256 == _ipc_adopting.scene_sha256 and not after.can_undo and not after.can_redo
		_ipc_reply(int(_ipc_adopting.sequence), {"ok": good, "code": "EDITOR_ADOPTED" if good else "EDITOR_ADOPT_READBACK_MISMATCH",
			"before": _ipc_adopting.before, "after": after, "effect_started_ms": _ipc_adopting.effect_started_ms,
			"effect_completed_ms": int(Time.get_unix_time_from_system() * 1000.0), "history_boundary": true})
		_ipc_adopting.clear()
		if not good:
			_ipc_stopped = true
	elif _ipc_adopting.frames >= 180:
		_ipc_reply(int(_ipc_adopting.sequence), {"ok": false, "code": "EDITOR_ADOPT_TIMEOUT"})
		_ipc_adopting.clear()
		_ipc_stopped = true
