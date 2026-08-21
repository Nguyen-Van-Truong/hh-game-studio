class_name HHAgentSceneMeta
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")

## Editor-tree fingerprint + disk hash. No sidecar writes.

var _errors: HHAgentErrors = HHAgentErrors.new()


func jail(command_id: String, res_path: String) -> Dictionary:
	if not res_path.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path must be res://", res_path)
	if res_path.contains(".."):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path escapes via ..", res_path)
	var abs_path: String = ProjectSettings.globalize_path(res_path)
	var root: String = ProjectSettings.globalize_path("res://")
	if not abs_path.begins_with(root):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path is outside project root", res_path)
	return {"ok": true, "abs": abs_path}


func is_scene_path(res_path: String) -> bool:
	return res_path.ends_with(".tscn") or res_path.ends_with(".scn")


func disk_hash(res_path: String) -> String:
	if not FileAccess.file_exists(res_path):
		return "missing"
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(res_path)
	return _sha256_bytes(bytes)


func fingerprint(root: Node) -> String:
	if root == null:
		return ""
	var lines: PackedStringArray = PackedStringArray()
	_fp_walk(root, ".", str(root.scene_file_path), lines)
	var joined: String = "\n".join(lines)
	return _sha256_bytes(joined.to_utf8_buffer())


func history_version(root: Node) -> int:
	if root == null:
		return 0
	var mgr: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	if mgr == null:
		return 0
	var hid: int = mgr.get_history_id_for_object(root)
	if not mgr.has_method("get_history_undo_redo"):
		return hid
	var ur: UndoRedo = mgr.get_history_undo_redo(hid)
	if ur == null:
		return 0
	return ur.get_version()


func is_dirty(root: Node) -> bool:
	if root == null:
		return false
	var mgr: EditorUndoRedoManager = EditorInterface.get_editor_undo_redo()
	if mgr == null:
		return false
	var hid: int = mgr.get_history_id_for_object(root)
	if mgr.has_method("is_history_unsaved"):
		return mgr.is_history_unsaved(hid)
	return false


func is_inherited_file(res_path: String) -> bool:
	if not FileAccess.file_exists(res_path):
		return false
	var text: String = FileAccess.get_file_as_string(res_path)
	return text.contains("instance=")


func open_scenes() -> Array:
	var out: Array = []
	var raw: PackedStringArray = EditorInterface.get_open_scenes()
	for item: String in raw:
		out.append(item)
	return out


func edited_path() -> String:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return ""
	return str(edited.scene_file_path)


func snapshot(root: Node, res_path: String) -> Dictionary:
	var path_use: String = res_path
	if path_use.is_empty() and root != null:
		path_use = str(root.scene_file_path)
	return {
		"path": path_use,
		"root": "" if root == null else root.name,
		"root_class": "" if root == null else root.get_class(),
		"fingerprint": fingerprint(root),
		"history_version": str(history_version(root)),
		"disk_hash": disk_hash(path_use),
		"dirty": is_dirty(root),
		"inherited": is_inherited_file(path_use),
		"edited_scene": edited_path(),
		"open_scenes": open_scenes(),
	}


func refresh_fs(res_path: String) -> void:
	var efs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	if efs != null:
		efs.update_file(res_path)


func ensure_parent_dir(res_path: String) -> Error:
	var parent: String = res_path.get_base_dir()
	if parent.is_empty() or parent == "res://":
		return OK
	var da: DirAccess = DirAccess.open("res://")
	if da == null:
		return ERR_CANT_OPEN
	var rel: String = parent.trim_prefix("res://")
	var err: Error = da.make_dir_recursive(rel)
	if err == ERR_ALREADY_EXISTS:
		return OK
	return err


func _fp_walk(node: Node, path_s: String, edited: String, out: PackedStringArray) -> void:
	var inst: String = ""
	if not node.scene_file_path.is_empty() and node.scene_file_path != edited:
		inst = "\tinstance:%s" % node.scene_file_path
	out.append("%s\t%s\t%s%s" % [path_s, node.name, node.get_class(), inst])
	var i: int = 0
	while i < node.get_child_count():
		var child: Node = node.get_child(i)
		var child_path: String = child.name if path_s == "." else "%s/%s" % [path_s, child.name]
		_fp_walk(child, child_path, edited, out)
		i += 1


func _sha256_bytes(bytes: PackedByteArray) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	if start_err != OK:
		return ""
	ctx.update(bytes)
	return ctx.finish().hex_encode()
