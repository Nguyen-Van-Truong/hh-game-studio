"""Hostile captured-byte vectors; no process or engine is launched here."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.pipeline import native_job, run_validation


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def source_digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))


class CaptureBindingTests(unittest.TestCase):
    RUN_ID = 'gt05-capture-test'
    SKIN_WARNING = b'12:00:00 | WARNING: Armature must be the parent of skinned meshArmature is selected by its name, but may be false in case of instances\n'
    SAMPLER_WARNING = b'12:00:00 | WARNING: More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.\n'
    WARNINGS = SKIN_WARNING * 4 + SAMPLER_WARNING

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-gt05-capture-test-')
        self.addCleanup(self.temporary.cleanup)
        self.studio = Path(self.temporary.name)
        self.root = self.studio / '.local/reviews' / self.RUN_ID
        self.host = self.root / 'host'
        self.host.mkdir(parents=True)
        self.patch = patch.object(run_validation, 'STUDIO', self.studio)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.source = {'pipeline/producer/run_blender.py': sha(b'# fixed source\n')}
        source = self.root / 'source/pipeline/producer/run_blender.py'
        source.parent.mkdir(parents=True)
        source.write_bytes(b'# fixed source\n')
        write(self.root / 'source-files.json', self.source)
        self.payloads = {'fixture.glb': b'captured-glb-bytes', 'fixture.blend': b'captured-blend-bytes'}
        for name, raw in self.payloads.items():
            target = self.root / 'fixture' / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(raw)
        self.producer = {'variant': 'baseline', 'license': 'original-fixture', 'external_inputs': [],
            'formal_acceptance': False, 'pins': {'source_files': copy.deepcopy(self.source),
                'source_sha256': source_digest(self.source)},
            'artifacts': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in self.payloads.items()}}
        self.capture = {'completed': True, 'formal_acceptance': False, 'public_ack': False,
            'actual_process_exit': {'pid': 101, 'exit_code': 0}, 'wrapper_exit_code': 0,
            'natural_tree_exit': True, 'active_before_cleanup': 0,
            'job': {'configured': True, 'assigned': True, 'closed': True, 'zero_observed': True,
                'tainted': False, 'handle_retained': False, 'active_count': 0}}
        write(self.host / 'process-start.json', {'pid': 101})
        write(self.host / 'process-exit.json', {'pid': 101, 'exit_code': 0})
        (self.host / 'stderr.txt').write_bytes(b'')
        self.diagnostic = {'run_id': self.RUN_ID, 'variant': 'baseline', 'producer_completed': True,
            'source_files': copy.deepcopy(self.source), 'formal_acceptance': False, 'public_ack': False}
        self.seal_producer()

    def marker(self):
        return {'variant': self.producer['variant'], 'source_sha256': self.producer['pins']['source_sha256'],
            'report_sha256': sha((self.root / 'fixture/producer-report.json').read_bytes()),
            'blend_bytes': len(self.payloads['fixture.blend']), 'glb_bytes': len(self.payloads['fixture.glb']),
            'formal_acceptance': False}

    def seal_capture(self):
        self.capture['artifacts'] = {name: sha((self.host / name).read_bytes()) for name in
            ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json')}
        write(self.host / 'capture.json', self.capture)
        self.diagnostic['host_capture_sha256'] = sha((self.host / 'capture.json').read_bytes())
        write(self.root / 'diagnostic.json', self.diagnostic)

    def seal_producer(self):
        write(self.root / 'fixture/producer-report.json', self.producer)
        self.diagnostic['report_sha256'] = sha((self.root / 'fixture/producer-report.json').read_bytes())
        self.diagnostic['artifacts'] = copy.deepcopy(self.producer['artifacts'])
        (self.host / 'stdout.txt').write_bytes(self.WARNINGS + b'GT05_PRODUCER_COMPLETE ' + encoded(self.marker()))
        self.seal_capture()

    def verify_host(self):
        return native_job.verify_captured_stage(self.host, self.diagnostic['host_capture_sha256'])

    def rejects_host(self, code):
        with self.assertRaisesRegex(native_job.StageFailed, '^' + code + '$'):
            self.verify_host()

    def rejects_producer(self, code):
        with self.assertRaisesRegex(ValueError, '^' + code + '$'):
            run_validation.captured_producer(self.RUN_ID)

    def test_valid_capture_returns_verified_immutable_payload_bytes(self):
        self.assertEqual(self.verify_host()['actual_process_exit'], {'pid': 101, 'exit_code': 0})
        root, producer, raw, payloads = run_validation.captured_producer(self.RUN_ID)
        self.assertEqual(root, self.root)
        self.assertEqual(producer, self.producer)
        self.assertEqual(sha(raw), self.diagnostic['report_sha256'])
        self.assertEqual(payloads, self.payloads)
        (self.root / 'fixture/fixture.glb').write_bytes(b'changed after verification')
        self.assertEqual(payloads['fixture.glb'], self.payloads['fixture.glb'])

    def test_capture_and_raw_artifact_hash_drift_rejected(self):
        (self.host / 'capture.json').write_bytes(encoded(self.capture) + b' ')
        self.rejects_host('CAPTURE_HASH')
        self.seal_capture()
        (self.host / 'stderr.txt').write_bytes(b'unbound diagnostic')
        self.rejects_host('CAPTURE_ARTIFACT_HASH')

    def test_missing_extra_and_hostile_artifact_membership_rejected_even_with_new_capture_hash(self):
        original = copy.deepcopy(self.capture)
        for name in ('stderr.txt', 'process-start.json', 'process-exit.json', 'stdout.txt'):
            with self.subTest(missing=name):
                self.capture = copy.deepcopy(original)
                self.capture['artifacts'].pop(name)
                write(self.host / 'capture.json', self.capture)
                self.diagnostic['host_capture_sha256'] = sha((self.host / 'capture.json').read_bytes())
                self.rejects_host('CAPTURE_ARTIFACT_SET')
        self.capture = copy.deepcopy(original)
        self.capture['artifacts']['../outside.txt'] = '0' * 64
        write(self.host / 'capture.json', self.capture)
        self.diagnostic['host_capture_sha256'] = sha((self.host / 'capture.json').read_bytes())
        self.rejects_host('CAPTURE_ARTIFACT_SET')

    def test_hash_consistent_nonzero_native_exit_cannot_be_hidden_by_success_scalar(self):
        write(self.host / 'process-exit.json', {'pid': 101, 'exit_code': 17})
        self.seal_capture()
        self.rejects_host('CAPTURE_PROCESS_BINDING')
        self.capture['actual_process_exit']['exit_code'] = 17
        self.seal_capture()
        self.rejects_host('CAPTURE_PROCESS_BINDING')

    def test_hash_consistent_pid_mismatch_and_invalid_native_record_types_rejected(self):
        pairs = [({'pid': 101}, {'pid': 102, 'exit_code': 0}),
                 ({'pid': True}, {'pid': 1, 'exit_code': 0}),
                 ({'pid': 0}, {'pid': 0, 'exit_code': 0}),
                 ({'pid': 101}, {'pid': 101, 'exit_code': False}),
                 ({'pid': 101, 'extra': 'unallowed'}, {'pid': 101, 'exit_code': 0})]
        for started, exited in pairs:
            with self.subTest(started=started, exited=exited):
                write(self.host / 'process-start.json', started)
                write(self.host / 'process-exit.json', exited)
                self.capture['actual_process_exit'] = exited
                self.seal_capture()
                self.rejects_host('CAPTURE_PROCESS_BINDING')

    def test_nonzero_wrapper_forced_cleanup_and_unknown_job_state_rejected(self):
        original = copy.deepcopy(self.capture)
        patches = [('wrapper_exit_code', 17), ('wrapper_exit_code', False), ('completed', False),
                   ('natural_tree_exit', False), ('active_before_cleanup', 1), ('active_before_cleanup', False)]
        for key, value in patches:
            with self.subTest(key=key, value=value):
                self.capture = copy.deepcopy(original)
                self.capture[key] = value
                self.seal_capture()
                self.rejects_host('CAPTURE_PROCESS_BINDING')
        for key, value in [('closed', False), ('zero_observed', False), ('tainted', True), ('handle_retained', True)]:
            with self.subTest(job_key=key):
                self.capture = copy.deepcopy(original)
                self.capture['job'][key] = value
                self.seal_capture()
                self.rejects_host('CAPTURE_PROCESS_BINDING')

    def test_missing_raw_process_record_rejected(self):
        (self.host / 'process-exit.json').unlink()
        with self.assertRaises(OSError):
            self.verify_host()

    def test_missing_duplicate_wrong_and_extra_marker_fields_rejected_after_rebinding_logs(self):
        good = self.marker()
        variants = [b'', (b'GT05_PRODUCER_COMPLETE ' + encoded(good)) * 2]
        for key, value in [('report_sha256', '0' * 64), ('source_sha256', '1' * 64),
                           ('variant', 'edited'), ('glb_bytes', 999), ('formal_acceptance', True),
                           ('unexpected', 'field')]:
            wrong = dict(good, **{key: value})
            variants.append(b'GT05_PRODUCER_COMPLETE ' + encoded(wrong))
        for index, raw in enumerate(variants):
            with self.subTest(vector=index):
                (self.host / 'stdout.txt').write_bytes(self.WARNINGS + raw)
                self.seal_capture()
                self.rejects_producer('PRODUCER_CAPTURE_MARKER')

    def test_missing_unknown_and_duplicated_exporter_warnings_rejected_after_hash_rebinding(self):
        marker = b'GT05_PRODUCER_COMPLETE ' + encoded(self.marker())
        for warnings in (self.SKIN_WARNING * 3 + self.SAMPLER_WARNING,
                         self.WARNINGS + self.SAMPLER_WARNING,
                         self.WARNINGS + b'12:00:00 | WARNING: another exporter issue\n'):
            with self.subTest(warnings=warnings[-100:]):
                (self.host / 'stdout.txt').write_bytes(warnings + marker)
                self.seal_capture()
                self.rejects_producer('PRODUCER_WARNING_SET_CHANGED')

    def test_exporter_error_or_stderr_cannot_be_hidden_by_success_capture(self):
        marker = b'GT05_PRODUCER_COMPLETE ' + encoded(self.marker())
        (self.host / 'stdout.txt').write_bytes(self.WARNINGS + b'Error: invalid export\n' + marker)
        self.seal_capture()
        self.rejects_producer('PRODUCER_UNEXPLAINED_LOG')
        (self.host / 'stdout.txt').write_bytes(self.WARNINGS + marker)
        (self.host / 'stderr.txt').write_bytes(b'native diagnostic requiring review')
        self.seal_capture()
        self.rejects_producer('PRODUCER_STDERR_REQUIRES_REVIEW')

    def test_source_map_snapshot_hash_and_traversal_rejected(self):
        write(self.root / 'source-files.json', {})
        self.rejects_producer('PRODUCER_SOURCE_MAP')
        write(self.root / 'source-files.json', self.source)
        (self.root / 'source/pipeline/producer/run_blender.py').write_bytes(b'unreviewed source')
        self.rejects_producer('PRODUCER_SOURCE_SNAPSHOT')
        self.diagnostic['source_files'] = {'../outside.py': '0' * 64}
        write(self.root / 'source-files.json', self.diagnostic['source_files'])
        write(self.root / 'diagnostic.json', self.diagnostic)
        self.rejects_producer('PRODUCER_SOURCE_PATH')

    def test_empty_source_closure_is_rejected(self):
        self.diagnostic['source_files'] = {}
        write(self.root / 'source-files.json', {})
        write(self.root / 'diagnostic.json', self.diagnostic)
        with self.assertRaises(ValueError):
            run_validation.captured_producer(self.RUN_ID)

    def test_self_consistent_report_and_marker_cannot_claim_unbound_producer_source(self):
        self.producer['pins']['source_files'] = {'pipeline/producer/run_blender.py': '0' * 64}
        self.producer['pins']['source_sha256'] = source_digest(self.producer['pins']['source_files'])
        self.seal_producer()
        with self.assertRaises(ValueError):
            run_validation.captured_producer(self.RUN_ID)

    def test_report_and_artifact_byte_hash_drift_rejected(self):
        raw_report = (self.root / 'fixture/producer-report.json').read_bytes()
        (self.root / 'fixture/producer-report.json').write_bytes(raw_report + b' ')
        self.rejects_producer('PRODUCER_REPORT_HASH')
        (self.root / 'fixture/producer-report.json').write_bytes(raw_report)
        (self.root / 'fixture/fixture.glb').write_bytes(b'wrong geometry')
        self.rejects_producer('PRODUCER_BYTES')

    def test_missing_and_extra_source_artifact_slots_rejected_when_report_hashes_match(self):
        original = copy.deepcopy(self.producer['artifacts'])
        for artifacts in ({'fixture.glb': original['fixture.glb']},
                          dict(original, **{'../outside.blend': original['fixture.blend']})):
            with self.subTest(artifacts=list(artifacts)):
                self.producer['artifacts'] = artifacts
                self.seal_producer()
                self.rejects_producer('PRODUCER_SLOT_SET')


if __name__ == '__main__':
    unittest.main()
