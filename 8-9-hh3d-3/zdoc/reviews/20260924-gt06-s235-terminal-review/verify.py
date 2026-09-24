"""Verify the sealed S232 terminal package from raw bytes only."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
RAW=ROOT/'8-9-hh3d-3/studio/.local/reviews/gt06-s232-formal-01'
ARCH=ROOT/'8-9-hh3d-3/studio/.local/archives/gt06-s232-formal-01-s235-terminal.zip'
SUP=ROOT/'8-9-hh3d-3/studio/.local/reviews/gt06-s232-formal-01-supervisor'
def sha(b): return hashlib.sha256(b).hexdigest()
def doc(b): return json.loads(b)
def need(x,m):
    if not x: raise ValueError(m)
def regular(p):
    need(p.is_file() and not p.is_symlink(),f'file:{p}')
    return p.read_bytes()
def main():
    a=doc(regular(HERE/'analysis.json')); need(a['authority']==0 and a['formal_acceptance'] is False,'authority')
    need(sha(regular(RAW/'raw-manifest.json'))==a['raw_manifest_sha256'],'raw manifest')
    archive=regular(ARCH); need(sha(archive)==a['archive_sha256'],'archive')
    m=doc(regular(RAW/'raw-manifest.json')); rows=m['files']; need(len(rows)==a['raw_entries'],'entry count')
    payload={}
    for row in rows:
        p=row['path']; need((p.startswith('raw/') or p.startswith('supervisor/')) and p not in payload,'manifest path')
        root=RAW if p.startswith('raw/') else SUP
        rel=p.removeprefix('raw/').removeprefix('supervisor/')
        b=regular(root/Path(rel)); need(len(b)==row['bytes'] and sha(b)==row['sha256'],p); payload[p]=b
    actual_raw={'raw/'+p.relative_to(RAW).as_posix() for p in RAW.rglob('*') if p.is_file() and p.name!='raw-manifest.json'}
    actual_sup={'supervisor/'+p.relative_to(SUP).as_posix() for p in SUP.rglob('*') if p.is_file() and p.name not in ('task-deleted.json',)}
    need(actual_raw|actual_sup==set(payload),'raw exact')
    with zipfile.ZipFile(ARCH) as z:
        names=z.namelist(); need(len(names)==a['archive_members'] and len(set(names))==len(names),'zip entries')
        need(set(names)==set(payload)|{'raw-manifest.json'},'zip exact'); need(z.read('raw-manifest.json')==regular(RAW/'raw-manifest.json'),'zip manifest')
        for n,b in payload.items(): need(z.read(n)==b,n)
    fail=doc(payload['raw/run-00-attempt-01/child-failure.json']); need(fail['code']==a['failure_code'] and fail['completed_batches']==9,'failure')
    s=fail['screen_observation']; need(s['batch_index']==8 and s['role']=='editor' and s['counter']=='held_handles' and s['baseline_value']==552 and s['observed_value']==554,'screen row')
    clean=doc(payload['raw/run-00-attempt-01/child-terminal-cleanup.json']); obs=clean['observations']; owner=obs['editor_owner']; job=owner['job']
    need(obs['editor_exit_after_cleanup']['exit_code']==2 and obs['editor_exit_after_cleanup']['natural_exit_not_inferred'] is True,'editor cleanup exit')
    need(job['closed'] and job['zero_observed'] and job['handle_retained'] is False and owner['closed'],'editor cleanup')
    need(obs['import_target']['actual_target_exit']['exit_code']==0 and obs['import_observer']['probe_handles_released'] is True,'import cleanup')
    host=doc(payload['raw/run-00-attempt-01/host-owner/process-exit.json']); imp=doc(payload['raw/run-00-attempt-01/import-host/process-exit.json'])
    need(host['exit_code']==1 and imp['exit_code']==0,'actual exits')
    need(clean['supervisor_actual_exit'] is None and clean['formal_acceptance'] is False,'supervisor scope')
    joints=[doc(payload[f'raw/run-00-attempt-01/joint-{i:02d}.json']) for i in range(9)]
    need(len(joints)==9 and joints[-1]['editor']['held_handles']['value']==554 and joints[4]['editor']['held_handles']['value']==552,'joint rows')
    need(len([n for n in payload if n.startswith('raw/run-00-attempt-01/counter-probe-')])==0,'formal raw no probe files')
    task=doc(regular(HERE/'task-deleted.json')); need(task['formal_acceptance'] is False and task['campaign_id']==a['campaign_id'],'task supplement')
    print(json.dumps({'campaign_id':a['campaign_id'],'raw_entries':len(payload),'archive_members':len(names),'failure':s,'host_exit':host['exit_code'],'import_exit':imp['exit_code'],'editor_cleanup_exit':obs['editor_exit_after_cleanup']['exit_code'],'supervisor_actual_exit':None,'authority':0,'formal_acceptance':False},sort_keys=True))
if __name__=='__main__': main()
