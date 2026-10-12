# HH gamekit kit save v1 - self-made (HH Studio)
extends Node
## Versioned JSON saves in user://saves/<slot>.json. Assign `migrate` to upgrade older files.

const SAVE_VERSION: int = 1

## migrate.call(old_version, data) -> Dictionary. Used when the file version is older than SAVE_VERSION.
var migrate: Callable = Callable()


func save_game(slot: String, data: Dictionary) -> Error:
	if not _slot_ok(slot):
		return ERR_INVALID_PARAMETER
	var errs: Array = []
	var normalized: Variant = _normalize(data, 0, errs)
	if not errs.is_empty() or not (normalized is Dictionary):
		return ERR_INVALID_DATA
	var body_data: Dictionary = normalized
	var canon: String = JSON.stringify(body_data, "", true, true)
	if canon.is_empty():
		return ERR_INVALID_DATA
	var dir_abs: String = ProjectSettings.globalize_path("user://saves")
	if not DirAccess.dir_exists_absolute(dir_abs):
		var made: Error = DirAccess.make_dir_recursive_absolute(dir_abs)
		if made != OK:
			return made
	var envelope: Dictionary = {
		"version": SAVE_VERSION,
		"sha256": canon.sha256_text(),
		"data": body_data,
	}
	var text: String = JSON.stringify(envelope, "\t", true, true)
	if text.is_empty():
		return ERR_INVALID_DATA
	var temp_abs: String = ProjectSettings.globalize_path("user://saves/.%s.json.hhtmp" % slot)
	var final_abs: String = ProjectSettings.globalize_path("user://saves/%s.json" % slot)
	var fa: FileAccess = FileAccess.open(temp_abs, FileAccess.WRITE)
	if fa == null:
		return FileAccess.get_open_error()
	fa.store_string(text)
	fa.flush()
	fa.close()
	return _replace(temp_abs, final_abs)


func load_game(slot: String) -> Dictionary:
	if not _slot_ok(slot):
		push_warning("HHSave: bad slot name")
		return {}
	var path: String = _resolve_path(slot)
	if path.is_empty():
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not (parsed is Dictionary):
		push_warning("HHSave: corrupt save (not an object): " + slot)
		return {}
	var body: Dictionary = parsed
	if not body.has("version") or not body.has("sha256") or not (body.get("data") is Dictionary):
		push_warning("HHSave: corrupt save (missing fields): " + slot)
		return {}
	var version: int = int(body["version"])
	var errs: Array = []
	var normalized: Variant = _normalize(body["data"], 0, errs)
	if not errs.is_empty() or not (normalized is Dictionary):
		push_warning("HHSave: corrupt save (unsupported data): " + slot)
		return {}
	var data: Dictionary = normalized
	var canon: String = JSON.stringify(data, "", true, true)
	if canon.is_empty() or canon.sha256_text() != str(body["sha256"]):
		push_warning("HHSave: save hash mismatch (corrupt): " + slot)
		return {}
	if version == SAVE_VERSION:
		return data
	if version > SAVE_VERSION:
		push_warning("HHSave: save version %d is newer than %d" % [version, SAVE_VERSION])
		return {}
	if not migrate.is_valid():
		push_warning("HHSave: save version %d is older than %d and no migrate hook is set" % [version, SAVE_VERSION])
		return {}
	var migrated: Variant = migrate.call(version, data)
	if not (migrated is Dictionary):
		push_warning("HHSave: migrate hook did not return a dictionary")
		return {}
	var errs2: Array = []
	var out: Variant = _normalize(migrated, 0, errs2)
	if not errs2.is_empty() or not (out is Dictionary):
		push_warning("HHSave: migrate hook returned unsupported data")
		return {}
	return out


func list_slots() -> PackedStringArray:
	var out: PackedStringArray = PackedStringArray()
	var da: DirAccess = DirAccess.open("user://saves")
	if da == null:
		return out
	for file_name: String in da.get_files():
		if file_name.begins_with("."):
			continue
		if file_name.ends_with(".json"):
			out.append(file_name.get_basename())
	out.sort()
	return out


func delete_slot(slot: String) -> Error:
	if not _slot_ok(slot):
		return ERR_INVALID_PARAMETER
	var path: String = "user://saves/%s.json" % slot
	var bak: String = "user://saves/.%s.json.bak" % slot
	if not FileAccess.file_exists(path) and not FileAccess.file_exists(bak):
		return ERR_FILE_NOT_FOUND
	# Drop the backup first, or load_game would bring a deleted slot back.
	if FileAccess.file_exists(bak):
		var cleared: Error = DirAccess.remove_absolute(ProjectSettings.globalize_path(bak))
		if cleared != OK:
			return cleared
	if FileAccess.file_exists(path):
		return DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	return OK


func _slot_ok(slot: String) -> bool:
	if slot.is_empty() or slot.length() > 64:
		return false
	for i: int in slot.length():
		var c: String = slot.substr(i, 1)
		var ok: bool = (c >= "a" and c <= "z") or (c >= "A" and c <= "Z") or (c >= "0" and c <= "9") or c == "_" or c == "-"
		if not ok:
			return false
	return true


func _resolve_path(slot: String) -> String:
	var path: String = "user://saves/%s.json" % slot
	if FileAccess.file_exists(path):
		return path
	var bak: String = "user://saves/.%s.json.bak" % slot
	if FileAccess.file_exists(bak):
		push_warning("HHSave: loaded backup for slot " + slot)
		return bak
	return ""

func _backup_abs(final_abs: String) -> String:
	var slash: int = maxi(final_abs.rfind("/"), final_abs.rfind("\\"))
	var file_name: String = final_abs.substr(slash + 1)
	var folder: String = final_abs.substr(0, slash + 1)
	var hidden: String = "." + file_name + ".bak"
	return folder + hidden


## Move the live file aside, then put the temp file in its place.
## Never delete the live file until the new bytes have its name.
func _replace(temp_abs: String, final_abs: String) -> Error:
	var bak_abs: String = _backup_abs(final_abs)
	var backed_up: bool = false
	if FileAccess.file_exists(final_abs):
		if FileAccess.file_exists(bak_abs):
			var cleared: Error = DirAccess.remove_absolute(bak_abs)
			if cleared != OK:
				DirAccess.remove_absolute(temp_abs)
				return cleared
		var parked: Error = DirAccess.rename_absolute(final_abs, bak_abs)
		if parked != OK:
			DirAccess.remove_absolute(temp_abs)
			return parked
		backed_up = true
	var renamed: Error = DirAccess.rename_absolute(temp_abs, final_abs)
	if renamed != OK:
		if backed_up:
			DirAccess.rename_absolute(bak_abs, final_abs)
		DirAccess.remove_absolute(temp_abs)
		return renamed
	if FileAccess.file_exists(bak_abs):
		DirAccess.remove_absolute(bak_abs)
	return OK


## JSON.parse_string turns integers into floats. Fold whole floats back to int so the hash is stable.
func _normalize(value: Variant, depth: int, errs: Array) -> Variant:
	if not errs.is_empty():
		return null
	if depth > 12:
		errs.append("nested too deep")
		return null
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return value
		TYPE_FLOAT:
			var f: float = value
			if is_nan(f) or is_inf(f):
				errs.append("non-finite number")
				return null
			if f == floor(f) and absf(f) < 9007199254740992.0:
				return int(f)
			return f
		TYPE_ARRAY:
			var src: Array = value
			var arr: Array = []
			for item: Variant in src:
				arr.append(_normalize(item, depth + 1, errs))
				if not errs.is_empty():
					return null
			return arr
		TYPE_DICTIONARY:
			var src_d: Dictionary = value
			var out: Dictionary = {}
			for k: Variant in src_d.keys():
				if typeof(k) != TYPE_STRING:
					errs.append("dictionary keys must be strings")
					return null
				out[k] = _normalize(src_d[k], depth + 1, errs)
				if not errs.is_empty():
					return null
			return out
		_:
			errs.append("unsupported type")
			return null
