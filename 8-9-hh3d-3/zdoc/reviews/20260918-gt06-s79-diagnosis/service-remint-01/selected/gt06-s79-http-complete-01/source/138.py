"""Read-only, resumable GT05 evidence admission; never runs an engine or publishes.

Local host records are trusted capture inputs, not cryptographic attestations of
an adversarial host. Every success binds their raw bytes, owned invocation,
natural process exit, frozen source, payload and actual observation. Summaries
and PASS flags cannot replace those records. Historical snapshots may be read
for diagnostics, but never authorize publication against different source.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import copy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Callable


class RunRejected(ValueError):
    """Stable machine-readable error; never includes a host path or raw input."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VerifiedRun:
    proof: dict
    payloads: dict[str, bytes]


def need(condition, code):
    if not condition:
        raise RunRejected(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'JSON_DUPLICATE_KEY')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(RunRejected('JSON_NONFINITE')))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise RunRejected('JSON_SYNTAX') from None
    need(type(value) is dict, 'JSON_OBJECT')
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop(); count += 1
        need(depth <= 40 and count <= 250000, 'JSON_GRAPH')
        if type(item) is dict:
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth + 1) for v in item)
        elif type(item) is float:
            need(math.isfinite(item), 'JSON_NONFINITE')
    return value


def safe_name(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name
         and not PureWindowsPath(name).drive and not PurePosixPath(name).is_absolute()
         and all(part not in ('', '.', '..') for part in name.split('/')), 'SOURCE_PATH')
    return name


def digest_value(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'DIGEST_FORMAT')
    return value


# Mandatory loaded-host dependencies and explicit native child dependencies.
# These are contract requirements, never inferred from a caller's manifest.
HOST = frozenset('''blender-addon/ipc_client.py godot-addon/cli_job.py
host/blender/__init__.py host/blender/deadline.py host/blender/export_job.py
host/blender/glb_preflight.py host/blender/ui_host.py host/core/limits.py
host/core/private_store.py host/core/safe_create.py host/core/safe_open.py
pipeline/__init__.py pipeline/native_job.py pipeline/run_diagnostic.py
protocol/__init__.py protocol/_rfc8785/__init__.py protocol/_rfc8785/_impl.py
protocol/core.py'''.split())
PRODUCER_PINS = frozenset('''blender-addon/exporter.lock.json
contracts/naming-convention-v1.md fixtures/assets-src/fixture-source.json
pipeline/naming.py pipeline/producer/__init__.py pipeline/producer/contract.py
pipeline/producer/run_blender.py tests/asset-profile.json toolchain.lock.json'''.split())
DECODE = frozenset('''pipeline/accessor_values.py pipeline/glb_container.py
pipeline/glb_semantics.py pipeline/png_decode.py pipeline/preflight.py'''.split())
VALIDATION = HOST | DECODE | {'pipeline/run_validation.py'}
AUTHORED = ('project.godot', 'authored.tscn', 'authored.gd', 'authored_material.tres', 'probe.gd')
INPUTS = ('fixture.glb', 'manifest.json', 'producer-report.json')
CONSUMER = VALIDATION | {'pipeline/run_consumer.py', 'pipeline/godot/consumer.py',
    'pipeline/naming.py', 'pipeline/producer/__init__.py', 'pipeline/producer/contract.py',
    'tests/asset-profile.json', 'contracts/naming-convention-v1.md', 'toolchain.lock.json'} | {
    'pipeline/godot/' + name for name in AUTHORED}
DEPENDENCY_FILES = frozenset('''package/ISSUES.md package/LICENSE package/NOTICES
package/README.md package/gltf_validator.dart.js package/index.js package/module.mjs
package/package.json package/validation.schema.json'''.split())
COMPARATORS = DECODE | {'pipeline/godot/consumer.py', 'pipeline/naming.py',
    'pipeline/producer/__init__.py', 'pipeline/producer/contract.py'}
REJECTION_CASES = frozenset('''mesh-scale model-axis world-bounds missing-bone renamed-bone
bone-parent inverse-bind skin-weight clip-trim clip-loop animation-keys animation-optimizer
animation-compression missing-texture texture-pixels material-color material-roughness
socket-world authored-socket socket-bone authored-script authored-material authored-color
lod-switch collider-ray nav-region sampled-bone-pose'''.split())


class _Verifier:
    def __init__(self, studio, current, phase_guard: Callable[[], None] | None = None):
        need(phase_guard is None or callable(phase_guard), 'PHASE_GUARD')
        self.phase_guard = phase_guard
        self.guard_failure = None
        self.guard()
        need(type(current) is bool, 'CURRENT_SOURCE_POLICY')
        self.studio = Path(studio).absolute()
        self.current = current
        self.reads = {}
        self.sources = {}
        self.stale = set()
        self.qualifiers = {}
        self.evidence = {}

    def guard(self):
        """The owner controls the absolute deadline and Stop; preserve its error."""
        if self.phase_guard is not None:
            try:
                self.phase_guard()
            except BaseException as error:
                self.guard_failure = error
                raise

    def read(self, path, cap=16 * 1024 * 1024):
        self.guard()
        path = Path(path).absolute()
        need(path.is_relative_to(self.studio), 'EVIDENCE_OUTSIDE_ROOT')
        for part in (path, *path.parents):
            self.guard()
            try:
                info = part.lstat()
            except OSError:
                raise RunRejected('EVIDENCE_MISSING') from None
            need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'EVIDENCE_REPARSE')
        self.guard()
        try:
            need(path.is_file() and 0 <= path.stat().st_size <= cap, 'EVIDENCE_SIZE')
            raw = path.read_bytes()
        except OSError:
            raise RunRejected('EVIDENCE_READ') from None
        self.guard()
        need(len(raw) <= cap, 'EVIDENCE_SIZE')
        key = path.relative_to(self.studio).as_posix()
        old = self.reads.setdefault(key, sha(raw))
        need(old == sha(raw), 'EVIDENCE_CHANGED_DURING_VERIFY')
        return raw

    def obj(self, path, cap=16 * 1024 * 1024):
        raw = self.read(path, cap)
        value = strict(raw)
        self.guard()
        return raw, value

    def root(self, run_id):
        need(type(run_id) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run_id), 'RUN_ID')
        return self.studio / '.local/reviews' / run_id

    def source(self, root, required, *, admission=False, producer=False):
        self.guard()
        map_name = 'admission-source-files.json' if admission else 'source-files.json'
        folder = 'admission-source' if admission else 'source'
        raw_map, files = self.obj(root / map_name, 1024 * 1024)
        need(bool(files) and set(required) <= set(files) and len(files) <= 512, 'SOURCE_CLOSURE')
        snapshots = {}
        aliases = set()
        for name, digest in files.items():
            self.guard()
            safe_name(name); digest_value(digest)
            need(name.casefold() not in aliases, 'SOURCE_ALIAS')
            aliases.add(name.casefold())
            slot = name if producer else sha(name.encode()) + Path(name).suffix
            raw = self.read(root / folder / slot)
            need(sha(raw) == digest, 'SOURCE_SNAPSHOT_HASH')
            snapshots[name] = raw
            if not name.startswith('.local/'):
                current = self.read(self.studio / name)
                if sha(current) != digest:
                    self.stale.add(name)
                    need(not self.current, 'SOURCE_STALE')
        recovery = root / 'snapshot-recovery.json'
        qualifier = 'PRE_EXECUTION_SOURCE_SNAPSHOT'
        if recovery.exists():
            _, recovered = self.obj(recovery)
            need(recovered['mode'] == 'POST_EXECUTION_RECOVERY_FROM_EXACT_HASH_EQUAL_BYTES'
                 and recovered['does_not_claim_pre_execution_copy'] is True, 'RECOVERY_QUALIFIER')
            item = recovered['maps'][map_name]
            need(item['map_sha256'] == sha(raw_map) and set(item['entries']) == set(files), 'RECOVERY_MAP')
            for name, digest in files.items():
                self.guard()
                row = item['entries'][name]
                need(row['sha256'] == digest and row['snapshot'] == folder + '/' +
                    sha(name.encode()) + Path(name).suffix, 'RECOVERY_SNAPSHOT')
            qualifier = recovered['mode']
        self.qualifiers[root.name + '/' + map_name] = qualifier
        self.sources[root.name + '/' + map_name] = files
        return files, snapshots

    def host(self, root, capture_hash, files, *, argv_tail=None, binary=None, cwd=None,
             producer=False):
        self.guard()
        raw, capture = self.obj(root / 'capture.json', 1024 * 1024)
        need(sha(raw) == digest_value(capture_hash), 'CAPTURE_HASH')
        required = {'stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json'}
        need(set(capture['artifacts']) == required, 'CAPTURE_ARTIFACT_SET')
        artifacts = {name: self.read(root / name, 262144) for name in required}
        need(all(sha(raw) == capture['artifacts'][name] for name, raw in artifacts.items()), 'CAPTURE_ARTIFACT_HASH')
        started, exited = strict(artifacts['process-start.json']), strict(artifacts['process-exit.json'])
        need(set(started) == {'pid'} and type(started['pid']) is int and started['pid'] > 0
             and set(exited) == {'pid', 'exit_code'} and type(exited['pid']) is int
             and type(exited['exit_code']) is int and exited['exit_code'] == 0
             and exited['pid'] == started['pid'] and capture['actual_process_exit'] == exited
             and type(capture['wrapper_exit_code']) is int and capture['wrapper_exit_code'] == 0,
             'CAPTURE_PROCESS_BINDING')
        job = capture['job']
        need(capture['completed'] is True and capture['natural_tree_exit'] is True
             and type(capture['active_before_cleanup']) is int and capture['active_before_cleanup'] == 0
             and job['closed'] is True and job['zero_observed'] is True and job['tainted'] is False
             and job['handle_retained'] is False and job['assigned'] is True and job['configured'] is True
             and job['active_count'] == 0 and job['failed_operations'] == []
             and job['create_uncertain'] is False and job['close_uncertain'] is False
             and 'failure' not in capture and 'cleanup_failure' not in capture, 'CAPTURE_NATURAL_EXIT')
        limits = capture['limits']
        need(0 < limits['effective_wall_seconds'] <= limits['wall_seconds'] <= 20
             and 0 <= capture['elapsed_seconds'] <= limits['effective_wall_seconds'] + 3
             and limits['job_memory_bytes'] <= 2147483648 and limits['job_user_time_100ns'] <= 150000000
             and limits['active_process_limit'] <= 4 and limits['each_log_capture_bytes'] <= 262144
             and capture['final_workspace_bytes'] <= limits['workspace_bytes_limit'] <= 33554432,
             'CAPTURE_LIMITS')
        _, invocation = self.obj(root / 'invocation.json', 1024 * 1024)
        need(invocation['source_files'] == files and invocation['formal_acceptance'] is False, 'INVOCATION_SOURCE_MAP')
        args = invocation['argv']
        need(type(args) is list and args and all(type(arg) is str for arg in args), 'INVOCATION_ARGV')
        if argv_tail is not None:
            need(args[1:] == argv_tail, 'INVOCATION_ARGV')
        if cwd is not None:
            need(invocation['cwd'] == str(cwd), 'INVOCATION_CWD')
        if binary is not None:
            need(invocation['binary_sha256'] == binary, 'INVOCATION_BINARY')
        digest_value(invocation['binary_sha256'])
        need(not artifacts['stderr.txt'].strip(), 'CAPTURE_STDERR')
        if producer:
            expected = {
                b'Armature must be the parent of skinned meshArmature is selected by its name, but may be false in case of instances': 4,
                b'More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.': 1}
            found = []
            for line in artifacts['stdout.txt'].splitlines():
                if any(word in line for word in (b'WARNING', b'ERROR', b'Error:')):
                    match = re.fullmatch(rb'\d{2}:\d{2}:\d{2} \| WARNING: (.+)', line)
                    need(match is not None, 'PRODUCER_LOG')
                    found.append(match[1])
            need(Counter(found) == expected, 'PRODUCER_WARNINGS')
        else:
            need(not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', artifacts['stdout.txt']), 'CAPTURE_LOG')
        return capture, artifacts['stdout.txt'], invocation

    @staticmethod
    def marker(stdout, prefix, expected):
        rows = [strict(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
        need(rows == [expected], 'COMPLETION_MARKER')

    def producer(self, run_id):
        self.guard()
        root = self.root(run_id)
        raw_summary, summary = self.obj(root / 'diagnostic.json')
        files, snapshots = self.source(root, HOST | PRODUCER_PINS, producer=True)
        need(summary['run_id'] == run_id and summary['source_files'] == files, 'PRODUCER_SOURCE_MAP')
        raw, report = self.obj(root / 'fixture/producer-report.json', 1048576)
        need(sha(raw) == summary['report_sha256'], 'PRODUCER_REPORT_HASH')
        pins = report['pins']
        need(set(pins['source_files']) == PRODUCER_PINS and all(files.get(k) == v for k, v in pins['source_files'].items())
             and pins['source_sha256'] == sha(canonical(pins['source_files'])), 'PRODUCER_SOURCE_PINS')
        for field, name in [('profile_sha256', 'tests/asset-profile.json'),
            ('naming_sha256', 'contracts/naming-convention-v1.md'), ('toolchain_sha256', 'toolchain.lock.json')]:
            need(pins[field] == files[name], 'PRODUCER_TOOL_PINS')
        lock, exporter = strict(snapshots['toolchain.lock.json']), strict(snapshots['blender-addon/exporter.lock.json'])
        need(pins['blender_binary_sha256'] == lock['blender']['executable_sha256']
             and pins['exporter_files_sha256'] == sha(canonical(exporter['files']))
             and pins['exporter_file_count'] == len(exporter['files'])
             and pins['exporter_version'] == exporter['exporter_version'], 'PRODUCER_TOOL_PINS')
        need(report['schema'] == 'HH-GT05-PRODUCER-1' and report['profile_id'] == 'gt05-original-fixture-v1'
             and report['license'] == 'original-fixture' and report['external_inputs'] == []
             and report['variant'] in ('baseline', 'edited') and summary['variant'] == report['variant']
             and report['source_reopened_exact'] is True and report['export_preserved_source'] is True
             and report['formal_acceptance'] is False and report['artifacts'] == summary['artifacts']
             and report['observed_sha256'] == sha(canonical(report['observed']))
             and pins['settings_sha256'] == sha(canonical(report['settings'])), 'PRODUCER_CONTRACT')
        need(set(report['artifacts']) == {'fixture.glb', 'fixture.blend'}, 'PRODUCER_SLOT_SET')
        payloads = {}
        for name, item in report['artifacts'].items():
            payloads[name] = self.read(root / 'fixture' / name, 1048576)
            need(item == {'sha256': sha(payloads[name]), 'bytes': len(payloads[name])} and len(payloads[name]) > 0,
                 'PRODUCER_PAYLOAD')
        _, stdout, _ = self.host(root / 'host', summary['host_capture_sha256'], files,
            argv_tail=['--background', '--factory-startup', '--disable-autoexec', '--offline-mode', '--threads', '1',
                '--python-exit-code', '17', '--python', str(self.studio / 'pipeline/producer/run_blender.py'),
                '--', str(root / 'fixture'), report['variant']],
            binary=pins['blender_binary_sha256'], cwd=root / 'fixture', producer=True)
        self.marker(stdout, b'GT05_PRODUCER_COMPLETE ', {'variant': report['variant'],
            'source_sha256': pins['source_sha256'], 'report_sha256': sha(raw),
            'blend_bytes': len(payloads['fixture.blend']), 'glb_bytes': len(payloads['fixture.glb']), 'formal_acceptance': False})
        return {'id': run_id, 'report': report, 'raw': raw, 'payloads': payloads, 'summary_sha256': sha(raw_summary)}

    def validation(self, run_id, producer):
        self.guard()
        root = self.root(run_id); prefix = root.relative_to(self.studio).as_posix() + '/'
        summary_raw, summary = self.obj(root / 'validation.json')
        need(summary['run_id'] == run_id and summary['upstream_run_id'] == producer['id'], 'VALIDATION_UPSTREAM')
        raw, manifest = self.obj(root / 'manifest.json')
        need(sha(raw) == summary['manifest_sha256'], 'MANIFEST_HASH')
        payloads = {'fixture.glb': self.read(root / 'fixture.glb', 1048576),
            'producer-report.json': self.read(root / 'producer-report.json', 1048576), 'manifest.json': raw}
        need(payloads['fixture.glb'] == producer['payloads']['fixture.glb']
             and payloads['producer-report.json'] == producer['raw'], 'VALIDATION_PRODUCER_BINDING')
        lock_raw, lock = self.obj(root / 'gltf-validator.lock.json')
        _, installed_lock = self.obj(self.studio / 'pipeline/dependencies/gltf-validator.lock.json')
        need(set(lock['files']) == DEPENDENCY_FILES and lock['version'] == '2.0.0-dev.3.10'
             and lock['name'] == 'gltf-validator' and lock['files'] == installed_lock['files'], 'DEPENDENCY_LOCK_SET')
        required = VALIDATION | {'pipeline/validate_glb.cjs', 'pipeline/dependencies/node.lock.json',
            'pipeline/dependencies/gltf-validator.lock.json'} | {prefix + name for name in
            ('fixture.glb', 'admission.json', 'gltf-validator.lock.json')} | {
            prefix + 'dependency/' + name for name in DEPENDENCY_FILES}
        files, frozen = self.source(root, required)
        need(frozen['pipeline/dependencies/gltf-validator.lock.json'] == lock_raw
             and frozen[prefix + 'gltf-validator.lock.json'] == lock_raw
             and frozen[prefix + 'fixture.glb'] == payloads['fixture.glb'], 'VALIDATOR_INPUT_SNAPSHOT')
        need(strict(frozen[prefix + 'admission.json']) == {'schema': 'HH-GT05-VALIDATOR-INPUT-1',
            'artifact_sha256': sha(payloads['fixture.glb'])}, 'VALIDATOR_ADMISSION_INPUT')
        for name, digest in lock['files'].items():
            need(files[prefix + 'dependency/' + name] == digest
                 and sha(self.read(root / 'dependency' / name)) == digest, 'DEPENDENCY_HASH')
        node = strict(frozen['pipeline/dependencies/node.lock.json'])
        host, stdout, _ = self.host(root / 'host', summary['host_capture_sha256'], files,
            argv_tail=['--max-old-space-size=256', str(self.studio / 'pipeline/validate_glb.cjs'), str(root)],
            binary=node['binary_sha256'], cwd=root)
        validator_raw, validator = self.obj(root / 'validator.json')
        need(validator['schema'] == 'HH-GT05-KHRONOS-1' and validator['artifact_sha256'] == sha(payloads['fixture.glb'])
             and validator['validator_version'] == lock['version']
             and validator['dependency_lock_sha256'] == sha(lock_raw)
             and validator['external_resource_requested'] is False, 'VALIDATOR_BINDING')
        issues = validator['result']['issues']
        need(type(issues['numErrors']) is int and issues['numErrors'] == 0
             and type(issues['numWarnings']) is int and issues['numWarnings'] == 0
             and issues['truncated'] is False
             and all(type(row['severity']) is int and row['severity'] >= 2 for row in issues['messages'])
             and validator['result']['validatorVersion'] == lock['version'], 'VALIDATOR_ISSUES')
        self.marker(stdout, b'GT05_KHRONOS_COMPLETE ', {'artifact_sha256': sha(payloads['fixture.glb']),
            'report_sha256': sha(validator_raw)})
        admission_files, admission_frozen = self.source(root, VALIDATION | {'pipeline/admission_worker.py',
            prefix + 'admission/fixture.glb', prefix + 'admission/expected.json'}, admission=True)
        need(admission_frozen[prefix + 'admission/fixture.glb'] == payloads['fixture.glb']
             and strict(admission_frozen[prefix + 'admission/expected.json']) == {
                 'artifact_sha256': sha(payloads['fixture.glb'])}, 'ADMISSION_INPUT_SNAPSHOT')
        admission_host, admission_stdout, admission_invocation = self.host(root / 'admission-host',
            summary['admission_capture_sha256'], admission_files, argv_tail=['-B',
                str(self.studio / 'pipeline/admission_worker.py'), str(root / 'admission')], cwd=root / 'admission')
        report_raw, report = self.obj(root / 'preflight.json')
        semantic_raw, semantic = self.obj(root / 'semantic.json')
        outputs = {'artifact_sha256': sha(payloads['fixture.glb']), 'preflight_sha256': sha(report_raw),
                   'semantic_sha256': sha(semantic_raw)}
        self.marker(admission_stdout, b'GT05_ADMISSION_COMPLETE ', outputs)
        need(summary['admission_outputs'] == outputs and report['artifact_sha256'] == outputs['artifact_sha256']
             and report['artifact_bytes'] == len(payloads['fixture.glb'])
             and report['semantic_sha256'] == sha(canonical(semantic))
             and report['semantic_hash_domain'] == 'decoded-core-indexed-v1/json-sort-compact', 'ADMISSION_OUTPUT_BINDING')
        need(self.read(root / 'admission/preflight.json') == report_raw
             and self.read(root / 'admission/semantic.json') == semantic_raw, 'ADMISSION_OUTPUT_COPY')
        expected_images = producer['report']['observed']['images']
        need(len(report['images']) == len(expected_images) and {row['name'] for row in report['images']} == set(expected_images)
             and all(all(row[k] == expected_images[row['name']][k] for k in ('width', 'height', 'rgba8_sha256'))
                     for row in report['images']), 'ADMISSION_IMAGE_BINDING')
        p = producer['report']
        expected = {'schema': 'HH-GT05-ASSET-MANIFEST-1', 'profile_id': p['profile_id'], 'license': p['license'],
            'external_inputs': [], 'variant': p['variant'], 'source_pins': p['pins'], 'artifacts': p['artifacts'],
            'producer_report_sha256': sha(producer['raw']), 'preflight_sha256': sha(report_raw),
            'validator_sha256': sha(validator_raw), 'semantic_sha256': report['semantic_sha256'],
            'semantic_hash_domain': report['semantic_hash_domain'], 'catalog': p['catalog'],
            'formal_acceptance': False, 'public_ack': False}
        need(manifest == expected, 'MANIFEST_BINDING')
        return {'id': run_id, 'manifest': manifest, 'payloads': payloads, 'semantic': semantic,
            'semantic_raw_sha256': sha(semantic_raw), 'summary_sha256': sha(summary_raw),
            'admission_sha256': sha(canonical({'capture': summary['admission_capture_sha256'], 'outputs': outputs})),
            'khronos_sha256': sha(canonical({'capture': summary['host_capture_sha256'], 'validator': sha(validator_raw)})),
            'python_binary_sha256': admission_invocation['binary_sha256'], 'node_binary_sha256': node['binary_sha256']}

    def comparator_current(self, files):
        installed = Path(__file__).resolve().parents[1]
        # A verifier may inspect a relocated copy. Python still imports the
        # installed comparator; equality with files in that copy alone would
        # silently execute a different comparator than the captured one.
        return all(name in files and sha(self.read(self.studio / name)) == files[name]
            and self.installed_hash(installed / name) == files[name] for name in COMPARATORS)

    def installed_hash(self, path):
        self.guard()
        digest = sha(path.read_bytes())
        self.guard()
        return digest

    def consumer(self, run_id, producer, validation, *, phase='baseline', consumer_id=None, previous=None):
        self.guard()
        root = self.root(run_id); consumer_id = consumer_id or run_id
        project = self.root(consumer_id) / 'project'
        prefix = project.relative_to(self.studio).as_posix() + '/'
        summary_raw, summary = self.obj(root / ('consumer.json' if phase == 'baseline' else 'followup.json'))
        need(summary['validator_run_id'] == (None if phase == 'visual' else validation['id']), 'CONSUMER_VALIDATION_BINDING')
        if phase == 'baseline':
            need(summary['run_id'] == run_id and summary['schema'] == 'HH-GT05-CONSUMER-DIAGNOSTIC-1', 'CONSUMER_SUMMARY')
        else:
            need(summary['phase'] == phase and summary['consumer_run_id'] == consumer_id
                 and summary['schema'] == 'HH-GT05-CONSUMER-FOLLOWUP-1', 'CONSUMER_SUMMARY')
        files, frozen = self.source(root, CONSUMER | {prefix + name for name in AUTHORED} | {
            prefix + 'input/' + name for name in (*INPUTS, 'consumer.json')})
        input_raw = {name: frozen[prefix + 'input/' + name] for name in (*INPUTS, 'consumer.json')}
        need(all(input_raw[name] == validation['payloads'][name] for name in INPUTS), 'CONSUMER_FROZEN_INPUT')
        seed = strict(input_raw['consumer.json'])
        inputs = {name: sha(input_raw[name]) for name in INPUTS}
        authored = {name: sha(frozen[prefix + name]) for name in AUTHORED}
        need(seed['input_sha256'] == inputs and seed['authored_sha256'] == authored
             and all(frozen[prefix + name] == frozen['pipeline/godot/' + name] for name in AUTHORED), 'CONSUMER_SEED')
        preset_before = self.read(root / 'input-preset.snapshot', 1048576)
        preset_after = self.read(root / 'imported-preset.snapshot', 1048576)
        need(sha(preset_before) == summary['import_preset_before_sha256']
             and sha(preset_after) == summary['import_preset_after_sha256'], 'CONSUMER_PRESET_SNAPSHOT')
        if phase == 'baseline':
            need(sha(preset_before) == seed['preset_sha256'], 'CONSUMER_IMPORT_PRESET')
        if phase == 'visual':
            need(preset_before == preset_after, 'VISUAL_PRESET_CHANGED')
        for field, name in [('profile_sha256', 'tests/asset-profile.json'),
            ('naming_sha256', 'contracts/naming-convention-v1.md'), ('toolchain_sha256', 'toolchain.lock.json')]:
            need(seed[field] == files[name] == producer['report']['pins'][field], 'CONSUMER_PINS')
        lock = strict(frozen['toolchain.lock.json'])['godot']
        stages = ('visual',) if phase == 'visual' else ('import', phase)
        need(set(summary['host_captures']) == set(stages), 'CONSUMER_STAGE_SET')
        for stage in stages:
            args = (['--headless', '--editor', '--path', str(project), '--import'] if stage == 'import' else
                ([] if stage == 'visual' else ['--headless']) + ['--path', str(project), '--script',
                    'res://probe.gd', '--', '--phase', stage])
            host, stdout, _ = self.host(root / (stage + '-host'), summary['host_captures'][stage], files,
                argv_tail=args, binary=lock['gui_sha256'], cwd=project)
        raw, observed = self.obj(project / 'out' / (phase + '.json'))
        need(sha(raw) == summary['observation_sha256'] and observed['schema'] == 'HH-GT05-GODOT-OBSERVATION-1'
             and observed['phase'] == phase and observed['formal_acceptance'] is False
             and type(observed['pid']) is int and observed['pid'] == host['actual_process_exit']['pid']
             and observed['input_sha256'] == inputs and observed['authored_sha256'] == authored
             and observed['consumer_sha256'] == sha(input_raw['consumer.json']), 'CONSUMER_OBSERVATION_BINDING')
        engine = observed['engine']
        need((engine['major'], engine['minor'], engine['patch'], engine['status']) == (4, 7, 2, 'stable')
             and str(engine['hash']).startswith('ed1daf0bf'), 'CONSUMER_ENGINE')
        self.marker(stdout, b'GT05_GODOT_OBSERVED ', {'phase': phase, 'pid': observed['pid'],
            'report_sha256': sha(raw), 'formal_acceptance': False})
        comparable = self.comparator_current(files)
        checks = None
        if comparable:
            from studio.pipeline.godot.consumer import compare_observation, ConsumerRejected, PRESET
            need(seed['preset_sha256'] == sha(PRESET.encode()), 'CONSUMER_IMPORT_PRESET')
            self.guard()
            try:
                checks = compare_observation(producer['report'], observed)
            except (ConsumerRejected, KeyError, TypeError, ValueError, IndexError):
                raise RunRejected('CONSUMER_COMPARISON') from None
            self.guard()
            need(checks == summary['comparison'] == self.obj(root / 'comparison.json')[1], 'CONSUMER_COMPARISON_SUMMARY')
        else:
            need(not self.current, 'COMPARATOR_STALE')
        if phase != 'baseline':
            need(previous is not None, 'FOLLOWUP_PREVIOUS_REQUIRED')
            need(preset_before == previous['preset_after'], 'FOLLOWUP_PRESET_CONTINUITY')
            need(summary['previous_input_sha256'] == {name: sha(value) for name, value in previous['input_raw'].items()},
                 'FOLLOWUP_CONTINUITY')
            need(all(self.read(root / 'previous-input' / name) == value for name, value in previous['input_raw'].items()),
                 'FOLLOWUP_PREVIOUS_BYTES')
            need(observed['authored'] == previous['observed']['authored']
                 and observed['authored_sha256'] == previous['observed']['authored_sha256'], 'REIMPORT_AUTHORED')
            if phase == 'reimport':
                need(inputs['fixture.glb'] != previous['observed']['input_sha256']['fixture.glb'], 'REIMPORT_CHANGED_GLB')
        if phase == 'visual':
            # New visual metadata explicitly proves that native imported PBR was
            # visible during capture; the old override-only run cannot pass.
            need(observed.get('visual_material', {}).get('override_disabled') is True, 'VISUAL_ORIGINAL_PBR')
            labels = {'front', 'back', 'left', 'right', 'top', 'bottom'} | {
                f'{clip}_{frame:02d}' for clip in ('idle', 'walk') for frame in range(31)}
            need(set(observed['captures']) == labels, 'VISUAL_CAPTURE_SET')
            need({path.name for path in (project / 'out').glob('*.png')} == {label + '.png' for label in labels},
                 'VISUAL_CAPTURE_FILE_SET')
            from studio.pipeline.godot.consumer import _verify_visual_png, ConsumerRejected
            decoded = set()
            for label, capture in observed['captures'].items():
                self.guard()
                png = self.read(project / 'out' / (label + '.png'), 1048576)
                need(sha(png) == capture['sha256'] and capture['pid'] == observed['pid']
                     and capture['width'] == capture['height'] == 640
                     and png[:8] == b'\x89PNG\r\n\x1a\n'
                     and int.from_bytes(png[16:20], 'big') == int.from_bytes(png[20:24], 'big') == 640,
                     'VISUAL_CAPTURE_BYTES')
                if capture['sha256'] not in decoded:
                    self.guard()
                    try:
                        _verify_visual_png(png)
                    except ConsumerRejected:
                        raise RunRejected('VISUAL_CAPTURE_DECODE') from None
                    self.guard()
                    decoded.add(capture['sha256'])
            need(comparable, 'VISUAL_COMPARATOR_STALE')
        return {'id': run_id, 'summary_sha256': sha(summary_raw), 'summary': summary, 'observed': observed,
            'observation_sha256': sha(raw), 'input_raw': input_raw, 'checks': checks, 'comparable': comparable,
            'source_map_sha256': sha(self.read(root / 'source-files.json')), 'files': files, 'seed': seed,
            'godot_binary_sha256': lock['gui_sha256'], 'preset_after': preset_after,
            'preset_readback': {'before_sha256': sha(preset_before), 'after_sha256': sha(preset_after),
                'scope': 'exact authored input and generated config bytes; not a complete generated-parameter parser'}}

    def rejections(self, run_id, baseline, validation):
        self.guard()
        root = self.root(run_id)
        raw, report = self.obj(root / 'output/result.json', 262144)
        need(report['schema'] == 'HH-GT05-NATIVE-OBSERVATION-REJECTIONS-1', 'REJECTIONS_SCHEMA')
        _, summary = self.obj(root / 'rejections.json')
        need(summary['schema'] == 'HH-GT05-REJECTIONS-CAPTURE-1' and summary['run_id'] == run_id
             and summary['consumer_run_id'] == baseline['id'] and summary['validator_run_id'] == validation['id']
             and summary['result_sha256'] == sha(raw), 'REJECTIONS_SUMMARY')
        required = (CONSUMER - {'pipeline/godot/' + name for name in AUTHORED}
            - {'tests/asset-profile.json', 'contracts/naming-convention-v1.md', 'toolchain.lock.json'}) | {
            'tests/pipeline/check_native_observation_rejections.py', 'pipeline/run_rejections.py'}
        files, _ = self.source(root, required)
        # The child imports its own execution closure; the supervisor also pins
        # authored assets and its driver. Both closures must be checked, rather
        # than requiring those additional supervisor files to be Python imports.
        need(set(report['execution_source_files']) <= set(files), 'REJECTIONS_SOURCE_CLOSURE')
        for name, digest in report['execution_source_files'].items():
            self.guard()
            safe_name(name); digest_value(digest)
            need(not name.startswith('.local/') and sha(self.read(self.studio / name)) == digest, 'REJECTIONS_SOURCE_STALE')
            if name in files:
                need(files[name] == digest, 'REJECTIONS_SOURCE_BINDING')
        capture_raw = self.read(root / 'host/capture.json')
        _, stdout, _ = self.host(root / 'host', summary['host_capture_sha256'], files,
            argv_tail=['-B', str(self.studio / 'tests/pipeline/check_native_observation_rejections.py'),
                '--consumer-root', str(self.root(baseline['id'])), '--validation-root', str(self.root(validation['id'])),
                '--output-root', str(root / 'output')], cwd=root, binary=validation['python_binary_sha256'])
        self.marker(stdout, b'GT05_REJECTIONS_COMPLETE ', {
            'result_sha256': sha(raw), 'cases': 27, 'all_expected_rejections_observed': True,
            'formal_acceptance': False})
        need(report['bindings'] == {'consumer_run_id': baseline['id'], 'validator_run_id': validation['id'],
            'consumer_summary_sha256': baseline['summary_sha256'], 'native_source_map_sha256': baseline['source_map_sha256'],
            'observation_sha256': baseline['observation_sha256'], 'input_sha256': baseline['observed']['input_sha256'],
            'host_captures': baseline['summary']['host_captures'], 'validation_summary_sha256': validation['summary_sha256']},
            'REJECTIONS_NATIVE_BINDING')
        need(baseline['comparable'] and report['baseline_comparison'] == baseline['checks'], 'REJECTIONS_BASELINE')
        rows = report['cases']
        need(len(rows) == 27 and {row['case'] for row in rows} == REJECTION_CASES, 'REJECTIONS_CASE_SET')
        # Recompute each fixed mutation's bytes. Captured per-case code/site is
        # evidence only when bound to the exact installed negative worker.
        from studio.tests.pipeline.check_native_observation_rejections import cases, mutate
        from studio.pipeline.godot.consumer import encoded
        vectors = {name: (path, replacement, code) for name, path, replacement, code in cases()}
        need(set(vectors) == REJECTION_CASES, 'REJECTIONS_CASE_SET')
        for row in rows:
            self.guard()
            path, replacement, code = vectors[row['case']]
            changed = copy.deepcopy(baseline['observed']); mutate(changed, path, replacement)
            need(row['field'] == list(path) and row['expected_error'] == row['actual_error'] == code
                 and row['rejected'] is True and row['mutated_observation_sha256'] == sha(encoded(changed))
                 and row['check_sites'] and all(type(site['line']) is int and site['line'] > 0
                    and type(site['function']) is str for site in row['check_sites']), 'REJECTIONS_CASE_BINDING')
            lines = self.read(self.studio / 'pipeline/godot/consumer.py').decode().splitlines()
            need(all(site['line'] <= len(lines) and site['source'] == lines[site['line'] - 1].strip()
                     for site in row['check_sites']), 'REJECTIONS_CHECK_SITE')
        return sha(canonical({'report': sha(raw), 'capture': sha(capture_raw)}))


def _repeat(first, repeated, left, right):
    need(first['report']['variant'] == repeated['report']['variant'] == 'baseline'
         and first['report']['pins'] == repeated['report']['pins']
         and first['report']['observed'] == repeated['report']['observed'], 'REPEAT_PRODUCER')
    from studio.pipeline.preflight import compare_repeat, PreflightRejected
    try:
        result = compare_repeat(left['semantic'], right['semantic'])
    except PreflightRejected:
        raise RunRejected('REPEAT_SEMANTICS') from None
    return {'comparison': result, 'producer': repeated['summary_sha256'], 'validation': right['summary_sha256']}


def _edit(first, edited, left, right):
    need(first['report']['variant'] == 'baseline' and edited['report']['variant'] == 'edited'
         and first['report']['pins'] == edited['report']['pins']
         and first['payloads']['fixture.glb'] != edited['payloads']['fixture.glb']
         and left['semantic'] != right['semantic'], 'EDIT_SENSITIVITY')
    before, after = copy.deepcopy(first['report']['observed']), copy.deepcopy(edited['report']['observed'])
    for name in ('prp_fixture_crate_lod0', 'prp_fixture_crate_collider'):
        a, b = before['meshes'].pop(name), after['meshes'].pop(name)
        need(a['geometry_sha256'] != b['geometry_sha256'], 'EDIT_GEOMETRY')
        need(abs(a['gltf_world_bounds']['max'][0] - a['gltf_world_bounds']['min'][0] - .6) < .001
             and abs(b['gltf_world_bounds']['max'][0] - b['gltf_world_bounds']['min'][0] - .8) < .001, 'EDIT_CRATE_WIDTH')
        for field in ('geometry_sha256', 'source_local_bounds', 'source_world_bounds', 'gltf_world_bounds'):
            a.pop(field); b.pop(field)
        need(a == b, 'EDIT_UNEXPECTED_MESH_CHANGE')
    need(before == after, 'EDIT_UNEXPECTED_CHANGE')
    return {'producer': edited['summary_sha256'], 'validation': right['summary_sha256'], 'crate_width_m': [.6, .8]}


def verify_chain(studio, producer_id, validation_id, consumer_id, *, repeat_producer_id=None,
                 repeat_validation_id=None, edited_producer_id=None, edited_validation_id=None,
                 reimport_id=None, visual_id=None, rejections_id=None, require_current_source=True,
                 phase_guard: Callable[[], None] | None = None) -> VerifiedRun:
    """Verify available lanes; incomplete/stale chains are explicitly diagnostic.

    Passing ``require_current_source=False`` can never yield ``publishable``.
    Optional IDs form whole pairs; full staged publication also requires native
    reimport, actual original-PBR captures and bound 27-case rejection evidence.
    The trusted publication provider must call this itself, not accept a proof
    dict supplied by a client. All result hashes use JSON sort/compact or exact
    file bytes as labelled; this function makes no filesystem mutations.
    ``phase_guard`` is an optional owner callback for an absolute deadline/Stop.
    Its original exception propagates, including errors derived from ValueError.
    Checks bracket each read and expensive bounded comparison/decode; a running
    comparison is allowed to finish before the next guard observes cancellation.
    """
    verifier = _Verifier(studio, require_current_source, phase_guard)
    try:
        need((repeat_producer_id is None) == (repeat_validation_id is None)
             and (edited_producer_id is None) == (edited_validation_id is None), 'CHAIN_PAIR')
        need(reimport_id is None or edited_producer_id is not None, 'CHAIN_REIMPORT_EDIT')
        first = verifier.producer(producer_id)
        validation = verifier.validation(validation_id, first)
        baseline = verifier.consumer(consumer_id, first, validation)
        evidence = {'producer': first['summary_sha256'], 'admission': validation['admission_sha256'],
            'khronos': validation['khronos_sha256'], 'godot': baseline['summary_sha256']}
        if repeat_producer_id is not None:
            repeated = verifier.producer(repeat_producer_id)
            repeat_validation = verifier.validation(repeat_validation_id, repeated)
            # Never silently apply a changed comparator to historical semantics.
            for stage in (validation_id, repeat_validation_id):
                verifier.guard()
                files = verifier.sources[stage + '/admission-source-files.json']
                installed = Path(__file__).resolve().parents[1]
                need(all(sha(verifier.read(verifier.studio / name)) == files[name]
                    and verifier.installed_hash(installed / name) == files[name] for name in DECODE), 'REPEAT_COMPARATOR_STALE')
            verifier.guard()
            evidence['repeat'] = sha(canonical(_repeat(first, repeated, validation, repeat_validation)))
            verifier.guard()
        edited = edited_validation = None
        if edited_producer_id is not None:
            edited = verifier.producer(edited_producer_id)
            edited_validation = verifier.validation(edited_validation_id, edited)
            verifier.guard()
            evidence['edit'] = sha(canonical(_edit(first, edited, validation, edited_validation)))
            verifier.guard()
        previous = baseline
        if reimport_id is not None:
            previous = verifier.consumer(reimport_id, edited, edited_validation,
                phase='reimport', consumer_id=consumer_id, previous=baseline)
            evidence['reimport'] = previous['summary_sha256']
        if visual_id is not None:
            # Visual may precede or follow reimport. Frozen inputs select which
            # chain it continues; do not consult the project's mutable input.
            _, visual_summary = verifier.obj(verifier.root(visual_id) / 'followup.json')
            after_edit = (edited_validation is not None and visual_summary['previous_input_sha256']['fixture.glb'] ==
                sha(edited_validation['payloads']['fixture.glb']))
            need(not after_edit or reimport_id is not None, 'VISUAL_REIMPORT_REQUIRED')
            visual = verifier.consumer(visual_id, edited if after_edit else first,
                edited_validation if after_edit else validation, phase='visual', consumer_id=consumer_id,
                previous=previous if after_edit else baseline)
            evidence['visual'] = visual['summary_sha256']
        if rejections_id is not None:
            evidence['rejections'] = verifier.rejections(rejections_id, baseline, validation)
        complete = set(evidence) == {'producer', 'admission', 'khronos', 'godot', 'repeat', 'edit', 'reimport', 'visual', 'rejections'}
        source_union = {}
        for files in verifier.sources.values():
            for name, digest in files.items():
                verifier.guard()
                if not name.startswith('.local/'):
                    if name in source_union and source_union[name] != digest:
                        # Only stale diagnostics may carry multiple historical
                        # versions; their per-stage maps remain the authority.
                        need(not require_current_source, 'SOURCE_VERSION_CONFLICT')
                    source_union[name] = digest
        source_digest = sha(canonical(source_union))
        proof = {'schema': 'HH-GT05-VERIFIED-RUN-1', 'source_sha256': source_digest,
            'source_hash_domain': 'sha256:source-map/json-sort-compact',
            'evidence': evidence, 'evidence_files': dict(sorted(verifier.reads.items())),
            'source_files': source_union, 'stage_source_files': verifier.sources, 'snapshot_qualifiers': verifier.qualifiers,
            'stale_source_files': sorted(verifier.stale), 'current_source_required': require_current_source,
            'current_source_verified': require_current_source and not verifier.stale,
            'complete': complete, 'publishable': complete and require_current_source and not verifier.stale,
            'formal_acceptance': False, 'public_ack': False, 'baseline_comparison': baseline['checks'],
            'semantic': {'sha256': validation['semantic_raw_sha256'], 'hash_domain': 'sha256:exact-file-bytes'},
            'import_preset_sha256': baseline['seed']['preset_sha256'],
            'import_preset_readback': baseline['preset_readback'],
            'binaries': {'blender': first['report']['pins']['blender_binary_sha256'],
                'godot': baseline['godot_binary_sha256'],
                'python': validation['python_binary_sha256'], 'node': validation['node_binary_sha256']}}
        payloads = {'fixture.glb': first['payloads']['fixture.glb'], 'fixture.blend': first['payloads']['fixture.blend'],
            'producer-report.json': first['raw'], 'asset-manifest.json': validation['payloads']['manifest.json']}
        # Recheck all bytes already used, including installed comparator code,
        # immediately before returning the copied payload to a trusted provider.
        for name in tuple(verifier.reads):
            verifier.read(verifier.studio / name)
        result = VerifiedRun(copy.deepcopy(proof), payloads)
        verifier.guard()
        return result
    except RunRejected:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError, RecursionError) as error:
        if error is verifier.guard_failure:
            raise
        raise RunRejected('EVIDENCE_SCHEMA') from None
