"""Owned no-engine S114 attribution on an exact copy of S110 durable history.

--check never starts a host. --launch refuses an existing run directory.
Runtime files are copied byte exactly; supplemental subclasses seed the history,
use a fresh fixture project, and measure original calls without replacing them.
Thread CPU and wall time are observations, not a disk/scheduler attribution.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from unittest.mock import patch

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN_ID = 'gt06-s114-history-01'
CLOSURE = '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467'
HISTORY_HASH = '8bc2e17e06b11051cb2cba9f5110c6afb268bce87c6be990c0c20b80506ce4f7'
HISTORY_SIZE = 5797257
HISTORY_LINES = 8292
CHILD_SECONDS = 210
OUTER_SECONDS = 240


def support(path):
    spec = importlib.util.spec_from_file_location('s114_support', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Timings:
    """Bounded fixed-label aggregates and three slowest original calls per label."""
    def __init__(self):
        self.local = threading.local()
        self.lock = threading.Lock()
        self.phase = 'initialize'
        self.rows = {}

    def call(self, label, function, *args, **kwargs):
        start, cpu = time.perf_counter_ns(), time.thread_time_ns()
        previous = getattr(self.local, 'scope', 'none')
        self.local.scope = label
        try:
            return function(*args, **kwargs)
        finally:
            end, cpu_end = time.perf_counter_ns(), time.thread_time_ns()
            self.local.scope = previous
            row = {'start_ns': start, 'end_ns': end, 'thread_id': threading.get_native_id(),
                   'wall_ms': (end - start) / 1e6, 'thread_cpu_ms': (cpu_end - cpu) / 1e6,
                   'enclosing_scope': previous}
            key = self.phase + '.' + label
            with self.lock:
                if len(self.rows) >= 64 and key not in self.rows:
                    raise RuntimeError('ATTRIBUTION_LABEL_BOUND')
                item = self.rows.setdefault(key, {'count': 0, 'wall_sum_ms': 0.0,
                    'cpu_sum_ms': 0.0, 'wall_max_ms': 0.0, 'slowest': []})
                item['count'] += 1
                item['wall_sum_ms'] += row['wall_ms']
                item['cpu_sum_ms'] += row['thread_cpu_ms']
                item['wall_max_ms'] = max(item['wall_max_ms'], row['wall_ms'])
                item['slowest'] = sorted(item['slowest'] + [row],
                    key=lambda value: value['wall_ms'], reverse=True)[:3]


def check():
    helper = ROOT / 'zdoc/reviews/20260919-gt06-s102-observability/preflight.py'
    util = support(helper)
    campaign, _, _, sources = util.load_campaign(ROOT)
    util.need(campaign.closure(sources) == CLOSURE, 'S114_SOURCE_DRIFT')
    history = ROOT / 'studio/.local/reviews/gt06-s110-formal-01/run-00-attempt-01/commands/commands.jsonl'
    raw = history.read_bytes()
    util.need(len(raw) == HISTORY_SIZE and raw.count(b'\n') == HISTORY_LINES
              and hashlib.sha256(raw).hexdigest() == HISTORY_HASH, 'S114_HISTORY_DRIFT')
    util.need(campaign.commands.GROUPS == 100 if hasattr(campaign, 'commands') else True,
              'S114_WORKLOAD')
    return util, campaign, sources, history, helper


def launch():
    util, campaign, sources, history, helper = check()
    run = BASE / 'run-01'
    run.mkdir(exist_ok=False)
    frozen = {}
    for name, digest in sources.items():
        target = run / 'source/studio' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'studio' / name, target)
        util.need(util.sha(target) == digest, 'S114_FREEZE_COPY')
        frozen['source/studio/' + name] = digest
    for name, path in (('history_replay.py', Path(__file__)), ('support.py', helper),
                       ('history-seed.jsonl', history)):
        shutil.copyfile(path, run / name)
        frozen[name] = util.sha(run / name)
    freeze = {'schema': 's114.history-replay.freeze.1', 'run_id': RUN_ID,
        'started_utc': datetime.now(timezone.utc).isoformat(), 'source_files': sources,
        'source_closure': CLOSURE, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'execution_files': frozen, 'history_hash': HISTORY_HASH, 'history_size': HISTORY_SIZE,
        'history_lines': HISTORY_LINES, 'python_sha256': util.sha(Path(sys.executable)),
        'formal_acceptance': False, 'eligible_for_dataset': False, 'engine_runs': 0,
        'child_seconds': CHILD_SECONDS, 'outer_seconds': OUTER_SECONDS,
        'differences': ['Seed final S110 history, not a reproduction of its exact batch5 interleaving',
            'Fresh distinct fixture project/revision0 and new command IDs; old leases/effects not restored',
            'One complete original HTTP batch plus Cancel; no Godot/native/ACK workload',
            'Bounded supplemental timing wrappers add overhead; do not subtract it']}
    util.write(run / 'freeze.json', freeze)
    execution = {**frozen, 'freeze.json': util.sha(run / 'freeze.json')}
    util.write(run / 'execution-source-files.json', execution)
    owner, capture, errors = None, None, []
    started = time.monotonic()
    try:
        owner = campaign.BenchmarkProcess([sys.executable, '-B', str(run / 'history_replay.py'),
            '--child', str(run)], cwd=run, output=run / 'owned', source_root=run,
            source_files=execution, binary_sha256=freeze['python_sha256'], campaign_host=True)
        while owner.tick() is None:
            util.need(time.monotonic() - started < OUTER_SECONDS, 'S114_OUTER_LIMIT')
            time.sleep(.05)
        capture = owner.finish()
        campaign.verify_capture(run / 'owned', util.sha(run / 'owned/capture.json'),
            source_root=run, expected_source_files=execution,
            expected_binary_sha256=freeze['python_sha256'], expected_campaign_host=True)
        child_report = json.loads((run / 'child-report.json').read_bytes())
        util.need(child_report['completed'] and not child_report['errors'], 'S114_CHILD_INCOMPLETE')
        util.need(child_report['pid'] == capture['actual_process_exit']['pid'], 'S114_HOST_IDENTITY')
    except BaseException as error:
        errors.append(('parent', error))
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(('owner_close', error))
        observations = {}
        for name, getter in (
            ('owner', lambda: campaign._editor_cleanup_state(owner)),
            ('target', lambda: campaign._target_exit_state(run, 'owned')),
            ('source_unchanged', lambda: campaign.source_files() == sources),
            ('execution_unchanged', lambda: all(util.sha(run / p) == h for p, h in execution.items())),
            ('original_history_unchanged', lambda: util.sha(history) == HISTORY_HASH),
        ):
            try:
                observations[name] = getter()
            except BaseException as error:
                errors.append((name, error))
                observations[name] = None
        for name in ('source_unchanged', 'execution_unchanged', 'original_history_unchanged'):
            if observations.get(name) is not True:
                errors.append((name, RuntimeError('S114_PIN_CHANGED')))
        result = {'schema': 's114.history-replay.result.1', 'run_id': RUN_ID,
            'completed': capture is not None and not errors, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'engine_runs': 0,
            'ended_utc': datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds': time.monotonic() - started, 'observations': observations,
            'errors': util.errors_record(errors), 'execution_map_sha256': util.sha(run / 'execution-source-files.json'),
            'child_report_sha256': util.sha(run / 'child-report.json') if (run / 'child-report.json').exists() else None}
        util.write(run / 'result.json', result)
    print(json.dumps({'completed': result['completed'], 'elapsed_seconds': result['elapsed_seconds'],
                      'result': str(run / 'result.json')}), flush=True)
    return 0 if result['completed'] else 1


def child(run):
    run = Path(run).resolve()
    util = support(run / 'support.py')
    freeze = json.loads((run / 'freeze.json').read_bytes())
    util.need(Path(__file__).resolve() == run / 'history_replay.py', 'S114_COPIED_CHILD_REQUIRED')
    util.need(all(util.sha(run / p) == h for p, h in freeze['execution_files'].items()), 'S114_EXECUTION_DRIFT')
    campaign, _, _, sources = util.load_campaign(run / 'source')
    util.need(sources == freeze['source_files'] and campaign.closure(sources) == CLOSURE, 'S114_SOURCE_DRIFT')
    from studio.tests.replay import benchmark_commands as benchmark
    util.need(benchmark.GROUPS == 100 and benchmark.TERMINAL_TIMEOUT_SECONDS == 5, 'S114_WORKLOAD')
    timings = Timings()
    deadline = time.monotonic() + CHILD_SECONDS
    original_journal, original_host, original_fsync = benchmark.Journal, benchmark.LoopbackFixtureHost, os.fsync
    constructor_journals = []

    class SeededJournal(original_journal):
        def __init__(self, path):
            util.need(path == run / 'commands/commands.jsonl' and not path.exists(), 'S114_SEED_DESTINATION')
            shutil.copyfile(run / 'history-seed.jsonl', path)
            util.need(util.sha(path) == HISTORY_HASH, 'S114_SEED_COPY')
            super().__init__(path)
            constructor_journals.append(self)
            util.need(self._index_store._one('PRAGMA synchronous')[0] == 2
                and self._index_store._one('PRAGMA journal_mode')[0] == 'delete', 'S114_INDEX_POLICY')

        def _snapshot(self, *, synchronize):
            return timings.call('snapshot_' + str(synchronize).lower(),
                super()._snapshot, synchronize=synchronize)

        def _load(self):
            return timings.call('load', super()._load)

        def _reload(self):
            return timings.call('reload', super()._reload)

        def _append(self, *args, **kwargs):
            return timings.call('append', super()._append, *args, **kwargs)

    class SeededHost(original_host):
        def __init__(self, _project_id, path, journal):
            super().__init__('gt06.s114.history', path, journal)

    class BoundedProducer(benchmark.CommandProducer):
        def _command(self, *args):
            util.need(time.monotonic() < deadline, 'S114_CHILD_LIMIT')
            try:
                return super()._command(*args)
            finally:
                ordinal = args[-1]['ordinal'] + 1
                if ordinal % 100 == 0:
                    print(json.dumps({'attempted_commands': ordinal}), flush=True)

    def fsync(fd):
        label = 'fsync_' + getattr(timings.local, 'scope', 'none')
        return timings.call(label, original_fsync, fd)

    producer, batch, states = None, None, {}
    errors, body_done = [], False
    with ExitStack() as stack:
        for target, name, replacement in ((benchmark, 'Journal', SeededJournal),
                (benchmark, 'LoopbackFixtureHost', SeededHost), (os, 'fsync', fsync)):
            stack.enter_context(patch.object(target, name, replacement))
        try:
            producer = BoundedProducer(run / 'commands', RUN_ID)
            util.need(producer.observer.kind == 'native_windows_process_probe', 'S114_NATIVE_OBSERVER_REQUIRED')
            util.need(producer.host.fixture.snapshot() == {'value': 0, 'revision': 'rev-0', 'effect_count': 0},
                      'S114_FRESH_FIXTURE')
            timings.phase = 'http_batch'
            batch = producer.run_batch(0)
            util.need(producer.client.timeout == 2.0 and len(batch['commands']) == 1000, 'S114_BATCH_INCOMPLETE')
            body_done = True
        except BaseException as error:
            errors.append(('child', error))
            batch = getattr(error, 'report', batch)
            if producer is None:
                producer = getattr(error, 'cleanup_owner', None)
        finally:
            timings.phase = 'shutdown'
            if producer is not None:
                try:
                    producer.close()
                except BaseException as error:
                    errors.append(('producer_close', error))
            for journal in constructor_journals:
                try:
                    journal.close()
                except BaseException as error:
                    errors.append(('journal_close', error))
    if batch is not None:
        util.write(run / 'command-batch.json', batch)
    if producer is not None:
        util.write(run / 'http-phases-final.json', producer.phase_snapshot())
    try:
        states['producer'] = campaign._producer_cleanup_state(producer)
        state = states['producer']
        util.need(state['closed'] and not any(state['host']['threads_alive'])
            and state['host']['main_socket_closed'] and state['host']['control_socket_closed']
            and not state['observer_probe']['handle_retained'] and not state['observer_probe']['close_uncertain']
            and state['journal']['cache_closed'] and not state['journal']['index_retained'], 'S114_CLEANUP_HELD')
        journal_bytes = (run / 'commands/commands.jsonl').read_bytes()
        states['history_prefix_unchanged'] = hashlib.sha256(journal_bytes[:HISTORY_SIZE]).hexdigest() == HISTORY_HASH
        states['history_size_after'] = len(journal_bytes)
        states['records_appended'] = journal_bytes.count(b'\n') - HISTORY_LINES
        util.need(states['history_prefix_unchanged'], 'S114_HISTORY_PREFIX_CHANGED')
    except BaseException as error:
        errors.append(('verify_cleanup_history', error))
    states['source_unchanged'] = campaign.source_files() == sources
    util.write(run / 'child-report.json', {'schema': 's114.history-replay.child.1', 'run_id': RUN_ID,
        'completed': body_done and not errors and states['source_unchanged'],
        'formal_acceptance': False, 'eligible_for_dataset': False, 'engine_runs': 0,
        'pid': os.getpid(), 'errors': util.errors_record(errors), 'states': states, 'timings': timings.rows,
        'batch_status': batch.get('status') if batch else None,
        'commands': len(batch['commands']) if batch else 0,
        'max_status_gap_ms': batch.get('max_status_gap_ms') if batch else None,
        'timing_limitations': 'Nested spans overlap; non-CPU time includes I/O, lock wait, GIL and scheduling. No subtraction or root-cause inference.',
        'target_exit': None, 'target_exit_reason': 'OBSERVED_BY_PARENT_AFTER_CHILD_EXIT'})
    return 0 if body_done and not errors and states['source_unchanged'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        util, campaign, sources, history, helper = check()
        print(json.dumps({'checked': True, 'source_count': len(sources), 'closure': campaign.closure(sources),
            'profile': campaign.profile.PROFILE_SHA256, 'history_sha256': util.sha(history), 'engine_runs': 0}))
    elif sys.argv[1:] == ['--launch']:
        raise SystemExit(launch())
    elif len(sys.argv) == 3 and sys.argv[1] == '--child':
        raise SystemExit(child(sys.argv[2]))
    else:
        raise SystemExit('Use --check, --launch, or --child <frozen-run>')
