"""Focused engine-free checks for the disposable derived journal index."""
from pathlib import Path
import tempfile
import unittest

from studio.host.replay.disk_journal_index import DiskJournalIndex, DiskIndexError


class DiskJournalIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt06-disk-index-')
        self.addCleanup(self.temp.cleanup)
        self.index = DiskJournalIndex(Path(self.temp.name))
        self.addCleanup(self.index.close)

    def test_exact_keys_and_grouped_insertion_order(self):
        keys = [('p', 'same'), ('q', 'same'), ('p', 'nul\x00'),
                ('p', 'e\u0301'), ('p', 'é'), ('😀', '\ud800')]
        for number, key in enumerate(keys):
            self.index.commands[key] = number
        self.assertEqual(list(self.index.commands),
                         [keys[0], keys[2], keys[3], keys[4], keys[1], keys[5]])
        self.assertEqual(self.index.commands[('😀', '\ud800')], 5)

    def test_offsets_are_lossless_and_indexed_bytes_tracks_disk_rows(self):
        pairs = [(0, 9), (2**63 + 1, 2**32 + 3)]
        for pair in pairs:
            self.index.offsets.append(pair)
        self.assertEqual(list(self.index.offsets), pairs)
        self.assertEqual(self.index.indexed_bytes, sum(pair[1] for pair in pairs))
        self.index.offsets.clear()
        self.assertEqual(self.index.indexed_bytes, 0)

    def test_transaction_rolls_back_rows_and_meta(self):
        with self.assertRaises(RuntimeError):
            with self.index.transaction():
                self.index.commands[('p', 'c')] = 1
                raise RuntimeError('abort')
        self.assertNotIn(('p', 'c'), self.index.commands)
        self.assertEqual(len(self.index.offsets), 0)

    def test_clear_and_reinsert_get_new_project_order(self):
        self.index.commands[('p', 'a')] = 1
        self.index.commands[('q', 'b')] = 2
        del self.index.commands[('p', 'a')]
        self.index.commands[('p', 'c')] = 3
        self.assertEqual(list(self.index.commands), [('q', 'b'), ('p', 'c')])

    def test_close_is_idempotent_and_blocks_access(self):
        self.index.close()
        self.index.close()
        with self.assertRaises(DiskIndexError):
            len(self.index.commands)


if __name__ == '__main__':
    unittest.main(verbosity=2)
