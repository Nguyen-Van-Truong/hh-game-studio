"""Real loopback API timings with explicit in-process mock effects.

CommandProducer owns one unchanged accepted LoopbackFixtureHost/Journal for
up to 35 batches. run_batch(index) sends the exact 5/3/2 mix 100 times.
run_diagnostic() sends one group and never claims benchmark completeness.
Inspection includes terminal readback; admission measures ACCEPTED_PENDING;
validation rejection is the actual INVALID_FIXTURE_PAYLOAD wire response.
Auxiliary discovery, lease, lookup and Cancel calls are outside the 1000 mix.
One delayed mock job is canceled after group 49 through the control listener.
No native effects, engine launches, public cap increases or journal clearing.
Only explicit connection-loss uncertainty during lookup is reconciled by
another lookup of the same ID, within the original five-second terminal budget.
This covers a known uncertainty path; it does not establish the cause of any
older failure whose lookup response was not captured.

Failure retains partial rows on CommandError.report and latches the producer.
Call close() even on failure; uncertain cleanup retains cleanup_owner.
Each returned batch is a separate intermediate artifact, not the combined
benchmark_profile dataset. Persist it before releasing the caller's reference.
"""
from __future__ import annotations

from dataclasses import replace
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
if __name__ == '__main__':
    sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay.verified_journal import VerifiedJournal as Journal
from studio.host.core.transport import FixtureClient, LoopbackFixtureHost, epoch_ms
from studio.host.replay.process_probe import ProcessProbe
from studio.protocol.core import Status, canonical_bytes

MAX_BATCHES = 35
GROUPS = 100
BATCH_TIMEOUT_SECONDS = 600
TERMINAL_TIMEOUT_SECONDS = 5
_SCOPES = frozenset({'fixture.read', 'fixture.write', 'control.cancel'})
_ID = re.compile(r'[a-z][a-z0-9._-]{0,47}\Z')


class CommandError(RuntimeError):
    def __init__(self, code, *, report=None, cleanup_owner=None):
        self.code, self.report, self.cleanup_owner = code, report, cleanup_owner
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise CommandError(code)


def _clock():
    return time.perf_counter_ns()


def _counter(value=None, reason=None):
    return {'value': value, 'unavailable_reason': reason}


class NativeObserver:
    """Retained native PID/start/RSS binding; no fabricated portable fallback."""
    kind = 'native_windows_process_probe'

    def __init__(self):
        self.probe = ProcessProbe(os.getpid(), Path(sys.executable))
        self.identity = {'pid': self.probe.pid, 'process_start': self.probe.process_start}

    def sample(self):
        from ctypes import wintypes as w
        row = self.probe.sample()
        _need(row is not None, 'HOST_PROCESS_EXITED')
        count = w.DWORD()
        api = self.probe.k.GetProcessHandleCount
        api.argtypes, api.restype = [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL
        ok = api(self.probe.handle, ctypes.byref(count))
        return {'process': dict(self.identity), 'monotonic_us': row['host_mono_us'],
                'counters': {'rss_bytes': _counter(row['rss_bytes']),
                    'held_handles': _counter(int(count.value)) if ok else _counter(None, 'GetProcessHandleCount unavailable'),
                    'objects': _counter(None, 'NOT_APPLICABLE_PYTHON_HOST'),
                    'resources': _counter(None, 'NOT_APPLICABLE_PYTHON_HOST')}}

    def close(self):
        self.probe.close()


class CommandProducer:
    """One resident host. observer injection is only for explicitly marked tests."""
    def __init__(self, root, run_id, *, observer=None):
        _need(type(run_id) is str and _ID.fullmatch(run_id), 'RUN_ID')
        self.root, self.run_id = Path(root), run_id
        self.host, self.observer, self.credential, self.client, self.journal = None, observer, None, None, None
        self.next_index, self.failed, self.closed, self.mode = 0, False, False, None
        self.effects, self.revision = 0, 'rev-0'
        self._status_ns = []
        self.root.mkdir(parents=False, exist_ok=False)
        try:
            self.observer = self.observer or NativeObserver()
            _need(self.observer.kind in ('native_windows_process_probe', 'synthetic_test_observer'), 'OBSERVER_KIND')
            self.identity = dict(self.observer.identity)
            _need(self.identity['pid'] == os.getpid(), 'HOST_PROCESS_IDENTITY')
            self.journal = Journal(self.root / 'commands.jsonl')
            self.host = LoopbackFixtureHost('benchmark.commands', self.root, self.journal)
            self.host.start()
            self.initial_memory = self._observe()
        except Exception as error:
            self.failed = True
            try:
                self.close()
            except Exception:
                raise CommandError('START_CLEANUP_HELD', cleanup_owner=self) from error
            raise

    def _observe(self):
        row = self.observer.sample()
        _need(row['process'] == self.identity, 'HOST_PROCESS_CHANGED')
        _need(type(row['counters']['rss_bytes']['value']) is int and row['counters']['rss_bytes']['value'] > 0,
              'HOST_RSS_UNAVAILABLE')
        return row

    def _connect_batch(self):
        # Rotation preserves the live lease owner while invalidating its old
        # bearer. Never erase lease state or receipt/secret history to reuse it.
        if self.credential is not None and self.credential.expires_ms > epoch_ms():
            self.credential = self.host.sessions.rotate(self.credential, ttl_ms=900_000)
        else:
            self.credential = self.host.sessions.issue(scopes=_SCOPES, ttl_ms=900_000)
        self.client = FixtureClient(self.host.port, self.host.control_port, self.credential)
        discovery = self.client.discover()
        _need(discovery.supports('fixture.inspect') and discovery.supports('fixture.set'), 'CATALOG')
        lease = self.client.lease(ttl_ms=900_000)
        _need(lease.revision == self.revision, 'REVISION_DRIFT')
        return lease

    def _received(self):
        now = _clock()
        self._status_ns.append(now)
        # Expected invalid-payload responses are diagnostic events in the
        # accepted host. Check every response so an unexpected event cannot be
        # silently displaced by the next 32 deliberate validation rejections.
        for raw in self.host.diagnostics:
            _need(json.loads(raw) == {'kind': 'log', 'payload': {'code': 'INVALID_FIXTURE_PAYLOAD'}},
                  'HOST_DIAGNOSTICS')
        return now

    def _terminal(self, command_id, request_digest, row, *, started_ns=None):
        deadline = None
        while True:
            started = _clock()
            if deadline is None:
                deadline = started + TERMINAL_TIMEOUT_SECONDS * 1_000_000_000
                if started_ns is None:
                    started_ns = started
            remaining = (deadline - started) / 1_000_000_000
            _need(remaining > 0, 'TERMINAL_TIMEOUT')
            attempt = {'status': None, 'code': None, 'command_id': command_id,
                       'request_digest': None, 'started_mono_us': started // 1000,
                       'ended_mono_us': None}
            row['lookup_attempts'].append(attempt)
            original_timeout = self.client.timeout
            try:
                # Bound this call by the remaining existing budget. The
                # accepted transport and its normal timeout are unchanged.
                self.client.timeout = min(original_timeout, remaining)
                result = self.client.lookup(command_id)
            finally:
                self.client.timeout = original_timeout
            # Persist the actual response before any identity/status/readback
            # guard, including the response that makes a partial batch fail.
            row['terminal_response'] = result.as_dict()
            attempt.update(status=result.status.value, code=result.code,
                           command_id=result.command_id,
                           request_digest=result.postconditions.get('request_digest'),
                           ended_mono_us=_clock() // 1000)
            ended = self._received()
            attempt['ended_mono_us'] = ended // 1000
            row['terminal_mono_us'] = ended // 1000
            row['terminal_ms'] = (ended - started_ns) / 1_000_000
            _need(ended <= deadline, 'TERMINAL_TIMEOUT')
            _need(result.command_id == command_id, 'TERMINAL_IDENTITY')
            uncertain = result.status is Status.UNKNOWN and result.code == 'CONNECTION_LOST_LOOKUP'
            digest = result.postconditions.get('request_digest')
            _need(digest == request_digest or uncertain and digest is None, 'TERMINAL_IDENTITY')
            if result.status is not Status.ACCEPTED_PENDING and not uncertain:
                return result, ended
            time.sleep(0.001)

    def _readback(self, result, expected_effects, expected_value=None):
        _need(result.status is Status.COMMITTED, 'TERMINAL_' + result.status.value)
        snapshot = result.postconditions.get('snapshot')
        _need(type(snapshot) is dict and snapshot.get('effect_count') == expected_effects, 'DUPLICATE_OR_LOST_EFFECT')
        _need(result.result_hash == 'sha256:' + hashlib.sha256(canonical_bytes(snapshot)).hexdigest(), 'READBACK_HASH')
        _need(snapshot.get('revision') == 'rev-' + str(expected_effects), 'READBACK_REVISION')
        if expected_value is not None:
            _need(snapshot.get('value') == expected_value, 'READBACK_VALUE')
        self.effects, self.revision = expected_effects, snapshot['revision']
        return snapshot

    def _command(self, kind, command_id, lease, row):
        expected = self.effects
        row['lookup_attempts'] = []
        # All three classes use the real fixed catalog; rejection has a valid
        # payload digest and is rejected specifically by host payload validation.
        value = expected + 1 if kind == 'admitted' else 1_000_001 if kind == 'rejected' else None
        request = self.client.request(command_id, value=value, lease=replace(lease, revision=self.revision))
        start = _clock()
        result = self.client.submit(request)
        received = self._received()
        row.update(started_mono_us=start // 1000, receipt_mono_us=received // 1000,
                   receipt_ms=(received - start) / 1_000_000, receipt_status=result.status.value,
                   receipt_code=result.code, request_digest=request.digest)
        _need(result.command_id == command_id, 'RECEIPT_IDENTITY')
        if kind == 'rejected':
            _need(result.status is Status.REJECTED and result.code == 'INVALID_FIXTURE_PAYLOAD', 'WRONG_VALIDATION_REJECTION')
            _need(self.host.fixture.effect_count == expected, 'REJECTED_EFFECT')
            row.update(latency_ms=row['receipt_ms'], terminal_status=result.status.value,
                       effect_count_before=expected, effect_count_after=expected)
            return
        _need(result.status is Status.ACCEPTED_PENDING, 'ADMISSION_' + result.status.value)
        _need(result.postconditions.get('request_digest') == request.digest, 'RECEIPT_DIGEST')
        terminal, ended = self._terminal(command_id, request.digest, row, started_ns=start)
        snapshot = self._readback(terminal, expected + (kind == 'admitted'), value if kind == 'admitted' else None)
        row.update(terminal_mono_us=ended // 1000, terminal_ms=(ended - start) / 1_000_000,
                   terminal_status=terminal.status.value, terminal_code=terminal.code,
                   result_hash=terminal.result_hash, snapshot=snapshot,
                   effect_count_before=expected, effect_count_after=self.effects)
        row['latency_ms'] = row['receipt_ms'] if kind == 'admitted' else row['terminal_ms']

    def _cancel_probe(self, index, lease, row):
        command_id = f'{self.run_id}.b{index}.cancel'
        request = self.client.request(command_id, value=999_999, delay_ms=1000,
                                      lease=replace(lease, revision=self.revision))
        row.update(command_id=command_id, kind='cancel', separate_from_mix=True,
                   delay_ms=1000, request_digest=request.digest, lookup_attempts=[])
        queued = self.client.submit(request)
        self._received()
        _need(queued.status is Status.ACCEPTED_PENDING, 'CANCEL_JOB_NOT_ADMITTED')
        _need(queued.command_id == command_id and queued.postconditions.get('request_digest') == request.digest,
              'CANCEL_JOB_IDENTITY')
        start = _clock()
        receipt = self.client.cancel(command_id)
        end = self._received()
        row.update(started_mono_us=start // 1000, receipt_mono_us=end // 1000,
                   receipt_ms=(end - start) / 1_000_000, status=receipt.status.value)
        _need(receipt.status is Status.CANCELED and receipt.code == 'CANCELED_BEFORE_APPLY', 'CANCEL_NOT_LATCHED')
        _need(receipt.command_id == command_id and receipt.postconditions.get('request_digest') == request.digest,
              'CANCEL_RECEIPT_IDENTITY')
        terminal, ended = self._terminal(command_id, request.digest, row, started_ns=start)
        _need(terminal.status is Status.CANCELED and terminal.postconditions.get('no_effect') is True, 'CANCEL_TERMINAL')
        _need(self.host.fixture.effect_count == self.effects, 'CANCEL_JOB_EFFECT')
        row.update(terminal_mono_us=ended // 1000, terminal_ms=(ended - start) / 1_000_000,
                   terminal_status=terminal.status.value, no_effect=True)
        return row

    def run_batch(self, index):
        return self._run(index, GROUPS, 'benchmark')

    def run_diagnostic(self, index=None):
        return self._run(self.next_index if index is None else index, 1, 'diagnostic')

    def _run(self, index, groups, mode):
        _need(not self.closed and not self.failed, 'PRODUCER_CLOSED_OR_HELD')
        _need(type(index) is int and index == self.next_index and 0 <= index < MAX_BATCHES, 'BATCH_ORDER')
        _need(self.mode in (None, mode), 'MODE_MIX')
        self.mode = mode
        report = {'schema_id': 'hh-studio.benchmark-command-batch', 'schema_version': '1.1.0',
                  'run_id': self.run_id, 'index': index, 'mode': mode, 'complete_command_mix': False,
                  'native_acceptance': False, 'effects_kind': 'in_process_mock_fixture',
                  'transport_kind': 'accepted_loopback_fixture_http', 'observation_kind': self.observer.kind,
                  'host_process': dict(self.identity), 'warmup': index < 5,
                  'commands': [], 'latency_ms': {'inspect': [], 'rejected': [], 'admitted': []},
                  'effects_per_admission': [], 'cancel': None, 'status': 'RUNNING'}
        start, initial_effects = _clock(), self.effects
        self._status_ns = [start]
        report['started_mono_us'] = start // 1000
        try:
            lease = self._connect_batch()
            report['memory_before'] = self._observe()
            for group in range(groups):
                for kind in ('inspect',) * 5 + ('rejected',) * 3 + ('admitted',) * 2:
                    _need((_clock() - start) / 1_000_000_000 < BATCH_TIMEOUT_SECONDS, 'BATCH_TIMEOUT')
                    ordinal = len(report['commands'])
                    command_id = f'{self.run_id}.b{index}.{kind}.{len(report["latency_ms"][kind])}'
                    row = {'ordinal': ordinal, 'group': group, 'kind': kind, 'command_id': command_id}
                    report['commands'].append(row)  # Keep uncertainty even if submit fails.
                    self._command(kind, command_id, lease, row)
                    report['latency_ms'][kind].append(row['latency_ms'])
                    if kind == 'admitted':
                        report['effects_per_admission'].append(row['effect_count_after'] - row['effect_count_before'])
                if group == (groups - 1) // 2:
                    report['cancel'] = {}
                    self._cancel_probe(index, lease, report['cancel'])
            _need(self.effects == initial_effects + groups * 2, 'BATCH_EFFECT_COUNT')
            report['memory_after'] = self._observe()
            report.update(status='COMPLETE' if mode == 'benchmark' else 'DIAGNOSTIC',
                          complete_command_mix=groups == GROUPS, effect_count_before=initial_effects,
                          effect_count_after=self.effects, dropped_commands=0, dropped_telemetry=0,
                          journal_bytes=(self.root / 'commands.jsonl').stat().st_size)
            report['diagnostic_retention'] = 'bounded host ring; every expected rejection retained in command rows; unexpected codes fail at each response'
            self.next_index += 1
        except Exception as error:
            self.failed = True
            report.update(status='FAILED', failure_code=getattr(error, 'code', type(error).__name__))
            # Preserve only the client's fixed, secret-free failure categories.
            # Successful batch schemas and uncertainty/retry policy do not change.
            transport_failure = getattr(self.client, 'last_transport_failure', None)
            if transport_failure is not None:
                report['transport_failure'] = transport_failure
            raise CommandError(report['failure_code'], report=report, cleanup_owner=self) from error
        finally:
            end = _clock()
            self._status_ns.append(end)
            report['ended_mono_us'] = end // 1000
            report['host_response_mono_us'] = [n // 1000 for n in self._status_ns]
            report['max_status_gap_ms'] = max(b - a for a, b in zip(self._status_ns, self._status_ns[1:])) / 1_000_000
            report['status_gap_scope'] = 'host command-lane response progress; not editor UI heartbeat'
            self._status_ns = []
        return report

    def close(self):
        if self.closed:
            return
        self.failed = True
        try:
            if self.host is not None:
                self.host.close()
            if self.observer is not None:
                self.observer.close()
            if self.journal is not None:
                self.journal.close()
        except Exception as error:
            raise CommandError('CLEANUP_HELD', cleanup_owner=self) from error
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main(argv=None):
    """A ten-command diagnostic only; full campaign is coordinator-owned."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path, help='new exclusive command artifact directory')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args(argv)
    producer = None
    try:
        producer = CommandProducer(args.root, args.run_id)
        report = producer.run_diagnostic()
        producer.close()
        print(json.dumps(report, separators=(',', ':'), allow_nan=False))
        return 0
    except Exception as error:
        if producer is not None:
            producer.close()
        print(json.dumps({'status': 'FAILED', 'code': getattr(error, 'code', type(error).__name__),
                          'partial': getattr(error, 'report', None)}, separators=(',', ':')))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
