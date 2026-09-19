from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def main() -> int:
    probe_mod = load('s105_process_probe', ROOT / 'studio/host/replay/process_probe.py')
    adapter = load('s105_pss_adapter', Path(__file__).with_name('pss_adapter.py'))
    result = None
    try:
        with probe_mod.ProcessProbe(os.getpid(), Path(sys.executable)) as probe:
            result = adapter.capture_owned(probe)
    except Exception as exc:  # safe fixed class only; no exception text in evidence
        result = {'status': 'UNKNOWN', 'exception_code': type(exc).__name__,
                  'formal_acceptance': False, 'eligible_for_dataset': False,
                  'binding_verified': False, 'entries': [], 'type_counts': {},
                  'errors': []}
    summary = {
        'schema': 'gt06-s105-pss-adapter-selfcheck-v1',
        'actual_exit': 0,
        'python_pid': os.getpid(),
        'python_executable': str(Path(sys.executable).resolve()),
        'adapter_sha256': hashlib.sha256(
            (ROOT / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py').read_bytes()
        ).hexdigest(),
        'probe_sha256': hashlib.sha256(
            (ROOT / 'studio/host/replay/process_probe.py').read_bytes()
        ).hexdigest(),
        'status': result.get('status', 'UNKNOWN'),
        'formal_acceptance': False,
        'eligible_for_dataset': False,
        'binding_verified': result.get('binding_verified', False),
        'handles_captured': result.get('handles_captured'),
        'entry_count': len(result.get('entries', [])),
        'type_counts': result.get('type_counts', {}),
        'cleanup': result.get('cleanup'),
        'errors': result.get('errors', []),
    }
    out = Path(__file__).with_name('pss-adapter-selfcheck.json')
    out.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
