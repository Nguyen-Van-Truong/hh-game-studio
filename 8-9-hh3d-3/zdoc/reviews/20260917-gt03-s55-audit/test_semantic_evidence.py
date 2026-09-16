"""In-memory corruption checks; no evidence, native resource or storage writes."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('s55_semantic_negative_target', HERE / 'verify_semantic_evidence.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def changed(path, keys, value):
    obj = json.loads(path.read_bytes())
    current = obj
    for key in keys[:-1]:
        current = current[key]
    current[keys[-1]] = value
    return {path.resolve(): json.dumps(obj).encode()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'semantic-corruption-tests.json')
    args = parser.parse_args()
    target = args.output.resolve()
    audit.need(target.parent == HERE.resolve(), 'owned audit report required')
    audit.need(not target.exists(), 'immutable corruption report already exists')
    ev = audit.Evidence()
    files = audit.source(ev)
    mods = audit.modules()
    checks = []
    originals = {}
    audit.supporting_evidence(ev, files)
    units = audit.REVIEWS / '20260917-gt03-s55-units-01'
    inspection = audit.REVIEWS / '20260917-gt03-s55-recovery-inspection-native-01'
    unit_capture = json.loads((units / 'capture.json').read_bytes())
    unit_attempt = units / unit_capture['lanes']['other']['attempt']
    support_cases = [
        ('unit source closure', changed(units / 'invocation.json', ['source_closure_sha256'], '0' * 64)),
        ('unit controller binding', changed(units / 'runtime-source-reference.json', ['controller_sha256'], '0' * 64)),
        ('unit forged counts', changed(units / 'capture.json', ['counts', 'run'], 700)),
        ('unit raw actual exit', changed(unit_attempt / 'run-host.json', ['exit_code'], 9)),
        ('inspection actual exit', changed(inspection / 'native-host.json', ['exit_code'], 9)),
        ('inspection completion marker', { (inspection / 'native-stdout.txt').resolve(): b'NATIVE_INSPECTION_COMPLETE {}\n' }),
    ]
    for label, overlay in support_cases:
        originals.update({path: audit.sha(path.read_bytes()) for path in overlay})
        try:
            audit.supporting_evidence(audit.Evidence(overlay), files)
        except (ValueError, KeyError, TypeError, AssertionError) as error:
            checks.append({'lane': 'supporting', 'mutation': label, 'rejected': True, 'reason': str(error)})
        else:
            checks.append({'lane': 'supporting', 'mutation': label, 'rejected': False})
    for lane in ('stop', 'edit'):
        package = audit.REVIEWS / ('20260917-gt03-s55-' + lane + '-01')
        capture = json.loads((package / 'capture.json').read_bytes())
        snapshot = package / ('reopened.json' if lane == 'stop' else 'journal-snapshot.json')
        after = package / ('after.json' if lane == 'stop' else 'after-save.json')
        root = next((package / 'owned/editor').glob('editor-*'))
        scenes = root / 'project/scenes/fixture.tscn'
        terminal_response = package / ('save-response.json' if lane == 'stop' else 'edit.create-response.json')
        mutation_cases = [
            ('source reference closure', changed(package / 'source-reference.json', ['source_closure_sha256'], '0' * 64)),
            ('source reference inventory count', changed(package / 'source-reference.json', ['file_count'], 175)),
            ('raw host exit', changed(package / capture['host']['host'], ['exit_code'], 7)),
            ('raw host PID', changed(package / capture['host']['host'], ['target_pid'], capture['host']['target_pid'] + 1)),
            ('snapshot terminal response', changed(snapshot, ['commands', 0, 'response', 'status'], 'FORGED')),
            ('selected FileID', changed(snapshot, ['selected', 'selector_version', 'file_id'], '0' * 32)),
            ('readback semantic state', changed(after, ['state', 'nodes', 0, 'position', 0], 777)),
            ('readback files', changed(after, ['working_files', 'scenes/fixture.tscn', 'sha256'], '0' * 64)),
            ('actual selected bytes', {scenes.resolve(): b'corrupted scene'}),
            ('terminal wire content', changed(terminal_response, ['result', 'status'] if lane == 'stop' else ['status'], 'FORGED')),
        ]
        for label, overlay in mutation_cases:
            originals.update({path: audit.sha(path.read_bytes()) for path in overlay})
            altered = audit.Evidence(overlay)
            try:
                actual_lane, _ = audit.common(altered, package, files)
                events, snap, responses = audit.journal(altered, package, actual_lane, mods)
                audit.editor_evidence(altered, package, actual_lane, snap)
                audit.edit_observations(altered, package, actual_lane, snap, mods)
            except (ValueError, KeyError, TypeError, AssertionError) as error:
                checks.append({'lane': lane, 'mutation': label, 'rejected': True, 'reason': str(error)})
            else:
                checks.append({'lane': lane, 'mutation': label, 'rejected': False})
        if lane == 'edit':
            snap = json.loads(snapshot.read_bytes())
            observed = root / (snap['commands'][0]['edit_observation']['observation_id'] + '.json')
            overlay = changed(observed, ['semantic_state', 'nodes', 0, 'position', 0], 555)
            originals.update({path: audit.sha(path.read_bytes()) for path in overlay})
            try:
                audit.edit_observations(audit.Evidence(overlay), package, lane, snap, mods)
            except (ValueError, KeyError, TypeError, AssertionError) as error:
                checks.append({'lane': lane, 'mutation': 'raw edit observation', 'rejected': True, 'reason': str(error)})
            else:
                checks.append({'lane': lane, 'mutation': 'raw edit observation', 'rejected': False})
    edit = audit.REVIEWS / '20260917-gt03-s55-edit-01'
    native_root = HERE / 'native-exports01'
    native = native_root / edit.name
    native_cases = [
        ('Registry storage identity', changed(native / 'native-capture.json', ['storage_id'], '0' * 32)),
        ('Registry stream FileID', changed(native / 'native-capture.json', ['native_binding', 'stream', 'file_id'], '0' * 32)),
        ('selected manifest FileID', changed(native / 'native-capture.json', ['manifest_version', 'file_id'], '0' * 32)),
        ('native resources not closed', changed(native / 'native-capture.json', ['native_resources_closed'], False)),
        ('export actual exit', changed(native_root / 'native-export-host.json', ['exit_code'], 8)),
        ('native stream bytes', {(native / 'native-events.bin').resolve(): b'not a framed journal'}),
        ('native checkpoint blob', {next((native / 'blobs').iterdir()).resolve(): b'changed checkpoint'}),
    ]
    events, snap, _ = audit.journal(ev, edit, 'edit', mods)
    audit.custody_export(ev, edit, events, snap)
    for label, overlay in native_cases:
        originals.update({path: audit.sha(path.read_bytes()) for path in overlay})
        try:
            audit.custody_export(audit.Evidence(overlay), edit, events, snap)
        except (ValueError, KeyError, TypeError, AssertionError) as error:
            checks.append({'lane': 'native-export', 'mutation': label, 'rejected': True, 'reason': str(error)})
        else:
            checks.append({'lane': 'native-export', 'mutation': label, 'rejected': False})
    supplemental_lanes_tested = []
    for package in sorted(audit.REVIEWS.glob('20260917-gt03-s55-*')):
        if not (package / 'effective-execution.json').exists() or not (package / 'capture.json').exists():
            continue
        if json.loads((package / 'capture.json').read_bytes()).get('passed') is not True:
            continue
        lane, _ = audit.common(ev, package, files)
        supplemental_lanes_tested.append(lane)
        cases = [
            ('external driver bytes', {(package / 'driver.py').resolve(): (package / 'driver.py').read_bytes() + b'\n# changed\n'}),
            ('effective original probe hash', changed(package / 'effective-execution.json', ['original_probe_sha256'], '0' * 64)),
            ('effective runtime mutation claim', changed(package / 'invocation.json', ['effective_execution', 'runtime_modified'], True)),
            ('Stop still pending', changed(package / 'stop-terminal.json', ['response', 'stop_persistence'], 'PENDING')),
        ]
        for label, overlay in cases:
            originals.update({path: audit.sha(path.read_bytes()) for path in overlay})
            try:
                audit.common(audit.Evidence(overlay), package, files)
            except (ValueError, KeyError, TypeError, AssertionError) as error:
                checks.append({'lane': lane, 'mutation': label, 'rejected': True, 'reason': str(error)})
            else:
                checks.append({'lane': lane, 'mutation': label, 'rejected': False})
        if (package / 'response-wire.json').exists():
            wire = (package / 'response-wire.json').resolve()
            originals[wire] = audit.sha(wire.read_bytes())
            try:
                audit.journal(audit.Evidence({wire: b'changed HTTP response bytes'}), package, lane, mods)
            except (ValueError, KeyError, TypeError, AssertionError) as error:
                checks.append({'lane': lane, 'mutation': 'original HTTP response wire', 'rejected': True, 'reason': str(error)})
            else:
                checks.append({'lane': lane, 'mutation': 'original HTTP response wire', 'rejected': False})
    audit.need(audit.controller.inventory() == files, 'shared source changed')
    audit.need(all(audit.sha(path.read_bytes()) == digest for path, digest in originals.items()), 'historical evidence changed')
    audit.need(all(audit.sha((audit.ROOT / name).read_bytes()) == value for name, value in ev.files.items()), 'audit input changed')
    report = {'passed': all(row['rejected'] for row in checks), 'checks': checks,
              'verifier_sha256': audit.sha((HERE / 'verify_semantic_evidence.py').read_bytes()),
              'test_sha256': audit.sha(Path(__file__).read_bytes()), 'source_closure_sha256': audit.CLOSURE,
              'native_processes_started': 0, 'native_handles_opened': 0, 'mutations_in_memory_only': True,
              'supplemental_lanes_tested': supplemental_lanes_tested,
              'shared_source_unchanged': True, 'historical_evidence_unchanged': True,
              'tested_files_sha256': {path.relative_to(audit.ROOT).as_posix(): value for path, value in originals.items()},
              'gt03_acceptance': False}
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'passed': report['passed'], 'corruptions_rejected': sum(row['rejected'] for row in checks),
                      'total': len(checks), 'failures': [row for row in checks if not row['rejected']]}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
