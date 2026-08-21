class_name HHAgentAssetAdapter
extends RefCounted

const _ConstantsScript: GDScript = preload("res://addons/hh_agent/core/hh_constants.gd")
const _ErrorsScript: GDScript = preload("res://addons/hh_agent/core/hh_errors.gd")
const _ActionsScript: GDScript = preload("res://addons/hh_agent/core/hh_actions.gd")
const _MetaScript: GDScript = preload("res://addons/hh_agent/core/hh_scene_meta.gd")
const _PauseScript: GDScript = preload("res://addons/hh_agent/core/hh_pause.gd")

## Ingest/import/reimport/move/delete. Stage outside res://, sniff, atomic promote, wait import.

const MAX_BYTES: int = 8388608
const IMPORT_WAIT_MS: int = 12000
const POLL_MS: int = 25

static var _import_busy: bool = false
static var _job_token: String = ""


var _errors: HHAgentErrors = HHAgentErrors.new()
var _meta: HHAgentSceneMeta = HHAgentSceneMeta.new()


func handles(action: String) -> bool:
	return (
		action == "import"
		or action == "reimport"
		or action == "move"
		or action == "rename"
		or action == "delete"
	)


func handle(
	command_id: String,
	method: String,
	action: String,
	params: Dictionary,
	actions: HHAgentActions,
	_precondition: Dictionary,
	pause_gate: HHAgentPauseGate = null,
) -> Dictionary:
	if method != "godot.asset":
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "not an asset verb", "")
	if _import_busy:
		return _errors.fail(command_id, HHAgentErrors.E_BUSY, "asset import job is already running", "busy")
	_import_busy = true
	_job_token = command_id
	var def: Dictionary = actions.lookup(method, action)
	var post: String = str(def.get("postcondition", ""))
	if post.is_empty():
		post = _fallback_post(action)
	var result: Dictionary = {}
	if action == "import":
		result = _import(command_id, params, post, pause_gate)
	elif action == "reimport":
		result = _reimport(command_id, params, post, pause_gate)
	elif action == "move":
		result = _move(
			command_id,
			str(params.get("from", "")),
			str(params.get("to", "")),
			params.get("rewrite_plan", false) == true,
			post,
		)
	elif action == "rename":
		result = _rename(command_id, params, post)
	elif action == "delete":
		result = _delete(command_id, params, post)
	else:
		result = _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "asset.%s is not a proven verb" % action, "")
	if _job_token == command_id:
		_import_busy = false
		_job_token = ""
	return result


func _fallback_post(action: String) -> String:
	if action == "import":
		return "import_sidecar_exists"
	if action == "reimport":
		return "import_timestamp_updated"
	if action == "move":
		return "old_path_absent_new_path_present"
	if action == "rename":
		return "asset_renamed"
	if action == "delete":
		return "asset_absent_or_quarantined"
	return "asset_op"


func _import(
	command_id: String,
	params: Dictionary,
	post: String,
	pause_gate: HHAgentPauseGate,
) -> Dictionary:
	var dest: String = str(params.get("path", ""))
	var source: String = str(params.get("source", ""))
	var dest_jail: Dictionary = _jail_dest(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if FileAccess.file_exists(dest):
		if source.is_empty():
			return _reimport(command_id, params, post, pause_gate)
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "destination already exists", dest)
	if source.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "source is required for ingest", "params.source")
	var staged: Dictionary = _stage_and_sniff(command_id, source, dest, params)
	if staged.get("ok", false) != true:
		return staged
	var promoted: Dictionary = _promote(command_id, dest, staged.get("bytes") as PackedByteArray)
	if promoted.get("ok", false) != true:
		_cleanup_staging(str(staged.get("staging_dir", "")))
		return promoted
	var waited: Dictionary = _wait_import(command_id, dest, pause_gate, IMPORT_WAIT_MS)
	if waited.get("ok", false) != true:
		_quarantine_new(dest, command_id)
		_cleanup_staging(str(staged.get("staging_dir", "")))
		return waited
	_cleanup_staging(str(staged.get("staging_dir", "")))
	return _import_ack(command_id, dest, post, str(staged.get("kind", "")), staged.get("license"))


func _reimport(
	command_id: String,
	params: Dictionary,
	post: String,
	pause_gate: HHAgentPauseGate,
) -> Dictionary:
	var dest: String = str(params.get("path", ""))
	var dest_jail: Dictionary = _jail_dest(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "asset missing")
	var waited: Dictionary = _wait_import(command_id, dest, pause_gate, IMPORT_WAIT_MS)
	if waited.get("ok", false) != true:
		return waited
	return _import_ack(command_id, dest, post, dest.get_extension().to_lower(), {"license": "unknown"})


func _import_ack(command_id: String, dest: String, post: String, kind: String, license_v: Variant) -> Dictionary:
	if _job_token != command_id:
		return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "late import must not commit an old job", dest)
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "dest missing after import wait")
	if not FileAccess.file_exists(dest + ".import"):
		return _unverified(command_id, ".import sidecar missing after wait")
	if not ResourceLoader.exists(dest):
		return _unverified(command_id, "ResourceLoader.exists was false after wait")
	var disk: String = _meta.disk_hash(dest)
	if disk.is_empty() or disk == "missing":
		return _unverified(command_id, "import disk SHA-256 missing")
	var license: Dictionary = license_v if license_v is Dictionary else {"license": "unknown"}
	var after: Dictionary = {
		"path": dest,
		"disk_hash": disk,
		"uid": _uid_of(dest),
		"kind": kind,
		"import_sidecar": true,
		"resource_exists": true,
		"job": command_id,
		"license": str(license.get("license", "unknown")),
		"license_manifest": str(license.get("manifest", "")),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _stage_and_sniff(command_id: String, source: String, dest: String, params: Dictionary) -> Dictionary:
	var opened: Dictionary = _read_source(command_id, source)
	if opened.get("ok", false) != true:
		return opened
	var bytes: PackedByteArray = opened.get("bytes") as PackedByteArray
	if bytes.size() > MAX_BYTES:
		return _errors.fail(command_id, HHAgentErrors.E_OUT_OF_BOUNDS, "source exceeds %d bytes" % MAX_BYTES, source)
	if bytes.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "source is empty", source)
	var sniffed: Dictionary = _sniff(command_id, bytes, dest)
	if sniffed.get("ok", false) != true:
		return sniffed
	var staging_dir: String = _staging_dir(command_id)
	var mk: Error = DirAccess.make_dir_recursive_absolute(staging_dir)
	if mk != OK and mk != ERR_ALREADY_EXISTS:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create staging directory", staging_dir)
	var staged_file: String = staging_dir.path_join(dest.get_file())
	var wrote: Dictionary = _write_abs_bytes(command_id, staged_file, bytes)
	if wrote.get("ok", false) != true:
		_cleanup_staging(staging_dir)
		return wrote
	var license: Dictionary = _license_of(source, params)
	return {
		"ok": true,
		"bytes": bytes,
		"kind": str(sniffed.get("kind", "")),
		"staging_dir": staging_dir,
		"staging_file": staged_file,
		"license": license,
	}


func _read_source(command_id: String, source: String) -> Dictionary:
	if source.is_empty() or source.find(char(0)) >= 0:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "source path is empty or contains NUL", source)
	if source.length() > 512:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "source path too long", source)
	var norm: String = source.replace("\\", "/")
	if norm.begins_with("res://"):
		var jail: Dictionary = _meta.jail(command_id, norm)
		if jail.get("ok", false) != true:
			return jail
		if not FileAccess.file_exists(norm):
			return _errors.fail(command_id, HHAgentErrors.E_PATH, "source res:// file missing", norm)
		return {"ok": true, "bytes": FileAccess.get_file_as_bytes(norm)}
	if norm.contains("://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "source scheme is not allowed", source)
	var f: FileAccess = FileAccess.open(source, FileAccess.READ)
	if f == null:
		f = FileAccess.open(norm, FileAccess.READ)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot open external source", source)
	var bytes: PackedByteArray = f.get_buffer(f.get_length())
	f.close()
	return {"ok": true, "bytes": bytes}


func _sniff(command_id: String, bytes: PackedByteArray, dest: String) -> Dictionary:
	var kind: String = _magic_kind(bytes)
	if kind.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "unrecognized or corrupt magic", dest)
	var ext: String = dest.get_extension().to_lower()
	if not _ext_matches(kind, ext):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "magic %s does not match dest .%s" % [kind, ext], dest)
	if _is_polyglot(bytes, kind):
		return _errors.fail(command_id, HHAgentErrors.E_INVALID_TYPE, "polyglot or trailing payload rejected", dest)
	var decoded: Dictionary = _decode(kind, bytes)
	if decoded.get("ok", false) != true:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_INVALID_TYPE,
			str(decoded.get("message", "decode failed")),
			dest,
		)
	return {"ok": true, "kind": kind}


func _magic_kind(bytes: PackedByteArray) -> String:
	if bytes.size() >= 8 and bytes[0] == 0x89 and bytes[1] == 0x50 and bytes[2] == 0x4E and bytes[3] == 0x47:
		if bytes[4] == 0x0D and bytes[5] == 0x0A and bytes[6] == 0x1A and bytes[7] == 0x0A:
			return "png"
	if bytes.size() >= 3 and bytes[0] == 0xFF and bytes[1] == 0xD8 and bytes[2] == 0xFF:
		return "jpg"
	if bytes.size() >= 12 and bytes[0] == 0x52 and bytes[1] == 0x49 and bytes[2] == 0x46 and bytes[3] == 0x46:
		if bytes[8] == 0x57 and bytes[9] == 0x45 and bytes[10] == 0x42 and bytes[11] == 0x50:
			return "webp"
		if bytes[8] == 0x57 and bytes[9] == 0x41 and bytes[10] == 0x56 and bytes[11] == 0x45:
			return "wav"
	if bytes.size() >= 4 and bytes[0] == 0x4F and bytes[1] == 0x67 and bytes[2] == 0x67 and bytes[3] == 0x53:
		return "ogg"
	return ""


func _ext_matches(kind: String, ext: String) -> bool:
	if kind == "png":
		return ext == "png"
	if kind == "jpg":
		return ext == "jpg" or ext == "jpeg"
	if kind == "webp":
		return ext == "webp"
	if kind == "wav":
		return ext == "wav"
	if kind == "ogg":
		return ext == "ogg"
	return false


func _is_polyglot(bytes: PackedByteArray, kind: String) -> bool:
	if kind == "png":
		var end_at: int = _png_iend_end(bytes)
		if end_at < 0:
			return true
		if end_at < bytes.size():
			return true
	elif kind == "jpg":
		var eoi: int = _jpeg_eoi_end(bytes)
		if eoi < 0 or eoi < bytes.size():
			return true
	elif kind == "wav" or kind == "webp":
		if bytes.size() < 8:
			return true
		var declared: int = bytes[4] | (bytes[5] << 8) | (bytes[6] << 16) | (bytes[7] << 24)
		if declared + 8 != bytes.size():
			return true
	if _has_foreign_magic(bytes, kind):
		return true
	return false


func _png_iend_end(bytes: PackedByteArray) -> int:
	if bytes.size() < 8:
		return -1
	var i: int = 8
	while i + 12 <= bytes.size():
		var length: int = (int(bytes[i]) << 24) | (int(bytes[i + 1]) << 16) | (int(bytes[i + 2]) << 8) | int(bytes[i + 3])
		if length < 0 or i + 12 + length > bytes.size():
			return -1
		var is_iend: bool = bytes[i + 4] == 73 and bytes[i + 5] == 69 and bytes[i + 6] == 78 and bytes[i + 7] == 68
		var next: int = i + 12 + length
		if is_iend:
			return next
		i = next
	return -1


func _jpeg_eoi_end(bytes: PackedByteArray) -> int:
	var last: int = -1
	var i: int = 0
	while i + 1 < bytes.size():
		if bytes[i] == 0xFF and bytes[i + 1] == 0xD9:
			last = i + 2
		i += 1
	return last


func _has_foreign_magic(bytes: PackedByteArray, kind: String) -> bool:
	var start: int = 8
	if kind == "jpg":
		start = 3
	if _find_bytes(bytes, PackedByteArray([0x50, 0x4B, 0x03, 0x04]), start) >= 0:
		return true
	if _find_bytes(bytes, PackedByteArray([0x25, 0x50, 0x44, 0x46]), start) >= 0:
		return true
	if kind != "ogg" and _find_bytes(bytes, PackedByteArray([0x4F, 0x67, 0x67, 0x53]), start) >= 0:
		return true
	if kind != "wav" and kind != "webp" and _find_bytes(bytes, PackedByteArray([0x52, 0x49, 0x46, 0x46]), start) >= 0:
		return true
	return false


func _find_bytes(hay: PackedByteArray, needle: PackedByteArray, start: int) -> int:
	if needle.is_empty() or hay.size() < needle.size():
		return -1
	var i: int = start
	var last: int = hay.size() - needle.size()
	while i <= last:
		var hit: bool = true
		var j: int = 0
		while j < needle.size():
			if hay[i + j] != needle[j]:
				hit = false
				break
			j += 1
		if hit:
			return i
		i += 1
	return -1


func _decode(kind: String, bytes: PackedByteArray) -> Dictionary:
	if kind == "png" or kind == "jpg" or kind == "webp":
		var img: Image = Image.new()
		var err: Error = FAILED
		if kind == "png":
			err = img.load_png_from_buffer(bytes)
		elif kind == "jpg":
			err = img.load_jpg_from_buffer(bytes)
		else:
			err = img.load_webp_from_buffer(bytes)
		if err != OK:
			return {"ok": false, "message": "image decode failed: %s" % error_string(err)}
		if img.get_width() < 1 or img.get_height() < 1:
			return {"ok": false, "message": "decoded image has no pixels"}
		return {"ok": true}
	if kind == "wav":
		if bytes.size() < 44:
			return {"ok": false, "message": "WAV header truncated"}
		return {"ok": true}
	if kind == "ogg":
		if bytes.size() < 28:
			return {"ok": false, "message": "OGG header truncated"}
		return {"ok": true}
	return {"ok": false, "message": "unsupported kind"}


func _license_of(source: String, params: Dictionary) -> Dictionary:
	var declared: String = str(params.get("license", ""))
	var manifest: String = ""
	var candidates: PackedStringArray = PackedStringArray()
	candidates.append(source + ".license.json")
	candidates.append(source.get_basename() + ".license.json")
	var i: int = 0
	while i < candidates.size():
		var item: String = candidates[i]
		if FileAccess.file_exists(item):
			manifest = item
			if declared.is_empty():
				var text: String = FileAccess.get_file_as_string(item)
				if text.contains("license"):
					declared = "manifest"
			break
		i += 1
	if declared.is_empty():
		declared = "unknown"
	return {"license": declared, "manifest": manifest}


func _promote(command_id: String, dest: String, bytes: PackedByteArray) -> Dictionary:
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "destination already exists", dest)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create destination directory", dest)
	var tmp: String = dest + ".tmp"
	var tmp_abs: String = ProjectSettings.globalize_path(tmp)
	var dest_abs: String = ProjectSettings.globalize_path(dest)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot open dest tmp", tmp)
	f.store_buffer(bytes)
	f.flush()
	f.close()
	var wrote: PackedByteArray = FileAccess.get_file_as_bytes(tmp)
	if wrote.size() != bytes.size() or _sha256_bytes(wrote) != _sha256_bytes(bytes):
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "tmp write did not match intended bytes")
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "atomic promote rename failed: %s" % error_string(ren))
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	if not FileAccess.file_exists(dest):
		return _unverified(command_id, "dest missing after atomic promote")
	return {"ok": true}


func _wait_import(
	command_id: String,
	dest: String,
	pause_gate: HHAgentPauseGate,
	timeout_ms: int,
) -> Dictionary:
	var efs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	if efs == null:
		return _unverified(command_id, "EditorFileSystem missing")
	efs.update_file(dest)
	var files: PackedStringArray = PackedStringArray()
	files.append(dest)
	if efs.has_method("reimport_files"):
		efs.reimport_files(files)
	var t0: int = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < timeout_ms:
		if _job_token != command_id:
			return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, "late import must not commit an old job", dest)
		if pause_gate != null and pause_gate.is_paused():
			return _errors.fail(command_id, HHAgentErrors.E_PAUSED, "import cancelled at pause safe-point", "pause")
		if FileAccess.file_exists(dest + ".import") and ResourceLoader.exists(dest):
			return {"ok": true}
		if efs.is_scanning() == false:
			efs.update_file(dest)
			if efs.has_method("scan_changes"):
				efs.scan_changes()
		OS.delay_msec(POLL_MS)
	return _errors.fail(command_id, HHAgentErrors.E_BUSY, "importer wait timed out", dest)


func _rename(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var src: String = str(params.get("path", ""))
	var name_s: String = str(params.get("name", ""))
	var jail: Dictionary = _jail_dest(command_id, src)
	if jail.get("ok", false) != true:
		return jail
	if name_s.is_empty():
		return _errors.fail(command_id, HHAgentErrors.E_MISSING_REQUIRED, "name is required", "params.name")
	var ext: String = "." + src.get_extension()
	var dest: String = src.get_base_dir().rstrip("/") + "/" + name_s + ext
	return _move(command_id, src, dest, params.get("rewrite_plan", false) == true, post)


func _delete(command_id: String, params: Dictionary, post: String) -> Dictionary:
	var res_path: String = str(params.get("path", ""))
	var jail: Dictionary = _jail_dest(command_id, res_path)
	if jail.get("ok", false) != true:
		return jail
	if not FileAccess.file_exists(res_path):
		return _unverified(command_id, "asset missing")
	var refs: PackedStringArray = _referencers(res_path)
	if refs.size() > 0:
		return _errors.fail(
			command_id,
			HHAgentErrors.E_CONFLICT,
			"refusing delete of still-referenced asset; quarantine is not a silent remove",
			res_path,
		)
	var quarantined: Dictionary = _quarantine_path(command_id, res_path)
	if quarantined.get("ok", false) != true:
		return quarantined
	_meta.refresh_fs(res_path)
	if FileAccess.file_exists(res_path):
		return _unverified(command_id, "asset still on disk after quarantine")
	var after: Dictionary = {
		"path": res_path,
		"absent": true,
		"quarantined": true,
		"quarantine_path": str(quarantined.get("dest", "")),
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _move(command_id: String, src: String, dest: String, rewrite_plan: bool, post: String) -> Dictionary:
	var src_jail: Dictionary = _jail_dest(command_id, src)
	if src_jail.get("ok", false) != true:
		return src_jail
	var dest_jail: Dictionary = _jail_dest(command_id, dest)
	if dest_jail.get("ok", false) != true:
		return dest_jail
	if not FileAccess.file_exists(src):
		return _unverified(command_id, "source missing")
	if FileAccess.file_exists(dest):
		return _errors.fail(command_id, HHAgentErrors.E_CONFLICT, "destination already exists", dest)
	var refs: PackedStringArray = _referencers(src)
	var rewritten: int = 0
	var rewritten_paths: Array = []
	if refs.size() > 0:
		if not rewrite_plan:
			return _errors.fail(
				command_id,
				HHAgentErrors.E_CONFLICT,
				"asset is still referenced; pass rewrite_plan for atomic rewrite",
				src,
			)
		var planned: Dictionary = _rewrite_refs(command_id, src, dest, refs)
		if planned.get("ok", false) != true:
			return planned
		rewritten = int(planned.get("rewritten", 0))
		var paths_v: Variant = planned.get("paths", [])
		if paths_v is Array:
			rewritten_paths = paths_v as Array
	var uid_text: String = _uid_of(src)
	var uid_id: int = ResourceUID.INVALID_ID
	if not uid_text.is_empty():
		uid_id = ResourceUID.text_to_id(uid_text)
	var live: Resource = _load_res(src)
	var dir_err: Error = _meta.ensure_parent_dir(dest)
	if dir_err != OK:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create destination directory", dest)
	var rename_err: Error = DirAccess.rename_absolute(
		ProjectSettings.globalize_path(src), ProjectSettings.globalize_path(dest)
	)
	if rename_err != OK:
		return _unverified(command_id, "move failed: %s" % error_string(rename_err))
	_move_sidecar(src + ".import", dest + ".import")
	_move_sidecar(src + ".uid", dest + ".uid")
	if uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
	if live != null and live.has_method("take_over_path"):
		live.take_over_path(dest)
	_meta.refresh_fs(src)
	_meta.refresh_fs(dest)
	if FileAccess.file_exists(src) or not FileAccess.file_exists(dest):
		return _unverified(command_id, "move did not relocate the file")
	var new_uid: String = _uid_of(dest)
	if new_uid.is_empty() and uid_id != ResourceUID.INVALID_ID:
		ResourceUID.set_id(uid_id, dest)
		new_uid = ResourceUID.id_to_text(uid_id)
	if not uid_text.is_empty() and not new_uid.is_empty() and uid_text != new_uid:
		return _unverified(command_id, "UID changed during move")
	var after: Dictionary = {
		"path": dest,
		"from": src,
		"uid": new_uid,
		"old_path_absent": true,
		"disk_hash": _meta.disk_hash(dest),
		"rewritten": rewritten,
		"rewritten_paths": rewritten_paths,
		"source": "editor",
	}
	return _errors.ok_changed(command_id, _checks(post), after, true)


func _rewrite_refs(command_id: String, src: String, dest: String, refs: PackedStringArray) -> Dictionary:
	var backups: Array[Dictionary] = []
	var paths: Array = []
	var open_scenes: Dictionary = {}
	for scene_path: String in EditorInterface.get_open_scenes():
		open_scenes[scene_path] = true
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null and not edited.scene_file_path.is_empty():
		open_scenes[edited.scene_file_path] = true
	for item: String in refs:
		var item_jail: Dictionary = _meta.jail(command_id, item)
		if item_jail.get("ok", false) != true:
			_restore_rewrites(backups)
			return item_jail
		if not FileAccess.file_exists(item):
			continue
		if open_scenes.has(item):
			continue
		var text: String = FileAccess.get_file_as_string(item)
		if not text.contains(src):
			continue
		var next_text: String = text.replace(src, dest)
		if next_text == text:
			continue
		var wr: Dictionary = _atomic_text_replace(command_id, item, next_text)
		if wr.get("ok", false) != true:
			_restore_rewrites(backups)
			return wr
		backups.append({"path": item, "bak": str(wr.get("bak", ""))})
		paths.append(item)
	_drop_rewrite_baks(backups)
	return {"ok": true, "rewritten": backups.size(), "paths": paths}


func _drop_rewrite_baks(backups: Array[Dictionary]) -> void:
	for row: Dictionary in backups:
		var bak: String = str(row.get("bak", ""))
		if bak.is_empty() or not FileAccess.file_exists(bak):
			continue
		DirAccess.remove_absolute(ProjectSettings.globalize_path(bak))


func _atomic_text_replace(command_id: String, dest: String, contents: String) -> Dictionary:
	var bytes: PackedByteArray = contents.to_utf8_buffer()
	var tmp: String = dest + ".tmp"
	var bak: String = dest + ".hh-bak"
	var tmp_abs: String = ProjectSettings.globalize_path(tmp)
	var dest_abs: String = ProjectSettings.globalize_path(dest)
	var bak_abs: String = ProjectSettings.globalize_path(bak)
	if FileAccess.file_exists(tmp):
		DirAccess.remove_absolute(tmp_abs)
	var f: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot open rewrite tmp", tmp)
	f.store_buffer(bytes)
	f.flush()
	f.close()
	var wrote: PackedByteArray = FileAccess.get_file_as_bytes(tmp)
	if wrote.size() != bytes.size():
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "rewrite tmp size mismatch")
	if FileAccess.file_exists(bak):
		DirAccess.remove_absolute(bak_abs)
	var bak_err: Error = DirAccess.rename_absolute(dest_abs, bak_abs)
	if bak_err != OK:
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "could not park file for atomic rewrite")
	var ren: Error = DirAccess.rename_absolute(tmp_abs, dest_abs)
	if ren != OK:
		DirAccess.rename_absolute(bak_abs, dest_abs)
		DirAccess.remove_absolute(tmp_abs)
		return _unverified(command_id, "atomic rewrite rename failed")
	return {"ok": true, "bak": bak}


func _restore_rewrites(backups: Array[Dictionary]) -> void:
	var i: int = backups.size() - 1
	while i >= 0:
		var row: Dictionary = backups[i]
		var dest: String = str(row.get("path", ""))
		var bak: String = str(row.get("bak", ""))
		if dest.is_empty() or bak.is_empty():
			i -= 1
			continue
		if FileAccess.file_exists(bak):
			if FileAccess.file_exists(dest):
				DirAccess.remove_absolute(ProjectSettings.globalize_path(dest))
			DirAccess.rename_absolute(ProjectSettings.globalize_path(bak), ProjectSettings.globalize_path(dest))
		i -= 1


func _quarantine_path(command_id: String, res_path: String) -> Dictionary:
	var dest_dir: String = _quarantine_dir(command_id)
	var mk: Error = DirAccess.make_dir_recursive_absolute(dest_dir)
	if mk != OK and mk != ERR_ALREADY_EXISTS:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot create quarantine directory", dest_dir)
	var dest: String = dest_dir.path_join(res_path.get_file())
	var ren: Error = DirAccess.rename_absolute(ProjectSettings.globalize_path(res_path), dest)
	if ren != OK:
		return _unverified(command_id, "quarantine rename failed: %s" % error_string(ren))
	if FileAccess.file_exists(res_path + ".import"):
		DirAccess.rename_absolute(ProjectSettings.globalize_path(res_path + ".import"), dest + ".import")
	if FileAccess.file_exists(res_path + ".uid"):
		DirAccess.rename_absolute(ProjectSettings.globalize_path(res_path + ".uid"), dest + ".uid")
	var uid_id: int = ResourceLoader.get_resource_uid(res_path)
	if uid_id != ResourceUID.INVALID_ID and ResourceUID.has_id(uid_id):
		ResourceUID.remove_id(uid_id)
	return {"ok": true, "dest": dest}


func _quarantine_new(res_path: String, command_id: String) -> void:
	if res_path.is_empty() or not FileAccess.file_exists(res_path):
		return
	_quarantine_path(command_id, res_path)


func _move_sidecar(src: String, dest: String) -> void:
	if FileAccess.file_exists(src):
		DirAccess.rename_absolute(ProjectSettings.globalize_path(src), ProjectSettings.globalize_path(dest))


func _jail_dest(command_id: String, dest: String) -> Dictionary:
	var simple: String = dest.simplify_path()
	if simple.contains("..") or not simple.begins_with("res://"):
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "path escapes via ..", dest)
	return _meta.jail(command_id, dest)


func _referencers(res_path: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var uid_text: String = _uid_of(res_path)
	var files: PackedStringArray = PackedStringArray()
	_collect_files("res://", files)
	_append_text_owners(files)
	for item: String in files:
		if item == res_path or item == res_path + ".uid" or item == res_path + ".import":
			continue
		if _file_refs(item, res_path, uid_text):
			out.append(item)
	var edited: Node = EditorInterface.get_edited_scene_root()
	if edited != null:
		var live: Resource = _load_res(res_path)
		if live != null and _count_in_tree(edited, live) > 0:
			var scene_p: String = edited.scene_file_path
			if not scene_p.is_empty() and not (scene_p in out):
				out.append(scene_p)
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


func _append_text_owners(out: PackedStringArray) -> void:
	# project.godot / export_presets.cfg are text owners (autoload, icon, presets).
	var owners: PackedStringArray = PackedStringArray()
	owners.append("res://project.godot")
	owners.append("res://export_presets.cfg")
	for item: String in owners:
		if not FileAccess.file_exists(item):
			continue
		if item in out:
			continue
		out.append(item)


func _collect_files(dir_path: String, out: PackedStringArray) -> void:
	if dir_path == "res://":
		_append_text_owners(out)
	var abs_dir: String = ProjectSettings.globalize_path(dir_path)
	var da: DirAccess = DirAccess.open(abs_dir)
	if da == null:
		da = DirAccess.open(dir_path)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if name_s == "." or name_s == "..":
			name_s = da.get_next()
			continue
		if name_s.begins_with("."):
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
		elif (
			name_s.ends_with(".tscn")
			or name_s.ends_with(".scn")
			or name_s.ends_with(".tres")
			or name_s.ends_with(".res")
			or name_s.ends_with(".gd")
		):
			out.append(child)
		name_s = da.get_next()
	da.list_dir_end()


func _count_in_tree(root: Node, res: Resource) -> int:
	var n: int = 0
	var walk_seen: Dictionary = {}
	var stack: Array = [root]
	while not stack.is_empty():
		var node_v: Variant = stack.pop_back()
		if not (node_v is Node):
			continue
		var node: Node = node_v
		n += _count_on_object(node, res, walk_seen)
		var i: int = 0
		while i < node.get_child_count():
			stack.append(node.get_child(i))
			i += 1
	return n


func _count_on_object(obj: Object, res: Resource, walk_seen: Dictionary) -> int:
	if obj == null or res == null:
		return 0
	var key: int = obj.get_instance_id()
	if walk_seen.has(key):
		return 0
	walk_seen[key] = true
	var n: int = 0
	for item_v: Variant in obj.get_property_list():
		if not (item_v is Dictionary):
			continue
		var info: Dictionary = item_v
		if int(info.get("type", 0)) != TYPE_OBJECT:
			continue
		var val: Variant = obj.get(str(info.get("name", "")))
		if val is Resource:
			var other: Resource = val as Resource
			if other == res:
				n += 1
			elif not res.resource_path.is_empty() and other.resource_path == res.resource_path:
				n += 1
			else:
				n += _count_on_object(other, res, walk_seen)
	return n


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


func _uid_of(res_path: String) -> String:
	if res_path.is_empty():
		return ""
	var id: int = ResourceLoader.get_resource_uid(res_path)
	if id != ResourceUID.INVALID_ID:
		return ResourceUID.id_to_text(id)
	return ""


func _staging_dir(command_id: String) -> String:
	return _agent_os_dir().path_join("staging").path_join(command_id)


func _quarantine_dir(command_id: String) -> String:
	return _agent_os_dir().path_join("quarantine").path_join(command_id)


func _agent_os_dir() -> String:
	var root: String = ProjectSettings.globalize_path("res://").rstrip("/\\")
	return root.path_join(".hh-agent")


func _cleanup_staging(staging_dir: String) -> void:
	if staging_dir.is_empty():
		return
	var da: DirAccess = DirAccess.open(staging_dir)
	if da == null:
		return
	da.list_dir_begin()
	var name_s: String = da.get_next()
	while name_s != "":
		if name_s != "." and name_s != "..":
			DirAccess.remove_absolute(staging_dir.path_join(name_s))
		name_s = da.get_next()
	da.list_dir_end()
	DirAccess.remove_absolute(staging_dir)


func _write_abs_bytes(command_id: String, abs_path: String, bytes: PackedByteArray) -> Dictionary:
	var f: FileAccess = FileAccess.open(abs_path, FileAccess.WRITE)
	if f == null:
		return _errors.fail(command_id, HHAgentErrors.E_PATH, "cannot write staging file", abs_path)
	f.store_buffer(bytes)
	f.flush()
	f.close()
	return {"ok": true}


func _sha256_bytes(bytes: PackedByteArray) -> String:
	var ctx: HashingContext = HashingContext.new()
	var start_err: Error = ctx.start(HashingContext.HASH_SHA256)
	if start_err != OK:
		return ""
	ctx.update(bytes)
	return ctx.finish().hex_encode()


func _unverified(command_id: String, message: String) -> Dictionary:
	return _errors.fail(command_id, HHAgentErrors.E_UNVERIFIED, message, "")


func _checks(post: String) -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	out.append(post)
	return out
