"""Pure checks for the delegated runner admission boundary."""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
import json
import shutil

try:
    from . import run_delegated_playtest as runner
except ImportError:
    import run_delegated_playtest as runner


class DelegatedRunnerTests(unittest.TestCase):
    _ARENA_PUBLICATION = (runner.RAW_ROOT / "o2-publication-gt09-arena-20261009-15")
    _ROOM_PUBLICATION = (runner.RAW_ROOT / "o2-publication-gt09-room-20261009-10")

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

    def test_publication_uses_native_snapshot_and_records_selected_revision(self) -> None:
        snapshot, provenance = runner._publication_project(self._ARENA_PUBLICATION, "arena")
        self.assertEqual(runner.sha(snapshot / "scripts" / "fixture_actor.gd"),
                         "c36103c938a6bee442c09619b2684657225871f2087a041ddff6029022c73f04")
        self.assertEqual(provenance["selected_revision"],
                         "sha256:f51768fe655e1f7e9fe21b92dc0d59b51d47825aa02b252c27378d24c05e62e2")
        self.assertTrue(provenance["selected_matches_executed_snapshot"])

    def test_publication_rejects_room_without_requested_lifecycle(self) -> None:
        with self.assertRaisesRegex(ValueError, "PUBLICATION_LIFECYCLE_MISSING"):
            runner._publication_project(self._ROOM_PUBLICATION, "room")

    def test_publication_rejects_altered_snapshot_asset_and_script(self) -> None:
        with tempfile.TemporaryDirectory(dir=runner.RAW_ROOT) as directory:
            root = Path(directory) / "publication"
            shutil.copytree(self._ARENA_PUBLICATION, root)
            asset = root / "gameplay-owner-40ac41080d454b71bb9407a8e137da10" / "runs" / "command.publication.1" / "snapshot" / "assets" / "avatar.glb"
            self.assertTrue(asset.is_file())
            asset.write_bytes(asset.read_bytes() + b"drift")
            with self.assertRaisesRegex(ValueError, "NATIVE_SNAPSHOT_HASH_MISMATCH"):
                runner._publication_project(root, "arena")
            shutil.copytree(self._ARENA_PUBLICATION, root, dirs_exist_ok=True)
            script = root / "gameplay-owner-40ac41080d454b71bb9407a8e137da10" / "runs" / "command.publication.1" / "snapshot" / "scripts" / "fixture_actor.gd"
            script.write_bytes(script.read_bytes() + b"drift")
            with self.assertRaisesRegex(ValueError, "NATIVE_SNAPSHOT_HASH_MISMATCH"):
                runner._publication_project(root, "arena")

    def test_publication_rejects_altered_observation_provenance(self) -> None:
        with tempfile.TemporaryDirectory(dir=runner.RAW_ROOT) as directory:
            root = Path(directory) / "publication"
            shutil.copytree(self._ARENA_PUBLICATION, root)
            observation_path = root / "native-observation.json"
            observation = json.loads(observation_path.read_text(encoding="utf-8"))
            observation["fixture_script_sha256"] = "f" * 64
            observation_path.write_text(json.dumps(observation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "NATIVE_FIXTURE_SCRIPT_BINDING"):
                runner._publication_project(root, "arena")

    def test_selected_revision_drift_is_reported_without_rebinding_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(dir=runner.RAW_ROOT) as directory:
            root = Path(directory) / "publication"
            shutil.copytree(self._ARENA_PUBLICATION, root)
            result_path = root / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["selected"]["files"]["scripts/fixture_actor.gd"] = "f" * 64
            result_path.write_text(json.dumps(result), encoding="utf-8")
            snapshot, provenance = runner._publication_project(root, "arena")
            self.assertEqual(runner.sha(snapshot / "scripts" / "fixture_actor.gd"),
                             "c36103c938a6bee442c09619b2684657225871f2087a041ddff6029022c73f04")
            self.assertFalse(provenance["selected_matches_executed_snapshot"])

    def test_publication_rejects_path_outside_review_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "PUBLICATION_ROOT_OUTSIDE_REVIEWS"):
                runner._publication_project(Path(directory), "arena")

    def test_prepare_publication_does_not_overwrite_native_bytes(self) -> None:
        run_id = "gt09-playtest-20990101-01"
        root = runner.RAW_ROOT / run_id
        try:
            metadata = runner.prepare(run_id, "arena", publication_root=self._ARENA_PUBLICATION)
            project = Path(metadata["project"])
            self.assertEqual(metadata["source_mode"], "native-publication-snapshot")
            self.assertFalse(metadata["legacy_unaccepted"])
            self.assertEqual(runner.sha(project / "scripts" / "fixture_actor.gd"),
                             "c36103c938a6bee442c09619b2684657225871f2087a041ddff6029022c73f04")
            self.assertEqual((project / "scripts" / "fixture_lifecycle.gd").read_bytes(),
                             (self._ARENA_PUBLICATION / "gameplay-owner-40ac41080d454b71bb9407a8e137da10" /
                              "runs" / "command.publication.1" / "snapshot" / "scripts" / "fixture_lifecycle.gd").read_bytes())
            tampered = json.loads(json.dumps(metadata))
            tampered["publication_provenance"]["executed_snapshot_files"]["assets/avatar.glb"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "PUBLICATION_PROVENANCE_CHANGED"):
                runner._load_metadata(tampered)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
