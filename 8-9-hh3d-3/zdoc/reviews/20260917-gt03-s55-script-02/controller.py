"""Cleanup-only test-driver supplement over the unchanged S55 runtime.

The original script fixture closed its owner while durable Stop was PENDING.
Keep that failed run and every runtime/unit byte. This explicit driver waits
for the existing Stop contract and captures its final native state. It neither
patches runtime methods nor changes command/lease/operation deadlines.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
BASE_HASH = '46d27dd3a3c188ad90abd8a951d6723314e989ebd642fae6be68dbe1232394da'
POLICY = 'cleanup-only-stop-drain-v1'

HELPER = '''
def wait_for_durable_stop(owner, output, call, stopped, check):
    import time
    started = time.monotonic()
    deadline = started + 25
    status = 200
    while stopped.get('stop_persistence') == 'PENDING' and time.monotonic() < deadline:
        time.sleep(.05)
        reply = call('/v1/stop', {'project_id': owner.project_id,
            'command_id': 'control.stop'}, control=True)
        status, stopped = reply[:2]
    save(output / 'stop-terminal.json', {'response': stopped,
        'http_status': status, 'drain_elapsed_ms': (time.monotonic() - started) * 1000})
    check('durable_stop_before_owner_close', status == 200
          and stopped.get('stop_persistence') == 'DURABLE'
          and owner._journal.snapshot()['stopped'] is True)
    for name in ('events.json', 'journal.json'):
        if (output / name).exists():
            with (output / ('before-stop-' + name)).open('xb') as saved:
                saved.write((output / name).read_bytes())
    save(output / 'journal.json', owner._journal.snapshot())
    save(output / 'events.json', [json.loads(raw) for raw in owner._journal._state.events])

'''


def build_driver(original, source):
    text = original.decode('utf-8').replace('\r\n', '\n')
    location = 'STUDIO = Path(__file__).resolve().parents[2]'
    if location not in text:
        location = 'STUDIO=Path(__file__).resolve().parents[2]'
    assert text.count(location) == 1, 'unexpected probe root binding'
    text = text.replace(location, 'STUDIO = Path(' + repr(str(source)) + ')')
    match = re.findall(r"^        check\('authenticated_stop',[^\n]+\)$", text, re.M)
    assert len(match) == 1, 'unexpected original Stop assertion'
    text = text.replace(match[0], match[0] + '\n        wait_for_durable_stop(owner, output, call, stopped, check)')
    marker = 'def main():'
    assert text.count(marker) == 1
    text = text.replace(marker, HELPER + marker)
    compile(text, '<cleanup-driver>', 'exec')
    return text.encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', required=True, choices=('script', 'save'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    base_path = HERE / 'run_native_lane.py'
    assert hashlib.sha256(base_path.read_bytes()).hexdigest() == BASE_HASH, 'base controller changed'
    spec = importlib.util.spec_from_file_location('s55_pinned_lane_controller', base_path)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    runner, before, manifest_hash, binary, linux, pins = base.preflight()
    output = args.output.resolve()
    base.need(output.parent == base.REVIEWS.resolve() and not output.exists(), 'fresh reviews output required')
    base.need(re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id), 'valid run id required')
    script, timeout, _, _, _ = base.LANES[args.lane]
    original = (base.SOURCE / 'tests/godot' / script).read_bytes()
    driver = build_driver(original, base.SOURCE)
    driver_hash = hashlib.sha256(driver).hexdigest()
    controller = Path(__file__).resolve()
    controller_hash = base.digest(controller)
    binding = {'policy': POLICY, 'runtime_closure_sha256': base.CLOSURE,
        'original_probe': 'tests/godot/' + script,
        'original_probe_sha256': hashlib.sha256(original).hexdigest(),
        'executed_driver': 'driver.py', 'executed_driver_sha256': driver_hash,
        'controller_sha256': controller_hash, 'base_controller_sha256': BASE_HASH,
        'runtime_modified': False, 'unit_dependencies_modified': False}
    argv = [sys.executable, '-B', str(output / 'driver.py'), '--frozen', '--output', str(output),
        '--run-id', args.run_id, '--binary', str(binary), '--closure', base.CLOSURE]
    invocation = {'lane': args.lane, 'run_id': args.run_id, 'argv': argv, 'cwd': str(base.SOURCE),
        'timeout_seconds': timeout, 'source_closure_sha256': base.CLOSURE,
        'controller_sha256': controller_hash, 'runtime_entrypoint_sha256': binding['original_probe_sha256'],
        'effective_execution': binding, 'pins': pins,
        'python': {'path': sys.executable, 'version': sys.version, 'sha256': base.digest(Path(sys.executable))},
        'environment_overrides': {'HH_STUDIO_LINUX_GODOT': str(linux), 'PYTHONDONTWRITEBYTECODE': '1'},
        'one_lane_only': True, 'requires_coordinator_native_slot': True}
    if args.dry_run:
        print(json.dumps({'dry_run': True, 'engines_started': 0, 'invocation': invocation}, indent=2))
        return 0
    output.mkdir()
    (output / 'driver.py').write_bytes(driver)
    (output / 'controller.py').write_bytes(controller.read_bytes())
    base.save(output / 'effective-execution.json', binding)
    base.save(output / 'invocation.json', invocation)
    base.save(output / 'source-reference.json', {'source_package': str(base.PACKAGE), 'source_root': str(base.SOURCE),
        'source_closure_sha256': base.CLOSURE, 'file_count': base.FILE_COUNT,
        'source_manifest_sha256': manifest_hash, 'runtime_copied': False,
        'controller_sha256': controller_hash, 'effective_execution': binding})
    capture = {'run_id': args.run_id, 'lane': args.lane, 'passed': False,
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'source_closure_sha256': base.CLOSURE,
        'controller_sha256': controller_hash, 'candidate_only': True, 'gt03_acceptance': False,
        'effective_execution': binding}
    try:
        environment = dict(os.environ)
        environment.update(invocation['environment_overrides'])
        host = runner.run_process(argv, cwd=base.SOURCE, output=output, timeout=timeout,
            label='native-' + args.lane, env=environment)
        capture['host'] = host
        base.save(output / 'host-report.json', host)
        base.need(base.clean_exit(output, host, 0), 'raw exit/wrapper/owned Job mismatch')
        capture['result'] = base.validate_result(output, args.lane, host)
        stop = base.read(output / 'stop-terminal.json')
        base.need(stop['response']['stop_persistence'] == 'DURABLE' and stop['http_status'] == 200,
            'durable Stop completion missing')
        logs = base.typed_logs(output)
        base.save(output / 'log-audit.json', logs)
        base.need(logs['clean'] is True, 'unexplained log diagnostic')
        capture.update(passed=True, native_logs_clean=True)
    except BaseException as error:
        capture['failure'] = type(error).__name__ + ': ' + str(error)
    finally:
        same = base.inventory() == before and base.digest(base.PACKAGE / 'source-closure.json') == manifest_hash
        controller_same = base.digest(controller) == controller_hash == base.digest(output / 'controller.py')
        driver_same = base.digest(output / 'driver.py') == driver_hash
        pins_same = base.digest(binary) == pins['windows_gui']['sha256'] and base.digest(linux) == pins['linux']['sha256']
        capture.update(source_inventory_unchanged=same, controller_unchanged=controller_same,
            driver_unchanged=driver_same, executable_pins_unchanged=pins_same)
        capture['passed'] = capture['passed'] and same and controller_same and driver_same and pins_same
        base.save(output / 'source-check-after.json', {'unchanged': same, 'file_count': len(before)})
        capture['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        base.save(output / 'capture.json', capture)
    print(json.dumps({'lane': args.lane, 'passed': capture['passed'], 'effective_execution': binding,
        'checks': capture.get('result', {}).get('check_count'), 'failure': capture.get('failure')}, indent=2), flush=True)
    return int(not capture['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
