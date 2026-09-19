"""Compile/delegation/overhead preparation only. No HTTP, engine or Journal I/O."""
from pathlib import Path
import hashlib
import json
import sys
import time
from types import SimpleNamespace

from snapshot_metrics import SnapshotMetrics, instrument_snapshot
from phase_observer import PhaseRecorder

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
calls = []
failure = RuntimeError('sentinel')


class Stream:
    def read(self, size):
        calls.append(('read', size))
        return b'abc'


class Digest:
    fail = False

    def update(self, value):
        calls.append(('hash', len(value)))
        if self.fail:
            raise failure


def fake_fsync(fd):
    calls.append(('fsync', fd))


os = SimpleNamespace(fsync=fake_fsync)


class Fake:
    def __init__(self):
        self.stream, self.digest, self.fd = Stream(), Digest(), 123

    def _snapshot(self, *, synchronize):
        stream, digest = self.stream, self.digest
        value = stream.read(17)
        digest.update(value)
        if synchronize:
            os.fsync(self.fd)
        return value


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def main():
    helpers = ('probe.py', 'run_probe.py', 'phase_observer.py', 'snapshot_metrics.py')
    for name in (*helpers, 'selfcheck.py'):
        compile((BASE / name).read_bytes(), str(BASE / name), 'exec')
    observed = SnapshotMetrics()
    transformed = instrument_snapshot(Fake._snapshot, observed)
    value = observed.run(transformed, Fake(), synchronize=True)
    assert value == b'abc' and calls == [('read', 17), ('hash', 3), ('fsync', 123)]
    calls.clear()
    obj = Fake()
    obj.digest.fail = True
    caught = None
    try:
        observed.run(transformed, obj, synchronize=True)
    except RuntimeError as error:
        caught = error
    assert caught is failure and calls == [('read', 17), ('hash', 3)]
    assert observed.snapshot()['unfinished'] == []
    assert observed.snapshot()['rows']['initialize']['snapshots']['returned'] == 1
    calls.clear()
    observed.run(transformed, Fake(), synchronize=False)
    assert calls == [('read', 17), ('hash', 3)]
    recorder = PhaseRecorder(event_capacity=16)
    with recorder.span('client.call', route='lookup') as call_id:
        recorder.capture_failure(call_id, route='lookup')
    retained = recorder.snapshot()['first_failure']
    assert retained['failed_call_id'] == call_id and len(retained['unfinished']) == 1

    # Bounded fake-operation overhead only, not a runtime latency calibration.
    loops = 2000
    obj = Fake()
    start = time.perf_counter_ns()
    for _ in range(loops):
        obj._snapshot(synchronize=True)
        calls.clear()
    plain_ns = time.perf_counter_ns() - start
    start = time.perf_counter_ns()
    for _ in range(loops):
        observed.run(transformed, obj, synchronize=True)
        calls.clear()
    wrapped_ns = time.perf_counter_ns() - start

    # Imports collect source only. No fixture creation, Journal or worker starts.
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_benchmark_campaign as campaign
    campaign.load_fixture()
    source_files = campaign.source_files()
    assert len(source_files) == 51
    from studio.host.replay.verified_journal import VerifiedJournal
    actual_metrics = SnapshotMetrics()
    instrument_snapshot(VerifiedJournal._snapshot, actual_metrics)
    history = ROOT / 'studio/.local/reviews/gt06-s98-campaign-01/run-00-attempt-01/commands/commands.jsonl'
    prepared = {'schema': 'HH-S100-HTTP-PREPARED-1', 'formal_acceptance': False,
        'eligible_for_dataset': False, 'engine_runs': 0, 'http_runs': 0,
        'helpers': {name: sha(BASE / name) for name in helpers},
        'selfcheck_sha256': sha(Path(__file__)), 'current_studio_source_files': source_files,
        'current_source_closure_sha256': campaign.closure(source_files),
        'history_sha256': sha(history), 'history_bytes': history.stat().st_size,
        'history_kind': 'Exact S98 postterminal journal; not pre-failure batch17 snapshot',
        'actual_snapshot_ast_proof': actual_metrics.proof,
        'runner_sha256': sha(ROOT / 'studio/build/bootstrap/run_fixture.py'),
        'python_sha256': sha(Path(sys.executable))}
    write(BASE / 'prepared-manifest.json', prepared)
    write(BASE / 'selfcheck-01.json', {'schema': 'HH-S100-HTTP-SELFCHECK-1',
        'status': 'PASS', 'scope': 'compile, exact AST stripping, fake call/return/exception/order, first failure retention; no HTTP/engine/Journal construction',
        'formal_acceptance': False, 'loops': loops, 'plain_fake_total_ns': plain_ns,
        'wrapped_fake_total_ns': wrapped_ns, 'extra_ns_per_fake_snapshot': (wrapped_ns-plain_ns)/loops,
        'overhead_limit': 'fake same-thread operations only; does not establish I/O/thread contention overhead or permit subtraction',
        'actual_snapshot_ast_proof': actual_metrics.proof,
        'prepared_manifest_sha256': sha(BASE / 'prepared-manifest.json')})
    print(json.dumps({'status': 'PASS', 'engine_runs': 0, 'http_runs': 0,
        'source_count': len(source_files), 'source_closure': campaign.closure(source_files),
        'prepared_manifest_sha256': sha(BASE / 'prepared-manifest.json'),
        'extra_ns_per_fake_snapshot': (wrapped_ns-plain_ns)/loops}, sort_keys=True))


if __name__ == '__main__':
    main()
