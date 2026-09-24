"""Verify the S239 bounded-resume ADR packet."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
def need(v,m):
    if not v: raise ValueError(m)
def main():
    d=json.loads((HERE/'decision.json').read_text(encoding='utf-8'))
    need(d['authority']==0 and d['formal_acceptance'] is False,'scope')
    a=d['authorization']; need(a['campaign_id']=='gt06-s239-formal-01','campaign')
    need(a['source_closure_sha256']=='d7c78724ed827c8182af62c3f7bc1489d8dd35d29abe1f70216736a896e66bb3','source')
    need(a['profile_sha256']=='0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85','profile')
    need('timeout' in ' '.join(a['changes_forbidden']) and 'partial merge' in a['changes_forbidden'],'frozen gate')
    need(d['decision'].startswith('OWNER_AUTHORIZED_BOUNDED_RESUME'),'decision')
    pm=json.loads((HERE/'package-manifest.json').read_text(encoding='utf-8'))
    need(pm['package_id']=='gt06-s239-owner-resume' and pm['authority']==0 and pm['formal_acceptance'] is False,'manifest scope')
    need({r['path'] for r in pm['files']}=={'README.md','decision.json','verify.py'},'manifest members')
    for r in pm['files']:
        p=HERE/r['path']; b=p.read_bytes(); need(len(b)==r['size_bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path'])
    print(json.dumps({'adr_id':d['adr_id'],'campaign_id':a['campaign_id'],'formal_gate_unchanged':True,'authority':0,'formal_acceptance':False},sort_keys=True))
if __name__=='__main__': main()
