@tool
extends EditorPlugin
## Fault-injected ordering test, not a real editor save or latency reproducer.
## The copied subject differs only at the save API call. All phase logic is real.

class ReadbackAdapter extends "res://addons/hh_studio/plugin.gd":
    var reads: int = 0

    func inspect_scene(_offset: int = 0, _limit: int = 64) -> Dictionary:
        reads += 1
        return {"ok": true, "held": false, "revision": "sha256:" + "a".repeat(64), "generation": 1}

class Subject extends "res://addons/hh_benchmark/benchmark_native.gd":
    var scenario: String = "sync_ok"
    var failure: String = ""
    var observations: Array[Dictionary] = []

    func _test_save_scene() -> Error:
        if scenario != "delayed_signal":
            _on_scene_saved("res://wrong.tscn" if scenario == "wrong_signal" else SCENE)
        if scenario == "duplicate_signal":
            _on_scene_saved(SCENE)
        if scenario == "phase_timeout":
            _phase_started_us -= PHASE_TIMEOUT_US + 1
        _process(0.0)
        observations.append({"phase": Phase.keys()[_phase], "reads": _adapter.get("reads"),
            "failed": _failed, "save_recorded": _row.has("saved_file_sha256")})
        return ERR_CANT_CREATE if scenario == "sync_error" else OK

    func _fail(code: String) -> void:
        if not _failed:
            failure = code
            _failed = true
            _phase = Phase.FINISHED

var _checks: Array[Dictionary] = []
var _rows: Array[Dictionary] = []

func _enter_tree() -> void:
    call_deferred("_run")

func _check(name: String, passed: bool) -> void:
    _checks.append({"name": name, "passed": passed})

func _subject(scenario: String) -> Subject:
    var subject := Subject.new()
    subject._adapter = ReadbackAdapter.new()
    subject.scenario = scenario
    subject._baseline_revision = "sha256:" + "a".repeat(64)
    subject._run_started_us = Time.get_ticks_usec()
    subject._row = {"latency_ms": {}}
    subject._phase = Subject.Phase.SAVE
    return subject

func _release(subject: Subject) -> void:
    _rows.append({"scenario": subject.scenario, "observations": subject.observations,
        "phase": Subject.Phase.keys()[subject._phase], "failure": subject.failure,
        "reads": subject._adapter.get("reads"), "saved_file_sha256": subject._row.get("saved_file_sha256")})
    subject._adapter.free()
    subject._adapter = null
    subject.free()

func _run() -> void:
    await get_tree().process_frame
    while EditorInterface.get_resource_filesystem().is_scanning():
        await get_tree().process_frame
    for scenario: String in ["sync_ok", "sync_error", "delayed_signal", "wrong_signal", "duplicate_signal", "phase_timeout"]:
        var subject: Subject = _subject(scenario)
        subject._save()
        var nested: Dictionary = subject.observations[0]
        _check(scenario + ":no_early_readback", nested.reads == 0 and not nested.save_recorded)
        if scenario in ["sync_ok", "sync_error", "delayed_signal", "duplicate_signal"]:
            _check(scenario + ":no_early_reload", nested.phase == "SAVE_WAIT")
        if scenario == "delayed_signal":
            subject._process(0.0)
            _check("delayed:waits_for_signal", subject._phase == Subject.Phase.SAVE_WAIT and subject._adapter.get("reads") == 0)
            subject._on_scene_saved(subject.SCENE)
        if subject._phase == Subject.Phase.SAVE_WAIT:
            subject._process(0.0)
        if scenario in ["sync_ok", "delayed_signal"]:
            _check(scenario + ":readback_after_return", subject._phase == Subject.Phase.RELOAD and subject._adapter.get("reads") == 1)
            _check(scenario + ":disk_hash", subject._row.get("saved_file_sha256") == FileAccess.get_sha256(subject.SCENE))
            # Reusing the subject exercises reset of the return latch each cycle.
            subject._row = {"latency_ms": {}}
            subject.scenario = "sync_ok"
            subject._phase = Subject.Phase.SAVE
            subject._save()
            _check(scenario + ":next_cycle_waits", subject.observations[1].phase == "SAVE_WAIT" and subject.observations[1].reads == 1)
            if subject._phase == Subject.Phase.SAVE_WAIT:
                subject._process(0.0)
            _check(scenario + ":next_cycle_completes", subject._phase == Subject.Phase.RELOAD and subject._adapter.get("reads") == 2)
        else:
            var expected: Dictionary = {"sync_error": "BENCHMARK_SAVE_CALL", "wrong_signal": "BENCHMARK_UNEXPECTED_SAVE",
                "duplicate_signal": "BENCHMARK_SAVE_READBACK", "phase_timeout": "BENCHMARK_PHASE_TIMEOUT"}
            _check(scenario + ":failure_preserved", subject._failed and subject._phase == Subject.Phase.FINISHED and subject.failure == expected[scenario])
            if scenario != "duplicate_signal":
                _check(scenario + ":failure_no_readback", subject._adapter.get("reads") == 0)
        _release(subject)
    var heartbeat: Subject = _subject("sync_ok")
    heartbeat._last_heartbeat_us = Time.get_ticks_usec() - 2500000
    heartbeat._save()
    _check("status_gap_not_hidden", heartbeat._max_status_gap_us >= 2500000)
    _release(heartbeat)
    var passed: bool = true
    for check: Dictionary in _checks:
        passed = passed and check.passed
    print("HH_SAVE_BOUNDARY " + JSON.stringify({"pid": OS.get_process_id(), "checks": _checks,
        "observations": _rows, "passed": passed, "authority": 0, "fault_injected": true,
        "real_save_exercised": false, "formal14_root_cause_proven": false}))
    while EditorInterface.get_resource_filesystem().is_scanning():
        await get_tree().process_frame
    get_tree().quit(0 if passed else 41)
