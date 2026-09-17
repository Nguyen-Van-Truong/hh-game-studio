"""Inert publication/export deadline boundaries; no native owners or engines."""
import hashlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender import deadline, publication_owner as publication, export_job
from studio.host.blender.publication_owner import BlenderPublicationOwner
from studio.host.blender.publication_state import PublicationError
from studio.host.blender.ui_host import HostError
from studio.host.core.custody import identity_from
from studio.protocol.core import canonical_bytes, parse_json
from test_publication import descriptor, events, replay


class Clock:
    def __init__(self):
        self.wall = 1000.0
        self.mono = 20.0

    def expire(self):
        self.wall = 1001.0


class MemoryPublication(BlenderPublicationOwner):
    """Use the real publication reducer with inert storage and native doubles."""
    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.trace = []
        self.hooks = {}
        self._state = replay(events()[:1])
        self._readonly = False
        self.host = SimpleNamespace(_deadline=200.0, _session='a' * 32, _source={'fixture.py': 'b' * 64}, _stopped=False)
        self.lease = SimpleNamespace(fencing_epoch=1, expires_ms=1005000)
        self.snapshot = {'objects': []}
        self.after = {'snapshot': self.snapshot, 'revision': publication.queue.c.digest(self.snapshot),
                      'context': {'mode': 'OBJECT', 'active_id': None, 'selected_ids': []}}
        self.request = {'schema': publication.model.SCHEMA, 'command_id': 'publish',
                        'expected_revision': self.after['revision'], 'expected_context': self.after['context']}
        self.prepared = {'after': self.after, 'artifact': {'sha256': hashlib.sha256(b'blend').hexdigest()}}
        self.export = {'completed': True, 'snapshot_geometry_bound': True,
                       'artifact': {'sha256': hashlib.sha256(b'glb').hexdigest()},
                       'native': {'snapshot': self.snapshot, 'scene_revision': self.after['revision'], 'profile': {}}}
        self.writes = {}
        self.files = SimpleNamespace(root=SimpleNamespace(iterdir=lambda: [SimpleNamespace(name='.writer')]),
            check_mutation_available=lambda: self.step('namespace'), create_new=self.create_file,
            read=lambda name: self.writes[name], confirm_barrier=lambda *args: self.step('barrier'))
        self.count = 0
        self.job_options = None

    def step(self, label):
        self.trace.append(label)
        if label in self.hooks:
            self.hooks[label]()

    def _refresh(self):
        return self._state

    def _authorize(self, lease):
        self.step('authorize')
        publication.need(not self._held and not self._stop.is_set(), 'PUBLICATION_READONLY_OR_HELD')
        assert lease is self.lease

    def _append(self, kind, **fields):
        self._state = publication.model.reduce(self._state, dict(schema=publication.model.SCHEMA, kind=kind, **fields))
        self.step('append:' + kind)

    def _native(self, key, operation, lease, request=None, **options):
        self.step('native:' + operation)
        self.native_options.append(options)
        return {'state': 'COMPLETED', 'result': self.prepared if operation == 'export.prepare' else self.after}

    def _owned_bytes(self, path, expected):
        self.step('capture:' + path.name)
        return (b'blend' if path.name == 'input.blend' else b'glb'), descriptor(9)['identity']

    def _put(self, name, raw):
        self.step('put:' + name)
        self.count += 1
        return descriptor(self.count)

    def _read_bundle(self, staged):
        self.step('read-bundle')

    def create_file(self, name, raw):
        self.step('create:' + name)
        version = SimpleNamespace(identity=identity_from(dict(descriptor(8)['identity'], size=len(raw))),
                                  sha256=hashlib.sha256(raw).hexdigest())
        self.writes[name] = (version, raw)
        return version

    def job(self, host, prepared, **options):
        self.step('export:construct')
        self.job_options = options
        def run():
            self.step('export:run')
            if 'phase_guard' in options:
                options['phase_guard']()
            return self.export
        return SimpleNamespace(directory=Path('inert/export'), run=run)


class PublicationDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.enterContext(patch.object(deadline.time, 'time', lambda: self.clock.wall))
        self.enterContext(patch.object(deadline.time, 'monotonic', lambda: self.clock.mono))
        self.owner = MemoryPublication(self.clock)
        self.owner.native_options = []
        self.enterContext(patch.object(publication, 'ExportJob', self.owner.job))
        self.enterContext(patch.object(publication, 'inspect_glb', return_value={}))
        self.enterContext(patch.object(publication, 'bind_snapshot'))

    def publish(self, **options):
        return self.owner.publish(self.owner.request, self.owner.lease, **options)

    def test_fresh_malformed_deadline_has_no_intent_or_effect(self):
        for value in (False, True, 0, -1, 2**53, 1.5, '1001000', {}, []):
            with self.subTest(value=value), self.assertRaisesRegex(deadline.DeadlineError, 'ABSOLUTE_DEADLINE_LIMIT'):
                self.publish(deadline_ms=value)
            self.assertEqual(self.owner.trace, [])
            self.assertFalse(self.owner._held)

    def test_boundary_expired_before_admission_has_no_intent(self):
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            self.publish(deadline_ms=1000000)
        self.assertEqual(self.owner.trace, [])
        self.assertFalse(self.owner._held)

    def test_native_owner_horizon_also_bounds_admission(self):
        self.owner.host._deadline = self.clock.mono
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            self.publish(deadline_ms=1001000)
        self.assertEqual(self.owner.trace, [])

    def test_deadline_consumed_by_namespace_check_still_precedes_intent(self):
        self.owner.hooks['namespace'] = self.clock.expire
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            self.publish(deadline_ms=1001000)
        self.assertNotIn('append:INTENT', self.owner.trace)
        self.assertFalse(self.owner._held)

    def test_history_precedes_new_invalid_expired_guard_and_lease(self):
        for state in (replay(events()), replay(events()[:2])):
            owner = BlenderPublicationOwner()
            owner._refresh = Mock(return_value=state)
            owner._authorize = Mock(side_effect=AssertionError('historical receipt must not read fresh authority'))
            expected = owner.lookup_bytes('publish')
            for value in (True, 1, 2**53):
                self.assertEqual(owner.publish(state['intent']['request'], None, deadline_ms=value,
                                               phase_guard=object()), expected)
            owner._authorize.assert_not_called()

    def test_changed_historical_request_remains_conflict_before_deadline(self):
        owner = BlenderPublicationOwner()
        owner._refresh = Mock(return_value=replay(events()))
        request = dict(events()[1]['request'], expected_revision='sha256:' + '2' * 64)
        with self.assertRaisesRegex(PublicationError, 'COMMAND_CONFLICT'):
            owner.publish(request, None, deadline_ms=1)
        self.assertFalse(owner._held)

    def test_valid_publication_passes_exact_deadline_and_guard_to_export(self):
        guard = Mock()
        result = parse_json(self.publish(deadline_ms=1001000, phase_guard=guard))
        self.assertEqual(result['status'], 'COMMITTED')
        self.assertEqual(self.owner.native_options, [{'deadline_ms': 1001000}] * 2)
        self.assertEqual(self.owner.job_options['deadline_ms'], 1001000)
        self.assertTrue(callable(self.owner.job_options['phase_guard']))
        self.assertGreater(guard.call_count, 5)
        self.assertEqual(self.owner.trace.count('create:active.json'), 1)

    def test_optional_absent_deadline_keeps_legacy_export_constructor(self):
        self.assertEqual(parse_json(self.publish())['status'], 'COMMITTED')
        self.assertEqual(self.owner.job_options, {})

    def test_exact_deadline_is_forwarded_to_native_host_without_schema_change(self):
        owner = BlenderPublicationOwner()
        owner.host = Mock()
        lease = SimpleNamespace(fencing_epoch=3, expires_ms=2000000)
        owner._state = {'config': {'publication_profile': 'export.publish'}}
        owner._native('prepare', 'export.prepare', lease, self.owner.request, deadline_ms=1001000)
        command = owner.host.execute.call_args.args[0]
        self.assertNotIn('deadline_ms', command)
        self.assertEqual(owner.host.execute.call_args.kwargs,
                         {'lease': {'fencing_epoch': 3, 'expires_ms': 2000000}, 'deadline_ms': 1001000})
        owner._native('inspect', 'scene.inspect', lease)
        self.assertNotIn('deadline_ms', owner.host.execute.call_args.kwargs)

    def test_post_intent_phase_expiry_never_activates_or_fabricates_terminal(self):
        boundaries = ('append:INTENT', 'native:export.prepare', 'export:run', 'capture:input.blend',
                      'native:scene.inspect', 'put:checkpoint.blend', 'put:scene.glb',
                      'put:manifest.json', 'append:STAGED', 'read-bundle', 'append:SELECTING')
        for boundary in boundaries:
            with self.subTest(boundary=boundary):
                self.clock.wall = 1000
                self.owner = MemoryPublication(self.clock)
                self.owner.native_options = []
                self.owner.hooks[boundary] = self.clock.expire
                with patch.object(publication, 'ExportJob', self.owner.job):
                    with self.assertRaisesRegex(PublicationError, 'OUTCOME_UNKNOWN') as caught:
                        self.publish(deadline_ms=1001000)
                self.assertTrue(caught.exception.outcome_unknown)
                self.assertTrue(self.owner._held)
                self.assertNotIn('create:active.json', self.owner.trace)
                self.assertNotIn('append:TERMINAL', self.owner.trace)
                self.assertEqual(parse_json(self.owner.lookup_bytes('publish'))['status'], 'UNKNOWN')

    def test_expiry_during_selector_write_retains_unknown_without_rollback(self):
        self.owner.hooks['create:active.json'] = self.clock.expire
        with self.assertRaisesRegex(PublicationError, 'OUTCOME_UNKNOWN'):
            self.publish(deadline_ms=1001000)
        self.assertIn('active.json', self.owner.writes)
        self.assertEqual(self.owner._state['phase'], 'SELECTING')
        self.assertNotIn('append:TERMINAL', self.owner.trace)

    def test_original_monotonic_budget_survives_wall_rollback_and_child_start(self):
        def rollback():
            self.clock.wall = 900
            self.clock.mono = 21
        self.owner.hooks['export:run'] = rollback
        with self.assertRaisesRegex(PublicationError, 'OUTCOME_UNKNOWN') as caught:
            self.publish(deadline_ms=1001000)
        self.assertIsInstance(caught.exception.__cause__, deadline.DeadlineError)
        self.assertNotIn('create:active.json', self.owner.trace)

    def test_phase_guard_is_additional_authority_and_revocation_holds_intent(self):
        denied = False
        def guard():
            if denied:
                raise ValueError('revoked')
        def revoke():
            nonlocal denied
            denied = True
        self.owner.hooks['append:SELECTING'] = revoke
        with self.assertRaisesRegex(PublicationError, 'OUTCOME_UNKNOWN'):
            self.publish(deadline_ms=1001000, phase_guard=guard)
        self.assertGreater(self.owner.trace.count('authorize'), 5)
        self.assertNotIn('create:active.json', self.owner.trace)

    def test_rejected_guard_before_intent_has_no_effect(self):
        with self.assertRaisesRegex(ValueError, 'revoked'):
            self.publish(deadline_ms=1001000, phase_guard=Mock(side_effect=ValueError('revoked')))
        self.assertEqual(self.owner.trace, ['authorize'])
        self.assertFalse(self.owner._held)

    def test_stop_during_export_constructor_is_seen_before_export_effect(self):
        self.owner.hooks['export:construct'] = self.owner._stop.set
        with self.assertRaisesRegex(PublicationError, 'OUTCOME_UNKNOWN'):
            self.publish(deadline_ms=1001000)
        self.assertIsNotNone(self.owner._job)
        self.assertNotIn('capture:input.blend', self.owner.trace)
        self.assertNotIn('create:active.json', self.owner.trace)

    def test_stop_arriving_in_phase_guard_still_prevents_intent(self):
        with self.assertRaisesRegex(PublicationError, 'READONLY_OR_HELD'):
            self.publish(deadline_ms=1001000, phase_guard=self.owner._stop.set)
        self.assertNotIn('append:INTENT', self.owner.trace)
        self.assertFalse(self.owner._held)


class InertApi:
    def __init__(self, raw):
        self.raw = raw
        self.directories = []
    def mkdir(self, path):
        self.directories.append(path)
        path.mkdir()
    def open(self, path): return object()
    def inspect(self, handle, path): return ('same', len(self.raw))
    def read(self, handle, limit): return self.raw
    def close(self, handle): pass


class InertProcess:
    def __init__(self, polls=(0,)):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO()
        self.stderr = io.BytesIO()
        self.polls = iter(polls)
        self.returncode = 0
        self.gate = self.stdin
    def poll(self): return next(self.polls, 0)


class InertThread:
    ident = 1
    def start(self): pass
    def join(self, timeout): pass
    def is_alive(self): return False


class ExportDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.enterContext(patch.object(deadline.time, 'time', lambda: self.clock.wall))
        self.enterContext(patch.object(deadline.time, 'monotonic', lambda: self.clock.mono))
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='hh-publication-deadline-'))
        self.api = InertApi(b'blend')
        self.host = SimpleNamespace(directory=Path(self.temp), project=Path(self.temp), _api=self.api,
                                    _deadline=100.0, _stopped=False, _check_project=lambda: None,
                                    _binary=Path('inert-blender.exe'), _source={'fixture.py': 'b' * 64})
        self.prepared = {'artifact': {'name': 'export.blend', 'size_bytes': 5,
                                     'sha256': hashlib.sha256(b'blend').hexdigest()},
                         'after': {'snapshot': {'objects': []}, 'revision': 'sha256:' + '0' * 64}}
        self.process = InertProcess()
        self.popen = self.enterContext(patch.object(export_job.subprocess, 'Popen', return_value=self.process))
        from studio.host.blender import ui_host
        self.native_job = SimpleNamespace(snapshot=lambda: {'closed': True})
        self.enterContext(patch.object(ui_host.cli_job, 'create', return_value=self.native_job))
        self.configure = self.enterContext(patch.object(export_job, 'configure_limits', return_value={}))
        self.enterContext(patch.object(export_job.threading, 'Thread', side_effect=lambda **options: InertThread()))
        self.inspect_glb = self.enterContext(patch.object(export_job, 'inspect_glb', return_value={
            'sha256': 'a' * 64, 'size_bytes': 3, 'objects': 0}))
        self.enterContext(patch.object(export_job, 'bind_snapshot'))
        self.enterContext(patch.object(export_job.time, 'sleep'))

    def job(self, **options):
        value = export_job.ExportJob(self.host, self.prepared, **options)
        value._cleanup = Mock(return_value={'job': {'closed': True}, 'wrapper_exit_code': 0,
                                            'actual_process_exit': {'exit_code': 0}})
        value._threads = []
        # No thread runs: output is an inert captured result for readback checks.
        self.native = {'native_finished': True, 'context_unchanged': True, 'public_ack': False,
                       'snapshot': self.prepared['after']['snapshot'], 'scene_revision': self.prepared['after']['revision'],
                       'input_sha256': self.prepared['artifact']['sha256'], 'output_sha256': 'a' * 64,
                       'output_size_bytes': 3}
        (value.directory / 'result.json').write_bytes(canonical_bytes(self.native))
        (value.directory / 'output.glb').write_bytes(b'glb')
        return value

    def test_invalid_or_expired_constructor_does_not_create_directory(self):
        for value in (True, 0, 2**53, '1001000', 1000000):
            with self.subTest(value=value), self.assertRaises(deadline.DeadlineError):
                export_job.ExportJob(self.host, self.prepared, deadline_ms=value)
        self.assertEqual(self.api.directories, [])
        self.popen.assert_not_called()

    def test_delayed_run_cannot_renew_original_monotonic_budget(self):
        job = self.job(deadline_ms=1001000)
        self.clock.wall = 900
        self.clock.mono = 21
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.popen.assert_not_called()
        job._cleanup.assert_called_once()
        self.assertTrue(job.done.is_set())

    def test_host_horizon_bounds_export(self):
        self.host._deadline = 20.25
        job = self.job(deadline_ms=1001000)
        self.clock.mono = 20.25
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.popen.assert_not_called()

    def test_expiry_during_input_read_prevents_wrapper_launch(self):
        job = self.job(deadline_ms=1001000)
        self.host._check_project = self.clock.expire
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.popen.assert_not_called()

    def test_valid_export_completes_once_and_rechecks_guard(self):
        guard = Mock()
        job = self.job(deadline_ms=1001000, phase_guard=guard)
        report = job.run()
        self.assertTrue(report['completed'])
        self.assertTrue(report['snapshot_geometry_bound'])
        self.assertGreaterEqual(guard.call_count, 6)
        self.popen.assert_called_once()
        job._cleanup.assert_called_once()
        with self.assertRaisesRegex(HostError, 'RUN_ALREADY_STARTED'):
            job.run()
        self.popen.assert_called_once()

    def test_expiry_during_output_preflight_never_reports_completed(self):
        job = self.job(deadline_ms=1001000)
        def expired(raw):
            self.clock.expire()
            return {'sha256': 'a' * 64, 'size_bytes': 3, 'objects': 0}
        self.inspect_glb.side_effect = expired
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.assertFalse(parse_json((job.directory / 'host-result.json').read_bytes())['completed'])

    def test_expiry_during_cleanup_cannot_return_late_completion(self):
        job = self.job(deadline_ms=1001000)
        def cleanup():
            self.clock.expire()
            return {'job': {'closed': True}, 'wrapper_exit_code': 0, 'actual_process_exit': {'exit_code': 0}}
        job._cleanup.side_effect = cleanup
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        report = parse_json((job.directory / 'host-result.json').read_bytes())
        self.assertFalse(report['completed'])
        self.assertEqual(report['status'], 'EXPORT_COMPLETION_EXPIRED_OR_REVOKED')
        self.assertTrue(job.done.is_set())

    def test_legacy_export_omits_absolute_budget(self):
        job = self.job()
        self.clock.expire()
        self.assertTrue(job.run()['completed'])

    def test_expiry_during_limits_blocks_gate_and_retains_cleanup_owner(self):
        job = self.job(deadline_ms=1001000)
        self.configure.side_effect = lambda native: self.clock.expire() or {}
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.assertEqual(self.process.gate.getvalue(), b'')
        self.assertIs(job._job, self.native_job)
        job._cleanup.assert_called_once()

    def test_expiry_after_wrapper_creation_blocks_gate(self):
        job = self.job(deadline_ms=1001000)
        def created(*args, **kwargs):
            self.clock.expire()
            return self.process
        self.popen.side_effect = created
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.assertEqual(self.process.gate.getvalue(), b'')

    def test_poll_rechecks_original_absolute_deadline(self):
        job = self.job(deadline_ms=1001000)
        def poll():
            self.clock.expire()
            return None
        self.process.poll = poll
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        job._cleanup.assert_called_once()

    def test_completed_process_after_deadline_is_not_completed_export(self):
        job = self.job(deadline_ms=1001000)
        def poll():
            self.clock.expire()
            return 0
        self.process.poll = poll
        with self.assertRaisesRegex(deadline.DeadlineError, 'DEADLINE_EXPIRED'):
            job.run()
        self.assertFalse(parse_json((job.directory / 'host-result.json').read_bytes())['completed'])

    def test_guard_is_rechecked_before_gate_and_denial_closes_owned_wrapper(self):
        allowed = True
        def guard():
            if not allowed:
                raise ValueError('revoked')
        def revoke(native):
            nonlocal allowed
            allowed = False
            return {}
        job = self.job(deadline_ms=1001000, phase_guard=guard)
        self.configure.side_effect = revoke
        with self.assertRaisesRegex(ValueError, 'revoked'):
            job.run()
        self.assertEqual(self.process.gate.getvalue(), b'')
        job._cleanup.assert_called_once()

    def test_stop_remains_before_deadline_and_guard(self):
        guard = Mock()
        job = self.job(deadline_ms=1001000, phase_guard=guard)
        job.request_stop()
        self.clock.expire()
        with self.assertRaisesRegex(HostError, 'EXPORT_STOPPED'):
            job.run()
        guard.assert_not_called()
        self.popen.assert_not_called()

    def test_stop_during_constructor_directory_creation_never_launches_child(self):
        original = self.api.mkdir
        def stopped(path):
            original(path)
            self.host._stopped = True
        self.api.mkdir = stopped
        job = self.job(deadline_ms=1001000)
        with self.assertRaisesRegex(HostError, 'EXPORT_STOPPED'):
            job.run()
        self.popen.assert_not_called()
        job._cleanup.assert_called_once()

    def test_stop_arriving_in_phase_guard_never_launches_child(self):
        def stop():
            self.host._stopped = True
        job = self.job(deadline_ms=1001000, phase_guard=stop)
        with self.assertRaisesRegex(HostError, 'EXPORT_STOPPED'):
            job.run()
        self.popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
