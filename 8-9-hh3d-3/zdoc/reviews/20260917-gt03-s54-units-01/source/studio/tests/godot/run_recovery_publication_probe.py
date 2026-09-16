"""Actual validated publication owner crash, then authenticated readonly recovery."""
from __future__ import annotations
import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import traceback

STUDIO=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def call(server,path,body,bearer,catalog,*,control=False):
    from studio.protocol.core import canonical_bytes,parse_json
    connection=http.client.HTTPConnection('127.0.0.1',server.control_port if control else server.port,timeout=95)
    try:
        connection.request('POST',path,canonical_bytes(body),{'Content-Type':'application/json',
            'Authorization':'Bearer '+bearer,'X-HH-Catalog':catalog})
        response=connection.getresponse();raw=response.read()
        return response.status,parse_json(raw),raw
    finally:connection.close()


def crash_child(output,binary,closure):
    sys.path.insert(0,str(STUDIO.parent))
    from studio.protocol.core import Request,canonical_bytes
    from studio.host.core.transport import epoch_ms
    module=load('recovery_original_owner',STUDIO/'godot-addon/publication_owner.py')
    validation=module._load('validation_owner');factory=validation.factory
    initial=factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision='sha256:'+hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    work=output/'owned';work.mkdir()
    owner=module.GodotPublicationOwner.create(work,project_id='project.fixture',initial_bundle=initial,
        editor_binary=binary,source_closure_sha256=closure)
    server=module._load('publication_transport').PublicationTransport(owner).start()
    try:
        credential=owner.sessions.issue()
        catalog=owner.contract.CATALOG_DIGEST
        status,lease,_=call(server,'/v1/lease',{'project_id':owner.project_id,'ttl_ms':90000},credential.bearer,catalog)
        if status!=200:raise AssertionError('original writer lease')
        before=owner.inspect()
        payload={'expected_generation':before['generation'],'expected_project_revision':before['project_revision'],
            'expected_files':{name:before['working_files'][name]['sha256'] for name in
                (owner.contract.SCENE_PATH,owner.contract.SCRIPT_PATH)}}
        request=Request(command_id='recovery.original',project_id=owner.project_id,operation='scene.save',
            lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=before['revision'],
            target={'stable_id':'root'},payload=payload,
            payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=min(lease['expires_ms'],epoch_ms()+89000))
        save(output/'original.json',{'storage_id':owner.storage_id,'project_id':owner.project_id,
            'source_closure_sha256':closure,'request':request.as_dict(),'before':before,
            'editor_identity':owner._editor.identity,'selection':owner._journal.selection_facts()})
        save(output/'original-validator.json',owner._validator.snapshot())

        def crash_after_capture(command,digest,capture,*,observed_ms):
            save(output/'crash-boundary.json',{'command_id':command,'digest':digest,'captured':capture,
                'journal':owner._journal.lookup(command,digest),'observed_ms':observed_ms,'expected_exit_code':92})
            print('HH_AUTHENTICATED_PUBLICATION_CRASH_AFTER_NATIVE_CAPTURE',flush=True)
            os._exit(92)
        owner._journal.captured=crash_after_capture
        call(server,'/v1/commands',request.as_dict(),credential.bearer,catalog)
        raise AssertionError('crash hook did not exit')
    finally:
        owner.sessions.halt();server.close();owner.close()


def frozen(output,binary,closure):
    sys.path.insert(0,str(STUDIO.parent))
    from studio.protocol.core import canonical_bytes,parse_json
    from studio.host.core.transport import epoch_ms
    runner=load('recovery_original_runner',STUDIO/'build/bootstrap/run_fixture.py')
    child=output/'original';child.mkdir()
    child_host=runner.run_process([sys.executable,'-B',str(Path(__file__)), '--crash-child',
        '--output',str(child),'--binary',str(binary),'--closure',closure,'--run-id','ORIGINAL-CRASH'],
        cwd=STUDIO,output=child,timeout=150,label='original')
    save(output/'original-host.json',child_host)
    rows=[]
    def check(label,condition):
        rows.append({'label':label,'passed':condition is True});save(output/'progress.json',rows)
        if condition is not True:raise AssertionError(label)
    check('actual_original_target_exit92_wrapper0_tree_clean',child_host['exit_code']==92
        and child_host['wrapper_exit_code']==0 and child_host['tree_verified'] and not child_host['timed_out'])
    original=json.loads((child/'original.json').read_bytes())
    boundary=json.loads((child/'crash-boundary.json').read_bytes())
    check('actual_capture_precedes_crash_uncommitted',boundary['journal']['phase']=='CAPTURE_PREPARED'
        and boundary['captured']['capture_id'].startswith('capture-')
        and boundary['captured']['semantic_revision']==original['before']['revision'])
    module=load('recovery_http_probe',STUDIO/'godot-addon/recovery_host.py')
    work=output/'recovery';work.mkdir()
    owner=server=reopened=None
    try:
        owner=module.GodotRecoveryHost.open(work,storage_id=original['storage_id'],project_id=original['project_id'],
            expected_source_closure_sha256=closure,editor_binary=binary)
        credential=owner.sessions.issue(operations=module.GRANTS)
        server=module.RecoveryTransport(owner).start()
        def rpc(path,body,**kwargs):
            return call(server,path,body,credential.bearer,module.CATALOG_DIGEST,**kwargs)
        status,discovery,_=rpc('/v1/discovery',{'project_id':owner.project_id})
        save(output/'discovery.json',discovery)
        check('fresh_recovery_discovery',status==200 and discovery['new_mutation_permitted'] is False)
        status,lease,_=rpc('/v1/lease',{'project_id':owner.project_id,'ttl_ms':30000})
        check('fresh_recovery_fence',status==200 and lease['fencing_epoch']>original['request']['fencing_epoch'])
        body={'project_id':owner.project_id,'command_id':original['request']['command_id'],
            'digest':original['request']['digest'],'lease_id':lease['lease_id'],'fencing_epoch':lease['fencing_epoch'],
            'deadline_ms':min(lease['expires_ms'],epoch_ms()+29000)}
        readonly=owner.sessions.issue(operations=frozenset({'control.lookup'}))
        before=owner._recovery.authority_context()
        denied,_,_=call(server,'/v1/reconcile',body,readonly.bearer,module.CATALOG_DIGEST)
        check('read_only_grant_cannot_reconcile',denied==400 and owner._recovery.authority_context()==before)
        save(output/'request.json',body)
        status,result,wire=rpc('/v1/reconcile',body)
        save(output/'response.json',result);(output/'response-wire.json').write_bytes(wire)
        if result.get('status') not in ('REJECTED','COMMITTED') and hasattr(owner,'_last_error'):
            traceback.print_exception(owner._last_error)
        check('actual_recovery_has_durable_terminal',status==200 and result.get('status')=='REJECTED')
        raw=owner._recovery._journal.recovered_response(body['command_id'],body['digest'])
        check('exact_recovered_response_bytes',raw==canonical_bytes(result))
        snapshot=owner._recovery._journal.snapshot();save(output/'journal-snapshot.json',snapshot)
        save(output/'recovery-events.json',[parse_json(value) for value in owner._recovery._journal._events])
        selected=owner._recovery._journal.selection_facts()
        check('last_good_selector_unchanged',selected==original['selection'])
        editor=owner._recovery._editor;actual=editor.inspect()
        save(output/'actual-editor.json',actual);save(output/'actual-editor-identity.json',editor.identity)
        check('actual_new_editor_identity',editor.identity['session_id']!=original['editor_identity']['session_id']
            and editor.identity['creation_filetime']!=original['editor_identity']['creation_filetime'])
        check('actual_reopened_last_good_state',actual['state']==original['before']['state']
            and actual['generation']>original['before']['generation'] and not actual['can_undo'] and not actual['can_redo'])
        status,again,again_wire=rpc('/v1/reconcile',body)
        check('retry_exact_without_second_editor_or_events',status==200 and again_wire==wire and again==result
            and owner._recovery._editor is editor and owner._recovery._journal.snapshot()==snapshot)
        status,looked,_=rpc('/v1/lookup',{'project_id':owner.project_id,'command_id':body['command_id']},control=True)
        check('control_lookup_exact_terminal',status==200 and canonical_bytes(looked)==raw)
        owner.sessions.halt();server.close();server=None;owner.close()
        save(output/'editor-close.json',editor._cleanup)
        restart_work=output/'restart';restart_work.mkdir()
        reopened=module.GodotRecoveryHost.open(restart_work,storage_id=original['storage_id'],
            project_id=original['project_id'],expected_source_closure_sha256=closure,editor_binary=binary)
        fresh=reopened.sessions.issue(operations=module.GRANTS)
        server=module.RecoveryTransport(reopened).start()
        head=reopened._recovery._journal._head
        status,looked,_=call(server,'/v1/lookup',{'project_id':original['project_id'],
            'command_id':body['command_id']},fresh.bearer,module.CATALOG_DIGEST,control=True)
        check('fresh_http_host_lookup_replays_terminal',status==200 and canonical_bytes(looked)==raw)
        status,retried,retry_wire=call(server,'/v1/reconcile',body,fresh.bearer,module.CATALOG_DIGEST)
        check('fresh_http_host_retry_has_no_new_engine_or_event',status==200 and retry_wire==wire
            and canonical_bytes(retried)==raw and reopened._recovery._editor is None
            and reopened._recovery._journal._head==head and reopened._recovery._journal.selection_facts()==selected)
        server.close();server=None;reopened.close();reopened=None
        save(output/'recovery.json',{'passed':True,'checks':rows,'candidate_only':True,'gt03_acceptance':False,
            'source_closure_sha256':closure,'actual_authenticated_recovery':True})
        print('HH_AUTHENTICATED_RECOVERY_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        failures=[]
        if owner is not None:owner.sessions.halt()
        for resource in (server,owner,reopened):
            if resource is not None:
                try:resource.close()
                except BaseException as error:failures.append(error)
        if failures:raise failures[0]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True);parser.add_argument('--frozen',action='store_true')
    parser.add_argument('--crash-child',action='store_true');parser.add_argument('--binary',type=Path);parser.add_argument('--closure')
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',args.run_id):parser.error('invalid run ID')
    if args.crash_child:return crash_child(args.output,args.binary,args.closure)
    if args.frozen:return frozen(args.output,args.binary,args.closure)
    output=args.output.resolve();output.relative_to(STUDIO.parent/'zdoc/reviews');output.mkdir(parents=True,exist_ok=False)
    inventory=load('recovery_inventory',STUDIO/'tests/godot/run_editor_probe.py');before=inventory.inputs()
    source=output/'source/studio'
    for name,digest in before.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest:raise ValueError('source changed during freeze')
    runner=load('recovery_runner',source/'build/bootstrap/run_fixture.py');closure=runner.source_closure_sha256(before)
    save(output/'source-closure.json',{'files':before,'source_closure_sha256':closure})
    lock=json.loads((source/'toolchain.lock.json').read_bytes())['godot']
    local=json.loads((STUDIO/'.local/toolchain.local.json').read_bytes());binary=Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary)!=lock['gui_sha256']:raise ValueError('GUI pin mismatch')
    environment=dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT']=str(STUDIO/'.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    result=runner.run_process([sys.executable,'-B',str(source/'tests/godot/run_recovery_publication_probe.py'),
        '--frozen','--output',str(output),'--run-id',args.run_id,'--binary',str(binary),'--closure',closure],
        cwd=source,output=output,timeout=240,label='recovery-publication',env=environment)
    unchanged=before==inventory.inputs();frozen_unchanged=all(sha(source/name)==digest for name,digest in before.items())
    passed=(result['exit_code']==result['wrapper_exit_code']==0 and result['tree_verified'] and not result['timed_out'] and frozen_unchanged)
    save(output/'capture.json',{'run_id':args.run_id,'host':result,'passed':passed,'source_closure_sha256':closure,
        'origin_source_unchanged':unchanged,'snapshot_unchanged':frozen_unchanged,'candidate_only':True,'gt03_acceptance':False})
    print(json.dumps({'passed':passed,'host':result,'origin_source_unchanged':unchanged}),flush=True)
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
