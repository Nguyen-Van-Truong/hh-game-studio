"""Pure evidence negatives: no Docker, engine, subprocess or admission calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.godot import test_linux_probe_evidence as evidence

probe = evidence.probe


class GameplayProbeEvidenceTests(unittest.TestCase):
    def test_gameplay_busy_fixture_allows_startup_before_supervisor_watchdog(self):
        fixtures = probe.load('gameplay_fixture_catalog',
                              probe.STUDIO / 'tests/godot/linux_probe_fixtures.py').FIXTURES
        self.assertEqual(fixtures['gameplay_source_busy']['expect'], 'watchdog')
        self.assertEqual(fixtures['gameplay_source_busy']['timeout'], 20)
        self.assertLessEqual(fixtures['gameplay_source_busy']['timeout'], 20)

    def test_negative_source_fixtures_cover_syntax_type_and_dependency_failures(self):
        fixtures = probe.load('gameplay_fixture_catalog',
                              probe.STUDIO / 'tests/godot/linux_probe_fixtures.py').FIXTURES
        for name in ('syntax_error', 'type_error', 'dependency_error'):
            with self.subTest(name=name):
                self.assertEqual(fixtures[name]['mode'], 'parse')
                self.assertEqual(fixtures[name]['expect'], 'engine_rejection')
                self.assertNotEqual(fixtures[name]['script'], '')
                guarded = fixtures['gameplay_' + name]
                self.assertEqual(guarded['mode'], 'gameplay-source')
                self.assertEqual(guarded['script'], fixtures[name]['script'])
                self.assertEqual(guarded['expect'], 'engine_rejection')
                self.assertTrue(guarded['parse_errors'])

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
        self.assertFalse(row['asset_import_observed'])
        for key in ('public_ack', 'sandbox_acceptance', 'validation_attribution_proven'):
            self.assertIs(row[key], False)
        self.assertIs(self.result['diagnostic_process_clean'], False)

    def test_asset_fixture_requires_both_native_readback_values(self):
        self.case['asset_readback'] = True
        self.stdout = self.stdout.replace(
            'HH_PROBE_PLAY {"ticks":12,"x":12.0}',
            'HH_PROBE_ASSET_READBACK {"avatar_loaded":true,"sprite_loaded":true}\n'
            'HH_PROBE_PLAY {"ticks":12,"x":12.0}')
        row = self.check()
        self.assertTrue(row['fixture_observed'])
        self.assertTrue(row['asset_import_observed'])
        dirty = copy.deepcopy(self.result)
        dirty['owned_removed'] = False
        self.assertFalse(self.check(result=dirty)['asset_import_observed'])
        self.assertFalse(self.check(stderr=self.stderr + 'ERROR: unexplained\n')['asset_import_observed'])
        for output in (self.stdout.replace('"avatar_loaded":true', '"avatar_loaded":false'),
                       self.stdout.replace('"sprite_loaded":true', '"sprite_loaded":false'),
                       self.stdout.replace('HH_PROBE_ASSET_READBACK {"avatar_loaded":true,"sprite_loaded":true}\n', '')):
            with self.subTest(output=output):
                self.assertFalse(self.check(stdout=output)['fixture_observed'])
                self.assertFalse(self.check(stdout=output)['asset_import_observed'])

    def test_asset_marker_without_asset_fixture_does_not_claim_import(self):
        self.stdout = self.stdout.replace('HH_PROBE_PLAY ',
            'HH_PROBE_ASSET_READBACK {"avatar_loaded":true,"sprite_loaded":true}\nHH_PROBE_PLAY ')
        self.assertFalse(self.check()['asset_import_observed'])

    def test_fixture_state_requires_exact_typed_gameplay_result(self):
        self.case.update(expect='fixture_state', fixture_kind='arena_2d',
                         expected_state={'ticks': 12, 'player_health': 4,
                                         'bot_health': 0, 'projectile_hits': 2,
                                         'pickups': 1, 'round_won': True})
        self.stdout = self.stdout.replace(
            'HH_PROBE_PLAY {"ticks":12,"x":12.0}',
            'HH_PROBE_FIXTURE {"ticks":12,"player_health":4,"bot_health":0,"projectile_hits":2,"pickups":1,"round_won":true}')
        self.assertTrue(self.check()['fixture_observed'])
        for output in (self.stdout.replace('"round_won":true', '"round_won":false'),
                       self.stdout.replace('"round_won":true', '"round_won":1'),
                       self.stdout.replace('"bot_health":0', '"bot_health":false'),
                       self.stdout.replace('HH_PROBE_FIXTURE', 'HH_PROBE_PLAY'),
                       self.stdout + 'HH_PROBE_FIXTURE {"ticks":12}\n'):
            self.assertFalse(self.check(stdout=output)['fixture_observed'])

    def test_physics_fixture_requires_input_and_collision_telemetry(self):
        self.case = probe.load('physics_fixture_catalog',
            probe.STUDIO / 'tests/godot/linux_probe_fixtures.py').FIXTURES['gameplay_arena_physics']
        inputs = [{'tick': t, 'key': k, 'pressed': p} for t, k, p in self.case['input_trace']]
        ticks = (0, 10, 26, 29, 45, 74, 87, 150)
        xs = (32.0, 56.0, 101.0, 110.0, 161.0, 248.0, 281.92, 281.92)
        events = [{'event': label, 'tick': tick, 'x': x, 'y': 173.92,
                   'health': 3 if i == 0 else 4, 'bot_health': 1 if i < 4 else 0,
                   'hits': 0 if i < 4 else 1, 'wall_contacts': 0 if i < 6 else (1 if i == 6 else 30)}
                  for i, (label, tick, x) in enumerate(zip(self.case['event_trace'], ticks, xs))]
        def transcript(trace_inputs, trace_events):
            lines = [*probe.GAMEPLAY_PHASE_EVENTS[:-1]]
            lines += ['HH_FIXTURE_INPUT ' + json.dumps(row) for row in trace_inputs]
            lines += ['HH_FIXTURE_EVENT ' + json.dumps(row) for row in trace_events]
            lines += ['HH_PROBE_FIXTURE ' + json.dumps(self.case['expected_state']),
                      probe.GAMEPLAY_PHASE_EVENTS[-1]]
            return '\n'.join(lines) + '\n'
        self.assertTrue(self.check(stdout=transcript(inputs, events))['fixture_observed'])
        bad_events = copy.deepcopy(events)
        bad_events[-1]['wall_contacts'] = 0
        early = copy.deepcopy(events)
        early[-1]['tick'] = 4
        wrong_body = copy.deepcopy(events)
        wrong_body[-2]['x'] = 100.0
        wrong_input_tick = copy.deepcopy(events)
        wrong_input_tick[2]['tick'] = 25
        bad_input = copy.deepcopy(inputs)
        bad_input[-1]['pressed'] = 0
        for trace in (transcript([], events), transcript(bad_input, events),
                      transcript(inputs, events[:-1]), transcript(inputs, events + [events[-1]]),
                      transcript(inputs, bad_events), transcript(inputs, early),
                      transcript(inputs, wrong_body), transcript(inputs, wrong_input_tick)):
            self.assertFalse(self.check(stdout=trace)['fixture_observed'])

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

    def rejection(self):
        self.case = {'expect': 'engine_rejection', 'mode': 'gameplay-source', 'timeout': 20,
                     'parse_errors': ('Expected parameter name.',)}
        self.result['docker_wait_exit'] = 45
        self.result['command_host']['exit_code'] = 45
        self.result['container_state']['ExitCode'] = 45
        self.stdout = ('HH_GAMEPLAY_PHASE_BEGIN parse\n' + probe.GUARD_MARKER
                       + '\nHH_GAMEPLAY_PHASE_END parse 1\n')
        self.stderr = (probe.GUARDED_STARTUP_ERROR
            + 'SCRIPT ERROR: Parse Error: Expected parameter name.\n'
            '          at: GDScript::reload (res://scripts/fixture_actor.gd:2)\n'
            'ERROR: Failed to load script "res://scripts/fixture_actor.gd" with error "Parse error".\n'
            '   at: load (modules/gdscript/gdscript_resource_format.cpp:46)\n')

    def test_parse_rejection_requires_guard_and_no_later_phase_or_callback(self):
        self.rejection()
        row = self.check()
        self.assertTrue(row['fixture_observed'])
        for key in ('public_ack', 'sandbox_acceptance', 'validation_attribution_proven'):
            self.assertIs(row[key], False)
        for output in (self.stdout.replace(probe.GUARD_MARKER + '\n', ''),
                       self.stdout.replace('parse 1', 'parse 0'),
                       self.stdout + 'HH_GAMEPLAY_PHASE_BEGIN import\n',
                       self.stdout + 'HH_GAMEPLAY_PHASE_BEGIN play\n',
                       self.stdout + 'HH_PROBE_PLAY {"ticks":12,"x":12}\n',
                       self.stdout + 'HH_PROBE_BUSY_ENTERED\n'):
            self.assertFalse(self.check(stdout=output)['fixture_observed'])

    def test_parse_rejection_requires_exact_reason_and_actual_parent_exit(self):
        self.rejection()
        for stderr in ('', self.stderr.replace('Expected parameter name.', 'unrelated failure'),
                       self.stderr + 'WARNING: extra\n', self.stderr + 'ERROR: extra\n',
                       self.stderr + 'ObjectDB instances leaked\n'):
            self.assertFalse(self.check(stderr=stderr)['fixture_observed'])
        for code in (0, 1, 124, 137, 139, None, True):
            bad = copy.deepcopy(self.result)
            bad['command_host']['exit_code'] = bad['container_state']['ExitCode'] = code
            bad['docker_wait_exit'] = code
            self.assertFalse(self.check(result=bad)['fixture_observed'])

    def test_secondary_rejection_requires_its_direct_parse_before_any_import(self):
        self.rejection()
        self.case.update(extra_files={'scripts/unused.gd': 'bad source'},
                         parse_error_path='scripts/unused.gd')
        self.stdout = ('HH_GAMEPLAY_PHASE_BEGIN parse\n' + probe.GUARD_MARKER + '\n'
            'HH_GAMEPLAY_MODULE_BEGIN scripts/unused.gd\n' + probe.GUARD_MARKER + '\n'
            'HH_GAMEPLAY_MODULE_END scripts/unused.gd 1\nHH_GAMEPLAY_PHASE_END parse 1\n')
        self.stderr = probe.GUARDED_STARTUP_ERROR + self.stderr.replace(
            'scripts/fixture_actor.gd', 'scripts/unused.gd')
        self.assertTrue(self.check()['fixture_observed'])
        for output in (self.stdout.replace('MODULE_END scripts/unused.gd 1',
                                          'MODULE_END scripts/unused.gd 0'),
                       self.stdout.replace('MODULE_BEGIN scripts/unused.gd',
                                           'MODULE_BEGIN scripts/other.gd'),
                       self.stdout + 'HH_GAMEPLAY_PHASE_BEGIN import\n'):
            self.assertFalse(self.check(stdout=output)['fixture_observed'])
        self.assertFalse(self.check(stderr=self.stderr.replace(
            'scripts/unused.gd', 'scripts/fixture_actor.gd'))['fixture_observed'])
        for mutate in (lambda r: r['command_host'].update(timed_out=True),
                       lambda r: r['command_host'].update(stream_cap_exceeded=True),
                       lambda r: r.update(owned_removed=False),
                       lambda r: r['command_host']['job_owner'].update(handle_retained=True)):
            bad = copy.deepcopy(self.result)
            mutate(bad)
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
            'tool_mount_source': 'C:/tool',
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
                'HostConfig': {'Tmpfs': dict(executor.TMPFS)},
                'Mounts': [
                    {'Destination': '/tool', 'Source': 'C:/tool',
                     'Type': 'bind', 'RW': False, 'Propagation': 'rprivate'},
                    {'Destination': '/project', 'Source': str(root / 'snapshot'),
                     'Type': 'bind', 'RW': False, 'Propagation': 'rprivate'},
                    {'Destination': '/harness', 'Source': str(root / 'harness'),
                     'Type': 'bind', 'RW': False, 'Propagation': 'rprivate'},
                ]}

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
