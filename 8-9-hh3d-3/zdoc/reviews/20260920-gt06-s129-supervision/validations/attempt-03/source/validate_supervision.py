"""Bounded no-engine S129 validation; only kills its exact retained fixture handles."""
from __future__ import annotations
import argparse
import copy
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
import passive_observer as observer

BASE = observer.BASE
REFERENCES = {
    '../20260919-gt06-s106-coordinator/observe_runner.ps1': '182dfafd4fb1695028ec4c6fc221e3c38171a17b44767879fe6ccf7b4bef7ac6',
    '../20260919-gt06-s119-launch-recovery/task.ps1': '8d6577e57ced78406f7d47898b26419e5a0ae1f89768979f76eb6d2ab2ce5df6',
    '../20260919-gt06-s119-launch-recovery/launch.ps1': '1bdc4dad584cd48528f6001be3edeac590f354bce897c7ecf190f86a39724cb8',
}


def native():
    k = observer.kernel()
    k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    k.TerminateProcess.argtypes, k.TerminateProcess.restype = [w.HANDLE, w.UINT], w.BOOL
    k.GetCurrentProcess.restype = w.HANDLE
    k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    k.DuplicateHandle.restype = w.BOOL
    return k


def parent_pid(handle):
    class Basic(ctypes.Structure):
        _fields_ = [('reserved1', ctypes.c_void_p), ('peb', ctypes.c_void_p),
                    ('reserved2', ctypes.c_void_p * 2), ('pid', ctypes.c_size_t), ('parent', ctypes.c_size_t)]
    dll = ctypes.WinDLL('ntdll')
    dll.NtQueryInformationProcess.argtypes = [w.HANDLE, w.ULONG, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
    dll.NtQueryInformationProcess.restype = w.LONG
    value, length = Basic(), w.ULONG()
    observer.need(dll.NtQueryInformationProcess(handle, 0, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(length)) == 0
        and length.value == ctypes.sizeof(value), 'S129_TEST_PARENT_QUERY')
    return int(value.parent)


def wait_exit(handle, identity):
    observer.need(native().WaitForSingleObject(handle, 3000) == 0, 'S129_TEST_EXIT_WAIT')
    value = observer.observe_exit(handle, identity)
    observer.need(value is not None, 'S129_TEST_EXIT_UNKNOWN')
    return value


def probe(mode, expected, attempt):
    run_id = 'gt06-s129-probe-' + mode + f'-{attempt:02d}'
    fixture = BASE / 'fixtures' / run_id
    fixture.parent.mkdir(exist_ok=True)
    fixture.mkdir(exist_ok=False)
    request = observer.make_request(run_id, BASE / 'controller_probe.py',
        ['--mode', 'abrupt' if mode == 'timeout' else mode, '--fixture', str(fixture), '--gated'],
        observation_seconds=1 if mode == 'timeout' else 15)
    retained = {}
    interventions = []
    k = native()

    def hook(process, start, output):
        try:
            duplicate = w.HANDLE()
            current = k.GetCurrentProcess()
            observer.need(k.DuplicateHandle(current, int(process._handle), current, ctypes.byref(duplicate), 0, False, 2), 'S129_TEST_DUPLICATE_CONTROLLER')
            retained['controller_handle'] = duplicate.value
            retained['controller_identity'] = start
            deadline = time.monotonic() + 3
            ready = fixture / 'child-start.json'
            while not ready.exists():
                observer.need(time.monotonic() < deadline, 'S129_TEST_CHILD_START_TIMEOUT')
                time.sleep(.01)
            child = json.loads(ready.read_bytes())
            observer.need(child['parent_pid'] == process.pid, 'S129_TEST_CHILD_RECEIPT_PARENT')
            handle = k.OpenProcess(0x100000 | 0x1000 | 0x0001, False, child['identity']['pid'])
            observer.need(handle, 'S129_TEST_CHILD_HANDLE')
            retained['handle'] = handle
            retained['identity'] = child['identity']
            observer.need(observer.identity(handle, child['identity']['pid']) == child['identity'], 'S129_TEST_CHILD_IDENTITY')
            observer.need(parent_pid(handle) == start['pid'], 'S129_TEST_CHILD_ACTUAL_PARENT')
            observer.need(Path(child['identity']['executable']) == Path(request['argv'][0]), 'S129_TEST_CHILD_IMAGE')
            observer.need(k.WaitForSingleObject(handle, 0) == 258, 'S129_TEST_CHILD_LIVE')
            if mode == 'abrupt':
                # The observer remains passive; only this fixture harness acts.
                observer.need(k.TerminateProcess(int(process._handle), 47), 'S129_TEST_CONTROLLER_TERMINATE')
                interventions.append({'role': 'controller', 'identity': start, 'api': 'TerminateProcess(retained_Popen_handle)', 'requested_exit': 47})
            elif mode != 'timeout':
                (fixture / 'release-leaf').write_bytes(b'owned fixture release\n')
        except BaseException:
            # Exact owned controller handle only; never reopen/kill a PID.
            if process.poll() is None:
                k.TerminateProcess(int(process._handle), 91)
                process.wait(timeout=3)
            raise

    result = None
    cleanup = None
    try:
        result = observer.observe(request, fixture_hook=hook)
        if mode == 'timeout':
            observer.need(result['actual_exit'] is None and result['status'] == 'UNKNOWN_OR_OBSERVER_ERROR'
                and [e['code'] for e in result['errors']] == ['S129_OBSERVATION_TIMEOUT_WORKLOAD_UNCHANGED'], 'S129_TEST_PASSIVE_TIMEOUT')
            observer.need(k.WaitForSingleObject(retained['controller_handle'], 0) == 258, 'S129_TEST_TIMEOUT_CONTROLLER_STILL_LIVE')
            observer.need(not (BASE / 'runs' / run_id / 'launcher-exit.json').exists(), 'S129_TEST_NO_FABRICATED_EXIT')
        else:
            observer.need(not result['errors'] and result['status'] == 'EXIT_OBSERVED', 'S129_TEST_OBSERVER_FAILED')
            observer.need(result['actual_exit']['exit_code_uint32'] == expected, 'S129_TEST_CONTROLLER_EXIT')
        observer.need(result['handle_close']['native_close_succeeded'], 'S129_TEST_CONTROLLER_CLOSE')
    finally:
        if retained.get('controller_handle'):
            handle = retained['controller_handle']
            live = k.WaitForSingleObject(handle, 0) == 258
            if live:
                observer.need(k.TerminateProcess(handle, 49), 'S129_TEST_TIMEOUT_CONTROLLER_CLEANUP')
                interventions.append({'role': 'controller', 'identity': retained['controller_identity'],
                    'api': 'TerminateProcess(retained_duplicated_handle)', 'requested_exit': 49})
            after = wait_exit(handle, retained['controller_identity'])
            closed = bool(k.CloseHandle(handle))
            observer.write(fixture / 'controller-cleanup-supplement.json', {'actual_exit': after,
                'forced_by_fixture_harness_after_observer_return': live, 'native_close_bool_observed': True,
                'native_close_succeeded': closed, 'does_not_rewrite_observer_result': True})
            observer.need(closed, 'S129_TEST_DUPLICATE_CLOSE')
        if retained.get('handle'):
            handle = retained['handle']
            was_live = k.WaitForSingleObject(handle, 0) == 258
            if was_live:
                observer.need(k.TerminateProcess(handle, 48), 'S129_TEST_CHILD_TERMINATE')
                interventions.append({'role': 'leaf', 'identity': retained['identity'],
                    'api': 'TerminateProcess(retained_identity_checked_handle)', 'requested_exit': 48})
            actual = wait_exit(handle, retained['identity'])
            closed = bool(k.CloseHandle(handle))
            cleanup = {'identity': retained['identity'], 'actual_exit': actual,
                'forced_by_fixture_harness': was_live, 'native_close_bool_observed': True,
                'native_close_succeeded': closed, 'observed_utc': observer.utc()}
            observer.write(fixture / 'leaf-cleanup-observation.json', cleanup)
            observer.need(closed, 'S129_TEST_CHILD_CLOSE')
    observer.need(cleanup is not None and cleanup['actual_exit']['exit_code_uint32'] == (48 if mode in ('abrupt', 'timeout') else 0), 'S129_TEST_LEAF_EXIT')
    observer.need(cleanup['forced_by_fixture_harness'] == (mode in ('abrupt', 'timeout')), 'S129_TEST_LEAF_FORCED_SCOPE')
    observer.need((fixture / 'child-exit.json').exists() == (mode not in ('abrupt', 'timeout')), 'S129_TEST_ABRUPT_NO_CONTROLLER_FINALLY')
    row = {'mode': mode, 'expected_launcher_exit': expected, 'actual_launcher_exit': result['actual_exit'],
        'launcher_identity': result['identity'], 'launcher_native_close': result['handle_close'],
        'leaf_cleanup': cleanup, 'interventions': interventions,
        'source_pins': observer.own_pins(), 'run_id': run_id, 'formal_acceptance': False}
    observer.write(fixture / 'validation-row.json', row)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=int, required=True)
    args = parser.parse_args()
    observer.need(1 <= args.attempt <= 99, 'S129_ATTEMPT')
    observer.need(os.name == 'nt', 'S129_WINDOWS_ONLY')
    began = time.monotonic()
    pins = observer.own_pins()
    retained_source = BASE / 'validations' / f'attempt-{args.attempt:02d}' / 'source'
    retained_source.mkdir(parents=True, exist_ok=False)
    for name, expected in pins.items():
        shutil.copyfile(BASE / name, retained_source / name)
        observer.need(observer.sha(retained_source / name) == expected, 'S129_VALIDATION_SOURCE_COPY')
    for name, value in REFERENCES.items():
        observer.need(observer.sha(BASE / name) == value, 'S129_REUSE_SOURCE_DRIFT')
    provenance = {'sources': REFERENCES, 'read_only_originals': True,
        'reuse': 'S106 retained-process observation; S119 demand-only scheduler definition', 'formal_acceptance': False}
    provenance_path = BASE / 'reuse-source-pins.json'
    if provenance_path.exists():
        observer.need(json.loads(provenance_path.read_bytes()) == provenance, 'S129_REUSE_RECORD_DRIFT')
    else:
        observer.write(provenance_path, provenance)
    template = observer.make_request('gt06-s129-negative-01', BASE / 'controller_probe.py', ['--mode', 'exit0'])
    negatives = []
    for field in ('argv_sha256', 'python_sha256', 'launcher_sha256', 'observer_sha256'):
        bad = copy.deepcopy(template)
        bad[field] = '0' * 64
        with patch.object(observer, 'RetainedPopen') as launch:
            try:
                observer.observe(bad)
            except RuntimeError as error:
                negatives.append({'field': field, 'rejected': str(error), 'dispatched': launch.called})
            else:
                raise RuntimeError('S129_NEGATIVE_ACCEPTED')
            launch.assert_not_called()
    rows = [probe(mode, expected, args.attempt) for mode, expected in (('exit0', 0), ('exit7', 7), ('abrupt', 47), ('timeout', None))]
    scheduler_id = f'gt06-s129-scheduler-probe-{args.attempt:02d}'
    fixture = BASE / 'fixtures' / scheduler_id
    fixture.mkdir(exist_ok=False)
    request = observer.make_request(scheduler_id, BASE / 'controller_probe.py',
        ['--mode', 'exit0', '--fixture', str(fixture)])
    scheduler_request = BASE / f'request-{scheduler_id}.json'
    observer.write(scheduler_request, request)
    observer.need(observer.own_pins() == pins, 'S129_VALIDATION_SOURCE_DRIFT')
    elapsed = time.monotonic() - began
    observer.need(elapsed < 60, 'S129_VALIDATION_WALL_LIMIT')
    result = {'schema': 'HH-S129-NO-ENGINE-VALIDATION-1', 'status': 'PASS', 'rows': rows,
        'negative_pins': negatives, 'source_pins': pins, 'reuse_source_pins': REFERENCES,
        'scheduler_request_sha256': observer.sha(scheduler_request), 'scheduler_probe_run_id': scheduler_id,
        'validation_attempt': args.attempt,
        'elapsed_seconds': elapsed, 'engine_launched': False, 'jobs_created': False,
        'scheduler_registered': False, 'scheduler_dispatched': False,
        'limitations': ['Observer loss/receipt write failure remains UNKNOWN.',
            'Scheduled survival not exercised; prepared request is only a non-engine probe.',
            'No poweroff survival; no cleanup inference for unobserved descendants.',
            'Probe TerminateProcess exit is an injected fixture observation, not an S128 cause.'],
        'formal_acceptance': False, 'eligible_for_dataset': False}
    current_validation = BASE / 'validation.json'
    if current_validation.exists():
        archive = BASE / ('historical-validation-' + observer.sha(current_validation)[:16] + '.json')
        if not archive.exists():
            shutil.copyfile(current_validation, archive)
    observer.write(retained_source.parent / 'validation.json', result)
    temporary = BASE / f'.validation-{args.attempt:02d}.json'
    observer.write(temporary, result)
    os.replace(temporary, current_validation)
    print(json.dumps({'status': result['status'], 'elapsed_seconds': elapsed, 'launcher_exits': [0, 7, 47],
        'leaf_exits': [0, 0, 48, 48], 'timeout_status': rows[-1]['actual_launcher_exit'],
        'negative_checks': len(negatives), 'engine_launched': False}))


if __name__ == '__main__':
    main()
