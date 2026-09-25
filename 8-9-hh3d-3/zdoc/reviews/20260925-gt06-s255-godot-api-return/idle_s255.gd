@tool
extends EditorPlugin
## S255 diagnostic only: CDB attaches before the owned editor resumes.
const DURATION_US: int = 22000000
var active := false
var started_us := 0
var next_sample_us := 0
var sample_count := 0

func _enter_tree() -> void:
    active = OS.get_cmdline_user_args() == PackedStringArray(["--hh-s255-cdb-api"])
    set_process(active)
    if active:
        started_us = Time.get_ticks_usec()
        print("HH_S255_READY " + JSON.stringify({"pid": OS.get_process_id(), "duration_us": DURATION_US, "workload": "cdb_api_entry_return"}))

func _process(_delta: float) -> void:
    var now := Time.get_ticks_usec()
    if now < next_sample_us: return
    next_sample_us = now + 1000000
    sample_count += 1
    print("HH_S255_IDLE " + JSON.stringify({"pid": OS.get_process_id(), "elapsed_us": now - started_us, "sequence": sample_count, "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)), "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT))}))
    if now - started_us >= DURATION_US:
        set_process(false)
        print("HH_S255_COMPLETE " + JSON.stringify({"pid": OS.get_process_id(), "sample_count": sample_count, "elapsed_us": now - started_us, "formal_acceptance": false}))
        get_tree().quit(0)
