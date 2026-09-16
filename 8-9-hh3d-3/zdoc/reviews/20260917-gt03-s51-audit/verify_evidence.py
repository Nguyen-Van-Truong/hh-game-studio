"""S51 offline diagnostic consistency audit. AUTHORITY=0; no acceptance.

Reuse the exact hash-pinned S49 raw-source/process/executor auditor. Bind the
S51 components and exact semantic parity packages explicitly. No engine or
daemon calls are made; native records remain historical host evidence.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
LEGACY = AUDIT.parent / '20260917-gt03-s49-audit/verify_evidence.py'
LEGACY_SHA256 = 'ad040b4512fbdfd865131a7d281ca958fad853cee36b1c21e3e0b2870338271f'
EXPECTED_CLOSURE = '55f15f2a431b8b065565143d456bd4cafbc59bca78a99492e3674ef93a97007c'
EXPECTED_TESTS = 471  # Actual completed S51 raw marker/stderr and clean capture.
COMPONENTS = AUDIT.parent / '20260917-gt03-s51-components-01'
SEMANTIC = AUDIT.parent / '20260917-gt03-s51-semantic-04'
COMPONENTS_HELPER_SHA256 = 'af144df7107fe1dbaba4f2f8242452962a9d514805255f70b4eb31bcea9ea55e'
OLD_MARKER, MARKER = 'S49_IDLE_BODY_AFTER_HOST_DEATH', 'S51_IDLE_BODY_AFTER_HOST_DEATH'
SEMANTIC_CASES = ('defaults_override', 'script_replaced', 'transformed_box',
                  'typed_scene_override', 'tiny_export', 'nested_node')


def load_legacy(path=LEGACY):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA256:
        raise ValueError('S49 auditor dependency hash changed')
    if raw.count(OLD_MARKER.encode()) != 2:
        raise ValueError('S49 auditor marker binding changed')
    spec = importlib.util.spec_from_file_location('s51_pinned_audit_helpers', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(raw.replace(OLD_MARKER.encode(), MARKER.encode()), str(path), 'exec'), module.__dict__)
    module.AUDIT = AUDIT
    module.PACKAGE = AUDIT.parent / '20260917-gt03-s51-editor-01'
    module.LINUX = AUDIT.parent / '20260917-gt03-s51-linux-01'
    module.PROFILE = AUDIT.parent / '20260917-gt03-s51-profile-01'
    module.HOST_DEATH = AUDIT.parent / '20260917-gt03-s51-host-death-01'
    module.EXPECTED_TESTS = EXPECTED_TESTS
    module.EXPECTED_ENGINE_CHECKS = {'edit': 103, 'reopen': 10, 'contract': 31}
    return module


H = load_legacy()


def shape(value, keys, message):
    H.need(type(value) is dict and set(value) == set(keys), message)


def principal_inventory(package, artifacts):
    prefix = package.relative_to(H.ROOT).as_posix() + '/'
    listed = {name[len(prefix):]: digest for name, digest in artifacts.items() if name.startswith(prefix)}
    H.need(listed == H.inventory(package), 'mandatory S51 package inventory omitted/added: ' + package.name)


def verify_components():
    path = AUDIT / 'components_check.py'
    H.need(type(COMPONENTS_HELPER_SHA256) is str and H.sha(path) == COMPONENTS_HELPER_SHA256,
           'S51 component helper not frozen or changed')
    helper = H.module('s51_pinned_components', path)
    return helper.verify(COMPONENTS)


def editor_parity(case, bundle, semantic, source, comparator):
    """Recompute one live-editor observation from exact raw process/log files."""
    saved = H.read(case / 'editor-observation.json')
    shape(saved, {'passed', 'host', 'inputs_unchanged', 'logs_clean', 'observation',
                  'observation_source', 'binary_sha256'}, 'semantic editor record shape')
    for flag in ('passed', 'inputs_unchanged', 'logs_clean'):
        H.need(saved.get(flag) is True, 'semantic editor missing fact: ' + flag)
    H.need(saved['observation_source'] == 'editor-engine.log', 'semantic editor log substitution')
    lock = H.read(source / 'toolchain.lock.json')['godot']
    H.need(saved['binary_sha256'] == lock['gui_sha256'], 'semantic editor binary pin')
    stdout, stderr = H.host(case, saved['host'])
    H.need(saved['host']['argv'] == [lock['gui_executable'], '--headless', '--editor', '--path',
           '$SNAPSHOT/.', '--log-file', 'engine.log', 'res://scenes/fixture.tscn'], 'semantic editor fixed argv')
    log = (case / 'editor-engine.log').read_text(encoding='utf-8', errors='strict')
    H.need(not H.BAD_LOG.search(stdout + '\n' + stderr + '\n' + log), 'semantic editor dirty log')
    reports = H.markers(log, 'HH_EDITOR_SEMANTIC ')
    H.need(len(reports) == 1 and H.exact(reports[0], saved['observation']), 'semantic editor raw report differs')
    report = reports[0]
    shape(report, {'schema', 'public_ack', 'context_kind', 'editor_hint', 'engine_version', 'pid', 'snapshot'},
          'semantic editor report shape')
    H.need(report['schema'] == 'hh-editor-semantic-probe-1' and report['public_ack'] is False
           and report['context_kind'] == 'live_editor' and report['editor_hint'] is True
           and report['engine_version'] == '4.7.2-stable (official)'
           and H.integer(report['pid'], saved['host']['target_pid']), 'semantic editor native context/PID')
    snapshot = report['snapshot']
    shape(snapshot, {'ok', 'code', 'generation', 'revision', 'state', 'total', 'offset',
                     'history_id', 'held', 'filesystem_mutated'}, 'semantic editor snapshot shape')
    H.need(snapshot['ok'] is True and snapshot['code'] == 'SCENE_INSPECTED'
           and H.integer(snapshot['generation']) and snapshot['generation'] > 0
           and H.integer(snapshot['history_id']) and snapshot['history_id'] > 0
           and H.integer(snapshot['offset'], 0) and H.integer(snapshot['total'], len(semantic['state']['nodes']))
           and snapshot['held'] is False and snapshot['filesystem_mutated'] is False,
           'semantic live editor guard/history facts')
    inputs = {name: H.digest(raw) for name, raw in bundle.files.items()}
    overlay = 'addons/hh_studio/semantic_probe.gd'
    inputs[overlay] = H.sha(source / 'tests/godot/semantic_editor_probe.gd')
    inputs['addons/hh_studio/plugin.cfg'] = H.digest(bundle.files['addons/hh_studio/plugin.cfg'].replace(
        b'script="plugin.gd"', b'script="semantic_probe.gd"'))
    expected_inputs = {'files': inputs, 'overlay_paths': ['addons/hh_studio/plugin.cfg', overlay],
        'unchanged_bundle_paths': [name for name in bundle.files if name != 'addons/hh_studio/plugin.cfg']}
    H.need(H.exact(H.read(case / 'editor-inputs.json'), expected_inputs), 'semantic editor exact trusted overlay')
    left = comparator.semantic_state_bytes(semantic)
    right = comparator.factory.bundle_codec.canonical_bytes(snapshot['state'])
    H.need(left == right and snapshot['revision'] == semantic['revision'] == 'sha256:' + H.digest(right),
           'semantic candidate/editor exact JCS mismatch')
    H.need((case / 'linux-state.jcs').read_bytes() == left and (case / 'editor-state.jcs').read_bytes() == right,
           'semantic archived canonical bytes changed')
    return saved


def verify_semantic(files, closure):
    source, _ = H.source_copy(SEMANTIC, files, closure)
    capture = H.read(SEMANTIC / 'capture.json')
    H.need(capture.get('source_closure_sha256') == closure, 'semantic capture source mismatch')
    for flag in ('passed', 'snapshot_unchanged', 'origin_source_unchanged', 'windows_binary_unchanged'):
        H.need(capture.get(flag) is True, 'final semantic capture missing fact: ' + flag)
    for flag in ('public_ack', 'sandbox_acceptance', 'selected_state_verified'):
        H.need(capture.get(flag) is False, 'semantic diagnostic overclaim')
    stdout, stderr = H.host(SEMANTIC, capture['host'])
    H.need(not H.BAD_LOG.search(stdout + '\n' + stderr), 'semantic outer host streams')
    code = ('import importlib.util,sys;from pathlib import Path;'
        'p=Path("tests/godot/run_semantic_probe.py").resolve();'
        's=importlib.util.spec_from_file_location("frozen_semantic",p);'
        'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
        'sys.exit(m.frozen_cases(Path(sys.argv[1]),Path(sys.argv[2])))')
    lock = H.read(source / 'toolchain.lock.json')['godot']
    H.need(capture['host']['argv'] == ['python.exe', '-B', '-c', code, SEMANTIC.name, lock['gui_executable']],
           'semantic outer fixed invocation')
    profile = H.module('s51_semantic_profile', source / 'tests/godot/run_profile_probe.py')
    comparator = H.module('s51_semantic_comparator', source / 'godot-addon/profile_readback.py')
    executor = H.module('s51_semantic_executor', source / 'godot-addon/linux_executor.py')
    linux_probe = H.module('s51_semantic_linux_binding', source / 'tests/godot/run_linux_probe.py')
    factory = comparator.factory
    cases = profile.cases(factory)
    cases.insert(1, ('script_replaced', cases[0][1], cases[0][2].replace(b'int = 9', b'int = 11')))
    H.need(tuple(row[0] for row in cases) == SEMANTIC_CASES, 'semantic exact six-case coverage')
    rows = []
    for name, scene, script in cases:
        case = SEMANTIC / name
        files_ = {path: H.inside(case / 'input', path).read_bytes() for path in factory.bundle_codec.PATHS}
        H.need(H.inventory(case / 'input') == {key: H.digest(raw) for key, raw in files_.items()}, 'semantic input inventory')
        bundle = factory.bundle_codec.decode_bundle((case / 'manifest.json').read_bytes(), files_)
        expected = factory.compose(scene, script, scene_revision='sha256:' + '1' * 64, engine_sha256=executor.BINARY_SHA256)
        H.need(bundle.manifest_bytes == expected.manifest_bytes and dict(bundle.files) == dict(expected.files),
               'semantic exact frozen candidate: ' + name)
        factory.qualify(bundle)
        native = H.verify_executor(case / 'executor', executor, linux_probe,
                                   mode='profile-validate', timeout=20, inputs=files_)
        raw_stdout = (case / 'executor/engine-stdout.txt').read_text(encoding='utf-8', errors='strict')
        raw_stderr = (case / 'executor/engine-stderr.txt').read_text(encoding='utf-8', errors='strict')
        linux = profile.evaluate(native, raw_stdout, raw_stderr, bundle, comparator)
        H.need(linux.get('passed') is True and linux.get('comparison', {}).get('semantic_observed') is True
               and H.exact(linux, H.read(case / 'linux-observation.json')), 'semantic raw native candidate readback')
        editor = editor_parity(case, bundle, linux['observation']['semantic'], source, comparator)
        rows.append({'name': name, 'passed': True, 'linux': linux, 'public_ack': False, 'editor': editor,
                     'exact_state_bytes_equal': True, 'exact_revision_equal': True, 'editor_hash_recomputed': True})
        if name == 'defaults_override':
            H.need(H.exact(H.read(SEMANTIC / 'validation-run-semantic-baseline.json'),
                {'result': native, 'stdout': raw_stdout, 'stderr': raw_stderr, 'scene': scene.decode(), 'script': script.decode()}),
                'semantic actual replay fixture differs from native baseline')
    H.need(rows[0]['linux']['comparison']['semantic_revision'] != rows[1]['linux']['comparison']['semantic_revision'],
           'script-only replacement did not change exact semantic revision')
    expected_summary = {'passed': True, 'cases': rows, 'public_ack': False, 'sandbox_acceptance': False,
                        'script_replacement_changed_revision': True}
    H.need(H.exact(H.read(SEMANTIC / 'semantic-cases.json'), expected_summary)
           and H.exact(capture.get('cases'), expected_summary), 'semantic summary differs from raw recomputation')
    return {'cases': 6, 'exact_jcs_parity': True, 'script_replacement_changed_revision': True,
            'public_ack': False, 'selected_state_verified': False, 'sandbox_acceptance': False}


def verify():
    H.need(H.integer(EXPECTED_TESTS) and EXPECTED_TESTS > 0, 'actual completed S51 unit count not yet bound')
    H.EXPECTED_TESTS = EXPECTED_TESTS
    manifest = H.read(H.PACKAGE / 'source-closure.json')
    H.need(manifest.get('source_closure_sha256') == EXPECTED_CLOSURE, 'wrong S51 final frozen closure')
    summary = H.verify()
    summary['components'] = verify_components()
    summary['semantic'] = verify_semantic(manifest['files'], EXPECTED_CLOSURE)
    artifacts = H.read(AUDIT / 'artifact-manifest.json')['files']
    for package in (COMPONENTS, SEMANTIC): principal_inventory(package, artifacts)
    summary.update(status='S51_DIAGNOSTIC_CHECKPOINT_VERIFIED', authority=0, acceptance=False,
                   formal_acceptance=False, public_ack=False, reused_auditor_sha256=LEGACY_SHA256,
                   components_helper_sha256=COMPONENTS_HELPER_SHA256, host_death_marker=MARKER)
    return summary


if __name__ == '__main__':
    H.need(len(sys.argv) <= 2, 'usage: verify_evidence.py [index|HEAD]')
    summary = verify()
    if len(sys.argv) == 2: H.git_bytes(summary, sys.argv[1])
    destination = AUDIT / ('verification.json' if len(sys.argv) == 1 else 'git-byte-verification-' + sys.argv[1] + '.json')
    destination.write_text(H.json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(H.json.dumps(summary))
