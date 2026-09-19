# S122 bounded diagnostic failure analysis

AUTHORITY=0; diagnostic-only; excluded from F13/F14 and GT06 acceptance.

The fresh S122 launch `gt06-s122-lookup-repair-01` stopped at batch 0 on `HOST_DIAGNOSTICS`. The command-lane status gap was only 13.171 ms and HTTP transport failures were zero. Raw evidence is retained under `studio/.local/reviews/gt06-s122-lookup-repair-01`.

A local one-batch reproduction captured the hidden diagnostic as `TRANSPORT_FAILED`: the S122 candidate called `_lookup(command_id, fast_pending=False)` from `_existing`, while the benchmark phase recorder subclass overrides `_lookup(command_id)` with the prior one-argument contract. The resulting `TypeError` was converted by the transport boundary into `TRANSPORT_FAILED`, so S122 did not test the lookup boundary.

The repair was narrowed to use the normal lookup path. This remains safe because the pending snapshot is published only after durable journal admission. The focused replay group passed 93 tests, py_compile and diff checks passed, and a local diagnostic completed 10 commands with two effects and only the three expected invalid-payload diagnostics.

No claim is made about leak, root cause, or formal performance.
