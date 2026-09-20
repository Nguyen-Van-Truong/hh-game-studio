"""Offline allocation diagnostic on retained S131 bytes; no engines or HTTP.

Repeats six captured assemblies three times, releases each transient graph and
records tracemalloc current/peak plus process working set/private commit. This
cannot reproduce the coupled workload or convert failed samples into acceptance.
"""
import ctypes
from ctypes import wintypes as w
import gc
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import tracemalloc

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from studio.tests.replay import benchmark_job as job
from studio.tests.replay.benchmark_assembly import read_artifact, assemble_sample
from studio.host.replay.process_probe import ProcessProbe

PACKET=ROOT/'zdoc/reviews/20260920-gt06-s131-rss-failure'
EXPECTED_MANIFEST='2bab12d6417a1b9cbf404f0fb786bacd2d0817e306b4d7fbb47a595d8c2d9ead'
OUT=BASE/'memory-replay-untraced-01'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source_map():
    helper=ROOT/'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    spec=importlib.util.spec_from_file_location('s131_support',helper)
    util=importlib.util.module_from_spec(spec); spec.loader.exec_module(util)
    campaign,_,_,source=util.load_campaign(ROOT)
    return campaign,source

def child():
    campaign,sources=source_map()
    assert sha(PACKET/'manifest.json')==EXPECTED_MANIFEST
    root=PACKET/'raw/attempt'
    closure=campaign.closure(sources)
    probe=ProcessProbe(os.getpid(),Path(sys.executable))
    class Memory(ctypes.Structure):
        _fields_=probe.Memory._fields_+[('private_usage',ctypes.c_size_t)]
    api=ctypes.WinDLL('psapi',use_last_error=True).GetProcessMemoryInfo
    api.argtypes=[w.HANDLE,ctypes.POINTER(Memory),w.DWORD]; api.restype=w.BOOL
    rows=[]
    def measure(pass_index,index,phase):
        memory=Memory(); memory.cb=ctypes.sizeof(memory)
        assert api(probe.handle,ctypes.byref(memory),memory.cb)
        current,peak=None,None
        rows.append(dict(pass_index=pass_index,batch=index,phase=phase,
            working_set=int(memory.working_set),private_commit=int(memory.private_usage),
            page_faults=int(memory.page_faults),traced_current=current,traced_peak=peak,
            monotonic_ns=time.perf_counter_ns()))
    started=time.monotonic()
    references=[]
    for index in range(6):
        refs=json.loads((root/f'batch-capture-{index:02d}.json').read_bytes())
        references.append(refs)
    gc.collect()
    # Tracemalloc disabled in this controlled comparison arm.
    try:
        measure(-1,-1,'initial')
        for pass_index in range(3):
            for index,refs in enumerate(references):
                assert time.monotonic()-started<180
                # No allocation tracking overhead in this comparison arm.
                measure(pass_index,index,'before')
                bound={name:read_artifact(root,ref) for name,ref in refs.items() if name!='index'}
                joint=json.loads(bound['joint'].raw)
                measure(pass_index,index,'bound_inputs')
                sample=assemble_sample(bound['native'],bound['command'],bound['joint'],
                    run_id=joint['run_id'],index=index,processes=joint['processes'],
                    source_closure_sha256=joint['source_closure_sha256'],
                    barrier_receipt=joint['barrier_receipt'],ack=bound['ack'],ready=bound['ready'],start=bound['start'])
                expected=json.loads((root/f'sample-preview-{index:02d}.json').read_bytes())
                assert sample==expected
                measure(pass_index,index,'assembled')
                del bound,joint,sample,expected
                gc.collect()
                measure(pass_index,index,'released')
        job.write(OUT/'allocation-rows.json',dict(rows=rows,source_files=sources,source_closure=closure,
            manifest_sha256=EXPECTED_MANIFEST,engine_launched=False,http_launched=False,
            formal_acceptance=False,eligible_for_dataset=False,
            limitations='offline assembly without tracemalloc; not original host journal/thread/residency or leak proof'))
    finally:
        # No trace tracker to stop in this arm.
        pass
        probe.close()
    job.write(OUT/'probe-cleanup.json',dict(handle_released=probe.handle is None,
        close_uncertain=probe.close_uncertain,elapsed_seconds=time.monotonic()-started))

def launch():
    OUT.mkdir(exist_ok=False)
    campaign,sources=source_map()
    pins={'studio/'+p:h for p,h in sources.items()}
    pins[Path(__file__).relative_to(ROOT).as_posix()]=sha(__file__)
    pins[(PACKET/'manifest.json').relative_to(ROOT).as_posix()]=EXPECTED_MANIFEST
    argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--child']
    owner=None
    try:
        owner=job.BenchmarkProcess(argv,cwd=OUT,output=OUT/'owner',source_root=ROOT,
            source_files=pins,binary_sha256=sha(sys.executable),campaign_host=False)
        end=time.monotonic()+210
        while owner.tick() is None:
            assert time.monotonic()<end
            time.sleep(.05)
        capture=owner.finish()
        job.verify_capture(OUT/'owner',sha(OUT/'owner/capture.json'),source_root=ROOT,
            expected_source_files=pins,expected_binary_sha256=sha(sys.executable))
        print(json.dumps({'actual_target_exit':capture['actual_process_exit'],'helper_exit':capture['wrapper_exit_code'],
                         'job_closed':capture['job']['closed'],'engine_launched':False}))
    except BaseException as error:
        if owner is None: owner=getattr(error,'cleanup_owner',None)
        raise
    finally:
        if owner is not None: owner.close()

if __name__=='__main__':
    if sys.argv[1:]==['--child']: child()
    elif not sys.argv[1:]: launch()
    else: raise SystemExit('No arguments, or --child')
