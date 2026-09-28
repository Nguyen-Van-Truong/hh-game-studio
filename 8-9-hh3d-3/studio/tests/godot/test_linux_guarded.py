"""Guarded modes keep the accepted validator separate and inspect exact mounts."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.godot.test_linux_executor import executor, inspected, write_project, NAME, CID, IMAGE_ENV


class GuardedExecutorTests(unittest.TestCase):
    def test_only_guarded_modes_use_the_sandbox_bootstrap(self):
        for mode in ('parse', 'import', 'profile-validate'):
            argv = executor._supervised_command(mode)
            self.assertNotIn('/harness/gameplay_sandbox.py', str(argv))
        for mode in executor.GUARDED_MODES:
            argv = executor._supervised_command(mode)
            phase = mode.removeprefix('guarded-')
            self.assertEqual(argv[-2:], ['/harness/gameplay_sandbox.py', phase])
        for mode in ('guarded-exec', 'guarded-readback', '', None):
            with self.assertRaises(executor.ExecutorError):
                executor._supervised_command(mode)

    def test_guarded_bootstrap_is_pinned_before_any_daemon_call(self):
        self.assertEqual(executor._sha(executor._sandbox_harness()), executor.SANDBOX_BOOTSTRAP_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'input'
            write_project(project)
            (project / 'scripts/fixture_actor.gd').write_bytes(
                b'extends Node3D\nvar ticks: int = 0\n'
                b'func _ready() -> void:\n\tticks += 1\n')
            for mode in executor.GUARDED_MODES:
                with self.subTest(mode=mode), patch.object(executor, '_sandbox_harness',
                        side_effect=executor.ExecutorError('EXECUTOR_SANDBOX_HARNESS_PIN')), \
                        patch.object(executor, '_cli') as cli:
                    with self.assertRaisesRegex(executor.ExecutorError, 'HARNESS_PIN'):
                        executor.run(project, mode=mode, output=Path(directory) / 'output')
                    cli.assert_not_called()
                    self.assertFalse((Path(directory) / 'output').exists())

    def test_gameplay_source_profile_is_pinned_before_daemon_call(self):
        self.assertEqual(executor._sha(executor._read_file(
            executor.STUDIO / 'godot-addon/gameplay_source_profile.py', 65536)),
            executor.GAMEPLAY_PROFILE_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'input'
            write_project(project)
            with patch.object(executor, '_gameplay_profile',
                              side_effect=executor.ExecutorError('EXECUTOR_GAMEPLAY_PROFILE_PIN')), \
                 patch.object(executor, '_cli') as cli:
                with self.assertRaisesRegex(executor.ExecutorError, 'GAMEPLAY_PROFILE_PIN'):
                    executor.run(project, mode='gameplay-source', output=Path(directory) / 'output')
                cli.assert_not_called()
                self.assertFalse((Path(directory) / 'output').exists())

    def test_gameplay_source_uses_play_phase_and_exact_harness_mount(self):
        command = executor._supervised_command('gameplay-source')
        self.assertIn('/harness/gameplay_sandbox.py', command[-1])
        tool, snapshot = Path('C:/tool'), Path('C:/out/snapshot')
        row = inspected(NAME, CID, 'gameplay-source', tool, snapshot)
        row['Mounts'].append({'Type': 'bind', 'Source': str(snapshot.parent / 'harness'),
                             'Destination': '/harness', 'RW': False, 'Propagation': 'rprivate'})
        executor._validate_inspect(row, name=NAME, container_id=CID, mode='gameplay-source',
                                   tool=tool, snapshot=snapshot, image_environment=IMAGE_ENV)

    def test_guarded_inspect_rejects_missing_mutable_foreign_or_unprotected_harness(self):
        tool, snapshot = Path('C:/tool'), Path('C:/out/snapshot')
        for mode in executor.SANDBOX_MODES:
            row = inspected(NAME, CID, mode, tool, snapshot)
            row['Mounts'].append({'Type': 'bind', 'Source': str(snapshot.parent / 'harness'),
                                 'Destination': '/harness', 'RW': False, 'Propagation': 'rprivate'})
            args = dict(name=NAME, container_id=CID, mode=mode, tool=tool,
                        snapshot=snapshot, image_environment=IMAGE_ENV)
            executor._validate_inspect(row, **args)
            for mutate in (lambda r: r['Mounts'].pop(),
                           lambda r: r['Mounts'][-1].update(RW=True),
                           lambda r: r['Mounts'][-1].update(Source='C:/foreign'),
                           lambda r: r['Config'].update(Cmd=executor._supervised_command('parse'))):
                changed = copy.deepcopy(row)
                mutate(changed)
                with self.subTest(mode=mode), self.assertRaises(executor.ExecutorError):
                    executor._validate_inspect(changed, **args)


if __name__ == '__main__':
    unittest.main()
