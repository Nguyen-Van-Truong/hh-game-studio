"""V4/V5 recovery distinctions; synthetic histories, never native authority."""
import importlib.util
from pathlib import Path
import sys
import unittest


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


v5=load('recovery_v5_fixture',Path(__file__).with_name('test_publication_state_v5.py'))
fx=v5.fx
recovery=load('recovery_mixed_module',fx.STUDIO/'godot-addon/publication_recovery.py')
from studio.protocol.core import canonical_bytes,parse_json


def tail(publication,command_id,route,*,orphan=False):
    snapshot=publication.snapshot();command=recovery._model.lookup(publication,command_id);rows=[]
    def head(seq):return {'sequence':seq,'sha256':fx.sha(str(seq)),'size':100+seq}
    def event(kind,**fields):return {'schema':recovery.RECOVERY_SCHEMA,'kind':kind,'sequence':len(rows)+1,
        'project_id':snapshot['project_id'],'observed_ms':1000+len(rows),
        'publication_prefix_sha256':recovery._prefix_hash(publication),**fields}
    if orphan:rows.append(canonical_bytes(event('HOLD',saved_head=head(len(publication.events)+3),
        observed_head=head(len(publication.events)+4),reason='unwitnessed-tail',blocked_original_commands=[command_id],selected=snapshot['selected'])))
    generation=recovery._next_editor_generation(publication,[])
    rows.append(canonical_bytes(event('ADMITTED',command_id=command_id,digest=command['digest'],recovery_id='recovery.test',
        admission={'session_id':'new.authority','authority_epoch':snapshot['highest_fencing_epoch']+1,
            'admitted_ms':900,'deadline_ms':2000,'explicit_reconcile':True},route=route,selected=snapshot['selected'],
        native_head=head(len(publication.events)+4+len(rows)),editor_generation=generation)))
    current=recovery._fold_recovery(publication,rows);manifest=snapshot['selected']['bundle_manifest']
    old=recovery._original_prepared(publication,command_id)['editor']
    observation={'command_id':command_id,'digest':command['digest'],'observation_id':'readback.fresh',
        'observation_sha256':fx.sha('readback'),'editor':{**old,'session_id':'editor.new',
            'creation_filetime':str(int(old['creation_filetime'])+100),'root_identity':{'volume':'12','file_id':'e'*32}},
        'generation':generation,'root_instance_id':1,'semantic_revision':manifest['caller_observations']['scene_revision'],
        'semantic_sha256':manifest['caller_observations']['scene_revision'][7:],'project_revision':manifest['project_revision'],
        'manifest_sha256':recovery._model.digest(manifest),'selection':snapshot['selected']['selector']['selection'],
        'selector_version':snapshot['selected']['selector_version'],'files':manifest['files'],
        'started_ms':1000+len(rows),'observed_ms':1000+len(rows),'history_boundary':True,'public_ack':False}
    rows.append(canonical_bytes(event('READBACK',command_id=command_id,digest=command['digest'],recovery_id='recovery.test',observation=observation)))
    current=recovery._fold_recovery(publication,rows)
    response=recovery._recovery_response(publication,current['attempts'][-1],current['blocked_original_commands'])['response']
    rows.append(canonical_bytes(event('TERMINAL',command_id=command_id,digest=command['digest'],recovery_id='recovery.test',response=response)))
    return recovery._fold_recovery(publication,rows)


class MixedPrefixRecoveryTests(unittest.TestCase):
    def test_pending_edit_restores_only_selected_files_not_volatile_history(self):
        for phase in ('EDIT_INTENT','EDIT_READY'):
            publication=v5.state.replay(v5.history(phase))
            result=tail(publication,'edit.one','restore-last-good')['attempts'][-1]
            self.assertEqual(result['response']['status'],'REJECTED')
            self.assertIs(result['response']['postconditions']['files_saved'],False)
            self.assertIs(result['response']['postconditions']['restored_editor_history'],False)

    def test_committed_edit_preserves_exact_historical_bytes_not_saved_scene_claim(self):
        publication=v5.state.replay(v5.history())
        original=v5.state.lookup_response(publication,'edit.one',fx.rev('edit.one'))
        result=tail(publication,'edit.one','verify-historical-edit')['attempts'][-1]
        self.assertEqual(canonical_bytes(result['response']),original)
        self.assertNotEqual(result['response']['postconditions']['scene_revision'],result['receipt']['scene_revision'])
        self.assertEqual(result['receipt']['route'],'verify-historical-edit')
        self.assertIs(result['response']['postconditions']['files_saved'],False)
        with self.assertRaises(recovery.RecoveryError):tail(publication,'edit.one','verify-original')
        with self.assertRaises(recovery.RecoveryError):tail(publication,'edit.one','complete-selected')

    def test_orphan_edit_terminal_is_not_minted_as_original_success(self):
        publication=v5.state.replay(v5.history())
        result=tail(publication,'edit.one','restore-last-good',orphan=True)
        self.assertIn('edit.one',result['blocked_original_commands'])
        self.assertEqual(result['attempts'][-1]['response']['status'],'REJECTED')
        self.assertIs(result['attempts'][-1]['response']['postconditions']['original_outcome_unknown'],True)
        with self.assertRaises(recovery.RecoveryError):tail(publication,'edit.one','verify-historical-edit',orphan=True)

    def unknown(self,phase):
        publication=fx.state.replay(fx.history('scene.save',phase));command=fx.state.lookup(publication,'command.one')
        response=fx.state.terminal_plan(publication.snapshot(),command,'UNKNOWN','host-crash')['response']
        return fx.state.reduce_event(publication,fx.event(publication,'UNKNOWN',command_id='command.one',
            digest=fx.rev('command.one'),reason='host-crash',response=response))

    def test_explicit_unknown_last_good_restore_preserves_original_unknown(self):
        publication=self.unknown('CAPTURED');original=fx.state.lookup_response(publication,'command.one',fx.rev('command.one'))
        result=tail(publication,'command.one','restore-last-good')['attempts'][-1]['response']
        self.assertEqual(result['status'],'REJECTED');self.assertIs(result['postconditions']['original_outcome_unknown'],True)
        self.assertEqual(fx.state.lookup_response(publication,'command.one',fx.rev('command.one')),original)
        self.assertEqual(parse_json(original)['status'],'UNKNOWN')

    def test_durable_stop_and_unknown_candidate_selected_remain_held(self):
        selected=fx.state.replay(fx.history('scene.save','SELECTED'))
        stopped=fx.state.reduce_event(selected,fx.event(selected,'STOP',reason='user-stop'))
        for publication in (stopped,self.unknown('SELECTED')):
            for route in ('restore-last-good','complete-selected'):
                with self.subTest(route=route),self.assertRaises(recovery.RecoveryError):tail(publication,'command.one',route)


if __name__=='__main__':unittest.main(verbosity=2)
