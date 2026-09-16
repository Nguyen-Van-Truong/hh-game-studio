"""Component harness ownership failure paths; every native owner is a test double."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.safe_replace import ProtectedFileRoot
spec = importlib.util.spec_from_file_location('components_cleanup_probe',
    STUDIO / 'tests/godot/run_components_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-components-cleanup-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.parent = self.base / 'hh-gt03-components-mocked'
        self.parent.mkdir()
        self.output = self.base / 'output'
        self.output.mkdir()
        self.events = []
        self.codec = object()
        self.validation = SimpleNamespace(factory=SimpleNamespace(bundle_codec=self.codec),
                                          ValidationOwner=Mock())
        self.storage = SimpleNamespace(bundle_codec=self.codec, ProtectedBundleStore=Mock())

    def owner(self, name, *, fails=False):
        def close():
            self.events.append(name + '.close')
            if fails:
                raise RuntimeError(name + ' held')
        return SimpleNamespace(close=Mock(side_effect=close), root=self.parent, root_identity=object())

    def exercise(self, *, native=None, create_error=None, wrap_error=None, validator_error=None):
        def delete(path):
            self.assertEqual(path, self.parent)
            self.events.append('delete')
        with ExitStack() as stack:
            stack.enter_context(patch.object(probe, 'load', side_effect=lambda name, path:
                self.validation if name == 'component_validation' else self.storage))
            stack.enter_context(patch.object(probe.tempfile, 'gettempdir', return_value=str(self.base)))
            stack.enter_context(patch.object(probe.tempfile, 'mkdtemp', return_value=str(self.parent)))
            create = stack.enter_context(patch.object(ProtectedFileRoot, 'create', return_value=native,
                                                       side_effect=create_error))
            deletion = stack.enter_context(patch.object(probe.shutil, 'rmtree', side_effect=delete))
            self.storage.ProtectedBundleStore.side_effect = wrap_error
            if validator_error is not None:
                self.storage.ProtectedBundleStore.return_value = native
                self.validation.ValidationOwner.side_effect = validator_error
            with self.assertRaises(BaseException) as raised:
                probe.frozen_run(self.output)
            create.assert_called_once_with(self.parent)
            return raised.exception, deletion.call_count

    def test_retained_native_constructor_owner_closes_before_delete(self):
        owner = self.owner('native'); error = RuntimeError('constructor failed')
        error.cleanup_owner = owner
        caught, deleted = self.exercise(create_error=error)
        self.assertIs(caught, error); self.assertEqual(deleted, 1)
        self.assertEqual(self.events, ['native.close', 'delete'])
        self.storage.ProtectedBundleStore.assert_not_called()

    def test_retained_constructor_close_failure_prevents_delete(self):
        owner = self.owner('native', fails=True); error = RuntimeError('constructor failed')
        error.cleanup_owner = owner
        caught, deleted = self.exercise(create_error=error)
        self.assertEqual(str(caught), 'native held'); self.assertEqual(deleted, 0)
        self.assertEqual(self.events, ['native.close'])

    def test_wrapper_failure_closes_acquired_native_owner(self):
        native = self.owner('native'); error = RuntimeError('wrapper failed')
        caught, deleted = self.exercise(native=native, wrap_error=error)
        self.assertIs(caught, error); self.assertEqual(deleted, 1)
        self.assertEqual(self.events, ['native.close', 'delete'])

    def test_wrapper_cleanup_owner_alias_is_closed_exactly_once(self):
        native = self.owner('native'); error = RuntimeError('wrapper failed')
        error.cleanup_owner = native
        caught, deleted = self.exercise(native=native, wrap_error=error)
        self.assertIs(caught, error); self.assertEqual(deleted, 1)
        native.close.assert_called_once()

    def test_low_level_cleanup_api_uses_registry_close_not_handle_close(self):
        api = SimpleNamespace(close=Mock(side_effect=AssertionError('close requires a handle')),
            close_owned=Mock(side_effect=lambda: self.events.append('api.close_owned')))
        error = RuntimeError('native allocation failed'); error.cleanup_api = api
        caught, deleted = self.exercise(create_error=error)
        self.assertIs(caught, error); self.assertEqual(deleted, 1)
        api.close.assert_not_called(); api.close_owned.assert_called_once()
        self.assertEqual(self.events, ['api.close_owned', 'delete'])

    def test_low_level_registry_close_failure_prevents_delete(self):
        api = SimpleNamespace(close=Mock(side_effect=AssertionError('wrong close')),
            close_owned=Mock(side_effect=RuntimeError('api held')))
        error = RuntimeError('native allocation failed'); error.cleanup_api = api
        caught, deleted = self.exercise(create_error=error)
        self.assertEqual(str(caught), 'api held'); self.assertEqual(deleted, 0)
        api.close.assert_not_called(); api.close_owned.assert_called_once()

    def test_transferred_store_close_failure_prevents_delete_after_validator_error(self):
        store = self.owner('store', fails=True)
        caught, deleted = self.exercise(native=store, validator_error=RuntimeError('validator failed'))
        self.assertEqual(str(caught), 'store held'); self.assertEqual(deleted, 0)
        store.close.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
