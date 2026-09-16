"""Verify the recorded coordinator closeout without modifying frozen records."""
import json
from pathlib import Path
import verify_evidence as evidence


def verify():
    record=evidence.read(evidence.AUDIT/'acceptance.json')
    assert record['gate']=='GT-02' and record['status']=='ACCEPTED'
    assert record['source_closure_sha256']==evidence.CLOSURE and record['source_files']==106
    assert evidence.sha(evidence.AUDIT/'verification.json')==record['coordinator_verification_sha256']
    assert evidence.sha(evidence.AUDIT/'git-byte-verification-head.json')==record['git_head_proof_sha256']
    assert evidence.read(evidence.AUDIT/'git-byte-verification-head.json')['head_at_verification'].startswith(record['source_checkpoint'])
    assert len(record['critics'])==2
    assert {row['reviewer'] for row in record['critics']}=={'independent-a','independent-b'}
    assert len({row['report'] for row in record['critics']})==2
    for row in record['critics']:
        path=evidence.confined(evidence.ROOT,row['report'])
        assert evidence.sha(path)==row['sha256']
        text=path.read_text(encoding='utf-8')
        assert row['verdict']=='PASS' and row['tick']=='yes'
        for marker in ('VERDICT=PASS','TICK=yes','SOURCE_CLOSURE_SHA256='+evidence.CLOSURE):
            assert marker in text
        for name,digest in row['evidence'].items():
            assert evidence.sha(evidence.confined(evidence.ROOT,name))==digest,name
    evidence.verify()
    return {'status':'ACCEPTANCE_RECORD_VERIFIED','gate':'GT-02',
            'source_closure_sha256':evidence.CLOSURE,'independent_reviews':2}


if __name__=='__main__':
    if not __debug__: raise SystemExit('OPTIMIZED_VERIFICATION_FORBIDDEN')
    result=verify()
    Path(__file__).with_name('acceptance-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
