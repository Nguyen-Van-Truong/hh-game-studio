"""Disposable exact disk indexes; the checksummed JSONL journal is authority.

One private connection per owner, with bounded pager/statement caches. This
removes cardinality-sized Python ID/offset containers; it is not an RSS bound.
Callers hold the journal writer guard across verification and derived updates.
"""
from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from contextlib import contextmanager
import operator
from pathlib import Path
import sqlite3
import stat
import tempfile
import threading
import weakref


class DiskIndexError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _encode_int(value):
    if type(value) is not int or value < 0:
        raise ValueError("index value must be a nonnegative integer")
    return value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")


def _decode_int(value):
    if type(value) is not bytes or not value:
        raise DiskIndexError("INDEX_VALUE_INVALID")
    return int.from_bytes(value, "big")


def _pair(key):
    if (not isinstance(key, tuple) or len(key) != 2
            or not all(isinstance(part, str) for part in key)):
        raise TypeError("command key must be a pair of strings")
    return tuple(part.encode("utf-8", "surrogatepass") for part in key)


def _identity(path, *, directory):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or (not stat.S_ISDIR(info.st_mode) if directory else
                not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
        raise DiskIndexError("INDEX_PATH_UNSAFE")
    return info.st_dev, info.st_ino


class DiskJournalIndex:
    """Own only one random directory beneath already trusted journal state.

    No persisted index is ever reopened. Same-principal hostile writers still
    require the journal's existing OS isolation; this is not a safe-write API.
    """
    def __init__(self, private_parent, *, cache_kib=256, cached_statements=32):
        self._lock = threading.RLock()
        self._depth = 0
        self._generation = 0
        self._closing = False
        self._broken = False
        self._db = self._dir = self._dir_identity = None
        try:
            parent = Path(private_parent).absolute()
            for item in (parent, *parent.parents):
                _identity(item, directory=True)
            self._parent = parent
            self._dir = Path(tempfile.mkdtemp(prefix=".hh-index-", dir=parent))
            self._dir_identity = _identity(self._dir, directory=True)
            self._db = sqlite3.connect(self._dir / "index.sqlite3",
                isolation_level=None, check_same_thread=False,
                cached_statements=cached_statements, timeout=2)
            if sqlite3.threadsafety == 0:
                raise DiskIndexError("INDEX_THREADS_UNSUPPORTED")
            settings = {"page_size": 4096, "cache_size": -cache_kib,
                        "mmap_size": 0, "temp_store": 1, "synchronous": 2}
            for key, value in settings.items():
                if type(value) is not int:
                    raise ValueError("integer index setting required")
                self._execute(f"PRAGMA {key}={value}")
                if self._one(f"PRAGMA {key}")[0] != value:
                    raise DiskIndexError("INDEX_SETTINGS_UNSUPPORTED")
            if self._one("PRAGMA journal_mode=DELETE")[0] != "delete":
                raise DiskIndexError("INDEX_SETTINGS_UNSUPPORTED")
            self._execute("PRAGMA cache_spill=ON")
            if self._one("PRAGMA cache_spill")[0] <= 0:
                raise DiskIndexError("INDEX_SETTINGS_UNSUPPORTED")
            self._execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value BLOB NOT NULL)")
            self._execute("CREATE TABLE records (ordinal INTEGER PRIMARY KEY, offset BLOB NOT NULL, size BLOB NOT NULL)")
            self._execute("CREATE TABLE projects (ordinal INTEGER PRIMARY KEY, key BLOB UNIQUE NOT NULL)")
            self._execute("CREATE TABLE commands (project INTEGER NOT NULL, key BLOB NOT NULL, ordinal INTEGER NOT NULL, value BLOB NOT NULL, PRIMARY KEY(project,key), UNIQUE(project,ordinal)) WITHOUT ROWID")
            with self.transaction():
                for key in ("records", "commands", "project_seq", "command_seq", "bytes"):
                    self._execute("INSERT INTO meta VALUES (?,?)", (key, _encode_int(0)))
            self.offsets = DiskOffsets(self)
            self.commands = DiskCommands(self)
        except BaseException as error:
            failure = error if isinstance(error, DiskIndexError) else DiskIndexError("INDEX_OPEN_FAILED")
            try:
                self.close()
            except BaseException:
                failure.cleanup_owner = self
            raise failure from error

    def _ensure(self):
        if self._closing or self._broken or self._db is None:
            raise DiskIndexError("INDEX_CLOSED_OR_POISONED")

    def _execute(self, sql, args=(), *, fetch=False):
        with self._lock:
            self._ensure()
            cursor = None
            try:
                try:
                    cursor = self._db.execute(sql, args)
                    return cursor.fetchone() if fetch else None
                finally:
                    if cursor is not None:
                        cursor.close()
            except sqlite3.Error as error:
                raise DiskIndexError("INDEX_IO_FAILED") from error

    def _one(self, sql, args=()):
        return self._execute(sql, args, fetch=True)

    def _meta(self, key):
        return _decode_int(self._one("SELECT value FROM meta WHERE key=?", (key,))[0])

    def _set_meta(self, key, value):
        self._execute("UPDATE meta SET value=? WHERE key=?", (_encode_int(value), key))

    @property
    def indexed_bytes(self):
        return self._meta("bytes")

    @contextmanager
    def transaction(self):
        with self._lock:
            self._ensure()
            outer = self._depth == 0
            if outer:
                self._execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield
                if outer:
                    self._execute("COMMIT")
            except BaseException:
                if outer:
                    try:
                        self._execute("ROLLBACK")
                    except DiskIndexError:
                        self._broken = True
                # Journal validation/flush exceptions keep their original code.
                raise
            finally:
                self._depth -= 1
                self._generation += 1

    def close(self):
        with self._lock:
            self._closing = True
            try:
                if self._db is not None:
                    self._db.close()
                    self._db = None
                if self._dir is not None:
                    # Never recursively delete: verify the exact owned directory
                    # and reject unknown entries or aliases before unlinking.
                    if (self._dir.parent != self._parent or
                            _identity(self._dir, directory=True) != self._dir_identity):
                        raise DiskIndexError("INDEX_CLEANUP_IDENTITY")
                    entries = list(self._dir.iterdir())
                    if len(entries) > 2:
                        raise DiskIndexError("INDEX_CLEANUP_UNEXPECTED")
                    for path in entries:
                        if path.name not in {"index.sqlite3", "index.sqlite3-journal"}:
                            raise DiskIndexError("INDEX_CLEANUP_UNEXPECTED")
                        _identity(path, directory=False)
                    for path in entries:
                        path.unlink()
                    self._dir.rmdir()
                    self._dir = None
            except (sqlite3.Error, OSError, DiskIndexError) as error:
                failure = DiskIndexError("INDEX_CLOSE_FAILED")
                failure.cleanup_owner = self
                raise failure from error


class DiskOffsets(Sequence):
    def __init__(self, owner):
        self._owner = weakref.ref(owner)

    @property
    def owner(self):
        owner = self._owner()
        if owner is None:
            raise DiskIndexError("INDEX_OWNER_GONE")
        return owner

    def __len__(self):
        return self.owner._meta("records")

    def __getitem__(self, index):
        with self.owner._lock:
            if isinstance(index, slice):
                return [self[i] for i in range(*index.indices(len(self)))]
            index = operator.index(index)
            if index < 0:
                index += len(self)
            if not 0 <= index < len(self):
                raise IndexError("offset index out of range")
            row = self.owner._one("SELECT offset,size FROM records WHERE ordinal=?", (index,))
            if row is None:
                raise DiskIndexError("INDEX_OFFSET_MISSING")
            return _decode_int(row[0]), _decode_int(row[1])

    def append(self, pair):
        offset, size = pair
        if any(type(value) is not int for value in (offset, size)):
            raise TypeError("offset and size must be integers")
        if any(not 0 <= value < 2**64 for value in (offset, size)):
            raise OverflowError("offset and size must fit uint64")
        with self.owner.transaction():
            index = len(self)
            self.owner._execute("INSERT INTO records VALUES (?,?,?)",
                (index, _encode_int(offset), _encode_int(size)))
            self.owner._set_meta("records", index + 1)
            self.owner._set_meta("bytes", self.owner.indexed_bytes + size)

    def clear(self):
        with self.owner.transaction():
            self.owner._execute("DELETE FROM records")
            self.owner._set_meta("records", 0)
            self.owner._set_meta("bytes", 0)


class DiskCommands(MutableMapping):
    def __init__(self, owner):
        self._owner = weakref.ref(owner)

    @property
    def owner(self):
        owner = self._owner()
        if owner is None:
            raise DiskIndexError("INDEX_OWNER_GONE")
        return owner

    def __len__(self):
        return self.owner._meta("commands")

    def __getitem__(self, key):
        row = self.owner._one("SELECT c.value FROM commands c JOIN projects p ON p.ordinal=c.project WHERE p.key=? AND c.key=?", _pair(key))
        if row is None:
            raise KeyError(key)
        return _decode_int(row[0])

    def __setitem__(self, key, value):
        project_key, command_key = _pair(key)
        encoded = _encode_int(value)
        with self.owner.transaction():
            row = self.owner._one("SELECT ordinal FROM projects WHERE key=?", (project_key,))
            if row is None:
                project = self.owner._meta("project_seq")
                self.owner._execute("INSERT INTO projects VALUES (?,?)", (project, project_key))
                self.owner._set_meta("project_seq", project + 1)
            else:
                project = row[0]
            row = self.owner._one("SELECT ordinal FROM commands WHERE project=? AND key=?", (project, command_key))
            if row is None:
                ordinal = self.owner._meta("command_seq")
                self.owner._execute("INSERT INTO commands VALUES (?,?,?,?)", (project, command_key, ordinal, encoded))
                self.owner._set_meta("command_seq", ordinal + 1)
                self.owner._set_meta("commands", len(self) + 1)
            else:
                self.owner._execute("UPDATE commands SET value=? WHERE project=? AND key=?", (encoded, project, command_key))

    def __delitem__(self, key):
        project_key, command_key = _pair(key)
        with self.owner.transaction():
            row = self.owner._one("SELECT c.project FROM commands c JOIN projects p ON p.ordinal=c.project WHERE p.key=? AND c.key=?", (project_key, command_key))
            if row is None:
                raise KeyError(key)
            project = row[0]
            self.owner._execute("DELETE FROM commands WHERE project=? AND key=?", (project, command_key))
            self.owner._set_meta("commands", len(self) - 1)
            if self.owner._one("SELECT 1 FROM commands WHERE project=? LIMIT 1", (project,)) is None:
                self.owner._execute("DELETE FROM projects WHERE ordinal=?", (project,))

    def __iter__(self):
        # Keyset iteration opens no cursor across yield; exact grouped insertion
        # order uses the covering (project,ordinal) index without a full sorter.
        generation = self.owner._generation
        project = command = -1
        while True:
            with self.owner._lock:
                if generation != self.owner._generation:
                    raise RuntimeError("index mutated during iteration")
                row = self.owner._one("SELECT p.key,c.key,c.project,c.ordinal FROM commands c JOIN projects p ON p.ordinal=c.project WHERE (c.project,c.ordinal)>(?,?) ORDER BY c.project,c.ordinal LIMIT 1", (project, command))
                if row is None:
                    return
                project, command = row[2], row[3]
            yield tuple(part.decode("utf-8", "surrogatepass") for part in row[:2])

    def clear(self):
        with self.owner.transaction():
            self.owner._execute("DELETE FROM commands")
            self.owner._execute("DELETE FROM projects")
            for key in ("commands", "project_seq", "command_seq"):
                self.owner._set_meta(key, 0)
