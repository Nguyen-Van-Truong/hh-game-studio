# S46 native managed-service diagnostic

AUTHORITY=0. No acceptance claim. The native C program is a fixed diagnostic
client, not the production typed client or a general JSON implementation.

`capture.py` runs `managed_probe.py` under the repository's bounded owned Job
runner. Each native child has its own retained process binding and kill-on-close
Job. Compilation and linking use the S44 bounded compiler helper; compiler root
exits and helper teardown are recorded separately. The probe copies the complete
current source manifest to a temporary immutable runtime and verifies the source
and snapshot hashes again afterward. Supply the coordinator's exact closure hash
as the final argument for final evidence; a mismatch refuses the run.

The launcher uses `ManagedFixtureOwner`, `SelectorFixtureBroker.from_managed`
and `ManagedPipeService`. It never dispatches RPCs or advances selector phases
directly. The service sends the fresh bearer only in its bound work-pipe bootstrap.
Environment and argv contain no bearer or authenticated request. Native output
does not record the bootstrap; bearer/plain/hex/base64 scans precede output.

Three actual AppContainer children exercise:

1. Fresh discovery, control inspect, lease, native canonical activation and
   SHA-256, bounded control lookup to COMMITTED, exact retry and final inspect.
2. Close/reopen the managed owner from storage ID alone in the same broker
   process; a fresh worker/session/lease replaces generation 1 with generation 2,
   verifies idempotent retry and sends durable Stop.
3. Drop the work reply by closing that pipe, then use healthy control lookup,
   inspect and Stop. A held UNKNOWN is expected; no-effect is not inferred.

The second case is owner close/reopen, not a fresh broker-process crash/restart
claim. S45 separately records actual process-cut recovery. Production typed
client conformance comes from its own tests, not this diagnostic parser.

Each child probes pipe WRITE_DAC/WRITE_OWNER/second instance, private directory
list/create, event read/write, and protected registry query/set. It also reads,
writes and reads back a newly created AppContainer-accessible positive-control
registry leaf under the same user/product prefix. The host checks that result.
Before sending bootstrap, the host verifies protected custody bytes, event
binding and root namespaces remain unchanged. Attempted rights are explicit in
the result. All three newly minted registry leaves are removed through validated
no-follow native key handles; shared product configuration is preserved.

`prototype-01` preserves a failed diagnostic assumption: lookup may legitimately
report transient UNKNOWN/SELECTED while the live pump is adopting. Subsequent
versions poll within the fixed deadline for a durable terminal result.
`prototype-02` passed the lifecycle flow; `prototype-03` added registry positive
control; `prototype-04` added explicit rights and unchanged-state checks and
passed all three cases. Prototypes are not final candidate evidence.

Final invocation, once source is frozen:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s46-native/capture.py run-01 GT02-S46-NATIVE-01 <exact-source-closure-sha256>
```

Successful evidence must include native exit 86 for all three children, no forced
termination, each native Job PID list empty, zero live service threads and
endpoint/I/O/event owners, compiler/link exit 0 with helper Jobs empty, actual
outer exit 0 and verified tree, same frozen source map, and removed registry
leaves/profile/temp/runtime snapshot. General safe file mutation and acceptance
remain false in the diagnostic result.
