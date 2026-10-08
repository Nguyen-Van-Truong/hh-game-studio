"""Pure checks for the delegated runner admission boundary."""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
import json

try:
    from . import run_delegated_playtest as runner
except ImportError:
    import run_delegated_playtest as runner


class DelegatedRunnerTests(unittest.TestCase):
    def test_config_overlay_replaces_duplicate_sections_once(self) -> None:
        raw = "[application]\nconfig/name=old\n\n[display]\na=1\n\n[application]\nconfig/name=stale\n"
        result = runner._upsert_project_sections(raw, {
            "application": {"config/name": '"new"'},
            "display": {"a": "2"},
        })
        self.assertEqual(result.count("[application]"), 1)
        self.assertEqual(result.count("[display]"), 1)
        self.assertIn('config/name="new"', result)

    def test_pinned_binary_rejects_old_pin_and_external_copy(self) -> None:
        with self.assertRaises(ValueError):
            runner.pinned_godot(Path("C:/tmp/Godot_v4.7.1-stable_win64_console.exe"))

    def test_source_closure_changes_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "scripts").mkdir()
            (project / "scripts" / "fixture.gd").write_text("extends Node\n", encoding="utf-8")
            before = runner._source_files(project)
            (project / "scripts" / "fixture.gd").write_text("extends Node\n# drift\n", encoding="utf-8")
            after = runner._source_files(project)
            self.assertNotEqual(before, after)

    def test_runner_has_no_post_freeze_capture_injection(self) -> None:
        source = Path(runner.__file__).read_text(encoding="utf-8")
        self.assertNotIn("_capture_enabled_lifecycle", source)
        self.assertIn("--fixture-lifecycle-", source)
        self.assertIn("DRY_RUN_REQUIRED", source)
        self.assertIn("source_closure_sha256", source)

    def test_dry_run_binds_mode_deadline_and_both_argvs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "Godot_v4.7.2-stable_win64_console.exe"
            binary.write_bytes(b"pinned")
            project = root / "project"
            metadata = {"run_id": "gt09-playtest-20261008-01", "fixture": "arena",
                        "source_closure_sha256": "a" * 64, "project": str(project)}
            argv = runner._fixture_argv(binary, project, "smoke")
            import_argv = runner._import_argv(binary, project)
            (root / "dry-run.json").write_text(json.dumps({
                "schema": runner.DRY_RUN_SCHEMA, "run_id": metadata["run_id"],
                "fixture": metadata["fixture"], "dry_run": True,
                "native_run_performed": False, "source_closure_sha256": metadata["source_closure_sha256"],
                "godot": str(binary), "godot_sha256": runner.sha(binary),
                "mode": "smoke", "deadline_seconds": 30.0,
                "argv": argv, "import_argv": import_argv,
            }), encoding="utf-8")
            runner._require_dry_run(metadata, binary, root, mode="smoke", deadline=30.0,
                                    argv=argv, import_argv=import_argv)
            receipt = json.loads((root / "dry-run.json").read_text(encoding="utf-8"))
            receipt["mode"] = "scripted"
            (root / "dry-run.json").write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                runner._require_dry_run(metadata, binary, root, mode="smoke", deadline=30.0,
                                        argv=argv, import_argv=import_argv)
            (root / "dry-run.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "DRY_RUN_INVALID"):
                runner._require_dry_run(metadata, binary, root, mode="smoke", deadline=30.0,
                                        argv=argv, import_argv=import_argv)

    def test_engine_log_failure_and_import_cache_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stdout.txt").write_text("normal\n", encoding="utf-8")
            self.assertIsNone(runner._engine_log_failure(root))
            (root / "stderr.txt").write_text("ERROR: No loader found for resource\n", encoding="utf-8")
            self.assertEqual(runner._engine_log_failure(root), "ERROR: No loader found for resource")
            project = root / "project"
            with self.assertRaisesRegex(RuntimeError, "GODOT_IMPORT_CACHE_MISSING"):
                runner._import_cache(project)
            imported = project / ".godot" / "imported"
            imported.mkdir(parents=True)
            (imported / "avatar.glb-1.import").write_bytes(b"cache")
            (imported / "sprite_sheet.png-1.import").write_bytes(b"cache")
            cache = runner._import_cache(project)
            self.assertEqual(cache["files"], {
                "avatar.glb-1.import": runner.sha(imported / "avatar.glb-1.import"),
                "sprite_sheet.png-1.import": runner.sha(imported / "sprite_sheet.png-1.import"),
            })

    def test_deadline_zero_is_rejected_and_mode_defaults_are_stable(self) -> None:
        self.assertEqual(runner._resolve_deadline(None, "scripted"), 960.0)
        self.assertEqual(runner._resolve_deadline(None, "smoke"), 30.0)
        with self.assertRaisesRegex(ValueError, "DEADLINE_OUT_OF_RANGE"):
            runner._resolve_deadline(0.0, "smoke")


if __name__ == "__main__":
    unittest.main()
