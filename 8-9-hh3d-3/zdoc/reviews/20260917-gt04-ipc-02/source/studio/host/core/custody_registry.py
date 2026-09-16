"""Bounded Windows custody anchor; trusted local broker code only.

Registry compare/read/write is NOT interprocess CAS. The supervisor must own
its unique file writer guard before updates; this module prevents duplicate
local owners only. It does not validate supervisor record schemas/checksums.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
import os
import re
import threading

from .limits import SafetyViolation


MAX_STATE_BYTES = 16 * 1024
BASE_PARTS = ("HHStudio", "ManagedFixture", "v1")
BASE_PATH = "Software\\" + "\\".join(BASE_PARTS)
_HKCU = C.c_void_p(0xFFFFFFFF80000001)
_ACCESS = 0x20000 | 0x1 | 0x2 | 0x4 | 0x100  # RC/query/set/create/64-bit
_REG_BINARY = 3
_FORMAT = b"hh-registry-custody-1\0"
_ID = re.compile(r"[0-9a-f]{32}\Z")
_OWNERS_LOCK = threading.RLock()
_OWNERS: dict[str, RegistryCustody] = {}
_CLEANUP_APIS: set[_RegistryApi] = set()
_MAX_OWNERS = 16
_PROVISION_LOCK = threading.Lock()


class CustodyError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner: RegistryCustody | None = None
        self.cleanup_api: _RegistryApi | None = None
        super().__init__(code)


class _SecurityAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


def _need(ok: object, code: str) -> None:
    if not ok:
        raise CustodyError(code)


def pending_custody_cleanup() -> tuple[object, ...]:
    """Strong local owners retained until their real native cleanup succeeds."""
    with _OWNERS_LOCK:
        return tuple(owner for owner in _OWNERS.values() if owner._closed) + tuple(_CLEANUP_APIS)


class _RegistryApi:
    def __init__(self) -> None:
        _need(os.name == "nt", "UNSUPPORTED_CUSTODY_WINDOWS")
        with _OWNERS_LOCK:
            _need(len(_CLEANUP_APIS) < _MAX_OWNERS, "CUSTODY_CLEANUP_CAPACITY")
        self.keys: set[int] = set()
        self.tokens: set[int] = set()
        self.allocations: set[int] = set()
        self.created_components: list[str] = []
        self.dll = C.WinDLL("kernel32", use_last_error=True)
        self.adv = C.WinDLL("advapi32", use_last_error=True)
        self.nt = C.WinDLL("ntdll", use_last_error=True)
        signatures = (
            (self.dll, "GetCurrentProcess", [], W.HANDLE),
            (self.dll, "GetCurrentThread", [], W.HANDLE),
            (self.dll, "CloseHandle", [W.HANDLE], W.BOOL),
            (self.dll, "LocalFree", [C.c_void_p], C.c_void_p),
            (self.adv, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL),
            (self.adv, "OpenThreadToken", [W.HANDLE, W.DWORD, W.BOOL, C.POINTER(W.HANDLE)], W.BOOL),
            (self.adv, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
            (self.adv, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(C.c_void_p)], W.BOOL),
            (self.adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL),
            (self.adv, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL),
            (self.adv, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD),
            (self.adv, "RegOpenKeyExW", [W.HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(W.HANDLE)], W.LONG),
            (self.adv, "RegCreateKeyExW", [W.HANDLE, W.LPCWSTR, W.DWORD, W.LPWSTR, W.DWORD, W.DWORD, C.POINTER(_SecurityAttributes), C.POINTER(W.HANDLE), C.POINTER(W.DWORD)], W.LONG),
            (self.adv, "RegQueryValueExW", [W.HANDLE, W.LPCWSTR, C.c_void_p, C.POINTER(W.DWORD), C.c_void_p, C.POINTER(W.DWORD)], W.LONG),
            (self.adv, "RegSetValueExW", [W.HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD], W.LONG),
            (self.adv, "RegFlushKey", [W.HANDLE], W.LONG),
            (self.adv, "RegCloseKey", [W.HANDLE], W.LONG),
            (self.nt, "NtQueryKey", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.LONG),
        )
        for dll, name, args, result in signatures:
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        try:
            self.owner = self._owner_sid()
            self.sddl = f"O:{self.owner}D:P(A;;RC;;;OW)(A;;KA;;;{self.owner})"
            with self.descriptor() as descriptor:
                self.expected_security = self.render_security(descriptor)
        except BaseException:
            try:
                self.close_owned()
            except CustodyError:
                error = CustodyError("CUSTODY_API_INIT_CLEANUP_UNCERTAIN", outcome_unknown=True)
                error.cleanup_api = self
                raise error from None
            raise

    def close_token(self, handle: int) -> None:
        _need(self.dll.CloseHandle(handle), "CUSTODY_TOKEN_CLOSE_FAILED")
        self.tokens.discard(handle)

    def free(self, pointer: int) -> None:
        _need(self.dll.LocalFree(pointer) is None, "CUSTODY_SECURITY_FREE_FAILED")
        self.allocations.discard(pointer)

    def close_key(self, handle: int) -> None:
        _need(self.adv.RegCloseKey(handle) == 0, "CUSTODY_KEY_CLOSE_FAILED")
        self.keys.discard(handle)

    def close_owned(self) -> None:
        failed = False
        for collection, close in ((self.keys, self.close_key), (self.tokens, self.close_token), (self.allocations, self.free)):
            for value in tuple(collection):
                try:
                    close(value)
                except SafetyViolation:
                    failed = True
        with _OWNERS_LOCK:
            if failed:
                _CLEANUP_APIS.add(self)
            else:
                _CLEANUP_APIS.discard(self)
        _need(not failed, "CUSTODY_CLEANUP_UNCERTAIN")

    def no_impersonation(self) -> None:
        token = W.HANDLE()
        if self.adv.OpenThreadToken(self.dll.GetCurrentThread(), 8, True, C.byref(token)):
            self.tokens.add(token.value)
            self.close_token(token.value)
            raise CustodyError("CUSTODY_IMPERSONATION_UNSUPPORTED")
        _need(C.get_last_error() == 1008, "CUSTODY_TOKEN_UNVERIFIED")

    def _owner_sid(self) -> str:
        self.no_impersonation()
        token = W.HANDLE()
        _need(self.adv.OpenProcessToken(self.dll.GetCurrentProcess(), 8, C.byref(token)), "CUSTODY_TOKEN_UNVERIFIED")
        self.tokens.add(token.value)
        try:
            size, container = W.DWORD(), W.DWORD()
            _need(self.adv.GetTokenInformation(token, 29, C.byref(container), C.sizeof(container), C.byref(size)), "CUSTODY_TOKEN_UNVERIFIED")
            _need(container.value == 0, "CUSTODY_BROKER_TOKEN_REQUIRED")
            self.adv.GetTokenInformation(token, 1, None, 0, C.byref(size))
            _need(0 < size.value <= 65536, "CUSTODY_TOKEN_UNVERIFIED")
            buffer = C.create_string_buffer(size.value)
            _need(self.adv.GetTokenInformation(token, 1, buffer, len(buffer), C.byref(size)), "CUSTODY_TOKEN_UNVERIFIED")
            sid = C.cast(buffer, C.POINTER(C.c_void_p)).contents.value
            rendered = C.c_void_p()
            _need(self.adv.ConvertSidToStringSidW(sid, C.byref(rendered)), "CUSTODY_TOKEN_UNVERIFIED")
            self.allocations.add(rendered.value)
            try:
                return C.wstring_at(rendered)
            finally:
                self.free(rendered.value)
        finally:
            self.close_token(token.value)

    @contextmanager
    def descriptor(self):
        descriptor = C.c_void_p()
        _need(self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(self.sddl, 1, C.byref(descriptor), None), "CUSTODY_SECURITY_UNAVAILABLE")
        self.allocations.add(descriptor.value)
        try:
            yield descriptor
        finally:
            self.free(descriptor.value)

    def render_security(self, descriptor) -> str:
        text = C.c_void_p()
        _need(self.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 5, C.byref(text), None), "CUSTODY_SECURITY_UNVERIFIED")
        self.allocations.add(text.value)
        try:
            return C.wstring_at(text)
        finally:
            self.free(text.value)

    def check_security(self, handle: int) -> None:
        descriptor = C.c_void_p()
        _need(self.adv.GetSecurityInfo(handle, 4, 5, None, None, None, None, C.byref(descriptor)) == 0, "CUSTODY_SECURITY_UNVERIFIED")
        self.allocations.add(descriptor.value)
        try:
            _need(self.render_security(descriptor) == self.expected_security, "CUSTODY_SECURITY_CHANGED")
        finally:
            self.free(descriptor.value)

    def open(self, parent, name: str, *, follow: bool = False) -> int:
        handle = W.HANDLE()
        error = self.adv.RegOpenKeyExW(parent, name, 0 if follow else 8, _ACCESS, C.byref(handle))
        if error:
            raise CustodyError("CUSTODY_KEY_MISSING" if error == 2 else "CUSTODY_OPEN_DENIED")
        self.keys.add(handle.value)
        return handle.value

    def create(self, parent, name: str) -> int:
        # Called only for an immediate component, with a checked retained parent.
        handle, disposition = W.HANDLE(), W.DWORD()
        with self.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            error = self.adv.RegCreateKeyExW(parent, name, 0, None, 0, _ACCESS,
                                            C.byref(attributes), C.byref(handle), C.byref(disposition))
            if error:
                raise CustodyError("CUSTODY_CREATE_FAILED")
            self.keys.add(handle.value)
            _need(disposition.value == 1, "CUSTODY_KEY_EXISTS")
        return handle.value

    def native_name(self, handle: int) -> str:
        buffer, length = C.create_string_buffer(32768), W.DWORD()
        _need(self.nt.NtQueryKey(handle, 3, buffer, len(buffer), C.byref(length)) == 0, "CUSTODY_PATH_UNVERIFIED")
        count = int.from_bytes(buffer.raw[:4], "little")
        _need(count % 2 == 0 and 0 < count <= len(buffer) - 4 and length.value >= 4 + count,
              "CUSTODY_PATH_UNVERIFIED")
        try:
            return buffer.raw[4:4 + count].decode("utf-16-le", "strict")
        except UnicodeError:
            raise CustodyError("CUSTODY_PATH_UNVERIFIED") from None

    def query(self, handle: int, name: str, *, cap: int = MAX_STATE_BYTES) -> tuple[int, bytes] | None:
        data, size, kind = C.create_string_buffer(cap + 1), W.DWORD(cap + 1), W.DWORD()
        error = self.adv.RegQueryValueExW(handle, name, None, C.byref(kind), data, C.byref(size))
        if error == 2:
            return None
        _need(error != 234 and size.value <= cap, "CUSTODY_STATE_LIMIT")
        _need(error == 0, "CUSTODY_READ_FAILED")
        return kind.value, data.raw[:size.value]

    def validate_key(self, handle: int, expected_path: str, *, protected: bool = True) -> None:
        _need(self.query(handle, "SymbolicLinkValue") is None, "CUSTODY_LINK_FORBIDDEN")
        _need(self.native_name(handle) == expected_path, "CUSTODY_PATH_CHANGED")
        if protected:
            self.check_security(handle)

    def validate_normal_open(self, parent, name: str, expected_path: str, *, protected: bool = True) -> None:
        # OPEN_LINK catches configured links; ordinary open must also succeed
        # at the same native name, rejecting an unfinished/broken link object.
        handle = self.open(parent, name, follow=True)
        try:
            self.validate_key(handle, expected_path, protected=protected)
        finally:
            self.close_key(handle)

    def set(self, handle: int, name: str, data: bytes) -> None:
        buffer = C.create_string_buffer(data)
        _need(self.adv.RegSetValueExW(handle, name, 0, _REG_BINARY, buffer, len(data)) == 0, "CUSTODY_WRITE_FAILED")

    def flush(self, handle: int) -> None:
        _need(self.adv.RegFlushKey(handle) == 0, "CUSTODY_BARRIER_FAILED")

    def base(self, *, provision: bool = False) -> tuple[int, list[tuple[int, str]], tuple[str, ...]]:
        self.no_impersonation()
        software = self.open(_HKCU, "Software")
        native = self.native_name(software)
        _need(native.casefold() == ("\\REGISTRY\\USER\\" + self.owner + "\\Software").casefold(), "CUSTODY_USER_ROOT_CHANGED")
        self.validate_key(software, native, protected=False)
        self.validate_normal_open(_HKCU, "Software", native, protected=False)
        records, created = [], []
        parent = software
        for part in BASE_PARTS:
            path = native + "\\" + part
            try:
                child = self.open(parent, part)
            except CustodyError as exc:
                if exc.code != "CUSTODY_KEY_MISSING" or not provision:
                    raise
                child = self.create(parent, part)
                created.append(path)
                self.created_components.append(path)
                self.flush(child)
            self.validate_key(child, path)
            self.validate_normal_open(parent, part, path)
            records.append((child, path))
            parent, native = child, path
        return parent, records, tuple(created)


class RegistryCustody:
    """Opaque state anchor with one live local owner per trusted local UUID."""

    @classmethod
    def provision_base(cls) -> tuple[str, ...]:
        """Explicit trusted setup; never rewrites any existing key's ACL.

        Returns product-owned parent paths created during this call. They are
        configuration, not disposable test leaves and are never auto-deleted.
        """
        with _PROVISION_LOCK:
            api = _RegistryApi()
            started = False
            try:
                # Any failed setup may have created a parent; preserve it.
                started = True
                _, _, created = api.base(provision=True)
                return created
            except BaseException as exc:
                if started and isinstance(exc, (SafetyViolation, OSError)):
                    error = CustodyError("CUSTODY_PROVISION_UNCERTAIN", outcome_unknown=True)
                    error.created_components = tuple(api.created_components)
                    raise error from exc
                raise
            finally:
                try:
                    api.close_owned()
                except CustodyError:
                    error = CustodyError("CUSTODY_PROVISION_CLEANUP_UNCERTAIN", outcome_unknown=True)
                    error.cleanup_api = api
                    raise error from None

    @classmethod
    def create(cls, local_id: str) -> RegistryCustody:
        return cls(local_id, create=True)

    @classmethod
    def reopen(cls, local_id: str) -> RegistryCustody:
        return cls(local_id, create=False)

    def __init__(self, local_id: str, *, create: bool) -> None:
        _need(type(local_id) is str and _ID.fullmatch(local_id), "CUSTODY_LOCAL_ID_INVALID")
        self._local_id = local_id
        self._mutex = threading.RLock()
        self._closed = self._poisoned = False
        self._fresh = create
        self._api: _RegistryApi | None = None
        self._marker = _FORMAT + local_id.encode("ascii")
        with _OWNERS_LOCK:
            _need(local_id not in _OWNERS, "CUSTODY_LOCAL_OWNER_EXISTS")
            _need(len(_OWNERS) + len(_CLEANUP_APIS) < _MAX_OWNERS, "CUSTODY_OWNER_LIMIT")
            _OWNERS[local_id] = self
        started = False
        try:
            try:
                self._api = _RegistryApi()
            except CustodyError as exc:
                self._api = exc.cleanup_api
                raise
            base, self._parents, _ = self._api.base()
            self._path = self._parents[-1][1] + "\\" + local_id
            if create:
                # Distinguish collision before any registry mutation attempt.
                try:
                    existing = self._api.open(base, local_id)
                except CustodyError as exc:
                    if exc.code != "CUSTODY_KEY_MISSING":
                        raise
                else:
                    self._api.close_key(existing)
                    raise CustodyError("CUSTODY_KEY_EXISTS")
                started = True
                self._handle = self._api.create(base, local_id)
                self._api.validate_key(self._handle, self._path)
                self._api.set(self._handle, "Format", self._marker)
                self._api.flush(self._handle)
            else:
                self._handle = self._api.open(base, local_id)
            self._api.validate_normal_open(base, local_id, self._path)
            self._check()
            self._api.flush(self._handle)
            self._read_value()
        except BaseException as exc:
            self._poisoned = started
            try:
                self.close()
            except CustodyError:
                error = CustodyError("CUSTODY_INIT_CLEANUP_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            if started:
                raise CustodyError("CUSTODY_INIT_UNCERTAIN", outcome_unknown=True) from exc
            raise

    def _check(self) -> None:
        _need(not self._closed, "CUSTODY_CLOSED")
        if self._poisoned:
            raise CustodyError("CUSTODY_RECONCILIATION_REQUIRED", outcome_unknown=True)
        self._api.no_impersonation()
        for handle, path in self._parents:
            self._api.validate_key(handle, path)
        self._api.validate_key(self._handle, self._path)
        _need(self._api.query(self._handle, "Format") == (_REG_BINARY, self._marker), "CUSTODY_FORMAT_INVALID")

    def _read_value(self) -> bytes | None:
        value = self._api.query(self._handle, "State")
        if value is None:
            _need(self._fresh, "CUSTODY_INCOMPLETE_PROVISIONING")
            return None
        _need(value[0] == _REG_BINARY, "CUSTODY_STATE_TYPE_INVALID")
        self._fresh = False
        return value[1]

    @property
    def local_id(self) -> str:
        return self._local_id

    def read(self) -> bytes | None:
        with self._mutex:
            try:
                self._check()
                self._api.flush(self._handle)
                value = self._read_value()
                self._check()
                return value
            except BaseException:
                self._poisoned = True
                raise

    def store(self, data: bytes, expected: bytes | None) -> None:
        _need(type(data) is bytes and len(data) <= MAX_STATE_BYTES, "CUSTODY_STATE_LIMIT")
        _need(expected is None or (type(expected) is bytes and len(expected) <= MAX_STATE_BYTES), "CUSTODY_EXPECTED_INVALID")
        with self._mutex:
            started = False
            try:
                self._check()
                self._api.flush(self._handle)
                _need(self._read_value() == expected, "CUSTODY_STATE_CONFLICT")
                started = True  # A failed native set is not permission to retry.
                self._api.set(self._handle, "State", data)
                self._api.flush(self._handle)
                _need(self._api.query(self._handle, "State") == (_REG_BINARY, data), "CUSTODY_READBACK_FAILED")
                self._check()
                self._fresh = False
            except BaseException as exc:
                if started:
                    self._poisoned = True
                    raise CustodyError("CUSTODY_STORE_UNCERTAIN", outcome_unknown=True) from exc
                if not (isinstance(exc, CustodyError) and exc.code == "CUSTODY_STATE_CONFLICT"):
                    self._poisoned = True
                raise

    def close(self) -> None:
        with self._mutex:
            self._closed = True
            try:
                if self._api is not None:
                    self._api.close_owned()
            except CustodyError:
                error = CustodyError("CUSTODY_CLOSE_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            with _OWNERS_LOCK:
                if _OWNERS.get(self.local_id) is self:
                    del _OWNERS[self.local_id]

    def __enter__(self) -> RegistryCustody:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
