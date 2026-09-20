"""Checked ownership of one Windows CLI Job; no Docker/container authority."""
from __future__ import annotations

import ctypes
import os
import threading
import time

MAX_OWNERS = 16
SETTLE_SECONDS = 1.0
HOLDS: list[Owner] = []
_LIVE: set[Owner] = set()
_REGISTRY_LOCK = threading.RLock()


class JobError(RuntimeError):
    def __init__(self, code: str, *, cleanup_owner=None, native_error: int | None = None):
        super().__init__(code)
        self.code = code
        self.cleanup_owner = cleanup_owner
        self.native_error = native_error


class _Native:
    def __init__(self):
        if os.name != 'nt':
            raise JobError('CLI_JOB_WINDOWS_REQUIRED')
        from ctypes import wintypes as w
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        class BasicLimit(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                        ('active_limit', w.DWORD), ('affinity', ctypes.c_size_t),
                        ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class ExtendedLimit(ctypes.Structure):
            _fields_ = [('basic', BasicLimit), ('io', ctypes.c_ulonglong * 6),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]
        class Accounting(ctypes.Structure):
            _fields_ = [('user_time', ctypes.c_longlong), ('kernel_time', ctypes.c_longlong),
                        ('period_user', ctypes.c_longlong), ('period_kernel', ctypes.c_longlong),
                        ('page_faults', w.DWORD), ('total_processes', w.DWORD),
                        ('active_processes', w.DWORD), ('terminated_processes', w.DWORD)]
        self.ExtendedLimit, self.Accounting = ExtendedLimit, Accounting
        k = self.kernel
        k.CreateJobObjectW.argtypes, k.CreateJobObjectW.restype = [w.LPVOID, w.LPCWSTR], w.HANDLE
        k.SetInformationJobObject.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(ExtendedLimit), w.DWORD]
        k.SetInformationJobObject.restype = w.BOOL
        k.AssignProcessToJobObject.argtypes, k.AssignProcessToJobObject.restype = [w.HANDLE, w.HANDLE], w.BOOL
        k.QueryInformationJobObject.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(Accounting), w.DWORD, ctypes.POINTER(w.DWORD)]
        k.QueryInformationJobObject.restype = w.BOOL
        k.TerminateJobObject.argtypes, k.TerminateJobObject.restype = [w.HANDLE, w.UINT], w.BOOL
        k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL

    @staticmethod
    def _checked(value, operation):
        if not value:
            raise OSError(ctypes.get_last_error(), operation)
        return value

    def create(self):
        return self._checked(self.kernel.CreateJobObjectW(None, None), 'CreateJobObjectW')

    def configure(self, handle):
        limits = self.ExtendedLimit()
        limits.basic.flags = 0x2000  # KILL_ON_JOB_CLOSE; no breakaway flags.
        self._checked(self.kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)),
                      'SetInformationJobObject')

    def assign(self, handle, process):
        self._checked(self.kernel.AssignProcessToJobObject(handle, int(process._handle)), 'AssignProcessToJobObject')

    def active_count(self, handle):
        from ctypes import wintypes as w
        value, returned = self.Accounting(), w.DWORD()
        self._checked(self.kernel.QueryInformationJobObject(handle, 1, ctypes.byref(value), ctypes.sizeof(value),
                                                           ctypes.byref(returned)), 'QueryInformationJobObject')
        if returned.value != ctypes.sizeof(value):
            raise OSError('QueryInformationJobObject size mismatch')
        return int(value.active_processes)

    def terminate(self, handle):
        self._checked(self.kernel.TerminateJobObject(handle, 2), 'TerminateJobObject')

    def close(self, handle):
        self._checked(self.kernel.CloseHandle(handle), 'CloseHandle')


def _native():
    return _Native()


def _hold(owner):
    with _REGISTRY_LOCK:
        if owner not in HOLDS:
            HOLDS.append(owner)  # Always a member of the bounded _LIVE registry.


def require_no_holds() -> None:
    with _REGISTRY_LOCK:
        if HOLDS:
            raise JobError('CLI_JOB_CLEANUP_HELD', cleanup_owner=HOLDS[0])


def owner_for_process(process):
    """Recover a constructor return interrupted before the caller stored it."""
    with _REGISTRY_LOCK:
        return next((owner for owner in _LIVE if owner._process is process), None)


class Owner:
    def __init__(self, native):
        self._native = native
        self._handle = None
        self._process = None
        self._lock = threading.RLock()
        self.configured = False
        self.assigned = False
        self.closed = False
        self.tainted = False
        self.zero_observed = False
        self.last_active_count = None
        self.last_native_error = None
        self.failed_operations: set[str] = set()
        self.create_uncertain = False
        self.close_uncertain = False

    def _failure(self, operation, error):
        self.tainted = True
        self.failed_operations.add(operation)
        self.last_native_error = getattr(error, 'winerror', None) or getattr(error, 'errno', None)
        if self._handle is not None or self.create_uncertain or self.close_uncertain:
            _hold(self)
        return JobError('CLI_JOB_' + operation + '_UNCERTAIN', cleanup_owner=self if self in HOLDS else None,
                        native_error=self.last_native_error)

    def _cancel(self, operation, error):
        self._failure(operation, error)
        error.cleanup_owner = self if not self.closed else None

    def active_count(self) -> int | None:
        with self._lock:
            if self.closed:
                return 0 if self.zero_observed else None
            if self.create_uncertain or self.close_uncertain:
                return None  # Never query a possibly closed/reused numeric handle.
            if self._handle is None:
                return None
            try:
                count = self._native.active_count(self._handle)
                if type(count) is not int or count < 0:
                    raise ValueError('invalid native active count')
                self.last_active_count = count
                self.zero_observed = count == 0
                return count
            except BaseException as error:
                self.last_active_count = None
                self.zero_observed = False
                self._failure('QUERY', error)
                if not isinstance(error, Exception):
                    self._cancel('QUERY', error)
                    raise
                return None

    def terminate(self) -> None:
        with self._lock:
            if self.closed:
                return
            if self.create_uncertain or self.close_uncertain:
                raise JobError('CLI_JOB_NATIVE_RESULT_UNCERTAIN', cleanup_owner=self)
            if self._handle is None:
                raise JobError('CLI_JOB_HANDLE_MISSING', cleanup_owner=self)
            try:
                self._native.terminate(self._handle)
            except BaseException as error:
                failure = self._failure('TERMINATE', error)
                if not isinstance(error, Exception):
                    self._cancel('TERMINATE', error)
                    raise
                raise failure from error

    def close(self) -> None:
        """Return only after actual zero-active query and checked handle close."""
        with self._lock:
            if self.closed:
                return  # Successful handle close is never repeated.
            try:
                if self.create_uncertain or self.close_uncertain:
                    raise JobError('CLI_JOB_NATIVE_RESULT_UNCERTAIN', cleanup_owner=self)
                count = self.active_count()
                if count is None:
                    raise JobError('CLI_JOB_QUERY_UNCERTAIN', cleanup_owner=self)
                if count:
                    self.terminate()
                    deadline = time.monotonic() + SETTLE_SECONDS
                    while count and time.monotonic() < deadline:
                        time.sleep(.01)
                        count = self.active_count()
                        if count is None:
                            raise JobError('CLI_JOB_QUERY_UNCERTAIN', cleanup_owner=self)
                    if count:
                        raise self._failure('ACTIVE', TimeoutError('owned Job did not drain'))
                # A cancellation can hide whether CloseHandle completed. Do
                # not query/retry that number after an unobserved result.
                self.close_uncertain = True
                try:
                    self._native.close(self._handle)
                except Exception as error:
                    self.close_uncertain = False  # Checked native failure: handle remains owned.
                    raise self._failure('CLOSE', error) from error
                self._handle = None
                self.closed = True
                self.close_uncertain = False
                with _REGISTRY_LOCK:
                    if self in HOLDS:
                        HOLDS.remove(self)
                    _LIVE.discard(self)
            except BaseException as error:
                if not isinstance(error, Exception):
                    self._cancel('CLOSE', error)
                raise

    def snapshot(self) -> dict:
        with self._lock:
            return {'configured': self.configured, 'assigned': self.assigned, 'closed': self.closed,
                    'handle_retained': self._handle is not None, 'tainted': self.tainted,
                    'zero_observed': self.zero_observed, 'active_count': self.last_active_count,
                    'create_uncertain': self.create_uncertain, 'close_uncertain': self.close_uncertain,
                    'failed_operations': sorted(self.failed_operations), 'native_error': self.last_native_error}


def create(process, *, before_assign=None) -> Owner:
    """Own the Job, optionally configure it empty, then assign the gated helper.

    The caller must keep its helper behind GO until this returns. The optional
    trusted callback uses the same constructor cleanup and cancellation path;
    existing callers keep the default KILL_ON_CLOSE configuration.
    """
    with _REGISTRY_LOCK:
        require_no_holds()
        if len(_LIVE) >= MAX_OWNERS:
            raise JobError('CLI_JOB_OWNER_CAPACITY')
        owner = Owner(_native())
        owner._process = process
        _LIVE.add(owner)
        _hold(owner)  # Constructor ownership exists before the first native allocation.
    operation = 'CREATE'
    try:
        owner._handle = owner._native.create()
        if not owner._handle:
            raise OSError('native create returned no handle')
        operation = 'CONFIGURE'
        owner._native.configure(owner._handle)
        if before_assign is not None:
            before_assign(owner)
        owner.configured = True
        operation = 'ASSIGN'
        owner._native.assign(owner._handle, process)
        owner.assigned = True
        with _REGISTRY_LOCK:
            HOLDS.remove(owner)
        return owner
    except BaseException as error:
        cancellation = error if not isinstance(error, Exception) else None
        if cancellation and owner._handle is None:
            owner.create_uncertain = True  # Allocation result was never received.
        failure = owner._failure(operation, error)
        if owner._handle is None and not owner.create_uncertain:
            with _REGISTRY_LOCK:
                _LIVE.discard(owner)
                if owner in HOLDS:
                    HOLDS.remove(owner)
            failure.cleanup_owner = None
        else:
            try:
                owner.close()
            except BaseException as cleanup_error:
                if not isinstance(cleanup_error, Exception) and cancellation is None:
                    cancellation = cleanup_error
                # The registry retains every unresolved native owner.
            if owner.closed:
                failure.cleanup_owner = None
        if cancellation is not None:
            cancellation.cleanup_owner = owner if not owner.closed else None
            raise cancellation
        raise failure from error


def retry_cleanup() -> list[dict]:
    """One bounded cleanup attempt per retained owner; never drop failed owners."""
    with _REGISTRY_LOCK:
        pending = list(HOLDS)
    rows = []
    for owner in pending:
        try:
            owner.close()
        except JobError:
            pass
        rows.append(owner.snapshot())
    return rows
