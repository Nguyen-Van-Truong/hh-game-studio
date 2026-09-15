"""Owned native AppContainer through the actual S35 endpoint/RPC modules.

Fixed fixture only. Imported frozen S32 code supplies compiler/Job/profile
declarations, not endpoint authentication or dispatch. No runtime method is
patched. Process roots, profiles and every artifact belong to this diagnostic.
"""
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import uuid

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
PREVIOUS = BASE.parent / '20260915-gt02-s32-boundary'
sys.path.insert(0, str(PREVIOUS))
import boundary_probe as prior
from windows_api import *
sys.path.insert(0, str(PRODUCT))
from studio.host.core.fixture_pipe import FixturePipeServer, fixture_frame
from studio.host.core.pipe_endpoint import AppContainerEndpoint, EndpointError, _ENDPOINTS
from studio.host.core.pipe_io import PipeIOError, _OWNERS
from studio.host.core.journal import Journal
from studio.host.core.transport import LoopbackFixtureHost, FixtureClient
from studio.protocol.core import Status

RUN_ID = 'GT02-S35-NATIVE-01'
MODES = ('submit', 'wrong_token', 'stale_lease', 'drop_reply', 'cancel', 'stop')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminal(client, command):
    end = time.monotonic() + 3
    while time.monotonic() < end:
        result = client.lookup(command)
        if result.status is not Status.ACCEPTED_PENDING:
            return result
        time.sleep(.005)
    raise TimeoutError('Owned fixture terminal deadline')


def run_case(executable, scratch, broker_root, package, mode):
    pi, si = PI(), SIEX()
    job, attrs, assigned = None, None, False
    logfile = scratch / (mode + '.json')
    record = {'mode': mode, 'inherit_handles': False, 'primary_token_verified': False}
    with ExitStack() as stack:
        host = stack.enter_context(LoopbackFixtureHost('project.fixture', broker_root, Journal(broker_root/'journal.jsonl')))
        credential = host.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))
        client = FixtureClient(host.port, host.control_port, credential)
        work = AppContainerEndpoint.create(sid_text(package), role='work')
        stack.callback(work.close)
        control = AppContainerEndpoint.create(sid_text(package), role='control')
        stack.callback(control.close)
        work_server = FixturePipeServer(work, host, credential)
        control_server = FixturePipeServer(control, host, credential)
        command = 's35.' + mode
        request = client.request(command, value=101, lease=client.lease(), delay_ms=1000 if mode in ('cancel','stop') else 0)
        body = request.as_dict()
        if mode == 'stale_lease':
            body['fencing_epoch'] += 1
        first_credential = host.sessions.issue() if mode == 'wrong_token' else credential
        route = '/v1/cancel' if mode == 'cancel' else ('/v1/stop' if mode == 'stop' else '/v1/lookup')
        control_id = 's35.stop.control' if mode == 'stop' else command
        frames = [fixture_frame(first_credential, '/v1/commands', body).decode('ascii'),
                  fixture_frame(credential, route, {'project_id':host.project_id,'command_id':control_id}).decode('ascii')]
        try:
            size = C.c_size_t()
            K.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
            attrs = C.create_string_buffer(size.value)
            checked(K.InitializeProcThreadAttributeList(attrs, 2, 0, C.byref(size)))
            caps, policy = CAPS(package, None, 0, 0), W.DWORD(1)
            checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
            checked(K.UpdateProcThreadAttribute(attrs, 0, 0x2000e, C.byref(policy), C.sizeof(policy), None, None))
            si.si.cb, si.attributes = C.sizeof(SIEX), C.addressof(attrs)
            values = {key: os.environ[key] for key in ('SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','SystemDrive')}
            values.update(WINDIR=os.environ['SystemRoot'], PATH=str(Path(os.environ['SystemRoot'])/'System32'),
                          TEMP=str(scratch), TMP=str(scratch), S35_WORK=work.address, S35_CONTROL=control.address,
                          S35_LOG=str(logfile), S35_MODE=mode, S35_FRAME0=frames[0], S35_FRAME1=frames[1])
            environment = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(values.items()))+'\0\0')
            checked(K.CreateProcessW(str(executable), C.create_unicode_buffer('"'+str(executable)+'"'), None, None, False,
                                     0x8040c, environment, str(scratch), C.byref(si), C.byref(pi)))
            record['pid'] = int(pi.pid)
            work.bind_worker(pi.process)
            control.bind_worker(pi.process)
            record['primary_token_verified'] = True
            record['retained_process_binding'] = {'work':list(work._identity),'control':list(control._identity)}
            job = checked(K.CreateJobObjectW(None, None))
            limits = JEXT()
            limits.basic.flags, limits.basic.active_processes, limits.process_memory = 0x2108, 1, 128*1024*1024
            checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
            checked(K.AssignProcessToJobObject(job,pi.process))
            assigned = True
            checked(K.ResumeThread(pi.thread) != 0xffffffff)
            work.connect(timeout_ms=3000)
            control.connect(timeout_ms=3000)
            try:
                record['work_dispatch'] = work_server.serve_one().as_dict()
            except (EndpointError, PipeIOError) as exc:
                record['work_transport_error'] = exc.code
                if mode != 'drop_reply':
                    raise
            if mode in ('submit','drop_reply'):
                record['terminal_before_lookup'] = terminal(client, command).as_dict()
                assert record['terminal_before_lookup']['status'] == 'COMMITTED'
            record['control_dispatch'] = control_server.serve_one().as_dict()
            if mode in ('cancel','stop'):
                record['final_control_terminal'] = terminal(client, control_id).as_dict()
                record['final_work_terminal'] = terminal(client, command).as_dict()
            assert control.read_frame(timeout_ms=3000) == b'S35_FINAL_ACK'
            record['snapshot'] = host.fixture.snapshot()
            if mode in ('submit','drop_reply'):
                assert record['snapshot'] == {'value':101,'revision':'rev-1','effect_count':1}
                assert client.submit(request).as_dict() == record['terminal_before_lookup']
                assert record['control_dispatch']['status'] == 'COMMITTED'
                record['same_id_replay_effect_count'] = host.fixture.effect_count
            else:
                assert record['snapshot'] == {'value':0,'revision':'rev-0','effect_count':0}
            if mode == 'wrong_token':
                assert record['work_dispatch']['code'] == 'SESSION_BINDING_MISMATCH'
                assert record['control_dispatch']['code'] == 'COMMAND_NOT_FOUND'
            if mode == 'stale_lease':
                assert record['work_dispatch']['code'] == 'STALE_LEASE'
                assert record['control_dispatch']['code'] == 'COMMAND_NOT_FOUND'
            if mode in ('cancel','stop'):
                assert record['final_work_terminal']['status'] == 'CANCELED'
            if mode == 'stop':
                assert record['final_control_terminal']['status'] == 'COMMITTED' and host._stopped.is_set()
            control.write_frame(b'S35_FINAL_BYE', timeout_ms=3000)
            assert K.WaitForSingleObject(pi.process,5000)==0
            code = W.DWORD()
            checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
            record['host_exit'] = int(code.value)
            record['native'] = json.loads(logfile.read_bytes())
            assert record['host_exit'] == 57 and record['native']['complete'] == 'S35_NATIVE_COMPLETE'
            assert all(record['native'][key]==5 for key in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error'))
            for role in ('work','control'):
                key = role+'_reply_hex'
                if key in record['native']:
                    reply = json.loads(bytes.fromhex(record['native'][key]))
                    assert reply == record[role+'_dispatch']
            assert record['native']['work_reply_received'] == (mode != 'drop_reply')
        except Exception as exc:
            record['error'] = {'type':type(exc).__name__, 'message':str(exc), 'winerror':getattr(exc,'winerror',None)}
        finally:
            if pi.process and K.WaitForSingleObject(pi.process,0)!=0:
                if assigned: K.TerminateJobObject(job,123)
                else: K.TerminateProcess(pi.process,123)
                K.WaitForSingleObject(pi.process,5000)
                record['forced_owned_termination']=True
            if pi.process:
                code=W.DWORD()
                checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
                record['final_host_exit']=int(code.value)
            if assigned:
                account=JACCOUNT()
                for _ in range(101):
                    checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                    if account.active_processes==0: break
                    time.sleep(.02)
                pids=prior.PIDLIST()
                checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
                record['final_job_active'],record['final_job_pids']=int(account.active_processes),list(pids.pids)[:pids.count]
            if logfile.exists():
                raw=logfile.read_bytes()
                try:record['native']=json.loads(raw)
                except ValueError:record['partial_native_log']=raw.decode(errors='replace')
            for handle in (pi.thread,pi.process,job):
                if handle: checked(K.CloseHandle(handle))
            if attrs is not None:K.DeleteProcThreadAttributeList(attrs)
    return record


def main():
    run_uuid=uuid.uuid4().hex
    moniker='hh-gt02-s35-'+run_uuid
    profile=Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package,token=C.c_void_p(),W.HANDLE()
    created,base=False,None
    out={'run_id':RUN_ID,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(Path(__file__)),
         'native_source_sha256':sha(BASE/'boundary_child.c'),'cases':[],'safe_write':False,'acceptance':False}
    source_names=('pipe_io.py','pipe_endpoint.py','fixture_pipe.py','transport.py','journal.py','private_store.py')
    out['runtime_source_sha256']={name:sha(PRODUCT/'studio/host/core'/name) for name in source_names}
    out['imported_source_sha256']={name:sha(PREVIOUS/name) for name in ('boundary_probe.py','windows_api.py')}
    checked(A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(token)))
    owner=token_sid(token,1)
    checked(K.CloseHandle(token))
    pointer=C.c_void_p()
    checked(U.DeriveAppContainerSidFromAppContainerName(moniker,C.byref(pointer))==0)
    sid=sid_text(pointer)
    checked(A.FreeSid(pointer) is None)
    mapping='Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+sid
    out['profile_absent_before']=not profile.exists() and not prior.mapping_exists(mapping)
    try:
        assert out['profile_absent_before']
        with tempfile.TemporaryDirectory(prefix='gt02-s35-native-') as tmp:
            base=Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            prior.BASE=BASE
            image=prior.compile_native(base,out)
            common=f'D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;{owner})'
            scratch,image_dir=base/'scratch',base/'image'
            make_directory(scratch,common+f'(A;OICI;0x1301bf;;;{sid})S:(ML;OICI;NW;;;LW)')
            make_directory(image_dir,common+f'(A;OICI;GRGX;;;{sid})')
            executable=image_dir/'ipc_child.exe'
            executable.write_bytes(image.read_bytes())
            out['native_executable_sha256']=sha(executable)
            raw_dir=PRODUCT/'studio/.local/review-raw/S35'
            raw_dir.mkdir(parents=True,exist_ok=True)
            saved=raw_dir/(RUN_ID+'-'+run_uuid+'.exe')
            with saved.open('xb') as stream:stream.write(executable.read_bytes())
            out['native_executable_relative']=saved.relative_to(PRODUCT).as_posix()
            hr=U.CreateAppContainerProfile(moniker,moniker,'Owned S35 typed IPC fixture',None,0,C.byref(package))
            out['create_profile_hresult']=int(hr)
            assert hr==0
            created=True
            assert sid_text(package)==sid
            out['profile_exists_after_create']=profile.exists() and prior.mapping_exists(mapping)
            assert out['profile_exists_after_create']
            for mode in MODES:
                broker_root=base/('broker-'+mode)
                make_directory(broker_root,common)
                record=run_case(executable,scratch,broker_root,package,mode)
                out['cases'].append(record)
                if 'error' in record:raise RuntimeError('Native typed IPC case failed: '+mode)
                assert record['final_job_active']==0 and record['final_job_pids']==[]
                assert record['final_host_exit']==57 and not record.get('forced_owned_termination')
            out['remaining_endpoint_owners'],out['remaining_io_owners']=len(_ENDPOINTS),len(_OWNERS)
            assert out['remaining_endpoint_owners']==out['remaining_io_owners']==0
            out['marker']='S35_TYPED_IPC_DIAGNOSTIC_COMPLETE'
    except Exception as exc:
        out['error']={'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if package.value:A.FreeSid(package)
        if created:out['delete_profile_hresult']=int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after']=not profile.exists() and not prior.mapping_exists(mapping)
        out['owned_temp_removed']=base is not None and not base.exists()
    out['diagnostic_complete']=bool(out.get('marker') and out['profile_absent_after'] and out['owned_temp_removed'])
    raw_dir=PRODUCT/'studio/.local/review-raw/S35'
    raw_dir.mkdir(parents=True,exist_ok=True)
    raw_path=raw_dir/(RUN_ID+'-'+run_uuid+'.json')
    raw=json.dumps(out,indent=2).encode()
    with raw_path.open('xb') as stream:stream.write(raw)
    text=raw.decode()
    for old,new in ((str(base),'<OWNED_TEMP>'),(str(profile),'<OWNED_PROFILE>'),(str(PRODUCT),'<PRODUCT_ROOT>'),
                    (owner,'<BROKER_SID>'),(sid,'<APPCONTAINER_SID>'),(moniker,'<OWNED_PROFILE_NAME>')):
        text=text.replace(json.dumps(old)[1:-1],new)
    public=json.loads(re.sub(r'S-1-5-21-\d+-\d+-\d+-\d+','<HOST_ACCOUNT_SID>',text))
    public['raw_relative']=raw_path.relative_to(PRODUCT).as_posix()
    public['raw_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(public,indent=2))
    return 0 if out['diagnostic_complete'] else 1


if __name__=='__main__':
    sys.exit(main())
