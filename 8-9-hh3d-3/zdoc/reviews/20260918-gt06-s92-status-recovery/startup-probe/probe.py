"""Supplemental startup timing on a copied S91 journal, no engine or acceptance."""
from pathlib import Path
from contextlib import ExitStack
import hashlib
import json
import shutil
import sys
import time
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    arm = sys.argv[1]
    assert arm in ('baseline', 'repaired')
    source = BASE / (arm + '-source')
    frozen = json.loads((BASE / (arm + '-freeze.json')).read_bytes())['files']
    assert all(sha(source / name) == digest for name, digest in frozen.items())
    sys.path.insert(0, str(source))
    from studio.tests.replay import benchmark_commands as b
    original = ROOT / 'studio/.local/reviews/gt06-s91-sparse-attribution-01/commands/commands.jsonl'
    original_hash = sha(original)
    output = BASE / ('result-' + arm) / 'child'
    output.mkdir()
    spans, phase, producer = [], ['initialize'], None
    actual_journal, actual_host = b.Journal, b.LoopbackFixtureHost

    def journal(path):
        assert path.parent == output / 'commands' and not path.exists()
        shutil.copyfile(original, path)
        assert sha(path) == original_hash
        return actual_journal(path)

    def host(_project, path, journal):
        return actual_host('gt06.s93.startup.' + arm, path, journal)

    def measured(label, method):
        def wrapped(*args, **kwargs):
            start, returned = time.perf_counter_ns(), False
            try:
                result = method(*args, **kwargs)
                returned = True
                return result
            finally:
                assert len(spans) < 256
                spans.append({'phase': phase[0], 'kind': label, 'returned': returned,
                              'started_ns': start, 'ended_ns': time.perf_counter_ns()})
        return wrapped

    report = {'formal_acceptance': False, 'eligible_for_dataset': False, 'engine_runs': 0,
              'arm': arm, 'history_sha256': original_hash, 'history_bytes': original.stat().st_size,
              'scope': 'Two ten-command diagnostics, fresh distinct project on copied history; not restoration of old fixture or reproduction of S91 environmental conditions',
              'spans': spans, 'batches': []}
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(b, 'Journal', journal))
            stack.enter_context(patch.object(b, 'LoopbackFixtureHost', host))
            for name in ('discover', 'lease', 'request', 'submit'):
                stack.enter_context(patch.object(b.FixtureClient, name, measured(name, getattr(b.FixtureClient, name))))
            stack.enter_context(patch.object(b.CommandProducer, '_observe', measured('observe', b.CommandProducer._observe)))
            producer = b.CommandProducer(output / 'commands', 'gt06.s93.' + arm)
            for name in ('issue', 'rotate'):
                stack.enter_context(patch.object(producer.host.sessions, name, measured(name, getattr(producer.host.sessions, name))))
            for index in range(2):
                phase[0] = 'batch-' + str(index)
                row = producer.run_diagnostic()
                write(output / ('command-' + str(index) + '.json'), row)
                setup = [r for r in spans if r['phase'] == phase[0] and r['kind'] in ('discover', 'lease') and r['returned']]
                assert len(setup) == 2
                augmented = sorted(row['host_response_mono_us'] + [r['ended_ns'] // 1000 for r in setup])
                report['batches'].append({'index': index, 'schema_version': row['schema_version'],
                    'original_reported_gap_ms': row['max_status_gap_ms'],
                    'supplemental_gap_including_observed_setup_returns_ms': max(y-x for x,y in zip(augmented, augmented[1:])) / 1000,
                    'setup_spans': setup, 'effect_count_before': row['effect_count_before'],
                    'effect_count_after': row['effect_count_after'], 'commands': len(row['commands'])})
                assert len(row['commands']) == 10 and row['effect_count_after'] == 2*(index+1)
            report['completed'] = True
    finally:
        if producer is not None:
            producer.close()
            report['closed'] = producer.closed
            report['threads_alive'] = [t.is_alive() for t in producer.host._threads] if hasattr(producer.host, '_threads') else None
        report['history_unchanged'] = sha(original) == original_hash
        report['source_unchanged'] = all(sha(source / name) == digest for name, digest in frozen.items())
        loaded = {}
        for name, module in list(sys.modules.items()):
            path = getattr(module, '__file__', None)
            if name.startswith('studio.') and path:
                path = Path(path).resolve()
                relative = path.relative_to(source.resolve()).as_posix()
                assert relative in frozen and sha(path) == frozen[relative]
                loaded[name] = {'path': relative, 'sha256': frozen[relative]}
        report['loaded_modules'] = loaded
        write(output / 'report.json', report)
    assert report['source_unchanged'] and report['history_unchanged'] and report['closed']


if __name__ == '__main__':
    main()
