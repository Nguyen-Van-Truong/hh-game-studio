"""Fixed trusted editor only. No hostile input or claimed disk/network isolation."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
HELPER = BASE.parent/'20260915-gt02-s32-boundary'
sys.path.insert(0,str(HELPER))
import boundary_probe as prior
from windows_api import *


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    output = Path(sys.argv[1]).resolve(); output.relative_to(BASE)
    lock = json.loads((PRODUCT/'studio/toolchain.lock.json').read_bytes())
    local = json.loads((PRODUCT/'studio/.local/toolchain.local.json').read_bytes())
    engine = Path(local['godot_console']).with_name(lock['godot']['gui_executable'])
    assert sha(engine) == lock['godot']['gui_sha256']
    run_uuid = uuid.uuid4().hex
    moniker = 'hh-gt03-s47-'+run_uuid
    profile = Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    base = Path(tempfile.mkdtemp(prefix='gt03-s47-sandbox-')).resolve()
    assert base.parent == Path(tempfile.gettempdir()).resolve() and base.name.startswith('gt03-s47-sandbox-')
    package,owner_token,child_token = C.c_void_p(),W.HANDLE(),W.HANDLE()
    pi,si = PI(),SIEX()
    attrs = job = None; handles = []; created = assigned = False; mapping = None
    out = {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'run_id':'GT03-S47-'+output.name,
        'engine_sha256':sha(engine),'engine_pin':lock['godot']['version'],'engine_source_commit':lock['godot']['source_commit'],
        'direct_gui_executable':True,'trusted_addon_only':True,'hostile_script_safety':False,
        'hard_directory_disk_quota':False,'network_denial_tested':False,'child_execution_denial_tested':False,
        'outer_timeout_seconds':60,'inner_timeout_seconds':30,'memory_limit_bytes':1024*1024*1024,
        'diagnostic_sources':{name:sha(BASE/name) for name in ('startup_probe.py','capture.py','project.godot','main.tscn','plugin.cfg','probe.gd')}}
    try:
        checked(A.OpenProcessToken(K.GetCurrentProcess(),8,C.byref(owner_token)))
        owner = token_sid(owner_token,1)
        checked(U.DeriveAppContainerSidFromAppContainerName(moniker,C.byref(package)) == 0)
        sid = sid_text(package)
        mapping = 'Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+sid
        assert not profile.exists() and not prior.mapping_exists(mapping)
        created_sid = C.c_void_p()
        assert U.CreateAppContainerProfile(moniker,moniker,'Owned trusted S47 startup probe',None,0,C.byref(created_sid)) == 0
        created = True; A.FreeSid(created_sid)
        private_acl = 'D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;'+owner+')'
        read_acl = private_acl+'(A;OICI;GRGX;;;'+sid+')'
        write_acl = private_acl+'(A;OICI;0x1301bf;;;'+sid+')S:(ML;OICI;NW;;;LW)'
        images,project,scratch,private = (base/name for name in ('images','project','scratch','private'))
        for path,acl in ((images,read_acl),(project,read_acl),(scratch,write_acl),(private,private_acl)):
            make_directory(path,acl)
        image = images/engine.name; image.write_bytes(engine.read_bytes()); assert sha(image) == out['engine_sha256']
        make_directory(project/'addons',read_acl); make_directory(project/'addons/s47_probe',read_acl)
        make_directory(project/'.godot',write_acl)
        for name,target in (('project.godot',project/'project.godot'),('main.tscn',project/'main.tscn'),
                            ('plugin.cfg',project/'addons/s47_probe/plugin.cfg'),('probe.gd',project/'addons/s47_probe/probe.gd')):
            target.write_bytes((BASE/name).read_bytes())
        (project/'addons/s47_probe/probe.gd.uid').write_text('uid://cfr7w1br17usr\n',encoding='utf-8')
        sources = {path.relative_to(project).as_posix():sha(path) for path in project.rglob('*') if path.is_file()}
        out['copied_project_sources'] = sources
        sentinel = private/'sentinel.bin'; sentinel.write_bytes(b'S47_PRIVATE_SENTINEL_UNCHANGED')
        out['private_before_sha256'] = sha(sentinel)
        out['directory_security'] = {key:security_readback(path,True) for key,path in
            (('project_readonly',project),('cache_writable',project/'.godot'),('scratch_writable',scratch),('private',private))}
        for name in ('roaming','local','profile','temp'):
            make_directory(scratch/name,write_acl)
        environment = {'SystemRoot':os.environ['SystemRoot'],'WINDIR':os.environ['SystemRoot'],
            'SystemDrive':os.environ['SystemDrive'],'PATH':str(Path(os.environ['SystemRoot'])/'System32'),
            'APPDATA':str(scratch/'roaming'),'LOCALAPPDATA':str(scratch/'local'),'USERPROFILE':str(scratch/'profile'),
            'TEMP':str(scratch/'temp'),'TMP':str(scratch/'temp'),'S47_PRIVATE_ROOT':str(private),
            'S47_PRIVATE_FILE':str(sentinel),'S47_CONTROL_FILE':str(scratch/'control.txt'),'S47_OUTPUT':str(scratch/'result.json')}
        out['environment_keys'] = sorted(environment)
        sa = SA(C.sizeof(SA),None,True)
        for path,access,disposition in ((str(scratch/'stdout.txt'),0x40000000,1),
                                      (str(scratch/'stderr.txt'),0x40000000,1),('NUL',0x80000000,3)):
            handle = K.CreateFileW(path,access,7,C.byref(sa),disposition,0,None)
            checked(handle != BAD); handles.append(handle)
        size = C.c_size_t(); K.InitializeProcThreadAttributeList(None,3,0,C.byref(size))
        attrs = C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs,3,0,C.byref(size)))
        caps,policy = CAPS(package,None,0,0),W.DWORD(1)
        allowed = (W.HANDLE*3)(*handles)
        checked(K.UpdateProcThreadAttribute(attrs,0,0x20009,C.byref(caps),C.sizeof(caps),None,None))
        checked(K.UpdateProcThreadAttribute(attrs,0,0x2000e,C.byref(policy),C.sizeof(policy),None,None))
        checked(K.UpdateProcThreadAttribute(attrs,0,0x20002,allowed,C.sizeof(allowed),None,None))
        si.si.cb,si.attributes,si.si.flags = C.sizeof(SIEX),C.addressof(attrs),0x100
        si.si.stdout,si.si.stderr,si.si.stdin = handles
        envblock = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items()))+'\0\0')
        argv = [str(image),'--headless','--editor','--path',str(project),'res://main.tscn','--','--s47-probe']
        checked(K.CreateProcessW(str(image),C.create_unicode_buffer(subprocess.list2cmdline(argv)),None,None,True,
            0x08080404,envblock,str(project),C.byref(si),C.byref(pi)))
        out['pid'] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process,8,C.byref(child_token)))
        out['primary_token'] = {'type':token_number(child_token,8),'appcontainer':token_number(child_token,29),
            'capabilities':token_number(child_token,30),'package':token_sid(child_token,31),
            'user':token_sid(child_token,1),'integrity':token_sid(child_token,25)}
        assert out['primary_token'] == {'type':1,'appcontainer':1,'capabilities':0,'package':sid,
                                       'user':owner,'integrity':'S-1-16-4096'}
        signature(K,'GetProcessTimes',[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)],W.BOOL)
        birth,exited,kernel,user = W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
        checked(K.GetProcessTimes(pi.process,C.byref(birth),C.byref(exited),C.byref(kernel),C.byref(user)))
        out['process_identity'] = [int(pi.pid),(birth.dwHighDateTime<<32)|birth.dwLowDateTime]
        job = checked(K.CreateJobObjectW(None,None)); limits = JEXT()
        limits.basic.flags,limits.basic.active_processes = 0x230a,1
        limits.basic.process_time = 20*10_000_000
        limits.process_memory = limits.job_memory = out['memory_limit_bytes']
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        observed = JEXT(); checked(K.QueryInformationJobObject(job,9,C.byref(observed),C.sizeof(observed),None))
        assert observed.basic.flags == limits.basic.flags and observed.process_memory == limits.process_memory
        out['job_limit_readback'] = {'flags':observed.basic.flags,'active_processes':observed.basic.active_processes,
            'process_memory':observed.process_memory,'job_memory':observed.job_memory,'process_cpu_100ns':observed.basic.process_time}
        out['child_process_creation_disabled'] = True
        checked(K.AssignProcessToJobObject(job,pi.process)); assigned = True
        assert time.monotonic()-started < 20, 'setup exceeded inner budget'
        checked(K.ResumeThread(pi.thread) != 0xffffffff)
        deadline = min(started+50,time.monotonic()+30)
        while K.WaitForSingleObject(pi.process,100) != 0:
            assert time.monotonic() < deadline, 'Godot startup timeout'
            # Observation/early stop is not a hard filesystem quota.
            assert sum(path.stat().st_size for path in scratch.rglob('*') if path.is_file()) < 16*1024*1024, 'scratch soft cap'
        code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
        out['actual_godot_exit'] = int(code.value)
        if (scratch/'result.json').exists(): out['godot'] = json.loads((scratch/'result.json').read_bytes())
        out['private_after_sha256'] = sha(sentinel)
        out['private_unchanged'] = out['private_before_sha256'] == out['private_after_sha256']
        out['readonly_sources_unchanged'] = all((project/name).is_file() and sha(project/name) == digest for name,digest in sources.items())
        out['readonly_project_no_new_file'] = not (project/'forbidden-created.txt').exists()
        out['scratch_positive_control'] = (scratch/'control.txt').read_text() == 'S47_GRANTED_SCRATCH_OK' if (scratch/'control.txt').exists() else False
        assert out['actual_godot_exit'] == 87 and out.get('godot',{}).get('ok') is True
        assert out['godot']['pid'] == out['pid'] and out['godot']['version']['hash'] == lock['godot']['source_commit']
        assert out['private_unchanged'] and out['readonly_sources_unchanged'] and out['readonly_project_no_new_file'] and out['scratch_positive_control']
        out['marker'] = 'S47_ACTUAL_GODOT_TRUSTED_STARTUP_AND_PRIVATE_DENIAL'
    except Exception as exc:
        out['error'] = {'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if pi.process and K.WaitForSingleObject(pi.process,0) != 0:
            checked(K.TerminateJobObject(job,125) if assigned else K.TerminateProcess(pi.process,125))
            assert K.WaitForSingleObject(pi.process,5000) == 0
            out['forced_owned_termination'] = True
        if pi.process:
            code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(code))); out['final_actual_exit'] = int(code.value)
        if assigned:
            account = JACCOUNT()
            for _ in range(101):
                checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
                if account.active_processes == 0: break
                time.sleep(.01)
            pids = prior.PIDLIST(); checked(K.QueryInformationJobObject(job,3,C.byref(pids),C.sizeof(pids),None))
            out['final_job_active'],out['final_job_pids'] = int(account.active_processes),list(pids.pids)[:pids.count]
            peaks = JEXT(); checked(K.QueryInformationJobObject(job,9,C.byref(peaks),C.sizeof(peaks),None))
            out['peak_process_memory'],out['peak_job_memory'] = peaks.peak_process,peaks.peak_job
        for handle in (*handles,child_token,owner_token,pi.thread,pi.process,job):
            if handle: checked(K.CloseHandle(handle))
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)
        for name in ('stdout.txt','stderr.txt','result.json','control.txt'):
            path = base/'scratch'/name
            if path.exists():
                raw = path.read_bytes(); assert len(raw) <= 16*1024*1024
                (output/('engine-'+name)).write_bytes(raw)
        out['runtime_files'] = {path.relative_to(base).as_posix():path.stat().st_size for path in base.rglob('*') if path.is_file()}
        if package.value: A.FreeSid(package)
        if created: out['delete_profile_hresult'] = int(U.DeleteAppContainerProfile(moniker))
        out['profile_removed'] = not profile.exists() and (mapping is None or not prior.mapping_exists(mapping))
        if out.get('marker') and not out.get('forced_owned_termination'):
            assert base.parent == Path(tempfile.gettempdir()).resolve() and base.name.startswith('gt03-s47-sandbox-')
            shutil.rmtree(base)
            out['owned_temp_removed'] = not base.exists()
        else:
            out['failure_state_preserved_at'] = str(base)
        out['elapsed_seconds'] = round(time.monotonic()-started,3)
    out['complete'] = bool(out.get('marker') and out.get('final_job_active') == 0 and out.get('final_job_pids') == []
        and out['profile_removed'] and out.get('owned_temp_removed') and not out.get('forced_owned_termination'))
    (output/'result.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2),flush=True)
    return 0 if out['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
