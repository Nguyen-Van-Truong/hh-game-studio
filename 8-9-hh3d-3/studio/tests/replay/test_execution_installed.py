"""Synthetic fixed-selector tests; no runtime tree, engine, process or network I/O."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import execution_binding as binding
from studio.host.replay import execution_installed as installed


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


class InstalledBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-gt06-installed-binding-')
        self.addCleanup(self.temporary.cleanup)
        self.studio = Path(self.temporary.name) / 'studio'
        self.studio.mkdir()
        self.source = {
            'toolchain.lock.json': b'tool pin\n',
            'build/bootstrap/run_fixture.py': b'owned launcher\n',
            'godot-addon/cli_job.py': b'current Job source\n',
            'godot-addon/plugin.cfg': b'plugin configuration\n',
            'godot-addon/fixture_profile/source-pins.json': b'source pins\n',
            'godot-addon/observe/observer.gd': b'observe script\n',
            'godot-addon/observe/resource.tres': b'observe resource\n',
            'godot-addon/observe/scene.tscn': b'observe scene\n',
            'host/core/transport.py': b'current transport\n',
            'protocol/core.py': b'protocol\n',
            'host/replay/native_runner.py': b'native runner\n',
            'host/replay/execution_binding.py': b'installed reader\n',
            'host/replay/execution_installed.py': b'installed selector loader\n',
            'host/replay/profile.json': b'fixed replay profile\n',
            'contracts/perf-collector.schema.json': b'perf schema\n',
            'fixtures/play-observe/fixture.gd': b'fixture script\n',
            'fixtures/play-observe/fixture.gd.uid': b'fixture uid\n',
            'fixtures/play-observe/project.godot': b'fixture project\n',
            'fixtures/play-observe/fixture.tscn': b'fixture scene\n',
            'fixtures/play-observe/material.tres': b'fixture resource\n',
        }
        for name, raw in self.source.items():
            self.write(name, raw)
        self.source_map = {name: sha(raw) for name, raw in self.source.items()}
        self.accepted = {binding.GT05_SOURCE_PREFIX + 'godot-addon/cli_job.py': 'a' * 64}
        self.document = {'schema': binding.SCHEMA,
                         'accepted_gt05_manifest_sha256': binding.GT05_MANIFEST_SHA256,
                         'source_files': dict(self.source_map)}
        self.freeze()

    def write(self, name, raw):
        path = self.studio / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def freeze(self, *, selector=None, binding_raw=None):
        self.binding_raw = encoded(self.document) if binding_raw is None else binding_raw
        self.selector = {'schema': installed.SELECTOR_SCHEMA, 'binding_sha256': sha(self.binding_raw)} \
            if selector is None else selector
        self.selector_raw = encoded(self.selector)
        self.write(installed.BINDING_PATH, self.binding_raw)
        self.write(installed.SELECTOR_PATH, self.selector_raw)

    def read(self):
        return installed.load_installed(self.studio, self.accepted)

    def rejected(self, code):
        with self.assertRaises(binding.BindingRejected) as caught:
            self.read()
        self.assertEqual(caught.exception.code, code)

    def test_verified_map_includes_independent_metadata_hashes_without_cycle(self):
        self.assertEqual(installed._required_sources(self.studio), frozenset(self.source_map))
        result = self.read()
        expected = {**self.source_map, installed.SELECTOR_PATH: sha(self.selector_raw),
                    installed.BINDING_PATH: sha(self.binding_raw)}
        self.assertEqual(result, expected)
        self.assertEqual(list(result), sorted(result))
        self.assertTrue(installed.METADATA_PATHS.isdisjoint(self.document['source_files']))

    def test_selection_identity_matches_metadata_and_changes_with_new_generation(self):
        before = installed.selection_identity(self.studio)
        self.assertEqual(before, {name: self.read()[name] for name in installed.METADATA_PATHS})
        self.write('host/replay/profile.json', b'new generation profile\n')
        self.document['source_files']['host/replay/profile.json'] = sha(b'new generation profile\n')
        self.freeze()
        after = installed.selection_identity(self.studio)
        self.assertNotEqual(before, after)
        self.assertEqual(after, {name: self.read()[name] for name in installed.METADATA_PATHS})

    def test_selection_identity_retains_strict_binding_checks(self):
        self.freeze(selector={'schema': installed.SELECTOR_SCHEMA, 'binding_sha256': '0' * 64})
        with self.assertRaises(binding.BindingRejected) as caught:
            installed.selection_identity(self.studio)
        self.assertEqual(caught.exception.code, 'BINDING_MANIFEST_HASH')

    def test_selector_schema_exact_and_no_path_or_request_override(self):
        variants = [{'schema': 'other', 'binding_sha256': sha(self.binding_raw)},
                    {'schema': installed.SELECTOR_SCHEMA},
                    {**self.selector, 'path': 'elsewhere.json'},
                    {**self.selector, 'source_files': self.source_map}]
        for selector in variants:
            with self.subTest(selector=selector):
                self.freeze(selector=selector)
                self.rejected('SELECTION_SCHEMA')

    def test_selector_digest_and_bound_bytes_are_strict(self):
        self.freeze(selector={'schema': installed.SELECTOR_SCHEMA, 'binding_sha256': 'A' * 64})
        self.rejected('BINDING_DIGEST')
        self.freeze(selector={'schema': installed.SELECTOR_SCHEMA, 'binding_sha256': '0' * 64})
        self.rejected('BINDING_MANIFEST_HASH')

    def test_duplicate_selector_json_key_rejected(self):
        raw = b'{"binding_sha256":"' + b'0' * 64 + b'",' + self.selector_raw[1:]
        self.write(installed.SELECTOR_PATH, raw)
        self.rejected('BINDING_JSON_DUPLICATE_KEY')

    def test_missing_selector_or_binding_fails_closed(self):
        for name in installed.METADATA_PATHS:
            with self.subTest(name=name):
                self.freeze()
                (self.studio / name).unlink()
                self.rejected('BINDING_FILE_MISSING_OR_UNREADABLE')

    def test_metadata_paths_and_case_variants_cannot_enter_source_map(self):
        for name in (*installed.METADATA_PATHS, installed.SELECTOR_PATH.upper()):
            with self.subTest(name=name):
                self.document['source_files'] = {**self.source_map, name: '0' * 64}
                self.freeze()
                self.rejected('SELECTION_METADATA_IN_SOURCE')

    def test_current_inventory_cannot_be_omitted_from_candidate(self):
        for name in ('host/core/transport.py', 'host/replay/execution_binding.py',
                     'godot-addon/fixture_profile/source-pins.json',
                     'godot-addon/observe/resource.tres', 'fixtures/play-observe/fixture.tscn',
                     'build/bootstrap/run_fixture.py', 'toolchain.lock.json', 'host/replay/profile.json'):
            with self.subTest(name=name):
                self.document['source_files'] = {key: value for key, value in self.source_map.items()
                                                  if key != name}
                self.freeze()
                self.rejected('BINDING_MISSING_DEPENDENCY')

    def test_new_python_or_recursive_data_dependency_requires_new_binding(self):
        for name in ('host/replay/new_reader.py', 'host/core/nested/new_transport.py',
                     'godot-addon/new-pins.json', 'protocol/new.py',
                     'fixtures/play-observe/nested/new.tres'):
            with self.subTest(name=name):
                self.write(name, b'new dependency\n')
                self.rejected('BINDING_MISSING_DEPENDENCY')
                (self.studio / name).unlink()

    def test_pycache_and_unselected_extensions_are_not_dependencies(self):
        self.write('host/core/__pycache__/ignored.py', b'not source\n')
        self.write('godot-addon/README.txt', b'not selected\n')
        self.write('host/replay/nested/not-top-level.py', b'not selected\n')
        self.assertEqual(installed._required_sources(self.studio), frozenset(self.source_map))
        self.read()

    def test_source_removal_or_change_fails_closed(self):
        path = self.studio / 'host/core/transport.py'
        path.unlink()
        self.rejected('BINDING_FILE_MISSING_OR_UNREADABLE')
        path.write_bytes(b'changed transport\n')
        self.rejected('REPLAY_REUSE_SOURCE_CHANGED')

    def test_missing_required_inventory_directory_fails_closed(self):
        path = self.studio / 'protocol/core.py'
        path.unlink()
        path.parent.rmdir()
        self.rejected('BINDING_FILE_MISSING_OR_UNREADABLE')

    def test_reparse_directory_rejected_before_inventory_descent(self):
        target = self.studio / 'godot-addon/fixture_profile'
        original = Path.lstat

        def reported(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400) if path == target else info

        with patch.object(Path, 'lstat', reported):
            self.rejected('BINDING_REPARSE')

    def test_new_dependency_during_verification_rejected(self):
        original = binding.read_execution_binding

        def verify_and_add(*args, **kwargs):
            result = original(*args, **kwargs)
            self.write('host/replay/late_dependency.py', b'late source\n')
            return result

        with patch.object(binding, 'read_execution_binding', verify_and_add):
            self.rejected('SELECTION_DEPENDENCIES_CHANGED')

    def test_selector_or_binding_change_during_verification_rejected(self):
        original = binding.read_execution_binding
        for name in installed.METADATA_PATHS:
            with self.subTest(name=name):
                self.freeze()

                def verify_and_change(*args, **kwargs):
                    result = original(*args, **kwargs)
                    path = self.studio / name
                    path.write_bytes(path.read_bytes() + b' ')
                    return result

                with patch.object(binding, 'read_execution_binding', verify_and_change):
                    self.rejected('SELECTION_CHANGED')


if __name__ == '__main__':
    unittest.main()
