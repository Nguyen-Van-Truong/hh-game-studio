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
OUTPUT = STUDIO / '.local/reviews/gt06-f25-functional-20261003-02'
PREFIX = 'gt06-f25'
spec = importlib.util.spec_from_file_location('f25_existing_service_refresh', ORIGINAL)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.OUTPUT = OUTPUT / 'lanes'
helper.run_id = lambda label: PREFIX + '-' + label + '-02'


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
    for name, expected in value['source_files'].items():
        helper.need(digest(ROOT / name) == expected, 'DRIVER_SOURCE_CHANGED')
    helper.need(value['helper_freeze_sha256'] == digest(helper.OUTPUT / 'freeze.json'), 'HELPER_FREEZE_CHANGED')
    helper.verify_freeze()
    return value


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
        files = campaign.source_files()
        source = {'studio/' + name: value for name, value in files.items()}
        source[Path(__file__).relative_to(ROOT).as_posix()] = digest(Path(__file__))
        source[ORIGINAL.relative_to(ROOT).as_posix()] = digest(ORIGINAL)
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
    helper.need(not (OUTPUT / 'run-attempt.json').exists(), 'RUN_ATTEMPT_EXISTS')
    write(OUTPUT / 'run-attempt.json', {'started_at': helper.utc(), 'formal_acceptance': False})
    clean = True
    try:
        with measurement_window('gt06-f25-functional-20261003-02',
                                'Seven functional lanes; not formal benchmark',
                                safe_to_release=lambda: clean):
            preflight = campaign.environment_preflight()
            write(OUTPUT / 'preflight.json', preflight)
            campaign.require_environment_preflight(preflight)
            launch = OUTPUT / 'launch'; launch.mkdir()
            # The launch sampler deliberately validates its exact 64-file
            # campaign domain. verify_envelope separately guards functional217.
            source = campaign.source_files()
            campaign.verify_sources(source)
            campaign.observe_pair_launch(launch, {
                'run_id': 'gt06-f25-functional-20261003-02',
                'source_files': source,
                'source_closure_sha256': helper.native.closure(source),
                'campaign_sha256': digest(OUTPUT / 'driver-freeze.json'),
            }, verify_envelope)
            clean = False
            code = helper.run()
            clean = code == 0
            write(OUTPUT / 'terminal.json', {'completed_at': helper.utc(),
                  'exit_code': code, 'verified_lanes': len(helper.LANES),
                  'cleanup_verified': clean, 'formal_acceptance': False})
            return code
    except Exception as error:
        helper.failure_receipt(error)
        write(OUTPUT / 'terminal.json', {'completed_at': helper.utc(),
              'exit_code': 1, 'error_type': type(error).__name__,
              'code': getattr(error, 'code', 'FUNCTIONAL_REFRESH_FAILED'),
              'cleanup_verified': clean, 'formal_acceptance': False})
        print(json.dumps({'completed': False, 'error_type': type(error).__name__,
                          'cleanup_verified': clean}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
