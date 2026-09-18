@tool
extends "res://addons/hh_benchmark/benchmark_native.gd"
## Reader fixture only: inherited candidate methods, real adapter/root/files.
## Successful advance is intercepted before any native cycle or next batch.

var _case_config: Dictionary = {}
var _case_ready: bool = false
var _case_done: bool = false
var _case_settle_us: int = 0
var _case_settle_root: int = 0
var _case_deadline_us: int = 0
var _case_pending_frames: int = 0
var _case_pending_objects_first: int = -1
var _case_pending_objects_last: int = -1
var _case_pending_resources_first: int = -1
var _case_pending_resources_last: int = -1
var _case_advances: int = 0


func _enter_tree() -> void:
    if not OS.get_cmdline_user_args().has("--hh-reader-regression"):
        set_process(false)
        return
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://benchmark/reader-case.json"))
    if not parsed is Dictionary:
        get_tree().quit(87)
        return
    _case_config = parsed
    _mode = "full"
    _run_started_us = Time.get_ticks_usec()
    _input = _case_config.binding
    set_process(true)


func _process(delta: float) -> void:
    if _case_done:
        return
    if not _case_ready:
        _prepare_reader_case()
        return
    # Host arms only after publishing bytes and acquiring its actual handle.
    # This fixture gate is outside the candidate reader and supplies no ACK.
    if not FileAccess.file_exists("res://benchmark/input/reader-armed.json"):
        if Time.get_ticks_usec() > _case_deadline_us:
            _fail("READER_FIXTURE_ARM_TIMEOUT")
        return
    var previous_attempts: int = _host_open_attempts
    super._process(delta)
    if _host_open_attempts - previous_attempts > 1:
        _fail("READER_FIXTURE_MULTIPLE_OPENS_PER_FRAME")
    if not _case_done and _host_open_first_us > 0 and not _host_open_recovered:
        _case_pending_frames += 1
        var objects: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
        var resources: int = int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT))
        if _case_pending_objects_first < 0:
            _case_pending_objects_first = objects
            _case_pending_resources_first = resources
        _case_pending_objects_last = objects
        _case_pending_resources_last = resources


func _prepare_reader_case() -> void:
    var root: Node = EditorInterface.get_edited_scene_root()
    if root == null:
        return
    if _adapter == null:
        _adapter = _find_adapter()
    if _adapter == null:
        return
    var snapshot: Dictionary = _adapter.inspect_scene()
    if not _good_snapshot(snapshot):
        return
    if _case_settle_root != root.get_instance_id():
        _case_settle_root = root.get_instance_id()
        _case_settle_us = Time.get_ticks_usec()
        return
    if Time.get_ticks_usec() - _case_settle_us < SETTLE_US:
        return
    _baseline_revision = str(snapshot.revision)
    _last_root_id = root.get_instance_id()
    _batch = 0
    var issued: int = Time.get_ticks_usec()
    # Near-deadline fixtures exercise the unchanged absolute deadline checks;
    # production HOST_*_TIMEOUT_US constants are not modified.
    _case_deadline_us = issued + (2500000 if _case_config.case == "locked_timeout" else 10000000)
    var scene_hash: String = FileAccess.get_sha256(SCENE)
    var payload: Dictionary
    if _case_config.stage == "start":
        _start_offer = {"issued_mono_us": issued, "deadline_mono_us": _case_deadline_us,
            "root_instance_id": _last_root_id, "generation": int(snapshot.generation),
            "scene_file_sha256": scene_hash, "start_file": "benchmark/input/start-00.json"}
        var ready: Dictionary = _write_new("ready-00.json", _start_offer)
        _start_offer_sha256 = str(ready.sha256)
        payload = {"schema_id": "hh-studio.native-cycle-batch-start", "schema_version": "1.0.0",
            "run_id": _input.run_id, "batch_index": 0,
            "source_closure_sha256": _input.source_closure_sha256, "profile_sha256": _input.profile_sha256,
            "command_batch_sha256": "c".repeat(64), "ready_sha256": _start_offer_sha256,
            "deadline_mono_us": _case_deadline_us}
        _set_phase(Phase.HOST_START)
    else:
        var batch_file: Dictionary = _write_new("reader-native-batch.json", {"reader_fixture": true})
        _pending_batch_sha256 = str(batch_file.sha256)
        _cycles.assign([{"saved_file_sha256": scene_hash}])
        _barrier = {"issued_mono_us": issued, "deadline_mono_us": _case_deadline_us,
            "root_instance_id": _last_root_id, "generation": int(snapshot.generation),
            "ack_file": "benchmark/input/ack-00.json"}
        payload = {"schema_id": "hh-studio.native-cycle-batch-ack", "schema_version": "1.0.0",
            "run_id": _input.run_id, "batch_index": 0, "native_batch_sha256": _pending_batch_sha256,
            "source_closure_sha256": _input.source_closure_sha256, "profile_sha256": _input.profile_sha256,
            "deadline_mono_us": _case_deadline_us}
        _set_phase(Phase.HOST_BARRIER)
    _case_ready = true
    _write_new("reader-ready.json", {"payload": payload, "stage": _case_config.stage,
        "case": _case_config.case, "deadline_mono_us": _case_deadline_us,
        "source_candidate_sha256": _case_config.source_candidate_sha256})


func _host_input_open_log(event: String, code: String) -> void:
    super._host_input_open_log(event, code)
    if event == "pending":
        # One fixture synchronization artifact, never a per-attempt history.
        _write_new("reader-pending.json", {"attempts": _host_open_attempts,
            "first_error": _host_open_first_error, "first_mono_us": _host_open_first_us})


func _start_native_batch() -> void:
    _case_advances += 1
    _complete_reader_case("success", "START_VALIDATED")


func _advance_batch() -> void:
    _case_advances += 1
    _complete_reader_case("success", "ACK_VALIDATED")


func _fail(code: String) -> void:
    if not _case_done:
        _write_reader_result("failed", code)
    # Keep the real candidate failure artifact, terminal diagnostic and exit86.
    super._fail(code)


func _complete_reader_case(status: String, code: String) -> void:
    _write_reader_result(status, code)
    _phase = Phase.FINISHED
    get_tree().quit(0)


func _write_reader_result(status: String, code: String) -> void:
    if _case_done:
        return
    _case_done = true
    var deadline: int = int(_start_offer.get("deadline_mono_us", 0)) if _case_config.stage == "start" else int(_barrier.get("deadline_mono_us", 0))
    _write_new("reader-result.json", {"schema": "HH-S97-NATIVE-READER-REGRESSION-1",
        "formal_acceptance": false, "native_benchmark": false, "case": _case_config.case,
        "stage": _case_config.stage, "status": status, "code": code,
        "source_candidate_sha256": _case_config.source_candidate_sha256,
        "buffer_shortening_injected": _case_config.case in ["short_read", "locked_short_read"], "pid": OS.get_process_id(),
        "monotonic_us": Time.get_ticks_usec(), "process_frame": Engine.get_process_frames(),
        "deadline_before_us": _case_deadline_us, "deadline_after_us": deadline,
        "attempts": _host_open_attempts, "first_error": _host_open_first_error,
        "first_error_mono_us": _host_open_first_us, "first_error_frame": _host_open_first_frame,
        "open_recovered": _host_open_recovered, "pending_frames": _case_pending_frames,
        "pending_objects_first": _case_pending_objects_first, "pending_objects_last": _case_pending_objects_last,
        "pending_resources_first": _case_pending_resources_first, "pending_resources_last": _case_pending_resources_last,
        "advances": _case_advances, "start_receipts": _start_receipts,
        "ack_receipts": _barrier_receipts, "max_heartbeat_gap_us": _max_status_gap_us})
