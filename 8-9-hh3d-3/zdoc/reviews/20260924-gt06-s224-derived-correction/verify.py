"""Engine-free replay of sealed S218 rows against old and current screen code."""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign

RAW = ROOT / 'studio/.local/reviews/gt06-s218-formal-01'
MANIFEST_HASH = '434315b750c489713437d7045a7b7d97b5b2ce04cb647d76a5aa82a14b14968c'
OLD_HASH = '71a3d19cf0b435baf598d6caad13daeb910799457f89a282366ee2fefa5223fd'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    manifest_bytes = (RAW / 'raw-manifest.json').read_bytes()
    assert digest(manifest_bytes) == MANIFEST_HASH
    manifest = json.loads(manifest_bytes)
    rows = {row['path']: row for row in manifest['files']}
    verified = {}

    def sealed(name):
        relative = 'run-00-attempt-01/' + name
        raw = (RAW / relative).read_bytes()
        row = rows['raw/' + relative]
        assert digest(raw) == row['sha256'] and len(raw) == row['bytes']
        verified[relative] = row['sha256']
        return json.loads(raw)

    before, after = sealed('sample-preview-04.json'), sealed('sample-preview-05.json')
    joint_before, joint_after = sealed('joint-04.json'), sealed('joint-05.json')
    context = sealed('context.json')
    failure = sealed('child-failure.json')
    started, exited = sealed('host-owner/process-start.json'), sealed('host-owner/process-exit.json')
    cleanup = sealed('host-owner/cleanup-001.json')
    imported = sealed('import-host/process-exit.json')
    assert before['index'] == 4 and after['index'] == 5
    assert before['processes'] == after['processes'] == joint_before['processes'] == joint_after['processes']
    assert started['pid'] == exited['pid'] == after['processes']['host']['pid']
    assert exited['exit_code'] == 1 and imported['exit_code'] == 0
    assert cleanup['wrapper_exit_code'] == 1 and cleanup['closed']
    assert cleanup['job']['closed'] and cleanup['job']['zero_observed'] and cleanup['job']['active_count'] == 0
    assert not cleanup['wrapper_process_handle']['handle_retained']

    old = subprocess.check_output(['git', 'show',
        '5a054cc3:8-9-hh3d-3/studio/tests/replay/run_benchmark_campaign.py'], cwd=ROOT)
    assert digest(old) == OLD_HASH == context['source_files']['tests/replay/run_benchmark_campaign.py']
    screen = next(node for node in ast.parse(old).body
                  if isinstance(node, ast.FunctionDef) and node.name == 'screen_sample')

    class HistoricalFailure(Exception):
        pass

    first = {}

    def require(condition, code):
        if not condition:
            # Read the failing old predicate's locals; never mutate the row.
            frame = inspect.currentframe().f_back
            try:
                first.update(code=code, role=frame.f_locals['role'], counter=frame.f_locals['name'])
            finally:
                del frame
            raise HistoricalFailure(code)

    namespace = {'require': require}
    exec(compile(ast.Module(body=[screen], type_ignores=[]), '<sealed-S218-screen>', 'exec'), namespace)
    namespace['screen_sample'](before, None)
    try:
        namespace['screen_sample'](after, before['memory'])
    except HistoricalFailure:
        pass
    else:
        raise AssertionError('Historical screen must reject this sealed row')
    assert first == {'code': failure['code'], 'role': 'host', 'counter': 'rss_bytes'}
    unchanged = json.dumps((before, after), sort_keys=True)
    try:
        campaign.screen_sample(after, before['memory'])
    except campaign.CampaignScreenError as error:
        assert error.code == first['code']
        observation = error.screen_observation
    else:
        raise AssertionError('Current screen must reject this sealed row')
    assert json.dumps((before, after), sort_keys=True) == unchanged
    assert observation['role'] == 'host' and observation['counter'] == 'rss_bytes'
    assert observation['baseline_value'] == 27451392 and observation['observed_value'] == 38883328
    assert observation['maximum_inclusive'] == 30196531
    assert after['max_status_gap_ms'] == 1675.9498
    assert joint_after['barrier_receipt']['max_status_gap_ms'] == 691.731
    timeline = []
    for index in range(6):
        command = sealed(f'command-{index:02d}.json')
        joint = sealed(f'joint-{index:02d}.json')
        assert command['host_process'] == joint['processes']['host']
        timeline.append({'batch': index,
            'command_before_rss': command['memory_before']['counters']['rss_bytes']['value'],
            'command_after_rss': command['memory_after']['counters']['rss_bytes']['value'],
            'host_joint_rss': joint['host']['counters']['rss_bytes']['value'],
            'editor_joint_rss': joint['editor']['rss_bytes']['value'],
            'command_started_mono_us': command['started_mono_us'],
            'command_ended_mono_us': command['ended_mono_us'],
            'host_joint_mono_us': joint['host']['monotonic_us'],
            'post_command_to_joint_us': joint['host']['monotonic_us'] - command['ended_mono_us']})
    phases = sealed('http-phases-final.json')['observation']
    first_lookup_ns = phases['first_failure']['captured_ns']
    assert timeline[1]['command_started_mono_us'] * 1000 <= first_lookup_ns <= timeline[1]['command_ended_mono_us'] * 1000
    assert first_lookup_ns < joint_before['host']['monotonic_us'] * 1000
    campaign.load_fixture()
    files = campaign.source_files()
    campaign.verify_sources(files)
    assert set(files) == set(context['source_files']) and len(files) == 53
    changed = [name for name in files if files[name] != context['source_files'][name]]
    assert changed == ['tests/replay/run_benchmark_campaign.py']
    print(json.dumps({'authority': 0, 'engine_started': False, 'formal_acceptance': False,
        'verified_raw': verified, 'historical_first_failure': first, 'current_observation': observation,
        'source_files': files, 'source_closure_sha256': campaign.closure(files),
        'historical_source_closure_sha256': context['source_closure_sha256'],
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        'rss_timeline': timeline, 'first_lookup_failure_captured_ns': first_lookup_ns,
        'first_lookup_failure_batch': 1, 'post_warmup_first_failure_allocation_hypothesis': 'CONTRADICTED_BY_RAW_TIMESTAMP',
        'timeline_root_cause_claim': False,
        'host_actual_exit': exited, 'editor_actual_exit': None,
        'changed_source_files': changed, 'status': 'VERIFIED'}, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
