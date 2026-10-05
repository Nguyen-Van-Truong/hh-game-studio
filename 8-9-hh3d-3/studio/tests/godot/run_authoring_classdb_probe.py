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
         'vector2': (5,), 'vector3': (9,), 'rect2': (7,), 'enum': (2,), 'resource': (24,)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def compare(catalog, observation):
    """Compare reflection; candidate caps and native ranges are separate."""
    raw_classes = {c['class_name']: c for c in catalog.as_dict()['classes']}
    resources = observation.get('resource_types')
    if type(resources) is not list or len(resources) != len(catalog.resource_bases):
        raise ValueError('CLASSDB_RESOURCE_SET')
    lineage = {}
    for resource in resources:
        if type(resource) is not dict or set(resource) != {'class_name', 'exists', 'inheritance'}:
            raise ValueError('CLASSDB_RESOURCE_SHAPE')
        name, ancestors = resource['class_name'], resource['inheritance']
        if (type(name) is not str or name not in catalog.resource_bases or name in lineage or
                type(resource['exists']) is not bool or type(ancestors) is not list or
                any(type(base) is not str or not re.fullmatch(r'[A-Z][A-Za-z0-9_]*', base)
                    for base in ancestors) or len(ancestors) > 64 or
                len(set(ancestors)) != len(ancestors)):
            raise ValueError('CLASSDB_RESOURCE_SHAPE')
        if resource['exists']:
            if not ancestors or ancestors[0] != name or ancestors[-1] != 'Object':
                raise ValueError('CLASSDB_RESOURCE_INHERITANCE')
        elif ancestors:
            raise ValueError('CLASSDB_RESOURCE_INHERITANCE')
        lineage[name] = ancestors
    rows = observation.get('classes')
    if type(rows) is not list or len(rows) != len(raw_classes):
        raise ValueError('CLASSDB_CLASS_SET')
    names = [r['class_name'] for r in rows]
    if len(set(names)) != len(names) or set(names) != set(raw_classes):
        raise ValueError('CLASSDB_CLASS_SET')
    findings = [dict(class_name=name, code='NOT_NATIVE_RESOURCE')
                for name, ancestors in lineage.items() if 'Resource' not in ancestors]
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
            if policy.type == 'resource':
                # A catalog may safely narrow Material to ShaderMaterial. Exact
                # string equality rejected this even though native ClassDB accepts
                # the subtype. Require the observed native RESOURCE_TYPE hint and
                # a reflected ancestor; do not invent inheritance from class names.
                hints = prop['hint_string'].split(',') if type(prop['hint_string']) is str else []
                if (type(prop['hint']) is not int or prop['hint'] != 17 or
                        not hints or any(not re.fullmatch(r'[A-Z][A-Za-z0-9_]*', h) for h in hints) or
                        not any(base in lineage[policy.resource_base] for base in hints)):
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


def resolve_direct_engine(binary, lock):
    """Prefer the GUI executable so the captured PID is the Godot process.

    The pinned Windows ``*_console.exe`` is a launcher which creates the
    actual engine process.  Capturing its launcher PID and comparing it with
    ``OS.get_process_id()`` therefore reports a false binding drift.  The
    sibling GUI executable from the same verified release is the direct
    engine and still accepts redirected stdout/stderr under the trusted Job.
    """
    binary = binary.resolve(strict=True)
    if sha(binary) == lock['gui_sha256']:
        return binary, lock['gui_sha256'], 'gui-direct'
    if sha(binary) == lock['console_sha256'] and binary.name.lower().endswith('_console.exe'):
        sibling = binary.with_name(binary.name[:-len('_console.exe')] + '.exe')
        if sibling.is_file() and sha(sibling) == lock['gui_sha256']:
            return sibling, lock['gui_sha256'], 'console-input-resolved-to-gui-direct'
    raise ValueError('PIN_HASH')


def resolve_console(binary, lock):
    """Return the matching console twin used only for the version receipt."""
    binary = binary.resolve(strict=True)
    if sha(binary) == lock['console_sha256']:
        return binary, lock['console_sha256']
    if sha(binary) == lock['gui_sha256'] and binary.name.lower().endswith('.exe'):
        sibling = binary.with_name(binary.stem + '_console.exe')
        if sibling.is_file() and sha(sibling) == lock['console_sha256']:
            return sibling, lock['console_sha256']
    raise ValueError('PIN_CONSOLE_HASH')


def run(binary, run_id):
    if not re.fullmatch(r'o2-classdb-[a-z0-9-]{1,32}', run_id):
        raise ValueError('RUN_ID')
    lock = parse_json((STUDIO/'toolchain.lock.json').read_bytes())['godot']
    requested_binary = binary.resolve(strict=True)
    binary, binary_sha256, binary_mode = resolve_direct_engine(requested_binary, lock)
    version_binary, version_sha256 = resolve_console(requested_binary, lock)
    catalog = contract.load_catalog()
    source = source_files()
    root = STUDIO/'.local/reviews'/run_id
    root.mkdir(parents=True, exist_ok=False)
    project = root/'project'
    project.mkdir()
    project.joinpath('project.godot').write_text('config_version=5\n[application]\nconfig/name="O2 ClassDB probe"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    shutil.copyfile(STUDIO/'tests/godot/authoring_classdb_probe.gd', project/'probe.gd')
    requested = {'resource_types': sorted(catalog.resource_bases),
                 'classes': [dict(class_name=name, properties=sorted(spec.properties))
                            for name, spec in sorted(catalog.classes.items())]}
    project.joinpath('catalog-input.json').write_bytes(canonical_bytes(requested))
    project_hashes = {p.name: sha(p) for p in project.iterdir()}
    closure = hashlib.sha256(''.join(f'{n}\0{v}\n' for n,v in source.items()).encode()).hexdigest()
    save(root/'freeze.json', dict(source_files=source, source_closure=closure, binary_sha256=binary_sha256,
                                  version_binary_sha256=version_sha256,
                                  binary_mode=binary_mode, binary_path_role='gui_executable',
                                  catalog_digest=catalog.digest, project_files=project_hashes, authority=0))
    def stage(name, args, stage_binary=binary, stage_sha256=binary_sha256):
        out = root/name
        run_trusted_stage([str(stage_binary), *args], cwd=project, output=out,
                          source_files=source, source_root=STUDIO, binary_sha256=stage_sha256)
        capture = verify_captured_stage(out, sha(out/'capture.json'))
        stdout = (out/'stdout.txt').read_text(encoding='utf-8')
        stderr = (out/'stderr.txt').read_text(encoding='utf-8')
        if stderr.strip() or re.search(r'(?mi)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', stdout):
            raise ValueError('NATIVE_LOG_ERROR')
        if any(sha(project/n) != digest for n,digest in project_hashes.items()):
            raise ValueError('PROJECT_SOURCE_CHANGED')
        return capture, stdout
    try:
        _, version = stage('version', ['--version'], version_binary, version_sha256)
        if version.strip() != lock['observed_version']:
            raise ValueError('PIN_VERSION')
        common = ['--headless', '--path', str(project), '--script', 'res://probe.gd']
        stage('parse', [*common, '--check-only'])
        capture, stdout = stage('reflection', common)
        markers = [s.removeprefix('HH_O2_CLASSDB ') for s in stdout.splitlines() if s.startswith('HH_O2_CLASSDB ')]
        if len(markers) != 1:
            raise ValueError('CLASSDB_MARKER_COUNT')
        observed = parse_json(markers[0])
        if (observed['schema'] != 'hh-o2-classdb-observation-2' or
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
                      source_closure=closure, binary_mode=binary_mode, findings=findings, observation=observed,
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
