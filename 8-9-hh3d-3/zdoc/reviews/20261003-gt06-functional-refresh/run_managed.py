"""Current-source F06 supplement; preserve the historical S65 fault anchor.

Reuse the unchanged S138 repair/replay verifier. The shared kernel guard
excludes a concurrent benchmark, but no measurement marker is created: this
functional repair needs the Linux validator, whose measurement fence stays on.
"""
from contextlib import contextmanager
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.measure_window import default_path, plain

ORIGINAL = ROOT / 'zdoc/reviews/20260921-gt06-s138-coordinator/run_managed_refresh_s138.py'
OUTPUT = STUDIO / '.local/reviews/gt06-f25-managed-20261003-02'
spec = importlib.util.spec_from_file_location('f25_s138_managed', ORIGINAL)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
helper.OUTPUT = OUTPUT / 'managed'
helper.REPAIR = 'gt06-f25-managed-repair-02'
helper.REPLAY = 'gt06-f25-managed-replay-02'
# Both retained fault and repair verification lazily register script_profile.
# Register it consistently before freezing the interpreter's imported domain.
# This validates fixed declarative bytes only; it launches no engine.
helper.native.configuration('3.0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    helper.write(path, value)


def driver_sources():
    result = {'studio/' + name: value for name, value in campaign.source_files().items()}
    result[Path(__file__).relative_to(ROOT).as_posix()] = sha(Path(__file__))
    result[ORIGINAL.relative_to(ROOT).as_posix()] = sha(ORIGINAL)
    return result


def verify_freeze():
    value = helper.read(OUTPUT / 'driver-freeze.json')
    helper.native.need(value['source_files'] == driver_sources(), 'MANAGED_DRIVER_CHANGED')
    for name, digest in value['source_files'].items():
        helper.native.need(sha(OUTPUT / 'driver-source' / name) == digest, 'MANAGED_DRIVER_COPY')
    helper.native.need(value['managed_freeze_sha256'] == sha(helper.OUTPUT / 'freeze.json'), 'MANAGED_FREEZE_HASH')
    return helper.freeze()


@contextmanager
def functional_guard():
    """Use the same byte lock as measurement_window, never clear its marker."""
    import msvcrt
    marker = default_path()
    plain(marker)
    helper.native.need(not marker.exists(), 'MANAGED_MEASUREMENT_ACTIVE')
    guard = marker.with_suffix('.guard')
    plain(guard)
    fd = os.open(guard, os.O_CREAT | os.O_RDWR | os.O_BINARY, 0o600)
    locked = False
    try:
        info = os.fstat(fd)
        helper.native.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'MANAGED_GUARD_SHAPE')
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        locked = True
        helper.native.need(not marker.exists(), 'MANAGED_MEASUREMENT_ACTIVE')
        yield
    finally:
        try:
            if locked:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


def unused_lane(lane):
    raw = STUDIO / '.local/reviews' / (helper.REPAIR if lane == 'repair' else helper.REPLAY)
    helper.native.need(not (helper.OUTPUT / lane).exists() and not raw.exists(), 'MANAGED_NO_RETRY')


def run_lane(lane):
    unused_lane(lane)
    with functional_guard():
        verify_freeze()
        unused_lane(lane)
        if lane == 'replay':
            helper.verify('repair')
        admissions = OUTPUT / ('admission-' + lane)
        admissions.mkdir(exist_ok=True)
        numbers = [int(p.name) for p in admissions.iterdir() if p.is_dir() and p.name.isdigit()]
        attempt = admissions / str(max(numbers, default=0) + 1).zfill(4)
        attempt.mkdir(exist_ok=False)
        preflight = campaign.environment_preflight()
        write(attempt / 'preflight.json', preflight)
        campaign.require_environment_preflight(preflight)
        launch = attempt / 'launch'; launch.mkdir()
        source = campaign.source_files()
        campaign.observe_pair_launch(launch, {
            'run_id': helper.REPAIR if lane == 'repair' else helper.REPLAY,
            'source_files': source, 'source_closure_sha256': helper.native.closure(source),
            'campaign_sha256': sha(OUTPUT / 'driver-freeze.json'),
        }, verify_freeze)
        write(attempt / 'admitted.json', {'lane': lane, 'formal_acceptance': False})
        result = helper.run(lane)
        # S138 verifies its native domain; this adapter also owns the separate
        # preflight/driver domain, which must still match after native teardown.
        verify_freeze()
        write(attempt / 'result.json', {'lane': lane, 'verified': True,
              'actual_target': result['actual_target'], 'formal_acceptance': False})
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--lane', choices=('repair', 'replay'))
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        helper.native.need(not args.lane and not args.verify_existing, 'MANAGED_ARGUMENTS')
        OUTPUT.mkdir(exist_ok=False)
        helper.freeze()
        source = driver_sources()
        for name in source:
            target = OUTPUT / 'driver-source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        write(OUTPUT / 'driver-freeze.json', {'source_files': source,
              'managed_freeze_sha256': sha(helper.OUTPUT / 'freeze.json'), 'formal_acceptance': False})
        verify_freeze()
        print(json.dumps({'prepared': True, 'engine_runs': 0}), flush=True)
        return 0
    helper.native.need(args.lane is not None, 'MANAGED_LANE_REQUIRED')
    try:
        verify_freeze()
        result = helper.verify(args.lane) if args.verify_existing else run_lane(args.lane)
        print(json.dumps({'verified': True, 'lane': args.lane,
              'actual_target': result['actual_target'], 'formal_acceptance': False}), flush=True)
        return 0
    except Exception as error:
        failure = {'lane': args.lane, 'error_type': type(error).__name__,
                   'code': getattr(error, 'code', str(error) if isinstance(error, helper.native.ReplayError)
                                   else 'MANAGED_OPERATION_FAILED'),
                   'formal_acceptance': False, 'automatic_retry': False}
        for index in range(1, 1000):
            path = OUTPUT / ('failure-%04d.json' % index)
            if not path.exists():
                write(path, failure)
                break
        print(json.dumps(failure), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
