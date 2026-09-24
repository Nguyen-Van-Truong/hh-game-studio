"""One bounded Python-only Job cleanup probe; never GT06 acceptance."""
from pathlib import Path
import hashlib
import json
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_job import BenchmarkProcess, HELD_OWNERS, require
from studio.host.replay.process_probe import ProcessProbe, HELD_PROBES

RUN_ID = 'gt06-s227-terminal-exit-01'
RAW = ROOT / 'studio/.local/reviews' / RUN_ID


def main():
    campaign.load_fixture()
    sources = campaign.source_files()
    RAW.mkdir(exist_ok=False)
    context = {'run_id': RUN_ID, 'index': 0, 'source_files': sources,
               'source_closure_sha256': campaign.closure(sources),
               'profile_sha256': campaign.profile.PROFILE_SHA256}
    campaign.write(RAW / 'context.json', context)
    campaign.write(RAW / 'preflight.json', {
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'python_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        'engine_started': False, 'formal_acceptance': False, 'authority': 0,
        'hypothesis': 'Read exact target exit through the existing probe after owned Job cleanup kills helper and target.'})
    for name, expected in sources.items():
        raw = (ROOT / 'studio' / name).read_bytes()
        require(campaign.sha(raw) == expected, 'EXIT_PROBE_SOURCE_CHANGED')
        campaign.write(RAW / 'source' / name, raw)
    owner = probe = None
    try:
        owner = BenchmarkProcess([sys.executable, '-B', '-c', 'import time; time.sleep(15)'],
            cwd=RAW, output=RAW / 'editor-host', source_root=ROOT / 'studio',
            source_files=sources, binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())
        deadline = time.monotonic() + 5
        while True:
            try:
                launched = json.loads((RAW / 'editor-host/process-start.json').read_bytes())
                break
            except (FileNotFoundError, json.JSONDecodeError):
                require(owner.tick() is None and time.monotonic() < deadline, 'EXIT_PROBE_START')
                time.sleep(.02)
        probe = ProcessProbe(launched['pid'], Path(sys.executable))
        require(probe.exit_observation() is None, 'EXIT_PROBE_PREMATURE_EXIT')
        primary = campaign.BenchmarkJobError('EXIT_PROBE_INJECTED_FAILURE')
        campaign._finish_child_cleanup(RAW, context, {'batch': 0, 'phase': 'injected_cleanup'}, [],
            producer=None, probe=probe, owner=owner, retained=None, done=threading.Event(),
            thread=threading.Thread(), primary=primary, errors=[])
        terminal = json.loads((RAW / 'child-terminal-cleanup.json').read_bytes())
        observed = terminal['observations']
        exit_row = observed['editor_exit_after_cleanup']
        require(not terminal['errors'], 'EXIT_PROBE_CLEANUP_ERROR')
        require(exit_row is not None and exit_row['pid'] == launched['pid']
                and exit_row['process_start'] == probe.process_start and exit_row['exit_code'] == 2
                and exit_row['natural_exit_not_inferred'], 'EXIT_PROBE_NATIVE_EXIT')
        require(owner.closed and owner.job.closed and owner.job.zero_observed
                and probe.handle is None and not HELD_OWNERS and not HELD_PROBES, 'EXIT_PROBE_HELD')
        campaign.verify_sources(sources)
        campaign.write(RAW / 'result.json', {
            'run_id': RUN_ID, 'authority': 0, 'formal_acceptance': False, 'engine_started': False,
            'passed': True, 'target_observation': exit_row,
            'helper_exit': owner.process.returncode,
            'original_target_receipt': observed['editor_target']['actual_target_exit'],
            'job': owner.job.snapshot(), 'wrapper_handle': owner.process_handle_snapshot(),
            'probe_handle_released': probe.handle is None,
            'source_unchanged': True, 'terminal_sha256': campaign.sha((RAW / 'child-terminal-cleanup.json').read_bytes())})
        print(json.dumps({'run_id': RUN_ID, 'passed': True, 'target_exit': exit_row['exit_code'],
                          'helper_exit': owner.process.returncode, 'engine_started': False}))
    finally:
        if owner is not None and not owner.closed:
            owner.close()
        if probe is not None:
            probe.close()


if __name__ == '__main__':
    main()
