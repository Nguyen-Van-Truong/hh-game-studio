"""Fresh F25 functional supplement using the existing seven-lane verifier.

The historical helper and evidence remain unchanged. No launch without --run;
--verify-existing only checks retained outputs. This is not another benchmark.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.measure_window import measurement_window

ORIGINAL = ROOT / 'zdoc/reviews/20260920-gt06-s133-functional/run_service_refresh.py'
OUTPUT = STUDIO / '.local/reviews/gt06-f25-functional-20261003-03'
GROUP = OUTPUT.name
PREFIX = 'gt06-f25'
spec = importlib.util.spec_from_file_location('f25_existing_service_refresh', ORIGINAL)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.OUTPUT = OUTPUT / 'lanes'
helper.run_id = lambda label: PREFIX + '-' + label + '-03'
DEFERRED_EXIT = 75
DEFER_CODES = frozenset({
    'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT', 'CAMPAIGN_PREFLIGHT_FOREIGN_ENGINE',
    'CAMPAIGN_PREFLIGHT_CPU_BUSY',
})


def driver_sources():
    files = campaign.source_files()
    result = {'studio/' + name: value for name, value in files.items()}
    result[Path(__file__).relative_to(ROOT).as_posix()] = digest(Path(__file__))
    result[ORIGINAL.relative_to(ROOT).as_posix()] = digest(ORIGINAL)
    return result


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')


def verify_envelope():
    value = json.loads((OUTPUT / 'driver-freeze.json').read_bytes())
    helper.need(value['schema'] == 'HH-GT06-F25-FUNCTIONAL-DRIVER-1', 'DRIVER_SCHEMA')
    helper.need(value['run_ids'] == [helper.run_id(lane[0]) for lane in helper.LANES], 'DRIVER_IDS')
    helper.need(value['source_files'] == driver_sources(), 'DRIVER_MEMBERSHIP_OR_SOURCE_CHANGED')
    for name, expected in value['source_files'].items():
        helper.need(digest(ROOT / name) == expected
                    and digest(OUTPUT / 'driver-source' / name) == expected, 'DRIVER_SOURCE_CHANGED')
    helper.need(value['helper_freeze_sha256'] == digest(helper.OUTPUT / 'freeze.json'), 'HELPER_FREEZE_CHANGED')
    helper.verify_freeze()
    return value


def run_once():
    """One admission per invocation; only an admitted launch consumes IDs."""
    # Reject terminal/uncertain work before touching a retained ownership marker.
    helper.need(not (OUTPUT / 'terminal.json').exists(), 'GROUP_TERMINAL')
    helper.need(not (helper.OUTPUT / 'run-started.json').exists(), 'RUN_ALREADY_STARTED')
    helper.unused_ids()
    clean = True
    with measurement_window(GROUP, 'Seven functional lanes; not formal benchmark',
                            safe_to_release=lambda: clean):
        verify_envelope()
        helper.need(not (OUTPUT / 'terminal.json').exists(), 'GROUP_TERMINAL')
        helper.need(not (helper.OUTPUT / 'run-started.json').exists(), 'RUN_ALREADY_STARTED')
        helper.unused_ids()
        admissions = OUTPUT / 'admissions'
        admissions.mkdir(exist_ok=True)
        # The cooperative window serializes admission numbering. No poll/retry.
        numbers = [int(p.name) for p in admissions.iterdir() if p.is_dir() and p.name.isdigit()]
        attempt = admissions / str(max(numbers, default=0) + 1).zfill(4)
        attempt.mkdir(exist_ok=False)
        write(attempt / 'started.json', {'started_at': helper.utc(), 'group': GROUP})
        engine_started = False
        try:
            preflight = campaign.environment_preflight()
            write(attempt / 'preflight.json', preflight)
            campaign.require_environment_preflight(preflight)
            launch = attempt / 'launch'; launch.mkdir()
            # The sampler validates its exact 64-file domain, and the callback
            # separately guards functional217 and both frozen source copies.
            source = campaign.source_files()
            campaign.verify_sources(source)
            campaign.observe_pair_launch(launch, {
                'run_id': GROUP, 'source_files': source,
                'source_closure_sha256': helper.native.closure(source),
                'campaign_sha256': digest(OUTPUT / 'driver-freeze.json'),
            }, verify_envelope)
            write(attempt / 'admitted.json', {'admitted_at': helper.utc(), 'group': GROUP})
            clean = False
            engine_started = True
            code = helper.run()
            clean = code == 0
            result = {'completed_at': helper.utc(), 'exit_code': code,
                      'verified_lanes': len(helper.LANES), 'cleanup_verified': clean,
                      'engine_launch_attempted': True, 'formal_acceptance': False}
            write(attempt / 'result.json', result)
            write(OUTPUT / 'terminal.json', result)
            return code
        except Exception as error:
            code = getattr(error, 'code', 'FUNCTIONAL_REFRESH_FAILED')
            deferred = not engine_started and code in DEFER_CODES
            result = {'completed_at': helper.utc(), 'error_type': type(error).__name__,
                      'code': code, 'state': 'DEFERRED' if deferred else 'FAILED',
                      'exit_code': DEFERRED_EXIT if deferred else 1,
                      'cleanup_verified': clean, 'engine_launch_attempted': engine_started,
                      'formal_acceptance': False}
            write(attempt / 'result.json', result)
            if not deferred:
                helper.failure_receipt(error)
                write(OUTPUT / 'terminal.json', result)
            print(json.dumps(result), flush=True)
            return result['exit_code']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--prepare', action='store_true')
    options.add_argument('--run', action='store_true')
    options.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if not args.run and not args.verify_existing:
        OUTPUT.mkdir(exist_ok=False)
        helper.prepare()
        # Freeze both this adapter and all measurement/preflight dependencies.
        source = driver_sources()
        for name, expected in source.items():
            raw = (ROOT / name).read_bytes()
            helper.need(hashlib.sha256(raw).hexdigest() == expected, 'DRIVER_FREEZE_CHANGED')
            target = OUTPUT / 'driver-source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        write(OUTPUT / 'driver-freeze.json', {
            'schema': 'HH-GT06-F25-FUNCTIONAL-DRIVER-1', 'source_files': source,
            'run_ids': [helper.run_id(lane[0]) for lane in helper.LANES],
            'helper_freeze_sha256': digest(helper.OUTPUT / 'freeze.json'),
            'formal_acceptance': False,
        })
        verify_envelope()
        print(json.dumps({'prepared': True, 'output': str(OUTPUT), 'engine_runs': 0}), flush=True)
        return 0
    verify_envelope()
    if args.verify_existing:
        return helper.verify_existing()
    return run_once()


if __name__ == '__main__':
    raise SystemExit(main())
