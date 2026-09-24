"""Bounded provider-differential RSS diagnostic for one native cycle."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
RAW = STUDIO / '.local/reviews/gt06-s228-phase-rss-01'
RUN_ID = 'gt06-s228-phase-rss-01'
NATIVE_ID = 'gt06-s228-native-cycle-01'
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.host.replay.process_probe import ProcessProbe, HELD_PROBES


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise RuntimeError('S228_READBACK')


def observe(root, executable, rows, stop, errors):
    probe = None
    started = time.monotonic()
    try:
        process_start = root / 'editor-host/process-start.json'
        while probe is None and not stop.is_set():
            if time.monotonic() - started > 30:
                raise RuntimeError('S228_EDITOR_START')
            try:
                record = json.loads(process_start.read_bytes())
                probe = ProcessProbe(record['pid'], executable)
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.025)
        while probe is not None and not stop.is_set():
            sample = probe.sample_with_handle_count()
            if sample is None:
                break
            sample['sequence'] = len(rows)
            sample['provider'] = 'external-retained-ProcessProbe'
            rows.append(sample)
            time.sleep(.025)
    except BaseException as error:
            errors.append({'type': type(error).__name__, 'code': str(error)})
    finally:
        if probe is not None:
            try:
                probe.close()
            except BaseException as error:
                errors.append({'type': type(error).__name__, 'code': str(error)})
    return errors


def nearest_pairs(internal, external):
    if not internal or not external:
        return []
    pairs = []
    for row in internal:
        near = min(external, key=lambda item: abs(item['host_mono_us'] - row['host_mono_us']))
        delta = abs(near['host_mono_us'] - row['host_mono_us'])
        pairs.append({'internal_mono_us': row['host_mono_us'], 'external_mono_us': near['host_mono_us'],
                      'delta_us': delta, 'internal_rss': row['rss_bytes'], 'external_rss': near['rss_bytes'],
                      'internal_window_handles': row.get('visible_window_handles', []),
                      'external_held_handles': near.get('held_handles')})
    return pairs


def main():
    if RAW.exists():
        raise RuntimeError('S228_ALREADY_EXISTS')
    RAW.mkdir(parents=True)
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64.exe'
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    if sha(executable.read_bytes()) != lock['gui_sha256']:
        raise RuntimeError('S228_BINARY')
    write(RAW / 'preflight.json', {'run_id': RUN_ID, 'native_run_id': NATIVE_ID,
        'authority': 0, 'formal_acceptance': False, 'engine_started': False,
        'binary_sha256': lock['gui_sha256'],
        'provider_external': 'ProcessProbe.sample_with_handle_count',
        'provider_internal': 'run_native_benchmark.Sampler.ProcessProbe.sample',
        'hypothesis': 'Do independent and campaign-local retained-handle RSS observations agree at native-cycle phase?',
        'gate_unchanged': True})
    native_script = ROOT / 'studio/tests/replay/run_native_benchmark.py'
    internal = subprocess.Popen([sys.executable, '-B', str(native_script), '--run-id', NATIVE_ID],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW)
    root = STUDIO / '.local/reviews' / NATIVE_ID
    rows, errors, stop = [], [], threading.Event()
    thread = threading.Thread(target=observe, args=(root, executable, rows, stop, errors), daemon=True)
    thread.start()
    stdout, stderr = internal.communicate(timeout=180)
    stop.set(); thread.join(10)
    write(RAW / 'native-process-exit.json', {'pid': internal.pid, 'actual_exit': internal.returncode,
        'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr), 'stdout_bytes': len(stdout), 'stderr_bytes': len(stderr)})
    write(RAW / 'native-stdout.txt', stdout)
    write(RAW / 'native-stderr.txt', stderr)
    if thread.is_alive():
        errors.append('S228_OBSERVER_DRAIN')
    if rows:
        write(RAW / 'external-samples.json', {'schema_id': 'hh-studio.gt06-s228-external-samples',
            'schema_version': '1.0.0', 'run_id': RUN_ID, 'native_run_id': NATIVE_ID,
            'rows': rows, 'errors': errors, 'formal_acceptance': False})
    native_capture = json.loads((root / 'capture.json').read_bytes()) if (root / 'capture.json').exists() else None
    internal_rows = json.loads((root / 'process-metrics.json').read_bytes()).get('samples', []) if (root / 'process-metrics.json').exists() else []
    pairs = nearest_pairs(internal_rows, rows)
    comparable = [row for row in pairs if row['delta_us'] <= 100_000]
    diffs = [abs(row['external_rss'] - row['internal_rss']) / max(row['internal_rss'], 1) for row in comparable]
    analysis = {'schema_id': 'hh-studio.gt06-s228-analysis', 'schema_version': '1.0.0',
        'run_id': RUN_ID, 'native_run_id': NATIVE_ID, 'authority': 0, 'formal_acceptance': False,
        'engine_started': bool(native_capture), 'native_actual_exit': None if native_capture is None else native_capture['actual_exits']['editor'],
        'external_sample_count': len(rows), 'internal_sample_count': len(internal_rows),
        'comparable_pairs': len(comparable), 'max_pair_delta_us': max((row['delta_us'] for row in comparable), default=None),
        'median_relative_rss_difference': sorted(diffs)[len(diffs)//2] if diffs else None,
        'internal_rss_min': min((row['rss_bytes'] for row in internal_rows), default=None),
        'internal_rss_max': max((row['rss_bytes'] for row in internal_rows), default=None),
        'external_rss_min': min((row['rss_bytes'] for row in rows), default=None),
        'external_rss_max': max((row['rss_bytes'] for row in rows), default=None),
        'provider_agreement_not_rootcause': bool(comparable and diffs and sorted(diffs)[len(diffs)//2] <= .05),
        'measurement_defect_proven': False, 'leak_owner_rootcause_proven': False,
        'next_action': 'REVIEW_PHASE_CORRELATED_DIFFERENTIAL; DO_NOT_CHANGE_GATE_OR_RETRY_UNCHANGED',
        'raw_native_capture_sha256': None if native_capture is None else sha((root / 'capture.json').read_bytes()),
        'raw_internal_metrics_sha256': None if not (root / 'process-metrics.json').exists() else sha((root / 'process-metrics.json').read_bytes())}
    write(RAW / 'analysis.json', analysis)
    write(RAW / 'pairs-sample.json', {'schema_id': 'hh-studio.gt06-s228-pairs', 'schema_version': '1.0.0',
        'run_id': RUN_ID, 'rows': comparable[:200], 'formal_acceptance': False})
    if internal.returncode != 0 or not rows or errors:
        raise RuntimeError('S228_DIAGNOSTIC_FAILED')
    print(json.dumps(analysis, sort_keys=True))


if __name__ == '__main__':
    main()
