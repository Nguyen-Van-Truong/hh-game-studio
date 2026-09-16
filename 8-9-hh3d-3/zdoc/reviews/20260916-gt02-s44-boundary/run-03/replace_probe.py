"""Real confined native adversary concurrent with unpatched protected replace.

S32 supplies fixed compiler/Win32 declarations. The runtime source is copied
and hashed before import; this diagnostic does not enable public capability.
"""
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
sys.path.insert(0, str(HELPER))
import boundary_probe as prior
from windows_api import *
from compile_native import compile_native

spec = importlib.util.spec_from_file_location('freeze', PRODUCT/'studio/tests/protocol/run_gt02_candidate.py')
freeze = importlib.util.module_from_spec(spec); spec.loader.exec_module(freeze)
FILES = freeze.source_manifest()
RUNTIME = tempfile.TemporaryDirectory(prefix='gt02-s44-snapshot-')
RUNTIME_ROOT = Path(RUNTIME.name).resolve()
for name, digest in FILES.items():
    raw = (PRODUCT/'studio'/name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    path = RUNTIME_ROOT/'studio'/name
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
sys.path.insert(0, str(RUNTIME_ROOT))
from studio.host.core.safe_replace import ProtectedFileRoot


def launch(executable, scratch, files, package, out):
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
        environment = {key: os.environ[key] for key in ('SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','SystemDrive')}
        environment.update(WINDIR=os.environ['SystemRoot'], PATH=str(Path(os.environ['SystemRoot'])/'System32'),
            TEMP=str(scratch), TMP=str(scratch), S44_ROOT=str(files.root), S44_SCRATCH=str(scratch), S44_BROKER=str(os.getpid()))
        block = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items(),key=lambda row:row[0].lower()))+'\0\0')
        checked(K.CreateProcessW(str(executable), C.create_unicode_buffer('"'+str(executable)+'"'), None, None, False,
                                0x8040c, block, str(scratch), C.byref(si), C.byref(pi)))
        out['pid'] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process, 8, C.byref(token)))
        out['token_is_appcontainer'] = token_number(token, 29)
        out['token_package_matches'] = token_sid(token, 31) == sid_text(package)
        out['integrity_sid'], out['capabilities'] = token_sid(token, 25), token_number(token, 30)
        assert out['token_is_appcontainer'] == 1 and out['token_package_matches']
        assert out['integrity_sid'] == 'S-1-16-4096' and out['capabilities'] == 0
        job = checked(K.CreateJobObjectW(None, None))
        limits = JEXT(); limits.basic.flags, limits.basic.active_processes, limits.process_memory = 0x2108, 1, 128*1024*1024
        checked(K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job, pi.process)); assigned = True
        assert K.ResumeThread(pi.thread) != 0xffffffff
        deadline = time.monotonic() + 5
        while not (scratch/'ready').exists():
            assert time.monotonic() < deadline and K.WaitForSingleObject(pi.process, 0) != 0, 'native readiness failed'
            time.sleep(.005)
        assert (scratch/'ready').read_bytes() == b'READY'
        first, _ = files.read('asset.txt')
        transitions = []
        version = first
        for index in range(20):
            data = ('version-'+str(index)).encode()
            after = files.atomic_replace('asset.txt', data, expected=version)
            assert not after.identity.same_file(version.identity)
            assert files.read('asset.txt') == (after, data)
            transitions.append({'old_id':version.identity.file_id,'new_id':after.identity.file_id,'sha256':after.sha256})
            version = after
            time.sleep(.001)
        out['replacements'] = transitions
        assert (scratch/'attacker.txt').read_bytes() == b'ATTACKER'
        (scratch/'stop').write_bytes(b'STOP')
        assert K.WaitForSingleObject(pi.process, 5000) == 0, 'native exit timeout'
        code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process, C.byref(code)))
        out['host_exit'] = int(code.value)
        out['native'] = json.loads((scratch/'result.json').read_bytes())
        assert out['host_exit'] == 67 and out['native']['complete'] == 'S44_NATIVE_COMPLETE'
        assert out['native']['allowed'] == out['native']['unexpected_errors'] == 0
        assert out['native']['attempts'] == 9*out['native']['loops'] and out['native']['loops'] >= 2
        assert sorted(p.name for p in files.root.iterdir()) == ['.writer','asset.txt']
        out['outside_alias_absent'] = not (scratch/'outward-link').exists()
        assert out['outside_alias_absent']
    finally:
        if pi.process and K.WaitForSingleObject(pi.process, 0) != 0:
            if assigned: K.TerminateJobObject(job, 123)
            else: K.TerminateProcess(pi.process, 123)
            K.WaitForSingleObject(pi.process, 5000); out['forced_owned_termination'] = True
        if pi.process:
            code = W.DWORD(); checked(K.GetExitCodeProcess(pi.process, C.byref(code)))
            out['final_host_exit'] = int(code.value)
        if assigned:
            account = JACCOUNT()
            for _ in range(101):
                checked(K.QueryInformationJobObject(job, 1, C.byref(account), C.sizeof(account), None))
                if not account.active_processes: break
                time.sleep(.02)
            pids = prior.PIDLIST()
            checked(K.QueryInformationJobObject(job, 3, C.byref(pids), C.sizeof(pids), None))
            out['final_job_active'],out['final_job_pids'] = int(account.active_processes),list(pids.pids)[:pids.count]
        if (scratch/'result.json').exists(): out['native'] = json.loads((scratch/'result.json').read_bytes())
        for handle in (token,pi.thread,pi.process,job):
            if handle: checked(K.CloseHandle(handle))
        if attrs is not None: K.DeleteProcThreadAttributeList(attrs)


def main():
    moniker = 'hh-gt02-s44-'+uuid.uuid4().hex
    profile = Path(os.environ['LOCALAPPDATA'])/'Packages'/moniker
    package, token = C.c_void_p(), W.HANDLE()
    created, base, mapping = False, None, None
    out = {'run_id':sys.argv[1],'timestamp_utc':datetime.now(timezone.utc).isoformat(),
           'runtime_closure':{'source_closure_sha256':freeze.RUNNER.source_closure_sha256(FILES),'files':FILES},
           'safe_write':False,'acceptance':False,'snapshot_used':True}
    out['diagnostic_sources'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),BASE/'boundary_child.c',BASE/'compile_native.py',HELPER/'boundary_probe.py',HELPER/'windows_api.py')}
    try:
        checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(token)))
        user = token_sid(token, 1)
        assert U.DeriveAppContainerSidFromAppContainerName(moniker, C.byref(package)) == 0
        package_string = sid_text(package)
        mapping = 'Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\'+package_string
        assert not profile.exists() and not prior.mapping_exists(mapping)
        created_sid = C.c_void_p()
        assert U.CreateAppContainerProfile(moniker, moniker, 'Owned S44 fixture', None, 0, C.byref(created_sid)) == 0
        created = True; A.FreeSid(created_sid)
        with tempfile.TemporaryDirectory(prefix='gt02-s44-native-') as tmp:
            base = Path(tmp).resolve(); base.relative_to(Path(tempfile.gettempdir()).resolve())
            executable = compile_native(base, BASE/'boundary_child.c', out)
            common = 'D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;'+user+')'
            scratch, images = base/'scratch', base/'images'
            make_directory(scratch, common+'(A;OICI;0x1301bf;;;'+package_string+')S:(ML;OICI;NW;;;LW)')
            make_directory(images, common+'(A;OICI;GRGX;;;'+package_string+')')
            image = images/'boundary_child.exe'; image.write_bytes(executable.read_bytes())
            out['executable_sha256'] = hashlib.sha256(image.read_bytes()).hexdigest()
            with ProtectedFileRoot.create(base) as files:
                files.create_new('asset.txt', b'initial')
                launch(image, scratch, files, package, out)
            assert out['final_job_active'] == 0 and out['final_job_pids'] == []
            assert out['final_host_exit'] == 67 and not out.get('forced_owned_termination')
            out['marker'] = 'S44_REPLACE_BOUNDARY_COMPLETE'
    except Exception as exc:
        out['error'] = {'type':type(exc).__name__,'message':str(exc),'winerror':getattr(exc,'winerror',None)}
    finally:
        if token: K.CloseHandle(token)
        if package.value: A.FreeSid(package)
        if created: out['delete_profile_hresult'] = int(U.DeleteAppContainerProfile(moniker))
        out['profile_absent_after'] = not profile.exists() and (mapping is None or not prior.mapping_exists(mapping))
        out['owned_temp_removed'] = base is not None and not base.exists()
        out['source_unchanged'] = freeze.source_manifest() == FILES
        out['snapshot_unchanged'] = freeze.source_manifest(RUNTIME_ROOT/'studio') == FILES
        RUNTIME.cleanup(); out['snapshot_removed'] = not RUNTIME_ROOT.exists()
    out['complete'] = bool(out.get('marker') and all(out[key] for key in ('profile_absent_after','owned_temp_removed','source_unchanged','snapshot_unchanged','snapshot_removed')))
    print(json.dumps(out,indent=2),flush=True)
    return 0 if out['complete'] else 1


if __name__ == '__main__':
    sys.exit(main())
