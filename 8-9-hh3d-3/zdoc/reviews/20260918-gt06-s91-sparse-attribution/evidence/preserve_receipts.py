"""Preserve only the fixed S91 preflight, observer tests, and two smoke runs.

Offline byte copying and hash verification only. No engine, tests, task, or
source edits. Every destination is new; originals remain unchanged.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os

EVIDENCE = Path(__file__).resolve().parent
BASE = EVIDENCE.parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
PREFLIGHT = STUDIO / '.local/reviews/gt06-s91-sparse-attribution-preflight-01'
OBSERVERS = BASE / 'observer-tests-39648'
SMOKES = [STUDIO / '.local/reviews' / ('gt06-s91-sparse-smoke-' + number) for number in ('01', '02')]
RECEIPTS = ('capture.json', 'invocation.json', 'process-start.json', 'process-exit.json', 'stdout.txt', 'stderr.txt')


def need(value, message):
    if not value:
        raise RuntimeError(message)


def checked(path):
    path = Path(path).absolute()
    need(path.is_relative_to(ROOT), 'outside HH3D root')
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'reparse path')
    need(not any(part in ('.godot', '__pycache__') for part in path.parts), 'cache path')
    need(path.suffix.lower() not in ('.exe', '.dll', '.pyc', '.pdb'), 'binary/cache artifact')
    return path


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def raw(path):
    path = checked(path)
    need(path.is_file() and path.stat().st_size <= 2 * 1024**2, 'not a bounded regular file')
    return path.read_bytes()


def load(path):
    return json.loads(raw(path))


def emit(path, value):
    content = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with checked(path).open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    need(raw(path) == content, 'manifest readback')
    return digest(content)


selected = {}


def select(source, group, base, expected=None):
    source, base = checked(source), checked(base)
    need(source.is_relative_to(base), 'selection outside group root')
    copy = EVIDENCE / 'copies' / group / source.relative_to(base)
    if copy in selected:
        need(selected[copy][0] == source, 'copy collision')
        return
    data = raw(source)
    actual = digest(data)
    need(expected is None or actual == expected, 'frozen hash mismatch: ' + str(source))
    selected[copy] = source, group, data, actual


def capture_check(directory, expected_exit, expected_completed):
    capture = load(directory / 'capture.json')
    started, exited = load(directory / 'process-start.json'), load(directory / 'process-exit.json')
    need(started['pid'] == exited['pid'] and exited['exit_code'] == expected_exit, 'actual exit binding')
    need(capture['completed'] is expected_completed and capture['wrapper_exit_code'] == expected_exit, 'capture outcome')
    need(capture['job']['closed'] and capture['job']['zero_observed'] and not capture['job']['tainted'], 'Job cleanup')
    for name, expected in capture['artifacts'].items():
        need(name in RECEIPTS and digest(raw(directory / name)) == expected, 'capture artifact binding')
    return {'actual_exit': exited, 'completed': capture['completed'],
            'capture_sha256': digest(raw(directory / 'capture.json')),
            'job_zero_and_closed': True}


pre = load(PREFLIGHT / 'preflight.json')
diagnostic = load(PREFLIGHT / 'diagnostic.json')
need(pre['verified_import'] is True and pre['helper_files'] == diagnostic['helper_files'], 'preflight helper binding')
need(len(diagnostic['base_source_files']) == 51 and len(pre['helper_files']) == 6, 'preflight source count')
for name in ('benchmark-profile.json', 'context.json', 'diagnostic.json', 'native-overlay.json',
             'preflight.json', 'source-files.json', 'toolchain.lock.json'):
    select(PREFLIGHT / name, 'preflight01', PREFLIGHT)
for name in RECEIPTS:
    select(PREFLIGHT / 'import-host' / name, 'preflight01', PREFLIGHT)
frozen = {**{'studio/' + name: value for name, value in diagnostic['base_source_files'].items()}, **pre['helper_files']}
for name, expected in frozen.items():
    select(PREFLIGHT / 'source' / name, 'preflight01', PREFLIGHT, expected)
invocation = load(PREFLIGHT / 'import-host/invocation.json')
project_count = 0
for name, expected in invocation['source_files'].items():
    if name in diagnostic['base_source_files']:
        need(diagnostic['base_source_files'][name] == expected, 'import source binding')
        continue
    path = STUDIO / name
    need(path.is_relative_to(PREFLIGHT / 'project'), 'unexpected import source')
    select(path, 'preflight01', PREFLIGHT, expected)
    project_count += 1
current_helpers = []
for name, expected in pre['helper_files'].items():
    need(digest(raw(ROOT / name)) == expected, 'current frozen helper changed')
    current_helpers.append({'original': name, 'sha256': expected,
        'copy': ('copies/preflight01/source/' + name)})
outcomes = {'preflight01': capture_check(PREFLIGHT / 'import-host', 0, True)}

for mode, expected_exit in (('success', 0), ('wait', 2)):
    result = load(OBSERVERS / mode / 'result.json')
    need(result['passed'] is True and result['actual_popen_exit'] == expected_exit, 'observer result')
    need(result['process']['actual_exit']['exit_code_uint32'] == expected_exit
         and result['process']['handle_closed'] and result['popen_handle_closed'], 'observer exact exit/handles')
    need(result['job']['closed'] and result['job']['zero_observed'] and not result['job']['tainted'], 'observer Job')
    for name in ('result.json', 'supervisor-console-stdout.txt', 'supervisor-console-stderr.txt'):
        select(OBSERVERS / mode / name, 'observer-tests-39648', OBSERVERS)
outcomes['observer-tests-39648'] = {'success_actual_exit': 0, 'forced_actual_exit': 2,
    'native_and_popen_exits_match': True, 'jobs_zero_and_closed': True, 'handles_closed': True}

for smoke, expected_exit, passed in zip(SMOKES, (1, 0), (False, True)):
    group = 'smoke' + smoke.name[-2:]
    inputs, result = load(smoke / 'smoke-input.json'), load(smoke / 'smoke-result.json')
    need(result['passed'] is passed and result['run_id'] == smoke.name, 'smoke result')
    need(result['formal_acceptance'] is False and result['eligible_for_dataset'] is False, 'diagnostic only')
    for name in ('smoke-input.json', 'smoke-result.json'):
        select(smoke / name, group, smoke)
    if (smoke / 'output-manifest.json').exists():
        select(smoke / 'output-manifest.json', group, smoke)
    for name in RECEIPTS:
        select(smoke / 'native-host' / name, group, smoke)
    log = smoke / 'native-host/appdata/Godot/app_userdata/S91 Controlled Diagnostic/logs/godot.log'
    if log.exists():
        select(log, group, smoke)
    for name, expected in inputs['source_files'].items():
        select(smoke / 'source' / name, group, smoke, expected)
    for name in ('project.godot', 'smoke.gd'):
        source = smoke / 'project' / name
        expected = inputs['source_files'][source.relative_to(ROOT).as_posix()]
        select(source, group, smoke, expected)
    need(digest(raw(smoke / 'project/smoke.gd')) == inputs['generated_script_sha256'], 'generated smoke script')
    for source in sorted((smoke / 'project/out').rglob('*.json')):
        select(source, group, smoke)
    outcomes[group] = {**capture_check(smoke / 'native-host', expected_exit, passed), 'passed': passed,
        'run_id': smoke.name, 'original_failure': result.get('failure'),
        'harness_sha256': inputs['source_files'][(BASE / 'native_probe_smoke.py').relative_to(ROOT).as_posix()],
        'generated_script_sha256': inputs['generated_script_sha256']}
    if passed:
        need(result['capture_sha256'] == outcomes[group]['capture_sha256'], 'smoke02 capture binding')
        for arm, evidence in result['arms'].items():
            need(evidence['passed'] is True and evidence['exact_id_serialization'] is True, 'smoke02 arm')
            need(all(value is True for value in evidence['native_checks'].values()), 'smoke02 arm checks')
            for name, expected in evidence['artifacts'].items():
                need(digest(raw(smoke / 'project/out' / arm / name)) == expected, 'smoke02 arm artifact')

copies = EVIDENCE / 'copies'
need(not copies.exists(), 'packet already exists: never overwrite')
copies.mkdir()
rows = []
for copy, (original, group, content, expected) in sorted(selected.items()):
    checked(copy).parent.mkdir(parents=True, exist_ok=True)
    with copy.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    need(digest(raw(original)) == expected and digest(raw(copy)) == expected, 'copy or original drift')
    rows.append({'group': group, 'original': original.relative_to(ROOT).as_posix(),
        'copy': copy.relative_to(EVIDENCE).as_posix(), 'size_bytes': len(content),
        'original_sha256': expected, 'copy_sha256': expected})
manifest = {'schema': 'HH-GT06-S91-PRESERVATION-1', 'created_utc': datetime.now(timezone.utc).isoformat(),
    'original_path_base': '8-9-hh3d-3', 'copy_path_base': EVIDENCE.relative_to(ROOT).as_posix(),
    'formal_acceptance': False, 'eligible_for_dataset': False, 'file_count': len(rows),
    'counts_by_group': dict(Counter(row['group'] for row in rows)),
    'copied_bytes': sum(row['size_bytes'] for row in rows),
    'preflight_base_source_count': 51, 'preflight_helper_count': 6, 'preflight_project_source_count': project_count,
    'current_frozen_helpers': current_helpers, 'outcomes': outcomes, 'files': rows,
    'builder': {'file': Path(__file__).name, 'sha256': digest(raw(Path(__file__)))},
    'limits': ['Offline preservation only; no new engine or test execution.',
        'Smoke01 remains failed; smoke02 is a separate controlled smoke, not workload attribution.',
        'Preflight proves import and closure binding only; observer receipts cover short Python children.',
        'Caches, editor settings, executable binaries, older observer test runs, and long-run artifacts excluded.',
        'No claim of full S91 campaign completion, GT06 acceptance, or whole-ObjectDB attribution.']}
manifest_hash = emit(EVIDENCE / 'preservation-manifest.json', manifest)
emit(EVIDENCE / 'preservation-seal.json', {'manifest_file': 'preservation-manifest.json',
    'manifest_sha256': manifest_hash, 'file_count': len(rows), 'formal_acceptance': False})
print(json.dumps({'manifest_sha256': manifest_hash, 'file_count': len(rows),
    'counts_by_group': manifest['counts_by_group'], 'copied_bytes': manifest['copied_bytes'],
    'outcomes': outcomes}, indent=2))
