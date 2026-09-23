"""Diagnostic candidate: one temporary bounded buffer, exact full-file hash.

No persistent history cache and no retained buffer at an observation boundary.
The stock caller still owns identity checks, lock, error mapping and fsync.
"""
from studio.host.core.journal import JournalError


def digest_stream(stream, digest, max_bytes, buffer_bytes):
    size = 0
    scratch = bytearray(min(buffer_bytes, max_bytes + 1))
    with memoryview(scratch) as view:
        while True:
            # Read at most one byte beyond the policy cap to detect overflow.
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
