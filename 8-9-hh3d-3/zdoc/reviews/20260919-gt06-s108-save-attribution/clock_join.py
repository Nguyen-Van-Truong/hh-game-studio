"""Conservative host/native clock join; pure derived observations, no engine I/O.

GetThreadTimes deltas below cover enclosing sampled observation windows, not
an exact call's CPU time. No GPU/disk/lock/scheduler attribution is inferred.
"""
from __future__ import annotations


class JoinError(ValueError):
    pass


def integer(value, name):
    if type(value) is not int or value < 0:
        raise JoinError('S108_JOIN_INTEGER_' + name)
    return value


def offset_interval(anchors):
    """h = n + offset. ACK publish-before <= native ACK <= receipt-after.

    Two microseconds of outward rounding cover integer-microsecond clock
    conversion. This is not an overhead subtraction or latency gate allowance.
    The caller must supply only hash/identity-validated original ACK receipts.
    """
    if not anchors:
        raise JoinError('S108_JOIN_MISSING_ANCHOR')
    lows, highs = [], []
    for anchor in anchors:
        if anchor.get('kind') != 'ACK':
            raise JoinError('S108_JOIN_ANCHOR_KIND')
        before = integer(anchor.get('host_before_publish_us'), 'before_publish')
        after = integer(anchor.get('host_after_receipt_us'), 'after_receipt')
        native = integer(anchor.get('native_observed_us'), 'native_observed')
        if before > after:
            raise JoinError('S108_JOIN_ANCHOR_ORDER')
        lows.append(before - native - 2)
        highs.append(after - native + 2)
    low, high = max(lows), min(highs)
    if low > high:
        raise JoinError('S108_JOIN_CLOCK_INTERVAL_DISJOINT')
    return low, high


def join_interval(native_start_us, native_end_us, anchors, samples):
    """Return an enclosing observed CPU delta, or an explicit UNKNOWN gap.

    Expected samples are normalized from one retained thread's capture:
    {host_before_ns,host_after_ns,kernel_100ns,user_100ns,tid,thread_created_100ns}.
    Never combine batches/threads based only on a numeric thread ID.
    """
    base = {'formal_acceptance':False,'eligible_for_dataset':False,
            'cpu_scope':'ENCLOSING_SAMPLED_OBSERVATION_WINDOW',
            'exact_call_cpu_available':False,'wait_cause':'UNKNOWN',
            'quantization':'GetThreadTimes accounting is not exact instantaneous execution timing',
            'overhead_subtracted':False}
    try:
        start = integer(native_start_us, 'native_start')
        end = integer(native_end_us, 'native_end')
        if start >= end:
            raise JoinError('S108_JOIN_NATIVE_ORDER')
        low, high = offset_interval(anchors)
        earliest_ns, latest_ns = (start + low)*1000, (end + high)*1000
        if not samples:
            raise JoinError('S108_JOIN_NO_SAMPLES')
        identity = (samples[0].get('tid'), samples[0].get('thread_created_100ns'))
        integer(identity[0], 'tid')
        integer(identity[1], 'thread_created_100ns')
        if min(identity) <= 0:
            raise JoinError('S108_JOIN_IDENTITY')
        previous = None
        for sample in samples:
            if (sample.get('tid'), sample.get('thread_created_100ns')) != identity:
                raise JoinError('S108_JOIN_THREAD_DRIFT')
            for key in ('host_before_ns','host_after_ns','kernel_100ns','user_100ns'):
                integer(sample.get(key), key)
            if sample['host_before_ns'] > sample['host_after_ns']:
                raise JoinError('S108_JOIN_SAMPLE_ORDER')
            if previous and (sample['host_before_ns'] < previous['host_after_ns'] or
                             sample['kernel_100ns'] < previous['kernel_100ns'] or
                             sample['user_100ns'] < previous['user_100ns']):
                raise JoinError('S108_JOIN_COUNTER_OR_CLOCK_REGRESSION')
            previous = sample
        before = [(i,s) for i,s in enumerate(samples) if s['host_after_ns'] <= earliest_ns]
        after = [(i,s) for i,s in enumerate(samples) if s['host_before_ns'] >= latest_ns]
        if not before or not after:
            raise JoinError('S108_JOIN_ENCLOSING_SAMPLES_MISSING')
        first_i, first = before[-1]
        last_i, last = after[0]
        if first_i >= last_i:
            raise JoinError('S108_JOIN_ENVELOPE_ORDER')
        delta_kernel = last['kernel_100ns'] - first['kernel_100ns']
        delta_user = last['user_100ns'] - first['user_100ns']
        return dict(base, status='OBSERVED_ENVELOPE', native_start_us=start,native_end_us=end,
                    native_wall_us=end-start,offset_low_us=low,offset_high_us=high,
                    offset_uncertainty_us=high-low,
                    host_interval_earliest_ns=earliest_ns,host_interval_latest_ns=latest_ns,
                    first_sample=first_i,last_sample=last_i,
                    enclosing_observation_start_ns=first['host_before_ns'],
                    enclosing_observation_end_ns=last['host_after_ns'],
                    enclosing_observation_wall_ns=last['host_after_ns']-first['host_before_ns'],
                    kernel_delta_100ns=delta_kernel,user_delta_100ns=delta_user,
                    cpu_delta_100ns=delta_kernel+delta_user,
                    tid=identity[0],thread_created_100ns=identity[1])
    except JoinError as error:
        return dict(base,status='UNKNOWN',reason=str(error))
