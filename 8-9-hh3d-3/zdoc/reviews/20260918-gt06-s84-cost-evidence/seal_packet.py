"""Small packet-only byte seal during separate long diagnostic; no raw reread."""
from pathlib import Path
import datetime,hashlib,json
OUT=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_bytes())

def sha(p):
    assert not p.is_symlink() and not getattr(p.lstat(),'st_file_attributes',0)&0x400
    before=p.stat();data=p.read_bytes();after=p.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return hashlib.sha256(data).hexdigest()

excluded={'package-manifest.json','package-manifest.sha256'}
assert all(not (OUT/n).exists() for n in excluded)
copy_rows=load(OUT/'copy-map.json')['files']
assert {r['path'] for r in copy_rows}=={p.relative_to(OUT).as_posix() for p in (OUT/'raw').rglob('*') if p.is_file()}
for row in copy_rows:assert sha(OUT/row['path'])==row['sha256'] and (OUT/row['path']).stat().st_size==row['bytes']
for row in load(OUT/'current-helper-comparison.json')['current_files']:assert sha(OUT/row['packet_path'])==row['sha256']
assert len(load(OUT/'offline-source-check.json')['current_runtime_files'])==51
rows=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()]
manifest=dict(schema='S84_COST_EVIDENCE_PACKET_1',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),authority=0,formal_acceptance=False,
    hash_domain='Exact bytes; every packet file except manifest and sidecar',files=rows)
data=(json.dumps(manifest,indent=2)+'\n').encode()
with (OUT/'package-manifest.json').open('xb') as f:f.write(data)
value=hashlib.sha256(data).hexdigest()
with (OUT/'package-manifest.sha256').open('xb') as f:f.write((value+'\n').encode())
assert sha(OUT/'package-manifest.json')==value
assert {r['path'] for r in rows}|excluded=={p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file()}
print(json.dumps(dict(status='PACKET_COPIES_VERIFIED_AND_SEALED',formal_acceptance=False,packet_sha256=value,exact_copies=len(copy_rows),sealed_files=len(rows),total_files=len(rows)+2)))
