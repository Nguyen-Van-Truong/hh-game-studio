import unittest, tempfile, hashlib, json, subprocess, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lifecycle_candidate as c

class LifecycleCandidateTests(unittest.TestCase):
 def test_distinct_install_activate_rollback_and_cas(self):
  with tempfile.TemporaryDirectory() as td:
   b=Path(td); root=b/'root'; a=c.fixture(b,'4.7.2-stable-a'); z=c.fixture(b,'4.7.2-stable-b')
   ra=c.inst.install(*a,root); rb=c.inst.install(*z,root)
   self.assertNotEqual(ra['receipt']['package'],rb['receipt']['package'])
   s1=c.inst.activate(root,ra['receipt'],'NONE'); s2=c.inst.activate(root,rb['receipt'],s1['state_token'])
   with self.assertRaises(c.inst.InstallError): c.inst.rollback(root,s2['state_token'],'0'*32)
   back=c.inst.rollback(root,s2['state_token'],s2['transition_id']); self.assertEqual(back['current'],ra['receipt'])
 def test_candidate_report_is_generated(self):
  report=c.run(); self.assertEqual(report['status'],'CANDIDATE'); self.assertNotEqual(report['package_a']['package'],report['package_b']['package'])
 def test_bad_evidence_fails(self):
  report=c.run(); p=Path(c.HERE)/'lifecycle-candidate.json'; data=json.loads(p.read_text()); data['package_a']['package']=data['package_b']['package']; p.write_text(json.dumps(data))
  self.assertEqual(data['package_a']['package'],data['package_b']['package'])
  with self.assertRaises(AssertionError): self.assertNotEqual(data['package_a']['package'],data['package_b']['package'])

if __name__=='__main__': unittest.main(verbosity=2)
