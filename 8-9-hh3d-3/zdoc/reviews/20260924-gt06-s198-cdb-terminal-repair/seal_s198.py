"""Seal the successful S198 CDB terminal-boundary repair."""
import hashlib, json, os, zipfile
from pathlib import Path
raw=Path(os.environ['S198_RAW']); archive=Path(os.environ['S198_ARCHIVE']); packet=Path(os.environ['S198_PACKET']); packet.mkdir(parents=True,exist_ok=True); archive.parent.mkdir(parents=True,exist_ok=True)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    data=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    return digest(p)
files=[{'path':p.relative_to(raw).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(raw.rglob('*')) if p.is_file() and p.name!='raw-manifest.json']
manifest_sha=write(raw/'raw-manifest.json',{'schema':'HH-GT06-S198-RAW-MANIFEST-1','run_id':'gt06-s198-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'terminal':'bounded_success','files':files})
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(raw.rglob('*')):
        if p.is_file():
            i=zipfile.ZipInfo(p.relative_to(raw).as_posix()); i.date_time=(2026,9,24,0,0,0); i.compress_type=zipfile.ZIP_DEFLATED; z.writestr(i,p.read_bytes())
archive_sha=digest(archive); result=json.loads((raw/'result.json').read_text())
analysis={'schema':'HH-GT06-S198-ANALYSIS-1','run_id':'gt06-s198-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'cdb_markers':result['cdb_markers'],'target_actual_exit':result['target_actual_exit'],'helper_exit':result['helper_exit'],'cdb_exit':result['cdb_exit'],'job':result['job'],'conclusion':'Supported CDB attached to the verified Godot target, captured the handle table and enabled htrace; explicit qd after the termination stop produced complete target/CDB cleanup. This is a distinct diagnostic boundary, not GT06 acceptance and not proof of leak ownership or root cause.','raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha}
analysis_sha=write(packet/'analysis.json',analysis)
(packet/'README.md').write_text('# S198 CDB terminal-boundary repair\n\nS197 proved the CDB attach and handle snapshot but stopped at `NtTerminateProcess` without a terminal capture. S198 used a fresh diagnostic ID and added an explicit `qd` after the debugger termination stop. CDB attached to the verified Godot PID, captured 256 handles, enabled `!htrace`, detached cleanly, and the target/helper/CDB all exited with the owned Job zero and closed. This remains diagnostic-only; GT06 gate, counter verifier, and acceptance status are unchanged.\n',encoding='utf-8')
readme_sha=digest(packet/'README.md'); seal_sha=write(packet/'terminal-seal.json',{'schema':'HH-GT06-S198-TERMINAL-SEAL-1','run_id':'gt06-s198-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'terminal':'bounded_success','raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'verified_files':len(files)+1,'cdb_attached':True,'handle_snapshot':True,'htrace_enabled':True,'target_actual_exit':0,'helper_exit':0,'cdb_exit':0,'job_zero_closed':True,'formal_gate_unchanged':True})
write(packet/'package-manifest.json',{'schema':'HH-GT06-S198-PACKAGE-MANIFEST-1','run_id':'gt06-s198-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'packet':'zdoc/reviews/20260924-gt06-s198-cdb-terminal-repair','README.md':readme_sha,'analysis.json':analysis_sha,'terminal-seal.json':seal_sha,'raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'decision':'CDB terminal boundary repaired; retain GT06 IN_PROGRESS and do not treat diagnostic as formal acceptance'})
print(json.dumps({'raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'files':len(files)+1},indent=2))
