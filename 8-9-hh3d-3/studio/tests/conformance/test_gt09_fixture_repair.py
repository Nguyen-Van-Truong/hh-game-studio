"""K9 must bind both real fixtures and reject incomplete/tampered raw.

Native tests use the retained real -72 diagnostic when present. It is never
input to final; final creates its own publications and repair runs.
"""
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from studio.tests.conformance import run_gt09_fixture_repair as repair

RAW = repair.STUDIO / '.local/reviews/k9-real-72'


class FixtureRepairTests(unittest.TestCase):
    def test_committed_repairs_restore_only_the_defective_assignment(self):
        recipe = repair.read(repair.RECIPE)
        for fixture, row in recipe['fixtures'].items():
            name = 'arena_physics.gd' if fixture == 'arena' else 'room3d_native.gd'
            files = {row['target']: (repair.STUDIO / 'tests/godot/gameplay_fixture' / name).read_bytes(),
                     'assets/unchanged.bin': b'untouched'}
            broken = repair.changed(files, row, seed=True)
            self.assertNotEqual(files, broken)
            self.assertEqual(repair.changed(broken, row, seed=False), files)
            with self.assertRaisesRegex(ValueError, 'K9_REPAIR_PRECONDITION'):
                repair.changed(broken, row, seed=True)

    @unittest.skipUnless((RAW / 'result.json').is_file(), 'local native diagnostic unavailable')
    def test_real_raw_verifier_is_readonly_and_requires_both_fixtures(self):
        trees = [RAW, RAW.with_name(RAW.name + '-arena'), RAW.with_name(RAW.name + '-room')]
        def inventory():
            return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                    for tree in trees for p in tree.rglob('*') if p.is_file()}
        before = inventory()
        repair.verify(RAW)
        self.assertEqual(inventory(), before)
        original = repair.read
        tampered = copy.deepcopy(original(RAW / 'result.json'))
        del tampered['fixtures']['arena']
        with patch.object(repair, 'read', side_effect=lambda p: tampered if p == RAW / 'result.json' else original(p)):
            with self.assertRaisesRegex(ValueError, 'K9_BOTH_FIXTURES_REQUIRED'):
                repair.verify(RAW)

    @unittest.skipUnless((RAW / 'result.json').is_file(), 'local native diagnostic unavailable')
    def test_clean_banner_cannot_replace_seed_symptom(self):
        doc = repair.read(RAW / 'result.json')
        row = doc['fixtures']['arena']
        files, expected, _ = repair.inputs(Path(row['publication']), 'arena')
        recipe = repair.read(repair.RECIPE)['fixtures']['arena']
        case = repair.case_for(repair.changed(files, recipe, seed=True), 'arena', expected)
        with self.assertRaisesRegex(ValueError, 'K9_PLAY_STATE'):
            repair.observe(RAW.with_name(RAW.name + '-arena') / 'seed', case, 'arena',
                           doc['source_closure_sha256'], seeded=True, play_exit=31)


if __name__ == '__main__':
    unittest.main()
