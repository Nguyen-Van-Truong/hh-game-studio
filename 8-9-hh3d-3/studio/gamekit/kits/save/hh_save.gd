# HH gamekit kit save v1 - self-made (HH Studio)
extends Node
## Versioned JSON saves in user://saves/<slot>.json. Assign `migrate` to upgrade older files.
## A successful replacement retains the previous valid save as .<slot>.json.bak.

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
	var stored: bool = fa.store_string(text)
	fa.flush()
	var write_error: Error = fa.get_error()
	fa.close()
	if not stored or write_error != OK or FileAccess.get_file_as_string(temp_abs) != text or not _is_valid_save(temp_abs):
		@warning_ignore("return_value_discarded") # failed staging must not replace live or backup
		DirAccess.remove_absolute(temp_abs)
		return write_error if write_error != OK else ERR_FILE_CORRUPT
	return _replace(temp_abs, final_abs)


func load_game(slot: String) -> Dictionary:
	if not _slot_ok(slot):
		push_warning("HHSave: bad slot name")
		return {}
	var path: String = _resolve_path(slot)
	if path.is_empty():
		return {}
	var parser: JSON = JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path)) != OK:
		push_warning("HHSave: corrupt save (invalid JSON): " + slot)
		return {}
	var parsed: Variant = parser.data
	if not (parsed is Dictionary):
		push_warning("HHSave: corrupt save (not an object): " + slot)
		return {}
	var body: Dictionary = parsed
	if not body.has("version") or not body.has("sha256") or not (body.get("data") is Dictionary):
		push_warning("HHSave: corrupt save (missing fields): " + slot)
		return {}
	var version: int = _to_int(body["version"])
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
			@warning_ignore("return_value_discarded") # false means the slot name was not stored
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


func _to_int(value: Variant) -> int:
	var converted: Variant = type_convert(value, TYPE_INT)
	if converted is int:
		return converted
	return 0


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
		# Prefer the live file when its envelope/hash is valid. If a previous
		# interrupted write left a corrupt live file, fall back to the last-good
		# backup instead of silently losing progress.
		if _is_valid_save(ProjectSettings.globalize_path(path)):
			return path
		var backup: String = "user://saves/.%s.json.bak" % slot
		if FileAccess.file_exists(backup) and _is_valid_save(ProjectSettings.globalize_path(backup)):
			push_warning("HHSave: live save is corrupt; loaded last-good backup for slot " + slot)
			return backup
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


func _is_valid_save(path_abs: String) -> bool:
	if not FileAccess.file_exists(path_abs):
		return false
	var parser: JSON = JSON.new()
	if parser.parse(FileAccess.get_file_as_string(path_abs)) != OK:
		return false
	var parsed: Variant = parser.data
	if not (parsed is Dictionary):
		return false
	var body: Dictionary = parsed
	if not body.has("version") or not body.has("sha256") or not (body.get("data") is Dictionary):
		return false
	var raw_version: Variant = body.get("version")
	if not (raw_version is int or raw_version is float):
		return false
	var version: int = _to_int(raw_version)
	if version < 0 or raw_version != version:
		return false
	var errs: Array = []
	var normalized: Variant = _normalize(body["data"], 0, errs)
	if not errs.is_empty() or not (normalized is Dictionary):
		return false
	var canon: String = JSON.stringify(normalized, "", true, true)
	return not canon.is_empty() and canon.sha256_text() == str(body["sha256"])


## Move the live file aside, then put the temp file in its place.
## Never delete the live file until the new bytes have its name.
func _replace(temp_abs: String, final_abs: String) -> Error:
	var bak_abs: String = _backup_abs(final_abs)
	var backed_up: bool = false
	var quarantined_abs: String = final_abs + ".hhtmp-bad"
	if FileAccess.file_exists(quarantined_abs):
		@warning_ignore("return_value_discarded")
		DirAccess.remove_absolute(quarantined_abs)
	if FileAccess.file_exists(final_abs):
		# Never replace an existing last-good backup with a corrupt live file.
		# Quarantine the bad live bytes while publishing, then remove them only
		# after the new file has its final name.
		var park_path: String = bak_abs
		if not _is_valid_save(final_abs):
			park_path = quarantined_abs
		elif FileAccess.file_exists(bak_abs):
			var cleared: Error = DirAccess.remove_absolute(bak_abs)
			if cleared != OK:
				@warning_ignore("return_value_discarded") # publish failed; drop the temp file
				DirAccess.remove_absolute(temp_abs)
				return cleared
		var parked: Error = DirAccess.rename_absolute(final_abs, park_path)
		if parked != OK:
			@warning_ignore("return_value_discarded") # publish failed; drop the temp file
			DirAccess.remove_absolute(temp_abs)
			return parked
		backed_up = park_path == bak_abs
	var placed: Error = DirAccess.rename_absolute(temp_abs, final_abs)
	if placed != OK:
		if backed_up:
			@warning_ignore("return_value_discarded") # put the previous file back and still return the rename error
			DirAccess.rename_absolute(bak_abs, final_abs)
		elif FileAccess.file_exists(quarantined_abs):
			@warning_ignore("return_value_discarded")
			DirAccess.rename_absolute(quarantined_abs, final_abs)
		@warning_ignore("return_value_discarded") # publish failed; drop the temp file
		DirAccess.remove_absolute(temp_abs)
		return placed
	if FileAccess.file_exists(quarantined_abs):
		@warning_ignore("return_value_discarded") # corrupt bytes are no longer recoverable
		DirAccess.remove_absolute(quarantined_abs)
	# Keep bak_abs intentionally: it is the last-good recovery point for a
	# later interrupted/corrupt write. The next valid save rotates it.
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
