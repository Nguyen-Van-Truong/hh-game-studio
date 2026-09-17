"""Bounded FIFO writer tickets on the unchanged GT02 durable Journal.

Compound ticket/lease decisions use its existing OS writer lock and record
validation. Native IPC occurs after releasing that lock. A grant has a durable
intent before native arming and a terminal receipt after native readback.
"""
from dataclasses import asdict
import hashlib

from studio.host.core.journal import Journal,JournalError,Lease
from studio.protocol.core import canonical_bytes,parse_json

PROJECT='blender.owned-fixture'
TARGET='blender.owned-scene'
REQUESTS=PROJECT+'.writer-requests'
GRANTS=PROJECT+'.writer-grants'
META=PROJECT+'.metadata'
MAX_WAITERS=8
MAX_TICKETS=64
MAX_WAIT_MS=120000


def need(value,code):
    if not value:raise JournalError(code)
def digest(value):return 'sha256:'+hashlib.sha256(canonical_bytes(value)).hexdigest()


class BlenderWriterJournal(Journal):
    def _append_command(self,**kwargs):return Journal.append_command.__wrapped__(self,**kwargs)
    def _finish_command(self,**kwargs):return Journal.finish_command.__wrapped__(self,**kwargs)
    def _stopped(self):return self._command((META,'writer-stop')) is not None
    def _check_running(self):need(not self._stopped(),'BLENDER_WRITER_STOPPED')
    def _requests(self):
        return [(index,self._records[index]) for (project,_),index in self._commands.items() if project==REQUESTS]
    def _pending_requests(self):
        return sorted((index,row) for index,row in self._requests() if row['status']=='ACCEPTED_PENDING')
    def _view(self,row):
        value=parse_json(canonical_bytes(row['receipt']))
        if row['status']=='ACCEPTED_PENDING':
            marker=self._command((GRANTS,value['ticket_id']))
            value['state']='GRANTING' if marker is not None else 'WAITING'
        return value
    def _end(self,row,state,now_ms,reason):
        receipt=dict(row['receipt'],state=state,reason=reason)
        result=self._finish_command(project_id=REQUESTS,command_id=row['command_id'],
            status='CANCELED' if state=='CANCELED' else 'UNKNOWN' if state=='UNKNOWN' else 'REJECTED',
            receipt=receipt,now_ms=now_ms)
        marker=self._command((GRANTS,row['command_id']))
        if marker is not None and marker['status']=='ACCEPTED_PENDING':
            self._finish_command(project_id=GRANTS,command_id=row['command_id'],status='UNKNOWN',
                receipt=dict(marker['receipt'],reason=reason),now_ms=now_ms)
        return result
    def _expire(self,now_ms):
        for _,row in self._pending_requests():
            if row['receipt']['queue_expires_ms']<=now_ms:self._end(row,'EXPIRED',now_ms,'QUEUE_DEADLINE')

    @Journal._mutating
    def check_running(self):self._check_running()

    @Journal._mutating
    def acquire_immediate(self,*,writer,now_ms,ttl_ms):
        self._check_running()
        need(self._command((META,'writer-fifo')) is None,'BLENDER_FIFO_REQUIRED')
        return Journal.acquire_lease.__wrapped__(self,project_id=PROJECT,target=TARGET,owner=writer,
            now_ms=now_ms,ttl_ms=ttl_ms)

    @Journal._mutating
    def enqueue_writer(self,*,ticket_id,writer,generation,now_ms,wait_ms,lease_ms):
        need(type(now_ms) is int and 0<=now_ms<2**53,'INVALID_CLOCK')
        need(type(wait_ms) is int and 1<=wait_ms<=MAX_WAIT_MS
            and type(lease_ms) is int and 1<=lease_ms<=self.limits.max_lease_ttl_ms,'BLENDER_WRITER_DEADLINE')
        shape={'ticket_id':ticket_id,'writer':writer,'generation':generation,'wait_ms':wait_ms,'lease_ms':lease_ms}
        key=(REQUESTS,ticket_id);old=self._command(key);request_digest=digest(shape)
        if old is not None:
            need(old['digest']==request_digest,'BLENDER_WRITER_TICKET_CONFLICT')
            need(now_ms<=old['expires_ms'],'RETRY_HORIZON_EXPIRED')
            return self._view(old)
        self._check_running();self._expire(now_ms)
        requests=self._requests();pending=self._pending_requests()
        need(len(requests)<MAX_TICKETS and len(pending)<MAX_WAITERS,'BLENDER_WRITER_QUEUE_FULL')
        need(all(row['receipt']['writer']!=writer for _,row in pending),'BLENDER_WRITER_ALREADY_QUEUED')
        self._append_command(project_id=META,command_id='writer-fifo',digest=digest({'schema':1}),
            receipt={'schema':1,'public_ack':False},now_ms=now_ms)
        response=dict(shape,state='WAITING',queue_expires_ms=now_ms+wait_ms,lease=None,reason=None,public_ack=False)
        self._append_command(project_id=REQUESTS,command_id=ticket_id,digest=request_digest,
            receipt=response,now_ms=now_ms,pending=True)
        return self._view(self._command(key))

    @Journal._mutating
    def lookup_writer(self,*,ticket_id,writer,now_ms):
        self._expire(now_ms)
        row=self._command((REQUESTS,ticket_id));need(row is not None,'BLENDER_WRITER_TICKET_UNKNOWN')
        need(row['receipt']['writer']==writer,'BLENDER_WRITER_TICKET_OWNER')
        need(now_ms<=row['expires_ms'],'RETRY_HORIZON_EXPIRED')
        return self._view(row)

    @Journal._mutating
    def cancel_writer(self,*,ticket_id,writer,now_ms):
        self._expire(now_ms)
        row=self._command((REQUESTS,ticket_id));need(row is not None,'BLENDER_WRITER_TICKET_UNKNOWN')
        need(row['receipt']['writer']==writer,'BLENDER_WRITER_TICKET_OWNER')
        if row['status']=='ACCEPTED_PENDING':self._end(row,'CANCELED',now_ms,'CLIENT_CANCELLED')
        else:need(row['receipt']['state']!='GRANTED','BLENDER_WRITER_ALREADY_GRANTED')
        return self._view(self._command((REQUESTS,ticket_id)))

    @Journal._mutating
    def prepare_next_writer(self,*,generation,now_ms):
        self._check_running();self._expire(now_ms)
        # A terminal ticket can survive a crash before its bookkeeping marker
        # finishes. Close only that metadata; never re-arm a native grant.
        for (_,key),index in list(self._commands.items()):
            marker=self._records[index]
            if marker['project_id']!=GRANTS or marker['status']!='ACCEPTED_PENDING':continue
            ticket=self._command((REQUESTS,key))
            if ticket is not None and ticket['status']!='ACCEPTED_PENDING':
                self._finish_command(project_id=GRANTS,command_id=key,
                    status='COMMITTED' if ticket['receipt']['state']=='GRANTED' else 'UNKNOWN',
                    receipt=marker['receipt'],now_ms=now_ms)
        current=self._leases.get((PROJECT,TARGET))
        if current is not None and current.expires_ms>now_ms:return None
        for _,row in self._pending_requests():
            value=row['receipt'];need(value['generation']==generation,'BLENDER_WRITER_GENERATION')
            # A lost native grant reply cannot renew/regrant the same ticket.
            if self._command((GRANTS,value['ticket_id'])) is not None:
                self._end(row,'UNKNOWN',now_ms,'GRANT_READBACK_UNRESOLVED');continue
            ttl=min(value['lease_ms'],value['queue_expires_ms']-now_ms)
            lease=Journal.acquire_lease.__wrapped__(self,project_id=PROJECT,target=TARGET,
                owner=value['writer'],now_ms=now_ms,ttl_ms=ttl)
            grant={'ticket_id':value['ticket_id'],'generation':generation,'lease':asdict(lease),'public_ack':False}
            self._append_command(project_id=GRANTS,command_id=value['ticket_id'],digest=digest(grant),
                receipt=grant,now_ms=now_ms,pending=True)
            return grant
        return None

    @Journal._mutating
    def complete_writer(self,*,grant,now_ms):
        self._check_running();self._expire(now_ms)
        key=grant['ticket_id'];row=self._command((REQUESTS,key));marker=self._command((GRANTS,key))
        need(row is not None and row['status']=='ACCEPTED_PENDING','BLENDER_WRITER_GRANT_NOT_PENDING')
        need(marker is not None and marker['receipt']==grant and marker['status']=='ACCEPTED_PENDING',
            'BLENDER_WRITER_GRANT_BINDING')
        lease=Lease(**grant['lease'])
        Journal.check_lease.__wrapped__(self,lease,now_ms=now_ms)
        receipt=dict(row['receipt'],state='GRANTED',lease=asdict(lease))
        self._finish_command(project_id=REQUESTS,command_id=key,status='COMMITTED',receipt=receipt,now_ms=now_ms)
        self._finish_command(project_id=GRANTS,command_id=key,status='COMMITTED',receipt=grant,now_ms=now_ms)
        return self._view(self._command((REQUESTS,key)))

    @Journal._mutating
    def stop_writers(self,*,now_ms):
        self._append_command(project_id=META,command_id='writer-stop',digest=digest({'stopped':True}),
            receipt={'stopped':True,'public_ack':False},now_ms=now_ms)
        for _,row in self._pending_requests():self._end(row,'CANCELED',now_ms,'HOST_STOPPED')
        return {'stopped':True,'public_ack':False}
