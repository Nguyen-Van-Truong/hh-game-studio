# GT-06 S81: diagnose S80 admission uncertainty

AUTHORITY=0. GT-06 is still in progress. This directory does not contain an
acceptance verdict or independent critic signatures.

S80 stopped at batch 15, inspect command 400, with `ADMISSION_UNKNOWN` after
2,003.3888 ms. Its exact journal contains pending followed by cleanup's
`CANCELED_BEFORE_APPLY/no_effect`. There are 15 complete prefix batches and no
complete run. The precise socket failure stage was not recorded, so this is
not proof of an index error, ObjectDB growth, or a particular I/O stall.

`failure-summary.md` and `failure/` preserve the raw failure, source bindings,
cleanup observations and explicit missing evidence. Preservation manifest:
`591c4086394c1c1086234b84526378f3899b860488bc12509781dcb2d13a560b`.
The initial collector's incorrect immutable-scene assertion and the corrected
continuation remain visible. No raw data was repaired or overwritten.

`index-analysis.md` / `.json` describe a four-arm diagnostic on copied
history. Disabling synchronization for the disposable index reduced SQLite
COMMIT cost but did not improve whole-operation latency. That configuration
change was rejected; FULL/DELETE and canonical JSONL fsync remain unchanged.
The original and copied journals remain local; selected reports, scripts and
hashes are sufficient to reproduce the supplemental comparison.

The first diagnostic snapshot (`checks-01`, not the final source) added a
bounded local client failure observation: fixed endpoint, request/getresponse/read stage, error category,
and elapsed time. It never records exception text, credentials or payloads.
UNKNOWN wire semantics, timeouts and retry behavior are unchanged. A failed
command batch retains its own copy. This is observability, not a latency fix.

`checks-01/`: **141/141** affected protocol, transport, recovery, producer,
assembly, verified-journal, index-fault and service tests passed. Actual child
11240 exited 0; helper 51656 exited 0; the owned process tree was verified.
The 410-file source snapshot was unchanged. `diagnostic-source.json` binds
the 50-file campaign runtime closure after loading the fixture dependencies:
`b9880d49fde90b83fe0ba018aeeabc45c274cfdc4ccdf4a2efb86d3af6be8fda`.
This differs from S80 and must not inherit S80 measurements or old signatures.

`http-analysis.md` records the first supplemental HTTP probe: all 1,000
commands completed, but a 342.438 ms pre-reply fault-hook wait enclosed worker
journal I/O. It did not reproduce S80's 2-second timeout. The second probe
uses the final benchmark-only subclasses on a fresh copy of the same history. Its timings include
instrumentation and are not full native benchmark acceptance. Keep the normal
Cancel workload, 2-second client timeout, 5-second lookup budget and all
benchmark gates. Select a repair from the observations, then remint only
affected evidence. Do not start another long campaign merely because these
unit tests are green.

Lessons: measure the complete request path before changing storage settings;
preserve failures before cleanup metadata changes; distinguish current source
from historical closures; and record natural exits separately from forced
cleanup or scheduler return codes. The old 11-hour extrapolation is withdrawn.

## Final repair source and affected checks

The diagnostic initially changed `host/core/transport.py`. Dependency review
found that doing so would invalidate the exact accepted GT05 source pin before
native replay started. The final implementation restores that file and both
existing protocol tests byte-for-byte. No accepted pin or reuse guard changed.

`tests/replay/benchmark_transport.py` derives a host whose disconnect-test
hooks use a dedicated mutex, with a synchronized local arming API. Admission,
worker, journal, Stop, and socket reply logic stay inherited. The submit-drop
fault remains the original implementation. The diagnostic client overrides
only its small `_call` method, with differential tests against the accepted
client. This isolates benchmark support code from accepted tools source.

The campaign now writes an exclusive durable terminal cleanup record after
attempting every independent close, including failed runs. Primary exceptions
and their original causes survive secondary cleanup or evidence failures.
Missing native exits remain null, independently of helper exit codes. Future
successful-run verification requires and validates this new record.

`checks-02/`: **204/204**, zero skips/failures/errors, actual child10500 exit0,
helper36760 exit0, owned tree verified. All414 captured source files unchanged.
The final 51-file campaign closure in `repair-source.json` is
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.
`checks-01` and HTTP probe01 remain explicitly older diagnostic source.

Exact per-file joins after core restoration preserve S79 backend174, GUI5 and
S69 runtime159 evidence. See `dependency-impact.md` for the verified maps;
these do not cover the new benchmark-only module or terminal cleanup path.
Those paths receive their own tests and supplemental runtime probes before a
new full campaign. No source change inherits an old benchmark PASS.

## Supplemental repair verification

HTTP probe02 completed all 1,000 commands on another copy of the same history:
actual target7060 exit0, helper53616 exit0, owned tree verified and captured
source unchanged. `http-repair-analysis.md` / `.json` compare it with probe01.
Maximum after-dispatch hook time fell from342.4381 to0.0343ms, and admitted
receipt p95 from202.6804 to120.353865ms. Batch duration was125.417286 versus
126.490066seconds: this is not a demonstrated overall throughput improvement.
Legitimate lookup/journal waiting remains; neither probe reproduced S80's
2-second timeout. These instrumented HTTP probes do not prove the native
campaign or the full ten-run performance gate.

The native cleanup probe completed on the same 51-file closure. Real Godot
reached READY before an explicit error was injected at the first command
batch. The original primary error and cause survived; the persisted cleanup
record agrees with direct observations of released producer threads,
listeners, journal index, probes, Job and wrapper handle. Observer14112 and
import34944 had actual exit0. Editor18744's natural exit is absent, as expected
for this forced path; helper33296 exit2 remains separate. No command batch,
native cycle, effect or benchmark success is claimed. See
`native-cleanup-probe/evidence/` for exact selected bytes and raw inventory.

`preflight-review.md` is a bounded implementation preflight, not a final
critic. `verify_checkpoint.py` verifies the51 runtime files and explicitly
selected Git bytes before the new campaign. The failure's scheduler task was
retired only after its terminal/no-instance readback; the post-preservation
receipt lives under `scheduler-retirement/` and does not rewrite its seal.
