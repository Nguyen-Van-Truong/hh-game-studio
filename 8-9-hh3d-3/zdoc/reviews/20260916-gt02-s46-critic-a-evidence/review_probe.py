"""Read-only-source independent critic A check; run under the owned runner."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import unittest

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
STUDIO = PRODUCT / 'studio'
REVIEWS = HERE.parent
EXPECTED = 'f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf'
sys.path[:0] = [str(PRODUCT), str(STUDIO/'tests/protocol')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    freeze = json.loads((REVIEWS/'20260916-gt02-s46-01/source-closure.json').read_text())
    files = freeze['files']
    assert len(files) == 106
    rows = ''.join(sorted('8-9-hh3d-3/studio/'+name+'\0'+digest+'\n' for name,digest in files.items()))
    assert hashlib.sha256(rows.encode()).hexdigest() == EXPECTED == freeze['source_closure_sha256']
    assert all(sha(STUDIO/name) == digest for name,digest in files.items())
    spec = importlib.util.spec_from_file_location('candidate_manifest',STUDIO/'tests/protocol/run_gt02_candidate.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.source_manifest() == files
    candidate_dir = REVIEWS/'20260916-gt02-s46-01'
    candidate = json.loads((candidate_dir/'candidate.json').read_text())
    assert candidate['source_closure_sha256'] == EXPECTED and candidate['source_unchanged']
    for name,digest in candidate['artifacts'].items():
        assert sha(candidate_dir/name) == digest, name
    suites = []
    for lane in candidate['lanes']:
        host = lane['host']
        captured = json.loads((candidate_dir/host['host']).read_text())
        assert host['exit_code'] == captured['exit_code'] == host['wrapper_exit_code'] == 0
        assert host['target_pid'] == captured['target_pid']
        assert host['tree_verified'] and not host['timed_out']
        summary = lane['summary']
        assert summary['failures'] == summary['errors'] == 0
        suites.append({'suite':lane['suite'],'tests':summary['tests_run'],'skips':summary['skips'],
                       'exit':captured['exit_code'],'tree_verified':host['tree_verified']})
    native = []
    for folder,label,expected_exit in (
        ('20260916-gt02-s46-native','managed-native',86),
        ('20260916-gt02-s46-boundary','native',67),
        ('20260916-gt02-s46-registry-native','registry-native',89)):
        path = REVIEWS/folder/'run-01'
        out = json.loads((path/(label+'-stdout.txt')).read_text())
        cap = json.loads((path/'capture.json').read_text())
        host = json.loads((path/(label+'-host.json')).read_text())
        assert out['runtime_closure']['files'] == files
        assert out['runtime_closure']['source_closure_sha256'] == EXPECTED
        assert host['exit_code'] == cap['host']['exit_code'] == cap['host']['wrapper_exit_code'] == 0
        assert host['target_pid'] == cap['host']['target_pid']
        assert cap['host']['tree_verified'] and not cap['host']['timed_out']
        assert (path/(label+'-stderr.txt')).read_bytes() == b''
        assert cap['job_samples'][-1]['active'] == 0 and cap['job_samples'][-1]['pids'] == []
        cases = out.get('cases',[out])
        for case in cases:
            assert case['final_host_exit'] == case['host_exit'] == expected_exit
            assert case['final_job_active'] == 0 and case['final_job_pids'] == []
            assert not case.get('forced_owned_termination') and 'error' not in case
        assert out.get('runtime_source_unchanged',out.get('source_unchanged'))
        assert out.get('runtime_snapshot_unchanged',out.get('snapshot_unchanged'))
        assert out.get('runtime_snapshot_removed',out.get('snapshot_removed'))
        for item in out.get('loaded_runtime_modules',{}).values():
            assert files[item['relative']] == item['sha256']
        native.append({'package':folder,'exact_file_map':True,'cases':len(cases),
                       'native_exits':[c['final_host_exit'] for c in cases],'host_exit':host['exit_code']})
    return {'closure':EXPECTED,'file_count':len(files),'artifact_count':len(candidate['artifacts']),
            'suites':suites,'native':native}

from test_selector_public import SelectorPublicTests, fixture_frame
from studio.protocol.core import canonical_bytes
from studio.host.core.limits import payload_digest
from studio.host.core.selector_pipe import SelectorPipeServer

class IndependentAdmission(SelectorPublicTests):
    def test_adversarial_variants_never_append_or_publish(self):
        base = self.request('critic.valid')
        before = self.observe()
        old = self.credential
        self.credential = self.broker.sessions.rotate(old)
        self.server = SelectorPipeServer(self.work,self.broker,self.credential)
        self.control_server = SelectorPipeServer(self.control,self.broker,self.credential)
        variants = []
        def add(name, mutate):
            body=copy.deepcopy(base); body['command_id']='critic.'+name
            mutate(body)
            body['payload_hash']=payload_digest(body['operation'],body['target'],body['payload'],body['schema_version'])
            variants.append((name,body))
        add('operation',lambda b:b.update(operation='os.execute'))
        add('path',lambda b:b.update(target={'path':'../../outside'}))
        add('boolgeneration',lambda b:b['payload'].update(expected_generation=True))
        add('dangling',lambda b:b['payload']['assets']['scene'].update(references=['missing']))
        add('extraassetfield',lambda b:b['payload']['assets']['scene'].update(extra=1))
        add('stalegame',lambda b:b.update(expected_revision='game-stale'))
        add('expired',lambda b:b.update(deadline_ms=1))
        add('retiredbearer',lambda b:b['payload']['assets']['scene'].update(value=old.bearer))
        add('hostpath',lambda b:b['payload']['assets']['scene'].update(value=str(self.owner.files.root)))
        add('oversize',lambda b:b['payload']['assets']['scene'].update(value='x'*9000))
        rows=[]
        for name,body in variants:
            reply=self.rpc('/v1/commands',body)
            self.assertEqual(reply['status'],'REJECTED',name)
            self.assertEqual(self.observe(),before,name)
            self.assertIsNone(self.owner.selector.lookup(body['command_id']),name)
            encoded=canonical_bytes(reply)
            self.assertNotIn(old.bearer.encode(),encoded)
            self.assertNotIn(self.credential.bearer.encode(),encoded)
            rows.append({'case':name,'code':reply['code'],'intent_absent':True,'state_unchanged':True})
        body=canonical_bytes(base)
        for name,raw in [('duplicate',body[:-1]+b',"command_id":"second"}'),
                         ('nonfinite',body.replace(b'"value":"one"',b'"value":NaN')),
                         ('utf8',b'{"project_id":"\xff"}')]:
            wire=('Bearer '+self.credential.bearer+'\n/v1/commands\n').encode()+raw
            reply=self.rpc('/v1/commands',{},raw=wire)
            self.assertEqual(reply['status'],'REJECTED',name)
            self.assertEqual(self.observe(),before,name)
            rows.append({'case':name,'code':reply['code'],'state_unchanged':True})
        (HERE/'admission-rows.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':
    result=verify()
    suite=unittest.TestSuite([IndependentAdmission('test_adversarial_variants_never_append_or_publish')])
    selected = {
        'test_selector_public': ['test_internal_broker_and_unbound_or_closed_owner_cannot_register',
            'test_registration_is_rechecked_after_custody_detaches',
            'test_authentication_revocation_roles_and_versions_reject_without_events',
            'test_revoked_control_cannot_signal_stop_or_cancel'],
        'test_managed_service': ['test_late_read_cannot_dispatch_before_watchdog_observes_expiry',
            'test_deadline_revokes_admission_even_while_phase_pump_is_blocked'],
        'test_safe_replace': ['test_hardlinked_target_rejects_and_outside_bytes_stay_unchanged',
            'test_owner_swap_before_open_is_detected_and_preserves_contender'],
    }
    for module_name,names in selected.items():
        mod=__import__(module_name)
        classes=[v for v in vars(mod).values() if isinstance(v,type) and issubclass(v,unittest.TestCase)]
        for name in names:
            cls=next(c for c in classes if hasattr(c,name))
            suite.addTest(cls(name))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_redaction'))
    run=unittest.TextTestRunner(verbosity=2).run(suite)
    result['focused']={'tests':run.testsRun,'failures':len(run.failures),'errors':len(run.errors),'skips':len(run.skipped)}
    result['after']=verify()
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('CRITIC_A_COMPLETE '+json.dumps(result))
    sys.exit(0 if run.wasSuccessful() else 1)
