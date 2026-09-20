"""Seal a selected exact-copy view of S131 failure; never edits raw or gates."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
RUN='gt06-s129-host-attribution-03'
RAW=ROOT/'studio/.local/reviews'/RUN
SUP=ROOT/'zdoc/reviews/20260920-gt06-s129-supervision'
OUT=ROOT/'zdoc/reviews/20260920-gt06-s131-rss-failure'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    with p.open('xb') as f: f.write((json.dumps(v,indent=2,sort_keys=True)+'\n').encode())

def main():
    OUT.mkdir(exist_ok=False)
    (OUT/'.gitattributes').write_text('* -text\n',encoding='ascii')
    selected=[]
    def include(path,dest):
        if path.is_file(): selected.append((path,dest))
    for p in RAW.glob('*.json'): include(p,Path('raw')/p.name)
    for p in (RAW/'attempt').glob('*.json'): include(p,Path('raw/attempt')/p.name)
    for folder in ('owned','attempt/editor-host','attempt/import-host'):
        for p in (RAW/folder).iterdir():
            if p.is_file() and p.suffix in ('.json','.txt'):
                include(p,Path('raw')/folder/p.name)
    for folder in ('input','out'):
        for p in (RAW/'attempt/project/benchmark'/folder).glob('*.json'):
            include(p,Path('raw/attempt/project/benchmark')/folder/p.name)
    for folder,label in ((SUP/'runs'/RUN,'observer'),(SUP/'tasks'/RUN,'scheduler')):
        for p in folder.iterdir():
            if p.is_file(): include(p,Path(label)/p.name)
    # Direct S129 import evidence omitted from the earlier packet: supplement,
    # not a modification of the original S130 manifest/hash domain.
    old=ROOT/'studio/.local/reviews/gt06-s129-host-attribution-02/attempt/import-host'
    for name in ('invocation.json','capture.json','process-start.json','process-exit.json','stdout.txt','stderr.txt'):
        include(old/name,Path('s130-corrigendum/import-host')/name)
    rows=[]
    for source,relative in sorted(selected,key=lambda r:r[1].as_posix()):
        target=OUT/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        digest=sha(source)
        assert sha(target)==digest
        rows.append({'file':relative.as_posix(),'source':source.relative_to(ROOT).as_posix(),
                     'sha256':digest,'size_bytes':target.stat().st_size})
    joint=[json.loads(p.read_bytes()) for p in sorted((RAW/'attempt').glob('joint-*.json'))]
    counters=[{'batch':d['index'],'host':d['host']['counters'],
               'editor_rss':d['editor']['rss_bytes'],'editor_handles':d['editor']['held_handles'],
               'objects':d['barrier_receipt']['objects'],'resources':d['barrier_receipt']['resources'],
               'native_gap_ms':d['barrier_receipt']['max_status_gap_ms']} for d in joint]
    summary={'schema':'S131.failure-analysis.1','run_id':RUN,'formal_acceptance':False,
        'eligible_for_dataset':False,'observed_utc':datetime.now(timezone.utc).isoformat(),
        'failure':json.loads((RAW/'attempt/child-failure.json').read_bytes()),
        'counters':counters,'source_closure':'763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4',
        'baseline_batch':4,'host_rss_delta_bytes':45395968-40861696,
        'host_rss_growth_percent':100*(45395968/40861696-1),
        'root_cause':'UNKNOWN','leak_proven':False,
        'known_gaps':['editor target exit not recorded; helper2 does not imply target exit',
                      'observer self exit not recorded by retained launcher observer',
                      'RSS is working set only; private commit/allocation/page-fault timeline missing'],
        'next':'Analyze retained report/allocation lifetimes with a bounded no-engine replay; do not repeat full engine workload blindly.',
        's130_correction':{'s129_observed_job_time':None,'s129_import_actual_exit':0,
                          's129_benchmark_started':False,'numeric_156250_source':'S126 reference only'}}
    write(OUT/'analysis.json',summary)
    rows.append({'file':'analysis.json','source':None,'sha256':sha(OUT/'analysis.json'),
                 'size_bytes':(OUT/'analysis.json').stat().st_size})
    write(OUT/'manifest.json',{'schema':'S131.failure-manifest.1','formal_acceptance':False,
        'files':rows,'excluded':'raw commands journal, SQLite/private index, caches, generated project, secrets',
        'raw_root':RAW.relative_to(ROOT).as_posix()})
    checked=all(sha(OUT/r['file'])==r['sha256'] for r in rows)
    print(json.dumps({'files':len(rows),'verified':checked,'manifest_sha256':sha(OUT/'manifest.json')}))
    assert checked

if __name__=='__main__': main()
