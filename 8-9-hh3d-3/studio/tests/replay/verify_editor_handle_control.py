"""Offline O6.5 editor-handle analysis; no engine, writes, or acceptance.

The complete control JSONL array is split at floor(i*N/35), i=0..35.
Each contiguous window differs in size by at most one and contributes its last
row. No startup/shutdown row is trimmed. Baseline uses windows 2..4; measured
windows 5..34 use the current profile's editor gate and supplemental trend.
Formal inputs use the 35 hash-bound joint observations in their existing
assembly manifest. Applying current rules never changes a historical verdict.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import statistics
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from studio.tests.replay import benchmark_profile as profile

WINDOW_COUNT = 35
MAX_INPUT_BYTES = 16 * 1024 * 1024
WINDOW_ALGORITHM = 'floor boundaries: [floor(i*N/35), floor((i+1)*N/35)); select end-1'


class HandleControlError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(value, code):
    if not value:
        raise HandleControlError(code)


def _integer(value, *, low=0):
    _need(type(value) is int and low <= value <= profile.SAFE_INTEGER, 'INTEGER')
    return value


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, 'DUPLICATE_KEY')
            result[key] = value
        return result

    def bad(_):
        raise HandleControlError('NONFINITE_JSON')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise HandleControlError('INVALID_JSON') from error


def _read(path):
    path = Path(path)
    _need(path.is_file() and not path.is_symlink(), 'INPUT_FILE')
    _need(0 < path.stat().st_size <= MAX_INPUT_BYTES, 'INPUT_SIZE')
    raw = path.read_bytes()
    _need(0 < len(raw) <= MAX_INPUT_BYTES, 'INPUT_SIZE')
    return raw, {'path': path.resolve().as_posix(), 'size_bytes': len(raw),
                 'sha256': hashlib.sha256(raw).hexdigest()}


def evaluate_series(values):
    """Return only the current handle rule's diagnostic result for 35 values."""
    _need(type(values) is list and len(values) == WINDOW_COUNT, 'SERIES_COUNT')
    for value in values:
        _integer(value)
    baseline_values = values[2:5]
    baseline = int(statistics.median(baseline_values))
    measured = values[5:35]
    codes = profile.editor_handle_gate_codes(baseline, measured)
    trend = profile.retained_handle_trend_code('editor', 'held_handles', measured)
    if trend is not None:
        codes.append(trend)
    early, late = measured[:15], measured[15:]
    return {
        'authority': 0, 'formal_acceptance': False,
        'scope': 'editor held_handles only; historical verdict unchanged',
        'diagnostic_result': 'FAIL' if codes else 'PASS', 'codes': codes,
        'baseline_window_indices': [2, 3, 4], 'baseline_values': baseline_values,
        'baseline': baseline, 'measured_window_indices': list(range(5, 35)),
        'early_median': statistics.median(early), 'late_median': statistics.median(late),
        'measured_max': max(measured),
        'growth_limit': baseline + profile.PROFILE.editor_handles_tolerance,
        'late_median_limit': statistics.median(early) + profile.PROFILE.editor_handles_trend,
        'values': list(values),
    }


def analyze_control(path, *, package_manifest=None):
    raw, binding = _read(path)
    lines = raw.splitlines()
    _need(len(lines) >= WINDOW_COUNT and all(line.strip() for line in lines), 'CONTROL_SAMPLE_COUNT')
    rows = [_json(line) for line in lines]
    previous_host = previous_handle = 0
    for row in rows:
        _need(type(row) is dict and 'held_handles' in row, 'CONTROL_SAMPLE')
        _integer(row['held_handles'])
        host = _integer(row.get('host_mono_us'), low=1)
        handle = _integer(row.get('handle_mono_us'), low=1)
        _need(previous_host < host <= handle and previous_handle < handle, 'CONTROL_CLOCK_ORDER')
        previous_host, previous_handle = host, handle
    n = len(rows)
    windows = []
    for index in range(WINDOW_COUNT):
        start, end = index * n // WINDOW_COUNT, (index + 1) * n // WINDOW_COUNT
        row = rows[end - 1]
        windows.append({'index': index, 'start_row_inclusive': start,
                        'end_row_exclusive': end, 'selected_row_index': end - 1,
                        'host_mono_us': row['host_mono_us'],
                        'handle_mono_us': row['handle_mono_us'], 'held_handles': row['held_handles']})
    result = evaluate_series([window['held_handles'] for window in windows])
    result.update(input=binding, sample_count=n, trimmed_samples=0,
                  window_algorithm=WINDOW_ALGORITHM, windows=windows,
                  full_raw_min=min(row['held_handles'] for row in rows),
                  full_raw_max=max(row['held_handles'] for row in rows))
    if package_manifest is not None:
        manifest_raw, manifest_binding = _read(package_manifest)
        manifest = _json(manifest_raw)
        _need(type(manifest) is dict and type(manifest.get('members')) is list, 'CONTROL_MANIFEST')
        refs = [ref for ref in manifest['members'] if ref.get('path') == Path(path).name]
        _need(len(refs) == 1 and refs[0]['sha256'] == binding['sha256']
              and refs[0]['size_bytes'] == binding['size_bytes'], 'CONTROL_MANIFEST_BINDING')
        result['package_manifest'] = manifest_binding
    return result


def analyze_formal(manifest_path):
    raw, binding = _read(manifest_path)
    manifest = _json(raw)
    _need(type(manifest) is dict and type(manifest.get('joint_observations')) is list
          and len(manifest['joint_observations']) == WINDOW_COUNT, 'FORMAL_MANIFEST')
    root = Path(manifest_path).resolve().parent
    values, inputs = [], []
    for index, ref in enumerate(manifest['joint_observations']):
        _need(type(ref) is dict and set(ref) == {'file', 'sha256', 'size_bytes'}, 'FORMAL_REFERENCE')
        name = ref['file']
        _need(type(name) is str and '\\' not in name, 'FORMAL_PATH')
        relative = PurePosixPath(name)
        _need(not relative.is_absolute() and relative.as_posix() == name
              and all(part not in ('.', '..') for part in relative.parts), 'FORMAL_PATH')
        path = root.joinpath(*relative.parts)
        _need(all(not item.is_symlink() for item in (path, *path.parents[:len(relative.parts)])), 'FORMAL_PATH')
        row_raw, row_binding = _read(path)
        _need(row_binding['sha256'] == ref['sha256'] and row_binding['size_bytes'] == ref['size_bytes'],
              'FORMAL_HASH_BINDING')
        row = _json(row_raw)
        _need(type(row) is dict and type(row.get('index')) is int and row['index'] == index
              and row.get('run_id') == manifest.get('run_id')
              and row.get('schema_id') == 'hh-studio.benchmark-joint-observation'
              and row.get('phase') == profile.PROFILE.quiescent_phase
              and row.get('processes') == manifest.get('processes')
              and row.get('profile_sha256') == manifest.get('profile_sha256')
              and row.get('source_closure_sha256') == manifest.get('source_closure_sha256'), 'FORMAL_OBSERVATION')
        editor = row.get('editor')
        _need(type(editor) is dict, 'FORMAL_COUNTER')
        counter = editor.get('held_handles')
        _need(type(counter) is dict and set(counter) == {'value', 'unavailable_reason'}
              and counter['unavailable_reason'] is None, 'FORMAL_COUNTER')
        values.append(_integer(counter['value']))
        inputs.append(row_binding)
    result = evaluate_series(values)
    result.update(input_manifest=binding, observations=inputs,
                  run_id=manifest['run_id'], historical_profile_sha256=manifest['profile_sha256'],
                  historical_source_closure_sha256=manifest['source_closure_sha256'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-samples', type=Path, required=True)
    parser.add_argument('--control-package-manifest', type=Path)
    parser.add_argument('--formal-manifest', type=Path)
    args = parser.parse_args(argv)
    try:
        results = {'control': analyze_control(args.control_samples,
                    package_manifest=args.control_package_manifest)}
        if args.formal_manifest is not None:
            results['formal_reference'] = analyze_formal(args.formal_manifest)
        result = {
            'schema_id': 'hh-studio.editor-handle-offline-control', 'schema_version': '1.0.0',
            'authority': 0, 'formal_acceptance': False,
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'profile_sha256': profile.PROFILE_SHA256,
            'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'results': results,
        }
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 1 if any(item['diagnostic_result'] == 'FAIL' for item in results.values()) else 0
    except (HandleControlError, OSError) as error:
        print(json.dumps({'authority': 0, 'formal_acceptance': False, 'diagnostic_result': 'GAP',
                          'code': getattr(error, 'code', 'INPUT_IO')}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
