# S95 HTTP phase observations

`AUTHORITY=0`; `formal_acceptance=false`. This folder prepares a reusable
diagnostic wrapper for the unresolved S93 lookup gap. It does not change the
accepted implementation, repair the failure, or supply acceptance evidence.
Importing `phase_observer.py` imports only standard-library modules and installs
nothing. There is no runner, engine launch, disk writer or automatic retry.

The factories subclass the caller's pinned classes and delegate each operation
once with its original arguments. They retain primitive IDs, fixed phase/route
enums, QPC timestamps and numeric loopback ports. They do not retain command IDs,
arguments, request/response bodies, credentials, exception text or runtime
objects. Transport errors and existing `last_transport_failure` remain the
base client's responsibility. All original timeouts, locks, journal reloads,
fsyncs, cancellation, Stop and reconciliation remain in the delegated methods.

## Integration in a future diagnostic process

Reuse the existing HTTP probe's `ExitStack`/`patch.object` setup and ownership
capture, with these additional wrappers. Resolve the frozen source imports
before this setup. `b` below is its frozen `studio.tests.replay.benchmark_commands`
module, whose client/host aliases already select the benchmark transport.

```python
recorder = PhaseRecorder(event_capacity=512, active_capacity=64)
journal_type = observed_journal_type(b.Journal, recorder)
host_type = observed_host_type(b.LoopbackFixtureHost, recorder)
client_type = observed_client_type(b.FixtureClient, recorder)
connection_type = observed_connection_type(http.client.HTTPConnection, recorder)

with ExitStack() as stack:
    # Existing history-copy/project factories should instantiate these types.
    stack.enter_context(patch.object(b, 'Journal', journal_factory))
    stack.enter_context(patch.object(b, 'LoopbackFixtureHost', host_factory))
    stack.enter_context(patch.object(b, 'FixtureClient', client_type))
    stack.enter_context(patch.object(http.client, 'HTTPConnection', connection_type))
    # Construct/use/close the existing producer before leaving this scope.
    ...
    captured = recorder.snapshot()
```

Capture original classes before patching. The process-local HTTP class patch is
intended for a disposable, dedicated diagnostic process; do not install it in
the live app or native helper. Keep it installed through producer cleanup. The
base must remain `BenchmarkFixtureClient` (or a compatible subclass exposing
its existing nullable `last_transport_failure`). Pin this wrapper file with the
runner/probe helpers and the complete source closure used by the diagnostic.
Any native overlay needs its own complete closure and exact reversal proof.
Use a fresh run ID and actual owned process exits. Coordinate the next run after
the active measurement is terminal; do not introduce another approval gate.

## What the record establishes

Every tracked span has immediate `enter` and final `exit` events. `outcome` is
`returned` or `raised`; it is not a status receipt. Open spans also remain in a
separate bounded `unfinished` map. `client.connect` binds the connected socket
before request send can block, propagating the port pair to active ancestor
spans through `bind` events. Server binding occurs at `_handle` entry. A failed
connect can have no identity; `identity_missing` makes that limitation explicit.

Each `client.call` root span identifies one attempt in the current client, which
creates one connection per call. Join the server handle by numeric
`(server_port, client_port)` plus the QPC lifecycle window, and join the producer
attempt by its enclosing QPC interval and route/order. Retried same-ID calls have
distinct client root IDs. Do not join on command ID alone. No command ID or wire
header is added. If port reuse, missing/evicted entries or multiple candidates
make a join ambiguous, report UNKNOWN. This module records; it does not guess a
join or implement an analyzer.

| Span | Actual delegated boundary and limit |
|---|---|
| `client.call` | Existing benchmark `_call`, including its encoding, validation and close. |
| `client.connect` / `client.request` | Standard HTTP connection methods. Connect is nested in request; request also includes its HTTP formatting/send. Canonical body encoding precedes the request method. |
| `client.headers` / `client.body` | `getresponse` / response `read`; these identify the client operation that remained open or raised. |
| `server.handle` / `server.read_request` | `_handle` / `_read_request`. The parse return precedes authentication/JSON/session validation and dispatch. No accept/queue marker exists here. |
| `server.dispatch` / `server.lookup` | `_dispatch` / `_lookup`. Dispatch-to-lookup includes route/session validation and possible host-lock contention: **not pure lock wait**. |
| `server.send` | `_send`, including encoding, send and bounded drain; completion is not proof of client delivery. |
| `host.finish` | `_finish`, including terminal journal publication. May run on a worker or a request/cancel path; thread/context IDs distinguish them. |
| `journal.guard_wait` | Entry through the original combined cache-mutex and OS-guard acquisition. No split of the two locks is claimed. |
| `journal.guard_held` | After acquisition through the original guard exit/release/error mapping. |
| `journal.snapshot/reload/append/load` | Exactly those existing methods; nested spans overlap and are not additive. No fsync/SQLite subphase is inferred. |

On the first existing non-null **lookup** transport failure, the client wrapper freezes
the current ring and all unfinished spans **before returning to the producer or
allowing retry to reset metadata**. `first_failure.failed_call_id` references that
attempt; the call itself is still open at this capture. Later `snapshot()` output
contains the current ring, completion events and the unchanged first-failure
copy. An earlier non-lookup transport failure is counted but never consumes this
lookup window. The commands-drop regression is explicitly injected test input;
there is no demonstrated intentional drop in the current coupled producer.
An observed failure alone does not classify an injected case as an anomaly.
Route selection uses the fixed path
mapping, without inspecting bodies. `failure_trigger` is
`first_lookup_transport_failure`. There is only one retained lookup-failure
window; all failures increment `transport_failures_observed` and the bounded,
fixed-enum `transport_failures_by_route` counters. Persist snapshots outside delegated operations;
the recorder performs no synchronous disk IO under host/journal locks.

Default bounds are 512 events and 64 active spans; configuration is limited to
8192 and 256 respectively. The first-failure copy adds at most one more bounded
window. `events_evicted`, `spans_dropped` and `identity_missing` are cumulative;
overflow does not skip the underlying operation. A null failed-call ID means
its span overflowed. Missing markers cannot establish absence of activity or a
complete chain. Snapshots are defensive copies, so persisting/annotating an
output cannot mutate the retained first-failure window.

All times use `perf_counter_ns`, the same QPC domain as the producer on this
Windows/Python pin. The recorder adds mutex/allocation/snapshot overhead, which
is neither removed nor called transport latency. This is a diagnostic causal
trace, never a replacement performance measurement or a relaxed threshold.

## Focused validation

`test_phase_observer.py` uses fakes only, including a bounded two-thread open-span
case. It checks QPC use, eviction/active overflow, immutable first-failure capture,
fixed enums, sanitized fields, commands-drop then lookup-failure triggering,
retry/port identity, unchanged wire arguments and
exceptions, original method order, and guard release/suppression semantics.

Owned `unit-02` passed 12/12 checks (target 4300, helper 20936, both exit 0;
Job tree verified, no timeout, exact tested pins unchanged). The regression
`test_commands_drop_does_not_consume_later_lookup_failure_window` verifies the
corrected trigger. `unit-01` remains historical evidence for the earlier
11-test helper; it does not verify this corrected trigger.

Owned `smoke-02` passed against the reused frozen 48-file HTTP source, matched
to the current map, with a fresh copy of the historical journal and a new project.
It ran one unchanged ten-command diagnostic, then **explicitly injected** a
before-dispatch read-only inspect-submit disconnect, an after-dispatch lookup
disconnect and a same-ID read-only lookup retry. These are smoke-only faults,
not behavior asserted of the current coupled producer or a reproduction of S93.
Both effects came from the normal diagnostic; the injected sequence left the
effect count at two. All 17 phase kinds were observed. Commands/lookup failure
counts were 1/1; the first frozen window belongs to the lookup.

The failed lookup's client root 408 and ports `(65432, 65460)` match server root
411. Its retry has client root 420, ports `(65432, 65461)` and server root 424.
There were zero evicted events, dropped spans or missing identities, and no
unfinished spans after cleanup. Target 47412 and helper 17632 both exited 0;
the owned Job tree, host threads/sockets, observer and journal were closed.
Mapped current source, historical source/history and pinned helpers stayed
unchanged. See `smoke-02/{freeze,capture,report,phases}.json` and raw HTTP logs.
`smoke-01` is retained for the earlier helper only. Neither smoke proves the
cause of the rare two-second gap or authorizes a performance acceptance claim.

Final tested wrapper SHA-256:
`9a79e5767f07674e80fb457b6d8f6326cb3558e9feb1d5d51884ad7784f5be57`.
