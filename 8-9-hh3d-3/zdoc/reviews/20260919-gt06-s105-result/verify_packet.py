"""Read only the retained packet; never import runtime helpers or start engines."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUN_SUFFIXES = ('preflight-01', 'preflight-02', '01', '02', '03')
EXPECTED = {
    'preflight-01': ('COLLECTOR_PREPARE_FAILED_BEFORE_ENGINE', 0, None),
    'preflight-02': ('DIAGNOSTIC_BOUNDARY_ONE_BATCH', 1, 'S105_PREFIX_BOUNDARY'),
    '01': ('COLLECTOR_KEYERROR_AT_BASELINE', 5, 'KeyError'),
    '02': ('COLLECTOR_NAMEERROR_AFTER_CAPTURE_BEFORE_PERSIST', 5, 'NameError'),
    '03': ('DIAGNOSTIC_BOUNDARY_SIX_BATCHES_PSS_BASELINE_ONLY', 6, 'S105_PREFIX_BOUNDARY'),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read(path):
    return json.loads(path.read_bytes())


def optional(path):
    return read(path) if path.is_file() else None


def ref_check(base, row):
    path = (base / row['file']).resolve()
    require(path.is_relative_to(base.resolve()), 'REFERENCE_TRAVERSAL')
    raw = path.read_bytes()
    require(len(raw) == row['size_bytes'] and sha(raw) == row['sha256'], 'REFERENCE_HASH:' + row['file'])


def clean_job(value):
    return (value['closed'] is True and value['zero_observed'] is True
            and value['active_count'] == 0 and value['handle_retained'] is False
            and value['tainted'] is False and value['close_uncertain'] is False
            and value['create_uncertain'] is False and value['failed_operations'] == [])


def derive(root=HERE):
    rows = []
    verified_capture_refs = 0
    for suffix in RUN_SUFFIXES:
        run_id = 'gt06-s105-handles-' + suffix
        run = root / 'raw' / run_id
        ctx = read(run / 'context.json')
        original = read(run / 'diagnostic-result.json')
        child = root / 'generated-children' / (run_id + '.py')
        require(sha(child.read_bytes()) == ctx['child_script_sha256'], 'CHILD_HASH:' + run_id)
        require(ctx['run_id'] == run_id and not ctx['formal_acceptance'] and not ctx['eligible_for_dataset'], 'CONTEXT:' + run_id)
        require(read(run / 'source-files.json') == ctx['source_files'], 'SOURCE_LIST:' + run_id)
        failure = optional(run / 'child-failure.json')
        terminal = optional(run / 'child-terminal-cleanup.json')
        samples = [read(p) for p in sorted(run.glob('sample-preview-*.json'))]
        commands, natives = [], []
        for index, sample in enumerate(samples):
            require(sample['index'] == index, 'SAMPLE_INDEX:' + run_id)
            cap = read(run / f'batch-capture-{index:02d}.json')
            require(cap['index'] == index, 'CAPTURE_INDEX:' + run_id)
            for name, ref in cap.items():
                if name != 'index':
                    ref_check(run, ref)
                    verified_capture_refs += 1
            commands.append(read(run / cap['command']['file']))
            natives.append(read(run / cap['native']['file']))
            require(len(commands[-1]['commands']) == 1000 and len(natives[-1]['cycles']) == 100, 'BATCH_COUNTS:' + run_id)
            require(sample['dropped_commands'] == 0 and sample['dropped_telemetry'] == 0, 'DROPPED:' + run_id)
        classification, expected_count, expected_error = EXPECTED[suffix]
        require(len(samples) == expected_count, 'EXPECTED_COUNT:' + run_id)
        require((failure or {}).get('code') == expected_error, 'EXPECTED_FAILURE:' + run_id)
        host_exit = read(run / 'host-owner/process-exit.json')
        host_cleanup = read(run / 'host-owner/cleanup-001.json')
        require(host_exit['exit_code'] == 1 and host_cleanup['wrapper_exit_code'] == 1, 'HOST_EXIT:' + run_id)
        require(clean_job(host_cleanup['job']), 'HOST_JOB:' + run_id)
        require(host_cleanup['wrapper_process_handle']['closed'] and not host_cleanup['wrapper_process_handle']['handle_retained'], 'HOST_HANDLE:' + run_id)
        editor_exit = optional(run / 'editor-host/process-exit.json')
        import_exit = optional(run / 'import-host/process-exit.json')
        editor_cleanup = optional(run / 'editor-host/cleanup-001.json')
        import_capture = optional(run / 'import-host/capture.json')
        engine_started = (run / 'editor-host/process-start.json').is_file()
        require(engine_started == bool(samples), 'ENGINE_START:' + run_id)
        gaps = ['OUTER_RUNNER_ACTUAL_EXIT_NOT_IN_PACKET']
        if terminal is not None:
            ref_check(run, terminal['context'])
            require(terminal['run_id'] == run_id and terminal['completed_batches'] == len(samples), 'TERMINAL_BINDING:' + run_id)
            require(terminal['errors'] == [], 'TERMINAL_ERRORS:' + run_id)
            observations = terminal['observations']
            for name in ('import_target', 'editor_target'):
                for kind in ('start', 'exit'):
                    ref = observations[name][kind]
                    if ref is not None:
                        ref_check(run, ref)
            require(editor_exit is None and observations['editor_target']['actual_target_exit'] is None, 'EDITOR_EXIT_GAP_CHANGED:' + run_id)
            require(import_exit['exit_code'] == 0 and import_capture['wrapper_exit_code'] == 0, 'IMPORT_EXIT:' + run_id)
            require(editor_cleanup['wrapper_exit_code'] == 2 and clean_job(editor_cleanup['job']), 'EDITOR_CLEANUP:' + run_id)
            require(clean_job(import_capture['job']), 'IMPORT_JOB:' + run_id)
            require(not observations['heartbeat_alive'], 'HEARTBEAT:' + run_id)
            require(not any(observations['editor_owner']['drain_threads_alive']), 'DRAIN_THREADS:' + run_id)
            require(not observations['editor_probe']['handle_retained'], 'EDITOR_PROBE:' + run_id)
            require(observations['import_observer']['probe_handles_released'] and not observations['import_observer']['thread_alive'], 'IMPORT_OBSERVER:' + run_id)
            require(not any(observations['producer']['host']['threads_alive']), 'PRODUCER_THREADS:' + run_id)
            gaps.extend(['EDITOR_TARGET_ACTUAL_EXIT_UNKNOWN', 'IMPORT_WRAPPER_PROCESS_HANDLE_CLOSE_NOT_EXPLICIT'])
        else:
            require(suffix == 'preflight-01' and failure is None, 'MISSING_TERMINAL:' + run_id)
            stderr = (run / 'host-owner/stderr.txt').read_text()
            require("NameError: name 'os' is not defined" in stderr, 'PREFLIGHT_ERROR')
            gaps.extend(['CHILD_FAILURE_AND_TERMINAL_MISSING_PREPARE_EXCEPTION', 'ORIGINAL_ENGINE_STARTED_TRUE_IS_UNSUPPORTED'])
        http = optional(run / 'http-phases-final.json')
        http_obs = http['observation'] if http else None
        if http_obs:
            require(http_obs['transport_failures_observed'] == 0 and http_obs['first_failure'] is None, 'HTTP_FAILURES:' + run_id)
        pss_rows = []
        for p in sorted((run / 'pss').glob('*.json')):
            d = read(p)
            s = samples[d['index']]
            capture = d['capture']
            require(d['sample_sha256'] == sha(canonical(s)), 'PSS_SAMPLE_HASH')
            require(d['run_id'] == run_id and d['source_closure_sha256'] == ctx['source_closure_sha256'] and d['profile_sha256'] == ctx['profile_sha256'], 'PSS_CONTEXT')
            identity = capture['identity']
            require(identity['pid'] == s['processes']['editor']['pid'] and identity['process_start'] == s['processes']['editor']['process_start'], 'PSS_IDENTITY')
            require(capture['handles_captured'] == len(capture['entries']) == sum(capture['type_counts'].values()), 'PSS_COUNTS')
            pss_rows.append({
                'file': str(p.relative_to(run)).replace('\\', '/'), 'index': d['index'],
                'sample_sha256': d['sample_sha256'], 'original_gate_error': d['original_gate_error'],
                'status': capture['status'], 'binding_verified': capture['binding_verified'],
                'identity': identity, 'handles_captured': capture['handles_captured'],
                'target_count_before': capture['target_handle_count_before'],
                'target_count_after': capture['target_handle_count_after'],
                'observer_count_before': capture['observer_handle_count_before'],
                'observer_count_after': capture['observer_handle_count_after'],
                'cleanup': capture['cleanup'], 'errors': capture['errors'],
                'timing': capture['timing'], 'type_counts': capture['type_counts'],
                'limitations': capture['limitations'],
            })
        require(len(pss_rows) == (1 if suffix == '03' else 0), 'PSS_COUNT:' + run_id)
        if suffix == '03':
            require(pss_rows[0]['index'] == 4 and pss_rows[0]['status'] == 'OBSERVED' and pss_rows[0]['cleanup']['all_released'], 'BASELINE_PSS')
            baseline, final = samples[4], samples[5]
            for role in ('host', 'editor'):
                for metric, row in final['memory'][role].items():
                    if row['value'] is None:
                        continue
                    base_value = baseline['memory'][role][metric]['value']
                    require(row['value'] * 100 <= base_value * 110 if metric == 'rss_bytes' else row['value'] <= base_value, 'BATCH5_ORIGINAL_COUNTER_GATE')
            require(final['max_status_gap_ms'] <= 2000, 'BATCH5_ORIGINAL_STATUS_GATE')
            gaps.append('NO_FAILURE_SNAPSHOT_NO_PSS_DELTA_NO_CAUSAL_ATTRIBUTION')
        rows.append({
            'run_id': run_id, 'classification': classification, 'captured_batches': len(samples),
            'failure': failure, 'original_summary_status': original['status'],
            'original_engine_started': original['engine_started'], 'engine_start_observed': engine_started,
            'original_summary_is_acceptance': False, 'host_actual_exit': host_exit,
            'host_helper_exit': host_cleanup['wrapper_exit_code'], 'host_job_zero_closed': clean_job(host_cleanup['job']),
            'editor_actual_exit': editor_exit, 'editor_helper_exit': editor_cleanup['wrapper_exit_code'] if editor_cleanup else None,
            'editor_job_zero_closed': clean_job(editor_cleanup['job']) if editor_cleanup else None,
            'import_actual_exit': import_exit, 'import_helper_exit': import_capture['wrapper_exit_code'] if import_capture else None,
            'import_job_zero_closed': clean_job(import_capture['job']) if import_capture else None,
            'outer_runner_actual_exit': None, 'terminal_errors': terminal['errors'] if terminal else None,
            'terminal_utc': terminal['observed_utc'] if terminal else None, 'gaps': gaps,
            'http_commands': sum(len(c['commands']) for c in commands),
            'native_cycles': sum(len(n['cycles']) for n in natives),
            'editor_handles': [s['memory']['editor']['held_handles']['value'] for s in samples],
            'host_handles': [s['memory']['host']['held_handles']['value'] for s in samples],
            'editor_objects': [s['memory']['editor']['objects']['value'] for s in samples],
            'editor_resources': [s['memory']['editor']['resources']['value'] for s in samples],
            'editor_rss_bytes': [s['memory']['editor']['rss_bytes']['value'] for s in samples],
            'host_rss_bytes': [s['memory']['host']['rss_bytes']['value'] for s in samples],
            'max_http_status_gap_ms': max((c['max_status_gap_ms'] for c in commands), default=None),
            'max_native_status_gap_ms': max((n['max_status_gap_ms'] for n in natives), default=None),
            'max_combined_status_gap_ms': max((s['max_status_gap_ms'] for s in samples), default=None),
            'http_transport_failures': http_obs['transport_failures_observed'] if http_obs else None,
            'http_first_failure': http_obs['first_failure'] if http_obs else None,
            'pss': pss_rows, 'source_closure_sha256': ctx['source_closure_sha256'],
            'profile_sha256': ctx['profile_sha256'], 'generated_overlay_sha256': ctx['generated_overlay_sha256'],
            'generated_child_sha256_verified': ctx['child_script_sha256'],
        })
    require(verified_capture_refs == 102, 'TOTAL_CAPTURE_REFERENCES')
    return {
        'schema': 'gt06-s105-derived-results-v1', 'authority': 0,
        'formal_acceptance': False, 'eligible_for_dataset': False, 'final_critic': False,
        'runtime_repair_justified': False, 'root_cause_established': False,
        'verified_capture_references': verified_capture_refs,
        'captured_batches_total': sum(r['captured_batches'] for r in rows),
        'http_commands_total': sum(r['http_commands'] for r in rows),
        'native_cycles_total': sum(r['native_cycles'] for r in rows), 'runs': rows,
    }


def verify(root=HERE):
    manifest = read(root / 'manifest.json')
    files = manifest['files']
    for rel, record in files.items():
        path = (root / rel).resolve()
        require(path.is_relative_to(root.resolve()), 'MANIFEST_TRAVERSAL')
        raw = path.read_bytes()
        require(sha(raw) == record['sha256'] and len(raw) == record['size_bytes'], 'MANIFEST_HASH:' + rel)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    expected = set(files) | {'manifest.json'}
    if (root / 'verification.json').exists():
        expected.add('verification.json')
    require(actual == expected, 'UNEXPECTED_OR_MISSING_PACKET_FILES')
    domain = read(root / 'raw-selected-domain.json')
    require(sha(canonical(domain['files'])) == domain['selected_domain_sha256'], 'RAW_DOMAIN_HASH')
    require(domain['selection_only'] and not domain['complete_raw_roots_inventory'], 'DOMAIN_SCOPE')
    for source, record in domain['files'].items():
        portable = files[record['portable_path']]
        require(portable['sha256'] == record['sha256'] and portable['size_bytes'] == record['size_bytes'], 'RAW_PORTABLE_BINDING:' + source)
    portable_rows = {rel: row for rel, row in files.items() if rel.startswith(('raw/', 'generated-children/'))}
    require(sha(canonical(portable_rows)) == manifest['portable_exact_domain_sha256'], 'PORTABLE_DOMAIN_HASH')
    require(len(portable_rows) == len(domain['files']), 'DOMAIN_COUNT')
    summary = derive(root)
    require(summary == read(root / 'summary.json'), 'DERIVED_SUMMARY_MISMATCH')
    return {'schema': 'gt06-s105-packet-verification-v1', 'status': 'VERIFIED_PACKET_ONLY',
            'authority': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
            'final_critic': False, 'manifest_sha256': sha((root / 'manifest.json').read_bytes()),
            'manifest_files_verified': len(files), 'portable_exact_copies_verified': len(portable_rows),
            'raw_selected_domain_sha256': domain['selected_domain_sha256'],
            'portable_exact_domain_sha256': manifest['portable_exact_domain_sha256'],
            'capture_references_verified': summary['verified_capture_references'],
            'generated_children_verified': 5, 'terminal_context_bindings_verified': 4,
            'canonical_pss_sample_bindings_verified': 1, 'source_live_roots_read': False,
            'engine_or_runtime_imported': False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({'status': 'FAILED', 'error': str(error)}))
        sys.exit(1)
