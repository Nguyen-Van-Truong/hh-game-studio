"""Inert probe gates only: no engine, Journal constructor, lock or Registry.

Temporary files model already-produced runner artifacts, never backend I/O.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_client_ledger_probe as probe
from studio.host.blender import client_ledger as ledger
from studio.host.core.journal import Journal, JournalError
from studio.host.core.limits import DEFAULT_LIMITS
from studio.protocol.core import canonical_bytes


def host():
    return {'exit_code': 0, 'wrapper_exit_code': 0, 'timed_out': False,
            'tree_verified': True, 'target_pid': 101, 'wrapper_pid': 100, 'host': 'native-host.json'}


def cleanup():
    return {'closed': True, 'actual_process_exit': {'pid': 202, 'exit_code': 0},
        'wrapper_exit_code': 0, 'logs_overflow': False,
        'job': {'zero_observed': True, 'active_count': 0, 'closed': True, 'handle_retained': False}}


def stop_response(status):
    return SimpleNamespace(status=SimpleNamespace(value=status))


class ProbeGates(unittest.TestCase):
    def test_unique_inventory_and_exact_counts_required(self):
        counts = {'run': 2, 'failures': 0, 'errors': 0, 'skips': 0}
        inventory = probe.UNIT_INVENTORY + json.dumps(['test.a', 'test.b'])
        complete = probe.UNIT_COMPLETE + json.dumps(counts)
        self.assertEqual(probe.unit_completion(inventory + '\n' + complete), (True, [counts]))
        for text in (complete, inventory, inventory + '\n' + inventory + '\n' + complete,
                     probe.UNIT_INVENTORY + '["test.a","test.a"]\n' + complete,
                     inventory + '\n' + complete.replace('"run": 2', '"run": 1'),
                     inventory + '\n' + complete.replace('"skips": 0', '"skips": 1'),
                     inventory + '\n' + complete.replace('"failures": 0', '"failures": false'),
                     probe.UNIT_INVENTORY + 'bad json'):
            with self.subTest(text=text):
                self.assertFalse(probe.unit_completion(text)[0])

    def test_raw_host_exit_tree_and_timeout_all_required(self):
        self.assertTrue(probe.host_passed(host()))
        self.assertFalse(probe.host_passed(None))
        for key, value in (('exit_code', None), ('exit_code', False), ('wrapper_exit_code', 1),
                           ('wrapper_exit_code', False), ('target_pid', True),
                           ('timed_out', True), ('tree_verified', False)):
            with self.subTest(key=key):
                self.assertFalse(probe.host_passed({**host(), key: value}))

    def test_cleanup_requires_exact_native_pid_empty_job_and_closed_handle(self):
        self.assertTrue(probe.cleanup_passed(cleanup(), 202))
        self.assertFalse(probe.cleanup_passed(cleanup(), 203))
        self.assertFalse(probe.cleanup_passed(cleanup(), None))
        for key, value in (('active_count', 1), ('active_count', False), ('closed', False),
                           ('zero_observed', False), ('handle_retained', True)):
            row = cleanup()
            row['job'][key] = value
            with self.subTest(key=key):
                self.assertFalse(probe.cleanup_passed(row, 202))
        for key, value in (('closed', False), ('logs_overflow', True), ('wrapper_exit_code', 1)):
            self.assertFalse(probe.cleanup_passed({**cleanup(), key: value}, 202))
        row = cleanup()
        row['actual_process_exit']['exit_code'] = False
        self.assertFalse(probe.cleanup_passed(row, 202))

    def test_json_validation_failure_does_not_create_empty_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaises(Exception):
                probe.write_json(output, 'invalid.json', {'value': float('nan')})
            self.assertFalse((output / 'invalid.json').exists())

    def test_pending_stop_waits_for_terminal_with_same_call(self):
        clock = [0.0]
        calls = []
        replies = [stop_response('ACCEPTED_PENDING'), stop_response('ACCEPTED_PENDING'),
                   stop_response('COMMITTED')]

        def call():
            calls.append(len(calls))
            return replies[len(calls) - 1]

        def pause(seconds):
            clock[0] += seconds

        result, pending, elapsed = probe.stop_until_terminal(call, clock=lambda: clock[0], pause=pause)
        self.assertIs(result, replies[-1])
        self.assertEqual((len(calls), pending, elapsed), (3, 2, 40.0))

    def test_pending_stop_timeout_never_starts_extra_call_after_deadline(self):
        clock = [0.0]
        calls = []

        def call():
            calls.append(clock[0])
            return stop_response('ACCEPTED_PENDING')

        def pause(seconds):
            clock[0] += seconds

        with self.assertRaisesRegex(TimeoutError, 'STOP_PENDING'):
            probe.stop_until_terminal(call, timeout=0.05, clock=lambda: clock[0], pause=pause)
        self.assertEqual(calls, [0.0, 0.02, 0.04])

    def test_unknown_stop_is_not_retried_or_reclassified_as_success(self):
        unknown = stop_response('UNKNOWN')
        result, pending, _ = probe.stop_until_terminal(lambda: unknown)
        self.assertIs(result, unknown)
        self.assertEqual(pending, 0)

    def test_disk_snapshot_preserves_backend_newline_and_checksum_contract(self):
        # Calling only core encoding/decoding bypasses every native constructor
        # and filesystem primitive. This catches dropped-newline probe bugs.
        backend = object.__new__(Journal)
        backend.profile = DEFAULT_LIMITS
        binding = ledger.LedgerBinding('blender.test', 'a' * 32, 'sha256:' + 'b' * 64,
            'sha256:' + 'c' * 64, 'sha256:' + 'd' * 64)
        config = {'schema': ledger.SCHEMA, 'binding': ledger.binding_value(binding)}
        row = {'kind': 'command', 'project_id': ledger.PROJECT, 'command_id': 'ledger-config',
            'digest': ledger.sha(canonical_bytes(config)), 'status': 'COMMITTED',
            'receipt': config, 'created_ms': 1, 'expires_ms': 2}
        raw = backend._encoded_record(row)
        records, state = probe.decode_disk_snapshot(raw, backend, binding)
        self.assertEqual(records, [row])
        self.assertEqual(state, {})
        with self.assertRaisesRegex(JournalError, 'JOURNAL_TRUNCATED'):
            probe.decode_disk_snapshot(raw.rstrip(b'\n'), backend, binding)
        with self.assertRaises(JournalError):
            probe.decode_disk_snapshot(raw.replace(b'ledger-config', b'ledger-tamper'), backend, binding)

    def test_failure_summary_excludes_arbitrary_exception_details(self):
        self.assertEqual(probe.safe_failure(ValueError('secret value')),
                         {'type': 'ValueError', 'code': None})
        error = JournalError('SAFE_CODE')
        self.assertEqual(probe.safe_failure(error)['code'], 'SAFE_CODE')
        error.code = 'C:/private/file'
        self.assertIsNone(probe.safe_failure(error)['code'])


class NativeArtifactGates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.directory = self.output / 'gui-owned'
        self.directory.mkdir()
        self.report = {'passed': True, 'probe_pid': 101, 'native_pid': 202,
            'gui_directory': self.directory.name, 'cleanup': cleanup(),
            'checks': [{'label': 'observed', 'passed': True}],
            'public_ack': False, 'public_write_facade': False}
        self.persist()

    def persist(self):
        (self.output / 'native-host.json').write_text(json.dumps(
            {'target_pid': 101, 'exit_code': 0}), encoding='utf-8')
        (self.output / 'ledger-native.json').write_text(json.dumps(self.report), encoding='utf-8')
        (self.output / 'native-stdout.txt').write_text(probe.NATIVE_COMPLETE
            + json.dumps({'passed': True, 'checks': len(self.report['checks'])}) + '\n', encoding='utf-8')
        (self.directory / 'process-exit.json').write_text(json.dumps(
            self.report['cleanup']['actual_process_exit']), encoding='utf-8')
        (self.directory / 'close.json').write_text(json.dumps(self.report['cleanup']), encoding='utf-8')

    def test_complete_raw_artifacts_and_matching_parent_target(self):
        self.assertTrue(probe.native_completion(self.output, host()))
        self.assertFalse(probe.native_completion(self.output, {**host(), 'target_pid': 999}))
        self.assertFalse(probe.native_completion(self.output, {**host(), 'tree_verified': False}))

    def test_raw_exit_or_cleanup_disagreement_rejects_claimed_success(self):
        (self.output / 'native-host.json').write_text('{"target_pid":101,"exit_code":false}', encoding='utf-8')
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        (self.directory / 'process-exit.json').write_text('{"pid":202,"exit_code":1}', encoding='utf-8')
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        raw = copy.deepcopy(self.report['cleanup'])
        raw['job']['handle_retained'] = True
        (self.directory / 'close.json').write_text(json.dumps(raw), encoding='utf-8')
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_duplicate_marker_duplicate_checks_and_public_ack_rejected(self):
        stdout = self.output / 'native-stdout.txt'
        stdout.write_text(stdout.read_text() * 2, encoding='utf-8')
        self.assertFalse(probe.native_completion(self.output, host()))
        self.report['checks'] *= 2
        self.persist()
        self.assertFalse(probe.native_completion(self.output, host()))
        self.report['checks'] = self.report['checks'][:1]
        self.report['public_ack'] = True
        self.persist()
        self.assertFalse(probe.native_completion(self.output, host()))


if __name__ == '__main__':
    unittest.main()
