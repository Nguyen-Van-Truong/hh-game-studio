"""Internal local pipe bound to one trusted launcher's AppContainer process.

No launch, capability issuance or command dispatch lives here. Configuration
and the retained process handle come from the broker, never request fields.
The peer's primary token is queried through the retained process object; the
broker thread never impersonates client data. Arbitrary same-account peers
are outside the private-broker trust boundary and are not accepted as workers.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import re
import threading
import uuid

from .limits import SafetyViolation
from .pipe_io import OwnedPipe, PipeIOError, pending_cleanup
from .private_store import _StoreApi, _SecurityAttributes

_PACKAGE = re.compile(r"S-1-15-2(?:-[0-9]{1,10}){7}\Z")
_ENDPOINTS: set[AppContainerEndpoint] = set()
_ENDPOINTS_LOCK = threading.Lock()
MAX_ENDPOINTS = 16


class EndpointError(SafetyViolation):
    def __init__(self, code: str, owner: AppContainerEndpoint | None = None) -> None:
        super().__init__(code)
        self.cleanup_owner = owner  # Local only, never a response field.


class _EndpointApi(_StoreApi):
    def __init__(self):
        super().__init__()
        signatures = {
            "CreateNamedPipeW": ([W.LPCWSTR, W.DWORD, W.DWORD, W.DWORD, W.DWORD,
                                  W.DWORD, W.DWORD, C.POINTER(_SecurityAttributes)], W.HANDLE),
            "DuplicateHandle": ([W.HANDLE, W.HANDLE, W.HANDLE, C.POINTER(W.HANDLE),
                                  W.DWORD, W.BOOL, W.DWORD], W.BOOL),
            "GetProcessId": ([W.HANDLE], W.DWORD),
            "GetCurrentProcessId": ([], W.DWORD),
            "ProcessIdToSessionId": ([W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
            "GetProcessTimes": ([W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
                                  C.POINTER(W.FILETIME), C.POINTER(W.FILETIME)], W.BOOL),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "GetNamedPipeClientProcessId": ([W.HANDLE, C.POINTER(W.ULONG)], W.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = arguments, result
        session = W.DWORD()
        self._checked(self.dll.ProcessIdToSessionId(self.dll.GetCurrentProcessId(), C.byref(session)),
                      "BROKER_SESSION_UNVERIFIED")
        self.session = session.value

    def _render_security(self, descriptor):
        rendered = W.LPWSTR()
        self._checked(self.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 0x15, C.byref(rendered), None), "PIPE_ACL_UNVERIFIED")
        try:
            return rendered.value
        finally:
            self.dll.LocalFree(rendered)

    def create_pipe(self, address: str, package: str) -> int:
        # Windows reports SE_SACL_AUTO_INHERITED for the created pipe label.
        # Author that control bit explicitly; compare the entire resulting SD.
        self.sddl = f"O:{self.owner}D:P(A;;RC;;;OW)(A;;FA;;;{self.owner})(A;;0x12019b;;;{package})S:AI(ML;;NW;;;LW)"
        with self.descriptor() as descriptor:
            self.expected_security = self._render_security(descriptor)
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.dll.CreateNamedPipeW(address, 3 | 0x40000000 | 0x80000,
                                               8, 1, 4096, 4096, 1000, C.byref(attributes))
        if handle == C.c_void_p(-1).value:
            raise EndpointError("PIPE_CREATE_FAILED")
        self._owned_handles.add(handle)
        return handle

    def check_security(self, handle):
        descriptor = C.c_void_p()
        if self.adv.GetSecurityInfo(handle, 1, 0x15, None, None, None, None, C.byref(descriptor)):
            raise EndpointError("PIPE_ACL_UNVERIFIED")
        try:
            if self._render_security(descriptor) != self.expected_security:
                raise EndpointError("PIPE_ACL_CHANGED")
        finally:
            if descriptor.value:
                self.dll.LocalFree(descriptor)

    def duplicate_process(self, process: int) -> int:
        owned = W.HANDLE()
        current = self.dll.GetCurrentProcess()
        self._checked(self.dll.DuplicateHandle(current, process, current, C.byref(owned),
                                              0x101000, False, 0), "PEER_PROCESS_UNVERIFIED")
        self._owned_handles.add(owned.value)
        return owned.value

    def _token_info(self, token, kind):
        size = W.DWORD()
        self.adv.GetTokenInformation(token, kind, None, 0, C.byref(size))
        if C.get_last_error() != 122 or not 4 <= size.value <= 65536:
            raise EndpointError("PEER_TOKEN_UNVERIFIED")
        buffer = C.create_string_buffer(size.value)
        self._checked(self.adv.GetTokenInformation(token, kind, buffer, len(buffer), C.byref(size)),
                      "PEER_TOKEN_UNVERIFIED")
        if not 4 <= size.value <= len(buffer):
            raise EndpointError("PEER_TOKEN_UNVERIFIED")
        return buffer

    @staticmethod
    def _number(buffer):
        return int.from_bytes(buffer.raw[:4], "little")

    @staticmethod
    def _sid(buffer):
        # TOKEN_USER/APPCONTAINER_SID/MANDATORY_LABEL start with a SID pointer.
        # Never dereference an unchecked pointer outside the bounded result.
        if len(buffer) < C.sizeof(C.c_void_p):
            raise EndpointError("PEER_TOKEN_UNVERIFIED")
        pointer = C.cast(buffer, C.POINTER(C.c_void_p)).contents.value
        start = (pointer or 0) - C.addressof(buffer)
        if start < C.sizeof(C.c_void_p) or start + 8 > len(buffer):
            raise EndpointError("PEER_TOKEN_UNVERIFIED")
        raw = buffer.raw[start:]
        revision, count = raw[0], raw[1]
        if revision != 1 or count > 15 or len(raw) < 8 + 4 * count:
            raise EndpointError("PEER_TOKEN_UNVERIFIED")
        authority = int.from_bytes(raw[2:8], "big")
        sub = [int.from_bytes(raw[8 + 4 * i:12 + 4 * i], "little") for i in range(count)]
        return "S-1-" + str(authority) + "".join("-" + str(value) for value in sub)

    def inspect_worker(self, process: int, package: str) -> tuple[int, int]:
        self.check_no_impersonation()
        if self.dll.WaitForSingleObject(process, 0) != 258:
            raise EndpointError("PEER_PROCESS_NOT_LIVE")
        pid = int(self.dll.GetProcessId(process))
        created, exited, kernel, user = W.FILETIME(), W.FILETIME(), W.FILETIME(), W.FILETIME()
        if not pid or not self.dll.GetProcessTimes(process, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)):
            raise EndpointError("PEER_PROCESS_UNVERIFIED")
        token = W.HANDLE()
        self._checked(self.adv.OpenProcessToken(process, 8, C.byref(token)), "PEER_TOKEN_UNVERIFIED")
        self._owned_handles.add(token.value)
        try:
            if (self._number(self._token_info(token, 8)) != 1
                    or self._number(self._token_info(token, 29)) != 1):
                raise EndpointError("PEER_NOT_APPCONTAINER")
            if (self._sid(self._token_info(token, 31)) != package
                    or self._sid(self._token_info(token, 1)) != self.owner
                    or self._sid(self._token_info(token, 25)) != "S-1-16-4096"
                    or self._number(self._token_info(token, 30)) != 0
                    or self._number(self._token_info(token, 12)) != self.session):
                raise EndpointError("PEER_TOKEN_MISMATCH")
        finally:
            self.close(token.value)
        if self.dll.WaitForSingleObject(process, 0) != 258:
            raise EndpointError("PEER_PROCESS_NOT_LIVE")
        return pid, created.dwLowDateTime | (created.dwHighDateTime << 32)


class AppContainerEndpoint:
    """One pre-created endpoint role, one immutable launch-time process binding.

    Create both work and control endpoints before launching a worker. Neither
    role, package SID, process handle nor address is accepted from frame data.
    This validates primary process identity; the RPC layer additionally binds
    and rechecks its locally issued session credential on every request.
    """

    @classmethod
    def create(cls, package_sid: str, *, role: str) -> AppContainerEndpoint:
        if type(package_sid) is not str or not _PACKAGE.fullmatch(package_sid):
            raise EndpointError("INVALID_PACKAGE_SID")
        if role not in ("work", "control"):
            raise EndpointError("INVALID_ENDPOINT_ROLE")
        owner = cls()
        owner._api = None
        owner._pipe = None
        owner._process = None
        owner._identity = None
        owner._poisoned = owner._closed = False
        owner._mutex = threading.Lock()
        owner._role, owner._package = role, package_sid
        owner._address = "\\\\.\\pipe\\" + package_sid + "\\hh-studio-" + uuid.uuid4().hex
        with _ENDPOINTS_LOCK:
            if len(_ENDPOINTS) >= MAX_ENDPOINTS:
                raise EndpointError("ENDPOINT_LIMIT")
            _ENDPOINTS.add(owner)
        try:
            owner._api = _EndpointApi()
            handle = owner._api.create_pipe(owner._address, package_sid)
            owner._api.check_security(handle)
            owner._pipe = OwnedPipe._adopt(handle)
            owner._api._owned_handles.remove(handle)  # Transfer, not two owners.
            return owner
        except Exception as exc:
            owner._poisoned = True
            try:
                owner.close()
            except Exception:
                raise EndpointError("ENDPOINT_CLEANUP_PENDING", owner) from None
            raise EndpointError(exc.code if isinstance(exc, SafetyViolation) else "ENDPOINT_CREATE_FAILED") from None

    @property
    def address(self) -> str:
        return self._address  # Protected local launch metadata; never discovery/log data.

    @property
    def role(self) -> str:
        return self._role

    @contextmanager
    def _guard(self):
        if not self._mutex.acquire(blocking=False):
            raise EndpointError("ENDPOINT_BUSY", self)
        try:
            if self._closed or self._poisoned:
                raise EndpointError("ENDPOINT_CLOSED_OR_POISONED", self)
            self._api.check_no_impersonation()
            self._api.check_security(self._pipe._handle)
            yield
        except Exception as exc:
            self._poisoned = True
            self.request_stop()
            if isinstance(exc, (EndpointError, PipeIOError)):
                raise
            raise EndpointError(exc.code if isinstance(exc, SafetyViolation) else "ENDPOINT_UNVERIFIED", self) from None
        finally:
            self._mutex.release()

    def bind_worker(self, retained_process: int) -> None:
        with self._guard():
            if self._process is not None:
                raise EndpointError("PEER_ALREADY_BOUND", self)
            self._process = self._api.duplicate_process(retained_process)
            self._identity = self._api.inspect_worker(self._process, self._package)

    def _check_peer(self) -> None:
        if self._process is None or self._identity is None:
            raise EndpointError("PEER_NOT_BOUND", self)
        if self._api.inspect_worker(self._process, self._package) != self._identity:
            raise EndpointError("PEER_IDENTITY_CHANGED", self)
        pid = W.ULONG()
        if (not self._api.dll.GetNamedPipeClientProcessId(self._pipe._handle, C.byref(pid))
                or pid.value != self._identity[0]):
            raise EndpointError("PIPE_CLIENT_MISMATCH", self)

    def connect(self, *, timeout_ms: int = 1000) -> None:
        with self._guard():
            if self._identity is None:
                raise EndpointError("PEER_NOT_BOUND", self)
            self._pipe.connect(timeout_ms=timeout_ms)
            self._check_peer()

    def read_frame(self, *, timeout_ms: int = 1000) -> bytes:
        with self._guard():
            self._check_peer()
            data = self._pipe.read_frame(timeout_ms=timeout_ms)
            self._check_peer()
            return data

    def write_frame(self, data: bytes, *, timeout_ms: int = 1000) -> None:
        with self._guard():
            self._check_peer()
            self._pipe.write_frame(data, timeout_ms=timeout_ms)

    def request_stop(self) -> None:
        if self._pipe is not None:
            self._pipe.request_stop()

    def close(self) -> None:
        self.request_stop()
        if not self._mutex.acquire(blocking=False):
            raise EndpointError("ENDPOINT_BUSY", self)
        try:
            if self._closed:
                return
            try:
                if self._pipe is not None:
                    self._pipe.close()
                if self._api is not None:
                    self._api.close_owned()
            except Exception:
                raise EndpointError("ENDPOINT_CLEANUP_PENDING", self) from None
            with _ENDPOINTS_LOCK:
                self._closed = True
                _ENDPOINTS.remove(self)
        finally:
            self._mutex.release()


def pending_endpoint_cleanup() -> tuple[AppContainerEndpoint, ...]:
    pipes = set(pending_cleanup())
    with _ENDPOINTS_LOCK:
        return tuple(owner for owner in _ENDPOINTS if owner._poisoned or owner._pipe is not None
                     and owner._pipe in pipes)
