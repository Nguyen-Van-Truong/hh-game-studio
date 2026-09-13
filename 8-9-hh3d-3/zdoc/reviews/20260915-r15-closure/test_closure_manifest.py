import json
import shutil
import tempfile
import unittest
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("closure_manifest", HERE / "closure_manifest.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

RUNNER_PATH = module.PRODUCT / "studio/build/bootstrap/run_fixture.py"
runner_spec = importlib.util.spec_from_file_location("actual_run_fixture", RUNNER_PATH)
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)


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

    def test_inventory_matches_actual_runner_and_discovers_new_helper(self):
        actual = {"studio/" + path for path in runner.checked_files(module.PRODUCT / "studio")}
        self.assertEqual(set(module.discover(module.PRODUCT)), actual)
        runner_hashes = runner.checked_files(module.PRODUCT / "studio")
        with tempfile.TemporaryDirectory() as generated:
            rows = module.generate(Path(generated))["required_files"]
        closure_hashes = {row["path"][len("8-9-hh3d-3/"):]: row["sha256"] for row in rows}
        self.assertEqual(module.closure_hash(closure_hashes),
                         runner.source_closure_sha256(runner_hashes))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            shutil.copytree(module.PRODUCT / "studio", root / "studio",
                            ignore=shutil.ignore_patterns(".local", ".godot", "evidence", "__pycache__"))
            helper = root / "studio/build/bootstrap/lifecycle_probe.py"
            helper.write_text("print('probe')\n", encoding="utf-8")
            payload = module.generate(Path(tmp) / "out", root)
            paths = {row["path"] for row in payload["required_files"]}
            self.assertIn("8-9-hh3d-3/studio/build/bootstrap/lifecycle_probe.py", paths)
            self.assertEqual(payload["status"], "CANDIDATE")

    def test_path_traversal_and_extra_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            module.generate(out)
            manifest = out / "source-closure-manifest.json"
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["required_files"][0]["path"] = "8-9-hh3d-3/studio/../outside.py"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            result = module.verify(manifest, module.PRODUCT)
            self.assertEqual(result["status"], "GAP")
            self.assertIn("traversal", result["failures"][0])

    def test_hardlink_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            shutil.copytree(module.PRODUCT / "studio", root / "studio",
                            ignore=shutil.ignore_patterns(".local", ".godot", "evidence", "__pycache__"))
            source = root / "studio/toolchain.lock.json"
            alias = root / "studio/build/bootstrap/hardlink.tmp"
            try:
                alias.hardlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("hard links unavailable")
            payload = module.generate(Path(tmp) / "out", root)
            self.assertEqual(payload["status"], "GAP")
            self.assertTrue(any(g["code"] == "UNSAFE_FILE_IDENTITY" for g in payload["gaps"]))

    def test_symlink_directory_is_rejected_without_following(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            shutil.copytree(module.PRODUCT / "studio", root / "studio",
                            ignore=shutil.ignore_patterns(".local", ".godot", "evidence", "__pycache__"))
            link = root / "studio/build/bootstrap/linked"
            try:
                link.symlink_to(root / "studio/fixtures", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            payload = module.generate(Path(tmp) / "out", root)
            self.assertEqual(payload["status"], "GAP")
            self.assertTrue(any(g["code"] == "UNSAFE_INVENTORY" for g in payload["gaps"]))


if __name__ == "__main__":
    unittest.main()
