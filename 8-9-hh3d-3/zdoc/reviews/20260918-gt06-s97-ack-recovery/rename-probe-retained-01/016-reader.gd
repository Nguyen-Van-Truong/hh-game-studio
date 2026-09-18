extends SceneTree

var _began: int = 0
var _finished: bool = false


func _digest(raw: PackedByteArray) -> String:
    var context := HashingContext.new()
    context.start(HashingContext.HASH_SHA256)
    context.update(raw)
    return context.finish().hex_encode()


func _read_one(path: String, stage: String) -> Dictionary:
    var exists: bool = FileAccess.file_exists(path)
    var began: int = Time.get_ticks_usec()
    var file: FileAccess = FileAccess.open(path, FileAccess.READ)
    var error: Error = FileAccess.get_open_error()
    var row: Dictionary = {"stage": stage, "exists": exists, "opened": file != null,
        "open_error": int(error), "started_mono_us": began, "size": null,
        "read_size": null, "read_error": null, "sha256": null, "closed": file == null}
    if file != null:
        var size: int = file.get_length()
        row["size"] = size
        if size >= 0 and size <= 8192:
            var raw: PackedByteArray = file.get_buffer(size)
            row["read_error"] = int(file.get_error())
            row["read_size"] = raw.size()
            row["sha256"] = _digest(raw)
        file.close()
        row["closed"] = true
    row["ended_mono_us"] = Time.get_ticks_usec()
    return row


func _initialize() -> void:
    _began = Time.get_ticks_usec()
    var control: Dictionary = _read_one("res://control.json", "python_read_handle_control")
    var held: Dictionary = _read_one("res://renamed.json", "delete_handle_held")
    print("HH_S97_HELD " + JSON.stringify({"pid": OS.get_process_id(),
        "engine": Engine.get_version_info(), "control": control, "held": held,
        "formal_acceptance": false}))


func _process(_delta: float) -> bool:
    if _finished:
        return false
    if Time.get_ticks_usec() - _began > 15000000:
        _finished = true
        print("HH_S97_TIMEOUT " + JSON.stringify({"pid": OS.get_process_id(), "formal_acceptance": false}))
        quit(86)
        return false
    if FileAccess.file_exists("res://release.flag"):
        _finished = true
        var released: Dictionary = _read_one("res://renamed.json", "delete_handle_released")
        print("HH_S97_RELEASED " + JSON.stringify({"pid": OS.get_process_id(),
            "released": released, "formal_acceptance": false}))
        quit(0)
    return false
