"""Read-only replay of completed lane schemas; mutations use owned temp copies."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REVIEWS = HERE.parent
spec = importlib.util.spec_from_file_location('s55_controller_schema_replay', HERE / 'run_native_lane.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)

FIXTURES = {
    'save': '20260917-gt03-s53-publication-01',
    'script': '20260917-gt03-s53-script-publication-02',
    'edit': '20260917-gt03-s54-edit-publication-03',
    'stop': '20260917-gt03-s53-stop-01',
    'fifo': '20260917-gt03-s54-fifo-publication-01',
    'recovery-publication': '20260917-gt03-s54-recovery-publication-01',
    'scene-cas': '20260917-gt03-s54-recovery-cuts-02/scene-cas',
    'script-committed': '20260917-gt03-s54-recovery-cuts-03/script-committed',
    'script-retired': '20260917-gt03-s54-recovery-cuts-03/script-retired',
    'edit-applied': '20260917-gt03-s54-recovery-cuts-03/edit-applied',
    'script-unwitnessed': '20260917-gt03-s54-recovery-cuts-03/script-unwitnessed',
}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def accepted(output, lane, host):
    try:
        controller.need(controller.clean_exit(output, host, 0), 'outer raw exit mismatch')
        controller.validate_result(output, lane, host)
        return True, None
    except (ValueError, KeyError, TypeError, OSError) as error:
        return False, str(error)


def main():
    target = HERE / 'controller-schema-replay.json'
    controller.need(not target.exists(), 'replay report already exists')
    checks = []
    fixture_records = []
    pinned_closure = controller.CLOSURE
    manifest = controller.PACKAGE / 'source-closure.json'
    before_shared = controller.inventory()
    before_manifest = controller.digest(manifest)
    for lane, relative in FIXTURES.items():
        output = REVIEWS / relative
        _, _, result_name, _, marker = controller.LANES[lane]
        result = controller.read(output / result_name)
        if lane in controller.CRASH_EXITS:
            capture = controller.read(output.parent / 'capture.json')
            host = next(row['host'] for row in capture['cases'] if row['case'] == lane)
        else:
            capture = controller.read(output / 'capture.json')
            host = capture['host']
        # This test alone temporarily accepts each historical fixture's real
        # closure. Production controller and all evidence files stay unchanged.
        controller.CLOSURE = result['source_closure_sha256']
        files = [result_name, host['stdout'], host['host']]
        if lane in controller.CRASH_EXITS or lane == 'recovery-publication':
            original = controller.read(output / 'original-host.json')
            files += ['original-host.json', 'original/' + original['host']]
        before = {name: controller.digest(output / name) for name in files}
        ok, error = accepted(output, lane, host)
        checks.append({'name': lane + ': historical result/marker/raw exit', 'passed': ok, 'error': error})
        fixture_records.append({'lane': lane, 'path': relative, 'source_closure_sha256': controller.CLOSURE,
                                'files_sha256': before, 'check_count': len(result['checks'])})
        mutations = ['raw_pid', 'raw_exit', 'source', 'marker', 'count']
        if lane in controller.CRASH_EXITS or lane == 'recovery-publication':
            mutations += ['original_raw_pid', 'original_raw_exit']
        for mutation in mutations:
            # Only five small metadata/log files at most; never copy runtime.
            with tempfile.TemporaryDirectory(prefix='controller-negative-', dir=HERE) as temporary:
                scratch = Path(temporary).resolve()
                controller.need(scratch.parent == HERE.resolve(), 'owned temporary path escaped audit directory')
                for name in files:
                    destination = scratch / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes((output / name).read_bytes())
                if mutation.startswith('raw_'):
                    path = scratch / host['host']
                    raw = controller.read(path)
                    key = 'target_pid' if mutation == 'raw_pid' else 'exit_code'
                    raw[key] += 1
                    dump(path, raw)
                elif mutation.startswith('original_raw_'):
                    path = scratch / 'original' / original['host']
                    raw = controller.read(path)
                    key = 'target_pid' if mutation == 'original_raw_pid' else 'exit_code'
                    raw[key] += 1
                    dump(path, raw)
                elif mutation == 'source':
                    changed = copy.deepcopy(result)
                    changed['source_closure_sha256'] = '0' * 64
                    dump(scratch / result_name, changed)
                else:
                    path = scratch / host['stdout']
                    lines = path.read_text(encoding='utf-8').splitlines()
                    for index, line in enumerate(lines):
                        if line.startswith(marker + ' '):
                            if mutation == 'marker':
                                lines[index] = 'INVALID_' + line
                            else:
                                payload = json.loads(line[len(marker) + 1:])
                                payload['checks'] += 1
                                lines[index] = marker + ' ' + json.dumps(payload)
                    path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
                admitted, error = accepted(scratch, lane, host)
                checks.append({'name': lane + ': reject ' + mutation, 'passed': not admitted, 'rejection': error})
                controller.need(scratch.resolve().parent == HERE.resolve(), 'temporary cleanup boundary changed')
        checks.append({'name': lane + ': historical bytes unchanged',
                       'passed': before == {name: controller.digest(output / name) for name in files}})
    controller.CLOSURE = pinned_closure
    checks.append({'name': 'shared S55 source and manifest unchanged',
                   'passed': controller.inventory() == before_shared and controller.digest(manifest) == before_manifest})
    report = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'controller_sha256': controller.digest(HERE / 'run_native_lane.py'),
              'verification_script_sha256': controller.digest(Path(__file__)),
              'source_closure_sha256': pinned_closure, 'native_processes_started': 0,
              'historical_fixture_replay_only': True, 'gt03_acceptance': False,
              'fixtures': fixture_records, 'checks': checks, 'passed': all(row['passed'] for row in checks)}
    dump(target, report)
    print(json.dumps({'passed': report['passed'], 'checks': len(checks),
                      'failures': [row for row in checks if not row['passed']]}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
