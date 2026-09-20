"""Sequential default Job caller regressions; run only after live measurement.

No Godot/Blender engine is dispatched by these six fixed test modules. Some
cases use bounded actual Python helper/target processes. This is regression
evidence only, never a replacement for functional engine lanes or acceptance.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
REPO=ROOT.parent
STUDIO=ROOT/'studio'
OUT=BASE/'default-callers-01'
MEASUREMENT=STUDIO/'.local/reviews/gt06-s129-host-memory-01'
LANES=(('godot','test_linux_cli_cleanup.py'),('godot','test_validation_binding.py'),
       ('godot','test_editor_owner.py'),('blender','test_export_cleanup.py'),
       ('blender','test_publication_deadline.py'),('pipeline','test_native_job.py'))

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def write(path,value):
    with path.open('xb') as stream:
        stream.write((json.dumps(value,indent=2,sort_keys=True)+'\n').encode())

def source_map():
    files=subprocess.check_output(['git','ls-files','-z','--','8-9-hh3d-3/studio'],cwd=REPO).decode().split('\0')[:-1]
    suffixes={'.py','.gd','.json','.godot','.tscn','.tres','.uid'}
    result={}
    for name in files:
        path=REPO/name
        if '.local' not in path.parts and path.suffix in suffixes:
            result[path.relative_to(ROOT).as_posix()]=sha(path)
    result[Path(__file__).relative_to(ROOT).as_posix()]=sha(__file__)
    return dict(sorted(result.items()))

def main():
    # A terminal receipt alone is not liveness proof: coordinator separately
    # verifies retained exits and owned cleanup before invoking this helper.
    assert (MEASUREMENT/'result.json').is_file(),'S132_MEASUREMENT_NOT_TERMINAL'
    terminal=json.loads((MEASUREMENT/'result.json').read_bytes())
    assert terminal['helper_exit'] is not None and terminal['job']['closed']
    assert terminal['job']['zero_observed'] and terminal['handle']['closed']
    OUT.mkdir(exist_ok=False)
    before=source_map()
    write(OUT/'source-files.json',before)
    rows=[]
    for folder,pattern in LANES:
        lane=OUT/pattern.removesuffix('.py'); lane.mkdir()
        command=[sys.executable,'-B','-W','default','-m','unittest','discover',
                 '-s',str(STUDIO/'tests'/folder),'-p',pattern,'-v']
        began=utc(); timed_out=False; actual_exit=None
        with (lane/'stdout.txt').open('xb') as stdout,(lane/'stderr.txt').open('xb') as stderr:
            try:
                completed=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,timeout=180)
                actual_exit=completed.returncode
            except subprocess.TimeoutExpired:
                timed_out=True
        stderr=(lane/'stderr.txt').read_text(encoding='utf-8',errors='replace')
        counts=re.findall(r'Ran (\d+) tests? in',stderr)
        row={'command':command,'started_utc':began,'ended_utc':utc(),
             'actual_exit':actual_exit,'timed_out':timed_out,
             'tests_run':int(counts[-1]) if counts else None,
             'skipped_count':len(re.findall(r'\.\.\. skipped ',stderr)),
             'streams':{n:sha(lane/n) for n in ('stdout.txt','stderr.txt')},
             'engine_launched':False,'formal_acceptance':False}
        write(lane/'receipt.json',row); rows.append(row)
        print(json.dumps({'lane':pattern,'exit':actual_exit,'tests':row['tests_run'],'timeout':timed_out}),flush=True)
        if timed_out or actual_exit!=0 or not row['tests_run']: break
    after=source_map()
    summary={'lanes':rows,'source_files_sha256':sha(OUT/'source-files.json'),
             'source_unchanged':before==after,'complete':len(rows)==len(LANES),
             'python_sha256':sha(sys.executable),'engine_launched':False,'formal_acceptance':False}
    write(OUT/'summary.json',summary)
    assert summary['source_unchanged'] and summary['complete']
    assert all(r['actual_exit']==0 and not r['timed_out'] and r['tests_run'] for r in rows)

if __name__=='__main__': main()
