"""Bounded O2 ClassDB reflection in a fresh worktree-local disposable project.

No scene mutation, runtime capability grant or GT06 evidence. Native owner is
the existing trusted-stage Job wrapper; source, version and process are bound.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
from studio.protocol.core import canonical_bytes, parse_json

SPEC = importlib.util.spec_from_file_location('o2_classdb_contract', STUDIO / 'godot-addon/authoring_contract.py')
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)
TYPES = {'bool': (1,), 'int': (2,), 'float': (3,), 'string': (4, 21),
         'vector2': (5,), 'vector3': (9,), 'enum': (2,), 'resource': (24,)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def compare(catalog, observation):
    """Compare reflection; candidate caps and native ranges are separate."""
    raw_classes = {c['class_name']: c for c in catalog.as_dict()['classes']}
    rows = observation.get('classes')
    if type(rows) is not list or len(rows) != len(raw_classes):
        raise ValueError('CLASSDB_CLASS_SET')
    names = [r['class_name'] for r in rows]
    if len(set(names)) != len(names) or set(names) != set(raw_classes):
        raise ValueError('CLASSDB_CLASS_SET')
    findings = []
    for row in rows:
        name = row['class_name']
        expected = catalog.classes[name]
        if row['exists'] is not True:
            findings.append(dict(class_name=name, code='MISSING_NATIVE_CLASS'))
            continue
        if row['parent'] != raw_classes[name]['native_base']:
            findings.append(dict(class_name=name, code='NATIVE_BASE', expected=raw_classes[name]['native_base'], observed=row['parent']))
        if expected.kind == 'singleton':
            if row['singleton'] is not True:
                findings.append(dict(class_name=name, code='NOT_NATIVE_SINGLETON'))
        elif row['can_instantiate'] is not True:
            findings.append(dict(class_name=name, code='NOT_INSTANTIABLE'))
        observed_properties = row['properties']
        if (type(observed_properties) is not list or len(observed_properties) != len(expected.properties) or
                {p['name'] for p in observed_properties} != set(expected.properties)):
            raise ValueError('CLASSDB_PROPERTY_SET')
        for property_row in observed_properties:
            pname = property_row['name']
            matches = property_row['matches']
            if type(matches) is not list or len(matches) != 1 or matches[0]['name'] != pname:
                findings.append(dict(class_name=name, property=pname, code='MISSING_OR_AMBIGUOUS_PROPERTY'))
                continue
            prop = matches[0]
            policy = expected.properties[pname]
            if type(prop['type']) is not int or prop['type'] not in TYPES[policy.type]:
                findings.append(dict(class_name=name, property=pname, code='VARIANT_TYPE', expected=policy.type, observed=prop['type']))
            if policy.writable and (not prop['setter'] or prop['usage'] & (1 << 28)):
                findings.append(dict(class_name=name, property=pname, code='NO_WRITABLE_SETTER'))
            if policy.type == 'resource' and policy.resource_base not in prop['hint_string'].split(','):
                findings.append(dict(class_name=name, property=pname, code='RESOURCE_BASE',
                                     expected=policy.resource_base, observed=prop['hint_string']))
    return findings


def source_files():
    # Source-only superset of trusted owner/protocol dependencies, frozen before
    # any run. No cache, accepted evidence, live project, or foreign game data.
    names = ['toolchain.lock.json', 'godot-addon/authoring_contract.py',
             'contracts/godot-authoring-schema-v1.json',
             'tests/godot/authoring_classdb_probe.gd', 'tests/godot/run_authoring_classdb_probe.py']
    for prefix in ('protocol', 'host', 'pipeline'):
        names.extend(p.relative_to(STUDIO).as_posix() for p in (STUDIO / prefix).rglob('*.py'))
    return {n: sha(STUDIO/n) for n in sorted(set(names))}


def run(binary, run_id):
    if not re.fullmatch(r'o2-classdb-[a-z0-9-]{1,32}', run_id):
        raise ValueError('RUN_ID')
    binary = binary.resolve(strict=True)
    lock = parse_json((STUDIO/'toolchain.lock.json').read_bytes())['godot']
    if sha(binary) != lock['console_sha256']:
        raise ValueError('PIN_HASH')
    catalog = contract.load_catalog()
    source = source_files()
    root = STUDIO/'.local/reviews'/run_id
    root.mkdir(parents=True, exist_ok=False)
    project = root/'project'
    project.mkdir()
    project.joinpath('project.godot').write_text('config_version=5\n[application]\nconfig/name="O2 ClassDB probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    shutil.copyfile(STUDIO/'tests/godot/authoring_classdb_probe.gd', project/'probe.gd')
    requested = {'classes': [dict(class_name=name, properties=sorted(spec.properties))
                            for name, spec in sorted(catalog.classes.items())]}
    project.joinpath('catalog-input.json').write_bytes(canonical_bytes(requested))
    project_hashes = {p.name: sha(p) for p in project.iterdir()}
    closure = hashlib.sha256(''.join(f'{n}\0{v}\n' for n,v in source.items()).encode()).hexdigest()
    save(root/'freeze.json', dict(source_files=source, source_closure=closure, binary_sha256=lock['console_sha256'],
                                  catalog_digest=catalog.digest, project_files=project_hashes, authority=0))
    def stage(name, args):
        out = root/name
        run_trusted_stage([str(binary), *args], cwd=project, output=out,
                          source_files=source, source_root=STUDIO, binary_sha256=lock['console_sha256'])
        capture = verify_captured_stage(out, sha(out/'capture.json'))
        stdout = (out/'stdout.txt').read_text(encoding='utf-8')
        stderr = (out/'stderr.txt').read_text(encoding='utf-8')
        if stderr.strip() or re.search(r'(?mi)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', stdout):
            raise ValueError('NATIVE_LOG_ERROR')
        if any(sha(project/n) != digest for n,digest in project_hashes.items()):
            raise ValueError('PROJECT_SOURCE_CHANGED')
        return capture, stdout
    try:
        _, version = stage('version', ['--version'])
        if version.strip() != lock['observed_version']:
            raise ValueError('PIN_VERSION')
        common = ['--headless', '--path', str(project), '--script', 'res://probe.gd']
        stage('parse', [*common, '--check-only'])
        capture, stdout = stage('reflection', common)
        markers = [s.removeprefix('HH_O2_CLASSDB ') for s in stdout.splitlines() if s.startswith('HH_O2_CLASSDB ')]
        if len(markers) != 1:
            raise ValueError('CLASSDB_MARKER_COUNT')
        observed = parse_json(markers[0])
        if (observed['schema'] != 'hh-o2-classdb-observation-1' or
                type(observed.get('pid')) is not int or observed['pid'] <= 0 or
                observed['catalog_input_sha256'] != project_hashes['catalog-input.json'] or
                observed['runtime_authorized'] is not False or observed['native_mutation'] is not False):
            raise ValueError('CLASSDB_BINDING')
        findings = compare(catalog, observed)
        if observed['pid'] != capture['actual_process_exit']['pid']:
            findings.append({'code': 'PROCESS_PID_BINDING_DIAGNOSTIC',
                             'observed_engine_pid': observed['pid'],
                             'captured_target_pid': capture['actual_process_exit']['pid']})
        result = dict(status='DRIFT' if findings else 'CLASSDB_MATCH', run_id=run_id,
                      source_closure=closure, findings=findings, observation=observed,
                      formal_acceptance=False, native_readback_undo=False, authority=0)
        save(root/'result.json', result)
        return result
    except Exception as error:
        save(root/'failure.json', dict(error=type(error).__name__, code=str(error), formal_acceptance=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--godot', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    result = run(args.godot, args.run_id)
    print(json.dumps({k:v for k,v in result.items() if k != 'observation'}))
    sys.exit(1 if result['findings'] else 0)
