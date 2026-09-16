"""Loaded-release regressions using disposable copies only; no engine or Docker."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-validation-binding-')
        self.addCleanup(self.temp.cleanup)
        self.studio = Path(self.temp.name).resolve() / 'studio'
        self.studio.mkdir()
        for relative in ('godot-addon', 'host/core', 'protocol'):
            shutil.copytree(STUDIO / relative, self.studio / relative,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for relative in ('toolchain.lock.json', 'build/bootstrap/run_fixture.py'):
            target = self.studio / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((STUDIO / relative).read_bytes())
        self.evidence = Path(self.temp.name).resolve() / 'evidence'
        self.evidence.mkdir()

    def load_owner(self):
        name = 'isolated_validation_binding_' + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, self.studio / 'godot-addon/validation_owner.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        return module

    def test_unchanged_isolated_release_can_construct_without_execution(self):
        module = self.load_owner()
        with patch.object(module.executor, 'run') as run:
            issuer = module.ValidationOwner(self.evidence)
            self.assertEqual((issuer._source_files, issuer._source_sha), module._IMPORT_RELEASE)
            issuer.close()
            run.assert_not_called()

    def test_disk_dependency_drift_after_import_rejects_before_constructor_adoption(self):
        module = self.load_owner()
        for relative in ('bundle_v2.py', 'bundle_staging.py', 'cli_job.py'):
            target = self.studio / 'godot-addon' / relative
            original = target.read_bytes()
            try:
                target.write_bytes(original + b'\n# isolated post-import drift\n')
                with self.subTest(relative=relative), patch.object(module.executor, 'run') as run:
                    with self.assertRaisesRegex(module.ValidationOwnerError, 'IMPORT_RELEASE_CHANGED'):
                        module.ValidationOwner(self.evidence)
                    run.assert_not_called()
            finally:
                target.write_bytes(original)

    def test_disk_drift_after_construction_rejects_before_attempt_or_receipt(self):
        module = self.load_owner()
        issuer = module.ValidationOwner(self.evidence)
        self.addCleanup(issuer.close)
        factory = module.factory
        bundle = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
            scene_revision='sha256:' + '1' * 64, engine_sha256=module.executor.BINARY_SHA256)
        path = self.studio / 'godot-addon/bundle_v2.py'
        path.write_bytes(path.read_bytes() + b'\n# isolated later drift\n')
        with patch.object(module.executor, 'run') as run:
            with self.assertRaisesRegex(module.ValidationOwnerError, 'RELEASE_CHANGED'):
                issuer.validate('binding.drift', bundle)
            run.assert_not_called()
        self.assertEqual(issuer.snapshot()['attempts'], ())
        self.assertEqual(issuer.snapshot()['registered_commands'], ())

    def test_stale_retained_dependency_metadata_rejects_matching_disk_release(self):
        module = self.load_owner()
        scene = module.factory._sibling('scene_profile')
        cli = module.executor._cli_jobs()
        bindings = ((module.bundle_codec, '_bundle_source_sha256', '0' * 64),
                    (module.factory.staging, '_fixture_source_sha256', '0' * 64),
                    (scene, 'SCRIPT_PROFILE_SHA256', '0' * 64),
                    (cli, '__name__', 'stale_loaded_cli_job'),
                    (cli, '__file__', 'C:/unrelated/cli_job.py'))
        for dependency, attribute, replacement in bindings:
            with self.subTest(attribute=attribute), patch.object(dependency, attribute, replacement), \
                 patch.object(module.executor, 'run') as run:
                with self.assertRaisesRegex(module.ValidationOwnerError, 'LOADED_DEPENDENCY_CHANGED'):
                    module.ValidationOwner(self.evidence)
                run.assert_not_called()

    def test_release_change_during_addon_import_is_not_adopted(self):
        target = self.studio / 'godot-addon/profile_readback.py'
        changed = self.studio / 'godot-addon/bundle_v2.py'
        read_bytes = Path.read_bytes
        count = 0
        def read(path):
            nonlocal count
            raw = read_bytes(path)
            if path == target:
                count += 1
                if count == 2:  # Initial manifest captured; addon loading now begins.
                    changed.write_bytes(read_bytes(changed) + b'\n# isolated import drift\n')
            return raw
        with patch.object(Path, 'read_bytes', read):
            with self.assertRaisesRegex(ValueError, 'IMPORT_RELEASE_CHANGED'):
                self.load_owner()
        self.assertGreaterEqual(count, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
