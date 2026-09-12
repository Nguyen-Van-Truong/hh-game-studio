"""S13 regression checks for the static validator; no external worker calls."""
import hashlib, json, sys, unittest
from pathlib import Path
import validate_plans as validator

def manifest_for(inputs, revision="S13"):
    rows=[{"path": n, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
          for n,b in inputs.items()]
    agg=hashlib.sha256("\n".join(sorted(f"{r['path']} {r['sha256']}" for r in rows)).encode()).hexdigest()
    return {"revision": revision, "files": rows, "manifest_sha256": agg}

class S13Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs={n:(validator.Z/n).read_bytes() for n in validator.NAMES}
    def result(self, name=None, old=None, new=None):
        inputs=self.inputs.copy()
        if name is not None:
            text=inputs[name].decode("utf-8")
            self.assertIn(old, text)
            inputs[name]=text.replace(old,new,1).encode()
        return validator.validate(manifest_for(inputs),inputs,validator.Z)
    def test_baseline_static_pass(self):
        self.assertEqual(self.result()["errors"], [])
    def test_only_two_active_plans(self):
        result=self.result()
        self.assertEqual(result["plans"][0]["wp_rows"],10)
        self.assertEqual(result["plans"][1]["wp_rows"],32)
    def test_plan_only_and_no_tick(self):
        for name in validator.NAMES:
            text=self.inputs[name].decode()
            self.assertIn("EXECUTION_AUTHORIZATION=PLAN_ONLY", text)
            self.assertNotIn("[x]", text.lower())
    def test_release_profile_closed_schema(self):
        result=self.result(validator.NAMES[1],"BLOCKED_RELEASE_PROFILE_SCHEMA","BROKEN_PROFILE")
        self.assertTrue(any("S13 release profile" in e for e in result["errors"]))
    def test_load_profile_contract_required(self):
        result=self.result(validator.NAMES[1],"contracts/load-profile-v1.json","contracts/old-load.json")
        self.assertTrue(any("S13 load profile" in e for e in result["errors"]))
    def test_deployment_profile_contract_required(self):
        result=self.result(validator.NAMES[1],"BLOCKED_DEPLOYMENT_PROFILE","OLD_DEPLOYMENT_STATUS")
        self.assertTrue(any("S13 deployment profile" in e for e in result["errors"]))
    def test_linked_closure_and_safe_open_required(self):
        result=self.result(validator.NAMES[0],"UNSUPPORTED_SAFE_OPEN_WINDOWS","SAFE_OPEN")
        self.assertTrue(any("linked inputs" in e for e in result["errors"]))
    def test_codex_policy_required(self):
        result=self.result(validator.NAMES[0],"gpt-6-astra","gpt-5.6-luna")
        self.assertTrue(any("Codex Astra" in e for e in result["errors"]))
    def test_dependency_regression_rejected(self):
        result=self.result(validator.NAMES[1],"H2-P3-04","H2-P2-04",)
        self.assertTrue(any("economy and load" in e for e in result["errors"]))
    def test_sizing_is_illustration(self):
        result=self.result()
        self.assertEqual(result["sizing_illustration"]["rooms_cpu"],13)
        self.assertEqual(result["sizing_illustration"]["peak_TB"],77.76)

if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={"result":"PASS" if result.wasSuccessful() else "FAIL",
            "tests_run":result.testsRun,
            "limits":"Static plan and mutation checks only; no runtime/legal/human/scale acceptance."}
    (validator.OUT/"selfcheck-s13.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
