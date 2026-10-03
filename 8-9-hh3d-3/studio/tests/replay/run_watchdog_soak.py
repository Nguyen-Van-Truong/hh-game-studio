"""O9.1 watchdog-only soak; never starts Godot or creates a Docker container."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_environment as environment
from studio.tests.replay import run_benchmark_campaign as campaign

SOAK_SCHEMA = 'HH-GT06-O9-WATCHDOG-SOAK-1'


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def source_manifest() -> dict[str, str]:
    # Reuse the campaign's verified import closure so observer-only runs bind
    # the same Docker/query modules as a formal watchdog. Add this runner
    # explicitly because it is the entry point rather than a campaign import.
    campaign.load_fixture()
    files = campaign.source_files()
    relative = Path(__file__).relative_to(STUDIO).as_posix()
    files[relative] = digest(Path(__file__))
    return dict(sorted(files.items()))


def closure(files: dict[str, str]) -> str:
    raw = ''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode()
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def run(root: Path, seconds: int, interval: float) -> int:
    if root.exists():
        raise RuntimeError('SOAK_OUTPUT_EXISTS')
    if type(seconds) is not int or seconds < 1800:
        raise ValueError('SOAK_DURATION')
    if not 1 <= interval <= 10:
        raise ValueError('SOAK_INTERVAL')
    root.mkdir(parents=True)
    files = source_manifest()
    binding = {'run_id': root.name, 'source_closure_sha256': closure(files),
               'campaign_sha256': hashlib.sha256((SOAK_SCHEMA + root.name).encode()).hexdigest()}
    started = time.monotonic()
    write_new(root / 'soak-context.json', {
        'schema': SOAK_SCHEMA, **binding, 'duration_seconds': seconds,
        'interval_seconds': interval, 'source_files': files,
        'formal_acceptance': False, 'godot_started': False,
        'docker_create_started': False, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    watchdog = environment.Watchdog(
        root,
        lambda: campaign.environment_snapshot(docker_inventory=[]),
        binding,
        campaign.write,
        docker_probe=environment.running_containers,
        # O9.1d is an observer soak. Resource/foreign-engine policy events are
        # retained and replayed, while only mandatory harness failures stop it.
        observation_only=True)
    primary = None
    try:
        with environment.KeepAwake():
            while time.monotonic() - started < seconds:
                watchdog.poll(force=True)
                remaining = seconds - (time.monotonic() - started)
                time.sleep(max(0.2, min(interval, remaining)))
    except BaseException as error:
        primary = error
    finally:
        try:
            watchdog.close()
        except BaseException as error:
            primary = primary or error
    elapsed = time.monotonic() - started
    if primary is None:
        try:
            environment.verify_watchdog(root, campaign.read_regular, elapsed_seconds=elapsed,
                                        expected_binding=binding, require_docker_inventory=True,
                                        observation_only=True)
        except BaseException as error:
            primary = error
    result = {'schema': SOAK_SCHEMA, **binding, 'actual_exit_code': 0 if primary is None else 1,
              'elapsed_seconds': round(elapsed, 3), 'sample_stream_closed': watchdog.stream.closed,
              'event_stream_closed': watchdog.event_stream.closed,
              'verified_watchdog': primary is None, 'formal_acceptance': False,
              'error_code': getattr(primary, 'code', type(primary).__name__) if primary else None}
    write_new(root / 'soak-result.json', result)
    if primary is not None:
        raise primary
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--interval', type=float, default=5)
    args = parser.parse_args()
    return run(Path(args.output), args.seconds, args.interval)


if __name__ == '__main__':
    raise SystemExit(main())
