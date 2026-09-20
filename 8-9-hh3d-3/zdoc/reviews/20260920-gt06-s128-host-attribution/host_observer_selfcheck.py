"""Read-only deterministic check for the S127 host-side diagnostic observer."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('s127_observation', HERE / 'post_failure_handles.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def sleep(self, value):
        self.value += value


clock = Clock()
rows = {}
binding = {'host': {'pid': 42, 'process_start': 'windows:123'}}


def sample(_probe):
    return {'process': dict(binding['host']), 'counters': {
        'rss_bytes': {'value': 1, 'unavailable_reason': None},
        'held_handles': {'value': 210, 'unavailable_reason': None}}}


def capture(_probe):
    return {'status': 'OBSERVED', 'binding_verified': True,
            'cleanup': {'all_released': True},
            'identity': {'pid': 42, 'creation_filetime': 123}}


mod.observe_host(object(), binding=binding, sample_host=sample, capture=capture,
                 write=lambda name, value: rows.setdefault(name, value),
                 check_stop=lambda: None, clock=clock, sleep=clock.sleep)
assert sorted(rows) == [
    'post-failure-host-00.json', 'post-failure-host-01.json',
    'post-failure-host-03.json', 'post-failure-host-05.json']


class Primary(RuntimeError):
    code = 'CAMPAIGN_RETAINED_COUNTER_GROWTH'


called = []
observer = mod.GateObserver(
    original=lambda _sample, _baseline: (_ for _ in ()).throw(Primary()),
    boundary=RuntimeError, limit=35, binding=lambda _sample: binding,
    probe=lambda: object(), observe_fn=lambda *_: called.append('editor'),
    host_probe=lambda: object(), observe_host_fn=lambda *_: called.append('host'),
    write=lambda *_: None, error_record=lambda _errors: [])
try:
    observer({'memory': {'editor': {'held_handles': {'value': 5}},
                         'host': {'held_handles': {'value': 210}}}},
             {'editor': {'held_handles': {'value': 5}},
              'host': {'held_handles': {'value': 209}}})
except Primary:
    pass
assert called == ['host']
print('S127_HOST_OBSERVER_SELFCHECK=PASS')
