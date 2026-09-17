"""Sequential bounded native matrix; successful lanes are immutable and resumed.

All runtime and original probe code comes from the S59 snapshot. This supplement
replaces obsolete outer test-count/source pins, never native postconditions.
Each lane gets its own raw process/Job capture. This is not an acceptance vote.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
from binding import HERE, ROOT, STUDIO, BINARY, CLOSURE, sha, verify

CRASH = ('after_intent','before_selector','after_selector','before_terminal_witness','after_terminal_witness')
STOP = ('stop_export','stop_before_selector','stop_after_selector')
MODULES = {'ipc':'run_blender_ipc_probe', 'material':'run_material_probe',
    'cleanup':'run_export_cleanup_probe', 'durable':'run_durable_session_probe',
    'fifo':'run_writer_fifo_probe', 'checkpoint':'run_checkpoint_recovery_probe',
    'deadline':'run_absolute_deadline_probe'}
LANES = ('ui', *MODULES, *CRASH, *STOP)
MARKERS = {'ipc':'GT04_IPC_COMPLETE ', 'material':'GT04_MATERIAL_COMPLETE ',
    'cleanup':'GT04_CLEANUP_COMPLETE ', 'durable':'GT04_DURABLE_COMPLETE ',
    'fifo':'GT04_FIFO_COMPLETE ', 'checkpoint':'GT04_CHECKPOINT_RECOVERY_COMPLETE ',
    'deadline':'GT04_DEADLINE_NATIVE_COMPLETE '}


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def native_report(lane, output):
    name = 'absolute-deadline-native.json' if lane=='deadline' else 'native.json'
    return json.loads((output/name).read_bytes())


def ui(output):
    import run_blender_ui_probe as probe
    bg = probe.bg
    runner = bg.load(STUDIO/'build/bootstrap/run_fixture.py')
    env = {key:value for key,value in os.environ.items() if not key.upper().startswith(('PYTHON','BLENDER_','HH_BLENDER_'))}
    env['PYTHONDONTWRITEBYTECODE']='1'
    runs=[]; checks={}
    for lane in ('gui','background'):
        fixture=output/(lane+'-fixture'); fixture.mkdir()
        for key, folder in [('BLENDER_USER_RESOURCES','user'),('TEMP','temp'),('TMP','temp')]:
            path=fixture/folder; path.mkdir(exist_ok=True); env[key]=str(path)
        for phase in ('edit','reopen','checkpoint'):
            argv=[str(BINARY)]+(['--background'] if lane=='background' else [])
            argv+=['--factory-startup','--disable-autoexec','--offline-mode','--threads','1','--python-exit-code','17',
                '--python',str(STUDIO/'tests/blender'/('blender_ui_probe.py' if lane=='gui' else 'blender_probe.py')),
                '--','--phase',phase,'--owned-root',str(fixture)]
            run=runner.run_process(argv,cwd=STUDIO,output=output,timeout=60,label=lane+'-'+phase,env=env)
            runs.append(run); bg.require_host(run,output)
            assert not (output/run['stderr']).read_bytes()
            report=json.loads((fixture/(phase+'-result.json')).read_bytes())
            (probe.evaluate if lane=='gui' else bg.evaluate)(phase,report,(output/run['stdout']).read_text(encoding='utf-8'))
            checks[lane+'-'+phase]=len(report['checks'])
        expected=json.loads((fixture/'expected.json').read_bytes())
        for key in ('saved','checkpoint'):
            row=expected[key]; path=fixture/row['name']
            assert bg.sha(path)==row['sha256'] and path.stat().st_size==row['size_bytes']
    save(output/'native.json',{'passed':True,'checks':checks,'runs':runs,'public_ack':False})
    print('S59_UI_COMPLETE '+json.dumps({'passed':True,'checks':sum(checks.values())}),flush=True)
    return 0


def child(lane, output):
    verify()
    sys.path[:0]=[str(STUDIO.parent),str(STUDIO/'tests/blender')]
    from studio.host.blender.ui_host import source_files
    runtime=source_files()
    expected=json.loads((HERE/'execution-closure.json').read_bytes())
    assert runtime==expected['runtime_files']
    save(output/'runtime-binding.json',{'source_files':runtime,'source_closure_sha256':CLOSURE,
        'execution_closure_sha256':expected['execution_closure_sha256']})
    if lane=='ui': return ui(output)
    if lane in MODULES:
        module=importlib.import_module(MODULES[lane])
        assert Path(module.__file__).resolve()==STUDIO/'tests/blender'/(MODULES[lane]+'.py')
        if lane=='deadline': return module.frozen(output,BINARY,'GT04-S59-MATRIX-DEADLINE',CLOSURE)
        if lane=='ipc': return module.frozen(output,BINARY,export=True)
        return module.frozen(output,BINARY)
    import publication_recovery_bound as recovery
    result=(recovery.observe_crash if lane in CRASH else recovery.stop_case)(output,BINARY,lane)
    print('GT04_PUBLICATION_RECOVERY '+json.dumps({'case':lane,'passed':result['passed'],'public_ack':False}),flush=True)
    return 0


def evaluate(lane, output, host):
    sys.path[:0]=[str(STUDIO.parent),str(STUDIO/'tests/blender')]
    from run_client_ledger_probe import host_artifact_passed
    assert host_artifact_passed(output,host)
    assert not (output/'native-stderr.txt').read_bytes()
    text=(output/'native-stdout.txt').read_text(encoding='utf-8')
    if lane in CRASH+STOP:
        report=json.loads((output/'observed.json').read_bytes())
        marker='GT04_PUBLICATION_RECOVERY '
        expected={'case':lane,'passed':True,'public_ack':False}
        checks=1
    else:
        report=native_report(lane,output)
        if lane=='ui':
            checks=sum(report['checks'].values()); marker='S59_UI_COMPLETE '
        else:
            rows=report['checks']; checks=len(rows)
            assert checks>0 and len({row['label'] for row in rows})==checks
            assert all(row['passed'] is True for row in rows)
            marker=MARKERS[lane]
        expected={'passed':True,'checks':checks}
    assert report['passed'] is True
    assert [json.loads(line[len(marker):]) for line in text.splitlines() if line.startswith(marker)]==[expected]
    return checks


def run(lane):
    binding=verify()
    output=HERE/lane
    capture=output/'capture.json'
    if capture.exists():
        old=json.loads(capture.read_bytes())
        assert old['passed'] is True and old['execution_closure_sha256']==binding['execution_closure_sha256']
        for name,digest in old['artifacts'].items(): assert sha((output/name).read_bytes())==digest,name
        evaluate(lane,output,old['host'])
        print(json.dumps({'lane':lane,'resumed_verified_pass':True}),flush=True)
        return
    output.mkdir(exist_ok=False)
    sys.path[:0]=[str(STUDIO.parent),str(STUDIO/'tests/blender')]
    from run_blender_ipc_probe import load,sources
    runner=load(STUDIO/'build/bootstrap/run_fixture.py')
    host=runner.run_process([sys.executable,'-B',str(Path(__file__).resolve()),'--child',lane],
        cwd=STUDIO,output=output,timeout=210 if lane=='ui' else 120,label='native')
    result={'lane':lane,'host':host,'source_closure_sha256':CLOSURE,
        'execution_closure_sha256':binding['execution_closure_sha256'],'passed':False,'formal_acceptance':False}
    try:
        result['checks']=evaluate(lane,output,host)
        verify()
        assert sources(STUDIO)==json.loads((STUDIO.parent.parent/'source-closure.json').read_bytes())['files']
        result['passed']=True
    except Exception as error:
        result['failure']=type(error).__name__+': '+str(error)
    result['artifacts']={p.relative_to(output).as_posix():sha(p.read_bytes()) for p in output.rglob('*')
        if p.is_file() and p.name!='.writer' and '__pycache__' not in p.parts}
    save(capture,result)
    print(json.dumps({key:value for key,value in result.items() if key!='artifacts'}),flush=True)
    assert result['passed'],result.get('failure')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--child',choices=LANES)
    parser.add_argument('--lane',choices=LANES,action='append')
    args=parser.parse_args()
    if args.child: raise SystemExit(child(args.child,HERE/args.child))
    for lane in args.lane or LANES: run(lane)
