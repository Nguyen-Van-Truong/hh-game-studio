"""Read-only S52 integration evidence audit. AUTHORITY=0; CANDIDATE only.

No editor, container, Registry, protected-file reopen or native mutation runs.
The portable inventory includes only evidence actually read by this checker,
the complete frozen source closures, and the pinned auditor dependency.
"""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
REVIEWS = AUDIT.parent
ROOT = REVIEWS.parent.parent
STUDIO = ROOT / 'studio'
HELPER = REVIEWS / '20260917-gt03-s49-audit/verify_evidence.py'
HELPER_SHA256 = 'ad040b4512fbdfd865131a7d281ca958fad853cee36b1c21e3e0b2870338271f'
HAPPY_LABELS = ('authenticated_discovery', 'foreign_bearer_denied', 'actual_editor_transform',
    'dirty_scene_differs_from_selection', 'authenticated_lease', 'authenticated_save_committed',
    'same_semantic_after_actual_reload', 'actual_new_editor_root', 'selected_project_changed',
    'history_boundary', 'duplicate_exact_reply_no_effect', 'control_lookup_exact_reply',
    'authenticated_stop', 'readonly_reopen_exact_selection', 'readonly_reopen_durable_commit',
    'readonly_reopen_selected_bundle')
STOP_LABELS = ('actual_editor_mutation', 'dirty_editor_differs_from_selection', 'authenticated_lease',
    'real_validator_entered_after_capture', 'actual_owned_linux_validator_running',
    'http_stop_latches_without_waiting_validation', 'save_drained_bounded', 'save_http_thread_exited',
    'interrupted_save_unknown_no_ack', 'real_validation_completed_with_registered_receipt',
    'same_validator_run_exited_cleanly', 'stop_time_inside_native_validation_interval',
    'selected_native_bytes_and_identity_unchanged', 'no_native_stage_objects_created',
    'durable_unknown_before_stage_select_adopt', 'same_dirty_editor_root_no_adoption',
    'authenticated_lookup_original_unknown', 'actual_editor_exit_and_owned_job_clean',
    'readonly_reopen_preserves_unknown_and_original_selection')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_helper():
    raw = HELPER.read_bytes()
    need(digest(raw) == HELPER_SHA256, 'pinned raw-evidence auditor changed')
    spec = importlib.util.spec_from_file_location('s52_pinned_raw_auditor', HELPER)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(raw, str(HELPER), 'exec'), module.__dict__)
    return module


H = load_helper()


class Evidence:
    def __init__(self):
        self.files = {}

    def add(self, path):
        path = Path(path).absolute()
        relative = path.relative_to(ROOT).as_posix()
        need(not any(part in ('.godot', '__pycache__', '.cache') for part in path.parts),
             'generated cache is not portable proof')
        need('/owned/storage/' not in '/' + relative and not any(
            part.startswith(('hh-private-', 'hh-files-')) for part in path.parts),
            'private native storage must not enter portable proof')
        H.inside(ROOT, relative)
        self.files[relative] = sha(path)
        return path

    def read(self, path):
        return H.read(self.add(path))

    def text(self, path):
        return self.add(path).read_text(encoding='utf-8', errors='strict')

    def tree(self, path):
        for relative in H.inventory(path):
            self.add(Path(path) / relative)


def closure_digest(files):
    H.hash_map(files)
    return digest(''.join('8-9-hh3d-3/studio/' + name + '\0' + value + '\n'
                          for name, value in sorted(files.items())).encode('utf-8'))


def runtime_map(files):
    # Tests/reports can differ between lanes; all production input files stay
    # exact. Each full producer closure is separately retained and validated.
    return {name: value for name, value in files.items() if not name.startswith('tests/')
            and not name.lower().endswith('.md')}


def same_runtime(file_maps):
    need(bool(file_maps), 'missing runtime source maps')
    runtime = runtime_map(file_maps[0])
    need(all(runtime_map(files) == runtime for files in file_maps),
         'runtime per-file maps differ across final lanes')
    return runtime


def source(ev, package):
    manifest = ev.read(package / 'source-closure.json')
    need(set(manifest) == {'files', 'source_closure_sha256'}, 'source manifest fields')
    files, closure = manifest['files'], manifest['source_closure_sha256']
    need(closure_digest(files) == closure, 'source closure digest differs')
    snapshot, _ = H.source_copy(package, files, closure)
    ev.tree(snapshot)
    return snapshot, files, closure


def checked_host(ev, package, host):
    for key in ('host', 'stdout', 'stderr'):
        ev.add(H.inside(package, host[key]))
    return H.host(package, host)


def phase_summary(ev, package, closure, *, stop=False, final=True):
    capture = ev.read(package / 'capture.json')
    need(capture['source_closure_sha256'] == closure and capture['passed'] is True
         and capture['snapshot_unchanged'] is True, 'publication capture/source failed')
    if final:
        need(capture['origin_source_unchanged'] is True, 'origin changed during final run')
    need(capture['candidate_only'] is True and capture['gt03_acceptance'] is False,
         'integration capture acceptance overclaim')
    label = 'publication-stop' if stop else 'publication'
    summary = ev.read(package / (label + '.json'))
    labels = STOP_LABELS if stop else HAPPY_LABELS
    checks = summary['checks']
    need(type(checks) is list and len(checks) == len(labels), 'missing integration checks')
    need(all(type(row) is dict and set(row) == {'label', 'passed'} and row['passed'] is True
             for row in checks) and [row['label'] for row in checks] == list(labels),
         'false/untyped/reordered integration checks')
    need(H.exact(ev.read(package / 'progress.json'), checks), 'raw progress differs')
    need(summary['passed'] is True and summary['candidate_only'] is True
         and summary['gt03_acceptance'] is False and summary['source_closure_sha256'] == closure,
         'integration summary mismatch')
    host = capture['host']
    need(all(host[key] == label + suffix for key, suffix in (
        ('host', '-host.json'), ('stdout', '-stdout.txt'), ('stderr', '-stderr.txt'))),
        'outer process evidence path substitution')
    stdout, stderr = checked_host(ev, package, host)
    marker = 'HH_PUBLICATION_STOP_COMPLETE ' if stop else 'HH_PUBLICATION_COMPLETE '
    need(H.exact(H.markers(stdout, marker), [{'passed': True, 'checks': len(labels)}])
         and not stderr.strip() and not H.BAD_LOG.search(stdout), 'unclean/missing actual completion')
    lock = ev.read(package / 'source/studio/toolchain.lock.json')['godot']
    script = 'run_publication_stop_probe.py' if stop else 'run_publication_probe.py'
    need(host['argv'] == ['python.exe', '-B', '$SNAPSHOT/tests/godot/' + script, '--frozen',
         '--output', package.name, '--run-id', capture['run_id'], '--binary', lock['gui_executable'],
         '--closure', closure], 'publication executable argv mismatch')
    return summary


def checked_job(job):
    for field in ('configured', 'assigned', 'closed', 'zero_observed'):
        need(job.get(field) is True, 'native Job missing ' + field)
    for field in ('handle_retained', 'tainted', 'create_uncertain', 'close_uncertain'):
        need(job.get(field) is False, 'native Job uncertain ' + field)
    need(H.integer(job.get('active_count'), 0) and job.get('failed_operations') == []
         and job.get('native_error') is None, 'native Job did not drain')


def live_editor(ev, package, source_root, canonical, *, adoption, release):
    roots = list((package / 'owned/editor').glob('editor-*'))
    need(len(roots) == 1 and roots[0].is_dir(), 'exactly one owned editor required')
    root = roots[0]
    closed = ev.read(package / 'editor-close.json')
    need(H.exact(closed, ev.read(root / 'close.json')), 'editor close record differs')
    started, exited = ev.read(root / 'process-start.json'), ev.read(root / 'process-exit.json')
    need(H.integer(started.get('pid')) and started['pid'] > 0 and
         H.integer(exited.get('pid'), started['pid']) and H.integer(exited.get('exit_code'), 0),
         'actual editor process PID/exit')
    need(H.exact(closed['actual_process_exit'], exited) and H.integer(closed['wrapper_exit_code'], 0)
         and closed['closed'] is True and closed['held'] is False and closed['logs_overflow'] is False
         and closed['public_ack'] is False, 'unclean editor ownership')
    checked_job(closed['job'])
    hello = ev.read(root / 'hello.json')
    need(hello['main_thread'] is True and hello['editor_hint'] is True
         and H.integer(hello['pid'], started['pid']) and hello['version'] == '4.7.2-stable (official)',
         'wrong native editor hello')
    for name in ('stdout.txt', 'stderr.txt'):
        need(not H.BAD_LOG.search(ev.text(root / name)), 'native editor diagnostic')
    captures = list(root.glob('capture-*.json'))
    adopts = list(root.glob('adoption-*.json'))
    need(len(captures) == 1 and len(adopts) == int(adoption), 'actual effect observation inventory')
    rows = [ev.read(path) for path in captures + adopts]
    identity_keys = ('editor_session_id', 'editor_pid', 'editor_creation_time', 'editor_engine_sha256',
                     'project_root_identity', 'source_release_sha256')
    lock = ev.read(source_root / 'toolchain.lock.json')['godot']
    for row in rows:
        need(row['schema'] == 'hh-godot-live-editor-observation-1' and row['context_kind'] == 'live_editor'
             and row['public_ack'] is False and H.integer(row['editor_pid'], started['pid'])
             and row['editor_session_id'] == hello['editor_session_id']
             and row['editor_engine_sha256'] == lock['gui_sha256']
             and row['source_release_sha256'] == release, 'editor observation identity/source')
        need(row['semantic_sha256'] == digest(canonical(row['semantic_state']))
             and row['semantic_revision'] == 'sha256:' + row['semantic_sha256'], 'full editor semantic hash')
        need(H.integer(row['effect_started_ms']) and H.integer(row['effect_completed_ms'])
             and row['effect_started_ms'] <= row['effect_completed_ms'], 'native effect time interval')
        need(all(H.exact(row[key], rows[0][key]) for key in identity_keys), 'editor identity changed')
    capture = rows[0]
    need(capture['kind'] == 'capture' and capture['generation_after'] == capture['generation_before']
         and capture['root_after'] == capture['root_before'], 'capture mutated editor context')
    scratch = list((root / 'scratch').glob('capture-*.tscn'))
    need(len(scratch) == 1 and ev.add(scratch[0]).stat().st_size == capture['scene_size_bytes']
         and sha(scratch[0]) == capture['scene_sha256'], 'captured scene bytes mismatch')
    project_files = rows[-1]['working_files']
    need(type(project_files) is dict and len(project_files) == 11, 'complete editor input set')
    for relative, descriptor in project_files.items():
        path = ev.add(H.inside(root / 'project', relative))
        need(sha(path) == descriptor['sha256'] and path.stat().st_size == descriptor['size_bytes'],
             'editor working input mismatch: ' + relative)
    if adoption:
        adopted = rows[1]
        need(adopted['kind'] == 'adopt' and adopted['generation_before'] == capture['generation_after']
             and adopted['generation_after'] > adopted['generation_before']
             and adopted['root_before'] == capture['root_after'] and adopted['root_after'] != adopted['root_before']
             and adopted['history_boundary'] is True and adopted['can_undo'] is False
             and adopted['can_redo'] is False and canonical(adopted['semantic_state']) == canonical(capture['semantic_state']),
             'same-session adoption/history/full semantic mismatch')
    return rows


def validators(ev, package, modules):
    validation, linux_probe = modules[:2]
    codec, factory, executor = validation.bundle_codec, validation.factory, validation.executor
    directories = list((package / 'owned/validation').glob('validate-*'))
    need(len(directories) == 2, 'bootstrap plus candidate native validations required')
    results = []
    for directory in directories:
        ev.tree(directory / 'input')
        raw = {name: H.inside(directory / 'input', name).read_bytes() for name in codec.PATHS}
        bundle = codec.decode_bundle(ev.add(directory / 'manifest.json').read_bytes(), raw)
        factory.qualify(bundle)
        base = directory / 'executor'
        # Only these flat CLI records and the two readonly input directories
        # are required; no private native writer trees or caches are packaged.
        for path in base.iterdir():
            if path.is_file(): ev.add(path)
        ev.tree(base / 'snapshot'); ev.tree(base / 'harness')
        result = H.verify_executor(base, executor, linux_probe, mode='profile-validate', timeout=20, inputs=raw)
        observation, comparison = validation.evaluate_run(result,
            ev.text(base / 'engine-stdout.txt'), ev.text(base / 'engine-stderr.txt'), bundle)
        need(comparison.get('semantic_observed') is True, 'missing raw complete Linux semantic report')
        results.append((directory, bundle, result, observation))
    need(len({result['run_id'] for _, _, result, _ in results}) == 2, 'duplicate native validation run')
    return results


def check_selection(value, canonical):
    selector, version = value['selector'], value['selector_version']
    need(selector['schema'] == 'hh-godot-active-selection-1'
         and digest(canonical(selector['descriptor'])) == selector['descriptor_sha256'], 'selector descriptor hash')
    raw = canonical(selector)
    need(version['sha256'] == digest(raw) and H.integer(version['size_bytes'], len(raw))
         and re.fullmatch('[0-9a-f]{32}', version['file_id']) and type(version['volume']) is str,
         'selector exact byte/version binding')
    return selector


def bind_editor_event(event, observation, *, adoption=False):
    identity = {'session_id':observation['editor_session_id'], 'pid':observation['editor_pid'],
        'creation_filetime':observation['editor_creation_time'],
        'root_identity':observation['project_root_identity'],
        'engine_sha256':observation['editor_engine_sha256'],
        'installed_source_sha256':observation['source_release_sha256']}
    need(H.exact(event['editor'],identity), 'event editor identity differs from actual observation')
    for key in ('effect_started_ms','effect_completed_ms','generation_before','generation_after',
                'semantic_revision','semantic_sha256'):
        need(H.exact(event[key],observation[key]), 'event observation differs: '+key)
    need(event['adoption_id' if adoption else 'capture_id']==observation['observation_id'],
         'event observation identity differs')
    if adoption:
        for key in ('context_kind','manifest_sha256','project_revision','selection','history_boundary'):
            need(H.exact(event[key],observation[key]), 'adoption event differs: '+key)
        need(event['root_instance_id_before']==int(observation['root_before'])
             and event['root_instance_id_after']==int(observation['root_after']), 'adoption actual root IDs differ')
        files=observation['working_files']
    else:
        need(event['root_instance_id']==int(observation['root_before'])
             and event['scene_sha256']==observation['scene_sha256']
             and event['scene_size_bytes']==observation['scene_size_bytes'], 'capture actual file/root differs')
        files=dict(observation['working_files'])
        files['scenes/fixture.tscn']={'sha256':observation['scene_sha256'],
                                     'size_bytes':observation['scene_size_bytes']}
    need(set(event['files'])==set(files) and all({key:row[key] for key in ('sha256','size_bytes')}
         ==files[name] for name,row in event['files'].items()), 'event actual bytes differ')


def bind_validation_receipt(receipt, validation, directory, bundle, native, observation, *, semantic):
    canonical=validation.canonical_bytes
    expected={'command_id':'command.save','source_release_sha256':validation.source_release()[1],
        'observation_sha256':digest(canonical(observation)),
        'evidence_sha256':digest(canonical(H.inventory(directory))), 'run_id':native['run_id']}
    if semantic:
        final=validation.bundle_codec.create_bundle(dict(bundle.files),
            scene_revision=observation['semantic']['revision'],engine_sha256=bundle.engine_sha256)
        expected.update(project_revision=final.project_revision,manifest_sha256=digest(final.manifest_bytes),
            input_files_sha256=digest(canonical(validation.parse_json(final.manifest_bytes)['files'])),
            validator_engine_sha256=native['toolchain']['binary_sha256'],
            scene_revision=observation['semantic']['revision'],context_kind='isolated_candidate',
            public_ack=False,selected_state_verified=False,live_editor_adoption_verified=False)
        need(H.integer(receipt['validation_started_ms']) and H.integer(receipt['validation_completed_ms'])
             and receipt['validation_started_ms']<=milliseconds(native['container_state']['StartedAt'])
             <=milliseconds(native['container_state']['FinishedAt'])<=receipt['validation_completed_ms'],
             'semantic receipt does not enclose actual native interval')
    else:
        expected.update(project_revision=bundle.project_revision,manifest_sha256=digest(bundle.manifest_bytes),
                        engine_sha256=native['toolchain']['binary_sha256'])
    need(all(H.exact(receipt.get(key),value) for key,value in expected.items()),
         'validation receipt not bound to exact raw native execution')


def verify_happy(ev, package, source_root, closure, modules, *, final=True):
    phase_summary(ev, package, closure, final=final)
    validation, _, state_model, editor_model = modules
    canonical = validation.canonical_bytes
    capture, adoption = live_editor(ev, package, source_root, canonical, adoption=True,
        release=digest(canonical(editor_model._release())))
    runs = validators(ev, package, modules)
    before, dirty, after = [ev.read(package / (name + '.json')) for name in ('before', 'dirty', 'after')]
    request, response = ev.read(package / 'request.json'), ev.read(package / 'response.json')
    discovery=ev.read(package/'discovery.json')
    catalog=H.module('s52_audit_catalog_'+closure[:16],source_root/'godot-addon/contract.py')
    need(H.exact(discovery,catalog.discovery(request['project_id'],
        implemented=frozenset({'scene.inspect','scene.save'}),runtime_enabled=frozenset({'scene.inspect','scene.save'})).as_dict()),
        'actual discovery differs from frozen implemented catalog')
    selector_facts = ev.read(package / 'selection.json')
    selector = check_selection(selector_facts, canonical)
    journal, reopened = ev.read(package / 'journal.json'), ev.read(package / 'reopened.json')
    from studio.protocol.core import Request
    req = Request.from_dict(request)
    need(response['status'] == 'COMMITTED' and response['command_id'] == request['command_id']
         and response['postconditions']['public_ack'] is True, 'actual public save response')
    need(dirty['revision'] != before['revision'] and dirty['project_revision'] == before['project_revision']
         and after['revision'] == dirty['revision'] == capture['semantic_revision'] == adoption['semantic_revision']
         and after['project_revision'] != before['project_revision']
         and after['generation'] > dirty['generation'] and after['root_instance_id'] != dirty['root_instance_id'],
         'dirty/captured/reloaded editor state binding')
    need(after['can_undo'] is False and after['can_redo'] is False
         and H.exact(after['working_files'], adoption['working_files'])
         and H.exact(selector['selection'], adoption['selection'])
         and canonical(dirty['state']) == canonical(after['state']) == canonical(capture['semantic_state']),
         'adoption selected files/history/full state')
    need(len(journal['commands']) == len(reopened['commands']) == 1, 'command journal membership')
    command = journal['commands'][0]
    need(command['phase'] == 'COMMITTED' and command['digest'] == req.digest
         == capture['request_digest'] == adoption['request_digest']
         and H.exact(command, reopened['commands'][0])
         and command['receipt_sha256'] == digest(canonical(command['receipt']))
         and command['receipt_sha256'] == response['postconditions']['durable_receipt_sha256'],
         'durable response/reopen receipt binding')
    for state in (journal, reopened):
        need(state['source_closure_sha256'] == closure and state['public_ack'] is False
             and state['pending_command_id'] is None and state['selected']['bundle_manifest']['project_revision']
             == after['project_revision'] and H.exact(state['selected']['selector'], selector)
             and H.exact(state['selected']['selector_version'], selector_facts['selector_version']),
             'journal selected/reopen facts')
    need(reopened['journal_read_only'] is True and reopened['execution_permitted'] is False,
         'reopen is not permanently readonly')
    candidates = [(directory, bundle, result, obs) for directory, bundle, result, obs in runs
                  if digest(bundle.files['scenes/fixture.tscn']) == capture['scene_sha256']]
    need(len(candidates) == 1, 'captured bytes not bound to exactly one native validation')
    directory, bundle, native, observation = candidates[0]
    need(canonical(observation['semantic']['state']) == canonical(capture['semantic_state']),
         'Linux candidate differs from actual captured/editor state')
    manifest = journal['selected']['bundle_manifest']
    need(manifest['files'] == validation.parse_json(bundle.manifest_bytes)['files'], 'selected input bytes differ from validated bundle')
    need(manifest['caller_observations']['scene_revision'] == observation['semantic']['revision'], 'selected semantic revision differs')
    for name, row in manifest['files'].items():
        need({key: row[key] for key in ('sha256','size_bytes')} == adoption['working_files'][name], 'selected/adopted bytes differ')
    raw_responses = all((package / name).is_file() for name in
                        ('duplicate-response.json', 'lookup-response.json', 'stop-response.json'))
    if final: need(raw_responses, 'final run missing actual duplicate/lookup/Stop responses')
    if raw_responses:
        need(H.exact(ev.read(package / 'duplicate-response.json'), response)
             and H.exact(ev.read(package / 'lookup-response.json'), response), 'duplicate/lookup raw response differs')
        stopped = ev.read(package / 'stop-response.json')
        need(stopped['stopped'] is True and stopped['draining'] is False, 'actual Stop response differs')
    events_present = (package / 'events.json').is_file()
    if final: need(events_present, 'final run missing portable state events')
    if events_present:
        events=ev.read(package/'events.json')
        replayed = state_model.replay(events).snapshot()
        need(all(H.exact(value,journal.get(key)) for key,value in replayed.items()),
             'public state replay differs from live journal snapshot')
        indexed={event['kind']:event for event in events}
        need(len(indexed)==len(events),'duplicate phase event')
        bind_editor_event(indexed['CAPTURED']['capture'],capture)
        bind_editor_event(indexed['READBACK']['adoption'],adoption,adoption=True)
        bind_validation_receipt(indexed['VALIDATED']['validation'],validation,directory,bundle,
                                native,observation,semantic=True)
    return {'checks':len(HAPPY_LABELS),'native_validations':2,'selected_editor_bytes_verified':True,
            'readonly_reopen_historical_verified':True,'duplicate_lookup_stop_raw_saved':raw_responses,
            'public_state_events_saved':events_present,'foreign_bearer_denial_producer_assertion_only':True,
            'live_registry_reopened_by_auditor':False}


def milliseconds(value):
    return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1000)


def verify_stop(ev, package, source_root, closure, modules):
    phase_summary(ev, package, closure, stop=True)
    validation, _, state_model, editor_model = modules
    canonical = validation.canonical_bytes
    capture = live_editor(ev, package, source_root, canonical, adoption=False,
        release=digest(canonical(editor_model._release())))[0]
    runs = validators(ev, package, modules)
    dirty, after = ev.read(package/'dirty.json'), ev.read(package/'after.json')
    need(all(H.exact(dirty[key],after[key]) for key in ('revision','generation','root_instance_id',
        'working_files','state','project_revision')), 'Stop allowed adoption or changed live state')
    response = ev.read(package/'save-response.json')
    need(H.integer(response['status'],200) and response['result']['status']=='UNKNOWN'
         and response['result']['postconditions']['public_ack'] is False, 'interrupted save must be UNKNOWN')
    stopped, timing, running = [ev.read(package/name) for name in
                               ('stop-response.json','timing.json','running.json')]
    need(H.integer(stopped['http_status'],200) and stopped['response']['stopped'] is True
         and stopped['response']['public_ack'] is False and timing['validation_returned_at_stop_response'] is False
         and type(timing['stop_elapsed_ms']) in (int,float) and 0<=timing['stop_elapsed_ms']<2000,
         'Stop did not return before actual validation drain')
    candidates=[row for row in runs if digest(row[1].files['scenes/fixture.tscn'])==capture['scene_sha256']]
    need(len(candidates)==1,'Stop candidate input binding')
    directory,bundle,native,observation=candidates[0]
    bind_validation_receipt(timing['registered_validation_receipt'],validation,directory,bundle,
                            native,observation,semantic=False)
    record=running['record']; state=native['container_state']
    need(record['name']==native['run_id'] and record['container_id']==native['container_id']
         and running['native']['Id']==native['container_id'] and running['native']['State']['Running'] is True
         and H.integer(running['native']['State']['Pid']) and running['native']['State']['Pid']>0,
         'Stop native running identity mismatch')
    row=running['host']; label=Path(row['stdout']).name.removesuffix('-stdout.txt')
    observer=package/'stop-observer'
    for path in observer.iterdir():
        if path.is_file(): ev.add(path)
    raw_host=H.cli(observer,label,validation.executor,args=['inspect',native['container_id']])
    need(H.exact(row,raw_host) and H.exact(H.one_inspect(observer,label),running['native']),
         'native running observation is not raw inspect output')
    need(milliseconds(state['StartedAt'])<=timing['stop_started_ms']<=timing['stop_completed_ms']
         <timing['validation_returned_ms'] and timing['stop_completed_ms']<milliseconds(state['FinishedAt'])
         and running['observed_ms']<=timing['stop_started_ms'], 'Stop time not inside actual native run')
    need(timing['native_result_sha256']==sha(directory/'executor/result.json')
         and timing['native_result_relative']==(directory/'executor/result.json').relative_to(package).as_posix(),
         'Stop native result byte binding')
    selection=ev.read(package/'selection-before.json'); check_selection(selection,canonical)
    reopened=ev.read(package/'reopened.json'); events=ev.read(package/'events.json')
    need([event['kind'] for event in events]==['CONFIG','CAPTURE_PREPARED','CAPTURED','UNKNOWN'],
         'Stop has stage/select/readback/commit effects')
    replayed=state_model.replay(events).snapshot()
    need(all(H.exact(value,reopened.get(key)) for key,value in replayed.items()),
         'Stop public state replay differs from reopened snapshot')
    bind_editor_event(events[2]['capture'],capture)
    need(reopened['journal_read_only'] is True and reopened['execution_permitted'] is False
         and H.exact(reopened['selected']['selector'],selection['selector'])
         and H.exact(reopened['selected']['selector_version'],selection['selector_version'])
         and len(reopened['commands'])==1 and reopened['commands'][0]['phase']=='UNKNOWN',
         'readonly unknown/reopened selector differs')
    return {'checks':len(STOP_LABELS),'stop_elapsed_ms':timing['stop_elapsed_ms'],
            'native_running_inspect_verified':True,'no_stage_select_adopt_event':True,
            'private_storage_names_assertion_only':True,'live_registry_reopened_by_auditor':False}


def verify_editor_engines(ev, package, source, files, closure):
    # Preserve the initial failed unit outcome; only native lanes are checked here.
    # Engine checks below retain the pinned S49 conditions without rewriting logs.
    checks = H.module('s52_native_editor_checks', source / 'tests/godot/evidence_checks.py')
    capture = ev.read(package / 'capture.json')
    need(capture['source_closure_sha256'] == closure and capture['passed'] is False
         and capture['unit']['passed'] is False, 'initial failed unit outcome was changed')
    for flag in ('source_unchanged', 'snapshot_unchanged', 'binary_unchanged', 'temporary_removed'):
        need(capture.get(flag) is True, 'editor source/lifecycle failed: ' + flag)
    for flag in ('production_save_verified', 'hostile_script_sandbox_verified'):
        need(capture.get(flag) is False, 'unsupported editor scope: ' + flag)
    lock = ev.read(source / 'toolchain.lock.json')['godot']
    need(capture['godot_sha256'] == lock['gui_sha256'], 'unlocked Windows engine')
    need([lane['mode'] for lane in capture['lanes']] == ['edit', 'reopen', 'contract'], 'engine lane missing')
    # Rebuild every executable byte from the frozen runner's documented fixture.
    # The diagnostic plugin.cfg replacement is deliberate and also bound here.
    expected = {}
    addon = source / 'godot-addon/addons/hh_studio'
    for path in addon.rglob('*'):
        if path.is_file() and path.suffix in ('.gd', '.cfg', '.godot'):
            raw = path.read_bytes()
            if path.name == 'plugin.cfg':
                raw = path.read_text(encoding='utf-8').replace('script="plugin.gd"', 'script="diagnostic_plugin.gd"').replace('\n', '\r\n').encode('utf-8')
            expected['addons/hh_studio/' + path.relative_to(addon).as_posix()] = digest(raw)
    for runtime, frozen in {'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
                            'addons/hh_studio/diagnostic_plugin.gd': 'tests/godot/diagnostic_plugin.gd',
                            'tests/editor_probe.gd': 'tests/godot/editor_probe.gd'}.items():
        expected[runtime] = files[frozen]
    script = b'extends Node3D\n@export var fixture_value: int = 7\n'
    project = (b'config_version=5\n[application]\nconfig/name="HH GT03 trusted editor fixture"\n'
               b'[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
               b'[editor_plugins]\nenabled=PackedStringArray("res://addons/hh_studio/plugin.cfg")\n')
    expected.update({'scripts/fixture_actor.gd': digest(script.replace(b'\n', b'\r\n')),
                     'project.godot': digest(project.replace(b'\n', b'\r\n'))})
    need(H.read(package / 'executed-inputs.json') == expected, 'all executed editor inputs must match frozen fixture')
    fixture = H.read(package / 'fixture-inputs.json')
    need(all(fixture.get(name) == value for name, value in expected.items()), 'initial fixture input differs')
    results = {}
    for lane in capture['lanes']:
        mode = lane['mode']
        streams = H.host(package, lane['host'])
        need(lane['host'].get('argv') == [lock['gui_executable'], '--headless', '--editor', '--path', '$SNAPSHOT/.',
             '--log-file', '$SNAPSHOT/' + mode + '-engine.log', 'res://scenes/fixture.tscn', '--',
             '--hh-studio-editor-probe', '--probe-mode=' + mode], 'actual editor argv differs')
        for flag in ('passed', 'clean_log', 'result_valid', 'execution_unchanged', 'exact_reopen_revision'):
            need(lane.get(flag) is True, mode + ' invalid fact: ' + flag)
        need(lane.get('result_validation_error') is None and lane['execution_before'] == lane['execution_after'] == expected, 'executed editor input changed')
        result = H.read(package / (mode + '-result.json'))
        progress = [H.parse(line) for line in (package / (mode + '-progress.jsonl')).read_text(encoding='utf-8').splitlines()]
        need(checks.validate_result(mode, result, progress) is True, 'invalid engine result/progress')
        need(type(H.EXPECTED_ENGINE_CHECKS) is dict and H.integer(H.EXPECTED_ENGINE_CHECKS.get(mode), len(result['checks'])), 'actual expected engine count not established/mismatch')
        for text in (*streams, (package / (mode + '-engine.log')).read_text(encoding='utf-8')):
            need(H.BAD_LOG.search(text) is None, 'unclean editor stream')
        results[mode] = result
    need(results['edit']['saved_revision'] == results['reopen']['saved_revision'], 'reopened complete-state revision differs')
    vectors = H.read(package / 'contract-vectors.json')
    need(vectors.get('snapshot_mode') == 'SUPPLIED_NATIVE_OBSERVATION' and vectors.get('file_hashes_observed') is True, 'synthetic contract vectors')
    need(vectors.get('runtime_authorized') is False and vectors.get('acceptance') is False, 'contract vector overclaim')
    need(len(vectors['rejected']) == 14 and all(row['engine_projection'] is None for row in vectors['rejected']), 'rejected host wire reached engine')
    need(vectors.get('schema') == 'hh-gt03-contract-vectors-2', 'legacy vectors')
    need(vectors['context']['project_revision'] == H.read(package / 'contract-base-bundle.json')['project_revision'], 'wire complete-project revision differs')
    return {name: len(value['checks']) for name, value in results.items()}


REPAIR_FILES = {'tests/godot/test_profile_probe_evidence.py', 'tests/godot/test_profile_readback.py'}


def unittest_rows(stderr, expected):
    rows = re.findall(r'^test\w+ \(([^()\r\n]+)\) \.\.\. (ok|FAIL|ERROR)$', stderr, re.MULTILINE)
    need(len(rows) == expected and len(dict(rows)) == expected, 'raw unittest IDs missing/duplicate')
    need(re.findall(r'Ran (\d+) tests? in ', stderr) == [str(expected)], 'raw unittest count differs')
    return dict(rows)


def test_ids(source, names):
    ids = set()
    for name in names:
        tree = ast.parse(H.inside(source, name).read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith('test_'):
                        ids.add(Path(name).stem + '.' + node.name + '.' + method.name)
    return ids


def verify_unit_repair(ev, package, initial, repair, repaired, expected_tests):
    source_root, files, closure = initial
    repair_root, repaired_files, repaired_closure = repaired
    need(set(files) == set(repaired_files) and {name for name in files if files[name] != repaired_files[name]}
         == REPAIR_FILES, 'repair changed files outside the exact two test modules')
    expected_ids = test_ids(source_root, REPAIR_FILES)
    need(expected_ids == test_ids(repair_root, REPAIR_FILES) and len(expected_ids) == 30,
         'repair removed/renamed/added tests')
    capture = ev.read(package/'capture.json'); unit = capture['unit']; row = unit['host']
    runner_tree=ast.parse((source_root/'tests/godot/run_editor_probe.py').read_text(encoding='utf-8'))
    unit_code=[ast.literal_eval(node.value) for node in ast.walk(runner_tree)
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='unit_code'
                                               for target in node.targets)]
    need(len(unit_code)==1 and row['argv']==['python.exe','-B','-c',unit_code[0]],
         'initial unit executable code differs from frozen runner')
    raw = ev.read(H.inside(package, row['host']))
    need(H.integer(raw.get('target_pid')) and raw['target_pid'] > 0
         and H.integer(row['target_pid'], raw['target_pid']) and H.integer(row['wrapper_pid'])
         and row['wrapper_pid'] > 0 and H.integer(raw['exit_code'], 1)
         and H.integer(row['exit_code'], 1) and H.integer(row['wrapper_exit_code'], 0),
         'initial failed suite actual exit/PID mismatch')
    need(row['timed_out'] is False and row['tree_verified'] is True
         and row['ownership'] == 'gated_job_kill_on_close'
         and type(raw.get('started_at')) is str and raw['started_at'], 'initial failed suite did not drain')
    stdout, stderr = (ev.text(H.inside(package, row[key])) for key in ('stdout','stderr'))
    counts = unit['counts']
    need(H.exact(counts, {'run':expected_tests,'failures':18,'errors':0,'skips':0})
         and H.exact(H.markers(stdout,'GT03_UNIT_COMPLETE '),[counts])
         and stderr.rstrip().endswith('FAILED (failures=18)'), 'initial failure counts/raw marker differ')
    original = unittest_rows(stderr, expected_tests)
    failed = {key for key,value in original.items() if value == 'FAIL'}
    need(len(failed) == 18 and failed <= expected_ids and set(original.values()) == {'ok','FAIL'}
         and set(re.findall(r'^FAIL: test\w+ \(([^()\r\n]+)\)$',stderr,re.MULTILINE)) == failed,
         'initial failures do not match repaired test IDs')
    # The saved failures are the historical trusted-input hash assertion, never
    # a native mutation failure silently converted into a successful process.
    blocks = re.split(r'^FAIL: ',stderr,flags=re.MULTILINE)[1:]
    need(len(blocks)==18 and all('AssertionError:' in block and
         'self.assertEqual({k:v for k,v in ' in block for block in blocks),
         'initial failure cause differs from reviewed fixture provenance assertion')
    fixed = ev.read(repair/'capture.json'); invocation = ev.read(repair/'invocation.json')
    need(fixed['source_closure_sha256'] == repaired_closure and fixed['candidate_only'] is True
         and fixed['origin_source_unchanged'] is True and fixed['snapshot_unchanged'] is True,
         'repair snapshot/source changed')
    need(invocation['repair_of'] == package.name and set(invocation['changed_source_files']) == REPAIR_FILES
         and invocation['runner_sha256'] == repaired_files['build/bootstrap/run_fixture.py'],
         'repair invocation source binding')
    repair_host = fixed['host']
    need(repair_host['argv'] == ['python.exe','-B','-c',invocation['code']], 'repair actual argv differs')
    out, err = checked_host(ev,repair,repair_host)
    markers = H.markers(out,'GT03_UNIT_REPAIR_COMPLETE ')
    need(len(markers)==1,'repair raw completion missing/duplicate')
    result = markers[0]
    need(H.integer(result['run'],30) and all(H.integer(result[key],0) for key in ('failures','errors','skips'))
         and type(result['tests']) is list and len(result['tests'])==30
         and set(result['tests'])==expected_ids and err.rstrip().endswith('OK'), 'repair actual test IDs/counts')
    rerun = unittest_rows(err,30)
    need(set(rerun)==expected_ids and set(rerun.values())=={'ok'}, 'repair raw tests incomplete/failed')
    current = H.module('s52_repair_enumerator',repair_root/'tests/godot/run_editor_probe.py')
    current.STUDIO=STUDIO
    need(current.inputs()==repaired_files,'current full source differs from repaired frozen closure')
    for path in repair.iterdir():
        if path.is_file(): ev.add(path)
    unique_passed = {name for name,status in original.items() if status=='ok'} | set(rerun)
    need(len(unique_passed)==expected_tests and unique_passed==set(original),'repair left unresolved tests')
    return {'initial':counts,'initial_passed':expected_tests-18,'initial_capture_passed':False,
        'repair':{key:result[key] for key in ('run','failures','errors','skips')},
        'initial_failed_test_ids':sorted(failed),'repaired_test_ids':sorted(rerun),
        'unique_tests_with_passing_evidence':len(unique_passed),'one_clean_full_rerun':False,
        'runtime_unchanged':True,'repair_changed_files':sorted(REPAIR_FILES)}


def git_proof(ref, artifacts, current_source):
    expected=dict(artifacts)
    expected.update({'studio/'+name:value for name,value in current_source.items()})
    for name in ('portable-artifacts.json','verification.json'):
        path=AUDIT/name
        expected[path.relative_to(ROOT).as_posix()]=sha(path)
    names=sorted(expected)
    prefix=':' if ref=='index' else 'HEAD:'
    expressions=[prefix+ROOT.name+'/'+name for name in names]
    child=subprocess.run(['git','cat-file','--batch'],input=('\n'.join(expressions)+'\n').encode(),
        cwd=ROOT.parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=30)
    offset=0
    for name in names:
        end=child.stdout.index(b'\n',offset)
        header=child.stdout[offset:end].split()
        need(len(header)==3 and header[1]==b'blob','Git file missing or not blob: '+name)
        size=int(header[2]); offset=end+1
        raw=child.stdout[offset:offset+size]; offset+=size
        need(child.stdout[offset:offset+1]==b'\n','Git batch framing')
        offset+=1
        need(digest(raw)==expected[name] and raw==(ROOT/name).read_bytes(),'Git/disk bytes differ: '+name)
    need(offset==len(child.stdout),'unexpected Git batch output')
    proof={'passed':True,'ref':ref,'file_count':len(names),'source_files':len(current_source),
        'artifact_files':len(artifacts),'formal_acceptance':False,
        'portable_manifest_sha256':sha(AUDIT/'portable-artifacts.json')}
    (AUDIT/('git-byte-verification-'+ref+'.json')).write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    return proof


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--editor',type=Path,required=True)
    parser.add_argument('--happy',type=Path,required=True)
    parser.add_argument('--stop',type=Path,required=True)
    parser.add_argument('--repair',type=Path,required=True)
    parser.add_argument('--expected-tests',type=int,required=True)
    parser.add_argument('--git-ref',choices=('index','HEAD'))
    args=parser.parse_args()
    packages=[path.resolve() for path in (args.editor,args.happy,args.stop,args.repair)]
    ev=Evidence(); ev.add(HELPER); ev.add(Path(__file__)); ev.add(AUDIT/'README.md')
    test_path=ev.add(AUDIT/'test_negative.py')
    negative=ev.read(AUDIT/'negative-results.json')
    need(negative['passed'] is True and H.integer(negative['run'],4)
         and all(H.integer(negative[key],0) for key in ('failures','errors','skips'))
         and negative['read_only_evidence'] is True and negative['native_processes_launched'] is False
         and negative['formal_acceptance'] is False and negative['audit_sha256']==sha(Path(__file__))
         and negative['test_sha256']==sha(test_path), 'corruption regression evidence missing or stale')
    sources=[source(ev,p) for p in packages]
    runtime=same_runtime([files for _,files,_ in sources])
    need(all(sha(H.inside(STUDIO,name))==value for name,value in runtime.items()), 'current runtime differs from tested runtime')
    source_root=sources[0][0]
    sys.path.insert(0,str(source_root.parent))
    validation=H.module('s52_frozen_audit_validation',source_root/'godot-addon/validation_owner.py')
    linux_probe=H.module('s52_frozen_audit_linux',source_root/'tests/godot/run_linux_probe.py')
    state_model=H.module('s52_frozen_audit_state',source_root/'godot-addon/publication_state_v3.py')
    editor_model=H.module('s52_frozen_audit_editor',source_root/'godot-addon/editor_owner.py')
    modules=(validation,linux_probe,state_model,editor_model)
    engine_counts=verify_editor_engines(ev,packages[0],source_root,sources[0][1],sources[0][2])
    unit_counts=verify_unit_repair(ev,packages[0],sources[0],packages[3],sources[3],args.expected_tests)
    for path in packages[0].iterdir():
        if path.is_file(): ev.add(path)
    happy=verify_happy(ev,packages[1],sources[1][0],sources[1][2],modules)
    stop=verify_stop(ev,packages[2],sources[2][0],sources[2][2],modules)
    result={'passed':True,'status':'CANDIDATE','formal_acceptance':False,'gt03_accepted':False,
        'verified_at':datetime.now(timezone.utc).isoformat(),'unit_counts':unit_counts,'engine_counts':engine_counts,
        'happy':happy,'stop':stop,'runtime_files':runtime,'source_closures':{
            package.name:closure for package,(_,_,closure) in zip(packages,sources)},
        'portable_artifact_count':len(ev.files),'pinned_raw_auditor_sha256':HELPER_SHA256}
    if args.git_ref:
        need(H.exact(H.read(AUDIT/'portable-artifacts.json'),{'files':dict(sorted(ev.files.items()))}),
             'portable manifest changed since verification')
        saved=H.read(AUDIT/'verification.json')
        need(H.exact({key:value for key,value in saved.items() if key!='verified_at'},
                     {key:value for key,value in result.items() if key!='verified_at'}),
             'audit summary changed since verification')
        result['git_proof']=git_proof(args.git_ref,ev.files,sources[3][1])
    else:
        (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(ev.files.items()))},indent=2)+'\n',encoding='utf-8')
        (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='runtime_files'},sort_keys=True))


if __name__=='__main__':
    main()
