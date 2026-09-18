# GT06 S81 admission investigation

Date: 2026-09-18, Asia/Saigon. Read-only investigation; no engines, tests,
process operations, source edits, thresholds, plan changes, or acceptance verdict.
This file is the sole authored artifact for this worker.

## Finding

S80 failed because the client did not receive the submission receipt within
approximately its two-second socket timeout. The server durably admitted the
exact command; the failure cleanup then canceled it before apply. The raw data
supports `UNKNOWN/CONNECTION_LOST_LOOKUP`, not rejected admission, a successful
inspection, or a committed command. The transport discards the socket exception
subtype and phase, so `TimeoutError` and the precise source of the stall cannot
be proved retrospectively. Do not report an index/fsync mechanism as a measured
cause based on this evidence alone.

The source clearly performs repeated full-history validation/fsync operations,
plus durable SQLite cache commits, in the admission and terminal paths. There
is **no safe redundant reload to bypass under an already shared journal guard**:
each public journal call acquires and releases its own OS guard. The transport
lock is an in-process `RLock`, not that journal guard.

## Exact retained request and response evidence

Raw root: `studio/.local/reviews/gt06-s80-campaign-01/run-00-attempt-01`.

- Run `gt06-s80-campaign-01.r00.a01`; 15 completed batches; zero-based batch 15,
  commands phase, group 80, ordinal 800. Partial batch retains 801 command rows.
- Command `gt06-s80-campaign-01.r00.a01.b15.inspect.400`.
- Request digest
  `sha256:9fcd89ae83efa97157edb213f5952b12ee72517c5e535b63a4ecf61f8fe1f19b`.
- Host monotonic submit start `615166730531` us; receipt observation
  `615168733920` us; exact recorded duration `2003.3888` ms.
- Retained response fields: `receipt_status=UNKNOWN`,
  `receipt_code=CONNECTION_LOST_LOOKUP`; `lookup_attempts=[]`.
- The complete original HTTP envelope and complete client response are not
  retained. Source establishes `fixture.inspect`, empty payload, fixed fixture
  target and a ten-second request deadline. It is not valid to invent original
  wire bytes, exception subtype, or exact deadline from those facts.
- Journal line **22169** retains the same ID/digest with
  `ACCEPTED_PENDING/QUEUED`, `created_ms=1789716956880`,
  `expires_ms=1789803356880`.
- Journal line **22170** retains the same ID/digest with
  `CANCELED/CANCELED_BEFORE_APPLY` and `no_effect=true`. Both journal checksums
  independently match their canonical record bytes. Terminal records reuse
  creation time; that field does not timestamp cancellation.
- Previous row is `...b15.admitted.159`: committed value/effect count 3160,
  revision `rev-3160`; submit 126.8964 ms, total terminal 1845.8792 ms. Its only
  lookup lasted about 1717 ms. Latency pressure was already visible immediately
  before the failed submit.
- Partial `max_status_gap_ms=2045.7443` already exceeds the unchanged 2000 ms
  gate. Reconciliation or a larger client timeout cannot make this a passing
  sample while preserving those measurements.
- Actual wrapper exit is 1 for PID 34988. `host-owner/cleanup-001.json` records
  Job active count 0, zero observed, closed and no retained handles; parent
  failure records `BENCHMARK_WRAPPER_EXIT`, `owned_tree_zero=true`,
  `owner_closed=true`.

The failed inspection was not COMMITTED. That differs from the older S71 case.

## Source and raw binding

All 50 frozen source files match `source-files.json`; all 50 corresponding live
files also matched at inspection. Independently recomputed closure, using the
campaign's sorted `path + NUL + SHA256 + newline` domain, is
`1dc889ef923dee9b53c6faeeb1d6fd781acc3a89a4b860b531b55fc3a124cf8f`.
The campaign checkpoint is `f75a5d08`; repository HEAD at inspection was
`d8da8a21d22d415e097bef884d6056942a0fe719`. Existing unrelated untracked evidence
was left untouched.

| Raw relative file | Bytes | SHA-256 |
| --- | ---: | --- |
| `child-failure.json` | 923281 | `9ea461e39d74924e3a3f42044e7c00fd2525220ec7b3ae277648ceb6f79aad25` |
| `commands/commands.jsonl` | 15586409 | `4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a` |
| `source-files.json` | 5051 | `33633279752064f5cec7005148a99755e683bbd89962858f6d00fdd740da51f0` |
| `host-owner/stderr.txt` | 2133 | `e19792744f18457cbeafdd8ae748a49a7826ea5db948093d6ac5be78f68b9e37` |
| `host-owner/process-exit.json` | 30 | `a88ae92eb85ac5a4854409cc2d859c7ed7fed075e581f6ca24effca6af99c9cd` |

All 22170 JSONL checksum records match independently recomputed SHA-256: 16
lease rows and 22154 command rows; no pending command remains in the final
history. This is read-only checksum/state corroboration, not rerunning the
accepted journal validator. Journal size is below 64 MiB and rows below 100000;
the pending command had terminal capacity. Last lease expires at 1789717746755,
789875 ms after the failed command creation, and inspection does not need the
write lease. No expiry, cap, corruption, or lease rejection explains this ID.

## Exact execution path

`tests/replay/benchmark_commands.py:207-226` submits once, saves receipt timing
and status/code, and requires `ACCEPTED_PENDING`; UNKNOWN raises
`ADMISSION_UNKNOWN` before `_terminal` can run. `_terminal` reconciles only
uncertainty from a later lookup. Existing
`test_failure_keeps_partial_row_and_latches_no_retry` expressly protects failure
after a lost submit response.

`host/core/transport.py:858-884` uses a default 2.0-second timeout. Any `OSError`
or `HTTPException` during request, headers, or body is mapped to
`UNKNOWN/CONNECTION_LOST_LOOKUP`, with no automatic retry. It retains neither
exception category nor failing I/O phase.

`LoopbackFixtureHost._dispatch` holds the host lock through `_submit`.
`_submit` validates payload, checks existing ID/digest, validates new envelope,
checks Stop/queue/lease/revision, then durably appends pending before enqueueing
the job. Only afterward can the handler send the pending receipt.
`run_benchmark_campaign.py` writes the failure report and finally closes the
producer. `LoopbackFixtureHost.close` sets `_stopped`; `_execute` writes the
observed `CANCELED_BEFORE_APPLY` when it sees that flag. There was no explicit
Cancel command for the failed ID. This source and the final record support the
cleanup interpretation, without inventing its missing timestamp.

The handler also reacquires the host lock in `_disconnect_probe` after dispatch
and before reply, even when its fault is unarmed; concurrent worker journal
completion can therefore delay a receipt after durable admission. This is a
static latency mechanism, not a proven attribution for S80. The observed
cancellation means this inspection did not complete before cleanup.

## Lock, validation, and fsync accounting

Accepted `Journal._mutating` (`host/core/journal.py:263-280`) wraps **each**
lookup/check/append/finish in its own OS writer lock and `_reload`.
`VerifiedJournal._reload` reads/hashes the complete regular single-link history
and fsyncs it if the bytes still match; changed history gets the accepted full
parser and recovery barrier. Its in-process cache mutex also covers each whole
operation. Local append additionally fsyncs authoritative JSONL and commits a
SQLite index transaction.

Minimum counts for fresh commands with one successful terminal lookup:

| Phase | Inspection | Set |
| --- | ---: | ---: |
| Submit `_existing -> lookup` full scan/recovery fsync | 1 | 1 |
| Submit `check_lease` full scan/recovery fsync | 0 | 1 |
| Submit `append_command` full scan/recovery fsync | 1 | 1 |
| Worker `lease_guard` full scan/recovery fsync | 0 | 1 |
| Worker `finish_command` full scan/recovery fsync | 1 | 1 |
| Terminal lookup full scan/recovery fsync | 1 | 1 |
| **Total full scans/recovery fsyncs** | **4** | **6** |
| Additional authoritative append fsyncs | 2 | 2 |
| Additional SQLite index transaction commits | 2 | 2 |

Thus the fixed 500 inspections + 200 admitted sets imply at least 3200 whole
history scans/recovery fsyncs and 1400 authoritative append fsyncs/index commits
per batch, before Cancel/lease/extra lookup work. Invalid-payload rejections
occur before journal access. History-proportional work is concrete; its share
of this particular two-second stall is unmeasured.

No present pair in this table shares one continuously held OS guard. Skipping
the second `_reload` based on `_dispatch`'s host lock, cached fingerprint alone,
or unchanged mtime would drop external-writer/history validation. Likewise,
removing `_existing` would change same-ID terminal replay and could enqueue a
replayed intent because `_submit` currently ignores append's `replayed` result.

## Smallest correct follow-up

1. Keep S80 failed, including its UNKNOWN, timings, final cancellation and
   cleanup ownership. Retain the existing driver latch and assembler
   `ACCEPTED_PENDING/QUEUED` requirement (`benchmark_assembly.py:302`). No timeout,
   threshold, cap, retry-horizon, history, or workload change is justified.
2. Add focused **local** client diagnostics for a fixed I/O phase enum
   (`request`, `response_headers`, `response_body`) and allowlisted exception
   category (`timeout`, `connection`, `http`, `other_os`). Persist that bounded
   diagnostic with the failure row. Keep wire Response status/code/shape and
   transport retry behavior unchanged. Do not serialize arbitrary exception
   strings, request headers, bearer, raw request, or session objects.
3. Reducing disposable-index commit overhead is a smaller candidate than
   redesigning admission; the separate index worker owns that evaluation.
   Retain authoritative JSONL validation/fsync and poison/rebuild cache behavior.
   Supplement it with bounded phase timings if needed to establish causality.
4. If scan cost remains limiting, a proper composition must hold **one** OS
   guard across a fresh snapshot, existing-ID decision, required lease checks
   and append. It must preserve ordering, dedupe return handling, readback,
   append durability, and guard-entry/exit UNKNOWN classification. This requires
   an explicit scoped API; there is no safe one-line reload bypass. Do not call
   decorated journal methods recursively inside the present non-reentrant
   `lease_guard`, or use `__wrapped__` to silently bypass its protections.

Focused regression proposals, not executed:

- Inject `TimeoutError`, connection loss, and HTTP failure separately at each
  client I/O phase: exact UNKNOWN reply remains; fixed local diagnostic has no
  secrets; no retry; success clears any previous failure diagnostic.
- Keep lost-submit driver test and assert original receipt/status gap survive;
  the producer remains latched and its cleanup owner retained.
- If optional same-ID failure reconciliation is added, keep the original failed
  receipt and timings, never resubmit or convert it into benchmark acceptance,
  and use a fixed budget with mismatch/continued-UNKNOWN tests.
- For any future composite guard, prove a second journal instance cannot
  interleave between dedupe/lease/admission; external append/replace/corruption
  is seen at the next guard; stale lease and expired-new-request reject; valid
  existing terminal replay still works after deadline/Stop; same ID never queues
  a second job; all entry/append/exit I/O failures preserve correct UNKNOWN.

No acceptance, gate tick, or independent critic verdict is issued here.
