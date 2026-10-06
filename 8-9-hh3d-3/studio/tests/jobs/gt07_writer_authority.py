"""M2 Blender scenario: real effects, delayed replies, real-clock authority loss.

Only reply delivery is delayed by this fixture. The production absolute native
deadline, result bytes, session checks and durable collection are unchanged.
Ledger inspection after revoke is supervisor evidence, never a public lookup.
"""
from dataclasses import replace
import hashlib
import threading
import time

from studio.host.blender import client_write_catalog as catalog
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import epoch_ms
from studio.host.jobs.native_dispatch import BlenderOwnerBinding, NativeDispatchError
from studio.protocol.core import Response, Status, canonical_bytes, parse_json


def need(value, code):
    if not value:
        raise RuntimeError(code)


def final_inspect_command():
    # This is a private native ID, whose syntax differs from public IDs.
    return {'schema': catalog.queue.SCHEMA, 'command_id': 'm2-final-inspect',
            'operation': 'scene.inspect', 'expected_revision': None,
            'expected_context': None, 'payload': {}}


def validate_native_recipes():
    command = final_inspect_command()
    need(catalog.queue.parse(canonical_bytes(command)) == command,
         'M2_FINAL_INSPECT_SCHEMA_INVALID')


def blender_cases(owner, gui, dispatch, queue, writer, request_for, *, lease_ms=5000):
    """Use two credentials against the same registered Blender session."""
    validate_native_recipes()
    other = owner.sessions.issue(operations=catalog.EDIT_OPERATIONS |
        {catalog.READ, 'control.lookup', 'control.stop'}, ttl_ms=60000)
    kw = {'authorization': 'Bearer ' + writer.bearer, 'catalog_digest': owner.catalog_digest}
    other_kw = dict(kw, authorization='Bearer ' + other.bearer)
    original = gui.execute
    observed = []

    def acquire(options):
        return owner.lease({'project_id': owner.project_id, 'access': 'write',
                            'ttl_ms': lease_ms}, **options)

    def admit(lease, options, *, operation, command_id):
        request = request_for(before=parse_json(owner._read_owner._baseline), lease=lease,
            project_id=owner.project_id, now_ms=epoch_ms(), operation=operation)
        if operation == 'mesh.create_box':
            payload = parse_json(canonical_bytes(request.payload))
            payload['arguments']['object_id'] = 'authority_second_box'
            request = replace(request, payload=payload,
                payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest())
        request = replace(request, command_id=command_id)
        binding = BlenderOwnerBinding.create(owner, body=request.as_dict(), **options)
        dispatch.register(binding)
        row = dispatch.enqueue(binding)
        ticket = dispatch.reserve()
        need(ticket is not None, 'M2_RESERVATION_MISSING')
        return request, binding, row, ticket

    lease = acquire(kw)
    request, binding, row, ticket = admit(lease, kw, operation='object.transform.set',
                                         command_id='M2LateCompletion')
    timing = {'lease_expires_ms': lease['expires_ms'], 'deadline_ms': request.deadline_ms}

    def delayed(command, **options):
        result = original(command, **options)
        need(result.get('state') == 'COMPLETED', 'M2_NATIVE_EFFECT_INCOMPLETE')
        timing['native_result_ms'] = epoch_ms()
        observed.append(result)
        # Do not move the authority clock or renew the lease/deadline.
        until = time.monotonic() + lease_ms / 1000 + 1
        while epoch_ms() <= lease['expires_ms']:
            need(time.monotonic() < until, 'M2_EXPIRY_WAIT_BOUND')
            time.sleep(min(.05, max(.001, (lease['expires_ms'] - epoch_ms()) / 1000)))
        timing['reply_release_ms'] = epoch_ms()
        # A different OS thread cannot acquire through the active admission
        # gate even though the original lease is now expired.
        attempts = []
        def contender():
            try:
                acquire(other_kw)
            except SafetyViolation as error:
                attempts.append(error.code)
            except BaseException as error:
                attempts.append(type(error).__name__)
            else:
                attempts.append('UNEXPECTED_GRANT')
        contender_thread = threading.Thread(target=contender, daemon=True)
        contender_thread.start()
        contender_thread.join(1)
        need(not contender_thread.is_alive() and attempts == ['BLENDER_CLIENT_BUSY'],
             'M2_OVERLAPPING_WRITER_NOT_BLOCKED')
        timing['contender_denial'] = attempts[0]
        return result

    gui.execute = delayed
    try:
        late = dispatch.advance(ticket)
    finally:
        gui.execute = original
    need(late.status is Status.COMMITTED and binding.lookup() == late
         and queue.broker.lookup(row.job.job_id).state == 'COMMITTED', 'M2_LATE_RECEIPT_LOST')
    need(timing['native_result_ms'] <= timing['deadline_ms'] <= timing['lease_expires_ms']
         < timing['reply_release_ms'], 'M2_LATE_TIMING_UNPROVEN')
    need(owner.submit(request.as_dict(), **kw) == late and len(observed) == 1,
         'M2_LATE_RETRY_NOT_HISTORICAL')
    current_before = parse_json(owner._read_owner._baseline)
    stale_request = request_for(before=current_before, lease=lease,
        project_id=owner.project_id, now_ms=epoch_ms(), operation='object.transform.set')
    stale_request = replace(stale_request, command_id='M2ExpiredFresh')
    stale = stale_request.as_dict()
    rejected = owner.submit(stale, **kw)
    need(rejected.status is Status.REJECTED and len(observed) == 1,
         'M2_EXPIRED_WRITER_ADMITTED')

    next_lease = acquire(other_kw)
    need(next_lease['fencing_epoch'] > lease['fencing_epoch'], 'M2_FENCE_DID_NOT_ADVANCE')
    request2, binding2, row2, ticket2 = admit(next_lease, other_kw,
        operation='mesh.create_box', command_id='M2RevokedCompletion')
    revocation = {}
    def revoked(command, **options):
        result = original(command, **options)
        need(result.get('state') == 'COMPLETED', 'M2_NATIVE_EFFECT_INCOMPLETE')
        observed.append(result)
        revocation.update(owner.sessions.revoke(other))
        need(revocation.get('write_phase') == 'DISPATCHING'
             and revocation.get('write_draining') is True, 'M2_REVOKE_PHASE_UNPROVEN')
        return result
    gui.execute = revoked
    try:
        try:
            dispatch.advance(ticket2)
        except SafetyViolation as error:
            need(error.code == 'AUTH_REQUIRED', 'M2_REVOKED_COLLECTION_UNEXPECTED')
        else:
            raise RuntimeError('M2_REVOKED_COLLECTION_ACCEPTED')
    finally:
        gui.execute = original
    for action in (lambda: binding2.lookup(),
                   lambda: owner.submit(request2.as_dict(), **other_kw)):
        try:
            action()
        except SafetyViolation as error:
            need(error.code == 'AUTH_REQUIRED', 'M2_REVOKED_AUTH_UNEXPECTED')
        else:
            raise RuntimeError('M2_REVOKED_CALL_ACCEPTED')
    try:
        dispatch.advance(ticket2)
    except NativeDispatchError as error:
        need(error.code == 'NATIVE_RESERVATION_REQUIRED', 'M2_REPLAY_REFUSAL_UNEXPECTED')
    else:
        raise RuntimeError('M2_REVOKED_EFFECT_REPLAYED')
    private = parse_json(catalog.translate(request2, binding=owner._ledger.binding,
                                           session_id=other.session_id))
    # Reconstruct from the actual journal under its own OS guard, after all
    # write phases have ended. No new public grant impersonates this session.
    with owner._ledger._journal._writer_lock():
        owner._ledger._journal._reload()
        terminal = owner._ledger._journal._state()[private['command_id']]
    retained = Response.from_dict(parse_json(terminal['response']))
    need(retained.status is Status.COMMITTED and len(observed) == 2,
         'M2_REVOKE_LOST_HISTORICAL_TRUTH')
    current = original(final_inspect_command())
    scene = current.get('result')
    need(current.get('state') == 'COMPLETED'
         and scene == retained.postconditions['observation']['scene'], 'M2_FINAL_READBACK_CHANGED')
    objects = scene['snapshot']['objects']
    need(sorted(item['object_id'] for item in objects) == ['authority_second_box', 'queue_probe_box']
         and next(item for item in objects if item['object_id'] == 'queue_probe_box')['location'] == [3, 4, 5],
         'M2_DUPLICATE_OR_LOST_EFFECT')
    final = queue.broker.lookup(row2.job.job_id)
    need(final.state == 'RESERVED' and final.fence == ticket2.fence,
         'M2_REVOKED_RESERVATION_NOT_RETAINED')
    return {'reply_delay_injected': True, 'real_clock_expiry': timing,
            'late_receipt': late.as_dict(), 'expired_fresh_status': rejected.status.value,
            'first_fence': lease['fencing_epoch'], 'second_fence': next_lease['fencing_epoch'],
            'revocation': revocation, 'retained_receipt': retained.as_dict(),
            'retained_receipt_scope': 'supervisor-journal-only',
            'revoked_queue_state': final.state, 'native_results': observed,
            'final_readback': current, 'native_effects_in_cases': 2,
            'public_ack': False}, row2
