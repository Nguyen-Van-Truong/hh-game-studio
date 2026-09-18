# S95: next observation for the S93 lookup gap

2026-09-18, Asia/Saigon. `AUTHORITY=0`; `formal_acceptance=false`;
`root_cause_established=false`. File review only: no engine, test, profiling,
hash audit, source change or rerun was performed for this note.

Established facts from `../20260918-gt06-s95-status-recovery/gap-analysis.json`:
S93 `b6.inspect.4` had an admission receipt at 641389534598 us, a lookup starting
641389564757 us and returning local `UNKNOWN/CONNECTION_LOST_LOOKUP` at
641391567730 us, then a successful same-ID lookup at 641391910066 us. The
reported gap is 2033.1318 ms; the unsuccessful call spans 2002.973 ms. Its
transport stage/category were not retained. A two-second socket timeout is
consistent with these timings, **not proved**. Local UNKNOWN is not a server
receipt: known admission to successful readback spans 2375.468 ms. Discovery
and lease receipts are present. Native gap 579.328 ms does not explain this
host-lane failure, and the failure remains valid.

The HTTP attribution `summary.md`/`analysis.json` establish only a narrower
negative result: 20 ten-command groups over copied 6,928,143-byte S93 history,
160 lookups, zero UNKNOWN/non-null transport failures, maximum lookup interval
141.931 ms and maximum progress gap 401.4742 ms. The largest dispatch contains
353.2521 ms writer-held and 336.0078 ms append spans. They overlap; they are not
additive and do not locate encoding, SQLite, file IO, fsync or scheduling within
append. Initialization's 5031.4 ms load is outside the HTTP window. The 48-file
HTTP closure matches the corresponding paths in the 51-file current closure;
it is not the S93 source/workload or a formal replacement.

Source facts: `host/core/transport.py::_dispatch` holds the host RLock while
calling `_lookup`; worker terminal publication also calls `_finish` under that
lock. Journal lookup uses the `_mutating` guard. `VerifiedJournal._writer_lock`
then takes its cache mutex and inherited OS guard; `_reload/_snapshot` reads and
hashes the journal and preserves its durability synchronization. These are
plausible blocking boundaries, not measurements of the failed request.

| Hypothesis, still unproven | Observation that would distinguish it |
|---|---|
| Lookup waited behind another host operation, including worker terminal publication | Long dispatch-entry to lookup-entry interval, with an overlapping worker-finish/journal span. That interval also includes session validation: do not label it pure lock wait without a lock-acquisition marker. |
| Lookup's own journal guard, verification or IO stalled | Lookup entered promptly; guard-wait or guarded snapshot/reload/lookup span accounts for the delay. Split append/fsync/SQLite only if the captured interval actually localizes there. |
| Request arrival/parsing, response generation/delivery or scheduling stalled | Missing/delayed handler/request-parsed markers, or dispatch finishes promptly but response-send/client-header/body completion does not. Absence of a handler marker alone does not prove the network caused it. |

Current per-lookup diagnostics are necessary but insufficient for causal
location. They preserve endpoint, failing client operation (`request`,
`getresponse`, `read`), error category and QPC elapsed time across a recovered
retry. That elapsed time covers the **whole call**, not just the named stage.
`request` includes encoding/connect/send; `getresponse` waits for response
status/headers; `read` receives the body. None identifies which server boundary
was slow. The S95 clock correction aligns diagnostic time with the producer's
`perf_counter_ns`; it does not repair or invalidate S93.

Before the next coordinator-scheduled HTTP diagnostic, the minimum useful
addition is a bounded, correlated phase record in a disposable diagnostic
wrapper, delegating unchanged methods to the accepted implementation:

- Client call entry, request return, header return, body return/error, and the
  existing attempt ID/failure metadata. Use QPC throughout.
- Server handler entry, request-parse return, dispatch entry, lookup entry,
  lookup return, send entry/return, plus writer-guard wait/acquired/released
  and snapshot/reload/append boundaries. Retain an overlapping worker-finish
  span so a competing lock holder is visible.
- Join retry attempts by an observation-only connection ordinal/loopback port
  pair and the validated public fixture command ID. Command ID alone cannot
  distinguish two overlapping same-ID lookups. Add no wire header or command.
- Record entry markers immediately, not only completed `finally` durations.
  On the first UNKNOWN, retain the bounded pre-event window and currently
  unfinished spans, then preserve any subsequent completion separately. A
  largest-sixteen-slow-spans list can lose the matching request or unfinished
  wait. Record capacity/overflow explicitly; a dropped marker is UNKNOWN.

The `_send` boundary includes response encoding, send and bounded drain; its
return is not proof of delivery to the client. Only if delay localizes there,
add diagnostic encode/sendall boundaries that forward the original operation
unchanged. Likewise, dispatch-to-lookup bounds do not justify replacing locks
or moving durability work outside them. No speculative server repair is yet
supported by the evidence.

Prepare this observation contract without touching the live native run. Use
primitive enums/IDs/timestamps only: no bodies, credentials, raw exceptions or
Object references; no synchronous diagnostic disk writes under server locks.
Any later instrumented run needs a fresh ID/freeze and explicit diagnostic
label, unchanged two-second status criterion, existing transport/terminal
timeouts, same-ID reconciliation, locks and fsync policy. Do not add artificial
status receipts, shorten timeouts to manufacture progress, promote the short
HTTP result, or launch a blind full campaign. Choose a single bounded follow-up
only after this record can distinguish the competing explanations.
