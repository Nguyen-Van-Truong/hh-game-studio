"""Owned GT05 import/readback diagnostic from a completed fixed validator run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.godot import consumer
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
from studio.pipeline.run_diagnostic import sha, source_map, write
from studio.pipeline.run_validation import need, owned_run


def capture_preset(root, project, stage):
    raw = (project / 'input/fixture.glb.import').read_bytes()
    need(0 < len(raw) <= 1048576, 'GODOT_IMPORT_PRESET_CAP')
    with (root / (stage + '-preset.snapshot')).open('xb') as stream:
        stream.write(raw)
    return sha(raw)


def admitted(run_id):
    root = owned_run(run_id)
    validation = json.loads((root / 'validation.json').read_bytes())
    manifest_raw = (root / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    need(validation['completed'] is True and sha(manifest_raw) == validation['manifest_sha256']
         and verify_captured_stage(root / 'host', validation['host_capture_sha256'])['completed'],
         'VALIDATION_HOST_INCOMPLETE')
    glb = (root / 'fixture.glb').read_bytes()
    report_raw = (root / 'producer-report.json').read_bytes()
    native_validator = (root / 'validator.json').read_bytes()
    need(sha(glb) == manifest['artifacts']['fixture.glb']['sha256']
         and sha(report_raw) == manifest['producer_report_sha256']
         and sha(native_validator) == manifest['validator_sha256'], 'VALIDATION_INPUT_BINDING')
    verify_captured_stage(root / 'admission-host', validation['admission_capture_sha256'])
    admission = validation['admission_outputs']
    preflight_raw = (root / 'preflight.json').read_bytes()
    report = json.loads(preflight_raw)
    need(admission['artifact_sha256'] == sha(glb) == report['artifact_sha256']
         and sha(preflight_raw) == admission['preflight_sha256'] == manifest['preflight_sha256']
         and sha((root / 'semantic.json').read_bytes()) == admission['semantic_sha256']
         and report['semantic_sha256'] == manifest['semantic_sha256'], 'VALIDATION_PREFLIGHT_BINDING')
    return glb, manifest_raw, report_raw


def run(validator_id, run_id):
    glb, manifest, producer = admitted(validator_id)
    root = owned_run(run_id)
    root.mkdir(exist_ok=False)
    project = root / 'project'
    consumer.prepare(project, glb=glb, manifest=manifest, producer_report=producer)
    preset_before = capture_preset(root, project, 'input')
    need(preset_before == sha(consumer.PRESET.encode()), 'GODOT_AUTHORED_PRESET')
    extra = [p for p in (STUDIO / 'pipeline/godot').iterdir() if p.is_file()]
    extra += [p for p in project.rglob('*') if p.is_file() and p.suffix != '.import']
    extra += [STUDIO / name for name in ('tests/asset-profile.json',
        'contracts/naming-convention-v1.md', 'toolchain.lock.json')]
    files = source_map(extra)
    write(root / 'source-files.json', files)
    for name in files:
        # Source snapshots use normalized ordinal slots to avoid re-nesting an
        # already long .local path. The map still binds its exact logical path.
        target = root / 'source' / (sha(name.encode()) + Path(name).suffix)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    # The Windows console executable launches the GUI executable as another PID.
    # Launch the pinned engine directly so OS.get_process_id binds the owned child.
    binary = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    hosts = {}
    for phase in ('import', 'baseline'):
        hosts[phase] = run_trusted_stage(consumer.command(binary, project, phase),
            cwd=project, output=root / (phase + '-host'), source_root=STUDIO,
            source_files=files, binary_sha256=lock['gui_sha256'])
        stderr = (root / (phase + '-host') / 'stderr.txt').read_bytes()
        need(not stderr.strip(), 'GODOT_STDERR_REQUIRES_REVIEW')
    observed = consumer.verify_binding(project, phase='baseline',
        stdout=(root / 'baseline-host/stdout.txt').read_bytes())
    need(observed['pid'] == hosts['baseline']['actual_process_exit']['pid'], 'GODOT_PID_BINDING')
    checks = consumer.compare_observation(json.loads(producer), observed)
    preset_after = capture_preset(root, project, 'imported')
    write(root / 'comparison.json', checks)
    summary = {'schema': 'HH-GT05-CONSUMER-DIAGNOSTIC-1', 'run_id': run_id,
        'validator_run_id': validator_id, 'comparison': checks,
        'import_preset_before_sha256': preset_before, 'import_preset_after_sha256': preset_after,
        'host_captures': {phase: sha((root / (phase + '-host') / 'capture.json').read_bytes()) for phase in hosts},
        'observation_sha256': sha((project / 'out/baseline.json').read_bytes()),
        'formal_acceptance': False, 'public_ack': False}
    write(root / 'consumer.json', summary)
    print(json.dumps(summary))


def followup(consumer_id, run_id, phase, validator_id=None):
    """Resume an owned engine-stopped project without overwriting earlier logs."""
    need(phase in ('reimport', 'visual'), 'FOLLOWUP_PHASE')
    previous = owned_run(consumer_id)
    prior = json.loads((previous / 'consumer.json').read_bytes())
    project = previous / 'project'
    need(sha((project / 'out/baseline.json').read_bytes()) == prior['observation_sha256'], 'BASELINE_OBSERVATION_HASH')
    baseline_host = verify_captured_stage(previous / 'baseline-host', prior['host_captures']['baseline'])
    baseline = json.loads((project / 'out/baseline.json').read_bytes())
    need(baseline['pid'] == baseline_host['actual_process_exit']['pid'], 'BASELINE_PID')
    root = owned_run(run_id)
    root.mkdir(exist_ok=False)
    before = {name: (project / 'input' / name).read_bytes()
              for name in (*consumer.INPUTS, 'consumer.json')}
    for name, raw in before.items():
        target = root / 'previous-input' / name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(raw)
    if phase == 'reimport':
        need(validator_id is not None, 'REIMPORT_VALIDATOR_REQUIRED')
        glb, manifest, producer = admitted(validator_id)
        consumer.replace_inputs(project, glb=glb, manifest=manifest, producer_report=producer)
    else:
        need(validator_id is None, 'VISUAL_USES_CURRENT_INPUT')
        producer = before['producer-report.json']
    need(not (project / 'out' / (phase + '.json')).exists(), 'FOLLOWUP_OUTPUT_EXISTS')
    preset_before = capture_preset(root, project, 'input')
    extra = [p for p in (STUDIO / 'pipeline/godot').iterdir() if p.is_file()]
    extra += [project / name for name in consumer.SOURCES]
    extra += [project / 'input' / name for name in (*consumer.INPUTS, 'consumer.json')]
    extra += [STUDIO / name for name in ('tests/asset-profile.json', 'contracts/naming-convention-v1.md', 'toolchain.lock.json')]
    files = source_map(extra)
    write(root / 'source-files.json', files)
    for name in files:
        target = root / 'source' / (sha(name.encode()) + Path(name).suffix)
        target.parent.mkdir(exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    binary = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    hosts = {}
    for stage in (('import', phase) if phase == 'reimport' else (phase,)):
        hosts[stage] = run_trusted_stage(consumer.command(binary, project, stage),
            cwd=project, output=root / (stage + '-host'), source_root=STUDIO,
            source_files=files, binary_sha256=lock['gui_sha256'])
        need(not (root / (stage + '-host') / 'stderr.txt').read_bytes().strip(), 'GODOT_STDERR_REQUIRES_REVIEW')
    observed = consumer.verify_binding(project, phase=phase,
        stdout=(root / (phase + '-host') / 'stdout.txt').read_bytes())
    need(observed['pid'] == hosts[phase]['actual_process_exit']['pid'], 'GODOT_PID_BINDING')
    checks = consumer.compare_observation(json.loads(producer), observed)
    preset_after = capture_preset(root, project, 'imported')
    write(root / 'comparison.json', checks)
    write(root / 'followup.json', {'schema': 'HH-GT05-CONSUMER-FOLLOWUP-1',
        'consumer_run_id': consumer_id, 'validator_run_id': validator_id, 'phase': phase,
        'import_preset_before_sha256': preset_before, 'import_preset_after_sha256': preset_after,
        'comparison': checks, 'previous_input_sha256': {name: sha(raw) for name, raw in before.items()},
        'observation_sha256': sha((project / 'out' / (phase + '.json')).read_bytes()),
        'host_captures': {stage: sha((root / (stage + '-host') / 'capture.json').read_bytes()) for stage in hosts},
        'formal_acceptance': False, 'public_ack': False})
    print(json.dumps({'run_id': run_id, 'phase': phase, 'comparison': checks, 'formal_acceptance': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validator-id')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--consumer-id')
    parser.add_argument('--phase', choices=('baseline', 'reimport', 'visual'), default='baseline')
    args = parser.parse_args()
    if args.phase == 'baseline':
        need(args.validator_id is not None and args.consumer_id is None, 'BASELINE_ARGUMENTS')
        run(args.validator_id, args.run_id)
    else:
        need(args.consumer_id is not None, 'FOLLOWUP_CONSUMER_REQUIRED')
        followup(args.consumer_id, args.run_id, args.phase, args.validator_id)
