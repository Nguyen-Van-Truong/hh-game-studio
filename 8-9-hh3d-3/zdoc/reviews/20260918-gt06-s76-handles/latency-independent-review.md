# S76 independent latency analysis — recommendation only

Review time: 2026-09-18 00:02 UTC / 07:02 Asia/Saigon. Observed HEAD:
`dfbed1621a831abd9cc005f2b1ee01de9fec2702`.

This is a bounded static performance/safety review, **not a final acceptance
critic**, PASS, TICK, or proof that the 2-second failure is repaired. I read
the root and nested AGENTS, S76 tools plan, current journal/transport callers,
S76 HTTP attribution, and the preserved S75 batch-8 command evidence. No test,
engine, benchmark, task/process control, runtime edit, or commit was performed.
Only this leased report is authored. Tracked status was clean at initial
inspection; existing untracked evidence was left alone. The read-only process
snapshot showed Python processes and no Godot/Blender process; it is not an
ownership or historical-exit proof.

## Recommendation

Reduce repeated byte scans **only within one explicitly bounded admission
operation that continuously holds the inherited journal kernel guard**.
For a fresh inspect, this combines the existing-ID lookup and pending append;
for a fresh set, it can also include the admission lease check. Keep every
existing recovery/append fsync boundary, every external lookup's full byte
verification, and the worker's independent lease/terminal boundaries.

Do not add an elapsed-time cache, mtime cache, host-RLock-scoped cache, or a
cache spanning HTTP calls. There is no sound `_reload()`-only shortcut in
the current call graph: the accepted journal guard is released between its
public methods. A cooperating second writer can append a receipt or fencing
epoch during that interval even while the host's private RLock remains held.

This is a targeted throughput candidate, not an established fix for S75.
The failed inspect was already admitted before its slow lookups. Admission
coalescing cannot remove all later scans and does not establish the cause of
the rare delay.

## What is measured, and what is inferred

S76 `profile_http.py` wraps existing methods and stream calls and delegates
all arguments/results. The stored durations are inclusive and instrumentation
adds overhead. Its `http-attribution-timing.json` reports:

| Observation | Count | Inclusive time |
|---|---:|---:|
| `_snapshot` | 122 | 10.6833467 s |
| `_reload` | 121 | 10.6097616 s |
| Snapshot reads | 62,090 | 2.4235267 s |
| Snapshot opens | 122 | 0.3296853 s |
| Snapshot fsync | 121 | 0.1691146 s |
| `_append` | 60 | 0.5870049 s |
| Initial `_load` | 1 | 33.0182259 s |
| HTTP submit / lookup | 30 / 31 | 5.5840326 / 6.2718851 s |

The caller graph explains the 121 reloads exactly: 30 inspections each have
an existing-ID lookup, pending append, and terminal finish (90); the 31
external lookups add 31. The constructor accounts for the extra snapshot.
This matches a run in which each normal lookup already saw the terminal
result, plus one repeated terminal lookup. It is not 122 duplicate scans of
one continuously locked operation.

Subtracting only the disjoint read/open/flush/fsync children from snapshot
time leaves about 7.760 s. That residual contains hashing, fstat, Python and
wrapper overhead, and scheduling; it is **not measured hash CPU time**.
The fsync maximum is 91.8991 ms, while its aggregate is only 0.169 s. Neither
the small aggregate nor the residual justifies skipping durability or naming
fsync/hash as the S75 cause.

The diagnostic read a private copy of a 33,224,600-byte history. Its 30/30
completions, terminal p95 466.165 ms and maximum response gap 308.506 ms do not
reproduce the failure. That workload is not the full 1,000-command mix. The
initial 33.018-second load is outside the repeated HTTP phase and should not
be counted as per-command gain.

## S75 inspect.226 timeline

The relevant raw file is S76's preserved
`failure/raw/campaign/run-00-attempt-01/command-08.json`, not the older
S75-directory failure package, which preserves an S73 failure. The command is
`gt06-s75-campaign-01.r00.a01.b8.inspect.226`.

| Event | Start monotonic us | End monotonic us | Observed result |
|---|---:|---:|---|
| Submit | 584439775570 | 584439876762 | ACCEPTED_PENDING, 101.1921 ms |
| Lookup 1 | 584439878171 | 584440189731 | ACCEPTED_PENDING / QUEUED |
| Lookup 2 | 584440192013 | 584442205953 | UNKNOWN / CONNECTION_LOST_LOOKUP |
| Lookup 3 | 584442245235 | 584443294929 | COMMITTED / READBACK_CONFIRMED |

Lookup 2 lasted approximately 2,013.940 ms; the response-to-response gap from
lookup 1 to lookup 2 is 2,016.222 ms in the retained microsecond timestamps.
The source's nanosecond calculation is `max_status_gap_ms=2016.2214`; rounding
the exported timestamps explains the small difference. Total terminal latency
is 3,519.3582 ms. `effect_count_before` and `effect_count_after` both remain
1690, with terminal revision `rev-1690` and the expected result/digest.

This is successful same-ID reconciliation after a real uncertainty response,
not a lost effect and not a latency PASS. Nearby inspections 222/224 also took
953.1882/1081.9863 ms, which suggests a local period of slowdown but does not
identify its cause. The raw row has no server lock-wait, journal-scan, fsync,
or scheduler timing. Client timeout is 2 seconds; a timeout response by itself
does not prove which server stage consumed that time. Preserve the UNKNOWN
response, existing 5-second total lookup budget, 2-second gap gate, and all
samples.

## Smallest safe implementation shape

The following is design pseudocode, not an applied patch. It deliberately
keeps the accepted `Journal` writer and validator unchanged.

1. Add one private grouped-admission helper/facade in
   `studio/host/replay/verified_journal.py`. Its lifetime owns exactly one
   inherited `_writer_lock()` acquisition. It exposes only existing lookup,
   admission lease-check, and pending-append operations; no general nested
   transaction API, effect callback, compaction, engine I/O, or waiting.
2. Keep the transport's existing validation order: parse/schema/capability,
   target, and payload validation happen before entering this scope. Then
   enter the journal scope at the current `_existing` call (core transport
   line 636) and leave immediately after pending append (line 653), before
   adding/waking the job. Existing-ID lookup and the exact digest/orphan-
   pending resolver remain first inside the scope. A replay returns before
   the new-command deadline, Stop, queue, lease, and revision checks.
3. The first journal subcall executes the current `_reload()` in full under
   the inherited guard: regular/single-link/path/policy checks, complete
   SHA-512 byte verification, accepted replay on mismatch, and recovery
   fsync. The proof belongs to this particular guard acquisition and current
   owner thread, never to a time interval or to the host lock.
4. A later admission subcall under that **same uninterrupted guard** can reuse
   the verified decoded index. Keep its recovery flush/fsync in place,
   including the same durability-error mapping. Recheck private namespace,
   file identity/regular/single-link/size, policy and expected local generation
   around that barrier. Unexpected changes invalidate the scoped proof and
   use the full accepted validation path or fail closed. These metadata
   checks are a consistency check on already verified bytes held under the
   guard, not a replacement for byte verification across guard acquisitions.
5. Dispatch the original accepted method bodies under this guard, preserving
   their validation, bounds, disk receipt decoding and error semantics. The
   facade must reproduce the accepted `_mutating` phase bookkeeping per
   subcall: a reload/barrier failure or a guard-exit failure is uncertain;
   a known method-body validation refusal is not silently reclassified as a
   pre-effect success. If using the existing `__wrapped__` bodies to avoid
   copying validators, isolate that private adapter and test parity; never
   expose an unguarded method or a bypass flag to a client.
6. The pending append still uses the inherited serializer, capacity reserve,
   write, flush and fsync. Index extension remains conditional on confirmed
   local append identity/length. Do not enqueue until scope exit succeeds.
   Every exit, exception, policy change, failed append/barrier, and uncertain
   unlock destroys the scoped proof. An expected COMMAND_NOT_FOUND may be
   consumed solely for the new-command branch after successful verification.
7. Retain separate full-scan operations for external lookup/archive, worker
   terminal persistence, worker effect-time lease_guard, Stop and cancel.
   Never carry the scoped proof across worker dispatch, readback, HTTP reply,
   or release/reacquisition of the kernel guard.

The transport must explicitly opt into this helper; silently changing
`VerifiedJournal._writer_lock` into a general reentrant lock is unnecessary
and conflicts with the accepted lease_guard contract. Do not temporarily swap
`host.journal` for a facade, because other threads may access it. Pass the
scoped facade locally to the existing receipt resolver instead.

Current GT-06 allowed implementation paths include `host/replay`, not the
accepted `host/core`. Prefer a thin replay-owned fixture-host admission
adapter, sharing the existing receipt resolution logic, or an explicitly
reviewed narrowly scoped transport hook if the coordinator establishes that
file scope. Do not duplicate the complete transport or claim it is unchanged
after adding the hook. Any affected dependency requires a new source map and
focused regression evidence; existing signatures do not move to it.

If minimizing the first candidate further, apply the grouped path only to
`fixture.inspect`. It removes one scan per new inspection while leaving the
write admission and effect-time fencing paths exactly as they are. Expanding
to `fixture.set` can follow only after the same-scope lease cases below pass.

## Safety boundaries and expected benefit

| Boundary | Required behavior |
|---|---|
| Durable terminal precedence | Existing same-ID terminal/orphan result wins over new deadline/lease checks exactly as `_existing` does today; changed digest conflicts. |
| Durability | Keep recovery fsync at each logical subcall and actual append fsync; no deferred/group commit or ACK before scope exit. |
| Fencing | Admission reuse is only inside the inherited guard; worker rechecks fresh lease and real deadline immediately before effect. |
| UNKNOWN | Storage/lock uncertainty and failed scope exit cannot produce REJECTED/no_effect or enqueue a second execution. Reconciliation uses the same ID. |
| Exact bytes | Every new guard acquisition rehashes the complete file; same-size/same-mtime edits, replacement, truncation, external append and policy changes still force validation/rejection. |
| Stop/control | No scope crosses effect/readback/delay; Stop's latch and existing control listener behavior remain intact. |
| Receipt memory | Keep only existing indexes/digest, not persistent receipt bodies or full journal bytes. |

For S76's 30-read shape, the candidate removes 30 of 121 steady-state full
scans (24.8%) while preserving the fsync boundaries; 91 steady-state scans
remain, plus the initial snapshot. This is a call-count prediction, not a
measured wall-clock speedup. A fresh inspect normally has four scans including
one external terminal lookup: 4 becomes 3. A fresh set normally has six
(existing, admission lease, pending append, effect lease, terminal finish,
external lookup): 6 becomes 4 if the broader admission path is grouped.
Pending/retry/cancel/control calls add further scans and cannot be omitted.
Avoid extrapolating the instrumented mean scan cost to the rare 2-second tail.

## Verification needed before claiming improvement

No checks listed here were run by this reviewer.

- Focused journal/transport parity: same-length/same-mtime corruption; file
  replacement/truncation; policy changes; external writer append and lease
  renewal; independent cached writers; tombstone/archive/compaction behavior.
- Group lifetime: count full scans and fsyncs independently; one verify per
  scope, unchanged barrier count, no reuse after guard exit; another writer
  blocks during the scope and is observed on the next operation. Cross-thread
  access cannot borrow the proof. Force failure at every recovery/append/
  unlock phase and verify pending/terminal/UNKNOWN and zero duplicate effects.
- Receipt precedence: duplicate terminal with expired deadline/obsolete lease
  still returns the old terminal; conflicting digest rejects; orphan pending
  remains UNKNOWN; racing same-ID admission does not enqueue twice.
- Fencing/Stop: lease expiry before effect, renewal between admission and
  execution, revision change, revoke/Stop/deadline before and after effect,
  delayed readback, and terminal-fsync failure retain accepted behavior.
- Only after focused checks: a bounded real HTTP diagnostic on an immutable
  private history copy, with stage timing for host RLock wait, journal guard
  wait, byte read/hash, recovery fsync, terminal append and response send.
  Split request-handler and worker spans using monotonic times/command IDs;
  keep output buffered/bounded and redact secrets. This can distinguish the
  inspect.226 failure paths without changing timeout or thresholds. Instrumented
  diagnostic measurements remain supplemental, not campaign measurements.
- The unchanged full 10 fresh pairs × 35 batches remains mandatory after a
  fresh freeze; no merging partial attempts. Handle failure also remains open.

## Coordinator follow-up: two-file hook and whether to implement now

The coordinator specifically asked whether this can stay in `VerifiedJournal`
plus one explicit opt-in `core/transport.py` hook with `nullcontext` as default.
**Yes.** That is smaller than copying a fixture host. Keep `core/journal.py`
byte-identical. A trusted in-process hook such as
`getattr(self.journal, 'admission_scope', nullcontext)()` can wrap only the
existing/lease/pending-append block. Ordinary accepted Journal instances take
the no-op context. Invalid schema/target/payload requests remain before the
hook, so the 300 validation rejects per batch still perform no journal I/O.

For that variant, `VerifiedJournal.admission_scope()` acquires
`super()._writer_lock()` once and owns a thread-local, acquisition-specific
token. A narrowly conditional `_writer_lock()` override may reuse the held
guard for nested accepted methods **only while this explicit scope is active
on its owner thread**; otherwise it delegates unchanged. This is not general
reentrancy and must not change `lease_guard`'s no-nested-calls contract. Use
the accepted decorators/methods themselves, eliminating the need for the
facade/`__wrapped__` adaptation described above. `_reload()` performs the full
verification on the first subcall, then only the preserved durability barrier
and scoped consistency checks for the subsequent subcalls. No scoped proof
survives exit or an unhandled error; `_reload`/`_append` uncertainty clears it
immediately. A thread-local boolean alone is insufficient: require a token
created only after this very instance acquired its inherited guard, and clear
it in `finally`, including unlock failures and exception unwinding.

One easy-to-miss detail: a fresh `_existing()` uses `lookup()` which raises
`COMMAND_NOT_FOUND`, and `_existing()` catches that expected absence **inside
the still-active admission scope**. Clearing the scoped verification merely
because that known non-mutating miss crossed the nested lookup frame would
force the second full scan and erase the intended inspect benefit. Keep
invalidation on the outer escaping exception and on reload/append failure;
do not conflate an internally consumed, successfully verified lookup miss
with a failed verification. Add an explicit test for this path. Unhandled
validation errors still exit/clear the scope; no failed admission gets queued.

**Immediate recommendation: collect bounded post-admission timing first; do
not implement this optimization solely to fix inspect.226.** It is a sound
candidate to reduce known repeated work, but the 2-second failure is later,
and there is no before/after measurement yet. The tradeoff is material:

| Item | Current evidence / expected cost |
|---|---|
| Demonstrated speedup from grouping | None; code has not been changed or run. |
| Static S76 saving | 30 of 121 steady-state scans; 24.8% fewer scans, same fsync boundaries. |
| Optimistic scan-only magnitude | 30 × observed average snapshot 87.568 ms ≈ 2.627 s across that 30-read diagnostic; this is arithmetic, not a wall-clock or tail-latency prediction, and slightly overstates saved work because barriers remain. |
| Full benchmark | New runtime49 closure/freeze and all 10×35 batches on it; the campaign was already required, but all candidate-source proof must be reminted. |
| Current service dependencies | Both edited files occur in all five S73 service runtime173 maps (HTTP complete, HTTP Stop, saturated Stop, revoked result, stale capture); their inherited 158 checks / 1,281 raw files cease to be an exact-current source projection. Budget five scoped service remints under the existing policy, or supply a coordinator-approved explicit dependency bridge before claiming reuse. |
| Managed replay | `core/transport.py` occurs in S69 runtime159; `verified_journal.py` does not. The two-file hook loses that exact-current projection too. Establish an explicit unaffected-execution bridge or remint the affected managed replay lane; no old hash can be relabeled. |
| Historical GUI/adversary dependencies | Both edited files occur in their five runtime173 maps. Update the service bridge using new proof; the two five-file UI maps themselves have no overlap, so source overlap alone does not require recreating the UI captures. |
| Review/tests | The broad review-runner148 map contains both edited files. Run focused journal, default-no-op transport, grouped transport, uncertainty and fencing regressions, then update the source/review map; do not rerun unrelated native gates merely for report edits. |

These overlap counts were read directly from the 14 declared source-map
locators in `20260918-gt06-s75-recovery/next/affected-dependency-bridge.json`.
Twelve of those 14 maps contain at least one proposed edited file; the two
UI-only maps do not. This is source-map membership analysis, not a fresh
execution or complete raw/hash re-audit. The current S76 history hashes above
remain the review baseline; coordinator edits to plan/README during this
review do not turn the recorded plan hash into a current-head assertion.

Because a timing-only diagnostic leaves these runtime dependencies unchanged,
it has a much lower remint cost and can establish whether terminal finish,
external lookup, RLock wait, kernel-lock wait, or non-journal scheduling is
responsible. If that attributes material delay to repeated admission scans,
the two-file candidate is justified. If the long tail stays wholly after
admission, tune the evidenced stage while preserving the gate; do not claim
the admission optimization solved it merely because a short rerun passes.

## Read source/evidence identity

Paths below are relative to `8-9-hh3d-3`; values were read from file bytes.
The S76 campaign runtime manifest declares closure
`ffa6071a1fb9d324da7cd860fb41b656e99135a3118367873c7399e85e8432fe`.
That declaration is context, not a new full-closure audit by this reviewer.

| Path | SHA-256 |
|---|---|
| `AGENTS.md` | `c93a79b7833f8a02246d0373545f05efc680fc299e2090002b756ae9b0e6d49f` |
| `zdoc/8-9-godot-blender-agent-studio-plan.txt` | `d2949a341a3021942c4150873f46c1234d29eb9e04419cdf4ec62038a1120bc5` |
| `studio/host/core/journal.py` | `826bc5e4c60817e3a22dd2e0b6a199eb522a4eb78532cb5300249fe9056c0cc6` |
| `studio/host/core/transport.py` | `1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0` |
| `studio/host/replay/verified_journal.py` | `9128749e6a04242106e56a86e959b6de0a67e0f10ffb97965e1bc88390d5a6f2` |
| `studio/tests/replay/benchmark_commands.py` | `522e91341eda6175704b692cd9bc5454951f93a891657e815a9a2111cd3eb438` |
| `zdoc/reviews/20260918-gt06-s76-handles/profile_http.py` | `f7e5cdeefd72c5a7f6490845ede607a6b4dc7eebcbd1c1bf684ce8798e0f93d7` |
| `zdoc/reviews/20260918-gt06-s76-handles/http-attribution-timing.json` | `620a075b8648c4ad29d015af4aea6afee5df9caccf96cba60448283efa546522` |
| `zdoc/reviews/20260918-gt06-s76-handles/failure/raw/campaign/run-00-attempt-01/command-08.json` | `43daf97dcda536688c4687d00f71c284b24a0312e9a877a4c310a9f73aede2ed` |

Static repro: read the call sequence in `core/transport.py:636`, `:648`,
`:652`, `:707`, `:777`, `:590`; compare `Journal._mutating` at `core/journal.py:263`
with `VerifiedJournal._reload` at `replay/verified_journal.py:84`. Parse the
preserved `command-08.json`, select `.commands[]` whose `.command_id` ends in
`.inspect.226`, and compare its lookup timestamps with `.max_status_gap_ms`.
Use the raw nanosecond-derived field for the gate, not rounded exported
microsecond differences.
