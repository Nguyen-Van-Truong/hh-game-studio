"""Freeze once and partition the full GT03 unittest inventory, bounded per lane."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
STUDIO=ROOT/'studio'


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();output.relative_to(ROOT/'zdoc/reviews');output.mkdir(exist_ok=False)
    inventory=load('s54_unit_inventory',STUDIO/'tests/godot/run_editor_probe.py')
    files=inventory.inputs();source=output/'source/studio'
    for name,digest in files.items():
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((STUDIO/name).read_bytes())
        if sha(target)!=digest:raise ValueError('source changed during freeze')
    runner=load('s54_unit_runner',source/'build/bootstrap/run_fixture.py')
    closure=runner.source_closure_sha256(files)
    save(output/'source-closure.json',{'files':files,'source_closure_sha256':closure})
    code="""import unittest,json,sys
suite=unittest.defaultTestLoader.discover('tests/godot',pattern='test_*.py')
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item
all_tests=list(flatten(suite));ids=[case.id() for case in all_tests]
assert len(ids)==len(set(ids))
label=sys.argv[1]
chosen=[case for case in all_tests if (not case.id().startswith('test_publication_journal')
    if label=='other' else case.id().split('.')[0]==label)]
print('GT03_UNIT_INVENTORY '+json.dumps({'all':sorted(ids),'chosen':sorted(case.id() for case in chosen)}),flush=True)
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(chosen))
print('GT03_UNIT_COMPLETE '+json.dumps({'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}),flush=True)
sys.exit(not result.wasSuccessful())
"""
    labels=['test_publication_journal']+['test_publication_journal_v'+str(v) for v in range(2,6)]+['other']
    save(output/'invocation.json',{'code':code,'partitions':labels,
        'timeouts':{label:600 if label=='other' else 360 for label in labels},
        'runner_sha256':sha(source/'build/bootstrap/run_fixture.py'),'controller_sha256':sha(Path(__file__))})
    def lane(label):
        host=runner.run_process([sys.executable,'-B','-c',code,label],cwd=source,output=output,
            timeout=600 if label=='other' else 360,label=label)
        lines=(output/host['stdout']).read_text(encoding='utf-8').splitlines()
        marker=lambda prefix:[json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
        results=marker('GT03_UNIT_COMPLETE ');inventories=marker('GT03_UNIT_INVENTORY ')
        result={'host':host,'counts':results[0] if len(results)==1 else None,
            'inventory':inventories[0] if len(inventories)==1 else None}
        result['passed']=bool(host['exit_code']==host['wrapper_exit_code']==0 and host['tree_verified']
            and not host['timed_out'] and result['counts'] and all(result['counts'][key]==0
            for key in ('failures','errors','skips')) and result['counts']['run']>0)
        save(output/(label+'-result.json'),result)
        print(json.dumps({'lane':label,'counts':result['counts'],'passed':result['passed']}),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        lanes=list(pool.map(lane,labels))
    inventories=[row['inventory'] for row in lanes]
    selected=[name for row in inventories if row for name in row['chosen']]
    partition=bool(all(inventories) and all(row['all']==inventories[0]['all'] for row in inventories)
        and len(selected)==len(set(selected)) and set(selected)==set(inventories[0]['all'])
        and all(row['counts'] is not None and row['counts']['run']==len(row['inventory']['chosen']) for row in lanes))
    unchanged=files==inventory.inputs()
    snapshot=files=={name:sha(source/name) for name in files}
    clean_inventory=set(files)=={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    result={'source_closure_sha256':closure,'source_unchanged':unchanged,'snapshot_unchanged':snapshot,
        'snapshot_inventory_unchanged':clean_inventory,'partitions_disjoint_complete':partition,
        'counts':({key:sum(row['counts'][key] for row in lanes) for key in ('run','failures','errors','skips')}
            if all(row['counts'] is not None for row in lanes) else None),
        'passed':all(row['passed'] for row in lanes) and partition and unchanged and snapshot and clean_inventory,
        'formal_acceptance':False,'lanes':lanes}
    save(output/'capture.json',result)
    print(json.dumps({key:value for key,value in result.items() if key!='lanes'}),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
