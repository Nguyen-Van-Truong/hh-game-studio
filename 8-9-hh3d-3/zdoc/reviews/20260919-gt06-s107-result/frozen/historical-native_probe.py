"""S103 diagnostic-only, exact-byte native save boundary overlay.

transform() never reads/writes files or launches an engine. Its only accepted
input is the frozen S102 benchmark plugin. The harness must hash and preserve
both input and transformed bytes, use a fresh diagnostic ID, and exclude the
entire run from acceptance. No benchmark heartbeat, gate, deadline, workload,
source declaration, or lifecycle decision is replaced.

At most 700 SAVE_ENTER and 700 SAVE_COMPLETE lines are emitted. ENTER is printed
before the call-entry clock is sampled, so an unmatched ENTER does not prove
the native call began. COMPLETE distinguishes call return, signal, save-frame
exit, and the first following _process entry/exit. Zero denotes an unobserved
boundary. The signal can occur before or after save_scene() returns.
"""
from __future__ import annotations

import hashlib


SOURCE_SHA256 = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
PROBE_VERSION = "s103-native-save-boundaries-v1"
MAX_SAVE_RECORDS = 700


class ProbeError(ValueError):
    """The diagnostic overlay cannot be applied to this exact source."""


_PROCESS = b"func _process(_delta: float) -> void:\n"
_DISPATCH = b"func _hh_s103_process_dispatch(_delta: float) -> void:\n"
_SAVE_CALL = b"    var result: Error = EditorInterface.save_scene()\n"
_SAVE_OBSERVED = b'''    _hh_s103_enter_save()
    if not _hh_s103_save.is_empty():
        _hh_s103_save.call_entry_us = Time.get_ticks_usec()
    var result: Error = EditorInterface.save_scene()
    var hh_s103_call_return_us: int = Time.get_ticks_usec()
    if not _hh_s103_save.is_empty():
        _hh_s103_save.call_return_us = hh_s103_call_return_us
        _hh_s103_save.save_result = int(result)
'''
_SIGNAL = b"    _save_signal_us = Time.get_ticks_usec()\n"
_SIGNAL_OBSERVED = _SIGNAL + b'''    if not _hh_s103_save.is_empty():
        _hh_s103_save.signal_us = _save_signal_us
        _hh_s103_save.signal_frame = Engine.get_process_frames()
'''

# Append-only declarations/functions. The original _process body is merely
# renamed, so every early return still unwinds into the observed wrapper.
_SUFFIX = r'''


# BEGIN HH_S103_DIAGNOSTIC_NATIVE_SAVE_BOUNDARIES_V1
# Diagnostic observations only. Original heartbeat stamps/gates remain above.
const HH_S103_SAVE_RECORD_CAP: int = 700
const HH_S103_PROBE_SOURCE_SHA256: String = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
var _hh_s103_save: Dictionary = {}
var _hh_s103_save_records: int = 0
var _hh_s103_process_entry_us: int = 0
var _hh_s103_process_entry_frame: int = 0


func _process(_delta: float) -> void:
    var entered: int = Time.get_ticks_usec()
    var entered_frame: int = Engine.get_process_frames()
    _hh_s103_process_entry_us = entered
    _hh_s103_process_entry_frame = entered_frame
    if not _hh_s103_save.is_empty() and int(_hh_s103_save.call_return_us) > 0 and int(_hh_s103_save.next_process_entry_us) == 0:
        _hh_s103_save.next_process_entry_us = entered
        _hh_s103_save.next_process_entry_frame = entered_frame
    _hh_s103_process_dispatch(_delta)
    var exited: int = Time.get_ticks_usec()
    if _hh_s103_save.is_empty():
        return
    var exited_frame: int = Engine.get_process_frames()
    if int(_hh_s103_save.process_entry_us) == entered:
        _hh_s103_save.save_process_exit_us = exited
        _hh_s103_save.save_process_exit_frame = exited_frame
    if int(_hh_s103_save.next_process_entry_us) == entered:
        _hh_s103_save.next_process_exit_us = exited
        _hh_s103_save.next_process_exit_frame = exited_frame
    var readback_end: int = 0
    if _timing.has("save"):
        readback_end = int(_timing.save.end_us)
    if readback_end > 0 or _failed:
        _hh_s103_save.event = "save_complete"
        _hh_s103_save.readback_end_us = readback_end
        _hh_s103_save.failed = _failed
        _hh_s103_save.observation_complete = (int(_hh_s103_save.call_entry_us) > 0
            and int(_hh_s103_save.call_return_us) > 0 and int(_hh_s103_save.signal_us) > 0
            and int(_hh_s103_save.save_process_exit_us) > 0
            and int(_hh_s103_save.next_process_entry_us) > 0
            and int(_hh_s103_save.next_process_exit_us) > 0 and readback_end > 0 and not _failed)
        print("HH_GT06_S103_SAVE_COMPLETE " + JSON.stringify(_hh_s103_save))
        _hh_s103_save = {}


func _hh_s103_enter_save() -> void:
    if _hh_s103_save_records >= HH_S103_SAVE_RECORD_CAP:
        return
    _hh_s103_save_records += 1
    var entry: Dictionary = {"schema_id": "hh-studio.s103-native-save", "schema_version": "1.0.0",
        "event": "save_enter", "formal_acceptance": false, "run_id": _input.get("run_id", "unbound"),
        "pid": OS.get_process_id(), "batch": _batch, "cycle": _cycle, "sequence": _hh_s103_save_records,
        "source_closure_sha256": _input.get("source_closure_sha256", ""),
        "profile_sha256": _input.get("profile_sha256", ""), "probe_source_sha256": HH_S103_PROBE_SOURCE_SHA256,
        "save_start_us": int(_timing.save.start_us), "process_entry_us": _hh_s103_process_entry_us,
        "process_entry_frame": _hh_s103_process_entry_frame, "entry_event_us": Time.get_ticks_usec()}
    _hh_s103_save = entry.duplicate()
    _hh_s103_save.merge({"call_entry_us": 0, "call_return_us": 0, "save_result": -1,
        "signal_us": 0, "signal_frame": 0, "save_process_exit_us": 0, "save_process_exit_frame": 0,
        "next_process_entry_us": 0, "next_process_entry_frame": 0,
        "next_process_exit_us": 0, "next_process_exit_frame": 0, "readback_end_us": 0,
        "failed": false, "observation_complete": false})
    print("HH_GT06_S103_SAVE_ENTER " + JSON.stringify(entry))
# END HH_S103_DIAGNOSTIC_NATIVE_SAVE_BOUNDARIES_V1
'''.encode("utf-8")


def transform(raw: bytes) -> bytes:
    """Return deterministic additive source bytes, or fail before any output."""
    if type(raw) is not bytes:
        raise ProbeError("S103_NATIVE_SOURCE_TYPE")
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ProbeError("S103_NATIVE_SOURCE_HASH")
    replacements = ((_PROCESS, _DISPATCH), (_SAVE_CALL, _SAVE_OBSERVED),
                    (_SIGNAL, _SIGNAL_OBSERVED))
    for old, new in replacements:
        if raw.count(old) != 1:
            raise ProbeError("S103_NATIVE_SOURCE_ANCHOR")
        raw = raw.replace(old, new, 1)
    return raw + _SUFFIX
