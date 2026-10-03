"""Bounded Windows I/O probe for O9.4b; never starts Godot or Docker.

The probe writes only beneath the caller supplied diagnostic root.  It measures
open/read, append+fsync, and replacement of a same-directory file with a
bounded tail record.  It is diagnostic evidence only and cannot authorize a
formal pair.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import re
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
if __name__ == '__main__':
    sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_benchmark_campaign as campaign

MIN_ITERATIONS = 20_000
TAIL_MS = 500.0
MAX_TAIL = 64


def _replace_file(destination: Path, replacement: Path) -> None:
    """Use ReplaceFileW on Windows and same-volume replace elsewhere."""
    if os.name != 'nt':
        os.replace(replacement, destination)
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.ReplaceFileW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR,
                                    w.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    kernel.ReplaceFileW.restype = w.BOOL
    if not kernel.ReplaceFileW(str(destination), str(replacement), None, 0, None, None):
        raise OSError(ctypes.get_last_error(), 'ReplaceFileW')


def _timed_tail(rows, started_ns, ended_ns):
    elapsed = (ended_ns - started_ns) / 1_000_000
    rows.append(elapsed)
    if elapsed >= TAIL_MS:
        return {'elapsed_ms': elapsed, 'ordinal': len(rows) - 1}
    return None


def _process_snapshot():
    """Return CPU counters for Defender/SearchIndexer when available."""
    try:
        entries = campaign.heavy_preflight_processes(all_processes=True)
        counters = campaign.environment._nt_process_times(None)
    except Exception as error:
        return {'available': False, 'error': type(error).__name__, 'processes': []}
    wanted = {'msmpeng.exe', 'searchindexer.exe', 'searchprotocolhost.exe'}
    rows = []
    for item in entries:
        if item['name'] not in wanted:
            continue
        counter = counters.get(item['pid'])
        rows.append({'pid': item['pid'], 'name': item['name'],
                     'cpu_total_100ns': None if counter is None else counter['cpu_total_100ns'],
                     'process_start_100ns': None if counter is None else counter['process_start_100ns']})
    return {'available': True, 'error': None, 'processes': rows}


def run(root: Path, run_id: str, iterations: int = MIN_ITERATIONS):
    if not isinstance(iterations, int) or iterations < MIN_ITERATIONS:
        raise ValueError('O9_IO_ITERATIONS')
    if not isinstance(run_id, str) or re.fullmatch(r'[a-z0-9-]{1,64}', run_id) is None:
        raise ValueError('O9_IO_RUN_ID')
    root.mkdir(parents=True, exist_ok=False)
    payload = b'o9-io-probe\n'
    source = root / 'replace-source.bin'
    destination = root / 'replace-target.bin'
    append_path = root / 'append.bin'
    source.write_bytes(payload)
    destination.write_bytes(payload)
    append_path.write_bytes(b'')
    expected_destination = payload
    before_cpu = _process_snapshot()
    timings = {'open_read_ms': [], 'append_fsync_ms': [], 'replace_ms': []}
    tails = {'open_read': [], 'append_fsync': [], 'replace': []}
    max_rows = {key: None for key in timings}
    for ordinal in range(iterations):
        started = time.perf_counter_ns()
        with destination.open('rb') as stream:
            if stream.read() != expected_destination:
                raise RuntimeError('O9_IO_READBACK')
        ended = time.perf_counter_ns()
        tail = _timed_tail(timings['open_read_ms'], started, ended)
        if tail is not None and len(tails['open_read']) < MAX_TAIL:
            tails['open_read'].append(tail)
        started = time.perf_counter_ns()
        with append_path.open('ab') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        ended = time.perf_counter_ns()
        tail = _timed_tail(timings['append_fsync_ms'], started, ended)
        if tail is not None and len(tails['append_fsync']) < MAX_TAIL:
            tails['append_fsync'].append(tail)
        replacement = payload + str(ordinal).encode()
        source.write_bytes(replacement)
        started = time.perf_counter_ns()
        _replace_file(destination, source)
        ended = time.perf_counter_ns()
        tail = _timed_tail(timings['replace_ms'], started, ended)
        if tail is not None and len(tails['replace']) < MAX_TAIL:
            tails['replace'].append(tail)
        expected_destination = replacement
        source.write_bytes(payload)
        for key, values in timings.items():
            current = values[-1]
            if max_rows[key] is None or current > max_rows[key]['elapsed_ms']:
                max_rows[key] = {'elapsed_ms': current, 'ordinal': ordinal}
    after_cpu = _process_snapshot()
    result = {'schema_id': 'hh-studio.o9-io-probe', 'schema_version': '1.0.0',
              'run_id': run_id, 'iterations': iterations, 'formal_acceptance': False,
              'operations': {key: {'count': len(values), 'max': max_rows[key],
                                   'tail_ge_500ms': tails[name]}
                             for (key, values), name in zip(timings.items(),
                                                            ('open_read', 'append_fsync', 'replace'))},
              'cpu_processes': {'before': before_cpu, 'after': after_cpu},
              'files': {name: {'size_bytes': path.stat().st_size}
                        for name, path in (('destination', destination), ('append', append_path))}}
    (root / 'result.json').write_text(json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--iterations', type=int, default=MIN_ITERATIONS)
    args = parser.parse_args(argv)
    try:
        run(args.root, args.run_id, args.iterations)
        return 0
    except Exception as error:
        print(type(error).__name__ + ':' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
