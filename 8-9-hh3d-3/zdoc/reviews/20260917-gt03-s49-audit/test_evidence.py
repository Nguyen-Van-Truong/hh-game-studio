"""Pure audit tamper regressions; never launches Docker, Godot, or a native Job."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
PATH = Path(__file__).with_name('verify_evidence.py')
spec = importlib.util.spec_from_file_location('s49_audit_under_test', PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
SOURCE = audit.PROFILE / 'source/studio'
sys.path.insert(0, str(SOURCE.parent))
executor = audit.module('s49_test_frozen_executor', SOURCE / 'godot-addon/linux_executor.py')
probe = audit.module('s49_test_frozen_probe', SOURCE / 'tests/godot/run_linux_probe.py')
BASE = audit.PROFILE / 'defaults_override/executor'
INPUTS = {name: (BASE / 'snapshot' / name).read_bytes()
          for name in audit.read(BASE / 'input-manifest.json')}


class AuditTests(unittest.TestCase):
    def verify_executor(self, mutate=None):
        original_read, original_inventory = audit.read, audit.inventory
        tool = audit.STUDIO / '.local/tooling/godot-4.7.2-stable-linux'
        lock = original_read(SOURCE / 'godot-addon/validator-toolchain.lock.json')
        def read(path):
            result = copy.deepcopy(original_read(path))
            return mutate(Path(path), result) if mutate else result
        def inventory(path):
            # This regression suite does not repeatedly hash the 200 MiB tool.
            # The standalone verifier still checks its actual exact inventory.
            if path == tool:
                return {lock['binary_name']: lock['binary_sha256']}
            return original_inventory(path)
        with patch.object(audit, 'read', read), patch.object(audit, 'inventory', inventory):
            return audit.verify_executor(BASE, executor, probe, mode='profile-validate', timeout=20, inputs=INPUTS)

    def mutation(self, filename, change):
        def mutate(path, value):
            if path.name == filename:
                change(value)
            return value
        with self.assertRaises(ValueError):
            self.verify_executor(mutate)

    def test_actual_profile_raw_evidence_baseline(self):
        self.assertIs(self.verify_executor()['diagnostic_process_clean'], True)

    def test_duplicate_and_nonfinite_json_rejected(self):
        for text in ('{"a":1,"a":2}', '{"n":NaN}', '{"n":Infinity}', '{"n":1e309}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                audit.parse(text)

    def test_alias_paths_rejected(self):
        for name in ('../x', '/x', 'a//b', 'a/./b', 'a\\b', 'a:b', 'a./b', 'a\nb'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                audit.relative(name)

    def test_json_bool_is_not_integer(self):
        self.assertFalse(audit.integer(False, 0))
        self.assertFalse(audit.exact({'n': False}, {'n': 0}))

    def test_wrong_mode(self):
        self.mutation('result.json', lambda row: row.update(mode='parse'))

    def test_stale_source_input_hash(self):
        self.mutation('result.json', lambda row: row['input_hashes_before'].update({'scripts/fixture_actor.gd': '0' * 64}))

    def test_admission_release_missing(self):
        self.mutation('result.json', lambda row: row['admission'].pop('released'))

    def test_public_ack_forged(self):
        self.mutation('result.json', lambda row: row.update(public_ack=True))

    def test_supervisor_changed(self):
        self.mutation('result.json', lambda row: row['supervisor'].update(pid=2))

    def test_create_argv_changed(self):
        self.mutation('create-argv.json', lambda row: row.remove('--read-only'))

    def test_native_writable_harness(self):
        def change(rows):
            next(row for row in rows[0]['Mounts'] if row['Destination'] == '/harness')['RW'] = True
        self.mutation('created-inspect-stdout.txt', change)

    def test_native_wrong_mount_source(self):
        self.mutation('created-inspect-stdout.txt', lambda rows: rows[0]['Mounts'][0].update(Source='C:\\wrong'))

    def test_closed_job_missing(self):
        self.mutation('engine-host.json', lambda row: row['job_owner'].pop('closed'))

    def test_retained_job_handle(self):
        self.mutation('engine-host.json', lambda row: row['job_owner'].update(handle_retained=True))

    def test_eof_integer_not_boolean(self):
        self.mutation('engine-host.json', lambda row: row.update(stream_reader_eof=[1, True]))

    def test_capture_byte_count_wrong(self):
        self.mutation('engine-host.json', lambda row: row['stream_byte_counts'].__setitem__(0, 0))

    def test_missing_native_exit(self):
        self.mutation('cleanup-inspect-stdout.txt', lambda rows: rows[0]['State'].pop('ExitCode'))

    def test_missing_removal_job_close(self):
        self.mutation('owned-remove-host.json', lambda row: row['job_owner'].update(closed=False))

    def test_changed_harness_hash(self):
        self.mutation('result.json', lambda row: row.update(profile_harness_sha256='0' * 64))

    def test_source_inventory_extra_rejected(self):
        with tempfile.TemporaryDirectory(prefix='hh-s49-audit-unit-') as temporary:
            base = Path(temporary); source = base / 'source/studio'; source.mkdir(parents=True)
            (source / 'x.py').write_bytes(b'x=1\n')
            files = {'x.py': audit.sha(source / 'x.py')}
            (base / 'source-closure.json').write_text(json.dumps({'files': files, 'source_closure_sha256': 'a' * 64}))
            audit.source_copy(base, files, 'a' * 64)
            (source / 'extra.py').write_bytes(b'x=2\n')
            with self.assertRaises(ValueError):
                audit.source_copy(base, files, 'a' * 64)

    def test_artifact_inventory_omission_rejected(self):
        with tempfile.TemporaryDirectory(prefix='hh-s49-audit-unit-') as temporary:
            root = Path(temporary)
            directories = {name: root / 'zdoc/reviews' / name.lower()
                           for name in ('AUDIT', 'PACKAGE', 'LINUX', 'PROFILE', 'HOST_DEATH')}
            files = {}
            for directory in directories.values():
                directory.mkdir(parents=True)
                (directory / 'raw.txt').write_bytes(b'raw\n')
                files[(directory / 'raw.txt').relative_to(root).as_posix()] = audit.sha(directory / 'raw.txt')
            manifest = directories['AUDIT'] / 'artifact-manifest.json'
            manifest.write_text(json.dumps({'files': files}))
            with patch.multiple(audit, ROOT=root, **directories):
                self.assertEqual(audit.verify_artifacts(), files)
                (directories['PROFILE'] / 'omitted.txt').write_bytes(b'missing inventory entry\n')
                with self.assertRaises(ValueError):
                    audit.verify_artifacts()


if __name__ == '__main__':
    unittest.main(verbosity=2)
