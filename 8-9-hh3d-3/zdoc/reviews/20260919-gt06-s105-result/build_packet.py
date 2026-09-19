"""One-time allowlisted retention; writes only its own new result directory."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

from verify_packet import RUN_SUFFIXES, canonical, derive, require, sha

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RAW = REPO / 'studio/.local/reviews'
CHILDREN = REPO / 'zdoc/reviews/20260919-gt06-s105-handles/owned'
TOP = ('context.json', 'source-files.json', 'diagnostic-result.json', 'child-failure.json',
       'child-terminal-cleanup.json', 'editor-snapshot.json', 'http-phases-final.json',
       'import-observation.json', 'initial-project-files.json')
HOST = ('invocation.json', 'process-start.json', 'process-exit.json', 'capture.json', 'stdout.txt', 'stderr.txt')
EXCLUDED = [
    {'scope': 'commands/**', 'reason': 'LOCAL_JOURNAL_COMMAND_STORE_AND_GUARDS'},
    {'scope': 'project/** except benchmark input.json,input/{ack,start}-NN.json,out/{batch,ready}-NN.json', 'reason': 'PROJECT_SOURCE_AND_GENERATED_CACHE_OUTSIDE_SELECTED_EVIDENCE'},
    {'scope': '{host-owner,editor-host,import-host}/{appdata,localappdata,temp,blender-user}/**', 'reason': 'PRIVATE_ENVIRONMENT_AND_GENERATED_CACHE'},
    {'scope': 'Any files not matched by the explicit retention allowlist', 'reason': 'NOT_SELECTED; NO_RECURSIVE_RAW_INVENTORY_OR_HASH_SWEEP'},
    {'scope': 'Secret-bearing material', 'reason': 'NO_SECRET_RETENTION; selected text receives a bounded high-confidence secret-pattern screen'},
]


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)


def secret_screen(raw, source):
    text = raw.decode('utf-8')
    require(not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_.\-]{16,}|\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}', text), 'SECRET_PATTERN:' + source)
    if source.endswith('.json'):
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    require(not (key.lower() in ('secret', 'token', 'password', 'authorization', 'credential', 'api_key', 'access_token') and child), 'SENSITIVE_JSON_KEY:' + source + ':' + key)
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(json.loads(text))


def main():
    require(not (HERE / 'manifest.json').exists(), 'PACKET_ALREADY_BUILT')
    selected = {}
    for suffix in RUN_SUFFIXES:
        run_id = 'gt06-s105-handles-' + suffix
        run = RAW / run_id
        paths = {run / name for name in TOP if (run / name).is_file()}
        for pattern in ('batch-capture-[0-9][0-9].json', 'command-[0-9][0-9].json', 'joint-[0-9][0-9].json', 'sample-preview-[0-9][0-9].json'):
            paths.update(run.glob(pattern))
        for host in ('host-owner', 'editor-host', 'import-host'):
            paths.update(run / host / name for name in HOST if (run / host / name).is_file())
            paths.update((run / host).glob('cleanup-[0-9][0-9][0-9].json'))
        for folder, patterns in (('project/benchmark/input', ('ack-[0-9][0-9].json', 'start-[0-9][0-9].json')),
                                 ('project/benchmark/out', ('batch-[0-9][0-9].json', 'ready-[0-9][0-9].json')),
                                 ('pss', ('batch-[0-9][0-9]-after-gate.json',))):
            for pattern in patterns:
                paths.update((run / folder).glob(pattern))
        if (run / 'project/benchmark/input.json').is_file():
            paths.add(run / 'project/benchmark/input.json')
        for source in sorted(paths):
            selected[source] = HERE / 'raw' / run_id / source.relative_to(run)
        selected[CHILDREN / (run_id + '.py')] = HERE / 'generated-children' / (run_id + '.py')
    domain_rows = {}
    for source, target in selected.items():
        require(target.resolve().is_relative_to(HERE), 'WRITE_SCOPE')
        raw = source.read_bytes()
        source_rel = source.relative_to(REPO).as_posix()
        secret_screen(raw, source_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        require(target.read_bytes() == raw, 'COPY_READBACK')
        domain_rows[source_rel] = {'sha256': sha(raw), 'size_bytes': len(raw), 'portable_path': target.relative_to(HERE).as_posix()}
    write(HERE / 'raw-selected-domain.json', {
        'schema': 'gt06-s105-selected-raw-domain-v1', 'authority': 0,
        'selection_only': True, 'complete_raw_roots_inventory': False,
        'scope': 'Selected original evidence from five raw roots plus five generated child scripts; no excluded-tree inventory or hashes.',
        'selected_file_count': len(domain_rows), 'selected_bytes': sum(v['size_bytes'] for v in domain_rows.values()),
        'selected_domain_sha256': sha(canonical(domain_rows)), 'files': domain_rows,
        'bounded_exclusions': EXCLUDED,
    })
    write(HERE / 'summary.json', derive(HERE))
    files = {}
    for p in sorted(HERE.rglob('*')):
        if p.is_file() and p.name not in ('manifest.json', 'verification.json'):
            raw = p.read_bytes()
            files[p.relative_to(HERE).as_posix()] = {'sha256': sha(raw), 'size_bytes': len(raw)}
    portable = {k: v for k, v in files.items() if k.startswith(('raw/', 'generated-children/'))}
    write(HERE / 'manifest.json', {
        'schema': 'gt06-s105-retained-result-packet-v1', 'authority': 0,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'formal_acceptance': False,
        'eligible_for_dataset': False, 'final_critic': False, 'full_run_pass': False,
        'portable_exact_copies': len(portable), 'portable_exact_bytes': sum(v['size_bytes'] for v in portable.values()),
        'portable_exact_domain_sha256': sha(canonical(portable)),
        'raw_domain_file': 'raw-selected-domain.json', 'derived_summary_file': 'summary.json',
        'source_byte_comparison': 'SELECTED_SOURCE_BYTES_READ_ONCE_AND_EXACT_COPY_READBACK; NOT_FULL_RUNTIME_REVALIDATION',
        'excluded_from_manifest': ['manifest.json (self)', 'verification.json (derived verifier output containing manifest hash)'],
        'files': files,
    })
    print(json.dumps({'status': 'BUILT_DIAGNOSTIC_PACKET', 'files': len(files), 'portable_exact_copies': len(portable)}))


if __name__ == '__main__':
    main()
