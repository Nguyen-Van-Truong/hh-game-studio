"""S108 exact-base startup window announcement over the frozen S103 overlay.

Pure byte transformation: callers supply both the fixed S102 base and the
exact S103 save-boundary overlay. No files, imports of runtime code, threads,
engine launches, save changes, clock changes, or acceptance claims are made.
The runner must retain both inputs, this helper, generated output, and the
frozen context sidecar. Full-mode 100-cycle batches and original gates remain.

One MAIN_WINDOW record is emitted after settled startup and before READY 0.
Its checked Godot main-thread label is not a Windows thread ID. The host must
independently bind HWND to the owning PID/Windows thread using retained handles.
Pinned APIs: Godot ed1daf0bf001b61586d9930840f2f1394092c079 doc/classes/
DisplayServer.xml (WINDOW_HANDLE, window_get_native_handle, get_window_list)
and Thread.xml (is_main_thread). A headless/missing window fails before READY.
"""
from __future__ import annotations

import hashlib

BASE_SOURCE_SHA256 = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
SOURCE_SHA256 = BASE_SOURCE_SHA256
BASE_SOURCE_CLOSURE_SHA256 = "7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467"
PROFILE_SHA256 = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
S103_HELPER_SHA256 = "47dd4957deb2f1dc7995b0a30aecf424ef7ebe6c55d239f437fa9865d9583855"
S103_OVERLAY_SHA256 = "bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46"
WINDOW_MARKER = "HH_GT06_S108_MAIN_WINDOW "
CONTEXT_PATH = "res://benchmark/s108-context.json"
CONTEXT_SCHEMA = "hh-studio.s108-save-attribution-context"
CONTEXT_FIELDS = ("schema_id", "schema_version", "run_id", "base_source_closure_sha256",
                  "profile_sha256", "generated_overlay_sha256", "diagnostic_closure_sha256")
PROBE_VERSION = "s108-main-window-over-s103-v1"


class ProbeError(ValueError):
    """An input is outside the frozen diagnostic contract."""


_REPLACEMENTS = (
    (b'    "res://project.godot", INPUT, EVIDENCE_IGNORE]\n',
     b'    "res://project.godot", INPUT, EVIDENCE_IGNORE, "res://benchmark/s108-context.json"]\n'),
    (b'    _last_root_id = root.get_instance_id()\n    _begin_batch()\n',
     b'''    _last_root_id = root.get_instance_id()
    if not _s108_announce_main_window():
        return
    _begin_batch()
'''),
)

_SUFFIX = r'''


# BEGIN HH_S108_DIAGNOSTIC_MAIN_WINDOW_V1
const S108_CONTEXT: String = "res://benchmark/s108-context.json"
const S108_BASE_SOURCE_SHA256: String = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
const S108_BASE_CLOSURE_SHA256: String = "7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467"
const S108_PROFILE_SHA256: String = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
var _s108_window_announced: bool = false


func _s108_announce_main_window() -> bool:
    if _s108_window_announced:
        _fail("S108_MAIN_WINDOW_DUPLICATE")
        return false
    if _mode != "full" or not str(_input.run_id).begins_with("gt06-s108-"):
        _fail("S108_DIAGNOSTIC_FULL_PREFIX_ONLY")
        return false
    if not Thread.is_main_thread() or DisplayServer.get_name() != "Windows":
        _fail("S108_MAIN_WINDOW_PLATFORM_THREAD")
        return false
    if not DisplayServer.get_window_list().has(DisplayServer.MAIN_WINDOW_ID):
        _fail("S108_MAIN_WINDOW_MISSING")
        return false
    var hwnd: int = DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE, DisplayServer.MAIN_WINDOW_ID)
    if hwnd <= 0:
        _fail("S108_MAIN_WINDOW_HANDLE")
        return false
    var file: FileAccess = FileAccess.open(S108_CONTEXT, FileAccess.READ)
    if file == null:
        _fail("S108_CONTEXT_MISSING")
        return false
    var size: int = file.get_length()
    if size < 1 or size > 8192:
        file.close()
        _fail("S108_CONTEXT_SIZE")
        return false
    var parsed: Variant = JSON.parse_string(file.get_as_text())
    file.close()
    var fields: Array[String] = ["schema_id", "schema_version", "run_id", "base_source_closure_sha256",
        "profile_sha256", "generated_overlay_sha256", "diagnostic_closure_sha256"]
    if not parsed is Dictionary or parsed.size() != fields.size() or not parsed.has_all(fields):
        _fail("S108_CONTEXT_FIELDS")
        return false
    if parsed.schema_id != "hh-studio.s108-save-attribution-context" or parsed.schema_version != "1.0.0":
        _fail("S108_CONTEXT_SCHEMA")
        return false
    if parsed.run_id != _input.run_id or parsed.base_source_closure_sha256 != _input.source_closure_sha256 or parsed.profile_sha256 != _input.profile_sha256:
        _fail("S108_CONTEXT_BINDING")
        return false
    if parsed.base_source_closure_sha256 != S108_BASE_CLOSURE_SHA256 or parsed.profile_sha256 != S108_PROFILE_SHA256:
        _fail("S108_BASE_PROFILE_PIN")
        return false
    if parsed.generated_overlay_sha256 != _source_hashes["res://addons/hh_benchmark/benchmark_native.gd"] or not _hex(parsed.diagnostic_closure_sha256):
        _fail("S108_CONTEXT_HASH")
        return false
    if FileAccess.get_sha256(S108_CONTEXT) != _source_hashes[S108_CONTEXT]:
        _fail("S108_CONTEXT_DRIFT")
        return false
    var announcement: Dictionary = {"schema_id": "hh-studio.s108-main-window", "schema_version": "1.0.0",
        "run_id": _input.run_id, "pid": OS.get_process_id(), "hwnd": hwnd,
        "window_id": DisplayServer.MAIN_WINDOW_ID, "display_server": DisplayServer.get_name(),
        "main_thread": true, "logical_thread": "godot_editor_main", "windows_thread_id": null,
        "mono_us": Time.get_ticks_usec(), "process_frame": Engine.get_process_frames(),
        "base_source_sha256": S108_BASE_SOURCE_SHA256,
        "source_closure_sha256": _input.source_closure_sha256, "profile_sha256": _input.profile_sha256,
        "generated_overlay_sha256": parsed.generated_overlay_sha256,
        "diagnostic_closure_sha256": parsed.diagnostic_closure_sha256,
        "context_sha256": _source_hashes[S108_CONTEXT], "formal_acceptance": false, "eligible_for_dataset": false}
    _s108_window_announced = true
    print("HH_GT06_S108_MAIN_WINDOW " + JSON.stringify(announcement))
    return true
# END HH_S108_DIAGNOSTIC_MAIN_WINDOW_V1
'''.encode("utf-8")


def build_overlay(base: bytes, save_overlay: bytes) -> bytes:
    """Add the bounded announcement only to the exact frozen S103 overlay."""
    if type(base) is not bytes or type(save_overlay) is not bytes:
        raise ProbeError("S108_NATIVE_SOURCE_TYPE")
    if hashlib.sha256(base).hexdigest() != BASE_SOURCE_SHA256:
        raise ProbeError("S108_NATIVE_SOURCE_HASH")
    if hashlib.sha256(save_overlay).hexdigest() != S103_OVERLAY_SHA256:
        raise ProbeError("S108_S103_OVERLAY_HASH")
    result = save_overlay
    for old, new in _REPLACEMENTS:
        if result.count(old) != 1:
            raise ProbeError("S108_NATIVE_SOURCE_ANCHOR")
        result = result.replace(old, new, 1)
    return result + _SUFFIX


transform = build_overlay
