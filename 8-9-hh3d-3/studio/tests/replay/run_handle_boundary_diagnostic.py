"""One diagnostic pair, at most nine batches; never a formal campaign.

Reuse the unchanged campaign screen and owned cleanup. Keep the first failed
sample, then observe the same retained target handle for two seconds without
issuing another START permit. Successful prefixes receive no additional idle.
This trusted local entrypoint has no product/API capability or dataset output.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_benchmark_campaign as campaign

MAX_BATCHES = 9
IDLE_SECONDS = 2.0
POLL_SECONDS = .1
OUTER_SECONDS = 1800


class DiagnosticBoundReached(campaign.BenchmarkJobError):
    def __init__(self):
        super().__init__('DIAGNOSTIC_NINE_BATCH_BOUND')


class BoundaryRecorder:
    def __init__(self, root, context):
        self.root, self.context = root, context
        self.probe = self.log = None
        self.samples = []
        self.original_screen = campaign.screen_sample

    def observe(self, phase, index, observation=None):
        if observation is None:
            observation = self.probe.sample_with_handle_count()
        campaign.require(observation is not None, 'DIAGNOSTIC_TARGET_EXITED')
        self.samples.append({'phase': phase, 'batch_index': index,
            'pid': self.probe.pid, 'process_start': self.probe.process_start,
            'observation': observation})

    def stop(self):
        return campaign.stop_requested(self.root,
            **{key: self.context[key] for key in
               ('run_id', 'source_closure_sha256', 'campaign_sha256')})

    def collect_idle(self, index):
        started = time.monotonic()
        error_code = None
        try:
            # Both time and count are bounded, including under a broken clock.
            for _ in range(21):
                campaign.require(not self.stop(), 'BENCHMARK_STOPPED')
                campaign.require(self.log.poll() is None, 'DIAGNOSTIC_TARGET_EXITED')
                self.observe('terminal_idle', index)
                remaining = IDLE_SECONDS - (time.monotonic() - started)
                if remaining <= 0:
                    break
                time.sleep(min(POLL_SECONDS, remaining))
        except Exception as error:
            error_code = getattr(error, 'code', type(error).__name__)
        campaign.write(self.root / 'handle-boundary.json', {
            'schema_id': 'hh-studio.diagnostic-handle-boundary', 'schema_version': '1.0.0',
            'run_id': self.context['run_id'], 'authority': 0, 'formal_acceptance': False,
            'source_closure_sha256': self.context['source_closure_sha256'],
            'profile_sha256': self.context['profile_sha256'],
            'samples': self.samples, 'collection_error': error_code,
            'max_batches': MAX_BATCHES, 'idle_budget_seconds': IDLE_SECONDS,
            'no_next_start_permit': True, 'baseline_or_gate_replaced': False,
            'root_cause_claim': False})
        return error_code

    def screen(self, sample, baseline):
        try:
            self.original_screen(sample, baseline)
        except campaign.CampaignScreenError as error:
            # Persist the ORIGINAL error before any supplemental observation.
            campaign.write(self.root / 'diagnostic-first-failure.json', {
                'code': error.code, 'screen_observation': error.screen_observation,
                'formal_acceptance': False, 'authority': 0})
            try:
                self.collect_idle(sample['index'])
            except Exception as collector_error:
                # A supplemental write failure must not replace the first gate failure.
                campaign.write(self.root / 'diagnostic-collector-error.json', {
                    'type': type(collector_error).__name__, 'formal_acceptance': False})
            raise
        if sample['index'] == MAX_BATCHES - 1:
            collection_error = self.collect_idle(sample['index'])
            campaign.require(collection_error is None, collection_error or 'DIAGNOSTIC_COLLECTION')
            raise DiagnosticBoundReached()

    @contextmanager
    def installed(self):
        original_probe = campaign.open_probe
        original_sample = campaign.sample_editor
        original_log = campaign.NativeLog
        original_screen = campaign.screen_sample
        recorder = self

        def open_probe(*args):
            self.probe = original_probe(*args)
            return self.probe

        def sample_editor(probe):
            observed = original_sample(probe)
            self.observe('original_pre_ack', self.log.batch_index, observed)
            return observed

        class DiagnosticLog(original_log):
            batch_index = -1

            def __init__(self, owner):
                super().__init__(owner)
                recorder.log = self

            def wait(self, suffix, index, timeout):
                result = super().wait(suffix, index, timeout)
                self.batch_index = index
                if suffix == 'ACK':
                    recorder.observe('after_ack', index)
                return result

        campaign.open_probe = open_probe
        campaign.sample_editor = sample_editor
        campaign.NativeLog = DiagnosticLog
        campaign.screen_sample = self.screen
        try:
            yield
        finally:
            campaign.open_probe = original_probe
            campaign.sample_editor = original_sample
            campaign.NativeLog = original_log
            campaign.screen_sample = original_screen


def run_child(root):
    context = json.loads(campaign.read_regular(root / 'context.json'))
    recorder = BoundaryRecorder(root, context)
    with recorder.installed():
        try:
            campaign.run_child(root)
        except (campaign.CampaignScreenError, DiagnosticBoundReached) as error:
            # Exit 0 here means bounded collection returned after owned cleanup,
            # not native success or a passed screen. The failed row stays failed.
            campaign.write(root / 'diagnostic-result.json', {
                'run_id': context['run_id'], 'terminal_reason': error.code,
                'authority': 0, 'formal_acceptance': False,
                'benchmark_completed': False, 'collector_returned': True})
            return 0
    raise RuntimeError('DIAGNOSTIC_BOUND_NOT_ENFORCED')


def run_parent(run_id):
    campaign.load_fixture()
    sources = campaign.source_files()
    campaign.require('tests/replay/run_handle_boundary_diagnostic.py' in sources,
                     'DIAGNOSTIC_SOURCE_MISSING')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    digest = campaign.closure(sources)
    context = {'run_id': run_id, 'index': 0, 'attempt': 1, 'source_files': sources,
        'source_closure_sha256': digest, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'campaign_sha256': campaign.sha(campaign.encoded({'diagnostic_id': run_id,
            'source': digest, 'max_batches': MAX_BATCHES}))}
    campaign.write(root / 'context.json', context)
    campaign.write(root / 'source-files.json', sources)
    campaign.write(root / 'preflight.json', {'authority': 0, 'formal_acceptance': False,
        'hypothesis': 'Target handles at first failed screen may settle during no-permit idle.',
        'max_batches': MAX_BATCHES, 'outer_seconds': OUTER_SECONDS,
        'idle_seconds': IDLE_SECONDS, 'workstation': campaign.workstation_profile(),
        'source_closure_sha256': digest, 'source_files': len(sources),
        'profile_sha256': campaign.profile.PROFILE_SHA256})
    campaign.write(root / 'benchmark-profile.json',
        campaign.encoded(campaign.asdict(campaign.profile.PROFILE)))
    for name, expected in sources.items():
        raw = campaign.read_regular(STUDIO / name)
        campaign.require(campaign.sha(raw) == expected, 'DIAGNOSTIC_FREEZE_CHANGED')
        campaign.write(root / 'source/studio' / name, raw)
    owner = None
    try:
        owner = campaign.BenchmarkProcess([sys.executable, '-B', str(Path(__file__).resolve()),
            '--run-id', run_id, '--child'], cwd=root, output=root / 'host-owner',
            source_root=STUDIO, source_files=sources, campaign_host=True,
            binary_sha256=campaign.sha(campaign.read_regular(Path(sys.executable), 256 * 1024**2)))
        deadline = time.monotonic() + OUTER_SECONDS
        while True:
            stop = campaign.stop_requested(root, **{key: context[key] for key in
                ('run_id', 'source_closure_sha256', 'campaign_sha256')})
            campaign.require(time.monotonic() < deadline, 'DIAGNOSTIC_OUTER_TIMEOUT')
            if owner.tick(stop=stop) is not None:
                campaign.require(not stop, 'BENCHMARK_STOPPED')
                break
            time.sleep(.1)
        capture = owner.finish()
        campaign.verify_sources(sources)
        result = json.loads(campaign.read_regular(root / 'diagnostic-result.json'))
        cleanup = json.loads(campaign.read_regular(root / 'child-terminal-cleanup.json'))
        campaign.write(root / 'parent-result.json', {'authority': 0, 'formal_acceptance': False,
            'run_id': run_id, 'terminal_reason': result['terminal_reason'],
            'host_actual_exit': capture['actual_process_exit'],
            'job': capture['job'], 'wrapper_process_handle': capture['wrapper_process_handle'],
            'child_cleanup_sha256': campaign.sha(campaign.read_regular(root / 'child-terminal-cleanup.json')),
            'child_cleanup_errors': cleanup['errors'], 'source_unchanged': True})
        return 0
    except BaseException as error:
        owner = owner or getattr(error, 'cleanup_owner', None)
        if owner is not None:
            owner.close()
        campaign.write(root / 'parent-failure.json', {
            'run_id': run_id, 'authority': 0, 'formal_acceptance': False,
            'code': getattr(error, 'code', type(error).__name__),
            'owner_closed': owner.closed if owner else False,
            'owned_tree_zero': owner.job.zero_observed if owner and owner.job else False})
        raise
    finally:
        if owner is not None:
            owner.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    campaign.require(os.name == 'nt' and re.fullmatch(r'gt06-[a-z0-9-]{1,40}', args.run_id),
                     'DIAGNOSTIC_ID_OR_PLATFORM')
    if args.child:
        return run_child(STUDIO / '.local/reviews' / args.run_id)
    return run_parent(args.run_id)


if __name__ == '__main__':
    raise SystemExit(main())
