"""Provider gate regressions; mock captured verification, never claim native proof."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.protocol.core import canonical_bytes
from studio.pipeline import snapshot_provider as implementation, snapshot_state as model
from studio.pipeline.verify_run import VerifiedRun
from studio.tests.pipeline.test_snapshot_state import candidate


class SnapshotProviderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='hh-gt05-provider-')
        self.addCleanup(self.temporary.cleanup)
        self.studio = Path(self.temporary.name)
        for name in implementation.REQUIRED_SOURCE:
            path = self.studio / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixed source\n')
        self.profile_path = self.studio / 'tests/asset-profile.json'
        self.profile_path.write_bytes(canonical_bytes({'profile_id': 'test-fixture', 'tolerances': {'position': .001}}))
        self.files = {name: implementation.sha((self.studio / name).read_bytes()) for name in implementation.REQUIRED_SOURCE}
        self.runs = {name: 'gt05-' + name.replace('_', '-') for name in implementation.RUN_ROLES}
        self.provider = implementation.CapturedSnapshotProvider(self.studio, runs=self.runs, source_files=self.files)
        self.request = {'schema': model.SCHEMA, 'profile': model.PROFILE, 'command_id': 'provider.case',
                        'expected_source_sha256': self.provider.current_source()}
        info = json.loads(candidate().metadata_json)
        self.payloads = {'fixture.blend': b'blend', 'fixture.glb': b'glb'}
        artifact = {name: {'sha256': implementation.sha(raw), 'bytes': len(raw)} for name, raw in self.payloads.items()}
        manifest = {'catalog': info['catalog'], 'license': 'original-fixture', 'profile_id': 'test-fixture', 'artifacts': artifact}
        self.payloads.update({'asset-manifest.json': canonical_bytes(manifest), 'producer-report.json': canonical_bytes(manifest)})
        self.proof = {'publishable': True, 'current_source_verified': True, 'complete': True,
            'stale_source_files': [], 'source_files': self.files, 'evidence': dict(candidate().evidence),
            'import_preset_sha256': '1' * 64, 'binaries': info['binaries'], 'semantic': info['semantic']}

    def verify(self, **kwargs):
        with patch.object(implementation, 'verify_chain', return_value=VerifiedRun(copy.deepcopy(self.proof), dict(self.payloads))):
            return self.provider.verify(self.request, deadline_ms=int(time.time() * 1000) + 30000,
                                        stop=threading.Event(), **kwargs)

    def test_exact_verified_payloads_become_small_staged_snapshot(self):
        result = self.verify()
        self.assertEqual(dict(result.payloads), self.payloads)
        self.assertEqual(result.source_sha256, self.request['expected_source_sha256'])
        model.verified(result)

    def test_incomplete_chain_cannot_supply_publication_candidate(self):
        self.proof['publishable'] = False
        with self.assertRaisesRegex(model.SnapshotError, 'SNAPSHOT_CHAIN_INCOMPLETE'):
            self.verify()

    def test_payload_hash_mismatch_is_not_a_proof(self):
        self.payloads['fixture.glb'] = b'tampered'
        with self.assertRaisesRegex(model.SnapshotError, 'SNAPSHOT_PAYLOAD_BINDING'):
            self.verify()

    def test_stop_before_verification_avoids_all_gate_work(self):
        self.provider.request_stop()
        with patch.object(implementation, 'verify_chain') as checker:
            with self.assertRaisesRegex(model.SnapshotError, 'SNAPSHOT_VERIFIER_STOPPED'):
                self.provider.verify(self.request, deadline_ms=int(time.time() * 1000) + 30000, stop=threading.Event())
            checker.assert_not_called()

    def test_stop_is_observed_inside_verifier_guard(self):
        def stop_during(*args, phase_guard, **kwargs):
            self.provider.request_stop()
            phase_guard()
        with patch.object(implementation, 'verify_chain', side_effect=stop_during):
            with self.assertRaisesRegex(model.SnapshotError, 'SNAPSHOT_VERIFIER_STOPPED'):
                self.provider.verify(self.request, deadline_ms=int(time.time() * 1000) + 30000, stop=threading.Event())
        self.assertIsNone(self.provider.last_proof)

    def test_metadata_uses_exact_frozen_profile_bytes(self):
        original_read = Path.read_bytes
        seen = []

        def transient_read(path):
            raw = original_read(path)
            if path == self.profile_path:
                seen.append(path)
                # During verify, first read is the source check; the second is
                # the actual metadata use. The final source check would see the
                # original bytes again, so only a direct pin comparison closes it.
                if len(seen) == 2:
                    return canonical_bytes({'profile_id': 'test-fixture', 'tolerances': {'position': .5}})
            return raw

        with patch.object(Path, 'read_bytes', transient_read):
            with self.assertRaisesRegex(model.SnapshotError, 'SNAPSHOT_PROFILE_NOT_FROZEN'):
                self.verify()
        self.assertIsNone(self.provider.last_proof)


if __name__ == '__main__':
    unittest.main()
