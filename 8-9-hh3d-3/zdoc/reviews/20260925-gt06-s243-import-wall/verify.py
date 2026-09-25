from pathlib import Path
import hashlib,json,zipfile
base=Path(__file__).parent
m=json.loads((base/'manifest.json').read_text())
raw=json.loads((base/'raw-manifest.json').read_text())
assert hashlib.sha256((base/'raw-manifest.json').read_bytes()).hexdigest()==m['raw_manifest_sha256']
archive=base.parents[2]/'studio/.local/archives/gt06-s243-formal-01-s244-import-wall.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==m['archive_sha256']
with zipfile.ZipFile(archive) as z:
 names=sorted(z.namelist()); expected=sorted(e['path'] for e in raw['entries'])
 assert names==expected
 for e in raw['entries']:
  b=z.read(e['path']); assert len(b)==e['size_bytes']; assert hashlib.sha256(b).hexdigest()==e['sha256']
assert m['authority']==0 and m['formal_acceptance'] is False
print(json.dumps({'verified':True,'raw_files':len(raw['entries']),'archive_members':len(names),'authority':m['authority'],'formal_acceptance':m['formal_acceptance']}))
