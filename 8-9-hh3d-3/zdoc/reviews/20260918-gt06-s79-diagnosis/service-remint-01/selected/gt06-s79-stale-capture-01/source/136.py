"""Closed GT05 staged-asset history; no disk, engine or activation authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.custody import identity_from
from studio.host.core.private_store import StagedBlob, MAX_BLOB_BYTES, MAX_STAGED_BYTES, MAX_STAGED_OBJECTS
from studio.host.core.safe_replace import MAX_FILES, MAX_TOTAL_BYTES
from .naming import validate_catalog

SCHEMA = 'HH-GT05-STAGED-SNAPSHOT-1'
PROFILE = 'gt05.original-fixture.staged'
PROJECT = 'pipeline.gt05.staged'
TARGET = 'snapshot'
NAMES = ('fixture.blend', 'fixture.glb', 'producer-report.json', 'asset-manifest.json')
MANIFEST = 'publication-manifest.json'
SELECTOR = 'snapshot.json'
EVIDENCE = ('producer', 'admission', 'khronos', 'godot', 'repeat', 'edit', 'reimport', 'visual', 'rejections')
MAX_METADATA_BYTES = 16 * 1024
MAX_HISTORY = 7  # Genesis, Config, Intent, Staged, Selecting, Terminal, Stop.


class SnapshotError(ValueError):
    def __init__(self, code, *, outcome_unknown=False, cleanup_owner=None):
        self.code = code
        self.outcome_unknown = outcome_unknown
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def need(value, code='SNAPSHOT_HISTORY_INVALID'):
    if not value:
        raise SnapshotError(code)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hash_value(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'SNAPSHOT_HASH_REQUIRED')


def identifier(value):
    need(type(value) is str and re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,127}', value) is not None,
         'SNAPSHOT_COMMAND_ID')


def validate_request(value):
    exact(value, ('schema', 'profile', 'command_id', 'expected_source_sha256'))
    need(value['schema'] == SCHEMA and value['profile'] == PROFILE, 'SNAPSHOT_PROFILE_REQUIRED')
    identifier(value['command_id'])
    hash_value(value['expected_source_sha256'])
    return parse_json(canonical_bytes(value))


def metadata(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_METADATA_BYTES, 'SNAPSHOT_METADATA_CAP')
    value = parse_json(raw)
    need(canonical_bytes(value) == raw, 'SNAPSHOT_METADATA_CANONICAL')
    hashes = ('profile_sha256', 'naming_sha256', 'toolchain_sha256', 'import_preset_sha256',
              'tolerances_sha256', 'exporter_sha256', 'validator_sha256')
    exact(value, ('schema', 'timestamp', *hashes, 'binaries', 'semantic', 'license', 'creator', 'attribution', 'catalog'))
    need(value['schema'] == 'HH-GT05-SNAPSHOT-METADATA-1', 'SNAPSHOT_METADATA_SCHEMA')
    need(type(value['timestamp']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value['timestamp']) is not None,
         'SNAPSHOT_TIMESTAMP')
    try:
        datetime.strptime(value['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as error:
        raise SnapshotError('SNAPSHOT_TIMESTAMP') from error
    for name in hashes:
        hash_value(value[name])
    exact(value['binaries'], ('blender', 'godot', 'python', 'node'))
    for digest in value['binaries'].values():
        hash_value(digest)
    exact(value['semantic'], ('sha256', 'hash_domain'))
    hash_value(value['semantic']['sha256'])
    need(value['semantic']['hash_domain'] == 'sha256:exact-file-bytes', 'SNAPSHOT_HASH_DOMAIN')
    need(value['license'] == 'original-fixture', 'SNAPSHOT_LICENSE')
    for name in ('creator', 'attribution'):
        need(type(value[name]) is str and len(value[name]) <= 1024, 'SNAPSHOT_ATTRIBUTION')
    need(bool(value['creator'].strip()), 'SNAPSHOT_CREATOR')
    need(validate_catalog(value['catalog'])['assets'] > 0, 'SNAPSHOT_EMPTY_CATALOG')
    return value


@dataclass(frozen=True)
class VerifiedSnapshot:
    """Trusted installed verifier output, never a wire/caller certificate.

    The provider owns native capture identity, process-exit and gate validation,
    and must bind every payload hash and the complete catalog to the producer,
    admission and Godot reports. A caller-declared catalog is insufficient.
    This value only transports immutable, already verified exact bytes.
    """
    source_sha256: str
    payloads: tuple[tuple[str, bytes], ...]
    evidence: tuple[tuple[str, str], ...]
    metadata_json: bytes


def verified(value):
    need(type(value) is VerifiedSnapshot, 'SNAPSHOT_VERIFIED_PROVIDER_REQUIRED')
    hash_value(value.source_sha256)
    need(type(value.payloads) is tuple and len(value.payloads) == len(NAMES), 'SNAPSHOT_FIXED_PAYLOADS')
    for row in value.payloads:
        need(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes,
             'SNAPSHOT_IMMUTABLE_PAYLOADS')
        need(0 < len(row[1]) <= MAX_BLOB_BYTES, 'SNAPSHOT_ARTIFACT_CAP')
    payloads = dict(value.payloads)
    exact(payloads, NAMES)
    need(type(value.evidence) is tuple and len(value.evidence) == len(EVIDENCE), 'SNAPSHOT_EVIDENCE_REQUIRED')
    for row in value.evidence:
        need(type(row) is tuple and len(row) == 2 and type(row[0]) is str, 'SNAPSHOT_IMMUTABLE_EVIDENCE')
        hash_value(row[1])
    evidence = dict(value.evidence)
    exact(evidence, EVIDENCE)
    info = metadata(value.metadata_json)
    # Reserve the full manifest, selector and one temporary protected file.
    # The private blob mirror has no selector but uses the same conservative cap.
    need(len(NAMES) + 3 <= min(MAX_FILES, MAX_STAGED_OBJECTS), 'SNAPSHOT_ENTRY_CAP')
    need(sum(map(len, payloads.values())) + 3 * MAX_BLOB_BYTES <= min(MAX_TOTAL_BYTES, MAX_STAGED_BYTES),
         'SNAPSHOT_AGGREGATE_CAP')
    return payloads, evidence, info


def artifact_hashes(payloads):
    return {name: {'sha256': sha(payloads[name]), 'size_bytes': len(payloads[name])} for name in NAMES}


def manifest(config, request, payloads, evidence, info):
    return {'schema': SCHEMA, 'profile': PROFILE, 'storage_id': config['storage_id'],
            'command_id': request['command_id'], 'request_sha256': sha(canonical_bytes(request)),
            'source_sha256': request['expected_source_sha256'], 'artifacts': artifact_hashes(payloads),
            'evidence': evidence, 'metadata': info, 'public_ack': False, 'editor_activation': False,
            'snapshot_kind': 'staged-assets'}


def proof(value, manifest_raw):
    payloads, evidence, _ = verified(value)
    need(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= MAX_BLOB_BYTES, 'SNAPSHOT_MANIFEST_CAP')
    return {'source_sha256': value.source_sha256, 'artifacts': artifact_hashes(payloads),
            'evidence': evidence, 'metadata_sha256': sha(value.metadata_json), 'manifest_sha256': sha(manifest_raw)}


def file_version(value, *, digest=None, size=None):
    exact(value, ('identity', 'sha256'))
    identity = identity_from(value['identity'])
    hash_value(value['sha256'])
    need(0 < identity.size <= MAX_BLOB_BYTES)
    need(digest is None or value['sha256'] == digest)
    need(size is None or identity.size == size)
    return identity


def blob(value):
    exact(value, ('object_id', 'identity', 'sha256', 'file_version'))
    need(type(value['object_id']) is str and re.fullmatch('blob-[0-9a-f]{32}', value['object_id']) is not None)
    identity = identity_from(value['identity'])
    durable = file_version(value['file_version'], digest=value['sha256'], size=identity.size)
    need(identity.volume == durable.volume and not identity.same_file(durable))
    return StagedBlob(value['object_id'], identity, value['sha256'])


def selection(state):
    return {'schema': SCHEMA, 'profile': PROFILE, 'storage_id': state['config']['storage_id'],
            'command_id': state['intent']['request']['command_id'],
            'request_sha256': state['intent']['request_sha256'], 'manifest': state['staged']['manifest'],
            'public_ack': False, 'editor_activation': False, 'snapshot_kind': 'staged-assets'}


def response(state):
    return {'schema': SCHEMA, 'profile': PROFILE, 'storage_id': state['config']['storage_id'],
            'command_id': state['intent']['request']['command_id'],
            'request_sha256': state['intent']['request_sha256'], 'status': 'COMMITTED',
            'source_sha256': state['config']['source_sha256'], 'artifacts': state['intent']['proof']['artifacts'],
            'manifest_sha256': state['intent']['proof']['manifest_sha256'],
            'selector_sha256': sha(canonical_bytes(state['selector'])),
            'public_ack': False, 'editor_activation': False, 'snapshot_kind': 'staged-assets'}


def unknown(storage_id, command_id, digest, phase):
    return {'schema': SCHEMA, 'storage_id': storage_id, 'command_id': command_id,
            'request_sha256': digest, 'status': 'UNKNOWN', 'phase': phase, 'public_ack': False}


def reduce(state, event):
    state, event = parse_json(canonical_bytes(state)), parse_json(canonical_bytes(event))
    need(type(event) is dict and event.get('schema') == SCHEMA)
    kind, phase = event.get('kind'), state.get('phase')
    if kind == 'CONFIG':
        exact(event, ('schema', 'kind', 'storage_id', 'profile', 'source_sha256'))
        need(not state and type(event['storage_id']) is str and re.fullmatch('[0-9a-f]{32}', event['storage_id']) is not None)
        need(event['profile'] == PROFILE)
        hash_value(event['source_sha256'])
        return {'phase': 'EMPTY', 'config': event, 'stopped': False}
    need(phase is not None)
    if kind == 'STOP':
        exact(event, ('schema', 'kind'))
        need(not state['stopped'])
        state['stopped'] = True
        return state
    need(not state['stopped'])
    if kind == 'INTENT':
        exact(event, ('schema', 'kind', 'request', 'request_sha256', 'lease_epoch', 'proof'))
        need(phase == 'EMPTY')
        request = validate_request(event['request'])
        need(event['request_sha256'] == sha(canonical_bytes(request)))
        need(type(event['lease_epoch']) is int and 0 < event['lease_epoch'] < 2**53)
        p = event['proof']
        exact(p, ('source_sha256', 'artifacts', 'evidence', 'metadata_sha256', 'manifest_sha256'))
        need(p['source_sha256'] == request['expected_source_sha256'] == state['config']['source_sha256'])
        hash_value(p['metadata_sha256'])
        hash_value(p['manifest_sha256'])
        exact(p['evidence'], EVIDENCE)
        for digest in p['evidence'].values():
            hash_value(digest)
        exact(p['artifacts'], NAMES)
        for value in p['artifacts'].values():
            exact(value, ('sha256', 'size_bytes'))
            hash_value(value['sha256'])
            need(type(value['size_bytes']) is int and 0 < value['size_bytes'] <= MAX_BLOB_BYTES)
        need(sum(x['size_bytes'] for x in p['artifacts'].values()) + 3 * MAX_BLOB_BYTES <= min(MAX_TOTAL_BYTES, MAX_STAGED_BYTES))
        state.update(phase='INTENT', intent=event)
    elif kind == 'STAGED':
        exact(event, ('schema', 'kind', 'command_id', 'request_sha256', 'manifest', 'artifacts'))
        need(phase == 'INTENT' and event['command_id'] == state['intent']['request']['command_id']
             and event['request_sha256'] == state['intent']['request_sha256'])
        exact(event['artifacts'], NAMES)
        blob(event['manifest'])
        need(event['manifest']['sha256'] == state['intent']['proof']['manifest_sha256'])
        for name, value in event['artifacts'].items():
            bound = blob(value)
            need({'sha256': bound.sha256, 'size_bytes': bound.identity.size} == state['intent']['proof']['artifacts'][name])
        descriptors = [event['manifest'], *event['artifacts'].values()]
        need(len({x['object_id'] for x in descriptors}) == len(descriptors))
        identities = [identity_from(x[k]['identity'] if k else x['identity'])
                      for x in descriptors for k in ('', 'file_version')]
        need(len({(i.volume, i.file_id) for i in identities}) == len(identities))
        need(len({i.volume for i in identities}) == 1)
        state.update(phase='STAGED', staged=event)
    elif kind == 'SELECTING':
        exact(event, ('schema', 'kind', 'selector'))
        need(phase == 'STAGED' and canonical_bytes(event['selector']) == canonical_bytes(selection(state)))
        state.update(phase='SELECTING', selector=event['selector'])
    elif kind == 'TERMINAL':
        exact(event, ('schema', 'kind', 'response', 'response_sha256', 'selector_version'))
        need(phase == 'SELECTING')
        expected = response(state)
        need(canonical_bytes(event['response']) == canonical_bytes(expected)
             and event['response_sha256'] == sha(canonical_bytes(expected)))
        selected = canonical_bytes(state['selector'])
        identity = file_version(event['selector_version'], digest=sha(selected), size=len(selected))
        versions = [state['staged']['manifest'], *state['staged']['artifacts'].values()]
        need(all(identity.volume == identity_from(v['file_version']['identity']).volume
                 and not identity.same_file(identity_from(v['file_version']['identity'])) for v in versions))
        state.update(phase='TERMINAL', terminal=event)
    else:
        need(False)
    return state
