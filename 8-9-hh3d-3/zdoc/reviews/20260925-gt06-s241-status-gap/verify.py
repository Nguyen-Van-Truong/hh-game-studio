from pathlib import Path
import hashlib,json,zipfile,sys
here=Path(__file__).resolve().parent
manifest=json.loads((here/'manifest.json').read_bytes()); raw=json.loads((here/'raw-manifest.json').read_bytes()); archive=Path('8-9-hh3d-3/studio/.local/archives/gt06-s241-formal-01-s242-status-gap.zip')
def fail(x): raise SystemExit(x)
if hashlib.sha256((here/'raw-manifest.json').read_bytes()).hexdigest()!=manifest['raw_manifest_sha256']: fail('RAW_MANIFEST_HASH')
if hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['archive_sha256']: fail('ARCHIVE_HASH')
with zipfile.ZipFile(archive) as z:
 infos={i.filename:i for i in z.infolist()}
 if len(infos)!=raw['archive_members'] or set(infos)!={x['path'] for x in raw['entries']}: fail('ARCHIVE_MEMBERS')
 for e in raw['entries']:
  b=z.read(e['path'])
  if len(b)!=e['size_bytes'] or hashlib.sha256(b).hexdigest()!=e['sha256']: fail('RAW_HASH:'+e['path'])
print(json.dumps({'verified':True,'raw_files':raw['raw_files'],'archive_members':raw['archive_members'],'authority':0,'formal_acceptance':False}))
