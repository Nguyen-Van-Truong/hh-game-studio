# S150 event quiescence review

## Result

S150 is a read-only, AUTHORITY=0 diagnostic. The child completed all eleven
host-only 1000-command batches and kept the original host counters within
their gate:

| checkpoint | handle count | Event | File | Thread | Semaphore |
| --- | ---: | ---: | ---: | ---: | ---: |
| batch 4 baseline | 173 | 23 | 14 | 3 | 48 |
| batch 9 quiet checkpoint | 173 | 23 | 14 | 3 | 48 |
| batch 10 terminal checkpoint | 173 | 23 | 14 | 3 | 48 |

The quiet census was captured after the bounded 250 ms scheduler-yield
interval. The final census was captured at batch 10 after the normal command
completion path. RSS decreased from about 49.0 MiB at the batch-4 baseline to
about 43.2 MiB at batch 10. Every PSS census reported target counts 173 before
and after capture, all observer resources released, and no held resources.

The evidence therefore does not reproduce the S147/S149 Event 23 to 24
transition. It supports the narrower conclusion that the extra unnamed Event
was transient, run-specific, or boundary-sensitive. It does not identify an
owner and does not prove that the request-thread response-drain hypothesis is
correct. PSS still reports unnamed Event rows with object_identity UNKNOWN,
and numeric handle values cannot establish kernel object identity.

## Immediate versus quiet qualification

S150's available pair is a quiet batch-9 census and a terminal batch-10
census, both stable at Event 23. The child script did not emit a separate
same-batch immediate checkpoint at batch 9 when the retained-counter gate was
green; it emitted only the 09-quiet checkpoint. Batch 10 then emitted its
normal checkpoint. Consequently, the package demonstrates stability across a
quiet interval and the following batch boundary, but it is not a strict
same-command immediate-versus-quiet A/B pair. This limitation must remain
visible in any attribution claim.

## Terminal and acceptance status

The workload itself reached batch 10, but the owning wrapper ended with
S149_OUTER_LIMIT and helper exit code 2. The result has no captured target
process-exit record, no child summary, and no child-cleanup record. Wrapper
and probe handles were released and the job reported zero active work, yet
the missing process-exit evidence prevents treating the package as a formal
PASS. The original retained-counter gate was not relaxed or bypassed.

## Retry recommendation

Do not launch an Event-focused formal retry solely to chase the S147/S149
extra Event. S150's fresh process remained at 173 handles through the quiet
checkpoint and terminal batch, so the attribution question is currently
non-reproducing. Preserve the S147/S149 failures and the GT06 hold.

If GT06 later requires a formal host campaign for package completeness, use a
fresh run with the original counter, status-gap, process-exit, cleanup, and
source-freeze gates unchanged. The orchestration timeout and missing exit
publication must be resolved before that run; changing the threshold,
subtracting observer cost, or treating helper exit 2 as success would make
the retry invalid. No source repair or acceptance waiver is justified by
S150.
