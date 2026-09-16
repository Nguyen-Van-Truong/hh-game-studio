"""Fixed native AppContainer registry denial plus a same-prefix positive control."""
from datetime import datetime, timezone
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
BUILD_HELPER = BASE.parent / '20260916-gt02-s44-boundary' / 'run-06'
sys.path.insert(0, str(HELPER))
import boundary_probe as prior
from windows_api import *
spec = importlib.util.spec_from_file_location('s44_build', BUILD_HELPER/'compile_native.py')
compiler = importlib.util.module_from_spec(spec); spec.loader.exec_module(compiler)


def launch(executable, scratch, custody, control_path, package, out):
    pi, si, attrs, job, assigned = PI(), SIEX(), None, None, False
    token = W.HANDLE()
    try:
        size = C.c_size_t(); K.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
        attrs = C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs, 2, 0, C.byref(size)))
        caps, policy = CAPS(package, None, 0, 0), W.DWORD(1)
        checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
        checked(K.UpdateProcThreadAttribute(attrs, 0, 0x2000e, C.byref(policy), C.sizeof(policy), None, None))
        si.si.cb, si.attributes = C.sizeof(SIEX), C.addressof(attrs)
        environment = {key:os.environ[key] for key in ('SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','SystemDrive')}
        environment.update(WINDIR=os.environ['SystemRoot'],PATH=str(Path(os.environ['SystemRoot'])/'System32'),
            TEMP=str(scratch),TMP=str(scratch),S45_SCRATCH=str(scratch),
            S45_TARGET=custody._path[len('\\REGISTRY\\USER\\'):],S45_CONTROL=control_path)
        block = C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(environment.items(),key=lambda row:row[0].lower()))+'\0\0')
        checked(K.CreateProcessW(str(executable),C.create_unicode_buffer('"'+str(executable)+'"'),None,None,False,
                                0x8040c,block,str(scratch),C.byref(si),C.byref(pi)))
        out['pid'] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process,8,C.byref(token)))
        out['token_is_appcontainer'] = token_number(token,29)
        out['token_package_matches'] = token_sid(token,31) == sid_text(package)
        out['integrity_sid'],out['capabilities'] = token_sid(token,25),token_number(token,30)
        assert out['token_is_appcontainer']==1 and out['token_package_matches']
        assert out['integrity_sid']=='S-1-16-4096' and out['capabilities']==0
        job = checked(K.CreateJobObjectW(None,None))
        limits=JEXT(); limits.basic.flags,limits.basic.active_processes,limits.process_memory=0x2108,1,128*1024*1024
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job,pi.process)); assigned=True
        assert K.ResumeThread(pi.thread)!=0xffffffff
        deadline=time.monotonic()+8
        while not (scratch/'ready').exists():
            assert time.monotonic()<deadline and K.WaitForSingleObject(pi.process,0)!=0,'native readiness failed'
            time.sleep(.005)
        assert (scratch/'ready').read_bytes()==b'READY'
        current=custody.read()
        out['custody_updates']=[]
        for number in range(12):
            after=('protected-state-'+str(number)).encode()
            custody.store(after,expected=current)
            assert custody.read()==after
            out['custody_updates'].append(hashlib.sha256(after).hexdigest())
            current=after
            time.sleep(.002)
        (scratch/'stop').write_bytes(b'STOP')
        assert K.WaitForSingleObject(pi.process,5000)==0,'native exit timeout'
        exit_code=W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(exit_code)))
        out['host_exit']=int(exit_code.value)
        out['native']=json.loads((scratch/'result.json').read_bytes())
        assert out['host_exit']==89 and out['native']['complete']=='S45_REGISTRY_BOUNDARY_COMPLETE'
        assert out['native']['attempts']==9*out['native']['loops'] and out['native']['loops']>=2
        assert out['native']['denied']==out['native']['attempts'] and out['native']['allowed']==out['native']['unexpected']==0
        assert custody.read()==current
        out['protected_state_verified']=True
    finally:
        if pi.process and K.WaitForSingleObject(pi.process,0)!=0:
            if assigned: K.TerminateJobObject(job,123)
            else: K.TerminateProcess(pi.process,123)
            K.WaitForSingleObject(pi.process,5000); out['forced_owned_termination']=True
        if pi.process:
            exit_code=W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(exit_code)))
            out['final_host_exit']=int(exit_code.value)
        if assigned:
            account=JACCOUNT()
            for _ in range(101):
                checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                if not account.active_processes: break
                time.sleep(.02)
            pids=prior.PIDLIST()
            checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
            out['final_job_active'],out['final_job_pids']=int(account.active_processes),list(pids.pids)[:pids.count]
        if (scratch/'result.json').exists(): out['native']=json.loads((scratch/'result.json').read_bytes())
        for handle in (token,pi.thread,pi.process,job):
            if handle: checked(K.CloseHandle(handle))
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)


def main():
    spec=importlib.util.spec_from_file_location('freeze',PRODUCT/'studio/tests/protocol/run_gt02_candidate.py')
    freeze=importlib.util.module_from_spec(spec); spec.loader.exec_module(freeze)
    files=freeze.source_manifest()
    runtime=tempfile.TemporaryDirectory(prefix='gt02-s45-registry-snapshot-')
    runtime_root=Path(runtime.name).resolve()
    for name,digest in files.items():
        data=(PRODUCT/'studio'/name).read_bytes(); assert hashlib.sha256(data).hexdigest()==digest
        destination=runtime_root/'studio'/name; destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(data)
    sys.path.insert(0,str(runtime_root))
    from studio.host.core.custody_registry import RegistryCustody,_RegistryApi,BASE_PATH,_HKCU,_ACCESS
    from studio.host.core.private_store import PrivateBlobStore
    moniker='hh-gt02-s45-registry-'+uuid.uuid4().hex
    profile=Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package,token=C.c_void_p(),W.HANDLE()
    created=False; base=mapping=api=custody=None
    owned_ids=[]
    out={'run_id':sys.argv[1],'timestamp_utc':datetime.now(timezone.utc).isoformat(),
         'runtime_closure':{'source_closure_sha256':freeze.RUNNER.source_closure_sha256(files),'files':files},
         'safe_write':False,'acceptance':False,'snapshot_used':True}
    out['diagnostic_sources']={str(p.relative_to(BASE.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        Path(__file__),BASE/'boundary_child.c',BUILD_HELPER/'compile_native.py',HELPER/'boundary_probe.py',HELPER/'windows_api.py')}
    try:
        checked(A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(token)))
        user=token_sid(token,1)
        assert U.DeriveAppContainerSidFromAppContainerName(moniker,C.byref(package))==0
        package_string=sid_text(package)
        mapping='Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+package_string
        assert not profile.exists() and not prior.mapping_exists(mapping)
        created_sid=C.c_void_p()
        assert U.CreateAppContainerProfile(moniker,moniker,'Owned S45 registry probe',None,0,C.byref(created_sid))==0
        created=True; A.FreeSid(created_sid)
        out['base_created_components']=RegistryCustody.provision_base()
        api=_RegistryApi(); anchor,_,_=api.base()
        control_id=uuid.uuid4().hex
        original=api.sddl
        api.sddl=original+'(A;;KRKW;;;'+package_string+')S:(ML;;NW;;;LW)'
        try:
            control=api.create(anchor,control_id)
            owned_ids.append(control_id)
        finally: api.sddl=original
        control_path=user+'\\'+BASE_PATH+'\\'+control_id
        api.set(control,'State',b'CONTROL'); api.flush(control)
        api.validate_key(control,'\\REGISTRY\\USER\\'+control_path,protected=False)
        identifier=uuid.uuid4().hex
        custody=RegistryCustody.create(identifier); owned_ids.append(identifier)
        with tempfile.TemporaryDirectory(prefix='gt02-s45-registry-native-') as tmp:
            base=Path(tmp).resolve(); base.relative_to(Path(tempfile.gettempdir()).resolve())
            executable=compiler.compile_native(base,BASE/'boundary_child.c',out)
            common='D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;'+user+')'
            scratch,images=base/'scratch',base/'images'
            make_directory(scratch,common+'(A;OICI;0x1301bf;;;'+package_string+')S:(ML;OICI;NW;;;LW)')
            make_directory(images,common+'(A;OICI;GRGX;;;'+package_string+')')
            image=images/'boundary_child.exe'; image.write_bytes(executable.read_bytes())
            out['executable_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
            # This trusted caller owns a native exclusive file writer guard.
            # The registry primitive itself does not claim interprocess CAS.
            with PrivateBlobStore.create(base) as writer_guard:
                out['file_writer_guard_held']=writer_guard._guard_handle is not None
                custody.store(b'initial-protected-state',expected=None)
                launch(image,scratch,custody,control_path,package,out)
            assert api.query(control,'State')==(3,b'CHILD_OK')
            out['positive_control_read_write_verified']=True
            assert out['final_job_active']==0 and out['final_job_pids']==[]
            assert out['final_host_exit']==89 and not out.get('forced_owned_termination')
            out['marker']='S45_REGISTRY_BOUNDARY_VERIFIED'
    except Exception as exc:
        out['error']={'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if custody is not None: custody.close()
        if api is not None:
            api.close_owned()
        # Delete only recorded newly-created test leaves, verified by no-follow
        # actual native path. Never delete shared product/configuration keys.
        cleanup=_RegistryApi()
        try:
            cleanup.nt.NtDeleteKey.argtypes,cleanup.nt.NtDeleteKey.restype=[W.HANDLE],W.LONG
            for identifier in reversed(owned_ids):
                handle=W.HANDLE()
                assert cleanup.adv.RegOpenKeyExW(_HKCU,BASE_PATH+'\\'+identifier,8,_ACCESS|0x10000,C.byref(handle))==0
                cleanup.keys.add(handle.value)
                assert cleanup.native_name(handle.value)=='\\REGISTRY\\USER\\'+cleanup.owner+'\\'+BASE_PATH+'\\'+identifier
                assert cleanup.nt.NtDeleteKey(handle)==0
                cleanup.close_key(handle.value)
                assert cleanup.adv.RegOpenKeyExW(_HKCU,BASE_PATH+'\\'+identifier,8,_ACCESS,C.byref(handle))==2
            out['owned_registry_leaves_removed']=len(owned_ids)
        finally: cleanup.close_owned()
        if token: K.CloseHandle(token)
        if package.value: A.FreeSid(package)
        if created: out['delete_profile_hresult']=int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after']=not profile.exists() and (mapping is None or not prior.mapping_exists(mapping))
        out['owned_temp_removed']=base is not None and not base.exists()
        out['source_unchanged']=freeze.source_manifest()==files
        out['snapshot_unchanged']=freeze.source_manifest(runtime_root/'studio')==files
        runtime.cleanup(); out['snapshot_removed']=not runtime_root.exists()
    out['complete']=bool(out.get('marker') and out.get('owned_registry_leaves_removed')==2 and all(out[key] for key in (
        'profile_absent_after','owned_temp_removed','source_unchanged','snapshot_unchanged','snapshot_removed')))
    print(json.dumps(out,indent=2),flush=True)
    return 0 if out['complete'] else 1


if __name__=='__main__':
    sys.exit(main())
