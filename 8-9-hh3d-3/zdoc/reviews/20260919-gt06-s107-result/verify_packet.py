"""Verify portable S107 packet without engine imports or original raw roots."""
from pathlib import Path
import hashlib
import json
import types

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def closure(files):
    return sha(''.join(path+'\0'+files[path]+'\n' for path in sorted(files)).encode())


def need(ok, message):
    if not ok:
        raise ValueError('S107_PACKET_' + message)


def load(path):
    return json.loads(path.read_bytes())


def safe(root, name):
    path = Path(name)
    need(not path.is_absolute() and '..' not in path.parts and ':' not in name, 'PATH')
    return root / path


def verify(root=HERE):
    manifest = load(root/'manifest.json')
    for relative, digest in manifest['files'].items():
        need(sha(safe(root, relative).read_bytes()) == digest, 'FILE_HASH '+relative)
    raw = root/'raw'
    context, capture, result = (load(raw/name) for name in
                                ('context.json','capture-manifest.json','diagnostic-result.json'))
    need(len(context['source_files']) == 53 and closure(context['source_files']) ==
         context['source_closure_sha256'] == manifest['base_source_closure_sha256'], 'BASE_CLOSURE')
    need(closure(context['diagnostic_files']) == context['diagnostic_closure_sha256'], 'DIAGNOSTIC_CLOSURE')
    for original, digest in context['diagnostic_files'].items():
        need(sha((root/'frozen'/Path(original).name).read_bytes()) == digest, 'FROZEN_HELPER')
    for entry in capture['files']:
        data = safe(raw, entry['file']).read_bytes()
        need(len(data) == entry['size_bytes'] and sha(data) == entry['sha256'], 'RAW_CAPTURE_REF')
    need(result['status'] == 'CAPTURED' and not result['errors'] and
         result['formal_acceptance'] is False and result['eligible_for_dataset'] is False, 'RESULT')
    for role in ('host-owner','editor-host','import-host'):
        start, exit, stage = (load(raw/role/name) for name in
                              ('process-start.json','process-exit.json','capture.json'))
        need(start['pid'] == exit['pid'] == stage['actual_process_exit']['pid'] and
             exit['exit_code'] == stage['actual_process_exit']['exit_code'] ==
             stage['wrapper_exit_code'] == 0, 'ACTUAL_EXIT_'+role)
        job = stage['job']
        need(job['active_count'] == 0 and job['closed'] and job['zero_observed'] and
             not job['handle_retained'] and not job['close_uncertain'] and
             not job['tainted'] and not job['failed_operations'], 'JOB_'+role)
        if role != 'import-host':
            handle = stage['wrapper_process_handle']
            need(handle['closed'] and not handle['handle_retained'] and
                 not handle['close_uncertain'], 'WRAPPER_'+role)
    start, exit, closed, request = (load(root/'outer'/name) for name in
        ('process-start.json','process-exit.json','observer-close.json','request.json'))
    need(start['run_id'] == exit['run_id'] == context['run_id'] and start['pid'] == exit['pid'] and
         start['start_utc'] == exit['start_utc'] and exit['exit_code'] == 0 and
         start['handle_retained'] and closed['managed_process_disposed'] and
         not closed['native_close_bool_observed'], 'OUTER_EXIT')
    need(request['helper_sha256'] == sha((root/'frozen/run_probe.py').read_bytes()) and
         request['observer_sha256'] == sha((root/'observer/observe_runner.ps1').read_bytes()), 'OUTER_SOURCE')
    terminal = load(raw/'child-terminal-cleanup.json')
    need(terminal['primary_error'] is None and not terminal['errors'], 'TERMINAL')
    observation = terminal['observations']
    need(observation['editor_probe']['handle_retained'] is False and
         observation['editor_probe']['close_uncertain'] is False and
         not any(observation['editor_owner']['drain_threads_alive']) and
         observation['import_observer']['closed'] and
         observation['import_observer']['probe_handles_released'] and
         observation['import_observer']['global_held_probe_count'] == 0 and
         not observation['import_observer']['thread_alive'], 'CLEANUP')
    child = load(raw/'child-result.json')
    reader = types.ModuleType('_frozen_s107_packet_reader')
    reader_path = root/'frozen/read_preview.py'
    need(sha(reader_path.read_bytes()) == context['reader_sha256'], 'READER_PIN')
    exec(compile(reader_path.read_bytes(), str(reader_path), 'exec'), reader.__dict__)
    analysis = reader.analyze((raw/'editor-host/stdout.txt').read_bytes(),
                             (raw/'project/benchmark/out/preview-cost.json').read_bytes(),
                             (raw/'project/benchmark/out/index.json').read_bytes(),
                             child['analysis']['bindings'])
    need(analysis == child['analysis'], 'DERIVED_ANALYSIS')
    need(analysis['bindings']['pid'] == result['actual_exits']['editor-host']['actual_exit']['pid'] and
         analysis['bindings']['run_id'] == context['run_id'], 'READER_IDENTITY')
    return {'status':'VERIFIED_PACKET_ONLY','formal_acceptance':False,'eligible_for_dataset':False,
            'files':len(manifest['files']),'exact_copies':len(manifest['exact_copies']),
            'raw_capture_refs':len(capture['files']),'frozen_helpers':len(context['diagnostic_files']),
            'manifest_sha256':sha((root/'manifest.json').read_bytes()),
            'all_rows':len(analysis['observations']), 'outer_actual_exit':exit['exit_code'],
            'original_raw_roots_read':False,'engine_imported':False,
            'remaining_gaps':['import wrapper native handle close UNKNOWN','live Stop not exercised']}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
