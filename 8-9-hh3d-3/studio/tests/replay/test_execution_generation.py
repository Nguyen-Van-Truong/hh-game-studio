"""Admission rejects mixed imported/disk generations before native preparation."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import native_runner as native


class ExecutionGenerationTests(unittest.TestCase):
    def test_reject_install_switch_before_validation(self):
        changed = {key: '0' * 64 for key in native._IMPORT_EXECUTION_SELECTION}
        with patch.object(native.execution_installed, 'selection_identity', return_value=changed), \
                patch.object(native.execution_installed, 'load_installed') as load:
            with self.assertRaisesRegex(native.ReplayError, 'REPLAY_IMPORTED_GENERATION_CHANGED'):
                native.sources({'source_files': {}})
            load.assert_not_called()

    def test_reject_install_switch_during_validation(self):
        changed = {key: '0' * 64 for key in native._IMPORT_EXECUTION_SELECTION}
        with patch.object(native.execution_installed, 'selection_identity',
                          return_value=dict(native._IMPORT_EXECUTION_SELECTION)), \
                patch.object(native.execution_installed, 'load_installed', return_value=changed):
            with self.assertRaisesRegex(native.ReplayError, 'REPLAY_IMPORTED_GENERATION_CHANGED'):
                native.sources({'source_files': {}})

    def test_installed_map_and_accepted_assets_are_separate(self):
        inputs, accepted = native.accepted_inputs()
        files = native.sources(accepted)
        self.assertEqual(set(inputs), set(native.consumer.INPUTS))
        self.assertTrue({'godot-addon/publication_transport.py', 'host/replay/execution_binding.py',
                         'host/replay/profile.json', 'contracts/perf-collector.schema.json'} <= files.keys())
        self.assertEqual({name: files[name] for name in native.execution_installed.METADATA_PATHS},
                         native._IMPORT_EXECUTION_SELECTION)
        old_job = accepted['source_files']['8-9-hh3d-3/studio/godot-addon/cli_job.py']
        self.assertNotEqual(files['godot-addon/cli_job.py'], old_job)
        self.assertEqual(native.sha(native.read_regular(native.ACCEPTED_MANIFEST)), native.MANIFEST_SHA)


if __name__ == '__main__':
    unittest.main()
