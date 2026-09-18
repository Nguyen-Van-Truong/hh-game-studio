"""Supplement skipped original collector postchecks; read-only static evidence.

collect writes one exclusive observation; verify repeats the current/frozen check.
This never imports runtime/helpers and never rewrites any original exit/result.
"""
from pathlib import Path
import datetime,hashlib,json,sys
from inventory import OUT,ROOT,ARMS,plain

def sha(path):
    plain(path);before=path.stat();value=hashlib.sha256(path.read_bytes()).hexdigest();after=path.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return value

def load(path):return json.loads(path.read_bytes())

def check():
    raw_inventory=load(OUT/'raw-inventory.json')
    declarations={arm:load(Path(raw_inventory['roots'][arm+'/raw'])/'invocation.json') for arm in ARMS}
    source=declarations['original']['source_files']
    assert len(source)==51 and all(d['source_files']==source for d in declarations.values())
    closure=hashlib.sha256(''.join(k+'\0'+source[k]+'\n' for k in sorted(source)).encode()).hexdigest()
    assert closure=='e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
    rows=[]
    for name,expected in sorted(source.items()):
        current=sha(ROOT/'studio'/name)
        frozen={arm:sha(Path(raw_inventory['roots'][arm+'/raw'])/'source/studio'/name) for arm in ARMS}
        assert current==expected and all(v==expected for v in frozen.values()),name
        rows.append(dict(path=name,declared_sha256=expected,current_sha256=current,frozen_arm_sha256=frozen))
    helpers=[]
    for arm,invocation in declarations.items():
        raw=Path(raw_inventory['roots'][arm+'/raw'])
        for name,expected in sorted(invocation['helper_files'].items()):
            frozen=sha(raw/'source'/name);copy=sha(OUT/'raw'/arm/'raw/source'/name)
            assert frozen==copy==expected
            helpers.append(dict(arm=arm,path=name,declared_executed_sha256=expected,frozen_raw_sha256=frozen,preserved_copy_sha256=copy))
    runner_snapshot=OUT/'current-context/studio/build/bootstrap/run_fixture.py'
    runner_hash=sha(runner_snapshot)
    for arm in ARMS:
        assert load(Path(raw_inventory['roots'][arm+'/outer'])/'invocation.json')['runner_sha256']==runner_hash
    return dict(authority=0,formal_acceptance=False,source_closure_sha256=closure,current_runtime_files=rows,executed_helpers=helpers,
        outer_runner_snapshot_sha256=runner_hash,outer_runner_declared_hashes_match=True,
        scope='Offline timestamped supplement. Original collector failed before c.verify_sources/helper-after checks; those skipped runtime checks remain skipped.',
        domains=['Current runtime bytes compared to declared/frozen bytes for all51 files in all4 arms.',
                'Executed diagnostic helpers compared only to declared per-arm hashes, original raw/source and exact packet copies.',
                'Current measure_cost.py snapshot is contextual only and intentionally differs from older executed arms; never execution authority.',
                'No original exit/result rewritten and no claim that current checks happened during the original run.'])

if __name__=='__main__':
    assert sys.argv[1:] in [['collect'],['verify']]
    result=check()
    if sys.argv[1]=='collect':
        result['observed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (OUT/'offline-source-check.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    else:
        prior=load(OUT/'offline-source-check.json');prior.pop('observed_utc');assert prior==result
    print(json.dumps(dict(status='OFFLINE_SOURCE_BINDINGS_VERIFIED',formal_acceptance=False,current_runtime_files=51,frozen_source_copies=204,executed_helper_bindings=12)))
