"""Read-only, bounded analysis of the fixed S77 object diagnostic03.

Reproduce after the owner confirms completion:
    python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s77-object-recovery/analyze_objects.py

JSON goes to stdout; this script creates no files, launches no process and imports
no project code. Exit 0 means complete diagnostic evidence was checked, never
GT-06 acceptance or leak/root-cause clearance. Exit 1 fails closed. No arguments,
alternate run directories, partial-run fallback, threshold changes or sampling.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import statistics
import sys
import time


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
RUN_ID = 'gt06-s77-object-diagnostic-03'
RAW = STUDIO / '.local/reviews' / RUN_ID
OWNER = BASE / 'object-owner-03'
OUT = RAW / 'project/benchmark/out'
COUNTERS = ('objects', 'cached_resources', 'tree_nodes', 'orphan_nodes')
HEX = re.compile(r'[0-9a-f]{64}\Z')
BAD_LOG = re.compile(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED')
LIMITATIONS = [
    'Diagnostic only: no GT-06 acceptance, critic verdict, full campaign PASS, leak clearance or root-cause proof.',
    'The initial reachable inventory omits all IDs. An unchanged initial descriptor remains unknown; class counts do not recover identities.',
    'Inventory covers reachable Nodes, TreeItems, incoming-signal sources, orphan Nodes and processed Tweens, not all ObjectDB objects. Unreachable objects remain unattributed.',
    'Added/removed means entering/leaving the reachable census. Removed still_valid=true explicitly does not mean destruction; no sampled absence proves lifetime between points.',
    'RichTextLabel totals cover only active IDs whose descriptors have appeared. Whole reachable-class totals are reported only when that count equals class_counts.RichTextLabel; this still is not all ObjectDB.',
    'Counters are sequential reads. Equal before/after counts do not prove atomicity, identity stability or scanner inactivity between reads. Scan flags are observations, not causal attribution.',
    'Census collection runs on the editor thread and perturbs timing. Serialization/write time is delayed into the next point; the final point write duration is unrecorded.',
    'The 60-second idle contract is tied to the hashed probe control flow and final idle_end point; an exact idle-deadline timestamp is not emitted.',
    'Import has closed/zero Job-handle evidence but no separate wrapper-process-handle receipt. Outer bootstrap records tree_verified and kill-on-close ownership, not independently checked CloseHandle receipts.',
    'Artifact hash consistency is checked offline; it is not a cryptographic signature or a fresh operating-system process/liveness observation.',
]


class InvalidEvidence(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise InvalidEvidence(reason)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(InvalidEvidence('Nonfinite JSON: ' + value)))


class Reader:
    def __init__(self):
        self.started = time.monotonic()
        self.total = 0
        self.manifest = {}

    def read(self, path, cap=8 * 1024 * 1024):
        require(time.monotonic() - self.started < 60, 'Analysis wall limit (60 seconds)')
        require(path.is_absolute(), 'Read path must be absolute')
        require(path.is_relative_to(ROOT), 'Read path outside fixed HH3D root')
        for component in (path, *path.parents):
            info = component.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                    'Symlink/reparse evidence: ' + str(component))
        info = path.stat()
        require(stat.S_ISREG(info.st_mode) and info.st_size <= cap, 'Not a bounded regular file: ' + str(path))
        self.total += info.st_size
        require(self.total <= 512 * 1024 * 1024, 'Analysis cumulative input limit (512 MiB)')
        with path.open('rb') as handle:
            raw = handle.read(cap + 1)
        require(len(raw) == info.st_size and len(raw) <= cap, 'File size changed during read: ' + str(path))
        digest = sha(raw)
        key = path.relative_to(ROOT).as_posix()
        require(key not in self.manifest or self.manifest[key] == digest, 'Read drift: ' + key)
        self.manifest[key] = digest
        return raw

    def json(self, path, cap=8 * 1024 * 1024):
        value = decode(self.read(path, cap))
        require(type(value) is dict, 'Expected JSON object: ' + str(path))
        return value


def clean_log(raw, name):
    require(not BAD_LOG.search(raw), 'Warning/error/failure in ' + name)


def path_map(value, name):
    require(type(value) is dict and 0 < len(value) <= 256, name + ' file count')
    for relative, digest in value.items():
        require(type(relative) is str and '\\' not in relative and ':' not in relative
                and not PurePosixPath(relative).is_absolute()
                and all(part not in ('', '.', '..') for part in relative.split('/')),
                name + ' unsafe relative path')
        require(type(digest) is str and HEX.fullmatch(digest), name + ' invalid digest')


def job_check(job, name):
    require(type(job) is dict, name + ' missing Job')
    for key in ('configured', 'assigned', 'closed', 'zero_observed'):
        require(job.get(key) is True, name + ' Job ' + key)
    for key in ('handle_retained', 'tainted', 'create_uncertain', 'close_uncertain'):
        require(job.get(key) is False, name + ' Job ' + key)
    require(type(job.get('active_count')) is int and job['active_count'] == 0
            and job.get('failed_operations') == [] and job.get('native_error') is None,
            name + ' Job zero/error proof')


def native_capture(reader, lane, sources, binary, native=False):
    folder = RAW / lane
    capture = reader.json(folder / 'capture.json')
    invocation_raw = reader.read(folder / 'invocation.json')
    invocation = decode(invocation_raw)
    artifacts = {'stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json'}
    require(type(capture.get('artifacts')) is dict and set(capture['artifacts']) == artifacts,
            lane + ' artifact set')
    records = {}
    for name in artifacts:
        raw = reader.read(folder / name, 32 * 1024 * 1024 if name.endswith('.txt') else 8192)
        require(sha(raw) == capture['artifacts'][name], lane + ' artifact hash ' + name)
        records[name] = decode(raw) if name.endswith('.json') else raw
    started, exited = records['process-start.json'], records['process-exit.json']
    require(type(started) is dict and set(started) == {'pid'} and integer(started['pid'], 1), lane + ' start PID')
    require(type(exited) is dict and set(exited) == {'pid', 'exit_code'}
            and integer(exited['pid'], 1) and exited['pid'] == started['pid']
            and type(exited['exit_code']) is int and exited['exit_code'] == 0,
            lane + ' independently read actual process exit')
    require(capture.get('actual_process_exit') == exited and capture.get('completed') is True
            and type(capture.get('wrapper_exit_code')) is int and capture['wrapper_exit_code'] == 0
            and capture.get('natural_tree_exit') is True
            and type(capture.get('active_before_cleanup')) is int and capture['active_before_cleanup'] == 0
            and integer(capture.get('active_at_wrapper_exit'))
            and capture.get('formal_acceptance') is False, lane + ' terminal binding')
    job_check(capture.get('job'), lane)
    require(invocation.get('source_files') == sources and invocation.get('binary_sha256') == binary
            and invocation.get('formal_acceptance') is False
            and invocation.get('cwd') == str(RAW / 'project'), lane + ' invocation source binding')
    argv = invocation.get('argv')
    require(type(argv) is list and argv and all(type(arg) is str for arg in argv), lane + ' argv')
    expected_tail = (['--editor', '--path', str(RAW / 'project'), 'res://scenes/fixture.tscn',
                      '--', '--hh-benchmark-mode=diagnostic'] if native else
                     ['--headless', '--editor', '--path', str(RAW / 'project'), '--import'])
    require(argv[1:] == expected_tail, lane + ' exact fixed invocation')
    require(not records['stderr.txt'].strip(), lane + ' nonempty stderr')
    clean_log(records['stdout.txt'], lane)
    if native:
        require(capture.get('schema') == 'HH-GT06-BENCHMARK-CAPTURE-2'
                and capture.get('actual_process_start') == started
                and capture.get('source_unchanged') is True
                and capture.get('invocation_sha256') == sha(invocation_raw), 'Native capture schema/invocation')
        for key in ('argv', 'cwd', 'source_root', 'source_files', 'binary_sha256', 'profile'):
            require(capture.get(key) == invocation.get(key), 'Native invocation mismatch: ' + key)
        expected_handle = {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False}
        require(capture.get('wrapper_process_handle') == expected_handle
                and all(type(value) is bool for value in capture['wrapper_process_handle'].values()),
                'Native wrapper process handle receipt')
        cleanup_paths = sorted(folder.glob('cleanup-*.json'))
        require(len(cleanup_paths) == 1, 'Native cleanup receipt count')
        cleanup = reader.json(cleanup_paths[0])
        require(cleanup.get('closed') is True and cleanup.get('job') == capture['job']
                and type(cleanup.get('wrapper_exit_code')) is int and cleanup['wrapper_exit_code'] == 0
                and cleanup.get('failure_code') is None
                and cleanup.get('wrapper_process_handle') == expected_handle, 'Native cleanup mismatch')
    return capture, invocation, records['stdout.txt']


def outer_capture(reader, diagnostic):
    capture = reader.json(OWNER / 'capture.json')
    invocation = reader.json(OWNER / 'invocation.json')
    actual = reader.json(OWNER / 'probe-host.json', 8192)
    host = capture.get('host')
    require(type(host) is dict and capture.get('helper_source_unchanged') is True, 'Outer capture incomplete')
    require(type(actual.get('exit_code')) is int and actual['exit_code'] == 0
            and integer(actual.get('target_pid'), 1), 'Outer independently read actual child exit')
    require(host.get('target_pid') == actual['target_pid'] and type(host.get('exit_code')) is int
            and host['exit_code'] == actual['exit_code'] and integer(host.get('wrapper_pid'), 1)
            and host['wrapper_pid'] != actual['target_pid']
            and type(host.get('wrapper_exit_code')) is int and host['wrapper_exit_code'] == 0
            and host.get('timed_out') is False and host.get('tree_verified') is True
            and host.get('ownership') == 'gated_job_kill_on_close', 'Outer wrapper/tree/timeout proof')
    require({key: host.get(key) for key in ('stdout', 'stderr', 'host')} == {
        'stdout': 'probe-stdout.txt', 'stderr': 'probe-stderr.txt', 'host': 'probe-host.json'}, 'Outer artifact names')
    require(invocation.get('timeout_seconds') == 600 and invocation.get('formal_acceptance') is False
            and invocation.get('full_benchmark') is False, 'Outer scope/bound')
    argv = invocation.get('argv')
    require(type(argv) is list and len(argv) == 4 and Path(argv[0]).name.lower() == 'python.exe'
            and argv[1:] == ['-B', str(BASE / 'diagnose_objects.py'), '--owned-child'], 'Outer exact argv')
    helpers = invocation.get('helper_files')
    require(type(helpers) is dict and set(helpers) == {'diagnose_objects.py', 'object_probe.gd'}, 'Helper manifest')
    for name, expected in helpers.items():
        require(sha(reader.read(OWNER / name)) == expected == sha(reader.read(BASE / name)), 'Helper bytes changed: ' + name)
    require(diagnostic.get('runner_sha256') == helpers['diagnose_objects.py']
            and diagnostic.get('probe_sha256') == helpers['object_probe.gd'], 'Diagnostic/helper hash binding')
    require(sha(reader.read(STUDIO / 'build/bootstrap/run_fixture.py')) == invocation.get('runner_sha256'),
            'Outer bootstrap helper hash')
    require(not reader.read(OWNER / 'probe-stderr.txt', 32 * 1024 * 1024).strip(), 'Outer stderr')
    clean_log(reader.read(OWNER / 'probe-stdout.txt', 32 * 1024 * 1024), 'outer')
    return {'actual_child_exit': actual, 'wrapper_pid': host['wrapper_pid'], 'wrapper_exit_code': 0,
            'tree_verified': True, 'timed_out': False, 'helper_files': helpers,
            'bootstrap_sha256': invocation['runner_sha256']}


def markers(raw, name):
    prefix = name.encode() + b' '
    return [decode(line[len(prefix):]) for line in raw.splitlines() if line.startswith(prefix)]


def analyze_points(points):
    known = {}
    unknown = Counter(points[0]['class_counts'])
    ever_seen = set()
    output = []
    event_totals = {kind: Counter() for kind in ('added', 'changed', 'removed')}
    previous = None
    for point in points:
        classes = point['class_counts']
        require(type(classes) is dict and all(type(key) is str and integer(value, 1) for key, value in classes.items())
                and sum(classes.values()) == point['inventory_count'], 'Point class-count sum')
        groups = {}
        seen_this_point = set()
        details = {}
        for kind in ('added', 'changed', 'removed'):
            rows = point[kind]
            require(type(rows) is list and len(rows) <= 100000, 'Descriptor array limit')
            groups[kind] = Counter()
            details[kind] = []
            for row in rows:
                require(type(row) is dict and type(row.get('id')) is str
                        and re.fullmatch(r'[1-9][0-9]{0,19}', row['id'])
                        and type(row.get('class')) is str and row['class']
                        and type(row.get('relation')) is str and type(row.get('queued_for_deletion')) is bool,
                        'Invalid class/ID descriptor')
                identity, classname = row['id'], row['class']
                require(identity not in seen_this_point, 'Duplicate transition ID at point')
                seen_this_point.add(identity)
                old = known.get(identity)
                if kind == 'added':
                    require(old is None, 'Added ID already reachable')
                    known[identity] = row
                    details[kind].append(row)
                elif kind == 'changed':
                    if old is None:
                        require(unknown[classname] > 0, 'Changed ID cannot come from omitted initial inventory')
                        unknown[classname] -= 1
                    else:
                        require(old['class'] == classname and old != row, 'Changed descriptor class/no change')
                    details[kind].append({'before_known': old is not None, 'before': old, 'after': row,
                                          'changed_fields': sorted(key for key in set(old or {}) | set(row)
                                                                   if old is not None and old.get(key) != row.get(key))})
                    known[identity] = row
                else:
                    require(type(row.get('still_valid')) is bool, 'Removed descriptor validity missing')
                    if old is None:
                        require(unknown[classname] > 0, 'Removed ID cannot come from omitted initial inventory')
                        unknown[classname] -= 1
                    else:
                        require({key: value for key, value in row.items() if key != 'still_valid'} == old,
                                'Removed descriptor differs from last reachable row')
                        del known[identity]
                    details[kind].append(row)
                ever_seen.add(identity)
                groups[kind][classname] += 1
                event_totals[kind][classname] += 1
        if previous is None:
            require(not any(point[kind] for kind in groups), 'Initial identities must be omitted')
        else:
            expected = Counter(previous['class_counts'])
            expected.update(groups['added'])
            expected.subtract(groups['removed'])
            require(all(value >= 0 for value in expected.values()) and +expected == Counter(classes),
                    'Class-count changes differ from added/removed descriptors')
        require(Counter(row['class'] for row in known.values()) + (+unknown) == Counter(classes),
                'Known/omitted population reconstruction differs from inventory')
        labels = [row for row in known.values() if row['class'] == 'RichTextLabel']
        require(all(integer(row.get('paragraph_count')) and integer(row.get('character_count')) for row in labels),
                'RichTextLabel metrics missing')
        before, after = point['counters_before'], point['counters_after']
        scan = {'point': point['filesystem_scanning'],
                'before_read_start': before['filesystem_scanning_before'],
                'before_read_end': before['filesystem_scanning_after'],
                'after_read_start': after['filesystem_scanning_before'],
                'after_read_end': after['filesystem_scanning_after']}
        entry = {key: point[key] for key in ('sequence', 'label', 'batch', 'cycle', 'phase', 'frame', 'mono_us',
                                            'focused', 'inventory_count', 'inventory_duration_us', 'previous_snapshot_write_us')}
        entry.update(counters_before=before, counters_after=after,
                     counters_equal_across_collection=point['counters_equal_across_collection'],
                     delta_during_collection={key: after[key] - before[key] for key in COUNTERS},
                     delta_since_previous_before=({key: before[key] - previous['counters_before'][key] for key in COUNTERS}
                                                  if previous else None),
                     scan_flags=scan, any_scan_flag=any(scan.values()),
                     unattributed_before=before['objects'] - point['inventory_count'],
                     unattributed_after=after['objects'] - point['inventory_count'],
                     omitted_initial_active_ids=sum(unknown.values()), known_active_ids=len(known),
                     class_counts=classes, transitions_by_class={kind: dict(value) for kind, value in groups.items()},
                     descriptors=details,
                     rich_text_labels={'reachable_class_count': classes.get('RichTextLabel', 0),
                                       'known_active_id_count': len(labels),
                                       'all_reachable_ids_seen': len(labels) == classes.get('RichTextLabel', 0),
                                       'known_active_paragraphs': sum(row['paragraph_count'] for row in labels),
                                       'known_active_characters': sum(row['character_count'] for row in labels),
                                       'scope': 'whole reachable class' if len(labels) == classes.get('RichTextLabel', 0)
                                                else 'partial known active IDs only',
                                       'descriptors': sorted(labels, key=lambda row: int(row['id']))})
        output.append(entry)
        previous = point
    return output, {'unique_descriptor_ids_ever_seen': len(ever_seen),
                    'transitions_by_class': {kind: dict(value) for kind, value in event_totals.items()},
                    'final_omitted_initial_active_ids': sum(unknown.values())}


def run(reader):
    # Both terminal documents are mandatory before any observations are analyzed.
    result = reader.json(RAW / 'result.json')
    require(result.get('completed_diagnostic') is True and result.get('formal_acceptance') is False
            and result.get('full_benchmark') is False and result.get('source_unchanged') is True,
            'Missing/unsuccessful terminal diagnostic result')
    for name in ('failure.json', 'cleanup-failure.json'):
        require(not (RAW / name).exists(), 'Terminal failure artifact: ' + name)
    diagnostic = reader.json(RAW / 'diagnostic.json')
    require(diagnostic.get('run_id') == RUN_ID and diagnostic.get('formal_acceptance') is False
            and diagnostic.get('full_benchmark') is False and diagnostic.get('inventory_complete_objectdb') is False
            and diagnostic.get('native_batches') == 6 and diagnostic.get('cycles_each') == 100
            and diagnostic.get('idle_seconds') == 60 and diagnostic.get('inner_wall_seconds') == 540,
            'Diagnostic identity/scope/bounds')
    outer = outer_capture(reader, diagnostic)
    sources = diagnostic['source_files']
    path_map(sources, 'Source')
    for relative, digest in sources.items():
        require(sha(reader.read(RAW / 'source/studio' / relative)) == digest, 'Retained source hash: ' + relative)
        require(sha(reader.read(STUDIO / relative)) == digest, 'Current source drift: ' + relative)
    binding = diagnostic['binding']
    closure = sha(''.join(name + '\0' + sources[name] + '\n' for name in sorted(sources)).encode())
    require(binding.get('source_closure_sha256') == closure and binding.get('run_id') == RUN_ID
            and binding.get('mode') == 'diagnostic' and binding.get('batch_barrier') == 'diagnostic_none'
            and binding.get('batch_start') == 'diagnostic_immediate', 'Source/binding closure')
    initial = diagnostic['initial_project_files']
    path_map(initial, 'Initial project')
    runtime = reader.json(RAW / 'runtime-source-files.json')
    path_map(runtime, 'Runtime')
    project_prefix = (RAW / 'project').relative_to(STUDIO).as_posix() + '/'
    require(all(runtime.get(name) == digest for name, digest in sources.items()), 'Runtime missing source dependency')
    for relative, digest in runtime.items():
        require(relative in sources or relative.startswith(project_prefix), 'Runtime path outside fixed source/project')
        require(sha(reader.read(STUDIO / relative)) == digest, 'Runtime source hash: ' + relative)
    for relative, digest in initial.items():
        if relative != 'scenes/fixture.tscn':
            require(runtime.get(project_prefix + relative) == digest, 'Initial/runtime project binding: ' + relative)
    # Re-derive the disposable-only instrumentation from retained source and
    # captured helper bytes; no report-provided path chooses the driver.
    driver = reader.read(RAW / 'source/studio/tests/replay/benchmark_native.gd').decode('utf-8')
    driver = driver.replace('\r\n', '\n').replace('\r', '\n')
    for old, new in (
        ('        _batch_limit = 1\n        _cycle_limit = 1',
         '        _batch_limit = 6\n        _cycle_limit = 100'),
        ('    if _mode != "full":\n        _advance_batch()',
         '    if _mode != "full":\n        _object_probe_after_batch()'),
        ('    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n',
         '    if _object_probe_tick():\n        return\n    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n'),
    ):
        require(driver.count(old) == 1, 'Instrumented driver replacement not unique')
        driver = driver.replace(old, new)
    probe = reader.read(OWNER / 'object_probe.gd').decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
    require((driver + '\n' + probe).encode('utf-8') == reader.read(RAW / 'project/addons/hh_benchmark/benchmark_native.gd'),
            'Disposable driver differs from exact retained-source/probe reconstruction')
    require(reader.json(RAW / 'project/benchmark/input.json') == binding, 'Native input/binding')
    lock = reader.json(RAW / 'source/studio/toolchain.lock.json')['godot']
    binary_path = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    require(sha(reader.read(binary_path, 256 * 1024 * 1024)) == lock['gui_sha256'], 'Pinned executable bytes')
    imported, import_invocation, _ = native_capture(reader, 'import-host', sources, lock['gui_sha256'])
    native, native_invocation, stdout = native_capture(reader, 'editor-host', runtime, lock['gui_sha256'], True)
    require(import_invocation['argv'][0] == native_invocation['argv'][0] == str(binary_path), 'Exact native executable path')
    require(result.get('actual_process_exit') == native['actual_process_exit'] and result.get('job') == native['job'],
            'Terminal result/native capture binding')
    pid = native['actual_process_exit']['pid']
    index_raw = reader.read(OUT / 'index.json')
    index = decode(index_raw)
    require(index.get('completed') is True and index.get('formal_acceptance') is False
            and index.get('benchmark_complete') is False and index.get('host_integrated') is False
            and index.get('input') == binding and index.get('pid') == pid
            and index.get('batches_completed') == 6 and index.get('cycles_per_batch') == 100,
            'Native terminal index')
    require(markers(stdout, 'HH_GT06_BENCHMARK_COMPLETE') == [{
        'run_id': RUN_ID, 'pid': pid, 'mode': 'diagnostic', 'batches': 6,
        'index_sha256': sha(index_raw), 'benchmark_complete': False, 'host_integrated': False}],
        'Terminal stdout/index hash binding')
    batch_paths = sorted(OUT.glob('batch-*.json'))
    require([path.name for path in batch_paths] == ['batch-%02d.json' % i for i in range(6)], 'Exactly six batches required')
    require(type(index.get('batches')) is list and len(index['batches']) == 6, 'Index batch list')
    batch_markers = markers(stdout, 'HH_GT06_BENCHMARK_BATCH')
    require(len(batch_markers) == 6, 'Batch stdout count')
    batches = []
    for number, path in enumerate(batch_paths):
        raw = reader.read(path)
        batch = decode(raw)
        require(index['batches'][number] == {'index': number, 'file': path.name, 'sha256': sha(raw), 'size_bytes': len(raw)},
                'Batch/index hash binding')
        require(batch.get('index') == number and batch.get('run_id') == RUN_ID and batch.get('pid') == pid
                and batch.get('mode') == 'diagnostic', 'Batch identity')
        require(type(batch.get('cycles')) is list and len(batch['cycles']) == 100
                and [row.get('index') for row in batch['cycles']] == list(range(100)), 'One hundred indexed cycles per batch')
        require(all(row.get('main_thread') is True and row.get('effects') == {'create': 1, 'undo': 1, 'save': 1, 'reload': 1}
                    for row in batch['cycles']), 'Batch semantic effects')
        require(batch_markers[number] == {'run_id': RUN_ID, 'pid': pid, 'index': number, 'sha256': sha(raw),
                                         'memory_mono_us': batch['ended_mono_us'], 'barrier': batch['barrier']},
                'Batch/stdout hash binding')
        batches.append({key: batch[key] for key in ('index', 'started_mono_us', 'ended_mono_us', 'memory', 'max_status_gap_ms')})
    hashes = result.get('points')
    require(type(hashes) is dict and 8 <= len(hashes) <= 512
            and type(result.get('point_count')) is int and result['point_count'] == len(hashes), 'Point count/bound')
    point_paths = sorted(OUT.glob('object-*.json'))
    require([path.name for path in point_paths] == ['object-%04d.json' % i for i in range(len(hashes))]
            and set(hashes) == {path.name for path in point_paths}, 'Point sequence/hash manifest set')
    require(not list(OUT.glob('*.pending')), 'Incomplete pending point/publication')
    points = []
    total_point_bytes = 0
    for sequence, path in enumerate(point_paths):
        raw = reader.read(path)
        total_point_bytes += len(raw)
        require(total_point_bytes <= 128 * 1024 * 1024 and sha(raw) == hashes[path.name], 'Point byte/hash bound')
        point = decode(raw)
        require(point.get('schema_id') == 'hh-studio.object-attribution-diagnostic'
                and point.get('schema_version') == '1.0.0' and point.get('sequence') == sequence
                and point.get('run_id') == RUN_ID and point.get('pid') == pid
                and point.get('formal_acceptance') is False and point.get('full_benchmark') is False
                and point.get('inventory_complete_objectdb') is False
                and point.get('initial_inventory_ids_omitted') is (sequence == 0), 'Point identity/scope')
        require(point.get('label') in ('settle', 'after_batch', 'idle', 'idle_end')
                and point.get('phase') == ('BATCH_SETTLE' if point['label'] == 'settle' else 'BATCH_WRITE')
                and integer(point.get('batch')) and point['batch'] < 6 and point.get('cycle') == 100,
                'Point phase/batch boundary')
        for key in ('mono_us', 'frame', 'inventory_duration_us', 'previous_snapshot_write_us', 'inventory_count'):
            require(integer(point.get(key)), 'Point integer: ' + key)
        require(point['inventory_duration_us'] > 0
                and (point['previous_snapshot_write_us'] == 0 if sequence == 0 else point['previous_snapshot_write_us'] > 0),
                'Point collection/write duration')
        require(type(point.get('filesystem_scanning')) is bool and type(point.get('focused')) is bool, 'Point scan/focus bool')
        before, after = point.get('counters_before'), point.get('counters_after')
        for counters in (before, after):
            require(type(counters) is dict and all(integer(counters.get(key)) for key in COUNTERS)
                    and all(type(counters.get(key)) is bool for key in ('filesystem_scanning_before', 'filesystem_scanning_after')),
                    'Counter field types')
        require(point.get('counters_equal_across_collection') is (before == after)
                and point.get('unattributed_object_count') == before['objects'] - point['inventory_count'],
                'Counter equality/unattributed arithmetic')
        if points:
            previous = points[-1]
            require(point['mono_us'] >= previous['mono_us'] + previous['inventory_duration_us']
                    and point['frame'] >= previous['frame'] and point['batch'] >= previous['batch'], 'Point ordering')
        points.append(point)
    after_batches = [point for point in points if point['label'] == 'after_batch']
    require([point['batch'] for point in after_batches] == list(range(6)), 'Six final batch census points')
    require(points[-1]['label'] == 'idle_end' and points[-1]['batch'] == 5
            and sum(point['label'] == 'idle_end' for point in points) == 1
            and any(point['label'] == 'idle' for point in points), 'Final idle_end point')
    final_batch = after_batches[-1]
    require(all(point['batch'] == 5 and point['label'] in ('idle', 'idle_end')
                for point in points[final_batch['sequence'] + 1:]), 'No workload during final idle')
    idle_observed_us = points[-1]['mono_us'] - final_batch['mono_us'] - final_batch['inventory_duration_us']
    require(idle_observed_us >= 60_000_000, 'Insufficient observed final idle interval')
    for batch, point in zip(batches, after_batches):
        require(point['mono_us'] >= batch['ended_mono_us'], 'After-batch census precedes publication')
    require(index['ended_mono_us'] >= points[-1]['mono_us'] + points[-1]['inventory_duration_us'], 'Index precedes final census')
    timeline, transitions = analyze_points(points)
    durations = [point['inventory_duration_us'] for point in points]
    writes = [point['previous_snapshot_write_us'] for point in points[1:]]
    unequal = [point['sequence'] for point in points if not point['counters_equal_across_collection']]
    scans = [entry['sequence'] for entry in timeline if entry['any_scan_flag']]
    counter_summary = {key: {'first_before': points[0]['counters_before'][key], 'final_before': points[-1]['counters_before'][key],
                             'min': min(point[phase][key] for point in points for phase in ('counters_before', 'counters_after')),
                             'max': max(point[phase][key] for point in points for phase in ('counters_before', 'counters_after'))}
                       for key in COUNTERS}
    # Attempt02 is explicitly excluded; absent actual exits can never become exit0.
    interrupted = reader.json(BASE / 'object-interruption-02.json')
    require(interrupted.get('diagnostic_complete') is False and interrupted.get('native_actual_exit_known') is False
            and interrupted.get('job_close_receipt_available') is False, 'Attempt02 interruption receipt changed')
    # Re-read terminal publications after processing so a concurrent overwrite
    # cannot silently rebind the analyzed points to a different completion.
    require(reader.json(RAW / 'result.json') == result, 'Terminal result read drift')
    reader.json(OWNER / 'capture.json')
    return {'schema': 'HH-S77-OBJECT-DIAGNOSTIC-ANALYSIS-1', 'run_id': RUN_ID,
            'status': 'COMPLETE_DIAGNOSTIC_EVIDENCE_VERIFIED', 'formal_acceptance': False, 'full_benchmark': False,
            'full_objectdb_attribution': False, 'root_cause_proven': False,
            'generated_utc': datetime.now(timezone.utc).isoformat(), 'source_closure_sha256': closure,
            'process_evidence': {'outer': outer, 'import_actual_exit': imported['actual_process_exit'],
                                 'native_actual_exit': native['actual_process_exit'], 'import_job': imported['job'],
                                 'native_job': native['job'], 'native_wrapper_process_handle': native['wrapper_process_handle']},
            'attempt02': {'status': 'INTERRUPTED', 'eligible_for_complete_analysis': False,
                          'native_actual_exit': None, 'job_close_receipt_available': False},
            'batches': batches, 'point_count': len(points), 'points_sha256': hashes,
            'idle': {'required_seconds': 60, 'after_batch_point': final_batch['sequence'],
                     'final_point': points[-1]['sequence'], 'observed_us_from_last_batch_census_end': idle_observed_us,
                     'exact_idle_deadline_timestamp_recorded': False},
            'counter_summary': counter_summary, 'counter_unequal_points': unequal, 'any_scanning_points': scans,
            'overhead': {'collection_total_us': sum(durations), 'collection_min_us': min(durations),
                         'collection_median_us': statistics.median(durations), 'collection_max_us': max(durations),
                         'recorded_write_total_us_excludes_final': sum(writes),
                         'recorded_write_max_us_excludes_final': max(writes),
                         'final_write_duration_known': False, 'timing_eligible_for_acceptance': False},
            'descriptor_summary': transitions, 'timeline': timeline, 'limitations': LIMITATIONS}


def main():
    reader = Reader()
    try:
        require(not sys.argv[1:], 'No arguments: only fixed completed diagnostic03 is allowed')
        report = run(reader)
        report['analyzer_sha256'] = sha(reader.read(Path(__file__).absolute()))
        report['checked_file_sha256'] = reader.manifest
        report['input_bytes_read'] = reader.total
        rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        require(len(rendered.encode('utf-8')) <= 32 * 1024 * 1024, 'Analysis output limit (32 MiB)')
        print(rendered)
        return 0
    except (InvalidEvidence, OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as error:
        print(json.dumps({'status': 'INCOMPLETE_OR_INVALID_DIAGNOSTIC', 'run_id': RUN_ID,
                          'formal_acceptance': False, 'full_benchmark': False,
                          'full_objectdb_attribution': False, 'error_type': type(error).__name__,
                          'reason': str(error), 'attempt02_status': 'INTERRUPTED_NOT_ELIGIBLE',
                          'checked_file_count_before_failure': len(reader.manifest)}, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
