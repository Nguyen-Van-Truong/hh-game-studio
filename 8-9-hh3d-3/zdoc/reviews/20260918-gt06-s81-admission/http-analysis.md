# S81 supplemental HTTP analysis

AUTHORITY=0; no benchmark or GT-06 acceptance claim. Analysis only: no further
runs, runtime edits, or edits to sealed `http-probe/result-01` artifacts.

The supplemental batch completed all 1,000 commands in **125.417 s**, with
500 inspections, 300 expected rejections and 200 admitted mutations. It made
700 mix lookups plus the original auxiliary Cancel lookup; effects ended at
200 and Cancel reported no effect. **No two-second failure was reproduced**:
maximum host response gap was 452.986 ms and `transport_failure` is null.

Target PID 39776 and helper PID 42432 both have captured exit 0; no timeout,
owned tree verified. Both listener fds are -1, host threads stopped, observer
handle and journal index owner released, and no private index directory
remains. The copied journal retained the original prefix SHA-256
`4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a`
and appended exactly 1,403 records. Original journal hash is unchanged.

## Latency and measured work

Percentiles below are calculated from every command row using linear type 7.
Inspect latency includes terminal readback; admitted latency is its pending
receipt; rejection latency is its validation response.

| Kind | n | p50 | p95 | Maximum |
|---|---:|---:|---:|---:|
| Inspect terminal | 500 | 152.586 ms | 179.644 ms | 254.783 ms |
| Admitted receipt | 200 | 175.985 ms | 202.680 ms | 452.773 ms |
| Rejected receipt | 300 | 2.067 ms | 22.556 ms | 27.282 ms |

Admitted terminal readback p95/max were 251.896/485.047 ms. Inspect pending
receipt p95/max were 142.064/208.499 ms. Auxiliary Cancel terminal was 128.017 ms.

| Instrumented phase | Calls | Sum | Maximum |
|---|---:|---:|---:|
| Full journal snapshot, including recovery fsync | 3,207 | 93.754 s | 272.837 ms |
| Canonical fsync, recovery and append | 4,610 | 2.279 s | 245.903 ms |
| Command dispatch | 1,001 | 52.522 s | 144.202 ms |
| Lookup dispatch | 701 | 21.664 s | 76.933 ms |
| Fault probe before dispatch | 1,705 | 23.405 s | 120.268 ms |
| Fault probe after dispatch | 1,405 | 15.479 s | 342.438 ms |
| Fault probe before reply | 1,405 | 3.119 s | 92.585 ms |
| Fault probe after reply | 1,405 | 25.028 s | 122.920 ms |
| Response send | 1,705 | 1.087 s | 3.884 ms |

These spans overlap through nesting and concurrent request/worker threads;
they must not be added. Fault-probe totals are not a predicted recoverable
wall-time improvement. Phase p95 cannot be reconstructed from the retained
aggregates and three slowest spans.

Full snapshots account for 74.75% of batch duration and read at least
49,985,613,663 bytes of history, since every scan includes the initial 15.6 MB
prefix. The 4,610 canonical fsyncs equal 3,207 recovery barriers plus 1,403
appends. Even subtracting *all* canonical fsync time from snapshot time leaves
at least 91.475 s in snapshot read/hash/stat work. This is an inclusive timing
bound, not a measurement of SHA CPU time. SQLite's internal sync is separate.

## Concrete ACK delay

The slowest receipt was `gt06-s81-http-probe-01.b0.admitted.119`, ordinal 599,
at 452.773 ms. Its after-dispatch fault probe spans monotonic microseconds
616340676058–616341018497 (342.438 ms). Entirely inside that interval are a
worker snapshot at 616340719631–616340992469 (272.837 ms), and canonical fsync
at 616340746256–616340992159 (245.903 ms). The receipt arrives only **0.699 ms
after the fault probe returns**.

Frozen `transport.py:473` takes the main host lock even when no disconnect
fault is armed; `_execute` performs lease/readback journal work while holding
that same lock. The fixed fault probe itself merely compares the configured
phase in this normal run. The timing and source therefore support an avoidable
ACK delay behind worker journal I/O in this run. They do not identify the exact
cause of the historical S80 two-second event.

The smallest supported next candidate is to isolate optional one-shot
disconnect-probe synchronization from the main host worker/dispatch lock.
A dedicated fault lock can preserve atomic phase matching and at-most-once
consumption without waiting for unrelated journal/effect work. Keep the journal,
lease, authorization and effect locks unchanged, together with FULL/DELETE,
full-history verification, fsync, current budgets, limits and UNKNOWN policy.
Required regressions: inactive probe does not await a worker-held main lock;
concurrent matching probes consume one shot once; unmatched phases do not
consume it; existing before/after dispatch/reply fault and uncertainty cases
retain their behavior. This recommendation is not a fixed-campaign verdict.

## Provenance

The full frozen selection contains 355 Python files; all hashes independently
match `checks-01/source`. All 12 loaded `studio.*` module entries match those
hashes, and the after-import/after-shutdown module maps are identical. All 12
files listed in sealed `capture.json` independently match their hashes.
The separate owner binds the Python executable, generic process owner and
driver. Source-manifest SHA-256 is
`74e2b3f522d85f55e07d5789a814c447989d6e9eccd044732cfdc78674466ff8`;
batch SHA-256 is
`17b2ad14f24bbaa2f73eac7551470c467a97b66d2e50d17ffbfd33b61a1cabcb`.
Exact timings, closure, cleanup and input hashes are in `http-analysis.json`.
