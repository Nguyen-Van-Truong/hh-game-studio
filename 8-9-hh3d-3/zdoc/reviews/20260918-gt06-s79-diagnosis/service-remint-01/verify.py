"""Read-only recheck of this remint's frozen bytes and process records.

Writes no evidence; redirect stdout to a fresh audit file. Not a critic verdict.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
STUDIO = ROOT / 'studio'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def need(value, label):
    if not value:
        raise RuntimeError(label)


def main():
    need(not sys.argv[1:], 'fixed invocation')
    freeze = read(BASE / 'freeze.json')
    for name, digest in freeze['source_files'].items():
        need(sha(ROOT / name) == sha(BASE / 'source' / name) == digest, 'frozen source/copy ' + name)
    launcher = BASE.parent / 'run_service_remints.py'
    need(sha(launcher) == freeze['source_files'][launcher.relative_to(ROOT).as_posix()], 'launcher bytes')
    spec = importlib.util.spec_from_file_location('s79_frozen_remint', launcher)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = freeze['backend_source_files']
    need(len(source) == 174 and 'host/replay/disk_journal_index.py' in source, 'backend domain')
    verification = read(BASE / 'verification.json')
    need(len(verification['lanes']) == len(module.LANES) == 7, 'seven lanes')
    raw_count = raw_bytes = copied_count = checks_count = 0
    summaries = []
    for label, driver, mode, _ in module.LANES:
        lane = BASE / label
        summary = read(lane / 'verification.json')
        run_id = 'gt06-s79-' + label + '-01'
        raw = STUDIO / '.local/reviews' / run_id
        need(summary == verification['lanes'][len(summaries)], 'lane summary binding')
        module.verify_outer(lane, read(lane / 'capture.json')['host'])
        if 'adversary' in driver or 'reviewer' in driver:
            inner = STUDIO / '.local/reviews' / (run_id + ('-outer' if 'adversary' in driver else '-driver'))
            capture = read(inner / 'capture.json')
            need(capture['completed'] is True, 'inner completion')
            module.verify_outer(inner, capture['host'])
        need(read(raw / 'source-files.json') == source, 'runtime exact source')
        need(module.verify_stage(raw / 'import-host') == summary['import'], 'import summary binding')
        need(module.verify_stage(raw / 'runtime-host', mode in ('stop', 'saturated-stop')) == summary['runtime'], 'runtime summary binding')
        inventory = read(lane / 'raw-files.json')
        for name, entry in inventory.items():
            path = ROOT / name
            need(path.stat().st_size == entry['size_bytes'] and sha(path) == entry['sha256'], 'raw hash ' + name)
            copy = BASE / 'selected' / path.relative_to(STUDIO / '.local/reviews')
            if copy.exists():
                need(sha(copy) == entry['sha256'], 'selected copy ' + name)
                copied_count += 1
        domain = 'reviewer-probe' if 'reviewer' in driver else 'http-adversary' if 'adversary' in driver else 'http-probe'
        result = read(raw / domain / 'result.json')
        if domain == 'reviewer-probe':
            events = read(raw / domain / 'observations.json')
            need(not events['errors'] and events['closed'] and events['window_closed'], 'reviewer close')
            need(any(e['phase'] == 'running' for e in events['events']), 'reviewer running')
            need(result['flags']['play_key'] and (result['flags']['stop_key'] if mode == 'stop'
                 else result['flags']['inspect_button'] and result['flags']['capture_button']), 'reviewer input')
        else:
            need(all(row['passed'] is True for row in result['checks']), 'HTTP checks')
            checks_count += len(result['checks'])
        raw_count += len(inventory)
        raw_bytes += sum(row['size_bytes'] for row in inventory.values())
        summaries.append({'run_id': run_id, 'checks': summary['checks'],
                          'actual_native_exit': summary['runtime']['actual_native_exit']})
    print(json.dumps({'schema': 'HH-GT06-S79-SERVICE-RECHECK-1', 'passed': True,
          'verifier_sha256': sha(Path(__file__)), 'launcher_sha256': sha(launcher),
          'freeze_sha256': sha(BASE / 'freeze.json'), 'frozen_files': len(freeze['source_files']),
          'backend_source_files': len(source), 'backend_source_sha256': freeze['backend_source_sha256'],
          'raw_files': raw_count, 'raw_bytes': raw_bytes, 'selected_files': copied_count,
          'http_checks': checks_count, 'lanes': summaries, 'formal_acceptance': False}, indent=2))


if __name__ == '__main__':
    main()
