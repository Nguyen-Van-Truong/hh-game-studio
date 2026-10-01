"""Guarded modes keep the accepted validator separate and inspect exact mounts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.godot.test_linux_executor import executor, inspected, write_project, NAME, CID, IMAGE_ENV


class GuardedExecutorTests(unittest.TestCase):
    def test_transitive_and_loaded_runtime_changes_reject_old_binding(self):
        current = executor.gameplay_runtime_source_closure()[1]
        read = executor._read_file
        # Load the trusted CLI helper before simulating a disk change. The
        # admission check must notice even dependencies already in memory.
        executor._cli_jobs()
        for dependency in ('godot-addon/cli_job.py', 'host/core/journal.py',
                           'host/core/redaction.py', 'protocol/__init__.py',
                           'protocol/_rfc8785/__init__.py', 'protocol/_rfc8785/_impl.py'):
            target = executor.STUDIO / dependency

            def changed(path, cap):
                raw = read(path, cap)
                return raw + b'\n# simulated revision\n' if path == target else raw

            with self.subTest(dependency=dependency), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'output'
                with patch.object(executor, '_read_file', side_effect=changed), \
                     patch.object(executor, '_cli') as cli:
                    with self.assertRaisesRegex(executor.ExecutorError, 'SOURCE_CLOSURE_MISMATCH'):
                        executor.run(Path(directory) / 'unused', mode='gameplay-source',
                                     output=output, source_closure_sha256=current)
                    cli.assert_not_called()
                    self.assertFalse(output.exists())

    def test_runtime_source_closure_rejects_invalid_or_stale_binding_before_output(self):
        current = executor.gameplay_runtime_source_closure()[1]
        for supplied in ('0' * 64, '', 'A' * 64, 42, True):
            with self.subTest(supplied=supplied), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'output'
                with patch.object(executor, '_cli') as cli:
                    with self.assertRaisesRegex(executor.ExecutorError, 'SOURCE_CLOSURE'):
                        executor.run(Path(directory) / 'unused', mode='gameplay-source',
                                     output=output, source_closure_sha256=supplied)
                    cli.assert_not_called()
                    self.assertFalse(output.exists())
        with patch.object(executor, '_cli') as cli:
            with self.assertRaisesRegex(executor.ExecutorError, 'SOURCE_CLOSURE_MODE'):
                executor.run(Path('unused'), mode='parse', output=Path('unused-output'),
                             source_closure_sha256=current)
            cli.assert_not_called()

    def test_runtime_source_closure_is_observed_before_and_after_executor_work(self):
        current = executor.gameplay_runtime_source_closure()[1]
        for after in (current, '0' * 64):
            with self.subTest(changed=after != current), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / 'input'
                write_project(project)
                (project / 'project.godot').write_bytes(
                    executor._gameplay_profile().PROJECT_TEMPLATE.encode())
                output = Path(directory) / 'output'
                with patch.object(executor, 'gameplay_runtime_source_closure',
                                  side_effect=[({}, current), ({}, after)]), \
                     patch.object(executor, '_lock',
                                  side_effect=executor.ExecutorError('STOP_BEFORE_DAEMON')), \
                     patch.object(executor, '_cli') as cli:
                    result = executor.run(project, mode='gameplay-source', output=output,
                                          source_closure_sha256=current)
                    cli.assert_not_called()
                self.assertEqual(result['source_closure_sha256'], current)
                self.assertIs(result['source_closure_unchanged'], after == current)
                self.assertEqual(json.loads((output / 'result.json').read_bytes()), result)
                self.assertFalse(result['diagnostic_process_clean'])
                if after != current:
                    self.assertIn('EXECUTOR_SOURCE_CLOSURE_CHANGED', result['errors'])

    def test_gameplay_diagnostic_records_observed_closure_without_a_caller_hash(self):
        current = executor.gameplay_runtime_source_closure()[1]
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'input'
            write_project(project)
            (project / 'project.godot').write_bytes(
                executor._gameplay_profile().PROJECT_TEMPLATE.encode())
            with patch.object(executor, 'gameplay_runtime_source_closure',
                              return_value=({}, current)) as closure, \
                 patch.object(executor, '_lock',
                              side_effect=executor.ExecutorError('STOP_BEFORE_DAEMON')), \
                 patch.object(executor, '_cli') as cli:
                result = executor.run(project, mode='gameplay-source',
                                      output=Path(directory) / 'output')
                cli.assert_not_called()
                self.assertEqual(closure.call_count, 2)
            self.assertEqual(result['source_closure_sha256'], current)
            self.assertIs(result['source_closure_unchanged'], True)
            self.assertFalse(result['diagnostic_process_clean'])

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

    def test_gameplay_input_admits_only_the_bounded_source_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'input'
            project.mkdir(); (project / 'scenes').mkdir(); (project / 'scripts').mkdir()
            (project / 'project.godot').write_bytes(
                executor._gameplay_profile().PROJECT_TEMPLATE.encode())
            (project / 'scenes/fixture.tscn').write_bytes(
                b'[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n')
            (project / 'scripts/fixture_actor.gd').write_bytes(b'extends Node3D\n')
            (project / 'scenes/arena.tscn').write_bytes(
                b'[gd_scene format=3]\n[node name="Arena" type="Node2D"]\n')
            (project / 'scripts/shared.gd').write_bytes(b'extends Node\n')
            values = executor._gameplay_project_bytes(project)
            self.assertIn('scripts/fixture_actor.gd', values)
            self.assertIn('scenes/arena.tscn', values)
            self.assertIn('scripts/shared.gd', values)
            self.assertEqual(set(values), {'project.godot', 'scenes/arena.tscn',
                                           'scenes/fixture.tscn', 'scripts/fixture_actor.gd',
                                           'scripts/shared.gd'})
            profile = executor._gameplay_profile()
            bundle = profile.validate_source_bundle(
                {'scripts/fixture_actor.gd': b'extends Node3D\n',
                 'scripts/unused.gd': b'extends Node3D\n'},
                entrypoint='scripts/fixture_actor.gd')
            self.assertTrue(bundle['dependency_inventory_verified'])
            self.assertFalse(bundle['dependency_closure_verified'])

    def test_gameplay_source_uses_play_phase_and_exact_harness_mount(self):
        command = executor._supervised_command('gameplay-source')
        self.assertIn('/harness/gameplay_sandbox.py', command[-1])
        tool, snapshot = Path('C:/tool'), Path('C:/out/snapshot')
        row = inspected(NAME, CID, 'gameplay-source', tool, snapshot)
        row['Mounts'].append({'Type': 'bind', 'Source': str(snapshot.parent / 'harness'),
                             'Destination': '/harness', 'RW': False, 'Propagation': 'rprivate'})
        executor._validate_inspect(row, name=NAME, container_id=CID, mode='gameplay-source',
                                   tool=tool, snapshot=snapshot, image_environment=IMAGE_ENV)

    def test_invalid_secondary_source_is_rejected_before_docker_or_snapshot(self):
        for extra in ({'scenes/secondary.tscn': b'\xff'},
                      {'scripts/secondary.gd': b'extends Node\x00'},
                      {f'scripts/extra{i}.gd': b'#' * 16384 for i in range(16)},
                      {f'scripts/extra{i}.gd': b'extends Node\n' for i in range(63)}):
            with self.subTest(files=len(extra)), tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / 'input'
                write_project(project)
                profile = executor._gameplay_profile()
                (project / 'project.godot').write_bytes(profile.PROJECT_TEMPLATE.encode())
                for name, raw in extra.items():
                    (project / name).write_bytes(raw)
                output = Path(directory) / 'output'
                with patch.object(executor, '_cli') as cli:
                    with self.assertRaises(profile.GameplaySourceError):
                        executor.run(project, mode='gameplay-source', output=output)
                    cli.assert_not_called()
                    self.assertFalse(output.exists())

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
