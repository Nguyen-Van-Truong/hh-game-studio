"""Read-only coordinator verification; never an independent critic signature."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / 'zdoc/reviews/20260915-gt02-s30-01'
STUDIO = ROOT / 'studio'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('DUPLICATE_KEY')
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def confined(base, name):
    parts = name.split('/')
    assert name and '\\' not in name and ':' not in name and all(p not in ('', '.', '..') for p in parts)
    path = base.joinpath(*parts)
    path.resolve().relative_to(base.resolve())
    assert not path.is_symlink()
    return path


def verify():
    candidate = read(PACK / 'candidate.json')
    manifest = read(PACK / 'source-closure.json')
    files = manifest['files']
    rows = []
    for name, digest in sorted(files.items()):
        assert re.fullmatch('[0-9a-f]{64}', digest)
        assert sha(confined(STUDIO, name)) == digest, name
        rows.append(f'8-9-hh3d-3/studio/{name}\0{digest}\n')
    closure = hashlib.sha256(''.join(rows).encode()).hexdigest()
    assert closure == manifest['source_closure_sha256'] == candidate['source_closure_sha256']
    excluded = {'__pycache__', '.godot', '.local', 'evidence'}
    actual = {'toolchain.lock.json'}
    for folder in ('protocol', 'host/core', 'tests/protocol', 'tests/bootstrap', 'build/bootstrap', 'fixtures'):
        actual.update(p.relative_to(STUDIO).as_posix() for p in (STUDIO / folder).rglob('*')
                      if p.is_file() and not set(p.relative_to(STUDIO).parts) & excluded)
    assert actual == set(files), 'missing or added closure dependency'
    for name, digest in candidate['artifacts'].items():
        assert sha(confined(PACK, name)) == digest, name
    actual_artifacts = {p.relative_to(PACK).as_posix() for p in PACK.rglob('*') if p.is_file()}
    assert actual_artifacts == set(candidate['artifacts']) | {'candidate.json'}
    assert candidate['status'] == 'CANDIDATE' and candidate['source_unchanged'] is True
    assert candidate['acceptance_ready'] is False and candidate['acceptance'] == 'NOT_REVIEWED'
    assert {lane['suite'] for lane in candidate['lanes']} == {'protocol', 'bootstrap'}
    tests = set()
    counts = {}
    skips = []
    for lane in candidate['lanes']:
        run, summary = lane['host'], lane['summary']
        host = read(confined(PACK, run['host']))
        assert type(host['exit_code']) is int and host['exit_code'] == 0
        assert host['target_pid'] == run['target_pid'] and host['started_at']
        assert run['exit_code'] == run['wrapper_exit_code'] == 0
        assert run['ownership'] == 'gated_job_kill_on_close' and run['tree_verified'] is True
        assert run['timed_out'] is False and lane['passed'] is True
        assert not lane['missing_required_evidence']
        assert summary['errors'] == summary['failures'] == 0
        assert summary['tests_run'] == len(summary['test_ids']) == len(set(summary['test_ids']))
        assert summary['skips'] == len(summary['skipped'])
        output = confined(PACK, run['stdout']).read_text(encoding='utf-8')
        markers = [json.loads(line[len('HH_GT02_TEST_RESULT '):]) for line in output.split('\n')
                   if line.startswith('HH_GT02_TEST_RESULT ')]
        assert markers == [summary], 'missing or altered child completion marker'
        skipped = {item['id'] for item in summary['skipped']}
        assert skipped <= set(summary['test_ids'])
        tests.update(set(summary['test_ids']) - skipped)
        skips.extend(summary['skipped'])
        counts[lane['suite']] = {'run': summary['tests_run'], 'passed': summary['tests_run'] - summary['skips'], 'skipped': summary['skips']}
    golden = [read(p) for p in (PACK / 'golden').glob('*.json')]
    godot = next(record for record in golden if record['format'] == 'hh-gt02-golden-host-v1')
    node = next(record for record in golden if record['format'] == 'hh-gt02-node-golden-host-v1')
    assert godot['host_exit'] == node['host_exit'] == 0
    assert godot['leftover_before'] == godot['leftover_after'] == [] and godot['source_unchanged'] is True
    assert godot['stderr'] == node['stderr'] == ''
    payloads = [json.loads(line[len('HH_GT02_JCS '):]) for line in godot['stdout'].split('\n') if line.startswith('HH_GT02_JCS ')]
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload['rows'] == node['rows'] and len(payload['rows']) == 2396
    assert len(payload['rejected']) == 9 and all(v['ok'] is False for v in payload['rejected'].values())
    spec = importlib.util.spec_from_file_location('gt02_golden_verify', STUDIO / 'tests/protocol/test_golden_vectors.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.GoldenVectorTests.setUpClass()
    assert payload['rows'] == module.GoldenVectorTests.expected
    for row in payload['rows']:
        data = row['canonical'].encode('utf-8')
        assert row['utf8_hex'] == data.hex() and row['sha256'] == 'sha256:' + hashlib.sha256(data).hexdigest()
    mapping = {
        'P-01': ['raw_wire_rejections_leave_every_observed_boundary_unchanged'],
        'P-02': ['python_vectors', 'node_consumer_when_available', 'godot_consumer_when_available'],
        'P-03': ['unicode_and_large_integer_reject', 'raw_wire_rejections_leave_every_observed_boundary_unchanged'],
        'P-04': ['non_nfc_name_rejects_before_command_construction', 'wire_payload_hashes_preserve_composed_and_decomposed_text'],
        'P-05': ['every_required_envelope_field_is_required_without_side_effects', 'envelope_type_and_unknown_field_rejections_have_no_effect'],
        'P-06': ['response_status', 'authenticated_discovery_and_typed_fixture_roundtrip'],
        'P-07': ['authenticated_discovery_and_typed_fixture_roundtrip', 'read_only_default_session_cannot_mutate_or_stop'],
        'P-08': ['semantic_scope_identity_hash_and_deadline_rejections_have_no_effect'],
        'P-09': ['fence_cannot_change_between_validation_and_effect', 'queued_revision_and_lease_are_checked_again_before_apply'],
        'P-10': ['same_command_concurrent_retries_have_one_durable_result', 'same_id_different_payload_rejects'],
        'P-11': ['same_id_changed_payload_conflicts_and_cannot_apply_twice'],
        'P-12': ['archive_retains_original_receipt_across_repeated_compact_and_reopen', 'expired_archive_is_authenticated_read_only_and_retains_original_receipt'],
        'P-13': ['capacity_reserves_terminal_record_and_bytes_before_mutation', 'reopen_and_compaction_stream_receipts_with_bounded_memory', 'unreadable_history_never_rejects_an_already_applied_command'],
        'P-14': ['parent_handle_blocks_rename_before_final_file_is_open', 'ancestor_swap_between_resolve_and_open_is_rejected', 'final_file_swap_to_hardlink_between_resolve_and_open_rejects'],
        'P-15': ['every_mutation_rejects_before_io_even_during_junction_swaps', 'exclusive_handle_hardlink_counterexample_keeps_mutation_disabled'],
        'P-16': ['auth_required_for_every_read_write_and_control_route', 'queued_read_authorization_is_rechecked_after_rotation_revoke_and_expiry'],
        'P-17': ['no_exec_primitives_in_validation_modules', 'semantic_scope_identity_hash_and_deadline_rejections_have_no_effect', 'open_lane_policy_rejects_valid_wire_without_execution_or_effect'],
        'P-18': ['old_credentials_and_encoded_variants_never_enter_metadata_or_output', 'real_log_receipt_output_file_contains_only_redacted_bytes'],
        'P-19': ['pending_ack_socket_cuts_preserve_lookup_and_one_effect', 'committed_lookup_ack_socket_cuts_return_original_receipt', 'cancel_ack_socket_cuts_do_not_duplicate_or_apply', 'stop_ack_socket_cuts_preserve_stopped_state_on_reconnect', 'reload_barrier_failure_across_fresh_process_and_archive', 'terminal_write_failure_across_fresh_process_and_archive', 'partial_terminal_record_never_authorizes_success_or_retry', 'terminal_flush_failure_across_fresh_process_and_archive', 'terminal_fsync_failure_across_fresh_process_and_archive'],
        'P-20': ['prompt_injection_is_data_and_never_executed', 'semantic_scope_identity_hash_and_deadline_rejections_have_no_effect'],
        'P-21': ['python_vectors', 'node_consumer_when_available', 'godot_consumer_when_available'],
        'P-22': ['real_parser_rejections_resolve_to_fixed_actionable_guidance', 'unknown_codes_are_bounded_inert_and_never_echoed'],
    }
    coverage = []
    for requirement, names in mapping.items():
        bound = []
        for name in names:
            found = [item for item in tests if item.endswith('.test_' + name)]
            assert len(found) == 1, (requirement, name)
            bound.extend(found)
        coverage.append({'requirement': requirement, 'test_ids': bound, 'observed': 'PASSED_TEST_SCOPE_ONLY'})
    return {'schema': 'hh-gt02-coordinator-verification-v1', 'status': 'COORDINATOR_LOGIC_VERIFIED',
            'source_closure_sha256': closure, 'source_files': len(files), 'artifacts_verified': len(candidate['artifacts']),
            'candidate_sha256': sha(PACK / 'candidate.json'), 'counts': counts, 'skips': skips,
            'golden_rows': len(payload['rows']), 'godot_negative_cases': len(payload['rejected']),
            'coverage': coverage, 'formal_acceptance': False, 'independent_critic_signatures': 0,
            'limits': ['P-02/P-21 serializer conformance; Python host owns raw wire admission',
                       'P-14/P-15 read identity and safe rejection only; Windows/Linux file mutation unsupported',
                       'P-19 in-process fixture transport; engine tree recovery belongs to later gates',
                       'one coordinator verification is not two independent reviews']}


if __name__ == '__main__':
    result = verify()
    output = Path(__file__).with_name('verification.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('status', 'source_closure_sha256', 'source_files', 'artifacts_verified', 'counts')}))
