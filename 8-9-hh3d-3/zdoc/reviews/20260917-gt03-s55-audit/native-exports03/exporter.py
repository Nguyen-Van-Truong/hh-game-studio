"""Coordinator-scheduled, bounded non-publishing native content verification.

Existing .writer/.events handles have write-capable verification access and
native verification may flush unchanged bytes. No create, append, Registry
persistence, publication, rearm, or recovery owner is invoked. Exported portable
checksums are not native ACL authority. This tool must run only with the slot.
"""
from __future__ import annotations
import argparse
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
HERE = next(path for path in Path(__file__).resolve().parents if path.name == '20260917-gt03-s55-audit')
REVIEWS = HERE.parent
SOURCE_PACKAGE = REVIEWS / '20260917-gt03-s55-source-01'
SOURCE = SOURCE_PACKAGE / 'source/studio'
CLOSURE = '3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e'


def need(value, label):
    if not value:
        raise ValueError(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    need(not path.exists(), 'refuse evidence overwrite: ' + path.name)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def freeze_check():
    manifest = read(SOURCE_PACKAGE / 'source-closure.json')
    files = {path.relative_to(SOURCE).as_posix(): sha(path.read_bytes()) for path in SOURCE.rglob('*') if path.is_file()}
    need(len(files) == 176 and files == manifest['files'] and manifest['source_closure_sha256'] == CLOSURE, 'shared source changed')
    need(sha(''.join('8-9-hh3d-3/studio/' + name + '\0' + value + '\n'
                    for name, value in sorted(files.items())).encode()) == CLOSURE, 'canonical full source closure differs')
    return files


def package_facts(package):
    need(package.parent == REVIEWS and package.name.startswith('20260917-gt03-s55-'), 'known S55 package root required')
    reference, capture, invocation = [read(package / name) for name in ('source-reference.json', 'capture.json', 'invocation.json')]
    need(reference['source_closure_sha256'] == capture['source_closure_sha256'] == CLOSURE
         and reference['file_count'] == 176 and capture['passed'] is True, 'closed same-source successful lane required')
    lane = invocation['lane']
    recovery = lane in ('recovery-publication', 'scene-cas', 'script-committed', 'script-retired', 'edit-applied', 'script-unwitnessed')
    name = 'journal-snapshot.json' if recovery or lane == 'edit' else ('reopened.json' if lane == 'stop' else 'journal.json')
    snapshot = read(package / name)
    events_name = 'recovery-events.json' if recovery else ('journal-events.json' if lane == 'edit' else 'events.json')
    return snapshot, read(package / events_name), recovery


def export_one(package, output):
    from studio.host.core.custody_registry import RegistryCustody, BASE_PATH
    from studio.host.core.custody import decode_record, binding_from, binding_value, identity_from
    from studio.host.core.private_events import PrivateEventLog
    from studio.host.core.private_store import PrivateBlobStore, StagedBlob
    from studio.host.core.safe_replace import ProtectedFileRoot
    from studio.protocol.core import canonical_bytes
    import winreg

    snapshot, events, recovery = package_facts(package)
    storage_parent = package / ('original/owned/storage' if recovery else 'owned/storage')
    files_roots = list(storage_parent.glob('hh-files-*'))
    need(len(files_roots) == 1, 'one retained selected root required')
    exact_path = str(files_roots[0].resolve())
    candidates = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BASE_PATH, 0, winreg.KEY_READ) as root:
        count = winreg.QueryInfoKey(root)[0]
        need(count <= 10000, 'bounded fixture registry inventory')
        for index in range(count):
            key = winreg.EnumKey(root, index)
            try:
                with winreg.OpenKey(root, key, 0, winreg.KEY_READ) as child:
                    value, kind = winreg.QueryValueEx(child, 'State')
            except FileNotFoundError:
                continue
            if kind != winreg.REG_BINARY or type(value) is not bytes or len(value) > 131072:
                continue
            try:
                record = json.loads(value).get('record', {})
            except (ValueError, UnicodeError):
                continue
            if record.get('files', {}).get('path') == exact_path:
                candidates.append(key)
    need(len(candidates) == 1, 'exact existing custody required')
    need(not output.exists(), 'export already exists')
    output.mkdir()
    report = {'schema': 'hh-s55-native-export-1', 'observed_ms': time.time_ns() // 1_000_000,
              'source_closure_sha256': CLOSURE, 'storage_id': candidates[0], 'project_id': snapshot['project_id'],
              'access_scope': 'non-publishing content verification with write-capable verification handles',
              'native_current_state_evidence': True, 'portable_checksum_is_native_authority': False,
              'creates_appends_registry_updates_or_rearms': False, 'gt03_acceptance': False}
    registry = files = log = blobs = None
    succeeded = False
    try:
        registry = RegistryCustody.reopen(candidates[0])
        custody_raw = registry.read()
        custody = decode_record(custody_raw)
        need(custody['project_id'] == snapshot['project_id'] and custody['storage_id'] == candidates[0]
             and custody['files']['path'] == exact_path, 'custody identity mismatch')
        saved = binding_from(custody['events']['binding'])
        # Supplied bindings reopen existing objects. No creation APIs are used.
        files = ProtectedFileRoot.reopen_readonly(custody['files']['path'], identity_from(custody['files']['identity']))
        need(files._readonly is True, 'selected root must be readonly')
        log = PrivateEventLog.reopen(custody['events']['path'], saved)
        current = log.binding()
        need(current.root.same_file(saved.root) and current.stream.same_file(saved.stream)
             and current.witnessed == saved.witnessed, 'unacknowledged or changed event suffix')
        with log._locked():
            raw = log._read_at(0, log._inspect().size)
        head, records = log.fold((), lambda rows, record: (*rows, {'head': dataclasses.asdict(record.head), 'event': json.loads(record.event)}))
        need(head == saved.witnessed and len(raw) == head.size, 'unacknowledged raw suffix')
        need([row['event'] for row in records[4:]] == events, 'native events differ from lane export')
        selected = snapshot['selected']

        def native_file(name, expected):
            version, content = files.read(name)
            actual = {'volume': str(version.identity.volume), 'file_id': version.identity.file_id,
                      'size_bytes': version.identity.size, 'sha256': version.sha256}
            need(actual == {key: expected[key] for key in actual}
                 and sha(content) == actual['sha256'] and len(content) == actual['size_bytes'], 'selected native file identity: ' + name)
            return actual, content

        selector_version, selector_raw = native_file('active.json', selected['selector_version'])
        descriptor = selected['selector']['descriptor']
        manifest_version, manifest_raw = native_file(descriptor['manifest']['name'], descriptor['manifest'])
        need(selector_raw == canonical_bytes(selected['selector']) and manifest_raw == canonical_bytes(selected['bundle_manifest']), 'native selector/manifest bytes')
        inventory = {}
        for name, desc in descriptor['files'].items():
            inventory[name], content = native_file(desc['name'], desc)
            expected = selected['bundle_manifest']['files'][name]
            need(sha(content) == expected['sha256'] and len(content) == expected['size_bytes'], 'selected bundle bytes')
        need(len(inventory) == 11, 'full selected bundle required')
        descriptions = {}
        for event in events:
            for field in ('scene_blob', 'capture_blob', 'observation_blob'):
                if field in event:
                    desc = event[field]
                    need(desc['object_id'] not in descriptions or descriptions[desc['object_id']] == desc, 'conflicting blob identity')
                    descriptions[desc['object_id']] = desc
        if descriptions:
            blobs = PrivateBlobStore.reopen(custody['blobs']['path'], identity_from(custody['blobs']['identity']))
            (output / 'blobs').mkdir()
            for object_id, desc in descriptions.items():
                content = blobs.read_blob(StagedBlob(object_id, identity_from(desc['identity']), desc['sha256']))
                need(sha(content) == desc['sha256'] and len(content) == desc['identity']['size'], 'edit blob bytes')
                (output / 'blobs' / object_id).write_bytes(content)
        # Re-read all evidence-bearing native objects before releasing handles.
        for name, desc in descriptor['files'].items():
            need(native_file(desc['name'], desc)[0] == inventory[name], 'selected identity changed during export')
        need(native_file('active.json', selected['selector_version']) == (selector_version, selector_raw)
             and native_file(descriptor['manifest']['name'], descriptor['manifest']) == (manifest_version, manifest_raw), 'selection changed during export')
        with log._locked():
            final_raw = log._read_at(0, log._inspect().size)
        need(final_raw == raw and registry.read() == custody_raw and log.binding() == current, 'native bytes/custody/head changed during export')
        for object_id, desc in descriptions.items():
            need(blobs.read_blob(StagedBlob(object_id, identity_from(desc['identity']), desc['sha256'])) == (output / 'blobs' / object_id).read_bytes(), 'blob changed during export')
        report.update(registry_unchanged=True, stream_unchanged=True, selected_files_unchanged=True,
                      native_binding=binding_value(current), native_records=list(records), edit_blobs=descriptions,
                      files_root={'volume': str(files.root_identity.volume), 'file_id': files.root_identity.file_id},
                      selector_version=selector_version, manifest_version=manifest_version, selected_files=inventory,
                      custody_sha256=sha(custody_raw), stream_sha256=sha(raw), stream_size_bytes=len(raw))
        for name, content in (('native-custody.json', custody_raw), ('native-events.bin', raw),
                              ('native-selector.json', selector_raw), ('native-manifest.json', manifest_raw)):
            (output / name).write_bytes(content)
        succeeded = True
    finally:
        errors = []
        for resource in (blobs, log, files, registry):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(type(error).__name__ + ': ' + str(error))
        report.update(cleanup_errors=errors, native_resources_closed=not errors, passed=succeeded and not errors)
        write(output / 'native-capture.json', report)
        need(not errors, 'native cleanup failed: ' + str(errors))
    return {'package': package.name, 'native_sequence': head.sequence, 'selected_files': len(inventory), 'edit_blobs': len(descriptions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', action='append', required=True, help='one known S55 lane directory name; repeat serially')
    parser.add_argument('--output', type=Path, required=True, help='fresh owned directory under the S55 audit')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--check-only', action='store_true', help='source/package preflight only; no native access or writes')
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.parent == HERE and len(args.package) <= 11 and len(set(args.package)) == len(args.package), 'bounded owned output/packages required')
    packages = [(REVIEWS / name).resolve() for name in args.package]
    before = freeze_check()
    for package in packages:
        package_facts(package)
    if args.check_only:
        print(json.dumps({'source_closure_sha256': CLOSURE, 'files': len(before), 'packages': args.package, 'native_handles_opened': 0}))
        return 0
    if args.frozen:
        sys.path.insert(0, str(SOURCE.parent))
        rows = [export_one(package, output / package.name) for package in packages]
        need(freeze_check() == before, 'source changed during native verification')
        write(output / 'export-results.json', {'packages': rows, 'source_unchanged': True, 'gt03_acceptance': False})
        print('HH_S55_NATIVE_EXPORT_COMPLETE ' + json.dumps({'packages': len(rows), 'passed': True}), flush=True)
        return 0
    need(not output.exists(), 'fresh export output required')
    output.mkdir()
    driver = output / 'exporter.py'
    driver.write_bytes(Path(__file__).read_bytes())
    spec = importlib.util.spec_from_file_location('s55_export_owned_runner', SOURCE / 'build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    argv = [sys.executable, '-B', str(driver), '--frozen', '--output', str(output)]
    for name in args.package:
        argv += ['--package', name]
    write(output / 'export-invocation.json', {'argv': argv, 'timeout_seconds': 300,
          'source_closure_sha256': CLOSURE, 'source_manifest_sha256': sha((SOURCE_PACKAGE / 'source-closure.json').read_bytes()),
          'exporter_sha256': sha(driver.read_bytes()), 'requires_coordinator_native_slot': True,
          'access_scope': 'non-publishing content verification with write-capable verification handles'})
    host = runner.run_process(argv, cwd=SOURCE, output=output, timeout=300, label='native-export')
    write(output / 'export-host-report.json', host)
    raw = read(output / host['host'])
    need(type(raw['exit_code']) is int and raw['exit_code'] == host['exit_code'] == host['wrapper_exit_code'] == 0
         and raw['target_pid'] == host['target_pid'] and host['tree_verified'] is True and host['timed_out'] is False
         and host['ownership'] == 'gated_job_kill_on_close', 'native export raw exit/Job failed')
    markers = [json.loads(line.split(' ', 1)[1]) for line in (output / host['stdout']).read_text(encoding='utf-8').splitlines()
               if line.startswith('HH_S55_NATIVE_EXPORT_COMPLETE ')]
    need(markers == [{'packages': len(packages), 'passed': True}] and not (output / host['stderr']).read_bytes(),
         'native export completion marker/diagnostic mismatch')
    need([row['package'] for row in read(output / 'export-results.json')['packages']] == args.package,
         'native export package inventory differs')
    need(freeze_check() == before and driver.read_bytes() == Path(__file__).read_bytes(), 'source/exporter changed')
    print(json.dumps({'passed': True, 'packages': args.package, 'source_unchanged': True, 'gt03_acceptance': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
