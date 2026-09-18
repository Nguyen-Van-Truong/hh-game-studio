"""Continue the read-only collector after its documented scene-assumption error.

No original raw or previously written evidence file is replaced. This script
uses the original collector functions/remaining checks, changing only its
incorrect initial-scene equality assertion to an explicit comparison record.
"""
from pathlib import Path
original = Path(__file__).with_name('preserve.py').read_text(encoding='utf-8')
exec(compile(original.split('started = utc()', 1)[0], 'preserve.py:definitions', 'exec'))
started = utc()
scheduler = read(OUT / 'observations/scheduler-terminal.stdout.txt')
processes = read(OUT / 'observations/processes.stdout.txt')
raw = read(OUT / 'raw-locator-hashmaps.json')['files']
copies = read(OUT / 'preserved-byte-manifest.json')['files']
scene = ATTEMPT / 'project/scenes/fixture.tscn'
relative = scene.relative_to(CAMPAIGN).as_posix()
expected = next(r for r in raw['campaign'] if r['path'] == relative)
data = scene.read_bytes()
assert len(data) == expected['bytes'] and hashlib.sha256(data).hexdigest() == expected['sha256']
destination = 'raw/campaign/' + relative
write(destination, data)
supplement = {'path': destination, 'raw_root': 'campaign', 'raw_path': relative,
              'bytes': len(data), 'sha256': expected['sha256']}
write('preserved-byte-manifest-supplement.json', {'created_utc': utc(),
    'scope': 'Exact terminal mutable fixture scene; original selected-copy manifest remains unchanged.',
    'files': [supplement]})
copies = copies + [supplement]
rest = 'campaign = read(CAMPAIGN' + original.split('campaign = read(CAMPAIGN', 1)[1]
old = "assert all(r['expected_sha256'] == r['actual_sha256'] for r in project_rows)"
new = "for r in project_rows:\n    r['matches_initial'] = r['expected_sha256'] == r['actual_sha256']\n    r['scope'] = 'mutable benchmark fixture scene' if r['path'] == 'scenes/fixture.tscn' else 'initial project file comparison'"
assert rest.count(old) == 1
rest = rest.replace(old, new).replace("'immutable_project_files': project_rows", "'initial_project_files_comparison': project_rows")
exec(compile(rest, 'preserve.py:continued-with-disclosed-scene-comparison', 'exec'))
