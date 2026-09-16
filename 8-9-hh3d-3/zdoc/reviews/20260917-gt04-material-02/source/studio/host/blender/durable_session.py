"""Internal durable receipts and fenced admission for one owned Blender GUI.

The unchanged GT02 journal provides checksums, locking, fsync, dedupe and lease
epochs. Receipts record observations; they do not persist or recover GUI state.
Reopening without the original host is lookup-only and never repeats an effect.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import threading
import time

from studio.host.core.journal import Journal,JournalError,JournalLimits,Lease
from studio.protocol.core import canonical_bytes,parse_json
from .ui_host import HostError,load,need

queue=load('blender-addon/ui_queue.py')
PROJECT='blender.owned-fixture'
TARGET='blender.owned-scene'
SCHEMA='HH-BLENDER-DURABLE-RESPONSE-1'
MAX_WIRE=65536


def epoch_ms():return time.time_ns()//1_000_000


def receipt(command_digest,response):
    raw=canonical_bytes(response);need(len(raw)<=MAX_WIRE,'BLENDER_RESPONSE_CAP')
    text=raw.decode('utf-8')
    return {'command_digest':command_digest,'wire_sha256':hashlib.sha256(raw).hexdigest(),
        'wire_chunks':[text[index:index+8192] for index in range(0,len(text),8192)]}


def response_bytes(value):
    need(type(value) is dict and set(value)=={'command_digest','wire_sha256','wire_chunks'},'BLENDER_RECEIPT_FIELDS')
    chunks=value['wire_chunks']
    need(type(chunks) is list and 1<=len(chunks)<=32 and all(type(x) is str and len(x)<=8192 for x in chunks),
        'BLENDER_RECEIPT_CHUNKS')
    raw=''.join(chunks).encode('utf-8');need(len(raw)<=MAX_WIRE,'BLENDER_RESPONSE_CAP')
    decoded=parse_json(raw)
    need(canonical_bytes(decoded)==raw and hashlib.sha256(raw).hexdigest()==value['wire_sha256']
        and decoded['schema']==SCHEMA and decoded['public_ack'] is False
        and decoded['scene_state_durable'] is False,'BLENDER_RECEIPT_BINDING')
    return raw


class DurableBlenderSession:
    """Trusted local owner; no HTTP/public capability and no arbitrary paths.

    ``directory`` is a host-owned state directory, never a command argument.
    Cross-process journal locking protects durable records. Native fencing is
    checked again by the Blender main-thread queue immediately before dispatch.
    """
    def __init__(self,directory:Path,*,host=None,clock=epoch_ms):
        self.directory=Path(directory).absolute();self.host=host;self.clock=clock
        self._lock=threading.RLock();self._held=False;self._stopped=False
        if host is not None:
            need(self.directory==host.directory/'journal','BLENDER_FIXED_JOURNAL_DIRECTORY')
            if not self.directory.exists():host._api.mkdir(self.directory)
        else:need((self.directory/'blender-journal.jsonl').is_file(),'BLENDER_EXISTING_JOURNAL_REQUIRED')
        self.journal=Journal(self.directory/'blender-journal.jsonl',limits=JournalLimits(
            max_bytes=16*1024**2,max_records=512,max_pending_commands=8,
            retry_horizon_ms=86400000,max_lease_ttl_ms=120000))
        if host is not None:
            config={'generation':host._session,'public_ack':False}
            binding=self.journal.append_command(project_id=PROJECT+'.metadata',command_id='session-binding',
                digest='sha256:'+hashlib.sha256(b'HH-BLENDER-DURABLE-SESSION-1').hexdigest(),
                receipt=config,now_ms=self.clock())
            need(binding['receipt']==config,'BLENDER_DIFFERENT_GENERATION_REQUIRES_RECONCILE')

    def acquire_writer(self,writer,*,ttl_ms=10000):
        queue.c.identifier(writer)
        with self._lock:
            need(self.host is not None and not self._held and not self._stopped,'BLENDER_SESSION_READONLY_OR_HELD')
            lease=self.journal.acquire_lease(project_id=PROJECT,target=TARGET,owner=writer,now_ms=self.clock(),ttl_ms=ttl_ms)
            wire={'fencing_epoch':lease.fencing_epoch,'expires_ms':lease.expires_ms}
            try:need(self.host.arm_lease(wire)==wire,'BLENDER_LEASE_NATIVE_READBACK')
            except BaseException:
                self._held=True;raise
            return lease

    def _lookup(self,key,digest=None):
        row=self.journal.lookup(project_id=PROJECT,command_id=key,now_ms=self.clock())
        need(digest is None or row['receipt']['command_digest']==digest,'BLENDER_COMMAND_CONFLICT')
        return row

    @staticmethod
    def _response(key,status,*,native=None,reason=None):
        return {'schema':SCHEMA,'command_id':key,'status':status,'native':native,'reason':reason,
            'public_ack':False,'scene_state_durable':False}

    def lookup_bytes(self,key):
        queue.c.identifier(key)
        with self._lock:
            row=self._lookup(key)
            if row['status']=='ACCEPTED_PENDING':
                # An interrupted owner cannot prove whether dispatch/effect ran.
                return canonical_bytes(self._response(key,'UNKNOWN',reason='UNRESOLVED_DURABLE_INTENT'))
            return response_bytes(row['receipt'])

    def execute_bytes(self,command,lease):
        value=queue.parse(queue.c.canonical(command));key=value['command_id'];digest=queue.c.digest(value)
        with self._lock:
            try:previous=self._lookup(key,digest)
            except JournalError as error:
                if error.code!='COMMAND_NOT_FOUND':raise
            else:
                if previous['status']=='ACCEPTED_PENDING':
                    return canonical_bytes(self._response(key,'UNKNOWN',reason='UNRESOLVED_DURABLE_INTENT'))
                return response_bytes(previous['receipt'])
            need(self.host is not None and not self._held and not self._stopped,'BLENDER_SESSION_READONLY_OR_HELD')
            need(type(lease) is Lease and lease.project_id==PROJECT and lease.target==TARGET,'BLENDER_WRITER_LEASE_REQUIRED')
            self.journal.check_lease(lease,now_ms=self.clock())
            pending={'command_digest':digest,'generation':self.host._session,'lease_epoch':lease.fencing_epoch,
                'operation':value['operation'],'public_ack':False}
            admitted=self.journal.append_command(project_id=PROJECT,command_id=key,digest=digest,
                receipt=pending,now_ms=self.clock(),pending=True)
            if admitted['replayed']:
                if admitted['status']=='ACCEPTED_PENDING':
                    return canonical_bytes(self._response(key,'UNKNOWN',reason='UNRESOLVED_DURABLE_INTENT'))
                return response_bytes(admitted['receipt'])
            status='UNKNOWN';native=None;reason='DISPATCH_OR_READBACK_UNKNOWN'
            try:
                self.journal.check_lease(lease,now_ms=self.clock())
                native=self.host.execute(value,lease={'fencing_epoch':lease.fencing_epoch,'expires_ms':lease.expires_ms})
                need(native.get('command_id')==key and native.get('command_digest')==digest
                    and native.get('public_ack') is False,'BLENDER_NATIVE_RESPONSE_BINDING')
                state=native.get('state')
                need(state in ('COMPLETED','REJECTED','EXPIRED','CANCELLED','HELD'),'BLENDER_NATIVE_RESPONSE_STATE')
                status='COMMITTED' if state=='COMPLETED' else ('UNKNOWN' if state=='HELD' else 'REJECTED')
                reason=None if status=='COMMITTED' else 'NATIVE_'+state
            except Exception:
                self._held=True
            response=self._response(key,status,native=native,reason=reason)
            saved=receipt(digest,response)
            try:
                self.journal.finish_command(project_id=PROJECT,command_id=key,status=status,receipt=saved,now_ms=self.clock())
                observed=self._lookup(key,digest)
                need(observed['status']==status and observed['receipt']==saved,'BLENDER_DURABLE_RESPONSE_READBACK')
                return response_bytes(observed['receipt'])
            except BaseException:
                self._held=True;raise

    def stop(self):
        # Do not wait for the data/receipt lock before priority native Stop.
        self._stopped=True
        return self.host.stop() if self.host is not None else {'stopped':True,'public_ack':False}
