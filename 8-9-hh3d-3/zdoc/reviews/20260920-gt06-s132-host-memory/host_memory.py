"""Seven stock HTTP batches, no Godot, supplementary working-set/commit metrics.

This isolates command/journal/request-thread ownership from native and offline
assembly. Unchanged 1000-command mix/client budgets, five warmups, original host
10% RSS/handle/status checks; diagnostic-only, never an accepted run or dataset.
"""
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes as w
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from studio.tests.replay import benchmark_job as job
from studio.tests.replay.benchmark_commands import CommandProducer
from studio.host.replay.process_probe import ProcessProbe

RUN_ID='gt06-s129-host-memory-01'
CLOSURE='763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4'
PROFILE='0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
OUT=ROOT/'studio/.local/reviews'/RUN_ID
INNER_SECONDS=1200
OUTER_SECONDS=1230

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,code): job.require(value,code)
def write(path,data): job.write(path,data)
def utc(): return datetime.now(timezone.utc).isoformat()

def check():
    p=ROOT/'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    spec=importlib.util.spec_from_file_location('s132_support',p)
    util=importlib.util.module_from_spec(spec); spec.loader.exec_module(util)
    campaign,_,_,sources=util.load_campaign(ROOT)
    need(campaign.closure(sources)==CLOSURE,'S132_SOURCE_PIN')
    need(campaign.profile.PROFILE_SHA256==PROFILE,'S132_PROFILE_PIN')
    return campaign,sources,p

class Metrics:
    def __init__(self,probe):
        self.probe=probe
        class Memory(ctypes.Structure):
            _fields_=probe.Memory._fields_+[('private_usage',ctypes.c_size_t)]
        class System(ctypes.Structure):
            _fields_=[('length',w.DWORD),('load',w.DWORD)]+[
                (name,ctypes.c_ulonglong) for name in ('physical','available','page_total',
                'page_available','virtual_total','virtual_available','extended_available')]
        self.Memory,self.System=Memory,System
        self.p=ctypes.WinDLL('psapi',use_last_error=True)
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.p.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Memory),w.DWORD]
        self.p.GetProcessMemoryInfo.restype=w.BOOL
        self.k.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(System)]
        self.k.GlobalMemoryStatusEx.restype=w.BOOL

    def sample(self):
        p=self.probe
        need(p.handle is not None and not p.close_uncertain,'S132_PROBE_HELD')
        need(p.k.WaitForSingleObject(p.handle,0)==258,'S132_TARGET_EXITED')
        memory=self.Memory(); memory.cb=ctypes.sizeof(memory)
        system=self.System(); system.length=ctypes.sizeof(system)
        need(self.p.GetProcessMemoryInfo(p.handle,ctypes.byref(memory),memory.cb),'S132_MEMORY_API')
        need(self.k.GlobalMemoryStatusEx(ctypes.byref(system)),'S132_SYSTEM_MEMORY_API')
        return {'pid':p.pid,'process_start':p.process_start,'monotonic_ns':time.perf_counter_ns(),
            'working_set':int(memory.working_set),'private_commit':int(memory.private_usage),
            'page_faults':int(memory.page_faults),'allocated_python_blocks':sys.getallocatedblocks(),
            'system_memory_load_percent':int(system.load),'system_available_physical':int(system.available),
            'system_commit_limit':int(system.page_total),'system_commit_available':int(system.page_available)}

def screen(current,baseline,gap,index):
    for name in ('rss_bytes','held_handles'):
        need(type(current['counters'][name]['value']) is int,'CAMPAIGN_COUNTER_UNAVAILABLE')
    if index<5: return
    now,before=current['counters'],baseline['counters']
    need(now['rss_bytes']['value']*100<=before['rss_bytes']['value']*110,'CAMPAIGN_RSS_GROWTH')
    need(now['held_handles']['value']<=before['held_handles']['value'],'CAMPAIGN_RETAINED_COUNTER_GROWTH')
    need(gap<=2000,'CAMPAIGN_STATUS_GAP')

def close_producer(producer,campaign,sources):
    error=None
    if producer is not None:
        try: producer.close()
        except BaseException as failure: error=getattr(failure,'code',type(failure).__name__)
    observer=getattr(producer,'observer',None)
    journal=getattr(producer,'journal',None)
    cleanup={'producer_closed':producer is None or producer.closed,
        'source_unchanged':campaign.source_files()==sources,
        'threads_alive':[t.name for t in threading.enumerate() if t is not threading.current_thread()],
        'probe_released':observer is None or observer.probe.handle is None,
        'journal_closed':journal is None or journal._cache_closed,'cleanup_error':error}
    write(OUT/'child-cleanup.json',cleanup)
    if producer is not None:
        write(OUT/'http-phases-final.json',producer.phase_snapshot())
    return cleanup

def child():
    campaign,sources,_=check()
    producer=None; baseline=None; completed=0; rows=[]; primary=None
    began=time.monotonic()
    def stop():
        need(not (OUT/'stop-request.json').exists(),'BENCHMARK_STOPPED')
        need(time.monotonic()-began<INNER_SECONDS,'S132_CHILD_LIMIT')
    try:
        stop()
        producer=CommandProducer(OUT/'commands',RUN_ID)
        metrics=Metrics(producer.observer.probe)
        for index in range(7):
            stop()
            start=metrics.sample()
            report=producer.run_batch(index)
            gap=report['max_status_gap_ms']
            lookup_attempts=sum(len(r.get('lookup_attempts',())) for r in report['commands'])
            live=metrics.sample()
            write(OUT/f'command-{index:02d}.json',report)
            written=metrics.sample()
            del report
            gc.collect()
            current=producer._observe()
            released=metrics.sample()
            recorder=producer._phase_recorder
            with recorder._lock:
                cardinality={'recorder_events':len(recorder._events),'recorder_active':len(recorder._active)}
            row=dict(batch=index,start=start,report_live=live,after_write_report_held=written,released=released,
                original_host_observation=current,lookup_attempts=lookup_attempts,
                max_status_gap_ms=gap,cardinality=cardinality)
            write(OUT/f'memory-{index:02d}.json',row)
            rows.append(row); completed+=1
            print(json.dumps({'batch':index,'complete':True,'rss':current['counters']['rss_bytes']['value'],
                'private_commit':released['private_commit'],'gap_ms':gap}),flush=True)
            screen(current,baseline,gap,index)
            if index==4: baseline=current
        disposition='SEVEN_HOST_BATCHES_COMPLETED'
    except BaseException as error:
        primary=error
        if producer is None: producer=getattr(error,'cleanup_owner',None)
        disposition='FAILED'
        partial=getattr(error,'report',None)
        if partial is not None: write(OUT/'partial-command.json',partial)
        write(OUT/'failure.json',{'code':getattr(error,'code',type(error).__name__),
                                'completed_batches':completed,'formal_acceptance':False})
    finally:
        cleanup=close_producer(producer,campaign,sources)
        clean=(cleanup['source_unchanged'] and cleanup['producer_closed'] and cleanup['probe_released']
               and cleanup['journal_closed'] and not cleanup['threads_alive'] and cleanup['cleanup_error'] is None)
        if not clean:
            disposition='FAILED'
            primary=primary or RuntimeError('S132_CLEANUP_GAP')
    write(OUT/'summary.json',{'schema':'S132.host-memory.1','disposition':disposition,
        'completed_batches':completed,'ended_utc':utc(),'elapsed_seconds':time.monotonic()-began,
        'source_closure':CLOSURE,'profile_sha256':PROFILE,'engine_launched':False,'formal_acceptance':False,
        'eligible_for_dataset':False,'limits':'Host-only, no native/ACK/idle/assembly; supplementary metrics do not replace RSS gate',
        'rows':rows,'error_code':getattr(primary,'code',type(primary).__name__) if primary else None})
    return 1 if primary else 0

def launch():
    campaign,sources,support=check()
    OUT.mkdir(exist_ok=False)
    pins={'studio/'+p:h for p,h in sources.items()}
    pins[Path(__file__).relative_to(ROOT).as_posix()]=sha(__file__)
    pins[support.relative_to(ROOT).as_posix()]=sha(support)
    write(OUT/'freeze.json',{'source_files':pins,'runtime_closure':CLOSURE,'profile_sha256':PROFILE,
        'started_utc':utc(),'formal_acceptance':False,'engine_launched':False})
    owner=None; captured=None; errors=[]; began=time.monotonic()
    try:
        owner=job.BenchmarkProcess([sys.executable,'-B',str(Path(__file__).resolve()),'--child'],
            cwd=OUT,output=OUT/'owner',source_root=ROOT,source_files=pins,
            binary_sha256=sha(sys.executable),campaign_host=False)
        while owner.tick(stop=(OUT/'stop-request.json').exists()) is None:
            need(time.monotonic()-began<OUTER_SECONDS,'S132_OUTER_LIMIT')
            time.sleep(.1)
        captured=owner.finish()
        job.verify_capture(OUT/'owner',sha(OUT/'owner/capture.json'),source_root=ROOT,
            expected_source_files=pins,expected_binary_sha256=sha(sys.executable))
    except BaseException as error:
        if owner is None: owner=getattr(error,'cleanup_owner',None)
        errors.append(getattr(error,'code',type(error).__name__))
    finally:
        if owner is not None:
            try: owner.close()
            except BaseException as error: errors.append(getattr(error,'code',type(error).__name__))
        write(OUT/'result.json',{'ended_utc':utc(),'captured_success':captured is not None,'errors':errors,
            'helper_pid':owner.process.pid if owner and owner.process else None,
            'helper_exit':owner.process.returncode if owner and owner.process else None,
            'job':owner.job.snapshot() if owner and owner.job else None,
            'handle':owner.process_handle_snapshot() if owner else None,'formal_acceptance':False})
    return 0 if captured is not None and not errors else 1

if __name__=='__main__':
    if sys.argv[1:]==['--check']:
        campaign,sources,_=check()
        with ProcessProbe(os.getpid(),Path(sys.executable)) as probe:
            metrics=Metrics(probe).sample()
        print(json.dumps({'checked':True,'closure':CLOSURE,'source_count':len(sources),
            'native_metric_fields':list(metrics),'probe_closed':True,'engine_launched':False,'http_launched':False}))
    elif sys.argv[1:]==['--child']: raise SystemExit(child())
    elif sys.argv[1:]==['--launch']: raise SystemExit(launch())
    else: raise SystemExit('Use --check or --launch')
