"""Exact descriptor for the managed, fixed active-release public fixture scope."""
from __future__ import annotations

import hashlib

from ...protocol.core import PROTOCOL_VERSION, SCHEMA_VERSION, canonical_bytes

SELECTOR_SCOPE = 'fixture.active-release'
SELECTOR_INSPECT_MAX_BYTES = 4096
SELECTOR_PAYLOAD_MAX_BYTES = 8192
SELECTOR_DESCRIPTOR = {
    'protocol_version': PROTOCOL_VERSION,
    'schema_version': SCHEMA_VERSION,
    'scope': SELECTOR_SCOPE,
    'registration': 'exact-live-managed-fixture-owner-with-durable-custody',
    'target': {'stable_id': 'active-release'},
    'routes': {
        '/v1/discovery': {'role':'work','request':['project_id','protocol_version'],'response':'Discovery'},
        '/v1/inspect': {'role':'control','request':['project_id','protocol_version'],'response':'SelectorSnapshot'},
        '/v1/lease': {'role':'work','request':['project_id','ttl_ms'],
                      'response':['lease_id','fencing_epoch','expires_ms']},
        '/v1/commands': {'role':'work','request':'Request','response':'Response'},
        '/v1/lookup': {'role':'control','request':['project_id','command_id'],'response':'Response'},
        '/v1/cancel': {'role':'control','request':['project_id','command_id'],'response':'Response'},
        '/v1/stop': {'role':'control','request':['project_id','command_id'],
                     'response':['stopped','pending_command','command']},
    },
    'operations': {
        'fixture.release.activate': {
            'session_scope':'fixture.write','write_scopes':[SELECTOR_SCOPE],
            'payload_fields':['assets','entrypoint','expected_generation','expected_selection_hash',
                              'expected_source_revision','expected_source_sha256','expected_game_revision'],
            'asset_id_pattern':'[a-z][a-z0-9_-]{0,47}',
            'asset_fields':['value','references'],
            'value':'inert bounded JSON; no evaluation or filesystem access',
            'references':'sorted unique asset IDs; all present; every asset reachable from entrypoint',
            'max_payload_bytes':SELECTOR_PAYLOAD_MAX_BYTES,'max_assets':16,'max_references_per_asset':16,
            'expected_generation':'integer:0..9007199254740991',
            'expected_selection_hash':'lowercase SHA-256 hex',
            'expected_source_sha256':'lowercase SHA-256 hex',
            'revision_pattern':'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',
        },
        'fixture.release.inspect': {
            'session_scope':'fixture.read','read_scopes':[SELECTOR_SCOPE],
            'max_response_bytes':SELECTOR_INSPECT_MAX_BYTES,
            'fields':['project_id','protocol_version','schema_digest','generation','selection_hash',
                      'revisions','stopped','ready','pending_command','selected','last_verified_adopted'],
            'revisions':['source_revision','source_sha256','game_revision'],
            'selection':'null or exact generation/selection_hash/release_id/manifest_sha256; release fields nullable',
            'asset_bytes_exposed':False,'filesystem_identifiers_exposed':False,
        },
    },
    'validation': {
        'additional_fields':False,'json':'strict UTF-8 / canonical RFC8785 digest',
        'max_depth':32,'max_object_members':256,'max_array_items':256,'max_string_chars':16384,
        'max_pending':1,'max_lease_ttl_ms':30000,
        'manifest_scope':'fixed active release hashes and logical IDs only; no blob paths or FileIDs',
        'general_safe_file_mutation':False,
    },
}
SELECTOR_SCHEMA_DIGEST = 'sha256:' + hashlib.sha256(canonical_bytes(SELECTOR_DESCRIPTOR)).hexdigest()
