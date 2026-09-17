"""File-only exact S59 native matrix audit, including all retained failed attempts."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent.parent
REVIEWS=HERE.parent
CLOSURE='943cff74f23a61427765071f7fd6661acbdad23c0e8386364f5615a2a0016134'
MATRIX=REVIEWS/'20260917-gt04-s59-matrix-02'
SUPPLEMENT=REVIEWS/'20260917-gt04-s59-matrix-03'
SOURCE=REVIEWS/'20260917-gt04-s59-scene-01/source/studio'
COUNTS={'ui':95,'ipc':31,'material':16,'cleanup':13,'durable':16,'fifo':19,'checkpoint':22,'deadline':19,
    'after_intent':1,'before_selector':1,'after_selector':1,'before_terminal_witness':1,'after_terminal_witness':1,
    'stop_export':1,'stop_before_selector':1,'stop_after_selector':1,'stop_after_terminal':1}
FILES={};CHECKS=[]


def need(value,label):
    if not value:raise ValueError(label)
    CHECKS.append(label)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def raw(path):
    path=path.absolute();path.relative_to(ROOT)
    need('..' not in path.parts,'no traversal in evidence path')
    for parent in (path,*path.parents):
        if parent.exists():
            need(not parent.is_symlink() and not getattr(parent.lstat(),'st_file_attributes',0)&0x400,'no reparse evidence path')
        if parent==ROOT:break
    if path.name.endswith('.guard') or '.cache' in path.parts or 'temp' in path.parts or any(part.endswith('-temp') for part in path.parts):
        # Preserve closed incidental bytes as evidence, never install a live
        # guard or generated Blender cache into a clean evidence checkout.
        captured=HERE/'closed-artifacts'/(sha(path.relative_to(ROOT).as_posix().encode())+'.captured')
        if path.exists():
            original=path.read_bytes()
            captured.parent.mkdir(exist_ok=True)
            if not captured.exists():captured.write_bytes(original)
            need(captured.read_bytes()==original,'exact captured closed incidental bytes')
        path=captured
    need(not path.is_symlink() and path.is_file(),'regular owned evidence')
    value=path.read_bytes()
    if path.name!='.writer':FILES[path.relative_to(ROOT).as_posix()]=sha(value)
    return value


def read(path):return json.loads(raw(path))


def verify():
    manifest=read(SOURCE.parent.parent/'source-closure.json')
    need(manifest['source_closure_sha256']==CLOSURE,'frozen source identity')
    need({p.relative_to(SOURCE).as_posix():sha(raw(p)) for p in SOURCE.rglob('*') if p.is_file()}==manifest['files'],
        'complete exact snapshot; no generated files in portable source')
    for name,digest in manifest['files'].items():need(sha((ROOT/'studio'/name).read_bytes())==digest,'working bytes match frozen source')
    sys.path[:0]=[str(SOURCE.parent),str(SOURCE/'tests/blender')]
    from studio.host.blender import publication_state as publication
    from studio.protocol.core import canonical_bytes
    from run_client_ledger_probe import host_artifact_passed
    import run_blender_ui_probe as ui_probe
    bindings={}
    for folder in (MATRIX,SUPPLEMENT):
        binding=read(folder/'execution-closure.json')
        need(binding['source_closure_sha256']==CLOSURE,'supplement same source closure')
        need(sha(json.dumps(binding['files'],sort_keys=True,separators=(',',':')).encode())==binding['execution_closure_sha256'],
             'effective execution digest')
        for name,digest in binding['files'].items():need(sha(raw(ROOT/name))==digest,'effective execution bytes')
        runtime={name:digest for name,digest in manifest['files'].items()
            if name.endswith('.py') and name.startswith(('blender-addon/','protocol/','host/blender/','host/core/'))
            or name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
        need(binding['runtime_files']==runtime and binding['runtime_sha256']==sha(canonical_bytes(runtime)),
             'complete native runtime binding')
        bindings[folder]=binding
    lanes=[]
    for lane,count in COUNTS.items():
        folder=SUPPLEMENT if lane in ('stop_after_selector','stop_after_terminal') else MATRIX
        output=folder/lane;capture=read(output/'capture.json');binding=bindings[folder]
        need(capture['passed'] is True and capture['checks']==count and capture['formal_acceptance'] is False,
             'native lane completed expected checks')
        need(capture['source_closure_sha256']==CLOSURE and capture['execution_closure_sha256']==binding['execution_closure_sha256'],
             'lane exact execution binding')
        need(host_artifact_passed(output,capture['host']),'raw target/wrapper exit and bounded owned tree')
        host=read(output/'native-host.json')
        need(host['target_pid']==capture['host']['target_pid'] and type(host['exit_code']) is int and host['exit_code']==0,
             'exact native target identity')
        for name,digest in capture['artifacts'].items():
            path=output/name;path.resolve().relative_to(output)
            need(sha(raw(path))==digest,'captured native artifact exact bytes')
        runtime=read(output/'runtime-binding.json')
        need(runtime=={'source_files':binding['runtime_files'],'source_closure_sha256':CLOSURE,
                       'execution_closure_sha256':binding['execution_closure_sha256']},'child exact runtime proof')
        for path in output.rglob('launch.json'):
            launch=read(path)
            if 'source_files' in launch:need(launch['source_files']==binding['runtime_files'],'all launched children use same runtime')
        stdout=raw(output/'native-stdout.txt').decode('utf-8')
        need(raw(output/'native-stderr.txt')==b'','no unexpected host diagnostics')
        if lane=='ui':
            report=read(output/'native.json')
            need(report['passed'] is True and len(report['runs'])==6 and sum(report['checks'].values())==count,'six native UI/background phases')
            for run in report['runs']:
                need(host_artifact_passed(output,run),'actual GUI/background phase exit')
                label=run['stdout'].removesuffix('-stdout.txt');kind,phase=label.split('-')
                native=read(output/(kind+'-fixture')/(phase+'-result.json'))
                (ui_probe.evaluate if kind=='gui' else ui_probe.bg.evaluate)(phase,native,raw(output/run['stdout']).decode('utf-8'))
                need(raw(output/run['stderr'])==b'','clean GUI/background phase stderr')
            marker='S59_UI_COMPLETE '
        elif lane in ('ipc','material','cleanup','durable','fifo','checkpoint','deadline'):
            report=read(output/('absolute-deadline-native.json' if lane=='deadline' else 'native.json'))
            rows=report['checks']
            need(report['passed'] is True and len(rows)==len({row['label'] for row in rows})==count
                 and all(row['passed'] is True for row in rows),'complete unique native result checks')
            marker={'ipc':'GT04_IPC_COMPLETE ','material':'GT04_MATERIAL_COMPLETE ','cleanup':'GT04_CLEANUP_COMPLETE ',
                'durable':'GT04_DURABLE_COMPLETE ','fifo':'GT04_FIFO_COMPLETE ','checkpoint':'GT04_CHECKPOINT_RECOVERY_COMPLETE ',
                'deadline':'GT04_DEADLINE_NATIVE_COMPLETE '}[lane]
        else:marker='GT04_PUBLICATION_RECOVERY '
        expected=({'case':lane,'passed':True,'public_ack':False} if count==1 else {'passed':True,'checks':count})
        need([json.loads(line[len(marker):]) for line in stdout.splitlines() if line.startswith(marker)]==[expected],
             'raw completion marker equals complete native result')
        if lane in ('after_intent','before_selector','after_selector','before_terminal_witness','after_terminal_witness',
                    'stop_export','stop_before_selector','stop_after_selector','stop_after_terminal'):
            observed=read(output/'observed.json');recovery=read(output/'recovery.json');ready=read(output/'ready.json')
            need(observed['passed'] is True and observed['case']==lane and observed['recovery']==recovery,'exact recovery result')
            committed=lane in ('after_terminal_witness','stop_after_terminal')
            expected='HELD' if lane=='before_terminal_witness' else 'COMMITTED' if committed else 'UNKNOWN'
            need(recovery['status']==expected and recovery['bytes_unchanged'] is True
                 and recovery['live_scene_recovered'] is False,'terminal witness determines recovery, never live restart')
            for name,digest in recovery['persisted_graph'].items():
                if Path(name).name=='.writer':
                    need(digest==sha(b''),'empty writer sentinel has no recovery content')
                    if (output/name).exists():need(sha((output/name).read_bytes())==digest,'original closed sentinel unchanged')
                else:need(sha(raw(output/name))==digest,'readonly recovery persisted graph unchanged')
            state=ready['image']['state']
            if committed:
                response=read(output/'recovered-response.json')
                need(response==recovery['response'] and response['status']=='COMMITTED'
                     and recovery['response_sha256']==sha(canonical_bytes(response)),'exact terminal replay')
            elif lane!='before_terminal_witness':
                need(recovery['readonly'] is True and recovery['retry_exact'] is True,'unknown prefix remains lookup only')
            if lane in ('stop_after_selector','stop_after_terminal'):
                need(('active.json' in ready['image']['artifacts']) and ready['image']['phase']==('TERMINAL' if committed else 'SELECTING')
                     and (state.get('terminal') is not None)==committed,'Stop selector is not terminal witness')
            if lane.startswith('stop_'):
                need(observed['native_stop_ms']<3000 and observed['stop']=={'stopped':True,'public_ack':False},'priority Stop')
            else:
                need(observed['host_exit_code']==observed['observed_host_exit_code']==86
                     and all(row['live_wait_before']==258 and row['dead_wait_after']==0 for row in observed['processes']),
                     'actual host crash and exact owned children dead')
        lanes.append({'lane':lane,'checks':count,'execution_closure_sha256':binding['execution_closure_sha256'],
                      'directory':output.relative_to(ROOT).as_posix()})
    result={'passed':True,'formal_acceptance':False,'source_closure_sha256':CLOSURE,'source_files':len(manifest['files']),
        'lanes':lanes,'lane_count':len(lanes),'top_level_native_checks':sum(COUNTS.values()),
        'assertions':len(CHECKS),'native_handles_opened':0,
        'limitations':['component proof only','two independent final critics pending','no writable restart or restored Undo claim']}
    return result


if __name__=='__main__':
    try:result=verify()
    except Exception as error:result={'passed':False,'failure':str(error),'type':type(error).__name__,'formal_acceptance':False}
    (HERE/'matrix-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    (HERE/'matrix-portable-artifacts.json').write_text(json.dumps(dict(sorted(FILES.items())),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({key:value for key,value in result.items() if key!='lanes'}));raise SystemExit(not result['passed'])
