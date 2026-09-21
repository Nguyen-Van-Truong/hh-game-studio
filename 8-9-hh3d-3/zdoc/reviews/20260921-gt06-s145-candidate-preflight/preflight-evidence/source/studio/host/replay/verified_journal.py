"""GT06 candidate: reuse a decoded index only for byte-identical durable history.

The accepted Journal remains the writer/validator/lock implementation. Every
operation still takes its process lock, reads and hashes the entire regular
single-link file, and fsyncs it before exposing a receipt. Any external append,
replacement, truncation or policy change runs the accepted complete replay.
Only a successful local append extends the previously verified digest/index.
No mtime-only trust, skipped recovery barrier, journal reset, or larger limits.
The private in-memory fingerprint uses SHA-512, which is faster on the pinned
workstation. Persisted record checksums and protocol/evidence hashes remain
SHA-256; no history bytes or persistent receipt bodies are cached in RAM.
"""
from __future__ import annotations

import hashlib
import os
import stat
import threading
from contextlib import contextmanager

from studio.host.core.journal import Journal, JournalError
from studio.host.replay.disk_journal_index import DiskJournalIndex, DiskIndexError


class VerifiedJournal(Journal):
    def __init__(self, *args, **kwargs):
        self._cache_mutex = threading.RLock()
        self._cache_closed = False
        self._index_store = None
        self._verified_hash = None
        self._verified_identity = None
        self._verified_size = 0
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
                # Batch disk reads without retaining history. Large hashlib
                # updates release the GIL on each call; under concurrent host
                # work that can turn a short hash into repeated scheduling
                # waits. Small updates preserve the exact digest while normal
                # Python scheduling still allows other threads to progress.
                # Keep each disk read bounded so the host does not hold a large
                # temporary buffer across a coupled editor/native observation.
                # Hash updates remain <=2047 bytes, preserving the GIL-yield
                # avoidance proven by S142 while reducing transient pressure.
                while chunk := stream.read(min(65_536, self.limits.max_bytes - size + 1)):
                    size += len(chunk)
                    if size > self.limits.max_bytes:
                        raise JournalError('JOURNAL_FULL')
                    view = memoryview(chunk)
                    for offset in range(0, len(view), 2047):
                        digest.update(view[offset:offset + 2047])
                    view.release()
                    del view, chunk
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
        self._verified_policy = (self.limits, self.profile)

    def _reload(self):
        try:
            digest, size, identity = self._snapshot(synchronize=True)
            if self._matches(digest, size, identity):
                return
            self._load()
        except BaseException:
            self._verified_hash = None
            raise

    def _matches(self, digest, size, identity):
        return (self._verified_hash is not None and size == self._verified_size
                and identity == self._verified_identity
                and (self.limits, self.profile) == self._verified_policy
                and digest.digest() == self._verified_hash.digest())

    def _append(self, record):
        # Encode using exactly the accepted serializer; never hash caller JSON.
        line = self._encoded_record(record)
        old_hash, old_size, old_identity = self._verified_hash, self._verified_size, self._verified_identity
        self._verified_hash = None
        # A cache commit can fail after the authoritative append has fsynced.
        # Its rollback cannot undo that append. Leave the fingerprint poisoned
        # and report UNKNOWN so a later locked replay reconciles the same ID.
        try:
            with self._index_store.transaction():
                super()._append(record)
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
        self._verified_policy = (self.limits, self.profile)
