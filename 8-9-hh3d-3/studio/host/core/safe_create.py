"""Bounded Windows create-only publication experiment.

This module deliberately does not change ``safe_open.capabilities()``. It
proves the smaller primitive needed before a replace operation: bytes are
written through one retained handle while the new name is delete-pending,
then the immutable handle is renamed exactly once. Replace/CAS remains
unsupported until its destination identity and durability contract is proved.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import struct
import threading
import uuid
from typing import Iterator

from .limits import SafePathResolver, SafetyViolation
from .safe_open import (_BACKUP, _LIST_DIRECTORY, _NOFOLLOW, _FileStandardInfo,
                        _READ_ATTRIBUTES, _WindowsApi, FileIdentity)

MAX_BYTES = 1024 * 1024


class SafeCreateError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        super().__init__(code)


class SafeCreateApi(_WindowsApi):
    def __init__(self) -> None:
        super().__init__()
        self.owned: set[int] = set()
        self.dll.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                       wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.dll.WriteFile.restype = wintypes.BOOL
        self.dll.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.dll.FlushFileBuffers.restype = wintypes.BOOL
        self.dll.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                                        ctypes.c_void_p, wintypes.DWORD]
        self.dll.SetFileInformationByHandle.restype = wintypes.BOOL

    def open_parent(self, path: Path, *, publish: bool) -> int:
        # The final parent permits the kernel's destination open to complete
        # (read/write share, no delete share). Ancestors remain delete-locked.
        share = 3 if publish else 1
        access = _READ_ATTRIBUTES | _LIST_DIRECTORY
        handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, share, None,
                                      3, _NOFOLLOW | _BACKUP, None)
        if handle == ctypes.c_void_p(-1).value:
            raise SafetyViolation("SAFE_PARENT_OPEN_FAILED")
        self.owned.add(handle)
        return handle

    def open_new(self, path: Path) -> int:
        access = 0xC0000000 | 0x00010000 | _READ_ATTRIBUTES
        handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, 0, None,
                                      1, _NOFOLLOW | 0x80000000, None)
        if handle == ctypes.c_void_p(-1).value:
            code = "DESTINATION_EXISTS" if ctypes.get_last_error() in (80, 183) else "SAFE_OPEN_DENIED"
            raise SafetyViolation(code)
        self.owned.add(handle)
        return handle

    def close(self, handle: int) -> None:
        if not self.dll.CloseHandle(handle):
            raise SafeCreateError("SAFE_CREATE_CLOSE_UNCERTAIN", outcome_unknown=True)
        self.owned.discard(handle)

    def close_owned(self) -> None:
        failed = False
        for handle in tuple(self.owned):
            try:
                self.close(handle)
            except SafeCreateError:
                failed = True
        if failed:
            raise SafeCreateError("SAFE_CREATE_CLOSE_UNCERTAIN", outcome_unknown=True)

    def pending(self, handle: int, value: bool) -> None:
        flag = ctypes.c_int(1 if value else 0)
        if not self.dll.SetFileInformationByHandle(handle, 4, ctypes.byref(flag), ctypes.sizeof(flag)):
            raise SafetyViolation("SAFE_DELETE_PENDING_FAILED")

    def write_flush(self, handle: int, data: bytes) -> None:
        standard = _FileStandardInfo()
        if not self.dll.GetFileInformationByHandleEx(handle, 1, ctypes.byref(standard), ctypes.sizeof(standard)):
            raise SafetyViolation("SAFE_PENDING_UNVERIFIED")
        # NTFS excludes the pending link from NumberOfLinks. Any remaining
        # link proves an alias appeared before the pending transition.
        if not standard.delete_pending or standard.directory or standard.links != 0:
            raise SafetyViolation("SAFE_PENDING_ALIAS")
        buf, count = ctypes.create_string_buffer(data), wintypes.DWORD()
        if not self.dll.WriteFile(handle, buf, len(data), ctypes.byref(count), None):
            raise SafetyViolation("SAFE_WRITE_FAILED")
        if count.value != len(data):
            raise SafetyViolation("SAFE_SHORT_WRITE")
        if not self.dll.FlushFileBuffers(handle):
            raise SafetyViolation("SAFE_FLUSH_FAILED")

    def rename(self, handle: int, destination: Path) -> None:
        encoded = str(destination).encode("utf-16-le")
        payload = bytearray(20 + len(encoded) + 2)
        struct.pack_into("<I4xQI", payload, 0, 0, 0, len(encoded))
        payload[20:20 + len(encoded)] = encoded
        view = (ctypes.c_ubyte * len(payload)).from_buffer(payload)
        if not self.dll.SetFileInformationByHandle(handle, 3, view, len(payload)):
            raise SafetyViolation("SAFE_RENAME_FAILED")

    def flush_parent(self, path: Path, expected: FileIdentity) -> None:
        handle = self.dll.CreateFileW("\\\\?\\" + str(path), 0x40000000 | _READ_ATTRIBUTES | _LIST_DIRECTORY,
                                      1, None, 3, _NOFOLLOW | _BACKUP, None)
        if handle == ctypes.c_void_p(-1).value:
            raise SafetyViolation("SAFE_DIRECTORY_FLUSH_UNAVAILABLE")
        self.owned.add(handle)
        try:
            if not expected.same_file(self.inspect(handle, path, directory=True)):
                raise SafetyViolation("DIRECTORY_IDENTITY_CHANGED")
            if not self.dll.FlushFileBuffers(handle):
                raise SafetyViolation("SAFE_DIRECTORY_FLUSH_UNAVAILABLE")
        finally:
            self.close(handle)


class SafeCreateOnly:
    """Create-only proof object; never replaces an existing destination."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        if os.name != "nt":
            raise SafetyViolation("UNSUPPORTED_SAFE_OPEN_LINUX")
        self._resolver = SafePathResolver(root)
        self._root = self._resolver.root
        self._api = SafeCreateApi()
        self._root_identity: FileIdentity | None = None
        self._poisoned = self._closed = False
        self._mutex = threading.Lock()
        with self._parents(self._root) as handle:
            self._root_identity = self._api.inspect(handle, self._root, directory=True)

    def close(self) -> None:
        with self._mutex:
            self._closed = True
            self._api.close_owned()

    @contextmanager
    def _parents(self, parent: Path) -> Iterator[int]:
        records: list[tuple[int, Path, FileIdentity]] = []
        directories = (*reversed(parent.parents), parent)
        try:
            for index, directory in enumerate(directories):
                handle = self._api.open_parent(directory, publish=index == len(directories) - 1)
                try:
                    identity = self._api.inspect(handle, directory, directory=True)
                except BaseException:
                    self._api.close(handle)
                    raise
                records.append((handle, directory, identity))
                if directory == self._root and self._root_identity is not None and not self._root_identity.same_file(identity):
                    raise SafetyViolation("ROOT_IDENTITY_CHANGED")
            yield records[-1][0]
            for handle, directory, identity in records:
                if not identity.same_file(self._api.inspect(handle, directory, directory=True)):
                    raise SafetyViolation("DIRECTORY_IDENTITY_CHANGED")
        finally:
            failure = False
            for handle, _, _ in reversed(records):
                try:
                    self._api.close(handle)
                except SafeCreateError:
                    failure = True
            if failure:
                raise SafeCreateError("SAFE_CREATE_CLOSE_UNCERTAIN", outcome_unknown=True)

    def create_new(self, relative: str, data: bytes) -> FileIdentity:
        with self._mutex:
            if self._closed or self._poisoned:
                raise SafeCreateError("SAFE_CREATE_RECONCILIATION_REQUIRED", outcome_unknown=self._poisoned)
            self._started = False
            try:
                return self._create_new(relative, data)
            except BaseException:
                if self._started:
                    self._poisoned = True
                    raise SafeCreateError("SAFE_CREATE_UNCERTAIN", outcome_unknown=True) from None
                raise

    def _create_new(self, relative: str, data: bytes) -> FileIdentity:
        if type(data) is not bytes or len(data) > MAX_BYTES:
            raise SafetyViolation("SAFE_SIZE_LIMIT")
        destination = self._resolver.resolve(relative, require_existing=False)
        if destination.exists():
            raise SafetyViolation("DESTINATION_EXISTS")
        with self._parents(destination.parent) as parent_handle:
            parent_identity = self._api.inspect(parent_handle, destination.parent, directory=True)
            self._api.flush_parent(destination.parent, parent_identity)
            if destination.exists():
                raise SafetyViolation("DESTINATION_EXISTS")
            stage = destination.parent / (".hh-stage-" + uuid.uuid4().hex)
            handle = self._api.open_new(stage)
            self._started = True
            published = False
            try:
                before = self._api.inspect(handle, stage)
                self._api.pending(handle, True)
                self._api.write_flush(handle, data)
                if self._api.read(handle, MAX_BYTES) != data:
                    raise SafetyViolation("SAFE_READBACK_FAILED")
                self._api.pending(handle, False)
                after = self._api.inspect(handle, stage)
                if before.file_id != after.file_id or before.volume != after.volume or after.size != len(data):
                    raise SafetyViolation("FILE_IDENTITY_CHANGED")
                self._api.rename(handle, destination)
                published = True
                result = self._api.inspect(handle, destination)
                if result.size != len(data) or self._api.read(handle, MAX_BYTES) != data:
                    raise SafetyViolation("SAFE_READBACK_FAILED")
                self._api.flush_parent(destination.parent, parent_identity)
                return result
            except BaseException:
                self._poisoned = True
                raise SafeCreateError("SAFE_CREATE_UNCERTAIN", outcome_unknown=True) from None
            finally:
                if not published:
                    try:
                        self._api.pending(handle, True)
                    except SafetyViolation:
                        pass
                try:
                    self._api.close(handle)
                except SafeCreateError:
                    self._poisoned = True
                    raise
