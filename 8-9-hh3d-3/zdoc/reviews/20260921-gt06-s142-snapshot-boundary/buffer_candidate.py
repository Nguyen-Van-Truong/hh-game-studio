"""Exact-method candidate microprobe, scoped to copied history; never acceptance."""
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import sys
import textwrap
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from snapshot_probe import BASE, HH3D, SOURCE, FREEZE, sha, write
from snapshot_contention import BoundedDigest, SHA512

OUT = HH3D/"studio/.local/reviews/gt06-s142-buffer-candidate-01"


def main():
    freeze = json.loads(FREEZE.read_bytes())
    assert all(sha(HH3D/n) == h for n,h in freeze['files'].items())
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(SOURCE, OUT/'commands.jsonl')
    sys.path.insert(0, str(HH3D))
    from studio.host.replay import verified_journal as module
    original = module.VerifiedJournal._snapshot
    source = textwrap.dedent(inspect.getsource(original))
    assert source.count('min(65_536,') == 1
    candidate = source.replace('min(65_536,', 'min(1_048_576,')
    namespace = {}
    exec(compile(candidate, '<S142-generated-snapshot-candidate>', 'exec'), module.__dict__, namespace)
    journal = module.VerifiedJournal(OUT/'commands.jsonl')
    rows = []
    try:
        for contended in (False, True):
            stop, ready = threading.Event(), threading.Event()
            counter = [0]
            def compete():
                limit = time.monotonic()+60
                ready.set()
                while not stop.is_set() and time.monotonic()<limit:
                    for _ in range(1000):
                        counter[0] += 1
            worker = threading.Thread(target=compete, name='S142-buffer-competitor') if contended else None
            try:
                if worker:
                    worker.start()
                    assert ready.wait(2)
                for trial in range(3):
                    for tuned in ((False,True) if trial%2==0 else (True,False)):
                        before_progress = counter[0]
                        with patch.object(module,'hashlib',SimpleNamespace(sha512=BoundedDigest if tuned else SHA512)):
                            with journal._writer_lock():
                                start, cpu = time.perf_counter_ns(),time.thread_time_ns()
                                value=(namespace['_snapshot'] if tuned else original)(journal,synchronize=True)
                                wall=(time.perf_counter_ns()-start)/1e6
                                cpu_ms=(time.thread_time_ns()-cpu)/1e6
                                assert journal._matches(*value)
                        assert not worker or worker.is_alive()
                        rows.append({'contended':contended,'candidate':tuned,'trial':trial,'wall_ms':wall,
                                     'cpu_ms':cpu_ms,'bytes':value[1],'matches':True,
                                     'competing_progress':counter[0]-before_progress})
            finally:
                stop.set()
                if worker:
                    worker.join(2)
                    assert not worker.is_alive()
    finally:
        journal.close()
    assert sha(SOURCE)==sha(OUT/'commands.jsonl')
    assert all(sha(HH3D/n)==h for n,h in freeze['files'].items())
    result={'authority':0,'formal_acceptance':False,'engine_runs':0,'rows':rows,
            'source_unchanged':True,'history_unchanged':True,'history_sha256':sha(SOURCE),
            'helper_sha256':sha(Path(__file__)),'original_method_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'candidate_method_sha256':hashlib.sha256(candidate.encode()).hexdigest(),
            'owned_threads_stopped':True,'journal_closed':journal._index_store is None,
            'limits':'Synthetic competitor, copied history and generated method: no S141 root-cause/formal/RSS acceptance. All bytes, identity, bounds, parsing fallback and fsync retained.'}
    write(OUT/'result.json',result)
    for row in rows:print(json.dumps(row))


if __name__=='__main__':main()
