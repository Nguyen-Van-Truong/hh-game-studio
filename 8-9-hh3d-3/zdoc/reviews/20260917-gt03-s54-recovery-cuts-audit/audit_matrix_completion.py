"""Independent read-only raw-exit/source/log binding for the distinct cut matrix."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / '20260917-gt03-s54-recovery-cuts-03'
SOURCE_PACKAGE = HERE.parent / '20260917-gt03-s54-recovery-cuts-02'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_bytes())
capture = read(PACKAGE / 'capture.json')
reference = read(PACKAGE / 'runtime-source-reference.json')
closure = read(PACKAGE / 'source-closure.json')
driver = PACKAGE / 'driver.py'
spec = importlib.util.spec_from_file_location('matrix_frozen_log_scanner', driver)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)
expected_cases = ['script-committed', 'script-retired', 'edit-applied', 'script-unwitnessed']

def raw_exit(directory, report, expected):
    raw = read(directory / report['host'])
    return (type(raw['exit_code']) is int and raw['exit_code'] == report['exit_code'] == expected
        and raw['target_pid'] == report['target_pid']
        and report['wrapper_exit_code'] == 0 and report['timed_out'] is False
        and report['tree_verified'] is True and report['ownership'] == 'gated_job_kill_on_close')

checks = {
    'exact_case_inventory': [r['case'] for r in capture['cases']] == expected_cases,
    'aggregate_pass': capture['passed'] is True,
    'same_frozen_runtime': closure == read(SOURCE_PACKAGE / 'source-closure.json')
        and capture['source_closure_sha256'] == closure['source_closure_sha256'] == reference['source_closure_sha256'],
    'driver_frozen_exact': sha(driver) == reference['driver_sha256'] == capture['driver_sha256'],
    'runtime_source_bytes_exact': all(sha(SOURCE_PACKAGE / 'source/studio' / name) == digest
        for name, digest in closure['files'].items()),
    'snapshot_stability': capture['origin_source_unchanged'] is True and capture['snapshot_unchanged'] is True,
}
rows = []
for item in capture['cases']:
    case = item['case']
    output = PACKAGE / case
    result = read(output / 'result.json')
    original = read(output / 'original-host.json')
    logs = scanner.audit_logs([output])
    editor = read(output / 'editor-close.json')
    local = {
        'functional_checks_pass': result['ok'] is True and len(result['checks']) >= 20
            and all(r['passed'] is True for r in result['checks']),
        'case_raw_exit': raw_exit(output, item['host'], 0),
        'publisher_exact_crash_exit': raw_exit(output / 'original', original, scanner.CASES[case][2]),
        'engine_cleanup': editor['actual_process_exit']['exit_code'] == 0 and editor['wrapper_exit_code'] == 0
            and editor['job']['active_count'] == 0 and editor['job']['closed'] is True
            and editor['job']['zero_observed'] is True and editor['job']['handle_retained'] is False,
        'logs_reaudited': logs['clean'] is True,
    }
    rows.append({'case': case, 'passed': all(local.values()), 'checks': local,
        'functional_check_count': len(result['checks']),
        'response_sha256': sha(output / 'response-wire.json'),
        'log_file_count': len(logs['logs']), 'expected_diagnostic_count': sum(
            r['reason'] != 'no_diagnostic' for r in logs['logs'])})
report = {'passed': all(checks.values()) and len(rows) == len(expected_cases) and all(r['passed'] for r in rows),
    'checks': checks, 'cases': rows, 'source_closure_sha256': capture['source_closure_sha256'],
    'driver_sha256': sha(driver), 'candidate_only': True, 'gt03_acceptance': False,
    'scope': 'Actual distinct crash classes only; no inference of unexecuted adjacent cases or acceptance.',
    'no_native_process_launched': True}
(HERE / 'matrix-completion-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['passed'] else 1)
