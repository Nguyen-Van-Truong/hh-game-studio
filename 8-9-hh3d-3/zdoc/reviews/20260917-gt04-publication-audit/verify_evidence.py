"""Publication03 portable audit. Read-only by default; never opens an engine."""
import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import sys
sys.dont_write_bytecode=True
AUDIT=Path(__file__).resolve().parent;ROOT=AUDIT.parents[2]
PACKAGE=AUDIT.parent/'20260917-gt04-publication-03';FILES={}
EXPECTED_CLOSURE='fc54433ac4a373e6e79aac33de1e6641e1a434cf2894a8ced622a445db36cd20'

def digest(raw):return hashlib.sha256(raw).hexdigest()
def need(value,label):
    if not value:raise ValueError(label)

def verify(overrides=None,*,check_live=False):
    overrides=overrides or {};FILES.clear()
    def raw(path):
        name=path.relative_to(ROOT).as_posix();data=overrides.get(name,path.read_bytes())
        FILES[name]=digest(data);return data
    def read(path):return json.loads(raw(path))
    source=read(PACKAGE/'source-closure.json');files=source['files'];snapshot=PACKAGE/'source/studio'
    closure=digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(files.items())).encode())
    need(closure==source['source_closure_sha256']==EXPECTED_CLOSURE,'closure digest')
    need({path.relative_to(snapshot).as_posix():digest(raw(path)) for path in snapshot.rglob('*')
        if path.is_file() and '__pycache__' not in path.parts}==files,'frozen inventory')
    if check_live:
        for name,value in files.items():need(digest((ROOT/'studio'/name).read_bytes())==value,'live source '+name)
    runtime={name:value for name,value in files.items() if (name.endswith('.py') and
        name.startswith(('blender-addon/','host/core/','protocol/','host/blender/'))) or
        name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
    sys.path.insert(0,str(snapshot.parent))
    from studio.protocol.core import canonical_bytes
    from studio.host.core.private_events import PrivateEventLog
    from studio.host.blender import publication_state as model
    from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot
    capture=read(PACKAGE/'capture.json');native=read(PACKAGE/'native.json')
    need(capture['source_closure_sha256']==closure and capture['source_unchanged'] is True
        and capture['snapshot_unchanged'] is True and capture['candidate_only'] is True
        and capture['public_ack'] is False and native['source_files']==files,'source map binding')
    def process(label,record):
        actual=read(PACKAGE/record['host'])
        need(record['exit_code']==0 and record['wrapper_exit_code']==0 and actual['exit_code']==0
            and actual['target_pid']==record['target_pid'] and record['timed_out'] is False
            and record['tree_verified'] is True and record['ownership']=='gated_job_kill_on_close','actual '+label+' exit')
        raw(PACKAGE/record['stdout']);raw(PACKAGE/record['stderr'])
    process('unit',capture['unit']);process('native',capture['host']);process('reopen',native['reopen'])
    tests=raw(PACKAGE/'unit-stderr.txt').decode().replace('\r\n','\n')
    need(re.findall(r'Ran (\d+) tests in ',tests)==['135'] and tests.rstrip().endswith('OK')
        and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',tests,re.M))==135,'raw 135 tests')
    stdout=raw(PACKAGE/'native-stdout.txt').decode();need(not raw(PACKAGE/'native-stderr.txt'),'native stderr')
    checks=[json.loads(line[len('GT04_PUBLICATION_CHECK '):]) for line in stdout.splitlines()
        if line.startswith('GT04_PUBLICATION_CHECK ')]
    need(checks==native['checks'] and len(checks)==16 and len({row['label'] for row in checks})==16
        and all(row['passed'] is True for row in checks),'native 16 checks')
    complete=[json.loads(line[len('GT04_PUBLICATION_COMPLETE '):]) for line in stdout.splitlines()
        if line.startswith('GT04_PUBLICATION_COMPLETE ')]
    need(complete==[{'passed':True,'checks':16}] and native['passed'] is True
        and native['public_ack'] is False and native['formal_acceptance'] is False,'native completion')
    roots=list(PACKAGE.glob('blender-*'));need(len(roots)==1,'one GUI owner');gui=roots[0]
    launch=read(gui/'launch.json');start=read(gui/'process-start.json');end=read(gui/'process-exit.json')
    closed=read(gui/'close.json')
    def job(value):
        need(value['closed'] is True and value['zero_observed'] is True and value['active_count']==0
            and value['handle_retained'] is False and value['tainted'] is False
            and value['close_uncertain'] is False and not value['failed_operations'],'native Job zero')
    need(launch['source_files']==runtime and end=={'pid':start['pid'],'exit_code':0}
        and closed==native['cleanup'] and closed['actual_process_exit']==end and closed['wrapper_exit_code']==0
        and closed['closed'] is True and closed['held'] is False and closed['logs_overflow'] is False,'GUI binding')
    job(closed['job'])
    for name in ('control-hello.json','data-hello.json','stdout.txt','stderr.txt'):raw(gui/name)
    exports=list(gui.glob('export-*'));need(len(exports)==1,'one export after duplicate');export=exports[0]
    export_start=read(export/'process-start.json');export_end=read(export/'process-exit.json')
    result=read(export/'result.json');export_host=read(export/'host-result.json');limits=read(export/'limits.json')
    need(read(export/'launch.json')['source_files']==runtime and export_end=={'pid':export_start['pid'],'exit_code':0}
        and export_host['actual_process_exit']==export_end and export_host['wrapper_exit_code']==0
        and export_host['completed'] is True and export_host['snapshot_geometry_bound'] is True
        and export_host['native']==result and export_host['limits']==limits,'background actual exit/readback')
    job(export_host['job']);cleanup=read(export/'cleanup-attempt-0001.json')
    need(cleanup['job']==export_host['job'] and cleanup['cleanup_held'] is False
        and cleanup['threads_drained'] is True and cleanup['actual_process_exit']==export_end,'export cleanup')
    need(limits['job_memory_bytes']==2*1024**3 and limits['active_process_limit']==4
        and limits['job_user_time_100ns']==150000000 and limits['wall_seconds']==20,'resource caps')
    for name in ('stdout.txt','stderr.txt'):raw(export/name)
    custody=read(PACKAGE/'custody.json');root_names=native['roots']
    need(custody['storage_id']==native['storage_id'] and custody['phase']=='READY'
        and custody['project_id']==model.PROJECT,'custody storage')
    for name,key in (('files','files'),('store','blobs'),('log','events')):
        need(PureWindowsPath(custody[key]['path']).name==root_names[name],'custody root '+name)
    files_root=PACKAGE/root_names['files'];store_root=PACKAGE/root_names['store'];log_root=PACKAGE/root_names['log']
    stream=raw(log_root/'.events');events=[];offset=0;previous='0'*64;decoder=object.__new__(PrivateEventLog)
    binding=custody['events']['binding']
    decoder._genesis=lambda:{'kind':'GENESIS','store_id':log_root.name,'volume':binding['stream']['volume'],
        'file_id':binding['stream']['file_id'],'root_file_id':binding['root']['file_id']}
    while offset<len(stream):
        size=int.from_bytes(stream[offset:offset+4],'little');need(0<size<=16384,'event frame cap')
        body=stream[offset+4:offset+4+size];checksum=stream[offset+4+size:offset+size+36]
        event=decoder._decode(body,checksum,len(events)+1,previous)
        events.append(event);offset+=size+36;previous=checksum.hex()
    witness={'sequence':len(events),'sha256':previous,'size':offset}
    need(offset==len(stream) and witness==custody['events']['binding']['witnessed']
        and events==read(PACKAGE/'events.json'),'exact binary chain/custody witness')
    binding=custody['events']['binding'];genesis=events[0]
    need(genesis=={'kind':'GENESIS','store_id':log_root.name,'volume':binding['stream']['volume'],
        'file_id':binding['stream']['file_id'],'root_file_id':binding['root']['file_id']},'genesis native binding')
    need([x['kind'] for x in events]==['GENESIS','CONFIG','INTENT','STAGED','SELECTING','TERMINAL'],'exact transition sequence')
    state={}
    for event in events[1:]:state=model.reduce(state,event)
    need(state['phase']=='TERMINAL' and state['config']['generation']==launch['session']
        and state['config']['source_sha256']==digest(canonical_bytes(runtime))
        and state['config']['binary_sha256']==launch['binary_sha256'],'native generation/source binding')
    staged=state['staged'];manifest_raw=raw(files_root/'manifest.json');manifest=json.loads(manifest_raw)
    need(manifest_raw==raw(PACKAGE/'publication-manifest.json')==canonical_bytes(manifest)
        and staged['artifacts']==manifest['artifacts'] and manifest['source_files']==runtime
        and manifest['generation']==launch['session'] and manifest['binary_sha256']==launch['binary_sha256']
        and manifest['license']=='original-fixture' and manifest['external_inputs']==[]
        and manifest['public_ack'] is False,'complete manifest binding')
    need(manifest['command_id']==state['intent']['request']['command_id']
        and manifest['request_sha256']==state['intent']['request_sha256']
        and manifest['scene_revision']==state['intent']['request']['expected_revision'],'request manifest binding')
    native_snapshot=model.check_snapshot_wire(manifest['snapshot_native_json'],manifest['snapshot'],manifest['scene_revision'])
    need(model.queue.c.digest(native_snapshot)==result['scene_revision'] and native_snapshot==result['snapshot'],
        'native numeric revision preserved')
    artifacts={}
    for name,entry in dict(staged['artifacts'],**{'manifest.json':staged['manifest']}).items():
        model.blob(entry);content=raw(files_root/name);artifacts[name]=content
        need(len(content)==entry['file_version']['identity']['size'] and digest(content)==entry['sha256']
            and raw(store_root/entry['object_id'])==content,'protected bytes and staging mirror '+name)
    need(set(path.name for path in files_root.iterdir())=={'.writer','checkpoint.blend','scene.glb','manifest.json','active.json'},
        'protected complete namespace')
    selected=raw(files_root/'active.json');terminal=state['terminal']
    need(selected==canonical_bytes(state['selector']) and digest(selected)==terminal['selector_version']['sha256']
        and len(selected)==terminal['selector_version']['identity']['size'],'exact selector version')
    response=raw(PACKAGE/'response.json');fault=read(PACKAGE/'reply-loss-or-failure.json')
    need(response==canonical_bytes(terminal['response']) and digest(response)==terminal['response_sha256']==native['response_sha256']
        and native['fault']==fault['fault'] and native['fault']['armed'] is True and native['fault']['fired'] is True
        and native['fault']['terminal_sha256']==digest(response)
        and fault['chain']==[{'code':'PUBLICATION_OUTCOME_UNKNOWN','type':'PublicationError'},
            {'code':None,'type':'OSError'}],'exact lost-reply durable response')
    expected=read(export/'expected.json')
    need(artifacts['checkpoint.blend']==raw(export/'input.blend')==raw(gui/'project/export.blend')
        and digest(artifacts['checkpoint.blend'])==result['input_sha256']==expected['input_sha256']
        and manifest['input_identity']['size']==len(artifacts['checkpoint.blend'])
        and artifacts['scene.glb']==raw(export/'output.glb') and digest(artifacts['scene.glb'])==result['output_sha256']
        and expected['snapshot']==manifest['snapshot'] and expected['revision']==manifest['scene_revision'],'exact native binary graph')
    bind_snapshot(inspect_glb(artifacts['scene.glb']),manifest['snapshot'])
    need(manifest['native']=={'input_sha256':result['input_sha256'],'glb_sha256':result['output_sha256'],
        'profile':result['profile'],'main_thread_save':True,'background_reopen':True},'native profile manifest')
    reopened=read(PACKAGE/'reopened-native.json');expected_reopen=read(PACKAGE/'reopen-expected.json')
    reopen_stdout=raw(PACKAGE/'reopen-stdout.txt').decode()
    messages=[json.loads(line[len('GT04_PUBLICATION_REOPEN '):]) for line in reopen_stdout.splitlines()
        if line.startswith('GT04_PUBLICATION_REOPEN ')]
    need(messages==[reopened] and not raw(PACKAGE/'reopen-stderr.txt') and reopened['passed'] is True
        and reopened['public_ack'] is False and reopened['snapshot']==manifest['snapshot']
        and reopened['revision']==manifest['scene_revision'] and reopened['checkpoint_sha256']==result['input_sha256']
        and expected_reopen['sha256']==reopened['checkpoint_sha256']
        and expected_reopen['snapshot']==reopened['snapshot'] and expected_reopen['revision']==reopened['revision']
        and PureWindowsPath(expected_reopen['path']).name=='checkpoint.blend','fresh native protected checkpoint reopen')
    for root in (files_root,store_root,log_root):need(raw(root/'.writer')==b'','empty native writer guard')
    raw(gui/'journal/blender-journal.jsonl')
    for name in ('README.md','verify_evidence.py','test_evidence.py'):raw(AUDIT/name)
    return {'passed':True,'source_closure_sha256':closure,'source_files':len(files),'python_tests':135,
        'native_checks':16,'binary_events':len(events),'portable_artifacts':len(FILES),'public_ack':False,
        'formal_acceptance':False,'current_source_checked':check_live}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-derived',action='store_true')
    parser.add_argument('--check-live',action='store_true');args=parser.parse_args();result=verify(check_live=args.check_live)
    if args.write_derived:
        (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(FILES.items()))},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
