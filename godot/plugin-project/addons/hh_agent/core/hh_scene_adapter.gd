class_name HHAgentSceneAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")

## Proven scene lifecycle via EditorInterface. Not node CRUD.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()


func handles(action: String) -> bool:
	return action == "create" or action == "open" or action == "save" or action == "save_as" or action == "reload" or action == "activate" or action == "close"


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.scene":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a scene verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "create":
		return _create(command_id, params, post)
	if action == "open" or action == "activate":
		return _open(command_id, params, post)
	if action == "save":
		return _save(command_id, params, precondition, post, false)
	if action == "save_as":
		return _save(command_id, params, precondition, post, true)
	if action == "reload":
		return _reload(command_id, params, precondition, post)
	if action == "close":
		return _close(command_id, params, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "scene.%s is not a proven lifecycle verb" % action, "")


func _fallback_post(action: String) -> String:
	if action == "create":
		return "scene_file_exists_with_root_type"
	if action == "open" or action == "activate":
		return "edited_scene_path_matches"
	if action == "save" or action == "save_as":
		return "scene_disk_hash_matches_pack"
	if action == "reload":
		return "scene_tree_matches_disk"
	if action == "close":
		return "scene_not_in_open_list"
	return "scene_lifecycle"


func _create(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var root_class: String = str(params.get("root_class", ""))
	var inherit_from: String = str(params.get("inherit_from", ""))
	var gated: Dictionary = _gate_scene_path(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if FileAccess.file_exists(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "scene already exists", res_path)
	var dir_err: Error = _meta.ensure_parent_dir(res_path)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create scene directory", res_path)
	if not inherit_from.is_empty():
		return _create_inherited(command_id, res_path, inherit_from, post)
	if not ClassDB.class_exists(root_class):
		return _unverified(command_id, "ClassDB has no class %s" % root_class)
	if not ClassDB.can_instantiate(root_class):
		return _unverified(command_id, "class %s is not instantiable" % root_class)
	if not ClassDB.is_parent_class(root_class, "Node") and root_class != "Node":
		return _unverified(command_id, "root_class must extend Node")
	var obj: Variant = ClassDB.instantiate(root_class)
	if obj == null or not (obj is Node):
		if obj is Object:
			(obj as Object).free()
		return _unverified(command_id, "failed to instantiate %s" % root_class)
	var root: Node = obj as Node
	root.name = res_path.get_file().get_basename()
	var packed: PackedScene = PackedScene.new()
	var pack_err: Error = packed.pack(root)
	root.free()
	if pack_err != OK:
		return _unverified(command_id, "PackedScene.pack failed")
	var save_err: Error = ResourceSaver.save(packed, res_path)
	if save_err != OK:
		return _save_fail(command_id, save_err, res_path)
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene file missing after plugin write")
	EditorInterface.open_scene_from_path(res_path)
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "EditorInterface did not edit %s" % res_path)
	if edited.get_class() != root_class:
		return _unverified(command_id, "edited root class %s != %s" % [edited.get_class(), root_class])
	_maybe_mark_dirty(res_path, edited)
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["source"] = "editor"
	if after.get("disk_hash", "") == "missing" or str(after.get("disk_hash", "")).is_empty():
		return _unverified(command_id, "create disk hash missing")
	if after.get("dirty", false) != true:
		return _unverified(command_id, "create did not leave an unsaved/dirty tab")
	if int(after.get("history_version", "0")) <= 0:
		return _unverified(command_id, "create history_version did not bind EditorUndoRedo")
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _create_inherited(
	command_id: String,
	res_path: String,
	inherit_from: String,
	post: String,
) -> Dictionary:
	var base_gate: Dictionary = _gate_scene_path(command_id, inherit_from)
	if base_gate.get("ok", false) != true:
		return base_gate
	if not FileAccess.file_exists(inherit_from):
		return _unverified(command_id, "inherit_from scene missing")
	var loaded: Resource = ResourceLoader.load(inherit_from)
	if loaded == null or not (loaded is PackedScene):
		return _unverified(command_id, "inherit_from is not a PackedScene")
	var base: PackedScene = loaded as PackedScene
	var inst: Node = base.instantiate(PackedScene.GEN_EDIT_STATE_MAIN_INHERITED)
	if inst == null:
		inst = base.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	if inst == null:
		return _unverified(command_id, "failed to instantiate inherit_from")
	inst.name = res_path.get_file().get_basename()
	var packed: PackedScene = PackedScene.new()
	var pack_err: Error = packed.pack(inst)
	inst.free()
	if pack_err != OK:
		return _unverified(command_id, "inherited PackedScene.pack failed")
	var save_err: Error = ResourceSaver.save(packed, res_path)
	if save_err != OK:
		return _save_fail(command_id, save_err, res_path)
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "inherited scene file missing after plugin write")
	var text: String = FileAccess.get_file_as_string(res_path)
	if not text.contains("instance="):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(res_path))
		_meta.refresh_fs(res_path)
		return _unverified(command_id, "ResourceSaver flattened inherit; refusing raw tscn stub")
	EditorInterface.open_scene_from_path(res_path)
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "inherited scene did not become edited")
	_maybe_mark_dirty(res_path, edited)
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["source"] = "editor"
	after["inherit_from"] = inherit_from
	if after.get("inherited", false) != true:
		return _unverified(command_id, "inherited snapshot lost instance=")
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _open(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var gated: Dictionary = _gate_scene_path(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	EditorInterface.open_scene_from_path(res_path)
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "edited_scene is not %s" % res_path)
	var again: String = _meta.edited_path()
	if again != res_path:
		return _unverified(command_id, "edited_scene changed during readback")
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _save(
	command_id: String,
	params: Dictionary,
	precondition: Dictionary,
	post: String,
	save_as: bool,
) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var gated: Dictionary = _gate_scene_path(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return _unverified(command_id, "no edited scene to save")
	if not save_as:
		if edited.scene_file_path != res_path:
			EditorInterface.open_scene_from_path(res_path)
			edited = EditorInterface.get_edited_scene_root()
			if edited == null or edited.scene_file_path != res_path:
				return _unverified(command_id, "cannot edit %s for save" % res_path)
	var pre_err: Dictionary = _check_precondition(command_id, precondition, edited, edited.scene_file_path)
	if pre_err.get("ok", false) != true:
		return pre_err
	_strip_mark_meta(edited)
	if save_as:
		if not EditorInterface.has_method("save_scene_as"):
			return _unverified(command_id, "EditorInterface.save_scene_as missing")
		EditorInterface.save_scene_as(res_path, false)
	else:
		var save_err: Error = EditorInterface.save_scene()
		if save_err != OK:
			return _save_fail(command_id, save_err, res_path)
	_meta.refresh_fs(res_path)
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "save did not produce a file")
	var disk: String = _meta.disk_hash(res_path)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "save disk hash missing")
	edited = EditorInterface.get_edited_scene_root()
	if edited == null:
		return _unverified(command_id, "edited scene vanished after save")
	if save_as and edited.scene_file_path != res_path:
		EditorInterface.open_scene_from_path(res_path)
		edited = EditorInterface.get_edited_scene_root()
		if edited == null or edited.scene_file_path != res_path:
			return _unverified(command_id, "save-as did not switch edited scene")
	_meta.clear_dirty(res_path)
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["source"] = "editor"
	if str(after.get("disk_hash", "")) != disk:
		return _unverified(command_id, "disk hash changed during readback")
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _reload(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var gated: Dictionary = _gate_scene_path(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "scene missing")
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and edited.scene_file_path == res_path:
		if _meta.is_dirty(edited) and precondition.is_empty():
			return _errors.fail(
				command_id,
				HHAgentErrors.E_CONFLICT,
				"reload refused on dirty tab without matching precondition",
				res_path,
			)
		var pre_err: Dictionary = _check_precondition(command_id, precondition, edited, res_path)
		if pre_err.get("ok", false) != true:
			return pre_err
	EditorInterface.reload_scene_from_path(res_path)
	edited = EditorInterface.get_edited_scene_root()
	if edited == null or edited.scene_file_path != res_path:
		return _unverified(command_id, "reload did not leave %s edited" % res_path)
	var after: Dictionary = _meta.snapshot(edited, res_path)
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _close(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var gated: Dictionary = _gate_scene_path(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if not EditorInterface.has_method("close_scene"):
		return _unverified(
			command_id,
			"EditorInterface.close_scene is not available on this stock EditorInterface; refusing to fake close",
		)
	if _meta.edited_path() != res_path:
		if FileAccess.file_exists(res_path):
			EditorInterface.open_scene_from_path(res_path)
	if _meta.edited_path() != res_path:
		return _unverified(command_id, "cannot activate %s to close it" % res_path)
	var closing: Node = EditorInterface.get_edited_scene_root()
	if _meta.is_dirty(closing):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"close refused on dirty tab; save or match precondition first",
			res_path,
		)
	EditorInterface.close_scene()
	var open: Array = _meta.open_scenes()
	if res_path in open:
		return _unverified(command_id, "scene still in open list after close")
	var again: Array = _meta.open_scenes()
	if res_path in again:
		return _unverified(command_id, "close postcondition raced")
	var after: Dictionary = {
		"path": res_path,
		"open_scenes": again,
		"edited_scene": _meta.edited_path(),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _gate_scene_path(command_id: String, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not _meta.is_scene_path(res_path):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be .tscn or .scn", res_path)
	return {"ok": true}


func _check_precondition(
	command_id: String,
	precondition: Dictionary,
	root: Node,
	res_path: String,
) -> Dictionary:
	if precondition.is_empty():
		return {"ok": true}
	var want_fp: String = str(precondition.get("fingerprint", ""))
	var want_hv: String = str(precondition.get("history_version", ""))
	var want_hash: String = str(precondition.get("scene_hash", ""))
	var now_fp: String = _meta.fingerprint(root)
	var now_hv: String = str(_meta.history_version(root))
	var now_hash: String = _meta.disk_hash(res_path)
	if not want_fp.is_empty() and want_fp != now_fp:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"editor fingerprint changed; resync",
			"precondition.fingerprint",
		)
	if not want_hv.is_empty() and want_hv != now_hv:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"editor history version changed; resync",
			"precondition.history_version",
		)
	if not want_hash.is_empty() and want_hash != now_hash:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"disk hash changed (human/external edit); resync",
			"precondition.scene_hash",
		)
	return {"ok": true}


func _strip_mark_meta(root: Node) -> void:
	if root != null and root.has_meta("_hh_unsaved"):
		root.remove_meta("_hh_unsaved")


func _maybe_mark_dirty(res_path: String, root: Node) -> void:
	_meta.mark_dirty(res_path)
	if EditorInterface.has_method("mark_scene_as_unsaved"):
		EditorInterface.mark_scene_as_unsaved()
	var mgr: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	if mgr == null or root == null:
		return
	mgr.create_action("hh.scene.mark_unsaved")
	mgr.add_do_method(root, "set_meta", "_hh_unsaved", true)
	mgr.add_undo_method(root, "remove_meta", "_hh_unsaved")
	mgr.commit_action()


func _save_fail(command_id: String, err: Error, res_path: String) -> Dictionary:
	if err == ERR_FILE_CANT_WRITE or err == ERR_CANT_CREATE or err == ERR_UNAUTHORIZED:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "scene save failed: %s" % error_string(err), res_path)
	return _unverified(command_id, "scene save failed: %s" % error_string(err))


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
