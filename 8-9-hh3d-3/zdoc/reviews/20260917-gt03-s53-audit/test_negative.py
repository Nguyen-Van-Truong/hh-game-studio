"""Corrupt detached evidence views; never change the captured files."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('s53_negative_audit',HERE/'verify_publication.py')
audit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=audit;spec.loader.exec_module(audit)
PACKAGE=HERE.parent/'20260917-gt03-s53-script-publication-02'


class ChangedView(audit.base.Evidence):
    def __init__(self,name,change):super().__init__();self.name,self.change=name,change
    def read(self,path):
        value=super().read(path)
        if Path(path).name==self.name:
            value=copy.deepcopy(value);self.change(value)
        return value


class NegativeTests(unittest.TestCase):
    def reject(self,name,change):
        with self.assertRaises(ValueError):audit.verify(PACKAGE,ChangedView(name,change))

    def test_unproven_host_exit(self):
        self.reject('capture.json',lambda v:v['host'].update(exit_code=17))

    def test_false_native_check(self):
        self.reject('publication.json',lambda v:v['checks'][0].update(passed=False))

    def test_response_not_original(self):
        self.reject('response.json',lambda v:v.update(code='DIFFERENT_RESULT'))

    def test_replay_changed_after_restart(self):
        self.reject('reopened.json',lambda v:v['commands'][0].update(digest='sha256:'+'1'*64))

    def test_new_script_defaults_not_actual(self):
        self.reject('script-readback.json',lambda v:v['script']['defaults']['fixture_value'].update(value=901))

    def test_runtime_difference_between_lanes(self):
        with self.assertRaises(ValueError):
            audit.base.same_runtime([{'godot-addon/plugin.gd':'1'*64},{'godot-addon/plugin.gd':'2'*64}])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NegativeTests))
    (HERE/'negative-results.json').write_text(json.dumps({'passed':result.wasSuccessful(),'run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),
        'audit_sha256':audit.base.sha(HERE/'verify_publication.py'),'test_sha256':audit.base.sha(Path(__file__)),
        'read_only_evidence':True,'native_processes_launched':False,'formal_acceptance':False},indent=2)+'\n',encoding='utf-8')
    sys.exit(not result.wasSuccessful())
