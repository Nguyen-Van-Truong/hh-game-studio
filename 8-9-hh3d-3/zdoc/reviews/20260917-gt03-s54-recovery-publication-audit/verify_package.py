"""Portable read-only verification of ONE frozen recovery component run.

No engines, native custody, transport, or subprocesses are opened by this tool.
The source-addressed pure folds are loaded only after the entire source closure
passes. --write emits audit records in this directory; normal mode is read-only.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
RUN_NAME = '20260917-gt03-s54-recovery-publication-01'
PACKAGE = HERE.parent / RUN_NAME
EXPECTED = '469b22d6788ef63c7ca4d6e7dc91e703494db439834dffacdef7d476a9464bdc'
VALIDATION = 'original/owned/validation/validate-599db36eefcd462c92c0fe22a6948e24'
EXECUTOR = VALIDATION + '/executor/'
ORIGINAL_EDITOR = 'original/owned/editor/editor-63088d157c0a41e0924c7a2b5d57de1e/'
RECOVERY_EDITOR = 'recovery/recovery-editor/editor-7826453e02c14f498b042a7d6c4d1e1d/'
canonical = recovery = None


class Invalid(ValueError):
    pass


def need(value, code):
    if not value:
        raise Invalid(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Tree:
    def __init__(self, overlay=None):
        self.overlay = overlay or {}

    def read(self, name):
        if name in self.overlay:
            return self.overlay[name]
        prefix, relative = name.split('/', 1)
        need(prefix in ('run', 'audit') and not any(p in ('', '.', '..') for p in relative.split('/')), 'UNSAFE_AUDIT_PATH')
        return ((PACKAGE if prefix == 'run' else HERE) / relative).read_bytes()

    def json(self, name):
        return json.loads(self.read(name))


def source_check(tree):
    manifest = tree.json('run/source-closure.json')
    files = manifest['files']
    need(files and manifest['source_closure_sha256'] == EXPECTED, 'SOURCE_DECLARED_CLOSURE')
    rows = []
    for name, digest in sorted(files.items()):
        need(not name.startswith('/') and '\\' not in name and all(p not in ('', '.', '..') for p in name.split('/')), 'SOURCE_PATH')
        need(re.fullmatch('[0-9a-f]{64}', digest), 'SOURCE_DIGEST')
        need(sha(tree.read('run/source/studio/' + name)) == digest, 'SOURCE_FILE:' + name)
        rows.append('8-9-hh3d-3/studio/' + name + '\0' + digest + '\n')
    need(sha(''.join(sorted(rows)).encode()) == EXPECTED, 'SOURCE_COMPUTED_CLOSURE')
    return files


def load_pure():
    global canonical, recovery
    if canonical is not None:
        return
    sys.path.insert(0, str(PACKAGE / 'source'))
    from studio.protocol.core import canonical_bytes
    canonical = canonical_bytes
    path = PACKAGE / 'source/studio/godot-addon/publication_recovery.py'
    name = '_hh_s54_audit_' + sha(path.read_bytes())
    spec = importlib.util.spec_from_file_location(name, path)
    recovery = importlib.util.module_from_spec(spec)
    sys.modules[name] = recovery
    spec.loader.exec_module(recovery)


def job_clean(job):
    return (all(job.get(k) is True for k in ('configured', 'assigned', 'closed', 'zero_observed'))
            and all(job.get(k) is False for k in ('handle_retained', 'tainted', 'create_uncertain', 'close_uncertain'))
            and job.get('active_count') == 0 and job.get('failed_operations') == [] and job.get('native_error') is None)


def native_records(raw):
    offset, previous, rows = 0, '0' * 64, []
    need(0 < len(raw) <= 8 * 1024 * 1024, 'STREAM_SIZE')
    while offset < len(raw):
        need(len(rows) < 512 and len(raw) - offset >= 36, 'STREAM_TRUNCATED')
        size = int.from_bytes(raw[offset:offset + 4], 'little')
        need(1 <= size <= 16384 and offset + size + 36 <= len(raw), 'STREAM_FRAME_LENGTH')
        body = raw[offset + 4:offset + 4 + size]
        digest = raw[offset + 4 + size:offset + 36 + size]
        need(hashlib.sha256(body).digest() == digest, 'STREAM_FRAME_CHECKSUM')
        wrapper = json.loads(body)
        need(set(wrapper) == {'format', 'sequence', 'previous', 'event'} and canonical(wrapper) == body,
             'STREAM_CANONICAL_WRAPPER')
        need(wrapper['format'] == 'hh-private-events-1' and wrapper['sequence'] == len(rows) + 1
             and wrapper['previous'] == previous, 'STREAM_CHAIN')
        offset += size + 36
        previous = digest.hex()
        rows.append({'head': {'sequence': len(rows) + 1, 'sha256': previous, 'size': offset}, 'event': wrapper['event']})
    return rows


def check_processes(tree):
    capture = tree.json('run/capture.json')
    for result, raw_name, expected in ((capture['host'], 'recovery-publication-host.json', 0),
            (tree.json('run/original-host.json'), 'original/original-host.json', 92)):
        raw = tree.json('run/' + raw_name)
        need(result['exit_code'] == raw['exit_code'] == expected and result['target_pid'] == raw['target_pid'], 'ACTUAL_TARGET_EXIT')
        need(result['wrapper_exit_code'] == 0 and result['tree_verified'] is True and result['timed_out'] is False,
             'OWNED_WRAPPER_EXIT')
        need(result['ownership'] == 'gated_job_kill_on_close', 'OWNED_PROCESS_TREE')
    need(capture['passed'] is True and capture['snapshot_unchanged'] is True and capture['source_closure_sha256'] == EXPECTED,
         'CAPTURE_SCOPE')
    need(capture['origin_source_unchanged'] is False, 'CAPTURE_ORIGIN_BOUNDARY')
    need(capture['gt03_acceptance'] is False and capture['candidate_only'] is True, 'CAPTURE_ACCEPTANCE_SCOPE')
    need(tree.read('run/recovery-publication-stderr.txt') == b'', 'OUTER_STDERR')
    need(json.loads(tree.read('run/recovery-publication-stdout.txt').decode().split('HH_AUTHENTICATED_RECOVERY_COMPLETE ', 1)[1])
         == {'passed': True, 'checks': 14}, 'HARNESS_COMPLETION')
    report = tree.json('run/recovery.json')
    harness = tree.read('run/source/studio/tests/godot/run_recovery_publication_probe.py').decode()
    labels = re.findall(r"check\('([^']+)'", harness)
    need(report['checks'] == [{'label': label, 'passed': True} for label in labels] and len(labels) == 14,
         'FROZEN_HARNESS_ASSERTIONS')
    need(report['source_closure_sha256'] == EXPECTED and report['passed'] and report['actual_authenticated_recovery']
         and report['candidate_only'] and report['gt03_acceptance'] is False, 'HARNESS_SCOPE')


def check_linux(tree):
    result = tree.json('run/' + EXECUTOR + 'result.json')
    container = result['container_id']
    need(re.fullmatch('[0-9a-f]{64}', container), 'CONTAINER_ID')
    host_names = [p.name for p in (PACKAGE / EXECUTOR).glob('*-host.json')]
    for name in host_names:
        h = tree.json('run/' + EXECUTOR + name)
        need(h['exit_code'] == (1 if name == 'removed-inspect-host.json' else 0), 'LINUX_HOST_EXIT:' + name)
        need(not h['timed_out'] and not h['stream_cap_exceeded'] and h['readers_stopped'] and h['job_active_count'] == 0
             and job_clean(h['job_owner']), 'LINUX_HOST_CLEANUP:' + name)
        raw = [tree.read('run/' + EXECUTOR + h[k]) for k in ('stdout', 'stderr')]
        need([len(x) for x in raw] == h['stream_byte_counts'] and h['stream_reader_eof'] == [True, True]
             and h['stream_reader_errors'] == [None, None], 'LINUX_HOST_STREAMS:' + name)
        if name not in ('context-host.json', 'admission-inventory-host.json', 'image-host.json', 'create-host.json'):
            need(container in h['argv'], 'LINUX_COMMAND_CONTAINER:' + name)
    engine = tree.json('run/' + EXECUTOR + 'engine-host.json')
    need(engine == result['command_host'] == result['commandhost'], 'LINUX_REPORT_RAW_COMMAND')
    need(tree.read('run/' + EXECUTOR + 'create-stdout.txt').decode().strip() == container, 'CONTAINER_CREATED_ID')
    created = tree.json('run/' + EXECUTOR + 'created-inspect-stdout.txt')[0]
    exited = tree.json('run/' + EXECUTOR + 'exited-inspect-stdout.txt')[0]
    need(created['Id'] == exited['Id'] == container and created['State']['Status'] == 'created', 'CONTAINER_INSPECTION_ID')
    state = exited['State']
    need(state == result['container_state'] and state['Status'] == 'exited' and state['Pid'] == state['ExitCode'] == 0
         and all(state[k] is False for k in ('Running', 'Paused', 'Restarting', 'OOMKilled', 'Dead')) and not state['Error'],
         'CONTAINER_EXIT_STATE')
    need(tree.read('run/' + EXECUTOR + 'wait-stdout.txt').strip() == b'0' and result['docker_wait_exit'] == 0, 'DOCKER_WAIT_EXIT')
    need(tree.read('run/' + EXECUTOR + 'owned-remove-stdout.txt').decode().strip() == container
         and 'no such object: ' + container in tree.read('run/' + EXECUTOR + 'removed-inspect-stderr.txt').decode()
         and tree.json('run/' + EXECUTOR + 'removed-inspect-stdout.txt') == [], 'OWNED_CONTAINER_REMOVED')
    hc = created['HostConfig']
    need(hc['ReadonlyRootfs'] and hc['NetworkMode'] == 'none' and hc['CapDrop'] == ['ALL']
         and hc['PidsLimit'] == 64 and hc['Memory'] == hc['MemorySwap'] == 1073741824
         and created['Config']['User'] == '65532:65532' and created['Config']['Labels']['hh.gt03.owner'] == result['run_id'],
         'CONTAINER_BOUNDARY')
    need(all(m['RW'] is False for m in created['Mounts'] if m['Type'] == 'bind'), 'CONTAINER_READONLY_BINDS')
    need(created['Path'] == '/usr/local/bin/python3' and "os.getpid()==1" in created['Args'][3]
         and '--kill-after=1s' in created['Args'] and '19s' in created['Args'], 'BOUNDED_PID1')
    stdout = tree.read('run/' + EXECUTOR + 'engine-stdout.txt').decode()
    need(re.findall(r'HH_PROFILE_PHASE_END (\w+) (\d+)', stdout) == [('parse', '0'), ('import', '0'), ('readback', '0')],
         'LINUX_ACTUAL_PHASE_EXITS')
    need(tree.read('run/' + EXECUTOR + 'engine-stderr.txt') == b'' and not re.search(r'ERROR|WARNING|leaked', stdout), 'LINUX_ENGINE_LOG')
    reads = [json.loads(line.removeprefix('HH_PROFILE_READBACK ')) for line in stdout.splitlines() if line.startswith('HH_PROFILE_READBACK ')]
    need(len(reads) == 1 and reads[0]['ok'] is True and reads[0]['public_ack'] is False, 'LINUX_READBACK_COUNT')
    readback = reads[0]
    need(readback['semantic']['context_kind'] == 'isolated_candidate' and readback['semantic']['revision']
         == 'sha256:' + sha(canonical(readback['semantic']['state'])), 'LINUX_SEMANTIC_HASH')
    need(result['profile_eligible'] and result['diagnostic_process_clean'] and result['owned_removed']
         and result['input_unchanged'] and result['snapshot_unchanged'] and result['binary_unchanged'] and result['log_clean']
         and result['errors'] == [] and result['public_ack'] is False and result['sandbox_acceptance'] is False, 'LINUX_REPORT_SCOPE')
    need(result['admission']['released'] and result['admission']['maximum_active'] == 1
         and result['owner_record_retained'] is False, 'LINUX_ADMISSION_RELEASE')
    harness = tree.read('run/' + EXECUTOR + 'harness/validation_bootstrap.gd')
    need(sha(harness) == result['profile_harness_sha256'] and result['profile_harness_unchanged'], 'LINUX_HARNESS_HASH')
    hashes = tree.json('run/' + EXECUTOR + 'input-manifest.json')
    need(len(hashes) == 11 and hashes == result['input_hashes_before'] == result['input_hashes_after'] == result['snapshot_hashes_after'],
         'LINUX_INPUT_MAPS')
    for name, digest in hashes.items():
        for root in (VALIDATION + '/input/', EXECUTOR + 'snapshot/'):
            need(sha(tree.read('run/' + root + name)) == digest, 'LINUX_INPUT_BYTES:' + name)
    return result, readback, hashes


def check_journal(tree):
    export = tree.json('audit/native-capture.json')
    custody_raw = tree.read('audit/native-custody.json')
    custody_envelope = json.loads(custody_raw)
    custody = custody_envelope['record']
    need(canonical(custody_envelope) == custody_raw and sha(canonical(custody)) == custody_envelope['sha256'], 'CUSTODY_CHECKSUM')
    need(sha(custody_raw) == export['custody_sha256'] and export['registry_unchanged'] and export['stream_unchanged']
         and export['native_resources_closed'] and export['cleanup_errors'] == [], 'NATIVE_EXPORT_HEALTH')
    raw = tree.read('audit/native-events.bin')
    need(sha(raw) == export['stream_sha256'] and len(raw) == export['stream_size_bytes'], 'NATIVE_EXPORT_BYTES')
    records = native_records(raw)
    need(records == export['native_records'] and len(records) == 9, 'NATIVE_EXPORT_RECORDS')
    binding = export['native_binding']
    need(records[-1]['head'] == binding['witnessed'] == custody['events']['binding']['witnessed'], 'CUSTODY_HEAD_BINDING')
    for key in ('root', 'stream'):
        need(all(binding[key][k] == custody['events']['binding'][key][k] for k in ('volume', 'file_id')), 'CUSTODY_NATIVE_IDENTITY')
    need(records[0]['event'] == {'kind': 'GENESIS', 'store_id': custody['events']['path'].replace('\\', '/').split('/')[-1],
          'volume': binding['stream']['volume'], 'file_id': binding['stream']['file_id'], 'root_file_id': binding['root']['file_id']}, 'STREAM_GENESIS')
    events = [record['event'] for record in records[4:]]
    need(events == tree.json('run/recovery-events.json') and [e['kind'] for e in events]
         == ['CONFIG', 'CAPTURE_PREPARED', 'ADMITTED', 'READBACK', 'TERMINAL'], 'EXACT_RECOVERY_EVENT_SEQUENCE')
    prefix = recovery._model.replay(tuple(canonical(event) for event in events[:2]))
    folded = recovery._fold_recovery(prefix, tuple(canonical(event) for event in events[2:]))
    snapshot = tree.json('run/journal-snapshot.json')
    need(folded == snapshot['recovery'], 'PURE_RECOVERY_FOLD')
    need(all(snapshot[k] == v for k, v in prefix.snapshot().items()), 'PURE_PUBLICATION_PREFIX_FOLD')
    need(snapshot['source_closure_sha256'] == EXPECTED and snapshot['journal_read_only'] is True
         and snapshot['new_mutation_permitted'] is False and snapshot['public_ack'] is False
         and snapshot['held'] is False and snapshot['stopped'] is False, 'JOURNAL_SCOPE')
    need(events[2]['native_head'] == records[5]['head'], 'ADMISSION_NATIVE_HEAD')
    need(events[2]['admission']['authority_epoch'] == 2 > snapshot['highest_fencing_epoch']
         and events[2]['admission']['session_id'] != events[1]['admission']['session_id'], 'FRESH_REGISTERED_FENCE')
    original = tree.json('run/original/original.json')
    need(custody['storage_id'] == original['storage_id'] and custody['project_id'] == original['project_id']
         == snapshot['project_id'] and custody['phase'] == 'READY', 'CUSTODY_PROJECT')
    selected = snapshot['selected']
    need(selected == snapshot['last_good'] == events[2]['selected'] and {'selector': selected['selector'],
         'selector_version': selected['selector_version']} == original['selection'], 'ORIGINAL_SELECTOR_UNCHANGED')
    need(tree.read('audit/native-selector.json') == canonical(selected['selector'])
         and export['selector_version'] == selected['selector_version'], 'SELECTOR_RAW_BINDING')
    manifest = selected['bundle_manifest']
    descriptor = selected['selector']['descriptor']
    need(tree.read('audit/native-manifest.json') == canonical(manifest), 'MANIFEST_RAW_BINDING')
    need(export['manifest_version'] == {k: v for k, v in descriptor['manifest'].items() if k != 'name'}, 'MANIFEST_NATIVE_VERSION')
    need(export['files_root'] == descriptor['root_identity'] == snapshot['content_root_identity'], 'PROJECT_NATIVE_ROOT')
    need(all(export['files_root'][k] == custody['files']['identity'][k] for k in ('volume', 'file_id')), 'PROJECT_CUSTODY_ROOT')
    need(export['selected_files'] == {name: {k: v for k, v in row.items() if k != 'name'}
         for name, row in descriptor['files'].items()} and len(export['selected_files']) == 11, 'ALL_NATIVE_FILE_VERSIONS')
    boot = [r['event'] for r in records[1:4]]
    need([e['kind'] for e in boot] == ['BOOTSTRAP_PREPARED', 'BOOTSTRAP_SELECTING', 'BOOTSTRAP_SELECTED']
         and boot[0]['bundle_manifest'] == manifest and boot[1]['selector'] == selected['selector']
         and boot[2]['selector_version'] == selected['selector_version'], 'BOOTSTRAP_NATIVE_BINDING')
    need(events[0] == dict(boot[0]['config'], initial=selected), 'BOOTSTRAP_CONFIG_BINDING')
    command = snapshot['commands'][0]
    need(len(snapshot['commands']) == 1 and command['phase'] == 'CAPTURE_PREPARED' and 'response' not in command,
         'ORIGINAL_PENDING_WITHOUT_RESPONSE')
    response = tree.json('run/response.json')
    wire = tree.read('run/response-wire.json')
    need(wire == canonical(response) == canonical(events[4]['response']) == canonical(folded['attempts'][0]['response']), 'EXACT_TERMINAL_WIRE')
    need(response['status'] == 'REJECTED' and response['code'] == 'GODOT_RECOVERED_LAST_GOOD'
         and response['postconditions']['files_saved'] is False and response['postconditions']['restored_editor_history'] is False
         and response['postconditions']['restored_last_good'] is True and response['postconditions']['public_ack'] is False,
         'RECOVERED_REJECTION_SEMANTICS')
    request = tree.json('run/request.json')
    need(request['command_id'] == command['command_id'] == response['command_id']
         and request['digest'] == command['digest'] == original['request']['digest']
         and request['fencing_epoch'] == events[2]['admission']['authority_epoch']
         and request['deadline_ms'] == events[2]['admission']['deadline_ms'], 'AUTHENTICATED_REQUEST_BINDING')
    return snapshot, original, events


def check_editors(tree, linux, readback, hashes, snapshot, original, events):
    selected = snapshot['selected']
    manifest = selected['bundle_manifest']
    scene_revision = 'sha256:' + sha(canonical(readback['semantic']['state']))
    need(original['before']['state'] == readback['semantic']['state'] and original['before']['revision'] == scene_revision
         == manifest['caller_observations']['scene_revision'], 'ORIGINAL_LINUX_SEMANTIC_BINDING')
    need({k: v['sha256'] for k, v in manifest['files'].items()} == hashes, 'SELECTED_LINUX_FILE_BINDING')
    need(snapshot['validator_engine_sha256'] == linux['toolchain']['binary_sha256'], 'VALIDATOR_ENGINE_PIN')
    boundary = tree.json('run/original/crash-boundary.json')
    captured = boundary['captured']
    raw_capture = tree.json('run/' + ORIGINAL_EDITOR + captured['capture_id'] + '.json')
    need(boundary['journal'] == dict(snapshot['commands'][0], execution_permitted=False, public_ack=False,
         engine_effects_verified=False, durable_owner_required=True) and captured['editor'] == original['editor_identity']
         and captured['scratch_name'] == events[1]['scratch_name'], 'CRASH_NATIVE_CAPTURE_BINDING')
    scratch = tree.read('run/' + ORIGINAL_EDITOR + 'scratch/' + captured['scratch_name'])
    need(sha(scratch) == captured['scene_sha256'] == raw_capture['scene_sha256'] and len(scratch)
         == captured['scene_size_bytes'] == raw_capture['scene_size_bytes'], 'CRASH_SCRATCH_BYTES')
    need(raw_capture['semantic_state'] == readback['semantic']['state'] and raw_capture['semantic_revision'] == scene_revision
         and raw_capture['request_digest'] == boundary['digest'] == original['request']['digest']
         and raw_capture['command_id'] == boundary['command_id'], 'CAPTURE_ACTUAL_SEMANTIC_BINDING')
    need(raw_capture['effect_started_ms'] == captured['effect_started_ms'] <= captured['effect_completed_ms']
         == raw_capture['effect_completed_ms'] <= boundary['observed_ms'], 'CAPTURE_BEFORE_CRASH')
    fresh = tree.json('run/actual-editor-identity.json')
    actual = tree.json('run/actual-editor.json')
    observation = events[3]['observation']
    need(fresh == observation['editor'] and all(fresh[k] != original['editor_identity'][k]
         for k in ('session_id', 'pid', 'creation_filetime', 'root_identity')), 'ACTUAL_FRESH_EDITOR_IDENTITY')
    need(actual['generation'] == observation['generation'] == 2 > original['before']['generation']
         and not actual['can_undo'] and not actual['can_redo'] and not actual['held'], 'ACTUAL_FRESH_HISTORY_BOUNDARY')
    need(actual['state'] == original['before']['state'] and actual['revision'] == observation['semantic_revision']
         == scene_revision and actual['editor_session_id'] == fresh['session_id'], 'RECOVERY_SEMANTIC_READBACK')
    need(observation['files'] == manifest['files'] and observation['manifest_sha256'] == sha(canonical(manifest))
         and observation['selector_version'] == selected['selector_version'], 'RECOVERY_COMPLETE_BUNDLE_BINDING')
    expected_files = {k: {n: v[n] for n in ('sha256', 'size_bytes')} for k, v in manifest['files'].items()}
    need(actual['working_files'] == original['before']['working_files'] == expected_files, 'EDITOR_FULL_WORKING_FILES')
    lock = tree.json('run/source/studio/toolchain.lock.json')
    need(fresh['engine_sha256'] == original['editor_identity']['engine_sha256'] == snapshot['editor_engine_sha256']
         == lock['godot']['gui_sha256'], 'WINDOWS_EDITOR_ENGINE_PIN')
    for root, identity in ((ORIGINAL_EDITOR, original['editor_identity']), (RECOVERY_EDITOR, fresh)):
        start = tree.json('run/' + root + 'process-start.json')
        hello = tree.json('run/' + root + 'hello.json')
        need(start['pid'] == hello['pid'] == identity['pid'] and hello['editor_session_id'] == identity['session_id']
             and hello['main_thread'] and hello['editor_hint'], 'EDITOR_RAW_HANDSHAKE')
        text = tree.read('run/' + root + 'stdout.txt').decode() + tree.read('run/' + root + 'stderr.txt').decode()
        need(not re.search(r'ERROR|WARNING|leaked', text), 'EDITOR_LOG_CLEAN')
        for name, digest in hashes.items():
            need(sha(tree.read('run/' + root + 'project/' + name)) == digest, 'EDITOR_PROJECT_BYTES:' + name)
    closed = tree.json('run/editor-close.json')
    need(closed == tree.json('run/' + RECOVERY_EDITOR + 'close.json') and closed['actual_process_exit']
         == tree.json('run/' + RECOVERY_EDITOR + 'process-exit.json') == {'pid': fresh['pid'], 'exit_code': 0}
         and closed['wrapper_exit_code'] == 0 and job_clean(closed['job']) and closed['closed'] and not closed['held']
         and not closed['logs_overflow'], 'EDITOR_ACTUAL_EXIT_CLEANUP')
    editor_module = recovery._load('editor_owner')
    validation_module = recovery._load('validation_owner')
    need(sha(canonical(editor_module._release())) == fresh['installed_source_sha256']
         == original['editor_identity']['installed_source_sha256'], 'EDITOR_RUNTIME_RELEASE')
    need(validation_module.source_release()[1] == snapshot['validation_source_release_sha256'], 'VALIDATION_RUNTIME_RELEASE')


def verify(tree):
    files = source_check(tree)
    load_pure()
    check_processes(tree)
    linux, readback, hashes = check_linux(tree)
    snapshot, original, events = check_journal(tree)
    check_editors(tree, linux, readback, hashes, snapshot, original, events)
    return {'schema': 'hh-recovery-publication-audit-1', 'passed': True, 'candidate_only': True,
            'gt03_acceptance': False, 'independent_acceptance_critic': False, 'source_closure_sha256': EXPECTED,
            'source_files_verified': len(files), 'harness_assertions_verified': 14, 'native_sequence': 9,
            'native_selected_files': 11, 'original_target_exit': 92, 'outer_target_exit': 0,
            'validation_container_id': linux['container_id'],
            'actual_pids': {'outer': tree.json('run/recovery-publication-host.json')['target_pid'],
                           'original': tree.json('run/original/original-host.json')['target_pid'],
                           'original_editor': original['editor_identity']['pid'],
                           'recovery_editor': tree.json('run/actual-editor-identity.json')['pid']},
            'runtime_release_sha256': {'validation': snapshot['validation_source_release_sha256'],
                                      'editor': tree.json('run/actual-editor-identity.json')['installed_source_sha256']},
            'linux_phase_exits': {'parse': 0, 'import': 0, 'readback': 0}, 'recovery_editor_exit': 0,
            'original_response': 'absent; original command remains CAPTURE_PREPARED',
            'recovered_response': 'REJECTED / GODOT_RECOVERED_LAST_GOOD',
            'public_mutation_enabled': False, 'original_live_source_unchanged': False,
            'scope': 'exact frozen component chain; captured HTTP assertions; read-only native post-run export',
            'limitations': ['No independent GT03 acceptance signature.', 'No full HTTP packet transcript is persisted; retry/auth claims are captured harness assertions.',
                'Original editor has no graceful exit receipt after intentional host crash; enclosing owned Job tree is captured clean.',
                'Portable custody export detects alteration but does not itself reproduce Windows ACL authority.',
                'No proof transfers to newer live source, V5 edit recovery, Undo/Redo, unknown restoration, orphan COMMITTED, or GT07.']}


def mutation_tests():
    tree = Tree()
    cases = []
    def raw(name, value, label):
        cases.append((label, {name: value}))
    def change(name, path, value, label):
        obj = tree.json(name)
        at = obj
        for key in path[:-1]:
            at = at[key]
        at[path[-1]] = value
        raw(name, json.dumps(obj).encode(), label)
    raw('run/source/studio/godot-addon/publication_recovery.py', tree.read('run/source/studio/godot-addon/publication_recovery.py') + b'\n# corrupted\n', 'changed frozen recovery source')
    change('run/recovery-publication-host.json', ['exit_code'], 1, 'forged outer success')
    change('run/original/original-host.json', ['exit_code'], 0, 'lost actual crash92')
    change('run/' + EXECUTOR + 'engine-host.json', ['job_owner', 'active_count'], 1, 'unclosed Linux host Job')
    raw('run/' + EXECUTOR + 'wait-stdout.txt', b'7\n', 'nonzero actual docker wait')
    change('run/' + EXECUTOR + 'exited-inspect-stdout.txt', [0, 'State', 'ExitCode'], 23, 'forged container success')
    raw('run/' + EXECUTOR + 'snapshot/scenes/fixture.tscn', b'tampered', 'changed isolated input')
    change('audit/native-capture.json', ['selected_files', 'scenes/fixture.tscn', 'file_id'], '0' * 32, 'substituted selected native FileID')
    raw('audit/native-events.bin', tree.read('audit/native-events.bin')[:-1], 'truncated protected event stream')
    stream = bytearray(tree.read('audit/native-events.bin')); stream[-40] ^= 1
    raw('audit/native-events.bin', bytes(stream), 'changed native terminal bytes')
    change('audit/native-custody.json', ['record', 'events', 'binding', 'witnessed', 'sequence'], 8, 'rolled back durable custody witness')
    change('run/actual-editor.json', ['state', 'nodes', 0, 'position', 0], 99, 'changed actual recovered semantic state')
    change('run/actual-editor-identity.json', ['session_id'], tree.json('run/original/original.json')['editor_identity']['session_id'], 'reused old editor session')
    change('run/response.json', ['status'], 'COMMITTED', 'invented successful original save')
    raw('run/response-wire.json', tree.read('run/response-wire.json') + b'\n', 'non-exact terminal wire retry bytes')
    change('run/recovery.json', ['gt03_acceptance'], True, 'inflated acceptance claim')
    results = []
    for label, overlay in cases:
        try:
            verify(Tree(overlay))
        except (ValueError, AssertionError, KeyError) as exc:
            results.append({'case': label, 'rejected': True, 'reason': str(exc)})
        else:
            raise Invalid('TAMPER_ACCEPTED:' + label)
    # Deep replay tests bypass artifact digests, exercising the typed suffix fold.
    events = tree.json('run/recovery-events.json')
    prefix = recovery._model.replay(tuple(canonical(e) for e in events[:2]))
    suffix_cases = [('stale reconciliation authority', (0, 'admission', 'authority_epoch'), 1),
                    ('forged recovery generation', (0, 'editor_generation'), 1),
                    ('forged terminal save success', (2, 'response', 'status'), 'COMMITTED'),
                    ('changed recovery prefix digest', (1, 'publication_prefix_sha256'), '0' * 64)]
    for label, path, value in suffix_cases:
        suffix = copy.deepcopy(events[2:]); at = suffix
        for key in path[:-1]:
            at = at[key]
        at[path[-1]] = value
        try:
            recovery._fold_recovery(prefix, tuple(canonical(e) for e in suffix))
        except ValueError as exc:
            results.append({'case': label, 'rejected': True, 'reason': str(exc)})
        else:
            raise Invalid('REPLAY_TAMPER_ACCEPTED:' + label)
    return {'schema': 'hh-recovery-audit-tamper-1', 'passed': True, 'rejected': len(results),
            'original_package_mutated': False, 'engine_rerun': False, 'cases': results}


def manifest_files():
    result = {}
    for directory in (PACKAGE, HERE):
        for path in sorted(directory.rglob('*')):
            if not path.is_file() or any(part.lower() in ('.godot', '__pycache__', 'appdata', 'localappdata', 'storage', 'temp')
                                         for part in path.relative_to(directory).parts):
                continue
            if directory == HERE and path.name == 'portable-manifest.json':
                continue
            result[path.relative_to(HERE.parent).as_posix()] = sha(path.read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--write', action='store_true'); args = parser.parse_args()
    result = verify(Tree())
    mutations = mutation_tests()
    result['tamper_rejections'] = mutations['rejected']
    if args.write:
        for name, value in (('verification.json', result), ('tamper-report.json', mutations)):
            (HERE / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        files = manifest_files()
        manifest = {'schema': 'hh-recovery-portable-manifest-1', 'source_closure_sha256': EXPECTED,
                    'algorithm': 'sha256(relative-posix-path NUL sha256 NEWLINE), sorted by path',
                    'excluded': ['.godot/', '__pycache__/', 'appdata/', 'localappdata/', 'storage/', 'temp/', 'portable-manifest.json itself'],
                    'files': files, 'files_sha256': sha(''.join(k + '\0' + v + '\n' for k, v in sorted(files.items())).encode()),
                    'gt03_acceptance': False}
        (HERE / 'portable-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    else:
        manifest = json.loads((HERE / 'portable-manifest.json').read_text())
        need(manifest['files'] == manifest_files(), 'PORTABLE_ARTIFACT_MANIFEST')
        need(manifest['files_sha256'] == sha(''.join(k + '\0' + v + '\n' for k, v in sorted(manifest['files'].items())).encode()), 'PORTABLE_MANIFEST_DIGEST')
        need(json.loads((HERE / 'verification.json').read_text()) == result, 'STORED_VERIFICATION_RESULT')
        need(json.loads((HERE / 'tamper-report.json').read_text()) == mutations, 'STORED_TAMPER_RESULT')
    print(json.dumps(dict(result, portable_artifacts=len(manifest['files']), portable_artifact_digest=manifest['files_sha256'])))


if __name__ == '__main__':
    main()
