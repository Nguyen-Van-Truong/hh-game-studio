"""Compare supplemental PSS arms without promoting incomplete ownership proof."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import statistics

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def arm(name, owner):
    root = RAW / ('gt06-s76-handles-' + name + '-01')
    source = json.loads((root / 'diagnostic.json').read_bytes())
    refs = {'diagnostic.json': sha(root / 'diagnostic.json')}
    rows = []
    previous = None
    for label in [f'batch-{i:02d}' for i in range(6)] + ['idle']:
        point_path, handles_path = root / 'points' / (label + '.json'), root / 'handles' / (label + '.json')
        if not point_path.exists() or not handles_path.exists():
            continue
        point, handles = json.loads(point_path.read_bytes()), json.loads(handles_path.read_bytes())
        assert point['label'] == label and point['pid'] == handles['identity']['pid']
        assert handles['capture_flags'] == 0x3c and handles['snapshot_and_marker_freed'] is True
        counts = Counter(item['type'] or '<unavailable>' for item in handles['entries'])
        assert dict(counts) == handles['type_counts'] and sum(counts.values()) == handles['handles_captured']
        if previous:
            assert point['mono_us'] > previous['mono_us'] and point['frames'] > previous['frames']
        refs[point_path.relative_to(root).as_posix()] = sha(point_path)
        refs[handles_path.relative_to(root).as_posix()] = sha(handles_path)
        rows.append({**point, 'handles_before': handles['before_handle_count'],
                     'handles_after': handles['after_handle_count'], 'captured': handles['handles_captured'],
                     'type_counts': handles['type_counts'], 'capture_ms': handles['duration_ms'],
                     'since_previous_ms': (point['mono_us'] - previous['mono_us']) / 1000 if previous else None,
                     'type_delta': {key: counts[key] - previous['type_counts'].get(key, 0)
                                    for key in sorted(set(counts) | set(previous['type_counts']))
                                    if counts[key] != previous['type_counts'].get(key, 0)} if previous else {}})
        previous = rows[-1]
    assert [row['label'] for row in rows[:6]] == [f'batch-{i:02d}' for i in range(6)]
    completed = False
    if (root / 'result.json').exists() and (BASE / owner / 'capture.json').exists():
        result = json.loads((root / 'result.json').read_bytes())
        outer = json.loads((BASE / owner / 'capture.json').read_bytes())
        host = outer['host']
        assert result['completed_diagnostic'] is True and result['formal_acceptance'] is False
        assert result['actual_process_exit']['exit_code'] == 0 and result['source_unchanged'] is True
        assert result['job']['zero_observed'] is True and result['job']['closed'] is True
        assert host['exit_code'] == host['wrapper_exit_code'] == 0
        assert host['tree_verified'] is True and host['timed_out'] is False and outer['source_unchanged'] is True
        assert len(rows) == 7
        for label, digest in result['points'].items():
            assert refs['handles/' + label + '.json'] == digest
        refs['result.json'] = sha(root / 'result.json')
        completed = True
    return {'arm': name, 'source_closure': source['binding']['source_closure_sha256'],
            'source_files': source['source_files'], 'profile_sha256': source['binding']['profile_sha256'],
            'completed_diagnostic': completed, 'rows': rows,
            'median_50_cycle_interval_ms': statistics.median(row['since_previous_ms'] for row in rows[1:6]),
            'references': refs, 'owner_capture_sha256': sha(BASE / owner / 'capture.json') if completed else None}


if __name__ == '__main__':
    stock, responsive = arm('stock', 'stock-owner-02'), arm('responsive', 'responsive-owner-01')
    assert stock['source_files'] == responsive['source_files']
    assert stock['profile_sha256'] == responsive['profile_sha256']
    result = {'schema_version': 1, 'formal_acceptance': False, 'full_benchmark': False,
              'paired_diagnostic_completed': stock['completed_diagnostic'] and responsive['completed_diagnostic'],
              'stock_interruption_sha256': sha(BASE / 'stock-interruption.json'),
              'limitations': ['Stock interrupted before idle/exit; six captured batches are supplemental timing observations only.',
                             'PSS is observational and adds overhead; this is not the 1000 HTTP plus 100 native campaign.',
                             'Numeric handle slots can be reused; type deltas do not prove object identity or leak causation.',
                             'Unavailable PSS entry types remain unclassified; no threshold or failed sample is waived.'],
              'stock': stock, 'responsive': responsive,
              'observed_interval_ratio': stock['median_50_cycle_interval_ms'] / responsive['median_50_cycle_interval_ms']}
    output = BASE / 'comparison.json'
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key not in ('stock', 'responsive')}))
