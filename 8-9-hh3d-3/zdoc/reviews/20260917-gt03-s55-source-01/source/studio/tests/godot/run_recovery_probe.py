"""Frozen Windows recovery component: owned crash, fresh auth/editor, same custody.

The bootstrap uses observed Windows semantics of the trusted fixture. It is not
isolated Linux validation or the complete authenticated publication pipeline.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

STUDIO=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def now():return time.time_ns()//1_000_000


def initial_crash(output,binary,closure,storage_id):
    sys.path.insert(0,str(STUDIO.parent))
    recovery=load('recovery_crash_component',STUDIO/'godot-addon/publication_recovery.py')
    from studio.host.core.custody_registry import RegistryCustody
    from studio.protocol.core import canonical_bytes
    RegistryCustody.provision_base()
    editor_model=recovery._load('editor_owner');factory=editor_model.factory
    initial=factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision='sha256:'+'0'*64,engine_sha256=editor_model.GUI_SHA256)
    original_parent=output/'original-editor';original_parent.mkdir()
    editor=editor_model.EditorOwner(original_parent,initial,editor_binary=binary)
    before=editor.script_observation()['snapshot']
    initial=factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision=before['revision'],engine_sha256=editor_model.GUI_SHA256)
    storage_parent=output/'storage';storage_parent.mkdir()
    journal=recovery._v4.PublicationJournalV4.create(storage_parent,storage_id=storage_id,
        config={'schema':recovery._model.SCHEMA,'kind':'CONFIG','sequence':1,'project_id':'recovery.component',
            'observed_ms':now(),'validator_engine_sha256':editor_model.GUI_SHA256,
            'editor_engine_sha256':editor_model.GUI_SHA256,'source_closure_sha256':closure,
            'validation_source_release_sha256':sha(canonical_bytes(editor_model._release()))},initial_bundle=initial)
    sessions=recovery.session_model.PublicationSession('recovery.component',output,'sha256:'+closure)
    credential=sessions.issue(operations=frozenset({'scene.save'}))
    grant=sessions.authorize('Bearer '+credential.bearer,'scene.save',project_id='recovery.component',catalog_digest='sha256:'+closure)
    lease=sessions.lease(grant,ttl_ms=30000);deadline=min(now()+20000,lease.expires_ms)
    command,digest='component.crash','sha256:'+sha(b'component.crash')
    intent=editor.prepare_effect(command,digest,'capture',expected_generation=before['generation'],
        expected_revision=before['revision'],deadline_ms=deadline)
    sessions.check(grant,lease,deadline_ms=deadline,operation='scene.save');at=now()
    journal.capture_prepared(command,digest,operation='scene.save',script_change=None,
        expected_revision=before['revision'],editor=editor.identity,editor_generation=before['generation'],
        root_instance_id=int(before['root_instance_id']),admission={'session_id':grant.session_id,
            'catalog_digest':grant.catalog_digest,'lease_id':lease.lease_id,'fencing_epoch':lease.fencing_epoch,
            'admitted_ms':at,'deadline_ms':deadline,'lease_expires_ms':lease.expires_ms},
        scratch_name=intent.scratch_name,observed_ms=at)
    save(output/'original.json',{'scope':'Windows observed trusted bootstrap; no isolated validator execution',
        'storage_id':storage_id,'identity':editor.identity,'selection':journal.selection_facts(),
        'snapshot':journal.snapshot(),'before':before,'source_closure_sha256':closure})
    # Actual process death: no Python close/finally and no publication ACK.
    os._exit(92)


def component(output,binary,closure):
    sys.path.insert(0,str(STUDIO.parent))
    recovery=load('recovery_component',STUDIO/'godot-addon/publication_recovery.py')
    runner=load('recovery_owned_runner',STUDIO/'build/bootstrap/run_fixture.py')
    from studio.protocol.core import parse_json,canonical_bytes
    storage_id=uuid.uuid4().hex;owner=None;rows=[]
    report={'ok':False,'scope':'actual Windows storage/auth/editor recovery component; trusted Windows-observed bootstrap; no Linux validator or HTTP proof',
        'acceptance':False,'public_ack':False,'storage_id':storage_id,'source_closure_sha256':closure,'checks':rows}
    def check(label,value):
        rows.append({'label':label,'passed':value is True});save(output/'progress.json',rows)
        if value is not True:raise AssertionError(label)
    try:
        child=runner.run_process([sys.executable,'-B',str(Path(__file__).resolve()),'--initial-crash',
            '--output',str(output),'--binary',str(binary),'--closure',closure,'--storage-id',storage_id],
            cwd=STUDIO,output=output,timeout=120,label='original-crash')
        report['original_host']=child
        check('actual_original_host_exit92',child['exit_code']==92 and child['wrapper_exit_code']==0
            and child['timed_out'] is False and child['tree_verified'] is True)
        original=json.loads((output/'original.json').read_bytes())
        check('original_capture_intent_is_durable',original['snapshot']['pending_command_id']=='component.crash'
            and original['snapshot']['commands'][-1]['phase']=='CAPTURE_PREPARED')
        owner=recovery.PublicationRecovery.open(storage_id,project_id='recovery.component',expected_source_closure_sha256=closure)
        context=owner.authority_context()
        sessions=recovery.session_model.PublicationSession('recovery.component',output,'sha256:'+closure,
            minimum_fencing_epoch=context['minimum_authority_epoch'])
        credential=sessions.issue(operations=frozenset({'project.reconcile','control.stop'}))
        grant=sessions.authorize('Bearer '+credential.bearer,'project.reconcile',project_id='recovery.component',catalog_digest='sha256:'+closure)
        lease=sessions.lease(grant,ttl_ms=30000);authority=recovery.ReconciliationAuthority(sessions,grant,lease)
        editor_parent=output/'recovered-editor';editor_parent.mkdir()
        raw=owner.reconcile(authority,'component.crash','sha256:'+sha(b'component.crash'),editor_parent=editor_parent,
            editor_binary=binary,deadline_ms=min(now()+30000,lease.expires_ms))
        response=parse_json(raw);save(output/'response.json',response)
        snapshot=owner._journal.snapshot();save(output/'recovered-snapshot.json',snapshot)
        receipt=next(iter(owner._records.values()))[0]
        observation=owner.observation(receipt);save(output/'observation.json',observation)
        check('actual_selected_last_good_restored_without_replaying_command',response['status']=='REJECTED'
            and response['code']=='GODOT_RECOVERED_LAST_GOOD' and response['postconditions']['public_ack'] is False)
        check('same_selector_native_identity_no_replacement',owner._journal.selection_facts()==original['selection'])
        check('registered_fresh_engine_full_readback',observation['engine_readback_verified'] is True
            and observation['editor']['session_id']!=original['identity']['session_id']
            and observation['generation']>original['before']['generation']
            and observation['semantic_revision']==original['before']['revision']
            and len(observation['working_files'])==11)
        check('durable_terminal_same_stream',snapshot['recovery']['attempts'][-1]['phase']=='TERMINAL'
            and snapshot['journal_read_only'] is True and snapshot['new_mutation_permitted'] is False)
        check('new_publication_still_readonly',owner._journal._files._readonly is True)
        old_head=owner._journal._head;selected=owner._journal.selection_facts()
        owner.close();owner=None
        reopened=recovery.RecoveryJournal.open(storage_id,project_id='recovery.component',expected_source_closure_sha256=closure)
        try:
            check('reopen_replays_exact_recovered_bytes',reopened.recovered_response('component.crash','sha256:'+sha(b'component.crash'))==raw)
            check('readonly_retry_does_not_append_or_select',reopened._head==old_head and reopened.selection_facts()==selected)
        finally:reopened.close()
        report['ok']=True
    except BaseException as exc:
        report['failure']=type(exc).__name__+': '+str(exc)
        causes=[];cause=exc.__cause__
        while cause is not None:causes.append(type(cause).__name__+': '+str(cause));cause=cause.__cause__
        report['causes']=causes
        retained=getattr(exc,'cleanup_owner',None)
        if owner is None and retained is not None:owner=retained
    finally:
        if owner is not None:
            try:owner.close()
            except BaseException as exc:report['cleanup_failure']=str(exc);report['ok']=False
        report['artifacts']={p.relative_to(output).as_posix():sha(p.read_bytes()) for p in sorted(output.rglob('*'))
            if p.is_file() and not any(part in ('.godot','appdata','localappdata','temp','tmp','storage') for part in p.relative_to(output).parts)}
        save(output/'result.json',report)
    return 0 if report['ok'] else 1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path);parser.add_argument('--closure');parser.add_argument('--storage-id')
    parser.add_argument('--initial-crash',action='store_true');parser.add_argument('--component',action='store_true')
    parser.add_argument('--storage-tests-only',action='store_true');args=parser.parse_args()
    output=args.output.absolute()
    if args.initial_crash:initial_crash(output,args.binary,args.closure,args.storage_id)
    if args.component:return component(output,args.binary,args.closure)
    output.mkdir(parents=True,exist_ok=False)
    paths=[]
    for directory in ('godot-addon','host/core','protocol'):
        for path in (STUDIO/directory).rglob('*'):
            if (path.is_file() and not any(p in ('.godot','__pycache__') for p in path.relative_to(STUDIO).parts)
                and path.suffix in ('.py','.gd','.json','.uid','.tscn','.cfg','.godot')):
                paths.append(path)
    paths.extend(STUDIO/path for path in ('toolchain.lock.json','build/bootstrap/run_fixture.py',
        'tests/godot/run_recovery_probe.py','tests/godot/test_recovery_journal_native.py',
        'tests/godot/test_publication_journal_v4.py','tests/godot/test_publication_state_v4.py','tests/godot/test_publication_journal.py'))
    inventory={}
    for path in sorted(set(paths)):
        name=path.relative_to(STUDIO).as_posix();raw=path.read_bytes();inventory[name]=sha(raw)
        target=output/'source/studio'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    closure=sha(json.dumps(inventory,sort_keys=True,separators=(',',':')).encode())
    save(output/'source-closure.json',{'algorithm':'sha256-json-sorted-file-map','source_closure_sha256':closure,'files':inventory})
    runner=load('recovery_outer_runner',STUDIO/'build/bootstrap/run_fixture.py')
    frozen_studio=output/'source/studio'
    if args.storage_tests_only:
        argv=[sys.executable,'-B',str(frozen_studio/'tests/godot/test_recovery_journal_native.py')]
    else:
        local=json.loads((STUDIO/'.local/toolchain.local.json').read_bytes())
        binary=args.binary or Path(local['godot_console']).with_name('Godot_v4.7.2-stable_win64.exe')
        owned=output/'owned';owned.mkdir()
        argv=[sys.executable,'-B',str(frozen_studio/'tests/godot/run_recovery_probe.py'),'--component',
            '--output',str(owned),'--binary',str(binary),'--closure',closure]
    result=runner.run_process(argv,cwd=frozen_studio,output=output,timeout=360,label='recovery')
    result['source_snapshot_unchanged']=all(sha((frozen_studio/name).read_bytes())==digest for name,digest in inventory.items())
    result['source_origin_matches_snapshot']=all(sha((STUDIO/name).read_bytes())==digest for name,digest in inventory.items())
    save(output/'host-result.json',result)
    return 0 if result['exit_code']==0 and result['wrapper_exit_code']==0 and result['tree_verified'] is True and result['source_snapshot_unchanged'] else 1


if __name__=='__main__':raise SystemExit(main())
