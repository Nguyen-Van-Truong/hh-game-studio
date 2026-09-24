"""Verify the S238 read-only capability catalog; no engine or device access."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]
def need(v,m):
    if not v: raise ValueError(m)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    pm=json.loads((HERE/'package-manifest.json').read_text(encoding='utf-8'))
    need(pm['package_id']=='gt07-10-s238-capability-catalog' and pm['authority']==0 and pm['formal_acceptance'] is False,'packet manifest scope')
    need({r['path'] for r in pm['files']}=={'README.md','catalog.json','verify.py'},'packet manifest members')
    for r in pm['files']:
        q=HERE/r['path']; need(q.is_file() and q.stat().st_size==r['size_bytes'] and hashlib.sha256(q.read_bytes()).hexdigest()==r['sha256'],f"packet:{r['path']}")
    c=json.loads((HERE/'catalog.json').read_text(encoding='utf-8'))
    need(c['authority']==0 and c['formal_acceptance'] is False,'scope')
    need(c['plan_revision']=='S238' and c['gt06_dependency']['accepted_full_runs']==0,'dependency')
    need(all(c['status'][k]=='PLANNED_UNOPENED' for k in ('GT07','GT08','GT09','GT10')),'statuses')
    need(c['decision'].startswith('READONLY_PREPARATION_ONLY'),'decision')
    count=0
    for rows in c['source_observations'].values():
        for row in rows:
            p=ROOT/row['path']; need(p.is_file() and '__pycache__' not in p.parts and '.godot' not in p.parts,row['path']); need(p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']); count+=1
    need(count>0,'observations')
    print(json.dumps({'run_id':c['run_id'],'observed_files':count,'authority':0,'formal_acceptance':False,'GT07_GT10':'PLANNED_UNOPENED'},sort_keys=True))
if __name__=='__main__': main()
