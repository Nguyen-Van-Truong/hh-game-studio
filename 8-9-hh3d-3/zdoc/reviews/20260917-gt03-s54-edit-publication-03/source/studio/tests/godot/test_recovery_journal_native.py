"""Windows storage cut tests; all engine/authority facts are synthetic."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

PROJECT=Path(__file__).resolve().parents[3];STUDIO=PROJECT/'studio'
sys.path.insert(0,str(PROJECT))


def load(name,path,*,virtual=None):
    spec=importlib.util.spec_from_file_location(name,virtual or path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    if virtual:exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    else:spec.loader.exec_module(module)
    return module


helpers=load('recovery_native_v4_helpers',STUDIO/'tests/godot/test_publication_journal_v4.py')
recovery=load('recovery_native_module',STUDIO/'godot-addon/publication_recovery.py')
runner=load('recovery_native_owned_runner',STUDIO/'build/bootstrap/run_fixture.py')
from studio.protocol.core import canonical_bytes,parse_json


def clock():return time.time_ns()//1_000_000


def child_commit_crash(parent,storage_id):
    helper=helpers.JournalV4Tests('test_script_whole_bundle_cas_exact_response_then_readonly_reopen')
    helper.base=Path(parent);helper.storage_id=storage_id;helper.owners=[]
    owner=helper.create();helper.activate(owner)
    owner.select_prepared('command.one',helpers.fixtures.rev('command.one'),observed_ms=clock())
    at=clock();owner.readback('command.one',helpers.fixtures.rev('command.one'),helpers.fixtures.adoption_facts(helper.command(owner),at),observed_ms=at)
    print('RECOVERY_CRASH_BEFORE_COMMIT '+json.dumps({'storage_id':storage_id,'phase':helper.command(owner)['phase']}),flush=True)
    # PrivateEventLog has already written, flushed and read back COMMITTED
    # before it calls persist_binding. Die without Python cleanup or ACK.
    with mock.patch.object(owner._custody,'persist_binding',side_effect=lambda binding:os._exit(91)):
        owner.commit('command.one',helpers.fixtures.rev('command.one'),observed_ms=clock())
    raise AssertionError('crash injection did not execute')


@unittest.skipUnless(os.name=='nt','actual Windows Registry and native readonly roots required')
class RecoveryJournalNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):helpers.RegistryCustody.provision_base()

    setUp=helpers.JournalV4Tests.setUp
    create=helpers.JournalV4Tests.create
    command=helpers.JournalV4Tests.command
    capture=helpers.JournalV4Tests.capture
    validated=helpers.JournalV4Tests.validated
    retire_intent=helpers.JournalV4Tests.retire_intent
    activate=helpers.JournalV4Tests.activate

    def open_recovery(self):
        try:owner=recovery.RecoveryJournal.open(self.storage_id,project_id='v4-journal-test',expected_source_closure_sha256=helpers.fixtures.sha('source'))
        except helpers.journal.PublicationJournalV4Error as exc:
            if exc.cleanup_owner is not None:self.owners.append(exc.cleanup_owner)
            raise
        self.owners.append(owner);return owner

    def reconcile_synthetic(self,owner,*,recovery_id='recover-one'):
        t=clock();owner.admit('command.one',helpers.fixtures.rev('command.one'),recovery_id=recovery_id,
            admission={'session_id':'synthetic-recovery-authority','authority_epoch':10,'admitted_ms':t,
                       'deadline_ms':t+30000,'explicit_reconcile':True},observed_ms=t)
        snapshot=owner.snapshot();selected=snapshot['selected'];manifest=selected['bundle_manifest'];t=clock()
        facts={'command_id':'command.one','digest':helpers.fixtures.rev('command.one'),'observation_id':'synthetic-recovered-readback',
            'observation_sha256':helpers.fixtures.sha('synthetic-readback'),'editor':{'session_id':'fresh-synthetic-editor',
                'pid':4321,'creation_filetime':'123456792','root_identity':{'volume':'12','file_id':'d'*32},
                'engine_sha256':helpers.fixtures.sha('editor'),'installed_source_sha256':helpers.fixtures.sha('installed')},
            'generation':snapshot['recovery']['attempts'][-1]['editor_generation'],'root_instance_id':1,'semantic_revision':manifest['caller_observations']['scene_revision'],
            'semantic_sha256':manifest['caller_observations']['scene_revision'][7:],'project_revision':manifest['project_revision'],
            'manifest_sha256':helpers.state.digest(manifest),'selection':selected['selector']['selection'],
            'selector_version':selected['selector_version'],'files':manifest['files'],'started_ms':t,'observed_ms':t,
            'history_boundary':True,'public_ack':False}
        owner.readback_recovered('command.one',helpers.fixtures.rev('command.one'),recovery_id=recovery_id,observation=facts,observed_ms=t)
        owner.terminal_recovered('command.one',helpers.fixtures.rev('command.one'),recovery_id=recovery_id,observed_ms=clock())
        return owner.recovered_response('command.one',helpers.fixtures.rev('command.one'))

    def test_before_cas_load_plan_restores_only_unchanged_last_good(self):
        owner=self.create();old=owner.selection_facts();self.activate(owner);owner.close()
        recovered=self.open_recovery();self.assertEqual(recovered.selection_facts(),old)
        response=self.reconcile_synthetic(recovered)
        self.assertEqual(parse_json(response)['code'],'GODOT_RECOVERED_LAST_GOOD')
        self.assertIs(parse_json(response)['postconditions']['public_ack'],False)
        self.assertEqual(recovered.selection_facts(),old);self.assertIs(recovered._files._readonly,True)
        head=recovered._head;recovered.close();again=self.open_recovery()
        self.assertEqual(again._head,head);self.assertEqual(again.recovered_response('command.one',helpers.fixtures.rev('command.one')),response)

    def test_after_actual_cas_missing_selected_is_recorded_without_another_selector_write(self):
        owner=self.create();self.activate(owner);actual=owner._store.select
        def cut(intent):
            actual(intent)
            raise OSError('native CAS returned but SELECTED was not appended')
        with mock.patch.object(owner._store,'select',side_effect=cut):
            with self.assertRaises(helpers.journal.PublicationJournalV4Error):owner.select_prepared('command.one',helpers.fixtures.rev('command.one'),observed_ms=clock())
        original_events=owner._state.events;owner.close();recovered=self.open_recovery()
        self.assertEqual(recovered._state.events,original_events)
        self.assertEqual(parse_json(recovered._events[len(original_events)])['kind'],'HOLD')
        selected=recovered.selection_facts();response=self.reconcile_synthetic(recovered)
        self.assertEqual(parse_json(response)['status'],'COMMITTED')
        self.assertEqual(recovered.selection_facts(),selected);self.assertIs(recovered._files._readonly,True)
        head=recovered._head;recovered.close();again=self.open_recovery()
        self.assertEqual(again._head,head);self.assertEqual(again.recovered_response('command.one',helpers.fixtures.rev('command.one')),response)

    def test_real_exit91_before_commit_custody_requires_hold_before_witness_and_blocks_original(self):
        evidence=self.base/'crash-host';evidence.mkdir()
        result=runner.run_process([sys.executable,'-B',str(Path(__file__).resolve()),'--child-commit-crash',str(self.base),self.storage_id],
            cwd=STUDIO,output=evidence,timeout=90,label='crash')
        print('RECOVERY_NATIVE_CRASH_HOST '+json.dumps(result),flush=True)
        self.assertEqual(result['exit_code'],91);self.assertEqual(result['wrapper_exit_code'],0)
        self.assertIs(result['timed_out'],False);self.assertIs(result['tree_verified'],True)
        with mock.patch.object(recovery.WitnessCustody,'persist_binding',side_effect=OSError('cut after durable HOLD before witness')):
            with self.assertRaises(helpers.journal.PublicationJournalV4Error):self.open_recovery()
        recovered=self.open_recovery();tail=recovered._events[len(recovered._state.events):]
        self.assertEqual([parse_json(row)['kind'] for row in tail],['HOLD'])
        self.assertEqual(recovered.snapshot()['recovery']['blocked_original_commands'],['command.one'])
        with self.assertRaisesRegex(recovery.RecoveryError,'NOT_WITNESSED'):recovered.original_response('command.one',helpers.fixtures.rev('command.one'))
        selected=recovered.selection_facts();response=self.reconcile_synthetic(recovered)
        self.assertEqual(parse_json(response)['status'],'COMMITTED');self.assertIs(parse_json(response)['postconditions']['reconciled'],True)
        self.assertEqual(recovered.selection_facts(),selected)
        recovered.close();again=self.open_recovery()
        with self.assertRaisesRegex(recovery.RecoveryError,'NOT_WITNESSED'):again.original_response('command.one',helpers.fixtures.rev('command.one'))
        self.assertEqual(again.recovered_response('command.one',helpers.fixtures.rev('command.one')),response)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child-commit-crash':child_commit_crash(sys.argv[2],sys.argv[3])
    else:unittest.main(verbosity=2)
