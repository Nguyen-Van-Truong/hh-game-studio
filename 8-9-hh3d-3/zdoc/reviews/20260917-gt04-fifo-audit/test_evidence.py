import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
path=Path(__file__).with_name('verify_evidence.py')
spec=importlib.util.spec_from_file_location('fifo_audit',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class AuditTests(unittest.TestCase):
    def reject(self,path,change):
        value=json.loads(path.read_bytes());change(value)
        with self.assertRaises((ValueError,KeyError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix():json.dumps(value).encode()})
    def test_real_package(self):self.assertTrue(audit.verify()['passed'])
    def test_native_exit(self):self.reject(audit.PACKAGE/'native-host.json',lambda x:x.update(exit_code=17))
    def test_client_exit(self):self.reject(audit.PACKAGE/'client-0-exit.json',lambda x:x.update(exit_code=17))
    def test_client_pid_alias(self):self.reject(audit.PACKAGE/'native.json',lambda x:x['client_pids'].__setitem__(1,x['client_pids'][0]))
    def test_grant_stale_fence(self):self.reject(audit.PACKAGE/'native.json',lambda x:x['grants'][1]['lease'].update(fencing_epoch=2))
    def test_response_tamper(self):self.reject(audit.PACKAGE/'client-alice.json',lambda x:x['response'].update(status='UNKNOWN'))
    def journal_change(self,change):
        path=next(audit.PACKAGE.glob('blender-*/journal/*.jsonl'))
        rows=[json.loads(line) for line in path.read_bytes().splitlines()];change(rows)
        def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        for row in rows:row['checksum']=hashlib.sha256(canonical(row['record'])).hexdigest()
        data=b''.join(canonical(row)+b'\n' for row in rows)
        with self.assertRaises((ValueError,KeyError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix():data})
    def test_checksummed_stop_tamper(self):
        def change(rows):
            for row in rows:
                if row['record'].get('command_id')=='writer-stop':row['record']['receipt']['stopped']=False
        self.journal_change(change)
    def test_checksummed_fifo_order_swap(self):
        def change(rows):
            indexes=[i for i,row in enumerate(rows) if row['record'].get('project_id','').endswith('.writer-requests')
                and row['record'].get('command_id') in ('ticket-alice','ticket-bob')
                and row['record']['status']=='ACCEPTED_PENDING']
            rows[indexes[0]],rows[indexes[1]]=rows[indexes[1]],rows[indexes[0]]
        self.journal_change(change)

if __name__=='__main__':unittest.main()
