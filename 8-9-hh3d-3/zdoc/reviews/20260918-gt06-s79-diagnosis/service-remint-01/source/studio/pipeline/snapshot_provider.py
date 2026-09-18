"""Installed captured-evidence provider for the closed GT05 staged asset owner.

The coordinator fixes the run IDs and complete frozen source map at construction.
No remote request supplies paths, evidence dictionaries, native commands or a
completed flag. Returned payload bytes come directly from strict verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time

from studio.protocol.core import canonical_bytes
from studio.host.blender.deadline import AbsoluteDeadline
from . import snapshot_state as model
from .verify_run import verify_chain, safe_name, strict, sha

RUN_ROLES = ('producer_id', 'validation_id', 'consumer_id', 'repeat_producer_id',
             'repeat_validation_id', 'edited_producer_id', 'edited_validation_id',
             'reimport_id', 'visual_id', 'rejections_id')
REQUIRED_SOURCE = frozenset(('pipeline/snapshot_provider.py', 'pipeline/snapshot_owner.py',
    'pipeline/snapshot_state.py', 'pipeline/verify_run.py', 'pipeline/godot/consumer.py',
    'protocol/core.py', 'toolchain.lock.json', 'tests/asset-profile.json',
    'contracts/naming-convention-v1.md', 'blender-addon/exporter.lock.json',
    'pipeline/dependencies/gltf-validator.lock.json'))


class CapturedSnapshotProvider:
    def __init__(self, studio, *, runs, source_files):
        self.studio = Path(studio).absolute()
        model.need(type(runs) is dict and set(runs) == set(RUN_ROLES), 'SNAPSHOT_COMPLETE_RUN_IDS')
        import re
        model.need(all(type(value) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', value)
                       for value in runs.values()), 'SNAPSHOT_RUN_ID')
        model.need(type(source_files) is dict and REQUIRED_SOURCE <= set(source_files)
                   and len(source_files) <= 2048, 'SNAPSHOT_COMPLETE_SOURCE')
        self._files = dict(sorted(source_files.items()))
        for name, digest in self._files.items():
            safe_name(name)
            model.need(not name.startswith('.local/'), 'SNAPSHOT_SOURCE_NOT_RUNTIME')
            model.hash_value(digest)
        self._runs = dict(runs)
        self._expected = sha(canonical_bytes(self._files))
        self._stop = threading.Event()
        self.last_proof = None
        model.need(self.current_source() == self._expected, 'SNAPSHOT_PROVIDER_SOURCE_CHANGED')

    def current_source(self):
        files = {}
        for name in self._files:
            path = self.studio / name
            info = path.stat(follow_symlinks=False)
            model.need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                       'SNAPSHOT_SOURCE_REPARSE')
            files[name] = sha(path.read_bytes())
        return sha(canonical_bytes(files))

    def request_stop(self):
        self._stop.set()

    def __call__(self, request):
        return self.verify(request, deadline_ms=int(time.time() * 1000) + 60000, stop=self._stop)

    def verify(self, request, *, deadline_ms, stop):
        budget = AbsoluteDeadline(deadline_ms, host_deadline=time.monotonic() + 60)

        def guard():
            model.need(not self._stop.is_set() and not stop.is_set(), 'SNAPSHOT_VERIFIER_STOPPED')
            budget.check()

        request = model.validate_request(request)
        guard()
        model.need(request['expected_source_sha256'] == self._expected == self.current_source(),
                   'SNAPSHOT_PROVIDER_SOURCE_CHANGED')
        verified = verify_chain(self.studio, **self._runs, require_current_source=True, phase_guard=guard)
        proof, payloads = verified.proof, verified.payloads
        model.need(proof['publishable'] is True and proof['current_source_verified'] is True
                   and proof['complete'] is True and not proof['stale_source_files'], 'SNAPSHOT_CHAIN_INCOMPLETE')
        model.need(set(proof['evidence']) == set(model.EVIDENCE), 'SNAPSHOT_EVIDENCE_REQUIRED')
        model.need(set(proof['source_files']) <= set(self._files)
                   and all(self._files[name] == digest for name, digest in proof['source_files'].items()),
                   'SNAPSHOT_CHAIN_SOURCE_NOT_FROZEN')
        asset = strict(payloads['asset-manifest.json'])
        producer = strict(payloads['producer-report.json'])
        profile_raw = (self.studio / 'tests/asset-profile.json').read_bytes()
        model.need(sha(profile_raw) == self._files['tests/asset-profile.json'], 'SNAPSHOT_PROFILE_NOT_FROZEN')
        profile = strict(profile_raw)
        model.need(asset['catalog'] == producer['catalog'] and asset['license'] == producer['license']
                   == 'original-fixture' and asset['profile_id'] == producer['profile_id'] == profile['profile_id'],
                   'SNAPSHOT_METADATA_PROVENANCE')
        for name in ('fixture.blend', 'fixture.glb'):
            model.need(asset['artifacts'][name] == producer['artifacts'][name]
                       == {'sha256': sha(payloads[name]), 'bytes': len(payloads[name])}, 'SNAPSHOT_PAYLOAD_BINDING')
        info = {'schema': 'HH-GT05-SNAPSHOT-METADATA-1',
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'profile_sha256': sha(profile_raw),
            'naming_sha256': self._files['contracts/naming-convention-v1.md'],
            'toolchain_sha256': self._files['toolchain.lock.json'],
            'import_preset_sha256': proof['import_preset_sha256'],
            'tolerances_sha256': sha(canonical_bytes(profile['tolerances'])),
            'binaries': proof['binaries'],
            'exporter_sha256': self._files['blender-addon/exporter.lock.json'],
            'validator_sha256': self._files['pipeline/dependencies/gltf-validator.lock.json'],
            'semantic': proof['semantic'], 'license': 'original-fixture',
            'creator': 'HH Studio original procedural fixture generator', 'attribution': '',
            'catalog': asset['catalog']}
        guard()
        model.need(self.current_source() == self._expected, 'SNAPSHOT_PROVIDER_SOURCE_CHANGED')
        candidate = model.VerifiedSnapshot(self._expected,
            tuple((name, payloads[name]) for name in model.NAMES),
            tuple((name, proof['evidence'][name]) for name in model.EVIDENCE), canonical_bytes(info))
        model.verified(candidate)
        self.last_proof = proof
        return candidate
