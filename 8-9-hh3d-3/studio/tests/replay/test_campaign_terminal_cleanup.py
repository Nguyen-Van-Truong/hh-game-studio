"""Inert child-finally regressions. No engines, HTTP, or real native handles."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_commands import CommandError, CommandProducer
from studio.tests.replay.benchmark_job import BenchmarkJobError
from studio.host.replay.process_probe import ProcessProbe, ProbeError


class InertThread:
    def __init__(self, events, join_error=None):
        self.events, self.join_error, self.ident, self.alive = events, join_error, None, False

    def start(self):
        self.ident, self.alive = 1, True

    def join(self, _timeout):
        self.events.append('heartbeat_join')
        if self.join_error is not None:
            raise self.join_error
        self.alive = False

    def is_alive(self):
        return self.alive


class InertProbe(ProcessProbe):
    def __init__(self, events, role, error=None):
        self.events, self.role, self.error = events, role, error
        self.handle, self.close_uncertain = object(), False
        self.pid, self.process_start = 5900, 'windows:5900'

    def close(self):
        self.events.append(self.role + '_close')
        if self.error is not None:
            self.close_uncertain = True
            self.error.cleanup_owner = self
            raise self.error
        self.handle = None


class InertOwner(campaign.BenchmarkProcess):
    def __init__(self, events, error=None):
        self.events, self.error, self.closed = events, error, False
        self.process, self.threads = SimpleNamespace(pid=900, returncode=2), []
        self.job = SimpleNamespace(snapshot=lambda: {'closed': self.closed,
            'zero_observed': self.closed, 'handle_retained': not self.closed,
            'active_count': 0 if self.closed else None, 'close_uncertain': False})

    def close(self):
        self.events.append('editor_owner_close')
        if self.error is not None:
            self.error.cleanup_owner = self
            raise self.error
        self.closed = True

    def process_handle_snapshot(self):
        return {'required': True, 'closed': self.closed, 'handle_retained': not self.closed,
                'close_uncertain': False}


class InertProducer(CommandProducer):
    def __init__(self, events, error=None):
        self.events, self.close_error, self.closed, self.failed = events, error, False, False
        self.identity = {'pid': 123, 'process_start': 'windows:123'}
        self.host = SimpleNamespace(_stopped=campaign.threading.Event(),
            _closing=campaign.threading.Event(), _threads=[],
            _main=SimpleNamespace(socket=SimpleNamespace(fileno=lambda: -1 if self.closed else 1)),
            _control=SimpleNamespace(socket=SimpleNamespace(fileno=lambda: -1 if self.closed else 2)))
        self.observer = SimpleNamespace(probe=InertProbe(events, 'host_probe'))
        self.journal = SimpleNamespace(_cache_closed=False,
            _index_store=SimpleNamespace(_db=object(), _dir=object()))

    def close(self):
        self.events.append('producer_close')
        self.failed = True
        if self.close_error is not None:
            self.close_error.cleanup_owner = self
            raise self.close_error
        self.host._stopped.set()
        self.host._closing.set()
        self.observer.probe.close()
        self.journal._cache_closed, self.journal._index_store = True, None
        self.closed = True


class TerminalCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='gt06-terminal-inert-')
        self.addCleanup(temporary.cleanup)
        self.studio = Path(temporary.name)
        self.root = self.studio / 'attempt'
        self.root.mkdir()
        sources = {'fixture.py': campaign.sha(b'fixture')}
        self.context = {'run_id': 'gt06.terminal.r00.a01', 'index': 0,
            'source_files': sources, 'source_closure_sha256': campaign.closure(sources),
            'profile_sha256': campaign.profile.PROFILE_SHA256}
        campaign.write(self.root / 'context.json', self.context)
        campaign.write(self.studio / 'toolchain.lock.json', {'godot': {
            'gui_executable': 'never-launched.exe', 'gui_sha256': 'a' * 64}})
        self.events = []
        self.producer = InertProducer(self.events)
        self.probe = InertProbe(self.events, 'editor_probe')
        self.owner = InertOwner(self.events)
        self.thread = InertThread(self.events)
        self.thread.start()
        self.done = campaign.threading.Event()

    def terminal(self):
        return json.loads((self.root / 'child-terminal-cleanup.json').read_bytes())

    def finish(self, primary=None, **overrides):
        values = dict(producer=self.producer, probe=self.probe, owner=self.owner,
            retained=None, done=self.done, thread=self.thread, primary=primary, errors=[])
        values.update(overrides)
        return campaign._finish_child_cleanup(self.root, self.context,
            {'batch': 0, 'phase': 'commands'}, [], **values)

    def child_harness(self, *, producer_error=None, probe_error=None, join_error=None,
                      constructor_error=None, write_error=None, terminal_error=None):
        test = self
        primary = CommandError('ADMISSION_UNKNOWN', report={'status': 'FAILED', 'commands': [{}]})
        primary.__cause__ = RuntimeError('original cause stays intact')
        self.thread = InertThread(self.events, join_error)
        self.probe.error = probe_error

        class EditorOwner(InertOwner):
            def __init__(self, *args, **kwargs):
                super().__init__(test.events)
                test.owner = self
                output = kwargs['output']
                campaign.write(output / 'process-start.json', {'pid': 5900})
                if constructor_error is not None:
                    constructor_error.cleanup_owner = self
                    raise constructor_error

        class Producer(InertProducer):
            def __init__(self, *args):
                super().__init__(test.events, producer_error)
                test.producer = self

            def run_batch(self, index):
                primary.cleanup_owner = self
                raise primary

        def prepare(project, *_):
            (project / 'benchmark/out').mkdir(parents=True)
            return {}

        def imported(*_, **kwargs):
            campaign.write(kwargs['output'] / 'capture.json', {})
            return {}

        def ready(kind, index, _timeout):
            self.assertEqual((kind, index), ('READY', 0))
            path = self.root / 'project/benchmark/out/ready-00.json'
            campaign.write(path, {'run_id': self.context['run_id'], 'batch_index': 0,
                'source_closure_sha256': self.context['source_closure_sha256'],
                'profile_sha256': self.context['profile_sha256']})
            return {'sha256': campaign.sha(path.read_bytes())}

        write_original = campaign.write
        def writer(path, value):
            if path.name == 'child-failure.json' and write_error is not None:
                raise write_error
            return write_original(path, value)

        stack = ExitStack()
        self.addCleanup(stack.close)
        for name, value in [('STUDIO', self.studio), ('load_fixture', lambda: (None, {})),
                            ('verify_sources', lambda _: None), ('prepare', prepare),
                            ('project_files', lambda _: {}), ('BenchmarkProcess', EditorOwner),
                            ('CampaignProducer', Producer), ('open_probe', lambda *_: self.probe),
                            ('NativeLog', lambda _: SimpleNamespace(wait=ready)), ('write', writer)]:
            stack.enter_context(patch.object(campaign, name, value))
        stack.enter_context(patch.object(campaign.threading, 'Thread', return_value=self.thread))
        stack.enter_context(patch.object(campaign.native_job, 'run_trusted_stage', side_effect=imported))
        stack.enter_context(patch.object(campaign.native_job, 'verify_captured_stage', return_value={}))
        if terminal_error is not None:
            stack.enter_context(patch.object(campaign, 'write_cleanup', side_effect=terminal_error))
        return primary

    def test_inert_run_child_records_post_close_states_and_preserves_primary_cause(self):
        primary = self.child_harness()
        cause = primary.__cause__
        with self.assertRaises(CommandError) as caught:
            campaign.run_child(self.root)
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cause)
        self.assertEqual(self.events, ['heartbeat_join', 'producer_close', 'host_probe_close',
                                      'editor_probe_close', 'editor_owner_close'])
        record = self.terminal()
        observed = record['observations']
        self.assertTrue(observed['producer']['closed'])
        self.assertFalse(observed['producer']['observer_probe']['handle_retained'])
        self.assertFalse(observed['producer']['journal']['index_retained'])
        self.assertFalse(observed['editor_probe']['handle_retained'])
        self.assertTrue(observed['editor_owner']['job']['zero_observed'])
        self.assertEqual(observed['editor_owner']['helper_exit_code'], 2)
        self.assertIsNone(observed['editor_target']['actual_target_exit'])
        self.assertEqual(observed['editor_target']['missing_reason'], 'TARGET_EXIT_NOT_RECORDED')
        self.assertIsNone(record['host_actual_exit'])
        self.assertIsNone(record['supervisor_actual_exit'])
        self.assertFalse(record['formal_acceptance'])
        self.assertEqual(record['completed_batches'], 0)
        self.assertEqual(record['errors'], [])
        self.assertEqual(json.loads((self.root / 'child-failure.json').read_bytes())['code'], 'ADMISSION_UNKNOWN')
        self.assertFalse((self.root / 'child-result.json').exists())

    def test_join_and_multiple_close_failures_do_not_skip_owner_or_mask_primary(self):
        join = RuntimeError('join failed')
        producer = CommandError('CLEANUP_HELD')
        probe = ProbeError('PROBE_CLOSE_UNCERTAIN')
        primary = self.child_harness(join_error=join, producer_error=producer, probe_error=probe)
        cause = primary.__cause__
        with self.assertRaises(CommandError) as caught:
            campaign.run_child(self.root)
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cause)
        self.assertIn(join, primary.cleanup_errors)
        self.assertIn(producer, primary.cleanup_errors)
        self.assertIn(probe, primary.cleanup_errors)
        self.assertIn(self.producer, primary.cleanup_owners)
        self.assertIn(self.probe, primary.cleanup_owners)
        self.assertTrue(self.owner.closed)
        observed = self.terminal()['observations']
        self.assertFalse(observed['producer']['closed'])
        self.assertTrue(observed['producer']['journal']['database_retained'])
        self.assertTrue(observed['editor_probe']['handle_retained'])
        self.assertTrue(observed['editor_probe']['close_uncertain'])
        self.assertEqual(self.events.count('editor_probe_close'), 1)

    def test_failure_receipt_write_error_does_not_replace_body_error_or_skip_closes(self):
        receipt_error = OSError('injected failure receipt write')
        primary = self.child_harness(write_error=receipt_error)
        cause = primary.__cause__
        with self.assertRaises(CommandError) as caught:
            campaign.run_child(self.root)
        self.assertIs(caught.exception, primary)
        self.assertIs(primary.__cause__, cause)
        self.assertIn(receipt_error, primary.cleanup_errors)
        self.assertTrue(self.owner.closed)
        self.assertTrue(self.producer.closed)
        self.assertEqual(self.terminal()['errors'][0]['stage'], 'failure_receipt')

    def test_terminal_write_failure_retains_primary_and_all_owner_references(self):
        receipt_error = OSError('injected terminal receipt write')
        primary = self.child_harness(terminal_error=receipt_error)
        with self.assertRaises(CommandError) as caught:
            campaign.run_child(self.root)
        self.assertIs(caught.exception, primary)
        self.assertIn(receipt_error, primary.cleanup_errors)
        self.assertIn(self.owner, primary.cleanup_owners)
        self.assertTrue(self.owner.closed)
        self.assertFalse((self.root / 'child-terminal-cleanup.json').exists())

    def test_constructor_retained_editor_owner_is_closed_and_recorded(self):
        original = BenchmarkJobError('BENCHMARK_JOB_CONFIGURE')
        cause = RuntimeError('original constructor cause')
        original.__cause__ = cause
        self.child_harness(constructor_error=original)
        with self.assertRaises(BenchmarkJobError) as caught:
            campaign.run_child(self.root)
        self.assertIs(caught.exception, original)
        self.assertIs(original.__cause__, cause)
        self.assertTrue(original.cleanup_owner.closed)
        observed = self.terminal()['observations']
        self.assertEqual(observed['producer'], {'present': False})
        self.assertEqual(observed['editor_probe'], {'present': False})
        self.assertTrue(observed['editor_owner']['closed'])

    def test_cleanup_failure_without_primary_cannot_return_success(self):
        self.owner.error = BenchmarkJobError('BENCHMARK_CLEANUP_HELD')
        with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_CLEANUP_HELD') as caught:
            self.finish()
        self.assertIn(self.owner, caught.exception.cleanup_owners)
        self.assertIn(self.owner.error, caught.exception.cleanup_errors)
        self.assertFalse(self.terminal()['observations']['editor_owner']['closed'])

    def test_snapshot_failure_is_unknown_and_does_not_suppress_other_roles(self):
        original = CommandError('ADMISSION_UNKNOWN')
        error = RuntimeError('snapshot unavailable')
        with patch.object(campaign, '_producer_cleanup_state', side_effect=error):
            self.finish(primary=original)
        self.assertIsNone(self.terminal()['observations']['producer'])
        self.assertTrue(self.terminal()['observations']['editor_owner']['closed'])
        self.assertIn(error, original.cleanup_errors)

    def test_existing_terminal_receipt_is_never_overwritten(self):
        path = self.root / 'child-terminal-cleanup.json'
        path.write_bytes(b'original evidence\n')
        original = CommandError('ADMISSION_UNKNOWN')
        self.finish(primary=original)
        self.assertEqual(path.read_bytes(), b'original evidence\n')
        self.assertTrue(any(isinstance(e, FileExistsError) for e in original.cleanup_errors))
        self.assertTrue(self.owner.closed)

    def test_actual_exit_receipt_is_pid_bound_and_not_a_helper_exit(self):
        directory = self.root / 'editor-host'
        campaign.write(directory / 'process-start.json', {'pid': 5900})
        campaign.write(directory / 'process-exit.json', {'pid': 5900, 'exit_code': 86})
        self.finish()
        row = self.terminal()['observations']['editor_target']
        self.assertEqual(row['actual_target_exit'], {'pid': 5900, 'exit_code': 86})
        self.assertIsNone(row['missing_reason'])
        self.assertEqual(row['exit']['sha256'], campaign.sha((directory / 'process-exit.json').read_bytes()))
        self.assertEqual(self.terminal()['observations']['editor_owner']['helper_exit_code'], 2)

    def test_malformed_or_wrong_pid_exit_is_an_error_not_an_observed_exit(self):
        directory = self.root / 'editor-host'
        campaign.write(directory / 'process-start.json', {'pid': 5900})
        for raw in [b'bad json', b'{"pid":5901,"exit_code":0}', b'{"pid":5900,"exit_code":true}']:
            with self.subTest(raw=raw):
                (directory / 'process-exit.json').write_bytes(raw)
                with self.assertRaises((ValueError, BenchmarkJobError)):
                    campaign._target_exit_state(self.root, 'editor-host')

    def test_error_text_and_handle_values_are_not_serialized(self):
        original = CommandError('contains secret bearer abc123')
        self.probe.error = ProbeError('secret bearer abc123')
        self.finish(primary=original)
        text = (self.root / 'child-terminal-cleanup.json').read_text()
        self.assertNotIn('abc123', text)
        self.assertNotIn('object at', text)
        self.assertIsNone(self.terminal()['primary_error']['code'])
        self.assertTrue(self.terminal()['observations']['editor_probe']['close_uncertain'])

    def test_separate_retained_import_job_is_closed_without_replacing_editor_owner(self):
        events = self.events
        class ImportJob(campaign.native_job.cli_job.Owner):
            def __init__(self):
                self.closed = False

            def close(self):
                events.append('import_owner_close')
                self.closed = True

            def snapshot(self):
                return {'closed': self.closed, 'zero_observed': self.closed, 'handle_retained': not self.closed}
        imported = ImportJob()
        self.finish(primary=campaign.native_job.StageFailed('STAGE_CLEANUP_HELD', cleanup_owner=imported),
                    retained=imported)
        self.assertTrue(self.owner.closed)
        self.assertTrue(imported.closed)
        self.assertTrue(self.terminal()['observations']['constructor_owner']['job']['zero_observed'])
        self.assertEqual(self.events[-1], 'import_owner_close')


if __name__ == '__main__':
    unittest.main()
