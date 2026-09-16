"""Experimental atomic replacement inside a broker-owned NTFS namespace.

This is a local primitive, not a transport command or COMMITTED receipt. Fresh
protected roots can mutate. Reopen is read-only until a higher-level durable
transaction verifies the committed snapshot and rearms it. Public generic
safe_open stays disabled.

The expected target CAS relies on ONE broker writer and OS-confined workers:
the owner-only DACL excludes AppContainer workers, the guard excludes another
cooperating broker, and a mutex serializes this instance. Unrestricted owner
processes/administrators have broker authority. Rename flags alone are NOT a
conditional replace primitive for a directory writable by an adversary.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import threading
import uuid

from .limits import SafePathResolver, SafetyViolation
from .private_store import _StoreApi, _SecurityAttributes, _READ_CONTROL
from .safe_create import MAX_BYTES, SafeCreateApi
from .safe_open import FileIdentity


MAX_FILES = 64
MAX_TOTAL_BYTES = 8 * 1024 * 1024
_ROOT = re.compile(r"hh-files-[0-9a-f]{32}\Z")


class SafeReplaceError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner: ProtectedFileRoot | None = None
        super().__init__(code)


@dataclass(frozen=True)
class FileVersion:
    identity: FileIdentity
    sha256: str


class _ReplaceApi(_StoreApi):
    def __init__(self) -> None:
        super().__init__()
        self.dll.SetFileInformationByHandle.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
        self.dll.SetFileInformationByHandle.restype = W.BOOL

    def open_file(self, path: Path, *, create: bool = False, target: bool = False,
                  directory: bool = False, flush: bool = False, publish: bool = False) -> int:
        access = (0x81 if directory else 0x80000000) | _READ_CONTROL
        if create:
            access |= 0x40010000  # write + DELETE for pending/rename
        if flush:
            access |= 0x40000000
        share = (3 if publish else 1) if directory else (5 if target else 0)
        flags = 0x00200000 | (0x02000000 if directory else 0) | (0x80000000 if create else 0)
        with self.descriptor() as descriptor:
            attributes = _SecurityAttributes(C.sizeof(_SecurityAttributes), descriptor, False)
            handle = self.dll.CreateFileW("\\\\?\\" + str(path), access, share,
                                          C.byref(attributes), 1 if create else 3, flags, None)
        if handle == C.c_void_p(-1).value:
            error = C.get_last_error()
            code = "DESTINATION_EXISTS" if error in (80, 183) else (
                "PATH_NOT_FOUND" if error in (2, 3) else "SAFE_REPLACE_OPEN_DENIED")
            raise SafeReplaceError(code)
        self._owned_handles.add(handle)
        return handle

    pending = SafeCreateApi.pending
    write_flush = SafeCreateApi.write_flush
    rename = SafeCreateApi.rename

    def flush_directory(self, path: Path, identity: FileIdentity, *, private: bool = True) -> None:
        handle = self.open_file(path, directory=True, flush=True, publish=True)
        try:
            if not identity.same_file(self.inspect(handle, path, directory=True)):
                raise SafeReplaceError("DIRECTORY_IDENTITY_CHANGED")
            if private:
                self.check_security(handle)
            self.flush(handle)
        finally:
            self.close(handle)


class ProtectedFileRoot:
    """One broker owns all names; clients receive bytes/version values only."""

    @classmethod
    def create(cls, parent: str | os.PathLike[str]) -> ProtectedFileRoot:
        return cls(parent, expected_root=None)

    @classmethod
    def reopen_readonly(cls, root: str | os.PathLike[str], expected_root: FileIdentity) -> ProtectedFileRoot:
        if type(expected_root) is not FileIdentity:
            raise SafeReplaceError("SAFE_ROOT_IDENTITY_REQUIRED")
        return cls(root, expected_root=expected_root)

    def __init__(self, path: str | os.PathLike[str], *, expected_root: FileIdentity | None) -> None:
        self._mutex = threading.Lock()
        self._closed = self._poisoned = False
        self._readonly = expected_root is not None
        self._api = _ReplaceApi()
        self._parents: list[tuple[int, Path, FileIdentity]] = []
        started = False
        try:
            spelling = os.fspath(path)
            if type(spelling) is not str or not re.match(r"^[A-Za-z]:[\\/]", spelling) or spelling.startswith("\\\\"):
                raise SafeReplaceError("INVALID_PROJECT_ROOT")
            canonical = SafePathResolver(path).root
            if os.path.normcase(str(canonical)) != os.path.normcase(os.path.abspath(spelling)):
                raise SafeReplaceError("ROOT_PATH_CHANGED")
            parent = canonical if expected_root is None else canonical.parent
            directories = (*reversed(parent.parents), parent)
            for index, directory in enumerate(directories):
                handle = self._api.open_file(directory, directory=True, publish=index == len(directories) - 1)
                self._parents.append((handle, directory, self._api.inspect(handle, directory, directory=True)))
            self._api.ntfs(self._parents[-1][0])
            self.root = parent / ("hh-files-" + uuid.uuid4().hex) if expected_root is None else canonical
            if expected_root is None:
                started = True  # CreateDirectoryW failure is not permission to retry blindly.
                self._api.mkdir(self.root)
            elif not _ROOT.fullmatch(self.root.name):
                raise SafeReplaceError("SAFE_ROOT_IDENTITY_CHANGED")
            self._root_handle = self._api.open_file(self.root, directory=True, publish=True)
            self.root_identity = self._api.inspect(self._root_handle, self.root, directory=True)
            self._api.check_security(self._root_handle)
            self._api.ntfs(self._root_handle)
            if expected_root is not None and not expected_root.same_file(self.root_identity):
                raise SafeReplaceError("SAFE_ROOT_IDENTITY_CHANGED")
            self._resolver = SafePathResolver(self.root)
            self._guard = self._api.open_file(self.root / ".writer", create=expected_root is None)
            self._guard_identity = self._api.inspect(self._guard, self.root / ".writer")
            self._api.check_security(self._guard)
            if self._guard_identity.size != 0 or self._guard_identity.volume != self.root_identity.volume:
                raise SafeReplaceError("SAFE_GUARD_INVALID")
            if expected_root is None:
                self._api.flush(self._guard)
                self._api.flush_directory(self.root, self.root_identity)
                self._api.flush_directory(parent, self._parents[-1][2], private=False)
        except BaseException as exc:
            self._poisoned = started
            try:
                self.close()
            except SafetyViolation:
                error = SafeReplaceError("SAFE_REPLACE_INIT_CLEANUP_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            if started and isinstance(exc, (SafetyViolation, OSError)):
                error = SafeReplaceError("SAFE_REPLACE_INIT_UNCERTAIN", outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            raise

    def __enter__(self) -> ProtectedFileRoot:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._mutex:
            self._closed = True
            self._api.close_owned()

    def check_mutation_available(self) -> None:
        """Read-only admission preflight; never clears a hold or reserves a write.

        The actual operation still rechecks under this mutex. Callers must not
        treat a successful preflight as permission to bypass later checks.
        """
        with self._mutex:
            self._check(mutation=True)

    def _rearm_verified_snapshot(self, expected: FileVersion) -> None:
        """Private supervisor step after terminal/custody/fence verification.

        Only the fixed file consumer can use a reopened root. A caller cannot
        turn an arbitrary root/version list into recovered write authority.
        This does not replay a command or repair an incomplete namespace.
        """
        with self._mutex:
            self._check()
            if (not self._readonly or type(expected) is not FileVersion
                    or getattr(self, '_fixture_file_consumer', None) is None):
                raise SafeReplaceError('SAFE_REARM_REQUIRES_VERIFIED_CONSUMER')
            if {entry.name for entry in self.root.iterdir()} != {'.writer', 'active.json'}:
                raise SafeReplaceError('SAFE_REARM_NAMESPACE_UNCERTAIN', outcome_unknown=True)
            path = self._path('active.json')
            handle = self._api.open_file(path, flush=True)
            try:
                if self._version(handle, path)[0] != expected:
                    raise SafeReplaceError('SAFE_TARGET_CONFLICT')
                self._api.flush(handle)
                self._api.flush_directory(self.root, self.root_identity)
                if self._version(handle, path)[0] != expected:
                    raise SafeReplaceError('SAFE_TARGET_CONFLICT')
                self._check()
            except BaseException:
                self._poisoned = True
                raise SafeReplaceError('SAFE_REARM_BARRIER_UNCERTAIN', outcome_unknown=True) from None
            finally:
                self._close_operation(handle)
            self._readonly = False

    def _check(self, *, mutation: bool = False) -> None:
        if self._closed or self._poisoned:
            raise SafeReplaceError("SAFE_REPLACE_RECONCILIATION_REQUIRED", outcome_unknown=self._poisoned)
        if mutation and self._readonly:
            raise SafeReplaceError("SAFE_REOPEN_REQUIRES_RECONCILIATION")
        self._api.check_no_impersonation()
        for handle, path, identity in (*self._parents, (self._root_handle, self.root, self.root_identity)):
            if not identity.same_file(self._api.inspect(handle, path, directory=True)):
                raise SafeReplaceError("DIRECTORY_IDENTITY_CHANGED")
        self._api.check_security(self._root_handle)
        if self._api.inspect(self._guard, self.root / ".writer") != self._guard_identity:
            raise SafeReplaceError("SAFE_GUARD_INVALID")
        self._api.check_security(self._guard)

    def _path(self, name: str) -> Path:
        # A finite single-directory prototype. Subdirectory creation is not
        # delegated to clients and cannot smuggle inherited permissive ACLs.
        if type(name) is not str or name.startswith(".") or "/" in name or "\\" in name:
            raise SafeReplaceError("SAFE_FILE_NAME_INVALID")
        path = self._resolver.resolve(name, require_existing=False)
        if path.parent != self.root:
            raise SafeReplaceError("SAFE_FILE_NAME_INVALID")
        return path

    def _version(self, handle: int, path: Path) -> tuple[FileVersion, bytes]:
        before = self._api.inspect(handle, path)
        self._api.check_security(handle)
        if before.volume != self.root_identity.volume or before.size > MAX_BYTES:
            raise SafeReplaceError("SAFE_FILE_SIZE_LIMIT")
        data = self._api.read(handle, MAX_BYTES)
        after = self._api.inspect(handle, path)
        self._api.check_security(handle)
        if before != after or len(data) != after.size:
            raise SafeReplaceError("FILE_IDENTITY_CHANGED")
        return FileVersion(after, hashlib.sha256(data).hexdigest()), data

    def read(self, name: str) -> tuple[FileVersion, bytes]:
        with self._mutex:
            self._check()
            path = self._path(name)
            handle = self._api.open_file(path)
            try:
                result = self._version(handle, path)
                self._check()
                return result
            finally:
                self._close_operation(handle)

    def confirm_barrier(self, name: str, expected: FileVersion) -> None:
        """Reconcile a known complete value without rewriting or enabling replay.

        A reopened read-only instance can flush a value validated against the
        durable selector. Cache readback by itself is not a durability barrier.
        This call does not clear the read-only hold or acknowledge a command.
        """
        with self._mutex:
            self._check()
            path = self._path(name)
            handle = self._api.open_file(path, flush=True)
            try:
                if self._version(handle, path)[0] != expected:
                    raise SafeReplaceError("SAFE_TARGET_CONFLICT")
                self._api.flush(handle)
                self._api.flush_directory(self.root, self.root_identity)
                if self._version(handle, path)[0] != expected:
                    raise SafeReplaceError("SAFE_TARGET_CONFLICT")
                self._check()
            except BaseException:
                self._poisoned = True
                raise SafeReplaceError("SAFE_REPLACE_BARRIER_UNCERTAIN", outcome_unknown=True) from None
            finally:
                self._close_operation(handle)

    def _close_operation(self, handle: int) -> None:
        try:
            self._api.close(handle)
        except SafetyViolation:
            self._poisoned = True
            raise SafeReplaceError("SAFE_REPLACE_CLOSE_UNCERTAIN", outcome_unknown=True) from None

    def _quota(self, requested: int) -> None:
        count, size = 0, 0
        with os.scandir(self.root) as entries:
            for entry in entries:
                if entry.name == ".writer":
                    continue
                count += 1
                if count >= MAX_FILES:
                    raise SafeReplaceError("SAFE_ROOT_QUOTA")
                path = self._path(entry.name)
                handle = self._api.open_file(path)
                try:
                    version, _ = self._version(handle, path)
                    size += version.identity.size
                finally:
                    self._close_operation(handle)
                if size + requested > MAX_TOTAL_BYTES:
                    raise SafeReplaceError("SAFE_ROOT_QUOTA")

    def create_new(self, name: str, data: bytes) -> FileVersion:
        return self._put(name, data, None)

    def atomic_replace(self, name: str, data: bytes, *, expected: FileVersion) -> FileVersion:
        if (type(expected) is not FileVersion or type(expected.identity) is not FileIdentity
                or type(expected.sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected.sha256)):
            raise SafeReplaceError("SAFE_EXPECTED_VERSION_REQUIRED")
        return self._put(name, data, expected)

    def _put(self, name: str, data: bytes, expected: FileVersion | None) -> FileVersion:
        if type(data) is not bytes or len(data) > MAX_BYTES:
            raise SafeReplaceError("SAFE_FILE_SIZE_LIMIT")
        with self._mutex:
            started = False
            old = stage = None
            published = False
            try:
                self._check(mutation=True)
                destination = self._path(name)
                self._quota(len(data))
                if expected is None:
                    if destination.exists():
                        raise SafeReplaceError("DESTINATION_EXISTS")
                else:
                    old = self._api.open_file(destination, target=True)
                    if self._version(old, destination)[0] != expected:
                        raise SafeReplaceError("SAFE_TARGET_CONFLICT")
                self._api.flush_directory(self.root, self.root_identity)
                stage_path = self.root / (".hh-stage-" + uuid.uuid4().hex)
                stage = self._api.open_file(stage_path, create=True)
                started = True
                before = self._api.inspect(stage, stage_path)
                self._api.check_security(stage)
                self._api.pending(stage, True)
                self._api.write_flush(stage, data)
                if self._api.read(stage, MAX_BYTES) != data:
                    raise SafeReplaceError("SAFE_READBACK_FAILED")
                self._api.pending(stage, False)
                staged, actual = self._version(stage, stage_path)
                if not before.same_file(staged.identity) or actual != data:
                    raise SafeReplaceError("SAFE_READBACK_FAILED")
                self._check(mutation=True)
                if old is not None and self._version(old, destination)[0] != expected:
                    raise SafeReplaceError("SAFE_TARGET_CONFLICT")
                self._api.rename(stage, destination, replace=old is not None)
                published = True
                result, actual = self._version(stage, destination)
                if result != staged or actual != data:
                    raise SafeReplaceError("SAFE_READBACK_FAILED")
                # Old target is retained with read/delete sharing, no write.
                # POSIX rename unlinks its old name without modifying its bytes.
                if old is not None and hashlib.sha256(self._api.read(old, MAX_BYTES)).hexdigest() != expected.sha256:
                    raise SafeReplaceError("SAFE_OLD_VERSION_CHANGED")
                self._api.flush_directory(self.root, self.root_identity)
                self._check(mutation=True)
                return result
            except BaseException:
                if started:
                    self._poisoned = True
                    raise SafeReplaceError("SAFE_REPLACE_UNCERTAIN", outcome_unknown=True) from None
                raise
            finally:
                # Close every owned operation handle even if one close fails.
                # Failed closes remain registered for explicit close() retry.
                failed = False
                if stage is not None and not published:
                    try:
                        self._api.pending(stage, True)
                    except SafetyViolation:
                        pass
                for handle in (stage, old):
                    if handle is not None:
                        try:
                            self._close_operation(handle)
                        except SafeReplaceError:
                            failed = True
                if failed:
                    raise SafeReplaceError("SAFE_REPLACE_CLOSE_UNCERTAIN", outcome_unknown=True)
