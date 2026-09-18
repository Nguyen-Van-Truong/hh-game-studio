"""Offline S95 selected-identity analysis. No processes, runtime imports or writes.

Only the fixed terminal isolation-01 artifacts are accepted. The operator must
first establish that every writer has stopped; this program cannot establish it.
Reader/strict JSON/hash primitives are reused from the read-only S83 analyzer.
Delta reconstruction follows S84; the different S95 schema is checked here.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
RUN = 'gt06-s95-native-isolation-01'
OUT = 'project/benchmark/out/'
HELPER_DIR = 'zdoc/reviews/20260918-gt06-s95-native-isolation/'
S83 = ROOT / 'zdoc/reviews/20260918-gt06-s83-analyzer/analyze_attribution.py'
S83_SHA = 'da8ecb76ff4871e7ecb827bfb57bfa61319748009bfde17f3da7e4da2c461903'
SOURCE = 'ebed9418490379bb902d2049e4a2f98a96e3378d09b369aef02684e16214c74e'
HELPER = '4448ab35a6e087c8756063e0d8a025f4dc60a44329fcf56c4b270e6d1474302b'
PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
DIMENSIONS = {'batches': 35, 'cycles': 100, 'launch_editor': True, 'wall_seconds': 1800}
FALSE_FLAGS = ('formal_acceptance', 'full_benchmark', 'eligible_for_dataset')
LIMITS = [
    'Only reachable Tree owners, their TreeItems and reachable Node3D-family IDs are inventoried; this is not a full ObjectDB census.',
    'Growth membership is reconstructed from the published baseline and delta, not independently checked against a second full ID list.',
    'Node3D-family membership does not identify concrete subclasses, object content, allocation stacks or ownership lifetimes.',
    'Runtime still-valid flags are reported observations; removal from this inventory does not by itself establish destruction or a leak.',
    'Only batch 4 and the first later object-count increase have identity snapshots. No second snapshot means later identity stability was not measured.',
    'No HTTP producer, host-start/ACK work, coupled idle durations or post-ACK observation is reproduced here.',
    'No-growth means not reproduced in this isolated workload; it does not rule out a leak, repair a coupled failure or satisfy a formal memory gate.',
    'Process/cleanup receipts are preserved, not reverified through OS handles. Task Scheduler must separately capture the outer observer exit.',
]


def primitives():
    import hashlib
    if hashlib.sha256(S83.read_bytes()).hexdigest() != S83_SHA:
        raise ValueError('S83_READER_SOURCE_PIN')
    spec = importlib.util.spec_from_file_location('_s95_s83_readonly', S83)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = primitives()
need, digest = p.require, p.digest


def integer(value, label, minimum=0):
    need(type(value) is int and value >= minimum, label + ': exact integer required')
    return value


def identity(value):
    need(type(value) is int and value != 0 and -(2**63) <= value < 2**63,
         'ObjectID must be a nonzero exact signed-int64 JSON integer')
    return value


def owner_id(value):
    need(p.instance_id(value), 'Tree owner key must be canonical signed-int64 text')
    return int(value)


def ids(value):
    need(type(value) is list, 'ID array required')
    result = [identity(item) for item in value]
    need(result == sorted(set(result)), 'IDs must be sorted and unique')
    return set(result)


def emit_ids(value):
    # Keep exact IDs safe for downstream JavaScript/JSON consumers too.
    return [str(item) for item in sorted(value)]


def flags(row):
    need(row['run_id'] == RUN and all(row[key] is False for key in FALSE_FLAGS), 'diagnostic-only flags/run')


class Evidence:
    def __init__(self):
        self.reader = p.Reader(ROOT / 'studio/.local/reviews' / RUN)
        self.outer = p.Reader(ROOT / 'studio/.local/reviews' / (RUN + '-outer'))
        # Both terminal publications are required, even when reporting failure.
        self.terminal = self.outer.json('terminal.json')
        self.manifest = self.reader.json('output-manifest.json')
        flags(self.terminal)
        flags(self.manifest)
        need(self.manifest['source_closure_sha256'] == SOURCE
             and self.manifest['helper_closure_sha256'] == HELPER, 'terminal source/helper pin')
        self.artifacts = self.manifest['artifacts']
        need(type(self.artifacts) is dict, 'artifact manifest map')

    def read(self, name):
        need(name in self.artifacts, 'unsealed or missing artifact: ' + name)
        raw = self.reader.raw(name)
        need(len(raw) <= 8 * 1024**2 and self.artifacts[name] == {
            'sha256': digest(raw), 'size_bytes': len(raw)}, 'artifact hash/size mismatch: ' + name)
        return p.decode(raw)

    def optional(self, name):
        need((name in self.artifacts) == self.reader.exists(name), 'manifest/publication set mismatch: ' + name)
        return self.read(name) if name in self.artifacts else None


def source_binding(e):
    meta = e.read('diagnostic.json')
    flags(meta)
    pins = meta['pins']
    need(meta['schema'] == 'HH-GT06-S95-NATIVE-ISOLATION-1' and meta['mode'] == 'isolation'
         and meta['dimensions'] == DIMENSIONS and meta['analytical_baseline_batch_index'] == 4
         and meta['no_http_producer'] is True and meta['native_warmup_field_remains_false'] is True
         and meta['host_integrated'] is False, 'native diagnostic metadata')
    helper_map = pins['helper_files']
    need(pins['source_closure_sha256'] == p.closure(pins['source_files']) == SOURCE
         and pins['profile_sha256'] == PROFILE
         and pins['helper_closure_sha256'] == digest(json.dumps(helper_map, sort_keys=True,
             separators=(',', ':'), allow_nan=False).encode()) == HELPER
         and set(helper_map) == {'native_isolation.py', 'object_probe_s95.gd'}, 'source/helper map binding')
    # Hash just the two archived helpers and one effective overlay, not the full source tree.
    for name, expected in helper_map.items():
        need(digest(e.reader.raw('source/' + HELPER_DIR + name)) == expected, 'archived helper bytes: ' + name)
    overlay = e.read('native-overlay.json')
    frozen = e.read('editor-snapshot.json')
    effective = digest(e.reader.raw('source/effective-benchmark_native.gd'))
    need(overlay['base_sha256'] == pins['source_files']['tests/replay/benchmark_native.gd']
         and overlay['effective_sha256'] == effective == frozen['addons/hh_benchmark/benchmark_native.gd']
         and overlay['helper_sha256'] == helper_map['object_probe_s95.gd']
         and overlay['dimensions'] == DIMENSIONS and overlay['original_runtime_source_edited'] is False
         and overlay['formal_thresholds_modified'] is False, 'effective overlay binding')
    request = e.outer.json('request-copy.json')
    need(request['run_id'] == RUN and request['native_pins'] == pins
         and request['source_sha256'] == SOURCE and request['helper_sha256'] == HELPER,
         'outer request source/helper binding')
    return {'source_closure_sha256': SOURCE, 'helper_closure_sha256': HELPER,
            'profile_sha256': PROFILE, 'effective_driver_sha256': effective,
            'source_map_digest_checked': True, 'complete_archived_source_bytes_rehashed': False}


def batches(e):
    result = []
    missing = False
    expected_names = {OUT + f'batch-{number:02d}.json' for number in range(35)}
    expected_names |= {OUT + f'{kind}-{number:02d}.json'
                       for number in range(2) for kind in ('sparse', 'sparse-post')}
    expected_names.add(OUT + 'index.json')
    need(all(name in expected_names for name in e.artifacts if name.startswith(OUT)), 'unexpected native output artifact')
    for number in range(35):
        row = e.optional(OUT + f'batch-{number:02d}.json')
        if row is None:
            missing = True
            continue
        need(not missing, 'noncontiguous native batch prefix')
        need(row['schema_id'] == 'hh-studio.native-cycle-batch' and row['schema_version'] == '1.2.0'
             and row['run_id'] == RUN and row['index'] == number and row['mode'] == 'diagnostic'
             and row['warmup'] is False and row['barrier'] == {'mode': 'diagnostic_none', 'required': False}
             and row['start_permit'] is None and len(row['cycles']) == len(row['raw_timings']) == 100,
             'batch run/dimensions/diagnostic binding')
        integer(row['pid'], 'native PID', 1)
        start, end = integer(row['started_mono_us'], 'batch start'), integer(row['ended_mono_us'], 'batch end')
        memory = row['memory']
        need(start <= end and memory['phase'] == 'post_batch_quiescent' and memory['monotonic_us'] == end
             and memory['settle_frames'] >= 4 and memory['settle_us'] >= 1_100_000, 'native readback phase')
        integer(memory['process_frame'], 'native frame')
        if result:
            need(row['pid'] == result[0]['pid'] and result[-1]['ended_mono_us'] <= start, 'batch PID/time chain')
        for name in ('objects', 'resources'):
            integer(memory['editor'][name]['value'], name)
            need(memory['editor'][name]['unavailable_reason'] is None, 'native counter unavailable')
        result.append(row)
    index = e.optional(OUT + 'index.json')
    if index is not None:
        need(len(result) == 35 and index['schema_id'] == 'hh-studio.native-cycle-benchmark'
             and index['schema_version'] == '1.3.0' and index['completed'] is True
             and index['benchmark_complete'] is False and index['formal_acceptance'] is False
             and index['host_integrated'] is False and index['pid'] == result[0]['pid']
             and index['cycles_per_batch'] == 100 and index['batches_completed'] == 35
             and index['host_barriers'] == index['start_permits'] == []
             and index['batch_order'] == 'diagnostic_native_cycle_only', 'native terminal index')
        need(index['input'] == {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
            'run_id': RUN, 'mode': 'diagnostic', 'source_closure_sha256': SOURCE, 'profile_sha256': PROFILE,
            'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}, 'index input/source binding')
        expected = []
        for number in range(35):
            name = f'batch-{number:02d}.json'
            ref = e.reader.ref(OUT + name)
            expected.append({**ref, 'file': name, 'index': number})
        need(index['batches'] == expected, 'index batch hash/size references')
    return result, index


def snapshot(e, number, rows):
    name = OUT + f'sparse-{number:02d}.json'
    row = e.optional(name)
    post = e.optional(OUT + f'sparse-post-{number:02d}.json')
    need((row is None) == (post is None), 'unpaired sparse publication')
    if row is None:
        return None
    batch = integer(row['batch'], 'snapshot batch', 4)
    need(batch < len(rows), 'snapshot missing matching native readback')
    native, memory = rows[batch], rows[batch]['memory']
    need(row['schema_id'] == 'hh-studio.gt06.s95-sparse-attribution' and row['schema_version'] == '1.0.0'
         and row['run_id'] == RUN and row['pid'] == native['pid'] and row['sequence'] == number
         and row['phase'] == 'before_batch_counter_readback', 'snapshot identity/phase')
    need(row['partial_inventory'] is True and row['complete_within_target_scope'] is True
         and row['formal_acceptance'] is False and row['eligible_for_dataset'] is False
         and row['object_references_retained'] is False and row['user_content_collected'] is False
         and row['id_cap'] == 32768 and row['snapshot_cap'] == 2
         and row['target_scope'] == 'reachable_Tree_owned_TreeItems_and_reachable_Node3D_family', 'snapshot scope')
    need(post['schema_id'] == 'hh-studio.gt06.s95-sparse-post' and post['schema_version'] == '1.0.0'
         and post['run_id'] == RUN and post['batch'] == batch and post['sequence'] == number
         and post['snapshot_sha256'] == digest(e.reader.raw(name))
         and post['formal_acceptance'] is False and post['eligible_for_dataset'] is False, 'snapshot publication hash/binding')
    before = row['before']
    need(set(before) == {'objects', 'resources', 'nodes', 'orphan_nodes'}, 'sparse counter keys')
    for key, value in before.items():
        integer(value, key)
    need(before == row['after_collection'] == post['before'] == post['after_publication']
         and row['counter_self_drift'] is False and post['counter_self_drift'] is False, 'sparse collection/publication drift')
    need(all(before[key] == memory['editor'][key]['value'] for key in ('objects', 'resources')),
         'sparse/native same-phase counter mismatch')
    start, end = integer(row['started_mono_us'], 'collection start'), integer(row['collected_mono_us'], 'collection end')
    duration = integer(post['through_snapshot_publication_elapsed_us'], 'publication duration')
    need(native['started_mono_us'] <= start <= end <= start + duration <= native['ended_mono_us']
         and row['collection_elapsed_us'] == end - start and row['process_frame'] == memory['process_frame'],
         'sparse/native synchronous frame/time binding')
    return row


def inventory(trees, nodes, row):
    owners = set(trees)
    items = set()
    for members in trees.values():
        need(not items & members, 'TreeItem assigned to multiple Tree owners')
        items |= members
    need(not (owners & items or owners & nodes or items & nodes), 'selected identity class/family collision')
    counts = {'Tree': len(owners), 'TreeItem': len(items), 'Node3D_family': len(nodes)}
    for key in ('tree_count', 'tree_item_count', 'node3d_count', 'target_id_count'):
        integer(row[key], key)
    need(row['tree_count'] == counts['Tree'] and row['tree_item_count'] == counts['TreeItem']
         and row['node3d_count'] == counts['Node3D_family'] and row['target_id_count'] == sum(counts.values())
         and sum(counts.values()) <= min(32768, row['before']['objects']), 'selected inventory counts')
    return {'trees': trees, 'nodes': nodes, 'items': items, 'counts': counts}


def baseline(row):
    need(row['batch'] == 4 and row['trigger'] == 'baseline_batch4'
         and row['baseline_objects'] == row['before']['objects'] and row['object_delta_from_baseline'] == 0
         and row['delta'] == {}, 'baseline trigger/count')
    raw = row['baseline_primitive_inventory']
    need(raw['complete'] is True and raw['id_count'] == row['target_id_count']
         and raw['tree_item_count'] == row['tree_item_count'], 'baseline primitive completeness/count')
    return inventory({owner_id(key): ids(value) for key, value in raw['trees'].items()}, ids(raw['node3d_ids']), row)


def delta_ids(previous, delta):
    added, removed, valid = (ids(delta[key]) for key in ('added', 'removed', 'removed_still_valid'))
    need(not added & previous and removed <= previous and not added & removed and valid <= removed
         and type(delta['net_count']) is int and delta['net_count'] == len(added) - len(removed), 'identity delta arithmetic')
    return (previous - removed) | added


def changes(old, new):
    return {'added': emit_ids(new - old), 'removed': emit_ids(old - new), 'net_count': len(new) - len(old)}


def growth(before, old, row):
    need(row['batch'] > 4 and row['trigger'] == 'first_prepublication_object_growth'
         and row['baseline_objects'] == before['before']['objects']
         and row['object_delta_from_baseline'] == row['before']['objects'] - row['baseline_objects'] > 0
         and row['baseline_primitive_inventory'] == {}, 'growth trigger/count')
    delta = row['delta']
    trees, owners = dict(old['trees']), []
    for key, change in delta['trees'].items():
        owner = owner_id(key)
        need(type(change['tree_exists_now']) is bool and type(change['tree_still_valid']) is bool
             and change['tree_existed_before'] is (owner in old['trees']), 'Tree owner existence flags')
        prior = old['trees'].get(owner, set())
        now = delta_ids(prior, change)
        need(change['added'] or change['removed'] or change['tree_existed_before'] != change['tree_exists_now'],
             'empty unchanged Tree delta')
        if change['tree_exists_now']:
            need(change['tree_still_valid'] is True, 'reachable Tree reported invalid')
            trees[owner] = now
        else:
            need(not now and owner in trees, 'removed Tree still owns inventoried items')
            del trees[owner]
        owners.append({'tree_id': str(owner), **changes(prior, now),
                       'tree_existed_before': change['tree_existed_before'], 'tree_exists_now': change['tree_exists_now'],
                       'runtime_tree_still_valid': change['tree_still_valid'],
                       'runtime_removed_items_still_valid': emit_ids(ids(change['removed_still_valid']))})
    current = inventory(trees, delta_ids(old['nodes'], delta['node3d_ids']), row)
    need(not (set(old['trees']) & (current['items'] | current['nodes'])
              or old['items'] & (set(trees) | current['nodes'])
              or old['nodes'] & (set(trees) | current['items'])), 'same exact ID changed class/family')
    net = row['target_id_count'] - before['target_id_count']
    need(type(delta['target_net_count']) is int and delta['target_net_count'] == net, 'selected target net delta')
    old_owner = {item: owner for owner, members in old['trees'].items() for item in members}
    new_owner = {item: owner for owner, members in trees.items() for item in members}
    moves = [{'id': str(item), 'from_tree': str(old_owner[item]), 'to_tree': str(new_owner[item])}
             for item in sorted(old['items'] & current['items']) if old_owner[item] != new_owner[item]]
    return {'batch': row['batch'], 'objectdb_count_delta': row['object_delta_from_baseline'],
            'selected_id_net': net, 'unattributed_net_count_delta': row['object_delta_from_baseline'] - net,
            'class_or_family': {'Tree': changes(set(old['trees']), set(trees)),
                'TreeItem': changes(old['items'], current['items']), 'Node3D_family': changes(old['nodes'], current['nodes'])},
            'tree_owner_deltas': sorted(owners, key=lambda item: int(item['tree_id'])), 'TreeItem_owner_moves': moves,
            'runtime_removed_node3d_ids_still_valid': emit_ids(ids(delta['node3d_ids']['removed_still_valid'])),
            'reconstructed_class_or_family_counts': current['counts'], 'independent_second_full_id_list': False}


def analyze():
    e = Evidence()
    binding = source_binding(e)
    supervisor, child = e.read('supervisor-result.json'), e.optional('child-result.json')
    flags(supervisor)
    if child is not None:
        flags(child)
    rows, index = batches(e)
    receipts = {'outer_terminal': e.terminal, 'native_supervisor': supervisor,
                'child_completed_diagnostic': child.get('completed_diagnostic') if child else None,
                'child_error': child.get('error') if child else None}
    captures = {}
    for lane in ('import-host', 'editor-host', 'host-owner'):
        capture = e.optional(lane + '/capture.json')
        captures[lane] = None if capture is None else {key: capture.get(key) for key in
            ('actual_process_exit', 'wrapper_exit_code', 'job', 'wrapper_process_handle')}
    receipts['captures'] = captures
    completed = (index is not None and child is not None and child['completed_diagnostic'] is True
                 and supervisor['completed_diagnostic'] is True and e.terminal['completed_diagnostic'] is True)
    if completed:
        need(e.manifest['outcome'] == 'DIAGNOSTIC_COMPLETE' and child['native_batches'] == 35
             and child['native_cycles'] == 3500, 'completed diagnostic dimensions/outcome')
        for lane in captures:
            need(captures[lane] is not None and captures[lane]['actual_process_exit']['exit_code'] == 0
                 and captures[lane]['wrapper_exit_code'] == 0, 'completed diagnostic missing/nonzero captured exit')
        need(captures['editor-host']['actual_process_exit']['pid'] == rows[0]['pid']
             and child['editor_actual_exit'] == captures['editor-host']['actual_process_exit']
             and child['import_actual_exit'] == captures['import-host']['actual_process_exit']
             and supervisor['child_actual_exit'] == captures['host-owner']['actual_process_exit'], 'captured exit/PID binding')
    counts = [{'batch': row['index'], **{key: row['memory']['editor'][key]['value'] for key in ('objects', 'resources')},
               'duration_seconds': (row['ended_mono_us'] - row['started_mono_us']) / 1_000_000} for row in rows]
    first, second = snapshot(e, 0, rows), snapshot(e, 1, rows)
    need(first is not None or (len(rows) < 5 and second is None), 'missing batch-4 baseline')
    analysis = None
    if first is not None:
        initial = baseline(first)
        growth_batches = [row['batch'] for row in counts[5:] if row['objects'] > counts[4]['objects']]
        need((second is None and not growth_batches) or
             (second is not None and growth_batches and second['batch'] == growth_batches[0]), 'first count-growth capture')
        analysis = {'baseline_batch': 4, 'baseline_counts': first['before'], 'baseline_selected_counts': initial['counts'],
                    'baseline_selected_id_count': first['target_id_count'],
                    'baseline_uninventoried_object_count': first['before']['objects'] - first['target_id_count'],
                    'object_growth_batches': growth_batches, 'baseline_ids_are_not_growth': True,
                    'identity_comparison_scope': 'baseline_to_first_growth_only' if second else 'baseline_only',
                    'all_later_identity_stability_measured': False,
                    'growth': growth(first, initial, second) if second is not None else None}
    interpretation = ('GROWTH_OBSERVED_IN_ISOLATED_WORKLOAD' if second is not None else
                      'NOT_REPRODUCED_IN_COMPLETED_ISOLATED_WORKLOAD' if completed else
                      'INCOMPLETE_DIAGNOSTIC_NO_ABSENCE_CONCLUSION')
    return {'schema': 'HH-GT06-S95-SELECTED-IDENTITY-ANALYSIS-1', 'authority': 0, 'run_id': RUN,
            **dict.fromkeys(FALSE_FLAGS, False), 'no_leak_claim': False, 'full_objectdb_inventory': False,
            'writers_stopped': 'operator_assertion_only', 'interpretation': interpretation,
            'completed_diagnostic_receipts_present': completed, 'native_batches_observed': len(rows),
            'source_binding': binding, 'batch_counts': counts, 'selected_identity_analysis': analysis,
            'native_heartbeat': None if index is None else {key: index[key] for key in ('max_status_gap_ms', 'heartbeat_target_met')},
            'native_elapsed_seconds': child.get('native_elapsed_seconds') if child else None,
            'child_wall_seconds': child.get('wall_seconds') if child else None,
            'execution_receipts': receipts, 'process_lifecycle_independently_verified': False,
            'outer_observer_actual_exit_verified': False, 'limitations': LIMITS,
            'inputs': [e.reader.ref(name) for name in sorted(e.reader.cache)],
            'outer_inputs': [e.outer.ref(name) for name in sorted(e.outer.cache)],
            'reader_sha256': S83_SHA, 'analyzer_sha256': digest(Path(__file__).read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--writers-stopped', action='store_true', required=True,
                        help='Operator has confirmed terminal state and that all evidence writers stopped.')
    parser.parse_args()
    try:
        result = analyze()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'authority': 0, 'formal_acceptance': False, 'run_id': RUN,
            'interpretation': 'ANALYSIS_GAP', 'error_type': type(error).__name__, 'error': str(error),
            'no_leak_claim': False, 'limitations': LIMITS}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result['completed_diagnostic_receipts_present'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
