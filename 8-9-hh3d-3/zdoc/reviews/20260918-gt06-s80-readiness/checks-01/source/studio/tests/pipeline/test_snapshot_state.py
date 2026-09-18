"""Closed-history adversarial vectors; these do not claim native storage proof."""
from dataclasses import replace
from pathlib import Path
import copy
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline import snapshot_state as model
from studio.protocol.core import canonical_bytes


def request(command_id='snapshot'):
    return {'schema': model.SCHEMA, 'profile': model.PROFILE, 'command_id': command_id,
            'expected_source_sha256': '1' * 64}


def candidate():
    catalog = {'schema': 'HH-ASSET-NAMES-1', 'assets': [{'asset_id': 'prp_fixture', 'class': 'prop',
        'nodes': [{'name': 'prp_fixture_lod0', 'role': 'render', 'lod': 0}],
        'bones': [], 'clips': [], 'materials': ['mat_fixture'], 'sockets': []}]}
    metadata = {'schema': 'HH-GT05-SNAPSHOT-METADATA-1', 'timestamp': '2026-09-17T12:00:00Z',
        **{key: '2' * 64 for key in ('profile_sha256', 'naming_sha256', 'toolchain_sha256',
           'import_preset_sha256', 'tolerances_sha256', 'exporter_sha256', 'validator_sha256')},
        'binaries': {key: '3' * 64 for key in ('blender', 'godot', 'python', 'node')},
        'semantic': {'sha256': '4' * 64, 'hash_domain': 'sha256:exact-file-bytes'},
        'license': 'original-fixture', 'creator': 'HH Studio original fixture', 'attribution': '', 'catalog': catalog}
    return model.VerifiedSnapshot('1' * 64, tuple((name, (name + '\n').encode()) for name in model.NAMES),
        tuple((name, '%064x' % (n + 1)) for n, name in enumerate(model.EVIDENCE)), canonical_bytes(metadata))


def descriptor(number, raw):
    identity = {'volume': '1', 'file_id': '%032x' % number, 'size': len(raw)}
    digest = model.sha(raw)
    return {'object_id': 'blob-' + '%032x' % number, 'identity': identity, 'sha256': digest,
            'file_version': {'identity': dict(identity, file_id='%032x' % (number + 100)), 'sha256': digest}}


def replay(rows):
    state = {}
    for row in rows:
        state = model.reduce(state, row)
    return state


def events():
    value = candidate()
    payloads, evidence, metadata = model.verified(value)
    req = request()
    config = dict(schema=model.SCHEMA, kind='CONFIG', profile=model.PROFILE, storage_id='a' * 32,
                  source_sha256=value.source_sha256)
    manifest_raw = canonical_bytes(model.manifest(config, req, payloads, evidence, metadata))
    intent = dict(schema=model.SCHEMA, kind='INTENT', request=req, request_sha256=model.sha(canonical_bytes(req)),
                  lease_epoch=1, proof=model.proof(value, manifest_raw))
    staged = dict(schema=model.SCHEMA, kind='STAGED', command_id=req['command_id'], request_sha256=intent['request_sha256'],
                  manifest=descriptor(5, manifest_raw),
                  artifacts={name: descriptor(i + 1, payloads[name]) for i, name in enumerate(model.NAMES)})
    rows = [config, intent, staged]
    selected = model.selection(replay(rows))
    rows.append(dict(schema=model.SCHEMA, kind='SELECTING', selector=selected))
    result = model.response(replay(rows))
    rows.append(dict(schema=model.SCHEMA, kind='TERMINAL', response=result,
        response_sha256=model.sha(canonical_bytes(result)), selector_version=descriptor(6, canonical_bytes(selected))['file_version']))
    return rows


class SnapshotStateTests(unittest.TestCase):
    def test_every_interrupted_prefix_is_uncommitted(self):
        rows = events()
        for count in range(1, len(rows)):
            with self.subTest(count=count):
                self.assertNotIn('terminal', replay(rows[:count]))
        self.assertEqual(replay(rows)['terminal']['response']['status'], 'COMMITTED')

    def test_skips_reorders_and_duplicate_phases_rejected(self):
        rows = events()
        bad = [rows[:i] + rows[i + 1:] for i in range(len(rows) - 1)]
        bad += [rows[:i] + [rows[i], rows[i]] + rows[i + 1:] for i in range(len(rows))]
        for changed in bad:
            with self.subTest(rows=[x['kind'] for x in changed]), self.assertRaises(ValueError):
                replay(changed)

    def test_profile_source_slot_and_manifest_substitution(self):
        mutations = [lambda r: r[0].update(profile='export.publish'),
            lambda r: r[1]['proof'].update(source_sha256='9' * 64),
            lambda r: r[2]['artifacts'].update({'scene.glb': r[2]['artifacts'].pop('fixture.glb')}),
            lambda r: r[2]['manifest'].update(sha256='9' * 64),
            lambda r: r[2]['artifacts']['fixture.glb']['file_version'].update(sha256='9' * 64),
            lambda r: r[1]['proof']['artifacts']['fixture.glb'].update(size_bytes=1),
            lambda r: r[2]['artifacts']['fixture.glb'].update(object_id=r[2]['manifest']['object_id'])]
        for mutation in mutations:
            rows = events()
            mutation(rows)
            with self.assertRaises(ValueError):
                replay(rows)

    def test_forged_terminal_selector_hash_size_identity_or_claim(self):
        mutations = [lambda r: r[-1]['response'].update(public_ack=True),
            lambda r: r[-1]['response'].update(public_ack=0),
            lambda r: r[-1]['response'].update(editor_activation=True),
            lambda r: r[-1].update(response_sha256='0' * 64),
            lambda r: r[-1]['selector_version'].update(sha256='0' * 64),
            lambda r: r[-1]['selector_version']['identity'].update(size=1),
            lambda r: r[-1]['selector_version']['identity'].update(file_id=r[2]['manifest']['file_version']['identity']['file_id'])]
        for mutation in mutations:
            rows = events()
            mutation(rows)
            with self.assertRaises(ValueError):
                replay(rows)

    def test_selector_numeric_boolean_substitution_is_not_exact_bytes(self):
        rows = events()
        rows[3]['selector']['public_ack'] = 0
        with self.assertRaises(ValueError):
            replay(rows)

    def test_stop_all_prefixes_prevents_progress_preserves_completed(self):
        stop = {'schema': model.SCHEMA, 'kind': 'STOP'}
        rows = events()
        for count in range(1, len(rows)):
            state = replay(rows[:count] + [stop])
            self.assertTrue(state['stopped'])
            with self.assertRaises(ValueError):
                model.reduce(state, rows[count])
        self.assertEqual(replay(rows + [stop])['terminal'], rows[-1])

    def test_request_is_closed_and_detached(self):
        for req in (dict(request(), completed=True), dict(request(), path='C:/source'), dict(request(), profile='export.publish')):
            with self.assertRaises(ValueError):
                model.validate_request(req)
        req = request()
        other = model.validate_request(req)
        req['command_id'] = 'changed'
        self.assertEqual(other['command_id'], 'snapshot')

    def test_provider_must_be_immutable_exact_and_bounded(self):
        value = candidate()
        bad = [dict(value.__dict__), replace(value, payloads=list(value.payloads)),
            replace(value, payloads=value.payloads[:-1]), replace(value, evidence=value.evidence[:-1]),
            replace(value, payloads=((model.NAMES[0], b'x' * (model.MAX_BLOB_BYTES + 1)),) + value.payloads[1:]),
            replace(value, payloads=((model.NAMES[0], bytearray(b'x')), ) + value.payloads[1:])]
        for value in bad:
            with self.assertRaises(ValueError):
                model.verified(value)

    def test_caps_reserve_namespace_and_manifest(self):
        from unittest.mock import patch
        value = candidate()
        boundary = replace(value, payloads=tuple((name, b'x' * model.MAX_BLOB_BYTES) for name in model.NAMES))
        model.verified(boundary)
        for constant, limit, code in [('MAX_FILES', 6, 'ENTRY_CAP'), ('MAX_STAGED_OBJECTS', 6, 'ENTRY_CAP'),
                                      ('MAX_TOTAL_BYTES', 3 * model.MAX_BLOB_BYTES, 'AGGREGATE_CAP'),
                                      ('MAX_STAGED_BYTES', 3 * model.MAX_BLOB_BYTES, 'AGGREGATE_CAP')]:
            with patch.object(model, constant, limit), self.assertRaisesRegex(ValueError, code):
                model.verified(value)

    def test_metadata_requires_name_license_timestamp_domain_and_canonical_bytes(self):
        value = candidate()
        for key, replacement in [('license', 'downloaded'), ('timestamp', '2026-99-99T12:00:00Z'), ('creator', ''),
            ('semantic', {'sha256': '4' * 64, 'hash_domain': 'compact-json'}),
            ('catalog', {'schema': 'HH-ASSET-NAMES-1', 'assets': []})]:
            meta = model.parse_json(value.metadata_json)
            meta[key] = replacement
            with self.assertRaises(ValueError):
                model.verified(replace(value, metadata_json=canonical_bytes(meta)))
        meta = model.parse_json(value.metadata_json)
        meta['catalog']['assets'][0]['asset_id'] = '../outside'
        with self.assertRaises(ValueError):
            model.verified(replace(value, metadata_json=canonical_bytes(meta)))
        with self.assertRaises(ValueError):
            model.verified(replace(value, metadata_json=value.metadata_json + b'\n'))


if __name__ == '__main__':
    unittest.main()
