"""Supplemental Windows x64 handle-table snapshots of explicitly owned processes.

Uses documented PSS APIs, with handles only: no VA clone, thread context,
remote memory writes, process settings, privileges or target handle closes.
Caller supplies PID + exact creation FILETIME + executable ownership binding
and an external process deadline. Snapshot creation/walk itself is not a hard
watchdog. Handle values can be reused; these are observations, not identities.
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry
https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot
"""
import ctypes as C
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time

D = C.c_uint32
H = C.c_void_p


class FT(C.Structure):
    _fields_ = [('low', D), ('high', D)]


class ThreadInfo(C.Structure):
    _fields_ = [('exit_status', D), ('teb', H), ('pid', D), ('tid', D),
                ('affinity', C.c_size_t), ('priority', C.c_int32),
                ('base_priority', C.c_int32), ('start', H)]


class Specific(C.Union):
    _fields_ = [('thread', ThreadInfo), ('padding', C.c_byte * 48)]


class Entry(C.Structure):
    _fields_ = [('handle', H), ('flags', D), ('object_type', D), ('capture_time', FT),
                ('attributes', D), ('access', D), ('handle_count', D),
                ('pointer_count', D), ('paged', D), ('nonpaged', D), ('created', FT),
                ('type_length', C.c_uint16), ('type_name', H),
                ('name_length', C.c_uint16), ('name', H), ('specific', Specific)]


class HandleProbe:
    def __init__(self, pid, created, executable):
        if os.name != 'nt' or C.sizeof(H) != 8 or C.sizeof(Entry) != 136:
            raise RuntimeError('PSS_X64_LAYOUT')
        self.k = C.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'OpenProcess': ([D, C.c_int32, D], H), 'CloseHandle': ([H], C.c_int32),
            'GetCurrentProcess': ([], H), 'GetProcessHandleCount': ([H, C.POINTER(D)], C.c_int32),
            'GetProcessTimes': ([H]+[C.POINTER(FT)]*4, C.c_int32),
            'QueryFullProcessImageNameW': ([H,D,C.c_wchar_p,C.POINTER(D)], C.c_int32),
            'WaitForSingleObject': ([H,D],D),
            'PssCaptureSnapshot': ([H,D,D,C.POINTER(H)],D),
            'PssFreeSnapshot': ([H,H],D), 'PssWalkMarkerCreate': ([H,C.POINTER(H)],D),
            'PssWalkMarkerFree': ([H],D), 'PssWalkSnapshot': ([H,D,H,H,D],D),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.k,name); fn.argtypes=args; fn.restype=result
        self.pid=pid; self.handle=None; self.snapshots=[]; self.markers=[]
        # Empirically tested mask, not a documented minimum guarantee for PSS.
        self.access=0x0400 | 0x0010 | 0x0040 | 0x100000
        try:
            self.handle=self.k.OpenProcess(self.access,False,pid)
            if not self.handle: raise C.WinError(C.get_last_error())
            times=[FT() for _ in range(4)]
            if not self.k.GetProcessTimes(self.handle,*(C.byref(t) for t in times)):
                raise C.WinError(C.get_last_error())
            actual=(times[0].high<<32)|times[0].low
            size=D(32768); name=C.create_unicode_buffer(32768)
            if not self.k.QueryFullProcessImageNameW(self.handle,0,name,C.byref(size)):
                raise C.WinError(C.get_last_error())
            if actual!=int(created) or os.path.normcase(name.value)!=os.path.normcase(str(Path(executable).resolve())):
                raise RuntimeError('PSS_PROCESS_IDENTITY')
            self.identity={'pid':pid,'creation_filetime':actual,'executable':name.value}
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _ok(code, api):
        if code: raise RuntimeError(f'{api}:{code}')

    def count(self):
        count=D()
        if not self.k.GetProcessHandleCount(self.handle,C.byref(count)):
            raise C.WinError(C.get_last_error())
        return count.value

    @staticmethod
    def _wide(pointer,length):
        if length>65534 or length%2 or (length and not pointer):
            raise RuntimeError('PSS_NAME_LENGTH')
        return C.string_at(pointer,length).decode('utf-16-le') if length else ''

    def snapshot(self):
        if self.k.WaitForSingleObject(self.handle,0)!=258:
            raise RuntimeError('PSS_TARGET_NOT_LIVE')
        start=time.perf_counter_ns(); before=self.count(); snapshot=H(); marker=H(); rows=[]
        try:
            self._ok(self.k.PssCaptureSnapshot(self.handle,0x3c,0,C.byref(snapshot)),'PssCaptureSnapshot')
            self.snapshots.append(snapshot.value)
            self._ok(self.k.PssWalkMarkerCreate(None,C.byref(marker)),'PssWalkMarkerCreate')
            self.markers.append(marker.value)
            while True:
                entry=Entry()
                code=self.k.PssWalkSnapshot(snapshot,2,marker,C.byref(entry),C.sizeof(entry))
                if code==259: break  # ERROR_NO_MORE_ITEMS
                self._ok(code,'PssWalkSnapshot')
                if len(rows)>=65536 or time.perf_counter_ns()-start>15_000_000_000:
                    raise RuntimeError('PSS_WALK_BUDGET')
                typ=self._wide(entry.type_name,entry.type_length) if entry.flags&1 else None
                # Names may contain private namespaces. Keep only a digest.
                name=self._wide(entry.name,entry.name_length) if entry.flags&2 else None
                row={'handle':int(entry.handle or 0),'flags':entry.flags,'type':typ,
                     'object_type':entry.object_type if entry.flags&1 else None,
                     'name_sha256':hashlib.sha256(name.encode()).hexdigest() if name else None}
                if entry.flags&8 and entry.object_type==2:
                    t=entry.specific.thread
                    row['thread']={'pid':t.pid,'tid':t.tid,'exit_status':t.exit_status,
                        'start_address':hex(t.start or 0),'priority':t.priority,'base_priority':t.base_priority}
                rows.append(row)
        finally:
            self._free_snapshots()
        after=self.count()
        return {'identity':self.identity,'capture_flags':0x3c,'access_mask':self.access,
                'started_perf_ns':start,'duration_ms':(time.perf_counter_ns()-start)/1e6,
                'before_handle_count':before,'after_handle_count':after,'entries':rows,
                'type_counts':dict(Counter(r['type'] or '<unavailable>' for r in rows)),
                'snapshot_and_marker_freed':not self.snapshots and not self.markers,
                'formal_acceptance':False}

    def _free_snapshots(self):
        errors=[]
        for marker in self.markers[:]:
            code=self.k.PssWalkMarkerFree(marker)
            if code: errors.append(['PssWalkMarkerFree',code])
            else: self.markers.remove(marker)
        for snapshot in self.snapshots[:]:
            code=self.k.PssFreeSnapshot(self.k.GetCurrentProcess(),snapshot)
            if code: errors.append(['PssFreeSnapshot',code])
            else: self.snapshots.remove(snapshot)
        if errors: raise RuntimeError(json.dumps({'cleanup_errors':errors}))

    def close(self):
        self._free_snapshots()
        if self.handle:
            if not self.k.CloseHandle(self.handle): raise C.WinError(C.get_last_error())
            self.handle=None


def self_test():
    k=C.WinDLL('kernel32',use_last_error=True)
    k.GetCurrentProcess.restype=H; k.GetProcessTimes.argtypes=[H]+[C.POINTER(FT)]*4
    times=[FT() for _ in range(4)]
    if not k.GetProcessTimes(k.GetCurrentProcess(),*(C.byref(t) for t in times)):
        raise C.WinError(C.get_last_error())
    created=(times[0].high<<32)|times[0].low
    probe=HandleProbe(os.getpid(),created,sys.executable)
    k.CreateEventW.argtypes=[H,C.c_int32,C.c_int32,C.c_wchar_p]; k.CreateEventW.restype=H
    event=k.CreateEventW(None,True,False,None)
    if not event: raise C.WinError(C.get_last_error())
    try:
        result=probe.snapshot()
        rows=[r for r in result['entries'] if r['handle']==event]
        print(json.dumps({'sentinel':event,'matched':rows,'type_counts':result['type_counts']}),flush=True)
        assert len(rows)==1 and rows[0]['type']=='Event' and rows[0]['object_type']==4
        print(json.dumps({'self_test':True,'sentinel_event_verified':True,'snapshot':result}),flush=True)
    finally:
        if not probe.k.CloseHandle(event): raise C.WinError(C.get_last_error())
        probe.close()


if __name__=='__main__':
    self_test()
