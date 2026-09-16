"""Recovery planning/ownership tests; no native or engine proof."""
import copy
import importlib.util
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock

PROJECT=Path(__file__).resolve().parents[3]
STUDIO=PROJECT/'studio';sys.path.insert(0,str(PROJECT))


def load(name,path,*,source=None,assumed_path=None):
    spec=importlib.util.spec_from_file_location(name,path if source is None else assumed_path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    if source is None:spec.loader.exec_module(module)
    else:exec(compile(source,str(path),'exec'),module.__dict__)
    return module


fixtures=load('gt03_recovery_fixture_values',STUDIO/'tests/godot/test_publication_state_v4.py')
recovery=load('gt03_recovery_tests',STUDIO/'godot-addon/publication_recovery.py')
from studio.protocol.core import canonical_bytes


def material(operation,phase):
    folded=fixtures.state.replay(fixtures.history(operation,phase))
    snapshot=folded.snapshot();snapshot['journal_read_only']=True
    return folded,snapshot,fixtures.state.lookup(folded,'command.one',fixtures.rev('command.one'))


class DraftRecoveryTests(unittest.TestCase):
    def test_phase_plans_distinguish_restore_complete_and_historical_terminal(self):
        for operation in ('scene.save','script_text.replace'):
            for phase in ('CAPTURE_PREPARED','CAPTURED','PREPARED','STAGED','VALIDATED','ACTIVATING','SELECTED','READBACK','COMMITTED'):
                with self.subTest(operation=operation,phase=phase):
                    folded,snapshot,command=material(operation,phase)
                    plan=recovery.classify(snapshot,command)
                    expected='COMMITTED_ORIGINAL' if phase=='COMMITTED' else 'SELECTED_REQUIRES_DURABLE_COMPLETION' if phase in ('SELECTED','READBACK') else 'RESTORE_LAST_GOOD'
                    self.assertEqual(plan['route'],expected)
                    for key in ('public_ack','engine_readback_verified','recovery_complete','new_mutation_permitted'):
                        self.assertIs(plan[key],False)
        folded,snapshot,command=material('scene.save','COMMITTED')
        command=copy.deepcopy(command);command['receipt']['selection']['generation']+=1
        self.assertEqual(recovery.classify(snapshot,command)['route'],'HISTORICAL_TERMINAL')

    def test_stop_or_unknown_never_grants_auto_observation_completion(self):
        for phase in ('VALIDATED','RETIRE_PREPARED','RETIRED','SELECTED','COMMITTED'):
            folded,snapshot,command=material('script_text.replace',phase)
            stopped=fixtures.state.reduce_event(folded,fixtures.event(folded,'STOP',reason='user-stop'))
            plan=recovery.classify(stopped.snapshot(),fixtures.state.lookup(stopped,'command.one'))
            self.assertEqual(plan['route'],'HOLD_UNKNOWN_OR_STOP');self.assertIs(plan['recovery_complete'],False)

    def owner(self,operation='scene.save',phase='COMMITTED'):
        folded,snapshot,command=material(operation,phase)
        owner=object.__new__(recovery.PublicationRecovery)
        owner._lock=threading.RLock();owner._closed=owner._held=False
        owner._cleanup=[];owner._records={};owner._editor=None;owner._expected_source=fixtures.sha('source')
        # Exact type with inert boundaries; this does not establish native proof.
        owner._journal=object.__new__(recovery.RecoveryJournal);owner._journal._state=folded
        for name in ('snapshot','lookup','read_selected_bundle','selection_facts','inspect_command',
                     'lookup_response','commit','prepare_activation','close'):
            setattr(owner._journal,name,mock.Mock())
        owner._journal.snapshot.return_value=snapshot;owner._journal.lookup.return_value=command
        bundle=fixtures.bundle('captured-scene',script='replacement-script' if operation=='script_text.replace' else 'initial-script',
            revision='replacement-state' if operation=='script_text.replace' else 'captured-state') if phase in ('SELECTED','READBACK','COMMITTED') else fixtures.bundle()
        owner._journal.read_selected_bundle.return_value=bundle
        owner._journal.selection_facts.return_value={k:snapshot['selected'][k] for k in ('selector','selector_version')}
        def inspection(command_id,digest):
            observed=owner._journal.snapshot()
            selected={**observed['selected'],**owner._journal.selection_facts()}
            return observed,owner._journal.lookup(command_id,digest),owner._journal.read_selected_bundle(),{'selected':selected}
        owner._journal.inspect_command.side_effect=inspection
        owner._journal.lookup_response.return_value=canonical_bytes(command['response']) if 'response' in command else None
        owner._editor_model=mock.Mock()
        return owner

    def test_historical_original_response_is_not_reconstructed_or_reexecuted(self):
        owner=self.owner();expected=owner._journal.lookup_response.return_value
        self.assertEqual(owner.original_response('command.one',fixtures.rev('command.one')),expected)
        owner._editor_model.EditorOwner.assert_not_called()
        owner._journal.commit.assert_not_called();owner._journal.prepare_activation.assert_not_called()

    def test_source_readonly_and_selected_content_mismatch_reject(self):
        for changed in ('source','readonly','selector','bundle'):
            owner=self.owner()
            if changed=='source':owner._expected_source=fixtures.sha('different')
            elif changed=='readonly':owner._journal.snapshot.return_value['journal_read_only']=1
            elif changed=='selector':owner._journal.selection_facts.return_value=copy.deepcopy(owner._journal.selection_facts.return_value);owner._journal.selection_facts.return_value['selector_version']['file_id']='f'*32
            else:owner._journal.read_selected_bundle.return_value=fixtures.bundle()
            with self.subTest(changed=changed),self.assertRaises(recovery.RecoveryError):owner.inspect('command.one',fixtures.rev('command.one'))

    def test_unknown_digest_is_delegated_to_verified_journal_lookup(self):
        owner=self.owner();owner._journal.lookup.side_effect=fixtures.state.PublicationError('PUBLICATION_COMMAND_CONFLICT')
        with self.assertRaises(fixtures.state.PublicationError):owner.original_response('command.one',fixtures.rev('changed'))
        owner._journal.lookup_response.assert_not_called()

    def test_caller_inspection_dictionary_does_not_replace_native_journal_owner(self):
        owner=self.owner();impostor=mock.Mock();owner._journal=impostor
        with self.assertRaisesRegex(recovery.RecoveryError,'JOURNAL_OWNER_REQUIRED'):
            owner.inspect('command.one',fixtures.rev('command.one'))
        impostor.inspect_command.assert_not_called()

    def test_blocked_route_never_constructs_an_editor(self):
        owner=self.owner();owner._journal.snapshot.return_value['stopped']=True
        with self.assertRaisesRegex(recovery.RecoveryError,'NOT_PERMITTED'):
            owner.observe_selected('command.one',fixtures.rev('command.one'),editor_parent=Path('unused'),editor_binary=Path('unused'),deadline_ms=recovery._now()+10000)
        owner._editor_model.EditorOwner.assert_not_called()

    def test_constructor_retained_cleanup_owner_stays_reachable(self):
        owner=self.owner();retained=mock.Mock();error=RuntimeError('synthetic constructor failure');error.cleanup_owner=retained
        owner._editor_model.EditorOwner.side_effect=error
        with self.assertRaises(recovery.RecoveryError) as raised:
            owner.observe_selected('command.one',fixtures.rev('command.one'),editor_parent=Path('unused'),editor_binary=Path('unused'),deadline_ms=recovery._now()+10000)
        self.assertIs(raised.exception.cleanup_owner,owner);self.assertIn(retained,owner._cleanup)
        owner.close();retained.close.assert_called_once();owner._journal if owner._journal is None else self.fail('journal retained after successful close')

    def test_close_failure_retains_exact_resource_and_can_retry(self):
        owner=self.owner();editor=mock.Mock();owner._editor=editor
        editor.close.side_effect=[OSError('synthetic close failure'),{}]
        with self.assertRaises(recovery.RecoveryError) as raised:owner.close()
        self.assertIs(raised.exception.cleanup_owner,owner);self.assertIs(owner._editor,editor)
        owner.close();self.assertIsNone(owner._editor);self.assertIsNone(owner._journal)

    def test_unregistered_or_copied_observation_never_proves_readback(self):
        owner=self.owner();receipt=recovery.RecoveryObservation('command.one',fixtures.rev('command.one'),'recovery-madeup',fixtures.sha('madeup'))
        with self.assertRaisesRegex(recovery.RecoveryError,'REGISTERED'):owner.observation(receipt)
        owner._editor_model.EditorOwner.assert_not_called()


class DraftRecoveryFoldTests(unittest.TestCase):
    def history(self,orphan=False):
        publication=fixtures.state.replay(fixtures.history('script_text.replace'));snapshot=publication.snapshot();rows=[]
        def event(kind,**fields):
            return {'schema':recovery.RECOVERY_SCHEMA,'kind':kind,'sequence':len(rows)+1,'project_id':snapshot['project_id'],
                'observed_ms':1000+len(rows),'publication_prefix_sha256':recovery._prefix_hash(publication),**fields}
        def head(sequence):return {'sequence':sequence,'sha256':fixtures.sha(str(sequence)),'size':100+sequence}
        if orphan:
            rows.append(canonical_bytes(event('HOLD',saved_head=head(len(publication.events)+3),observed_head=head(len(publication.events)+4),
                reason='unwitnessed-tail',blocked_original_commands=['command.one'],selected=snapshot['selected'])))
        current=recovery._fold_recovery(publication,rows)
        rows.append(canonical_bytes(event('ADMITTED',command_id='command.one',digest=fixtures.rev('command.one'),recovery_id='recover-one',
            admission={'session_id':'new-authority','authority_epoch':10,'admitted_ms':900,'deadline_ms':2000,'explicit_reconcile':True},
            route='complete-selected' if orphan else 'verify-original',selected=snapshot['selected'],
            native_head=head(len(publication.events)+4+len(rows)),editor_generation=recovery._next_editor_generation(publication,current['attempts']))))
        attempt=recovery._fold_recovery(publication,rows)['attempts'][-1];m=snapshot['selected']['bundle_manifest'];old=recovery._original_prepared(publication,'command.one')['editor']
        new={**old,'session_id':'new-editor','creation_filetime':'123456794','root_identity':{'volume':'12','file_id':'e'*32}}
        facts={'command_id':'command.one','digest':fixtures.rev('command.one'),'observation_id':'readback-one','observation_sha256':fixtures.sha('readback'),
            'editor':new,'generation':attempt['editor_generation'],'root_instance_id':1,'semantic_revision':m['caller_observations']['scene_revision'],
            'semantic_sha256':m['caller_observations']['scene_revision'][7:],'project_revision':m['project_revision'],'manifest_sha256':fixtures.state.digest(m),
            'selection':snapshot['selected']['selector']['selection'],'selector_version':snapshot['selected']['selector_version'],'files':m['files'],
            'started_ms':1000+len(rows),'observed_ms':1000+len(rows),'history_boundary':True,'public_ack':False}
        rows.append(canonical_bytes(event('READBACK',command_id='command.one',digest=fixtures.rev('command.one'),recovery_id='recover-one',observation=facts)))
        current=recovery._fold_recovery(publication,rows)
        response=recovery._recovery_response(publication,current['attempts'][-1],current['blocked_original_commands'])['response']
        rows.append(canonical_bytes(event('TERMINAL',command_id='command.one',digest=fixtures.rev('command.one'),recovery_id='recover-one',response=response)))
        return publication,rows

    def test_original_and_orphan_terminal_responses_stay_distinct(self):
        for orphan in (False,True):
            publication,rows=self.history(orphan);folded=recovery._fold_recovery(publication,rows)
            actual=folded['attempts'][-1]['response'];original=fixtures.state.lookup(publication,'command.one')['response']
            if orphan:self.assertNotEqual(actual,original);self.assertIn('command.one',folded['blocked_original_commands'])
            else:self.assertEqual(actual,original)

    def test_fresh_generation_is_durable_and_boolean_alias_rejected(self):
        publication,rows=self.history();event=fixtures.parse_json(rows[0]);event['editor_generation']=True
        with self.assertRaises((recovery.RecoveryError,fixtures.state.PublicationError)):recovery._fold_recovery(publication,[canonical_bytes(event)])
        event=fixtures.parse_json(rows[1]);event['observation']['generation']-=1
        with self.assertRaises((recovery.RecoveryError,fixtures.state.PublicationError)):recovery._fold_recovery(publication,[rows[0],canonical_bytes(event)])

    def test_readback_started_before_admission_or_outside_deadline_rejected(self):
        publication,rows=self.history()
        for field,value in [('started_ms',999),('started_ms',True),('observed_ms',2001),('public_ack',0),('history_boundary',1)]:
            event=fixtures.parse_json(rows[1]);event['observation'][field]=value
            with self.subTest(field=field),self.assertRaises((recovery.RecoveryError,fixtures.state.PublicationError)):recovery._fold_recovery(publication,[rows[0],canonical_bytes(event)])

    def test_pending_attempt_cannot_be_replaced_without_a_durable_hold(self):
        publication,rows=self.history();event=fixtures.parse_json(rows[0]);event.update(sequence=2,observed_ms=1001,recovery_id='recover-two')
        event['admission']['authority_epoch']=11;event['editor_generation']+=1
        with self.assertRaises(recovery.RecoveryError):recovery._fold_recovery(publication,[rows[0],canonical_bytes(event)])

    def test_false_original_witness_map_and_response_forgery_rejected(self):
        publication,rows=self.history(True);hold=fixtures.parse_json(rows[0]);hold['blocked_original_commands']=[]
        with self.assertRaises(recovery.RecoveryError):recovery._fold_recovery(publication,[canonical_bytes(hold)])
        terminal=fixtures.parse_json(rows[-1]);terminal['response']['postconditions']['public_ack']=False
        with self.assertRaises(recovery.RecoveryError):recovery._fold_recovery(publication,[*rows[:-1],canonical_bytes(terminal)])

    def test_unknown_kind_shape_never_becomes_authority(self):
        publication,rows=self.history();event=fixtures.parse_json(rows[0]);event['kind']=[]
        with self.assertRaises(recovery.RecoveryError):recovery._fold_recovery(publication,[canonical_bytes(event)])

    def test_recovery_stop_preserves_historical_terminal_but_rejects_new_admission(self):
        publication,rows=self.history()
        stop={'schema':recovery.RECOVERY_SCHEMA,'kind':'STOPPED','sequence':len(rows)+1,
            'project_id':publication.snapshot()['project_id'],'observed_ms':1500,
            'publication_prefix_sha256':recovery._prefix_hash(publication),'reason':'user.stop'}
        stopped=recovery._fold_recovery(publication,[*rows,canonical_bytes(stop)])
        self.assertTrue(stopped['stopped']);self.assertTrue(stopped['held'])
        self.assertEqual(stopped['attempts'][-1]['phase'],'TERMINAL')
        self.assertEqual(stopped['attempts'][-1]['response'],fixtures.parse_json(rows[-1])['response'])
        next_event=fixtures.parse_json(rows[0]);next_event.update(sequence=len(rows)+2,observed_ms=1501,recovery_id='recover-two')
        next_event['admission']['authority_epoch']+=1;next_event['editor_generation']+=1
        with self.assertRaisesRegex(recovery.RecoveryError,'RECOVERY_STOPPED'):
            recovery._fold_recovery(publication,[*rows,canonical_bytes(stop),canonical_bytes(next_event)])

    def test_recovery_stop_pending_effect_cannot_later_write_terminal(self):
        publication,rows=self.history()
        stop={'schema':recovery.RECOVERY_SCHEMA,'kind':'STOPPED','sequence':2,
            'project_id':publication.snapshot()['project_id'],'observed_ms':1001,
            'publication_prefix_sha256':recovery._prefix_hash(publication),'reason':'user.stop'}
        prefix=[rows[0],canonical_bytes(stop)]
        stopped=recovery._fold_recovery(publication,prefix)
        self.assertEqual(stopped['attempts'][-1]['phase'],'HELD')
        readback=fixtures.parse_json(rows[1]);readback.update(sequence=3,observed_ms=1002)
        with self.assertRaisesRegex(recovery.RecoveryError,'ADMISSION_REQUIRED'):
            recovery._fold_recovery(publication,[*prefix,canonical_bytes(readback)])
        duplicate={**stop,'sequence':3,'observed_ms':1002}
        with self.assertRaisesRegex(recovery.RecoveryError,'ALREADY_STOPPED'):
            recovery._fold_recovery(publication,[*prefix,canonical_bytes(duplicate)])

    def test_unwitnessed_stop_hold_keeps_witnessed_recovered_response(self):
        publication,rows=self.history(orphan=True)
        terminal_head=len(publication.events)+4+len(rows)
        stop={'schema':recovery.RECOVERY_SCHEMA,'kind':'STOPPED','sequence':len(rows)+1,
            'project_id':publication.snapshot()['project_id'],'observed_ms':1500,
            'publication_prefix_sha256':recovery._prefix_hash(publication),'reason':'user.stop'}
        head=lambda number:{'sequence':number,'sha256':fixtures.sha(str(number)),'size':100+number}
        hold={**stop,'kind':'HOLD','sequence':len(rows)+2,'observed_ms':1501,
            'saved_head':head(terminal_head),'observed_head':head(terminal_head+1),
            'reason':'unwitnessed-tail','blocked_original_commands':[],
            'selected':publication.snapshot()['selected']}
        folded=recovery._fold_recovery(publication,[*rows,canonical_bytes(stop),canonical_bytes(hold)])
        self.assertTrue(folded['stopped']);self.assertTrue(folded['held'])
        self.assertEqual(folded['attempts'][-1]['phase'],'TERMINAL')
        self.assertEqual(folded['attempts'][-1]['response'],fixtures.parse_json(rows[-1])['response'])
        hold['saved_head']=head(terminal_head-1)
        folded=recovery._fold_recovery(publication,[*rows,canonical_bytes(stop),canonical_bytes(hold)])
        self.assertEqual(folded['attempts'][-1]['phase'],'HELD')


if __name__=='__main__':unittest.main(verbosity=2)
