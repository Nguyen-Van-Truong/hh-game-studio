"""Read-only S53 publication audit; no native processes and no acceptance.

Reuses pinned S52 raw host/container checks. Different full test closures stay
separate; production source maps must match for the combined candidate.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent/'20260917-gt03-s52-audit/verify_integration.py'
PIN = 'a4500bf057cd0e7d50201453b427e7124db2c04efb99cc114f8d73606ff31c66'
if hashlib.sha256(PREVIOUS.read_bytes()).hexdigest() != PIN:
    raise ValueError('pinned raw audit helper changed')
spec = importlib.util.spec_from_file_location('s53_raw_audit',PREVIOUS)
base = importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)
need,H,digest = base.need,base.H,base.digest


def publication_summary(ev,package,source,closure,script):
    stem='script-publication' if script else 'publication'
    runner='run_script_publication_probe.py' if script else 'run_publication_probe.py'
    capture=ev.read(package/'capture.json');summary=ev.read(package/'publication.json')
    need(capture['passed'] is True and capture['snapshot_unchanged'] is True
         and capture['origin_source_unchanged'] is True and capture['source_closure_sha256']==closure,
         'publication source/capture mismatch')
    need(capture['candidate_only'] is True and capture['gt03_acceptance'] is False
         and summary['candidate_only'] is True and summary['gt03_acceptance'] is False
         and summary['passed'] is True and summary['source_closure_sha256']==closure,'acceptance overclaim')
    syntax=ast.parse((source/'tests/godot'/runner).read_text(encoding='utf-8'))
    labels=[n.args[0].value for n in ast.walk(syntax) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name) and n.func.id=='check' and n.args
            and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str)]
    rows=summary['checks']
    need(len(rows)==len(labels)==len(set(labels)) and {r['label'] for r in rows}==set(labels)
         and all(set(r)=={'label','passed'} and r['passed'] is True for r in rows)
         and H.exact(ev.read(package/'progress.json'),rows),'native check coverage')
    host=capture['host'];lock=ev.read(source/'toolchain.lock.json')['godot']
    need(all(host[k]==stem+suffix for k,suffix in
             (('host','-host.json'),('stdout','-stdout.txt'),('stderr','-stderr.txt'))),'host path substitution')
    stdout,stderr=base.checked_host(ev,package,host)
    marker='HH_SCRIPT_PUBLICATION_COMPLETE ' if script else 'HH_PUBLICATION_COMPLETE '
    need(H.exact(H.markers(stdout,marker),[{'passed':True,'checks':len(labels)}])
         and not stderr.strip() and not H.BAD_LOG.search(stdout),'unclean actual publication exit')
    need(host['argv']==['python.exe','-B','$SNAPSHOT/tests/godot/'+runner,'--frozen',
         '--output',package.name,'--run-id',capture['run_id'],'--binary',lock['gui_executable'],
         '--closure',closure],'publication executable binding')
    return len(labels)


def closed_editor(ev,root,expected,canonical):
    start,exit_record,close=[ev.read(root/name) for name in ('process-start.json','process-exit.json','close.json')]
    need(H.integer(start.get('pid'),expected['pid']) and H.integer(exit_record.get('pid'),expected['pid'])
         and H.integer(exit_record.get('exit_code'),0) and H.exact(close['actual_process_exit'],exit_record)
         and H.integer(close['wrapper_exit_code'],0) and close['closed'] is True and close['held'] is False
         and close['logs_overflow'] is False and close['public_ack'] is False,'editor process cleanup')
    base.checked_job(close['job'])
    hello=ev.read(root/'hello.json')
    need(hello['editor_session_id']==expected['session_id'] and H.integer(hello['pid'],expected['pid'])
         and hello['main_thread'] is True and hello['editor_hint'] is True
         and hello['version']=='4.7.2-stable (official)','editor native hello')
    for name in ('stdout.txt','stderr.txt'):
        need(not H.BAD_LOG.search(ev.text(root/name)),'editor native diagnostic')
    return close


def script_editors(ev,package,source,editor_model,canonical):
    roots=list((package/'owned/editor').glob('editor-*'))
    need(len(roots)==2,'two actual editor generations required')
    old=ev.read(package/'old-editor-identity.json');new=ev.read(package/'new-editor-identity.json')
    indexed={ev.read(root/'hello.json')['editor_session_id']:root for root in roots}
    need(set(indexed)=={old['session_id'],new['session_id']},'fresh editor sessions')
    lock=ev.read(source/'toolchain.lock.json')['godot']
    release=digest(canonical(editor_model._release()))
    for identity in (old,new):
        need(identity['engine_sha256']==lock['gui_sha256']
             and identity['installed_source_sha256']==release,'editor frozen release')
        close=closed_editor(ev,indexed[identity['session_id']],identity,canonical)
        name='old-editor-close.json' if identity is old else 'new-editor-close.json'
        need(H.exact(close,ev.read(package/name)),'editor close artifact mismatch')
    old_root,new_root=indexed[old['session_id']],indexed[new['session_id']]
    paths=[list(old_root.glob('capture-*.json')),list(old_root.glob('retired-*.json')),
           list(new_root.glob('generation-*.json'))]
    need(all(len(row)==1 for row in paths),'registered editor observations missing')
    capture,retired,adopted=[ev.read(row[0]) for row in paths]
    need(H.exact(retired['editor'],old) and H.exact(adopted['old_editor'],old)
         and H.exact(adopted['new_editor'],new) and adopted['retirement_observation_id']==retired['observation_id']
         and adopted['retirement_sha256']==digest(canonical(retired)),'editor retirement hash binding')
    need(retired['public_ack'] is False and adopted['public_ack'] is False
         and retired['close_completed_ms']<=adopted['effect_started_ms']
         and int(new['creation_filetime'])>int(old['creation_filetime'])
         and adopted['generation_after']==retired['next_generation']==adopted['generation_before']+1,
         'editor retirement/generation order')
    for root,files in ((old_root,capture['working_files']),(new_root,adopted['working_files'])):
        need(len(files)==11,'complete editor working input set')
        for name,row in files.items():
            path=ev.add(H.inside(root/'project',name))
            need(base.sha(path)==row['sha256'] and path.stat().st_size==row['size_bytes'],'editor input changed')
    scratch=list((old_root/'scratch').glob('capture-*.tscn'))
    need(len(scratch)==1 and base.sha(ev.add(scratch[0]))==capture['scene_sha256']
         and scratch[0].stat().st_size==capture['scene_size_bytes'],'captured scene hash')
    return capture,retired,adopted


def validation_receipt(receipt,command_id,validation,directory,bundle,native,observation):
    canonical=validation.canonical_bytes
    final=validation.bundle_codec.create_bundle(dict(bundle.files),
        scene_revision=observation['semantic']['revision'],engine_sha256=bundle.engine_sha256)
    expected={'command_id':command_id,'source_release_sha256':validation.source_release()[1],
        'observation_sha256':digest(canonical(observation)),
        'evidence_sha256':digest(canonical(H.inventory(directory))),'run_id':native['run_id'],
        'project_revision':final.project_revision,'manifest_sha256':digest(final.manifest_bytes),
        'input_files_sha256':digest(canonical(validation.parse_json(final.manifest_bytes)['files'])),
        'validator_engine_sha256':native['toolchain']['binary_sha256'],
        'scene_revision':observation['semantic']['revision'],'context_kind':'isolated_candidate',
        'public_ack':False,'selected_state_verified':False,'live_editor_adoption_verified':False}
    need(all(H.exact(receipt.get(k),v) for k,v in expected.items()),'exact native validation receipt binding')
    need(H.integer(receipt['validation_started_ms']) and H.integer(receipt['validation_completed_ms'])
         and receipt['validation_started_ms']<=base.milliseconds(native['container_state']['StartedAt'])
         <=base.milliseconds(native['container_state']['FinishedAt'])<=receipt['validation_completed_ms'],
         'native validation interval binding')


def verify(package,ev):
    source,files,closure=base.source(ev,package)
    sys.path.insert(0,str(source.parent))
    validation=H.module('s53_validation_'+closure,source/'godot-addon/validation_owner.py')
    linux=H.module('s53_linux_'+closure,source/'tests/godot/run_linux_probe.py')
    state=H.module('s53_state_'+closure,source/'godot-addon/publication_state_v4.py')
    editor=H.module('s53_editor_'+closure,source/'godot-addon/editor_owner.py')
    canonical=validation.canonical_bytes
    request=ev.read(package/'request.json');script=request['operation']=='script_text.replace'
    need(request['operation'] in ('scene.save','script_text.replace'),'operation scope')
    count=publication_summary(ev,package,source,closure,script)
    from studio.protocol.core import Request
    req=Request.from_dict(request)
    catalog=H.module('s53_catalog_'+closure,source/'godot-addon/contract.py')
    enabled=frozenset({'scene.inspect','scene.preview','scene.save','script_text.replace'})
    need(H.exact(ev.read(package/'discovery.json'),catalog.discovery(req.project_id,
         implemented=enabled,runtime_enabled=enabled).as_dict()),'frozen runtime discovery mismatch')
    before,dirty,after=[ev.read(package/(name+'.json')) for name in ('before','dirty','after')]
    events=ev.read(package/'events.json');journal=ev.read(package/'journal.json');reopened=ev.read(package/'reopened.json')
    replay=state.replay(events)
    need(all(H.exact(v,journal.get(k)) for k,v in replay.snapshot().items()),'journal event replay differs')
    response=ev.read(package/'response.json')
    raw=state.lookup_response(replay,req.command_id,req.digest)
    need(canonical(response)==raw and response['status']=='COMMITTED'
         and response['postconditions']['public_ack'] is True,'original durable response')
    need(H.exact(journal['commands'],reopened['commands']) and reopened['journal_read_only'] is True
         and reopened['execution_permitted'] is False,'readonly reopen receipt')
    for name in ('duplicate-response.json','lookup-response.json'):
        need(canonical(ev.read(package/name))==raw,'original reply changed')
    selector=ev.read(package/'selection.json');base.check_selection(selector,canonical)
    need(H.exact(journal['selected'],reopened['selected'])
         and H.exact(selector['selector'],journal['selected']['selector'])
         and H.exact(selector['selector_version'],journal['selected']['selector_version']),'actual selection binding')
    indexed={row['kind']:row for row in events}
    need(len(indexed)==len(events),'duplicate event phase')
    if script:
        captured,retired,adopted=script_editors(ev,package,source,editor,canonical)
        projected=H.module('s53_owner_'+closure,source/'godot-addon/publication_owner.py').GodotPublicationOwner
        from types import SimpleNamespace
        need(H.exact(indexed['RETIRED']['retirement'],projected._retirement_facts(
            SimpleNamespace(observation_id=retired['observation_id']),retired)),'retirement projection mismatch')
        owner=object.__new__(projected);owner._editor=SimpleNamespace(identity=adopted['new_editor'])
    else:
        captured,adopted=base.live_editor(ev,package,source,canonical,adoption=True,
            release=digest(canonical(editor._release())))
    base.bind_editor_event(indexed['CAPTURED']['capture'],captured)
    runs=base.validators(ev,package,(validation,linux,state,editor))
    candidates=[row for row in runs if digest(row[1].files['scenes/fixture.tscn'])==captured['scene_sha256']]
    need(len(candidates)==1,'one exact captured candidate validation')
    directory,bundle,native,observation=candidates[0]
    validation_receipt(indexed['VALIDATED']['validation'],req.command_id,validation,directory,bundle,native,observation)
    need(canonical(observation['semantic']['state'])==canonical(after['state'])==canonical(adopted['semantic_state'])
         and after['revision']=='sha256:'+digest(canonical(after['state'])),'actual Linux/editor semantic mismatch')
    need(canonical(dirty['state'])==canonical(captured['semantic_state'])
         and dirty['project_revision']==before['project_revision'] and dirty['revision']!=before['revision'],
         'dirty scene capture mismatch')
    manifest=journal['selected']['bundle_manifest']
    final=validation.bundle_codec.decode_bundle(canonical(manifest),bundle.files)
    need(manifest['files']==validation.parse_json(bundle.manifest_bytes)['files']
         and final.scene_revision==after['revision'] and final.project_revision==after['project_revision'],
         'selected manifest differs from validated/readback inputs')
    if script:
        facts=owner._fresh_adoption_facts(SimpleNamespace(observation_id=adopted['observation_id']),adopted,final,selector)
        need(H.exact(facts,indexed['READBACK']['adoption']),'fresh adoption projection differs')
        need(final.files[validation.bundle_codec.SCRIPT_PATH]==request['payload']['text'].encode('utf-8'),'selected script differs')
        need(H.exact(ev.read(package/'script-readback.json')['script'],adopted['script']),'actual script default report differs')
    else:
        facts=dict(indexed['READBACK']['adoption']);need(facts.pop('mode')=='same_editor','wrong adoption mode')
        base.bind_editor_event(facts,adopted,adoption=True)
        need(canonical(dirty['state'])==canonical(after['state']),'save changed full semantics')
    need(after['can_undo'] is False and after['can_redo'] is False
         and all({k:row[k] for k in ('sha256','size_bytes')}==after['working_files'][name]
                 for name,row in manifest['files'].items()),'complete selected editor files/history')
    stopped=ev.read(package/'stop-response.json')
    need(stopped['stopped'] is True and stopped['draining'] is False,'Stop response')
    return files,{'package':package.name,'source_closure_sha256':closure,'checks':count,
        'operation':request['operation'],'native_validations':len(runs),'original_response_verified':True,
        'fresh_generation':script,'live_registry_reopened_by_auditor':False,
        'preview_and_foreign_bearer_no_effect_producer_assertions_only':True}


def verify_stop(package,ev):
    source,files,closure=base.source(ev,package)
    sys.path.insert(0,str(source.parent))
    validation=H.module('s53_stop_validation_'+closure,source/'godot-addon/validation_owner.py')
    linux=H.module('s53_stop_linux_'+closure,source/'tests/godot/run_linux_probe.py')
    state=H.module('s53_stop_state_'+closure,source/'godot-addon/publication_state_v4.py')
    editor=H.module('s53_stop_editor_'+closure,source/'godot-addon/editor_owner.py')
    result=base.verify_stop(ev,package,source,closure,(validation,linux,state,editor))
    events=ev.read(package/'events.json');request=ev.read(package/'request.json')
    from studio.protocol.core import Request
    req=Request.from_dict(request)
    response=ev.read(package/'save-response.json')['result']
    need(state.lookup_response(state.replay(events),req.command_id,req.digest)==validation.canonical_bytes(response),
         'Stop original response is not durable')
    return files,{'package':package.name,'source_closure_sha256':closure,'operation':'control.stop',
                  'original_response_verified':True,**result}


def verify_units(package,ev):
    _,files,closure=base.source(ev,package)
    capture=ev.read(package/'capture.json');invocation=ev.read(package/'invocation.json')
    need(capture['passed'] is True and capture['source_closure_sha256']==closure
         and all(capture[key] is True for key in ('source_unchanged','snapshot_unchanged',
             'snapshot_inventory_unchanged','partitions_disjoint_complete')),'unit source/capture')
    need(invocation['runner_sha256']==files['build/bootstrap/run_fixture.py']
         and invocation['controller_sha256']==base.sha(ev.add(HERE/'run_unit_matrix.py'))
         and invocation['partitions']==['journals','other'],'unit controller binding')
    inventories=[];counts=[]
    for label,expected in zip(('journals','other'),capture['lanes']):
        result=ev.read(package/(label+'-result.json'));need(H.exact(result,expected),'unit result mismatch')
        host=result['host']
        need(host['argv']==['python.exe','-B','-c',invocation['code'],label],'unit argv binding')
        stdout,stderr=base.checked_host(ev,package,host)
        raw_counts=H.markers(stdout,'GT03_UNIT_COMPLETE ');raw_inventory=H.markers(stdout,'GT03_UNIT_INVENTORY ')
        need(H.exact(raw_counts,[result['counts']]) and H.exact(raw_inventory,[result['inventory']])
             and result['passed'] is True,'unit raw markers')
        need(H.integer(result['counts']['run']) and result['counts']['run']>0
             and all(H.integer(result['counts'][key],0) for key in ('failures','errors','skips')),'unit failures')
        need(len(result['inventory']['chosen'])==result['counts']['run'],'unit count differs from inventory')
        rows=base.unittest_rows(stderr,result['counts']['run'])
        need(set(rows)==set(result['inventory']['chosen']) and all(status=='ok' for status in rows.values()),
             'unit individual outcomes')
        inventories.append(result['inventory']);counts.append(result['counts'])
    a,b=inventories
    need(a['all']==b['all'] and not set(a['chosen'])&set(b['chosen'])
         and set(a['chosen'])|set(b['chosen'])==set(a['all']),'incomplete/overlapping unit partition')
    total={key:sum(row[key] for row in counts) for key in ('run','failures','errors','skips')}
    need(H.exact(total,capture['counts']),'unit totals')
    return files,{'package':package.name,'source_closure_sha256':closure,'operation':'unit_matrix',**total}


def git_proof(ref,artifacts,source):
    expected=dict(artifacts);expected.update({'studio/'+name:value for name,value in source.items()})
    for name in ('portable-artifacts.json','verification.json'):
        path=HERE/name;expected[path.relative_to(base.ROOT).as_posix()]=base.sha(path)
    names=sorted(expected);prefix=':' if ref=='index' else 'HEAD:'
    expressions=[prefix+base.ROOT.name+'/'+name for name in names]
    child=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(expressions)+'\n').encode(),
        cwd=base.ROOT.parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30)
    offset=0
    for name in names:
        end=child.stdout.index(b'\n',offset);header=child.stdout[offset:end].split()
        need(len(header)==3 and header[1]==b'blob','Git file missing: '+name)
        size=int(header[2]);offset=end+1;raw=child.stdout[offset:offset+size];offset+=size
        need(child.stdout[offset:offset+1]==b'\n','Git batch framing');offset+=1
        need(digest(raw)==expected[name] and raw==(base.ROOT/name).read_bytes(),'Git/disk mismatch: '+name)
    need(offset==len(child.stdout),'unexpected Git output')
    return {'passed':True,'ref':ref,'file_count':len(names),'source_files':len(source),
        'artifact_files':len(artifacts),'formal_acceptance':False,
        'portable_manifest_sha256':base.sha(HERE/'portable-artifacts.json')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('packages',nargs='+',type=Path)
    parser.add_argument('--stop',type=Path);parser.add_argument('--units',type=Path)
    parser.add_argument('--git-ref',choices=('index','HEAD'));args=parser.parse_args()
    ev=base.Evidence();ev.add(PREVIOUS);ev.add(base.HELPER);ev.add(Path(__file__))
    ev.add(HERE/'README.md');negative=ev.read(HERE/'negative-results.json');test=ev.add(HERE/'test_negative.py')
    need(negative['passed'] is True and H.integer(negative['run'],6)
         and all(H.integer(negative[k],0) for k in ('failures','errors','skips'))
         and negative['audit_sha256']==base.sha(Path(__file__)) and negative['test_sha256']==base.sha(test)
         and negative['native_processes_launched'] is False,'audit corruption regressions stale')
    results=[verify(path.resolve(),ev) for path in args.packages]
    if args.stop:results.append(verify_stop(args.stop.resolve(),ev))
    if args.units:results.append(verify_units(args.units.resolve(),ev))
    runtime=base.same_runtime([files for files,_ in results])
    result={'passed':True,'formal_acceptance':False,'status':'CANDIDATE',
        'lanes':[row for _,row in results],'runtime_files':runtime,'portable_artifact_count':len(ev.files)}
    if args.git_ref:
        need(H.exact(H.read(HERE/'portable-artifacts.json'),{'files':dict(sorted(ev.files.items()))}),
             'portable manifest changed since verification')
        need(H.exact(H.read(HERE/'verification.json'),result),'audit result changed since verification')
        proof=git_proof(args.git_ref,ev.files,results[0][0])
        (HERE/('git-byte-verification-'+args.git_ref+'.json')).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
        result['git_proof']=proof
    else:
        (HERE/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(ev.files.items()))},indent=2)+'\n',encoding='utf-8')
        (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='runtime_files'}))


if __name__=='__main__':main()
