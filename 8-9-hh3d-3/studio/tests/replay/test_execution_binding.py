"""Lightweight isolated reader tests. No engine, process launch or repository writes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch


import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import execution_binding as binding


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ExecutionBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-gt06-binding-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.studio = self.root / 'studio'
        self.studio.mkdir()
        self.path = self.root / 'execution-binding.json'
        self.files = {'godot-addon/cli_job.py': b'current Job source\n',
                      'host/replay/native_runner.py': b'current replay source\n'}
        for name, raw in self.files.items():
            target = self.studio / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.current = {name: sha(raw) for name, raw in self.files.items()}
        # Deliberately historical: the new current map must not rewrite this map
        # or require old runtime hashes after a properly frozen source refresh.
        self.accepted = {binding.GT05_SOURCE_PREFIX + 'godot-addon/cli_job.py': 'a' * 64}
        self.required = frozenset({'host/replay/native_runner.py'})
        self.document = {'schema': binding.SCHEMA,
                         'accepted_gt05_manifest_sha256': binding.GT05_MANIFEST_SHA256,
                         'source_files': dict(self.current)}
        self.freeze()

    def freeze(self, raw=None):
        raw = (json.dumps(self.document, sort_keys=True, separators=(',', ':')) + '\n').encode() \
            if raw is None else raw
        self.path.write_bytes(raw)
        self.expected = sha(raw)

    def read(self, **changes):
        args = {'expected_sha256': self.expected, 'accepted_source_files': self.accepted,
                'required_sources': self.required}
        args.update(changes)
        return binding.read_execution_binding(self.studio, self.path, **args)

    def rejected(self, code, **changes):
        with self.assertRaises(binding.BindingRejected) as caught:
            self.read(**changes)
        self.assertEqual(caught.exception.code, code)

    def test_exact_current_map_retains_historical_input_and_returns_detached_sorted_map(self):
        previous = dict(self.accepted)
        result = self.read()
        self.assertEqual(result, self.current)
        self.assertEqual(list(result), sorted(result))
        self.assertEqual(self.accepted, previous)
        result.clear()
        self.assertEqual(self.read(), self.current)

    def test_raw_hash_is_external_and_exact(self):
        self.path.write_bytes(self.path.read_bytes() + b' ')
        self.rejected('BINDING_MANIFEST_HASH')
        self.rejected('BINDING_DIGEST', expected_sha256='A' * 64)

    def test_empty_source_is_allowed_only_with_its_exact_hash(self):
        name = 'host/empty.py'
        (self.studio / name).write_bytes(b'')
        self.document['source_files'][name] = sha(b'')
        self.freeze()
        self.assertEqual(self.read()[name], sha(b''))
        self.freeze(b'')
        self.rejected('BINDING_JSON')

    def test_schema_is_exact_and_unknown_keys_are_rejected(self):
        for update in ({'schema': 'HH-GT06-EXECUTION-BINDING-0'}, {'accepted': True}):
            with self.subTest(update=update):
                original = dict(self.document)
                self.document.update(update)
                self.freeze()
                self.rejected('BINDING_SCHEMA')
                self.document = original

    def test_original_gt05_anchor_is_fixed(self):
        self.document['accepted_gt05_manifest_sha256'] = '0' * 64
        self.freeze()
        self.rejected('BINDING_GT05_ANCHOR')

    def test_duplicate_json_keys_rejected_at_top_and_source_level(self):
        raw = self.path.read_bytes()
        variants = [b'{"schema":"duplicate",' + raw[1:],
                    raw.replace(b'"source_files":{',
                        b'"source_files":{"godot-addon/cli_job.py":"' + b'0' * 64 + b'",')]
        for changed in variants:
            with self.subTest(raw=changed):
                self.freeze(changed)
                self.rejected('BINDING_JSON_DUPLICATE_KEY')

    def test_nonfinite_utf16_and_nonobject_json_rejected(self):
        for raw, code in ((b'{"schema":NaN}', 'BINDING_JSON_NONFINITE'),
                          ('{}'.encode('utf-16'), 'BINDING_JSON'),
                          (b'[]', 'BINDING_SCHEMA')):
            with self.subTest(code=code, raw=raw):
                self.freeze(raw)
                self.rejected(code)

    def test_both_inherited_and_explicit_current_dependencies_are_mandatory(self):
        for name in self.current:
            with self.subTest(name=name):
                self.document['source_files'] = {key: digest for key, digest in self.current.items()
                                                  if key != name}
                self.freeze()
                self.rejected('BINDING_MISSING_DEPENDENCY')

    def test_additional_current_dependency_cannot_be_omitted(self):
        self.rejected('BINDING_MISSING_DEPENDENCY', required_sources=self.required |
                      frozenset({'host/core/transport.py'}))

    def test_historical_source_domain_and_required_set_are_not_optional(self):
        self.rejected('BINDING_ACCEPTED_SOURCE_DOMAIN',
                      accepted_source_files={'other/studio/cli_job.py': 'a' * 64})
        self.rejected('BINDING_ACCEPTED_SOURCE_MAP', accepted_source_files={})
        self.rejected('BINDING_REQUIRED_SOURCES', required_sources=frozenset())
        self.rejected('BINDING_REQUIRED_SOURCES', required_sources=set(self.required))

    def test_path_traversal_absolute_windows_alias_and_generated_entries_rejected(self):
        names = ['../outside.py', '/outside.py', 'C:/outside.py', 'a\\b.py',
                 'a//b.py', './a.py', 'a/../b.py', 'a/trailing. ', 'NUL.py',
                 'a/COM1.txt', 'a/stream:code', 'a/\x00.py', 'a/\ud800.py', '.local/runtime.py']
        for name in names:
            with self.subTest(name=name):
                self.document['source_files'] = {**self.current, name: '0' * 64}
                self.freeze()
                self.rejected('BINDING_GENERATED_SOURCE' if name.startswith('.local/')
                              else 'BINDING_SOURCE_PATH')

    def test_case_alias_rejected_in_binding_and_required_set(self):
        self.document['source_files']['GODOT-ADDON/CLI_JOB.PY'] = '0' * 64
        self.freeze()
        self.rejected('BINDING_SOURCE_ALIAS')
        self.document['source_files'] = dict(self.current)
        self.freeze()
        self.rejected('BINDING_SOURCE_ALIAS', required_sources=self.required |
                      frozenset({'HOST/REPLAY/NATIVE_RUNNER.PY'}))

    def test_bad_source_digest_missing_source_and_directory_rejected(self):
        name = 'host/replay/native_runner.py'
        self.document['source_files'][name] = True
        self.freeze()
        self.rejected('BINDING_DIGEST')
        self.document['source_files'][name] = self.current[name]
        self.freeze()
        path = self.studio / name
        path.unlink()
        self.rejected('BINDING_FILE_MISSING_OR_UNREADABLE')
        path.mkdir()
        self.rejected('BINDING_FILE_TYPE')

    def test_current_source_mismatch_keeps_original_guard_code(self):
        (self.studio / 'godot-addon/cli_job.py').write_bytes(b'changed after freeze\n')
        self.rejected('REPLAY_REUSE_SOURCE_CHANGED')

    def test_reparse_flag_rejected_on_leaf_parent_and_binding_file(self):
        original_lstat = Path.lstat
        for target in (self.studio / 'godot-addon/cli_job.py',
                       self.studio / 'host', self.path):
            def reported(path, *args, **kwargs):
                info = original_lstat(path, *args, **kwargs)
                if path == target:
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            with self.subTest(target=target), patch.object(Path, 'lstat', reported):
                self.rejected('BINDING_REPARSE')

    def test_symbolic_link_mode_rejected_without_platform_privileges(self):
        import stat
        original_lstat = Path.lstat
        target = self.studio / 'godot-addon/cli_job.py'

        def reported(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            return SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0) if path == target else info

        with patch.object(Path, 'lstat', reported):
            self.rejected('BINDING_REPARSE')

    def test_binding_change_during_source_read_rejected(self):
        original_read = binding._read
        altered = False

        def read_and_alter(path, cap):
            nonlocal altered
            raw = original_read(path, cap)
            if path != self.path and not altered:
                self.path.write_bytes(self.path.read_bytes() + b' ')
                altered = True
            return raw

        with patch.object(binding, '_read', read_and_alter):
            self.rejected('BINDING_FILE_CHANGED')


if __name__ == '__main__':
    unittest.main()
