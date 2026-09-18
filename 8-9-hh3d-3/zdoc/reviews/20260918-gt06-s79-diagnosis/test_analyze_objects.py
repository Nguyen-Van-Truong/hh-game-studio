"""Synthetic S79 analyzer accounting checks; no native process or real evidence reads."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location('s79_object_analyzer', Path(__file__).with_name('analyze_objects.py'))
ANALYZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZER)


def descriptor(identity, classname):
    return {'id': str(identity), 'class': classname, 'relation': 'node', 'queued_for_deletion': False}


def tree(columns=1):
    return descriptor(10, 'Tree') | {'path': '/root/Editor/History/Tree', 'parent_id': '9',
                                    'inside_tree': True, 'visible': False,
                                    'columns': columns, 'hide_root': True}


def label():
    return descriptor(11, 'RichTextLabel') | {'path': '/root/Editor/Output/Label', 'parent_id': '8',
                                             'inside_tree': True, 'visible': False,
                                             'paragraph_count': 101, 'character_count': 1024}


def item(identity=30, text='entry', columns=1):
    cells = [{'column': column, 'text': text[:512], 'length': len(text),
              'sha256': ANALYZER.sha(text.encode('utf-8')), 'truncated': len(text) > 512}
             for column in range(min(columns, 8))]
    return descriptor(identity, 'TreeItem') | {
        'relation': 'tree_item:10', 'owner_tree_id': '10', 'owner_tree_path': tree()['path'],
        'owner_tree_visible': False, 'parent_item_id': '20', 'columns': columns, 'cell_texts': cells}


def point(sequence, items=2, added=None, changed=None, removed=None, columns=1):
    classes = {'Tree': 1, 'RichTextLabel': 1, 'TreeItem': items}
    count = sum(classes.values())
    counters = {'objects': 10 + 2 * (items - 2), 'cached_resources': 6, 'tree_nodes': 2,
                'orphan_nodes': 0, 'filesystem_scanning_before': False, 'filesystem_scanning_after': False}
    return {'sequence': sequence, 'label': 'settle' if sequence == 0 else 'idle',
            'batch': 5, 'cycle': 100, 'phase': 'BATCH_SETTLE' if sequence == 0 else 'BATCH_WRITE',
            'frame': 100 + sequence, 'mono_us': 1000000 * (sequence + 1), 'focused': False,
            'inventory_count': count, 'inventory_duration_us': 100, 'previous_snapshot_write_us': 20,
            'class_counts': classes, 'counters_before': counters, 'counters_after': deepcopy(counters),
            'counters_equal_across_collection': True, 'filesystem_scanning': False,
            'initial_inventory_ids_omitted': sequence == 0, 'initial_tree_and_richtext_ids_included': True,
            'added': ([tree(columns), label()] if sequence == 0 else []) if added is None else added,
            'changed': [] if changed is None else changed, 'removed': [] if removed is None else removed}


class PointAccountingTests(unittest.TestCase):
    def test_initial_known_population_is_not_added_or_double_counted(self):
        timeline, summary = ANALYZER.analyze_points([point(0)])
        self.assertEqual(timeline[0]['known_active_ids'], 2)
        self.assertEqual(timeline[0]['omitted_initial_active_ids'], 2)
        self.assertEqual(summary['initial_observations_by_class'], {'Tree': 1, 'RichTextLabel': 1})
        self.assertEqual(summary['transitions_by_class'], {'added': {}, 'changed': {}, 'removed': {}})
        self.assertEqual(len(timeline[0]['descriptors']['initial']), 2)
        self.assertEqual(timeline[0]['descriptors']['added'], [])
        self.assertTrue(timeline[0]['rich_text_labels']['all_reachable_ids_seen'])

    def test_add_discover_omitted_and_remove_reconstruct_population(self):
        new_item = item(30, 'Việt Nam 🚀')
        existing = item(20, 'root')
        points = [point(0), point(1, 3, added=[new_item]), point(2, 3, changed=[existing]),
                  point(3, 2, removed=[item(21) | {'still_valid': False}]),
                  point(4, 1, removed=[new_item | {'still_valid': True}])]
        timeline, summary = ANALYZER.analyze_points(points)
        self.assertEqual([entry['known_active_ids'] for entry in timeline], [2, 3, 4, 4, 3])
        self.assertEqual([entry['omitted_initial_active_ids'] for entry in timeline], [2, 2, 1, 0, 0])
        self.assertEqual(timeline[1]['descriptors']['added'][0], new_item)
        self.assertFalse(timeline[2]['descriptors']['changed'][0]['before_known'])
        self.assertTrue(timeline[4]['descriptors']['removed'][0]['still_valid'])
        additions = summary['tree_item_additions']
        self.assertEqual(additions['count'], 1)
        self.assertEqual(additions['by_column_count'], {'1': 1})
        self.assertEqual(additions['entries'][0]['descriptor']['cell_texts'][0]['text'], 'Việt Nam 🚀')
        self.assertFalse(additions['entries'][0]['reachable_at_final_point'])

    def test_empty_and_nonempty_unicode_digest_validation(self):
        for text in ('', 'Việt Nam 🚀', 'e\u0301', '\U0001f680'):
            with self.subTest(text=text):
                row = item(text=text)
                ANALYZER.descriptor_check(row)
                row['cell_texts'][0]['sha256'] = '0' * 64
                with self.assertRaisesRegex(ANALYZER.InvalidEvidence, 'text hash mismatch'):
                    ANALYZER.descriptor_check(row)
        self.assertEqual(item(text='')['cell_texts'][0]['sha256'],
                         'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')

    def test_truncated_text_and_column_bound_are_explicit(self):
        row = item(text='ấ' * 513, columns=9)
        ANALYZER.descriptor_check(row)
        self.assertEqual(len(row['cell_texts']), 8)
        self.assertTrue(row['cell_texts'][0]['truncated'])
        timeline, summary = ANALYZER.analyze_points([point(0, columns=9), point(1, 3, added=[row])])
        self.assertEqual(summary['tree_item_additions']['by_column_count'], {'9': 1})
        self.assertEqual(timeline[1]['descriptors']['added'][0]['columns'], 9)
        row['cell_texts'].pop()
        with self.assertRaisesRegex(ANALYZER.InvalidEvidence, 'column coverage'):
            ANALYZER.descriptor_check(row)

    def test_initial_missing_unallowed_duplicate_and_transition_rows_rejected(self):
        cases = [point(0, added=[tree()]), point(0, added=[tree(), label(), item()]),
                 point(0, added=[tree(), label(), tree()]), point(0, changed=[item()]),
                 point(0, removed=[item() | {'still_valid': False}])]
        for initial in cases:
            with self.subTest(initial=initial), self.assertRaises(ANALYZER.InvalidEvidence):
                ANALYZER.analyze_points([initial])

    def test_owner_path_columns_visibility_and_id_must_resolve(self):
        mutations = [{'owner_tree_path': '/root/Wrong'}, {'columns': 2}, {'owner_tree_visible': True},
                     {'owner_tree_id': '99', 'relation': 'tree_item:99'}]
        for changed in mutations:
            row = item(columns=changed.get('columns', 1)) | changed
            with self.subTest(changed=changed), self.assertRaises(ANALYZER.InvalidEvidence):
                ANALYZER.analyze_points([point(0), point(1, 3, added=[row])])

    def test_inconsistent_class_totals_and_unavailable_omitted_population_rejected(self):
        with self.assertRaisesRegex(ANALYZER.InvalidEvidence, 'Class-count changes'):
            ANALYZER.analyze_points([point(0), point(1, 2, added=[item()])])
        with self.assertRaisesRegex(ANALYZER.InvalidEvidence, 'omitted initial inventory'):
            ANALYZER.analyze_points([point(0), point(1, changed=[label() | {'id': '99'}])])

    def test_known_change_remove_and_reachable_reentry(self):
        row = item()
        changed = item(text='changed')
        timeline, summary = ANALYZER.analyze_points([
            point(0), point(1, 3, added=[row]), point(2, 3, changed=[changed]),
            point(3, 2, removed=[changed | {'still_valid': True}]), point(4, 3, added=[changed])])
        self.assertTrue(timeline[2]['descriptors']['changed'][0]['before_known'])
        self.assertEqual(summary['tree_item_additions']['count'], 2)
        self.assertEqual(summary['transitions_by_class']['added'], {'TreeItem': 2})

    def test_error_log_is_rejected_even_when_text_digest_is_valid(self):
        ANALYZER.descriptor_check(item(text=''))
        with self.assertRaisesRegex(ANALYZER.InvalidEvidence, 'Warning/error/failure'):
            ANALYZER.clean_log(b'ERROR: Condition "p_src_len == 0" is true.\n at: update (core/crypto/hashing_context.cpp:47)',
                               'synthetic editor stderr')


if __name__ == '__main__':
    unittest.main(verbosity=2)
