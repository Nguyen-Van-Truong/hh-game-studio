"""Path portability and separate evidence hash domains; no engine processes."""
from pathlib import Path
import json
import tempfile
import unittest

import evidence_view as view


class EvidenceViewTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.raw = self.base / 'raw'
        self.raw.mkdir()
        self.output = self.base / 'portable'
        self.scrub = view.PathView({'PROJECT': r'Q:\owned space\project-đ'}, forbidden_words=('private-user',))

    def write(self, name, data):
        path = self.raw / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def build(self):
        return view.build(self.raw, self.output, self.scrub)

    def test_empty_stderr_is_preserved_and_inventoried(self):
        self.write('stderr.txt', b'')
        manifest = self.build()
        self.assertEqual((self.output / 'view/stderr.txt').read_bytes(), b'')
        self.assertEqual(manifest['files']['stderr.txt']['view_sha256'], view.sha(b''))
        self.assertTrue(view.verify(self.output)['view_integrity'])

    def test_json_escaping_unicode_case_and_slashes_are_scrubbed_without_raw_mutation(self):
        original = view.encoded({'argv': [r'q:\OWNED SPACE\project-đ\a.blend',
                                         'Q:/owned space/project-đ/a.blend'], 'exit_code': 0})
        self.write('launch.json', original)
        manifest = self.build()
        clean = json.loads((self.output / 'view/launch.json').read_bytes())
        self.assertEqual(clean, {'argv': [r'$PROJECT\a.blend', '$PROJECT/a.blend'], 'exit_code': 0})
        self.assertEqual((self.raw / 'launch.json').read_bytes(), original)
        row = manifest['files']['launch.json']
        self.assertNotEqual(row['raw_sha256'], row['view_sha256'])
        self.assertTrue(view.verify(self.output, raw_root=self.raw, scrubber=self.scrub)['raw_transform_verified'])
        self.assertFalse(view.verify(self.output)['raw_transform_verified'])

    def test_sibling_prefix_and_unknown_drive_unc_posix_fail_before_output(self):
        for path in (r'Q:\owned space\project-đ-other\asset', r'X:\foreign\asset',
                     r'\\invalid.example\share\asset', '/home/private-user/asset'):
            self.write('log.txt', path.encode())
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.build()
            self.assertFalse(self.output.exists())

    def test_binary_and_source_are_hash_only_not_transformed(self):
        binary = b'BLENDER\0' + r'Q:\owned space\project-đ\source.blend'.encode('utf-16-le')
        self.write('source/module.py', b'original source')
        self.write('mesh.blend', binary)
        manifest = self.build()
        self.assertFalse((self.output / 'view').exists())
        self.assertEqual((self.raw / 'mesh.blend').read_bytes(), binary)
        for row in manifest['files'].values():
            self.assertIsNone(row['view_sha256'])
            self.assertEqual(row['mode'], 'hash-only-source-or-binary')
        self.assertTrue(view.verify(self.output, raw_root=self.raw, scrubber=self.scrub)['raw_transform_verified'])

    def test_raw_tamper_cannot_be_verified_by_view_hash(self):
        self.write('stdout.txt', b'PASS\n')
        self.build()
        self.write('stdout.txt', b'FAIL\n')
        with self.assertRaisesRegex(ValueError, 'LOCAL_RAW_INVENTORY_MISMATCH'):
            view.verify(self.output, raw_root=self.raw, scrubber=self.scrub)

    def test_view_tamper_and_missing_empty_stream_reject(self):
        self.write('stdout.txt', b'FAIL\n')
        self.write('stderr.txt', b'')
        self.build()
        output = self.output / 'view/stdout.txt'
        output.write_bytes(b'PASS\n')
        with self.assertRaisesRegex(ValueError, 'VIEW_INVENTORY_MISMATCH'):
            view.verify(self.output)
        output.write_bytes(b'FAIL\n')
        (self.output / 'view/stderr.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'VIEW_INVENTORY_MISMATCH'):
            view.verify(self.output)

    def test_view_cannot_claim_raw_is_present(self):
        self.write('stdout.txt', b'PASS\n')
        manifest = self.build()
        manifest['exact_raw_available_in_view'] = True
        (self.output / 'manifest.json').write_bytes(view.encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'VIEW_SCOPE'):
            view.verify(self.output)

    def test_changed_transformation_mode_rejected_against_originals(self):
        self.write('stdout.txt', b'PASS\n')
        manifest = self.build()
        manifest['files']['stdout.txt']['mode'] = 'sanitized-utf8'
        (self.output / 'manifest.json').write_bytes(view.encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'TRANSFORM_BINDING_MISMATCH'):
            view.verify(self.output, raw_root=self.raw, scrubber=self.scrub)

    def test_duplicate_keys_nonfinite_or_personal_values_reject(self):
        for raw in (b'{"exit":0,"exit":1}', b'{"value":NaN}', b'{"user":"private-user"}'):
            self.write('report.json', raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.build()
            self.assertFalse(self.output.exists())

    def test_path_key_collision_rejected(self):
        self.write('report.json', view.encoded({r'Q:\owned space\project-đ\asset': 0, r'$PROJECT\asset': 1}))
        with self.assertRaisesRegex(ValueError, 'NORMALIZED_KEY_COLLISION'):
            self.build()

    def test_existing_view_is_never_overwritten(self):
        self.write('report.json', b'{}')
        self.build()
        before = view.inventory(self.output)
        with self.assertRaisesRegex(ValueError, 'VIEW_ALREADY_EXISTS'):
            self.build()
        self.assertEqual(view.inventory(self.output), before)

    def test_unsafe_manifest_path_is_never_opened(self):
        self.write('stdout.txt', b'PASS\n')
        manifest = self.build()
        manifest['files']['../outside'] = manifest['files'].pop('stdout.txt')
        (self.output / 'manifest.json').write_bytes(view.encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'UNSAFE_MANIFEST_PATH'):
            view.verify(self.output)


if __name__ == '__main__':
    unittest.main()
