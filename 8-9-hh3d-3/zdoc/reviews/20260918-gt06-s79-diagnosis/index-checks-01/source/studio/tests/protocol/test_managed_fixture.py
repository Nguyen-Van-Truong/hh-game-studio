"""Durable supervised fixture restart with real native storage/registry."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.custody import decode_record, encode_record, CustodyError
from host.core.custody_registry import BASE_PATH, RegistryCustody
from host.core.managed_fixture import ManagedFixtureOwner, ManagedFixtureError
from host.core.limits import Request, payload_digest, SafetyViolation


@unittest.skipUnless(os.name == 'nt', 'Windows custody/NTFS fixture required')
class ManagedFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-managed-')
        self.addCleanup(self.temp.cleanup)
        self.owner = ManagedFixtureOwner.create(self.temp.name, project_id='project-one',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        self.storage_id = self.owner.storage_id
        self.addCleanup(self.delete_key)
        self.addCleanup(lambda: self.owner.close())

    def delete_key(self):
        import winreg
        # The exact UUID was returned by this test's create, never enumerated.
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, BASE_PATH+'\\'+self.storage_id, winreg.KEY_WOW64_64KEY)

    def request(self, name='cmd-one', value='one', now=100):
        selector = self.owner.selector
        lease = selector.lease('owner', now_ms=now)
        state = selector.snapshot()
        payload = {'assets':{'scene':{'value':value,'references':[]}},'entrypoint':'scene',
                   'expected_generation':state['generation'],'expected_selection_hash':state['selection_hash'],
                   **{'expected_'+key:value for key,value in state['revisions'].items()}}
        target = {'stable_id':'active-release'}
        return Request(name,'project-one','fixture.release.activate',lease['lease_id'],lease['fencing_epoch'],
                       state['revisions']['game_revision'],target,payload,
                       payload_digest('fixture.release.activate',target,payload,'hh-studio-0.1'),10_000).as_dict()

    def activate(self, request, now=101):
        selector, name = self.owner.selector, request['command_id']
        selector.prepare(request, now_ms=now)
        selector.stage(name, now_ms=now+1)
        selector.select(name, now_ms=now+2)
        return selector.adopt(name, now_ms=now+3)

    def reopen(self, now=200):
        self.owner.close()
        self.owner = ManagedFixtureOwner.reopen(self.storage_id, project_id='project-one', now_ms=now)

    def test_terminal_restart_rearms_fresh_command_and_keeps_original_receipts(self):
        request = self.request()
        receipt = self.activate(request)
        first = self.owner.files.read('active.json')
        self.assertEqual(self.owner.custody.binding.witnessed, self.owner.log.binding().witnessed)
        self.reopen()
        self.assertEqual(self.owner.files.read('active.json'), first)
        self.assertTrue(self.owner.selector.snapshot()['ready'])
        self.assertEqual(self.owner.selector.prepare(request, now_ms=201), receipt)
        second = self.request('cmd-two','two',now=202)
        second_receipt = self.activate(second,now=203)
        self.assertEqual(second_receipt['status'], 'COMMITTED')
        self.assertFalse(first[0].identity.same_file(self.owner.files.read('active.json')[0].identity))
        self.reopen(now=300)
        self.assertEqual(self.owner.selector.lookup('cmd-one'), receipt)
        self.assertEqual(self.owner.selector.lookup('cmd-two'), second_receipt)
        self.assertEqual(self.owner.consumer.adoption_count, 1)

    def test_stop_restart_keeps_write_hold_and_never_resumes(self):
        request = self.request()
        receipt = self.activate(request)
        self.owner.selector.stop()
        before = self.owner.files.read('active.json')
        self.reopen()
        self.assertTrue(self.owner.selector.snapshot()['stopped'])
        self.assertEqual(self.owner.selector.lookup('cmd-one'), receipt)
        self.assertEqual(self.owner.files.read('active.json'), before)
        with self.assertRaises(SafetyViolation):
            self.owner.files.check_mutation_available()

    def test_pending_restart_preserves_file_and_denies_fresh_admission(self):
        self.activate(self.request())
        before = self.owner.files.read('active.json')
        request = self.request('cmd-pending', 'two',now=110)
        self.owner.selector.prepare(request,now_ms=111)
        self.reopen()
        self.assertEqual(self.owner.selector.lookup('cmd-pending')['status'],'ACCEPTED_PENDING')
        self.assertEqual(self.owner.files.read('active.json'), before)
        self.assertEqual(self.owner.consumer.adoption_count,0)
        with self.assertRaises(SafetyViolation):
            self.owner.files.check_mutation_available()

    def test_custody_failure_after_terminal_write_is_unknown_then_confirms_once(self):
        request = self.request()
        selector = self.owner.selector
        selector.prepare(request,now_ms=101);selector.stage('cmd-one',now_ms=102);selector.select('cmd-one',now_ms=103)
        with mock.patch.object(self.owner.registry,'store',side_effect=SafetyViolation('TEST_CUSTODY_FAILURE')):
            with self.assertRaises(SafetyViolation) as caught:
                selector.adopt('cmd-one',now_ms=104)
        self.assertTrue(caught.exception.outcome_unknown)
        before = self.owner.files.read('active.json')
        self.reopen()
        self.assertEqual(self.owner.files.read('active.json'), before)
        self.assertEqual(self.owner.selector.lookup('cmd-one')['status'],'COMMITTED')
        self.assertEqual(self.owner.consumer.adoption_count,1)

    def test_whole_record_loss_below_durable_witness_is_rejected(self):
        self.activate(self.request())
        log_path = self.owner.log.root/'.events'
        tail = self.owner.log._index[-2][2].size
        self.owner.close()
        with log_path.open('r+b') as stream:
            stream.truncate(tail);stream.flush();os.fsync(stream.fileno())
        with self.assertRaises(ManagedFixtureError) as caught:
            ManagedFixtureOwner.reopen(self.storage_id,project_id='project-one',now_ms=200)
        caught.exception.cleanup_owner.close()
        self.assertEqual(log_path.stat().st_size,tail)

    def test_corrupt_or_swapped_custody_never_opens_new_roots(self):
        raw=self.owner.registry.read()
        record=decode_record(raw)
        invalid=copy.deepcopy(record);invalid['files']['identity']=invalid['blobs']['identity']
        with self.assertRaises(CustodyError):encode_record(invalid)
        damaged=bytearray(raw);damaged[len(damaged)//2]^=1
        with self.assertRaises(CustodyError):decode_record(bytes(damaged))
        self.owner.registry.store(bytes(damaged),expected=raw)
        roots=sorted(p.name for p in Path(self.temp.name).iterdir())
        self.owner.close()
        with self.assertRaises(ManagedFixtureError) as caught:
            ManagedFixtureOwner.reopen(self.storage_id,project_id='project-one',now_ms=200)
        caught.exception.cleanup_owner.close()
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()),roots)

    def test_actual_process_exit_reopens_only_from_durable_storage_id(self):
        request=self.request();receipt=self.activate(request)
        storage_id=self.storage_id
        self.owner.close()
        code='''import json,os,sys
from host.core.managed_fixture import ManagedFixtureOwner
from host.core.limits import Request,payload_digest
owner=ManagedFixtureOwner.reopen(sys.argv[1],project_id='project-one',now_ms=200)
selector=owner.selector;lease=selector.lease('child',now_ms=201);state=selector.snapshot()
payload={'assets':{'scene':{'value':'child','references':[]}},'entrypoint':'scene','expected_generation':state['generation'],'expected_selection_hash':state['selection_hash'],**{'expected_'+k:v for k,v in state['revisions'].items()}}
target={'stable_id':'active-release'}
r=Request('cmd-child','project-one','fixture.release.activate',lease['lease_id'],lease['fencing_epoch'],state['revisions']['game_revision'],target,payload,payload_digest('fixture.release.activate',target,payload,'hh-studio-0.1'),10000).as_dict()
selector.prepare(r,now_ms=202);selector.stage('cmd-child',now_ms=203);selector.select('cmd-child',now_ms=204);selector.adopt('cmd-child',now_ms=205)
os._exit(87)
'''
        child=subprocess.run([sys.executable,'-B','-c',code,storage_id],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(child.returncode,87,child.stderr.decode(errors='replace'))
        self.owner=ManagedFixtureOwner.reopen(storage_id,project_id='project-one',now_ms=300)
        self.assertEqual(self.owner.selector.lookup('cmd-one'),receipt)
        self.assertEqual(self.owner.selector.lookup('cmd-child')['status'],'COMMITTED')
        self.assertEqual(json.loads(self.owner.files.read('active.json')[1])['assets']['scene']['value'],'child')
        print('HH_GT02_MANAGED_PROCESS_CUT '+json.dumps({'exit':child.returncode,'recovery_source':'protected_registry_only'}),flush=True)

    def test_invalid_setup_is_rejected_before_registry_or_root_creation(self):
        initial={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'}
        before=sorted(p.name for p in Path(self.temp.name).iterdir())
        with mock.patch.object(RegistryCustody,'provision_base',side_effect=AssertionError('no provisioning')):
            for project,revisions in [('bad:project',initial),('project-two',{**initial,'source_sha256':'x'*64})]:
                with self.subTest(project=project),self.assertRaises(SafetyViolation):
                    ManagedFixtureOwner.create(self.temp.name,project_id=project,initial_revisions=revisions)
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()),before)

    def test_poisoned_custody_retries_remain_unknown_without_writes(self):
        custody=self.owner.custody
        request=self.request()
        with mock.patch.object(self.owner.registry,'store',side_effect=SafetyViolation('TEST_FAILURE')) as store:
            with self.assertRaises(SafetyViolation) as caught:
                self.owner.selector.prepare(request,now_ms=101)
            self.assertTrue(caught.exception.outcome_unknown)
            writes=store.call_count
            for action in (lambda:custody.record,lambda:custody.binding,custody.confirm_current,
                           lambda:custody.persist_binding(None)):
                with self.assertRaises(CustodyError) as retry:
                    action()
                self.assertTrue(retry.exception.outcome_unknown)
            self.assertEqual(store.call_count,writes)

    def test_restart_fences_unexpired_old_lease_before_new_session(self):
        original=self.request()
        self.activate(original)
        self.reopen(now=200)  # old owner TTL was 30 seconds, still unexpired
        state=self.owner.selector.snapshot()
        stale=copy.deepcopy(original);stale['command_id']='stale-after-restart'
        stale['expected_revision']=state['revisions']['game_revision']
        stale['payload'].update(expected_generation=state['generation'],expected_selection_hash=state['selection_hash'],
                                **{'expected_'+k:v for k,v in state['revisions'].items()})
        stale['payload_hash']=payload_digest(stale['operation'],stale['target'],stale['payload'],stale['schema_version'])
        head=self.owner.log.binding().witnessed
        with self.assertRaises(SafetyViolation):self.owner.selector.prepare(stale,now_ms=200)
        self.assertEqual(self.owner.log.binding().witnessed,head)
        lease=self.owner.selector.lease('new-session',now_ms=202)
        self.assertGreater(lease['fencing_epoch'],original['fencing_epoch'])
        self.assertNotEqual(lease['lease_id'],original['lease_id'])

    def test_rearm_refuses_orphan_namespace_without_overwriting_or_deleting(self):
        self.activate(self.request())
        root=self.owner.files.root
        self.owner.close()
        orphan=root/'.hh-stage-orphan'
        orphan.write_bytes(b'preserve')
        with self.assertRaises(ManagedFixtureError) as caught:
            ManagedFixtureOwner.reopen(self.storage_id,project_id='project-one',now_ms=200)
        caught.exception.cleanup_owner.close()
        self.assertEqual(orphan.read_bytes(),b'preserve')

    def test_second_owner_cannot_change_custody_while_guard_is_owned(self):
        raw=self.owner.registry.read()
        with self.assertRaises(ManagedFixtureError) as caught:
            ManagedFixtureOwner.reopen(self.storage_id,project_id='project-one',now_ms=200)
        caught.exception.cleanup_owner.close()
        self.assertEqual(self.owner.registry.read(),raw)


if __name__ == '__main__':
    unittest.main(verbosity=2)
