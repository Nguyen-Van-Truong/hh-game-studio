class_name MapAuthor
extends RefCounted

## Semantic map commands (VF5-WP1). One in-memory writer, unique
## command_id, validate-before-apply, ACK after readback hash.
## Persist is temp+rename under user://. ledger:RL-MAP-AUTHOR.

const _MapCodec: GDScript = preload("res://src/maps/map_codec.gd")
const _MapValidator: GDScript = preload("res://src/maps/map_validator.gd")

const COMMAND_ID: String = "vf.maps.command.v1"
const STORE_DIR: String = "user://vf_maps/"
const LAYERS: PackedStringArray = [
	"solid", "one_way", "ladder", "hazard", "prop"
]

var _store: Dictionary = {}
var _acks: Dictionary = {}
var last_error: String = ""
var last_save_path: String = ""


func apply(req: Dictionary) -> Dictionary:
	var command_id: String = str(req.get("command_id", ""))
	if not RuntimeConstants.command_id_ok(command_id):
		return _reject(req, PackedStringArray(["bad command_id"]))
	if _acks.has(command_id):
		return (_acks[command_id] as Dictionary).duplicate(true)
	var errors: PackedStringArray = _validate_req(req)
	if not errors.is_empty():
		return _reject(req, errors)
	var op: String = str(req.get("op", ""))
	var payload: Dictionary = _dict(req.get("payload", {}))
	if op == "map.create":
		errors = _op_create(payload)
	elif op == "map.paint_rect":
		errors = _op_paint(payload)
	elif op == "map.set_cell":
		errors = _op_set_cell(payload, false)
	elif op == "map.clear_cell":
		errors = _op_set_cell(payload, true)
	elif op == "map.set_spawn":
		errors = _op_spawn(payload)
	elif op == "map.set_pickup":
		errors = _op_pickup(payload)
	elif op == "map.validate":
		errors = _op_validate(payload)
	elif op == "map.serialize":
		return _ack_serialize(req, payload)
	elif op == "map.deserialize":
		errors = _op_deserialize(payload)
	elif op == "map.persist":
		return _ack_persist(req, payload)
	else:
		errors = PackedStringArray(["unknown map op"])
	if not errors.is_empty():
		return _reject(req, errors)
	var map_id: String = str(payload.get("id", ""))
	var doc: Dictionary = document(map_id)
	var digest: String = _MapCodec.stable_hash(doc) if not doc.is_empty() else ""
	var res: Dictionary = _ok(req, {
		"id": map_id,
		"hash": digest,
		"display_name": str(doc.get("display_name", "")),
	})
	_acks[command_id] = res
	return res.duplicate(true)


func document(map_id: String) -> Dictionary:
	if _store.has(map_id):
		return _MapCodec.normalize(_store[map_id] as Dictionary)
	return {}


func has_id(map_id: String) -> bool:
	return _store.has(map_id)


func reset() -> void:
	_store = {}
	_acks = {}
	last_error = ""
	last_save_path = ""


func _validate_req(req: Dictionary) -> PackedStringArray:
	var errors: PackedStringArray = PackedStringArray()
	if str(req.get("schema", COMMAND_ID)) != COMMAND_ID:
		errors.append("map command schema mismatch")
	if str(req.get("op", "")) == "":
		errors.append("map command missing op")
	return errors


func _op_create(payload: Dictionary) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _id_ok(map_id):
		return PackedStringArray(["bad map id"])
	if _store.has(map_id):
		return PackedStringArray([])
	var width: int = int(payload.get("width", 0))
	var height: int = int(payload.get("height", 0))
	var display_name: String = str(payload.get("display_name", map_id))
	var theme: String = str(payload.get("theme", "concrete"))
	if display_name.to_lower().contains("superfighter"):
		return PackedStringArray(["display name uses Superfighters trademark"])
	if width < 1 or height < 1:
		return PackedStringArray(["map create needs width/height"])
	var doc: Dictionary = _MapCodec.empty_doc(map_id, width, height, display_name, theme)
	_store[map_id] = doc
	return PackedStringArray()


func _op_paint(payload: Dictionary) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _store.has(map_id):
		return PackedStringArray(["map %s not created" % map_id])
	var layer: String = str(payload.get("layer", ""))
	if not LAYERS.has(layer):
		return PackedStringArray(["unknown layer %s" % layer])
	var doc: Dictionary = _store[map_id] as Dictionary
	var x: int = int(payload.get("x", 0))
	var y: int = int(payload.get("y", 0))
	var w: int = int(payload.get("w", 1))
	var h: int = int(payload.get("h", 1))
	if w < 1 or h < 1:
		return PackedStringArray(["paint_rect needs positive size"])
	var iy: int = 0
	while iy < h:
		var ix: int = 0
		while ix < w:
			var cx: int = x + ix
			var cy: int = y + iy
			if not _MapCodec.in_bounds(doc, cx, cy):
				return PackedStringArray(["paint_rect %d,%d out of bounds" % [cx, cy]])
			ix += 1
		iy += 1
	iy = 0
	while iy < h:
		var ix2: int = 0
		while ix2 < w:
			_write_cell(doc, layer, x + ix2, y + iy, false)
			ix2 += 1
		iy += 1
	_store[map_id] = _MapCodec.normalize(doc)
	return PackedStringArray()


func _op_set_cell(payload: Dictionary, clear: bool) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _store.has(map_id):
		return PackedStringArray(["map %s not created" % map_id])
	var layer: String = str(payload.get("layer", ""))
	if not LAYERS.has(layer):
		return PackedStringArray(["unknown layer %s" % layer])
	var doc: Dictionary = _store[map_id] as Dictionary
	var x: int = int(payload.get("x", 0))
	var y: int = int(payload.get("y", 0))
	if not _MapCodec.in_bounds(doc, x, y):
		return PackedStringArray(["cell %d,%d out of bounds" % [x, y]])
	_write_cell(doc, layer, x, y, clear)
	_store[map_id] = _MapCodec.normalize(doc)
	return PackedStringArray()


func _op_spawn(payload: Dictionary) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _store.has(map_id):
		return PackedStringArray(["map %s not created" % map_id])
	var doc: Dictionary = _store[map_id] as Dictionary
	var x: int = int(payload.get("x", 0))
	var y: int = int(payload.get("y", 0))
	var slot: int = int(payload.get("slot", 0))
	if not _MapCodec.in_bounds(doc, x, y):
		return PackedStringArray(["spawn out of bounds"])
	if slot < 0 or slot > 3:
		return PackedStringArray(["spawn slot must be 0..3"])
	var layers: Dictionary = doc["layers"] as Dictionary
	var rows: Array = (layers["spawn"] as Array).duplicate()
	var kept: Array = []
	var i: int = 0
	while i < rows.size():
		var cell: Array = rows[i] as Array
		if int(cell[2]) != slot:
			kept.append(cell)
		i += 1
	kept.append([x, y, slot])
	layers["spawn"] = kept
	_store[map_id] = _MapCodec.normalize(doc)
	return PackedStringArray()


func _op_pickup(payload: Dictionary) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _store.has(map_id):
		return PackedStringArray(["map %s not created" % map_id])
	var doc: Dictionary = _store[map_id] as Dictionary
	var x: int = int(payload.get("x", 0))
	var y: int = int(payload.get("y", 0))
	if not _MapCodec.in_bounds(doc, x, y):
		return PackedStringArray(["pickup out of bounds"])
	_write_cell(doc, "pickup", x, y, false)
	_store[map_id] = _MapCodec.normalize(doc)
	return PackedStringArray()


func _op_validate(payload: Dictionary) -> PackedStringArray:
	var map_id: String = str(payload.get("id", ""))
	if not _store.has(map_id):
		return PackedStringArray(["map %s not created" % map_id])
	return _MapValidator.validate_doc(document(map_id), false, true)


func _ack_serialize(req: Dictionary, payload: Dictionary) -> Dictionary:
	var map_id: String = str(payload.get("id", ""))
	var doc: Dictionary = document(map_id)
	if doc.is_empty():
		return _reject(req, PackedStringArray(["map %s not created" % map_id]))
	var res: Dictionary = _ok(req, {
		"id": map_id,
		"hash": _MapCodec.stable_hash(doc),
		"canonical": _MapCodec.serialize(doc),
	})
	_acks[str(req.get("command_id", ""))] = res
	return res.duplicate(true)


func _op_deserialize(payload: Dictionary) -> PackedStringArray:
	var raw: Variant = payload.get("doc", payload.get("canonical", {}))
	var doc: Dictionary = _MapCodec.deserialize(raw)
	var map_id: String = str(doc.get("id", ""))
	if map_id == "":
		return PackedStringArray(["deserialize missing id"])
	_store[map_id] = doc
	return PackedStringArray()


func _ack_persist(req: Dictionary, payload: Dictionary) -> Dictionary:
	var map_id: String = str(payload.get("id", ""))
	var doc: Dictionary = document(map_id)
	if doc.is_empty():
		return _reject(req, PackedStringArray(["map %s not created" % map_id]))
	var filename: String = str(payload.get("filename", map_id + ".json"))
	var stored: String = persist_atomic(filename, doc)
	if stored == "":
		return _reject(req, PackedStringArray([last_error if last_error != "" else "persist failed"]))
	var res: Dictionary = _ok(req, {
		"id": map_id,
		"hash": _MapCodec.stable_hash(doc),
		"store": stored,
	})
	_acks[str(req.get("command_id", ""))] = res
	return res.duplicate(true)


func persist_atomic(filename: String, doc: Dictionary) -> String:
	last_error = ""
	if filename.contains("..") or filename.contains("/") or filename.contains("\\"):
		last_error = "illegal map filename"
		return ""
	if not filename.ends_with(".json"):
		last_error = "map persist must be json"
		return ""
	var errors: PackedStringArray = _MapValidator.validate_doc(doc, false, true)
	if not errors.is_empty():
		last_error = String(errors[0])
		return ""
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(STORE_DIR))
	var rel: String = STORE_DIR + filename
	var tmp: String = rel + ".tmp"
	var file: FileAccess = FileAccess.open(tmp, FileAccess.WRITE)
	if file == null:
		last_error = "map tmp open failed"
		return ""
	file.store_string(JSON.stringify(_MapCodec.normalize(doc)))
	file.close()
	var abs_tmp: String = ProjectSettings.globalize_path(tmp)
	var abs_final: String = ProjectSettings.globalize_path(rel)
	if FileAccess.file_exists(rel):
		DirAccess.remove_absolute(abs_final)
	var err: Error = DirAccess.rename_absolute(abs_tmp, abs_final)
	if err != OK:
		DirAccess.remove_absolute(abs_tmp)
		last_error = "map rename failed"
		return ""
	last_save_path = rel
	return rel


func _write_cell(doc: Dictionary, layer: String, x: int, y: int, clear: bool) -> void:
	var layers: Dictionary = doc["layers"] as Dictionary
	var rows: Array = (layers.get(layer, []) as Array).duplicate()
	var kept: Array = []
	var i: int = 0
	while i < rows.size():
		var cell: Array = rows[i] as Array
		if int(cell[0]) != x or int(cell[1]) != y:
			kept.append(cell)
		i += 1
	if not clear:
		if layer == "spawn":
			kept.append([x, y, 0])
		else:
			kept.append([x, y])
	layers[layer] = kept


func _id_ok(map_id: String) -> bool:
	if map_id.is_empty() or map_id.length() > 48:
		return false
	if map_id.contains("..") or map_id.contains("/") or map_id.contains("\\"):
		return false
	return true


func _ok(req: Dictionary, extra: Dictionary) -> Dictionary:
	var out: Dictionary = {
		"ok": true,
		"command_id": str(req.get("command_id", "")),
		"op": str(req.get("op", "")),
	}
	var keys: Array = extra.keys()
	var i: int = 0
	while i < keys.size():
		out[str(keys[i])] = extra[keys[i]]
		i += 1
	return out


func _reject(req: Dictionary, errors: PackedStringArray) -> Dictionary:
	last_error = String(errors[0]) if not errors.is_empty() else "reject"
	return {
		"ok": false,
		"command_id": str(req.get("command_id", "")),
		"op": str(req.get("op", "")),
		"errors": errors,
	}


func _dict(value: Variant) -> Dictionary:
	if value is Dictionary:
		return value as Dictionary
	return {}
