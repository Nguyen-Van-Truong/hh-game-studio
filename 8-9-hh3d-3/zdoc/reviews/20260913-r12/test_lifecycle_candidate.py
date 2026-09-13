import importlib.util, json, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[3] / 'studio' / 'build' / 'bootstrap' / 'install_toolchain.py'
spec = importlib.util.spec_from_file_location('it', HERE)
it = importlib.util.module_from_spec(spec); spec.loader.exec_module(it)

class LifecycleCandidate(unittest.TestCase):
    def mkroot(self):
        td = tempfile.TemporaryDirectory(); root = Path(td.name); self.addCleanup(td.cleanup)
        return root
    def lock(self, root, pid=424242, start='linux:00000000-0000-0000-0000-000000000000:1234', age=600):
        payload={'schema':it.LOCK_SCHEMA,'pid':pid,'process_start':start,'created_ns':time.time_ns()-age*1_000_000_000,'nonce':'a'*32}
        p=root/'.mutation.lock'; p.write_bytes(it.encode(payload)); return p, it.sha(p)
    def test_manual_edit_reconciliation_requires_cas(self):
        root=self.mkroot(); p,tok=self.lock(root)
        p.write_bytes(p.read_bytes().replace(b'424242',b'424243'))
        with self.assertRaises(it.InstallError): it.recover_lock(root, expected_lock=tok, max_age_seconds=0)
        self.assertTrue(p.exists())
    def test_live_owner_refused_even_when_old(self):
        root=self.mkroot(); p,tok=self.lock(root)
        old=it.process_start; it.process_start=lambda pid:'linux:00000000-0000-0000-0000-000000000000:1234'
        self.addCleanup(setattr,it,'process_start',old)
        with self.assertRaises(it.InstallError): it.recover_lock(root, expected_lock=tok, max_age_seconds=0)
        self.assertTrue(p.exists())
    def test_crashed_owner_recovered(self):
        root=self.mkroot(); p,tok=self.lock(root)
        old=it.process_start; it.process_start=lambda pid:None
        self.addCleanup(setattr,it,'process_start',old)
        result=it.recover_lock(root, expected_lock=tok, max_age_seconds=0)
        self.assertEqual(result['status'],'STALE_LOCK_RECOVERED'); self.assertFalse(p.exists())
    def test_replacement_lock_cas_refused(self):
        root=self.mkroot(); p,tok=self.lock(root)
        old=it.require_lock_unchanged
        def replace(path, identity, token):
            path.write_bytes(path.read_bytes().replace(b'424242',b'9'))
            return old(path,identity,token)
        it.require_lock_unchanged=replace; self.addCleanup(setattr,it,'require_lock_unchanged',old)
        oldps=it.process_start; it.process_start=lambda pid:None; self.addCleanup(setattr,it,'process_start',oldps)
        with self.assertRaises(it.InstallError): it.recover_lock(root, expected_lock=tok, max_age_seconds=0)
        self.assertTrue(p.exists())
    def test_too_recent_lock_refused(self):
        root=self.mkroot(); p,tok=self.lock(root, age=0)
        with self.assertRaises(it.InstallError): it.recover_lock(root, expected_lock=tok, max_age_seconds=300)
        self.assertTrue(p.exists())

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleCandidate)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
