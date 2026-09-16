import importlib.util
import json
from pathlib import Path
import unittest
path=Path(__file__).with_name('verify_evidence.py')
spec=importlib.util.spec_from_file_location('material_audit',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
class AuditTests(unittest.TestCase):
    def reject(self,path,change):
        value=json.loads(path.read_bytes());change(value)
        with self.assertRaises((ValueError,KeyError)):
            audit.verify({path.relative_to(audit.ROOT).as_posix():json.dumps(value).encode()})
    def test_real_package(self):self.assertTrue(audit.verify()['passed'])
    def test_reopen_exit(self):self.reject(audit.PACKAGE/'reopen-host.json',lambda x:x.update(exit_code=17))
    def test_reopen_material_tamper(self):
        self.reject(audit.PACKAGE/'checkpoint-reopened.json',lambda x:x['snapshot']['objects'][0]['material'].update(metallic=1))
    def test_fake_rejection(self):
        self.reject(audit.PACKAGE/'admission.json',lambda x:x['native']['admission_probe'][0].update(passed=False))
    def test_glb_byte_tamper(self):
        path=next(audit.PACKAGE.glob('blender-*/export-*/output.glb'));data=path.read_bytes()
        with self.assertRaises(ValueError):audit.verify({path.relative_to(audit.ROOT).as_posix():data[:-1]})
if __name__=='__main__':unittest.main()
