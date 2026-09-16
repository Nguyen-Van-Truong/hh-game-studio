"""Frozen real HTTP -> editor capture -> validation -> selector -> reload probe."""
from __future__ import annotations
import argparse
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import re
import sys
import traceback

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(output, binary, closure):
    sys.path.insert(0,str(STUDIO.parent))
    from studio.protocol.core import Request, canonical_bytes, parse_json
    from studio.host.core.transport import epoch_ms
    module = load('publication_probe_owner', STUDIO/'godot-addon/publication_owner.py')
    validation = module._load('validation_owner')
    factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE,factory.DEFAULT_SCRIPT,
        scene_revision='sha256:'+hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    workspace = output/'owned'; workspace.mkdir()
    owner = server = reopened = None
    rows = []
    def check(label, condition):
        rows.append({'label':label,'passed':condition is True})
        save(output/'progress.json',rows)
        if condition is not True:
            raise AssertionError(label)
    try:
        owner = module.GodotPublicationOwner.create(workspace,project_id='project.fixture',
            initial_bundle=initial,editor_binary=binary,source_closure_sha256=closure)
        credential = owner.sessions.issue()
        transport = module._load('publication_transport')
        server = transport.PublicationTransport(owner).start()
        def call(path, body, *, control=False, bearer=None):
            connection = http.client.HTTPConnection('127.0.0.1',server.control_port if control else server.port,timeout=35)
            try:
                connection.request('POST',path,canonical_bytes(body),{'Content-Type':'application/json',
                    'Authorization':'Bearer '+(bearer or credential.bearer),'X-HH-Catalog':owner.contract.CATALOG_DIGEST})
                response = connection.getresponse()
                return response.status,parse_json(response.read())
            finally:
                connection.close()
        status, discovery = call('/v1/discovery',{'project_id':owner.project_id})
        check('authenticated_discovery',status==200)
        save(output/'discovery.json',discovery)
        denied,_ = call('/v1/discovery',{'project_id':owner.project_id},bearer='z'*43)
        check('foreign_bearer_denied',denied==400)
        before = owner.inspect()
        save(output/'before.json',before)
        changed = owner._editor.apply_projection({'operation':'scene.node.update','command_id':'local.dirty',
            'expected_revision':before['revision'],'expected_generation':before['generation'],
            'target_stable_id':'root','payload':{'expected_generation':before['generation'],'changes':{'position':[2,3,4]}}})
        check('actual_editor_transform',changed.get('ok') is True)
        dirty = owner.inspect()
        check('dirty_scene_differs_from_selection',dirty['revision']!=before['revision']
              and dirty['project_revision']==before['project_revision'])
        save(output/'dirty.json',dirty)
        status,lease = call('/v1/lease',{'project_id':owner.project_id,'ttl_ms':30_000})
        check('authenticated_lease',status==200)
        payload = {'expected_generation':dirty['generation'],'expected_project_revision':dirty['project_revision'],
            'expected_files':{path:dirty['working_files'][path]['sha256'] for path in
                              (owner.contract.SCENE_PATH,owner.contract.SCRIPT_PATH)}}
        request = Request(command_id='command.save',project_id=owner.project_id,operation='scene.save',
            lease_id=lease['lease_id'],fencing_epoch=lease['fencing_epoch'],expected_revision=dirty['revision'],
            target={'stable_id':'root'},payload=payload,payload_hash='sha256:'+hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=min(lease['expires_ms'],epoch_ms()+29_000))
        save(output/'request.json',request.as_dict())
        status,result = call('/v1/commands',request.as_dict())
        save(output/'response.json',result)
        if result.get('status')!='COMMITTED' and hasattr(owner,'_last_error'):
            traceback.print_exception(owner._last_error)
        check('authenticated_save_committed',status==200 and result.get('status')=='COMMITTED'
              and result.get('postconditions',{}).get('public_ack') is True)
        after = owner.inspect()
        save(output/'after.json',after)
        check('same_semantic_after_actual_reload',after['revision']==dirty['revision'])
        check('actual_new_editor_root',after['generation']>dirty['generation']
              and after['root_instance_id']!=dirty['root_instance_id'])
        check('selected_project_changed',after['project_revision']!=before['project_revision'])
        check('history_boundary',after['can_undo'] is False and after['can_redo'] is False)
        selection = owner._journal.selection_facts(); save(output/'selection.json',selection)
        journal = owner._journal.snapshot(); save(output/'journal.json',journal)
        _,duplicate = call('/v1/commands',request.as_dict())
        check('duplicate_exact_reply_no_effect',duplicate==result and owner._journal.selection_facts()==selection)
        _,lookup = call('/v1/lookup',{'project_id':owner.project_id,'command_id':request.command_id},control=True)
        check('control_lookup_exact_reply',lookup==result)
        _,stopped = call('/v1/stop',{'project_id':owner.project_id,'command_id':'control.stop'},control=True)
        check('authenticated_stop',stopped.get('stopped') is True and stopped.get('draining') is False)
        journal_model,storage_id = owner.journal_model,owner.storage_id
        editor = owner._editor
        server.close(); server=None
        owner.close(); owner=None
        save(output/'editor-close.json',editor.close())
        reopened = journal_model.PublicationJournalV3.reopen(storage_id,project_id='project.fixture')
        check('readonly_reopen_exact_selection',reopened.selection_facts()==selection)
        saved = reopened.lookup(request.command_id,request.digest)
        check('readonly_reopen_durable_commit',saved['phase']=='COMMITTED'
              and saved['receipt']['status']=='COMMITTED' and saved['public_ack'] is False)
        check('readonly_reopen_selected_bundle',reopened.read_selected_bundle().project_revision==after['project_revision'])
        save(output/'reopened.json',reopened.snapshot())
        reopened.close(); reopened=None
        save(output/'publication.json',{'passed':True,'checks':rows,'candidate_only':True,
            'gt03_acceptance':False,'authenticated_scene_save_observed':True,
            'source_closure_sha256':closure})
        print('HH_PUBLICATION_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        if server is not None: server.close()
        if owner is not None: owner.close()
        if reopened is not None: reopened.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--frozen',action='store_true')
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--closure')
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',args.run_id): parser.error('invalid run ID')
    if args.frozen: return frozen(args.output,args.binary,args.closure)
    output=args.output.resolve(); output.relative_to(STUDIO.parent/'zdoc/reviews')
    output.mkdir(parents=True,exist_ok=False)
    inventory=load('publication_inventory',STUDIO/'tests/godot/run_editor_probe.py')
    before=inventory.inputs(); source=output/'source/studio'
    for name,digest in before.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest: raise ValueError('source changed during freeze')
    runner=load('publication_runner',source/'build/bootstrap/run_fixture.py')
    closure=runner.source_closure_sha256(before)
    save(output/'source-closure.json',{'files':before,'source_closure_sha256':closure})
    lock=json.loads((source/'toolchain.lock.json').read_bytes())['godot']
    local=json.loads((STUDIO/'.local/toolchain.local.json').read_bytes())
    binary=Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary)!=lock['gui_sha256']: raise ValueError('GUI pin mismatch')
    host=runner.run_process([sys.executable,'-B',str(source/'tests/godot/run_publication_probe.py'),
        '--frozen','--output',str(output),'--run-id',args.run_id,'--binary',str(binary),'--closure',closure],
        cwd=source,output=output,timeout=180,label='publication')
    unchanged=before==inventory.inputs()
    frozen_unchanged=all(sha(source/name)==digest for name,digest in before.items())
    passed=(host['exit_code']==host['wrapper_exit_code']==0 and host['tree_verified']
            and not host['timed_out'] and frozen_unchanged)
    save(output/'capture.json',{'run_id':args.run_id,'host':host,'passed':passed,
        'source_closure_sha256':closure,'origin_source_unchanged':unchanged,
        'snapshot_unchanged':frozen_unchanged,'candidate_only':True,'gt03_acceptance':False})
    print(json.dumps({'passed':passed,'host':host,'origin_source_unchanged':unchanged}),flush=True)
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
