"""Owned Windows overlapped pipe I/O; internal transport building block.

The trusted launcher supplies an exclusively owned, non-inheritable, byte-mode
FILE_FLAG_OVERLAPPED pipe. This module does not authenticate the peer, create
an endpoint, dispatch commands or acknowledge application effects. Never take
handles or I/O settings from a request. A successful write only delivers bytes.

Cancellation is a request, not completion. A process-wide bounded registry
retains each owner, pipe, OVERLAPPED, event and buffer until native completion
and checked close. A stalled driver closes admission, not Python ownership.
The supervisor may retry close on the retained owner or terminate its own
broker process; it must not free pending buffers or blindly resend a command.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import math
import os
import struct
import threading
import time

from .limits import SafetyViolation

MAX_FRAME_BYTES = 256 * 1024
MAX_OWNED_PIPES = 32
_PENDING, _INCOMPLETE = 997, 996
_POLL_MS = 20
# Errors that describe a completed operation, not a bad query handle/argument.
_TERMINAL_ERRORS = {0, 109, 232, 233, 234, 995}
_OWNERS: set[OwnedPipe] = set()
_OWNERS_LOCK = threading.Lock()


class PipeIOError(SafetyViolation):
    def __init__(self, code: str, *, delivery_unknown: bool = False,
                 cleanup_owner: OwnedPipe | None = None) -> None:
        super().__init__(code)
        # Local provenance, never serialized as an application receipt.
        self.delivery_unknown = delivery_unknown
        self.cleanup_owner = cleanup_owner


class _Overlapped(C.Structure):
    _fields_ = [("internal", C.c_size_t), ("internal_high", C.c_size_t),
                ("offset", W.DWORD), ("offset_high", W.DWORD), ("event", W.HANDLE)]


@dataclass(eq=False, repr=False)
class _Operation:
    kind: str
    size: int
    buffer: object
    overlapped: _Overlapped
    count: W.DWORD
    complete: bool = False
    error: int = 0


class _PipeApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise PipeIOError("UNSUPPORTED_PIPE_PLATFORM")
        self.dll = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateEventW": ([C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "ConnectNamedPipe": ([W.HANDLE, C.POINTER(_Overlapped)], W.BOOL),
            "ReadFile": ([W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(_Overlapped)], W.BOOL),
            "WriteFile": ([W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(_Overlapped)], W.BOOL),
            "GetOverlappedResult": ([W.HANDLE, C.POINTER(_Overlapped), C.POINTER(W.DWORD), W.BOOL], W.BOOL),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "CancelIoEx": ([W.HANDLE, C.POINTER(_Overlapped)], W.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = arguments, result

    def event(self) -> int:
        handle = self.dll.CreateEventW(None, True, False, None)
        if not handle:
            raise PipeIOError("PIPE_EVENT_CREATE_FAILED")
        return handle

    def start(self, pipe: int, op: _Operation) -> int:
        if op.kind == "connect":
            ok = self.dll.ConnectNamedPipe(pipe, C.byref(op.overlapped))
        else:
            function = self.dll.ReadFile if op.kind == "read" else self.dll.WriteFile
            ok = function(pipe, op.buffer, op.size, C.byref(op.count), C.byref(op.overlapped))
        return 0 if ok else C.get_last_error()

    def result(self, pipe: int, op: _Operation) -> int:
        ok = self.dll.GetOverlappedResult(pipe, C.byref(op.overlapped), C.byref(op.count), False)
        return 0 if ok else C.get_last_error()

    def wait(self, op: _Operation, milliseconds: int) -> int:
        return int(self.dll.WaitForSingleObject(op.overlapped.event, milliseconds))

    def cancel(self, pipe: int, op: _Operation) -> int:
        ok = self.dll.CancelIoEx(pipe, C.byref(op.overlapped))
        return 0 if ok else C.get_last_error()

    def close(self, handle: int) -> None:
        if not self.dll.CloseHandle(handle):
            raise PipeIOError("PIPE_CLOSE_FAILED")


class OwnedPipe:
    """One serial I/O owner, one frame deadline, independently callable Stop.

    _adopt is a trusted local ownership transfer: the caller must not close or
    use the pipe again after it succeeds. On refusal, ownership stays with the
    caller. No finalizer guesses that pending native memory can be released.
    """

    @classmethod
    def _adopt(cls, handle: int, *, cancel_grace_ms: int = 250,
               _api: _PipeApi | None = None) -> OwnedPipe:
        if type(handle) is not int or not 0 < handle < C.c_void_p(-1).value:
            raise PipeIOError("INVALID_PIPE_HANDLE")
        if type(cancel_grace_ms) is not int or not 1 <= cancel_grace_ms <= 1000:
            raise PipeIOError("INVALID_PIPE_LIMIT")
        api = _api if _api is not None else _PipeApi()
        owner = cls()
        owner._api, owner._handle = api, handle
        owner._grace_ms = cancel_grace_ms
        owner._operation: _Operation | None = None
        owner._mutex = threading.Lock()
        owner._stop = threading.Event()
        owner._poisoned = False
        owner._write_started = False
        with _OWNERS_LOCK:
            if len(_OWNERS) >= MAX_OWNED_PIPES:
                raise PipeIOError("PIPE_OWNER_LIMIT")
            if any(item._handle == handle for item in _OWNERS):
                raise PipeIOError("PIPE_ALREADY_OWNED")
            _OWNERS.add(owner)
        return owner

    @property
    def closed(self) -> bool:
        return self._handle is None

    def request_stop(self) -> None:
        # No handle access on the caller's thread and no waiting for I/O locks.
        self._stop.set()

    def _error(self, code: str) -> PipeIOError:
        return PipeIOError(code, delivery_unknown=self._write_started, cleanup_owner=self)

    @staticmethod
    def _deadline(timeout_ms: int) -> float:
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 30_000:
            raise PipeIOError("INVALID_PIPE_LIMIT")
        return time.monotonic() + timeout_ms / 1000

    def _check(self, deadline: float) -> None:
        if self.closed or self._poisoned:
            raise self._error("PIPE_CLOSED_OR_POISONED")
        if self._stop.is_set():
            raise self._error("PIPE_STOPPED")
        if time.monotonic() >= deadline:
            raise self._error("PIPE_TIMEOUT")

    def _observe(self, op: _Operation) -> bool:
        if op.complete:
            return True
        error = self._api.result(self._handle, op)
        if error in _TERMINAL_ERRORS:
            op.complete, op.error = True, error
        elif error not in (_INCOMPLETE, _PENDING):
            raise self._error("PIPE_COMPLETION_UNVERIFIED")
        return op.complete

    def _wait(self, op: _Operation, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        result = self._api.wait(op, min(_POLL_MS, max(1, math.ceil(remaining * 1000))))
        if result not in (0, 258):
            raise self._error("PIPE_WAIT_FAILED")

    def _cancel_and_drain(self, op: _Operation) -> bool:
        if op.complete:
            return True
        # Even ERROR_NOT_FOUND (completion race) is NOT a completion witness.
        # A cancel error must not prevent a subsequent successful observation.
        try:
            self._api.cancel(self._handle, op)
        except Exception:
            pass
        deadline = time.monotonic() + self._grace_ms / 1000
        while True:
            try:
                if self._observe(op):
                    return True
                if time.monotonic() >= deadline:
                    return False
                self._wait(op, deadline)
            except Exception:
                return False

    def _release_operation(self, op: _Operation) -> None:
        if not op.complete:
            raise self._error("PIPE_DRAIN_PENDING")
        # Do not lose event ownership on a failed native close.
        self._api.close(op.overlapped.event)
        self._operation = None

    def _io(self, kind: str, size: int, deadline: float, payload: bytes = b"") -> bytes:
        self._check(deadline)
        buffer = C.create_string_buffer(payload, size) if kind == "write" else C.create_string_buffer(max(size, 1))
        # Allocate Python storage before the native event; register the event
        # in the retained owner before any I/O can reference that storage.
        op = _Operation(kind, size, buffer, _Overlapped(), W.DWORD())
        op.overlapped.event = self._api.event()
        self._operation = op
        if kind == "write":
            self._write_started = True
        try:
            error = self._api.start(self._handle, op)
            if kind == "connect" and error == 535:  # Client connected first.
                error = 0
            if error != _PENDING:
                op.complete, op.error = True, error
            while not op.complete:
                self._check(deadline)
                if self._observe(op):
                    break
                self._wait(op, deadline)
            if op.error:
                raise self._error("PIPE_IO_FAILED")
            if not 0 <= op.count.value <= size or (kind == "write" and op.count.value != size):
                raise self._error("PIPE_SHORT_OR_INVALID_TRANSFER")
            result = buffer.raw[:op.count.value] if kind == "read" else b""
            self._release_operation(op)
            return result
        except BaseException as exc:
            self._poisoned = True
            if self._operation is not None:
                if not self._cancel_and_drain(op):
                    raise self._error("PIPE_DRAIN_PENDING") from None
                try:
                    self._release_operation(op)
                except Exception:
                    raise self._error("PIPE_CLEANUP_PENDING") from None
            if isinstance(exc, PipeIOError):
                raise self._error(exc.code) from None
            raise self._error("PIPE_IO_UNCERTAIN") from None

    def _read_exact(self, size: int, deadline: float) -> bytes:
        result = bytearray()
        while len(result) < size:
            chunk = self._io("read", size - len(result), deadline)
            if not chunk:
                raise self._error("PIPE_EOF")
            result.extend(chunk)
        return bytes(result)

    def _run(self, operation, timeout_ms: int):
        deadline = self._deadline(timeout_ms)
        if not self._mutex.acquire(blocking=False):
            raise self._error("PIPE_BUSY")
        try:
            self._check(deadline)
            return operation(deadline)
        except BaseException:
            self._poisoned = True
            raise
        finally:
            self._mutex.release()

    def connect(self, *, timeout_ms: int = 1000) -> None:
        self._run(lambda deadline: self._io("connect", 0, deadline), timeout_ms)

    def read_frame(self, *, timeout_ms: int = 1000) -> bytes:
        def read(deadline):
            size = struct.unpack("<I", self._read_exact(4, deadline))[0]
            if not 0 < size <= MAX_FRAME_BYTES:
                raise self._error("PIPE_FRAME_LIMIT")
            return self._read_exact(size, deadline)
        return self._run(read, timeout_ms)

    def write_frame(self, data: bytes, *, timeout_ms: int = 1000) -> None:
        if type(data) is not bytes or not 0 < len(data) <= MAX_FRAME_BYTES:
            raise PipeIOError("PIPE_FRAME_LIMIT")
        frame = struct.pack("<I", len(data)) + data
        self._run(lambda deadline: self._io("write", len(frame), deadline, frame), timeout_ms)

    def close(self) -> None:
        self.request_stop()
        if not self._mutex.acquire(blocking=False):
            raise self._error("PIPE_BUSY")
        try:
            if self.closed:
                return
            op = self._operation
            if op is not None:
                if not self._cancel_and_drain(op):
                    raise self._error("PIPE_DRAIN_PENDING")
                try:
                    self._release_operation(op)
                except Exception:
                    raise self._error("PIPE_CLEANUP_PENDING") from None
            try:
                self._api.close(self._handle)
            except Exception:
                raise self._error("PIPE_CLEANUP_PENDING") from None
            with _OWNERS_LOCK:
                self._handle = None
                _OWNERS.remove(self)
        finally:
            self._mutex.release()


def pending_cleanup() -> tuple[OwnedPipe, ...]:
    """Local supervisor recovery, not wire discovery or automatic resubmission."""
    with _OWNERS_LOCK:
        return tuple(owner for owner in _OWNERS if owner._stop.is_set() or owner._poisoned)
