"""One supplemental HTTP compatibility smoke with an explicitly injected cut.

Uses only a separately pinned, existing frozen HTTP source and a fresh copy of
history. Not an S93 reproduction, performance benchmark or acceptance run.
"""
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import hashlib
import http.client
import json
import shutil
import sys

from phase_observer import (PHASES, PhaseRecorder, observed_client_type,
                            observed_connection_type, observed_host_type,
                            observed_journal_type)


BASE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def need(value):
    if not value:
        raise AssertionError('HTTP_PHASE_SMOKE_POSTCONDITION')


def main():
    run = Path(sys.argv[1]).resolve()
    need(run.parent == BASE and run.name == 'smoke-02')
    freeze = json.loads((run / 'freeze.json').read_text(encoding='utf-8'))
    source = Path(freeze['frozen_source'])
    need(all(sha(source / name) == digest for name, digest in freeze['source_files'].items()))
    need(all(sha(BASE / name) == digest for name, digest in freeze['helpers'].items()))
    need(sha(run / 'history.jsonl') == freeze['history_sha256'])
    sys.path.insert(0, str(source))
    from studio.tests.replay import benchmark_commands as b
    from studio.protocol.core import Status

    recorder = PhaseRecorder(event_capacity=8192)
    journal_type = observed_journal_type(b.Journal, recorder)
    host_type = observed_host_type(b.LoopbackFixtureHost, recorder)
    client_type = observed_client_type(b.FixtureClient, recorder)
    connection_type = observed_connection_type(http.client.HTTPConnection, recorder)
    def journal(path):
        need(path == run / 'commands/commands.jsonl' and not path.exists())
        shutil.copyfile(run / 'history.jsonl', path)
        need(sha(path) == freeze['history_sha256'])
        return journal_type(path)

    def host(_project, path, value):
        return host_type('gt06.s95.http-phases.smoke-02', path, value)

    producer = None
    report = {'schema': 'HH-S95-HTTP-PHASE-SMOKE-1', 'formal_acceptance': False,
              'eligible_for_dataset': False, 'engine_runs': 0, 'completed': False,
              'fault_kind': 'intentionally injected before_dispatch inspect-submit cut, then after_dispatch lookup cut',
              's93_reproduction': False}
    with ExitStack() as stack:
        stack.enter_context(patch.object(b, 'Journal', journal))
        stack.enter_context(patch.object(b, 'LoopbackFixtureHost', host))
        stack.enter_context(patch.object(b, 'FixtureClient', client_type))
        stack.enter_context(patch.object(http.client, 'HTTPConnection', connection_type))
        try:
            producer = b.CommandProducer(run / 'commands', 'gt06.s95.http-phases.smoke-02')
            baseline = producer.run_diagnostic()
            write(run / 'command-00.json', baseline)
            need(len(baseline['commands']) == 10 and baseline['effect_count_after'] == 2
                 and baseline['cancel']['no_effect'] is True)
            before = recorder.snapshot()
            need(before['transport_failures_observed'] == 0)
            command_id = next(row['command_id'] for row in baseline['commands'] if row['kind'] == 'inspect')
            # Explicit smoke-only non-lookup fault, before any inspect admission.
            # This is not asserted to be behavior of the coupled producer.
            request = producer.client.request('gt06.s95.http-phases.smoke-02.injected.inspect')
            producer.host.arm_disconnect('/v1/commands', 'before_dispatch')
            nonlookup = producer.client.submit(request)
            nonlookup_metadata = producer.client.last_transport_failure
            need(nonlookup.status is Status.UNKNOWN and nonlookup_metadata is not None)
            need(recorder.snapshot()['first_failure'] is None)
            producer.host.arm_disconnect('/v1/lookup', 'after_dispatch')
            failed = producer.client.lookup(command_id)
            failure_metadata = producer.client.last_transport_failure
            need(failed.status is Status.UNKNOWN and failed.code == 'CONNECTION_LOST_LOOKUP')
            need(failure_metadata is not None and failure_metadata['stage'] == 'getresponse')
            recovered = producer.client.lookup(command_id)
            need(recovered.status is Status.COMMITTED and producer.client.last_transport_failure is None)
            need(producer.host.fixture.effect_count == 2)
            report.update(completed=True, command_count=10, effects=2,
                          injected_nonlookup_failure=nonlookup_metadata,
                          injected_transport_failure=failure_metadata,
                          recovered_status=recovered.status.value, baseline_transport_failures=0)
        except BaseException as error:
            producer = producer or getattr(error, 'cleanup_owner', None)
            report.update(completed=False, exception_class=type(error).__name__)
        finally:
            if producer is not None:
                try:
                    producer.close()
                except BaseException as error:
                    report['cleanup_exception_class'] = type(error).__name__
                report['closed'] = producer.closed
                report['threads_alive'] = [thread.is_alive() for thread in producer.host._threads] if producer.host else []
                report['sockets_closed'] = (producer.host is not None and
                    producer.host._main.socket.fileno() == -1 and producer.host._control.socket.fileno() == -1)
                report['observer_closed'] = (producer.observer is not None and
                    producer.observer.probe.handle is None and not producer.observer.probe.close_uncertain)
                report['journal_closed'] = (producer.journal is not None and producer.journal._cache_closed
                                            and producer.journal._index_store is None)

    trace = recorder.snapshot()
    write(run / 'phases.json', trace)
    first = trace['first_failure']
    exits = [row for row in trace['events'] if row['phase'] == 'client.call' and row['kind'] == 'exit']
    failed_call = next((row for row in exits if first and row['span_id'] == first['failed_call_id']), None)
    retry = next((row for row in exits if failed_call and row['started_ns'] > failed_call['started_ns']), None)
    pairs = []
    for call in (failed_call, retry):
        handles = []
        if call is not None:
            handles = sorted({row['root_id'] for row in trace['events']
                if row['phase'] == 'server.handle' and row['kind'] == 'bind'
                and (row['server_port'], row['client_port']) == (call['server_port'], call['client_port'])})
        pairs.append({'client_root': None if call is None else call['root_id'],
                      'ports': None if call is None else [call['server_port'], call['client_port']],
                      'server_roots': handles})
    report['injected_retry_correlations'] = pairs
    report['phase_kinds'] = sorted({row['phase'] for row in trace['events']})
    report['trace_complete_for_smoke'] = (
        trace['events_evicted'] == trace['spans_dropped'] == trace['identity_missing'] == 0
        and trace['unfinished'] == [] and trace['transport_failures_observed'] == 2
        and trace['transport_failures_by_route']['commands'] == 1
        and trace['transport_failures_by_route']['lookup'] == 1
        and set(report['phase_kinds']) == PHASES
        and failed_call is not None and retry is not None
        and all(len(pair['server_roots']) == 1 for pair in pairs)
        and pairs[0]['ports'] != pairs[1]['ports']
        and pairs[0]['client_root'] != pairs[1]['client_root'])
    loaded = {}
    for name, module in list(sys.modules.items()):
        if name.startswith('studio.') and getattr(module, '__file__', None):
            path = Path(module.__file__).resolve()
            relative = path.relative_to(source).as_posix()
            loaded[relative] = sha(path)
    report['loaded_source_files'] = loaded
    report['loaded_source_pinned'] = all(freeze['source_files'].get(name) == digest for name, digest in loaded.items())
    report['source_unchanged'] = all(sha(source / name) == digest for name, digest in freeze['source_files'].items())
    report['helpers_unchanged'] = all(sha(BASE / name) == digest for name, digest in freeze['helpers'].items())
    report['history_copy_unchanged'] = sha(run / 'history.jsonl') == freeze['history_sha256']
    write(run / 'report.json', report)
    ok = all(report.get(key) is True for key in ('completed', 'closed', 'sockets_closed',
        'observer_closed', 'journal_closed', 'trace_complete_for_smoke', 'loaded_source_pinned',
        'source_unchanged', 'helpers_unchanged', 'history_copy_unchanged')) and not any(report.get('threads_alive', [True]))
    print(json.dumps({'status': 'PASS' if ok else 'GAP', 'formal_acceptance': False,
                      'injected_disconnect': True, 's93_reproduction': False}), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
