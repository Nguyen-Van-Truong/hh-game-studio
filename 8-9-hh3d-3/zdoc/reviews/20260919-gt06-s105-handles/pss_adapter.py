"""Supplemental, owned-process-only Windows x64 PSS handle observations.

Adapted from the S76 pss_handles.py layout, with the S103 attribution contract.
Public API: capture_owned(existing_process_probe) -> JSON-compatible dict.
The caller serializes this with its immutable sample/gate/run/source bindings.
Call only AFTER the original counter/gate and outside its measured interval.

ProcessProbe retains PID/start/handle, but not executable. Read the executable
from that retained handle, then re-open ONLY that PID with the S76 access mask
and check PID/start/executable again. The caller retains the original handle;
this module owns only its extra process handle, local snapshot and walk marker.
No enumeration, privileges, target handle closes, contexts, VA clone or writes.

The 15-second budget is cooperative: checked around each native call and walk
iteration. A blocked PSS call cannot be interrupted here; the existing owner
must retain its external process deadline. Capture may perturb/quiesce a target.
UNKNOWN is required on any incomplete capture or unverified cleanup. A failed
cleanup retains in-memory ownership and prevents another capture; it never
re-closes a potentially reused numeric handle. No leak/root-cause/identity claim.

Native contract references (Microsoft):
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_handle_flags
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot
"""
from __future__ import annotations

from collections import Counter
import ctypes as C
from datetime import datetime, timezone
import hashlib
import ntpath
import os
import re
import threading
import time


DWORD = C.c_uint32
HANDLE = C.c_void_p
CAPTURE_FLAGS = 0x04 | 0x08 | 0x10 | 0x20
# S76 empirically used mask; not a documented universal PSS minimum guarantee.
PROCESS_ACCESS = 0x0400 | 0x0010 | 0x0040 | 0x100000
MAX_ENTRIES = 65_536
MAX_TOTAL_NS = 15_000_000_000
MAX_NAME_BYTES = 65_534
ERROR_NO_MORE_ITEMS = 259
WAIT_TIMEOUT = 258
_CAPTURE_LOCK = threading.Lock()
_HELD_RESOURCES: list[dict] = []


class FileTime(C.Structure):
    _fields_ = [('low', DWORD), ('high', DWORD)]


class ProcessInfo(C.Structure):
    _fields_ = [('exit_status', DWORD), ('peb', HANDLE),
                ('affinity', C.c_size_t), ('base_priority', C.c_int32),
                ('pid', DWORD), ('parent_pid', DWORD), ('flags', DWORD)]


class ThreadInfo(C.Structure):
    _fields_ = [('exit_status', DWORD), ('teb', HANDLE), ('pid', DWORD),
                ('tid', DWORD), ('affinity', C.c_size_t), ('priority', C.c_int32),
                ('base_priority', C.c_int32), ('start', HANDLE)]


class TypeSpecific(C.Union):
    _fields_ = [('process', ProcessInfo), ('thread', ThreadInfo),
                ('padding', C.c_byte * 48)]


class HandleEntry(C.Structure):
    _fields_ = [('handle', HANDLE), ('flags', DWORD), ('object_type', DWORD),
                ('capture_time', FileTime), ('attributes', DWORD),
                ('access', DWORD), ('handle_count', DWORD), ('pointer_count', DWORD),
                ('paged', DWORD), ('nonpaged', DWORD), ('created', FileTime),
                ('type_length', C.c_uint16), ('type_name', HANDLE),
                ('name_length', C.c_uint16), ('name', HANDLE),
                ('specific', TypeSpecific)]


class PssError(RuntimeError):
    """Only explicit safe codes reach receipts; exception text is never emitted."""
    def __init__(self, code: str, *, api: str | None = None,
                 native_code: int | None = None):
        super().__init__(code)
        self.code, self.api, self.native_code = code, api, native_code


def _error(exc: Exception) -> dict:
    if isinstance(exc, PssError):
        return {'code': exc.code, 'api': exc.api, 'native_code': exc.native_code}
    return {'code': 'PSS_UNEXPECTED_EXCEPTION', 'api': None, 'native_code': None}


def _check_layout() -> None:
    # Fixed Windows x64 ABI; DWORD/LONG are explicit 32-bit even on POSIX tests.
    expected = {'handle': 0, 'flags': 8, 'object_type': 12, 'capture_time': 16,
                'type_length': 56, 'type_name': 64, 'name_length': 72,
                'name': 80, 'specific': 88}
    if (C.sizeof(HANDLE) != 8 or C.sizeof(HandleEntry) != 136
            or C.sizeof(ThreadInfo) != 48 or C.sizeof(ProcessInfo) != 40
            or any(getattr(HandleEntry, name).offset != offset
                   for name, offset in expected.items())):
        raise PssError('PSS_X64_LAYOUT')


def _name_bytes(pointer: int | None, length: int) -> bytes:
    if length < 0 or length > MAX_NAME_BYTES or length % 2 or (length and not pointer):
        raise PssError('PSS_NAME_LENGTH')
    return C.string_at(pointer, length) if length else b''


def _redact_entry(entry: HandleEntry) -> dict:
    """Copy/hash native buffers before marker free; emit no pointers/object names."""
    flags = int(entry.flags)
    type_name = None
    if flags & 1:
        if entry.type_length > 256:
            raise PssError('PSS_TYPE_NAME_LENGTH')
        raw_type = _name_bytes(entry.type_name, int(entry.type_length))
        try:
            type_name = raw_type.decode('utf-16-le').removesuffix('\0') or None
        except UnicodeError:
            raise PssError('PSS_TYPE_NAME_ENCODING') from None
        if type_name is not None and not re.fullmatch(r'[A-Za-z0-9_ .-]{1,128}', type_name):
            raise PssError('PSS_TYPE_NAME_FORMAT')
    raw_name = _name_bytes(entry.name, int(entry.name_length)) if flags & 2 else None
    row = {
        'handle': int(entry.handle or 0), 'flags': flags, 'type': type_name,
        'object_type': int(entry.object_type) if flags & 1 else None,
        'name_state': ('UNAVAILABLE' if raw_name is None else
                       'EMPTY' if not any(raw_name) else 'REDACTED'),
        'name_length_bytes': len(raw_name) if raw_name is not None else None,
        'name_sha256': hashlib.sha256(raw_name).hexdigest() if raw_name else None,
        'name_hash_encoding': 'exact-utf16le-bytes-including-any-terminator',
        # Even an identical attribute tuple does not prove the same kernel object.
        'object_identity': 'UNKNOWN',
    }
    if flags & 1 and flags & 8:
        if entry.object_type == 2:
            value = entry.specific.thread
            row['thread'] = {'pid': int(value.pid), 'tid': int(value.tid),
                             'exit_status': int(value.exit_status),
                             'priority': int(value.priority),
                             'base_priority': int(value.base_priority)}
        elif entry.object_type == 1:
            value = entry.specific.process
            row['process'] = {'pid': int(value.pid), 'parent_pid': int(value.parent_pid),
                              'exit_status': int(value.exit_status)}
    return row


class _Native:
    def __init__(self) -> None:
        if os.name != 'nt':
            raise PssError('PSS_WINDOWS_ONLY')
        _check_layout()
        self.k = C.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'OpenProcess': ([DWORD, C.c_int32, DWORD], HANDLE),
            'CloseHandle': ([HANDLE], C.c_int32),
            'GetCurrentProcess': ([], HANDLE),
            'GetProcessId': ([HANDLE], DWORD),
            'GetProcessHandleCount': ([HANDLE, C.POINTER(DWORD)], C.c_int32),
            'GetProcessTimes': ([HANDLE] + [C.POINTER(FileTime)] * 4, C.c_int32),
            'QueryFullProcessImageNameW': ([HANDLE, DWORD, C.c_wchar_p, C.POINTER(DWORD)], C.c_int32),
            'WaitForSingleObject': ([HANDLE, DWORD], DWORD),
            'PssCaptureSnapshot': ([HANDLE, DWORD, DWORD, C.POINTER(HANDLE)], DWORD),
            'PssQuerySnapshot': ([HANDLE, DWORD, HANDLE, DWORD], DWORD),
            'PssWalkMarkerCreate': ([HANDLE, C.POINTER(HANDLE)], DWORD),
            'PssWalkSnapshot': ([HANDLE, DWORD, HANDLE, HANDLE, DWORD], DWORD),
            'PssWalkMarkerFree': ([HANDLE], DWORD),
            'PssFreeSnapshot': ([HANDLE, HANDLE], DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.k, name)
            function.argtypes, function.restype = arguments, result
        self.current = self.k.GetCurrentProcess()

    @staticmethod
    def _bool(value, api: str):
        if not value:
            raise PssError('PSS_NATIVE_ERROR', api=api, native_code=C.get_last_error())
        return value

    @staticmethod
    def _code(value: int, api: str) -> None:
        if value:
            raise PssError('PSS_NATIVE_ERROR', api=api, native_code=int(value))

    def identity(self, handle: int) -> dict:
        pid = self._bool(self.k.GetProcessId(handle), 'GetProcessId')
        times = [FileTime() for _ in range(4)]
        self._bool(self.k.GetProcessTimes(handle, *(C.byref(v) for v in times)), 'GetProcessTimes')
        size, name = DWORD(32768), C.create_unicode_buffer(32768)
        self._bool(self.k.QueryFullProcessImageNameW(handle, 0, name, C.byref(size)),
                   'QueryFullProcessImageNameW')
        if not 0 < size.value < 32768 or not ntpath.isabs(name.value):
            raise PssError('PSS_EXECUTABLE_BINDING')
        return {'pid': int(pid),
                'process_start': 'windows:' + str((times[0].high << 32) | times[0].low),
                'executable': ntpath.normcase(ntpath.normpath(name.value))}

    def require_live(self, handle: int) -> None:
        code = int(self.k.WaitForSingleObject(handle, 0))
        if code != WAIT_TIMEOUT:
            raise PssError('PSS_TARGET_NOT_LIVE', api='WaitForSingleObject', native_code=code)

    def count(self, handle: int) -> int:
        value = DWORD()
        self._bool(self.k.GetProcessHandleCount(handle, C.byref(value)), 'GetProcessHandleCount')
        return int(value.value)

    def open_owned(self, pid: int) -> int:
        return self._bool(self.k.OpenProcess(PROCESS_ACCESS, False, pid), 'OpenProcess')

    def capture(self, handle: int) -> int:
        snapshot = HANDLE()
        self._code(self.k.PssCaptureSnapshot(handle, CAPTURE_FLAGS, 0, C.byref(snapshot)),
                   'PssCaptureSnapshot')
        if not snapshot.value:
            raise PssError('PSS_NULL_SNAPSHOT')
        return snapshot.value

    def captured_count(self, snapshot: int) -> int:
        value = DWORD()
        self._code(self.k.PssQuerySnapshot(snapshot, 4, C.byref(value), C.sizeof(value)),
                   'PssQuerySnapshot')
        return int(value.value)

    def marker(self) -> int:
        marker = HANDLE()
        self._code(self.k.PssWalkMarkerCreate(None, C.byref(marker)), 'PssWalkMarkerCreate')
        if not marker.value:
            raise PssError('PSS_NULL_MARKER')
        return marker.value

    def walk(self, snapshot: int, marker: int) -> HandleEntry | None:
        entry = HandleEntry()
        code = self.k.PssWalkSnapshot(snapshot, 2, marker, C.byref(entry), C.sizeof(entry))
        if code == ERROR_NO_MORE_ITEMS:
            return None
        self._code(code, 'PssWalkSnapshot')
        return entry

    def free_marker(self, marker: int) -> int:
        return int(self.k.PssWalkMarkerFree(marker))

    def free_snapshot(self, snapshot: int) -> int:
        # The descriptor is allocated in this observer, not in the target.
        return int(self.k.PssFreeSnapshot(self.current, snapshot))

    def close_process(self, handle: int) -> int:
        return 0 if self.k.CloseHandle(handle) else int(C.get_last_error() or 1)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _cleanup(api, owned: dict) -> dict:
    receipts = {}
    for resource, method in [('marker', 'free_marker'), ('snapshot', 'free_snapshot'),
                             ('process_handle', 'close_process')]:
        value = owned.get(resource)
        receipt = {'attempted': value is not None, 'native_code': None,
                   'success': None, 'outcome': 'NOT_ACQUIRED'}
        if value is not None:
            try:
                code = getattr(api, method)(value)
                receipt.update(native_code=code, success=code == 0,
                               outcome='RELEASED' if code == 0 else 'NATIVE_FAILURE')
                if code == 0:
                    owned[resource] = None
            except Exception:
                receipt.update(success=False, outcome='UNKNOWN_EXCEPTION')
        receipts[resource] = receipt
    held = [name for name, value in owned.items() if value is not None]
    if held:
        # Never emit these numeric descriptors or blindly retry after uncertainty.
        _HELD_RESOURCES.append({'api': api, 'owned': owned.copy()})
    receipts.update(all_released=not held, held_resources=held)
    return receipts


def capture_owned(probe, *, _api=None, _clock=None) -> dict:
    """Observe exactly the supplied retained ProcessProbe, never a bare PID.

    _api/_clock are fake-only seams for static tests. Production callers use
    capture_owned(probe). The caller must not close/mutate probe concurrently.
    Failed snapshots remain supplemental UNKNOWN; original gates stay intact.
    """
    clock = _clock or time.perf_counter_ns
    started = clock()
    result = {
        'schema': 'gt06-s105-owned-pss-v1', 'status': 'UNKNOWN',
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'identity': None, 'binding_verified': False,
        'capture_flags': CAPTURE_FLAGS, 'process_access_mask': PROCESS_ACCESS,
        'handles_captured': None, 'entries': [], 'type_counts': {}, 'errors': [],
        'observer_handle_count_before': None, 'observer_handle_count_after': None,
        'target_handle_count_before': None, 'target_handle_count_after': None,
        'timing': {'started_utc': _utc(), 'started_perf_ns': started,
                   'capture_ms': None, 'walk_ms': None},
        'budget': {'max_entries': MAX_ENTRIES, 'max_total_ms': MAX_TOTAL_NS / 1e6,
                   'native_calls_interruptible': False, 'external_deadline_required': True},
        'limitations': ['SUPPLEMENTAL_OBSERVER_EFFECT_UNKNOWN',
                        'NUMERIC_HANDLES_AND_ATTRIBUTE_MATCHES_ARE_NOT_OBJECT_IDENTITY',
                        'NO_LEAK_OR_ROOT_CAUSE_CLAIM'],
    }
    owned = {'process_handle': None, 'snapshot': None, 'marker': None}
    api = None
    locked = _CAPTURE_LOCK.acquire(blocking=False)

    def budget() -> None:
        if clock() - started > MAX_TOTAL_NS:
            raise PssError('PSS_TIME_BUDGET')

    def check_identity(actual: dict, expected: dict) -> None:
        if actual != expected:
            raise PssError('PSS_PROCESS_IDENTITY')

    try:
        if not locked:
            raise PssError('PSS_CAPTURE_BUSY')
        if _HELD_RESOURCES:
            raise PssError('PSS_PRIOR_CLEANUP_HELD')
        handle, pid = getattr(probe, 'handle', None), getattr(probe, 'pid', None)
        process_start = getattr(probe, 'process_start', None)
        if (not handle or type(pid) is not int or not 0 < pid < 0xffffffff
                or not isinstance(process_start, str)
                or not re.fullmatch(r'windows:[1-9][0-9]{0,19}', process_start)
                or int(process_start.split(':')[1]) > 0xffffffffffffffff
                or getattr(probe, 'close_uncertain', False)):
            raise PssError('PSS_OWNED_PROBE_REQUIRED')
        api = _api if _api is not None else _Native()
        result['observer_handle_count_before'] = api.count(api.current)
        api.require_live(handle)
        identity = api.identity(handle)
        if identity['pid'] != pid or identity['process_start'] != process_start:
            raise PssError('PSS_RETAINED_HANDLE_IDENTITY')
        expected_executable = getattr(probe, 'executable', None)
        if expected_executable is not None:
            expected_executable = ntpath.normcase(ntpath.normpath(str(expected_executable)))
            if identity['executable'] != expected_executable:
                raise PssError('PSS_EXPECTED_EXECUTABLE_IDENTITY')
        result['identity'] = identity
        result['executable_binding_source'] = 'RETAINED_HANDLE_QUERY'
        budget()
        owned['process_handle'] = api.open_owned(pid)
        check_identity(api.identity(owned['process_handle']), identity)
        api.require_live(handle)
        api.require_live(owned['process_handle'])
        result['binding_verified'] = True
        result['target_handle_count_before'] = api.count(owned['process_handle'])
        budget()
        capture_start = clock()
        try:
            owned['snapshot'] = api.capture(owned['process_handle'])
        finally:
            result['timing']['capture_ms'] = (clock() - capture_start) / 1e6
        budget()
        result['handles_captured'] = api.captured_count(owned['snapshot'])
        if result['handles_captured'] > MAX_ENTRIES:
            raise PssError('PSS_ENTRY_BUDGET')
        budget()
        owned['marker'] = api.marker()
        walk_start = clock()
        try:
            while True:
                budget()
                entry = api.walk(owned['snapshot'], owned['marker'])
                budget()
                if entry is None:
                    break
                if len(result['entries']) >= MAX_ENTRIES:
                    raise PssError('PSS_ENTRY_BUDGET')
                result['entries'].append(_redact_entry(entry))
            if len(result['entries']) != result['handles_captured']:
                raise PssError('PSS_CAPTURED_COUNT_MISMATCH')
        finally:
            result['timing']['walk_ms'] = (clock() - walk_start) / 1e6
        check_identity(api.identity(owned['process_handle']), identity)
        check_identity(api.identity(handle), identity)
        api.require_live(handle)
        api.require_live(owned['process_handle'])
        result['target_handle_count_after'] = api.count(owned['process_handle'])
        budget()
        result['status'] = 'OBSERVED'
    except Exception as exc:
        result['errors'].append(_error(exc))
    finally:
        try:
            result['cleanup'] = _cleanup(api, owned)
            if _HELD_RESOURCES:
                result['cleanup']['all_released'] = False
                result['cleanup']['prior_or_current_cleanup_held'] = True
            if not result['cleanup']['all_released']:
                result['errors'].append({'code': 'PSS_CLEANUP_UNVERIFIED',
                                         'api': None, 'native_code': None})
            if api is not None:
                try:
                    result['observer_handle_count_after'] = api.count(api.current)
                except Exception as exc:
                    result['errors'].append(_error(exc))
            result['type_counts'] = dict(sorted(Counter(
                row['type'] or '<unavailable>' for row in result['entries']).items()))
            ended = clock()
            result['timing'].update(ended_utc=_utc(), ended_perf_ns=ended,
                                    total_ms=(ended - started) / 1e6)
            if ended - started > MAX_TOTAL_NS and not any(
                    error['code'] == 'PSS_TIME_BUDGET' for error in result['errors']):
                result['errors'].append({'code': 'PSS_TIME_BUDGET', 'api': None,
                                         'native_code': None})
            if result['errors']:
                result['status'] = 'UNKNOWN'
        finally:
            if locked:
                _CAPTURE_LOCK.release()
    return result
