"""Experimental broker-owned, create-only Windows staging storage.

This is not a transport operation, active release, or COMMITTED receipt. The
caller is trusted broker code; all untrusted processes must be OS-confined and
receive neither this object nor its handles/root. Ordinary unrestricted peers
using the broker's OS account are outside this boundary. A random name is not
the permission mechanism: every object gets an explicit protected owner DACL.

Existing public safe_write/atomic_replace capabilities remain false. This
building block has no IPC/sandbox launcher, lease/dedupe, activation, namespace
durability acknowledgement or automatic recovery/cleanup. Failed staging stays
on disk for reconciliation, and poisons the instance instead of retrying writes.
Only local NTFS and a trusted, retained ancestor chain are accepted.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import threading
from typing import Iterator
import uuid

from .limits import SafePathResolver, SafetyViolation
from .safe_open import FileIdentity, _WindowsApi


MAX_BLOB_BYTES = 1024 * 1024
MAX_STAGED_OBJECTS = 64
MAX_STAGED_BYTES = 8 * 1024 * 1024
_READ_CONTROL = 0x20000
_INVALID = C.c_void_p(-1).value
_BLOB = re.compile(r"blob-[0-9a-f]{32}\Z")
_ROOT = re.compile(r"hh-private-[0-9a-f]{32}\Z")


class PrivateStoreError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        # Internal local cleanup ownership, never serialized to a client.
        self.cleanup_owner: PrivateBlobStore | None = None
        super().__init__(code)


@dataclass(frozen=True)
class StagedBlob:
    """Local broker descriptor, not a trusted value accepted from the wire."""

    object_id: str
    identity: FileIdentity
    sha256: str


class _SecurityAttributes(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]


class _StoreApi(_WindowsApi):
    def __init__(self) -> None:
        super().__init__()
        self._owned_handles: set[int] = set()
        self.adv = C.WinDLL("advapi32", use_last_error=True)
        signatures = (
            (self.dll, "GetCurrentProcess", [], W.HANDLE),
            (self.dll, "GetCurrentThread", [], W.HANDLE),
            (self.dll, "LocalFree", [C.c_void_p], C.c_void_p),
            (self.dll, "CreateDirectoryW", [W.LPCWSTR, C.POINTER(_SecurityAttributes)], W.BOOL),
            (self.dll, "WriteFile", [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p], W.BOOL),
            (self.dll, "FlushFileBuffers", [W.HANDLE], W.BOOL),
            (self.dll, "GetVolumeInformationByHandleW", [W.HANDLE, W.LPWSTR, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, W.LPWSTR, W.DWORD], W.BOOL),
            (self.adv, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL),
            (self.adv, "OpenThreadToken", [W.HANDLE, W.DWORD, W.BOOL, C.POINTER(W.HANDLE)], W.BOOL),
            (self.adv, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL),
            (self.adv, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL),
            (self.adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL),
            (self.adv, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD),
            (self.adv, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(W.LPWSTR), C.c_void_p], W.BOOL),
        )
        for dll, name, args, result in signatures:
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        self.owner = self._owner_sid()
        # OWNER RIGHTS suppresses implicit owner WRITE_DAC; only the broker
        # user's explicit ACE grants mutation. No inherited/package grants.
        self.sddl = f"O:{self.owner}D:P(A;;RC;;;OW)(A;;FA;;;{self.owner})"
        with self.descriptor() as descriptor:
            self.expected_security = self._render_security(descriptor)

    def _checked(self, result: object, code: str) -> None:
        if not result:
            raise PrivateStoreError(code)

    def check_no_impersonation(self) -> None:
        thread = W.HANDLE()
        if self.adv.OpenThreadToken(self.dll.GetCurrentThread(), 8, True, C.byref(thread)):
            self.close(thread.value)
            raise PrivateStoreError("BROKER_IMPERSONATION_UNSUPPORTED")
        if C.get_last_error() != 1008:  # ERROR_NO_TOKEN
            raise PrivateStoreError("BROKER_TOKEN_UNVERIFIED")

    def _owner_sid(self) -> str:
        self.check_no_impersonation()
        token, rendered = W.HANDLE(), W.LPWSTR()
        self._checked(self.adv.OpenProcessToken(self.dll.GetCurrentProcess(), 8, C.byref(token)), "BROKER_TOKEN_UNVERIFIED")
        try:
            count, container = W.DWORD(), W.DWORD()
            self._checked(self.adv.GetTokenInformation(token, 29, C.byref(container), C.sizeof(container), C.byref(count)), "BROKER_TOKEN_UNVERIFIED")
            if container.value:
                raise PrivateStoreError("BROKER_TOKEN_UNVERIFIED")
            self.adv.GetTokenInformation(token, 1, None, 0, C.byref(count))
            if not 0 < count.value <= 65536:
                raise PrivateStoreError("BROKER_TOKEN_UNVERIFIED")
            buffer = C.create_string_buffer(count.value)
            self._checked(self.adv.GetTokenInformation(token, 1, buffer, len(buffer), C.byref(count)), "BROKER_TOKEN_UNVERIFIED")
            sid = C.cast(buffer, C.POINTER(C.c_void_p)).contents.value
            self._checked(self.adv.ConvertSidToStringSidW(sid, C.byref(rendered)), "BROKER_TOKEN_UNVERIFIED")
            return rendered.value
        finally:
            if rendered:
                self.dll.LocalFree(rendered)
            self.close(token.value)

    @contextmanager
    def descriptor(self) -> Iterator[C.c_void_p]:
        descriptor = C.c_void_p()
        self._checked(self.adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(self.sddl, 1, C.byref(descriptor), None), "PRIVATE_ACL_UNAVAILABLE")
        try:
            yield descriptor
        finally:
            self.dll.LocalFree(descriptor)

    def _render_security(self, descriptor: C.c_void_p) -> str:
        value = W.LPWSTR()
        self._checked(self.adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 5, C.byref(value), None), "PRIVATE_ACL_UNVERIFIED")
        try:
            return value.value
        finally:
            self.dll.LocalFree(value)

    def check_security(self, handle: int) -> None:
        descriptor = C.c_void_p()
        error = self.adv.GetSecurityInfo(handle, 1, 5, None, None, None, None, C.byref(descriptor))
        if error:
            raise PrivateStoreError("PRIVATE_ACL_UNVERIFIED")
        try:
            if self._render_security(descriptor) != self.expected_security:
                raise PrivateStoreError("PRIVATE_ACL_CHANGED")
        finally:
            self.dll.LocalFree(descriptor)

    def mkdir(self, path: Path) -> None:
        with self.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            self._checked(self.dll.CreateDirectoryW("\\\\?\\" + str(path), C.byref(attributes)), "PRIVATE_ROOT_CREATE_FAILED")

    def open(self, path: Path, *, directory: bool = False, create: bool = False, writer: bool = False) -> int:
        access = (0x81 if directory else 0x80000000) | _READ_CONTROL
        if create or writer:
            access |= 0x40000000
        flags = 0x00200000 | (0x02000000 if directory else 0)
        if create or writer:
            flags |= 0x80000000  # FILE_FLAG_WRITE_THROUGH, not NO_BUFFERING
        with self.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, 1 if directory else 0, C.byref(attributes), 1 if create else 3, flags, None)
        if handle == _INVALID:
            code = "DESTINATION_EXISTS" if C.get_last_error() in (80, 183) else "PRIVATE_OPEN_DENIED"
            raise PrivateStoreError(code)
        self._owned_handles.add(handle)
        return handle

    def ntfs(self, handle: int) -> None:
        name = C.create_unicode_buffer(256)
        self._checked(self.dll.GetVolumeInformationByHandleW(handle, None, 0, None, None, None, name, len(name)), "PRIVATE_VOLUME_UNVERIFIED")
        if name.value != "NTFS":
            raise PrivateStoreError("PRIVATE_FILESYSTEM_UNSUPPORTED")

    def write(self, handle: int, data: bytes) -> None:
        # A short write is uncertain; never blindly replay a partial blob.
        count = W.DWORD()
        buffer = C.create_string_buffer(data)
        self._checked(self.dll.WriteFile(handle, buffer, len(data), C.byref(count), None), "PRIVATE_WRITE_FAILED")
        if count.value != len(data):
            raise PrivateStoreError("PRIVATE_SHORT_WRITE")

    def flush(self, handle: int) -> None:
        self._checked(self.dll.FlushFileBuffers(handle), "PRIVATE_FLUSH_FAILED")

    def close(self, handle: int) -> None:
        self._checked(self.dll.CloseHandle(handle), "PRIVATE_CLOSE_FAILED")
        self._owned_handles.discard(handle)

    def close_owned(self) -> None:
        # ExitStack removes a callback even if it raises. The registry retains
        # ownership until an actual successful native close, allowing retries.
        failed = False
        for handle in tuple(self._owned_handles):
            try:
                self.close(handle)
            except SafetyViolation:
                failed = True
        if failed:
            raise PrivateStoreError("PRIVATE_CLOSE_UNCERTAIN", outcome_unknown=True)


class PrivateBlobStore:
    """Single-broker staging instance. Constructor settings are never wire data.

    create() mints a private child root; reopen() requires the saved root
    identity from trusted broker state. Both keep the entire ancestor chain
    and a share=0 guard until close(). A staged result must later be activated
    by a separate journal/recovery transaction; put_bytes() does not do that.
    """

    @classmethod
    def create(cls, parent: str | os.PathLike[str]) -> PrivateBlobStore:
        return cls(parent, expected_root=None)

    @classmethod
    def reopen(cls, root: str | os.PathLike[str], expected_root: FileIdentity) -> PrivateBlobStore:
        if type(expected_root) is not FileIdentity:
            raise PrivateStoreError("PRIVATE_ROOT_IDENTITY_REQUIRED")
        return cls(root, expected_root=expected_root)

    def __init__(self, path: str | os.PathLike[str], *, expected_root: FileIdentity | None) -> None:
        self._api = _StoreApi()
        self._stack = ExitStack()
        self._closed, self._poisoned = False, False
        self._mutex = threading.Lock()
        created = False
        try:
            spelling = os.fspath(path)
            if type(spelling) is not str or not re.match(r"^[A-Za-z]:[\\/]", spelling) or spelling.startswith("\\\\"):
                raise PrivateStoreError("INVALID_PROJECT_ROOT")
            canonical = SafePathResolver(path).root
            if os.path.normcase(str(canonical)) != os.path.normcase(os.path.abspath(spelling)):
                raise PrivateStoreError("ROOT_PATH_CHANGED")
            records: list[tuple[int, Path, FileIdentity]] = []
            self._ancestor_records = records
            for parent in (*reversed(canonical.parents), canonical):
                ancestor = self._api.open(parent, directory=True)
                self._stack.callback(self._api.close, ancestor)
                records.append((ancestor, parent, self._api.inspect(ancestor, parent, directory=True)))
            # Refuse unsupported volumes before creating the new root.
            self._api.ntfs(records[-1][0])
            if expected_root is None:
                self.root = canonical / ("hh-private-" + uuid.uuid4().hex)
                self._api.mkdir(self.root)
                created = True
            else:
                self.root = canonical
                if not _ROOT.fullmatch(self.root.name) or not expected_root.same_file(records[-1][2]):
                    raise PrivateStoreError("PRIVATE_ROOT_IDENTITY_CHANGED")
            handle = self._api.open(self.root, directory=True)
            self._stack.callback(self._api.close, handle)
            self._root_handle = handle
            self.root_identity = self._api.inspect(handle, self.root, directory=True)
            self._api.check_security(handle)
            self._api.ntfs(handle)
            guard = self._api.open(self.root / ".writer", create=expected_root is None, writer=True)
            self._stack.callback(self._api.close, guard)
            guard_id = self._api.inspect(guard, self.root / ".writer")
            self._guard_handle, self._guard_identity = guard, guard_id
            self._api.check_security(guard)
            if guard_id.volume != self.root_identity.volume or guard_id.size != 0:
                raise PrivateStoreError("PRIVATE_GUARD_INVALID")
        except BaseException as exc:
            self._poisoned = created
            try:
                self.close()
            except SafetyViolation:
                error = PrivateStoreError("PRIVATE_INIT_CLEANUP_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            if created and isinstance(exc, (SafetyViolation, OSError)):
                error = PrivateStoreError("PRIVATE_INIT_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            raise

    def __enter__(self) -> PrivateBlobStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._mutex:
            if not self._closed:
                self._closed = True
                try:
                    self._stack.close()
                finally:
                    self._api.close_owned()
            else:
                self._api.close_owned()

    def _check(self) -> None:
        if self._closed or self._poisoned:
            raise PrivateStoreError("PRIVATE_STORE_RECONCILIATION_REQUIRED", outcome_unknown=self._poisoned)
        self._api.check_no_impersonation()
        current = self._api.inspect(self._root_handle, self.root, directory=True)
        if not self.root_identity.same_file(current):
            raise PrivateStoreError("PRIVATE_ROOT_IDENTITY_CHANGED")
        self._api.check_security(self._root_handle)
        for handle, path, identity in self._ancestor_records:
            after = self._api.inspect(handle, path, directory=True)
            if not identity.same_file(after):
                raise PrivateStoreError("PRIVATE_ANCESTOR_IDENTITY_CHANGED")
        guard = self._api.inspect(self._guard_handle, self.root / ".writer")
        if guard != self._guard_identity:
            raise PrivateStoreError("PRIVATE_GUARD_INVALID")
        self._api.check_security(self._guard_handle)

    def _check_quota(self, requested: int) -> None:
        count, size = 0, 0
        # Enumeration supplies names only. Retained ancestors pin this root;
        # all metadata/security is read from subsequently verified handles.
        with os.scandir(self.root) as entries:
            for entry in entries:
                if entry.name == ".writer":
                    continue
                count += 1
                if count >= MAX_STAGED_OBJECTS:
                    raise PrivateStoreError("PRIVATE_STAGE_QUOTA")
                if not _BLOB.fullmatch(entry.name):
                    raise PrivateStoreError("PRIVATE_STAGE_RECONCILIATION_REQUIRED")
                path = self.root / entry.name
                handle = self._api.open(path)
                try:
                    identity = self._api.inspect(handle, path)
                    self._api.check_security(handle)
                    if identity.volume != self.root_identity.volume or not 0 <= identity.size <= MAX_BLOB_BYTES:
                        raise PrivateStoreError("PRIVATE_STAGE_RECONCILIATION_REQUIRED")
                    size += identity.size
                finally:
                    self._api.close(handle)
                if size + requested > MAX_STAGED_BYTES:
                    raise PrivateStoreError("PRIVATE_STAGE_QUOTA")

    def put_bytes(self, data: bytes) -> StagedBlob:
        if type(data) is not bytes or len(data) > MAX_BLOB_BYTES:
            raise PrivateStoreError("PRIVATE_BLOB_LIMIT")
        with self._mutex:
            self._check()
            self._check_quota(len(data))
            object_id = "blob-" + uuid.uuid4().hex
            path = self.root / object_id
            handle = self._api.open(path, create=True)
            try:
                before = self._api.inspect(handle, path)
                self._api.check_security(handle)
                if before.size or before.volume != self.root_identity.volume:
                    raise PrivateStoreError("PRIVATE_NEW_IDENTITY_INVALID")
                self._api.write(handle, data)
                self._api.flush(handle)
                actual = self._api.read(handle, MAX_BLOB_BYTES)
                after = self._api.inspect(handle, path)
                self._api.check_security(handle)
                self._check()
                if not before.same_file(after) or after.size != len(data) or actual != data:
                    raise PrivateStoreError("PRIVATE_READBACK_MISMATCH")
                blob = StagedBlob(object_id, after, hashlib.sha256(actual).hexdigest())
            except BaseException as exc:
                self._poisoned = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise PrivateStoreError("PRIVATE_STAGE_UNCERTAIN", outcome_unknown=True) from None
                raise
            finally:
                try:
                    self._api.close(handle)
                except SafetyViolation:
                    self._poisoned = True
                    raise PrivateStoreError("PRIVATE_CLOSE_UNCERTAIN", outcome_unknown=True) from None
            return blob

    def read_blob(self, blob: StagedBlob) -> bytes:
        if (type(blob) is not StagedBlob or type(blob.object_id) is not str or not _BLOB.fullmatch(blob.object_id)
                or type(blob.identity) is not FileIdentity or type(blob.sha256) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", blob.sha256)
                or type(blob.identity.size) is not int or not 0 <= blob.identity.size <= MAX_BLOB_BYTES):
            raise PrivateStoreError("PRIVATE_BLOB_INVALID")
        with self._mutex:
            self._check()
            path = self.root / blob.object_id
            handle = self._api.open(path)
            try:
                before = self._api.inspect(handle, path)
                self._api.check_security(handle)
                if before != blob.identity or before.volume != self.root_identity.volume:
                    raise PrivateStoreError("PRIVATE_BLOB_IDENTITY_CHANGED")
                data = self._api.read(handle, MAX_BLOB_BYTES)
                after = self._api.inspect(handle, path)
                self._api.check_security(handle)
                self._check()
                if before != after or len(data) != after.size or hashlib.sha256(data).hexdigest() != blob.sha256:
                    raise PrivateStoreError("PRIVATE_READBACK_MISMATCH")
                return data
            finally:
                self._api.close(handle)
