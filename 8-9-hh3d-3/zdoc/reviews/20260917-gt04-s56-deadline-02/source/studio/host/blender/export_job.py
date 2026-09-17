"""One owned background export. Checked OS caps; internal staged output only."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from studio.protocol.core import canonical_bytes,parse_json
from .glb_preflight import inspect_glb,bind_snapshot

MEMORY_BYTES=2*1024**3
CPU_SECONDS=15
WALL_SECONDS=20
DISK_BYTES=32*1024**2
LOG_BYTES=262144
PROCESS_LIMIT=4


def configure_limits(job):
    native=job._native;limits=native.ExtendedLimit()
    limits.basic.flags=0x2000|0x200|0x8|0x4
    limits.basic.active_limit=PROCESS_LIMIT;limits.basic.job_time=CPU_SECONDS*10_000_000
    limits.job_memory=MEMORY_BYTES
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,w.INT,ctypes.c_void_p,w.DWORD]
    kernel.SetInformationJobObject.restype=w.BOOL
    kernel.QueryInformationJobObject.argtypes=[w.HANDLE,w.INT,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)]
    kernel.QueryInformationJobObject.restype=w.BOOL
    if not kernel.SetInformationJobObject(job._handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        raise OSError(ctypes.get_last_error(),'export Job limits')
    observed=native.ExtendedLimit();size=w.DWORD()
    if not kernel.QueryInformationJobObject(job._handle,9,ctypes.byref(observed),ctypes.sizeof(observed),ctypes.byref(size)):
        raise OSError(ctypes.get_last_error(),'export Job limits query')
    if (size.value!=ctypes.sizeof(observed) or observed.basic.flags!=limits.basic.flags
        or observed.basic.active_limit!=PROCESS_LIMIT or observed.basic.job_time!=limits.basic.job_time
        or observed.job_memory!=MEMORY_BYTES):raise ValueError('EXPORT_NATIVE_CAPS_MISMATCH')
    return {'job_memory_bytes':int(observed.job_memory),'job_user_time_100ns':int(observed.basic.job_time),
        'active_process_limit':int(observed.basic.active_limit),'limit_flags':int(observed.basic.flags),
        'wall_seconds':WALL_SECONDS,'workspace_bytes_limit':DISK_BYTES,'workspace_limit_is_watchdog':True,
        'each_log_capture_bytes':LOG_BYTES}


class ExportJob:
    def __init__(self,host,prepared,*,admission_probe=False,diagnostic=None):
        if type(admission_probe) is not bool:raise ValueError('EXPORT_PROBE_BOOLEAN')
        if diagnostic not in (None,'pause','oom') or (diagnostic and admission_probe):raise ValueError('EXPORT_PROBE_KIND')
        self.diagnostic=diagnostic
        self.admission_probe=admission_probe;self.cleanup_held=False
        self.host=host;self.prepared=prepared
        self._stop=threading.Event();self.done=threading.Event();self._overflow=threading.Event()
        # Retain the exact native owners across every uncertain cleanup return.
        self._process=self._job=None;self._threads=[]
        self._cleanup_lock=threading.Lock();self._run_lock=threading.Lock()
        self._started=False;self._cleanup_attempt=0;self._cleanup_result=None
        self.directory=host.directory/('export-'+uuid.uuid4().hex)
        host._api.mkdir(self.directory)

    def request_stop(self):self._stop.set()

    def _cleanup(self):
        from .ui_host import cli_job,need
        with self._cleanup_lock:
            if self._cleanup_result is not None:return parse_json(self._cleanup_result)
            self._cleanup_attempt+=1
            failure=None
            try:
                if self._job is None and self._process is not None:
                    self._job=cli_job.owner_for_process(self._process)
                if self._job is not None:self._job.close()
                elif self._process is not None and self._process.poll() is None:self._process.kill()
                if self._process is not None:self._process.wait(timeout=3)
                for thread in self._threads:
                    if thread.ident is not None:
                        thread.join(2);need(not thread.is_alive(),'EXPORT_THREAD_DRAIN_UNKNOWN')
                if self._process is not None:
                    for pipe in (self._process.stdin,self._process.stdout,self._process.stderr):
                        if pipe is not None and not pipe.closed:pipe.close()
            except BaseException as exc:failure=exc
            self.cleanup_held=failure is not None
            row={'attempt':self._cleanup_attempt,'cleanup_held':self.cleanup_held,'public_ack':False,
                'job':self._job.snapshot() if self._job else None,
                'wrapper_exit_code':self._process.returncode if self._process else None,
                'threads_drained':all(not thread.is_alive() for thread in self._threads),
                'actual_process_exit':parse_json((self.directory/'process-exit.json').read_bytes())
                if (self.directory/'process-exit.json').exists() else None}
            if failure is not None:row['failure']=type(failure).__name__
            try:
                # Retry evidence is append-only; never relabel the original run.
                with (self.directory/('cleanup-attempt-%04d.json'%self._cleanup_attempt)).open('xb') as stream:
                    stream.write(canonical_bytes(row))
            except BaseException as exc:
                self.cleanup_held=True;failure=exc
            if failure is not None:
                failure.cleanup_owner=self
                raise failure
            self._cleanup_result=canonical_bytes(row)
            return parse_json(self._cleanup_result)

    def retry_cleanup(self):
        from .ui_host import need
        need(self.done.is_set(),'EXPORT_CLEANUP_RUN_ACTIVE')
        return self._cleanup()

    def _drain(self,name,pipe):
        count=0
        try:
            with (self.directory/(name+'.txt')).open('xb') as output:
                while True:
                    raw=pipe.read1(4096)
                    if not raw:break
                    output.write(raw[:max(0,LOG_BYTES-count)]);output.flush();count+=len(raw)
                    if count>LOG_BYTES:self._overflow.set()
        finally:pipe.close()

    def run(self):
        from .ui_host import cli_job,HELPER,STUDIO,HostError,need
        with self._run_lock:
            need(not self._started,'EXPORT_RUN_ALREADY_STARTED');self._started=True
        failure=None;limits=None
        report={'public_ack':False,'candidate_only':True,'completed':False}
        try:
            need(not self._stop.is_set() and not self.host._stopped,'EXPORT_STOPPED')
            artifact=self.prepared['artifact'];need(artifact['name']=='export.blend','EXPORT_FIXED_INPUT')
            path=self.host.project/artifact['name'];self.host._check_project()
            handle=self.host._api.open(path)
            try:
                before=self.host._api.inspect(handle,path)
                raw=self.host._api.read(handle,8*1024**2)
                need(before==self.host._api.inspect(handle,path) and len(raw)==artifact['size_bytes']
                     and hashlib.sha256(raw).hexdigest()==artifact['sha256'],'EXPORT_INPUT_IDENTITY_OR_HASH')
            finally:self.host._api.close(handle)
            (self.directory/'input.blend').write_bytes(raw)
            expected={'input_sha256':artifact['sha256'],'snapshot':self.prepared['after']['snapshot'],
                'revision':self.prepared['after']['revision']}
            (self.directory/'expected.json').write_bytes(canonical_bytes(expected))
            env={key:value for key,value in os.environ.items() if not key.upper().startswith(('PYTHON','BLENDER_','HH_BLENDER_'))}
            env['PYTHONDONTWRITEBYTECODE']='1'
            for key,folder in (('BLENDER_USER_RESOURCES','user'),('TEMP','temp'),('TMP','temp')):
                p=self.directory/folder;p.mkdir(exist_ok=True);env[key]=str(p)
            argv=[str(self.host._binary),'--background','--factory-startup','--disable-autoexec','--offline-mode','--threads','1',
                '--python-exit-code','17','--python',str(STUDIO/'blender-addon/export_background.py'),'--',str(self.directory)]
            probe_sha=None
            if self.admission_probe:
                argv.append('--admission-probe')
                probe_sha=hashlib.sha256((STUDIO/'tests/blender/export_negative_probe.py').read_bytes()).hexdigest()
            elif self.diagnostic:argv.append('--'+self.diagnostic+'-probe')
            (self.directory/'launch.json').write_bytes(canonical_bytes({'argv':argv,'source_files':self.host._source,
                'admission_probe_sha256':probe_sha,'public_ack':False}))
            self._process=subprocess.Popen([sys.executable,'-B','-c',HELPER,str(self.directory/'process'),*argv],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=self.directory,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW)
            process=self._process
            self._job=cli_job.create(process);limits=configure_limits(self._job)
            (self.directory/'limits.json').write_bytes(canonical_bytes(limits))
            for name,pipe in (('stdout',process.stdout),('stderr',process.stderr)):
                thread=threading.Thread(target=self._drain,args=(name,pipe),daemon=True);self._threads.append(thread);thread.start()
            need(not self._stop.is_set() and not self.host._stopped,'EXPORT_STOPPED')
            process.stdin.write(b'{}\n');process.stdin.close()
            deadline=time.monotonic()+WALL_SECONDS
            while process.poll() is None:
                need(not self._stop.is_set(),'EXPORT_CANCELLED')
                need(time.monotonic()<deadline,'EXPORT_DEADLINE')
                need(not self._overflow.is_set(),'EXPORT_LOG_CAP')
                total=sum(path.stat().st_size for path in self.directory.rglob('*') if path.is_file())
                need(total<=DISK_BYTES,'EXPORT_WORKSPACE_CAP')
                time.sleep(.02)
            need(process.returncode==0,'EXPORT_NATIVE_FAILED')
            for thread in self._threads:thread.join(2);need(not thread.is_alive(),'EXPORT_LOG_DRAIN_UNKNOWN')
            native=parse_json((self.directory/'result.json').read_bytes())
            need(native['native_finished'] is True and native['context_unchanged'] is True
                 and native['public_ack'] is False and native['snapshot']==expected['snapshot']
                 and native['scene_revision']==expected['revision'] and native['input_sha256']==expected['input_sha256'],
                 'EXPORT_NATIVE_READBACK')
            output=self.directory/'output.glb';need(output.stat().st_size<=4*1024**2,'EXPORT_OUTPUT_CAP')
            preflight=inspect_glb(output.read_bytes())
            need(preflight['sha256']==native['output_sha256'] and preflight['size_bytes']==native['output_size_bytes']
                 and preflight['objects']==len(expected['snapshot']['objects']),'EXPORT_GLB_BINDING')
            bind_snapshot(preflight,expected['snapshot'])
            need(not self._stop.is_set(),'EXPORT_CANCELLED')
            report.update(completed=True,native=native,preflight=preflight,snapshot_geometry_bound=True,artifact={'name':'output.glb',
                'sha256':preflight['sha256'],'size_bytes':preflight['size_bytes']},status='INTERNAL_EXPORT_VERIFIED')
        except BaseException as exc:
            failure=exc;report['failure']=str(exc) if isinstance(exc,HostError) else type(exc).__name__
        finally:
            try:
                cleanup=self._cleanup()
                report.update({name:cleanup[name] for name in ('job','wrapper_exit_code','actual_process_exit')})
            except BaseException as exc:
                self.cleanup_held=True;report.update(completed=False,cleanup_held=True,status='EXPORT_CLEANUP_HELD',
                    job=self._job.snapshot() if self._job else None,
                    wrapper_exit_code=self._process.returncode if self._process else None)
                failure=exc;failure.cleanup_owner=self
            report['limits']=limits
            try:
                with (self.directory/'host-result.json').open('xb') as stream:stream.write(canonical_bytes(report))
            except BaseException as exc:
                failure=exc;failure.cleanup_owner=self
            finally:self.done.set()
        if failure is not None:raise failure
        return report
