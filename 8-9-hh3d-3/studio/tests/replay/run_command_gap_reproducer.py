"""Short host-only command-gap reproducer; never starts Godot or Docker.

The delay is injected at one loopback lookup boundary so the diagnostic proves
that phase timestamps and the unchanged 2-second status gate observe the stall.
It does not claim to reproduce the scheduler cause from formal21.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_commands
from studio.tests.replay import run_benchmark_campaign as campaign


SCHEMA = 'HH-GT06-COMMAND-GAP-REPRODUCER-1'
RUN_ID = re.compile(r'gt06-[a-z0-9-]{1,35}\Z')


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()


def run(root: Path, run_id: str, delay_seconds: float) -> int:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('REPRODUCER_RUN_ID')
    if root.exists():
        raise RuntimeError('REPRODUCER_OUTPUT_EXISTS')
    if not 2.1 <= delay_seconds <= 3.0:
        raise ValueError('REPRODUCER_DELAY')
    root.mkdir(parents=True)
    source_files = campaign.source_files()
    source_files[Path(__file__).relative_to(STUDIO).as_posix()] = sha(Path(__file__))
    source_files = dict(sorted(source_files.items()))
    state = {'injected': False, 'command_id': None}
    original_lookup = benchmark_commands.FixtureClient.lookup

    def delayed_lookup(client, command_id):
        if command_id.endswith('.admitted.0') and not state['injected']:
            state['injected'] = True
            state['command_id'] = command_id
            time.sleep(delay_seconds)
        return original_lookup(client, command_id)

    producer = None
    report = None
    error = None
    try:
        benchmark_commands.FixtureClient.lookup = delayed_lookup
        producer = benchmark_commands.CommandProducer(root / 'commands', run_id)
        report = producer.run_diagnostic()
    except BaseException as caught:
        error = caught
    finally:
        try:
            if producer is not None:
                producer.close()
        finally:
            benchmark_commands.FixtureClient.lookup = original_lookup
    if report is None:
        write_new(root / 'reproducer-result.json', {
            'schema': SCHEMA, 'run_id': run_id, 'actual_exit_code': 1,
            'formal_acceptance': False, 'root_cause_proven': False,
            'source_files': source_files,
            'error_code': getattr(error, 'code', type(error).__name__),
            'injected': state,
        })
        raise error
    result = {
        'schema': SCHEMA, 'run_id': run_id, 'actual_exit_code': 0,
        'formal_acceptance': False, 'root_cause_proven': False,
        'godot_started': False, 'docker_create_started': False,
        'delay_seconds': delay_seconds, 'injected': state,
        'source_files': source_files,
        'source_closure_sha256': campaign.closure(source_files),
        'report': report,
        'phase_snapshot': producer.phase_snapshot(),
        'journal_timing_snapshot': producer.journal_timing_snapshot(),
        'reproducer_conclusion': (
            'An injected loopback lookup delay crosses the unchanged 2-second '
            'host command-lane gate and is recorded with phase/journal data. '
            'This validates the boundary only; it does not identify the '
            'formal21 scheduler or journal cause.'
        ),
    }
    write_new(root / 'reproducer-result.json', result)
    if not state['injected'] or report.get('max_status_gap_ms', 0) <= 2000:
        raise RuntimeError('REPRODUCER_BOUNDARY_NOT_OBSERVED')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--delay-seconds', type=float, default=2.5)
    args = parser.parse_args(argv)
    return run(args.output, args.run_id, args.delay_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
