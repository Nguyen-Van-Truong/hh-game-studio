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
from functools import wraps
from pathlib import Path
import re
import tempfile
import time
from contextlib import contextmanager
from typing import Any, Mapping

from .limits import DEFAULT_LIMITS, LimitsProfile, SafetyViolation, canonical_json, parse_json_utf8


class JournalError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
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


class Journal:
    """Checksummed durable journal with command dedupe and lease fencing."""

    def __init__(self, path: str | os.PathLike[str], *, limits: JournalLimits | None = None,
                 profile: LimitsProfile = DEFAULT_LIMITS) -> None:
        self.path = Path(path)
        self.limits = limits or JournalLimits()
        self.profile = profile
        self._records: list[dict[str, Any]] = []
        self._commands: dict[tuple[str, str], dict[str, Any]] = {}
        self._leases: dict[tuple[str, str], Lease] = {}
        self._load()

    @property
    def _lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return False
        return True

    @contextmanager
    def _writer_lock(self):
        """Acquire an atomic local writer lock, recovering dead owners.

        O_EXCL is available on Windows and POSIX and is deliberately used
        instead of advisory byte-range locks: a lock file survives a crashed
        writer and can therefore be inspected/recovered deterministically.
        """
        lock = self._lock_path
        lock.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.limits.lock_timeout_ms / 1000
        # Canonical protocol JSON encodes integers as decimal strings to avoid
        # cross-language precision loss (including the lock metadata).
        token = {"pid": str(os.getpid()), "created_ns": str(time.time_ns())}
        encoded = canonical_json(token) + b"\n"
        acquired = False
        while not acquired:
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    os.write(fd, encoded)
                    os.fsync(fd)
                finally:
                    os.close(fd)
                acquired = True
                break
            except FileExistsError:
                stale = False
                try:
                    stat = lock.stat()
                    age_ms = max(0, (time.time_ns() - stat.st_mtime_ns) // 1_000_000)
                    data = json.loads(lock.read_text(encoding="utf-8"))
                    pid_raw = data.get("pid") if isinstance(data, dict) else None
                    pid = int(pid_raw) if isinstance(pid_raw, str) and pid_raw.isdecimal() else -1
                    stale = (pid <= 0 or not self._pid_alive(pid)) or age_ms > self.limits.lock_stale_ms
                except (OSError, ValueError, TypeError, UnicodeError):
                    # A malformed lock is recoverable only after the stale
                    # grace period, avoiding deletion during a concurrent write.
                    try:
                        stale = (time.time_ns() - lock.stat().st_mtime_ns) // 1_000_000 > self.limits.lock_stale_ms
                    except OSError:
                        continue
                if stale:
                    try:
                        lock.unlink()
                    except FileNotFoundError:
                        continue
                    except OSError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise JournalError("JOURNAL_LOCKED")
                time.sleep(0.01)
            except OSError as exc:
                raise JournalError("JOURNAL_LOCK_FAILED", str(exc)) from exc
        try:
            yield
        finally:
            try:
                # Never remove a replacement lock if cleanup races with a
                # stale-owner recovery.  Compare the owner token first.
                current = json.loads(lock.read_text(encoding="utf-8"))
                if current == token:
                    lock.unlink()
            except (OSError, ValueError, TypeError, UnicodeError):
                pass

    def _reload(self) -> None:
        self._records.clear()
        self._commands.clear()
        self._leases.clear()
        self._load()

    @staticmethod
    def _mutating(method):
        @wraps(method)
        def guarded(self, *args, **kwargs):
            with self._writer_lock():
                # Refresh after taking the lock so a second process cannot
                # make a decision from stale in-memory dedupe/lease state.
                self._reload()
                return method(self, *args, **kwargs)
        return guarded

    @staticmethod
    def _checksum(record: Mapping[str, Any]) -> str:
        return hashlib.sha256(canonical_json(dict(record))).hexdigest()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise JournalError("JOURNAL_UNREADABLE", str(exc)) from exc
        if len(raw) > self.limits.max_bytes:
            raise JournalError("JOURNAL_FULL")
        if not raw:
            return
        if not raw.endswith(b"\n"):
            raise JournalError("JOURNAL_TRUNCATED")
        for line_no, line in enumerate(raw.splitlines(), 1):
            try:
                envelope = parse_json_utf8(line, limits=self.profile)
                if not isinstance(envelope, dict) or set(envelope) != {"record", "checksum"}:
                    raise JournalError("JOURNAL_RECORD_INVALID", str(line_no))
                record, checksum = envelope["record"], envelope["checksum"]
                if not isinstance(record, dict) or not isinstance(checksum, str) or checksum != self._checksum(record):
                    raise JournalError("JOURNAL_CHECKSUM_MISMATCH", str(line_no))
                self._apply_loaded(record)
                self._records.append(record)
            except (SafetyViolation, json.JSONDecodeError, UnicodeError) as exc:
                raise JournalError("JOURNAL_RECORD_INVALID", str(line_no)) from exc
        if len(self._records) > self.limits.max_records:
            raise JournalError("JOURNAL_RECORD_LIMIT")

    def _apply_loaded(self, record: dict[str, Any]) -> None:
        kind = record.get("kind")
        if kind == "command":
            if set(record) != {"kind", "project_id", "command_id", "digest", "status", "receipt", "created_ms", "expires_ms"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            key = (record.get("project_id"), record.get("command_id"))
            if not all(isinstance(item, str) and item for item in key):
                raise JournalError("JOURNAL_RECORD_INVALID")
            if not isinstance(record.get("digest"), str) or not _DIGEST.fullmatch(record["digest"]):
                raise JournalError("JOURNAL_RECORD_INVALID")
            if record.get("status") not in _TERMINAL | {"ACCEPTED_PENDING", "EXPIRED_TOMBSTONE"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            if (not isinstance(record.get("receipt"), dict) or not isinstance(record.get("expires_ms"), int)
                    or not isinstance(record.get("created_ms"), int)):
                raise JournalError("JOURNAL_RECORD_INVALID")
            self._commands[key] = record
        elif kind == "lease":
            if set(record) != {"kind", "project_id", "target", "owner", "fencing_epoch", "expires_ms"}:
                raise JournalError("JOURNAL_RECORD_INVALID")
            key = (record.get("project_id"), record.get("target"))
            lease = Lease(key[0], key[1], record.get("owner"), record.get("fencing_epoch"), record.get("expires_ms"))
            if not all(isinstance(item, str) and item for item in key + (lease.owner,)) or lease.fencing_epoch < 1 or lease.expires_ms < 0:
                raise JournalError("JOURNAL_RECORD_INVALID")
            self._leases[key] = lease
        elif kind == "revision":
            return
        else:
            raise JournalError("JOURNAL_RECORD_INVALID", str(kind))

    def _append(self, record: dict[str, Any]) -> None:
        if len(self._records) >= self.limits.max_records:
            raise JournalError("JOURNAL_RECORD_LIMIT")
        line = canonical_json({"record": record, "checksum": self._checksum(record)}) + b"\n"
        existing = self.path.stat().st_size if self.path.exists() else 0
        if existing + len(line) > self.limits.max_bytes:
            raise JournalError("JOURNAL_FULL")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("ab") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise JournalError("JOURNAL_WRITE_FAILED", str(exc)) from exc
        self._records.append(record)
        self._apply_loaded(record)

    @_mutating
    def append_command(self, *, project_id: str, command_id: str, digest: str,
                       receipt: Mapping[str, Any], now_ms: int, pending: bool = False) -> dict[str, Any]:
        if not all(isinstance(value, str) and value for value in (project_id, command_id)):
            raise JournalError("INVALID_COMMAND_ID")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise JournalError("INVALID_DIGEST")
        key = (project_id, command_id)
        existing = self._commands.get(key)
        if existing is not None:
            if existing["digest"] != digest:
                raise JournalError("COMMAND_ID_PAYLOAD_CONFLICT")
            if now_ms > existing["expires_ms"]:
                raise JournalError("RETRY_HORIZON_EXPIRED")
            return {"receipt": existing["receipt"], "replayed": True, "status": existing["status"]}
        if not isinstance(receipt, Mapping):
            raise JournalError("INVALID_RECEIPT")
        if pending and sum(1 for item in self._commands.values() if item["status"] == "ACCEPTED_PENDING") >= self.limits.max_pending_commands:
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
        key = (project_id, command_id)
        existing = self._commands.get(key)
        if existing is None:
            raise JournalError("COMMAND_NOT_FOUND")
        if now_ms > existing["expires_ms"]:
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

    def lookup(self, *, project_id: str, command_id: str, now_ms: int) -> dict[str, Any]:
        existing = self._commands.get((project_id, command_id))
        if existing is None:
            raise JournalError("COMMAND_NOT_FOUND")
        if now_ms > existing["expires_ms"]:
            raise JournalError("RETRY_HORIZON_EXPIRED")
        return {"receipt": existing["receipt"], "status": existing["status"], "replayed": True}

    @_mutating
    def acquire_lease(self, *, project_id: str, target: str, owner: str,
                      now_ms: int, ttl_ms: int) -> Lease:
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

    def check_lease(self, lease: Lease, *, now_ms: int) -> None:
        current = self._leases.get((lease.project_id, lease.target))
        if current != lease or lease.expires_ms <= now_ms:
            raise JournalError("STALE_LEASE")

    @staticmethod
    def check_revision(*, expected_revision: str, current_revision: str) -> None:
        if not isinstance(expected_revision, str) or not isinstance(current_revision, str) or expected_revision != current_revision:
            raise JournalError("REVISION_MISMATCH")

    @_mutating
    def compact(self, *, now_ms: int) -> None:
        """Atomically rewrite retained tombstones/leases after a checkpoint."""
        # Keep an immutable tombstone for every expired ID.  Dropping it would
        # permit a retry after the horizon to be interpreted as a new command.
        records = []
        for record in self._commands.values():
            if record["expires_ms"] >= now_ms:
                records.append(record)
            else:
                tombstone = dict(record)
                tombstone.update(status="EXPIRED_TOMBSTONE", receipt={})
                records.append(tombstone)
        records += [{"kind": "lease", "project_id": lease.project_id, "target": lease.target,
                     "owner": lease.owner, "fencing_epoch": lease.fencing_epoch, "expires_ms": lease.expires_ms}
                    for lease in self._leases.values() if lease.expires_ms >= now_ms]
        encoded = b"".join(canonical_json({"record": r, "checksum": self._checksum(r)}) + b"\n" for r in records)
        if len(encoded) > self.limits.max_bytes:
            raise JournalError("JOURNAL_FULL")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self._records = records
        except OSError as exc:
            try:
                os.unlink(name)
            except OSError:
                pass
            raise JournalError("JOURNAL_COMPACT_FAILED", str(exc)) from exc
