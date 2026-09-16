import importlib.util
import json
from pathlib import Path
import unittest

path=Path(__file__).with_name('verify_evidence.py')
spec=importlib.util.spec_from_file_location('audit',path);audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class AuditTests(unittest.TestCase):
    def reject(self,path,change):
        value=json.loads(path.read_bytes());change(value)
        with self.assertRaises((ValueError,AssertionError,KeyError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix():json.dumps(value).encode()})
    def test_real_package(self):self.assertTrue(audit.verify()['passed'])
    def test_actual_exit(self):self.reject(audit.PACKAGE/'native-host.json',lambda x:x.update(exit_code=5))
    def test_fake_cleanup_success(self):
        failed=json.loads((audit.PACKAGE/'cleanup/native.json').read_bytes())['failed_directory']
        self.reject(audit.PACKAGE/'cleanup'/failed/'host-result.json',lambda x:x.update(completed=True))
    def test_death_observation(self):self.reject(audit.PACKAGE/'host-death/observed.json',lambda x:x.update(dead_wait_after=258))
    def test_receipt_bytes(self):
        path=audit.PACKAGE/'committed-response.json'
        with self.assertRaises(ValueError):audit.verify({path.relative_to(audit.ROOT).as_posix():b'{}'})

if __name__=='__main__':unittest.main()
