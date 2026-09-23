"""Seal S197 after the CDB command boundary failed to produce terminal capture."""
import hashlib, json, os, zipfile
from pathlib import Path
raw=Path(os.environ['S197_RAW']); archive=Path(os.environ['S197_ARCHIVE']); packet=Path(os.environ['S197_PACKET']); packet.mkdir(parents=True,exist_ok=True); archive.parent.mkdir(parents=True,exist_ok=True)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    data=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();
    with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    return digest(p)
files=[{'path':p.relative_to(raw).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(raw.rglob('*')) if p.is_file() and p.name!='raw-manifest.json']
manifest_sha=write(raw/'raw-manifest.json',{'schema':'HH-GT06-S197-RAW-MANIFEST-1','run_id':'gt06-s197-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'terminal':'harness_boundary_failure','files':files})
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in sorted(raw.rglob('*')):
        if p.is_file():
            i=zipfile.ZipInfo(p.relative_to(raw).as_posix()); i.date_time=(2026,9,24,0,0,0); i.compress_type=zipfile.ZIP_DEFLATED; z.writestr(i,p.read_bytes())
archive_sha=digest(archive)
cdb=(raw/'cdb.stdout.txt').read_text(errors='replace')
target=(raw/'editor-host'/'stdout.txt').read_text(errors='replace')
result={'schema':'HH-GT06-S197-ANALYSIS-1','run_id':'gt06-s197-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'cdb_attached':'S197_CDB_ATTACHED' in cdb,'handle_snapshot':'S197_HANDLE_SNAPSHOT_DONE' in cdb,'htrace_enabled':'S197_HTRACE_ENABLED' in cdb,'handle_table_summary':'256 Handles' in cdb,'target_ready':'HH_S197_READY' in target,'target_complete':'HH_S197_COMPLETE' in target,'target_terminal_exit':'UNKNOWN','driver_exit':1,'cdb_exit':'UNKNOWN_AFTER_DRIVER_DEADLINE','failure':'S197_EDITOR_DEADLINE_CDB_REMAINED_AT_NTTERMINATEPROCESS_BOUNDARY','decision':'CDB attach/snapshot capability proven; terminal command requires explicit detach/continue boundary; no attribution/root-cause or GT06 acceptance claim','raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha}
analysis_sha=write(packet/'analysis.json',result)
(packet/'README.md').write_text('# S197 CDB handle snapshot\n\nCDB attached to the verified Godot target and captured a `!handle 0 7` snapshot with 256 handles and enabled `!htrace`. The target emitted its completion marker, but the command script stopped at the process termination boundary, so the host driver could not capture an independently verified target exit before its bounded deadline. This is a harness terminal failure; preserve it and use a fresh ID with an explicit detach/continue command. The packet is diagnostic-only and does not change GT06.\n',encoding='utf-8')
readme_sha=digest(packet/'README.md'); seal_sha=write(packet/'terminal-seal.json',{'schema':'HH-GT06-S197-TERMINAL-SEAL-1','run_id':'gt06-s197-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'terminal':'failed_harness_boundary','raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'verified_files':len(files)+1,'cdb_attached':True,'handle_snapshot':True,'htrace_enabled':True,'target_exit':'UNKNOWN','job_cleanup':'UNKNOWN_FROM_DRIVER_PATH','formal_gate_unchanged':True})
write(packet/'package-manifest.json',{'schema':'HH-GT06-S197-PACKAGE-MANIFEST-1','run_id':'gt06-s197-cdb-handle-snapshot-01','authority':0,'formal_acceptance':False,'packet':'zdoc/reviews/20260924-gt06-s197-cdb-handle-snapshot','README.md':readme_sha,'analysis.json':analysis_sha,'terminal-seal.json':seal_sha,'raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'decision':'retain failure; fresh ID required for terminal detach/continue repair'})
print(json.dumps({'raw_manifest_sha256':manifest_sha,'archive_sha256':archive_sha,'files':len(files)+1},indent=2))
