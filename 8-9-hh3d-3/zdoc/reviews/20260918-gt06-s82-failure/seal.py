"""Seal preservation packet by exact bytes. Exclusive output, no acceptance."""
from pathlib import Path
import datetime
import hashlib
import json

OUT = Path(__file__).resolve().parent
EXCLUDE = {'package-manifest.json', 'package-manifest.sha256'}
for name in EXCLUDE:
    assert not (OUT / name).exists(), 'Already sealed: ' + name
assert json.loads((OUT / 'verification.json').read_bytes())['status'] == 'PRESERVATION_VERIFIED'
assert json.loads((OUT / 'verification-recheck.json').read_bytes())['status'] == 'PRESERVATION_RECHECK_VERIFIED'
files = []
for path in sorted(OUT.rglob('*')):
    assert not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400
    if path.is_file() and path.relative_to(OUT).as_posix() not in EXCLUDE:
        before = path.stat()
        data = path.read_bytes()
        assert (before.st_size, before.st_mtime_ns) == (path.stat().st_size, path.stat().st_mtime_ns)
        files.append(dict(path=path.relative_to(OUT).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
manifest = dict(schema='HH-GT06-S82-FAILURE-PACKET-1', created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                authority=0, formal_acceptance=False, campaign_id='gt06-s81-campaign-01',
                status='FAILED_PARTIAL_PRESERVATION_ONLY',
                hash_domain='SHA256 of exact manifest bytes. Enumerates every packet file except package-manifest.json and package-manifest.sha256; no self-reference.',
                files=files)
data = (json.dumps(manifest, indent=2) + '\n').encode()
with (OUT / 'package-manifest.json').open('xb') as stream:
    stream.write(data)
digest = hashlib.sha256(data).hexdigest()
with (OUT / 'package-manifest.sha256').open('xb') as stream:
    stream.write((digest + '\n').encode())
for row in files:
    raw = (OUT / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
assert {p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file()} == {r['path'] for r in files} | EXCLUDE
print(json.dumps(dict(packet_sha256=digest, sealed_files=len(files), total_packet_files=len(files) + 2,
                     enumerated_bytes=sum(r['bytes'] for r in files), formal_acceptance=False)))
