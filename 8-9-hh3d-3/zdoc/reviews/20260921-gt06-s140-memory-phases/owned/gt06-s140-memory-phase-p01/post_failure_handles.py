"""S129 diagnostic observations after an original gate rejection; no launcher.

The caller owns process handles, durable writes and the external deadline.
Successful rows are published only after identity/cleanup/time validation.
The completion receipt is required before claiming the entire observation ran.
"""
from __future__ import annotations

from copy import deepcopy
import math
import ntpath
import re
import time

SCHEMA = 'S129.post-failure-observation.1'
OFFSETS = (0, 1, 3, 5)


class ObservationError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def need(condition, code):
    if not condition:
        raise ObservationError(code)


def _identity(value):
    need(isinstance(value, dict), 'S129_IDENTITY_SCHEMA')
    need(type(value.get('pid')) is int and 0 < value['pid'] < 0xffffffff,
         'S129_IDENTITY_PID')
    start = value.get('process_start')
    need(isinstance(start, str) and re.fullmatch(r'windows:[1-9][0-9]{0,19}', start)
         and int(start.split(':')[1]) <= 0xffffffffffffffff, 'S129_IDENTITY_START')
    result = {'pid': value['pid'], 'process_start': start}
    if 'executable' in value:
        executable = value['executable']
        need(isinstance(executable, str) and ntpath.isabs(executable)
             and '\0' not in executable, 'S129_IDENTITY_EXECUTABLE')
        result['executable'] = ntpath.normcase(ntpath.normpath(executable))
    return result


def validate_role_binding(binding, role, *observed, require_executable=False):
    """Pure PID/start join; compare every available executable identity.

    Counter-only host samples need not repeat executable. PSS identities must
    always supply it, including the first capture from a PID/start-only probe.
    """
    need(role in ('editor', 'host') and isinstance(binding, dict) and role in binding,
         'S129_ROLE_BINDING')
    expected = _identity(binding[role])
    for value in observed:
        actual = _identity(value)
        need(all(actual[key] == expected[key] for key in ('pid', 'process_start')),
             'S129_' + role.upper() + '_IDENTITY')
        if require_executable:
            need('executable' in actual, 'S129_' + role.upper() + '_EXECUTABLE_MISSING')
        if 'executable' in actual:
            need('executable' not in expected or actual['executable'] == expected['executable'],
                 'S129_' + role.upper() + '_EXECUTABLE')
            expected['executable'] = actual['executable']
    return expected


def validate_roles(binding, *, editor, host):
    """Pure joint-to-retained-role validation for both roles, not editor alone."""
    return {role: validate_role_binding(binding, role, identity)
            for role, identity in (('editor', editor), ('host', host))}


def probe_identity(probe):
    need(not getattr(probe, 'close_uncertain', False), 'S129_PROBE_CLOSE_UNCERTAIN')
    value = {'pid': getattr(probe, 'pid', None),
             'process_start': getattr(probe, 'process_start', None)}
    executable = getattr(probe, 'executable', None)
    if executable is not None:
        value['executable'] = str(executable)
    return _identity(value)


def validate_pss(binding, role, pss):
    """Validate the adapter's returned schema before any successful row write."""
    need(isinstance(pss, dict) and pss.get('status') == 'OBSERVED'
         and pss.get('binding_verified') is True
         and isinstance(pss.get('cleanup'), dict)
         and pss['cleanup'].get('all_released') is True
         and pss.get('errors') == [], 'S129_PSS_INCOMPLETE')
    return validate_role_binding(binding, role, pss.get('identity'),
                                 require_executable=True)


def sanitized_pss_result(pss):
    """Keep the adapter's redacted JSON fields, never arbitrary callback extras.

    PSS already omits object names, pointers and exception text. This projection
    preserves its UNKNOWN/cleanup evidence without adding unrecognized fields.
    """
    def fields(value, names):
        if not isinstance(value, dict):
            return None
        return {key: item for key in names if key in value
                for item in (value[key],)
                if item is None or type(item) in (str, int, bool)
                or type(item) is float and math.isfinite(item)}

    if not isinstance(pss, dict):
        return {'status': 'UNKNOWN', 'errors': [{'code': 'S129_PSS_RESULT_SCHEMA'}]}
    result = fields(pss, ('schema', 'status', 'binding_verified', 'capture_flags',
        'process_access_mask', 'handles_captured', 'observer_handle_count_before',
        'observer_handle_count_after', 'target_handle_count_before',
        'target_handle_count_after', 'executable_binding_source'))
    result.update(formal_acceptance=False, eligible_for_dataset=False)
    for key, names in (
        ('identity', ('pid', 'process_start', 'executable')),
        ('timing', ('started_utc', 'started_perf_ns', 'ended_utc', 'ended_perf_ns',
                    'capture_ms', 'walk_ms', 'total_ms')),
        ('budget', ('max_entries', 'max_total_ms', 'native_calls_interruptible',
                    'external_deadline_required')),
    ):
        if key in pss:
            result[key] = fields(pss[key], names)
    if isinstance(pss.get('errors'), list):
        result['errors'] = [fields(error, ('code', 'api', 'native_code')) for error in pss['errors']]
    cleanup = pss.get('cleanup')
    if isinstance(cleanup, dict):
        result['cleanup'] = fields(cleanup, ('all_released', 'prior_or_current_cleanup_held'))
        for resource in ('marker', 'snapshot', 'process_handle'):
            if resource in cleanup:
                result['cleanup'][resource] = fields(cleanup[resource],
                    ('attempted', 'native_code', 'success', 'outcome'))
        if isinstance(cleanup.get('held_resources'), list):
            result['cleanup']['held_resources'] = [name for name in cleanup['held_resources']
                if name in ('marker', 'snapshot', 'process_handle')]
    if isinstance(pss.get('entries'), list):
        result['entries'] = []
        for entry in pss['entries']:
            row = fields(entry, ('handle', 'flags', 'type', 'object_type', 'name_state',
                'name_length_bytes', 'name_sha256', 'name_hash_encoding', 'object_identity'))
            if row is not None:
                for key, names in (('process', ('pid', 'parent_pid', 'exit_status')),
                                   ('thread', ('pid', 'tid', 'exit_status', 'priority', 'base_priority'))):
                    if key in entry:
                        row[key] = fields(entry[key], names)
                result['entries'].append(row)
    if isinstance(pss.get('type_counts'), dict):
        result['type_counts'] = {key: value for key, value in pss['type_counts'].items()
            if isinstance(key, str) and (key == '<unavailable>'
                or re.fullmatch(r'[A-Za-z0-9_ .-]{1,128}', key)) and type(value) is int}
    if isinstance(pss.get('limitations'), list):
        result['limitations'] = [item for item in pss['limitations'] if isinstance(item, str)
            and re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', item)]
    return result


def validate_observation_packet(rows, receipt, *, binding, role):
    """Pure completion check; individual rows never prove the sequence completed.

    This is a diagnostic structural check, not a durable-write/hash verifier or
    formal benchmark acceptance. The caller supplies the expected frozen binding.
    """
    expected = validate_role_binding(binding, role)
    need(isinstance(rows, list) and len(rows) == len(OFFSETS), 'S129_PACKET_ROWS')
    need(isinstance(receipt, dict) and receipt.get('completed') is True
         and receipt.get('validated_offsets') == list(OFFSETS), 'S129_PACKET_INCOMPLETE')
    for value in [*rows, receipt]:
        need(isinstance(value, dict) and value.get('schema') == SCHEMA
             and value.get('role') == role and value.get('binding') == binding
             and value.get('formal_acceptance') is False
             and value.get('eligible_for_dataset') is False, 'S129_PACKET_BINDING')
    for offset, row in zip(OFFSETS, rows):
        elapsed = row.get('elapsed_seconds')
        need(type(row.get('offset_seconds')) is int and row['offset_seconds'] == offset
             and row.get('observation_validated') is True
             and type(elapsed) in (int, float) and offset <= elapsed < 8
             and isinstance(row.get('counters'), dict), 'S129_PACKET_ROW_INCOMPLETE')
        if offset in (0, 5):
            expected = validate_pss({role: expected}, role, row.get('pss'))
        else:
            need('pss' not in row, 'S129_PACKET_UNEXPECTED_PSS')
    return True


def _observe(role, probe, *, binding, sample, capture, write, check_stop, clock, sleep):
    started, rows, offset, pss = clock(), [], None, None
    prefix = 'post-failure-' + role
    try:
        binding = deepcopy(binding)
        expected = validate_role_binding(binding, role, probe_identity(probe))
        for offset in OFFSETS:
            pss = None
            check_stop()
            while True:
                remaining = offset - (clock() - started)
                if remaining <= 0:
                    break
                sleep(min(.05, remaining))
                check_stop()
            need(clock() - started < 8, 'S129_OBSERVATION_WALL_LIMIT')
            validate_role_binding({role: expected}, role, probe_identity(probe))
            before = sample(probe)
            if role == 'host':
                validate_role_binding({role: expected}, role, before.get('process'))
                counters = before['counters']
            else:
                counters = before
            need(isinstance(counters, dict), 'S129_COUNTERS_SCHEMA')
            row = {'schema': SCHEMA, 'role': role, 'offset_seconds': offset,
                   'binding': binding, 'counters': counters,
                   'formal_acceptance': False, 'eligible_for_dataset': False}
            if offset in (0, 5):
                pss = capture(probe)
                expected = validate_pss({role: expected}, role, pss)
                row['pss'] = pss
            check_stop()
            validate_role_binding({role: expected}, role, probe_identity(probe))
            elapsed = clock() - started
            need(elapsed < 8, 'S129_OBSERVATION_WALL_LIMIT')
            row.update(elapsed_seconds=elapsed, observation_validated=True)
            write(f'{prefix}-{offset:02d}.json', row)
            rows.append(row)
        receipt = {'schema': SCHEMA, 'role': role,
            'binding': binding, 'completed': True,
            'validated_offsets': [row['offset_seconds'] for row in rows],
            'formal_acceptance': False, 'eligible_for_dataset': False}
        validate_observation_packet(rows, receipt, binding=binding, role=role)
        write(prefix + '-complete.json', receipt)
        return rows
    except BaseException as error:
        if pss is not None:
            try:
                write(f'{prefix}-{offset:02d}-incomplete-pss.json', {
                    'schema': SCHEMA, 'role': role, 'binding': binding,
                    'offset_seconds': offset, 'completed': False, 'observation_validated': False,
                    'validated_offsets': [row['offset_seconds'] for row in rows],
                    'pss': sanitized_pss_result(pss), 'error_code': getattr(error, 'code', type(error).__name__),
                    'formal_acceptance': False, 'eligible_for_dataset': False})
            except BaseException:
                pass  # An evidence-write failure must not replace the observation failure.
        try:
            write(prefix + '-error.json', {'schema': SCHEMA, 'role': role,
                'binding': binding, 'completed': False, 'failed_offset_seconds': offset,
                'validated_offsets': [row['offset_seconds'] for row in rows],
                'error_code': getattr(error, 'code', type(error).__name__),
                'formal_acceptance': False, 'eligible_for_dataset': False})
        except BaseException:
            pass  # A failed receipt is a gap; preserve the initiating exception.
        raise


def observe(probe, *, binding, sample_editor, capture, write, check_stop,
            clock=time.monotonic, sleep=time.sleep):
    return _observe('editor', probe, binding=binding, sample=sample_editor,
                    capture=capture, write=write, check_stop=check_stop, clock=clock, sleep=sleep)


def observe_host(probe, *, binding, sample_host, capture, write, check_stop,
                 clock=time.monotonic, sleep=time.sleep):
    return _observe('host', probe, binding=binding, sample=sample_host,
                    capture=capture, write=write, check_stop=check_stop, clock=clock, sleep=sleep)


class GateObserver:
    def __init__(self, *, original, boundary, limit, stop_at_boundary, binding,
                 probe, observe_fn, write, error_record, host_probe, observe_host_fn, check_stop):
        need(type(stop_at_boundary) is bool, 'S129_BOUNDARY_FLAG')
        need(type(limit) is int and limit > 0, 'S129_BOUNDARY_LIMIT')
        self.original, self.boundary, self.limit = original, boundary, limit
        self.stop_at_boundary = stop_at_boundary
        self.binding, self.probe, self.observe_fn = binding, probe, observe_fn
        self.host_probe, self.observe_host_fn = host_probe, observe_host_fn
        self.check_stop = check_stop
        self.write, self.error_record, self.gates = write, error_record, []

    def __call__(self, sample, baseline):
        try:
            result = self.original(sample, baseline)
        except BaseException as primary:
            dispositions = {role: {'disposition': 'skipped', 'reason': 'PREFLIGHT_NOT_COMPLETED'}
                            for role in ('editor', 'host')}
            supplemental_errors, dispatch_completed = [], False
            try:
                # Record the original even when resolving supplemental binding fails.
                self.write('original-gate-failure.json', {'schema': SCHEMA,
                    'sample': sample, 'baseline': baseline,
                    'primary': self.error_record([('original_gate', primary)]),
                    'formal_acceptance': False, 'eligible_for_dataset': False})
                binding = self.binding(sample)
                editor_probe, host_probe = self.probe(), self.host_probe()
                identities = validate_roles(binding, editor=probe_identity(editor_probe),
                                             host=probe_identity(host_probe))
                self.write('original-gate-binding.json', {'schema': SCHEMA,
                    'binding': binding, 'validated_identities': identities,
                    'formal_acceptance': False, 'eligible_for_dataset': False})
                if getattr(primary, 'code', None) == 'CAMPAIGN_RETAINED_COUNTER_GROWTH':
                    stop_rejected = False
                    for role, retained, observer in (('editor', editor_probe, self.observe_fn),
                                                     ('host', host_probe, self.observe_host_fn)):
                        value = sample['memory'][role]['held_handles']['value']
                        reference = baseline[role]['held_handles']['value']
                        if value <= reference:
                            dispositions[role] = {'disposition': 'skipped', 'reason': 'COUNTER_NOT_GROWING'}
                            continue
                        if not stop_rejected:
                            try:
                                self.check_stop()
                            except BaseException as stopped:
                                supplemental_errors.append((role + '_stop_check', stopped))
                                stop_rejected = True
                        if stop_rejected:
                            dispositions[role] = {'disposition': 'skipped', 'reason': 'STOP_CHECK_REJECTED'}
                            continue
                        try:
                            need(observer is not None, 'S129_' + role.upper() + '_OBSERVER_UNWIRED')
                            observer(retained, binding)
                            dispositions[role] = {'disposition': 'observed'}
                        except BaseException as supplemental:
                            supplemental_errors.append((role, supplemental))
                            dispositions[role] = {'disposition': 'failed',
                                'error_code': getattr(supplemental, 'code', type(supplemental).__name__)}
                else:
                    dispositions = {role: {'disposition': 'skipped', 'reason': 'ORIGINAL_GATE_NOT_HANDLE_GROWTH'}
                                    for role in dispositions}
                dispatch_completed = True
            except BaseException as supplemental:
                supplemental_errors.append(('supplemental', supplemental))
            if supplemental_errors:
                try:
                    self.write('post-failure-error.json', {'schema': SCHEMA, 'completed': False,
                        'errors': self.error_record(supplemental_errors),
                        'formal_acceptance': False, 'eligible_for_dataset': False})
                except BaseException:
                    pass
            try:
                self.write('post-failure-roles.json', {'schema': SCHEMA, 'completed': False,
                    'observation_validated': False, 'role_dispatch_completed': dispatch_completed,
                    'roles': dispositions, 'formal_acceptance': False, 'eligible_for_dataset': False})
            except BaseException:
                pass
            raise
        self.gates.append({'index': sample['index'], 'original_gate': 'PASSED'})
        if self.stop_at_boundary and len(self.gates) == self.limit:
            raise self.boundary('S129_PREFIX_BOUNDARY')
        return result
