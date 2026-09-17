"""Windows held-handle read/identity probe; all mutation fails closed.

GT-02 requires Windows CreateFileW(FILE_FLAG_OPEN_REPARSE_POINT), final
canonical handle paths, FileIdInfo + FileStandardInfo, protected ancestors
and identity-preserving replace. FILE_FLAG_OPEN_REPARSE_POINT controls the
opened object; checking the final component alone does not prove that the
ancestors were not swapped. A check followed by os.replace is another race.

Every ancestor is held without write/delete sharing, and every opened handle
is checked for reparse tags, identity and canonical path before data use.
Mutation is unsupported, including CREATE_NEW. The executable adversarial
test proves that Windows permits a second hardlink while a file handle has
share=0; link-count inspection followed by WriteFile would therefore still
permit an outside write. Exclusive handles alone do not prove a private
staging namespace. No unverified write/publish prototype is retained here.
This read primitive is not an immutable snapshot, lease, journal or recovery
manager. Linux remains unsupported until an equivalent openat2 path exists.

Official API references (reviewed 2026-09-14):
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew
https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex
https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info
https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info
https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Iterator, NoReturn

from .limits import SafePathResolver, SafetyViolation


_MAX_BYTES = 1024 * 1024
_REPARSE = 0x400
_DIRECTORY = 0x10
_NOFOLLOW = 0x00200000
_BACKUP = 0x02000000
_READ = 0x80000000
_READ_ATTRIBUTES = 0x80
_LIST_DIRECTORY = 0x1


class _FileIdInfo(ctypes.Structure):
    _fields_ = [("volume", ctypes.c_ulonglong), ("identifier", ctypes.c_ubyte * 16)]


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [("allocation", ctypes.c_longlong), ("size", ctypes.c_longlong),
                ("links", wintypes.DWORD), ("delete_pending", ctypes.c_ubyte),
                ("directory", ctypes.c_ubyte)]


class _FileAttributeInfo(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]


@dataclass(frozen=True)
class FileIdentity:
    volume: int
    file_id: str
    size: int

    def same_file(self, other: FileIdentity) -> bool:
        return (self.volume, self.file_id) == (other.volume, other.file_id)


class _WindowsApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise SafetyViolation(unsupported_code())
        try:
            self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
            signatures = {
                "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
                "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
                "GetFileInformationByHandleEx": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
                "GetFinalPathNameByHandleW": ([wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD], wintypes.DWORD),
                "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
                "SetFilePointerEx": ([wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(self.dll, name)
                function.argtypes, function.restype = arguments, result
        except (AttributeError, OSError):
            raise SafetyViolation(unsupported_code()) from None

    def open(self, path: Path, *, directory: bool = False) -> int:
        flags = _NOFOLLOW | (_BACKUP if directory else 0)
        # Attribute-only access is exempt from sharing checks and does not
        # block a directory rename. Request directory data access as well.
        access = (_READ_ATTRIBUTES | _LIST_DIRECTORY) if directory else _READ
        # Inheritable=false; no write/delete sharing; OPEN_EXISTING only.
        handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, 1, None, 3, flags, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.get_last_error()
            code = "PATH_NOT_FOUND" if error in (2, 3) else (
                "DESTINATION_EXISTS" if error in (80, 183) else "SAFE_OPEN_DENIED")
            raise SafetyViolation(code)
        return handle

    def close(self, handle: int) -> None:
        self.dll.CloseHandle(handle)

    def inspect(self, handle: int, expected_path: Path, *, directory: bool = False) -> FileIdentity:
        identity, standard, attributes = _FileIdInfo(), _FileStandardInfo(), _FileAttributeInfo()
        for info_class, structure in ((18, identity), (1, standard), (9, attributes)):
            if not self.dll.GetFileInformationByHandleEx(handle, info_class, ctypes.byref(structure), ctypes.sizeof(structure)):
                raise SafetyViolation(unsupported_code())
        if attributes.attributes & _REPARSE or attributes.tag:
            raise SafetyViolation("REPARSE_OR_SYMLINK")
        if bool(standard.directory) != directory or bool(attributes.attributes & _DIRECTORY) != directory:
            raise SafetyViolation("UNEXPECTED_FILE_TYPE")
        if standard.delete_pending:
            raise SafetyViolation("FILE_DELETE_PENDING")
        if not directory and standard.links != 1:
            raise SafetyViolation("HARDLINK_UNSAFE")
        buffer = ctypes.create_unicode_buffer(32768)
        count = self.dll.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not count or count >= len(buffer):
            raise SafetyViolation("UNVERIFIED_FINAL_PATH")
        final = buffer.value
        if not final.startswith("\\\\?\\") or final.startswith("\\\\?\\UNC\\"):
            raise SafetyViolation("UNVERIFIED_FINAL_PATH")
        final = final[4:]
        # Exact spelling rejects case/short-name aliases; config root is canonical.
        if final.rstrip("\\") != str(expected_path).rstrip("\\"):
            raise SafetyViolation("FINAL_PATH_MISMATCH")
        return FileIdentity(int(identity.volume), bytes(identity.identifier).hex(), int(standard.size))

    def read(self, handle: int, cap: int) -> bytes:
        if not self.dll.SetFilePointerEx(handle, 0, None, 0):
            raise SafetyViolation("SAFE_READ_FAILED")
        buffer = ctypes.create_string_buffer(cap + 1)
        count = wintypes.DWORD()
        if not self.dll.ReadFile(handle, buffer, cap + 1, ctypes.byref(count), None):
            raise SafetyViolation("SAFE_READ_FAILED")
        if count.value > cap:
            raise SafetyViolation("SAFE_FILE_SIZE_LIMIT")
        return buffer.raw[:count.value]

def unsupported_code() -> str:
    return "UNSUPPORTED_SAFE_OPEN_WINDOWS" if os.name == "nt" else "UNSUPPORTED_SAFE_OPEN_LINUX"


def capabilities() -> dict[str, object]:
    """Never advertise general file mutation from a platform name alone."""
    return {"safe_open": False, "safe_write": False, "atomic_replace": False,
            "code": unsupported_code(), "windows_subset": "read_identity_requires_root_probe"}


class SafeFileAccess:
    """A root-pinned Windows subset; no returned writeable handle or Path.

    The legacy boolean is ignored. The constructor proves API availability and
    root identity using real handles; each operation reacquires ancestor locks.
    Keep this on a private staged root behind host lease/schema/journal gates.
    """

    def __init__(self, root: str | os.PathLike[str], *, safe_open_supported: bool = False) -> None:
        self._api = _WindowsApi()
        spelling = os.fspath(root)
        if type(spelling) is not str or not re.match(r"^[A-Za-z]:[\\/]", spelling) or spelling.startswith("\\\\"):
            raise SafetyViolation("INVALID_PROJECT_ROOT")
        self._resolver = SafePathResolver(root)
        self._root = self._resolver.root
        if os.path.normcase(str(self._root)) != os.path.normcase(os.path.abspath(spelling)):
            raise SafetyViolation("ROOT_PATH_CHANGED")
        self._root_identity: FileIdentity | None = None
        with self._parents(self._root) as records:
            self._root_identity = records[-1][2]

    def capabilities(self) -> dict[str, object]:
        return {"read_identity": True, "atomic_create_new": False,
                "safe_write": False, "atomic_replace": False,
                "mutation_code": unsupported_code(), "max_bytes": _MAX_BYTES}

    @contextmanager
    def _parents(self, parent: Path) -> Iterator[list[tuple[int, Path, FileIdentity]]]:
        records: list[tuple[int, Path, FileIdentity]] = []
        try:
            for directory in (*reversed(parent.parents), parent):
                handle = self._api.open(directory, directory=True)
                try:
                    identity = self._api.inspect(handle, directory, directory=True)
                except BaseException:
                    self._api.close(handle)
                    raise
                records.append((handle, directory, identity))
                if directory == self._root and self._root_identity is not None and not self._root_identity.same_file(identity):
                    raise SafetyViolation("ROOT_IDENTITY_CHANGED")
            yield records
            for handle, directory, identity in records:
                after = self._api.inspect(handle, directory, directory=True)
                if not identity.same_file(after):
                    raise SafetyViolation("DIRECTORY_IDENTITY_CHANGED")
        finally:
            for handle, _, _ in reversed(records):
                self._api.close(handle)

    def probe(self, relative: str) -> FileIdentity:
        destination = self._resolver.resolve(relative, require_existing=True)
        with self._parents(destination.parent):
            handle = self._api.open(destination)
            try:
                return self._api.inspect(handle, destination)
            finally:
                self._api.close(handle)

    def read_bytes(self, relative: str, *, max_bytes: int = _MAX_BYTES) -> bytes:
        if type(max_bytes) is not int or not 0 < max_bytes <= _MAX_BYTES:
            raise SafetyViolation("SAFE_FILE_SIZE_LIMIT")
        destination = self._resolver.resolve(relative, require_existing=True)
        with self._parents(destination.parent):
            handle = self._api.open(destination)
            try:
                before = self._api.inspect(handle, destination)
                if before.size > max_bytes:
                    raise SafetyViolation("SAFE_FILE_SIZE_LIMIT")
                data = self._api.read(handle, max_bytes)
                after = self._api.inspect(handle, destination)
                if before != after or len(data) != after.size:
                    raise SafetyViolation("FILE_IDENTITY_CHANGED")
                return data
            finally:
                self._api.close(handle)

    def create_new(self, relative: str, data: bytes) -> NoReturn:
        raise SafetyViolation(unsupported_code())

    def open_for_write(self, relative: str) -> NoReturn:
        raise SafetyViolation(unsupported_code())

    def write_bytes(self, relative: str, data: bytes) -> NoReturn:
        raise SafetyViolation(unsupported_code())

    def atomic_replace(self, relative: str, data: bytes, *, expected_identity: object = None) -> NoReturn:
        raise SafetyViolation(unsupported_code())
