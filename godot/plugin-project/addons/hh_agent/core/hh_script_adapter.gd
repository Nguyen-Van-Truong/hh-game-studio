class_name HHAgentScriptAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _IdentityScript: GDScript = preload("res://addons/hh_agent/core/hh_identity.gd")

## Script write/patch/attach/detach/rename. Validate before dest replace. Dirty buffer → E_CONFLICT.

var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()
var _identity: HHAgentIdentity = HHAgentIdentity.new()


func handles(action: String) -> bool:
	return (
		action == "write"
		or action == "patch"
		or action == "attach"
		or action == "detach"
		or action == "rename"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	precondition: Dictionary,
) -> Dictionary:
	if method != "godot.script":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not a script verb", "")
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	if action == "write":
		return _write(command_id, params, precondition, post)
	if action == "patch":
		return _patch(command_id, params, precondition, post)
	if action == "attach":
		return _attach(command_id, params, precondition, post, false)
	if action == "detach":
		return _attach(command_id, params, precondition, post, true)
	if action == "rename":
		return _rename(command_id, params, precondition, post)
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "script.%s is not a proven verb" % action, "")


func validate_source(contents: String) -> Dictionary:
	return _validate_source(contents)


func fallback_post(action: String) -> String:
	return _fallback_post(action)


func _fallback_post(action: String) -> String:
	if action == "write":
		return "script_disk_equals_write"
	if action == "patch":
		return "script_patch_applied"
	if action == "attach" or action == "detach":
		return "node_script_path_equals"
	if action == "rename":
		return "script_renamed"
	return "script_op"


func _write(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var contents: String = str(params.get("contents", ""))
	var gated: Dictionary = _gate_gd(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	var conflict: Dictionary = _conflict_gate(command_id, res_path, params, precondition)
	if conflict.get("ok", false) != true:
		return conflict
	var parsed: Dictionary = _validate_source(contents)
	if parsed.get("ok", false) != true:
		return _parse_fail(command_id, parsed, res_path)
	var persisted: Dictionary = _atomic_replace(command_id, res_path, contents)
	if persisted.get("ok", false) != true:
		return persisted
	_sync_open_buffer(res_path, contents)
	_reload_cached(res_path, contents)
	_meta.refresh_fs(res_path)
	var readback: String = _read_utf8(res_path)
	if readback != contents:
		return _unverified(command_id, "disk text did not equal write contents")
	if _has_bom_bytes(FileAccess.get_file_as_bytes(res_path)):
		return _unverified(command_id, "write left a UTF-8 BOM")
	var disk_hash: String = _meta.disk_hash(res_path)
	if disk_hash.is_empty() or disk_hash == "missing" or disk_hash != _sha256_text(contents):
		return _unverified(command_id, "write disk SHA-256 mismatch")
	var after: Dictionary = {
		"path": res_path,
		"disk_hash": disk_hash,
		"base": str(parsed.get("base", "")),
		"line_count": _line_count(contents),
		"created": conflict.get("existed", true) != true,
		"valid": true,
		"diagnostics": _diag_list(parsed),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _patch(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var find_s: String = str(params.get("find", ""))
	var replace_s: String = str(params.get("replace", ""))
	var buffer_only: bool = params.get("buffer_only", false) == true
	var gated: Dictionary = _gate_gd(command_id, res_path)
	if gated.get("ok", false) != true:
		return gated
	if find_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "find must be non-empty", "params.find")
	var conflict: Dictionary = _conflict_gate(command_id, res_path, params, precondition)
	if conflict.get("ok", false) != true:
		return conflict
	if not FileAccess.file_exists(res_path) and not buffer_only:
		return _unverified(command_id, "script missing")
	var start_line: int = 0
	var end_line: int = 0
	if params.has("start_line"):
		start_line = int(params.get("start_line"))
	if params.has("end_line"):
		end_line = int(params.get("end_line"))
	var state_v: Variant = conflict.get("state", {})
	var state: Dictionary = state_v if state_v is Dictionary else {}
	var source: String = _read_utf8(res_path)
	if buffer_only:
		if state.get("open", false) != true:
			return _unverified(command_id, "buffer_only requires an open ScriptEditor")
		source = str(state.get("buffer", ""))
	var patched: Dictionary = _apply_patch(source, find_s, replace_s, start_line, end_line)
	if patched.get("ok", false) != true:
		return _errors.fail(
			command_id,
			str(patched.get("code", HHAgentErrors.E_CONFLICT)),
			str(patched.get("message", "patch failed")),
			res_path,
		)
	var next_text: String = str(patched.get("text", ""))
	if buffer_only:
		if not _sync_open_buffer(res_path, next_text):
			return _unverified(command_id, "failed to write ScriptEditor buffer")
		var after_buf: Dictionary = {
			"path": res_path,
			"disk_hash": _meta.disk_hash(res_path),
			"buffer_hash": _sha256_text(next_text),
			"buffer_only": true,
			"dirty": true,
			"source": "editor",
		}
		return _errors.ok_changed(command_id, _checks(post), after_buf, true)
	var parsed: Dictionary = _validate_source(next_text)
	if parsed.get("ok", false) != true:
		return _parse_fail(command_id, parsed, res_path)
	if not _patch_constraint_holds(source, next_text, find_s, replace_s, start_line, end_line):
		return _unverified(command_id, "patch would change unrelated lines")
	var persisted: Dictionary = _atomic_replace(command_id, res_path, next_text)
	if persisted.get("ok", false) != true:
		return persisted
	_sync_open_buffer(res_path, next_text)
	_reload_cached(res_path, next_text)
	_meta.refresh_fs(res_path)
	var readback: String = _read_utf8(res_path)
	if readback != next_text:
		return _unverified(command_id, "patched disk text mismatch")
	if not _patch_constraint_holds(source, readback, find_s, replace_s, start_line, end_line):
		return _unverified(command_id, "patch changed unrelated lines")
	var disk_hash: String = _meta.disk_hash(res_path)
	if disk_hash != _sha256_text(next_text):
		return _unverified(command_id, "patch disk SHA-256 mismatch")
	var after: Dictionary = {
		"path": res_path,
		"disk_hash": disk_hash,
		"base": str(parsed.get("base", "")),
		"replaced": 1,
		"valid": true,
		"diagnostics": _diag_list(parsed),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _attach(
	command_id: String,
	params: Dictionary,
	precondition: Dictionary,
	post: String,
	detach: bool,
) -> Dictionary:
	var scene_path: String = str(params.get("scene", ""))
	var node_path: String = str(params.get("node_path", ""))
	var script_path: String = str(params.get("path", ""))
	var hold: Dictionary = _hold_scene(command_id, scene_path, precondition)
	if hold.get("ok", false) != true:
		return hold
	var edited: Node = hold.get("root") as Node
	var node: Node = _resolve(edited, node_path)
	if node == null:
		return _unverified(command_id, "node not found")
	var packed_err: Dictionary = _reject_packed(command_id, node, edited)
	if not packed_err.is_empty():
		return packed_err
	var loaded: Script = null
	if not detach:
		var gated: Dictionary = _gate_gd(command_id, script_path)
		if gated.get("ok", false) != true:
			return gated
		if not FileAccess.file_exists(script_path):
			return _unverified(command_id, "script missing")
		var res: Resource = ResourceLoader.load(script_path, "", ResourceLoader.CACHE_MODE_REUSE)
		if res == null or not (res is Script):
			return _unverified(command_id, "script load failed")
		loaded = res as Script
	var old_v: Variant = node.get("script")
	var action_name: String = "%sscript.%s %s" % [
		HHAgentConstants.UNDO_ACTION_PREFIX,
		"detach" if detach else "attach",
		node_path,
	]
	var mgr: EditorUndoRedoManager = _mgr()
	if mgr == null:
		return _unverified(command_id, "EditorUndoRedoManager missing")
	mgr.create_action(action_name, UndoRedo.MERGE_DISABLE, edited)
	mgr.add_do_property(node, "script", loaded)
	mgr.add_undo_property(node, "script", old_v)
	mgr.commit_action()
	var now_v: Variant = node.get("script")
	if detach:
		if now_v != null:
			return _unverified(command_id, "detach readback still has a script")
	else:
		if now_v != loaded:
			return _unverified(command_id, "attach readback did not equal Script")
		var now_script: Script = now_v as Script
		if now_script == null or now_script.resource_path != script_path:
			return _unverified(command_id, "attach path mismatch")
	_meta.mark_dirty(scene_path)
	var after: Dictionary = _meta.snapshot(edited, scene_path)
	after["scene"] = scene_path
	after["node_path"] = node_path
	after["path"] = "" if detach else script_path
	after["attached"] = not detach
	after["readback_equals"] = true
	after["source"] = "editor"
	return _errors.ok_changed(command_id, _checks(post), after, true, action_name)


func _rename(command_id: String, params: Dictionary, precondition: Dictionary, post: String) -> Dictionary:
	var src: String = str(params.get("path", ""))
	var name_s: String = str(params.get("name", ""))
	var gated: Dictionary = _gate_gd(command_id, src)
	if gated.get("ok", false) != true:
		return gated
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "name is required", "params.name")
	var dest: String = src.get_base_dir().rstrip("/") + "/" + name_s + ".gd"
	var dest_gate: Dictionary = _gate_gd(command_id, dest)
	if dest_gate.get("ok", false) != true:
		return dest_gate
	if dest == src:
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "rename dest equals source", dest)
	if not FileAccess.file_exists(src):
		return _unverified(command_id, "script missing")
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "rename dest already exists", dest)
	var conflict: Dictionary = _conflict_gate(command_id, src, params, precondition)
	if conflict.get("ok", false) != true:
		return conflict
	if _meta.any_open_dirty():
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"open scene is dirty; save before script.rename so refs do not drop edits",
			src,
		)
	var refs: PackedStringArray = _referencers(src)
	var uid_text: String = _uid_of(src)
	var uid_id: int = ResourceUID.INVALID_ID
	if not uid_text.is_empty():
		uid_id = ResourceUID.text_to_id(uid_text)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create destination directory", dest)
	var rename_err: Error = DirAccess.rename_absolute(
		ProjectSettings.globalize_path(src),
		ProjectSettings.globalize_path(dest),
	)
	if rename_err != OK:
		return _unverified(command_id, "rename failed: %s" % error_string(rename_err))
	var uid_sidecar: String = src + ".uid"
	if FileAccess.file_exists(uid_sidecar):
		DirAccess.rename_absolute(
			ProjectSettings.globalize_path(uid_sidecar),
			ProjectSettings.globalize_path(dest + ".uid"),
		)
	if uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
	var rewritten: int = _rewrite_refs(refs, src, dest)
	_rebind_open_nodes(src, dest)
	_meta.refresh_fs(src)
	_meta.refresh_fs(dest)
	if FileAccess.file_exists(src) or not FileAccess.file_exists(dest):
		return _unverified(command_id, "rename did not relocate the script")
	var new_uid: String = _uid_of(dest)
	if new_uid.is_empty() and uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
		new_uid = ResourceUID.id_to_text(uid_id)
	var after: Dictionary = {
		"path": dest,
		"from": src,
		"uid": new_uid,
		"old_path_absent": true,
		"disk_hash": _meta.disk_hash(dest),
		"rewritten": rewritten,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _gate_gd(command_id: String, res_path: String) -> Dictionary:
	var jail: Dictionary = _meta.jail(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not res_path.ends_with(".gd"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "script path must end with .gd", res_path)
	return jail


func _conflict_gate(command_id: String, res_path: String, params: Dictionary, precondition: Dictionary) -> Dictionary:
	_recover_bak(res_path)
	var state: Dictionary = _buffer_state(res_path)
	var expected: String = str(params.get("expected_hash", ""))
	if expected.is_empty():
		expected = str(params.get("base_hash", ""))
	if expected.is_empty() and not precondition.is_empty():
		expected = str(precondition.get("disk_hash", ""))
		if expected.is_empty():
			expected = str(precondition.get("scene_hash", ""))
	if state.get("dirty", false) == true:
		if expected.is_empty() or expected != str(state.get("buffer_hash", "")):
			return _errors.fail(
				command_id,
				HHAgentErrors.E_CONFLICT,
				"ScriptEditor buffer is dirty; expected_hash must match the unsaved buffer",
				res_path,
			)
		state["existed"] = FileAccess.file_exists(res_path)
		return {"ok": true, "state": state, "existed": FileAccess.file_exists(res_path)}
	if not expected.is_empty() and FileAccess.file_exists(res_path):
		var disk_hash: String = str(state.get("disk_hash", ""))
		var buffer_hash: String = str(state.get("buffer_hash", ""))
		if expected != disk_hash and expected != buffer_hash:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_CONFLICT,
				"base content hash mismatch (concurrent edit)",
				res_path,
			)
	return {"ok": true, "state": state, "existed": FileAccess.file_exists(res_path)}


func _validate_source(contents: String) -> Dictionary:
	if contents.begins_with("\ufeff") or _has_bom_bytes(contents.to_utf8_buffer()):
		return {
			"ok": false,
			"code": HHAgentErrors.E_INVALID_TYPE,
			"message": "UTF-8 BOM is not allowed",
		}
	var probe: GDScript = GDScript.new()
	probe.source_code = contents
	var err: Error = probe.reload()
	if err != OK:
		return {
			"ok": false,
			"code": HHAgentErrors.E_INVALID_TYPE,
			"message": "GDScript parse failed: %s" % error_string(err),
			"error": err,
			"base": "",
		}
	var base: String = probe.get_instance_base_type()
	if base.is_empty() and contents.contains("extends "):
		return {
			"ok": false,
			"code": HHAgentErrors.E_INVALID_TYPE,
			"message": "GDScript has no instance base type",
			"base": "",
		}
	return {"ok": true, "base": base, "valid": true}


func _parse_fail(command_id: String, parsed: Dictionary, res_path: String) -> Dictionary:
	return _errors.fail(
		command_id,
		str(parsed.get("code", HHAgentErrors.E_INVALID_TYPE)),
		str(parsed.get("message", "GDScript validate failed")),
		res_path,
	)


func _atomic_replace(command_id: String, dest: String, contents: String) -> Dictionary:
	var bytes: PackedByteArray = contents.to_utf8_buffer()
	if _has_bom_bytes(bytes):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "UTF-8 BOM is not allowed", dest)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create script directory", dest)
	_recover_bak(dest)
	var tmp: String = dest + ".tmp"
	var bak: String = dest + ".hh-bak"
	var tmp_abs: String = ProjectSettings.globalize_path(tmp)
	var dest_abs: String = ProjectSettings.globalize_path(dest)
	var bak_abs: String = ProjectSettings.globalize_path(bak)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot open script tmp", tmp)
	f.store_buffer(bytes)
	f.flush()
	f.close()
	var tmp_bytes: PackedByteArray = FileAccess.get_file_as_bytes(tmp)
	if tmp_bytes.size() != bytes.size() or _sha256_bytes(tmp_bytes) != _sha256_bytes(bytes):
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "tmp write did not match intended bytes")
	var existed: bool = FileAccess.file_exists(dest)
	if existed:
		if FileAccess.file_exists(bak):
			DirAccess.remove_absolute(bak_abs)
		var bak_err: Error = DirAccess.rename_absolute(dest_abs, bak_abs)
		if bak_err != OK:
			DirAccess.remove_absolute(tmp_abs)
			return _unverified(command_id, "could not park existing script for atomic replace")
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		if existed:
			DirAccess.rename_absolute(bak_abs, dest_abs)
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "atomic rename failed: %s" % error_string(ren))
	if existed and FileAccess.file_exists(bak):
		DirAccess.remove_absolute(bak_abs)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "dest missing after atomic rename")
	return {"ok": true}


func _recover_bak(dest: String) -> void:
	var bak: String = dest + ".hh-bak"
	if FileAccess.file_exists(dest):
		if FileAccess.file_exists(bak):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(bak))
		return
	if FileAccess.file_exists(bak):
		DirAccess.rename_absolute(ProjectSettings.globalize_path(bak), ProjectSettings.globalize_path(dest))


func _apply_patch(text: String, find_s: String, replace_s: String, start_line: int, end_line: int) -> Dictionary:
	var from_i: int = 0
	var to_i: int = text.length()
	if start_line >= 1:
		var last: int = end_line if end_line >= start_line else start_line
		var span: Vector2i = _line_span(text, start_line, last)
		from_i = span.x
		to_i = span.y
	var slice: String = text.substr(from_i, to_i - from_i)
	var idx: int = slice.find(find_s)
	if idx < 0:
		return {"ok": false, "code": HHAgentErrors.E_CONFLICT, "message": "find text not present in range"}
	var next_slice: String = slice.substr(0, idx) + replace_s + slice.substr(idx + find_s.length())
	var next_text: String = text.substr(0, from_i) + next_slice + text.substr(to_i)
	return {"ok": true, "text": next_text}


func _line_span(text: String, start_line: int, end_line: int) -> Vector2i:
	var line: int = 1
	var i: int = 0
	var start_i: int = 0
	while i < text.length() and line < start_line:
		if text[i] == "\n":
			line += 1
		i += 1
	start_i = i
	var end_i: int = text.length()
	while i < text.length() and line <= end_line:
		if text[i] == "\n":
			line += 1
			if line > end_line:
				end_i = i + 1
				break
		i += 1
	return Vector2i(start_i, end_i)


func _unrelated_lines_hold(before: String, after: String, find_s: String, replace_s: String) -> bool:
	var idx: int = before.find(find_s)
	if idx < 0:
		return false
	var expected: String = before.substr(0, idx) + replace_s + before.substr(idx + find_s.length())
	return expected == after


func _patch_constraint_holds(
	before: String,
	after: String,
	find_s: String,
	replace_s: String,
	start_line: int,
	end_line: int,
) -> bool:
	if start_line < 1:
		return _unrelated_lines_hold(before, after, find_s, replace_s)
	var last: int = end_line if end_line >= start_line else start_line
	var span: Vector2i = _line_span(before, start_line, last)
	var prefix: String = before.substr(0, span.x)
	var suffix: String = before.substr(span.y)
	if not after.begins_with(prefix):
		return false
	if after.length() < prefix.length() + suffix.length():
		return false
	if suffix.length() > 0 and after.substr(after.length() - suffix.length()) != suffix:
		return false
	var before_mid: String = before.substr(span.x, span.y - span.x)
	var after_mid: String = after.substr(prefix.length(), after.length() - prefix.length() - suffix.length())
	var idx: int = before_mid.find(find_s)
	if idx < 0:
		return false
	return before_mid.substr(0, idx) + replace_s + before_mid.substr(idx + find_s.length()) == after_mid


func _reject_packed(command_id: String, node: Node, edited: Node) -> Dictionary:
	if _identity.is_packed_internal(node, edited):
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"packed instance child requires make_local; refusing a flatten",
			"params.node_path",
		)
	return {}


func _buffer_state(res_path: String) -> Dictionary:
	var existed: bool = FileAccess.file_exists(res_path)
	var disk: String = _read_utf8(res_path) if existed else ""
	var disk_hash: String = _sha256_text(disk) if existed else "missing"
	var ed: Dictionary = _open_editor(res_path)
	if ed.get("open", false) != true:
		return {
			"open": false,
			"dirty": false,
			"disk": disk,
			"disk_hash": disk_hash,
			"buffer": disk,
			"buffer_hash": disk_hash,
		}
	var buffer: String = str(ed.get("text", ""))
	var buffer_hash: String = _sha256_text(buffer)
	return {
		"open": true,
		"dirty": buffer != disk,
		"disk": disk,
		"disk_hash": disk_hash,
		"buffer": buffer,
		"buffer_hash": buffer_hash,
	}


func _open_editor(res_path: String) -> Dictionary:
	var se: ScriptEditor = EditorInterface.get_script_editor()
	if se == null:
		return {"open": false}
	if not se.has_method("get_open_scripts"):
		return {"open": false}
	var scripts_v: Variant = se.get_open_scripts()
	if not (scripts_v is Array):
		return {"open": false}
	var scripts: Array = scripts_v
	var editors: Array = []
	if se.has_method("get_open_script_editors"):
		var editors_v: Variant = se.get_open_script_editors()
		if editors_v is Array:
			editors = editors_v
	var i: int = 0
	while i < scripts.size():
		var sc_v: Variant = scripts[i]
		if sc_v is Script and (sc_v as Script).resource_path == res_path:
			var text: String = ""
			var code: CodeEdit = null
			if i < editors.size() and editors[i] is ScriptEditorBase:
				var base: Control = (editors[i] as ScriptEditorBase).get_base_editor()
				if base is CodeEdit:
					code = base as CodeEdit
					text = code.get_text()
				elif base is TextEdit:
					text = (base as TextEdit).get_text()
			elif sc_v is GDScript:
				text = (sc_v as GDScript).source_code
			return {"open": true, "text": text, "code": code, "script": sc_v}
		i += 1
	return {"open": false}


func _sync_open_buffer(res_path: String, text: String) -> bool:
	var ed: Dictionary = _open_editor(res_path)
	if ed.get("open", false) != true:
		return true
	var code_v: Variant = ed.get("code")
	if code_v is CodeEdit:
		(code_v as CodeEdit).set_text(text)
		return (code_v as CodeEdit).get_text() == text
	var sc_v: Variant = ed.get("script")
	if sc_v is GDScript:
		(sc_v as GDScript).source_code = text
		return true
	return false


func _reload_cached(res_path: String, contents: String) -> void:
	if not ResourceLoader.exists(res_path) and not FileAccess.file_exists(res_path):
		return
	var loaded: Resource = ResourceLoader.load(res_path, "", ResourceLoader.CACHE_MODE_REPLACE)
	if loaded is GDScript:
		var gd: GDScript = loaded as GDScript
		gd.source_code = contents
		gd.reload()


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


func _referencers(res_path: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var uid_text: String = _uid_of(res_path)
	var files: PackedStringArray = PackedStringArray()
	_collect_files("res://", files)
	for item: String in files:
		if item == res_path or item == res_path + ".uid":
			continue
		if _file_refs(item, res_path, uid_text):
			out.append(item)
	return out


func _file_refs(file_path: String, res_path: String, uid_text: String) -> bool:
	if ResourceLoader.exists(file_path):
		var deps: PackedStringArray = ResourceLoader.get_dependencies(file_path)
		for dep: String in deps:
			if dep.contains(res_path):
				return true
			if not uid_text.is_empty() and dep.contains(uid_text):
				return true
	if not FileAccess.file_exists(file_path):
		return false
	var text: String = FileAccess.get_file_as_string(file_path)
	if text.contains(res_path):
		return true
	if not uid_text.is_empty() and text.contains(uid_text):
		return true
	return false


func _collect_files(dir_path: String, out: PackedStringArray) -> void:
	var da: DirAccess = DirAccess.open(dir_path)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if name_s == "." or name_s == ".." or name_s.begins_with("."):
			name_s = da.get_next()
			continue
		var child: String = dir_path
		if child.ends_with("/"):
			child += name_s
		else:
			child += "/" + name_s
		if da.current_is_dir():
			if name_s != "addons":
				_collect_files(child, out)
		elif name_s.ends_with(".tscn") or name_s.ends_with(".scn") or name_s.ends_with(".tres") or name_s.ends_with(".res"):
			out.append(child)
		name_s = da.get_next()
	da.list_dir_end()


func _rewrite_refs(refs: PackedStringArray, src: String, dest: String) -> int:
	var n: int = 0
	for item: String in refs:
		if not FileAccess.file_exists(item):
			continue
		var text: String = FileAccess.get_file_as_bytes(item).get_string_from_utf8()
		if not text.contains(src):
			continue
		var next_text: String = text.replace(src, dest)
		if next_text == text:
			continue
		var replaced: Dictionary = _atomic_replace("rename-ref", item, next_text)
		if replaced.get("ok", false) == true:
			_meta.refresh_fs(item)
			n += 1
	return n


func _rebind_open_nodes(src: String, dest: String) -> void:
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited == null:
		return
	var loaded: Resource = ResourceLoader.load(dest, "", ResourceLoader.CACHE_MODE_REPLACE)
	if loaded == null or not (loaded is Script):
		return
	var script: Script = loaded as Script
	_rebind_walk(edited, src, script)


func _rebind_walk(node: Node, src: String, script: Script) -> void:
	var cur: Variant = node.get("script")
	if cur is Script and (cur as Script).resource_path == src:
		node.set("script", script)
	var i: int = 0
	while i < node.get_child_count():
		_rebind_walk(node.get_child(i), src, script)
		i += 1


func _uid_of(res_path: String) -> String:
	if res_path.is_empty():
		return ""
	var id: int = ResourceLoader.get_resource_uid(res_path)
	if id != ResourceUID.INVALID_ID:
		return ResourceUID.id_to_text(id)
	return ""


func _read_utf8(res_path: String) -> String:
	if not FileAccess.file_exists(res_path):
		return ""
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(res_path)
	return bytes.get_string_from_utf8()


func _has_bom_bytes(bytes: PackedByteArray) -> bool:
	if bytes.size() < 3:
		return false
	return bytes[0] == 0xEF and bytes[1] == 0xBB and bytes[2] == 0xBF


func _line_count(text: String) -> int:
	if text.is_empty():
		return 0
	return text.count("\n") + 1


func _diag_list(parsed: Dictionary) -> Array:
	var out: Array = []
	if parsed.get("ok", false) == true:
		return out
	out.append({
		"line": 0,
		"code": str(parsed.get("code", "")),
		"message": str(parsed.get("message", "")),
	})
	return out


func _sha256_text(text: String) -> String:
	return _sha256_bytes(text.to_utf8_buffer())


func _sha256_bytes(bytes: PackedByteArray) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	if start_err != OK:
		return ""
	ctx.update(bytes)
	return ctx.finish().hex_encode()


func _mgr() -> EditorUndoRedoManager:
	return EditorInterface.get_editor_undo_redo()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
