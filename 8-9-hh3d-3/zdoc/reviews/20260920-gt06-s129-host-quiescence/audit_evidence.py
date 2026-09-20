"""Offline consistency checks for this diagnostic only; no host or engine."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


audit = {'formal_acceptance': False, 'runs': []}
frozen = read(HERE / 'source-snapshot.json')
for name in ('run-01', 'run-02'):
    folder = HERE / name
    result, supervisor = read(folder / 'result.json'), read(folder / 'supervisor.json')
    before, after = read(folder / 'source-before.json'), read(folder / 'source-after.json')
    assert before == after
    assert digest(folder / 'source-before.json') == result['source_before_sha256']
    assert digest(folder / 'source-after.json') == result['source_after_sha256']
    assert supervisor['actual_exit_code'] == 0 and supervisor['exit_kind'] == 'NATURAL_WAIT_RETURN'
    assert supervisor['child_pid'] == result['pid'] and supervisor['child_reaped']
    assert supervisor['elapsed_seconds'] < 60
    assert digest(folder / 'stdout.txt') == supervisor['stdout_sha256']
    assert digest(folder / 'stderr.txt') == supervisor['stderr_sha256']
    assert (folder / 'stderr.txt').stat().st_size == 0
    executing = folder / 'host_quiescence.execution.py' if name == 'run-01' else HERE / 'host_quiescence.py'
    assert digest(executing) == supervisor['script_sha256']
    for source, expected in before.items():
        actual = executing if source.endswith('host_quiescence.py') else HERE / frozen[source]['artifact']
        assert digest(actual) == expected
    active, entered, returned = set(), set(), set()
    prior = 0
    for event in result['request_events']:
        seq = event['seq']
        assert event['mono_ns'] >= prior
        prior = event['mono_ns']
        assert type(event['fd']) is int and event['fd'] >= 0
        if event['kind'] == 'process_request_start':
            assert seq not in active
            active.add(seq)
        elif event['kind'] == 'process_request_thread_enter':
            assert seq in active and seq not in entered
            entered.add(seq)
        elif event['kind'] == 'process_request_thread_return':
            assert seq in active and seq in entered and seq not in returned
            assert event['fd_after'] == -1 and event['outcome'] == 'returned'
            active.remove(seq)
            returned.add(seq)
        else:
            raise AssertionError('Unexpected synchronous rejection in this small workload')
        assert len(active) == event['active_count']
    assert not active and entered == returned
    assert result['active_requests_final'] == result['fixed_threads_alive_final'] == 0
    assert result['own_client_socket_closed'] and result['extra_threads_final'] == []
    assert len(result['batches']) == 3
    for index, batch in enumerate(result['batches']):
        assert batch['status'] == 'DIAGNOSTIC' and batch['mode'] == 'diagnostic'
        assert batch['commands_by_kind'] == {'admitted': 2, 'inspect': 5, 'rejected': 3}
        assert batch['effect_count_before'] == index * 2 and batch['effect_count_after'] == index * 2 + 2
        assert batch['cancel_status'] == 'CANCELED' and batch['cancel_no_effect']
        assert batch['producer_observation_kind'] == 'synthetic_test_observer'
        assert batch['producer_held_handles_SYNTHETIC'] == 10
        assert not batch['complete_command_mix']
    partial = next(row for row in result['samples'] if row['label'] == 'partial_close_returned_client_open')
    assert partial['active_count'] == partial['request_threads_alive'] == 1
    assert partial['fixed_host_threads_alive'] == 0
    final_seq = max(returned)
    final_return = next(row for row in result['request_events']
                        if row['kind'] == 'process_request_thread_return' and row['seq'] == final_seq)
    assert final_return['mono_ns'] > partial['mono_ns']
    audit['runs'].append({'name': name, 'source_hashes_match': True, 'actual_exit_code': 0,
        'supervisor_elapsed_seconds': supervisor['elapsed_seconds'], 'request_lifecycles_complete': len(returned),
        'close_return_precedes_partial_request_return_ms': (final_return['mono_ns'] - partial['mono_ns']) / 1_000_000,
        'counter_interpretation': 'CONTAMINATED_BY_RETAINED_THREAD_OBJECTS' if name == 'run-01' else 'NUMERIC_ONLY_RECORDER'})

(HERE / 'audit.json').write_text(json.dumps(audit, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(audit))
