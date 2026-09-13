import json
import tempfile
import unittest
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("closure_manifest", HERE / "closure_manifest.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ClosureManifestTests(unittest.TestCase):
    def test_generate_contains_runtime_tests_and_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = module.generate(Path(tmp))
            self.assertEqual(payload["status"], "CANDIDATE")
            roles = {row["role"] for row in payload["required_files"]}
            self.assertEqual(roles, {"runtime", "fixture", "documentation", "test"})
            self.assertGreaterEqual(len(payload["required_files"]), 15)
            self.assertEqual(len(payload["gaps"]), 0)

    def test_verify_detects_source_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            payload = module.generate(out)
            manifest = out / "source-closure-manifest.json"
            good = module.verify(manifest, module.PRODUCT)
            self.assertEqual(good["status"], "READY")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["required_files"][0]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(data), encoding="utf-8")
            bad = module.verify(manifest, module.PRODUCT)
            self.assertEqual(bad["status"], "GAP")

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"schema":1,"schema":2}', encoding="utf-8")
            with self.assertRaises(module.ClosureError):
                module.load(path)

    def test_incomplete_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            module.generate(out)
            manifest = out / "source-closure-manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["required_files"].pop()
            manifest.write_text(json.dumps(data), encoding="utf-8")
            result = module.verify(manifest, module.PRODUCT)
            self.assertEqual(result["status"], "GAP")
            self.assertIn("inventory mismatch", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
