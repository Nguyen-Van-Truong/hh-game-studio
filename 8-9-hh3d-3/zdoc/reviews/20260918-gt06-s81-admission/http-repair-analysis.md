# S81 supplemental HTTP repair comparison

AUTHORITY=0. Read-only analysis of sealed `http-probe/result-01` and `result-02`;
no tests, source changes, engines, new probes, or acceptance verdict. Exact
derived metrics, evidence hashes and verification results are retained in
`http-repair-analysis.json`.

**Probe 02 removed the measured disconnect-hook contention while preserving
the complete supplemental workload.** Its maximum after-dispatch hook duration
fell from 342.4381 ms to 0.0343 ms; admitted receipt p95 fell from 202.680400 ms
to 120.353865 ms. Total batch duration did not improve: 125.417286 s became
126.490066 s, an increase of 1.072780 s (0.8554%). Whole-history journal work
remains substantial, and legitimate terminal lookup waiting remains.

Both runs completed one 1000-command batch over the copied 15.6 MB history, with
500 inspections, 300 expected validation rejections, 200 admitted mutations,
final effect count 200, and the original auxiliary Cancel ending with no effect.
Neither reproduced S80's two-second transport failure. These are instrumented,
supplemental mock-fixture runs; neither is a full campaign or GT-06 acceptance.

## Timing comparison

Percentiles use linear type 7 over every retained command row. Status-gap p95
uses the retained integer-microsecond response sequence. The reported maximum
gap uses the driver's higher-resolution clock; recomputation from the retained
sequence agrees within 0.001 ms. Phase p95 cannot be reconstructed from phase
aggregates and their three retained slowest spans.

| Metric | Probe 01 | Probe 02 |
| --- | ---: | ---: |
| Exact batch elapsed | 125.417286 s | 126.490066 s |
| Child report start-to-end wall interval | 136.428796 s | 137.380213 s |
| All 1000 receipt p95 | 186.465705 ms | 108.199340 ms |
| All receipt maximum | 452.772600 ms | 354.387400 ms |
| Reported maximum host response gap | 452.986100 ms | 354.610400 ms |
| Host response gap p95 | 180.375300 ms | 118.131000 ms |
| Gap count, including start/end observations | 1704 | 1705 |
| Inspect receipt p95 / max | 142.063930 / 208.499100 ms | 89.278030 / 131.485200 ms |
| Inspect terminal p95 / max | 179.644270 / 254.783100 ms | 182.517655 / 410.970600 ms |
| Admitted receipt p95 / max | 202.680400 / 452.772600 ms | 120.353865 / 354.387400 ms |
| Admitted terminal p95 / max | 251.896400 / 485.046800 ms | 243.155910 / 477.748200 ms |
| Rejection receipt p95 / max | 22.556460 / 27.282300 ms | 22.847625 / 26.986300 ms |
| Auxiliary Cancel terminal | 128.017200 ms | 134.934500 ms |

The child report wall interval includes setup/import/replay/cleanup before and
after the measured batch; it is not a separately captured process lifetime.
Receipt p95 is 40.62% lower for admitted commands and 41.97% lower across all
commands. These describe the observed pair, not an estimated future speedup.
Inspection terminal maximum increased, underscoring that earlier admission ACK
does not eliminate the work required to produce terminal readback.

Probe 02 has one additional lookup: `gt06-s81-http-probe-02.b0.admitted.146`
first returned `ACCEPTED_PENDING/QUEUED`, then `COMMITTED/READBACK_CONFIRMED`,
with the same request digest. It was not a retry of submit or an UNKNOWN. This
accounts for 701 versus 700 mix lookups, plus one Cancel lookup in each run.

## Hook contention and remaining costs

All sums below are inclusive spans that can overlap through nesting and
concurrent handler/worker threads. They cannot be added as disjoint wall time.

| Instrumented phase | Calls 01 / 02 | Sum 01 / 02 | Maximum 01 / 02 |
| --- | ---: | ---: | ---: |
| Snapshot with recovery fsync | 3207 / 3208 | 93.7540454 / 95.4163892 s | 272.8374 / 286.8566 ms |
| Canonical fsync | 4610 / 4611 | 2.2785640 / 2.6942528 s | 245.9026 / 259.6473 ms |
| Command dispatch | 1001 / 1001 | 52.5222463 / 53.6032768 s | 144.2021 / 352.7463 ms |
| Lookup dispatch | 701 / 702 | 21.6640078 / 63.9056557 s | 76.9333 / 330.0910 ms |
| Fault hook before dispatch | 1705 / 1706 | 23.4054161 / 0.0032777 s | 120.2676 / 0.0175 ms |
| Fault hook after dispatch | 1405 / 1406 | 15.4789912 / 0.0029348 s | 342.4381 / 0.0343 ms |
| Fault hook before reply | 1405 / 1406 | 3.1186989 / 0.0010522 s | 92.5853 / 0.0148 ms |
| Fault hook after reply | 1405 / 1406 | 25.0282468 / 0.0024604 s | 122.9196 / 0.0148 ms |
| Response send | 1705 / 1706 | 1.0870509 / 1.1352239 s | 3.8837 / 4.9930 ms |

The hook duration includes mutex acquisition and the tiny hook body; it is not
a separately instrumented pure mutex-wait counter. In the normal unarmed run,
the old hook's body only checks the configured phase. The new maximum of
0.0343 ms therefore supports removal of that response-path contention mechanism.

Probe 01's slowest receipt, admitted ordinal 599, lasted 452.7726 ms. Its
after-dispatch hook spanned 616340676058–616341018497 monotonic microseconds;
that interval contains a worker snapshot of 272.8374 ms and its canonical fsync
of 245.9026 ms. Receipt observation followed the hook's return by 0.699 ms.

Probe 02's slowest receipt, admitted ordinal 558, lasted 354.3874 ms. Its command
dispatch spanned 617094058062–617094410808 microseconds (352.7463 ms), enclosing
a command-thread snapshot of 286.8566 ms and canonical fsync of 259.6473 ms.
Receipt observation followed dispatch's return by 0.690 ms. This remaining
outlier lies in required admission work, not an observed long disconnect hook.

Lookup dispatch now contains more waiting: its sum rose to 63.905656 s, while
the hook sums collapsed. This is consistent with earlier ACK delivery allowing
the client to request terminal lookup while the worker is still completing.
Do not add the old hook sums or claim they represent recoverable throughput.

The 3208 Probe 02 snapshots read at least **50,001,200,072 bytes** because every
scan includes the original 15,586,409-byte prefix; actual reads are larger as
the journal grows. Mean snapshot duration is 29.743263 ms. Snapshot sum equals
75.43% of batch duration. Subtracting even all canonical fsync time leaves an
inclusive lower bound of 92.722136 s in snapshot read/hash/stat work, rather
than a measurement of SHA CPU time. SQLite's internal sync is separate from
the wrapped Python `os.fsync` calls. Canonical fsync count is exactly 3208
recovery barriers plus 1403 appended records; Probe 01 had one fewer lookup
and therefore one fewer snapshot/fsync. No barrier was removed.

## Independent evidence and source checks

All recorded hashes were reread from disk, without importing probe/runtime
modules or rerunning their validators:

- **Probe 01:** 12/12 captured evidence files, 355/355 frozen Python files and
  12/12 loaded module bindings match. After-import and after-shutdown loaded
  maps match. Its original files were not modified.
- **Probe 02:** 12/12 captured evidence files, 358/358 frozen Python files and
  13/13 loaded module bindings match. After-import and after-shutdown maps match.
  No evidence file is outside the capture hash map, apart from `capture.json`
  itself, whose hash is separately recorded in this analysis.
- Both owner-source hashes, frozen generic runner hashes, driver hashes, source
  manifest hashes, command-batch hashes and the referenced Python executable
  hash match their recorded bindings.
- Both copied journals have **23573 independently checked checksum records**,
  retain the exact original prefix, and append exactly 1403 records. The
  original S80 journal still hashes to
  `4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a`.

| Binding | Probe 01 SHA-256 | Probe 02 SHA-256 |
| --- | --- | --- |
| Source manifest | `74e2b3f522d85f55e07d5789a814c447989d6e9eccd044732cfdc78674466ff8` | `3e0320f2b75d6a019a0c246abefbfefc25da9c1c362df7f603e52167da992afc` |
| Command batch | `17b2ad14f24bbaa2f73eac7551470c467a97b66d2e50d17ffbfd33b61a1cabcb` | `57ddf49c4ca5baf77b667d5587441cb6efbbe9f391084099966f5d137de36b1c` |
| Child report | `f75389625b9a326118e4cc8a1b5e774a5823b1fefb0ceecef9b721e589e4c56a` | `445b07cf14b8a7b6c3a60427d6017a2bb5c8d7a382231a80a0f76e3c9678a770` |
| Capture | `e03cc24376bf7b11255b3c9f2f0e08a3cd96527e2a3df92df8bb3aa492532398` | `6032cfc212a5a33f0a3702f887c307a8a4fafab4e40acdfa8bcf14388d07ea63` |

Probe 02 uses the benchmark-local host/client subclasses. Its accepted
`core/transport.py` is restored to SHA-256
`1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0`.
The full frozen selection differs in eight entries, including unexecuted tests
and campaign cleanup code; the exact list is in the JSON analysis. Journal
modules are unchanged between these selections. The probe driver changed only
which class owns instrumentation/diagnostic lookup, so the subclass is actually
measured; it did not change the mix, delays, journal copying or timing labels.
These are different source selections, not retroactive labels for the same run.

## Recorded exits and cleanup

Probe 01 records target PID 39776 exit 0 and helper PID 42432 exit 0; Probe 02
records target PID 7060 exit 0 and helper PID 53616 exit 0. Both captures report
`gated_job_kill_on_close`, `tree_verified=true`, `timed_out=false`, and unchanged
source. Each target PID/exit agrees with its separate host record and child PID.

Both child reports record producer closed, all host threads stopped, listener
fds -1, released observer handle and released journal-index owner. No private
index directory remains on disk. This analysis verifies those recorded exit
and ownership bindings; it does not claim a new live process inspection.

The two-second client timeout, five-second terminal budget, 210-second
cooperative bound, 240-second owner bound, FULL/DELETE index settings, journal
history validation and durability barriers remain in the frozen probe paths.
The comparison supports the narrow ACK contention repair. It does not resolve
S80's exact timeout cause, predict rare-tail reliability, establish campaign
throughput, or replace the required complete GT-06 campaign and reviews.
