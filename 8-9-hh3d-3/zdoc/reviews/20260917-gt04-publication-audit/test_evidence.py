import importlib.util
import json
from pathlib import Path
import unittest
path=Path(__file__).with_name('verify_evidence.py')
spec=importlib.util.spec_from_file_location('publication_audit',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class AuditTests(unittest.TestCase):
    def reject_raw(self,path,data):
        with self.assertRaises((ValueError,KeyError,AssertionError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix():data})
    def reject(self,path,change):
        value=json.loads(path.read_bytes());change(value);self.reject_raw(path,json.dumps(value).encode())
    def test_real_package(self):self.assertTrue(audit.verify()['passed'])
    def test_outer_native_exit(self):self.reject(audit.PACKAGE/'native-host.json',lambda x:x.update(exit_code=17))
    def test_reopen_exit(self):self.reject(audit.PACKAGE/'reopen-host.json',lambda x:x.update(exit_code=17))
    def test_background_exit(self):self.reject(next(audit.PACKAGE.glob('blender-*/export-*/process-exit.json')),lambda x:x.update(exit_code=17))
    def test_job_leftover(self):self.reject(next(audit.PACKAGE.glob('blender-*/close.json')),lambda x:x['job'].update(active_count=1))
    def test_native_marker(self):self.reject_raw(audit.PACKAGE/'native-stdout.txt',b'GT04_PUBLICATION_COMPLETE {"passed":true,"checks":16}\n')
    def test_response(self):self.reject(audit.PACKAGE/'response.json',lambda x:x.update(public_ack=True))
    def test_custody_witness(self):self.reject(audit.PACKAGE/'custody.json',lambda x:x['events']['binding']['witnessed'].update(sequence=5))
    def test_selector(self):self.reject(next(audit.PACKAGE.glob('hh-files-*/active.json')),lambda x:x.update(generation=2))
    def test_checkpoint_binary(self):
        path=next(audit.PACKAGE.glob('hh-files-*/checkpoint.blend'));self.reject_raw(path,path.read_bytes()+b'x')
    def test_glb_binary(self):
        path=next(audit.PACKAGE.glob('hh-files-*/scene.glb'));self.reject_raw(path,path.read_bytes()+b'x')
    def test_native_reopen_revision(self):self.reject(audit.PACKAGE/'reopened-native.json',lambda x:x.update(revision='sha256:'+'0'*64))
    def test_binary_event_suffix(self):
        path=next(audit.PACKAGE.glob('hh-private-*/.events'));self.reject_raw(path,path.read_bytes()[:-1])
    def test_rehashed_wrong_terminal(self):
        # A checksummed edit still cannot forge the saved custody witness.
        from studio.host.core.private_events import PrivateEventLog
        rows=json.loads((audit.PACKAGE/'events.json').read_bytes());rows[-1]['response']['public_ack']=True
        stream=b'';previous='0'*64
        for index,row in enumerate(rows):
            body,frame=PrivateEventLog._encode(row,index+1,previous);stream+=frame;previous=audit.digest(body)
        self.reject_raw(next(audit.PACKAGE.glob('hh-private-*/.events')),stream)

if __name__=='__main__':unittest.main()
