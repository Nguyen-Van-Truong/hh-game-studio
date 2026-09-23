@tool
extends EditorPlugin
## S198 diagnostic only: short idle editor for a CDB handle-table snapshot.
const DURATION_US: int = 45000000
var active := false
var started_us := 0
var next_sample_us := 0
var sample_count := 0
func _enter_tree() -> void:
    active = OS.get_cmdline_user_args() == PackedStringArray(["--hh-s198-cdb-idle"])
    set_process(active)
    if active:
        started_us = Time.get_ticks_usec()
        print("HH_S198_READY " + JSON.stringify({"pid": OS.get_process_id(), "duration_us": DURATION_US, "workload": "idle_editor_cdb_snapshot", "engine_version": Engine.get_version_info()}))
func _process(_delta: float) -> void:
    var now := Time.get_ticks_usec()
    if now < next_sample_us: return
    next_sample_us = now + 1000000
    sample_count += 1
    print("HH_S198_IDLE " + JSON.stringify({"pid": OS.get_process_id(), "elapsed_us": now - started_us, "sequence": sample_count, "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)), "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT))}))
    if now - started_us >= DURATION_US:
        set_process(false)
        print("HH_S198_COMPLETE " + JSON.stringify({"pid": OS.get_process_id(), "sample_count": sample_count, "elapsed_us": now - started_us, "formal_acceptance": false}))
        get_tree().quit(0)

