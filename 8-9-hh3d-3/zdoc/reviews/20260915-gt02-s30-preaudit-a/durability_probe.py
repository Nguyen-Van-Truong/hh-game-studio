"""Independent preparatory diagnostics; no candidate mutation or engine run."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT))
from studio.host.core import journal as jm
from studio.host.core import transport as tm
from studio.protocol.core import Status


def hashes():
    return {name: hashlib.sha256((PROJECT / 'studio/host/core' / name).read_bytes()).hexdigest()
            for name in ('journal.py', 'transport.py')}


def child_read(path, command, failed, archive=False):
    code = '''
import json, sys
from pathlib import Path
from unittest import mock
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from studio.host.core import journal as jm
try:
    with mock.patch.object(jm.os, "fsync", side_effect=OSError("private-child-barrier")) if sys.argv[4] == "1" else __import__("contextlib").nullcontext():
        journal = jm.Journal(sys.argv[2])
        result = (journal.lookup_archive if sys.argv[5] == "1" else journal.lookup)(project_id="project.fixture", command_id=sys.argv[3], now_ms=int(sys.argv[6]))
    print(json.dumps({"status": result["status"]}))
except jm.JournalError as exc:
    print(json.dumps({"error": exc.code}))
'''
    # Fresh interpreter proves the result is not inherited from a poison flag.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-B', '-c', code, str(PROJECT), str(path),
                             command, str(int(failed)), str(int(archive)),
                             str(tm.epoch_ms() + (20_000 if archive else 0))],
                            capture_output=True, text=True, timeout=10, env=env)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
    return {'process_exit': result.returncode, **json.loads(result.stdout)}


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='gt02-preaudit-a-') as directory:
        root = Path(directory)
        faults = tm.FixtureFaults(readback_gate=threading.Event())
        journal = jm.Journal(root / 'journal.jsonl', limits=jm.JournalLimits(retry_horizon_ms=10_000))
        with tm.LoopbackFixtureHost('project.fixture', root, journal, faults=faults) as host:
            credential = host.sessions.issue(scopes=frozenset(
                {'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'}))
            client = tm.FixtureClient(host.port, host.control_port, credential)
            try:
                yield root, host, client
            finally:
                faults.readback_gate.set()


class InjectIO:
    """Fail the selected terminal primitive; keep later barriers failing too."""
    def __init__(self, path, pending_size, mode):
        self.path, self.pending_size, self.mode = path, pending_size, mode
        self.real_open, self.real_fsync = Path.open, os.fsync
        self.triggered = False
        self.calls = []

    def open(self, path, mode='r', *args, **kwargs):
        stream = self.real_open(path, mode, *args, **kwargs)
        if path != self.path or mode != 'ab':
            return stream
        probe = self

        class Wrapped:
            def __enter__(self):
                stream.__enter__()
                return self

            def __exit__(self, *args):
                return stream.__exit__(*args)

            def fileno(self):
                return stream.fileno()

            def write(self, raw):
                if not probe.triggered and probe.mode in {'write_before', 'write_partial'}:
                    probe.triggered = True
                    probe.calls.append(probe.mode)
                    if probe.mode == 'write_partial':
                        stream.write(raw[:len(raw) // 2])
                        stream.flush()
                    raise OSError('private-terminal-write')
                return stream.write(raw)

            def flush(self):
                stream.flush()
                if not probe.triggered and probe.mode == 'flush_after':
                    probe.triggered = True
                    probe.calls.append(probe.mode)
                    raise OSError('private-terminal-flush')

        return Wrapped()

    def fsync(self, fd):
        self.calls.append('fsync')
        if self.mode == 'pre_barrier':
            self.triggered = True
        elif self.mode == 'terminal_fsync' and self.path.stat().st_size > self.pending_size:
            self.triggered = True
        if self.triggered:
            raise OSError('private-persistent-barrier')
        return self.real_fsync(fd)

    @contextmanager
    def armed(self):
        probe = self
        def patched_open(path, *args, **kwargs):
            return probe.open(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', patched_open), mock.patch.object(jm.os, 'fsync', self.fsync):
            yield


def summarize(response):
    return {'status': response.status.value, 'code': response.code,
            'command_id': response.command_id, 'no_effect': response.postconditions.get('no_effect')}


def scenario(mode):
    with fixture() as (_, host, client):
        command = 'preaudit-a.' + mode
        request = client.request(command, value=43, lease=client.lease())
        assert client.submit(request).status is Status.ACCEPTED_PENDING
        assert host.faults.applied.wait(1)
        before = host.journal.path.stat().st_size
        fault = InjectIO(host.journal.path, before, mode)
        out = {'case': mode, 'source': hashes()}
        with fault.armed():
            host.faults.readback_gate.set()
            deadline = time.monotonic() + 2
            while not host._stopped.is_set() and time.monotonic() < deadline:
                time.sleep(.005)
            assert fault.triggered and host._stopped.is_set()
            expected_error = 'JOURNAL_TRUNCATED' if mode == 'write_partial' else 'JOURNAL_DURABILITY_UNCONFIRMED'
            results = [client.lookup(command), client.submit(request), client.lookup_archive(command)]
            out['during_fault'] = [summarize(result) for result in results]
            assert all(result.status is Status.UNKNOWN and result.code == expected_error
                       and result.command_id == command and 'no_effect' not in result.postconditions
                       for result in results)
            out['fresh_process_fault'] = child_read(host.journal.path, command, True)
            assert out['fresh_process_fault']['error'] == expected_error
            try:
                host.journal.compact(now_ms=tm.epoch_ms() + 20_000)
            except jm.JournalError as exc:
                out['compact_during_fault'] = exc.code
            else:
                raise AssertionError('compaction succeeded during unresolved fault')
            assert out['compact_during_fault'] == expected_error
        out['terminal_bytes_added'] = host.journal.path.stat().st_size - before
        out['fault_calls'] = fault.calls
        out['fresh_process_recovery'] = child_read(host.journal.path, command, False)
        after = client.lookup(command)
        retry = client.submit(request)
        out['after_recovery'] = [summarize(after), summarize(retry)]
        expected_status = Status.COMMITTED if mode in {'terminal_fsync', 'flush_after'} else Status.UNKNOWN
        assert after.status is expected_status and retry.status is expected_status
        if mode != 'write_partial':
            expected_record = 'COMMITTED' if expected_status is Status.COMMITTED else 'ACCEPTED_PENDING'
            assert out['fresh_process_recovery']['status'] == expected_record
            later = tm.epoch_ms() + 20_000
            with mock.patch.object(tm, 'epoch_ms', return_value=later):
                host.journal.compact(now_ms=later)
                host.journal = jm.Journal(host.journal.path, limits=host.journal.limits)
                archive = client.lookup_archive(command)
                assert isinstance(archive, tm.ArchivedResult)
                out['archive'] = {'status': archive.receipt.status.value,
                                  'original_status': archive.original_status.value,
                                  'execution_permitted': archive.execution_permitted}
                assert archive.receipt.status is expected_status and not archive.execution_permitted
                expired_retry = client.submit(request)
                assert expired_retry.code == 'RETRY_HORIZON_EXPIRED'
                out['expired_retry'] = summarize(expired_retry)
            out['fresh_process_archive'] = child_read(host.journal.path, command, False, True)
            assert out['fresh_process_archive']['status'] == expected_record
        else:
            assert out['fresh_process_recovery']['error'] == 'JOURNAL_TRUNCATED'
            assert after.code == retry.code == 'JOURNAL_TRUNCATED'
        out['effects'] = host.fixture.effect_count
        assert out['effects'] == 1
        out['source_after'] = hashes()
        assert out['source'] == out['source_after']
        return out


def main():
    start = hashes()
    results = [scenario(mode) for mode in ('pre_barrier', 'write_before', 'write_partial',
                                           'flush_after', 'terminal_fsync')]
    assert start == hashes()
    print(json.dumps({'proof_class': 'PREPARATORY_LOGIC_FAULT_INJECTION',
                      'source': start, 'results': results, 'completion': 'PREAUDIT_A_MATRIX_COMPLETE'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
