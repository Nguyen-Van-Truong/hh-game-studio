"""Focused independent S30 review on exact frozen copies; no engine launch."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
EXPECTED='60799065f406fbb3b13d2dc0df093477210927f86e84b54175dfd36351521a1a'
manifest=json.loads((ROOT/'zdoc/reviews/20260915-gt02-s30-01/source-closure.json').read_text(encoding='utf-8'))
source={name:(ROOT/'studio'/name).read_bytes() for name in manifest['files']}
assert all(hashlib.sha256(raw).hexdigest()==manifest['files'][name] for name,raw in source.items())
assert hashlib.sha256(''.join(sorted(f'8-9-hh3d-3/studio/{name}\0{sha}\n' for name,sha in manifest['files'].items())).encode()).hexdigest()==EXPECTED
selected=['test_transport_recovery','test_journal_durability','test_rejection_matrix','test_domain_contract',
          'test_transport.TransportTests.test_journal_full_rejects_admission_without_mutation',
          'test_transport.TransportTests.test_stop_closes_admission_even_when_journal_cannot_persist']
started=datetime.now(timezone.utc).isoformat()
clock=time.monotonic()
with tempfile.TemporaryDirectory(prefix='gt02-s30-final-b-') as tmp:
    snapshot=Path(tmp)
    for name,raw in source.items():
        path=snapshot/'studio'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
    sys.path[:0]=[str(snapshot),str(snapshot/'studio/tests/protocol')]
    suite=unittest.defaultTestLoader.loadTestsFromNames(selected)
    def ids(item):
        return [item.id()] if isinstance(item,unittest.TestCase) else [name for child in item for name in ids(child)]
    test_ids=ids(suite)
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    assert all((ROOT/'studio'/name).read_bytes()==raw for name,raw in source.items())
    record={'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
        'source_closure_sha256':EXPECTED,'source_files':len(source),'source_unchanged':True,
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':[{'id':test.id(),'reason':reason} for test,reason in result.skipped],
        'elapsed_seconds':time.monotonic()-clock,'test_ids':test_ids}
    Path(__file__).with_name('focused-results.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    Path(__file__).with_name('focused-log.txt').write_text(output.getvalue(),encoding='utf-8')
    print(json.dumps({key:value for key,value in record.items() if key!='test_ids'},indent=2))
    if not result.wasSuccessful(): print(output.getvalue())
    sys.exit(0 if result.wasSuccessful() else 1)
