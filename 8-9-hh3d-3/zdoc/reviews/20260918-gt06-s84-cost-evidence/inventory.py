"""Exclusive metadata/hash snapshot of four terminal S84 cost arms; no runtime imports."""
from pathlib import Path
import datetime, hashlib, json, re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ARMS = ['original', 'sham', 'compact', 'compact-growth']

def plain(path):
    for p in [path, *path.parents]:
        assert not p.is_symlink() and not getattr(p.lstat(), 'st_file_attributes', 0) & 0x400, str(p)

def exclusion(name):
    if any(p.lower() in {'.godot','__pycache__','appdata','localappdata'} for p in Path(name).parts):
        return 'Generated cache or per-process settings: metadata only; not hashed/copied'
    if re.search(r'(?i)(?:^|/)(?:\.env(?:\..*)?|.*(?:token|secret|credential|password).*|.*\.(?:pem|pfx|p12|key|keystore))$', name):
        return 'Sensitive filename class: metadata only; not hashed/copied'
    return None

def inventory(base):
    plain(base)
    rows=[]
    for p in sorted(base.rglob('*')):
        plain(p)
        if not p.is_file(): continue
        before=p.stat(); relative=p.relative_to(base).as_posix()
        row=dict(path=relative,bytes=before.st_size,mtime_ns=before.st_mtime_ns)
        reason=exclusion(relative)
        if reason: row.update(excluded=reason,sha256=None)
        else:
            h=hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda:f.read(1048576),b''): h.update(block)
            row['sha256']=h.hexdigest()
        after=p.stat()
        assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns), str(p)
        rows.append(row)
    return rows

def collect():
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    roots={}
    for arm in ARMS:
        roots[arm+'/raw']=ROOT/'studio/.local/reviews'/('gt06-s84-cost-'+arm+'-01')
        roots[arm+'/outer']=ROOT/'zdoc/reviews/20260918-gt06-s84-probe-cost'/(arm+'-01')
    files={key:inventory(base) for key,base in roots.items()}
    result=dict(schema='S84_COST_RAW_INVENTORY_1',authority=0,formal_acceptance=False,started_utc=started,
                finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),roots={k:str(v) for k,v in roots.items()},files=files)
    with (OUT/'raw-inventory.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(started_utc=started,finished_utc=result['finished_utc'],hashed_files=sum(sum(r['sha256'] is not None for r in rows) for rows in files.values()),excluded_files=sum(sum(r['sha256'] is None for r in rows) for rows in files.values()),hashed_bytes=sum(r['bytes'] for rows in files.values() for r in rows if r['sha256']))))

if __name__=='__main__': collect()
