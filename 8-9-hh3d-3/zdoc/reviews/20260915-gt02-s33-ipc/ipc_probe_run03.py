"""S33 fixed native worker -> authenticated pipe -> actual private staging.

Diagnostic only. Reuses frozen S32 compile/lifecycle declarations; no product
operation, generic execution, network exemption or activation is introduced.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import ctypes as C
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
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
sys.path.insert(0, str(PRODUCT / 'studio'))
from host.core.private_store import PrivateBlobStore

RUN_ID = 'GT02-S33-IPC-03'
PAYLOAD = b'S33_FIXED_STAGE_BYTES'


class OVERLAPPED(C.Structure):
    _fields_ = [('internal', C.c_size_t), ('internal_high', C.c_size_t),
                ('offset', W.DWORD), ('offset_high', W.DWORD), ('event', W.HANDLE)]


signature(K, 'CreateNamedPipeW', [W.LPCWSTR, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, W.DWORD, C.POINTER(SA)], W.HANDLE)
signature(K, 'ConnectNamedPipe', [W.HANDLE, C.POINTER(OVERLAPPED)], W.BOOL)
signature(K, 'CreateEventW', [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE)
signature(K, 'ReadFile', [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)], W.BOOL)
signature(K, 'WriteFile', [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(OVERLAPPED)], W.BOOL)
signature(K, 'GetOverlappedResult', [W.HANDLE, C.POINTER(OVERLAPPED), C.POINTER(W.DWORD), W.BOOL], W.BOOL)
signature(K, 'CancelIoEx', [W.HANDLE, C.POINTER(OVERLAPPED)], W.BOOL)
signature(K, 'GetNamedPipeClientProcessId', [W.HANDLE, C.POINTER(W.ULONG)], W.BOOL)
signature(A, 'ImpersonateNamedPipeClient', [W.HANDLE], W.BOOL)
signature(A, 'OpenThreadToken', [W.HANDLE, W.DWORD, W.BOOL, C.POINTER(W.HANDLE)], W.BOOL)
signature(A, 'RevertToSelf', [], W.BOOL)
signature(K, 'GetCurrentThread', [], W.HANDLE)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def operation(pipe, kind, payload=None, size=0):
    event = checked(K.CreateEventW(None, True, False, None))
    overlapped = OVERLAPPED(event=event)
    count = W.DWORD()
    buffer = C.create_string_buffer(payload) if kind == 'write' else C.create_string_buffer(max(size, 1))
    try:
        if kind == 'connect':
            ok = K.ConnectNamedPipe(pipe, C.byref(overlapped))
        else:
            function = K.WriteFile if kind == 'write' else K.ReadFile
            ok = function(pipe, buffer, len(payload) if kind == 'write' else size, C.byref(count), C.byref(overlapped))
        error = 0 if ok else C.get_last_error()
        if kind == 'connect' and error == 535:
            return b''
        if not ok and error != 997:
            raise C.WinError(error)
        if not ok:
            if K.WaitForSingleObject(event, 3000) != 0:
                K.CancelIoEx(pipe, C.byref(overlapped))
                # Keep OVERLAPPED/buffer alive until cancellation completes.
                checked(K.WaitForSingleObject(event, 3000) == 0)
                raise TimeoutError('Owned pipe operation timed out')
            checked(K.GetOverlappedResult(pipe, C.byref(overlapped), C.byref(count), False))
        if kind == 'write':
            assert count.value == len(payload), 'Short pipe write'
            return b''
        return buffer.raw[:count.value]
    finally:
        checked(K.CloseHandle(event))


def read_exact(pipe, length):
    assert 0 < length <= 192
    parts = bytearray()
    deadline = time.monotonic() + 3
    while len(parts) < length:
        if time.monotonic() > deadline:
            raise TimeoutError('Owned pipe frame timed out')
        part = operation(pipe, 'read', size=length-len(parts))
        assert part, 'Pipe closed mid-frame'
        parts.extend(part)
    return bytes(parts)


def run_case(executable, scratch, store, owner, package, mode):
    package_string = sid_text(package)
    endpoint = '\\\\.\\pipe\\' + package_string + '\\hh-gt02-s33-' + uuid.uuid4().hex
    descriptor = C.c_void_p()
    # Individual data rights omit FILE_CREATE_PIPE_INSTANCE. Local-only pipe,
    # one first instance, Low label, no inherited handle to either endpoint.
    sddl = f'D:P(A;;FA;;;{owner})(A;;0x120003;;;{package_string})S:(ML;;NW;;;LW)'
    checked(A.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
    pipe = K.CreateNamedPipeW(endpoint, 3 | 0x40000000 | 0x80000, 8, 1, 4096, 4096, 3000, C.byref(SA(C.sizeof(SA), descriptor, False)))
    K.LocalFree(descriptor)
    if pipe == BAD:
        raise C.WinError(C.get_last_error())
    record = {'mode': mode, 'pipe_remote_rejected': True, 'pipe_first_instance': True, 'handle_inheritance': False,
              'pipe_namespace':'AppContainer SID'}
    pi, si, token = PI(), SIEX(), W.HANDLE()
    job, attrs, assigned = None, None, False
    logfile = scratch / (mode + '.json')
    try:
        size = C.c_size_t()
        K.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        attrs = C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs, 2, 0, C.byref(size)))
        caps, policy = CAPS(package, None, 0, 0), W.DWORD(1)
        checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
        checked(K.UpdateProcThreadAttribute(attrs, 0, 0x2000e, C.byref(policy), C.sizeof(policy), None, None))
        si.si.cb, si.attributes = C.sizeof(SIEX), C.addressof(attrs)
        logfile = scratch / (mode + '.json')
        values = {key: os.environ[key] for key in ('SystemRoot', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'SystemDrive')}
        values.update(WINDIR=os.environ['SystemRoot'], PATH=str(Path(os.environ['SystemRoot'])/'System32'),
                      TEMP=str(scratch), TMP=str(scratch), S33_PIPE=endpoint, S33_LOG=str(logfile), S33_ROOT=str(store.root))
        environment = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(values.items()))+'\0\0')
        checked(K.CreateProcessW(str(executable), C.create_unicode_buffer('"'+str(executable)+'"'), None, None, False,
                                 0x8040c, environment, str(scratch), C.byref(si), C.byref(pi)))
        record['pid'] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process, 8, C.byref(token)))
        record['primary_token'] = {'appcontainer': token_number(token,29), 'sid_matches': token_sid(token,31)==package_string,
                                   'integrity':token_sid(token,25), 'capabilities':token_number(token,30)}
        assert record['primary_token'] == {'appcontainer':1,'sid_matches':True,'integrity':'S-1-16-4096','capabilities':0}
        job = checked(K.CreateJobObjectW(None, None))
        limits = JEXT()
        limits.basic.flags, limits.basic.active_processes, limits.process_memory = 0x2108, 1, 128*1024*1024
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job,pi.process))
        assigned = True
        checked(K.ResumeThread(pi.thread) != 0xffffffff)
        operation(pipe,'connect')
        pid = W.ULONG()
        checked(K.GetNamedPipeClientProcessId(pipe,C.byref(pid)))
        record['actual_pipe_pid'] = int(pid.value)
        expected_pid = int(pi.pid) if mode == 'stage' else int(pi.pid)+1
        bound = pid.value == expected_pid and K.WaitForSingleObject(pi.process,0) == 258
        length = struct.unpack('<I',read_exact(pipe,4))[0]
        assert 0 < length <= 128
        data = read_exact(pipe,length)
        impersonated = False
        impersonation_token = W.HANDLE()
        try:
            checked(A.ImpersonateNamedPipeClient(pipe))
            impersonated = True
            checked(A.OpenThreadToken(K.GetCurrentThread(),8,True,C.byref(impersonation_token)))
            record['pipe_token'] = {'appcontainer': token_number(impersonation_token,29),
                                    'sid_matches':token_sid(impersonation_token,31)==package_string}
            bound = bound and record['pipe_token'] == {'appcontainer':1,'sid_matches':True}
        finally:
            if impersonation_token: checked(K.CloseHandle(impersonation_token))
            if impersonated: checked(A.RevertToSelf())
        record['identity_binding_accepted'] = bound
        before = len(list(store.root.glob('blob-*')))
        if bound and data == PAYLOAD:
            blob = store.put_bytes(data)
            assert store.read_blob(blob) == PAYLOAD
            record['staged_blob'] = {'object_id':blob.object_id, 'file_id':blob.identity.file_id, 'sha256':blob.sha256}
            response = ('STAGED '+blob.object_id+' '+blob.sha256).encode()
        else:
            response = b'REJECTED_IDENTITY'
        operation(pipe,'write',struct.pack('<I',len(response))+response)
        assert read_exact(pipe,1) == b'!'
        record['new_blob_count'] = len(list(store.root.glob('blob-*')))-before
        assert K.WaitForSingleObject(pi.process,5000)==0
        code = W.DWORD()
        checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
        record['host_exit'] = int(code.value)
        account = JACCOUNT()
        for _ in range(101):
            checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
            if account.active_processes==0: break
            time.sleep(0.02)
        pids = prior.PIDLIST()
        checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
        record['job_active'],record['job_pids'] = int(account.active_processes),list(pids.pids)[:pids.count]
        record['native'] = json.loads(logfile.read_bytes())
        assert record['host_exit']==53 and record['job_active']==0 and record['job_pids']==[]
        assert record['native']['complete']=='S33_NATIVE_COMPLETE'
        assert record['new_blob_count']==int(mode=='stage')
        if mode=='stage':
            assert record['native']['direct_read_error']==record['native']['direct_write_error']==5
            assert store.read_blob(blob)==PAYLOAD
    except Exception as exc:
        record['error'] = {'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
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
                if account.active_processes==0:break
                time.sleep(0.02)
            pids=prior.PIDLIST()
            checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
            record['final_job_active'],record['final_job_pids']=int(account.active_processes),list(pids.pids)[:pids.count]
        if logfile.exists():
            raw_log=logfile.read_bytes()
            try:record['native']=json.loads(raw_log)
            except ValueError:record['partial_native_log']=raw_log.decode(errors='replace')
        for handle in (token,pi.thread,pi.process,job,pipe):
            if handle: K.CloseHandle(handle)
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)
    return record


def main():
    run_uuid = uuid.uuid4().hex
    moniker = 'hh-gt02-s33-'+run_uuid
    out = {'run_id':RUN_ID,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
           'source_sha256':digest(Path(__file__)), 'native_source_sha256':digest(BASE/'boundary_child.c'),
           'private_store_sha256':digest(PRODUCT/'studio/host/core/private_store.py'),
           'safe_write':'UNSUPPORTED_SAFE_OPEN_WINDOWS','production_protocol':False,'cases':[]}
    profile = Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package,token = C.c_void_p(),W.HANDLE()
    created,base = False,None
    checked(A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(token)))
    owner = token_sid(token,1)
    checked(K.CloseHandle(token))
    sid_pointer = C.c_void_p()
    checked(U.DeriveAppContainerSidFromAppContainerName(moniker,C.byref(sid_pointer))==0)
    sid = sid_text(sid_pointer)
    checked(A.FreeSid(sid_pointer) is None)
    mapping = 'Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+sid
    out['profile_absent_before'] = not profile.exists() and not prior.mapping_exists(mapping)
    try:
        assert out['profile_absent_before']
        with tempfile.TemporaryDirectory(prefix='gt02-s33-ipc-') as tmp:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            prior.BASE = BASE
            image = prior.compile_native(base,out)
            common = f'D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;{owner})'
            scratch,image_dir = base/'scratch',base/'image'
            make_directory(scratch,common+f'(A;OICI;0x1301bf;;;{sid})S:(ML;OICI;NW;;;LW)')
            make_directory(image_dir,common+f'(A;OICI;GRGX;;;{sid})')
            executable = image_dir/'ipc_child.exe'
            executable.write_bytes(image.read_bytes())
            out['native_executable_sha256']=digest(executable)
            hr = U.CreateAppContainerProfile(moniker,moniker,'Owned S33 fixed IPC diagnostic',None,0,C.byref(package))
            out['create_profile_hresult']=int(hr)
            assert hr==0
            created=True
            with PrivateBlobStore.create(base) as store:
                for mode in ('stage','wrong_pid'):
                    result=run_case(executable,scratch,store,owner,package,mode)
                    out['cases'].append(result)
                    if 'error' in result: raise RuntimeError('IPC case failed: '+mode)
            out['marker']='S33_IPC_STAGING_DIAGNOSTIC_COMPLETE'
    except Exception as exc:
        out['error']={'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if package.value: A.FreeSid(package)
        if created: out['delete_profile_hresult']=int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after']=not profile.exists() and not prior.mapping_exists(mapping)
        out['owned_temp_removed']=base is not None and not base.exists()
    out['diagnostic_complete']=bool(out.get('marker') and out['profile_absent_after'] and out['owned_temp_removed'])
    raw_dir=PRODUCT/'studio/.local/review-raw/S33'
    raw_dir.mkdir(parents=True,exist_ok=True)
    raw_path=raw_dir/(RUN_ID+'-'+run_uuid+'.json')
    raw=json.dumps(out,indent=2).encode()
    with raw_path.open('xb') as stream:stream.write(raw)
    text=raw.decode()
    for old,new in ((str(base),'<OWNED_TEMP>'),(str(profile),'<OWNED_PROFILE>'),(str(PRODUCT),'<PRODUCT_ROOT>'),
                    (owner,'<BROKER_SID>'),(sid,'<APPCONTAINER_SID>'),(moniker,'<OWNED_PROFILE_NAME>')):
        text=text.replace(json.dumps(old)[1:-1],new)
    public=json.loads(text)
    public['raw_relative']=raw_path.relative_to(PRODUCT).as_posix()
    public['raw_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(public,indent=2))
    return 0 if out['diagnostic_complete'] else 1


if __name__=='__main__':
    sys.exit(main())
