"""Pure filesystem fixtures; no engine, real Scheduler or process mutation."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import closeout_quiet_chain as closeout


class CloseoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.studio = Path(self.temp.name) / 'studio'
        self.campaign = 'gt06-o9-chain-f22-r01'
        self.host_id = 'gt06-o9-host-f22-r01'
        reviews = self.studio / '.local/reviews'
        self.supervisor = reviews / (self.campaign + '-supervisor')
        self.chain = reviews / self.campaign
        self.host = reviews / self.host_id
        self.output = reviews / (self.campaign + '-closeout')
        for directory in (self.supervisor, self.chain, self.host / 'owner', self.studio / 'tests/replay'):
            directory.mkdir(parents=True)
        self.calls = []
        files = {}
        for name in ('run_campaign_task.py', 'campaign_task.ps1', 'run_command_residency.py'):
            path = self.studio / 'tests/replay' / name
            path.write_bytes(('fixture ' + name).encode())
            files[path.relative_to(self.studio).as_posix()] = closeout.digest(path)
        self.python = self.studio / 'python.exe'
        self.pythonw = self.studio / 'pythonw.exe'
        self.python.write_bytes(b'fixture console')
        self.pythonw.write_bytes(b'fixture windowed')
        self.plan = {'chain_id': self.campaign, 'formal_id': 'gt06-o4-formal-22',
                     'formal_acceptance': False, 'source_files': files,
                     'source_closure_sha256': closeout.closure(files), 'profile_sha256': 'e' * 64}
        self.put(self.supervisor / 'quiet-chain-plan.json', self.plan)
        self.put(self.chain / 'chain-context.json', self.plan)
        self.put(self.host / 'soak-context.json', {'run_id': self.host_id,
                 'source_files': files, 'source_closure_sha256': self.plan['source_closure_sha256']})
        self.request = {'schema': 'HH-GT06-TASK-REQUEST-1', 'campaign_id': self.campaign,
                        'mode': 'quiet-chain', 'script_sha256': files['tests/replay/run_campaign_task.py'],
                        'python_sha256': closeout.digest(self.python), 'pythonw_sha256': closeout.digest(self.pythonw),
                        'chain_plan_sha256': closeout.digest(self.supervisor / 'quiet-chain-plan.json')}
        self.put(self.supervisor / 'request.json', self.request)
        self.task_path = '\\HHStudio.GT06.' + self.campaign
        (self.supervisor / 'task-definition.xml').write_text('<fixture/>')
        xml_hash = closeout.digest(self.supervisor / 'task-definition.xml')
        (self.supervisor / 'task-definition.sha256').write_text(xml_hash + '\n')
        common = {'campaign_id': self.campaign, 'mode': 'quiet-chain', 'launch_number': 1,
                  'task_path': self.task_path, 'task_definition_sha256': xml_hash,
                  'request_sha256': closeout.digest(self.supervisor / 'request.json')}
        self.registration = {**common, 'schema': 'HH-GT06-TASK-REGISTRATION-1',
                             'script_path': str(self.studio / 'tests/replay/run_campaign_task.py'),
                             'python_path': str(self.python), 'pythonw_path': str(self.pythonw)}
        self.put(self.supervisor / 'task-registration.json', self.registration)
        self.put(self.supervisor / 'task-start.json', {**common, 'schema': 'HH-GT06-TASK-START-1'})
        self.put(self.supervisor / 'start.json', {**common, 'pid': 101, 'process_start': 'windows:12345',
                 'supervisor_script_sha256': self.request['script_sha256']})
        self.put(self.supervisor / 'return.json', {'returned_exit_code': 1, 'elapsed_seconds': 135.5,
                 'formal_acceptance': False, 'actual_process_exit_not_yet_observed': True})
        job = {'active_count': 0, 'assigned': True, 'close_uncertain': False, 'closed': True,
               'configured': True, 'create_uncertain': False, 'failed_operations': [],
               'handle_retained': False, 'native_error': None, 'tainted': False, 'zero_observed': True}
        self.put(self.host / 'owner-failure.json', {'classification': 'INFRA_ABORT',
                 'code': 'CAMPAIGN_WATCHDOG_EXTERNAL_CPU_PRESSURE', 'completed': False,
                 'formal_acceptance': False, 'job': job})
        self.put(self.host / 'owner/cleanup-001.json', {'closed': True, 'completed': False,
                 'job': job, 'wrapper_exit_code': 2, 'wrapper_process_handle': {'required': True,
                 'closed': True, 'handle_retained': False, 'close_uncertain': False}})
        self.put(self.host / 'owner/process-start.json', {'pid': 202})
        self.put(self.host / 'owner/invocation.json', {'source_files': files, 'source_root': str(self.studio),
                 'cwd': str(self.host), 'binary_sha256': self.request['python_sha256'],
                 'argv': [str(self.python), '-B', str(self.studio / 'tests/replay/run_command_residency.py'),
                          '--child', '--run-id', self.host_id, '--minimum-seconds', '1800']})
        self.status = {'schema': 'HH-GT06-TASK-STATUS-1', 'campaign_id': self.campaign,
                       'task_path': self.task_path, 'mode': 'quiet-chain', 'launch_number': 1,
                       'output_directory': str(self.supervisor), 'state': 3, 'instances': [], 'last_task_result': 1}

    @staticmethod
    def put(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def change(self, path, **fields):
        self.put(path, {**json.loads(path.read_text()), **fields})

    @staticmethod
    def absent(pid):
        return {'pid': pid, 'state': 'absent', 'process_start': None, 'native_error': 87}

    def scheduler(self, studio, campaign_id, command):
        self.assertEqual((studio, campaign_id), (self.studio, self.campaign))
        self.calls.append(command)
        if command == 'status':
            return deepcopy(self.status), {'exit_code': 0, 'stdout': json.dumps(self.status), 'stderr': ''}
        self.assertEqual(command, 'delete')
        receipt = {'schema': 'HH-GT06-TASK-DELETED-1', 'campaign_id': self.campaign,
                   'task_path': self.task_path, 'launch_number': 1, 'formal_acceptance': False,
                   'task_definition_sha256': self.registration['task_definition_sha256']}
        self.put(self.supervisor / 'task-deleted.json', receipt)
        return receipt, {'exit_code': 0, 'stdout': json.dumps(receipt), 'stderr': ''}

    def run_closeout(self, **kwargs):
        return closeout.closeout(self.studio, self.campaign, scheduler=self.scheduler,
                                 probe=kwargs.pop('probe', self.absent), **kwargs)

    def test_default_read_only_unknown_child_is_not_wrapper_exit(self):
        before = {p: p.read_bytes() for p in self.studio.rglob('*') if p.is_file()}
        result = self.run_closeout()
        self.assertEqual(result['actual_child_exit']['status'], 'UNKNOWN')
        self.assertIsNone(result['actual_child_exit']['exit_code'])
        self.assertEqual(result['wrapper_return_code'], 1)
        self.assertEqual(result['owner_helper_wrapper_exit_code'], 2)
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertFalse(result['formal_acceptance'])
        self.assertFalse(result['acceptance_verified'])
        self.assertEqual(self.calls, ['status'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.studio.rglob('*') if p.is_file()})

    def test_write_exports_new_manifest_and_preserves_raw(self):
        result = self.run_closeout(write=True)
        self.assertEqual(result['output_directory'], str(self.output))
        manifest = json.loads((self.output / 'raw-manifest.json').read_text())
        self.assertTrue(manifest['raw_retained_in_place'])
        for name, row in manifest['files'].items():
            self.assertEqual(row['sha256'], closeout.digest(self.studio / name))
        self.assertTrue((self.output / 'closeout.json').is_file())
        self.assertFalse(result['task_deleted'])
        self.assertEqual(self.calls, ['status'])

    def test_existing_export_never_overwritten(self):
        self.run_closeout(write=True)
        before = (self.output / 'closeout.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'CLOSEOUT_ALREADY_EXISTS'):
            self.run_closeout(write=True)
        self.assertEqual(before, (self.output / 'closeout.json').read_bytes())

    def test_delete_requires_write(self):
        with self.assertRaisesRegex(ValueError, 'DELETE_REQUIRES_WRITE'):
            self.run_closeout(delete_task=True)
        self.assertEqual(self.calls, [])

    def test_explicit_delete_rechecks_and_verifies_exact_receipt(self):
        result = self.run_closeout(write=True, delete_task=True)
        self.assertEqual(self.calls, ['status', 'status', 'delete'])
        self.assertTrue(result['task_deleted'])
        self.assertIsNone(result['actual_child_exit']['exit_code'])
        self.assertTrue((self.output / 'task-deletion.json').is_file())

    def test_running_scheduler_refuses_mutation(self):
        for field, value in (('instances', [{'instance_guid': 'active'}]), ('state', 4), ('last_task_result', 0)):
            with self.subTest(field=field):
                old = deepcopy(self.status)
                self.status[field] = value
                with self.assertRaisesRegex(ValueError, 'SCHEDULER_NOT_TERMINAL'):
                    self.run_closeout(write=True, delete_task=True)
                self.status = old
        self.assertNotIn('delete', self.calls)
        self.assertFalse(self.output.exists())

    def test_live_unknown_and_reused_live_pid_fail_closed(self):
        for state in ('live', 'unknown'):
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, 'LIVE_OR_UNKNOWN_OWNED_PID'):
                self.run_closeout(probe=lambda pid: {'pid': pid, 'state': state, 'process_start': 'windows:999'})

    def test_cleanup_uncertainty_and_retained_handles_fail_closed(self):
        path = self.host / 'owner/cleanup-001.json'
        original = json.loads(path.read_text())
        for field, value in (('zero_observed', False), ('active_count', 1), ('tainted', True),
                             ('handle_retained', True), ('close_uncertain', True)):
            with self.subTest(field=field):
                changed = deepcopy(original)
                changed['job'][field] = value
                self.put(path, changed)
                with self.assertRaisesRegex(ValueError, 'CLEANUP_UNPROVEN'):
                    self.run_closeout()
        self.put(path, original)
        changed = deepcopy(original)
        changed['wrapper_process_handle']['closed'] = False
        self.put(path, changed)
        with self.assertRaisesRegex(ValueError, 'CLEANUP_UNPROVEN'):
            self.run_closeout()

    def test_frozen_source_drift_refuses_status_and_delete(self):
        (self.studio / 'tests/replay/run_command_residency.py').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'FROZEN_SOURCE_CHANGED'):
            self.run_closeout(write=True, delete_task=True)
        self.assertEqual(self.calls, [])

    def test_plan_request_start_and_xml_hash_binding(self):
        for name in ('quiet-chain-plan.json', 'request.json', 'task-definition.xml'):
            path = self.supervisor / name
            before = path.read_bytes()
            path.write_bytes(before + b' ')
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.run_closeout()
            path.write_bytes(before)
        self.change(self.supervisor / 'start.json', request_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'REQUEST_HASH'):
            self.run_closeout()

    def test_missing_receipt_is_not_acceptance(self):
        (self.host / 'owner/cleanup-001.json').unlink()
        with self.assertRaises(ValueError):
            self.run_closeout(write=True, delete_task=True)
        self.assertNotIn('delete', self.calls)

    def test_foreign_host_invocation_rejected(self):
        self.change(self.host / 'owner/invocation.json', cwd=str(self.chain))
        with self.assertRaisesRegex(ValueError, 'OWNER_INVOCATION_BINDING'):
            self.run_closeout()

    def test_classification_never_promotes_pass(self):
        self.change(self.host / 'owner-failure.json', classification='PASS')
        with self.assertRaisesRegex(ValueError, 'FAILURE_CLASSIFICATION'):
            self.run_closeout()

    def test_recorded_child_exit_remains_nonacceptance(self):
        self.put(self.host / 'owner/process-exit.json', {'pid': 202, 'exit_code': 7})
        result = self.run_closeout()
        self.assertEqual(result['actual_child_exit']['exit_code'], 7)
        self.assertFalse(result['acceptance_verified'])
        self.change(self.host / 'owner/process-exit.json', pid=999)
        with self.assertRaisesRegex(ValueError, 'CHILD_EXIT_BINDING'):
            self.run_closeout()

    def test_formal_dispatch_is_outside_this_closeout_scope(self):
        self.put(self.chain / 'formal-dispatch.json', {})
        with self.assertRaisesRegex(ValueError, 'DISPATCHED_OR_COMPLETE_CHAIN_UNSUPPORTED'):
            self.run_closeout()

    def test_invalid_campaign_paths_rejected(self):
        for value in ('../escape', 'gt06-o9-chain-f22-r01/else', 'gt06-o9-chain-f21-r01;cmd', ''):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'CAMPAIGN_ID'):
                closeout.closeout(self.studio, value, scheduler=self.scheduler, probe=self.absent)
        self.assertEqual(self.calls, [])

    def test_manifest_path_escape_and_bad_closure_rejected(self):
        for name in ('../escape', 'C:/escape', 'tests\\escape', '/escape', 'tests/../escape'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'SOURCE_PATH'):
                closeout.verify_sources(self.studio, {'source_files': {name: 'a' * 64}})
        with self.assertRaisesRegex(ValueError, 'SOURCE_CLOSURE'):
            closeout.verify_sources(self.studio, {**self.plan, 'source_closure_sha256': '0' * 64})

    def test_raw_change_during_status_is_rejected(self):
        def changed(studio, campaign_id, command):
            self.put(self.host / 'new.json', {'late': True})
            return self.scheduler(studio, campaign_id, command)
        with self.assertRaisesRegex(ValueError, 'RAW_CHANGED_DURING_COLLECTION'):
            closeout.closeout(self.studio, self.campaign, scheduler=changed, probe=self.absent)

    def test_source_change_during_status_is_rejected(self):
        def changed(studio, campaign_id, command):
            (studio / 'tests/replay/run_command_residency.py').write_bytes(b'changed during observation')
            return self.scheduler(studio, campaign_id, command)
        with self.assertRaisesRegex(ValueError, 'FROZEN_SOURCE_CHANGED'):
            closeout.closeout(self.studio, self.campaign, scheduler=changed, probe=self.absent)

    def test_source_reparse_rejected(self):
        source = self.studio / 'tests/replay/run_command_residency.py'
        target = self.studio / 'retained.py'
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except OSError as error:
            self.skipTest('symlink unavailable: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'REPARSE_PATH'):
            self.run_closeout()

    def test_restart_before_delete_refuses_exact_task_mutation(self):
        def restart(studio, campaign_id, command):
            if self.calls:
                self.status['state'] = 4
            return self.scheduler(studio, campaign_id, command)
        with self.assertRaisesRegex(ValueError, 'SCHEDULER_NOT_TERMINAL'):
            closeout.closeout(self.studio, self.campaign, write=True, delete_task=True,
                              scheduler=restart, probe=self.absent)
        self.assertEqual(self.calls, ['status', 'status'])
        self.assertTrue((self.output / 'raw-manifest.json').is_file())

    def test_deleted_receipt_mismatch_is_unproven(self):
        def mismatch(studio, campaign_id, command):
            value, raw = self.scheduler(studio, campaign_id, command)
            if command == 'delete':
                value['task_path'] = '\\wrong-task'
            return value, raw
        with self.assertRaisesRegex(ValueError, 'DELETE_RECEIPT_UNPROVEN'):
            closeout.closeout(self.studio, self.campaign, write=True, delete_task=True,
                              scheduler=mismatch, probe=self.absent)
        self.assertFalse((self.output / 'closeout-after-delete.json').exists())

    def test_hash_inventory_bounds(self):
        with patch.object(closeout, 'MAX_FILES', 1), self.assertRaisesRegex(ValueError, 'RAW_BOUND'):
            self.run_closeout()


if __name__ == '__main__':
    unittest.main()
