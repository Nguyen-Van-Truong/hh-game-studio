"""Synthetic assembly plus one tiny loopback fixture; no engines or native claims."""
import copy
from contextlib import contextmanager
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_assembly as assembly
from studio.tests.replay import benchmark_profile as profile
from studio.protocol.core import canonical_bytes

RUN = 'synthetic.assembly'
SOURCE = 'e' * 64
PROCESSES = {'host': {'pid': 101, 'process_start': 'windows:10001'},
             'editor': {'pid': 202, 'process_start': 'windows:10002'}}


def counter(value, reason=None):
    return {'value': value, 'unavailable_reason': reason}


def host_counters():
    return {'rss_bytes': counter(1000000), 'held_handles': counter(20),
            'objects': counter(None, profile.HOST_NOT_APPLICABLE),
            'resources': counter(None, profile.HOST_NOT_APPLICABLE)}


def artifact(name, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return assembly.BoundArtifact(name, hashlib.sha256(raw).hexdigest(), raw)


def terminal_fields(row, *, canceled=False):
    status, code = ('CANCELED', 'CANCELED_BEFORE_APPLY') if canceled else ('COMMITTED', 'READBACK_CONFIRMED')
    response = {'status': status, 'code': code, 'command_id': row['command_id'],
        'result_revision': None if canceled else row['snapshot']['revision'],
        'result_hash': None if canceled else row['result_hash'],
        'postconditions': {'request_digest': row['request_digest'],
                          **({'no_effect': True} if canceled else {'snapshot': row['snapshot']})}}
    return {'terminal_response': response, 'lookup_attempts': [{'status': status, 'code': code,
        'command_id': row['command_id'], 'request_digest': row['request_digest'],
        'started_mono_us': row['receipt_mono_us'] + 1, 'ended_mono_us': row['terminal_mono_us']}]}


def command_fixture(index=0):
    start = 1000000000000 + index * 10000000  # Incomparable with Godot's clock origin.
    tick, effects = start + 100, index * 200
    rows, status = [], [start]
    latencies = {kind: [] for kind in ('inspect', 'rejected', 'admitted')}
    cancel = None
    for ordinal in range(1000):
        kind = (['inspect'] * 5 + ['rejected'] * 3 + ['admitted'] * 2)[ordinal % 10]
        row = {'ordinal': ordinal, 'group': ordinal // 10, 'kind': kind,
               'command_id': f'{RUN}.b{index}.{kind}.{len(latencies[kind])}', 'started_mono_us': tick,
               'receipt_mono_us': tick + 1000, 'receipt_ms': 1.0,
               'receipt_status': 'REJECTED' if kind == 'rejected' else 'ACCEPTED_PENDING',
               'receipt_code': 'INVALID_FIXTURE_PAYLOAD' if kind == 'rejected' else 'QUEUED',
               'request_digest': 'sha256:' + 'f' * 64, 'effect_count_before': effects, 'lookup_attempts': []}
        status.append(tick + 1000)
        if kind != 'rejected':
            effects += int(kind == 'admitted')
            snapshot = {'effect_count': effects, 'revision': f'rev-{effects}', 'value': effects}
            row.update(terminal_mono_us=tick + 2000, terminal_ms=2.0, terminal_code='READBACK_CONFIRMED',
                       terminal_status='COMMITTED', snapshot=snapshot,
                       result_hash='sha256:' + hashlib.sha256(canonical_bytes(snapshot)).hexdigest())
            row.update(terminal_fields(row))
            status.append(tick + 2000)
            tick += 2000
        else:
            row['terminal_status'] = 'REJECTED'
            tick += 1000
        row['effect_count_after'] = effects
        row['latency_ms'] = 2.0 if kind == 'inspect' else 1.0
        latencies[kind].append(row['latency_ms'])
        rows.append(row)
        if ordinal == 499:
            cancel = {'command_id': f'{RUN}.b{index}.cancel', 'kind': 'cancel', 'separate_from_mix': True,
                      'delay_ms': 1000, 'started_mono_us': tick + 100, 'receipt_mono_us': tick + 1100,
                      'receipt_ms': 1.0, 'status': 'CANCELED', 'terminal_status': 'CANCELED',
                      'request_digest': 'sha256:' + 'f' * 64, 'no_effect': True,
                      'terminal_mono_us': tick + 1200, 'terminal_ms': 1.1}
            cancel.update(terminal_fields(cancel, canceled=True))
            status.extend([tick + 50, tick + 1100, tick + 1200])
            tick += 1300
        tick += 100
    end = tick + 100
    status.append(end)
    observation = lambda time: {'process': copy.deepcopy(PROCESSES['host']), 'monotonic_us': time, 'counters': host_counters()}
    return {'schema_id': 'hh-studio.benchmark-command-batch', 'schema_version': '1.1.0',
            'run_id': RUN, 'index': index, 'mode': 'benchmark', 'complete_command_mix': True,
            'native_acceptance': False, 'effects_kind': 'in_process_mock_fixture',
            'transport_kind': 'accepted_loopback_fixture_http', 'observation_kind': 'native_windows_process_probe',
            'host_process': copy.deepcopy(PROCESSES['host']), 'warmup': index < 5, 'commands': rows,
            'latency_ms': latencies, 'effects_per_admission': [1] * 200, 'cancel': cancel, 'status': 'COMPLETE',
            'started_mono_us': start, 'ended_mono_us': end, 'memory_before': observation(start + 1),
            'memory_after': observation(end - 1), 'effect_count_before': index * 200, 'effect_count_after': (index + 1) * 200,
            'dropped_commands': 0, 'dropped_telemetry': 0, 'journal_bytes': 100000,
            'diagnostic_retention': 'expected rejection receipts retained', 'host_response_mono_us': status,
            'max_status_gap_ms': max(b - a for a, b in zip(status, status[1:])) / 1000,
            'status_gap_scope': 'host command-lane response progress; not editor UI heartbeat'}


def add_lookup_recovery(value, *, canceled=False, extra_us=2000):
    """Insert one timed loss and move later host events, never native clocks."""
    row = value['cancel'] if canceled else value['commands'][0]
    threshold = row['terminal_mono_us']
    def shift(item):
        if type(item) is dict:
            for key, child in item.items():
                if key.endswith('_mono_us') and type(child) is int and child >= threshold:
                    item[key] += extra_us
                elif key == 'host_response_mono_us':
                    item[key] = [stamp + extra_us if stamp >= threshold else stamp for stamp in child]
                elif key == 'monotonic_us' and type(child) is int and child >= threshold:
                    item[key] += extra_us
                else:
                    shift(child)
        elif type(item) is list:
            for child in item:
                shift(child)
    shift(value)
    row['terminal_ms'] += extra_us / 1000
    if not canceled:
        row['latency_ms'] = row['terminal_ms']
        value['latency_ms']['inspect'][0] = row['terminal_ms']
    attempt = {'status': 'UNKNOWN', 'code': 'CONNECTION_LOST_LOOKUP', 'command_id': row['command_id'],
        'request_digest': None, 'started_mono_us': row['receipt_mono_us'] + 1,
        'ended_mono_us': row['receipt_mono_us'] + 50}
    row['lookup_attempts'][0]['started_mono_us'] = attempt['ended_mono_us'] + 1000
    row['lookup_attempts'].insert(0, attempt)
    stamps = value['host_response_mono_us']
    stamps.append(attempt['ended_mono_us'])
    stamps.sort()
    value['max_status_gap_ms'] = max(b - a for a, b in zip(stamps, stamps[1:])) / 1000
    return row


def fixture(index=0, source=SOURCE, scene_hash='c' * 64):
    native_base, root_base, generation_base, frame_base = index * 10000000, 1000 + index * 100, 1 + index * 100, index * 2000
    suffix = f'{index:02d}.json'
    command_value = command_fixture(index)
    command = artifact('commands/batch-' + suffix, command_value)
    ready_value = {'schema_id': 'hh-studio.native-cycle-batch-ready', 'schema_version': '1.0.0',
        'run_id': RUN, 'pid': 202, 'batch_index': index, 'source_closure_sha256': source,
        'profile_sha256': profile.PROFILE_SHA256, 'start_file': 'benchmark/input/start-' + suffix,
        'issued_mono_us': native_base + 100, 'deadline_mono_us': native_base + 600000100, 'root_instance_id': root_base,
        'generation': generation_base, 'baseline_sha256': 'a' * 64, 'scene_file_sha256': scene_hash, 'process_frame': frame_base + 1}
    ready = artifact('project/benchmark/out/ready-' + suffix, ready_value)
    start = artifact('project/benchmark/input/start-' + suffix, {
        'schema_id': 'hh-studio.native-cycle-batch-start', 'schema_version': '1.0.0', 'run_id': RUN,
        'batch_index': index, 'source_closure_sha256': source, 'profile_sha256': profile.PROFILE_SHA256,
        'command_batch_sha256': command.sha256, 'ready_sha256': ready.sha256, 'deadline_mono_us': native_base + 600000100})
    permit = {'batch_index': index, 'start_file': 'benchmark/input/start-' + suffix, 'start_sha256': start.sha256,
        'start_size_bytes': len(start.raw), 'ready_file': 'benchmark/out/ready-' + suffix, 'ready_sha256': ready.sha256,
        'command_batch_sha256': command.sha256, 'issued_mono_us': native_base + 100, 'deadline_mono_us': native_base + 600000100,
        'start_observed_mono_us': native_base + 200, 'process_frame': frame_base + 2, 'root_instance_id': root_base, 'generation': generation_base,
        'semantic_sha256': 'a' * 64, 'max_status_gap_ms': 500.0}
    cycles, timings, tick = [], [], native_base + 1000
    for number in range(100):
        timing = {'index': number, 'generation_before': generation_base + number, 'generation_after': generation_base + number + 1,
                  'reload_observed_process_frame': frame_base + 10 + number * 10}
        for step in ('create', 'undo', 'save', 'reload'):
            timing[step] = {'start_us': tick + 10, 'end_us': tick + 110}
            tick += 200
        timing['save_signal_mono_us'] = timing['save']['start_us'] + 50
        timings.append(timing)
        cycles.append({'index': number, 'root_before': root_base + number, 'root_after': root_base + number + 1,
            'before_sha256': 'a' * 64, 'created_sha256': 'b' * 64, 'undone_sha256': 'a' * 64,
            'saved_file_sha256': scene_hash, 'reloaded_sha256': 'a' * 64,
            'latency_ms': dict.fromkeys(('create', 'undo', 'save', 'reload'), .1),
            'effects': dict.fromkeys(('create', 'undo', 'save', 'reload'), 1), 'main_thread': True})
    ended = tick + 1100000
    native_value = {'schema_id': 'hh-studio.native-cycle-batch', 'schema_version': '1.2.0',
        'run_id': RUN, 'mode': 'full', 'pid': 202, 'index': index, 'warmup': index < 5,
        'started_mono_us': native_base + 1000, 'ended_mono_us': ended, 'cycles': cycles, 'raw_timings': timings,
        'memory': {'phase': 'post_batch_quiescent', 'monotonic_us': ended, 'process_frame': frame_base + 1004,
            'settle_frames': 4, 'settle_us': 1100000, 'editor': {
                'rss_bytes': counter(None, 'Requires retained host process sampler'), 'objects': counter(500),
                'resources': counter(6), 'held_handles': counter(None, 'Requires retained host process sampler')}},
        'barrier': {'mode': 'host_ack_v1', 'required': True, 'ack_file': 'benchmark/input/ack-' + suffix,
            'issued_mono_us': ended, 'deadline_mono_us': ended + 30000000, 'root_instance_id': root_base + 100,
            'generation': generation_base + 100, 'baseline_sha256': 'a' * 64}, 'start_permit': permit,
        'max_status_gap_ms': 500.0, 'dropped_commands': 0, 'dropped_telemetry': 0}
    native = artifact('project/benchmark/out/batch-' + suffix, native_value)
    ack = artifact('project/benchmark/input/ack-' + suffix, {
        'schema_id': 'hh-studio.native-cycle-batch-ack', 'schema_version': '1.0.0', 'run_id': RUN,
        'batch_index': index, 'native_batch_sha256': native.sha256, 'source_closure_sha256': source,
        'profile_sha256': profile.PROFILE_SHA256, 'deadline_mono_us': ended + 30000000})
    receipt = {'batch_index': index, 'ack_file': 'benchmark/input/ack-' + suffix, 'ack_sha256': ack.sha256,
        'ack_size_bytes': len(ack.raw), 'native_batch_sha256': native.sha256, 'issued_mono_us': ended,
        'deadline_mono_us': ended + 30000000, 'ack_observed_mono_us': ended + 1000,
        'root_instance_id': root_base + 100, 'generation': generation_base + 100, 'semantic_sha256': 'a' * 64,
        'max_status_gap_ms': 501.0, 'process_frame': frame_base + 1005, 'objects': counter(501), 'resources': counter(6)}
    host_end = command_value['ended_mono_us']
    joint_value = {'schema_id': 'hh-studio.benchmark-joint-observation', 'schema_version': '1.0.0',
        'run_id': RUN, 'index': index, 'profile_sha256': profile.PROFILE_SHA256, 'source_closure_sha256': source,
        'native_batch_sha256': native.sha256, 'command_batch_sha256': command.sha256,
        'processes': copy.deepcopy(PROCESSES), 'phase': 'post_batch_quiescent',
        'host_window': {'started_mono_us': command_value['started_mono_us'] - 100,
                        'ended_mono_us': host_end + 2000, 'ack_written_mono_us': host_end + 1000},
        'host': {'monotonic_us': host_end + 100, 'counters': host_counters()},
        'editor': {'host_mono_us': host_end + 200, 'rss_bytes': counter(10000000), 'held_handles': counter(30),
            'visible_window_handles': ['1234'], 'native_observation': {'source': 'native_ack',
            'native_mono_us': receipt['ack_observed_mono_us'], 'process_frame': frame_base + 1005,
            'objects': counter(501), 'resources': counter(6)}}, 'host_effect_count': (index + 1) * 200,
        'barrier_receipt': receipt, 'ack_ref': {'file': ack.file, 'sha256': ack.sha256, 'size_bytes': len(ack.raw)}}
    return {'native': native, 'command': command, 'joint': artifact('joint/' + suffix, joint_value),
            'ack': ack, 'ready': ready, 'start': start, 'barrier_receipt': receipt}


def write_raw(root, name, raw):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {'file': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}


def write_value(root, name, value):
    return write_raw(root, name, artifact(name, value).raw)


def complete_run_fixture(root):
    """One 35-batch synthetic run, with hashes of real source-file copies.

    Invented process observations are exclusively unit-test data. No native
    code is executed and this helper never writes a benchmark evidence package.
    """
    mapping = {
        'addons/hh_studio/plugin.gd': 'godot-addon/addons/hh_studio/plugin.gd',
        'addons/hh_studio/scene_commands.gd': 'godot-addon/addons/hh_studio/scene_commands.gd',
        'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
        'addons/hh_benchmark/benchmark_native.gd': 'tests/replay/benchmark_native.gd',
        'addons/hh_benchmark/plugin.cfg': 'tests/replay/benchmark_plugin.cfg'}
    source_names = set(mapping.values()) | {'toolchain.lock.json', 'tests/replay/benchmark_profile.py',
        'tests/replay/benchmark_commands.py', 'tests/replay/benchmark_assembly.py',
        'host/core/transport.py', 'host/replay/verified_journal.py', 'protocol/core.py'}
    files = {}
    for name in sorted(source_names):
        files[name] = write_raw(root, 'source/studio/' + name, (STUDIO / name).read_bytes())['sha256']
    closure = hashlib.sha256(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode()).hexdigest()
    refs = {'source_manifest': write_value(root, 'source-files.json', files),
            'toolchain': write_raw(root, 'toolchain.json', (STUDIO / 'toolchain.lock.json').read_bytes()),
            'profile': write_value(root, 'profile.json', asdict(profile.PROFILE))}
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': RUN, 'mode': 'full', 'source_closure_sha256': closure, 'profile_sha256': profile.PROFILE_SHA256,
        'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}
    native_sources = {}
    for destination, source in mapping.items():
        native_sources['res://' + destination] = write_raw(root, 'project/' + destination,
            (root / 'source/studio' / source).read_bytes())['sha256']
    for name in ('addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', 'project.godot'):
        native_sources['res://' + name] = write_raw(root, 'project/' + name,
            ('# Synthetic unit fixture for ' + name + '\n').encode())['sha256']
    native_sources['res://benchmark/input.json'] = write_value(root, 'project/benchmark/input.json', binding)['sha256']
    native_sources['res://benchmark/.gdignore'] = write_raw(root, 'project/benchmark/.gdignore',
        b'# HH Studio benchmark evidence is not a Godot asset.\n')['sha256']
    scene_hash = write_raw(root, 'project/scenes/fixture.tscn', b'; Synthetic scene bytes\n')['sha256']
    field_names = {'native': 'native_batches', 'command': 'command_batches', 'joint': 'joint_observations',
                   'ready': 'ready_artifacts', 'start': 'start_artifacts', 'ack': 'ack_artifacts'}
    manifest = {'schema_id': 'hh-studio.benchmark-run-assembly', 'schema_version': '1.0.0',
        'run_id': RUN, 'index': 0, 'profile_sha256': profile.PROFILE_SHA256,
        'source_closure_sha256': closure, 'processes': copy.deepcopy(PROCESSES), 'refs': refs,
        **{field: [] for field in field_names.values()}}
    batches, barriers, permits = [], [], []
    for index in range(35):
        values = fixture(index, closure, scene_hash)
        for name, field in field_names.items():
            bound = values[name]
            manifest[field].append(write_raw(root, bound.file, bound.raw))
        bound = values['native']
        batches.append({'index': index, 'file': f'batch-{index:02d}.json', 'sha256': bound.sha256,
                        'size_bytes': len(bound.raw)})
        barriers.append(values['barrier_receipt'])
        permits.append(bound.value['start_permit'])
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())
    native_index = {'schema_id': 'hh-studio.native-cycle-benchmark', 'schema_version': '1.2.0',
        'input': binding, 'pid': PROCESSES['editor']['pid'], 'engine': {'hash': lock['godot']['source_commit']},
        'display_server': 'Windows', 'editor_hint': True, 'main_thread': True, 'started_mono_us': 1,
        'ended_mono_us': barriers[-1]['ack_observed_mono_us'] + 100, 'started_unix': 1700000000.0,
        'source_files': native_sources, 'batches': batches, 'batches_completed': 35, 'host_barriers': barriers,
        'host_integrated': True, 'cycles_per_batch': 100, 'baseline_revision': 'sha256:' + 'a' * 64,
        'max_status_gap_ms': 501.0, 'heartbeat_target_met': True,
        'quiescence': {'minimum_frames': 4, 'minimum_us': 1100000}, 'host_barrier_timeout_us': 30000000,
        'counter_definitions': {'objects': 'Performance.OBJECT_COUNT -> ObjectDB::get_object_count',
            'resources': 'Performance.OBJECT_RESOURCE_COUNT -> ResourceCache::get_cached_resource_count'},
        'scope': 'direct-semantic test fixture; excludes public/API command mix and Stop latency',
        'benchmark_complete': True, 'completed': True, 'formal_acceptance': False, 'start_permits': permits,
        'host_start_timeout_us': 600000000, 'batch_order': 'host_commands_then_native_cycles_then_joint_ack'}
    refs['native_index'] = write_value(root, 'project/benchmark/out/index.json', native_index)
    complete = {'run_id': RUN, 'pid': PROCESSES['editor']['pid'], 'mode': 'full', 'batches': 35,
                'index_sha256': refs['native_index']['sha256'], 'benchmark_complete': True, 'host_integrated': True}
    refs['native_stdout'] = write_raw(root, 'native-stdout.txt', b'HH_GT06_BENCHMARK_COMPLETE ' + artifact('marker', complete).raw + b'\n')
    refs['native_stderr'] = write_raw(root, 'native-stderr.txt', b'')
    refs['cleanup'] = write_value(root, 'cleanup.json', {'schema_id': 'hh-studio.benchmark-cleanup',
        'schema_version': '1.0.0', 'run_id': RUN, 'processes': copy.deepcopy(PROCESSES),
        'host_exit_code': 0, 'editor_exit_code': 0, 'owned_tree_zero': True, 'held_handles': 0})
    return manifest


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.values = fixture()

    def assemble(self):
        return assembly.assemble_sample(**self.values, run_id=RUN, index=0,
                                        processes=PROCESSES, source_closure_sha256=SOURCE)

    def mutate(self, key, change):
        old = self.values[key]
        value = old.value
        change(value)
        self.values[key] = artifact(old.file, value)

    def test_exact_sample_uses_fresh_ack_counters_and_host_clock_only(self):
        sample = self.assemble()
        self.assertEqual(sample['memory']['editor']['objects']['value'], 501)
        self.assertEqual(sample['started_mono_us'], self.values['joint'].value['host_window']['started_mono_us'])
        self.assertEqual(len(sample['cycles']), 100)
        self.assertEqual(len(sample['latency_ms']['inspect']), 500)
        self.assertEqual(sample['effects_per_admission'], [1] * 200)
        self.assertEqual(sample['max_status_gap_ms'], 501)
        self.assertEqual(sample['stop_receipt_ms'], 1)
        self.assertNotEqual(sample['started_mono_us'], self.values['native'].value['started_mono_us'])

    def test_command_timing_aggregate_and_effect_tampering_fail(self):
        for mutation, code in (
            (lambda value: value['commands'][0].update(receipt_ms=99), 'TIMING_MISMATCH'),
            (lambda value: value['latency_ms']['inspect'].__setitem__(0, 7), 'COMMAND_AGGREGATES'),
            (lambda value: value['commands'][8].update(effect_count_after=2), 'INTEGER'),
            (lambda value: value['commands'][5].update(receipt_code='QUEUE_FULL'), 'REJECTION_KIND'),
            (lambda value: value['commands'].pop(), 'COMMAND_COUNT')):
            value = self.values['command'].value
            mutation(value)
            with self.assertRaisesRegex(assembly.AssemblyError, code):
                assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])

    def test_lookup_loss_preserves_command_and_cancel_latency_and_no_effect(self):
        value = self.values['command'].value
        row = add_lookup_recovery(value)
        cancel = add_lookup_recovery(value, canceled=True)
        validated = assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])
        self.assertEqual(row['terminal_ms'], 4.0)
        self.assertEqual(cancel['terminal_ms'], 3.1)
        self.assertEqual(cancel['receipt_ms'], 1.0)
        self.assertEqual(len(validated['commands']), 1000)
        self.assertEqual(validated['effect_count_after'], 200)
        self.assertEqual(validated['effects_per_admission'], [1] * 200)

    def test_lookup_wrong_identity_digest_retry_class_response_and_missing_clock_reject(self):
        changes = (
            (lambda row: row['lookup_attempts'][0].update(command_id='other.command'), 'LOOKUP_IDENTITY'),
            (lambda row: row['lookup_attempts'][0].update(request_digest='sha256:' + '0' * 64), 'LOOKUP_DIGEST'),
            (lambda row: row['lookup_attempts'][0].update(code='OTHER_UNKNOWN', request_digest=row['request_digest']), 'LOOKUP_RETRY_SCOPE'),
            (lambda row: row['lookup_attempts'][0].update(status='REJECTED', request_digest=row['request_digest']), 'LOOKUP_RETRY_SCOPE'),
            (lambda row: row['lookup_attempts'][-1].update(ended_mono_us=row['terminal_mono_us'] - 1), 'LOOKUP_TERMINAL'),
            (lambda row: row['terminal_response'].update(command_id='other.command'), 'TERMINAL_RESPONSE_IDENTITY'),
            (lambda row: row['terminal_response']['postconditions']['snapshot'].update(value=123), 'TERMINAL_RESPONSE_READBACK'),
            (lambda row: row['lookup_attempts'][0].update(ended_mono_us=None), 'INTEGER'))
        for change, code in changes:
            value = self.values['command'].value
            row = add_lookup_recovery(value)
            change(row)
            with self.subTest(code=code), self.assertRaisesRegex(assembly.AssemblyError, code):
                assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])
        value = self.values['command'].value
        row = add_lookup_recovery(value)
        value['host_response_mono_us'].remove(row['lookup_attempts'][0]['ended_mono_us'])
        stamps = value['host_response_mono_us']
        value['max_status_gap_ms'] = max(b - a for a, b in zip(stamps, stamps[1:])) / 1000
        with self.assertRaisesRegex(assembly.AssemblyError, 'STATUS_LOOKUP_MISSING'):
            assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])

    def test_lookup_budget_legacy_schema_and_forged_cancel_counter_rejected(self):
        value = self.values['command'].value
        add_lookup_recovery(value, extra_us=5000001)
        with self.assertRaisesRegex(assembly.AssemblyError, 'INTEGER'):
            assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])
        value = self.values['command'].value
        value['schema_version'] = '1.0.0'
        with self.assertRaisesRegex(assembly.AssemblyError, 'COMMAND_SCHEMA'):
            assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])
        value = self.values['command'].value
        value['cancel']['terminal_response']['postconditions']['no_effect'] = 1
        with self.assertRaisesRegex(assembly.AssemblyError, 'CANCEL_RESPONSE'):
            assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])

    def test_synthetic_observer_diagnostic_or_clock_loss_cannot_promote(self):
        for key, new, code in (('mode', 'diagnostic', 'COMMAND_INCOMPLETE_OR_DIAGNOSTIC'),
                              ('observation_kind', 'synthetic_test_observer', 'COMMAND_ORIGIN'),
                              ('dropped_commands', 1, 'INTEGER')):
            value = self.values['command'].value
            value[key] = new
            with self.assertRaisesRegex(assembly.AssemblyError, code):
                assembly.validate_command_batch(value, run_id=RUN, index=0, host_identity=PROCESSES['host'])

    def test_missing_or_stale_native_ack_observation_rejected(self):
        for change in (lambda value: value['editor'].pop('native_observation'),
                       lambda value: value['editor']['native_observation'].update(source='native_batch.memory'),
                       lambda value: value['editor']['native_observation'].update(objects=counter(500))):
            self.values = fixture()
            self.mutate('joint', change)
            with self.assertRaises(assembly.AssemblyError):
                self.assemble()

    def test_wrong_pid_hash_ack_deadline_and_stale_host_sample_rejected(self):
        changes = (
            lambda value: value['processes']['editor'].update(process_start='windows:99999'),
            lambda value: value.update(native_batch_sha256='0' * 64),
            lambda value: value['host'].update(monotonic_us=100),
            lambda value: value['editor'].update(host_mono_us=value['host_window']['ack_written_mono_us'] + 1))
        for change in changes:
            self.values = fixture()
            self.mutate('joint', change)
            with self.assertRaises(assembly.AssemblyError):
                self.assemble()
        self.values = fixture()
        self.values['barrier_receipt']['ack_observed_mono_us'] = self.values['barrier_receipt']['deadline_mono_us'] + 1
        with self.assertRaises(assembly.AssemblyError):
            self.assemble()

    def test_native_raw_duration_generation_and_bool_effect_rejected(self):
        for change, code in (
            (lambda value: value['cycles'][0]['latency_ms'].update(save=5), 'TIMING_MISMATCH'),
            (lambda value: value['raw_timings'][0].update(generation_after=1), 'INTEGER'),
            (lambda value: value['cycles'][0]['effects'].update(create=True), 'INTEGER'),
            (lambda value: value.update(mode='diagnostic'), 'NATIVE_DIAGNOSTIC')):
            value = self.values['native'].value
            change(value)
            with self.assertRaisesRegex(assembly.AssemblyError, code):
                assembly.validate_native_batch(value, run_id=RUN, index=0, editor_identity=PROCESSES['editor'])

    def test_wrong_start_command_binding_is_rejected(self):
        self.mutate('start', lambda value: value.update(command_batch_sha256='0' * 64))
        with self.assertRaisesRegex(assembly.AssemblyError, 'START_HASH_BINDING'):
            self.assemble()

    def test_unavailable_applicable_counter_is_preserved_not_zero(self):
        self.mutate('joint', lambda value: value['editor'].update(held_handles=counter(None, 'Native OS query unavailable')))
        sample = self.assemble()
        self.assertIsNone(sample['memory']['editor']['held_handles']['value'])
        self.assertEqual(sample['memory']['editor']['held_handles']['unavailable_reason'], 'Native OS query unavailable')

    def test_path_hash_duplicate_nonfinite_and_byte_caps(self):
        with tempfile.TemporaryDirectory(prefix='assembly-test-') as directory:
            root = Path(directory)
            raw = b'{"ok":true}'
            (root / 'sample.json').write_bytes(raw)
            reference = {'file': 'sample.json', 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}
            self.assertEqual(assembly.read_artifact(root, reference).value, {'ok': True})
            for change, code in (({'file': '../sample.json'}, 'ARTIFACT_PATH'),
                                 ({'sha256': '0' * 64}, 'ARTIFACT_HASH'),
                                 ({'size_bytes': assembly.MAX_RAW_BYTES + 1}, 'INTEGER')):
                with self.assertRaisesRegex(assembly.AssemblyError, code):
                    assembly.read_artifact(root, dict(reference, **change))
        for raw, code in ((b'{"a":1,"a":2}', 'DUPLICATE_KEY'), (b'{"a":1e999}', 'NONFINITE_JSON')):
            with self.assertRaisesRegex(assembly.AssemblyError, code):
                assembly.BoundArtifact('x.json', hashlib.sha256(raw).hexdigest(), raw).value

    def test_incomplete_dataset_is_not_promoted(self):
        with self.assertRaisesRegex(profile.BenchmarkError, 'INCOMPLETE_ARRAY'):
            assembly.assemble_dataset(dict.fromkeys(('source_closure_sha256', 'toolchain_sha256',
                'workstation_profile_sha256', 'driver_sha256', 'capture_manifest_sha256'), 'a' * 64), [])

    def test_real_tiny_http_producer_lookup_rows_interoperate_without_promoting_diagnostic(self):
        from studio.tests.replay.benchmark_commands import CommandProducer
        from studio.tests.replay.test_benchmark_commands import SyntheticObserver
        with tempfile.TemporaryDirectory(prefix='assembly-http-diagnostic-') as directory:
            producer = CommandProducer(Path(directory) / 'host', 'test.assembly.http', observer=SyntheticObserver())
            try:
                report = producer.run_diagnostic()
            finally:
                producer.close()
        self.assertEqual(report['schema_version'], '1.1.0')
        self.assertEqual(len(report['commands']), 10)
        for row in report['commands']:
            if row['kind'] == 'rejected':
                self.assertEqual(row['lookup_attempts'], [])
                continue
            ends = assembly._lookup_trace(row)
            self.assertEqual(ends[-1], row['terminal_mono_us'])
            self.assertTrue(set(ends).issubset(report['host_response_mono_us']))
            assembly._timing(row['started_mono_us'], row['terminal_mono_us'], row['terminal_ms'], host=True)
        cancel = report['cancel']
        self.assertEqual(assembly._lookup_trace(cancel, canceled=True)[-1], cancel['terminal_mono_us'])
        with self.assertRaisesRegex(assembly.AssemblyError, 'COMMAND_INCOMPLETE_OR_DIAGNOSTIC'):
            assembly.validate_command_batch(report, run_id=report['run_id'], index=0,
                                            host_identity=report['host_process'])


class CompleteRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='assembly-full-synthetic-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        cls.original = complete_run_fixture(cls.root)

    def setUp(self):
        self.manifest = copy.deepcopy(self.original)

    @contextmanager
    def changed_file(self, name, raw):
        previous = (self.root / name).read_bytes()
        try:
            yield write_raw(self.root, name, raw)
        finally:
            write_raw(self.root, name, previous)

    @contextmanager
    def changed_index(self, change):
        ref = self.manifest['refs']['native_index']
        value = json.loads((self.root / ref['file']).read_bytes())
        change(value)
        with self.changed_file(ref['file'], artifact(ref['file'], value).raw) as replacement:
            self.manifest['refs']['native_index'] = replacement
            yield

    def test_complete_35_batch_run_preserves_warmup_boundaries_and_source_hashes(self):
        bound = assembly.assemble_run(self.root, self.manifest)
        self.assertIsInstance(bound, assembly.BoundRun)
        envelope = bound.value
        self.assertEqual(envelope['source_closure_sha256'], self.manifest['source_closure_sha256'])
        self.assertEqual(envelope['toolchain_sha256'], self.manifest['refs']['toolchain']['sha256'])
        self.assertEqual(envelope['profile_sha256'], self.manifest['profile_sha256'])
        run = envelope['run']
        self.assertEqual(len(run['samples']), 35)
        self.assertEqual([sample['warmup'] for sample in run['samples']], [True] * 5 + [False] * 30)
        self.assertEqual(run['baseline'], {'after_batch_index': 4, 'memory': run['samples'][4]['memory']})
        self.assertEqual(sum(len(sample['cycles']) for sample in run['samples']), 3500)
        self.assertEqual(sum(len(sample['latency_ms']['inspect']) for sample in run['samples']), 17500)
        self.assertEqual(run['samples'][-1]['cycles'][-1]['root_after'], 4500)
        self.assertEqual(run['samples'][5]['memory']['editor']['objects']['value'], 501)
        self.assertEqual(len({sample['stop_target_instance_id'] for sample in run['samples']}), 35)
        self.assertEqual(len({sample['evidence_sha256'] for sample in run['samples']}), 35)
        sources = json.loads((self.root / self.manifest['refs']['source_manifest']['file']).read_bytes())
        self.assertEqual(sources['tests/replay/benchmark_assembly.py'],
                         hashlib.sha256((STUDIO / 'tests/replay/benchmark_assembly.py').read_bytes()).hexdigest())
        # A complete run is deliberately insufficient for a ten-run campaign.
        provenance = dict.fromkeys(('source_closure_sha256', 'toolchain_sha256', 'workstation_profile_sha256',
                                   'driver_sha256', 'capture_manifest_sha256'), 'a' * 64)
        provenance.update(source_closure_sha256=envelope['source_closure_sha256'],
                          toolchain_sha256=envelope['toolchain_sha256'])
        with self.assertRaisesRegex(profile.BenchmarkError, 'INCOMPLETE_ARRAY'):
            assembly.assemble_dataset(provenance, [bound])
        # Verify the runner handoff without manufacturing nine extra runs.
        with patch.object(profile, 'validate_dataset', side_effect=lambda dataset: dataset) as validate:
            dataset = assembly.assemble_dataset(provenance, [bound])
        validate.assert_called_once_with(dataset)
        self.assertEqual(dataset['schema_version'], '1.1.0')
        self.assertEqual(dataset['runs'], [run])
        self.assertNotIn('status', dataset)

    def test_global_heartbeat_breach_or_inconsistent_claim_is_rejected(self):
        for change, code in (
            (lambda value: value.update(max_status_gap_ms=2001, heartbeat_target_met=False), 'NATIVE_HEARTBEAT'),
            (lambda value: value.update(max_status_gap_ms=2001, heartbeat_target_met=True), 'NATIVE_TIMING_DEFINITION'),
            (lambda value: value.update(max_status_gap_ms=500), 'NATIVE_RUN_CLOCK')):
            with self.subTest(code=code), self.changed_index(change):
                with self.assertRaisesRegex(assembly.AssemblyError, code):
                    assembly.assemble_run(self.root, self.manifest)

    def test_global_clock_baseline_counter_definition_and_start_receipt_rejects(self):
        for change, code in (
            (lambda value: value.update(started_mono_us=101), 'NATIVE_RUN_CLOCK'),
            (lambda value: value['counter_definitions'].update(objects='invented counter'), 'NATIVE_COUNTER_DEFINITION'),
            (lambda value: value['start_permits'][0].update(command_batch_sha256='0' * 64), 'INDEX_BATCH_BINDING'),
            (lambda value: value['host_barriers'][0].update(objects=counter(500)), 'JOINT_BINDING'),
            (lambda value: value['host_barriers'][0].update(objects=counter(None, 'not sampled')), 'COUNTER_UNAVAILABLE')):
            with self.subTest(code=code), self.changed_index(change):
                with self.assertRaisesRegex(assembly.AssemblyError, code):
                    assembly.assemble_run(self.root, self.manifest)

    def test_source_copy_drift_and_self_consistent_wrong_runtime_mapping_rejected(self):
        frozen_name = 'source/studio/protocol/core.py'
        with self.changed_file(frozen_name, (self.root / frozen_name).read_bytes() + b'\n# drift\n'):
            with self.assertRaisesRegex(assembly.AssemblyError, 'ARTIFACT_HASH'):
                assembly.assemble_run(self.root, self.manifest)
        destination = 'project/addons/hh_studio/scene_commands.gd'
        with self.changed_file(destination, b'# Coherently rehashed, but not the frozen accepted source\n') as ref:
            with self.changed_index(lambda value: value['source_files'].update({'res://addons/hh_studio/scene_commands.gd': ref['sha256']})):
                with self.assertRaisesRegex(assembly.AssemblyError, 'NATIVE_SOURCE_CLOSURE'):
                    assembly.assemble_run(self.root, self.manifest)

    def test_missing_or_coherently_rehashed_wrong_ignore_marker_rejected(self):
        with self.changed_index(lambda value: value['source_files'].pop('res://benchmark/.gdignore')):
            with self.assertRaisesRegex(assembly.AssemblyError, 'NATIVE_SOURCE_SET'):
                assembly.assemble_run(self.root, self.manifest)
        name = 'project/benchmark/.gdignore'
        expected = (self.root / name).read_bytes()
        for wrong in (b'# changed\n', b'\xef\xbb\xbf' + expected, expected.replace(b'\n', b'\r\n')):
            with self.subTest(wrong=wrong), self.changed_file(name, wrong) as ref:
                with self.changed_index(lambda value: value['source_files'].update({'res://benchmark/.gdignore': ref['sha256']})):
                    with self.assertRaisesRegex(assembly.AssemblyError, 'NATIVE_EVIDENCE_IGNORE'):
                        assembly.assemble_run(self.root, self.manifest)

    def test_missing_batch_and_diagnostic_index_never_promote(self):
        self.manifest['command_batches'].pop()
        with self.assertRaisesRegex(assembly.AssemblyError, 'RUN_INCOMPLETE'):
            assembly.assemble_run(self.root, self.manifest)
        self.manifest = copy.deepcopy(self.original)
        with self.changed_index(lambda value: value.update(benchmark_complete=False, host_integrated=False)):
            with self.assertRaisesRegex(assembly.AssemblyError, 'NATIVE_INDEX_SCOPE'):
                assembly.assemble_run(self.root, self.manifest)

    def test_profile_trailing_newline_rejected_even_with_valid_file_hash(self):
        ref = self.manifest['refs']['profile']
        with self.changed_file(ref['file'], (self.root / ref['file']).read_bytes() + b'\n') as replacement:
            self.manifest['refs']['profile'] = replacement
            with self.assertRaisesRegex(assembly.AssemblyError, 'PROFILE_BYTES'):
                assembly.assemble_run(self.root, self.manifest)


class BoundRunProvenanceTests(unittest.TestCase):
    """Synthetic complete shapes test provenance equality, not native execution."""
    @staticmethod
    def bind(value):
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return assembly.BoundRun(sha256=hashlib.sha256(raw).hexdigest(), raw=raw)

    @classmethod
    def setUpClass(cls):
        from studio.tests.replay.test_benchmark_profile import synthetic_dataset
        cls.template = synthetic_dataset()
        cls.bound_runs = [cls.bind({
            'source_closure_sha256': cls.template['provenance']['source_closure_sha256'],
            'toolchain_sha256': cls.template['provenance']['toolchain_sha256'],
            'profile_sha256': profile.PROFILE_SHA256, 'run': run})
            for run in cls.template['runs']]

    def setUp(self):
        self.provenance = dict(self.template['provenance'])
        self.runs = list(self.bound_runs)

    def test_matching_ten_run_provenance_preserves_strict_dataset_schema(self):
        actual = assembly.assemble_dataset(self.provenance, self.runs)
        expected = copy.deepcopy(self.template)
        # Synthetic containers deliberately exercise the native assembly entry
        # point; this remains unit data and is not written as native evidence.
        expected['evidence_kind'] = 'native'
        self.assertEqual(actual, expected)

    def test_one_run_with_different_source_toolchain_or_profile_is_rejected(self):
        for field in ('source_closure_sha256', 'toolchain_sha256', 'profile_sha256'):
            with self.subTest(field=field):
                value = self.bound_runs[3].value
                value[field] = '0' * 64
                runs = list(self.bound_runs)
                runs[3] = self.bind(value)
                with self.assertRaisesRegex(assembly.AssemblyError, 'RUN_PROVENANCE_MISMATCH'):
                    assembly.assemble_dataset(self.provenance, runs)

    def test_wrong_declared_dataset_source_or_toolchain_is_rejected(self):
        for field in ('source_closure_sha256', 'toolchain_sha256'):
            with self.subTest(field=field):
                provenance = dict(self.provenance, **{field: '0' * 64})
                with self.assertRaisesRegex(assembly.AssemblyError, 'RUN_PROVENANCE_MISMATCH'):
                    assembly.assemble_dataset(provenance, self.runs)

    def test_plain_valid_run_dictionary_cannot_bypass_binding(self):
        self.runs[3] = self.bound_runs[3].value['run']
        with self.assertRaisesRegex(assembly.AssemblyError, 'BOUND_RUN_REQUIRED'):
            assembly.assemble_dataset(self.provenance, self.runs)

    def test_changed_run_or_provenance_bytes_require_a_new_binding(self):
        for field in ('run', 'source_closure_sha256'):
            with self.subTest(field=field):
                value = self.bound_runs[0].value
                if field == 'run':
                    value['run']['run_id'] = 'changed.run'
                else:
                    value[field] = '0' * 64
                changed = self.bind(value)
                runs = list(self.bound_runs)
                runs[0] = replace(self.bound_runs[0], raw=changed.raw)
                with self.assertRaisesRegex(assembly.AssemblyError, 'RUN_BINDING'):
                    assembly.assemble_dataset(self.provenance, runs)

    def test_readback_mutation_cannot_change_the_retained_run_or_provenance(self):
        value = self.bound_runs[0].value
        value['run']['samples'][5]['stop_receipt_ms'] = 999
        value['source_closure_sha256'] = '0' * 64
        retained = self.bound_runs[0].value
        self.assertEqual(retained['run'], self.template['runs'][0])
        self.assertEqual(retained['source_closure_sha256'], self.provenance['source_closure_sha256'])

    def test_rehashed_envelope_still_requires_exact_provenance_fields(self):
        for change, code in (
            (lambda value: value.pop('toolchain_sha256'), 'FIELDS'),
            (lambda value: value.update(toolchain_sha256='not-a-hash'), 'HASH'),
            (lambda value: value.update(unexpected=True), 'FIELDS')):
            with self.subTest(code=code):
                value = self.bound_runs[0].value
                change(value)
                runs = list(self.bound_runs)
                runs[0] = self.bind(value)
                with self.assertRaisesRegex(assembly.AssemblyError, code):
                    assembly.assemble_dataset(self.provenance, runs)


if __name__ == '__main__':
    unittest.main()
