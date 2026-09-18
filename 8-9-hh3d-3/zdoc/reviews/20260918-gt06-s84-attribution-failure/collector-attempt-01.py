"""Read-only S82 attribution failure preservation; no runtime module imports.

python -B preserve.py collect   # exclusive creation; reads originals only
python -B preserve.py verify    # repeatable read-only bytes/static verification
python -B preserve.py seal      # exclusive exact-byte package manifest
"""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
RUN = 'gt06-s82-attribution-01'
RAW = ROOT / 'studio/.local/reviews' / RUN
LAUNCH = ROOT / 'zdoc/reviews/20260918-gt06-s82-attribution/launch'
ROOTS = {'run': RAW, 'launch': LAUNCH}
SOURCE = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
SEAL_EXCLUDES = {'package-manifest.json', 'package-manifest.sha256'}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def regular(path):
    for part in [path, *path.parents]:
        stat = part.lstat()
        assert not part.is_symlink() and not getattr(stat, 'st_file_attributes', 0) & 0x400, str(part)


def digest(path):
    regular(path)
    before = path.stat()
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    return value.hexdigest()


def load(path):
    regular(path)
    return json.loads(path.read_bytes())


def write(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    regular(path.parent)
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)


def exclusion(relative):
    parts = Path(relative).parts
    if any(p.lower() in {'.godot', '__pycache__', 'appdata', 'localappdata'} for p in parts):
        return 'Generated cache or isolated per-process user settings; metadata only, no content read/hash/copy'
    if re.search(r'(?i)(?:^|/)(?:\.env(?:\..*)?|.*(?:token|secret|credential|password).*|.*\.(?:pem|pfx|p12|key|keystore))$', relative):
        return 'Sensitive filename class; metadata only, no content read/hash/copy'
    return None


def inventory(base):
    regular(base)
    files, excluded = [], []
    for path in sorted(base.rglob('*')):
        regular(path)
        if not path.is_file():
            continue
        stat = path.stat()
        relative = path.relative_to(base).as_posix()
        row = dict(path=relative, bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
        reason = exclusion(relative)
        if reason:
            excluded.append(dict(**row, reason=reason, sha256=None))
        else:
            row['sha256'] = digest(path)
            files.append(row)
    return dict(files=files, excluded_metadata_only=excluded)


def screen(data, relative):
    # Limited credential-pattern/key screen, not a claim of universal absence.
    assert not re.search(rb'(?i)(?:Bearer\s+[a-z0-9_\-.]{12,}|-----BEGIN[^\r\n]*PRIVATE KEY-----|sk-[a-zA-Z0-9]{20,})', data), relative
    if relative.startswith('source/'):
        return  # Controlled source may declare security/schema keys without credentials.
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert not re.search(r'(?:^|_)(?:token|secret|password|credential|authorization|api_key)(?:$|_)', key, re.I), (relative, key)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    if relative.endswith('.json'):
        walk(json.loads(data))
    elif relative.endswith('.jsonl'):
        for line in data.splitlines():
            if line.strip():
                walk(json.loads(line))


def closure(mapping):
    return hashlib.sha256(''.join(p + '\0' + mapping[p] + '\n' for p in sorted(mapping)).encode()).hexdigest()


def ref_check(ref):
    path = RAW / ref['file']
    assert path.resolve().is_relative_to(RAW)
    assert path.stat().st_size == ref['size_bytes'] and digest(path) == ref['sha256'], ref['file']


def facts():
    diagnostic, context = load(RAW / 'diagnostic.json'), load(RAW / 'context.json')
    mapping = load(RAW / 'source-files.json')
    terminal = load(RAW / 'child-terminal-cleanup.json')
    failure = load(RAW / 'child-failure.json')
    overlay = load(RAW / 'native-overlay.json')
    assert mapping == context['source_files'] == diagnostic['base_source_files']
    assert len(mapping) == 51 and closure(mapping) == SOURCE
    assert diagnostic['base_source_closure_sha256'] == context['source_closure_sha256'] == terminal['source_closure_sha256'] == SOURCE
    assert diagnostic['profile_sha256'] == context['profile_sha256'] == terminal['profile_sha256'] == digest(RAW / 'benchmark-profile.json') == PROFILE
    assert context['campaign_sha256'] == digest(RAW / 'diagnostic.json')
    assert diagnostic['eligible_for_dataset'] is False and diagnostic['full_benchmark'] is False
    assert failure['code'] == terminal['primary_error']['code'] == 'CAMPAIGN_RSS_GROWTH'
    assert failure['completed_batches'] == terminal['completed_batches'] == 6
    assert failure['phase'] == terminal['phase'] == {'batch': 5, 'phase': 'joint_observation'}
    assert diagnostic['maximum_batches'] == 35 and diagnostic['run_count'] == 1
    source_rows = []
    for name, expected in sorted(mapping.items()):
        frozen = digest(RAW / 'source/studio' / name)
        current = digest(ROOT / 'studio' / name)
        assert frozen == current == expected, name
        source_rows.append(dict(path=name, expected_sha256=expected, frozen_sha256=frozen, live_at_preservation_sha256=current))
    helpers = []
    for name, expected in sorted(diagnostic['helper_files'].items()):
        frozen = digest(RAW / 'source' / name)
        current = digest(ROOT / name)
        assert frozen == current == expected, name
        helpers.append(dict(path=name, executed_sha256=expected, frozen_sha256=frozen, current_sha256=current))
    host_invocation = load(RAW / 'host-owner/invocation.json')
    assert host_invocation['source_files'] == {**{'studio/' + k: v for k, v in mapping.items()}, **diagnostic['helper_files']}
    assert load(RAW / 'import-host/invocation.json')['source_files'] == mapping
    editor_invocation = load(RAW / 'editor-host/invocation.json')
    for name, expected in editor_invocation['source_files'].items():
        assert digest(ROOT / 'studio' / name) == expected, name
    assert overlay['base_sha256'] == mapping['tests/replay/benchmark_native.gd']
    assert overlay['probe_sha256'] == diagnostic['helper_files']['zdoc/reviews/20260918-gt06-s82-attribution/object_probe.gd']
    assert overlay['effective_sha256'] == digest(RAW / 'project/addons/hh_benchmark/benchmark_native.gd')
    assert overlay['runtime_source_modified'] is False and overlay['thresholds_modified'] is False
    assert load(LAUNCH / 'dispatch.json')['script_sha256'] == diagnostic['helper_files']['zdoc/reviews/20260918-gt06-s82-attribution/diagnose_sequence.py']
    # Record scene serialization changes; never silently require unchanged bytes.
    snapshots = {name: load(RAW / name) for name in ['initial-project-files.json', 'editor-snapshot.json']}
    project_rows = []
    for name, expected in snapshots['editor-snapshot.json'].items():
        actual = digest(RAW / 'project' / name)
        project_rows.append(dict(path=name, expected_sha256=expected, actual_sha256=actual, matches=(actual == expected)))
    mismatch = [row for row in project_rows if not row['matches']]
    assert [row['path'] for row in mismatch] == ['scenes/fixture.tscn']
    saved_scene = digest(RAW / 'project/scenes/fixture.tscn')
    sample_rows, references, cancels = [], [], []
    samples = [load(RAW / f'sample-preview-{i:02d}.json') for i in range(6)]
    assert sorted(p.name for p in RAW.glob('batch-capture-*.json')) == [f'batch-capture-{i:02d}.json' for i in range(6)]
    baseline = samples[4]['memory']
    for index, sample in enumerate(samples):
        capture = load(RAW / f'batch-capture-{index:02d}.json')
        artifacts = {key: value for key, value in capture.items() if key != 'index'}
        for key, ref in artifacts.items():
            ref_check(ref)
            references.append(dict(batch=index, kind=key, **ref))
        command = load(RAW / f'command-{index:02d}.json')
        native = load(RAW / f'project/benchmark/out/batch-{index:02d}.json')
        joint = load(RAW / f'joint-{index:02d}.json')
        evidence = dict(profile_sha256=PROFILE, source_closure_sha256=SOURCE, run_id=RUN,
                        index=index, processes=sample['processes'], artifacts=artifacts, barrier_receipt=joint['barrier_receipt'])
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        assert sample['evidence_sha256'] == evidence_hash
        assert capture['index'] == command['index'] == native['index'] == joint['index'] == sample['index'] == index
        assert len(command['commands']) == 1000 and len(native['cycles']) == len(sample['cycles']) == 100
        assert Counter(row['kind'] for row in command['commands']) == {'inspect': 500, 'rejected': 300, 'admitted': 200}
        assert command['complete_command_mix'] is True
        assert all(row['saved_file_sha256'] == saved_scene for row in native['cycles'])
        assert native['pid'] == 32860 and sample['processes'] == joint['processes'] == samples[0]['processes']
        assert sample['warmup'] == (index < 5)
        cancel = command['cancel']
        assert cancel['terminal_status'] == 'CANCELED' and cancel['no_effect'] is True
        assert cancel['command_id'] == sample['stop_target_instance_id']
        assert cancel['receipt_ms'] == sample['stop_receipt_ms']
        cancels.append(dict(batch=index, command_id=cancel['command_id'], receipt_ms=cancel['receipt_ms'], terminal_status=cancel['terminal_status'], no_effect=cancel['no_effect']))
        breaches = []
        if index >= 5:
            for role, keys in [('host', ['rss_bytes', 'held_handles']), ('editor', ['rss_bytes', 'held_handles', 'objects', 'resources'])]:
                for key in keys:
                    value, base = sample['memory'][role][key]['value'], baseline[role][key]['value']
                    if (value * 100 > base * 110 if key == 'rss_bytes' else value > base):
                        breaches.append(dict(role=role, metric=key, value=value, baseline=base))
            if sample['max_status_gap_ms'] > 2000:
                breaches.append(dict(metric='max_status_gap_ms', value=sample['max_status_gap_ms'], limit=2000))
        sample_rows.append(dict(index=index, warmup=sample['warmup'], memory=sample['memory'], max_status_gap_ms=sample['max_status_gap_ms'], screen_breaches=breaches))
    assert len(references) == 36 and len({row['command_id'] for row in cancels}) == 6
    assert baseline['editor']['rss_bytes']['value'] == 758169600
    assert samples[5]['memory']['editor']['rss_bytes']['value'] == 881020928
    assert samples[5]['max_status_gap_ms'] == 2044.2252
    assert all(s['memory']['editor']['objects']['value'] == 71128 for s in samples[4:])
    census = load(RAW / 'project/benchmark/out/object-0000.json')
    assert census['label'] == 'joint_baseline' and census['batch'] == 4 and census['inventory_complete_objectdb'] is False
    assert census['inventory_count'] == 27401 and census['unattributed_object_count'] == 43727
    assert census['counters_equal_across_collection'] is True
    assert len(census['initial_id_classes']) == census['inventory_count']
    assert [p.name for p in RAW.glob('project/benchmark/out/object-*.json')] == ['object-0000.json']
    assert load(RAW / 'host-owner/process-exit.json') == {'pid': 42832, 'exit_code': 1}
    assert load(RAW / 'import-host/process-exit.json') == {'pid': 23584, 'exit_code': 0}
    assert terminal['observations']['editor_owner']['helper_pid'] == 47556
    assert terminal['observations']['editor_owner']['helper_exit_code'] == 2
    assert terminal['observations']['editor_target']['actual_target_exit'] is None
    assert terminal['observations']['editor_target']['natural_exit_not_inferred'] is True
    cleanup = {name: load(RAW / name) for name in ['host-owner/cleanup-001.json', 'editor-host/cleanup-001.json', 'import-host/capture.json']}
    for name, record in cleanup.items():
        job = record['job']
        assert job['active_count'] == 0 and job['zero_observed'] and job['closed']
        assert not job['create_uncertain'] and not job['close_uncertain'] and not job['handle_retained'] and not job['failed_operations']
    absent_names = ['stop-request.json', 'editor-host/process-exit.json', 'editor-host/capture.json', 'host-owner/capture.json',
                    'supervisor-process-exit.json', 'process-exit.json', 'child-result.json', 'campaign.json', 'run-capture.json',
                    'assembly-manifest.json', 'assembled-run.json', 'dataset.json', 'summary.json',
                    'command-06.json', 'batch-capture-06.json', 'joint-06.json', 'sample-preview-06.json',
                    'project/benchmark/input/start-06.json', 'project/benchmark/input/ack-06.json',
                    'project/benchmark/out/batch-06.json', 'project/benchmark/out/index.json', 'project/benchmark/out/object-0001.json']
    absences = {name: not os.path.lexists(RAW / name) for name in absent_names}
    assert all(absences.values())
    stop_paths = {label: [p.relative_to(base).as_posix() for p in base.rglob('stop-request.json')] for label, base in ROOTS.items()}
    assert all(not rows for rows in stop_paths.values())
    return dict(authority=0, formal_acceptance=False, eligible_for_dataset=False, status='FAILED_DIAGNOSTIC_PARTIAL',
                run_id=RUN, primary_failure=failure, cleanup_terminal_utc=terminal['observed_utc'],
                source_closure_sha256=SOURCE, source_files=source_rows, profile_sha256=PROFILE,
                helper_files=helpers, overlay=overlay, host_invocation_bindings_verified=True,
                editor_invocation_bindings_verified=True, import_invocation_bindings_verified=True,
                binary_hash_scope='Invocation-declared binary hashes retained; native/Python binaries not rehashed in this packet',
                project_files=project_rows, scene_serialization_mismatches=mismatch, all_600_saved_scene_receipts_match=True,
                samples=sample_rows, artifact_references=references, cancel_receipts=cancels,
                baseline_census={k: census[k] for k in ['label', 'batch', 'inventory_count', 'unattributed_object_count', 'inventory_duration_us', 'counters_before', 'counters_after', 'counters_equal_across_collection', 'inventory_complete_objectdb']},
                captured_batches=6, warmup_batches=5, measured_captures_including_failure=1, remaining_batches=29, completed_full_runs=0,
                host_actual_exit=load(RAW / 'host-owner/process-exit.json'), import_actual_exit=load(RAW / 'import-host/process-exit.json'),
                editor_actual_exit=None, editor_helper=dict(pid=47556, exit_code=2), supervisor_actual_exit=None,
                supervisor_start=load(RAW / 'supervisor-start.json'), supervisor_return=load(RAW / 'supervisor-return.json'),
                child_terminal_cleanup=terminal, cleanup=cleanup, confirmed_absences=absences,
                stop_slots=[dict(root='run', path='stop-request.json', lexists=False)], recursive_stop_latches=stop_paths,
                next_native_ready_exists=(RAW / 'project/benchmark/out/ready-06.json').is_file(),
                gaps=[
                    'Editor PID32860 actual native exit is missing; helper PID47556 exit2 is separate.',
                    'Supervisor PID19068 actual exit receipt is missing; returned_exit_code1 is pre-exit self-report.',
                    'Host target actual exit1 is present, but host helper PID inventory is absent.',
                    'Import actual exit0 is present, but import helper PID and explicit wrapper-process-handle receipt are absent.',
                    'Only ACK4 baseline object census exists; no growth census or root-cause attribution.',
                    'Instrumented diagnostic is ineligible for official dataset regardless of outcome; six captures are not a full35-batch run.',
                    'Stable ObjectDB at this shorter prefix does not refute prior +2 growth or prove a fix.',
                    'RSS/status failure cause, including instrument overhead versus runtime behavior, is not established here.',
                    'No independent critic, engine/test run, or acceptance verdict is supplied by preservation.'
                ])


def collect():
    assert not (OUT / 'raw-locator-hashmaps.json').exists(), 'Collection already exists'
    before = {key: inventory(base) for key, base in ROOTS.items()}
    derived = facts()
    # Screen every selected file before writing any raw evidence copy.
    for key, group in before.items():
        for row in group['files']:
            screen((ROOTS[key] / row['path']).read_bytes(), row['path'])
    copies = []
    for key, group in before.items():
        for row in group['files']:
            source = ROOTS[key] / row['path']
            data = source.read_bytes()
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
            destination = 'raw/' + key + '/' + row['path']
            write(destination, data)
            assert digest(OUT / destination) == row['sha256']
            copies.append(dict(path=destination, raw_root=key, raw_path=row['path'], bytes=row['bytes'], sha256=row['sha256']))
    assert before == {key: inventory(base) for key, base in ROOTS.items()}, 'Original file set, bytes or mtimes changed'
    write('raw-locator-hashmaps.json', dict(created_utc=utc(), roots={k: str(v) for k, v in ROOTS.items()}, inventories=before,
        scope='Complete names/size/mtime inventory; all nonexcluded files exact-byte hashed twice. Cache/settings/sensitive filename classes metadata only, no payload hash or copy. No raw writes.',
        reparse_policy='Reject symlinks/reparse points; no traversal', originals_before_after_equal=True))
    write('preserved-byte-manifest.json', dict(created_utc=utc(), files=copies, raw_copy_policy='All eligible non-cache/non-sensitive raw files plus three launch records; exact unmodified bytes',
        sensitive_screen='Limited bearer/private-key/API-key bytes and sensitive JSON keys; controlled source is byte-pattern screened only; not universal absence proof'))
    write('terminal-facts.json', derived)
    write('collection.json', dict(created_utc=utc(), formal_acceptance=False, status='PRESERVATION_COLLECTED',
        nonexcluded_raw_files=len(copies), metadata_only_excluded=sum(len(v['excluded_metadata_only']) for v in before.values()),
        source_files=51, captured_batches=6, artifact_references=36, copied_bytes=sum(r['bytes'] for r in copies), originals_before_after_equal=True))
    print(json.dumps(load(OUT / 'collection.json')))


def verify():
    index = load(OUT / 'raw-locator-hashmaps.json')
    assert index['inventories'] == {key: inventory(Path(base)) for key, base in index['roots'].items()}
    rows = load(OUT / 'preserved-byte-manifest.json')['files']
    assert {r['path'] for r in rows} == {p.relative_to(OUT).as_posix() for p in (OUT / 'raw').rglob('*') if p.is_file()}
    for row in rows:
        path = OUT / row['path']
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
        assert digest(Path(index['roots'][row['raw_root']]) / row['raw_path']) == row['sha256']
    derived = facts()
    assert derived == load(OUT / 'terminal-facts.json')
    if (OUT / 'package-manifest.json').exists():
        manifest = load(OUT / 'package-manifest.json')
        assert digest(OUT / 'package-manifest.json') == (OUT / 'package-manifest.sha256').read_text().strip()
        assert {r['path'] for r in manifest['files']} | SEAL_EXCLUDES == {p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file()}
        for row in manifest['files']:
            assert (OUT / row['path']).stat().st_size == row['bytes'] and digest(OUT / row['path']) == row['sha256']
    result = dict(status='PRESERVATION_RECHECK_VERIFIED', formal_acceptance=False, raw_nonexcluded_files=len(rows), exact_copies=len(rows),
                  source_files=51, captured_batches=6, artifact_references=36, command_rows=6000, native_cycles=600,
                  completed_full_runs=0, primary_failure='CAMPAIGN_RSS_GROWTH', editor_actual_exit_missing=True, supervisor_actual_exit_missing=True,
                  verifier_scope='Static/byte recheck by preserving agent; not independent critic or runtime/test acceptance')
    print(json.dumps(result))
    return result


def seal():
    assert all(not (OUT / name).exists() for name in SEAL_EXCLUDES), 'Already sealed'
    verify()
    files = [dict(path=p.relative_to(OUT).as_posix(), bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest = dict(schema='HH-GT06-S84-ATTRIBUTION-FAILURE-PACKET-1', created_utc=utc(), authority=0, formal_acceptance=False,
                    run_id=RUN, status='FAILED_DIAGNOSTIC_PRESERVATION_ONLY', source_closure_sha256=SOURCE,
                    hash_domain='SHA256 exact bytes; all packet files except this manifest and digest sidecar; no self-reference', files=files)
    write('package-manifest.json', manifest)
    value = digest(OUT / 'package-manifest.json')
    write('package-manifest.sha256', (value + '\n').encode())
    verify()
    print(json.dumps(dict(packet_sha256=value, sealed_files=len(files), total_packet_files=len(files) + 2, formal_acceptance=False)))


if __name__ == '__main__':
    assert sys.argv[1:] in [['collect'], ['verify'], ['seal']]
    {'collect': collect, 'verify': verify, 'seal': seal}[sys.argv[1]]()
