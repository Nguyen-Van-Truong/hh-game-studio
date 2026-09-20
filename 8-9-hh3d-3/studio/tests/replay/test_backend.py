"""PreparedPlay lifecycle injections with synthetic stages; never engine proof.

Native launch/preparation/sampling and observation evaluation are replaced.
The real backend, files, immutable bindings and captured-stage verifier run.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import backend
from studio.pipeline.native_job import StageFailed


class HeldNative:
    def __init__(self, failures=0):
        self.failures, self.calls = failures, 0
        self.closed = False

    def close(self):
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise StageFailed('INJECT_CLEANUP_FAILED', cleanup_owner=self)
        self.closed = True


class FakeSampler:
    def __init__(self, output, executable):
        self.output, self.executable = output, executable
        self.identity = {'pid': 1234, 'process_start': 'windows:133000000000000000'}
        self.rows = [{'host_mono_us': 1000, 'rss_bytes': 1024, 'visible_window_handles': ['555']}]
        self.errors, self.close_calls = [], 0
        self.close_failures = 0
        self.thread = threading.Thread(target=lambda: None, name='synthetic-sampler')

    def close(self):
        self.close_calls += 1
        if self.close_failures:
            self.close_failures -= 1
            raise backend.native.ReplayError('REPLAY_SAMPLER_DRAIN')
        if self.thread.ident is not None:
            self.thread.join(1)


class NativeFixture:
    def __init__(self, directory):
        self.studio = Path(directory) / 'studio'
        self.studio.mkdir()
        (self.studio / '.local/reviews').mkdir(parents=True)
        self.release, self.entered = threading.Event(), threading.Event()
        self.release.set()
        self.calls, self.samplers = [], []
        self.mutation = None
        self.import_error = self.runtime_error = None
        self.sampler_error = None
        self.sampler_close_failures = 0
        self.stop_during_runtime = False
        self.postconditions = True
        self.write(self.studio / 'host/replay/synthetic.py', b'# synthetic installed source\n')
        self.write(self.studio / 'contracts/perf-collector.schema.json', b'{}\n')
        self.write(self.studio / 'toolchain.lock.json', {'godot': {
            'gui_executable': 'synthetic-never-executed.exe', 'gui_sha256': 'b' * 64}})
        # sources() now supplies the complete verified installed map; the
        # backend may not silently append freshly computed dependency hashes.
        self.originals = ('toolchain.lock.json', 'host/replay/synthetic.py',
                          'contracts/perf-collector.schema.json')

    @staticmethod
    def write(path, data):
        backend.native.write(path, data)

    def sources(self, _manifest):
        return {name: backend.native.sha((self.studio / name).read_bytes()) for name in self.originals}

    def prepare(self, root, trace, config, inputs):
        project = root / 'project'
        project.mkdir()
        self.write(project / 'project.godot', b'; synthetic fixture, never launched\n')
        self.write(project / 'input/trace.json', trace.raw)
        self.write(project / 'input/fixture.glb', inputs['fixture.glb'])
        self.write(project / 'config/fixture_actor.gd', config)
        (project / 'out').mkdir()
        return project

    def sampler(self, output, executable):
        if self.sampler_error is not None:
            raise self.sampler_error
        result = FakeSampler(output, executable)
        result.close_failures = self.sampler_close_failures
        self.samplers.append(result)
        return result

    def stage(self, argv, *, cwd, output, **kwargs):
        phase = 'import' if '--import' in argv else 'runtime'
        self.calls.append((phase, argv, kwargs))
        if phase == 'import' and self.import_error is not None:
            raise self.import_error
        pid = 1233 if phase == 'import' else 1234
        stdout, stderr = b'', b''
        if phase == 'runtime':
            self.entered.set()
            if not self.release.wait(3):
                raise RuntimeError('synthetic release deadline')
            if self.runtime_error is not None:
                raise self.runtime_error
            if self.stop_during_runtime:
                if not kwargs['stop'].wait(2):
                    raise RuntimeError('synthetic stop deadline')
                raise StageFailed('STAGE_STOPPED')
            binding = json.loads((cwd / 'input/run.json').read_bytes())
            report = {'binding': binding, 'completed': True, 'synthetic_test': True}
            self.write(cwd / 'out/report.json', report)
            marker = {'pid': pid, 'report_sha256': backend.native.sha((cwd / 'out/report.json').read_bytes()),
                      **{key: binding[key] for key in ('run_id', 'command_id', 'runtime_instance_id')}}
            if self.mutation == 'marker':
                marker['report_sha256'] = '0' * 64
            elif self.mutation == 'marker_pid':
                marker['pid'] += 1
            elif self.mutation == 'pid':
                pid += 1
            elif self.mutation == 'source':
                (self.studio / 'host/replay/synthetic.py').write_bytes(b'# drift during run\n')
            elif self.mutation == 'stderr':
                stderr = b'injected native stderr\n'
            stdout = b'HH_GT06_COMPLETE ' + backend.native.encoded(marker)
            if self.mutation == 'log':
                stdout += b'ERROR: injected native failure\n'
        self.write(output / 'stdout.txt', stdout)
        self.write(output / 'stderr.txt', stderr)
        self.write(output / 'process-start.json', {'pid': pid})
        self.write(output / 'process-exit.json', {'pid': pid, 'exit_code': 0})
        capture = {'completed': True, 'natural_tree_exit': True, 'wrapper_exit_code': 0,
            'actual_process_exit': {'pid': pid, 'exit_code': 0}, 'active_before_cleanup': 0,
            'job': {'closed': True, 'zero_observed': True, 'tainted': False, 'handle_retained': False},
            'artifacts': {name: backend.native.sha((output / name).read_bytes()) for name in
                          ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json')}}
        self.write(output / 'capture.json', capture)
        return capture


class PreparedPlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-replay-backend-')
        self.addCleanup(self.temp.cleanup)
        self.fixture = NativeFixture(self.temp.name)
        self.owners = []
        replacements = (
            (backend, 'HELD_BACKENDS', []),
            (backend.native, 'STUDIO', self.fixture.studio),
            (backend.native, 'accepted_inputs', lambda: ({'fixture.glb': b'synthetic-glb'}, {})),
            (backend.native, 'sources', self.fixture.sources),
            (backend.native, 'configuration', lambda speed: b'# synthetic speed ' + speed.encode() + b'\n'),
            (backend.native, 'prepare', self.fixture.prepare),
            (backend.native, 'run_trusted_stage', self.fixture.stage),
            (backend.native, 'Sampler', self.fixture.sampler),
            (backend, 'validate_observation', lambda *_args, **_kwargs: {'all_postconditions': self.fixture.postconditions}),
        )
        for target, name, value in replacements:
            replacement = patch.object(target, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.addCleanup(self.drain)

    def drain(self):
        self.fixture.release.set()
        for owner in self.owners:
            try:
                owner.stop()
                if owner._thread is not None and owner._thread.ident is not None:
                    owner._thread.join(2)
            except (AttributeError, RuntimeError):
                pass

    def prepare(self):
        owner = backend.PreparedPlay.prepare('gt06-synthetic-backend')
        self.owners.append(owner)
        return owner

    def complete(self, owner):
        owner.start()
        self.assertTrue(owner._done.wait(2), 'synthetic backend did not finish')
        if owner._thread.ident is not None:
            owner._thread.join(1)
        return owner.status()

    def test_prepare_has_detached_binding_and_fixed_runtime_configuration(self):
        owner = self.prepare()
        self.assertEqual(owner.status()['phase'], 'PREPARED')
        self.assertEqual([call[0] for call in self.fixture.calls], ['import'])
        binding = owner.binding
        binding['generation'] = 99
        self.assertEqual(owner.binding['generation'], 1)
        self.assertIn('contracts/perf-collector.schema.json', owner.source)
        self.assertEqual((owner.project / 'config/fixture_actor.gd').read_bytes(), b'# synthetic speed 3.0\n')

    def test_stop_before_start_prevents_runtime_launch(self):
        owner = self.prepare()
        status = owner.stop()
        self.assertEqual(status['phase'], 'STOPPED')
        self.assertTrue(status['stopped'])
        with self.assertRaisesRegex(backend.BackendError, 'REPLAY_BACKEND_ALREADY_STARTED_OR_STOPPED'):
            owner.start()
        self.assertEqual([call[0] for call in self.fixture.calls], ['import'])
        self.assertEqual(self.fixture.samplers, [])
        owner.close()
        self.assertTrue(owner._closed)

    def test_second_start_does_not_launch_again(self):
        owner = self.prepare()
        self.complete(owner)
        with self.assertRaisesRegex(backend.BackendError, 'REPLAY_BACKEND_ALREADY_STARTED_OR_STOPPED'):
            owner.start()
        self.assertEqual([call[0] for call in self.fixture.calls], ['import', 'runtime'])

    def test_completed_is_separate_from_stopped_after_completion(self):
        owner = self.prepare()
        completed = self.complete(owner)
        self.assertEqual(completed['phase'], 'COMPLETED')
        self.assertTrue(completed['completed_native'])
        self.assertTrue(completed['historical_inspection_available'])
        stopped = owner.stop()
        self.assertEqual(stopped['phase'], 'STOPPED_AFTER_COMPLETION')
        self.assertTrue(stopped['completed_native'])
        self.assertFalse(stopped['historical_inspection_available'])
        owner.close()

    def test_stop_racing_completed_readback_preserves_history_without_inspection(self):
        owner = self.prepare()
        self.fixture.release.clear()
        owner.start()
        self.assertTrue(self.fixture.entered.wait(1))
        owner.stop()
        self.fixture.release.set()
        self.assertTrue(owner._done.wait(2))
        status = owner.status()
        self.assertEqual(status['phase'], 'STOPPED_AFTER_COMPLETION')
        self.assertTrue(status['completed_native'])
        self.assertFalse(status['historical_inspection_available'])

    def test_native_stage_stop_is_not_claimed_as_completed(self):
        owner = self.prepare()
        self.fixture.stop_during_runtime = True
        owner.start()
        self.assertTrue(self.fixture.entered.wait(1))
        owner.stop()
        self.assertTrue(owner._done.wait(2))
        status = owner.status()
        self.assertEqual((status['phase'], status['error']), ('STOPPED', 'STAGE_STOPPED'))
        self.assertFalse(status['completed_native'])
        self.assertFalse((owner.root / 'capture.json').exists())

    def test_sampler_construction_failure_latches_stop_and_retains_owner(self):
        owner = self.prepare()
        self.fixture.sampler_error = RuntimeError('injected sampler construction')
        with self.assertRaises(Exception) as caught:
            owner.start()
        self.assertTrue(owner.status()['stopped'])
        self.assertEqual(owner.status()['phase'], 'UNKNOWN')
        self.assertIs(getattr(caught.exception, 'cleanup_owner', None), owner)
        self.assertEqual([call[0] for call in self.fixture.calls], ['import'])
        owner.close()

    def test_worker_start_uncertain_latches_stop_and_returns_cleanup_owner(self):
        owner = self.prepare()
        original = threading.Thread.start
        def fail_worker(thread):
            if thread.name == 'hh-gt06-owned-play':
                raise RuntimeError('injected worker startup uncertainty')
            return original(thread)
        with patch.object(threading.Thread, 'start', fail_worker):
            with self.assertRaises(Exception) as caught:
                owner.start()
        self.assertEqual(owner.status()['phase'], 'UNKNOWN')
        self.assertTrue(owner.status()['stopped'])
        self.assertIs(getattr(caught.exception, 'cleanup_owner', None), owner)
        self.assertEqual([call[0] for call in self.fixture.calls], ['import'])
        owner.close()

    def test_sampler_thread_start_failure_attempts_sampler_cleanup(self):
        owner = self.prepare()
        original = threading.Thread.start
        def fail_sampler(thread):
            if thread.name == 'synthetic-sampler':
                original(thread)
                raise RuntimeError('injected sampler thread startup')
            return original(thread)
        with patch.object(threading.Thread, 'start', fail_sampler):
            status = self.complete(owner)
        self.assertEqual(status['phase'], 'UNKNOWN')
        self.assertTrue(status['stopped'])
        self.assertEqual(self.fixture.samplers[0].close_calls, 1)
        self.assertEqual([call[0] for call in self.fixture.calls], ['import'])

    def test_start_timeout_retains_owner_until_actual_drain(self):
        owner = self.prepare()
        self.fixture.release.clear()
        with patch.object(backend.time, 'monotonic', side_effect=[0, 6]):
            with self.assertRaisesRegex(backend.BackendError, 'REPLAY_BACKEND_START_UNKNOWN') as caught:
                owner.start()
        self.assertIs(caught.exception.cleanup_owner, owner)
        self.assertTrue(owner.status()['stopped'])
        self.assertIn(owner, backend.HELD_BACKENDS)
        with self.assertRaisesRegex(backend.BackendError, 'REPLAY_BACKEND_CLEANUP_HELD'):
            backend.PreparedPlay.prepare('gt06-unrelated-run')
        self.fixture.release.set()
        owner.close()
        self.assertNotIn(owner, backend.HELD_BACKENDS)

    def test_prepare_cleanup_owner_can_close_before_binding_exists(self):
        held = HeldNative()
        self.fixture.import_error = StageFailed('STAGE_CLEANUP_HELD', cleanup_owner=held)
        with self.assertRaises(backend.BackendError) as caught:
            self.prepare()
        owner = caught.exception.cleanup_owner
        self.owners.append(owner)
        self.assertIn(owner, backend.HELD_BACKENDS)
        owner.close()
        self.assertTrue(held.closed)
        self.assertNotIn(owner, backend.HELD_BACKENDS)
        self.assertTrue(owner._closed)

    def test_cleanup_failure_retains_owner_and_retry_releases(self):
        owner = self.prepare()
        held = HeldNative(failures=1)
        self.fixture.runtime_error = StageFailed('STAGE_CLEANUP_HELD', cleanup_owner=held)
        status = self.complete(owner)
        self.assertEqual(status['phase'], 'UNKNOWN')
        self.assertTrue(status['stopped'])
        self.assertIn(owner, backend.HELD_BACKENDS)
        with self.assertRaisesRegex(backend.BackendError, 'REPLAY_BACKEND_CLEANUP_HELD'):
            backend.PreparedPlay.prepare('gt06-unrelated-run')
        with self.assertRaises(Exception):
            owner.close()
        self.assertIs(owner._held_native, held)
        self.assertFalse(owner._closed)
        self.assertIn(owner, backend.HELD_BACKENDS)
        owner.close()
        self.assertEqual(held.calls, 2)
        self.assertTrue(held.closed)
        self.assertNotIn(owner, backend.HELD_BACKENDS)

    def test_sampler_cleanup_error_cannot_discard_retained_native_job(self):
        owner = self.prepare()
        held = HeldNative()
        self.fixture.runtime_error = StageFailed('STAGE_CLEANUP_HELD', cleanup_owner=held)
        self.fixture.sampler_close_failures = 1
        status = self.complete(owner)
        self.assertEqual(status['phase'], 'UNKNOWN')
        self.assertTrue(status['stopped'])
        self.assertIn(owner, backend.HELD_BACKENDS)
        owner.close()
        self.assertTrue(held.closed, 'secondary sampler failure must not lose the native cleanup owner')
        self.assertNotIn(owner, backend.HELD_BACKENDS)

    def test_source_drift_rejects_completion(self):
        owner = self.prepare()
        self.fixture.mutation = 'source'
        status = self.complete(owner)
        self.assertEqual((status['phase'], status['error']), ('UNKNOWN', 'REPLAY_BACKEND_SOURCE_CHANGED'))
        self.assertFalse(status['completed_native'])
        self.assertFalse((owner.root / 'capture.json').exists())

    def test_bad_marker_rejects_completion(self):
        owner = self.prepare()
        self.fixture.mutation = 'marker'
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_MARKER')
        self.assertFalse(status['completed_native'])

    def test_bad_marker_pid_rejects_completion(self):
        owner = self.prepare()
        self.fixture.mutation = 'marker_pid'
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_MARKER')
        self.assertFalse(status['completed_native'])

    def test_runtime_exit_pid_must_match_sampler_identity(self):
        owner = self.prepare()
        self.fixture.mutation = 'pid'
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_PID')
        self.assertFalse(status['completed_native'])

    def test_log_error_rejects_even_with_clean_captured_exit(self):
        owner = self.prepare()
        self.fixture.mutation = 'log'
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_LOG')
        self.assertFalse(status['completed_native'])

    def test_stderr_rejects_even_with_clean_captured_exit(self):
        owner = self.prepare()
        self.fixture.mutation = 'stderr'
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_LOG')
        self.assertFalse(status['completed_native'])

    def test_failed_observation_never_creates_completion_capture(self):
        owner = self.prepare()
        self.fixture.postconditions = False
        status = self.complete(owner)
        self.assertEqual(status['error'], 'REPLAY_BACKEND_POSTCONDITION')
        self.assertFalse(status['completed_native'])
        self.assertFalse((owner.root / 'capture.json').exists())


if __name__ == '__main__':
    unittest.main()
