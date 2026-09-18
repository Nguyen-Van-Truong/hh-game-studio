"""Verify the finished supplemental retention probe without rerunning Godot."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import statistics
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import verify_capture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    raw = ROOT / 'studio/.local/reviews/gt06-s76-retention-01'
    diagnostic = read(raw / 'diagnostic.json')
    result = read(raw / 'result.json')
    owner = read(BASE / 'retention-owner-01/capture.json')
    host = owner['host']
    assert host['exit_code'] == host['wrapper_exit_code'] == 0
    assert host['tree_verified'] and not host['timed_out'] and owner['source_unchanged']
    assert result['completed_diagnostic'] and result['source_unchanged']
    assert not result['formal_acceptance'] and not result['full_benchmark']
    assert diagnostic['binding']['source_closure_sha256'] == native.closure(diagnostic['source_files'])
    current = read(BASE / 'current-runtime-source.json')
    for name, expected in diagnostic['source_files'].items():
        assert sha(raw / 'source/studio' / name) == expected == current['source_files'][name]
        assert sha(ROOT / 'studio' / name) == expected
    for name, expected in read(BASE / 'retention-owner-01/invocation.json')['source_files'].items():
        assert sha(BASE / 'retention-owner-01' / name) == expected == sha(BASE / name)
    capture = read(raw / 'editor-host/capture.json')
    runtime = read(raw / 'runtime-source-files.json')
    verify_capture(raw / 'editor-host', sha(raw / 'editor-host/capture.json'),
                   source_root=ROOT / 'studio', expected_source_files=runtime,
                   expected_binary_sha256=capture['binary_sha256'])
    native.native_job.verify_captured_stage(raw / 'import-host', sha(raw / 'import-host/capture.json'))
    assert result['actual_process_exit'] == capture['actual_process_exit']
    assert result['job'] == capture['job']
    index = read(raw / 'project/benchmark/out/index.json')
    assert index['completed'] and not index['benchmark_complete'] and not index['host_integrated']
    assert index['input'] == diagnostic['binding']
    assert index['batches_completed'] == 8 and index['cycles_per_batch'] == 100
    assert index['pid'] == capture['actual_process_exit']['pid']
    for name, expected in index['source_files'].items():
        assert sha(raw / 'project' / name.removeprefix('res://')) == expected
    rows, durations = [], []
    previous = None
    for label in [f'batch-{i:02d}' for i in range(8)] + ['idle']:
        point = read(raw / 'points' / (label + '.json'))
        handles = read(raw / 'handles' / (label + '.json'))
        assert sha(raw / 'handles' / (label + '.json')) == result['points'][label]
        assert point['pid'] == handles['identity']['pid'] == index['pid']
        assert handles['capture_flags'] == 0x3c and handles['snapshot_and_marker_freed']
        counts = Counter(item['type'] or '<unavailable>' for item in handles['entries'])
        assert dict(counts) == handles['type_counts']
        assert sum(counts.values()) == handles['handles_captured']
        if previous:
            assert point['mono_us'] > previous['mono_us'] and point['frames'] > previous['frames']
        rows.append({**point, 'held_handles': handles['before_handle_count'],
                     'type_counts': dict(counts), 'type_delta': {
                         key: counts[key] - previous['type_counts'].get(key, 0)
                         for key in sorted(set(counts) | set(previous['type_counts']))
                         if counts[key] != previous['type_counts'].get(key, 0)} if previous else {}})
        previous = rows[-1]
    for i, reference in enumerate(index['batches']):
        path = raw / 'project/benchmark/out' / reference['file']
        assert sha(path) == reference['sha256'] and path.stat().st_size == reference['size_bytes']
        batch = read(path)
        assert batch['index'] == i and batch['pid'] == index['pid']
        assert batch['run_id'] == diagnostic['run_id'] and batch['mode'] == 'diagnostic'
        assert batch['dropped_commands'] == batch['dropped_telemetry'] == 0
        assert len(batch['cycles']) == len(batch['raw_timings']) == 100
        for j, (cycle, timing) in enumerate(zip(batch['cycles'], batch['raw_timings'])):
            assert cycle['index'] == j and cycle['effects'] == dict.fromkeys(('create','undo','save','reload'), 1)
            assert cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256'] == index['baseline_revision'].removeprefix('sha256:')
            assert cycle['root_before'] != cycle['root_after'] and cycle['main_thread']
            native.validate_cycle_timing(timing, cycle, batch['memory'], batch)
        for counter in ('objects', 'resources'):
            assert batch['memory']['editor'][counter]['value'] == rows[i][counter]
        durations.append((batch['ended_mono_us'] - batch['started_mono_us']) / 1_000_000)
    for lane in ('import-host', 'editor-host'):
        assert not (raw / lane / 'stderr.txt').read_bytes().strip()
        assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED', (raw / lane / 'stdout.txt').read_bytes())
    copied = BASE / 'retention-evidence'
    manifest = []
    for path in sorted(raw.rglob('*')):
        if not path.is_file() or '.godot' in path.parts:
            continue
        relative = path.relative_to(raw)
        content = path.read_bytes()
        target = copied / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == content
        else:
            target.write_bytes(content)
        manifest.append({'file': relative.as_posix(), 'bytes': len(content), 'sha256': sha(path)})
    report = {'verified': True, 'formal_acceptance': False, 'full_benchmark': False,
              'native_cycles': 800, 'point_count': 9, 'native_exit': result['actual_process_exit'],
              'owner': host, 'source_count': len(diagnostic['source_files']),
              'source_closure': diagnostic['binding']['source_closure_sha256'],
              'campaign_source_closure': current['closure_sha256'],
              'source_is_matching_subset_not_exact_campaign': True,
              'median_batch_seconds': statistics.median(durations), 'batch_seconds': durations,
              'max_native_status_gap_ms': index['max_status_gap_ms'], 'rows': rows,
              'limitations': ['Native only, no 1000 HTTP command mix or full campaign.',
                              'PSS numeric handle slots can be reused; type deltas do not identify object lifetimes.',
                              'No RSS claim; unavailable PSS types remain unclassified.',
                              'Post-warmup stability in three diagnostic batches does not establish full benchmark acceptance.'],
              'exact_copies': manifest, 'owner_capture_sha256': sha(BASE / 'retention-owner-01/capture.json')}
    (BASE / 'retention-analysis.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key,value in report.items() if key not in ('rows','exact_copies','owner','limitations')}))


if __name__ == '__main__':
    main()
