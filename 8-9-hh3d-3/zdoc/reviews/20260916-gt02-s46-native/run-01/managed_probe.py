"""Owned native service diagnostic; no direct dispatch/advance or source patches."""
from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
HELPER = BASE.parent / '20260915-gt02-s32-boundary'
BUILD_HELPER = BASE.parent / '20260916-gt02-s44-boundary'
sys.path[:0] = [str(HELPER), str(BUILD_HELPER)]
import boundary_probe as prior
from windows_api import *
from compile_native import compile_native


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(executable, scratch, package, owner, mode, user, registry_control):
    from studio.host.core.managed_service import ManagedPipeService
    from studio.host.core.selector_pipe import SelectorFixtureBroker
    from studio.host.core.pipe_endpoint import AppContainerEndpoint
    from studio.host.core.transport import TransportLimits
    from studio.host.core.custody_registry import BASE_PATH
    pi, si = PI(), SIEX()
    job = attrs = service = work = control = broker = None
    assigned = False
    logfile = scratch / (mode + '.json')
    record = {'mode':mode, 'inherit_handles':False, 'credentials_in_environment':False,
              'launcher_calls_dispatch_or_advance':False}
    record['attempted_access'] = {
        'pipe_write_dac_error':'WRITE_DAC (0x00040000)',
        'pipe_write_owner_error':'WRITE_OWNER (0x00080000)',
        'second_instance_error':'PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE | PIPE_REJECT_REMOTE_CLIENTS',
        'private_read_error':'FILE_LIST_DIRECTORY (0x1); OPEN_REPARSE_POINT | BACKUP_SEMANTICS',
        'private_write_error':'FILE_ADD_FILE (0x2); OPEN_REPARSE_POINT | BACKUP_SEMANTICS',
        'events_access_error':'FILE_READ_DATA | FILE_WRITE_DATA (0x3); OPEN_REPARSE_POINT',
        'registry_read_write_error':'KEY_QUERY_VALUE | KEY_SET_VALUE | KEY_WOW64_64KEY (0x103); REG_OPTION_OPEN_LINK',
        'registry_positive_control':'same HKU owner prefix; same 0x103 access/open-link; query/set/query State',
    }
    secret = None
    try:
        broker = SelectorFixtureBroker.from_managed(owner, limits=TransportLimits(request_timeout_ms=10_000))
        credential = broker.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))
        secret = credential.bearer
        work = AppContainerEndpoint.create(sid_text(package), role='work')
        control = AppContainerEndpoint.create(sid_text(package), role='control')
        before_custody = owner.registry.read()
        before_binding = owner.log.binding()
        before_active = owner.files.read('active.json') if owner.selector.snapshot()['selected'] is not None else None
        before_names = {key:sorted(p.name for p in component.root.iterdir()) for key,component in
                        (('files',owner.files),('store',owner.store),('events',owner.log))}
        size = C.c_size_t()
        K.InitializeProcThreadAttributeList(None,2,0,C.byref(size))
        attrs = C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs,2,0,C.byref(size)))
        caps, policy = CAPS(package,None,0,0), W.DWORD(1)
        checked(K.UpdateProcThreadAttribute(attrs,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
        checked(K.UpdateProcThreadAttribute(attrs,0,0x2000e,C.byref(policy),C.sizeof(policy),None,None))
        si.si.cb, si.attributes = C.sizeof(SIEX), C.addressof(attrs)
        values = {key:os.environ[key] for key in ('SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','SystemDrive')}
        values.update(WINDIR=os.environ['SystemRoot'],PATH=str(Path(os.environ['SystemRoot'])/'System32'),
            TEMP=str(scratch),TMP=str(scratch),S46_WORK=work.address,S46_CONTROL=control.address,
            S46_LOG=str(logfile),S46_MODE=mode,S46_PRIVATE_ROOT=str(owner.files.root),
            S46_EVENTS=str(owner.log.root/'.events'),S46_REGISTRY=user+'\\'+BASE_PATH+'\\'+owner.storage_id,
            S46_REG_CONTROL=registry_control)
        assert all(secret not in value for value in values.values())
        environment = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(values.items()))+'\0\0')
        checked(K.CreateProcessW(str(executable),C.create_unicode_buffer('"'+str(executable)+'"'),None,None,False,
            0x8040c,environment,str(scratch),C.byref(si),C.byref(pi)))
        record['pid'] = int(pi.pid)
        work.bind_worker(pi.process); control.bind_worker(pi.process)
        record['retained_process_binding'] = {'work':list(work._identity),'control':list(control._identity)}
        job = checked(K.CreateJobObjectW(None,None))
        limits = JEXT()
        limits.basic.flags, limits.basic.active_processes, limits.process_memory = 0x2108,1,128*1024*1024
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job,pi.process)); assigned = True
        checked(K.ResumeThread(pi.thread) != 0xffffffff)
        work.connect(timeout_ms=3000); control.connect(timeout_ms=3000)
        # Child completed all adversarial filesystem/registry attempts before
        # opening both pipes and blocks awaiting bootstrap. No RPC can run yet.
        assert owner.registry.read() == before_custody and owner.log.binding() == before_binding
        if before_active is not None:
            assert owner.files.read('active.json') == before_active
        assert {key:sorted(p.name for p in component.root.iterdir()) for key,component in
                (('files',owner.files),('store',owner.store),('events',owner.log))} == before_names
        record['protected_custody_binding_and_names_unchanged_before_bootstrap'] = True
        record['existing_active_file_identity_and_bytes_unchanged_before_bootstrap'] = before_active is not None
        record['protected_custody_before_bootstrap_sha256'] = hashlib.sha256(before_custody).hexdigest()
        service = ManagedPipeService(owner,broker,work,control,credential,session_timeout_ms=30_000,drain_timeout_ms=2000)
        service.start()
        assert K.WaitForSingleObject(pi.process,15_000) == 0, 'native child timeout'
        code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
        record['host_exit'] = int(code.value)
        native_raw = logfile.read_bytes()
        import base64
        assert secret.encode() not in native_raw and secret.encode().hex().encode() not in native_raw
        assert base64.b64encode(secret.encode()) not in native_raw
        record['credential_artifact_scan_passed'] = True
        record['native'] = json.loads(native_raw)
        assert record['host_exit'] == 86 and record['native']['complete'] == 'S46_NATIVE_COMPLETE'
        assert record['native']['registry_positive_control_read_write'] is True
        for key in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error','private_read_error',
                    'private_write_error','events_access_error','registry_read_write_error'):
            assert record['native'][key] == 5
        decoded = {key[:-4]:json.loads(bytes.fromhex(value)) for key,value in record['native'].items() if key.endswith('_hex')}
        record['decoded_replies'] = decoded
        assert decoded['discovery']['project_id'] == owner.project_id
        assert decoded['discovery']['schema_digest'].startswith('sha256:')
        assert {cap['operation'] for cap in decoded['discovery']['capabilities']} == {'fixture.release.activate','fixture.release.inspect'}
        assert 'filesystem_identifiers' not in json.dumps(decoded)
        if mode != 'drop_reply':
            assert decoded['lookup']['status'] == 'COMMITTED'
            assert decoded['retry'] == decoded['lookup']
            assert decoded['final_inspect']['generation'] == decoded['initial_inspect']['generation'] + 1
            assert decoded['final_inspect']['ready'] is True
        else:
            assert decoded['lookup']['status'] in ('UNKNOWN','COMMITTED')
            assert record['native']['work_reply_received'] is False
        if mode != 'create': assert decoded['stop']['stopped'] is True
        service.close()
        record['service_closed'] = service.status()
        assert record['service_closed']['closed'] and record['service_closed']['live_threads'] == 0
        record['snapshot'] = owner.selector.snapshot()
        record['event_kinds'] = [json.loads(owner.log.read(i).event)['kind'] for i in range(1,owner.log.binding().witnessed.sequence+1)]
        record['custody_epoch'] = owner.custody.record['epoch']
        record['event_high_water'] = owner.custody.binding.witnessed.sequence
        assert owner.custody.binding == owner.log.binding()
        if mode != 'drop_reply':
            version, data = owner.files.read('active.json')
            record['active_file'] = asdict(version)
            record['active_bytes_sha256'] = hashlib.sha256(data).hexdigest()
            record['active_generation_value'] = json.loads(data)['assets']['scene']['value']
            assert record['active_generation_value'] == 'native generation '+str(record['snapshot']['generation'])
            assert record['event_kinds'].count('TERMINAL') == record['snapshot']['generation']
        assert record['snapshot']['stopped'] == (mode != 'create')
    except Exception as exc:
        # No exception can include the secret-bearing bootstrap/requests here.
        message = str(exc)
        if secret: message = message.replace(secret,'<REDACTED>')
        record['error'] = {'type':type(exc).__name__,'message':message,'winerror':getattr(exc,'winerror',None)}
    finally:
        if pi.process and K.WaitForSingleObject(pi.process,0) != 0:
            checked(K.TerminateJobObject(job,123) if assigned else K.TerminateProcess(pi.process,123))
            assert K.WaitForSingleObject(pi.process,5000) == 0
            record['forced_owned_termination'] = True
        if service is not None:
            service.close()
        else:
            for endpoint in (work,control):
                if endpoint is not None: endpoint.close()
            if broker is not None: broker.close()
        if pi.process:
            code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
            record['final_host_exit'] = int(code.value)
        if assigned:
            account = JACCOUNT()
            for _ in range(101):
                checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                if account.active_processes == 0: break
                time.sleep(.02)
            pids = prior.PIDLIST(); checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
            record['final_job_active'], record['final_job_pids'] = int(account.active_processes),list(pids.pids)[:pids.count]
        if logfile.exists() and 'native' not in record:
            raw = logfile.read_bytes()
            if secret: assert secret.encode() not in raw
            try: record['native'] = json.loads(raw)
            except ValueError: record['partial_native_log'] = raw.decode(errors='replace')
        for handle in (pi.thread,pi.process,job):
            if handle: checked(K.CloseHandle(handle))
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)
    return record


def main():
    spec = importlib.util.spec_from_file_location('freeze',PRODUCT/'studio/tests/protocol/run_gt02_candidate.py')
    freeze = importlib.util.module_from_spec(spec); spec.loader.exec_module(freeze)
    files = freeze.source_manifest()
    runtime = tempfile.TemporaryDirectory(prefix='gt02-s46-runtime-')
    runtime_root = Path(runtime.name).resolve()
    for name,digest in files.items():
        data = (PRODUCT/'studio'/name).read_bytes(); assert hashlib.sha256(data).hexdigest() == digest
        target = runtime_root/'studio'/name; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    sys.path.insert(0,str(runtime_root))
    from studio.host.core.managed_fixture import ManagedFixtureOwner
    from studio.host.core.custody_registry import _RegistryApi,BASE_PATH,_HKCU,_ACCESS,pending_custody_cleanup
    from studio.host.core.pipe_endpoint import _ENDPOINTS
    from studio.host.core.pipe_io import _OWNERS
    from studio.host.core.private_events import _OWNERS as EVENT_OWNERS
    from studio.host.core.transport import epoch_ms
    moniker = 'hh-gt02-s46-'+uuid.uuid4().hex
    profile = Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package,token = C.c_void_p(),W.HANDLE()
    created = False; base = mapping = managed = control_api = None; owned_ids = []; managed_ids = []
    out = {'run_id':sys.argv[1],'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'runtime_closure':{'source_closure_sha256':freeze.RUNNER.source_closure_sha256(files),'files':files},
        'acceptance':False,'general_safe_write':False,'runtime_snapshot_used':True,'cases':[]}
    out['diagnostic_sources'] = {str(path.relative_to(BASE.parent)):sha(path) for path in
        (Path(__file__),BASE/'boundary_child.c',BUILD_HELPER/'compile_native.py',HELPER/'boundary_probe.py',HELPER/'windows_api.py')}
    try:
        if len(sys.argv) > 2: assert out['runtime_closure']['source_closure_sha256'] == sys.argv[2], 'candidate closure mismatch'
        checked(A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(token)))
        user = token_sid(token,1)
        checked(U.DeriveAppContainerSidFromAppContainerName(moniker,C.byref(package)) == 0)
        package_string = sid_text(package)
        mapping = 'Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+package_string
        assert not profile.exists() and not prior.mapping_exists(mapping)
        created_sid = C.c_void_p()
        assert U.CreateAppContainerProfile(moniker,moniker,'Owned S46 managed lifecycle probe',None,0,C.byref(created_sid)) == 0
        created = True; A.FreeSid(created_sid)
        control_api = _RegistryApi(); anchor,_,_ = control_api.base()
        control_id = uuid.uuid4().hex
        original = control_api.sddl
        control_api.sddl = original+'(A;;KRKW;;;'+package_string+')S:(ML;;NW;;;LW)'
        try:
            control_key = control_api.create(anchor,control_id); owned_ids.append(control_id)
        finally: control_api.sddl = original
        control_path = user+'\\'+BASE_PATH+'\\'+control_id
        control_api.validate_key(control_key,'\\REGISTRY\\USER\\'+control_path,protected=False)
        with tempfile.TemporaryDirectory(prefix='gt02-s46-native-') as tmp:
            base = Path(tmp).resolve(); base.relative_to(Path(tempfile.gettempdir()).resolve())
            compiled = compile_native(base,BASE/'boundary_child.c',out)
            common = 'D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;'+user+')'
            scratch,images = base/'scratch',base/'images'
            make_directory(scratch,common+'(A;OICI;0x1301bf;;;'+package_string+')S:(ML;OICI;NW;;;LW)')
            make_directory(images,common+'(A;OICI;GRGX;;;'+package_string+')')
            image = images/'boundary_child.exe'; image.write_bytes(compiled.read_bytes())
            out['executable_sha256'] = sha(image)
            try:
                for mode in ('create','replace_stop','drop_reply'):
                    if mode == 'replace_stop':
                        managed = ManagedFixtureOwner.reopen(managed_ids[0],project_id='project.fixture',now_ms=epoch_ms())
                        out['reopen_used_storage_id_only'] = True
                    else:
                        parent = base/('owner-'+mode); make_directory(parent,common)
                        managed = ManagedFixtureOwner.create(parent,project_id='project.fixture',initial_revisions={
                            'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
                        owned_ids.append(managed.storage_id); managed_ids.append(managed.storage_id)
                    control_api.set(control_key,'State',b'CONTROL'); control_api.flush(control_key)
                    record = run_case(image,scratch,package,managed,mode,user,control_path)
                    out['cases'].append(record)
                    record['registry_positive_control_host_readback'] = control_api.query(control_key,'State') == (3,b'CHILD_OK')
                    assert record['registry_positive_control_host_readback']
                    managed.close(); managed = None
                    assert 'error' not in record, 'native managed case failed: '+mode
                    assert record['final_host_exit'] == 86 and record['final_job_active'] == 0 and record['final_job_pids'] == []
                    assert not record.get('forced_owned_termination')
                assert out['cases'][0]['snapshot']['generation'] == 1
                assert out['cases'][1]['snapshot']['generation'] == 2
                assert out['cases'][0]['active_file']['identity'] != out['cases'][1]['active_file']['identity']
                out['native_create_replace_and_retry_verified'] = True
                out['work_disconnect_control_stop_verified'] = True
                out['remaining_endpoint_owners'],out['remaining_io_owners'] = len(_ENDPOINTS),len(_OWNERS)
                out['remaining_event_owners'] = len(EVENT_OWNERS)
                assert len(_ENDPOINTS) == len(_OWNERS) == len(EVENT_OWNERS) == 0
                assert not pending_custody_cleanup()
                out['marker'] = 'S46_MANAGED_SERVICE_NATIVE_COMPLETE'
            finally:
                if managed is not None: managed.close(); managed = None
    except Exception as exc:
        out['error'] = {'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if control_api is not None: control_api.close_owned()
        cleanup = _RegistryApi()
        try:
            cleanup.nt.NtDeleteKey.argtypes,cleanup.nt.NtDeleteKey.restype = [W.HANDLE],W.LONG
            for identifier in reversed(owned_ids):
                handle = W.HANDLE()
                assert cleanup.adv.RegOpenKeyExW(_HKCU,BASE_PATH+'\\'+identifier,8,_ACCESS|0x10000,C.byref(handle)) == 0
                cleanup.keys.add(handle.value)
                cleanup.validate_key(handle.value,'\\REGISTRY\\USER\\'+cleanup.owner+'\\'+BASE_PATH+'\\'+identifier,
                                     protected=identifier in managed_ids)
                assert cleanup.nt.NtDeleteKey(handle) == 0
                cleanup.close_key(handle.value)
                assert cleanup.adv.RegOpenKeyExW(_HKCU,BASE_PATH+'\\'+identifier,8,_ACCESS,C.byref(handle)) == 2
            out['owned_registry_leaves_removed'] = len(owned_ids)
        finally: cleanup.close_owned()
        if token: checked(K.CloseHandle(token))
        if package.value: A.FreeSid(package)
        if created: out['delete_profile_hresult'] = int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after'] = not profile.exists() and (mapping is None or not prior.mapping_exists(mapping))
        out['owned_temp_removed'] = base is not None and not base.exists()
        out['runtime_source_unchanged'] = freeze.source_manifest() == files
        out['runtime_snapshot_unchanged'] = freeze.source_manifest(runtime_root/'studio') == files
        out['loaded_runtime_modules'] = {}
        for name,module in tuple(sys.modules.items()):
            if name.startswith('studio.') and getattr(module,'__file__',None):
                path = Path(module.__file__).resolve(); relative = path.relative_to(runtime_root/'studio').as_posix()
                assert relative in files and sha(path) == files[relative]
                out['loaded_runtime_modules'][name] = {'relative':relative,'sha256':sha(path)}
        runtime.cleanup(); out['runtime_snapshot_removed'] = not runtime_root.exists()
    out['diagnostic_complete'] = bool(out.get('marker') and out.get('owned_registry_leaves_removed') == 3 and all(out[key] for key in (
        'profile_absent_after','owned_temp_removed','runtime_source_unchanged','runtime_snapshot_unchanged','runtime_snapshot_removed')))
    print(json.dumps(out,indent=2),flush=True)
    return 0 if out['diagnostic_complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
