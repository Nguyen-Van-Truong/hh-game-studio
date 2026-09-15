"""Internal retained-handle event log for a future release selector.

One private root, one permanent writer guard, one event stream. This is a
storage primitive, not command admission, activation, consumer adoption or a
public safe-write capability. No path/handle/configuration is accepted by IPC.
Torn/corrupt history is preserved and quarantined; there is no tail repair.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import threading
from typing import Iterator

from .limits import SafetyViolation, canonical_json, parse_json_utf8
from .private_store import PrivateBlobStore
from .safe_open import FileIdentity

MAX_EVENT_BYTES = 16 * 1024
MAX_LOG_BYTES = 8 * 1024 * 1024
MAX_RECORDS = 512
_ZERO = '0' * 64
_FORMAT = 'hh-private-events-1'
_OWNERS: dict[int, PrivateEventLog] = {}
_OWNERS_LOCK = threading.Lock()
MAX_OPEN_LOGS = 16


def pending_event_cleanup() -> tuple[PrivateEventLog, ...]:
    """Local supervisor ownership; never a wire result or automatic deletion."""
    with _OWNERS_LOCK:
        return tuple(_OWNERS.values())


class EventLogError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner: PrivateEventLog | None = None
        super().__init__(code)


@dataclass(frozen=True)
class EventHead:
    sequence: int
    sha256: str
    size: int


@dataclass(frozen=True)
class EventBinding:
    """Trusted local binding/high-water witness; not an agent-supplied token."""
    root: FileIdentity
    stream: FileIdentity
    witnessed: EventHead


@dataclass(frozen=True)
class EventRecord:
    head: EventHead
    event: bytes  # canonical immutable bytes; caller cannot mutate the log index


def _head_valid(head: object) -> bool:
    return (type(head) is EventHead and type(head.sequence) is int
            and 1 <= head.sequence <= MAX_RECORDS and type(head.size) is int
            and 36 < head.size <= MAX_LOG_BYTES and type(head.sha256) is str
            and re.fullmatch('[0-9a-f]{64}', head.sha256) is not None)


def _identity_valid(identity: object) -> bool:
    return (type(identity) is FileIdentity and type(identity.volume) is int
            and 0 <= identity.volume < 2**64 and type(identity.size) is int
            and identity.size >= 0 and type(identity.file_id) is str
            and re.fullmatch('[0-9a-f]{32}', identity.file_id) is not None)


class PrivateEventLog:
    """Exclusive broker storage. create() provisions, reopen() never creates.

    Reopening requires a trusted identity + acknowledged high-water witness.
    A fresh flush/chain check can reveal additional complete records; deciding
    their command/effect outcome belongs to explicit selector reconciliation.
    Storage calls are synchronous; an external owned-process deadline is needed
    for an unresponsive device. In-memory history stores offsets/hashes only.
    """
    @classmethod
    def create(cls, parent: str | Path) -> PrivateEventLog:
        return cls(parent, binding=None)

    @classmethod
    def reopen(cls, root: str | Path, binding: EventBinding) -> PrivateEventLog:
        if (type(binding) is not EventBinding or not _identity_valid(binding.root)
                or not _identity_valid(binding.stream) or not _head_valid(binding.witnessed)):
            raise EventLogError('EVENT_BINDING_REQUIRED')
        return cls(root, binding=binding)

    def __init__(self, path: str | Path, *, binding: EventBinding | None) -> None:
        self._mutex = threading.Lock()
        self._closed = self._poisoned = False
        self._store: PrivateBlobStore | None = None
        self._handle: int | None = None
        self._index: list[tuple[int, int, EventHead]] = []
        self._witness: EventHead | None = None
        with _OWNERS_LOCK:
            if len(_OWNERS) >= MAX_OPEN_LOGS:
                raise EventLogError('EVENT_OWNER_LIMIT')
            _OWNERS[id(self)] = self
        try:
            self._store = (PrivateBlobStore.create(path) if binding is None else
                           PrivateBlobStore.reopen(path, binding.root))
            self.root = self._store.root
            self._api = self._store._api
            self._path = self.root / '.events'
            self._handle = self._api.open(self._path, create=binding is None, writer=True)
            self._identity = self._api.inspect(self._handle, self._path)
            self._api.check_security(self._handle)
            if self._identity.volume != self._store.root_identity.volume:
                raise EventLogError('EVENT_VOLUME_CHANGED')
            if binding is None:
                if self._identity.size:
                    raise EventLogError('EVENT_NEW_FILE_NOT_EMPTY')
                # Flush the existing zero-byte guard too; neither it nor an
                # empty/missing event stream can authorize an empty recovery.
                self._api.flush(self._store._guard_handle)
                body, frame = self._encode(self._genesis(), 1, _ZERO)
                self._write_at(0, frame)
                self._api.flush(self._handle)
                self._scan()
                if self._read_at(0, len(frame)) != frame:
                    raise EventLogError('EVENT_INITIAL_READBACK_FAILED')
            else:
                if not binding.stream.same_file(self._identity):
                    raise EventLogError('EVENT_STREAM_IDENTITY_CHANGED')
                self._witness = binding.witnessed
                self._scan()
            self._witness = self._index[-1][2]
        except BaseException as exc:
            if self._store is None and type(getattr(exc, 'cleanup_owner', None)) is PrivateBlobStore:
                self._store = exc.cleanup_owner
            self._poisoned = True
            try:
                self.close()
            except BaseException:
                error = EventLogError('EVENT_INIT_CLEANUP_UNCERTAIN', outcome_unknown=True)
                error.cleanup_owner = self
                raise error from None
            if isinstance(exc, (SafetyViolation, OSError)):
                error = EventLogError('EVENT_RECOVERY_REQUIRED', outcome_unknown=True)
                error.cleanup_owner = self
                raise error from exc
            raise

    def _genesis(self) -> dict:
        return {'kind': 'GENESIS', 'store_id': self.root.name,
                'volume': str(self._identity.volume), 'file_id': self._identity.file_id,
                'root_file_id': self._store.root_identity.file_id}

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if not self._mutex.acquire(timeout=2):
            raise EventLogError('EVENT_STORE_BUSY', outcome_unknown=True)
        try:
            if self._closed or self._poisoned:
                raise EventLogError('EVENT_RECOVERY_REQUIRED', outcome_unknown=self._poisoned)
            yield
        finally:
            self._mutex.release()

    def _inspect(self) -> FileIdentity:
        self._store._check()
        identity = self._api.inspect(self._handle, self._path)
        self._api.check_security(self._handle)
        if not self._identity.same_file(identity) or not 0 <= identity.size <= MAX_LOG_BYTES:
            raise EventLogError('EVENT_STREAM_IDENTITY_CHANGED')
        # Only these two minted entries are valid in this dedicated log root.
        if {entry.name for entry in self.root.iterdir()} != {'.writer', '.events'}:
            raise EventLogError('EVENT_NAMESPACE_CHANGED')
        return identity

    def _read_at(self, offset: int, size: int) -> bytes:
        if not self._api.dll.SetFilePointerEx(self._handle, offset, None, 0):
            raise EventLogError('EVENT_SEEK_FAILED')
        buffer, count = C.create_string_buffer(size), W.DWORD()
        if not self._api.dll.ReadFile(self._handle, buffer, size, C.byref(count), None):
            raise EventLogError('EVENT_READ_FAILED')
        if count.value != size:
            raise EventLogError('EVENT_SHORT_READ')
        return buffer.raw

    def _write_at(self, offset: int, frame: bytes) -> None:
        if not self._api.dll.SetFilePointerEx(self._handle, offset, None, 0):
            raise EventLogError('EVENT_SEEK_FAILED')
        self._api.write(self._handle, frame)

    @staticmethod
    def _encode(event: dict, sequence: int, previous: str) -> tuple[bytes, bytes]:
        if type(event) is not dict:
            raise EventLogError('INVALID_EVENT')
        body = canonical_json({'format': _FORMAT, 'sequence': sequence,
                               'previous': previous, 'event': event})
        if not 1 <= len(body) <= MAX_EVENT_BYTES:
            raise EventLogError('EVENT_SIZE_LIMIT')
        return body, len(body).to_bytes(4, 'little') + body + hashlib.sha256(body).digest()

    def _decode(self, body: bytes, digest: bytes, sequence: int, previous: str) -> dict:
        if hashlib.sha256(body).digest() != digest:
            raise EventLogError('EVENT_CHECKSUM_FAILED')
        value = parse_json_utf8(body)
        if (type(value) is not dict or set(value) != {'format', 'sequence', 'previous', 'event'}
                or value['format'] != _FORMAT or type(value['sequence']) is not int
                or value['sequence'] != sequence or value['previous'] != previous
                or type(value['event']) is not dict or canonical_json(value) != body):
            raise EventLogError('EVENT_CHAIN_FAILED')
        if sequence == 1 and value['event'] != self._genesis():
            raise EventLogError('EVENT_GENESIS_FAILED')
        return value['event']

    def _scan(self) -> None:
        """Fresh persistence barrier, bounded streaming validation, then publish index."""
        try:
            before = self._inspect()
            self._api.flush(self._handle)
            index, offset, previous = [], 0, _ZERO
            while offset < before.size:
                if len(index) >= MAX_RECORDS or before.size - offset < 36:
                    raise EventLogError('EVENT_TRUNCATED_OR_LIMIT')
                size = int.from_bytes(self._read_at(offset, 4), 'little')
                if not 1 <= size <= MAX_EVENT_BYTES or offset + size + 36 > before.size:
                    raise EventLogError('EVENT_TRUNCATED_OR_LIMIT')
                body = self._read_at(offset + 4, size)
                digest = self._read_at(offset + 4 + size, 32)
                self._decode(body, digest, len(index) + 1, previous)
                previous = digest.hex()
                head = EventHead(len(index) + 1, previous, offset + size + 36)
                index.append((offset, size, head))
                offset = head.size
            if not index or self._inspect() != before:
                raise EventLogError('EVENT_HISTORY_CHANGED')
            if self._witness is not None:
                witness = self._witness
                if len(index) < witness.sequence or index[witness.sequence - 1][2] != witness:
                    raise EventLogError('EVENT_HIGH_WATER_MISMATCH')
            self._index = index
        except BaseException as exc:
            self._poisoned = True
            if isinstance(exc, (SafetyViolation, OSError)):
                raise EventLogError('EVENT_RECOVERY_REQUIRED', outcome_unknown=True) from exc
            raise

    def binding(self) -> EventBinding:
        with self._locked():
            self._scan()
            self._witness = self._index[-1][2]
            return EventBinding(self._store.root_identity, self._identity, self._witness)

    def read(self, sequence: int) -> EventRecord:
        if type(sequence) is not int or not 1 <= sequence <= MAX_RECORDS:
            raise EventLogError('INVALID_EVENT_SEQUENCE')
        with self._locked():
            self._scan()
            if sequence > len(self._index):
                raise EventLogError('EVENT_NOT_FOUND')
            offset, size, head = self._index[sequence - 1]
            try:
                body = self._read_at(offset + 4, size)
                event = self._decode(body, bytes.fromhex(head.sha256), sequence,
                                     _ZERO if sequence == 1 else self._index[sequence - 2][2].sha256)
                self._inspect()
                self._witness = self._index[-1][2]
                return EventRecord(head, canonical_json(event))
            except BaseException as exc:
                self._poisoned = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise EventLogError('EVENT_RECOVERY_REQUIRED', outcome_unknown=True) from exc
                raise

    def append(self, event: dict, expected: EventHead, *, reserve_records: int = 0,
               reserve_bytes: int = 0) -> EventHead:
        """Compare tail and append under one guard. Reservations are capacity
        checks for the trusted selector; it must persist/reconstruct ownership
        of those reservations in its typed intent records before new admission.
        """
        if (not _head_valid(expected) or type(reserve_records) is not int
                or not 0 <= reserve_records < MAX_RECORDS or type(reserve_bytes) is not int
                or not 0 <= reserve_bytes <= MAX_LOG_BYTES):
            raise EventLogError('INVALID_EVENT_APPEND')
        # Canonicalize/copy input before I/O: later caller mutation cannot alter
        # the bytes whose checksum and size were validated.
        body, frame = self._encode(event, expected.sequence + 1, expected.sha256)
        with self._locked():
            self._scan()
            if self._index[-1][2] != expected:
                raise EventLogError('EVENT_HEAD_CONFLICT')
            if (expected.sequence + 1 + reserve_records > MAX_RECORDS
                    or expected.size + len(frame) + reserve_bytes > MAX_LOG_BYTES):
                raise EventLogError('EVENT_CAPACITY')
            try:
                self._write_at(expected.size, frame)
                self._api.flush(self._handle)
                self._scan()
                head = EventHead(expected.sequence + 1, hashlib.sha256(body).hexdigest(), expected.size + len(frame))
                if self._index[-1][2] != head or self._read_at(expected.size, len(frame)) != frame:
                    raise EventLogError('EVENT_APPEND_READBACK_FAILED')
                self._inspect()
                self._witness = head
                return head
            except BaseException as exc:
                self._poisoned = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise EventLogError('EVENT_APPEND_UNCERTAIN', outcome_unknown=True) from exc
                raise

    def close(self) -> None:
        if not self._mutex.acquire(timeout=2):
            raise EventLogError('EVENT_STORE_BUSY', outcome_unknown=True)
        try:
            self._closed = True
            # Stream first; retain root/guard if stream close fails. A later
            # close resumes these exact owners, even after constructor failure.
            if self._handle is not None:
                try:
                    self._api.close(self._handle)
                except SafetyViolation as exc:
                    raise EventLogError('EVENT_CLOSE_UNCERTAIN', outcome_unknown=True) from exc
                self._handle = None
            if self._store is not None:
                self._store.close()
            with _OWNERS_LOCK:
                _OWNERS.pop(id(self), None)
        finally:
            self._mutex.release()

    def __enter__(self) -> PrivateEventLog:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
