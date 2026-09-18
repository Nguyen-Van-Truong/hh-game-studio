"""Preserve the pre-measurement import failure and verify retry prerequisites."""
from pathlib import Path
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    raw = ROOT / 'studio/.local/reviews/gt06-s76-campaign-01'
    run = raw / 'run-00-attempt-01'
    supervisor = raw.with_name(raw.name + '-supervisor')
    failure = read(run / 'child-failure.json')
    assert failure['phase'] == {'batch': -1, 'phase': 'import'} and failure['completed_batches'] == 0
    parent = read(run / 'parent-failure.json')
    assert parent['owned_tree_zero'] and parent['owner_closed'] and parent['cleanup_error'] is None
    host = read(run / 'host-owner/cleanup-001.json')
    imported = read(run / 'import-host/capture.json')
    for capture in (host, imported):
        job = capture['job']
        assert job['zero_observed'] and job['closed'] and not job['handle_retained'] and not job['failed_operations']
        assert not job['tainted'] and not job['create_uncertain'] and not job['close_uncertain']
    assert host['wrapper_process_handle']['closed'] and not host['wrapper_process_handle']['handle_retained']
    assert read(run / 'host-owner/process-exit.json')['exit_code'] == 1
    assert imported['failure'] == 'STAGE_WALL_LIMIT' and imported['limits']['effective_wall_seconds'] == 20
    assert not (run / 'import-host/process-exit.json').exists()
    assert not list(run.glob('batch-capture-*')) and not (run / 'editor-host').exists()
    current = read(BASE / 'current-runtime-source.json')
    assert current['source_files'] == read(run / 'source-files.json')
    for name, digest in current['source_files'].items():
        assert sha(ROOT / 'studio' / name) == digest
    campaign.load_fixture()
    assert campaign.source_files() == current['source_files']
    # Match the runner's JSON representation: platform.win32_ver() returns a
    # tuple, while a saved JSON array decodes as list. The first ad hoc check
    # compared these directly and failed before copying any evidence.
    assert json.loads(campaign.encoded(campaign.workstation_profile())) == read(raw / 'campaign.json')['workstation']
    campaign.require_campaign_running(raw)
    records = []
    output = BASE / 'campaign-import-failure-01'
    for label, folder in [('campaign', raw), ('supervisor', supervisor)]:
        paths = sorted(folder.rglob('*'))
        for path in paths:
            if not path.is_file() or '.godot' in path.parts:
                continue
            # Seal launch1 only; a later verified resume has its own evidence.
            relative = path.relative_to(folder)
            if label == 'campaign' and relative.parts[0].startswith('run-') and relative.parts[0] != run.name:
                continue
            target = output / label / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = path.read_bytes()
            if target.exists():
                assert target.read_bytes() == content
            else:
                target.write_bytes(content)
            records.append({'file': (Path(label) / relative).as_posix(), 'bytes': len(content), 'sha256': sha(path)})
    report = {'formal_acceptance': False, 'campaign_id': raw.name, 'launch': 1,
              'failure': 'STAGE_WALL_LIMIT', 'phase': 'import', 'complete_batches': 0,
              'native_pid': read(run / 'import-host/process-start.json')['pid'], 'native_exit': None,
              'import_wrapper_exit': imported['wrapper_exit_code'],
              'host_actual': read(run / 'host-owner/process-exit.json'), 'host_wrapper_exit': host['wrapper_exit_code'],
              'all_jobs_zero_closed': True, 'owner_process_handle_closed': True,
              'source_profile_machine_unchanged': True, 'stop_latches_absent': True,
              'source_closure': current['closure_sha256'], 'files': records}
    (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}))
    print('exact_copies', len(records))


if __name__ == '__main__':
    main()
