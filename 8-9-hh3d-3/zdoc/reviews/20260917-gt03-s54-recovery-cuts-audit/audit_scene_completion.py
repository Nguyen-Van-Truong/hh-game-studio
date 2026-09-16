"""Read-only completion audit; preserves the original log-classification failure."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / '20260917-gt03-s54-recovery-cuts-02'
CASE = PACKAGE / 'scene-cas'
SCANNER = HERE / 'log-scanner-source.py'
spec = importlib.util.spec_from_file_location('cut_completion_scanner', SCANNER)
scanner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scanner
spec.loader.exec_module(scanner)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
load = lambda path: json.loads(path.read_bytes())
capture = load(PACKAGE / 'capture.json')
result = load(CASE / 'result.json')
row = capture['cases'][0]
raw_host = load(CASE / row['host']['host'])
publisher = load(CASE / 'original-host.json')
raw_publisher = load(CASE / 'original' / publisher['host'])
frozen = load(PACKAGE / 'source-closure.json')
log_audit = scanner.audit_logs([CASE])
checks = {
    'original_capture_false_preserved': capture['passed'] is False and row['native_logs_clean'] is False,
    'functional_result_exactly_21_clean_checks': result['ok'] is True and len(result['checks']) == 21
        and all(r['passed'] is True for r in result['checks']),
    'raw_case_exit_and_pid_match': raw_host['exit_code'] == row['host']['exit_code'] == 0
        and raw_host['target_pid'] == row['host']['target_pid']
        and row['host']['wrapper_exit_code'] == 0 and row['host']['tree_verified'] is True
        and row['host']['timed_out'] is False,
    'raw_publisher_exit_and_pid_match': raw_publisher['exit_code'] == publisher['exit_code'] == 93
        and raw_publisher['target_pid'] == publisher['target_pid']
        and publisher['wrapper_exit_code'] == 0 and publisher['tree_verified'] is True
        and publisher['timed_out'] is False,
    'frozen_sources_exact': all(sha(PACKAGE / 'source/studio' / name) == digest
        for name, digest in frozen['files'].items()),
    'original_source_stability_proved_by_run': capture['origin_source_unchanged'] is True
        and capture['snapshot_unchanged'] is True,
    'typed_log_evidence_clean': log_audit['clean'] is True,
}
report = {'passed': all(checks.values()), 'checks': checks, 'package': PACKAGE.name,
    'source_closure_sha256': frozen['source_closure_sha256'], 'candidate_only': True,
    'gt03_acceptance': False, 'no_native_process_launched': True,
    'raw_capture_sha256': sha(PACKAGE / 'capture.json'), 'raw_result_sha256': sha(CASE / 'result.json'),
    'scanner_sha256': sha(SCANNER), 'log_audit': log_audit,
    'scope': 'Reclassifies only empty Docker State.Error and exact owned-container absence probes using native host reports, IDs, removal results and Job cleanup. Original aggregate false remains unchanged.'}
(HERE / 'scene-cas-completion-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'passed': report['passed'], 'checks': checks,
    'typed_diagnostics': sum(r['reason'] != 'no_diagnostic' for r in log_audit['logs'])}, indent=2))
raise SystemExit(0 if report['passed'] else 1)
