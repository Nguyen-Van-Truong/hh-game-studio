"""Verify S76 scoped diagnostic evidence; never an acceptance/tick operation."""
from pathlib import Path
import hashlib
import json
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
REPO = ROOT.parent


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(host):
    assert type(host['exit_code']) is int and host['exit_code'] == 0
    assert host['wrapper_exit_code'] == 0 and host['tree_verified'] is True
    assert host['timed_out'] is False


def main():
    current = read(BASE / 'current-runtime-source.json')
    assert len(current['source_files']) == 49
    for relative, expected in current['source_files'].items():
        assert digest(STUDIO / relative) == expected
        git_path = (STUDIO / relative).relative_to(REPO).as_posix()
        raw = subprocess.check_output(['git', 'show', 'HEAD:' + git_path], cwd=REPO)
        assert hashlib.sha256(raw).hexdigest() == expected
    computed = hashlib.sha256(b''.join((name + '\0' + sha + '\n').encode()
                                      for name, sha in sorted(current['source_files'].items()))).hexdigest()
    assert computed == current['closure_sha256']
    manifest = read(BASE / 'native-evidence/manifest.json')
    for row in manifest['files']:
        copy = BASE / 'native-evidence' / row['run_id'] / row['file']
        raw = STUDIO / '.local/reviews' / row['run_id'] / row['file']
        assert copy.stat().st_size == raw.stat().st_size == row['bytes']
        assert digest(copy) == digest(raw) == row['sha256']
    unit = read(BASE / 'cadence-units-01/capture.json')
    clean(unit['host'])
    assert unit['source_unchanged'] is True
    prefix = 'CADENCE_UNITS_COMPLETE '
    lines = (BASE / 'cadence-units-01/units-stdout.txt').read_text().splitlines()
    summaries = [json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
    assert summaries == [{'run': 57, 'failures': 0, 'errors': 0, 'skips': 0}]
    clean(read(BASE / 'cadence-native-owner-01/capture.json'))
    native = BASE / 'native-evidence/gt06-s76-cadence-native-01'
    capture = read(native / 'capture.json')
    for stage in ('import', 'editor'):
        assert capture['actual_exits'][stage]['exit_code'] == 0
        assert capture['jobs'][stage]['zero_observed'] and capture['jobs'][stage]['closed']
    cadence = read(BASE / 'cadence-readback.json')
    assert cadence['verified'] is True and cadence['capture_sha256'] == digest(native / 'capture.json')
    assert cadence['event']['os_low_processor_usage_mode_sleep_usec'] == 6900
    for variant in ('old-key', 'slow', 'float', 'bool', 'missing'):
        row = read(BASE / ('cadence-guard-verification-' + variant + '.json'))
        root = BASE / 'native-evidence' / ('gt06-s76-cadence-' + variant + '-01')
        assert row['guard_rejected'] and row['scene_unchanged'] and row['no_batch']
        assert row['actual_exit']['exit_code'] == row['wrapper_exit'] == 86
        assert row['job']['zero_observed'] and row['job']['closed'] and not row['job']['handle_retained']
        assert row['capture_sha256'] == digest(root / 'editor-host/capture.json')
        assert read(root / 'editor-host/process-exit.json') == row['actual_exit']
        assert row['failure_marker']['code'] == 'BENCHMARK_EDITOR_CADENCE'
    comparison = read(BASE / 'comparison.json')
    assert comparison['formal_acceptance'] is False and comparison['paired_diagnostic_completed'] is False
    assert comparison['stock']['completed_diagnostic'] is False
    assert comparison['responsive']['completed_diagnostic'] is True
    assert not (BASE / 'native-evidence/gt06-s76-handles-stock-01/result.json').exists()
    clean(read(BASE / 'responsive-owner-01/capture.json')['host'])
    clean(read(BASE / 'http-owner-01/capture.json'))
    http = read(BASE / 'http-attribution-01/report.json')
    assert http['completed'] is True and http['host_closed'] is True and not http['failures']
    assert http['summary']['terminal_samples'] == 30
    assert http['source_sha256_before'] == http['source_sha256_after']
    history = ROOT / 'zdoc/reviews/20260918-plan-history-s75/tools-plan-s75.txt'
    assert digest(history) == 'fc338e3651a406d09dffd3199b9bc49acc1dad9c5445f233babff25fb5af6a0e'
    print(json.dumps({'verified': True, 'formal_acceptance': False,
                      'source_files_matching_git': 49, 'native_exact_copies': len(manifest['files']),
                      'units': 57, 'negative_guards': 5, 'http_commands': 30,
                      'stock_interruption_preserved': True, 'full_campaign_pass': False}))


if __name__ == '__main__':
    main()
