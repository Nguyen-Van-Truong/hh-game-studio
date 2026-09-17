"""Tamper copies of retained S63 raw bytes in memory; never modify raw runs."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gt05_package_verify', HERE/'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
REPO = HERE.parents[3]
STUDIO = REPO/verify.STUDIO_PREFIX


class PackageTamperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {'units': 'gt05-units-s63-01', 'snapshot_native': 'gt05-snapshot-native-s63-01',
            'snapshot_staged': 'gt05-staged-cut-s63-01', 'publication': 'gt05-publication-s63-01',
            'visual_review': 'gt05-visual-review-s62-02'}
        if not all((STUDIO/'.local/reviews'/name).is_dir() for name in cls.runs.values()):
            raise unittest.SkipTest('Retained local S63 raw fixture required; no fixture is synthesized as native proof')
        cls.raw = {}
        for run in cls.runs.values():
            for path in (STUDIO/'.local/reviews'/run).rglob('*'):
                if path.is_file():
                    cls.raw[path.relative_to(STUDIO).as_posix()] = path.read_bytes()
        proof = json.loads(cls.raw['.local/reviews/' + cls.runs['publication'] + '/verified-chain.json'])
        for name in proof['evidence_files']:
            if name.startswith('.local/reviews/'):
                cls.raw[name] = (STUDIO/name).read_bytes()
        unit = '.local/reviews/' + cls.runs['units']
        cls.sources = json.loads(cls.raw[unit + '/source-closure.json'])['files']
        # The fixture intentionally keeps its executed source when the live
        # implementation advances. These tests do not claim it is current.
        cls.source_raw = {verify.STUDIO_PREFIX + name: cls.raw[unit + '/source/studio/' + name] for name in cls.sources}
        sys.path.insert(0, str(STUDIO.parent))
        from studio.protocol.core import canonical_bytes
        cls.canonical = staticmethod(canonical_bytes)

    def setUp(self):
        self.p = object.__new__(verify.Package)
        self.p.repo, self.p.studio = REPO, STUDIO
        self.p.studio_sources = dict(self.sources)
        self.p.source = {verify.STUDIO_PREFIX + name: digest for name, digest in self.sources.items()}
        self.p.raw_map = {name: verify.sha(raw) for name, raw in self.raw.items()}
        driver = '.local/reviews/' + self.runs['snapshot_staged'] + '/driver.snapshot'
        driver_name = (HERE/'run_staged_cut.py').relative_to(REPO).as_posix()
        self.p.review = {driver_name: verify.sha(self.raw[driver])}
        self.p.data = {**self.source_raw, **{verify.STUDIO_PREFIX + name: raw for name, raw in self.raw.items()},
                       driver_name: self.raw[driver]}
        self.p.canonical = self.canonical
        self.p.manifest = {'runs': dict(self.runs)}

    def set_raw(self, name, value):
        raw = value if isinstance(value, bytes) else json.dumps(value, indent=2).encode() + b'\n'
        self.p.data[verify.STUDIO_PREFIX + name] = raw
        self.p.raw_map[name] = verify.sha(raw)
        return raw

    def expect(self, code, call):
        with self.assertRaises(verify.Rejected) as rejected:
            call()
        self.assertEqual(rejected.exception.code, code)

    def native_reseal(self, case, observed):
        lane = self.p.run('snapshot_native') + '/' + case
        raw = self.set_raw(lane + '/observed.json', observed)
        self.set_raw(lane + '/native-stdout.txt', b'GT05_SNAPSHOT_PROBE ' + verify.compact({
            'case': case, 'observed_sha256': verify.sha(raw), 'passed': True,
            'synthetic_storage_only': True, 'asset_validation_proven': False}) + b'\n')

    def test_retained_bound_components_verify_without_replay(self):
        units = self.p.units()
        self.assertEqual(units['tests'], 223)
        self.assertEqual(self.p.snapshot_native()['cases'], 11)
        self.assertEqual(self.p.staged_cut(units)['recovery'], 'UNKNOWN')
        publication, config, proof = self.p.publication(units)
        self.assertEqual(len(publication['receipt_sha256']), 64)
        self.assertEqual(self.p.visual_review(config, proof)['captured_frames'], 68)

    def test_missing_raw_host_is_not_substituted_from_summary(self):
        del self.p.raw_map[self.p.run('units') + '/unit-host.json']
        self.expect('RAW_NOT_INDEXED', self.p.units)

    def test_run_inventory_cannot_omit_retained_selector(self):
        self.p.check_raw_inventory()
        name = next(name for name in self.p.raw_map if name.startswith(self.p.run('snapshot_native') + '/')
                    and name.endswith('/snapshot.json'))
        del self.p.raw_map[name]
        self.expect('RAW_INVENTORY', self.p.check_raw_inventory)

    def test_rehashed_wrong_unit_marker_still_rejects(self):
        root = self.p.run('units')
        capture = self.p.obj(root + '/capture.json')
        fake = copy.deepcopy(capture['summary']); fake['run'] = 222
        raw = self.set_raw(root + '/unit-stdout.txt', b'GT05_UNIT_COMPLETE ' + verify.compact(fake) + b'\n')
        capture['artifacts']['unit-stdout.txt'] = verify.sha(raw)
        self.set_raw(root + '/capture.json', capture)
        self.expect('RAW_MARKER_BINDING', self.p.units)

    def test_rehashed_claim_zero_cannot_hide_actual_host_exit(self):
        root = self.p.run('units'); host = self.p.obj(root + '/unit-host.json')
        host['exit_code'] = 9; raw = self.set_raw(root + '/unit-host.json', host)
        capture = self.p.obj(root + '/capture.json'); capture['artifacts']['unit-host.json'] = verify.sha(raw)
        self.set_raw(root + '/capture.json', capture)
        self.expect('HOST_ACTUAL_EXIT', self.p.units)

    def test_rehashed_crash_pass_requires_exit_86(self):
        case = 'crash_artifact'; observed = self.p.obj(self.p.run('snapshot_native') + '/' + case + '/observed.json')
        observed['child_exit'] = 0; self.native_reseal(case, observed)
        self.expect('NATIVE_ACTUAL_CRASH_BINDING', self.p.snapshot_native)

    def test_rehashed_fault_report_requires_exact_hook(self):
        case = 'write_failure'; observed = self.p.obj(self.p.run('snapshot_native') + '/' + case + '/observed.json')
        observed['fault_hooks'] = ['publication-manifest.json']; self.native_reseal(case, observed)
        self.expect('NATIVE_FAULT_HOOK', self.p.snapshot_native)

    def test_last_good_bytes_checked_beyond_unchanged_flag(self):
        prefix = self.p.run('snapshot_native') + '/success/hh-files-'
        name = next(name for name in self.p.raw_map if name.startswith(prefix) and name.endswith('/fixture.glb'))
        self.set_raw(name, b'tampered last-good payload')
        self.expect('STORAGE_PAYLOAD_BINDING', self.p.snapshot_native)

    def test_rehashed_manifest_cannot_change_receipt_bound_metadata(self):
        units = self.p.units(); root = self.p.run('publication')
        manifest = self.p.obj(root + '/publication-manifest.json'); manifest['metadata']['creator'] = 'different creator'
        raw = self.set_raw(root + '/publication-manifest.json', manifest)
        observed = self.p.obj(root + '/observed.json'); observed['manifest_sha256'] = verify.sha(raw)
        observed_raw = self.set_raw(root + '/observed.json', observed)
        self.set_raw(root + '/publication-stdout.txt', b'GT05_ACTUAL_SNAPSHOT ' + verify.compact({
            'observed_sha256': verify.sha(observed_raw), 'receipt_sha256': observed['receipt_sha256'],
            'status': 'COMMITTED', 'public_ack': False}) + b'\n')
        self.expect('PUBLICATION_MANIFEST_RECEIPT', lambda: self.p.publication(units))

    def test_chain_evidence_cannot_reference_unindexed_raw(self):
        units = self.p.units()
        del self.p.raw_map['.local/reviews/gt05-validation-s62-01/admission-host/capture.json']
        self.expect('CHAIN_RAW_BINDING', lambda: self.p.publication(units))

    def test_wrong_current_source_or_subset_is_rejected(self):
        def read(path, *unused):
            return self.source_raw[path.relative_to(REPO).as_posix()]
        self.p.studio_sources.pop('pipeline/verify_run.py')
        with patch.object(verify, 'read_file', read):
            self.expect('CURRENT_SOURCE_CLOSURE', self.p.check_current_source)

    def test_staged_success_flag_cannot_hide_selector(self):
        units = self.p.units(); root = self.p.run('snapshot_staged')
        manifest_name = next(name for name in self.p.raw_map if name.startswith(root + '/hh-files-')
                             and name.endswith('/publication-manifest.json'))
        self.set_raw(manifest_name.rsplit('/', 1)[0] + '/snapshot.json', b'{}')
        self.expect('STAGED_SELECTOR_ABSENT', lambda: self.p.staged_cut(units))

    def test_unsafe_duplicate_alias_and_duplicate_json_reject(self):
        self.expect('UNSAFE_PATH', lambda: verify.hash_map({'../outside': 'a'*64}))
        self.expect('PATH_ALIAS', lambda: verify.hash_map({'A/file.py': 'a'*64, 'a/File.py': 'a'*64}))
        self.expect('JSON_DUPLICATE', lambda: verify.strict(b'{"passed":false,"passed":true}'))


class NativeBoneTamperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bone_run = 'gt05-bone-migration-s64-01'
        root = STUDIO / '.local/reviews' / cls.bone_run
        if not (root / 'capture.json').is_file():
            raise unittest.SkipTest('Retained native bone capture required; no native success is synthesized')
        cls.config = json.loads((root / 'invocation.json').read_bytes())
        cls.raw = {}
        for run in (cls.bone_run, cls.config['last_good_run_id']):
            for path in (STUDIO / '.local/reviews' / run).rglob('*'):
                if path.is_file():
                    cls.raw[path.relative_to(STUDIO).as_posix()] = path.read_bytes()
        for name in cls.config['baseline_files']:
            path = STUDIO / '.local/reviews' / cls.config['baseline_run_id'] / 'fixture' / name
            cls.raw[path.relative_to(STUDIO).as_posix()] = path.read_bytes()

    def setUp(self):
        self.p = object.__new__(verify.Package)
        self.p.repo, self.p.studio = REPO, STUDIO
        self.p.studio_sources = dict(self.config['source_files'])
        self.p.raw_map = {name: verify.sha(raw) for name, raw in self.raw.items()}
        self.p.data = {verify.STUDIO_PREFIX + name: raw for name, raw in self.raw.items()}
        root = '.local/reviews/' + self.bone_run
        self.p.data.update({verify.STUDIO_PREFIX + name: self.raw[root + '/source/' + name]
                            for name in self.p.studio_sources})
        driver_name = '8-9-hh3d-3/' + self.config['driver_path']
        self.p.review = {driver_name: self.config['driver_sha256']}
        self.p.data[driver_name] = self.raw[root + '/driver.snapshot']
        self.p.manifest = {'runs': {'bone_migration': self.bone_run, 'publication': self.config['last_good_run_id']}}

    set_raw = PackageTamperTests.set_raw
    expect = PackageTamperTests.expect

    def reseal_report(self, case, report):
        root = self.p.run('bone_migration'); lane = root + '/' + case
        raw = self.set_raw(lane + '/report.json', report)
        marker = {'case': case, 'native_pid': report['native_pid'], 'report_sha256': verify.sha(raw),
            'changed_blend_sha256': report['changed_blend_sha256'], 'rejection': 'OBSERVED_NAME_SET',
            'migration_required': True, 'formal_acceptance': False}
        stdout = self.set_raw(lane + '/host/stdout.txt', b'GT05_BONE_MIGRATION_REJECTED ' + verify.compact(marker) + b'\n')
        host = self.p.obj(lane + '/host/capture.json'); host['artifacts']['stdout.txt'] = verify.sha(stdout)
        host_raw = self.set_raw(lane + '/host/capture.json', host)
        capture = self.p.obj(root + '/capture.json')
        row = next(row for row in capture['cases'] if row['case'] == case)
        row.update(report_sha256=verify.sha(raw), host_capture_sha256=verify.sha(host_raw))
        self.set_raw(root + '/capture.json', capture)

    def test_actual_native_rename_and_delete_records_verify(self):
        result = self.p.bone_migration()
        self.assertEqual(result['cases'], ['rename', 'delete'])
        self.assertFalse(result['accepted_mapping'])
        self.assertEqual(len(result['affected_ids']['meshes']), 4)
        self.assertEqual(result['affected_ids']['sockets'], [])

    def test_resealed_setup_error_cannot_count_as_admission_rejection(self):
        report = self.p.obj(self.p.run('bone_migration') + '/rename/report.json')
        report['admission']['stage'] = 'observe'
        self.reseal_report('rename', report)
        self.expect('BONE_ADMISSION_REACHED', self.p.bone_migration)

    def test_resealed_proposed_mapping_cannot_be_claimed_accepted(self):
        report = self.p.obj(self.p.run('bone_migration') + '/delete/report.json')
        report['accepted_mapping'] = True
        self.reseal_report('delete', report)
        self.expect('BONE_MAPPING_SCOPE', self.p.bone_migration)

    def test_resealed_report_cannot_omit_shared_skin_consumer(self):
        report = self.p.obj(self.p.run('bone_migration') + '/rename/report.json')
        report['dependencies']['meshes'].pop()
        self.reseal_report('rename', report)
        self.expect('BONE_NATIVE_REPORT', self.p.bone_migration)

    def test_resealed_bone_diff_must_match_native_observation(self):
        report = self.p.obj(self.p.run('bone_migration') + '/delete/report.json')
        report['bone_diff']['missing'] = []
        self.reseal_report('delete', report)
        self.expect('BONE_NATIVE_DIFF', self.p.bone_migration)


if __name__ == '__main__':
    unittest.main()
