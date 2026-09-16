# S46 bounded managed pipe lifecycle design review

Date: 2026-09-16. AUTHORITY=0. Read-only source review; no acceptance or capability claim.

Baseline: S45 checkpoint `1951d802fd570a435198900bd5ea382c2e00b179`, including the managed fixture owner, durable registry custody and native S44 IPC diagnostic. S46 factory/client/service work is concurrent and is not represented as frozen or verified by this review. This report records required behavior and review targets for that implementation.

## Minimal ownership and execution model

One service owns one exact live `ManagedFixtureOwner`, one broker/session, two distinct endpoint roles, and three bounded threads: work serve, control serve and activation pump. The external launcher owns the retained worker process and its kill-on-close Job; endpoint process-handle duplicates belong to the endpoints. A service does not gain permission to kill unrelated processes, delete roots, replace custody, or reconstruct runnable work from durable history.

Reserve both endpoint roles before launching a worker. Create the worker suspended, assign its owned Job, bind both endpoints to its retained process identity, then resume. Connecting/bootstrapping either endpoint has a finite deadline. A partial setup failure follows the same retained-resource cleanup rules as normal shutdown. The existing global pipe limit does not itself reserve control capacity.

Construct a managed broker only from the exact live owner and its selector, after checking the owner's custody/consumer/file-root readiness. A caller-supplied selector or matching path is insufficient. The service attaches an ownership guard that refuses direct owner or broker close while service threads can access them. That guard persists through failed shutdown, rather than merely while the service considers itself RUNNING.

Each serve thread performs one request/response at a time on its own endpoint. The pump is the sole caller of `broker.advance()` and uses existing broker admission/pump locks. Request I/O never runs while holding a selector, custody or broker state mutex. The existing selector permits one admitted synchronous phase to complete after a subsequent revocation or Stop request; no new phase may be admitted after the hold/revocation check.

The wake event must be set when `_job` is published, before response serialization/write. `serve_one()` returns only after write completion, so waking only after its successful return can leave durable admitted work unscheduled when the reply blocks or is lost. The pump clears the wake before checking/draining available work; it must not clear a newer wake after deciding that no work exists. It stops pumping on hold, terminal state or full shutdown. Reopen never restores `_job` from disk.

## Session states and failure policy

| State | Permitted behavior |
| --- | --- |
| STARTING | Bounded connect and credential bootstrap; no public command admission before both identities/roles are ready. |
| RUNNING | Authenticated work requests, independent control requests and one local activation pump. |
| WORK_FAILED | Poison/stop the work endpoint, set broker hold and disable work admission/new phases; keep healthy control inspect, lookup, cancel and Stop available. An already admitted synchronous phase may finish. |
| ENDING | On control failure, peer exit, finite session expiry or explicit full shutdown: set hold, revoke/end the session, request stop on both endpoints and wake the pump. |
| DRAIN_PENDING | Retain the entire owner/broker/endpoints/thread graph. Retry cleanup; do not free native I/O buffers, release the writer guard or pretend the service is closed. |
| CLOSED | All service threads joined; pending I/O completion observed; endpoint/broker/managed owner close succeeded. |

`OwnedPipe` timeout is a poisoned-channel failure, not a benign poll result. Repeated short read timeouts cannot implement an idle server loop. Use a documented finite session/idle budget within the existing 1–30000 ms per-frame API and end the affected channel when it expires. Validate configured limits before acquiring resources; `TransportLimits` can otherwise admit a positive timeout that the pipe API rejects later. A read/write frame's one deadline includes all fragments, so a malicious partial frame cannot reset the budget.

A work reply failure is delivery uncertainty, not evidence of no effect. Keep the original command ID; control lookup may return durable terminal state or UNKNOWN/held pending state. Never invent REJECTED/no-effect from byte delivery failure. Healthy control must remain usable following work failure, as required by `PIPE_IO.md`.

Ordinary disconnect/shutdown and durable human Stop are distinct. A transport shutdown sets a local hold/revokes the session; it does not silently append a durable STOP unless the explicit product policy says so. `/v1/stop` does persist Stop through the selector. Reopen may validate terminal state and grant a fresh session/lease, but pending work remains held and durable Stop is never automatically cleared.

Session revocation is idempotent at the lifecycle level. The current authority's `revoke()` authenticates first, so an expired or replaced bearer can already be unusable; that must not prevent endpoint/thread cleanup or leak the bearer in a diagnostic. No secret, bearer-bearing request, bootstrap frame or encoded equivalent belongs in argv, environment, logs or evidence.

## Shutdown and retained ownership

Shutdown first sets hold and the service stop flag, ends authentication, signals both endpoint stop events and wakes the pump. It then joins all three threads using one absolute monotonic deadline. Giving each join the full timeout multiplies the advertised shutdown bound. No endpoint or managed storage is closed underneath a still-running thread.

Once joined, close endpoints so their `OwnedPipe` owners observe cancellation completion and release event/pipe handles in the existing checked order. Then detach/close broker and close managed owner. Every close failure preserves the failed owner and all dependencies it may still use. A later cleanup call resumes that operation; it neither starts replacement I/O nor releases the file writer guard early. `CancelIoEx` success or ERROR_NOT_FOUND does not establish completion.

If synchronous selector/storage work or native cancellation exceeds the deadline, return a bounded drain-pending result retaining ownership. The separately owned broker/worker process supervisor may terminate its exact Job and observe actual exit. An in-process service cannot promise that arbitrary synchronous storage I/O can be killed safely. The external Job is part of bounded integration evidence, not an implicit ability to discard Python threads.

## Managed owner and custody review

S45 establishes a useful non-circular restart boundary: the protected registry leaf stores typed canonical custody containing independent file/store/event identities and event high-water. Reopen starts from local storage ID, validates registry owner/DACL and state, acquires the file writer guard, re-reads custody under that guard, opens the exact roots, then validates event history before persisting an accepted newer suffix. Event append flushes before custody persistence; reply/effect gates must continue to depend on that append completing. Failed/torn/older custody is not reset to empty.

Preserve the current lock direction: log append may persist custody; custody does not call back into the log. Service shutdown must join users before closing either. A registry compare/readback is not cross-process CAS; the file guard remains the serialized writer authority.

There is one concrete readiness edge: a READY record plus CONFIG with no selected release and no pending command reopens with a read-only file root. Current rearm requires `selected is not None`. Consequently a process restart immediately after initial creation is held rather than a fresh writable empty fixture. S46 discovery/factory must report that state honestly and refuse mutations. Supporting that case requires a separately verified empty-snapshot rearm path; treating READY alone as permission would weaken the gate.

Discovery must reflect the exact ready managed registration, supported descriptor/schema and fixed `fixture.active-release` scope. It must not expose arbitrary file mutation, registry/root paths, FileIDs, blob paths or asset bytes. Existing internal success, AppContainer denial and Windows availability do not independently authorize a public capability flag.

## Required focused tests

| Priority | Scenario and decisive assertion |
| --- | --- |
| P0 | Publish `_job`, then block/fail ACCEPTED_PENDING response delivery: scheduler observes admission before response completion; outcome remains durable lookup/held uncertainty, never fabricated no-effect. |
| P0 | Work EOF/timeout while control stays healthy: hold prevents the next phase; control lookup and Stop still receive bounded replies. |
| P0 | Control EOF/timeout, peer exit or session expiry: both channels end, auth is invalid, no later phase starts, all owners remain retained until joined/drained. |
| P0 | Pump blocked inside a real phase during close: one overall deadline, DRAIN_PENDING, owner/broker direct close refused, exclusive writer guard still held; retry succeeds after release. |
| P0 | Pending overlapped cancellation/failed endpoint close: no buffer/event/handle release until native completion is observed; service retains storage dependencies too. |
| P0 | Native AppContainer calls discovery, inspect, lease, command and control lookup through actual service threads; no launcher calls to `advance()` or direct broker dispatch stand in for lifecycle. |
| P1 | Wake arrives while pump transitions to idle, duplicate command races, Stop arrives at phase boundary: no lost wake, no duplicate effect, expected held/terminal state. |
| P1 | Partial connect/bootstrap failure, wrong endpoint role/session, stale lease/fence/schema, second owner/service, exhausted slot/session budgets: bounded refusal and no effect/resource leak. |
| P1 | Owner restart by storage ID only: fresh session/lease; selected terminal state can replace again; pending/stopped/empty-reopen cases remain held as specified. |
| P1 | Inspect during stage/select/adopt exposes a consistent bounded snapshot and no filesystem identities; control result remains valid after work failure. |
| P1 | Scan all native artifacts for bearer and its encoded representations; bootstrap secret exists only in the bound pipe and transient process memory. |

## Native S44 launcher adaptation

Use a new S46 evidence folder and preserve S44 sources/results. Replace direct `ProtectedFileRoot`/store/log/selector construction with `ManagedFixtureOwner.create()` and the new managed factory/service. Keep suspended-process binding, exact package identity, owned Job, actual child exit, owned-tree-zero verification and bounded compiler supervision. Final capture must match the frozen complete source closure.

Pass only nonsecret endpoint addresses, mode and exact disposable diagnostic output locations through environment. After both endpoints connect to the bound child, send one bounded server-to-child bootstrap frame on the work pipe before its work request loop begins. It carries the fresh bearer/session/project and bounded inert fixture data needed for the diagnostic. Never send an authenticated prerecorded request through environment. Do not log the bootstrap frame.

The child first calls discovery on work and inspect on control, acquires its lease on work, then builds a canonical typed activation using the lease ID/fence and inspected expected generation/revisions. It submits, polls control lookup within a fixed deadline, inspects verified terminal state, retries the exact same command and checks idempotent terminal state. A second activation proves replacement. Host-supplied inert fixture payload/hash vectors are acceptable test input if clearly labelled; they do not prove independent canonical-JSON client implementation. Native transport/lifecycle evidence and Python typed-client conformance evidence should remain distinct.

Remove S44's raw `S39_FINAL_ACK`/`S39_FINAL_BYE` exchange from the RPC channel: it competes with a reusable control server and is not a public route. Completion is the child's bounded diagnostic result plus actual process exit. Preserve private-root/event/registry denial checks and a positive control where required; record attempted rights and unchanged protected state. Deterministic phase barriers used for Stop/drop-reply race tests must be marked diagnostic instrumentation and cannot replace a healthy uninstrumented create/replace run.

## Scope boundary and next bounded task

GT02 needs the exact managed factory/discovery contract, bounded two-channel typed client, lifecycle admission/pump/shutdown ownership, and native whole-path evidence with independent review. This establishes one fixed inert active-release fixture capability only after the coordinator's gate; it does not complete general safe file mutation.

GT03 editor mutation/UndoRedo, GT04 Blender, GT05 production build/export, GT06 Play, and GT07 cross-application scheduling, long-lived multi-worker orchestration and broader recovery remain separate. Do not add another journal, arbitrary filesystem routes, worker execution, automatic pending resumption or production owner-trust defense merely to close this lifecycle slice.

The next bounded coding task is the agreed one-service/one-session implementation with the three owned threads, wake-at-admission, WORK_FAILED control preservation, one-deadline retained shutdown and guarded managed owner closure. Freeze those APIs, run the focused races above, then remint the S46 native bootstrap/discovery/lease/command/lookup/inspect path against that exact closure. Acceptance remains pending.

## Final diagnostic addendum

The coordinator's final S46 service also includes an independent deadline watcher and a late-read admission guard; the three-thread proposal above is historical design input, not a description of the final thread count. Native `GT02-S46-NATIVE-01` ran the corrected 106-file closure `f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf` through the actual managed factory/service. Fresh create, owner close/reopen and replace, exact retries, work-reply loss with healthy control, inspect and Stop passed. All three actual native child exits were 86, outer exit was 0 with verified empty process tree, and resource/profile/registry cleanup completed. See `20260916-gt02-s46-native/HANDOFF.md` for exact evidence and limitations. This diagnostic does not independently accept GT02 or substitute for the coordinator's full candidate and critics.
