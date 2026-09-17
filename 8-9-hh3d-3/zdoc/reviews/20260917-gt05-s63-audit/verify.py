"""Read-only GT-05 package verification. No engine, replay, publication or acceptance.

Raw captures attest what the trusted owned workers observed. This checks their
exact bytes and cross-record bindings; it does not re-enact OS process death or
re-open protected custody registries. Git checking reads blobs without staging.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import unicodedata

sys.dont_write_bytecode = True
STUDIO_PREFIX = '8-9-hh3d-3/studio/'
DIRECTORIES = ('pipeline', 'tests/pipeline', 'host/core', 'host/blender', 'protocol',
               'blender-addon', 'fixtures/assets-src', 'contracts')
SUFFIXES = {'.py', '.json', '.md', '.txt', '.cjs', '.gd', '.uid', '.godot', '.tscn', '.tres'}
CRASH_PHASES = {'intent': 'INTENT', 'artifact': 'INTENT', 'manifest': 'INTENT',
    'selecting': 'SELECTING', 'selector': 'SELECTING', 'before_witness': 'SELECTING', 'terminal': 'TERMINAL'}
CASES = ('success', 'stop_before_intent', 'stop_after_selector', 'write_failure',
         *('crash_' + phase for phase in CRASH_PHASES))
PAYLOADS = {'fixture.blend', 'fixture.glb', 'producer-report.json', 'asset-manifest.json'}
EVIDENCE = {'producer', 'admission', 'khronos', 'godot', 'repeat', 'edit', 'reimport', 'visual', 'rejections'}


class Rejected(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(value, code):
    if not value:
        raise Rejected(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def strict(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'JSON_DUPLICATE')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Rejected('JSON_NONFINITE')))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Rejected('JSON_SYNTAX') from None
    need(type(value) is dict, 'JSON_OBJECT')
    return value


def safe(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name
         and not name.startswith('/') and not PureWindowsPath(name).drive
         and all(ord(char) >= 32 for char in name)
         and all(part not in ('', '.', '..') and part.rstrip(' .') == part for part in name.split('/')),
         'UNSAFE_PATH')
    return name


def hash_map(files):
    need(type(files) is dict and 0 < len(files) <= 20000, 'HASH_MAP_EMPTY_OR_SIZE')
    aliases = set()
    for name, digest in files.items():
        safe(name)
        alias = unicodedata.normalize('NFC', name).casefold()
        need(alias not in aliases, 'PATH_ALIAS')
        aliases.add(alias)
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'HASH_FORMAT')
    return files


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def read_file(path, cap=32 * 1024 * 1024):
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
        need(path.is_file() and path.stat().st_size <= cap, 'FILE_SIZE_OR_KIND')
        raw = path.read_bytes()
        need(len(raw) <= cap, 'FILE_SIZE_OR_KIND')
        return raw
    except OSError:
        raise Rejected('FILE_MISSING_OR_UNREADABLE') from None


def marker(stdout, prefix, expected):
    rows = [strict(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
    need(rows == [expected], 'RAW_MARKER_BINDING')


class Package:
    def __init__(self, manifest_path, repo_root):
        self.repo = Path(repo_root).absolute()
        self.studio = self.repo / STUDIO_PREFIX
        self.manifest_path = Path(manifest_path).absolute()
        need(self.manifest_path.is_relative_to(self.repo), 'MANIFEST_OUTSIDE_REPO')
        self.manifest_raw = read_file(self.manifest_path)
        self.manifest = strict(self.manifest_raw)
        m = self.manifest
        need(m['schema'] == 'HH-GT05-REVIEW-CLOSURE-1', 'MANIFEST_SCHEMA')
        self.source, self.review, self.raw_map = (hash_map(m[key]) for key in ('source_files', 'review_files', 'raw_files'))
        need(len(self.source) == 143 and all(name.startswith(STUDIO_PREFIX) for name in self.source), 'COMPLETE_SOURCE_SET')
        need(all(name.startswith('.local/reviews/') for name in self.raw_map), 'RAW_PATH_SCOPE')
        self.all_map = dict(self.source)
        for name, digest in [*self.review.items(), *((STUDIO_PREFIX + n, d) for n, d in self.raw_map.items())]:
            need(name not in self.all_map, 'MAP_OVERLAP')
            self.all_map[name] = digest
        hash_map(self.all_map)
        manifest_name = self.manifest_path.relative_to(self.repo).as_posix()
        need(manifest_name not in self.all_map, 'MANIFEST_SELF_REFERENCE')
        for role, files in [('source', self.source), ('review', self.review), ('raw', self.raw_map)]:
            need(m[role + '_closure_sha256'] == closure(files), 'CLOSURE_HASH')
        self.data = {}
        for name, digest in self.all_map.items():
            value = read_file(self.repo / name)
            need(sha(value) == digest, 'FILE_HASH')
            self.data[name] = value
        self.studio_sources = {name[len(STUDIO_PREFIX):]: digest for name, digest in self.source.items()}
        self.check_current_source()
        need(type(m['runs']) is dict and set(m['runs']) == {'units', 'snapshot_native', 'snapshot_staged', 'publication', 'visual_review', 'bone_migration'}, 'RUN_ROLES')
        for name in m['runs'].values():
            need(type(name) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', name), 'RUN_ID')
        need(len(set(m['runs'].values())) == 6, 'RUN_ALIAS')
        self.check_raw_inventory()
        # Canonicalization is the pinned protocol implementation, never source
        # supplied by raw evidence. No protected store is opened by this import.
        sys.path.insert(0, str(self.studio.parent))
        from studio.protocol.core import canonical_bytes
        self.canonical = canonical_bytes

    def check_current_source(self):
        paths = {self.studio / name for name in ('build/bootstrap/run_fixture.py',
            'godot-addon/cli_job.py', 'tests/asset-profile.json', 'toolchain.lock.json')}
        for directory in DIRECTORIES:
            paths.update(path for path in (self.studio / directory).rglob('*')
                if path.is_file() and path.suffix in SUFFIXES and '__pycache__' not in path.parts)
        actual = {path.relative_to(self.studio).as_posix(): sha(read_file(path)) for path in paths}
        need(actual == self.studio_sources, 'CURRENT_SOURCE_CLOSURE')

    def check_raw_inventory(self):
        proof = self.obj(self.run('publication') + '/verified-chain.json')
        expected = {name for name in hash_map(proof['evidence_files']) if name.startswith('.local/reviews/')}
        for run in self.manifest['runs'].values():
            root = self.studio / '.local/reviews' / run
            need(root.is_dir(), 'RAW_RUN_MISSING')
            for path in (root, *root.rglob('*')):
                info = path.lstat()
                need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
                if path.is_file():
                    expected.add(path.relative_to(self.studio).as_posix())
        need(set(self.raw_map) == expected, 'RAW_INVENTORY')

    def raw(self, name):
        safe(name)
        need(name in self.raw_map, 'RAW_NOT_INDEXED')
        return self.data[STUDIO_PREFIX + name]

    def obj(self, name):
        return strict(self.raw(name))

    def run(self, role):
        return '.local/reviews/' + self.manifest['runs'][role]

    def host(self, root, host, label, argv):
        need(host['argv'] == argv and host['stdout'] == label + '-stdout.txt'
             and host['stderr'] == label + '-stderr.txt' and host['host'] == label + '-host.json', 'HOST_INVOCATION')
        actual = self.obj(root + '/' + host['host'])
        need(set(actual) == {'target_pid', 'started_at', 'exit_code'}
             and type(actual['target_pid']) is int and actual['target_pid'] > 0
             and actual['target_pid'] == host['target_pid']
             and type(actual['exit_code']) is int and actual['exit_code'] == 0
             and type(host['exit_code']) is int and host['exit_code'] == 0
             and type(host['wrapper_exit_code']) is int and host['wrapper_exit_code'] == 0
             and type(host['wrapper_pid']) is int and host['wrapper_pid'] > 0
             and host['wrapper_pid'] != host['target_pid']
             and host['timed_out'] is False and host['tree_verified'] is True
             and host['ownership'] == 'gated_job_kill_on_close', 'HOST_ACTUAL_EXIT')
        need(datetime.fromisoformat(actual['started_at']) >= datetime.fromisoformat(host['started_at']), 'HOST_START_BINDING')
        stdout, stderr = (self.raw(root + '/' + host[key]) for key in ('stdout', 'stderr'))
        if label != 'unit':
            need(not stderr.strip(), 'HOST_STDERR')
        return stdout, stderr

    def frozen_source(self, root, ordinal=False):
        if ordinal:
            source = self.obj(root + '/invocation.json')['source_files']
            need(source == self.studio_sources, 'CAPTURE_SOURCE_CLOSURE')
        else:
            doc = self.obj(root + '/source-closure.json'); source = doc['files']
            need(source == self.studio_sources and doc['source_closure_sha256'] == closure(self.source), 'CAPTURE_SOURCE_CLOSURE')
        for name, digest in source.items():
            slot = ('source/' + sha(name.encode()) + Path(name).suffix) if ordinal else 'source/studio/' + name
            need(sha(self.raw(root + '/' + slot)) == digest, 'CAPTURE_SOURCE_SNAPSHOT')

    def units(self):
        root = self.run('units'); capture = self.obj(root + '/capture.json'); invocation = self.obj(root + '/invocation.json')
        need(capture['schema'] == 'HH-GT05-UNIT-CAPTURE-1' and capture['run_id'] == self.manifest['runs']['units'], 'UNIT_SCHEMA')
        self.frozen_source(root)
        need(invocation['pattern'] == 'test_*.py' and capture['source_closure_sha256'] ==
             invocation['source_closure_sha256'] == closure(self.source), 'UNIT_SOURCE_BINDING')
        required = {'unit-stdout.txt', 'unit-stderr.txt', 'unit-host.json', 'invocation.json', 'source-closure.json', 'dependency-files.json'}
        need(set(capture['artifacts']) == required and all(sha(self.raw(root + '/' + name)) == digest
            for name, digest in capture['artifacts'].items()), 'UNIT_ARTIFACT_BINDING')
        stdout, stderr = self.host(root, capture['host'], 'unit', ['python.exe', '-B', '-c', invocation['code'], 'test_*.py'])
        summary = capture['summary']
        marker(stdout, b'GT05_UNIT_COMPLETE ', summary)
        roster = set()
        for name in self.studio_sources:
            if name.startswith('tests/pipeline/test_') and name.endswith('.py'):
                tree = ast.parse(self.data[STUDIO_PREFIX + name])
                for cls in tree.body:
                    if isinstance(cls, ast.ClassDef):
                        roster.update(Path(name).stem + '.' + cls.name + '.' + node.name for node in cls.body
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'))
        need(type(summary['run']) is int and summary['run'] == len(roster) > 0
             and len(summary['ids']) == len(set(summary['ids'])) == len(roster) and set(summary['ids']) == roster
             and type(summary['errors']) is int and summary['errors'] == 0
             and type(summary['failures']) is int and summary['failures'] == 0, 'UNIT_RESULTS')
        need(len(summary['skips']) == 1 and 'symlink' in summary['skips'][0]['id'].lower(), 'UNIT_SKIP_SCOPE')
        need(re.search(rb'Ran ' + str(len(roster)).encode() + rb' tests in [0-9.]+s\r?\n\r?\nOK \(skipped=1\)\r?\n?$', stderr), 'UNIT_RAW_RESULT')
        lock = strict(self.data[STUDIO_PREFIX + 'pipeline/dependencies/gltf-validator.lock.json'])
        expected = {'.local/tooling/gt05/gltf-validator-' + lock['version'] + '/' + name: digest for name, digest in lock['files'].items()}
        need(len(expected) == 9 and self.obj(root + '/dependency-files.json') == expected, 'UNIT_DEPENDENCIES')
        for name, digest in expected.items():
            need(sha(self.raw(root + '/source/studio/' + name)) == digest, 'UNIT_DEPENDENCY_BYTES')
        return {'tests': len(roster), 'skips': summary['skips'], 'python_sha256': invocation['python_sha256']}

    def staged_cut(self, units):
        root = self.run('snapshot_staged'); invocation = self.obj(root + '/invocation.json')
        capture = self.obj(root + '/capture.json'); raw = self.raw(root + '/observed.json'); observed = strict(raw)
        driver_names = [name for name in self.review if name.endswith('/run_staged_cut.py')]
        need(len(driver_names) == 1 and self.raw(root + '/driver.snapshot') == self.data[driver_names[0]]
             and invocation['driver_sha256'] == self.review[driver_names[0]]
             and invocation['source_files'] == self.studio_sources
             and invocation['python_sha256'] == units['python_sha256'] and invocation['timeout_seconds'] == 45,
             'STAGED_DRIVER_SOURCE')
        stdout, _ = self.host(root, capture['host'], 'staged', ['python.exe', '-B',
            'run_staged_cut.py', '--worker', '$SNAPSHOT/' + root])
        marker(stdout, b'GT05_STAGED_CUT ', {'observed_sha256': sha(raw), 'phase': 'STAGED', 'child_exit': 86})
        ready_raw = self.raw(root + '/ready.json'); ready = strict(ready_raw)
        need(observed['schema'] == 'HH-GT05-STAGED-CUT-1' and observed['phase'] == ready['phase'] == 'STAGED'
             and type(observed['child_exit']) is int and observed['child_exit'] == 86
             and type(observed['child_pid']) is int and observed['child_pid'] == ready['pid'] > 0
             and ready['pid'] not in (capture['host']['target_pid'], capture['host']['wrapper_pid'])
             and ready['provider_calls'] == 1 and observed['ready_sha256'] == sha(ready_raw)
             and ready['files'] == sorted(['.writer', 'publication-manifest.json', *PAYLOADS])
             and not self.raw(root + '/child-stdout.txt') and not self.raw(root + '/child-stderr.txt'), 'STAGED_ACTUAL_CRASH')
        need(ready['request']['expected_source_sha256'] == sha(self.canonical(self.studio_sources)), 'STAGED_REQUEST_SOURCE')
        need(observed['recovery_status'] == 'UNKNOWN' and observed['native_payload_readback'] is True
             and observed['selector_absent'] is True and observed['readonly_prefix_unchanged'] is True
             and observed['last_good_unchanged'] is True and observed['synthetic_storage_only'] is True
             and observed['asset_validation_proven'] is False and observed['public_ack'] is False
             and observed['formal_acceptance'] is False, 'STAGED_RECOVERY')
        last_good = self.manifest['runs']['snapshot_native'] + '/success'
        need(invocation['last_good_run'] == last_good, 'STAGED_LAST_GOOD_RUN')
        prefix = '.local/reviews/' + last_good + '/'
        actual_graph = {name[len(prefix):]: digest for name, digest in self.raw_map.items()
                        if name.startswith(prefix + 'hh-')}
        need(actual_graph and observed['last_good_graph'] == invocation['last_good_graph'] == actual_graph, 'STAGED_LAST_GOOD_GRAPH')
        manifests = [name for name in self.raw_map if name.startswith(root + '/hh-files-') and name.endswith('/publication-manifest.json')]
        need(len(manifests) == 1 and not any(name.startswith(root + '/hh-files-') and name.endswith('/snapshot.json')
                                           for name in self.raw_map), 'STAGED_SELECTOR_ABSENT')
        manifest = self.obj(manifests[0]); folder = manifests[0].rsplit('/', 1)[0]
        need(manifest['storage_id'] == ready['storage_id'] and set(manifest['artifacts']) == PAYLOADS, 'STAGED_MANIFEST')
        for name, item in manifest['artifacts'].items():
            value = self.raw(folder + '/' + name)
            need(value == ('SYNTHETIC_STORAGE_TEST_ONLY:' + name).encode()
                 and item == {'sha256': sha(value), 'size_bytes': len(value)}, 'STAGED_PAYLOAD_READBACK')
        return {'phase': 'STAGED', 'actual_crash_exit': 86, 'recovery': 'UNKNOWN', 'selector_absent': True}

    def stored_snapshot(self, root, storage_id, receipt_digest):
        candidates = [name for name in self.raw_map if name.startswith(root + '/hh-files-')
            and name.count('/') == root.count('/') + 2 and name.endswith('/snapshot.json')]
        selected = [(name, self.obj(name)) for name in candidates if self.obj(name)['storage_id'] == storage_id]
        need(len(selected) == 1, 'STORAGE_SELECTOR_SET')
        selector_name, selector = selected[0]; folder = selector_name.rsplit('/', 1)[0]
        manifest_raw = self.raw(folder + '/publication-manifest.json'); manifest = strict(manifest_raw)
        need(selector['manifest']['sha256'] == sha(manifest_raw) == selector['manifest']['file_version']['sha256']
             and selector['manifest']['identity']['size'] == selector['manifest']['file_version']['identity']['size'] == len(manifest_raw)
             and manifest['storage_id'] == storage_id and manifest['public_ack'] is False
             and manifest['editor_activation'] is False and set(manifest['artifacts']) == PAYLOADS, 'STORAGE_MANIFEST_BINDING')
        payloads = {}
        for name, item in manifest['artifacts'].items():
            value = self.raw(folder + '/' + name)
            need(item == {'sha256': sha(value), 'size_bytes': len(value)}, 'STORAGE_PAYLOAD_BINDING')
            payloads[name] = value
        for field in ('command_id', 'profile', 'request_sha256', 'schema', 'snapshot_kind', 'storage_id', 'public_ack', 'editor_activation'):
            need(selector[field] == manifest[field], 'STORAGE_SELECTOR_BINDING')
        receipt = {key: manifest[key] for key in ('artifacts', 'command_id', 'profile', 'request_sha256', 'schema',
            'snapshot_kind', 'source_sha256', 'storage_id', 'public_ack', 'editor_activation')}
        receipt.update(status='COMMITTED', manifest_sha256=sha(manifest_raw), selector_sha256=sha(self.raw(selector_name)))
        need(sha(self.canonical(receipt)) == receipt_digest, 'STORAGE_RECEIPT_BINDING')
        # The selected sealed manifest descriptor must resolve to retained blob
        # bytes, not only an editable visible mirror with the same JSON fields.
        blob = selector['manifest']['object_id']
        matches = [name for name in self.raw_map if name.startswith(root + '/hh-private-') and name.endswith('/' + blob)]
        need(len(matches) == 1 and self.raw(matches[0]) == manifest_raw, 'STORAGE_SEALED_MANIFEST')
        return manifest, payloads, receipt

    def snapshot_native(self):
        root = self.run('snapshot_native'); capture = self.obj(root + '/capture.json')
        self.frozen_source(root)
        need([row['case'] for row in capture['runs']] == list(CASES)
             and capture['synthetic_storage_only'] is True and capture['asset_validation_proven'] is False, 'NATIVE_MATRIX_SET')
        success_digest = None
        for row in capture['runs']:
            case = row['case']; lane = root + '/' + case
            need(self.obj(root + '/' + case + '-capture.json') == row, 'NATIVE_LANE_CAPTURE')
            stdout, _ = self.host(lane, row['host'], 'native', ['python.exe', '-B',
                '$SNAPSHOT/tests/pipeline/run_snapshot_probe.py', '--worker', case, '--output', case])
            observed_raw = self.raw(lane + '/observed.json'); observed = strict(observed_raw)
            marker(stdout, b'GT05_SNAPSHOT_PROBE ', {'case': case, 'observed_sha256': sha(observed_raw),
                'passed': True, 'synthetic_storage_only': True, 'asset_validation_proven': False})
            need(observed['case'] == case and observed['synthetic_storage_only'] is True
                 and observed['asset_validation_proven'] is False and observed['public_ack'] is False
                 and observed['formal_acceptance'] is False and row['previous_completed_snapshot_unchanged'] is True,
                 'NATIVE_SCOPE_OR_LAST_GOOD')
            if case == 'success':
                need(observed['recovery'] == {'status': 'COMMITTED', 'receipt_sha256': observed['receipt_sha256']}, 'NATIVE_SUCCESS_RECOVERY')
                _, payloads, _ = self.stored_snapshot(lane, observed['storage_id'], observed['receipt_sha256'])
                need(all(value == ('SYNTHETIC_STORAGE_TEST_ONLY:' + name).encode() for name, value in payloads.items()), 'NATIVE_SYNTHETIC_BYTES')
                success_digest = sha(compact({name: digest for name, digest in self.raw_map.items()
                    if name.startswith(lane + '/hh-')}))
            elif case == 'stop_before_intent':
                need(observed['stopped_before_provider'] is True
                     and not any(name.startswith(lane + '/hh-files-') and name.rsplit('/', 1)[1] != '.writer'
                                 for name in self.raw_map), 'NATIVE_STOP_BEFORE_WRITE')
            elif case in ('stop_after_selector', 'write_failure'):
                need(observed['fault_hooks'] == (['snapshot.json'] if case == 'stop_after_selector' else ['fixture.blend'])
                     and observed['provider_calls'] == 1 and observed['recovery']['status'] == 'UNKNOWN'
                     and observed['errors'][0]['code'] == 'SNAPSHOT_OUTCOME_UNKNOWN', 'NATIVE_FAULT_HOOK')
                if case == 'write_failure':
                    need({'type': 'OSError', 'code': 'injected-storage-io-failure'} in observed['errors'], 'NATIVE_WRITE_CAUSE')
            else:
                cut = case.removeprefix('crash_'); ready = self.obj(lane + '/ready.json')
                need(type(observed['child_exit']) is int and observed['child_exit'] == 86
                     and ready == observed['ready'] and ready['case'] == cut
                     and ready['phase'] == CRASH_PHASES[cut] and type(ready['pid']) is int and ready['pid'] > 0
                     and ready['pid'] not in (row['host']['target_pid'], row['host']['wrapper_pid'])
                     and ready['provider_calls'] == 1 and not self.raw(lane + '/child-stdout.txt')
                     and not self.raw(lane + '/child-stderr.txt'), 'NATIVE_ACTUAL_CRASH_BINDING')
                need(ready['request']['expected_source_sha256'] == sha(self.canonical(self.studio_sources)), 'NATIVE_CRASH_SOURCE')
                expected = 'COMMITTED' if cut == 'terminal' else 'HELD' if cut == 'before_witness' else 'UNKNOWN'
                need(observed['recovery']['status'] == expected, 'NATIVE_CRASH_RECOVERY')
                if expected == 'HELD':
                    need(any(error['code'] == 'EVENT_CUSTODY_BINDING_MISMATCH' for error in observed['recovery']['errors']), 'NATIVE_WITNESS_HOLD')
                elif expected == 'COMMITTED':
                    self.stored_snapshot(lane, ready['storage_id'], observed['recovery']['receipt_sha256'])
        need(success_digest is not None, 'NATIVE_LAST_GOOD_MISSING')
        return {'cases': len(CASES), 'actual_crash_exit': 86, 'last_good_retained_sha256': success_digest,
                'scope': 'synthetic protected-storage behavior; child exit is captured by the hash-bound owned worker'}

    def publication(self, units):
        root = self.run('publication'); capture = self.obj(root + '/capture.json'); config = self.obj(root + '/invocation.json')
        self.frozen_source(root, ordinal=True)
        need(config['source_closure_sha256'] == sha(self.canonical(self.studio_sources))
             and config['python_sha256'] == units['python_sha256']
             and config['worker_timeout_seconds'] == 90 and config['verification_deadline_seconds'] == 60, 'PUBLICATION_SOURCE_BINDING')
        stdout, _ = self.host(root, capture['host'], 'publication', ['python.exe', '-B',
            '$SNAPSHOT/tests/pipeline/run_snapshot_publication.py', '--worker', '$SNAPSHOT/' + root])
        observed_raw = self.raw(root + '/observed.json'); observed = strict(observed_raw)
        receipt_raw = self.raw(root + '/receipt.json'); receipt = strict(receipt_raw)
        proof_raw = self.raw(root + '/verified-chain.json'); proof = strict(proof_raw)
        manifest_raw = self.raw(root + '/publication-manifest.json'); manifest = strict(manifest_raw)
        marker(stdout, b'GT05_ACTUAL_SNAPSHOT ', {'observed_sha256': sha(observed_raw),
            'receipt_sha256': sha(receipt_raw), 'status': 'COMMITTED', 'public_ack': False})
        need(observed['schema'] == 'HH-GT05-ACTUAL-SNAPSHOT-CAPTURE-1' and observed['receipt_sha256'] == sha(receipt_raw)
             and observed['verified_chain_sha256'] == sha(proof_raw) and observed['manifest_sha256'] == sha(manifest_raw), 'PUBLICATION_REPORT_BINDING')
        stored, payloads, actual_receipt = self.stored_snapshot(root, observed['storage_id'], sha(receipt_raw))
        need(stored == manifest and actual_receipt == receipt and receipt_raw == self.canonical(receipt)
             and receipt['manifest_sha256'] == sha(self.canonical(manifest))
             and receipt['source_sha256'] == config['source_closure_sha256'], 'PUBLICATION_MANIFEST_RECEIPT')
        request = observed['request']
        need(receipt['request_sha256'] == sha(self.canonical(request))
             and request['expected_source_sha256'] == receipt['source_sha256']
             and request['command_id'] == receipt['command_id'] == 'snapshot.actual-assets'
             and observed['payload_sha256'] == {name: sha(value) for name, value in payloads.items()}, 'PUBLICATION_REQUEST_PAYLOAD')
        need(proof['schema'] == 'HH-GT05-VERIFIED-RUN-1' and proof['publishable'] is True and proof['complete'] is True
             and proof['current_source_verified'] is True and proof['current_source_required'] is True
             and proof['stale_source_files'] == [] and set(proof['evidence']) == EVIDENCE
             and manifest['evidence'] == proof['evidence'] and proof['source_sha256'] == sha(compact(proof['source_files'])), 'PUBLICATION_CHAIN_PROOF')
        for name, digest in hash_map(proof['source_files']).items():
            need(self.studio_sources.get(name) == digest, 'CHAIN_SOURCE_BINDING')
        for name, digest in hash_map(proof['evidence_files']).items():
            expected = self.raw_map.get(name) if name.startswith('.local/') else self.studio_sources.get(name)
            need(expected == digest, 'CHAIN_RAW_BINDING')
        for stage, files in proof['stage_source_files'].items():
            need(self.obj('.local/reviews/' + safe(stage)) == files, 'CHAIN_STAGE_SOURCE_MAP')
        need(set(proof['snapshot_qualifiers'].values()) == {'PRE_EXECUTION_SOURCE_SNAPSHOT'}, 'CHAIN_SNAPSHOT_QUALIFIERS')
        run_roles = {'producer_id', 'validation_id', 'consumer_id', 'repeat_producer_id', 'repeat_validation_id',
            'edited_producer_id', 'edited_validation_id', 'reimport_id', 'visual_id', 'rejections_id'}
        need(set(config['runs']) == run_roles, 'PUBLICATION_RUN_ROLES')
        for run in config['runs'].values():
            need(type(run) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run)
                 and any(name.startswith('.local/reviews/' + run + '/') for name in proof['evidence_files']), 'PUBLICATION_RUN_BINDING')
        runs = config['runs']
        expected_stages = {run + '/source-files.json' for run in runs.values()} | {
            runs[role] + '/admission-source-files.json' for role in
            ('validation_id', 'repeat_validation_id', 'edited_validation_id')}
        need(set(proof['stage_source_files']) == expected_stages, 'CHAIN_STAGE_SET')
        union = {}
        for files in proof['stage_source_files'].values():
            for name, digest in hash_map(files).items():
                if not name.startswith('.local/'):
                    need(name not in union or union[name] == digest, 'CHAIN_STAGE_SOURCE_CONFLICT')
                    union[name] = digest
        need(union == proof['source_files'], 'CHAIN_SOURCE_UNION')
        def raw_hash(role, filename):
            return sha(self.raw('.local/reviews/' + runs[role] + '/' + filename))
        validation = self.obj('.local/reviews/' + runs['validation_id'] + '/validation.json')
        need(validation['upstream_run_id'] == runs['producer_id'], 'CHAIN_VALIDATION_UPSTREAM')
        for vr, pr in [('repeat_validation_id', 'repeat_producer_id'), ('edited_validation_id', 'edited_producer_id')]:
            need(self.obj('.local/reviews/' + runs[vr] + '/validation.json')['upstream_run_id'] == runs[pr], 'CHAIN_VALIDATION_UPSTREAM')
        expected_evidence = {
            'producer': raw_hash('producer_id', 'diagnostic.json'),
            'admission': sha(compact({'capture': validation['admission_capture_sha256'], 'outputs': validation['admission_outputs']})),
            'khronos': sha(compact({'capture': validation['host_capture_sha256'], 'validator': raw_hash('validation_id', 'validator.json')})),
            'godot': raw_hash('consumer_id', 'consumer.json'),
            'repeat': sha(compact({'comparison': {'equivalent': True, 'numeric_tolerance': 1e-7, 'formal_acceptance': False},
                'producer': raw_hash('repeat_producer_id', 'diagnostic.json'), 'validation': raw_hash('repeat_validation_id', 'validation.json')})),
            'edit': sha(compact({'producer': raw_hash('edited_producer_id', 'diagnostic.json'),
                'validation': raw_hash('edited_validation_id', 'validation.json'), 'crate_width_m': [.6, .8]})),
            'reimport': raw_hash('reimport_id', 'followup.json'), 'visual': raw_hash('visual_id', 'followup.json'),
            'rejections': sha(compact({'report': raw_hash('rejections_id', 'output/result.json'),
                'capture': raw_hash('rejections_id', 'host/capture.json')}))}
        need(proof['evidence'] == expected_evidence, 'CHAIN_EVIDENCE_ROLES')
        producer = strict(payloads['producer-report.json']); asset = strict(payloads['asset-manifest.json'])
        need(asset['producer_report_sha256'] == sha(payloads['producer-report.json']) and asset['source_pins'] == producer['pins']
             and producer['license'] == asset['license'] == 'original-fixture' and producer['external_inputs'] == [], 'PUBLICATION_ASSET_BINDING')
        for name in ('fixture.glb', 'fixture.blend'):
            need(asset['artifacts'][name] == producer['artifacts'][name] == {'sha256': sha(payloads[name]), 'bytes': len(payloads[name])}, 'PUBLICATION_ASSET_BYTES')
        info = manifest['metadata']
        need(info['semantic'] == proof['semantic'] and info['binaries'] == proof['binaries']
             and info['catalog'] == producer['catalog'] and info['import_preset_sha256'] == proof['import_preset_sha256']
             and info['license'] == 'original-fixture', 'PUBLICATION_METADATA')
        for field, name in [('profile_sha256', 'tests/asset-profile.json'), ('naming_sha256', 'contracts/naming-convention-v1.md'),
            ('toolchain_sha256', 'toolchain.lock.json'), ('exporter_sha256', 'blender-addon/exporter.lock.json'),
            ('validator_sha256', 'pipeline/dependencies/gltf-validator.lock.json')]:
            need(info[field] == self.studio_sources[name], 'PUBLICATION_METADATA_PIN')
        profile = strict(self.data[STUDIO_PREFIX + 'tests/asset-profile.json'])
        need(info['tolerances_sha256'] == sha(self.canonical(profile['tolerances'])), 'PUBLICATION_TOLERANCE_PIN')
        for field in ('same_owner_exact_retry', 'readonly_reopen_exact_retry', 'cross_owner_exact_retry_without_provider'):
            need(observed[field] is True, 'PUBLICATION_RETRY_READBACK')
        need(all(observed[field] is False for field in ('public_ack', 'editor_activation', 'formal_acceptance')), 'PUBLICATION_SCOPE')
        return {'storage_id': receipt['storage_id'], 'receipt_sha256': sha(receipt_raw), 'proof_sha256': sha(proof_raw)}, config, proof

    def visual_review(self, config, proof):
        review = self.obj(self.run('visual_review') + '/review.json')
        runs = config['runs']; consumer = '.local/reviews/' + runs['consumer_id']
        raw = self.raw(consumer + '/project/out/visual.json'); observed = strict(raw)
        need(review['schema'] == 'HH-GT05-COORDINATOR-VISUAL-REVIEW-1'
             and review['consumer_run_id'] == runs['consumer_id'] and review['visual_run_id'] == runs['visual_id']
             and review['observed_sha256'] == sha(raw) and review['full_frame_set'] == len(observed['captures']) == 68
             and review['formal_acceptance'] is False and review['independent_critic'] is False, 'VISUAL_REVIEW_BINDING')
        expected = {'front.png', 'back.png', 'left.png', 'right.png', 'top.png', 'bottom.png',
                    'idle_00.png', 'walk_08.png', 'walk_22.png'}
        need(set(review['images_inspected']) == expected, 'VISUAL_REVIEW_IMAGES')
        for name, digest in review['images_inspected'].items():
            need(sha(self.raw(consumer + '/project/out/' + name)) == digest == observed['captures'][name[:-4]]['sha256'], 'VISUAL_REVIEW_IMAGE_BYTES')
        draws = [frame['draw_calls']['total'] for frame in observed['captures'].values()]
        need(review['draw_calls_min'] == min(draws) and review['draw_calls_max'] == max(draws) <= 150
             and proof['evidence']['visual'] == sha(self.raw('.local/reviews/' + runs['visual_id'] + '/followup.json')), 'VISUAL_REVIEW_DRAW_BINDING')
        return {'captured_frames': 68, 'coordinator_inspected_images': len(expected), 'independent_critic': False}

    def bone_migration(self):
        root = self.run('bone_migration'); config = self.obj(root + '/invocation.json')
        capture = self.obj(root + '/capture.json')
        drivers = [name for name in self.review if name.endswith('/run_bone_migration.py')]
        need(len(drivers) == 1 and self.raw(root + '/driver.snapshot') == self.data[drivers[0]]
             and config['driver_sha256'] == self.review[drivers[0]], 'BONE_DRIVER_PIN')
        spec = importlib.util.spec_from_file_location('gt05_review_bone_driver', self.repo / drivers[0])
        driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
        need(config['schema'] == 'HH-GT05-BONE-MIGRATION-INVOCATION-1'
             and capture['schema'] == 'HH-GT05-BONE-MIGRATION-CAPTURE-1'
             and capture['run_id'] == config['run_id'] == self.manifest['runs']['bone_migration']
             and capture['invocation_sha256'] == sha(self.raw(root + '/invocation.json'))
             and config['cases'] == [row['case'] for row in capture['cases']] == list(driver.CASES)
             and config['baseline_run_id'] == driver.BASELINE and config['baseline_files'] == driver.PINS
             and config['source_files'] == self.studio_sources and config['timeout_seconds_per_case'] == 20,
             'BONE_INVOCATION_BINDING')
        for name, digest in self.studio_sources.items():
            need(sha(self.raw(root + '/source/' + name)) == digest, 'BONE_SOURCE_SNAPSHOT')
        need(config['last_good_run_id'] == self.manifest['runs']['publication'], 'BONE_LAST_GOOD_RUN')
        prefix = self.run('publication') + '/'
        previous = {name[len(prefix):]: digest for name, digest in self.raw_map.items() if name.startswith(prefix)}
        need(previous and config['last_good_graph'] == capture['last_good_graph'] == previous
             and capture['last_good_unchanged'] is True, 'BONE_LAST_GOOD_GRAPH')
        baseline = '.local/reviews/' + driver.BASELINE + '/fixture/'
        originals = {name: self.raw(baseline + name) for name in driver.PINS}
        need({name: sha(raw) for name, raw in originals.items()} == driver.PINS, 'BONE_BASELINE_PIN')
        producer = strict(originals['producer-report.json'])
        refs = driver.dependencies(originals['fixture.glb'], producer)
        need(config['dependencies'] == refs, 'BONE_DERIVED_DEPENDENCIES')
        binary = strict(self.data[STUDIO_PREFIX + 'toolchain.lock.json'])['blender']['executable_sha256']
        driver_path = drivers[0].removeprefix('8-9-hh3d-3/')
        need(config['driver_path'] == driver_path, 'BONE_DRIVER_PATH')
        for row in capture['cases']:
            case = row['case']; lane = root + '/' + case; work = lane + '/work'
            host = self.obj(lane + '/host/capture.json'); invocation = self.obj(lane + '/host/invocation.json')
            expected_sources = {'studio/' + name: digest for name, digest in self.studio_sources.items()}
            expected_sources.update({driver_path: config['driver_sha256'],
                'studio/' + root + '/invocation.json': capture['invocation_sha256']})
            expected_sources.update({'studio/' + work + '/' + name: digest for name, digest in driver.PINS.items()})
            need(invocation['source_files'] == self.obj(lane + '/source-files.json') == expected_sources
                 and invocation['binary_sha256'] == binary and invocation['formal_acceptance'] is False,
                 'BONE_STAGE_SOURCE_BINDING')
            argv = invocation['argv']
            need(len(argv) == 17 and PureWindowsPath(argv[0]).name == 'blender.exe'
                 and PureWindowsPath(argv[0]).as_posix().endswith('/studio/.local/tooling/blender-5.2.1-windows-x64/blender.exe')
                 and argv[1:10] == ['--background', '--factory-startup', '--disable-autoexec', '--offline-mode',
                    '--threads', '1', '--python-exit-code', '17', '--python']
                 and PureWindowsPath(argv[10]).as_posix().endswith('/' + driver_path)
                 and argv[11:] == ['--', '--worker', '--run-id', config['run_id'], '--case', case]
                 and PureWindowsPath(invocation['cwd']).as_posix().endswith('/studio/' + work), 'BONE_STAGE_ARGV')
            need(sha(self.raw(lane + '/host/capture.json')) == row['host_capture_sha256']
                 and set(host['artifacts']) == {'stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json'}
                 and all(sha(self.raw(lane + '/host/' + name)) == digest for name, digest in host['artifacts'].items()),
                 'BONE_HOST_ARTIFACTS')
            started = self.obj(lane + '/host/process-start.json'); exited = self.obj(lane + '/host/process-exit.json')
            need(set(started) == {'pid'} and type(started['pid']) is int and started['pid'] > 0
                 and exited == {'pid': started['pid'], 'exit_code': 0} and type(exited['exit_code']) is int
                 and host['actual_process_exit'] == exited and type(host['wrapper_exit_code']) is int
                 and host['wrapper_exit_code'] == 0 and host['completed'] is True and host['natural_tree_exit'] is True
                 and type(host['active_before_cleanup']) is int and host['active_before_cleanup'] == 0
                 and all(host['job'][field] is True for field in ('configured', 'assigned', 'closed', 'zero_observed'))
                 and all(host['job'][field] is False for field in ('tainted', 'handle_retained', 'create_uncertain', 'close_uncertain'))
                 and host['job']['failed_operations'] == [] and host['job']['active_count'] == 0, 'BONE_ACTUAL_HOST_EXIT')
            need(host['limits'] == {'job_memory_bytes': 2147483648, 'job_user_time_100ns': 150000000,
                'active_process_limit': 4, 'limit_flags': 8716, 'wall_seconds': 20, 'workspace_bytes_limit': 33554432,
                'workspace_limit_is_watchdog': True, 'each_log_capture_bytes': 262144, 'effective_wall_seconds': 20}
                and 0 <= host['elapsed_seconds'] <= 23 and 0 < host['final_workspace_bytes'] <= 33554432, 'BONE_NATIVE_CAPS')
            report_raw = self.raw(lane + '/report.json'); report = strict(report_raw)
            changed = self.raw(work + '/changed.blend')
            need(sha(report_raw) == row['report_sha256'] and sha(changed) == row['changed_blend_sha256']
                 == report['changed_blend_sha256'] != driver.PINS['fixture.blend']
                 and len(changed) == report['changed_blend_bytes'] and 0 < len(changed) <= 1048576,
                 'BONE_CHANGED_BLEND_BINDING')
            marker(self.raw(lane + '/host/stdout.txt'), driver.MARKER.encode(), {'case': case, 'native_pid': started['pid'],
                'report_sha256': sha(report_raw), 'changed_blend_sha256': sha(changed), 'rejection': 'OBSERVED_NAME_SET',
                'migration_required': True, 'formal_acceptance': False})
            need(not self.raw(lane + '/host/stderr.txt').strip(), 'BONE_NATIVE_STDERR')
            need(report['schema'] == 'HH-GT05-BONE-MIGRATION-1' and report['case'] == case
                 and report['run_id'] == config['run_id'] and report['native_pid'] == row['native_pid'] == started['pid']
                 and report['baseline_run_id'] == driver.BASELINE and report['baseline_files'] == driver.PINS
                 and report['pins'] == producer['pins'] and report['dependencies'] == refs, 'BONE_NATIVE_REPORT')
            need(report['admission'] == {'stage': 'installed_admit_observation_after_save_reopen', 'error': 'OBSERVED_NAME_SET'}
                 and row['rejection'] == 'OBSERVED_NAME_SET' and row['last_good_unchanged'] is True,
                 'BONE_ADMISSION_REACHED')
            before = self.obj(lane + '/before-observation.json'); after = self.obj(lane + '/after-observation.json')
            need(sha(self.raw(lane + '/before-observation.json')) == report['before_observation_sha256']
                 and sha(self.raw(lane + '/after-observation.json')) == report['after_observation_sha256']
                 and before == producer['observed'], 'BONE_NATIVE_OBSERVATION')
            before_names = sorted(before['rig']['bones'])
            after_names = sorted((set(before_names) - {driver.BONE}) | ({driver.NEW_BONE} if case == 'rename' else set()))
            need(report['native_before']['bones'] == before_names and report['native_after']['bones'] == after_names
                 == sorted(after['rig']['bones']) and report['bone_diff'] == {'missing': [driver.BONE],
                     'added': [driver.NEW_BONE] if case == 'rename' else []}
                 and report['native_before']['sockets'] == report['native_after']['sockets']
                 == {name: value['bone'] for name, value in before['sockets'].items()}, 'BONE_NATIVE_DIFF')
            need(report['migration_required'] is True and report['unsupported'] is True
                 and report['accepted_mapping'] is False
                 and report['proposed_mapping'] == {driver.BONE: driver.NEW_BONE if case == 'rename' else None}
                 and all(report[field] is False for field in ('automatic_migration_performed', 'export_performed',
                     'publication_performed', 'public_ack', 'formal_acceptance')), 'BONE_MAPPING_SCOPE')
            expected_work = {work + '/' + name for name in (*driver.PINS, 'changed.blend')}
            need({name for name in self.raw_map if name.startswith(work + '/')} == expected_work
                 and all(self.raw(work + '/' + name) == raw for name, raw in originals.items()), 'BONE_NO_EXPORT')
        need(capture['migration_required'] is True and all(capture[field] is False
             for field in ('automatic_migration_performed', 'public_ack', 'formal_acceptance')), 'BONE_CAPTURE_SCOPE')
        return {'cases': list(driver.CASES), 'rejection': 'OBSERVED_NAME_SET', 'migration_required': True,
            'accepted_mapping': False, 'affected_ids': refs['affected_ids'], 'last_good_unchanged': True}

    def git(self, ref):
        need(ref in ('index', 'HEAD'), 'GIT_REF')
        files = {**self.source, **self.review, self.manifest_path.relative_to(self.repo).as_posix(): sha(self.manifest_raw)}
        names = sorted(files)
        specs = [(':' if ref == 'index' else 'HEAD:') + name for name in names]
        result = subprocess.run(['git', '-C', str(self.repo), 'cat-file', '--batch'],
            input=('\n'.join(specs) + '\n').encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=30)
        need(result.returncode == 0, 'GIT_READ_FAILED')
        offset = 0
        for name in names:
            end = result.stdout.find(b'\n', offset); header = result.stdout[offset:end].split()
            need(end >= offset and len(header) == 3 and header[1] == b'blob', 'GIT_BLOB_MISSING')
            count = int(header[2]); start = end + 1; raw = result.stdout[start:start + count]
            need(len(raw) == count and result.stdout[start + count:start + count + 1] == b'\n'
                 and sha(raw) == files[name], 'GIT_BLOB_MISMATCH')
            offset = start + count + 1
        need(offset == len(result.stdout), 'GIT_EXTRA_OUTPUT')
        return {'ref': ref, 'blobs': len(names)}


def verify(manifest_path, repo_root=None, git_ref=None):
    try:
        package = Package(manifest_path, repo_root or Path(__file__).resolve().parents[4])
        units = package.units(); native = package.snapshot_native(); staged = package.staged_cut(units)
        publication, config, proof = package.publication(units)
        visual = package.visual_review(config, proof)
        bone = package.bone_migration()
        git = package.git(git_ref) if git_ref is not None else None
        return {'schema': 'HH-GT05-REVIEW-VERIFY-1', 'verified': True, 'formal_acceptance': False,
            'manifest_sha256': sha(package.manifest_raw), 'source_files': len(package.source),
            'review_files': len(package.review), 'raw_files': len(package.raw_map),
            'units': units, 'snapshot_native': native, 'snapshot_staged': staged,
            'publication': publication, 'visual_review': visual, 'bone_migration': bone, 'git': git}
    except Rejected:
        raise
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError, RecursionError, subprocess.SubprocessError):
        raise Rejected('EVIDENCE_SCHEMA') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('manifest.json'))
    parser.add_argument('--repo-root', type=Path)
    parser.add_argument('--git-ref', choices=('index', 'HEAD'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.manifest, args.repo_root, args.git_ref)
        if args.output is not None:
            repo = (args.repo_root or Path(__file__).resolve().parents[4]).absolute()
            manifest = strict(read_file(args.manifest.absolute()))
            protected = {repo / name for key in ('source_files', 'review_files') for name in manifest[key]}
            protected.update(repo / STUDIO_PREFIX / name for name in manifest['raw_files'])
            protected.add(args.manifest.absolute())
            target = args.output.absolute()
            need(target not in protected, 'OUTPUT_IS_INPUT')
            for part in (target.parent, *target.parent.parents):
                info = part.lstat()
                need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'OUTPUT_REPARSE')
            with target.open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except (Rejected, OSError) as error:
        print(json.dumps({'verified': False, 'error': getattr(error, 'code', 'OUTPUT_IO'), 'formal_acceptance': False}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
