"""Selector journal + protected-file publication; fixed inert fixture only."""
import json
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from host.core.fixture_selector import FixtureSelector, FixtureReleaseConsumer, FileFixtureReleaseConsumer, SelectorError
from host.core.private_events import PrivateEventLog, EventBinding, EventHead
from host.core.private_store import PrivateBlobStore
from host.core.safe_replace import ProtectedFileRoot, SafeReplaceError
from host.core.safe_open import FileIdentity
from host.core.limits import Request, payload_digest, SafetyViolation


@unittest.skipUnless(os.name == 'nt', 'Windows NTFS selector file fixture required')
class FileConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-file-consumer-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.file_parent = self.base/'managed-files'
        self.file_parent.mkdir()
        self.alternate_parent = self.base/'alternate-files'
        self.alternate_parent.mkdir()
        self.files = ProtectedFileRoot.create(self.file_parent)
        self.addCleanup(lambda: self.files.close())
        self.log = PrivateEventLog.create(self.base)
        self.addCleanup(lambda: self.log.close())
        self.store = PrivateBlobStore.create(self.base)
        self.addCleanup(self.store.close)
        self.consumer = FileFixtureReleaseConsumer('project-one', self.files)
        self.addCleanup(lambda: self.consumer.close())
        self.selector = FixtureSelector(self.log, self.store, self.consumer, project_id='project-one',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        self.addCleanup(lambda: self.selector.close())
        self.lease = self.selector.lease('owner', now_ms=100)

    def request(self, identifier='cmd-one', value='one'):
        snap = self.selector.snapshot()
        payload = {'assets':{'scene':{'value':value,'references':[]}},'entrypoint':'scene',
                   'expected_generation':snap['generation'],'expected_selection_hash':snap['selection_hash'],
                   **{'expected_'+k:v for k,v in snap['revisions'].items()}}
        target = {'stable_id':'active-release'}
        return Request(identifier,'project-one','fixture.release.activate',self.lease['lease_id'],self.lease['fencing_epoch'],
            snap['revisions']['game_revision'],target,payload,payload_digest('fixture.release.activate',target,payload,'hh-studio-0.1'),10_000).as_dict()

    def prepare_selection(self, request):
        name = request['command_id']
        self.selector.prepare(request, now_ms=101)
        self.selector.stage(name, now_ms=102)
        self.selector.select(name, now_ms=103)

    def activate(self, request):
        self.prepare_selection(request)
        return self.selector.adopt(request['command_id'], now_ms=104)

    def reopen(self):
        log_root, log_binding = self.log.root, self.log.binding()
        file_root, file_identity = self.files.root, self.files.root_identity
        self.selector.close(); self.consumer.close(); self.files.close(); self.log.close()
        self.files = ProtectedFileRoot.reopen_readonly(file_root, file_identity)
        self.log = PrivateEventLog.reopen(log_root, log_binding)
        self.consumer = FileFixtureReleaseConsumer('project-one', self.files)
        self.selector = FixtureSelector(self.log, self.store, self.consumer, project_id='project-one')
        self.lease = self.selector.lease('owner', now_ms=200)

    def test_commit_reads_actual_file_then_second_revision_replaces_once(self):
        first_receipt = self.activate(self.request())
        first, raw = self.files.read('active.json')
        self.assertEqual(first_receipt['status'], 'COMMITTED')
        self.assertEqual(json.loads(raw)['assets']['scene']['value'], 'one')
        second_request = self.request('cmd-two', 'two')
        # The trusted clock must remain monotonic between transactions.
        self.selector.prepare(second_request, now_ms=105)
        self.selector.stage('cmd-two', now_ms=106)
        self.selector.select('cmd-two', now_ms=107)
        self.assertEqual(self.files.read('active.json'), (first, raw))
        receipt = self.selector.adopt('cmd-two', now_ms=108)
        second, actual = self.files.read('active.json')
        self.assertEqual(receipt['status'], 'COMMITTED')
        self.assertFalse(first.identity.same_file(second.identity))
        self.assertEqual(json.loads(actual)['assets']['scene']['value'], 'two')
        with mock.patch.object(self.files, 'atomic_replace', side_effect=AssertionError('must not replay')):
            self.assertEqual(self.selector.prepare(second_request, now_ms=109), receipt)
        self.assertEqual(self.consumer.adoption_count, 2)

    def test_terminal_loss_reconciles_same_bytes_without_rewrite(self):
        request = self.request()
        self.prepare_selection(request)
        original = self.selector._append
        def fail_terminal(event):
            if event['kind'] == 'TERMINAL':
                raise SafetyViolation('INJECTED_TERMINAL_LOSS')
            return original(event)
        with mock.patch.object(self.selector, '_append', side_effect=fail_terminal):
            with self.assertRaisesRegex(SelectorError, 'ADOPTION_UNKNOWN'):
                self.selector.adopt('cmd-one', now_ms=104)
        version, raw = self.files.read('active.json')
        self.reopen()
        self.assertEqual(self.selector.lookup('cmd-one')['status'], 'UNKNOWN')
        self.assertIsNone(self.consumer.readback())
        with mock.patch.object(self.files, 'atomic_replace', side_effect=AssertionError('no rewrite')), \
             mock.patch.object(self.files, 'create_new', side_effect=AssertionError('no recreate')):
            receipt = self.selector.reconcile('cmd-one', 'adopt', now_ms=201)
        self.assertEqual(receipt['status'], 'COMMITTED')
        self.assertEqual(self.files.read('active.json'), (version, raw))
        self.assertTrue(self.selector.snapshot()['ready'])

    def test_recovery_barrier_failure_cannot_be_a_commit(self):
        self.activate(self.request())
        self.reopen()
        with mock.patch.object(self.files._api, 'flush_directory', side_effect=SafetyViolation('INJECTED_BARRIER')):
            with self.assertRaisesRegex(SelectorError, 'ADOPTION_UNKNOWN'):
                self.selector.load_committed(now_ms=201)
        self.assertIsNone(self.consumer.readback())
        with self.assertRaisesRegex(SafeReplaceError, 'RECONCILIATION_REQUIRED'):
            self.files.read('active.json')

    def test_load_committed_confirms_file_without_new_effect_or_receipt(self):
        receipt = self.activate(self.request())
        version, raw = self.files.read('active.json')
        self.reopen()
        before = self.log.binding().witnessed
        self.selector.load_committed(now_ms=201)
        self.assertEqual(self.log.binding().witnessed, before)
        self.assertEqual(self.files.read('active.json'), (version, raw))
        self.assertEqual(self.selector.lookup('cmd-one'), receipt)
        self.assertTrue(self.selector.snapshot()['ready'])
        with self.assertRaisesRegex(SafeReplaceError, 'REQUIRES_RECONCILIATION'):
            self.files.atomic_replace('active.json', b'cannot-unlock-write', expected=version)

    def test_wrong_managed_root_and_memory_consumer_cannot_rebind_journal(self):
        self.activate(self.request())
        self.selector.close()
        with self.assertRaisesRegex(SelectorError, 'BINDING_MISMATCH'):
            FixtureSelector(self.log, self.store, FixtureReleaseConsumer('project-one'), project_id='project-one')
        with ProtectedFileRoot.create(self.alternate_parent) as other:
            alternate = FileFixtureReleaseConsumer('project-one', other)
            try:
                with self.assertRaisesRegex(SelectorError, 'BINDING_MISMATCH'):
                    FixtureSelector(self.log, self.store, alternate, project_id='project-one')
            finally:
                alternate.close()

    def test_second_consumer_and_close_while_bound_reject(self):
        with self.assertRaisesRegex(SelectorError, 'ROOT_ALREADY_BOUND'):
            FileFixtureReleaseConsumer('project-one', self.files)
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STILL_BOUND'):
            self.consumer.close()

    def test_out_of_band_file_change_never_reads_as_verified_consumer(self):
        self.activate(self.request())
        (self.files.root/'active.json').write_bytes(b'owner-change')
        with self.assertRaisesRegex(SelectorError, 'READBACK_FAILED'):
            self.consumer.readback()

    def test_stop_before_adoption_leaves_existing_file_unchanged(self):
        self.activate(self.request())
        before = self.files.read('active.json')
        request = self.request('cmd-two', 'two')
        self.selector.prepare(request, now_ms=105)
        self.selector.stage('cmd-two', now_ms=106)
        self.selector.select('cmd-two', now_ms=107)
        self.selector.stop()
        with self.assertRaisesRegex(SelectorError, 'SELECTOR_STOPPED'):
            self.selector.adopt('cmd-two', now_ms=108)
        self.assertEqual(self.files.read('active.json'), before)
        self.assertEqual(self.selector.lookup('cmd-two')['status'], 'UNKNOWN')

    def test_actual_crash_between_replace_and_terminal_reconciles_without_rewrite(self):
        # stdout carries a trusted test witness, not a production custody claim.
        script = r'''import json,os,sys
from dataclasses import asdict
from pathlib import Path
from host.core.fixture_selector import FixtureSelector,FileFixtureReleaseConsumer
from host.core.private_events import PrivateEventLog
from host.core.private_store import PrivateBlobStore
from host.core.safe_replace import ProtectedFileRoot
from host.core.limits import Request,payload_digest
c=json.loads(sys.stdin.read()); parent=Path(c['parent']); parent.mkdir()
fp=parent/'files'; fp.mkdir(); files=ProtectedFileRoot.create(fp)
log=PrivateEventLog.create(parent); store=PrivateBlobStore.create(parent)
consumer=FileFixtureReleaseConsumer('project-one',files)
selector=FixtureSelector(log,store,consumer,project_id='project-one',initial_revisions={
 'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
lease=selector.lease('owner',now_ms=100)
def prepare(identifier,value,now):
 snap=selector.snapshot()
 payload={'assets':{'scene':{'value':value,'references':[]}},'entrypoint':'scene',
  'expected_generation':snap['generation'],'expected_selection_hash':snap['selection_hash'],
  **{'expected_'+k:v for k,v in snap['revisions'].items()}}
 target={'stable_id':'active-release'}
 request=Request(identifier,'project-one','fixture.release.activate',lease['lease_id'],lease['fencing_epoch'],
  snap['revisions']['game_revision'],target,payload,payload_digest('fixture.release.activate',target,payload,'hh-studio-0.1'),10_000).as_dict()
 selector.prepare(request,now_ms=now); selector.stage(identifier,now_ms=now+1); selector.select(identifier,now_ms=now+2)
 return request
prepare('first','before',101); selector.adopt('first',now_ms=104)
request=prepare('second','after',105)
def cut():
 print(json.dumps({'marker':'FILE_SELECTOR_CUT','phase':c['phase'],'pid':os.getpid(),
  'log_root':str(log.root),'binding':asdict(log.binding()),'store_root':str(store.root),
  'store_identity':asdict(store.root_identity),'files_root':str(files.root),
  'files_identity':asdict(files.root_identity),'request':request}),flush=True)
 os._exit(83)
if c['phase'] in ('before_rename','after_rename'):
 original=files._api.rename
 def rename(h,p,**kw):
  if c['phase']=='before_rename': cut()
  original(h,p,**kw); cut()
 files._api.rename=rename
else:
 original=selector._append
 def append(event):
  original(event)
  if event['kind']=='TERMINAL': cut()
 selector._append=append
selector.adopt('second',now_ms=108)
raise AssertionError('cut not reached')
'''
        for phase in ('before_rename', 'after_rename', 'after_terminal'):
            with self.subTest(phase=phase):
                child = subprocess.Popen([sys.executable, '-B', '-c', script], cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    stdout, stderr = child.communicate(json.dumps({'phase':phase,'parent':str(self.base/phase)}), timeout=20)
                except subprocess.TimeoutExpired:
                    child.kill(); child.communicate(timeout=5)
                    raise
                self.assertEqual(child.returncode, 83, stderr)
                self.assertEqual(stderr, '')
                c = json.loads(stdout)
                self.assertEqual((c['marker'],c['phase'],c['pid']), ('FILE_SELECTOR_CUT',phase,child.pid))
                b = c['binding']
                binding = EventBinding(FileIdentity(**b['root']),FileIdentity(**b['stream']),EventHead(**b['witnessed']))
                with ExitStack() as stack:
                    files = stack.enter_context(ProtectedFileRoot.reopen_readonly(c['files_root'],FileIdentity(**c['files_identity'])))
                    log = stack.enter_context(PrivateEventLog.reopen(c['log_root'],binding))
                    store = stack.enter_context(PrivateBlobStore.reopen(c['store_root'],FileIdentity(**c['store_identity'])))
                    consumer = FileFixtureReleaseConsumer('project-one',files); stack.callback(consumer.close)
                    selector = FixtureSelector(log,store,consumer,project_id='project-one'); stack.callback(selector.close)
                    before = files.read('active.json')
                    selector.lease('owner',now_ms=200)
                    status = selector.lookup('second')['status']
                    self.assertEqual(status, 'COMMITTED' if phase=='after_terminal' else 'UNKNOWN')
                    with mock.patch.object(files,'atomic_replace',side_effect=AssertionError('no replay')):
                        if phase=='before_rename':
                            with self.assertRaisesRegex(SelectorError,'ADOPTION_UNKNOWN'):
                                selector.reconcile('second','adopt',now_ms=201)
                            self.assertEqual(selector.lookup('second')['status'],'UNKNOWN')
                        elif phase=='after_rename':
                            self.assertEqual(selector.reconcile('second','adopt',now_ms=201)['status'],'COMMITTED')
                        else:
                            head = log.binding().witnessed
                            selector.load_committed(now_ms=201)
                            self.assertEqual(log.binding().witnessed,head)
                    self.assertEqual(files.read('active.json'), before)
                    self.assertEqual(json.loads(before[1])['assets']['scene']['value'], 'before' if phase=='before_rename' else 'after')
                    print('HH_GT02_FILE_SELECTOR_CUT '+json.dumps({'phase':phase,'host_pid':child.pid,'host_exit':child.returncode,
                        'status_before':status,'status_after':selector.lookup('second')['status'],'file_id_unchanged':True}),flush=True)


if __name__ == '__main__':
    unittest.main()
