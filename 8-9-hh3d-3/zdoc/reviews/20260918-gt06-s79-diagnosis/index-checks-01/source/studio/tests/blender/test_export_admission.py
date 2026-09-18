"""Unsupported dependencies are rejected before path resolution or any I/O."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_native_preview as fixture

profile = fixture.load('gt04_export_admission', 'blender-addon/export_profile.py')


class UnreadableReference:
    """Even reading the filepath is unnecessary for unsupported datablocks."""
    @property
    def filepath(self):
        raise AssertionError('unsupported filepath read')

    @property
    def source(self):
        raise AssertionError('unsupported image inspected')


class ExportAdmissionTests(unittest.TestCase):
    def check_dependency(self, kind, reference):
        resolver = Mock(side_effect=AssertionError('external path resolution'))
        bpy = SimpleNamespace(app=SimpleNamespace(version=(5, 2, 1)),
            context=SimpleNamespace(preferences=SimpleNamespace(
                filepaths=SimpleNamespace(use_scripts_auto_execute=False))),
            data=SimpleNamespace(libraries=[reference] if kind == 'library' else [],
                                 images=[reference] if kind == 'image' else []),
            path=SimpleNamespace(abspath=resolver))
        code = 'EXPORT_LINKED_LIBRARY_UNSUPPORTED' if kind == 'library' else 'EXPORT_IMAGE_UNSUPPORTED'
        # Catch reads as well as path probing. A future regression may not
        # replace is_file with another I/O method and still pass this test.
        with patch.object(profile, 'Path', side_effect=AssertionError('filesystem access')):
            with self.assertRaisesRegex(profile.ExportRejected, '^' + code + '$'):
                profile.preflight(bpy)
        resolver.assert_not_called()

    def test_library_filepath_is_never_read(self):
        self.check_dependency('library', UnreadableReference())

    def test_image_filepath_or_source_is_never_read(self):
        self.check_dependency('image', UnreadableReference())

    def test_absolute_unc_relative_and_device_references_all_reject_without_io(self):
        for kind in ('library', 'image'):
            for path in ('//outside/asset', '../outside/asset', r'Z:\outside\asset',
                         r'\\invalid.example\share\asset', r'\\?\UNC\invalid.example\share\asset',
                         r'\\.\PIPE\asset', 'asset:stream', ''):
                with self.subTest(kind=kind, spelling=path):
                    self.check_dependency(kind, SimpleNamespace(filepath=path, source='FILE', packed_file=None))

    def test_packed_generated_and_file_images_share_unsupported_boundary(self):
        for source, packed in (('FILE', None), ('FILE', object()), ('GENERATED', None), ('VIEWER', None)):
            with self.subTest(source=source, packed=packed is not None):
                self.check_dependency('image', SimpleNamespace(source=source, packed_file=packed))

    def test_stale_export_does_not_reach_exporter_or_file_preflight(self):
        for mutation, code in (({'expected_revision': 'sha256:' + '0' * 64}, 'STALE_REVISION'),
                               ({'expected_context': dict(fixture.CONTEXT, active_id='box', selected_ids=['box'])}, 'CONTEXT_DRIFT')):
            owner = fixture.fake_ui()
            owner._export_preflight = Mock(side_effect=AssertionError('stale export preflight'))
            owner._save = Mock(side_effect=AssertionError('stale save'))
            command = fixture.command(operation='export.prepare', payload={'slot': 'export'}, **mutation)
            for execute in (owner._preview, owner._dispatch_checked):
                with self.subTest(method=execute.__name__, code=code), self.assertRaisesRegex(fixture.q.c.Rejected, code):
                    execute(copy.deepcopy(command))
            owner._export_preflight.assert_not_called()
            owner._save.assert_not_called()
            self.assertEqual(owner.bpy.ops.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
