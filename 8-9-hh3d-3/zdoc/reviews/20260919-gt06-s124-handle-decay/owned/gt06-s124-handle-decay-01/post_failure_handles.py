"""Diagnostic-only observations AFTER a durably recorded original rejection.

No observations precede the failing gate. No result changes or replaces it.
The caller retains ownership of the process and performs normal cleanup.
"""
from __future__ import annotations

import time


class ObservationError(RuntimeError):
    pass


def need(condition, code):
    if not condition:
        raise ObservationError(code)


def observe(probe, *, binding, sample_editor, capture, write, check_stop,
            clock=time.monotonic, sleep=time.sleep):
    started = clock()
    rows = []
    for offset in (0, 1, 3, 5):
        check_stop()
        while clock() - started < offset:
            sleep(min(.05, offset - (clock() - started)))
            check_stop()
        need(clock() - started < 8, 'S124_OBSERVATION_WALL_LIMIT')
        before = sample_editor(probe)
        row = {'offset_seconds': offset, 'elapsed_seconds': clock() - started,
               'binding': binding, 'counters': before,
               'formal_acceptance': False, 'eligible_for_dataset': False}
        # Two type inventories, both strictly after rejection. Numeric handle
        # values cannot establish persistent kernel object identity.
        if offset in (0, 5):
            row['pss'] = capture(probe)
        write(f'post-failure-{offset:02d}.json', row)
        rows.append(row)
        if 'pss' in row:
            pss = row['pss']
            need(pss.get('status') == 'OBSERVED'
                 and pss.get('binding_verified') is True
                 and pss.get('cleanup', {}).get('all_released') is True,
                 'S124_PSS_INCOMPLETE')
            identity = pss['identity']
            need(identity['pid'] == binding['editor']['pid']
                 and 'windows:' + str(identity['creation_filetime'])
                     == binding['editor']['process_start'], 'S124_PSS_IDENTITY')
        check_stop()
        need(clock() - started < 8, 'S124_OBSERVATION_WALL_LIMIT')
    return rows


class GateObserver:
    def __init__(self, *, original, boundary, limit, binding, probe, observe_fn,
                 write, error_record):
        self.original, self.boundary, self.limit = original, boundary, limit
        self.binding, self.probe, self.observe_fn = binding, probe, observe_fn
        self.write, self.error_record = write, error_record
        self.gates = []

    def __call__(self, sample, baseline):
        try:
            self.original(sample, baseline)
        except BaseException as primary:
            # The original exception is re-raised even if receipt/probe fails.
            try:
                binding = self.binding(sample)
                self.write('original-gate-failure.json', {
                    'binding': binding, 'sample': sample, 'baseline': baseline,
                    'primary': self.error_record([('original_gate', primary)]),
                    'formal_acceptance': False, 'eligible_for_dataset': False})
                value = sample['memory']['editor']['held_handles']['value']
                reference = baseline['editor']['held_handles']['value']
                if (getattr(primary, 'code', None) == 'CAMPAIGN_RETAINED_COUNTER_GROWTH'
                        and value > reference):
                    self.observe_fn(self.probe(), binding)
            except BaseException as supplemental:
                # Failed writes remain a gap; never disguise the original gate.
                try:
                    self.write('post-failure-error.json', {
                        'errors': self.error_record([('supplemental', supplemental)]),
                        'formal_acceptance': False, 'eligible_for_dataset': False})
                except BaseException:
                    pass
            raise
        self.gates.append({'index': sample['index'], 'original_gate': 'PASSED'})
        if len(self.gates) == self.limit:
            raise self.boundary('S124_PREFIX_BOUNDARY_NO_HANDLE_REPRODUCTION')
