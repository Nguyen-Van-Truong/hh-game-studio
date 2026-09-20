"""One cached, read-only source comparison after the live measurement ends.

The output is an inventory, not acceptance or dependency-completeness proof.
Never changes an old manifest, runtime source, gate or source binding.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
STUDIO=ROOT/'studio'
MAPS={
 'gt05_accepted143':ROOT/'zdoc/reviews/20260917-gt05-s63-audit/manifest.json',
 's79_backend174':STUDIO/'.local/reviews/gt06-s79-http-complete-01/source-files.json',
 's69_managed159':STUDIO/'.local/reviews/gt06-s69-managed-replay-01/source-files.json',
}
def sha(raw): return hashlib.sha256(raw).hexdigest()
def plain(path):
    for parent in (path,*path.parents):
        info=parent.lstat()
        assert not parent.is_symlink() and not getattr(info,'st_file_attributes',0)&0x400,'reparse'
    assert path.is_file() and path.stat().st_size<=8*1024*1024,'file size'
    return path.read_bytes()

def main():
    terminal=json.loads(plain(STUDIO/'.local/reviews/gt06-s129-host-memory-01/result.json'))
    assert terminal['helper_exit'] is not None and terminal['job']['closed']
    assert terminal['job']['zero_observed'] and terminal['handle']['closed']
    current={}; rows={}
    for label,path in MAPS.items():
        raw=plain(path); data=json.loads(raw)
        original=data['source_files'] if label.startswith('gt05') else data
        assert isinstance(original,dict) and original
        inherited={}; changed=[]; missing=[]
        for name,expected in original.items():
            prefix='8-9-hh3d-3/studio/'
            relative=name[len(prefix):] if name.startswith(prefix) else name
            parts=PurePosixPath(relative)
            assert not parts.is_absolute() and '\\' not in relative and '..' not in parts.parts
            assert str(parts)==relative and ':' not in relative
            assert relative.casefold() not in {k.casefold() for k in inherited}
            inherited[relative]=expected
            if relative not in current:
                p=STUDIO/relative
                current[relative]=sha(plain(p)) if p.exists() else None
            actual=current[relative]
            if actual is None: missing.append(relative)
            elif actual!=expected: changed.append({'path':relative,'historical':expected,'current':actual})
        rows[label]={'manifest':path.relative_to(ROOT).as_posix(),'manifest_sha256':sha(raw),
                     'declared_count':len(inherited),'changed':changed,'missing':missing,
                     'unchanged_count':len(inherited)-len(changed)-len(missing)}
    result={'schema':'S132.dependency-delta.1','authority':0,'formal_acceptance':False,
            'scope':'Inherited maps only; not current dependency completeness','maps':rows,
            'current_union':dict(sorted(current.items()))}
    with (BASE/'dependency-delta-01.json').open('xb') as f:
        f.write((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps({'maps':{k:{'declared':v['declared_count'],'changed':[x['path'] for x in v['changed']],
                     'missing':v['missing']} for k,v in rows.items()},'unique_files':len(current)}))

if __name__=='__main__': main()
