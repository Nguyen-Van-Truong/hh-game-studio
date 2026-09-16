"""Pure mixed-stream/edit binding tests; synthetic facts never prove engine effects."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


fx=load('gt03_v5_legacy_fixtures',Path(__file__).with_name('test_publication_state_v4.py'))
journal=load('gt03_v5_journal',fx.STUDIO/'godot-addon/publication_journal_v5.py')
state=journal.state_model
from studio.protocol.core import canonical_bytes,parse_json,ValidationError

SCENE=b'unsaved editor checkpoint\n'
BEFORE={'nodes':[{'stable_id':'root','position':[0,0,0]}]}
AFTER={'nodes':[{'stable_id':'root','position':[1,2,3]}]}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def event(current,kind,*,at=None,**fields):
    snap=current.snapshot()
    return {'schema':state.EDIT_SCHEMA if kind.startswith('EDIT_') else state.SCHEMA,'kind':kind,
        'sequence':current.event_count+1,'project_id':snap['project_id'],
        'observed_ms':snap['last_observed_ms']+1 if at is None else at,**fields}


def projection(command='edit.one',operation='scene.node.update'):
    return {'operation':operation,'command_id':command,'expected_revision':'sha256:'+state.digest(BEFORE),
        'expected_generation':1,'target_stable_id':'root','payload':{'expected_generation':1,'changes':{'position':[1,2,3]}}}


def prepared(current,*,at=None,command='edit.one'):
    old=fx.prepared(current,at=at)
    retained=('before_project_revision','expected_files','parent_selection','previous_selector_version',
        'previous_selector_sha256','editor','editor_generation','root_instance_id','admission')
    projected=projection(command);digest,size=state.projection_binding(projected,command,projected['operation'],projected['expected_revision'],1)
    return event(current,'EDIT_INTENT',at=old['observed_ms'],command_id=command,digest=fx.rev(command),
        **{key:old[key] for key in retained},operation=projected['operation'],projection_sha256=digest,
        projection_size_bytes=size,before_scene_revision=projected['expected_revision'],
        scratch_name='capture-'+sha(command.encode())[:32]+'.tscn',lease_owner='synthetic-auth')


def raw_capture(command,at):
    p=command['edit_prepared'];identity=p['editor']
    return {'schema':'hh-godot-live-editor-observation-1','context_kind':'live_editor','kind':'capture',
        'command_id':p['command_id'],'request_digest':p['digest'],'editor_session_id':identity['session_id'],
        'editor_pid':identity['pid'],'editor_creation_time':identity['creation_filetime'],
        'project_root_identity':identity['root_identity'],'editor_engine_sha256':identity['engine_sha256'],
        'source_release_sha256':identity['installed_source_sha256'],'generation_before':1,'generation_after':1,
        'root_before':'1','root_after':'1','effect_started_ms':at,'effect_completed_ms':at,
        'semantic_revision':p['before_scene_revision'],'semantic_sha256':p['before_scene_revision'][7:],
        'semantic_state':copy.deepcopy(BEFORE),'working_files':state._metadata(p['expected_files']),
        'history_boundary':False,'can_undo':False,'can_redo':False,'public_ack':False,
        'observation_id':'capture-'+p['command_id'],'scene_sha256':sha(SCENE),'scene_size_bytes':len(SCENE)}


def raw_edit(command,at):
    value=raw_capture(command,at)
    for key in ('scene_sha256','scene_size_bytes'):del value[key]
    value.update(kind='edit',observation_id='observed-'+command['command_id'],semantic_state=copy.deepcopy(AFTER),
        semantic_revision='sha256:'+state.digest(AFTER),semantic_sha256=state.digest(AFTER),can_undo=True,
        operation=command['edit_prepared']['operation'],projection_sha256=command['edit_prepared']['projection_sha256'],
        checkpoint_observation_id=command['checkpoint']['capture']['observation_id'],checkpoint_scene_sha256=sha(SCENE),
        before_revision='sha256:'+state.digest(BEFORE),before_semantic_sha256=state.digest(BEFORE),
        history_id_before=1,history_id_after=1,files_saved=False,live_state_durable=False)
    return value


def blob(raw,name):
    return {'object_id':'blob-'+fx.sha(name)[:32],'identity':{'volume':'12','file_id':fx.sha('file-'+name)[:32],
        'size':len(raw)},'sha256':sha(raw)}


def ready(current,*,at=None):
    c=current.snapshot()['commands'][-1];t=current.snapshot()['last_observed_ms']+1 if at is None else at
    raw=raw_capture(c,t);summary=state.capture_summary(raw,c['edit_prepared'],t)
    return event(current,'EDIT_READY',at=t,command_id=c['command_id'],digest=c['digest'],capture=summary,
        scene_blob=blob(SCENE,c['command_id']+'-scene'),capture_blob=blob(canonical_bytes(raw),c['command_id']+'-capture'))


def committed(current,*,at=None):
    c=current.snapshot()['commands'][-1];t=current.snapshot()['last_observed_ms']+1 if at is None else at
    raw=raw_edit(c,t);summary=state.observation_summary(raw,c,t);desc=blob(canonical_bytes(raw),c['command_id']+'-edit')
    response=state.terminal_plan(current.snapshot(),{**c,'edit_observation':summary,'observation_blob':desc})['response']
    return event(current,'EDIT_COMMITTED',at=t,command_id=c['command_id'],digest=c['digest'],
                 observation=summary,observation_blob=desc,response=response)


def history(until='COMMITTED'):
    rows=[fx.configuration()];current=state.replay(rows)
    rows.append(prepared(current));current=state.reduce_event(current,rows[-1])
    if until=='EDIT_INTENT':return rows
    rows.append(ready(current));current=state.reduce_event(current,rows[-1])
    if until=='EDIT_READY':return rows
    rows.append(committed(current));return rows


class PublicationStateV5Tests(unittest.TestCase):
    def test_legacy_histories_keep_original_bytes_and_response(self):
        for operation in ('scene.save','script_text.replace'):
            rows=fx.history(operation);old=fx.state.replay(rows);new=state.replay(old.events)
            self.assertEqual(new.events,old.events)
            self.assertEqual(state.lookup_response(new,'command.one',fx.rev('command.one')),
                             fx.state.lookup_response(old,'command.one',fx.rev('command.one')))

    def test_edit_commit_preserves_selection_and_exact_truthful_response(self):
        rows=history();current=state.replay(rows);c=state.lookup(current,'edit.one')
        self.assertEqual(current.snapshot()['selected'],state.replay(rows[:1]).snapshot()['selected'])
        self.assertEqual(current.snapshot()['last_good'],state.replay(rows[:1]).snapshot()['last_good'])
        response=parse_json(state.lookup_response(current,'edit.one',fx.rev('edit.one')))
        self.assertEqual(response,rows[-1]['response']);post=response['postconditions']
        self.assertEqual(post['effect_scope'],'editor_session')
        for key in ('files_saved','live_state_durable','history_boundary'):self.assertIs(post[key],False)
        self.assertIs(post['journal_receipt_durable'],True);self.assertIs(c['public_ack'],False)
        self.assertEqual(post['durable_receipt_sha256'],state.digest(c['receipt']))
        self.assertEqual(len(current.snapshot()['edit_blobs']),3)

    def test_every_cut_keeps_checkpoint_and_no_false_terminal_response(self):
        rows=history()
        for count in range(1,len(rows)):
            current=state.replay(rows[:count]);self.assertEqual(state.replay(current.events).snapshot(),current.snapshot())
            with self.assertRaises(ValidationError):state.lookup_response(current,'edit.one',fx.rev('edit.one'))
        self.assertIn('checkpoint',state.lookup(state.replay(rows[:3]),'edit.one'))

    def test_wrong_version_and_phase_cannot_relabel_or_skip_checkpoint(self):
        with self.assertRaises(ValidationError):fx.state.replay(history())
        current=state.replay(history('EDIT_INTENT'));bad=committed(state.replay(history('EDIT_READY')))
        bad['sequence']=current.event_count+1
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)
        bad=ready(current);bad['schema']=state.SCHEMA
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_checkpoint_descriptor_and_summary_tampering_rejected(self):
        current=state.replay(history('EDIT_INTENT'));good=ready(current)
        for mutate in (lambda x:x['capture'].__setitem__('scene_sha256','0'*64),
                       lambda x:x['capture'].__setitem__('can_undo',1),
                       lambda x:x['scene_blob']['identity'].__setitem__('size',True),
                       lambda x:x.__setitem__('capture_blob',x['scene_blob']),
                       lambda x:x['capture'].__setitem__('semantic_revision',fx.rev('wrong'))):
            bad=copy.deepcopy(good);mutate(bad)
            with self.assertRaises(ValidationError):state.reduce_event(current,bad)

    def test_registered_observation_bindings_reject_substitution(self):
        current=state.replay(history('EDIT_READY'));c=state.lookup(current,'edit.one');raw=raw_edit(c,104)
        for key,value in (('source_release_sha256','0'*64),('command_id','other'),('editor_pid',True),
            ('generation_after',True),('root_after','2'),('semantic_state',BEFORE),('files_saved',True),
            ('checkpoint_scene_sha256','0'*64),('projection_sha256','0'*64),('history_id_after',2),('public_ack',True)):
            bad=copy.deepcopy(raw);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):state.observation_summary(bad,c,104)

    def test_response_tampering_and_digest_reuse_rejected(self):
        current=state.replay(history('EDIT_READY'));good=committed(current)
        for key,value in (('files_saved',True),('live_state_durable',True),('journal_receipt_durable',False),
                          ('durable_receipt_sha256','0'*64),('public_ack',False)):
            bad=copy.deepcopy(good);bad['response']['postconditions'][key]=value
            with self.subTest(key=key),self.assertRaises(ValidationError):state.reduce_event(current,bad)
        current=state.reduce_event(current,good)
        with self.assertRaises(ValidationError):state.lookup_response(current,'edit.one',fx.rev('changed'))
        with self.assertRaises(ValidationError):state.reduce_event(current,prepared(current))

    def test_stop_before_ready_is_failed_after_ready_unknown_without_replay(self):
        for phase,expected in (('EDIT_INTENT','FAILED'),('EDIT_READY','UNKNOWN')):
            current=state.replay(history(phase));current=state.reduce_event(current,event(current,'STOP',reason='user-stop'))
            c=state.lookup(current,'edit.one');self.assertEqual(c['phase'],expected)
            self.assertIs(c['response']['postconditions']['public_ack'],False)
            self.assertEqual(parse_json(state.lookup_response(current,'edit.one',fx.rev('edit.one'))),c['response'])

    def test_failed_after_ready_is_forbidden_and_unknown_retains_checkpoint(self):
        current=state.replay(history('EDIT_READY'));c=state.lookup(current,'edit.one')
        for kind in ('FAILED','UNKNOWN'):
            response=state.terminal_plan(current.snapshot(),c,kind,'lost-reply')['response']
            row=event(current,'EDIT_'+kind,command_id='edit.one',digest=c['digest'],reason='lost-reply',response=response)
            if kind=='FAILED':
                with self.assertRaises(ValidationError):state.reduce_event(current,row)
            else:
                result=state.reduce_event(current,row);self.assertTrue(result.snapshot()['held'])
                self.assertEqual(state.lookup(result,'edit.one')['checkpoint'],c['checkpoint'])

    def test_edit_then_save_in_same_stream_preserves_both_original_responses(self):
        current=state.replay(history());edit_response=state.lookup_response(current,'edit.one',fx.rev('edit.one'))
        current=state.reduce_event(current,fx.prepared(current))
        while state.lookup(current,'command.one')['phase']!='COMMITTED':current=state.reduce_event(current,fx.next_event(current))
        self.assertEqual(state.lookup_response(current,'edit.one',fx.rev('edit.one')),edit_response)
        self.assertEqual(parse_json(state.lookup_response(current,'command.one',fx.rev('command.one')))['code'],'GODOT_MANAGED_SCENE_SAVED')

    def test_stale_selection_deadline_and_invalid_projection_rejected_before_intent(self):
        current=state.replay([fx.configuration()]);good=prepared(current)
        for key,value in (('before_project_revision',fx.rev('wrong')),('editor_generation',True),('projection_sha256','bad')):
            bad=copy.deepcopy(good);bad[key]=value
            with self.assertRaises(ValidationError):state.reduce_event(current,bad)
        bad=copy.deepcopy(good);bad['admission']['deadline_ms']=bad['observed_ms']
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)
        p=projection();p['payload']['expected_generation']=True
        with self.assertRaises(ValidationError):state.projection_binding(p,'edit.one',p['operation'],p['expected_revision'],1)

    def test_lease_owner_and_snapshot_growth_are_reserved_before_intent(self):
        current=state.replay([fx.configuration()]);good=prepared(current)
        bad=copy.deepcopy(good);bad['lease_owner']='foreign-session'
        with self.assertRaises(ValidationError):state.reduce_event(current,bad)
        # Existing history and INTENT fit; the future durable receipt does not.
        limit=len(canonical_bytes(current.snapshot()))+len(canonical_bytes(good))+1024
        with mock.patch.object(state,'MAX_SNAPSHOT_BYTES',limit):
            with self.assertRaisesRegex(ValidationError,'SNAPSHOT_CAPACITY'):state.reduce_event(current,good)


if __name__=='__main__':unittest.main(verbosity=2)
