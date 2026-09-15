"""Read-only preaudit B; copied source and focused fixtures live in disposable roots."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
manifest = json.loads((ROOT / 'zdoc/reviews/20260915-gt02-s29-01/source-closure.json').read_text())
frozen = manifest['files']
source = {name: (ROOT / 'studio' / name).read_bytes() for name in frozen}
hashes = {name: hashlib.sha256(data).hexdigest() for name, data in source.items()}
unchanged_at_copy = all((ROOT / 'studio' / name).read_bytes() == data for name, data in source.items())
if not unchanged_at_copy:
    raise RuntimeError('SOURCE_CHANGED_WHILE_COPYING')

selected = [
    'test_redaction', 'test_security_vectors', 'test_domain_contract', 'test_safe_open',
    'test_transport.TransportTests.test_authenticated_discovery_and_typed_fixture_roundtrip',
    'test_transport.TransportTests.test_read_only_default_session_cannot_mutate_or_stop',
    'test_transport.TransportTests.test_auth_required_for_every_read_write_and_control_route',
    'test_transport.TransportTests.test_expiry_rotation_revocation_and_session_cap',
    'test_transport.TransportTests.test_host_origin_encoding_route_and_project_reject_before_effect',
    'test_transport.TransportTests.test_preauth_byte_caps_duplicate_headers_and_compression_rejection',
    'test_transport.TransportTests.test_actual_wire_and_retained_diagnostics_do_not_echo_credentials_or_paths',
    'test_transport.TransportTests.test_queued_rotation_revoke_and_expiry_are_rechecked_before_apply',
    'test_transport_recovery.TransportRecoveryTests.test_old_credentials_and_encoded_variants_never_enter_metadata_or_output',
    'test_transport_recovery.TransportRecoveryTests.test_credential_history_budget_never_forgets_and_rotation_failure_is_atomic',
    'test_transport_recovery.TransportRecoveryTests.test_queued_read_authorization_is_rechecked_after_rotation_revoke_and_expiry',
]

with tempfile.TemporaryDirectory(prefix='gt02-s30-preaudit-b-source-') as directory:
    snapshot = Path(directory)
    for name, data in source.items():
        path = snapshot / 'studio' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    sys.path[:0] = [str(snapshot), str(snapshot / 'studio/tests/protocol')]
    from studio.build.bootstrap.run_fixture import source_closure_sha256
    closure = source_closure_sha256(hashes)
    suite = unittest.defaultTestLoader.loadTestsFromNames(selected)
    def ids(item):
        return [item.id()] if isinstance(item, unittest.TestCase) else [name for child in item for name in ids(child)]
    test_ids = ids(suite)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    # An independently selected raw-wire check, outside the existing test cases.
    from test_transport import TransportTests
    from studio.protocol.core import canonical_bytes
    from studio.host.core.limits import payload_digest
    fixture = TransportTests()
    fixture.setUp()
    probes = []
    try:
        before = fixture.host.fixture.snapshot()
        discover = fixture.client.discover()
        for operation in ('python.eval', 'gdscript.eval', 'shell.exec', 'open_lane.exec', 'file.write', 'url.fetch'):
            request = fixture.client.request('probe.' + operation).as_dict()
            request['operation'] = operation
            request['payload_hash'] = payload_digest(operation, request['target'], request['payload'], request['schema_version'])
            request.pop('digest', None)
            _, reply = fixture.raw(canonical_bytes(request), path='/v1/commands')
            assert reply['status'] == 'REJECTED' and reply['code'] == 'UNSUPPORTED_OPERATION', (operation, reply['status'], reply['code'])
            assert not discover.supports(operation)
            probes.append({'operation': operation, 'code': reply['code'], 'advertised': False})
        assert fixture.host.fixture.snapshot() == before
        # Archive is also a read boundary, including unknown command IDs.
        _, archive = fixture.raw(canonical_bytes({'project_id':'project.fixture','command_id':'probe.unknown'}),
                                 path='/v1/archive', control=True, auth=False)
        assert archive['code'] == 'AUTH_REQUIRED'
        probes.append({'route':'/v1/archive','unauthenticated_code':archive['code']})
        _, wildcard = fixture.raw(fixture.discovery_body(), headers={'Origin':'http://127.0.0.1:12346'})
        assert wildcard['code'] == 'ORIGIN_REJECTED'
        probes.append({'route':'/v1/discovery','unlisted_loopback_origin_code':wildcard['code']})
    finally:
        fixture.tearDown()
    summary = {
        'proof_class':'PREAUDIT_ONLY_NOT_CANDIDATE', 'snapshot_closure_sha256':closure,
        'source_files':len(hashes), 'source_changed_from_s29':{key:{'s29':frozen[key],'snapshot':value} for key,value in hashes.items() if value != frozen[key]},
        'reviewed_hashes':{key:value for key,value in hashes.items() if key.startswith('host/core/') or key in ('protocol/core.py','protocol/errors.py','protocol/ERRORS.md')},
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':[{'id':item.id(),'reason':reason} for item,reason in result.skipped],
        'test_ids':test_ids,'extra_probes':probes,
        'workspace_matches_snapshot_after_tests':all((ROOT/'studio'/name).read_bytes()==data for name,data in source.items()),
    }
    print(json.dumps(summary, indent=2))
    print(output.getvalue())
    sys.exit(0 if result.wasSuccessful() else 1)
