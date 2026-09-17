"""One disclosed, read-only120s telemetry window on the owned S75 pair."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.host.replay.process_probe import ProcessProbe

BASE = Path(__file__).parent
raw = ROOT / 'studio/.local/reviews/gt06-s75-campaign-01/run-00-attempt-01'
out = BASE / 'startup-telemetry-01'
out.mkdir(exist_ok=False)
lock = json.loads((ROOT / 'studio/toolchain.lock.json').read_bytes())['godot']
editor = ROOT / 'studio/.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
helper = BASE / 'owned_telemetry.py'
argv = [sys.executable, '-B', str(helper), '--run-id', 'gt06-s75-startup-telemetry-01',
    '--duration', '120', '--interval', '1']
identities = []
for role, executable in (('host-owner', Path(sys.executable)), ('editor-host', editor)):
    start = json.loads((raw / role / 'process-start.json').read_bytes())
    with ProcessProbe(start['pid'], executable) as probe:
        assert probe.sample() is not None
        identity = {'role': role, 'pid': probe.pid,
            'creation_time_100ns': probe.process_start.removeprefix('windows:'),
            'exe_path': str(executable.resolve())}
    identities.append(identity)
    argv += ['--target', str(identity['pid']), identity['creation_time_100ns'], identity['exe_path']]
invocation = {'targets': identities, 'argv': argv, 'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
    'diagnostic_only': True, 'formal_acceptance': False,
    'overhead': 'External read-only observer once/second for120s; no gate/baseline replacement'}
(out / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n', encoding='utf-8')
spec = importlib.util.spec_from_file_location('owned_runner', ROOT / 'studio/build/bootstrap/run_fixture.py')
owned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owned)
result = owned.run_process(argv, cwd=ROOT, output=out, timeout=130, label='telemetry')
(out / 'capture.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
assert hashlib.sha256(helper.read_bytes()).hexdigest() == invocation['helper_sha256']
print(json.dumps(result), flush=True)
sys.exit(result['exit_code'])
