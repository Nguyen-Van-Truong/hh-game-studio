"""Small durable command journal for the GT-02 safety baseline.

The journal is intentionally boring: newline-delimited, checksummed records,
durably flushed before a receipt is returned, and fail-closed on any malformed
or truncated record.  It is suitable for a local adapter fixture; it is not a
distributed database or a production multi-host lease service.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import errno
import stat
from functools import wraps
from pathlib import Path
import re
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Mapping
from collections.abc import Sequence

from .limits import DEFAULT_LIMITS, LimitsProfile, SafetyViolation, canonical_json, parse_json_utf8


class JournalError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        # Local provenance, never accepted from a request: a read/lock failure
        # cannot establish that this command was not already applied.
        self.outcome_unknown = False
        super().__init__(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class JournalLimits:
    max_bytes: int = DEFAULT_LIMITS.max_journal_bytes
    max_records: int = 100_000
    max_pending_commands: int = DEFAULT_LIMITS.max_pending_commands
    retry_horizon_ms: int = DEFAULT_LIMITS.max_retry_horizon_ms
    max_lease_ttl_ms: int = DEFAULT_LIMITS.max_lease_ttl_ms
    lock_timeout_ms: int = 2_000
    lock_stale_ms: int = 30_000

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"invalid journal limit: {name}")


@dataclass(frozen=True)
class Lease:
    project_id: str
    target: str
    owner: str
    fencing_epoch: int
    expires_ms: int


_HEX = re.compile(r"^[0-9a-f]{64}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_TERMINAL = frozenset({"COMMITTED", "REJECTED", "CANCELED", "UNKNOWN"})
_SAFE_INTEGER = (1 << 53) - 1


def _clock(value: int) -> None:
    if type(value) is not int or not 0 <= value <= _SAFE_INTEGER:
        raise JournalError("INVALID_CLOCK")


class _DiskRecords(Sequence):
    """Bounded offset index; receipt bodies remain on disk, not in the index."""
    def __init__(self, journal):
        self.journal = journal
        self.offsets: list[tuple[int, int]] = []

    def __len__(self):
        return len(self.offsets)

    def __getitem__(self, index):
        offset, size = self.offsets[index]
        try:
            with self.journal.path.open("rb") as stream:
                stream.seek(offset)
                raw = stream.read(size)
        except OSError as exc:
            raise JournalError("JOURNAL_UNREADABLE") from exc
        return self.journal._decode_record(raw)

    def clear(self):
        self.offsets.clear()


class Journal:
    """Checksummed durable journal with command dedupe and lease fencing."""

    def __init__(self, path: str | os.PathLike[str], *, limits: JournalLimits | None = None,
                 profile: LimitsProfile = DEFAULT_LIMITS) -> None:
        self.path = Path(path)
        self.limits = limits or JournalLimits()
        self.profile = profile
        self._records = _DiskRecords(self)
        self._commands: dict[tuple[str, str], int] = {}
        self._pending: set[tuple[str, str]] = set()
        self._leases: dict[tuple[str, str], Lease] = {}
        with self._writer_lock():
            self._load()

    def _check_private_namespace(self) -> None:
        """Journal paths are trusted host state, never agent-selected targets.

        Refuse existing aliases that split one inode across multiple guards.
        Adversarial writes by the same OS principal still require isolation;
        this check does not advertise a general project safe-write capability.
        """
        for path in (self.path, *self.path.absolute().parents):
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise JournalError("JOURNAL_PATH_UNSAFE")
            if path == self.path and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
                raise JournalError("JOURNAL_PATH_UNSAFE")

    @property
    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            # os.kill(pid, 0) TERMINATES a process on Windows. Observe a
            # synchronizable handle instead; access denied is not proof of death.
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
            if not handle:
                return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER
            try:
                return kernel.WaitForSingleObject(handle, 0) != 0  # signaled = exited
            finally:
                kernel.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return True  # Unknown/access denied must never steal a live lock.
        return True

    @contextmanager
    def _writer_lock(self):
        """OS lock protects metadata recovery and every read/write snapshot.

        The guard inode is permanent. Unlinking an advisory-lock file would
        allow another writer to lock a replacement inode at the same path.
        Kernel ownership is released automatically on process death.
        """
        guard = self.path.with_name(self.path.name + ".guard")
        self._check_private_namespace()
        guard.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        deadline = time.monotonic() + self.limits.lock_timeout_ms / 1000
        try:
            fd = os.open(guard, flags, 0o600)
        except OSError as exc:
            raise JournalError("JOURNAL_LOCK_FAILED") from exc
        held = False
        try:
            identity = os.fstat(fd)
            if (not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1
                    or getattr(identity, "st_file_attributes", 0) & 0x400):
                raise JournalError("JOURNAL_LOCK_UNSAFE")
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    held = True
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise JournalError("JOURNAL_LOCK_FAILED") from exc
                    if time.monotonic() >= deadline:
                        raise JournalError("JOURNAL_LOCKED") from exc
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            with self._metadata_lock(deadline):
                self._check_private_namespace()
                yield
        finally:
            if held:
                if os.name == "nt":
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @contextmanager
    def _metadata_lock(self, deadline: float):
        """Reconcile legacy metadata; new writers use only the kernel guard.

        Creating an auxiliary owner file introduces a crash window before its
        metadata is written. New writers never create that file: the kernel
        handle is the ownership evidence and vanishes automatically on death.
        A surviving legacy marker is retained unless its owner is proven dead.
        """
        lock = self._lock_path
        while lock.exists():
            if time.monotonic() >= deadline:
                raise JournalError("JOURNAL_LOCKED")
            try:
                with lock.open("rb") as stream:
                    raw = stream.read(1025)
                if len(raw) > 1024:
                    raise JournalError("JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED")
                data = json.loads(raw.decode("utf-8"))
                pid_raw = data.get("pid") if isinstance(data, dict) else None
                if not isinstance(pid_raw, str) or not pid_raw.isdecimal() or int(pid_raw) <= 0:
                    raise JournalError("JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED")
                if not self._pid_alive(int(pid_raw)):
                    # This legacy check runs inside the nonreplaceable guard;
                    # all current writers participate in that lock domain.
                    with lock.open("rb") as stream:
                        current = stream.read(1025)
                    if current != raw:
                        continue
                    lock.unlink()
                    break
            except FileNotFoundError:
                break
            except (ValueError, UnicodeError) as exc:
                raise JournalError("JOURNAL_LEGACY_LOCK_RECOVERY_REQUIRED") from exc
            except OSError as exc:
                raise JournalError("JOURNAL_LOCK_FAILED") from exc
            time.sleep(min(0.01, max(0, deadline - time.monotonic())))
        yield

    def _reload(self) -> None:
        self._records.clear()
        self._commands.clear()
        self._pending.clear()
        self._leases.clear()
        self._load()

    @staticmethod
    def _mutating(method):
        @wraps(method)
        def guarded(self, *args, **kwargs):
            entered = completed = False
            try:
                with self._writer_lock():
                    # Refresh after taking the lock so a second process cannot
                    # make a decision from stale in-memory dedupe/lease state.
                    self._reload()
                    entered = True
                    result = method(self, *args, **kwargs)
                    completed = True
                    return result
            except JournalError as exc:
                # The same FULL/LOCKED code can mean unavailable history or a
                # known pre-admission refusal. Preserve that phase distinction.
                # A guard-exit failure after the method is uncertain as well.
                if not entered or completed:
                    exc.outcome_unknown = True
                raise
        return guarded

    @staticmethod
    def _checksum(record: Mapping[str, Any]) -> str:
        return hashlib.sha256(canonical_json(dict(record))).hexdigest()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            # A terminal line can be visible in the page cache even when the
            # writer's fsync failed. Open with write access and synchronize the
            # complete journal before exposing any receipt to a new reader.
            # This is the recovery barrier for a fresh Journal instance too;
            # an in-memory poison flag would not protect reopen/lookup.
            with self.path.open("r+b") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise JournalError("JOURNAL_PATH_UNSAFE")
                if info.st_size > self.limits.max_bytes:
                    raise JournalError("JOURNAL_FULL")
                while True:
                    offset = stream.tell()
                    line = stream.readline(self.profile.max_envelope_bytes + 1)
                    if not line:
                        break
                    if len(line) > self.profile.max_envelope_bytes:
                        raise JournalError("JOURNAL_RECORD_INVALID")
                    if len(self._records) >= self.limits.max_records:
                        raise JournalError("JOURNAL_RECORD_LIMIT")
                    record = self._decode_record(line)
                    self._apply_loaded(record, len(self._records))
                    self._records.offsets.append((offset, len(line)))
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError as exc:
                    raise JournalError("JOURNAL_DURABILITY_UNCONFIRMED") from exc
        except OSError as exc:
            raise JournalError("JOURNAL_UNREADABLE") from exc

    def _decode_record(self, line: bytes) -> dict[str, Any]:
        if not line.endswith(b"\n"):
            raise JournalError("JOURNAL_TRUNCATED")
        try:
            envelope = parse_json_utf8(line, limits=self.profile)
            if not isinstance(envelope, dict) or set(envelope) != {"record", "checksum"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            record, checksum = envelope["record"], envelope["checksum"]
            if not isinstance(record, dict) or not isinstance(checksum, str) or checksum != self._checksum(record):
                raise JournalError("JOURNAL_CHECKSUM_MISMATCH")
            return record
        except (SafetyViolation, json.JSONDecodeError, UnicodeError) as exc:
            raise JournalError("JOURNAL_RECORD_INVALID") from exc

    def _command(self, key) -> dict[str, Any] | None:
        index = self._commands.get(key)
        return None if index is None else self._records[index]

    def _validate_record(self, record: dict[str, Any]) -> None:
        kind = record.get("kind")
        if kind == "command":
            required = {"kind", "project_id", "command_id", "digest", "status", "receipt", "created_ms", "expires_ms"}
            if "archive_status" in record:
                required.add("archive_status")
                if (record.get("status") != "EXPIRED_TOMBSTONE"
                        or not isinstance(record["archive_status"], str)
                        or record["archive_status"] not in _TERMINAL | {"ACCEPTED_PENDING"}):
                    raise JournalError("JOURNAL_RECORD_INVALID")
            if set(record) != required:
                raise JournalError("JOURNAL_RECORD_INVALID")
            key = (record.get("project_id"), record.get("command_id"))
            if not all(isinstance(item, str) and item for item in key):
                raise JournalError("JOURNAL_RECORD_INVALID")
            if not isinstance(record.get("digest"), str) or not _DIGEST.fullmatch(record["digest"]):
                raise JournalError("JOURNAL_RECORD_INVALID")
            if not isinstance(record.get("status"), str) or record["status"] not in _TERMINAL | {"ACCEPTED_PENDING", "EXPIRED_TOMBSTONE"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            if (not isinstance(record.get("receipt"), dict) or type(record.get("expires_ms")) is not int
                    or type(record.get("created_ms")) is not int
                    or not 0 <= record["created_ms"] <= record["expires_ms"] <= _SAFE_INTEGER):
                raise JournalError("JOURNAL_RECORD_INVALID")
            previous = self._command(key)
            if previous is not None:
                if any(record[field] != previous[field] for field in ("digest", "created_ms", "expires_ms")):
                    raise JournalError("JOURNAL_HISTORY_INVALID")
                if previous["status"] != "ACCEPTED_PENDING" or record["status"] not in _TERMINAL:
                    raise JournalError("JOURNAL_HISTORY_INVALID")
        elif kind == "lease":
            if set(record) != {"kind", "project_id", "target", "owner", "fencing_epoch", "expires_ms"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            key = (record.get("project_id"), record.get("target"))
            lease = Lease(key[0], key[1], record.get("owner"), record.get("fencing_epoch"), record.get("expires_ms"))
            if (not all(isinstance(item, str) and item for item in key + (lease.owner,))
                    or type(lease.fencing_epoch) is not int or not 1 <= lease.fencing_epoch <= _SAFE_INTEGER
                    or type(lease.expires_ms) is not int or not 0 <= lease.expires_ms <= _SAFE_INTEGER):
                raise JournalError("JOURNAL_RECORD_INVALID")
            previous = self._leases.get(key)
            if previous is not None and lease.fencing_epoch <= previous.fencing_epoch:
                raise JournalError("JOURNAL_HISTORY_INVALID")
        else:
            raise JournalError("JOURNAL_RECORD_INVALID")

    def _apply_loaded(self, record: dict[str, Any], index: int) -> None:
        self._validate_record(record)
        if record["kind"] == "command":
            key = (record["project_id"], record["command_id"])
            self._commands[key] = index
            if record["status"] == "ACCEPTED_PENDING":
                self._pending.add(key)
            else:
                self._pending.discard(key)
        else:
            self._leases[(record["project_id"], record["target"])] = Lease(
                record["project_id"], record["target"], record["owner"], record["fencing_epoch"], record["expires_ms"])

    def _append(self, record: dict[str, Any]) -> None:
        self._validate_record(record)
        pending_after = len(self._pending)
        if record["kind"] == "command":
            key = (record["project_id"], record["command_id"])
            pending_after += int(record["status"] == "ACCEPTED_PENDING") - int(key in self._pending)
        # Each durable intent owns one future terminal row and the maximum
        # encoded record size. Other commands/leases cannot consume its budget.
        # This reserves configured capacity, not immunity to physical I/O faults.
        if len(self._records) + 1 + pending_after > self.limits.max_records:
            raise JournalError("JOURNAL_RECORD_LIMIT")
        line = self._encoded_record(record)
        existing = self.path.stat().st_size if self.path.exists() else 0
        if existing + len(line) + pending_after * self.profile.max_envelope_bytes > self.limits.max_bytes:
            raise JournalError("JOURNAL_FULL")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("ab") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise JournalError("JOURNAL_WRITE_FAILED") from exc
        self._apply_loaded(record, len(self._records))
        self._records.offsets.append((existing, len(line)))

    def _encoded_record(self, record: dict[str, Any]) -> bytes:
        """Validate exact durable bytes with the same profile used on reopen."""
        try:
            line = canonical_json({"record": record, "checksum": self._checksum(record)}, limits=self.profile) + b"\n"
            if len(line) > self.profile.max_envelope_bytes:
                raise JournalError("JOURNAL_RECORD_INVALID")
            self._decode_record(line)
            return line
        except SafetyViolation as exc:
            raise JournalError("JOURNAL_RECORD_INVALID") from exc

    @_mutating
    def append_command(self, *, project_id: str, command_id: str, digest: str,
                       receipt: Mapping[str, Any], now_ms: int, pending: bool = False) -> dict[str, Any]:
        _clock(now_ms)
        if type(pending) is not bool:
            raise JournalError("INVALID_PENDING")
        if not all(isinstance(value, str) and value for value in (project_id, command_id)):
            raise JournalError("INVALID_COMMAND_ID")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise JournalError("INVALID_DIGEST")
        key = (project_id, command_id)
        existing = self._command(key)
        if existing is not None:
            if existing["digest"] != digest:
                raise JournalError("COMMAND_ID_PAYLOAD_CONFLICT")
            if existing["status"] == "EXPIRED_TOMBSTONE" or now_ms > existing["expires_ms"]:
                raise JournalError("RETRY_HORIZON_EXPIRED")
            return {"receipt": existing["receipt"], "replayed": True, "status": existing["status"]}
        if not isinstance(receipt, Mapping):
            raise JournalError("INVALID_RECEIPT")
        if pending and len(self._pending) >= self.limits.max_pending_commands:
            raise JournalError("PENDING_LIMIT")
        expires = now_ms + self.limits.retry_horizon_ms
        record = {"kind": "command", "project_id": project_id, "command_id": command_id,
                  "digest": digest, "status": "ACCEPTED_PENDING" if pending else "COMMITTED",
                  "receipt": dict(receipt), "created_ms": now_ms, "expires_ms": expires}
        self._append(record)
        return {"receipt": dict(receipt), "replayed": False, "status": record["status"]}

    @_mutating
    def finish_command(self, *, project_id: str, command_id: str, status: str,
                       receipt: Mapping[str, Any], now_ms: int) -> dict[str, Any]:
        _clock(now_ms)
        if not isinstance(receipt, Mapping):
            raise JournalError("INVALID_RECEIPT")
        if not isinstance(status, str) or status not in _TERMINAL:
            raise JournalError("INVALID_STATUS")
        key = (project_id, command_id)
        existing = self._command(key)
        if existing is None:
            raise JournalError("COMMAND_NOT_FOUND")
        if existing["status"] == "EXPIRED_TOMBSTONE" or now_ms > existing["expires_ms"]:
            raise JournalError("RETRY_HORIZON_EXPIRED")
        if existing["status"] != "ACCEPTED_PENDING":
            if dict(receipt) == existing["receipt"] and status == existing["status"]:
                return {"receipt": existing["receipt"], "replayed": True, "status": existing["status"]}
            raise JournalError("COMMAND_ALREADY_TERMINAL")
        record = dict(existing)
        if status not in _TERMINAL:
            raise JournalError("INVALID_STATUS")
        if not isinstance(receipt, Mapping):
            raise JournalError("INVALID_RECEIPT")
        record.update(status=status, receipt=dict(receipt))
        self._append(record)
        return {"receipt": dict(receipt), "replayed": False, "status": status}

    @_mutating
    def lookup(self, *, project_id: str, command_id: str, now_ms: int) -> dict[str, Any]:
        _clock(now_ms)
        existing = self._command((project_id, command_id))
        if existing is None:
            raise JournalError("COMMAND_NOT_FOUND")
        if existing["status"] == "EXPIRED_TOMBSTONE" or now_ms > existing["expires_ms"]:
            raise JournalError("RETRY_HORIZON_EXPIRED")
        return {"receipt": existing["receipt"], "status": existing["status"], "replayed": True}

    @_mutating
    def lookup_archive(self, *, project_id: str, command_id: str, now_ms: int) -> dict[str, Any]:
        """Read an expired result without renewing its ID or permitting retry.

        Archive bodies share the bounded disk journal and offset index. A
        compacted tombstone retains its original status and receipt. Legacy
        tombstones whose bodies were already discarded cannot invent a result.
        """
        _clock(now_ms)
        existing = self._command((project_id, command_id))
        if existing is None:
            raise JournalError("COMMAND_NOT_FOUND")
        if existing["status"] == "EXPIRED_TOMBSTONE":
            if "archive_status" not in existing:
                raise JournalError("ARCHIVE_RESULT_UNAVAILABLE")
            original_status = existing["archive_status"]
        else:
            if now_ms <= existing["expires_ms"]:
                raise JournalError("ARCHIVE_NOT_EXPIRED")
            original_status = existing["status"]
        return {"receipt": existing["receipt"], "status": original_status,
                "digest": existing["digest"], "created_ms": existing["created_ms"],
                "expires_ms": existing["expires_ms"], "archived": True,
                "execution_permitted": False}

    @_mutating
    def acquire_lease(self, *, project_id: str, target: str, owner: str,
                      now_ms: int, ttl_ms: int) -> Lease:
        _clock(now_ms)
        if not all(isinstance(value, str) and value for value in (project_id, target, owner)):
            raise JournalError("INVALID_LEASE")
        if not isinstance(ttl_ms, int) or isinstance(ttl_ms, bool) or ttl_ms <= 0 or ttl_ms > self.limits.max_lease_ttl_ms:
            raise JournalError("LEASE_TTL_OUT_OF_RANGE")
        key = (project_id, target)
        old = self._leases.get(key)
        if old and old.expires_ms > now_ms and old.owner != owner:
            raise JournalError("LEASE_BUSY")
        epoch = old.fencing_epoch + 1 if old else 1
        lease = Lease(project_id, target, owner, epoch, now_ms + ttl_ms)
        self._append({"kind": "lease", "project_id": project_id, "target": target,
                      "owner": owner, "fencing_epoch": epoch, "expires_ms": lease.expires_ms})
        return lease

    @_mutating
    def check_lease(self, lease: Lease, *, now_ms: int) -> None:
        _clock(now_ms)
        current = self._leases.get((lease.project_id, lease.target))
        if current != lease or lease.expires_ms <= now_ms:
            raise JournalError("STALE_LEASE")

    @contextmanager
    def lease_guard(self, lease: Lease, *, now_ms: int):
        """Keep fencing validation and a bounded local effect in one lock.

        Callers must check the real deadline immediately before their effect.
        Do not call another journal method, perform I/O or wait for readback
        while holding this non-reentrant guard. Terminal persistence follows
        after releasing it. Other cooperating lease writers cannot interleave.
        """
        _clock(now_ms)
        with self._writer_lock():
            self._reload()
            if self._leases.get((lease.project_id, lease.target)) != lease or lease.expires_ms <= now_ms:
                raise JournalError("STALE_LEASE")
            yield

    @staticmethod
    def check_revision(*, expected_revision: str, current_revision: str) -> None:
        if not isinstance(expected_revision, str) or not isinstance(current_revision, str) or expected_revision != current_revision:
            raise JournalError("REVISION_MISMATCH")

    @_mutating
    def compact(self, *, now_ms: int) -> None:
        """Atomically rewrite retained tombstones/leases after a checkpoint."""
        _clock(now_ms)
        # Keep an immutable tombstone for every expired ID.  Dropping it would
        # permit a retry after the horizon to be interpreted as a new command.
        def retained_records():
            for index in self._commands.values():
                record = self._records[index]
                if record["expires_ms"] < now_ms and record["status"] != "EXPIRED_TOMBSTONE":
                    record.update(archive_status=record["status"], status="EXPIRED_TOMBSTONE")
                yield record
            for lease in self._leases.values():
                yield {"kind": "lease", "project_id": lease.project_id, "target": lease.target,
                       "owner": lease.owner, "fencing_epoch": lease.fencing_epoch, "expires_ms": lease.expires_ms}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                size = 0
                pending_count = 0
                count = 0
                for record in retained_records():
                    encoded = self._encoded_record(record)
                    size += len(encoded)
                    if size > self.limits.max_bytes:
                        raise JournalError("JOURNAL_FULL")
                    count += 1
                    pending_count += int(record.get("status") == "ACCEPTED_PENDING")
                    stream.write(encoded)
                if size + pending_count * self.profile.max_envelope_bytes > self.limits.max_bytes:
                    raise JournalError("JOURNAL_FULL")
                if count + pending_count > self.limits.max_records:
                    raise JournalError("JOURNAL_RECORD_LIMIT")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self._reload()
        except (OSError, JournalError) as exc:
            try:
                os.unlink(name)
            except OSError:
                pass
            if isinstance(exc, JournalError):
                raise
            raise JournalError("JOURNAL_COMPACT_FAILED") from exc
