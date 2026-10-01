"""Bounded offline reader for retained O7 probe03, outside formal closure.

Only production trim interval 1 gates the finite-workload comparison. The
interval 64 experiment is validated for coverage but never pooled into it.
Raw summaries are checked against raw arrays, never used as metric inputs.
The historical manifest omitted the probe and its imported p95 helper: current
inspection hashes are provenance for this analysis, not a historical closure.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import random
from statistics import mean, median

from studio.tests.replay.residency_metrics import need, number, p95
from studio.tests.replay.run_journal_microbench import source_closure

ROUNDS = 6
ORDER_SEED = 61001
BASELINE_INTERVAL = 1
INTERVALS = (1, 64)
SEEDS = ('early', 'late')
OPERATION_COUNTS = {'lookup_ms': 50, 'append_ms': 75}
# Inspected retained script, not a run-time capture of historical harness code.
INSPECTED_PROBE_SHA256 = '1e8cd1ab4d38351559afe3ed58b427c73bfea1c8f976e26d3b34c97449b31666'
SHARED_REQUIRED = {'host/core/journal.py', 'host/replay/verified_journal.py',
                   'host/replay/disk_journal_index.py'}


def stats(values):
    need(type(values) is list and values and all(number(v) for v in values), 'PROBE_TIMING_VALUES')
    return {'n': len(values), 'median_ms': median(values), 'p95_ms': p95(values),
            'min_ms': min(values), 'max_ms': max(values)}


def _matches_claim(claim, actual):
    need(type(claim) is dict and type(claim.get('n')) is int and claim['n'] == actual['n']
         and all(number(claim.get(name))
                 and math.isclose(claim[name], actual[name], rel_tol=1e-12, abs_tol=1e-12)
                 for name in ('median_ms', 'p95_ms')), 'PROBE_FORGED_STATS')


def expected_order():
    rng = random.Random(ORDER_SEED)
    result = []
    for round_id in range(ROUNDS):
        order = [(label, interval) for label in SEEDS for interval in INTERVALS]
        rng.shuffle(order)
        result.extend((round_id, label, interval) for label, interval in order)
    return result


def calculate_probe(probe):
    """Raw-array comparison only; returns no acceptance or metrics_pass verdict."""
    need(type(probe) is dict and probe.get('authority') == 0
         and type(probe.get('authority')) is int and probe.get('acceptance') is False,
         'PROBE_DIAGNOSTIC_SCOPE')
    blocks = probe.get('blocks')
    need(type(blocks) is list and len(blocks) == ROUNDS * len(SEEDS) * len(INTERVALS),
         'PROBE_ROUND_COVERAGE')
    seen = set()
    for block, expected in zip(blocks, expected_order()):
        need(type(block) is dict and type(block.get('round')) is int
             and type(block.get('interval')) is int and block.get('seed') in SEEDS,
             'PROBE_BLOCK_SHAPE')
        identity = (block['round'], block['seed'], block['interval'])
        need(identity not in seen, 'PROBE_DUPLICATE_BLOCK')
        seen.add(identity)
        need(identity == expected, 'PROBE_RANDOMIZED_ORDER')
        need(number(block.get('system_cpu_percent')) and block['system_cpu_percent'] <= 100,
             'PROBE_CPU')
        need(number(block.get('wall_seconds')) and block['wall_seconds'] > 0,
             'PROBE_WALL_WINDOW')
        for operation, count in OPERATION_COUNTS.items():
            values = block.get(operation)
            need(type(values) is list and len(values) == count, 'PROBE_OPERATION_COVERAGE')
            actual = stats(values)
            _matches_claim(block['metrics'][operation], actual)
    # Validate the retained experiment's summaries, but calculate the gate
    # directly from the baseline arrays below. No favorable subset is selected.
    summaries = probe.get('summary')
    need(type(summaries) is list and len(summaries) == 4, 'PROBE_SUMMARY_COVERAGE')
    summary_seen = set()
    for summary in summaries:
        need(type(summary) is dict and summary.get('seed') in SEEDS
             and type(summary.get('interval')) is int and summary['interval'] in INTERVALS,
             'PROBE_SUMMARY_COVERAGE')
        identity = (summary['seed'], summary['interval'])
        need(identity not in summary_seen, 'PROBE_SUMMARY_COVERAGE')
        summary_seen.add(identity)
        chosen = [b for b in blocks if (b['seed'], b['interval']) == identity]
        for operation in OPERATION_COUNTS:
            _matches_claim(summary['metrics'][operation],
                           stats([v for b in chosen for v in b[operation]]))
    chosen = [b for b in blocks if b['interval'] == BASELINE_INTERVAL]
    need(len(chosen) == 12 and all(sum(b['round'] == r and b['seed'] == s for b in chosen) == 1
                                  for r in range(ROUNDS) for s in SEEDS), 'PROBE_ROUND_COVERAGE')
    latency, checks = {}, {}
    for operation in OPERATION_COUNTS:
        by_seed = {s: stats([v for b in chosen if b['seed'] == s for v in b[operation]]) for s in SEEDS}
        small, large = by_seed['early']['median_ms'], by_seed['late']['median_ms']
        need(small > 0, 'PROBE_TIMING_BASELINE')
        name = operation.removesuffix('_ms')
        checks[name] = large <= 1.3 * small
        latency[name] = {**by_seed, 'large_over_small_median_percent': 100 * large / small,
                         'median_limit_percent': 130, 'p95_report_only': True}
    return {'baseline_interval': BASELINE_INTERVAL, 'excluded_experimental_interval': 64,
            'rounds': ROUNDS, 'order_seed': ORDER_SEED, 'baseline_blocks': len(chosen),
            'blocks_per_seed': ROUNDS, 'excluded_experimental_blocks': len(blocks) - len(chosen),
            'checks': checks, 'latency': latency,
            'baseline_block_observations': [
                {'round': b['round'], 'seed': b['seed'], 'interval': b['interval'],
                 'system_cpu_percent': b['system_cpu_percent'], 'wall_seconds': b['wall_seconds'],
                 'lookup': stats(b['lookup_ms']), 'append': stats(b['append_ms'])} for b in chosen],
            'mean_system_cpu_percent': {s: mean(b['system_cpu_percent'] for b in chosen if b['seed'] == s)
                                        for s in SEEDS},
            'scope': 'finite retained workload; no asymptotic complexity proof or per-variant memory proof'}


def _regular(path, cap):
    path = Path(path)
    for component in (path, *path.parents):
        info = component.lstat()
        need(not component.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'PROBE_REPARSE')
    need(path.is_file() and 0 < path.stat().st_size <= cap, 'PROBE_ARTIFACT_SIZE')
    return path


def _sha_file(path, cap=4 * 1024 * 1024):
    path = _regular(path, cap)
    size = path.stat().st_size
    digest, total = hashlib.sha256(), 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            total += len(chunk)
            need(total <= cap, 'PROBE_ARTIFACT_SIZE')
            digest.update(chunk)
    need(total == size == path.stat().st_size, 'PROBE_ARTIFACT_CHANGED')
    return {'sha256': digest.hexdigest(), 'size_bytes': size}


def _json(path, cap):
    path = _regular(path, cap)
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    need(len(raw) <= cap, 'PROBE_ARTIFACT_SIZE')
    return json.loads(raw), {'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}


def _manifest(value):
    need(type(value) is dict and 0 < len(value) <= 512, 'PROBE_SOURCE_MANIFEST')
    seen = set()
    for name, digest in value.items():
        need(type(name) is str and name and '\\' not in name and ':' not in name
             and not PurePosixPath(name).is_absolute()
             and all(part not in ('', '.', '..') for part in name.split('/'))
             and name.casefold() not in seen, 'PROBE_SOURCE_PATH')
        seen.add(name.casefold())
        need(type(digest) is str and len(digest) == 64
             and all(c in '0123456789abcdef' for c in digest), 'PROBE_SOURCE_HASH')
    return value


def bind_seed_prefixes(seed_root, soak_root, seeds):
    """Bind original seeds to batch 4/34 journal prefixes, not caller hashes alone."""
    journal = _regular(soak_root / 'commands/commands.jsonl', 64 * 1024 * 1024)
    binding = _sha_file(journal, 64 * 1024 * 1024)
    summaries = {}
    for label, index in (('early', 4), ('late', 34)):
        summary, summary_binding = _json(soak_root / f'summary-{index:02d}.json', 65536)
        expected = summary.get('journal_bytes')
        need(type(expected) is int and expected > 0
             and expected == seeds[label]['size_bytes'] <= binding['size_bytes'],
             'PROBE_SEED_BATCH_SIZE')
        count, total, digest = 0, 0, hashlib.sha256()
        with journal.open('rb') as source, (seed_root / (label + '.jsonl')).open('rb') as stream:
            while line := stream.readline(1024 * 1024 + 1):
                need(len(line) <= 1024 * 1024 and line.endswith(b'\n'), 'PROBE_SEED_RECORD')
                total += len(line)
                count += 1
                need(total <= expected and count <= 100000, 'PROBE_SEED_RECORD')
                need(type(json.loads(line)) is dict, 'PROBE_SEED_RECORD')
                need(source.read(len(line)) == line, 'PROBE_SEED_PREFIX')
                digest.update(line)
        need(total == expected and digest.hexdigest() == seeds[label]['sha256'],
             'PROBE_SEED_CHANGED')
        seeds[label]['record_count'] = count
        summaries[label] = summary_binding
    need(seeds['early']['record_count'] > 0 and
         seeds['late']['record_count'] >= 5 * seeds['early']['record_count'],
         'PROBE_SEED_RECORD_RATIO')
    need(_sha_file(journal, 64 * 1024 * 1024) == binding, 'PROBE_JOURNAL_CHANGED')
    return {'journal': binding, 'batch_summaries': summaries, 'prefixes_match': True}


def _current_manifest(source_root, files):
    root = source_root.resolve(strict=True)
    for name, expected in _manifest(files).items():
        path = root / name
        need(path.resolve(strict=True).is_relative_to(root), 'PROBE_SOURCE_PATH')
        need(_sha_file(path)['sha256'] == expected, 'PROBE_SOURCE_CHANGED')


def current_probe_sources(source_root):
    """Same conservative imported file set as run_journal_microbench.source_files."""
    paths = {source_root / 'tests/replay/run_journal_microbench.py',
             source_root / 'tests/replay/benchmark_profile.py'}
    for relative in ('host/core', 'host/replay', 'protocol'):
        root = source_root / relative
        need(root.is_dir(), 'PROBE_SOURCE_MANIFEST')
        paths.update(path for path in root.rglob('*.py') if path.is_file())
    return {path.relative_to(source_root).as_posix(): _sha_file(path)['sha256']
            for path in sorted(paths)}


def read_bound_probe(probe_path, seed_root, *, source_root, soak_root):
    """Validate retained raw inputs/current graph, then calculate baseline stats."""
    probe, raw_binding = _json(probe_path, 2 * 1024 * 1024)
    result = calculate_probe(probe)
    code_binding = _sha_file(probe_path.parent / 'probe.py', 64 * 1024)
    need(code_binding['sha256'] == INSPECTED_PROBE_SHA256, 'PROBE_INSPECTED_CODE_CHANGED')
    need(probe.get('source_after_equal') is True and probe.get('seed_unchanged') is True,
         'PROBE_UNCHANGED_FLAGS')
    files = _manifest(probe['source_before'])
    need(source_closure(files) == probe.get('source_closure'), 'PROBE_SOURCE_CLOSURE')
    _current_manifest(source_root, files)
    need(files == current_probe_sources(source_root), 'PROBE_SOURCE_COVERAGE')
    need(type(probe.get('seed_hashes')) is dict and set(probe['seed_hashes']) == set(SEEDS),
         'PROBE_SEED_BINDING')
    seeds = {s: _sha_file(seed_root / (s + '.jsonl'), 64 * 1024 * 1024) for s in SEEDS}
    need(all(seeds[s]['sha256'] == probe['seed_hashes'][s] for s in SEEDS), 'PROBE_SEED_HASH')
    need(seeds['late']['size_bytes'] >= 5 * seeds['early']['size_bytes'], 'PROBE_SEED_SIZE_RATIO')
    seed_binding = bind_seed_prefixes(seed_root, soak_root, seeds)
    soak_sources, soak_source_binding = _json(soak_root / 'source-files.json', 256 * 1024)
    soak_result, soak_result_binding = _json(soak_root / 'result.json', 2 * 1024 * 1024)
    soak_sources = _manifest(soak_sources)
    _current_manifest(source_root, soak_sources)
    need(soak_result.get('run_id') == soak_root.name and soak_result.get('completed') is True
         and soak_result.get('source_unchanged') is True
         and soak_result.get('formal_acceptance') is False
         and soak_result.get('source_closure_sha256') == source_closure(soak_sources),
         'SOAK_SOURCE_BINDING')
    shared = set(files) & set(soak_sources)
    need(SHARED_REQUIRED <= shared and all(files[n] == soak_sources[n] for n in shared),
         'PROBE_SOAK_SOURCE_MISMATCH')
    result['evidence_binding'] = {
        'analysed_at_utc': datetime.now(timezone.utc).isoformat(),
        'probe_result': raw_binding, 'inspected_retained_probe_code': code_binding,
        'original_seeds': seeds,
        'seed_soak_binding': seed_binding,
        'large_over_small_seed_size_ratio': seeds['late']['size_bytes'] / seeds['early']['size_bytes'],
        'probe_imported_source_files': len(files), 'probe_imported_source_closure': source_closure(files),
        'soak_source_files': len(soak_sources), 'soak_source_closure': source_closure(soak_sources),
        'soak_source_manifest': soak_source_binding, 'soak_result': soak_result_binding,
        'shared_source_files': len(shared), 'shared_source_hashes': {n: files[n] for n in sorted(shared)},
        'current_source_graph_consistent': True, 'historical_harness_closure_complete': False,
        'historical_harness_omissions': ['probe.py', 'tests/replay/residency_metrics.py'],
        'current_offline_verifier_files': {
            'tests/replay/journal_scaling_metrics.py': _sha_file(Path(__file__)),
            'tests/replay/residency_metrics.py': _sha_file(Path(__file__).with_name('residency_metrics.py'))},
        'scope': 'current/retained inspection hashes; historical complete harness binding is unproven'}
    return result
