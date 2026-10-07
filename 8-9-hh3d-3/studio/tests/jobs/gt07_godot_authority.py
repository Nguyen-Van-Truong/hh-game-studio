"""M2 Godot scenarios: real grants, clocks, editor and publication journal.

Delay the return from a durable commit; separately revoke a second writer
after its actual editor mutation and before commit. UNKNOWN is not an ACK.
"""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import threading
import time

from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.host.jobs.native_dispatch import GodotOwnerBinding, NativeDispatchError
from studio.protocol.core import Response, Status, ValidationError, canonical_bytes, parse_json


class AuthorityProbeError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def need(value, code):
    if not value:
        raise AuthorityProbeError(code)


def request_for_case(recipe, owner, before, lease, default_script, *, revoked=False):
    request = recipe('scene.node.update', before=before, lease=lease,
        contract=owner.contract, default_script=default_script,
        now_ms=epoch_ms(), project_id=owner.project_id)
    payload = parse_json(canonical_bytes(request.payload))
    payload['changes']['position'] = [7, 8, 9] if revoked else [4, 5, 6]
    return replace(request, command_id='m2.godot.revoked' if revoked else 'm2.godot.late',
        payload=payload, payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest())


def wait_expiry(expires_ms):
    # The caller may pass the ordinary native lease, which can have tens of
    # seconds left after a cold validator. This bound is only a local wait
    # safety cap; expiry itself is always checked with the real wall clock.
    bound = time.monotonic() + 120
    while epoch_ms() <= expires_ms:
        need(time.monotonic() < bound, 'M2_GODOT_EXPIRY_WAIT_BOUND')
        time.sleep(min(.05, max(.001, (expires_ms - epoch_ms()) / 1000)))


def acquire(owner, options, *, ttl_ms=5000):
    # Public FIFO route, never reconstructed or manually installed authority.
    return owner.lease({'project_id': owner.project_id, 'access': 'write', 'ttl_ms': ttl_ms},
                       **options)


@contextmanager
def delayed_commit(owner, lease, contender_options, timing):
    original = owner._journal.edit_committed
    def delayed(*args, **kwargs):
        result = original(*args, **kwargs)
        timing['terminal_commit_ms'] = epoch_ms()
        wait_expiry(lease['expires_ms'])
        attempts = []
        def contender():
            try:
                acquire(owner, contender_options)
            except SafetyViolation as error:
                attempts.append(error.code)
            except BaseException as error:
                attempts.append(type(error).__name__)
            else:
                attempts.append('UNEXPECTED_GRANT')
        thread = threading.Thread(target=contender, daemon=True)
        thread.start()
        thread.join(1)
        need(not thread.is_alive() and attempts == ['GODOT_LEASE_BUSY'],
             'M2_GODOT_OVERLAPPING_WRITER_NOT_BLOCKED')
        timing['contender_denial'] = attempts[0]
        timing['reply_release_ms'] = epoch_ms()
        return result
    owner._journal.edit_committed = delayed
    try:
        yield
    finally:
        owner._journal.edit_committed = original


@contextmanager
def revoked_edit(owner, credential, proof):
    original = owner._editor.apply_edit
    def apply(*args, **kwargs):
        result = original(*args, **kwargs)
        proof['native_observation'] = owner._editor.observation(result)
        proof['native_result_ms'] = epoch_ms()
        proof['revocation'] = owner.sessions.revoke(credential)
        need(proof['revocation'].get('draining') is True,
             'M2_GODOT_REVOKE_PHASE_UNPROVEN')
        return result
    owner._editor.apply_edit = apply
    try:
        yield
    finally:
        owner._editor.apply_edit = original


@contextmanager
def observed_edits(owner, calls):
    original = owner._editor.apply_edit
    def apply(intent):
        call = {'command_id': intent.command_id, 'request_digest': intent.request_digest,
                'started_ms': epoch_ms()}
        calls.append(call)
        result = original(intent)
        call['observation'] = owner._editor.observation(result)
        call['completed_ms'] = epoch_ms()
        return result
    owner._editor.apply_edit = apply
    try:
        yield
    finally:
        owner._editor.apply_edit = original


def verify_edits(calls, final):
    need([row['command_id'] for row in calls] == ['m2.godot.late', 'm2.godot.revoked']
         and all('observation' in row and 'completed_ms' in row for row in calls),
         'M2_GODOT_EFFECT_COUNT_UNPROVEN')
    first, second = [row['observation'] for row in calls]
    need(first['semantic_revision'] == second['before_revision']
         and first['before_revision'] != first['semantic_revision']
         and second['before_revision'] != second['semantic_revision']
         and second['semantic_revision'] == final['revision']
         and all(row['history_id_before'] == row['history_id_after'] == final['history_id']
                 for row in (first, second)), 'M2_GODOT_EFFECT_CHAIN_UNPROVEN')


def godot_cases(owner, dispatch, recipe, credential, initial_lease, *, default_script):
    calls = []
    with observed_edits(owner, calls):
        proof = _godot_cases(owner, dispatch, recipe, credential, initial_lease,
                             default_script=default_script)
    verify_edits(calls, proof['final_readback'])
    proof['native_effects_in_cases'] = len(calls)
    proof['native_edit_calls'] = calls
    return proof


def _godot_cases(owner, dispatch, recipe, credential, initial_lease, *, default_script):
    # The base queue operation may spend tens of seconds in a cold validator;
    # its credential can therefore be close to expiry even though the initial
    # lease was correctly admitted. Authority cases use a new public session
    # after that operation, while retaining the original credential only as
    # historical input. This avoids a false three-second lease horizon.
    fresh = owner.sessions.issue(ttl_ms=900_000)
    other = owner.sessions.issue(ttl_ms=900_000)
    options = {'authorization': 'Bearer ' + fresh.bearer,
               'catalog_digest': owner.contract.CATALOG_DIGEST}
    other_options = dict(options, authorization='Bearer ' + other.bearer)
    wait_expiry(initial_lease['expires_ms'])

    def admit(lease, auth, revoked=False):
        request = request_for_case(recipe, owner, owner.inspect(), lease, default_script,
                                   revoked=revoked)
        binding = GodotOwnerBinding.create(owner, body=request.as_dict(), **auth)
        dispatch.register(binding)
        row = dispatch.enqueue(binding)
        ticket = dispatch.reserve()
        need(ticket is not None, 'M2_GODOT_RESERVATION_MISSING')
        return request, binding, row, ticket

    # The authority case deliberately leaves enough deadline for the real
    # editor plus validator startup. Reply delay still crosses this lease's
    # expiry in delayed_commit; a 5s lease expires before native edit returns
    # on a cold Docker/Godot host and creates a false pre-effect UNKNOWN.
    # FIFO admission can take about a minute on a cold validator. Keep the
    # maximum catalog lease so the 29-second edit deadline still has headroom;
    # delayed_commit waits for this same lease's real expiry before replying.
    lease = acquire(owner, options, ttl_ms=90_000)
    timing = {'lease_acquired_ms': epoch_ms(),
              'lease_expires_ms': lease['expires_ms']}
    timing['lease_remaining_ms_at_acquire'] = lease['expires_ms'] - timing['lease_acquired_ms']
    request, binding, row, ticket = admit(lease, options)
    timing['admitted_ms'] = epoch_ms()
    timing['deadline_ms'] = request.deadline_ms
    timing['lease_remaining_ms_at_admit'] = lease['expires_ms'] - timing['admitted_ms']
    with delayed_commit(owner, lease, other_options, timing):
        late = dispatch.advance(ticket)
    try:
        looked_up = binding.lookup()
    except BaseException as error:
        raise AuthorityProbeError('M2_GODOT_LATE_LOOKUP_EXCEPTION:' + type(error).__name__ + ':' + str(error)) from error
    try:
        broker_state = dispatch.queue.broker.lookup(row.job.job_id).state
    except BaseException as error:
        raise AuthorityProbeError('M2_GODOT_LATE_BROKER_EXCEPTION:' + type(error).__name__ + ':' + str(error)) from error
    need(late.status is Status.COMMITTED and looked_up == late
         and broker_state == 'COMMITTED',
         'M2_GODOT_LATE_RECEIPT_LOST:' + repr({
             'late': late.as_dict(), 'lookup': looked_up.as_dict(),
             'broker_state': broker_state, 'timing': timing}))
    need(timing['terminal_commit_ms'] <= request.deadline_ms <= lease['expires_ms']
         < timing['reply_release_ms'], 'M2_GODOT_LATE_TIMING_UNPROVEN')
    state = owner.inspect()
    need(next(item for item in state['state']['nodes'] if item['stable_id'] == 'root')['position']
         == [4, 5, 6], 'M2_GODOT_LATE_READBACK_MISMATCH')
    need(owner.submit(request.as_dict(), **options) == late
         and owner.inspect() == state, 'M2_GODOT_LATE_RETRY_NOT_HISTORICAL')
    fresh = request_for_case(recipe, owner, state, lease, default_script)
    fresh = replace(fresh, command_id='m2.godot.expired')
    try:
        owner.submit(fresh.as_dict(), **options)
    except (ValidationError, SafetyViolation) as error:
        need(error.code == 'GODOT_DEADLINE_EXPIRED', 'M2_GODOT_EXPIRED_WRONG_REASON')
        expiry_code = error.code
    else:
        raise AuthorityProbeError('M2_GODOT_EXPIRED_FRESH_ADMITTED')
    need(fresh.command_id not in owner._jobs and owner.inspect() == state,
         'M2_GODOT_EXPIRED_FRESH_EFFECT')

    second = owner.sessions.issue(ttl_ms=900_000)
    other_options = dict(options, authorization='Bearer ' + second.bearer)
    next_lease = acquire(owner, other_options, ttl_ms=90_000)
    need(next_lease['fencing_epoch'] > lease['fencing_epoch'], 'M2_GODOT_FENCE_DID_NOT_ADVANCE')
    request2, binding2, row2, ticket2 = admit(next_lease, other_options, revoked=True)
    proof = {}
    selection = owner._journal.selection_facts()
    with revoked_edit(owner, second, proof):
        try:
            dispatch.advance(ticket2)
        except SafetyViolation as error:
            need(error.code == 'AUTH_REQUIRED', 'M2_GODOT_REVOKED_COLLECTION_UNEXPECTED')
        else:
            raise AuthorityProbeError('M2_GODOT_REVOKED_COLLECTION_ACCEPTED')
    for action in (lambda: binding2.lookup(),
                   lambda: owner.submit(request2.as_dict(), **other_options)):
        try:
            action()
        except SafetyViolation as error:
            need(error.code == 'AUTH_REQUIRED', 'M2_GODOT_REVOKED_AUTH_UNEXPECTED')
        else:
            raise AuthorityProbeError('M2_GODOT_REVOKED_CALL_ACCEPTED')
    try:
        dispatch.advance(ticket2)
    except NativeDispatchError as error:
        need(error.code == 'NATIVE_RESERVATION_REQUIRED', 'M2_GODOT_REPLAY_REFUSAL_UNEXPECTED')
    else:
        raise AuthorityProbeError('M2_GODOT_REVOKED_EFFECT_REPLAYED')
    # Supervisor facts never impersonate delivery to the revoked credential.
    terminal = owner._journal.lookup(request2.command_id, request2.digest)
    raw = owner._journal.lookup_response(request2.command_id, request2.digest)
    retained = Response.from_dict(parse_json(raw))
    need(terminal['phase'] == 'UNKNOWN' and retained.status is Status.UNKNOWN
         and retained.postconditions.get('public_ack') is False
         and retained.postconditions.get('next_action') == 'lookup.reconcile',
         'M2_GODOT_REVOKE_MISSING_UNCERTAINTY')
    final = owner.inspect()
    root = next(item for item in final['state']['nodes'] if item['stable_id'] == 'root')
    native = proof['native_observation']
    need(root['position'] == [7, 8, 9] and final['history_id'] == state['history_id']
         and native['history_id_after'] == final['history_id']
         and native['semantic_revision'] == final['revision']
         and owner._journal.selection_facts() == selection
         and final['working_files'] == state['working_files'],
         'M2_GODOT_DUPLICATE_OR_LOST_EFFECT')
    final_row = dispatch.queue.broker.lookup(row2.job.job_id)
    need(final_row.state == 'RESERVED' and final_row.fence == ticket2.fence,
         'M2_GODOT_REVOKED_RESERVATION_NOT_RETAINED')
    return {'delay_boundary': 'durable_commit_return', 'reply_delay_injected': True,
        'real_clock_expiry': timing, 'late_receipt': late.as_dict(),
        'expired_fresh_code': expiry_code,
        'first_fence': lease['fencing_epoch'], 'second_fence': next_lease['fencing_epoch'],
        'revoke_boundary': 'native_edit_return_before_commit', 'revocation': proof,
        'retained_receipt': retained.as_dict(), 'retained_receipt_scope': 'supervisor-journal-only',
        'revoked_queue_state': final_row.state,
        'final_readback': final, 'public_ack': False}
