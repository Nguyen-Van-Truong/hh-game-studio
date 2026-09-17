"""File-only S59 fixed-profile audit; each process imports one frozen closure."""
from pathlib import Path
import importlib.util
import importlib
import json
import sys

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
REVIEWS = BASE.parent
ROOT = REVIEWS.parent.parent
PROFILES = {'scene':'scene.save','checkpoint':'checkpoint.save','export':'export.publish'}
PROFILE = sys.argv[1]
assert PROFILE in PROFILES
HERE = BASE / PROFILE
HERE.mkdir(exist_ok=True)
PACKAGE = REVIEWS / ('20260917-gt04-s59-' + PROFILE + '-01')
SOURCE = PACKAGE / 'source/studio'
CLOSURE = '943cff74f23a61427765071f7fd6661acbdad23c0e8386364f5615a2a0016134'
COUNT = 594 if PROFILE == 'scene' else 328
spec = importlib.util.spec_from_file_location('s56_file_audit', REVIEWS/'20260917-gt04-s56-audit/verify_evidence.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.HERE, base.WRITER, base.SOURCE, base.CLOSURE = HERE, PACKAGE, SOURCE, CLOSURE
need, raw, read, sha = base.need, base.raw, base.read, base.sha


def verify():
    manifest = base.snapshot(PACKAGE)
    sys.path[:0] = [str(SOURCE.parent), str(SOURCE/'tests/blender')]
    from studio.protocol import core
    from studio.host.blender import client_ledger as ledger, client_write_catalog as catalog, client_preview as preview
    from studio.host.blender import publication_state as publication, glb_preflight
    from studio.host.core.journal import Journal
    runner = importlib.import_module('run_writer_client_probe')
    need(Path(ledger.__file__).resolve() == SOURCE/'host/blender/client_ledger.py'
         and Path(runner.__file__).resolve() == SOURCE/'tests/blender/run_writer_client_probe.py', 'frozen imports only')
    capture, report, gui, launch, runtime = base.package_facts(PACKAGE, manifest, runner, COUNT, 'writer-native.json')
    inventory = read(PACKAGE/'evidence-inventory.json')
    client = read(PACKAGE/'client.json')
    need(client == runner.client_report(raw(PACKAGE/'client-stdout.txt')), 'exact client report')
    exited = read(PACKAGE/'client-exit.json')
    need(exited == report['client_cleanup'] and runner.cli_cleanup_passed(exited)
         and client['pid'] == exited['pid'] and exited['pid'] not in (report['probe_pid'], report['native_pid']),
         'actual separate client process exit')
    base.zero_job(exited['job']); base.secret_shape(client)
    calls = client['calls']
    need(len(calls) == 36 and len(client['checks']) == 49 and len(report['checks']) == 10, 'bounded full integration trace')
    values = []
    for call in calls:
        data = call['response_wire'].encode()
        value = core.parse_json(data)
        need(core.canonical_bytes(value) == data and call['response_sha256'] == 'sha256:'+sha(data)
             and call['request_sha256'] == 'sha256:'+sha(core.canonical_bytes(call['request'])), 'HTTP wire hashes')
        need(call['role'] in ('writer','reader','foreign'), 'trace role scope')
        values.append(value)
    discoveries = [v for c,v in zip(calls,values) if c['route']=='/v1/discovery']
    need({v['operation'] for v in discoveries[0]['capabilities']} == catalog.EDIT_OPERATIONS|{catalog.READ,PROFILES[PROFILE]}
         and [v['operation'] for v in discoveries[1]['capabilities']] == [catalog.READ]
         and discoveries[-1]['capabilities'] == [] and len(discoveries)==4, 'connected/granted discovery and Stop')
    need(discoveries[0]['schema_digest'] == catalog.CATALOG_DIGEST
         and discoveries[0]['build'] == 'sha256:'+sha(core.canonical_bytes(runtime)), 'source catalog discovery')
    stops = [(c,v) for c,v in zip(calls,values) if c['listener']=='stop']
    need(len(stops)==2 and stops[0][0]['route']=='/v1/lookup' and stops[0][1]['code']=='UNSUPPORTED_ROUTE'
         and stops[1][0]['route']=='/v1/stop' and stops[1][1]['status']=='COMMITTED'
         and stops[1][1]['postconditions']['stopped'] is True, 'separate Stop listener')
    decoder = object.__new__(Journal); decoder.profile = ledger.DEFAULT_LIMITS
    data = base.closed_journal(gui,'client-ledger/client-commands.jsonl','client-commands.jsonl',inventory)
    records = [decoder._decode_record(line) for line in data.splitlines(keepends=True)]
    base.secret_shape(records)
    binding = ledger.LedgerBinding(**records[0]['receipt']['binding'])
    need(binding.catalog_digest==catalog.CATALOG_DIGEST and binding.generation==launch['session']
         and binding.source_sha256=='sha256:'+sha(core.canonical_bytes(runtime))
         and binding.owner_pin_sha256=='sha256:'+sha(core.canonical_bytes({'pid':report['native_pid'],
             'generation':launch['session'],'binary_sha256':launch['binary_sha256']})), 'ledger native owner binding')
    history = ledger.validate_history(records,binding)
    need(len(records)==19 and len(history)==9 and all(e['response'] is not None for e in history.values()), 'eight committed pairs and one known capacity rejection')
    by_public = {e['intent']['command_id']:e for e in history.values()}
    previews = {}
    successful = {}
    denials = set()
    previous = None
    for call,value in zip(calls,values):
        route = call['route']; key = call['request'].get('command_id')
        if value.get('status')=='REJECTED':
            denials.add(value['code'])
            need('observation' not in value.get('postconditions',{}) and 'publication' not in value.get('postconditions',{}), 'denial has no observation')
        if route == '/v1/preview':
            entry = by_public[key]
            request = core.Request.from_dict(call['request'])
            native = core.parse_json(ledger.unchunk(entry['intent']['native_chunks'],ledger.queue.c.MAX_BYTES))
            if request.operation in publication.PROFILES:
                projected = native if request.operation=='export.publish' else publication.save_request(native,request.operation)
                prepare = publication.preparation_command(projected,{'publication_profile':request.operation})
                native_preview = {'schema':preview.PREVIEW_SCHEMA,'command_id':prepare['command_id'],
                    'command_digest':ledger.queue.c.digest(prepare),'operation':prepare['operation'],
                    'before':value['before'],'requested_changes':prepare['payload'],'history_target':None,
                    'affected_files':[prepare['payload']['slot']+'.blend'],
                    'undo_policy':'immutable-private-copy-no-file-undo',
                    'value_policy':'native-preflight-only; artifact-hashes-require-publication',
                    'no_effect':True,'apply_id_reserved':False,'public_ack':False,'scene_state_durable':False}
                storage_id=read(PACKAGE/'publication.json')['publication']['storage_id']
                wrapper={'schema':'HH-BLENDER-PUBLICATION-PREVIEW-1','command_id':projected['command_id'],
                    'request_sha256':publication.sha(core.canonical_bytes(projected)),
                    'profile':request.operation,'storage_id':storage_id,'native_command':prepare,
                    'native_preview':native_preview,'no_effect':True,'apply_id_reserved':False,'public_ack':False}
                need(value==preview.normalize_publication_preview(request,native,wrapper,
                    source_sha256=binding.source_sha256,generation=binding.generation,storage_id=storage_id),
                    'exact file advisory/publication/profile binding')
                need(value['before']==previous,'live file preview before equals latest readback')
            else:
                # Rebuild the private advisory fields; normalizer checks exact
                # operation, typed payload, native ID/digest, history and bounds.
                private = {'schema':preview.PREVIEW_SCHEMA,'command_id':native['command_id'],
                    'command_digest':value['native_command_digest'],'operation':value['operation'],
                    'before':value['before'],'requested_changes':value['requested_changes'],
                    'history_target':value['history_target'],'affected_files':value['affected_files'],
                    'undo_policy':value['undo_policy'],'value_policy':value['value_policy'],
                    'no_effect':value['no_effect'],'apply_id_reserved':value['apply_id_reserved'],
                    'public_ack':value['public_ack'],'scene_state_durable':value['scene_state_durable']}
                need(value==preview.normalize_preview(request,native,private,
                    source_sha256=binding.source_sha256,generation=binding.generation), 'exact advisory request/native binding')
            if key in previews: need(previews[key]==value,'repeat preview exact and no ID reservation')
            previews[key]=value
        if route not in ('/v1/commands','/v1/lookup') or value.get('status')!='COMMITTED': continue
        entry = by_public[key]
        need(entry['response']==call['response_wire'].encode(),'all successful retry/lookup wires equal original terminal')
        if route=='/v1/lookup' or key in successful: continue
        request = core.Request.from_dict(call['request']); intent=entry['intent']
        native = core.parse_json(catalog.translate(request,binding=binding,session_id=intent['session_id']))
        need(entry['request']==request and ledger.make_intent(binding,intent['session_id'],request,native)==intent,
             'common request translated into exact persisted private bytes')
        successful[key]=value
        post=value['postconditions']
        need(post['public_ack'] is False and post['scene_state_durable'] is False and post['ledger_receipt_only'] is True,'receipt scope')
        if request.operation in publication.PROFILES: continue
        observed=post['observation']; scene=observed['scene']
        preview.observation(scene)
        need(value['result_hash']=='sha256:'+sha(core.canonical_bytes(observed))
             and value['result_revision']==observed['native_revision']==scene['revision']
             and observed['source_sha256']==binding.source_sha256 and observed['generation']==binding.generation
             and observed['pid']==report['native_pid'] and post['before_revision']==request.expected_revision,
             'actual observation hashes and native provenance')
        if previous is not None: need(request.expected_revision==previous['revision'],'actual revision chain')
        if request.operation in catalog.EDIT_OPERATIONS:
            need(previews[key]['before']==previous and post['actual_diff']==preview.actual_diff(previous,scene,operation=request.operation),
                 'preview before and actual effect diff')
        previous=scene
    need(len(successful)==8 and len(previews)==6, 'all effect and preview bindings present')
    need({'BLENDER_WRITER_GRANT_REQUIRED','BLENDER_LEDGER_COMMAND_CONFLICT','BLENDER_LEDGER_COMMAND_NOT_FOUND',
         'BLENDER_LEDGER_COMMAND_OWNER','BLENDER_OPERATION_FORBIDDEN','BLENDER_DEADLINE_EXPIRED','UNSUPPORTED_ROUTE','PUBLICATION_ONE_BUNDLE_CAPACITY'}<=denials,
         'required authority/retry/expired denials')
    observed=client['observed']
    need(observed['initial_inspect']['snapshot']['objects']==[] and observed['undo']==observed['transform']
         and observed['redo']==observed['material'] and observed['final_inspect']==observed['redo'], 'native empty/create/history chain')
    published=read(PACKAGE/'publication.json'); base.secret_shape(published)
    state={}
    need(published['events'][0]['kind']=='GENESIS','publication genesis')
    for event in published['events'][1:]: state=publication.reduce(state,event)
    need(state['phase']=='TERMINAL' and state['stopped'] is True,'complete witnessed publication transitions plus Stop')
    entry=by_public['Writer.Export']; private=core.parse_json(ledger.unchunk(entry['intent']['native_chunks'],ledger.queue.c.MAX_BYTES))
    common=successful['Writer.Export']; details=common['postconditions']['publication']
    if PROFILES[PROFILE]!='export.publish': private=publication.save_request(private,PROFILES[PROFILE])
    need(details['operation']==PROFILES[PROFILE] and published['manifest']['publication_profile']==PROFILES[PROFILE]
         and publication.profile(state['config'])==PROFILES[PROFILE], 'exact immutable save/publication profile')
    need(published['publication']==observed['publication']==details and state['intent']['request']==private
         and details['receipt']==state['terminal']['response'] and details['selector_version']==state['terminal']['selector_version']
         and details['receipt_sha256']=='sha256:'+sha(core.canonical_bytes(details['receipt']))
         and common['result_hash']=='sha256:'+sha(core.canonical_bytes(details))
         and common['postconditions']['durable_publication'] is True,'public/private/selector/receipt exact binding')
    file_root=published['roots']['files']
    need(Path(file_root).name==file_root and file_root.startswith('hh-files-'),'fixed protected root')
    selected=raw(PACKAGE/file_root/'active.json')
    need(selected==core.canonical_bytes(state['selector']) and sha(selected)==details['receipt']['selection']['selector_sha256'],'protected selector bytes')
    manifest_raw=raw(PACKAGE/file_root/'manifest.json')
    need(core.parse_json(manifest_raw)==published['manifest'] and sha(manifest_raw)==state['staged']['manifest']['sha256'],'protected manifest bytes')
    files={name:raw(PACKAGE/file_root/name) for name in publication.NAMES}
    for name,data in files.items():
        need(details['receipt']['artifacts'][name]=={'sha256':sha(data),'size_bytes':len(data)}
             and sha(data)==state['staged']['artifacts'][name]['sha256'],'protected artifact hashes')
    publication.check_snapshot_wire(published['manifest']['snapshot_native_json'],published['manifest']['snapshot'],private['expected_revision'])
    glb_preflight.bind_snapshot(glb_preflight.inspect_glb(files['scene.glb']),published['manifest']['snapshot'])
    need(core.canonical_bytes(published['manifest']['snapshot'])==core.canonical_bytes(observed['final_inspect']['snapshot']),'published geometry exactly observed scene')
    export=PACKAGE/published['export_directory']; export.relative_to(gui)
    export_close=read(export/'cleanup-attempt-0001.json'); export_result=read(export/'host-result.json')
    export_exit=read(export/'process-exit.json'); export_start=read(export/'process-start.json')
    need(export_close==published['export_cleanup'] and export_close['actual_process_exit']==export_exit
         and export_exit['pid']==export_start['pid'] and type(export_exit['exit_code']) is int and export_exit['exit_code']==0
         and export_close['wrapper_exit_code']==0 and export_close['threads_drained'] is True
         and export_close['cleanup_held'] is False and export_result['completed'] is True,'actual export exit and cleanup')
    base.zero_job(export_close['job'])
    for name in ('stdout.txt','stderr.txt'): raw(export/name)
    native=read(export/'result.json')
    need(native==export_result['native'] and native['scene_revision']==private['expected_revision']
         and native['input_sha256']==sha(files['checkpoint.blend']) and native['output_sha256']==sha(files['scene.glb'])
         and native['snapshot']==published['manifest']['snapshot'],'native background reopen/export hashes')
    lease_data=base.closed_journal(gui,'journal/blender-journal.jsonl','writer-leases.jsonl',inventory)
    leases=[decoder._decode_record(line) for line in lease_data.splitlines(keepends=True)]
    need(len(leases)==3 and leases[1]['kind']=='lease' and leases[2]['command_id']=='writer-stop'
         and leases[1]['fencing_epoch']==state['intent']['lease_epoch'],'native writer fence and Stop')
    for path,digest in list(base.FILES.items()):
        absolute=ROOT/path
        if absolute.is_relative_to(PACKAGE):
            relative=absolute.relative_to(PACKAGE).as_posix()
            if not relative.startswith('source/') and relative!='evidence-inventory.json':
                need(inventory[relative]=={'sha256':'sha256:'+digest,'bytes':absolute.stat().st_size},'captured artifact inventory')
    for path,data in base.COPIES.items():
        if not path.exists(): path.write_bytes(data)
        need(raw(path)==data,'exact portable closed journal')
    return {'passed':True,'formal_acceptance':False,'source_closure_sha256':CLOSURE,'source_files':len(manifest['files']),
        'unit_tests':COUNT,'client_checks':49,'profile':PROFILES[PROFILE],'native_checks':10,'http_calls':len(calls),'common_commands':len(history),
        'preview_operations':len(previews),'assertions':len(base.CHECKS),'native_handles_opened':0,
        'scope':'GT04 S59 fixed-profile component integration; final matrix and two critics still pending'}


if __name__=='__main__':
    try: result=verify()
    except Exception as error:
        result={'passed':False,'formal_acceptance':False,'failure':str(error),'type':type(error).__name__}
    (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    (HERE/'portable-artifacts.json').write_text(json.dumps(dict(sorted(base.FILES.items())),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result)); raise SystemExit(not result['passed'])
