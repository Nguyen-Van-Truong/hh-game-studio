@tool
extends EditorPlugin
## Diagnostic only: no scene create/undo/save/reload, no HTTP workload.
const DURATION_US: int = 720000000
var active: bool = false
var started_us: int = 0
var next_sample_us: int = 0
var sample_count: int = 0
var filesystem_changes: int = 0

func _enter_tree() -> void:
    active = OS.get_cmdline_user_args() == PackedStringArray(["--hh-s188-idle"])
    set_process(active)
    if active:
        started_us = Time.get_ticks_usec()
        EditorInterface.get_resource_filesystem().filesystem_changed.connect(_filesystem_changed)
        print("HH_S188_READY " + JSON.stringify({"pid": OS.get_process_id(), "duration_us": DURATION_US, "native_us": started_us, "workload": "idle_editor", "engine_version": Engine.get_version_info()}))

func _filesystem_changed() -> void:
    filesystem_changes += 1

func _process(_delta: float) -> void:
    var now: int = Time.get_ticks_usec()
    if now < next_sample_us:
        return
    next_sample_us = now + 1000000
    var fs: EditorFileSystem = EditorInterface.get_resource_filesystem()
    var elapsed: int = now - started_us
    var row: Dictionary = {"pid": OS.get_process_id(), "native_us": now,
        "elapsed_us": elapsed, "sequence": sample_count,
        "process_frame": Engine.get_process_frames(), "scanning": fs.is_scanning(),
        "importing": fs.is_importing(), "filesystem_changes": filesystem_changes,
        "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
        "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT))}
    sample_count += 1
    print("HH_S188_IDLE " + JSON.stringify(row))
    if elapsed >= DURATION_US:
        set_process(false)
        print("HH_S188_COMPLETE " + JSON.stringify({"pid": OS.get_process_id(), "sample_count": sample_count, "elapsed_us": elapsed, "formal_acceptance": false}))
        get_tree().quit(0)
