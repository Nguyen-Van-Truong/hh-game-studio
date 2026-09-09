from pathlib import Path
import hashlib, os, tempfile
ROOT=Path(__file__).resolve().parents[3]
P=ROOT/'zdoc/8-9-hh-world-gameplay-viet-nam-plan.txt'
old_hash='7932eb9df8d96c9abc7d457548c9890e26a5af92222f9c46684094924c061ec6'
raw=P.read_bytes()
if hashlib.sha256(raw).hexdigest()!=old_hash: raise SystemExit('S4 source changed; reconcile before repair')
s=raw.decode('utf-8')
old='\n+closure. Requirement→WP→test ID→artifact/hash phải có mapping, threshold trước\n+code consumer. Không spec nào tự giảm contract chung; orphan requirement là GAP.\n+Dependency ACCEPTED; files đúng lease;'
new='\nclosure. Requirement→WP→test ID→artifact/hash phải có mapping, threshold trước\ncode consumer. Không spec nào tự giảm contract chung; orphan requirement là GAP.\nDependency ACCEPTED; files đúng lease;'
if s.count(old)!=1: raise SystemExit(f'anchor count {s.count(old)}')
s=s.replace(old,new,1)
fd,n=tempfile.mkstemp(prefix=P.name+'.',suffix='.tmp',dir=P.parent)
with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
    f.write(s); f.flush(); os.fsync(f.fileno())
os.replace(n,P)
print(hashlib.sha256(P.read_bytes()).hexdigest())
