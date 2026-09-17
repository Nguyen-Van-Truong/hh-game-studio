"""Engine-free index equivalence checks and explicitly synthetic sizing."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.replay.journal_index import PackedOffsets, ProjectCommandIndex


class PackedOffsetsTests(unittest.TestCase):
    def test_index_iteration_and_negative_bounds_match_list(self):
        pairs = [(0, 9), (9, 11), (20, 13)]
        packed = PackedOffsets(pairs)
        self.assertEqual(len(packed), len(pairs))
        self.assertEqual(list(packed), pairs)
        for position in range(-len(pairs), len(pairs)):
            self.assertEqual(packed[position], pairs[position])
        for position in (-4, 3):
            with self.assertRaises(IndexError):
                packed[position]
        with self.assertRaises(TypeError):
            packed[1.0]
        self.assertEqual(packed[::-1], pairs[::-1])
        self.assertEqual(packed[1:], pairs[1:])
        self.assertEqual(list(reversed(packed)), list(reversed(pairs)))

    def test_full_uint64_domain_is_lossless(self):
        pairs = [(2**32 + 17, 2**40 + 3), (2**64 - 1, 2**64 - 1)]
        self.assertEqual(list(PackedOffsets(pairs)), pairs)

    def test_invalid_append_cannot_partially_mutate_a_pair(self):
        packed = PackedOffsets([(3, 5)])
        for pair, error in (((4, 2**64), OverflowError), ((-1, 7), OverflowError),
                            ((4, -7), OverflowError), ((4, '7'), TypeError),
                            ((4, True), TypeError), ((4,), ValueError), ((4, 5, 6), ValueError)):
            with self.subTest(pair=pair):
                with self.assertRaises(error):
                    packed.append(pair)
                self.assertEqual(list(packed), [(3, 5)])

    def test_clear_then_rebuild_discards_previous_offsets(self):
        packed = PackedOffsets([(2**50, 800), (2**51, 900)])
        packed.clear()
        self.assertEqual(len(packed), 0)
        with self.assertRaises(IndexError):
            packed[-1]
        packed.append((0, 400))
        self.assertEqual(list(packed), [(0, 400)])


class ProjectCommandIndexTests(unittest.TestCase):
    def test_same_id_in_different_projects_and_overwrites(self):
        index = ProjectCommandIndex({('p1', 'c'): 1, ('p2', 'c'): 2})
        index['p1', 'c'] = 9
        self.assertEqual(len(index), 2)
        self.assertEqual(index['p1', 'c'], 9)
        self.assertEqual(index['p2', 'c'], 2)
        self.assertIsNone(index.get(('p3', 'c')))

    def test_prefix_separator_and_unicode_keys_never_alias(self):
        keys = [('ab', 'c'), ('a', 'bc'), ('a:b', 'c'), ('a', 'b:c'),
                ('a\0b', 'c'), ('a', 'b\0c'), ('é', '雪'), ('e\u0301', '雪'),
                ('😀', '\ud800'), ('', ''), ('p', 'é'), ('p', 'e\u0301')]
        expected = {key: value for value, key in enumerate(keys)}
        index = ProjectCommandIndex(expected)
        self.assertEqual(dict(index), expected)
        self.assertEqual(len(index), len(keys))

    def test_values_view_retains_all_latest_records_for_compaction(self):
        index = ProjectCommandIndex()
        expected = {}
        values = index.values()
        for number in range(90):
            key = ('project' + str(number % 3), 'c' + str(number % 11))
            expected[key] = number
            index[key] = number
        self.assertEqual(dict(index), expected)
        self.assertCountEqual(values, expected.values())
        self.assertEqual(len(values), len(expected))
        self.assertEqual(sum(values), sum(expected.values()))

    def test_clear_and_rebuild_preserve_live_mapping_views(self):
        index = ProjectCommandIndex({('p', 'one'): 1, ('q', 'two'): 2})
        values = index.values()
        index.clear()
        self.assertEqual(len(values), 0)
        self.assertEqual(list(index), [])
        index.update({('new', 'id'): 2**70})
        self.assertEqual(list(values), [2**70])
        self.assertNotIn(('p', 'one'), index)

    def test_delete_removes_empty_project_and_missing_key_keeps_count(self):
        index = ProjectCommandIndex({('p', 'a'): 1, ('p', 'b'): 2, ('q', 'a'): 3})
        del index['p', 'a']
        del index['p', 'b']
        self.assertEqual(index._projects, {'q': {'a': 3}})
        with self.assertRaises(KeyError) as caught:
            del index['p', 'a']
        self.assertEqual(caught.exception.args, (('p', 'a'),))
        self.assertEqual(len(index), 1)

    def test_invalid_keys_do_not_alias_valid_tuple(self):
        index = ProjectCommandIndex({('a', 'b'): 3})
        for key in ('ab', ['a', 'b'], ('a',), ('a', 2)):
            with self.subTest(key=key), self.assertRaises(TypeError):
                index[key] = 4
        self.assertEqual(dict(index), {('a', 'b'): 3})
        for value in (-1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                index['a', 'b'] = value
        self.assertEqual(index['a', 'b'], 3)


class _IndexedJournal(Journal):
    """Test-only injection; the live Journal/VerifiedJournal are unchanged."""
    def _load(self):
        if not isinstance(self._records.offsets, PackedOffsets):
            self._records.offsets = PackedOffsets(self._records.offsets)
        if not isinstance(self._commands, ProjectCommandIndex):
            self._commands = ProjectCommandIndex(self._commands)
        super()._load()


class JournalIndexIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='gt06-index-test-')
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'commands.jsonl'

    @staticmethod
    def append(journal, project, command, *, pending=False, now=1):
        return journal.append_command(project_id=project, command_id=command,
            digest='sha256:' + 'a' * 64, receipt={'project': project, 'command': command},
            now_ms=now, pending=pending)

    def test_disk_records_reload_and_external_append_rebuild_exact_indexes(self):
        journal = _IndexedJournal(self.path)
        self.append(journal, 'p1', 'same')
        self.append(Journal(self.path), 'p2', 'same')
        self.assertEqual(journal.lookup(project_id='p2', command_id='same', now_ms=2)['receipt']['project'], 'p2')
        self.assertEqual(journal.lookup(project_id='p1', command_id='same', now_ms=2)['receipt']['project'], 'p1')
        self.assertIsInstance(journal._records.offsets, PackedOffsets)
        self.assertIsInstance(journal._commands, ProjectCommandIndex)
        self.assertEqual(len(journal._records), 2)
        self.assertEqual(journal._records[-1]['project_id'], 'p2')
        self.assertEqual(sum(size for _, size in journal._records.offsets), self.path.stat().st_size)

    def test_compaction_retains_each_cross_project_expired_tombstone(self):
        journal = _IndexedJournal(self.path, limits=JournalLimits(retry_horizon_ms=10))
        keys = [('p1', 'same'), ('p2', 'same'), ('p1', 'other'), ('p2', 'other')]
        for project, command in keys:
            self.append(journal, project, command)
        journal.compact(now_ms=30)
        self.assertEqual(len(journal._commands), len(keys))
        self.assertEqual(len(journal._records), len(keys))
        self.assertEqual({(row['project_id'], row['command_id']) for row in journal._records}, set(keys))
        self.assertTrue(all(row['status'] == 'EXPIRED_TOMBSTONE' for row in journal._records))
        reopened = _IndexedJournal(self.path, limits=journal.limits)
        for target in (journal, reopened):
            for project, command in keys:
                with self.assertRaisesRegex(JournalError, 'RETRY_HORIZON_EXPIRED'):
                    self.append(target, project, command, now=31)

    def test_terminal_transition_replaces_index_without_losing_receipt_or_dedupe(self):
        journal = _IndexedJournal(self.path)
        self.append(journal, 'p', 'c', pending=True)
        terminal = {'result': 'terminal readback'}
        journal.finish_command(project_id='p', command_id='c', status='COMMITTED',
                               receipt=terminal, now_ms=2)
        self.assertEqual(len(journal._records), 2)
        self.assertEqual(list(journal._commands.values()), [1])
        self.assertEqual(journal.lookup(project_id='p', command_id='c', now_ms=3)['receipt'], terminal)
        journal.compact(now_ms=4)
        self.assertEqual(len(journal._records), 1)
        self.assertEqual(list(journal._commands.values()), [0])
        self.assertEqual(self.append(journal, 'p', 'c', now=5)['receipt'], terminal)
        with self.assertRaisesRegex(JournalError, 'COMMAND_ID_PAYLOAD_CONFLICT'):
            journal.append_command(project_id='p', command_id='c', digest='sha256:' + 'b' * 64,
                                   receipt={'different': True}, now_ms=5)

    def test_corrupted_history_still_rejected_by_accepted_parser(self):
        journal = _IndexedJournal(self.path)
        self.append(journal, 'p', 'c')
        with self.path.open('ab') as stream:
            stream.write(b'{')
        with self.assertRaisesRegex(JournalError, 'TRUNCATED'):
            journal.lookup(project_id='p', command_id='c', now_ms=2)


def _retained_bytes(value, seen=None):
    """Reachable allocation sizing, counting shared Python objects only once."""
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    result = sys.getsizeof(value)
    if isinstance(value, dict):
        return result + sum(_retained_bytes(k, seen) + _retained_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return result + sum(_retained_bytes(item, seen) for item in value)
    if isinstance(value, PackedOffsets):
        return result + _retained_bytes(value._words, seen)
    if isinstance(value, ProjectCommandIndex):
        return result + _retained_bytes(value._projects, seen) + _retained_bytes(value._size, seen)
    # array.__sizeof__ already includes its allocated payload. Iterating would
    # materialize integers which the packed container does not retain.
    return result


def allocation_report():
    offsets = [(number * 384, int('384')) for number in range(50_000)]
    packed = PackedOffsets(offsets)
    flat = {(b'gt06-synthetic-project'.decode(), f'gt06-synthetic.r00.a01.command.{number}'): number
            for number in range(24_500)}
    grouped = ProjectCommandIndex(flat)
    def comparison(before, after):
        old, new = _retained_bytes(before), _retained_bytes(after)
        return {'baseline_retained_bytes': old, 'candidate_retained_bytes': new,
                'saved_bytes': old - new, 'candidate_percent_of_baseline': round(100 * new / old, 3)}
    return {'scope': 'synthetic sys.getsizeof reachable allocations; not RSS or benchmark acceptance',
        'python': sys.version.split()[0], 'offset_pairs': 50_000, 'command_ids': 24_500,
        'projects': 1, 'offsets': comparison(offsets, packed), 'commands': comparison(flat, grouped),
        'assumptions': 'distinct decoded project strings as in JSON reload; exact command strings and indices retained'}


if __name__ == '__main__':
    if sys.argv[1:] == ['--size-report']:
        print(json.dumps(allocation_report(), sort_keys=True, indent=2))
    else:
        unittest.main()
