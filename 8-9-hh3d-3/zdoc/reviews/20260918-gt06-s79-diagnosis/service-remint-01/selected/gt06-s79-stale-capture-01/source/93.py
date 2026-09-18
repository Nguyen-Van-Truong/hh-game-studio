"""Compact, derived in-memory indexes; the journal remains authoritative.

These containers own no files, receipts, locks or durability decisions. They
do not expire or evict entries. The caller must retain the accepted journal's
validation, writer lock, corruption checks and recovery fsync boundaries.
"""
from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator, MutableMapping, Sequence
import operator

_UINT64_MAX = (1 << 64) - 1


class PackedOffsets(Sequence[tuple[int, int]]):
    """Offset/length pairs stored as uint64 words, materialized only on access."""

    __slots__ = ('_words',)

    def __init__(self, pairs: Iterable[tuple[int, int]] = ()) -> None:
        self._words = array('Q')
        if self._words.itemsize != 8:
            raise RuntimeError('PackedOffsets requires 64-bit unsigned array words')
        for pair in pairs:
            self.append(pair)

    def __len__(self) -> int:
        return len(self._words) // 2

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[position] for position in range(*index.indices(len(self)))]
        index = operator.index(index)
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError('offset index out of range')
        position = index * 2
        return self._words[position], self._words[position + 1]

    def __iter__(self) -> Iterator[tuple[int, int]]:
        for position in range(0, len(self._words), 2):
            yield self._words[position], self._words[position + 1]

    def append(self, pair: tuple[int, int]) -> None:
        offset, length = pair
        if any(type(value) is not int for value in (offset, length)):
            raise TypeError('offset and length must be integers')
        if not (0 <= offset <= _UINT64_MAX and 0 <= length <= _UINT64_MAX):
            raise OverflowError('offset and length must fit uint64')
        # Validate/convert both words before extending: a bad second value
        # cannot leave half a pair in the live index.
        self._words.extend(array('Q', (offset, length)))

    def clear(self) -> None:
        self._words = array('Q')


class ProjectCommandIndex(MutableMapping[tuple[str, str], int]):
    """Exact latest-record map, retaining each project string once.

Iteration is grouped by project, then by command insertion order. It is not
the global insertion order of a flat dict. Mapping views still enumerate
every latest record exactly once, as journal compaction requires.
"""

    __slots__ = ('_projects', '_size')

    def __init__(self, entries=()) -> None:
        self._projects: dict[str, dict[str, int]] = {}
        self._size = 0
        self.update(entries)

    @staticmethod
    def _key(key) -> tuple[str, str]:
        if (not isinstance(key, tuple) or len(key) != 2
                or not all(isinstance(part, str) for part in key)):
            raise TypeError('command key must be a (project_id, command_id) string tuple')
        return key

    def __getitem__(self, key: tuple[str, str]) -> int:
        project, command = self._key(key)
        try:
            return self._projects[project][command]
        except KeyError:
            raise KeyError(key) from None

    def __setitem__(self, key: tuple[str, str], value: int) -> None:
        project, command = self._key(key)
        if type(value) is not int or value < 0:
            raise ValueError('record index must be a nonnegative integer')
        commands = self._projects.get(project)
        if commands is None:
            self._projects[project] = {command: value}
            self._size += 1
        else:
            added = command not in commands
            commands[command] = value
            self._size += int(added)

    def __delitem__(self, key: tuple[str, str]) -> None:
        project, command = self._key(key)
        try:
            commands = self._projects[project]
            del commands[command]
        except KeyError:
            raise KeyError(key) from None
        self._size -= 1
        if not commands:
            del self._projects[project]

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for project, commands in self._projects.items():
            for command in commands:
                yield project, command

    def __len__(self) -> int:
        return self._size

    def clear(self) -> None:
        self._projects.clear()
        self._size = 0
