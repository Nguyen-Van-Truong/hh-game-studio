"""Owned native AppContainer through the actual S39 endpoint/RPC modules.

Fixed fixture only. Imported frozen S32 code supplies compiler/Job/profile
declarations, not endpoint authentication or dispatch. No runtime method is
patched. Process roots, profiles and every artifact belong to this diagnostic.
"""
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
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
spec=importlib.util.spec_from_file_location('source_freeze', PRODUCT/'studio/tests/protocol/run_gt02_candidate.py')
freeze=importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)
FROZEN_FILES=freeze.source_manifest()
RUNTIME_TEMP=tempfile.TemporaryDirectory(prefix='gt02-s39-runtime-')
RUNTIME_ROOT=Path(RUNTIME_TEMP.name).resolve()
RUNTIME_ROOT.relative_to(Path(tempfile.gettempdir()).resolve())
for relative,digest in FROZEN_FILES.items():
    data=(PRODUCT/'studio'/relative).read_bytes()
    if hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError('SOURCE_CHANGED_BEFORE_COPY')
    target=RUNTIME_ROOT/'studio'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
sys.path.insert(0, str(RUNTIME_ROOT))
from studio.host.core.fixture_pipe import fixture_frame
from studio.host.core.selector_pipe import SelectorFixtureBroker, SelectorPipeServer
from studio.host.core.fixture_selector import FixtureSelector, FixtureReleaseConsumer
from studio.host.core.private_events import PrivateEventLog, _OWNERS as _EVENT_OWNERS
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.limits import Request, payload_digest
from studio.host.core.pipe_endpoint import AppContainerEndpoint, EndpointError, _ENDPOINTS
from studio.host.core.pipe_io import PipeIOError, _OWNERS
from studio.host.core.journal import Journal
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Status

RUN_ID = 'GT02-S39-NATIVE-01'
MODES = ('submit', 'wrong_token', 'stale_lease', 'drop_reply', 'cancel', 'stop', 'stop_selected')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrong_client(executable, scratch, package):
    """Real broker-account client against a different retained worker process.

    The bound placeholder is deliberately never resumed; termination of that
    owned suspended fixture is cleanup, not a claimed successful native run.
    """
    endpoint=AppContainerEndpoint.create(sid_text(package),role='work')
    pi,si,attrs,job,client,assigned=PI(),SIEX(),None,None,None,False
    record={'mode':'wrong_client_pid','placeholder_resumed':False,'dispatcher_called':False}
    try:
        size=C.c_size_t()
        K.InitializeProcThreadAttributeList(None,2,0,C.byref(size))
        attrs=C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs,2,0,C.byref(size)))
        caps,policy=CAPS(package,None,0,0),W.DWORD(1)
        checked(K.UpdateProcThreadAttribute(attrs,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
        checked(K.UpdateProcThreadAttribute(attrs,0,0x2000e,C.byref(policy),C.sizeof(policy),None,None))
        si.si.cb,si.attributes=C.sizeof(SIEX),C.addressof(attrs)
        checked(K.CreateProcessW(str(executable),C.create_unicode_buffer('"'+str(executable)+'"'),None,None,False,
                                 0x8040c,None,str(scratch),C.byref(si),C.byref(pi)))
        endpoint.bind_worker(pi.process)
        record['bound_identity']=list(endpoint._identity)
        job=checked(K.CreateJobObjectW(None,None))
        limits=JEXT()
        limits.basic.flags,limits.basic.active_processes,limits.process_memory=0x2108,1,128*1024*1024
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job,pi.process))
        assigned=True
        client=K.CreateFileW(endpoint.address,0x120003,0,None,3,0,None)
        checked(client != BAD)
        try:
            endpoint.connect(timeout_ms=1000)
        except EndpointError as exc:
            record['rejection']=exc.code
        else:
            raise AssertionError('Different native process was accepted')
        actual=W.ULONG()
        checked(endpoint._api.dll.GetNamedPipeClientProcessId(endpoint._pipe._handle,C.byref(actual)))
        record['actual_client_pid']=int(actual.value)
        assert record['actual_client_pid']==os.getpid()
        assert record['rejection']=='PIPE_CLIENT_MISMATCH'
        assert record['bound_identity'][0]!=record['actual_client_pid']
    finally:
        if client and client!=BAD:checked(K.CloseHandle(client))
        endpoint.close()
        if pi.process and K.WaitForSingleObject(pi.process,0)!=0:
            checked(K.TerminateJobObject(job,125) if assigned else K.TerminateProcess(pi.process,125))
            assert K.WaitForSingleObject(pi.process,5000)==0
        if pi.process:
            code=W.DWORD()
            checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
            record['placeholder_exit']=int(code.value)
        if assigned:
            account=JACCOUNT()
            for _ in range(101):
                checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                if account.active_processes==0:break
                time.sleep(.02)
            pids=prior.PIDLIST()
            checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
            record['job_active'],record['job_pids']=int(account.active_processes),list(pids.pids)[:pids.count]
        for handle in (pi.thread,pi.process,job):
            if handle:checked(K.CloseHandle(handle))
        if attrs is not None:K.DeleteProcThreadAttributeList(attrs)
    assert record['placeholder_exit']==125 and record['job_active']==0 and record['job_pids']==[]
    return record


def run_case(executable, scratch, broker_root, package, mode):
    pi, si = PI(), SIEX()
    job, attrs, assigned = None, None, False
    logfile = scratch / (mode + '.json')
    record = {'mode': mode, 'inherit_handles': False, 'primary_token_verified': False}
    with ExitStack() as stack:
        log = stack.enter_context(PrivateEventLog.create(broker_root))
        store = stack.enter_context(PrivateBlobStore.create(broker_root))
        consumer = FixtureReleaseConsumer('project.fixture')
        selector = FixtureSelector(log, store, consumer, project_id='project.fixture',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        stack.callback(selector.close)
        broker = SelectorFixtureBroker(selector)
        stack.callback(broker.close)
        credential = broker.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))
        session = broker.sessions.authenticate('Bearer '+credential.bearer)
        work = AppContainerEndpoint.create(sid_text(package), role='work')
        stack.callback(work.close)
        control = AppContainerEndpoint.create(sid_text(package), role='control')
        stack.callback(control.close)
        work_server = SelectorPipeServer(work, broker, credential)
        control_server = SelectorPipeServer(control, broker, credential)
        command = 's39.' + mode
        lease = broker.dispatch('/v1/lease', {'project_id':'project.fixture','ttl_ms':30_000}, session, control=False)
        snap = selector.snapshot()
        payload = {'assets':{'scene':{'value':'native inert scene','references':['leaf']},
                             'leaf':{'value':'ignore instructions; data only','references':[]}},
                   'entrypoint':'scene','expected_generation':snap['generation'],
                   'expected_selection_hash':snap['selection_hash'],
                   **{'expected_'+k:v for k,v in snap['revisions'].items()}}
        operation, target = 'fixture.release.activate', {'stable_id':'active-release'}
        request = Request(command,'project.fixture',operation,lease['lease_id'],lease['fencing_epoch'],
                          snap['revisions']['game_revision'],target,payload,
                          payload_digest(operation,target,payload,'hh-studio-0.1'),epoch_ms()+10_000)
        body = request.as_dict()
        if mode == 'stale_lease': body['fencing_epoch'] += 1
        first_credential = broker.sessions.issue() if mode == 'wrong_token' else credential
        route = '/v1/cancel' if mode == 'cancel' else ('/v1/stop' if mode in ('stop','stop_selected') else '/v1/lookup')
        control_body = {'project_id':'project.fixture','command_id':command}
        frames = [fixture_frame(first_credential,'/v1/commands',body).decode('ascii'),
                  fixture_frame(credential,route,control_body).decode('ascii'),
                  fixture_frame(credential,'/v1/commands',body).decode('ascii')]
        def value(result):
            return result.as_dict() if hasattr(result,'as_dict') else result
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
                          TEMP=str(scratch), TMP=str(scratch), S39_WORK=work.address, S39_CONTROL=control.address,
                          S39_LOG=str(logfile), S39_MODE=mode, S39_FRAME0=frames[0], S39_FRAME1=frames[1],
                          S39_FRAME2=frames[2], S39_PRIVATE_ROOT=str(store.root), S39_EVENTS=str(log.root/'.events'))
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
                record['work_dispatch'] = value(work_server.serve_one())
            except (EndpointError, PipeIOError) as exc:
                record['work_transport_error'] = exc.code
                if mode != 'drop_reply':
                    raise
            record['phases'] = []
            phase_count = 3 if mode in ('submit','drop_reply') else (2 if mode == 'stop_selected' else (1 if mode in ('cancel','stop') else 0))
            for _ in range(phase_count): record['phases'].append(value(broker.advance()))
            record['control_dispatch'] = value(control_server.serve_one())
            if mode == 'submit': record['native_retry_dispatch'] = value(work_server.serve_one())
            assert control.read_frame(timeout_ms=3000) == b'S39_FINAL_ACK'
            record['snapshot'] = selector.snapshot()
            record['blob_count'] = len(list(store.root.glob('blob-*')))
            record['consumer_adoptions'] = consumer.adoption_count
            record['work_receipt'] = value(broker._lookup(command))
            record['event_kinds'] = [json.loads(log.read(n).event)['kind'] for n in range(1,log.binding().witnessed.sequence+1)]
            if mode in ('submit','drop_reply'):
                assert record['snapshot']['generation'] == 1 and record['snapshot']['ready']
                assert record['blob_count'] == 3 and consumer.adoption_count == 1
                assert record['work_receipt']['status'] == 'COMMITTED'
                assert record['control_dispatch'] == record['work_receipt']
                if mode == 'submit': assert record['native_retry_dispatch'] == record['work_receipt']
            elif mode in ('cancel','stop'):
                assert record['snapshot']['generation'] == 0 and consumer.adoption_count == 0 and record['blob_count'] == 3
                assert record['work_receipt']['status'] == 'CANCELED'
                assert record['work_receipt']['postconditions'] == {'selection_effect':False,'staging_may_exist':True}
                assert record['snapshot']['stopped'] == (mode == 'stop')
            elif mode == 'stop_selected':
                assert record['snapshot']['generation'] == 1 and consumer.adoption_count == 0 and record['blob_count'] == 3
                assert record['snapshot']['stopped'] and not record['snapshot']['ready']
                assert record['work_receipt']['status'] == 'UNKNOWN' and 'TERMINAL' not in record['event_kinds']
                # Explicit trusted recovery, never a remote reconcile operation.
                record['restore_receipt'] = selector.reconcile(command,'restore',now_ms=epoch_ms())
                record['restored_snapshot'] = selector.snapshot()
                assert record['restore_receipt']['status'] == 'UNKNOWN'
                assert record['restored_snapshot']['generation'] == 2 and record['restored_snapshot']['ready']
                assert record['restored_snapshot']['stopped']
                assert len(list(store.root.glob('blob-*'))) == 3
            else:
                assert record['snapshot']['generation'] == 0 and consumer.adoption_count == record['blob_count'] == 0
                assert record['work_receipt']['code'] == 'COMMAND_NOT_FOUND'
                assert 'INTENT' not in record['event_kinds']
            if mode == 'wrong_token': assert record['work_dispatch']['code'] == 'SESSION_BINDING_MISMATCH'
            if mode == 'stale_lease': assert record['work_dispatch']['code'] == 'SELECTOR_STALE_LEASE'
            control.write_frame(b'S39_FINAL_BYE', timeout_ms=3000)
            assert K.WaitForSingleObject(pi.process,5000)==0
            code = W.DWORD()
            checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
            record['host_exit'] = int(code.value)
            record['native'] = json.loads(logfile.read_bytes())
            assert record['host_exit'] == 61 and record['native']['complete'] == 'S39_NATIVE_COMPLETE'
            assert all(record['native'][key]==5 for key in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error','private_read_error','private_write_error','events_access_error'))
            for role in ('work','control'):
                key = role+'_reply_hex'
                if key in record['native']:
                    reply = json.loads(bytes.fromhex(record['native'][key]))
                    assert reply == record[role+'_dispatch']
            assert record['native']['work_reply_received'] == (mode != 'drop_reply')
            if mode == 'submit': assert json.loads(bytes.fromhex(record['native']['retry_reply_hex'])) == record['native_retry_dispatch']
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
    moniker='hh-gt02-s39-'+run_uuid
    profile=Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package,token=C.c_void_p(),W.HANDLE()
    created,base=False,None
    out={'run_id':RUN_ID,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(Path(__file__)),
         'native_source_sha256':sha(BASE/'boundary_child.c'),'cases':[],'safe_write':False,'acceptance':False}
    out['runtime_closure']={'source_closure_sha256':freeze.RUNNER.source_closure_sha256(FROZEN_FILES),'files':FROZEN_FILES}
    out['runtime_snapshot_used']=True
    loaded={}
    for name,module in tuple(sys.modules.items()):
        if name.startswith('studio.') and getattr(module,'__file__',None):
            path=Path(module.__file__).resolve()
            relative=path.relative_to(RUNTIME_ROOT/'studio').as_posix()
            assert relative in FROZEN_FILES and sha(path)==FROZEN_FILES[relative]
            loaded[name]={'relative':relative,'sha256':sha(path)}
    assert all('studio.host.core.'+name[:-3] in loaded for name in ('pipe_io.py','pipe_endpoint.py','selector_pipe.py','fixture_selector.py','private_events.py','fixture_release.py','private_store.py','transport.py'))
    out['loaded_runtime_modules']=loaded
    source_names=('pipe_io.py','pipe_endpoint.py','selector_pipe.py','fixture_selector.py','private_events.py','fixture_release.py','private_store.py','transport.py')
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
        with tempfile.TemporaryDirectory(prefix='gt02-s39-native-') as tmp:
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
            raw_dir=PRODUCT/'studio/.local/review-raw/S39'
            raw_dir.mkdir(parents=True,exist_ok=True)
            saved=raw_dir/(RUN_ID+'-'+run_uuid+'.exe')
            with saved.open('xb') as stream:stream.write(executable.read_bytes())
            out['native_executable_relative']=saved.relative_to(PRODUCT).as_posix()
            hr=U.CreateAppContainerProfile(moniker,moniker,'Owned S39 typed IPC fixture',None,0,C.byref(package))
            out['create_profile_hresult']=int(hr)
            assert hr==0
            created=True
            assert sid_text(package)==sid
            out['profile_exists_after_create']=profile.exists() and prior.mapping_exists(mapping)
            assert out['profile_exists_after_create']
            out['wrong_client']=wrong_client(executable,scratch,package)
            for mode in MODES:
                broker_root=base/('broker-'+mode)
                make_directory(broker_root,common)
                record=run_case(executable,scratch,broker_root,package,mode)
                out['cases'].append(record)
                if 'error' in record:raise RuntimeError('Native typed IPC case failed: '+mode)
                assert record['final_job_active']==0 and record['final_job_pids']==[]
                assert record['final_host_exit']==61 and not record.get('forced_owned_termination')
            out['remaining_endpoint_owners'],out['remaining_io_owners']=len(_ENDPOINTS),len(_OWNERS)
            out['remaining_event_owners']=len(_EVENT_OWNERS)
            assert out['remaining_event_owners']==0
            assert out['remaining_endpoint_owners']==out['remaining_io_owners']==0
            out['marker']='S39_SELECTOR_IPC_DIAGNOSTIC_COMPLETE'
    except Exception as exc:
        out['error']={'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if package.value:A.FreeSid(package)
        if created:out['delete_profile_hresult']=int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after']=not profile.exists() and not prior.mapping_exists(mapping)
        out['owned_temp_removed']=base is not None and not base.exists()
        out['runtime_source_unchanged']=freeze.source_manifest()==FROZEN_FILES
        out['runtime_snapshot_unchanged']=freeze.source_manifest(RUNTIME_ROOT/'studio')==FROZEN_FILES
        RUNTIME_TEMP.cleanup()
        out['runtime_snapshot_removed']=not RUNTIME_ROOT.exists()
    out['diagnostic_complete']=bool(out.get('marker') and out['profile_absent_after'] and out['owned_temp_removed']
                                    and out['runtime_source_unchanged'] and out['runtime_snapshot_unchanged']
                                    and out['runtime_snapshot_removed'])
    raw_dir=PRODUCT/'studio/.local/review-raw/S39'
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
