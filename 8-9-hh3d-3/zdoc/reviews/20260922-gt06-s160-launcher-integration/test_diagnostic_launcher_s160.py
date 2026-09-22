"""Fake/raw-only S160 integration tests.

The owner launch is exercised with a retained fake process and raw receipts;
no Godot, Blender, benchmark worker, or native process is started.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import contextmanager

HERE = Path(__file__).resolve().parent
HH3D = HERE.parents[2]
sys.path.insert(0, str(HH3D))
sys.path.insert(0, str(HERE))
import diagnostic_launcher_s160 as launcher


class Owner:
    def __init__(self, fixture):
        self.fixture = fixture
        self.closed = False
        self.process = SimpleNamespace(pid=7001, returncode=None)
        self.job = SimpleNamespace(snapshot=lambda: {
            'closed': True, 'zero_observed': True, 'tainted': False})
        self.threads = []

    def tick(self, stop=False):
        if stop:
            raise launcher.IntegrationError('STOP')
        if self.process.returncode is None:
            self.process.returncode = 1
            self.fixture.write_boundary_raw()
        return self.process.returncode

    def close(self):
        self.closed = True

    def process_handle_snapshot(self):
        return {'required': True, 'closed': self.closed,
                'close_uncertain': False, 'handle_retained': not self.closed}


class Services:
    def __init__(self, fixture):
        self.fixture = fixture
        self.spawned = []
        self.now = 0.0

    def observed_source(self):
        return {'closure': launcher.SOURCE, 'count': 1,
                'profile_sha256': launcher.PROFILE,
                'files': self.fixture.source_files}

    def workstation(self):
        return self.fixture.workstation

    def python_executable(self):
        return str(self.fixture.python)

    def python_sha256(self):
        return launcher.digest(self.fixture.python)

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds

    def utc(self):
        return '2026-09-22T08:00:00Z'

    def stop_requested(self, output, *, run_id, source_closure_sha256, campaign_sha256):
        path = Path(output) / 'stop-request.json'
        if not path.exists():
            return False
        value = json.loads(path.read_bytes())
        return (value.get('run_id') == run_id and value.get('source_closure_sha256') == source_closure_sha256
                and value.get('campaign_sha256') == campaign_sha256)

    def spawn(self, argv, **kwargs):
        self.spawned.append((list(argv), kwargs))
        owner = Owner(self.fixture)
        self.owner = owner
        return owner

    def editor_cleanup(self, owner):
        if owner is None:
            return {'present': False}
        return {'present': True, 'closed': owner.closed,
                'job': owner.job.snapshot(),
                'wrapper_process_handle': owner.process_handle_snapshot(),
                'drain_threads_alive': [], 'helper_pid': owner.process.pid,
                'helper_exit_code': owner.process.returncode}

    def target_exit(self, root, role):
        root = Path(root)
        start = root / role / 'process-start.json'
        exit_ = root / role / 'process-exit.json'
        def ref(path):
            if not path.exists():
                return None
            raw = path.read_bytes()
            return {'file': path.relative_to(root).as_posix(),
                    'sha256': __import__('hashlib').sha256(raw).hexdigest(),
                    'size_bytes': len(raw)}
        if not start.exists():
            return {'actual_target_exit': None, 'missing_reason': 'TARGET_EXIT_NOT_RECORDED',
                    'natural_exit_not_inferred': True, 'start': None, 'exit': None}
        s = json.loads(start.read_bytes())
        e = json.loads(exit_.read_bytes()) if exit_.exists() else None
        if e is not None and e.get('pid') != s.get('pid'):
            raise launcher.IntegrationError('S160_TARGET_IDENTITY')
        return {'actual_target_exit': e, 'missing_reason': None if e else 'TARGET_EXIT_NOT_RECORDED',
                'natural_exit_not_inferred': True, 'start': ref(start), 'exit': ref(exit_)}


class Fixture:
    def __init__(self, temp):
        self.temp = temp
        self.root = Path(temp.name) / 'root'
        self.root.mkdir()
        (self.root / 'studio').mkdir()
        (self.root / 'studio/pin.txt').write_bytes(b'fixture-pin\n')
        self.source_files = {'studio/pin.txt': launcher.digest(self.root / 'studio/pin.txt')}
        self.python = self.root / 'python.bin'
        self.python.write_bytes(b'fake-python\n')
        self.workstation = {'schema_id': 'hh-studio.benchmark-workstation',
                            'schema_version': '1.0.0', 'machine': 'fixture',
                            'logical_processors': 8, 'pointer_bits': 64,
                            'python': 'fixture', 'renderer': 'none',
                            'sequence': 'fake', 'scope': 'raw fixture only'}
        self.predecessor = self.root / 'freeze-s153.json'
        predecessor = {
            'schema': launcher.base.PREDECESSOR_SCHEMA,
            'benchmark53': launcher.SOURCE, 'profile_sha256': launcher.PROFILE,
            'files': self.source_files, 'binaries': {str(self.python): launcher.digest(self.python)},
            'workstation': self.workstation, 'formal_acceptance': False,
            'campaign_id': 'gt06-s153-formal-01'}
        launcher.publish(self.predecessor, predecessor)
        self.services = Services(self)

    def prepare(self, run_id='gt06-s160-diag-a01', prefix=1):
        result = launcher.prepare(self.root, run_id, prefix, self.services,
                                  predecessor_path=self.predecessor)
        self.run = Path(result['run'])
        self.auth = launcher.authenticate(self.run, self.services,
                                          freeze_sha256=result['freeze_sha256'])
        self.freeze_sha = result['freeze_sha256']
        return result

    def write_boundary_raw(self):
        auth = self.auth
        root = self.run / 'attempt'
        (root / 's160-gates').mkdir(exist_ok=True)
        (root / 'editor-host').mkdir(exist_ok=True)
        launcher.publish(root / 'editor-host/process-start.json', {'pid': 8001})
        idx = 0
        sample = {'index': idx, 'run_id': auth['context']['run_id'],
                  'source_closure_sha256': launcher.SOURCE,
                  'profile_sha256': launcher.PROFILE,
                  'processes': {'host': {'pid': 9001},
                                'editor': {'pid': 8001, 'process_start': 'fixture'}}}
        joint = dict(sample)
        launcher.publish(root / 'sample-preview-00.json', sample)
        launcher.publish(root / 'joint-00.json', joint)
        gate = {'schema': 'HH-S160-original-gate-1', 'run_id': auth['context']['run_id'],
                'pid': 9001, 'index': idx, 'result': 'PASSED', 'error_code': None,
                'context': launcher.reference(root, root / 'context.json'),
                'sample': launcher.reference(root, root / 'sample-preview-00.json'),
                'joint': launcher.reference(root, root / 'joint-00.json'), **launcher.FLAGS}
        gate_path = root / 's160-gates/gate-00.json'
        launcher.publish(gate_path, gate)
        summary = {'schema': 'HH-S160-summary-1', 'bindings': launcher.bindings(auth),
                   'pid': 9001, 'status': 'BOUNDARY_CAPTURED', 'primary_error': None,
                   'cleanup_errors': [], 'screened_batches': [
                       {'index': 0, 'gate': launcher.reference(root, gate_path)}],
                   'reauthenticated': True, **launcher.FLAGS}
        launcher.publish(self.run / 'diagnostic-summary.json', summary)
        owned = self.run / 'owned'
        launcher.publish(owned / 'process-start.json', {'pid': 9001})
        launcher.publish(owned / 'process-exit.json', {'pid': 9001, 'exit_code': 1})

    def stop(self):
        launcher.publish(self.run / 'attempt/stop-request.json', {
            'run_id': self.auth['context']['run_id'],
            'source_closure_sha256': launcher.SOURCE,
            'campaign_sha256': self.auth['context']['campaign_sha256']})


class S160Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fx = Fixture(self.temp)

    def test_prepare_pins_exact_helper_and_execution_closures(self):
        result = self.fx.prepare()
        freeze = json.loads((self.fx.run / 'freeze.json').read_bytes())
        self.assertEqual(set(freeze['helper_files']),
                         {'driver.py', 'launcher_base.py', 'editor_handles.py', 'pss_adapter.py'})
        self.assertEqual(freeze['helper_closure_sha256'], launcher.closure(freeze['helper_files']))
        self.assertFalse(result['launched'])

    def test_helper_extra_file_and_child_pin_fail_closed(self):
        self.fx.prepare()
        (self.fx.run / 'helpers/extra.txt').write_bytes(b'drift')
        with self.assertRaises(launcher.IntegrationError) as error:
            launcher.authenticate(self.fx.run, self.services,
                                  freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(error.exception.code, 'S160_HELPER_DRIFT')

    def test_execution_map_drift_is_rejected_before_spawn(self):
        self.fx.prepare()
        path = self.fx.run / 'execution-source-files.json'
        value = json.loads(path.read_bytes())
        value['studio/pin.txt'] = '0' * 64
        path.write_bytes(launcher.encoded(value))
        with self.assertRaises(launcher.IntegrationError) as error:
            launcher.authenticate(self.fx.run, self.services,
                                  freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(error.exception.code, 'S160_EXECUTION_EXACT_SET')

    @property
    def services(self):
        return self.fx.services

    def test_launch_boundary_uses_actual_target_and_helper_exits(self):
        self.fx.prepare()
        record = launcher.launch_existing(self.fx.run, self.services,
                                          freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(record['status'], 'BOUNDARY_CAPTURED')
        self.assertEqual(record['launcher_exit'], 0)
        self.assertEqual(record['helper_pid'], 7001)
        self.assertEqual(record['helper_exit_before_close'], 1)
        self.assertEqual(record['child_target']['actual_target_exit'], {'pid': 9001, 'exit_code': 1})
        self.assertTrue(record['reauthenticated'])
        self.assertTrue(record['boundary_permitted'])
        self.assertEqual(record['authority'], 0)
        self.assertFalse(record['formal_acceptance'])

    def test_exact_prefix_rejects_missing_row_and_raw_hash_is_bound(self):
        self.fx.prepare()
        self.fx.write_boundary_raw()
        summary = json.loads((self.fx.run / 'diagnostic-summary.json').read_bytes())
        summary['screened_batches'] = []
        with self.assertRaises(launcher.IntegrationError) as error:
            launcher.validate_boundary(self.fx.run, self.fx.auth, summary,
                                       {'actual_target_exit': {'pid': 9001, 'exit_code': 1}})
        self.assertEqual(error.exception.code, 'S160_EXACT_PREFIX')
        summary = json.loads((self.fx.run / 'diagnostic-summary.json').read_bytes())
        summary['screened_batches'][0]['gate']['sha256'] = '0' * 64
        with self.assertRaises(launcher.IntegrationError) as error:
            launcher.validate_boundary(self.fx.run, self.fx.auth, summary,
                                       {'actual_target_exit': {'pid': 9001, 'exit_code': 1}})
        self.assertEqual(error.exception.code, 'S160_RAW_HASH_BINDING')

    def test_failure_exit_is_distinct_from_boundary_and_stop_is_preserved(self):
        self.fx.prepare()
        # A helper that exits without a valid summary is a failure exit.
        class EmptyOwner(Owner):
            def tick(self, stop=False):
                self.process.returncode = 1
                return 1
        self.services.spawn = lambda argv, **kwargs: EmptyOwner(self.fx)
        record = launcher.launch_existing(self.fx.run, self.services,
                                          freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(record['status'], 'FAILURE')
        self.assertEqual(record['launcher_exit'], 1)
        self.assertFalse(record['boundary_permitted'])

        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        self.fx = Fixture(other)
        self.fx.prepare('gt06-s160-diag-stop1')
        self.fx.stop()
        record = launcher.launch_existing(self.fx.run, self.fx.services,
                                          freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(record['status'], 'STOPPED')
        self.assertEqual(record['launcher_exit'], 2)
        self.assertEqual(record['stop']['before_terminal'], True)
        self.assertFalse(record['boundary_permitted'])

    def test_child_path_reauthenticates_without_starting_engine(self):
        self.fx.prepare()
        auth = self.fx.auth
        claim = {'schema': 'HH-S160-dispatch-claim-1', 'bindings': launcher.bindings(auth),
                 **launcher.FLAGS}
        launcher.publish(self.fx.run / 'dispatch-claim.json', claim)

        class Observer:
            class EditorCensus:
                def __init__(self, *args): self.root = Path(args[0])
                def observe(self, *args): return None
            class BoundaryStop(Exception): pass
            @staticmethod
            @contextmanager
            def installed(campaign, census):
                yield census

        class Campaign:
            @staticmethod
            def run_child(root):
                raise Observer.BoundaryStop()

        code = launcher.run_child(self.fx.run, self.fx.services,
                                  freeze_sha256=self.fx.freeze_sha,
                                  campaign=Campaign(), observer=Observer(), adapter=object(),
                                  script_path=self.fx.run / 'helpers/driver.py', pid=9001)
        self.assertEqual(code, 1)
        summary = json.loads((self.fx.run / 'diagnostic-summary.json').read_bytes())
        self.assertTrue(summary['reauthenticated'])
        self.assertEqual(summary['status'], 'BOUNDARY_CAPTURED')

    def test_post_run_reauthentication_rejects_source_drift(self):
        self.fx.prepare()
        class DriftOwner(Owner):
            def close(inner):
                super().close()
                (self.fx.root / 'studio/pin.txt').write_bytes(b'changed-after-run')
        self.services.spawn = lambda argv, **kwargs: DriftOwner(self.fx)
        record = launcher.launch_existing(self.fx.run, self.services,
                                          freeze_sha256=self.fx.freeze_sha)
        self.assertEqual(record['status'], 'FAILURE')
        self.assertEqual(record['launcher_exit'], 1)
        self.assertFalse(record['boundary_permitted'])
        self.assertFalse(record['reauthenticated'])


if __name__ == '__main__':
    unittest.main()
