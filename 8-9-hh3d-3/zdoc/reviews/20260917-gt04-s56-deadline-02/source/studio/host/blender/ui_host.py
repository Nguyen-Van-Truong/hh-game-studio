"""Bounded private Blender GUI host. No public ACK, journal, or writer lease."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid

from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.private_store import _StoreApi
from studio.host.core.safe_create import SafeCreateApi

STUDIO=Path(__file__).resolve().parents[2]
MAX_LOG=262144
BLENDER_SHA256='8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06'


def load(relative):
    path=STUDIO/relative; raw=path.read_bytes()
    key='_hh_blender_'+hashlib.sha256(str(path).encode()+raw).hexdigest()
    if key not in sys.modules:
        spec=importlib.util.spec_from_file_location(key,path)
        module=importlib.util.module_from_spec(spec); sys.modules[key]=module
        exec(compile(raw,str(path),'exec'),module.__dict__)
    return sys.modules[key]


ipc=load('blender-addon/ipc_client.py')
cli_job=load('godot-addon/cli_job.py')


class HostError(ValueError):
    def __init__(self,code,*,delivery_unknown=False,cleanup_owner=None):
        super().__init__(code)
        self.delivery_unknown,self.cleanup_owner=delivery_unknown,cleanup_owner


def need(value,code):
    if not value: raise HostError(code)


def regular(path):
    info=path.stat(follow_symlinks=False)
    need(not path.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400,'BLENDER_REPARSE')
    return info


def source_files():
    paths=[STUDIO/name for name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')]
    for directory in ('blender-addon','protocol','host/core','host/blender'):
        paths.extend(path for path in (STUDIO/directory).rglob('*.py') if '__pycache__' not in path.parts)
    return {path.relative_to(STUDIO).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


# The helper cannot launch Blender until its stdin gate arrives after Job assignment.
# Bootstrap data is passed through private stdin again; no secret argv/environment.
HELPER="""import json,subprocess,sys
line=sys.stdin.buffer.readline(4097)
if len(line)>4096 or not line.endswith(b'\\n'):sys.exit(125)
p=subprocess.Popen(sys.argv[2:],stdin=subprocess.PIPE)
with open(sys.argv[1]+'-start.json','x',encoding='utf-8') as f:json.dump({'pid':p.pid},f)
p.stdin.write(line);p.stdin.close();line=b''
code=p.wait()
with open(sys.argv[1]+'-exit.json','x',encoding='utf-8') as f:json.dump({'pid':p.pid,'exit_code':code},f)
sys.exit(code)
"""


class BlenderUIHost:
    def __init__(self,parent:Path,*,binary:Path,session_seconds=90,_recovery_seed=None):
        need(os.name=='nt','BLENDER_WINDOWS_REQUIRED')
        need(type(session_seconds) is int and 5<=session_seconds<=120,'BLENDER_SESSION_LIMIT')
        self._recovery_readonly=_recovery_seed is not None
        self._recovery_observation=None;self._recovery_descriptor=None
        recovery_data=None
        if self._recovery_readonly:
            from .recovery_owner import _claim_seed
            recovery_data=_claim_seed(_recovery_seed)
        self.channels={}; self.listeners={}; self.threads=[]
        self._process=self._job=self._api=self._pin_api=None
        self._root=None
        self._closed=self._held=self._stopped=False
        self._done=threading.Event(); self._overflow=threading.Event()
        self._locks={lane:threading.Lock() for lane in ('data','control')}
        self._close_lock=threading.Lock(); self._cleanup=None
        self._export_lock=threading.Lock();self._export_job=None;self._exports={}
        self._source=source_files(); self._session=uuid.uuid4().hex
        self._key=secrets.token_bytes(32); self._deadline=time.monotonic()+session_seconds
        self._binary=Path(binary).absolute()
        try:
            parent=Path(parent).absolute()
            for path in (parent,*parent.parents,self._binary,*self._binary.parents): regular(path)
            need(parent.is_dir() and self._binary.name=='blender.exe'
                 and hashlib.sha256(self._binary.read_bytes()).hexdigest()==BLENDER_SHA256,'BLENDER_BINARY_PIN')
            self._api=_StoreApi()
            self.directory=parent/('blender-'+uuid.uuid4().hex); self._api.mkdir(self.directory)
            self.project=self.directory/'project'; self._api.mkdir(self.project)
            # Blender's own temp-file rename needs immediate-parent WRITE sharing.
            # Keep DELETE denied and verify private ACL using a short-lived reader.
            self._pin_api=SafeCreateApi()
            self._root=self._pin_api.open_parent(self.project,publish=True)
            self._identity=self._pin_api.inspect(self._root,self.project,directory=True)
            self._check_project()
            if recovery_data is not None:
                self._prepare_recovery_input(*recovery_data);recovery_data=None
            for lane in ('control','data'):
                listener=socket.socket(); self.listeners[lane]=listener
                listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                listener.bind(('127.0.0.1',0)); listener.listen(1); listener.settimeout(.05)
            env={key:value for key,value in os.environ.items() if not key.upper().startswith(('PYTHON','BLENDER_','HH_BLENDER_'))}
            env['PYTHONDONTWRITEBYTECODE']='1'
            for key,folder in (('BLENDER_USER_RESOURCES','user'),('TEMP','temp'),('TMP','temp')):
                path=self.directory/folder; path.mkdir(exist_ok=True); env[key]=str(path)
            argv=[str(self._binary),'--factory-startup','--disable-autoexec','--offline-mode','--threads','1',
                  '--python-exit-code','17','--python',str(STUDIO/'blender-addon/ipc_client.py')]
            (self.directory/'launch.json').write_bytes(canonical_bytes({'argv':argv,'source_files':self._source,
                'session':self._session,'binary_sha256':BLENDER_SHA256,'public_ack':False}))
            self._process=subprocess.Popen([sys.executable,'-B','-c',HELPER,str(self.directory/'process'),*argv],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=self.project,env=env,
                creationflags=subprocess.CREATE_NO_WINDOW)
            self._job=cli_job.create(self._process)
            for name,pipe in (('stdout',self._process.stdout),('stderr',self._process.stderr)):
                thread=threading.Thread(target=self._drain,args=(name,pipe),daemon=True)
                self.threads.append(thread); thread.start()
            watchdog=threading.Thread(target=self._watchdog,daemon=True)
            self.threads.append(watchdog); watchdog.start()
            bootstrap={'key':self._key.hex(),'session':self._session,'owned_root':str(self.project),
                       'ports':{lane:sock.getsockname()[1] for lane,sock in self.listeners.items()}}
            if self._recovery_readonly:
                bootstrap['recovery']={'checkpoint_sha256':self._recovery_descriptor['checkpoint_sha256'],
                    'descriptor_sha256':hashlib.sha256(canonical_bytes(self._recovery_descriptor)).hexdigest()}
            raw=canonical_bytes(bootstrap)+b'\n'; need(len(raw)<=4096,'BLENDER_BOOTSTRAP_CAP')
            self._process.stdin.write(raw); self._process.stdin.close()
            bootstrap.clear(); raw=b''
            deadline=min(self._deadline,time.monotonic()+20)
            while not (self.directory/'process-start.json').is_file():
                self._check(deadline); time.sleep(.005)
            self.pid=parse_json((self.directory/'process-start.json').read_bytes())['pid']
            need(type(self.pid) is int and self.pid>0,'BLENDER_ACTUAL_PID')
            for lane in ('control','data'):
                while True:
                    self._check(deadline)
                    try: sock,address=self.listeners[lane].accept(); break
                    except socket.timeout: pass
                need(address[0]=='127.0.0.1','BLENDER_LOOPBACK')
                channel=ipc.Channel(sock,self._key,self._session,lane,'host'); self.channels[lane]=channel
                hello=self._wait(channel,deadline)
                need(hello['kind']=='hello' and hello['body']=={'pid':self.pid,'version':'5.2.1 LTS',
                    'main_thread':True,'background':False,'python_threads':1,'public_ack':False},'BLENDER_HELLO')
                (self.directory/(lane+'-hello.json')).write_bytes(canonical_bytes(hello['body']))
                channel.queue('welcome',{'public_ack':False})
            for channel in self.channels.values():
                while channel.tx:
                    self._check(deadline); need(channel.poll() is None,'BLENDER_UNEXPECTED_EARLY_MESSAGE'); time.sleep(.005)
            ready=self._wait(self.channels['control'],deadline)
            need(ready['kind']=='ready','BLENDER_READY')
            if self._recovery_readonly:
                from .recovery_owner import validate_observation
                ipc.exact(ready['body'],('pid','public_ack','recovery'))
                need(ready['body']['pid']==self.pid and ready['body']['public_ack'] is False,'BLENDER_READY')
                validate_observation(ready['body']['recovery'],self._recovery_descriptor,pid=self.pid,
                    descriptor_sha256=hashlib.sha256(canonical_bytes(self._recovery_descriptor)).hexdigest())
                self._recovery_observation=parse_json(canonical_bytes(ready['body']['recovery']))
                (self.directory/'recovery-ready.json').write_bytes(canonical_bytes(self._recovery_observation))
            else:need(ready['body']=={'pid':self.pid,'public_ack':False},'BLENDER_READY')
            self._key=b''
            for listener in self.listeners.values(): listener.close()
            self.listeners.clear()
        except BaseException as error:
            self._held=True
            try: self.close()
            except BaseException: error.cleanup_owner=self
            raise

    def _prepare_recovery_input(self,checkpoint,descriptor):
        need(type(checkpoint) is bytes and 0<len(checkpoint)<=1024**2
            and hashlib.sha256(checkpoint).hexdigest()==descriptor['checkpoint_sha256']
            and descriptor['source_sha256']==hashlib.sha256(canonical_bytes(self._source)).hexdigest()
            and descriptor['binary_sha256']==BLENDER_SHA256,'BLENDER_RECOVERY_SEED_BINDING')
        root=self.directory/'recovery-input';self._api.mkdir(root)
        # Retain this exact private directory handle through the owned GUI lifetime.
        parent=self._api.open(root,directory=True);self._api.check_security(parent)
        identity=self._api.inspect(parent,root,directory=True)
        for name,raw in (('checkpoint.blend',checkpoint),('descriptor.json',canonical_bytes(descriptor))):
            path=root/name;handle=self._api.open(path,create=True)
            try:
                self._api.write(handle,raw);self._api.flush(handle);self._api.check_security(handle)
                observed=self._api.inspect(handle,path)
                need(self._api.read(handle,1024**2)==raw and observed==self._api.inspect(handle,path),
                    'BLENDER_RECOVERY_STAGING_READBACK')
            finally:self._api.close(handle)
        need(identity.same_file(self._api.inspect(parent,root,directory=True)),'BLENDER_RECOVERY_ROOT_CHANGED')
        self._recovery_descriptor=parse_json(canonical_bytes(descriptor))

    def _drain(self,name,pipe):
        count=0
        try:
            with (self.directory/(name+'.txt')).open('xb') as output:
                while True:
                    raw=pipe.read1(4096)
                    if not raw: break
                    output.write(raw[:max(0,MAX_LOG-count)]); output.flush(); count+=len(raw)
                    if count>MAX_LOG: self._overflow.set()
        finally: pipe.close()

    def _watchdog(self):
        while not self._done.wait(.05):
            if self._overflow.is_set() or time.monotonic()>=self._deadline:
                self._held=True
                try: self._job.terminate()
                except Exception: pass  # close() retains/checks the owner on the caller.
                return

    def _check(self,deadline):
        need(time.monotonic()<deadline and not self._overflow.is_set(),'BLENDER_IPC_DEADLINE')
        need(self._process is not None and self._process.poll() is None,'BLENDER_PROCESS_EXITED')

    def _check_project(self):
        current=self._pin_api.inspect(self._root,self.project,directory=True)
        need(current.same_file(self._identity),'BLENDER_ROOT_CHANGED')
        handle=self._api.open(self.project,directory=True)
        try:self._api.check_security(handle)
        finally:self._api.close(handle)

    def _wait(self,channel,deadline):
        while True:
            self._check(deadline)
            value=channel.poll()
            if value is not None: return value
            time.sleep(.005)

    def _ask(self,lane,kind,body,*,timeout=3,closing=False):
        need(type(timeout) in (int,float) and 0<timeout<=10,'BLENDER_TIMEOUT_LIMIT')
        need(not self._closed and (closing or not self._held),'BLENDER_HELD_OR_CLOSED')
        deadline=min(self._deadline,time.monotonic()+timeout)
        lock=self._locks[lane]
        need(lock.acquire(timeout=max(0,deadline-time.monotonic())),'BLENDER_CHANNEL_BUSY')
        started=False
        try:
            channel=self.channels[lane]
            # The Blender side also sends ready after hello. Preserve enough
            # sequence capacity for both Stop and orderly quit, on both sides.
            if lane=='control' and kind not in ('stop','quit'):
                need(channel.sent<ipc.MAX_MESSAGES-3,'BLENDER_CONTROL_RESERVED')
            sequence=channel.queue(kind,body); started=True
            reply=self._wait(channel,deadline)
            ipc.exact(reply['body'],('request_sequence','ok','result','public_ack') if reply['body'].get('ok') is True
                      else ('request_sequence','ok','reason','public_ack'))
            need(reply['kind']=='reply' and type(reply['body']['request_sequence']) is int
                 and reply['body']['request_sequence']==sequence and type(reply['body']['ok']) is bool
                 and reply['body']['public_ack'] is False,'BLENDER_REPLY_BINDING')
            if reply['body']['ok'] is not True: raise HostError('BLENDER_COMMAND_REJECTED')
            return reply['body']['result']
        except BaseException as error:
            if not isinstance(error,HostError) or str(error)!='BLENDER_COMMAND_REJECTED':
                self._held=True
                if started and lane=='data': error.delivery_unknown=True
            raise
        finally: lock.release()

    def arm_lease(self,lease):
        need(not getattr(self,'_recovery_readonly',False),'BLENDER_RECOVERY_READONLY')
        return self._ask('control','lease',{'lease':lease})

    def submit(self,command,*,ttl_ms=5000,lease=None,deadline_ms=None):
        if deadline_ms is not None:
            need(type(deadline_ms) is int and 1 <= deadline_ms < 2**53, 'BLENDER_ABSOLUTE_DEADLINE_LIMIT')
        if getattr(self,'_recovery_readonly',False):
            need(type(command) is dict and command.get('operation')=='scene.inspect' and lease is None,
                'BLENDER_RECOVERY_READONLY')
        need(not self._stopped,'BLENDER_STOPPED')
        need(source_files()==self._source,'BLENDER_SOURCE_CHANGED')
        self._check_project()
        body={'command':command,'ttl_ms':ttl_ms}
        if lease is not None:body['lease']=lease
        if deadline_ms is not None:body['deadline_ms']=deadline_ms
        return self._ask('data','submit',body)

    def result(self,command_id):
        return self._ask('control','result',{'command_id':command_id})

    def execute(self,command,*,timeout=6,lease=None,deadline_ms=None):
        need(type(timeout) in (int,float) and 0<timeout<=10,'BLENDER_TIMEOUT_LIMIT')
        options = {'lease': lease}
        if deadline_ms is not None:
            options['deadline_ms'] = deadline_ms
        row=self.submit(command,**options); deadline=time.monotonic()+timeout
        while row.get('state')=='PENDING':
            if time.monotonic()>=deadline:
                self._held=True; raise HostError('BLENDER_RESULT_UNKNOWN',delivery_unknown=True)
            time.sleep(.01); row=self.result(command['command_id'])
        return row

    def stop(self):
        self._stopped=True
        with self._export_lock:
            if self._export_job is not None:self._export_job.request_stop()
        return self._ask('control','stop',{},timeout=2,closing=True)

    def export_glb(self,command):
        from .export_job import ExportJob
        need(type(command) is dict and command.get('operation')=='export.prepare','EXPORT_OPERATION_REQUIRED')
        row=self.execute(command)
        need(row.get('state')=='COMPLETED','EXPORT_PREPARATION_REJECTED')
        with self._export_lock:
            key=row['command_id']
            if key in self._exports:
                saved=self._exports[key]
                need(saved is not None,'EXPORT_PREVIOUS_UNKNOWN')
                return parse_json(saved)
            need(not self._stopped and self._export_job is None,'EXPORT_BUSY_OR_STOPPED')
            need(len(self._exports)<8,'EXPORT_SESSION_CAPACITY')
            self._exports[key]=None
            job=ExportJob(self,row['result']);self._export_job=job
        try:
            result=job.run()
            with self._export_lock:self._exports[key]=canonical_bytes(result)
            return result
        finally:
            if job.done.is_set() and not job.cleanup_held:
                with self._export_lock:self._export_job=None

    def close(self):
        with self._close_lock:
            if self._closed: return self._cleanup
            self._stopped=True
            export_failure=None;export_cleanup=None
            with self._export_lock:
                export=self._export_job
                if export is not None:export.request_stop()
            if export is not None:
                try:
                    need(export.done.wait(5),'EXPORT_CLEANUP_RUN_ACTIVE')
                    export_cleanup=export.retry_cleanup()
                    with self._export_lock:
                        if self._export_job is export:self._export_job=None
                except BaseException as exc:
                    export_failure=exc;self._held=True
                # The export owns its native process/Job independently. Even a
                # retained export close failure must not strand the GUI owner.
            if 'control' in self.channels and self._process.poll() is None:
                try:
                    self._ask('control','quit',{},timeout=1,closing=True)
                    self._process.wait(timeout=3)
                except (OSError,ValueError,subprocess.TimeoutExpired): pass
            if self._job is None and self._process is not None:
                self._job=cli_job.owner_for_process(self._process)
            if self._job is not None: self._job.close()
            elif self._process is not None and self._process.poll() is None: self._process.kill()
            if self._process is not None: self._process.wait(timeout=3)
            self._done.set()
            for thread in self.threads:
                if thread.ident is not None:
                    thread.join(2); need(not thread.is_alive(),'BLENDER_THREAD_DRAIN_UNKNOWN')
            for channel in self.channels.values(): channel.close()
            for listener in self.listeners.values(): listener.close()
            if self._process is not None and self._process.stdin is not None and not self._process.stdin.closed:
                self._process.stdin.close()
            if self._process is not None:
                for pipe in (self._process.stdout,self._process.stderr):
                    if pipe is not None and not pipe.closed: pipe.close()
            # An active export may still be reading the pinned project. Retain
            # those parent resources until its run has drained.
            export_active=export is not None and not export.done.is_set()
            if self._api is not None and not export_active: self._api.close_owned()
            if self._root is not None and not export_active:
                self._pin_api.close(self._root); self._root=None
            self._key=b''
            if export_failure is not None:
                raise HostError('EXPORT_CLEANUP_HELD',cleanup_owner=self) from export_failure
            self._closed=True
            actual=self.directory/'process-exit.json' if hasattr(self,'directory') else None
            self._cleanup={'actual_process_exit':parse_json(actual.read_bytes()) if actual and actual.is_file() else None,
                'wrapper_exit_code':self._process.returncode if self._process else None,
                'job':self._job.snapshot() if self._job else None,'logs_overflow':self._overflow.is_set(),
                'closed':True,'held':self._held,'public_ack':False}
            if export_cleanup is not None:self._cleanup['export_cleanup']=export_cleanup
            if hasattr(self,'directory'):
                (self.directory/'close.json').write_bytes(canonical_bytes(self._cleanup))
            return self._cleanup

    def __enter__(self): return self
    def __exit__(self,*args): self.close()
