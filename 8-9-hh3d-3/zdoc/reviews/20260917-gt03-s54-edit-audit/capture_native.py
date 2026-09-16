"""Windows-only read-only export of retained native identities and stream bytes.

Never opens RecoveryJournal, attaches custody, appends, provisions, or rearms.
The exported Registry checksum is corruption detection, not portable authority.
"""
from pathlib import Path
import dataclasses
import hashlib
import json
import sys
import time

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / '20260917-gt03-s54-edit-publication-03'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    source = json.loads((PACKAGE / 'source-closure.json').read_text())
    for name, digest in source['files'].items():
        assert sha((PACKAGE / 'source/studio' / name).read_bytes()) == digest, name
    sys.path.insert(0, str(PACKAGE / 'source'))
    from studio.host.core.custody_registry import RegistryCustody, BASE_PATH
    from studio.host.core.custody import decode_record, binding_from, binding_value, identity_from
    from studio.host.core.private_events import PrivateEventLog
    from studio.host.core.safe_replace import ProtectedFileRoot
    from studio.host.core.limits import canonical_json
    snapshot = json.loads((PACKAGE / 'journal-snapshot.json').read_text())
    # Locate only this retained fixture's opaque storage ID, then validate it
    # through RegistryCustody. Enumeration itself supplies no authority.
    import winreg
    candidates=[]
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,BASE_PATH,0,winreg.KEY_READ) as root:
        count=winreg.QueryInfoKey(root)[0]
        assert count<=10000, 'bounded local fixture inventory'
        for index in range(count):
            key=winreg.EnumKey(root,index)
            try:
                with winreg.OpenKey(root,key,0,winreg.KEY_READ) as child:
                    value,kind=winreg.QueryValueEx(child,'State')
            except FileNotFoundError:
                continue
            if kind!=winreg.REG_BINARY or type(value) is not bytes or len(value)>131072:continue
            try: record=json.loads(value).get('record',{})
            except (ValueError,UnicodeError):continue
            if record.get('files',{}).get('path')==str(next((PACKAGE/'owned/storage').glob('hh-files-*'))):
                candidates.append(key)
    assert len(candidates)==1, 'exact retained fixture registry'
    original={'storage_id':candidates[0],'project_id':snapshot['project_id']}
    registry = files = log = blobs = None
    report = {'schema': 'hh-editor-native-audit-1', 'observed_ms': time.time_ns() // 1_000_000,
              'source_closure_sha256': source['source_closure_sha256'],
              'storage_id': original['storage_id'], 'project_id': original['project_id'],
              'read_only_audit': True, 'gt03_acceptance': False}
    try:
        registry = RegistryCustody.reopen(original['storage_id'])
        custody_raw = registry.read()
        custody = decode_record(custody_raw)
        assert custody['storage_id'] == original['storage_id'] and custody['project_id'] == original['project_id']
        saved = binding_from(custody['events']['binding'])
        files = ProtectedFileRoot.reopen_readonly(custody['files']['path'], identity_from(custody['files']['identity']))
        assert files._readonly is True
        log = PrivateEventLog.reopen(custody['events']['path'], saved)
        current = log.binding()
        assert current.root.same_file(saved.root) and current.stream.same_file(saved.stream)
        assert current.witnessed == saved.witnessed
        with log._locked():
            raw = log._read_at(0, log._inspect().size)
        head, records = log.fold((), lambda rows, record: (*rows, {'head': dataclasses.asdict(record.head),
                                                                 'event': json.loads(record.event)}))
        assert head == current.witnessed and len(raw) == head.size
        selected = snapshot['selected']
        assert selected == snapshot['last_good']
        def read_native(name, expected):
            version, content = files.read(name)
            actual = {'volume': str(version.identity.volume), 'file_id': version.identity.file_id,
                      'size_bytes': version.identity.size, 'sha256': version.sha256}
            assert actual == {key: expected[key] for key in actual}, name
            assert sha(content) == actual['sha256'] and len(content) == actual['size_bytes'], name
            return actual, content
        active_version, active_raw = read_native('active.json', selected['selector_version'])
        assert canonical_json(selected['selector']) == active_raw
        descriptor = selected['selector']['descriptor']
        manifest_version, manifest_raw = read_native(descriptor['manifest']['name'], descriptor['manifest'])
        assert canonical_json(selected['bundle_manifest']) == manifest_raw
        inventory = {}
        for name, desc in descriptor['files'].items():
            inventory[name], content = read_native(desc['name'], desc)
            expected = selected['bundle_manifest']['files'][name]
            assert sha(content) == expected['sha256'] and len(content) == expected['size_bytes']
        assert len(inventory) == 11
        from studio.host.core.private_store import PrivateBlobStore,StagedBlob
        blobs=PrivateBlobStore.reopen(custody['blobs']['path'],identity_from(custody['blobs']['identity']))
        exported={}
        for row in json.loads((PACKAGE/'journal-events.json').read_bytes()):
            for field in ('scene_blob','capture_blob','observation_blob'):
                if field not in row:continue
                desc=row[field]
                content=blobs.read_blob(StagedBlob(desc['object_id'],identity_from(desc['identity']),desc['sha256']))
                assert sha(content)==desc['sha256'] and len(content)==desc['identity']['size']
                target=HERE/'blobs'/desc['object_id'];target.parent.mkdir(exist_ok=True)
                target.write_bytes(content);exported[desc['object_id']]=desc
        assert len(exported)==18
        report['edit_blobs']=exported
        assert registry.read() == custody_raw and log.binding() == current
        report.update({'registry_unchanged': True, 'stream_unchanged': True,
                       'native_binding': binding_value(current), 'native_records': list(records),
                       'files_root': {'volume': str(files.root_identity.volume), 'file_id': files.root_identity.file_id},
                       'selector_version': active_version, 'manifest_version': manifest_version,
                       'selected_files': inventory, 'custody_sha256': sha(custody_raw),
                       'stream_sha256': sha(raw), 'stream_size_bytes': len(raw)})
        (HERE / 'native-custody.json').write_bytes(custody_raw)
        (HERE / 'native-events.bin').write_bytes(raw)
        (HERE / 'native-selector.json').write_bytes(active_raw)
        (HERE / 'native-manifest.json').write_bytes(manifest_raw)
    finally:
        errors = []
        for resource in (blobs, log, files, registry):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    errors.append(type(exc).__name__ + ': ' + str(exc))
        report['cleanup_errors'] = errors
        report['native_resources_closed'] = not errors
        write('native-capture.json', report)
        if errors:
            raise RuntimeError(errors)
    print(json.dumps({'native_sequence': head.sequence, 'selected_files': len(inventory),
                      'custody_unchanged': True, 'stream_unchanged': True, 'resources_closed': True}))


if __name__ == '__main__':
    main()
