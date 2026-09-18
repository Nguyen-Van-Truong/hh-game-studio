"""Seal only the fixed S97 24-case reader matrix; never launch or import a runner.

An explicit reviewed selection keeps the one collector-only correction separate.
Pack mode reads stopped evidence. Verify mode reads only the sealed packet.
Neither mode certifies a benchmark, S96 causation, or absence of leaks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
PREFIX = 'zdoc/reviews/20260918-gt06-s97-ack-recovery/'
CASES = ('normal', 'read_overlap', 'locked_release', 'locked_timeout', 'malformed',
         'locked_malformed', 'wrong_hash', 'wrong_schema', 'empty', 'oversized',
         'short_read', 'locked_short_read')
WORK = [(stage, case) for stage in ('start', 'ack') for case in CASES]
CANDIDATE = '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95'
GDS = '4265d17f1767f6f95602a09d7444fdba5dca50dd7237439b833515092e43db91'
OLD_DRIVER = '6233514e57b02429bad477200454c3033f324622d5cd289dda4cae1ed88eaee1'
FIRST_DRIVER = '4dd5cdaf79a41e8dfec195d77c61be8a4b51911774c7bb3030da0fbcf7bbe880'
FINAL_DRIVER = '88e4df1040b31a3239057759e8d85d89cdb71a9d2b38b17d8e7c4ce9988611fe'
DERIVED_SHA = '1ef2b2e863efc8d312e91c5c07496cdd2b41080e4b2c0f3939ad1c3d494130cd'
DRIVER_PATH = PREFIX + 'reader-regression/run_reader_regression.py'
GDS_PATH = PREFIX + 'reader-regression/reader_regression.gd'
NATIVE_PATH = 'studio/tests/replay/benchmark_native.gd'
BOOTSTRAP_PATH = 'studio/build/bootstrap/run_fixture.py'
BOOTSTRAP_SHA = 'ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328'
FLAGS = {'formal_acceptance': False, 'native_benchmark': False,
         's96_cause_proven': False, 'no_leak_proven': False}
HANDLE = {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False}
FILE_CAP = 16 * 1024 * 1024
TOTAL_CAP = 512 * 1024 * 1024
ENTRY_CAP = 12000


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def relative(value):
    need(type(value) is str and value and '\\' not in value and ':' not in value, 'RELATIVE_PATH')
    path = PurePosixPath(value)
    need(not path.is_absolute() and str(path) == value and all(p not in ('.', '..') for p in path.parts),
         'RELATIVE_PATH')
    return value


def hash_map(value):
    need(type(value) is dict and 1 <= len(value) <= 256, 'HASH_MAP')
    for name, digest in value.items():
        relative(name)
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'HASH_MAP_DIGEST')
    return value


def exact_int(value, minimum=0):
    return type(value) is int and value >= minimum


def checked(path, cap=FILE_CAP):
    for item in (path, *path.parents):
        info = item.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'REPARSE_PATH')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_size <= cap, 'FILE_SIZE_OR_TYPE')
    raw = path.read_bytes()
    after = path.stat()
    need(len(raw) == info.st_size and (info.st_size, info.st_mtime_ns) ==
         (after.st_size, after.st_mtime_ns), 'FILE_CHANGED_DURING_READ')
    return raw


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


class Evidence:
    """Bounded bytes, with one locator for every raw file and no source imports."""
    def __init__(self, packet=None, inventory=None):
        self.packet, self.inventory = packet, inventory or {}
        self.cache = {}
        self.total = 0

    def raw(self, key, *, pool=False):
        relative(key)
        if key in self.cache:
            return self.cache[key]
        if self.packet:
            need(key in self.inventory, 'PACKET_MISSING:' + key)
            row = self.inventory[key]
            raw = checked(self.packet / relative(row['packet_path']))
            need(len(raw) == row['size_bytes'] and sha(raw) == row['sha256'], 'PACKET_HASH:' + key)
        else:
            workspace = key.startswith('@workspace/')
            local = key[len('@workspace/'):] if workspace else key
            raw = checked((ROOT if workspace else BASE) / local)
            digest = sha(raw)
            self.inventory[key] = {'raw_locator': {'base': 'workspace' if workspace else 's97', 'path': local},
                                   'size_bytes': len(raw), 'sha256': digest,
                                   'packet_path': 'source-pool/' + digest if pool else 'raw/' + key}
        self.total += len(raw)
        need(self.total <= TOTAL_CAP and len(self.cache) < ENTRY_CAP, 'PACKET_BUDGET')
        self.cache[key] = raw
        return raw

    def obj(self, key):
        return decode(self.raw(key))

    def has(self, key):
        return key in self.inventory if self.packet else (BASE / relative(key)).is_file()

    def files(self, prefix, *, recursive=False, pool=False, project=False):
        relative(prefix)
        if self.packet:
            keys = [key for key in self.inventory if key.startswith(prefix + '/') and
                    (recursive or '/' not in key[len(prefix) + 1:])]
        else:
            directory = BASE / prefix
            need(directory.is_dir() and not directory.is_symlink(), 'DIRECTORY:' + prefix)
            keys = []
            for current, dirs, files in os.walk(directory):
                dirs[:] = [name for name in dirs if name not in ('.godot', '__pycache__', '.git')]
                for name in dirs:
                    info = (Path(current) / name).lstat()
                    need(not getattr(info, 'st_file_attributes', 0) & 0x400 and
                         not stat.S_ISLNK(info.st_mode), 'REPARSE_DIRECTORY')
                for name in files:
                    if name.endswith(('.pyc', '.pyo')):
                        continue
                    keys.append((Path(current) / name).relative_to(BASE).as_posix())
                if not recursive:
                    break
                need(len(keys) <= ENTRY_CAP, 'TREE_BUDGET')
        for key in sorted(keys):
            # Inputs/outputs keep an exact per-case copy; repeated source and
            # project source bytes use the content-addressed pool.
            use_pool = pool or (project and '/benchmark/' not in key)
            self.raw(key, pool=use_pool)
        return keys


def clean_job(job):
    need(type(job) is dict and job.get('active_count') == 0 and type(job.get('active_count')) is int,
         'JOB_ACTIVE')
    for name in ('assigned', 'configured', 'closed', 'zero_observed'):
        need(job.get(name) is True, 'JOB_' + name)
    for name in ('tainted', 'handle_retained', 'create_uncertain', 'close_uncertain'):
        need(job.get(name) is False, 'JOB_' + name)
    need(job.get('failed_operations') == [] and job.get('native_error') is None, 'JOB_ERRORS')


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def outer(ev, path, expected_exit, stage=None, case=None, run_id=None):
    path = relative(path)
    folder = path.rsplit('/', 1)[0]
    ev.files(folder)
    capture = ev.obj(path)
    need(capture.get('exit_code') == expected_exit and type(capture['exit_code']) is int and
         capture.get('wrapper_exit_code') == 0 and type(capture['wrapper_exit_code']) is int,
         'OUTER_ACTUAL_EXIT')
    need(capture.get('timed_out') is False and capture.get('tree_verified') is True and
         capture.get('ownership') == 'gated_job_kill_on_close', 'OUTER_OWNERSHIP')
    need(exact_int(capture.get('target_pid'), 1) and exact_int(capture.get('wrapper_pid'), 1), 'OUTER_PIDS')
    host = ev.obj(folder + '/' + relative(capture['host']))
    need(set(host) == {'target_pid', 'started_at', 'exit_code'} and
         host['target_pid'] == capture['target_pid'] and host['exit_code'] == expected_exit,
         'OUTER_HOST_EXIT')
    need(not ev.raw(folder + '/' + relative(capture['stderr'])).strip(), 'OUTER_STDERR')
    stdout = ev.raw(folder + '/' + relative(capture['stdout']))
    if stage is not None:
        expected_argv = ['python.exe', '-B', '$SNAPSHOT/' + DRIVER_PATH, '--run-id', run_id,
                         '--stage', stage, '--case', case]
        need(capture['argv'] == expected_argv, 'OUTER_ARGV')
        # RuntimeError does not escape the collector; its final stdout still
        # identifies whether that original collector succeeded or failed.
        final = decode(stdout.splitlines()[-1])
        need(final['checks_passed'] is (expected_exit == 0) and final['formal_acceptance'] is False,
             'OUTER_RESULT_LINE')
    return capture


def process_capture(ev, run, role, expected_exit, frozen, result):
    directory = run + '/' + role + '-owner'
    ev.files(directory)
    cap = ev.obj(directory + '/reader-capture.json')
    need(cap == result[role + '_capture'] and cap['schema'] == 'HH-S97-READER-PROCESS-CAPTURE-1',
         'INNER_CAPTURE_BINDING')
    for flag in ('formal_acceptance', 'native_benchmark', 's96_cause_proven'):
        need(cap[flag] is False, 'INNER_SCOPE')
    for flag in ('natural_tree_exit', 'drains_joined', 'source_unchanged', 'close_before_finish_is_diagnostic_only'):
        need(cap[flag] is True, 'INNER_TERMINAL')
    need(exact_int(cap['active_at_helper_exit']) and cap['active_before_cleanup'] == 0 and
         type(cap['active_before_cleanup']) is int and exact_int(cap['helper_pid'], 1) and
         cap['actual_helper_exit'] == expected_exit, 'INNER_HELPER_EXIT')
    start, end = ev.obj(directory + '/process-start.json'), ev.obj(directory + '/process-exit.json')
    need(set(start) == {'pid'} and exact_int(start['pid'], 1) and set(end) == {'pid', 'exit_code'} and
         type(end['exit_code']) is int and end == {'pid': start['pid'], 'exit_code': expected_exit} and
         cap['actual_process_start'] == start and cap['actual_process_exit'] == end, 'INNER_TARGET_EXIT')
    need(set(cap['artifacts']) == {'invocation.json', 'stdout.txt', 'stderr.txt', 'process-start.json',
                                  'process-exit.json'}, 'INNER_ARTIFACT_SET')
    for name, digest in cap['artifacts'].items():
        need(sha(ev.raw(directory + '/' + name)) == digest, 'INNER_ARTIFACT_HASH:' + name)
    clean_job(cap['job'])
    need(cap['wrapper_process_handle'] == HANDLE, 'INNER_HANDLE')
    cleanup = ev.obj(directory + '/cleanup-001.json')
    need(cleanup == {'closed': True, 'completed': False, 'failure_code': 'BENCHMARK_CLOSED_BEFORE_FINISH',
                     'job': cap['job'], 'wrapper_exit_code': expected_exit,
                     'wrapper_process_handle': HANDLE}, 'INNER_CLEANUP_PRESERVED')
    inv = ev.obj(directory + '/invocation.json')
    combined = dict(frozen['source_files'])
    combined.update({PREFIX + run + '/project/' + name: digest for name, digest in frozen['project_files'].items()})
    need(inv['source_files'] == combined and inv['binary_sha256'] == frozen['godot_sha256'] and
         inv['formal_acceptance'] is False and inv['profile']['process_limit'] == 4, 'INNER_INVOCATION_BINDING')
    expected_args = [frozen['godot'], '--headless', '--editor', '--path', inv['cwd'], '--import'] if role == 'import' else [
        frozen['godot'], '--editor', '--path', inv['cwd'], 'res://scenes/fixture.tscn', '--', '--hh-reader-regression']
    need(inv['argv'] == expected_args and Path(inv['cwd']).name == 'project' and
         Path(inv['cwd']).parent.name == frozen['run_id'], 'INNER_ARGV')
    if role == 'import':
        need(not ev.raw(directory + '/stderr.txt').strip(), 'IMPORT_STDERR')
    return cap


def line_in(raw, function, text):
    lines = raw.decode('utf-8').splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith('func ' + function + '('))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('func ')), len(lines))
    hits = [i + 1 for i in range(start, end) if lines[i].strip() == text]
    need(len(hits) == 1, 'EXPECTED_DIAGNOSTIC_SOURCE_LINE')
    return hits[0]


def parser_stderr(candidate, harness, stage):
    method = '_wait_host_' + stage
    lines = ["ERROR: Parse JSON failed. Error at line 0: Expected '}'",
             '   at: parse_string (core/io/json.cpp:629)', '   GDScript backtrace (most recent call first):',
             f'       [0] {method} (res://addons/hh_benchmark/benchmark_native.gd:{line_in(candidate, method, "var decoded: Variant = JSON.parse_string(raw.get_string_from_utf8())")})',
             f'       [1] _process (res://addons/hh_benchmark/benchmark_native.gd:{line_in(candidate, "_process", method + "()")})',
             f'       [2] _process (res://addons/hh_benchmark/reader_regression.gd:{line_in(harness, "_process", "super._process(delta)")})']
    return ('\n'.join(lines) + '\n').encode()


def reader(ev, run, stage, case, frozen, result, native_cap, candidate, harness):
    out = run + '/project/benchmark/out/'
    row = ev.obj(out + 'reader-result.json')
    success = case in ('normal', 'read_overlap', 'locked_release')
    suffix = {'locked_timeout': 'TIMEOUT', 'malformed': 'JSON', 'locked_malformed': 'JSON',
              'wrong_hash': 'HASH', 'wrong_schema': 'BINDING', 'empty': 'SIZE', 'oversized': 'SIZE',
              'short_read': 'SHORT_READ', 'locked_short_read': 'SHORT_READ'}.get(case)
    expected_code = stage.upper() + '_VALIDATED' if success else 'BENCHMARK_HOST_' + stage.upper() + '_' + suffix
    need(row['schema'] == 'HH-S97-NATIVE-READER-REGRESSION-1' and row['case'] == case and row['stage'] == stage and
         row['status'] == ('success' if success else 'failed') and row['code'] == expected_code and
         row['pid'] == native_cap['actual_process_exit']['pid'] and row['source_candidate_sha256'] == CANDIDATE,
         'READER_BINDING')
    need(row['formal_acceptance'] is False and row['native_benchmark'] is False and
         row['buffer_shortening_injected'] is (case in ('short_read', 'locked_short_read')), 'READER_SCOPE')
    need(exact_int(row['deadline_before_us'], 1) and row['deadline_before_us'] == row['deadline_after_us'] and
         row['advances'] == int(success), 'READER_DEADLINE_OR_ADVANCE')
    receipts = row[stage + '_receipts']
    need(len(receipts) == int(success) and row['ack_receipts' if stage == 'start' else 'start_receipts'] == [],
         'READER_RECEIPTS')
    payload = ev.raw(run + '/project/benchmark/input/' + stage + '-00.json')
    need(result['publication']['payload_sha256'] == sha(payload) and result['publication']['size_bytes'] == len(payload),
         'PUBLISHED_BYTES')
    ready = ev.obj(out + 'reader-ready.json')
    need(ready['stage'] == stage and ready['case'] == case and ready['source_candidate_sha256'] == CANDIDATE and
         ready['deadline_mono_us'] == row['deadline_before_us'], 'READER_READY')
    if success:
        receipt = receipts[0]
        need(receipt[stage + '_sha256'] == sha(payload) and receipt[stage + '_size_bytes'] == len(payload) and
             receipt['deadline_mono_us'] == row['deadline_after_us'] and receipt['batch_index'] == 0 and
             receipt['issued_mono_us'] < receipt[stage + '_observed_mono_us'] <= row['monotonic_us'] <=
             row['deadline_after_us'], 'READER_RECEIPT_BINDING')
        need(not ev.has(out + 'failure.json'), 'UNEXPECTED_NATIVE_FAILURE')
    else:
        failure = ev.obj(out + 'failure.json')
        need(failure['code'] == expected_code and failure['pid'] == row['pid'] and failure['batch'] == 0 and
             failure['completed'] is False and failure['formal_acceptance'] is False and
             failure['input']['run_id'] == frozen['run_id'], 'NATIVE_FAILURE_BINDING')
    locked, timeout = case.startswith('locked_'), case == 'locked_timeout'
    need(exact_int(row['attempts'], 1) and (row['attempts'] >= 2 if locked else row['attempts'] == 1) and
         (row['first_error'] != 0 if locked else row['first_error'] == 0) and
         row['open_recovered'] is (locked and not timeout), 'OPEN_STATE')
    if locked:
        need(row['pending_frames'] >= 2 and row['process_frame'] > row['first_error_frame'] and
             row['first_error_mono_us'] > 0, 'NORMAL_FRAME_RETRY')
    need(row['monotonic_us'] > row['deadline_after_us'] if timeout else
         row['monotonic_us'] <= row['deadline_after_us'], 'UNCHANGED_TERMINAL_DEADLINE')
    need(0 <= row['max_heartbeat_gap_us'] <= 2_000_000, 'HEARTBEAT_BOUND')
    stdout = ev.raw(run + '/native-owner/stdout.txt')
    need(not re.search(rb'\b(?:ERROR|WARNING)\b|ObjectDB instances leaked', stdout), 'UNEXPECTED_NATIVE_LOG')
    lines = stdout.decode('utf-8').splitlines()
    markers = lambda prefix: [decode(line[len(prefix):]) for line in lines if line.startswith(prefix)]
    events = markers('HH_GT06_HOST_INPUT_OPEN ')
    need([item['event'] for item in events] == (['pending', 'terminal'] if timeout else
         ['pending', 'recovered'] if locked else []), 'BOUNDED_OPEN_DIAGNOSTICS')
    for item in events:
        need(item['stage'] == stage and item['batch'] == 0 and item['scope'] == 'open_only_not_receipt' and
             item['first_error'] == row['first_error'] and item['first_mono_us'] == row['first_error_mono_us'] and
             item['first_process_frame'] == row['first_error_frame'], 'FIRST_ERROR_RETAINED')
    if events:
        need(events[-1]['attempts'] == row['attempts'], 'FINAL_ATTEMPT_COUNT')
    need(markers('HH_GT06_BENCHMARK_' + stage.upper() + ' ') == receipts, 'RECEIPT_LOG_BINDING')
    failed = markers('HH_GT06_BENCHMARK_FAILED ')
    need(failed == ([] if success else [{'code': expected_code, 'pid': row['pid'], 'batch': 0,
                                       'cycle': 0, 'completed': False}]), 'FAILED_LOG_BINDING')
    need(not markers('HH_GT06_BENCHMARK_COMPLETE ') and not ev.has(out + 'index.json'), 'NOT_NATIVE_BENCHMARK')
    stderr = ev.raw(run + '/native-owner/stderr.txt')
    if case in ('malformed', 'locked_malformed'):
        need(payload == b'{' and stderr.replace(b'\r\n', b'\n') == parser_stderr(candidate, harness, stage),
             'EXACT_EXPECTED_PARSER_DIAGNOSTIC')
    else:
        need(not stderr.strip(), 'UNEXPECTED_NATIVE_STDERR')
    return row


def validate(ev, selection):
    need(selection['schema'] == 'HH-S97-READER-SELECTION-1' and selection['writers_stopped'] is True,
         'STOPPED_SELECTION_REQUIRED')
    late_driver = selection['matrix02_driver_sha256']
    need(late_driver == FINAL_DRIVER, 'MATRIX02_DRIVER_PIN')
    selected = selection['cases']
    need(len(selected) == 24 and [(x['stage'], x['case']) for x in selected] == WORK, 'EXACT_24_CASE_SELECTION')
    baseline = None
    reports = []
    for item in selected:
        stage, case = item['stage'], item['case']
        run_id = 'gt06-s97-reader-' + stage + '-' + case.replace('_', '-') + '-01'
        run = 'reader-regression/runs/' + run_id
        need(item['run'] == run, 'FIXED_RUN_ID')
        corrected = (stage, case) == ('start', 'malformed')
        first = (stage, case) == ('start', 'normal')
        tranche1 = stage == 'start' and case in ('read_overlap', 'locked_release', 'locked_timeout', 'malformed')
        outer_root = 'reader-start-normal-owned-01' if first else 'reader-matrix-owned-' + ('01' if tranche1 else '02')
        expected_outer = outer_root + ('/capture.json' if first else '/' + stage + '-' + case + '/capture.json')
        need(item['outer_capture'] == expected_outer and item['outer_invocation'] == outer_root + '/invocation.json',
             'FIXED_OUTER_MAPPING')
        driver = OLD_DRIVER if first else FIRST_DRIVER if tranche1 else late_driver
        ev.files(run)
        ev.files(run + '/source', recursive=True, pool=True)
        ev.files(run + '/project', recursive=True, project=True)
        frozen, result = ev.obj(run + '/freeze.json'), ev.obj(run + '/result.json')
        need(frozen['run_id'] == result['run_id'] == run_id and frozen['case'] == case and frozen['stage'] == stage,
             'CASE_BINDING')
        for record in (frozen, result):
            for flag in ('formal_acceptance', 'native_benchmark', 's96_cause_proven'):
                need(record[flag] is False, 'CASE_SCOPE')
        source_files, project_files = hash_map(frozen['source_files']), hash_map(frozen['project_files'])
        need(source_files[DRIVER_PATH] == driver and source_files[GDS_PATH] == GDS and
             source_files[NATIVE_PATH] == CANDIDATE, 'FROZEN_PINS')
        common = {name: digest for name, digest in source_files.items() if name != DRIVER_PATH}
        if baseline is None:
            baseline = common
        need(common == baseline, 'RUNTIME_OR_HARNESS_CHANGED_BETWEEN_CASES')
        for name, digest in source_files.items():
            need(sha(ev.raw(run + '/source/' + name, pool=True)) == digest, 'SOURCE_SNAPSHOT_HASH:' + name)
        for name, digest in project_files.items():
            need(sha(ev.raw(run + '/project/' + name)) == digest and
                 sha(ev.raw(run + '/source/' + PREFIX + run + '/project/' + name, pool=True)) == digest,
                 'PROJECT_AND_SNAPSHOT_HASH:' + name)
        candidate = ev.raw(run + '/source/' + NATIVE_PATH, pool=True)
        harness = ev.raw(run + '/source/' + GDS_PATH, pool=True)
        executed = ev.raw(run + '/project/addons/hh_benchmark/benchmark_native.gd')
        injected = case in ('short_read', 'locked_short_read')
        nl = b'\r\n' if b'\r\n' in candidate else b'\n'
        needle = b'    var raw: PackedByteArray = file.get_buffer(size)' + nl
        seam = b'    raw.resize(maxi(0, raw.size() - 1)) # S97 injected short-read seam' + nl
        need(candidate.count(needle) == 2 and seam not in candidate, 'CANDIDATE_SEAM_ANCHOR')
        need(executed == (candidate.replace(needle, needle + seam) if injected else candidate) and
             (not injected or executed.count(seam) == 2 and executed.replace(seam, b'') == candidate),
             'EXACT_EXECUTED_OVERLAY_REVERSAL')
        need(frozen['candidate_sha256'] == CANDIDATE and frozen['executed_candidate_sha256'] == sha(executed) and
             frozen['buffer_shortening_injected'] is injected and frozen['seam_exact_reversal'] is injected,
             'OVERLAY_METADATA')
        config = ev.obj(run + '/project/benchmark/reader-case.json')
        binding = ev.obj(run + '/project/benchmark/input.json')
        need(config['binding'] == binding and config['stage'] == stage and config['case'] == case and
             binding['source_closure_sha256'] == closure(source_files) and binding['run_id'] == run_id and
             binding['mode'] == 'full' and binding['batch_barrier'] == 'host_ack_v1' and
             binding['batch_start'] == 'host_permit_v1', 'INPUT_FREEZE_BINDING')
        lock = decode(ev.raw(run + '/source/studio/toolchain.lock.json', pool=True))['godot']
        need(lock['gui_sha256'] == frozen['godot_sha256'] and lock['source_commit'] == frozen['godot_commit'] and
             lock['version'] == '4.7.2-stable', 'BINARY_IDENTITY_BINDING')
        imported = process_capture(ev, run, 'import', 0, frozen, result)
        success = case in ('normal', 'read_overlap', 'locked_release')
        captured = process_capture(ev, run, 'native', 0 if success else 86, frozen, result)
        raw_reader = reader(ev, run, stage, case, frozen, result, captured, executed, harness)
        outer_record = outer(ev, item['outer_capture'], 1 if corrected else 0, stage, case, run_id)
        invocation = ev.obj(item['outer_invocation'])
        expected_outer_sources = {DRIVER_PATH: driver, GDS_PATH: GDS, NATIVE_PATH: CANDIDATE,
                                  BOOTSTRAP_PATH: BOOTSTRAP_SHA}
        need(invocation['source_files'] == expected_outer_sources and invocation['formal_acceptance'] is False,
             'OUTER_SOURCE_BINDING')
        need(sha(ev.raw('@workspace/' + BOOTSTRAP_PATH, pool=True)) == BOOTSTRAP_SHA, 'OUTER_BOOTSTRAP_PIN')
        if corrected:
            need(result['checks_passed'] is False and result['completed'] is False and len(result['errors']) == 1 and
                 result['errors'][0]['class'] == 'RuntimeError' and result['errors'][0]['code'] == 'READER_NATIVE_STDERR',
                 'ONLY_ALLOWED_COLLECTOR_FAILURE')
            correction(ev, item, run, result, raw_reader, late_driver)
        else:
            need('derived_validation' not in item and result['checks_passed'] is True and result['completed'] is True and
                 result['errors'] == [], 'ORIGINAL_COLLECTOR_RESULT')
            extra = {'pending_memory_observation_only': True, 'whole_editor_memory_plateau_proven': False}
            # Later collector versions may add a narrowly scoped diagnostic note.
            need(all(result['reader'].get(name) == value for name, value in raw_reader.items()) and
                 all(result['reader'].get(name) is value for name, value in extra.items()), 'RESULT_READER_BINDING')
        if case.startswith('locked_') or case == 'read_overlap':
            holder = result['holder']
            need(holder['closed'] is True and holder['close_error'] is None and holder['share_read_write_delete'] is True and
                 holder['delete_access'] is case.startswith('locked_') and
                 holder['closed_qpc_ns'] >= holder['opened_qpc_ns'], 'HOLDER_CLEANUP')
        reports.append({'run_id': run_id, 'stage': stage, 'case': case, 'driver_sha256': driver,
                        'diagnostic_case_verified': True, 'native_actual_exit': 0 if success else 86,
                        'expected_negative_native_exit': not success,
                        'original_outer_actual_exit': outer_record['exit_code'],
                        'collector_only_derived_correction': corrected,
                        'import_pid': imported['actual_process_start']['pid'],
                        'native_pid': captured['actual_process_start']['pid']})
    return {'schema': 'HH-S97-READER-VALIDATION-1', **FLAGS, 'case_count': 24,
            'all_selected_cases_verified': True, 'cases': reports,
            'limits': ['Reader fixture bypasses production boot/admission and uses near-deadline offers.',
                       'Expected native exit 86 is successful rejection coverage, not PASS-native.',
                       'No absent-to-pending, post-validation deadline crossing, or owned Stop case.',
                       'Pending memory observations do not prove a whole-editor memory plateau.',
                       'Binary hashes bind captured identities; the executable binary is not bundled.',
                       'Outer actual target exits come from retained host receipts, never self-reported success.']}


def correction(ev, item, run, result, raw_reader, validator_sha):
    """One explicit metadata-only correction; never authorize other failures."""
    need(item.get('derived_validation') == 'reader-start-malformed-revalidated-01.json' and
         item.get('derived_outer_capture') == 'reader-revalidation-owned-02/capture.json', 'FIXED_CORRECTION_MAPPING')
    need(sha(ev.raw(item['derived_validation'])) == DERIVED_SHA, 'DERIVED_EXACT_PIN')
    derived = ev.obj(item['derived_validation'])
    need(derived['schema'] == 'HH-S97-READER-REVALIDATION-1' and
         derived['original_run_id'] == result['run_id'] and derived['stage'] == 'start' and
         derived['case'] == 'malformed' and derived['validator_driver_sha256'] == validator_sha == FINAL_DRIVER and
         derived['tested_driver_sha256'] == FIRST_DRIVER, 'DERIVED_BINDING')
    for key in ('engine_rerun', 'formal_acceptance', 'native_benchmark', 's96_cause_proven'):
        need(derived[key] is False, 'DERIVED_SCOPE')
    for key in ('checks_passed', 'expected_parser_diagnostic_matched', 'raw_evidence_unchanged',
                'original_harness_failure_retained', 'orchestrator_own_exit_is_separate_outer_evidence'):
        need(derived[key] is True, 'DERIVED_CHECK')
    bindings = {'original_result_sha256': 'result.json', 'original_freeze_sha256': 'freeze.json',
                'original_native_capture_sha256': 'native-owner/reader-capture.json',
                'original_import_capture_sha256': 'import-owner/reader-capture.json',
                'original_native_stdout_sha256': 'native-owner/stdout.txt',
                'original_native_stderr_sha256': 'native-owner/stderr.txt'}
    for key, name in bindings.items():
        need(derived[key] == sha(ev.raw(run + '/' + name)), 'DERIVED_ORIGINAL_HASH')
    names = {'freeze.json', 'result.json', 'project/benchmark/out/failure.json',
             'project/benchmark/out/reader-result.json'}
    names.update(role + '-owner/' + name for role in ('native', 'import') for name in
                 ('invocation.json', 'process-start.json', 'process-exit.json', 'reader-capture.json',
                  'stdout.txt', 'stderr.txt'))
    need(set(derived['evidence_sha256']) == names, 'DERIVED_EVIDENCE_SET')
    for name, digest in derived['evidence_sha256'].items():
        need(sha(ev.raw(run + '/' + name)) == digest, 'DERIVED_EVIDENCE_HASH')
    expected_reader = {**raw_reader, 'pending_memory_observation_only': True,
                       'whole_editor_memory_plateau_proven': False,
                       'stderr_classification': 'exact_expected_malformed_json_diagnostic'}
    need(derived['revalidated_reader'] == expected_reader, 'DERIVED_READER_BINDING')
    cap = outer(ev, item['derived_outer_capture'], 0)
    need(cap['argv'] == ['python.exe', '-B', '$SNAPSHOT/' + DRIVER_PATH, '--revalidate', '--run-id',
                         result['run_id'], '--stage', 'start', '--case', 'malformed'], 'DERIVED_OUTER_ARGV')
    need(ev.obj('reader-revalidation-owned-02/' + cap['stdout']) == derived, 'DERIVED_ACTUAL_STDOUT')
    inv = ev.obj('reader-revalidation-owned-02/invocation.json')
    need(inv['engine_launch'] is False and inv['formal_acceptance'] is False and inv['source_files'] == {
        DRIVER_PATH: FINAL_DRIVER, BOOTSTRAP_PATH: BOOTSTRAP_SHA}, 'DERIVED_INVOCATION')
    validator_copy = 'reader-regression/runs/gt06-s97-reader-start-locked-malformed-01/source/' + DRIVER_PATH
    need(sha(ev.raw(validator_copy, pool=True)) == FINAL_DRIVER, 'DERIVED_VALIDATOR_SOURCE')
    aborted = ev.obj('reader-revalidation-owned-01/prelaunch-aborted.json')
    need(aborted['owned_child_launched'] is False and aborted['engine_launched'] is False and
         aborted['formal_acceptance'] is False, 'PRELAUNCH_ABORT_PRESERVED')


def ingest_outer_metadata(ev, selection):
    for folder in ('reader-start-normal-owned-01', 'reader-matrix-owned-01',
                   'reader-matrix-owned-02', 'reader-revalidation-owned-01', 'reader-revalidation-owned-02'):
        ev.files(folder)
    # The first matrix deliberately stopped on its collector failure; the next
    # contains only the 19 unexecuted cases. Both histories stay intact.
    first = ev.obj('reader-matrix-owned-01/summary.json')
    second = ev.obj('reader-matrix-owned-02/summary.json')
    expected_first = [('start', name) for name in ('read_overlap', 'locked_release', 'locked_timeout', 'malformed')]
    expected_second = [pair for pair in WORK if pair != ('start', 'normal') and pair not in expected_first]
    for summary, expected, completed in ((first, expected_first, False), (second, expected_second, True)):
        need(summary['all_completed'] is completed and summary['source_unchanged'] is True and
             summary['formal_acceptance'] is False and
             [(row['stage'], row['case']) for row in summary['results']] == expected, 'MATRIX_TERMINAL_SELECTION')
        for row in summary['results']:
            expected_exit = 1 if (row['stage'], row['case']) == ('start', 'malformed') else 0
            need(row['exit_code'] == expected_exit and row['wrapper_exit_code'] == 0 and row['tree_verified'] is True,
                 'MATRIX_ORIGINAL_OUTCOME')
    need(first['expected_count'] == 23 and second['expected_count'] == 19, 'MATRIX_EXPECTED_COUNTS')


def seal(selection_path, output):
    need(not output.exists() and output.parent == BASE and re.fullmatch('reader-validation-packet-[0-9]{2}', output.name),
         'EXCLUSIVE_PACKET_OUTPUT')
    output.mkdir()
    try:
        selection_raw = checked(selection_path)
        selection = decode(selection_raw)
        ev = Evidence()
        ingest_outer_metadata(ev, selection)
        report = validate(ev, selection)
        # Re-read the bounded selected bytes before publishing a success seal.
        # This is evidence stability checking, not a runtime/source-tree sweep.
        for key, row in ev.inventory.items():
            loc = row['raw_locator']
            original = (ROOT if loc['base'] == 'workspace' else BASE) / loc['path']
            need(sha(checked(original)) == row['sha256'], 'EVIDENCE_CHANGED_BEFORE_SEAL:' + key)
        written = set()
        for key, row in ev.inventory.items():
            destination = row['packet_path']
            if destination not in written:
                put(output / destination, ev.cache[key])
                written.add(destination)
            else:
                need(sha(checked(output / destination)) == row['sha256'], 'POOL_COLLISION')
        put(output / 'selection.json', selection_raw)
        put(output / 'validation.json', encoded(report))
        manifest = {'schema': 'HH-S97-READER-PACKET-1', **FLAGS,
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'selection_sha256': sha(selection_raw), 'validation_sha256': sha(encoded(report)),
                    'packer_sha256': sha(checked(Path(__file__))), 'inventory': ev.inventory,
                    'raw_bytes_read': ev.total, 'unique_stored_files': len(written),
                    'exclusions': ['.godot', '__pycache__', '.git', '*.pyc', '*.pyo',
                                   'owner appdata/localappdata/temp/blender-user cache directories'],
                    'original_normal01_driver_preserved': OLD_DRIVER,
                    'raw_evidence_unchanged': True}
        put(output / 'manifest.json', encoded(manifest))
        return verify(output)
    except BaseException as error:
        if not (output / 'failure.json').exists():
            put(output / 'failure.json', encoded({'schema': 'HH-S97-READER-PACKET-FAILURE-1', **FLAGS,
                'completed': False, 'error_class': type(error).__name__, 'error': str(error)}))
        raise


def verify(packet):
    need(not (packet / 'failure.json').exists(), 'FAILED_PACKET')
    manifest = decode(checked(packet / 'manifest.json', 32 * 1024 * 1024))
    need(manifest['schema'] == 'HH-S97-READER-PACKET-1', 'PACKET_SCHEMA')
    selection_raw, validation_raw = checked(packet / 'selection.json'), checked(packet / 'validation.json')
    need(sha(selection_raw) == manifest['selection_sha256'] and sha(validation_raw) == manifest['validation_sha256'],
         'PACKET_ROOT_HASH')
    ev = Evidence(packet, manifest['inventory'])
    for key in manifest['inventory']:
        ev.raw(key)
    selection = decode(selection_raw)
    ingest_outer_metadata(ev, selection)
    report = validate(ev, selection)
    need(report == decode(validation_raw), 'PACKET_REVALIDATION_CHANGED')
    return {'packet': str(packet), 'verified_cases': 24, 'packet_integrity_verified': True,
            'manifest_sha256': sha(checked(packet / 'manifest.json', 32 * 1024 * 1024)), **FLAGS}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--selection', type=Path)
    group.add_argument('--verify-packet', type=Path)
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    try:
        if options.verify_packet:
            need(options.output is None, 'VERIFY_HAS_NO_OUTPUT')
            answer = verify(options.verify_packet.absolute())
        else:
            need(options.output is not None, 'PACKET_OUTPUT_REQUIRED')
            answer = seal(options.selection.absolute(), options.output.absolute())
        print(json.dumps(answer, sort_keys=True))
    except BaseException as error:
        print(json.dumps({'completed': False, 'error_class': type(error).__name__, 'error': str(error), **FLAGS}))
        sys.exit(1)
