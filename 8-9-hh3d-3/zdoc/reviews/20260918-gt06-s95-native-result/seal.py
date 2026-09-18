"""Preserve the completed S95 diagnostic; no engine or acceptance claim."""
from pathlib import Path
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN = 'gt06-s95-native-isolation-01'
RAW = ROOT / 'studio/.local/reviews' / RUN
OUTER = RAW.with_name(RUN + '-outer')
PACK = BASE / 'evidence'


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def ref(path):
    raw = path.read_bytes()
    return {'sha256': sha(raw), 'size_bytes': len(raw)}


def verify_inputs():
    manifest = read(RAW / 'output-manifest.json')
    need(manifest['outcome'] == 'DIAGNOSTIC_COMPLETE' and manifest['formal_acceptance'] is False,
         'DIAGNOSTIC_SCOPE')
    for relative, expected in manifest['artifacts'].items():
        need(not Path(relative).is_absolute() and '..' not in Path(relative).parts, 'ARTIFACT_PATH')
        need(ref(RAW / relative) == expected, 'RAW_ARTIFACT_HASH:' + relative)
    pins = read(RAW / 'diagnostic.json')['pins']
    for relative, expected in pins['source_files'].items():
        need(sha((RAW / 'source/studio' / relative).read_bytes()) == expected, 'ARCHIVED_SOURCE:' + relative)
    for relative, expected in pins['helper_files'].items():
        path = RAW / 'source/zdoc/reviews/20260918-gt06-s95-native-isolation' / relative
        need(sha(path.read_bytes()) == expected, 'ARCHIVED_HELPER:' + relative)
    sys.path.insert(0, str(ROOT))
    from studio.pipeline.native_job import verify_captured_stage
    captures = {}
    for lane in ('import-host', 'editor-host', 'host-owner'):
        captures[lane] = verify_captured_stage(RAW / lane, manifest['artifacts'][lane + '/capture.json']['sha256'])
        need(captures[lane]['wrapper_process_handle'] == {
            'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False}, 'WRAPPER_HANDLE')
    for lane in ('import-host', 'editor-host'):
        terminal = read(RAW / (lane + '-terminal.json'))
        need(not terminal['cleanup_errors'] and terminal['owner']['closed'] is True
             and terminal['probe_handle_retained'] is False, 'NATIVE_OWNER_CLEANUP')
    outer = read(OUTER / 'terminal.json')
    need(outer['completed_diagnostic'] is True and not outer['errors'] and not outer['timed_out']
         and outer['supervisor_popen_actual_exit_code'] == 0
         and outer['actual_supervisor_exit']['actual_exit']['exit_code_uint32'] == 0
         and outer['actual_supervisor_exit']['handle_closed'] and outer['popen_handle_closed']
         and outer['outer_job_active_before_cleanup'] == 0, 'OUTER_EXIT')
    job = outer['job']
    need(job['zero_observed'] and job['closed'] and not job['tainted']
         and not job['handle_retained'] and not job['failed_operations'], 'OUTER_JOB')
    scheduler = read(BASE / 'scheduler-terminal.json')
    need(scheduler['scheduler']['state'] == 3 and scheduler['scheduler']['last_task_result'] == 0
         and scheduler['scheduler']['instances'] == 0 and scheduler['known_pids_current'] == [], 'SCHEDULER_TERMINAL')
    need(not (RAW / 'stop-request.json').exists(), 'STOP_LATCH')
    return manifest, pins


def main():
    need(sys.argv[1:] in ([], ['--verify']), 'USAGE')
    raw_manifest, pins = verify_inputs()
    if not sys.argv[1:]:
        PACK.mkdir(exist_ok=False)
        sources = {RAW / name for name in raw_manifest['artifacts']}
        sources.add(RAW / 'output-manifest.json')
        sources.update(p for p in (RAW / 'source').rglob('*') if p.is_file())
        sources.update(p for p in OUTER.iterdir() if p.is_file())
        sources.update((BASE / 'scheduler-terminal.json', BASE / 'scheduler-terminal.xml'))
        files = {}
        for source in sorted(sources):
            domain, parent = ('raw', RAW) if source.is_relative_to(RAW) else ('outer', OUTER) if source.is_relative_to(OUTER) else ('scheduler', BASE)
            relative = domain + '/' + source.relative_to(parent).as_posix()
            target = PACK / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            files[relative] = {**ref(source), 'source': source.relative_to(ROOT).as_posix()}
        manifest = {'authority': 0, 'run_id': RUN, 'formal_acceptance': False, 'eligible_for_dataset': False,
                    'source_closure_sha256': pins['source_closure_sha256'],
                    'helper_closure_sha256': pins['helper_closure_sha256'], 'files': files,
                    'scope': 'Exact diagnostic copies; isolated negative result is not absence of a leak or coupled benchmark PASS.'}
        (PACK / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    manifest = read(PACK / 'manifest.json')
    for relative, row in manifest['files'].items():
        need(ref(PACK / relative) == {k: row[k] for k in ('sha256', 'size_bytes')}, 'COPY_HASH:' + relative)
        need((PACK / relative).read_bytes() == (ROOT / row['source']).read_bytes(), 'COPY_BYTES:' + relative)
    print(json.dumps({'verified': True, 'formal_acceptance': False, 'exact_copies': len(manifest['files']),
                      'raw_artifacts': len(raw_manifest['artifacts']), 'source_files': len(pins['source_files']),
                      'manifest_sha256': sha((PACK / 'manifest.json').read_bytes())}))


if __name__ == '__main__':
    main()
