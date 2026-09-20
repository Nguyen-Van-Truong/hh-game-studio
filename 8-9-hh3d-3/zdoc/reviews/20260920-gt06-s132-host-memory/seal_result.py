"""Selected exact-copy terminal packet; excludes journal, index and secrets."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
RUN='gt06-s129-host-memory-01'
RAW=ROOT/'studio/.local/reviews'/RUN
SUP=ROOT/'zdoc/reviews/20260920-gt06-s129-supervision'
OUT=BASE/'result-packet-01'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_bytes())
def write(path,value):
    with path.open('xb') as f:f.write((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
def main():
    result=read(RAW/'result.json')
    terminal=read(SUP/'runs'/RUN/'terminal.json')
    assert result['helper_exit'] is not None
    assert result['job']['closed'] and result['job']['zero_observed'] and result['handle']['closed']
    OUT.mkdir(exist_ok=False)
    (OUT/'.gitattributes').write_bytes(b'* -text\n')
    selected=[]
    for p in RAW.glob('*.json'): selected.append((p,Path('raw')/p.name))
    for p in (RAW/'owner').iterdir():
        if p.is_file() and p.suffix in ('.json','.txt'):selected.append((p,Path('raw/owner')/p.name))
    for label,folder in (('observer',SUP/'runs'/RUN),('scheduler',SUP/'tasks'/RUN)):
        for p in folder.iterdir():
            if p.is_file() and p.suffix in ('.json','.txt','.xml'):selected.append((p,Path(label)/p.name))
    manifest=[]
    for source,relative in sorted(selected,key=lambda x:x[1].as_posix()):
        for p in (source,*source.parents):
            assert not p.is_symlink() and not getattr(p.lstat(),'st_file_attributes',0)&0x400
        target=OUT/relative; target.parent.mkdir(exist_ok=True,parents=True)
        digest=sha(source); shutil.copyfile(source,target)
        assert digest==sha(target)==sha(source)
        manifest.append({'file':relative.as_posix(),'source':source.relative_to(ROOT).as_posix(),
                         'sha256':digest,'size_bytes':target.stat().st_size})
    summary=read(RAW/'summary.json') if (RAW/'summary.json').exists() else None
    cleanup=read(RAW/'child-cleanup.json') if (RAW/'child-cleanup.json').exists() else None
    rows=summary['rows'] if summary else []
    metrics=[{'batch':r['batch'],'rss_gate':r['original_host_observation']['counters']['rss_bytes']['value'],
              'handles':r['original_host_observation']['counters']['held_handles']['value'],
              'gap_ms':r['max_status_gap_ms'],
              'phases':{p:{k:r[p][k] for k in ('working_set','private_commit','allocated_python_blocks','page_faults')}
                        for p in ('start','report_live','after_write_report_held','released')}} for r in rows]
    analysis={'schema':'S132.host-result-analysis.1','run_id':RUN,'observed_utc':datetime.now(timezone.utc).isoformat(),
              'formal_acceptance':False,'eligible_for_dataset':False,
              'disposition':summary['disposition'] if summary else 'UNKNOWN',
              'completed_batches':summary['completed_batches'] if summary else None,
              'target_exit':read(RAW/'owner/process-exit.json') if (RAW/'owner/process-exit.json').exists() else None,
              'helper_exit':result['helper_exit'],'observer_terminal':terminal,'cleanup':cleanup,'metrics':metrics,
              'limits':['Host only; no native/ACK/idle/assembly','Observation boundaries differ from formal campaign',
                        'No leak/no-leak or original failure root-cause proof','Observer own process exit not held by itself']}
    write(OUT/'analysis.json',analysis)
    manifest.append({'file':'analysis.json','source':None,'sha256':sha(OUT/'analysis.json'),'size_bytes':(OUT/'analysis.json').stat().st_size})
    write(OUT/'manifest.json',{'schema':'S132.selected-result-manifest.1','files':manifest,
                             'exclusions':'commands directory/journal/SQLite/private files; unrelated files',
                             'formal_acceptance':False,'eligible_for_dataset':False})
    assert all(sha(OUT/r['file'])==r['sha256'] for r in manifest)
    print(json.dumps({'files':len(manifest),'manifest_sha256':sha(OUT/'manifest.json'),
                     'verified':True,'disposition':analysis['disposition'],'batches':len(metrics),
                     'target_exit':analysis['target_exit'],'helper_exit':result['helper_exit']}))

if __name__=='__main__':main()
