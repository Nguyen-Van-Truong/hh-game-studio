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

from studio.host.core.journal import Journal, JournalError
from studio.host.replay.journal_index import PackedOffsets, ProjectCommandIndex


class VerifiedJournal(Journal):
    def __init__(self, *args, **kwargs):
        self._verified_hash = None
        self._verified_identity = None
        self._verified_size = 0
        self._verified_policy = None
        super().__init__(*args, **kwargs)

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
                while chunk := stream.read(min(65_536, self.limits.max_bytes - size + 1)):
                    size += len(chunk)
                    if size > self.limits.max_bytes:
                        raise JournalError('JOURNAL_FULL')
                    digest.update(chunk)
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
        # Derived exact indexes retain every record/command. Packing offsets
        # and sharing a project-key dictionary removes redundant Python
        # allocations without changing receipt bytes or the retry horizon.
        if not isinstance(self._records.offsets, PackedOffsets):
            self._records.offsets = PackedOffsets(self._records.offsets)
        if not isinstance(self._commands, ProjectCommandIndex):
            self._commands = ProjectCommandIndex(self._commands.items())
        # Includes record checksum/history/cap validation and its recovery fsync.
        super()._load()
        digest, size, identity = self._snapshot(synchronize=False)
        expected_size = sum(length for _, length in self._records.offsets)
        if size != expected_size:
            raise JournalError('JOURNAL_HISTORY_CHANGED')
        self._verified_hash, self._verified_size = digest, size
        self._verified_identity = identity
        self._verified_policy = (self.limits, self.profile)

    def _reload(self):
        try:
            digest, size, identity = self._snapshot(synchronize=True)
            if self._matches(digest, size, identity):
                return
            super()._reload()
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
        super()._append(record)
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
