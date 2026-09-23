from pathlib import Path
import hashlib
import io
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from read_buffer import digest_stream
from studio.host.core.journal import JournalError


class ReadBufferTests(unittest.TestCase):
    def test_full_digest_and_tail_across_boundaries(self):
        raw = bytes(range(256)) * 8200 + b'last tail'
        for buffer_size in (65536, 262144, 1048576):
            with self.subTest(buffer=buffer_size):
                digest = hashlib.sha512()
                size = digest_stream(io.BytesIO(raw), digest, len(raw), buffer_size)
                self.assertEqual(size, len(raw))
                self.assertEqual(digest.digest(), hashlib.sha512(raw).digest())

    def test_short_reads_are_not_eof(self):
        class ShortRead(io.BytesIO):
            def readinto(self, target):
                return super().readinto(target[:7])
        raw = b'short read coverage' * 200
        digest = hashlib.sha512()
        self.assertEqual(digest_stream(ShortRead(raw), digest, len(raw), 1024), len(raw))
        self.assertEqual(digest.digest(), hashlib.sha512(raw).digest())

    def test_overflow_reads_only_one_extra_byte(self):
        stream = io.BytesIO(b'x' * 100)
        with self.assertRaisesRegex(JournalError, 'JOURNAL_FULL'):
            digest_stream(stream, hashlib.sha512(), 31, 64)
        self.assertEqual(stream.tell(), 32)

    def test_empty_file_and_zero_cap(self):
        self.assertEqual(digest_stream(io.BytesIO(), hashlib.sha512(), 0, 64), 0)
        with self.assertRaisesRegex(JournalError, 'JOURNAL_FULL'):
            digest_stream(io.BytesIO(b'x'), hashlib.sha512(), 0, 64)

    def test_unreadable_stream_rejected(self):
        for value in (None, -1, True, 200):
            with self.subTest(value=value):
                class Bad:
                    def readinto(self, target):
                        return value
                with self.assertRaisesRegex(JournalError, 'JOURNAL_UNREADABLE'):
                    digest_stream(Bad(), hashlib.sha512(), 100, 64)

    def test_hash_update_never_exceeds_original_gil_boundary(self):
        class Digest:
            sizes = []
            def update(self, value):
                self.sizes.append(len(value))
        digest = Digest()
        size = digest_stream(io.BytesIO(b'a' * 300000), digest, 300000, 262144)
        self.assertEqual(sum(digest.sizes), size)
        self.assertLessEqual(max(digest.sizes), 2047)


if __name__ == '__main__':
    unittest.main()
