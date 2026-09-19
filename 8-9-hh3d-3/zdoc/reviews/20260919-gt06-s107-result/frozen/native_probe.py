"""Exact-base S107 preview-cost diagnostic overlay; no I/O or engine launch.

The returned source is for a disposable diagnostic project only. It executes
40 create/undo/save/reload cycles in ten ABBA groups. Original heartbeat,
phase/run deadlines, semantic checks and natural completion remain intact.
The altered workload is never a formal v2 benchmark or public-save evidence.
"""
from __future__ import annotations

import hashlib
import json

BASE_SOURCE_SHA256 = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
ROW_MARKER = "HH_GT06_S107_PREVIEW_COST "
COMPLETE_MARKER = "HH_GT06_S107_PREVIEW_COST_COMPLETE "
REPORT_FILE = "preview-cost.json"
CONTEXT_PATH = "res://benchmark/s107-context.json"
MAX_RECORDS = 40
RECIPE = {
    "schema_id": "hh-studio.s107-preview-cost-recipe", "schema_version": "1.0.0",
    "base_source_sha256": BASE_SOURCE_SHA256,
    "groups": 10, "group_order": "ABBA", "cycles": 40,
    "A": {"method": "save_scene", "with_preview": True, "return_kind": "Error"},
    "B": {"method": "save_scene_as", "with_preview": False, "return_kind": "void"},
    "mode": "diagnostic", "host_commands": 0, "pss_captures": 0,
    "outer_deadline_seconds": 180, "formal_acceptance": False,
    "eligible_for_dataset": False, "artificial_pressure": False,
    "scene_bytes": "first_observed_A_normalization_then_exact_saved_and_reloaded_bytes",
    "script_bytes": "exact_boot_source_hash_before_save_after_save_and_after_reload",
}
RECIPE_BYTES = (json.dumps(RECIPE, sort_keys=True, separators=(",", ":")) + "\n").encode()
RECIPE_SHA256 = hashlib.sha256(RECIPE_BYTES).hexdigest()


class ProbeError(ValueError):
    pass


def expected_arm(cycle: int) -> str:
    if type(cycle) is not int or not 0 <= cycle < MAX_RECORDS:
        raise ProbeError("S107_CYCLE_RANGE")
    return "ABBA"[cycle % 4]


_SAVE_OLD = b'''    var result: Error = EditorInterface.save_scene()
    if result != OK:
        _fail("BENCHMARK_SAVE_CALL")
'''
_SAVE_NEW = b'''    if not _s107_begin_save():
        return
    if _s107_current.arm == "A":
        _s107_current.call_entry_us = Time.get_ticks_usec()
        var result: Error = EditorInterface.save_scene()
        _s107_current.call_return_us = Time.get_ticks_usec()
        _s107_current.return_error = int(result)
        if result != OK:
            _fail("BENCHMARK_SAVE_CALL")
    else:
        _s107_current.call_entry_us = Time.get_ticks_usec()
        EditorInterface.save_scene_as(SCENE, false)
        _s107_current.call_return_us = Time.get_ticks_usec()
        # A void method has no fabricated Error/OK result.
        _s107_current.return_error = null
'''

_REPLACEMENTS = (
    (b'    "res://project.godot", INPUT, EVIDENCE_IGNORE]\n',
     b'    "res://project.godot", INPUT, EVIDENCE_IGNORE, "res://benchmark/s107-context.json"]\n'),
    (b'func _boot() -> void:\n', b'''func _boot() -> void:
    if _mode != "diagnostic":
        _fail("S107_DIAGNOSTIC_ONLY")
        return
'''),
    (b'''    if _mode == "diagnostic":
        _batch_limit = 1
        _cycle_limit = 1
''', b'''    if not _s107_bind_context():
        return
    if _mode == "diagnostic":
        _batch_limit = 1
        _cycle_limit = S107_RECORD_CAP
'''),
    (b'func _process(_delta: float) -> void:\n', b'func _s107_dispatch(_delta: float) -> void:\n'),
    (_SAVE_OLD, _SAVE_NEW),
    (b'    _save_signal_us = Time.get_ticks_usec()\n', b'''    _save_signal_us = Time.get_ticks_usec()
    if not _s107_current.is_empty():
        _s107_current.signal_us = _save_signal_us
        _s107_current.signal_frame = Engine.get_process_frames()
        _s107_current.signal_count_after = _save_signal_count
'''),
    (b'    _record_time("save", int(_timing.save.start_us), Time.get_ticks_usec())\n', b'''    _record_time("save", int(_timing.save.start_us), Time.get_ticks_usec())
    if _failed or not _s107_save_readback(digest):
        return
'''),
    (b'    _cycles.append(_row)\n', b'''    if not _s107_complete_cycle():
        return
    _cycles.append(_row)
'''),
    (b'    var report: Dictionary = {"schema_id": "hh-studio.native-cycle-benchmark",',
     b'''    if _s107_rows.size() != S107_RECORD_CAP or not _s107_current.is_empty():
        _fail("S107_RECORD_COUNT")
        return
    if not _s107_flush(true):
        _fail("S107_REPORT_WRITE")
        return
    var report: Dictionary = {"schema_id": "hh-studio.native-cycle-benchmark",'''),
    (b'''    _set_phase(Phase.FINISHED)
    print("HH_GT06_BENCHMARK_COMPLETE "''', b'''    _set_phase(Phase.FINISHED)
    _s107_emit_complete(str(written.sha256))
    print("HH_GT06_BENCHMARK_COMPLETE "'''),
    (b'''    _failed = true
    if _host_open_first_us''', b'''    _failed = true
    _s107_flush(false)
    if _host_open_first_us'''),
)

_SUFFIX_TEMPLATE = r'''


# BEGIN HH_S107_DIAGNOSTIC_PREVIEW_COST_V1
const S107_RECORD_CAP: int = 40
const S107_BASE_SOURCE_SHA256: String = "@@BASE@@"
const S107_RECIPE_SHA256: String = "@@RECIPE@@"
const S107_CONTEXT: String = "res://benchmark/s107-context.json"
var _s107_context: Dictionary = {}
var _s107_current: Dictionary = {}
var _s107_rows: Array[Dictionary] = []
var _s107_report_ref: Dictionary = {}
var _s107_rows_sha256: String = ""
var _s107_flushed: bool = false
var _s107_entry_us: int = 0
var _s107_entry_frame: int = 0
var _s107_saved_scene_sha256: String = ""


func _s107_bind_context() -> bool:
    var file: FileAccess = FileAccess.open(S107_CONTEXT, FileAccess.READ)
    if file == null:
        _fail("S107_CONTEXT_MISSING")
        return false
    var size: int = file.get_length()
    if size < 1 or size > 8192:
        file.close()
        _fail("S107_CONTEXT_SIZE")
        return false
    var parsed: Variant = JSON.parse_string(file.get_as_text())
    file.close()
    var fields: Array[String] = ["schema_id", "schema_version", "run_id", "base_source_closure_sha256",
        "profile_sha256", "recipe_sha256", "generated_overlay_sha256", "diagnostic_closure_sha256"]
    if not parsed is Dictionary or parsed.size() != fields.size() or not parsed.has_all(fields):
        _fail("S107_CONTEXT_FIELDS")
        return false
    if parsed.schema_id != "hh-studio.s107-preview-cost-context" or parsed.schema_version != "1.0.0":
        _fail("S107_CONTEXT_SCHEMA")
        return false
    if parsed.run_id != _input.run_id or parsed.base_source_closure_sha256 != _input.source_closure_sha256 or parsed.profile_sha256 != _input.profile_sha256:
        _fail("S107_CONTEXT_BINDING")
        return false
    if parsed.recipe_sha256 != S107_RECIPE_SHA256 or parsed.generated_overlay_sha256 != _source_hashes["res://addons/hh_benchmark/benchmark_native.gd"] or not _hex(parsed.diagnostic_closure_sha256):
        _fail("S107_CONTEXT_HASH")
        return false
    _s107_context = parsed
    return true


func _s107_binding() -> Dictionary:
    return {"run_id": _input.get("run_id", "unbound"), "pid": OS.get_process_id(),
        "source_closure_sha256": _input.get("source_closure_sha256", ""),
        "profile_sha256": _input.get("profile_sha256", ""), "base_source_sha256": S107_BASE_SOURCE_SHA256,
        "recipe_sha256": S107_RECIPE_SHA256,
        "generated_overlay_sha256": _s107_context.get("generated_overlay_sha256", ""),
        "diagnostic_closure_sha256": _s107_context.get("diagnostic_closure_sha256", ""),
        "context_sha256": _source_hashes.get(S107_CONTEXT, ""),
        "formal_acceptance": false, "eligible_for_dataset": false}


func _process(_delta: float) -> void:
    var entered: int = Time.get_ticks_usec()
    var frame: int = Engine.get_process_frames()
    _s107_entry_us = entered
    _s107_entry_frame = frame
    if not _s107_current.is_empty() and int(_s107_current.call_return_us) > 0 and int(_s107_current.next_process_entry_us) == 0:
        _s107_current.next_process_entry_us = entered
        _s107_current.next_process_entry_frame = frame
    _s107_dispatch(_delta)
    var exited: int = Time.get_ticks_usec()
    var exited_frame: int = Engine.get_process_frames()
    if _s107_current.is_empty():
        return
    if int(_s107_current.process_entry_us) == entered:
        _s107_current.save_process_exit_us = exited
        _s107_current.save_process_exit_frame = exited_frame
    if int(_s107_current.next_process_entry_us) == entered:
        _s107_current.next_process_exit_us = exited
        _s107_current.next_process_exit_frame = exited_frame


func _s107_begin_save() -> bool:
    if _mode != "diagnostic" or _batch != 0 or _cycle < 0 or _cycle >= S107_RECORD_CAP or _s107_rows.size() != _cycle or not _s107_current.is_empty() or _s107_flushed:
        _fail("S107_RECORD_ORDER")
        return false
    var arm: String = "ABBA".substr(_cycle % 4, 1)
    var scene_hash: String = FileAccess.get_sha256(SCENE)
    var script_hash: String = FileAccess.get_sha256("res://scripts/fixture_actor.gd")
    if not _hex(scene_hash) or script_hash != _source_hashes["res://scripts/fixture_actor.gd"]:
        _fail("S107_PRE_SAVE_BYTES")
        return false
    if _cycle > 0 and scene_hash != _s107_saved_scene_sha256:
        _fail("S107_PRE_SAVE_SCENE_DRIFT")
        return false
    _s107_current = _s107_binding()
    _s107_current.merge({"schema_id": "hh-studio.s107-preview-cost-cycle", "schema_version": "1.0.0",
        "cycle": _cycle, "group": floori(float(_cycle) / 4.0), "position": _cycle % 4,
        "arm": arm, "method": "save_scene" if arm == "A" else "save_scene_as", "with_preview": arm == "A",
        "return_error": null, "completed": false,
        "save_start_us": int(_timing.save.start_us), "process_entry_us": _s107_entry_us,
        "process_entry_frame": _s107_entry_frame, "call_entry_us": 0, "call_return_us": 0,
        "signal_us": 0, "signal_frame": 0, "save_process_exit_us": 0, "save_process_exit_frame": 0,
        "next_process_entry_us": 0, "next_process_entry_frame": 0,
        "next_process_exit_us": 0, "next_process_exit_frame": 0, "readback_end_us": 0,
        "signal_count_before": _save_signal_before, "signal_count_after": _save_signal_count,
        "scene_before_sha256": scene_hash, "script_before_sha256": script_hash,
        "scene_sha256": "", "script_sha256": "", "scene_reloaded_sha256": "", "script_reloaded_sha256": "",
        "baseline_sha256": _bare(_baseline_revision), "before_sha256": "", "created_sha256": "",
        "undone_sha256": "", "reloaded_sha256": "", "root_before": 0, "root_after": 0,
        "generation_before": 0, "generation_after": 0, "effects": {}})
    return true


func _s107_save_readback(scene_hash: String) -> bool:
    if _s107_current.is_empty():
        _fail("S107_SAVE_RECORD_MISSING")
        return false
    var script_hash: String = FileAccess.get_sha256("res://scripts/fixture_actor.gd")
    if script_hash != _source_hashes["res://scripts/fixture_actor.gd"]:
        _fail("S107_SCRIPT_CHANGED")
        return false
    # The first A keeps its observed initial serialization normalization.
    # No uncounted warmup save is inserted and no first row is discarded.
    if _s107_saved_scene_sha256.is_empty():
        _s107_saved_scene_sha256 = scene_hash
    if scene_hash != _s107_saved_scene_sha256:
        _fail("S107_SAVED_SCENE_DRIFT")
        return false
    _s107_current.scene_sha256 = scene_hash
    _s107_current.script_sha256 = script_hash
    _s107_current.readback_end_us = int(_timing.save.end_us)
    return true


func _s107_complete_cycle() -> bool:
    if _s107_current.is_empty() or _s107_rows.size() != _cycle or _s107_rows.size() >= S107_RECORD_CAP or int(_s107_current.cycle) != _cycle:
        _fail("S107_CYCLE_RECORD_ORDER")
        return false
    for field: String in ["process_entry_us", "call_entry_us", "call_return_us", "signal_us", "save_process_exit_us", "next_process_entry_us", "next_process_exit_us", "readback_end_us"]:
        if int(_s107_current[field]) <= 0:
            _fail("S107_BOUNDARY_MISSING")
            return false
    if int(_s107_current.signal_count_after) != int(_s107_current.signal_count_before) + 1:
        _fail("S107_SIGNAL_COUNT")
        return false
    var scene_hash: String = FileAccess.get_sha256(SCENE)
    var script_hash: String = FileAccess.get_sha256("res://scripts/fixture_actor.gd")
    if scene_hash != _s107_saved_scene_sha256 or scene_hash != str(_row.saved_file_sha256) or script_hash != _source_hashes["res://scripts/fixture_actor.gd"]:
        _fail("S107_RELOAD_BYTES")
        return false
    _s107_current.scene_reloaded_sha256 = scene_hash
    _s107_current.script_reloaded_sha256 = script_hash
    for field: String in ["before_sha256", "created_sha256", "undone_sha256", "reloaded_sha256", "root_before", "root_after", "effects"]:
        _s107_current[field] = _row[field]
    _s107_current.generation_before = int(_timing.generation_before)
    _s107_current.generation_after = int(_timing.generation_after)
    _s107_current.completed = true
    _s107_rows.append(_s107_current.duplicate(true))
    _s107_current = {}
    return true


func _s107_flush(completed: bool) -> bool:
    if _s107_flushed:
        return not _s107_report_ref.is_empty()
    _s107_flushed = true
    var rows: Array[Dictionary] = _s107_rows.duplicate(true)
    if not completed and not _s107_current.is_empty() and rows.size() < S107_RECORD_CAP:
        rows.append(_s107_current.duplicate(true))
    if rows.size() > S107_RECORD_CAP:
        return false
    var arms: Dictionary = {"A": 0, "B": 0}
    for row: Dictionary in rows:
        arms[str(row.arm)] = int(arms[str(row.arm)]) + 1
    _s107_rows_sha256 = _bytes_sha256(JSON.stringify(rows, "", true, true).to_utf8_buffer())
    var report: Dictionary = _s107_binding()
    report.merge({"schema_id": "hh-studio.s107-preview-cost", "schema_version": "1.0.0",
        "completed": completed, "rows": rows, "row_count": rows.size(), "arms": arms,
        "rows_sha256": _s107_rows_sha256})
    _s107_report_ref = _write_new("preview-cost.json", report)
    for row: Dictionary in rows:
        print("HH_GT06_S107_PREVIEW_COST " + JSON.stringify(row, "", true, true))
    return not _s107_report_ref.is_empty()


func _s107_emit_complete(index_sha256: String) -> void:
    var result: Dictionary = _s107_binding()
    result.merge({"schema_id": "hh-studio.s107-preview-cost-complete", "schema_version": "1.0.0",
        "completed": true, "cycles": S107_RECORD_CAP, "row_count": _s107_rows.size(),
        "arms": {"A": 20, "B": 20}, "rows_sha256": _s107_rows_sha256,
        "report_file": "preview-cost.json", "report_sha256": _s107_report_ref.sha256,
        "report_size_bytes": _s107_report_ref.size_bytes, "index_sha256": index_sha256})
    print("HH_GT06_S107_PREVIEW_COST_COMPLETE " + JSON.stringify(result, "", true, true))
# END HH_S107_DIAGNOSTIC_PREVIEW_COST_V1
'''


def build_overlay(base: bytes) -> bytes:
    """Return generated diagnostic bytes, fail closed before any mutation."""
    if type(base) is not bytes:
        raise ProbeError("S107_NATIVE_SOURCE_TYPE")
    if hashlib.sha256(base).hexdigest() != BASE_SOURCE_SHA256:
        raise ProbeError("S107_NATIVE_SOURCE_HASH")
    result = base
    for old, new in _REPLACEMENTS:
        if result.count(old) != 1:
            raise ProbeError("S107_NATIVE_SOURCE_ANCHOR")
        result = result.replace(old, new, 1)
    suffix = _SUFFIX_TEMPLATE.replace("@@BASE@@", BASE_SOURCE_SHA256).replace("@@RECIPE@@", RECIPE_SHA256)
    return result + suffix.encode()
