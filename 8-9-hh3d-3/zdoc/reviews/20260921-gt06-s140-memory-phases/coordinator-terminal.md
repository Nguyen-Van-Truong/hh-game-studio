# S140 terminal decision

Authority 0; diagnostic only. GT06 remains in progress with zero accepted full runs.

P04 ended at 2026-09-21T06:52:12Z after 716.11 seconds. All seven original
batch screen calls returned, then the original post-assembly GC triggered the
declared prefix boundary. The 70 phase rows have zero drops. Source and execution
pins stayed unchanged, Stop was absent, and cleanup recorded no errors. The
174-entry selected exact-copy packet verifies with zero missing/hash mismatches.
The manifest is `d286c517e401b04080689d5c64b3f2cddeb4fcae3d4372b6871a9378ec5f3a72`.
This packet excludes journals/cache/assets and is not the final acceptance closure.

## What the measurement resolves

At the original batch 4→5 comparison, joint host RSS changed from 47,546,368
to 47,169,536 B (-376,832 B). Private commit at ACK increased 225,280 B and
post-assembly GC increased 323,584 B; post-GC allocated blocks increased 202.
The earlier S131 +4,534,272 B joint-RSS jump did not recur in this instrumented
prefix. Telemetry's maximum observed cost was 1,428 microseconds; no cost is
subtracted from any gate.

Artifact binding allocates roughly the raw command-file size temporarily, and
the original end-of-batch release/GC removes most of that interval's growth.
Batch 5 command-GC→post-assembly-GC private commit increased 1,290,240 B.
There is no measured abrupt batch 4→5 native/ACK/assembly retention step that
justifies changing runtime code. Page faults, private commit and RSS diverge;
this does not identify workstation pressure, a leak, or an allocator root cause.

Static review: live `assemble_sample` decodes each large command/native artifact
once; it also coexists with the campaign's validated native object until the
original release. Repeated `.value` decodes in `assemble_run` happen after the
editor exits, so they do not explain the measured live S131 sample. A cache
change is not justified as the S131 repair and could retain more memory.

## Lifecycle limits

Host 27552/helper 49348 exited 1 for the deliberate boundary; import 54836
exited 0. Editor natural target exit is UNKNOWN; editor helper 5544 exited 2.
Host/editor Jobs were observed zero and closed, wrapper handles and probes
released, and owned threads/sockets stopped. The passive observer retained
launcher 3884's actual exit 0 and native successful CloseHandle. Scheduler
state 3/result 0 was retained separately before this demand task was retired.
Neither scheduler status nor owner cleanup supplies the missing editor exit.

P01 helper failure and P03 missing-terminal interruption remain failures/gaps.
P03 cannot be resumed after its process exits; P04 obtained the unmeasured prefix
through a detached owner. No earlier partial rows were reused. Future long runs
use the detached scheduler boundary, with current identity checks after dispatch.

## Next action

The requested discriminating prefix is complete. Repeating it without a new
hypothesis would not add the missing stock evidence. Keep the runtime, native
driver, profile, workstation and gates unchanged; freeze the union dependency
and input map, then run a fresh stock formal campaign under retained supervision.
This is a readiness decision to collect the missing full workload, not a claim
that S131 is fixed. Stop at the first original failure, preserve it, and diagnose
that boundary. Do not automatically retry an unsuccessful pair.

S133 service/reviewer and S138 repair/replay proofs remain reusable only by exact
dependency. The new stock campaign must independently supply 10 fresh pairs ×35
batches and all actual successful exits, full dataset and ownership proof. Final
freeze/requirement mapping and two fresh independent critics remain mandatory.
Three requested Astra xhigh review workers again returned model-capacity errors;
coordinator completed this review, which is not an independent critic signature.
