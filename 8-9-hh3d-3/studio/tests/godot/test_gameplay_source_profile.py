"""The gameplay-source admission profile is closed before Docker is touched."""
import importlib.util
from contextlib import redirect_stdout
import io
import json
from pathlib import Path, PurePosixPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('gameplay_source_profile_tests',
                                              STUDIO / 'godot-addon/gameplay_source_profile.py')
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)

VALID = b'''extends Node3D
var ticks: int = 0
func _physics_process(_delta: float) -> void:
\tticks += 1
'''
DEPENDENCY = b'''extends "res://scripts/base.gd"
func _ready() -> void:
\tpass
'''
BASE = b'''extends Node3D
'''
GLB = b'glTF' + (2).to_bytes(4, 'little') + (12).to_bytes(4, 'little')
PNG = b'\x89PNG\r\n\x1a\nfixture'


class GameplaySourceProfileTests(unittest.TestCase):
    def test_valid_typed_source_is_diagnostic_only(self):
        result = profile.validate_source(VALID)
        self.assertEqual(result['profile'], profile.PROFILE)
        self.assertEqual(result['authority'], 0)
        self.assertFalse(result['syntax_and_types_verified'])
        self.assertFalse(result['dependency_closure_verified'])
        self.assertFalse(result['sandbox_acceptance'])

    def test_hostile_source_is_admitted_for_os_observation_not_trusted(self):
        source = b'extends Node3D\nfunc _ready() -> void:\n\tOS.execute("x")\n'
        result = profile.validate_source(source)
        self.assertEqual(result['authority'], 0)
        self.assertFalse(result['syntax_and_types_verified'])

    def test_rejects_bad_bytes_and_limits(self):
        for source in (b'extends Node3D\x00\n', b'\xef\xbb\xbfextends Node3D\n',
                       b'x' * (profile.MAX_BYTES + 1)):
            with self.assertRaises(profile.GameplaySourceError):
                profile.validate_source(source)

    def test_driver_has_fixed_parse_import_play_order(self):
        driver = profile.driver()
        self.assertLess(driver.index('"parse"'), driver.index('"import"'))
        self.assertLess(driver.index('"import"'), driver.index('"play"'))
        self.assertIn('/harness/gameplay_sandbox.py', driver)

    def test_source_bundle_is_bounded_and_hash_bound_but_not_closure_proof(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': DEPENDENCY, 'scripts/base.gd': BASE},
            entrypoint='scripts/main.gd')
        self.assertTrue(result['dependency_inventory_verified'])
        self.assertFalse(result['dependency_closure_verified'])
        self.assertFalse(result['syntax_and_types_verified'])
        self.assertEqual(set(result['files']), {'scripts/base.gd', 'scripts/main.gd'})

    def test_source_bundle_does_not_infer_missing_or_unreferenced_files(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': DEPENDENCY}, entrypoint='scripts/main.gd')
        self.assertFalse(result['dependency_closure_verified'])
        result = profile.validate_source_bundle(
            {'scripts/main.gd': VALID, 'scripts/unused.gd': BASE}, entrypoint='scripts/main.gd')
        self.assertEqual(len(result['files']), 2)

    def test_dependency_closure_rejects_traversal_and_non_bytes(self):
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_SHAPE'):
            profile.validate_source_bundle({'../outside.gd': BASE}, entrypoint='../outside.gd')
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_FILE'):
            profile.validate_source_bundle({'scripts/main.gd': 'text'}, entrypoint='scripts/main.gd')

    def test_source_bundle_rejects_res_alias_and_dot_segments(self):
        for name in ('res://scripts/main.gd', 'scripts/./main.gd', 'scripts/a/../main.gd',
                     'scripts/CON.gd', 'scripts/main.gd:stream', 'scripts/main.gd\x00'):
            with self.assertRaisesRegex(profile.GameplaySourceError,
                                        'GAMEPLAY_DEPENDENCY_SHAPE|GAMEPLAY_DEPENDENCY_FILE'):
                profile.validate_source_bundle({name: BASE}, entrypoint=name)

    def test_source_bundle_rejects_cross_platform_case_aliases(self):
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_DEPENDENCY_ALIAS'):
            profile.validate_source_bundle(
                {'scripts/Main.gd': BASE, 'scripts/main.gd': BASE},
                entrypoint='scripts/Main.gd')

    def test_allowlisted_binary_assets_are_hash_bound_separately(self):
        result = profile.validate_source_bundle(
            {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n',
             'assets/avatar.glb': GLB, 'assets/sprite_sheet.png': PNG},
            entrypoint='scripts/main.gd')
        self.assertEqual(set(result['assets']), {'assets/avatar.glb', 'assets/sprite_sheet.png'})
        self.assertEqual(result['assets']['assets/avatar.glb']['size_bytes'], len(GLB))
        self.assertFalse(result['assets']['assets/avatar.glb']['asset_import_verified'])

    def test_binary_asset_caps_signatures_and_aliases_fail_closed(self):
        base = {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n'}
        cases = (
            ({**base, 'assets/avatar.glb': b'bad'}, 'GAMEPLAY_ASSET_GLB'),
            ({**base, 'assets/sprite_sheet.png': b'bad'}, 'GAMEPLAY_ASSET_PNG'),
            ({**base, 'assets/avatar.glb': GLB, 'assets/Avatar.glb': GLB}, 'GAMEPLAY_DEPENDENCY_FILE|GAMEPLAY_DEPENDENCY_ALIAS'),
            ({**base, 'assets/avatar.glb': b'glTF' + (2).to_bytes(4, 'little') + (13).to_bytes(4, 'little')}, 'GAMEPLAY_ASSET_GLB'),
            ({**base, 'assets/not-allowed.bin': GLB}, 'GAMEPLAY_ASSET_FILE|GAMEPLAY_DEPENDENCY_FILE'),
        )
        for files, code in cases:
            with self.subTest(code=code):
                with self.assertRaisesRegex(profile.GameplaySourceError, code):
                    profile.validate_source_bundle(files, entrypoint='scripts/main.gd')

    def test_asset_total_is_separate_from_source_cap(self):
        base = {'scripts/main.gd': BASE, 'scenes/main.tscn': b'[gd_scene format=3]\n'}
        oversized = b'glTF' + (2).to_bytes(4, 'little') + (profile.MAX_ASSET_BYTES + 12).to_bytes(4, 'little')
        oversized += b'x' * (profile.MAX_ASSET_BYTES - 12)
        with self.assertRaisesRegex(profile.GameplaySourceError, 'GAMEPLAY_ASSET_SIZE|GAMEPLAY_ASSET_GLB'):
            profile.validate_source_bundle({**base, 'assets/avatar.glb': oversized}, entrypoint='scripts/main.gd')


class GameplayDriverResourceTests(unittest.TestCase):
    def execute(self, codes, *, scripts=('scripts/fixture_actor.gd',), unavailable=False,
                memory=b'low 0\nhigh 0\nmax 1\noom 0\noom_kill 0\n', clock_start=1000000):
        """Execute only generated Python, replacing every child and telemetry API."""
        reads, calls = [], []
        class MemoryStream(io.BytesIO):
            def read(self, size=-1):
                reads.append(size)
                return super().read(size)
        class FixedPath(PurePosixPath):
            def rglob(self, pattern):
                self_case.assertEqual((str(self), pattern), ('/project/scripts', '*.gd'))
                return [FixedPath('/project/' + name) for name in scripts]
            def is_file(self):
                return True
            def open(self, mode):
                self_case.assertEqual((str(self), mode), ('/sys/fs/cgroup/memory.events', 'rb'))
                if unavailable:
                    raise OSError('private telemetry path must not enter transcript')
                return MemoryStream(memory)
        self_case = self
        returns = iter(codes)
        def child(argv, **kwargs):
            self.assertEqual(kwargs, {'stdin': -3})  # No new per-child timeout.
            self.assertEqual(argv[:4], ['/usr/local/bin/python3', '-I', '-B', '/harness/gameplay_sandbox.py'])
            calls.append(argv)
            print('HH_GAMEPLAY_OS_GUARD fork=EPERM socket=EPERM')
            return SimpleNamespace(returncode=next(returns))
        telemetry = SimpleNamespace(RUSAGE_CHILDREN=-1, RLIMIT_CPU=0,
            getrusage=Mock(side_effect=[SimpleNamespace(ru_utime=i * .25, ru_stime=i * .5)
                                       for i in range(len(codes) * 2)]),
            getrlimit=Mock(return_value=(10, 10)))
        clock = SimpleNamespace(monotonic_ns=Mock(side_effect=range(clock_start, clock_start + len(codes) * 2 * 1000000, 1000000)))
        if unavailable:
            for function in (telemetry.getrusage, telemetry.getrlimit, clock.monotonic_ns):
                function.side_effect = OSError('private telemetry path must not enter transcript')
        output = io.StringIO()
        exit_code = 0
        with patch.dict(sys.modules, {'subprocess': SimpleNamespace(run=child, DEVNULL=-3),
                'resource': telemetry, 'time': clock, 'pathlib': SimpleNamespace(Path=FixedPath)}), redirect_stdout(output):
            try:
                exec(compile(profile.driver(), '<mocked-gameplay-driver>', 'exec'), {})
            except SystemExit as exited:
                exit_code = exited.code
        raw = output.getvalue()
        prefix = 'HH_GAMEPLAY_CHILD_RESOURCES '
        records = [json.loads(line[len(prefix):]) for line in raw.splitlines() if line.startswith(prefix)]
        return exit_code, raw, records, calls, reads

    def test_import_signal_is_preserved_and_stops_before_play(self):
        exit_code, raw, records, calls, reads = self.execute([0, -9])
        self.assertEqual(exit_code, 45)
        self.assertEqual([argv[4] for argv in calls], ['parse', 'import'])
        self.assertIn('HH_GAMEPLAY_PHASE_END import -9\n', raw)
        self.assertNotIn('HH_GAMEPLAY_PHASE_BEGIN play', raw)
        self.assertEqual([row['returncode'] for row in records], [0, -9])
        self.assertEqual(reads, [4097] * 4)
        for row in records:
            self.assertEqual(row['scope'], 'diagnostic_untrusted_transcript')
            self.assertEqual(row['authority'], 0)
            self.assertEqual(row['cpu_limit_soft_seconds'], 10)
            self.assertEqual(row['cpu_limit_hard_seconds'], 10)
            self.assertEqual(row['elapsed_ns'], 1000000)
            self.assertEqual(row['user_cpu_seconds'], .25)
            self.assertEqual(row['system_cpu_seconds'], .5)
            self.assertEqual(row['memory_events_before']['counts']['oom_kill'], 0)
            self.assertIsNone(row['memory_events_before']['counts']['oom_group_kill'])

    def test_unavailable_or_malformed_telemetry_stays_unknown_without_affecting_exit(self):
        exit_code, raw, rows, calls, _ = self.execute([0, 0, 0], unavailable=True)
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(calls), 3)
        self.assertNotIn('private telemetry path', raw)
        for row in rows:
            for key in ('start_monotonic_us', 'end_monotonic_us', 'elapsed_ns',
                        'cpu_limit_soft_seconds', 'cpu_limit_hard_seconds', 'user_cpu_seconds', 'system_cpu_seconds'):
                self.assertIsNone(row[key])
            for key in ('memory_events_before', 'memory_events_after'):
                self.assertEqual(row[key]['status'], 'unavailable')
                self.assertTrue(all(value is None for value in row[key]['counts'].values()))
        for memory in (b'x' * 4097, b'oom_kill 0\noom_kill 1\n', b'oom_kill -1\n', b'\xff', b''):
            with self.subTest(memory=memory[:40]):
                exit_code, _, rows, _, _ = self.execute([0, -9], memory=memory)
                self.assertEqual(exit_code, 45)
                self.assertTrue(all(row['memory_events_after']['status'] == 'unavailable' for row in rows))

    def test_long_uptime_preserves_elapsed_nanoseconds(self):
        start = 1 << 54
        exit_code, _, rows, _, _ = self.execute([0, 0, 0], clock_start=start)
        self.assertEqual(exit_code, 0)
        for index, row in enumerate(rows):
            self.assertEqual(row['start_monotonic_us'], (start + index * 2000000) // 1000)
            self.assertEqual(row['end_monotonic_us'], (start + index * 2000000 + 1000000) // 1000)
            self.assertEqual(row['elapsed_ns'], 1000000)

    def test_bounded_records_preserve_existing_log_policy(self):
        spec = importlib.util.spec_from_file_location('gameplay_resource_log_policy_tests',
            STUDIO / 'godot-addon/gameplay_log_policy.py')
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)
        scripts = ('scripts/fixture_actor.gd',) + tuple('scripts/module%02d.gd' % i for i in range(63))
        exit_code, raw, rows, calls, reads = self.execute([0] * 66, scripts=scripts)
        self.assertEqual(exit_code, 0)
        self.assertEqual(len(rows), 66)
        self.assertEqual([row['sample_index'] for row in rows], list(range(66)))
        self.assertEqual([call[4] for call in calls], ['parse'] * 64 + ['import', 'play'])
        self.assertEqual(reads, [4097] * 132)
        self.assertLess(len(raw.encode()), policy.MAX_LOG_BYTES)
        stderr = policy.GUARDED_STARTUP_ERROR * 63 + policy.GAMEPLAY_STARTUP_ERRORS
        self.assertTrue(policy.classify(raw.encode(), stderr.encode(), list(scripts))['accepted'])
        _, failed, _, _, _ = self.execute([0, -9])
        self.assertFalse(policy.classify(failed.encode(), policy.GAMEPLAY_STARTUP_ERRORS.encode(),
                                        ['scripts/fixture_actor.gd'])['accepted'])


if __name__ == '__main__':
    unittest.main()
