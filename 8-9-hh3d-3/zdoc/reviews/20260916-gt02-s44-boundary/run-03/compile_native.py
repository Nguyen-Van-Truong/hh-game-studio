"""Fixed MSVC /c and link lanes: bounded Job, no child process creation."""
import hashlib
import os
from pathlib import Path
import subprocess
import time
from windows_api import *


def run_tool(argv, cwd, environment, label):
    pi, si, attrs, job, assigned = PI(), SIEX(), None, None, False
    handles = []
    out = {'timeout_ms':25000,'child_process_creation_disabled':True}
    try:
        sa = SA(C.sizeof(SA),None,True)
        for path, access, disposition in ((str(cwd/(label+'.out')),0x40000000,1),(str(cwd/(label+'.err')),0x40000000,1),('NUL',0x80000000,3)):
            handle = K.CreateFileW(path,access,7,C.byref(sa),disposition,0,None)
            checked(handle != BAD); handles.append(handle)
        size = C.c_size_t(); K.InitializeProcThreadAttributeList(None,2,0,C.byref(size))
        attrs = C.create_string_buffer(size.value)
        checked(K.InitializeProcThreadAttributeList(attrs,2,0,C.byref(size)))
        policy, allowlist = W.DWORD(1),(W.HANDLE*len(handles))(*handles)
        checked(K.UpdateProcThreadAttribute(attrs,0,0x2000e,C.byref(policy),C.sizeof(policy),None,None))
        checked(K.UpdateProcThreadAttribute(attrs,0,0x20002,allowlist,C.sizeof(allowlist),None,None))
        si.si.cb, si.attributes, si.si.flags = C.sizeof(SIEX),C.addressof(attrs),0x100
        si.si.stdout,si.si.stderr,si.si.stdin = handles
        block = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items(),key=lambda row:row[0].lower()))+'\0\0')
        checked(K.CreateProcessW(argv[0],C.create_unicode_buffer(subprocess.list2cmdline(argv)),None,None,True,
                                0x08080404,block,str(cwd),C.byref(si),C.byref(pi)))
        out['pid'] = int(pi.pid)
        job = checked(K.CreateJobObjectW(None,None))
        limits = JEXT(); limits.basic.flags,limits.basic.active_processes = 0x2008,1
        checked(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job,pi.process)); assigned=True
        assert K.ResumeThread(pi.thread) != 0xffffffff
        out['wait_result'] = int(K.WaitForSingleObject(pi.process,out['timeout_ms']))
        assert out['wait_result'] == 0, 'compiler timeout'
        code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process,C.byref(code)))
        out['host_exit'] = int(code.value)
        account = JACCOUNT()
        for _ in range(101):
            checked(K.QueryInformationJobObject(job,1,C.byref(account),C.sizeof(account),None))
            if not account.active_processes: break
            time.sleep(.02)
        out['job_active'] = int(account.active_processes)
        out['job_total'] = int(account.total_processes)
    finally:
        if pi.process and K.WaitForSingleObject(pi.process,0) != 0:
            if assigned: K.TerminateJobObject(job,125)
            else: K.TerminateProcess(pi.process,125)
            K.WaitForSingleObject(pi.process,5000); out['forced_termination']=True
        for handle in (*handles,pi.thread,pi.process,job):
            if handle: checked(K.CloseHandle(handle))
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)
    out['stdout'] = (cwd/(label+'.out')).read_text(errors='replace')
    out['stderr'] = (cwd/(label+'.err')).read_text(errors='replace')
    return out


def compile_native(base, source, out):
    build = base/'build'; build.mkdir()
    local_source = build/'boundary_child.c'; local_source.write_bytes(source.read_bytes())
    programs = Path(os.environ['ProgramFiles(x86)'])
    msvc = programs/'Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/14.44.35207'
    sdk = programs/'Windows Kits/10'; tools = msvc/'bin/Hostx64/x64'
    includes = [msvc/'include']+[sdk/'Include/10.0.26100.0'/name for name in ('shared','um','ucrt')]
    libs = [msvc/'lib/x64',sdk/'Lib/10.0.26100.0/um/x64',sdk/'Lib/10.0.26100.0/ucrt/x64']
    environment = {'SystemRoot':os.environ['SystemRoot'],'TEMP':str(build),'TMP':str(build),
                   'PATH':str(tools)+os.pathsep+str(Path(os.environ['SystemRoot'])/'System32')}
    obj,exe = build/'boundary_child.obj',build/'boundary_child.exe'
    compile_args = [str(tools/'cl.exe'),'/nologo','/W4','/WX','/O1','/MT','/DUNICODE','/D_UNICODE','/D_WIN32_WINNT=0x0A00',
                    '/c',str(local_source),'/Fo'+str(obj)]+['/I'+str(p) for p in includes]
    link_args = [str(tools/'link.exe'),'/NOLOGO','/BREPRO','/SUBSYSTEM:CONSOLE','/OUT:'+str(exe),str(obj),'kernel32.lib']+['/LIBPATH:'+str(p) for p in libs]
    out['compiler'] = {'cl_sha256':hashlib.sha256((tools/'cl.exe').read_bytes()).hexdigest(),
                       'link_sha256':hashlib.sha256((tools/'link.exe').read_bytes()).hexdigest(),
                       'msvc_version':'14.44.35207','sdk_version':'10.0.26100.0',
                       'source_sha256':hashlib.sha256(local_source.read_bytes()).hexdigest()}
    for label,argv in (('compile',compile_args),('link',link_args)):
        lane = run_tool(argv,build,environment,label); out['compiler'][label] = lane
        assert lane['host_exit']==0 and lane['job_active']==0 and lane['job_total']==1 and not lane.get('forced_termination'), label+' failed'
    return exe
