"""Focused binding/overlay tests; no campaign, scheduler, HTTP or engine launch."""
import importlib.util
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('s97_adapter_under_test', BASE / 'coupled_phases.py')
entry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(entry)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.retained = entry.load_retained()
        self.old = {f'file-{index}.py': 'a' * 64 for index in range(50)}
        self.old[entry.NATIVE] = 'b' * 64
        self.files = dict(self.old, **{entry.NATIVE: 'c' * 64})
        self.value = {'freeze_status': 'ROOT_FROZEN', 'source_files': self.files,
                      'source_closure_sha256': self.retained.map_digest(self.files)}

    def test_pending_or_malformed_freeze_cannot_bind(self):
        for value in ({}, {'freeze_status': 'PENDING_ROOT_FREEZE'},
                      dict(self.value, source_closure_sha256='PENDING_ROOT_FREEZE'),
                      dict(self.value, source_closure_sha256='f' * 64)):
            with self.assertRaises(RuntimeError):
                entry.validate_freeze(value, self.old, self.retained.map_digest)

    def test_only_native_source_delta_and_complete_map_allowed(self):
        self.assertEqual(entry.validate_freeze(self.value, self.old, self.retained.map_digest),
                         self.value['source_closure_sha256'])
        for files in (self.old, dict(self.files, **{'file-0.py': 'd' * 64}),
                      {name: pin for name, pin in self.files.items() if name != 'file-0.py'}):
            value = dict(self.value, source_files=files,
                         source_closure_sha256=self.retained.map_digest(files))
            with self.assertRaises(RuntimeError):
                entry.validate_freeze(value, self.old, self.retained.map_digest)

    def test_new_identity_with_complete_original_helper_provenance(self):
        original_helpers = set(self.retained.HELPERS)
        original_patch = self.retained.patch_native
        self.retained.request_value = lambda console, windowed: ({'schema': 'old'}, 'no-launch')
        configured = entry.configure(self.retained, self.value['source_closure_sha256'])
        self.assertEqual(configured.RUN_ID, 'gt06-s97-coupled-phases-01')
        self.assertEqual(configured.PREFLIGHT_ID, 'gt06-s97-coupled-phases-preflight-01')
        self.assertEqual(configured.ENTRY, entry.ENTRY)
        self.assertEqual(configured.OUTPUT.name, configured.RUN_ID)
        self.assertEqual(configured.LAUNCH, BASE / 'launch-01')
        self.assertEqual(configured.SOURCE_MAP, BASE / 'source-current.json')
        self.assertTrue(original_helpers < set(configured.HELPERS))
        self.assertIn(entry.ENTRY, configured.HELPERS)
        self.assertIn(entry.SOURCE_MAP, configured.HELPERS)
        self.assertIs(configured.patch_native, original_patch)
        request, marker = configured.request_value(None, None)
        self.assertEqual(request['schema'], 'HH-GT06-S97-COUPLED-REQUEST-1')
        self.assertEqual(request['base_source_role'], 'root_frozen_S97_candidate_not_accepted')
        self.assertEqual(marker, 'no-launch')
        with self.assertRaisesRegex(RuntimeError, 'S97_COMPOSITION_REBOUND'):
            entry.configure(configured, 'd' * 64)

    def test_overlay_reversal_preserves_candidate_shared_open_helper(self):
        raw = (self.retained.STUDIO / 'tests/replay/benchmark_native.gd').read_bytes()
        probe = (self.retained.S95 / 'object_probe_s95.gd').read_bytes()
        self.assertIn(b'func _open_host_input(path: String, stage: String) -> FileAccess:', raw)
        inserted = b'    _s96_before_ack(digest)\n    if _failed:\n        return\n'
        patched = self.retained.patch_native(raw, probe)
        prefix = patched[:len(raw) + len(inserted)]
        self.assertEqual(prefix.count(inserted), 1)
        self.assertEqual(prefix.replace(inserted, b'', 1), raw)
        self.assertIn(b'hh-studio.gt06.s96-ack-sparse-attribution', patched)
        self.assertIn(b'"phase": "before_ack_counter_readback"', patched)


if __name__ == '__main__':
    unittest.main(verbosity=2)
