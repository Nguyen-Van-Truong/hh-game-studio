class_name HHAgentAudioAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")

## Typed Godot 4.7.1 AudioStreamPlayer / AudioServer verbs (editor assignment).
## Stream is AudioStreamGenerator only. Never invent dummy WAV/OGG bytes.
## Do not call play() as heard-SFX proof. playing==true is not heard.
## Bus persist = generate_bus_layout + ResourceSaver AudioBusLayout +
## ProjectSettings audio/buses/default_bus_layout. RAM-only bus is not durable.
## Isolate r5w6 layout and restore. Catalog: register in actions.json.
## Generated plugin-validator.json / mcp-tools.json are coordinator-owned
## (`npm run generate`). Honest Alternative: heard SFX is deferred R6.

const BUS_SETTING: String = "audio/buses/default_bus_layout"
const LICENSE_GENERATOR: String = "AudioStreamGenerator builtin"

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


class PlayerStroke:
	extends RefCounted
	var player: Node
	var old_stream: AudioStream
	var new_stream: AudioStream
	var old_bus: String = ""
	var new_bus: String = ""
	var old_volume: float = 0.0
	var new_volume: float = 0.0

	func apply() -> void:
		if player == null:
			return
		HHAgentAudioAdapter._write_player(player, new_stream, new_bus, new_volume)

	func revert() -> void:
		if player == null:
			return
		HHAgentAudioAdapter._write_player(player, old_stream, old_bus, old_volume)


class BusStroke:
	extends RefCounted
	var old_layout: AudioBusLayout
	var new_layout: AudioBusLayout

	func apply() -> void:
		if new_layout != null:
			AudioServer.set_bus_layout(new_layout)

	func revert() -> void:
		if old_layout != null:
			AudioServer.set_bus_layout(old_layout)


func handles(action: String) -> bool:
	return action == "player" or action == "bus" or action == "preview"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.audio" or not handles(action):
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an audio verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "player":
		return _player(command_id, params, precondition, post)
	if action == "bus":
		return _bus(command_id, params, post)
	if action == "preview":
		return _preview(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "audio.%s is not a proven verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "player":
		return "audio_player_stream_bus_matches"
	if action == "bus":
		return "audio_bus_layout_matches"
	if action == "preview":
		return "audio_preview_editor_only"
	return "audio_verb"


func _player(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null:
		return _unverified(command_id, "AudioStreamPlayer not found")
	if not (node is AudioStreamPlayer) and not (node is AudioStreamPlayer2D):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			"audio.player requires AudioStreamPlayer or AudioStreamPlayer2D",
			"params.node_path",
		)
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var stream_path: String = str(params.get("stream", ""))
	if stream_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only audio durable ACK")
	var stream_hold: Dictionary = _ensure_generator(command_id, stream_path)
	if stream_hold.get("ok", false) != true:
		return stream_hold
	var stream: AudioStreamGenerator = stream_hold.get("stream") as AudioStreamGenerator
	var stroke: PlayerStroke = PlayerStroke.new()
	stroke.player = node
	stroke.old_stream = _player_stream(node)
	stroke.new_stream = stream
	stroke.old_bus = _player_bus(node)
	stroke.new_bus = str(params.get("bus", stroke.old_bus))
	stroke.old_volume = _player_volume(node)
	stroke.new_volume = float(params.get("volume_db", stroke.old_volume))
	var action_name: String = "%saudio.player %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, node.get_class()]
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var live_stream: AudioStream = _player_stream(node)
	if live_stream == null or not (live_stream is AudioStreamGenerator):
		return _unverified(command_id, "AudioStreamGenerator assign readback missing")
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if _is_external_res(stream_path):
		persisted = _persist_res(command_id, live_stream, stream_path)
		if persisted.get("ok", false) != true:
			return persisted
	_meta.mark_dirty(str(params.get("scene", "")))
	var after: Dictionary = _audio_after(edited, params, node)
	after["stream"] = stream_path
	after["stream_class"] = live_stream.get_class()
	after["bus"] = _player_bus(node)
	after["volume_db"] = _player_volume(node)
	after["license"] = LICENSE_GENERATOR
	after["heard"] = false
	after["playing"] = _player_playing(node)
	after["disk_hash"] = str(persisted.get("disk_hash", ""))
	after["durable"] = _is_external_res(stream_path)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _bus(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var bus_name: String = str(params.get("bus", ""))
	if bus_name.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "bus name required", "params.bus")
	var layout_path: String = str(params.get("layout", ""))
	var restore_path: String = str(params.get("restore_layout", ""))
	if layout_path.contains("::") or restore_path.contains("::"):
		return _unverified(command_id, "refusing RAM-only audio durable ACK")
	if params.get("restore", false) == true:
		return _restore_layout(command_id, params, post)
	var previous_setting: String = str(ProjectSettings.get_setting(BUS_SETTING, ""))
	var old_layout: AudioBusLayout = AudioServer.generate_bus_layout()
	if params.get("isolate", false) == true:
		if restore_path.is_empty():
			return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "isolate requires restore_layout", "params.restore_layout")
		var snap: Dictionary = _persist_res(command_id, old_layout, restore_path)
		if snap.get("ok", false) != true:
			return snap
	var idx: int = AudioServer.get_bus_index(bus_name)
	if idx < 0:
		if params.get("add", true) != true:
			return _unverified(command_id, "bus %s not found" % bus_name)
		AudioServer.add_bus()
		idx = AudioServer.get_bus_count() - 1
		AudioServer.set_bus_name(idx, bus_name)
		AudioServer.set_bus_send(idx, str(params.get("send", "Master")))
	else:
		if params.has("send"):
			AudioServer.set_bus_send(idx, str(params.get("send", "Master")))
	idx = AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return _unverified(command_id, "bus index missing after add")
	if params.has("mute"):
		AudioServer.set_bus_mute(idx, params.get("mute") == true)
	if params.has("volume_db"):
		AudioServer.set_bus_volume_db(idx, float(params.get("volume_db", 0.0)))
	var live_idx: int = AudioServer.get_bus_index(bus_name)
	if live_idx < 0:
		return _unverified(command_id, "bus index missing after mutate")
	var new_layout: AudioBusLayout = AudioServer.generate_bus_layout()
	var stroke: BusStroke = BusStroke.new()
	stroke.old_layout = old_layout
	stroke.new_layout = new_layout
	var edited: Node = EditorInterface.get_edited_scene_root()
	var action_name: String = "%saudio.bus %s" % [HHAgentConstants.UNDO_ACTION_PREFIX, bus_name]
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var persisted: Dictionary = {"ok": true, "disk_hash": ""}
	if _is_external_res(layout_path):
		persisted = _persist_res(command_id, new_layout, layout_path)
		if persisted.get("ok", false) != true:
			return persisted
		ProjectSettings.set_setting(BUS_SETTING, layout_path)
		var save_err: Error = ProjectSettings.save()
		if save_err != OK:
			return _unverified(command_id, "ProjectSettings.save failed for bus layout")
	elif params.get("isolate", false) == true:
		return _unverified(command_id, "isolate requires a durable AudioBusLayout .tres")
	var after: Dictionary = {
		"bus": AudioServer.get_bus_name(live_idx),
		"mute": AudioServer.is_bus_mute(live_idx),
		"volume_db": AudioServer.get_bus_volume_db(live_idx),
		"send": AudioServer.get_bus_send(live_idx),
		"layout": layout_path,
		"restore_layout": restore_path,
		"previous_layout": previous_setting,
		"disk_hash": str(persisted.get("disk_hash", "")),
		"durable": _is_external_res(layout_path),
		"invented_box": false,
		"heard": false,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _restore_layout(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var restore_path: String = str(params.get("restore_layout", params.get("layout", "")))
	if restore_path.contains("::") or not _is_external_res(restore_path):
		return _unverified(command_id, "restore requires a durable AudioBusLayout .tres")
	var jail: Dictionary = _meta.jail(command_id, restore_path)
	if jail.get("ok", false) != true:
		return jail
	var loaded: Resource = _load_res(restore_path)
	if loaded == null or not (loaded is AudioBusLayout):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "restore_layout is not AudioBusLayout", restore_path)
	var old_layout: AudioBusLayout = AudioServer.generate_bus_layout()
	var stroke: BusStroke = BusStroke.new()
	stroke.old_layout = old_layout
	stroke.new_layout = loaded as AudioBusLayout
	var edited: Node = EditorInterface.get_edited_scene_root()
	var action_name: String = "%saudio.bus restore" % HHAgentConstants.UNDO_ACTION_PREFIX
	var committed: Dictionary = _commit_stroke(command_id, edited, action_name, stroke)
	if committed.get("ok", false) != true:
		return committed
	var previous_setting: String = str(params.get("previous_layout", ""))
	if previous_setting.is_empty():
		ProjectSettings.clear(BUS_SETTING)
	else:
		ProjectSettings.set_setting(BUS_SETTING, previous_setting)
	var save_err: Error = ProjectSettings.save()
	if save_err != OK:
		return _unverified(command_id, "ProjectSettings.save failed restoring bus layout")
	var bus_name: String = str(params.get("bus", ""))
	var after: Dictionary = {
		"bus": bus_name,
		"restored": true,
		"layout": restore_path,
		"previous_layout": previous_setting,
		"disk_hash": _meta.disk_hash(restore_path),
		"durable": true,
		"invented_box": false,
		"heard": false,
		"source": "editor",
	}
	var idx: int = AudioServer.get_bus_index(bus_name)
	if idx >= 0:
		after["mute"] = AudioServer.is_bus_mute(idx)
		after["volume_db"] = AudioServer.get_bus_volume_db(idx)
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _preview(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var hold: Dictionary = _hold_scene(command_id, str(params.get("scene", "")), {})
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, str(params.get("node_path", "")))
	if node == null or (not (node is AudioStreamPlayer) and not (node is AudioStreamPlayer2D)):
		return _unverified(command_id, "AudioStreamPlayer not found")
	var stream: AudioStream = _player_stream(node)
	var after: Dictionary = {
		"scene": str(params.get("scene", "")),
		"node_path": str(params.get("node_path", "")),
		"class_name": node.get_class(),
		"stream_class": stream.get_class() if stream != null else "",
		"bus": _player_bus(node),
		"volume_db": _player_volume(node),
		"playing": _player_playing(node),
		"heard": false,
		"heard_proven": false,
		"license": LICENSE_GENERATOR if stream is AudioStreamGenerator else "",
		"alternative": "playing==true is not heard SFX; Alternative: editor assign only; deferred R6",
		"invented_box": false,
		"source": "editor",
	}
	return _errors.ok_read(command_id, _checks(post), after)


func _ensure_generator(command_id: String, stream_path: String) -> Dictionary:
	if stream_path.is_empty():
		return {"ok": true, "stream": AudioStreamGenerator.new()}
	var jail: Dictionary = _meta.jail(command_id, stream_path)
	if jail.get("ok", false) != true:
		return jail
	if FileAccess.file_exists(stream_path) or ResourceLoader.exists(stream_path):
		var loaded: Resource = _load_res(stream_path)
		if loaded == null or not (loaded is AudioStreamGenerator):
			return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "stream is not AudioStreamGenerator", "params.stream")
		return {"ok": true, "stream": loaded as AudioStreamGenerator}
	if not _is_external_res(stream_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "AudioStreamGenerator persist requires .tres or .res", stream_path)
	return {"ok": true, "stream": AudioStreamGenerator.new()}


static func _write_player(player: Node, stream: AudioStream, bus: String, volume_db: float) -> void:
	if player is AudioStreamPlayer:
		var p1: AudioStreamPlayer = player as AudioStreamPlayer
		p1.stream = stream
		if not bus.is_empty():
			p1.bus = bus
		p1.volume_db = volume_db
	elif player is AudioStreamPlayer2D:
		var p2: AudioStreamPlayer2D = player as AudioStreamPlayer2D
		p2.stream = stream
		if not bus.is_empty():
			p2.bus = bus
		p2.volume_db = volume_db


func _player_stream(player: Node) -> AudioStream:
	if player is AudioStreamPlayer:
		return (player as AudioStreamPlayer).stream
	if player is AudioStreamPlayer2D:
		return (player as AudioStreamPlayer2D).stream
	return null


func _player_bus(player: Node) -> String:
	if player is AudioStreamPlayer:
		return (player as AudioStreamPlayer).bus
	if player is AudioStreamPlayer2D:
		return (player as AudioStreamPlayer2D).bus
	return ""


func _player_volume(player: Node) -> float:
	if player is AudioStreamPlayer:
		return (player as AudioStreamPlayer).volume_db
	if player is AudioStreamPlayer2D:
		return (player as AudioStreamPlayer2D).volume_db
	return 0.0


func _player_playing(player: Node) -> bool:
	if player is AudioStreamPlayer:
		return (player as AudioStreamPlayer).playing
	if player is AudioStreamPlayer2D:
		return (player as AudioStreamPlayer2D).playing
	return false


func _audio_after(edited: Node, params: Dictionary, node: Node) -> Dictionary:
	var after: Dictionary = _meta.snapshot(edited, str(params.get("scene", "")))
	after["scene"] = str(params.get("scene", ""))
	after["node_path"] = str(params.get("node_path", ""))
	after["class_name"] = node.get_class() if node != null else ""
	after["path"] = str(params.get("node_path", ""))
	after["invented_box"] = false
	after["used_engine_transform"] = true
	after["source"] = "editor"
	return after


func _commit_stroke(command_id: String, edited: Node, action_name: String, stroke: RefCounted) -> Dictionary:
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_method(stroke, "apply")
	mgr.add_undo_method(stroke, "revert")
	mgr.add_do_reference(stroke)
	mgr.commit_action()
	return {"ok": true}


func _hold_scene(command_id: String, res_path: String, precondition: Dictionary) -> Dictionary:
	var gated: Dictionary = _meta.jail(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	if not precondition.is_empty():
		var want_fp: String = str(precondition.get("fingerprint", ""))
		var want_hv: String = str(precondition.get("history_version", ""))
		var want_hash: String = str(precondition.get("scene_hash", ""))
		if not want_fp.is_empty() and want_fp != _meta.fingerprint(edited):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor fingerprint changed; resync", "precondition.fingerprint")
		if not want_hv.is_empty() and want_hv != str(_meta.history_version(edited)):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "editor history version changed; resync", "precondition.history_version")
		if not want_hash.is_empty() and want_hash != _meta.disk_hash(res_path):
			return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "disk hash changed (human/external edit); resync", "precondition.scene_hash")
	return {"ok": true, "root": edited}


func _persist_res(command_id: String, res: Resource, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _is_external_res(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "resource persist requires .tres or .res", res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create resource directory", res_path)
	var save_err: Error = ResourceSaver.save(res, res_path)
	if save_err != OK:
		return _unverified(command_id, "ResourceSaver.save failed: %s" % error_string(save_err))
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "resource file missing after save")
	var disk: String = _meta.disk_hash(res_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "resource disk hash missing after save")
	return {"ok": true, "disk_hash": disk, "path": res_path}


func _resolve(root: Node, path_s: String) -> Node:
	if root == null:
		return null
	if path_s.is_empty() or path_s == "." or path_s == root.name:
		return root
	var found: Node = root.get_node_or_null(NodePath(path_s))
	if found != null:
		return found
	if path_s.begins_with(root.name + "/"):
		return root.get_node_or_null(NodePath(path_s.substr(root.name.length() + 1)))
	return null


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _load_res(res_path: String) -> Resource:
	if res_path.is_empty():
		return null
	if ResourceLoader.exists(res_path):
		var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if loaded != null:
			return loaded
	if FileAccess.file_exists(res_path):
		return ResourceLoader.load(res_path)
	return null


func _is_external_res(path_s: String) -> bool:
	return (path_s.ends_with(".tres") or path_s.ends_with(".res")) and not path_s.contains("::")


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
