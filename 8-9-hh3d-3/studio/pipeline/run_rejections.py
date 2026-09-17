"""Run copied native-observation negatives under the existing bounded Python Job.

This does not import or modify a live engine/project. A fresh run captures its
own source bytes, process records and output, preserving every earlier attempt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import run_trusted_stage
from studio.pipeline.godot import consumer
from studio.pipeline.run_diagnostic import sha, source_map, write
from studio.pipeline.run_validation import freeze_stage_sources, need, owned_run


def run(consumer_id, validator_id, run_id):
    previous = owned_run(consumer_id)
    validation = owned_run(validator_id)
    root = owned_run(run_id)
    need(root not in (previous, validation), 'REJECTION_OUTPUT_INPUT_COLLISION')
    root.mkdir(exist_ok=False)
    script = STUDIO / 'tests/pipeline/check_native_observation_rejections.py'
    # The worker imports the consumer/comparator and its producer contract.
    # Include their complete fixed source directories even before worker import.
    extra = [script, STUDIO / 'pipeline/run_consumer.py']
    extra += list(consumer.HERE.glob('*'))
    extra += list((STUDIO / 'pipeline/producer').glob('*.py'))
    files = source_map([path for path in extra if path.is_file()])
    write(root / 'source-files.json', files)
    freeze_stage_sources(root, 'source', files)
    host = run_trusted_stage([sys.executable, '-B', str(script),
        '--consumer-root', str(previous), '--validation-root', str(validation),
        '--output-root', str(root / 'output')], cwd=root, output=root / 'host',
        source_root=STUDIO, source_files=files,
        binary_sha256=sha(Path(sys.executable).read_bytes()))
    raw = (root / 'output/result.json').read_bytes()
    report = json.loads(raw)
    marker = {'result_sha256': sha(raw), 'cases': 27,
        'all_expected_rejections_observed': True, 'formal_acceptance': False}
    prefix = b'GT05_REJECTIONS_COMPLETE '
    markers = [json.loads(line[len(prefix):])
        for line in (root / 'host/stdout.txt').read_bytes().splitlines() if line.startswith(prefix)]
    need(not (root / 'host/stderr.txt').read_bytes().strip()
         and markers == [marker] and len(report['cases']) == 27
         and report['bindings']['consumer_run_id'] == consumer_id
         and report['bindings']['validator_run_id'] == validator_id
         and all(row['rejected'] is True and row['actual_error'] == row['expected_error']
                 and bool(row['check_sites']) for row in report['cases']), 'REJECTION_RESULT_BINDING')
    write(root / 'rejections.json', {'schema': 'HH-GT05-REJECTIONS-CAPTURE-1',
        'run_id': run_id, 'consumer_run_id': consumer_id, 'validator_run_id': validator_id,
        'host_capture_sha256': sha((root / 'host/capture.json').read_bytes()),
        'result_sha256': sha(raw), 'completed': host['completed'], 'formal_acceptance': False})
    print(json.dumps({'run_id': run_id, **marker}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-id', required=True)
    parser.add_argument('--validator-id', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    run(args.consumer_id, args.validator_id, args.run_id)
