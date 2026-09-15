"""Read-only native artifact verification. Works under python -O as well.

The pinned manifest covers runtime inputs/logs; this verifier is covered by
Git, not by its own manifest (which would create a circular hash). Missing raw
local records are reported explicitly in a portable public reconstruction.
"""
import hashlib
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
MANIFEST = '3f5a5d5b26b199897161048a8c70bf4a98cef46595b00e3d08d5c33f8b903363'
CLOSURE = '264ed3e3f35ca76038ba20cc00f41f3345ba6e9352e111b3be5e7ed38fe6e111'


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(items):
    result = {}
    for key, value in items:
        need(key not in result, 'DUPLICATE_KEY')
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def confined(root, relative):
    need(type(relative) is str and relative and ':' not in relative and '\\' not in relative
         and all(item not in ('', '.', '..') for item in relative.split('/')), 'UNSAFE_PATH')
    path = root.joinpath(*relative.split('/'))
    path.resolve().relative_to(root.resolve())
    need(not path.is_symlink(), 'UNSAFE_PATH')
    return path


def verify():
    need(sha(BASE/'manifest.json') == MANIFEST, 'MANIFEST_HASH_MISMATCH')
    manifest = read(BASE/'manifest.json')
    need(manifest['source_closure_sha256'] == CLOSURE and manifest['acceptance'] is False, 'MANIFEST_SCOPE')
    for name, digest in manifest['files'].items():
        need(sha(confined(BASE, name)) == digest, 'ARTIFACT_HASH_MISMATCH')
    for name, digest in manifest['dependencies'].items():
        need(sha(confined(ROOT, name)) == digest, 'DEPENDENCY_HASH_MISMATCH')
    public = None
    for number in ('01', '02', '03'):
        host = read(BASE/('run-'+number+'.host.json'))
        output = BASE/('run-'+number+'.stdout.json')
        error = BASE/('run-'+number+'.stderr.txt')
        source = BASE/('ipc_probe.py' if number == '03' else 'ipc_probe.run-'+number+'.py')
        need(host['run_id'] == 'GT02-S35-NATIVE-'+number and host['host_exit'] == 0
             and host['timed_out'] is False, 'PROBE_EXIT')
        need(host['probe_sha256'] == sha(source) and host['stdout_sha256'] == sha(output)
             and host['stderr_sha256'] == sha(error) and error.read_bytes() == b'', 'CAPTURE_HASH')
        value = read(output)
        need(value['source_sha256'] == host['probe_sha256'] and value['diagnostic_complete'] is True, 'PROBE_COMPLETION')
        if number == '03':
            public = value
    need(public['native_source_sha256'] == sha(BASE/'boundary_child.c'), 'NATIVE_SOURCE')
    need(public['safe_write'] is False and public['acceptance'] is False, 'NO_ACCEPTANCE')
    for key in ('runtime_snapshot_used','runtime_source_unchanged','runtime_snapshot_unchanged',
                'runtime_snapshot_removed','profile_absent_before','profile_exists_after_create',
                'profile_absent_after','owned_temp_removed'):
        need(public[key] is True, key)
    need(public['create_profile_hresult'] == public['delete_profile_hresult'] == 0, 'PROFILE_LIFECYCLE')
    need(public['remaining_endpoint_owners'] == public['remaining_io_owners'] == 0, 'OWNER_CLEANUP')
    files = public['runtime_closure']['files']
    rows = []
    for name, digest in sorted(files.items()):
        need(sha(confined(ROOT/'studio', name)) == digest, 'RUNTIME_SOURCE_HASH')
        rows.append('8-9-hh3d-3/studio/'+name+'\0'+digest+'\n')
    need(hashlib.sha256(''.join(rows).encode()).hexdigest() == CLOSURE
         == public['runtime_closure']['source_closure_sha256'], 'RUNTIME_CLOSURE')
    for module, record in public['loaded_runtime_modules'].items():
        need(module.startswith('studio.') and files.get(record['relative']) == record['sha256'], 'LOADED_MODULE')
    for name in ('pipe_io','pipe_endpoint','fixture_pipe','transport','journal'):
        need('studio.host.core.'+name in public['loaded_runtime_modules'], 'MISSING_RUNTIME_MODULE')
    modes = ['submit','wrong_token','stale_lease','drop_reply','cancel','stop']
    need([item['mode'] for item in public['cases']] == modes, 'CASE_MEMBERSHIP')
    for item in public['cases']:
        mode = item['mode']
        need('error' not in item and not item.get('forced_owned_termination'), 'CASE_ERROR')
        need(item['host_exit'] == item['final_host_exit'] == 57
             and item['final_job_active'] == 0 and item['final_job_pids'] == [], 'NATIVE_EXIT_TREE')
        need(item['primary_token_verified'] is True and item['inherit_handles'] is False, 'PROCESS_BOUNDARY')
        bindings = item['retained_process_binding']
        need(bindings['work'] == bindings['control'] and bindings['work'][0] == item['pid']
             and bindings['work'][1] > 0, 'RETAINED_PROCESS_IDENTITY')
        native = item['native']
        need(native['started'] == 'S35_NATIVE_STARTED' and native['complete'] == 'S35_NATIVE_COMPLETE', 'NATIVE_MARKERS')
        need(all(native[key] == 5 for key in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error')), 'PIPE_RIGHTS')
        need(native['work_reply_received'] == (mode != 'drop_reply'), 'REPLY_DELIVERY')
        for role in ('work','control'):
            key = role+'_reply_hex'
            if key in native:
                need(json.loads(bytes.fromhex(native[key]), object_pairs_hook=unique) == item[role+'_dispatch'], 'NATIVE_REPLY_READBACK')
        changed = mode in ('submit','drop_reply')
        need(item['snapshot'] == {'value':101 if changed else 0,'revision':'rev-1' if changed else 'rev-0',
                                   'effect_count':int(changed)}, 'FIXTURE_POSTCONDITION')
        if changed:
            need(item['terminal_before_lookup']['status'] == item['control_dispatch']['status'] == 'COMMITTED'
                 and item['same_id_replay_effect_count'] == 1, 'REPLAY_DUPLICATED_EFFECT')
        if mode == 'wrong_token':
            need(item['work_dispatch']['code'] == 'SESSION_BINDING_MISMATCH', 'SESSION_NOT_BOUND')
        if mode == 'stale_lease':
            need(item['work_dispatch']['code'] == 'STALE_LEASE', 'LEASE_NOT_CHECKED')
        if mode in ('wrong_token','stale_lease'):
            need(item['control_dispatch']['code'] == 'COMMAND_NOT_FOUND', 'INVALID_ADMISSION')
        if mode in ('cancel','stop'):
            need(item['final_work_terminal']['status'] == 'CANCELED', 'CANCEL_FAILED')
        if mode == 'stop':
            need(item['final_control_terminal']['status'] == 'COMMITTED', 'STOP_FAILED')
    wrong = public['wrong_client']
    need(wrong['rejection'] == 'PIPE_CLIENT_MISMATCH' and wrong['bound_identity'][0] != wrong['actual_client_pid'], 'WRONG_PID_NOT_REJECTED')
    need(wrong['placeholder_resumed'] is False and wrong['dispatcher_called'] is False
         and wrong['placeholder_exit'] == 125 and wrong['job_active'] == 0 and wrong['job_pids'] == [], 'PLACEHOLDER_LIFECYCLE')
    local = []
    for field, digest_key in (('raw_relative','raw_sha256'),('native_executable_relative','native_executable_sha256')):
        need(public[field].startswith('studio/.local/review-raw/S35/'), 'RAW_SCOPE')
        path = confined(ROOT, public[field])
        if path.exists():
            need(sha(path) == public[digest_key], 'RAW_OR_BINARY_HASH')
            local.append(field)
            if field == 'raw_relative':
                need(read(path) == {key:value for key,value in public.items() if key not in ('raw_relative','raw_sha256')}, 'RAW_PUBLIC_DERIVATION')
    need(not re.search(r'S-1-5-21-\d+-\d+-\d+-\d+', (BASE/'run-03.stdout.json').read_text()), 'HOST_SID_LEAK')
    return {'status':'DIAGNOSTIC_ARTIFACTS_VERIFIED','manifest_sha256':MANIFEST,
            'source_closure_sha256':CLOSURE,'source_files':len(files),'artifacts':len(manifest['files']),
            'runtime_modules':len(public['loaded_runtime_modules']),'native_cases':len(modes),
            'wrong_client_pid_rejected':True,'local_raw_checks':local,
            'raw_available':len(local)==2,'formal_acceptance':False}


if __name__ == '__main__':
    print(json.dumps(verify()))
