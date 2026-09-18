"""Separate read-only recheck by preserving agent, never an acceptance critic."""
from pathlib import Path
import datetime
import hashlib
import json
import os

OUT = Path(__file__).resolve().parent
load = lambda path: json.loads(path.read_bytes())


def sha(path):
    before = path.stat()
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return value.hexdigest()


inventory = load(OUT / 'raw-locator-hashmaps.json')
raw_count = 0
for kind, rows in inventory['files'].items():
    base = Path(inventory['roots'][kind])
    assert {r['path'] for r in rows} == {p.relative_to(base).as_posix() for p in base.rglob('*') if p.is_file()}
    for row in rows:
        path = base / row['path']
        assert not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400
        assert path.stat().st_size == row['bytes'] and path.stat().st_mtime_ns == row['mtime_ns']
        assert sha(path) == row['sha256']
        raw_count += 1
copy_manifest = load(OUT / 'preserved-byte-manifest.json')
copies = copy_manifest['files']
assert len({r['path'] for r in copies}) == len(copies)
assert {r['path'] for r in copies} == {p.relative_to(OUT).as_posix() for p in (OUT / 'raw').rglob('*') if p.is_file()}
for row in copies:
    path = OUT / row['path']
    original = Path(inventory['roots'][row['raw_root']]) / row['raw_path']
    assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'] == sha(original)
assert len([r for r in copies if r['raw_root'] == 'supervisor']) == len(inventory['files']['supervisor']) == 12
base = Path(inventory['roots']['campaign'])
attempt = base / 'run-00-attempt-01'
mapping = load(base / 'campaign.json')['source_files']
assert mapping == load(attempt / 'source-files.json') == load(attempt / 'context.json')['source_files']
closure = hashlib.sha256(''.join(p + '\0' + mapping[p] + '\n' for p in sorted(mapping)).encode()).hexdigest()
assert closure == 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f' and len(mapping) == 51
for name, expected in mapping.items():
    assert sha(base / 'source/studio' / name) == sha(attempt / 'source/studio' / name) == expected
assert sha(base / 'benchmark-profile.json') == sha(attempt / 'benchmark-profile.json') == '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
facts = load(OUT / 'terminal-facts.json')
assert load(attempt / 'host-owner/process-exit.json') == {'pid': 4132, 'exit_code': 1}
assert not os.path.lexists(attempt / 'editor-host/process-exit.json')
assert facts['editor_actual_target_exit'] is None and facts['editor_helper_pid'] == 22376 and facts['editor_helper_exit_code'] == 2
assert facts['child_terminal_cleanup'] == load(attempt / 'child-terminal-cleanup.json')
for slot in facts['fixed_attempt_slots']:
    assert not os.path.lexists(base / slot['path'] / 'stop-request.json')
assert not os.path.lexists(Path(inventory['roots']['supervisor']) / 'stop-request.json')
assert not list(base.rglob('stop-request.json')) and not list(Path(inventory['roots']['supervisor']).rglob('stop-request.json'))
ref_count = 0
saved_hashes = set()
for index in range(16):
    capture = load(attempt / f'batch-capture-{index:02d}.json')
    for name, ref in capture.items():
        if name == 'index':
            continue
        path = attempt / ref['file']
        assert path.resolve().is_relative_to(attempt)
        assert path.stat().st_size == ref['size_bytes'] and sha(path) == ref['sha256']
        ref_count += 1
    command = load(attempt / f'command-{index:02d}.json')
    native = load(attempt / f'project/benchmark/out/batch-{index:02d}.json')
    assert len(command['commands']) == 1000 and len(native['cycles']) == 100
    assert command['cancel']['terminal_status'] == 'CANCELED' and command['cancel']['no_effect'] is True
    saved_hashes.update(c['saved_file_sha256'] for c in native['cycles'])
assert saved_hashes == {sha(attempt / 'project/scenes/fixture.tscn')}
report = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              status='PRESERVATION_RECHECK_VERIFIED', formal_acceptance=False,
              scope='Same preserving agent; byte/static recheck only, no independent acceptance critic or native test',
              raw_files=raw_count, exact_copies=len(copies), supervisor_files=12, source_files=51,
              source_closure_sha256=closure, batch_references=ref_count, captured_batches=16,
              complete_runs=0, raw_hashes_names_sizes_mtimes_unchanged=True,
              copies_exact=True, editor_natural_exit_still_absent=True,
              serialized_project_scene_difference_preserved=True, operator_stop_latches_absent=True)
with (OUT / 'verification-recheck.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps(report))
