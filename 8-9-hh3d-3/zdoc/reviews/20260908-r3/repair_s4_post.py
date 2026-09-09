from pathlib import Path
import hashlib, os, tempfile

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
expected = '196ea12541f9d91900f9359a903191ad8182d2222bd26dae5545b1ebfe9c246f'
b = P.read_bytes()
if hashlib.sha256(b).hexdigest() != expected:
    raise SystemExit('S4 source changed; reconcile before repair')
s = b.decode('utf-8')
old = '\n+là acceptance closure. Limits/fixtures/test IDs phải khóa trước code consumer;\n+coverage map liên kết requirement→test→artifact/hash, orphan requirement là GAP.\n+Mỗi GT có'
new = '\nlà acceptance closure. Limits/fixtures/test IDs phải khóa trước code consumer;\ncoverage map liên kết requirement→test→artifact/hash, orphan requirement là GAP.\nMỗi GT có'
s2 = s.replace(old, new)
if s2 == s:
    raise SystemExit('expected TQ00 typo not found')
fd,n = tempfile.mkstemp(prefix=P.name+'.', suffix='.tmp', dir=P.parent)
with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
    f.write(s2); f.flush(); os.fsync(f.fileno())
os.replace(n, P)
print(hashlib.sha256(P.read_bytes()).hexdigest())
