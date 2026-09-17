# GT06 S73 implementation investigation: S71 admission failure

Date: 2026-09-18, Asia/Saigon. Role: implementation investigator, not acceptance critic. Read-only inspection of existing source and raw evidence; no engines, tests, source edits, process termination, or acceptance changes. This report is the sole authored artifact.

**Finding:** `ADMISSION_UNKNOWN` is the benchmark driver's response to a lost HTTP submission receipt. The exact request was durably admitted and committed. There is no evidence of an admission rejection, exhausted journal capacity, expired lease/session, or a journal lock failure. A roughly two-second client timeout is strongly indicated; the raw evidence cannot identify the underlying socket exception or attribute its elapsed time conclusively to disk, scheduler, hashing, or lock wait.

## Evidence and exact failing call

Raw root: `studio/.local/reviews/gt06-s71-campaign-01/run-00-attempt-01` within `8-9-hh3d-3`.

- Frozen source: `bb881a4ad594144f0bc70a580736578942f3977f`; declared closure `38a0848b68c4d6b34f1a03839008d54aa9e99a33458abaa88a939c8d2a744d86`. All 49 files in raw `source-files.json` were independently read and match their recorded SHA-256 in `source/studio/`. The five source files central to this finding also matched the working copies at inspection.
- `child-failure.json`: run `gt06-s71-campaign-01.r00.a01`, 33 completed batches; failure in zero-based batch 33, commands phase, ordinal 631 / group 63. The partial report contains 632 rows, including the failed row.
- Exact ID: `gt06-s71-campaign-01.r00.a01.b33.inspect.316`.
- Exact digest: `sha256:9fcd89ae83efa97157edb213f5952b12ee72517c5e535b63a4ecf61f8fe1f19b`.
- Submission start `576641407965` and receipt observation `576643421815` microseconds on the host monotonic clock; recorded `receipt_ms=2013.8505`, `receipt_status=UNKNOWN`, `receipt_code=CONNECTION_LOST_LOOKUP`, and empty `lookup_attempts`.
- Journal lines **47187 and 47188** contain that same ID and digest: `ACCEPTED_PENDING/QUEUED`, followed by `COMMITTED/READBACK_CONFIRMED`. Terminal readback is `{effect_count:6726, revision:"rev-6726", value:6726}`, with result hash `sha256:1125a23f65361b032dc3d60a1d3f079b94df6dd5f68e207a5b2fd373b21f93bf`. This inspection does not increment the effect count. The same digest on the previous inspection is expected because the operation, target and empty payload are identical; command IDs remain distinct.
- Journal creation time for the failed request is `1789678438326`; its terminal row retains that creation time. The journal does **not** record a distinct terminal completion timestamp, so do not infer an exact completion time from it.
- `host-owner/process-exit.json` captures actual wrapper exit 1. Its cleanup record reports Job active count 0, zero observed, closed, and no retained handles. The campaign remains failed.

SHA-256 evidence bindings:

| Relative raw file | Bytes | SHA-256 |
| --- | ---: | --- |
| `child-failure.json` | 729944 | `5c858e32b9c55df70e46eb12bed7ea657e5d8314f7e7670a54d03089e31f20e3` |
| `commands/commands.jsonl` | 33224600 | `1fa1c75a60335c0811506c46ccd8e2af54fe3066b67d12d9a33e5e7848127c83` |
| `source-files.json` | 4941 | `478f879161938837df151dec5847fab99596081f60d29a78f0d15e046fb3f865` |
| `host-owner/stderr.txt` | 2133 | `1a48398bb4afa878962bd0edf16f1de8ca9bb550e8373b0b4b60fb8135cbfef0` |

## Causal path and excluded explanations

`studio/host/core/transport.py:857` sets `FixtureClient`'s default timeout to 2.0 seconds. `_call` at lines 862–884 converts any `OSError` or `HTTPException` into client-side `UNKNOWN/CONNECTION_LOST_LOOKUP`. It preserves neither exception subtype nor whether failure occurred during connect, headers, or response body. The observed 2013.8505 ms closely matches this timeout but is insufficient to prove `TimeoutError` specifically.

`studio/tests/replay/benchmark_commands.py:207–226` submits once, retains that response, and requires `ACCEPTED_PENDING`. The unknown receipt immediately raises `ADMISSION_UNKNOWN`, before `_terminal` can perform a lookup. Existing `_terminal` reconciliation applies only after an accepted submission; it does not cover a lost submission receipt. The existing `test_failure_keeps_partial_row_and_latches_no_retry` deliberately requires this fail-closed behavior for dropped submission responses.

On the server, `_submit` (`transport.py:623–658`) appends the durable pending receipt before queueing and returning. The matching final journal records prove that this path and terminal readback completed, irrespective of the client receiving the receipt.

| Candidate cause | Existing evidence |
| --- | --- |
| Journal byte/record cap | 33,224,600 bytes versus 67,108,864-byte cap; 47,188 records versus 100,000-record cap. There are 34 lease records, 47,154 command records, and zero pending commands at the final snapshot. All record checksums independently recomputed successfully. Capacity was available, including a terminal reservation. |
| Lease expiry | Last lease epoch 34 expires at `1789679120324`, 681,998 ms after the failed request's recorded creation time. Moreover, `fixture.inspect` does not use the write lease. |
| Session/request expiry | Session rotation occurs at batch start with 900,000 ms TTL; partial batch lasted 219.276 seconds. Requests use a 10,000 ms deadline. Successful durable completion also excludes expiry rejection of this request. |
| Retry horizon | Failed command expiry is `1789764838326`, exactly 24 hours after creation; no expired/tombstone record. |
| Journal lock failure | No `JOURNAL_LOCKED`, `JOURNAL_LOCK_FAILED`, or admission rejection is recorded for this ID; it reached COMMITTED. The zero-length `.guard` is the normal permanent lock inode, not evidence of a stale lock. Temporary lock wait may contribute latency, but the evidence contains no timings to prove or exclude it. |
| Corruption or duplicate mutation | All 47,188 checksums match; failed inspection's expected snapshot matches its predecessor and has no extra effect. This is checksum/state corroboration, not a claim to have rerun the accepted journal validator. |

## Latency growth and benchmark implications

The verified-journal wrapper reads and hashes the entire history under the accepted writer lock on every journal operation, then fsyncs an unchanged verified snapshot. It reduces JSON replay/allocation but retains history-proportional I/O and hashing. Transport dispatch and worker completion also serialize under the host lock. These mechanisms and the recorded trend establish a plausible scaling bottleneck; the run lacks per-phase timing to claim an exact wall-time attribution.

Derived diagnostic figures use recorded arrays and linear type-7 p95; no workload was replayed:

| Batch | Complete command rows | Inspection p95 ms | Command phase seconds |
| --- | ---: | ---: | ---: |
| 0 | 1000 | 63.5410 | 37.242 |
| 4 | 1000 | 96.3869 | 66.964 |
| 10 | 1000 | 149.8099 | 108.773 |
| 20 | 1000 | 242.7261 | 183.168 |
| 30 | 1000 | 437.6779 | 276.961 |
| 31 | 1000 | 522.1038 | 302.612 |
| 32 | 1000 | 497.2096 | 293.517 |
| 33 partial | 631 plus failed row | 689.4383 over 316 completed inspections | 219.276 |

The profile pools inspection latency across all 30 measured batches within each complete run (`benchmark_profile.py:292–303`); batch 31 exceeding 500 ms alone is not a run verdict. Partial batch 33 has `max_status_gap_ms=2337.9602`, exceeding the unchanged 2000 ms maximum. A completed run retaining that observation would fail the gap gate.

The assembler separately requires every successful command's submission receipt to be `ACCEPTED_PENDING/QUEUED` (`benchmark_assembly.py:301–302`). A later COMMITTED lookup cannot be relabeled as the missing receipt. The 33 completed batches and partial batch cannot be joined to another attempt or source to create a valid 35-batch run.

## Minimal corrective work and regressions

1. **Keep S71 failed and preserve raw files.** Do not raise the client timeout, profile thresholds, limits, or retry horizon merely to make this attempt pass. Do not replace UNKNOWN with an accepted receipt or remove its timing.
2. **Improve failure diagnosis without changing acceptance.** On exact `UNKNOWN/CONNECTION_LOST_LOOKUP` from submit, optionally perform bounded same-ID lookup solely as failure reconciliation. Retain original receipt status/code/duration and failure latch, record actual lookup attempts/digest/readback separately, and never resubmit or increment effects. Cleanup ownership must survive reconciliation failure. Other UNKNOWN codes must remain fail-closed. A safe exception-class/phase diagnostic would disambiguate timeout from disconnect without serializing credentials or arbitrary exception text.
3. **Address the measured latency path before a new frozen campaign.** Instrument hash-read, fsync, accepted lock wait, dispatch, and reply phases in a separate diagnostic. Optimize only within a reviewed equivalence-preserving wrapper: retain exact-byte validation, accepted lock/recovery/durability behavior, capacity reservation, receipt/tombstone history, and external-change detection. No mtime-only trust, journal reset, skipped fsync, or increased cap. This report identifies the likely path; it does not claim a proven optimization.
4. **Focused regression coverage:** lost submit after durable admission must retain UNKNOWN, lookup the same ID, show one terminal/effect, and still fail benchmark assembly; lost submit before dispatch must not resubmit; repeated lookup uncertainty must stop at the fixed reconciliation budget and retain ownership; wrong ID/digest must reject; original measured latency/status gaps must survive failure reporting. Retain the existing lost-submission failure test and assembler receipt check. Any journal optimization also needs external append/replace/truncate/corruption, lock, policy-change, capacity-reservation, and durability-failure regressions already protecting `VerifiedJournal`.
5. **New acceptance evidence requires a fresh source freeze/run ID and the unchanged complete campaign.** A command-only scaling diagnostic near 47,000 records can identify latency before another long native run, but it is supplemental and cannot stand in for the required 10 × 35 workload.

No acceptance or critic verdict is issued by this investigation.
