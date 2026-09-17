# Campaign02 first measured sample: host retention analysis

Bounded static/evidence review of
`gt06-s70-campaign-02/run-00-attempt-01`, frozen closure
`21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`.
No native execution, tests, task retry, source edit, receipt/journal clearing,
threshold change or failing-artifact rewrite was performed. This is diagnosis,
not an acceptance verdict.

## Actual failure

**No host counter failed. The observed failure is editor objects +476.**
The batch4 baseline and first measured batch5 show:

| Counter | Baseline4 | Measured5 | Outcome under unchanged predicate |
| --- | ---: | ---: | --- |
| Host RSS bytes | 26,693,632 | 27,267,072 | +573,440 bytes / +2.148%; below10% limit |
| Host held handles | 194 | 194 | Equal; passes |
| Host objects/resources | N/A | N/A | Explicit `NOT_APPLICABLE_PYTHON_HOST`; skipped by contract |
| Editor objects | 72,866 | 73,342 | **+476; fails nonincrease requirement** |
| Editor resources | 6 | 6 | Equal; passes |
| Editor held handles | 555 | 555 | Equal; passes |
| Editor RSS bytes | 223,989,760 | 181,624,832 | Falls; passes |

`run_benchmark_campaign.py:256–271` visits host before editor, skipping only
the two canonical host N/A counters. Its exact predicate is
`value * 100 <= baseline * 110` for RSS and `value <= baseline` otherwise.
The only violating pair above is editor objects. Both status-gap values
(605.98ms and607.484ms) are below2000ms too.

`child-failure.json` records `CAMPAIGN_RETAINED_COUNTER_GROWTH`, six published
batches, and batch5/joint_observation. The traceback reaches `screen_sample`
at runner line670, after writing sample-preview05. Its generic error code
does not name the role or counter. The parent records
`BENCHMARK_WRAPPER_EXIT`, which is the downstream nonzero host exit, not the
original measurement failure. Five warmups plus one measured failing sample
are not one successful run.

The six small joint records corroborate the host trend:

| Batch | Host RSS bytes | Host handles | Editor objects |
| --- | ---: | ---: | ---: |
| 0 | 36,409,344 | 194 | 71,261 |
| 1 | 38,674,432 | 194 | 71,497 |
| 2 | 34,390,016 | 194 | 71,945 |
| 3 | 27,377,664 | 194 | 72,400 |
| 4 | 26,693,632 | 194 | 72,866 |
| 5 | 27,267,072 | 194 | 73,342 |

This does not establish whether native objects are permanently retained or
still pending destruction at the claimed quiescent boundary. That needs the
separate native lifecycle investigation. Python allocations cannot explain
Godot's native object counter.

## Host retention and handle ownership

Paths below are relative to `8-9-hh3d-3/studio/`; line references describe the
source read for this report.

| Area | Observed ownership / retained data | Interpretation |
| --- | --- | --- |
| `tests/replay/benchmark_commands.py:68–91` | NativeObserver constructs one ProcessProbe for the host and reuses it across samples. | No process handle is opened per sample. |
| `host/replay/process_probe.py:20–65,72–95,97–108` | One checked OpenProcess handle; sample allocates local Memory/window-list/callback values. GetProcessHandleCount reads the retained handle. CloseHandle success clears it; checked failure retains it. | Per-sample ctypes values are transient. Handle194 throughout all six observations gives no evidence of per-sample leakage. |
| `tests/replay/benchmark_commands.py:94–117,128–140` | One resident host and journal, one client/credential reference. Client changes per batch; lease continuity and old-secret redaction history are retained. | Replacing FixtureClient does not discard persistent sockets; it owns none. |
| `host/core/transport.py:855–893` | `_call` creates one HTTPConnection and closes it in `finally`. | Calls have explicit socket cleanup, including response/error paths. |
| `host/core/transport.py:234–263,331–352,707–711` | Two listeners, three persistent host threads, bounded connection slots, terminal `_jobs` entries removed. | Fixed host service ownership; not one retained thread/job per command. |
| `host/core/transport.py:102–159,303` | Session rotation preserves all issued secrets for redaction, capped at64; diagnostics are a deque capped32. | Necessary bounded security/diagnostic retention. Removing it would change correctness, not repair the observed native failure. |
| `tests/replay/benchmark_commands.py:269–320` | Per-batch report owns command rows; response timestamps reset in `finally`. Caller receives report, producer keeps no archive of reports. | Bounded to the current batch on successful execution. Partial report retained on exception is deliberate evidence. |
| `tests/replay/run_benchmark_campaign.py:615–619,665–675` | Report is written then deleted and collected; decoded assembly objects/sample/native buffers are deleted and collected each batch. | Full command/native bodies are not appended to a35-batch in-memory history. |
| `tests/replay/run_benchmark_campaign.py:99–137,578,659–663` | NativeLog retains one latest heartbeat and <=256 nonheartbeat markers; `batches` retains small artifact references, not raw report bodies. | Metadata grows within known campaign bounds; cannot account for Godot object growth. |
| `host/core/journal.py:73–90,104–107,386–396`; `host/replay/journal_index.py` | Disk receipt bodies with exact record offsets and latest-record command index. PackedOffsets uses two uint64 words per record; ProjectCommandIndex retains command IDs and integer indexes. | Some real Python retention grows with history by design. Every receipt/tombstone remains recoverable; no eviction/reset proposed. |
| `host/replay/verified_journal.py:28–56,63–80,83–127` | Reads/hashes journal in64KiB chunks under accepted lock; stores digest/size/identity/policy and exact indexes. | Temporary read buffers are bounded; no full-byte history retained by this optimization. |

The host sample comes after command-report deletion/GC but while the current
native batch JSON is decoded for validation. This is a fixed100-cycle batch
allocation, not an expanding list of previous batches. The last `cycle` and
`timing` loop locals survive until overwritten, but retain at most one pair,
not all100 or all prior batches. Startup/import metadata and the frozen source
map likewise remain stable during the run.

RSS is specifically Windows `PROCESS_MEMORY_COUNTERS.WorkingSetSize`, as read
by ProcessProbe. It is not a direct measurement of live Python allocation
bytes or committed private bytes. Its large warmup rise/fall and +0.55MiB
baseline-to-first-sample change cannot identify a particular retained object.
Required journal indexes, allocator retention and working-set residency can
all contribute. No allocation tracing was run, and no claim is made that the
host would pass every later batch. Current evidence supports **no host growth
failure at batch5**, not a proof of zero host retention.

## Actionable recommendation

Do not modify host retention or its limits to address this failure. Do not
clear journal/receipts, rotate a new host per batch, empty security history,
trim the working set, subtract counters, or raise the baseline/threshold.
The corrective lifecycle change belongs to the native editor object owner
identified by the separate investigation; it must preserve real operations
and the same five-warmup/thirty-measured profile.

One precise, optional host-side diagnostic improvement would prevent this
misclassification without changing any predicate: when `screen_sample` rejects
a counter, raise the existing BenchmarkJobError code with a small structured
attribute containing `role`, `counter`, `baseline`, `observed`, and `index`.
The child failure writer can persist that attribute under a versioned or
explicitly optional diagnostic field. Keep the error code and predicate
unchanged, never put this field into a successful measurement result, and
preserve the original exception/cause. For this evidence the attribute would
be `{role: editor, counter: objects, baseline: 72866, observed: 73342, index: 5}`.
This is error attribution only, not a fix for retained native objects. No
source patch is supplied because no host retention defect is substantiated by
the failing sample, and coordinator owns the native integration.

## Failure cleanup and evidence anchors

Host-owner cleanup records `closed=true`, untainted Jobclosed/zero,
active_count0, no retained Job handle, wrapper exit1 and released wrapper
process handle. Editor-owner cleanup records the same checked closed/zero and
released handles, with `BENCHMARK_CLOSED_BEFORE_FINISH`, wrapper exit2.
Parent failure says `owner_closed=true`, `owned_tree_zero=true`,
`cleanup_error=null`. These records describe truthful failure cleanup;
they are not natural-success capture proof or authority to retry automatically.

Raw root (unchanged):
`studio/.local/reviews/gt06-s70-campaign-02/run-00-attempt-01/`.

| Artifact | SHA256 read during this review |
| --- | --- |
| sample-preview-04.json | `593307e15fb49b3695baea64c36ef6c9eb46b0c4cf87fcb3e005890f84d91e14` |
| sample-preview-05.json | `2f5a7039b99f390dd678734fa148509ed79709522c2330ab00f6286b98d6a2da` |
| child-failure.json | `d7bcb91140e7b854edf107861a5b4e46734e0bdd49c9cdf2616a0f284eefad7a` |
| parent-failure.json | `bb8c672ac79412c26ed3a366b7ea4bd8a5f6e45af5677144d4b10c5adf43bb29` |

Only the two small preview JSONs, six joint JSONs, failure/cleanup records,
stderr tail, source files and these small-artifact hashes were used. Full
command/native raw shards were not scanned or rewritten.
