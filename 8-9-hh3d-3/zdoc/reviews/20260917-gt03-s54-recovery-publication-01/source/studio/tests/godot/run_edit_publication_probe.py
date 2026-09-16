"""Actual authenticated editor edits, durable historical receipts, save/reopen.

Every mutation reaches native EditorUndoRedoManager via the public HTTP route.
This candidate does not turn an editor-session receipt into saved-file proof.
"""
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

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(output,binary,closure):
    sys.path.insert(0,str(STUDIO.parent))
    from studio.protocol.core import Request,canonical_bytes,parse_json
    from studio.host.core.transport import epoch_ms
    module = load('s54_edit_publication_owner',STUDIO/'godot-addon/publication_owner.py')
    validation = module._load('validation_owner')
    factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision='sha256:'+hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    workspace = output/'owned'; workspace.mkdir()
    owner = server = reopened = None
    rows = []

    def check(label,condition):
        rows.append({'label':label,'passed':condition is True})
        save(output/'progress.json',rows)
        if condition is not True:
            raise AssertionError(label)

    try:
        owner = module.GodotPublicationOwner.create(workspace,project_id='project.fixture',
            initial_bundle=initial,editor_binary=binary,source_closure_sha256=closure)
        credential = owner.sessions.issue()
        server = module._load('publication_transport').PublicationTransport(owner).start()

        def call(path,body,*,control=False,bearer=None):
            connection = http.client.HTTPConnection('127.0.0.1',
                server.control_port if control else server.port,timeout=95)
            try:
                connection.request('POST',path,canonical_bytes(body),{'Content-Type':'application/json',
                    'Authorization':'Bearer '+(bearer or credential.bearer),
                    'X-HH-Catalog':owner.contract.CATALOG_DIGEST})
                response = connection.getresponse(); raw = response.read()
                return response.status,parse_json(raw),raw
            finally:
                connection.close()

        status,discovery,_ = call('/v1/discovery',{'project_id':owner.project_id})
        save(output/'discovery.json',discovery)
        check('authenticated_discovery',status==200)
        original = owner.inspect(); save(output/'before.json',original)
        original_editor = owner._editor
        original_events = tuple(owner._journal._state.events)
        status,lease,_ = call('/v1/lease',{'project_id':owner.project_id,'ttl_ms':90_000})
        check('authenticated_writer_lease',status==200)

        def request(command,operation,target,payload,*,before=None,horizon=29_000):
            before = owner.inspect() if before is None else before
            value = {'expected_generation':before['generation'],
                'expected_project_revision':before['project_revision'],**payload}
            return Request(command_id=command,project_id=owner.project_id,operation=operation,
                lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],
                expected_revision=before['revision'],target={'stable_id':target},payload=value,
                payload_hash='sha256:'+hashlib.sha256(canonical_bytes(value)).hexdigest(),
                deadline_ms=min(lease['expires_ms'],epoch_ms()+horizon))

        # An inspect-only credential never inherits the writer's edit scope.
        reader = owner.sessions.issue(operations=frozenset({'scene.inspect'}))
        denied = request('edit.denied','scene.node.update','root',{'changes':{'position':[9,9,9]}})
        status,_,_ = call('/v1/commands',denied.as_dict(),bearer=reader.bearer)
        check('operation_grant_denied_before_journal_or_editor',status==400
            and tuple(owner._journal._state.events)==original_events and owner.inspect()==original)
        commands = []
        snapshots = []

        def edit(command,operation,target,payload):
            before = owner.inspect()
            value = request(command,operation,target,payload,before=before)
            save(output/(command+'-request.json'),value.as_dict())
            status,result,wire = call('/v1/commands',value.as_dict())
            save(output/(command+'-response.json'),result)
            (output/(command+'-wire.json')).write_bytes(wire)
            if result.get('status')!='COMMITTED' and hasattr(owner,'_last_error'):
                traceback.print_exception(owner._last_error)
            post = result.get('postconditions',{})
            check(command+'_committed',status==200 and result.get('status')=='COMMITTED'
                and result.get('code')=='GODOT_EDITOR_EDITED' and post.get('public_ack') is True)
            check(command+'_scope_truthful',post.get('effect_scope')=='editor_session'
                and post.get('files_saved') is False and post.get('live_state_durable') is False
                and post.get('journal_receipt_durable') is True)
            after = owner.inspect(); save(output/(command+'-after.json'),after)
            check(command+'_same_editor_and_disk',owner._editor is original_editor
                and after['generation']==original['generation']
                and after['root_instance_id']==original['root_instance_id']
                and after['working_files']==original['working_files']
                and after['project_revision']==original['project_revision']
                and after['history_id']==original['history_id'])
            durable = owner._journal.lookup_response(command,value.digest)
            check(command+'_exact_durable_response',durable==canonical_bytes(result))
            events = tuple(owner._journal._state.events)
            status,retry,retry_wire = call('/v1/commands',value.as_dict())
            check(command+'_retry_no_effect',status==200 and retry_wire==wire
                and retry==result and tuple(owner._journal._state.events)==events and owner.inspect()==after)
            commands.append((value,result,wire)); snapshots.append(after)
            return after

        created = edit('edit.create','scene.node.create','root',{'stable_id':'box.public',
            'node_type':'MeshInstance3D','name':'PublicBox','position':[1,2,3],
            'rotation_degrees':[0,15,0],'scale':[1,1,1],'box_size':[2,3,4]})
        check('native_create_observed',any(n['stable_id']=='box.public' and n['box_size']==[2,3,4]
            for n in created['state']['nodes']))
        updated = edit('edit.update','scene.node.update','box.public',{'changes':{'position':[4,5,6]}})
        check('native_update_observed',next(n for n in updated['state']['nodes']
            if n['stable_id']=='box.public')['position']==[4,5,6])
        undone = edit('edit.undo','scene.undo','root',{'steps':1})
        check('native_undo_restores_created_state',undone['state']==created['state'] and undone['can_redo'])
        redone = edit('edit.redo','scene.redo','root',{'steps':1})
        check('native_redo_restores_updated_state',redone['state']==updated['state'])
        removed = edit('edit.remove','scene.node.remove','box.public',{})
        check('native_remove_observed',all(n['stable_id']!='box.public' for n in removed['state']['nodes']))
        restored = edit('edit.restore','scene.undo','root',{'steps':1})
        check('native_remove_undo_restores_node',restored['state']==updated['state'])
        events = tuple(owner._journal._state.events)
        status,historical,wire = call('/v1/commands',commands[0][0].as_dict())
        check('old_ack_stays_historical_after_later_edits',status==200 and wire==commands[0][2]
            and historical==commands[0][1] and owner.inspect()==restored
            and tuple(owner._journal._state.events)==events)
        stale = request('edit.stale','scene.node.update','box.public',{'changes':{'position':[0,0,0]}},before=created)
        status,_,_ = call('/v1/commands',stale.as_dict())
        check('stale_revision_rejected_without_effect',status==400 and owner.inspect()==restored
            and tuple(owner._journal._state.events)==events)

        # Rotate managed credentials before the independent slow save phase.
        credential = owner.sessions.rotate(credential)
        status,lease,_ = call('/v1/lease',{'project_id':owner.project_id,'ttl_ms':90_000})
        check('rotated_writer_new_fence',status==200 and lease['fencing_epoch']>commands[-1][0].fencing_epoch)
        saved_request = request('edit.save','scene.save','root',{'expected_files':{
            name:restored['working_files'][name]['sha256'] for name in
            (owner.contract.SCENE_PATH,owner.contract.SCRIPT_PATH)}},horizon=89_000)
        status,saved,_ = call('/v1/commands',saved_request.as_dict())
        save(output/'save-response.json',saved)
        if saved.get('status')!='COMMITTED' and hasattr(owner,'_last_error'):
            traceback.print_exception(owner._last_error)
        check('edited_scene_subsequently_saved',status==200 and saved.get('status')=='COMMITTED')
        after_save = owner.inspect(); save(output/'after-save.json',after_save)
        check('save_persists_state_and_creates_history_boundary',after_save['state']==restored['state']
            and after_save['project_revision']!=restored['project_revision']
            and not after_save['can_undo'] and not after_save['can_redo'])
        save(output/'journal-events.json',[parse_json(raw) for raw in owner._journal._state.events])
        save(output/'journal-snapshot.json',owner._journal._state.snapshot())
        save(output/'validator.json',owner._validator.snapshot())
        storage_id = owner.storage_id
        selected = owner._journal.selection_facts()
        owner.sessions.halt(); server.close(); server=None
        editor = owner._editor
        owner.close()
        save(output/'editor-close.json',editor._cleanup)
        reopened = module._load('publication_journal_v5').PublicationJournalV5.open(storage_id,
            project_id='project.fixture',expected_source_closure_sha256=closure)
        check('readonly_reopen_selection_exact',reopened.selection_facts()==selected)
        for command,result,_ in commands:
            check(command.command_id+'_reopen_exact_response',
                reopened.lookup_response(command.command_id,command.digest)==canonical_bytes(result))
        reopened.close(); reopened=None
        save(output/'publication.json',{'passed':True,'checks':rows,'source_closure_sha256':closure,
            'candidate_only':True,'gt03_acceptance':False,'authenticated_editor_mutations':True})
        print('HH_EDIT_PUBLICATION_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
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
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--frozen',action='store_true')
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--closure')
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',args.run_id):parser.error('invalid run ID')
    if args.frozen:return frozen(args.output,args.binary,args.closure)
    output=args.output.resolve();output.relative_to(STUDIO.parent/'zdoc/reviews')
    output.mkdir(parents=True,exist_ok=False)
    inventory=load('edit_inventory',STUDIO/'tests/godot/run_editor_probe.py')
    before=inventory.inputs();source=output/'source/studio'
    for name,digest in before.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest:raise ValueError('source changed during freeze')
    runner=load('edit_runner',source/'build/bootstrap/run_fixture.py')
    closure=runner.source_closure_sha256(before)
    save(output/'source-closure.json',{'files':before,'source_closure_sha256':closure})
    lock=json.loads((source/'toolchain.lock.json').read_bytes())['godot']
    local=json.loads((STUDIO/'.local/toolchain.local.json').read_bytes())
    binary=Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary)!=lock['gui_sha256']:raise ValueError('GUI pin mismatch')
    environment=dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT']=str(STUDIO/'.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host=runner.run_process([sys.executable,'-B',str(source/'tests/godot/run_edit_publication_probe.py'),
        '--frozen','--output',str(output),'--run-id',args.run_id,'--binary',str(binary),'--closure',closure],
        cwd=source,output=output,timeout=360,label='edit-publication',env=environment)
    unchanged=before==inventory.inputs()
    frozen_unchanged=all(sha(source/name)==digest for name,digest in before.items())
    passed=(host['exit_code']==host['wrapper_exit_code']==0 and host['tree_verified']
        and not host['timed_out'] and frozen_unchanged)
    save(output/'capture.json',{'run_id':args.run_id,'host':host,'passed':passed,
        'source_closure_sha256':closure,'origin_source_unchanged':unchanged,'snapshot_unchanged':frozen_unchanged,
        'candidate_only':True,'gt03_acceptance':False})
    print(json.dumps({'passed':passed,'host':host,'origin_source_unchanged':unchanged}),flush=True)
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
