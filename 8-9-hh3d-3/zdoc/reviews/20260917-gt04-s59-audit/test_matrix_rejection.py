"""Changed matrix facts are rejected without changing raw native evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('matrix_audit',HERE/'verify_matrix.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class MatrixRejectionTests(unittest.TestCase):
    def reject(self,suffix,mutate):
        audit.FILES.clear();audit.CHECKS.clear()
        original=audit.read;touched=[]
        def changed(path):
            value=original(path)
            if path.as_posix().endswith(suffix):
                value=copy.deepcopy(value);mutate(value);touched.append(str(path))
            return value
        with patch.object(audit,'read',side_effect=changed):
            with self.assertRaises(ValueError):audit.verify()
        self.assertTrue(touched)

    def test_effective_source_pin(self):
        self.reject('matrix-02/execution-closure.json',lambda v:v.__setitem__('source_closure_sha256','0'*64))

    def test_actual_parent_exit(self):
        self.reject('ui/native-host.json',lambda v:v.__setitem__('exit_code',False))

    def test_native_runtime_missing_file(self):
        self.reject('ipc/runtime-binding.json',lambda v:v['source_files'].pop('host/blender/client_preview.py'))

    def test_missing_native_check(self):
        self.reject('ipc/native.json',lambda v:v['checks'].pop())

    def test_unwitnessed_tail_forged_committed(self):
        self.reject('before_terminal_witness/recovery.json',lambda v:v.__setitem__('status','COMMITTED'))

    def test_unknown_selector_forged_committed(self):
        self.reject('stop_after_selector/recovery.json',lambda v:v.__setitem__('status','COMMITTED'))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MatrixRejectionTests))
    report={'passed':result.wasSuccessful(),'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'native_handles_opened':0,'formal_acceptance':False}
    (HERE/'matrix-negative-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.wasSuccessful())
