"""GT06 journal with verified incremental tail replay.

The accepted Journal remains the writer/validator/lock implementation. A
fresh owner or replaced/truncated file still gets a complete parse and
durability barrier. Once the file identity is unchanged, an operation only
parses and hashes the bytes appended after the verified offset; a lookup with
no new tail does not reread or fsync the complete history. The decoded command
index remains in the bounded private SQLite store and receipt bodies stay on
disk. Any identity/size race fails closed and forces a later full recovery.
"""
from __future__ import annotations

import hashlib
import os
import stat
import threading
from contextlib import contextmanager

from studio.host.core.journal import Journal, JournalError
from studio.host.replay.disk_journal_index import DiskJournalIndex, DiskIndexError


def _read_verified_bytes(stream, digest, max_bytes):
    """Hash every byte using one temporary bounded buffer, then release it.

    Fewer read calls reduce I/O/GIL scheduling boundaries on large histories.
    The buffer is local to this operation, never retained or preallocated to
    affect baseline memory. Hash updates keep the existing 2047-byte bound.
    """
    size = 0
    scratch = bytearray(min(1_048_576, max_bytes + 1))
    with memoryview(scratch) as view:
        while True:
            capacity = min(len(view), max_bytes - size + 1)
            with view[:capacity] as destination:
                count = stream.readinto(destination)
            if type(count) is not int or not 0 <= count <= capacity:
                raise JournalError('JOURNAL_UNREADABLE')
            if not count:
                return size
            size += count
            if size > max_bytes:
                raise JournalError('JOURNAL_FULL')
            for offset in range(0, count, 2047):
                digest.update(view[offset:min(offset + 2047, count)])


class VerifiedJournal(Journal):
    def __init__(self, *args, **kwargs):
        self._cache_mutex = threading.RLock()
        self._cache_closed = False
        self._index_store = None
        self._verified_hash = None
        self._verified_identity = None
        self._verified_size = 0
        self._verified_generation = None
        self._verified_policy = None
        try:
            super().__init__(*args, **kwargs)
        except BaseException as error:
            try:
                self.close()
            except BaseException:
                error.cleanup_owner = self
            raise

    @staticmethod
    def _index_error(error):
        failure = JournalError('JOURNAL_INDEX_UNAVAILABLE')
        failure.outcome_unknown = True
        return failure

    @contextmanager
    def _writer_lock(self):
        # SQLite crosses request/Stop/completion threads. Serialize the whole
        # verified operation, including teardown, before the existing OS guard.
        acquired = self._cache_mutex.acquire(timeout=self.limits.lock_timeout_ms / 1000)
        if not acquired:
            error = JournalError('JOURNAL_LOCKED')
            error.outcome_unknown = True
            raise error
        try:
            if self._cache_closed:
                raise self._index_error(None)
            with super()._writer_lock():
                yield
        except DiskIndexError as error:
            self._verified_hash = None
            raise self._index_error(error) from error
        finally:
            self._cache_mutex.release()

    def close(self):
        # A failed close retains the same owner for a later cleanup attempt;
        # operations stay disabled even while that attempt is outstanding.
        with self._cache_mutex:
            self._cache_closed = True
            self._verified_hash = None
            self._verified_generation = None
            if self._index_store is not None:
                try:
                    self._index_store.close()
                except DiskIndexError as error:
                    failure = self._index_error(error)
                    failure.cleanup_owner = self
                    raise failure from error
                self._index_store = None

    def __enter__(self):
        if self._cache_closed:
            raise self._index_error(None)
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        # Tests and defensive constructor paths may abandon an instance
        # without reaching an explicit owner close. Best-effort only; normal
        # service shutdown still calls close and reports failures.
        try:
            if getattr(self, '_index_store', None) is not None:
                self._index_store.close()
        except BaseException:
            pass

    def _snapshot(self, *, synchronize):
        """Caller holds the inherited writer lock for the entire operation."""
        digest, size = hashlib.sha512(), 0
        try:
            with self.path.open('r+b') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise JournalError('JOURNAL_PATH_UNSAFE')
                if info.st_size > self.limits.max_bytes:
                    raise JournalError('JOURNAL_FULL')
                size = _read_verified_bytes(stream, digest, self.limits.max_bytes)
                final = os.fstat(stream.fileno())
                if (size != info.st_size or final.st_size != size
                        or (info.st_dev, info.st_ino) != (final.st_dev, final.st_ino)):
                    raise JournalError('JOURNAL_HISTORY_CHANGED')
                identity = (info.st_dev, info.st_ino)
                # Changed bytes must go through the accepted parser BEFORE
                # its fsync, preserving corruption/partial-record precedence.
                if synchronize and self._matches(digest, size, identity):
                    try:
                        stream.flush()
                        os.fsync(stream.fileno())
                    except OSError as error:
                        raise JournalError('JOURNAL_DURABILITY_UNCONFIRMED') from error
                return digest, size, identity
        except FileNotFoundError:
            return digest, 0, None
        except OSError as error:
            raise JournalError('JOURNAL_UNREADABLE') from error

    def _load(self):
        self._verified_hash = None
        self._verified_generation = None
        if self._index_store is not None:
            self._index_store.close()
            self._index_store = None
        try:
            self._index_store = DiskJournalIndex(self.path.parent)
        except DiskIndexError as error:
            self._index_store = getattr(error, 'cleanup_owner', None)
            raise
        self._records.offsets = self._index_store.offsets
        self._commands = self._index_store.commands
        self._pending.clear()
        self._leases.clear()
        # No fully populated Python index is built then converted. All replay
        # state is private until the accepted parser and recovery fsync succeed.
        before_digest, before_size, before_identity = self._snapshot(synchronize=False)
        with self._index_store.transaction():
            super()._load()
        digest, size, identity = self._snapshot(synchronize=False)
        expected_size = self._index_store.indexed_bytes
        if (size != expected_size or size != before_size or identity != before_identity
                or digest.digest() != before_digest.digest()):
            raise JournalError('JOURNAL_HISTORY_CHANGED')
        self._verified_hash, self._verified_size = digest, size
        self._verified_identity = identity
        if identity is None:
            self._verified_generation = None
            self._verified_policy = (self.limits, self.profile)
            return
        try:
            info = self.path.stat(follow_symlinks=False)
        except OSError as error:
            raise JournalError('JOURNAL_UNREADABLE') from error
        self._verified_generation = (info.st_mtime_ns, info.st_ctime_ns)
        self._verified_policy = (self.limits, self.profile)

    def _reload(self):
        try:
            if self._verified_hash is not None and self._tail_replay():
                return
            self._load()
        except BaseException:
            self._verified_hash = None
            self._verified_generation = None
            raise

    def _command(self, key):
        try:
            return super()._command(key)
        except JournalError:
            # Receipts are checked on disk even on a cached no-tail lookup.
            # Corrupt requested bytes poison the cache, including a rewrite
            # by the same OS principal that restores the metadata timestamp.
            self._verified_hash = None
            self._verified_generation = None
            raise

    def _tail_replay(self) -> bool:
        """Apply only a verified append after the current durable offset.

        The caller holds the writer guard.  We read one bounded record at a
        time, update the SQLite offset/command index in one transaction, and
        compare the file identity and size again before publishing the new
        fingerprint.  A partial or concurrently changed tail is never made
        visible as a successful operation.
        """
        try:
            with self.path.open('rb') as stream:
                first = os.fstat(stream.fileno())
                if not stat.S_ISREG(first.st_mode) or first.st_nlink != 1:
                    raise JournalError('JOURNAL_PATH_UNSAFE')
                identity = (first.st_dev, first.st_ino)
                if identity != self._verified_identity:
                    return False
                if first.st_size < self._verified_size:
                    return False
                if first.st_size > self.limits.max_bytes:
                    raise JournalError('JOURNAL_FULL')
                generation = (first.st_mtime_ns, first.st_ctime_ns)
                if self._verified_policy != (self.limits, self.profile):
                    return False
                # An append from another writer changes the generation.  A
                # local append updates the verified generation atomically, so
                # only that hot path can use tail replay; external changes
                # retain the complete rebuild/index fault boundary.
                if generation != self._verified_generation:
                    return False
                if first.st_size == self._verified_size:
                    # A metadata generation change can represent an in-place
                    # rewrite even when identity and size are unchanged.  It
                    # forces the existing full parser/checksum barrier rather
                    # than trusting a stale digest.  With no tail and no
                    # generation change, no full read or fsync is necessary.
                    if generation != self._verified_generation:
                        return False
                    # Keep the disposable SQLite index exercised on every
                    # cached operation.  This is a single bounded query, not a
                    # journal scan, and keeps index faults fail-closed.
                    self._index_store.health_check()
                    return True
                stream.seek(self._verified_size)
                digest = self._verified_hash.copy()
                offset = self._verified_size
                with self._index_store.transaction():
                    while offset < first.st_size:
                        if len(self._records) >= self.limits.max_records:
                            raise JournalError('JOURNAL_RECORD_LIMIT')
                        line = stream.readline(self.profile.max_envelope_bytes + 1)
                        if not line:
                            raise JournalError('JOURNAL_TRUNCATED')
                        if len(line) > self.profile.max_envelope_bytes:
                            raise JournalError('JOURNAL_RECORD_INVALID')
                        record = self._decode_record(line)
                        self._apply_loaded(record, len(self._records))
                        self._records.offsets.append((offset, len(line)))
                        digest.update(line)
                        offset += len(line)
                    final = os.fstat(stream.fileno())
                    if ((final.st_dev, final.st_ino) != identity or final.st_size != offset
                            or offset != first.st_size
                            or (final.st_mtime_ns, final.st_ctime_ns) != generation):
                        raise JournalError('JOURNAL_HISTORY_CHANGED')
                # The appending writer has already flushed and fsynced its
                # record.  Preserve the old recovery barrier for a new tail,
                # without paying it on no-op lookups.
                try:
                    with self.path.open('r+b') as durable:
                        durable.flush()
                        os.fsync(durable.fileno())
                except OSError as error:
                    raise JournalError('JOURNAL_DURABILITY_UNCONFIRMED') from error
                self._verified_hash = digest
                self._verified_size = offset
                self._verified_identity = identity
                self._verified_generation = generation
                self._verified_policy = (self.limits, self.profile)
                return True
        except FileNotFoundError:
            # An empty journal has no inode yet. Keep its disposable index and
            # cache stable; a populated history disappearing must recover via
            # the full loader instead.
            return self._verified_identity is None and self._verified_size == 0
        except OSError as error:
            raise JournalError('JOURNAL_UNREADABLE') from error

    def _matches(self, digest, size, identity):
        return (self._verified_hash is not None and size == self._verified_size
                and identity == self._verified_identity
                and (self.limits, self.profile) == self._verified_policy
                and digest.digest() == self._verified_hash.digest())

    def _append(self, record):
        # Compaction may replace the index owner. Do it before the disposable
        # transaction; never close/rebuild a connection inside its own commit.
        line, existing = self._prepare_append(record)
        # Encode using exactly the accepted serializer; never hash caller JSON.
        old_hash, old_size, old_identity = self._verified_hash, self._verified_size, self._verified_identity
        self._verified_hash = None
        self._verified_generation = None
        # A cache commit can fail after the authoritative append has fsynced.
        # Its rollback cannot undo that append. Leave the fingerprint poisoned
        # and report UNKNOWN so a later locked replay reconciles the same ID.
        try:
            with self._index_store.transaction():
                super()._append_prepared(record, line, existing)
        except DiskIndexError as error:
            raise self._index_error(error) from error
        if old_hash is None:
            return
        # An index cache is optional. If metadata cannot be confirmed, the next
        # operation performs full validation; the accepted append already fsynced.
        try:
            info = self.path.stat(follow_symlinks=False)
        except OSError:
            return
        identity = (info.st_dev, info.st_ino)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size != old_size + len(line)
                or old_identity is not None and identity != old_identity):
            return
        old_hash = old_hash.copy()
        old_hash.update(line)
        self._verified_hash, self._verified_size = old_hash, info.st_size
        self._verified_identity = identity
        self._verified_generation = (info.st_mtime_ns, info.st_ctime_ns)
        self._verified_policy = (self.limits, self.profile)
