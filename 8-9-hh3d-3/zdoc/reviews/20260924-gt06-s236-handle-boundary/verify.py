"""Verify S236 sealed diagnostic from raw bytes and identity receipts."""
from pathlib import Path
import hashlib,json,zipfile
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
RAW=ROOT/'8-9-hh3d-3/studio/.local/reviews/gt06-s236-handle-boundary-01'; ARCH=ROOT/'8-9-hh3d-3/studio/.local/archives/gt06-s236-handle-boundary-01-s237-terminal.zip'
def sha(b): return hashlib.sha256(b).hexdigest()
def doc(b): return json.loads(b)
def need(x,m):
    if not x: raise ValueError(m)
def regular(p):
    need(p.is_file() and not p.is_symlink(),f'file:{p}')
    return p.read_bytes()
def verify_packet_manifest():
    m=doc(regular(HERE/'package-manifest.json'))
    need(m['package_id']=='gt06-s236-handle-boundary' and m['authority']==0 and m['formal_acceptance'] is False,'packet manifest scope')
    listed={x['path'] for x in m['files']}; need(listed=={'README.md','analysis.json','verify.py'},'packet manifest members')
    for row in m['files']:
        b=regular(HERE/row['path']); need(len(b)==row['size_bytes'] and sha(b)==row['sha256'],f"packet:{row['path']}")
def main():
    verify_packet_manifest()
    a=doc(regular(HERE/'analysis.json')); need(a['authority']==0 and a['formal_acceptance'] is False,'authority')
    man=regular(RAW/'raw-manifest.json'); need(sha(man)==a['raw_manifest_sha256'],'manifest')
    arc=regular(ARCH); need(sha(arc)==a['archive_sha256'],'archive')
    m=doc(man); rows=m['files']; need(len(rows)==a['raw_entries'],'rows'); payload={}
    for row in rows:
        p=row['path']; need(p.startswith('raw/') and p not in payload,'path'); b=regular(RAW/Path(p[4:])); need(len(b)==row['bytes'] and sha(b)==row['sha256'],p); payload[p]=b
    actual={'raw/'+p.relative_to(RAW).as_posix() for p in RAW.rglob('*') if p.is_file() and p.name!='raw-manifest.json'}; need(actual==set(payload),'membership')
    with zipfile.ZipFile(ARCH) as z:
        names=z.namelist(); need(len(names)==a['archive_members'] and len(set(names))==len(names),'zip count'); need(set(names)==set(payload)|{'raw-manifest.json'},'zip members'); need(z.read('raw-manifest.json')==man,'zip manifest')
        for n,b in payload.items(): need(z.read(n)==b,n)
    ctx=doc(payload['raw/context.json']); need(len(ctx['source_files'])==a['source_files'] and ctx['source_closure_sha256']==a['source_closure_sha256'],'source closure')
    need(all(isinstance(k,str) and isinstance(v,str) and len(v)==64 for k,v in ctx['source_files'].items()),'source file hashes')
    fail=doc(payload['raw/child-failure.json']); need(fail['code']==a['terminal_reason'] and fail['completed_batches']==9,'bound')
    boundary=doc(payload['raw/handle-boundary.json']); samples=boundary['samples']; need(boundary['no_next_start_permit'] and boundary['formal_acceptance'] is False and boundary['collection_error'] is None,'boundary scope')
    pre=[r['observation']['held_handles']['value'] for r in samples if r['phase']=='original_pre_ack']; post=[r['observation']['held_handles'] for r in samples if r['phase']=='after_ack']; idle=[r['observation']['held_handles'] for r in samples if r['phase']=='terminal_idle']; need(pre==a['pre_ack_handles'] and post==a['post_ack_handles'] and idle==a['terminal_idle_handles'],'counter rows')
    target_ids={(r['pid'],r['process_start']) for r in samples}; need(target_ids=={(a['target_pid'],a['target_process_start'])},'sample target identity')
    clean=doc(payload['raw/child-terminal-cleanup.json']); obs=clean['observations']; need(obs['editor_exit_after_cleanup']['exit_code']==2 and obs['editor_exit_after_cleanup']['natural_exit_not_inferred'],'cleanup exit'); need(obs['editor_exit_after_cleanup']['pid']==a['target_pid'] and obs['editor_exit_after_cleanup']['process_start']==a['target_process_start'],'cleanup identity'); need(obs['editor_owner']['job']['zero_observed'] and obs['editor_owner']['job']['closed'] and not obs['editor_owner']['job']['handle_retained'],'job'); need(obs['import_target']['actual_target_exit']['exit_code']==0,'import')
    parent=doc(payload['raw/parent-result.json']); need(parent['host_actual_exit']['exit_code']==0 and parent['job']['zero_observed'] and parent['job']['closed'] and not parent['job']['handle_retained'],'host')
    print(json.dumps({'run_id':a['run_id'],'raw_entries':len(payload),'archive_members':len(names),'pre_ack_handles':pre,'post_ack_handles':post,'terminal_idle_handles':idle,'failure_reproduced':False,'formal_acceptance':False,'authority':0},sort_keys=True))
if __name__=='__main__': main()
