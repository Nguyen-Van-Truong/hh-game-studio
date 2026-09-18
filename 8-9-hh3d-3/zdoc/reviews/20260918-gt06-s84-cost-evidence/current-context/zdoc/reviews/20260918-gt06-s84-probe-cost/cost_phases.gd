# Diagnostic overlay only. External host samples RSS at each phase before ACK.
var _cost_phase: int = -1
var _cost_due: int = 0
var _cost_waiting: bool = false


func _cost_begin() -> void:
    _cost_phase = 0
    _cost_due = Time.get_ticks_usec() + 2000000


func _cost_tick() -> bool:
    if _cost_phase < 0:
        return false
    _heartbeat()
    var now: int = Time.get_ticks_usec()
    if now < _cost_due:
        return true
    if not _cost_waiting:
        var receipt: Dictionary = _write_new("cost-%02d.json" % _cost_phase,
            {"run_id": _input.run_id, "pid": OS.get_process_id(), "phase": _cost_phase,
            "label": ["before", "retained", "released"][_cost_phase],
            "objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
            "resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
            "static_memory_bytes": OS.get_static_memory_usage(),
            "mono_us": now, "formal_acceptance": false})
        if receipt.is_empty():
            _fail("COST_RECEIPT")
            return true
        _cost_waiting = true
        _cost_due = now + 10000
        return true
    var ack: String = ACK_DIRECTORY.path_join("cost-%02d.ack" % _cost_phase)
    if not FileAccess.file_exists(ack):
        return true
    if FileAccess.get_file_as_string(ack) != _input.run_id:
        _fail("COST_ACK_BINDING")
        return true
    if _cost_phase == 0:
        _object_probe_sample("cost_baseline", true)
    elif _cost_phase == 1:
        _object_probe_clear_retained()
    else:
        _cost_phase = -1
        _advance_batch()
        return true
    if _failed:
        return true
    _cost_phase += 1
    _cost_waiting = false
    _cost_due = Time.get_ticks_usec() + 2000000
    return true
