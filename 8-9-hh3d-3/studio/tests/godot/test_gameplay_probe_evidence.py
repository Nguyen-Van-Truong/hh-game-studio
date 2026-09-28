"""Pure evidence negatives: no Docker, engine, subprocess or admission calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.godot import test_linux_probe_evidence as evidence

probe = evidence.probe


class GameplayProbeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.case = {'expect': 'gameplay_source', 'mode': 'gameplay-source', 'timeout': 20}
        self.result = evidence.LinuxProbeEvidenceTests.clean_result()
        self.result.update(mode='gameplay-source', sandbox_harness_unchanged=True,
            gameplay_source_envelope_checked=True, gameplay_profile_unchanged=True,
            gameplay_profile='hh-godot-gameplay-source-1', diagnostic_process_clean=False,
            errors=['EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN'])
        events = list(probe.GAMEPLAY_PHASE_EVENTS)
        events.insert(-1, 'HH_PROBE_PLAY {"ticks":12,"x":12.0}')
        self.stdout = '\n'.join(events) + '\n'
        self.stderr = probe.GAMEPLAY_STARTUP_ERRORS

    def check(self, stdout=None, stderr=None, result=None):
        return probe.evaluate(self.case, self.result if result is None else result,
            self.stdout if stdout is None else stdout, self.stderr if stderr is None else stderr)

    def test_complete_fixture_is_observed_but_never_public_validation(self):
        row = self.check()
        self.assertTrue(row['fixture_observed'])
        for key in ('public_ack', 'sandbox_acceptance', 'validation_attribution_proven'):
            self.assertIs(row[key], False)
        self.assertIs(self.result['diagnostic_process_clean'], False)

    def test_phase_order_and_exactly_one_guard_per_phase_are_required(self):
        variants = [self.stdout.replace(probe.GUARD_MARKER + '\n', '', 1),
            self.stdout + probe.GUARD_MARKER + '\n',
            self.stdout.replace('HH_GAMEPLAY_PHASE_BEGIN parse\n' + probe.GUARD_MARKER,
                                probe.GUARD_MARKER + '\nHH_GAMEPLAY_PHASE_BEGIN parse'),
            self.stdout.replace('HH_GAMEPLAY_PHASE_END import 0', 'HH_GAMEPLAY_PHASE_END import 1'),
            self.stdout.replace('HH_GAMEPLAY_PHASE_END play 0\n', ''),
            self.stdout + 'HH_GAMEPLAY_PHASE_BEGIN parse\n']
        for output in variants:
            with self.subTest(output=output):
                self.assertFalse(self.check(stdout=output)['fixture_observed'])

    def test_unexplained_diagnostics_in_either_stream_fail_closed(self):
        for diagnostic in ('ERROR: unexpected\n', 'WARNING: unsafe call\n', 'ObjectDB instances leaked\n'):
            self.assertFalse(self.check(stdout=self.stdout + diagnostic)['fixture_observed'])
            self.assertFalse(self.check(stderr=self.stderr + diagnostic)['fixture_observed'])
        for stderr in ('', probe.GUARDED_STARTUP_ERROR, self.stderr + probe.GUARDED_STARTUP_ERROR):
            self.assertFalse(self.check(stderr=stderr)['fixture_observed'])

    def test_missing_or_changed_profile_is_not_a_fixture_pass(self):
        for key in ('gameplay_source_envelope_checked', 'gameplay_profile_unchanged',
                    'sandbox_harness_unchanged', 'gameplay_profile', 'mode'):
            for value in (None, 1, 'other'):
                bad = copy.deepcopy(self.result)
                bad[key] = value
                self.assertFalse(self.check(result=bad)['fixture_observed'])

    def test_watchdog_requires_play_entry_and_no_successful_play_end(self):
        self.case['expect'] = 'watchdog'
        self.result.update(docker_wait_exit=124)
        self.result['command_host']['exit_code'] = 124
        self.result['container_state']['ExitCode'] = 124
        events = probe.GAMEPLAY_PHASE_EVENTS[:-1]
        good = '\n'.join((*events, 'HH_PROBE_BUSY_ENTERED')) + '\n'
        self.assertTrue(self.check(stdout=good)['supervisor_watchdog_observed'])
        self.assertTrue(self.check(stdout=good)['fixture_observed'])
        # Raw -03 had only two startups and timed out during import. Raw -04
        # reached play and emitted all seven explained diagnostic blocks.
        self.assertFalse(self.check(stdout=good,
            stderr=probe.GUARDED_STARTUP_ERROR * 2)['fixture_observed'])
        for output in (good.replace('HH_PROBE_BUSY_ENTERED\n', ''),
                       '\n'.join((*events[:5], 'HH_PROBE_BUSY_ENTERED')) + '\n',
                       good + 'HH_GAMEPLAY_PHASE_END play 0\n',
                       good + 'HH_PROBE_BUSY_ENTERED\n'):
            row = self.check(stdout=output)
            self.assertFalse(row['fixture_observed'])
            self.assertFalse(row['supervisor_watchdog_observed'])

    def test_native_binding_rejects_forged_driver_mount_source_and_identity(self):
        executor = probe.load('gameplay_evidence_test_executor', probe.STUDIO / 'godot-addon/linux_executor.py')
        files = {name: probe.sha(probe.STUDIO / name) for name in (
            'godot-addon/linux_executor.py', 'godot-addon/gameplay_sandbox.py',
            'godot-addon/gameplay_source_profile.py')}
        binding = {'files': files}
        result = {**self.result, 'sandbox_bootstrap_sha256': files['godot-addon/gameplay_sandbox.py'],
            'gameplay_profile_sha256': files['godot-addon/gameplay_source_profile.py'],
            'toolchain': {'gameplay_profile_sha256': files['godot-addon/gameplay_source_profile.py']}}
        with tempfile.TemporaryDirectory(prefix='hh-gameplay-evidence-') as temp:
            root = Path(temp)
            (root / 'harness').mkdir()
            guard = root / 'harness/gameplay_sandbox.py'
            guard.write_bytes((probe.STUDIO / 'godot-addon/gameplay_sandbox.py').read_bytes())
            inspect_file = root / 'created-inspect-stdout.txt'
            row = {'Id': result['container_id'], 'Config': {
                'Entrypoint': ['/usr/local/bin/python3'],
                'Cmd': executor._supervised_command('gameplay-source', 20)},
                'Mounts': [{'Destination': '/harness', 'Source': str(root / 'harness'),
                            'Type': 'bind', 'RW': False, 'Propagation': 'rprivate'}]}

            def verify(inspected=row, actual=result, source=binding):
                inspect_file.write_text(json.dumps([inspected]), encoding='utf-8')
                probe.sandbox_binding(root, self.case, actual, source)

            verify()
            mutations = (
                lambda r: r.update(Id='d' * 64),
                lambda r: r['Config'].update(Entrypoint=['/bin/sh']),
                lambda r: r['Config']['Cmd'].__setitem__(-1, '# ' + r['Config']['Cmd'][-1]),
                lambda r: r['Config']['Cmd'].__setitem__(6, '200s'),
                lambda r: r['Mounts'][0].update(RW=True),
                lambda r: r['Mounts'][0].update(Source='C:/foreign'),
                lambda r: r['Mounts'][0].update(Type='volume'),
                lambda r: r['Mounts'][0].update(Propagation='shared'),
                lambda r: r['Mounts'].append(copy.deepcopy(r['Mounts'][0])),
                lambda r: r.update(Mounts=[]))
            for mutate in mutations:
                bad = copy.deepcopy(row)
                mutate(bad)
                with self.assertRaises(ValueError):
                    verify(inspected=bad)
            for key in ('gameplay_profile_sha256', 'sandbox_bootstrap_sha256'):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    verify(actual={**result, key: '0' * 64})
            with self.assertRaises(ValueError):
                verify(actual={**result, 'toolchain': {}})
            for name in files:
                with self.subTest(path=name), self.assertRaises(ValueError):
                    verify(source={'files': {**files, name: '0' * 64}})
            guard.write_bytes(b'# forged but claimed unchanged\n')
            with self.assertRaises(ValueError):
                verify()


if __name__ == '__main__':
    unittest.main()
