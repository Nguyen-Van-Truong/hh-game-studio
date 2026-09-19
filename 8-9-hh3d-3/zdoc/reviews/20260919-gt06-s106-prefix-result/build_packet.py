"""One-time bounded exact retention. No engine/runtime imports or process control."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from parse_prefix import HERE, RUN_ID, canonical, derive, need, read, sha

HH3D = HERE.parents[2]
RUN = HH3D / 'studio/.local/reviews' / RUN_ID
OUTER = RUN.with_name(RUN_ID + '-outer')
EXCLUSIONS = [
    {'scope': 'commands/**', 'reason': 'LOCAL_JOURNAL_COMMAND_STORE_GUARDS'},
    {'scope': 'project/** except benchmark input.json,input/{ack,start}-NN.json,out/{batch,ready}-NN.json', 'reason': 'GENERAL_PROJECT_SOURCE_AND_GENERATED_CACHES'},
    {'scope': '{host-owner,editor-host,import-host}/{appdata,localappdata,temp,blender-user}/**', 'reason': 'PRIVATE_ENVIRONMENT_AND_CACHE'},
    {'scope': 'All raw files not selected by explicit file-name allowlists', 'reason': 'NO_RECURSIVE_RAW_INVENTORY_OR_EXCLUDED_HASH_SWEEP'},
    {'scope': 'Runtime source closure and executables except two supporting Python sources', 'reason': 'HASH_AUDIT_ONLY_NO_BINARY_OR_FULL_RUNTIME_DUPLICATION'},
    {'scope': 'Secret-bearing material', 'reason': 'NOT_RETAINED; SELECTED_TEXT_HAS_BOUNDED_HIGH_CONFIDENCE_PATTERN_SCREEN'},
]


def write(path, value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def screen(raw, name):
    text = raw.decode('utf-8')
    need(not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_.\-]{16,}|\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}', text), 'SECRET_PATTERN:' + name)
    if name.endswith('.json'):
        def visit(v):
            if isinstance(v, dict):
                for k, child in v.items():
                    need(not (k.lower() in ('secret', 'token', 'password', 'authorization', 'credential', 'api_key', 'access_token') and child), 'SENSITIVE_KEY:' + name)
                    visit(child)
            elif isinstance(v, list):
                for child in v:
                    visit(child)
        visit(json.loads(text))


def main():
    need(not (HERE / 'manifest.json').exists(), 'PACKET_ALREADY_EXISTS')
    context = read(RUN / 'context.json'); request = read(OUTER / 'request.json')
    sources = {}
    top = ('context.json', 'source-files.json', 'diagnostic-result.json', 'child-failure.json',
           'child-terminal-cleanup.json', 'editor-snapshot.json', 'http-phases-final.json',
           'import-observation.json', 'initial-project-files.json', 'stop-request.json')
    paths = {RUN / name for name in top if (RUN / name).is_file()}
    for pattern in ('batch-capture-[0-9][0-9].json', 'command-[0-9][0-9].json', 'joint-[0-9][0-9].json', 'sample-preview-[0-9][0-9].json'):
        paths.update(RUN.glob(pattern))
    for folder in ('host-owner', 'editor-host', 'import-host'):
        for name in ('invocation.json', 'process-start.json', 'process-exit.json', 'capture.json', 'stdout.txt', 'stderr.txt'):
            p = RUN / folder / name
            if p.is_file():
                paths.add(p)
        paths.update((RUN / folder).glob('cleanup-[0-9][0-9][0-9].json'))
    for folder, patterns in (('project/benchmark/input', ('ack-[0-9][0-9].json', 'start-[0-9][0-9].json')),
                             ('project/benchmark/out', ('batch-[0-9][0-9].json', 'ready-[0-9][0-9].json')),
                             ('gates', ('batch-[0-9][0-9].json',)), ('pss', ('batch-[0-9][0-9].json',))):
        for pattern in patterns:
            paths.update((RUN / folder).glob(pattern))
    paths.add(RUN / 'project/benchmark/input.json')
    sources.update({p: HERE / 'raw' / p.relative_to(RUN) for p in paths})
    for name in ('request.json', 'process-start.json', 'process-exit.json', 'observer-close.json', 'observer-error.json', 'stdout.txt', 'stderr.txt'):
        p = OUTER / name
        if p.is_file():
            sources[p] = HERE / 'outer' / name
    for path, expected in context['diagnostic_files'].items():
        p = HH3D / path
        need(digest_file(p) == expected, 'FROZEN_SOURCE_HASH:' + path)
        sources[p] = HERE / 'frozen' / p.name
    observer = HH3D / 'zdoc/reviews/20260919-gt06-s106-coordinator/observe_runner.ps1'
    need(digest_file(observer) == request['observer_sha256'], 'OBSERVER_SOURCE_HASH')
    sources[observer] = HERE / 'observer/observe_runner.ps1'
    for name in ('run_benchmark_campaign.py', 'benchmark_profile.py'):
        sources[HH3D / 'studio/tests/replay' / name] = HERE / 'supporting-source' / name
    for path, expected in context['source_files'].items():
        need(digest_file(HH3D / 'studio' / path) == expected, 'LIVE_SOURCE_HASH:' + path)
    for path, expected in context['helper_original_pins'].items():
        need(digest_file(HH3D / path) == expected, 'LIVE_HELPER_HASH:' + path)
    python_sha = digest_file(Path(request['python']))
    godot_sha = digest_file(Path(context['godot_executable']))
    need(python_sha == request['python_sha256'] == context['python_sha256'], 'PYTHON_HASH')
    need(godot_sha == context['godot_sha256'], 'GODOT_HASH')
    selected = {}
    for source, target in sorted(sources.items()):
        need(target.resolve().is_relative_to(HERE), 'OUTPUT_SCOPE')
        raw = source.read_bytes(); source_name = source.relative_to(HH3D).as_posix()
        screen(raw, source_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        need(target.read_bytes() == raw, 'EXACT_COPY_READBACK')
        selected[source_name] = {'portable_path': target.relative_to(HERE).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw)}
    write(HERE / 'source-audit.json', {
        'schema': 'gt06-s106-prefix-selected-live-hash-audit-v1', 'observed_utc': datetime.now(timezone.utc).isoformat(),
        'authority': 0, 'formal_acceptance': False, 'all_selected_live_hashes_matched': True,
        'source_files': context['source_files'], 'diagnostic_files': context['diagnostic_files'],
        'helper_original_pins': context['helper_original_pins'], 'observer_sha256': request['observer_sha256'],
        'python_sha256_observed': python_sha, 'godot_sha256_observed': godot_sha,
        'stop_request_present': os.path.lexists(RUN / 'stop-request.json'),
        'runtime_stop_exercised': False,
        'method': 'Hash only the explicit 53 source paths, 6 frozen diagnostic paths, 4 original helper paths, observer and two executable paths. No raw cache/journal traversal.',
        'limits': 'Runtime files/executables are not copied, except 2 supporting sources. This is a recorded local audit; packet-only verification checks its bindings, not absent live bytes.'})
    write(HERE / 'raw-selected-domain.json', {
        'schema': 'gt06-s106-prefix-selected-original-domain-v1', 'authority': 0,
        'selection_only': True, 'complete_raw_roots_inventory': False,
        'selected_files': len(selected), 'selected_bytes': sum(v['size_bytes'] for v in selected.values()),
        'selected_domain_sha256': sha(canonical(selected)), 'files': selected, 'bounded_exclusions': EXCLUSIONS,
        'scope': 'Prefix raw and outer evidence, six frozen diagnostics, exact observer, two supporting runtime sources.'})
    write(HERE / 'summary.json', derive(HERE))
    files = {p.relative_to(HERE).as_posix(): {'sha256': digest_file(p), 'size_bytes': p.stat().st_size}
             for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in ('manifest.json', 'verification.json')}
    exact = {v['portable_path']: files[v['portable_path']] for v in selected.values()}
    write(HERE / 'manifest.json', {
        'schema': 'gt06-s106-prefix-retained-packet-v1', 'authority': 0, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'formal_acceptance': False, 'eligible_for_dataset': False, 'final_critic': False,
        'classification': 'NON_REPRODUCED', 'identical_prefix_branch': 'CLOSED_NO_IDENTICAL_RETRY',
        'portable_exact_files': len(exact), 'portable_exact_bytes': sum(v['size_bytes'] for v in exact.values()),
        'portable_exact_domain_sha256': sha(canonical(exact)), 'files': files,
        'excluded_from_manifest': ['manifest.json (self)', 'verification.json (derived output containing manifest hash)']})
    print(json.dumps({'status': 'BUILT_DIAGNOSTIC_PACKET', 'manifest_files': len(files), 'portable_exact_files': len(exact)}))


if __name__ == '__main__':
    main()
