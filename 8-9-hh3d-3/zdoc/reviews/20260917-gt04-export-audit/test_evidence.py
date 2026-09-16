"""Corrupt only decoded copies; never edit the frozen evidence or start engines."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

path=Path(__file__).with_name('verify_evidence.py')
spec=importlib.util.spec_from_file_location('gt04_export_evidence',path)
V=importlib.util.module_from_spec(spec);exec(compile(path.read_bytes(),str(path),'exec'),V.__dict__)


class EvidenceNegatives(unittest.TestCase):
    def reject(self,select,mutate,reason):
        original=V.read;seen=[]
        def read(path):
            value=original(path)
            if select(Path(path),value):
                seen.append(str(path));value=copy.deepcopy(value);mutate(value)
            return value
        with patch.object(V,'read',read),patch.object(V.H,'read',read),self.assertRaisesRegex(ValueError,reason):
            V.main()
        self.assertTrue(seen)

    def test_foreign_runtime_hash_rejected(self):
        self.reject(lambda p,v:p.name=='launch.json',
            lambda v:v['source_files'].update({'host/blender/export_job.py':'0'*64}),'GUI launched source')

    def test_valid_output_with_forged_pose_receipt_rejected(self):
        self.reject(lambda p,v:p.name=='host-result.json' and v['completed'] is True,
            lambda v:v['preflight']['meshes'][0].update(translation=[0,0,0]),'actual GLB postcondition')

    def test_boolean_actual_host_exit_rejected(self):
        self.reject(lambda p,v:p.name=='unit-host.json',lambda v:v.update(exit_code=False),'host exits')

    def test_stop_without_observed_native_exit_rejected(self):
        self.reject(lambda p,v:p.name=='stop.json',lambda v:v.update(dead_wait_after=258),'forced native exit observer')


if __name__=='__main__':unittest.main(verbosity=2)
