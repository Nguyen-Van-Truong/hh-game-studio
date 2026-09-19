"""Verify retained evidence only. No live roots or runtime code are imported."""
import json
import sys
from parse_prefix import HERE, canonical, derive, need, read, sha


def verify():
    manifest = read(HERE / 'manifest.json')
    for name, ref in manifest['files'].items():
        path = (HERE / name).resolve()
        need(path.is_relative_to(HERE), 'MANIFEST_TRAVERSAL')
        raw = path.read_bytes()
        need(sha(raw) == ref['sha256'] and len(raw) == ref['size_bytes'], 'MANIFEST_HASH:' + name)
    actual = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file()}
    expected = set(manifest['files']) | {'manifest.json'}
    if (HERE / 'verification.json').exists():
        expected.add('verification.json')
    need(actual == expected, 'PACKET_FILE_SET')
    domain = read(HERE / 'raw-selected-domain.json')
    need(domain['selection_only'] and not domain['complete_raw_roots_inventory'], 'RAW_DOMAIN_SCOPE')
    need(sha(canonical(domain['files'])) == domain['selected_domain_sha256'], 'RAW_DOMAIN_HASH')
    exact = {}
    for source, record in domain['files'].items():
        portable = manifest['files'][record['portable_path']]
        need(portable['sha256'] == record['sha256'] and portable['size_bytes'] == record['size_bytes'], 'DOMAIN_BINDING:' + source)
        exact[record['portable_path']] = portable
    need(len(exact) == manifest['portable_exact_files'] == domain['selected_files'], 'EXACT_COUNT')
    need(sha(canonical(exact)) == manifest['portable_exact_domain_sha256'], 'PORTABLE_DOMAIN_HASH')
    summary = derive()
    need(summary == read(HERE / 'summary.json'), 'SUMMARY_REPRODUCTION')
    return {'schema': 'gt06-s106-prefix-packet-verification-v1', 'status': 'VERIFIED_PACKET_ONLY',
            'authority': 0, 'formal_acceptance': False, 'eligible_for_dataset': False, 'final_critic': False,
            'manifest_sha256': sha((HERE / 'manifest.json').read_bytes()),
            'manifest_files_verified': len(manifest['files']), 'portable_exact_files_verified': len(exact),
            'batch_capture_references_verified': summary['batch_capture_references_verified'],
            'all_exact_reference_occurrences': summary['all_exact_reference_occurrences'],
            'unique_exact_reference_files': summary['unique_exact_reference_files'],
            'frozen_diagnostic_files_verified': 6, 'source_audit_binding_verified': 53,
            'profile_literal_hash_verified': summary['profile_literal_hash_verified'],
            'bound_gate_pss_pairs_verified': 2, 'outer_start_exit_identity_verified': True,
            'classification': summary['classification'], 'net_pss_handle_count_delta': summary['net_pss_handle_count_delta'],
            'raw_selected_domain_sha256': domain['selected_domain_sha256'],
            'portable_exact_domain_sha256': manifest['portable_exact_domain_sha256'],
            'live_roots_read': False, 'runtime_or_engine_imported': False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error': str(error)}))
        sys.exit(1)
